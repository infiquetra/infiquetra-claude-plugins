# SDLC Manager Asgard/Olympus Issue Readiness Ideation

**Date:** 2026-05-30

**Focus:** Determine whether `sdlc-manager` can create issues that match the current Asgard and
Mount Olympus board expectations, and identify the strongest follow-up ideas for making issue
preparation reliable.

**Status:** Ideation only. No remote rollout, issue creation, or project-board mutation was
performed.

## Framing Update

This should be framed in board/team terms, not around a named runtime owner or orchestrator. The
useful product framing is **Asgard vs. Olympus issue readiness**.

The systems may converge later, and home-lab runtime files are useful evidence for today's stricter
Olympus-style checks, but the plugin should speak in board/team terms:

- **Asgard** expects work to be shaped enough for rapid action, incubation, or mission-mode
  coordination.
- **Mount Olympus** expects work to be dispatch-ready for the autonomous engineering pipeline.
- A source like `QUEUED.md` should be treated as prompt/source text, not as a special first-class
  workflow target.

## Executive Summary

The answer is conditional, not a clean yes.

1. **Does `sdlc-manager` account for the agentic teams and boards in `infiquetra-sdlc`?**
   Mostly yes for the canonical SDLC boards: Jeff Intent, Asgard, and Mount Olympus. The plugin's
   vendored schema and board commands know those boards and workflows.

2. **Can `sdlc-manager` create issues that pass the stricter Olympus-style readiness checks?**
   It can help, but it cannot guarantee that today. It understands the shared actionable issue
   shape and has a body validator mirror, but the current issue-create flow is still
   browser/manual, does not validate labels or author allow-list, and relies on target repos having
   the canonical issue templates deployed.

3. **Can we use it to shape `hermes-claude-code-router` work into board-ready issues?**
   Yes with manual care; no as a reliable one-command path. The missing piece is a team-aware issue
   preparation workflow that can produce either Asgard-ready shaping issues or Olympus-ready
   dispatch issues from ordinary source text.

The strongest survivor is a dry-run-first `sdlc-manager` workflow tentatively named
`issue prepare` or `issue prepare-team-card`. It should take a target repo, a target team/board,
and free-form source text, then produce a complete issue draft plus a readiness report. Issue
creation can come later once the dry-run shape is trusted.

## Grounding

Checked local repositories and files:

- Current repo: `infiquetra-claude-plugins`
  - `plugins/sdlc-manager/scripts/sdlc_manager.py`
  - `plugins/sdlc-manager/config/sdlc-schema.json`
  - `plugins/sdlc-manager/config/project-mappings.json`
  - `plugins/sdlc-manager/skills/sdlc-issues/SKILL.md`
  - `plugins/sdlc-manager/skills/sdlc-board/references/kanban-workflow.md`
  - `plugins/sdlc-manager/skills/sdlc-rollout/SKILL.md`
- SDLC repo:
  - `../infiquetra-sdlc/config/sdlc-schema.json`
  - `../infiquetra-sdlc/.github/ISSUE_TEMPLATE/capability.yml`
  - `../infiquetra-sdlc/AGENTS.md`
- Runtime/readiness evidence from home-lab:
  - `../home-lab/ansible/roles/hermes_orchestrator/files/card_validator.py`
  - `../home-lab/ansible/roles/hermes_orchestrator/files/config.py`
  - `../home-lab/ansible/roles/hermes_orchestrator/files/handlers.py`
  - `../home-lab/ansible/roles/hermes_agent_listener/files/prompts/assign_work.md`
  - `../home-lab/ansible/roles/hermes/files/skills/mimir-orchestration/SKILL.md`
  - `../home-lab/ansible/roles/hermes/files/skills/mimir-orchestration/references/issue-intake.md`
  - `../home-lab/ansible/roles/hermes/files/skills/mimir-orchestration/references/card-grammar.md`
  - `../home-lab/ansible/roles/hermes/files/skills/mimir-orchestration/references/selection-and-gates.md`
- Target repo:
  - `../hermes-claude-code-router/docs/engineering-journal/QUEUED.md`
  - `../hermes-claude-code-router/AGENTS.md`
  - local `.github/` contains `workflows/ci.yml` only; no `.github/ISSUE_TEMPLATE/` files.

Remote sanity check:

- `gh repo view infiquetra/hermes-claude-code-router` reports default branch `main`, last pushed
  `2026-05-27T03:45:47Z`.
- Local `hermes-claude-code-router` is on `main` at `d8711cf`, tracking `origin/main`.

## What `infiquetra-sdlc` Defines

The current SDLC schema defines these teams and boards:

| Team or role | Kind | Board |
|---|---|---|
| `jeff` | human operator | `jeff_intent` |
| `asgard` | agent team | `asgard` |
| `olympus` | agent team | `olympus` |
| `hermes` | system role | none |
| `themis` | retired historical role | none |

The board workflows are:

- Jeff Intent and Asgard: `Idea -> Shaping -> Ready -> Active -> Verify -> Done`
- Mount Olympus: `Backlog -> Ready -> Planning -> Assigned -> In Review -> Done -> Closed`

The Olympus Ready gate is the strict one:

- Actionable issue schema passes.
- Work is labeled for Olympus dispatch.
- Acceptance criteria and verification are present.

`sdlc-manager` has caught up to this board topology at the schema and board-tooling level. It has
`PROJECT_CHOICES = ("mount-olympus", "asgard", "jeff-intent")`, board references for all three,
and WIP/status behavior backed by the vendored schema.

## Asgard vs. Olympus Expectations

### Asgard Readiness

Asgard is for rapid action, incubation, and mission-mode work close to Jeff. An Asgard issue or
card can be useful before it is fully dispatch-ready. The shape should emphasize:

- Clear intent or problem statement.
- Target repository or surface.
- Mode: Rapid Action, Incubator, or Mission.
- Known constraints and risk.
- What would make the work promotable to Olympus, if promotion is expected.
- Jeff-needed or decision-needed state when the work crosses an approval boundary.

Asgard should be allowed to hold issue drafts that are not yet strict implementation contracts.
The plugin should not force every Asgard card through the Olympus issue schema.

### Olympus Readiness

Olympus is the autonomous engineering execution pipeline. An Olympus-ready issue needs the stricter
shape currently enforced by the runtime validator and assignment prompt:

- Actionable labels are present: type label, `hermes-task`, and `needs-plan`.
- Required H3 sections exist:
  - `Objective`
  - `Acceptance criteria`
  - `Out-of-scope / non-goals`
  - `Files expected to change`
  - `Tests to add or update`
  - `Verification`
- Acceptance criteria include at least one checklist item.
- Files expected to change include at least one plausible path.
- Verification includes a fenced command block.
- Placeholder-only sections fail.
- The issue author is allowed by the runtime configuration.
- The issue is on the intended project/status.

The stricter issue body matters because the assignment prompt treats the structured fields as the
execution contract: the worker only touches files in `Files expected to change`, and the exact
command in `Verification` is the acceptance signal.

## Current `sdlc-manager` Capability

What works today:

- Knows the six SDLC issue types.
- Documents actionable templates as `capability`, `enhancement`, and `defect`.
- Documents actionable template labels as type label + `hermes-task` + `needs-plan`.
- Can deploy canonical labels and issue templates to a repo using rollout commands.
- Can add issues to a GitHub Projects v2 board.
- Can set project fields via live field discovery.
- Can validate an issue body against the stricter body-shape checks.
- Can target Jeff Intent, Asgard, or Mount Olympus for board commands.

Important gaps:

- `issue create` has no `--project` override. It only discovers projects from repo mappings.
- `hermes-claude-code-router` is not in the vendored `project-mappings.json`.
- The sibling `infiquetra-sdlc` checkout currently has no local `config/project-mappings.json`, so
  the vendored mapping is the practical local source.
- Post-create metadata applies `hermes-task` or `hermes-not-actionable`, but relies on the selected
  issue template for `needs-plan` and the type label.
- The `--web` flow has a documented caveat: GitHub CLI may open a blank issue form even when a
  template was requested.
- If the template labels do not apply, the tool does not currently guarantee `needs-plan` or the
  type label.
- `flow validate-card` is a body validator, not a full label/author/project/status readiness check.
- The router repo lacks local issue templates, so template-driven issue creation will not work
  cleanly until templates are deployed.

## Source Text, Not Queue-Specific Automation

The router backlog is in `../hermes-claude-code-router/docs/engineering-journal/QUEUED.md`, and it
contains useful source material such as voice transcript routing, voice playback, button approvals,
tmux spawning, and hybrid tool dispatch.

That file does not need a special command. The better abstraction is:

- Take any source text: pasted prompt, copied queued entry, roadmap excerpt, blueprint section, or
  free-form note.
- Ask the operator for target team/board and issue type when not inferable.
- Produce a board-specific issue draft and readiness report.

This keeps `QUEUED.md` useful without making the plugin depend on one journal file format.

## Feasibility Answer

### Manual path today: feasible with care

For a single router item, a safe manual workflow today would be:

1. Deploy or confirm SDLC labels and templates on `hermes-claude-code-router`.
2. Decide board routing:
   - Use Asgard if the work is still shaping, incubating, or mission-mode near Jeff.
   - Use Mount Olympus if the card should be dispatch-ready for autonomous engineering execution.
3. If using `sdlc-manager` without mapping changes, create the issue with the template, then add it
   explicitly with `board add --project mount-olympus` or `board add --project asgard`.
4. Fill every required issue-form field with concrete content for Olympus-directed work.
5. Confirm labels include the type label, `hermes-task`, and `needs-plan` for Olympus-directed work.
6. Run `flow validate-card` for Olympus-directed work.
7. Keep the issue in Backlog/Shaping until it passes the appropriate team readiness expectations.

### One-command path today: not feasible

There is no current command that takes arbitrary source text, emits a team-specific issue draft,
proves labels/templates/author/project/readiness, and routes the card without manual steps.

### Risk if we use today's flow naively

The likely failure modes are:

- The router repo has no issue templates, so the issue body is blank or ad hoc.
- The issue has `hermes-task` but not `needs-plan` or the type label.
- The body passes the six-heading validator but lacks risk, authority, or definition-of-done detail
  that the team needs to execute safely.
- The repo is unmapped, so issue-create does not add it to the intended project.
- An Asgard-shaped issue is treated as Olympus-ready too early.
- An Olympus card is moved to Ready before it satisfies the stricter execution checks.

## Strongest Ideas

### 1. Add Dry-Run `issue prepare`

Create a dry-run-first command that turns source text into a board-ready issue draft.

Inputs:

- Target repo.
- Source text, from stdin, file path, or prompt argument.
- Issue type.
- Target team or project: Asgard or Mount Olympus first, Jeff Intent later if useful.
- Optional risk, affected repos, authority boundaries, validation expectations, and parent issue.

Outputs:

- Issue title.
- Complete issue body appropriate to the chosen team.
- Label set.
- Target project/status recommendation.
- Readiness report with pass/fail/warn results.

Why this survives: it gives the operator the high-leverage part without mutating GitHub first.
Issue authoring is the brittle step, and Asgard/Olympus need different levels of strictness.

### 2. Add `issue create` Support On Top Of Prepared Drafts

After the draft command is trusted, add a mutation-capable path that creates the issue and applies
metadata.

Required behavior:

- Refuse to create Olympus-directed actionable issues if target repo lacks canonical templates or
  labels unless `--allow-missing-rollout` is explicit.
- Add type label, `hermes-task`, and `needs-plan` explicitly after creation, not only via template.
- Support `--project mount-olympus|asgard|jeff-intent`.
- Add to the selected board explicitly.
- Set status to Backlog/Shaping by default, not Ready.
- Print the exact reason the card is or is not ready for the selected board.

Why this survives: direct creation becomes safe only after dry-run shape is deterministic.

### 3. Add Team-Aware Readiness Profiles

Extend `flow validate-card` into a broader checker:

```bash
sdlc_manager.py issue readiness --team olympus --repo <repo> --number <n>
sdlc_manager.py issue readiness --team asgard --repo <repo> --number <n>
```

Olympus checks:

- Body-shape validation.
- Required actionable labels.
- Author allow-list risk, or at least report issue author and configured/default allowed authors.
- Target repo template deployment.
- Target repo label deployment.
- Project mapping or explicit project presence.
- Project status.
- Verification block and expected file path sanity.

Asgard checks:

- Intent/problem is stated.
- Target repo/surface is present.
- Mode or promotion target is clear.
- Known constraints and risk are present.
- Jeff-needed state is clear when relevant.
- If marked for promotion to Olympus, the Olympus readiness gaps are listed.

Why this survives: the current body validator is necessary but too narrow.

### 4. Update Project Mappings And Routing Semantics

Add or generate a mapping for `hermes-claude-code-router`, but do not hide the routing decision.

Recommended default:

- `hermes-claude-code-router` should map to Mount Olympus if the goal is autonomous engineering
  dispatch.
- Asgard should stay available as an explicit target for shaping, incubation, and mission-mode work.

Why this survives: an unmapped repo is the reason the current issue-create flow cannot route router
issues automatically.

### 5. Keep Shared Templates Stable; Generate Team-Specific Additions In The Body

Do not add team-internal machinery as required shared template fields. Use generated body sections
or comments for team-specific details.

Why this survives: shared issue templates should remain human-facing and cross-team. The
team-specific details belong in generated drafts and readiness checks.

### 6. Add Drift Tests Against Asgard/Olympus Readiness Expectations

Add tests that keep `sdlc-manager` aligned with selected source facts:

- Board names and workflow statuses from `infiquetra-sdlc/config/sdlc-schema.json`.
- Required Olympus H3 headings.
- Actionable label names.
- Asgard mode/routing terms.
- Body-shape semantics.

Why this survives: there are now multiple moving sources. The costly drift is between issue
authoring guidance and runtime/team readiness.

## Rejected Or Deferred Ideas

### Add A Dedicated Source-File-To-Issues Command

Reject for now. A queued entry is just one possible source text. The stronger abstraction is
source-text-in, team-ready issue draft out.

### Auto-Move Created Issues Directly To Ready

Reject. Ready is a dispatch signal. A newly created issue should be Backlog/Shaping until the
appropriate readiness checks pass and the operator intends dispatch.

### Treat Every Unmapped Repo As Mount Olympus

Reject. It would make new repos easy to route incorrectly. The tool should require mapping or an
explicit `--project`.

### Add Team-Specific Required Fields To Shared Issue Templates

Reject for now. The shared templates should stay human-facing and cross-team. Team-specific
readiness detail belongs in generated issue bodies, comments, or project fields.

### Depend On GitHub's Browser Issue Form To Apply Everything

Reject. The current `gh issue create --web` caveat makes this too fragile. The plugin should
explicitly verify and, for labels, explicitly apply the required machine labels.

### Hardcode A Separate Runtime Board Into `sdlc-manager`

Defer. The stable public surfaces in `infiquetra-sdlc` are Asgard and Mount Olympus. If another
board or runtime API becomes canonical later, model it then.

## Recommended Next Brainstorm Topic

Use `ce-brainstorm` for:

> Define the `sdlc-manager` team-ready issue preparation workflow for turning source text into
> validated GitHub issue drafts that can be routed to Asgard or Mount Olympus without confusing
> shaping readiness with dispatch readiness.

Decisions that brainstorming should settle:

- Command name: `issue prepare`, `issue draft`, or `issue prepare-team-card`.
- Whether v1 is dry-run only.
- How target team is represented: `--team asgard|olympus`, `--project`, or both.
- Exact required inputs versus inferred fields.
- How source text is supplied: stdin, file path, prompt argument, or all three.
- The Asgard readiness checklist.
- The Olympus readiness checklist.
- The readiness output schema.
- The minimum change needed before creating router issues from copied queued entries or prompts.

## Practical Next Step For The Router Repo

Before creating real router issues:

1. Deploy or confirm canonical SDLC labels/templates on `hermes-claude-code-router`.
2. Add `hermes-claude-code-router` to project mappings or use explicit `board add --project`.
3. Pick one router work item and draft it twice:
   - Asgard version: shaping/mission-ready.
   - Olympus version: dispatch-ready.
4. Compare what fields differ.
5. Use that comparison as the input to `ce-brainstorm` for `issue prepare`.

This gives one concrete calibration issue before automating the workflow.
