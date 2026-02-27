---
name: sdk-security-review
description: Perform comprehensive security review of SDK projects including dependency scanning, OWASP checklist, and vulnerability management
when_to_use: |
  Use this skill when the user wants to:
  - Review SDK security
  - Perform security audit
  - Scan dependencies for vulnerabilities
  - Check OWASP compliance
  - Generate security scorecard
  - Validate security practices
---

# SDK Security Review Guide

You are helping the user perform a comprehensive security review of their SDK project.

## Overview

The sdk-security-review skill provides:
- **Dependency Vulnerability Scanning** - Detect CVEs in dependencies
- **OWASP Security Checklist** - Validate against SDK-specific security requirements
- **Security Scorecard** - Generate comprehensive security assessment
- **Remediation Guidance** - Actionable steps to fix issues

## Prerequisites Check

Before conducting security review, verify:
1. **Project type** - Which language (Python, .NET, TypeScript)?
2. **Access** - Can run security scanning tools?
3. **Dependencies** - Are package manifests present?

## Security Review Process

### Step 1: Run Dependency Scan

Use the `security_audit.py` script:

```bash
python plugins/sdk-lifecycle/skills/sdk-security-review/scripts/security_audit.py \
  --project-path "path/to/sdk" \
  --language "python|dotnet|typescript" \
  --report-format "json|html|markdown"
```

The script will:
- Detect project language automatically
- Scan dependencies for known vulnerabilities
- Check for outdated packages
- Validate license compliance
- Generate detailed report

### Step 2: Review OWASP Checklist

Validate the SDK against OWASP Top 10 for SDKs:

#### 1. Input Validation
- [ ] All user inputs are validated
- [ ] Type checking enforced
- [ ] Length limits on strings
- [ ] Whitelist validation where possible

#### 2. Output Encoding
- [ ] Data properly escaped before output
- [ ] HTML/XML encoding when needed
- [ ] JSON serialization secure

#### 3. Authentication & Authorization
- [ ] API keys stored securely (not hardcoded)
- [ ] Support for secure credential providers
- [ ] Token refresh mechanisms
- [ ] Clear auth documentation

#### 4. Sensitive Data Handling
- [ ] No secrets in logs
- [ ] PII handling documented
- [ ] Encryption for sensitive data in transit
- [ ] No secrets in error messages

#### 5. Error Handling
- [ ] All exceptions caught appropriately
- [ ] No sensitive data in error messages
- [ ] Proper error propagation
- [ ] Logging doesn't expose secrets

#### 6. Cryptography
- [ ] Use established crypto libraries (no custom crypto)
- [ ] Strong encryption algorithms (AES-256, RSA-2048+)
- [ ] Secure random number generation
- [ ] Certificate validation enabled

#### 7. Configuration
- [ ] No hardcoded credentials
- [ ] Secure defaults
- [ ] Configuration validation
- [ ] Environment variable support

#### 8. Dependencies
- [ ] All dependencies up to date
- [ ] No known CVEs
- [ ] Minimal dependency footprint
- [ ] License compatibility verified

#### 9. Rate Limiting
- [ ] Client-side rate limiting implemented
- [ ] Retry with exponential backoff
- [ ] Configurable timeout values

#### 10. Logging & Monitoring
- [ ] Structured logging
- [ ] No PII/secrets in logs
- [ ] Request IDs for tracing
- [ ] Security events logged

### Step 3: Language-Specific Security Checks

#### Python Security

```bash
# Install security tools
pip install safety bandit pip-audit

# Scan dependencies
safety check --json
pip-audit --desc

# Code security scan
bandit -r src/ -f json -o bandit-report.json

# Check for outdated packages
pip list --outdated
```

**Common Python vulnerabilities:**
- SQL injection (use parameterized queries)
- Path traversal (validate file paths)
- Deserialization attacks (use JSON instead of unsafe formats)
- Command injection (avoid shell=True)

#### .NET Security

```bash
# Scan dependencies
dotnet list package --vulnerable --include-transitive

# Check for outdated packages
dotnet list package --outdated

# Use security analyzers
dotnet add package Microsoft.CodeAnalysis.NetAnalyzers
dotnet build /p:RunAnalyzers=true
```

**Common .NET vulnerabilities:**
- SQL injection (use parameterized queries)
- XSS (validate/encode output)
- Insecure deserialization (avoid BinaryFormatter)
- Path traversal (use Path.GetFullPath validation)

#### TypeScript Security

```bash
# Scan dependencies
npm audit --json
npm audit fix

# Use Snyk for deeper analysis
npx snyk test

# Check for outdated packages
npm outdated
```

**Common TypeScript vulnerabilities:**
- Prototype pollution
- ReDoS (Regular Expression Denial of Service)
- XSS in DOM manipulation
- Insecure dependencies

### Step 4: Generate Security Scorecard

The security audit script generates a scorecard:

```
Infiquetra SDK Security Scorecard
============================

Project: my-sdk
Language: Python
Scan Date: 2026-02-11

Vulnerability Summary
---------------------
Critical: 0
High: 1
Medium: 3
Low: 5
Info: 2

Dependency Status
-----------------
Total Dependencies: 15
Outdated: 3
Vulnerable: 1
License Issues: 0

OWASP Checklist Compliance
--------------------------
Input Validation: ✓ PASS
Output Encoding: ✓ PASS
Authentication: ⚠ WARNING (API key in example code)
Sensitive Data: ✓ PASS
Error Handling: ✓ PASS
Cryptography: ✓ PASS
Configuration: ✓ PASS
Dependencies: ✗ FAIL (1 vulnerable dependency)
Rate Limiting: ✓ PASS
Logging: ✓ PASS

Overall Score: 85/100 (B)

Critical Actions Required
-------------------------
1. Update httpx to >= 0.27.2 (CVE-2024-XXXX)
2. Remove hardcoded API key from examples/quickstart.py
3. Update outdated dependencies (see details below)

Recommendations
---------------
- Add security.md file with vulnerability reporting process
- Implement automated dependency scanning in CI/CD
- Add pre-commit hooks for secret detection
- Consider adding rate limiting to client
```

### Step 5: Review Remediation Steps

For each finding, the report includes:

**Example: Vulnerable Dependency**
```
Finding: httpx 0.26.0 has known vulnerability CVE-2024-XXXX
Severity: HIGH
Impact: Potential for SSRF attacks
Remediation:
  1. Update pyproject.toml: httpx>=0.27.2
  2. Run: pip install --upgrade httpx
  3. Test SDK functionality after upgrade
  4. Update CHANGELOG.md with security fix
Reference: https://nvd.nist.gov/vuln/detail/CVE-2024-XXXX
```

## Common Security Issues

### Issue: Hardcoded secrets in code

**Detection:**
```bash
# Use truffleHog or git-secrets
trufflehog filesystem src/
```

**Remediation:**
- Remove hardcoded secrets from code
- Use environment variables or secret managers
- Add patterns to .gitignore
- Rotate exposed secrets immediately
- Add pre-commit hooks to prevent future occurrences

### Issue: Vulnerable dependencies

**Detection:**
Language-specific tools (safety, npm audit, dotnet list package --vulnerable)

**Remediation:**
- Update to patched version
- If no patch available, consider alternative package
- Document risk if upgrade not possible
- Add to security.md for transparency

### Issue: Missing input validation

**Detection:**
Code review and testing with invalid inputs

**Remediation:**
- Add validation for all user inputs
- Use type hints/interfaces
- Implement length/range checks
- Whitelist acceptable values
- Return clear validation errors

### Issue: Secrets in logs

**Detection:**
```bash
# Search for potential secret logging
grep -r "logger.*api_key" src/
grep -r "print.*password" src/
```

**Remediation:**
- Redact sensitive fields in logs
- Use structured logging with field filtering
- Review logging statements in error handlers
- Add tests for log output

## Security Best Practices

### 1. Secure Defaults
```python
# Good: Secure by default
def __init__(self, api_key: str, verify_ssl: bool = True):
    self.verify_ssl = verify_ssl  # Default to True

# Bad: Insecure default
def __init__(self, api_key: str, verify_ssl: bool = False):
    self.verify_ssl = verify_ssl  # Default to False is dangerous
```

### 2. Certificate Validation
```python
# Always validate certificates
async def _make_request(self, url: str):
    async with httpx.AsyncClient(verify=True) as client:
        response = await client.get(url)
```

### 3. Timeout Configuration
```python
# Always set timeouts
client = httpx.AsyncClient(timeout=30.0)  # Prevent hanging requests
```

### 4. Secret Redaction
```python
def __repr__(self):
    # Redact sensitive fields
    return f"Client(base_url={self.base_url}, api_key=***)"
```

### 5. Rate Limiting
```python
from asyncio import Semaphore

class Client:
    def __init__(self, max_concurrent=10):
        self._semaphore = Semaphore(max_concurrent)

    async def _make_request(self, url: str):
        async with self._semaphore:
            # Make request with concurrency limit
            pass
```

## CI/CD Integration

Add security scanning to GitHub Actions:

```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run dependency scan
        run: |
          python plugins/sdk-lifecycle/skills/sdk-security-review/scripts/security_audit.py \
            --project-path . \
            --fail-on critical,high

      - name: Upload security report
        uses: actions/upload-artifact@v4
        with:
          name: security-report
          path: security-report.html
```

## Vulnerability Disclosure

Create `SECURITY.md` in repository root:

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| 0.x.x   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Email: user@example.com

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

Response time: 48 hours

## Security Update Process

1. Vulnerability assessed within 48 hours
2. Fix developed and tested
3. Security advisory published
4. Patch release issued
5. Users notified via GitHub Security Advisories
```

## Next Steps

After security review:
1. **Fix critical/high vulnerabilities** immediately
2. **Update dependencies** to latest secure versions
3. **Document security practices** in README
4. **Add security scanning** to CI/CD pipeline
5. **Create SECURITY.md** file
6. **Schedule regular reviews** (quarterly)

## References

For detailed security guidelines, see:
- `references/security-checklist.md` - Complete OWASP security checklist
- `references/dependency-scanning.md` - Tool setup and automation
- `references/vulnerability-management.md` - Process for handling findings
