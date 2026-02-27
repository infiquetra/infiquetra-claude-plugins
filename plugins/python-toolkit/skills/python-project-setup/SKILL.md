---
name: python-project-setup
description: Set up Python project with pyproject.toml, ruff, mypy, pre-commit, and uv
when_to_use: |
  Use this skill when the user wants to:
  - Create new Python project
  - Set up pyproject.toml
  - Configure ruff linting
  - Configure mypy type checking
  - Set up pre-commit hooks
  - Initialize project structure
  - Configure uv package manager
  - Scaffold Python service
---

# Python Project Setup Guide

You are helping the user set up a Python project with modern tooling and Infiquetra standards.

## Quick Start

For a new Infiquetra Python project, create this structure:

```
project-name/
├── src/
│   └── service/
│       ├── __init__.py
│       └── handler.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── unit/
│       └── __init__.py
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitignore
├── README.md
└── .python-version (optional)
```

## Step-by-Step Setup

### 1. Create pyproject.toml

Start with the minimal template from [references/pyproject-template.md](../../references/pyproject-template.md):

```toml
[project]
name = "your-service-name"
version = "0.1.0"
description = "Your service description"
requires-python = ">=3.12"
dependencies = [
    "boto3>=1.34.0",
    "aws-lambda-powertools>=2.30.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.2.0",
    "mypy>=1.8.0",
    "moto[all]>=5.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "C4", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=html --cov-fail-under=80"

[tool.mypy]
python_version = "3.12"
disallow_untyped_defs = true
```

### 2. Install uv (Recommended Package Manager)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with homebrew
brew install uv

# Verify installation
uv --version
```

### 3. Initialize Project

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install project with dev dependencies
uv pip install -e ".[dev]"

# Or with standard pip
pip install -e ".[dev]"
```

### 4. Set Up Pre-commit Hooks

Create `.pre-commit-config.yaml` (see [references/pre-commit-config.md](../../references/pre-commit-config.md)):

```yaml
default_language_version:
  python: python3.12

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [boto3-stubs]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: [-r, src/]
```

Install hooks:
```bash
pip install pre-commit
pre-commit install
```

### 5. Create .gitignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
.venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# AWS
.aws-sam/
samconfig.toml

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json
```

### 6. Create Basic Source Structure

```python
# src/service/__init__.py
"""Infiquetra Service."""
__version__ = "0.1.0"


# src/service/handler.py
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler."""
    logger.info("Processing request")

    return {
        "statusCode": 200,
        "body": {"message": "Hello from Infiquetra!"},
    }
```

### 7. Create Basic Test Structure

```python
# tests/conftest.py
import os
import pytest

# Set AWS credentials for moto
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    class MockContext:
        function_name = "test-function"
        aws_request_id = "test-request-id"

        def get_remaining_time_in_millis(self) -> int:
            return 300000

    return MockContext()


# tests/unit/test_handler.py
from src.service.handler import handler


def test_handler_success(lambda_context):
    """Test handler returns 200."""
    event = {}

    response = handler(event, lambda_context)

    assert response["statusCode"] == 200
    assert "message" in response["body"]
```

## Configuration Details

### Ruff Configuration

Ruff replaces flake8, isort, black, and more. Essential rules:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "W",      # pycodestyle warnings
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
]
ignore = [
    "E501",   # Line too long (handled by formatter)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]  # Allow assert in tests
```

Run ruff:
```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .
```

### mypy Configuration

Type checking configuration:

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
show_error_codes = true
pretty = true

# Allow third-party packages without stubs
[[tool.mypy.overrides]]
module = ["moto.*"]
ignore_missing_imports = true
```

Run mypy:
```bash
# Type check entire project
mypy src/

# Check specific file
mypy src/service/handler.py
```

### pytest Configuration

Testing configuration:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
    "-ra",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests",
]
```

Run tests:
```bash
# Run all tests with coverage
pytest

# Run only unit tests
pytest -m unit

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_handler.py
```

## Using uv Package Manager

uv is a fast Python package installer (10-100x faster than pip):

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Add new dependency
uv pip install requests

# Update pyproject.toml manually, then:
uv pip install -e ".[dev]"

# Install from requirements.txt
uv pip install -r requirements.txt

# Compile requirements
uv pip compile pyproject.toml -o requirements.txt
```

## Project Templates

### Lambda Function Project

```toml
[project]
dependencies = [
    "boto3>=1.34.0",
    "aws-lambda-powertools>=2.30.0",
]
```

### FastAPI Project

```toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "pydantic>=2.5.0",
]
```

### CDK Infrastructure Project

```toml
[project]
dependencies = [
    "aws-cdk-lib>=2.120.0",
        "constructs>=10.3.0",
]
```

## Verification Steps

After setup, verify everything works:

```bash
# 1. Check ruff
ruff check .

# 2. Check mypy
mypy src/

# 3. Run tests
pytest

# 4. Test pre-commit
pre-commit run --all-files

# 5. Verify coverage
coverage report
```

All checks should pass with 0 errors and 80%+ coverage.

## Common Issues

### "ModuleNotFoundError" when running tests

Install project in editable mode:
```bash
pip install -e .
```

### mypy complains about missing type stubs

Install type stubs:
```bash
pip install boto3-stubs[essential] types-requests
```

### Pre-commit hooks fail

Run hooks manually to see detailed errors:
```bash
pre-commit run ruff --all-files
pre-commit run mypy --all-files
```

### Coverage below 80%

View coverage report:
```bash
coverage html
open htmlcov/index.html
```

Add tests for uncovered lines.

## Infiquetra Standards Checklist

- ✅ Python 3.12+ required
- ✅ pyproject.toml with all tools configured
- ✅ ruff for linting and formatting (line-length: 100)
- ✅ mypy with strict type checking
- ✅ pytest with 80% minimum coverage
- ✅ Pre-commit hooks installed (ruff, mypy, bandit)
- ✅ AWS Lambda Powertools for serverless
- ✅ Proper test structure (unit + integration)
- ✅ .gitignore with Python exclusions
- ✅ README with setup instructions

## Next Steps

After project setup:
1. **Add business logic** to src/service/
2. **Write tests** following [python-testing-patterns](../python-testing-patterns/SKILL.md)
3. **Use Cox patterns** from [cox-python-patterns](../cox-python-patterns/SKILL.md)
4. **Run quality checks** before committing
5. **Set up CI/CD** with GitHub Actions

## Related Skills

- [python-testing-patterns](../python-testing-patterns/SKILL.md) - Testing best practices
- [cox-python-patterns](../cox-python-patterns/SKILL.md) - Cox/Infiquetra-specific patterns

## Related References

- [pyproject-template.md](../../references/pyproject-template.md) - Complete pyproject.toml examples
- [pre-commit-config.md](../../references/pre-commit-config.md) - Pre-commit setup details
- [testing-patterns.md](../../references/testing-patterns.md) - Testing strategies
