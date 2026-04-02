"""
MCP (Model Context Protocol) server for tool integration.
"""

import asyncio
from typing import Any, Dict, List, Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from rag_agent.graph import run_agent


# Create MCP server instance
server = Server("rag-agent")


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """
    List available tools.
    
    Returns:
        List of tool definitions.
    """
    return [
        Tool(
            name="query_data",
            description="Answer questions about the loaded database using natural language. "
            "The tool generates and executes SQL queries based on your question.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the data",
                    },
                    "db_source": {
                        "type": "string",
                        "description": "Database source (file path or connection string). "
                        "Defaults to 'default.db' if not specified.",
                        "default": "default.db",
                    },
                    "db_type": {
                        "type": "string",
                        "description": "Database type: sqlite, postgresql, mysql, csv, xlsx. "
                        "Defaults to 'sqlite' if not specified.",
                        "default": "sqlite",
                        "enum": ["sqlite", "postgresql", "mysql", "csv", "xlsx"],
                    },
                },
                "required": ["question"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: Dict[str, Any],
) -> List[TextContent]:
    """
    Handle tool execution requests.
    
    Args:
        name: Tool name to execute.
        arguments: Tool arguments.
        
    Returns:
        List of text content results.
        
    Raises:
        ValueError: If unknown tool is requested.
    """
    if name == "query_data":
        question = arguments.get("question")
        db_source = arguments.get("db_source", "default.db")
        db_type = arguments.get("db_type", "sqlite")
        
        if not question:
            return [
                TextContent(
                    type="text",
                    text="Error: 'question' argument is required.",
                )
            ]
        
        try:
            result = run_agent(
                question=question,
                db_source=db_source,
                db_type=db_type,
            )
            
            if result.get("error"):
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {result['error']}",
                    )
                ]
            
            response_text = result.get("response", "No response generated.")
            
            # Include SQL if available
            sql = result.get("sql") or result.get("validated_sql")
            if sql:
                response_text = f"Generated SQL:\n```sql\n{sql}\n```\n\n{response_text}"
            
            return [
                TextContent(
                    type="text",
                    text=response_text,
                )
            ]
        
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error executing query: {str(e)}",
                )
            ]
    
    raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                name="rag-agent",
                version="0.1.0",
                capabilities=server.get_capabilities(),
            ),
        )


def run():
    """Entry point for running the MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
