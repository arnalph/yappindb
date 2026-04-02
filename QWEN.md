# YappinDB - Project Context

## Project Overview

**YappinDB** (subtitle: "Chat with your database") is a **LangGraph-based RAG (Retrieval-Augmented Generation) agent** that converts natural language questions into SQL queries. It uses lightweight GGUF-format models (Qwen2.5-Coder-3B, Phi-3, DeepSeek-Coder) for local CPU inference, eliminating the need for GPU hardware.

### Core Features
- **Natural Language to SQL**: Ask questions in plain English, get SQL queries and answers
- **Multiple Database Support**: SQLite files, CSV/XLSX files, PostgreSQL, MySQL
- **GGUF Model Support**: Local inference via llama-cpp-python (~0.8-4.5 GB RAM depending on model)
- **Read-Only Safety**: SQL validation ensures only SELECT queries are executed
- **Persistent Caching**: File-based caching in `cache/cache.db` reduces repeated LLM calls
- **FastAPI Web Interface**: REST API with built-in web UI for file upload and chat
- **MCP Support**: Model Context Protocol for tool integration

### Architecture

The agent follows a LangGraph workflow with these nodes:

```
load_schema → generate_sql → validate_sql → execute_sql → generate_response
                                      ↓
                              (error path) → generate_response
```

**Node Responsibilities:**
| Node | File | Purpose |
|------|------|---------|
| `load_schema` | `rag_agent/nodes/load_schema.py` | Extract database schema |
| `generate_sql` | `rag_agent/nodes/generate_sql.py` | LLM generates SQL from question + schema |
| `validate_sql` | `rag_agent/nodes/validate_sql.py` | Ensure only SELECT queries (security) |
| `execute_sql` | `rag_agent/nodes/execute_sql.py` | Run query with caching |
| `generate_response` | `rag_agent/nodes/generate_response.py` | Format results as natural language |

## Project Structure

```
DBarf/
├── rag_agent/
│   ├── __init__.py           # Package init
│   ├── state.py              # AgentState Pydantic model
│   ├── graph.py              # LangGraph workflow definition
│   ├── model.py              # SQLGenerator (GGUF/HF API)
│   ├── config.py             # Configuration manager (config.json + .env)
│   ├── db.py                 # DatabaseManager (SQLAlchemy)
│   ├── cache.py              # DiskCache wrapper
│   ├── api.py                # FastAPI app + REST endpoints
│   ├── web_ui.py             # HTML template for web interface
│   ├── session_manager.py    # Session/file upload management
│   ├── sql_validator.py      # Additional SQL validation utilities
│   ├── schema_validator.py   # Schema validation
│   ├── query_logger.py       # Query logging
│   ├── mcp_server.py         # MCP server implementation
│   └── nodes/
│       ├── __init__.py
│       ├── load_schema.py
│       ├── generate_sql.py
│       ├── validate_sql.py
│       ├── execute_sql.py
│       └── generate_response.py
├── models/                   # GGUF model files (downloaded separately)
├── cache/
│   └── cache.db              # Query cache (auto-created)
├── tests/
│   ├── __init__.py
│   ├── test_rag_agent.py     # Unit tests for nodes and graph
│   └── test_db_translation.py # DB translation tests
├── scripts/
│   └── download_model.py     # Model download script
├── config.json               # Main configuration file
├── .env.example              # Environment variable template
├── requirements.txt          # Python dependencies
└── README.md                 # User documentation
```

## Building and Running

### Prerequisites
- Python 3.10+
- pip package manager
- C++ compiler (for llama-cpp-python on Windows)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Download a GGUF model (if using local mode)
python scripts/download_model.py
```

### Running the Application

```bash
# Start FastAPI server (includes web UI at http://localhost:8000)
uvicorn rag_agent.api:app --host 0.0.0.0 --port 8000

# Or run directly
python -m uvicorn rag_agent.api:app --reload
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=rag_agent

# Run specific test class
pytest tests/test_rag_agent.py::TestValidateSqlNode -v
```

### Key Commands Summary

| Command | Purpose |
|---------|---------|
| `pip install -r requirements.txt` | Install dependencies |
| `python scripts/download_model.py` | Download GGUF model |
| `uvicorn rag_agent.api:app --port 8000` | Start web server |
| `pytest tests/ -v` | Run tests |
| `pytest tests/ -v --cov=rag_agent` | Run tests with coverage |

## Configuration

Configuration is managed via `config.json` and environment variables (`.env` file).

### config.json Structure

```json
{
  "model_mode": "gguf",
  "gguf": {
    "model_name": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
    "hf_repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
    "n_ctx": 8192,
    "n_threads": 8,
    "n_gpu_layers": 0
  },
  "hf_api": {
    "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "api_key": "your_huggingface_api_key_here",
    "max_new_tokens": 1024,
    "temperature": 0.1,
    "top_p": 0.9
  },
  "generation": {
    "max_tokens": 1024,
    "temperature": 0.1,
    "top_p": 0.9,
    "top_k": 40
  },
  "debug": {
    "print_schema": true,
    "log_queries": true
  },
  "validation": {
    "enable_schema_validation": true,
    "strict_alias_checking": false,
    "disable_aliases": true
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DBARF_MODEL_MODE` | `gguf` (local) or `hf_api` | `hf_api` |
| `GGUF_MODEL_NAME` | Model filename in `models/` | `qwen2.5-coder-3b-instruct-q4_k_m.gguf` |
| `GGUF_N_CTX` | Context window size | `8192` |
| `GGUF_N_THREADS` | CPU threads for inference | `8` |
| `HF_API_TOKEN` | HuggingFace API token (for hf_api mode, overrides config.json) | - |
| `HF_API_KEY` | Alternative env var for API key | - |
| `HF_MODEL_ID` | HF model ID (for hf_api mode) | `Qwen/Qwen2.5-Coder-32B-Instruct` |
| `DEBUG_PRINT_SCHEMA` | Print schema to console | `true` |
| `DEBUG_LOG_QUERIES` | Log queries to file | `true` |

### API Key Configuration

You can set your Hugging Face API key in two ways:

**Option 1: In config.json (recommended)**
```json
{
  "hf_api": {
    "api_key": "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

**Option 2: In .env file**
```
HF_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Get your API token from: https://huggingface.co/settings/tokens

### Recommended Models for HF API

| Model | Size | Quality | Notes |
|-------|------|---------|-------|
| `Qwen/Qwen2.5-Coder-32B-Instruct` | 32B | Best | Requires Pro account, excellent SQL generation |
| `Qwen/Qwen2.5-Coder-7B-Instruct` | 7B | Good | Free tier, good SQL generation |
| `defog/sqlcoder-7b-2` | 7B | Good | Specialized for SQL, may be slower |

## Development Conventions

### Code Style
- **Type Hints**: Used throughout with `typing` module
- **Pydantic Models**: `AgentState` uses Pydantic for validation
- **Docstrings**: Google-style docstrings on all public functions/classes
- **Error Handling**: Errors propagated via `state.error` field

### Testing Practices
- **pytest**: All tests in `tests/` directory
- **Unit Tests**: Individual node testing with mocks
- **Integration Tests**: Full graph flow testing
- **Test Classes**: Organized by component (e.g., `TestValidateSqlNode`)

### Key Design Patterns
- **Singleton Pattern**: Model loaded once via `get_generator()`
- **Factory Pattern**: `get_graph()`, `get_config()`, `get_db_manager()`
- **State Machine**: LangGraph workflow with conditional routing
- **Caching**: DiskCache for query results with expiration

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/chat` | POST | Ask questions (JSON body) |
| `/upload` | POST | Upload database file |
| `/schema/{session_id}` | GET | Get database schema |
| `/session/{session_id}` | GET | Get session info |
| `/session/{session_id}` | DELETE | End session |
| `/health` | GET | Health check |
| `/stats` | GET | Server statistics |

### Chat Request Format

```json
{
  "question": "What are the top 5 products by revenue?",
  "db_source": "sales.db",
  "db_type": "sqlite",
  "session_id": "optional-session-id",
  "file_id": "optional-file-id"
}
```

### Chat Response Format

```json
{
  "answer": "The top 5 products by revenue are...",
  "sql": "SELECT product, SUM(revenue) FROM sales GROUP BY product ORDER BY 2 DESC LIMIT 5",
  "data": [{"product": "A", "revenue": 1000}, ...],
  "error": null
}
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `rag_agent/state.py` | AgentState Pydantic model definition |
| `rag_agent/graph.py` | LangGraph workflow builder and `run_agent()` entry point |
| `rag_agent/model.py` | SQLGenerator class for LLM inference |
| `rag_agent/config.py` | Configuration manager (loads config.json + .env) |
| `rag_agent/db.py` | DatabaseManager for SQLAlchemy operations |
| `rag_agent/cache.py` | DiskCache wrapper for query caching |
| `rag_agent/api.py` | FastAPI application with REST endpoints |
| `rag_agent/nodes/validate_sql.py` | SQL validation (SELECT-only enforcement) |
| `tests/test_rag_agent.py` | Comprehensive unit tests |

## Common Tasks

### Add a New Node
1. Create file in `rag_agent/nodes/`
2. Define function with signature `def node_name(state: AgentState) -> AgentState`
3. Import and add to `rag_agent/graph.py` workflow

### Change Model Configuration
1. Edit `config.json` or set environment variables
2. For new GGUF models, add to `KNOWN_GGUF_MODELS` in `config.py`
3. Download model: `python scripts/download_model.py`

### Debug SQL Generation
- Set `DEBUG_PRINT_SCHEMA=true` to see schema sent to LLM
- Set `DEBUG_LOG_QUERIES=true` to log failed queries
- Check `err_sql.txt` for failed query logs with timestamps

### Performance Tuning
- Increase `GGUF_N_THREADS` to match CPU cores
- Use smaller models (Q2_K, Q4_K_M) for faster inference
- Enable GPU offload with `n_gpu_layers > 0` (if GPU available)

## SQL Accuracy Improvements

The system includes several mechanisms to improve SQL generation accuracy:

### 1. Enhanced Schema Format
- Schema now includes sample values for each column (e.g., `price NUMERIC -- e.g., 29.99`)
- This helps the LLM understand data types and formats

### 2. Stricter Prompt Rules
- The SQL generation prompt now includes explicit rules:
  - "USE ONLY EXISTING COLUMNS"
  - "COPY COLUMN NAMES EXACTLY"
  - "NO ASSUMPTIONS" about column existence
  - Specific guidance for common terms (revenue → price, quantity → COUNT)

### 3. Schema Validation with Alias Support
- Before execution, SQL is validated against the actual database schema
- **Properly handles table aliases** (e.g., `products AS T3`)
- If a column is not found, the system suggests similar column names

### 4. Semantic Query Refinement
- The system analyzes the user's question to identify key business terms
- Maps terms to appropriate column types:
  - `revenue`, `sales` → numeric_metric (prefer price, payment_value)
  - `quantity`, `count` → count_metric (prefer COUNT or quantity columns)
  - `category`, `type` → category_dimension
  - `customer`, `buyer` → customer_dimension
  - `product`, `item` → product_dimension
- Provides intelligent column suggestions in correction prompts

### 5. Automatic SQL Repair
- When execution fails with "no such column" error, the system:
  1. Identifies the invalid column
  2. Analyzes the question for semantic intent
  3. Suggests appropriate columns based on term analysis
  4. Asks the LLM to repair using the suggestions
  5. Retries execution with the repaired query

### 6. Error Logging
- All failed queries are logged to `err_sql.txt` with:
  - Timestamp
  - Original question
  - Failed SQL
  - Error message
  - Available tables

### 7. Configurable Validation
- Schema validation can be enabled/disabled via `config.json`
- Useful for debugging LLM output without validation interference
```json
{
  "validation": {
    "enable_schema_validation": true
  }
}
```

### 8. Automatic Alias Expansion
- When `disable_aliases: true`, the system automatically converts table aliases to full names
- Example: `FROM order_items AS T1` → `FROM order_items`
- Example: `T1.price` → `order_items.price`
```json
{
  "validation": {
    "enable_schema_validation": true
  }
}
```
