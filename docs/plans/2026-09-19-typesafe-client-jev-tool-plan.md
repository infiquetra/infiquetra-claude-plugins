---
title: TypeSafe client, the jev command-line tool, the evaluation harness, and the data rule
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-18-typesafe-jev-integration-research.md
backend: inline
deepened: 2026-09-19
---

# TypeSafe client, the jev command-line tool, the evaluation harness, and the data rule

## Summary

This plan builds the foundation layer for every planned TypeSafe judgment point: a client module in the fleet-core plugin that calls the TypeSafe System One evaluation endpoint, a `jev` command-line tool that wraps it, an evaluation harness that scores past answers against known-correct labels, a durable verdict log, and an enforced rule about what data may leave the machine.

Nothing here makes a decision on its own. This card ships a library, a command, a log, and a policy document; the cards that consume them (issue 1033 onward) are out of scope.

---

## Problem Frame

On 2026-09-18 a research pass measured TypeSafe's Jev model against real work from this repository using a thirty-line throwaway script, `docs/analysis/2026-09-18-typesafe-jev-research-inputs/jev.py.txt`. The measurements were good enough to justify building on: model-tier selection agreed with this repository's own staffing policy on 10 of 10 tasks, batching ten questions into one request cost about a sixth as much and returned in 388 milliseconds, and a diff-size probe showed that how the input is truncated can change the answer.

That script is not shippable. It has no tests, no error handling, no retry, no logging, and it reads the API key inline. Eight downstream cards are blocked on a real one existing.

The research document proposed writing the client against Python's standard library only. On 2026-09-19 the operator recorded a steer on the card that changes that input: TypeSafe now ships official software development kits, and the Python one should be evaluated as the client before direct HTTP calls are written, with the standard-library pattern kept only where a hook or script must run outside this project's Python environment. Resolving that fork with evidence is the main design work in this plan (see KTD1).

---

## Requirements

Grouped by concern. R-IDs are continuous across groups and never renumbered.

### The client

R1. A module `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py` sends a question set and a state to the TypeSafe System One endpoint and returns a typed result, with no live network access required by any test.

R2. The client supports two transports behind one calling interface: the official `typesafe-sdk` Python package when it is importable, and a standard-library `urllib.request` implementation when it is not. The transport in use is reported on every result.

R3. The API key is read from the environment variable `TYPESAFE_API_KEY` once per request build, placed only in the `Authorization` header, and never written to a log, an exception message, a verdict-log record, a dry-run print, or a repr.

R4. Every outcome maps to one of a closed status vocabulary — `ok`, `error`, `timeout`, `malformed` — mirroring `plugins/saga/scripts/engine_bridge_http.py:47-50`. An HTTP error, a timeout, or an unparseable body never reports `ok`.

R5. HTTP 429 (rate limited) and HTTP 529 (overloaded) are retried with exponential backoff, bounded by a maximum attempt count and a total deadline; 400, 401, and 422 are not retried.

R6. Every result records the model version the API resolved (the response's `model` field, for example `jev-1.13.0`), not the alias that was requested (`jev-latest`).

### State handling

R7. Outgoing state passes through a redaction step before any transport sees it: known credential and token patterns and high-entropy strings are replaced with a fixed placeholder.

R8. Outgoing state passes through a deterministic truncation ladder sized to the documented budget — 64,000 tokens for state plus all questions, 32,000 tokens for state plus the single longest question. The ladder's stages are fixed and ordered, and the stages that fired are recorded on the result.

R9. The same input produces the same truncation outcome on every run, on every machine.

### The verdict log and the cache

R10. Every answer is appended to a durable verdict log outside any model's context, carrying the decision identifier, a hash of the question set, a hash of the state, the answer, the confidence, the threshold in force, the resolved model version, and a timestamp.

R10a. Because a yes/no (`noul`) answer carries a probability and no confidence field, while `choice` and `score` answers carry both, the verdict record stores `confidence` as null for a `noul` and records the probability in the answer field. The harness in R17 treats a `noul`'s distance from 0.5 as its confidence for banding, and that derivation is stated in the reference document rather than left to each caller.

R11. An operator override of a suggestion is recorded in the same log, linked to the verdict it overrode.

R12. Answers are cached keyed by the triple (state hash, question-set hash, resolved model) so a replay costs nothing and a change to any of the three misses the cache.

### The command-line tool

R13. A command-line tool `plugins/fleet-core/scripts/jev.py` exposes a raw `ask` verb and the named verbs the downstream cards need: `tier`, `triage`, `lenses`, `bucket`, `status`, `journal-route`, `preflight`, `handoff-check`, `roster-check`, `dedupe`, `readiness`, and `eval`.

R14. Each named verb carries its policy text and question criteria in exactly one place, so a caller never restates them.

R15. `ask --dry-run` prints the request body that would be sent and makes no network call, and its output contains no part of the API key.

R16. The tool emits machine-readable JSON on standard output, uses exit code 0 for a completed call, and a non-zero exit code for a failed one, with the failure reason on standard error.

### The evaluation harness

R17. `jev eval` replays cached or recorded answers against labeled outcomes and reports agreement overall and per confidence band, with no network access.

R18. `jev eval --cached docs/analysis/2026-09-18-typesafe-jev-research-inputs/` reproduces the recorded tier probe's result of 10 of 10 on model-tier agreement.

R18a. Because that folder today contains the probe scripts and the labels but no recorded answers, the work seeds the cache once: the ten tier-probe tasks are re-run live, and the responses are committed as a recorded answer file beside the existing inputs. Every later run of R18 replays that file and makes no network call.

R18b. The evaluation harness's input format is specified, not inferred: a JSON file whose top level is a list of records, each carrying `id`, `state`, `questions`, `answer` (the recorded response), `label` (the known-correct value), and `resolved_model`. The verdict log's own records are accepted as a second input format, so a run against real accumulated verdicts needs no conversion step.

### The data rule

R19. A reference document `plugins/fleet-core/references/typesafe.md` states what may and may not be sent, and the verdict-log record format.

R20. The data rule is enforced in code, not only documented: the redaction step of R7 is on the only path to a transport, so no caller can bypass it.

### Release and governance

R21. The fleet-core plugin's version, the marketplace registry entry, and the fleet-core changelog tell the same story as the diff, and the release-surface parity guard is green.

R22. A guard test fails when the installed `typesafe-sdk` version leaves the pinned range, so a breaking vendor release is caught by continuous integration rather than by a live judgment point.

---

## Key Technical Decisions

### KTD1. Two transports behind one interface: the official Python SDK where it can be imported, standard-library `urllib` everywhere else

The operator's steer asks for the SDK where a dependency is acceptable and the dependency-free pattern where a hook or script must run outside the project environment. That sentence requires both, so the client offers both behind one function.

The evidence supports the split rather than either extreme. In the SDK's favor: it is the vendor's own contract, MIT licensed, free, marked Production/Stable, and it carries typed responses and a retry policy this plan would otherwise hand-write. Against relying on it alone: `typesafe-sdk` is at version 0.7.0, published 2026-09-18, the fourth release in ten days, and two of the last three releases were breaking (0.6.0 changed how `Score` criteria are passed; 0.7.0 swapped the serialization library). It also pulls in `httpx2`, a package from the pydantic organization at version 2.13.0, which this repository does not have today.

The out-of-project case is real and not hypothetical: the research measured a cold Python process at 1.07 to 1.94 seconds, and named hooks that must run without this project's virtual environment. A hook cannot assume `typesafe-sdk` is importable; `urllib` is always there.

Rejected alternative, SDK only: it would leave every out-of-project caller with no path, contradicting the second half of the operator's steer. Rejected alternative, `urllib` only (the research document's original position at section 7.2): it contradicts the first half of the steer, and it means hand-writing retry and response typing the vendor already ships.

Revisit when: `typesafe-sdk` reaches 1.0 and goes ninety days without a breaking release, at which point the `urllib` transport can be reconsidered as a hook-only fallback rather than a co-equal implementation.

### KTD2. The SDK dependency is pinned to a compatible-minor range and guarded by a test

`typesafe-sdk` is declared as `typesafe-sdk>=0.7,<0.8` in `pyproject.toml`, and a test asserts the installed version falls in that range. A pre-1.0 package that shipped two breaking changes in four days will ship another; the question is only whether continuous integration or a live judgment point discovers it. Pinning without the guard is weaker than it looks, because `uv.lock` can be regenerated without anyone reading the diff.

Rejected alternative, an unpinned `typesafe-sdk` dependency: the next breaking minor lands silently on the next lock refresh. Revisit when: the vendor publishes a stability policy or reaches 1.0.

### KTD3. The declared `pydantic` floor is raised to match what the SDK actually requires

`pyproject.toml:17` declares `pydantic>=2.5`; `typesafe-sdk` requires `pydantic>=2.12.0`. The lock file already resolves pydantic 2.13.3 and tenacity 9.1.4, so nothing breaks today — but leaving the declared floor at 2.5 makes the real constraint invisible and lets a future resolution pick a pydantic the SDK cannot use. Raise the declared floor to `>=2.12` in the same change that adds the SDK.

Rejected alternative, leaving the floor alone because the lock happens to satisfy it: an implicit constraint that only a transitive requirement enforces is exactly the kind of drift this repository's parity guards exist to prevent.

### KTD4. The shipped command-line tool is `jev.py`, not `jev.py.txt`

The card's body and three of its four acceptance criteria name `plugins/fleet-core/scripts/jev.py.txt`. That suffix is an artifact of the research folder, where probe scripts were deliberately stored as text so linting would skip them (commit 54693671, "docs(analysis): keep the probe scripts as text records so lint skips them"). There are zero `*.py.txt` files anywhere under `plugins/`; all six in the repository sit under `docs/analysis/`. Meanwhile 100 shipped scripts under `plugins/` import `argparse` and every one of them is named `*.py`.

Shipping a plugin script with a `.txt` suffix would make it invisible to the repository-wide `ruff check .` that the gate and continuous integration run, and would break the ordinary `import`-and-call-`main([...])` pattern that 89 scripts and their tests use. Being precise about what would *not* break: `fleet_commons_shim.load()` resolves modules by file path through `importlib.util.spec_from_file_location` (`plugins/fleet-core/scripts/fleet_commons_shim.py:151-165`), so a `.txt` file could still be loaded that way; and mypy already excludes `plugins/.*/scripts/` by regex (`pyproject.toml:84`), so type checking is lost either way. Linting and the test-import convention are the real costs.

The card's two other new files, `typesafe_client.py` and `jev_eval.py`, carry a plain `.py` suffix on the same line, which is the signature of a copy artifact rather than a deliberate choice.

The plan therefore ships `plugins/fleet-core/scripts/jev.py` and treats the three acceptance criteria as naming that path. This is a correction to a stated acceptance criterion and is flagged for the operator rather than applied silently; see Open Questions.

### KTD5. Redaction runs before truncation, on the only path to a transport

State preparation is one ordered pipeline — redact, then truncate, then serialize — and the transports accept only prepared state. Redacting after truncation would let a secret survive in a segment the ladder kept, and redacting in the caller would make the data rule a convention rather than a mechanism (R20). The cost is that a redaction placeholder consumes budget in the truncation step, which is the correct direction to fail.

### KTD6. The truncation ladder's stages are fixed, ordered, and reported

The ladder follows the research's staged design: cut tool outputs, then abridge long values head and tail, then collapse structures to counts. It never samples, never reorders, and never makes a size-dependent choice that a rerun could make differently (R9). Each fired stage is named on the result, because the research's diff probe showed truncation changing an answer from one plugin to another — an unreported truncation is an unexplainable verdict.

### KTD7. The verdict log is append-only JSON Lines under the git-ignored `.claude/` tree

One record per line, opened in append mode, never rewritten. This matches how the delegation audit store already keeps machine-local durable state (DECISIONS `{#delegation-audit-store-ktds-396}`) and keeps the log out of the repository and out of any model's context (R10). An override record carries the hash of the verdict it overrode rather than repeating it.

### KTD8. The named verbs are declarative policy data, not code branches

Each named verb is an entry in a registry mapping the verb to its question set, its criteria text, its policy text, and its confidence floor. The `ask` verb is the same machinery with the question set supplied by the caller. A new verb is a registry entry plus a test, never a new code path — which is what makes R14 ("in exactly one place") enforceable rather than aspirational.

---

## High-Level Technical Design

### What the endpoint actually returns, verified live

A single request was sent to the endpoint from this worktree on 2026-09-19 to check the contract the plan is built on, rather than trusting the vendor documentation alone. The results below are the observed response, and the implementer should treat them as the shape to code against.

| Observation | Value |
|---|---|
| Status and latency | HTTP 200 in 436 milliseconds |
| Top-level response keys | exactly `answers`, `model`, `usage` |
| Resolved model from the `jev-latest` alias | `jev-1.13.0` |
| Usage fields | `input_tokens`, `output_tokens` |
| A yes/no (`noul`) answer | `{"type": "noul", "noul": 0.97}` — a probability, and **no** `confidence` field |
| A `choice` answer | `{"type": "choice", "choice": ..., "confidence": 0.99, "probabilities": {...}}` |
| Rate-limit headers on a success | none returned |

Two consequences the implementer must not have to discover: a `noul` has no `confidence`, which is why R10a exists; and because no rate-limit headers arrive on a success, the client cannot pace itself pre-emptively and must react to a 429 status, tolerating a missing `Retry-After` header (which `parse_retry_after` already reports as "no usable hint").

### The pipeline

The module is one pipeline with a pluggable tail.

```
caller (jev.py CLI, or a plugin importing through fleet_commons_shim)
        |
        v
  verb registry  ---> question set + criteria + policy text + confidence floor
        |
        v
  state preparation:  redact()  ->  truncate()  ->  serialize()
        |
        v
  cache lookup  (state hash, question hash, model)  -- hit? return, no transport
        |  miss
        v
  transport seam
     |                        |
  SdkTransport          UrllibTransport
  (typesafe-sdk)        (urllib.request; urlopen/getenv/clock injected)
     |                        |
     +-----------+------------+
                 v
       result: status, answers, resolved model, transport, truncation stages, latency
                 |
                 v
       verdict log (append-only JSON Lines)  +  cache write
```

Transport selection resolves in this order: an explicit argument, then the environment variable `INFIQUETRA_TYPESAFE_TRANSPORT` (`sdk` or `urllib`), then the SDK if importable, then `urllib`. Tests exercise both transports with fakes; neither reaches the network.

The `urllib` transport mirrors `plugins/saga/scripts/engine_bridge_http.py` deliberately: the same injection seam names (`urlopen`, `getenv`, `clock`, `timeout`) at `engine_bridge_http.py:58-74`, and the same closed status vocabulary at `engine_bridge_http.py:47-50`. A reviewer who knows one knows the other.

---

## Implementation Units

Units are dependency-ordered. U-IDs are never renumbered.

### U1. Add the SDK dependency, raise the pydantic floor, and guard the pin

Wire the vendor package into the project so later units can import it, and make a breaking vendor release fail continuous integration.

**Goal:** `typesafe-sdk` is a declared, pinned, lock-file-resolved dependency, and a test fails if the installed version leaves the pinned range.

**Requirements:** R22, and the dependency precondition for R2.

**Dependencies:** none.

**Files:** `pyproject.toml`, `uv.lock`, `tests/test_typesafe_sdk_pin.py`.

**Approach:** Add `typesafe-sdk>=0.7,<0.8` to `[project].dependencies` and raise `pydantic>=2.5` to `pydantic>=2.12` (KTD2, KTD3). Refresh the lock with `uv`. The guard test reads the installed distribution version through `importlib.metadata` and asserts it satisfies the declared specifier parsed from `pyproject.toml`, so the test cannot drift from the declaration it guards.

**Patterns to follow:** the existing dependency block at `pyproject.toml:13-20`; the drift-guard posture described in DECISIONS `{#http-bridge-receipt-pair-387-383}` KTD9, where a guard proves a declaration rather than restating it.

**Test scenarios:**

- Happy path: the installed `typesafe-sdk` version satisfies the specifier declared in `pyproject.toml`; the test passes.
- Failure path: a fake installed version of `0.8.0`, injected by monkeypatching the metadata lookup, fails the assertion with a message naming both the installed version and the declared range.
- Edge case: the specifier is read from `pyproject.toml` at test time, so editing the declared range and the installed version together keeps the test green — proving the test guards the declaration rather than a hard-coded literal.
- Error path: `typesafe-sdk` not installed at all raises a clear skip-or-fail with a message naming the package, never an opaque `PackageNotFoundError`.

**Verification:** `uv sync` resolves without conflict, and the guard test passes and demonstrably fails against a seeded wrong version.

### U2. The client module and its transport seam

The heart of the card: one calling interface, two transports, a closed status vocabulary, and a key that never leaks.

**Goal:** `typesafe_client.py` sends a prepared request over either transport and returns a typed result.

**Requirements:** R1, R2, R3, R4, R5, R6.

**Dependencies:** U1.

**Files:** `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py`, `tests/test_typesafe_client.py`.

**Approach:** A module-level `ask(state, questions, *, model="jev-latest", transport=None, ...)` returning a frozen `dataclass` named `AskResult` — a dataclass rather than a bare dictionary, so a typo in a field name fails at the call site instead of silently reading `None`, and so the two transports are forced to produce the same shape. Its fields are `status` (one of the four constants), `answers`, `model` (the resolved version, never the alias), `transport` (`"sdk"` or `"urllib"`), `truncation` (the stages that fired), `usage`, `latency_ms`, and `note` (the failure reason, empty on success). It carries no field that could hold the key. The `urllib` transport is a close sibling of `engine_bridge_http.py`'s `runner` factory: `urlopen`, `getenv`, and `clock` are keyword-injected with real defaults bound at call time so tests pass fakes. The SDK transport wraps `typesafe_sdk.TypeSafeClient` and normalizes its exception classes onto the same closed status vocabulary, so a caller cannot tell the transports apart from the result's shape. The key is read through the injected `getenv` at request-build time and written only into the `Authorization` header.

Retry uses the existing `retry_with_backoff` in `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py:137-186` rather than a second backoff implementation — but note its default `is_retryable` fires on status 429 only (`retry_backoff.py:38-40`). This client must pass an explicit `is_retryable` covering both 429 and 529, or 529 will fall straight through as a non-retryable error. That is the single most likely way this unit ships subtly wrong, which is why it has its own test scenario below. `parse_retry_after` in the same module handles both `Retry-After` header forms and should be passed through.

**Patterns to follow:** `plugins/saga/scripts/engine_bridge_http.py:47-50` (status constants), `:58-79` (injection seams and the lazy `getenv` default), `:112-120` (the "SECRET BOUNDARY" comment block and the resolve-once-into-the-header discipline), `:128-140` (mapping `HTTPError` and `URLError` onto statuses); `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py:69-186` for backoff and `Retry-After` parsing; the two UniFi clients (`plugins/unifi/skills/unifi-network/scripts/unifi_network_client.py:187-197`) as the only existing callers of that helper.

**Test scenarios:**

- Happy path, `urllib` transport: a fake `urlopen` returns a recorded 200 body; the result status is `ok`, the answers match, and the resolved model reads `jev-1.13.0` even though `jev-latest` was requested.
- Happy path, SDK transport: a fake SDK client returns a recorded response object; the result has the same shape and field values as the `urllib` result for the same input, proving the two transports are interchangeable.
- Request shape: the posted body's `questions` is a dictionary keyed by question identifier, `state` and `model` are present, and the target URL is the System One endpoint.
- Authentication header: the bearer token is taken from the injected `getenv` for `TYPESAFE_API_KEY` and appears only in the `Authorization` header.
- Error path, 400: a fake `urlopen` raising `HTTPError` with status 400 yields status `error`, is not retried, and the note names the status.
- Error path, 401 and 422: same as 400 — mapped to `error`, not retried.
- Error path, 429: the first two attempts raise 429, the third returns 200; the result is `ok` after exactly three attempts, and the fake clock shows backoff grew between attempts.
- Error path, 529: same retry behavior as 429. This scenario is mandatory and must be written against the real `retry_with_backoff` rather than a stub, because the helper's default retry predicate covers 429 only — a client that forgets its own `is_retryable` passes every other test in this unit and fails only here.

- Error path, `Retry-After` honored: a 429 carrying a `Retry-After` header of two seconds produces a wait of at least that long on the fake clock, proving `parse_retry_after` is wired in rather than ignored.

- Error path, `Retry-After` absent: a 429 with no `Retry-After` header still retries on the plain exponential schedule rather than raising or waiting forever. A live success returns no rate-limit headers at all, so absence is the normal case, not the exception.

- Answer shapes: a recorded response containing a `noul`, a `choice`, and a `score` answer parses all three; the `noul` result carries its probability and a null confidence, and the `choice` result carries `choice`, `confidence`, and `probabilities`.
- Error path, retry exhaustion: every attempt raises 429; the result is `error` after the bounded maximum attempts, never an unbounded loop.
- Error path, timeout: a fake `urlopen` raising a socket timeout yields status `timeout`, distinct from `error`.
- Error path, malformed body: a 200 response whose body is not JSON, and a 200 whose body is JSON but lacks `answers`, both yield status `malformed`, never `ok`.
- Secret containment: with the environment key set to a recognizable sentinel, every string in the result, every log record emitted, and the text of every exception raised across all of the failure scenarios above contains no substring of the sentinel.
- Edge case, missing key: `TYPESAFE_API_KEY` unset yields a clear `error` naming the missing variable, and makes no network call.
- Edge case, transport selection: with the SDK importable and no override, the SDK transport is chosen; with `INFIQUETRA_TYPESAFE_TRANSPORT=urllib`, the `urllib` transport is chosen; with the SDK not importable, the `urllib` transport is chosen and the result says so.
- Edge case, called twice: two identical calls with the cache disabled produce two transport calls with byte-identical request bodies.

**Verification:** both transports return equivalent results for a recorded response; no test touches the network; the sentinel key appears in no test output.

### U3. State preparation — redaction then the truncation ladder

The step that makes the data rule a mechanism rather than a promise.

**Goal:** prepared state is redacted, within budget, deterministic, and self-describing about what was cut.

**Requirements:** R7, R8, R9, R20.

**Dependencies:** U2.

**Files:** `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py` (the `prepare_state` pipeline and the redactor), `tests/test_typesafe_client.py`.

**Approach:** `prepare_state(state, questions)` returns the prepared state plus a record of the ladder stages that fired. Redaction replaces matches of a fixed pattern set — bearer tokens, common cloud and vendor key shapes, `*_API_KEY`-style assignments, private-key headers, and long high-entropy strings — with a fixed placeholder. Truncation then applies the fixed ladder in order until the budget is met: drop recorded tool outputs, abridge long string values head-and-tail with an explicit elision marker, then collapse lists and mappings to counts. Budget is measured against the documented 32,000-token state-plus-longest-question limit and the 64,000-token total, using a conservative character-to-token estimate that errs toward cutting more rather than less. Nothing in the pipeline consults a clock, a random source, or an environment value.

**Patterns to follow:** the staged ladder described in `docs/analysis/2026-09-18-typesafe-jev-integration-research.md` section 7.4. There is no general-purpose text scrubber in the repository to reuse — a survey found only `_sanitize_argv`, duplicated in `plugins/codex/scripts/codex_delegate.py:409-426` and `plugins/agy/scripts/agy_delegate.py:1851-1868`, which redacts command-line arguments rather than arbitrary text, and the credential *detector* in `plugins/unifi/skills/unifi-network/scripts/site_profile_loader.py:192-211`, which rejects documents rather than scrubbing them. Borrow the pattern vocabulary from both; write the general scrubber here.

**Test scenarios:**

- Happy path: a small state passes through unchanged, and the reported ladder stages are empty.
- Redaction: a state containing a bearer token, an `AWS_SECRET_ACCESS_KEY=` assignment, a private-key header block, and a sixty-character high-entropy string emerges with each replaced by the placeholder and none of the originals present anywhere in the output.
- Redaction, nested: secrets inside nested mappings and inside list elements are redacted at every depth.
- Redaction, no false positive on ordinary prose: a plan paragraph and a unified diff hunk with no credentials pass through byte-identical.
- Ladder stage 1: a state whose tool-output field alone exceeds the budget is reduced by dropping that field, and the reported stages name only stage 1.
- Ladder stage 2: a state still over budget after stage 1 has its long strings abridged head and tail, and the elision marker is present.
- Ladder stage 3: a state still over budget after stage 2 has its collections collapsed to counts.
- Determinism: the same oversized input prepared one hundred times yields byte-identical output and an identical stage record every time.
- Edge case, empty: empty state, empty question set, and a state that is the empty string each prepare without raising.
- Edge case, huge: a state an order of magnitude over budget terminates through the full ladder and ends within budget, rather than looping.
- Edge case, irreducible: a state that is still over budget after every stage returns a clear refusal rather than silently sending an oversized request.
- Integration: the redactor is on the only path to both transports — a test calls the public `ask` with a secret-bearing state and asserts the fake transport received the placeholder, not the secret.

**Verification:** an oversized, secret-bearing state reaches the transport redacted, within budget, and with its ladder stages named.

### U4. The verdict log and the answer cache

Durable memory outside model context, so the harness in U6 has something to score.

**Goal:** every answer and every override is recorded, and a replay costs nothing.

**Requirements:** R10, R11, R12.

**Dependencies:** U2.

**Files:** `plugins/fleet-core/scripts/fleet_commons/jev_log.py`, `tests/test_jev_log.py`.

**Approach:** Append-only JSON Lines under the git-ignored `.claude/` tree (KTD7), one record per line, with the field set fixed by R10. Hashes are of the canonical serialized form, so key ordering cannot change a hash. The cache is keyed by the triple in R12 and stores the full result; a lookup that misses on any element of the triple is a miss. An override record carries the hash of the verdict it overrode, the value the operator chose, and a timestamp.

**Patterns to follow:** `plugins/fleet-core/scripts/fleet_commons/audit_store.py` and `delegation_state.py` for machine-local durable state under `.claude/`; DECISIONS `{#delegation-audit-store-ktds-396}` for the write-once posture.

**Test scenarios:**

- Happy path: writing a verdict appends one line whose parsed fields match the record contract exactly, with no extra and no missing fields.
- Happy path: an override record links to its verdict by hash and round-trips.
- Cache hit: a second call with the identical state, question set, and resolved model returns the cached result and makes no transport call.
- Cache miss on state: the same questions with a one-character state change misses.
- Cache miss on questions: the same state with a reordered criteria value misses, because the hash is of the canonical form of the content, not of the dictionary's iteration order.
- Cache miss on model: the same state and questions recorded under `jev-1.13.0` miss when the resolved model reads `jev-1.14.0`.
- Edge case, hash stability: two logically identical question sets built with keys inserted in different orders produce the same hash.
- Edge case, called twice: appending the same verdict twice yields two lines, not a rewrite or a silent deduplication, and the reader tolerates both.
- Error path, unwritable log directory: the write fails loudly with a message naming the path, and never swallows the error into a silent no-op.
- Error path, corrupt line: a reader encountering a truncated final line reports it and reads the intact records rather than raising on the whole file.
- Secret containment: a verdict written from a call whose state contained a sentinel secret contains no substring of the sentinel — proving the log stores hashes and prepared state, not raw input.

**Verification:** a call writes exactly one verdict line, a replay of the same call makes no transport call, and no log line contains a secret.

### U5. The `jev` command-line tool

The surface any harness can call with a shell command, without the plugin being visible to it.

**Goal:** `jev.py` exposes `ask` and the twelve named verbs, with a dry run that proves the request body.

**Requirements:** R13, R14, R15, R16, and KTD4's path correction.

**Dependencies:** U2, U3, U4.

**Files:** `plugins/fleet-core/scripts/jev.py`, `plugins/fleet-core/scripts/fleet_commons/jev_verbs.py`, `tests/test_jev_cli.py`.

**Approach:** `argparse` with one subparser per verb, matching the repository's existing command-line scripts — 100 scripts under `plugins/` use `argparse` and none uses `click`. Follow the prevailing shape: `def main(argv: Sequence[str] | None = None) -> int` with `sys.exit(main())` under the name guard, errors printed to standard error with an `ERROR: ` prefix. The verb registry (KTD8) lives in `jev_verbs.py` as declarative data: verb name, question set, criteria, policy text, confidence floor. `ask` takes `--state` or `--state-file`, and `--noul`, `--choice`, or `--score` to build a question set inline. `--dry-run` prints the prepared request body as JSON and exits 0 without a transport call. Output is JSON on standard output; errors go to standard error with a non-zero exit. The `eval` verb delegates to U6.

**Patterns to follow:** `plugins/deploy/scripts/mint_tag.py:198-258` for the flat-flag argparse and `main(argv) -> int` shape; `plugins/mission-control/scripts/sdlc_manager.py:837-850` for the dual text/JSON output helper and the `ERROR: `-to-standard-error convention; `plugins/fleet-core/scripts/fleet_commons_shim.py:151-165` for how a consumer loads a fleet-commons module. For the tests, `tests/test_check_delegation_proof.py:364-365` is the canonical `assert module.main([...]) == 0` form.

**Test scenarios:**

- Happy path, `ask`: `ask --state '{"x":"hello"}' --noul 'Is x a greeting?'` against a fake transport prints JSON containing a probability and exits 0.
- Happy path, dry run: the same invocation with `--dry-run` prints the request body, makes no transport call, and exits 0.
- Secret containment in dry run: with `TYPESAFE_API_KEY` set to a sentinel, the dry-run output contains no substring of the sentinel.
- Each named verb round-trips: for every one of `tier`, `triage`, `lenses`, `bucket`, `status`, `journal-route`, `preflight`, `handoff-check`, `roster-check`, `dedupe`, and `readiness`, a recorded response drives the verb to a parsed answer and exit 0. This is a parameterized test over the registry, so a new verb without a recorded response fails rather than being skipped.
- Registry completeness: the set of subparsers equals the set of registry entries plus `ask` and `eval` — a verb added to one and not the other reds the test.
- Error path, bad JSON state: `--state 'not json'` exits non-zero with a message naming the argument, and makes no transport call.
- Error path, missing key: with `TYPESAFE_API_KEY` unset and no `--dry-run`, the tool exits non-zero naming the variable.
- Error path, transport error: a fake transport returning status `error` produces a non-zero exit and the reason on standard error, never exit 0 with an error body on standard output.
- Edge case, empty state: `--state '{}'` is accepted and sent; the tool does not invent content.
- Edge case, both `--state` and `--state-file`: the tool exits non-zero rather than silently preferring one.
- Integration: running the tool as a subprocess with a fake transport configured through the environment produces the documented JSON on standard output and nothing on standard error.

**Verification:** each acceptance criterion in the card runs against the `jev.py` path; the dry run prints a body with no key; the tool is importable, linted, and type-checked like every other plugin script.

### U6. The evaluation harness

Turns "the suggestion seems good" into agreement per confidence band.

**Goal:** `jev eval` scores recorded answers against labels and reproduces the recorded tier probe.

**Requirements:** R17, R18, R18a, R18b.

**Dependencies:** U4, U5.

**Files:** `plugins/fleet-core/scripts/fleet_commons/jev_eval.py`, `tests/test_jev_eval.py`, `docs/analysis/2026-09-18-typesafe-jev-research-inputs/tier_probe_answers.json` (new, the seeded cache).

**Approach:** The harness reads an input file or a verdict log, pairs each recorded answer with its label, and reports overall agreement plus agreement within each confidence band. Bands are a parameter with a documented default, not a constant buried in code, because the research's explicit finding is that thresholds must come from the harness and never from a cookbook. A yes/no answer's distance from 0.5 stands in for its confidence when banding, per R10a.

**The cache must be seeded first, and this is the unit's first step.** A check on 2026-09-19 found that `docs/analysis/2026-09-18-typesafe-jev-research-inputs/` contains the probe scripts, the thirty-two candidate ideas, the rendered ranking table, and the five research briefs — and no recorded API responses at all. The ten tier-probe tasks and their expected labels exist only as literals inside `tier_probe.py.txt:9-20`. Taken literally, the card's third acceptance criterion therefore cannot pass, because there is nothing cached to replay.

The implementer resolves this by running the ten tier-probe tasks once against the live endpoint, writing the responses to `tier_probe_answers.json` in the format of R18b with the expected tiers as labels, and committing that file. The cost is about ten requests, and every subsequent evaluation run replays the file offline. The seeding step is a one-time action recorded in the changelog, not a recurring part of the harness.

**Patterns to follow:** the probe's own scoring loop in `docs/analysis/2026-09-18-typesafe-jev-research-inputs/tier_probe.py.txt:36-44`, which compares a chosen model tier against an expected one and counts agreement, and its task-and-label list at `:9-20`, which is the labeled dataset.

**Test scenarios:**

- Happy path: ten recorded answers with ten labels, all agreeing, report 10 of 10 and no band below full agreement.

- Seeded cache: the committed `tier_probe_answers.json` parses under the R18b format, carries exactly ten records, and each record has a label drawn from the tier vocabulary.

- Offline guarantee: the evaluation run with the seeded cache makes no transport call, asserted with a transport double that fails the test if it is invoked at all.
- Happy path, the real benchmark: `--cached docs/analysis/2026-09-18-typesafe-jev-research-inputs/` reports the tier probe's 10 of 10 model-tier agreement, matching the figure recorded in the research document's section 2.
- Band reporting: a fixture where high-confidence answers agree and low-confidence answers disagree reports different agreement in each band, proving the bands are computed rather than reported as one number.
- Edge case, empty: an empty input reports zero scored items and exits 0 with a clear message, rather than dividing by zero.
- Edge case, unlabeled: recorded answers with no label are counted as unscored and named in the output, never silently dropped from the denominator.
- Edge case, label disagrees with itself: two labels for the same item are reported as a labeling conflict rather than resolved by picking one.
- Error path, missing directory: a non-existent `--cached` path exits non-zero naming the path.
- Error path, malformed record: an unparseable line is reported with its line number and skipped, and the summary states how many were skipped.
- Integration: no test in this unit opens a network connection; all inputs are recorded files.

**Verification:** with the cache seeded, the card's third acceptance criterion passes against the real research inputs folder offline, and the printed figure matches the 10 of 10 recorded in the research document's section 2.

A caveat the implementer should expect and not paper over: the seeding run is a fresh set of live answers, not the original ones, and the model may not reproduce all ten. If the reseeded run scores below 10 of 10, that is a finding about reproducibility to report to the operator — not a reason to adjust the harness, the labels, or the criterion until it passes.

### U7. The reference document and the data rule

Writes down what may leave the machine and what a verdict record looks like.

**Goal:** `plugins/fleet-core/references/typesafe.md` states the data rule, the verdict-log format, and the transport decision, in a form a future implementer and a reviewer can both use.

**Requirements:** R19.

**Dependencies:** U3, U4.

**Files:** `plugins/fleet-core/references/typesafe.md`.

**Approach:** Three sections. The data rule: issue bodies, plan text, and diffs may be sent after redaction, because this repository already sends comparable content to other model vendors through the existing external-engine HTTP bridge; credentials, raw session transcripts, and customer content may never be sent, and the redaction step of U3 is named as the enforcing mechanism. The verdict-log format: the record's fields, their meanings, and where the log lives. The house rules for any use: the ten rules from the research document's section 8, stated as this repository's policy.

**Patterns to follow:** `plugins/fleet-core/references/effort-convention.md` and `tier-palette.md` for the reference-document shape in this plugin.

**Test expectation:** none — this unit is documentation, and the behavior it describes is tested in U3 and U4.

**Verification:** a reader can answer "may I send this?" and "what does a verdict record contain?" without reading the code.

### U8. Release surfaces and the engineering journal

Makes the installed plugin's metadata tell the same story as the diff.

**Goal:** the fleet-core version, the marketplace entry, and the changelog agree, and the decisions above are recorded where the repository keeps decisions.

**Requirements:** R21.

**Dependencies:** U1 through U7.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/fleet-core/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`.

**Approach:** Bump fleet-core from 0.25.3 to 0.26.0 — a new module family, not a fix — and mirror the version into the marketplace registry entry at `.claude-plugin/marketplace.json:201-204`. Add a `## [0.26.0]` changelog heading above the current top entry, `## [0.25.3] - 2026-08-24`. The guard that must stay green is `tests/test_release_triad.py`, which derives the plugin list from the marketplace file and asserts the three versions agree. Record in `DECISIONS.md`: the data rule, the two-transport decision with its rationale and rejected alternatives (KTD1), the version pin and its guard (KTD2), and the file-naming correction (KTD4), each with a "revisit when" condition. The repository's own instructions require this in the same commit that ships the change.

**Patterns to follow:** the release-surface paragraph of DECISIONS `{#http-bridge-receipt-pair-387-383}`, which names the exact four surfaces and the parity check.

**Test expectation:** none for the journal prose — the version parity is proven by the repository's existing release-surface parity guard, which this unit must leave green.

**Verification:** the release-surface parity check passes, and the full gate runs green.

---

## Scope Boundaries

### True non-goals

No judgment point is wired into any skill, hook, or command. This card ships the library, the tool, the log, and the policy; issue 1033 and the cards after it consume them.

No answer is cached across a state change. The cache key includes the state hash, so a changed state is a miss by construction — freshness is a property of the key, not a separate check.

No persistent local daemon or socket client. The research identified one for per-tool-call hooks; nothing in this card fires per tool call.

No skill, no command, and no agent is added to fleet-core. The plugin is scripts-only by its own description, and stays that way.

No global instruction file changes. The shared-register section in the global instructions is a separate card.

### Deferred to follow-up work

The `monitor-check` verb, which the research document listed but the card's verb list does not. It belongs with the agent-operations runbook card that needs it.

Automatic promotion of any suggestion from advisory to binding. That happens only after a recorded harness run at a chosen band, per the research's own rule 10, and is a decision for the consuming card.

Reconsidering the `urllib` transport once the vendor SDK reaches 1.0 (KTD1's revisit condition).

Folding the two duplicated `_sanitize_argv` implementations in the codex and agy delegation scripts onto the general scrubber this card introduces. The duplication is real and worth removing, but touching two other plugins' delegation paths is a separate change with its own blast radius.

---

## Risks & Dependencies

| Risk | Exposure | Mitigation |
|---|---|---|
| The vendor SDK is pre-1.0 and shipped two breaking changes in four days (0.6.0 and 0.7.0) | U1, U2 | Pinned to `>=0.7,<0.8` with a guard test (KTD2); the `urllib` transport is a working fallback, not a stub |
| `httpx2` is a new transitive dependency this repository does not have today | U1 | It is published by the pydantic organization at 2.13.0; the pin and the lock make the version explicit, and the `urllib` transport does not need it |
| The declared `pydantic` floor is below what the SDK requires | U1 | Raise the declared floor to `>=2.12` (KTD3); the lock already resolves 2.13.3 |
| Truncation can change an answer, as the research's diff probe showed | U3 | The ladder is deterministic and its fired stages are reported on every result (KTD6, R9) |
| A secret reaching the vendor | U3 | Redaction is on the only path to a transport (KTD5, R20), and a sentinel-containment test runs across every failure path in U2, U4, and U5 |
| Accuracy claims with no ground truth | U6 | The harness scores against this repository's own labels; every consuming card ships in suggest mode until a band is measured |
| A live acceptance criterion depends on the network and a valid key | U5 | Already proven: a live request from this worktree on 2026-09-19 returned HTTP 200 in 436 milliseconds, well inside the criterion's two-second bound. It is the only live check; every unit test uses fakes |
| The two Claude plugin trees drift after a fleet-core release | U8 | A known, recorded failure mode: verify both installed trees after the release, per the repository's standing memory on registry skew |

---

## Alternatives Considered

**Use the vendor SDK alone and drop `urllib`.** Simpler, one code path, vendor-maintained retries. Rejected because it leaves hooks and scripts that run outside this project's environment with no client at all, which is the case the operator's steer explicitly reserved for the standard-library pattern.

**Use `urllib` alone, as the research document originally proposed at section 7.2.** Also simpler, zero new dependencies, and the probes already proved it works. Rejected because the operator's steer supersedes that input and asks for the SDK where a dependency is acceptable, and because it means hand-writing typed responses and retry that the vendor ships.

**Put the client in the saga plugin next to `engine_bridge_http.py`.** Rejected: five plugins will consume it, and fleet-core plus the vendored shim is this repository's established mechanism for exactly that (DECISIONS `{#fleet-commons-mechanism-463}`).

**Vendor the SDK's source into the repository to escape version churn.** Rejected: it converts a pinned dependency into an un-upgradable fork, and the guard test in U1 solves the actual problem — being told when the vendor breaks something.

---

## Questions answered from the card

The interactive question tool was not available in this session, so every question the plan skill would have asked was answered from the card, the operator's recorded steer, and the analysis documents. Each answer and its source is recorded here.

| Question | Answer taken | Source |
|---|---|---|
| Scope class: lightweight, standard, or deep? | Deep | The card touches an external paid API and a credential, and eight later cards depend on it; the repository's own issue parser reports `has_security` and `has_api` true for this card's body |
| Resume an existing plan saga, or mint a new one? | Mint | `saga.py scan` returned zero candidates |
| Routing destination: plan-only, pull request, merge, or nonprod deploy? | Pull request | The structured pre-answer carrier supplied by the run driver, validated and applied at intake |
| Execution backend: inline or team execution? | Inline | The same carrier; the recommender was still consulted and its suggestion recorded alongside the chosen value |
| Deploy autonomy: gate or auto? | Not asked | The skill asks it only for a nonprod-deploy destination; this destination is a pull request |
| Gated or advisory consensus? | Not asked | The skill asks it only when a consensus or multi-reviewer signal is present; this card has none |
| Is a plan document warranted at all? | Yes | Eight units, eight load-bearing decisions, and an upstream research document needing traceability — none of the skip conditions hold |
| The official Python SDK, or the dependency-free standard-library client? | Both, behind one interface: the SDK by default where importable, `urllib` outside the project environment | The operator's steer on the card asks for exactly this split; KTD1 records the evidence on both sides |
| Is adding the `typesafe-sdk` package an external commitment needing operator sign-off? | No | The package is MIT licensed and free, and the paid API it calls is already in use with a key the operator provisioned; no new spending commitment is created |
| Should the command-line tool ship as `jev.py.txt`, as three acceptance criteria state? | No — it ships as `jev.py` | There are zero `*.py.txt` files under `plugins/`; the suffix is a research-folder convention from commit 54693671. Recorded as KTD4 and raised in Open Questions rather than applied silently |
| The verb list: the card's twelve plus `eval`, or the research document's list including `monitor-check`? | The card's list | The card is the authoritative scope; `monitor-check` is deferred to the agent-operations card that needs it |
| Where does the verdict log live? | Append-only JSON Lines under the git-ignored `.claude/` tree | The research requires it outside model context; this matches how the delegation audit store already keeps machine-local durable state |
| What does the evaluation harness read, and what plays the part of the cached answers the card names? | A specified JSON record format (R18b), plus the verdict log itself; the cache is seeded once by re-running the ten tier-probe tasks | A check of the research inputs folder found scripts and labels but no recorded responses, so the card's criterion needed a seeding step to be satisfiable at all |
| How is a yes/no answer's confidence recorded, given the API returns none for that type? | Null confidence in the record, with the probability's distance from 0.5 used for banding | Observed directly in a live response on 2026-09-19; the vendor documentation does not state it |

---

## Open Questions

**The file-naming correction in KTD4 changes the literal text of three acceptance criteria on the card.** The plan ships `plugins/fleet-core/scripts/jev.py` and reads those criteria as naming that path. The evidence that the `.txt` suffix is a copy artifact is strong — no such file exists anywhere under `plugins/`, and the two sibling files on the same line of the card carry a plain `.py` — but an acceptance criterion is the operator's text, so the correction is surfaced rather than assumed. If the operator wants the literal `jev.py.txt` path, the tool loses linting, type checking, and ordinary import, and the card's own test requirements become unsatisfiable; that tradeoff is the reason for the recommendation.

---

**The card's third acceptance criterion assumes cached answers that do not exist.** The research inputs folder holds the probe scripts and their labels but no recorded API responses, so `jev eval --cached` has nothing to replay until the cache is seeded. U6 seeds it by re-running the ten tier-probe tasks once and committing the responses, which preserves the criterion's intent — an offline, reproducible benchmark — at the cost of one live run. If the reseeded run does not reproduce 10 of 10, that result is reported rather than engineered away, and the operator decides whether the criterion stands.

---

## Sources / Research

- The card: infiquetra/infiquetra-claude-plugins issue 1032, and the operator's steer comment recorded 2026-09-19.
- `docs/analysis/2026-09-18-typesafe-jev-integration-research.md` — sections 2 (the measurements), 5 (requirements R1 to R4), 7 (delivery mechanics, the truncation ladder, logging and pinning), 8 (the house rules), 9 (risks), and 11 (the plan inputs).
- `docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md` — section 2 (how the simplification changes the TypeSafe plan) and section 8 (the card body).
- `docs/analysis/2026-09-18-typesafe-jev-research-inputs/jev.py.txt` and `tier_probe.py.txt` — the probe client and the recorded tier benchmark.
- `plugins/saga/scripts/engine_bridge_http.py:47-50` (status vocabulary) and `:58-74` (the injection seams this client mirrors).
- `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py` — the existing backoff helper.
- `pyproject.toml:13-20` (dependencies), `:89` (coverage options); `uv.lock` (pydantic 2.13.3, tenacity 9.1.4, httpx 0.28.1).
- `plugins/fleet-core/.claude-plugin/plugin.json` (version 0.25.3), the matching `.claude-plugin/marketplace.json:201-204` entry, `plugins/fleet-core/CHANGELOG.md:8` (latest entry `## [0.25.3] - 2026-08-24`), and `tests/test_release_triad.py` (the guard that holds the three in agreement).
- `tests/test_engine_bridge_http.py:99-174` — the `_capturing_urlopen` fake this card's client tests should mirror; `tests/conftest.py` for the shared fixtures, including the autouse `_no_live_gh` guard.
- A repository-wide survey on 2026-09-19 found no reference to TypeSafe or Jev anywhere outside `docs/analysis/` — zero in `plugins/`, `tests/`, and the engineering journal. This card is the first production touch-point, so the conventions above are the only prior art to match.
- `docs/engineering-journal/DECISIONS.md` — `{#http-bridge-receipt-pair-387-383}` (release-surface and drift-guard posture), `{#fleet-commons-mechanism-463}` (the fleet-commons plus shim distribution mechanism), `{#delegation-audit-store-ktds-396}` (machine-local durable state).
- Vendor documentation, read 2026-09-19: `https://docs.typesafe.ai/api.md` (the endpoint, the question types, the status codes), `https://docs.typesafe.ai/sdk/python.md` and `/sdk/python/usage` (the package, the client classes, the environment variables), `https://docs.typesafe.ai/sdk/python/changelog.md` (the breaking changes in 0.6.0 and 0.7.0), `https://docs.typesafe.ai/models.md` (the 64,000 and 32,000 token budgets, the input-token price, the resolved-model field), `https://docs.typesafe.ai/concepts/state.md` (the accepted state shapes).
- A live request to the endpoint from this worktree on 2026-09-19, recorded in the High-Level Technical Design section above: HTTP 200 in 436 milliseconds, resolved model `jev-1.13.0`, response keys `answers`/`model`/`usage`, no rate-limit headers on success, and a `noul` answer carrying a probability but no confidence field.
- The Python Package Index metadata for `typesafe-sdk`, read 2026-09-19: version 0.7.0 published 2026-09-18, four releases since 2026-09-09, MIT licensed, requiring `httpx2>=2.0.0`, `pydantic>=2.12.0`, `pydantic-core>=2.41.1`, `tenacity>=9.0.0`, and `typing-extensions>=4.13.0`.
