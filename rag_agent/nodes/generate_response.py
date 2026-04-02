"""
Generate response node - formats query results into natural language.
Returns structured data for HTML table rendering.
"""

from typing import Any, Dict, List

from rag_agent.state import AgentState


def generate_response_node(state: AgentState) -> AgentState:
    """
    Generate natural language response from query results.
    
    This node formats the retrieved data into a readable answer.
    The data is returned in a structured format for HTML table rendering.
    
    Args:
        state: Current agent state.
        
    Returns:
        Updated agent state with natural language response.
    """
    if state.error:
        # Return error message as response
        return AgentState(
            **{
                **state.model_dump(),
                "response": state.error,
            }
        )
    
    data = state.data
    
    if data is None:
        return AgentState(
            **{
                **state.model_dump(),
                "response": "No data returned from the query.",
            }
        )
    
    if len(data) == 0:
        return AgentState(
            **{
                **state.model_dump(),
                "response": "The query returned no results.",
            }
        )
    
    # Generate summary response
    response_lines = []
    
    # Summary line
    if len(data) == 1:
        response_lines.append(f"Found 1 result:")
    else:
        response_lines.append(f"Found {len(data)} result(s):")
    
    # For small result sets, add a brief text summary
    if data and len(data) <= 5:
        columns = list(data[0].keys())
        if len(columns) <= 3:
            # Show first row as summary
            first_row = data[0]
            summary_parts = [f"{col}: {format_value(first_row.get(col))}" for col in columns]
            response_lines.append("First result: " + ", ".join(summary_parts))
    
    response = "\n".join(response_lines)
    
    # Data is already in the state.data field for HTML rendering
    return AgentState(
        **{
            **state.model_dump(),
            "response": response,
        }
    )


def format_value(value: Any) -> str:
    """Format a single value for display."""
    if value is None:
        return "NULL"
    elif isinstance(value, float):
        # Round floats to 4 decimal places
        return f"{value:.4f}" if abs(value) < 1e6 else f"{value:.4e}"
    elif isinstance(value, (list, tuple)):
        return f"[{', '.join(format_value(v) for v in value)}]"
    else:
        return str(value)
