# Doc-Review — Fleet-Commons Distribution Mechanism Plan (#463)

- **Target:** `docs/plans/2026-07-04-fleet-commons-mechanism-plan.md`
- **Reviewed revision:** working tree, 2026-07-04 (pre-commit; plan authored this session)
- **Classification:** plan (docs/plans/ path; `origin:`, KTDs, Implementation Units, U-IDs all present)
- **Blocked:** false
- **Linked issue:** infiquetra/infiquetra-claude-plugins#463
- **Linked saga:** issue-463 (plan phase)

## Readiness summary

Ready to drive `/work`: the plan is grounded in live-observed install-layout evidence (not the
grounding brief alone), both open architectural forks were operator-confirmed before synthesis, and
four safe fixes were applied in place. A follow-up pass (operator: "fix all the findings",
2026-07-04) closed the remaining three findings — the P2 acceptance-criterion adaptation was
operator-acknowledged, and both P3s were resolved with new evidence and a specified provenance
transport. **Zero findings remain.**

## Applied fixes

| # | Fix | Evidence |
|---|---|---|
| 1 | KTD2 rung 3 made marketplace-agnostic (`fleet-core@` key prefix, no hardcoded marketplace name) | `installed_plugins.json` keys observed as `<plugin>@<marketplace>`; hardcoding would break a renamed/forked marketplace |
| 2 | `PASS_RULES` removed from the migration set (KTD3, U3) — stays in `execution_spec.py` | Survivor T3-F4-1 enumerates models/efforts/cheap-set/engine-intents/ordering only; `PASS_RULES` is refute-N vocabulary, and a smaller migration shrinks the re-export seam |
| 3 | U1 gains an installability smoke check for the scripts-only plugin shape, with a named fallback | `scripts/validate_plugins.py:81` only globs top-level `plugins/*.md` (none exist) — CI imposes nothing, so Claude Code's own install behavior is the only untested surface |
| 4 | U5's consumer made concrete: mission-control's `executor_profile_lint.py` executed end to end in the subprocess | "A consumer plugin's cache copy" was under-specified; the lint CLI is the only consumer with a natural subprocess entry point, and exercising it proves the full chain |

## Remaining findings

None. Disposition of the three findings from the initial pass:

| P | Finding | Resolution |
|---|---|---|
| P2 | AC5's "28 pool ideas" redefined by KTD6 as a recorded deterministic census (figure not reproducible: pool nets yield 10–21, survivors 19, no artifact enumerates 28 ids). | **Acknowledged by operator 2026-07-04** ("fix all the findings" follow-up); recorded in KTD6. `/work` still surfaces the final census count alongside AC5. |
| P3 | Claude Code might reject a plugin with no skills/commands/agents. | **Resolved by evidence**: `claude plugin validate` accepts a minimal scripts-only probe plugin ("Validation passed", exit 0, verified 2026-07-04). U1 keeps `claude plugin validate plugins/fleet-core` as a cheap gate; docs-only-skill fallback retained. |
| P3 | Rung-provenance transport for subprocess tests unspecified. | **Fixed in plan**: KTD2 now specifies `FLEET_COMMONS_DEBUG=1` → one stderr line `fleet-commons: rung=<n> (<name>) root=<path>`; U5 asserts that line. |

## Adversarial notes checked and cleared

- AC3's mechanical check (`grep -rl` across `plugins/*/scripts`) is satisfied by the two vendored
  shim locations plus the lint module — hits land in `plugins/saga/` and `plugins/mission-control/`.
- Three same-named `fleet_commons_shim.py` files cannot trip mypy duplicate-module detection:
  `pyproject.toml` `[tool.mypy]` excludes `plugins/.*/scripts/` wholesale.
- The issue's verification block (`test_fleet_commons_resolution.py`, `test_fleet_commons_install_time.py`,
  `grep "fleet-commons" DECISIONS.md`) maps one-to-one onto U2/U5/U6 outputs, including the anchor
  `{#fleet-commons-mechanism-463}` containing the grep token.
- Citation drift found and corrected during grounding: the issue cites
  `.../issue-map/issue-map-final.json`; the file lives at
  `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map-final.json`.
