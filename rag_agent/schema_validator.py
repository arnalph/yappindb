"""
Schema-aware SQL validation.
Validates table names and column names against actual database schema.
Properly handles table aliases (e.g., products AS T1).
"""

import re
from typing import Tuple, List, Dict, Any, Set, Optional
from difflib import SequenceMatcher

from rag_agent.config import get_config


# SQL keywords to exclude from table/column extraction
SQL_KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL',
    'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'AS', 'CROSS',
    'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'ASC', 'DESC',
    'UNION', 'ALL', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE',
    'TABLE', 'INDEX', 'VIEW', 'DROP', 'ALTER', 'PRIMARY', 'KEY',
    'FOREIGN', 'REFERENCES', 'CONSTRAINT', 'DEFAULT', 'UNIQUE',
    'SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'CAST', 'COALESCE',
    'NULLIF', 'EXTRACT', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
    'WITH', 'RECURSIVE', 'OVER', 'PARTITION', 'RANK', 'DENSE_RANK', 'ROW_NUMBER',
    'AS', 'DESC', 'ASC', 'NULLS', 'FIRST', 'LAST',
    # SQLite functions - DO NOT VALIDATE AS COLUMNS
    'STRFTIME', 'DATE', 'TIME', 'DATETIME', 'JULIANDAY', 'STRFTIME',
    'SUBSTR', 'SUBSTRING', 'LENGTH', 'LOWER', 'UPPER', 'TRIM', 'LTRIM', 'RTRIM',
    'REPLACE', 'INSTR', 'LIKE', 'GLOB', 'MATCH', 'REGEXP',
    'RANDOM', 'ABS', 'ROUND', 'CEIL', 'CEILING', 'FLOOR',
    'IIF', 'IFF', 'IFNULL', 'ZEROIFNULL', 'NVL',
    'TOTAL', 'GROUP_CONCAT',
}


def find_similar_columns(column: str, available_columns: Set[str], threshold: float = 0.5) -> List[str]:
    """
    Find columns similar to the given column name using fuzzy matching.
    
    Args:
        column: Column name that was not found.
        available_columns: Set of available column names.
        threshold: Similarity threshold (0-1).
        
    Returns:
        List of similar column names.
    """
    column_lower = column.lower()
    similar = []
    
    for avail_col in available_columns:
        similarity = SequenceMatcher(None, column_lower, avail_col.lower()).ratio()
        if similarity >= threshold:
            similar.append((avail_col, similarity))
    
    # Sort by similarity and return top 3
    similar.sort(key=lambda x: x[1], reverse=True)
    return [col for col, _ in similar[:3]]


def check_for_aliases(sql: str) -> List[str]:
    """
    Check if SQL query uses table aliases (AS keyword).
    
    Args:
        sql: SQL query to check.
        
    Returns:
        List of error messages if aliases found, empty list otherwise.
    """
    errors = []
    
    # Remove string literals to avoid false matches
    sql_no_strings = re.sub(r"'[^']*'", "''", sql)
    
    # Pattern to detect table aliases: table_name AS alias or table_name alias
    # FROM table_name AS alias
    from_alias_pattern = r'\bFROM\s+[a-zA-Z_][a-zA-Z0-9_]*\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\b'
    for match in re.finditer(from_alias_pattern, sql_no_strings, re.IGNORECASE):
        potential_alias = match.group(1).lower()
        # Check if it's actually an alias (not a keyword like WHERE, JOIN, etc.)
        if potential_alias not in SQL_KEYWORDS and potential_alias not in ('select', 'from'):
            # Check if this looks like an alias (short name like T1, T2, o, p, etc.)
            if len(potential_alias) <= 3 or re.match(r'^[tpo][1-9]$', potential_alias, re.IGNORECASE):
                errors.append(f"Table aliases are not allowed. Found alias: {match.group(1)}. Use full table names instead.")
                break
    
    # JOIN table_name AS alias
    join_alias_pattern = r'\bJOIN\s+[a-zA-Z_][a-zA-Z0-9_]*\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s+ON\b'
    for match in re.finditer(join_alias_pattern, sql_no_strings, re.IGNORECASE):
        potential_alias = match.group(1).lower()
        if potential_alias not in SQL_KEYWORDS:
            if len(potential_alias) <= 3 or re.match(r'^[tpo][1-9]$', potential_alias, re.IGNORECASE):
                errors.append(f"Table aliases are not allowed. Found alias: {match.group(1)}. Use full table names instead.")
                break
    
    return errors


def extract_tables_and_aliases(sql: str) -> Tuple[Dict[str, str], Set[str]]:
    """
    Extract table aliases from SQL query.
    
    Args:
        sql: SQL query.
        
    Returns:
        Tuple of (alias_to_table dict, set of direct table references).
    """
    alias_to_table = {}  # Maps alias -> actual table name
    direct_tables = set()  # Tables referenced without alias
    
    # Remove string literals to avoid false matches
    sql_no_strings = re.sub(r"'[^']*'", "''", sql)
    
    # Keywords that cannot be table names or aliases (but AS is allowed as keyword separator)
    table_keywords = SQL_KEYWORDS - {'AS'}  # Allow AS as it's used for aliasing
    
    # Pattern 1: FROM table_name [AS] alias
    from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?'
    for match in re.finditer(from_pattern, sql_no_strings, re.IGNORECASE):
        table_name = match.group(1).lower()
        alias = match.group(2)
        
        if table_name and table_name not in table_keywords:
            if alias and alias.lower() not in table_keywords:
                alias_to_table[alias.lower()] = table_name
            else:
                direct_tables.add(table_name)
    
    # Pattern 2: JOIN table_name [AS] alias ON
    join_pattern = r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?\s+ON\b'
    for match in re.finditer(join_pattern, sql_no_strings, re.IGNORECASE):
        table_name = match.group(1).lower()
        alias = match.group(2)
        
        if table_name and table_name not in table_keywords:
            if alias and alias.lower() not in table_keywords:
                alias_to_table[alias.lower()] = table_name
            else:
                direct_tables.add(table_name)
    
    # Pattern 3: Comma-separated tables in FROM clause: FROM table1 t1, table2 t2
    # This handles: FROM products T3, order_items T1
    comma_from_pattern = r'\bFROM\s+([^J]+?)(?:\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|$)'
    from_clause_match = re.search(comma_from_pattern, sql_no_strings, re.IGNORECASE)
    if from_clause_match:
        from_clause = from_clause_match.group(1)
        # Split by comma
        parts = from_clause.split(',')
        for part in parts:
            part = part.strip()
            # Match: table_name [AS] alias
            table_alias_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?', part)
            if table_alias_match:
                table_name = table_alias_match.group(1).lower()
                alias = table_alias_match.group(2)
                if table_name and table_name not in table_keywords:
                    if alias and alias.lower() not in table_keywords:
                        alias_to_table[alias.lower()] = table_name
                    else:
                        direct_tables.add(table_name)
    
    return alias_to_table, direct_tables


def extract_columns_from_sql(sql: str) -> Set[str]:
    """
    Extract column references from SQL query.
    Excludes aliases defined with AS.
    
    Args:
        sql: SQL query.
        
    Returns:
        Set of column references (may include table.column format).
    """
    columns = set()

    # Remove string literals to avoid false matches
    sql_no_strings = re.sub(r"'[^']*'", "''", sql)

    # Remove AS aliases before processing (they're not real columns)
    # Pattern: expression AS alias_name -> expression
    sql_no_aliases = re.sub(r'\s+AS\s+[a-zA-Z_][a-zA-Z0-9_]*', '', sql_no_strings, flags=re.IGNORECASE)
    
    # Remove SQL function calls to avoid matching function names as columns
    # This handles functions like strftime(), substr(), lower(), etc.
    sql_no_functions = re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)', '', sql_no_aliases, flags=re.IGNORECASE)
    
    # Match qualified columns (table.column) but exclude keywords
    qualified_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
    for match in re.finditer(qualified_pattern, sql_no_functions, re.IGNORECASE):
        table_ref = match.group(1)
        column = match.group(2)
        # Exclude SQL keywords
        if table_ref.upper() not in SQL_KEYWORDS and column.upper() not in SQL_KEYWORDS:
            columns.add(f"{table_ref}.{column}")
    
    # Match columns in SELECT clause (after removing aliases)
    select_match = re.search(r'\bSELECT\s+(.*?)\s+FROM\b', sql_no_functions, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_clause = select_match.group(1)
        # Remove function contents to avoid matching internal column names
        select_clause = re.sub(r'\([^)]*\)', '', select_clause)
        # Split by comma and extract column names
        parts = select_clause.split(',')
        for part in parts:
            part = part.strip()
            # Skip if empty or just operators
            if not part or part in ('+', '-', '*', '/'):
                continue
            # First try to match qualified column (table.column)
            qualified_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)', part)
            if qualified_match:
                table_ref = qualified_match.group(1)
                column = qualified_match.group(2)
                if table_ref.upper() not in SQL_KEYWORDS and column.upper() not in SQL_KEYWORDS:
                    columns.add(f"{table_ref}.{column}")
            else:
                # Extract unqualified column name (first identifier)
                col_match = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', part)
                if col_match:
                    col = col_match.group(0)
                    if col.upper() not in SQL_KEYWORDS:
                        columns.add(col)
    
    # Match columns in GROUP BY
    group_match = re.search(r'\bGROUP\s+BY\s+(.*?)(?:\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|$)', sql_no_aliases, re.IGNORECASE | re.DOTALL)
    if group_match:
        group_clause = group_match.group(1).strip()
        # Split by comma
        for part in group_clause.split(','):
            part = part.strip()
            # First try to match qualified columns (table.column)
            qualified_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)', part)
            if qualified_match:
                table_ref = qualified_match.group(1)
                column = qualified_match.group(2)
                if table_ref.upper() not in SQL_KEYWORDS and column.upper() not in SQL_KEYWORDS:
                    columns.add(f"{table_ref}.{column}")
            else:
                # Match unqualified column name
                col_match = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', part)
                if col_match:
                    col = col_match.group(0)
                    if col.upper() not in SQL_KEYWORDS:
                        columns.add(col)
    
    # Match columns in ORDER BY (skip validation - often aliases)
    # Match columns in WHERE clause
    where_match = re.search(r'\bWHERE\s+(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)', sql_no_aliases, re.IGNORECASE | re.DOTALL)
    if where_match:
        where_clause = where_match.group(1).strip()
        # Find qualified columns
        for match in re.finditer(qualified_pattern, where_clause, re.IGNORECASE):
            table_ref = match.group(1)
            column = match.group(2)
            if table_ref.upper() not in SQL_KEYWORDS and column.upper() not in SQL_KEYWORDS:
                columns.add(f"{table_ref}.{column}")
    
    return columns


def validate_against_schema(
    sql: str,
    schema: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Validate SQL query against database schema.
    Properly handles table aliases.
    
    Args:
        sql: SQL query to validate.
        schema: Database schema with tables and columns.
        
    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    errors = []
    
    if not schema:
        # No schema to validate against
        return True, []
    
    # Check if validation is enabled in config
    try:
        config = get_config()
        validation_config = config.config.get("validation", {})
        enable_validation = validation_config.get("enable_schema_validation", True)
        disable_aliases = validation_config.get("disable_aliases", False)
        if not enable_validation:
            return True, []
    except Exception:
        disable_aliases = False
        pass  # If config fails, proceed with validation
    
    # Check for aliases if disabled
    if disable_aliases:
        alias_errors = check_for_aliases(sql)
        if alias_errors:
            return False, alias_errors
    
    # Extract tables and aliases from SQL
    alias_to_table, direct_tables = extract_tables_and_aliases(sql)
    used_columns = extract_columns_from_sql(sql)
    
    # Build schema lookup
    table_names = set()
    all_columns = {}  # table_name -> set of column names
    all_columns_flat = set()  # all column names across all tables
    column_to_tables = {}  # column_name -> set of tables that have it
    
    for table in schema:
        table_name = table.get("table_name", "")
        table_names.add(table_name.lower())
        
        columns = table.get("columns", [])
        table_columns = set(col.get("name", "").lower() for col in columns)
        all_columns[table_name.lower()] = table_columns
        all_columns_flat.update(table_columns)
        
        # Map column to tables
        for col in table_columns:
            if col not in column_to_tables:
                column_to_tables[col] = set()
            column_to_tables[col].add(table_name.lower())
    
    # Build reverse lookup: table -> aliases
    table_to_aliases = {}
    for alias, table in alias_to_table.items():
        if table not in table_to_aliases:
            table_to_aliases[table] = []
        table_to_aliases[table].append(alias)
    
    # Validate tables exist (check both actual table names and aliases)
    for alias_or_table in set(list(alias_to_table.keys()) + list(direct_tables)):
        # Check if it's a direct table name
        if alias_or_table in table_names:
            continue
        # Check if it's an alias that maps to a valid table
        if alias_or_table in alias_to_table:
            actual_table = alias_to_table[alias_or_table]
            if actual_table in table_names:
                continue
        # Table/alias not found
        errors.append(f"Table '{alias_or_table}' not found in database. Available tables: {', '.join(sorted(table_names))}")
    
    # Validate columns exist
    for col_ref in used_columns:
        parts = col_ref.split('.')
        if len(parts) == 2:
            # Qualified column (table.column or alias.column)
            table_ref, column = parts
            table_ref_lower = table_ref.lower()
            column_lower = column.lower()
            
            # First check if table_ref is an alias
            if table_ref_lower in alias_to_table:
                actual_table = alias_to_table[table_ref_lower]
            # Then check if it's a direct table name
            elif table_ref_lower in table_names:
                actual_table = table_ref_lower
            else:
                errors.append(f"Table reference '{table_ref}' not found. Available tables: {', '.join(sorted(table_names))}")
                continue
            
            if actual_table in all_columns:
                if column_lower not in all_columns[actual_table]:
                    # Column not found - provide suggestions
                    available = list(all_columns[actual_table])
                    similar = find_similar_columns(column, set(available))
                    
                    error_msg = f"Column '{column}' not found in table '{table_ref}'"
                    if similar:
                        error_msg += f". Did you mean: {', '.join(similar)}?"
                    error_msg += f". Available columns: {', '.join(sorted(available))}"
                    errors.append(error_msg)
            else:
                errors.append(f"Table '{actual_table}' has no column information")
        else:
            # Unqualified column - check if it exists in ANY table
            column_lower = col_ref.lower()
            found = False
            for table_name, columns in all_columns.items():
                if column_lower in columns:
                    found = True
                    break
            
            if not found:
                # Column not found in any table - provide suggestions
                similar = find_similar_columns(col_ref, all_columns_flat)
                
                error_msg = f"Column '{col_ref}' not found in any table"
                if similar:
                    error_msg += f". Did you mean: {', '.join(similar)}?"
                
                all_available = sorted(list(all_columns_flat))
                if len(all_available) <= 20:
                    error_msg += f". Available columns: {', '.join(all_available)}"
                else:
                    error_msg += f". ({len(all_available)} total columns available)"
                errors.append(error_msg)
    
    return len(errors) == 0, errors


def get_schema_context(schema: List[Dict[str, Any]]) -> str:
    """
    Format schema as context for LLM.
    Simple format with explicit column lists.
    
    Args:
        schema: Database schema.
        
    Returns:
        Formatted schema string for LLM prompt.
    """
    lines = []
    
    for table in schema:
        table_name = table.get("table_name", "")
        columns = table.get("columns", [])
        
        # Extract just column names
        col_names = [col.get("name", "") for col in columns]
        
        lines.append(f"TABLE: {table_name}")
        lines.append(f"  COLUMNS: {', '.join(col_names)}")
    
    return "\n".join(lines)


def build_correction_prompt(
    original_question: str,
    original_sql: str,
    errors: List[str],
    schema_context: str
) -> str:
    """
    Build prompt for LLM to correct SQL query.
    
    Args:
        original_question: Original user question.
        original_sql: SQL query that failed validation.
        errors: List of validation errors.
        schema_context: Formatted schema context.
        
    Returns:
        Prompt for LLM correction.
    """
    # Check if aliases should be disabled
    disable_aliases = False
    try:
        from rag_agent.config import get_config
        config = get_config()
        validation_config = config.config.get("validation", {})
        disable_aliases = validation_config.get("disable_aliases", False)
    except Exception:
        pass
    
    alias_instruction = ""
    if disable_aliases:
        alias_instruction = """
**IMPORTANT: DO NOT USE TABLE ALIASES!**
- Do NOT use `AS T1`, `AS T2`, etc.
- Use FULL table names: `FROM order_items JOIN products`
- Reference columns as: `order_items.price`, `products.product_category_name`
"""
    
    return f"""You are a SQL correction assistant. Fix the SQL query below.

**CRITICAL RULES:**
1. Use ONLY the table names and column names listed in the schema
2. DO NOT use any column or table that is not explicitly listed
3. Copy names EXACTLY as shown (case-sensitive)
4. DO NOT invent or assume any column names
5. If a concept (like "revenue", "sales", "profit") is not a column name, find the closest matching column
{alias_instruction}
**VALIDATION ERRORS TO FIX:**
{chr(10).join(f"- {e}" for e in errors)}

**AVAILABLE SCHEMA (USE ONLY THESE):**
{schema_context}

**ORIGINAL QUESTION:** {original_question}

**ORIGINAL SQL (HAS ERRORS):**
{original_sql}

Fix the SQL to use ONLY the columns and tables listed above. Return ONLY the corrected SQL query, no explanation."""
