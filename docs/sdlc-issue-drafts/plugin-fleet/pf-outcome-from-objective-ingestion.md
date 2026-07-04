---
title: "capability: /outcome start --from-objective — seed the DAG from a parent Objective with edge inference and provenance stamps"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Ship run-start intent envelope for lifecycle autonomy"
wave: wave-1
---

# capability: /outcome start --from-objective — seed the DAG from a parent Objective with edge inference and provenance stamps

## Objective

Ship run-start intent envelope for lifecycle autonomy (`Objective: Ship run-start intent
envelope for lifecycle autonomy`, wave-1).

## Problem / motivation

Today `/outcome start` cannot seed its DAG from an existing GitHub Objective (a parent issue
with sub-issues) at all:

- `plugins/saga/scripts/outcome.py:244-267` (`start()`) accepts only a bare `objective` string
  and an optional `nodes` list; when `nodes` is omitted it falls back to a hardcoded
  `_starter_nodes()` two-node design→build skeleton (`outcome.py:270-274`). There is no
  `--from-objective` path anywhere in the CLI surface
  (`outcome.py:1087-1170`, the full `add_subparsers`/`add_argument` wiring for `start` takes
  only `outcome_id` and `objective` positionals).
- The GitHub-side reader this issue needs already exists but is unwired:
  `plugins/saga/scripts/discover_subissues.py` runs a working `SubIssues` GraphQL query
  (`:11-32`) against `gh api graphql` and normalizes parent + sub-issue `number`/`title`/
  `state`/`url`/`labels`/`assignees` (`:63-90`) — but nothing calls it from `outcome.py`, and
  it is invoked only as a standalone CLI (`:93-108`), never as an ingestion library function.
- The `Node` dataclass already carries the provenance slot this issue needs to populate:
  `plugins/saga/scripts/outcome_spec.py:187-221` documents `github: dict[str, Any]` as an
  "open pass-through map whose detailed schema lands in the units that consume them" — and two
  consumers already read it defensively today, proving the wiring is load-bearing the moment
  it is populated: `plugins/saga/scripts/outcome_reconcile.py:282` and
  `plugins/saga/scripts/outcome_board_sync.py:257` both do
  `node.github.get("issue", "") or node.github.get("sub_issue", "")` to resolve which GitHub
  issue a node tracks. Both currently degrade to an empty string on any ingested node because
  nothing writes `node.github` from an ingestion path yet.
- No edge-inference exists either: `Node.depends_on` (`outcome_spec.py:212`) is populated only
  by hand-authored specs or `_starter_nodes()`'s literal `["design"]`; there is no mapper from
  GitHub's blocked-by/tracked-by relationships to `depends_on` edges, and no cycle handling for
  one.
- The grounding brief records this precise gap directly: "`/outcome start` = 2-node starter
  DAG, but `outcome_decompose.py` (U7) is the real decomposition path — just not at start-time
  and not from an existing GitHub Objective. No ingestion path confirmed."
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:28-30`, correction (h)).
- The binding `/outcome` campaign decision register applies directly and must not be
  contradicted: "Derived-on-read status, never committed status fields; HALT-not-degrade;
  backend menu off-by-default with host-conditional degrade; cost ledger = leaf-produced fact"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`, `/outcome` campaign U1–U11 row).
  This issue's ingestion writes structural spec state only (nodes, `depends_on`, `github`
  stamps) — it must not invent a committed status field or bypass the existing derived-state
  machinery.

Net effect: an operator with a GitHub Objective issue and its sub-issues already filed has no
way to seed an `/outcome` run from that structure — they must hand-author the DAG from
scratch, re-typing what GitHub already tracks, and any node they do create by hand has no
`github` provenance stamp, so `outcome_reconcile.py` drift detection and
`outcome_board_sync.py` board-status sync silently no-op on it.

## Definition of Done

A merged PR that:

1. Wires `discover_subissues.py`'s existing GraphQL reader into `/outcome start
   --from-objective <owner>/<repo>#<number>` (or equivalent CLI shape — exact flag surface is
   `/plan`'s to determine), producing an `OutcomeSpec` whose nodes are seeded 1:1 from the
   parent issue's sub-issues.
2. Adds a pure `edges_from_relationships()` mapper that derives `Node.depends_on` edges from
   GitHub blocked-by/tracked-by relationships among the ingested sub-issues, dropping (and
   reporting, not silently discarding) any cyclic pair rather than producing an invalid DAG.
3. Stamps `node.github = {repo, issue, sub_issue}` on every ingested node so the two existing
   consumers that already read it defensively (`outcome_reconcile.py:282`,
   `outcome_board_sync.py:257`) receive real provenance instead of falling through to the
   empty-string branch.
4. Maps each sub-issue's GitHub label(s) to the ingested node's `kind` (`NODE_KINDS = ("code",
   "non-code")`, `outcome_spec.py:56`), and seeds a closed sub-issue's node in an
   already-satisfied state consistent with `TERMINAL_STATES`
   (`outcome_spec.py:77`, e.g. `"done"`) rather than the default `"pending"`
   (`outcome_spec.py:201`).
5. Is verified by tests asserting every acceptance criterion below, run against a fixture
   GraphQL response (no live network call in the test suite).
6. Does not change `outcome_decompose.py` (U7), `_starter_nodes()`'s existing no-flag
   behavior, `outcome_reconcile.py`/`outcome_board_sync.py`'s existing read logic, or any
   committed-status semantics — this issue is additive: a new ingestion path that feeds the
   existing spec/reconcile/board-sync machinery, not a redesign of it.

### Acceptance criteria
- [ ] **AC1 (T8-F1-1, primary).** `/outcome start --from-objective` produces an `OutcomeSpec`
      that passes `OutcomeSpec.validate()`. Test: fixture-GraphQL test asserting the produced
      spec validates cleanly.
- [ ] **AC2 (T8-F1-1).** Ingested node count equals the parent issue's sub-issue count. Test:
      fixture GraphQL response with N sub-issues → produced spec has exactly N nodes.
- [ ] **AC3 (T8-F1-1).** Each ingested node's `kind` is derived from its sub-issue's GitHub
      label(s) rather than defaulting silently. Test: a fixture sub-issue labeled `non-code`
      (or equivalent) yields a node with `kind == "non-code"`; an unlabeled/`code`-labeled
      sub-issue yields `kind == "code"`.
- [ ] **AC4 (T8-F1-1).** A closed sub-issue seeds its node pre-completed rather than
      `"pending"`. Test: a fixture sub-issue with `state: CLOSED` yields a node whose `state`
      is a member of `TERMINAL_STATES` (`outcome_spec.py:77`), not the default `"pending"`.
- [ ] **AC5 (T8-F2-2, primary facet).** A linear chain of blocked-by/tracked-by relationships
      among sub-issues yields corresponding `depends_on` edges. Test: a fixture linear chain
      (A blocks B blocks C) produces nodes whose `depends_on` reflects that ordering.
- [ ] **AC6 (T8-F2-2).** A cyclic relationship pair is dropped from the produced edges and
      reported (not silently discarded, not left in the spec to fail `validate()`'s
      self-dependency/cycle checks downstream). Test: a fixture cyclic pair (A blocks B, B
      blocks A) produces a spec with no cycle and a reported/logged drop for the pair.
- [ ] **AC7 (T8-F4-7, facet).** An ingested node's `node.github` stamp is consumed by
      `outcome_reconcile.py`'s drift detection without further wiring. Test: an ingested node
      whose GitHub-side issue closes as `not_planned` surfaces as a drift record via the
      existing `detect()` path (`outcome_reconcile.py:219`), reading `node.github.get("issue")`
      / `node.github.get("sub_issue")` (`:282`) populated by this issue's ingestion.
- [ ] **AC8 (T8-F4-7).** An ingested node's `node.github` stamp is consumed by
      `outcome_board_sync.py`'s status sync without further wiring. Test: an ingested node
      entering the dispatch frontier has its board Status set via the existing
      `reconcile_board()` path (`outcome_board_sync.py:177`), reading the same
      `node.github.get("issue")` / `node.github.get("sub_issue")` fallback (`:257`) populated
      by this issue's ingestion.
- [ ] **AC9 (S-23, dedup-merged seed).** Feeding a parent issue with 3 sub-issues produces 3
      leaves under the parent's ingested DAG with correct dependency edges (the end-to-end
      shape the seed asked for). Test: an end-to-end fixture test with a 3-sub-issue parent
      asserts 3 nodes + edges matching the fixture's declared relationships.

### Out-of-scope / non-goals
- **In scope:** wiring `discover_subissues.py` into `/outcome start`, the
  `edges_from_relationships()` mapper, `node.github` provenance stamping, kind-from-label
  mapping, closed-sub-issue pre-completion, and tests for all of the above against fixture
  GraphQL data.
- **Out of scope / non-goals:**
  - Changing `outcome_decompose.py` (U7) or its existing mid-run decomposition flow — this
    issue is a run-*start* ingestion path; U7 stays the mechanism for growing a DAG after
    start.
  - Changing `_starter_nodes()`'s existing no-flag two-node default — `/outcome start` without
    `--from-objective` continues to behave exactly as today.
  - Redesigning `outcome_reconcile.py`'s drift-detection logic or `outcome_board_sync.py`'s
    status-sync logic — both already read `node.github` defensively; this issue populates that
    field, it does not touch the consumers' internals.
  - A generic non-GitHub relationship-graph importer — v1 is scoped to the GitHub blocked-by/
    tracked-by relationships `discover_subissues.py`'s query already exposes (or a minimal
    query extension to expose them); no other issue-tracker integration.
  - Any change to committed status fields or the derived-on-read model — ingestion only
    writes structural spec state (nodes, `depends_on`, `github`), never a committed status
    field, per the binding `/outcome` campaign decision.
  - Reconciling a *changed* Objective structure after the initial ingest (e.g. a sub-issue
    added to the parent post-start) — that is `reconcile --from-objective` drift-guard
    territory (a related, separately-scoped concern), not this issue's one-shot seed path.

## Grounding References

- **T8-F1-1** (primary) — "Wire existing sub-issue reader into `/outcome start
  --from-objective`" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json`).
  DoD sketch: "Merged PR wiring `discover_subissues` into `start --from-objective`; verified by
  fixture-GraphQL test asserting produced spec `validate()`s, node count == sub-issue count,
  kind-from-label mapping, closed sub-issues seed pre-completed, `node.github` binds its ref."
- **T8-F2-2** (facet) — "Auto-derive `depends_on` edges from GitHub blocked-by/tracked-by
  relationships" (same survivors file, `basis_type: reasoned`). DoD sketch: "Merged PR
  extending the GraphQL query with `trackedIssues`/timeline cross-refs + a pure
  `edges_from_relationships()` mapper feeding the seeder; verified by a two-fixture test
  (linear chain yields `depends_on` edges; cyclic pair dropped-and-reported)."
- **T8-F4-7** (facet) — "Ingestion provenance stamps that make reconcile and board-sync fire
  for free" (same survivors file, `basis_type: direct`, `tier_guess: quick-win`). DoD sketch:
  "Merged PR ensuring ingest stamps `node.github={repo,issue,sub_issue}`; verified by a test
  that an ingested node flows through reconcile (external `not_planned` close surfaces as
  drift) and board-sync (Status set on entering the frontier). Distinct provenance-wiring
  artifact from F1-1."
- **S-23** (dedup-merged seed) — "/outcome ingests a parent issue with sub-issues"
  (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`, `basis_type: direct`,
  basis: operator statement "'/outcome ... ingest a parent issue with sub-issues'"). DoD
  sketch: "Merged `/outcome` ingestion mapping a parent issue + its sub-issues into a leaf DAG.
  Verify: feeding a parent with 3 sub-issues produces 3 leaves under the parent node with
  correct dependency edges." Folded into this issue as the original seed the consolidated
  facets above were built from.
- **Binding decisions engaged (must not be contradicted):**
  - `/outcome` campaign (U1–U11) register row
    (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`): derived-on-read status,
    HALT-not-degrade, backend menu off-by-default with host-conditional degrade, cost ledger =
    leaf-produced fact. Ingestion writes structural spec state only.
  - Correction (h) in the same brief (`:28-30`): explicit confirmation that no ingestion path
    exists today and that `outcome_decompose.py` (U7) is a distinct, not-at-start-time
    mechanism this issue must not conflate itself with.
- **Existing mechanism this issue extends** (not replaces):
  `plugins/saga/scripts/discover_subissues.py` (the unwired GraphQL reader),
  `plugins/saga/scripts/outcome.py:244-274` (`start()`/`_starter_nodes()`),
  `plugins/saga/scripts/outcome_spec.py:56-77,187-221` (`NODE_KINDS`, `NODE_STATES`,
  `TERMINAL_STATES`, `Node.github`/`Node.depends_on`),
  `plugins/saga/scripts/outcome_reconcile.py:219-282` (`detect()`, the `node.github` read),
  `plugins/saga/scripts/outcome_board_sync.py:177-257` (`reconcile_board()`, the same
  `node.github` read).

## Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** the mechanism is well-bounded (a GraphQL query extension, a pure mapper
  function, a CLI flag, and stamping an already-declared open pass-through field), but it
  touches three coordinated files (`discover_subissues.py`, `outcome.py`'s `start()`, and the
  new mapper) plus cycle-safety reasoning for edge inference and label-to-kind mapping
  judgment calls — high effort at sonnet is warranted over medium given the coordinated,
  multi-file nature of the wiring; does not warrant opus, since no architectural or policy
  judgment beyond following the already-declared `Node`/`OutcomeSpec` schema is required.

## Release-Surface Checklist

This changes `/outcome` CLI surface (new `--from-objective` flag) and runtime ingestion
behavior inside the `saga` plugin, so the same PR must also update:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — matching version/metadata for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing `/outcome start --from-objective`, the
      `edges_from_relationships()` mapper, and the `node.github` provenance stamping.
- [ ] Any version/metadata drift-guard tests in `tests/` that assert plugin.json /
      marketplace.json / CHANGELOG stay in lockstep — confirm they pass with the bump.

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/discover_subissues.py` — extend the GraphQL query with
  `trackedIssues`/timeline cross-refs for blocked-by/tracked-by relationships; expose a
  library-callable ingestion function (not CLI-only).
- `plugins/saga/scripts/outcome.py` — `start()` gains `--from-objective` handling; wires the
  discover-subissues reader + edge mapper into spec construction.
- `plugins/saga/scripts/outcome_edges.py` (or equivalent, proposed) — the pure
  `edges_from_relationships()` mapper and cycle-drop-and-report logic.
- `tests/test_outcome_command.py` and/or a new `tests/test_outcome_from_objective.py` — fixture
  GraphQL ingestion tests covering AC1–AC9.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface bump per checklist above.

### Tests to add or update
- Test: fixture-GraphQL ingestion produces a spec that passes `OutcomeSpec.validate()` (AC1).
- Test: node count equals fixture sub-issue count (AC2).
- Test: label-to-`kind` mapping for labeled and unlabeled fixture sub-issues (AC3).
- Test: a closed fixture sub-issue seeds a `TERMINAL_STATES` member instead of `"pending"`
  (AC4).
- Test: a linear blocked-by/tracked-by fixture chain yields matching `depends_on` edges (AC5).
- Test: a cyclic fixture pair is dropped from edges and reported, without breaking
  `validate()` (AC6).
- Test: an ingested node's `github` stamp flows through `outcome_reconcile.detect()` as a
  drift record on an external `not_planned` close (AC7).
- Test: an ingested node's `github` stamp flows through `outcome_board_sync.reconcile_board()`
  as a Status set on frontier entry (AC8).
- Test: an end-to-end 3-sub-issue fixture produces 3 nodes with correct edges (AC9).

### Verification
```bash
uv run pytest tests/test_outcome_command.py -v
uv run pytest tests/test_outcome_reconcile.py -v
uv run pytest tests/test_outcome_board_sync.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the new ingestion, edge-inference, and provenance-stamp tests pass
alongside the full existing `/outcome` suite (no regression to `start()`'s no-flag default,
`outcome_reconcile.py`'s drift detection, or `outcome_board_sync.py`'s status sync).

## Handoff maturity

requirements-ready

## Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` (ids `T8-F1-1`,
  `T8-F2-2`, `T8-F4-7`), `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
  (id `S-23`), and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`.
- Source type: ideation issue-map (`issue-map-final.json`, slug
  `pf-outcome-from-objective-ingestion`).
- Source title: /outcome start --from-objective: seed the DAG from a parent Objective with
  edge inference and provenance stamps.

### Intent

Today `/outcome start` cannot seed its DAG from an existing GitHub Objective (a parent issue with sub-issues) at all:

### Context library links

_none_

### Objective

"Ship run-start intent envelope for lifecycle autonomy"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/375
- Number: 375
- Created at: 2026-07-04T07:53:39.633171+00:00

