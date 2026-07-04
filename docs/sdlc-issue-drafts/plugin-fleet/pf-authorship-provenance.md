---
title: "enhancement: computed engine-vs-chaperone authorship ledger, artifact provenance trailer, /retro claim-vs-proof reconciliation, PR-gate cross-check"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
wave: wave-2
---

# enhancement: engine-vs-chaperone authorship ledger, computed from evidence, gated at the PR boundary

## Problem / motivation

The fleet already has a manifest format that carries producer attribution
(`plugins/saga/scripts/provenance_manifest.py:98`, "Producer attribution: who/what
emitted this output (R2)"; `provenance_manifest.py:376` requires an attribution record),
and an engine registry that resolves which engine (Claude / codex / agy) ran a unit
(`plugins/saga/scripts/engine_resolver.py:15`, `plugins/saga/scripts/execution_spec.py:263-294`).
But attribution today is a claim the manifest carries, not a fact the fleet checks:

- `docs/engineering-journal/LEARNINGS.md:305` records the generalizable rule that
  "delegated to an external CLI" is a claim to **verify per run from the transcript,
  never an assumption from the invocation" — after an agy/codex run you must grep the
  transcript for the actual external process call and confirm the external agent, not
  a local clone, did the Write/Edit before attributing authorship. That verification is
  documented as manual practice, not enforced by any gate.
- `docs/engineering-journal/LEARNINGS.md:239` shows the positive case — three genuine
  agy runs each carrying `agy_launched=true` in the run bundle — establishing that a
  hard, checkable `launched=true`-style signal already exists in at least one bridge's
  evidence, but nothing outside that one bridge consumes it as a gate input.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 6, theme 1 ("Silent
  no-ops in delegation & dead wiring") names this as a recurring-pain theme with 5+
  distinct learnings (agy silent Claude-fallback, dead-wiring producer+consumer,
  test-shape-masks-dead-wiring, fake-adapter mismatch) and concludes "any
  bridge/delegation idea needs 'did it actually run/persist' verification" — this is
  the grounding brief's own framing for new theme 15 (delegation integrity), of which
  this issue is one facet.
- Binding decision `{#external-engines-never-gatekeepers}` (#283, cited in the grounding
  brief section 2) establishes that Claude is verifier-of-record on every gated decision
  and external engines are generator/advisory-reviewer/non-gated-worker only — an
  authorship ledger that trusts a bridge's self-reported attribution without an
  independent evidence cross-check would violate this decision's spirit even if it
  never touches the gate mechanism itself.
- Binding decision `{#external-engine-chaperone-dispatch}` (#318) frames external-engine
  participation in teams as "chaperone dispatch" (offload/second-opinion), never a
  second executor kind or git participant — the ledger's job is to make that
  chaperone-vs-engine distinction a computed fact per delivered unit, not a title in a
  prompt.

No component today reconciles what a manifest *claims* about attribution against what
the underlying evidence *proves*, and nothing blocks a PR that asserts delegation
without the corresponding proof.

## Definition of Done

A merged PR that adds, wired into the existing manifest/evidence stack (not a parallel
system):

1. An **authorship ledger computation** — a pure function/module that takes a unit's
   evidence record (transcript grep result, bridge run-report, or equivalent
   `launched=true`/`agy_launched=true`-style signal) and computes the attributed
   engine identity, rather than accepting a self-reported `attribution` field at face
   value. Lives alongside `plugins/saga/scripts/provenance_manifest.py` (or is added to
   it) and is unit-tested independent of any live bridge call.
2. A **rendered provenance trailer** on the delivered artifact (unit run report /
   opt-in commit trailer) whose engine-identity content is sourced from the manifest's
   computed attribution, and a test asserting the rendered trailer text matches the
   manifest attribution byte-for-byte.
3. A **`/retro` reconciliation check** (or equivalent CLI hook consumable by
   `saga:retro`) that flags any manifest claiming an `EXTERNAL_ENGINE`-class
   attribution when the corresponding evidence shows zero invocation receipts for that
   run — i.e., a claim-vs-proof mismatch, not just a missing field.
4. A **PR-gate cross-check**: a PR body or commit asserting "delegated to X" without a
   corresponding `launched=true`-equivalent proof artifact fails the gate the same way
   other release-surface drift guards fail today (pattern: existing marketplace-drift
   guard style checks under `tests/`).
5. Release-surface updates for every plugin whose behavior, schema, or CLI surface
   changed as part of this work (see checklist below).

### Acceptance criteria
- [ ] AC1 (T15-F3-5, primary). Given a unit whose manifest self-reports an engine
  attribution but whose evidence record shows no matching invocation receipt, the
  authorship ledger computes and records the discrepancy rather than passing through
  the self-reported value unchecked.
  Check: a test that constructs a manifest with attribution `EXTERNAL_ENGINE` and an
  evidence record with zero receipts asserts the computed ledger entry differs from
  (does not simply echo) the manifest's self-reported claim.
- [ ] AC2 (T15-F1-5). The rendered provenance block on the delivered artifact (run report /
  opt-in commit trailer) matches the source manifest's attribution byte-for-byte.
  Check: a test renders the provenance block from a fixture manifest and asserts the
  engine-identity substring equals the manifest's `attribution.identity` field exactly.
- [ ] AC3 (T15-F2-6). `/retro` (or the reconciliation function it calls) flags any manifest
  claiming an `EXTERNAL_ENGINE`-class attribution against a zero-invocation-receipt
  evidence record, and does not flag a manifest whose claim is backed by a matching
  receipt.
  Check: a test with two fixtures — one manifest+evidence pair with a matching receipt
  (no flag expected) and one without (flag expected) — asserts the reconciliation
  function's output differs correctly between the two.
- [ ] AC4 (T15-F6-4). A PR asserting "delegated to X" in its body/commit trailer without a
  corresponding `launched=true`-equivalent proof artifact fails the gate; the same PR
  with the proof artifact present passes.
  Check: a test (or documented manual gate-check invocation) exercising the gate
  function against a delegation-claim-without-proof fixture (fails) and a
  delegation-claim-with-proof fixture (passes).

### Out-of-scope / non-goals
In scope:
- Computing authorship/attribution from evidence for units that already carry a
  manifest and evidence record (agy and any bridge that already emits a
  `launched=true`-equivalent signal).
- Rendering the provenance trailer from the manifest, not inventing a new attribution
  format.
- Wiring the reconciliation check into `/retro` as an additional check, and the PR-gate
  cross-check as an additional gate step — not restructuring `/retro` or the PR gate
  pipeline.

Out of scope (non-goals, deliberately deferred — do not build in this issue):
- A unified cross-bridge `bridge_receipt.v1` invocation-evidence contract spanning
  every delegation bridge (T15-F2-1) — this issue consumes whatever evidence signal a
  bridge already emits; standardizing that signal across bridges is separate,
  larger-blast-radius work.
- A provider-registry receipt guard blocking bridge registration without a
  `receipt_emitter` key (T15-F2-2) — registry-schema enforcement is a different unit of
  work with its own migration path.
- A real-time PreToolUse fail-loud tripwire hook (T15-F2-3) — that is a live-session
  enforcement mechanism, whereas this issue is a post-hoc/PR-boundary reconciliation.
- Cross-bridge append-only chain-of-custody ledgers (T15-F2-8, T15-F1-6-adjacent) — a
  separate, larger evidence-durability theme.
- Backfilling attribution/evidence onto bridges that do not yet emit any
  `launched=true`-equivalent signal — if a bridge has no receipt today, this issue's
  reconciliation check can only report "no evidence available," not retroactively
  invent one.
- Any change to which engine is chaperone vs. gatekeeper — this issue observes and
  reports authorship; it does not change dispatch policy (that is settled by
  `{#external-engines-never-gatekeepers}` and `{#external-engine-chaperone-dispatch}`).

## Grounding References

- T15-F3-5 (primary, absorbed) — "Machine-checked engine-vs-chaperone authorship
  ledger, replacing the manual commit-provenance correction." Basis: the manual
  commit-provenance-correction practice documented at
  `docs/engineering-journal/LEARNINGS.md:305`.
- T15-F1-5 (facet, absorbed) — "Provenance trailer on the delivered artifact, not just
  the sidecar manifest." Basis: `plugins/saga/scripts/provenance_manifest.py:98`/`:376`
  (attribution record required in the manifest but not rendered onto the delivered
  artifact).
- T15-F2-6 (facet, absorbed) — "Provenance-claim vs proof reconciliation in /retro —
  flag manifests that lie about attribution." Basis: the recurring-pain theme 1 in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 6 (silent no-ops in
  delegation & dead wiring, 5+ learnings).
- T15-F6-4 (facet, absorbed) — "Every token attributed: engine-vs-chaperone stamp on
  every committed unit." Basis: same theme-1 grounding, plus the genuine-run evidence
  pattern (`agy_launched=true`) at `docs/engineering-journal/LEARNINGS.md:239`.
- Binding decisions this issue must not violate:
  `{#external-engines-never-gatekeepers}` (#283) — Claude remains verifier-of-record;
  this issue's reconciliation logic runs on the Claude/gate side, never delegated to
  the engine being checked.
  `{#external-engine-chaperone-dispatch}` (#318) — external engines are chaperone
  dispatch only; the ledger reports this distinction, it does not alter it.
- Killed duplicates folded into this issue's scope note (do not re-open as separate
  ideas): T15-F4-3, T15-F5-5 (duplicate authorship-stamp-from-evidence ideas,
  consolidated into T15-F3-5 as canonical).

## Recommended executor profile

- Model: sonnet
- Effort: medium
- Backend: inline
- External-LLM posture: none
- Justification: this is bounded, mechanical wiring against an existing manifest/schema
  (`provenance_manifest.py`, `engine_resolver.py`) plus a small reconciliation function
  and a gate-check test — no open-ended design decision or adversarial judgment call
  that would justify opus/high. Matches the ideation map's own executor_profile
  (`sonnet`/`medium`/`inline`/`none`).

## Release-surface checklist

Complete in the same PR if any plugin-facing behavior, schema, or command changes:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump if `provenance_manifest.py`
      schema or `saga:retro` behavior changes.
- [ ] `.claude-plugin/marketplace.json` — entry updated to match any saga version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the computed-ledger,
      provenance-trailer, `/retro` reconciliation, and PR-gate cross-check additions.
- [ ] Any drift-guard test (marketplace-metadata-vs-plugin.json parity test) still green
      after the version bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording the "authorship computed
      from evidence, not self-report" pattern choice and the rejected alternative
      (trusting the manifest's self-reported attribution field as-is).

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/provenance_manifest.py` — add/extend the computed-authorship
  function consuming evidence alongside the existing attribution record.
- `plugins/saga/scripts/manifest_reader.py` — reconciliation helper reading both
  manifest and evidence for a unit.
- `plugins/saga/skills/retro/` (or equivalent retro reference doc) — wire the
  claim-vs-proof reconciliation check into `/retro`'s existing check list.
- `tests/test_provenance_manifest.py` (new or extended) — byte-for-byte trailer match,
  ledger-vs-self-report discrepancy, reconciliation flag/no-flag fixtures.
- `tests/test_pr_gate_authorship.py` (new, name indicative) — delegation-claim-without-
  proof fails, delegation-claim-with-proof passes.
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface parity per checklist above.

### Verification
```bash
# Ledger computation + trailer byte-match + reconciliation fixtures
uv run pytest tests/test_provenance_manifest.py -v

# PR-gate authorship cross-check
uv run pytest tests/test_pr_gate_authorship.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the ledger test demonstrates a self-reported attribution without
matching evidence is not passed through unchecked, the trailer test demonstrates
byte-for-byte match to the manifest, the reconciliation test demonstrates correct
flag/no-flag behavior on the two fixtures, and the gate test demonstrates a
delegation-claim-without-proof PR fixture fails while the proof-backed fixture passes.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json (ids T15-F3-5,
  T15-F1-5, T15-F2-6, T15-F6-4)
- Source type: ideation survivor map
- Source title: Engine-vs-chaperone authorship: computed ledger, artifact provenance
  trailer, /retro claim-vs-proof report, PR-gate cross-check

### Intent

The fleet already has a manifest format that carries producer attribution (`plugins/saga/scripts/provenance_manifest.py:98`, "Producer attribution: who/what emitted this output (R2)"; `provenance_manifest.py:376` requires an attribution record), and an engine registry that resolves which engine (Claude / codex / agy) ran a unit (`plugins/saga/scripts/engine_resolver.py:15`, `plugins/saga/scripts/execution_spec.py:263-294`). But attribution today is a claim the manifest carries, not a fact the fleet checks:

### Context library links

_none_

### Tests to add or update

- `tests/test_pr_gate_authorship.py`
- `tests/test_provenance_manifest.py`

### Objective

"Gate fleet integrity (agent files, prompts, release surfaces)"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/423
- Number: 423
- Created at: 2026-07-04T08:08:46.737584+00:00

