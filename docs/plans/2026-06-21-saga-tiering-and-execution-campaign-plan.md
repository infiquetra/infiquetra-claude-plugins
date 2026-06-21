---
title: Saga Tiering & Execution-Mechanism Campaign — Implementation Plan
type: feat
status: active
date: 2026-06-21
origin: docs/brainstorms/2026-06-20-saga-tiering-and-execution-campaign-requirements.md
---

# Saga Tiering & Execution-Mechanism Campaign — Implementation Plan

## Summary

Build the whole campaign — five dependency-sequenced epics (tiering spine, execution-backend
representation, dynamic-workflow authoring, hook harness, cheap executor + release guards) — and execute
it through **one hand-authored ultracode workflow** with a per-unit `{model, effort}` tier on every step.
The plan is the authoritative spec; the sibling
[`2026-06-21-saga-tiering-and-execution-campaign.workflow.js`](./2026-06-21-saga-tiering-and-execution-campaign.workflow.js)
is the execution harness `/work` runs. Authoring that script by hand is deliberate: it dogfoods the very
capability Epic 2 will automate (R9), validating the spec by walking it.

## Problem Frame

Saga keeps defaulting expensive by omission: 4 callable ecosystem agents still run on Opus, the repo has
zero hooks, the `/plan` offer undersells dynamic workflows as fan-out only, and the recommender
hard-forces team-execution on any consensus signal (`lifecycle_state.py:158`, `team = … or
needs_consensus`) so a workflow judge-panel is never recommended — even though `adversarial_confidence`
already exists as an ultracode trigger one branch away (`lifecycle_state.py:163`). The cross-doc seam is
tiering: "pin the model where agents are dispatched" and "assign a per-unit `{model, effort}` where plan
work is defined" are the same decision on two dispatch surfaces. This plan resolves the HOW for all of it.

## Requirements

Carried forward from the brainstorm (R-IDs stable), grouped by epic in build order. These are the
reviewer's and `/work`'s checklist; each maps to one or more Implementation Units below.

**Epic 0 — Tiering spine**

R1. A single tier rule governs every model/effort choice: judgment → Opus; mechanical/deterministic
(census, link checks, file-existence, enumeration) → Sonnet/Haiku; read-only sampling/survey → Sonnet.

R2. Enforced at both dispatch surfaces: (a) the **callable** ecosystem agents pin `model:` in frontmatter
(the per-call-model half has no saga dispatch site — see KTD7); (b) a `/plan`-authored workflow spec
carries an explicit per-unit `{model, effort}` annotation.

R3. A workflow spec asserts the pilot↔fan-out same-tier invariant at authoring time — a mis-tiered pilot
is an invalid oracle.

R4. The tier rule is recorded once as prose where it auto-loads every session (global `~/.claude/CLAUDE.md`),
not in `DECISIONS.md`.

**Epic 1 — Execution-backend representation**

R5. The `/plan` offer names dynamic workflows' **both** purposes — breadth/scale fan-out AND adversarial
confidence (judge-panel / refute-N / perspective-diverse) — and a drift-guard test asserts every offer
surface stays a superset of the `operator-choice.md` §3.2 purpose list.

R6. The offer frames the team↔workflow choice on the **governance** axis (does the verdict need to stick —
block a merge/deploy and persist — or is it throwaway?), not on "review depth," which both have.

R7. The recommender distinguishes **gated** consensus (must block/persist → team-execution) from
**advisory** consensus (N in-session votes → eligible for a workflow judge-panel) and stops hard-forcing
team-execution on every consensus signal.

R8. The operator-facing label is "dynamic workflows" via a display-label map; the stored enum value
`cc-workflows-ultracode` is unchanged (frozen wire contract).

**Epic 2 — Dynamic-workflow authoring**

R9. `/plan` can author one structured execution-spec and emit from it **either** a runnable Claude Code
workflow script **or** the team-execution markdown protocol; saga records a pointer, never vendors backend
machinery.

R10. Every fan-out unit declares an **enumerated** target list with post-run reconciliation — never a
silent filter.

R11. An authored workflow is capability-portable: every plan carries a runnable inline/serial baseline; the
dynamic layer applies on a capable host; on off-host resume the choice is re-checked, a one-line downgrade
is surfaced, and only the orchestration tier recompiles down (unit specs and tiers preserved).

R12. Backend choice-vs-recommendation is recorded; a `/retro`/`/optimize` pass surfaces the override-rate
(plus over/under-tier and budget-exhaustion signals) so any default re-weighting is evidence-driven.

**Epic 3 — Hook harness**

R13. A deterministic hook validates `marketplace.json` / `plugin.json` on edit (JSON parse + bracket-count)
and blocks on failure with the offending line.

R14. A hook nudges (does not write/block) when a `feat`/`fix` commit touches code but stages no
`docs/engineering-journal/` entry, and ships so it can fire cross-repo.

R15. A hook runs the repo's pre-push gate from a single-source gate manifest and reports by exception.

**Epic 4 — Cheap executor + release guards**

R16. Exactly one cheap-tier executor agent (haiku, Bash-only), dispatched by saga commands and inert until
called, handles mechanical op-discriminated work.

R17. A guard keeps the plugin release triad in sync (`plugin.json` ↔ `marketplace.json` ↔ `CHANGELOG.md`).

R18. A SHA-stamp stager and a stale-main-after-squash guard, scoped to this repo, close the remaining
release rituals.

## Key Technical Decisions

**KTD1 — One hand-authored ultracode workflow builds the campaign.** The plan stays decisions; the sibling
`.workflow.js` is the execution harness (the `context-fleet-audit.workflow.js` precedent — control-flow
only, agents do the work). Hand-authoring it now validates the R9 spec before Epic 2 automates it.

**KTD2 — Per-unit `{model, effort}` tiering (operator-approved): 5 Opus / 11 Sonnet / 1 Haiku.** Rule:
judgment → Opus, read-only survey → Sonnet, mechanical → Sonnet/Haiku. The full table is the Execution
Spec below.

**KTD3 — Full hands-off auto-merge (operator-chosen).** Each epic lands as its own PR and merges with a
plain `gh pr merge --squash` (**not** `--admin`) only after the agent confirms all 5 CI checks are
conclusively SUCCESS. The oracle is the test suite + the two plugin validators + the drift-guard tests.
**Verified caveat (doc-review):** `main` is currently **unprotected** — no GitHub-required checks — so the
merge gate is the agent's poll discipline alone, not GitHub enforcement (`--admin` would bypass nothing and
is dropped). The harness merge step therefore (a) merges only on all-SUCCESS, treating pending / null /
FAILURE as do-not-merge, and (b) forbids its gate-fix loop from weakening tests, deleting assertions, or
adding `# type: ignore` / `# noqa` to force a pass (cap 3 attempts, then leave the PR unmerged). The proper
hardening — enabling branch protection with the 5 checks so GitHub enforces the gate — is recommended but is
the operator's infra call (see Risk Analysis, R-RISK-1). No mid-run operator checkpoint.

**KTD4 — R7 gated-vs-advisory via an explicit interrogation question, work-shape pre-filled
(operator-chosen).** `/plan` asks "does this verdict need to block a merge/deploy or persist as evidence?",
defaulting to *gated* when deploy/security/persist signals are present, *advisory* otherwise. Advisory
routes to the existing `adversarial_confidence` ultracode branch; gated keeps team-execution. The operator
confirms.

**KTD5 — Decouple, do not rename (R8).** A display-label map renders "dynamic workflows"; the enum string
`cc-workflows-ultracode` is frozen (carried in persisted sagas). The label does **not** encode "(Claude
Code only)" — the existing omit-off-host rule (`operator-choice.md` §4) already hides the option where it
cannot run, so the suffix is on-host noise.

**KTD6 — One spec, two emitters, saga points (R9).** The structured execution-spec lives as a delimited
section authored into the plan; the two emitters produce sibling artifacts (a `.workflow.js` and the
`## Team Structure` markdown); saga stores only `orchestration_ref`. The governance difference is *which
emitter runs*, not the authoring.

**KTD7 — Epic 0 scope correction: pin 4 agents, not 5.** `redis-channel/redis-channel-coach` is a
reference pointer (the load-bearing guidance lives in the MCP server's `instructions=` field; "subagent
invocations not expected") — pinning `model:` on it is inert, so it is documented exempt. saga has no
`agents/` dir and no dispatch sites: the 4 callable agents live in 4 other plugins, dispatched by their own
plugins, so R2's frontmatter pin carries the whole enforcement.

**KTD8 — R4 is applied inline, not inside the workflow.** `~/.claude/CLAUDE.md` is a global file outside the
repo; editing it must not happen in an unattended fan-out. The operator confirms the ~3-line rule addition
out of band.

**KTD9 — Rebase-before-merge discipline (from the reference pattern).** Every workflow agent runs
`git fetch origin` and rebases the latest default branch before opening or merging its PR. The two
saga.py-touching units (U3 instrument, U4 label map) live in different epics; their merge order resolves by
rebase, not by a hard serialization. **Hands-off guardrail:** if the rebase produces a CONFLICT in
`plugins/saga/scripts/saga.py` (or any load-bearing logic file), the agent does **not** auto-resolve — it
aborts the rebase, leaves the PR unmerged with a "needs review" reason, and the run continues (the conflict
is surfaced to the operator at completion). Autonomous conflict resolution in load-bearing code is out of
bounds.

**KTD10 — R15 gate manifest is a small declarative file** co-located with the validators
(`tools/gate-manifest.*`); the exact format is settled inside U9 (Epic 3 is independent and lowest-stakes,
so the decision can land with its implementation).

## Implementation Units

Seventeen units, U-IDs stable, grouped by epic and dependency-ordered. Each unit is independently landable
on its epic branch. The **Tier** field is the workflow step's `{model, effort}`; the **Test** field gives
the repo-relative test path.

### U1. Preflight — re-verify grounding facts on origin/main

**Requirement:** gates the whole run (no R-ID).

**Tier:** haiku / low.

**Work:** confirm on `origin/main` that the 4 agents are unpinned, `ORCHESTRATION_MODES` matches
`saga.py:71`, the `or needs_consensus` line is at `lifecycle_state.py:158`, and the repo has zero hooks.
Reply `READY` or a short list of drift. HALT the workflow on drift.

**Files:** read-only.

**Test expectation:** none — a verification barrier, no code.

**Dependencies:** none (first step).

### U2. Pin the 4 callable ecosystem agents

**Requirement:** R1, R2(a).

**Tier:** sonnet / high.

**Work:** add `model:` to frontmatter — `home-lab-ops/homelab-sre` → `opus`;
`mission-control/sdlc-operator` → `sonnet`; `unifi/unifi-network-ops` → `sonnet`;
`deploy/release-orchestrator` → `sonnet`. Document `redis-channel/redis-channel-coach` exempt (KTD7). Bump
each touched plugin's release triad in the same change (`plugin.json` version, `.claude-plugin/marketplace.json`,
`CHANGELOG.md`) per CLAUDE.md §6.

**Files:** `plugins/{home-lab-ops,mission-control,unifi,deploy}/agents/*.md`, each plugin's `plugin.json`
+ `CHANGELOG.md`, `.claude-plugin/marketplace.json`.

**Failure modes:** double-`]` corruption of `marketplace.json` (mitigated structurally by U7's hook once it
lands, and by `python3 -m json.tool` validation here); version drift between the triad surfaces (U15 guards
it later).

**Test:** `tests/test_agent_tiering.py` (new) asserts the 4 agents carry their expected `model:` value and
the coach is recorded exempt; existing plugin validators stay green.

**Dependencies:** U1.

### U3. Instrument choice-vs-recommendation recording

**Requirement:** R12 (recording half; lands first so the field exists before any choice is recorded).

**Tier:** sonnet / medium.

**Work:** extend the saga envelope to record both the recommended backend and the operator's pick on each
orchestration decision, so override-rate is computable later. No analysis yet (that is U13).

**Files:** `plugins/saga/scripts/saga.py`, `plugins/saga/references/saga-spec.md` (field doc).

**Failure modes:** an older saga lacking the field must load (backward-compatible default); never crash on
absence.

**Test:** `tests/test_saga_saga.py` asserts the recommendation+choice fields round-trip and absent-field
sagas still load.

**Dependencies:** U1. Shares `saga.py` with U4 → KTD9 rebase discipline.

### U4. Display-label map (decouple, freeze the wire)

**Requirement:** R8.

**Tier:** sonnet / high.

**Work:** add a display-label map (`cc-workflows-ultracode` → "dynamic workflows",
`team-execution` → "team execution", `inline` → "inline"); route every offer surface's rendering through
it; assert the enum value is unchanged. Label carries no "(Claude Code only)" suffix (KTD5).

**Files:** `plugins/saga/scripts/saga.py` (or a small `lifecycle_state.py` helper), the offer surfaces in
`plugins/saga/skills/{plan,work,loop,code-review}/SKILL.md`.

**Failure modes:** a surface that renders the raw enum instead of the label (the drift-guard in U5 also
covers naming); a map miss must fall back to the enum string, never error.

**Test:** `tests/test_saga_saga.py` (or `tests/test_saga_plugin.py`) asserts the map renders "dynamic
workflows" while `ORCHESTRATION_MODES` is byte-for-byte unchanged.

**Dependencies:** U1. Shares `saga.py` with U3 → KTD9.

### U5. Offer rewrite + drift-guard test

**Requirement:** R5, R6.

**Tier:** opus / high.

**Work:** rewrite the `/plan` execution-backend offer (and the sibling offer in `code-review`) to name both
workflow purposes and frame the team↔workflow fork on the governance axis. Add a drift-guard test asserting
every offer surface's stated purpose list is a **superset** of `operator-choice.md` §3.2, so a future
rebuild cannot silently drop a purpose.

**Files:** `plugins/saga/skills/plan/SKILL.md` (the `:253` offer), `plugins/saga/skills/code-review/SKILL.md`,
new `tests/test_operator_choice_drift.py`.

**Failure modes:** the drift-guard must parse the §3.2 purpose list robustly (anchor on stable markers, not
line numbers); a brittle assertion that breaks on benign reformatting is itself a regression.

**Test:** `tests/test_operator_choice_drift.py` (new) — passes today, fails if any offer surface drops a
§3.2 purpose.

**Dependencies:** U1.

### U6. Recommender split — gated vs advisory consensus (R7 keystone)

**Requirement:** R7, KD5.

**Tier:** opus / high.

**Work:** in `recommend_execution_backend`, replace the single `needs_consensus` with a gated/advisory
distinction. Gated → team-execution (unchanged path); advisory → feed the existing `adversarial_confidence`
ultracode trigger; stop the unconditional `or needs_consensus` hard-force. Add the KTD4 interrogation
question + the work-shape default to the `/plan` flow. Cover AE1 (advisory → ultracode) and AE2 (gated →
team).

**Files:** `plugins/saga/scripts/lifecycle_state.py`, `plugins/saga/references/operator-choice.md` (§3.1
update), `plugins/saga/skills/plan/SKILL.md` (the new question), `tests/test_saga_plugin.py`.

**Failure modes:** a contested-but-not-gated job must NOT regress to inline (it should reach the advisory
ultracode branch); overlap (gated AND broad fan-out) still lists both alternatives; `has_code_surface`
docs-gating preserved.

**Test:** `tests/test_saga_plugin.py` — AE1, AE2, the overlap case, and the docs-gating case.

**Dependencies:** U1. Touches `lifecycle_state.py` + `operator-choice.md` (U5 also edits offer prose, not
this file).

### U7. Marketplace/plugin.json validation hook (R13)

**Requirement:** R13.

**Tier:** sonnet / high.

**Work:** the repo's first hook. A `PreToolUse`/edit-time hook that JSON-parses `marketplace.json` /
`plugin.json` and asserts balanced brackets, blocking on failure (exit 2) with the offending line. Ship as a
plugin's `hooks/hooks.json` (the langfuse-style cross-repo pattern) wired into the plugin that owns
marketplace integrity.

**Files:** new `plugins/<owner>/hooks/hooks.json` + the validator script, plugin release triad bump.

**Failure modes:** the hook must not block unrelated edits; must handle a transiently half-written file
without false-blocking a legitimate multi-edit; exit-code contract correct (2 blocks).

**Test:** `tests/test_marketplace_hook.py` (new) — AE5 (unbalanced brackets → block + named line; valid JSON
→ pass).

**Dependencies:** U1.

### U8. Journal-omission nudge hook (R14)

**Requirement:** R14.

**Tier:** sonnet / high.

**Work:** a non-blocking hook that, on a `feat`/`fix` commit touching code with no staged
`docs/engineering-journal/` entry, surfaces a nudge. Does not write the entry and does not block. Ships so
it can fire cross-repo (user-enabled).

**Files:** the hook entry in `hooks/hooks.json` + script.

**Failure modes:** must not nudge on docs-only or chore commits; must not block; cross-repo path assumptions
must degrade quietly where the journal dir is absent.

**Test:** `tests/test_journal_nudge_hook.py` (new) — AE6 (code `feat`/`fix`, no journal → nudge, no write,
no block; docs-only → silent).

**Dependencies:** U1. Co-located with U7's `hooks.json` → authored after U7 on the E3 branch.

### U9. Pre-push gate hook + manifest (R15)

**Requirement:** R15, KTD10.

**Tier:** sonnet / medium.

**Work:** a small declarative gate manifest (`tools/gate-manifest.*`) listing the pre-push gate
(`ruff format --check`, `ruff check`, the two validators, `pytest`) and a hook that runs it and reports by
exception. Settle the manifest format here.

**Files:** new `tools/gate-manifest.*`, the hook entry + runner.

**Failure modes:** report-by-exception (silence on pass); must not duplicate the CI definition divergently —
single source.

**Test:** `tests/test_pre_push_gate.py` (new) — manifest drives the gate; a seeded failure reports, a clean
tree is silent.

**Dependencies:** U1. Co-located with U7/U8 on the E3 branch.

### U10. Execution-spec schema + workflow-script emitter (R9 keystone)

**Requirement:** R9, R3, R10.

**Tier:** opus / high.

**Work:** define the structured execution-spec (units, per-unit `{model, effort}`, return contracts,
dependency barriers, escalations, enumerated fan-out targets) and the emitter that produces a runnable
Claude Code workflow script from it. Assert the pilot↔fan-out same-tier invariant (R3) and enumerated-target
reconciliation (R10) at emit time. This plan's own sibling `.workflow.js` is the worked reference.

**Files:** new `plugins/saga/scripts/<execution_spec>.py` + emitter, `plugins/saga/references/` doc.

**Failure modes:** a fan-out unit without an enumerated target list must fail emit (R10); a pilot at a
different tier than its fan-out must fail emit (R3); budget-exhaustion guidance baked into generated
cheap-tier agents (cap output, mandatory emit, skim, batch).

**Test:** `tests/test_workflow_emitter.py` (new) — a spec emits a valid script with per-unit tiers; missing
enumerated targets and mis-tiered pilots are rejected.

**Dependencies:** U2, U6 merged (Epic 0 + Epic 1 barrier).

### U11. team-execution markdown emitter + saga pointer (R9 second emitter)

**Requirement:** R9, KD4.

**Tier:** sonnet / high.

**Work:** a second emitter from the same spec producing the `## Team Structure` markdown (mirroring
`team-execution/SKILL.md:234`); saga records the `orchestration_ref` pointer. The governance choice selects
the emitter.

**Files:** the emitter beside U10's, `plugins/saga/scripts/saga.py` (pointer recording reuse).

**Failure modes:** the markdown must match the existing template's parsed structure (workers/reviewers/
validators/gates); never vendor team-execution machinery.

**Test:** `tests/test_team_emitter.py` (new) — the same spec yields valid Team Structure markdown.

**Dependencies:** U10 (shares the spec schema).

### U12. Capability-portable degradation (R11)

**Requirement:** R11.

**Tier:** opus / high.

**Work:** every authored plan carries a runnable inline/serial baseline; on off-host resume re-check the
Workflow tool, surface a one-line downgrade, and recompile only the orchestration tier down to
team-execution/inline with unit specs + per-unit tiers preserved. Record the downgrade.

**Files:** `plugins/saga/scripts/lifecycle_state.py` (capability re-check), the emitter (baseline embed),
saga record.

**Failure modes:** AE3 — off-host resume must downgrade with a note, never error or silently run nothing;
unit tiers must survive the recompile.

**Test:** `tests/test_capability_degrade.py` (new) — AE3.

**Dependencies:** U10.

### U13. Override-rate surface (R12 analysis half)

**Requirement:** R12.

**Tier:** sonnet / high.

**Work:** a `/retro`/`/optimize` pass that reads U3's recorded data and surfaces override-rate, over/under-
tier, and budget-exhaustion signals. Operational measurement accrues post-merge; this builds the surface.

**Files:** `plugins/saga/skills/retro/SKILL.md` (or `optimize`), a small reader helper.

**Failure modes:** zero-data must report "no data yet," not divide-by-zero; the surface is read-only.

**Test:** `tests/test_override_rate.py` (new) — recorded fixtures → correct rate; empty → graceful.

**Dependencies:** U3 (the recorded field).

### U14. Cheap-tier mechanical executor agent (R16)

**Requirement:** R16.

**Tier:** sonnet / high (authoring; the agent itself runs **haiku**).

**Work:** one `model: haiku`, Bash-only, op-discriminated executor agent, dispatched by saga commands and
inert until called. Designing the op-discrimination + dispatch contract is the judgment; the runtime is
haiku.

**Files:** new `plugins/saga/agents/mechanical-executor.md` (or the owning plugin), dispatch wiring in the
saga skills that use it, release triad bump.

**Failure modes:** must be inert until dispatched (no auto-trigger); Bash-only tool scope; op-discriminated
so an unknown op is rejected, not guessed.

**Test:** `tests/test_mechanical_executor.py` (new) — frontmatter pins haiku + Bash-only; op-discrimination
rejects unknown ops.

**Dependencies:** U2 merged (Epic 0 barrier — needs the tier rule).

### U15. Release-triad sync guard (R17)

**Requirement:** R17.

**Tier:** sonnet / medium.

**Work:** a guard (test or hook) that fails when `plugin.json` version, `.claude-plugin/marketplace.json`,
and `CHANGELOG.md` disagree on a version-bearing change.

**Files:** new `tests/test_release_triad.py` and/or a hook entry.

**Failure modes:** must fire only on version-bearing changes; clear message naming the drifting surface.

**Test:** `tests/test_release_triad.py` (new) — a seeded mismatch fails; a synced triad passes.

**Dependencies:** U2 (Epic 0 barrier).

### U16. SHA-stamp stager + stale-main guard (R18)

**Requirement:** R18.

**Tier:** sonnet / medium.

**Work:** a SHA-stamp stager and a stale-main-after-squash guard, scoped to this repo, closing the remaining
release rituals.

**Files:** new `tests/test_release_rituals.py` and/or `tools/` helpers.

**Failure modes:** this-repo-local only (do not assume the idiom cross-repo); the stale-main guard must not
false-fire on a legitimately current main.

**Test:** `tests/test_release_rituals.py` (new).

**Dependencies:** U2 (Epic 0 barrier).

### U17. Final verification + journal

**Requirement:** all (closure).

**Tier:** opus / high.

**Work:** run the full gate fleet-wide (`ruff format --check`, `ruff check`, the two validators, `pytest`,
`mypy`), confirm green, write the `DECISIONS.md` + `LEARNINGS.md` entries the campaign earned, and a
reconciliation report mapping every R-ID (R1–R18) to its landed unit (no silent skips). The reconciliation
**must** flag two things explicitly: **R4** as `applied-inline — operator confirm done` (it is not built by
any unit), and any epic left as an **unmerged open PR** (a non-required epic that did not merge, or a
saga.py-conflict HALT) so nothing is silently dropped.

**Files:** `docs/engineering-journal/{DECISIONS,LEARNINGS}.md`, a final report under `docs/analysis/`.

**Test expectation:** none — it *runs* the suite rather than being tested by it.

**Dependencies:** all prior units merged.

## Execution Spec (the workflow shape)

This is the R9 spec demonstrated by hand — the sibling
[`2026-06-21-saga-tiering-and-execution-campaign.workflow.js`](./2026-06-21-saga-tiering-and-execution-campaign.workflow.js)
encodes it. Each unit is one `agent()` call at its tier; epics are PR-isolated phases.

**Phases and barriers.** `Preflight` (U1) → `parallel(Epic 0 {U2,U3}, Epic 1 {U4,U5,U6}, Epic 3
{U7,U8,U9})` → barrier (E0+E1+E3 merged) → `parallel(Epic 2 {U10,U11,U12,U13}, Epic 4 {U14,U15,U16})` →
`Final` (U17). Epic 2 needs E0+E1; Epic 4 needs E0; Epic 3 is fully independent. Within an epic, units run
serially on one worktree+branch (no intra-epic race) and land as one PR; epics run in parallel.

**Per-unit tier table (KTD2).**

| Unit | Epic | `model` | `effort` | Shape |
|---|---|---|---|---|
| U1 | pre | haiku | low | verification barrier |
| U2 | 0 | sonnet | high | mechanical edits across 5 release triads |
| U3 | 0 | sonnet | medium | bounded field plumbing |
| U4 | 1 | sonnet | high | additive, wire-frozen, test-gated |
| U5 | 1 | opus | high | prose judgment + drift-guard design |
| U6 | 1 | opus | high | the load-bearing routing change |
| U7 | 3 | sonnet | high | greenfield hook harness |
| U8 | 3 | sonnet | high | heuristic, bounded |
| U9 | 3 | sonnet | medium | mechanical once manifest decided |
| U10 | 2 | opus | high | keystone spec + emitter |
| U11 | 2 | sonnet | high | mirrors existing template |
| U12 | 2 | opus | high | degradation semantics |
| U13 | 2 | sonnet | high | analysis pass, bounded |
| U14 | 4 | sonnet | high | authoring the dispatch contract |
| U15 | 4 | sonnet | medium | bounded guard |
| U16 | 4 | sonnet | medium | bounded, this-repo-local |
| U17 | fin | opus | high | final verify + journal |

**Safety model.** The oracle is the test suite + the two validators + the drift-guards (no human review
mid-run, per KTD3). Each epic agent runs the full local gate before opening its PR, fetches+rebases latest
main (KTD9), then merges only when all 5 CI checks are conclusively SUCCESS. A budget floor checkpoints the
run; a circuit breaker halts on repeated gate failure. The run HALTS on a preflight drift (U1) or a failed
barrier (a required epic PR not merged). A non-required epic that does not merge (E3 alone, or a wave-2
epic) is left as an open PR and surfaced at completion — never force-merged.

**Full-hands-off readiness (the explicit review lens).** Three properties make the unattended run safe to
leave: **(1) the merge gate** is the agent confirming all-SUCCESS with a plain `--squash` (no `--admin`
bypass) — and because `main` is unprotected, the gate-fix loop is constrained so it cannot game its own
oracle (KTD3); **(2) recoverability** — every HALT (preflight drift, dead agent, exhausted budget, a
saga.py conflict) is resumable via `resumeFromRunId`, which returns cached results for completed units and
re-runs only from the first incomplete one, so a transient failure costs a resume, not a redo; **(3) no
outward irreversibility** — merging the epics cuts **no release** (the CI `publish` job runs only on
`refs/tags/*`, verified), so nothing is published, deployed, or tagged autonomously. The standing residual
is that the merge gate is enforcement-by-prose until branch protection is enabled (R-RISK-1).

**Rate-limit discipline (operator-requested).** The topology is deliberately narrow-concurrency, not max
fan-out: wave 1 runs ≤3 concurrent epic agents (one per epic; units within an epic are serial), wave 2 ≤2.
CI-status polling sleeps between polls (≈25 s, capped at ~30 polls ≈ 12 min, then report-pending-and-stop,
never a tight loop). The Workflow runtime retries an agent on transient API errors before returning null; a
null/dead agent after those retries is treated as a (possibly rate-limit) HALT — surfaced, not swallowed —
and the whole run resumes later via `resumeFromRunId`. The per-epic gate-fix loop is capped (3 attempts) so
a stuck unit cannot burn the budget hammering the API.

**Out of the workflow (R4 — a REQUIRED operator step, tracked).** R4's global `~/.claude/CLAUDE.md` tier
rule is applied inline with operator confirmation (KTD8), not by an autonomous agent — but Epic 0's success
("the tier rule is loaded every session") **depends on it**, so it is not optional. U17's reconciliation
lists R4 explicitly as `applied-inline — operator must confirm done`, so a forgotten R4 shows up as an open
item rather than silently leaving Epic 0 incomplete.

## Scope Boundaries

In scope: all 17 units above (the 15 ideation survivors organized as 5 epics, plus the tiering-seam
resolution), built via the one workflow.

Out of scope:
- The revivable cuts (doc2 R1-R7; doc1 R-items) unless explicitly revived.
- Cross-host **routing** (shipping a workflow to a capable host); only the degradation path (R11) is in.
- Redesigning the enum into a continuous spectrum or two-axis vocabulary.
- Editing the global `~/.claude/CLAUDE.md` from inside the workflow (KTD8 — inline only).

Deferred to Follow-Up Work:
- Re-weighting any recommender default — blocked on real override-rate data (R12 measures; it does not
  re-weight).

## Risk Analysis & Mitigation

**R-RISK-1 — `main` is unprotected, so the autonomous merge gate is enforcement-by-prose (the top
full-hands-off risk).** GitHub requires no checks, so a buggy poll or a gamed gate could land a red PR on
main. *Mitigation (in-harness):* merge only on all-SUCCESS (pending / null / FAILURE → do-not-merge), plain
`--squash` not `--admin`, and a gate-fix loop that may not weaken tests / delete assertions / add ignore
comments (cap 3). *Mitigation (operator, recommended):* enable branch protection with the 5 checks so
GitHub enforces the gate — the real fix that removes the enforcement-by-prose residual; an infra call left
to the operator.

**Autonomous edits to load-bearing logic (U6 recommender, U10 spec) + the gate-fix loop gaming its own
oracle.** A subtle recommender regression mis-routes every future job; worse, an unattended "fix until
green" agent could make a red gate pass by weakening the very test that guards it. *Mitigation:*
AE1/AE2/overlap/docs-gating tests gate U6; the drift-guard (U5) catches purpose-list erosion; the harness
SPEC forbids test/assertion-weakening and ignore-comments in gate-fixes and caps the loop, so the oracle
stays trustworthy; a red gate blocks the merge.

**`marketplace.json` double-`]` corruption during the U2 triad bumps.** *Mitigation:* `python3 -m json.tool`
validation in U2; U7 makes it structurally unrepresentable thereafter (and U7 is in the parallel first
wave).

**Cross-epic `saga.py` conflict (U3 vs U4).** *Mitigation:* KTD9 rebase-before-merge; both are small,
additive edits authored in disjoint regions. **A genuine rebase conflict in saga.py is NOT auto-resolved** —
the epic halts unmerged for operator review (KTD9 guardrail), rather than an autonomous agent reconciling
load-bearing code.

**Cheap-tier budget exhaustion in generated agents (R9).** *Mitigation:* U10 bakes the
`workflow_structuredoutput_budget` lesson (cap output, mandatory emit, skim, batch) into emitted cheap-tier
agents; re-run only failed indices.

**PR/CI volume (5 epic PRs + CI each).** *Mitigation:* epic-grouped PRs (not per-unit) keep it to ~5 CI
runs; epics parallelize; a budget floor checkpoints for resume.

**API rate limits during the unattended run (operator-requested).** Many tiered agents + polling loops risk
throttling. *Mitigation:* narrow concurrency (≤3 wave-1 / ≤2 wave-2 agents, serial units within an epic),
CI polls sleep ≈25 s and cap out to report-pending (no tight loop), the runtime retries transient API
errors, and a post-retry dead agent HALTs the run resumably (`resumeFromRunId`) rather than failing hard.
A rate-limit interruption costs a resume, not a restart.

## Dependencies / Assumptions

- **Sequencing:** Epic 0 precedes Epic 2 (U10) and Epic 4 (U14-U16); Epic 1 precedes Epic 2; Epic 3 is
  independent. Encoded as workflow barriers.
- **Capability gate:** dynamic workflows run on Claude Code only — this is why the offer omits the option
  off-host and why R11 (degradation) exists. The workflow itself requires the Workflow tool to run.
- **Verified facts (2026-06-21, 7-plugin tree):** 4 callable agents unpinned (coach exempt); zero hooks;
  `adversarial_confidence` already a recommender trigger (`lifecycle_state.py:163`); `cc-workflows-ultracode`
  carried in persisted sagas (why R8 freezes it); recommender tested in `tests/test_saga_plugin.py`; the two
  validators are `marketplace/validator/validate.py` + `scripts/validate_plugins.py`.
- **Doc-review-verified (full-hands-off):** the CI `publish` job runs **only** on `refs/tags/*`
  (`.github/workflows/ci.yml:158`), so merging the epics cuts no release autonomously; and `main` is
  currently **unprotected** (no GitHub-required checks) — the merge gate is the harness's poll discipline,
  which R-RISK-1 hardens and recommends fixing via branch protection.
- **Assumption:** the Workflow tool's per-agent `model`/`effort` overrides and `budget` API are stable —
  R3, R9, R12 and this campaign's own harness depend on them.
- **Assumption (resumability):** the harness is restart-safe via `resumeFromRunId` — completed `agent()`
  calls return cached results, so any HALT (preflight drift, a dead/rate-limited agent, exhausted budget, a
  saga.py conflict) resumes from the first incomplete unit rather than from scratch.
- **Release-surface obligation (cross-cutting):** every epic that changes plugin behavior bumps the release
  triad in the same PR (CLAUDE.md §6). Epics 0-2 modify saga; Epic 3 adds hooks to a plugin; Epic 4 adds an
  agent — each carries it.

## Success Metrics

- **Epic 0:** no saga-dispatched subagent runs richer than its work warrants; the tier rule is loaded every
  session.
- **Epic 1:** the offer makes consensus-via-workflows legible without opening the contract; the drift-guard
  fails if a future rebuild drops a purpose; AE1/AE2 pass.
- **Epic 2:** a dynamic pick yields a runnable, correctly-tiered artifact with no silent-skip path; off-host
  resume degrades with a recorded note (AE3).
- **Epic 3:** the double-`]` corruption cannot reach a commit (AE5); a code-only `feat`/`fix` with no journal
  entry is nudged (AE6).
- **Epic 4:** mechanical handoff runs on haiku; the release triad cannot drift silently.
- **Campaign:** the full gate is green on main; the U17 reconciliation maps every R-ID to a landed unit.

## Sources / Research

- Requirements: `docs/brainstorms/2026-06-20-saga-tiering-and-execution-campaign-requirements.md`.
- Grounding (`file:line`): `plugins/saga/scripts/lifecycle_state.py:148-163` (the `or needs_consensus`
  hard-force + the existing `adversarial_confidence` branch); `plugins/saga/scripts/saga.py:71`
  (`ORCHESTRATION_MODES`), `:1077` (`--orchestration-mode` choices); `plugins/saga/skills/plan/SKILL.md:253`
  (the offer under-sell); `plugins/saga/references/operator-choice.md` §3.2 / §4 / §6; `team-execution/SKILL.md:234`
  (the markdown template); recommender tests in `tests/test_saga_plugin.py`; validators at
  `marketplace/validator/validate.py` + `scripts/validate_plugins.py`.
- The plan→script reference: `infiquetra-context-library/scripts/context-fleet-audit.workflow.js` (per-agent
  `{model, effort}`, pilot↔fan-out same-tier invariant, enumerated-target reconciliation / the silent-skip
  lesson behind R10, budget floor + circuit breaker, rebase-before-merge).
- Journal: `DECISIONS.md` `#operator-choice-framework`; `LEARNINGS.md` 2026-06-13 (the team↔workflow line is
  governance, not review depth); the `workflow_structuredoutput_budget` lesson (binds R9's cheap-tier agents).
