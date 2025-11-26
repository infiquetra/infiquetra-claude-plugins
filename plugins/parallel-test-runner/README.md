# Parallel Test Runner

Run pytest, ruff, mypy, and bandit in parallel for 4x faster quality checks.

## Features

- **Parallel Execution**: Run all quality checks simultaneously
- **Coverage Enforcement**: Configurable coverage threshold (default: 80%)
- **Consolidated Output**: Clear summary of all results
- **CI/CD Integration**: JSON output for pipeline integration
- **Fail-Fast Mode**: Stop on first failure
- **Configurable Timeout**: Per-check timeout settings

## Installation

This plugin is part of the infiquetra-claude-plugins collection.

```bash
# Clone the plugins repository
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git ~/.claude/plugins/infiquetra
```

## Usage

### Basic Usage
```bash
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py
```

### With Options
```bash
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py \
    --coverage 80 \
    --source-dir src \
    --test-dir tests \
    --verbose
```

### JSON Output for CI/CD
```bash
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py \
    --output json \
    --output-file results.json
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--coverage` | 80 | Minimum coverage threshold (%) |
| `--test-dir` | tests | Test directory |
| `--source-dir` | src | Source directory |
| `--fail-fast` | false | Stop on first failure |
| `--verbose`, `-v` | false | Verbose output |
| `--timeout` | 300 | Timeout per check (seconds) |
| `--output` | console | Output format: console or json |
| `--output-file` | - | Output file for JSON format |

## Quality Checks

| Check | Tool | Purpose |
|-------|------|---------|
| Tests | pytest | Run unit and integration tests |
| Coverage | pytest-cov | Measure code coverage |
| Linting | ruff | Code style and errors |
| Types | mypy | Static type checking |
| Security | bandit | Security vulnerability scanning |

## Example Output

```
Parallel Test Runner
═════════════════════════════════════════════

Configuration:
   Coverage threshold: 80%
   Test directory: tests/
   Source directory: src/

Running checks in parallel...

[1/4] pytest               ✓ (12.3s)
[2/4] ruff                 ✓ (0.5s)
[3/4] mypy                 ✓ (2.1s)
[4/4] bandit               ✓ (1.2s)

═════════════════════════════════════════════
Test Results Summary
═════════════════════════════════════════════

✓ pytest       45/45 tests passed   Coverage: 87%
✓ ruff         0 issues found
✓ mypy         0 type errors
✓ bandit       0 security issues

═════════════════════════════════════════════
All checks passed! (16.1s total)

Reports generated:
   - HTML: htmlcov/index.html
   - Coverage: .coverage
```

## Requirements

- Python 3.12+
- pytest
- pytest-cov
- ruff
- mypy
- bandit

## License

MIT
