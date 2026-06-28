---
title: "capability: team-spawn residency guard — warn-first hook for nameless team-family spawns"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
---

# capability: team-spawn residency guard — warn-first hook for nameless team-family spawns

### Objective
---
date: 2026-06-28
topic: team-spawn-residency-guard
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md (survivor R6 — team-spawn guard hook, warn-first PreToolUse; VECU te v3.13.0 B3a)
---

# Team-Spawn Residency Guard

## Summary

A warn-first `PreToolUse` hook that fires when the orchestrator spawns a team-execution agent in a
role that cycles through the review/remediation loop (a reviewer or tester) **without the
named-persistent-teammate shape** — and nudges that the teammate will re-pay its full context on every
cycle instead of keeping its prompt cache warm via `SendMessage`. It is advisory: it emits guidance
through `additionalContext` and **never blocks** the spawn. It is the runtime **observability** layer
for the named-teammate residency protocol defined in the S-1 worker-cache-scheduling plan (U3 workers,
U4 reviewers) — a protocol KTD4 deliberately keeps as silently-violable markdown prose. The hook
observes that protocol; it does not enforce it.

## Problem Frame

The team-execution protocol runs reviewers through up to three consensus cycles
(`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:54`) and validators
through a remediation loop (`validator-spawn-quirks.md:42`). A persistent **named** teammate would keep
its prompt cache warm across those cycles and be re-addressable via `SendMessage`; a teammate spawned
one-shot re-pays full context every cycle. That is the creation-tax-vs-carry-cost waste the
worker-cache-scheduling cost model names.

**That residency is not practiced today — it is the unbuilt S-1 protocol.** Today the consensus loop
re-runs each sub-threshold reviewer as a **fresh re-spawn**
(`consensus-protocol.md:51` — "Re-run B3a..B3d for ONLY the reviewers that scored < 9.0"), with no
persistence. The named-teammate residency that makes one-shot spawning wasteful is introduced by the
S-1 plan: **U3** ("one named persistent teammate per resident worker — `Agent` `name` +
`run_in_background` — reuse across units via `SendMessage`, no per-unit re-spawn") and **U4**
("Review-loop reviewer residency — independent quick win": re-engage the same named reviewer via
`SendMessage` for the `<9.0` re-review, no fresh re-spawn). Both are planned, not shipped
(`docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`).

KTD4 (`docs/engineering-journal/DECISIONS.md:1312`) deliberately keeps this residency as a behavioral
markdown protocol — "validated by `/doc-review` + operator runs + headroom telemetry," not code. That
is a principled choice, but a prose protocol is silently violable: once U3/U4 rewrite the prose to say
"spawn named teammates," the orchestrator can still forget the `name`, the run still **succeeds**
(correct output, just more expensive), and nothing surfaces the slip until a later retro reads
telemetry. A residency leak never fails a gate, so it is invisible by construction. There is no
spawn-shape guard anywhere today — `plugins/saga/hooks/hooks.json` watches SessionStart, Edit/Write
JSON validity, Bash pre-push, and PostToolUse journal nudges, but nothing watches the *shape* of an
agent spawn.

## Key Decisions

- **D1 — Warn-only, never block.** The hook emits advisory `hookSpecificOutput.additionalContext` and
  exits 0; it never denies the spawn. The anti-pattern's cost is *efficiency* (re-paid cache), not
  correctness or safety, so a block is disproportionate — and legitimate one-shot uses of team-family
  agents exist (D3, D4). This mirrors the warn-only `stale_main_session_hook.py:238-245`
  (`additionalContext` + non-blocking exit) and contrasts the blocking `pre_push_gate_hook.py:172`
  (which blocks because a failed push gate is a safety/correctness issue).

- **D2 — The signal is a `team-family subagent_type` spawned without the named-persistent-teammate
  shape.** Per S-1 U3 the persistent-teammate spawn is `Agent` `name` + `run_in_background`; a
  team-family agent lacking that shape has no durable `SendMessage` handle (KTD3,
  `DECISIONS.md:1310`), so it cannot be re-addressed across cycles — it is one-shot by construction.
  The exact field predicate (a missing non-empty `name`, and whether `run_in_background` is also
  required) is confirmed by the feasibility probe (Dependencies), not assumed here.

- **D3 — Scope the trigger set to residency-benefiting roles, not all 25 team-execution agents.** This
  decision determines whether the hook helps or becomes noise. The roster
  (`plugins/team-execution/agents/`, 25 agents) includes roles whose **residency value is low** — a
  scanner or monitor inspects fresh artifacts each run and carries little reusable context, so even when
  it re-runs (`validator-spawn-quirks.md:42`) it gains little from a warm cache. The
  residency-benefiting roles are the ones that cycle through the consensus/remediation loop:
  **reviewers and testers**. Default trigger set = reviewers + testers; scanners and monitors excluded
  on low-residency-value grounds (not a claim they never re-run). The set lives in a tunable data
  surface sourced from existing registries (R4).

- **D4 — Bias to false positives over false negatives, because the hook is stateless.** A `PreToolUse`
  hook sees one spawn at a time; it cannot know whether *this* reviewer will be re-engaged next cycle —
  and in fact only sub-9.0 reviewers re-enter (`consensus-protocol.md:51`), so a reviewer that passes
  first try is a genuine one-shot. The hook therefore judges spawn *shape* and accepts that some
  warnings are spurious. That is tolerable precisely because a warning is one ignorable advisory line,
  not a block (D1). The design optimizes for "never silently leak residency" over "never warn
  spuriously" — the inverse needs cross-spawn state the hook does not have. The accepted noise is
  documented, not hidden.

- **D5 — Cross-repo-safe silent degradation.** When the trigger-set source is absent — e.g. the hook is
  registered in a repo without team-execution installed — the set is empty and every spawn passes
  silently. Mirrors `pre_push_gate_hook.py:142-144` degrading when its manifest is absent. The hook must
  never break a repo that lacks team-execution.

- **D6 — Structurally standalone, value-coupled to S-1; sequence after U4.** The hook is its own
  artifact — its own issue and hook file — honoring the operator's reversal of the original `/ideate`
  fold (A5 was folded into S-1's wave-spawning, then revived as a standalone warn-first hook,
  `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:333,312`). But the discipline it observes is
  introduced by S-1 U3/U4, so it is **not** independent in value: it should ship **after U4** (the
  reviewer-residency "independent quick win"), the earliest point its trigger guards a real protocol.
  Shipping it before any residency protocol exists would warn about violating a rule nobody has adopted
  — premature noise. This is the same filed-but-sequenced pattern as R1 gated by S-2 (#279). When U3
  lands, worker roles can be added to the trigger set (R4) additively.

## Requirements

**Trigger & detection**

- R1. The hook fires on `PreToolUse` for the subagent-spawn tool and reads `tool_name` + `tool_input`
  from stdin — the fields the existing `PreToolUse` hooks read (`pre_push_gate_hook.py:122-128`). It
  does not assume those are the only envelope fields; the spawn tool's name and input shape are
  confirmed by the feasibility probe (Dependencies).
- R2. The hook warns when `tool_input.subagent_type` is in the team-family trigger set AND the spawn
  lacks the named-persistent-teammate shape (a non-empty `name`; plus `run_in_background` if the probe
  confirms it is required, per S-1 U3).
- R3. The team-family trigger set defaults to team-execution **reviewer and tester** roles; scanner,
  monitor, and operational roles are excluded (D3).
- R4. The trigger set is sourced from the existing maintained registries — reviewer roles from
  `reviewer-registry.md`, tester roles from `validator-registry.md`'s `## Testers` section — with an
  explicit operator override list. It does **not** introduce a new standalone manifest (which would be
  dead-wiring with no producer). If a derived set drifts from the registries, that is caught by reusing
  the registries as the single source.
- R5. Any spawn whose `subagent_type` is outside the trigger set, or that already carries the
  persistent-teammate shape, passes silently (exit 0, no output).

**Warning behavior**

- R6. On a trigger match, the hook emits a single advisory message via
  `hookSpecificOutput.additionalContext` and exits 0 — it never blocks, denies, or mutates the spawn
  (D1). It **observes**; it does not enforce.
- R7. The advisory names the specific agent, states that a one-shot spawn forfeits prompt-cache reuse
  across the review/remediation cycles, and points to the fix: give the teammate the persistent shape
  (`name` + `run_in_background`) so it persists and is re-addressable via `SendMessage` (per S-1 U3/U4).
- R8. The advisory is concise — the operator reads it inline mid-run. It states the residency cost in
  one line, not a lecture.

**Robustness & safety**

- R9. A malformed or unparseable hook envelope passes through silently (exit 0); the hook never blocks a
  spawn on its own error (mirrors `pre_push_gate_hook.py:118-120`).
- R10. When the trigger-set source is absent or unreadable, the set is empty and all spawns pass
  silently (D5).
- R11. The hook adds no perceptible latency to spawning — a stdin-read plus set-membership check, with
  no subprocess, per-call file-walk, or network I/O on the hot path (the registry-derived set is read
  once / cached, not re-walked per spawn).

**Registration & tests**

- R12. The hook is registered as a `PreToolUse` entry in `plugins/saga/hooks/hooks.json`, matcher scoped
  to the spawn tool confirmed by the probe, alongside the existing JSON-validate and pre-push-gate
  `PreToolUse` hooks.
- R13. The hook factors its trigger decision into a pure function (input: parsed `tool_input` + trigger
  set; output: warn-or-silent) with unit tests over that surface — trigger match → warn; persistent
  shape present → silent; non-team `subagent_type` → silent; trigger-set source absent → silent;
  malformed envelope → silent. (The existing hooks already isolate pure predicates such as
  `_is_git_push_command`; this hook follows that style.)

## Scope Boundaries

- Warn-only. No blocking mode and no `--strict` escalation in v1; revisit only if telemetry shows the
  warning is routinely ignored *and* the leak is costly.
- Stateless. No cross-spawn tracking of "did this agent get re-engaged" — that is the deliberate D4
  tradeoff.
- The hook nudges; it does not act. It does not assign a name, rewrite the spawn, or auto-persist the
  teammate.
- It does not enforce the residency protocol (KTD4 keeps that in prose); it only surfaces violations.
- Not a security control. It guards an efficiency discipline, not a safety boundary (contrast the
  pre-push gate).

## Dependencies / Assumptions

- **Sequenced after S-1 U4.** The discipline the hook observes is introduced by the S-1 plan — U3
  (worker residency) and U4 (reviewer residency, the "independent quick win") in
  `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`. The default reviewer/tester trigger
  binds on **U4**; worker coverage binds on U3. The hook is filed now as a standalone issue with this
  dependency recorded (mirrors R1 gated by S-2), not built before U4 lands.
- **Go/no-go feasibility probe (resolve before planning, see Outstanding Questions).** The exact
  `tool_name` the `PreToolUse` hook observes when a subagent is spawned, and which `tool_input` fields
  carry the persistence shape (`name`, and whether `run_in_background` is also required). This repo's
  harness exposes an `Agent` tool with `name` / `subagent_type` / `run_in_background`; stock Claude
  Code's native subagent tool is `Task`. The R12 matcher and the R2 predicate both hinge on this.
  `name` and `subagent_type` *are* `tool_input` fields, so the signal is hook-visible in principle (the
  favorable inverse of R14's profile-visibility problem) — but the precise tool name and field set must
  be confirmed against a live spawn before R1/R2/R12 are buildable as written.
- The trigger-set producer already exists: `reviewer-registry.md` (reviewer roles) and
  `validator-registry.md`'s `## Scanners` / `## Testers` / `## Monitors` / `## Operational` taxonomy
  (tester roles to include, scanner/monitor/operational to exclude). Verified present: 25 agents in
  `plugins/team-execution/agents/`.
- Residency benefit is real for the loop once U3/U4 land: persistent named teammates preserve prompt
  cache across cycles (the worker-cache-scheduling cost model, `DECISIONS.md:1297-1318`). The hook does
  not re-litigate that premise; it observes the discipline that protocol assumes.

## Outstanding Questions

**Resolve before planning**

- Confirm the spawn tool-name and the persistence-field set against a live spawn (the go/no-go probe
  above). This gates R1/R2/R12 — if the spawn tool the hook sees carries neither `name` nor
  `subagent_type`, the hook is not buildable as specified and the design must change. Make this `/plan`'s
  first task (the R14-style "first task is the feasibility matrix" pattern).

**Deferred to planning**

- Enumerate the exact default reviewer/tester role list from the registries and confirm the
  scanner/monitor/operational exclusions against the 25-agent roster. The split is decided (D3); the
  enumeration is mechanical.
- Whether the trigger set is computed from the registries at hook-load and cached, or materialized into
  a data file beside the hook (a layout choice; R4 fixes the *source*, not the cache strategy).
- Whether the warning debounces within a single run (warn once per agent per session vs every spawn) — a
  polish question.

## Sources / Research

- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:312,333,37` — R6 survivor: A5 folded into S-1's
  wave-spawning, then revived as a standalone warn-first hook.
- `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md` — S-1 plan; **U3** (worker residency:
  named persistent teammate = `Agent` `name` + `run_in_background`, `SendMessage` reuse) and **U4**
  (reviewer residency, the "independent quick win": re-engage the named reviewer via `SendMessage`, no
  fresh re-spawn). The protocol this hook observes; unbuilt.
- `docs/engineering-journal/DECISIONS.md:1297-1318` — worker×model cache scheduling. KTD3 (durable
  `SendMessage` handle); KTD4 (residency is markdown protocol, validated by `/doc-review` + operator
  runs + telemetry — the prose-protocol the hook makes observable).
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:44-54` — consensus
  re-runs ONLY sub-9.0 reviewers (`:51`), as fresh re-spawns today; ≤3 iterations (`:54`).
- `plugins/team-execution/skills/team-execution/references/validator-spawn-quirks.md:42` — "Re-run only
  validators affected by remediation" (scanners can re-run; their residency value is still low).
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` /
  `validator-registry.md` — the trigger-set producer (reviewer roles; scanner/tester/monitor taxonomy).
- `plugins/saga/hooks/pre_push_gate_hook.py:118-128,142-144,172` — `PreToolUse` stdin shape
  (`tool_name` + `tool_input`), silent-degrade-on-absent-manifest, malformed-envelope passthrough,
  blocking exit (the contrast to warn-only).
- `plugins/saga/hooks/stale_main_session_hook.py:238-245` — warn-only `additionalContext` + non-blocking
  exit precedent.
- `plugins/saga/hooks/hooks.json` — current hook registry (no spawn-shape guard).

### Intent

The team-execution review and remediation loops re-engage reviewers and testers across up to three
cycles. Once S-1 U3/U4 make those teammates named-persistent, spawning one **without** a `name`
silently forfeits prompt-cache reuse and re-pays full context every cycle — the creation-tax-vs-carry-cost
waste the worker-cache cost model names. KTD4 keeps that residency as un-enforced markdown prose, so the
slip never fails a gate and is invisible until a retro reads telemetry. This warn-first `PreToolUse` hook
surfaces the nameless team-family spawn shape at the moment it happens: runtime **observability** for a
discipline the engine deliberately left in prose. Warn-only (exit 0); it never blocks.

### Out-of-scope / non-goals

- Blocking or denying spawns — warn-only, exit 0 (D1).
- Enforcing the residency protocol — KTD4 keeps it prose; this only observes/surfaces violations.
- Cross-spawn state or tracking whether an agent is later re-engaged — stateless by design (D4).
- Assigning names, rewriting spawns, or auto-persisting teammates — it nudges, it does not act.
- A security control — it guards an efficiency discipline, not a safety boundary.
- Building before S-1 U4 (reviewer residency) lands — filed now, sequenced after U4.

### Files expected to change

- `plugins/saga/hooks/team_spawn_residency_hook.py` — new warn-only PreToolUse hook (pure decision fn + stdin shim)
- `plugins/saga/hooks/hooks.json` — register the new PreToolUse entry, matcher scoped to the spawn tool
- `tests/test_team_spawn_residency_hook.py` — unit tests over the decision surface
- `plugins/saga/.claude-plugin/plugin.json` — version bump (release surface)
- `plugins/saga/CHANGELOG.md` — changelog entry
- `.claude-plugin/marketplace.json` — marketplace version sync

### Tests to add or update

- `tests/test_team_spawn_residency_hook.py` — covering: nameless team-family spawn → warn; persistent
  shape (`name` + `run_in_background`) → silent; non-team `subagent_type` → silent; trigger-set source
  absent → silent; malformed envelope → silent.
- Version-drift guard (`tests/test_release_triad.py` or equivalent) if the saga release surfaces change.

### Context library links
- source_context: docs/brainstorms/2026-06-28-team-spawn-residency-guard-requirements.md

### Acceptance criteria

- [ ] Go/no-go probe resolved first: `grep -rE "Task|Agent" plugins/saga/hooks/team_spawn_residency_hook.py` confirms the matcher targets the real spawn tool-name and the predicate reads the real persistence fields (`name`, `run_in_background`) — established against a live spawn before R1/R2/R12 are built.
- [ ] Nameless team-family spawn warns: `printf '{"tool_name":"Task","tool_input":{"subagent_type":"security-reviewer"}}' | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"` prints an `additionalContext` advisory naming the agent and exits `exit=0`.
- [ ] Named persistent teammate is silent: the same envelope plus `"name":"sec-1","run_in_background":true` produces no output and `exit=0`.
- [ ] Non-team `subagent_type` is silent: `printf '{"tool_name":"Task","tool_input":{"subagent_type":"general-purpose"}}' | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"` produces no output and `exit=0`.
- [ ] Trigger-set source absent → silent degrade: with the team-execution registries unreadable, any team-family spawn produces no output and `exit=0`.
- [ ] Malformed envelope passes through: `printf 'not json' | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"` does not block and exits `exit=0`.
- [ ] Unit suite green: `uv run pytest tests/test_team_spawn_residency_hook.py` reports all tests passed.
- [ ] `hooks.json` stays valid after registration: `python3 -m json.tool plugins/saga/hooks/hooks.json` exits `0`.

### Verification

```bash
# Decision-surface unit tests
uv run pytest tests/test_team_spawn_residency_hook.py -v

# Lint, format, type (CI gate parity)
uv run ruff check plugins/saga/hooks/
uv run ruff format --check plugins/saga/hooks/
uv run mypy plugins/saga/hooks/team_spawn_residency_hook.py

# Manual decision checks: nameless team-family → advisory; named → silent
printf '{"tool_name":"Task","tool_input":{"subagent_type":"security-reviewer"}}' \
  | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"
printf '{"tool_name":"Task","tool_input":{"subagent_type":"security-reviewer","name":"sec-1","run_in_background":true}}' \
  | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"

# Registration remains valid JSON
python3 -m json.tool plugins/saga/hooks/hooks.json > /dev/null && echo "hooks.json valid"
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-28-team-spawn-residency-guard-requirements.md
- Source type: brainstorm
- Source title: Team-Spawn Residency Guard

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/289
- Number: 289
- Created at: 2026-06-28T15:06:58.707898+00:00

