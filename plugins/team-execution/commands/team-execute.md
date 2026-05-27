---
name: team-execute
description: Execute a plan with reviewer consensus, validator gates, and guarded nonprod automation
argument-hint: "[plan text or file path]"
---

Handle this command based on available input.

## Case 1: No plan provided

If `$ARGUMENTS` is empty and there is no plan in the current conversation context, ask the
user to describe the work or provide a plan.

Then enter plan mode and invoke:

`team-execution/skills/team-execution/SKILL.md`

## Case 2: Plan exists but has no `## Team Structure`

If a plan is present from `$ARGUMENTS`, a file path, or the current conversation, and it does
not contain `## Team Structure`, enter plan mode and invoke Phase A of:

`team-execution/skills/team-execution/SKILL.md`

Phase A will:

1. Inspect plan and repository signals.
2. Read optional `.team-execution.json`.
3. Derive workers from plan phases.
4. Select reviewers.
5. Select context-appropriate validators.
6. Decide whether nonprod automation is eligible.
7. Embed `## Team Structure`, validator gates, and reference files into the plan.

## Case 3: Plan already has `## Team Structure`

If the plan already contains `## Team Structure`, announce that it is ready for execution and
then follow Phase B of:

`team-execution/skills/team-execution/SKILL.md`

Phase B order is worker completion, reviewer consensus, scanners, CI/nonprod coordination,
testers, monitors, and final evidence report.

## Quick Reference

The plan to execute, if provided:

$ARGUMENTS
