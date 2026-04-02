"""
Query error logger - logs failed queries for debugging and analysis.
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Log file path
ERROR_LOG_PATH = Path(__file__).parent.parent / "error_queries.jsonl"


def log_failed_query(
    question: str,
    original_sql: str,
    errors: list,
    schema: list = None,
    db_type: str = "sqlite",
):
    """
    Log a failed query to the error log file.
    
    Args:
        question: Original user question.
        original_sql: SQL query that failed.
        errors: List of error messages.
        schema: Database schema (optional).
        db_type: Database type.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "original_sql": original_sql,
        "errors": errors,
        "db_type": db_type,
        "schema_tables": [t.get("table_name") for t in (schema or [])],
    }
    
    # Append to log file
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return ERROR_LOG_PATH


def get_failed_queries(limit: int = 10):
    """
    Read failed queries from the log file.
    
    Args:
        limit: Maximum number of entries to return.
        
    Returns:
        List of failed query entries.
    """
    if not ERROR_LOG_PATH.exists():
        return []
    
    entries = []
    with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    # Return most recent entries
    return entries[-limit:]


def clear_error_log():
    """Clear the error log file."""
    if ERROR_LOG_PATH.exists():
        ERROR_LOG_PATH.unlink()
