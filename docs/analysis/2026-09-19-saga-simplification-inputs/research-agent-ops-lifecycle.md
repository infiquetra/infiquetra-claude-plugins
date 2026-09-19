# How work actually flows, and what has already been decided about simplifying the lifecycle

This brief surveys `/Users/jefcox/workspace/infiquetra/infiquetra-agent-operations`, the operator's
private daily-coordination record for coding-agent sessions run through Herdr (a terminal-workspace
manager that keeps many agent panes open across named work areas). It answers a different question
than yesterday's brief on the same repository (`docs/analysis/2026-09-18-typesafe-jev-research-inputs/
research-agent-operations.md`, which looked for places a fast judgment model could plug into the daily
loop): this one extracts how work concretely flows through Saga (the operator's lifecycle plugin for
Claude Code) and its neighboring plugins today, and what the operator has already concluded about
making that lifecycle lighter, so the main thread does not re-derive or contradict settled ground.

## 1. How work flows today, step by step

The fullest documented trace is **L7**, the CAMPPS (Children's Activity Management and Program
Planning System) delivery objective covering the web application's admin and operations surfaces,
run September 12-15 in Herdr workspaces `w70`/`w81`/`w82`
(`docs/operations/2026-09-12-l7-web-app-workspace-planning.md`,
`2026-09-12-l7-web-app-lead-handoff.md`, `2026-09-13-l7-web-app-recovery-handoff.md`).

**Intake.** Work starts from an existing GitHub issue hierarchy, not a fresh idea: an orchestration
parent issue (`campps-context-library#44`) with 38 native child issues. Jeff first authorizes creating
Herdr workspaces "for inspection" only — creating the panes is explicitly not dispatch
(`2026-09-12-l7-web-app-workspace-planning.md`: "Workspace preparation does not... Dispatch planning
or implementation work merely by creating Herdr workspaces or seats").

**Roles**, per `docs/operations/lead-handoff-role-boundaries.md`: Lead (also called Delivery Manager)
coordinates and never implements; Product resolves intended behavior; Architect resolves technical
contracts and shared-file ownership; Issue Reviewer checks issue completeness; Planner writes the
implementation plan **and** a separate finite independent test plan; Plan Reviewer reviews both;
Test Authors (named individually — "Test Author One," "Test Author Two," never "an Author") write
tests before a developer touches the code; Developers (numbered, each with exclusive file ownership)
implement; exactly one Code Reviewer runs Saga's `/code-review`; Standard Repair Developer and Expert
Repair Developer implement fixes — Expert is an escalation tier, never a second reviewer; Investigator
diagnoses failures; Release Worker merges and deploys; Functional Tester independently exercises the
deployed result in a real browser. Each role runs as its own named Herdr pane, on whatever coding-agent
product Jeff assigned that day — the L7 roster alone mixed Antigravity (running Google's Gemini),
Claude Code, Codex (OpenAI's client), native Muse, Cursor (running xAI's Grok), and Ollama Cloud.

**Documents produced**, in order: a workspace-planning document (scope, exclusions, batches, shared-file
custody, roster); a lead-handoff document (role table, dispatch table, and the exact text for the
`/goal` slash command that activates the run); a recovery-handoff document when a Lead's session context
is lost or replaced (`2026-09-13-l7-web-app-recovery-handoff.md`); and, at the end of a work period, a
dated entry under `docs/operations/daily/`.

**Plugin commands invoked.** The coordinator prompt template embedded in
`docs/operations/single-issue-delivery.md` literally opens with `/plan issue <issue-number>`, and tells
the Doc Review pane to "run the installed Saga `/doc-review` process," the implementer to "Run Saga
`/work`," and the Code Review pane to "run the installed Saga `/code-review` process as the genuine
Code Review controller." Mission Control — a separate Claude Code plugin, not Saga — is now the only
agent allowed to write the GitHub project board's `Stage` and `Status` fields. Two Saga releases,
labelled W7 (version 0.145.0) and W8 (version 0.146.0) in the plugin's own changelog, deliberately
removed Saga's own authority to move board cards so Mission Control could be the sole writer, but the
evidence packages found the handoff was left half-built: "Plan and Work now name the move and invoke
nothing" (`docs/operations/saga-capability-cross-synthesis.md`).

**Merge and close.** A Release Worker merges through the repository's ordinary pull-request and
continuous-integration process — Saga does not own merge or deployment. A child issue enters "Verify"
only after merge and a real deployment, and a Functional Tester's browser acceptance is required before
it closes: "Local widget green is not deployed proof" (`2026-09-12-l7-web-app-workspace-planning.md`).
A parent issue closes only after the Lead reads back the actual merge and deployment evidence for every
child (`lead-handoff-role-boundaries.md`, "Read back the merge before closing a parent").

**End of day.** The Daily Operations console (a long-running Codex voice conversation) works through
the nine-step `docs/operations/end-of-day-closeout.md` runbook: refresh live state, reconcile the
session queue, write the day's file under `daily/`, and promote durable lessons into
`docs/engineering-journal/`.

## 2. Usage census

`grep -rl` / `grep -rc` across `docs/operations` for the literal strings gave inflated counts for
several tokens because the slash-prefixed string is also a substring of an unrelated word in a path:
`/work` matches inside `/workspace`, `/workflow`, `/worker(s)`, and `/worktree(s)`; `/plan` matches
inside `/plans`, `/planning`, and `/planned`; `/retro` matches inside every occurrence of the word
`retrospectives`; `/spec` matches inside `/specs` and `/specification(s)`. The table below reports the
raw count and, for the four contaminated tokens, a corrected count with the false-positive suffixes
excluded.

| Token | Files (raw) | Occurrences (raw) | Corrected occurrences | Most recent dated file |
|---|---:|---:|---:|---|
| `/plan` | 121 | 417 | 56 | `saga-plan-evidence-package.md` (2026-08-29) |
| `/doc-review` | 26 | 47 | — | `2026-09-11-sdlc-research/execution-evidence.md` |
| `/work` | 499 | 6,103 | 47 | `saga-work-evidence-package.md` (2026-08-29) |
| `/code-review` | 106 | 305 | — | `2026-09-11-sdlc-research/scope-and-sources.md` |
| `/qa` | 14 | 21 | — | `2026-09-11-sdlc-research/baseline.md` |
| `/handoff` | 23 | 41 | — | `daily/2026-09-12.md` |
| `/outcome` | 13 | 26 | — | superseded research draft |
| `/loop` | 26 | 40 | — | superseded research draft |
| `/resume` | 11 | 13 | — | mostly incidental (a JSON field) |
| `/retro` | 116 | 392 | ~4 real | `saga-current-behavior-review-program.md` |
| `/ideate` | 1 | 1 | — | `saga-current-behavior-review-program.md` only |
| `/brainstorm` | 25 | 40 | — | `RUN-LOG.md` (2026-09-05) |
| `/spec` | 12 | 22 | 3 | `saga-document-review-evidence-package.md` |
| `/investigate` | 3 | 3 | — | superseded research draft |
| `team-execution` | 15 | 21 | — | `DOCUMENTATION-IMPLEMENTATION-PLAN.md` |
| `orchestrate` | 72 | 294 | — | `2026-09-11-sdlc-research/scope-and-sources.md` |
| `herdr` | 136 | 2,992 | — | `2026-09-15-talaria-w7W-lead-handoff.md` |
| `codex` | 152 | 1,510 | — | `2026-09-15-talaria-w7W-lead-handoff.md` |
| `gemini` | 46 | 370 | — | `2026-09-13-mission-control-alignment-goal.md` |
| `mission-control` | 53 | 184 | — | `2026-09-13-mission-control-alignment-workspace-planning.md` |
| `fleet-core` | 1 | 1 | — | one retrospective JSON extract |
| `agent-launcher` | 46 | 165 | — | `2026-09-11-sdlc-research/scope-and-sources.md` |
| `worktree` | 335 | 1,447 | — | `2026-09-15-talaria-w7W-lead-handoff.md` |
| `lease` | 289 | 1,090 | — | `2026-09-15-talaria-w7W-lead-handoff.md` |

**Saga commands in actual documented use.** Only `/plan`, `/work`, `/doc-review`, and `/code-review`
appear as literal, embedded invocation text in a runbook or handoff (`single-issue-delivery.md`'s
coordinator prompt; the repeated instruction "use the installed Saga Work and Code Review" across the
L7 and SDLC-update handoffs). `/qa` appears only as a discussion topic in the September 11 research,
not as an invoked command. **Commands that never appear as used**: after removing path contamination,
`/retro` has no genuine invocation anywhere in this corpus — every real hit either names the
`docs/operations/retrospectives/` directory or discusses the command as a diagram label in
`RUN-LOG.md`. `/ideate`, `/investigate`, `/spec`, `/outcome`, `/loop`, `/resume`, and `/handoff` (the
Saga skill, as distinct from the everyday English word "handoff" used for Jeff's own Lead-handoff
documents) show no evidence of being run — all are listed, verbatim, as "Not reviewed in this program"
in `saga-current-behavior-review-program.md`. `/brainstorm` was run once, on 2026-08-27, to produce a
review artifact about itself, not for product ideation.

## 3. The saga current-behavior review program

Five of roughly twenty Saga capabilities were reviewed against Saga 0.143.0, then re-verified against
`origin/main` (Saga 0.147.0) on 2026-08-29 (`docs/operations/saga-current-behavior-review-program.md`).
A governing sentence recurs across every package, first stated for Brainstorm and then explicitly
tested against each other capability: **"Brainstorm should remain a creative conversation rather than
becoming a fixed questionnaire or a stage-gate script... add no rigidity without demonstrated value"**
(`saga-brainstorm-change-candidates.md`).

**Brainstorm.** Mostly small provenance and continuity fixes were approved (record which capability
produced an artifact; restore a pending confirmation without replaying the conversation). Explicitly
**rejected**: "a preset number of critique rounds before Brainstorm may present its scope-confirmation
boundary" and named assurance levels ("Low, Standard, or High") until repeated use proves they are
needed.

**Plan.** Top finding: Saga's W7 release deleted Plan's authority to move a board card to `Shaping` or
`Ready`, but nothing replaced that move — "on an ordinary interactive `/plan` run the Shaping and Ready
moves fall to the operator by hand — and neither section tells the operator that a move is owed"
(`saga-plan-evidence-package.md`). Second finding: the "Claude Code Workflow," an alternate execution
backend, occupies 44.9% of Plan's instructions for a path recorded in 0 of 137 saved plans; the
recommendation is to relocate it to a reference file, not delete it, because a closed issue (#808)
already ruled against retiring it.

**Work.** "Work changed more than any other capability in this window." After W7 and W8, Work no
longer moves a card to `Active`, `Verify`, or `Done`: **"Saga now writes zero of the six [board]
rungs... Ready has no automated writer at all."** The same unused-backend problem recurs: "A quarter of
the skill governs a branch the recommender cannot reach" (247 of 886 lines for the Workflow backend,
again 0 of 137 plans).

**Document Review.** Unchanged byte-for-byte since the earlier review. Its single highest-value defect:
the documented rubric command "fails from where sessions actually run" when run from the repository
root, and the skill's own degrade rule then says to continue anyway — **"The formal review layer can
silently evaporate."**

**Code Review.** Reframed by a new "publication lane" (release W18, version 0.144.0) that lets the
reviewer commit and push its own review document — "no longer accurate" that it is read-only. Live
data from a sibling repository showed **"every published review is born one commit stale"** against the
freshness checks other commands depend on. Jeff's recorded disposition: publish findings only as a
pull-request comment, never an approving review — **"preserve independent approval"** — and require
explicit consent before that publish step.

**Cross-synthesis.** No candidate is claimed by two packages; one cross-package recommendation (a
plan-artifact staleness gate) was independently challenged and withdrawn on evidence. The synthesis
names an unrelated but separately maintained mechanism, "the external-engine second opinion," as
worth **removing**: "Dead-but-maintained machinery is worse than removed machinery because it
*presents* as live" (`saga-code-review-evidence-package.md`), and Jeff's recorded disposition adopts
that: "Remove Work's in-process external-engine second-opinion offer and its feature-specific dispatch,
sidecar, streak, and state machinery."

**GitHub issue cross-references.** The packages name many *closed* issues as already-settled policy —
#812, #808, #776, #418, #403, #394, #393, #358, #344, #450, #593, #565, #369, #373 — and three *open,
unboarded* issues as adjacent live defects: #884, #885, #886, plus #908 with children #892-#899 and
#902. None of these fall in the 920-946 or 1001-1005 ranges named in the task; by 2026-09-13 the
Mission Control alignment work (`2026-09-13-mission-control-alignment-goal.md`) references issues
#1004, #999, #1000, and #942 instead. This repository's own records do not show 920-946 or 1001-1005
directly; confirming whether the brainstorm candidates became those specific numbers needs a live
GitHub read this repository alone cannot supply.

## 4. Lifecycle redesign and the SDLC research

The clearest already-decided direction predates the September 11 research by ten days.
`docs/operations/lifecycle-redesign/2026-09-02-issue-to-working-software/CHARTER.md` opens with the
diagnosis: **"Jeff's judgment is that the underlying flow — the actual step-by-step path a piece of
work takes from a defined issue to verified working software — has never been agreed on explicitly. It
has been inherited from the tools rather than chosen."** The same file states the standing rule for the
whole effort: **"Subtraction is a legitimate outcome. Do not default to proposing more gates, more
reviewers, more required artifacts, or more status fields."**

From the discussion record itself (`DISCUSSION-DECISIONS.md`, 2026-09-02), quoted decisions:

- On merge coordination: **"He explicitly rejected an overcomplicated race-management process and
  suggested that the controller indicate when a worker may merge."** The adopted design: "the run has
  a parent issue branch, children implement on their own branches, ideally in separate worktrees, and
  completed child work merges back into the parent branch," with the controller tracking whose turn it
  is "as ordinary execution state, not another operator approval or receipt ceremony," and the worker
  doing the merging resolving ordinary conflicts itself.
- On handoffs: **"Jeff explicitly rejected turning handoffs into extra receipt-validation process. The
  purpose is for the controller to know where work is and what happens next, not to defend against
  hypothetical forged receipts in personal tooling."**
- On scope discipline generally: **"Jeff emphasized keeping the process simple and increasing
  complexity only when a demonstrated need emerges. Do not add hypothetical failure machinery or new
  approval layers merely to make the conceptual design appear comprehensive."**
- On roles: an agreed four-part separation — Controller (routine dispatch), Orchestrator (judgment and
  exceptions), Planner (decomposition), and Workers/reviewers/testers — explicitly replacing a proposed
  dedicated "integration worker" role: **"The coordinator's dedicated integration-worker suggestion is
  not adopted."**

`SYNTHESIS.md` (2026-09-02), reading five research summaries together, adds two measured findings that
motivate lightening the process: **"The review gate does not decide delivery, and its shape has no
precedent"** (the installed acceptance rule passed only 17 of 52 score-bearing review cycles, yet seven
of eight studied runs merged anyway) and **"Coordination, not implementation, is where the cost is"**
(coordination was 42.7% of measured spend). `CONCEPTUAL-WALKTHROUGH.md` states the resulting design
principle in its own header: **"Design principle: start simple... they do not automatically require
additional sessions, ceremonies, or approval gates."**

This effort's actual output was a documentation and interactive-site design exercise (accepted by Jeff
around 2026-09-03) that does not appear, from this repository's record, to have been implemented into
Saga itself. The later September 11 research treats it explicitly as background, not baseline:
`2026-09-11-sdlc-research-workspace-planning.md` lists it as an entry point "as historical context,
explicitly distinguishing superseded drafts from the current baseline."

The September 11 SDLC research (`docs/operations/2026-09-11-sdlc-research/`) compared the published
lifecycle rules against ten real CAMPPS runs and reached a narrower conclusion, stated plainly in
`candidate-report.md`: **"the change set is smaller and, in my judgment, right."** Of thirteen
candidates, the final disposition was 3 recommended, 2 "existing-rule enforcement," 4 to investigate,
3 rejected, and 1 reclassified as documentation housekeeping — including explicit rejections of
**C-13 (using continuous integration as an admission gate)** and **C-12 (cross-run prerequisite
ownership)**. The operator's own next-session note (`daily/2026-09-12.md`, preserved by the commit for
pull request 23, `3cb7a02`) calls the whole research **"worth selective adoption, not a wholesale
rewrite."**

What actually shipped from that research is commit `01418a4` ("docs(operations): add governing
lifecycle reading list and admission SDLC revision capture," 2026-09-12), a 47-line addition to
`lead-handoff-role-boundaries.md`. It names six chapters in the `infiquetra-sdlc` repository as the
only real governing authority for gates, entry into "Verify," closure, and board writes, and
demotes the more elaborate `docs/lifecycle/run-model.md` document to reference status: **"`docs/
lifecycle/run-model.md` describes the target run design rather than current run authority; where it
and the six chapters above differ, the six chapters govern."** It adds one required line per run — the
exact source-control revision of the lifecycle rules a run is following, resolved "at admission" — and
a merge-and-delivery readback step before any parent issue closes. The implementation plan that
followed (`2026-09-12-sdlc-targeted-update-plan.md`) is a small, bounded edit: two wording
corrections, moving a documentation-publishing workflow off self-hosted runners, and this same
companion change — not a lifecycle rewrite.

## 5. Recorded pain

- **The review gate itself, called a formality:** "A gate met in 4 of 29 attempts is not a gate; it is
  a formality that work routes around, and every cycle spent against it is process cost."
  (`docs/engineering-journal/LEARNINGS.md`, 2026-08-31)
- **Unused machinery kept alive by presenting as live:** "Dead-but-maintained machinery is worse than
  removed machinery because it *presents* as live: another reviewer in this very program spent evidence
  budget documenting a second-opinion section whose carrier has never executed."
  (`saga-code-review-evidence-package.md`, 2026-08-29)
- **A backend nobody uses, occupying most of a skill file:** "A quarter of the skill governs a branch
  the recommender cannot reach" — 247 of 886 lines of Work's instructions, and 44.9% of Plan's, for an
  execution path recorded in 0 of 137 saved plans. (`saga-work-evidence-package.md`,
  `saga-plan-evidence-package.md`)
- **Explicit rejection of adding ceremony to fix a coordination failure:** "Jeff emphasized keeping the
  process simple and increasing complexity only when a demonstrated need emerges. Do not add
  hypothetical failure machinery or new approval layers merely to make the conceptual design appear
  comprehensive." (`DISCUSSION-DECISIONS.md`, 2026-09-02)
- **A named "stop" against retrospective process growth itself:** "Stop adding record types, store
  maps, approval ceremonies, or model rankings to the retrospective method... Do not turn this
  retrospective into another oversized process: the expensive failures were over-built shared fixtures,
  invented approval waits, and instruction overgeneralization, not missing ceremony."
  (`docs/operations/retrospectives/2026-09-09-campps-after-action/analysis/improvements.md`, "S8")
- **Invented approval waits named as the actual defect**, not a gap in approval: "Stop re-requesting
  preparation, admission, or routine repair already in the standing table... a readiness report is a
  progress report, not a new approval gate." (same file, "S1")
- **A gate proposed and refused because it duplicates a rule already agreed:** the September 11
  research rejected treating continuous integration as an admission gate and rejected adding a new
  sentence to the lifecycle text for a coordination failure that "is not fixable by text"
  (`2026-09-11-sdlc-research/candidate-report.md`).

No file in this corpus applies the word "race-obsessed" to Saga, team-execution, Orchestrate, or
fleet-core. The one explicit rejection of "race" language names a *proposed* mechanism the coordinator
had floated, not a repair for something that had gone wrong: "He explicitly rejected an overcomplicated
race-management process" (`DISCUSSION-DECISIONS.md`). The real incidents recorded are collisions in
shared state rather than git-level merge races — see Section 8.

## 6. Reviews, scans, and validation in practice

Saga Code Review is the near-universal pre-merge gate, run as its own dedicated Herdr pane, and the
rule that there is **exactly one** Code Reviewer is treated as load-bearing: a Lead who dispatched its
Expert Repair Developer as a second reviewer during the COPPA (Children's Online Privacy Protection
Act) consent run was corrected, and the fix was written into
`lead-handoff-role-boundaries.md` as a standing boundary, not a one-off note. Reviewer and implementer
are often deliberately different products — Talaria's Code Reviewer ran on Codex at "Sol High" while
its developers ran on Grok, specifically for an independent read
(`2026-09-15-talaria-w7W-lead-handoff.md`).

There is no dedicated Saga security- or dependency-scanning capability in routine use. Instead, ordinary
engineering tools run inside the developer's own pre-review step, a pattern Jeff endorsed directly:
"reuse established engineering tools such as linters, formatters, code-cleanup tools, type checkers,
and static analyzers... Implementers should run the applicable tools before handing work to review"
(`DISCUSSION-DECISIONS.md`). The closest real example is Talaria's pre-merge checklist — `ruff check`,
`mypy`, `bandit` (a Python security linter), `git diff --check`, and a manual conflict-marker search —
run as plain shell commands by the release-owning developer, not through a separate Saga capability
(`2026-09-15-talaria-w7W-lead-handoff.md`).

Quality assurance is a separately named "Functional Tester" role that must exercise the real deployed
build, never a local or widget test: "Local widget green is not deployed proof"
(`2026-09-12-l7-web-app-workspace-planning.md`), and `operating-model.md`'s evidence rules generally
forbid treating a report of success as the same thing as verified success. `unattended-orchestration.md`
adds that review should target "integration waves, not every worker unit" — batch several children into
one pull request and one Code Review pass so "review does not dominate delivery."

`controller-model-selection-and-loop-discipline.md` and `unattended-orchestration.md` give explicit,
narrow model and loop guidance rather than a general ranking. Fast, cheap models (Gemini 3.8 Flash) are
usable for routine dispatch only paired with an explicit blocking wait command
(`herdr agent wait`) — the same model was twice observed to stall mid-run by ending its turn with a
conversational sign-off instead of calling that command, once in the CAMPPS run and once in this
repository's own SDLC research workspace. Stronger, slower reasoning models are reserved for Architects,
Research Leads, and Code Review. Both files carry an unusually strong disclaimer against their own
content: the model-comparison table "has no reproducible evaluation record and must not determine
staffing defaults." Stop conditions throughout the corpus are evidence-based, never label-based: Herdr's
`idle` and `done` states are repeatedly and explicitly said not to prove a task succeeded.

## 7. Intake and up-front questions

`unattended-orchestration.md`'s "Make The Parent Issue Decision-Complete" step is a genuine batch-the-
questions-up-front gate: nine questions the parent issue "should answer... that would otherwise
interrupt the run." The `lead-handoff-role-boundaries.md` "controller continuation contract" section
does the same for handoffs: name every prerequisite's owner, every model and effort choice, and every
ambiguity before dispatch, "rather than inheriting a developer's settings" mid-run.
`2026-09-12-l7-web-app-workspace-planning.md` carries a literal, minimal example: a short "Unresolved
operator choices (carry, do not invent)" list naming exactly which two or three decisions are genuinely
Jeff's, with everything else left to the Lead and Architect.

But the same repository explicitly resists turning that admission step into ceremony. Jeff "explicitly
rejected turning handoffs into extra receipt-validation process" (`DISCUSSION-DECISIONS.md`), and the
September 11 research rejected using continuous integration as an admission gate (candidate C-13). Most
directly, `OPERATOR-REPORTS.md` records Jeff's own complaint about the admission boundary being drawn
in the wrong place, not being too small: **"False operator-only acceptance boundaries — decisions are
routed to the operator that did not need to be, and steps wait on his acceptance where an automated or
agent-owned check would have settled it. The boundary is treated as fixed when it was never
deliberately drawn... this entry is also most likely to point at removing a control rather than adding
one."** No document describes a formal "intake form"; the practice is a short, per-run, hand-written
list of exactly what is undecided, not a standard template.

## 8. Worktrees, branches, merging

Two different words are easy to conflate in this repository: a Herdr "workspace" is a named set of
terminal panes (`workspaces.md` inventories these), while a git "worktree" is an isolated working
directory for one branch. Both appear constantly and are handled separately.

The actual branch-and-worktree design, agreed 2026-09-02, is close to what a simplified lifecycle would
need: "the run has a parent issue branch, children implement on their own branches, ideally in separate
worktrees, and completed child work merges back into the parent branch," with the controller granting
one worker at a time the "merge turn" as ordinary execution state, and the merging worker resolving its
own straightforward conflicts — escalating only a conflict that requires a genuine product decision
(`DISCUSSION-DECISIONS.md`). `unattended-orchestration.md`, the runbook actually in force, matches this
shape: merge one pull request at a time on a shared release surface, re-integrate `main` into surviving
branches immediately after each merge, and assign exactly one owner to repair a blocker several units
hit at once rather than letting each unit patch it independently.

Recorded collisions that actually happened, not merely feared:

1. **Duplicate concurrent repairs of the same shared problem.** Two parallel units on the same run
   independently patched the same width-sensitive test assertion, producing two conflicting commits at
   reintegration (pull requests #833 and #834 in `infiquetra-claude-plugins`); the fix adopted was "one
   repair owner" for any blocker several units discover at once (`docs/engineering-journal/LEARNINGS.md`,
   2026-08-25, "Shared run blockers need one repair owner").
2. **A genuine last-writer-wins race in shared data**, not source code: four Herdr lanes writing to the
   same JSONL (line-delimited JSON) file during the orchestration-quality retrospective's own data
   collection silently dropped each other's records — "the second write carries the first lane's stale
   copy" (`LEARNINGS.md`, 2026-09-01, "Concurrent lanes rewriting one JSONL file silently drop each
   other's records").
3. **A real, filed-but-unfixed worktree defect**: open issue #886, "Orchestrate: relaunching a unit
   reuses stale worktree, strands undelivered prompts, and accumulates duplicate live controllers,"
   recorded as "an observed Auralis-run residual" rather than a hypothetical
   (`saga-capability-cross-synthesis.md`).
4. **Cleanup that looked complete but was not**: a successful `gh pr merge --delete-branch` left the
   remote branch behind because a linked local worktree was still holding the local branch open
   (`LEARNINGS.md`, 2026-08-25, "Merge-time branch deletion does not prove remote cleanup").
5. **Ordinary environment friction, not a race**: fresh worktrees on a run lacked a Python virtual
   environment, forcing an extra setup step into the review gate
   (`retrospectives/2026-08-31-orchestration-quality/REPORT.md`, line 1309).

The one place this repository explicitly names "race" is a rejection of a *proposed* mechanism, not a
repair for a git-level race that had actually occurred: "He explicitly rejected an overcomplicated
race-management process." The failures that did occur were collisions over shared files, shared board
fields, and shared worktree state — exactly the class of problem simple one-at-a-time merge turns and
serialized shared-file ownership (already the agreed design) are meant to prevent, not evidence that
richer locking or reservation machinery was needed.
