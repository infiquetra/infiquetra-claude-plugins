# Code review — readonly-verifier fallback + registration drift guard (#325)

**Verdict: CLEAN, not blocked.** Zero P0/P1 findings across the full review. Two findings
(P2, P3) surfaced by the testing lens, independently validated, and fixed in the same PR before
this artifact was written — both are marked `fixed` below, not `open`.

## Review-result contract

- **Target:** branch `fix/325-readonly-verifier-fallback` vs `origin/main`
- **Reviewed revision:** `3d91c58c4b8081e6c7e30babb5c6d212135fc2a0` (post-fix HEAD; the review
  that surfaced the two findings ran against `bf5fcd4b1805724d983f55fd88c5e6314b93ba9b` — see
  "Fix trail" below for why the fix commit didn't require a fresh full lens pass)
- **Blocked:** no
- **Mode:** programmatic, called from `/work`'s pre-PR gate
- **Linked issue:** infiquetra/infiquetra-claude-plugins#325
- **Linked plan:** `docs/plans/2026-07-03-readonly-verifier-registration-fallback-plan.md`
- **Linked work-session:** `docs/work-sessions/2026-07-03-readonly-verifier-registration-fallback.md`

## Scope check

**CLEAN.** Intent (from the plan + commit messages): document a fallback ladder for
`saga:readonly-verifier`, add a static registration drift guard, bump release surfaces, journal
the decision. Delivered: exactly that — 9 files across 5 commits, no unrelated changes. No scope
creep, no missing requirement.

## Plan-completion audit

| Requirement | Status | Evidence |
|---|---|---|
| R1 — reload-path verified as evidence, no code change | DONE | Plan's verification table + `docs/engineering-journal/LEARNINGS.md#stale-agent-roster-325`; a live `saga:readonly-verifier` spawn resolved and ran during plan-phase |
| R2 — fallback-ladder section in `sandbox-spawn-sites.md` | DONE | `plugins/saga/references/sandbox-spawn-sites.md` "Fallback when `saga:readonly-verifier` is unavailable" section |
| R3 — `CLAUDE.md` one-line pointer | DONE | `CLAUDE.md:9` |
| R4 — drift-guard test, 4 assertions (a)-(d) | DONE | `tests/test_agent_registration_drift.py`, 10 tests, all passing; assertions (a)/(b)/(c) now factored into shared `_name_matches_stem`/`_constant_matches_frontmatter`/`_dangling_references` helpers per the fix commit |
| R5 — release surfaces | DONE | `plugin.json`/`marketplace.json`/`CHANGELOG.md` all read `0.49.2`; `tests/test_saga_plugin.py:48` version-drift literal updated in the same PR |
| R6 — journal entries | DONE | `LEARNINGS.md#stale-agent-roster-325`, `DECISIONS.md#readonly-verifier-fallback-ladder-325` |

No PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE items.

## Findings

| # | File | Issue | Reviewer | Confidence | Route | Status |
|---|---|---|---|---|---|---|
| 1 | `tests/test_agent_registration_drift.py:79-141` (pre-fix line numbers) | Synthetic-negative tests reimplemented each comparison inline instead of calling the production logic — mutation-tested and confirmed all 3 stayed green with the real comparison neutered | testing | 100 | safe_auto → unit | **fixed** (commit `3d91c58`) |
| 2 | `tests/test_agent_registration_drift.py:158,169` (pre-fix line numbers) | Missing existence guard before `.read_text()` on the two doc paths, inconsistent with the file's own pattern at the agent-file check; raw `FileNotFoundError` instead of a clear assertion message | testing | 100 | safe_auto → unit | **fixed** (commit `3d91c58`) |

No P0/P1 findings at any point. No suppressed sub-threshold findings beyond the two
already-noted residual-risk items below.

## Fix trail (why no fresh full lens pass on the fix commit)

Both findings were independently validated by dedicated `saga:readonly-verifier` agents
(reproducing the exact mutation-kill failure and the exact `FileNotFoundError` before any fix
was applied). After applying the fix (extracting `_name_matches_stem` /
`_constant_matches_frontmatter` / `_dangling_references` and adding the two existence guards),
the same three mutations were re-applied to a working copy and re-verified to now fail the
correct synthetic-negative test — i.e., the fix was proven to close the exact gap the validators
found, using the same falsification method they used. Full suite (1821 tests), `ruff`, and
`mypy` all re-ran clean post-fix. This is treated as equivalent-or-stronger evidence to a fresh
lens pass for this narrow, mechanical, single-file fix — a full 4-lens re-fan-out was not
re-run.

## Coverage

- **Suppressed count:** 0 findings suppressed below confidence 75 (none arose below that bar
  worth recording).
- **Residual risks (sub-threshold, not gating):**
  - The "Explore agent structurally lacks Edit/Write/NotebookEdit" claim in the fallback-ladder
    doc is not independently verifiable from repo-side evidence (security lens) — it's a claim
    about the harness's runtime agent-type taxonomy, not something this repo can assert. Noted,
    not actionable here.
  - `_parse_frontmatter` in the new test file duplicates `tests/test_agent_tiering.py`'s helper
    with a different signature (`str` vs `Path`) — self-disclosed in the new file's docstring,
    judged not to rise to a reportable maintainability issue under this repo's existing
    per-test-file convention (maintainability lens).
  - No synthetic test for the "`name:` key entirely absent from frontmatter" branch of assertion
    (a) — only the mismatch case is covered (testing lens, confidence ~60, sub-threshold).
- **Testing gaps:** none blocking; the two gaps above are cosmetic/coverage-completeness notes,
  not defects.

## Lenses run

correctness, security, testing, maintainability/conventions (all 4 always-on). No conditional
lens selected — docs + one pure-local-filesystem test file, no deploy/migration/reliability/
performance/api-contract/adversarial surface in this diff.
