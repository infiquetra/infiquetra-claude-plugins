# Doc-review — /outcome start --from-objective (#375)

- **Target:** `docs/plans/2026-07-05-outcome-from-objective-375-plan.md`
- **Reviewed revision:** working tree (plan authored this session, pre-`/work`)
- **Blocked:** No — no P0/P1 remain after safe fixes; `/work` may proceed.
- **Linked:** issue #375; saga `issue-375`; execution-order row 7.

## Verdict

Ready to drive implementation. One P1 + two P2 gaps found and **fixed in place** (all evidence-backed);
one P3 (by-design) remains.

## Applied fixes (safe, in-place)

| # | Priority | Was | Fix | Evidence |
|---|---|---|---|---|
| F1 | P1 | KTD1/U1 named a speculative `blockedBy` GraphQL field "if available". An unknown field makes GraphQL **400 the whole query** → ingestion *breaks*, not degrades, defeating KTD1. | Relationship source is now `trackedIssues` + `timelineItems(CROSS_REFERENCED/CONNECTED)` — stable documented fields (the source the issue named) — with the relationship fetch **isolated** so any error yields empty relationships. Degradation is now real. | GitHub GraphQL rejects unknown fields; `Issue.trackedIssues`/`timelineItems`/`stateReason` are stable. Issue body names `trackedIssues`/timeline. |
| F2 | P2 | U1 said "runner injectable" but `fetch_subissues` hardcodes `subprocess.run`; the conftest no-live-gh guard blocks (doesn't return fixtures), so tests couldn't inject fixture JSON. | U1 now explicitly adds a `runner` seam to `fetch_subissues`/`fetch_objective`. | `discover_subissues.py:56` `subprocess.run(...)` has no runner param today. |
| F3 | P2 | `--from-objective` still required a separate `objective` positional even though the parent Objective's title is the objective. | U4 makes `objective` `nargs="?"`, defaulting to the parent title from normalized data when `--from-objective` is set. | `normalize()` already returns `parent.title` (`discover_subissues.py:69-71`). |

## Remaining findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P3 | Edge-inference *precision* is heuristic: `trackedIssues`/timeline cross-refs are not strict blocked-by ordering, so production edges are best-effort (fixture tests validate the pure mapper, not GraphQL→`blocked_by` fidelity). | Open (by design, KTD1) — nodes degrade to no-edges cleanly; documented. |

## Residual risk

Low. The one structural hazard (a schema-unknown GraphQL field breaking ingestion) is fixed by
restricting to stable fields + isolating the relationship fetch. Edge quality is best-effort by design;
the always-valid spec (KTD3 drops dangling/cyclic) and the no-flag regression guard (R7) bound the blast
radius.
