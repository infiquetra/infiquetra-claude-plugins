#!/usr/bin/env python3
"""
SDK Scaffolding Script

Generates complete SDK project structure for Python, .NET, or TypeScript.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any


def create_python_sdk(config: Dict[str, Any]) -> None:
    """Create Python SDK project structure."""
    name = config["name"]
    base_dir = Path(name)
    base_dir.mkdir(exist_ok=True)

    # Create directory structure
    src_dir = base_dir / "src" / name.replace("-", "_")
    src_dir.mkdir(parents=True, exist_ok=True)

    tests_dir = base_dir / "tests"
    tests_dir.mkdir(exist_ok=True)

    docs_dir = base_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    examples_dir = base_dir / "examples"
    examples_dir.mkdir(exist_ok=True)

    workflows_dir = base_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # Create pyproject.toml
    pyproject = f"""[project]
name = "{name}"
version = "0.1.0"
description = "{config['description']}"
authors = [{{name = "{config['author']}", email = "hello@infiquetra.com"}}]
requires-python = ">=3.12"
readme = "README.md"
license = {{text = "MIT"}}

dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.3.0",
    "mypy>=1.9.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = false

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "-v --cov=src --cov-report=html --cov-report=term"

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*"]

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80
"""
    (base_dir / "pyproject.toml").write_text(pyproject)

    # Create source files
    package_name = name.replace("-", "_")

    (src_dir / "__init__.py").write_text(f'''"""
{config["description"]}
"""

from .client import {to_pascal_case(name)}Client
from .version import __version__

__all__ = ["{to_pascal_case(name)}Client", "__version__"]
''')

    (src_dir / "version.py").write_text('__version__ = "0.1.0"\n')

    (src_dir / "client.py").write_text(f'''"""
Main SDK client for {config["name"]}.
"""

import httpx
from typing import Any, Dict, Optional


class {to_pascal_case(name)}Client:
    """Client for interacting with {config["description"]}."""

    def __init__(
        self,
        base_url: str = "{config['api_url']}",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the SDK client.

        Args:
            base_url: Base URL of the API
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {{"Content-Type": "application/json"}}
        if self.api_key:
            headers["Authorization"] = f"Bearer {{self.api_key}}"
        return headers

    async def get_resource(self, resource_id: str) -> Dict[str, Any]:
        """
        Get a resource by ID.

        Args:
            resource_id: The resource identifier

        Returns:
            Resource data as dictionary

        Raises:
            httpx.HTTPError: If the request fails
        """
        url = f"{{self.base_url}}/resources/{{resource_id}}"
        response = await self._client.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
''')

    (src_dir / "models.py").write_text('''"""
Data models for SDK.
"""

from pydantic import BaseModel, Field
from typing import Optional


class Resource(BaseModel):
    """Resource data model."""

    id: str = Field(..., description="Resource identifier")
    name: str = Field(..., description="Resource name")
    description: Optional[str] = Field(None, description="Resource description")
    created_at: str = Field(..., description="ISO 8601 timestamp")
''')

    (src_dir / "exceptions.py").write_text(f'''"""
Custom exceptions for {config["name"]}.
"""


class {to_pascal_case(name)}Error(Exception):
    """Base exception for SDK errors."""
    pass


class AuthenticationError({to_pascal_case(name)}Error):
    """Raised when authentication fails."""
    pass


class ResourceNotFoundError({to_pascal_case(name)}Error):
    """Raised when a resource is not found."""
    pass


class ValidationError({to_pascal_case(name)}Error):
    """Raised when request validation fails."""
    pass
''')

    # Create test files
    (tests_dir / "__init__.py").write_text("")

    (tests_dir / "test_client.py").write_text(f'''"""
Tests for {to_pascal_case(name)}Client.
"""

import pytest
from {package_name}.client import {to_pascal_case(name)}Client


@pytest.mark.asyncio
async def test_client_initialization():
    """Test client can be initialized."""
    async with {to_pascal_case(name)}Client(base_url="https://api.example.com") as client:
        assert client.base_url == "https://api.example.com"
        assert client.timeout == 30.0


@pytest.mark.asyncio
async def test_client_headers():
    """Test client generates correct headers."""
    async with {to_pascal_case(name)}Client(api_key="test-key") as client:
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
''')

    # Create README
    readme = f"""# {config["name"]}

{config["description"]}

## Installation

```bash
pip install {name}
```

## Quick Start

```python
from {package_name} import {to_pascal_case(name)}Client

async with {to_pascal_case(name)}Client(api_key="your-api-key") as client:
    resource = await client.get_resource("resource-id")
    print(resource)
```

## Development

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linting
ruff check src/

# Run type checking
mypy src/
```

## License

MIT
"""
    (base_dir / "README.md").write_text(readme)

    # Create .gitignore
    gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Testing
.pytest_cache/
.coverage
htmlcov/

# Virtual environments
venv/
ENV/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
"""
    (base_dir / ".gitignore").write_text(gitignore)

    # Create GitHub workflow
    workflow = f"""name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest tests/ -v

      - name: Run ruff
        run: ruff check src/

      - name: Run mypy
        run: mypy src/
"""
    (workflows_dir / "test.yml").write_text(workflow)

    print(f"✅ Python SDK scaffolded: {base_dir}/")


def create_dotnet_sdk(config: Dict[str, Any]) -> None:
    """Create .NET SDK project structure."""
    print("⚠️  .NET scaffolding not yet implemented. Use 'dotnet new classlib' for now.")
    print("   Reference: references/dotnet-template.md")


def create_typescript_sdk(config: Dict[str, Any]) -> None:
    """Create TypeScript SDK project structure."""
    print("⚠️  TypeScript scaffolding not yet implemented. Use 'npm init' for now.")
    print("   Reference: references/typescript-template.md")


def to_pascal_case(name: str) -> str:
    """Convert kebab-case to PascalCase."""
    return "".join(word.capitalize() for word in name.replace("_", "-").split("-"))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scaffold SDK project")
    parser.add_argument("--name", required=True, help="SDK name (e.g., my-sdk)")
    parser.add_argument(
        "--language",
        required=True,
        choices=["python", "dotnet", "typescript"],
        help="SDK language"
    )
    parser.add_argument("--description", required=True, help="SDK description")
    parser.add_argument(
        "--api-url",
        default="https://api.example.com",
        help="Base API URL"
    )
    parser.add_argument("--author", default="Infiquetra Team", help="Author name")

    args = parser.parse_args()

    config = {
        "name": args.name,
        "language": args.language,
        "description": args.description,
        "api_url": args.api_url,
        "author": args.author,
    }

    print(f"🚀 Scaffolding {args.language.upper()} SDK: {args.name}")

    if args.language == "python":
        create_python_sdk(config)
    elif args.language == "dotnet":
        create_dotnet_sdk(config)
    elif args.language == "typescript":
        create_typescript_sdk(config)

    print("\n📋 Next steps:")
    print(f"   cd {args.name}/")
    print("   # Initialize git repository")
    print("   # Customize client code")
    print("   # Add tests")
    print("   # Update documentation")


if __name__ == "__main__":
    main()
