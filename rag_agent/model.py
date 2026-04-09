"""
SQL Generator using Hugging Face Inference API.
Supports both local GGUF and HF API modes.
"""

import os
import re
import requests
from typing import Optional
from pathlib import Path

from rag_agent.config import get_config, ensure_gguf_model


def expand_sql_aliases(sql: str, schema: str) -> str:
    """
    Convert SQL with table aliases to use full table names.
    
    Args:
        sql: SQL query that may contain aliases.
        schema: Schema string to extract table names from.
        
    Returns:
        SQL query with aliases expanded to full table names.
    """
    # Extract table names from schema
    table_pattern = r'CREATE TABLE\s+(\w+)'
    tables = re.findall(table_pattern, schema, re.IGNORECASE)
    
    if not tables:
        return sql
    
    # Find aliases in the SQL (pattern: table_name AS alias or table_name alias)
    alias_map = {}  # Maps alias -> full table name
    
    # Pattern: FROM table AS alias or JOIN table AS alias
    from_pattern = r'\bFROM\s+(\w+)\s+(?:AS\s+)?(\w+)\b'
    join_pattern = r'\bJOIN\s+(\w+)\s+(?:AS\s+)?(\w+)\s+(?:ON|WHERE|GROUP|ORDER|LIMIT|$)'
    
    for pattern in [from_pattern, join_pattern]:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            table_name = match.group(1)
            potential_alias = match.group(2)
            
            # Check if this looks like an alias (short name, not a SQL keyword)
            sql_keywords = {'ON', 'WHERE', 'GROUP', 'ORDER', 'LIMIT', 'JOIN', 'AND', 'OR', 'SELECT', 'FROM'}
            if (len(potential_alias) <= 3 or re.match(r'^[tpo][1-9]$', potential_alias, re.IGNORECASE)):
                if potential_alias.upper() not in sql_keywords:
                    # Verify table_name is in schema
                    if table_name in tables:
                        alias_map[potential_alias.lower()] = table_name
    
    # Replace alias.column with table.column
    result = sql
    for alias, table_name in alias_map.items():
        # Replace alias.column with table_name.column
        result = re.sub(rf'\b{alias}\.(\w+)', f'{table_name}.\\1', result, flags=re.IGNORECASE)
    
    # Remove "AS alias" from FROM/JOIN clauses
    for alias, table_name in alias_map.items():
        result = re.sub(rf'\bFROM\s+{table_name}\s+(?:AS\s+)?{alias}\b', f'FROM {table_name}', result, flags=re.IGNORECASE)
        result = re.sub(rf'\bJOIN\s+{table_name}\s+(?:AS\s+)?{alias}\b', f'JOIN {table_name}', result, flags=re.IGNORECASE)
    
    return result


class SQLGenerator:
    """
    SQL generator using Hugging Face Inference API.
    """

    def __init__(self):
        """Initialize SQL generator with config."""
        self.config = get_config()
        self.use_hf_api = self.config.use_hf_api

        if self.use_hf_api:
            # HF API mode
            if not self.config.hf_api_token:
                raise ValueError(
                    "HF_API_TOKEN environment variable or hf_api.api_key in config.json "
                    "must be set to use HF Inference API.\n"
                    "Get your token from: https://huggingface.co/settings/tokens"
                )
            print(f"Using Hugging Face Inference API: {self.config.hf_model_id}")
        else:
            # Local GGUF mode (fallback)
            try:
                from llama_cpp import Llama
                model_path = ensure_gguf_model()
                gguf_cfg = self.config.gguf_config
                self.llm = Llama(
                    model_path=str(model_path),
                    n_ctx=gguf_cfg["n_ctx"],
                    n_threads=gguf_cfg["n_threads"],
                    n_gpu_layers=gguf_cfg["n_gpu_layers"],
                    verbose=False,
                )
                print(f"Using local GGUF model: {model_path.name}")
            except ImportError:
                raise RuntimeError("llama-cpp-python not installed. Install with: pip install llama-cpp-python")

    def generate_sql(self, question: str, schema: str, db_type: str = "sqlite", evidence: str = "") -> str:
        """Generate SQL query from question and schema.
        
        Args:
            question: Natural language question
            schema: Database schema string
            db_type: Database type (sqlite, postgresql, mysql)
            evidence: Optional hint/evidence from dataset
        """
        prompt = self._build_prompt(question, schema, db_type, evidence=evidence)

        # Debug: Print schema if enabled
        if self.config.debug_config.get("print_schema", True):
            print("\n" + "="*80)
            print("DEBUG: SCHEMA SENT TO LLM")
            print("="*80)
            print(schema[:3000] if len(schema) > 3000 else schema)
            print("="*80)
            print(f"DEBUG: QUESTION: {question}")
            print("="*80 + "\n")

        if self.use_hf_api:
            return self._generate_via_hf_api(prompt)
        else:
            return self._generate_via_local(prompt)

    def _build_prompt(self, question: str, schema: str, db_type: str = "sqlite", evidence: str = "") -> str:
        """
        Build a detailed prompt for SQL generation with strict rules.
        """
        # Check if aliases should be disabled
        disable_aliases = False
        try:
            validation_config = self.config.config.get("validation", {})
            disable_aliases = validation_config.get("disable_aliases", False)
        except Exception:
            pass
        
        # Determine dialect-specific instructions
        if db_type == "sqlite":
            dialect_notes = """- Use SQLite syntax (e.g., LIMIT offset, count is invalid, use LIMIT count OFFSET offset)
- SQLite does not support ILIKE, use LIKE with LOWER() for case-insensitive matching
- For dates, use date('now') instead of CURRENT_DATE
- Boolean values are 0 and 1, not TRUE and FALSE"""
        elif db_type == "postgresql":
            dialect_notes = """- Use PostgreSQL syntax
- You can use ILIKE for case-insensitive matching
- Use CURRENT_DATE for current date"""
        elif db_type == "mysql":
            dialect_notes = """- Use MySQL syntax
- Use LIMIT count (not LIMIT offset, count)
- For offset use: LIMIT count OFFSET offset"""
        else:
            dialect_notes = "- Use standard SQL syntax"
        
        # Alias rules based on config
        if disable_aliases:
            alias_rules = """6. **NO TABLE ALIASES**: Do NOT use aliases (AS keyword). Reference tables by their FULL names.
   - WRONG: `FROM order_items AS T1 JOIN products AS T2`
   - RIGHT: `FROM order_items JOIN products`
7. **USE FULL TABLE NAMES**: Always use complete table names like `order_items`, `products`, not `T1`, `T2`.
8. **QUALIFY COLUMNS**: Use `table_name.column_name` format to avoid ambiguity."""
        else:
            alias_rules = """6. **TABLE ALIASES**: When using multiple tables, use short aliases (T1, T2, T3) for clarity."""

        # Build evidence section if provided
        evidence_section = ""
        if evidence and evidence.strip():
            evidence_section = f"""
**HINT/EVIDENCE:**
The following hint is provided for this question. USE THIS INFORMATION to construct accurate SQL:
{evidence}

IMPORTANT: The hint above describes how to calculate or interpret the answer. Follow it carefully.
"""

        prompt = f"""You are an expert SQL query generator. Your task is to convert natural language questions into accurate SQL queries.

**CRITICAL RULES - FOLLOW EXACTLY:**

1. **USE ONLY EXISTING COLUMNS**: Look at the schema carefully. ONLY use column names that EXACTLY match what's in the schema. DO NOT invent column names or assume columns exist.

2. **COPY COLUMN NAMES EXACTLY**: Column names are case-sensitive. Copy them character-for-character from the schema.

3. **NO ASSUMPTIONS**: If a concept (like "revenue", "sales", "quantity") is not represented by a column in the schema, DO NOT create a column for it. 
   - For "revenue" or "sales": Use price, payment_value, amount, or similar numeric columns
   - For "quantity" or "count": Use COUNT(column) or COUNT(*) if no quantity column exists
   - For "top N": Use ORDER BY + LIMIT

4. **CHECK YOUR WORK**: Before outputting, verify each column name exists in the schema.

5. **AGGREGATIONS**: For "top N by X" questions, use GROUP BY with ORDER BY and LIMIT.
{alias_rules}

**DATABASE DIALECT NOTES:**
{dialect_notes}

**AVAILABLE SCHEMA:**
```sql
{schema}
```
{evidence_section}
**QUESTION:** {question}

**INSTRUCTIONS:**
1. Analyze which tables and columns are needed based on the question
2. Look at the schema and find EXACT column name matches
3. If a term like "revenue" doesn't have a direct column, find the closest match (e.g., price, payment_value)
4. Write the SQL query using ONLY those exact column names
5. Output ONLY the SQL query, no explanation

**SQL QUERY:**
```sql
"""
        return prompt

    def _generate_via_hf_api(self, prompt: str) -> str:
        """Generate SQL using Hugging Face Inference API."""
        hf_cfg = self.config.hf_config
        
        # Use the correct Hugging Face router endpoint
        api_url = "https://router.huggingface.co/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.config.hf_api_token}",
            "Content-Type": "application/json",
        }

        # Build payload for chat/instruct models
        payload = {
            "model": self.config.hf_model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": hf_cfg.get("max_new_tokens", 1024),
            "temperature": hf_cfg.get("temperature", 0.1),
            "top_p": hf_cfg.get("top_p", 0.9),
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=120)
            
            if response.status_code == 503:
                # Model loading
                raise RuntimeError("Model is loading. Please try again in a few seconds.")
            elif response.status_code == 401:
                raise RuntimeError("Invalid API key. Please check your HF_API_TOKEN or api_key in config.json. Get your token from: https://huggingface.co/settings/tokens")
            elif response.status_code == 429:
                raise RuntimeError("Rate limit exceeded. Please wait a moment and try again.")
            elif response.status_code == 404:
                raise RuntimeError(f"Model not found: {self.config.hf_model_id}. Check the model ID is correct.")
            elif response.status_code != 200:
                raise RuntimeError(f"HF API error ({response.status_code}): {response.text}")

            result = response.json()
            
            # Parse response from chat completion format
            if isinstance(result, dict) and "choices" in result:
                choices = result.get("choices", [])
                if choices and len(choices) > 0:
                    message = choices[0].get("message", {})
                    sql = message.get("content", "")
                else:
                    raise RuntimeError("No choices in API response")
            elif isinstance(result, dict) and "generated_text" in result:
                sql = result.get("generated_text", "")
            else:
                raise RuntimeError(f"Unexpected API response format: {result}")

            # Clean up the response
            sql = self._clean_sql_response(sql)
            return sql

        except requests.exceptions.Timeout:
            raise RuntimeError("HF API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HF API request failed: {str(e)}")

    def _generate_via_local(self, prompt: str) -> str:
        """Generate SQL using local GGUF model (fallback)."""
        gen_cfg = self.config.generation_config

        output = self.llm(
            prompt,
            max_tokens=gen_cfg["max_tokens"],
            temperature=gen_cfg["temperature"],
            top_p=gen_cfg["top_p"],
            top_k=gen_cfg.get("top_k", 40),
            stop=["```", "</s>", "\n\n"],
        )

        # Extract SQL from response
        sql = output["choices"][0]["text"].strip()
        sql = self._clean_sql_response(sql)
        return sql

    def _clean_sql_response(self, sql: str) -> str:
        """
        Clean up the LLM response to extract just the SQL.
        """
        # Remove markdown code blocks
        sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"^```", "", sql)
        sql = re.sub(r"```$", "", sql)

        # Remove leading/trailing whitespace
        sql = sql.strip()

        # Remove trailing semicolon if duplicated
        while sql.endswith(";;"):
            sql = sql[:-1]

        # Ensure single trailing semicolon
        if not sql.endswith(";"):
            sql += ";"

        # Remove any explanatory text after the SQL
        lines = sql.split("\n")
        if len(lines) > 1:
            sql_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("--") and not line.startswith("#"):
                    if re.search(r"\b(SELECT|FROM|WHERE|JOIN|GROUP|ORDER|LIMIT|WITH)\b", line, re.IGNORECASE):
                        sql_lines.append(line)
                    elif sql_lines:
                        sql_lines.append(line)
            sql = " ".join(sql_lines)

        return sql


# Global generator instance
_generator: Optional[SQLGenerator] = None


def get_generator() -> SQLGenerator:
    """Get or create the SQL generator singleton."""
    global _generator
    if _generator is None:
        _generator = SQLGenerator()
    return _generator


def generate_sql(question: str, schema: str, db_type: str = "sqlite", max_tokens: int = None) -> str:
    """
    Generate SQL query from question and schema.
    """
    generator = get_generator()

    if max_tokens is not None:
        original_max = generator.config.generation_config["max_tokens"]
        generator.config.generation_config["max_tokens"] = max_tokens
        try:
            result = generator.generate_sql(question, schema, db_type)
        finally:
            generator.config.generation_config["max_tokens"] = original_max
    else:
        result = generator.generate_sql(question, schema, db_type)

    return result
