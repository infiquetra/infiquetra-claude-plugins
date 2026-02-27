---
name: sdk-documentation
description: Generate comprehensive SDK documentation including API references, usage guides, and documentation portal integration
when_to_use: |
  Use this skill when the user wants to:
  - Document SDK
  - Generate API reference
  - Create SDK usage guide
  - Publish to documentation portal
  - Generate code examples
  - Create SDK tutorials
---

# SDK Documentation Guide

You are helping the user generate comprehensive documentation for their SDK.

## Overview

The sdk-documentation skill provides:
- **API Reference Generation** - Extract from code comments/docstrings
- **Usage Guide Templates** - Quickstart, examples, troubleshooting
- **documentation portal Integration** - Automated publishing workflow
- **Code Example Validation** - Ensure examples work

## Prerequisites Check

Before generating documentation:
1. **Project type** - Which language (Python, .NET, TypeScript)?
2. **Code comments** - Are functions/methods documented?
3. **Examples** - Do working examples exist?

## Documentation Generation Process

### Step 1: Generate API Reference

Use the `sdk_docs.py` script:

```bash
python plugins/sdk-lifecycle/skills/sdk-documentation/scripts/sdk_docs.py \
  --project-path "path/to/sdk" \
  --language "python|dotnet|typescript" \
  --output-dir "docs/" \
  --format "markdown|html"
```

The script will:
- Extract documentation from code
- Generate API reference pages
- Create usage guide templates
- Validate code examples
- Generate table of contents

### Step 2: Complete Usage Guide

Fill in the generated templates:

#### README.md Structure
```markdown
# SDK Name

Brief description of what the SDK does.

## Installation

\`\`\`bash
# Language-specific installation
\`\`\`

## Quick Start

\`\`\`language
# Minimal working example
\`\`\`

## Authentication

How to authenticate with the API.

## Core Concepts

Key concepts users need to understand.

## Usage Examples

### Example 1: Basic Operation
### Example 2: Advanced Feature

## Error Handling

How to handle errors.

## Configuration

Available configuration options.

## API Reference

Link to detailed API documentation.

## Troubleshooting

Common issues and solutions.

## Contributing

How to contribute to the SDK.

## License

License information.
```

#### API Reference Structure
```markdown
# API Reference

## Client

### Constructor

### Methods

#### get_resource(resource_id)

**Description**: Get a resource by ID.

**Parameters**:
- `resource_id` (str): Resource identifier

**Returns**: Resource object

**Raises**:
- `ResourceNotFoundError`: If resource doesn't exist
- `AuthenticationError`: If authentication fails

**Example**:
\`\`\`python
resource = await client.get_resource("res-123")
print(resource.name)
\`\`\`
```

### Step 3: Language-Specific Documentation

#### Python Documentation

Use docstrings throughout:

```python
class Client:
    """
    Client for Infiquetra Service API.

    Args:
        api_key: API key for authentication
        base_url: Base URL of the API (default: https://api.example.com)
        timeout: Request timeout in seconds (default: 30.0)

    Example:
        ```python
        async with Client(api_key="your-key") as client:
            resource = await client.get_resource("res-123")
            print(resource.name)
        ```

    Raises:
        ValueError: If api_key is not provided
    """

    async def get_resource(self, resource_id: str) -> Resource:
        """
        Get a resource by ID.

        Args:
            resource_id: The resource identifier

        Returns:
            Resource object with id, name, and other fields

        Raises:
            ResourceNotFoundError: If resource doesn't exist
            AuthenticationError: If authentication fails
            SDKError: For other API errors

        Example:
            ```python
            resource = await client.get_resource("res-123")
            assert resource.id == "res-123"
            ```
        """
```

Generate with Sphinx:
```bash
pip install sphinx sphinx-rtd-theme
sphinx-apidoc -o docs/api src/
sphinx-build -b html docs/ docs/_build/html
```

#### .NET Documentation

Use XML documentation comments:

```csharp
/// <summary>
/// Client for Infiquetra Service API.
/// </summary>
/// <example>
/// <code>
/// using var client = new ServiceClient("your-api-key");
/// var resource = await client.GetResourceAsync("res-123");
/// Console.WriteLine(resource.Name);
/// </code>
/// </example>
public class ServiceClient
{
    /// <summary>
    /// Gets a resource by ID.
    /// </summary>
    /// <param name="resourceId">The resource identifier</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>The resource</returns>
    /// <exception cref="ResourceNotFoundException">Thrown when resource is not found</exception>
    /// <exception cref="AuthenticationException">Thrown when authentication fails</exception>
    public async Task<Resource> GetResourceAsync(
        string resourceId,
        CancellationToken cancellationToken = default)
    {
        // Implementation
    }
}
```

Generate with DocFX:
```bash
dotnet tool install -g docfx
docfx init
docfx build
```

#### TypeScript Documentation

Use JSDoc comments:

```typescript
/**
 * Client for Infiquetra Service API.
 *
 * @example
 * ```typescript
 * const client = new VECUServiceClient({ apiKey: 'your-key' });
 * const resource = await client.getResource('res-123');
 * console.log(resource.name);
 * ```
 */
export class VECUServiceClient {
  /**
   * Gets a resource by ID.
   *
   * @param resourceId - The resource identifier
   * @returns The resource
   * @throws {ResourceNotFoundError} When resource is not found
   * @throws {AuthenticationError} When authentication fails
   *
   * @example
   * ```typescript
   * const resource = await client.getResource('res-123');
   * ```
   */
  async getResource(resourceId: string): Promise<Resource> {
    // Implementation
  }
}
```

Generate with TypeDoc:
```bash
npm install --save-dev typedoc
npx typedoc --out docs src/index.ts
```

### Step 4: Create Usage Examples

#### Quickstart Example

```python
# examples/quickstart.py
"""
Quickstart example for Infiquetra Service SDK.

This example demonstrates:
- Authentication
- Getting a resource
- Error handling
"""

import asyncio
from vecu_service_sdk import Client, SDKError


async def main():
    # Initialize client with API key
    async with Client(api_key="your-api-key") as client:
        try:
            # Get a resource
            resource = await client.get_resource("res-123")
            print(f"Resource: {resource.name}")

        except SDKError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### Advanced Examples

Create examples for:
- Pagination
- Error handling
- Retry logic
- Rate limiting
- Custom configuration
- Webhook handling
- Batch operations

### Step 5: documentation portal Integration

#### Publish to documentation portal

```bash
# Generate documentation
python sdk_docs.py --project-path . --output-dir docs/

# Sync to documentation portal
rsync -avz docs/ documentation portal:/var/www/docs/sdk-name/

# Or use documentation portal CLI
documentation portal publish --project sdk-name --docs docs/
```

#### documentation portal Configuration

```yaml
# .documentation portal.yml
name: service-sdk
version: 1.0.0
language: python
docs:
  source: docs/
  target: /service-sdk
  index: README.md
  api_reference: api/index.html
navigation:
  - title: Quick Start
    path: quickstart.md
  - title: API Reference
    path: api/
  - title: Examples
    path: examples/
```

### Step 6: Validate Examples

Ensure all code examples work:

```python
# tests/test_examples.py
"""Test that documentation examples work."""

import subprocess
import pytest
from pathlib import Path


def test_quickstart_example():
    """Test quickstart example runs successfully."""
    result = subprocess.run(
        ["python", "examples/quickstart.py"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Resource:" in result.stdout
```

## Documentation Best Practices

### 1. Be Concise
- Short, focused descriptions
- Clear parameter explanations
- Practical examples

### 2. Show, Don't Tell
```python
# Good: Show working code
async with Client(api_key="key") as client:
    resource = await client.get_resource("res-123")

# Bad: Explain without code
"First create a client, then call get_resource..."
```

### 3. Document Errors
```python
Raises:
    ResourceNotFoundError: When resource_id doesn't exist
    AuthenticationError: When API key is invalid
    RateLimitError: When rate limit exceeded (429 response)
```

### 4. Include Examples Everywhere
- Constructor examples
- Method examples
- Error handling examples
- Configuration examples

### 5. Keep Examples Updated
- Run examples in CI/CD
- Version examples with SDK
- Test against latest API

## CI/CD Integration

```yaml
name: Documentation

on:
  push:
    branches: [main]
  release:
    types: [published]

jobs:
  build-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate documentation
        run: |
          python sdk_docs.py --project-path . --output-dir docs/

      - name: Validate examples
        run: pytest tests/test_examples.py

      - name: Publish to documentation portal
        run: |
          documentation portal publish --project ${{ github.repository }} --docs docs/
```

## Documentation Checklist

- [ ] README.md with quickstart
- [ ] API reference generated
- [ ] All public methods documented
- [ ] Code examples provided
- [ ] Examples tested in CI/CD
- [ ] Troubleshooting section
- [ ] Configuration options documented
- [ ] Error handling documented
- [ ] Installation instructions clear
- [ ] License information included
- [ ] Contributing guidelines
- [ ] Changelog maintained
- [ ] documentation portal integration configured

## Next Steps

After generating documentation:
1. **Review** for accuracy and completeness
2. **Test** all code examples
3. **Publish** to documentation portal
4. **Update** with each release
5. **Gather feedback** from users
6. **Improve** based on common questions

## References

For detailed documentation patterns, see:
- `references/api-reference-template.md` - API documentation structure
- `references/usage-guide-template.md` - User guide structure
- `references/documentation portal-integration.md` - Publishing workflow
