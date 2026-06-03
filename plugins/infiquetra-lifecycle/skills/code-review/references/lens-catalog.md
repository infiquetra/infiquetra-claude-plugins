# Lens Catalog

The lean infiquetra review-lens set. Lenses are **judgment-selected**, not a fixed roster: the
orchestrator reads the full diff and spawns only the lenses with real work to do. A fixed specialist
list re-opens the "spawn reviewers that find nothing on this diff" problem; this catalog avoids it by
making selection a reasoned call. Each lens is spawned as a **generic agent** (`Explore`/`Task`) — this
plugin has no named `ce-*` agents.

## Always-on lenses (4 — every review)

Spawned on every review regardless of diff content.

### correctness
Logic errors, edge cases, state bugs, error propagation, intent compliance. Folds the high-signal
categories that catch silent breakage:
- **Enum and value completeness** — when the diff adds a new enum value, status, tier, or type constant,
  trace it through **every** consumer. This **requires reading code OUTSIDE the diff**: Grep for sibling
  values, then Read each switch/`if-elsif`/allowlist that branches on them, and confirm the new value is
  handled (not falling through to a wrong default).
- **Race conditions and concurrency** — read-check-write without a uniqueness constraint, find-or-create
  without a unique index, status transitions that are not atomic (`WHERE old_status = ? UPDATE`).
- **Conditional side effects** — a branch that forgets a side effect the sibling branch performs; a log
  that claims an action that was conditionally skipped.
- **Type coercion at boundaries** — values crossing language/JSON boundaries where the type silently
  changes; hash/digest inputs not normalized before serialization.

### security
Auth/authz, secrets, trust boundaries — goes deeper than the correctness pass. Sub-domains:
- **Input validation at trust boundaries** — user input, query params, request bodies, file uploads, and
  webhook payloads accepted without validation or signature verification.
- **Injection** — SQL via string interpolation (use parameterized queries), shell injection
  (`subprocess(shell=True)` + f-string, `os.system` with interpolation, `eval`/`exec` on LLM output),
  template/LDAP/path-traversal/header injection, SSRF via user- or LLM-controlled URLs (allowlist before
  fetch).
- **LLM output trust boundary** — LLM-generated emails/URLs/names persisted without format validation;
  structured tool output written to the DB without shape checks; LLM output stored in a vector DB without
  sanitization (stored prompt injection).
- **Auth/authz bypass** — missing auth middleware, authorization defaulting to allow, role escalation,
  insecure direct object reference, token validation that skips expiry.
- **Cryptographic misuse and secrets exposure** — weak hashes, predictable randomness for tokens,
  non-constant-time secret comparison, hardcoded keys, secrets in source/logs/URLs/error responses.

### testing
Coverage gaps, weak assertions, brittle tests. Sub-domains: missing negative-path and guard-clause tests,
missing edge-case coverage (zero/negative/max/empty/null, single-element collections, unicode), test
isolation violations (shared mutable state, order dependence, clock/timezone coupling, real network
calls), flaky patterns (timing-dependent assertions, ordering assumptions), and missing
security-enforcement tests (the "denied" auth case, rate-limit-blocks, malicious-input sanitization).

### maintainability / conventions
Structural quality plus project-standard compliance. Sub-domains: dead code and unused imports, magic
numbers and string coupling (named constants over bare literals; config over hardcoded URLs/ports), stale
comments and docstrings that describe old behavior, DRY violations (3+ line duplication, copy-paste where
a helper would be cleaner), and infiquetra conventions (ruff 100-char, type hints, naming, frontmatter,
cross-platform portability, version/CHANGELOG consistency).

## Conditional lenses (selected by judgment)

For each, the orchestrator reads the diff and decides whether the domain is genuinely touched. Announce
each selected conditional lens with a one-line justification.

### deploy/migration-verification (DISTINCT — never folded away)
Select when the diff touches DynamoDB schema/GSIs/backfills, IaC/CDK, Ansible, CI/CD publish steps, or any
deploy-boundary change. Infiquetra checklist:
- **DynamoDB** — schema/key changes, GSI additions (capacity, projection), and backfill scripts (batched
  vs all-at-once); a new required attribute needs a backfill before it is read.
- **IaC / CDK** — drift between the change and deployed state; a rollback path; destructive replacements
  (resource recreation that drops data).
- **Ansible** — destructive changes (file/package/service removal), idempotency (re-runs must converge),
  and ordering against application deploys.
- **Go/No-Go + rollback rubric** — pre-deploy baseline capture, a verification query/check that proves the
  change took, and an explicit rollback procedure. Multi-phase safety: does the change break the currently
  running code during a rolling deploy (deploy code first, then migrate)?

### reliability (DISTINCT)
Select when the diff touches error handling, retries, timeouts, circuit breakers, background jobs, async
handlers, queues/DLQs, or health checks. Checklist: retries with backoff and a cap; idempotency of
retried operations; timeouts on external calls; dead-letter handling for failed async work; partial-failure
recovery (3-of-5 processed then crash leaves consistent state); swallowed exceptions (catch-all + log
only); jobs that fail without alerting.

### performance
Select when the diff touches DB queries, ORM calls, loop-heavy transforms, caching, or async/concurrent
code. Checklist: N+1 queries (missing eager loading), missing indexes on new WHERE/ORDER-BY/foreign-key
columns, algorithmic complexity (nested loops, repeated linear search where a map would do), fetch
waterfalls that could be parallel.

### api-contract
Select when the diff touches routes, serializers, exported type signatures, event schemas, or versioning.
Checklist: breaking changes (removed/retyped fields, new required params, changed methods/status codes),
versioning strategy, error-response consistency, rate-limiting/pagination parity, and spec/doc drift.

### adversarial / red-team
Select when the diff is large (>= ~50 changed non-test lines) OR touches auth, payments, data mutations,
or external integrations. This is NOT a checklist — it is adversarial analysis: attack the happy path
(10x load, concurrent requests, slow DB, garbage from an external service), hunt silent failures, exploit
trust assumptions (frontend-only validation, unauthenticated internal APIs), and break the edge cases
(max input, zero/empty/null, first-ever run, double-click in 100ms).

### agent-native
Select when the diff adds user-facing features. Verify the new capability is reachable by an agent
(CLI/skill/programmatic surface), not only via a human UI.

### previous-comments (PR-only, comment-gated)
Select **only** when reviewing a PR that already has review comments or threads from a prior round. Skip
entirely when there is no PR or no prior comments.

## Selection rules

1. Always spawn the **4 always-on** lenses.
2. For each conditional lens, decide from the diff whether its domain has real work — this is judgment,
   not keyword matching. Do not spawn a language- or domain-specific lens just because one config or
   generated file matches.
3. Spawn **deploy/migration-verification** when migration/IaC/Ansible/CI-publish artifacts appear in the
   diff — not for model-only or query-only changes without those artifacts.
4. **Announce the team** before spawning, with a one-line justification per selected conditional lens.
