# Code Review — feat/pf-fleet-commons-463 (#463)

- **Target:** branch `feat/pf-fleet-commons-463` vs `main` (merge base `219a7bf`)
- **Reviewed revision:** `864c4c0` (final; round 1 reviewed `3300103`)
- **Mode:** programmatic (called by `/work` as the pre-PR gate)
- **Blocked:** false — zero unresolved findings after two fix rounds, each adversarially re-verified
- **Linked issue:** infiquetra/infiquetra-claude-plugins#463
- **Plan:** `docs/plans/2026-07-04-fleet-commons-mechanism-plan.md`
- **Work session:** `docs/work-sessions/2026-07-04-fleet-commons-mechanism.md`

## Verdict

**CLEAN.** Scope check: CLEAN (every changed file maps to a plan unit U1–U6 or a plan-mandated
release surface). Plan-completion audit: U1–U6 all **DONE** with commit evidence (`713a870`,
`131ef49`, `da8a07e`, `803be61`, `7eadf3d`). Suppressed findings (<75 anchor): none reported.

## Lens team (round 1, reviewed SHA `3300103`)

Four always-on lenses — correctness, security, testing, maintainability/conventions — each
spawned read-only in a disposable worktree (`saga:readonly-verifier`). No conditional lenses:
the diff has no deploy/migration or infra surface. Every finding below was *executed* (reproduced
live) by its lens, which served as the independent validation pass.

| # | Sev | File | Issue | Lens | Conf | Status |
|---|---|---|---|---|---|---|
| 1 | P1 | `fleet_commons_shim.py` `_rung_installed_plugins` | One malformed record in a multi-record registry list aborted the whole rung-3 scan (whole-function try/except) | testing | 90 | **FIXED** `8063908` — per-record tolerance + regression test |
| 2 | P2 | `executor_profile_lint.py:38` | `_FIELD` required bold markers; real corpus uses plain/backticked/packed bullet shapes | correctness | 90 | **FIXED** `8063908` + `864c4c0` — see round 2 |
| 3 | P2 | `fleet_commons_shim.py` `load()` | Module cache keyed by name only; mid-process `FLEET_COMMONS_ROOT` change returned a stale module | correctness | 100 | **FIXED** `8063908` — cache keyed by (module, root) + regression test |

Security lens: zero findings (all rungs resolve under the invoking user's control; lint regexes
linear-time; no injection path; subprocess tests use arg lists with explicit env).
Maintainability lens: zero findings after adversarial checks (release triads across all three
touched plugins verified live; vendored copies byte-identical; census ids cross-checked against
survivor files; README example matches the shim API; the two >100-char `execution_spec.py` lines
are pre-existing, blamed to commits before this branch's base).

## Round 2 (delta review of `8063908`)

Adversarial verifier **upheld** fixes #1 and #3 (per-record shapes covered; vendored copies
byte-identical; resolve-on-every-load breaks nothing — 34 targeted tests pass) and **refuted**
part of fix #2 with a live reproduction: unanchored `findall` let prose colons inside a
`Justification` bullet spawn phantom `model`/`effort` fields that overrode the authored values
via first-wins `setdefault`.

**FIXED** `864c4c0`: fields now match anchored per sentence segment (at most one field per
sentence); prose-valued fields (`Justification`, `External-LLM posture`) end their bullet's scan.
Regression test encodes the exact reproduction.

## Round 3 (verification of `864c4c0`)

Independent adversarial verifier attempted segment-boundary leaks, value-embedded sentence
splits, prose-field-first orderings, and all four corpus bullet shapes: **zero refutations**.
Exit-code contract (0/1/2) confirmed unchanged; full lint test file 13/13.

## Coverage

- Full gate at final SHA: `uv run pytest` **1930 passed**; `ruff format --check` / `ruff check`
  clean; `mypy plugins/ scripts/ tests/` clean.
- Corpus validation: `pf-single-vocab-source.md`, `pf-team-engine-worker-slot.md`,
  `pf-envelope-authorized-merge.md`, and issue #463's own body all lint exit 0.
- Residual risks: `installed_plugins.json` remains an undocumented internal (mitigation: rung-3
  degrade + KTD5 revisit trigger); vendored-shim drift (mitigation: byte-identity CI guard) —
  both accepted and recorded in DECISIONS `{#fleet-commons-mechanism-463}`.
