# Code review — feat/285-evidence-provenance-manifests

- **Target:** branch diff vs merge-base `fd2ca9e` (origin/main) · **Reviewed SHA:** `d5b340a`
- **Mode:** programmatic (called by /work) · **Backend:** inline, 5 parallel read-only lenses
  (correctness+security on opus, testing/maintainability/skill-wiring on sonnet; no fable subagents)
- **Blocked:** YES — one P0 remains at review time (safe_auto doc fix; see routing)
- **Linked:** issue infiquetra/infiquetra-claude-plugins#285 · plan
  docs/plans/2026-07-01-evidence-provenance-manifests-plan.md · work-session
  docs/work-sessions/2026-07-01-evidence-provenance-manifests.md

## Scope check: CLEAN

Intent (#285 R11 manifests) vs delivered: all 37 changed files map to plan units U0-U8 or their
documentation trail. `.serena/project.yml` is an uncommitted pre-existing local modification,
excluded. Untracked content: none in scope.

## Plan-completion audit: 9/9 DONE

U0 `766145a` · U1-U2 `f2f7160` · U3 `4054849` · U4 `10959eb` · U5 `e3840e4` · U6 `ba309b4` ·
U7 `4f2bba1` · U8 `2422137` (drift-comment drafted, not posted — by design). All five issue
acceptance selectors pass (15 tests): manifest_envelope, parroting_taxonomy,
completeness_contract_bearing, advisory_never_blocks, manifest_no_orphan_field.
Full suite 1620 passed; 1 known local-only leak-guard failure (green in CI). ruff/format/mypy clean.

## Findings (validated; Stage-B by direct-evidence checks — no validator agents, cost directive)

| # | Sev | File | Issue | Reviewer | Conf | Route |
|---|-----|------|-------|----------|------|-------|
| 1 | P0 | plugins/team-execution/skills/team-execution/references/worker-manifest.md:33 | CLI example puts `--repo-root`/`--saga-id` after the `write` subcommand — argparse parent-parser options must precede it; the documented command errors verbatim, silently breaking the worker producer path (R2) | skill-wiring | 100 | safe_auto → review-fixer |
| 2 | P2 | plugins/saga/CHANGELOG.md:13 | Claims `dispatch()` emits manifests; `dispatch()` body (engine_dispatch.py:72-121) has no manifest call — emission is `record_dispatch_manifest`, driver-invoked | maintainability | 100 (validated) | safe_auto → release |
| 3 | P2 | plugins/saga/scripts/provenance_manifest.py:208 | Unknown-enum / empty-text rejection paths in `Claim.from_dict` (lines 209, 220-221) have zero test coverage | testing | 75 (validated: 0 matching tests) | gated_auto → review-fixer |
| 4 | P2 | plugins/saga/scripts/engine_dispatch.py:208 | `adjudicate_manifest` keys adjudications by `claim.text`; two same-text claims with different source_refs cannot be adjudicated differently — wrong status can feed is_parroting and the R11 gate | correctness + testing (agreement) | 75 | manual → human |
| 5 | P2 | plugins/saga/scripts/manifest_store.py:161 | `manifest_ref`/`set_manifest_ref`/`resolve_manifest_ref` have no production caller (tests only) — dead wiring per the repo's standing rule; validated by repo-wide grep | maintainability | 75 (validated) | manual → human |
| 6 | P3 | plugins/saga/scripts/manifest_store.py:69 | `_safe_name` duplicated from outcome_store (which the module already imports privately for `_atomic_write`) — two copies of a security-relevant guard can drift | maintainability + security (parity noted) | 75 | gated_auto → review-fixer |

## Coverage

- Suppressed below-75: 0 reported by lenses (self-gated).
- Security lens: zero findings — traversal guards complete on both id levels, pointer re-validated
  post-resolve, no new exec surface, forged manifests can only skew advisory metrics (R8/R12/R20 hold).
- Correctness positive clearances: atomic write via `outcome_store._atomic_write`, rename fallout none,
  reader math zero-denominator safe, MODELS/EFFORTS ordering consumers verified.
- Residual risks: finding 4 (adjudication keying) is the only one touching gate semantics; findings
  3/5/6 are hardening. Testing gap: no duplicate-claim-text regression test (part of finding 4).
- Stage B.0: no saga-manifests tree exists for this build (units ran as workflow agents, not engine
  dispatches) — ordinary Stage-B path ran (R8/R12).
- Deviation note: Stage-B used direct-evidence inline validation (commands cited per finding) instead
  of per-finding validator agents, honoring the operator's usage-limit directive; finding 4 carries
  two-lens independent agreement in lieu of a validator.

> **Verdict: BLOCKED on finding 1 (P0)** — a one-line doc reorder, then clean. Findings 2 is a
> one-line CHANGELOG reword (safe_auto). Findings 3-6 are non-blocking hardening; 4 and 5 need an
> operator call (adjudication key design; wire-or-drop the manifest_ref helpers). Fix order: 1, 2
> pre-PR; 3-6 route per operator.

Review complete
