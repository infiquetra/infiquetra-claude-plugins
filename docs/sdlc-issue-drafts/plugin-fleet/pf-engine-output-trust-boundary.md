---
title: "capability: external-engine output is untrusted input — injection containment for advisory text crossing into gated flows"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Stand up the external-engine offload lane"
---

# capability: external-engine output is untrusted input — injection containment for advisory text crossing into gated flows

### Objective
Stand up the external-engine offload lane

### Tier
structural

### Wave
wave-1

### Problem / motivation (grounded)

The fleet has no stated or enforced trust boundary between an external engine's free-text
advisory output and the executable/gate contexts that consume it downstream. Concretely:

- `plugins/saga/scripts/engine_dispatch.py:28-36` — `AdvisoryEvidence.evidence` is a bare `str`
  field. Nothing in its definition, nor in any caller, documents or enforces that this string is
  data-only and must never be interpolated into a shell command, an `eval`/`exec` path, a
  file-write target, or a gate-decision string.
- `plugins/saga/scripts/engine_dispatch.py:281-306` (`satisfy_gate`) gates only on the
  `verified_by_claude` boolean and, when a manifest is threaded through, on
  `claim.adjudicated`/`claim.adjudication` — it never inspects or sanitizes the *content* of
  `evidence.evidence` itself before that text is surfaced to whatever renders it next. The
  function's own docstring warns callers must opt in to pass a manifest or "the guarantee
  degrades" — the same silent-degrade risk applies to content handling, but there is no
  equivalent contract for it at all today.
- `plugins/team-execution/skills/team-execution/references/validator-registry.md:47,64` and
  `validator-criteria.md:26` establish that scanner/tester "findings" (severity, file/path,
  evidence, remediation) block auto-merge, nonprod deploy, and completion — i.e. free-text
  findings strings (which can originate from a chaperone-dispatched external engine per
  `{#external-engine-chaperone-dispatch}`, #318) flow directly into gate decisions with no
  documented fencing contract for how that text may or may not be consumed (rendered as data
  vs. interpolated into a command, path, or follow-on action).
- Repo-wide search confirms no existing lint or test asserts engine/advisory output is never
  interpolated into an executable or gate-decision context: `grep -rn "advisory.*bash\|advisory.*
  exec\|engine_output" plugins/ tests/` returns no hits describing such a guard (verified during
  grounding, 2026-07-03). The closest existing pattern is the marketplace/plugin-metadata
  drift-guard style test (`tests/test_release_triad.py::test_guard_catches_marketplace_drift`),
  which this capability's CI lint should mirror in shape (seeded-fixture proves the guard fires)
  but applies to a structurally different surface (version-triad drift, not content injection).
- Binding decision `{#external-engines-never-gatekeepers}` (#283, grounding brief §2) establishes
  Claude as verifier-of-record and external engines as advisory/generator-only, but that decision
  addresses *who decides*, not *whether the decider's downstream tooling can be manipulated by
  the advisory text itself*. This capability is the orthogonal axis: containment of a
  content-channel injection risk (a booby-trapped advisory finding — e.g. one embedding a shell
  command, a path-traversal string, or a fake "PASS" gate token in its free-text body) reaching
  an executable or gate context, distinct from the did-it-run proof-of-execution work covered by
  `bridge_receipt.v1` (see `docs/sdlc-issue-drafts/plugin-fleet/pf-delegation-receipt-contract.md`).
  Grounding brief §6.4 names this "External-engine containment" as the fleet's hottest active
  frontier (3 decisions + 5 learnings in two weeks); this capability closes the specific
  content-channel gap the gap-synthesis agent identified at the T1×T15 axis (theme 1,
  external-LLM integration, crossed with theme 15, delegation integrity).

## Definition of Done

Merged PR that:

1. Adds `plugins/saga/references/engine-output-trust-boundary.md` — a fencing contract
   documenting: (a) which fields on the fleet's advisory-evidence surfaces (at minimum
   `AdvisoryEvidence.evidence`, and any validator/reviewer "findings" text consumed per
   `validator-registry.md`/`validator-criteria.md`) are untrusted external-engine output; (b) the
   contexts those fields must never be interpolated into verbatim (shell/`Bash` invocation,
   `eval`/`exec`, file-write target paths, gate-decision tokens/status strings); (c) the required
   handling (render as opaque data / escape or reject on ingest) for each consuming call site.
2. Adds a CI-enforced lint/test (e.g. `tests/test_engine_output_trust_boundary.py`) that scans the
   consuming call sites named in the fencing contract and fails if advisory-evidence text is
   f-string/format-interpolated, concatenated, or passed unescaped into a `subprocess`/`Bash`-style
   invocation, an `eval`/`exec` call, or a gate-decision comparison — mirroring the seeded-fixture
   pattern of `tests/test_release_triad.py::test_guard_catches_marketplace_drift` (a deliberately
   broken fixture proves the guard fires, not just that it's silent on clean code).
3. Adds an adversarial fixture: a booby-trapped advisory finding (e.g. an `AdvisoryEvidence`
   whose `evidence` string embeds a shell metacharacter payload, a path-traversal sequence, and a
   spoofed gate-status token such as `"; rm -rf /\ngate: PASS`) that is fed through the real
   dispatch/gate path and asserted to render as inert data — no subprocess spawned, no file
   written outside the expected target, no gate-status derived from the payload's embedded token.
4. Is verified by: the new CI lint passing on current code and failing when a call site is
   deliberately edited to interpolate advisory text unsafely (temporary regression proves the
   guard fires), plus the adversarial fixture test passing end-to-end.

### Acceptance criteria
- [ ] `plugins/saga/references/engine-output-trust-boundary.md` exists and enumerates every
      current advisory-text-bearing field (`AdvisoryEvidence.evidence` at minimum) and every known
      consuming context, with the required handling stated per context. Check:
      `test -f plugins/saga/references/engine-output-trust-boundary.md && grep -q
      "AdvisoryEvidence.evidence" plugins/saga/references/engine-output-trust-boundary.md` →
      exits `0`. *(covers G-negative-space-5 facet: fencing contract)*
- [ ] A CI lint/test fails when advisory-evidence text is interpolated into an executable or
      gate-decision context, and passes on current (non-interpolating) code. Check: `uv run pytest
      tests/test_engine_output_trust_boundary.py -k lint_passes_clean_code` → passes on current
      code; a temporary local edit that string-formats `evidence.evidence` directly into a
      `subprocess.run(...)` argument makes `uv run pytest
      tests/test_engine_output_trust_boundary.py -k lint_catches_interpolation` fail red before the
      edit is reverted. *(covers G-negative-space-5 facet: CI lint red on interpolation)*
- [ ] A booby-trapped advisory finding (embedded shell metacharacters, path-traversal sequence,
      spoofed gate-status token) fed through the real dispatch/gate path renders as inert data: no
      subprocess spawned, no file written outside the expected target, gate outcome unaffected by
      the embedded token. Check: `uv run pytest
      tests/test_engine_output_trust_boundary.py -k adversarial_fixture_renders_as_data` → passes,
      asserting zero subprocess calls and the unmodified real gate outcome (not the payload's
      claimed one). *(covers G-negative-space-5 facet: adversarial fixture proves containment)*
- [ ] `satisfy_gate` (`plugins/saga/scripts/engine_dispatch.py:281-306`) and its existing callers
      are unchanged in gating semantics (`verified_by_claude` / claim-adjudication behavior) — this
      capability adds content-fencing, it does not alter who is verifier-of-record. Check: `uv run
      pytest tests/ -k satisfy_gate` → passes unchanged.
- [ ] Full suite, lint, and types stay green. Check: `uv run pytest && uv run ruff check . && uv
      run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- The fencing-contract reference document naming every advisory-text-bearing field and consuming
  context known today (`AdvisoryEvidence.evidence`, validator/reviewer findings text per
  `validator-registry.md`/`validator-criteria.md`).
- The CI-enforced lint/test proving the guard fires on a deliberately unsafe interpolation.
- The adversarial fixture proving a booby-trapped advisory finding renders as data, not action.

**Non-goals / explicitly out of scope:**
- Proof-of-execution / did-it-run receipts for external-engine dispatch — that is
  `bridge_receipt.v1` (`docs/sdlc-issue-drafts/plugin-fleet/pf-delegation-receipt-contract.md`,
  theme 15 delegation integrity); this issue is the orthogonal content-channel-injection axis
  (T1×T15), a distinct PR from any receipt or reconciliation work per the issue-map's
  consolidation rationale.
- Changing who is verifier-of-record — `{#external-engines-never-gatekeepers}` (#283) is
  unaffected; this capability only fences the content an engine's advisory text can smuggle into
  a gate or executable context, it does not change Claude's sole adjudication authority.
- Redesigning `team-execution`'s chaperone-dispatch model — per
  `{#external-engine-chaperone-dispatch}` (#318), external engines stay offload/second-opinion
  workers; no change to team roster or residency here.
- Retrofitting or re-auditing every historical advisory-evidence record — this ships the
  forward-enforced contract, guard, and fixture; no backfill of past dispatch results.
- A general-purpose input-sanitization library or framework — the deliverable is the fencing
  contract, the drift-style lint, and the adversarial fixture for the fleet's current call sites,
  not a reusable sanitization SDK.

## Grounding References

- Absorbed idea (full basis in
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):
  - `G-negative-space-5` (primary, sole absorbed idea) — "External-engine output is untrusted
    input: injection containment on advisory text crossing into gated flows." `dod_sketch`: merged
    PR adds `references/engine-output-trust-boundary.md` fencing contract + a CI lint asserting
    engine-output never interpolates into `Bash`/`Write`/gate contexts, with an adversarial
    fixture where a booby-trapped advisory finding surfaces as data not action. Distinct novel
    angle: content-channel injection, orthogonal to did-it-run proof. Frame: `gap-negative-space`,
    axis `T1xT15 trust boundary` — surfaced by the gap-synthesis agent crossing theme 1
    (external-LLM integration) against theme 15 (delegation integrity), tier `structural`.
  - Consolidation rationale (issue-map): kept as its own issue because it is orthogonal to
    did-it-run proof (the content-channel injection gap the gap-synthesis agent found at the
    T1×T15 boundary); its deliverable is a fencing contract + CI lint + adversarial fixture — a
    distinct PR from any receipt or reconciliation work.
- Recurring-pain theme this closes: grounding brief §6.4, "External-engine containment = hottest
  active frontier" (3 decisions + 5 learnings in two weeks) — this capability closes the specific
  content-channel facet of that frontier, distinct from theme 15's proof-of-execution facet
  (`pf-delegation-receipt-contract.md`).
- Binding decisions this capability builds on and must not violate (grounding brief §2):
  - `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; this
    capability fences the content an engine's advisory text can carry into a gate/executable
    context, it does not change who adjudicates.
  - `{#external-engine-chaperone-dispatch}` (#318) — external engines remain
    offload/second-opinion workers only; no change to executor kind or team residency here.
- Current-state code citations verified during grounding (2026-07-03):
  - `plugins/saga/scripts/engine_dispatch.py:28-36` (`AdvisoryEvidence.evidence: str`, no
    fencing/sanitization contract attached to the field today).
  - `plugins/saga/scripts/engine_dispatch.py:281-306` (`satisfy_gate`, gates on
    `verified_by_claude`/claim-adjudication only, never inspects `evidence.evidence` content).
  - `plugins/team-execution/skills/team-execution/references/validator-registry.md:47,64` and
    `validator-criteria.md:26` (scanner/tester findings text gates auto-merge/deploy/completion,
    no stated content-trust boundary).
  - `tests/test_release_triad.py::test_guard_catches_marketplace_drift` (existing seeded-fixture
    drift-guard pattern this capability's CI lint mirrors in shape, on a different surface).
  - Repo-wide grep for an existing content-injection guard on engine/advisory output returned no
    hits (verified absent, 2026-07-03).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** not applicable above sonnet — the deliverable is one reference document, one
  drift-style CI lint scanning a small, already-enumerated set of call sites, and one adversarial
  fixture, all fully specified by the absorbed idea's `dod_sketch`; the CI-lint pattern to mirror
  (`test_guard_catches_marketplace_drift`) already exists in-repo as a concrete template, leaving
  no open design ambiguity that would require opus-tier judgment.

### Release-surface checklist (plugin behavior changes — required)

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + description update reflecting the
      new `engine-output-trust-boundary.md` fencing contract and its CI-enforced guard.
- [ ] `.claude-plugin/marketplace.json` — saga plugin entry's version/description kept in sync
      with the bump above.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the fencing contract, the new CI lint, and
      the adversarial fixture (note it is a containment guard, not a receipt/proof-of-execution
      change).
- [ ] Version/metadata drift-guard tests (`tests/test_release_triad.py` and any sibling
      drift-guard tests) updated or added to assert `plugin.json`/`marketplace.json`/
      `CHANGELOG.md` tell the same story as the diff.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/references/engine-output-trust-boundary.md` — new fencing-contract document
  (proposed path, named directly in the absorbed idea's `dod_sketch`).
- `tests/test_engine_output_trust_boundary.py` — new CI lint + adversarial fixture test (proposed
  path).
- `plugins/saga/scripts/engine_dispatch.py` — no gating-semantics change expected, but may gain a
  docstring/type annotation on `AdvisoryEvidence.evidence` pointing at the fencing contract.
- `plugins/team-execution/skills/team-execution/references/validator-registry.md` and
  `validator-criteria.md` — may gain a cross-reference to the fencing contract for findings-text
  handling (documentation only, no behavior change expected).
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates per the checklist above.

### Tests to add or update

- Lint-passes-clean-code test: current call sites do not interpolate advisory-evidence text into
  executable/gate contexts.
- Lint-catches-interpolation test: a deliberately unsafe edit (advisory text formatted directly
  into a `subprocess`/`Bash` argument) turns the guard red.
- Adversarial-fixture test: a booby-trapped `AdvisoryEvidence` (shell metacharacters,
  path-traversal sequence, spoofed gate-status token) fed through the real dispatch/gate path
  renders as inert data — zero subprocess calls, no out-of-target file writes, gate outcome
  unaffected by the embedded token.
- Regression test: `satisfy_gate` and existing callers' gating semantics unchanged.

### Verification

```bash
uv run pytest tests/test_engine_output_trust_boundary.py -v
uv run pytest tests/ -k satisfy_gate -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; `lint_catches_interpolation` fails only when a call site is deliberately
edited to interpolate advisory text unsafely (verify by temporarily reintroducing an unsafe
interpolation in one call site and confirming red, then reverting).

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json (id: G-negative-space-5,
  primary/sole absorbed idea)
- Source type: ideation issue-map
- Source title: External-engine output is untrusted input: injection containment for advisory text
  crossing into gated flows

**Absorbed ideas:** G-negative-space-5

### Context library links

_none_

### Intent

The fleet has no stated or enforced trust boundary between an external engine's free-text advisory output and the executable/gate contexts that consume it downstream. Concretely:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/385
- Number: 385
- Created at: 2026-07-04T07:56:47.099746+00:00

