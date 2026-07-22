---
target: branch work/615-workflow-child-lease-binding (diff ee8a2b1a..f7d08aa1)
reviewed_revision: f7d08aa1
blocked: false
verdict: CLEAN
scope_check: CLEAN
linked_issue: infiquetra/infiquetra-claude-plugins#615
linked_plan: docs/plans/2026-07-22-issue-615-workflow-child-lease-binding-plan.md
work_sessions:
  - docs/work-sessions/2026-07-22-issue-615-workflow-child-lease-binding.md
date: 2026-07-22
mode: programmatic (driven by /work)
backend: inline (3 lens spawns + 3 Stage-B validators, all saga:readonly-verifier + worktree, opus)
---

# Code review — issue #615 workflow-child lease binding

**Verdict: CLEAN — not blocked.** No P0/P1/P2. Three P3 test-coverage advisories found by the
testing lens, each independently validated (confirmed, confidence 88) and **deferred** — all
three are missing regression pins on inspection-correct code, not live defects. REVIEWED_SHA
`f7d08aa1`, diff base `ee8a2b1a` (= origin/main). Staleness check at composition time:
`git rev-list f7d08aa1..HEAD --count` = 0.

## Scope

Five commits, 16 files, +541/−11: `15c15938` (U1 fleet-core broker: unstamped batch claim with
stamped-first ordering, child-terminal recycle for unstamped slots, `_renew_live_batch_siblings`
keep-alive, `_renew_batch_member` mutation-path renewal; 9 broker tests + e2e workflow-child
lifecycle test), `2026b45d` (U2 saga hooks `INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off`
kill-switch + 2 tests), `beeba844` (U4 release surfaces: fleet-core 0.19.0, saga 0.110.0,
marketplace, CHANGELOGs, drift pins, DECISIONS entry), `d7ae3efc` (ruff format fixup),
`f7d08aa1` (work-session doc). Excluded: the operator's uncommitted
`docs/outcomes/external-engine-offload/report.md` edit and untracked `docs/sdlc-issue-drafts/*`.

## Scope check — CLEAN

- **Intent**: complete the #356 driver protocol at the broker claim/terminal seam so
  workflow children bind attested-but-unstamped batch slots (plan R1–R8; D1 operator-pinned to
  resolution (i) mutation-path renewal), plus the emergency kill-switch and release surfaces.
- **Delivered**: exactly that. All 16 diff files trace to #615; no drift into #616's worktree
  write-fence or #617's registry schema territory (diff deliberately narrow to the
  claim/terminal seam). R9 live canary deferred post-merge by design — not faulted.

## Plan-completion audit (R1–R8, U1–U4)

All twelve items audited **DONE** by the testing/plan-audit lens; every path:line citation
re-verified at `f7d08aa1`.

| Req | Evidence |
| --- | --- |
| R1 unstamped bind | claim filter drops the stamped-only gate (`fleet_commons/lease_broker.py:~2631`); e2e `test_workflow_child_binds_without_pretool_stamp_and_waves_recycle` |
| R2 non-batch byte-identical | ordering-key head `batch is not None and lease.tool_use_id is None` is constant `False` for non-batch; `test_non_batch_claim_ordering_ignores_stamp_state` + non-batch renewal exclusion test |
| R3 stamped-first deterministic | `test_stamped_slot_is_preferred_and_unstamped_claims_activate_the_remainder` (discriminating: `prepare_batch_call` stamps the oldest slot) |
| R4 child-terminal recycle | `unstamped_batch_slot` condition in `record_child_terminal`; both halves pinned (unstamped single-signal, stamped dual-signal) |
| R5 keep-alive + mutation renewal | `_renew_live_batch_siblings` (claim/terminal, in-lock) + `_renew_batch_member` (`assert_write_target`); never-resurrect pinned twice |
| R6 capacity truth | capacity charged only at `reserve_batch` via `_admit_agent`; claim binds without admission; recycle restores claim TTL |
| R7 kill-switch fail-armed | exact-string `!= "off"` in both hooks; bypass + 5-value armed parametrization tests |
| R8/U4 release surfaces | fleet-core 0.19.0 + saga 0.110.0 across plugin.json ×2, marketplace ×2, CHANGELOGs, drift pins ×4, DECISIONS `{#workflow-child-lease-binding-615}`; parity clean |
| U3 verification-only | codex frozen-seam nil-impact + choreography no-edit recorded in the work-session doc |

## Lens results (3 lenses, opus, independent worktrees)

**Correctness/concurrency — zero findings.** Strict additivity proven (old filter vs new
sort-key head; both candidate set and order byte-identical for non-batch, stamped claims select
the same slot); recycle double-fire safe (`agent_id=None` after recycle, second terminal
returns `False`); re-stamp of a claimed slot unreachable (`prepare_batch_call` requires
`agent_id is None`); no nested-lock path for `_renew_batch_member` (only broker call site of
`assert_write_target` is the top-level CLI dispatch); capacity uncharged at claim by
construction; `settle_batch`/`record_parent_completed`/`sweep` interplay verified — no function
assumes a claimed batch slot has a `tool_use_id`. Full broker+hooks suite (101 tests) green in
the lens worktree.

**Security/fail-closed — zero findings.** Cross-session binding blocked (`session_id` filter at
claim; batch pinned to one session at reserve); the `agent_type="*"` widening is by-design and
confined by the per-child worktree fence in `assert_write_target`; renewal cannot be spoofed
(`_renew_batch_member` re-reads under lock, requires matching `agent_id`, bails on
expiry/rebind) nor outlive supersession (`verify_agent` precedes renewal; renewal never writes
resource current-state); kill-switch disarms only on the exact byte string `off` and prints a
loud per-event notice; every new renewal path fails closed through the mutation hook's `_halt`.
Noted residual (below threshold): sibling keep-alive can extend a wedged-but-live sibling's
lease, but that lease is bound to an agent identity no hook presents, so it confers no mutation
authority.

**Testing/built-vs-planned — three P3 findings (below), plus the audit table above.**

## Findings

| # | Sev | File | Issue | Conf | Validation | Route | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P3 | tests/test_saga_workflow_emitter.py:281 | e2e exercises `verify_hook_mutation` but never advances time to assert the renewal *effect* through the adapter seam; the effect is pinned only at broker level (direct `assert_write_target`). Adapter is a thin passthrough, so marginal value is low. | 88 | confirmed (validator: no time source in the test file; seam real via saga adapter :397 → broker :3054) | test_addition | DEFERRED |
| 2 | P3 | tests/test_fleet_lease_broker.py:1744 | No pin that keep-alive skips siblings of a *different* batch — all new tests use a single `batch_id`; removing the `lease.batch_id != batch_id` filter would pass the suite (no pre-existing two-live-batch renewal test exists). | 88 | confirmed (validator: enumerated all call sites + pre-existing batch tests; mutation would survive) | test_addition | DEFERRED |
| 3 | P3 | tests/test_saga_hooks.py:780 | Kill-switch armed-baseline for env-*absent* not explicitly parametrized (list covers `''` but `_environment` always sets the var). Absent-is-armed is implicitly pinned by 8+ pre-existing halt tests whose env lacks the key. | 88 | confirmed (validator: `_environment` inherits `os.environ`, sets key for every parametrized value incl. `''`) | test_addition | DEFERRED |

Suppressed below confidence 75: none. Over-budget validator drops: none (3 survivors, cap 15).
Deferral rationale: all three are additive regression pins on behavior already proven correct at
another layer; repairing pre-PR would invalidate REVIEWED_SHA and force a re-review cycle for
zero behavioral delta. Candidates for a follow-up or an operator-elected pre-PR fix.

## Coverage and residual risk

- Gates green at `f7d08aa1`: pytest 5364 passed / 1 skipped, `ruff check` + `ruff format
  --check` clean, mypy clean, bandit zero new findings (5 pre-existing severity-Low subprocess
  findings in the broker, identical at base), release-surface parity clean.
- Residual: R9 live acceptance (armed installed hooks + one-agent canary workflow) is
  post-merge + post-plugin-update, operator-gated; until it passes, the
  hook-neutralization ritual remains the documented workaround.
- Merge-time note: re-check sibling-PR version collisions on 0.110.0/0.19.0 before merge
  (#616 is dispatched and also touches `lease_broker.py`).

## External opinion

`external_opinion.state=recommended` — stage default is a second-opinion (codex, opus/high
band) on finding #2 (the highest-leverage pin); not dispatched in programmatic mode. Operator
may request it before merge.

Review complete.
