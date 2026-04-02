"""
Execute SQL node - runs validated queries with schema validation and auto-correction.
Logs failed queries to err_sql.txt for debugging.
"""

from typing import List, Dict, Any
import re
from datetime import datetime
from pathlib import Path

from rag_agent.state import AgentState
from rag_agent.cache import get_cache
from rag_agent.db import get_db_manager, execute_query, translate_sql_for_sqlite, repair_sql
from rag_agent.sql_validator import validate_sql_syntax, fix_common_sql_errors
from rag_agent.schema_validator import (
    validate_against_schema,
    get_schema_context,
    build_correction_prompt,
)
from rag_agent.model import generate_sql as generate_sql_query
from rag_agent.config import get_config


# Error log file path
ERROR_SQL_LOG_PATH = Path(__file__).parent.parent / "err_sql.txt"


def is_validation_enabled() -> bool:
    """Check if schema validation is enabled in config."""
    try:
        config = get_config()
        validation_config = config.config.get("validation", {})
        return validation_config.get("enable_schema_validation", True)
    except Exception:
        return True  # Default to enabled if config fails


def log_failed_query_to_file(
    question: str,
    sql: str,
    error_message: str,
    schema: List[Dict[str, Any]] = None,
    db_type: str = "sqlite",
) -> Path:
    """
    Log a failed SQL query to err_sql.txt with timestamp.
    
    Args:
        question: Original user question.
        sql: SQL query that failed.
        error_message: Error message from execution.
        schema: Database schema (optional).
        db_type: Database type.
        
    Returns:
        Path to the log file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build log entry
    log_entry = f"""
{'='*80}
TIMESTAMP: {timestamp}
DATABASE TYPE: {db_type}
{'='*80}

QUESTION:
{question}

FAILED SQL:
{sql}

ERROR:
{error_message}

AVAILABLE TABLES:
{', '.join([t.get('table_name', 'unknown') for t in (schema or [])])}

{'='*80}

"""
    
    # Append to log file
    with open(ERROR_SQL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_entry)
    
    return ERROR_SQL_LOG_PATH


def execute_sql_node(state: AgentState) -> AgentState:
    """
    Execute the validated SQL query with schema validation and auto-correction.

    This node:
    1. Validates SQL syntax
    2. Validates against actual schema (tables/columns exist)
    3. If validation fails, asks LLM to regenerate with correct schema
    4. Executes the query (with translation if needed)
    5. Caches the result
    6. Logs failed queries to err_sql.txt

    Args:
        state: Current agent state.

    Returns:
        Updated agent state with query results.
    """
    if state.error:
        return state

    validated_sql = state.validated_sql
    if not validated_sql:
        return AgentState(
            **{
                **state.model_dump(),
                "error": "No validated SQL to execute.",
            }
        )

    try:
        cache = get_cache()
        db_type = state.db_type or "sqlite"

        # Check cache first
        cached_data = cache.get(
            question=state.question,
            schema=state.database_schema,
            sql=validated_sql,
        )

        if cached_data is not None:
            return AgentState(
                **{
                    **state.model_dump(),
                    "data": cached_data,
                }
            )

        # Step 1: Validate SQL syntax
        is_valid, syntax_error = validate_sql_syntax(validated_sql, db_type, state.database_schema)

        if not is_valid:
            # Try to fix common errors
            table_names = [t.get("table_name", "") for t in (state.database_schema or [])]
            fixed_sql = fix_common_sql_errors(validated_sql, table_names)

            # Validate the fixed SQL
            is_valid, syntax_error = validate_sql_syntax(fixed_sql, db_type, state.database_schema)

            if is_valid:
                validated_sql = fixed_sql
            else:
                return AgentState(
                    **{
                        **state.model_dump(),
                        "error": f"SQL syntax error: {syntax_error}\n\nOriginal query:\n{validated_sql}",
                    }
                )

        # Step 2: Validate against schema (only if enabled in config)
        validation_enabled = is_validation_enabled()
        
        if validation_enabled and state.database_schema:
            schema_valid, schema_errors = validate_against_schema(validated_sql, state.database_schema)

            if not schema_valid and schema_errors:
                # Schema validation failed - ask LLM to correct
                correction_result = retry_with_correction(
                    question=state.question,
                    original_sql=validated_sql,
                    errors=schema_errors,
                    schema=state.database_schema,
                    db_type=db_type,
                )

                if correction_result.get("error"):
                    # Log the failed query
                    log_failed_query_to_file(
                        question=state.question,
                        sql=validated_sql,
                        error_message="Schema validation failed: " + "; ".join(schema_errors),
                        schema=state.database_schema,
                        db_type=db_type,
                    )
                    return AgentState(
                        **{
                            **state.model_dump(),
                            "error": correction_result["error"],
                        }
                    )

                # Use corrected SQL
                validated_sql = correction_result["corrected_sql"]

        # Step 3: Validate corrected SQL one more time (only if validation enabled)
        # If validation fails after retry, try execution anyway to distinguish
        # validator errors from real SQL errors
        if validation_enabled and state.database_schema:
            schema_valid, schema_errors = validate_against_schema(validated_sql, state.database_schema)
            if not schema_valid and schema_errors:
                # Check if errors are about aliases - these are NOT false positives
                alias_error_indicators = ['alias', 'aliases are not allowed', 'use full table']
                is_alias_error = any(
                    ind in ' '.join(schema_errors).lower()
                    for ind in alias_error_indicators
                )
                
                if is_alias_error:
                    # This is a real validation error - don't bypass
                    error_msg = "Query uses table aliases which are not allowed.\n\n"
                    error_msg += "Errors:\n" + "\n".join(f"- {e}" for e in schema_errors)
                    error_msg += "\n\nPlease use full table names instead of aliases (T1, T2, etc.)."
                    return AgentState(
                        **{
                            **state.model_dump(),
                            "error": error_msg,
                        }
                    )
                
                # Check if errors are likely other false positives
                false_positive_indicators = ['not found in any table']
                is_likely_false_positive = any(
                    ind in ' '.join(schema_errors).lower()
                    for ind in false_positive_indicators
                )

                if is_likely_false_positive:
                    # Try execution anyway - database will give real error
                    print(f"Schema validation failed but may be false positive. Attempting execution...")
                    print(f"Errors: {schema_errors}")
                else:
                    # Real validation error - return with suggestions
                    error_msg = "Query validation failed after correction attempt.\n\n"
                    error_msg += "Errors:\n" + "\n".join(f"- {e}" for e in schema_errors)
                    error_msg += "\n\nPlease check your question and try again."
                    return AgentState(
                        **{
                            **state.model_dump(),
                            "error": error_msg,
                        }
                    )

        # Step 4: Translate for SQLite if needed
        sql_to_execute = validated_sql

        if db_type == "sqlite" and "information_schema" in validated_sql.lower():
            translated_sql = translate_sql_for_sqlite(validated_sql)
            if translated_sql != validated_sql:
                print(f"Translated SQL: {translated_sql}")
                sql_to_execute = translated_sql

        # Step 5: Execute query
        db_manager = get_db_manager()
        data = execute_query(sql_to_execute, db_manager)

        # Step 6: Cache result
        cache.set(
            question=state.question,
            schema=state.database_schema,
            sql=validated_sql,
            data=data,
            expire=3600,
        )

        return AgentState(
            **{
                **state.model_dump(),
                "data": data,
            }
        )

    except Exception as e:
        error_msg = str(e)
        
        # Log the failed query to err_sql.txt
        log_failed_query_to_file(
            question=state.question,
            sql=validated_sql,
            error_message=error_msg,
            schema=state.database_schema,
            db_type=state.db_type or "sqlite",
        )
        
        # Try to repair and retry for common column errors
        repair_result = try_repair_and_retry(
            question=state.question,
            original_sql=validated_sql,
            error_message=error_msg,
            schema=state.database_schema,
            db_type=state.db_type or "sqlite",
        )
        
        if repair_result.get("success"):
            # Successfully repaired and executed
            return AgentState(
                **{
                    **state.model_dump(),
                    "data": repair_result["data"],
                    "sql": repair_result["repaired_sql"],
                }
            )
        
        return AgentState(
            **{
                **state.model_dump(),
                "error": f"Query execution failed: {error_msg}\n\nQuery:\n{validated_sql}",
            }
        )


def try_repair_and_retry(
    question: str,
    original_sql: str,
    error_message: str,
    schema: List[Dict[str, Any]],
    db_type: str,
) -> Dict[str, Any]:
    """
    Attempt to repair SQL based on error message and retry execution.

    Args:
        question: Original question.
        original_sql: SQL that failed.
        error_message: Error from execution.
        schema: Database schema.
        db_type: Database type.

    Returns:
        Dict with success status and data if successful.
    """
    # Check for "no such column" error
    col_match = re.search(r'no such column: (?:T\d+\.)?(\w+)', error_message, re.IGNORECASE)
    if not col_match:
        return {"success": False}
    
    invalid_column = col_match.group(1)
    print(f"Detected invalid column: {invalid_column}. Attempting repair...")
    
    # Build schema context for repair
    schema_context = get_schema_context(schema)
    
    # Create repair prompt
    repair_prompt = f"""You are a SQL repair assistant. Fix the SQL query below.

**CRITICAL RULES:**
1. The column '{invalid_column}' does NOT exist in the database
2. Use ONLY the column names listed in the schema below
3. DO NOT invent or assume any column names
4. Copy names EXACTLY as shown (case-sensitive)

**AVAILABLE SCHEMA (USE ONLY THESE COLUMNS):**
{schema_context}

**ORIGINAL QUESTION:** {question}

**ORIGINAL SQL (HAS INVALID COLUMN '{invalid_column}'):**
{original_sql}

**TASK:**
Rewrite the SQL query to achieve the same goal using ONLY valid columns from the schema.
If the concept (like revenue, sales, profit) cannot be computed with available columns,
use the closest available numeric column instead.

Return ONLY the corrected SQL query, no explanation."""

    try:
        # Ask LLM to repair
        repaired_sql = generate_sql_query(
            question=repair_prompt,
            schema=[],  # Schema already in prompt
            db_type=db_type,
        )
        
        # Clean up the response
        repaired_sql = repaired_sql.strip()
        if repaired_sql.startswith("```sql"):
            repaired_sql = repaired_sql[6:]
        if repaired_sql.endswith("```"):
            repaired_sql = repaired_sql[:-3]
        repaired_sql = repaired_sql.strip()
        if repaired_sql.endswith(";;"):
            repaired_sql = repaired_sql[:-1]
        if not repaired_sql.endswith(";"):
            repaired_sql += ";"
        
        # Validate repaired SQL
        schema_valid, schema_errors = validate_against_schema(repaired_sql, schema)
        if not schema_valid:
            print(f"Repaired SQL still has validation errors: {schema_errors}")
            return {"success": False}
        
        # Try executing repaired SQL
        db_manager = get_db_manager()
        data = execute_query(repaired_sql, db_manager)
        
        print(f"Repair successful! Executed: {repaired_sql}")
        
        return {
            "success": True,
            "repaired_sql": repaired_sql,
            "data": data,
        }
        
    except Exception as e:
        print(f"Repair attempt failed: {str(e)}")
        return {"success": False}


def retry_with_correction(
    question: str,
    original_sql: str,
    errors: List[str],
    schema: List[Dict[str, Any]],
    db_type: str,
    max_retries: int = 1,
) -> Dict[str, Any]:
    """
    Ask LLM to correct SQL query based on schema validation errors.
    Uses intelligent column suggestion based on question semantics.

    Args:
        question: Original user question.
        original_sql: SQL query that failed.
        errors: List of validation errors.
        schema: Database schema.
        db_type: Database type.
        max_retries: Maximum retry attempts.

    Returns:
        Dict with corrected_sql or error.
    """
    try:
        # Use the new query refiner to generate a better correction prompt
        from rag_agent.query_refiner import generate_corrected_sql_prompt
        
        correction_prompt = generate_corrected_sql_prompt(
            question=question,
            original_sql=original_sql,
            errors=errors,
            schema=schema,
        )

        # Ask LLM to correct
        corrected_sql = generate_sql_query(
            question=correction_prompt,
            schema=[],  # Schema already in prompt
            db_type=db_type,
            max_tokens=1024,
        )

        # Clean up the response
        corrected_sql = corrected_sql.strip()
        # Remove markdown code blocks if present
        if corrected_sql.startswith("```sql"):
            corrected_sql = corrected_sql[6:]
        if corrected_sql.endswith("```"):
            corrected_sql = corrected_sql[:-3]
        corrected_sql = corrected_sql.strip()
        # Remove trailing semicolon if duplicated
        if corrected_sql.endswith(";;"):
            corrected_sql = corrected_sql[:-1]
        if not corrected_sql.endswith(";"):
            corrected_sql += ";"

        return {
            "corrected_sql": corrected_sql,
            "success": True,
        }

    except Exception as e:
        return {
            "error": f"Failed to correct query: {str(e)}\n\nOriginal errors:\n" + "\n".join(errors),
            "success": False,
        }
