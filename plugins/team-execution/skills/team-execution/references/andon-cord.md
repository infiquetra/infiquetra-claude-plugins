# Andon-cord — the worker-raised stop-the-line halt

This file defines the **andon-cord** signal lane referenced by the Step B1 rule in `SKILL.md`.
Read it when a worker or reviewer needs to stop a running team before the next wave dispatches.

The andon-cord is the bottom-up counterpart to the operator-raised quiesce and the plan-declared
pause point: **any worker or reviewer inside a team-execution wave can stop the line**. It is one of
the three writers into the shared mid-run *adjustment envelope* (`quiesce` = operator,
`pause_after` = plan, `andon_halt` = worker/reviewer). See
`plugins/saga/references/adjustment-envelope.md` for the full schema.

## The one channel — the shared envelope, not a side channel

An andon raised by a worker reaches the coordinator through the **same** adjustment-envelope file
every other mid-run directive uses — never a separate ad hoc channel:

```
.saga/adjustment-envelope.json
```

Raise it with the writer helper (or the CLI), which appends an `andon_halt` directive to that one
file:

```python
import adjustment_envelope
adjustment_envelope.raise_andon(
    adjustment_envelope.default_envelope_path(repo_root),
    writer="reviewer",            # "worker" or "reviewer"
    scope="segment-3",            # what this halt is about (optional)
    reason="tests look fabricated; do not proceed to the next wave",
)
```

```bash
python3 plugins/saga/scripts/adjustment_envelope.py andon --writer reviewer \
    --scope segment-3 --reason "tests look fabricated"
```

## Step B1 rule — block the next wave

When the coordinator polls the envelope at a wave/tick boundary and finds a raised `andon_halt`:

1. **The next wave/tick is not dispatched.** Poll precedence is `halt > drain > pause > proceed`, so
   an andon HALTs — it never degrades to a lower rung. This extends the existing HALT-not-degrade
   posture (`docs/engineering-journal/DECISIONS.md`, `{#outcome-backend-degrade-stance}`); it does
   **not** add a second, competing halt vocabulary.
2. **An operator-surface HALT record is written** — the surfaced decision names the directive, the
   writer (`worker`/`reviewer`), and the scope, so the operator sees who stopped the line and why.
3. **In-flight work drains**; the coordinator dispatches nothing new until the operator resolves the
   andon (clears it, or converts it to a quiesce/pause).

## Orthogonal to the iteration caps — both survive

The andon-cord is an **additional, orthogonal** halt path. It does **not** replace, weaken, or
bypass the existing per-loop iteration caps:

- the 3-cycle **best-available-proceed** cap in `consensus-protocol.md`
  ("Maximum iterations: **3**. After 3 cycles, proceed with the best available version…"), and
- the **maximum of 3 remediation loops** in `validator-execution-order.md`.

An andon halt (a worker says "stop, something is wrong") and an iteration-cap "proceed with best
available" (the review loop exhausted its budget) are **distinct, coexisting outcomes**. Hitting the
3-cycle cap is not an andon; raising an andon does not consume or reset an iteration counter. A team
can hit its cap and proceed while no andon is raised, and can be andon-halted at iteration 1 well
before any cap is near. The caps stay exactly as written; this lane only adds the stop-the-line
signal they never had.
