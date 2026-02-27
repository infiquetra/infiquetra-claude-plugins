# sdk-lifecycle

Comprehensive SDK development lifecycle management for multi-language projects (.NET, Python, TypeScript).

## Overview

The `sdk-lifecycle` plugin provides end-to-end support for SDK development, from initial scaffolding through security reviews to documentation publishing. Designed for your organization Infiquetra projects but applicable to any SDK development workflow.

**Key Features:**
- Multi-language project scaffolding (.NET, Python, TypeScript)
- Automated security auditing and vulnerability scanning
- Documentation generation with documentation portal integration
- CI/CD pipeline templates for package registry (PyPI/npm) publishing
- OWASP security checklist compliance
- Comprehensive reference documentation

## Skills

### 1. sdk-scaffolding

Generate complete SDK project structure with tests, docs, and CI/CD.

**Triggers:**
- "create SDK"
- "scaffold SDK project"
- "new client library"
- "initialize SDK"

**Capabilities:**
- Python projects with pyproject.toml and uv
- .NET projects with .csproj and NuGet configuration
- TypeScript projects with package.json and TypeScript config
- Complete directory structure (src/, tests/, docs/, examples/)
- GitHub Actions workflows for testing and publishing
- Quality tools configuration (ruff, mypy, eslint)

**Usage:**
```bash
python plugins/sdk-lifecycle/skills/sdk-scaffolding/scripts/scaffold_sdk.py \
  --name "my-sdk" \
  --language "python" \
  --description "Python SDK for Infiquetra Wallet Service" \
  --api-url "https://wallet.vecu.example.com"
```

**Output:**
- Complete project structure
- Package configuration files
- Example client implementation
- Test suite setup
- Documentation templates
- CI/CD workflows
- Git repository initialization

### 2. sdk-security-review

Perform comprehensive security review including dependency scanning and OWASP compliance.

**Triggers:**
- "review SDK security"
- "SDK security audit"
- "scan dependencies"
- "check vulnerabilities"

**Capabilities:**
- Dependency vulnerability scanning (safety, npm audit, dotnet list package)
- OWASP Top 10 checklist validation
- Code security analysis (bandit, SecurityCodeScan)
- Secret detection (hardcoded credentials)
- Security scorecard generation
- Remediation guidance

**Usage:**
```bash
python plugins/sdk-lifecycle/skills/sdk-security-review/scripts/security_audit.py \
  --project-path "path/to/sdk" \
  --language "python" \
  --report-format "text" \
  --fail-on "critical,high"
```

**Security Checks:**
1. Input validation
2. Output encoding
3. Authentication & authorization
4. Sensitive data handling
5. Error handling
6. Cryptography
7. Configuration
8. Dependencies
9. Rate limiting
10. Logging & monitoring

### 3. sdk-documentation

Generate comprehensive SDK documentation and publish to documentation portal.

**Triggers:**
- "document SDK"
- "generate API reference"
- "SDK usage guide"
- "publish to documentation portal"

**Capabilities:**
- API reference extraction from code comments
- Usage guide templates
- Code example validation
- Multi-format output (Markdown, HTML)
- documentation portal integration
- Documentation versioning

**Usage:**
```bash
python plugins/sdk-lifecycle/skills/sdk-documentation/scripts/sdk_docs.py \
  --project-path "path/to/sdk" \
  --language "python" \
  --output-dir "docs/" \
  --format "markdown"
```

**Generated Documentation:**
- README.md with quickstart
- API reference (all public methods)
- Usage guide with examples
- Troubleshooting section
- Configuration reference
- Contributing guidelines

## Supported Languages

### Python
- **Runtime**: Python 3.12+
- **Package Manager**: uv (modern) or pip
- **Testing**: pytest, pytest-cov
- **Linting**: ruff, mypy
- **Security**: safety, bandit, pip-audit
- **Documentation**: Sphinx, MkDocs

### .NET
- **Runtime**: .NET 8.0+
- **Package Manager**: NuGet
- **Testing**: xUnit, NUnit
- **Code Analysis**: Roslyn analyzers
- **Security**: SecurityCodeScan
- **Documentation**: DocFX

### TypeScript
- **Runtime**: Node.js 18+
- **Package Manager**: npm, pnpm
- **Testing**: Jest, Vitest
- **Linting**: ESLint, Prettier
- **Security**: Snyk, npm audit
- **Documentation**: TypeDoc

## CI/CD Integration

### GitHub Actions Workflows

**Test Workflow** (`test.yml`):
- Multi-version testing matrix
- Quality checks (linting, type checking)
- Security scanning
- Code coverage reporting

**Publish Workflow** (`publish.yml`):
- Automated builds on release
- package registry (PyPI/npm) publishing
- Version tagging
- Release artifact creation

**Security Workflow** (`security.yml`):
- Dependency scanning
- Vulnerability reporting
- Automated security updates

## package registry (PyPI/npm) Integration

Publish SDKs to your organization package registry (PyPI/npm):

**Python**:
```bash
twine upload --repository-url ${ARTIFACTORY_URL}/api/pypi/pypi-local dist/*
```

**.NET**:
```bash
dotnet nuget push --source artifactory
```

**TypeScript**:
```bash
npm publish --registry ${ARTIFACTORY_URL}/api/npm/npm-local/
```

## Reference Documentation

### Scaffolding References
- `python-template.md` - Python SDK structure and patterns
- `dotnet-template.md` - .NET SDK structure and patterns
- `typescript-template.md` - TypeScript SDK structure and patterns
- `ci-pipeline-patterns.md` - CI/CD workflow examples

### Security References
- `security-checklist.md` - Complete OWASP security checklist
- `dependency-scanning.md` - Vulnerability scanning tools and automation
- `vulnerability-management.md` - Process for handling security findings

### Documentation References
- `api-reference-template.md` - API documentation structure
- `usage-guide-template.md` - User guide structure
- `documentation portal-integration.md` - Publishing workflow

## Examples

### Example 1: Create Python SDK

```bash
# Scaffold new Python SDK
python plugins/sdk-lifecycle/skills/sdk-scaffolding/scripts/scaffold_sdk.py \
  --name "my-sdk" \
  --language "python" \
  --description "Python SDK for Infiquetra Wallet Service"

# Navigate to project
cd my-sdk/

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run security audit
python ../sdk-lifecycle/skills/sdk-security-review/scripts/security_audit.py \
  --project-path . \
  --language python

# Generate documentation
python ../sdk-lifecycle/skills/sdk-documentation/scripts/sdk_docs.py \
  --project-path . \
  --output-dir docs/
```

### Example 2: Security Review for Existing SDK

```bash
# Run comprehensive security audit
python plugins/sdk-lifecycle/skills/sdk-security-review/scripts/security_audit.py \
  --project-path /path/to/existing-sdk \
  --report-format json > security-report.json

# Fix vulnerabilities
# ... update dependencies, fix code issues ...

# Re-run audit to verify
python plugins/sdk-lifecycle/skills/sdk-security-review/scripts/security_audit.py \
  --project-path /path/to/existing-sdk \
  --fail-on critical,high
```

### Example 3: Generate and Publish Documentation

```bash
# Generate documentation
python plugins/sdk-lifecycle/skills/sdk-documentation/scripts/sdk_docs.py \
  --project-path /path/to/sdk \
  --output-dir docs/

# Validate examples work
pytest tests/test_examples.py

# Publish to documentation portal
documentation portal publish --project my-sdk --docs docs/
```

## Best Practices

### SDK Development
1. **Start with scaffolding** - Use templates for consistency
2. **Security first** - Run security audits early and often
3. **Document as you go** - Write docstrings/comments immediately
4. **Test comprehensively** - 80%+ code coverage
5. **Automate everything** - CI/CD for testing, security, docs

### Security
1. **No hardcoded secrets** - Use environment variables
2. **Validate all inputs** - Type checking and sanitization
3. **Secure defaults** - HTTPS, certificate validation enabled
4. **Regular audits** - Weekly dependency scans
5. **Respond quickly** - Critical vulnerabilities fixed in 24-48 hours

### Documentation
1. **Show, don't tell** - Code examples everywhere
2. **Keep it updated** - Regenerate with each release
3. **Test examples** - Ensure they actually work
4. **Make it searchable** - Good navigation and search
5. **Version docs** - Maintain docs for each major version

## Integration with Infiquetra Workflows

### During SDK Development

```bash
# 1. Create new SDK
scaffold-sdk service-sdk python

# 2. Implement client code
# ... write code ...

# 3. Run quality checks
pytest tests/ && ruff check src/ && mypy src/

# 4. Security audit
security-audit --fail-on critical,high

# 5. Generate documentation
generate-docs --publish-to documentation portal

# 6. Create release
git tag v0.1.0
git push --tags
```

### In CI/CD Pipelines

```yaml
# .github/workflows/sdk-lifecycle.yml
- name: Run security audit
  run: python sdk_security_audit.py --fail-on critical,high

- name: Generate documentation
  run: python sdk_docs.py --output-dir docs/

- name: Publish to package registry (PyPI/npm)
  run: |
    # Language-specific publish command
```

## Prerequisites

### Required Tools
- Python 3.12+ (for scripts)
- Language-specific tools (dotnet CLI, Node.js, etc.)
- Git
- GitHub CLI (for repository operations)

### Optional Tools
- safety, bandit (Python security)
- Snyk (multi-language security)
- Sphinx, DocFX, TypeDoc (documentation)
- Docker (for consistent build environments)

## Troubleshooting

### Issue: Scaffolding fails
**Solution**: Verify language and project name are valid, check write permissions

### Issue: Security scan reports false positives
**Solution**: Configure ignore rules in .safety-policy.yml or equivalent

### Issue: Documentation generation fails
**Solution**: Ensure code has proper comments/docstrings, install documentation tools

## Related Resources

- [Infiquetra Component Manager](../component-manager) - Component ID registration
- [Infiquetra Test Suite](../test-suite) - Parallel quality checks
- [Infiquetra Docs Generator](../docs-generator) - Service documentation
- [your organization package registry (PyPI/npm)](https://registry.example.com)
- [Infiquetra documentation portal](https://documentation portal.vecu.example.com)

## Contributing

For issues or feature requests:
- GitHub Issues: https://github.com/infiquetra/infiquetra-claude-plugins/issues
- Slack: 

## License

MIT
