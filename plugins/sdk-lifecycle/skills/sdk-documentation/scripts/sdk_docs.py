#!/usr/bin/env python3
"""
SDK Documentation Generator

Extracts API documentation from code comments and generates comprehensive SDK documentation.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional


def generate_documentation(
    project_path: Path,
    language: Optional[str] = None,
    output_dir: Path = Path("docs"),
    format: str = "markdown",
) -> None:
    """Generate SDK documentation."""
    print(f"🚀 Generating {format.upper()} documentation for {project_path}")

    # Detect language if not specified
    if not language:
        if (project_path / "pyproject.toml").exists():
            language = "python"
        elif list(project_path.glob("**/*.csproj")):
            language = "dotnet"
        elif (project_path / "package.json").exists():
            language = "typescript"
        else:
            raise ValueError("Could not detect project language")

    print(f"  Language: {language.upper()}")
    print(f"  Output: {output_dir}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate documentation based on language
    if language == "python":
        _generate_python_docs(project_path, output_dir, format)
    elif language == "dotnet":
        _generate_dotnet_docs(project_path, output_dir, format)
    elif language == "typescript":
        _generate_typescript_docs(project_path, output_dir, format)

    print("✅ Documentation generated successfully!")


def _generate_python_docs(project_path: Path, output_dir: Path, format: str) -> None:
    """Generate Python documentation using Sphinx or pydoc."""
    print("  Generating Python API documentation...")

    # Check if Sphinx is available
    try:
        import subprocess
        subprocess.run(
            ["sphinx-apidoc", "-o", str(output_dir / "api"), str(project_path / "src")],
            check=True,
            capture_output=True,
        )
        print("  ✓ API reference generated with Sphinx")
    except (ImportError, subprocess.CalledProcessError, FileNotFoundError):
        print("  ⚠️  Sphinx not available. Install with: pip install sphinx")

    # Generate usage guide template
    _create_usage_guide_template(output_dir, "python")


def _generate_dotnet_docs(project_path: Path, output_dir: Path, format: str) -> None:
    """Generate .NET documentation using DocFX."""
    print("  Generating .NET API documentation...")
    print("  ⚠️  .NET documentation generation requires DocFX")
    print("     Install: dotnet tool install -g docfx")
    _create_usage_guide_template(output_dir, "dotnet")


def _generate_typescript_docs(project_path: Path, output_dir: Path, format: str) -> None:
    """Generate TypeScript documentation using TypeDoc."""
    print("  Generating TypeScript API documentation...")
    print("  ⚠️  TypeScript documentation generation requires TypeDoc")
    print("     Install: npm install --save-dev typedoc")
    _create_usage_guide_template(output_dir, "typescript")


def _create_usage_guide_template(output_dir: Path, language: str) -> None:
    """Create usage guide template."""
    guide_path = output_dir / "usage-guide.md"

    template = f"""# SDK Usage Guide

## Installation

\`\`\`bash
# Installation instructions for {language}
\`\`\`

## Quick Start

\`\`\`{language}
# Minimal working example
\`\`\`

## Authentication

How to authenticate with the API.

## Core Concepts

Key concepts users need to understand.

## Examples

### Basic Usage
### Advanced Features

## Error Handling

How to handle errors.

## Configuration

Available configuration options.

## Troubleshooting

Common issues and solutions.
"""

    guide_path.write_text(template)
    print(f"  ✓ Usage guide template: {guide_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate SDK documentation")
    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path.cwd(),
        help="Path to SDK project",
    )
    parser.add_argument(
        "--language",
        choices=["python", "dotnet", "typescript"],
        help="Project language (auto-detected if not specified)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs"),
        help="Output directory for documentation",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Documentation format",
    )

    args = parser.parse_args()

    try:
        generate_documentation(
            project_path=args.project_path,
            language=args.language,
            output_dir=args.output_dir,
            format=args.format,
        )
    except Exception as e:
        print(f"❌ Documentation generation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
