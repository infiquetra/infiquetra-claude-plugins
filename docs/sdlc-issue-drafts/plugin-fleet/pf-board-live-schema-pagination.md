---
title: "defect: mission-control live-schema resolution and pagination exhaustion — no hardcoded board vocabulary, no silent truncation"
repo: infiquetra-claude-plugins
type: defect
tier: structural
wave: wave-2
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
team: campps
project: operations
status: Idea
labels: defect, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
---

# defect: mission-control live-schema resolution and pagination exhaustion

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

### Tier

structural

### Wave

wave-2

## Problem / motivation

mission-control's board and flow layer still trusts two kinds of stale, author-time
knowledge it should be resolving live, and one of its two integrity checks only
reconciles two of the three documents that actually need to agree:

1. **Item-list pagination is inconsistent across call sites, not absent everywhere.**
   `get_project_items()` in `plugins/mission-control/scripts/sdlc_manager.py:884-911`
   already loops on `pageInfo.hasNextPage` correctly for the Projects-items query
   (`QUERY_GET_PROJECT_ITEMS`, `sdlc_manager.py:766-812`, `first: 100` with a cursor).
   But other list-fetch call sites in the same module return a single page with no
   loop at all — e.g. the label fetch at `sdlc_manager.py:3783`
   (`_rest_get(f"/repos/{ORG}/{repo}/labels?per_page=100")`) and the sibling REST
   list calls immediately around it read one `per_page` page and stop. Nothing
   asserts that a >200-item board or a >100-item label set was read to completion;
   a truncated read is silently treated as the whole list. This is the pattern
   named in the grounding brief's session-mining synthesis: "mission-control
   board/field drift — nonexistent fields assumed, hardcoded aliases, item-list
   pagination silently truncating at 200 of 375 items, create/board-add/field-set
   racing (4 repos)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
   §7, pattern 3).

2. **No committed, live-derived census of the board schema exists**, so drift in
   field names, option IDs, or board shape has no failing signal until a write
   silently no-ops or mis-targets a field. `plugins/mission-control/config/
   sdlc-schema.json:9` itself documents the gap: "This file intentionally
   contains no live GitHub Projects field option IDs; tooling must resolve
   those from GitHub at runtime" — but no committed `board-schema.json` census
   and no CI diff step enforce that resolution ever happens or ever drifts.
   The repo's own `context_census.py` pattern (context-library census + CI
   `--check`, per the grounding brief §4) is the template to mirror for boards
   and has not been.

3. **The existing parity gate is two-way, not three-way.** `plugins/mission-
   control/config/generated/check_issue_contract_parity.py:1-30` explicitly
   documents itself as reconciling only the vendored `issue_contract_data.py`
   and `issue_contract_shim.py` against their pinned SHA256 manifests — a
   source-schema-vs-generated-shim match. It has no leg that resolves live
   GitHub Projects field options and checks them against what the schema and
   shim assume. Per `sdlc-schema.json:9`'s own admission that field option IDs
   are runtime-resolved, a renamed or removed upstream option can silently
   diverge from both vendored copies while the existing two-way gate stays
   green.

4. Recent repo history establishes the fix pattern to generalize, it just
   hasn't been generalized past one call site: commit `71faf92` ("fix(saga):
   schema-resolve /outcome board status instead of hardcoded 'In Progress'")
   and its accompanying decision record
   (`docs/engineering-journal/DECISIONS.md:173-186`,
   `{#outcome-board-status-schema-resolve-326}`) replaced one hardcoded board
   status literal with a schema-resolved value and made resolution failure
   fail-loud-and-retryable rather than silently wrong. mission-control's board
   writes (field-set, item-list, board-add) have not received the equivalent
   treatment.

## Definition of Done

A merged PR that:

- Adds a `board_census.py` script (mirroring the shape of the context-library's
  `context_census.py`) that derives a committed `board-schema.json` for each
  tracked project by fully paginating the live GitHub Projects GraphQL API
  (looping on `hasNextPage`/`endCursor` exactly like `get_project_items()`
  already does), and wires a CI `--check` step that fails when the committed
  census drifts from a fresh live derivation.
- Adds a `paginate-or-raise` helper used by every mission-control list-fetch
  call site (GraphQL and REST) that hard-errors — rather than silently
  returning a partial page — whenever a response's page boundary is hit
  without an explicit "no more pages" signal, and migrates the currently
  unguarded REST call sites (starting with the label fetch at
  `sdlc_manager.py:3783` and its siblings) onto it.
- Adds a call-site lint (`check_pagination.py`, or extends an existing lint
  script) that scans mission-control scripts and skill reference docs for
  `gh` list invocations (GraphQL `first:`/REST `per_page=` and raw
  `gh project item-list` / `gh api` calls) lacking a cursor loop or an
  explicit `--limit` guard, and wires it into CI.
- Extends `check_issue_contract_parity.py` with a third, `--live`-gated
  reconciliation leg that resolves the project's live field options via `gh`
  and fails when they diverge from what `sdlc-schema.json` and the vendored
  shim assume, with the `--live` leg skipped (not silently passed) in offline
  CI runs.
- Routes every mission-control board/field write (item add, field-set,
  status change) through the live schema-resolver before the write, fail-closed
  when a referenced field or option cannot be resolved, generalizing the
  pattern already landed for `/outcome` board status in commit `71faf92`.
- Ships test coverage (below) proving each of the four legs above actually
  traps the fault it targets.

### Acceptance criteria
Each criterion below maps to one absorbed facet (see Grounding references).

- [ ] **(T9-F2-6, primary)** A mocked live GraphQL response describing a project
   with more than 200 items causes `board_census.py` to return the full item
   count (not truncated at the first page), and a CI run against a mutated
   committed `board-schema.json` snapshot fails the `--check` diff step.
   Test: `uv run pytest tests/test_board_census.py -k over_200_items` and
   `uv run pytest tests/test_board_census.py -k mutated_snapshot_fails_check`.

- [ ] **(T9-F1-7)** A mocked GraphQL/REST response describing more than 100
   items with `hasNextPage: true` causes the shared `paginate-or-raise` helper
   to raise rather than silently returning the single fetched page (a
   silent 200-item truncation is a defect, not a valid partial result).
   Test: `uv run pytest tests/test_pagination_helper.py -k raises_on_truncation`.

- [ ] **(T9-F4-5)** An unguarded `gh project item-list` (or equivalent raw list
   call) added to a plugin script or an agent-facing skill reference doc,
   lacking a cursor loop or explicit `--limit`, fails the pagination lint in
   CI. Test: `uv run pytest tests/test_check_pagination.py -k unguarded_call_site_fails`.

- [ ] **(T14-F5-3)** A mocked live field-option rename (the option ID the schema
   and shim assume no longer resolves to the same name upstream) is flagged
   as a divergence by the third, `--live`-gated leg of
   `check_issue_contract_parity.py`, while the existing two vendored-artifact
   legs continue to pass on their own terms — proving the third leg adds
   coverage rather than replacing the existing two.
   Test: `uv run pytest tests/test_issue_contract_parity.py -k live_leg_flags_rename`.

- [ ] **(T14-F6-4)** A mocked upstream field-option rename on a board write path
   (item add / field-set) causes the write to resolve the new live ID (or
   fail loud with a typed, retryable error) rather than silently setting a
   stale cached alias — generalizing the `71faf92` pattern beyond `/outcome`
   board status to mission-control's board/field write surface.
   Test: `uv run pytest tests/test_sdlc_manager.py -k field_write_resolves_or_fails_loud`.

### Out-of-scope / non-goals
In scope: mission-control's own board/field/item list-fetch and write call
sites in `plugins/mission-control/scripts/sdlc_manager.py`, the new
`board_census.py` script, the pagination helper and lint, and the third leg
of `check_issue_contract_parity.py`.

Non-goals (explicitly out of scope for this issue):

- Reworking `/outcome`'s own board-status resolution — that already shipped
  in `71faf92` / `{#outcome-board-status-schema-resolve-326}`; this issue only
  generalizes the *pattern* to mission-control's separate board/field write
  surface, it does not touch `outcome_board_sync.py`.
- Backfilling a live-parity leg onto every other vendored-artifact consumer
  in the fleet — this issue scopes the third parity leg to
  `check_issue_contract_parity.py` only.
- Any change to the Projects board's own schema, field taxonomy, or board
  layout — this issue only makes existing reads/writes resolve that schema
  live and fail loud on drift; it does not redesign the schema.
- Any change to non-mission-control plugins' list-fetch call sites (saga,
  team-execution, etc.) — the pagination lint applies to mission-control's
  own scripts and skill docs only in this issue; extending it fleet-wide is
  a separate follow-up.

## Grounding References

- `T9-F2-6` (primary) — "Live-derived board schema census: remove
  hand-maintained field maps and the 200-item truncation." `dod_sketch`:
  merged `board_census.py` (mirrors `context_census.py`) deriving a committed
  `board-schema.json` from the live Projects API fully-paginated + CI diff
  step + the >200 pagination fix; verified by CI failing on a mutated
  snapshot and the census returning >200 items on a 375-item board.
- `T9-F1-7` (facet) — "Pagination-exhaustion assertion for mission-control
  list fetches." `dod_sketch`: merged paginate-or-raise helper used across
  mission-control board/flow/metrics scripts that hard-errors when a page
  boundary is hit without `hasNextPage==false`; verified by a mocked
  >200-item response test asserting the raise instead of a silent 200-slice.
- `T9-F4-5` (facet) — "Pagination-completeness lint over GitHub list-call
  sites." `dod_sketch`: merged `check_pagination.py` scanning plugin scripts
  and agent docs for `gh` list calls lacking a cursor loop or explicit
  `--limit` guard + a call-site registry + CI lint; verified by the guard
  failing on an unguarded `gh project item-list` in an agent doc.
- `T14-F5-3` (facet) — "Procurement three-way match: reconcile schema,
  generated shim, and live GitHub before trusting a field." Basis: the
  accounts-payable three-way match control (PO + goods receipt + invoice;
  standard AP internal control) applied by analogy — the current
  `check_issue_contract_parity.py` is a two-way match (source schema vs.
  generated shim) while `sdlc-schema.json`'s own description
  (`config/sdlc-schema.json:9`) declares live GitHub field-option resolution
  is a real, unreconciled third leg. `dod_sketch`: merged three-way parity
  leg (`--live`-gated) + test; verified mocking a live field-option rename
  flags divergence in the third leg.
- `T14-F6-4` (facet) — "Zero hardcoded board vocabulary: every field/option
  resolved live before any write." Basis (direct): grounding brief §7,
  pattern 3 — "mission-control board/field drift — nonexistent fields
  assumed, hardcoded aliases, item-list pagination silently truncating at
  200/375 items, create/board-add/field-set racing (4 repos)"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`), generalizing the
  pattern already established by commit `71faf92` ("schema-resolve /outcome
  board status instead of hardcoded 'In Progress'") and
  `{#outcome-board-status-schema-resolve-326}`
  (`docs/engineering-journal/DECISIONS.md:173-186`). `dod_sketch`: merged
  mission-control flow/board writes routed through live schema-resolve +
  complete-pagination with fail-closed guards; verified an upstream option
  rename makes the write resolve the new id or fail loud rather than set a
  stale alias.

Binding decisions this builds on / must not violate:

- `{#outcome-board-status-schema-resolve-326}` (#326,
  `docs/engineering-journal/DECISIONS.md:173-186`) — establishes the
  schema-resolve-over-hardcode pattern and its fail-loud-per-op,
  never-tick-fatal failure posture. This issue generalizes that posture to
  mission-control's board/field write surface without re-touching
  `outcome_board_sync.py` itself.
- `{#readonly-verifier-fallback-ladder-325}` /
  `{#verify-agent-git-checkout-clobber}` — any verify/review-class subagent
  spawned to validate this work (rather than as part of the normal
  `saga:work` / `saga:code-review` flow) must use the `saga:readonly-verifier`
  profile with worktree isolation, per
  `plugins/saga/references/sandbox-spawn-sites.md`.

## Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none

Justification: mechanical-but-multi-site work (adding a shared pagination
helper, a lint, a census script, and a third parity leg across several call
sites) with a clear, testable spec per facet — no architectural judgment call
or adversarial review is required beyond what `team-execution`'s consensus
review already provides, so sonnet/high is sufficient; no case for opus or an
external-engine hand-off.

## Release-surface checklist

This issue changes mission-control plugin behavior (new script, new CI gate,
new write-path guard), so the same PR must also update:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump and
      description/keyword updates reflecting the new census/pagination/parity
      behavior.
- [ ] `.claude-plugin/marketplace.json` — matching version bump for
      mission-control.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry describing the
      pagination-exhaustion fix, the board census, and the third parity leg.
- [ ] Any version/metadata drift-guard tests (e.g. a test asserting
      `plugin.json` version matches `marketplace.json` and `CHANGELOG.md`'s
      latest entry) stay green with the bump applied.

### Files expected to change

Indicative only; exact set is `/plan`'s to determine.

- `plugins/mission-control/scripts/sdlc_manager.py` — pagination helper
  migration for unguarded REST call sites (e.g. `:3783`), board/field write
  paths routed through live schema-resolve.
- `plugins/mission-control/scripts/board_census.py` (new) — live-derived
  `board-schema.json` census script.
- `plugins/mission-control/config/board-schema.json` (new, committed) — the
  census output CI diffs against.
- `plugins/mission-control/scripts/check_pagination.py` (new, or extends an
  existing lint) — call-site pagination-completeness lint.
- `plugins/mission-control/config/generated/check_issue_contract_parity.py`
  — third `--live`-gated reconciliation leg.
- `tests/test_board_census.py`, `tests/test_pagination_helper.py`,
  `tests/test_check_pagination.py`, `tests/test_issue_contract_parity.py`,
  `tests/test_sdlc_manager.py` — new/extended coverage per acceptance
  criterion above.
- `plugins/mission-control/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/mission-control/CHANGELOG.md`
  — release-surface updates (see checklist above).

### Tests to add or update

- [ ] `board_census.py` returns the full item count on a mocked >200-item
      board (no truncation at the first page). Check:
      `uv run pytest tests/test_board_census.py -k over_200_items` → passes.
- [ ] CI `--check` fails against a mutated committed `board-schema.json`
      snapshot. Check:
      `uv run pytest tests/test_board_census.py -k mutated_snapshot_fails_check` → passes.
- [ ] Shared pagination helper raises rather than silently truncating on a
      mocked >100-item, `hasNextPage: true` response. Check:
      `uv run pytest tests/test_pagination_helper.py -k raises_on_truncation` → passes.
- [ ] Pagination lint fails on an unguarded `gh project item-list` call added
      to a plugin script or skill reference doc. Check:
      `uv run pytest tests/test_check_pagination.py -k unguarded_call_site_fails` → passes.
- [ ] Third `--live`-gated parity leg flags a mocked live field-option rename
      while the existing two vendored-artifact legs still pass independently.
      Check:
      `uv run pytest tests/test_issue_contract_parity.py -k live_leg_flags_rename` → passes.
- [ ] A board/field write resolves a renamed upstream option's new live ID
      (or fails loud) instead of setting a stale cached alias. Check:
      `uv run pytest tests/test_sdlc_manager.py -k field_write_resolves_or_fails_loud` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification

```bash
# Targeted new/extended coverage
uv run pytest tests/test_board_census.py tests/test_pagination_helper.py \
  tests/test_check_pagination.py tests/test_issue_contract_parity.py \
  tests/test_sdlc_manager.py -v

# Live-gated parity leg, offline-skipped by default; run explicitly to prove it fires
uv run pytest tests/test_issue_contract_parity.py -k live_leg_flags_rename

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports \
  && uv run bandit -r plugins/
```

Expected: all green; the mutated-snapshot and unguarded-call-site tests fail
before the fix and pass after it (run once on the pre-fix tree to confirm
they're not vacuously passing).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`,
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json`,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- Source type: ideation survivor consolidation (issue-map)
- Source title: mission-control live-schema resolution and pagination
  exhaustion: no hardcoded board vocabulary, no silent truncation

### Intent

mission-control's board and flow layer still trusts two kinds of stale, author-time knowledge it should be resolving live, and one of its two integrity checks only reconciles two of the three documents that actually need to agree:

### Context library links

_none_

### Inputs inventory

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/mission-control/scripts/sdlc_manager.py`
- `plugins/saga/references/sandbox-spawn-sites.md`
- `plugins/mission-control/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/mission-control/CHANGELOG.md`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/424
- Number: 424
- Created at: 2026-07-04T08:09:03.475306+00:00

