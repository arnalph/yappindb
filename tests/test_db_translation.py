"""
Unit tests for SQL translation and repair functions.
"""

import pytest
from rag_agent.db import translate_sql_for_sqlite, repair_sql


class TestSqlTranslation:
    """Tests for SQL translation from PostgreSQL/MySQL to SQLite."""
    
    def test_translate_information_schema_public(self):
        """Test translation of information_schema.tables with public schema."""
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        expected = "SELECT name FROM sqlite_master WHERE type='table';"
        assert translate_sql_for_sqlite(sql) == expected
    
    def test_translate_general_information_schema(self):
        """Test translation of generic information_schema.tables query."""
        sql = "SELECT * FROM information_schema.tables;"
        expected = "SELECT * FROM sqlite_master;"
        assert translate_sql_for_sqlite(sql) == expected
    
    def test_no_translation_needed(self):
        """Test that regular SQL queries are not modified."""
        sql = "SELECT * FROM users;"
        assert translate_sql_for_sqlite(sql) == sql


class TestSqlRepair:
    """Tests for SQL repair function."""
    
    def test_repair_information_schema(self):
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        expected = "SELECT name FROM sqlite_master WHERE type='table';"
        assert repair_sql(sql, "sqlite") == expected

    def test_repair_general_information_schema(self):
        sql = "SELECT * FROM information_schema.tables;"
        expected = "SELECT * FROM sqlite_master;"
        assert repair_sql(sql, "sqlite") == expected

    def test_repair_information_schema_columns(self):
        sql = "SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"
        expected = "SELECT column_name FROM pragma_table_info WHERE table_name = 'users';"
        assert repair_sql(sql, "sqlite") == expected

    def test_repair_serial(self):
        sql = "CREATE TABLE test (id SERIAL PRIMARY KEY);"
        expected = "CREATE TABLE test (id INTEGER PRIMARY KEY);"
        assert repair_sql(sql, "sqlite") == expected

    def test_repair_timestamp(self):
        sql = "SELECT * FROM events WHERE created_at > TIMESTAMP '2024-01-01';"
        expected = "SELECT * FROM events WHERE created_at > DATETIME '2024-01-01';"
        assert repair_sql(sql, "sqlite") == expected

    def test_repair_limit_offset(self):
        sql = "SELECT * FROM users LIMIT 10, 20;"
        expected = "SELECT * FROM users LIMIT 20 OFFSET 10;"
        assert repair_sql(sql, "sqlite") == expected

    def test_no_repair(self):
        sql = "SELECT * FROM users;"
        assert repair_sql(sql, "sqlite") == sql
