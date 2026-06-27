---
title: defect: infiquetra-claude-plugins campps work
repo: infiquetra-claude-plugins
type: defect
team: campps
project: operations
status: Idea
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# defect: infiquetra-claude-plugins campps work

---
date: 2026-06-27
kind: brainstorm
maturity: requirements-ready
type: defect
source: field-observed defect — 4/4 across issue creations #275, #277, #278, #279 (VECU port-seeds campaign)
title: "create-prepared dies on a partial GraphQL NOT_FOUND — board-add + Status silently skipped"
---

# create-prepared Partial-GraphQL-Error Defect — Resolve the Node Without a Speculative 404

### Objective

Board objective: **improve-claude-plugins**. A defect on the saga ↔ mission-control write boundary
that breaks `issue create-prepared` on **every** run (4/4: #275, #277, #278, #279 — 100% reproducible),
forcing manual board-add + Status recovery each time. Hardens the operations tooling this campaign
itself runs on, and is a **near-dependency of S-2 (#279)**, whose R18 ("bounded-retry + fail-loud on
the create-prepared boundary") cannot ship over a resolver that misfires on every issue.

### Intent

Make `create-prepared` complete board-add + Status with **zero manual recovery** by resolving the
issue node with GitHub's `issueOrPullRequest(number:)` union — eliminating the speculative
`pullRequest` 404 at the source, with **no change to the shared `_graphql` error strictness** (which
guards ~7 mutation call sites). Add a fail-loud + resumable guard so a genuine post-create failure
never leaves an untracked issue.

### Out-of-scope / non-goals

- **Objective auto-set** — never part of the create flow; a separate enhancement.
- **Title recovery** — title is set at create (`--title`); not a code defect.
- **`deploy-templates` 404s** — separate, non-fatal.
- **Broad `_graphql` partial-tolerance (Option A')** — optional future-proofing; a `/plan` call, not
  required to fix the defect.
- **Auto-delete of created issues on failure** — destructive; explicitly excluded.

### Files expected to change

- `plugins/mission-control/scripts/sdlc_manager.py` — `QUERY_GET_ITEM_NODE_ID` (`:707-714`),
  `QUERY_GET_ITEM_LABELS` (`:816-823`) → `issueOrPullRequest` union; `board_add` response-access
  (`:1034`); fail-loud/resumable guard around the post-create steps (`:3984-3999`).
- `tests/test_graphql_issue_resolution.py` — **new** (repo-root, CI-collected).
- Release surfaces: `plugins/mission-control/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/mission-control/CHANGELOG.md`.

### Tests to add or update

Drive the **real** path (`_gh` raising `GhApiError(stdout=<envelope>)`), not a direct `_graphql` feed
(which hits the dead `:659` path). Cases: union resolver returns the node at `gh` exit 0; fatal
`data:null` + error raises; present-`data`-but-fatal (FORBIDDEN) raises; empty/non-JSON stdout
re-raises the original (no `JSONDecodeError` mask); partially-failed **mutation** (payload `null` +
error) raises; PR-direction symmetry; `board_add` + Status end-to-end against the fixed resolver.

### Context library links

- `docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md` — this requirements doc.
- `docs/reviews/2026-06-27-create-prepared-partial-graphql-error-readiness.md` — gated codex+agy review.
- S-2 issue **#279** — the autonomous-board-sync capability whose R18 this unblocks.

### Acceptance criteria

- [ ] `uv run pytest tests/test_graphql_issue_resolution.py` is green (all R8-R11 cases).
- [ ] `create-prepared` on a fresh draft adds the issue to the board **and** sets Status with **no**
  manual `gh project item-add` / `flow set-field` for those steps.
- [ ] The `issueOrPullRequest(number:)` resolver returns a single resolved node with `gh` exit 0 (no
  spurious `NOT_FOUND`).
- [ ] A partially-failed mutation (`updateProjectV2ItemFieldValue` payload `null` + error) **still
  raises** — no silent success.
- [ ] A simulated network failure during node resolution fails loud with the issue URL + remaining
  steps; a re-run completes board-add without creating a duplicate issue.

### Verification

- `uv run pytest` (full suite), `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy plugins/`, `uv run bandit -r plugins/`.
- Manual end-to-end: run `create-prepared` on a throwaway draft and confirm board membership + Status
  with zero manual steps; confirm the dogfood — this very issue's creation should be the first to
  complete cleanly once the fix lands.

## Summary

`mission-control issue create-prepared` creates the GitHub issue successfully, then **dies before
adding it to the board or setting Status**, every single time (4/4: #275, #277, #278, #279 — 100%
reproducible). The operator recovers by hand each time (`gh project item-add` + `flow set-field`).

Root cause, verified empirically this session: `board_add` resolves the new issue's node id with a
GraphQL query (`QUERY_GET_ITEM_NODE_ID`, `sdlc_manager.py:707-714`) that **deliberately queries both
`issue(number:N)` and `pullRequest(number:N)`** so it can resolve either kind. For an issue, the
`pullRequest` branch returns a partial `NOT_FOUND` error — *while `data.issue` is fully populated*.
GitHub's `gh api graphql` **exits non-zero (1)** on that partial error, so `_gh` (`:632-640`) raises a
typed `GhApiError` and the usable `data` is discarded. The call site in `board_add` (`:1032`) is
outside its try/except, so the whole `create-prepared` flow aborts after the issue already exists.

**The fix is to stop generating the speculative 404 at all**: replace the dual-branch `issue{} +
pullRequest{}` lookup with GitHub's union field `issueOrPullRequest(number:)`, which resolves
whichever exists with **no error and a zero exit** (verified live this session). This is surgical, per
the two affected queries, and — critically — needs **no change to the shared `_graphql` error
strictness**, so it introduces no risk of masking real failures on the ~7 mutation call sites that
share that helper.

> **Doc-review note (codex + agy, gated under Claude-side verification).** The first draft recommended
> relaxing `_graphql` to "return any non-null `data`" as the primary fix. Both engines independently
> flagged that as a **P0**: the shared `_graphql` also runs **mutations** (`addProjectV2ItemById`,
> `updateProjectV2ItemFieldValue`, `archiveProjectV2Item` — `:1043, :1128, :1170, :1340, :2199`), and a
> partially-failed mutation returns non-null `data` with the intended payload `null` plus an error;
> a blanket "return non-null data" would **silently swallow a failed board-add or Status-set**. agy
> added the field-level case (`{"data":{"repository":null},"errors":[FORBIDDEN]}` → a `TypeError`
> downstream). Claude independently quantified the radius (3 mutation constants, ~7 call sites) and
> verified `issueOrPullRequest` resolves cleanly (exit 0). The recommendation **flipped to the union
> query as primary**; the `_graphql` relaxation is demoted to an optional, strictly-scoped defense.

## Observed behavior (reproduction)

Every `create-prepared` run in the campaign produced:

```
ERROR: gh command failed: gh: Could not resolve to a PullRequest with the number of N.
```

After which:
- **Issue IS created** (with title + labels) — created at `_create_github_issue` (`:3984`), labels
  applied at `gh issue create --label` (`:3815-3816`), both *before* the failing call.
- **Board-add skipped**, **Status not set** — both are *after* the failing `board_add` (`:3985`) in
  the create flow (`flow_set_field` Status at `:3986`). (`flow_set_field` itself does **not**
  dual-branch — it resolves via `get_project_items` matching `content.number == number`, verified —
  so once `board_add` is fixed, Status-setting works with no further change.)
- Operator recovers manually: `gh project item-add 3 --owner infiquetra --url <issue-url>` +
  `flow set-field --field Status --option Todo` (+ `--field Objective …`, a *separate* gap — see Scope).

### Empirical proof (captured this session — read-only probes against issue #279)

Dual-branch query (the current code path) — **exit 1**, data present, spurious error:

```
EXIT_CODE=1
STDOUT: {"data":{"repository":{"issue":{"id":"I_kwDOQdql-c8AAAABG68biw","number":279},
         "pullRequest":null}},
         "errors":[{"type":"NOT_FOUND","path":["repository","pullRequest"],
         "message":"Could not resolve to a PullRequest with the number of 279."}]}
```

Union query (the proposed fix, Option B) — **exit 0, no error**:

```
EXIT_CODE=0
STDOUT: {"data":{"repository":{"issueOrPullRequest":{"__typename":"Issue",
         "id":"I_kwDOQdql-c8AAAABG68biw","number":279}}}}
```

## Root cause (two layers, both real)

1. **`_gh` raises on the non-zero exit (`:632-640`).** `gh api graphql` exits 1 on a partial error.
   `_gh` calls `_classify_gh_error(...)` → no `HTTP NNN` line in stderr, so it falls through to
   `GhApiError(full, status_code=None, ...)` (`:606`). The exception *carries* the usable stdout
   (`stdout=result.stdout`, `:639`) but the caller never reads it. *(codex CHECK-1 VERIFIED.)*
2. **`_graphql`'s own fatal-on-`errors` check (`:659-660`)** is the same mistake one layer up:
   `if "errors" in data: raise`. It is currently *dead code for this path* (because `_gh` raises
   first). This matters for testing (below): a regression test that feeds JSON straight to `_graphql`
   would exercise this dead path, **not** the real `_gh`-raises path.
3. **`board_add` resolves the node id unguarded.** `_graphql(QUERY_GET_ITEM_NODE_ID, …)` at `:1032`
   is *before* the `for proj in projects:` loop; the try/except (`:1042-1057`) only wraps the
   per-project add. So the resolution exception propagates and aborts `create-prepared`.
   *(codex CHECK-7 VERIFIED.)*

The dual-branch query is *intentional* (`:1034` does `repo_data.get("issue") or
repo_data.get("pullRequest")` so one helper resolves either kind). The design intent is fine; the
implementation generates a guaranteed-spurious 404 that the error layer then treats as fatal.

## Blast radius

**The bug** — every `_graphql` call whose query selects a speculative branch that may not resolve:
- **`QUERY_GET_ITEM_NODE_ID`** (`:707-714`) — the hot path; hit by `board_add` on **every** issue.
- **`QUERY_GET_ITEM_LABELS`** (`:816-823`) — same `issue {…} pullRequest {…}` dual-branch shape;
  hit by the label-field sync path (`_get_item_labels` → `_sync_label_fields_for_item`, `:1303`).

This list is **complete** for dual-branch issue/PR-by-number queries (codex CHECK-4 VERIFIED;
`QUERY_GET_ISSUE_TIMELINE` at `:825` is single-branch — `issue(number:)` only — verified, so it does
not emit the spurious 404 in its issue-only usage).

**The rejected fix's blast radius** — why a blanket-tolerant `_graphql` is unsafe: the shared helper
also executes **mutations** that must stay strict. Mutation constants `QUERY_ADD_ITEM_TO_PROJECT`,
`QUERY_SET_FIELD_VALUE`, `QUERY_ARCHIVE_ITEM` flow through `_graphql` at `:1043, :1128, :1170, :1340,
:2199`. A partially-failed mutation returns non-null `data` with the intended field `null` plus an
error; "return any non-null `data`" would report success on a failed write.

## Key decisions

- **KD1 — Eliminate the spurious 404 at the query, don't soften the error handler.** Switching the
  two dual-branch resolvers to `issueOrPullRequest(number:)` makes `gh` exit 0 (verified), so nothing
  in the error path needs to change. *(codex + agy + Claude convergence; flips the original draft.)*
- **KD2 — Keep `_graphql` strict; it guards ~7 mutation call sites.** Relaxing it globally trades a
  read bug for a silent-write bug. *(codex P0, agy P0, Claude-quantified.)*
- **KD3 — Union selection requires inline fragments.** `issueOrPullRequest` returns a union, so `id`
  must be selected via `... on Issue { id } ... on PullRequest { id }`; a bare `issueOrPullRequest {
  id }` is invalid. The fix also updates the response-access line (`:1034`) from `issue or
  pullRequest` to the single `issueOrPullRequest` node. *(codex P2.)*
- **KD4 — Tests must drive the real exception path.** The regression test must simulate `_gh` raising
  `GhApiError(stdout=<envelope>)` (and, post-fix, assert the union resolver returns the node with
  `gh` exit 0), **not** feed an envelope straight to `_graphql` (which hits the dead `:659` path).
  *(codex P1.)*
- **KD5 — A genuine resolution failure must fail loud and stay resumable.** Independent of the partial
  -error bug, `board_add`'s unguarded resolve means a real failure (network, true not-found) aborts
  *after* the issue exists, leaving an untracked issue. The fix must fail loud with the issue URL +
  remaining steps and record enough sidecar state that re-running `create-prepared` **resumes**
  board-add rather than re-creating the issue. **No auto-delete** (destructive). *(agy P0; couples to
  S-2 #279 R18.)*
- **KD6 — Scope to the resolver bug + the fail-loud guard.** Objective-auto-set and title-recovery are
  separate concerns (see Scope Boundaries). *(codex CHECK-6 + agy P3 + Claude agree.)*

## Fix options

**Option B — `issueOrPullRequest` single-branch query (recommended, PRIMARY).**
Replace the `issue {…} pullRequest {…}` dual-branch in `QUERY_GET_ITEM_NODE_ID` (and
`QUERY_GET_ITEM_LABELS`) with `issueOrPullRequest(number:$number){ __typename ... on Issue { id … }
... on PullRequest { id … } }`, and update the response-access at `:1034` to read the single node.
- *Pros*: removes the spurious 404 at the source (verified exit 0); **no `_graphql` change** → zero
  risk to the mutation call sites; the most correct GitHub-GraphQL idiom for "resolve issue-or-PR".
- *Cons*: per-query (apply to both `:707` and `:816`); does not by itself prevent a *future* dev from
  writing a new dual-branch query — mitigated by KD2's note + an optional scoped guard (Option A').

**Option A' — Strictly-scoped, opt-in partial tolerance in `_graphql` (optional defense-in-depth).**
NOT the blanket form. If adopted for future-proofing, `_graphql` gains an explicit `allow_partial`
parameter passed *only* by read-resolvers, and even then tolerates a partial error only when **(a)**
the `_gh` exception's `stdout` is non-empty and parses as JSON (else re-raise the original —
`json.loads(e.stdout)` must be guarded), **(b)** every error is `type: NOT_FOUND` on an un-requested
nullable path, and **(c)** the requested target node actually resolved. Mutations never pass
`allow_partial`.
- *Pros*: closes the class for future dual-branch read queries without endangering writes.
- *Cons*: more surface; only worth it if /plan judges the future-query risk real. Option B fixes the
  actual defect without it.

**Option A (blanket "return any non-null `data`") — REJECTED.**
Masks failed mutations (`:1043, :2199`, …) and field-level errors (`{"data":{"repository":null},
"errors":[FORBIDDEN]}` → downstream `TypeError`). Documented here so the rejection is durable.

**Option C — `_gh` graphql-aware non-zero handling — REJECTED.**
`_gh` is the shared shim for every gh call (REST included); widening its success criteria has the
widest blast radius. KD2 keeps it strict.

## Recommended fix

**Option B (primary)** for both dual-branch resolvers + the `:1034` access update, **plus KD5's
fail-loud/resumable guard** around the post-create steps. Option A' is an optional `/plan` call for
future-proofing, not required to fix the defect.

## Requirements

**Correctness (the fix):**
- **R1** — `board_add` resolves an issue/PR node id via `issueOrPullRequest(number:)` (inline
  fragments) and `gh` exits 0 with no spurious `NOT_FOUND`. *(Option B; `:707`/`:1032`/`:1034`)*
- **R2** — `QUERY_GET_ITEM_LABELS` (`:816`) is converted the same way; the label-field sync path stops
  emitting the spurious 404. *(Option B; `:1303`)*
- **R3** — the shared `_graphql` error strictness is **unchanged** by the primary fix; no mutation
  call site changes behavior. *(KD2)*
- **R4** — `_gh` remains strict for all callers. *(KD2)*

**End-to-end (the user-visible outcome):**
- **R5** — `create-prepared` on a fresh issue adds it to the target board **and** sets Status with
  **zero manual recovery for those two steps**. (Objective remains a separate, out-of-scope
  enhancement — this requirement does not claim Objective is auto-set.) *(the actual bug)*

**Robustness (KD5):**
- **R6** — a genuine post-create failure (network, real not-found) fails **loud** with the created
  issue URL and the remaining steps, never a bare traceback. *(agy P0)*
- **R7** — `create-prepared` is **resumable**: re-running it on a draft whose sidecar already records
  `created_issue_number` completes the board-add/Status steps instead of creating a duplicate issue.
  No issue is auto-deleted. *(agy P0; mechanism to /plan)*

**Anti-recurrence (KD4 — tests drive the real path):**
- **R8** — a test simulates `_gh` raising `GhApiError(stdout=<partial-error envelope>)` and asserts
  the **fixed** resolver returns the issue node (post-Option-B: asserts the union query yields a
  single resolved node with `gh` exit 0). *(codex P1)*
- **R9** — negative tests assert the system **still fails loud**: (a) fatal `data: null` + error
  raises; (b) `data` present but the *requested* node is `null` due to a field-level error (e.g.
  FORBIDDEN) raises; (c) an exception whose `stdout` is empty/non-JSON re-raises the original error
  (no `JSONDecodeError` mask); (d) a partially-failed **mutation** (intended payload `null` + error)
  raises. *(codex P1 + agy P1/P2 + Claude)*
- **R10** — PR-direction symmetry: a number that **is** a PR resolves via the union to the PR node.
- **R11** — an end-to-end test (mocked `_gh`) asserts `board_add` + Status complete against the fixed
  resolver. Tests live under repo-root `tests/` (CI-collected — `pyproject.toml:83-84`,
  `.github/workflows/ci.yml:42-43`; codex CHECK-8). *(R5 guard)*

## Acceptance examples

- **AE1** — Given issue #279, `issueOrPullRequest(number:279)` returns
  `{"__typename":"Issue","id":"…","number":279}` with `gh` exit 0 and no error. *(R1)*
- **AE2** — Given a fresh prepared draft, `create-prepared --yes` creates the issue, adds it to the
  board, and sets Status=Todo with no manual `gh project item-add` / `flow set-field` for those steps.
  *(R5)*
- **AE3** — Given a response with `data: null` + an auth error, the resolver raises the typed
  `ApiAuthError` exactly as today. *(R9a)*
- **AE4** — Given a partially-failed `updateProjectV2ItemFieldValue` (payload `null` + error),
  `flow_set_field` raises rather than reporting success. *(R9d — the rejected-Option-A guard)*
- **AE5** — Given a simulated network failure during node resolution after the issue is created,
  `create-prepared` prints the issue URL + remaining steps and exits non-zero; a re-run completes the
  board-add without creating a second issue. *(R6/R7)*

## Scope boundaries

- **IN**: the dual-branch resolver bug (both queries + the `:1034` access); the fail-loud/resumable
  guard on the post-create steps; the regression + e2e tests.
- **OUT — Objective not auto-set.** `create-prepared` never set Objective (it sets only Status,
  `:3986`); the manual `--field Objective` step is a *missing feature*, not a regression. A separate
  enhancement (auto-set a configured Objective from the draft sidecar). *(codex CHECK-6 + agy P3.)*
- **OUT — title recovery.** Title is set at create (`--title`, `:3810-3811`, verified); any title
  re-edit in the manual recovery was operator discretion, not a code defect.
- **OUT — `deploy-templates` 404s.** Separate, non-fatal, independent of this seam.
- **OUT — broad `_graphql` partial-tolerance (Option A').** Optional future-proofing, not required to
  fix the defect; a `/plan` call.

## Dependencies / assumptions

- `issueOrPullRequest(number:)` is a real `Repository` field returning the `IssueOrPullRequest` union;
  `id` is selectable only via inline fragments — **verified live this session** (exit 0) and against
  GitHub's GraphQL schema (codex web-verified).
- `GhApiError` carries `stdout` (`:501`, verified) — needed only if Option A' is pursued.
- Test harness: repo-root `tests/` (CI-collected); proposed `tests/test_graphql_issue_resolution.py`.

## Outstanding questions (deferred to /plan)

1. Whether to pursue Option A' (scoped, opt-in `_graphql` partial tolerance) for future-proofing, or
   rely solely on Option B for the two known queries.
2. KD5 resumability mechanism: detect `created_issue_number` in the sidecar and skip `_create_github_
   issue` on re-run, vs a dedicated `create-prepared --resume`. Idempotency key = (repo, issue number,
   target board).
3. Whether to also adopt `issueOrPullRequest` for any *other* by-number resolution that could be
   called with the non-matching kind (none in the dual-branch list today; `:825` is issue-only).

## Coupling note (why this matters now)

This defect lives on the **saga ↔ mission-control write boundary** — exactly the boundary that S-2
(reversibility/idempotency certificate, issue #279) proposes to make *autonomous*. S-2's R18 already
names "bounded-retry + fail-loud on the create-prepared boundary," and this defect's R6/R7 are the
concrete instance of it. You cannot ship reliable autonomous board-sync over a resolver that misfires
on every issue and abandons state on failure. Fixing this is effectively a near-dependency of S-2.

## Sources

- `plugins/mission-control/scripts/sdlc_manager.py:649-661` — `_graphql`, fatal-on-`errors` (strict;
  kept strict by the primary fix).
- `:617-646` — `_gh`, raises typed error on non-zero exit; carries stdout at `:639`. *(CHECK-1)*
- `:480-501` — `GhApiError`, carries `stdout`. *(CHECK-2)*
- `:559-606` — `_classify_gh_error`; no HTTP status ⇒ `GhApiError(status_code=None)` at `:606`.
- `:707-714` — `QUERY_GET_ITEM_NODE_ID` dual-branch; `:1032`/`:1034` — `board_add` resolution +
  `issue or pullRequest` fallback; `:1042-1057` — try/except wraps only the per-project loop. *(CHECK-7)*
- `:816-823` — `QUERY_GET_ITEM_LABELS`, the second (and last) dual-branch query. *(CHECK-4)*
- `:825-849` — `QUERY_GET_ISSUE_TIMELINE`, single-branch (issue-only), verified not in the bug class.
- Mutation call sites that a blanket-tolerant `_graphql` would endanger: `:1043, :1128, :1170, :1340,
  :2199` (`QUERY_ADD_ITEM_TO_PROJECT` / `QUERY_SET_FIELD_VALUE` / `QUERY_ARCHIVE_ITEM`). *(P0)*
- `:3984-3986` — `create-prepared` order: create issue → `board_add` → `flow_set_field` Status;
  `:3810-3816` title + labels at create. *(CHECK-6)*
- CI test collection: `pyproject.toml:83-84`, `.github/workflows/ci.yml:42-43`. *(CHECK-8)*
- Empirical probes (this session): dual-branch on #279 → exit 1 + spurious NOT_FOUND with data
  present; `issueOrPullRequest` on #279 → exit 0, single resolved node.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md
- Source type: brainstorm
- Source title: create-prepared Partial-GraphQL-Error Defect — Resolve the Node Without a Speculative 404
