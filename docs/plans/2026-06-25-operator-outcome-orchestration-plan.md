---
title: Operator Outcome-Orchestration — Implementation Plan
type: feat
status: active
date: 2026-06-25
deepened: 2026-06-25
origin: docs/brainstorms/2026-06-25-operator-outcome-orchestration-requirements.md
review: docs/reviews/2026-06-25-operator-outcome-orchestration-plan-review.md
---

# Operator Outcome-Orchestration — Implementation Plan

## Summary

Build an `OutcomeOrchestrator` into the `saga` plugin: a net-new coordinator over a DAG of leaf sagas
that drives a whole **outcome** across sessions, worktrees, and machines from a thin `/outcome` surface,
with team-execution / mission-control / deploy / cc-workflows-ultracode as per-subplot executors. It is
built whole (all 34 requirements co-equal at release) but along an internal build spine — minimal
coordinator+store → one backend → auto-merge → attention/failure → economics/projection → friend-plugin
reshape — so every step is verifiable as it lands. This plan is a HOW; the WHAT is settled in the origin
requirements doc.

## Problem Frame

The operator already runs multi-subplot outcomes by hand — holding the dependency graph in his head,
hand-writing prompts to other sessions, losing state when a worktree or session dies. That manual
coordination is the cost: attention spent routing instead of deciding, and no measured answer to whether
a DAG of right-sized executions beats one long thread. saga already has the substrate (a durable tick
model, Kahn DAG layering, a backend recommender) but never lifted above a single linear work thread.
This plan lifts it.

## Provenance — multi-engine synthesis

This plan was produced by unifying **three independently-generated plans** — one by Claude (this
session), one by Codex (gpt-5.5, xhigh), one by Antigravity (Gemini 3.1 Pro High) — under a strict
trust-but-verify discipline: no plan's claim about the code was adopted without checking it against the
actual files. The synthesis takes Codex's unit backbone and node/store schemas (the strongest), Claude's
honest cache-ledger boundary and the verification corrections, and Antigravity's rebase-attempt cap and
Mermaid cockpit. Where the three diverged, the choice and the loser are recorded in **Alternatives
Considered**. The two engines that actually verified (Claude, Codex) independently caught the same two
doc errors (below); Antigravity parroted them — a data point folded into the adjudication.

The plan was then **doc-reviewed by the same three engines** (Claude + Codex + Antigravity), and the
confirmed findings folded back in (this revision). Highlights of that round: the store-durability
mechanics were under-defined (→ KTD15); KTD5 as first written appeared to weaken R27/F5's "non-lossy"
guarantee until cold-re-entry and crash-replay were separated as distinct scenarios (→ KTD5 reframe); the
auto-merge queue needed an expected-base-SHA guard for the manual-merge-during-reverify race (→ KTD7,
refuting one of Claude's own review notes); release-surface sync had to be per-unit not deferred to U11
(→ KTD14); and three unit-boundary sequencing inversions were corrected (U5 owns the PR-state read, U6
the merge action; U8 renders cost gracefully instead of depending on U10; worktree negative state lives
with the worktree lifecycle in U7). Full finding/resolution trail in the linked review artifact.

## Verified grounding (trust-but-verify — load-bearing corrections)

Checked directly against the code this session. Two requirements-doc claims are **corrected**:

- **`recompile_for_tier` is NOT a downgrade-enforcer** (refines R5). It is a by-mode dispatcher
  (`execution_spec.py:708`): `cc-workflows-ultracode` → `emit_workflow_script`, everything else →
  `emit_inline_baseline` (`:719`–`:724`). The downgrade **policy** lives upstream in
  `recheck_orchestration_capability` (`lifecycle_state.py:223`–`309`). Consequence: the dispatcher seam
  (KTD-dispatch) wires the by-mode fork; the **halt-not-degrade and guarantee logic must NOT be injected
  into `recompile_for_tier`** (one of the three input plans proposed exactly that — it would attach the
  policy to the wrong layer). It belongs in the degrade policy.
- **tmux count is 60 lines / ~73 case-insensitive occurrences across 7 files, not 59** (refines R8) —
  `commands/team-setup.md` (37), `CHANGELOG.md` (7), `docs/agent-overflow.sh` (6),
  `references/validator-pane-behavior.md` (3), `README.md` (3), `skills/.../SKILL.md` (2),
  `docs/example_tmux.conf` (2). All vestigial; Phase B executes via native agent subagents
  (`team-execution/skills/team-execution/references/consensus-protocol.md:10` — `SKILL.md:276` is only
  the Phase B heading, not the spawn proof). **The validator-state safety check already
  lives in `team-execution/SKILL.md` Step A5 + `references/validator-evidence-state.md`, not in
  `team-setup`** — deleting `team-setup` does not orphan it; the "re-home" (R8) is near-trivial.

Confirmed as reusable substrate (no correction needed):

- `dependency_layers` (`execution_spec.py:361`) — Kahn layering, `list[list[str]]`, ready-layer at
  `:396`, cycle `SpecError` at `:399`. The frontier engine, reused verbatim.
- `ExecutionSpec`/`Unit`/`Tier` JSON-roundtrip dataclasses (`execution_spec.py:163`–`353`) with
  `validate()` (unique ids, depends_on resolves, no cycle) — the schema-and-validation house pattern the
  outcome spec mirrors.
- `recommend_execution_backend` (`lifecycle_state.py:99`) returns `{recommended, rationale,
  alternatives, omit_ultracode}` over the 3 backends; gated-vs-advisory split + elevated-risk
  suppressor — reused at the frontier.
- `ORCHESTRATION_TIERS = (cc-workflows-ultracode, team-execution, inline)` (`lifecycle_state.py:216`) =
  exactly R23's degrade ladder; `_HOST_DEPENDENT_TIERS = {cc-workflows-ultracode}` → team-execution
  always runs (so degrade only ever bites cc-workflows).
- `save`/`read_ticks`/`restore` (`saga.py:695`/`882`/`870`); one-file-per-tick `<ts>-N.md`
  (`_allocate_envelope_path` `saga.py:593`); `_assert_orchestration_provenance` (`saga.py:630`, the KTD7
  provenance guard). R10/R28's per-leaf immutable files lift this pattern.
- **Store correction-of-emphasis:** `STATE_DIR = Path(".claude/saga")` (`saga.py:44`) is **CWD-relative**
  → today's leaf ticks are per-worktree, not shared. The outcome store (R27) is therefore net-new and
  must root at `git rev-parse --git-common-dir`. **Verified directly:** the common-dir resolves to the
  identical absolute `.git` from a worktree, files written through it land in the shared `.git`, and they
  **survive `git worktree remove`**. The shared-store design is sound.
- Token-absence: literal **zero** `outcome`/`subplot`/`publish` tokens in `saga/scripts` → the
  orchestration layer is genuinely net build.
- `orchestration_ref` (`saga.py:168`) is a single-saga string backend pointer, **not** a parent→child
  link → R20 child recursion needs a new typed field.
- `tests/test_release_triad.py` (330L) guards plugin.json ↔ marketplace.json ↔ CHANGELOG version sync;
  `tests/test_team_execution_plugin.py::test_team_setup_references_existing_assets` asserts the tmux
  assets exist → **R8's deletion turns that test red**; both are release-gate work (U11).

## Key Technical Decisions

The load-bearing HOW choices. Each resolves a deferred-to-planning item from the origin doc.

**KTD1 — Outcome spec = canonical JSON, superset of `ExecutionSpec`.**

`docs/outcomes/<outcome-id>/outcome-spec.json` on the outcome's own branch `outcome/<slug>`. Top-level:
`schema_version`, `outcome_id`, `spec_revision`, `objective`, `nodes[]`, `decision_trail[]`,
`cost_rollup`, `created_at`, `updated_at`. Reuse `dependency_layers` for the frontier and the
`from_dict`/`to_dict`/`validate` house pattern. Rejected Markdown-frontmatter as canonical (the repo's
script tests favor JSON parsers; round-trip determinism) and SQLite (R26 needs branch-carried git
portability).

**KTD2 — Node schema captures the operational state machine in data.**

Each node: `subplot_id`, `title`, `kind` (code|non-code), `state`, `backend`, `gated`, `risky`,
`destructive`, `guarantee_tags[]`, `degrade_policy`, `timeout_seconds`, `heartbeat_seconds`,
`depends_on[]`, `leaf_saga_id`, `child_spec_ref`, `github`, `worktree`, `evidence`, `cost`. Putting
state/liveness/negative-state fields in the node (not implicit from issue titles) is what makes R30–R34
expressible. Rejected deriving structure from GitHub issue titles (R26 makes the spec the structural
source).

**KTD3 — Shared store = git-common-dir cache, never `.claude/saga`.**

Root `$(git rev-parse --git-common-dir)/infiquetra/saga/outcomes/<outcome-id>/` with subdirs `locks/`,
`dispatches/`, `completions/`, `heartbeats/`, `worktrees/`, `offline-queue/`, `ledger/`, `snapshots/`.
**Cache only** (R27): canonical structure is the branch artifact, canonical completion is GitHub. Distinct
from saga's CWD-relative per-worktree leaf ticks (R28). Verified to survive worktree cleanup.

**KTD4 — Completion events = per-leaf immutable JSON, exclusive-create.**

`completions/<subplot-id>-<utc-ts>-<event-id>.json`, written `O_CREAT|O_EXCL`. Shape: `event_id`,
`idempotency_key`, `outcome_id`, `subplot_id`, `leaf_saga_id`, `contract`, `state`, `completed_at`,
`producer`, `evidence`, `cost_delta`, `spec_revision`. Multi-writer-safe by construction (mirrors saga's
one-file-per-tick). Written via temp-file + atomic `os.replace` (never a torn file on crash); a malformed
file found on read is quarantined, not fatal. Rejected a shared append log (the doc-review F2 already
resolved that as unsafe). **Non-code leaves additionally write a durable completion marker to the
canonical store** — close the tracking sub-issue on GitHub and append to the committed spec's
completion log (R11) — so a fresh-machine reconstruct with no cache still sees a non-code leaf as done
and never re-runs it (the side-effect-duplication hole). The cache event is the *fast* signal; the
GitHub/spec marker is the *durable* one.

**KTD5 — Transition ledger lives in the cache; cold re-entry and crash-replay are distinct scenarios.**

Append-only `ledger/ledger.jsonl` in the git-common-dir store (coordinator-only writer; one transition
per line, appended with a torn-trailing-line tolerance on read so a crash mid-append never corrupts
replay). Each line: `transition_id`, deterministic `idempotency_key` =
`outcome:<id>:rev:<rev>:subplot:<id>:action:<action>:attempt:<n>:target:<target>` — the `attempt:<n>`
ordinal lets a retry *after a clean failure* (no side effect occurred) proceed instead of being skipped
as a duplicate of the first attempt — `action`, `from_state`, `to_state`, `inputs_sha256`,
`side_effects`, `outputs`, `status`, `replay_policy`. **Not committed per-transition** (avoids polluting
branch history mid-run — the R21-vs-R26 cadence tension).

The apparent tension with R27/F5 "non-lossy" dissolves once two scenarios are separated. **Cold re-entry
(F5)** is a *rest-state* scenario — the operator returns days later, nothing is mid-transition — so it
reconstructs fully: structure + decision trail + cost from the committed spec, completion from GitHub.
The cache/ledger absence loses nothing because there is no in-flight transition to replay; the "why"
lives in the committed `decision_trail`, so F5 stays non-lossy. **Crash recovery (R30)** is a
*same-machine* scenario — the reconcile loop died where its cache + ledger still live — so fine-grained
replay is available. The only lossy case (a mid-transition crash *and* a machine switch before
reconnect) is a non-scenario for a solo operator, and even it degrades safely to GitHub-truth idempotent
reconcile with no duplicated side effect. Rejected committing the ledger (one input plan did — stronger
cross-machine replay but commits on every transition).

**KTD6 — Reconcile runtime = local `/loop`-hosted `outcome advance`, host-agnostic.**

Default: `outcome advance --loop` inside a `/loop` session; `outcome advance --once` for tests/manual
ticks; scheduled routine is a later lights-out variant on the same entrypoint. Each tick reloads the
branch spec + GitHub issue/PR state + cache files and re-derives the frontier — **no authoritative
in-memory DAG** (crash-tolerant, R29). `/goal` and compiled workflows are executors it dispatches to,
never the host (the R3 collapse).

**KTD7 — Auto-merge = serialized coordinator merge queue, rebase-then-reverify, capped.**

Only the coordinator merges, processing the merge-ready set one at a time. "Clean" = required CI green
AND (team-execution reviewer-consensus met OR `/code-review` clean of P0/P1) AND not risky/destructive
AND base current. Stale base → rebase the leaf onto the updated base, rerun required checks, server-side
squash only if still green. Conflict → fail the leaf back to `work` and page (R32), never a silent skip.
**The final squash is guarded by an expected base-SHA / lease checked immediately before merge**
(`gh pr merge --match-head-commit <sha>`): a manual or external merge that lands on the base *during* the
reverify window fails the squash and reloops, rather than merging a stale tree. Serializing only stops
two *coordinator* merges from colliding — the base-SHA guard is what closes the third-party / manual-merge
race. **Capped at 3** base-churn/reverify cycles per subplot (then halt+page) — guards both the flaky-test
infinite-rebase loop and base-churn starvation. Rejected naive parallel squash and rejected depending on
GitHub's hosted Merge Queue config.

**KTD8 — Heartbeats/timeouts: concrete defaults, override per node.**

Reconcile sleep 300s; autonomous heartbeat every 300s; stale after 900s; hard timeout 7200s for
`cc-workflows`/fork/`/goal`, 14400s for `team-execution`; manual/attended leaves untimed unless set. A
stale-past-timeout leaf with no heartbeat → `stalled` terminal → paged once (R31). DAG validation
(extending `ExecutionSpec.validate` + `dependency_layers`) rejects duplicate ids, self-deps, missing
deps, cycles, unreachable nodes, invalid child specs, and deletion of a dispatched node without a
terminal transition — run before every dispatch (R20 review-before-dispatch).

**KTD9 — Guarantee/degrade = `guarantee_tags[]` + `degrade_policy`, in the degrade layer.**

Defaults: `cc-workflows` fan-out/refute-N, destructive, deployment, migration, or security-sensitive
leaves → `degrade_policy: halt`; autonomous pre-side-effect leaves → `operator_away_one_rung`. Enforced
in the dispatcher/degrade path (extending `recheck_orchestration_capability` with presence + a
side-effect guard), **not** in `recompile_for_tier` (per the verified correction). Aligns with `/work`'s
halt-not-degrade (`work/SKILL.md` §1.5). Degrade applies only before any side effect; a leaf that already
deployed/migrated/wrote HALTs rather than re-running on a lesser backend (R23).

**KTD10 — Child recursion = typed `child_spec_ref`, never overload `orchestration_ref`.**

A node may carry `child_spec_ref` (a child outcome with its own `outcome_id`) — net-new parent→child
link, distinct from the leaf's `leaf_saga_id` and from saga's existing single-saga `orchestration_ref`
backend pointer (untouched). Present → the node IS an outcome; reconcile recurses. **The parent reads the
child's terminal state from GitHub** (the child outcome's tracking issue closed / its terminal PR), NOT
by reading the child's spec file — the child's spec lives on its own `outcome/<child>` branch and is not
present in the parent's worktree, so a cross-branch file read would be required and is avoided. Completion
is canonical in GitHub (R26), so the barrier is a GitHub read; the child's spec matters only to the
child's own reconcile loop. Child recursion is depth-bounded and ancestor-cycle-checked at validation
(a child pointing back at an ancestor fails). This is the promote/lazy-grow mechanism (R21). Rejected
stuffing `child_spec:<path>` into the `orchestration_ref` string (an input plan proposed it — type-unsafe,
conflates two roles) and rejected cross-branch spec reads for the barrier.

**KTD11 — `/outcome` vocabulary: thin coordinator verbs only.**

`start`, `graph`, `advance`, `attend`, `report`, `resume`, `close`, `export`, `import`. Leaf work stays
native `/resume <leaf-saga-id>`, `/work`, `/code-review`, `/qa` — there is no `/outcome work`. `attend`
prints the native re-entry handoff for a leaf the operator wants hands-on (R16 altitude seam).

**KTD12 — Report = derived-on-read markdown with a Mermaid DAG.**

`docs/outcomes/<outcome-id>/report.md`, regenerated from state, never hand-edited. Sections: cockpit
summary, attention queue, **Mermaid graph/frontier**, subplot table, evidence, merge queue, decisions,
cost rollup, offline/replay notes. No operator-writable status field (R17 derived-on-read). The Mermaid
DAG gives the operator a one-glance topology of where the outcome is.

**KTD13 — R8 deletion includes the tests that pin the deleted assets.**

Deleting `team-setup` + the tmux assets turns `test_team_setup_references_existing_assets` red and
touches the validator-state test; both update in the same unit. Keep `validator-evidence-state.md` as the
state-location contract and ensure SKILL.md Step A5 still runs the `.claude/`-ignored check in Phase A
planning + Phase B preflight.

**KTD14 — Release-surface sync is per-unit-per-plugin, NOT deferred to U11.**

`AGENTS.md:104` requires every behavior/schema/command/prompt/guidance change to update its plugin's
release surfaces — `plugins/<p>/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/<p>/CHANGELOG.md`, README/docs, and the drift guards (`tests/test_release_triad.py`,
`tests/test_saga_plugin.py`, `tests/test_team_execution_plugin.py`) — **in the same PR**. So each unit
that changes a plugin carries that plugin's own triad bump (e.g. U4 bumps team-execution when it deletes
`team-setup`). Deferring all of it to U11 would either red the drift guard at every interim merge or ship
a gutted plugin early — the integration bomb both reviewers flagged. **U11 is the final feature-flip
gate**: it advertises the complete `/outcome` surface and asserts the full suite green, after the
per-unit surface updates have already kept each interim merge releasable. Co-equal at release (R4) is
about the *outcome-orchestration feature* shipping whole, not about withholding each plugin's own version
hygiene.

**KTD15 — Store durability + lock mechanics are explicit (not "locks" hand-waved).**

The store primitives all three reviewers flagged as under-defined:

- **Atomic writes.** Every store write (completion event, spec snapshot, report) is temp-file +
  `os.replace`; the ledger appends with `O_APPEND` and tolerates a torn trailing line on read. No reader
  ever sees a partial file; a malformed file is quarantined to `quarantine/`, logged, and skipped.
- **Coordinator singleton lock.** A lease-based `locks/coordinator.lock` (holder id + expiry =
  reconcile-sleep × 3) ensures only one reconcile loop mutates at a time; a second `advance` (a cron tick
  overlapping a manual one, or two machines) no-ops on a held, unexpired lease and reclaims a stale one.
- **Per-subplot dispatch lock** prevents duplicate dispatch (R13), keyed by `subplot_id`, released on a
  terminal transition or lease expiry.
- **GitHub offline / rate-limit policy (R34, made concrete).** Writes queue to `offline-queue/` with a
  retry budget (exponential backoff, cap N); on reconnect, **GitHub is authoritative for completion** —
  a queued mutation superseded by out-of-band server state is dropped (not replayed), structure is
  re-derived from the committed spec, and retry exhaustion pages the operator rather than looping. If the
  cache-only queue is lost before GitHub accepts a write, the intent is re-derived from the spec +
  ledger on the next reconcile (idempotent), never silently dropped.

## Requirements coverage

The build is all-or-nothing at release (R4): every R1–R34 from the origin doc must ship. This matrix is
the completeness checklist — each requirement maps to the unit(s) that satisfy it. Full requirement text
lives in the origin requirements doc.

| R | Concern | Unit(s) |
|---|---|---|
| R1 | distinct OutcomeOrchestrator, reuses saga machinery | U1, U3 |
| R2 | leaves are linear sagas; coordinator never executes | U1, U3 |
| R3 | coordinator degrades only leaves, never collapses | U3, U9 |
| R4 | all components co-equal at release | U11 |
| R5 | single dispatcher seam; HALT-not-degrade receipt | U4, U9 |
| R6 | full executor menu inline/fork/subagent/team/workflow/goal | U4, U9 |
| R7 | recommender at the frontier under budget; override telemetry | U9, U10 |
| R8 | team-execution reshape: strip tmux, delete team-setup, re-home check | U4 |
| R9 | bidirectional envelope; parent-owned barrier predicate | U2, U5 |
| R10 | per-leaf immutable completion files unlock the Kahn layer | U2, U5 |
| R11 | per-subplot completion contract (code→merge, non-code→durable tick) | U5 |
| R12 | auto-merge clean non-gated; rebase-then-reverify; conflict→work | U6 |
| R13 | concurrency safety: locks/idempotency/dup-dispatch prevention | U2, U7 |
| R14 | portable export/import across machines/worktrees | U2, U7 |
| R15 | durable session+worktree per sub-outcome; cap, reap, owner, shared installs | U6 (session/token), U7 (worktree cap/reap/installs) |
| R16 | thin `/outcome` surface; hands into native leaf verbs | U3 |
| R17 | interrupt-handler cockpit; status derived-on-read | U3, U8 |
| R18 | attention consolidator: one ranked page (type-tier then leverage) | U8 |
| R19 | `/outcome report` derived-on-read digest under docs/outcomes/ | U8 |
| R20 | draft-then-review decomposition incl. edge review | U1, U5, U7 |
| R21 | DAG grows lazily / elaborate-in-place / promote | U1, U7 |
| R22 | failure cascade: subtree pauses, siblings run; halt-all | U5, U6, U8 |
| R23 | degrade conditional on presence + side-effect guard | U4, U9 |
| R24 | economics rollup per subplot→outcome; falsifiable thesis | U9, U10 |
| R25 | mission-control secondary portfolio projection | U8 |
| R26 | store split by facet; spec canonical for structure | U1 |
| R27 | git-common-dir pure cache; non-lossy reconstruct | U2 |
| R28 | leaf ticks per-worktree; durable output = merged PR + event | U2, U5 |
| R29 | level-triggered reconcile loop; host-agnostic | U3 |
| R30 | crash/replay: transition ledger + idempotent reconcile | U2, U6 |
| R31 | liveness heartbeat/timeout + DAG validation | U1 (validation), U9 (liveness) |
| R32 | Git/PR/worktree negative terminal states + cascade | U6 (PR/branch), U7 (worktree) |
| R33 | in-flight DAG mutation rules + orphan reconciliation | U1, U7 |
| R34 | GitHub offline/rate-limit degraded mode | U2, U6 |

## Implementation Units

Eleven units, dependency-ordered along the build spine. Each is independently landable; the release stays
hidden until U11 proves all 34 requirements ship together. Per-unit `{model, effort}` tiers are proposed
for a possible cc-workflows execution and confirmed at `/work` time, not here.

### U1. Outcome spec + DAG validation

**Goal:** the canonical outcome spec, its DAG validator, and branch-artifact read/write helpers.

**Files:** `plugins/saga/scripts/outcome_spec.py`, `plugins/saga/references/outcome-spec.md`,
`tests/test_outcome_spec.py`.

**Requirements:** R1, R2, R20, R21, R26, R31 (validation), R33.

**Depends on:** none.

**Test scenarios** (`tests/test_outcome_spec.py`): valid DAG round-trips JSON; duplicate id / self-dep /
cycle / missing dep / unreachable node each fail `validate`; an edge redirect increments `spec_revision`;
an invalid `child_spec_ref` fails before any dispatch.

### U2. Shared store, completion events, transition ledger

**Goal:** the git-common-dir cache layout, the atomic immutable completion-event writer/reader, the
lease-based coordinator + per-subplot locks, the offline queue with its conflict policy, and the
replay-ledger primitives (KTD15).

**Files:** `plugins/saga/scripts/outcome_store.py`, `tests/test_outcome_store.py`,
`tests/test_outcome_replay.py`.

**Requirements:** R9, R10, R13, R14, R27, R28, R30, R34.

**Depends on:** U1.

**Test scenarios:** two leaves write completion files concurrently with no shared-append contention; a
write interrupted mid-flight leaves no torn file (temp + `os.replace`), and a malformed file is
quarantined not fatal; a torn trailing ledger line is tolerated on read; a duplicate idempotency key is
skipped but a retry with a new `attempt:<n>` proceeds; a second `advance` no-ops on a held coordinator
lease and reclaims a stale one; a crash after a side effect but before the commit record replays without
duplicating the effect; on offline reconnect a server-superseded queued write is dropped (GitHub wins for
completion) and retry exhaustion pages; deleting the cache loses no canonical state (reconstruct from spec
+ GitHub); the store path resolves identically from a second worktree.

### U3. Thin `/outcome` command + local reconcile skeleton

**Goal:** the command/skill and the reconcile entrypoint — `start`, `resume`, `advance --once`,
`advance --loop`, `attend`, `export`, `import` — level-triggered and idempotent.

**Files:** `plugins/saga/commands/outcome.md`, `plugins/saga/skills/outcome/SKILL.md`,
`plugins/saga/scripts/outcome.py`, `tests/test_outcome_command.py`.

**Requirements:** R1, R3, R16, R17, R29.

**Depends on:** U1, U2.

**Test scenarios:** `start` creates the branch-local spec + a 2-node DAG; `resume` reconstructs with the
cache deleted; `advance --once` is idempotent across repeated ticks (no duplicate dispatch); **the
coordinator dispatches but never runs a leaf's work in the advance process** (R3 invariant — assert no
leaf body executes in-context, only dispatch + harvest); a second concurrent `advance` no-ops on the held
coordinator lease; `attend` prints the native `/resume <leaf-saga-id>` handoff; status is computed, never
read from a stored field.

### U4. Team-execution backend + R8 cleanup

**Goal:** make team-execution the first real backend behind the dispatcher seam, remove tmux/`team-setup`,
and preserve the validator-evidence state check.

**Files:** `plugins/team-execution/**`, `plugins/saga/scripts/outcome_dispatcher.py`,
`plugins/saga/scripts/team_emitter.py`, `tests/test_team_execution_plugin.py`,
`tests/test_outcome_dispatcher.py`.

**Requirements:** R5, R6 (first backend), R8, R23 (HALT receipt).

**Depends on:** U3.

**Test scenarios:** no tmux references remain in team-execution outside an intentional CHANGELOG history
note; `/team-setup` is removed and `test_team_setup_references_existing_assets` is removed/replaced; the
validator-state `.claude/`-ignored check runs in Phase A + Phase B preflight; dispatching a node creates a
team-execution leaf with a return channel; a backend that cannot run emits a visible HALT receipt, never a
silent substitute; **team-execution's own plugin.json + marketplace.json + CHANGELOG bump ships in this
unit's PR so `test_release_triad.py` stays green** (KTD14 — surfaces sync per-unit, not deferred to U11).

### U5. Completion barrier + recursive child outcomes

**Goal:** parent-owned barrier predicates, the per-subplot completion contract, child-outcome waiting, and
the **read-only GitHub PR/issue-state primitive** the barrier depends on (merged / closed / open) — the
merge *action* is U6; this unit only *reads* completion truth.

**Files:** `plugins/saga/scripts/outcome_orchestrator.py`, `plugins/saga/scripts/outcome_github.py`
(read side), `tests/test_outcome_completion.py`.

**Requirements:** R9, R10, R11, R20, R22, R28.

**Depends on:** U4.

**Test scenarios:** a code leaf unlocks dependents only after its PR reads merged; a non-code leaf unlocks
on a durable completion tick that also writes the canonical GitHub/spec marker (so a cache-less machine
sees it done); a `child_spec_ref` node unlocks only after the child outcome's terminal state reads
successful on GitHub (no cross-branch spec read); a blocked child pauses its downstream subtree but not
independent siblings; "done" is the parent's predicate over returned evidence, HALTing on an unmet
contract.

### U6. Auto-merge queue + GitHub negative states

**Goal:** clean-merge detection, the serialized rebase/reverify/squash queue (base-SHA-guarded, capped),
and the **PR/branch** negative terminal states with recovery/cascade (worktree-removed is U7).

**Files:** `plugins/saga/scripts/outcome_merge.py`, `plugins/saga/scripts/outcome_github.py` (write
side), `tests/test_outcome_merge_queue.py`.

**Requirements:** R12, R22, R30, R32 (PR/branch), R34.

**Depends on:** U5.

**Test scenarios:** a stale sibling base triggers rebase-then-rerun before squash; a conflict returns the
leaf to `work` and pages; **a manual/external merge landing on the base *during* reverify fails the
expected-base-SHA squash guard and reloops (not a stale-tree merge)**; base-churn cycles cap at 3 then
halt+page (no starvation spin); a closed-unmerged PR cascades the subplot to `rejected`; a manual
out-of-band merge is detected without a duplicate merge; a deleted branch / force-push each reach a
defined terminal state; GitHub offline queues writes and, on reconnect, drops a server-superseded queued
write (GitHub wins) and pages on retry exhaustion.

### U7. Decomposition, graph editing, worktree lifecycle

**Goal:** the draft-then-review flow, in-flight graph-mutation rules, lazy growth / elaborate / promote,
orphan reconciliation, the durable named+owned session/worktree per sub-outcome, the worktree-removed
negative state, and worktree/session caps + shared installs.

**Files:** `plugins/saga/scripts/outcome_decompose.py`, `plugins/saga/scripts/outcome_worktrees.py`,
`tests/test_outcome_graph_edit.py`, `tests/test_outcome_worktrees.py`.

**Requirements:** R13, R14, R15, R20, R21, R32 (worktree), R33.

**Depends on:** U3, U5.

**Test scenarios:** no layer dispatches before the operator approves the ready frontier's edges; pruning
an undispatched node closes its projected GitHub sub-issue; pruning a dispatched node requires a terminal
transition and reaps its worktree + reconciles evidence (cost-reconcile lands with the economics
primitives in U10); each sub-outcome gets exactly one durable worktree, named + owner-tagged, reused
across its leaves (not one-per-leaf); heavy dependency installs are shared across an outcome's worktrees;
the worktree cap prevents more than N concurrent autonomous worktrees; a worktree removed out-of-band is
detected and its node reaches a defined terminal state; a promoted node gets a `child_spec_ref` and fails
validation if it points back at an ancestor (no cross-spec cycle).

### U8. Reporting, attention consolidator, mission-control projection

**Goal:** derived-on-read reports (with the Mermaid DAG), the single ranked operator prompt, and the
secondary portfolio projection.

**Files:** `plugins/saga/scripts/outcome_report.py`, `plugins/saga/scripts/outcome_projection.py`,
`docs/outcomes/` generated examples, `tests/test_outcome_report.py`, `tests/test_outcome_projection.py`.

**Requirements:** R17, R18, R19, R25, F3, F5, F6, AE5.

**Depends on:** U5, U6.

**Test scenarios:** report regeneration is deterministic (overwrite from state, no drift); the
consolidator sorts gate → ambiguity → failure then by unblock-leverage (AE5); the mission-control
projection is generated from the spec, never hand-authored; no operator-writable status field exists; the
report carries the Mermaid topology + decision trail, and renders the cost rollup **when present and "no
data yet" when absent** — U10 populates the cost fields later, so U8 depends only on U5/U6, never on U10
(avoids a U8↔U10 cycle).

### U9. Full backend menu, degradation policy, heartbeats

**Goal:** inline / fork / subagent / team-execution / cc-workflows-ultracode / `/goal` dispatch adapters,
the presence-conditional degrade policy, and liveness enforcement.

**Files:** `plugins/saga/scripts/outcome_dispatcher.py`, `plugins/saga/scripts/lifecycle_state.py`,
`plugins/saga/references/operator-choice.md`, `tests/test_outcome_backends.py`,
`tests/test_outcome_liveness.py`.

**Requirements:** R3, R5, R6, R7, R23, R24 (telemetry capture), R31.

**Depends on:** U4, U5.

**Test scenarios:** a guarantee-bearing leaf halts when attended; an autonomous pre-side-effect leaf
degrades one rung and records a receipt; a post-side-effect leaf never degrades; a stale heartbeat pages
once; the recommender is frontier-budget aware; the fork cost lever is taken only when model+system+tools
match the parent within TTL (else it is not claimed as cheap).

### U10. Economics + optimize/retro consumers

**Goal:** record realized cost / operator-touch / retry telemetry and expose the per-outcome rollup.

**Files:** `plugins/saga/scripts/outcome_costs.py`, `plugins/saga/scripts/override_rate_reader.py`,
`plugins/saga/skills/optimize/SKILL.md`, `plugins/saga/skills/retro/SKILL.md`,
`tests/test_outcome_economics.py`.

**Requirements:** R7, R24.

**Depends on:** U5, U8, U9.

**Test scenarios:** every dispatched leaf has both a producer and a consumer for its cost fields; retries
and operator touches aggregate per outcome; missing telemetry reports "no data yet" rather than a
fabricated zero; the rollup can answer "did the DAG beat one long thread?" with real numbers.

### U11. Release, docs, integration gate

**Goal:** the **final feature-flip gate** — advertise the complete `/outcome` surface and assert the full
suite green. Per-unit PRs already kept each plugin's release surfaces in sync as they landed (KTD14); U11
does the saga-feature-level flip (marketplace advertises `/outcome`, the integration suite proves all 34
ship), it does not retroactively sync surfaces that earlier units left drifting.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/*/CHANGELOG.md`, `plugins/saga/README.md`,
`tests/test_release_triad.py`, `tests/test_saga_plugin.py`.

**Requirements:** R4 + all release-facing surfaces.

**Depends on:** U1–U10.

**Test scenarios:** the release triad passes; saga metadata advertises `/outcome`; team-execution metadata
no longer advertises tmux/setup; the full `uv run pytest` suite plus `ruff format --check`, `ruff check`,
`mypy`, and `bandit` pass.

## Build Spine & Sequencing Rationale

U1–U3 stand up a minimal coordinator with durable state and a local reconcile tick — provable on a trivial
2-node DAG before any real backend exists. U4 adds one real backend (team-execution, which always runs)
and retires tmux. U5 proves completion unlocks (the barrier) before any merge automation. U6 adds
auto-merge only after barriers + replay keys exist. U7 handles graph/worktree complexity before broad
backend autonomy. U8 makes the operator's view derived-on-read. U9 expands the backend menu + degrade
behavior. U10 proves the economics thesis. U11 closes release drift. Co-equal at release ≠ co-equal as
work order — the spine is the work order; the release bar is all 34.

## Risk Analysis & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Net-new orchestration layer (zero existing machinery) | Highest | Small pure modules, JSON schemas, `tmp_path` tests; prove a vertical slice (U1–U5 on a 2-node DAG) before adding all backends |
| Concurrent sibling merge conflicts (stale base) | High | Serialized coordinator merge queue + rebase-then-reverify + conflict-to-`work` recovery, capped at 3, **final squash base-SHA-guarded** against a manual/external merge during reverify (KTD7, U6) |
| Store durability (torn files, lost/stale locks, partial writes) | High | Atomic temp + `os.replace`, malformed-file quarantine, torn-trailing-ledger-line tolerance, lease-based coordinator + per-subplot locks with stale reclamation (KTD15, U2) |
| Crash/replay idempotency | High | Deterministic idempotency keys with `attempt:<n>` retry ordinal + transition ledger + "probe before mutate" recovery tests (KTD5, U2/U6) |
| Worktree proliferation exhausts the machine | Medium | Default cap of 3 active autonomous worktrees, one durable worktree per sub-outcome (not per-leaf), owner metadata, explicit reap transitions, shared installs (R15, U7) |
| Cold re-entry vs crash-replay conflation | Medium | Resolved: F5 cold re-entry is a rest-state scenario → non-lossy from committed spec + GitHub; the ledger serves same-machine crash-replay; only mid-transition-crash + machine-switch degrades to GitHub-truth reconcile (KTD5) |
| All-34 big-bang integration | Medium | Land units independently with per-unit release-surface sync (each interim merge stays releasable); U11 is the final feature flip; drift tests gate every PR (KTD14, U11) |
| Contract drift (requirements ↔ operator-choice docs ↔ code) | Medium | Update docs/tests with the R23 halt/degrade distinction in the same units (KTD14, U11) |

## Scope Boundaries

**In scope (built whole):** every R1–R34 — coordinator, dispatch seam, envelope, concurrency/state,
operator surface, decomposition, failure/degrade, economics, storage, the operational state machine, and
the team-execution reshape (R8).

**Deferred to `/work` (mechanism within a unit, not product):** exact JSON field-level schemas finalized
in U1; the `/outcome` subcommand help text in U3; the precise consolidator ranking weights in U8.

**Outside the core build (add only on demonstrated need):** a networked cross-host completion stream
(e.g. Redis) for sub-second completion when subplots genuinely fan across machines — GitHub + the
git-common-dir cache cover the single-machine many-worktree common case.

## Alternatives Considered

The three input plans diverged on five load-bearing points; the unified choice and the rejected option:

- **Guarantee/degrade wiring.** Rejected injecting halt-not-degrade into `recompile_for_tier` (an input
  plan's choice) — verified to be the wrong layer (it is a by-mode dispatcher). Chose `guarantee_tags` +
  `degrade_policy` enforced in the degrade path (KTD9).
- **Transition ledger location.** Rejected committing the ledger per-transition (an input plan's choice) —
  stronger cross-machine replay but pollutes branch history mid-run. Chose cache-resident ledger with an
  honest fresh-machine boundary (KTD5).
- **Child recursion.** Rejected overloading `orchestration_ref` with a `child_spec:<path>` string (an
  input plan's choice) — type-unsafe, conflates two roles. Chose a typed `child_spec_ref` node field
  (KTD10).
- **Scope discipline.** Rejected staging out nested recursion / economics / team-execution cleanup (an
  input plan proposed deferring all three) — it violates the operator's all-co-equal release decision
  (R4). Kept all 34 in scope; the spine is internal work order only.
- **Unit granularity.** Rejected both 8 units (under-scopes the operational state machine) and 21 units
  (too fine). Chose 11 with an explicit R1–R34 coverage matrix as the completeness guard.

Adopted from the input plans: the rebase-attempt cap of 3 and the Mermaid cockpit (Antigravity); the node
schema, store layout, and release-gate unit (Codex); the cache-ledger boundary and verification
corrections (Claude).

## Success Criteria

- All R1–R34 ship together; no component is a stub (U11 drift gate enforces it).
- The cost thesis is measurable, not asserted — U10's rollup answers "did the DAG of right-sized
  executions beat one long thread?" with real per-outcome numbers.
- Cold re-entry on a different machine after a multi-day gap reconstructs where / what / why with nothing
  lost from the canonical store (F5), with the fresh-machine ledger boundary stated honestly.
- An overnight autonomous run progresses through code layers (auto-merge unlocks dependents) and survives
  a mid-run crash, a stale-base merge conflict, and a hung leaf without corrupting the DAG or duplicating
  a side effect.
- Concurrent blocks reach the operator as one ranked page, not N (R18).
- team-execution runs with zero tmux and no setup step, validators intact; the release triad is green.

## Dependencies / Assumptions

- Reuses saga machinery as the substrate (verified): `execution_spec` (`dependency_layers`, the
  emitters), `recommend_execution_backend` (`lifecycle_state.py:99`), and the
  `save`/`read_ticks`/`restore` tick model. The orchestration layer itself is net build.
- mission-control / GitHub is reachable for the canonical completion loop (R26); offline runs on the cache
  + queue until reconcile (R34).
- The git-common-dir store resolves identically across worktrees and survives cleanup — verified directly
  this session.
- The fork cost lever (R6/R24) is real but conditional: a fork reuses the parent's cached prefix only with
  byte-identical model/system/tools and within the cache TTL, in tension with downgrading the fork's
  model; U9/U10 measure whether a given fork actually paid off rather than assuming it.
- No root `STRATEGY.md` exists; the origin requirements doc + ideation brief are the scope anchors.
