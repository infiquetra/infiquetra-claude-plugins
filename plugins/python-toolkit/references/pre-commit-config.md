# Pre-commit Configuration

Complete pre-commit hooks setup for Infiquetra Python projects to enforce code quality standards before commits.

## Installation

```bash
# Install pre-commit
pip install pre-commit

# Or with uv
uv pip install pre-commit

# Install the git hooks
pre-commit install
```

## Complete Configuration

Create `.pre-commit-config.yaml` in your project root:

```yaml
# .pre-commit-config.yaml

# See https://pre-commit.com for more information
default_language_version:
  python: python3.12

repos:
  # ============================================================================
  # Ruff - Fast Python linter and formatter
  # ============================================================================
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      # Run the linter
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
        types_or: [python, pyi]

      # Run the formatter
      - id: ruff-format
        types_or: [python, pyi]

  # ============================================================================
  # mypy - Static type checker
  # ============================================================================
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--strict, --show-error-codes]
        additional_dependencies:
          - boto3-stubs[essential]
          - types-requests
          - types-pyyaml
        exclude: ^(tests/|scripts/)

  # ============================================================================
  # bandit - Security linter
  # ============================================================================
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: [-c, pyproject.toml, -r, src/]
        additional_dependencies: ["bandit[toml]"]

  # ============================================================================
  # General file quality checks
  # ============================================================================
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
        exclude: ^(.*\.md|.*\.txt)$
      - id: end-of-file-fixer
      - id: check-yaml
        args: [--safe]
      - id: check-json
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: mixed-line-ending
        args: [--fix=lf]
      - id: detect-private-key
      - id: debug-statements

  # ============================================================================
  # Additional security checks
  # ============================================================================
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]
        exclude: (poetry\.lock|package-lock\.json)
```

## Minimal Configuration

For quick setup with essential checks only:

```yaml
# .pre-commit-config.yaml (minimal)

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

## Usage

### Initial Setup
```bash
# Install pre-commit hooks in your repository
pre-commit install

# Test configuration
pre-commit run --all-files
```

### Running Hooks
```bash
# Hooks run automatically on git commit
git commit -m "Your commit message"

# Run manually on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
pre-commit run mypy --all-files

# Skip hooks (use sparingly)
git commit --no-verify -m "Emergency fix"
```

### Updating Hooks
```bash
# Update all hooks to latest versions
pre-commit autoupdate

# Update specific hook
pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit
```

## Hook Configuration Details

### Ruff Hook

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.2.0
  hooks:
    - id: ruff
      args:
        - --fix              # Auto-fix issues where possible
        - --exit-non-zero-on-fix  # Fail if fixes were made
      types_or: [python, pyi]
```

**Common args**:
- `--fix`: Automatically fix violations
- `--show-fixes`: Show applied fixes
- `--select E,F,I`: Only run specific rule categories
- `--ignore E501`: Ignore specific rules

### mypy Hook

```yaml
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.8.0
  hooks:
    - id: mypy
      args: [--strict, --show-error-codes]
      additional_dependencies:
        - boto3-stubs[essential]  # AWS SDK type stubs
        - types-requests          # requests type stubs
        - types-pyyaml           # pyyaml type stubs
      exclude: ^(tests/|scripts/)  # Skip type checking for tests
```

**Common args**:
- `--strict`: Enable all strict checks
- `--show-error-codes`: Show error codes in output
- `--ignore-missing-imports`: Ignore missing type stubs
- `--no-incremental`: Disable incremental mode

### bandit Hook

```yaml
- repo: https://github.com/PyCQA/bandit
  rev: 1.7.6
  hooks:
    - id: bandit
      args:
        - -c                # Config file
        - pyproject.toml    # Read config from pyproject.toml
        - -r                # Recursive
        - src/              # Only scan source code
      additional_dependencies: ["bandit[toml]"]
```

**Common args**:
- `-ll`: Only show low confidence and above
- `-lll`: Only show high confidence issues
- `--skip B101,B601`: Skip specific tests
- `-f json`: Output in JSON format

## Local vs Remote Hooks

### Local Hooks (Faster)

For custom scripts that don't need external repositories:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-fast
        name: Run fast tests
        entry: pytest -m "not slow"
        language: system
        pass_filenames: false
        always_run: true

      - id: check-coverage
        name: Check test coverage
        entry: coverage report --fail-under=80
        language: system
        pass_filenames: false
```

### Remote Hooks (Versioned)

Prefer remote hooks for standard tools to ensure version consistency across team.

## Selective Hook Execution

### By File Type

```yaml
- id: mypy
  types: [python]           # Only .py files
  types_or: [python, pyi]   # .py or .pyi files
  exclude: ^tests/          # Exclude directory
```

### By Stage

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-yaml
        stages: [commit, push]  # Run on commit and push

      - id: check-json
        stages: [manual]        # Only run manually
```

Run specific stage:
```bash
pre-commit run --hook-stage push
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Pre-commit

on: [push, pull_request]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: pre-commit/action@v3.0.0
```

### With Caching

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"

- uses: actions/cache@v3
  with:
    path: ~/.cache/pre-commit
    key: pre-commit-${{ hashFiles('.pre-commit-config.yaml') }}

- uses: pre-commit/action@v3.0.0
```

## Troubleshooting

### "command not found: ruff"

Install hooks in virtual environment:
```bash
source .venv/bin/activate
pip install pre-commit
pre-commit install
```

### Hooks are slow

Enable caching for mypy:
```yaml
- id: mypy
  args: [--cache-dir=/tmp/mypy_cache]
```

Or run only on changed files (default behavior).

### mypy can't find imports

Add to `.pre-commit-config.yaml`:
```yaml
- id: mypy
  additional_dependencies:
    - boto3-stubs
    - types-requests
    - your-package-name  # Your own package
```

### Skip specific files

```yaml
- id: mypy
  exclude: ^(tests/|migrations/|scripts/)
```

### Detect secrets baseline

Create baseline to ignore existing secrets:
```bash
detect-secrets scan > .secrets.baseline
```

## Infiquetra Standards

Required hooks for all Infiquetra projects:
- ✅ **ruff** (linter + formatter)
- ✅ **mypy** (type checking)
- ✅ **bandit** (security scanning)
- ✅ **trailing-whitespace** (file quality)
- ✅ **end-of-file-fixer** (file quality)
- ✅ **detect-private-key** (security)

Optional but recommended:
- **pytest** (run fast tests)
- **detect-secrets** (secret scanning)
- **check-yaml/json/toml** (config validation)

## Examples

### Full Infiquetra Service Setup

```bash
# 1. Create .pre-commit-config.yaml (use complete config above)
# 2. Install pre-commit
pip install pre-commit

# 3. Install hooks
pre-commit install

# 4. Test on all files
pre-commit run --all-files

# 5. Make a commit (hooks run automatically)
git add .
git commit -m "feat: add new feature"
```

### Update Hook Versions

```bash
# Update to latest versions
pre-commit autoupdate

# Review changes
git diff .pre-commit-config.yaml

# Test updated hooks
pre-commit run --all-files

# Commit updated config
git add .pre-commit-config.yaml
git commit -m "chore: update pre-commit hooks"
```

## Related References

- [pyproject-template.md](./pyproject-template.md) - Tool configurations
- [testing-patterns.md](./testing-patterns.md) - Testing strategies
- [Pre-commit Documentation](https://pre-commit.com/)
