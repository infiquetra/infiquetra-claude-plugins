---
date: 2026-06-27
kind: brainstorm
maturity: requirements-ready
type: defect
source: field-observed defect — 4/4 across issue creations #275, #277, #278, #279 (VECU port-seeds campaign)
title: "create-prepared dies on a partial GraphQL NOT_FOUND — board-add + Status silently skipped"
---

# create-prepared Partial-GraphQL-Error Defect — One Fix for the Whole Dual-Branch Class

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

The fix is a single, general correction at the `_graphql` seam: **a GraphQL response that carries a
non-null `data` payload is a partial success, not a failure** — return the data and let the existing
`issue or pullRequest` fallback (`:1034`) work. This protects the entire class of dual-branch queries
(there is a second one, `QUERY_GET_ITEM_LABELS`, `:816-823`) at once.

## Observed behavior (reproduction)

Every `create-prepared` run in the campaign produced:

```
ERROR: gh command failed: gh: Could not resolve to a PullRequest with the number of N.
```

After which:
- **Issue IS created** (with title + labels) — created at `_create_github_issue` (`:3984`), labels
  applied at `gh issue create --label` (`:3815-3816`), both *before* the failing call.
- **Board-add skipped**, **Status not set**, **Objective not set** — all are *after* the failing
  `board_add` (`:3985`) in the create flow (`flow_set_field` Status at `:3986`).
- Operator recovers manually: `gh project item-add 3 --owner infiquetra --url <issue-url>` +
  `flow set-field --field Status --option Todo` (+ `--field Objective --option improve-claude-plugins`,
  which is a *separate* gap — see Scope Boundaries).

### Empirical proof (captured this session — read-only probe against issue #279)

`gh api graphql` querying #279 as **both** issue and pullRequest:

```
EXIT_CODE=1
STDOUT: {"data":{"repository":{"issue":{"id":"I_kwDOQdql-c8AAAABG68biw","number":279},
         "pullRequest":null}},
         "errors":[{"type":"NOT_FOUND","path":["repository","pullRequest"],
         "message":"Could not resolve to a PullRequest with the number of 279."}]}
STDERR: gh: Could not resolve to a PullRequest with the number of 279.
```

The `data.repository.issue` node is fully resolved (`id` present); `pullRequest` is `null`; the only
error is a `NOT_FOUND` on the `pullRequest` path. `gh` still exits **1**.

## Root cause (two layers, both real)

1. **`_gh` raises on the non-zero exit (`:632-640`).** `gh api graphql` exits 1 on a partial error.
   `_gh` calls `_classify_gh_error(...)` → no `HTTP NNN` line in stderr, so it falls through to
   `GhApiError(full, status_code=None, ...)` (`:606`). The exception *carries* the usable stdout
   (`stdout=result.stdout`, `:639`) but the caller never reads it.
2. **`_graphql`'s own fatal-on-`errors` check (`:659-660`)** is the same mistake one layer up:
   `if "errors" in data: raise`. It is currently *dead code for this path* (because `_gh` raises
   first), but it would re-trigger the identical bug the moment `_gh` is taught to return stdout — so
   the fix must address the seam, not just one line.
3. **`board_add` resolves the node id unguarded.** `_graphql(QUERY_GET_ITEM_NODE_ID, …)` at `:1032`
   is *before* the `for proj in projects:` loop; the try/except (`:1042-1057`) only wraps the
   per-project add. So the resolution exception propagates and aborts `create-prepared`.

The dual-branch query is *intentional* (`:1034` does `repo_data.get("issue") or
repo_data.get("pullRequest")` so one helper resolves either kind). The design is fine; the error
handling underneath it is wrong — it treats GraphQL's normal partial-success contract as fatal.

## Blast radius

Every `_graphql` call whose query selects a speculative branch that may not resolve:
- **`QUERY_GET_ITEM_NODE_ID`** (`:707-714`) — the hot path; hit by `board_add` on **every** issue.
- **`QUERY_GET_ITEM_LABELS`** (`:816-823`) — same `issue {…} pullRequest {…}` dual-branch shape;
  hit by the label-field sync path (`_get_item_labels` → `_sync_label_fields_for_item`, `:1311`).

A fix at the `_graphql` layer covers both (and any future dual-branch query) in one place. A
per-query fix would have to be repeated and would silently regress the next time someone adds a
dual-branch query.

## Key decisions

- **KD1 — Fix at the `_graphql` seam, not per-query.** The defect is a general mishandling of
  GraphQL partial success; the correct layer is the one shared helper. Per-query rewrites leave the
  class open.
- **KD2 — "Non-null `data` ⇒ partial success" is the principled predicate.** Per the GraphQL spec,
  `data` is present (and may contain `null` sub-fields) when execution *partially* succeeded; `data`
  is `null`/absent for request-level failures (auth, bad syntax, rate limit). So: **if the response
  parses and `data` is non-null, return it; only raise when `data` is null/absent.** This keeps every
  genuinely-fatal error fatal.
- **KD3 — Keep `_gh` strict; do the partial-tolerance in `_graphql`.** `_gh` is the shared shim for
  *all* gh calls (REST included); loosening its non-zero-exit handling has a wide blast radius and
  could mask real failures. The exception already carries `stdout` (`:639`), so `_graphql` can catch
  the typed error, parse `e.stdout`, and apply KD2 — a change contained to one function.
- **KD4 — The recommended fix is verifiable by a golden fixture.** The exact partial-error JSON above
  is the regression fixture: feed it to `_graphql`, assert it returns `data` (issue node) instead of
  raising. This is the anti-recurrence guarantee, and the defect has earned one (4 silent recurrences).
- **KD5 — Scope to the partial-error bug only.** Objective-not-set and any title concerns are *not*
  this defect (see Scope Boundaries) — folding them in would turn a contained fix into a feature.

## Fix options

**Option A — Partial-tolerant `_graphql` (recommended, primary).**
`_graphql` wraps the `_gh` call; on a typed `GhApiError`, it parses `e.stdout` and, if the JSON has a
non-null `data`, returns `data` (partial tolerated per KD2); otherwise re-raises. Also relax the
existing `:659` check the same way (return data when `data` present, raise only when absent), so the
two layers agree.
- *Pros*: one-function change; fixes the whole dual-branch class (both known queries + future ones);
  preserves `_gh` strictness for every other caller; directly testable with the captured fixture.
- *Cons*: needs the fatal-vs-partial predicate to be exactly right (KD2 gives it); relies on the
  exception carrying stdout (it does, `:639`).

**Option B — `issueOrPullRequest` single-branch query (recommended, complementary hardening).**
Replace the `issue {…} pullRequest {…}` dual-branch in `QUERY_GET_ITEM_NODE_ID` (and optionally
`QUERY_GET_ITEM_LABELS`) with GitHub's union field `issueOrPullRequest(number:$number){ … on Issue
{id} … on PullRequest {id} }`, which resolves whichever exists **without** emitting a partial error.
- *Pros*: removes the spurious error at the source for the hot path → cleaner logs, no reliance on
  partial-tolerance for the most common op; more correct.
- *Cons*: per-query (must be applied to each dual-branch query); does **not** by itself fix the class
  (a future dual-branch query still breaks) — so it complements A, it does not replace it. Needs the
  `id` to be selectable on the union (it is — both `Issue` and `PullRequest` expose `id`).

**Option C — `_gh` graphql-aware non-zero handling (rejected).**
Teach `_gh` that for `api graphql` a non-zero exit with parseable `data` is non-fatal and return
stdout. Rejected: `_gh` is the shared shim; widening its success criteria risks masking real
failures across REST and every other call site. KD3 keeps it strict.

## Recommended fix

**A (primary) + B for the hot path (hardening).** A is the load-bearing, class-closing fix and the
one the regression fixture guards. B additionally makes `board_add`'s common path stop generating the
spurious error at all. The exact fatal-vs-partial predicate (KD2) is the one decision to confirm in
`/plan`.

## Requirements

**Correctness (the fix):**
- **R1** — `_graphql` returns the response's `data` when `data` is non-null, even if the response
  also carries an `errors[]` array (partial success), instead of raising. *(Option A)*
- **R2** — `_graphql` still raises (typed, unchanged) when the response has no usable `data` —
  request-level failures: auth (401/403), rate limit (429), bad syntax, or `data: null`. *(KD2)*
- **R3** — the fix lives in the shared `_graphql` helper (and its agreement with `_gh`'s exception
  stdout), not in individual queries, so it covers `QUERY_GET_ITEM_NODE_ID` **and**
  `QUERY_GET_ITEM_LABELS` and any future dual-branch query. *(KD1)*
- **R4** — `_gh` remains strict for all non-graphql callers; no REST call site changes behavior. *(KD3)*

**End-to-end (the user-visible outcome):**
- **R5** — `create-prepared` on a fresh issue adds it to the target project board **and** sets Status
  with **zero** manual recovery steps. *(the actual bug)*
- **R6** — `board_add` and the label-field sync resolve an issue node id without raising on the
  absent-PR branch. *(hot path + `:816` path)*

**Anti-recurrence:**
- **R7** — a regression fixture reproduces the captured partial-error response shape
  (`{"data":{… "issue":{…}, "pullRequest":null}}, "errors":[{"type":"NOT_FOUND",…}]}`) and asserts
  `_graphql` returns the issue node rather than raising. *(KD4)*
- **R8** — a test asserts a genuinely fatal response (`data: null` + errors) **still** raises, so the
  fix doesn't swallow real failures. *(R2 guard)*
- **R9** — an end-to-end test (mocked `_gh`) asserts `board_add` succeeds against a partial-error
  resolution response. *(R5/R6 guard)*

## Acceptance examples

- **AE1** — Given the captured `#279` partial-error JSON, `_graphql(QUERY_GET_ITEM_NODE_ID, …)`
  returns `{"repository":{"issue":{"id":"…","number":279},"pullRequest":null}}` (no raise). *(R1)*
- **AE2** — Given a fresh prepared draft, `create-prepared --yes` creates the issue, adds it to the
  board, and sets Status=Todo with no manual `gh project item-add` / `flow set-field` needed. *(R5)*
- **AE3** — Given a response with `data: null` and an auth error, `_graphql` raises the typed
  `ApiAuthError` exactly as today. *(R2/R8)*
- **AE4** — Given a number that **is** a PR, the same resolver returns the `pullRequest` node and the
  `issue` branch's `NOT_FOUND` is tolerated (symmetry). *(R1, dual-branch both directions)*

## Scope boundaries

- **IN**: the partial-GraphQL-error mishandling at the `_graphql`/`_gh` seam; the dual-branch node-id
  and label queries; the regression + e2e fixtures.
- **OUT — Objective not auto-set.** `create-prepared` never set the Objective field (it sets only
  Status, `:3986`); the manual `--field Objective` step is a *missing feature*, not a regression. A
  separate enhancement (auto-set a configured Objective from the draft sidecar) — do not fold in.
- **OUT — title recovery.** Title is set at create (`--title`, `:3810-3811`); any title re-edit in the
  manual recovery was operator discretion, not a code defect.
- **OUT — `deploy-templates` 404s.** Separate, non-fatal, independent of this seam.

## Dependencies / assumptions

- Assumes `GhApiError` carries `stdout` (verified, `:639`) so Option A can read the response off the
  exception without changing `_gh`.
- Assumes GitHub GraphQL's documented partial-success contract (non-null `data` alongside
  `errors[]`) — verified empirically this session against a live response.
- Test harness: repo-root `tests/` (collected by CI); proposed `tests/test_graphql_partial_error.py`.

## Outstanding questions (deferred to /plan)

1. Exact KD2 predicate boundary: "any non-null `data`" vs the stricter "non-null `data` **and** every
   error is `type: NOT_FOUND`". The former is simpler and spec-aligned; the latter is more
   conservative but risks over-tightening if GitHub varies the error `type`.
2. Whether to refactor `_graphql` in place vs add a `_graphql` that returns `(data, errors)` and a
   thin partial-tolerant wrapper — an internal-shape decision.
3. Whether to adopt `issueOrPullRequest` (Option B) for **both** dual-branch queries or only the hot
   path in v1.

## Coupling note (why this matters now)

This defect lives on the **saga ↔ mission-control write boundary** — exactly the boundary that S-2
(reversibility/idempotency certificate, issue #279) proposes to make *autonomous*. S-2's R18 already
names "bounded-retry + fail-loud on the create-prepared boundary." You cannot ship reliable
autonomous board-sync over a resolver that misfires on every issue. Fixing this is effectively a
near-dependency of S-2, not just hygiene.

## Sources

- `plugins/mission-control/scripts/sdlc_manager.py:649-661` — `_graphql`, fatal-on-`errors`.
- `:617-646` — `_gh`, raises typed error on non-zero exit; carries stdout at `:639`.
- `:559-606` — `_classify_gh_error`; no HTTP status ⇒ `GhApiError(status_code=None)` at `:606`.
- `:707-714` — `QUERY_GET_ITEM_NODE_ID` dual-branch; `:1032`/`:1034` — `board_add` resolution +
  `issue or pullRequest` fallback; `:1042-1057` — try/except wraps only the per-project loop.
- `:816-823` — `QUERY_GET_ITEM_LABELS`, the second dual-branch query.
- `:3984-3986` — `create-prepared` order: create issue → `board_add` → `flow_set_field` Status.
- Empirical probe (this session): `gh api graphql` on #279 → exit 1, `data.issue` populated,
  `pullRequest: null`, `errors:[NOT_FOUND]`.
