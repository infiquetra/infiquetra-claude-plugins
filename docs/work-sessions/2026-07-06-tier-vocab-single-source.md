# Work session — Single-source tier palette (#370)

**Issue:** infiquetra/infiquetra-claude-plugins#370 · **Plan:** `docs/plans/2026-07-06-tier-vocab-single-source-plan.md`
**Branch:** `feat/370-tier-vocab-single-source` · **Backend:** inline · **Destination:** merge
**Doc-review:** `docs/reviews/doc-review-issue-370-2026-07-06.md` (blocked=NO)

## What was built (by U-ID)

| Unit | What shipped | Commit |
|---|---|---|
| U1 | `models.json` registry (per-model `rank`/`effort_ceiling`, per-effort `rung`); `tier_palette.py` derives `MODELS`/`EFFORTS` from it at import; import-time validation rejects dup/gapped rank + missing ceiling | `89aec64` |
| U2 | `escalate`/`downgrade`/`clamp`/`stronger`/`strongest` ladder ops (strength-oriented) + `effort_ceiling`/`supports_effort`/`clamp_effort_to_model`; `segment_units()` refactored onto `strongest()` | `92671a4` |
| U3 | `Tier.validate()` HALTs on a Claude teammate's over-ceiling effort (haiku/xhigh); engine-owned units excluded; parametrized ladder-monotonicity guard | `359ac26` |
| U4 | Vocabulary-redefinition drift guard (AST scan of production Python) — the achievable form of AC1 | `22f6873` |
| U5 | `references/tier-palette.md` onboarding runbook + operator-table tier-token drift guard (AC8) | `79749ac` |
| U6 | Release surfaces: fleet-core 0.4.0→0.5.0, saga 0.63.0→0.64.0; marketplace regenerated; saga pin moved | `fd544a4` |

## Key decisions (from the plan, ratified in build)

- **KTD1 — extended `tier_palette.py` in fleet-core; did NOT create `tier_vocab.py`.** #463 already
  extracted the vocabulary there; a second module would be the drift the issue exists to kill.
- **AC9 was already satisfied** (execution_spec imports via the shim re-export) — regression-guarded only.
- **AC1 reinterpreted** (doc-review finding A): "zero bare literals" is unachievable vs ~205 legit
  model-name mentions; the guard enforces "no second vocabulary *source*" (a tuple/list of ≥2 same-vocab
  tokens) over production Python — precise, passes clean, reds on reintroduction.
- **AC8 team-execution half** (finding B): the illustrative worker table isn't catalog-generated, so the
  guard validates its displayed `model/effort` tokens against the vocabulary (catches `opus/superhigh`).

## Checks run

- `uv run pytest` — **2213 passed, 1 skipped**; new suite `tests/test_tier_vocab_single_source.py` (28 tests).
- `uv run ruff format --check .` + `uv run ruff check .` — clean.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — clean.
- `tools/release_surface_diff_guard.py --base-ref main` — all changed plugins bumped (fleet-core, saga).
- Existing ordering regression `test_segment_tier_merge_prefers_fable_and_xhigh` — green against the
  registry-derived tuples.

## Next step

Code-review gate → PR (merge on green CI). On merge, attach the PR to outcome node `sub-370` and
`/outcome advance` to unblock #364/#366/#367.
