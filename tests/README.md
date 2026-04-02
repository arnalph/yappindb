# YappinDB Test Suite

This directory contains the test suite for YappinDB.

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=rag_agent

# Run specific test file
pytest tests/test_rag_agent.py -v

# Run specific test class
pytest tests/test_rag_agent.py::TestValidateSqlNode -v
```

## Test Files

| File | Description |
|------|-------------|
| `test_rag_agent.py` | Unit tests for RAG agent nodes and graph |
| `test_db_translation.py` | Tests for database translation utilities |
| `data/` | Test data files (payloads, sample databases) |

## Test Data

The `data/` directory contains:
- `payload.json` - Sample chat request payload
- `payload_new.json` - Alternative request format
- `test_payload.json` - Test request format

## Coverage

Target coverage: 80%+

```bash
# Generate coverage report
pytest tests/ -v --cov=rag_agent --cov-report=html

# Open coverage report
start htmlcov/index.html  # Windows
open htmlcov/index.html   # macOS
xdg-open htmlcov/index.html  # Linux
```
