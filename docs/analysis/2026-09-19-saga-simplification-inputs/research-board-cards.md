# Operations board cards vs. the simplification direction

Scope: the 87 GitHub issues on the Operations board (GitHub project 3, owner `infiquetra`) under
the Objective field `improve-claude-plugins` — 38 open, 49 closed — reviewed against Jeff's
five-point simplification direction for the saga plugin family. Per-card classification for Jeff's
review; the main thread makes the final call.

**Method note.** Board status and issue state came from the two pre-fetched files
(`improve-issues.json`, `improve-cards.tsv`). Every *shipped* claim was checked against `git log
origin/main` and each plugin's `CHANGELOG.md`, not issue-body prose — several bodies predate their
own closure by hours and say nothing about what shipped.

## Direction, in shorthand used below

Jeff's five decisions for the saga plugin family (Claude Code plugins — saga, orchestrate,
agent-launcher, team-execution, mission-control — that run Infiquetra's software development
lifecycle, the standard sequence of planning, building, reviewing, and shipping code). Each is
named once here and referenced by name in the reasoning column below:

- **guidance-not-gates** — lifecycle commands stay but stop refusing or gating; they become
  automatic guidance the model follows.
- **mechanical review** — which review lenses (a lens is one reviewer perspective, such as security
  or correctness) apply is decided up front from the shape of the change, with help from TypeSafe's
  Jev — a "System One" model from the TypeSafe product that turns application state into a typed,
  structured judgment a program can act on — for the mechanical decisions.
- **build-then-review** — implement, deploy, and test loop until working software exists; only then
  does code review run.
- **herdr-roles** — team-execution's own spawning/ordering/gating machinery is removed; its roles
  (reviewer, scanner, tester, validator, monitor) survive only as prompts run in separate herdr
  (Jeff's terminal-workspace manager for coding agents) panes, across whichever tool runs there.
- **worktree-merge** — race, lease, launch-reservation, and double-dispatch protections are replaced
  by one git worktree (an independent working copy of the repository) and branch per unit, merged
  with ordinary git merge.

Severity labels below (Priority 0 through Priority 3, P0-P3) are the review tooling's own severity
ladder, most severe first. A code such as `F109` or `adv09` is an internal finding label, described
in plain language first, code given parenthetically for traceability.

## 1. The 38 open issues

Grouped into the five clusters the issues themselves already use (each parent names its own
children; the grouping is exhaustive and non-overlapping across all 38). Buckets: **KEEP** —
concern and fix both stay valid. **REWRITE** — the concern stays valid, but the fix targets
machinery the direction changes. **SUPERSEDE** — the fix only touches machinery the direction
removes. **UNRELATED** — not about these plugins or this direction (none of the 38 qualify).

### Cluster A — Orchestrate launch, relaunch, and recovery control surface (9 issues)

Grouped under issue 909, which calls issues 1002/1003 "adjacent, not yet fixed" — both shipped
2026-09-16 (section 2 below), so that's stale.

| # | Board | Type | Component | Problem | Prescribed fix | Machinery | Bucket | Reasoning (≤25 words) |
|---|---|---|---|---|---|---|---|---|
| 909 | Discovering | capability | orchestrate | Grouping parent for eight launch/relaunch/recovery defects, still written as a full run contract despite disclaiming run authority. | Serialize the four children, claim-field fix first. | run-contract ceremony; launch reservation | REWRITE | Grouping helps; the serialization/claim-field ceremony is the coordination overhead worktree-merge removes by isolating every unit. |
| 879 | Discovering | enhancement | orchestrate | A bad plan is only caught by starting a run, after worktrees and a run record already exist. | Add a non-mutating check running `start`'s own validation. | plan validation (dry run) | KEEP | Dry-run validation before mutating anything is plain hygiene, independent of the race or gate model in use. |
| 886 | Capturing | none | orchestrate | Relaunch reuses a stale worktree without fast-forwarding, can spawn duplicate live sessions per lifecycle, and drops unrecognized run-record fields. | Fast-forward or refuse a reused worktree, adopt or close the prior session, preserve unknown fields. | worktree reuse on relaunch; duplicate sessions | SUPERSEDE | These hazards exist only because relaunch mutates a shared worktree; worktree-merge gives every launch a fresh one. |
| 891 | Capturing | enhancement | orchestrate | Orchestrate watches only one running unit at a time, so a long unattended run can't notice every finished worker. | Add a bounded, multi-unit settlement watch, no daemon. | settlement/readiness watch | SUPERSEDE | Built for unattended multi-wave campaigns; herdr-roles has Jeff watching panes directly, removing the watch surface's purpose. |
| 900 | Capturing | defect | orchestrate | `go` claims a unit only after launch, so a repeated call in the launch window can double-launch into one worktree. | Write a durable claim before launching; exclude claimed units from eligibility. | launch reservation | SUPERSEDE | The double-launch race is structurally impossible once every launch gets its own fresh, isolated worktree. |
| 901 | Capturing | defect | orchestrate | `--limit` reads like a concurrency cap but only slices one call's launches, so a polling caller can exceed its intended cap. | Add a real total-concurrency ceiling separate from `--limit`, and document a bounded loop. | concurrency ceiling; driving-loop semantics | SUPERSEDE | Guards an automated polling driver; herdr-roles replaces that driver with Jeff running each pane by hand. |
| 988 | Capturing | none | orchestrate | `redrive --unit`, the one recovery command for a stuck unit, appears only as a bare, unexplained name. | Give `redrive` its own documented section. | redrive documentation | KEEP | A plain documentation gap; unrelated to races, gates, or team-execution's structure. |
| 990 | Capturing | defect | orchestrate | `go` doesn't persist a launched session's identity until after delivery, so an interrupt mid-window shows the unit unlaunched. | Persist session identity immediately on creation. | launch-record persistence; relaunch race | SUPERSEDE | A second `go` launching into the same worktree is the double-dispatch case worktree-merge makes impossible. |
| 992 | Capturing | defect | orchestrate | When `redrive` itself fails, it demotes the unit out of the one state its door can act on, so the next `redrive` refuses it. | Don't clear the recoverable state on a failed attempt. | redrive; prompt_undelivered state machine | KEEP | A state-machine bug in a recovery command, not a concurrency protection; needed under any model keeping `redrive`. |

*Issue 886 has five numbered findings, not one fate: §1/§3 drive the SUPERSEDE bucket above; §5
(`.orchestrate/` unreachable from a unit's worktree) is a residual KEEP nothing else covers; §4
duplicates issue 989 below; §2 mostly shipped via `redrive` and issue 1002 (closed).*

### Cluster B — Orchestrate run record, integration, and cleanup safety (11 issues)

Grouped under issue 910 — mostly plumbing beneath the worktree-per-unit model itself, so it stays
relevant regardless of the coordination layer on top.

| # | Board | Type | Component | Problem | Prescribed fix | Machinery | Bucket | Reasoning (≤25 words) |
|---|---|---|---|---|---|---|---|---|
| 910 | Discovering | capability | orchestrate | Grouping parent for ten defects in branch-deletion safety, run-branch integration, cleanup, and the run-record file; carries ordering rules as if live. | Deliver the four children in order, run-record last. | run-contract ceremony | REWRITE | Grouping real defects helps; the serialization order is what worktree-merge replaces with independent per-unit branches. |
| 874 | Discovering | defect | orchestrate | The `main`-deletion guard strips whitespace and normalizes case in the wrong order, so a stray-prefixed or differently-cased name slips past. | Casefold and strip whitespace before every comparison. | protected-branch denylist | KEEP | A plain string-normalization bug in a delete-safety check; unrelated to concurrency or gating models. |
| 875 | Discovering | defect | orchestrate | `collect` merges a run's branch with no currency check, so on a per-unit-pull-request run it can silently revert work on `main`. | Refuse the merge when it would revert a newer file, naming the files. | run-branch collect; merge regression guard | REWRITE | Real revert risk, but tied to run-branch-then-collect; worktree-merge should fold this into ordinary-merge guidance. |
| 876 | Discovering | enhancement | orchestrate | Cleanup never retires the herdr workspaces it created, and can't release a worktree at merge time, so branch deletion fails. | Retire empty run-created workspaces; release a worktree once it merges. | worktree/workspace cleanup | KEEP | Ordinary worktree-lifecycle hygiene any one-worktree-per-unit model still needs; git's own delete-blocks-on-worktree rule doesn't change. |
| 878 | Discovering | enhancement | orchestrate | One run record at a fixed path means a finished run blocks the next; two runs can't coexist. | Let a run be selected by name; unnamed calls unchanged. | run record (single fixed-path file) | KEEP | A plain resource-singleton bug; matters only if orchestrate keeps grouping units into shared campaign records. |
| 944 | Capturing | defect | orchestrate | Orchestrate discards the launcher's close-failure record in two places, so a still-running session reports as cleanly closed. | Keep the failure note; fail the sweep instead of reporting false success. | close-failure bookkeeping | KEEP | Plain data-loss bug in status reporting; unrelated to launch races, gates, or team-execution. |
| 960 | Capturing | defect | orchestrate | Finding F109: `land --clean` hitting one unremovable path silently skips cleanup for every unit just merged. | Run cleanup regardless of the earlier exit; name any unit left uncleaned. | land / reap reporting | KEEP | A reporting-discipline bug in post-merge cleanup; independent of race protection or review-ceremony changes. |
| 975 | Capturing | none | orchestrate | Finding F124: an unrecognized run-file version prints a raw Python error instead of the tool's usual one-line refusal. | Catch the error; print the same one-line refusal style used elsewhere. | run-file error handling | KEEP | An error-message-quality bug; the refusal logic is already correct and untouched by the direction. |
| 979 | Capturing | defect | orchestrate | Finding F128: a worktree-delete failure mid-exception is recorded where the failure-reporting code never reads it, so it's never named. | Run failure reporting even mid-exception; remove the git call that can itself raise. | landing cleanup; exception handling | KEEP | A reliability bug in cleanup error handling; not a concurrency protection, untouched by the direction. |
| 989 | Capturing | none | orchestrate | Finding F138: an unrecognized top-level run-file field is silently deleted on save, unlike a unit-row field, which warns. | Preserve unrecognized top-level fields across save. | run-record field preservation | KEEP | Silent data loss on save is a plain durability bug; matters as much under a simplified run record. |
| 991 | Capturing | none | orchestrate | Finding F140: the cleanup-failure test exercises a different failure mechanism per operating system, so a one-platform defect can pass CI, and leaves undeletable directories. | Force the same failure mechanism everywhere; clean up fully. | test-fixture reliability | KEEP | Test-quality hygiene, unrelated to gates, races, team-execution, or review-ceremony changes. |

### Cluster C — Saga Document Review improvement (5 issues)

Grouped under issue 920, the one sibling parent never given the 2026-09-13 "backlog grouping, not
a run" retirement note 909/910/921 got — worth fixing alongside the rewrite below.

| # | Board | Type | Component | Problem | Prescribed fix | Machinery | Bucket | Reasoning (≤25 words) |
|---|---|---|---|---|---|---|---|---|
| 920 | Ready for Planning | capability | saga-doc-review | Grouping parent for four Document Review fixes, still written as a fully staffed run with fixed membership. | Deliver the four children in order; they share one file. | run-contract ceremony; plan review | REWRITE | Guidance-not-gates keeps plan review itself; the run-contract wrapper, inconsistent with its sibling parents, should go. |
| 931 | Ready for Planning | defect | saga-doc-review | Document Review prohibits two deleted scripts by name, its cross-reference targets a dead contract, and the guarding test checks only the string. | Copy Code Review's general prohibition wording; check the target exists. | transport clause; prohibition wording | KEEP | Finishing an already-closed migration and fixing an unfalsifiable test; unrelated to guidance, mechanical review, or worktrees. |
| 932 | Ready for Planning | defect | saga-doc-review | The rubric-loading command only resolves from one directory, and a missing rubric silently continues the review weaker. | Resolve from any directory; fail loudly instead of degrading silently. | rubric command | KEEP | A silent-failure bug in a blocking gate is dangerous under any model; guidance-not-gates makes visible failure more necessary. |
| 933 | Ready for Planning | enhancement | saga-doc-review | Document Review has no repair-and-reverify protocol, and an explicitly submitted spec document can be silently redirected instead of reviewed. | One repair pass and re-check; a second model confirms unattended top-severity clearance; always honor an explicit request. | bounded repair protocol; P0-blocks-work gate | REWRITE | Guidance-not-gates wants steps to stop hard-refusing; "still blocks /work" should soften into guidance, not a tooling refusal. |
| 934 | Ready for Planning | enhancement | saga-doc-review | Document Review's docs describe a lifecycle stage it never enters, an undefined artifact-matching rule, and a stale rubric-engine path and line count. | Correct all three to match actual behavior. | doc-review maintenance | KEEP | Pure documentation accuracy; nothing depends on gates, mechanical review, the build-loop order, or worktrees. |

### Cluster D — Saga Code Review improvement (9 issues)

Grouped under issue 921, which calls issue 908 and issues 892-895/898/899/902 open, "do not
duplicate" — that family closed 2026-09-17 (section 2). This is where the direction bites hardest,
and it holds issue 1001, the closest match to mechanical review (section 5).

| # | Board | Type | Component | Problem | Prescribed fix | Machinery | Bucket | Reasoning (≤25 words) |
|---|---|---|---|---|---|---|---|---|
| 921 | Ready for Planning | capability | saga-code-review | Grouping parent for eight Code Review fixes, covering a publication feature actively corrupting its own freshness guarantee. | Land the publication-safety fix first; ledger, tier, second-opinion removal after. | run-contract ceremony; code review | REWRITE | The grouping and the urgent bug are real; the run-contract's ordering prose is what worktree-merge dissolves. |
| 935 | Ready for Planning | defect | saga-code-review | Publishing a review moves the branch forward, breaking a freshness check two tools rely on, and the evidence file never lands. | Bind the revision to the code commit; land the evidence file; publish only as a comment plus one go-ahead. | publication lane; evidence ledger | KEEP | Fixes a live, confirmed bug; the go-ahead step reads as guidance, not a refusal, surviving guidance-not-gates. |
| 936 | Ready for Planning | defect | saga-code-review | Two consumers misread a review's verdict: the closure check misses its vocabulary, and status guesses from prose instead of the field. | Make the evidence file authoritative, keep history, read the structured field first. | evidence ledger; review_result schema | KEEP | Plain producer/consumer data-contract fix; unaffected by whether lens selection is mechanical, adaptive, or worktree-based. |
| 937 | Ready for Planning | enhancement | saga-code-review | Reviewer models run at whatever hosts the session, not a deliberate choice, and an approved lens silently carries onto a later commit. | Resolve every seat from an explicit tier; re-show the prior lens choice on a new commit. | reviewer tier; lens roster | REWRITE | Explicit tier resolution fits mechanical review; per-commit manual reconfirmation should become mechanical up-front selection instead. |
| 938 | Ready for Planning | enhancement | saga-code-review | Saga Work still offers an older in-process second-opinion request, with its own dispatch/sidecar/state machinery, after a richer model replaced it. | Remove the offer and private machinery; keep only shared components with live consumers. | second-opinion offer | KEEP | Already matches herdr-roles' replacement of in-process second opinions; note its cited team-execution validator may itself disappear. |
| 939 | Ready for Planning | enhancement | saga-code-review | Documentation has stale citations, one name used for two things, no sentence on how a top finding forces a failing score, and no dedup. | Correct citations, rename one surface, add the sentence, dedupe by fingerprint. | lens-roster naming; finding dedup | KEEP | Documentation accuracy plus one small dedup bug; independent of lens choice or review timing. |
| 885 | Discovering | defect | saga-code-review | Code Review caps repair negotiation at three cycles; once capped with one finding open, there's no way to record it fixed and verified. | Add a bounded fourth cycle or a fixed-and-verified transition. | review cycle-cap; consensus closure | SUPERSEDE | Build-then-review moves repair-and-reverify outside code review into the build loop, so the cycle counter no longer needs a closure path. |
| 946 | Ready for Planning | defect | saga-code-review | A controller reset the cycle cap by starting a fresh review history for the same code, showing incomparable scores as a trend. | Bind one history per target, freeze its lens set, refuse incomparable comparisons. | review cycle-cap; consensus lineage | SUPERSEDE | Protects a multi-cycle negotiation build-then-review removes; one mechanical pass has no lineage to reset. |
| 1001 | Capturing | capability | saga-code-review | Saga hand-maintains its own review-lens list while infiquetra-sdlc generates a fuller, versioned catalogue and result shape Saga doesn't read. | Consume the generated roster as policy; emit the newer result shape. | lens roster; review_result schema | REWRITE | Closest existing match to mechanical review; needs Jev's typed-judgment layer added, which the issue as written omits. |

### Cluster E — Saga Plan save-contract residuals (4 issues)

Grouped under issue 1005, filed 2026-09-13 as backlog grouping only — unlike 909/910/920/921 it
never claimed to be a bounded run, so there's nothing to rewrite here.

| # | Board | Type | Component | Problem | Prescribed fix | Machinery | Bucket | Reasoning (≤25 words) |
|---|---|---|---|---|---|---|---|---|
| 1005 | Capturing | capability | saga-plan | Grouping parent for three small Plan-tool bugs, explicitly grouping only. | None of its own; each child fixes its own file. | plan save contract | KEEP | Already the lightweight style the other four parents were downgraded to. |
| 996 | Capturing | defect | saga-plan | Finding adv09: the Plan-save tool promises JSON (a structured text format) and fixed exit codes, but an interpreter exit inside loaded code escapes that promise. | Catch the broader exception class so every exit stays in the envelope. | plan save contract; error handling | KEEP | Plain exception-handling correctness; no connection to lenses, gates, races, or team-execution. |
| 997 | Capturing | defect | saga-plan | Finding adv10: a missing PyYAML dependency crashes the tool outside its JSON result, reporting the same code used for a real documentation mismatch. | Catch the missing-dependency case as its own outcome. | plan save contract; error handling | KEEP | Same class of reliability bug as the row above; unrelated to any direction point. |
| 998 | Capturing | defect | saga-plan | Finding agentusab06: the Plan-save proof tool has no command-line interface (CLI) entry point, so `--help` exits successfully printing nothing. | Give it a real CLI entry point with working `--help`. | plan save contract; CLI usability | KEEP | A plain usability gap in a validation tool; unaffected by any direction point. |

**Bucket totals across all 38:** KEEP 23, REWRITE 8, SUPERSEDE 7, UNRELATED 0.

## 2. The 49 closed issues

### Group 1 — Mission Control schema and readiness alignment (4 issues, board Closeout, closed 2026-09-13)

- 1004 — Mission Control alignment with the current infiquetra-sdlc schema: schema re-sync, the Risk field, and handoff maturity
- 942 — Mission Control: content-blind Brainstorm maturity inference, and pending-confirmation rejected by the handoff vocabulary
- 1000 — Mission Control: issue templates and prepared-issue path gain the Risk field; repair-window write; Technical Risk field retires
- 999 — Re-sync Mission Control's vendored SDLC schema after infiquetra-sdlc schema bump

Shipped via pull request 1006: Mission Control 2.16.0, Saga 0.158.0 — handoff-readiness now
delegates to Saga's shared envelope module instead of guessing from folder location; added a Risk
field and a `repair-window` command; retired Technical Risk; resynced the schema.

### Group 2 — Team Execution effort-marker fix (1 issue, board Ready to close, closed 2026-09-15)

- 993 — Team Execution's effort-emission comment still claims dispatch-time honoring does not exist

Shipped via pull requests 1007-1011: Team Execution 3.1.1 — corrected a comment wrongly claiming a
model-effort setting went unhonored at dispatch, added a regression test, recorded the fix.

### Group 3 — Agent Launcher pane-write door, receipts, and retry findings (22 issues, closed 2026-09-16 evening; 1002 at Implementing, the 21 findings beneath it at Capturing)

Parent: 1002 — Agent Launcher pane-write door, receipts, and retry findings carried from the issue
#907 review. Findings beneath it (number — finding code — gist; full titles are longer sentences
in the tracker, shortened here for space): 953 F102 staged-draft misread as empty; 954 F103 retry
door reopened onto a stale draft; 955 F104 private methods callable from outside; 961 F110
last-block-wins let a later marker stand in; 963 F112 receipt-key mismatch; 964 F113 markdown
bullet read as a menu choice; 965 F114 failed read still authorized a write; 966 F115 variant
check satisfied by the launcher's own echo; 967 F116 `herdr workspace list` had no timeout; 968
F117 account label scraped from anywhere; 969 F118 a "done" session was a fixed point; 970 F119
redrive accepted a contradictory receipt; 971 F120 evidence was per-site, not full; 972 F121
structural test missed evasion shapes; 981 F130 byte cap became a row cap; 982 F131 stale
character count kept; 983 F132 redaction covered only the refusal path; 984 F133 symlink escape
unchecked; 985 F134 five stop conditions untested; 986 F135 test measured wall-clock time; 987
F136 wrong observer cited for finding F41.

Shipped via pull requests 1013-1014: Agent Launcher 1.5.0-1.5.1. Rewrote composer-state
classification so a staged draft, stray echo, or picker menu can't be misread as confirmation;
consolidated every pane write through one inspected door; added timeouts, byte caps, and
symlink-escape checks; closed the redrive receipt-matching and dead-end-state bugs.

### Group 4 — Orchestrate/Agent Launcher companion-contract findings (9 issues, closed 2026-09-16 night; 1003 at Ready to merge, the 8 findings beneath it at Capturing)

Parent: 1003 — Orchestrate and Agent Launcher companion-contract findings carried from the issue
#907 review. Findings beneath it: 952 F101 orchestrate called a deleted launcher function; 957
F106 launcher source exec'd unconditionally; 958 F107 one missing name crashed read-only status;
962 F111 renamed internals not cross-checked; 973 F122 install docs omitted the version floor; 977
F126 gate comments named a dead write path; 978 F127 `check` reported agreement without asking;
980 F129 two required-name lists disagreed.

Shipped via pull request 1015: Orchestrate 4.4.0, Agent Launcher 1.5.2 — a companion install now
classifies as missing, below floor, broken, or usable instead of crashing or trusting a stub; the
two plugins' required-name lists were reconciled.

### Group 5 — Code Review result and repair-lifecycle integrity (13 issues, board Ready to close, closed 2026-09-17)

- 908 — Code Review result and repair-lifecycle integrity: seven defects as one bounded run
- 898 — Orchestrate orphans review state when a lifecycle is assigned after a controller already reviewed
- 893 — Orchestrate review-result overwrites a terminal Code Review outcome with a cycle-regressed artifact
- 892 — Orchestrate routes Code Review repairs to units in a terminal state and flips them back to running
- 902 — Replacement repair units take their name and workspace from the template worker but their lifecycle from the controller
- 884 — Orchestrate resubmits review to unrelated lifecycles, re-targeting an in-flight controller mid-cycle
- 895 — Orchestrate status hides a persisted review result and lets a free-text note contradict the typed outcome
- 956 — F105: In a multi-controller run any resubmission write failure other than…
- 959 — F108: land returns 3 for a leftover landing path even when an owed review…
- 974 — F123: land exits 0 while an owed review resubmission is held by operator fix…
- 976 — F125: Retrying review-result after a partial dispatch re-prompts every worker…
- 894 — Saga emits an accepted review result whose findings still read status active
- 899 — Saga fix identifiers collide across lifecycles

Shipped via pull request 1016: Orchestrate 4.5.0, Saga 0.159.0 — the review-result slot migrates
cleanly on a late lifecycle name, a terminal or regressed result can't overwrite a good one, status
matches the stored result, resubmission is scoped to the lifecycle that landed a repair, and Saga
refuses an accepted result with an open finding or a reused fix identifier.

*Strongest evidence for build-then-review: the team just spent a release train hardening the
internal multi-cycle review-and-repair machine that issues 885 and 946 (both SUPERSEDE above)
argue should stop existing once review is one mechanical pass gated behind a build-then-test loop.*

## 3. Board hygiene

No open issue sits in a closed-looking status — all 38 sit in `Capturing`, `Discovering`, or
`Ready for Planning`, internally consistent. All disagreement runs the other way: a closed GitHub
issue whose board card was never moved forward.

| Current board status | Count | Issues |
|---|---|---|
| Capturing | 29 | 952, 953, 954, 955, 957, 958, 961, 962, 963, 964, 965, 966, 967, 968, 969, 970, 971, 972, 973, 977, 978, 980, 981, 982, 983, 984, 985, 986, 987 |
| Closeout | 4 | 942, 999, 1000, 1004 |
| Implementing | 1 | 1002 |
| Ready to merge | 1 | 1003 |
| Ready to close (correct already) | 14 | 884, 892, 893, 894, 895, 898, 899, 902, 908, 956, 959, 974, 976, 993 |

All 35 in the first four rows should carry **Ready to close** — GitHub already agrees they're
done; the board never caught up. The 29 in `Capturing` (the board's first stage) are the sharpest
jump: shipped three days ago, still sitting as if untouched. Most are single carried-forward
findings; dropping them off the board entirely, rather than cycling each through `Ready to close`,
is a reasonable alternative.

## 4. Cross-cutting patterns

The five clusters above are exhaustive and non-overlapping across all 38 open issues
(9+11+5+9+4=38), so they double as the machinery grouping.

| Cluster | Issues | Direction verdict |
|---|---|---|
| B — orchestrate run record, integration, cleanup | 11 | Untouched. 9 of 11 are plain correctness/doc bugs; only `collect` (875) and the run-contract wrapper (910) need rewriting — foundation plumbing worktree-merge still needs. |
| A — orchestrate launch/relaunch/recovery control | 9 | Changed sharply. 5 of 9 are race/dispatch/ceiling protections worktree-merge and herdr-roles remove by construction; 3 stay as plain fixes; 909 needs rewriting to plain grouping. |
| D — saga code review improvement | 9 | Changed most of any cluster. 2 of 9 protect an internal consensus machine build-then-review removes outright; 2 more need rewriting toward mechanical, up-front lens selection; the rest stay. |
| C — saga document review improvement | 5 | Changed moderately. Capability and most fixes stay; only the P0-blocks-work gate (933) softens to guidance, plus the run-contract wrapper (920). |
| E — saga plan save-contract residuals | 4 | Untouched. All four are plain tool-reliability/CLI bugs with no connection to any direction point. |

**Largest group:** cluster B at 11 — the one the direction touches least. **Second largest:**
clusters A and D, tied at 9, carrying all 7 of the SUPERSEDE verdicts (5 in A, 2 in D) and half the
REWRITE verdicts (1 in A, 3 in D) — built around avoiding concurrent/duplicate work and a bad
multi-cycle review negotiation, exactly what mechanical review, build-then-review, and
worktree-merge replace.

**Oldest open card:** issue 874, filed 2026-08-27, 23 days old today. Neighbor issue 875 (filed
four minutes later) has had zero comments or edits since filing — the most neglected card, not
merely the oldest.

By mechanism: the 7 SUPERSEDE issues are all race/dispatch protections worktree-merge replaces
(900, 901, 886, 990, 891, 885, 946). Of the 8 REWRITE issues, 4 are run-contract parents (909, 910,
920, 921), 1 is the collect/run-branch model (875), and 3 are review-process redesign candidates
(933, 937, 1001). The other 23 are plain KEEP bugs, docs, or lightweight grouping (1005), owing
nothing to the direction.

## 5. Issue 1001 in detail

Filed 2026-09-07, titled "Saga code review consumes the generated review roster from
infiquetra-sdlc's lens catalogue and emits review_result.v2" — infiquetra-sdlc being Infiquetra's
separate repository for company software development lifecycle (SDLC) standards. It asks Code
Review to stop hand-maintaining its own lens list (a lens is one reviewer perspective, such as
security or correctness) and read a generated one instead. The **roster** is `review_roster.v1`,
produced by an infiquetra-sdlc script (`tools/docs/gen_review_roster.py`) resolving a catalogue of
fifteen lenses, a "quality profile" choosing defaults, a verification ledger of model-to-lens
pairings, and a per-run applicability declaration into one content-addressed file (its identity is
a hash of its own contents) naming exact lenses, thresholds, and reviewer-model assignments.
**`review_result.v2`** is the matching output this issue asks Saga to write: a structured record
naming the roster by hash, the exact revision reviewed, a score and threshold per lens, checks run
or skipped, a repair accounting, and classified findings, replacing Saga's older format. It
**depends on** infiquetra-sdlc pull request 159 (unit U7 of its documentation-update plan), which
landed the catalogue, profile, ledger, and generator script, plus a decision record (labelled C1a
through C1g, C4, E10) stating Saga's hand-maintained list stays live policy only until it consumes
the generated roster, with lens-execution retries on a fixed schedule: 30 seconds, then 120, then
one model substitution. Issue 1001 is the closest existing match to mechanical review — lenses
decided up front from the change's shape, not adaptively during review — but never mentions
TypeSafe's Jev; realizing the direction fully means adding a Jev-driven step on top of it.
