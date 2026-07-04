---
title: "capability: saga multi-repo arc — one /outcome DAG spanning repos with per-repo saga state"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan, saga
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Expand saga+deploy capability breadth (misc/quick-wins)"
wave: wave-3
---

# capability: saga multi-repo arc — one /outcome DAG spanning repos with per-repo saga state

### Intent
Today an `/outcome` DAG and every saga underneath it are pinned to exactly one repo's working
tree. Give the DAG a per-node repo identity so a single outcome can coordinate leaves that live
in two or more repos, with each leaf's saga state, git operations, and journal reads scoped to
its own repo — while the DAG's derived-on-read status still aggregates correctly across the
repo boundary.

## Problem Frame

The engine's core abstraction — `Saga` — was designed to carry a long arc with many subplots,
but the record and the surrounding machinery bind to exactly one repository at a time:

- `Saga.issue_ref` is a single `owner/repo#N` string
  (`plugins/saga/scripts/saga.py:183`; documented as the `owner/repo#N` pointer in
  `plugins/saga/references/saga-spec.md:126`). One saga, one repo, one issue.
- The `/outcome` DAG's node schema (`Node` in `plugins/saga/scripts/outcome_spec.py:187-222`)
  carries `leaf_saga_id`, `child_spec_ref`, `backend`, `depends_on`, `sandbox`, and several
  other per-node fields, but **no repo identity at all** — there is no `repo` / `repo_root`
  field on `Node`.
- `repo_root` is threaded as a single global `Path` through the entire outcome engine: spec
  storage (`plugins/saga/scripts/outcome.py:131-159`), git operations
  (`plugins/saga/scripts/outcome.py:170-230`), store materialization
  (`plugins/saga/scripts/outcome.py:235-236`), and the CLI entry point's `--repo-root` argument
  (`plugins/saga/scripts/outcome_projection.py:114-121`). Every helper that touches git or the
  spec file assumes one working tree.
- The board-sync ledger already groups records by `(repo, number)`
  (`plugins/saga/scripts/outcome_reconcile.py:105-116`), which shows the board-side reconciler
  can already reason about more than one repo per outcome — but the DAG spec and dispatch layer
  that feed it cannot yet *originate* nodes in more than one repo.

This is a pre-existing, explicitly named gap: QUEUED anchor
`{#saga-multi-repo-arc}` ("Saga arc binds one repo only — saga carry multiple repo subplots",
`docs/engineering-journal/QUEUED.md:331-346`) states the same verified evidence (single
`issue_ref`, single-working-tree `current_git_state`, single-repo `journal_entries` and
`prior_prs`) and the same target shape: "let one saga arc carry a SET of subplots, each with its
own `issue_ref` / PR / `/work` branch, per-subplot git/PR/journal" (back-compat: a subplot-of-one
stays valid). The grounding brief's binding-decision register additionally constrains how this
must be built: `/outcome`'s existing campaign (U1-U11) requires derived-on-read status (never a
committed status field), HALT-not-degrade on ambiguity, and a leaf-produced cost ledger — this
capability must extend that architecture, not bypass it
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, binding-decision register, row
"`/outcome` campaign (U1–U11)").

## Definition of Done

A merged extension to the `/outcome` DAG spec, dispatcher, and reconciler that lets an outcome
carry leaf nodes in two or more repos, each with its own repo-scoped saga state (own
`issue_ref`, own git working tree, own journal reads), while the DAG's derived-on-read status
aggregation still produces one correct consolidated view across the repo boundary. Concretely:

- `Node` gains an explicit per-node repo identity (e.g. a `repo_root` / `repo` field), validated
  by `OutcomeSpec.validate` the same way other node fields are validated today
  (`plugins/saga/scripts/outcome_spec.py:236-276`).
- The dispatcher (`plugins/saga/scripts/outcome_dispatcher.py`) resolves each node's git
  operations, store paths, and dispatched leaf saga against *that node's* repo, not the single
  global `repo_root` used everywhere today.
- The reconciler / projection layer (`outcome_reconcile.py`, `outcome_projection.py`,
  `outcome_report.py`) aggregates status across all repos represented in the DAG without
  assuming a single working tree, consistent with the existing `(repo, number)`-keyed grouping
  already present in `outcome_reconcile.py:105-116`.
- Single-repo outcomes continue to work unchanged (back-compat: a DAG with all nodes in one repo
  behaves exactly as it does today).
- A fixture-based test proves a two-repo arc: start an outcome with leaves in repo A and repo B,
  advance the ready frontier, and assert the derived-on-read status aggregates correctly across
  both repos.

### Acceptance criteria
- [ ] **AC1 (repo identity on Node).** `Node` carries an explicit repo field; `OutcomeSpec.validate`
  rejects a node with an empty/malformed repo identity the same way it rejects a malformed
  `subplot_id` today (`plugins/saga/scripts/outcome_spec.py:236-276`).
  Check: `uv run pytest tests/test_outcome_spec.py -k node_repo_identity` → passes.
- [ ] **AC2 (per-node git scope).** Dispatching a leaf whose node declares repo B performs its git
  operations (branch state, working tree) against repo B's checkout, not the outcome's own
  `repo_root`.
  Check: `uv run pytest tests/test_outcome_dispatcher.py -k dispatch_uses_node_repo` → passes.
- [ ] **AC3 (per-repo saga state, back-compat).** A leaf saga dispatched under a multi-repo outcome
  still writes a normal single-repo `Saga` record with its own `issue_ref` scoped to its node's
  repo; an existing single-repo outcome's leaves are byte-for-byte unaffected.
  Check: `uv run pytest tests/test_saga.py -k issue_ref_backcompat` → passes.
- [ ] **AC4 (two-repo arc advances and aggregates — the seed's own DoD sketch).** A fixture-based
  test starts an outcome with two nodes in two different repos, advances the ready frontier, and
  asserts the derived-on-read status aggregates correctly across the repo boundary (no committed
  status field is introduced — status stays derived-on-read per the binding `/outcome` campaign
  decision).
  Check: `uv run pytest tests/test_outcome_multi_repo.py -k two_repo_arc_status` → passes.
- [ ] **AC5 (reconciler multi-repo aggregation).** The reconciler's board-sync ledger grouping by
  `(repo, number)` (`plugins/saga/scripts/outcome_reconcile.py:105-116`) is exercised by a DAG
  whose nodes span more than one repo, and produces one consolidated attention/status view, not
  a per-repo fragment.
  Check: `uv run pytest tests/test_outcome_reconcile.py -k multi_repo_ledger` → passes.
- [ ] **AC6 (report/graph rendering stays correct).** `outcome_report.report_markdown` /
  `graph_mermaid` render a multi-repo DAG without crashing or silently dropping cross-repo edges,
  and the rendered node table shows each node's repo.
  Check: `uv run pytest tests/test_outcome_report.py -k multi_repo_render` → passes.
- [ ] **AC7 (full suite stays green).**
  Check: `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:** the `Node` schema, `OutcomeSpec.validate`, the dispatcher's git/store resolution,
and the reconciler/projection/report layer's status aggregation — enough to let one outcome DAG
span ≥2 repos correctly, per node.

**Out of scope / non-goals:**
- Rewriting `Saga.issue_ref` itself to hold multiple repos in one record — this issue keeps
  "one saga, one repo" (the existing model) and instead gives the *outcome DAG* the multi-repo
  reach; a saga-record schema change (as sketched more ambitiously in
  `{#saga-multi-repo-arc}`) is a separate, larger effort and explicitly deferred.
- Cross-repo transactional guarantees (e.g. atomic multi-repo commit/rollback) — each repo's
  git operations remain independent; the DAG only coordinates sequencing and status, not
  cross-repo atomicity.
- Any change to `/outcome`'s degrade/backend-menu policy, cost-ledger shape, or HALT semantics —
  this issue extends the existing U1-U11 architecture, it does not revisit those decisions.
- New CLI surface for cross-repo credential/auth handling — assumes the operator's existing
  per-repo git access already works; no new auth flow is introduced.
- Team-execution's own per-teammate/per-repo dispatch model — this issue is scoped to the saga
  `/outcome` engine only.

## Grounding References

- Absorbed idea `S-4` (seed, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`,
  `id: "S-4"`, theme `NEW:multi-repo-arc`) — basis: QUEUED anchor `{#saga-multi-repo-arc}`,
  grounding brief §5. Its own DoD sketch: "Merged extension letting an `/outcome` DAG carry
  leaves in ≥2 repos with per-repo saga state. Verify: start an arc with two repos, advance the
  frontier, and assert derived-on-read status aggregates correctly across repo boundaries." —
  reproduced verbatim as AC4 above.
- QUEUED anchor `{#saga-multi-repo-arc}` (`docs/engineering-journal/QUEUED.md:331-346`) — the
  full pre-existing seed this issue formalizes: verified single-repo binding at
  `plugins/saga/scripts/saga.py:154` (`issue_ref`), `saga.py:472-478` (`current_git_state`),
  `saga.py:924-927` (`journal_entries`), `saga.py:881` (`prior_prs`/`aggregate_context`); notes
  that saga state storage already floats above one repo (`root = Path.cwd()` under
  `.claude/saga/`, `saga.py:1126,44`), so the refactor is a record-schema + execution-layer
  change, not a storage-location change.
- Binding decision: `/outcome` campaign (U1-U11) — derived-on-read status, never committed
  status fields; HALT-not-degrade; backend menu off-by-default with host-conditional degrade;
  cost ledger = leaf-produced fact (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`,
  §2 binding-decision register). This issue's status-aggregation work (AC4, AC5) must comply
  with derived-on-read; it must not introduce a committed cross-repo status field.
  Revisit-when: none stated for this row — it is a standing architectural constraint.
  Cross-ref lifecycle-engine-merge initiative:
  `docs/engineering-journal/DECISIONS.md#work-engine-rebuild`.
  Companion QUEUED item (same "richer per-repo/per-teammate execution" family, not part of this
  issue): `{#team-execution-per-teammate-effort}`.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none (no external-engine participation; this is a schema + engine
  change to code Claude is verifier-of-record for, per `{#external-engines-never-gatekeepers}`).
- **Justification:** sonnet/high is appropriate — this is a well-scoped schema-extension and
  engine-plumbing change with a clear existing pattern to extend (the `Node` validation model
  already exists; this adds one field and threads it through git/dispatch/reconcile call sites)
  rather than a novel-design or adversarial-review task that would warrant opus.

## Release-Surface Checklist

This changes `/outcome` DAG spec behavior (a new `Node` field, new dispatcher/reconciler
semantics), so the following must land in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + changelog pointer for the
  `Node` schema addition.
- [ ] `.claude-plugin/marketplace.json` — saga plugin entry version/description kept in sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the new per-node repo field and multi-repo
  DAG support, with back-compat note (single-repo DAGs unaffected).
- [ ] `plugins/saga/references/saga-spec.md` — the `owner/repo#N` / `issue_ref` boundary table
  and node schema documentation updated to reflect per-node repo scoping.
- [ ] Any drift-guard test that asserts `Node` field completeness or `outcome-spec.json` schema
  shape (e.g. round-trip / unknown-key tests) updated to include the new field.
- [ ] `docs/engineering-journal/QUEUED.md` — `{#saga-multi-repo-arc}` entry marked resolved/moved
  to `DECISIONS.md` per the shared engineering-journal practice, in the same commit that ships
  this change.

## Files Expected to Change

- `plugins/saga/scripts/outcome_spec.py` — add per-node repo field + validation.
- `plugins/saga/scripts/outcome_dispatcher.py` — resolve git/store operations per-node repo.
- `plugins/saga/scripts/outcome_reconcile.py` — confirm/extend multi-repo `(repo, number)`
  ledger aggregation already present at `:105-116`.
- `plugins/saga/scripts/outcome_projection.py` / `outcome_report.py` — render multi-repo DAG
  status and graph correctly.
- `plugins/saga/references/saga-spec.md` — document the per-node repo field.
- `tests/test_outcome_spec.py`, `tests/test_outcome_dispatcher.py`,
  `tests/test_outcome_reconcile.py`, `tests/test_outcome_report.py`,
  `tests/test_outcome_multi_repo.py` (new) — coverage for AC1-AC6.

## Tests to Add or Update

- New: `tests/test_outcome_multi_repo.py` — fixture-based two-repo arc (start, advance frontier,
  assert aggregated derived-on-read status) — covers AC4.
- `tests/test_outcome_spec.py` — node repo-identity validation (AC1).
- `tests/test_outcome_dispatcher.py` — dispatch resolves node-specific repo for git/store ops
  (AC2).
- `tests/test_saga.py` — back-compat: existing single-repo `issue_ref` sagas unaffected (AC3).
- `tests/test_outcome_reconcile.py` — multi-repo ledger aggregation (AC5).
- `tests/test_outcome_report.py` — multi-repo render (AC6).

### Verification
```bash
# Targeted: multi-repo DAG fixture (the seed's own DoD check)
uv run pytest tests/test_outcome_multi_repo.py -v

# Node schema + dispatcher + reconciler + report coverage
uv run pytest tests/test_outcome_spec.py tests/test_outcome_dispatcher.py \
  tests/test_outcome_reconcile.py tests/test_outcome_report.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the multi-repo fixture test demonstrates a two-repo arc advancing its ready
frontier with correctly aggregated derived-on-read status, and every pre-existing single-repo
outcome test still passes unchanged.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (id `S-4`)
- Source type: seed (survivor of `saga:ideate`, absorbed into issue map)
- Source title: Saga multi-repo arc (one outcome DAG spanning repos)

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/scripts/outcome_dispatcher.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/saga-spec.md`
- `docs/engineering-journal/QUEUED.md`

### Tests to add or update

- `tests/test_outcome_dispatcher.py`
- `tests/test_outcome_multi_repo.py`
- `tests/test_outcome_reconcile.py`
- `tests/test_outcome_report.py`
- `tests/test_outcome_spec.py`
- `tests/test_saga.py`

### Objective

"Expand saga+deploy capability breadth (misc/quick-wins)"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/460
- Number: 460
- Created at: 2026-07-04T08:26:05.949273+00:00

