# Phase 1 acceptance — one real run, and what makes it a pass

Phase 1 is not "the tests are green". Seven module suites can be green while no orchestrator
exists, and that is the specific failure the composition unit was built to prevent. Phase 1 is a
**named end-to-end scenario, run once against real vendors, that leaves an evidence receipt**.
A failure here blocks Phase 2.

The machinery is in `skills/orchestrate/scripts/runner.py`. The gate itself is run by the
operator, because it starts real sessions and spends real tokens.

## The scenario

One **real, unrelated task** — not a task about this plugin, because a run that orchestrates work
on its own orchestrator cannot distinguish the plugin's failures from the task's.

The plan must contain:

| requirement | why it is in the scenario |
|---|---|
| at least **two children on different vendors** | routing across vendors is the reason the plugin exists; one vendor exercises none of the substitution, argument-adaptation, or per-vendor bound behaviour |
| at least one **mutating** child | integration verification, worktree isolation and the landing boundary are unreachable with read-only work |
| at least one **read-only** child | the shared-checkout attribution path and `integration_mode: none` are unreachable with mutating work |
| one deliberate **mid-run orchestrator restart** | the restart path is the one that duplicates a child, strands work, or loses the changed-paths snapshot, and none of those appear until it happens |

The restart is performed while at least one child is dispatched and unfinished. Stop the
orchestrator session and start a new one. **Construct a new `Coordinator` with the same `run_id`,
the same repository root, and the same workspace** — a different `run_id` is a different run and
will not find any of this one's state — then, before anything else, in this order:

```python
coordinator.reconcile_startup()   # names every occupant, asks resume-or-abandon per row
coordinator.catch_up()            # one snapshot pass over every registered pane
coordinator.ensure_subscriber()   # adopts the running subscriber; does not start a second
```

`ensure_subscriber()` finding a live subscriber and adopting it is the expected outcome, not a
failure. It returns `False` and logs `subscriber_adopted`.

**Two things the plan cannot contain**, and both are refused when the plan is built rather than
after a child has been paid for:

- `integration_mode: "path"`. The landing provisioner produces a branch worktree for any mutating
  child and the ambient checkout for a read-only one; there is no producer for a declared
  destination path. Use `branch` or `none`.
- judgment-shaped work (`judgment`, `second-opinion`, `divergence`). It requires an independently
  dispatched verifier, and this control flow does not yet dispatch one.

**Criterion 4 has to be produced deliberately, through the API.** While a mirror request is
outstanding, deliver an operator question with **`Coordinator.handle_operator_message`**:

```python
coordinator.ask_mirror(mirror.MirrorRequest(
    request_id="gate-1", kind="synthesis", instruction="Compare the two child reports."))
coordinator.handle_operator_message(
    "What is the run doing?", answer=lambda context: f"...mirror busy: {context.mirror_busy}")
```

There is no slash command yet, so a question typed at the session running the coordinator is not
an `operator-log.jsonl` line and will not satisfy criterion 4. This is the only step of the
scenario that cannot happen as a side effect of the run.

## Pass criteria

All five, computed from the durable record by `Coordinator.acceptance_receipt()`. None of them is
a summary of what the orchestrator believes it did.

1. **No child lost.** Every child row is `reaped`, or carries a `coordinator_disposition` recording
   that this coordinator deliberately abandoned it and why. A child that is neither is unaccounted
   for, and "unaccounted for" is reported as a failure rather than as an incomplete run.
2. **No duplicate launched.** No row has more than one distinct launch identity in the run log. The
   restart is what makes this criterion mean something.
3. **No false completion.** Every reaped row still re-authorises: an authenticated dispatch receipt,
   a settlement sealed under that receipt's own attempt nonce, a recorded passing verdict, an
   artifact still carrying this dispatch's binding token, and a recorded integration result. The
   receipt re-runs that check at the end rather than trusting the reap that already happened.
4. **The operator was answered while the mirror was busy.** At least one operator question is
   recorded as `answered` with `mirror_request_outstanding: true`. A run where the operator never
   asked anything while the mirror was working has not exercised this and does not pass.
5. **A spend figure was recorded.** `accounting.run_actual_tokens` returns a number for the run.
   Note that this fails closed rather than guessing: a launched child under a metered vendor that
   never printed a usage line makes the run's spend unknowable, and unknowable is not a pass.

## Evidence

Everything lands under `.orchestrate/runs/<run-id>/` in the work location the run recorded:

| file | written by | what it is |
|---|---|---|
| `run-log.jsonl` | the coordinator, append-only, flushed per line | every plan, approval, activation, launch, dispatch, evaluation, reap, halt, orphan decision and retirement, in order |
| `operator-log.jsonl` | the coordinator, append-only, flushed per line | every operator question with its disposition, its answer or park reason, and whether the mirror was busy at the time |
| `acceptance-receipt.json` | `Coordinator.acceptance_receipt()` | the five criteria above with the detail behind each |
| `register-final.json` | `register.retire_run` | the run's complete final register, archived at retirement |

The two ledgers are append-only and flushed on every write because they have to survive the process
that was writing them. A ledger that is only complete when the coordinator exits cleanly cannot
describe a coordinator that did not, and describing that is the point of the restart.

## Running it

Set both host directories away from live state only if you are rehearsing. **A real gate run uses
the operator's real host state**, because a rehearsal against temporary directories proves the
scenario ran and not that the plugin works where it will live.

**Before anything below runs, obtain three real values.** None of them is invented for this
document; each is either a literal you choose or a fact this host can already answer.

1. **Your own pane id, for `orchestrator_pane`.** Run `herdr --session default api snapshot` (the
   exact call `session_lifecycle.HerdrControl.snapshot` makes) and read the `tab_id`/`pane_id` of
   the session you are typing this procedure into from its `tabs`/`panes` arrays. Pane ids look
   like `w1:p2`.
2. **A second, empty pane, for `subscriber_pane`.** Open a new tab in the same Herdr workspace —
   any means the operator normally uses to do that — and read its pane id the same way. The
   subscriber writes nothing an operator reads directly; this pane exists only so Herdr has
   somewhere to run the process.
3. **An approved spend ceiling, for `ceiling`.** A number in tokens, chosen by the operator: the
   sum of each planned child's `tokens_max` plus headroom for a retry. There is no default; a run
   with no ceiling refuses at `plan_run` (`SpendHaltError`).

**The operator channel is not shipped.** This module defines the two-method protocol
(`deliver(text) -> None`, `ask(prompt, options) -> str`); nothing in this repository implements it
against a real human yet. Below is a complete, minimal one for an operator sitting at the terminal
that runs the coordinator process — not a placeholder, a working implementation:

```python
class TerminalOperatorChannel:
    """Delivers text to stdout and takes a decision from stdin. Nothing more is required."""

    def deliver(self, text: str) -> None:
        print(text)

    def ask(self, prompt: str, options: list[str]) -> str:
        choices = "/".join(options)
        while True:
            answer = input(f"{prompt} [{choices}] ").strip()
            if answer in options:
                return answer
            print(f"not one of {options}")
```

```python
from pathlib import Path

import mirror
import runner
import session_lifecycle  # all three from skills/orchestrate/scripts, on sys.path

ORCHESTRATOR_PANE = "w1:p1"    # from step 1 above
SUBSCRIBER_PANE = "w1:p3"      # from step 2 above
CEILING = 200_000.0            # from step 3 above

coordinator = runner.Coordinator(
    Path.cwd(),
    run_id="phase-1",
    workspace="phase-1",
    orchestrator_pane=ORCHESTRATOR_PANE,
    subscriber_pane=SUBSCRIBER_PANE,
    wrapper=session_lifecycle.AgentWrapper(),
    herdr=session_lifecycle.HerdrControl(),
    git=session_lifecycle.GitLanding(),
    interaction=session_lifecycle.HerdrInteraction(),
    channel=TerminalOperatorChannel(),
    supervisor=runner.SubprocessSubscriberSupervisor(),
)

coordinator.start_run()

# A concrete plan: two vendors, one mutating child, one read-only child -- the four scenario
# requirements above in one shape. Replace the task text and scope with the real, unrelated task;
# leave the row_id/vendor/work_shape/artifact_path/predicate/integration_mode/tokens_max keys as
# named -- ``planning.plan`` reads exactly these.
request = runner.parse_outcome("issue #1234")   # any of the four OUTCOME_KINDS forms; see below
children = [
    {
        "row_id": "survey",
        "task": "Survey the affected module and write findings to the artifact path.",
        "work_shape": "mechanical",
        "vendor": "claude",
        "scope": ["src"],
        "artifact_path": "survey.json",
        "predicate": {"argv": ["python3", "checks/survey_check.py", "<artifact-relpath>"]},
        "integration_mode": "none",
        "tokens_max": 40000,
    },
    {
        "row_id": "fix",
        "task": "Apply the fix described in the survey and write the result to the artifact path.",
        "work_shape": "mechanical",
        "vendor": "codex",
        "scope": ["src"],
        "artifact_path": "fix.json",
        "predicate": {"argv": ["python3", "checks/fix_check.py", "<artifact-relpath>"]},
        "integration_mode": "branch",
        "tokens_max": 60000,
    },
]
plan = coordinator.plan_run(request, children, ceiling=CEILING)
coordinator.approve_plan(plan)     # delivers the text, then takes the decision
coordinator.commit()               # reserves; queues what does not fit
coordinator.reconcile_startup()    # names every occupant, asks per orphan
coordinator.create_mirror()
coordinator.ensure_subscriber()
coordinator.launch_ready_children()
```

`runner.parse_outcome` accepts one of the four forms in `runner.OUTCOME_KINDS`: an issue reference
(`"issue #1234"`), a parent-issue reference, a path to a document, or free prose describing the
outcome directly. Use whichever names the real, unrelated task.

**The wake loop.** There is no shipped scheduler; this is the whole of it, and it is meant to be
run from whatever already wakes this session (a cron tick, an operator prompt, a Herdr event
delivered to the pane this coordinator runs in — this module does not care which):

```python
def on_wake(coordinator: runner.Coordinator) -> None:
    supervision = coordinator.supervise()
    print(f"subscriber_alive={supervision.subscriber_alive} mirror={supervision.mirror_state}")
    for row_id, row in sorted(coordinator.child_rows().items()):
        if row.get("phase") == "ready" and row.get("completion_sentinel"):
            # A completion sentinel event for this row arrived; the caller's event source names
            # which row_id woke this call, and that is the row_id to pass here.
            result = coordinator.integrate_child(row_id)
            if result.verified:
                coordinator.reap_child(row_id)
    report = coordinator.launch_ready_children()
    if report.withheld:
        print(f"withheld this sweep: {report.withheld}")
```

Call `on_wake(coordinator)` again after every event; `launch_ready_children()` is what picks up
whatever admission promoted once a slot freed.

**Failure branches**, all decided the same way -- ownership, never a clock:

```python
coordinator.interrupted_dispatches()          # what is stuck, and who claimed it
coordinator.reconcile_startup()               # asks resume-or-abandon for each one
```

See *Two behaviours that look like faults and are not* below for what each shape of "stuck" means
and what "resume" actually does for it.

**Restart.** Perform the deliberate mid-run restart the scenario requires exactly as described
under *The scenario* above: same `run_id`, same root, same workspace, `reconcile_startup()` then
`catch_up()` then `ensure_subscriber()`, in that order, before touching anything else. Then resume
the wake loop.

When the run is finished, **in this order**:

```python
coordinator.stop_writers()          # stops the subscriber by its durable record, closes the mirror
receipt = coordinator.acceptance_receipt()   # computed and sealed while the evidence still exists
archive = coordinator.retire()      # archives the register; the receipt is already on disk

print(f"passed={receipt.passed}")
print(f"receipt: {coordinator.receipt_path}")
print(f"archive: {archive}")
```

The order matters and is not a style preference. Retirement archives and deletes the live register
and the run key, and every pass criterion is computed from them. Asked afterwards,
`acceptance_receipt()` refuses rather than reporting a pass over an empty register, and points at
the sealed file. `retire()` seals one itself if you skipped the middle step, so both orders produce
the same true answer — but read the receipt, not the exit code.

## Two behaviours that look like faults and are not

**Fan-out serialises behind the first metered child's usage line.** The spend gate fails closed for
a launched child under a metered vendor that has not yet printed usage, so a second child is
withheld with a reason containing `no usage` until the first one reports. That is the accounting
contract working, not a hung run. `launch_ready_children()` returns it in `withheld` and the run
log records a `spend_halt`. Call `launch_ready_children()` again after the next wake.

**A dispatch can be interrupted anywhere before the child was confirmed told its task.** The run
log shows `slot_activated` and then `child_launch_failed` or `launch_withheld`, and
`interrupted_dispatches()` offers the row at the next `reconcile_startup()` regardless of which of
three shapes it is in -- there is no case an operator has to recognise by hand:

```python
coordinator.interrupted_dispatches()          # what is in that state, and who claimed it
coordinator.reconcile_startup()               # asks resume-or-abandon for each one
coordinator.launch_ready_children()           # carries out whatever "resume" means for its shape
```

1. **No pane at all.** The wrapper errored, or the process died before the launcher returned an
   identity. Resuming re-enters the launcher, which recovers an existing session by its run-bound
   label rather than opening a second one -- or, finding none, launches fresh.
2. **A pane, and a sealed dispatch receipt, but the final artifact-protocol send never confirmed
   landing.** The child has a live session and was told its task, but this coordinator cannot
   prove it was told where to write. Resuming resends the same, nonce-bound instructions to the
   same pane -- safe whether or not the first attempt landed, because a child that already read
   them once reads the same thing again. No second native session is opened.
3. **A pane, but readiness itself never completed** (a trust prompt, a timeout, an
   effort-application failure). There is nothing sealed yet to resend safely.
   `launch_ready_children()` withholds this row with an `UnconfirmedDispatchError` naming exactly
   that; the only supported decision is `abandon`.

Abandoning frees the slot and, when the child demonstrably never got a session, records that it
observed zero tokens so the run's spend stays knowable; abandoning a row that did get a session
(shapes 2 and 3) instead removes it from the spend gate entirely, the same way a reaped row already
is, so one stuck child cannot hold every sibling's spend unknowable forever. Nothing here is
time-based: an interrupted dispatch waits for a decision indefinitely and is never reclaimed by a
timer.

## What a pass does and does not establish

It establishes that the assembled loop launches, supervises, verifies, integrates, reaps, promotes,
restarts and converses against real vendors on a real task.

It does not establish that a child cannot forge its own evidence. Claude and Muse expose no
workspace-write flag, so for runtimes whose sandbox does not deny the register directory, a child
that reads this run's key can seal payloads that authenticate. `references/predicates.md` states
that boundary in full; the composition unit closes every route that does not require the key, and
this gate does not test the one that does.

It also does not establish anything about a second host. The register is host-global and one run id
belongs to one checkout; a cross-host claim needs the Phase 2 round-trip, not this.
