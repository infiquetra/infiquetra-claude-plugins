# test-suite

Parallel test runner for comprehensive Python quality checks across Infiquetra services.

## Overview

The `test-suite` skill executes all Python quality checks in parallel, dramatically reducing test execution time from 10-12 minutes to 3-4 minutes. It runs pytest, ruff linting, mypy type checking, and bandit security scanning simultaneously, then generates a consolidated HTML report with coverage metrics.

**Key Features:**
- **Parallel execution** of pytest, ruff, mypy, and bandit (4x faster)
- **Coverage enforcement** with configurable threshold (default: 80%)
- **Consolidated HTML report** with all results in one view
- **JSON output** for CI/CD integration
- **Pre-commit hook integration** for local development
- **Fail-fast mode** for rapid feedback
- **Selective test execution** (unit, integration, or all)

## Usage

```bash
# Run all tests in parallel (default)
python3 scripts/test_runner.py

# Run with specific coverage threshold
python3 scripts/test_runner.py --coverage 85

# Run only specific checks
python3 scripts/test_runner.py --checks pytest,ruff

# Fail-fast mode (stop on first failure)
python3 scripts/test_runner.py --fail-fast

# Generate JSON output for CI/CD
python3 scripts/test_runner.py --output json --output-file results.json

# Verbose mode
python3 scripts/test_runner.py --verbose

# Run only unit tests
python3 scripts/test_runner.py --test-type unit

# Skip slow tests
python3 scripts/test_runner.py --skip-slow
```

## Prerequisites

### Required Tools
- Python 3.12+
- `pytest` with coverage plugin
- `ruff` for linting
- `mypy` for type checking
- `bandit` for security scanning

### Installation
```bash
# Using uv (recommended)
uv pip install pytest pytest-cov ruff mypy bandit

# Using pip
pip install pytest pytest-cov ruff mypy bandit
```

### Project Structure
The test runner expects a standard Infiquetra project structure:
```
project/
├── src/              # Source code
├── tests/            # Test files
│   ├── unit/         # Unit tests
│   └── integration/  # Integration tests
├── pyproject.toml    # Project configuration
└── .coveragerc       # Coverage configuration (optional)
```

## Implementation

The skill is implemented in `scripts/test_runner.py` and provides:

### Parallel Test Execution
Uses Python's `concurrent.futures` to run checks simultaneously:
1. **pytest**: Unit and integration tests with coverage
2. **ruff**: Linting for code quality and style
3. **mypy**: Static type checking
4. **bandit**: Security vulnerability scanning

### Coverage Analysis
- Measures code coverage during test execution
- Enforces minimum threshold (default: 80%)
- Generates HTML coverage report in `htmlcov/`
- Identifies untested code paths

### Result Consolidation
- Combines all check results into single report
- Color-coded pass/fail status
- Execution time for each check
- Summary statistics

## Examples

### Example 1: Basic Test Run
```bash
$ python3 scripts/test_runner.py

🚀 Infiquetra Test Suite Runner
═════════════════════════════════════════

🔍 Detected configuration:
   Coverage threshold: 80%
   Test directory: tests/
   Source directory: src/

🏃 Running checks in parallel...

[1/4] pytest ................................. ✓ (12.3s)
[2/4] ruff .................................... ✓ (1.8s)
[3/4] mypy .................................... ✓ (4.2s)
[4/4] bandit .................................. ✓ (2.1s)

═════════════════════════════════════════
📊 Test Results Summary
═════════════════════════════════════════

✓ pytest     45/45 tests passed   Coverage: 82%
✓ ruff       0 issues found
✓ mypy       0 type errors
✓ bandit     0 security issues

═════════════════════════════════════════
✅ All checks passed! (20.4s total, 4.8s parallel)

📄 Reports generated:
   - HTML: htmlcov/index.html
   - Coverage: .coverage
```

### Example 2: Failed Tests with Details
```bash
$ python3 scripts/test_runner.py

🚀 Infiquetra Test Suite Runner
═════════════════════════════════════════

🏃 Running checks in parallel...

[1/4] pytest ................................. ✗ (8.3s)
[2/4] ruff .................................... ✓ (1.8s)
[3/4] mypy .................................... ✗ (4.2s)
[4/4] bandit .................................. ✓ (2.1s)

═════════════════════════════════════════
📊 Test Results Summary
═════════════════════════════════════════

✗ pytest     42/45 tests passed   Coverage: 76%
  Failed tests:
    - tests/unit/test_wallet.py::test_token_generation
    - tests/integration/test_api.py::test_auth_flow
    - tests/unit/test_validators.py::test_email_validation

✓ ruff       0 issues found

✗ mypy       3 type errors
  src/services/wallet.py:45: error: Incompatible return type
  src/utils/validators.py:23: error: Missing type annotation
  src/api/handlers.py:67: error: Argument has incompatible type

✓ bandit     0 security issues

═════════════════════════════════════════
❌ Some checks failed (16.4s total)

Coverage: 76% (below threshold of 80%)
```

### Example 3: CI/CD Integration
```bash
$ python3 scripts/test_runner.py --output json --output-file test-results.json

# test-results.json contains:
{
  "summary": {
    "total_checks": 4,
    "passed": 3,
    "failed": 1,
    "duration": 16.4,
    "timestamp": "2024-08-15T14:30:00Z"
  },
  "checks": {
    "pytest": {
      "status": "failed",
      "tests_run": 45,
      "tests_passed": 42,
      "tests_failed": 3,
      "coverage": 76.5,
      "duration": 8.3
    },
    "ruff": {
      "status": "passed",
      "issues": 0,
      "duration": 1.8
    },
    "mypy": {
      "status": "failed",
      "errors": 3,
      "duration": 4.2
    },
    "bandit": {
      "status": "passed",
      "issues": 0,
      "duration": 2.1
    }
  }
}
```

### Example 4: Pre-commit Hook Integration
```bash
# .git/hooks/pre-commit
#!/bin/bash
python3 scripts/test_runner.py --fail-fast --skip-slow

if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Commit aborted."
    exit 1
fi
```

## Integration with Infiquetra Workflows

### Local Development
```bash
# Quick check before committing
python3 scripts/test_runner.py --fail-fast

# Full validation before PR
python3 scripts/test_runner.py --coverage 85
```

### GitHub Actions
```yaml
# .github/workflows/test.yml
- name: Run Infiquetra Test Suite
  run: |
    python3 scripts/test_runner.py --output json --output-file test-results.json

- name: Upload Test Results
  uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: test-results.json

- name: Upload Coverage Report
  uses: actions/upload-artifact@v3
  with:
    name: coverage-report
    path: htmlcov/
```

### Pre-commit Configuration
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: test-suite
        name: Infiquetra Test Suite
        entry: python3 scripts/test_runner.py --fail-fast
        language: system
        pass_filenames: false
```

## Configuration

### pyproject.toml Integration
```toml
[tool.test-suite]
coverage_threshold = 80
test_directory = "tests"
source_directory = "src"
skip_slow = false
fail_fast = false

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "--cov=src --cov-report=html --cov-report=term"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.bandit]
exclude_dirs = ["tests", "venv", ".venv"]
```

## Error Handling

The test runner handles:
- **Missing dependencies**: Clear installation instructions
- **Configuration errors**: Validates pyproject.toml settings
- **Test failures**: Detailed error reports with file/line numbers
- **Coverage failures**: Shows which files need more tests
- **Timeout handling**: Kills hanging tests after 5 minutes

## Performance Optimization

### Speed Improvements
- **Parallel execution**: 4x faster than sequential
- **Smart caching**: Reuses pytest cache between runs
- **Selective execution**: Run only changed tests
- **Skip slow tests**: Development mode for rapid feedback

### Resource Management
- **CPU limits**: Uses available cores efficiently
- **Memory monitoring**: Prevents out-of-memory failures
- **Timeout protection**: Kills hanging processes

## Notes

- Test execution time varies by project size (3-15 minutes typical)
- Coverage reports are stored in `htmlcov/` directory
- Failed tests don't prevent other checks from running (unless `--fail-fast`)
- JSON output is compatible with CI/CD reporting tools
- Pre-commit hooks ensure code quality before commits

## Related Infiquetra Standards

- **Minimum Coverage**: 80% for all Infiquetra services
- **Required Checks**: pytest, ruff, mypy, bandit must pass
- **Type Annotations**: All public functions must have type hints
- **Security Scanning**: No high-severity bandit issues allowed
- **Pre-commit**: All Infiquetra repos should use pre-commit hooks

## Troubleshooting

### "pytest command not found"
```bash
uv pip install pytest pytest-cov
# or: pip install pytest pytest-cov
```

### "Coverage below threshold"
Run with verbose mode to see which files need tests:
```bash
python3 scripts/test_runner.py --verbose
# Then check htmlcov/index.html for detailed coverage
```

### "Tests hanging"
Use fail-fast mode and increase timeout:
```bash
python3 scripts/test_runner.py --fail-fast --timeout 300
```

### "mypy errors on third-party packages"
Add to pyproject.toml:
```toml
[tool.mypy]
ignore_missing_imports = true
```

## Related Resources

- [Infiquetra Testing Standards](https://github.com/infiquetra/infiquetra-claude-plugins/docs)
- [pytest Documentation](https://docs.pytest.org/)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [bandit Documentation](https://bandit.readthedocs.io/)
