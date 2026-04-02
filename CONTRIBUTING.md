# Contributing to YappinDB

Thank you for your interest in contributing to YappinDB! This document provides guidelines and instructions for contributing.

## 🎯 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected vs actual behavior**
- **Screenshots** if applicable
- **Environment details** (OS, Python version, browser)

**Example:**
```markdown
**Bug**: SQL generation fails for complex joins

**Steps to Reproduce:**
1. Upload database with multiple related tables
2. Ask "Show me all customers with their orders and products"
3. See error: "no such column: T1.customer_id"

**Expected:** Valid SQL with proper joins
**Actual:** SQL with invalid column references

**Environment:**
- OS: Windows 11
- Python: 3.11
- Browser: Chrome 120
```

### Suggesting Features

Feature suggestions are welcome! Please provide:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Any other approaches?

### Pull Requests

1. **Fork** the repository
2. **Create** a branch from `main`:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make** your changes
4. **Test** your changes:
   ```bash
   pytest tests/ -v
   ```
5. **Commit** with clear messages:
   ```bash
   git commit -m "feat: add export to CSV functionality"
   ```
6. **Push** and create a Pull Request

## 📋 Development Guidelines

### Code Style

- Follow **PEP 8** style guidelines
- Use **type hints** for function signatures
- Write **docstrings** for public functions/classes
- Keep functions **focused and small** (< 50 lines preferred)

```python
# Good
def validate_sql(sql: str, schema: List[Dict]) -> Tuple[bool, List[str]]:
    """Validate SQL query against database schema."""
    ...

# Bad
def validate(a, b):  # No types, unclear names
    ...
```

### Testing

- Write tests for **new features**
- Maintain **>80% code coverage**
- Use **descriptive test names**:
  ```python
  def test_validate_sql_rejects_insert():  # Good
  def test_insert():  # Bad
  ```

### Documentation

- Update **README.md** for user-facing changes
- Update **docstrings** for code changes
- Add **examples** for new features

## 🚀 Project Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/yappindb.git
cd yappindb

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest pytest-cov black flake8
```

## 🔧 Common Tasks

### Running Tests
```bash
pytest tests/ -v
```

### Code Formatting
```bash
black rag_agent/ tests/
```

### Type Checking
```bash
mypy rag_agent/
```

### Coverage Report
```bash
pytest tests/ -v --cov=rag_agent --cov-report=html
start htmlcov/index.html
```

## 📝 Commit Message Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting)
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Build/config changes

**Examples:**
```bash
feat: add export to CSV functionality
fix: resolve SQL validation error for aliases
docs: update README with installation steps
refactor: simplify schema validation logic
```

## 🎨 Architecture Overview

```
User Request
    ↓
FastAPI (api.py)
    ↓
LangGraph Agent (graph.py)
    ↓
┌─────────────────────────────────┐
│  load_schema → generate_sql →  │
│  validate_sql → execute_sql →  │
│  generate_response              │
└─────────────────────────────────┘
    ↓
JSON Response
```

## ❓ Questions?

- Check existing [issues](https://github.com/yourusername/yappindb/issues)
- Start a [discussion](https://github.com/yourusername/yappindb/discussions)
- Email: support@yappindb.com

## 🙏 Thank You!

Every contribution helps make YappinDB better!
