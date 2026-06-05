# PR Continuation Loop — how the round-N loop runs after PR-ready

`/work` does not dead-end at PR-ready. It **owns the round-N continuation loop** around the PR, driven by
the saga's round spine and the `destination` field. Every outward mutation is offered/confirmed, never
silent. Deploy and canary belong to `deploy`. `/work` owns its own re-entry — it does **not**
depend on `/resume` being rebuilt.

## Re-entry detection (SKILL Phase 0.4)

When `/work` is invoked and the matched/restored work-thread saga has a populated `pr_refs`, this is a
re-entry. Read the **total** live PR state before deciding anything:

```bash
gh pr view <N> --json state,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,isDraft,mergedAt
```

- `state` — `OPEN` / `MERGED` / `CLOSED`.
- `reviewDecision` — `""` (none) / `REVIEW_REQUIRED` / `CHANGES_REQUESTED` / `APPROVED`.
- `mergeable` — `MERGEABLE` / `CONFLICTING` / `UNKNOWN`.
- `mergeStateStatus` — `CLEAN` / `BLOCKED` / `UNSTABLE` / `DIRTY` / `BEHIND` / `DRAFT` / `HAS_HOOKS`.
- `statusCheckRollup` — the per-check states; "all success" means every required check passed.
- `isDraft` — true while the PR is a draft.
- `mergedAt` — non-null once merged.

## Total transition table

Evaluate in order; the first matching row wins.

| PR condition | `/work` action |
|---|---|
| `isDraft` is true | Offer "mark ready" (`gh pr ready`) before requesting review. Do **not** request review on a draft. |
| `state=OPEN`, `reviewDecision` empty or `REVIEW_REQUIRED` | **Pause** — set `next_step="await review on PR #N"`. No merge offer; review has not happened yet. |
| `state=OPEN`, `reviewDecision=CHANGES_REQUESTED` (or unresolved threads) | **Round N+1**: address the requested changes (re-execute affected units via Phases 2-5), re-run the test + review gates, re-push, re-request review. Tick with the round bumped. |
| `state=OPEN`, checks pending/failing (`statusCheckRollup` not all-success, or `mergeStateStatus ∈ {BLOCKED, UNSTABLE}`) | **Do NOT offer merge.** Route to fix (round N+1) if a check is red, or pause and wait if checks are still running. |
| `state=OPEN`, not mergeable (`mergeable=CONFLICTING` or `mergeStateStatus=DIRTY`) | **Round N+1**: offer to rebase/resolve against the base, re-run the gates, re-push. Tick with the round bumped. |
| `state=OPEN`, `reviewDecision=APPROVED`, checks clean, mergeable, **stale** (commits since the reviewed SHA — see test-and-gates.md) | **Re-run `/code-review`** (the staleness gate) before any merge offer. Do not merge on a review that predates the current HEAD. |
| `state=OPEN`, `reviewDecision=APPROVED`, checks clean, mergeable, **fresh** | If `destination ⊇ merge` → **offer `gh pr merge`** (explicitly confirmed). If `destination=pr` → set `status=done`, advisory route to `/qa`. |
| `state=MERGED` (`mergedAt` non-null) | Set `phase_status=complete`; advisory route to `/qa`. If `destination=nonprod-deploy`, route `/qa` → then `deploy`. **Leave `lifecycle_phase=work`** (see qa-deferral). |
| `state=CLOSED` unmerged | **Ask the operator** (pause vs abandon) and save the chosen `status` (`paused` or `abandoned`). |

## Round bump (via `rounds_seen`, never `next_round`)

When a row drives a new round (CHANGES_REQUESTED, conflicting, failing checks), bump the round by passing
the full observed set to `--rounds-seen` on the next `save` (e.g. round 1 → `--rounds-seen "1|2"`). The
engine derives `next_round = max(rounds_seen) + 1` at save time (saga-spec §6.1) — **never set
`next_round` directly**; it is a derived field. Each round re-enters Phases 2-5 with the incremented round
and re-runs the test + review gates from scratch (re-verify, don't trust the prior round's evidence).

## Merge is a confirmed git op `/work` owns

When `destination ⊇ merge` and the approved-fresh row fires, `/work` performs the merge itself — but only
as an **explicitly operator-confirmed** `gh pr merge`, never silent. There is no separate "git/human"
skill; merge is a git op `/work` owns under confirmation (saga-spec §1.1 keeps deploy as deploy's hard
boundary, but merge is a git operation, not a deployment). Use the repo's merge method; respect branch
protections (if the operator cannot merge, hand back the PR and stop).

## Deploy / canary belong to deploy

`/work` never deploys, never runs canary verification, and never performs a production-health revert.
gstack's `land-and-deploy` canary-verify + offer-revert capability — **and its first-run deploy dry-run**
(platform / prod-URL / deploy-workflow detection) — are **relocated to `deploy`** (read here so
they are relocated knowingly, not dropped silently; both are deploy-infrastructure concerns, not `/work`'s).
When `destination=nonprod-deploy`, the route after merge is `/qa` (ship-readiness) → `deploy`
(deployment mutation + dry-run + canary + production revert). `/work` records the `destination` intent and
`pr_refs`; deploy owns the mutation.

## Advisory routing + the qa-deferral

`/qa` is now the shipped **gate-only** engine (0.13.0) and is the saga's qa-track consumer — it
`restore`s the work-thread and, on a PASS verdict, advances `lifecycle_phase` `work`→`qa` (the advance
this rebuild deferred to it). `/work`'s own behavior on merge is unchanged: it sets
`phase_status=complete` and `next_step="run /qa (ship-readiness)"` and routes to `/qa` **advisorily**,
but **leaves `lifecycle_phase=work`** — it does **not** claim "/qa owns/advances the qa slot" from inside
`/work`; the advance happens when `/qa` actually runs and passes. The saga legitimately sits at `work`
post-merge until `/qa` lands the advance; `/handoff` deriving `resume-ready` for that state is correct
(the thread *is* resume-ready-into-qa).

Likewise **`/resume` routing is advisory**. `/work`'s own Phase-0.4 re-entry (this file) is the
load-bearing "come back later" mechanism — it does not depend on the `/resume` stub being rebuilt. A
re-invocation of `/work` on a saga with `pr_refs` re-runs this transition table; that is the durable loop.

## Saga writes summary (this loop)

- `pr_refs` — set when the PR is opened (SKILL Phase 5.4).
- `next_step` — the imperative resume anchor for each paused state ("await review on PR #N").
- `rounds_seen` — the full observed round set; drives the derived `next_round`.
- `status` — `done` on a clean `destination=pr` completion or post-merge thread close; `paused` /
  `abandoned` on CLOSED-unmerged per the operator.
- `phase_status=complete` — on merge.
- `lifecycle_phase` — stays `work` throughout (never advanced past `work` here — the qa-advance is
  deferred to the `/qa` rebuild).
