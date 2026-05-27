---
name: appsec-audit
description: |
  Application security audit focused on URL and input trust boundaries, SSRF-style risks,
  redirects, metadata endpoints, allowlists, and evidence-backed findings.
when_to_use: |
  Use when reviewing code that accepts URLs, fetches remote resources, follows redirects,
  proxies requests, imports external data, parses user-controlled input, or touches
  network egress controls.
---

# AppSec Audit

Use this skill to audit application code for URL and input trust boundary risks. Focus on
evidence-backed findings, not speculative concerns.

---

## Scope

Review:

- User-controlled URLs, hosts, paths, query strings, headers, and webhook destinations.
- HTTP clients, redirect handling, proxy code, file importers, and fetch/download helpers.
- SSRF-style paths to cloud metadata endpoint addresses and internal networks.
- DNS rebinding, scheme confusion, localhost/private-network access, and open redirects.
- Allowlist and blocklist enforcement.
- Input parsing at trust boundaries.

---

## Process

1. Map external inputs and trust boundaries.
2. Trace each input to network, file, shell, database, template, or redirect sinks.
3. Check validation order: parse, canonicalize, validate, then use.
4. Confirm allowlists are positive and exact enough for the risk.
5. Check redirects do not escape the approved destination set.
6. Check cloud metadata endpoint protections and private network restrictions.
7. Produce findings only when code evidence supports the risk.

---

## SSRF Checklist

- Reject non-HTTP schemes unless explicitly required.
- Reject localhost, loopback, link-local, private, multicast, and unspecified addresses.
- Protect metadata endpoints, including `169.254.169.254` and provider-specific hostnames.
- Re-resolve DNS or pin validated IPs when redirects or retries occur.
- Validate every redirect hop.
- Enforce outbound allowlists at the URL/host layer and, where possible, network egress layer.
- Set conservative timeouts and response size limits.

---

## Finding Format

```markdown
## AppSec Audit Finding

**Severity**: [Critical/High/Medium/Low]
**Category**: [SSRF / redirect / input validation / allowlist / metadata endpoint / other]
**File**: [path:line]
**Evidence**: [Specific code behavior and data flow]
**Impact**: [What an attacker can do]
**Fix**: [Concrete remediation]
**Validation**: [How to prove the fix]
```

If no findings are found, state the files reviewed and any residual test gaps.
