"""
Database engine management and schema extraction using SQLAlchemy.
"""

import tempfile
import sqlparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, Engine, text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError


class DatabaseManager:
    """
    Manages database connections and operations.
    
    Supports SQLite files, in-memory SQLite from CSV/XLSX,
    and remote databases via connection strings.
    """
    
    def __init__(self, source: str, db_type: str = "sqlite"):
        """
        Initialize database manager.
        
        Args:
            source: Database source (file path or connection string).
            db_type: Type of database (sqlite, postgresql, mysql, csv, xlsx).
        """
        self.source = source
        self.db_type = db_type
        self._engine: Optional[Engine] = None
        self._temp_file: Optional[str] = None
    
    @property
    def engine(self) -> Engine:
        """Get or create the SQLAlchemy engine."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine
    
    def _create_engine(self) -> Engine:
        """
        Create SQLAlchemy engine based on source and type.
        
        Returns:
            SQLAlchemy Engine instance.
        """
        if self.db_type in ("csv", "xlsx"):
            return self._create_temp_sqlite_from_file()
        elif self.db_type == "sqlite":
            if Path(self.source).exists():
                return create_engine(f"sqlite:///{self.source}")
            else:
                return create_engine(f"sqlite:///{self.source}")
        else:
            # Remote database (postgresql, mysql, etc.)
            return create_engine(self.source, pool_pre_ping=True)
    
    def _create_temp_sqlite_from_file(self) -> Engine:
        """
        Create in-memory SQLite from CSV/XLSX file.
        
        Returns:
            SQLAlchemy Engine for in-memory SQLite.
        """
        source_path = Path(self.source)
        
        if self.db_type == "csv":
            df = pd.read_csv(source_path)
        elif self.db_type == "xlsx":
            df = pd.read_excel(source_path)
        else:
            raise ValueError(f"Unsupported file type: {self.db_type}")
        
        # Create in-memory SQLite and insert data
        engine = create_engine("sqlite:///:memory:")
        table_name = source_path.stem.replace(" ", "_").replace("-", "_")
        df.to_sql(table_name, engine, index=False, if_exists="replace")
        
        return engine
    
    def extract_schema(self) -> List[Dict[str, Any]]:
        """
        Extract database schema.
        
        Returns:
            List of table definitions with columns and types.
        """
        try:
            inspector = inspect(self.engine)
            schema = []
            
            for table_name in inspector.get_table_names():
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append({
                        "name": str(col["name"]),
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "primary_key": col.get("primary_key", False),
                    })
                
                foreign_keys = []
                for fk in inspector.get_foreign_keys(table_name):
                    foreign_keys.append({
                        "constrained_columns": fk.get("constrained_columns", []),
                        "referenced_table": fk.get("referred_table"),
                        "referenced_columns": fk.get("referred_columns", []),
                    })
                
                schema.append({
                    "table_name": table_name,
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                })
            
            return schema
        except Exception as e:
            print(f"Schema extraction error: {e}")
            return []
    
    def execute_query(self, sql: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results.
        
        Args:
            sql: SQL query to execute.
            params: Optional parameters for parameterized queries.
            
        Returns:
            List of row dictionaries.
            
        Raises:
            SQLAlchemyError: If query execution fails.
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows
    
    def close(self) -> None:
        """Close database connection and cleanup."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        if self._temp_file and Path(self._temp_file).exists():
            Path(self._temp_file).unlink()


def translate_sql_for_sqlite(sql: str) -> str:
    """
    Attempt to translate common PostgreSQL/MySQL system queries to SQLite equivalents.
    
    Args:
        sql: SQL query string that may contain PostgreSQL/MySQL-specific syntax.
        
    Returns:
        Translated SQL query for SQLite, or original if no translation needed.
    """
    import re
    
    # Replace information_schema.tables with sqlite_master
    if "information_schema.tables" in sql:
        # Extract the condition on table_schema if present
        # For simplicity, replace the whole SELECT with a query on sqlite_master
        # Example: "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        # becomes: "SELECT name FROM sqlite_master WHERE type='table';"
        sql = re.sub(
            r"SELECT\s+table_name\s+FROM\s+information_schema\.tables\s+WHERE\s+table_schema\s*=\s*'public';?",
            "SELECT name FROM sqlite_master WHERE type='table';",
            sql,
            flags=re.IGNORECASE
        )
        # Fallback for any other information_schema usage
        sql = sql.replace("information_schema.tables", "sqlite_master")
    
    # Replace information_schema.columns with pragma table_info
    if "information_schema.columns" in sql:
        sql = sql.replace("information_schema.columns", "pragma_table_info")
        # Note: This is a simplification; full translation would require more complex logic
    
    # Replace PostgreSQL-specific data types
    sql = sql.replace("SERIAL", "INTEGER")
    sql = sql.replace("TEXT", "TEXT")  # SQLite supports TEXT
    sql = sql.replace("TIMESTAMP", "DATETIME")
    
    # Replace LIMIT/OFFSET syntax (already supported by SQLite, but ensure compatibility)
    # MySQL/PostgreSQL: LIMIT offset, count
    # SQLite: LIMIT count OFFSET offset
    limit_match = re.search(r'LIMIT\s+(\d+)\s*,\s*(\d+)', sql, re.IGNORECASE)
    if limit_match:
        offset, count = limit_match.groups()
        sql = re.sub(
            r'LIMIT\s+\d+\s*,\s*\d+',
            f'LIMIT {count} OFFSET {offset}',
            sql,
            flags=re.IGNORECASE
        )
    
    return sql


def repair_sql(sql: str, db_type: str) -> str:
    """Attempt to fix common SQL errors."""
    original = sql
    sql = sql.rstrip(';')

    # Basic syntax check
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return original
    except Exception:
        return original

    # Translate PostgreSQL system tables to SQLite equivalents
    if db_type == "sqlite":
        sql = re.sub(r'information_schema\.tables', 'sqlite_master', sql, flags=re.IGNORECASE)
        sql = re.sub(r"table_schema\s*=\s*'public'", "type='table'", sql, flags=re.IGNORECASE)
        sql = re.sub(r'SELECT\s+table_name\s+FROM\s+sqlite_master', 'SELECT name FROM sqlite_master', sql, flags=re.IGNORECASE)
        sql = re.sub(r'information_schema\.columns', 'pragma_table_info', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bSERIAL\b', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bTIMESTAMP\b', 'DATETIME', sql, flags=re.IGNORECASE)
        limit_match = re.search(r'LIMIT\s+(\d+)\s*,\s*(\d+)', sql, re.IGNORECASE)
        if limit_match:
            offset, count = limit_match.groups()
            sql = re.sub(r'LIMIT\s+\d+\s*,\s*\d+', f'LIMIT {count} OFFSET {offset}', sql, flags=re.IGNORECASE)

    if sql.strip().upper() == 'SELECT':
        return original

    if not sql.endswith(';'):
        sql += ';'
    return sql


def create_engine_for_source(source: str, db_type: str = "sqlite") -> Engine:
    """
    Create SQLAlchemy engine for a given source and database type.
    
    This is a convenience function for creating engines directly
    without using the DatabaseManager class.
    
    Args:
        source: Database source (file path or connection string).
        db_type: Database type (sqlite, postgresql, mysql, csv, xlsx).
        
    Returns:
        SQLAlchemy Engine instance.
    """
    manager = DatabaseManager(source, db_type)
    return manager.engine


def create_db_manager(source: str, db_type: str = "sqlite") -> DatabaseManager:
    """
    Factory function to create a DatabaseManager.
    
    Args:
        source: Database source.
        db_type: Database type.
        
    Returns:
        DatabaseManager instance.
    """
    return DatabaseManager(source, db_type)


def execute_query(sql: str, db_manager: Optional[DatabaseManager] = None) -> List[Dict[str, Any]]:
    """
    Execute a SQL query using the global or provided database manager.
    
    Args:
        sql: SQL query to execute.
        db_manager: Optional DatabaseManager instance.
        
    Returns:
        List of row dictionaries.
    """
    if db_manager is None:
        # Use global manager if available
        global _db_manager
        db_manager = _db_manager
    
    if db_manager is None:
        raise ValueError("No database manager available")
    
    return db_manager.execute_query(sql)


# Global database manager (set by load_schema_node)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> Optional[DatabaseManager]:
    """Get the global database manager."""
    return _db_manager


def set_db_manager(manager: DatabaseManager) -> None:
    """Set the global database manager."""
    global _db_manager
    _db_manager = manager
