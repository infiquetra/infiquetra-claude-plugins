# python-toolkit

Python development toolkit for Infiquetra projects with project setup, testing patterns, and your organization-specific Python practices.

## Overview

The `python-toolkit` plugin provides three specialized skills and comprehensive reference documentation for Python development at your organization, focusing on:
- Modern Python project setup with pyproject.toml, ruff, mypy, and pre-commit hooks
- Testing strategies with pytest, moto, fixtures, and 80%+ coverage
- your organization patterns including Lambda Powertools, and DynamoDB best practices

**Key Features:**
- **Project scaffolding** with Infiquetra standards
- **Testing frameworks** and AWS service mocking
- **Lambda Powertools** integration patterns
- **DynamoDB** single table design patterns
- **Pre-commit hooks** for code quality
- **Type checking** with mypy strict mode
- **Fast linting** with ruff
- **Complete reference documentation** with copy-paste examples

## Skills

### 1. python-project-setup

Set up Python projects with modern tooling and Infiquetra standards.

**Use when you need to:**
- Create new Python project
- Configure pyproject.toml
- Set up ruff linting
- Configure mypy type checking
- Initialize pre-commit hooks
- Create project directory structure
- Configure uv package manager

**What it provides:**
- Complete pyproject.toml template with all tools configured
- Pre-commit hooks setup (ruff, mypy, bandit)
- Project structure with src/ and tests/
- Virtual environment setup with uv
- .gitignore for Python projects
- Basic Lambda handler template

**Usage:**
```bash
# The skill will guide you through:
# 1. Creating pyproject.toml with Infiquetra standards
# 2. Installing uv package manager
# 3. Setting up pre-commit hooks
# 4. Creating project structure
# 5. Verifying setup with linting and tests
```

### 2. python-testing-patterns

Python testing best practices with pytest, moto, fixtures, and coverage.

**Use when you need to:**
- Write tests
- Set up pytest
- Create test fixtures
- Mock AWS services
- Improve test coverage
- Set up conftest.py
- Test Lambda functions
- Run integration tests

**What it provides:**
- conftest.py with AWS mocking fixtures
- Unit test patterns for Lambda handlers
- Integration test examples
- Moto setup for DynamoDB, S3, Lambda
- Parametrized testing patterns
- Coverage strategies (80%+ target)
- TDD workflow guidance

**Usage:**
```bash
# The skill covers:
# - Creating tests/conftest.py with shared fixtures
# - Writing unit tests for Lambda handlers
# - Mocking AWS services with moto
# - Parametrizing similar test cases
# - Achieving 80%+ test coverage
```

### 3. cox-python-patterns

Python patterns for Lambda Powertools, DynamoDB, and serverless applications.

**Use when you need to:**
- Set up Lambda Powertools
- Configure structured logging
- Access DynamoDB
- Use Infiquetra base classes
- Implement Cox patterns
- Handle AWS authentication
- Manage secrets

**What it provides:**
- Lambda Powertools integration (Logger, Tracer, Metrics)
- DynamoDB single table design
- Repository patterns
- Error handling standards
- Environment variable management
- Secrets retrieval patterns

**Usage:**
```bash
# The skill demonstrates:
# - Lambda Powertools decorators and usage
# - DynamoDB access patterns with composite keys
# - Structured error responses
# - Infiquetra best practices
```

## Reference Documentation

Complete reference guides with copy-paste templates:

### pyproject-template.md
Complete pyproject.toml configuration for Infiquetra projects:
- Full template with all tools configured (ruff, mypy, pytest, bandit, coverage)
- Minimal quick-start template
- Common dependencies by use case (Lambda, FastAPI, CDK)
- Tool configuration explanations

### pre-commit-config.md
Pre-commit hooks setup and configuration:
- Complete .pre-commit-config.yaml with all hooks
- Minimal configuration for quick setup
- Hook-by-hook explanations (ruff, mypy, bandit)
- CI/CD integration examples
- Troubleshooting guide

### testing-patterns.md
Comprehensive testing strategies and patterns:
- conftest.py fixtures for AWS mocking
- Lambda handler testing examples
- DynamoDB and S3 testing patterns
- Parametrized testing examples
- Integration test patterns
- Coverage strategies
- TDD workflow

### lambda-patterns.md
AWS Lambda Powertools patterns and best practices:
- Complete Lambda handler setup
- Structured logging patterns
- Distributed tracing examples
- Metrics and dimensions
- Event handler for API Gateway
- DynamoDB access patterns
- Error handling patterns
- Complete working examples

## Agent

### python-expert

Trimmed Python expert agent persona for specialized guidance.

**Expertise:**
- Python 3.12+ development
- pytest and testing strategies
- AWS Lambda Powertools
- DynamoDB patterns
- your organization standards
- Code quality and type checking

**When to use:**
- Complex Python architecture decisions
- Testing strategy guidance
- Lambda optimization
- DynamoDB design
- Debugging Python issues

## Installation

This plugin is part of the claude-plugins repository and is automatically available when the repository is installed.

### Prerequisites
- Python 3.12+
- uv package manager (recommended)
- git

### Plugin Location
```
~/.claude/plugins/python-toolkit/
```

## Quick Start Examples

### Example 1: New Python Lambda Project

```bash
# 1. Create project directory
mkdir my-lambda-service && cd my-lambda-service

# 2. Create pyproject.toml (use python-project-setup skill)
# - Copy minimal template from reference/pyproject-template.md
# - Update name and description

# 3. Install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 4. Set up pre-commit hooks
pip install pre-commit
# Create .pre-commit-config.yaml from reference/pre-commit-config.md
pre-commit install

# 5. Create project structure
mkdir -p src/service tests/unit tests/integration
touch src/service/__init__.py src/service/handler.py
touch tests/conftest.py tests/__init__.py

# 6. Create Lambda handler (use cox-python-patterns skill)
# Add Lambda Powertools pattern to src/service/handler.py

# 7. Create tests (use python-testing-patterns skill)
# Add conftest.py fixtures and unit tests

# 8. Verify setup
ruff check .
mypy src/
pytest

# 9. Ready to develop!
```

### Example 2: Add Testing to Existing Project

```bash
# 1. Add test dependencies to pyproject.toml
# [project.optional-dependencies]
# dev = ["pytest>=8.0.0", "pytest-cov>=4.1.0", "moto[all]>=5.0.0"]

# 2. Install dependencies
uv pip install -e ".[dev]"

# 3. Create tests/ directory structure
mkdir -p tests/unit tests/integration
touch tests/__init__.py

# 4. Create conftest.py (use python-testing-patterns skill)
# Add AWS mocking fixtures from reference/testing-patterns.md

# 5. Write unit tests
# Use examples from python-testing-patterns skill

# 6. Run tests with coverage
pytest --cov=src --cov-report=html

# 7. View coverage report
open htmlcov/index.html
```

### Example 3: Lambda with DynamoDB

```python
# Use cox-python-patterns skill for complete example

# src/handler.py
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="my-service")
tracer = Tracer(service="my-service")
metrics = Metrics(namespace="MyService")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler with Powertools."""
    logger.info("Processing request")

    # Business logic
    result = process_request(event)

    return {"statusCode": 200, "body": result}


# See cox-python-patterns skill for complete DynamoDB patterns
```

## Integration with Infiquetra Workflows

### During Development
1. **Project setup**: Use `python-project-setup` skill for new projects
2. **Add tests**: Use `python-testing-patterns` skill while coding
3. **Follow patterns**: Reference `cox-python-patterns` for Cox standards
4. **Pre-commit**: Hooks run automatically on `git commit`

### Pre-PR Checklist
```bash
# Run all quality checks
ruff check .            # Linting
ruff format .           # Formatting
mypy src/               # Type checking
bandit -r src/          # Security scan
pytest                  # Tests with coverage

# Or use test-suite plugin for parallel execution
```

### CI/CD Integration
```yaml
# .github/workflows/test.yml
- name: Run quality checks
  run: |
    pip install -e ".[dev]"
    ruff check .
    mypy src/
    pytest --cov=src --cov-fail-under=80
```

## Infiquetra Python Standards

This toolkit enforces Infiquetra Python standards:

### Required Standards
- ✅ **Python 3.12+** required
- ✅ **80% minimum test coverage**
- ✅ **Type hints** on all functions (mypy strict)
- ✅ **Line length**: 100 characters
- ✅ **Pre-commit hooks**: ruff, mypy, bandit
- ✅ **AWS Lambda Powertools** for serverless
- ✅ **Structured logging** with context
- ✅ **DynamoDB single table** design patterns

### Project Structure
```
project/
├── src/
│   └── service/
│       ├── __init__.py
│       ├── handler.py
│       ├── db/
│       │   └── service.py
│       └── repositories/
│           └── wallet.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   └── test_handler.py
│   └── integration/
│       └── test_api.py
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitignore
└── README.md
```

### Tool Versions
- ruff >= 0.2.0
- mypy >= 1.8.0
- pytest >= 8.0.0
- pytest-cov >= 4.1.0
- bandit >= 1.7.6
- aws-lambda-powertools >= 2.30.0
- moto >= 5.0.0

## Troubleshooting

### "ruff: command not found"
```bash
pip install ruff
# Or: uv pip install ruff
```

### "ModuleNotFoundError" in tests
```bash
# Install project in editable mode
pip install -e .
```

### mypy type errors on AWS libraries
```bash
# Install type stubs
pip install boto3-stubs[essential] types-requests types-pyyaml
```

### Coverage below 80%
```bash
# View detailed coverage report
coverage html
open htmlcov/index.html

# Focus on critical paths first
# Add tests for red/yellow highlighted code
```

### Pre-commit hooks fail
```bash
# Run hooks manually to see detailed errors
pre-commit run --all-files

# Fix issues
ruff check . --fix
mypy src/

# Try commit again
git commit -m "your message"
```

### Lambda cold starts too slow
- Minimize dependencies
- Use Lambda layers for large packages
- Enable X-Ray tracing to identify bottlenecks
- Consider provisioned concurrency for critical functions

## Related Plugins

- **test-suite**: Parallel test runner for Python quality checks
- **cdk-deployer**: CDK deployment
- **component-manager**: Component ID management
- **docs-generator**: Automated documentation generation

## Contributing

This plugin is maintained by the Infiquetra team. For issues or suggestions:
- Create issue in claude-plugins repository
- Slack: 

## Resources

### Documentation
- [AWS Lambda Powertools Python](https://docs.aws.amazon.com/powertools/python/latest/)
- [pytest Documentation](https://docs.pytest.org/)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [moto Documentation](https://docs.getmoto.org/)

### Internal Resources
- Infiquetra Documentation: Development standards and guidelines
- your organization Python Guidelines

## License

Proprietary - your organization Internal Use Only

## Support

- **Slack**: 
- **Email**: hello@infiquetra.com
- **Issues**: GitHub Issues in claude-plugins repository
