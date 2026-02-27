#!/usr/bin/env python3
"""
Infiquetra Plugin Marketplace Validator

Validates plugin manifests and marketplace registry against schemas.
Ensures all plugins meet quality and structure requirements.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_success(message: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}✗{Colors.RESET} {message}")


def print_warning(message: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {message}")


def print_info(message: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {message}")


class PluginValidator:
    """Validates Claude Code plugins and marketplace registry."""

    def __init__(self, repo_root: Path):
        """Initialize validator with repository root path."""
        self.repo_root = repo_root
        self.plugins_dir = repo_root / "plugins"
        self.marketplace_file = repo_root / ".claude-plugin" / "marketplace.json"
        self.schema_file = repo_root / "marketplace" / "validator" / "schema.json"
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all plugins and marketplace registry.

        Returns:
            Tuple of (success, errors, warnings)
        """
        print(f"\n{Colors.BOLD}🔍 Validating Infiquetra Plugin Marketplace{Colors.RESET}\n")

        # Validate marketplace registry
        print("Validating marketplace registry...")
        marketplace_valid, marketplace_errors = self.validate_marketplace_registry()

        if marketplace_valid:
            print_success("Marketplace registry is valid")
        else:
            for error in marketplace_errors:
                print_error(error)
            self.errors.extend(marketplace_errors)

        # Validate each plugin
        print("\nValidating individual plugins...")
        plugin_dirs = [d for d in self.plugins_dir.iterdir() if d.is_dir() and d.name != "example-plugin"]

        for plugin_dir in sorted(plugin_dirs):
            plugin_name = plugin_dir.name
            print(f"\n  Validating {plugin_name}...")

            plugin_valid, plugin_errors, plugin_warnings = self.validate_plugin(plugin_dir)

            if plugin_valid:
                print_success(f"  {plugin_name} is valid")
            else:
                for error in plugin_errors:
                    print_error(f"    {error}")
                self.errors.extend([f"{plugin_name}: {e}" for e in plugin_errors])

            for warning in plugin_warnings:
                print_warning(f"    {warning}")
                self.warnings.append(f"{plugin_name}: {warning}")

        # Summary
        print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Plugins validated: {len(plugin_dirs)}")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Warnings: {len(self.warnings)}")

        success = len(self.errors) == 0
        if success:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All validations passed!{Colors.RESET}\n")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ Validation failed with {len(self.errors)} errors{Colors.RESET}\n")

        return success, self.errors, self.warnings

    def validate_marketplace_registry(self) -> Tuple[bool, List[str]]:
        """Validate the marketplace.json registry file."""
        errors = []

        if not self.marketplace_file.exists():
            errors.append("marketplace.json not found")
            return False, errors

        try:
            with open(self.marketplace_file) as f:
                marketplace = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in marketplace.json: {e}")
            return False, errors

        # Validate structure
        required_fields = ["version", "name", "plugins"]
        for field in required_fields:
            if field not in marketplace:
                errors.append(f"Missing required field: {field}")

        # Validate each plugin entry
        for i, plugin in enumerate(marketplace.get("plugins", [])):
            plugin_errors = self._validate_marketplace_entry(plugin, i)
            errors.extend(plugin_errors)

        return len(errors) == 0, errors

    def validate_plugin(self, plugin_dir: Path) -> Tuple[bool, List[str], List[str]]:
        """
        Validate an individual plugin.

        Returns:
            Tuple of (success, errors, warnings)
        """
        errors = []
        warnings = []

        # Check required files
        required_files = {
            plugin_dir / ".claude-plugin" / "plugin.json": "Plugin manifest",
            plugin_dir / "README.md": "Plugin documentation",
            plugin_dir / "CHANGELOG.md": "Change log",
        }

        for file_path, description in required_files.items():
            if not file_path.exists():
                errors.append(f"Missing required file: {description} ({file_path.name})")

        # Check recommended directories
        recommended_dirs = {
            plugin_dir / "src": "Source directory",
            plugin_dir / "tests": "Tests directory",
        }

        for dir_path, description in recommended_dirs.items():
            if not dir_path.exists():
                warnings.append(f"Missing recommended directory: {description}")

        # Validate plugin.json
        manifest_file = plugin_dir / ".claude-plugin" / "plugin.json"
        if manifest_file.exists():
            manifest_errors, manifest_warnings = self._validate_manifest(manifest_file, plugin_dir)
            errors.extend(manifest_errors)
            warnings.extend(manifest_warnings)

        return len(errors) == 0, errors, warnings

    def _validate_manifest(self, manifest_file: Path, plugin_dir: Path) -> Tuple[List[str], List[str]]:
        """Validate plugin.json against schema."""
        errors = []
        warnings = []

        try:
            with open(manifest_file) as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"], []

        # Load schema
        try:
            with open(self.schema_file) as f:
                schema = json.load(f)
        except Exception as e:
            warnings.append(f"Could not load schema: {e}")
            schema = None

        # Validate against schema using jsonschema if available
        if schema:
            try:
                import jsonschema
                jsonschema.validate(manifest, schema)
            except ImportError:
                warnings.append("jsonschema not installed, skipping schema validation")
            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")

        # Validate required fields manually
        required_fields = ["id", "version", "name", "description", "author"]
        for field in required_fields:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")

        # Validate main script exists
        if "main" in manifest:
            main_script = plugin_dir / manifest["main"]
            if not main_script.exists():
                errors.append(f"Main script not found: {manifest['main']}")

        # Validate version format
        if "version" in manifest:
            version = manifest["version"]
            if not self._is_valid_semver(version):
                errors.append(f"Invalid version format: {version} (expected semver like 1.0.0)")

        # Validate id format
        if "id" in manifest:
            plugin_id = manifest["id"]
            if not self._is_valid_plugin_id(plugin_id):
                errors.append(f"Invalid plugin ID: {plugin_id} (expected kebab-case)")

        # Check for recommended fields
        recommended_fields = ["license", "homepage", "keywords", "engines"]
        for field in recommended_fields:
            if field not in manifest:
                warnings.append(f"Missing recommended field: {field}")

        return errors, warnings

    def _validate_marketplace_entry(self, entry: Dict, index: int) -> List[str]:
        """Validate a marketplace plugin entry."""
        errors = []
        required = ["id", "name", "version", "source"]

        for field in required:
            if field not in entry:
                errors.append(f"Plugin entry {index}: missing {field}")

        # Validate source
        if "source" in entry:
            source = entry["source"]
            if "type" not in source:
                errors.append(f"Plugin {entry.get('id', 'unknown')}: source missing type")
            elif source["type"] == "local":
                if "path" not in source:
                    errors.append(f"Plugin {entry['id']}: local source missing path")
                else:
                    plugin_path = self.repo_root / source["path"]
                    if not plugin_path.exists():
                        errors.append(f"Plugin {entry['id']}: path not found: {source['path']}")

        return errors

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if version follows semantic versioning."""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))

    @staticmethod
    def _is_valid_plugin_id(plugin_id: str) -> bool:
        """Check if plugin ID is in kebab-case."""
        import re
        pattern = r"^[a-z0-9-]+$"
        return bool(re.match(pattern, plugin_id)) and not plugin_id.startswith("-") and not plugin_id.endswith("-")


def main():
    """Main entry point for validation script."""
    parser = argparse.ArgumentParser(description="Validate Infiquetra Plugin Marketplace")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--plugins",
        type=str,
        help="Comma-separated list of plugin names to validate (default: all)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    args = parser.parse_args()

    validator = PluginValidator(args.repo_root)
    success, errors, warnings = validator.validate_all()

    if args.strict and warnings:
        print(f"\n{Colors.RED}Strict mode: treating warnings as errors{Colors.RESET}")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
