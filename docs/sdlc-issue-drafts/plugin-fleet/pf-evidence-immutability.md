---
title: "capability: content-addressed, append-only evidence ledger (FAIL is never overwritten)"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Build the fleet telemetry and ledger substrate"
wave: wave-2
---

# capability: content-addressed, append-only evidence ledger (FAIL is never overwritten)

## Problem / Motivation

Saga's `/qa` and `/code-review` gates write their durable verdicts as plain markdown files
(`docs/qa/<file>.md`, `docs/reviews/<file>.md`) via ordinary file writes — there is no
write-once or content-addressing guarantee on that path today. `plugins/saga/scripts/qa/SKILL.md`
documents the write at "5.1 Write durable artifact" and `plugins/saga/skills/code-review/SKILL.md`
at "5.3 Write durable artifact"; neither cites a clobber-guard. This is a grounded, previously
observed failure, not a hypothetical: the grounding brief records "a probe script overwriting a
FAIL evidence artifact with a later PASS (audit chain-of-custody)"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151`, restated in §7 singletons and
carried to §8's direct-to-candidate pool as "evidence-artifact immutability",
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:186`). The brief's theme-6 recurring pain
list independently names "provenance/status claims must be re-verified against current state"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:105`) as a 4-learning recurring pattern —
this issue is the mechanism-level fix for both.

The repo already has the *pattern* this issue extends, just not on the evidence-artifact path:
`plugins/saga/scripts/outcome_store.py:203-210` implements `_write_once()` — "Create `path`
atomically, refusing to clobber an existing file... the write-once / immutability guarantee for
completion events" — using temp-file + `os.link`. `_atomic_write()` at
`plugins/saga/scripts/outcome_store.py:195-200` is the existing atomic-replace primitive it builds
on. `plugins/saga/scripts/manifest_store.py:119-127` (`write_manifest`) is a second precedent that
reuses `outcome_store._atomic_write` for structured JSON writes. None of these three call sites are
wired into the `/qa` or `/code-review` artifact-write step, and none append a custody trail (they
overwrite-in-place by design, appropriately, for their own use case — leases and manifests are
mutable-by-contract; evidence verdicts are not).

## Definition of Done

- `plugins/saga/scripts/evidence_ledger.py` exists, providing:
  - a content-addressed write helper (hash each verification artifact's content; refuse an
    in-place overwrite of an existing hash-addressed entry, per H-F1-6 / H-F5-3 / S-17),
  - an append-only custody log (JSONL) recording `{hash, producer, timestamp, verdict}` per write
    (per H-F5-3 / T7-F3-5),
  - a pre-registered criteria block frozen at intent-capture time so the pass/fail contract for a
    given run cannot be redefined by a later attempt (per T7-F5-5),
  - a closure-time verify step that re-hashes an artifact and HALTs (rather than silently passing)
    if the bytes on disk don't match the ledger's recorded hash, and that refuses to accept a
    producer self-certifying its own verdict without a distinct verifier role (per T7-F5-6).
- `/qa`'s durable-artifact write step (`plugins/saga/skills/qa/SKILL.md`, "5.1 Write durable
  artifact") and `/code-review`'s durable-artifact write step
  (`plugins/saga/skills/code-review/SKILL.md`, "5.3 Write durable artifact") are wired through
  `evidence_ledger.py` instead of a bare file write.
- Merged, with `tests/test_evidence_ledger.py` proving: a second write of the same logical
  artifact cannot clobber the first; a FAIL-then-PASS sequence preserves both records with the
  PASS surfacing the prior FAIL as a supersession, not a silent green; the custody chain verifies
  end to end and a tamper (mutated bytes on disk) HALTs closure instead of passing.

### Acceptance criteria
One per absorbed facet, minimum:

- [ ] **No clobber on re-write (H-F1-6, H-F5-3, S-17).** Writing a second logical artifact under the
   same identity as an existing one is rejected by the ledger — it does not overwrite the first
   write. Check: `uv run pytest tests/test_evidence_ledger.py -k no_clobber` → passes.
- [ ] **Custody chain validates end to end (H-F5-3).** Given a sequence of ledger writes, a
   `verify_chain()` call reconstructs and validates the full custody log; an overwrite attempt is
   rejected by a dedicated test. Check: `uv run pytest tests/test_evidence_ledger.py -k
   custody_chain_validates` → passes.
- [ ] **FAIL is never overwritten by a later PASS; supersession is surfaced (T7-F3-5).** Writing PASS
   after an existing FAIL for the same check+SHA preserves the FAIL record unchanged in the JSONL
   log, and a reader (`latest-per-(check,sha)`) flags the FAIL→PASS transition as a supersession
   rather than only returning the latest verdict silently. Check: `uv run pytest
   tests/test_evidence_ledger.py -k fail_then_pass_supersession` → passes.
- [ ] **Pre-registered criteria are frozen at intent capture (T7-F5-5).** The pass/fail criteria
   block for a run is written once, before the run's first attempt, and is immutable across
   subsequent attempts of that same run; an attempt-1 FAIL followed by an attempt-2 PASS leaves
   both attempt records persisted and the criteria block byte-identical between attempts. Check:
   `uv run pytest tests/test_evidence_ledger.py -k criteria_frozen_across_attempts` → passes.
- [ ] **Closure HALTs on tamper (T7-F5-6).** Given a ledger entry whose on-disk artifact bytes are
   mutated after the write, a closure-time verify step detects the hash mismatch and HALTs
   (returns a non-zero / typed-failure result) instead of treating the artifact as valid. Check:
   `uv run pytest tests/test_evidence_ledger.py -k closure_halts_on_tamper` → passes.
- [ ] **Producer cannot self-certify (T7-F5-6).** A write attributed to the same actor role as the
   verifier for that check is rejected or flagged — the ledger records and can enforce a
   producer/verifier role distinction. Check: `uv run pytest tests/test_evidence_ledger.py -k
   producer_cannot_self_certify` → passes.
- [ ] **`/qa` and `/code-review` write through the ledger (H-F1-6).** Both skills' durable-artifact
   write steps call `evidence_ledger.py` rather than a bare file write; an end-to-end test drives
   each skill's write path and asserts the resulting artifact is present in the ledger's custody
   log. Check: `uv run pytest tests/test_evidence_ledger.py -k qa_and_code_review_write_through` →
   passes.
- [ ] **Full suite, format, lint, types stay green.** Check: `uv run pytest && uv run ruff format
   --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
   --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
In scope:
- A single new module, `evidence_ledger.py`, covering content-addressed write, append-only
  custody log, frozen pre-registered criteria, and closure-time tamper verification.
- Wiring `/qa` and `/code-review`'s existing durable-artifact write steps through that module.
- Tests proving each acceptance criterion above.

Out of scope (do not build in this issue):
- Backfilling ledger coverage onto any other saga artifact-write path (e.g., `outcome_store.py`
  leases/manifests, `manifest_store.py` manifests, `saga_spore.py`, `reversibility_certificate.py`)
  — those are separate, already-atomic, mutable-by-contract writes and are explicitly not the
  target of this issue. A future issue may extend ledger coverage to them; this one does not.
- Any new UI, dashboard, or CLI surface for browsing the custody log — this issue ships the
  library and its two call sites, not an operator-facing viewer.
- Changing `/qa` or `/code-review`'s verdict logic, severity model, or report format — only the
  write mechanism changes; the artifact content and skill behavior are otherwise unchanged.
- Any change to `outcome_store._write_once` or `_atomic_write` themselves — this issue is additive
  (a new module that may internally reuse or mirror these primitives) and must not alter their
  existing call sites or contracts.
- Retroactively re-hashing or migrating any evidence artifacts already on disk prior to this
  change — coverage starts at merge time, forward-only.

## Grounding References

- **H-F1-6** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`) — "Content-addressed,
  append-only evidence: verification artifacts that cannot be quietly rewritten." Primary role.
- **H-F5-3** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`) — "Chain-of-custody
  evidence ledger with content-addressed immutability." Basis: grounding brief §7 singleton (the
  probe-overwrite-FAIL-with-PASS incident) plus §6 pattern 2 (provenance re-verification) and
  reinforces §6 pattern 5 (derive-on-read). Dedup-merged.
- **S-17** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`) — "Evidence-artifact
  chain-of-custody (no overwrite)." Basis: grounding brief §8 direct-to-candidate pool entry
  "evidence-artifact immutability" and the same §7 probe-overwrite singleton. Dedup-merged.
- **T15-F1-6** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`) — "Write-once
  evidence artifacts — a later PASS must never overwrite an earlier FAIL." Dedup-merged; folded
  into acceptance criterion 3.
- **T7-F5-6** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`) — "Content-addressed
  evidence custody chain: closure verifies the seal and HALTs on tamper." Dedup-merged; folded
  into acceptance criteria 5 and 6.
- **T7-F3-5** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`) — "Evidence is an
  append-only ledger, not a file you overwrite." Primary role; folded into acceptance criterion 3.
- **T7-F5-5** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`) — "Pre-registered
  pass criteria: freeze the gate's evidence contract before the run so a later PASS cannot
  overwrite a FAIL." Facet role; folded into acceptance criterion 4.
- Binding decisions this builds on: `docs/engineering-journal/DECISIONS.md:960` (append-only
  canonical log pattern already established for the saga engine) and the derive-on-read principle
  restated at `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:109` (§6 pattern 5) — this
  issue's ledger is additive append-only storage that downstream readers derive latest-verdict
  from, not a mutable status field.
- Existing code precedent to reuse or mirror (not to modify): `_write_once` and `_atomic_write` in
  `plugins/saga/scripts/outcome_store.py:195-210`; `write_manifest` in
  `plugins/saga/scripts/manifest_store.py:119-127`.

## Recommended Executor Profile

- Model: Sonnet
- Effort: medium
- Backend: inline
- External LLM: none
- Justification: this is a self-contained, mechanically well-specified library module plus two
  call-site rewires within a single repo, with existing atomic-write primitives to reuse as a
  pattern. It does not require cross-repo reasoning, adversarial judgment, or external-model
  consultation, so it stays at Sonnet/medium rather than escalating to Opus or a higher effort
  tier.

## Release-Surface Checklist

This issue changes saga plugin behavior (a new artifact-write contract on `/qa` and
`/code-review`). Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump and changelog-relevant description
      update if the plugin's public behavior summary references artifact-write guarantees.
- [ ] `.claude-plugin/marketplace.json` — saga plugin version entry kept in sync with the bump
      above.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new evidence-ledger write path for
      `/qa` and `/code-review`.
- [ ] Any version/metadata drift-guard tests (e.g., a marketplace/plugin.json consistency test in
      `tests/`) re-run and passing after the bump.

### Verification
```bash
# New ledger module unit tests
uv run pytest tests/test_evidence_ledger.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && \
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the no-clobber, custody-chain, FAIL-preservation, frozen-criteria,
tamper-HALT, and self-certification tests all pass.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/ (ids H-F1-6, H-F5-3, S-17,
  T15-F1-6, T7-F5-6, T7-F3-5, T7-F5-5)
- Source type: ideation survivor set / issue-map
- Source title: Content-addressed append-only verification evidence: custody log, pre-registered
  pass criteria, FAIL never overwritten

### Intent

Saga's `/qa` and `/code-review` gates write their durable verdicts as plain markdown files (`docs/qa/<file>.md`, `docs/reviews/<file>.md`) via ordinary file writes — there is no write-once or content-addressing guarantee on that path today. `plugins/saga/scripts/qa/SKILL.md` documents the write at "5.1 Write durable artifact" and `plugins/saga/skills/code-review/SKILL.md` at "5.3 Write durable artifact"; neither cites a clobber-guard. This is a grounded, previously observed failure, not a hypothetical: the grounding brief records "a probe script overwriting a FAIL evidence artifact with a later PASS (audit chain-of-custody)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151`, restated in §7 singletons and carried to §8's direct-to-candidate pool as "evidence-artifact immutability", `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:186`). The brief's theme-6 recurring pain list independently names "provenance/status claims must be re-verified against current state" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:105`) as a 4-learning recurring pattern — this issue is the mechanism-level fix for both.

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/qa/SKILL.md`
- `plugins/saga/skills/code-review/SKILL.md`
- `plugins/saga/scripts/evidence_ledger.py`
- `plugins/saga/skills/qa/SKILL.md`
- `tests/test_evidence_ledger.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`

### Tests to add or update

- `tests/test_evidence_ledger.py`

### Objective

"Build the fleet telemetry and ledger substrate"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/398
- Number: 398
- Created at: 2026-07-04T08:01:09.078712+00:00

