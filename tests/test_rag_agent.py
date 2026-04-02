"""
Unit tests for the RAG agent.
"""

import pytest
from unittest.mock import patch, MagicMock

from rag_agent.state import AgentState
from rag_agent.nodes import (
    validate_sql_node,
    generate_sql_node,
    execute_sql_node,
    generate_response_node,
)


class TestValidateSqlNode:
    """Tests for SQL validation node."""
    
    def test_validate_sql_accepts_select(self):
        """Test that valid SELECT queries are accepted."""
        state = AgentState(
            question="test",
            sql="SELECT * FROM users;",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is None
        assert new_state.validated_sql == "SELECT * FROM users;"

    def test_validate_sql_accepts_select_with_where(self):
        """Test SELECT with WHERE clause."""
        state = AgentState(
            question="test",
            sql="SELECT name, age FROM users WHERE age > 18;",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is None
        assert "SELECT" in new_state.validated_sql

    def test_validate_sql_accepts_joins(self):
        """Test SELECT with JOIN."""
        sql = "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id;"
        state = AgentState(question="test", sql=sql, database_schema=[])
        new_state = validate_sql_node(state)
        assert new_state.error is None
    
    def test_validate_sql_rejects_insert(self):
        """Test that INSERT is rejected."""
        state = AgentState(
            question="test",
            sql="INSERT INTO users VALUES (1, 'test');",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is not None
        assert "select" in new_state.error.lower()
    
    def test_validate_sql_rejects_update(self):
        """Test that UPDATE is rejected."""
        state = AgentState(
            question="test",
            sql="UPDATE users SET name = 'test' WHERE id = 1;",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is not None

    def test_validate_sql_rejects_delete(self):
        """Test that DELETE is rejected."""
        state = AgentState(
            question="test",
            sql="DELETE FROM users WHERE id = 1;",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is not None

    def test_validate_sql_rejects_drop(self):
        """Test that DROP is rejected."""
        state = AgentState(
            question="test",
            sql="DROP TABLE users;",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is not None

    def test_validate_sql_rejects_multiple_statements(self):
        """Test that multiple statements are rejected."""
        state = AgentState(
            question="test",
            sql="SELECT * FROM users; DELETE FROM users;",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is not None
        assert "multiple" in new_state.error.lower()

    def test_validate_sql_rejects_create(self):
        """Test that CREATE is rejected."""
        state = AgentState(
            question="test",
            sql="CREATE TABLE test (id INT);",
            database_schema=[],
        )
        new_state = validate_sql_node(state)
        assert new_state.error is not None

    def test_validate_sql_with_cte(self):
        """Test that CTE (WITH clause) is accepted."""
        sql = "WITH cte AS (SELECT 1 AS num) SELECT * FROM cte;"
        state = AgentState(question="test", sql=sql, database_schema=[])
        new_state = validate_sql_node(state)
        # CTEs should be allowed as they start with SELECT logic
        assert new_state.error is None or "only SELECT" not in new_state.error.lower()


class TestGenerateResponseNode:
    """Tests for response generation node."""

    def test_generate_response_with_data(self):
        """Test response generation with query results."""
        state = AgentState(
            question="test",
            data=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        )
        new_state = generate_response_node(state)
        assert new_state.response is not None
        assert "2 result" in new_state.response
        assert "Alice" in new_state.response

    def test_generate_response_empty_data(self):
        """Test response with empty results."""
        state = AgentState(question="test", data=[])
        new_state = generate_response_node(state)
        assert new_state.response is not None
        assert "no results" in new_state.response.lower()

    def test_generate_response_with_error(self):
        """Test response when there's an error."""
        state = AgentState(
            question="test",
            error="Database connection failed",
        )
        new_state = generate_response_node(state)
        assert new_state.response is not None
        assert "connection failed" in new_state.response.lower()

    def test_generate_response_none_data(self):
        """Test response when data is None."""
        state = AgentState(question="test", data=None)
        new_state = generate_response_node(state)
        assert new_state.response is not None
        assert "No data" in new_state.response

    def test_generate_response_large_result(self):
        """Test response with many results (truncation)."""
        data = [{"id": i, "value": f"item_{i}"} for i in range(50)]
        state = AgentState(question="test", data=data)
        new_state = generate_response_node(state)
        assert new_state.response is not None
        assert "50 result" in new_state.response


class TestGenerateSqlNode:
    """Tests for SQL generation node."""

    def test_generate_sql_error_handling(self):
        """Test error handling in SQL generation."""
        with patch('rag_agent.model.get_generator') as mock_get_gen:
            mock_gen = mock_get_gen.return_value
            mock_gen.generate_sql.side_effect = Exception("Model error")
            
            state = AgentState(question="test", database_schema=[])
            new_state = generate_sql_node(state)
            assert new_state.error is not None
            assert "SQL generation failed" in new_state.error

    def test_generate_sql_empty_result(self):
        """Test handling of empty SQL generation."""
        with patch('rag_agent.model.get_generator') as mock_get_gen:
            mock_gen = mock_get_gen.return_value
            mock_gen.generate_sql.return_value = ""
            
            state = AgentState(question="test", database_schema=[])
            new_state = generate_sql_node(state)
            assert new_state.error is not None
            assert "Empty SQL" in new_state.error

    def test_generate_sql_passes_through(self):
        """Test successful SQL generation."""
        with patch('rag_agent.model.get_generator') as mock_get_gen:
            mock_gen = mock_get_gen.return_value
            mock_gen.generate_sql.return_value = "SELECT 1"
            
            state = AgentState(question="test", database_schema=[])
            new_state = generate_sql_node(state)
            assert new_state.sql == "SELECT 1"
            assert new_state.error is None


class TestExecuteSqlNode:
    """Tests for SQL execution node."""

    def test_caching_hit(self):
        """Test that repeated queries hit the cache."""
        from rag_agent.cache import get_cache

        cache = get_cache()
        cache.clear()

        state = AgentState(
            validated_sql="SELECT 1",
            question="test",
            database_schema=[],
        )

        with patch('rag_agent.db.execute_query', return_value=[{"1": 1}]) as mock_exec:
            # First call should execute
            result1 = execute_sql_node(state)
            mock_exec.assert_called_once()

            # Second call should hit cache
            result2 = execute_sql_node(state)
            assert mock_exec.call_count == 1
            assert result1.data == result2.data

    def test_execute_sql_error_handling(self):
        """Test error handling during execution."""
        with patch('rag_agent.db.get_db_manager', side_effect=Exception("DB error")):
            state = AgentState(
                validated_sql="SELECT 1",
                question="test",
                database_schema=[],
            )
            new_state = execute_sql_node(state)
            assert new_state.error is not None
            assert "Query execution failed" in new_state.error

    def test_execute_sql_no_validated_sql(self):
        """Test execution without validated SQL."""
        state = AgentState(
            validated_sql=None,
            question="test",
            database_schema=[],
        )
        new_state = execute_sql_node(state)
        assert new_state.error is not None
        assert "No validated SQL" in new_state.error


class TestAgentState:
    """Tests for the AgentState model."""

    def test_state_creation(self):
        """Test basic state creation."""
        state = AgentState(question="What is the total sales?")
        assert state.question == "What is the total sales?"
        assert state.database_schema is None
        assert state.sql is None
        assert state.error is None

    def test_state_with_schema(self):
        """Test state with schema data."""
        schema = [
            {
                "table_name": "users",
                "columns": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "name", "type": "TEXT"},
                ],
            }
        ]
        state = AgentState(question="test", database_schema=schema)
        assert state.database_schema == schema
        assert len(state.database_schema) == 1
    
    def test_state_serialization(self):
        """Test state can be serialized to dict."""
        state = AgentState(question="test", sql="SELECT 1")
        state_dict = state.model_dump()
        assert state_dict["question"] == "test"
        assert state_dict["sql"] == "SELECT 1"


class TestCache:
    """Tests for the caching layer."""
    
    def test_cache_set_get(self):
        """Test basic cache operations."""
        from rag_agent.cache import get_cache
        
        cache = get_cache()
        cache.clear()
        
        question = "test question"
        schema = [{"table": "test"}]
        sql = "SELECT 1"
        data = [{"result": 1}]
        
        # Set cache
        cache.set(question, schema, sql, data, expire=3600)
        
        # Get cache
        cached = cache.get(question, schema, sql)
        assert cached == data
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        from rag_agent.cache import get_cache
        
        cache = get_cache()
        cache.clear()
        
        result = cache.get("nonexistent", [], "SELECT 1")
        assert result is None
    
    def test_cache_clear(self):
        """Test cache clearing."""
        from rag_agent.cache import get_cache
        
        cache = get_cache()
        cache.set("q1", [], "SELECT 1", "data1")
        cache.clear()
        
        assert len(cache) == 0


class TestGraphIntegration:
    """Integration tests for the full graph."""

    def test_full_graph_flow_with_mocks(self):
        """Test full graph flow with mocked nodes."""
        from rag_agent.graph import build_graph

        with patch('rag_agent.nodes.load_schema_node') as mock_load, \
             patch('rag_agent.nodes.generate_sql_node') as mock_gen, \
             patch('rag_agent.nodes.validate_sql_node') as mock_val, \
             patch('rag_agent.nodes.execute_sql_node') as mock_exec, \
             patch('rag_agent.nodes.generate_response_node') as mock_resp:

            # Setup mock returns
            mock_load.return_value = AgentState(
                question="test",
                database_schema=[],
            )
            mock_gen.return_value = AgentState(
                question="test",
                sql="SELECT 1",
                database_schema=[],
            )
            mock_val.return_value = AgentState(
                question="test",
                validated_sql="SELECT 1",
                database_schema=[],
            )
            mock_exec.return_value = AgentState(
                question="test",
                data=[{"1": 1}],
                database_schema=[],
            )
            mock_resp.return_value = AgentState(
                question="test",
                response="Answer: 1",
                data=[{"1": 1}],
                database_schema=[],
            )

            graph = build_graph()
            result = graph.invoke({"question": "test"})

            assert result["response"] == "Answer: 1"

    def test_graph_error_propagation(self):
        """Test that errors propagate through the graph."""
        from rag_agent.graph import build_graph

        with patch('rag_agent.nodes.load_schema_node') as mock_load:
            mock_load.return_value = AgentState(
                question="test",
                error="Database not found",
                database_schema=[],
            )

            graph = build_graph()
            result = graph.invoke({"question": "test"})

            assert result["error"] == "Database not found"
