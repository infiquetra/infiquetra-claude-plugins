---
name: tier
description: Set a run-scoped model/effort tier ceiling, or patch a not-yet-run unit's tier mid-run, without aborting and re-planning. Writes a session-local override the emitters clamp to. Triggers on "set a tier ceiling", "cap the model this run", "change this unit's tier mid-run", "/tier".
argument-hint: "<model>/<effort> (ceiling) | <unit-id> <model>/<effort> (mid-run patch) | show | clear"
---

Adjust the fleet's model/effort tier **mid-run** without aborting and re-planning. `/tier` writes a
session-local override (`.claude/saga/tier-session-override.json`) that the workflow and team-execution
emitters clamp every unit down to; the `inline` backend honors it advisorily. It **never raises** a
tier — a ceiling only clamps down (`{#tier-vocab-ordering}`), and an up-ladder mid-run patch is gated
(asks) before it re-emits.

## Two forms

1. **Session ceiling** — `/tier sonnet/medium` caps the whole run: every subsequently emitted unit
   above the ceiling is clamped down to it, logged, with no re-prompt.
2. **Mid-run patch** — `/tier <unit-id> opus/high` edits the tier of the named **not-yet-run** unit(s)
   in the canonical `ExecutionSpec`, re-validates, and re-emits the downstream workflow. Already-run
   units are never touched.

## Instructions

1. **Parse the argument.** A bare `<model>/<effort>` is a ceiling; a `<unit-id> <model>/<effort>` pair
   is a mid-run patch; `show` / `clear` inspect or reset the override.

2. **Ceiling form.** Write it via the session-override CLI (values validated against the palette —
   off-palette fails loud):
   ```bash
   python3 plugins/saga/scripts/tier_session.py set-ceiling <model> <effort>
   ```
   The next `/work` emit (workflow or team-execution) reads the file and clamps each unit/segment tier
   down to the ceiling. Nothing else to do — the emitters enforce it.

3. **Mid-run patch form.**
   1. Record the per-unit override:
      ```bash
      python3 plugins/saga/scripts/tier_session.py set-unit <unit-id> <model> <effort>
      ```
   2. **Escalation gate.** If the new tier is *stronger* than the unit's current tier (up-ladder on
      either axis), this is an escalation — **confirm with the operator before re-emitting** (a
      cheapen-or-lateral move proceeds without a prompt). The cost-weighted spend-delta classifier is
      #367's; this is the minimal ask-gate.
   3. Apply to the canonical spec, re-validate (HARD block on failure — never emit an invalid spec),
      and re-emit. Derive `--already-run` from live run-state (the saga's completed units / the workflow
      manifest); absent reliable run-state, refuse rather than risk patching a unit that already ran:
      ```bash
      python3 plugins/saga/scripts/execution_spec.py patch <spec.json> --already-run "<ids>" -o <spec.json>
      python3 plugins/saga/scripts/execution_spec.py validate <spec.json>
      python3 plugins/saga/scripts/execution_spec.py emit <spec.json> -o <topic>.workflow.js
      ```

4. **Log, don't prompt (ceiling).** A ceiling clamp is logged (unit id, original -> clamped tier) and
   never re-prompts.

## Boundary

`/tier` writes the session override and drives the patch/validate/emit; it does not run leaf work,
merge, or deploy. It stays CLI-driven and spec-re-emit-based (`{#operator-choice-framework}` —
doc-only / CLI-driven), never a runtime-injection mechanism.
