"""
SQL Schema Validator using sqlglot.
Validates table names and column names against actual database schema.
Uses sqlglot's AST parser to accurately extract tables and columns.
"""

import sqlglot
from sqlglot.errors import ParseError
from sqlglot import exp
from typing import List, Dict, Any, Tuple, Set, Optional


class SQLSchemaValidator:
    """
    Validates SQL queries against a known schema using sqlglot AST parsing.
    
    This replaces the buggy regex-based validator with a proper SQL parser
    that correctly handles:
    - SQL functions (strftime, IIF, etc.) - NOT treated as columns
    - Nested subqueries
    - JOINs with ON conditions
    - Aliases (AS keyword)
    - Complex expressions
    """
    
    def __init__(self, schema: List[Dict[str, Any]], dialect: str = "sqlite"):
        """
        Initialize validator with schema.
        
        Args:
            schema: List of table definitions from database
            dialect: SQL dialect (sqlite, postgres, mysql)
        """
        self.schema = schema
        self.dialect = dialect
        
        # Build lookup structures
        self.tables: Dict[str, Set[str]] = {}  # table_name -> set of column names
        self.table_names_lower: Dict[str, str] = {}  # lowercase -> actual name
        self.all_columns: Set[str] = set()
        
        for table in schema:
            table_name = table.get("table_name", "")
            if table_name:
                self.table_names_lower[table_name.lower()] = table_name
                columns = set()
                for col in table.get("columns", []):
                    col_name = col.get("name", "")
                    if col_name:
                        columns.add(col_name.lower())
                        self.all_columns.add(col_name.lower())
                self.tables[table_name.lower()] = columns
    
    def validate(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Validate SQL query against schema.
        
        Args:
            sql: SQL query string
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Step 1: Parse SQL syntax
        try:
            ast = sqlglot.parse_one(sql, dialect=self.dialect)
        except ParseError as e:
            return False, [f"Invalid SQL syntax: {str(e)}"]
        
        # Step 2: Extract tables and validate they exist
        sql_tables = self._extract_tables(ast)
        for table_alias, table_name in sql_tables.items():
            if table_name.lower() not in self.tables:
                available = ", ".join(sorted(self.tables.keys()))
                errors.append(f"Table '{table_name}' not found in database. Available tables: {available}")
        
        if errors:
            return False, errors
        
        # Step 3: Build alias mapping for this query
        alias_map = self._build_alias_map(ast, sql_tables)
        
        # Step 4: Extract columns and validate they exist
        sql_columns = self._extract_columns(ast)
        for table_ref, column in sql_columns:
            # Resolve alias to actual table name
            actual_table = alias_map.get(table_ref.lower(), table_ref)
            
            # Skip validation for unqualified columns or special expressions
            if not actual_table or actual_table.lower() not in self.tables:
                continue
                
            # Check if column exists in table
            if column.lower() not in self.tables[actual_table.lower()]:
                # Provide suggestions
                suggestions = self._find_similar_columns(column, actual_table)
                if suggestions:
                    errors.append(
                        f"Column '{column}' not found in table '{actual_table}'. "
                        f"Did you mean: {', '.join(suggestions)}?"
                    )
                else:
                    errors.append(
                        f"Column '{column}' not found in table '{actual_table}'. "
                        f"Available columns: {', '.join(sorted(self.tables[actual_table.lower()]))}"
                    )
        
        if errors:
            return False, errors
        
        return True, []
    
    def _extract_tables(self, ast) -> Dict[str, str]:
        """
        Extract table references from AST.
        Returns dict of {alias: table_name}
        """
        tables = {}
        for table_node in ast.find_all(exp.Table):
            table_name = table_node.name
            alias = table_node.alias or table_name
            tables[alias] = table_name
        return tables
    
    def _extract_columns(self, ast) -> List[Tuple[str, str]]:
        """
        Extract column references from AST.
        Returns list of (table_ref, column_name) tuples.
        Table_ref may be empty for unqualified columns.
        """
        columns = []
        for col_node in ast.find_all(exp.Column):
            table = col_node.table or ""
            column = col_node.name
            if column:  # Skip empty column names
                columns.append((table, column))
        return columns
    
    def _build_alias_map(self, ast, sql_tables: Dict[str, str]) -> Dict[str, str]:
        """
        Build mapping from aliases to actual table names.
        """
        alias_map = {}
        for alias, table_name in sql_tables.items():
            alias_map[alias.lower()] = table_name
        return alias_map
    
    def _find_similar_columns(self, column: str, table: str, max_suggestions: int = 3) -> List[str]:
        """
        Find similar column names using simple string matching.
        """
        from difflib import get_close_matches
        
        table_columns = list(self.tables.get(table.lower(), set()))
        # Get original case column names
        original_case = {}
        for table_name, cols in self.tables.items():
            for col in cols:
                original_case[col.lower()] = col
        
        # Find close matches
        matches = get_close_matches(column.lower(), table_columns, n=max_suggestions, cutoff=0.5)
        return [original_case.get(m, m) for m in matches]
