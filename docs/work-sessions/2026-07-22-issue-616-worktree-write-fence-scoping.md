# Work session — issue #616 worktree write-fence scoping

- **Saga:** `issue-616` · branch `work/616-worktree-write-fence` (base `ab84003b`)
- **Plan:** `docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md`
- **Backend:** cc-workflows-ultracode (operator-approved), spec
  `docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-spec.json`
- **D1 pin:** operator (Jeff), 2026-07-22 — KTD3 resolution (i): unfenced non-isolated spawns;
  admission, mutation-mode check, and hook verification remain. Recorded in the doc-review
  artifact and the saga tick.

## Governed launch (first real-work run on the #615 machinery)

Invocation `9417e058-6bd8-49c0-af83-ac2a1c96ecf5`, batch
`workflow:35bf29747b1253e8b9658900:a4e523b6c6d47ba2fb8949f0`, width 3, attest
`launch_authorized: true`. Settlement manifest + one spawn attempt per unit (U1-U4) recorded
under dispatch `workflow:35bf29747b1253e8b9658900:invocation:a4e523b6c6d47ba2fb8949f0`.
Workflow run `wf_c0db62d7-210`.

## Pass 1 outcome: U1 built green, panel refuted 3/3 — machinery, not code

U1 (opus/high) landed the full broker diff and self-reported: broker suite 75 passed
(8 new tests R1-R6 + supersede + invalid-boundary), ruff + format + mypy clean, broader run
410 passed / 3 failed with all 3 failures the plan-anticipated U2 adapter seam in
`tests/test_saga_hooks.py`.

The refute-3 panel **upheld every mechanism claim by direct source read** (field placement,
backfill idiom, `_agent_isolation` normalizer, KTD3 three-way branch at claim, recycle reset,
`reserve_batch`/`assert_write_target` untouched) but voted REFUTE 3/3 **solely on the
quantitative claims** — every verifier's Bash was fenced by the saga lease-mutation hook
("no live fleet lease bound"), so pytest/ruff/mypy could not be reproduced, and the refute
mandate treats unproven as refuted. All three explicitly recorded "unproven, not shown false;
no counter-evidence."

**Root cause:** the workflow lease reservation carries `execution_ttl_seconds: 300`, and #615's
D1 chose mutation-path renewal (`_renew_batch_member` in `assert_write_target`) over a TTL
change. A long *read-only* stretch (U1's full pytest battery) performs no mutations, so nothing
renews; the batch lapsed fail-closed mid-U1 (the builder's own Bash got fenced near its end),
and the verifiers spawned after expiry never got leases at all.

## Driver adjudication (evidence reproduced in the driving session)

The driving session is the producer of record and is unfenced. Reproduced at the U1 diff on
`work/616-worktree-write-fence`:

- `uv run pytest -q tests/test_fleet_lease_broker.py` → **75 passed**
- `uv run ruff check .` → clean; `uv run ruff format --check .` → 437 files already formatted
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → clean
- `uv run pytest -q tests/test_saga_hooks.py tests/test_saga_workflow_emitter.py` → the
  anticipated failures reproduce, all in `tests/test_saga_hooks.py` (pre-#616 always-fenced
  expectations; U2's seam to update)

Verdict: pass-1 refute was a verifier-tooling casualty, not a U1 defect.

## Pass 2 relaunch (in flight)

- Re-reserved + attested under the **same invocation id** (crash/resume reuse per SKILL) —
  fresh batch slots, `launch_authorized: true`.
- **Driver-side cooperative renewal:** background loop renews the batch every 240 s
  (`workflow_emitter.py renew`, 2-hour iteration cap; log `.saga/renew-loop-9417e058.log`) —
  `renew_batch` renews every live slot under one lock, covering read-only verifier leases that
  the mutation-path renewal can never touch.
- Cache-busted the three U1 verifier prompts (re-verification note instructing a live
  quantitative check) so the resume replays U1's cached result but re-runs the panel with
  working Bash; U2-U4 then run fresh. Resumed as run `wf_c0db62d7-210`.

## Pass 2 outcome: refuted 3/3 again — a SECOND, distinct machinery fault

Pass 2's verifiers were fenced by **installed-plugin forward-schema poisoning**, not TTL expiry:
the driver's re-reservation ran *after* U1's diff landed, so the repo broker serialized the new
`isolation` key into the batch lease records in the shared registry
(`~/.local/state/infiquetra/fleet-leases/registry.json`). The installed hook broker (fleet-core
0.19.0, correctly current — not #642 staleness) hard-rejects unknown registry fields
(`HALT — delegated mutation refused: leases.0305cda0…: unknown field(s): isolation`), so **every
hook-fenced Bash on the machine failed closed** — verifier claims never bound, a slot expired at
the 30 s claim TTL, and `renew_batch` refuses batches containing an expired lease (renew loop
logged 2 misses, then was stopped). All three verifiers again upheld every mechanism claim by
direct read (field :841, backfill :865-868, normalizer :278-292, threading :2288/:2754,
KTD3 branch :2691-2693, recycle :3952, untouched reserve_batch/assert_write_target) and refuted
only the unexecutable quantitative claims as unproven-not-false. One verifier explicitly
identified the schema-skew mechanism in its verdict.

This is **#617's defect demonstrated live** (registry schema read-tolerance), closing a
chicken-and-egg: #617 is blocked by #616, and #616 could not verify itself under armed hooks
because #617 isn't fixed. Pass-1 vs pass-2 asymmetry: pass 1 reserved *before* U1 wrote the
field (old-schema records, hooks fine, TTL was the killer); pass 2 reserved *after* (new-schema
records, schema was the killer).

**Driver cleanup:** released the poisoned batch via the repo emitter
(`released_lease_ids`: 0305cda0/9c0e3aae/eda259d9) → registry back to 0 leases, restoring armed
hooks machine-wide.

## Pass 3 relaunch (in flight)

Both faults mitigated without touching gates or hooks:

- **Reservation pinned to the installed broker:** all choreography (`reserve`/`attest`/`renew`)
  runs with `FLEET_COMMONS_ROOT=/Users/jefcox/.claude/plugins/cache/infiquetra-plugins/fleet-core/0.19.0`
  — the shim's first-class rung-1 override (fail-loud, `FLEET_COMMONS_DEBUG=1` confirmed rung=1
  on every call). Lease records stay old-schema (verified: 3 slots, zero `isolation` keys), so
  installed hooks parse cleanly all pass. Verifier pytest still exercises U1's code — the test
  module loads the repo broker in-process with hermetic state dirs.
- **240 s renew loop** (pinned, bg task) covers pass-1's TTL starvation.
- Verifier prompts cache-busted with the pass-3 explanation; same invocation id
  (crash/explicit-resume reuse), resumed as run `wf_c0db62d7-210` — U1 stays cached, panel
  re-runs live, U2-U4 fresh.

## Pass 3 outcome: stopped by the driver mid-run — a THIRD distinct machinery fault

The schema fix held (old-schema records, hooks parseable), but the autonomous-loop heartbeat
found the registry **empty** minutes after reservation: all 3 slots expired at the 30 s
`claim_ttl_seconds` before the workflow's first live spawn could claim — a resume replays
cached agents first, so the first real claim comes minutes after `reserve`. The running
verifier had no lease (Bash fenced again), so the driver stopped the workflow before burning
the three doomed verifier runs. Also established from the renew logs: **the driver
`renew_batch` loop never succeeded once in any pass** — with serialized units, the unclaimed
slots lapse at claim TTL and `renew_batch` refuses any batch containing an expired member.
The pass-1 "mitigation" was therefore never protective.

## Pass 4 relaunch (in flight) — all three faults mitigated

- **Claim TTL 30 → 1800 s** in the driver-authored reservation metadata
  (`workflow_lease_reservation.v1`). The emitter hard-codes 30/300 and only validates
  positivity; `policy_sha256` covers the concurrency policy, not the TTLs, so this is a
  hash-safe run-parameter change. Verified post-reserve: 3 slots, `ttl_seconds: 1800`,
  zero `isolation` keys.
- **Per-member keeper loop** (scratchpad `lease_keeper.py`, log
  `.saga/lease-keeper-9417e058.log`): every 90 s, `inspect()` the registry via the installed
  0.19.0 broker and `renew(lease_id, token=FencingToken.from_dict(...))` each **live** lease
  individually, skipping expired members — replacing the all-or-nothing `renew_batch` path.
  This covers the 300 s execution TTL on claimed leases (the hook reads
  `INFIQUETRA_FLEET_TTL_SECONDS` from harness env, unreachable mid-session).
- Reservation/attest again pinned to the installed broker (rung-1), same invocation id,
  verifier prompts cache-busted with the pass-4 note; resumed as run `wf_c0db62d7-210`
  (U1 cached, panel live, U2-U4 fresh).

## Pass 4 outcome: 2/3 refuted — first working verifier UPHOLDS EVERYTHING; a fourth fault fences the other two

**Verifier 1 (abc15ebd) had fully working Bash and upheld all claims including the quantitative
ones by executing them itself**: 75 passed on the broker suite, ruff check + format clean, mypy
clean, and the 3 broader failures independently confirmed as the plan-anticipated U2 seam in
`tests/test_saga_hooks.py` (only the exact "410 passed" total noted as not reproduced, explicitly
non-refuting). This independently corroborates the driver adjudication of passes 1-3.

Verifiers 2 and 3 upheld every mechanism claim by direct read and refuted only on a NEW fence:
`expected exactly one fleet lease bound to agent <id>; found 0` — their SubagentStart claims
never bound. Keeper-log forensics: at 03:05-03:07 the registry held the 3 slots (1800 s TTL);
by 03:08:54 **all three lease records had vanished**, ~12 minutes before the workflow ended.
Verifier 1 completed inside that window; verifiers 2/3 spawned after the batch was gone. The
deletion coincides with verifier 1's terminal hook (stamped-slot dual-signal close) — fault #4,
mechanism not yet pinned to a line.

Honest note: the pass-4 keeper loop never successfully renewed anything — every attempt failed
with `KeyError` (the installed broker's `inspect()` output does not carry the fencing token the
way the keeper assumed). It played no protective role; pass 4's partial success came from the
1800 s claim TTL + rung-1 pin alone.

**Panel verdict record across 4 passes: 10 verifier verdicts, every mechanism claim upheld in
all 10, zero counter-evidence ever produced; quantitative claims confirmed by the one verifier
that ever had working Bash, and by the driver.** All four panel failures were
lease-infrastructure casualties: (1) execution-TTL starvation, (2) forward-schema poisoning,
(3) claim-TTL vs resume startup latency, (4) whole-batch disappearance at first child terminal.

## HALT — operator decision required (no further relaunches)

Driver stopped relaunching per its stated commitment and paged the operator with three options:
(A) adjudicate the U1 panel and resume U2-U4 governed, (B) finish U2-U4 in the driving session,
(C) diagnose fault #4 first.

## Operator decision: **A** (Jeff, 2026-07-23) — pass 5 in flight

U1's gate throw replaced with a logged operator-adjudication block (U1 only; U2-U4 panels remain
fully armed and throwing). Fallback agreed: if U2's panel dies to the same lease lottery, finish
the remainder driver-side (B). Pass-5 mechanics:

- Fresh pinned reserve + attest (rung-1, 1800 s claim TTL), `launch_authorized: true`.
- **Keeper v2** (60 s cadence): token reconstructed correctly this time —
  `FencingToken(broker_epoch=<registry top-level>, fencing_sequence=<lease record>)`, since
  `Lease.to_dict()`/`inspect()` deliberately omit the token (v1's KeyError). One-shot smoke test
  renewed all 3 fresh slots before launch. Also **self-heals fault #4**: when the batch has zero
  lease records, re-runs pinned reserve+attest so the next child spawn has slots to claim.
- Resumed as run `wf_c0db62d7-210`: U1 + pass-4 verifier verdicts replay from cache, the
  adjudication logs, U2-U4 run fresh.

## Durable machinery findings (for LEARNINGS at ship + operator follow-up)

1. **Long read-only stretches starve the batch lease.** `execution_ttl_seconds: 300` +
   mutation-only renewal means any unit whose tail is a big pytest run outlives its lease;
   expiry is fail-closed and unrecoverable for later spawns in the batch. Driver-side
   `renew_batch` cadence is the working mitigation; a durable fix (renewal on the read path,
   longer TTL, or a broker heartbeat) is follow-up material — candidate new defect issue.
2. **Fenced verifiers convert "unverifiable" into "refuted 3/3".** A refute-mandate panel with
   no Bash can only refute quantitative claims; the panel kill then reads like a code failure.
   Verifier lease health should be a precondition of panel validity (e.g. under-strength
   handling when Bash is fenced), also follow-up material.
3. **Broker schema changes cannot be exercised through governed choreography under armed
   installed hooks until read-tolerance ships (#617).** Any new-schema lease record written to
   the shared registry breaks the installed (older) hook broker fail-closed, machine-wide. The
   working mitigation is pinning the choreography's writes to the installed broker via
   `FLEET_COMMONS_ROOT` (rung-1 override) so the registry stays old-schema during pre-merge
   verification; the durable fix is #617's accept-unknown-fields read path landing *before* any
   further registry schema additions.
4. **The 30 s claim TTL + serialized units make `renew_batch` structurally unusable and kill
   slow-to-claim runs.** Unclaimed slots lapse in 30 s; a workflow resume replays cached agents
   before its first live spawn claims; and one lapsed member makes `renew_batch` fail forever
   (all-or-nothing). Mitigations that worked: driver-authored claim TTL raise (the emitter's
   hard-coded 30/300 in `_lease_reservation_metadata` is the root parameter) plus per-member
   `renew(lease_id, token=...)` keep-alive that skips expired members. Follow-up candidates:
   make the emitter TTLs spec-configurable, and give `renew_batch` a skip-expired mode.

## U3 — verification-only: frozen-seam nil-impact + R9 canary rehearsal

Read-only, no plugin code/tests/release surfaces touched. Diff base: current worktree state on
`work/616-worktree-write-fence` (U1's landed broker diff).

### (a) codex byte-frozen `outcome_compat` seam — nil-impact evidence

`plugins/saga/scripts/outcome_compat.py` (1700 lines) is the frozen seam. Enumerated every
import/call it makes into the fleet-core broker surface:

- Consumed symbols: `broker.verify`, `broker.verify_agent`(not called directly but via helpers),
  `broker.prepare_agent_settlement`, `broker.commit_agent_settlement`,
  `broker.inspect_resource_head`, `broker.acquire_successor`, `lb.LeaseBrokerError`,
  `lb.FencingToken` (via `_broker_module(broker)`, which resolves the module the live broker
  *instance* was defined in — never touches `Lease`, `_LEASE_KEYS`, `to_dict`/`from_dict`,
  `worktree_root`, or `isolation` by name; confirmed by grep, no hits).
- U1's diff (`git diff origin/main -- plugins/fleet-core/scripts/fleet_commons/lease_broker.py`)
  touches exactly: `_agent_isolation` (new), `Lease` dataclass fields/`from_dict`/`to_dict`,
  `_new_lease`, `acquire_agent`, `claim`, `prepare_batch_call`, `_complete_foreground_lease`.
  None of `verify`/`verify_agent`/`prepare_agent_settlement`/`commit_agent_settlement`/
  `inspect_resource_head`/`acquire_successor`/`LeaseBrokerError`/`FencingToken` fall inside any
  touched hunk, and none of the consumed functions call into any touched function internally
  (grepped each consumed function's body for the touched-function names — no hits).
- Saga adapter side: `plugins/saga/scripts/lease_broker.py`'s diff (`_declared_isolation`,
  threaded into `reserve_hook_agent`) is a reservation-time (PreToolUse) hook-only surface;
  `outcome_compat.py` never imports `plugins/saga/scripts/lease_broker.py` — it only reaches the
  fleet-core broker via `_broker_module(broker)` on a caller-supplied instance.
- Registry-bytes concern (plan U3 framing: "the frozen seam consumes broker APIs, not registry
  bytes"): confirmed — `outcome_compat.py` never reads `leases.*` registry fields directly; all
  registry shape is opaque behind the broker API surface above.
- Executed the two cross-runtime contract test modules read-only, no code changes:
  `uv run pytest -q tests/test_outcome_cross_runtime_contract.py tests/test_cross_runtime_acceptance.py`
  → **172 passed**, 0 failed.

**Verdict: nil impact confirmed** — the `Lease.isolation` addition and the claim-time fence
policy branch are fully outside the frozen seam's consumed surface, by both static (import/call
enumeration) and dynamic (172/172 green, no diff) evidence.

### (b) #615 R9 scripted canary — hermetic rehearsal against the changed broker

Rehearsed the #615 R9 shape (width-1 `workflow_lease_reservation.v1` metadata →
`workflow_emitter.py reserve`/`attest` → simulated unstamped batch claim with a cwd → child
terminal → settle/release) hermetically in an isolated `INFIQUETRA_FLEET_STATE_DIR` (a fresh
`tempfile.mkdtemp` root, never the shared
`~/.local/state/infiquetra/fleet-leases/registry.json`), against the in-repo (post-U1) broker —
not the installed plugin cache. Script:
`/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/r9_canary_rehearsal.py`.

Steps and assertions:

1. `workflow_emitter.reserve(...)` with `reservation_width=1` → 1 lease minted.
2. `workflow_emitter.attest(...)` → `launch_authorized: true`.
3. `saga_lease_broker.broker(env).claim(session_id=..., agent_type="claude-child",
   agent_id="u3-canary-child-agent", worktree_root=<cwd>, batch_id=...)` with no prior
   PreToolUse stamp (`tool_use_id is None`) — the Workflow-runtime-child shape.
4. **R3 assertion (KTD3 row 3):** claimed lease has `isolation=None` (batch path, no declared
   isolation, KTD6), `tool_use_id=None` (unstamped), and `resource_ref` **does** carry
   `worktree_root` stamped to the cwd's normalized path (`os.path.normpath`, matching the
   broker's own `_safe_absolute_path`, not a symlink-resolved path) — byte-identical to
   pre-#616 (0.19.0) unconditional-stamp behavior for this slot class.
   `resource_ref` key set stays closed to `{logical_unit_id, worktree_root}`
   (`_AGENT_RESOURCE_KEYS`, untouched by U1). **Passed.**
5. `record_child_terminal(...)` → unstamped-slot child-signal-only recycle (per the existing
   `record_child_terminal` comment) resets the slot to unclaimed, live.
6. `workflow_emitter.release(...)` (`settle_batch`) → releases the now-unclaimed slot.
7. `broker.inspect()` → **0 leases remain** for the batch.

Result: `status: PASS`, all assertions held, isolated state dir and cwd temp dir removed in a
`finally` block. Confirmed post-run that the shared registry
(`~/.local/state/infiquetra/fleet-leases/registry.json`) carried no `u3-canary-*` batch id —
the rehearsal never touched live state.

**Verdict: R3 (batch-slot byte-parity with 0.19.0) holds** under the changed broker, rehearsed
hermetically pre-merge. This is a scripted rehearsal, not the operator-gated R8 live-acceptance
canary against the installed plugin cache under armed hooks (still required post-merge per the
plan).

## Pass 5 outcome: COMPLETE — U2 panel clean, U3/U4 delivered, all faults held off

Run `wf_c0db62d7-210` completed with 10/10 agents done, 0 errors. U2 (saga adapter
`_declared_isolation` + both reserve paths + seam tests) passed its fully-armed refute-3 panel
**0 refuted from all three verifiers** (upheld 10/11/8) — the first live clean panel of the
whole execution, proving the keeper-v2 + 1800 s claim TTL + rung-1 pin combination works. The
keeper log shows per-member renewals succeeding every 60 s throughout. U3 recorded nil-impact +
R3 canary PASS (section above). U4 landed the release surfaces (fleet-core 0.20.0, saga
0.111.0, marketplace sync, both CHANGELOGs, drift pins, DECISIONS `{#worktree-fence-scoping-616}`).

## Settlement + gates (driver, post-run)

- Batch released (3 lease ids), registry back to 0 leases.
- Single settlement pass for invocation `9417e058`: evidence files
  `dispatch.workflow-result.v1` per unit under
  `.saga/workflow-evidence-9417e058-.../`, all 4 units **delivered**, casualties 0,
  `halt_required=false`, DLQ empty.
- Phase 3 gates on the full diff: **pytest 5378 passed / 0 failed / 1 skipped**, ruff check
  clean, `ruff format --check` 437 files already formatted, mypy clean,
  `check_release_surface_parity` all plugins in parity, bandit on both changed brokers
  **identical to base** (5 pre-existing Low, 0 new).

## Code review + PR

Programmatic code-review at REVIEWED_SHA `c816aad5`: **clean** — 4 lenses (correctness,
security, testing at opus; conventions at sonnet, all sandboxed), zero P0/P1/P2; two confirmed
P3 test-coverage findings **repaired** at `a0a2dc02` (corrupt-isolation read path + recycled
slot re-stamp; 127 passed post-repair); one pre-existing P3 advisory deferred; one finding
validator-rejected with counter-evidence. Artifact:
`docs/code-reviews/2026-07-23-issue-616-worktree-write-fence-scoping-code-review.md`.
Reviewer-environment note: 3 of 8 sandboxed subagents hit the lease "found 0" fence mid-run —
same machinery family as the workflow faults; verification completed via retries and Read
fallback.

**PR #643** opened (draft) via ship_ceremony: branch pushed, title/body set (Fixes #616, ends
with the session URL). Merge only on explicit operator confirmation; merge-time sibling-PR
version-collision re-check owed. Post-merge: R8 live canary (operator-gated, #642
`FLEET_COMMONS_DEBUG=1` provenance check first) and the installed-plugin registry-skew rollout
note.

## Post-merge rollout + R8 acceptance (2026-07-23, operator "go ahead and merge, then continue")

**Merge.** PR #643 squash-merged to `main` as `0b6bcbf5` (single parent `ab84003b`, repo
convention); issue #616 auto-closed (completed) at 11:42Z; branch deleted local+origin. CI was
8/8 green at head `a52e36e3` and #643 was the only open PR (no sibling version collisions).

**Rollout + #642 provenance preamble.** `claude plugin update` materialized fleet-core 0.20.0
and saga 0.111.0 into the cache (unlike the 2026-07-22 incident it did not claim
"already latest") — but `installed_plugins.json` records **stayed pinned to 0.19.0/0.110.0**,
the #642 hazard recurring exactly as memorized. Hand-repaired both records (backup:
scratchpad `installed_plugins.json.bak-20260723-pre-616-rollout`), then the gate:
`FLEET_COMMONS_DEBUG=1` through the installed saga 0.111.0 shim from a neutral cwd resolved
**rung 3 → fleet-core 0.20.0** — provenance PASS.

**R8 legs.**

- **Unadmitted direct Agent spawn refused — PASS (live).** With 0 admissions, a real Agent
  spawn was halted pre-launch by the armed PreToolUse hook with the admission-required message.
- **Leg (a) non-isolated cross-cwd write — PASS (scripted-live).** Reservation via
  `reserve_hook_agent` (no `isolation` in tool_input) → `claim_hook_agent` → lease
  `isolation=None`, `resource_ref={logical_unit_id}` **without** `worktree_root` →
  `assert_write_target` permits a write outside the spawn cwd; file actually written.
- **Leg (b) worktree-isolated fence — PASS (scripted-live).** `tool_input.isolation='worktree'`
  → lease `isolation='worktree'`, `resource_ref` pins the canonicalized worktree root →
  outside-write refused (`MissingResourceError: write target … outside leased worktree`),
  inside-write permitted. Registry drained to 0 leases/0 admissions afterward.
- **Leg (c) #615 workflow-child canary — PASS (installed adapter).** The U3 rehearsal script
  re-pointed at the installed saga 0.111.0 adapter (broker resolved 0.20.0): width-1 reserve →
  attest → unstamped child claim with byte-parity `worktree_root` cwd stamp (R3) → child
  terminal recycle → release → 0 leases. `status: PASS`.

**Why legs (a)/(b) are scripted-live, not spawn-live — new machinery defect diagnosed.** Three
consecutive real spawn attempts lost their lease ("expected exactly one fleet lease bound;
found 0"); a 100 ms-resolution registry watcher pinned the mechanism: the PreToolUse
reservation (boot id and admission both healthy, same sysctl-derived cohort) is **wiped
101–156 ms after creation** — the moment the async Agent tool call returns its launch
metadata. PostToolUse[Agent|Task] runs `record_hook_parent` → broker
`record_parent_completed` (fleet-core 0.20.0 `lease_broker.py:3895`), which treats a matching
lease with `agent_id is None` as spawn-never-happened and removes it (:3913-3921), then pops
the session admission once no live agents remain (:3924-3927). With **async spawns the tool
result returns at launch**, so this "completion" cleanup races SubagentStart's claim; when it
wins, the child starts unbound and every delegated mutation is refused. This also explains the
code-review phase's 3-of-8 verifier lease losses (the claim won the race 5 times) and is a
strong suspect for pass-4's whole-batch disappearance at first child terminal. Timelines:
scratchpad `registry_timeline.log` / `registry_timeline2.log`.

**Additional structural hazard (not today's trigger).** macOS boot identity is derived
preferentially from `sysctl -n kern.boottime` (`darwin:<sha>`) with a utmpx fallback
(`darwin-utmpx:<sec>:<usec>`) — the two formats can never compare equal, and even the raw
seconds differ by 1 on this host. Any process cohort that fails `sysctl` (PATH, sandbox, fork
pressure on the 2 s timeout) silently treats all other cohorts' leases and admissions as
boot-stale and purges them on its next locked write.

**R8 verdict: PASS** — every fence-policy assertion holds on the shipped installed artifacts;
the live-spawn path is blocked by the pre-existing async-race machinery defect above, not by
the #616 diff. Follow-up defects to file (operator-directed): the async PostToolUse race, the
boot-id cohort split, findings 1/2/4 from the durable list, the pre-existing unfenced edge
(code-review finding #2), and the #642 recurrence evidence.
