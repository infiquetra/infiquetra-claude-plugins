# Research brief: what the infiquetra-sdlc source of truth actually says

Prepared for the saga plugin simplification review. Citations are `path:line` against
`infiquetra-sdlc` (the documentation repository defining Infiquetra's software delivery lifecycle,
the standard sequence a piece of work travels from idea to shipped, verified software), at commit
`67845cdd19948c9c10608436174d11a9b80d43ca` on `main` (2026-09-12), fetched clean, zero commits behind
`origin/main`. Paths are relative to that repository's root. This extracts the source; it does not
compare it to the plugins.

## 1. The lifecycle as defined

The kanban workflow document (`docs/process/kanban-workflow.md`) is the single authority for the
board vocabulary. Every board — Operations, Asgard, and CAMPPS (Infiquetra's three active project
boards) — shares one flow: "No board runs its own variant of this flow, and no board has a column
another board lacks" (`docs/process/kanban-workflow.md:24-26`). A **Stage** is the board column
("how far along is this work?"); a **Status** is the card's condition inside that Stage ("what is
happening to it right now?") (`docs/process/kanban-workflow.md:32-34`).

The six Stages, in forward order, and every Status a card can carry inside each one
(`docs/process/kanban-workflow.md:99-110`, a generated table):

| Stage | Statuses |
|---|---|
| Intake | Capturing, Needs clarification, Triage, Backlog |
| Shaping | Discovering, Defining requirements, Ready for Planning |
| Planning | Designing, Design review, Execution planning, Ready for Active |
| Active | Implementing, Integrating, Code review, Repairing, Ready to merge, Deploying to non-production |
| Verify | Awaiting verification, Verifying, Verification failed, Closeout, Ready to close |
| Retro | Gathering evidence, Awaiting operator input, Capturing learnings, Ready to close |
| Any Stage | Blocked (cross-cutting) |

The three structural rules (`docs/process/kanban-workflow.md:113-137`): (1) the first Status listed
in each Stage is the entry option, except `Ready for Active` and `Ready to close`, which are
terminal within their Stage and never defaulted to; (2) `Blocked` cuts across every Stage — no board
has its own paused column, a deliberate pause is `Blocked` plus a recorded pause reason; (3) the
table is descriptive, not mechanically enforced — "a GitHub single-select field cannot offer
different options per column... nothing mechanically stops someone choosing a Status that belongs to
another Stage" (`docs/process/kanban-workflow.md:134-137`).

Entry/exit gates: leaving Planning requires the card body to satisfy the card contract, evaluated by
one organization-wide rule, Planning-to-Active readiness (`docs/process/kanban-workflow.md:74-77`,
detailed in Section 8). Entering Verify requires either a merge plus a succeeded non-production
deployment (deployable work), or a merge plus the delivered artifact existing in its real
consumption context (non-deployable work) — "Pre-merge continuous integration, tests, code review,
and pull-request readiness never advance the Stage" (`docs/process/verify-entry.md:21-33`).

Artifacts per phase (from the saga phase crosswalk, Section 7): ideation produces
`docs/ideation/`, `docs/office-hours/`; brainstorm produces `docs/brainstorms/`, `docs/specs/`;
plan produces `docs/plans/`; review (plan review) produces `docs/reviews/`; work produces
`docs/code-reviews/`, `docs/work-sessions/`; qa produces `docs/qa/`; retro produces
`docs/engineering-journal/`, `docs/retros/` (`docs/lifecycle/saga-crosswalk.md:114-120`).

## 2. The run model (`docs/lifecycle/run-model.md`)

This is explicitly the primary reading document, and it carries a hard warning at the top: "this
workflow is not implemented anywhere yet. It is an agreed design... Nothing on this page describes
behaviour you can observe today" (`docs/lifecycle/run-model.md:16`). A **run** is "one piece of
already-defined work — a single issue, or a parent issue with its sub-issues — travels all the way
to software that is merged, delivered into a real working environment, and tested against its
planned scenarios" (`docs/lifecycle/run-model.md:18`).

**Loop shape — does implementation loop before review?** No. The twelve steps run: (1) understand
work, (2) plan work and define how it will be evaluated, (3) **plan review — before any code is
written**, (4) orchestration setup, (5) implement, (6) integrate parallel lanes onto a parent
branch, (7) **code review — after implementation, on the combined built result, before merge**,
(8) repair planning and repair, (9) merge to the main branch, (10) deploy or install, (11) functional
test, (12) close the parent (`docs/lifecycle/run-model.md:169-182`). There is a review gate before
any implementation and a second review gate after implementation and before merge; deployment and
functional testing happen only after both review gates and only after merge. The model states this
distinction directly: plan review "sits strictly *before* implementation," code review is "the
review of built software... after implementation" (`docs/lifecycle/run-model.md:226-232,297-301`).

**Roles, contracts:** fifteen standing roles (Section 3) and sixteen handoff contracts
(`docs/process/run-contracts.md`, title line: "The sixteen handoff contracts... who sends each one,
who reads it, the fields it carries"). Every handoff is "a short structured comment on the issue
record," never a copy of the plan or review document itself, and machine validation is explicitly
deferred: "Nothing validates a contract instance mechanically, by decision rather than by omission"
(`docs/lifecycle/run-model.md:680`; contract catalogue `docs/process/run-contracts.md:13`, which
states: "the contracts and their fields are decided and machine-readable, but no tool validates an
instance yet: recipients and reviewers check them by reading").

**Worktrees, branches, merging:** a parent issue gets one shared parent branch; each work unit
implements on its own branch, "ideally checked out in a separate worktree" (a worktree is a second
working directory checked out from the same repository) (`docs/lifecycle/run-model.md:269`). Merges
onto the parent branch are serialized one worker at a time via "merge turns," coordinated by the
Delivery Manager as ordinary execution bookkeeping: "no lock service, no dedicated integration
worker, and no approval ceremony" (`docs/lifecycle/run-model.md:271`). Detail in Section 6.

**Every item the document itself marks undecided, verbatim.** A direct search of
`docs/lifecycle/run-model.md` for its own hatch markers — `> **Not yet decided.**` (a bounded
quantity or list left open) and `> **Open question.**` (no defined next step at all) — finds **zero
instances of either marker actually used in the document body**; both strings appear only in the
legend defining what the markers would mean (`docs/lifecycle/run-model.md:37-38,46`). The document's
own summary states this explicitly: "Counted over the whole model — every role, step, transition,
rule, decision point, run-configuration parameter, and handoff contract, 133 elements in all — all
133 are settled: no element is a deferred detail, and none is an undefined route"
(`docs/lifecycle/run-model.md:48`).

**This claim is internally inconsistent with a second table later in the same file.** Under "How
finished the design is, part by part," a coverage table reports a *different* total and non-zero
gaps: "Total 117 ... Settled 105 ... Deferred detail 11 ... Undefined route 1"
(`docs/lifecycle/run-model.md:715-724`), right after the prose claim "**Nothing, as of 2026-09-06.**
... There is nothing hatched in this workflow today" (`docs/lifecycle/run-model.md:698-703`). Neither
the total (133 vs. 117) nor the gap counts (0/0 vs. 11/1) match. This reads as a stale,
unregenerated table left over after the operator's 2026-09-06 decisions closed the real open
questions — `docs/process/open-questions.md:21` independently confirms that register is empty (see
Section 9) — but the file itself never resolves the contradiction. **Count of undecided items,
reported honestly: zero live callouts in the run model's own marking mechanism, plus one
unexplained internal inconsistency (11 deferred + 1 undefined, or 0) that a reader should not paper
over.**

**What no tooling implements — stated by the documents themselves, verbatim excerpts:**
- The entire run model: "this workflow is not implemented anywhere yet" (`docs/lifecycle/run-model.md:16`).
- Plan reviewer's per-field handoff check: "Today the plan reviewer only checks that the required
  handoff categories are present and substantive... no tooling validates a handoff against them yet"
  (`docs/roles/run-roles.md:576-580`).
- Repair planning: "no tooling runs it yet" (`docs/reviewers/repair-planning.md:19`).
- The lens catalogue: "No tooling reads this catalogue yet" (`docs/reviewers/code-review-lenses.md:38`).
- The three-review target (issue review added to plan review and code review): "agreed and not yet
  implemented by any tooling" (`docs/reviewers/README.md:97-99`); "No tooling runs it, and no Issue
  Reviewer is staffed today" (`docs/process/human-intent-intake.md:99`).
- Parent-branch integration: "none of it is implemented yet" (`docs/process/parent-branch-integration.md:13`).
- Functional QA: "not implemented anywhere yet" (`docs/process/functional-qa.md:13`).
- The target design where one multi-lens code review would itself be the authoritative pre-merge
  gate: "an agreed design that no tooling implements" (`docs/process/gates.md:81`).
- The saga phase crosswalk's mapping of run-model steps onto stored phases: "nothing below is stored
  anywhere yet, and no tooling runs these steps today" (`docs/lifecycle/saga-crosswalk.md:204-205`).

## 3. Roles (`docs/roles/run-roles.md`, `responsibilities.md`)

Fifteen standing run roles, each with a one-line responsibility (`docs/roles/run-roles.md:178-194`):

| Role | Responsibility |
|---|---|
| Product | Co-authors issue product content with the operator; rules on in-run product questions the recorded intent already answers |
| Issue Reviewer | Judges the Shaping exit (six checks); ready/not ready, before any run starts |
| Planner | Technical decomposition, lens applicability declaration, preflight evidence, repair amendments |
| Architect (role id `orchestrator`) | Writes the issue's technical context before planning; owns technical direction and disputed judgment calls during the run |
| Delivery Manager (role id `controller`) | Sets staffing/models/concurrency/allowances once at orchestration setup; dispatches and tracks the run |
| Initial Implementation Worker | Implements an assigned work unit; merges it onto the parent branch on its turn |
| Plan Reviewer | Pre-implementation readiness check |
| Review Controller | Runs one multi-lens review cycle; does not score |
| Lens Reviewer | Scores one lens against its rubric |
| Standard Repair Implementer | Executes the standard-tier repair batch |
| Expert Repair Implementer | Executes the escalated-tier repair batch |
| Release Worker | Merges the parent branch to `main`, then deploys/installs the merged change |
| Functional Tester | Exercises prescribed scenarios in a real environment |
| Investigator | Bounded, read-only fact-finding on request |
| Human Operator | Holds operator-reserved decisions; may take any responsibility by explicit assignment, holds none by default |

The categories the task asks about map only partly onto this vocabulary. **Reviewer**: Issue
Reviewer, Plan Reviewer, Lens Reviewer. **Tester**: Functional Tester. **Controller**: Delivery
Manager and Review Controller. **Worker**: Initial Implementation Worker, Standard/Expert Repair
Implementer, Release Worker. **"Scanner," "validator," and "monitor" are not run-model roles at
all** — those words belong to a different plugin's vocabulary, the `team-execution` plugin's gate
catalogue rows (`scanner-validator-gate`, `tester-validator-gate`, `monitor-validator-gate`, census
rows E2/E3/E4, `docs/process/gate-catalogue.md:351,353,390`), not to the fifteen run roles or the six
delivery responsibilities. There is no "lead" role either; the closest is the Architect, whose
machine identifier is literally `orchestrator` even though the process-level orchestrator is a
different thing entirely (Hermes, see below) — the document calls this out as a deliberate "naming
trap" (`docs/roles/run-roles.md:348-361`).

**Hosting.** Lenses may be hosted as isolated subagents of one review-controller session (what the
Saga plugin does today), as several sessions each hosting a group of isolated lens subagents, or as
a lens holding a session of its own — the only way to reach a genuinely different AI vendor
(`docs/reviewers/code-review-lenses.md:568-573`). A subordinate session (any role's) is never
force-compacted or cleared in place; a reset is always a full session replacement started fresh from
durable inputs (a named decision, item A5, 2026-09-06) (`docs/roles/run-roles.md:500-508`). Herdr (a
terminal workspace manager) "starts and supervises agent sessions across vendors" and supports 22
agent kinds, but "has no context command" — it cannot clear or compact a session itself
(`docs/tools/index.md:143-153`). Several agents — "Claude, Codex, Gemini, and others" — pull work
from the same shared boards today (`docs/process/multi-agent-collaboration.md:16`).

**Freya and Hermes.** Freya (`docs/roles/freya.md`) is a forward-looking research role, "not yet a
distinct research surface" (`docs/roles/freya.md:23`), separate from the bounded, in-run
Investigator role by scope: Freya does open-ended upstream research, the Investigator answers one
bounded factual question a run needs right now (`docs/roles/freya.md:30-43`). Hermes
(`docs/roles/hermes.md`) is the deployed orchestrator process — "a system role, not a delivery role:
it dispatches work and keeps state moving without being a reviewer, without writing code, and
without owning any board" (`docs/roles/hermes.md:17-20`). It coordinates plan-review dispatch, agent
assignment, PR-review event coordination, durable state, and human-input routing, and explicitly
does not write code, decide product/behaviour questions, or track work-in-progress limits
(`docs/roles/hermes.md:79-84`).

## 4. Review

**The lens catalogue** (`docs/reviewers/code-review-lenses.md`) names fifteen lenses: "15 lenses: 4
always on, 11 selected by the Planner's per-unit applicability declaration"
(`docs/reviewers/code-review-lenses.md:212`): Architecture and maintainability, Correctness,
Security, Testing (all four always-on); Deployment and infrastructure, Reliability, Performance, API
and interface contract, Adversarial, Privacy, Documentation and clarity, Agent usability, Previous
comments, Accessibility and human usability, Experience (all eleven conditional). **Only the four
always-on lenses are actually scorable today** — the other eleven have zero fixtures (a fixture is a
small annotated sample with a seeded defect used to qualify a scoring AI model), so "no executor can
be qualified against this lens and no score from it establishes a threshold... documented policy
until fixtures land" (`docs/reviewers/code-review-lenses.md:220-230,314-315` and per-lens rows).

**Lens selection is chosen up front, not discovered during review.** The Planner writes a per-unit
applicability declaration during planning, before implementation, naming every catalogue lens and a
reason for each it leaves out; the four always-on lenses can never be declared away
(`docs/lifecycle/run-model.md:212`, `docs/reviewers/rubric-applicability.md:82-93`). Rubric selection
rules (`docs/reviewers/rubric-applicability.md:26-31`): architecture/architecture-decision-record
changes need architecture review; runtime code needs correctness, test, maintainability, security;
process/schema docs need coherence, feasibility, scope review; deployment changes need release,
rollback, approval, environment-state review — "use the smallest set of rubrics that covers the
risk." Three layers, only the third (the declaration) is per-work-unit: catalogue (this repository
owns) → profile (an application's `quality-profile.json`, authored by its Architect, approved by the
operator) → declaration (the Planner's per-unit selection, checked at plan review)
(`docs/reviewers/rubric-applicability.md:73-80`).

**Verdict vocabulary.** Pull-request review today uses four typed outcomes under contract
`review_result.v1`: `accepted`, `repairs_requested`, `cycle_cap_best_available`, `review_incomplete`
(`docs/reviewers/pr-review.md:38-46`). Plan review uses a one-line plain-language readiness verdict
plus findings rated P0 through P3: P0 = "unsafe, incorrect, destructive, or materially wrong
execution"; P1 = a missing or wrong core assumption/mapping/requirement/default/gate; P2 =
"meaningful rework, ambiguity, or review risk"; P3 = "nice-to-fix... polish"
(`docs/reviewers/plan-review.md:42-47`). Consensus **today** is team-owned: majority agreement,
per-perspective floors, or owner approval, the team's choice
(`docs/reviewers/verdicts-and-consensus.md:56-61`). Consensus **under the run model (not in force)**
is fixed org-wide to one meaning: "every selected lens meets its own threshold" — never an average,
never majority, never owner approval standing in (`docs/reviewers/verdicts-and-consensus.md:72-77`).
Thresholds are a pair of numbers per strictness level on a 0-to-10 scale: baseline 8.0 overall / 6
per dimension, standard 9.0/7, elevated 9.5/8 (`docs/reviewers/verdicts-and-consensus.md:97-101`).

**The `review_result` schema has two versions in play.** The live pull-request-review contract is
`review_result.v1` (`docs/reviewers/pr-review.md:38`, `docs/reviewers/verdicts-and-consensus.md:159`).
The target/generated design calls for `review_result.v2`, "the shared structure every review kind
projects" (issue review, plan review, code review alike) (`docs/adrs/adr-001-code-review-executor-boundary.md:100`).

**Plan review vs. pull-request review vs. code review — these are not three parallel things, and one
name is overloaded.** Plan review is the pre-implementation gate. The team-owned pull-request review
is today's actual authoritative pre-merge gate (gate identifier `team-owned-pr-review`). "Code
review" names two different things depending on which document uses it: today, the gate identifier
`code-review` is only the Saga plugin's advisory internal lens pass inside the work loop and "holds
no merge authority" (`docs/process/gates.md:29-33`); under the target design, "code review" instead
means the full multi-lens review that would itself *become* the authoritative pre-merge gate,
replacing the team-owned review rather than sitting beside it (`docs/process/gates.md:64-98`). The
review model document calls this exact confusion out as a "naming trap"
(`docs/reviewers/README.md:79-82`).

**Repair planning** (`docs/reviewers/repair-planning.md`): an unsuccessful review never sends raw
findings to an implementer; the run's Planner (not a separate repair-planner role) writes a durable
repair amendment first (lines 14-38). Standard tier defaults to three cycles, escalated ("expert")
tier to two, per repair loop (lines 89-100); escalation fires when the standard allowance is
exhausted or "two consecutive standard cycles" show no progress on the same lens (lines 102-106). A
finding unresolved through two consecutive review results is "persistent" and gets classified
`out-of-scope`, `repairable-first`, `evidence-gap`, or `disputed`, each with its own route (lines
158-166). If the escalated tier still fails, the work normally merges anyway with residuals tracked
as new linked defect issues; the only thing that blocks that merge is reproduced evidence of data
loss/destructive behaviour or a security exposure (lines 175-192).

**ADR-001** (`docs/adrs/adr-001-code-review-executor-boundary.md`, an architecture decision record
— a durable, cross-repository record of a structural decision and its rationale) draws the boundary
that matters most here: the Saga Code Review plugin, "installed here at version 0.157.1," is a
"policy-free executor" with **no authority** over what a lens means, its dimensions, anchors,
strictness, threshold, catalogue membership, always-on status, or acceptance shape (lines 33-92).
Crucially, **the plugin does not consume any of this yet**: "Until the plugin consumes the generated
roster, the plugin's own `lens-roster.json` remains the live executable policy" — that file names
**fourteen** lenses, not the sdlc's fifteen (lines 33-37,110-118). So today's code review is scored
against the plugin's own bundled fourteen-lens roster, not the catalogue above; divergence is
reported, never enforced, until the plugin changes (`gen_review_roster.py --check`, non-zero only
under `--strict`) (lines 114-118).

## 5. Gates

The primary, canonical table (`docs/process/gates.md`, "the one gate-authority table for the SDLC,"
line 11) names five checkpoints (`docs/process/gates.md:107-112`):

| Gate | Applies | Blocking? | Advances phase? | What it tests |
|---|---|---|---|---|
| Internal code review (`code-review`) | Inside the work loop, before pull-request | Advisory | No | Quality-lens findings; holds no merge authority |
| Plan document review (`doc-review`) | Every `/plan` output, before `/work` | Blocking | Yes (`review`→`work`) | Unresolved P0/P1 findings against the plan |
| Plan readiness review (`plan-review`) | Before dispatch | Blocking | No | Readiness before implementation is assigned |
| Quality-assurance verdict (`qa`) | After merge and non-production deployment | Advisory | Yes (`qa`→`retro`) | Acceptance evidence against a severity threshold |
| Team-owned pull-request review (`team-owned-pr-review`) | Every pull request, before merge | Blocking, not overridable by one person | Yes (`work`→`qa`) | Plan fidelity, tests run, docs updated, approval boundaries understood |

A larger, separate 48-gate census exists (`docs/process/gate-catalogue.md`, sourced from a
2026-08-29 audit): **6 advisory, 35 blocking, 7 unclassified**
(`docs/process/gate-catalogue.md:137`). An unclassified gate is an explicit third state — "pauses
for an operator decision... never silently blocks and never silently advances"
(`docs/process/gate-catalogue.md:117-121`). Of the 48, 33 name no owner at all (the literal string
`not stated`) (`docs/process/open-questions.md:53`). One row, `wip-limits` (work-in-progress limits),
is kept only because census membership is fixed, but is retired and describes nothing live — the
organization has decided against any card-count cap anywhere (decision E6, 2026-09-06)
(`docs/process/gate-catalogue.md:82-91,191`, `docs/process/kanban-workflow.md:236-241`). Gates
most relevant to a plugin simplification pass, from that 48-row table
(`docs/process/gate-catalogue.md:145-192`): `andon-cord-safety-halt` (blocking, fabricated evidence
or unsafe mutation), `card-contract-at-creation` (blocking, refuses a malformed issue),
`prepared-issue-readiness-checks` (blocking, the Issue Reviewer's six checks), `no-force-push` /
`no-committing-secrets` / `no-gate-weakening` (blocking absolute invariants), `saga-code-review`
(advisory, "does not itself move the saga phase"), `work-hard-test-gate` (blocking, tests required
for risky change-kinds), and three identical `*-active-gate` rows for Operations/Asgard/CAMPPS — one
Planning-to-Active readiness rule seen from three boards.

**The floor no team may omit**: five named floor gates that bind every team regardless of local
practice — `planning_to_active`, `document_review`, `code_review_acceptance`, `verify_evidence`, and
`approval_boundary_safety` (`docs/roles/responsibilities.md:164,241`). A team may reassign *who*
performs a floor-gate responsibility; it may never make the gate stop applying to work it actually
does (`docs/roles/responsibilities.md:161-166`).

## 6. Branching, merging, worktrees, and concurrency

Two documents carry this at different authority levels: `multi-agent-collaboration.md` is
in-production (current practice), while `parent-branch-integration.md` is forward-looking —
"this document describes the agreed target workflow; none of it is implemented yet"
(`docs/process/parent-branch-integration.md:13`).

**Today** (`docs/process/multi-agent-collaboration.md`): simultaneous edits are resolved with
"ordinary Git merge semantics," preferring work split so collisions are rare (line 123); an
architectural disagreement goes to the Architect, who records the rationale as a durable decision
entry (lines 125-126); a priority conflict escalates to the operator (line 127).

**Target** (`docs/process/parent-branch-integration.md`): a parent issue gets a shared parent
branch; each lane's child branch is "ideally checked out in a separate worktree" (line 27). Merges
are serialized — exactly one worker holds the merge turn at a time — and the design explicitly
rejected a lock service: "A dedicated lock service was considered and explicitly rejected as
overcomplicated race management; the turn-taking above is the whole protocol" (line 43). No standing
integration-worker role exists; "one was proposed and not adopted" (line 81). Conflict ownership is
routed by kind, not by whoever is merging: a straightforward conflict is resolved by the merging
worker as normal development work; a technical/behavioural conflict under the recorded intent goes to
the Architect; a product question the recorded intent already answers goes to Product; a conflict
needing the plan itself changed returns to the Architect as that specific problem (lines 74-77). A
purely mechanical merge failure — a rejected push, a failed tool call — "raises no question for
anyone to answer and is routed to nobody": the worker holding the merge just retries under approved
recovery rules (`docs/lifecycle/run-model.md:390`). The final merge to `main` is a separate, later
step held by one dedicated Release Worker, not the lane-merging workers
(`docs/process/parent-branch-integration.md:93`).

**Concurrency has no global cap anywhere in this documentation.** "There is no single global
concurrency cap stated anywhere in this documentation, and no board work-in-progress limit exists to
supply one" (`docs/roles/run-roles.md:84-86`). Concurrency is instead resolved per run "from the live
staffing roster and the constraints that apply to each executor's vendor and account," and the
resulting allocation is recorded per hosting session in the run setup record
(`docs/roles/run-roles.md:82-84`). Work-in-progress limits were explicitly considered and rejected
org-wide (decision E6, 2026-09-06): "no Stage and no board caps how many cards may sit in it"
(`docs/process/kanban-workflow.md:227-241`).

## 7. The saga crosswalk (`docs/lifecycle/saga-crosswalk.md`)

Stability is marked **partial**, last reviewed **2026-09-05** (frontmatter,
`docs/lifecycle/saga-crosswalk.md:2-3`). It maps saga's seven stored `lifecycle_phase` values
(`ideation`, `brainstorm`, `plan`, `review`, `work`, `qa`, `retro` — the phase-tracking field the
saga command toolkit itself stores) onto board Stage, CAMPPS column, maturity produced, artifact
directory, and consuming command (`docs/lifecycle/saga-crosswalk.md:112-120`). It explicitly flags
two gaps it does not paper over: (1) "Two more reset edges exist only in the run model; neither is
performed by any tooling today" — a code-review cycle scoring below threshold, and a functional-test
failure, both of which the run model routes back into `work` but which nothing currently executes
(lines 175-190); (2) the run model's twelve steps mapped onto the seven stored phases: "nothing below
is stored anywhere yet, and no tooling runs these steps today" (lines 199-205). It also records a
plugin-relevant fact worth carrying into the simplification review: three saga commands —
`/outcome`, `/delegation-audit`, `/engines` — were only just classified (decision E10, 2026-09-07),
and `/outcome` "is expected to be removed from Saga at some point," which the crosswalk labels "an
expectation, not an implementation" (lines 52-69).

## 8. Board write authority and the intake path

**Who may write Stage/Status:** "Mission Control is the only routine executor of a card's board
Stage and Status fields. Saga and Orchestrate may decide that a card's lifecycle position should
change and submit that approved move through Mission Control, but neither may compose or execute the
write itself" (`docs/process/saga-board-write-authority.md:15-18`). Six specific (Stage, Status)
pairs are the only moves Saga may submit (lines 32-39); every other project field, `Objective`
included, "sits outside this boundary" (line 58). The write mechanism is all-boards-or-none: it
"discovers all boards carrying the issue," preflights every field, "writes all carrying boards, or
none," and compensates already-written boards on failure (lines 84-91).

**What the operator answers up front, per `docs/process/human-intent-intake.md`:** the Shaping exit
requires three things settled before any run starts — product content (co-authored by the operator
and Product), the issue's technical context (authored by the Architect, including a mandatory `Risk`
tier of low/medium/high/very-high with a one-sentence justification), and an independent Issue
Review returning `ready`/`not ready` against six named checks (lines 96-142). This entire sequence is
marked forward-looking: "No tooling runs it, and no Issue Reviewer is staffed today" (line 99).
Separately, at run setup the operator must record scope for the seven approval-boundary categories
(production changes, destructive operations, credentials, permissions, billing, external
commitments, process-authority changes) (`docs/process/operator-escalations.md:26-33`).

**What "an agent can pick this up cold" requires** (`docs/process/card-schema.md`): the card
contract is "what a GitHub issue body must contain before an agent can pick up the work cold, with
no context and no one to ask" (lines 14-16). It has 14 fields, 9 always required, 5 optional or
risk-conditional (line 77). It is enforced by `card_validator.py`, which lives in a *different*
repository, `home-lab`: "If the validator changes and this doc doesn't, the validator wins" (lines
33-36). Stage and Status are initialized atomically at the Intake exit by Mission Control's
prepared-issue path (`issue prepare` → `issue create-prepared`)
(`docs/process/human-intent-intake.md:194-197`).

## 9. Open questions the sdlc itself records

`docs/process/open-questions.md` states the register is currently **empty**: "There are none today.
Twenty-five questions were registered here; all twenty-five were decided by the operator on
2026-09-06" (line 21). It is explicit that empty is a state, not a finished design: "An empty
register is not the same as a finished design" (line 23), and it names three counted, unresolved
gaps that are real even though none is a registered "open question": **33 of 48 gates name no
owner**; **7 of 48 gates are still unclassified**; and **11 of 15 code-review lenses cannot be scored
today because no fixtures exist for them** (lines 53-55). It also repeats the run model's "133
elements... all settled" claim at face value (line 57) — which, per Section 2 above, conflicts with
a stale 117-element table later in the same run-model document that this open-questions page does
not surface. Distinct from this design register, several documents also carry live, unverified
`UNKNOWN` facts about the deployed system itself: whether the `olympus:*` Redis channels (a
message-bus namespace) still carry traffic (`docs/tools/index.md:101-110`); the convention-file names
Grok, OpenCode, and Antigravity auto-load (`docs/tools/ai-tooling.md:31-35`); mechanical-check
tool-chain pins for any non-Python stack (`docs/reviewers/code-review-lenses.md:208`); and whether a
given repository's `main` branch is directly consumed by users, which the Delivery Manager must ask
about rather than assume "no" when unstated (`docs/process/operator-escalations.md:165-168`).

## 10. Tooling expectations

Four plugins carry lifecycle-mutating authority, stated identically across three documents
(`docs/tools/index.md:179-182`, `docs/tools/ai-tooling.md:81-86`, `docs/tools/atlas.md:36-41`): **saga**
owns lifecycle choice, local state, and routing; **mission-control** owns GitHub issue mutation
(bodies, labels, project fields); **deploy** owns tag promotion and deployment mutation;
**team-execution** owns reviewer and validator orchestration. **Hermes** is a separate deployed
process (not a plugin) that dispatches work and coordinates plan-review and pull-request-review
events but "does not review code" and is "not a generalist agent" (`docs/tools/index.md:87-88`).
**Herdr** starts and supervises agent sessions across vendors but has no capability to clear or
compact a session's context (`docs/tools/index.md:143-153`).

Automatic today, versus by hand: Mission Control's prepared-issue path initializes Stage and Status
at the Intake exit automatically (`docs/process/kanban-workflow.md:222-224`); the constrained
lifecycle-field mutation writes Stage and Status atomically across every carrying board, all-or-none
(`docs/process/saga-board-write-authority.md:84-91`); and a documentation-gate continuous-integration
workflow enforces frontmatter validity, internal links, schema parity, and generated-region currency
automatically (`docs/process/gate-catalogue.md:159-165`). By contrast, most of the run model — all
twelve steps, the Issue Reviewer, the multi-lens code review as an authoritative gate, both repair
loops, and the deploy-then-test sequence — is a design nothing executes yet (Section 2); where any of
it happens today, it is the operator or an individual agent session acting by hand, loosely
coordinated by Hermes' plan-review dispatch and the saga toolkit's own phase tracking. The closest
sdlc analogue to "run everything automatically" is the **bounded work authorization**: once granted
for one work item, it "carries that change through merge and non-production deployment with no
second prompt," but "creates no standing authority" beyond that item
(`docs/roles/responsibilities.md:220-224`, `docs/process/operator-escalations.md:78-80`). Every saga
slash command, its board Stage, and its gate behaviour is the generated table at
`docs/tools/atlas.md:90-152`; two named exceptions: `/delegation-audit` has no command file at all
("never routable... the skip is knowing, not silent," line 145), and `/engines` is excluded from
lifecycle classification entirely (line 151).
