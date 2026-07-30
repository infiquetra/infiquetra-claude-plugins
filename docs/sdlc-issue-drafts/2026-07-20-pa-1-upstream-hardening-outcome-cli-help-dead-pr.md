---
title: PA-1 upstream hardening: outcome CLI help/dead-print + handoff-store and audit-store permissions
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
risk: low
labels: defect, hermes-task, needs-plan
handoff_maturity: plan-ready
---

# PA-1 upstream hardening: outcome CLI help/dead-print + handoff-store and audit-store permissions

### Objective

Pre-acceptance production unit PA-1 of the cross-runtime-acceptance plan
(`docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`, section "Pre-acceptance
production units"), discharging the upstream-first routings from the codex #34 code-review and QA
gates before the acceptance harness pins its inputs (plan KTD7). Supports acceptance leaf #605 /
objective #579 but is a standalone production PR, not part of the acceptance PR (plan KTD4).

Four fixes at baseline `cf15a09f`:

1. **Stale `export`/`import` help strings** (`plugins/saga/scripts/outcome.py:2281/:2284`): still
   describe the retired `outcome-bundle/1` flow; reword to live semantics (`export` is a
   deprecated read-only alias of `discover`; `import` always refuses with migration guidance).
2. **Unreachable success-print in the import arm** (`outcome.py:2624-2627`): `import_bundle`
   unconditionally raises; remove the dead success path and give the arm the same
   `CompatibilityHaltError -> refusal-receipt JSON + exit 3` shape as the export arm.
3. **Handoff-store directory created at default umask** (`outcome_compat.py` `_write_once`, line
   1135): create missing directories `0o700`; if the handoffs directory already exists, require
   directory, non-symlink, euid-owned, mode exactly `0o700`, refusing otherwise with a typed
   error (the `audit_store._ensure_private_dir` predicate). Sealed records stay `0o600`.
4. **`fleet_commons/audit_store.py` ancestor hardening**: for each path component strictly below
   the user's home (home excluded; paths outside home exempt — lexical scope test on the expanded
   absolute path), `lstat` without resolving; refuse any symlinked component and any existing
   world-writable (`mode & 0o002`) directory with the typed `AuditStoreError`. Scoped below home
   so temp-dir test roots stay valid.

### Intent

Ship the three production-change dispositions deferred out of codex #34 (two routed
upstream-first, one owned by the cross-runtime-acceptance leaf) plus the audit-store ancestor gap
in the upstream Claude repo first, so the acceptance harness pins final released behavior and
codex PA-2 re-ports from a merged SHA instead of patching codex-only. Risk: low — narrow,
enumerated remediation-class diffs (the same class as codex #34's `39a9ed4` remediation commit).

### Out-of-scope / non-goals

- No acceptance-harness code (that is the #605 acceptance PR; plan KTD4).
- No codex-side changes (PA-2 re-ports after this merges).
- No dispatcher lease-seam changes (Claude wiring is already live at `outcome.py:2422/:2478`;
  activation is PA-2's codex-side work).
- No behavior change to `discover`/`handoff`/`attach` semantics — help text, dead code, and
  directory-permission hardening only.

### Files expected to change

- plugins/saga/scripts/outcome.py
- plugins/saga/scripts/outcome_compat.py
- plugins/fleet-core/scripts/fleet_commons/audit_store.py
- plugins/saga/.claude-plugin/plugin.json
- plugins/fleet-core/.claude-plugin/plugin.json
- .claude-plugin/marketplace.json
- plugins/saga/CHANGELOG.md
- plugins/fleet-core/CHANGELOG.md
- tests/ (behavior tests per fix; guard-floor updates if the release-event guard pins floors)

### Tests to add or update

- Help-text pins for `outcome.py export`/`import` argparse descriptions (live semantics, no
  `outcome-bundle/1` wording).
- Import-arm refusal shape: `CompatibilityHaltError` receipt JSON on stdout, exit code 3, no
  success print, zero filesystem writes.
- `_write_once` handoff-dir: fresh store created `0o700`; pre-existing permissive/symlinked/
  non-owned handoffs dir refused with the typed error; sealed records remain `0o600`.
- `audit_store` ancestor hardening: symlinked component below home refused; world-writable
  ancestor below home refused; home itself and out-of-home (temp-root) paths exempt; typed
  `AuditStoreError` in every refusal.

### Context library links
- source_context: docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md (section "Pre-acceptance production units", PA-1)

### Acceptance criteria

- [ ] `uv run pytest tests/ -k "outcome or audit_store" -q` passes with the new behavior tests
      for all four fixes included and green.
- [ ] `uv run python plugins/saga/scripts/outcome.py import --help` output describes the
      always-refuse migration semantics and contains no `outcome-bundle/1` success wording;
      `export --help` names the deprecated read-only `discover` alias.
- [ ] `python3 -c "import json,subprocess;..."` refusal probe: running `outcome.py import` against
      a fixture bundle exits 3 with a refusal-receipt JSON and leaves the store byte-identical
      (asserted by the new import-arm test).
- [ ] `stat -f %Lp` on a freshly created handoff store directory reports `700` (asserted by the
      new `_write_once` test, including the pre-existing-dir refusal case).
- [ ] Release surfaces agree in one PR: saga `0.105.0` and fleet-core `0.16.0` in
      `plugins/*/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, both
      `CHANGELOG.md`s; guard floors raised as floors (`uv run python
      scripts/check_release_surface_parity.py` green).
- [ ] Full battery green and programmatic `saga:code-review` gate reports zero open P0-P3; PR
      closes this issue on merge.

### Verification

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
git diff --check
```

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md
- Source type: local-file
- Source title: PA-1 upstream hardening (cross-runtime-acceptance plan, pre-acceptance units)

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/624
- Number: 624
- Created at: 2026-07-20T05:11:09.053105+00:00

