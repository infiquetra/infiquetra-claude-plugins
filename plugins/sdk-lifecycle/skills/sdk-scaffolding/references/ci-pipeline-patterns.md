# CI/CD Pipeline Patterns for SDKs

GitHub Actions workflows for testing, building, and publishing SDKs to package registry (PyPI/npm).

## Test Workflow (All Languages)

### test.yml

```yaml
name: Test

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # Python SDK Testing
  test-python:
    runs-on: ubuntu-latest
    if: hashFiles('pyproject.toml') != ''
    strategy:
      matrix:
        python-version: ["3.12"]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"

      - name: Run pytest
        run: pytest tests/ -v --cov=src --cov-report=xml

      - name: Run ruff
        run: ruff check src/

      - name: Run mypy
        run: mypy src/

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: python

  # .NET SDK Testing
  test-dotnet:
    runs-on: ubuntu-latest
    if: hashFiles('**/*.csproj') != ''
    strategy:
      matrix:
        dotnet-version: ["8.0.x"]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: ${{ matrix.dotnet-version }}

      - name: Restore dependencies
        run: dotnet restore

      - name: Build
        run: dotnet build --no-restore --configuration Release

      - name: Test
        run: dotnet test --no-build --configuration Release --verbosity normal --collect:"XPlat Code Coverage"

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          flags: dotnet

  # TypeScript SDK Testing
  test-typescript:
    runs-on: ubuntu-latest
    if: hashFiles('package.json') != ''
    strategy:
      matrix:
        node-version: ["18.x", "20.x"]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run linting
        run: npm run lint

      - name: Run tests
        run: npm test -- --coverage

      - name: Build
        run: npm run build

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          flags: typescript

  # Security scanning (all languages)
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Snyk security scan
        uses: snyk/actions@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

## Publish Workflow (package registry (PyPI/npm))

### publish.yml

```yaml
name: Publish to package registry (PyPI/npm)

on:
  release:
    types: [created]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to publish'
        required: true

jobs:
  # Publish Python SDK
  publish-python:
    runs-on: ubuntu-latest
    if: hashFiles('pyproject.toml') != ''
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build package
        run: |
          pip install build
          python -m build

      - name: Publish to package registry (PyPI/npm)
        env:
          ARTIFACTORY_URL: ${{ secrets.ARTIFACTORY_URL }}
          ARTIFACTORY_USER: ${{ secrets.ARTIFACTORY_USER }}
          ARTIFACTORY_TOKEN: ${{ secrets.ARTIFACTORY_TOKEN }}
        run: |
          pip install twine
          twine upload \
            --repository-url "${ARTIFACTORY_URL}/api/pypi/pypi-local" \
            --username "${ARTIFACTORY_USER}" \
            --password "${ARTIFACTORY_TOKEN}" \
            dist/*

      - name: Create GitHub release artifacts
        uses: actions/upload-artifact@v4
        with:
          name: python-dist
          path: dist/

  # Publish .NET SDK
  publish-dotnet:
    runs-on: ubuntu-latest
    if: hashFiles('**/*.csproj') != ''
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: "8.0.x"

      - name: Restore dependencies
        run: dotnet restore

      - name: Build
        run: dotnet build --configuration Release --no-restore

      - name: Pack
        run: dotnet pack --configuration Release --no-build --output ./nupkgs

      - name: Publish to package registry (PyPI/npm)
        env:
          ARTIFACTORY_URL: ${{ secrets.ARTIFACTORY_URL }}
          ARTIFACTORY_API_KEY: ${{ secrets.ARTIFACTORY_API_KEY }}
        run: |
          dotnet nuget add source \
            "${ARTIFACTORY_URL}/api/nuget/nuget-local" \
            --name artifactory \
            --username github-actions \
            --password "${ARTIFACTORY_API_KEY}" \
            --store-password-in-clear-text

          dotnet nuget push ./nupkgs/*.nupkg \
            --source artifactory \
            --api-key "${ARTIFACTORY_API_KEY}"

      - name: Create GitHub release artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dotnet-nupkgs
          path: nupkgs/

  # Publish TypeScript SDK
  publish-typescript:
    runs-on: ubuntu-latest
    if: hashFiles('package.json') != ''
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20.x"
          registry-url: ${{ secrets.ARTIFACTORY_URL }}/api/npm/npm-local/

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Publish to package registry (PyPI/npm)
        env:
          NODE_AUTH_TOKEN: ${{ secrets.ARTIFACTORY_NPM_TOKEN }}
        run: npm publish

      - name: Create GitHub release artifacts
        uses: actions/upload-artifact@v4
        with:
          name: typescript-dist
          path: dist/
```

## Version Management Workflow

### version-bump.yml

```yaml
name: Version Bump

on:
  workflow_dispatch:
    inputs:
      version-type:
        description: 'Version bump type'
        required: true
        type: choice
        options:
          - patch
          - minor
          - major

jobs:
  bump-version:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Configure git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      # Python version bump
      - name: Bump Python version
        if: hashFiles('pyproject.toml') != ''
        run: |
          pip install bump2version
          bump2version ${{ github.event.inputs.version-type }}

      # .NET version bump
      - name: Bump .NET version
        if: hashFiles('**/*.csproj') != ''
        run: |
          # Update version in .csproj files
          VERSION=$(grep -oP '<Version>\K[^<]+' **/*.csproj | head -1)
          NEW_VERSION=$(python -c "from semver import VersionInfo; v = VersionInfo.parse('$VERSION'); print(getattr(v, 'bump_${{ github.event.inputs.version-type }}')())")
          find . -name "*.csproj" -exec sed -i "s/<Version>$VERSION<\/Version>/<Version>$NEW_VERSION<\/Version>/" {} \;

      # TypeScript version bump
      - name: Bump TypeScript version
        if: hashFiles('package.json') != ''
        run: |
          npm version ${{ github.event.inputs.version-type }} --no-git-tag-version

      - name: Update CHANGELOG
        run: |
          DATE=$(date +%Y-%m-%d)
          VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "0.1.0")
          sed -i "2i\## [$VERSION] - $DATE\n\n### Changed\n- Version bump: ${{ github.event.inputs.version-type }}\n" CHANGELOG.md

      - name: Commit and tag
        run: |
          git add .
          git commit -m "chore: bump version (${{ github.event.inputs.version-type }})"
          git tag -a "v$(git describe --tags --abbrev=0)" -m "Release v$(git describe --tags --abbrev=0)"
          git push origin main --tags
```

## Release Workflow

### release.yml

```yaml
name: Create Release

on:
  push:
    tags:
      - 'v*'

jobs:
  create-release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Extract version from tag
        id: version
        run: echo "VERSION=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT

      - name: Extract changelog
        id: changelog
        run: |
          VERSION=${{ steps.version.outputs.VERSION }}
          CHANGELOG=$(sed -n "/## \[$VERSION\]/,/## \[/p" CHANGELOG.md | sed '1d;$d')
          echo "CHANGELOG<<EOF" >> $GITHUB_OUTPUT
          echo "$CHANGELOG" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT

      - name: Create GitHub Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: v${{ steps.version.outputs.VERSION }}
          release_name: Release v${{ steps.version.outputs.VERSION }}
          body: ${{ steps.changelog.outputs.CHANGELOG }}
          draft: false
          prerelease: false
```

## package registry (PyPI/npm) Configuration

### Python (.pypirc)

```ini
[distutils]
index-servers =
    artifactory

[artifactory]
repository = https://registry.example.com/artifactory/api/pypi/pypi-local
username = ${ARTIFACTORY_USER}
password = ${ARTIFACTORY_TOKEN}
```

### .NET (NuGet.Config)

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="artifactory" value="https://registry.example.com/artifactory/api/nuget/nuget-local" />
  </packageSources>
  <packageSourceCredentials>
    <artifactory>
      <add key="Username" value="${ARTIFACTORY_USER}" />
      <add key="ClearTextPassword" value="${ARTIFACTORY_TOKEN}" />
    </artifactory>
  </packageSourceCredentials>
</configuration>
```

### TypeScript (.npmrc)

```
registry=https://registry.example.com/artifactory/api/npm/npm-local/
//registry.example.com/artifactory/api/npm/npm-local/:_authToken=${ARTIFACTORY_NPM_TOKEN}
```

## Required Secrets

Configure these secrets in GitHub repository settings:

- `ARTIFACTORY_URL` - package registry (PyPI/npm) base URL
- `ARTIFACTORY_USER` - package registry (PyPI/npm) username
- `ARTIFACTORY_TOKEN` - package registry (PyPI/npm) API token
- `ARTIFACTORY_API_KEY` - API key for NuGet
- `ARTIFACTORY_NPM_TOKEN` - NPM authentication token
- `SNYK_TOKEN` - Snyk security scanning token (optional)

## Best Practices

1. **Semantic versioning** - Use major.minor.patch format
2. **Automated testing** - Run full test suite before publish
3. **Security scanning** - Scan dependencies for vulnerabilities
4. **Code coverage** - Maintain 80%+ coverage
5. **Changelog updates** - Document all changes
6. **Git tags** - Tag releases for traceability
7. **Artifact storage** - Upload build artifacts to GitHub
8. **Multi-environment testing** - Test on multiple language versions
