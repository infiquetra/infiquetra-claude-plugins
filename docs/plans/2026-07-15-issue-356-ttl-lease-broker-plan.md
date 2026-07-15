---
title: Lease-safe runtime continuity wave 2 - TTL lease broker and write fencing
type: feat
status: active
date: 2026-07-15
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/356
---

# Lease-safe runtime continuity wave 2 - TTL lease broker and write fencing

## Summary

Implement issue #356 after issues #350 and #351 merge. Add one file-backed, fleet-wide lease broker
in fleet-core for delegated-agent admission and outcome-worktree ownership. Every lease has a bounded
TTL and a monotonic fencing token; expiry is derived on read; provisional reservations close the
pre-spawn race; delegated mutations are rejected when the bound lease is missing, expired, or
superseded; and expired worktrees are reclaimed only through Saga's existing validated reaper.

Destination is merge. Execution uses an operator-approved Verified Workflow. Root owns
implementation, Git, integration, PR, merge, issue closure, and board reconciliation. Agent-lens
roles independently review or validate and do not mutate the repository.

## Current State and Corrected Assumptions

- `plugins/fleet-core/scripts/fleet_commons/` is the canonical cross-plugin Python home. Saga and
  team-execution already load it through their vendored `fleet_commons_shim`; the broker belongs
  there rather than in a new Saga-only utility.
- The broker is a fleet authority, not Claude runtime state. Its default root must therefore be
  runtime-neutral so the later Codex parity child can consume the same host-local registry without
  importing a Claude home path. `~/.claude`, `~/.codex`, and plugin `PLUGIN_DATA` roots are forbidden
  as the default fleet authority.
- `plugins/saga/scripts/outcome_store.py` has per-outcome atomic lease files. It documents a stale
  reclaim time-of-check/time-of-use gap and has no fencing token. It is neither fleet-wide nor a
  replacement for the broker; its outcome-state semantics remain intact while broker-backed
  ownership closes the runtime race.
- `plugins/saga/scripts/outcome_worktrees.py` already owns the worktree registry, cap-four policy,
  and `reap_worktree` path. The broker tracks ownership and expiry; Saga validates structured
  resource references and calls the existing reaper. No registry-driven raw path deletion is added.
- Issue #356's phrase "default 3 concurrent agents" predates #350's settled policy. After #350,
  agent admission must consume the resolved `ExecutionSpec.concurrency` policy: base width 3,
  all-read-only lift 4, aggregate fleet ceiling 7, then tier/lane/run resolution. Acceptance criterion
  AC1 uses a policy fixture whose aggregate ceiling is 3; production does not gain another cap.
- Agent leases and worktree leases occupy different named capacity pools. An agent lease is
  short-lived execution admission; a worktree lease is resource ownership with the existing
  cap-four policy. Counting both in one scalar pool would either strand worktrees or permit agent
  oversubscription.
- An Agent hook cannot infer an `ExecutionSpec` from tool input. #356 therefore moves only the
  normalized base/read-only/aggregate constants and admission-limit record into fleet-core. Saga's
  #350 resolver remains the authority for spec, environment, mutation, tier, lane, and run
  precedence and passes its resolved snapshot to the broker. Team-execution generic calls consume
  the same fleet-core defaults. No adapter parses a second concurrency environment variable.
- Claude hook events execute in parallel and in non-deterministic order. `SubagentStop` can be
  blocked by another hook, so it may record child-terminal intent but cannot be the sole release
  boundary. Foreground Agent leases are removed only after both the bound child has recorded terminal
  intent and the exact provisional `tool_use_id` has reached parent `PostToolUse` or
  `PostToolUseFailure`. Resident workers release only after explicit stop confirmation in
  team-execution Step B8. TTL expiry is the crash fallback.
- Generated workflow JavaScript and its child agents have no filesystem access. `/work` must reserve
  the whole emitted wave before calling `Workflow(...)`; `SubagentStart` claims those reservations,
  and the root releases the batch only after the workflow returns or is authoritatively cancelled.
- `SubagentStart` cannot block launch. Normal Agent/Task calls therefore acquire a provisional lease
  in `PreToolUse`; workflow calls use the batch reservation above. A child that bypasses both seams
  may briefly exist, but its file and shell mutation tools fail closed because it has no bound lease.
- `plugins/saga/scripts/evidence_ledger.py` already provides append-only, content-addressed evidence
  protection. #356 fences delegated tool mutation and worktree ownership; it does not create a second
  evidence ledger or rewrite the existing one.

## Scope and Threat Model

The protected subject is delegated runtime work launched through the repository's installed Saga,
team-execution, outcome, and engine-bridge seams. The trusted root coordinator remains the sole
mutator outside a subagent and is not forced through a delegated-agent lease. The broker protects
against stale, superseded, orphaned, over-capacity, or accidentally unguarded delegated processes;
it is not a sandbox against a malicious local operator who can edit the registry, disable all hooks,
or replace installed plugin code.

The cap measures authorized concurrent leases, not instantaneous provider-side inference. Expiry
revokes authorization and permits a replacement lease, but cannot preempt a model request or Bash
process already in flight. Mutation fencing runs at the next tool boundary. Consequently, destructive
worktree sweep also requires dead-owner evidence; TTL alone never deletes beneath a live process.

The broker stores identifiers and timestamps only. It never stores prompts, model output,
credentials, environment values, or evidence payloads. Registry directory mode is 0700 and files
are 0600. Malformed, unreadable, permission-unsafe, or version-unknown authority fails closed on an
armed delegated path and produces a typed diagnostic; unarmed root operations retain current
behavior.

The store root, lock, and registry must be owned by the effective user and must not be symlinks.
Creation uses no-follow/exclusive semantics, a same-directory 0600 temporary file, fsync, atomic
replace, and parent-directory fsync while the stable sibling lock is held. Any identity, ownership,
mode, or no-follow check failure is an unsafe-authority error.

## Requirements

- **R1. One fleet-wide broker.** Add a canonical fleet-core broker with `acquire`, `reserve-batch`,
  `claim`, `renew`, `verify`, `release`, `release-owner`, `inspect`, and `sweep` operations. A sibling
  lock file guarded with `fcntl.flock` covers the complete read, validate, decide, mutate, and atomic
  replace sequence. Saga and team-execution use thin adapters, not copied state machines. Resolve the
  shared root from `INFIQUETRA_FLEET_STATE_DIR` when explicitly set to a safe absolute directory;
  otherwise use `$XDG_STATE_HOME/infiquetra/fleet-leases` when `XDG_STATE_HOME` is safe and absolute,
  or `~/.local/state/infiquetra/fleet-leases`. Every consumer exposes a digest of the canonical root
  for compatibility comparison without serializing the path. A mismatch HALTs before admission.
- **R2. Derived expiry and durable fencing.** Every lease contains `lease_id`, named pool,
  owner/session binding, resource reference, operator-facing wall timestamps, same-boot monotonic
  renewal time, boot identity, positive TTL, broker epoch, and globally increasing fencing sequence.
  On the same boot, expiry is derived from monotonic renewal time plus TTL; a boot-identity change
  expires process-bound authority because its owner cannot survive reboot. No `expired`, `stale`,
  `status`, or similar cached truth is committed. Clock/boot providers are injectable in tests.
- **R3. Collision-resistant monotonic tokens and durable resource heads.** A fresh store gets a
  random broker epoch and an integer `next_fencing_sequence`. Every grant increments the sequence and
  atomically updates a persistent `resource_fences` head keyed by the canonical resource digest. The
  effective token is `(broker_epoch, fencing_sequence)`, so deleting/recreating a test or local store
  cannot make an old token current again. Removing a released lease does not remove its resource head:
  head plus live leases must still distinguish current, derived-expired, closed/released, and
  superseded tokens for #355's evidence disposition without storing a mutable status field.
- **R4. Policy-owned capacity.** Move the normalized default constants and closed `AdmissionLimits`
  value into fleet-core; refactor #350's Saga resolver to import them while retaining all resolution
  precedence. Every agent reservation records the resolved `session_limit`, `aggregate_limit`,
  mutation mode, and policy digest. Admission counts nonexpired leases, applies the candidate's
  session limit, and applies the minimum aggregate limit asserted by the candidate and every live
  agent lease. A session cannot mix policy digests while leases are live; re-arm occurs only after it
  drains. Generic team-execution calls use the shared default snapshot; Saga `/work` and engine lanes
  pass their exact resolved snapshot. Worktree admission retains cap four. Exhaustion returns a typed
  refusal with earliest derived expiry; hooks do not sleep or queue invisibly.
- **R5. Pre-spawn reservation and binding.** Normal `Agent|Task` `PreToolUse` acquires a provisional
  agent lease keyed by trusted `(session_id, tool_use_id, agent_type)`. `SubagentStart` atomically
  claims the oldest compatible reservation for that session/type and binds trusted `agent_id` and
  canonical actual cwd. Same-type provisional slots are intentionally fungible because
  `SubagentStart` does not expose the parent `tool_use_id`; claims are serialized and single-use.
  Parent-return and child-terminal timestamps are recorded independently on the claimed lease, so a
  cross-ordered parallel claim may delay release but can never release a live child. Missing
  authority is an error, never an implicit grant.
- **R6. Workflow batch admission.** `ExecutionSpec` exports the maximum simultaneous wave width from
  #350. Before `Workflow(...)`, `/work` reserves exactly that many workflow slots in one atomic
  operation or launches none. Starts claim from the named batch; batch reservations have a short
  configurable claim TTL, and bound children receive the normal execution TTL. The driver releases
  unused reservations and confirmed-terminal children after return. Conformance rejects a workflow
  launch lacking this reservation contract.
- **R7. Lease renewal.** Acquisition requires a positive `ttl_seconds`; CLI adapters default to 300
  seconds and coordinators renew no later than one third of the TTL at existing tick, wave, and
  collection boundaries. There is no background daemon. A single tool call may outlive its lease;
  subsequent mutation is intentionally blocked until the root grants a new attempt.
- **R8. Delegated write fencing.** Saga's `PreToolUse` hook covers
  `Bash|Write|Edit|MultiEdit|NotebookEdit` whenever trusted hook input contains `agent_id`. Before the
  tool executes it verifies the current bound agent lease and exact current resource token. Missing,
  expired, released, or superseded authority exits 2 with a bounded recovery message. Root calls
  without `agent_id` are unchanged. Bash is included so a stale child cannot bypass file-tool fencing.
- **R9. Retry supersession.** Retrying one logical `resource_ref` grants a new fencing sequence and
  atomically supersedes its earlier current lease. The old agent remains unable to mutate even if its
  process is alive. Parallel logical units use distinct resource references and therefore do not
  supersede each other.
- **R10. Safe release.** `SubagentStop` records `child_terminal_at` by trusted `agent_id` but removes
  nothing. Parent `PostToolUse Agent|Task` or `PostToolUseFailure` records `parent_completed_at` by
  trusted `tool_use_id`; an unclaimed failed reservation may then be removed, while a claimed
  foreground grant is removed only when both timestamps exist. Team-execution Step B8 stops resident
  children, confirms terminal state, then calls `release-owner` and `sweep`. Repeated release is
  idempotent; mismatched owner or token is refused.
- **R11. Lease-backed worktree ownership.** Outcome dispatch acquires and renews a worktree-pool lease
  for structured `(repo_root, outcome_id, subplot_id)` ownership plus owner PID, process-start
  identity, and boot identity. `sweep` selects derived-expired leases, requires explicit terminal
  evidence or proves the recorded process is absent/not the same process, then Saga verifies the
  resource against its outcome registry and calls `outcome_worktrees.reap_worktree`. An expired lease
  with the same live owner is reported as `expired-live-owner` and not reaped. Reap failure keeps the
  lease/resource discoverable for retry; no silent deregistration or arbitrary registry path deletion.
- **R12. Every production spawn seam is armed.** Adopt normal Saga Agent calls, generated workflows,
  team-execution fan-outs, outcome dispatcher processes, and registered engine bridges. Extend #350's
  concurrency spawn-site inventory with lease pool, acquire/reserve seam, bind seam, renewal seam,
  and release seam. An injected executable spawn without those columns fails conformance.
- **R13. Compatibility and release integrity.** Preserve #351 settlement, evidence-ledger,
  artifact-pointer, and outcome-state contracts. Bump fleet-core, Saga, and team-execution versions;
  update all three manifests, marketplace entries, changelogs, drift guards, operator docs, and the
  engineering journal in the same PR. If a required broker version is missing or skewed, armed paths
  fail closed with an install/update diagnostic rather than silently running unleased.

## Data Contract

The file-backed store defaults to the runtime-neutral root resolved in R1 and stores
`registry.json` beneath it. Tests inject an explicit root. `~/.claude`, `~/.codex`, and plugin
`PLUGIN_DATA` paths are not fallback rungs. The schema is closed and contains only:

```text
schema: fleet_lease_registry.v1
broker_epoch: random UUID
next_fencing_sequence: positive integer
resource_fences:
  <canonical_resource_sha256>:
    resource_ref: closed pool-specific object
    broker_epoch: UUID
    fencing_sequence: positive integer
    lease_id: bounded string
leases:
  <lease_id>:
    pool: agent | worktree
    owner_id: bounded string
    owner_pid: positive integer or null
    owner_process_start: bounded OS identity or null
    session_id: bounded string
    agent_id: bounded string or null while provisional
    tool_use_id: bounded string or null
    agent_type: bounded string or null
    batch_id: bounded string or null
    resource_ref: closed pool-specific object or null while provisional
    policy_sha256: SHA-256 or null for worktree leases
    session_limit: positive integer or null for worktree leases
    aggregate_limit: positive integer or null for worktree leases
    mutation: read-write | none | null for worktree leases
    boot_id: bounded OS boot identity
    acquired_at: UTC wall timestamp
    renewed_at: UTC wall timestamp
    renewed_monotonic_ns: nonnegative integer
    claimed_at: UTC timestamp or null
    child_terminal_at: UTC timestamp or null
    parent_completed_at: UTC timestamp or null
    ttl_seconds: positive integer
    fencing_sequence: positive integer
```

The registry carries no expiry/status field. Released and successfully reaped lease entries are
removed under lock, but their last-granted `resource_fences` head remains. A presented token equal to
the head with a matching nonexpired lease is current; equal with an expired lease is expired; equal
with no lease is closed/released; and different from the head is superseded. Append-only audit truth
remains in existing Saga ledgers, not in the capacity authority.
For deterministic tests, wall time, monotonic time, boot identity, process liveness, and UUID sources
are injected. Production uses OS monotonic time for same-boot TTL and wall timestamps only for
inspection. A different boot identity makes process authority expired. Token monotonicity and
exclusivity come from the locked sequence, not either clock.

Agent `resource_ref` is a bounded logical unit identifier plus optional canonical worktree root.
Worktree `resource_ref` is exactly `repo_root`, `outcome_id`, and `subplot_id`; Saga resolves and
validates it against the live outcome registry before reaping. Paths must be canonical, inside the
registered repository/worktree authority, and not symlinks escaping that authority.

## Traceability and Dependencies

- Issue AC1 maps to R4 and uses an aggregate-cap-three fixture with a two-process contention test.
  AC2 maps to R4's session ceiling. AC3/AC4 map to R8/R9. AC5 maps to R11 with 15 registered
  worktrees. AC6 maps to R10. AC7 maps to R8/R11. AC8 maps to R2. AC9 maps to R12. AC10 maps to R4
  and explicitly proves that #350, not this broker, owns the agent cap.
- The parent context is the approved
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json` revision 3; issue #356's published
  ACs remain the implementation authority. The operator approved the exact Verified Workflow digest
  recorded below; dependency completion still gates dispatch.
- #350 is the behavioral prerequisite and must be merged: it supplies the canonical effective
  concurrency policy and spawn-site inventory. #351 is serialized first because both Wave 1 issues
  share Saga release surfaces; #356 starts from refreshed main with expected versions Saga 0.98,
  team-execution 2.17, and fleet-core 0.11.
- #356 supplies the lease primitives used by #355, #357, #358, #353, and both new #579 runtime-parity
  children. It owns broker lifecycle and the minimum Step B8 lease-release adoption. #358 later owns
  the broader non-skippable generic teardown contract; #356 must not pre-implement that issue.
- This issue closes through one atomic PR because a broker without every production adapter creates a
  false sense of safety. Implementation units receive focused commits/checkpoints where useful.
- No external service, credential, deployment environment, production data, or named human reviewer
  is required.

## Key Technical Decisions

- **KTD1 - fleet-core is the authority.** The broker is one shared fleet-commons module with thin
  plugin adapters; no plugin maintains a parallel lease schema.
- **KTD2 - pools separate execution from resource ownership.** Agent and worktree leases share one
  lock and fencing sequence but enforce their existing independent capacities.
- **KTD3 - resolution stays in Saga; normalized limits are shared.** Fleet-core owns the default
  constants and closed admission record so Saga and team-execution cannot drift numerically. Saga's
  #350 resolver alone interprets spec/environment/tier/lane/run inputs. The broker records the
  resolved snapshot and uses the minimum live aggregate ceiling; it never re-resolves policy.
- **KTD4 - reserve before spawn, bind after start.** Provisional and batch reservations close the
  only pre-spawn seam; trusted hook identity binds the actual child after launch. A bypassed child is
  mutation-fenced, not retrospectively counted as authorized.
- **KTD5 - foreground release requires two independent lifecycle signals.** Parallel hook behavior
  makes `SubagentStop` insufficient, while `SubagentStart` lacks the parent `tool_use_id`. A claimed
  foreground lease is removed only after its bound child records terminal intent and its provisional
  parent call records return/failure. Cross-ordered same-type claims can retain capacity until TTL but
  cannot release a live child. Resident workers use explicit stop confirmation.
- **KTD6 - fencing uses trusted runtime identity.** Mutation hooks look up the token bound to trusted
  `agent_id`; they never accept a caller-provided token as proof. Retry supersession changes the
  current resource head atomically. The head survives lease removal so later evidence writers can
  derive closed versus superseded without a mutable disposition field.
- **KTD7 - expiry is derived and renewal is cooperative.** No committed `expired` bit can drift from
  the clocks. Same-boot monotonic time avoids wall-clock jumps; a reboot invalidates process-bound
  authority. Existing coordinators renew at bounded lifecycle seams; post-expiry writes fail closed.
- **KTD8 - Saga owns reaping.** The broker selects expired structured resources, but only the existing
  Saga reaper may validate and remove an outcome worktree, and only after owner-death or explicit
  terminal proof. Expiry with a matching live owner is diagnostic, never deletion authority.
- **KTD9 - hook enforcement is an operational guard, not hostile-user containment.** Installed hooks
  protect supported delegated runtimes. A local operator who disables or replaces hooks is outside
  the threat model and receives conformance diagnostics, not a misleading security claim.

These decisions are recorded under `{#fleet-ttl-lease-broker-356}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

## Implementation Units

### U1. Fleet-core store, schema, and atomic operations

Move the normalized default constants and `AdmissionLimits` record to fleet-core, with Saga #350's
resolver importing them without changing resolution behavior. Create typed lease/resource records
and the locked registry operations. Validate schema, bounds,
permissions, canonical paths, TTL, pool, unique IDs, epoch, and sequence on every operation. Implement
atomic replace and parent-directory fsync using existing repository durability patterns. Provide an
injected clock/UUID seam and typed errors for capacity, corruption, unsafe permissions, mismatch, and
expiry.

**Files:** `plugins/fleet-core/scripts/fleet_commons/concurrency_policy.py` (new),
`plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (new), fleet-commons exports,
`plugins/saga/scripts/concurrency_governor.py`, `tests/test_fleet_lease_broker.py` (new),
`tests/test_concurrency_policy.py`.

**Tests:** #350 resolution remains byte/behavior compatible after extracting shared defaults,
runtime-neutral default parity, safe explicit environment override, unsafe/relative XDG or override
rejection, no Claude/Codex/PLUGIN_DATA fallback, root-identity digest equality/mismatch, first-write
modes, read-only inspect creates no files, two-process lock contention, no cap overshoot,
session/aggregate limits, conflicting live session-policy refusal, minimum live aggregate ceiling,
batch all-or-nothing, single-use claim, two-signal release,
TTL/renew/release, idempotent release, malformed/unknown schema refusal, unsafe permissions and
ownership, symlinked root/lock/registry refusal, epoch recreation, wall-clock jump immunity, boot
change invalidation, sequence monotonicity, resource-head persistence after release, four-way token
classification, and no derived-expiry/status fields.

### U2. Agent reservation, binding, renewal, and mutation hook

Add a thin Saga CLI and hook adapter. Acquire provisional leases at `Agent|Task` `PreToolUse`, claim
at `SubagentStart`, verify all delegated mutating file tools plus Bash, record child-terminal and
parent-completed signals separately, and remove a foreground lease only when both exist. Preserve
existing delegation-tripwire and stop-audit semantics when hook processes run in parallel.

**Files:** `plugins/saga/scripts/lease_broker.py` (new), `plugins/saga/hooks/hooks.json`, focused hook
scripts under `plugins/saga/hooks/`, `tests/test_saga_hooks.py`, `tests/test_saga_plugin.py`.

**Tests:** acquire-before-call ordering, two same-type parallel reservations and cross-ordered claims,
single-use claim, trusted-agent/cwd binding, missing/expired/superseded lease blocks Edit and Bash,
fresh retry succeeds, root tool call unchanged, unclaimed failure cleanup, both lifecycle signals in
either order before release, and blocked `SubagentStop` does not prematurely free capacity.

**Depends on:** U1.

### U3. Generated workflow batch admission

Extend #350's emitted metadata with required reservation width and stable batch/unit identities.
Update `/work` Phase 1.5 to reserve the complete simultaneous wave before `Workflow(...)`, expose the
batch to the runtime binding hook, renew at collection seams, and release after authoritative return.
If reservation or runtime attestation fails, launch none and HALT with the capacity/install receipt.

**Files:** `plugins/saga/scripts/execution_spec.py`, `plugins/saga/scripts/workflow_emitter.py`,
`plugins/saga/skills/work/SKILL.md`, `tests/test_saga_execution_spec.py`,
`tests/test_saga_workflow_emitter.py`, hook tests.

**Tests:** exact width exported, all-or-none batch reservation, each start claims one unit, unused
reservation cleanup, child terminal release, long-wave renewal, no direct filesystem grant to
workflow JavaScript/children, and launch absent reservation rejected by conformance.

**Depends on:** U2.

### U4. Team-execution and direct spawn adoption

Add a small team-execution lease CLI/protocol wrapper and arm every direct Agent fan-out. Step B8 must
stop resident workers, verify terminal state, release owner leases, and sweep. Outcome dispatcher and
registered engine bridges acquire before committing process/leaf dispatch, renew at heartbeats or
collection, and release only at authoritative settlement. Preserve #351's manifest/spawn/settle order.

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`, a focused script under
`plugins/team-execution/skills/team-execution/scripts/`, consensus/worker references,
`plugins/saga/scripts/outcome_dispatcher.py`, registered engine bridge files named by the inventory,
`tests/test_team_execution_plugin.py`, outcome/engine adapter tests.

**Tests:** every configured child is reserved before Agent call, Step B8 stop-confirm-release-sweep,
crashed child remains until TTL/sweep, settlement cannot release the wrong token, engine/outcome
dispatch refuses capacity, and #351 settlement evidence remains ordered and complete.

**Depends on:** U2; may run in parallel with U3 after the core hooks settle.

### U5. Worktree lease and validated reclamation

Acquire a worktree-pool lease when Saga registers an owned outcome worktree, renew it during active
outcome ticks, and sweep derived-expired leases through `Store.for_outcome`, registry validation,
`git_worktree_ops`, and `outcome_worktrees.reap_worktree`. A reap exception leaves the authority
visible and retryable. An expired/superseded agent bound to a removed worktree receives the loud hook
failure before any subsequent mutation.

**Files:** `plugins/saga/scripts/outcome_worktrees.py`, `plugins/saga/scripts/outcome_store.py`,
Saga broker adapter, `tests/test_outcome_worktrees.py`, `tests/test_outcome_store.py`, broker tests.

**Tests:** 15-worktree fixture with dead-owner identities, active renewal retained, expired live owner
reported but not reaped, expired dead owner reaped, reboot-invalidated owner reaped, mismatched
registry or escaping path refused, reap failure retained then retried, removed-worktree Edit/Bash
fails loudly, cap four unchanged, and existing outcome coordinator lease regression suite remains
green.

**Depends on:** U1 and U2; may run in parallel with U3/U4 after the core contract settles.

### U6. Spawn-site conformance, release surfaces, and full gate

Extend `plugins/saga/references/concurrency-spawn-sites.md` with lease lifecycle columns and a parser
that scans executable spawn seams. Keep the sandbox inventory separate and cross-linked. Document
operator inspection/recovery without granting manual token fabrication. Bump fleet-core 0.11 to 0.12,
Saga 0.98 to 0.99, and team-execution 2.17 to 2.18 from the refreshed post-Wave-1 base; update all
manifests, marketplace rows, changelogs, drift tests, and journal entries.

**Files:** concurrency inventory and validator, plugin/marketplace manifests, three changelogs,
operator docs, drift/conformance tests, `docs/engineering-journal/DECISIONS.md`, and
`docs/engineering-journal/LEARNINGS.md` only if implementation reveals a durable hook timing or
installation finding.

**Tests:** every discovered executable spawn has acquire/reserve, bind where applicable, renewal, and
release coverage; injected unguarded spawn fails; installed hook metadata parses; required broker
version skew fails closed; release parity and changelog coverage pass.

**Depends on:** U3, U4, and U5.

## Requirement Coverage

| requirement | implementation | primary proof |
|---|---|---|
| R1-R3 | U1 | locked multi-process state tests, schema/epoch/sequence tests |
| R4 | U1, U3, U4 | cap-three fixture, session/aggregate and batch admission tests |
| R5 | U1, U2 | pre-call ordering and parallel single-claim tests |
| R6-R7 | U3, U4 | batch launch refusal and injected-clock renewal tests |
| R8-R10 | U2, U4 | stale Edit/Bash rejection and safe release ordering tests |
| R11 | U5 | 15-worktree reclamation and failure-retention tests |
| R12 | U4, U6 | inventory parser plus injected unguarded-spawn failure |
| R13 | U6 | full gate, release parity, version-skew refusal |

## Verification

Run the narrowest tests after each unit, then the full gate from a refreshed clean issue branch:

```bash
uv run pytest tests/test_fleet_lease_broker.py -q
uv run pytest tests/test_saga_hooks.py tests/test_outcome_worktrees.py -q
uv run pytest tests/test_saga_execution_spec.py tests/test_saga_workflow_emitter.py -q
uv run pytest tests/test_team_execution_plugin.py tests/test_outcome_dispatcher.py -q
uv run pytest
uv run ruff check .
uv run mypy plugins/
uv run bandit -r plugins/
git diff --check
```

The concurrency validator must independently inspect command evidence for true multi-process
contention, aggregate and session limits, atomic batch admission, renewal/expiry behavior, and no
overshoot. The event-flow validator must independently trace reserve/acquire, claim, renew, verify,
supersede, release, sweep, reap failure, and Step B8 ordering. Both validators fail closed on missing
or self-reported evidence.

Manual evidence includes: a cap-three fixture with more contenders than slots; a stale child whose
Edit and Bash calls are refused after a retry gets a higher token; one blocked `SubagentStop` that
retains its slot until parent return; one failed batch reservation that launches zero workflow units;
and a 15-worktree sweep whose one injected reap failure remains visible and succeeds on retry.

## Failure Modes and Stop Conditions

- The broker or an adapter creates another numeric default/environment parser, combines agent and
  worktree capacities, permits mixed live policy digests in one session, or weakens the minimum live
  aggregate ceiling: stop and repair U1 before adapter work.
- A launch site cannot reserve before spawn. If it also cannot be restructured so an unbound child is
  mutation-fenced, stop for scope review; do not silently admit it after launch.
- `SubagentStart` matching can bind one reservation more than once or leave same-type parallel starts
  ambiguous after locked FIFO/unit identity resolution: stop and strengthen the host-binding seam.
- Any stop hook releases before the matching parent completion signal, any parent completion releases
  a claimed child without its terminal signal, or cross-ordered same-type claims can free a live
  lease: stop and restore the two-signal release contract.
- A registry record can cause raw deletion without Saga registry/path validation, or a reap failure
  removes its retry authority: stop as a destructive-path defect.
- Wall-clock movement can expire a same-boot lease, or sweep can reap a worktree whose recorded owner
  PID/start identity is still live: stop as a destructive-path defect.
- A stale child can mutate through any repository-supported file tool or Bash, a fresh token can be
  reused after store recreation, or malformed authority fails open: stop as a P0 safety defect.
- Required hooks are missing/disabled in installed metadata or fleet-core version skew silently
  degrades: stop; no PR/merge.
- Any P0-P3 document-review or code-review finding remains unresolved, a required validator lacks
  gate-capable evidence, release metadata drifts, or the full quality gate fails: no PR/merge.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's implementation paths plus exact release surfaces. Root
  records the pre-existing Git baseline before `implement`; unrelated worktree paths are excluded.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; the concurrency and
  event-flow testers independently assess captured command evidence and semantics. The installed
  registry currently has no deterministic-validator role, so none is fabricated.
- `vehicle=auto` requests the named profiles above. The runtime receipt must confirm model, effort,
  role-lens hash, and profile hash before the attempt counts. A mismatch is stopped and rerun in a
  fresh bounded context with the approved profile; missing independence or evidence blocks the gate.
- Every P0-P3 finding is fixed by root and returned to the affected role in a new attempt. Three
  unsuccessful remediation cycles halt and page the operator. Any model, effort, lens, validator, or
  execution-class change requires a newly approved workflow candidate.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No deploy,
  credential, production-data, force-push, or branch-deletion action is authorized.
- Workflow intents, runtime receipts, findings, command logs, workspace audits, PR URL, merge SHA,
  issue close, and board reconciliation are retained in the Verified Workflow evidence root and the
  issue/PR.

## Completion Gate

Completion requires all issue acceptance criteria, zero open P0-P3 doc/code-review findings, both
required validators passing with gate-capable evidence, the full verification gate green, one atomic
issue PR merged, issue #356 closed, its Operations card reconciled, dependent outcome nodes refreshed,
and the outcome worktree returned to a clean state except for the next planned wave.
