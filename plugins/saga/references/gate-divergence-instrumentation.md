# Gate-Divergence Instrumentation Convention

Any skill that fires an interactive `AskUserQuestion` gate offering a recommendation or a
pre-selected default can record a `gate_divergence` telemetry entry so `/retro` can report a
per-gate rubber-stamp rate (issue #399,
`docs/plans/2026-07-04-gate-divergence-telemetry-plan.md`). This rides the same `saga.py save`
call the skill already makes — it does not introduce a new write path, a new script, or a new
process boundary (KTD2).

## Steps

1. **Before** calling `AskUserQuestion`, capture an epoch-second timestamp:

   ```bash
   OFFERED_AT=$(date +%s)
   ```

2. Call `AskUserQuestion` as normal.

3. **After** the operator answers, capture a second timestamp and compute latency:

   ```bash
   ANSWERED_AT=$(date +%s)
   LATENCY=$((ANSWERED_AT - OFFERED_AT))
   ```

   If the gate could not be bracketed this way (e.g. resumed from a prior tick with no live
   offer/answer pair in this session), omit latency — encode `null`, never a fabricated `0`.

4. Compute the `divergence` bit yourself: `true` if the operator's answer differs from the
   offered default/recommendation, `false` if it matches. This is a simple string-equality
   check you already have both values for at the call site — it is not derived later by the
   reader (KTD3).

5. Encode the entry via `saga.py`'s `encode_gate_divergence_entry` (base64-wrapped JSON, KTD1 —
   safe against a `|` character appearing anywhere in `answer`):

   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'plugins/saga/scripts'); import saga
   print(saga.encode_gate_divergence_entry('<gate_id>', '<offered>', '<answer>', <true|false>, <latency|None>))
   "
   ```

6. Append the result to the **next** `saga.py save` call already made in this skill's flow:

   ```bash
   python3 plugins/saga/scripts/saga.py save \
     --kind <issue|task> --id <...> \
     --gate-divergence "<base64-string>" \
     ...
   ```

   Multiple gate interactions in the same tick each get their own `--gate-divergence` flag
   (repeatable, full-snapshot list semantics — pass every entry you want on this tick, not just
   the newest one, per the saga's full-snapshot contract).

## `gate_id` naming

One `gate_id` per **distinct decision point**, not per file — a single `SKILL.md` can fire more
than one gate (e.g. `founder-review/SKILL.md` fires both a mode-selection gate and a
per-expansion opt-in gate). Use a stable, kebab-case name scoped to the skill and decision, e.g.
`founder-review-mode-selection`, `founder-review-expansion-optin`,
`investigate-fix-vs-diagnosis`, `loop-mode-destination`, `outcome-coordinator-decision`,
`brainstorm-<decision>`. Verify each skill's actual gate sites before instrumenting — a citation
pointing at one line range does not guarantee exactly one gate.

## What this does not do

- Does not change what any gate offers or how it decides its default/recommendation.
- Does not add a new gate anywhere.
- Does not widen any autonomous-progression allowlist — it only produces the evidence a future
  widening decision would cite.
