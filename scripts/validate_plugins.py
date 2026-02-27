#!/usr/bin/env python3
"""
Validate Infiquetra Claude Code Plugin Formats

Checks that all plugin markdown files follow proper format and
that referenced scripts exist and are executable.
"""

import sys
from pathlib import Path

# Color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
RESET = "\033[0m"


def validate_plugin_file(plugin_path: Path, scripts_dir: Path) -> tuple[bool, list[str]]:
    """
    Validate a single plugin markdown file.

    Returns:
        (is_valid, errors) tuple
    """
    errors = []

    if not plugin_path.exists():
        errors.append(f"File does not exist: {plugin_path}")
        return False, errors

    content = plugin_path.read_text()

    # Check required sections
    required_sections = ["# ", "## Overview", "## Usage", "## Prerequisites", "## Examples"]

    for section in required_sections:
        if section not in content:
            errors.append(f"Missing required section: {section}")

    # Check for script references
    if "scripts/" in content:
        # Extract script references
        for line in content.split("\n"):
            if "scripts/" in line and (".py" in line or ".sh" in line):
                # Try to extract script path
                for word in line.split():
                    if "scripts/" in word and (".py" in word or ".sh" in word):
                        script_path = word.split()[0].strip("`").strip("'").strip('"')
                        full_script_path = scripts_dir / Path(script_path).name

                        if not full_script_path.exists():
                            errors.append(f"Referenced script not found: {script_path}")
                        elif not full_script_path.stat().st_mode & 0o111:
                            errors.append(f"Script not executable: {script_path}")

    # Check for code blocks
    if "```bash" not in content and "```python" not in content:
        errors.append("No code examples found (missing ```bash or ```python blocks)")

    return len(errors) == 0, errors


def main():
    """Main entry point."""
    print(f"\n{BOLD}🔍 Infiquetra Plugin Validator{RESET}")
    print(f"{'═' * 45}\n")

    # Get paths
    repo_root = Path(__file__).parent.parent
    plugins_dir = repo_root / "plugins"
    scripts_dir = repo_root / "scripts"

    if not plugins_dir.exists():
        print(f"{RED}❌ plugins/ directory not found{RESET}")
        sys.exit(1)

    # Find all plugin files
    plugin_files = list(plugins_dir.glob("*.md"))

    if not plugin_files:
        print(f"{YELLOW}⚠️  No plugin files found in {plugins_dir}{RESET}")
        sys.exit(0)

    print(f"{BLUE}Found {len(plugin_files)} plugin files to validate{RESET}\n")

    # Validate each plugin
    all_valid = True
    for plugin_file in plugin_files:
        print(f"Validating {plugin_file.name}...", end=" ")

        is_valid, errors = validate_plugin_file(plugin_file, scripts_dir)

        if is_valid:
            print(f"{GREEN}✓{RESET}")
        else:
            print(f"{RED}✗{RESET}")
            all_valid = False

            for error in errors:
                print(f"  {RED}• {error}{RESET}")

    # Summary
    print(f"\n{'═' * 45}")
    if all_valid:
        print(f"{GREEN}✅ All plugins validated successfully!{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}❌ Some plugins have validation errors{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
