"""
Generate SQL node - uses LLM to generate SQL from natural language.
Automatically expands table aliases to full table names when configured.
"""

from typing import Dict, Any

from rag_agent.state import AgentState
from rag_agent.model import generate_sql, get_generator, expand_sql_aliases
from rag_agent.config import get_config


def generate_sql_node(state: AgentState) -> AgentState:
    """
    Generate SQL query using the LLM.

    This node uses the Phi-3.5 model (GGUF format) to generate a SQL query
    based on the user's question and the database schema.
    Includes database type in the prompt for dialect-specific SQL.
    When disable_aliases is enabled, automatically converts any aliases to full table names.
    If evidence is provided in state, it's passed to the generator as a hint.

    Args:
        state: Current agent state.

    Returns:
        Updated agent state with generated SQL.
    """
    if state.error:
        return state

    try:
        generator = get_generator()
        # Use formatted_schema if available, otherwise fallback to raw schema
        if state.formatted_schema:
            schema_str = state.formatted_schema
        elif state.database_schema:
            from rag_agent.nodes.load_schema import format_schema_as_create_tables
            schema_str = format_schema_as_create_tables(state.database_schema)
        else:
            schema_str = ""

        db_type = state.db_type or "sqlite"
        evidence = getattr(state, 'evidence', '') or ''
        
        sql = generator.generate_sql(
            question=state.question,
            schema=schema_str,
            db_type=db_type,
            evidence=evidence
        )

        if not sql or not sql.strip():
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": "Empty SQL query generated. Please rephrase your question.",
                }
            )

        # Check if we should expand aliases
        disable_aliases = False
        try:
            config = get_config()
            validation_config = config.config.get("validation", {})
            disable_aliases = validation_config.get("disable_aliases", False)
        except Exception:
            pass

        # Expand aliases if configured
        if disable_aliases and schema_str:
            original_sql = sql
            sql = expand_sql_aliases(sql, schema_str)
            if sql != original_sql:
                print(f"Expanded aliases in SQL: {sql[:100]}...")

        return AgentState(
            **{
                **state.model_dump(),
                "sql": sql.strip(),
            }
        )

    except Exception as e:
        return AgentState(
            **{
                **state.model_dump(),
                "error": f"SQL generation failed: {str(e)}",
            }
        )
