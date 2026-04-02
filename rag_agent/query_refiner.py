"""
SQL Query Refiner - Analyzes validation errors and corrects column references.
Database-agnostic approach that learns from schema validation errors.
"""

import re
from typing import List, Dict, Any, Tuple, Optional


def analyze_question_terms(question: str) -> Dict[str, str]:
    """
    Extract key business terms from the question that need column mapping.
    
    Args:
        question: User's natural language question.
        
    Returns:
        Dict mapping detected terms to their context (e.g., 'revenue' -> 'metric')
    """
    terms = {}
    question_lower = question.lower()
    
    # Revenue/sales terms (need numeric column)
    revenue_terms = ['revenue', 'sales', 'income', 'earnings', 'profit', 'money', 'amount']
    for term in revenue_terms:
        if term in question_lower:
            terms[term] = 'numeric_metric'
    
    # Quantity terms (need count or quantity column)
    quantity_terms = ['quantity', 'count', 'number', 'how many', 'total items', 'volume']
    for term in quantity_terms:
        if term in question_lower:
            terms[term] = 'count_metric'
    
    # Time terms
    time_terms = ['date', 'time', 'when', 'period', 'month', 'year', 'day']
    for term in time_terms:
        if term in question_lower:
            terms[term] = 'time_dimension'
    
    # Category/grouping terms
    category_terms = ['category', 'type', 'kind', 'group', 'segment', 'class']
    for term in category_terms:
        if term in question_lower:
            terms[term] = 'category_dimension'
    
    # Customer terms
    customer_terms = ['customer', 'client', 'buyer', 'user', 'consumer']
    for term in customer_terms:
        if term in question_lower:
            terms[term] = 'customer_dimension'
    
    # Product terms
    product_terms = ['product', 'item', 'goods', 'merchandise', 'sku']
    for term in product_terms:
        if term in question_lower:
            terms[term] = 'product_dimension'
    
    return terms


def find_best_column_for_term(
    term: str, 
    term_type: str,
    schema: List[Dict[str, Any]],
    existing_errors: List[str] = None
) -> Optional[str]:
    """
    Find the best column for a given term based on schema analysis.
    
    Args:
        term: The term to find column for (e.g., 'revenue')
        term_type: Type of term (e.g., 'numeric_metric')
        schema: Database schema
        existing_errors: Columns that have already caused errors
        
    Returns:
        Best column in table.column format, or None if not found
    """
    # Get all available columns with their table names
    available_columns = []
    for table in schema:
        table_name = table.get("table_name", "")
        for col in table.get("columns", []):
            col_name = col.get("name", "")
            col_type = col.get("type", "TEXT")
            available_columns.append({
                "table": table_name,
                "column": col_name,
                "type": col_type,
                "full_name": f"{table_name}.{col_name}"
            })
    
    # Scoring function for column relevance
    def score_column(col_info: dict) -> int:
        score = 0
        col_name = col_info["column"].lower()
        table_name = col_info["table"].lower()
        full_name = col_info["full_name"].lower()
        
        # Check if column was in error list (penalize)
        if existing_errors:
            for error in existing_errors:
                if col_info["column"] in error:
                    score -= 100
        
        # Revenue/sales scoring - prefer order-related tables
        if term_type == 'numeric_metric':
            if term == 'revenue' or term == 'sales':
                # Exact match bonus
                if 'revenue' in col_name:
                    score += 30
                if 'sales' in col_name:
                    score += 30
                    
                # Context bonus - prefer order_items for revenue calculation
                if 'order' in table_name:
                    score += 40
                if 'item' in table_name:
                    score += 30
                    
                # Column type bonus
                if 'price' in col_name:
                    score += 50
                if 'value' in col_name:
                    score += 40
                if 'amount' in col_name:
                    score += 30
                if 'total' in col_name:
                    score += 20
                if 'payment' in col_name and 'value' in col_name:
                    score += 35
                    
            # Numeric type bonus
            if col_info["type"] in ('REAL', 'INTEGER', 'FLOAT', 'DOUBLE', 'NUMERIC', 'DECIMAL'):
                score += 10
        
        # Quantity/count scoring - prefer counting approach
        if term_type == 'count_metric':
            # Exact match
            if 'quantity' in col_name:
                score += 60
            if 'count' in col_name:
                score += 50
            if 'qty' in col_name:
                score += 50
                
            # Order items context - counting items sold
            if 'item' in col_name and 'order' in table_name:
                score += 40
                
            # ID columns can be counted
            if col_name.endswith('_id'):
                score += 20
        
        # Category scoring - prefer product tables
        if term_type == 'category_dimension':
            if 'category' in col_name:
                score += 60
            if 'type' in col_name:
                score += 40
            if 'name' in col_name and 'product' in table_name:
                score += 40
            if 'product' in table_name:
                score += 20
        
        # Customer scoring
        if term_type == 'customer_dimension':
            if 'customer' in col_name or 'customer' in table_name:
                score += 50
            if 'client' in col_name:
                score += 40
            if 'user' in col_name:
                score += 30
        
        # Product scoring - prefer product tables
        if term_type == 'product_dimension':
            if 'product' in table_name:
                score += 50
            if 'product' in col_name:
                score += 50
            if 'item' in col_name:
                score += 30
            if 'sku' in col_name:
                score += 30
        
        return score
    
    # Score all columns and return best match
    scored = [(col, score_column(col)) for col in available_columns]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Return top match if score is positive
    if scored and scored[0][1] > 0:
        return scored[0][0]["full_name"]
    
    return None


def extract_validation_errors(errors: List[str]) -> Dict[str, List[str]]:
    """
    Extract invalid column references from validation errors.
    
    Args:
        errors: List of validation error messages.
        
    Returns:
        Dict mapping table names to lists of invalid columns
    """
    invalid_refs = {}
    
    for error in errors:
        # Pattern: "Column 'X' not found in table 'Y'"
        match = re.search(r"Column '([^']+)' not found in table '([^']+)'", error)
        if match:
            column = match.group(1)
            table = match.group(2)
            if table not in invalid_refs:
                invalid_refs[table] = []
            invalid_refs[table].append(column)
        
        # Pattern: "Column 'X' not found in any table"
        match = re.search(r"Column '([^']+)' not found in any table", error)
        if match:
            column = match.group(1)
            if "_any_table_" not in invalid_refs:
                invalid_refs["_any_table_"] = []
            invalid_refs["_any_table_"].append(column)
    
    return invalid_refs


def suggest_column_alternatives(
    invalid_column: str,
    schema: List[Dict[str, Any]]
) -> List[str]:
    """
    Suggest alternative columns similar to the invalid one.
    
    Args:
        invalid_column: Column name that doesn't exist.
        schema: Database schema.
        
    Returns:
        List of suggested column names.
    """
    suggestions = []
    invalid_lower = invalid_column.lower()
    
    for table in schema:
        table_name = table.get("table_name", "")
        for col in table.get("columns", []):
            col_name = col.get("name", "")
            
            # Check for substring match
            if invalid_lower in col_name.lower() or col_name.lower() in invalid_lower:
                suggestions.append(f"{table_name}.{col_name}")
                continue
            
            # Check for semantic similarity
            # Price/revenue/value similarity
            if any(term in invalid_lower for term in ['price', 'cost', 'value', 'amount', 'revenue']):
                if any(term in col_name.lower() for term in ['price', 'cost', 'value', 'amount', 'revenue']):
                    suggestions.append(f"{table_name}.{col_name}")
            
            # Quantity/count similarity
            if any(term in invalid_lower for term in ['quantity', 'count', 'qty', 'amount']):
                if any(term in col_name.lower() for term in ['quantity', 'count', 'qty']):
                    suggestions.append(f"{table_name}.{col_name}")
    
    return list(set(suggestions))[:3]  # Return top 3 unique suggestions


def generate_corrected_sql_prompt(
    question: str,
    original_sql: str,
    errors: List[str],
    schema: List[Dict[str, Any]]
) -> str:
    """
    Generate a detailed correction prompt for the LLM.
    
    Args:
        question: Original user question.
        original_sql: SQL that failed validation.
        errors: Validation errors.
        schema: Database schema.
        
    Returns:
        Prompt for LLM to correct the SQL.
    """
    # Analyze question for key terms
    question_terms = analyze_question_terms(question)
    
    # Extract invalid columns from errors
    invalid_refs = extract_validation_errors(errors)
    
    # Build schema context with column suggestions
    schema_lines = []
    for table in schema:
        table_name = table.get("table_name", "")
        columns = table.get("columns", [])
        col_names = [col.get("name", "") for col in columns]
        schema_lines.append(f"TABLE: {table_name}")
        schema_lines.append(f"  COLUMNS: {', '.join(col_names)}")
    
    # Build term-to-column suggestions
    term_suggestions = []
    for term, term_type in question_terms.items():
        best_col = find_best_column_for_term(term, term_type, schema)
        if best_col:
            term_suggestions.append(f"- '{term}' ({term_type}) -> Consider using: {best_col}")
    
    # Build error context
    error_context = []
    for error in errors:
        error_context.append(f"- {error}")
    
    # Build invalid column suggestions
    invalid_suggestions = []
    for table, columns in invalid_refs.items():
        for col in columns:
            suggestions = suggest_column_alternatives(col, schema)
            if suggestions:
                invalid_suggestions.append(f"- '{col}' -> Did you mean: {', '.join(suggestions)}?")
    
    prompt = f"""You are a SQL expert. Fix the SQL query below to use ONLY valid columns from the schema.

**USER QUESTION:** {question}

**ANALYSIS OF QUESTION:**
{chr(10).join(f"- Term: '{term}' -> Type: {term_type}" for term, term_type in question_terms.items())}

**AVAILABLE SCHEMA (USE ONLY THESE TABLES AND COLUMNS):**
{chr(10).join(schema_lines)}

**RECOMMENDED COLUMNS FOR YOUR QUESTION:**
{chr(10).join(term_suggestions) if term_suggestions else "(No specific recommendations)"}

**ERRORS IN ORIGINAL SQL:**
{chr(10).join(error_context)}

**SUGGESTED ALTERNATIVES FOR INVALID COLUMNS:**
{chr(10).join(invalid_suggestions) if invalid_suggestions else "(No suggestions available)"}

**ORIGINAL SQL (HAS ERRORS):**
{original_sql}

**IMPORTANT RULES:**
1. Use ONLY the column names listed in the schema above
2. DO NOT invent column names like 'quantity' if they don't exist
3. For counting items, use COUNT(column_name) or COUNT(*)
4. For revenue/sales, use price, payment_value, or similar numeric columns
5. Return ONLY the corrected SQL query, no explanation

**CORRECTED SQL:**
```sql
"""
    return prompt
