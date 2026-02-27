---
name: run-quality-checks
description: Run comprehensive Python quality checks in parallel (pytest, ruff, mypy, bandit, coverage)
when_to_use: |
  Use this skill when the user wants to:
  - Run tests
  - Check code quality
  - Run pytest
  - Run linting (ruff)
  - Run type checking (mypy)
  - Run security scan (bandit)
  - Check test coverage
  - Run all quality checks in parallel
---

# Python Quality Checks Guide

You are helping the user run comprehensive Python quality checks for their project.

## Overview

The quality check suite runs 5 checks in parallel for maximum speed:
1. **pytest** - Unit and integration tests
2. **ruff** - Fast Python linter
3. **mypy** - Static type checker
4. **bandit** - Security vulnerability scanner
5. **coverage** - Test coverage analysis

Parallel execution reduces total time by ~60% compared to sequential checks.

## Running All Checks

Execute all checks in parallel:

```bash
python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --all
```

Expected output:
```
Running Python quality checks in parallel...

[pytest] ━━━━━━━━━━━━━━━━━━━━━ 48/48 tests passed
[ruff]   ━━━━━━━━━━━━━━━━━━━━━ 0 issues found
[mypy]   ━━━━━━━━━━━━━━━━━━━━━ Type check passed
[bandit] ━━━━━━━━━━━━━━━━━━━━━ 0 security issues
[coverage] ━━━━━━━━━━━━━━━━━━━ 85% coverage

✓ All checks passed in 45s (4x faster than sequential)
```

## Running Individual Checks

### pytest - Test Suite

Run unit and integration tests:

```bash
python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --pytest
```

Options:
- `--pytest-args="-v"` - Verbose output
- `--pytest-args="-k test_auth"` - Run specific tests
- `--pytest-args="--maxfail=1"` - Stop after first failure

### ruff - Linting

Check code style and common errors:

```bash
python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --ruff
```

Options:
- `--ruff-fix` - Auto-fix issues where possible
- `--ruff-args="--select E,F"` - Select specific rule categories

### mypy - Type Checking

Verify type annotations:

```bash
python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --mypy
```

Options:
- `--mypy-args="--strict"` - Strict type checking
- `--mypy-args="--ignore-missing-imports"` - Ignore missing type stubs

### bandit - Security Scanning

Scan for security vulnerabilities:

```bash
python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --bandit
```

Options:
- `--bandit-args="-ll"` - Low and low confidence issues
- `--bandit-args="--exclude tests/"` - Exclude directories

### coverage - Test Coverage

Generate coverage report:

```bash
python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --coverage
```

Options:
- `--coverage-min=80` - Set minimum coverage threshold
- `--coverage-html` - Generate HTML coverage report

## Configuration Files

### pytest - pytest.ini or pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "-v --strict-markers"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests"
]
```

### ruff - pyproject.toml

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "SIM"]
ignore = ["E501"]  # Line too long (handled by formatter)
```

### mypy - pyproject.toml

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = false
```

### bandit - pyproject.toml

```toml
[tool.bandit]
exclude_dirs = ["tests", "scripts"]
skips = ["B101", "B601"]  # Skip specific checks
```

### coverage - pyproject.toml

```toml
[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/scripts/*"]

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80
```

## Common Issues

### Issue: pytest failures

**Check:**
```bash
# Run specific failing test with verbose output
pytest tests/test_auth.py::test_login -v
```

**Solutions:**
- Check test dependencies are installed
- Verify test data/fixtures are present
- Check for environment variable requirements
- Review test output for assertion details

### Issue: ruff linting errors

**Check:**
```bash
# See detailed error with context
ruff check . --show-source
```

**Solutions:**
- Auto-fix where possible: `ruff check . --fix`
- Update code to match style guidelines
- Add `# noqa: E501` to ignore specific line (use sparingly)
- Update ruff configuration if rule is too strict

### Issue: mypy type errors

**Check:**
```bash
# Show detailed type error messages
mypy --show-error-codes --pretty
```

**Solutions:**
- Add type hints to functions
- Import types: `from typing import List, Dict, Optional`
- Use `# type: ignore` for third-party library issues
- Update mypy configuration for gradual typing

### Issue: bandit security warnings

**Check:**
```bash
# See detailed security issue descriptions
bandit -r src/ -f txt
```

**Solutions:**
- Fix security vulnerabilities (hardcoded passwords, SQL injection)
- Use `# nosec` comment for false positives (with justification)
- Update dependencies with known vulnerabilities
- Review bandit configuration if too noisy

### Issue: Low coverage

**Check:**
```bash
# Generate HTML report to see uncovered lines
coverage html
open htmlcov/index.html
```

**Solutions:**
- Add tests for uncovered code paths
- Remove dead code
- Exclude intentionally untested code (config, scripts)
- Focus on critical paths first

## CI/CD Integration

### GitHub Actions

```yaml
name: Quality Checks

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run quality checks
        run: |
          python plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py --all
```

## Performance Tips

1. **Parallel execution** - Always run checks in parallel (default)
2. **Caching** - Cache pip dependencies in CI/CD
3. **Selective testing** - Use pytest markers for targeted test runs
4. **Coverage caching** - Reuse .coverage file across runs
5. **Incremental mypy** - Enable mypy caching for faster checks

## Infiquetra Standards

For Infiquetra projects, aim for:
- **Coverage**: Minimum 80%, target 85%+
- **pytest**: All tests passing, no skipped tests
- **ruff**: Zero linting errors
- **mypy**: Type check passing (strict mode)
- **bandit**: Zero high-severity security issues

## Next Steps

After running checks:
1. Fix any failing tests
2. Address linting and type errors
3. Improve coverage for critical paths
4. Document any skipped checks with justification
5. Integrate into CI/CD pipeline
