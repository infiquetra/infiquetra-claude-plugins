---
title: Lease-safe runtime continuity wave 3 - non-skippable teardown and reclamation
type: feat
status: active
date: 2026-07-15
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json
deepened: 2026-07-15
refreshed: 2026-07-18
---

# Lease-safe runtime continuity wave 3 - non-skippable teardown and reclamation

## Summary

Implement issue #358 after #351, #356, and #357 by turning team-execution completion into an
executable terminal state machine. Every observed success, hard failure, and operator abort enters
Step B8, records teardown intent, stops and confirms owned residents or processes, releases their
canonical leases, invokes the #356 validated worktree sweep, and records an immutable closing
receipt. A run with retained or failed resources is terminal-but-blocked, never reported complete.

The issue's proposed second reclamation ledger and worktree reaper are stale after the outcome's
reviewed substrate. The #356 fleet broker is the live register-on-spawn ownership registry, #351's
hash-chained `run_fact.v1` ledger is the historical fact stream, and #357 supplies confirmed liveness
and idle-notice evidence. #358 composes those authorities and adds one broker-owned closing fence so
no new resource can race a zero-open receipt; it adds no parallel mutable store, lease format,
liveness detector, or arbitrary filesystem janitor.

Destination is merge. Execution uses the operator-approved cc-workflow ceremony defined in the
Workflow Structure and Operating Contract sections below. Root owns
implementation, resource actions, Git, integration, PR, merge, issue closure, and board
reconciliation. Agent-lens roles independently review or validate and authorize no repository or
resource mutation.

---

## Problem Frame and Current State

`plugins/team-execution/skills/team-execution/SKILL.md` on merged main (post-#356) ends Phase B at
a minimal `Step B8: Stop and release resident leases` (`SKILL.md:572`): B7 reports changes and
gates, and #356's shipped B8 closes the immediate safety gap with a resident stop, terminal
confirmation, session-lease release via `lease_protocol.py teardown` (which calls
`release_session_if_terminal`), and the broker `sweep`. That minimum intentionally leaves generic
terminal orchestration, typed process actions, recovery, receipts, and the all-path invariant to
#358, which extends the existing B8 rather than introducing it.

The original issue predates the now-binding outcome authorities below:

| concern in #358 | canonical owner after prior outcome leaves | #358 responsibility |
|---|---|---|
| register-on-spawn live ownership | #356 fleet-core broker and resource heads | require and reconcile it; do not create another registry |
| append-only lifecycle history | #351 Saga `run_fact.v1` ledger | add a closed `kind=teardown` event family |
| worktree TTL and dead-owner proof | #356 Saga `sweep` and outcome registry validation | invoke it and account for every result |
| idle/stalled detection and re-ping | #357 shared liveness engine and facts | act only on confirmed results, never phi suspicion alone |
| late/superseded evidence writes | #355 fencing/quarantine | retain its boundary; teardown does not reclassify evidence |
| terminal resource accounting pattern | #347 `ship_teardown.py` and ship ceremony | reuse reconcile/receipt semantics, not its mutable sidecar |

The live repository census on 2026-07-15 contains nine worktrees, not the fifteen-worktree snapshot
quoted by the issue. The primary worktree, this active outcome worktree, another active outcome
branch, and several detached/workflow worktrees cannot be classified as abandoned from names or age.
That census is attended acceptance input only. Neither planning nor CI removes a developer worktree,
and cleanup requires later explicit resource-specific authority plus #356 dead-owner and registry
proof.

Claude hooks provide useful recovery seams but not an exact-death guarantee. `SessionEnd` is a
bounded best-effort cleanup notification and cannot block termination; `SessionStart` can revisit
open runs on startup/resume. Therefore observed terminal paths execute B8 synchronously, while
`SIGKILL`, process crash, or host death is reclaimed only on a later recovery invocation after lease
expiry and trusted dead-owner proof. The plan makes that delay explicit instead of promising code can
run after the process no longer exists. Hook behavior is grounded in the official hook contract:
https://code.claude.com/docs/en/hooks

---

## Traceability and Dependencies

- **Parent outcome/spec:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` and subplot
  `sub-358` in `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`.
- **Source issue:** `infiquetra/infiquetra-claude-plugins#358`; its seven acceptance outcomes remain
  mandatory, but its optional-broker and second-ledger assumptions are superseded by the outcome DAG.
- **Hard upstream:** #351 supplies settlement and run facts; #356 supplies leases, resource heads,
  dead-owner proof, safe worktree sweep, and the minimum B8 adoption; #357 supplies confirmed idle and
  liveness evidence. All three must be merged and this plan refreshed against their exact APIs.
- **Sibling safety:** #355 merged 2026-07-17 (PR #614, `a1dc0c2a`), so its fencing/quarantine
  surfaces are part of the delivery base; #358 is serialized from refreshed main and never weakens
  #355 fencing/quarantine.
- **Downstream unlock:** #353 fleet doctor consumes #358 teardown facts and open-resource projection;
  the cross-runtime acceptance leaf later proves the contract under Claude and Codex control paths.
- **External prerequisites:** none. No deployment, credential change, production-data access, or
  automatic destructive cleanup of current developer worktrees is authorized by this plan.

| published issue acceptance | dependency-correct plan contract | primary executable evidence |
|---|---|---|
| every worktree/process/resident registers on spawn | #356 broker registration plus source-aware inventory | `register_on_spawn` production-call tests and conformance |
| repeated/partial `reclaim_all()` is idempotent | R3-R5, R9; U2-U4 | repeated terminal/recovery scenario with stable action keys |
| killed run reclaimed after TTL | R5-R6; U3-U5 | subprocess death, clock advance, recovery, dead-owner sweep |
| idle resident evicted without defeating warm pool | R7; U4 | #357 confirmed-stalled input, stop receipt, retained warm peer |
| B8 covers success/failure/abort | R3, R11; U2, U5 | terminal matrix and completion-claim ordering |
| leak invariant fails before and passes after cleanup | R10; U5 | isolated injected unledgered worktree fixture; no host deletion |
| repository quality gates pass | R13; U6 | focused selectors, full suite, static/security/release checks |

---

## Requirements

R1. **One live ownership authority and one historical fact stream.** The #356 fleet broker remains
the register-on-spawn live registry and lease/fencing authority. The #351 hash-chained run-fact ledger
remains the append-only history. #358 adds neither `reclamation_ledger.py` nor a second worktree
registry, mutable resource status file, TTL clock, heartbeat store, or reaper decision engine.

R2. **Stable run and resource identity.** Before Phase B can spawn anything, root opens a bounded
`team_run_id` and owner identity through the broker/run-fact adapter. Every resident, registered
process, and outcome worktree carries canonical run, owner, resource, lease, token, process-start,
and boot identity available from #356. Teardown actions use a stable idempotency key derived from
`team_run_id`, resource identity, resource generation, and action kind; prompts, agent prose,
arbitrary paths, environment values, or wall time cannot replace trusted identity. Fleet-core adds a
monotonic `close-owner-admission` operation under the broker lock: after it commits, every acquire,
reserve, claim, or retry for that exact `team_run_id` is refused while existing leases remain
inspectable. Repeating close is idempotent and there is no reopen operation for the same run ID.

R3. **Step B8 is the terminal state machine.** Every terminal path observed by the coordinator -
success, hard-fail, operator abort, and raised andon - enters Step B8 exactly once logically, even
when invoked repeatedly physically. Step B7 computes gates and a report draft but cannot assert run
completion. B8 first closes owner admission in the broker, appends `teardown-intent`, reconciles the
complete owned-resource snapshot, executes authorized actions, appends each outcome, re-reconciles,
and emits `teardown-complete` only when zero resources remain open. The final zero-open check and
completion append re-verify the still-closed broker generation. No configuration, best-effort flag,
or failure branch bypasses B8.

R4. **Closed resource actions are conservative and typed.** `reclaim_all()` consumes one
chain-verified ledger snapshot and one lock-consistent broker snapshot; it does not claim those two
stores are transactionally atomic. Every destructive adapter re-verifies the current closed owner
generation, lease/token, and resource identity immediately before action. The result classifies
every resource as `released`, `already-absent`, `retained`, or `failed` with trusted evidence.
Repeated calls converge without double-stop, double-release, or double-delete. If the process
crashes after an action but before its result fact, recovery reconciles trusted reality and appends
`already-absent` for the existing action key rather than acting again. Unknown kinds, identity
mismatch, corrupt authority, action exceptions, and missing receipts are retained/failed and keep
the run terminal-but-blocked; they are never silently dropped.

R5. **Crash recovery is eventual, not fictional.** The synchronous driver handles every terminal it
observes. A bounded Saga `SessionEnd` hook records/retries teardown only for the trusted hook
`session_id` mapped to this run and canonical repository; it is not the guarantee and its command
timeout is five seconds. Saga `SessionStart` recovery uses a 15-second hook timeout and at most four
resource actions per invocation, while an explicit operator CLI may request another bounded batch.
Both inspect open team runs only for the hook/CLI's canonical repository,
derive expired ownership, prove process death or consume terminal evidence, and re-enter the same
idempotent state machine. `SIGKILL` or host death may retain resources until the next recovery
invocation and TTL boundary; documentation and tests state that upper-bound assumption.

R6. **Worktree reclamation remains #356-safe.** #358 invokes the canonical `sweep`; it does not call
`git worktree remove` directly or reuse #347's broad merged-worktree janitor. A candidate needs
derived-expired/terminal ownership, boot/process dead-owner proof, canonical repo/outcome/subplot
identity, registry-path agreement, and the existing no-force reap. Dirty, unmerged, primary,
self/current-cwd, escaping, unregistered, live-owner, or failed-removal worktrees remain visible.

R7. **Idle eviction consumes confirmed #357 decisions.** Phi suspicion, chat activity, a bare idle
notice, or artifact-pointer age cannot stop a resident. Only #357 `confirmed-stalled` or an explicit
segment-boundary shed, paired with current #356 ownership, creates a resident stop intent. The action
records trusted host stop request and terminal confirmation before releasing the lease. Warm peers
within the idle policy stay resident; re-ping exhaustion and idle-TTL policy are distinct evidence.

R8. **Process reclaim requires exact process identity.** Only a coordinator-created process recorded
with PID, process-start identity, boot identity, argv digest/class, and current run ownership may be
signaled. External Agent/provider processes without trusted OS identity use their runtime stop API,
not PID guessing. Owned subprocess teardown sends `SIGTERM`, waits a configurable five seconds in
production (injectable clock/wait in tests), and may send `SIGKILL` only when the resource policy
explicitly records `escalation=term-then-kill`; otherwise it remains open. PID reuse, boot change,
identity mismatch, permission errors, or a still-live unowned process fail safe.

R9. **Teardown history is append-only and derived.** Extend `run_fact.v1` with `kind=teardown` and
closed events: `run-opened`, `teardown-intent`, `resource-attempt`, `resource-result`,
`recovery-observation`, and `teardown-complete`. Transition validation and append share the ledger's
exclusive lock. Facts contain bounded identity/evidence references and classifications, never raw
prompts, message text, stdout/stderr, or mutable `open`/`closed` summaries. Each fact retains #351's
authoritative leaf `subplot_id`; root records on behalf of that leaf and does not invent a
coordinator-only producer identity. Open runs/resources and completion are projected from one
chain-verified snapshot.

R10. **The leak invariant is isolated and source-aware.** CI constructs a temporary Git repository,
broker registry, and outcome worktree registry, injects one unledgered worktree, proves the invariant
fails, registers/reclaims it through production adapters, and proves it passes. Source-aware
conformance also fails a production spawn path without broker registration or a teardown consumer.
CI never enumerates or deletes the developer's global worktree set. A live repository census and any
cleanup are separate attended acceptance actions.

R11. **Production lifecycle wiring is executable.** The team-execution protocol contains exact Saga
CLI invocations at B0/B1, all observed terminal branches, B8, and recovery seams. Saga hooks use the
same CLI/library, have bounded timeouts, never trust transcript prose, and fail visibly without
claiming completion. `SessionEnd` runs `request` with a five-second hook timeout; `SessionStart`
with matcher `startup|resume` runs `recover --expired-only --max-actions 4` with a 15-second timeout. Tests invoke
production functions/CLI and hook JSON, so prose-only B8 wiring cannot pass.

R12. **Sibling ownership stays intact.** #351 owns delivery settlement, casualty accounting, and
retry; #355 owns bridge evidence rejection/quarantine; #356 owns leases/fencing/worktree sweep; #357
owns liveness scoring, ack, and re-ping; #358 owns terminal orchestration and authorized stop/release
action adapters. #347's ship teardown is a pattern for reconcile/receipt semantics only and does not
become the team-run state store.

R13. **Release integrity is atomic.** From the merged post-#357 base (verified 2026-07-18), bump
fleet-core 0.14.0 to 0.15.0, Saga 0.101.0 to 0.102.0, and team-execution 2.20.0 to 2.21.0 (#357
itself took team-execution to 2.20.0 in PR #619). The fleet-core bump publishes
the owner-admission closing fence required to prevent spawn-versus-completion races. Update all three
manifests, marketplace rows, changelogs, minimum-version/drift guards, Saga hook manifest, team
operator references, and engineering journal in the same PR. Refresh and reapprove exact increments
if the base or required API differs.

---

## High-Level Technical Design

```text
Phase B preflight
  open team_run_id + canonical owner
  reserve/register each resource before spawn
                 |
                 v
        observed terminal boundary
                 |
                 v
        Step B8 teardown driver <--------- SessionStart / explicit recovery
          1. append intent                           ^
          2. verified snapshot                       |
          3. typed owner actions              crash / SIGKILL
          4. append outcomes                         |
          5. reconcile ------------------------------+
                 |
        +--------+---------+
        |                  |
 zero open             retained/failed
 teardown-complete     terminal-but-blocked
 completion receipt    recovery remains armed
```

### Derived terminal contract

One `team_teardown.v1` projection is returned by `status` and `reclaim-all`:

```text
team_run_id
terminal_reason: success | hard-fail | operator-abort | andon | recovered-crash
intent_id
resources[]:
  resource_id, generation, kind, owner_ref
  action, disposition, evidence_refs[]
open_count
released_count
retained_count
failed_count
completion_fact_ref: string | null
```

`open_count == 0` plus a valid `teardown-complete` fact is the only completed teardown. A terminal
business result with open resources remains a truthful blocked terminal and can be recovered later.

### Resource action matrix

| resource kind | trusted action | completion evidence | retain when |
|---|---|---|---|
| resident Agent teammate | runtime stop request, await terminal, broker release-owner | host stop/terminal receipts plus current token | no terminal receipt, mismatch, stop failure |
| owned subprocess | verify PID/start/boot/run, TERM, optional policy-bound KILL, release | process absence with same identity plus signal receipt | identity mismatch, permission, alive after allowed policy |
| outcome worktree | #356 `sweep` only | broker classification plus outcome registry/reap result | live owner, dirty/unmerged/unsafe path, reap failure |
| provisional/unused lease | broker idempotent release | exact owner/tool/batch identity | claimed by a live child or identity mismatch |

### Hook and recovery contract

- `SessionEnd`: five-second bounded best-effort
  `request --cwd <trusted hook cwd> --reason <trusted reason>`;
  never says the run is closed merely because the hook ran or timed out.
- `SessionStart startup|resume`: read-only discovery of open runs, then the 15-second bounded
  `recover --expired-only --max-actions 4`; every destructive action still passes the same
  broker/process/worktree guards.
- explicit CLI: `status`, `request`, `reclaim-all`, and `recover`; JSON output is bounded and uses
  stable reason codes. Dry-run is available for attended census, but is not accepted as completion.

---

## Key Technical Decisions

- **KTD1 - compose #351/#356 rather than build a reclamation ledger.** Live ownership and the
  no-new-admission closing fence belong in the broker; immutable teardown history belongs in run
  facts. A third store would create cross-store atomicity and stale-status bugs.
- **KTD2 - B7 cannot claim completion before B8.** B7 calculates gate results and prepares the
  report; B8 is the final transition and its receipt gates the word `complete`.
- **KTD3 - exact process death is unrecoverable synchronously.** Hooks improve coverage, but only a
  later recovery run plus TTL/dead-owner proof can handle `SIGKILL` or host death honestly.
- **KTD4 - action authority follows resource type.** Runtime API for residents, identity-checked
  signals for owned subprocesses, and #356 sweep for outcome worktrees; no generic `kill -9` or path
  deletion primitive is introduced.
- **KTD5 - liveness suspicion never grants teardown.** #357 confirmation or explicit segment
  shedding is required, and current #356 ownership is rechecked at action time.
- **KTD6 - partial teardown is a blocked terminal.** Every retained/failed entry remains projected;
  the run never disappears and repeated recovery converges by stable action keys.
- **KTD7 - CI proves the mechanism in isolation.** Developer worktree state is nondeterministic and
  potentially valuable; CI plants its own leak and production adapters close it.
- **KTD8 - ship teardown is a semantic pattern, not shared state.** Its reconcile-then-receipt and
  fail-loud behavior are reused, while team teardown relies on fleet leases and run facts.
- **KTD9 - SessionEnd is best effort, SessionStart is recovery.** Hook limitations are part of the
  operator contract and tests; neither hook is described as an infallible finalizer.

These decisions are recorded under `{#team-execution-teardown-358}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

---

## Implementation Units

### U1. Canonical teardown event family and projection

**Goal:** Add the no-new-admission closing fence, typed append-only teardown facts, and one
chain-verified projection of open runs and resources.

**Requirements:** R1-R4, R9, R12.

**Dependencies:** #351 and #356 merged.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py`,
`plugins/saga/scripts/run_ledger.py`, `plugins/saga/scripts/team_teardown.py` (new),
`tests/test_fleet_lease_broker.py`, `tests/test_run_ledger.py`,
`tests/test_team_teardown.py` (new).

**Approach:** Add the broker-locked owner closing fence, `kind=teardown`, bounded event builders,
stable action identities, and locked transition validation. Read separate lock-consistent broker and
chain-verified run-fact snapshots into one immutable decision input without claiming cross-store
atomicity; action-time rechecks close that safety gap. Keep action execution behind injected adapters
so unit tests do not signal real processes or remove real worktrees.

**Test scenarios:** Acquire before close succeeds; acquire/reserve/claim/retry after close refuses;
close-versus-concurrent-acquire serialization; valid open-intent-attempt-result-complete chain;
duplicate identical event; conflicting duplicate; attempt without intent; result without attempt;
complete with open resource;
partial result then retry; broken/torn chain; corrupt broker; unknown schema/kind; bounded IDs and
refs; two concurrent reclaim callers allocate one logical action.

**Verification:** No mutable open/closed summary exists; one verified snapshot deterministically
projects the same open set and repeated calls cannot double-allocate an action.

### U2. Non-skippable terminal driver and B8 contract

**Goal:** Make all coordinator-observed terminal paths enter one idempotent B8 driver before
completion can be asserted.

**Requirements:** R2-R5, R9, R11-R12.

**Dependencies:** U1 and #356's minimum Step B8 adoption.

**Files:** `plugins/saga/scripts/team_teardown.py`,
`plugins/team-execution/skills/team-execution/SKILL.md`,
`plugins/team-execution/skills/team-execution/references/teardown-reclamation.md` (new),
`tests/test_team_teardown.py`, `tests/test_team_execution_plugin.py`.

**Approach:** Refactor the #356 minimal sequence behind `request`/`reclaim-all`. B0 opens the run;
B1 registers before spawn; success, hard-fail, operator abort, and andon use one `finally`-style
terminal driver. B7 becomes gate/report preparation. B8 closes owner admission before snapshotting,
then reconciles/actions/reconciles and rechecks that closed broker generation. Only the zero-open
receipt allows the final report to call the run complete.

**Test scenarios:** Each terminal reason reaches B8; exception during B1/B2/B3-B6; abort before any
spawn; abort after partial spawn; andon; repeated B8; action exception; corrupt evidence; zero
resources; retained resource; completion wording absent before receipt. Protocol conformance invokes
the real CLI symbols named by the skill.

**Verification:** There is one terminal entry function and no branch/configuration can emit a
completion receipt without a successful B8 projection.

### U3. Safe process, resident, and lease action adapters

**Goal:** Reclaim only resources provably owned by the current run and retain everything ambiguous.

**Requirements:** R4, R6-R8, R12.

**Dependencies:** U1-U2 and #357 merged.

**Files:** `plugins/saga/scripts/team_teardown.py`, Saga broker adapter from #356,
`plugins/team-execution/skills/team-execution/references/teardown-reclamation.md`,
`tests/test_team_teardown.py`, `tests/test_fleet_lease_broker.py`, relevant outcome worktree tests.

**Approach:** Implement injected resident-runtime, process, lease, and worktree-sweep adapters. Recheck
current token and trusted identity immediately before each action. Stop residents through host API;
TERM only exact owned PIDs; allow KILL only for the explicit escalation class; invoke #356 sweep for
worktrees. Record host/process/sweep receipts by digest/ref before releasing ownership.

**Test scenarios:** Resident stop success/failure/lost receipt; already terminal; current vs
superseded token; PID reuse; boot mismatch; process exits during identity check; TERM success; TERM
timeout without escalation; explicit TERM-then-KILL; permission error; provisional release; active
worktree retained; dead-owner worktree swept; dirty/unmerged/escaping/unregistered/primary/self
retained; reap failure then retry.

**Verification:** Tests use owned subprocess fixtures and temporary Git repositories only; no test
signals the test runner or touches a real developer worktree.

### U4. Confirmed idle eviction and eventual recovery

**Goal:** Compose #357 liveness with B8 actions and recover runs whose original coordinator vanished.

**Requirements:** R5, R7, R9, R11-R12.

**Dependencies:** U1-U3 and #357.

**Files:** `plugins/saga/scripts/team_teardown.py`, `plugins/saga/hooks/team_teardown_hook.py` (new),
`plugins/saga/hooks/hooks.json`, #357 liveness adapter/reference,
`plugins/team-execution/skills/team-execution/references/teardown-reclamation.md`,
`tests/test_team_teardown.py`, `tests/test_saga_hooks.py`, `tests/test_team_execution_liveness.py`.

**Approach:** Translate only confirmed liveness decisions or explicit segment shed into stop intent.
Add a five-second SessionEnd request and a 15-second, four-action SessionStart expired-only recovery
hook using trusted hook input.
Recovery projects open runs, proves process/worktree owner death through #356, and invokes the same
actions. It emits a recovery observation even when nothing is safe to reclaim.

**Test scenarios:** Phi suspect no action; idle notice no action; ack/re-ping pending no action;
confirmed-stalled stops exact resident; warm peer retained; lost SendMessage receipt retained;
SessionEnd success/timeout/malformed input; SessionStart no-run/read-only discovery, expired dead
owner recovery, expired live owner retained, reboot identity, repeated startup, interrupted recovery,
and subprocess killed before B8 then recovered after injected TTL.

**Verification:** Kill-mid-run acceptance proves eventual cleanup after a recovery call, not an
impossible exact-death callback; hook failures never fabricate `teardown-complete`.

### U5. Isolated leak invariant and production-site conformance

**Goal:** Make a leaked resource and an unwired spawn fail deterministically in CI without depending
on developer state.

**Requirements:** R1-R3, R6, R10-R12.

**Dependencies:** U2-U4.

**Files:** `plugins/saga/references/teardown-consumer-sites.md` (new),
`tests/test_teardown_ci_invariant.py` (new), `tests/test_team_execution_plugin.py`, spawn-site
conformance tests from #350/#356.

**Approach:** Extend the source-aware inventory with run-open, register, renewal, terminal driver,
action owner, release, recovery, and proof columns. In a temporary real Git repository, create one
worktree outside the fixture registry and assert the invariant reports it, then register and reclaim
through production adapters and assert zero unexplained entries. Add negative source fixtures for an
unregistered spawn and a terminal branch that bypasses B8.

**Test scenarios:** Clean fixture; one unledgered worktree; registry entry with missing path;
unrelated external worktree classified out of managed scope; active owner retained; failed cleanup
still red; successful retry green; injected new Agent/process/worktree spawn missing registration;
injected terminal completion missing B8; live-census dry-run makes no files/ref changes.

**Verification:** The invariant fails before fixture cleanup and passes after it in one hermetic test;
its command never inspects or mutates the machine's unrelated Git common directories.

### U6. Release surfaces and full gate

**Goal:** Publish the executable teardown/recovery contract coherently from the refreshed Wave 3
baseline.

**Requirements:** R10-R13.

**Dependencies:** U1-U5.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`,
`plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, both
consumer changelogs plus the fleet-core changelog, Saga hook manifest, version/drift tests, operator references, and
`docs/engineering-journal/DECISIONS.md`.

**Approach:** Bump fleet-core to 0.15.0, Saga to 0.102.0, and team-execution to 2.21.0 from the
merged post-#357 base (fleet-core 0.14.0 / Saga 0.101.0 / team-execution 2.20.0); update minimum
compatible fleet-core/Saga references. Document live
census/dry-run and resource-specific recovery, but do not perform current-worktree cleanup in CI or
as an unreviewed release side effect.

**Test scenarios:** Local and installed layouts resolve the same teardown CLI; hook commands resolve;
old/missing Saga or broker blocks armed B8; marketplace/manifests/changelogs agree; second teardown
store/reaper or dead inventory row fails conformance.

**Verification:** Full gate and release-surface parity are green from a clean refreshed branch.

---

## Requirement Coverage

| requirement | units | primary proof |
|---|---|---|
| R1-R2 | U1-U2, U5 | one broker/ledger pair, stable run/resource identities, spawn inventory |
| R3-R5 | U1-U2, U4 | all-terminal matrix, idempotency, crash recovery |
| R6-R8 | U3-U4 | typed resource actions, dead-owner/PID checks, confirmed idle boundary |
| R9 | U1-U4 | locked transition matrix and chain-verified projection |
| R10-R11 | U2, U4-U5 | hermetic leak fixture, real CLI/hook/lifecycle conformance |
| R12 | U1-U5 | sibling ownership and duplicate-mechanism guards |
| R13 | U6 | installed resolution, hook, version, and release parity |

---

## Scope Boundaries

### In scope

- Team run identity, append-only teardown facts, projection, and idempotent B8 driver.
- Conservative action adapters for residents, explicitly owned subprocesses, leases, and #356
  outcome worktree sweep.
- Confirmed idle eviction, SessionEnd request, SessionStart/explicit recovery.
- Hermetic leak invariant, production-site inventory, Saga/team release surfaces.

### Non-goals

- A second lease/reclamation registry, TTL reaper, heartbeat detector, liveness store, mutable queue,
  or daemon.
- Treating phi suspicion, chat, idle notice, pointer age, or agent prose as teardown authority.
- Arbitrary PID signaling, process discovery by name/argv alone, direct `git worktree remove`, force
  cleanup, deleting dirty/unmerged/live/self/primary worktrees, or automatic cleanup of the nine
  current developer worktrees.
- Changing #351 delivery/retry, #355 evidence quarantine, #356 lease/fence/sweep rules, #357
  scoring/re-ping, worker-cache scheduling, artifact-pointer semantics, or ship ceremony state.
- Cross-host distributed leases, a background scheduler/service, deployment, credential operations,
  production-data access, or Codex runtime parity (later outcome leaves own those).

---

## Risks and Mitigations

| risk | impact | mitigation/proof |
|---|---|---|
| teardown releases a live or reused PID | data loss / foreign-process kill | PID+start+boot+run identity; current token recheck; retain on ambiguity |
| a spawn races zero-open completion | resource appears after receipt | broker-locked owner closing fence before snapshot; final generation recheck |
| completion is reported before resources close | invisible leak | B7 draft only; B8 zero-open fact/receipt gates completion wording |
| crash bypasses finalizer | retained resources | explicit eventual guarantee; SessionStart/CLI recovery plus TTL/dead-owner proof |
| duplicate registry diverges from broker | false cleanup/open counts | conformance forbids second store; broker live + run facts historical |
| idle heuristic kills warm productive worker | lost work/context | only #357 confirmed result or explicit shed; phi/notice alone never acts |
| CI deletes local developer work | destructive test | temporary repo/registry only; live census dry-run and explicit later authority |
| hook timeout is mistaken for success | silent leak | hook receipt is request evidence only; completion requires derived zero-open fact |
| shared release surface collides | bad install/runtime | serialized refreshed main; exact version reapproval; installed-resolution tests |

---

## Verification

Run focused gates after their units, then the full repository gate:

```bash
uv run pytest tests/test_run_ledger.py tests/test_team_teardown.py -v
uv run pytest tests/test_fleet_lease_broker.py tests/test_outcome_worktrees.py -v
uv run pytest tests/test_saga_hooks.py tests/test_team_execution_liveness.py -v
uv run pytest tests/test_teardown_ci_invariant.py tests/test_team_execution_plugin.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
git diff --check
```

The concurrency validator independently challenges two reclaim callers, retry/supersession, PID exit
and reuse, release-versus-stop ordering, and repeated recovery. The event-flow validator traces
run-open, terminal intent, per-resource attempts/results, recovery, and completion, proving no
missing/failed receipt closes a resource. Both validators run sonnet at medium effort; the four
high-judgment reviewers run opus at high effort (see the Workflow Structure table).

Manual acceptance records a no-write live worktree census, classifies each candidate through the
production dry-run, and performs no cleanup without separate resource-specific authority. A
temporary subprocess kill plus injected TTL/recovery proves the crash path. Hook readback proves the
installed Saga plugin exposes the exact SessionEnd/SessionStart commands and bounded behavior.

---

## Failure Modes and Stop Conditions

- A second reclamation ledger, worktree TTL reaper, mutable open/closed store, or liveness algorithm
  appears: stop and consolidate into #351/#356/#357.
- B7 or any early/failure branch says complete without a valid B8 zero-open receipt: stop as a P0/P1
  lifecycle defect.
- Phi suspicion, an idle notice, chat, pointer age, prompt text, or agent-provided identity triggers a
  stop/release: stop at the trust boundary.
- A PID is signaled without exact start/boot/run identity, or a worktree is removed outside #356
  sweep: stop as unsafe destructive behavior.
- SessionEnd is described as guaranteed after `SIGKILL`/host death, or hook timeout is accepted as
  closure: stop and restore the eventual-recovery contract.
- A retained/failed resource disappears from projection, complete is emitted with nonzero open count,
  or duplicate reclaim double-acts: stop as evidence/idempotency failure.
- CI consults/deletes live developer worktrees, or attended cleanup lacks separate authority and
  dead-owner/registry proof: stop before action.
- Any P0-P3 document/code-review finding remains, a required validator lacks gate-capable evidence,
  full gates fail, or release metadata drifts: no PR/merge.

---

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | vehicle | agent_type | model | effort | isolation | mutation | required_evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | session-root | - | - | - | primary-worktree | root-only | authorized-diff,focused-tests |
| review-devils | implement | review | devils-advocate | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-security | implement | review | security | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-architecture | implement | review | architecture | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-testing | implement | review | testing | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,test-gaps |
| validate-concurrency | implement | validate | concurrency | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | sonnet | medium | worktree | none | concurrency-matrix,command-results |
| validate-event-flow | implement | validate | event-flow | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | sonnet | medium | worktree | none | event-trace,command-results |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | session-root | - | - | - | primary-worktree | root-only | fixed-findings,full-gate,release-parity,git-receipt |

## Workflow Operating Contract

- Runtime: root is the operator's Claude Code session on the cc-workflow backend. Root owns
  implementation, Git, integration, PR creation, merge under explicit operator confirmation, issue
  closure, and board reconciliation. The authorized subject is this issue's implementation paths
  plus exact release surfaces; root records the pre-existing Git baseline before `implement`, and
  unrelated worktree paths are excluded.
- Lens dispatch: the six agent-lens rows execute as `agent()` calls inside one root-authored Claude
  Code Workflow script, each with exactly the agent_type, model, effort, and worktree-isolation
  cells above, routed through a bounded pool so total in-flight subagents never exceed 3. Each call
  embeds its lens charter below plus the diff and evidence scope. Spawn parameters are
  harness-recorded and root records per-lens receipts in the review artifacts; no cryptographic
  attestation is claimed. If the Workflow tool is unavailable, halt and page the operator — never
  silently downgrade to another dispatch path.
- `agent_type=saga:readonly-verifier` is the repo's mandated read-only sandbox profile for
  review/verify spawns (Bash/Read/Grep/Glob in a disposable worktree, per
  `plugins/saga/references/sandbox-spawn-sites.md`); per-call model/effort opts override the
  profile's default tier. Root audits the primary tree after every lens attempt and treats any
  unexplained diff as workflow-integrity failure.
- Lens charters: **devils-advocate** — challenge assumptions and hunt edge cases in terminal-entry
  coverage, teardown-fact idempotency, owner-closing-fence races, and crash-recovery ordering;
  **security** — trust boundaries of resource actions (typed process stop, lease release, worktree
  sweep), path and identity validation, dead-owner proof handling, and refusal paths for
  unauthorized destructive actions; **architecture** — separation between fleet-core primitives,
  Saga adapters, and team-execution orchestration, consistency with the #351/#356/#357 canonical
  authorities, and release-surface coherence; **testing** — coverage adequacy of the
  terminal/recovery matrices, negative-path assertions on rejection guards, and hermetic-CI
  leak-invariant quality; **concurrency** (validator) — independently assess spawn-versus-completion
  fencing, duplicate reclaim, partial-crash replay, and lock interleavings from captured command
  evidence; **event-flow** (validator) — trace teardown facts end to end (register → terminal →
  reclaim → complete → recovery) across ledger, projection, and consumer sites.
- Root fixes every P0-P3 finding and re-runs the affected lenses fresh. Three unsuccessful
  remediation cycles halt and page the operator. Any model, effort, lens, validator, or
  execution-class change requires a newly approved workflow candidate. The approval anchor is the
  SHA-256 of the exact `## Workflow Structure` and `## Workflow Operating Contract` section bytes,
  recorded in the delta review artifact.
- Git mutation, resource action, PR creation, merge, issue/board mutation, and completion remain
  root-only. No deployment, credential, production-data, force-push, branch-deletion, broad process
  kill, or unproved worktree deletion is authorized.
- Workflow receipts, findings, command logs, workspace audits, resource-action receipts, PR URL,
  merge SHA, issue close, and board reconciliation are retained in the repo's review and
  work-session artifacts and on the issue/PR.

---

## Completion Gate

Completion requires every published acceptance outcome plus the corrected authority, identity,
crash-recovery, and hermetic-CI proofs; zero open P0-P3 doc/code-review findings; both required
validators passing with gate-capable evidence; full verification green; one atomic issue PR merged;
issue #358 closed and its Operations card reconciled; dependent outcome nodes refreshed; and the
outcome worktree clean except for the next planned wave. Current developer-worktree cleanup is not a
hidden merge condition: any attended cleanup must have its own dry-run receipt, explicit authority,
and per-resource #356 safety proof.
