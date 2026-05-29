---
name: resume
description: Resume Infiquetra work from durable plans, work sessions, issues, PRs, and ignored local loop state.
---

# Resume

Use this when a session ended, context was lost, or the user asks to continue a work loop.

## Workflow

1. Read committed artifacts first:
   - `docs/plans/`
   - `docs/work-sessions/`
   - `docs/qa/`
   - `docs/retros/`
   - issue and PR comments
2. Read `.claude/infiquetra-loop/` only for raw scratch state and active pointers.
3. Reconstruct current phase, selected destination, blockers, checks run, and next step.
4. Continue from the durable source of truth rather than chat memory alone.
5. If evidence conflicts, prefer committed docs and issue state over raw local cache.
