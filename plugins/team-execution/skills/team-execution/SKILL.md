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
  Use this skill PROACTIVELY when in plan mode and ANY of these are true:
  - The plan has 3+ steps, touches 3+ files, or involves docs/specs
  - The plan involves multiple parallel work streams
  - The user says: "agent team", "agentic team", "team of agents", "use agents",
    "set up a team", "use team-execution", "who should review this?", "what team
    do I need?", "agentic approach", "run this with agents"
  - The user asks for code review as part of a plan

  When auto-suggesting on a non-trivial plan, ask:
    "This plan has [N] steps across [M] files. Would you like to set up an agent
     team with workers and reviewers?
       A) Yes, run team planning
       B) No, I'll handle this myself"

  Do NOT use when:
  - The plan already has a ## Team Structure section (TeamCreate will fire automatically)
  - The change is trivially simple (single file, no security surface, < 3 steps)
  - The user has already declined team planning for this plan in this session
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

## Step A0: Environment Pre-flight

Before doing anything else, validate that the user's environment is ready for team execution.
Run these checks silently using bash commands. Only show output if something needs attention.

### A0a. CLAUDE.md Auto-Handoff Rule (always checked)

Run:
```bash
grep -q "Team Execution Auto-Handoff" ~/.claude/CLAUDE.md 2>/dev/null && echo "FOUND" || echo "MISSING"
```

If **MISSING**: this is critical — the skill will not work properly without it. Show:
```
⚠️  CLAUDE.md auto-handoff rule not found.

The team-execution skill requires a rule in ~/.claude/CLAUDE.md to trigger TeamCreate
automatically after plan approval. Without it, the handoff from planning to execution
will not fire.

Run /team-setup to install it, or add this to ~/.claude/CLAUDE.md manually:

  ## Team Execution Auto-Handoff

  When a plan exits plan mode and contains an explicit ## Team Structure section:
  1. Your ONLY next action is TeamCreate — no exceptions
  2. Do NOT use the Agent tool for implementation work
  3. Parse the Team Structure table for workers and reviewers
  4. Call TeamCreate immediately
  5. Then follow Phase B orchestration from team-execution SKILL.md

  This rule takes priority over any other agent-spawning behavior.
```

Proceed to A1 after showing the warning — do not block.

### A0b. tmux Environment (skipped if opted out)

First check if the user has dismissed tmux setup:
```bash
cat ~/.claude/team-execution.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('DISMISSED' if d.get('tmux_setup_dismissed') else 'CHECK')" 2>/dev/null || echo "CHECK"
```

If **DISMISSED**: skip all tmux checks silently. Proceed to A1.

If **CHECK**: run these checks and collect results:
```bash
# 1. tmux installed?
command -v tmux >/dev/null 2>&1 && echo "tmux:OK" || echo "tmux:MISSING"

# 2. Running inside tmux?
[ -n "$TMUX" ] && echo "session:OK" || echo "session:MISSING"

# 3. tmux.conf exists?
[ -f ~/.tmux.conf ] && echo "config:OK" || echo "config:MISSING"

# 4. Overflow script installed?
[ -x ~/.config/tmux/agent-overflow.sh ] && echo "overflow:OK" || echo "overflow:MISSING"

# 5. Claude settings: teammateMode set?
cat ~/.claude.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('teammateMode','unset'); print(f'teammateMode:{m}')" 2>/dev/null || echo "teammateMode:unset"

# 6. Claude settings: agent teams feature enabled?
cat ~/.claude/settings.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); v=d.get('env',{}).get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS','unset'); print(f'agentTeams:{v}')" 2>/dev/null || echo "agentTeams:unset"
```

If **all OK** (tmux installed, in session, config present, overflow installed, teammateMode is "tmux" or "auto", agentTeams is "1"): proceed silently to A1.

If **any MISSING or misconfigured**: show the results table and offer options:
```
tmux environment check:
  ✅ tmux installed          (or ⚠️  tmux not installed)
  ✅ Running in tmux session (or ⚠️  Not in tmux session)
  ✅ ~/.tmux.conf present    (or ⚠️  ~/.tmux.conf not found)
  ✅ Overflow script ready   (or ⚠️  agent-overflow.sh not installed)
  ✅ teammateMode: tmux      (or ⚠️  teammateMode not set — agents won't use split panes)
  ✅ Agent teams enabled     (or ⚠️  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS not set)

Options:
  A) Run /team-setup to configure tmux for agent teams
  B) Skip tmux setup — I have my own terminal config
  C) Don't ask again — dismiss tmux checks permanently
```

If user picks **B**: proceed to A1.
If user picks **C**: write the dismissal file and proceed:
```bash
mkdir -p ~/.claude && echo '{"tmux_setup_dismissed": true}' > ~/.claude/team-execution.json
```
If user picks **A**: tell them to run `/team-setup` after this session, then proceed to A1.

---

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
| `worker-1` | [Phase 1 name] | bypassPermissions | [Tasks from plan] |
| `worker-2` | [Phase 2 name] | bypassPermissions | [Tasks from plan] |
| `security-reviewer` | Security Reviewer | general-purpose | OWASP, secrets, auth/authZ, PII |
| `devils-advocate` | Devil's Advocate | general-purpose | Assumptions, edge cases, failure modes |
| `architecture-reviewer` | Architecture Reviewer | general-purpose | Design patterns, separation of concerns, conventions |
[optional reviewers if confirmed...]

### Review Protocol
- Consensus threshold: **>= 9.0/10** from every reviewer
- Maximum **3 review iterations**
- Security/auth < 5.0 is a **blocking stop**
- Workers run in `bypassPermissions` mode — no permission prompts, quality enforced by review cycle

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

# Phase B: Orchestration Protocol (Claude/Gemini acts as the Team Lead)

> **Phase B is not invoked as a separate agent.** When Phase A calls ExitPlanMode and the
> user approves, Claude/Gemini reads this section as its operating instructions and acts as the **Team Lead** to orchestrate directly.
> 
> **Consensus Role Definition**:
> - The **Team Lead** (main orchestrator agent) is responsible for the overall execution, routing fixes, and verifying changes.
> - The **Reviewers** (subagents) evaluate implementation quality.
> - **Consensus** is strictly a mutual agreement between the **Team Lead** and the **Reviewers** (max 3 rounds, achieving a score of >= 9.0/10).
> - The **Human User** is a passive stakeholder who is **not** part of the consensus agreement loop or review-revise iterations. Do not prompt the user for approvals or consensus sign-offs between cycles.

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

1. **Workers**: rows with `bypassPermissions` in the Mode column — your implementation
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

## Step B1: Worker Kickoff

Workers are spawned in `mode: "bypassPermissions"` — they have full permissions and begin
implementing immediately. No permission prompts reach the user; quality is enforced by the
review cycle in Step B3.

### B1a. Worker Start

Each worker:
1. Reads its assigned tasks from the plan's `## Team Structure` table
2. Reads relevant codebase context (existing files, patterns, conventions)
3. Implements the assigned work directly
4. Sends a brief summary to the orchestrator via SendMessage when complete (or if blocked)

### B1b. Orchestrator Oversight

Monitor worker progress via team messages and task status updates. If a worker's approach
seems off-track, redirect via SendMessage before the work goes too far. Workers should
acknowledge and adjust.

**No hard approval gate** — the user approved the full plan in Phase A. Workers execute
their assigned scope. The review cycle (Step B3) is the quality gate.

### B1c. Parallelism

Workers with no dependencies begin simultaneously. Workers with dependencies wait for
their upstream tasks to reach `completed` status before starting.

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

## Step B3: Review Cycle (Team Lead & Reviewer Consensus)

Read `team-execution/skills/team-execution/references/consensus-protocol.md`
for the full protocol. Summary below:
- The **Team Lead** coordinates the review-revise cycles entirely autonomously.
- Do not request the human user's approval or validation between cycles. 
- Iteratively apply fixes and re-run reviews until consensus (score >= 9.0/10) is achieved or the 3-cycle cap is met.

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
