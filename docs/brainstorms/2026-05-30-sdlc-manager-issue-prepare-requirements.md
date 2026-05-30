---
date: 2026-05-30
topic: sdlc-manager-issue-prepare
title: SDLC Manager Issue Prepare Requirements
source_idea: docs/ideation/2026-05-30-sdlc-manager-asgard-olympus-issue-readiness.md
---

# Requirements: SDLC Manager Issue Prepare

## Summary

Add a team-aware issue preparation workflow to `sdlc-manager`. The workflow turns source text into
reviewable issue drafts for Asgard or Mount Olympus, then creates the issue through a separate
confirmed command that can repair missing repo prerequisites and record the result back onto the
draft.

---

## Problem Frame

`sdlc-manager` can create template-guided issues, deploy labels/templates, add issues to project
boards, and validate the strict actionable body shape. It does not yet provide one reliable path
from rough source text to an issue that is ready for the intended team.

The current gap is not only issue body generation. Asgard and Mount Olympus have different
readiness expectations. Asgard can accept shaping, incubation, and mission-mode work that is not
yet a strict execution contract. Mount Olympus needs dispatch-ready issue structure: concrete
objective, acceptance criteria, scoped file paths, test expectations, verification commands,
labels, board placement, and safe default status.

Without a team-aware prepare/create workflow, agents and operators can create issues that look
valid but are routed too early, lack required labels/templates, miss project mappings, or require
manual repair before any team can use them.

---

## Key Decisions

- **Prepare and create are separate commands.** `issue prepare` writes a draft artifact and
  readiness sidecar. `issue create-prepared` performs GitHub mutations only after showing a final
  confirmation plan.
- **V1 includes creation.** Creation is not deferred to a later project, but it is separated from
  drafting so the operator can review before mutation.
- **Team and project are both required.** The deterministic command/API should know both target
  team and project. Natural-language skills may infer them when obvious, but must ask when the
  prompt is ambiguous.
- **The skill/model drafts; the CLI validates and mutates.** Rough-source interpretation belongs in
  the skill layer. `sdlc_manager.py` owns deterministic parsing, readiness checks, mutation-plan
  construction, and GitHub operations.
- **Repo readiness is self-healing by explicit confirmation.** Missing labels/templates are
  deployed directly. Missing project mappings trigger a branch-and-PR mapping update flow before
  issue creation proceeds by default.

---

## Actors

- A1. Operator — the human asking for issue preparation or creation.
- A2. Agent skill — interprets natural-language prompts, shapes rough source text, and writes draft
  artifacts for the CLI to validate.
- A3. `sdlc-manager` CLI — deterministic tool that parses drafts, validates readiness, builds
  mutation plans, and performs confirmed GitHub operations.
- A4. GitHub repository and project surfaces — target repo labels/templates/issues plus Asgard or
  Mount Olympus project board state.
- A5. SDLC mapping owner — the canonical source for repo-to-project mappings, normally the SDLC
  config repo; the plugin vendored mapping is a fallback.

---

## Requirements

**Draft Preparation**

- R1. `issue prepare` accepts source text from a prompt argument, stdin, or `--source-file`, and
  produces the same draft artifact shape regardless of input source.
- R2. `issue prepare` requires or infers the target repo, issue type, target team, and target
  project; if any cannot be inferred safely, it must ask rather than guess.
- R3. Prepared drafts are stored as repo files under `docs/sdlc-issue-drafts/` so they are easy to
  review, edit, commit, and pass to the create command.
- R4. Each prepared draft has a JSON sidecar containing structured readiness results and metadata
  needed by `issue create-prepared`.
- R5. Incomplete source text still produces a draft, but missing required fields are marked as
  blocking gaps.
- R6. A draft with blocking gaps cannot be created until the required gaps are resolved in the
  draft and sidecar.

**Team Readiness**

- R7. Asgard drafts use the existing SDLC issue types and a relaxed readiness profile focused on
  shaping quality: intent, target repo/surface, mode, constraints, risk, and promotion gaps.
- R8. Olympus drafts use the existing actionable issue templates and strict readiness profile:
  required H3 sections, checklist acceptance criteria, path-like expected files, fenced
  verification commands, actionable labels, author risk visibility, project presence, and safe
  status.
- R9. The workflow must not treat an Asgard-shaped draft as Olympus-ready unless the Olympus
  readiness profile passes.
- R10. The workflow must never auto-move a new issue to `Ready`.
- R11. `issue create-prepared` sets safe default statuses only: Asgard issues start in `Shaping`;
  Mount Olympus issues start in `Backlog`.

**Creation And Mutation**

- R12. `issue create-prepared <draft>` consumes the markdown draft and JSON sidecar, then presents a
  final mutation plan before any GitHub or mapping mutation.
- R13. The final mutation plan includes every planned side effect: label/template deployment,
  mapping branch/PR work, issue creation, board add, status setting, and draft update.
- R14. Missing labels/templates are deployed directly to the target repo after confirmation.
- R15. If the target repo is not mapped to the requested project, the create flow updates the
  canonical SDLC mapping when available; otherwise it may update the vendored plugin mapping with a
  clear warning.
- R16. Mapping updates are committed on a branch, pushed, and surfaced as a PR before issue
  creation continues by default.
- R17. If mapping is missing, creation stops after opening/reporting the mapping PR unless the
  operator explicitly chooses an override to create before the mapping PR merges.
- R18. The explicit override creates the issue using the requested project directly and records
  that canonical mapping is still pending.
- R19. After successful issue creation, the draft file is retained and marked with issue URL,
  issue number, creation timestamp, and mutation summary.

**Natural-Language Use**

- R20. Skills/docs treat natural-language usage as first-class. Prompts such as "create an
  Olympus issue from this text" route to prepare plus create-prepared, not to ad hoc issue
  creation.
- R21. Natural-language flows may infer team/project from explicit phrases such as "Asgard issue"
  or "Olympus issue"; ambiguous prompts must ask for the missing target.
- R22. Natural-language creation still uses the same draft artifact, JSON sidecar, readiness
  checks, and final mutation confirmation as direct CLI usage.

**Validation And Tests**

- R23. The feature includes parser and readiness unit tests for draft parsing, sidecar parsing,
  Asgard readiness, Olympus readiness, blocked creation, and sidecar/draft state transitions.
- R24. The feature includes mocked GitHub mutation tests for mutation-plan construction,
  label/template deployment, mapping PR flow, issue creation, board add, and status setting.
- R25. Tests must cover the override path that creates an issue before a mapping PR merges.

---

## Key Flows

- F1. Prepare from rough source text
  - **Trigger:** Operator or agent provides source text plus target repo/team/project.
  - **Actors:** A1, A2, A3.
  - **Steps:** Shape source text into an issue draft, write the markdown draft, write the JSON
    sidecar, and report readiness gaps.
  - **Outcome:** A reviewable draft exists without GitHub mutation.
  - **Covers:** R1-R8, R20-R22.

- F2. Prepare with incomplete source
  - **Trigger:** Source text lacks fields required by the selected team profile.
  - **Actors:** A1, A2, A3.
  - **Steps:** Write a draft with blocking gaps and sidecar failures.
  - **Outcome:** The operator can edit the draft, but `create-prepared` refuses to create until
    required gaps are resolved.
  - **Covers:** R5, R6, R9.

- F3. Create when prerequisites are present
  - **Trigger:** Operator runs `issue create-prepared <draft>` on a passing draft.
  - **Actors:** A1, A3, A4.
  - **Steps:** Present the mutation plan, receive confirmation, create the issue, add it to the
    selected project, set safe default status, and mark the draft created.
  - **Outcome:** The issue exists in the target repo and starts in the safe status for the chosen
    team.
  - **Covers:** R10-R13, R19.

- F4. Create with missing labels/templates
  - **Trigger:** Target repo lacks required SDLC labels or issue templates.
  - **Actors:** A1, A3, A4.
  - **Steps:** Include direct label/template deployment in the mutation plan, deploy after
    confirmation, then continue issue creation.
  - **Outcome:** Repo prerequisites are repaired and issue creation proceeds.
  - **Covers:** R13, R14.

- F5. Create with missing project mapping
  - **Trigger:** Target repo is not mapped to the requested project.
  - **Actors:** A1, A3, A5.
  - **Steps:** Include mapping branch/PR work in the mutation plan, create the mapping branch and
    PR after confirmation, then stop by default.
  - **Outcome:** Mapping repair is in flight; issue creation waits for merge unless explicitly
    overridden.
  - **Covers:** R15-R18.

---

## Acceptance Examples

- AE1. Olympus draft blocks on missing verification
  - **Covers R5, R6, R8.**
  - **Given:** Source text describes a router enhancement but does not include a verification
    command.
  - **When:** The agent prepares an Olympus issue draft.
  - **Then:** The draft is written with a blocking verification gap, and `create-prepared` refuses
    to create it.

- AE2. Asgard draft accepts shaping-quality input
  - **Covers R7, R9.**
  - **Given:** Source text describes mission-mode work with intent, repo, mode, constraints, and
    risk, but not expected file paths.
  - **When:** The agent prepares an Asgard issue draft.
  - **Then:** The Asgard readiness profile can pass, and the draft still reports Olympus promotion
    gaps separately.

- AE3. Create deploys missing labels/templates after confirmation
  - **Covers R12-R14.**
  - **Given:** A passing draft targets a repo missing SDLC templates.
  - **When:** The operator runs `issue create-prepared`.
  - **Then:** The confirmation plan lists template/label deployment before issue creation, and
    creation proceeds only after confirmation.

- AE4. Missing mapping opens PR and stops
  - **Covers R15-R17.**
  - **Given:** A passing Olympus draft targets an unmapped repo.
  - **When:** The operator confirms the mutation plan without an override.
  - **Then:** The command creates a mapping branch and PR, reports it, and stops before issue
    creation.

- AE5. Mapping override creates before merge
  - **Covers R17, R18.**
  - **Given:** A mapping PR was opened for the target repo.
  - **When:** The operator explicitly chooses to create before mapping merge.
  - **Then:** The command creates the issue using the requested project directly and records the
    pending mapping state in the draft.

- AE6. Natural-language creation uses the same path
  - **Covers R20-R22.**
  - **Given:** The operator says, "Create an Asgard issue from this text for the router repo."
  - **When:** An agent acts on the prompt.
  - **Then:** The agent prepares the draft artifact and invokes the create-prepared flow rather
    than bypassing readiness checks.

---

## Success Criteria

- The operator can review a prepared issue draft before any GitHub mutation.
- Asgard and Olympus readiness are visibly different and cannot be confused by accident.
- A prepared draft with missing required fields cannot be created.
- Creation presents one complete mutation plan before side effects occur.
- Missing labels/templates are fixed in the confirmed create flow.
- Missing project mappings result in a branch and PR, not an invisible local edit or default-branch
  push.
- Natural-language and direct CLI usage converge on the same artifacts and checks.
- Unit and mocked mutation tests cover blocked create, prerequisite repair, mapping PR flow, and
  successful issue creation.

---

## Scope Boundaries

- Dedicated `QUEUED.md` parsing is out of scope for v1. Queued entries are source text, not a
  separate workflow.
- Auto-moving issues to `Ready` is out of scope.
- Hidden repo setup or hidden mapping edits are out of scope; all mutations appear in the final
  confirmation plan.
- Direct default-branch mapping pushes are out of scope.
- Direct LLM calls from `sdlc_manager.py` are out of scope. Rough-source interpretation belongs in
  the skill/model layer.
- Replacing the existing six SDLC issue types is out of scope.

---

## Dependencies And Assumptions

- The target repo has or can receive canonical SDLC labels and templates.
- The create flow has GitHub permissions to create labels/templates/issues and add project items.
- Mapping update PRs require an authenticated GitHub flow and a writable checkout of the canonical
  SDLC config or plugin fallback mapping.
- The skill layer can generate a draft from source text before invoking deterministic CLI
  validation.
- Asgard and Mount Olympus remain the stable public target surfaces for this workflow.

---

## Sources

- `docs/ideation/2026-05-30-sdlc-manager-asgard-olympus-issue-readiness.md`
- `plugins/sdlc-manager/scripts/sdlc_manager.py`
- `plugins/sdlc-manager/config/sdlc-schema.json`
- `plugins/sdlc-manager/config/project-mappings.json`
- `plugins/sdlc-manager/skills/sdlc-issues/SKILL.md`
- `plugins/sdlc-manager/skills/sdlc-board/references/kanban-workflow.md`
- `plugins/sdlc-manager/skills/sdlc-rollout/SKILL.md`
- `infiquetra-sdlc: config/sdlc-schema.json`
- `home-lab: ansible/roles/hermes_orchestrator/files/card_validator.py`
- `home-lab: ansible/roles/hermes_agent_listener/files/prompts/assign_work.md`
