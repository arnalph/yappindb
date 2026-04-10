"""
Validate SQL node - ensures only safe SELECT queries are executed.
Uses sqlglot for reliable SQL parsing (no false positives on SQL functions).
"""

from rag_agent.state import AgentState
from rag_agent.config import get_config


def validate_sql_node(state: AgentState) -> AgentState:
    """
    Validate the generated SQL query.

    This node uses sqlglot to check for:
    - Valid SQL syntax
    - Only SELECT queries allowed (no INSERT, UPDATE, DELETE, etc.)
    - Single statement only
    - Optional: Schema validation (tables and columns exist)

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

    # Step 1: Parse SQL syntax with sqlglot
    try:
        import sqlglot
        from sqlglot.errors import ParseError
        
        # Parse ALL statements (multiple statements will parse as a list or block)
        statements = sqlglot.parse(sql, dialect="sqlite")
        
        # Check for multiple statements
        if len(statements) > 1:
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": "Multiple SQL statements not allowed. Please provide a single query.",
                }
            )
        
        # Get the single statement
        ast = statements[0]
        
        # Verify it's a SELECT statement
        if ast.key.upper() not in ("SELECT",):
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": f"Only SELECT queries are allowed. Got: {ast.key.upper()}",
                }
            )
            
    except ParseError as e:
        return AgentState(
            **{
                **state.model_dump(),
                "error": f"Invalid SQL syntax: {str(e)}",
            }
        )
    except ImportError:
        # Fallback to sqlparse if sqlglot not available
        return AgentState(
            **{
                **state.model_dump(),
                "error": "sqlglot not installed. Cannot validate SQL.",
            }
        )

    # Step 2: Check for forbidden keywords (extra safety)
    sql_upper = sql.upper()
    forbidden_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
        "TRUNCATE", "REPLACE", "MERGE", "EXEC", "EXECUTE", "CALL",
    ]
    
    for keyword in forbidden_keywords:
        import re
        if re.search(r'\b' + keyword + r'\b', sql_upper):
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": f"Only SELECT queries are allowed. Found forbidden keyword: {keyword}",
                }
            )

    # Step 3: Optional schema validation
    try:
        config = get_config()
        validation_config = config.config.get("validation", {})
        enable_schema_validation = validation_config.get("enable_schema_validation", False)
        
        if enable_schema_validation and state.database_schema:
            from rag_agent.sql_validator import SQLSchemaValidator
            
            validator = SQLSchemaValidator(state.database_schema, dialect="sqlite")
            is_valid, errors = validator.validate(sql)
            
            if not is_valid:
                return AgentState(
                    **{
                        **state.model_dump(),
                        "error": f"Schema validation failed: {'; '.join(errors)}",
                    }
                )
    except Exception as e:
        # Don't fail on schema validation errors, log and continue
        print(f"Schema validation skipped: {e}")
        pass

    return AgentState(
        **{
            **state.model_dump(),
            "validated_sql": sql,
        }
    )
