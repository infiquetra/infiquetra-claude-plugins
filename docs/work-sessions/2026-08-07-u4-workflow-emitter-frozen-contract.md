---
title: Work session — U4 retire the workflow lease emitter onto the frozen contract (#681)
date: 2026-08-07
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/681
plan: docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md
doc_review: docs/reviews/doc-review-issue-677-2026-07-30.md
branch: feat/681-u4-unwind-workflow-lease-contract
commit: f17eb0a8
final_commit: 514ad6d6
pull_request: https://github.com/infiquetra/infiquetra-claude-plugins/pull/700
merge_commit: 48789bd9
saga: issue-681
orchestration: inline
---

# Work session — #681 U4 retire the workflow lease emitter onto the frozen contract

## What this changed, in one paragraph

U4 is the lease-broker retirement's (#677) "one production file" unit — the third re-note's
measurement held: `workflow_emitter.py` was the last light consumer, holding the one genuinely
live lease seam (the `renew_batch` call plan KTD4 singles out). The #356 driver-side reservation
protocol retires onto its frozen contract shape: `reserve`/`attest`/`renew`/`release` still
validate the closed `workflow_lease_reservation.v1` metadata and print their schemas, but report
the retirement — zero leases bound, no fleet root, nothing renewed or settled. The CLI's `except`
re-narrows to the surviving `WorkflowLeaseContractError` alone (not bare, not deleted), and the
acceptance grep is empty. Net: −63 lines (11 files, +278/−341) with the coupled surfaces moving
by construction, as in U1–U3.

## The emitted contract keeps its shape; the producers retire (KTD1)

Renaming the schemas or deleting the commands would have rippled into `execution_spec.py`'s
`lease` producer and the `/work` ritual — outside U4's measured scope. So: the receipt loses
`root_sha256` (no fleet root survives) and binds `lease_ids: []` beside the contract's identity
fields; the attestation reports attested width 0 and keeps `launch_authorized` as the retired
gate's verdict; renew/release validate the contract and return empty. Vocabulary slots survive
without producers — the U2 re-key precedent.

## The hooks degrade safely — measured before deletion (KTD2)

The blocking runtime question: between U4 and U5 the lease lifecycle hook still fires on every
Agent/Task spawn and HALTs PreToolUse on any reservation exception. Reading
`lease_broker.reserve_hook_agent` first answered it: when `active_batch_id` finds no live batch
it falls back to the pre-#356 per-spawn `acquire_agent` path — the "degrade" branch IS the
original admission design (#356 inserted the batch branch in front of it). No HALT regression.
LEARNINGS `{#the-batch-fallback-was-the-original-admission-path}`.

## The ritual keeps its calls; the prose moves under R11 (KTD3)

The plan assigned `skills/work/SKILL.md` to U3; U3 re-keyed the second-opinion section and left
the lease ritual. U4 changes what the ritual's commands DO, so R11 ("no window where the shipped
skill lies") pulled the prose into this PR: attest is a contract-shape gate only, no atomic
reservation, no hook batch discovery — hooks fall back to per-spawn admission until U5 removes
them. The calls stay for protocol continuity (attest still genuinely rejects a malformed
contract before launch). Revisit-when: U5 deletes the hook; the retired calls can leave the
ritual entirely then.

## Conformance pins flip to ABSENCE (KTD4)

The conformance suite's required-call pins (`selected.reserve_batch` / `renew_batch` /
`settle_batch` in the emitter) became absence pins so re-arming the emitter against any fleet
lease authority fails loudly; `EXPECTED_LEASE_CALLS` dropped the emitter entries; the two
`execution_spec.py` spawn-site rows carry `retired:broker-free-(#677/U4)` markers while the
claim cell keeps `lease_broker.claim_hook_agent` until U5.

## CI load surfaced two latent defects; both absorbed (KTD5)

Merge-time CI failed twice on two different tests, each in code this unit never touched:
(1) `audit_store._ensure_private_dir` walked `exists()`-then-`mkdir` — a TOCTOU — and with
admission fencing gone (Scope Decision row 1: concurrent dispatches both proceed) two dispatches
mirror to ONE shared store root; the loser died on `FileExistsError` under CI load. Fixed in
fleet-core production code (`mkdir(exist_ok=True)`, post-state lstat validation unchanged),
pinned by a two-process creation-race test, fleet-core bumped 0.23.0 → 0.23.1. (2) The hook
test's lease-expiry simulation wrote `renewed_monotonic_ns = 0`, which only expires once machine
uptime exceeds the 300s claim TTL — a fresh runner flaked it; the tampered registry now also
carries `ttl_seconds = 1`. LEARNINGS
`{#ci-load-surfaces-the-races-and-clock-assumptions-local-machines-hide}`.

## Files modified

| File | Change |
|---|---|
| `plugins/saga/scripts/workflow_emitter.py` | Broker deleted outright: no import, no `broker(environment)` constructions, no `reserve_batch`/`renew_batch` (the live KTD4 seam)/`settle_batch`, no authority-environment threading; commands validate the frozen contract and report retired results; `except` re-narrowed to `WorkflowLeaseContractError` alone |
| `tests/test_saga_workflow_emitter.py` | Rewritten — 7 tests (11 → 7): seven broker-lifecycle tests extinct with their mechanisms, four contract/shape pins kept, issue's two mandated pins added (emit completes with no batch lease; failing emit HALTs through the re-narrowed handler) plus CLI exit-path coverage |
| `plugins/fleet-core/scripts/fleet_commons/audit_store.py` | KTD5 absorption: `_ensure_private_dir` mkdir now `exist_ok=True` — concurrent dispatches both proceed and mirror to one shared root; post-state lstat validation unchanged |
| `tests/test_audit_store.py` | New two-process creation-race pin (`test_ensure_private_dir_is_process_safe_when_two_creators_race`) |
| `tests/test_saga_hooks.py` | Lease-expiry simulation made uptime-independent (`ttl_seconds = 1` in the tampered registry) |
| `tests/test_concurrency_conformance.py` | EXPECTED_ROWS re-keyed to `retired:broker-free-(#677/U4)` markers; EXPECTED_LEASE_CALLS dropped the emitter entries; required-call pin flipped to an absence pin; drift-test row string updated |
| `plugins/saga/references/concurrency-spawn-sites.md` | Two execution_spec rows re-keyed; #677/U4 re-key paragraph names the hook fallback (R11) |
| `plugins/saga/skills/work/SKILL.md` | Lease ritual prose re-keyed: contract-shape gate, retired reserve/attest/release/renew semantics, hook fallback until U5 (R11; plan assigned this file to U3, which left the ritual) |
| `docs/engineering-journal/DECISIONS.md` | New `## 2026-08-07` section: `{#u4-retires-the-workflow-emitter-onto-the-frozen-contract-681}` KTD1–KTD5 |
| `docs/engineering-journal/LEARNINGS.md` | `{#the-batch-fallback-was-the-original-admission-path}`, `{#ci-load-surfaces-the-races-and-clock-assumptions-local-machines-hide}` |
| Release surfaces | saga 0.128.0 → 0.129.0 and fleet-core 0.23.0 → 0.23.1 (plugin.json, CHANGELOGs, marketplace.json via `scripts/sync_marketplace.py`, version-pin tests) under the #429 diff guard |

## Deliberately not done

- **No schema renames, no command deletions.** The frozen contract shape and the CLI vocabulary
  survive; `execution_spec.py`'s `lease` producer and the ritual keep working against them.
- **No substitute renewal mechanism.** Plan KTD4: no batch lease exists to renew; renew validates
  and reports empty.
- **Ritual calls not removed.** They stay for protocol continuity until U5 deletes the hook
  (revisit-when named in KTD3).
- **`execution_spec.py` untouched.** No broker imports there (measured); its protocol comment
  stays accurate while the ritual keeps the calls.
- **No 3.0.0 breaking bump.** Remains U6's per the plan.

## Checks run

| Gate | Result |
|---|---|
| Full suite `uv run python -m pytest -q` | **5498 passed, 1 skipped, 0 failed** (branch-point baseline at 07c98ec7: 5501 — net −3: four retired broker-lifecycle tests, one added audit-store race pin) |
| Acceptance grep `lease_broker\|lease_authority\|fleet_leases\|saga_leases` on `workflow_emitter.py` | no matches |
| Sentinel `tests/test_agy_run_lease.py` | unmodified |
| `uv run ruff check . && uv run ruff format --check .` | clean (434 files) |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | clean (268 files) |
| `uv run bandit -ll` | 0 medium+ on changed files |
| `python3 scripts/lint_journal_order.py` | 0 violations |
| `python3 scripts/check_release_surface_parity.py` | all plugins in parity |
| `python3 tools/release_surface_diff_guard.py --base-ref 07c98ec7` | all changed plugins bumped |

## Collected-count delta

Branch-point baseline: 5502 collected (5501 passed + 1 skipped). U4 retires six broker-lifecycle
tests (admission, capacity, claim/recycle/renew, hook binding — broker concepts with no
broker-free successor), re-keys one (the replay/release test becomes the no-batch-lease pin),
keeps four contract/shape pins, and adds three: the two issue-mandated pins (CLI reserve exit
path, CLI HALT through the re-narrowed handler) plus the audit-store two-process creation-race
pin from the KTD5 absorption: 5499 collected (5498 passed + 1 skipped). The conformance suite's
parametrized pin kept its count (3 required-call cases → 3 absence cases).

## Surprise during execution

1. **The issue's test-file line was a survey artifact.** "Update `tests/test_workflow_emitter.py`"
   — that file tests `execution_spec.py` emission with ZERO broker references; the lease
   protocol's home was always `test_saga_workflow_emitter.py`. Named in KTD4.
2. **The degrade branch was the predecessor mechanism.** The batch fallback everyone assumed was
   defensive code was the pre-#356 admission path; deleting the batch concept resurrects it as
   the runtime behavior with zero hook changes. LEARNINGS entry.
3. **The plan's SKILL.md ownership missed the lease ritual.** U3 re-keyed the second-opinion
   section only; R11 pulled the ritual prose into U4 rather than leaving a lying window.
4. **ruff format wrapped the version pin** — the long inline comment forced a multiline assert;
   caught by the gate, not by eyeball.

## Next step

Campaign #677 continues with U5 (#682): delete `plugins/saga/hooks/lease_lifecycle_hook.py` (92
lines) and `plugins/saga/scripts/lease_broker.py` (574 lines) whole, unhook the manifest
registration in the same commit, and verify no `import lease_broker` remains in saga first.
KTD3's revisit-when fires with U5: the retired reserve/attest/release/renew calls can leave the
`/work` ritual entirely once the hook is gone.
