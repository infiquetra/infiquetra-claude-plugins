# team-execution

Two-phase plan execution with automatic multi-reviewer consensus workflow.

**Phase A** runs during plan mode: reads the plan, derives workers from phases, detects optional
reviewers by keyword, and embeds a `## Team Structure` section into the plan.

**Phase B** runs after plan exit: a global CLAUDE.md rule sees `## Team Structure` and fires
TeamCreate automatically. Claude orchestrates workers through plan approval gates, parallel
execution, and a max-3-iteration review cycle with >= 9.0 consensus threshold.

---

## Quick Start

```
/team-execute
```

Or describe what you want to build — Claude enters plan mode, the skill embeds the Team
Structure, and execution begins automatically when you exit plan mode.

If you already have a written plan:
```
/team-execute [paste plan here or provide file path]
```

---

## Setup: CLAUDE.md Handoff Rule

This plugin requires one rule in your global `~/.claude/CLAUDE.md` to enable the automatic
Phase A → Phase B handoff:

```markdown
## Team Execution Auto-Handoff

When a plan exits plan mode and contains an explicit **## Team Structure** section with named
agents, skip all skill invocations and go directly to TeamCreate. Parse the Team Structure
table for workers and reviewers, then follow the Phase B orchestration protocol from
`team-execution/skills/team-execution/SKILL.md`.
```

Without this rule, Phase A will embed the Team Structure but execution won't start automatically
on plan exit.

---

## How It Works

```
Phase A: During Plan Mode
  → /team-execute enters plan mode
  → Skill reads plan, classifies type (code/docs/mixed)
  → Triage check: trivial config? offer to skip
  → Detect optional reviewers from plan keywords
  → Derive workers from plan phases
  → User confirms team lineup
  → Skill embeds ## Team Structure into the plan
  → User exits plan mode

                    ↓ CLAUDE.md handoff ↓

Phase B: After Plan Exit (automatic)
  → CLAUDE.md rule sees ## Team Structure → fires TeamCreate
  → Claude parses Team Structure, starts 4-step protocol:

  Step 1: Worker Kickoff
    → Workers execute (bypassPermissions — no user prompts)
    → Claude monitors progress via messaging
    → Redirects if a worker goes off-track

  Step 2: Execution
    → Workers implement in parallel where tasks allow
    → Claude monitors + unblocks dependencies

  Step 3: Review Cycle (max 3 iterations)
    → All reviewers score in parallel (5 dimensions each, 0-10)
    → If all >= 9.0 → consensus → done
    → Else: fixes routed to workers → only failed reviewers re-run

  Step 4: Completion
    → Final score report
    → Commit if needed
    → Team shutdown
```

---

## The CLAUDE.md Handoff Mechanism

The transition from Phase A to Phase B works through the rule in your global `~/.claude/CLAUDE.md`.

When the plan exits plan mode with a `## Team Structure` section embedded, this rule fires
automatically — no explicit `/team-execute` needed post-planning. This is why the skill
must embed the section BEFORE ExitPlanMode, not after.

---

## What You Get

### Always Included

| Reviewer | Color | Focus |
|----------|-------|-------|
| Devil's Advocate | 🔴 Red | Assumptions, edge cases, failure modes, scope creep |
| Security Reviewer | 🟠 Orange | OWASP Top 10, secrets, auth/authZ, PII |
| Architecture Reviewer | 🟣 Purple | Design patterns, separation of concerns, convention adherence |

### Automatically Suggested (by keyword detection)

| Trigger Keywords | Reviewer |
|-----------------|----------|
| CDK, Lambda, DynamoDB, S3, IAM, KMS, AWS | 🔵 Infra Reviewer |
| API, endpoint, REST, OpenAPI, versioning | 🟢 API Reviewer |
| pytest, test, coverage, mock, fixture | 🟡 Testing Reviewer |
| refactor, DRY, SOLID, complexity, patterns | 🩵 Code Quality Reviewer |
| PII, GDPR, consent, retention, privacy | 🩷 Privacy Reviewer |
| docs, README, specification, guide, runbook | 🩵 Clarity Reviewer |
| SKILL.md, GitHub issue, acceptance criteria | 🟡 AI Usefulness Reviewer |

---

## Team Structure Format

The canonical format embedded into plans:

```markdown
## Team Structure

| Agent | Role | Mode | Responsibilities |
|-------|------|------|------------------|
| `worker-1` | [Phase 1 name] | bypassPermissions | [Tasks from plan] |
| `worker-2` | [Phase 2 name] | bypassPermissions | [Tasks from plan] |
| `security-reviewer` | Security Reviewer | general-purpose | OWASP, secrets, auth/authZ, PII |
| `devils-advocate` | Devil's Advocate | general-purpose | Assumptions, edge cases, failure modes |
| `architecture-reviewer` | Architecture Reviewer | general-purpose | Design patterns, separation of concerns, conventions |

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

Note: No `lead` row — Claude orchestrates directly.

---

## Consensus Protocol

All reviewers must score **>= 9.0/10** to reach consensus.

If consensus is not reached, fix requests are consolidated and routed to workers. Only reviewers
that scored < 9.0 re-run in the next iteration. Maximum 3 iterations.

After 3 cycles, execution proceeds with the best available version and documents any
unresolved issues.

**Hard stop**: Any security or auth dimension scoring < 5.0 is treated as a blocking issue
and flagged immediately.

---

## Triage Escape Hatch

For trivial changes (single config file, no security surface, < 3 files, no docs content),
Phase A offers:

- **A)** Skip team planning entirely (recommended for trivial changes)
- **B)** Full review team anyway
- **C)** Devil's Advocate only (lightweight check)

Docs-only plans **do not qualify** for the escape hatch — documentation is specifications
for code and deserves full review.

---

## Architecture Reviewer Context Loading

The Architecture Reviewer searches for project-local architecture docs:

```
1. ./docs/adrs/
2. ./docs/architecture/
3. ./architecture-decisions/
4. ./architecture/
5. ./docs/decisions/
```

It keyword-matches the plan against any docs found, then loads only relevant ones. If no
architecture docs exist, it scores based on observable codebase patterns.

---

## Plugin Structure

```
team-execution/
├── .claude-plugin/plugin.json
├── skills/team-execution/
│   ├── SKILL.md                    # Phase A (plan mode) + Phase B (orchestration protocol)
│   └── references/
│       ├── reviewer-registry.md    # Keyword triggers + reviewer list
│       ├── review-criteria.md      # Scoring rubrics for all reviewers
│       └── consensus-protocol.md  # 3-iteration loop, re-review scoping
├── agents/
│   ├── devils-advocate-reviewer.md # Base (red)
│   ├── security-reviewer.md        # Base (orange)
│   ├── architecture-reviewer.md    # Base (purple)
│   ├── infra-reviewer.md           # Optional (blue)
│   ├── api-reviewer.md             # Optional (green)
│   ├── testing-reviewer.md         # Optional (yellow)
│   ├── code-quality-reviewer.md    # Optional (cyan)
│   ├── privacy-reviewer.md         # Optional (pink)
│   ├── clarity-reviewer.md         # Optional (teal)
│   └── ai-usefulness-reviewer.md   # Optional (gold)
├── commands/team-execute.md        # /team-execute slash command
├── README.md
└── CHANGELOG.md
```
