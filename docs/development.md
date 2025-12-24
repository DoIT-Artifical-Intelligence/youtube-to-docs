# Development Guide

## Prerequisites

- Python 3.14 or higher
- `uv` (recommended) or `pip`

## Installation

1. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   # OR
   pip install -r requirements.txt
   ```

## Running Tests

We use `pytest` for testing.

### Using `uv` (Recommended)

To run tests with all dependencies automatically handled:

```bash
uv run --with-requirements requirements.txt pytest
```

## Project Structure

- `main.py`: Main application script.
- `tests/`: Directory containing test files.
- `requirements.txt`: Python package dependencies.

## Tooling

This project uses modern Python tooling for code quality:

- **Ruff**: For linting and code formatting.
- **Ty**: For static type checking.

These tools are configured in `pyproject.toml`.

### Running Ruff

To check for linting errors:

```bash
uv tool run ruff check .
```

To fix fixable linting errors automatically:

```bash
uv tool run ruff check --fix .
```

To format the code:

```bash
uv tool run ruff format .
```

### Running Ty (Type Checking)

To run type checks:

```bash
uv tool run ty check
```

