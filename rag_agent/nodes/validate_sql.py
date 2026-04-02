"""
Validate SQL node - ensures only safe SELECT queries are executed.
"""

import re

import sqlparse
from sqlparse.sql import Statement

from rag_agent.state import AgentState


# Forbidden SQL keywords that indicate write operations
FORBIDDEN_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
    "EXEC",
    "EXECUTE",
    "CALL",
    "LOAD",
    "UNLOAD",
    "COPY",
    "IMPORT",
    "EXPORT",
]


def validate_sql_node(state: AgentState) -> AgentState:
    """
    Validate the generated SQL query.
    
    This node parses the SQL using sqlparse and checks for:
    - Single statement only
    - Only SELECT queries allowed
    - No forbidden DDL/DML keywords
    
    Args:
        state: Current agent state.
        
    Returns:
        Updated agent state with validated SQL or error.
    """
    if state.error:
        return state
    
    sql = state.sql
    if not sql:
        return AgentState(
            **{
                **state.model_dump(),
                "error": "No SQL query to validate.",
            }
        )
    
    sql = sql.strip()
    
    # Parse SQL statements
    try:
        statements = sqlparse.parse(sql)
    except Exception as e:
        return AgentState(
            **{
                **state.model_dump(),
                "error": f"SQL parsing failed: {str(e)}",
            }
        )
    
    # Check for multiple statements
    non_empty_statements = [s for s in statements if str(s).strip()]
    if len(non_empty_statements) != 1:
        return AgentState(
            **{
                **state.model_dump(),
                "error": "Multiple SQL statements not allowed. Please provide a single query.",
            }
        )
    
    stmt = non_empty_statements[0]
    
    # Check for forbidden keywords in the raw SQL
    sql_upper = sql.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + keyword + r'\b', sql_upper):
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": f"Only SELECT queries are allowed. Found forbidden keyword: {keyword}",
                }
            )
    
    # Verify statement type is SELECT
    stmt_type = stmt.get_type()
    if stmt_type and stmt_type.upper() != "SELECT":
        return AgentState(
            **{
                **state.model_dump(),
                "error": f"Only SELECT queries are allowed. Got: {stmt_type}",
            }
        )
    
    # Additional check: ensure the first meaningful token is SELECT
    tokens = list(stmt.flatten())
    for token in tokens:
        if token.is_whitespace or token.ttype is None:
            continue
        if token.ttype.name == 'Keyword' and token.value.upper() == 'SELECT':
            break
        elif token.ttype.name == 'Keyword' and token.value.upper() != 'WITH':
            # Allow CTEs (WITH clause) but reject other starting keywords
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": f"Query must start with SELECT. Got: {token.value.upper()}",
                }
            )
        break
    
    return AgentState(
        **{
            **state.model_dump(),
            "validated_sql": sql,
        }
    )
