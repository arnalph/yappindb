"""
FastAPI chat endpoint for the RAG agent with web UI and file upload support.
"""

from typing import Optional, List, Dict
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag_agent.graph import get_graph, run_agent
from rag_agent.state import AgentState
from rag_agent.web_ui import HTML_TEMPLATE
from rag_agent.session_manager import (
    get_session_manager,
    create_session,
    upload_file,
    remove_session,
    get_session_schema,
)


app = FastAPI(
    title="YappinDB API",
    description="Chat with your database - Natural language to SQL query generation",
    version="1.0.0",
)

# Mount static files for favicon
static_path = Path(__file__).parent.parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    question: str = Field(..., description="Natural language question")
    db_source: Optional[str] = Field(default=None, description="Database source (file path or connection string)")
    db_type: Optional[str] = Field(default="sqlite", description="Database type (sqlite, postgresql, mysql, csv, xlsx)")
    session_id: Optional[str] = Field(default=None, description="Session ID for uploaded files")
    file_id: Optional[str] = Field(default=None, description="File ID for uploaded file")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    answer: str = Field(..., description="Natural language answer")
    sql: Optional[str] = Field(default=None, description="Generated SQL query")
    data: Optional[List[Dict]] = Field(default=None, description="Query results as list of dicts")
    error: Optional[str] = Field(default=None, description="Error message if any")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")


class UploadResponse(BaseModel):
    """Response model for file upload endpoint."""

    session_id: str = Field(..., description="Session ID")
    file_id: str = Field(..., description="File ID")
    filename: str = Field(..., description="Original filename")
    db_type: str = Field(..., description="Detected database type")
    message: str = Field(default="", description="Additional message")


class SessionResponse(BaseModel):
    """Response model for session endpoints."""

    session_id: str
    active: bool
    file_count: int
    db_type: Optional[str]


class SchemaResponse(BaseModel):
    """Response model for schema endpoint."""

    tables: List[Dict] = Field(..., description="List of tables with columns")
    table_count: int = Field(..., description="Number of tables")
    message: str = Field(default="", description="Additional message")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the web UI at the root path."""
    return HTML_TEMPLATE


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/upload", response_model=UploadResponse)
async def upload_database_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
):
    """
    Upload a database file (SQLite, CSV, Excel).
    
    The file is stored in a temp folder and associated with a session.
    Files are automatically cleaned up when the session expires.
    
    Args:
        file: The file to upload.
        session_id: Optional existing session ID (creates new if not provided).
        
    Returns:
        UploadResponse with session_id, file_id, and detected db_type.
    """
    try:
        # Create or get session
        session_manager = get_session_manager()
        
        if session_id:
            session = session_manager.get_session(session_id)
            if not session:
                # Session expired, create new one
                session = session_manager.create_session()
                session_id = session.session_id
        else:
            session = session_manager.create_session()
            session_id = session.session_id
        
        # Read file content
        content = await file.read()
        
        # Upload file
        file_id, db_type, error = upload_file(
            session_id=session_id,
            file_content=content,
            filename=file.filename or "uploaded_file",
        )
        
        if error:
            raise HTTPException(status_code=400, detail=error)
        
        return UploadResponse(
            session_id=session_id,
            file_id=file_id,
            filename=file.filename or "uploaded_file",
            db_type=db_type or "unknown",
            message="File uploaded successfully. You can now ask questions about your data.",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/session/{session_id}", response_model=SessionResponse)
async def get_session_info(session_id: str):
    """
    Get session information.
    
    Args:
        session_id: Session ID to query.
        
    Returns:
        Session information including file count and db_type.
    """
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return SessionResponse(
        session_id=session_id,
        active=True,
        file_count=len(session.files),
        db_type=session.db_type,
    )


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and cleanup its files.

    Args:
        session_id: Session ID to delete.
    """
    session_manager = get_session_manager()
    session_manager.remove_session(session_id)
    return {"message": "Session deleted successfully"}


@app.get("/schema/{session_id}", response_model=SchemaResponse)
async def get_schema(session_id: str):
    """
    Get the database schema for a session.
    
    Extracts and returns the schema including tables, columns, data types,
    and foreign key relationships.
    
    Args:
        session_id: Session ID to get schema for.
        
    Returns:
        SchemaResponse with tables and column information.
    """
    schema = get_session_schema(session_id)
    
    if not schema:
        # Try to extract schema on-the-fly if not cached
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session or not session.files:
            raise HTTPException(status_code=404, detail="Session not found or no files uploaded")
        
        # Get the first file
        file_id = list(session.files.keys())[0]
        file_path = session.files[file_id]
        db_type = session.db_type or "sqlite"
        
        try:
            from rag_agent.db import DatabaseManager
            db_manager = DatabaseManager(str(file_path), db_type)
            schema = db_manager.extract_schema()
            session.set_schema(schema)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Schema extraction failed: {str(e)}")
    
    return SchemaResponse(
        tables=schema,
        table_count=len(schema),
        message=f"Schema extracted successfully. Found {len(schema)} table(s).",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a natural language question and return an answer.
    
    The agent will:
    1. Load the database schema (from uploaded file or path)
    2. Generate SQL using the LLM
    3. Validate the SQL (SELECT only)
    4. Execute the query
    5. Format results into natural language
    
    Args:
        request: Chat request with question and database info.
        
    Returns:
        Chat response with answer and optional SQL.
    """
    try:
        # Determine database source and type
        db_source = request.db_source
        db_type = request.db_type or "sqlite"
        
        # If file_id and session_id provided, use uploaded file
        if request.file_id and request.session_id:
            session_manager = get_session_manager()
            file_path = session_manager.get_file_path(request.session_id, request.file_id)
            
            if not file_path:
                return ChatResponse(
                    answer="Error: Uploaded file not found. Please upload the file again.",
                    error="File not found or session expired",
                )
            
            db_source = str(file_path)
            # Get db_type from session
            session = session_manager.get_session(request.session_id)
            if session and session.db_type:
                db_type = session.db_type
        
        # If no db_source provided, use default
        if not db_source:
            db_source = "default.db"
        
        result = run_agent(
            question=request.question,
            db_source=db_source,
            db_type=db_type,
        )
        
        if result.get("error"):
            return ChatResponse(
                answer=result.get("response", "An error occurred."),
                sql=result.get("sql") or result.get("validated_sql"),
                data=result.get("data"),
                error=result["error"],
            )

        return ChatResponse(
            answer=result.get("response", "No response generated."),
            sql=result.get("sql") or result.get("validated_sql"),
            data=result.get("data"),
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/stats")
async def get_stats():
    """Get session manager statistics."""
    session_manager = get_session_manager()
    return session_manager.get_stats()


@app.get("/api/conversations")
async def get_conversations():
    """
    Get list of active conversations/sessions.
    Returns session metadata for conversation history sidebar.
    """
    session_manager = get_session_manager()
    sessions = session_manager.get_all_sessions()
    
    # Sort by last_accessed descending
    sessions.sort(key=lambda x: x.get("last_accessed", ""), reverse=True)
    
    return {
        "conversations": sessions[:20],  # Limit to 20 most recent
        "total": len(sessions),
    }


@app.get("/api/preferences")
async def get_preferences():
    """Get user preferences (theme, etc.)."""
    # Preferences are stored client-side in localStorage
    # This endpoint is for server-side preferences if needed
    return {
        "theme": "system",  # Default to system preference
        "language": "en",
    }


@app.post("/api/preferences")
async def set_preferences(preferences: dict):
    """
    Set user preferences.
    
    Expected body:
    {
        "theme": "light" | "dark" | "system",
        "language": "en"
    }
    """
    # In production, this would save to a database
    # For now, just acknowledge the request
    return {"status": "ok", "preferences": preferences}


@app.get("/api/schema/{session_id}")
async def get_cached_schema(session_id: str):
    """
    Get cached schema for a session.
    Returns the schema that was extracted during file upload.
    """
    schema = get_session_schema(session_id)
    
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    return {
        "tables": schema,
        "table_count": len(schema),
    }
