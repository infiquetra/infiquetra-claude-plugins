# Ideation: Infiquetra Loop to SDLC Handoff

**Date:** 2026-05-30

**Focus:** Decide when lifecycle work should branch from local `infiquetra-loop` artifacts into an
SDLC issue artifact owned by `sdlc-manager`, especially when another team such as Asgard or Mount
Olympus will pick up the work.

**Status:** Ready for brainstorm. This captures the handoff timing, command naming, and
natural-language trigger decision surface. No command, issue, or remote mutation was created.

## Current Thesis

The useful product idea is not "make `/loop` create issues." The cleaner idea is a handoff boundary:
when work is ready to leave the current human/session, `infiquetra-loop` can package durable
context and route into an SDLC issue artifact, but `sdlc-manager` owns the issue artifact and all
GitHub/project mutation.

That boundary matters because the recipient may not have `infiquetra-loop` installed. The created
issue should be useful on its own: full issue body, target board/team fields, readiness profile,
links to source artifacts, and exact next action. It may include a small optional line for agents
that do have `infiquetra-loop`, but the issue must not depend on that plugin to be executable.

The operator-facing issue command should be named for the thing the user wants, not for the
implementation phase. Prefer `/create-issue` with natural-language routing and flags such as
`--prepare` or `--draft` over names like `/issue-handoff`, `/sdlc-handoff`, or
`create-prepared`. "Prepared issue" can remain an internal artifact and CLI state, but it should
not be the primary phrase users need to remember.

Brainstorm decisions captured so far:

- Explicit "create" language should build a mutation plan and create only after confirmation.
- Explicit "prepare", "draft", or "do not create yet" language should stop at the draft/sidecar.
- The canonical no-mutation flag is `--prepare`; `--draft` is an alias.
- `/create-issue` should become the primary documented command; `/sdlc-create` remains as a
  compatibility alias.
- Handoff maturity should live in both the issue body and the JSON sidecar.
- `/handoff` should infer maturity from the current artifact and ask only when uncertain.
- V1 should include both `/create-issue` and a thin `/handoff` surface.
- Asgard and Olympus are sibling target teams/boards, not stages in one funnel. Cross-team movement
  is explicit human/operator action only.
- The brainstorm requirements should include a P0 prerequisite to correct the stale
  Asgard-to-Olympus promotion model in the canonical SDLC materials and synced `sdlc-manager`
  references before implementing handoff behavior.
- `/create-issue` should support explicit source artifacts through `--from`, and natural-language
  prompts that imply an existing artifact should trigger repo-local artifact search before asking
  the user for a path.

## Grounding

- `/plan` already accepts an issue, spec, or request. The command hint is `[issue, spec, or
  request]`, and the plan skill starts by reading the issue, relevant docs, repository guidance, and
  local code before planning.
- `/work` accepts `[plan path or issue]`, but its skill says it is for an approved plan or resume
  case. That implies `/work <issue>` is appropriate only when the issue already contains or links a
  plan-grade execution contract.
- `sdlc-manager` already owns the prepared issue boundary. `issue prepare` writes a markdown draft
  plus JSON sidecar, and `issue create-prepared` re-runs readiness and shows a mutation plan before
  issue creation.
- `sdlc-manager` already distinguishes Asgard and Mount Olympus readiness profiles. Asgard can
  accept shaping-quality issues; Olympus requires strict actionable fields, labels, safe status,
  acceptance criteria, expected files, tests, and verification.
- Asgard and Olympus should be treated as sibling target teams/boards for this command. Do not
  imply an automatic Asgard-to-Olympus relationship. Asgard can carry work to completion; Olympus
  can carry work to completion. Moving an issue between them, or creating a linked issue for the
  other board, is an explicit human/operator action.
- `sdlc-manager` already has `/sdlc-create`; this should become a compatibility or namespaced
  alias if a clearer `/create-issue` command is added. The primary command should optimize for
  natural operator language.
- Current `infiquetra-sdlc` and vendored `sdlc-manager` materials still encode an older
  Asgard-to-Olympus promotion model. That should be corrected before implementing the handoff
  requirements so the new command does not inherit the stale team relationship.
- The prior Mimir orchestration analysis points in the same direction: do not reimplement the
  downstream team's execution substrate. Use the native board/card/issue mechanisms and add only
  the source-context and readiness information the downstream team needs.

## Domain Split

### `sdlc-manager` Owns

- The primary issue command, preferably `/create-issue`.
- Backward-compatible or namespaced aliases such as `/sdlc-create`.
- Draft/prepare behavior behind natural language or explicit flags:
  - `/create-issue --prepare`
  - `/create-issue --draft`
  - "prepare an issue but do not create it yet"
  - "turn this plan into an Olympus issue"
- Explicit and inferred source artifact discovery:
  - `/create-issue --from docs/brainstorms/router-requirements.md`
  - "from the plan we just made"
  - "from that brainstorm doc"
  - "turn the current requirements into an issue"
- Internal `issue prepare` and `issue create-prepared` mechanics.
- Handoff maturity/readiness fields in the draft and sidecar.
- Team-aware defaults:
  - Asgard starts in `Shaping`.
  - Mount Olympus starts in `Backlog`.
  - Never auto-move prepared work to `Ready`.
- The final issue body and mutation plan.

### `infiquetra-loop` Owns

- The lifecycle handoff prompt:
  - "Are we carrying this forward here, or handing it off?"
  - "Should this become an issue for another team?"
  - "Do we stop at requirements, plan it here, or hand it to someone else?"
- An optional `/handoff` command for the current lifecycle artifact.
- Detecting lifecycle exit points during ideation, brainstorm, planning, review, work, retro, and
  resume.
- Packaging source artifacts into a clear handoff bundle:
  - ideation doc
  - brainstorm/requirements doc
  - plan path
  - doc-review artifact
  - work-session summary
  - PR or branch state
  - checks and blockers
- Asking whether to hand off when the current session should stop carrying the work directly.
- Calling or pointing to `/create-issue` rather than creating issues itself.

Avoid making `/handoff-plan` and `/handoff-requirements` the primary command surface. They are
reasonable aliases or natural-language triggers, but a single `/handoff` can infer the current
artifact type from context and ask only when ambiguous.

## Planning Prerequisite

The requirements for this work should explicitly include a prerequisite workstream:

1. Correct the canonical Asgard/Olympus relationship in `infiquetra-sdlc`.
2. Sync the corrected model into the vendored `sdlc-manager` plugin materials.
3. Update `sdlc-manager` prepared-issue wording, readiness checks, and tests that still frame
   Asgard as a feeder, promotion, or staging lane for Olympus.
4. Only then implement `/create-issue`, `/handoff`, handoff maturity, and source-artifact packaging.

This prerequisite belongs in the plan generated from the requirements, not merely in background
notes. The plan should make it an early task group or precursor issue so the new handoff flow is
built on the desired model:

- Asgard and Olympus are sibling target teams/boards.
- Asgard can carry work to completion.
- Olympus can carry work to completion.
- Moving or cloning work across teams is explicit human/operator action only.
- Readiness can influence warnings and defaults, but it must not imply automatic promotion.

## When To Handoff

### 1. Raw Ideation

Default: do not hand off yet.

Use a handoff only when the target is Jeff Intent, Asgard Incubator, or an explicit exploration
issue. The artifact is not implementation-ready. Suggested next action:

```text
If using infiquetra-loop: /brainstorm <issue>
```

or, if the issue is already a clear research/shaping prompt:

```text
If using infiquetra-loop: /plan <issue>
```

### 2. Post-Brainstorm / Post-Requirements

This is the first natural handoff point.

Use this for Asgard, Jeff, or any team that should plan the work later. The issue should be
requirements-ready, not work-ready. It needs enough context for a recipient to understand the
problem, constraints, non-goals, risks, and likely verification path, but it may still lack a final
implementation plan.

Suggested next action:

```text
If using infiquetra-loop: /plan <issue>
```

### 3. Post-Plan

This is the best handoff point for Mount Olympus or another implementation team.

Use this when the work has an approved plan or plan-grade issue body: acceptance criteria, likely
files, tests, verification commands, review gates, deployment gates when relevant, and explicit
non-goals. This is where `/work <issue>` becomes valid.

Suggested next action:

```text
If using infiquetra-loop: /work <issue>
```

If the plan still needs review, use:

```text
If using infiquetra-loop: /doc-review <plan>, then /work <issue>
```

### 4. Mid-Work Pause Or Transfer

Use this when the current session started execution but another session/team must resume.

The issue must include the plan, current branch or PR, completed phases, checks run, blockers,
remaining acceptance criteria, and any review status. This is not a fresh planning handoff; it is a
resume handoff.

Suggested next action:

```text
If using infiquetra-loop: /work <issue>
```

### 5. External Or Deferred Work

Use this when the work should leave the current repo/session but is not ready for Asgard or
Olympus execution.

Targets include Jeff Intent, External/Deferred, context-update, exploration, or a repo engineering
journal queue. The artifact should preserve context and a decision-needed state rather than
pretending implementation is ready.

### 6. Cross-Team Transfer

Do not auto-offer cross-team transfer as part of normal handoff. If the human explicitly decides an
Asgard issue belongs on Olympus, or an Olympus issue belongs on Asgard, treat that as a separate
operator-directed action. The command should support it, but not infer it from readiness alone.

Open prerequisite: align `infiquetra-sdlc` and `sdlc-manager` references that still describe Asgard
as a feeder or staging lane for Olympus. The desired rule is: teams are target destinations; moving
or cloning work across teams is an explicit operator decision.

## Handoff Maturity Model

The issue artifact should carry a small maturity marker so the recipient does not infer too much
from the fact that an issue exists.

| Maturity | Meaning | Likely target | Next action |
|---|---|---|---|
| `idea-ready` | Captured intent worth preserving, not shaped enough for planning. | Jeff Intent / Asgard Incubator | `/brainstorm <issue>` or manual shaping |
| `requirements-ready` | Problem, constraints, risks, and desired outcome are clear. | Asgard / Jeff / later planner | `/plan <issue>` |
| `plan-ready` | A plan-grade execution contract exists or is embedded. | Olympus / implementation agent | `/work <issue>` |
| `resume-ready` | Work already started and has enough state to resume safely. | Current owner / implementation agent | `/work <issue>` |
| `deferred-context` | Useful context, not current execution work. | External/Deferred / context-update | no automatic loop command |

## Issue Artifact Expectations

The artifact should be self-contained first and plugin-assisted second.

Required:

- target repo or surface
- target team/board/project
- issue type
- handoff maturity
- source artifacts and links
- acceptance criteria or shaping criteria appropriate to maturity
- risk and approval boundary
- non-goals
- verification or proof path
- known blockers and open questions
- suggested next action

Optional:

- `Using infiquetra-loop: /plan <issue>`
- `Using infiquetra-loop: /work <issue>`
- `Using infiquetra-loop: /loop <issue>` only when the target is Jeff/operator lifecycle routing.

Do not suggest `/loop` to agent teams by default. `/loop` is a human lifecycle router, not the
normal downstream execution entrypoint.

## Command Naming Ideas

### Recommended Primary SDLC Command: `/create-issue`

This should be the operator-facing issue command in `sdlc-manager`.

Examples:

```text
/create-issue
/create-issue capability --repo infiquetra-claude-plugins
/create-issue --team olympus --repo campps-mvp
/create-issue --prepare --team asgard --from docs/brainstorms/router-requirements.md
/create-issue --draft --team olympus --from docs/plans/router-plan.md
/create-issue "turn this plan into an Olympus issue"
/create-issue "prepare an Asgard issue from these notes, but don't create it yet"
```

Behavior:

- Default to natural-language inference when the user supplies prose.
- Support `--from` for explicit source artifacts such as ideation docs, brainstorm requirements,
  plans, doc-review artifacts, work-session summaries, existing issue URLs, PR URLs, or branch
  state notes.
- When the user uses natural language that implies a source artifact exists, search likely local
  artifact locations before asking for a path. Example phrases include "from the plan we just
  made", "from that brainstorm", "from the requirements", "from the current issue", and "from the
  work summary".
- Present likely source matches when multiple artifacts fit the prompt; ask only after search
  cannot find a confident single match.
- Ask when repo, team, project, issue type, or maturity is ambiguous.
- Use `--type`, `--team`, `--repo`, `--project`, and `--maturity` when the user wants absolute
  control.
- Treat `--prepare` and `--draft` as no-GitHub-mutation modes. They write the draft/sidecar and
  stop.
- Treat an explicit create intent as permission to run the confirmed creation flow, still showing
  the mutation plan before side effects.

This keeps the mental model simple: the user is always creating an issue. Sometimes they are
creating only the draft first.

### Recommended Loop Command: `/handoff`

This should be an `infiquetra-loop` lifecycle command, not an issue system command.

Examples:

```text
/handoff
/handoff this plan to Olympus
/handoff requirements to Asgard
/handoff --team olympus --maturity plan-ready
```

Behavior:

- Read the active lifecycle pointer or the provided artifact path.
- Infer whether the source is ideation, requirements, plan, review, work-session, or resume state.
- Ask whether the user is carrying the work forward locally or handing it to another team.
- Package the source bundle and route to `/create-issue`.

### Good Natural-Language Triggers

These should activate `/create-issue` or `/handoff` without requiring slash-command precision:

- "Create an issue for this."
- "Turn this plan into an Olympus issue."
- "Prepare an issue but don't create it yet."
- "Draft an Asgard issue from these notes."
- "This is ready to hand off."
- "Hand this plan to Olympus."
- "Hand the requirements to Asgard."
- "We are stopping here; make the issue."
- "Do not keep working this, file it for the team."
- "Carry this forward here" should do the opposite: continue the local loop rather than create an
  issue.

### Names To Avoid As Primary Commands

- `/issue-handoff` and `/sdlc-handoff`: too abstract and too focused on process mechanics.
- `/create-prepared`, `/create-prepared-issue`, or `/issue-create-prepared`: describes the
  implementation boundary, not the user's intent.
- `/handoff-plan` and `/handoff-requirements`: useful as aliases or natural-language routes, but
  too fragmented as the main surface.

## Surviving Ideas

### 1. Primary `/create-issue` command with prepare/draft modes

Create one main issue command. It should infer issue type, target team, target repo, project, and
maturity when the language makes them clear, and expose flags when the user wants to be absolute.
Draft-only behavior should be expressed as `/create-issue --prepare`, `/create-issue --draft`, or
natural language such as "prepare an issue but do not create it yet."

**Why it matters:** The user wants to create an issue, not remember the internal prepare/create
state machine. A single verb keeps the surface obvious while still preserving the safe draft-first
boundary.

### 2. Loop exit prompts at maturity boundaries, with `/handoff` as the manual trigger

Teach `infiquetra-loop` to offer handoff at natural boundaries:

- after ideation if the user wants to preserve intent
- after brainstorm/requirements if another team should plan it
- after plan/doc-review if another team should execute it
- after interrupted work if another session should resume it

**Why it matters:** This keeps `/loop` useful for humans without making it the only way to create a
handoff artifact.

The prompt language should be plain:

```text
Are we carrying this forward here, or handing it off?
```

### 3. Handoff maturity in the prepared issue sidecar

Extend prepared issue metadata with an explicit maturity value and next-action hint. This is more
important than the exact slash command name because it prevents premature `/work` or Olympus
dispatch.

**Why it matters:** "An issue exists" is too weak a signal. The downstream agent needs to know
whether the issue is idea-ready, requirements-ready, plan-ready, resume-ready, or deferred context.

### 4. Optional plugin next-action line

Add a small optional line to the issue body:

```text
If using infiquetra-loop: /plan <issue>
```

or:

```text
If using infiquetra-loop: /work <issue>
```

**Why it matters:** It helps compatible sessions without making the issue depend on local plugin
installation.

## Rejected Or Deferred Ideas

### Make `/loop` the only handoff surface

Rejected. Handoff is a lifecycle exit in `/loop`, but it is also a standalone SDLC operation. The
artifact belongs to `sdlc-manager`.

### Make `/issue-handoff` or `/sdlc-handoff` the primary command

Rejected for now. These names are accurate from a workflow architecture view, but they make the
user think in process terms. `/create-issue` is closer to the operator's intent.

### Suggest `/loop <issue>` to agent teams

Reject as default behavior. `/loop` is for human/operator routing. Agent teams should receive an
issue that says either plan it, work it, review it, or preserve it.

### Require the target to have `infiquetra-loop`

Rejected. The issue artifact must be executable from GitHub and normal SDLC surfaces. Plugin hints
are optional convenience.

### Route post-brainstorm directly to `/work`

Rejected. Post-brainstorm output can be requirements-ready, but `/work` should require an approved
plan or plan-grade issue.

### Split the main surface into `/handoff-plan` and `/handoff-requirements`

Defer as aliases only. These names are understandable, but they encode artifact type in command
names. A context-aware `/handoff` should infer source type first and ask only when ambiguous.

### Auto-promote Asgard work to Olympus when it becomes actionable

Rejected. Asgard and Olympus are target teams, not maturity stages in a single funnel. Asgard can
finish work itself. If the human wants to move or clone work onto Olympus, that should be an
explicit action.

## Brainstorm Resolution

Resolved decisions:

1. The explicit no-mutation flag is `--prepare`; `--draft` is an alias.
2. `/create-issue` becomes the documented primary command; `/sdlc-create` remains a compatibility
   alias.
3. Handoff maturity appears in both the issue body and JSON sidecar.
4. `/plan <issue>` creates a durable `docs/plans/` artifact and syncs a compact summary/link back
   to the issue.
5. Source artifacts are first-class through `--from`, and natural-language artifact references
   trigger repo-local search before asking the operator for a path.
6. Cross-team movement is explicit operator action only. Asgard and Olympus are sibling targets,
   not stages in a single promotion funnel.

Durable requirements:

- `docs/brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md`
