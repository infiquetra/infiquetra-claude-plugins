---
title: Work session — U1 unwind lease settlement and successor handoff in outcome_compat (#678)
date: 2026-08-05
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/678
plan: docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md
doc_review: docs/reviews/doc-review-issue-677-2026-07-30.md
branch: feat/678-u1-unwind-lease-settlement
commit: b727fa5c
final_commit: 42080178
pull_request: https://github.com/infiquetra/infiquetra-claude-plugins/pull/697
merge_commit: af8cb644
saga: issue-678
orchestration: inline
---

# Work session — #678 U1 unwind lease settlement and successor handoff

## What this changed, in one paragraph

The cross-runtime handoff protocol in `plugins/saga/scripts/outcome_compat.py` recorded its offers
inside the fleet lease broker's settlement close (prepare → protected writer → canonical close
receipt) and completed acceptance by acquiring a successor lease through a close-receipt CAS. Unit
U1 of the lease-broker retirement (#677) removes all six broker call sites — `verify`,
`prepare_agent_settlement`, `commit_agent_settlement`, `inspect_resource_head`,
`acquire_successor`, `verify` — and lets the protocol record outcomes directly: the offer lands via
the store's write-once path, and the write-once intent/commit pair is now the whole acceptance
transition. Issuer identity becomes caller-asserted (the plan's Option C accepted loss) but stays
REQUIRED — an anonymous offer still HALTs.

## The scope decision: absorbing outcome.py's handoff/attach call sites

The shaped unit's constraints proved inconsistent before the first edit: acceptance criteria demand
a green full suite and no pass-through wrappers, the non-goal forbids touching `outcome.py` (U4's
file), and `outcome.py`'s `handoff`/`attach` CLI branches are the ONLY callers of the unwound
functions — passing `broker=`/`lease=`/`admission=` in and reading `accepted["lease"].lease_id`
out. No design satisfies all three. The operator chose to break the non-goal, minimally: U1 updates
exactly the handoff/attach surface of `outcome.py` (signatures, CLI branches, the callerless
`_cli_broker`/`_cli_broker_error`/`_cli_admission` helpers, the broker-error `except` arm) and
leaves the file's other broker uses (the prune path) for U3/U4. Full reasoning: DECISIONS
`{#u1-absorbs-outcome-handoff-callers-678}`, LEARNINGS `{#file-disjoint-units-must-be-api-disjoint}`.

Consequence for the campaign: U1 and U4 (#681) are no longer file-disjoint; U4's `outcome.py` row
shrinks to the prune-path `default_lease_authority()` threading and its issue needs re-noting before
it is pulled.

## Files modified

| File | Change |
|---|---|
| `plugins/saga/scripts/outcome_compat.py` | Six broker call sites removed; `offer_handoff` takes `issuer_owner_id` (caller-asserted, required); `accept_handoff` loses `broker`/`admission`, returns `{"offer","intent","commit"}`; deleted `_acquire_successor_or_resume`, `_broker_module`, `_lease_broker_mod`, `outcome_dispatch_resource`, `_HANDOFF_PRODUCER`; module docstring updated |
| `plugins/saga/scripts/outcome.py` | Absorbed: `attached_advance`/`attended_handoff` signatures, handoff/attach CLI branches, deleted `_cli_broker`/`_cli_broker_error`/`_cli_admission` + broker-error `except`; CLI admission flags stay accepted-unused for cross-runtime compat (commented) |
| `tests/test_saga_outcome_compat.py` | NEW — the unit's three required scenarios plus module-surface, resume, and guard tests (9 tests) |
| `tests/test_outcome_cross_runtime_contract.py` | Rewrote `TestProtectedHandoff` + `TestAttachedAdvance` broker-free; deleted four lease-only tests (unclosed-source-lease, released-issuer, close-receipt, broker-rejection CLI); race test re-pins the write-once binding |
| `tests/test_cross_runtime_acceptance.py` | Harness fixture repointed from the deleted `handoff-superseded` receipt to the live `handoff-expired` one |
| `plugins/saga/references/outcome-cross-runtime.md` | Handoff-lifecycle + recovery-guidance sections rewritten for the write-once protocol (R11: docs move with the code) |
| `plugins/saga/skills/outcome/SKILL.md` | `handoff`/`attach` verb rows updated (R11) |
| `docs/engineering-journal/DECISIONS.md` | `{#u1-absorbs-outcome-handoff-callers-678}` |
| `docs/engineering-journal/LEARNINGS.md` | `{#file-disjoint-units-must-be-api-disjoint}` + `{#shared-sys-modules-key-test-collision}` (the full-suite-only test collision the new test file's module-key load caused and fixed) |
| `docs/engineering-journal/QUEUED.md` | `{#handoff-negotiation-vocabulary-escapee}` |
| Release surfaces (second commit) | `plugins/saga/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (regenerated) + `plugins/saga/CHANGELOG.md` + the version-pin test: saga 0.125.0 → 0.126.0 under the #429 diff guard (KTD6) |

## Deliberately not done

- ~~**No plugin version bump**~~ — **OVERTURNED by CI**: the #429 diff-aware bump guard fails any
  PR that changes plugin behavior without moving that plugin's release surface in the same diff,
  so the unit's "no bump until U7" non-goal contradicted the standing repo rule. saga bumped
  0.125.0 → 0.126.0 in this PR (DECISIONS KTD6); U7's R8 table needs re-noting.
- **`REQUIRED_CAPABILITIES`/`AUTHORITY` still name `fleet-broker-fencing`/`fleet-broker`** — the
  discovery-envelope negotiation vocabulary the codex port consumes verbatim. Changing it is a
  cross-runtime decision, queued as `{#handoff-negotiation-vocabulary-escapee}` for U7-or-follow-up.
- **The other broker uses in `outcome.py`** (prune path `default_lease_authority()`, the dispatcher
  lease comments) — U3/U4 scope, untouched.
- **No schema-name bump** for the offer/intent/commit records: readers consume only fields they know
  (old records with lease fields load cleanly under the new accept; in-flight handoffs across the
  upgrade are operator-managed, per Option C).

## Checks run

| Gate | Result |
|---|---|
| `uv run pytest tests/test_saga_outcome_compat.py tests/test_outcome_cross_runtime_contract.py tests/test_outcome_command.py tests/test_cross_runtime_acceptance.py tests/test_fleet_doctor.py` | 120 + 58 + 158 + outcome cluster 81, all pass |
| Full suite `uv run python -m pytest -q` | **5584 passed, 1 skipped, 0 failed** (5585 collected; baseline pre-U1: 5580 — 5579 passed + 1 skipped at the #696 merge state) |
| `uv run ruff check . && uv run ruff format --check .` | clean (434 files) |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | clean (268 files) |
| `uv run bandit` (CI-style `-ll`) | 0 medium+ on changed files (one pre-existing LOW B404 subprocess-import note) |
| `python3 scripts/lint_journal_order.py` | 0 violations |
| `python3 scripts/check_release_surface_parity.py` | all plugins in parity |
| Acceptance grep `lease_broker\|lease_authority\|fleet_leases` on `outcome_compat.py` | no matches |
| Sentinel `tests/test_agy_run_lease.py` | unmodified (`git diff --exit-code`), 8 passed |

## Collected-count delta

Pre-U1 baseline: 5580 collected (5579 passed + 1 skipped). U1 adds `test_saga_outcome_compat.py`
(+9), removes four lease-only contract tests (−4): net +5 → 5585 expected.

## Surprise during execution

The first two full-suite runs failed exactly one test — the contract file's frontier-change halt —
only in the full-suite order. Root cause: the new test file loaded `outcome_compat.py` under the
same `sys.modules` key as the contract file, so the last-collected load won the key and
`outcome.py`'s lazy `import outcome_compat` raised a foreign `CompatibilityHaltError` class past
the contract test's `pytest.raises`. Fixed by loading under a distinct key
(`_test_outcome_compat_u1`); the deleted `_load_broker_module`'s old comment had documented exactly
this hazard. LEARNINGS `{#shared-sys-modules-key-test-collision}`.

## Next step

Merge, then pull U2 (#679) or U3 (#680) — both remain file-disjoint with U1's landed state. Re-note
U4 (#681) first: its `outcome.py` row shrank to the prune-path sites.
