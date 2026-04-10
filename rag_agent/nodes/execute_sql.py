"""
Execute SQL node - runs validated queries with caching.
Simple and focused on execution, not validation.
"""

from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

from rag_agent.state import AgentState
from rag_agent.cache import get_cache
from rag_agent.db import get_db_manager, execute_query


def execute_sql_node(state: AgentState) -> AgentState:
    """
    Execute the validated SQL query.

    This node:
    1. Checks cache for result
    2. Executes query
    3. Caches result
    4. Returns data

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

        # Execute query
        db_manager = get_db_manager()
        data = execute_query(validated_sql, db_manager)

        # Cache result
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

        return AgentState(
            **{
                **state.model_dump(),
                "error": f"Query execution failed: {error_msg}\n\nQuery:\n{validated_sql}",
            }
        )
