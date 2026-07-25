# Code review — issue #616 worktree write-fence scoping

**Verdict: clean** — zero P0/P1/P2; two confirmed P3 test-coverage findings, both repaired
in-branch before PR; one pre-existing P3 advisory deferred; scope check CLEAN.

## Review-result contract

- **Target:** branch `work/616-worktree-write-fence`, diff base `ab84003b` (= origin/main)
- **Reviewed revision (REVIEWED_SHA):** `c816aad5` (code commits `5d7f6988`/`1c8d7ec5`/`7ed3ccac`
  + docs `c816aad5`); repair commit `a0a2dc02` (test-only, delta-adjudicated below)
- **Mode:** programmatic report-only, caller `/work` Phase 5.1 (caller owns persistence — this
  artifact is that persistence)
- **Blocked:** no
- **Linked:** issue #616, saga `issue-616` (lifecycle `work`, destination `merge`), plan
  `docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md`, work-session
  `docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md`
- **External opinion:** none dispatched (programmatic mode never prompts; no `#N` pointed out)

## Review team (judgment-selected, all sandboxed saga:readonly-verifier + worktree)

| Lens | Model | Result |
|---|---|---|
| correctness + concurrency | opus | 0 surviving findings (1 suppressed at anchor 40); all six scrutiny targets verified clean with line-cited mechanism analysis; ran broker suite 75 passed |
| security / privilege boundary | opus | **0 findings** — widening exactly scoped; no self-spoof (claim path has no isolation parameter); unfenced path still authenticates (verify_agent + mutation check before fence-absent return); corrupt registry can only over-fence or fail loud; ran 114 tests green |
| testing adequacy | opus | 4 findings (3 survived the ≥75 gate); independently ran 125 tests green; every decision-matrix cell verified fail-on-regression |
| conventions / release surfaces | sonnet | 1 finding (validator-rejected); all release surfaces, drift pins, CHANGELOG claims, and journal anchors verified accurate; ruff/format/mypy clean |

## Built-vs-planned audit

Scope Check: **CLEAN**. Intent: scope the fleet-lease write-fence by reservation-declared
isolation (#616, KTD1-KTD6, operator-pinned D1 resolution (i)). Delivered: exactly that —
broker field + three-way claim fence + adapter forwarding + release surfaces + docs; no
unrelated files.

Plan completion: U1 **DONE** (diff + 8 tests + independent verifier execution), U2 **DONE**
(diff + seam tests + clean refute-3 panel 0/3), U3 **DONE** (verification-only; nil-impact +
hermetic R3 canary PASS recorded in the work-session doc), U4 **DONE** (0.20.0/0.111.0 +
marketplace + CHANGELOGs + drift pins + journal entries; parity clean). R1-R7 **DONE** via the
test matrix; R8 **DEFERRED by design** (post-merge operator-gated live canary — not faulted).

## Findings (stable numbering)

| # | Sev | File | Finding | Validator | Outcome |
|---|---|---|---|---|---|
| 1 | P3 | plugins/fleet-core/scripts/fleet_commons/lease_broker.py:919 | `from_dict` corrupt=True path for a present-but-invalid on-disk isolation value untested (RegistryCorruptError branch had no regression guard) | CONFIRMED | **REPAIRED** in `a0a2dc02`: `test_registry_with_invalid_isolation_value_raises_registry_corrupt` |
| 2 | P3 | plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2692 | Declared-worktree reservation claimed with no `worktree_root` yields an unfenced lease — unpinned edge | CONFIRMED but **pre-existing** (baseline had the identical fall-through with no isolation gate; adapter path cannot reach it — `_canonical_cwd` raises rather than returning None) | deferred advisory; candidate follow-up alongside the machinery defects |
| 3 | P3 | tests/test_fleet_lease_broker.py | No composition test: recycle a stamped slot → second `prepare_batch_call` with a different isolation → claim honors the NEW declaration (re-stamp at broker :2814) | CONFIRMED (exhaustive grep of all `prepare_batch_call` call sites; single-commit provenance proof) | **REPAIRED** in `a0a2dc02`: `test_recycled_slot_re_stamp_honors_new_isolation` |
| 4 | P3 | tests/test_saga_hooks.py:815 | Docstring sentence split across blank line inconsistent with repo style | **REJECTED** — style is consistent within the diff (4/4 new docstrings) and pre-exists in 3+ repo files | dropped |

Suppressed below the ≥75 confidence gate: 2 (replay-guard isolation omission P3@40 —
advisory-latent, adapter derives isolation deterministically per tool_use_id; worktree-value
round-trip assertion P3@50 — indirectly covered by fence assertions).

## Delta adjudication of repair commit `a0a2dc02`

Test-only additions to `tests/test_fleet_lease_broker.py` (61 insertions, zero production-code
changes); broker + adapter + emitter suites re-run at `a0a2dc02`: **127 passed** (125 + 2 new).
No new findings introduced; findings #1 and #3 resolved.

## Coverage and residual risk

- Gates at REVIEWED_SHA: pytest 5378 passed / 1 skipped (full battery), ruff check + format
  clean, mypy clean, release-surface parity clean, bandit delta zero vs base on both brokers.
- **Reviewer-environment instability (not a diff defect):** 3 of 8 sandboxed subagents had
  their fleet lease fail to bind or lapse mid-run ("expected exactly one fleet lease bound;
  found 0"), fencing their Bash; verification was completed via Read-tool fallback, retries,
  and the primary-checkout evidence. Same machinery family as the four workflow-pass faults
  recorded in the work-session doc — reinforces the queued follow-up defects.
- Residual: the pre-existing unfenced edge in finding #2 (unreachable via the shipped adapter);
  R8 live canary still owed post-merge (operator-gated, starts with the #642
  `FLEET_COMMONS_DEBUG=1` provenance check).

Review complete
