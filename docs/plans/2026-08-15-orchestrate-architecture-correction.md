# Orchestrate: architecture correction

**Date:** 2026-08-15
**Status:** agreed with the operator, not yet implemented
**Supersedes:** the module boundaries in `docs/plans/2026-08-12-orchestrate-plugin-plan.md`.
The plan's problem frame, its evidence ledger, and its unit decomposition still stand. What
changes is where durable state lives and which process owns which fact.

---

## Why this document exists

The composition unit — the one that assembles the other modules into a working run — went through
five repair rounds. Each round closed the defects that were named and the next review found new
ones of the same kind. After the fifth round a three-vendor panel returned seven merge-blocking
defects, and three reviewers independently filed the same low-ranked observation as the
explanation: the guarantees are single-decision **by convention**, not by construction.

Mapping all seven defects against the code produced the finding this document records:

> **Not one of them is a logic error.** No bad arithmetic, no wrong data structure, no off-by-one.
> Every one sits on the boundary where our durable record of the world meets the world.

That is a design property, not a run of bad luck, and it is fixable by moving a boundary rather
than by a sixth repair round.

---

## The defect, stated once

The run's durable table stores three different kinds of fact in identical columns:

```
  A ROW
  ┌──────────────┬───────────────┬──────────────┬──────────────────┐
  │ role         │ tokens_max    │ observed_    │ observed_state_  │
  │ "mirror"     │ 50000         │ state        │ source           │
  │              │               │ "exited"     │ "inferred:..."   │
  └──────────────┴───────────────┴──────────────┴──────────────────┘
         │               │              │                 │
    ┌────┴────┐    ┌─────┴─────┐   ┌────┴─────┐      ┌────┴──────┐
    │ AUTHORED│    │ AUTHORED  │   │ WHICH?   │      │ the answer│
    │ true by │    │ true by   │   │ observed │      │ ...that   │
    │ constr. │    │ constr.   │   │ or       │      │ nobody    │
    │         │    │           │   │ inferred?│      │ reads     │
    └─────────┘    └───────────┘   └──────────┘      └───────────┘

    AUTHORED  "I decided this"   → true forever
    OBSERVED  "I saw this at T"  → true at T, decays afterward
    INFERRED  "I concluded this" → never independently true
```

A consumer reading `observed_state == "exited"` cannot tell which kind it holds, so every consumer
treats all three as authored.

**Three places prove this is a missing type rather than three mistakes.** In each, the producer
explicitly recorded its own uncertainty and the consuming side had nowhere to put it:

1. The subscriber stamps a provenance column with an `inferred:` prefix — deliberately saying *I
   did not witness this*. The retirement gate reads the state column alone and never looks at the
   provenance column.
2. The spend module documents its row-exclusion parameter as *"Excluding is not charging zero: a
   row's true spend may be nonzero and genuinely unknown."* The ceiling gate subtracts the row from
   the sum, which against a ceiling **is** charging zero.
3. A scan result type was introduced specifically to carry *did the search finish* — and the
   scanner sets that flag true for a query that ran and failed, because it inspects only whether
   the query process raised, never its exit status.

Same shape, three modules, three authors. The information needed to fail closed was present and
correctly labelled each time. The consumers had no slot for it.

### The recurring class, and why enumeration lost

The journal entry `{#absence-must-be-proved-not-inferred}` records the general form: *"no record of
X" is not "X does not exist" — it is "not yet known."* By the fifth repair round it had appeared
nine times.

The reason it kept recurring is worth stating plainly, because the build diagnosed it after round
two and then did not act on the diagnosis: **a property with more entrances than anyone has
enumerated cannot be secured by enumerating entrances.** Rounds three, four and five each closed
the entrances that had been named; each was followed by a review finding new ones.

The eighth instance is the clearest demonstration — it survived *inside the fix for the seventh*.
A shutdown path was corrected to stop inferring "the tab closed" from "the close call returned,"
and the corrected re-ask was still gated on the row naming a tab. Two inferences meet at that gate:

- *Did the request take effect?* — fixed.
- *Is there anything to request?* — still answered by a missing field.

**Generalizable rule: two inferences meet at most gates. Fixing one does not fix its sibling.**

Where this codebase already enforces a property structurally — one construction site, pinned by a
test that walks the module's own syntax tree — the class has not recurred once. Where it is left to
careful authorship, it recurred in every round.

---

## Where the boundary moves

The durable table holds two categories of column, and only one of them is ours. The mirror module
already names the other category in its own source: `substrate`.

```
   A ROW
   ┌───────────────────────────────┬──────────────────────────────┐
   │  INTENT + OUTCOME             │  SUBSTRATE                   │
   │  ours — nothing else has it   │  the terminal multiplexer's — │
   │                               │  we copied it                │
   ├───────────────────────────────┼──────────────────────────────┤
   │  role, task, scope            │  pane id, tab id, cwd        │
   │  tokens_max, reservation      │  pid, observed_state, vendor │
   │  coordinator_disposition      │                              │
   │  base_commit, destination     │  ◄── EVERY merge-blocking    │
   │  verdict, settlement          │      defect lives here       │
   └───────────────────────────────┴──────────────────────────────┘
              KEEP                    STOP STORING — ASK AT READ TIME
```

**The rule: do not keep a durable record of a fact whose owner is already durable and queryable.**

The multiplexer knows which tabs and panes exist, what label each carries, and whether an agent in
one is idle, working or blocked. It survives our process. Copying those facts into our table
creates a second register, and a second register can disagree with the first. Every merge-blocking
defect in the composition unit is an instance of that disagreement.

What the multiplexer does **not** know, and what therefore must stay in our table: what a session
was *asked* to do, what scope it was allowed, what tier it should run at, what it cost, what came
back, and whether that return was accepted. Those are the intent and outcome columns.

---

## The three session roles

This is the part most easily lost, and it is load-bearing.

```
   ┌──────────────────────────────────────────────────────────────┐
   │  ORCHESTRATOR  (the operator's channel)                      │
   │  routes · decides · records · answers the operator           │
   │  performs NO substantive work in this channel                │
   └───────┬───────────────────────────────────┬──────────────────┘
           │                                   │
           │ "read these three reviews and     │ "build the repair"
           │  tell me where they disagree"     │
           ▼                                   ▼
   ┌───────────────────────┐          ┌──────────────────────────┐
   │  MIRROR               │          │  CHILDREN                │
   │  the ORCHESTRATOR's   │          │  the OUTCOME's own work  │
   │  own work             │          │                          │
   │  · synthesis          │          │  · build                 │
   │  · comparison         │          │  · review                │
   │  · bulk reading       │          │  · repair                │
   │                       │          │                          │
   │  persistent, paired   │          │  disposable, per-unit    │
   │  NEVER renders a      │          │  worktree-isolated       │
   │    verdict            │          │                          │
   │  NEVER writes the repo│          │                          │
   └───────┬───────────────┘          └──────────────────────────┘
           │
           │  returns a DISTILLED result under a declared byte bound
           │  over the bound → REJECTED, never truncated
           ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  the orchestrator's context stays small                      │
   └──────────────────────────────────────────────────────────────┘
```

**The mirror is context protection, not a resume mechanism.** It exists so the session that makes
decisions is not also the session that reads 25 KB of review material, source files and probe
output. This was misread once during the redesign discussion as redundant infrastructure; it is
not.

The evidence that it earns its place came from this campaign. A builder session compacted twice.
Its second compaction summary asserted that the codebase lacked a particular identity primitive —
an hour after that same session had written it. Every later turn reported from the summary rather
than the tree, and the resulting claim was a confident false negative. Context exhaustion does not
present as an error; it presents as a well-argued wrong answer.

The byte bound deserves its own note. A return larger than its declared bound is **rejected**, not
truncated, and the declaration itself is capped — because the way a byte bound erodes is not that
someone deletes it, it is that someone raises it. During this campaign, truncated command output
read as complete output produced four separate wrong conclusions, including one where a pipeline
killed a `git apply` mid-run and the truncated output reported success.

---

## What each module is for

Keep. Each addresses a category the plan ranked by `cost x silence`, and none of the
merge-blocking defects is in any of them.

| module | what it owns | why it cannot be policy |
|---|---|---|
| completion | the only place a child reaches `verified` | a false pass is indistinguishable from a true one downstream |
| mirror | the orchestrator's own bulk work, distilled and bounded | a summary that silently drops the fact that refutes it |
| admission | work-in-progress bounds, reservations, queue | must **refuse** the launch that exceeds the bound |
| subscriber | holds the event subscription, pushes a wake | "remembering" to watch is exactly what fails |
| planning | routes each child to a tier and vendor | wrong tier presents as success |
| accounting | spend ceiling from observed actuals | must **refuse** over budget |
| event client | newline-delimited JSON over the event socket | — |

### Why the completion module is as large as it is

It is one idea carried through: **you cannot verify a claim by inspecting its result afterward, so
the orchestrator must perform the step itself.**

```
   THE NAIVE SHAPE                    WHAT THE COMPLETION GATE DOES
   ───────────────                    ─────────────────────────────
   child writes its report            BEFORE dispatch:
   orchestrator reads it                issue a receipt — the expected
   "looks done"                         evidence identity, signed with a
                                        per-run secret the child cannot reach
        │
        ▼                              child writes ONLY to an in-flight
   ┌──────────────────┐                  sibling of the destination
   │ a false PASS is  │
   │ indistinguishable│                orchestrator performs the rename
   │ from a true one  │                  itself; the destination must be
   │ downstream       │                  byte-for-byte its pre-dispatch state
   └──────────────────┘
                                       the check runs from a path the child
                                         CANNOT WRITE

                                       a judgment-shaped child must supply an
                                         attributable independent read
```

Its own reason, from the module: a file on disk does not record whether it arrived by rename or by
direct write — neither `stat` nor content carries it — so a check that reads the finished artifact
can never establish it.

This matters because agent reports are claims. During this campaign a repair report asserted *"there
is one place that writes `exited`, and it is now behind the re-ask."* It was false, and it was
caught only because a human-directed read of the source contradicted it.

---

## The subscriber becomes a managed pane

The subscriber is launched today as a bare subprocess and tracked by process id. Three of the seven
merge-blocking defects exist only because of that choice: a process-table query that fails is read
as "no subscriber exists"; identity is a substring match that takes the first hit; and a stale
record naming a reused process id causes a signal to be sent to an unrelated process. The last was
reproduced — an unrelated process the orchestrator never started was terminated.

The correction relies on a distinction that is easy to miss:

```
   MANAGED PANE                        AGENT SESSION
   ────────────                        ─────────────
   a managed terminal                  a pane + a recognized coding agent
   runs ANY process                    a vendor CLI
   owner knows: alive? exited?         owner knows: idle/working/blocked
   costs: nothing                      costs: tokens
        ▲
        └── the subscriber should be THIS.
            Same script, same arguments, zero tokens.
            It simply stops being invisible.
```

There is no bootstrap cycle, because the subscriber does not need to be subscribed to. It
**pushes**: on each handled event it issues an `agent.prompt` request targeting the orchestrator's
pane — the same mechanism an operator uses to prompt any session. The sequence is unchanged:

```
  TODAY                                  PROPOSED
  ─────                                  ────────
  orchestrator                           orchestrator
    │                                      │
    ├─ spawn subprocess → pid              ├─ split a pane (no focus)
    │                                      ├─ run the same argv in that pane
    ▼                                      ▼
  subscriber                             subscriber        ← SAME SCRIPT
    │  connects, subscribes                 │  connects, subscribes
    │  ◄── event: a child settled           │  ◄── event: a child settled
    ├─ prompt → orchestrator pane           ├─ prompt → orchestrator pane
    ▼                                       ▼
  orchestrator wakes                     orchestrator wakes    ← IDENTICAL
```

One line differs, at startup. `"Is this run's subscriber alive?"` stops being a substring search of
the process table and becomes a pane lookup against the component that owns the answer.

### The deadman, named rather than papered over

```
   orchestrator idle, waiting to be woken
        │
        │   subscriber dies
        │        └─► nothing pushes. Ever.
        ▼
   orchestrator sleeps forever
```

The waker cannot report its own death, and this is true of both the current and the proposed
design. The agreed answer is the cheap one: **whenever the orchestrator wakes for any reason, it
checks the subscriber's pane before trusting silence.** No timer, no second watcher. It is the same
principle as everything else here — silence is not evidence; ask the owner — and it becomes a
reliable question only once the pane is managed.

---

## Resume with a different vendor

Confirmed by the operator as a real requirement, and the concrete case is mundane: a usage limit is
reached mid-campaign and the work continues in another vendor's session.

```
  the orchestrator's session ends, three children in flight
   │
   ▼
  a different vendor opens:  resume <run-id>
   │
   ├─► read OUR TABLE   ──► intent + outcome + approvals + ceiling
   │                        "repair round N, scope, ceiling 50k remaining,
   │                         two children verified, one open"
   │
   └─► ask the MULTIPLEXER ─► liveness
                             "this tab is alive and idle; that one is gone"
   ▼
  continue. No re-briefing, no re-approval, no guessing what is still running.
```

**This is the reason a prose handoff file is not sufficient — and not the reason one might expect.**
Markdown carries intent perfectly well; the campaign this document came from was run entirely from
markdown briefs. What markdown cannot do is **refuse**. On resume the new session must be told it is
already at its concurrency bound and cannot launch another child, and that the ceiling has a
specific amount left. Prose states that. Only machinery enforces it.

---

## Policy or machinery

The operator's framing: policy costs tokens every session forever and can be ignored; machinery
costs tokens once. Both are true. The caveat is that unnecessary machinery is worse than free,
because it is a liability surface — this unit produced seven merge-blocking defects.

The discriminator is not importance. It is **whether the violation is visible**:

```
   LOUD failure                        QUIET failure
   (the operator objects within        (presents as success)
    a round)
   ┌────────────────────────┐          ┌────────────────────────┐
   │ five repair rounds were│          │ nobody checked that the │
   │ run when the envelope  │          │ session label was       │
   │ allowed three          │          │ injective               │
   │                        │          │                         │
   │ noticed immediately    │          │ noticed only when it    │
   │                        │          │ closed another run's tab│
   │      → POLICY IS FINE  │          │   → NEEDS MACHINERY     │
   └────────────────────────┘          └────────────────────────┘
```

This is the plan's own `cost x silence` ranking applied to the plugin itself. The `lifecycle`
category led on raw count and ranked lowest on severity precisely because the operator objects out
loud every time. **Six of the seven merge-blocking defects are in that category** — the composition
unit spent five repair rounds defending the quadrant its own design document deprioritized.

---

## What is settled

1. The durable table keeps intent and outcome. It stops persisting substrate columns; those are
   asked of the multiplexer at read time.
2. The mirror stays, in its correct role: the orchestrator's paired worker for synthesis,
   comparison and bulk reading, with a hard byte bound on returns and no authority to render a
   verdict or write the repository.
3. The completion gate stays. It is the highest-value module by the plan's own ranking.
4. The subscriber becomes a managed pane running the same script, not a bare subprocess.
5. A deadman check on the subscriber's pane runs whenever the orchestrator wakes.
6. Session creation and driving are delegated to the existing wrapper and multiplexer. The
   lifecycle module thins to what is genuinely ours: tier, scope, label and landing.
7. The composition module shrinks to whatever remains once there is no shadow to reconcile.
8. Two defects survive the boundary move and need real fixes on their merits: the session label
   must be injective over its two identifiers, and the spend ceiling must distinguish *unknown*
   from *zero*.

## What is not yet settled

- How much of the composition module survives, and whether the remainder is one module or several.
- Whether the guarantees that remain should be pinned structurally — one construction site per
  guarantee, asserted by a syntax-tree test — as the predicate scanner already is. The evidence
  from five repair rounds argues yes.
- Whether the halted composition branch is repaired in place or rebuilt against the corrected
  boundary. Rebuilding is likely cheaper than a sixth repair round, but that has not been costed.

---

# Part II — Review machinery

Agreed with the operator in the same session, after the boundary correction above. This part
answers a different question: not *where does durable state live*, but *how does a review loop
terminate*.

## Two failures, opposite shapes, one missing mechanism

Two orchestration campaigns failed on reviews. They failed differently, and the difference is the
design input.

```
  A REQUIREMENTS REVIEW                      A CODE REVIEW
  ─────────────────────                      ─────────────
  "review of the requirements"  84x          rounds counted correctly 1 -> 5
  "review the spec/plan"        10x          budget extended twice by the operator
  "review code/diff"            10x          halted at seven merge-blocking defects

  full/whole-document re-read  162x          every round read the DELTA
  delta-only scoping            10x          (each brief scoped to a commit range)

  "another review"             440x
  competing counters running at once:
    round 0..7, cycle 1..2, iteration 1..3

  UNBOUNDED IN BREADTH                       UNBOUNDED IN DEPTH
  every review re-opened the whole           every repair created the next round's
  document, and a requirements               review surface
  document has unbounded
  improvable surface
```

The breadth failure needed **scope**. The depth failure needed a **cap**. Neither had either.

### Why "review until the reviewers find nothing" is not a stopping rule

It terminates only when reviewers run out of findings, and they never do, because the artifact
changes under them every round. This campaign demonstrated it in the sharpest available form: **the
eighth instance of the recurring defect class was inside the fix for the seventh.** A repair that
stopped inferring "the session closed" from "the close call returned" left its sibling inference —
*is there anything to close?* — reading a missing field. The fix was the finding.

A stopping rule conditioned on reviewer silence is a race between reviewer creativity and the
budget, and the reviewers win by construction.

### The finding a code review could not express

Three reviewers, three vendors, no shared context, independently filed the same structural
diagnosis — that the unit's guarantees are enforced by convention rather than by construction. **All
three ranked it P3**, the lowest rank, and correctly so: in a merge-gate rubric, "this is enforced
by convention" is not a blocker.

So the loop had exactly one available action — repair — for a finding that needed a different one.
Its outputs were *merge* or *halt-and-repair*. What it needed was **halt-and-escalate**: send this
back up a layer.

## The layers, and where `/orchestrate` sits

`/orchestrate` is not a layer inside the lifecycle. It is a wrapper around it, entering at a depth
its input decides:

```
   INPUT                    UPFRONT WORK              WHAT /orchestrate THEN RUNS
   -----                    ------------              ---------------------------
   a prompt          ->  interview the operator   ->  brainstorm-plan-work-review-qa-ship
                         heavily                      (full depth, many lifecycles)

   a requirements    ->  break into groups        ->  plan each group, then each group's
   document                                            full lifecycle

   an issue set      ->  group them               ->  plan each group, then each group's
   (parent + subs)                                     full lifecycle

   a plan document   ->  almost nothing           ->  work-review-qa-ship
                                                       (thin, one lifecycle)
                              |
                              +-------------->  THE ORCHESTRATION PLAN
                                                <- automated rigor pass
                                                <- then the operator's final say
```

**What the operator approves changes with the input.** Fed a plan, the orchestration plan is a work
split and a set of routes — a tactical approval. Fed a bare prompt, it includes the *lifecycle shape
itself*, so the operator is approving how deep the machinery is about to go. That is a much larger
and less reversible commitment, and it is least checkable against anything — which is exactly why an
automated rigor pass runs before it reaches the operator.

Because `/orchestrate` owns the whole lifecycle, an escalation from a code review back to planning
is **internal to one run**, not a handoff out of the tool.

```
  +- requirements ------------------------------------------+
  |                                                          |
  +----^-----------------------------------------------------+
       | escalate: "the requirements are wrong"
  +----+-----------------------------------------------------+
  |  plan  --> DOC-REVIEW          <- the breadth failure     |
  |            is it ready to drive implementation?           |
  +----^-----------------------------------------------------+
       | escalate: "the design is wrong"    <- the depth failure
  +----+-----------------------------------------------------+
  |  ORCHESTRATION-PLAN REVIEW                                |
  |  the split, the routes, the agents, the lifecycle depth   |
  +----^-----------------------------------------------------+
       | escalate: "the split is wrong"
  +----+-----------------------------------------------------+
  |  work  --> CODE-REVIEW                                    |
  |            lenses, per-lens scoring                       |
  +----^-----------------------------------------------------+
       | escalate: "the implementation cannot satisfy this"
  +----+-----------------------------------------------------+
  |  qa                                                       |
  +----------------------------------------------------------+
```

## The protocol splits in two

These are separable, and they have different scopes.

```
   THE LOOP BOUND                        THE CONSENSUS PANEL
   --------------                        -------------------
   max 3 iterations, per unit            multiple reviewers / lenses
   delta-scoped re-review                per-lens scoring
   dedup by CLASS, not location          quorum rule
   three verdicts                        vendor-exclusion roster
   escalation budget of one

   NEEDED BY: every layer                NEEDED BY: code-review, qa
                                         OPTIONAL:  doc-review
                                         NOT USED:  orchestration plan
                                                    (one voter: the operator)
```

The loop bound is universal because the one documented case of an unbounded loop was a
*requirements* review, not a code review. The panel is not universal because "is this plan ready to
drive implementation" is a threshold question with one right answer — a gate — while code quality
and security are continuums that genuinely benefit from independent lenses.

### Three verdicts, not two

| verdict | meaning | next |
|---|---|---|
| `pass` | above threshold, no blocking dimension | proceed |
| `halt-and-repair` | fixable within this layer | next iteration, delta-scoped |
| `halt-and-escalate` | the problem is upstream | hand to the layer above |

**`halt-and-escalate` fires mechanically, not by reviewer judgment: the same defect class recurring
in a third round, regardless of rank.** Reviewer judgment is what produced three independent P3s on
the finding that mattered.

### Dedup by class, not by location

```
  KEYED BY LOCATION                    KEYED BY CLASS
  -----------------                    --------------
  round 2: module A, line 174          round 2: absence-inferred  (1st)
  round 3: module B, line 922          round 3: absence-inferred  (2nd, 3rd)
  round 4: module B, line 3348         round 4: absence-inferred  (4th)
  round 5: module C, line 208          round 5: absence-inferred  (5th..9th)

  every finding looks NOVEL            SAME CLASS, THIRD ROUND
  -> "keep repairing"                  -> the design is wrong; escalate
```

Nine instances of one class across five rounds. Keyed on file and line, every finding was new. Keyed
on class, the signal was unmistakable by round three — and the conclusion this document records was
available then.

### The escalation budget, fixed at one

Bounding the inner loop moves the problem outward unless the outer loop is bounded too: a unit that
escalates, gets replanned, and escalates again is a second unbounded loop, and a more expensive one
because each turn discards a plan and its work.

**One escalation per unit.** A unit that would escalate twice is not a planning problem; it is a
"this unit should not exist in this shape" problem, and that is an operator decision. The budget is
fixed rather than configurable, for the same reason the mirror's byte bound is capped: a bound does
not erode by being deleted, it erodes by being raised. Raising it requires saying so in the prompt
or the plan — deliberate friction, not impossibility.

### The instrument belongs to the dimension, not the protocol

- **Threshold questions take a gate.** "Is this plan ready to drive implementation?" "Is evidence
  integrity intact?" A blocking finding blocks; a score of 8.7 means nothing.
- **Continuum questions take a score.** "How is the security posture?" "How clear is this code?"
  There is no blocker, there is a level, and the trend across rounds is the signal of convergence.

A uniform numeric gate is also nudgeable in both directions: a reviewer who wants to halt scores
just under the line, and a panel under time pressure inflates to end the loop. Where a rank binds
the decision, the score is free to be an honest measurement.

## The second-opinion transport, and an "external only" mode

`/code-review` and `/doc-review` already carry the whole operator-facing mechanism: the offer with
its durable gate-record contract, the prompt-and-remember path, provider selection, egress policy,
tier selection, and atomic persistence of the request state. **Only the transport changes** — the
external reviewer is engaged as a managed agent session rather than as a subagent.

The gain is not consistency. A managed session is **visible** — its pane can be watched, read and
interrupted — and it **outlives its caller**, where a subagent dies with the parent and reports only
what it chose to summarise. This campaign's central failure was a summary that dropped the fact
which refuted it.

Both skills also gain the loop bound. `/code-review` gains the consensus panel; for `/doc-review`
the panel is optional.

**A new offer mode: external only.** Today the offer is additive — the home vendor's panel plus an
external advisory seat. External-only excludes the home vendor's panel entirely.

```
   ADDITIVE (today)          EXTERNAL ONLY (new)
   ----------------          -------------------
   home panel                home panel: EXCLUDED
        +                    external vendors: the whole panel
   external advisory
        |                         |
        +- the home vendor        +- this is "never review your own vendor"
           reviews its own           applied at the skill level rather than
           work                      the campaign level
```

When `/code-review` runs inside a session over code that session's vendor wrote, external-only is
not a cost option, it is the correctness option — and it means the rule is implemented once rather
than twice.

**Quorum failure under external-only halts and tells the operator.** During this campaign an
external reviewer was terminated by its provider's content filter three separate times. Falling back
to the vendor that was deliberately excluded would silently convert a correctness choice into a cost
choice, and the operator would never learn it happened.

## Part II — what is settled

1. Every review layer gets the loop bound: three iterations per unit, delta-scoped re-review, dedup
   by class, three verdicts, one escalation per unit.
2. `halt-and-escalate` fires mechanically on a class recurring in a third round, not on reviewer
   judgment.
3. The consensus panel applies to code review and qa; it is optional for doc review; the
   orchestration-plan review has a single voter, the operator.
4. The orchestration-plan rigor pass applies evidence-backed safe fixes in place and reports the
   remainder with recommendations, reusing `/doc-review`'s existing contract rather than a parallel
   one.
5. Gate or score is chosen per dimension. Where both exist, the rank binds and the score measures.
6. `/code-review` and `/doc-review` engage external reviewers through managed agent sessions,
   replacing the subagent transport. The operator-facing offer is unchanged.
7. An external-only offer mode exists. Losing quorum under it halts rather than falling back.

## Part II — what is not yet settled

- The lens roster for code review, and whether lenses are named personas or model/effort
  combinations. The operator has called this secondary.
- Whether qa's panel is the same roster as code review's or a different one.
- How the orchestration-plan rigor pass expresses "this unit has no acceptance test" — a gate
  dimension, or a hard refusal to launch.

---

## The operator's goal, in one line

Do what has been done manually across these sessions — dispatch, wait, collect, adjudicate, merge —
**without restating the envelope every session and without devising the orchestration by hand each
time.**

Every decision above is answerable to that sentence. Anything that does not serve it is out.
