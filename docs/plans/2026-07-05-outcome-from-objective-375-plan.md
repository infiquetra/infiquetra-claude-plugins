---
title: "/outcome start --from-objective — seed the DAG from a GitHub Objective's sub-issues"
type: feat
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/375
---

# /outcome start --from-objective — seed the DAG from a GitHub Objective's sub-issues

Phase 0 item 7. Wire the existing (unwired) `discover_subissues.py` GraphQL reader into
`/outcome start --from-objective <owner>/<repo>#<N>`, producing an `OutcomeSpec` seeded 1:1 from the
parent Objective's sub-issues — with edge inference, `github` provenance stamps, kind-from-label, and
closed→terminal seeding. Ingestion writes **structural spec state only** (nodes, `depends_on`,
`github`, authored `state`) — never a committed status field, honoring the derived-on-read campaign.

## Problem & grounding

`/outcome start` (`outcome.py:244-267`) accepts only a bare `objective` string and an optional `nodes`
list; with no nodes it falls back to `_starter_nodes()`'s 2-node design→build skeleton (`:270-274`).
There is no `--from-objective` CLI path. `discover_subissues.py` already runs a working `SubIssues`
GraphQL query but is CLI-only — no library ingestion function, and it fetches no blocked-by/tracked-by
relationships. Hand-authored nodes carry no `github` stamp, so `outcome_reconcile`/`outcome_board_sync`
silently no-op on them.

Verified during planning:

- `start()` sig `start(repo_root, outcome_id, objective, nodes=None, *, runner=None)`; CLI `start`
  subparser at `outcome.py:1017-1019` (positionals `outcome_id`, `objective`), dispatched `:1114`.
- `discover_subissues.GRAPHQL_QUERY` (`:11-32`) fetches parent + sub-issue `number/title/state/url/
  labels/assignees` — **no `stateReason`, no dependency edges**. `normalize()` (`:63-90`) shapes it;
  `fetch_subissues(owner, repo, number)` (`:42`) is the fetch; both are library-callable already, but
  `main()` is the only caller.
- **`Node` has a structural `state: str = "pending"` field** (`outcome_spec.py:203`), read by
  `from_dict` (`:296`), validated against `NODE_STATES` (`:251`). `NODE_KINDS=("code","non-code")`
  (`:56`); `TERMINAL_STATES={done,failed,rejected,stalled}` (`:77`). `subplot_id` must be a slug
  `[A-Za-z0-9._-]+` (`:245`).
- **`OutcomeSpec.validate()` (`:431`) requires every `depends_on` to resolve to a declared node and the
  graph to be acyclic (Kahn, `:476`)** — a dangling or cyclic edge fails `validate`.
- Consumers read provenance defensively: `outcome_board_sync.py:257` and `outcome_reconcile.py:282`
  both do `node.github.get("issue", "") or node.github.get("sub_issue", "")` → `_parse_issue_ref`
  (accepts `owner/repo#N` or bare `N`).
- Current `saga` version is **0.57.0** (post-#344). Bump target: **0.58.0**.

## Requirements

- **R1.** `/outcome start --from-objective <owner>/<repo>#<N>` ingests the parent issue's sub-issues
  into an `OutcomeSpec` that passes `OutcomeSpec.validate()` (AC1), one node per sub-issue (AC2).
- **R2.** Each node's `kind` derives from the sub-issue's GitHub label(s): a `non-code` label →
  `kind="non-code"`, otherwise `kind="code"` (AC3). Never silently default past an explicit label.
- **R3.** A CLOSED sub-issue seeds a node whose authored `state` is a `TERMINAL_STATES` member
  (`COMPLETED`→`done`, `NOT_PLANNED`→`rejected`), not the default `pending` (AC4).
- **R4.** A pure `edges_from_relationships()` mapper derives `depends_on` edges from GitHub
  blocked-by/tracked-by relationships among the ingested sub-issues; a cyclic pair is dropped **and
  reported** (not silently discarded, not left to fail `validate`), and edges to non-ingested issues
  are dropped (AC5, AC6).
- **R5.** Each ingested node is stamped `node.github = {repo, issue, sub_issue}` so
  `outcome_reconcile.detect()` (AC7) and `outcome_board_sync.reconcile_board()` (AC8) resolve real
  provenance through their existing defensive reads — no consumer change.
- **R6.** End-to-end: a parent with 3 sub-issues yields a 3-node DAG with correct edges (AC9).
- **R7.** `start()`'s no-flag default (`_starter_nodes()`), `outcome_reconcile`'s drift logic, and
  `outcome_board_sync`'s sync logic are unchanged — no regression.

## Key Technical Decisions

**KTD1 — edge inference uses only stable GraphQL fields and degrades to no-edges.** The relationship
source is `trackedIssues` (task-list tracking) + `timelineItems(itemTypes:[CROSS_REFERENCED_EVENT,
CONNECTED_EVENT])` — both documented, stable `Issue` fields (the source the issue itself names). We do
**not** reference a speculative `blockedBy`/issue-dependency field: an unknown field makes GraphQL
**400 the entire query**, which would break ingestion rather than degrade it. The relationship fetch is
**isolated** (a per-sub-issue block that, on any GraphQL error or missing permission, yields an empty
relationship list) so `normalize()` always produces a per-sub-issue `blocked_by: [number,...]` list —
possibly empty. `edges_from_relationships()` is a **pure function** of that list, fully testable on
fixtures regardless of the live schema, and node **ingestion never fails** on missing relationship data
— worst case, nodes land without auto-edges (still a large win over hand-authoring). Edge inference is
therefore best-effort by design: the fixture tests validate the *mapper*, not GraphQL-to-`blocked_by`
fidelity, which is heuristic. Rejected: referencing a dependency field that may not exist on the schema.

**KTD2 — closed sub-issue → authored structural `state`, not a completion event.** `Node.state` is
structural authored spec state (the out-of-scope permits "nodes, `depends_on`, `github`, structural
spec state"), distinct from the forbidden committed *status* column the derived-on-read model
replaces. Ingest maps `state`+`stateReason`: `OPEN`→`pending`, `CLOSED`+`COMPLETED`→`done`,
`CLOSED`+`NOT_PLANNED`→`rejected`. This satisfies AC4 without writing a completion event or touching
`derive_states`/reconcile machinery. (Requires extending the query with `stateReason`.)

**KTD3 — edges only among the ingested set; drop dangling + cyclic, report both.** `OutcomeSpec.
validate()` fails on a `depends_on` to an undeclared node or on any cycle. So `edges_from_relationships`
(a) keeps only edges whose both endpoints are ingested sub-issues, (b) drops one edge of any cyclic
pair, and (c) returns `(depends_on_map, dropped: list[dict])` so the CLI can report the drops. This
guarantees the produced spec always passes `validate`.

**KTD4 — subplot_id = `sub-<number>` (slug-safe); provenance stamp is the sub-issue's own number.**
`subplot_id` must match `[A-Za-z0-9._-]+`, so a sub-issue becomes `sub-<N>`. The stamp
`node.github = {"repo": "<owner>/<repo>", "issue": "<owner>/<repo>#<N>", "sub_issue": <N>}` uses the
**sub-issue's own number** as the resolvable `issue` (fully-qualified so `_parse_issue_ref` recovers
the repo), because the consumers act on each node's own GitHub issue — never the parent Objective.

## Implementation Units

### U1 — Extend `discover_subissues.py` (query + normalize + library ingestion)

Extend `GRAPHQL_QUERY` with `stateReason` per sub-issue and a stable relationship source —
`trackedIssues(first:50){nodes{number}}` + `timelineItems(itemTypes:[CROSS_REFERENCED_EVENT,
CONNECTED_EVENT], first:50)` (KTD1; no speculative `blockedBy`). Extend `normalize()` to surface
`stateReason` and a `blocked_by: [number,...]` list per sub-issue (empty when the source is
absent/errors). Add a library entry point `fetch_objective(owner, repo, number, *, runner=None) -> dict`
returning the normalized structure. **Add a `runner` seam:** `fetch_subissues`/`fetch_objective` gain
`runner: Callable | None = None` (default `subprocess.run`) so tests inject fixture GraphQL JSON with no
live `gh` (the conftest no-live-gh guard blocks, it does not return fixtures). Keep the CLI.

**Test scenarios** (`tests/test_outcome_from_objective.py`, fixture GraphQL via injected `runner`):
- `normalize()` on a fixture payload surfaces `stateReason` and `blocked_by` lists.
- `fetch_objective` with an injected runner returning fixture JSON produces the normalized dict (no
  live `gh`).

### U2 — New `outcome_edges.py` — pure `edges_from_relationships()`

`edges_from_relationships(subissues: list[dict]) -> tuple[dict[str, list[str]], list[dict]]`: maps each
sub-issue's `blocked_by` numbers to `depends_on` subplot ids (`sub-<N>`), keeping only edges among the
ingested set, dropping one edge of each cyclic pair, and returning `(depends_on_by_subplot, dropped)`
where `dropped` entries carry `{reason, from, to}`.

**Test scenarios:**
- Linear chain A→B→C `blocked_by` yields `depends_on` reflecting the ordering (AC5).
- Cyclic pair (A blocks B, B blocks A) → one edge dropped, reported; produced map is acyclic (AC6).
- A `blocked_by` referencing a non-ingested number is dropped (dangling guard, KTD3).

### U3 — `nodes_from_objective()` ingestion assembler

Add `nodes_from_objective(owner, repo, number, *, runner=None) -> tuple[list[dict], list[dict]]` (in
`outcome.py`, or a small `outcome_ingest.py`): calls `discover_subissues.fetch_objective`, builds one
node dict per sub-issue — `subplot_id="sub-<N>"`, `title`, `kind` from label (KTD/R2), `state` from
state+reason (KTD2/R3), `github` stamp (KTD4/R5) — merges `edges_from_relationships` into each node's
`depends_on`, and returns `(nodes, dropped_edges)`.

**Test scenarios:**
- Node count == fixture sub-issue count (AC2); `kind` from label (AC3); CLOSED→terminal `state` (AC4).
- Ingested node `github` stamp flows through `outcome_reconcile.detect()` → drift record on external
  `not_planned` close (AC7) and through `outcome_board_sync.reconcile_board()` (AC8).

### U4 — CLI `--from-objective`

`p_start.add_argument("--from-objective", metavar="<owner>/<repo>#<N>")` and make the `objective`
positional optional (`nargs="?"`). In `main()`'s `start` branch, when `--from-objective` is set, call
`nodes_from_objective(...)`, default `objective` to the parent Objective's title from the normalized
data when the positional is omitted, then `start(root, outcome_id, objective, nodes=nodes)`, and print
any `dropped` edges to stderr (reported, not silent, KTD3). Without the flag, `objective` stays required
in practice (a bare `start` with neither is an error) and behavior is unchanged (R7).

**Test scenarios:**
- End-to-end: fixture parent with 3 sub-issues + a chain → `start --from-objective` produces a
  3-node spec passing `validate()`, edges correct (AC1, AC9).
- `start` without `--from-objective` still yields the 2-node starter DAG (R7 regression).

### U5 — Release surfaces

Bump `plugin.json` 0.57.0 → **0.58.0**; regenerate `marketplace.json` (`scripts/sync_marketplace.py`);
`CHANGELOG.md` `## [0.58.0] - 2026-07-05`; `tests/test_saga_plugin.py` version literal.

## Scope Boundaries

**In:** query extension (stateReason + relationships), library ingestion fn, `edges_from_relationships`,
node assembly (kind-from-label, closed→terminal, github stamp), CLI flag, fixture tests, release surfaces.

**Out (true non-goals):**
- Changing `outcome_decompose.py` (U7 mid-run decomposition) or `_starter_nodes()`'s no-flag default.
- Changing `outcome_reconcile`/`outcome_board_sync` internals — ingestion populates `github`, consumers
  unchanged.
- A generic non-GitHub relationship importer; any committed status field or completion event at ingest.
- `reconcile --from-objective` drift-on-changed-structure (separate concern).

## Definition of Done

- `/outcome start --from-objective` produces a validate-passing spec seeded from sub-issues, with
  kind-from-label, closed→terminal state, provenance stamps, and cycle-safe inferred edges.
- No-flag `start`, reconcile, and board-sync behavior unchanged.
- Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy
  plugins/ scripts/ tests/ --ignore-missing-imports`; release surfaces in lockstep.
