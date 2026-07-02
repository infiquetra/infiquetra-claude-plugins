---
title: Capability-Scoped Agent Sandbox — read-only-verify + sandboxed-mutate
type: feat
status: active
date: 2026-07-02
origin: docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md
---

# Capability-Scoped Agent Sandbox — read-only-verify + sandboxed-mutate

Give a delegated leaf a declared **sandbox** along two axes — `mutation_policy` (read-only |
read-write) × `workspace_isolation` (ambient | disposable-worktree | owned-worktree) — enforced
structurally per backend, composed into two named profiles: `read-only-verify` (closes the
verify-agent `git checkout` clobber) and `sandboxed-mutate` (lifts the external-engine
evidence-only ceiling by **wiring** the proven agy clone mechanism, not building new isolation).

## Issue / origin

- Issue: infiquetra/infiquetra-claude-plugins#287 (`requirements-ready` handoff)
- Requirements: `docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md`
  (readiness review verdict READY: `docs/reviews/2026-06-28-capability-scoped-sandbox-readiness.md`)
- Motivating incident: `docs/engineering-journal/LEARNINGS.md` `{#verify-agent-git-checkout-clobber}`

## Drift audit — issue premises re-verified 2026-07-02

The issue was written 2026-06-28; PRs #316, #317, #319 landed after it. Every load-bearing claim
was re-verified against the current tree before planning. This plan supersedes the issue's file
inventory where they disagree.

| Issue claim | Status today | Evidence |
|---|---|---|
| Verify panel emits label/model/effort only, no tool restriction | **Still true** (lines shifted) | `plugins/saga/scripts/execution_spec.py:882-897` (`_emit_verify_panel` opts) |
| Workers emitted `bypassPermissions` | **Still true** | `plugins/saga/scripts/team_emitter.py:128` |
| `/code-review` / `/qa` / `/investigate` / `/resume` read-only is prose | **Still true** | `code-review/SKILL.md:37,164`; `qa/SKILL.md:170-171`; `investigate/SKILL.md:211-216`; `resume/SKILL.md:232-233` |
| Worktrees are per-sub-outcome, not per-leaf | **Still true** | `plugins/saga/scripts/outcome_worktrees.py:1-8` (U7 design, WORKTREE_CAP=4) |
| "S-4 #283 and R11 #285 are filed but unbuilt" | **FALSE** — both shipped, plus #318 chaperone | commits c702668, e901ae1, 880b94c |
| Evidence-only ceiling is prose | **FALSE — now structural** | `engine_dispatch.py:44` (codex `sandbox: "read-only"`), `:50-69` (agy `mode: "no-write"`, `write_set: []` v1) |
| External-engine adapter (R14/A4/F3) must be designed | **Largely built + dogfooded n=3** | `plugins/agy/scripts/agy_delegate.py:808` (`setup_disposable_clone`, remotes stripped), `git diff <BASE_SHA>` harvest, `out_of_scope_mutation`; LEARNINGS `{#agy-pro-high-coder-dogfood-281}` |
| `capability` is a free field name | **FALSE — collision** | `execution_spec.py:396-398` — `Unit.engine`/`Unit.capability` are engine-routing selectors (mutually exclusive) |
| R18 manifest attribution has no consumer | **FALSE** — manifests shipped | `plugins/saga/scripts/provenance_manifest.py`, `manifest_store.py` (#285) |
| Isolation needs a saga-side wrapper everywhere | **Weakened** — inline Agent tool and cc-workflows `agent()` both natively support `isolation: 'worktree'` and `agentType` | Workflow/Agent tool contracts (host harness) |

Two settled decisions constrain this plan: DECISIONS `{#agy-delegated-build-no-jail}` (the
in-session junior-draft loop deliberately uses post-hoc verification, not isolation — do not
re-jail it) and `{#antigravity-teammate-plugin-plan-stance}` (the reusable teammate substrate is
clone-backed for all write modes — do not rebuild it). Adjacent open issue #293 (verify-panel
robustness) touches `_emit_verify_panel`; coordinate merge order, no dependency.

## Requirements

Carried forward from the requirements doc (issue R-numbers cited), re-baselined to the current tree.

- R1. A two-axis sandbox contract rides `Unit` and `Node` beside the model/effort tier:
  `mutation_policy` ∈ {read-only, read-write}, `workspace_isolation` ∈ {ambient,
  disposable-worktree, owned-worktree}. Absent ⇒ ambient × read-write, exactly today's behavior.
  (issue R1-R3)
- R2. Named profiles are compositions accepted as shorthand: `read-only-verify` = read-only ×
  disposable-worktree; `sandboxed-mutate` = read-write × owned-worktree. (issue R4-R5)
- R3. `mutation_policy: read-only` is enforced by tool-set omission at spawn (a restricted
  `agentType` without Edit/Write); `workspace_isolation` is enforced by worktree/clone routing.
  The isolation axis is the load-bearing clobber defense — Bash `git checkout` needs no Edit/Write
  tool, and verifiers must keep Bash to run tests. (issue R6-R7, D3-D4)
- R4. A per-backend enforceability matrix is code, not prose: a restrictive sandbox a backend
  cannot enforce HALTS visibly (spec-validate error or dispatch `HaltReceipt` naming the axis and
  backend), never downgrades. (issue R8, R10-R11)
- R5. The verify/review class defaults to `read-only-verify`: the verify-panel emitter attaches it
  unconditionally; `/code-review`, `/qa`, `/investigate`, `/resume` spawn guidance names the
  restricted agent type + isolation. (issue R15, R17)
- R6. The external write ceiling lifts by wiring, not building: a `sandboxed-mutate` engine unit
  dispatches an agy envelope with `mode: "patch-only"`, `write_set` = the unit's declared files,
  `apply_policy: "preserve-patch"` — riding `agy_delegate.py`'s existing clone + gated patch
  import. codex has no write adapter: a codex `sandboxed-mutate` unit HALTS. `satisfy_gate`'s
  `verified_by_claude` requirement is untouched. (issue R12-R14, D6, D8)
- R7. The provenance manifest records the leaf's declared sandbox as attribution — pre-hoc scope
  beside the post-hoc record. (issue R18)
- R8. A sandbox only narrows; it never grants a tool, path, or mutation the backend would
  otherwise deny. (issue R19)
- R9. A wired clobber-contained integration test proves the floor: a `git checkout <tracked>` run
  inside a disposable worktree leaves the primary tree's uncommitted work intact. (issue R16, AE1)
- R10. Release surfaces move in the same PR: saga + team-execution plugin.json, marketplace.json,
  CHANGELOGs, version drift-guard tests, journal entries.

## Key Technical Decisions

- KTD1. **Field name is `sandbox`, an envelope of the two axes** — `Unit.capability` is taken by
  engine routing (`execution_spec.py:398`), so the issue's working name is unusable. A single
  `sandbox` dict (`{"mutation_policy": …, "workspace_isolation": …}`) with profile-string
  shorthand (`"sandbox": "read-only-verify"` expands at parse) mirrors the #285 "one envelope,
  two subrecords" precedent and keeps `to_dict` round-trip absent-key-stable (existing specs gain
  no key).

- KTD2. **Native harness isolation over a saga-side wrapper on inline and cc-workflows.** The
  Agent tool and Workflow `agent()` both accept `isolation: 'worktree'` and `agentType`; the
  emitter and skill guidance pass them instead of saga provisioning per-leaf worktrees. This
  respects `outcome_worktrees.py`'s deliberate per-sub-outcome granularity and WORKTREE_CAP —
  disposable verify worktrees are harness-managed and auto-cleaned. The saga-side wrapper is NOT
  extended per-leaf in v1.

- KTD3. **team-execution is declared unenforceable for restrictive sandboxes in v1, checked at
  authoring time.** `team_emitter.py` emits residents with `bypassPermissions` and no per-leaf
  tool restriction consumer exists; rather than a runtime halt, `execution_spec.validate` /
  `team_emitter` raise `SpecError` when a restrictive-sandbox unit is routed to team-execution —
  halt-not-downgrade moved to the cheapest failure point. team-execution's own reviewer/validator
  registry keeps its existing protocol (documented out-of-scope in the inventory, with rationale).

- KTD4. **The external face is a dispatch-builder change, not new isolation.** `engine_dispatch`
  builders gain a sandbox parameter: agy `sandboxed-mutate` ⇒ `mode: "patch-only"` +
  `write_set` from unit files (vocabulary already exists: `agy_delegate.py:23,26`); codex
  `sandboxed-mutate` ⇒ halt (`sandbox: "read-only"` is codex's only supported posture today).
  Nothing about gate semantics changes.

- KTD5. **No hook-based command interception.** `PreToolUse` stdin is `{tool_name, tool_input}`
  only (`plugins/saga/hooks/pre_push_gate_hook.py:116-128`) — it cannot see the calling agent's
  profile, and parsing arbitrary shell for side effects is infeasible. Confirmed unchanged;
  enforcement stays spawn-time + isolation. (issue D4)

- KTD6. **Verify-class default has no opt-out in v1.** The verify-panel emitter attaches
  `read-only-verify` to every verifier unconditionally. A verifier that needs write access is a
  design smell, and an opt-out would be an escalation channel contradicting R8.

- KTD7. **Residual risks accepted under the accidental threat model.** A git worktree shares
  `.git` — an in-worktree `git push` or branch mutation is still possible via Bash. That is
  outside the accidental-clobber threat model (issue D2); the external-engine face, where push
  actually happened in the wild (n=1, LEARNINGS `{#agy-delegated-coder-contain-agency}`), uses
  the remotes-stripped clone which cannot push. Documented, not defended.

## Implementation Units

Dependency order: U1 → {U2, U3, U5} → U4 → U6 → U7. Each unit lands independently green.

### U1. `sandbox` contract on `Unit` and `Node`

**Summary:** Add the two-axis `sandbox` envelope + profile shorthand to
`plugins/saga/scripts/execution_spec.py` (`Unit`, module-level `SANDBOX_PROFILES`,
`_validate_sandbox`) and `plugins/saga/scripts/outcome_spec.py` (`Node`), with closed
vocabularies, parse-time profile expansion, absent-key round-trip, and validation (unknown axis
value, unknown profile, profile+explicit-axes conflict are `SpecError`s).

**Files:** `plugins/saga/scripts/execution_spec.py`, `plugins/saga/scripts/outcome_spec.py`

**Test scenarios** (`tests/test_saga_execution_spec.py`, `tests/test_outcome_spec.py`):
absent sandbox round-trips with no new key and defaults to ambient × read-write; profile string
expands to the exact axis pair; explicit axes accepted; unknown vocabulary/profile raises;
`sandbox` coexists with `engine`/`capability` fields without interference.

### U2. read-only verifier agent + emitter wiring

**Summary:** Add `plugins/saga/agents/readonly-verifier.md` (`tools: Bash, Read, Grep, Glob` —
no Edit/Write; system prompt states the read-only contract and disposable-worktree context) and
wire **all three** verifier-emitting sites in `execution_spec.py` to emit
`agentType: 'saga:readonly-verifier'` and `isolation: 'worktree'` in every verifier `agent()`
opts (KTD6, R5): `_emit_verify_panel` (`:864-912`), `_emit_verify_loop_singleton` (`:808`), and
the parallel-layer thunk's inlined iterate-to-consensus loop (`:735-760`, which builds its own
`verifier_opts`). Missing any one site is exactly the dead-wiring failure R9 guards against.

**Files:** `plugins/saga/agents/readonly-verifier.md`, `plugins/saga/scripts/execution_spec.py`

**Test scenarios** (`tests/test_saga_execution_spec.py`): emitted workflow script contains
`agentType` + `isolation: 'worktree'` on every verifier call across all three emission shapes
(plain panel, iterate-to-consensus singleton, parallel-layer thunk loop — one spec fixture
exercising each); the unit's own (non-verifier) `agent()` call is unchanged; agent definition
file exists with exactly the allowed tools (frontmatter parse); **literal-consistency guard** —
the `agentType` string emitted by all three sites is derived from (or asserted equal to) the
agent definition's `name:` frontmatter plus the plugin prefix, so a rename of either side fails
a test instead of silently un-enforcing (saga-side half of the registry-drift risk; the
harness-side half is the live spawn smoke in Verification below).

### U3. Enforceability matrix + halt-not-downgrade

**Summary:** Encode the per-backend matrix as data (backend → axis → enforceable primitive |
halt) in `execution_spec.py`. `validate` cannot see the backend (a spec is backend-agnostic), so
enforcement sits at the consumers: `team_emitter.emit` raises `SpecError` for a
restrictive-sandbox unit (KTD3), `emit_workflow_script` wires the enforcement opts (U2), and
`outcome_dispatcher.dispatch` probes the matrix producing an axis-naming `HaltReceipt` (reuses
the existing R5/R23 halt seam, `outcome_dispatcher.py:61-98`). Matrix v1: inline/cc-workflows
enforce read-only + disposable-worktree natively; internal `owned-worktree` is halt-v1 (no
defined internal harvest — sandboxed-mutate's only v1 consumer is the engine path, U5);
team-execution enforces neither restrictive axis; engines: agy = clone (both profiles), codex =
read-only only. Any backend NOT listed in the matrix (`fork`, `subagent`, `goal`, `manual` from
`NODE_BACKENDS`, and future ones) defaults to unenforceable ⇒ halt for a restrictive sandbox —
unknown never means permissive (R4).

**Files:** `plugins/saga/scripts/execution_spec.py`, `plugins/saga/scripts/team_emitter.py`,
`plugins/saga/scripts/outcome_dispatcher.py`

**Test scenarios** (`tests/test_saga_execution_spec.py`, `tests/test_team_emitter.py`,
`tests/test_outcome_dispatcher.py`): restrictive unit + team-execution emit raises naming unit,
axis, backend; default-sandbox unit emits unchanged everywhere; dispatcher halt receipt carries
the axis; no path silently strips or weakens a sandbox (`-k enforce_halt`).

### U4. Spawn-site inventory + skill attachments

**Summary:** Write `plugins/saga/references/sandbox-spawn-sites.md` — every delegated-agent
spawn site marked in-scope (profile attached), out-of-scope (rationale), or default — and edit
the four skill spawn instructions (`code-review/SKILL.md` lens dispatch, `qa/SKILL.md` parallel
verification, `investigate/SKILL.md` evidence sub-agents, `resume/SKILL.md` synthesis dispatch)
to name `readonly-verifier` + worktree isolation. Out-of-scope with rationale: team-execution
reviewer/validator registry (KTD3), the `/agy:delegate` junior-draft loop
(`{#agy-delegated-build-no-jail}`), `mechanical-executor` (already Bash-only), builder leaves
(R1 default). The inventory doc also carries the **ad-hoc spawn rule** — any verify/review-class
Agent-tool spawn made outside a skill must pass `subagent_type: saga:readonly-verifier` +
`isolation: "worktree"` — and the repo `CLAUDE.md` gains a one-line pointer to it, so the
prose-guarded ad-hoc class is at least instruction-guarded everywhere an agent reads context.

**Files:** `plugins/saga/references/sandbox-spawn-sites.md`, the four SKILL.md files, `CLAUDE.md`

**Test scenarios** (`tests/test_sandbox_spawn_sites.py`, new):
inventory guard — every skill file matching the spawn-instruction pattern is listed in the
inventory doc; the four in-scope skills reference `readonly-verifier` (`-k spawn_site_inventory`).

### U5. External write-ceiling lift (wire agy, halt codex)

**Summary:** `engine_dispatch.build_agy_envelope` accepts the unit's sandbox: `sandboxed-mutate`
⇒ `mode: "patch-only"`, `write_set` = unit `files`, `apply_policy: "preserve-patch"`;
default/read-only unchanged (`mode: "no-write"`, `write_set: []`). `build_codex_invocation`
raises/halts on `sandboxed-mutate` (KTD4). Update
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` to describe
the write-mode chaperone leg. Thread the declared sandbox into the provenance manifest as
attribution (R7) via `provenance_manifest.py` — an **optional, absent-tolerant field with no
`SCHEMA_VERSION` bump** (the version check is strict equality, `provenance_manifest.py:359-360`;
mirrors U1's absent-key round-trip pattern).

**Files:** `plugins/saga/scripts/engine_dispatch.py`, `plugins/saga/scripts/provenance_manifest.py`,
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`

**Test scenarios** (`tests/test_saga_engine_dispatch.py`): sandboxed-mutate agy envelope carries
patch-only + the unit's write_set + preserve-patch; payload byte-preservation assertion still
holds; codex sandboxed-mutate halts with a visible reason; no-sandbox dispatch is byte-identical
to today (`-k sandboxed_harvest or enforce_halt`); manifest records the declared sandbox.
End-to-end clone + patch-import harvest proof already exists in `tests/test_agy_apply_policy.py`
/ `tests/test_agy_delegate_contract.py` — this unit proves the *envelope contract*, not the
wrapper mechanics (issue AE3's harvest half is discharged by those existing suites; the
`git diff <BASE_SHA>` harvest also subsumes issue R13's self-clobber checkpoint, since the diff
captures uncommitted worktree state against base).

### U6. Clobber-contained integration test + no-escalation

**Summary:** The dead-wiring guard (R9, AE1), two layers: (a) mechanism — build a real temp git
repo with uncommitted edits, provision a disposable worktree, run `git checkout -- <tracked>`
inside it, assert the primary tree's uncommitted edits survive and the worktree is discardable;
(b) wiring — the emitted verify-panel script carries the isolation + agentType opts end-to-end
from a spec fixture. Plus the no-escalation property (R8): applying any sandbox to a
spec/envelope never adds a tool, mode, or path relative to the unsandboxed form.

**Files:** `tests/test_sandbox_clobber_contained.py` (new)

**Test scenarios:** `-k clobber_contained` passes (real work intact); `-k capability_axes`
profile-composition property; no-escalation comparison over all profiles × backends.

**Test expectation:** this unit IS tests; no separate scenarios.

### U7. Release surfaces + journal

**Summary:** saga `0.46.0 → 0.47.0`, team-execution `2.6.0 → 2.7.0`,
`.claude-plugin/marketplace.json`, both CHANGELOGs, version drift-guard tests
(`tests/test_saga_plugin.py:48`, `tests/test_team_execution_plugin.py:60` precedent); DECISIONS
entries for KTD1-KTD7 and a LEARNINGS entry only if the build surfaces a non-obvious mechanism.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`,
`docs/engineering-journal/DECISIONS.md`

**Test expectation:** none — release metadata + docs; guarded by existing drift tests.

## Per-unit tier recommendations

| Unit | Label | Tier | Rationale |
|---|---|---|---|
| U1 | sandbox contract | opus / high | Schema + validation seam design; round-trip subtleties |
| U2 | verifier agent + emitter | opus / high | Emitter is load-bearing; wrong opts = silent no-enforcement |
| U3 | enforceability + halt | opus / high | Cross-module seam threading; halt semantics |
| U4 | inventory + skills | sonnet / medium | Doc + guided prose edits, guard test mechanical |
| U5 | external wire | opus / high | Adversarial-adjacent dispatch contract; payload preservation |
| U6 | integration tests | opus / high | The proof the feature isn't dead wiring |
| U7 | release triad | sonnet / medium | Mechanical, drift-guard-covered |

## Scope Boundaries

**Out of scope (true non-goals):** adversarial/OS-level sandboxing (containers, seccomp);
least-privilege default for builder leaves; a `path`/`network` axis; re-jailing the
`/agy:delegate` junior-draft loop (settled: `{#agy-delegated-build-no-jail}`); rebuilding agy's
clone containment; changing `satisfy_gate` / gate semantics; per-leaf saga-side worktree
provisioning (KTD2).

**Deferred follow-up work:** a codex write-mode adapter (halt is v1's answer); a team-execution
per-leaf tool-restriction consumer (would flip KTD3's matrix row); S-4/R11 consumers pulling
`sandboxed-mutate` (their issues); filesystem-boundary audit for delegates (noted in the n=1
comment — needs the OS sandbox).

## Risk Analysis

- **Emitter opts drift (highest):** if `agentType`/`isolation` names don't match the harness
  registry, verifiers silently run unrestricted. Mitigation: U6 wiring assertions + the agent-def
  existence test in U2.
- **#293 merge collision:** verify-panel robustness edits the same emitter. **Decided
  (2026-07-02 doc-review fix pass): #287 lands first**; #293's `/plan` runs against the
  post-#287 emitter (its verifier calls will already carry `agentType`/`isolation` opts).
  Ordering note posted on #293.
- **Behavior regression for existing specs:** absent-key round-trip is asserted in U1; U5 asserts
  byte-identical no-sandbox dispatch.
- **Worktree-shares-.git residuals:** accepted under the threat model (KTD7), documented in the
  inventory doc so it is a known boundary, not a surprise.

## Verification

```bash
# Full local gate (mirrors CI)
uv run pytest -q
uv run ruff format --check . && uv run ruff check .
uv run mypy plugins/
uv run bandit -r plugins/ -q
# Capability-specific suites
uv run pytest tests/ -k "sandbox or clobber or enforce or spawn_site" -v
```

**`/qa` acceptance (live-harness, not pytest-able):** the registry-drift smoke — emit a minimal
one-unit spec with a verify panel, run it via the Workflow tool, and confirm from the run that
(a) `saga:readonly-verifier` resolved (no unknown-agentType fallback), (b) the verifier reported
a toolset without Edit/Write, and (c) its working directory was a worktree, not the primary
tree. This is the harness-side half of the registry-literal risk; the saga-side half is U2's
literal-consistency guard test.
