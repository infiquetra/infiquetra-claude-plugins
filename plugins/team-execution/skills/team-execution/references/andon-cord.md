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

## Orthogonal to review termination and validator remediation

The andon-cord is an **additional, orthogonal** halt path. It does **not** replace, weaken, or
bypass either independently owned terminal policy:

- Code Review's review-transition termination in
  `plugins/saga/scripts/review_consensus.py`, or
- the **maximum of 3 remediation loops** in `validator-execution-order.md`.

An andon halt (a worker says "stop, something is wrong") and a transition-engine terminal result
are **distinct, coexisting outcomes**. Review termination is not an andon; raising an andon does not
consume or reset review state or a validator remediation counter. This lane adds only the
stop-the-line signal and does not reinterpret either policy.
