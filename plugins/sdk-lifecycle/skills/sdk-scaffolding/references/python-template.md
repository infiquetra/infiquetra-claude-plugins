# Python SDK Template

Complete structure and patterns for Python SDK projects.

## Project Structure

```
service-sdk/
├── src/
│   └── vecu_service_sdk/
│       ├── __init__.py          # Package exports
│       ├── client.py            # Main SDK client
│       ├── models.py            # Pydantic data models
│       ├── exceptions.py        # Custom exceptions
│       ├── version.py           # Version string
│       └── utils.py             # Utility functions
├── tests/
│   ├── __init__.py
│   ├── test_client.py           # Client tests
│   ├── test_models.py           # Model tests
│   ├── conftest.py              # Pytest fixtures
│   └── integration/
│       └── test_api.py          # Integration tests
├── docs/
│   ├── index.md                 # Documentation home
│   ├── quickstart.md            # Getting started guide
│   ├── api-reference.md         # API documentation
│   └── examples.md              # Code examples
├── examples/
│   ├── quickstart.py            # Basic usage
│   └── advanced.py              # Advanced patterns
├── .github/
│   └── workflows/
│       ├── test.yml             # Test workflow
│       ├── publish.yml          # Publish to package registry (PyPI/npm)
│       └── docs.yml             # Generate documentation
├── pyproject.toml               # Project configuration
├── README.md                    # Project overview
├── CHANGELOG.md                 # Version history
├── LICENSE                      # MIT license
└── .gitignore                   # Git ignore patterns
```

## pyproject.toml Configuration

```toml
[project]
name = "service-sdk"
version = "0.1.0"
description = "Python SDK for Infiquetra Service"
authors = [
    {name = "Infiquetra Team", email = "hello@infiquetra.com"}
]
requires-python = ">=3.12"
readme = "README.md"
license = {text = "MIT"}
keywords = ["vecu", "sdk", "vehicle-custody"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Typing :: Typed",
]

dependencies = [
    "httpx>=0.27.0",        # Async HTTP client
    "pydantic>=2.0.0",      # Data validation
    "python-dateutil>=2.8.2",  # Date parsing
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.3.0",
    "mypy>=1.9.0",
    "pre-commit>=3.6.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.5.0",
]

[project.urls]
Homepage = "https://github.com/infiquetra/service-sdk"
Documentation = "https://documentation portal.vecu.example.com/service-sdk"
Repository = "https://github.com/infiquetra/service-sdk"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "W",   # pycodestyle warnings
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "S",   # bandit security
    "B",   # flake8-bugbear
    "A",   # flake8-builtins
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
]
ignore = [
    "E501",  # Line too long (handled by formatter)
    "S101",  # Use of assert (ok in tests)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]  # Allow assert in tests

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = false
strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = [
    "-v",
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term",
    "--strict-markers",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests (require API access)",
    "slow: Slow tests",
]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/examples/*",
]

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## Client Pattern

```python
"""Main SDK client."""

import httpx
from typing import Any, Dict, List, Optional
from .models import Resource, CreateResourceRequest
from .exceptions import (
    SDKError,
    AuthenticationError,
    ResourceNotFoundError,
    ValidationError,
)


class VECUServiceClient:
    """
    Client for interacting with Infiquetra Service API.

    Example:
        ```python
        async with VECUServiceClient(api_key="your-key") as client:
            resource = await client.get_resource("resource-id")
            print(resource.name)
        ```
    """

    def __init__(
        self,
        base_url: str = "https://api.service.vecu.example.com",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize the SDK client.

        Args:
            base_url: Base URL of the API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=timeout,
            transport=httpx.AsyncHTTPTransport(retries=max_retries),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"service-sdk/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid or missing API key")
        elif response.status_code == 404:
            raise ResourceNotFoundError("Resource not found")
        elif response.status_code == 422:
            raise ValidationError(f"Validation error: {response.text}")
        elif response.status_code >= 400:
            raise SDKError(f"API error: {response.status_code} - {response.text}")

        return response.json()

    async def get_resource(self, resource_id: str) -> Resource:
        """
        Get a resource by ID.

        Args:
            resource_id: The resource identifier

        Returns:
            Resource object

        Raises:
            AuthenticationError: If authentication fails
            ResourceNotFoundError: If resource doesn't exist
            SDKError: For other API errors
        """
        url = f"{self.base_url}/api/v1/resources/{resource_id}"
        response = await self._client.get(url, headers=self._get_headers())
        data = await self._handle_response(response)
        return Resource.model_validate(data)

    async def list_resources(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Resource]:
        """
        List resources with pagination.

        Args:
            limit: Maximum number of resources to return
            offset: Offset for pagination
            filters: Optional filters to apply

        Returns:
            List of Resource objects
        """
        url = f"{self.base_url}/api/v1/resources"
        params = {"limit": limit, "offset": offset}
        if filters:
            params.update(filters)

        response = await self._client.get(
            url,
            headers=self._get_headers(),
            params=params,
        )
        data = await self._handle_response(response)
        return [Resource.model_validate(item) for item in data["items"]]

    async def create_resource(self, request: CreateResourceRequest) -> Resource:
        """
        Create a new resource.

        Args:
            request: Resource creation request

        Returns:
            Created Resource object
        """
        url = f"{self.base_url}/api/v1/resources"
        response = await self._client.post(
            url,
            headers=self._get_headers(),
            json=request.model_dump(),
        )
        data = await self._handle_response(response)
        return Resource.model_validate(data)
```

## Models Pattern

```python
"""Data models using Pydantic."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Resource(BaseModel):
    """Resource data model."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str = Field(..., description="Resource identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Resource name")
    description: Optional[str] = Field(None, description="Resource description")
    status: str = Field("active", description="Resource status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CreateResourceRequest(BaseModel):
    """Request model for creating a resource."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
```

## Exception Pattern

```python
"""Custom exceptions."""


class SDKError(Exception):
    """Base exception for all SDK errors."""
    pass


class AuthenticationError(SDKError):
    """Raised when authentication fails."""
    pass


class ResourceNotFoundError(SDKError):
    """Raised when a resource is not found."""
    pass


class ValidationError(SDKError):
    """Raised when request validation fails."""
    pass


class RateLimitError(SDKError):
    """Raised when rate limit is exceeded."""
    pass
```

## Testing Pattern

```python
"""Test client functionality."""

import pytest
from unittest.mock import AsyncMock, patch
from vecu_service_sdk import VECUServiceClient
from vecu_service_sdk.models import Resource


@pytest.fixture
async def client():
    """Create test client."""
    async with VECUServiceClient(api_key="test-key") as client:
        yield client


@pytest.mark.asyncio
async def test_get_resource(client):
    """Test getting a resource."""
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "res-123",
            "name": "Test Resource",
            "status": "active",
            "created_at": "2026-02-11T00:00:00Z",
            "updated_at": "2026-02-11T00:00:00Z",
        }

        resource = await client.get_resource("res-123")

        assert resource.id == "res-123"
        assert resource.name == "Test Resource"
        assert isinstance(resource, Resource)
```

## Best Practices

1. **Use async/await** throughout for better performance
2. **Type hints** on all public methods and classes
3. **Pydantic models** for data validation and serialization
4. **Custom exceptions** for different error scenarios
5. **Retry logic** for transient failures
6. **Comprehensive docstrings** with examples
7. **80%+ test coverage** including integration tests
8. **Context manager** support for resource cleanup
