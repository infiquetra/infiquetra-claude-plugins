#!/usr/bin/env bash
#
# create-plugin.sh - Create a new VECU Claude plugin from template
#
# Usage: ./tools/create-plugin.sh <plugin-id> <plugin-name>
# Example: ./tools/create-plugin.sh api-tester "VECU API Tester"

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

# Helper functions
print_success() {
    echo -e "${GREEN}✓${RESET} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${RESET} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${RESET} $1"
}

print_error() {
    echo -e "${RED}✗${RESET} $1"
}

print_header() {
    echo -e "\n${BOLD}$1${RESET}\n"
}

# Validate arguments
if [ $# -lt 2 ]; then
    print_error "Usage: $0 <plugin-id> <plugin-name>"
    echo ""
    echo "Examples:"
    echo "  $0 api-tester \"VECU API Tester\""
    echo "  $0 log-analyzer \"VECU Log Analyzer\""
    exit 1
fi

PLUGIN_ID="$1"
PLUGIN_NAME="$2"
PLUGIN_DIR="plugins/$PLUGIN_ID"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Validate plugin ID format (kebab-case)
if ! [[ "$PLUGIN_ID" =~ ^[a-z0-9-]+$ ]]; then
    print_error "Plugin ID must be in kebab-case (lowercase letters, numbers, and hyphens only)"
    echo "  Valid: api-tester, log-analyzer"
    echo "  Invalid: VecuApiTester, vecu_api_tester"
    exit 1
fi

# Check if plugin already exists
if [ -d "$REPO_ROOT/$PLUGIN_DIR" ]; then
    print_error "Plugin directory already exists: $PLUGIN_DIR"
    exit 1
fi

print_header "🚀 Creating new VECU Claude plugin: $PLUGIN_NAME"

# Create directory structure
print_info "Creating directory structure..."
cd "$REPO_ROOT"
mkdir -p "$PLUGIN_DIR"/{.claude-plugin,src,tests,docs}
print_success "Created plugin directories"

# Generate plugin.json manifest
print_info "Generating plugin manifest..."
cat > "$PLUGIN_DIR/.claude-plugin/plugin.json" <<EOF
{
  "id": "$PLUGIN_ID",
  "version": "0.1.0",
  "name": "$PLUGIN_NAME",
  "description": "Description for $PLUGIN_NAME - update this!",
  "author": {
    "name": "VECU Team",
    "email": "hello@infiquetra.com",
    "organization": "your organization"
  },
  "license": "MIT",
  "homepage": "https://github.com/infiquetra/infiquetra-claude-plugins",
  "repository": {
    "type": "git",
    "url": "https://github.com/infiquetra/infiquetra-claude-plugins.git"
  },
  "bugs": {
    "url": "https://github.com/infiquetra/infiquetra-claude-plugins/issues"
  },
  "engines": {
    "claude": ">=1.0.0",
    "python": ">=3.12"
  },
  "main": "src/main.py",
  "scripts": {
    "run": "python3 src/main.py"
  },
  "dependencies": {},
  "devDependencies": {
    "pytest": ">=8.0.0",
    "ruff": ">=0.2.0",
    "mypy": ">=1.8.0"
  },
  "keywords": [
    "vecu"
  ],
  "config": {},
  "permissions": [],
  "category": "development"
}
EOF
print_success "Created plugin.json"

# Generate main script
print_info "Generating main script..."
cat > "$PLUGIN_DIR/src/main.py" <<'EOF'
#!/usr/bin/env python3
"""
Main script for VECU Claude plugin.

This is a template - customize it for your plugin's functionality.
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main entry point for the plugin."""
    parser = argparse.ArgumentParser(
        description="VECU Claude Plugin"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    print("Hello from your VECU plugin!")
    print("Implement your plugin logic here.")

    if args.verbose:
        print("Verbose mode enabled")

    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x "$PLUGIN_DIR/src/main.py"
print_success "Created src/main.py"

# Generate README
print_info "Generating README..."
cat > "$PLUGIN_DIR/README.md" <<EOF
# $PLUGIN_NAME

## Overview

Brief description of what this plugin does and why it's useful.

**Key Features:**
- Feature 1
- Feature 2
- Feature 3

## Usage

\`\`\`bash
# Basic usage
python3 src/main.py

# With options
python3 src/main.py --verbose
\`\`\`

## Prerequisites

### Required Environment Variables
- \`EXAMPLE_VAR\` - Description of required variable

### Required Tools
- Python 3.12+
- List other required tools

### Required Permissions
- Describe what permissions are needed

## Examples

### Example 1: Basic Usage
\`\`\`bash
$ python3 src/main.py
Hello from your VECU plugin!
\`\`\`

## Configuration

Describe any configuration options or environment variables.

## Integration with VECU Workflows

Describe how this plugin integrates with VECU development workflows.

## Troubleshooting

### Common Issue 1
- Solution or workaround

### Common Issue 2
- Solution or workaround

## Notes

- Important note 1
- Important note 2

## Related Resources

- [Link to related documentation]
- [Link to API reference]
EOF
print_success "Created README.md"

# Generate CHANGELOG
print_info "Generating CHANGELOG..."
cat > "$PLUGIN_DIR/CHANGELOG.md" <<EOF
# Changelog

All notable changes to the $PLUGIN_NAME plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial plugin structure
- Basic functionality template

## [0.1.0] - $(date +%Y-%m-%d)

### Added
- Initial development release
- Plugin scaffolding and structure
EOF
print_success "Created CHANGELOG.md"

# Generate test file
print_info "Generating test template..."
cat > "$PLUGIN_DIR/tests/test_main.py" <<'EOF'
"""
Tests for the main plugin functionality.
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import your main module
# from main import main


def test_example():
    """Example test - replace with actual tests."""
    assert True


def test_plugin_structure():
    """Verify plugin structure is correct."""
    plugin_dir = Path(__file__).parent.parent

    # Check required files exist
    assert (plugin_dir / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_dir / "README.md").exists()
    assert (plugin_dir / "CHANGELOG.md").exists()
    assert (plugin_dir / "src" / "main.py").exists()
EOF
print_success "Created tests/test_main.py"

# Generate requirements.txt
print_info "Generating requirements.txt..."
cat > "$PLUGIN_DIR/requirements.txt" <<EOF
# Production dependencies
# Add your dependencies here

# Example:
# requests>=2.31.0
# pyyaml>=6.0.1
EOF
print_success "Created requirements.txt"

# Generate requirements-dev.txt
cat > "$PLUGIN_DIR/requirements-dev.txt" <<EOF
# Development dependencies
pytest>=8.0.0
pytest-cov>=4.1.0
ruff>=0.2.0
mypy>=1.8.0
bandit>=1.7.5
EOF
print_success "Created requirements-dev.txt"

# Success summary
print_header "✅ Plugin created successfully!"

echo "Plugin directory: $PLUGIN_DIR"
echo ""
echo "Next steps:"
echo "  1. Update plugin.json with your plugin details:"
echo "     - description: Add a meaningful description"
echo "     - keywords: Add relevant search keywords"
echo "     - dependencies: List required packages"
echo "     - permissions: Specify required permissions"
echo ""
echo "  2. Implement your plugin logic in src/main.py"
echo ""
echo "  3. Add tests in tests/"
echo ""
echo "  4. Update README.md with usage examples and documentation"
echo ""
echo "  5. Test your plugin:"
echo "     cd $PLUGIN_DIR"
echo "     python3 src/main.py"
echo "     pytest tests/ -v"
echo ""
echo "  6. Validate your plugin:"
echo "     python3 marketplace/validator/validate.py"
echo ""
echo "  7. Update marketplace registry:"
echo "     Add your plugin entry to .claude-plugin/marketplace.json"
echo ""

print_warning "Remember to update the description in plugin.json!"
