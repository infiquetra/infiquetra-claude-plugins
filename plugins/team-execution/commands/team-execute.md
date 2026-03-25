---
name: team-execute
description: Execute a plan with automatic multi-reviewer consensus workflow
argument-hint: "[plan text or file path]"
---

Handle this command as follows based on what's available:

## Case 1: No plan provided

If `$ARGUMENTS` is empty and there is no plan in the current conversation context:

Ask the user:
```
Please describe what you want to build or provide a plan to execute.

Once you share the details, I'll enter plan mode to structure the work, then the
team-execution skill will embed a Team Structure into the plan. When you exit plan mode,
TeamCreate will fire automatically.
```

## Case 2: Plan exists but has no `## Team Structure` section

If a plan is present (from `$ARGUMENTS`, a file path, or the current conversation) but it
does NOT contain a `## Team Structure` section:

Enter plan mode and invoke Phase A of the `team-execution` skill:
`team-execution/skills/team-execution/SKILL.md`

Phase A will:
1. Classify the plan (code/docs/mixed)
2. Run the triage escape hatch check
3. Detect optional reviewers from plan keywords
4. Derive workers from plan phases
5. Get user confirmation
6. Embed `## Team Structure` into the plan

After Phase A completes, the plan is ready. When the user exits plan mode, the global
CLAUDE.md rule will detect `## Team Structure` and fire TeamCreate automatically.

## Case 3: Plan already has `## Team Structure`

If the plan already contains a `## Team Structure` section (e.g., the user ran Phase A in
a prior session and saved the plan):

Announce:
```
✅ This plan already has a Team Structure defined. Ready to begin execution.

Exiting plan mode now — TeamCreate will fire and you'll orchestrate workers and reviewers
directly following Phase B of the team-execution skill.
```

Then exit plan mode so the CLAUDE.md rule triggers TeamCreate.

---

## Quick Reference

The plan to execute (if provided):

$ARGUMENTS
