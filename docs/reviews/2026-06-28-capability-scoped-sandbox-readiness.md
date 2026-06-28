---
date: 2026-06-28
target: docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review)
verdict: READY
blocked: false
---

# Readiness Review — Capability-Scoped Agent Sandbox

## Verdict

**READY for `/plan`** after a heavy fix pass — the heaviest of this campaign. As first written the doc
was not planning-ready: all three engines raised `P0`s, and codex (repo access) put it bluntly — "not
planning-ready because they defer the backend enforceability decision that determines whether the
feature exists at all." Seventeen evidence-backed fixes were applied in place. No `P0`/`P1` remains
unaddressed: capability is now two orthogonal axes (not one enum), enforcement is tool-set omission plus
a universal worktree floor (not an impossible per-command hook), the threat model is scoped to accidental
clobber, degrade is halt-not-downgrade, and the per-backend enforceability matrix is recorded as the
first `/plan` task. The feature's existence no longer hinges on per-backend tool-filtering: the
worktree floor (R7) is saga-side and works everywhere, so the deferred matrix detail is a planning
agenda item, not vapor.

## Method

Reviewed as a requirements artifact (readiness-skeptic pass). Adversarial depth came from a
**three-engine panel as gated generators under Claude-side verification** — every finding verified
against the doc or repo source before adoption:

- **Codex / gpt-5.5** at `xhigh`, read-only, repo access (verified file:line claims + per-backend
  feasibility directly).
- **agy Gemini 3.1 Pro (High)**, hermetic (doc inlined).
- **agy Gemini 3.5 Flash (High)**, hermetic (doc inlined).

The panel earned its keep on every axis. **Three-way convergence** (codex + Pro + Flash) on the
two-axes split — codex even cited R11's "one envelope, two subrecords" as the precedent. **Independent
convergence** of Pro and Flash on the same decomposition names. Codex's repo access alone caught that
the cc-workflows emitter is unwired, team-execution has no enforcer, and a prior `delegate-agent`
ideation already mapped the external-CLI mechanics. Claude-side verification added the load-bearing
piece — the `PreToolUse` hook cannot see the agent's profile (`pre_push_gate_hook.py:116-128`) — and
the worktree-as-universal-floor reframe that resolved codex's existential `P0`. One Flash `P1` (flip to
least-privilege-default) was **declined** — the operator chose targeted posture — keeping only its
kernel (the verify-class default).

## Applied fixes

All evidence-backed; the doc was edited in place.

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | Capability split into two orthogonal axes (`mutation_policy` × `workspace_isolation`); profiles are compositions (D1, R1, R4-R5) | Codex P1d + Pro P1 + Flash P1 (3-way) | different abstraction layers; R11 `:87-90` precedent |
| 2 | Enforcement reframed to tool-set omission + worktree, not command interception (D4, R6) | Pro P0 + Flash P0 + Codex P2b + Claude C1 | hook stdin is `tool_name`+`tool_input` only (`pre_push_gate_hook.py:116-128`); shell side-effects unparseable |
| 3 | Worktree isolation established as the universal enforcement floor (D3, R7) | Claude (resolves Codex P0) | `outcome_worktrees.py` is saga-side; contains destructive git regardless of backend |
| 4 | Threat model scoped to accidental clobber + least-privilege, not adversarial (D2, R9) | Claude (resolves Pro/Flash "bypassable" P0) | adversarial escape needs the deferred OS sandbox |
| 5 | Per-backend enforceability matrix added as the first `/plan` task (R8, Outstanding) | Codex P0a/P0b/P1a/P1b | emitter passes only label/model/effort (`execution_spec.py:488-503`); `team_emitter.py:103-110` bypassPermissions |
| 6 | Degrade is halt-never-downgrade; pre-dispatch enforceability probes (R10) | Flash P2 + Codex P1g + Pro P1 | downgrade adds privilege; existing degrade checks availability not enforceability (`outcome_dispatcher.py:235-251`) |
| 7 | Owned-worktree harvest defined (commit-in-worktree → merge path) (R12, D6) | Flash P1 + Codex P1e + Claude C4 | `outcome_merge.py`, `outcome.py:465-506` |
| 8 | Self-clobber inside the worktree closed (commit before harvest) (R13) | Pro P2 | commit-before-verify discipline recursing |
| 9 | External-engine adapter required (codex/agy `--cd`/`--sandbox`/`--add-dir` + metadata redirect) (R14) | Codex P1f + Claude C3 | `delegate-agent-plugin-ideation.md:71-94` (verified) |
| 10 | Spawn-site inventory required; `/investigate` + `/resume` added (R15) | Codex P1h + Flash P1 kernel | `investigate/SKILL.md:211-216`, `resume/SKILL.md:224-228` |
| 11 | Dead-wiring guard: named enforcer per backend + required destructive-git-blocked integration test (R16, AE1) | Codex P1c | capability field with no consumer accumulates silently |
| 12 | Verify/review class defaults read-only so new spawns inherit (D5, R17) | Flash P1 kernel | targeted posture's coverage gap |
| 13 | D1↔R10 contradiction resolved (tool-omission, not blocklist) (D4) | Flash P2 | "not a blocklist" vs command-deny |
| 14 | "six reviewers" corrected to the reviewer/validator taxonomy | Codex P2a | `reviewer-registry.md`, `validator-registry.md` (verified) |
| 15 | cc-workflows feasibility stated precisely: capability exists (`agent()` `agentType`), emitter unwired | Codex P0b + Claude (tool doc) | `Explore` precedent; emitter at `:488-503` |
| 16 | R11-manifest coherence as the pre-hoc dual (R18) | Claude | R11 records what-touched; R14 declares what-may-touch |
| 17 | No-escalation safety (capability only narrows) (R19) | Claude | mirrors S-4 R23 evidence-only |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P0 | Backend enforceability deferred / "no blockers" false | Codex | Fixed (R8 + worktree floor makes it feasible; matrix = first /plan task) |
| P0 | Read-only + Bash via hook is bypassable | Pro + Flash + Codex(P2b) | Fixed (D2 threat model + D4 tool-omission + R7 worktree floor) |
| P0 | cc-workflows tool restriction unwired in emitter | Codex | Fixed (R8 — capability exists, wiring in scope) |
| P1 | Two faces forced into one enum | Codex + Pro + Flash | Fixed (D1 two axes) |
| P1 | team-execution has no profile enforcer | Codex | Fixed (R8 — worktree-floor-only until built) |
| P1 | inline spawn is prompt-only | Codex | Fixed (R8 — agentType+tools precedent) |
| P1 | Capability field dead-wiring | Codex | Fixed (R16 enforcer + integration test) |
| P1 | Harvest underspecified | Flash + Codex + Claude | Fixed (R12) |
| P1 | External-engine mutation hand-waved | Codex + Claude | Fixed (R14 adapter) |
| P1 | Degrade wrong-direction | Flash + Codex + Pro | Fixed (R10 halt) |
| P1 | Targeted coverage misses spawn sites | Codex + Flash | Fixed (R15 inventory + R17 default) |
| P2 | Self-clobber inside worktree | Pro | Fixed (R13) |
| P2 | D1↔R10 contradiction | Flash | Fixed (D4) |
| P2 | "six reviewers" inaccurate | Codex | Fixed (taxonomy) |
| P3 | Core citations resolve (clobber/no-field/per-child-worktree valid) | Codex | Confirmed — kept as premises |
| — | Invert to least-privilege-default | Flash | **Declined** — operator chose targeted; kept the verify-class-default kernel (R17) |
| — | Remove Bash entirely / OS-sandbox-or-bust | Pro + Flash | **Refined** — worktree floor contains accidental destructive git without removing Bash (verifiers need tests) or an OS sandbox, given the accidental threat model (D2) |

## Residual risk

- **team-execution tool-omission is unbuilt** — that backend is worktree-floor-only until a per-leaf
  enforcer exists. The floor still contains the clobber there; only the defense-in-depth tool layer is
  missing. The matrix's one genuine unknown, with a safe fallback.
- **cc-workflows `agentType` tool-enforcement** is a capability the Workflow tool exposes, but it is
  unproven inside saga's emitted workflows until the emitter is wired and the AE1 integration test runs.
- **External-engine confinement is cwd/flag-based** (the accidental threat model) — a determined engine
  escapes via absolute paths. Adversarial containment is the deferred OS sandbox.
- **Per-leaf worktree granularity** (vs today's per-child-outcome) is unproven until `/plan` extends
  `outcome_worktrees.py`.

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`), same pipeline as S-1 (#275) … R11 (#285). Recipient action: `/plan`, whose
first task is filling the per-backend enforceability matrix (R8).
