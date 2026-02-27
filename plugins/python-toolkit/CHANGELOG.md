# Changelog

All notable changes to the python-toolkit plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-11

### Added
- Initial release of python-toolkit plugin
- **python-project-setup** skill for project scaffolding with pyproject.toml, ruff, mypy, pre-commit
- **python-testing-patterns** skill for pytest, moto, fixtures, coverage, and TDD workflows
- **python-patterns** skill for Lambda Powertools, DynamoDB, and serverless patterns
- Reference documentation:
  - `pyproject-template.md` - Complete pyproject.toml configuration
  - `pre-commit-config.md` - Pre-commit hooks setup
  - `testing-patterns.md` - Testing strategies and examples
  - `lambda-patterns.md` - Lambda Powertools patterns
- Python expert agent persona for specialized guidance
- Infiquetra-specific standards: 80% coverage, Python 3.12+, comprehensive tooling

### Standards
- Python 3.12+ required
- 80% minimum test coverage
- Type hints with mypy strict mode
- Ruff for linting (line-length: 100)
- Pre-commit hooks: ruff, mypy, bandit
- AWS Lambda Powertools for serverless
