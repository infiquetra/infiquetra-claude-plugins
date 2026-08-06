---
title: Work session — U3 unwind dispatch and worktree routing off the lease broker (#680)
date: 2026-08-06
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/680
plan: docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md
doc_review: docs/reviews/doc-review-issue-677-2026-07-30.md
branch: feat/680-u3-unwind-dispatch-worktree-routing
commit: cc0db51e
final_commit: cc0db51e
pull_request: https://github.com/infiquetra/infiquetra-claude-plugins/pull/699
merge_commit: 19df7d99
saga: issue-680
orchestration: inline
---

# Work session — #680 U3 unwind dispatch and worktree routing off the lease broker

## What this changed, in one paragraph

U3 is the largest unit of the lease-broker retirement (#677) by call-site count — the
two domains where broker use was genuinely threaded rather than localized: engine
dispatch settlement and outcome worktree routing. Settlement fencing re-keys onto
self-authenticating **`saga.close-receipt.v1`** receipts: registered dispatch mints one
onto `provenance["dispatch_close"]`; the Team Execution claim and adjudication manifest
transitions chain from their predecessor by digest re-derivation; `satisfy_gate`
re-validates the terminal receipt beside the preserved byte CAS and strict audit mirror.
Identity becomes caller-asserted (bounded shape validation only). The one real loss —
cross-run worktree reclamation — becomes a report-only census plus a documented manual
operator path. Net: −1508 lines (37 files, +1589/−3097).

## Receipts prove themselves (KTD1)

`receipt_sha256` closes over every other field of the receipt; claim, adjudication, and
`satisfy_gate` validate by re-deriving the digest from the presented fields. No broker
fence head is consulted anywhere. The byte CAS and the strict audit mirror never needed
the broker and are preserved untouched. The lost fencing (a monotonic sequence a racing
second writer cannot re-present) is accepted per plan #677 Scope Decision row 1 and
pinned honestly rather than papered over.

## The race settles at the byte check (KTD2)

With admission fencing gone, two racing claims are BOTH admitted; the loser fails on the
post-write read-back — `canonical manifest write does not match expected output bytes`.
The two-process race pin (`test_team_execution_two_process_claim_race_both_proceed_and_one_state_persists`)
asserts exactly that: ok/error split, loser failing ONLY on the byte check. A re-claim
from identical inputs mints the IDENTICAL receipt — receipts are content-addressed, not
fencing-sequenced. LEARNINGS `{#post-write-readback-is-the-race-detector}`.

## Execution-stable resource identity (KTD3)

`_engine_resource_ref` hashes only `execution_id` — attempt is documentation, not
identity — so receipts share one `resource_ref` per execution and the chain stays
connected across re-claims. `session_id` survives everywhere it carried real weight
(arms the delegation tripwire, keys the integrity counter). `LeaseAdmission` is deleted
outright.

## Panels lose their fence, keep their session contract (KTD4)

Verify-panel member facts append directly post-validation; a second panel dispatch for
the same unit proceeds (pinned). The bounded session id remains required before any
preflight, dispatch, or fact write — the session contract is what replaced the lease.

## Three forced absorptions (DECISIONS `{#u3-absorbs-three-coupled-broker-consumers-680}`)

Per U1's KTD1 precedent, callers of deleted seams move in the same PR because a green
suite is unreachable otherwise:

1. **`outcome.py`** — the surviving broker surface: `production_worktree_processor` and
   the two CLI branches injecting `default_lease_authority()`.
2. **`second_opinion.py`** — the dispatch lease surface (`lease_admission_for_session`,
   the admission threading) re-keyed onto the trusted `session_id` alone.
3. **`outcome_dispatcher.py`** — the WHOLE broker surface. `DispatcherLeaseTransientError`
   is extinct; the transient-refusal category no longer exists, and `outcome.py`'s
   reconcile arm bare-raises on any `DispatcherError` — the loud pre-#627 abort posture
   (DECISIONS `{#u3-restores-loud-dispatcher-abort-680}`).

## The one real loss — cross-run worktree reclamation

`lease_authority.sweep(worktree_reaper=...)` was the only production reaper that crossed
run boundaries. It is replaced by the report-only **`reclaim_candidates(repo_root)`**
census (`--reclaim-list` CLI: `live` / `path-absent` / `unregistered`) and the documented
manual `git worktree remove --force` procedure in the new
`plugins/saga/references/worktree-reclamation.md` — including the R32 consequence of
removing a live sub-outcome's worktree (drives the rejected terminal). Nothing wires the
inventory to any tick; wiring a reaper would be a scope reversal. Revisit-when named in
DECISIONS `{#u3-makes-worktree-reclamation-an-operator-path-680}`.

## Files modified

| File | Change |
|---|---|
| `plugins/saga/scripts/engine_dispatch.py` | Settlement re-keyed: close-receipt minting on dispatch, claim/adjudication chain by digest re-derivation, `satisfy_gate` receipt re-validation beside preserved byte CAS + audit mirror; broker admission/fence plumbing deleted (−~600 lines net) |
| `plugins/saga/scripts/outcome_worktrees.py` | Broker routing removed; report-only `reclaim_candidates` census + `--reclaim-list` CLI added; `registered_entry_strict` prune preflight (corruption + outcome-mismatch refusals) preserved; docstrings point at the manual reclamation reference |
| `plugins/saga/scripts/outcome.py` | Absorption 1: `production_worktree_processor` and the two `default_lease_authority()` CLI injection branches removed; reconcile arm bare-raises on `DispatcherError` (loud abort restored) |
| `plugins/saga/scripts/outcome_dispatcher.py` | Absorption 3: whole broker surface removed — `default_lease_authority`, `DispatcherLeaseTransientError`, shim loads |
| `plugins/saga/scripts/second_opinion.py` | Absorption 2: dispatch lease surface re-keyed onto trusted `session_id` alone |
| `plugins/saga/scripts/outcome_decompose.py` | Broker threading removed from decompose dispatch |
| `plugins/saga/scripts/ship_teardown.py` | Note vocabulary re-keyed: "registered outcome worktree retained for canonical registry-owned reap: {exc}" with #677/U3 comment |
| `plugins/saga/references/worktree-reclamation.md` | NEW — the manual operator path: census interpretation, `git worktree remove --force` procedure, R32 consequence |
| `plugins/saga/references/engine-dispatch.md` | Rewritten for the receipt chain (R11) |
| `plugins/saga/references/evidence-write-sites.md` | Four rows re-keyed (R11) |
| `plugins/saga/references/concurrency-spawn-sites.md` | Broker-free rows carry `retired:broker-free-(#677/U3)` markers; pool column stays `agent|worktree` (R11) |
| `plugins/saga/skills/work/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md` | Second-opinion sections re-keyed to session-id-only dispatch |
| `plugins/team-execution/.../references/external-engine-workers.md` | §3/§5 rewritten to the receipt chain: `predecessor_close=evidence.provenance["dispatch_close"]`, `claim_result.close_receipt`, `manifest_close_receipt=adjudicated.close_receipt`, "A stale or tampered predecessor receipt fails digest re-derivation" — pinned by the manifest consumer matrix, which now also asserts the broker vocabulary is GONE from the contract |
| `tests/test_saga_engine_dispatch.py` | Rewritten — 138 tests: `_registered_kwargs` helper; `_PausingStore` delegating proxy for the frozen Store TOCTOU pin; forged/tampered/drifted receipts at the gate; concurrent-dispatch both-proceed (identical receipts by content-addressing) |
| `tests/test_outcome_worktrees.py` | Rewritten — 36 tests: reclaim census/CLI, `test_manual_reclamation_procedure_end_to_end` with real git (common-dir anchored `common = raw if raw.is_absolute() else (repo / raw).resolve()`) |
| `tests/test_outcome_dispatcher.py` | Both-proceed race pins at the dispatcher level |
| `tests/test_outcome_command.py` | Broker injection branches retired from the CLI surface |
| `tests/test_chaperone_liveness.py` | `_canonical_gate_binding` mints via `D._mint_close_receipt`, returns (close, audit_store_root) |
| `tests/test_manifest_consumer_matrix.py` | Banned-vocabulary assertions (broker terms gone) + required receipt-chain string pins |
| `tests/test_delegation_tripwire.py` | `_dispatch_close` helper; session_id-alone dispatch arms the tripwire |
| `tests/test_concurrency_conformance.py` | EXPECTED_ROWS == md table rows; LEASE_CALLS re-keyed to `retired:broker-free-(#677/U3)` |
| `tests/test_ship_teardown_reconciliation.py` | `_registered_outcome_worktree` helper; vestigial-lease test asserts `result["reaped_worktree"] is True` (registry reap, not broker) |
| `tests/test_review_second_opinion.py`, `tests/test_work_second_opinion.py` | Session-id-only dispatch re-key |
| `tests/test_outcome_graph_edit.py` | Prune fixture gained `outcome_id="o"` (production entry shape for strict preflight) |
| `tests/lifecycle_harness.py` | `reap_worktree` lost its `at=` kwarg — dropped |
| `tests/test_saga_plugin.py`, `tests/test_team_execution_plugin.py` | Version pins 0.128.0 / 2.25.0 |
| Release surfaces | saga 0.127.0 → 0.128.0, team-execution 2.24.0 → 2.25.0 (plugin.json, CHANGELOGs, marketplace.json via `scripts/sync_marketplace.py`, version-pin tests) under the #429 diff guard |
| `docs/engineering-journal/DECISIONS.md` | New `## 2026-08-06` section, four entries (anchors above) |
| `docs/engineering-journal/LEARNINGS.md` | `{#cwd-relative-git-common-dir-litters-repo}`, `{#post-write-readback-is-the-race-detector}` |
| `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` | Dated re-note blocks; U4 corrected to ONE file; "U1–U4 run in parallel" retired as a survey artifact |

## Deliberately not done

- **No fencing replacement.** The lost monotonic sequence (Scope Decision row 1) is
  pinned as accepted, not rebuilt by another mechanism. The byte read-back is the only
  race settlement.
- **No reaper wiring.** The reclaim census is report-only; connecting it to any tick
  would be a scope reversal of the campaign's decision to make reclamation an operator
  path.
- **No registry mutation in reclamation.** The census reports; removal is manual
  `git worktree remove` by an operator who has read the reference doc.
- **No 3.0.0 breaking bump.** Remains U6's per the plan.
- **U4 not pulled.** Re-noted (third correction) to ONE file — `workflow_emitter.py` —
  in this PR; the pull is a separate session per U1's KTD4 discipline.

## Checks run

| Gate | Result |
|---|---|
| Full suite `uv run python -m pytest -q` | **5501 passed, 1 skipped, 0 failed** (branch-point baseline at 10839b05: 5527 — net −26 retired broker-era tests) |
| Acceptance grep `lease_broker\|lease_authority\|fleet_leases\|saga_leases` on the six production files | no matches |
| Sentinel `tests/test_agy_run_lease.py` | unmodified |
| `uv run ruff check . && uv run ruff format --check .` | clean (434 files) |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | clean (268 files) |
| `uv run bandit -ll` | no new findings on changed files |
| `python3 scripts/lint_journal_order.py` | 0 violations |
| `python3 scripts/check_release_surface_parity.py` | all plugins in parity |
| `python3 tools/release_surface_diff_guard.py --base-ref 10839b05` | all changed plugins bumped |
| CI (PR #699, final round) | all checks green: Tests, Lint, Type Check, Validate Plugins, Security Scan, Release Surface Parity, Delegation proof — version-bump gate, Delegation integrity — fleet sweep |

## Collected-count delta

Branch-point baseline: 5527 passed, 1 skipped (post-U2 at 10839b05). U3 retires 26
net broker-era tests — the admission/fencing suites shrank or vanished with their
mechanisms (test_saga_engine_dispatch and test_outcome_worktrees rewritten smaller and
receipt-shaped; dispatcher transient-refusal category extinct) — while adding the
receipt-chain, both-proceed race, strict-preflight, and manual-reclamation pins: 5502
collected (5501 passed + 1 skipped).

## Surprise during execution

1. **The post-write byte read-back doubles as the race detector.** Empirical: with
   admission fencing gone, the loser of a two-process claim race fails ONLY on the
   canonical-manifest byte check. The existing CAS machinery was already the settlement
   authority; fencing had only been admission control. LEARNINGS entry.
2. **Content-addressed receipts mint identical on re-claim.** A test asserting racing
   receipts differ was wrong by design — identical inputs give identical digests. The
   equality is the pin.
3. **The frozen `Store` defeated naive TOCTOU injection** — a delegating
   `_PausingStore` proxy (pausing the second `manifest_path` call: capture vs CAS
   re-read) was needed.
4. **CWD-relative `git rev-parse --git-common-dir` output** in the e2e reclamation test
   littered the real repo root with `.git/saga-outcomes/o-store/` — anchored with an
   explicit resolve. LEARNINGS `{#cwd-relative-git-common-dir-litters-repo}`.
5. **GitHub-side CI flake at merge time.** Three rerun rounds: checks failed on the
   action-download step (`Service Unavailable`) or were cancelled while queued for
   runner capacity — every failure was infra, none ran project code. Fleet-sweep and
   bandit were re-verified locally while waiting.

## Next step

Campaign #677 continues: U4 (#681) is now precisely ONE file — `workflow_emitter.py`
(re-note discipline already satisfied by the U3 PR). U5 (#682) after; U6 (#683) owns
the eviction-gate story and the 3.0.0 breaking bump; U7 (#684) re-notes R8.
