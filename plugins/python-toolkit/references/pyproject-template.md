# pyproject.toml Template

Complete `pyproject.toml` template for Infiquetra Python projects with all standard configurations.

## Complete Template

```toml
[project]
name = "service-name"
version = "1.0.0"
description = "Description of your Infiquetra service"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "Proprietary" }
authors = [
    { name = "Infiquetra Team", email = "hello@infiquetra.com" }
]

dependencies = [
    # AWS Core
    "boto3>=1.34.0",
    "aws-lambda-powertools>=2.30.0",

    # HTTP & API
    "requests>=2.31.0",
    "httpx>=0.26.0",

    # Data & Parsing
    "pyyaml>=6.0.1",
    "pydantic>=2.5.0",

    # CDK (if applicable)
    "aws-cdk-lib>=2.120.0",
    ]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "moto[all]>=5.0.0",

    # Code Quality
    "ruff>=0.2.0",
    "mypy>=1.8.0",
    "bandit>=1.7.6",
    "safety>=3.0.0",

    # Type Stubs
    "boto3-stubs[essential]>=1.34.0",
    "types-requests>=2.31.0",
    "types-pyyaml>=6.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# ============================================================================
# Ruff Configuration
# ============================================================================

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]
extend-exclude = [
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    "*.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    "htmlcov",
    "dist",
    "build",
]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "RUF",    # ruff-specific rules
]
ignore = [
    "E501",   # Line too long (handled by formatter)
    "B008",   # Function call in argument defaults
    "UP007",  # Use X | Y for type annotations (prefer Optional)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "S101",   # Allow assert in tests
    "S105",   # Allow hardcoded passwords in tests
    "S106",   # Allow hardcoded passwords in tests
]
"__init__.py" = [
    "F401",   # Allow unused imports in __init__.py
]

[tool.ruff.lint.isort]
known-first-party = ["src"]
force-sort-within-sections = true

# ============================================================================
# pytest Configuration
# ============================================================================

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term-missing:skip-covered",
    "--cov-fail-under=80",
    "-ra",
    "--tb=short",
]
markers = [
    "unit: Unit tests (fast, isolated)",
    "integration: Integration tests (slower, external dependencies)",
    "slow: Slow tests (skip in CI with -m 'not slow')",
    "aws: Tests requiring AWS services",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
]

# ============================================================================
# Coverage Configuration
# ============================================================================

[tool.coverage.run]
source = ["src"]
branch = true
omit = [
    "*/tests/*",
    "*/test_*.py",
    "*/__pycache__/*",
    "*/site-packages/*",
    "*/venv/*",
    "*/.venv/*",
]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "def __str__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
    "@abc.abstractmethod",
]

[tool.coverage.html]
directory = "htmlcov"

# ============================================================================
# mypy Configuration
# ============================================================================

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
disallow_untyped_defs = true
disallow_any_unimported = false
disallow_any_generics = true
disallow_subclassing_any = true
check_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
show_error_context = true
pretty = true

# Allow third-party packages without type stubs
[[tool.mypy.overrides]]
module = [
    "moto.*",
    ]
ignore_missing_imports = true

# ============================================================================
# bandit Configuration
# ============================================================================

[tool.bandit]
exclude_dirs = [
    "tests",
    "scripts",
    ".venv",
    "venv",
]
skips = [
    "B101",  # Allow assert in tests
]
```

## Minimal Template (Quick Start)

For new projects, start with this minimal configuration:

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

## Common Dependencies by Use Case

### Lambda Function
```toml
dependencies = [
    "boto3>=1.34.0",
    "aws-lambda-powertools>=2.30.0",
]
```

### REST API (FastAPI)
```toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "pydantic>=2.5.0",
]
```

### CDK Infrastructure
```toml
dependencies = [
    "aws-cdk-lib>=2.120.0",
        "constructs>=10.3.0",
]
```

### DynamoDB Heavy
```toml
dependencies = [
    "boto3>=1.34.0",
    "pynamodb>=6.0.0",  # Optional ORM
]
```

### Testing with AWS Mocks
```toml
[project.optional-dependencies]
dev = [
    "moto[dynamodb,s3,lambda]>=5.0.0",  # Only needed services
]
```

## Usage

1. Copy the complete or minimal template to your project root as `pyproject.toml`
2. Update project name, version, and description
3. Add/remove dependencies based on your service needs
4. Install dependencies:
   ```bash
   # Using uv (recommended)
   uv pip install -e ".[dev]"

   # Using pip
   pip install -e ".[dev]"
   ```

## Infiquetra Standards

- **Python Version**: 3.12+ required
- **Line Length**: 100 characters (ruff + formatter)
- **Coverage**: Minimum 80%, fail under threshold
- **Type Checking**: Strict mode with mypy
- **Testing**: pytest with coverage reporting
- **Security**: bandit scanning for vulnerabilities

## Related References

- [pre-commit-config.md](./pre-commit-config.md) - Pre-commit hooks setup
- [testing-patterns.md](./testing-patterns.md) - Testing strategies
- [lambda-patterns.md](./lambda-patterns.md) - Lambda Powertools patterns
