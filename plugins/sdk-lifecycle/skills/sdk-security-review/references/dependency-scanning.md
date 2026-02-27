# Dependency Scanning Guide

Tools and automation for scanning SDK dependencies for vulnerabilities.

## Python Dependency Scanning

### Tools

**safety** - Check against known CVE database
```bash
pip install safety
safety check --json > safety-report.json
```

**pip-audit** - Scan for vulnerabilities
```bash
pip install pip-audit
pip-audit --desc --format json
```

**bandit** - Security linter for Python code
```bash
pip install bandit
bandit -r src/ -f json -o bandit-report.json
```

### Configuration

`.safety-policy.yml`:
```yaml
security:
  ignore-cvss-severity-below: 0
  ignore-cvss-unknown-severity: false
  ignore-vulnerabilities:
    # Temporary ignores with expiration
    70612:
      reason: "False positive - not using affected functionality"
      expires: "2026-03-01"
```

## .NET Dependency Scanning

### Built-in Tools

```bash
# Check for vulnerable packages
dotnet list package --vulnerable --include-transitive

# Check for outdated packages
dotnet list package --outdated
```

### Security Analyzers

Add to .csproj:
```xml
<ItemGroup>
  <PackageReference Include="Microsoft.CodeAnalysis.NetAnalyzers" Version="8.0.0">
    <PrivateAssets>all</PrivateAssets>
    <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
  </PackageReference>
  <PackageReference Include="SecurityCodeScan.VS2019" Version="5.6.7">
    <PrivateAssets>all</PrivateAssets>
    <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
  </PackageReference>
</ItemGroup>
```

## TypeScript Dependency Scanning

### npm audit

```bash
# Check for vulnerabilities
npm audit --json > npm-audit.json

# Auto-fix where possible
npm audit fix

# Force fix (may introduce breaking changes)
npm audit fix --force
```

### Snyk Integration

```bash
# Install Snyk CLI
npm install -g snyk

# Authenticate
snyk auth

# Test for vulnerabilities
snyk test --json > snyk-report.json

# Monitor project
snyk monitor
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Dependency Scan

on:
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Monday
  push:
    branches: [main]

jobs:
  scan-python:
    runs-on: ubuntu-latest
    if: hashFiles('pyproject.toml') != ''
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install safety pip-audit
      - name: Run safety
        run: safety check --json --output safety-report.json
      - name: Run pip-audit
        run: pip-audit --format json --output pip-audit-report.json
      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: python-security-reports
          path: |
            safety-report.json
            pip-audit-report.json

  scan-dotnet:
    runs-on: ubuntu-latest
    if: hashFiles('**/*.csproj') != ''
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
      - name: Check vulnerable packages
        run: dotnet list package --vulnerable --include-transitive

  scan-typescript:
    runs-on: ubuntu-latest
    if: hashFiles('package.json') != ''
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - name: Run npm audit
        run: npm audit --json > npm-audit.json
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: npm-audit-report
          path: npm-audit.json
```

## Automated Remediation

### Dependabot Configuration

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    reviewers:
      - "team"

  # .NET dependencies
  - package-ecosystem: "nuget"
    directory: "/"
    schedule:
      interval: "weekly"

  # npm dependencies
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    versioning-strategy: increase
```

## Vulnerability Management Workflow

1. **Detection** - Automated scans identify vulnerabilities
2. **Triage** - Assess severity and exploitability
3. **Remediation** - Update to patched version
4. **Testing** - Verify fix doesn't break functionality
5. **Release** - Publish updated SDK version
6. **Notification** - Inform users via security advisory

## Severity Levels

- **Critical**: Remote code execution, authentication bypass
- **High**: Privilege escalation, data leakage
- **Medium**: Denial of service, information disclosure
- **Low**: Minor security concerns

## Response SLAs

- **Critical**: 24 hours
- **High**: 7 days
- **Medium**: 30 days
- **Low**: 90 days
