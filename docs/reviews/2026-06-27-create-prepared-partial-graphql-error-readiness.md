---
date: 2026-06-27
kind: doc-review
target: docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md
reviewed_revision: working tree (fixes applied on top of commit 0e0d35d)
blocked: false
---

# Readiness Review — create-prepared Partial-GraphQL-Error Defect

## Readiness summary

**READY to drive planning.** No `P0` or `P1` findings remain open. The root cause was already
verified empirically before review (the dual-branch `issue{}+pullRequest{}` resolver emits a partial
`NOT_FOUND`; `gh api graphql` exits 1 on it; `_gh` raises before the usable `data` is read; the
`board_add` resolution is unguarded). The review's work was on the **fix design**, and it forced one
real change: the recommended fix **flipped** from "relax `_graphql` to return any non-null `data`" to
"resolve the node with the `issueOrPullRequest` union so no spurious 404 is generated at all." The
core thesis (fix the resolver so `create-prepared` completes board-add + Status; guard against
recurrence; keep scope tight) survived intact.

This review ran codex (`gpt-5.5`, xhigh, read-only with repo access) and agy (`Gemini 3.1 Pro
(High)`, hermetic, doc + key code excerpts inlined) as **gated generators under Claude-side
verification** — every finding was checked against the source or a live probe before adoption. Both
engines independently flagged the original "blanket non-null `data`" predicate as a **P0** (it would
silently swallow failed *mutations* on the ~7 mutation call sites that share `_graphql`); Claude had
reached the same conclusion independently and quantified the radius (3 mutation constants), then
verified the union alternative resolves cleanly (`issueOrPullRequest(number:279)` → exit 0). codex
additionally caught that the regression test, as first written, would exercise the *dead* `_graphql`
error path rather than the real `_gh`-raises path. Each engine surfaced distinct net-new value; both
plus Claude converged on the load-bearing P0.

## Applied fixes (10)

All edits are evidence-backed (verified source, internal consistency, or a live probe).

- **Flipped the primary fix to Option B (`issueOrPullRequest`).** Verified live: the union query on
  #279 returns a single resolved `Issue` node with `gh` exit 0 and no error — so the error path needs
  no change. *(codex P1-demote + agy P1 + Claude probe)*
- **Rejected the blanket "non-null `data`" predicate (was the original primary).** Verified the shared
  `_graphql` runs mutations at `:1043, :1128, :1170, :1340, :2199`; a partial mutation failure returns
  non-null `data` with the payload `null` — blanket tolerance reports a failed write as success.
  Recorded as REJECTED with rationale so the decision is durable. *(codex P0 + agy P0 + Claude)*
- **Demoted `_graphql` relaxation to optional, strictly-scoped Option A'.** If pursued, it is opt-in
  (`allow_partial` from read-resolvers only), tolerates only `NOT_FOUND` on un-requested nullable
  paths with the target node resolved, guards `json.loads(e.stdout)`, and never applies to mutations.
  *(agy P0/P1 + codex P0)*
- **Corrected the union selection caveat (KD3).** `issueOrPullRequest` returns a union; `id` requires
  inline fragments — a bare `issueOrPullRequest { id }` is invalid. The fix also updates the
  response-access at `:1034`. *(codex P2)*
- **Rewrote the test requirements to drive the real path (KD4 / R8-R11).** The test simulates `_gh`
  raising `GhApiError(stdout=<envelope>)` (the live mechanism), not a direct `_graphql` feed (which
  hits the dead `:659` path); added negatives for fatal `data:null`, present-data-but-fatal
  (FORBIDDEN), empty/non-JSON stdout, partial mutation failure, and PR-direction symmetry. *(codex P1
  + agy P2 + Claude)*
- **Added the fail-loud + resumable requirement (KD5 / R6-R7).** A genuine post-create failure leaves
  an untracked issue today (unguarded resolve after issue creation); require fail-loud with the issue
  URL + remaining steps and a resumable re-run, **no auto-delete**. *(agy P0; couples to S-2 R18)*
- **Softened the end-to-end claim (R5).** Scoped "zero manual recovery" to board-add + Status, the two
  steps the bug actually skips; Objective stays explicitly out-of-scope (never in-flow). *(Claude;
  consistent with codex CHECK-6)*
- **Confirmed and annotated the blast-radius completeness.** `{:707, :816}` is the full dual-branch
  set; `:825` (`QUERY_GET_ISSUE_TIMELINE`) is single-branch (issue-only) — verified directly, not
  trusted from the citation. *(codex CHECK-4, Claude re-verified)*
- **Confirmed `flow_set_field` does not independently break.** It resolves via `get_project_items`
  (matching `content.number`), not a dual-branch by-number lookup — so once `board_add` is fixed,
  Status-setting needs no further change. *(Claude)*
- **Added the live union probe + the rejected-mutation rationale to Sources.** So the next reader sees
  the exit-0 evidence and the mutation call-site list without re-deriving them.

## Findings by priority

| Pri | Finding | Source | Status |
|-----|---------|--------|--------|
| P0 | Blanket "non-null `data`" masks failed mutations (`:1043, :2199`, …) | codex + agy + claude | Fixed (flip to Option B) |
| P0 | Field-level error (`data.repository:null` + FORBIDDEN) → downstream `TypeError` | agy | Fixed (predicate rejected) |
| P0 | Unguarded resolve leaves an untracked issue on genuine failure | agy | Fixed (R6/R7 fail-loud + resumable) |
| P1 | Regression fixture tested the dead `_graphql` path, not the `_gh`-raises path | codex | Fixed (R8 drives real path) |
| P1 | `json.loads(e.stdout)` crashes/masks on empty/non-JSON stdout | agy | Fixed (R9c + A' guard) |
| P1 | Option B wrongly demoted to "hardening" | agy | Fixed (now primary) |
| P2 | Union `id` selection caveat under-specified | codex | Fixed (KD3) |
| P2 | Negative test for present-data-but-fatal missing | agy | Fixed (R9b) |
| P3 | Objective / title out-of-scope | codex + agy + claude | Verified SOUND (kept) |
| P3 | CHECK-1/2/4/6/7/8 citations | codex | Verified true |

## Residual risk from limited evidence

Low. The primary fix is the most-correct GitHub-GraphQL idiom and was validated with a live exit-0
probe against a real issue; it changes two query constants and one response-access line and touches
no error-handling or mutation code. The genuine sizing risk is concentrated in KD5's
fail-loud/resumable guard (new control flow on a boundary with a known recurring defect) — located and
scoped by R6/R7, with the resumability mechanism deferred to `/plan`. The test obligation is tractable:
the partial-error and union responses are both captured verbatim here as golden fixtures.

## Scope observation (operator's call, not a blocker)

The fix is genuinely small (Option B), but the review added net-new build surface in two places the
first draft under-scoped: the **test suite** (R8-R11 — the bug recurred 4× *silently*, so the negative
cases earn their keep) and the **fail-loud/resumable guard** (R6/R7 — strictly more than "swap the
query," but it is the difference between a fix and a fix that survives the next network blip on this
boundary). Both are defensible for a defect that has cost four manual recoveries; neither is required
for the core query swap if the operator wants the minimal cut. Stated plainly so `/plan` can choose.
