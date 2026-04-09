"""
LangGraph workflow definition for the RAG agent.
"""

from typing import Literal

from langgraph.graph import StateGraph, END

from rag_agent.state import AgentState
from rag_agent.nodes import (
    load_schema_node,
    generate_sql_node,
    validate_sql_node,
    execute_sql_node,
    generate_response_node,
)


def validate_sql_router(state: AgentState) -> Literal["execute_sql", "generate_response"]:
    """
    Route based on SQL validation result.
    
    Args:
        state: Current agent state.
        
    Returns:
        Next node name: "execute_sql" if valid, "generate_response" if error.
    """
    if state.error:
        return "generate_response"
    return "execute_sql"


def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph workflow.
    
    The workflow follows this path:
    load_schema → generate_sql → validate_sql → (execute_sql if valid) → generate_response
    
    Returns:
        Compiled LangGraph workflow.
    """
    # Create the state graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("load_schema", load_schema_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("generate_response", generate_response_node)
    
    # Set entry point
    workflow.set_entry_point("load_schema")
    
    # Add edges
    workflow.add_edge("load_schema", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    # Conditional edge based on validation result
    workflow.add_conditional_edges(
        "validate_sql",
        validate_sql_router,
        {
            "execute_sql": "execute_sql",
            "generate_response": "generate_response",
        },
    )
    
    workflow.add_edge("execute_sql", "generate_response")
    workflow.add_edge("generate_response", END)
    
    # Compile the graph
    return workflow.compile()


# Compiled graph instance (lazy loaded)
_graph_instance = None


def get_graph() -> StateGraph:
    """
    Get or create the compiled graph instance.
    
    Returns:
        Compiled LangGraph workflow.
    """
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance


def run_agent(
    question: str,
    db_source: str = "sales.db",
    db_type: str = "sqlite",
    evidence: str = "",
) -> dict:
    """
    Run the RAG agent with a question.

    Args:
        question: Natural language question.
        db_source: Database source (file path or connection string).
        db_type: Database type (sqlite, postgresql, mysql, csv, xlsx).
        evidence: Optional hint/evidence for the question.

    Returns:
        Final state dictionary with response.
    """
    graph = get_graph()

    initial_state = AgentState(
        question=question,
        db_source=db_source,
        db_type=db_type,
        evidence=evidence,
    )

    result = graph.invoke(initial_state.model_dump())

    return result
