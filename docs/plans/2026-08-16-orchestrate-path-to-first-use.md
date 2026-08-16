# Orchestrate: the path to first use

**Status:** ready for review · **Date:** 2026-08-16 · **Supersedes:** the unit ordering in
`2026-08-15-orchestrate-boundary-and-review-machinery-plan.md`, which is now complete except for its
units 3, 4 and 5.

This plan answers one question: **what stands between `main` today and an operator installing the
orchestrate plugin and running a real multi-vendor job.** It settles the repair-versus-rebuild
question for the composed runner with executed evidence rather than preference.

## Where `main` actually is

Twelve modules and one skill ship today. The boundary correction is complete: the durable register
keeps authored intent and outcomes, and every live session fact is asked of the terminal control
plane at the moment it is used. The review machinery — the loop bound, its escalation rule, the
multi-reviewer panel, and external reviewers as managed sessions — is merged and in service.

What does **not** ship is the thing that makes eleven modules a product. The skill says so itself:
*"No composed runner or slash command yet."* There is no `commands/` directory in the plugin at all.

```
operator installs the plugin
        |
        v
  gets a SKILL describing modules
        |
        X   no /orchestrate command to invoke
        X   no composed control flow to drive them
```

## The decision this plan settles: repair the composed runner, do not rebuild it

The composed control flow is 3,656 lines on the closed branch `feat/orchestrate-u8-composition`. It
was written against the *old* boundary, where the register stored live session facts. The question
has been open since the correction: repair it in place, or rebuild it against the corrected boundary.

**Repair. The evidence is not close.**

| Probe | Result |
|---|---|
| Does the runner import against merged `main`? | **Yes** — loads clean, no missing symbols |
| Register write calls in the runner | 24 |
| …that write a **removed** column at top level | **0** |
| Row reads of removed columns needing redirect | **30** |
| Read-through readers already on `main` to redirect to | 6 |
| Unrepaired merge-blocking defects from its own review | 3 |

The seven apparent write sites are all false positives on inspection: `vendor` is authored intent the
correction deliberately keeps, the `pid` written is the coordinator's own rather than a child
session's, and the one `tab_id` sits nested inside an owned fence field, not as a register column.

So the runner is not a 3,656-line rewrite. Rebuilding would discard working control flow to
re-derive it, which is the more expensive path and the one with more places to introduce new defects.

**What the evidence does and does not establish.** Every row above is either an import check or a
pattern match over source. The import proves no module-level symbol is missing; it proves nothing
about whether a code path runs, because Python executes almost nothing at import time. The counts
would miss a write constructed through a variable or a mapping assembled elsewhere.

So treat "thirty read sites plus the defects below" as a **lower bound on the work, not a
measurement of it.** Unit 1's first task is to replace this estimate with an executed one: run the
composition test suite against merged `main` and count what actually fails. If that number is wildly
larger than this estimate, the repair-versus-rebuild decision is reopened before any repair starts —
that is the cheap moment to change our minds, and the only one.

**Pre-mortem, stated before we commit:** the most likely way repair fails is that a redirected read
turns a cheap dictionary lookup into a control-plane query inside a loop, and the runner becomes slow
or chatty in a way no test notices. The mitigation is a counted number, not a promise to be careful:
record control-plane snapshot calls per orchestration tick on the first green run, **commit that
number as a constant, and pin it with a syntax-tree test** the way this codebase already pins its
escalation budget. A committed number can regress and be seen to regress; "does not grow" cannot fail.

## The three defects, and which unit each belongs to

All three were filed by a three-vendor panel and none was ever repaired. **They do not all belong to
the same unit, and the difference matters:** two of them live in code that unit 2 deletes outright,
so repairing them in unit 1 would be work thrown away.

That distinction is not hypothetical. The composition branch was closed precisely because six of its
seven blocking defects lived in code the corrected boundary deletes. Repairing a layer that is about
to disappear is the mistake this campaign already made once.

**Deleted by unit 2, not repaired by unit 1.** Both live in `find_orphan`
(`runner.py:949`), whose only real caller is the subscriber supervisor at `runner.py:1792`. That
scan exists solely because the subscriber is a bare process found by searching the process table.
Once the subscriber is a control-plane-managed pane, it is found by label and the whole scan goes:

1. **A failed process query reads as an empty one.** The scan runs `ps`, never examines its exit
   status, and returns `OrphanScan(process=None, complete=True)` — "the table could not be asked"
   reported as "the table said nothing." This is what turned a pull request's checks red, and the
   diagnosis sat unread in a review report for hours.
2. **Process identity is substring-based and takes the first match**, so any process whose command
   line happens to contain the tokens is adopted.

**Repaired by unit 1**, because it survives every change below:

3. **The run label is not injective.** `task_label("run-comp", "mirror")` and
   `task_label("run", "comp-mirror")` produce one identical string. Verified by execution. Two live
   colliding tabs are refused correctly; the danger is when they do not overlap — one run's recovery
   then finds the other's tab as the sole match, adopts its identifier, and its reap closes another
   run's tab.

If unit 1 must touch `find_orphan` to get its own tests green, it does the **minimum** to make them
pass and adds no new guarantees there, because that code is scheduled for deletion. Anything more is
work discarded one unit later.

## Units, in dependency order

### Unit 1 — Repair the composed runner against the corrected boundary
**Blocks everything.**

Its **first task is measurement, not repair**: run the composition test suite against merged `main`
and record what fails. That number replaces the estimate above, and if it is far larger, stop and
reopen repair-versus-rebuild before writing any repair.

Then: redirect the row reads at the six read-through readers. Fix **defect 3 only** — the
non-injective run label — and pin injectivity with a property test rather than an example. Touch
`find_orphan` only as far as its own tests demand, since unit 2 deletes it. Bring the composition
tests across. Record the snapshot-calls-per-tick number, commit it as a constant, and pin it with a
syntax-tree test.

*Acceptance:* the full gate green on a branch cut from `main`; the measured failure count recorded in
the pull request alongside the estimate it replaces; the pinned snapshot-call constant present and
its guard proven by removal; a review by two vendors that are not the one that built it.

### Unit 2 — The subscriber becomes a managed pane
Currently a bare process found by searching the process table — the last place a live fact is
inferred rather than asked for. It becomes a control-plane-managed pane running the same script, with
a deadman check whenever the orchestrator wakes.

**This unit deletes `find_orphan` and defects 1 and 2 with it.** Removing the process scan is part of
the unit's definition of done, not a side effect: if the scan is still there afterwards, the
subscriber is still being tracked by inference and the unit has not landed.

*Acceptance:* the subscriber survives an orchestrator restart and is recovered **by label**, with no
process-table search anywhere in the plugin — proven by a syntax-tree walk asserting no `ps`
invocation remains; a deadman check fires when its pane is gone; the full gate green; reviewed by two
vendors that are not the builder.

### Unit 3 — The `/orchestrate` command surface
The operator-facing entry point. A branch for this exists and was never verified — **no check ever
ran against it** — so it is treated as unreviewed material, not as work to resume. Its input decides
how much upfront work happens: a prompt is interviewed heavily, a requirements document is grouped
and planned, a plan document proceeds almost directly to work.

**This unit also owns the skill's own description.** It currently ends *"Planning never launches. No
composed runner or slash command yet,"* and its body repeats that claim while pointing at a
superseded plan. Both become false the moment this unit lands. That string is how the skill
advertises itself for discovery, so it is shipped, user-visible surface — not a comment.

*Acceptance:* on a machine that has never run this plugin, `/plugin marketplace update` followed by a
**new session** exposes the command; the operator invokes it with a real task and a multi-vendor run
completes. The stale-cache step is part of the acceptance test, because an acceptance run against an
already-cached plugin proves nothing about installation.

### Unit 4 — First-use hardening, after a real run
Deliberately last, and deliberately unspecified, because the first genuine run is what tells us what
is wrong. Reserve capacity for it rather than planning its contents now.

**It is bounded even though its contents are not.** Unit 4 runs for **three real orchestration runs**.
Everything those runs surface is either fixed inside the unit or filed; when the third completes, the
unit closes and anything still open becomes its own plan. An open-ended hardening unit is how a plan
acquires an indefinite tail, and this campaign has already spent one time box discovering that.

### Not blocking first use
Removing the reconciliation seam (the runner shrinks once there is no shadow to reconcile — partly
absorbed by unit 1), spend accounting that cannot distinguish unknown from zero, and the Codex port.

## What "first use" means

An operator installs the plugin, invokes the command with a real task, and a multi-vendor run
dispatches children, aggregates through the mirror, wakes on events, gates on completion evidence,
and reaps — without the operator touching a register file or a script directly.

## How this gets built

Same shape as the campaign that produced the merged work, because it caught things nothing else did:
one worktree per unit, the orchestrator as sole committer, per-unit pull request, and a review panel
whose reviewers are never the vendor that built the unit. Reviews run under the merged loop bound —
three rounds, findings deduped by declared defect class, and escalation on recurrence or an
explicitly declared blocking finding.

**One rule carried forward, because it accounted for more damage than any other cause:** if a check
passes because something stood in for the component under test, it is evidence about the stand-in.
Anything invoked as a command needs at least one test that runs it as a real process. A repair that
nothing calls is indistinguishable from a repair never written.
