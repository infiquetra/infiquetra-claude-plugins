---
name: sdk-scaffolding
description: Scaffold SDK projects for .NET, Python, or TypeScript with complete structure, tests, and CI/CD
when_to_use: |
  Use this skill when the user wants to:
  - Create a new SDK project
  - Scaffold SDK project
  - Generate client library
  - Set up SDK structure
  - Initialize SDK for .NET/Python/TypeScript
---

# SDK Scaffolding Guide

You are helping the user create a new SDK project with a complete structure, testing framework, and CI/CD pipeline.

## Overview

The sdk-scaffolding skill generates a production-ready SDK project structure for:
- **.NET (C#)**: NuGet package with .csproj configuration
- **Python**: Modern project with pyproject.toml and uv
- **TypeScript**: npm/pnpm package with TypeScript configuration

Each generated project includes:
- Source code structure with example client
- Comprehensive test suite setup
- Documentation templates
- CI/CD workflows (GitHub Actions)
- Quality tools configuration
- Example usage code

## Prerequisites Check

Before scaffolding, verify:
1. **Language choice** - Which language does the user want (.NET, Python, TypeScript)?
2. **SDK name** - What should the SDK be called? (e.g., "my-sdk")
3. **Target service** - What service/API will this SDK interact with?
4. **Package scope** - Organization/namespace (e.g., "@coxauto" or "CoxAuto.Infiquetra")

## Scaffolding Process

### Step 1: Gather Project Information

Ask the user for:
- **SDK name** (e.g., "my-sdk", "infiquetra.SDK", "@vecu/identity-sdk")
- **Language** (.NET, Python, or TypeScript)
- **Description** (brief description of SDK purpose)
- **Target API** (base URL of the service this SDK will wrap)
- **Author/Team** (default: Infiquetra Team)

### Step 2: Generate Project Structure

Use the `scaffold_sdk.py` script:

```bash
python plugins/sdk-lifecycle/skills/sdk-scaffolding/scripts/scaffold_sdk.py \
  --name "sdk-name" \
  --language "python|dotnet|typescript" \
  --description "SDK description" \
  --api-url "https://api.service.com" \
  --author "Infiquetra Team"
```

The script will create:

#### For Python Projects:
```
my-sdk/
├── src/
│   └── vecu_my_sdk/
│       ├── __init__.py
│       ├── client.py
│       ├── models.py
│       ├── exceptions.py
│       └── version.py
├── tests/
│   ├── __init__.py
│   ├── test_client.py
│   └── test_models.py
├── docs/
│   ├── index.md
│   └── api-reference.md
├── examples/
│   └── quickstart.py
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── publish.yml
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
└── .gitignore
```

#### For .NET Projects:
```
infiquetra.Wallet.SDK/
├── src/
│   └── infiquetra.Wallet.SDK/
│       ├── Client.cs
│       ├── Models/
│       ├── Exceptions/
│       └── infiquetra.Wallet.SDK.csproj
├── tests/
│   └── infiquetra.Wallet.SDK.Tests/
│       ├── ClientTests.cs
│       └── infiquetra.Wallet.SDK.Tests.csproj
├── docs/
├── examples/
│   └── Quickstart/
├── .github/workflows/
├── infiquetra.Wallet.SDK.sln
├── README.md
├── CHANGELOG.md
└── LICENSE
```

#### For TypeScript Projects:
```
my-sdk/
├── src/
│   ├── client.ts
│   ├── models.ts
│   ├── exceptions.ts
│   └── index.ts
├── tests/
│   ├── client.test.ts
│   └── models.test.ts
├── docs/
├── examples/
│   └── quickstart.ts
├── .github/workflows/
├── package.json
├── tsconfig.json
├── README.md
├── CHANGELOG.md
└── LICENSE
```

### Step 3: Initialize Package Configuration

The script generates language-specific configuration:

#### Python (pyproject.toml)
```toml
[project]
name = "my-sdk"
version = "0.1.0"
description = "Python SDK for Infiquetra Wallet Service"
authors = [{name = "Infiquetra Team", email = "hello@infiquetra.com"}]
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
    "mypy>=1.9.0"
]

[tool.ruff]
line-length = 100
target-version = "py312"
```

#### .NET (.csproj)
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <PackageId>infiquetra.Wallet.SDK</PackageId>
    <Version>0.1.0</Version>
    <Authors>Infiquetra Team</Authors>
    <Description>C# SDK for Infiquetra Wallet Service</Description>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Http" Version="8.0.0" />
    <PackageReference Include="System.Text.Json" Version="8.0.0" />
  </ItemGroup>
</Project>
```

#### TypeScript (package.json)
```json
{
  "name": "@vecu/my-sdk",
  "version": "0.1.0",
  "description": "TypeScript SDK for Infiquetra Wallet Service",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "jest",
    "lint": "eslint src/"
  },
  "dependencies": {
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.3.0",
    "jest": "^29.0.0",
    "eslint": "^8.0.0"
  }
}
```

### Step 4: Generate CI/CD Workflows

Create GitHub Actions workflows:

#### test.yml (All Languages)
```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup
        # Language-specific setup
      - name: Install dependencies
        # Language-specific install
      - name: Run tests
        # Language-specific test command
      - name: Run linting
        # Language-specific lint command
```

#### publish.yml (package registry (PyPI/npm))
```yaml
name: Publish

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build package
        # Language-specific build
      - name: Publish to package registry (PyPI/npm)
        # package registry (PyPI/npm) publish command
```

### Step 5: Initialize Git Repository

```bash
cd sdk-name/
git init
git add .
git commit -m "chore: initial SDK scaffolding"
```

### Step 6: Verify Project Setup

Run initial tests to verify:

**Python:**
```bash
uv pip install -e ".[dev]"
pytest tests/
ruff check src/
mypy src/
```

**/.NET:**
```bash
dotnet restore
dotnet build
dotnet test
```

**TypeScript:**
```bash
npm install
npm test
npm run lint
```

## Language-Specific Patterns

### Python Best Practices
- Use `httpx` for async HTTP client
- Use `pydantic` for data validation
- Type hints throughout
- Async/await support
- pytest for testing

### .NET Best Practices
- Target .NET 8.0+
- Use `HttpClient` with dependency injection
- System.Text.Json for serialization
- Async/await throughout
- xUnit for testing

### TypeScript Best Practices
- Use `axios` for HTTP client
- Strong typing with interfaces
- Async/await support
- Jest for testing
- ESLint for linting

## Common Issues

### Issue: "Package name already exists"
**Solution:**
- Check package registry (PyPI/npm) for existing packages
- Choose a unique name or namespace
- Use organization prefix (@coxauto/, CoxAuto.)

### Issue: "Dependencies not resolving"
**Solution:**
- Verify package registry (PyPI/npm) access
- Check network connectivity
- Update package manager configuration

### Issue: "Tests failing after scaffolding"
**Solution:**
- Example tests are templates - customize for your API
- Update mock data to match your service
- Add actual API integration tests

## Next Steps

After scaffolding:
1. **Customize client code** - Implement actual API calls
2. **Update models** - Add data models for your API
3. **Write tests** - Add comprehensive test coverage
4. **Update documentation** - Customize README and docs
5. **Configure CI/CD** - Add package registry (PyPI/npm) credentials
6. **Create first release** - Tag v0.1.0 and publish

## References

For detailed templates and patterns, see:
- `references/python-template.md` - Python SDK structure and patterns
- `references/dotnet-template.md` - .NET SDK structure and patterns
- `references/typescript-template.md` - TypeScript SDK structure and patterns
- `references/ci-pipeline-patterns.md` - CI/CD workflow examples
