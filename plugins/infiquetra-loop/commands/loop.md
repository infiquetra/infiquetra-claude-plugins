---
name: loop
description: Route Infiquetra work through the lifecycle from idea to plan, PR, merge, or nonprod deploy
argument-hint: "[issue, plan, or work description]"
---

Start or continue the Infiquetra lifecycle loop.

## Instructions

1. Load `infiquetra-loop/skills/loop/SKILL.md`.
2. Ask for the destination if it is not already clear: plan only, PR, merge, or nonprod deploy.
3. Ask whether to file an SDLC issue first for non-trivial ad-hoc work.
4. Persist durable artifacts in repo docs and raw runtime state under `.claude/infiquetra-loop/`.
5. Use `infiquetra-deploy` only when the chosen destination includes deployment.

Arguments provided to the command:

`$ARGUMENTS`
