# Work session — durable delegation audit store (#396)

## Summary

Implemented all 8 units of `docs/plans/2026-07-12-issue-396-delegation-audit-store-plan.md`:

- **U1** — `plugins/fleet-core/scripts/fleet_commons/audit_store.py` (new): the durable
  delegation audit store (`~/.claude/delegation-audit` by default), mirroring receipts, agy result
  snapshots, and provenance manifests, plus a write-once pre-fix draft snapshot primitive.
- **U2** — `plugins/fleet-core/scripts/fleet_commons/delegation_audit.py` extended with
  `reconcile_store(...)`, flagging exactly the delegations whose disposition claims real execution
  but carry no schema-valid receipt as no-ops.
- **U3** — `plugins/agy/scripts/agy_delegate.py`'s `--audit-store` CLI option + bundle mirroring at
  every return point of `create_validation_bundle`/`create_supervised_bundle`; isolated all 7
  existing subprocess-driven CLI test call sites.
- **U4** — `plugins/saga/scripts/engine_dispatch.py`'s `record_dispatch_manifest`/
  `adjudicate_manifest` mirror the manifest and raw receipt to the durable store.
- **U5** — `plugins/saga/scripts/delegation_audit_query.py` (new CLI) +
  `plugins/saga/skills/delegation-audit/SKILL.md` (new skill) — the `/delegation-audit`
  reconciliation surface.
- **U6** — `external-engine-workers.md` §5 step 1 documents the write-once draft-snapshot hook;
  `worker-manifest.md` cross-references it.
- **U7** — release surfaces: fleet-core 0.8.4→0.8.5, agy 0.2.1→0.2.2, saga 0.81.0→0.82.0,
  team-execution 2.14.4→2.14.5; `marketplace.json` regenerated; three hardcoded-literal
  drift-guard tests updated.
- **U8** — `docs/engineering-journal/DECISIONS.md` (recorded at plan time, commit `786e9d5`) and
  `docs/engineering-journal/LEARNINGS.md` (this session — the home-directory-pollution risk).

## Key decisions (see the plan's KTD1-9 for full rationale)

- Shared primitives live in fleet-core (`audit_store.py`), not saga — agy/saga/team-execution all
  need install-boundary-safe access, mirroring `bridge_receipt.py`'s own precedent.
- Machine-local, uncommitted store root — the deliberate opposite of `evidence_ledger.py`'s
  committed-per-saga home (different durability requirement: same-machine worktree-teardown
  survival, not cross-machine custody).
- Default-on behavior lives at the outermost entry point only (agy's CLI `main()`; the documented
  chaperone call site for `engine_dispatch.py`, which has no CLI) — every underlying function
  defaults `audit_store_root` to `None` (skip), so direct unit-test callers never touch a real home
  directory.
- Backend: inline, overriding the mechanical `recommend_execution_backend()` recommendation
  (team-execution, on file/phase-count volume signals alone, no governance signal present) —
  matches the issue's own recommended profile and sibling #398's identical override in this outcome.

## Files modified

23 files across 5 commits (see `git log --oneline 786e9d5..4877e91`):
`plugins/fleet-core/scripts/fleet_commons/{audit_store.py (new), delegation_audit.py}`,
`plugins/agy/scripts/agy_delegate.py`, `plugins/saga/scripts/{engine_dispatch.py,
delegation_audit_query.py (new)}`, `plugins/saga/skills/delegation-audit/SKILL.md` (new),
`plugins/team-execution/skills/team-execution/references/{external-engine-workers.md,
worker-manifest.md}`, 6 test files (3 new: `test_audit_store.py`,
`test_delegation_audit_query.py`, `test_team_execution_chaperone.py`; 3 extended), 4×`plugin.json`,
`marketplace.json`, 4×`CHANGELOG.md`, 3 drift-guard test literals, `LEARNINGS.md`.

## Checks run

- `pytest` (via `.venv/bin/python3 -m pytest`, uv-synced with the `dev` extra): 3374 passed, 1
  skipped, full repo suite, twice (before and after the release-surface commit) — zero regressions.
- `ruff check .`: clean. `ruff format --check .`: clean (two files auto-formatted mid-session).
- `mypy plugins/ scripts/ tests/ --ignore-missing-imports`: clean, 193 source files.
- `bandit -r plugins/`: only pre-existing findings in files this leaf touched but did not author
  (verified each cited line predates this change via `git show HEAD~1:<file>` / `git log -L`); zero
  new findings introduced.
- Confirmed zero home-directory pollution after every test run (`ls ~/.claude/delegation-audit`)
  once the KTD6 isolation fix landed; confirmed it WAS real before the fix (two stray run
  directories found and cleaned up during development).

## Code review (programmatic gate)

Ran the 4-lens `/code-review` (correctness, security, testing+conventions, built-vs-planned) as
`saga:readonly-verifier` + `isolation: "worktree"` subagents against `0e4085a` (reviewed SHA).

**Verdict: CLEAN — 0 P0, 0 P1.** Scope check clean; 12/14 plan items DONE with direct evidence,
2 correctly CHANGED (write-once draft snapshot is a documentation-only chaperone hook by design —
no executable `chaperone.py` exists in this repo). 3 findings, all fixed in commit `557604b`:

- **P2 (security)** — `audit_store.py`'s mirrored writes (receipts, agy result payloads, raw
  pre-fix draft snapshots) landed at the process umask's default mode instead of the `0600`
  `manifest_store.py` already uses for the identical `manifest.json` content this store also
  mirrors. Fixed with `_write_temp_0600` (mirrors `manifest_store._atomic_write_manifest`'s
  `os.fchmod(fd, 0o600)`); covered by `test_mirrored_files_are_not_world_or_group_readable`.
- **P3 (testing)** — `_read_json`'s valid-JSON-non-dict path untested. Fixed with
  `test_resolve_receipt_valid_json_non_dict_returns_none`.
- **P3 (testing)** — `delegation_audit_query.py`'s `--run-id` naming an absent run untested. Fixed
  with `test_cli_run_id_naming_absent_run_degrades_to_unflagged_entry`.

Correctness lens raised a non-blocking aside (4 mypy errors in `agy_delegate.py` when checked as a
standalone file) that was verified against the actual CI gate command
(`mypy plugins/ scripts/ tests/ --ignore-missing-imports`, clean at 193 files) and root-caused to
`pyproject.toml`'s pre-existing `[tool.mypy] exclude = ["plugins/.*/scripts/"]` policy, which
excludes recursively-discovered files under any `plugins/*/scripts/` directory but not
explicitly-named single-file arguments — a repo-wide, pre-existing discrepancy, not a regression.

Full review artifact: `/tmp/code-review-396.md` (not committed — programmatic-mode persistence is
optional per `/code-review`'s Phase 5.3; this section is the durable record).

## Post-review release-surface fix (commit `52df4af`)

The pre-push gate's marketplace validator (not run at commit time, only at push time) caught 3
schema violations U7's version-bump commit introduced: fleet-core's and team-execution's
`description` fields exceeded the marketplace schema's 200-character limit, and saga's `keywords`
array grew to 11 items against a 10-item cap. Fixed by trimming description wording (no
capability dropped) and declining to add the new `delegation-audit` keyword to saga's already-full
list (the description text already names the reconciliation capability) — minimal-blast-radius
choice over displacing one of the 10 existing keywords. Regenerated `marketplace.json` via
`sync_marketplace.py`; re-ran the full gate (`ruff format --check .`, `ruff check .`, `mypy
plugins/ scripts/ tests/ --ignore-missing-imports`, `marketplace/validator/validate.py`, full
`pytest`) — all green (3377 passed, 1 skipped) — then pushed clean.

## Next step

PR-ready boundary reached (draft PR #569, front-loaded ceremony start). Per the leaf's hard
boundary: draft PR stays draft, no review requested, no merge, no branch deletion.
