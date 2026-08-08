# Saga Command Selection

Saga has 25 command files and 24 routable commands. `/ceo-review` is an alias for `/founder-review`, so it is documented separately but does not add a lifecycle node.

![Command Matrix](assets/command-matrix.svg)

## Adjacent Command Distinctions

| Pair | Distinction |
|------|-------------|
| `/office-hours` vs `/ideate` | `/office-hours` finds the frame; `/ideate` generates options inside a usable frame. |
| `/ideate` vs `/brainstorm` | `/ideate` produces and critiques many ideas; `/brainstorm` deepens one chosen idea into requirements. |
| `/brainstorm` vs `/spec` | `/brainstorm` explores requirements and approaches; `/spec` interrogates an ambiguous WHAT until it is precise. |
| `/plan` vs `/doc-review` | `/plan` writes implementation units and decisions; `/doc-review` checks whether that plan is ready to execute. |
| `/qa` vs `/optimize` | `/qa` gates a shipped or merge-bound change; `/optimize` loops toward a metric target. |
| `/strategy` vs `/founder-review` | `/strategy` records direction; `/founder-review` challenges ambition, scope, and timing. |
| `/loop` vs `/resume` | `/loop` routes from current state; `/resume` reconstructs a confusing or cold thread in depth. |

## Command Cards

### /office-hours

Frame-finding front door for early, vague, or stage-sensitive work.

| Field | Value |
|-------|-------|
| Purpose | Find the right frame before selecting a lifecycle command. |
| Use when | The problem, stage, assumptions, or next artifact are unclear. |
| Do not use when | The WHAT is settled enough for requirements or planning, or the user is asking for implementation. |
| Inputs | Topic, early ask, vague business or builder problem. |
| Outputs | Optional `docs/office-hours/` note plus route to `/ideate`, `/brainstorm`, `/plan`, or `/strategy`. |
| Saga state | Does not write saga state directly; `/loop` may tick routing around it. |
| Routes in | cold-start vague ask, `/loop`. |
| Routes out | `/ideate`, `/brainstorm`, `/plan`, `/strategy`. |
| Gates | Never implement, plan, scaffold, or file an SDLC issue. |
| Boundary | Owns frame discovery only. |
| Common mistakes | Treating it as planning; skipping it when the frame is unknown. |
| Example | `/office-hours "I have an idea but do not know what it is yet"` |

### /ideate

Divergent engine for grounded idea generation and critique.

| Field | Value |
|-------|-------|
| Purpose | Generate, critique, and surface survivor ideas. |
| Use when | The user wants possible directions or has a theme but not one selected idea. |
| Do not use when | One idea already needs requirements, or the ask needs precise WHAT interrogation. |
| Inputs | Topic, repo context, strategy context, operator seed ideas. |
| Outputs | Survivor ideas and optional `docs/ideation/` artifact. |
| Saga state | Produces idea-ready artifacts; does not store maturity in saga state. |
| Routes in | `/office-hours`, cold-start divergent ask. |
| Routes out | `/brainstorm`, `/spec`, `/plan`. |
| Gates | Preserve rejection reasons; operator seed ideas face the same critique as generated ideas. |
| Boundary | Owns divergent generation and critique, not requirements or implementation. |
| Common mistakes | Using it for a chosen idea; dropping rejected ideas without reasons. |
| Example | `/ideate "Saga documentation improvements"` |

### /brainstorm

Requirements deep-dive for one chosen idea.

| Field | Value |
|-------|-------|
| Purpose | Turn one chosen idea into a right-sized requirements-ready document. |
| Use when | A single idea is chosen but requirements and approaches need pressure-testing. |
| Do not use when | The ask is still open-ended, or the WHAT is too vague for requirements. |
| Inputs | Chosen idea, ideation survivor, or named topic. |
| Outputs | Requirements document under `docs/brainstorms/`. |
| Saga state | Produces requirements-ready artifacts; does not store maturity in saga state. |
| Routes in | `/ideate`, `/office-hours`, selected idea. |
| Routes out | `/spec`, `/plan`, `/handoff`. |
| Gates | Keep WHAT and acceptance examples clear enough for `/plan`. |
| Boundary | Owns requirements exploration, not HOW planning. |
| Common mistakes | Treating the brainstorm as an implementation plan; skipping approach tradeoffs. |
| Example | `/brainstorm docs/ideation/2026-06-09-example.md` |

### /spec

WHAT-interrogation engine for vague asks.

| Field | Value |
|-------|-------|
| Purpose | Interrogate a vague ask into a precise backlog-ready WHAT spec. |
| Use when | The ask needs five-Why, scope, MVP, non-goal, and failure-mode rigor. |
| Do not use when | The user wants many possible ideas, or the HOW is the unsettled part. |
| Inputs | Vague ask, issue reference, rough doc path. |
| Outputs | Spec artifact under `docs/specs/`. |
| Saga state | Off-chain and saga-untouched; `docs/specs/` maps to requirements-ready at handoff. |
| Routes in | vague WHAT, `/brainstorm`. |
| Routes out | `/handoff`, `/plan`, `/doc-review`. |
| Gates | Do not produce a spec after message 1; interrogate first and read code before technical questions. |
| Boundary | Owns WHAT rigor, not HOW planning or issue mutation. |
| Common mistakes | Treating `spec` as a stored lifecycle phase; filing an SDLC issue directly. |
| Example | `/spec "make Saga docs better"` |

### /plan

HOW-planning engine for settled requirements.

| Field | Value |
|-------|-------|
| Purpose | Create a durable implementation plan from requirements-ready or plan-ready context. |
| Use when | The WHAT is settled and the work needs units, decisions, and verification. |
| Do not use when | The WHAT is still vague, or the change is truly atomic. |
| Inputs | Requirements doc, issue, source artifact, or request. |
| Outputs | Plan under `docs/plans/` and a plan saga tick. |
| Saga state | Writes `lifecycle_phase=plan` with complete phase status when done. |
| Routes in | `idea-ready`, `requirements-ready`, `docs/brainstorms/`, `docs/specs/`. |
| Routes out | `/doc-review`, `/work`. |
| Gates | Does not implement or run the review gauntlet. |
| Boundary | Owns HOW planning only. |
| Common mistakes | Re-deciding product scope; skipping `/doc-review` before `/work`. |
| Example | `/plan docs/brainstorms/2026-06-09-example.md` |

### /doc-review

Implementation-readiness review for plans and requirements.

| Field | Value |
|-------|-------|
| Purpose | Review plans, requirements, or formal SDLC artifacts for readiness. |
| Use when | A document must be checked before execution, and safe in-place fixes may help. |
| Do not use when | The target is code at the PR boundary, or the question is ambition/scope. |
| Inputs | Document path. |
| Outputs | Review artifact under `docs/reviews/` and optional safe fixes. |
| Saga state | Review evidence; unresolved P0/P1 blocks `/work` unless overridden. |
| Routes in | `/plan`, optional `/spec` review. |
| Routes out | `/work`, `/plan`, `/founder-review`. |
| Gates | P0/P1 findings block `/work` without recorded override. |
| Boundary | Owns document readiness, not code review or implementation. |
| Common mistakes | Treating it as `/code-review`; ignoring unresolved P0/P1 findings. |
| Example | `/doc-review docs/plans/2026-06-09-example-plan.md` |

### /work

Implementation engine and PR loop owner.

| Field | Value |
|-------|-------|
| Purpose | Execute an approved plan to PR-ready, then own the round-N PR continuation loop. |
| Use when | A reviewed plan is ready to build, or a plan-ready/resume-ready issue should be executed. |
| Do not use when | Requirements or HOW are unsettled, or deployment mutation is the only remaining step. |
| Inputs | Plan path, plan-ready issue, resume-ready issue. |
| Outputs | Changes, work-session writeups, commits, PR coordination, saga ticks. |
| Saga state | Primary writer for `lifecycle_phase=work`, rounds, branch, checks, PR refs, work sessions. |
| Routes in | `/doc-review`, `plan-ready`, `resume-ready`. |
| Routes out | `/code-review`, `/qa`, `/handoff`. |
| Gates | Hard test gate by risk; hard review gate on P0/P1 or stale review; PR and merge require confirmation. |
| Boundary | Owns build, test, record, and PR loop; does not own deploy or issue filing. |
| Common mistakes | Starting before readiness; claiming PR-ready without fresh tests and review. |
| Example | `/work docs/plans/2026-06-09-example-plan.md` |

### /code-review

Pre-PR code-quality gate.

| Field | Value |
|-------|-------|
| Purpose | Run structured code-quality review at the work-to-PR boundary. |
| Use when | Built work needs pre-PR or PR-boundary review. |
| Do not use when | The target is a plan/requirements document, or the user wants code changes applied by the reviewer. |
| Inputs | Diff, branch, PR, or scope. |
| Outputs | Code review artifact under `docs/code-reviews/`. |
| Saga state | Appends `review_paths` to active work-thread saga when present; does not advance lifecycle phase. |
| Routes in | `/work`, PR boundary. |
| Routes out | `/work`, PR-ready. |
| Gates | P0/P1 findings block PR-ready unless overridden. |
| Boundary | Owns findings, not fixes, commits, PR creation, or issue filing. |
| Common mistakes | Expecting it to fix findings; running against a stale diff. |
| Example | `/code-review HEAD~1..HEAD` |

### /qa

Acceptance-evidence gate.

| Field | Value |
|-------|-------|
| Purpose | Check whether shipped or merge-bound work actually works. |
| Use when | Work is merged or at an acceptance boundary. |
| Do not use when | The goal is metric optimization, root-cause diagnosis, or fixing. |
| Inputs | Scope, PR, merged change, or work-thread context. |
| Outputs | QA artifact under `docs/qa/` with severity, health score, and verdict. |
| Saga state | On pass, advances qa-track and records `qa_paths`; on fail, keeps `lifecycle_phase=work`. |
| Routes in | `/work`, post-merge. |
| Routes out | `/work`, `/handoff`, `/retro`, `/investigate`. |
| Gates | Verdict threshold determines ship, ship-with-deferred, or no-ship. |
| Boundary | Owns acceptance evidence and routing, not fixes, commits, deployment, or issue mutation. |
| Common mistakes | Using QA as an optimization loop; asking QA to fix the defect it finds. |
| Example | `/qa "PR #123 acceptance"` |

### /handoff

Handoff envelope builder for mission-control issue preparation.

| Field | Value |
|-------|-------|
| Purpose | Prepare a durable lifecycle artifact for SDLC issue handoff through `mission-control`. |
| Use when | Another team or future session should pick up a lifecycle artifact. |
| Do not use when | The user expects Saga to create the GitHub issue directly, or no source is identifiable. |
| Inputs | Source artifact, target team, target repo, handoff notes. |
| Outputs | Handoff envelope and suggested mission-control command. |
| Saga state | Reads saga/doc context to infer source and maturity; does not own mission-control mutation. |
| Routes in | `/qa`, `/retro`, `/spec`, `/brainstorm`, `/work`. |
| Routes out | `mission-control`. |
| Gates | Ask when source, maturity, target repo, team, or issue type is ambiguous. |
| Boundary | Saga owns the envelope; `mission-control` owns issue bodies, sidecars, labels, board, and GitHub mutation. |
| Common mistakes | Passing investigation reports directly to the classifier; suggesting `/loop` for normal team handoff. |
| Example | `/handoff docs/plans/2026-06-09-example-plan.md Asgard` |

### /retro

Lifecycle learning and meta-improvement engine.

| Field | Value |
|-------|-------|
| Purpose | Turn finished work into durable journal knowledge and gated lifecycle improvements. |
| Use when | Work is complete and learning should be captured. |
| Do not use when | The work is not complete, or the user wants implementation or GitHub mutation. |
| Inputs | Saga id, issue, branch, time window, or pass argument. |
| Outputs | Retro artifact or journal entries/proposals. |
| Saga state | Terminal and saga read-only; does not advance or write saga state. |
| Routes in | `/qa`, completed work. |
| Routes out | `/handoff` when learning should become work. |
| Gates | Self-edit safety gate; modifications/deletions require explicit apply/skip/modify choice. |
| Boundary | Owns learning capture and proposed lifecycle improvements, not SDLC mutation. |
| Common mistakes | Letting retro silently edit existing directives; treating retro as a required `/loop` blocker. |
| Example | `/retro task-saga-comprehensive-documentation` |

### /promote

Cross-repo journal feeder — lifts the select few transcendent learnings into the org library.

| Field | Value |
|-------|-------|
| Purpose | Promote the select few cross-repo transcendent learnings into `infiquetra-context-library` as distilled org standards. |
| Use when | The same lesson recurred across repos, or a learning was marked `**Transcendent.**`. |
| Do not use when | The lesson is repo-specific, you want a bulk harvest, or you want SDLC/source-repo mutation. |
| Inputs | Workspace root or repo subset; an optional recurrence threshold. |
| Outputs | Proposed gated upserts into context-library's `LEARNINGS.md`. |
| Saga state | Terminal and SDLC read-only; writes only to context-library, never to the saga. |
| Routes in | A `/retro`-declared marker, or recurrence across repos. |
| Routes out | None — terminal. |
| Gates | Every context-library write is propose-diff-and-wait; idempotent via the drift-stable source-key ledger. |
| Boundary | Owns the cross-repo journal feed into context-library, not source-repo or SDLC mutation. |
| Common mistakes | Treating it as a bulk copy of every generalizable rule; writing back to a source repo. |
| Example | `/promote ~/workspace/infiquetra` |

### /resume

Heavy forensic reconstruction engine.

| Field | Value |
|-------|-------|
| Purpose | Reconstruct an in-flight work thread in depth and route to the owning command. |
| Use when | Lightweight `/loop` restore is insufficient, or saga/issue/PR history is confusing. |
| Do not use when | Current saga state is easy to restore, or the user wants work/tests/PR mutation. |
| Inputs | Saga id, issue, plan path, PR refs, or resume request. |
| Outputs | Re-entry tick and route recommendation. |
| Saga state | Reads full tick chain and writes one git-ignored re-entry tick; reuses restored `saga_id`. |
| Routes in | cold resume, ambiguous work thread. |
| Routes out | `/work`, `/handoff`. |
| Gates | Read-only on world; Tier 2 session forensics only when no saga and no resolvable issue exist. |
| Boundary | Owns reconstruction and routing, not build/test/PR. |
| Common mistakes | Minting a new saga when an old saga should be reused; routing back to `/loop`. |
| Example | `/resume docs/plans/2026-06-09-example-plan.md` |

### /investigate

Root-cause diagnosis engine.

| Field | Value |
|-------|-------|
| Purpose | Find the root cause of a bug, failing test, or unexpected behavior before proposing a fix. |
| Use when | The user asks why something is broken, or QA needs causal diagnosis. |
| Do not use when | The fix is already planned for `/work`, or the ask is metric optimization. |
| Inputs | Error, failing test path, issue, or broken behavior. |
| Outputs | Debug report under `docs/investigations/` and optional trivial verified fix. |
| Saga state | Off-chain and saga read-only; never advances `lifecycle_phase`. |
| Routes in | `/qa`, defect reports, failing tests. |
| Routes out | `/work`, `/handoff`, `/brainstorm`, `/code-review`. |
| Gates | No fix without root-cause chain grounded in observed evidence. |
| Boundary | Owns diagnosis, not shipping real fixes. |
| Common mistakes | Starting with a fix hypothesis; routing back to `/qa` for verification. |
| Example | `/investigate tests/test_saga_docs_coverage.py` |

### /optimize

Metric-driven experiment loop.

| Field | Value |
|-------|-------|
| Purpose | Improve a measurable target through bounded one-variable experiments. |
| Use when | The user wants a metric better, cheaper, faster, safer, or more reliable. |
| Do not use when | The question is whether a shipped change is acceptable, or the winning change is already selected. |
| Inputs | Metric, workflow, or bottleneck. |
| Outputs | Optimization notes, experiment result, winning change routed to `/work`. |
| Saga state | Off-chain and saga-untouched; records backend choice narratively. |
| Routes in | metric optimization ask. |
| Routes out | `/work`. |
| Gates | Hard degenerate gates before any LLM judge; keep only measured improvement. |
| Boundary | Owns experiment loop, not merge or deployment. |
| Common mistakes | Using it as a QA gate; shipping an experiment without routing the winning change to `/work`. |
| Example | `/optimize "reduce docs update drift"` |

### /strategy

Durable direction anchor.

| Field | Value |
|-------|-------|
| Purpose | Create or maintain root `STRATEGY.md`. |
| Use when | Repo direction, target problem, approach, metrics, or tracks need updating. |
| Do not use when | The direction needs ambition/scope challenge, or the ask is concrete implementation. |
| Inputs | Optional section focus or strategy update request. |
| Outputs | Root `STRATEGY.md` update. |
| Saga state | Off-chain and saga-untouched. |
| Routes in | strategic-direction ask, `/office-hours`. |
| Routes out | `/ideate`, `/brainstorm`, `/plan`, `/founder-review`. |
| Gates | Interview-driven update with pushback; do not implement or file issues. |
| Boundary | Owns recording direction; `/founder-review` challenges direction. |
| Common mistakes | Treating it as ambition review; bypassing interview pushback. |
| Example | `/strategy metrics` |

### /founder-review

Founder/operator scope and ambition review.

| Field | Value |
|-------|-------|
| Purpose | Challenge scope, ambition, positioning, timing, and operator risk. |
| Use when | A plan, strategy, brainstorm, feature, or PR needs founder/operator judgment. |
| Do not use when | The question is implementation readiness, or the user wants code changes. |
| Inputs | Plan, strategy, feature, PR, or scope question. |
| Outputs | Scope-decision artifact under `docs/founder-reviews/`. |
| Saga state | Review artifact; does not implement or mutate git/GitHub. |
| Routes in | scope question, `/strategy`, `/plan`, `/brainstorm`. |
| Routes out | `/plan`, `/doc-review`, `/code-review`. |
| Gates | Opt-in ceremony before scope expansion. |
| Boundary | Owns challenge and decision capture, not direction recording or readiness review. |
| Common mistakes | Using it to record `STRATEGY.md`; letting it apply code changes. |
| Example | `/founder-review docs/plans/2026-06-09-example-plan.md` |

### /ceo-review

Alias for `/founder-review`.

| Field | Value |
|-------|-------|
| Purpose | Compatibility alias for founder/operator review. |
| Use when | The user invokes CEO-review terminology for the founder-review engine. |
| Do not use when | Counting routable lifecycle nodes. |
| Inputs | Same as `/founder-review`. |
| Outputs | Same as `/founder-review`. |
| Saga state | Same as `/founder-review`; not a separate lifecycle node. |
| Routes in | Same as `/founder-review`. |
| Routes out | Same as `/founder-review`. |
| Gates | Same as `/founder-review`. |
| Boundary | Alias only. |
| Common mistakes | Counting it as command 18 in the routable command set. |
| Example | `/ceo-review docs/plans/2026-06-09-example-plan.md` |

### /loop

Lifecycle router and lightweight resume substrate.

| Field | Value |
|-------|-------|
| Purpose | Classify input, find in-flight work, and dispatch to the command that owns the next phase. |
| Use when | The user wants Saga to route/drive lifecycle work or says resume/drive it. |
| Do not use when | The user already named the owning command, or heavy reconstruction is required. |
| Inputs | Issue, plan path, work description, resume request, drive request. |
| Outputs | Routing decision, saga tick, dispatched command. |
| Saga state | Scans/restores saga and ticks routing decisions; does not execute phase work. |
| Routes in | all lifecycle entry points. |
| Routes out | `/office-hours`, `/ideate`, `/brainstorm`, `/spec`, `/plan`, `/doc-review`, `/work`, `/code-review`, `/qa`, `/handoff`, `/retro`, `/resume`, `/strategy`, `/optimize`, `/investigate`, `/founder-review`. |
| Gates | Enforces doc-review P0/P1 hard gate before `/work`; stub/off-chain routes are advisory. |
| Boundary | Owns routing and handoff envelope, not phase work, backend choice, issue filing, deploy, or heavy forensics. |
| Common mistakes | Asking it to implement; routing normal team handoff through it. |
| Example | `/loop docs/plans/2026-06-09-example-plan.md` |

### /tier

| Field | Value |
|-------|-------|
| Purpose | Set a run-scoped tier ceiling or patch a not-yet-run unit's tier mid-run, without aborting and re-planning. |
| Use when | The operator wants to cap model/effort for the rest of a run, or change a not-yet-run unit's tier without re-planning. |
| Do not use when | The tier should be set once up front (use `/plan`'s tier table), or the unit has already run. |
| Inputs | A model/effort ceiling, a unit id plus a new tier, or `show`/`clear`. |
| Outputs | A session-override file write, or a patched + re-validated + re-emitted spec. |
| Saga state | Writes the git-ignored session override (`.claude/saga/tier-session-override.json`); does not tick a saga. |
| Routes in | `/plan`, `/work`. |
| Routes out | `/work`. |
| Gates | An up-ladder mid-run escalation requires operator confirmation before re-emit; a ceiling only ever clamps down. |
| Boundary | Writes the override and drives patch/validate/emit; does not run leaf work, merge, or deploy. |
| Common mistakes | Expecting a ceiling to raise a tier; patching a unit that already ran. |
| Example | `/tier sonnet/medium` |

### /outcome

Outcome coordinator over a DAG of leaf sagas — the layer above a single work-thread.

| Field | Value |
|-------|-------|
| Purpose | Coordinate a whole outcome as a durable DAG of leaf sagas via a level-triggered reconcile loop that dispatches the ready frontier and pages only on exceptions. |
| Use when | An outcome spans multiple concurrent subplots that each run their own saga; the operator wants to advance the frontier, attend a leaf, or resume an outcome. |
| Do not use when | The work is a single linear work-thread (use `/work`), or the graph still needs authoring from scratch (use `/plan` and the decompose flow). |
| Inputs | Outcome id, objective, or a portable outcome bundle. |
| Outputs | Branch-local outcome spec, dispatched leaf sagas, derived-on-read status, Mermaid graph. |
| Saga state | Coordinates leaf sagas; live node state is derived on read from spec + completion events, never a stored status field. |
| Routes in | outcome coordination ask, `/plan` decompose. |
| Routes out | `/resume`, `/work`, `/code-review`, `/qa`. |
| Gates | Coordinator routes and dispatches but never runs leaf work; pages only at gates, unsatisfiable barriers, ambiguity, and parent-close. |
| Boundary | Owns frontier dispatch, harvest, and operator-attention routing; does not run leaf implementations, file issues, or deploy. |
| Common mistakes | Expecting an `/outcome work` verb; treating status as stored rather than derived on read. |
| Example | `/outcome advance ship-feature-x` |

### /engines

External-engine registry visibility and repo-local route overlay.

| Field | Value |
|-------|-------|
| Purpose | Inspect registry rows, manage repo-local pins/deprecations, and dry-run route decisions without engine dispatch. |
| Use when | Operator wants to see engine capability ratings, cost rank, latency, stale/current state, local pins/deprecations, or a route explanation before invoking a lifecycle surface. |
| Do not use when | The task is to dispatch work to an engine, or registry seed ratings / committed policy need to change. |
| Inputs | `list`, `pin`, `deprecate`, `clear`, or `route explain <capability>`. |
| Outputs | Deterministic text/JSON listing or explanation; optional local overlay write. |
| Saga state | Does not tick saga; `.saga/engine-overlay.json` is git-ignored repo-local operator state. |
| Routes in | `/work`, `/code-review`, operator inspection. |
| Routes out | `/work`, `/plan`, `/code-review`. |
| Gates | Pin targets must exist, declare the capability, and not be locally deprecated; `route explain` is read-only. |
| Boundary | Owns local visibility and overlay mutation only; does not dispatch engines, rewrite registry seed data, or file issues. |
| Common mistakes | Treating `route explain` as an engine invocation; committing local overlay state as shared policy. |
| Example | `/engines route explain code-generation` |

### /pulse

Live fleet telemetry rendered from real signals (read-only).

| Field | Value |
|-------|-------|
| Purpose | Render live board, run, run-fact-ledger, and outcome-economics state from real signals in one read-only snapshot. |
| Use when | The operator asks what the fleet is doing right now (boards, in-flight sagas, spend), or a run is in flight and its state should be observed on refresh. |
| Do not use when | The goal is a bounded metric experiment with a target and budget (use `/optimize`), or board/issue state needs mutating (use mission-control). |
| Inputs | Optional `--project` boards, `--saga` focus id, `--json`, bounded `--watch --iterations N`. |
| Outputs | Terminal status card + per-saga detail, or `pulse_snapshot.v1` JSON. |
| Saga state | Strictly read-only and derive-on-read; writes no tick, fact, or cache and owns no status field. |
| Routes in | Operator telemetry ask, `/outcome` status curiosity. |
| Routes out | `/optimize`, `/resume`, `/outcome`. |
| Gates | Tri-state source honesty per panel (`ok` / `no-data` / `unavailable`, ledger adds `chain-broken`); a broken chain suppresses all aggregates; no thresholds, not a gate. |
| Boundary | Owns rendering only; mission-control owns board mutation, saga writers own ticks, ledger writers own facts. |
| Common mistakes | Treating an empty panel's "no data yet" as zero activity; expecting `/pulse` to feed `/optimize` automatically (settled: it stands beside it). |
| Example | `/pulse --project operations` |

### /fleet-doctor

Strict, bounded, read-only cross-source fleet audit — a tripwire, never a repair tool.

| Field | Value |
|-------|-------|
| Purpose | Derive one point-in-time `fleet_doctor_report.v1` correlating Git worktrees, outcome registries, retired broker leases/fences (deleted #677/U7, always absent), the chain-verified run-fact ledger, dispatch commit events, and the delegation audit store into `leaked-resource` / `unledgered-spawn` / `receiptless-delegation` findings plus explicit evidence errors. |
| Use when | The operator suspects leaked worktrees, unledgered spawns, or receiptless delegations, or a CI/acceptance gate needs a strict clean-fleet tripwire with fail-closed exits. |
| Do not use when | Anything needs repairing, reaping, settling, retrying, or releasing (findings name the owner; the doctor never acts), or a tolerant advisory query is enough (use `/delegation-audit`). |
| Inputs | Optional `--repo-root`, `--lease-store`, `--audit-store`, `--format text|json`, `--show-local-paths`. |
| Outputs | Deterministic text or JSON report; exit 0 complete-clean, 1 complete-with-findings, 2 incomplete proof. |
| Saga state | Strictly read-only and derive-fresh; imports no producer module, writes no file, cache, tick, or fact; bytecode writing disabled. |
| Routes in | Operator fleet-health ask, cross-runtime acceptance gate. |
| Routes out | `/outcome`, `/delegation-audit`. |
| Gates | Absence, corruption, and incompleteness are distinct verdicts; any cap, corruption, unsafe path, or mid-scan source change forces exit 2 and can never truncate to a clean report. |
| Boundary | Owns observation and classification only; `/outcome`, B8 teardown (lease broker deleted #677/U7), and `/delegation-audit` own every recovery action. |
| Common mistakes | Treating exit 2 (incomplete proof) as a disease finding; expecting the doctor to clean up what it finds. |
| Example | `/fleet-doctor --format json` |

### /undo

Replay the inverse of the most recent reversible mutation(s) from the mid-run adjustment envelope's act-log-inverse-notify path.

| Field | Value |
|-------|-------|
| Purpose | Replay the inverse of the most recent reversible mutation(s) recorded by the act-log-inverse-notify path, so reversible board/label/issue/branch/PR steps need not pause. |
| Use when | A reversible mutation proceeded under act-log-inverse-notify and the operator wants it undone, or wants to inspect / roll back the pending-undo ledger for a run. |
| Do not use when | The operation had no registered inverse (it went through a gated pause, not the ledger), or the goal is to change campaign posture or DAG structure (use `/outcome`). |
| Inputs | Optional count of trailing records to replay (default 1); reads `.saga/undo-ledger.jsonl`. |
| Outputs | Replayed inverse action(s) + an operator summary of what was undone. |
| Saga state | Reads and rewrites the git-ignored per-run undo ledger; writes no saga tick and owns no status field. |
| Routes in | Reversible mutation via adjustment-envelope act-log, operator rollback ask. |
| Routes out | mission-control, `/outcome`, `/work`. |
| Gates | Only registered reversible ops are in the ledger; gh-write inverses route through mission-control, saga-local inverses replay directly; an empty ledger fails closed. |
| Boundary | Owns inverse computation and ledger replay only; mission-control owns the gh write-ownership lane for board/label/issue inverses. |
| Common mistakes | Expecting `/undo` to reverse an irreversible op (those pause, they are never ledgered); calling `gh` directly from saga to replay a board inverse instead of routing through mission-control. |
| Example | `/undo 1` |
