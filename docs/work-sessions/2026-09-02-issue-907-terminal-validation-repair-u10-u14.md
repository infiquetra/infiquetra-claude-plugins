# Issue 907 terminal-validation repair — units U10 through U14 executed

**Date:** 2026-09-02
**Branch:** `work/cp907-launcher-session-contract`
**Plan:** `docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md` (round-3 document review ready)
**Backend:** inline (the plan's frontmatter)
**Scope:** U10 through U14. U1–U9 remain as recorded in
`docs/work-sessions/2026-09-02-issue-907-terminal-validation-repair-u1-u9.md`.
**change_kinds:** behavior, api, docs, config

## What was built, by unit

| Unit | Commit | One line |
|---|---|---|
| U10 | 86b5ac88 | Inspect unowned panes before review-result and land writes |
| U11 | d3f16e75 | Merge origin/main; keep three companion floors and both changelog histories |
| U12 | 41f947eb | Journal claims followable; six anchors bound |
| U13 | 8deccf2c | README and command doc say the agent-launcher floor is enforced |
| U14 | 121f0769 | Orchestrate 4.1.0, agent-launcher 1.2.2, cache dirs from manifests |

## Kill-list outcome per unit

- **U10:** both killed (removing the inspection fails unowned-draft; inspecting regardless of ownership fails owned-sends-without-a-read).
- **U11:** merge unit; no named code mutant. Conflict resolutions recorded below.
- **U12:** journal/anchor unit; the six-anchor drift pin is the observer.
- **U13:** both killed (restoring `nothing verifies them` fails the README contract; restoring `no code checks` fails the command-document contract).
- **U14:** killed (restoring a `3.0.1` orchestrate cache-dir literal fails the ARCH-20 source pin; leaving marketplace or CHANGELOG on 4.0.2 / 1.2.1 fails the release triad).

## U11 merge conflict resolutions

Merged `origin/main` (`f30d8678`) with no rebase.

1. `plugins/orchestrate/.claude-plugin/plugin.json` — version 4.0.2 at merge (U14 later 4.1.0); dependencies: `agent-launcher >=1.2.1` (then `>=1.2.2`), plus main's `mission-control >=2.15.1` and `saga >=0.151.0`.
2. `.claude-plugin/marketplace.json` — orchestrate stayed 4.0.2 at merge; U14 moved it to 4.1.0.
3. `plugins/orchestrate/CHANGELOG.md` — 4.0.2 (branch) above main's 4.0.1 and 4.0.0.
4. `orchestrate.py` `_controller_candidates` — kept U9 `_plugin_root` plus main's `_install_candidates`.

## Checks run

- After U10: plugin subset 932 passed.
- After U11 merge, before U12: plugin subset 981 passed.
- After U12: plugin subset 982 passed.
- After U13: plugin subset 983 passed.
- After U14: plugin subset plus release triad/parity 1042 passed.
- Full gate: `GATE_LOG_DIR=/tmp/gate-cp907-u14`. **GATE RED**, exit 1. Three blocking
  steps failed (none of these is a U14 pin or triad miss):
  1. `tests/test_plan_artifact_conformance.py` — the historical
     `docs/plans/2026-08-30-agent-launcher-907-run-plan.md` declares `backend: inline`
     (new-contract) but has no `Implementation Units` / KTD / `U1` markers (it uses
     L1–L7). The accepted plan was not edited.
  2. Journal newest-first guard — 907 entries filed under `## 2026-08-31` are new
     versus `origin/main` and must sit under `## 2026-09-02`.
  3. mypy — 11 errors in `tests/test_orchestrate_launch_and_land.py`,
     `tests/test_agent_launcher_plugin.py`, and
     `plugins/agent-launcher/tests/test_launcher_contract.py` (annotation / unpack
     mismatches, including a pre-existing `_matrix_layout` 3-tuple annotation on a
     4-tuple return).

## Follow-on units U15 and U16 (operator-bounded gate repairs)

Recorded after this session file was first written. Commits: U15 `2b7b8519`, U16 `ff7efa78`.
The plan-conformance failure on `docs/plans/2026-08-30-agent-launcher-907-run-plan.md` remains held.

## Next step

Stop. Do not launch the terminal Saga Code Review. Do not push, open a PR, merge to main, or close the issue. The review is held on a separate operator ruling.
