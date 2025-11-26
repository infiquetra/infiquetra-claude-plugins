# Claude Configuration for Infiquetra Claude Plugins

## Repository Information

- **Repository**: infiquetra-claude-plugins
- **Purpose**: Claude Code plugins for Infiquetra development workflows
- **Organization**: Infiquetra

## Plugin Development Guidelines

### Plugin Structure
Each plugin should follow this structure:
```
plugin-name/
├── .claude-plugin/
│   └── plugin.json        # Plugin manifest
├── src/
│   └── main_script.py     # Main implementation
├── tests/
│   └── test_main.py       # Tests
├── README.md              # Usage documentation
└── CHANGELOG.md           # Version history
```

### Naming Conventions
- Plugin directories: `kebab-case` (e.g., `parallel-test-runner`)
- Python files: `snake_case` (e.g., `test_runner.py`)
- Classes: `PascalCase` (e.g., `QualityCheckRunner`)

### Code Quality Standards
- Python 3.12+ required
- Type hints enforced with mypy
- Ruff linting with 100-character line limit
- Minimum 80% test coverage
- Security scanning with bandit

### Testing Requirements
- Unit tests for all core functionality
- Integration tests where applicable
- Use pytest as the test framework

## Development Workflow

1. Create plugin in `plugins/` directory
2. Add implementation in `src/`
3. Write tests in `tests/`
4. Document usage in README.md
5. Add to marketplace.json
6. Submit PR for review

## Running Quality Checks

```bash
# Run all checks
pytest

# Run specific plugin tests
pytest plugins/parallel-test-runner/tests/

# Run linting
ruff check .

# Run type checking
mypy plugins/
```
