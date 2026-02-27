# SDK Security Checklist

Comprehensive OWASP-based security checklist for SDK development.

## 1. Input Validation

### Requirements
- [ ] All user inputs are validated before processing
- [ ] Type checking enforced (type hints, interfaces, generics)
- [ ] Length limits enforced on strings
- [ ] Range validation for numeric inputs
- [ ] Whitelist validation for enums/known values
- [ ] Reject invalid inputs with clear error messages

### Code Examples

```python
# Python: Validation with Pydantic
from pydantic import BaseModel, Field, validator

class CreateResourceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    priority: int = Field(..., ge=1, le=10)

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
```

```csharp
// C#: Validation with Data Annotations
public class CreateResourceRequest
{
    [Required]
    [StringLength(255, MinimumLength = 1)]
    public string Name { get; set; }

    [Range(1, 10)]
    public int Priority { get; set; }
}
```

## 2. Output Encoding

### Requirements
- [ ] HTML entities escaped when rendering HTML
- [ ] XML special characters encoded
- [ ] JSON properly serialized (use libraries, not string concat)
- [ ] URL parameters properly encoded
- [ ] SQL queries parameterized (never string concatenation)

### Code Examples

```python
# Python: Safe JSON serialization
import json

def serialize_response(data: dict) -> str:
    return json.dumps(data)  # Safe serialization
```

```typescript
// TypeScript: Proper encoding
function encodeForUrl(value: string): string {
  return encodeURIComponent(value);
}
```

## 3. Authentication & Authorization

### Requirements
- [ ] No API keys hardcoded in source code
- [ ] Support environment variables for credentials
- [ ] Support credential providers (AWS Secrets Manager, Azure Key Vault)
- [ ] Token refresh mechanisms implemented
- [ ] Clear documentation on authentication methods
- [ ] Support for API key rotation without code changes

### Code Examples

```python
# Python: Secure credential handling
import os
from typing import Optional

class Client:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_key_env: str = "API_KEY"
    ):
        self.api_key = api_key or os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"API key required (set {api_key_env})")
```

## 4. Sensitive Data Handling

### Requirements
- [ ] No secrets in logs (even debug logs)
- [ ] PII handling documented (GDPR/CCPA compliance)
- [ ] Encryption for sensitive data in transit (HTTPS only)
- [ ] No secrets in error messages
- [ ] Secure string representations (__repr__, toString)
- [ ] Memory cleared for sensitive data when possible

### Code Examples

```python
# Python: Secret redaction
class Client:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def __repr__(self) -> str:
        return f"Client(api_key=***)"  # Redact in repr

    def _log_request(self, url: str, headers: dict):
        safe_headers = {k: "***" if "auth" in k.lower() else v for k, v in headers.items()}
        logger.debug(f"Request to {url} with headers {safe_headers}")
```

## 5. Error Handling

### Requirements
- [ ] All exceptions caught at appropriate levels
- [ ] No sensitive data in error messages
- [ ] Proper error types (don't catch generic Exception)
- [ ] Logging doesn't expose secrets
- [ ] User-friendly error messages
- [ ] Stack traces don't leak sensitive info

### Code Examples

```python
# Python: Safe error handling
class SDKError(Exception):
    """Base SDK error - safe to expose."""
    pass

async def make_request(url: str) -> dict:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        # Don't expose full response body (may contain secrets)
        raise SDKError(f"Request failed: {e.response.status_code}")
    except Exception as e:
        # Log full error internally, sanitize for user
        logger.error("Request failed", exc_info=True)
        raise SDKError("Request failed - see logs") from e
```

## 6. Cryptography

### Requirements
- [ ] Use established crypto libraries (no custom implementations)
- [ ] Strong algorithms: AES-256, RSA-2048+, SHA-256+
- [ ] Secure random number generation (secrets module, SecureRandom)
- [ ] Certificate validation enabled (no SSL verification disabled)
- [ ] TLS 1.2+ required
- [ ] No MD5/SHA-1 for cryptographic purposes

### Code Examples

```python
# Python: Secure randomness
import secrets

def generate_token() -> str:
    return secrets.token_urlsafe(32)  # Cryptographically secure

# Bad: Don't use random module for secrets
import random
token = random.randint(0, 999999)  # NOT SECURE
```

```python
# Python: Certificate validation
import httpx

# Good: Verify certificates
client = httpx.AsyncClient(verify=True)

# Bad: Never disable verification in production
client = httpx.AsyncClient(verify=False)  # INSECURE
```

## 7. Configuration

### Requirements
- [ ] No hardcoded credentials
- [ ] Secure defaults (HTTPS, certificate validation enabled)
- [ ] Configuration validation on initialization
- [ ] Environment variable support
- [ ] Clear error messages for misconfiguration
- [ ] Documentation of all configuration options

### Code Examples

```python
# Python: Secure configuration
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl

class ClientConfig(BaseModel):
    base_url: HttpUrl = Field(default="https://api.example.com")
    api_key: Optional[str] = Field(default=None)
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    verify_ssl: bool = Field(default=True)  # Secure default

    def validate_config(self):
        if not self.api_key:
            raise ValueError("API key is required")
```

## 8. Dependencies

### Requirements
- [ ] All dependencies up to date
- [ ] No known CVEs in dependencies
- [ ] Minimal dependency footprint (fewer deps = smaller attack surface)
- [ ] License compatibility verified
- [ ] Automated dependency scanning in CI/CD
- [ ] Dependency pinning for reproducible builds

### Dependency Management

```toml
# Python: Pin dependencies
[project]
dependencies = [
    "httpx>=0.27.2,<0.28",  # Pin to known-good version range
    "pydantic>=2.0.0,<3.0",
]

[project.optional-dependencies]
dev = [
    "safety>=3.0.0",  # Dependency scanning
    "pip-audit>=2.7.0",
]
```

```bash
# Regular dependency audits
pip-audit  # Python
npm audit  # TypeScript
dotnet list package --vulnerable  # .NET
```

## 9. Rate Limiting

### Requirements
- [ ] Client-side rate limiting implemented
- [ ] Retry with exponential backoff
- [ ] Configurable timeout values
- [ ] Circuit breaker for repeated failures
- [ ] Respect server rate limit headers (429 responses)

### Code Examples

```python
# Python: Rate limiting with semaphore
from asyncio import Semaphore

class RateLimitedClient:
    def __init__(self, max_concurrent: int = 10):
        self._semaphore = Semaphore(max_concurrent)

    async def make_request(self, url: str):
        async with self._semaphore:
            # Only max_concurrent requests at a time
            return await self._client.get(url)
```

```python
# Python: Exponential backoff
import asyncio
from typing import TypeVar, Callable

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0
) -> T:
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            await asyncio.sleep(delay)
```

## 10. Logging & Monitoring

### Requirements
- [ ] Structured logging (JSON format)
- [ ] No PII/secrets in logs
- [ ] Request IDs for distributed tracing
- [ ] Security events logged (auth failures, rate limits)
- [ ] Log levels properly used (DEBUG, INFO, WARNING, ERROR)
- [ ] Logs don't contain sensitive request/response bodies

### Code Examples

```python
# Python: Structured logging
import logging
import json

class StructuredLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def log_request(self, method: str, url: str, request_id: str):
        self.logger.info(json.dumps({
            "event": "api_request",
            "method": method,
            "url": url,
            "request_id": request_id,
            # Never log request body (may contain secrets)
        }))

    def log_auth_failure(self, reason: str):
        self.logger.warning(json.dumps({
            "event": "auth_failure",
            "reason": reason,
            # Security event - track for monitoring
        }))
```

## Security Testing Checklist

- [ ] Unit tests for input validation
- [ ] Tests for error handling (invalid inputs)
- [ ] Tests verify secrets not in logs
- [ ] Integration tests with invalid credentials
- [ ] Load tests to verify rate limiting
- [ ] Security scanning in CI/CD pipeline
- [ ] Dependency vulnerability scanning automated
- [ ] Regular penetration testing

## Compliance Checklist

- [ ] SECURITY.md file present
- [ ] Vulnerability disclosure process documented
- [ ] Security section in README.md
- [ ] License compatibility verified
- [ ] Data privacy compliance (GDPR/CCPA if applicable)
- [ ] Security audit completed before release
- [ ] Change log includes security fixes
