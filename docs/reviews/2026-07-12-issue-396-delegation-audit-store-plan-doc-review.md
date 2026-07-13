# Doc review — delegation audit store plan (#396)

Verdict: **READY** — three findings surfaced by direct verification; all three were evidence-backed
and fixed in place; nothing remains open.

## Review-result contract

- **Target:** `docs/plans/2026-07-12-issue-396-delegation-audit-store-plan.md`
- **Reviewed revision:** working tree on branch `worktree-agent-a93ce40abfa071890` (base commit
  `8007e07`, the merged evidence-ledger PR #567 tip on `main`; plan file untracked at review time)
- **Blocked status:** NOT blocked — zero unresolved P0/P1
- **Linked issue:** infiquetra/infiquetra-claude-plugins#396 (leaf `sub-396` of outcome
  `evidence-integrity`; depends on #398/PR #567, merged, and #383 `bridge_receipt.v1`, closed)
- **Linked plan saga:** `issue-396` (git-ignored, machine-local)
- **Review artifact:** `docs/reviews/2026-07-12-issue-396-delegation-audit-store-plan-doc-review.md`
  (this file)
- **Rubric engine:** not run — the rubric phases are `idea`/`issue`/`spec`; no plan-phase rubric
  exists, so the readiness-skeptic pass is the operative review for a `docs/plans/` artifact (same
  precedent as the sibling #398 doc-review).
- **External-engine offer:** not invoked — no operator ask for a cross-engine pass on this artifact;
  the opt-in panel is reserved for a high-stakes artifact the operator explicitly requests.

## Findings and dispositions

All three findings were fixed in place per the operator's instruction ("fix all issues found"); every
fix is backed by direct repository verification — none invents a decision.

| ID | Pri | Finding | Status |
|---|---|---|---|
| D1 | P2 | U7's version-bump targets applied one uniform rule (bump the middle/minor digit for every plugin) without checking each plugin's own observed CHANGELOG cadence. Verified against actual history: fleet-core patch-bumps for "Added: new module" entries (0.8.2, 0.8.3), agy patch-bumps a non-breaking "Added" change (0.2.0→0.2.1) and reserves minor bumps for explicitly BREAKING changes, and team-execution patch-bumps doc-only "Changed" entries (2.13.1, 2.14.1–4) versus minor-bumping when a new script ships alongside docs (2.14.0) | FIXED — U7 now targets fleet-core 0.8.4→0.8.5, agy 0.2.1→0.2.2, team-execution 2.14.4→2.14.5 (all patch, matched to precedent); saga 0.81.0→0.82.0 (minor) confirmed correct against the immediately-preceding evidence-ledger bump |
| D2 | P1 | U7 described release-surface verification as "covered by existing drift-guard tests" without naming that three of those tests hardcode the *current* version literal verbatim and will fail — not just flag a mismatch — the moment `plugin.json` is bumped unless edited in the same unit. Verified directly: `tests/test_agy_plugin.py:38` (`assert plugin_json["version"] == "0.2.1"`), and equivalent hardcoded literals in `tests/test_saga_plugin.py` and `tests/test_team_execution_plugin.py` (confirmed via `grep`, not assumed) | FIXED — U7's Files list now names all three test files and the exact literal each hardcodes; Test expectation reframed as "must edit, not merely covered." Also verified no `test_fleet_core_plugin.py` exists, so the fleet-core bump has no hardcoded-literal counterpart to update |
| D3 | P3 | No residual-risk note on the audit store's content-retention implication: `result.json` and `.delegation-drafts/*/raw.diff` mirror whatever an engine actually returned, now retained indefinitely on the operator's machine rather than briefly inside a disposable bundle — worth naming even though `bridge_receipt.v1` itself carries no secrets by contract and no new trust boundary is crossed | FIXED — added to the retention/pruning deferred-work bullet in Scope Boundaries: same machine, same operator, no new exposure surface, but the *lifetime* of already-existing content is extended and a future retention-policy follow-up should weigh it |

## Evidence verified during review

- Every `-k` test-name filter in the issue's four acceptance-criteria check commands maps to an exact
  test name the plan places in the exact file the issue's own check command names
  (`audit_store_survives_bundle_deletion` → `tests/test_agy_delegate_contract.py`;
  `flags_forced_fallback_only` and `draft_snapshot_write_once_guard` → `tests/test_delegation_audit.py`;
  `draft_snapshot_matches_fix_delta` → `tests/test_team_execution_chaperone.py`, confirmed absent
  today via `find`).
- Confirmed both target test files (`tests/test_delegation_audit.py`,
  `tests/test_agy_delegate_contract.py`) already exist with none of the four DoD-named test functions
  present yet (`grep -n "^def test_"` on both) — the plan extends, it does not invent duplicate
  coverage.
- Confirmed the exact receipt/run_id identity chain the mirror design depends on:
  `create_supervised_bundle`'s `resolved_run_id` → `_result_payload(run_id=resolved_run_id)` →
  `_supervised_receipt(run_id=run_id)` → `bridge_receipt.emit_receipt(run_id=run_id)` →
  `receipt["run_id"] = run_id` (`agy_delegate.py:1394-1504`) — the same value flows through end to
  end, so keying the durable mirror by that one `run_id` is sound, not an assumption.
- Confirmed `AdvisoryEvidence.runner_receipt: dict[str, Any] | None` (`engine_dispatch.py:75`) and
  `pm.Manifest`'s fields carry only a derived `bridge_run_key: str`, never the raw receipt
  (`provenance_manifest.py:429-465`) — so U4's plan to mirror the raw receipt *separately* from the
  manifest (not assume the manifest already carries it) is a verified necessity, not redundant.
- Confirmed the exact subprocess.run call-site counts KTD6 depends on, by direct script count (not
  estimation): `tests/test_agy_delegate_contract.py` — 3 blocks referencing `WRAPPER`;
  `tests/test_agy_run_lease.py` and `tests/test_agy_apply_policy.py` — 2 each (a shared `_run_wrapper`
  helper plus one direct call in each file); none of the three files pass `env=` today (`grep -n
  "env="` returned nothing in all three) — the home-directory-pollution risk is real, not
  hypothetical.
- Confirmed `tests/conftest.py`'s only autouse fixture (`_no_live_gh`) scopes to
  `{"test_mission_control", "test_outcome_board_sync", "test_ship_ceremony"}` only — it does not
  already guard the agy test modules, so KTD6's per-call-site fix is genuinely needed, not duplicate
  work.
- Confirmed team-execution has no executable chaperone script (`find plugins/team-execution -iname
  "*.py"` → `artifact_pointer.py`, `consensus_advisory.py` only) — U6 correctly targets prose
  reference docs plus a standalone unit test, not a nonexistent `chaperone.py`.
- Confirmed issue #383 (`bridge_receipt.v1`) is CLOSED and issue #398 merged as PR #567, both already
  landed — the plan's stated dependencies are satisfied, not aspirational.
- Confirmed the sibling-precedent claim: `docs/plans/2026-07-12-evidence-ledger-plan.md` "Execution
  prerequisites" independently chose inline for a 5-unit plan crossing the same `phase_count >= 4`
  mechanical threshold — the inline-override rationale in this plan is not a one-off deviation.

## Residual risk

- The `reconcile_store` no-op classification rule (claimed-real AND NOT observed-real) is a
  reviewer-authored decision rule consistent with the issue's wording, not an issue-stated algorithm
  verbatim — flag at implementation/code-review if a subtler disposition (e.g. `substituted-engine`)
  needs its own reconciliation branch rather than folding into the same binary flag.
- Rubric-engine coverage does not include plan-phase artifacts; this review's rigor rests on the
  readiness-skeptic pass alone, same limitation the sibling #398 review recorded.
