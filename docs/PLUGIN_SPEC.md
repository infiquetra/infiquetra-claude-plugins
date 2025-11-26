# Plugin Development Specification

Guide for creating new plugins for the Infiquetra Claude Plugins marketplace.

## Plugin Structure

Every plugin must follow this directory structure:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json        # Plugin manifest (required)
├── src/
│   └── main_script.py     # Main implementation (required)
├── tests/
│   └── test_main.py       # Tests (recommended)
├── README.md              # Documentation (required)
└── CHANGELOG.md           # Version history (required)
```

## Plugin Manifest (plugin.json)

Every plugin must include a `plugin.json` file in the `.claude-plugin/` directory:

```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Brief description of what the plugin does",
  "author": {
    "name": "Author Name",
    "email": "author@example.com",
    "url": "https://github.com/author"
  },
  "homepage": "https://github.com/infiquetra/infiquetra-claude-plugins",
  "repository": "https://github.com/infiquetra/infiquetra-claude-plugins.git",
  "license": "MIT",
  "keywords": [
    "keyword1",
    "keyword2"
  ]
}
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Plugin name (kebab-case) |
| `version` | Semantic version (e.g., 1.0.0) |
| `description` | Brief description (< 200 chars) |
| `author` | Author information |
| `license` | License type |
| `keywords` | Search keywords (array) |

## Naming Conventions

- **Plugin name**: `kebab-case` (e.g., `parallel-test-runner`)
- **Python files**: `snake_case` (e.g., `test_runner.py`)
- **Classes**: `PascalCase` (e.g., `TestRunner`)
- **Functions**: `snake_case` (e.g., `run_tests`)

## Code Standards

### Python Version
- Python 3.12+ required
- Use modern Python features (type hints, dataclasses, etc.)

### Type Hints
- All functions must have type hints
- Use `from typing import` for complex types

### Error Handling
- Handle exceptions gracefully
- Provide meaningful error messages
- Use appropriate exit codes

### Output
- Use color codes for terminal output
- Support both console and JSON output formats
- Include `--verbose` flag for detailed output

## Example Plugin Template

```python
#!/usr/bin/env python3
"""
Plugin Name

Brief description of the plugin.
"""

import argparse
import sys
from typing import Any

# Color codes
RED = "\\033[0;31m"
GREEN = "\\033[0;32m"
BLUE = "\\033[0;34m"
BOLD = "\\033[1m"
RESET = "\\033[0m"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Plugin description")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print(f"{BOLD}Plugin Name{RESET}")
    print("=" * 45)

    # Plugin logic here

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Testing Requirements

- Minimum 80% test coverage
- Use pytest as the test framework
- Include both unit and integration tests

### Test Structure

```python
import pytest
from src.main_script import PluginClass


class TestPluginClass:
    def test_basic_functionality(self):
        """Test basic plugin functionality."""
        plugin = PluginClass()
        result = plugin.run()
        assert result.status == "success"

    def test_error_handling(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            plugin = PluginClass(invalid_arg=True)
```

## Documentation Requirements

### README.md

Every plugin must include a README with:

1. **Title and Description**: What the plugin does
2. **Features**: Key capabilities
3. **Installation**: How to install
4. **Usage**: Command examples
5. **Options**: Available flags and arguments
6. **Examples**: Output examples
7. **Requirements**: Dependencies
8. **License**: License information

### CHANGELOG.md

Track version changes:

```markdown
# Changelog

## [1.0.0] - 2025-01-15

### Added
- Initial release
- Feature 1
- Feature 2
```

## Registering a Plugin

After creating your plugin:

1. Add entry to `/.claude-plugin/marketplace.json`
2. Submit PR for review
3. Plugin will be available after merge

### Marketplace Entry

```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Plugin description",
  "author": {
    "name": "Author",
    "email": "author@example.com"
  },
  "source": "./plugins/plugin-name",
  "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"],
  "category": "development"
}
```

### Categories

- `development`: Development tools (testing, linting, formatting)
- `documentation`: Documentation generation
- `infrastructure`: Deployment, CI/CD, cloud
- `utilities`: General-purpose utilities

## Best Practices

1. **Single Responsibility**: Each plugin should do one thing well
2. **Minimal Dependencies**: Only include necessary dependencies
3. **Cross-Platform**: Support macOS, Linux, Windows where possible
4. **Idempotent**: Running multiple times should be safe
5. **Configurable**: Support configuration via flags and env vars
6. **Well-Documented**: Clear usage examples and error messages
