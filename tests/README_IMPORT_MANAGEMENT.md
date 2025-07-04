# Managing Package Imports in Tests

This document explains the different approaches for managing package imports in tests and why we've chosen the current approach.

## Approaches (from Best to Worst)

### 1. **Install Package in Development Mode (Recommended)**

**Best Practice**: Install your package in development mode so tests can import it normally.

```bash
# Install in development mode
pip install -e .

# Or with uv
uv pip install -e .
```

**Benefits**:
- Tests can import normally: `from src.utils.gpt_helper import GPTContentGenerator`
- No path manipulation needed
- Works consistently across different environments
- IDE autocomplete and type checking work properly

### 2. **Use pytest Configuration (Current Approach)**

We've configured pytest to automatically add the `src` directory to the Python path:

```toml
# pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["src"]
```

**Benefits**:
- No manual path manipulation in test files
- Works automatically when running pytest
- Centralized configuration

### 3. **Use conftest.py for Shared Setup**

We've created `tests/conftest.py` that handles imports and provides shared fixtures:

```python
# tests/conftest.py
import sys
from pathlib import Path

# Add src to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
```

**Benefits**:
- Shared across all tests
- Provides common fixtures
- Handles imports automatically

### 4. **Manual Path Manipulation (Avoid)**

**Don't do this**:
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

**Problems**:
- Hard to maintain
- Brittle when file structure changes
- Duplicated across files
- IDE doesn't understand the imports

## Current Implementation

We've implemented a hybrid approach:

1. **pytest configuration**: Automatically adds `src` to Python path
2. **conftest.py**: Provides shared fixtures and handles edge cases
3. **Clean imports**: Test files can import normally without path manipulation

## Example Usage

### Before (Manual Path Management)
```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.gpt_helper import GPTContentGenerator
```

### After (Clean Imports)
```python
from src.utils.gpt_helper import GPTContentGenerator
```

## Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run with coverage
pytest --cov=src
```

## IDE Configuration

For best IDE support, make sure your IDE recognizes the project structure:

1. **VS Code**: Should automatically detect the Python path from `pyproject.toml`
2. **PyCharm**: Mark `src` as a source root
3. **Vim/Neovim**: Configure your LSP to use the project root

## Migration Guide

To migrate existing test files:

1. Remove manual `sys.path` manipulation
2. Remove `import sys, os` if only used for path manipulation
3. Keep clean imports: `from src.module import function`
4. Use fixtures from `conftest.py` when available

## Troubleshooting

### Import Errors
If you get import errors:
1. Make sure you're running tests from the project root
2. Check that `pyproject.toml` has the correct `pythonpath` setting
3. Verify `conftest.py` is in the `tests/` directory

### IDE Issues
If your IDE doesn't recognize imports:
1. Restart your IDE
2. Check that the project root is set correctly
3. Verify that `src` is marked as a source directory 