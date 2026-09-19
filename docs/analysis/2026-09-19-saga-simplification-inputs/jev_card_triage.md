# Jev second-opinion triage of open improve-claude-plugins cards

Model `jev-1.13.0`, 38 cards, one request per card with four questions, 95,681 input tokens, 347 ms mean latency. Advisory only; the main thread's own classification governs.

| Issue | Bucket | Conf | P(race) | P(review) | P(survives herdr+worktree) | Title |
|---|---|---|---|---|---|---|
| 874 | KEEP | 0.16 | 0.04 | 0.04 | 0.61 | Orchestrate protected-reference denylist misses whitespace and case variants of  |
| 875 | REWRITE | 0.24 | 0.25 | 0.04 | 0.62 | Orchestrate collect can silently regress main on a run that integrates by per-un |
| 876 | REWRITE | 0.65 | 0.14 | 0.02 | 0.70 | Orchestrate clean leaves empty lane workspaces behind and cannot release a workt |
| 878 | REWRITE | 0.12 | 0.69 | 0.04 | 0.78 | Orchestrate keeps one run record at a fixed path so a stale run blocks the next  |
| 879 | REWRITE | 0.63 | 0.06 | 0.04 | 0.77 | Orchestrate has no non-mutating plan validator so a bad plan is only discovered  |
| 885 | REWRITE | 0.92 | 0.05 | 0.96 | 0.73 | Saga Code Review: no representable closure path after cycle_cap_best_available;  |
| 886 | REWRITE | 0.80 | 0.89 | 0.16 | 0.54 | Orchestrate: relaunching a unit reuses stale worktree, strands undelivered promp |
| 891 | REWRITE | 0.62 | 0.26 | 0.05 | 0.71 | Orchestrate has no bounded multi-unit settlement watch, so an unattended run nee |
| 900 | REWRITE | 0.32 | 0.96 | 0.03 | 0.55 | Orchestrate go has no launch reservation, so a repeated call during the readines |
| 901 | REWRITE | 0.62 | 0.15 | 0.03 | 0.74 | Orchestrate go --limit is a per-invocation slice, not a concurrency cap, and wor |
| 909 | SUPERSEDE | 0.53 | 0.88 | 0.04 | 0.53 | Launch reservation and bounded unattended control: four control-surface defects  |
| 910 | REWRITE | 0.82 | 0.37 | 0.04 | 0.80 | Run record, integration, and cleanup safety: four defects as one bounded run |
| 920 | REWRITE | 0.64 | 0.09 | 0.86 | 0.81 | Saga Document Review improvement: finish the #776 transport migration, rubric re (body truncated) |
| 921 | REWRITE | 0.93 | 0.15 | 0.96 | 0.70 | Saga Code Review improvement: publication-lane integrity, canonical evidence, re (body truncated) |
| 931 | REWRITE | 0.80 | 0.04 | 0.25 | 0.88 | Saga Document Review: finish issue #776 migration — the operator-is-the-transpor |
| 932 | REWRITE | 0.57 | 0.03 | 0.75 | 0.82 | Saga Document Review: stop the rubric command degrading silently — root-relative |
| 933 | REWRITE | 0.72 | 0.04 | 0.92 | 0.77 | Saga Document Review: bounded repair with targeted verification, and an explicit |
| 934 | REWRITE | 0.90 | 0.04 | 0.34 | 0.85 | Saga Document Review maintenance: the never-written review phase, artifact-match |
| 935 | REWRITE | 0.86 | 0.10 | 0.94 | 0.65 | Saga Code Review: make the publication lane safe — bind the reviewed revision, g |
| 936 | REWRITE | 0.88 | 0.05 | 0.96 | 0.80 | Saga Code Review: make the evidence ledger canonical, preserve review_paths as h |
| 937 | REWRITE | 0.82 | 0.07 | 0.91 | 0.76 | Saga Code Review: pin review depth to an explicit tier and bind conditional-lens |
| 938 | REWRITE | 0.73 | 0.06 | 0.43 | 0.61 | Remove Work legacy in-process external-engine second-opinion offer and its featu |
| 939 | REWRITE | 0.84 | 0.05 | 0.63 | 0.85 | Saga Code Review maintenance: the Priority 0 sentence, three stale citations, th |
| 944 | REWRITE | 0.46 | 0.34 | 0.06 | 0.68 | Orchestrate erases the launcher's close-failure record and reports a live sessio |
| 946 | REWRITE | 0.93 | 0.09 | 0.96 | 0.73 | Saga Code Review: preserve cycle lineage and comparable scoring across revisions |
| 960 | REWRITE | 0.76 | 0.11 | 0.09 | 0.55 | F109: land --clean skips reaping entirely when a landing path could not be… |
| 975 | REWRITE | 0.43 | 0.06 | 0.15 | 0.77 | F124: An unknown run-file contract surfaces as a Python traceback, not the… |
| 979 | REWRITE | 0.55 | 0.54 | 0.09 | 0.55 | F128: A landing worktree whose removal fails while an exception is unwinding… |
| 988 | REWRITE | 0.50 | 0.03 | 0.14 | 0.88 | F137: redrive, a new 4.3.0 recovery command, has no dedicated explanation in… |
| 989 | REWRITE | 0.30 | 0.05 | 0.16 | 0.86 | F138: An unknown TOP-LEVEL run-file key is dropped silently and destroyed on… |
| 990 | REWRITE | 0.66 | 0.77 | 0.07 | 0.43 | F139: go does not persist the wrapper identity between the session create and… |
| 991 | REWRITE | 0.44 | 0.09 | 0.13 | 0.72 | F140: The landing-cleanup-failure test proves a different code path on each… |
| 992 | REWRITE | 0.53 | 0.08 | 0.12 | 0.73 | F141: redrive's own staged-input failure demotes the unit out of… |
| 996 | KEEP | 0.34 | 0.04 | 0.09 | 0.73 | adv09: BaseException from runpy-loaded checkout code escapes the plan_save_contr |
| 997 | KEEP | 0.49 | 0.03 | 0.11 | 0.86 | adv10: a missing PyYAML crashes plan_save_contract outside its JSON envelope and |
| 998 | KEEP | 0.72 | 0.03 | 0.11 | 0.89 | agentusab06: plan_save_proof.py has no CLI entrypoint, so --help exits 0 with em |
| 1001 | REWRITE | 0.68 | 0.04 | 0.97 | 0.85 | Saga code review consumes the generated review roster from infiquetra-sdlc's len |
| 1005 | KEEP | 0.55 | 0.04 | 0.13 | 0.79 | Saga Plan save-contract residuals carried from the issue #926 review |

## Bucket counts

- REWRITE: 32
- KEEP: 5
- SUPERSEDE: 1
