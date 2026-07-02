# Doc-review: team-spawn residency guard plan — readiness

- **Target:** `docs/plans/2026-07-02-team-spawn-residency-guard-plan.md`
- **Reviewed revision:** working tree (plan authored same session, HEAD `9fd2ab1`)
- **Classification:** plan (`docs/plans/`, `origin:`, U-IDs/KTDs present); formal rubric phases
  (idea/issue/spec) not applicable — readiness-skeptic pass ran inline per operator instruction
  (no agents)
- **Linked issue:** infiquetra/infiquetra-claude-plugins#289
- **Blocked:** NO — ready to drive `/work` after applied fixes
- **Review artifact:** `docs/reviews/2026-07-02-team-spawn-residency-guard-plan-readiness.md`

## Verdict

One materially wrong execution assumption (KTD3 registry resolution fails in the
marketplace-installed layout) was found and fixed in place with direct filesystem + docs evidence;
every other load-bearing claim re-verified fresh against current sources. No P0/P1 remains open.

## Findings

| # | Priority | Status | Finding |
|---|---|---|---|
| F1 | P1 | FIXED | KTD3's primary path `$CLAUDE_PLUGIN_ROOT/../team-execution/` does not exist when marketplace-installed — the installed layout is versioned (`cache/<marketplace>/<plugin>/<version>/`; verified: saga `0.46.0`, team-execution `2.6.0` under `cache/infiquetra-plugins/`). The hook would silently degrade to inert exactly in installed sessions, its primary habitat. Fixed: four-step resolution chain (plugin-root sibling → versioned-cache sibling picking highest semver → `CLAUDE_PROJECT_DIR` → bounded cwd-ancestor scan), plus matching U1 resolver description and tmp_path test scenarios. |
| F2 | P2 | FIXED | The manual `printf \| python3` acceptance checks run with no env vars and no `cwd` in the envelope, so the plan's original resolution (env var, then envelope-cwd walk) would return an empty trigger set and the "warns" AC would spuriously fail. Fixed: chain step 4 falls back to process cwd; noted explicitly in KTD3. |
| F3 | P3 | FIXED | KTD3's rationale ("the marketplace clones the whole repo") described the wrong mechanism for the layout that actually runs — the cache copy is per-plugin-per-version, not a repo clone. Subsumed by the F1 rewrite; probe table row added documenting the real layout. |

## Staleness re-verification (operator-requested)

Every load-bearing claim checked against a direct, current source this session:

| Claim | Verdict | Source |
|---|---|---|
| Spawn tool_name is `Agent` here / `Task` stock; `subagent_type`, `name` are `tool_input` fields | FRESH | Live transcript `d19962ce-….jsonl` Agent tool_use; current session Agent schema |
| `run_in_background` no longer exists on the Agent tool | FRESH | Current Agent tool schema (no such property); live spawn carries none |
| `additionalContext` honored on PreToolUse, exit-0 JSON | FRESH | code.claude.com/docs/en/hooks (fetched 2026-07-02) |
| `CLAUDE_PLUGIN_ROOT` + `CLAUDE_PROJECT_DIR` exported to hook processes | FRESH (newly verified) | plugins-reference, Environment variables section |
| Matcher `Agent\|Task` is an exact-string list — cannot fire on `TaskCreate`/`TaskStop` | FRESH (newly verified) | hooks docs matcher table (letters + `\|` → exact match) |
| S-1 (#275) CLOSED; U3/U4 residency prose live | FRESH | `gh issue list`; `consensus-protocol.md:26,51-53` grep |
| Trigger set 18 (10 reviewers + 8 testers), 7 excluded, 25 agent files | FRESH | `ls plugins/team-execution/agents/` enumeration cross-checked against both registries |
| Hook precedent line refs (`pre_push_gate_hook.py:118-128,142-144`; `stale_main_session_hook.py:235-245`) | FRESH | File reads this session |
| Release triad 0.47.0 → 0.48.0; `test_release_triad.py` parametrized drift guard | FRESH | `plugin.json:3`, `marketplace.json:86`, test header |
| Issue #289 OPEN, requirements-ready | FRESH | `gh issue view` this session |

## Applied fixes

1. KTD3 rewritten to the four-step resolution chain with layout evidence (F1/F3).
2. U1 `_find_references_dir` description aligned; resolver test scenarios added (F1).
3. Process-cwd fallback documented as what makes the manual ACs pass (F2).
4. Probe table extended with three verified rows: env-var export, matcher semantics, installed
   layout.
5. Journal entry `DECISIONS.md#team-spawn-residency-guard-ktds-289` KTD3 wording corrected to
   match.

## Amendment — same day, operator-requested residual-risk fix

| # | Priority | Status | Finding |
|---|---|---|---|
| F4 | P2 | FIXED | Version-pick heuristic staleness (former residual risk 1): the max-semver glob could read a just-superseded or downgraded team-execution registry. Fixed: KTD3 step 2 now reads the **authoritative** active version from `installed_plugins.json` (`ROOT.parents[3]`, verified shape `{"plugins": {"team-execution@<marketplace>": [{"installPath": …}]}}`, marketplace-matched key preferred); the semver glob survives only as last resort when the registry file is absent/unreadable/keyless. U1 resolver description + test scenarios (registry-authoritative-over-max-semver, fallback-on-malformed) and the journal entry updated to match. |

## Residual risk

- **Harness schema drift:** the name-only predicate is pinned to today's Agent tool schema; the
  journal entry carries the revisit-when (schema reintroduces/renames persistence fields). Not
  fixable in the plan — it is a monitoring condition, not a defect.
- **`CLAUDE_PLUGIN_ROOT` mid-session update nuance:** after a plugin update, hooks keep the
  previous version's path until `/reload-plugins` (per docs) — resolution keeps working because
  the old dir lingers; no action needed.
