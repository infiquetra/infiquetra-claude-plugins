# Doc review — orchestrate: the path to first use

**Target:** `docs/plans/2026-08-16-orchestrate-path-to-first-use.md`
**Reviewed revision:** working tree, against `main` at `dafb742f`
**Blocked:** no — all findings resolved by the operator's decision to rescope
**Review artifact:** this file

## Verdict

**The plan's central decision is sound but its unit ordering repeated the exact mistake that halted
the previous attempt.** Repair-not-rebuild survives scrutiny, though the evidence proves less than
the document originally claimed. The blocking problem was that unit 1 repaired two defects in code
unit 2 deletes. The operator chose **rescope**, and all seven findings are now resolved in the plan.

## Findings

| # | Priority | Status | Finding |
|---|---|---|---|
| D1 | P1 | **fixed (rescope)** | Unit 1 repaired two defects that unit 2 removes entirely |
| D2 | P2 | **fixed** | "Imports clean" did not support the weight placed on it |
| D3 | P2 | **fixed** | Unit 2 had no acceptance criteria; unit 4 had no exit condition |
| D4 | P2 | **fixed** | The pre-mortem's mitigation had no baseline, so it could not fail |
| D5 | P2 | **fixed** | Nothing updated the skill description, which unit 3 makes false |
| D6 | P3 | **fixed** | Install mechanics were absent from a path-to-first-use plan |
| D7 | P3 | **fixed** | Module count was wrong (eleven → twelve) |

## How each was resolved

- **D1 (rescope, operator's choice).** The three defects are now split by owning unit: defects 1 and
  2 are marked *deleted by unit 2*, with unit 1 instructed to touch `find_orphan` only as far as its
  own tests demand. Defect 3, which survives every change, stays in unit 1. Unit 2's definition of
  done now names the deletion explicitly, so the scan cannot silently survive.
- **D2.** The evidence is relabelled a lower bound, and unit 1's *first task is measurement*: run the
  composition suite against merged `main` and record what fails. If that number is far larger, the
  repair-versus-rebuild decision reopens before any repair is written.
- **D3.** Unit 2 gained acceptance criteria (recovered by label, no process-table search anywhere,
  proven by a syntax-tree walk; deadman fires). Unit 4 gained a bound: three real runs, then it
  closes and anything open becomes its own plan.
- **D4.** The guard is now a committed constant pinned by a syntax-tree test, baselined on the first
  green run — the same shape this codebase already uses for its escalation budget.
- **D5.** Unit 3 explicitly owns the skill description and its in-body repetition.
- **D6.** Unit 3's acceptance now requires `/plugin marketplace update` plus a **new session** on a
  machine that has never run the plugin, because an acceptance run against a cached plugin proves
  nothing about installation.
- **D7.** Corrected in place.

---

### D1 — `P1` — Unit 1 repairs two defects that unit 2 deletes

The plan folds three defects into unit 1, then says unit 2 "retires defects 1 and 2 above at the
source." Both statements cannot be economical at once, and the repository shows unit 2 wins.

Defects 1 and 2 — the process-table scan that cannot distinguish a failed query from an empty one,
and the substring-based process identity — live in exactly one place, and it is the code that exists
only because the subscriber is a bare process:

```
find_orphan defined at    runner.py:949
its only real caller      runner.py:1792  self.supervisor.find_orphan(signature=self._subscriber_signature())
```

When the subscriber becomes a control-plane-managed pane, you ask the control plane by label. The
process-table scan is not repaired — it is deleted, along with both defects.

**This is the same error that halted the composition work.** That branch was closed because "six of
its seven blocking defects live in code the corrected boundary deletes." This plan re-commits it at
smaller scale.

**Repair:** either move unit 2 ahead of unit 1, or have unit 1 fix only defect 3 (the non-injective
run label, which survives the change) and explicitly defer 1 and 2 to unit 2 as deletions. The
second is likely cheaper, because unit 1 is already the largest unit. Whichever is chosen, the plan
must say which defects are *repaired* and which are *deleted* — they are different work.

### D2 — `P2` — "Imports clean" does not support the weight placed on it

The evidence table leads with the runner importing successfully against merged `main`. That proves
no module-level symbol is missing. It does not prove a single code path runs, because Python
executes almost nothing at import time.

The other two rows are stronger but still syntactic: "0 top-level register writes of removed columns"
and "30 row reads needing redirect" both come from pattern matching over source, so a write
constructed through a variable or a mapping built elsewhere would not appear.

The conclusion — repair is cheaper than rebuild — is still well supported. The claim that it is
"thirty read sites plus three defects" is not; that is a lower bound on the work, not a measurement
of it. **Repair:** state it as a lower bound, and make unit 1's first task an executed inventory
rather than a grep — run the existing composition tests against merged `main` and count what fails.

### D3 — `P2` — Unit 2 has no acceptance criteria; unit 4 has no exit condition

Units 1 and 3 each carry an *Acceptance* line. Unit 2 carries none, and it is the unit this review
argues should go first. Unit 4 is deliberately open-ended, which is defensible, but with no exit
condition it cannot be declared finished — and "first-use hardening" with no boundary is how a plan
acquires an indefinite tail.

**Repair:** give unit 2 an acceptance criterion (the subscriber survives an orchestrator restart and
is found by label, not by scanning; a deadman check fires when its pane is gone). Give unit 4 a
bounded exit: a fixed number of real runs, or a time box, after which remaining items become their
own plan.

### D4 — `P2` — The pre-mortem's mitigation cannot fail

The pre-mortem is real and the failure mode is plausible. Its mitigation — "a unit that counts
snapshot calls per orchestration tick and fails when the count grows" — has no baseline, so nothing
can fail it. Grows relative to what?

**Repair:** record the count on the first green run as the baseline and pin it, the way this
codebase already pins a budget constant with a syntax-tree test. A number in the repository can
regress; "does not grow" cannot.

### D5 — `P2` — Nothing updates the skill description, which will become false

The shipped skill's description ends with *"Planning never launches. No composed runner or slash
command yet."* That sentence is load-bearing for discovery — it is how the skill advertises itself —
and unit 3 makes it false. No unit owns changing it, and its body carries the same claim at line 22,
pointing at a superseded plan document.

**Repair:** add it to unit 3's scope. This is a shipped, user-visible string, not a comment.

### D6 — `P3` — Install mechanics are absent

The plan defines first use as "an operator installs the plugin … and starts a real run" but never
states how installation reaches the operator's session. A cached plugin stays stale until the
marketplace is updated *and* a new session starts; a plan whose acceptance is "the operator can
install it" should say so, or its acceptance test will pass against a stale cache.

### D7 — `P3` — fixed

"Eleven modules" corrected to "twelve" — `plugins/orchestrate/skills/orchestrate/scripts/` contains
twelve Python modules.

## What I checked that was sound

- The merge claims: `main` is at `dafb742f`; the marketplace carries `orchestrate` at `0.13.0` among
  thirteen plugins; the predecessor plan's units 1, 2, 6, 7 and 8 are merged and 3, 4 and 5 are not.
- There is genuinely no `commands/` directory, so "cannot be installed and used" is accurate rather
  than rhetorical.
- The seven apparent register writes really are false positives. `vendor` is authored intent the
  correction keeps by decision, the `pid` written belongs to the coordinator rather than a child
  session, and the single `tab_id` is nested inside an owned fence field.
- Unit 3's treatment of the existing surface branch as unreviewed material is correct: no check ever
  ran against it.

## What I did not check

- I did not run the composition test suite against merged `main`. That is the measurement D2 asks
  for, and it belongs to unit 1 rather than to this review.
- I did not evaluate whether the subscriber-as-managed-pane design is correct, only where its
  defects live.
- I did not review the predecessor plan documents, the closed branches' review reports beyond the
  three defects named, or the command surface branch's contents.
- No external-engine second opinion was dispatched; this is a single-reviewer pass.
