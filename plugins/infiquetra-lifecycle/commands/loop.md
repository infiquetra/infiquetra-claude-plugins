---
name: loop
description: Route Infiquetra work through the lifecycle from idea to plan, PR, merge, or nonprod deploy
argument-hint: "[issue, plan path, work description, or 'resume' / 'drive it']"
---

Start, route, or resume the Infiquetra lifecycle loop. `/loop` is the lifecycle's **router** and
**resume substrate** — it classifies the input, finds in-flight work, and dispatches to the one
command that owns the next phase. It does not execute the phase work itself.

## Instructions

1. Load `infiquetra-lifecycle/skills/loop/SKILL.md` and run its three-mode flow:
   - **Route** (default) — dispatch to the one next command (it owns its phase, gates, AND its own
     backend).
   - **Drive** — walk phases across the lifecycle, agent-sequential, pausing at every hard gate and
     handoff.
   - **Resume** — `scan` the saga, `restore` the work-thread, re-enter where it left off; on a cold
     cache, reconstruct inline from committed `docs/*` and `load_saga_context.py`.
2. Scan the saga at entry, tick it on every routing decision, and pick the next command from
   `skills/loop/references/dispatch-table.md`. Volatile saga state lives under
   `.claude/infiquetra-lifecycle/`; the committed `docs/*` and issue/PR state are the durable source
   of truth.
3. Apply the one HARD gate (doc-review P0/P1 before `/work`); routes to stub targets
   (`/qa`, `/retro`, `/resume`, `/strategy`, `/optimize`) are advisory and never block `/loop`.
4. `/loop` owns the handoff envelope (`handoff_envelope.py`). It does **not** implement code (`/work`),
   plan (`/plan`), review (`/doc-review` / `/code-review` / `/founder-review`), run QA (`/qa`), file
   SDLC issues (`sdlc-manager`), deploy (`infiquetra-deploy`), **instruct a routed command's
   backend**, or do heavy forensic reconstruction (opt-in `/resume`).

Arguments provided to the command:

`$ARGUMENTS`
