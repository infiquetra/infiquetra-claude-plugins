---
title: "enhancement: outcome-ingest provenance + structural-drift and idempotent in-flight ingestion"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Ship run-start intent envelope for lifecycle autonomy
---

# enhancement: outcome-ingest provenance + structural-drift and idempotent in-flight ingestion

### Objective
Ship run-start intent envelope for lifecycle autonomy

### Tier
structural

### Wave
wave-1

### Intent

`plugins/saga/scripts/outcome_reconcile.py` (added in #295, "board<->saga reconciliation on resume")
already closes the loop for **field-level** drift on issues the saga already knows about: it detects
`status-drift`, `external-close`, and `external-reopen` for every ledger-bearing issue by diffing
asserted vs. expected vs. live board/issue state
(`plugins/saga/scripts/outcome_reconcile.py:20` doc comment; `DRIFT_KINDS` at
`plugins/saga/scripts/outcome_reconcile.py:78`). Its scope is explicitly ledger-bearing issues only
(KTD6, `plugins/saga/scripts/outcome_reconcile.py:20`) — "an issue with no recorded write is never
read, so a hand-added label the writer never owned can never false-positive."

That scope guard leaves two gaps unaddressed, both raised independently during Gate B ideation
(`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json`, ids `T8-F1-2` and `T8-F5-2`, axis
`objective-ingestion`, both `tier_guess: structural`, both surviving `verdict: survive`):

1. **Structural drift** — an operator or another agent adds a sub-issue to an already-ingested
   Objective *after* the outcome spec was built. There is no `ingest_source` provenance recorded
   anywhere in the spec (`plugins/saga/scripts/outcome_spec.py` `OutcomeSpec`/`Node` — verified: no
   `ingest_source` field exists today) and no detector that notices the live GitHub structure has
   grown beyond the spec's node set. Today this drift is silent and permanent, exactly the pattern
   the repo's own journal calls out as the dominant recurring failure class: "silent no-ops in
   delegation & dead wiring... any bridge/delegation idea needs 'did it actually run/persist'
   verification" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:101-104`) and "provenance/status
   claims must be re-verified against current state"
   (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:105`).
2. **Idempotent ingestion of an already-in-flight Objective** — there is no code path today (verified:
   `grep -rn "ingest" plugins/saga/scripts/*.py` returns no ingestion machinery) that takes a
   pre-existing GitHub Objective/sub-issue tree and derives each node's *initial* live state from
   GitHub reality (closed sub-issue -> `done`, open sub-issue with a linked PR -> `in-flight`) instead
   of defaulting every newly-ingested node to `ready`/`blocked`. Re-running that ingestion a second time
   over the same Objective must be a no-op — not a second write, not a duplicate node, not a changed
   revision. This is the same "derive-on-read over committed state" principle the engine already
   commits to elsewhere (`derive_states` in `plugins/saga/scripts/outcome.py:337`, "No node's state ever
   read from stored scalar (R17)") — recorded as a recurring rejected-alternative pattern in this
   repo's journal (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:109`, "Derive-on-read over
   committed state — recurring rejected alternative").

Both gaps sit in the same file family (`outcome_reconcile.py` for the drift detector,
`outcome_decompose.py`/`outcome_spec.py` for the growth/provenance primitives) and share one grounding
principle (derive-on-read, never silently auto-mutate), which is why they are shipped as one
enhancement rather than two.

### Key decisions

- **Structure-drift is a new `DRIFT_KIND`, not a mutation.** Add `"structure-drift"` alongside the
  existing `"status-drift" / "external-close" / "external-reopen"` in
  `plugins/saga/scripts/outcome_reconcile.py:78`. Detecting it never auto-adds the node — it produces a
  drift record the caller resolves explicitly via `lazy_grow`
  (`plugins/saga/scripts/outcome_decompose.py:120`), which bumps `spec_revision` through the existing
  atomic `_commit` path. This mirrors the existing drift records' "informational, never
  auto-applies" contract (`plugins/saga/scripts/outcome_reconcile.py:237`) — no new mutation semantics
  are invented.
- **Ingest provenance is additive spec metadata, not a new subsystem.** `ingest_source` is recorded
  wherever a node's origin needs to be told apart from a natively-authored node (e.g. "ingested from
  GitHub Objective #NNN at revision X") so the structure-drift comparison has a stable baseline to diff
  against on subsequent detects.
- **Initial state derivation is scoped to ingestion time only.** It reuses the existing derived-on-read
  precedence in `derive_states` (`plugins/saga/scripts/outcome.py:337`) as the model to extend — SUCCESS
  completion -> `done`, terminal-negative -> surfaced not masked, else dispatched/ready/blocked — adding
  the two GitHub-reality inputs (`closed` -> `done`, `open` + linked PR -> `in-flight`/`dispatched`) that
  don't yet exist because there is no ingestion entrypoint to derive them for.
- **Idempotency is enforced by re-derivation, not a run-once flag.** A second ingest over the same
  Objective recomputes the same derived states from the same live GitHub inputs and writes nothing new
  — no sentinel/lock file, consistent with the "no operator-writable status field" rule already
  governing `derive_states` and `outcome_projection.py:88`.

### Definition of Done
- A `structure-drift` `DRIFT_KIND` exists in `outcome_reconcile.py`, detects an added sub-issue absent
  from the ingested node set, and is resolvable only via `lazy_grow` — the detector itself never
  auto-mutates the spec.
- Ingestion derives each new node's initial live state from GitHub reality (closed -> `done`,
  open+PR -> `in-flight`/`dispatched`, plain open -> `ready`/`blocked`) instead of defaulting.
- Re-running ingestion a second time over the same Objective is a verified no-op: no new drift
  record, no duplicate node, no `spec_revision` bump, no additional GitHub write.
- Issues with no `ingest_source` provenance are never flagged for structure-drift, mirroring the
  existing KTD6 ledger-only guard.

### Out-of-scope / non-goals
- Auto-applying a detected structure-drift record (silently adding the sub-issue as a node) — the
  record is always resolved explicitly via `lazy_grow`; never auto-mutating.
- Detecting drift on issues with no ledger/ingest provenance at all — scope stays limited to
  ingest-tracked or ledger-bearing issues, mirroring the existing KTD6 scope guard in
  `outcome_reconcile.py` (an un-provenanced issue must never false-positive).
- Building a general-purpose "import any GitHub issue tree as an outcome spec" wizard/UI — this ships
  the detector + derivation primitives the ingestion path calls, not an end-user ingestion command
  surface (that is a follow-on if requested).
- Removed/deleted sub-issues, renamed Objectives, or cross-repo Objective moves — only the "added
  sub-issue" and "already-in-flight-at-ingest" cases in the two absorbed facets are in scope.
- Changing the existing `status-drift`/`external-close`/`external-reopen` detection semantics —
  those stay exactly as `#295` shipped them.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/outcome_reconcile.py` — add `"structure-drift"` to `DRIFT_KINDS`
  (currently `plugins/saga/scripts/outcome_reconcile.py:78`) and the detector logic that compares the
  ingest-provenance-recorded node set against the live GitHub sub-issue set.
- `plugins/saga/scripts/outcome_spec.py` — add `ingest_source` provenance field to `Node`/`OutcomeSpec`
  (near `plugins/saga/scripts/outcome_spec.py:187` `class Node` and `:361` `outcome_id`).
- `plugins/saga/scripts/outcome_decompose.py` — ingestion helper that derives each new node's initial
  live state from GitHub reality (closed -> done, open+PR -> in-flight) at ingest time, reusing
  `lazy_grow` (`plugins/saga/scripts/outcome_decompose.py:120`) for the resolve-drift path.
- `tests/test_outcome_reconcile.py` — new structure-drift detection tests (fixture: added sub-issue not
  in the ingested node set).
- `tests/test_outcome_decompose.py` — new idempotent-ingestion tests over closed/open/open-with-PR
  fixtures.

### Tests to add or update
- Structure-drift: an added sub-issue (present live, absent from the ingested node set) yields a
  `structure-drift` record; the record is resolvable via `lazy_grow` (bumps `spec_revision`); the
  detector never auto-mutates the spec on its own.
- Idempotent ingestion: a closed sub-issue derives initial state `done`; an open sub-issue with a
  linked PR derives `in-flight`/`dispatched`; a plain open sub-issue derives `ready`/`blocked` per the
  existing `derive_states` frontier rules.
- Idempotency: running the same ingestion a second time over the same Objective is a no-op — no new
  drift record, no duplicate node, no `spec_revision` bump, no additional GitHub write.
- Scope guard: an issue with no `ingest_source` provenance is never flagged for structure-drift
  (mirrors the existing KTD6 ledger-only guard for the other three drift kinds).

### Grounding References
- source_context: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json (ids `T8-F1-2`,
  `T8-F5-2`)
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md (sections 5-6)

### Acceptance criteria
- [ ] An added sub-issue (live GitHub state has a sub-issue absent from the ingested node set) yields a
  `structure-drift` record. Check: `uv run pytest tests/test_outcome_reconcile.py -k structure_drift_added` → passes.
- [ ] A `structure-drift` record is resolvable via `lazy_grow`, which bumps `spec_revision`; the
  detector itself never writes/mutates the spec. Check:
  `uv run pytest tests/test_outcome_reconcile.py -k structure_drift_resolve_lazy_grow` → passes.
- [ ] A closed sub-issue ingested for the first time derives initial state `done`. Check:
  `uv run pytest tests/test_outcome_decompose.py -k ingest_closed_derives_done` → passes.
- [ ] An open sub-issue with a linked PR ingested for the first time derives `in-flight`/`dispatched`.
  Check: `uv run pytest tests/test_outcome_decompose.py -k ingest_open_pr_derives_inflight` → passes.
- [ ] A second ingest over the same already-ingested Objective is a no-op (no new drift record, no
  duplicate node, no `spec_revision` bump). Check:
  `uv run pytest tests/test_outcome_decompose.py -k ingest_idempotent_second_pass` → passes.
- [ ] An issue with no `ingest_source` provenance is never flagged for structure-drift (KTD6-style
  scope guard). Check: `uv run pytest tests/test_outcome_reconcile.py -k structure_drift_scope_guard` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# Targeted reconcile + decompose ingestion tests
uv run pytest tests/test_outcome_reconcile.py tests/test_outcome_decompose.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; structure-drift and idempotent-ingestion tests pass alongside the existing
`status-drift`/`external-close`/`external-reopen` suite with no regressions.

### Release-surface checklist
This changes `saga` plugin behavior (new drift kind, new spec field, new ingestion derivation) — update
in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — matching version/metadata for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting `ingest_source` provenance, the new
  `structure-drift` kind, and idempotent in-flight-Objective ingestion (follow the `#295`-style entry
  format already in the file).
- [ ] Any version/metadata drift-guard test in `tests/` — confirm it still passes with the bumped
  version and updated changelog.

### Executor Profile
- Model: sonnet
- Effort: medium
- Backend: inline
- External LLM: none
- Justification: mechanical extension of an existing, well-understood detector/growth pattern
  (`outcome_reconcile.py` drift kinds, `outcome_decompose.py` `lazy_grow`, `outcome.py` `derive_states`)
  in a single file family with clear existing precedent to mirror — no architectural judgment or
  cross-repo reasoning required above Sonnet at medium effort.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json
- Source type: ideation-survivor
- Source title: Ingest provenance reconcile: structural drift detection and idempotent in-flight Objective ingestion
- Absorbed ids: T8-F1-2 (primary, "Ingest-provenance + `reconcile --from-objective` structural drift guard"), T8-F5-2 (facet, "Goods-receipt reconciliation: ingesting an already-in-flight Objective idempotently")

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/376
- Number: 376
- Created at: 2026-07-04T07:54:00.939942+00:00

