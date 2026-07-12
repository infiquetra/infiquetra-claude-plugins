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

## Next step

`/code-review` programmatic gate, then PR-ready boundary (draft PR #569 already open from the
front-loaded ceremony start).
