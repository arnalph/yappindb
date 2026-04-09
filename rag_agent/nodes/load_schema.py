"""
Load schema node - extracts database schema for the agent with enhanced details.
Includes column types, sample values, and statistics for better SQL generation.
"""

from typing import Dict, Any, List

from rag_agent.state import AgentState
from rag_agent.db import DatabaseManager, set_db_manager, get_db_manager


def format_schema_as_create_tables(schema: List[Dict[str, Any]], include_samples: bool = True) -> str:
    """
    Convert extracted schema dict to CREATE TABLE statements with sample values.

    Args:
        schema: Schema list from database.
        include_samples: Whether to include sample values.

    Returns:
        Formatted schema string.
    """
    lines = []
    for table in schema:
        name = table.get("table_name", "unknown")
        columns = table.get("columns", [])
        samples = table.get("samples", {})
        foreign_keys = table.get("foreign_keys", [])

        col_defs = []
        for col in columns:
            col_name = col.get("name", "unknown")
            col_type = col.get("type", "TEXT").upper()
            sample_val = samples.get(col_name)

            if col.get("primary_key", False):
                col_defs.append(f"{col_name} {col_type} PRIMARY KEY")
            else:
                col_def = f"{col_name} {col_type}"
                if sample_val is not None and include_samples:
                    col_def += f" -- e.g., {repr(sample_val)}"
                col_defs.append(col_def)

        # Add foreign key information
        fk_info = []
        if foreign_keys:
            for fk in foreign_keys:
                fk_columns = fk.get("columns", [])
                ref_table = fk.get("referenced_table", "")
                ref_columns = fk.get("referenced_columns", [])
                for i, fk_col in enumerate(fk_columns):
                    ref_col = ref_columns[i] if i < len(ref_columns) else "id"
                    fk_info.append(f"FOREIGN KEY ({fk_col}) REFERENCES {ref_table}({ref_col})")

        table_def = f"CREATE TABLE {name} (\n  "
        table_def += ",\n  ".join(col_defs)
        if fk_info:
            table_def += ",\n  " + ",\n  ".join(fk_info)
        table_def += "\n);"
        
        lines.append(table_def)

    return "\n".join(lines)


def get_column_samples(db_manager: DatabaseManager, table_name: str, columns: List[Dict]) -> Dict[str, Any]:
    """
    Get sample values for columns to help LLM understand data format.
    
    Args:
        db_manager: Database manager instance.
        table_name: Table to sample from.
        columns: Column definitions.
        
    Returns:
        Dict mapping column names to sample values.
    """
    samples = {}
    try:
        # Get one row of data for samples
        rows = db_manager.execute_query(f"SELECT * FROM {table_name} LIMIT 1")
        if rows:
            row = rows[0]
            for col in columns:
                col_name = col.get("name")
                if col_name in row and row[col_name] is not None:
                    val = row[col_name]
                    # Truncate long strings
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:47] + "..."
                    samples[col_name] = val
    except Exception:
        pass  # Samples are optional
    return samples


def load_schema_node(state: AgentState) -> AgentState:
    """
    Load database schema and store in state.

    This node connects to the database (SQLite, remote, or temp from CSV/XLSX)
    and extracts table names, column definitions, types, and sample values.

    Args:
        state: Current agent state.

    Returns:
        Updated agent state with schema information.
    """
    try:
        db_source = state.db_source
        db_type = state.db_type

        # Create database manager
        db_manager = DatabaseManager(db_source, db_type)

        # Set global manager for later use
        set_db_manager(db_manager)

        # Extract schema
        schema = db_manager.extract_schema()

        if not schema:
            return AgentState(
                **{
                    **state.model_dump(),
                    "error": "No tables found in the database. Check your data source.",
                }
            )

        # Enrich schema with sample values
        for table in schema:
            table_name = table.get("table_name")
            columns = table.get("columns", [])
            samples = get_column_samples(db_manager, table_name, columns)
            table["samples"] = samples

        # Store schema and formatted_schema in state for later use
        formatted_schema = format_schema_as_create_tables(schema, include_samples=True)
        
        return AgentState(
            **{
                **state.model_dump(),
                "database_schema": schema,
                "formatted_schema": formatted_schema,
                "db_type": db_type,
            }
        )

    except Exception as e:
        return AgentState(
            **{
                **state.model_dump(),
                "error": f"Unable to connect to the database: {str(e)}",
            }
        )
