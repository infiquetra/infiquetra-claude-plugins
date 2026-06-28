---
title: capability: capability-scoped agent sandbox — read-only-verify + sandboxed-mutate via worktree isolation
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: capability-scoped agent sandbox — read-only-verify + sandboxed-mutate via worktree isolation

### Objective

Give a delegated leaf a declared capability along two axes — `mutation_policy` (read-only | read-write)
× `workspace_isolation` (ambient | disposable-worktree | owned-worktree) — composed into two profiles:
`read-only-verify` (closes the verify-agent `git checkout` clobber) and `sandboxed-mutate`
(worktree-owned mutation, lifting the evidence-only ceiling S-4 #283 R23 and R11 #285 R21 wait on).
Worktree isolation is the universal enforcement floor; tool-set omission layers on where a backend
supports it.

### Intent

The clobber is recorded (`docs/engineering-journal/LEARNINGS.md:88-104`): a verify agent ran
`git checkout` on uncommitted work and destroyed it, because verifiers spawn with full Bash + write and
"read-only" is prose only (`team_emitter.py:103-110` bypassPermissions; `execution_spec.py:488-503`
emits no tool restriction). This makes capability a declared, structurally-enforced property — a third
tier beside model/effort — so verify/review agents structurally cannot mutate the real tree, and so
external/delegated workers can mutate safely (in an owned worktree) instead of being capped at
evidence-only. Threat model: accidental clobber + least-privilege hygiene, not adversarial escape.

### Out-of-scope / non-goals

- Adversarial / OS-level sandbox (containers, seccomp, escape-proof) — R14 is accidental-clobber +
  least-privilege only.
- Least-privilege-default for all leaves — v1 keeps the default unchanged; only the verify/review class
  defaults read-only.
- A `path`/`network` capability axis — v1 is mutation + isolation.
- Building S-4/R11's consumers — R14 provides `sandboxed-mutate`; those issues lift their own ceilings
  when they build.
- Exact per-backend enforcement primitives + harvest/adapter mechanism detail → `/plan`.

### Files expected to change

Exact files are a `/plan` decision; the expected surfaces are:

- `plugins/saga/scripts/execution_spec.py` — capability fields on `Unit`; verify-panel emitter wires the read-only `agentType`
- `plugins/saga/scripts/outcome_spec.py` — capability fields on `Node`
- `plugins/saga/scripts/outcome_dispatcher.py` — pre-dispatch enforceability probes; halt-not-downgrade
- `plugins/saga/scripts/outcome_worktrees.py` — per-leaf disposable/owned worktree extension
- `plugins/saga/skills/code-review/`, `plugins/saga/skills/qa/`, `plugins/saga/skills/investigate/`, `plugins/saga/skills/resume/` — attach profiles at spawn sites
- `tests/` — capability contract + the clobber-contained integration test

### Tests to add or update

- `tests/` — clobber-contained integration test: a `read-only-verify` verifier attempts `git checkout <tracked>` → real work intact
- two-axis contract + profile composition (`read-only-verify`, `sandboxed-mutate`)
- halt-not-downgrade: a backend that cannot enforce a restrictive capability HALTS
- sandboxed-mutate harvest: edits land in an owned worktree, merged via the existing path
- spawn-site inventory guard: every verify/review spawn carries a profile
- no-escalation: a capability only narrows, never grants

### Context library links

- `docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md` — requirements doc
- `docs/reviews/2026-06-28-capability-scoped-sandbox-readiness.md` — readiness review (verdict READY)
- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — survivor R14
- `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md` — external-CLI flag prior art (`--cd`/`--sandbox`/`--add-dir`)
- #283 (S-4 R23) and #285 (R11 R21) — the two evidence-only ceilings this lifts

### Acceptance criteria

Each criterion is a check that must pass once built:

- [ ] read-only-verify contains an accidental `git checkout` — `uv run pytest tests/ -k clobber_contained` → pass (real work intact)
- [ ] Two-axis capability composes into both profiles — `uv run pytest tests/ -k capability_axes` → pass
- [ ] Unenforceable restrictive capability HALTS, never downgrades — `uv run pytest tests/ -k enforce_halt` → pass
- [ ] sandboxed-mutate edits land in an owned worktree, harvested via merge — `uv run pytest tests/ -k sandboxed_harvest` → pass
- [ ] No verify/review spawn site runs unprofiled — `uv run pytest tests/ -k spawn_site_inventory` → pass
- [ ] Lint, types, security clean — `uv run ruff check . && uv run mypy plugins/ && uv run bandit -r plugins/` → exit 0

### Verification

```bash
# Full local gate (mirrors CI)
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/
uv run bandit -r plugins/ -q
# Capability-specific suites
uv run pytest tests/ -k "capability or clobber or worktree or enforce" -v
```

Expected: all green; the capability / clobber / worktree suites pass.

---
date: 2026-06-28
topic: capability-scoped-sandbox
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md (survivor R14 — capability-scoped agent sandboxing)
---

# Capability-Scoped Agent Sandbox

## Summary

Give a delegated leaf a declared **capability** along two orthogonal axes — a `mutation_policy`
(read-only | read-write) and a `workspace_isolation` (ambient | disposable-worktree | owned-worktree).
Two named profiles are compositions of those axes: `read-only-verify` (read-only × disposable-worktree,
closing the verify-agent clobber) and `sandboxed-mutate` (read-write × owned-worktree, lifting the
evidence-only ceiling S-4 R23 and R11 R21 wait on). Worktree isolation is the universal enforcement
floor — a saga-side wrapper that contains accidental destructive git on every backend — with tool-set
omission layered on where a backend supports it. The threat model is accidental clobber and
least-privilege hygiene, not adversarial escape.

## Problem Frame

The motivating failure is recorded. During the OutcomeOrchestrator U4 build a verify-lens agent ran
`git checkout <path>` against the uncommitted working tree and **permanently destroyed** the U4 edits —
never in a git object, so unrecoverable (`docs/engineering-journal/LEARNINGS.md:88-104`,
`{#verify-agent-git-checkout-clobber}`; `docs/work-sessions/2026-06-25-outcome-orchestration.md:314`).
The mechanism, quoted: "Workflow/subagent verifiers have full Bash + write access. A `git checkout
<path>` / `git restore` on a tracked file silently discards uncommitted edits ... a single agent
keystroke can destroy it."

The substrate is max-privilege, and "read-only" is prose. Workers are emitted with `bypassPermissions`
(`plugins/saga/scripts/team_emitter.py:103-110`). The refute-N verify panel emits `agent()` calls that
pass only `label`/`model`/`effort` — no tool restriction (`plugins/saga/scripts/execution_spec.py:488-503`).
`/code-review` lenses spawn as generic agents (`plugins/saga/skills/code-review/SKILL.md:164-166`), and
"strictly read-only over the diff" (`:34-38`) / "operationally read-only"
(`code-review/references/validator.md:52`) are instructions to the model, not enforced. No capability
field exists on `Unit` (`execution_spec.py:163-249`), `Node` (`outcome_spec.py:108-144`), or dispatch
(`outcome_dispatcher.py:100-133`) — dispatch is capability-blind.

There is downstream debt. Two filed issues made delegated mutation *wait* on "the ideation-R14 sandbox":
S-4 R23 (external workers are evidence-only "until that profile exists") and R11 R21 (manifests for
mutating workers "wait on the read-only sandbox"). The ideation promoted only the narrow read-only face
("small and independent"); the two issues re-expanded "ideation R14" to also cover safe mutation. Until
this capability ships both faces, those issues stay evidence-only.

Worktree isolation already exists as the substrate: `outcome_worktrees.py` gives real git-tree
separation, per child-outcome (not per-leaf), with no tool boundary inside
(`outcome_worktrees.py:1-8,51-57,91-93`), degrading to safe when git is unreadable (`:423-479`).

## Key Decisions

- **D1. Capability is two orthogonal axes, not one enum.** `mutation_policy` (read-only | read-write) is
  a tool-permission concern; `workspace_isolation` (ambient | disposable-worktree | owned-worktree) is a
  filesystem-routing concern — different layers. Named profiles are compositions: `read-only-verify` =
  read-only × disposable-worktree; `sandboxed-mutate` = read-write × owned-worktree. (This mirrors R11's
  "one envelope, two subrecords" resolution — `docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md:87-90`.)

- **D2. Threat model: accidental clobber + least-privilege hygiene, not adversarial escape.** A
  determined agent can defeat tool limits (shell redirects, subprocesses, absolute paths); adversarial
  containment needs the OS-level sandbox this capability explicitly defers. R14 prevents the *accidental*
  `git checkout` clobber and enforces least-privilege defaults — it is not an adversarial sandbox.

- **D3. Worktree isolation is the universal enforcement floor.** Running a delegated agent in a
  disposable or owned worktree (a saga-side wrapper that sets the agent's working directory) contains
  accidental destructive git on *every* backend, independent of whether that backend can restrict an
  agent's tool set. Tool-set omission is an additional layer where the backend supports it. (Extends
  `outcome_worktrees.py`.)

- **D4. Enforcement is tool-set omission at spawn + worktree isolation — not command-string
  interception.** A `PreToolUse` hook cannot see the calling agent's capability profile (its stdin is
  only `{tool_name, tool_input}` — `plugins/saga/hooks/pre_push_gate_hook.py:116-128`), and reliably
  parsing arbitrary shell for side-effects is infeasible. So a command-deny backstop is neither
  sufficient nor primary; it is at most defense-in-depth.

- **D5. Targeted attachment, default unchanged — but the verify/review class defaults to read-only.**
  The global default is `full` (today's behavior); v1 does not flip it or require every leaf to declare.
  But the verify/review *class* of spawns defaults to `read-only-verify`, so new spawns in that class
  inherit it rather than silently running full. Least-privilege-default for all leaves is out of v1.

- **D6. Safe mutation is an owned worktree plus a defined harvest.** `sandboxed-mutate` edits land in a
  worktree the leaf owns and are harvested back by committing in the worktree and merging its branch —
  not by copying files over the live tree. (Extends `outcome_worktrees.py` + `outcome_merge.py`.)

- **D7. R14 is the pre-hoc dual of R11.** R11 (#285) records "what I touched"; R14 declares "what I may
  touch." A leaf's capability is a field R11's manifest records as attribution. Coherence, not a build
  dependency.

- **D8. Cashing the IOUs is in scope.** v1 provides `sandboxed-mutate` for external/delegated workers —
  what S-4 R23 and R11 R21 named — via owned worktrees plus a per-engine adapter. It does not build
  their consumers (sequencing → `/plan`).

## Actors

- A1. **The leaf/agent** — carries a declared capability (two axes), or the default `full`
  (ambient × read-write).
- A2. **The spawn site** — verify-panel emitter, `/code-review` lens spawner, team-execution reviewer
  config, external/delegated-worker wrapper. Attaches the capability and binds enforcement.
- A3. **The worktree wrapper** — the saga-side enforcement floor (D3): provisions the worktree, runs the
  agent with its working directory set there, harvests or discards.
- A4. **The per-engine adapter** — for external CLIs (codex/agy), maps `sandboxed-mutate` onto the
  engine's own flags (`--cd`/`--sandbox`/`--add-dir`) and redirects engine metadata.

## Requirements

### Capability contract (two axes)

- R1. Capability is two orthogonal declared axes: `mutation_policy` (read-only | read-write) and
  `workspace_isolation` (ambient | disposable-worktree | owned-worktree). (Field names/storage → `/plan`.)
- R2. Both axes ride the same `Unit`/`Node` as the model/effort tier and are threaded through dispatch to
  the spawn site. `Unit` (`execution_spec.py:163-249`) and `Node` (`outcome_spec.py:108-144`) gain the
  fields; neither has one today.
- R3. The default is ambient × read-write — exactly today's `full` behavior. A leaf that declares
  nothing gets the default; nothing breaks for leaves that do not declare (targeted posture, D5).
- R4. `read-only-verify` = read-only × disposable-worktree. Its edits are discarded; it exists to verify
  without risk to real work.
- R5. `sandboxed-mutate` = read-write × owned-worktree. Its edits are retained and harvested (R12).

### Enforcement

- R6. `mutation_policy: read-only` is enforced by **tool-set omission at spawn** — the agent is spawned
  without `Edit`/`Write`/`MultiEdit` (a restricted `agentType`), not by intercepting command strings
  (D4).
- R7. `workspace_isolation` is enforced by the saga-side worktree wrapper (D3): a disposable or owned
  worktree with the agent's working directory set there. This is the **universal floor** — it contains
  an accidental `git checkout`/`restore`/`reset` on every backend, including backends that cannot
  restrict tools.
- R8. A **per-backend enforceability matrix** names, for each backend, the concrete primitive for each
  axis or declares that axis halt-only on that backend. Known state: the worktree floor (R7) is
  saga-side and available on all backends; tool-set omission (R6) is available via custom `agentType` on
  inline (`tools:` frontmatter precedent — `plugins/saga/agents/mechanical-executor.md:4`) and
  cc-workflows (the `agent()` `agentType` opt, `Explore` precedent), but the verify-panel emitter does
  not pass it today (`execution_spec.py:488-503`) and must be wired; team-execution has no per-leaf
  tool-restriction consumer (`team_emitter.py:103-110`) and is worktree-floor-only until one is built.
  The matrix must be filled at the start of `/plan` (Outstanding Questions).
- R9. The capability never claims to defend against an adversarial agent (D2); the threat model is
  accidental clobber and least-privilege hygiene. Adversarial containment is the deferred OS sandbox.

### Degrade and visibility

- R10. Enforcement degrades by **halt, never downgrade**. Downgrading a restrictive profile would *add*
  privilege, the wrong direction. Dispatch runs pre-dispatch enforceability probes (e.g.
  `supports_tool_omission`, `supports_owned_worktree`); a restrictive capability that a backend cannot
  enforce HALTS — it never silently becomes `full`. (Existing degrade checks backend *availability*, not
  *enforceability* — `outcome_dispatcher.py:235-251`, `lifecycle_state.py:223-264`.)
- R11. A blocked or halted action is surfaced, not silent — the operator sees that a capability blocked
  it, so a too-tight capability is debuggable (mirrors the visible `orchestration_downgrade`).

### Safe mutation (owned worktree)

- R12. `sandboxed-mutate` harvest is defined: the leaf commits in its owned worktree, and the branch is
  merged/imported through the existing merge path (`outcome_merge.py`, `outcome.py:465-506`) — not by
  copying files over the live tree. The harvest steps (changed-file detection, verification,
  conflict handling, cleanup) are named for `/plan` to detail.
- R13. The worker checkpoints (commits) in its worktree before harvest, so its own in-worktree
  uncommitted work cannot be lost to a self-`git checkout` — the commit-before-verify discipline applied
  inside the worktree.
- R14. External engines get a per-engine **adapter** that maps `sandboxed-mutate` onto the engine's own
  flags — codex `--cd`/`--sandbox`/`--add-dir`, agy `--sandbox`/`--add-dir` — and redirects engine-local
  metadata (e.g. agy's `.antigravitycli/<uuid>.json`). Confinement is cwd/flag-based (consistent with
  D2's accidental threat model), not hard isolation. (Prior art:
  `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md:71-94`.)

### Coverage, wiring, coherence

- R15. A **spawn-site inventory** lists every site that spawns a delegated agent — the verify panel
  (`execution_spec.py:488-503`), `/code-review` lenses (`code-review/SKILL.md:164-166`), team-execution
  reviewers/validators (`reviewer-registry.md`, `validator-registry.md`), `/qa` escalation, `/investigate`
  (`investigate/SKILL.md:211-216`), `/resume` (`resume/SKILL.md:224-228`) — and marks each in-scope
  (profile attached), out-of-scope (with rationale), or default. The targeted posture is only safe with
  this inventory complete.
- R16. The capability field has a named enforcer per backend (R8) and a required integration test: a
  `read-only-verify` verifier that attempts a destructive `git checkout` is contained (real work intact)
  — proving the field is wired, not dead. (Dead-wiring guard.)
- R17. The verify/review class defaults to `read-only-verify` (D5), so a newly added verify/review spawn
  inherits the profile rather than silently running full.
- R18. R11's manifest (#285) records the leaf's capability as attribution — the pre-hoc scope beside
  R11's post-hoc record (D7). Coherence note, not a build dependency.
- R19. A capability only **narrows**; it never grants a tool, path, or mutation the backend would
  otherwise deny.

## Key Flows

- F1. **Read-only verify (clobber contained).** **Trigger:** a verify/review agent is spawned
  `read-only-verify`. It runs in a disposable worktree (R7) without write tools (R6) → it reads, runs
  tests, emits its verdict → an accidental `git checkout <tracked>` hits only the disposable tree; real
  uncommitted work is intact; the worktree is discarded. **Covers R4, R6, R7.**
- F2. **Sandboxed mutation (S-4/R11 unblocked).** **Trigger:** an external/delegated worker is spawned
  `sandboxed-mutate`. It gets an owned worktree (R7) → edits land there → it commits (R13) → the branch
  is harvested via the merge path (R12) → the live tree is untouched until harvest. **Covers R5, R12,
  R13.**
- F3. **External engine via adapter.** **Trigger:** codex/agy run as a `sandboxed-mutate` worker. The
  adapter invokes the CLI with `--cd <worktree>`/`--sandbox`/`--add-dir` and redirects engine metadata
  → edits land in the worktree. **Covers R14.**
- F4. **Default unchanged.** **Trigger:** a builder leaf declares nothing → ambient × read-write =
  today's behavior. **Covers R3.**
- F5. **Unenforceable → halt.** **Trigger:** a backend cannot enforce a requested restrictive
  capability → the pre-dispatch probe fails → dispatch HALTS visibly, never downgrades to full. **Covers
  R10, R11.**

## Acceptance Examples

- AE1. **Clobber contained (required integration test).** **Covers R6, R7, R16.** Given a
  `read-only-verify` verifier in a disposable worktree attempts `git checkout <tracked-path>`, when it
  runs, then real uncommitted work is intact (the checkout hit only the disposable tree) and the attempt
  is surfaced. This is a wired test, not prose.
- AE2. **Verifier can still work.** **Covers R4.** Given a `read-only-verify` agent runs `pytest` and
  `git diff`, when they execute, then both succeed — inspection is not blocked.
- AE3. **Safe mutation + harvest.** **Covers R5, R12, R13.** Given a `sandboxed-mutate` worker edits and
  commits in its owned worktree, when harvest runs, then the branch merges through the existing path and
  the live tree was untouched until merge.
- AE4. **External worker confined.** **Covers R14.** Given codex/agy runs `sandboxed-mutate` via the
  adapter with `--cd <worktree>`, when it writes, then the edits land in the worktree and engine metadata
  is redirected out of the repo root.
- AE5. **Default unchanged.** **Covers R3.** Given a builder leaf declares no capability, when it runs,
  then it behaves exactly as today.
- AE6. **Unenforceable halts, never downgrades.** **Covers R10.** Given a backend cannot enforce
  `read-only-verify`, when dispatch probes it, then it HALTS visibly and never runs the agent at `full`.
- AE7. **No escalation.** **Covers R19.** Given any capability is applied, then it only removes or
  redirects capability and never grants a tool or path the backend would otherwise deny.

## Scope Boundaries

**In scope:** the two-axis capability contract (R1-R5); enforcement by tool-omission + worktree floor +
the per-backend matrix + the accidental threat model (R6-R9); halt-not-downgrade and visibility
(R10-R11); owned-worktree harvest, self-clobber checkpoint, and the external-engine adapter (R12-R14);
the spawn-site inventory, dead-wiring integration test, verify-class default, R11 coherence, and
no-escalation (R15-R19).

**Deferred for later (or owned elsewhere):**

- Filling the per-backend enforceability matrix with exact primitives, the harvest mechanism detail, and
  per-engine adapter detail → `/plan` (the matrix is the first `/plan` task).
- Building S-4 (#283) and R11 (#285)'s consumers — this capability *provides* `sandboxed-mutate`; those
  issues lift their ceilings when they build (sequencing → `/plan`).
- A `path`/`network` sub-axis (the original Codex framing) — v1 is mutation + isolation; path/network is
  a future axis.

**Outside this capability's identity:**

- An **adversarial** sandbox (OS-level: containers/seccomp, escape-proof). R14's threat model is
  accidental clobber + least-privilege (D2); adversarial containment is a separate, deferred capability.
- Least-privilege-default for all leaves — a deliberate v1 exclusion (D5).

## Dependencies / Assumptions

- **The worktree floor extends `outcome_worktrees.py`** from per-child-outcome to per-leaf/worker
  ownership. The lifecycle exists (cap, removal-as-rejected, degrade-to-safe — `:51-57,423-479`); the
  granularity extension is `/plan`.
- **Tool-set omission availability differs by backend (R8).** Inline supports a custom `agentType` with
  `tools:` frontmatter (precedent: `mechanical-executor.md:4`); cc-workflows supports the `agent()`
  `agentType` opt (`Explore` precedent) but the verify-panel emitter must be wired to pass it; team-execution
  has no per-leaf consumer today and is worktree-floor-only until one is built. The worktree floor (R7) is
  available everywhere regardless.
- **External-engine confinement is cwd/flag-based, not hard isolation** (D2). codex/agy expose
  `--cd`/`--sandbox`/`--add-dir`; the adapter uses them. Hard isolation is the deferred OS sandbox.
- **S-4 (#283) and R11 (#285) are filed but unbuilt.** This capability provides what they named; it does
  not build their consumers. Build order → `/plan`.
- **Claude Code's native permission/sandbox primitives** (settings `permissions`/`defaultMode`/`sandbox`)
  are prior art `/plan` may align to; this repo configures none today.

## Outstanding Questions

**Resolve at the start of `/plan` (the existence of the feature does not depend on these — the worktree
floor in R7 makes the accidental-clobber threat model enforceable on every backend — but unit planning
does):**

- Fill the per-backend enforceability matrix (R8): the exact tool-omission primitive for inline,
  cc-workflows (wire the emitter), and team-execution (build a per-leaf consumer, or declare it
  worktree-floor-only).

**Deferred to `/plan`:**

- The capability field names, where they live (`Unit`/`Node`/dispatch), and the closed vocabularies.
- The owned-worktree harvest mechanism (changed-file detection, verification, conflict handling, cleanup).
- The per-engine adapter detail (codex vs agy flags, metadata redirection, structured diff import).
- Whether to add a `path`/`network` axis now or later.
- Alignment to Claude Code's native permission/sandbox primitives vs a saga-local capability.

## Sources / Research

**The clobber incident (verified premises):**

- `docs/engineering-journal/LEARNINGS.md:88-104` (`{#verify-agent-git-checkout-clobber}`);
  `docs/work-sessions/2026-06-25-outcome-orchestration.md:314`.

**Max-privilege substrate / prose-only "read-only":**

- `plugins/saga/scripts/team_emitter.py:103-110` (`bypassPermissions`).
- `plugins/saga/scripts/execution_spec.py:488-503` (verify panel emits label/model/effort only).
- `plugins/saga/skills/code-review/SKILL.md:164-166` (generic lens spawn), `:34-38` (prose read-only);
  `plugins/saga/skills/code-review/references/validator.md:52`.
- team-execution reviewer/validator taxonomy: `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`,
  `.../validator-registry.md` (base + optional reviewers + validators — not a flat list).

**Capability-blind dispatch + the hook-visibility constraint:**

- `plugins/saga/scripts/execution_spec.py:163-249` (`Unit` — no capability field);
  `plugins/saga/scripts/outcome_spec.py:108-144` (`Node` — no capability field);
  `plugins/saga/scripts/outcome_dispatcher.py:100-133,235-251` (dispatch / degrade checks availability);
  `plugins/saga/scripts/lifecycle_state.py:223-264`.
- `plugins/saga/hooks/pre_push_gate_hook.py:116-128` (`PreToolUse` stdin = `tool_name`+`tool_input`
  only — cannot see the agent's profile); `plugins/saga/hooks/hooks.json:14-32`.

**Tool-restriction precedent (feasibility):**

- `plugins/saga/agents/mechanical-executor.md:4` (`tools: Bash`);
  `plugins/deploy/agents/release-orchestrator.md:4` (`tools: Read, Glob, Bash, WebFetch`).

**Worktree isolation substrate + harvest path:**

- `plugins/saga/scripts/outcome_worktrees.py:1-8,51-57,91-93,423-479`;
  `plugins/saga/scripts/outcome_merge.py`; `plugins/saga/scripts/outcome.py:465-506`.

**Other spawn sites (inventory, R15):**

- `plugins/saga/skills/investigate/SKILL.md:211-216`; `plugins/saga/skills/resume/SKILL.md:224-228`;
  `plugins/saga/skills/qa/SKILL.md:168-171`.

**External-engine adapter prior art:**

- `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md:71-94` (codex/agy CLI flags
  `--cd`/`--sandbox`/`--add-dir`; agy `.antigravitycli` local-metadata footgun).

**Downstream IOUs this capability cashes:**

- S-4 #283 R23 — `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md:177-179`
  (and AE7 `:240-243`).
- R11 #285 R21 — `docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md:223-225`;
  envelope/subrecords precedent `:87-90`.

**Ideation origin:** `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:43-44` (promoted narrow
read-only face), `:395` (full Codex "least-privilege per leaf — tool/path/mutation/network" framing).

**External prior art (for `/plan`):** Claude Code permission/sandbox primitives; capability-based
security; worktree-per-task isolation.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md
- Source type: brainstorm
- Source title: Capability-Scoped Agent Sandbox

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/287
- Number: 287
- Created at: 2026-06-28T05:50:24.766250+00:00

