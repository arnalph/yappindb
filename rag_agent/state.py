"""
LangGraph state definition for the RAG agent.
"""

from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    State object passed through the LangGraph workflow.

    Attributes:
        question: The natural language question from the user.
        database_schema: Extracted database schema (list of table definitions).
        sql: Generated SQL query from the LLM.
        validated_sql: SQL query that passed validation.
        data: Query results as a list of dictionaries.
        response: Natural language response to return to the user.
        error: Error message if any step fails.
        db_source: Source of the database (file path, connection string, etc.).
        db_type: Type of database (sqlite, postgresql, mysql, csv, xlsx).
    """
    question: str = Field(..., description="The natural language question from the user")
    database_schema: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Extracted database schema"
    )
    formatted_schema: Optional[str] = Field(
        default=None,
        description="Formatted schema as CREATE TABLE statements"
    )
    sql: Optional[str] = Field(default=None, description="Generated SQL query")
    validated_sql: Optional[str] = Field(default=None, description="Validated SQL query")
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Query results"
    )
    response: Optional[str] = Field(default=None, description="Natural language response")
    error: Optional[str] = Field(default=None, description="Error message if any step fails")
    retry_attempted: bool = Field(default=False, description="Flag for retry mechanism")
    db_source: str = Field(default="sales.db", description="Database source")
    db_type: str = Field(default="sqlite", description="Database type")

    class Config:
        arbitrary_types_allowed = True
