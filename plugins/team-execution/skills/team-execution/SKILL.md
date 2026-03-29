---
name: team-execution
description: |
  Two-phase structured plan execution with automatic multi-reviewer consensus workflow.

  Phase A runs DURING plan mode: reads the plan, derives workers from plan phases, detects
  optional reviewers from keywords, embeds a ## Team Structure section, and calls
  ExitPlanMode itself. The plan is a single atomic artifact — implementation steps, team
  roster, and review protocol approved together in one unit.

  Phase B is the orchestration protocol that Claude follows directly after plan approval:
  TeamCreate fires immediately (ONLY permitted first action), then plan approval gates,
  parallel execution, max-3-iteration review cycle with 9/10 consensus threshold, and
  completion reporting.

  Pattern source: adapted from a structured team review cycle for code/plan execution.
when_to_use: |
  Use this skill when:
  - The user is in plan mode with a non-trivial plan that lacks a ## Team Structure section
  - The user asks "who should review this?" or "what team do I need?" during planning
  - The user invokes /team-execute
  - A plan has 3+ steps, touches 3+ files, or involves docs/specs
  Do NOT use when:
  - The plan already has a ## Team Structure section (TeamCreate will fire automatically)
  - The change is trivially simple (single file, no security surface)
---

# Team Execution Skill

This skill has two phases:

- **Phase A** runs DURING plan mode. You read the current plan, classify it, derive workers
  from plan phases, detect optional reviewers, get user confirmation, embed the
  `## Team Structure` section, and then call `ExitPlanMode` yourself. The plan is a single
  atomic artifact — the user approves the implementation plan, team roster, and review
  protocol in one unit. You do NOT spawn agents or call TeamCreate during Phase A.

- **Phase B** is the orchestration protocol for Claude to follow directly. It is NOT
  invoked as a separate agent. When Phase A calls ExitPlanMode and the plan contains
  `## Team Structure`, your ONLY permitted next action is TeamCreate. Read Phase B as your
  operating instructions and orchestrate workers and reviewers directly.

---

# Phase A: Team Planning (runs DURING plan mode)

## Step A1: Plan Intake & Triage

### A1a. Locate the Plan

The plan is already in the current plan-mode session. If multiple plans are in context,
ask the user to confirm which one to annotate with a team structure.

### A1b. Classify Plan Type

Read the plan and classify it:

| Type | Definition |
|------|------------|
| **code** | Primarily code changes: implementations, refactors, bug fixes, infrastructure |
| **docs/specs** | Primarily documentation: README, specs, issue templates, SKILL.md, ADRs |
| **mixed** | Both code AND documentation/spec content |

This classification determines which optional reviewers are suggested in Step A2.

### A1c. Run Triage Check

A plan qualifies for the **triage escape hatch** ONLY if ALL four criteria are true:

1. Single config file change (version bump, env var, flag toggle)
2. No security surface affected (no auth, secrets, permissions, PII)
3. Fewer than 3 files modified
4. No specification or documentation content

**Docs-only plans do NOT qualify** — documentation is specs for code and deserves full review.

If all criteria are met, offer:
```
This looks like a trivial config change. How would you like to proceed?

A) Skip team planning (recommended for this change)
B) Full review team anyway
C) Devil's Advocate only (lightweight check)
```

If the user picks A, stop here — do not embed a Team Structure section.
If any criterion is not met, proceed directly to Step A2.

---

## Step A2: Reviewer Detection & Team Proposal

### A2a. Detect Optional Reviewers

Read `team-execution/skills/team-execution/references/reviewer-registry.md`.

Scan the plan content for keywords in the optional reviewer trigger table. Based on plan type:
- **code** plans: check code-focused keyword triggers
- **docs/specs** plans: check doc-focused keyword triggers
- **mixed** plans: check both trigger sets

### A2b. Present Reviewer Proposal

Show the user:
```
Base reviewers (always included):
  🔴 Devil's Advocate — assumptions, edge cases, failure modes
  🟠 Security Reviewer — OWASP, secrets, auth/authZ, PII
  🟣 Architecture Reviewer — design patterns, separation of concerns, convention adherence

Suggested optional reviewers (detected from plan content):
  [e.g., 🔵 Infra Reviewer — CDK/Lambda/cloud infrastructure detected]
  [e.g., 🟢 API Reviewer — new endpoint patterns detected]

Confirm, skip optional reviewers, or add custom reviewers?
```

**Hard gate**: Wait for user confirmation before proceeding to Step A3.

---

## Step A3: Worker Derivation

For each major phase or parallel work stream in the plan, propose a named worker:

- Worker names should reflect the phase: `worker-docs`, `worker-api`, `worker-infra`, etc.
- Each worker maps to one parallel group (`[P1]`, `[P2]`) or one major sequential phase
- If the plan has only one phase, propose a single `worker-1`

Present the worker proposal alongside the reviewer confirmation:

```
Workers (derived from plan phases):
  worker-1 — [Phase 1 name]: [key tasks]
  worker-2 — [Phase 2 name]: [key tasks]
  [etc.]

Reviewers confirmed above.

Proceed to embed Team Structure into the plan?
```

**Hard gate**: Wait for final user confirmation before Step A4.

---

## Step A4: Embed Team Structure

After confirmation, write the following section at the END of the plan (before any existing
`## Notes` or `## Review` sections, or at the very end if those don't exist):

```markdown
## Team Structure

| Agent | Role | Mode | Responsibilities |
|-------|------|------|------------------|
| `worker-1` | [Phase 1 name] | plan (requires approval) | [Tasks from plan] |
| `worker-2` | [Phase 2 name] | plan (requires approval) | [Tasks from plan] |
| `security-reviewer` | Security Reviewer | general-purpose | OWASP, secrets, auth/authZ, PII |
| `devils-advocate` | Devil's Advocate | general-purpose | Assumptions, edge cases, failure modes |
| `architecture-reviewer` | Architecture Reviewer | general-purpose | Design patterns, separation of concerns, conventions |
[optional reviewers if confirmed...]

### Review Protocol
- Consensus threshold: **>= 9.0/10** from every reviewer
- Maximum **3 review iterations**
- Security/auth < 5.0 is a **blocking stop**
- Workers run in `plan` mode — submit proposals for approval before edits

### Reference Files
- `team-execution/skills/team-execution/references/reviewer-registry.md`
- `team-execution/skills/team-execution/references/review-criteria.md`
- `team-execution/skills/team-execution/references/consensus-protocol.md`
```

After writing the section, announce:

```
✅ Team Structure embedded in the plan.

This plan is now complete — it contains the implementation steps, the full team roster,
and the review protocol. Submitting for your approval now.
```

**Do NOT call TeamCreate here.**
**Do NOT spawn any agents here.**

---

## Step A5: Submit the Plan for Approval

Call `ExitPlanMode` now.

The plan is the single artifact the user approves. It contains:
- The implementation plan (phases, tasks, files)
- The team roster (workers + confirmed reviewers)
- The review protocol (consensus threshold, blocking rules)

When the user approves, your ONLY next action is TeamCreate. See Phase B constraints.

---

# Phase B: Orchestration Protocol (Claude follows this directly after TeamCreate)

> **Phase B is not invoked as a separate agent.** When Phase A calls ExitPlanMode and the
> user approves, Claude reads this section as its operating instructions and orchestrates
> directly.

---

## ⚠️ Critical Constraints — Phase B Entry

These rules apply the moment the user approves the plan and ExitPlanMode returns:

1. **Your ONLY permitted next action is TeamCreate.** No exceptions.
2. **Do NOT use the Agent tool for any implementation work.** All work goes through TeamCreate workers listed in the `## Team Structure` table.
3. **Do NOT spawn Explore, Plan, or general-purpose agents** for work that belongs to a worker.
4. **Do NOT read files, analyze code, or do any preparatory work** before calling TeamCreate.
5. **Parse the `## Team Structure` table → call TeamCreate → THEN proceed to B0.**

If you find yourself about to use the Agent tool to implement something, stop. Route that work to the appropriate worker instead.

---

## Step B0: Read the Plan's Team Structure

Parse the `## Team Structure` table to identify:

1. **Workers**: rows with `plan (requires approval)` in the Mode column — your implementation
   agents. Note each worker's name and assigned responsibilities.
2. **Reviewers**: rows with reviewer role names (Security Reviewer, Devil's Advocate, etc.) —
   your review agents. Note which are base vs optional.
3. **Reference files**: the paths listed under `### Reference Files` in the plan — load these
   before running the review cycle.

If the plan does NOT have a `## Team Structure` section, stop and tell the user:
```
The plan does not have a ## Team Structure section. Please run /team-execute to enter
plan mode and have the team-execution skill embed the team structure first.
```

---

## Step B1: Plan Approval Gate

Workers are spawned in `mode: "plan"` — they propose their implementation approach before
writing any code.

### B1a. Worker Proposes Plan

Each worker:
1. Reads its assigned tasks from the plan's `## Team Structure` table
2. Proposes an implementation approach (files to change, approach, edge cases considered)
3. Calls `ExitPlanMode` → sends `plan_approval_request`

### B1b. Review Each Worker Plan

Review each worker's plan against:
- Is it consistent with the original plan's intent?
- Is it appropriately scoped (not over-engineering)?
- Does it introduce any obvious security concerns?
- Does it contradict known architectural patterns in this codebase?

**Approve**: Worker proceeds to implementation.
**Reject**: Return specific feedback. Worker revises and re-submits.

### B1c. Parallelism

Workers with no dependencies can be approved and begin implementation in parallel.
Workers with dependencies wait for their upstream task to complete before beginning.

---

## Step B2: Execution

Workers implement their approved plans.

### B2a. Task Tracking

Workers update task status via `TaskUpdate`:
- `in_progress` when starting a task
- `completed` when done

Monitor the task list and:
- Unblock downstream workers when upstream tasks complete
- Surface blockers to the user if a worker is stuck
- Do NOT implement code directly — delegate to workers

### B2b. Parallel Execution

For plans with parallel work streams (marked `[P1]`, `[P2]`, etc. in the plan), workers
operate simultaneously. Coordinate dependencies between streams.

### B2c. Completion Signal

When all tasks are `completed`, signal readiness for Step B3.

---

## Step B3: Review Cycle

Read `team-execution/skills/team-execution/references/consensus-protocol.md`
for the full protocol. Summary below.

### B3a. Spawn Reviewers in Parallel

Spawn ALL confirmed reviewers simultaneously. Provide each with:
```
Plan context: [1-3 sentence summary of what was built]
Intended outcome: [what success looks like]
Changes made: [git diff or list of changed files]
Review rubrics: team-execution/skills/team-execution/references/review-criteria.md
```

### B3b. Collect and Display Scores

After all reviewers complete, display:

```
## Review Cycle [N] Results

| Reviewer | Score | Verdict | Issues |
|----------|-------|---------|--------|
| Devil's Advocate | X.X/10 | ACCEPT / NEEDS REVISION | N fixes |
| Security Reviewer | X.X/10 | ACCEPT / NEEDS REVISION | N fixes |
| Architecture Reviewer | X.X/10 | ACCEPT / NEEDS REVISION | N fixes |
[Optional reviewers...]

Consensus: [REACHED / NOT REACHED]
```

### B3c. Consensus Check

**If ALL >= 9.0** → consensus reached → proceed to Step B4.

**If any < 9.0**:
1. Consolidate fix requests from all reviewers scoring < 9.0 (deduplicate overlaps)
2. Route consolidated fixes to the responsible worker(s)
3. Workers implement fixes
4. Re-run Step B3a for ONLY the reviewers that scored < 9.0
   (reviewers that already ACCEPTED do not re-review)
5. Increment cycle counter

### B3d. Cycle Cap

After **3 iterations**: proceed to Step B4 regardless of scores. Document final scores and
any unresolved fix requests in the completion report.

### B3e. Blocking Issues

If any security or auth dimension scores < 5.0:
- Immediately flag to user
- Do not wait for cycle to complete
- Treat as a hard stop until that dimension reaches >= 7.0

---

## Step B4: Completion

### B4a. Final Report

Present the completion summary:

```
## Team Execution Complete

Plan: [Plan name]
Date: [Date]
Iterations: [N] review cycle(s)

### Final Review Scores
| Reviewer | Score | Status |
|----------|-------|--------|
| Devil's Advocate | X.X/10 | ACCEPT |
| Security Reviewer | X.X/10 | ACCEPT |
| Architecture Reviewer | X.X/10 | ACCEPT |
[Optional reviewers...]

Consensus: [REACHED / NOT REACHED after 3 cycles]

### Unresolved Issues
[List if consensus not reached, otherwise "None"]

### Changes Made
[Summary of files changed and what was implemented]
```

### B4b. Commit (if applicable)

If the plan involved code changes and commits are appropriate, prompt:
```
Ready to commit. Suggested message:
  [type(scope): description based on plan]

Proceed with commit, or would you like to adjust the message?
```

### B4c. Shutdown Team

Gracefully shut down all teammates:
1. Send `shutdown_request` to each worker
2. Send `shutdown_request` to each reviewer

---

## Error Handling

**Worker plan rejected 3+ times**: Escalate to user — the worker may need clarification on scope.

**Reviewer cannot access git diff**: Ask user to provide the changes as a summary or file list.

**Architecture context not found**: Architecture Reviewer scores Architecture Documentation Coverage
as N/A (8.0 default), notes that no ADR/architecture directory was found.

**Worker stuck / blocked**: Notify user with the blocker details. Do not spin.

**Review cycle > 3 iterations**: Proceed with best version, document scores. Never loop indefinitely.

---

## Quick Reference: File Paths

```
team-execution/
├── .claude-plugin/plugin.json
├── skills/team-execution/
│   ├── SKILL.md                          ← this file (Phase A + Phase B)
│   └── references/
│       ├── reviewer-registry.md          ← keyword triggers, base/optional reviewer list
│       ├── review-criteria.md            ← scoring rubrics for all reviewer types
│       └── consensus-protocol.md         ← 3-iteration loop, re-review scoping
├── agents/
│   ├── devils-advocate-reviewer.md       ← base (red)
│   ├── security-reviewer.md              ← base (orange)
│   ├── architecture-reviewer.md          ← base (purple)
│   ├── infra-reviewer.md                 ← optional (blue)
│   ├── api-reviewer.md                   ← optional (green)
│   ├── testing-reviewer.md               ← optional (yellow)
│   ├── code-quality-reviewer.md          ← optional (cyan)
│   ├── privacy-reviewer.md               ← optional (pink)
│   ├── clarity-reviewer.md               ← optional (teal)
│   └── ai-usefulness-reviewer.md         ← optional (gold)
└── commands/team-execute.md              ← /team-execute slash command
```
