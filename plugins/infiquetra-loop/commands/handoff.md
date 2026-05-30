---
name: handoff
description: Prepare a lifecycle artifact for SDLC issue handoff through sdlc-manager
argument-hint: "[source artifact, target team, or handoff notes]"
---

Route current lifecycle work to `sdlc-manager` issue preparation.

## Instructions

1. Load `infiquetra-loop/skills/handoff/SKILL.md`.
2. Identify the source artifact from arguments, active loop state, or durable repo docs.
3. Build a handoff envelope with `scripts/handoff_envelope.py`.
4. If source, maturity, target repo, target team, or issue type is ambiguous, ask a focused
   question before routing.
5. Route to `/create-issue --prepare --from <source> --maturity <maturity>`.
6. Do not generate an SDLC issue body in `infiquetra-loop`; `sdlc-manager` owns that artifact and
   all GitHub mutation.

Arguments provided to the command:

`$ARGUMENTS`
