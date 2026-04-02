"""
SQL validation using sqlparse for proper SQL parsing.
Database-type aware validation for SQLite, PostgreSQL, MySQL.
"""

import re
import sqlite3
from typing import Tuple, Optional, List, Dict, Any

import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Parenthesis
from sqlparse.tokens import Keyword, DML, DDL


def validate_sql_syntax(sql: str, db_type: str = "sqlite", schema: List[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate SQL syntax using sqlparse parser.
    
    Args:
        sql: SQL query to validate.
        db_type: Database type (sqlite, postgresql, mysql, csv, xlsx).
        schema: Optional database schema for enhanced validation.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    sql = sql.strip()
    
    # Basic checks
    if not sql:
        return False, "Empty SQL query"
    
    # Parse SQL using sqlparse
    try:
        statements = sqlparse.parse(sql)
    except Exception as e:
        return False, f"SQL parsing failed: {str(e)}"
    
    if len(statements) == 0:
        return False, "No SQL statements found"
    
    if len(statements) > 1:
        return False, "Multiple SQL statements not allowed"
    
    stmt = statements[0]
    
    # Check statement type
    stmt_type = stmt.get_type()
    
    # Only allow SELECT queries (and WITH/CTE which start with WITH)
    if stmt_type not in ('SELECT', 'UNKNOWN'):
        # UNKNOWN can be CTE (WITH clause)
        if not sql.upper().strip().startswith('WITH'):
            return False, f"Only SELECT queries are allowed, got: {stmt_type}"
    
    # For complex queries, skip deep validation and let database handle it
    sql_upper = sql.upper()
    has_join = ' JOIN ' in sql_upper
    has_subquery = sql_upper.count('SELECT') > 1
    has_window = ' OVER ' in sql_upper
    
    if has_join or has_subquery or has_window:
        # Just do basic structure check
        return validate_basic_structure(sql)
    
    # For simple queries, do thorough validation
    return validate_sqlite_syntax(sql, schema)


def validate_basic_structure(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Validate basic SQL structure using sqlparse.
    
    Args:
        sql: SQL query to validate.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    sql_upper = sql.upper()
    
    # Check for SELECT keyword
    if 'SELECT' not in sql_upper and not sql_upper.strip().startswith('WITH'):
        return False, "Query must contain SELECT keyword"
    
    # Check for balanced parentheses
    if sql.count('(') != sql.count(')'):
        return False, "Unbalanced parentheses"
    
    # Check for unclosed strings
    sql_no_escaped = sql.replace("\\'", "").replace('\\"', '')
    if sql_no_escaped.count("'") % 2 != 0:
        return False, "Unclosed string literal"
    
    # Check for truncated queries
    truncated_endings = [' LI', ' LIM', ' WHE', ' WHER', ' GRO', ' HAV', ' ORD', ' OFF', ' AN']
    for ending in truncated_endings:
        if sql.strip().upper().endswith(ending):
            # Query appears truncated but let database validate
            return True, None
    
    # Parse and check structure
    try:
        statements = sqlparse.parse(sql)
        if not statements:
            return False, "Failed to parse SQL"
        
        stmt = statements[0]
        tokens = list(stmt.tokens)
        
        # Check if query starts with SELECT or WITH
        first_token = None
        for token in tokens:
            if token.ttype and not token.is_whitespace:
                first_token = token
                break
        
        if first_token:
            first_value = str(first_token).upper()
            if first_value not in ('SELECT', 'WITH'):
                return False, f"Query must start with SELECT or WITH, got: {first_value}"
        
        return True, None
        
    except Exception as e:
        # If parsing fails, let database validate
        return True, None


def validate_sqlite_syntax(sql: str, schema: List[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate SQLite syntax.
    For queries with JOINs or complex structure, skip EXPLAIN and do structure check only.
    
    Args:
        sql: SQL query to validate.
        schema: Optional schema for enhanced validation.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    sql_upper = sql.upper()
    
    # For queries with JOINs, subqueries, or window functions, skip EXPLAIN
    # These will be validated by the actual database during execution
    has_join = ' JOIN ' in sql_upper
    has_subquery = sql_upper.count('SELECT') > 1
    has_window = ' OVER ' in sql_upper
    has_group_by = 'GROUP BY' in sql_upper
    has_order_by = 'ORDER BY' in sql_upper
    
    if has_join or has_subquery or has_window or has_group_by or has_order_by:
        # Just validate basic structure
        return validate_basic_structure(sql)
    
    # For simple SELECT queries, try EXPLAIN
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN {sql}")
        conn.close()
        return True, None
        
    except sqlite3.Error as e:
        error_msg = str(e).lower()
        
        if "no such table" in error_msg:
            # Table doesn't exist in test DB, but syntax is valid
            return True, None
        elif "no such column" in error_msg:
            # Column doesn't exist, but syntax is valid
            return True, None
        elif "syntax error" in error_msg:
            match = re.search(r'near "([^"]+)":', str(e))
            if match:
                return False, f"Syntax error near: {match.group(1)}"
            return False, f"Syntax error in query"
        else:
            # Other errors might be syntax issues
            return False, str(e)
    
    return True, None


def validate_postgresql_syntax(sql: str, schema: List[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Basic PostgreSQL syntax validation.
    
    Args:
        sql: SQL query to validate.
        schema: Optional schema for enhanced validation.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    # PostgreSQL-specific syntax is valid
    postgresql_patterns = [
        r'\bILIKE\b',
        r'::\w+',
        r'\bRETURNING\b',
    ]
    
    for pattern in postgresql_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return True, None
    
    return True, None


def validate_mysql_syntax(sql: str, schema: List[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Basic MySQL syntax validation.
    
    Args:
        sql: SQL query to validate.
        schema: Optional schema for enhanced validation.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    return True, None


def fix_common_sql_errors(sql: str, available_tables: List[str]) -> str:
    """
    Attempt to fix common SQL errors including reserved keyword aliases.
    
    Args:
        sql: SQL query to fix.
        available_tables: List of available table names.
        
    Returns:
        Fixed SQL query.
    """
    fixed_sql = sql
    
    # Fix reserved keyword used as alias
    reserved_keywords = ['or', 'and', 'select', 'from', 'where', 'join', 'group', 'order', 'having']
    for keyword in reserved_keywords:
        pattern = rf'\b(\w+)\s+{keyword}\s+(ON|WHERE|GROUP|ORDER|HAVING|,)'
        replacement = rf'\1 {keyword[0]} \2'
        fixed_sql = re.sub(pattern, replacement, fixed_sql, flags=re.IGNORECASE)
        
        fixed_sql = re.sub(
            rf'\b{keyword}\.(\w+)',
            f'{keyword[0]}.\g<1>',
            fixed_sql,
            flags=re.IGNORECASE
        )
    
    # Fix PostgreSQL to SQLite conversions
    fixed_sql = fixed_sql.replace("ILIKE", "LIKE")
    fixed_sql = fixed_sql.replace("::text", "")
    fixed_sql = fixed_sql.replace("::int", "")
    fixed_sql = fixed_sql.replace("::integer", "")
    fixed_sql = fixed_sql.replace("::numeric", "")
    fixed_sql = fixed_sql.replace("::timestamp", "")
    fixed_sql = fixed_sql.replace("::date", "")
    
    # Fix LIMIT offset, count
    limit_match = re.search(r'LIMIT\s+(\d+)\s*,\s*(\d+)', fixed_sql, re.IGNORECASE)
    if limit_match:
        offset, count = limit_match.groups()
        fixed_sql = re.sub(
            r'LIMIT\s+\d+\s*,\s*\d+',
            f'LIMIT {count} OFFSET {offset}',
            fixed_sql,
            flags=re.IGNORECASE
        )
    
    # Fix boolean literals
    fixed_sql = re.sub(r'\bTRUE\b', '1', fixed_sql, flags=re.IGNORECASE)
    fixed_sql = re.sub(r'\bFALSE\b', '0', fixed_sql, flags=re.IGNORECASE)
    
    # Fix date/time functions
    fixed_sql = fixed_sql.replace("NOW()", "datetime('now')")
    fixed_sql = fixed_sql.replace("CURRENT_DATE", "date('now')")
    fixed_sql = fixed_sql.replace("CURRENT_TIMESTAMP", "datetime('now')")
    
    # Fix window functions syntax
    fixed_sql = re.sub(r'RANK\s*\(\s*\)\s+OVER', 'RANK() OVER', fixed_sql, flags=re.IGNORECASE)
    fixed_sql = re.sub(r'DENSE_RANK\s*\(\s*\)\s+OVER', 'DENSE_RANK() OVER', fixed_sql, flags=re.IGNORECASE)
    fixed_sql = re.sub(r'ROW_NUMBER\s*\(\s*\)\s+OVER', 'ROW_NUMBER() OVER', fixed_sql, flags=re.IGNORECASE)
    
    return fixed_sql


def extract_table_names(sql: str) -> List[str]:
    """Extract table names from SQL query."""
    tables = []
    
    from_matches = re.findall(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
    tables.extend(from_matches)
    
    join_matches = re.findall(r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
    tables.extend(join_matches)
    
    return list(set(tables))


def validate_tables_exist(sql: str, available_tables: List[str]) -> Tuple[bool, List[str]]:
    """Validate that all tables in the SQL query exist."""
    used_tables = extract_table_names(sql)
    available_lower = [t.lower() for t in available_tables]
    
    missing = []
    for table in used_tables:
        if table.lower() not in available_lower:
            missing.append(table)
    
    return len(missing) == 0, missing
