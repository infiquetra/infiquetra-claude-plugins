---
title: Issue #385 Engine Output Trust Boundary Plan
type: feat
status: active
date: 2026-07-09
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json
---

# Issue #385 Engine Output Trust Boundary Plan

## Summary

Add a documented and tested trust boundary for external-engine advisory text before that text reaches
gate or executable contexts. The implementation should treat advisory output as opaque data, prove the
current consuming paths do not interpolate it into commands or gate tokens, and keep existing
`satisfy_gate` verifier-of-record semantics unchanged.

## Problem Frame

Issue #385 is the content-channel half of the external-engine offload lane: an external engine remains
advisory, but its free-text output can still be dangerous if downstream tooling treats that text as a
command, path, or gate verdict. The issue points at `AdvisoryEvidence.evidence` and Team Execution
validator findings text as the current text-bearing surfaces.

Grounding confirms the gap is real. `plugins/saga/scripts/engine_dispatch.py:43` defines
`AdvisoryEvidence`, and `plugins/saga/scripts/engine_dispatch.py:640` defines `satisfy_gate`; existing
tests such as `tests/test_saga_engine_dispatch.py:135` prove Claude verification and observer
corroboration semantics, but there is no equivalent content-fencing contract or lint. Existing release
and drift guard patterns are available in `tests/test_release_triad.py:183`, which uses a seeded broken
fixture to prove a guard catches the class it claims to catch.

## Requirements

R1. Add `plugins/saga/references/engine-output-trust-boundary.md` documenting every current
advisory-text-bearing field in scope: `AdvisoryEvidence.evidence` and validator/reviewer findings text
described by Team Execution validator references.

R2. The contract must enumerate forbidden sinks for advisory text: shell or `Bash` invocation,
`eval`/`exec`, file-write target paths, and gate-decision tokens/status strings.

R3. The contract must define required handling per context: render as opaque data, escape when rendering
requires it, reject unsafe sink attempts, and never derive gate status from advisory text content.

R4. Add `tests/test_engine_output_trust_boundary.py` with a CI-enforced guard that scans the named
consuming call sites and fails on unsafe interpolation, concatenation, `format`/f-string use, or direct
pass-through of advisory text into forbidden sinks.

R5. The lint guard must include a seeded broken fixture proving the guard turns red when advisory text is
interpolated into a subprocess-style invocation or gate-token comparison. The final PR validation should
also record a temporary local mutation check, or explicitly state that the seeded fixture is the durable
equivalent of that temporary-red proof.

R6. Add an adversarial fixture using a booby-trapped advisory payload containing shell metacharacters,
path traversal, and a spoofed gate token. Feeding it through the real dispatch/gate path must leave it
as inert evidence data: no subprocess call, no out-of-target file write, and no gate status derived from
the payload.

R7. `satisfy_gate` semantics stay unchanged: gate satisfaction remains based on `verified_by_claude`,
observer corroboration, and manifest adjudication rules, not advisory text content.

R8. Release surfaces remain synchronized for every plugin whose behavior or user-facing guidance changes.
At minimum this plan expects Saga `0.75.9`; if Team Execution reference docs are changed, Team Execution
must bump to `2.14.1` in the same PR.

## Key Technical Decisions

KTD1. Treat this as a contract plus guard, not a sanitizer library: the deliverable is a precise trust
boundary, a seeded structural lint, and an adversarial fixture over current call sites. A reusable
sanitization framework is out of scope.

KTD2. Implement the lint as a narrow AST-backed test helper in `tests/test_engine_output_trust_boundary.py`.
Regex may help find candidate strings, but the red/green guard should reason over Python AST nodes so
f-strings, `.format`, concatenation, and sink calls are detected consistently.

KTD3. Seeded unsafe fixtures live inside the test file, not as production code mutations. The guard must
prove it catches a deliberately unsafe synthetic call site; a final temporary local edit may still be used
as PR evidence, but should not be the only regression proof.

KTD4. Keep `satisfy_gate` content-blind by design. The adversarial test should assert that malicious
text in `AdvisoryEvidence.evidence` cannot make an unverified payload pass, while a properly verified
payload passes for the existing reasons only.

KTD5. Cross-reference Team Execution validator text handling from source-of-truth docs if they are
edited. Because that is user-facing plugin guidance, a Team Execution release bump is required whenever
those docs change.

## Implementation Units

### U1. Add the Engine Output Trust-Boundary Contract

Create the reference document that names advisory text sources, forbidden sinks, and allowed handling.

**Goal:** Make the external-engine content boundary explicit enough for implementers and reviewers to
apply without inventing policy.

**Requirements:** R1, R2, R3.

**Files:** `plugins/saga/references/engine-output-trust-boundary.md`.

**Approach:** Document `AdvisoryEvidence.evidence`, Team Execution validator/reviewer findings text, and
the current gate/executable contexts. Include a small table mapping each text field to allowed handling
and forbidden sinks. Cite `engine_dispatch.py`, `validator-registry.md`, and `validator-criteria.md`.

**Test scenarios:** Documentation existence test checks the file names `AdvisoryEvidence.evidence`,
forbidden sink classes, and the opaque-data handling rule.

**Verification:** `uv run pytest tests/test_engine_output_trust_boundary.py -k contract` proves the
contract exists and contains the required anchors.

### U2. Add the Structural Unsafe-Interpolation Guard

Add a CI test that scans the named consuming call sites and red-tests itself with seeded unsafe code.

**Goal:** Prevent future code from piping advisory text into subprocess, `eval`/`exec`, file path, or gate
token sinks.

**Requirements:** R4, R5.

**Files:** `tests/test_engine_output_trust_boundary.py`.

**Approach:** Implement a small AST visitor that tracks identifiers and attributes named like
`evidence.evidence`, `advisory_text`, or `finding_text` within fixture code and Python call-site files.
Flag f-strings, `.format`, string concatenation, and direct call arguments when they reach forbidden
sinks such as `subprocess.run`, `eval`, `exec`, `Path(...)` write-target construction, or comparisons
against gate tokens. Keep the scanner narrow to named Python files to avoid noisy repo-wide subprocess
tests. Validate Markdown reference docs through contract-anchor assertions, not the AST visitor.

**Test scenarios:** Happy path: current `engine_dispatch.py` Python call sites produce no findings, and
Team Execution reference docs contain the expected trust-boundary cross-reference. Error path: a seeded
unsafe subprocess f-string fixture produces at least one finding. Error path: a seeded gate-token
comparison against advisory text produces at least one finding. Edge case: ordinary rendering of advisory
text as data is allowed.

**Verification:** `uv run pytest tests/test_engine_output_trust_boundary.py -k lint` passes on current
code and proves the red fixtures are detected.

### U3. Add the Adversarial Dispatch/Gate Fixture

Exercise a booby-trapped advisory payload through real Saga dispatch and gate logic.

**Goal:** Prove the dangerous string remains data and does not alter gate semantics or trigger external
side effects.

**Requirements:** R6, R7.

**Files:** `tests/test_engine_output_trust_boundary.py`, `plugins/saga/scripts/engine_dispatch.py`
only if a docstring/type comment is needed for the contract.

**Approach:** Build an `AdvisoryEvidence` payload with shell metacharacters, `../` traversal, and a fake
`gate: PASS` token. Assert unverified payloads still fail `satisfy_gate`; assert verified and
observer-corroborated payloads pass only because `verified_by_claude` and provenance rules are satisfied.
Monkeypatch subprocess/file-write sinks if the test invokes a real dispatch helper; otherwise assert the
dispatch/gate path performs no subprocess or file writes while preserving the payload as inert evidence
data.

**Test scenarios:** Happy path: verified and observer-corroborated evidence with malicious text passes
for existing verifier reasons. Error path: the same malicious text without verification fails. Security
path: no subprocess runner or file writer is invoked because of the text. Regression path:
`tests/test_saga_engine_dispatch.py -k satisfy_gate` remains green unchanged.

**Verification:** `uv run pytest tests/test_engine_output_trust_boundary.py -k adversarial_fixture` and
`uv run pytest tests/test_saga_engine_dispatch.py -k satisfy_gate` pass.

### U4. Cross-Reference Release Surfaces and Drift Guards

Keep plugin metadata, changelogs, and drift guards synchronized with the trust-boundary change.

**Goal:** Ship the new policy as installed-plugin truth, not only code and docs.

**Requirements:** R8.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`plugins/team-execution/skills/team-execution/references/validator-registry.md`,
`plugins/team-execution/skills/team-execution/references/validator-criteria.md`,
`plugins/team-execution/.claude-plugin/plugin.json`, `plugins/team-execution/CHANGELOG.md`,
`tests/test_team_execution_plugin.py`.

**Approach:** Bump Saga from `0.75.8` to `0.75.9`. If the Team Execution validator reference docs are
updated to point at the new trust-boundary contract, bump Team Execution from `2.14.0` to `2.14.1`.
Update marketplace entries and plugin-version assertions for every bumped plugin.

**Test scenarios:** Release parity passes for both changed plugins. Diff-aware guard fails if either
plugin reference surface changes without its release triad bump.

**Verification:** `uv run python scripts/check_release_surface_parity.py`,
`uv run python scripts/sync_marketplace.py --check`, and
`python3 tools/release_surface_diff_guard.py --base-ref origin/main` pass.

## Scope Boundaries

This issue does not change who is verifier-of-record. External engines remain advisory/generator-only.

This issue does not add proof-of-execution receipts, bridge receipt reconciliation, or historical
advisory-evidence backfills.

This issue does not implement a general-purpose sanitization SDK. The guard targets the current
engine-output advisory text surfaces and forbidden sinks.

This issue does not redesign Team Execution validator selection, gate severity, or chaperone dispatch.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| AST guard becomes too broad and flags unrelated subprocess use | Limit scan scope to named advisory text variables and named call-site files. |
| Guard misses a future new advisory-text field | The trust-boundary doc and drift test should enumerate current fields; future fields must update the contract. |
| Adversarial fixture accidentally changes gate semantics | Keep assertions paired with existing `satisfy_gate` tests and do not parse `evidence.evidence` for verdict. |
| Team Execution docs change without release bump | Include Team Execution release triad and version assertion in U4 when those docs are edited. |
| Release surface repeats prior CI failures | Run parity, marketplace sync, and diff guard locally before PR. |

## Verification Plan

- `uv run pytest tests/test_engine_output_trust_boundary.py -v`
- `uv run pytest tests/test_saga_engine_dispatch.py -k satisfy_gate -v`
- `uv run pytest tests/test_saga_plugin.py tests/test_team_execution_plugin.py -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`
- Temporary-red proof: either apply and revert a local unsafe interpolation edit to confirm
  `tests/test_engine_output_trust_boundary.py -k lint` fails, or document why the seeded broken fixture
  is the durable equivalent.

## Route

Destination: `merge`, per outcome authorization.

Execution backend: `inline`, recommended because this is a bounded Saga/Team Execution documentation
and test guard change with no deployment or cross-repo runtime mutation.

Next command: `/doc-review docs/plans/2026-07-09-issue-385-engine-output-trust-boundary-plan.md`
