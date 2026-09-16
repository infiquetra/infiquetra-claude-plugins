---
title: Finite test plan — Orchestrate / Agent Launcher companion-contract findings from issue 1003
type: test
status: active
date: 2026-09-16
origin: GitHub issue 1003 and children 952, 957, 958, 962, 973, 977, 978, 980
backend: inline
---

# Finite test plan — Orchestrate / Agent Launcher companion-contract findings from issue 1003

This plan exists before any implementation commit. Every scenario drives a shipped function or CLI entry in `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` (ingest, bind, `cmd_status`, `cmd_check`, write commands) or the bound-name list in `plugins/agent-launcher/skills/agent-launcher/SKILL.md`. Tests live in `tests/test_agent_launcher_plugin.py` unless a scenario names `plugins/agent-launcher/tests/test_launcher_contract.py` or `tests/test_orchestrate_drift_and_adopt.py`.

No scenario re-implements the unit under test, mocks `_ingest_agent_launcher` / `_bind_missing_launcher_names` / `cmd_status` / `cmd_check`, or starts past ingest. Companion state is produced by pointing `AGENT_LAUNCHER_ROOT` or the installed-plugin cache at a real tree.

## Key Technical Decisions

KTD1. Each scenario calls the shipped ingest path from a representative companion tree. Patching `_AGENT_LAUNCHER_AVAILABLE` is not coverage.

## Implementation Units

### U1. Finite scenario table

The table below is the executable unit. Implementation of the behaviors it names is the companion plan `docs/plans/2026-09-16-issue-1003-companion-contract-plan.md`.

## How to run

```bash
python3 -m pytest tests/test_agent_launcher_plugin.py tests/test_orchestrate_drift_and_adopt.py plugins/agent-launcher/tests/test_launcher_contract.py -q
```

A scenario is done when the named test calls the shipped function or CLI and the assertion matches the expected outcome column.

## Companion states this plan uses

One classification, four states. Every command under test reads the same classification.

| State | How the test produces it | Reads (`status`, `check`) | Writes (`go`, `land`, …) |
|---|---|---|---|
| missing | no launcher tree / empty `AGENT_LAUNCHER_ROOT` | degrade; no `SystemExit` from a bound name | refuse, install remedy |
| below-floor | manifest `<1.4.0`, source otherwise complete | live Herdr reads still run | refuse, update remedy |
| ingested-but-unusable | floor-satisfying tree missing a bound name, **or** a ~30-line name-only stub whose bound names exist but `guard_pane_before_write` does not call `pane_input_inspection` | degrade; no `SystemExit` | refuse, named companion fault |
| usable | shipped launcher at or above the floor | live Herdr reads | proceed |

`below-floor` is not a child of #1003; it stays in the table so F107/F127 cannot be implemented by collapsing it into unusable.

## Finding classes

| ID | Issue | Finding | Shipped function or CLI | Input companion state | Action | Expected outcome | Test |
|---|---|---|---|---|---|---|---|
| TP-F101 | #952 | Launcher that dropped a name Orchestrate still calls is selected as a write companion, including when the cache picks the highest version | `_agent_launcher_script` then `_ingest_agent_launcher` / `assert_agent_launcher_available` | Installed cache with a complete floor tree **and** a higher-version tree that renamed away one name in `REQUIRED_LAUNCHER_NAMES`; `CLAUDE_PLUGIN_ROOT` points at that cache (orchestrate install root, so `parent/agent-launcher/<ver>/…` is the glob `_agent_launcher_script` already uses) | `go` (write) and the pairing scan of shipped `launcher.py` | `go` refuses with the named companion fault (`does not define` + update remedy, not a `NameError` and not `not found`); shipped `launcher.py` still defines every name in `REQUIRED_LAUNCHER_NAMES` (assignment targets count, including `ComposerState = _COMPOSER.ComposerState`). The pairing test compares the shipped tree to the tuple; it does not encode semver. A later major bump updates the tuple and the floor together, then this test compares the new pair. | `test_highest_cache_version_that_dropped_a_bound_name_is_not_a_write_companion`, `test_shipped_launcher_defines_every_name_orchestrate_requires` |
| TP-F106 | #957 | Name-only stub (bound names present, no inspect behaviour) is treated as fully usable | `_ingest_agent_launcher` then `cmd_status` / `go` | `AGENT_LAUNCHER_ROOT` at a ~30-line `launcher.py` whose required names exist as `def …: return None` (and dummy types/dicts), manifest at the floor | ingest, then `status`, then `go` | companion is ingested-but-unusable: `status` degrades (exit 0, no traceback); `go` refuses with the named companion fault; `guard_pane_before_write` is not left bound as a no-op that authorizes writes | `test_a_name_only_stub_is_not_a_usable_companion` |
| TP-F107 | #958 | Floor-satisfying launcher missing a **read-path** bound name kills `status` | `_ingest_agent_launcher` / `_bind_missing_launcher_names` then `cmd_status` | `AGENT_LAUNCHER_ROOT` at a floor-satisfying tree with `live_agents` renamed away (write-path names may remain) | `status` | exit 0; herdr column is unknown / degraded; stderr carries the companion fault; no `SystemExit` traceback from the missing name | `test_a_launcher_root_that_lacks_a_read_path_bound_name_degrades_status` (extend `test_a_launcher_root_that_lacks_the_bound_names_is_the_named_companion_fault` so it also strips a read-path name, or add this sibling) |
| TP-F111 | #962 | LEARNINGS and test docstrings present deleted internals as current fact | document scan of `docs/engineering-journal/LEARNINGS.md` and the two live helper docstrings | working tree | assert | `{#907-osc-regex-quadratic}` still names `PANE_INSPECT_MAX_CHARS` as a present-tense cap (restored by #1002; do not delete it); `_prepare_resend_launch` and `test_redeliver_inspects_before_the_first_write_on_an_owned_unit` do not describe `say()` or `used_pane` as live helpers | `test_live_docs_do_not_present_deleted_say_or_used_pane_as_current` |
| TP-F122 | #973 | `orchestrate.md` install sentence omits the agent-launcher floor | `plugins/orchestrate/commands/orchestrate.md` | the bolded install sentence | read | that sentence names `agent-launcher` and the declared floor (`1.4.0` or whatever `plugin.json` currently declares). Floor itself does not move in this issue. | `test_orchestrate_install_sentence_names_the_agent_launcher_floor` |
| TP-F126 | #977 | `land` / `review-result` gate comments still cite `say` | `cmd_land` and `cmd_review_result` source | AST / source of those two functions | read the comment on `assert_agent_launcher_available` | each comment names `PaneWriter` or the pane-guard send, not `say` | `test_write_gate_comments_name_the_live_write_path` |
| TP-F127 | #978 | `check` prints `the record agrees with the repository` and exits 0 when liveness was not performed | `cmd_check` | missing companion, name-only stub, **or** floor-satisfying tree missing a bound name; run record otherwise clean | `check` | does **not** print `the record agrees with the repository`; does **not** exit 0; stdout or stderr names that liveness was not checked. A **usable** companion with an empty `live_agents` list still prints agreement and exits 0 (`test_a_clean_run_reports_nothing` stays green). | `test_check_does_not_agree_when_liveness_was_not_performed` |
| TP-F129 | #980 | SKILL.md bound-name list and `REQUIRED_LAUNCHER_NAMES` disagree | `REQUIRED_LAUNCHER_NAMES` and SKILL.md section "The surface Orchestrate binds" | shipped files | parse both lists | the sets are equal (including `ComposerState`, which SKILL.md already lists and which ingest already binds from `launcher.py`). Drift fails this test. | `test_skill_bound_name_list_matches_required_launcher_names` |

## Four-state CLI matrix (functional, not pytest)

From a clean worktree of the branch, with `AGENT_LAUNCHER_ROOT` pointed at (i) the shipped launcher, (ii) a missing companion, (iii) a name-only stub, (iv) a floor-satisfying tree missing a read-path bound name, run `python3 plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` for `--help`, `status`, `check`, and one write command (`go` or `land`). Repeat the four-state matrix. Both runs must match.

| Companion | `--help` | `status` | `check` | write (`go` or `land`) |
|---|---|---|---|---|
| (i) shipped | exit 0 | live or empty-run display, exit 0 | agreement only if liveness ran and git agrees | proceeds or ordinary run-state error, not a companion fault |
| (ii) missing | exit 0 | degrades, no traceback | no agreement sentence, non-zero | refuse, install remedy |
| (iii) name-only stub | exit 0 | degrades, no traceback | no agreement sentence, non-zero | refuse, named companion fault |
| (iv) missing read-path name | exit 0 | degrades, no traceback | no agreement sentence, non-zero | refuse, named companion fault |

## Assertions that must change with the behavior

These currently pin the defects. Leaving them green is not coverage.

| Current assertion | After this issue |
|---|---|
| `test_a_launcher_root_that_lacks_the_bound_names_is_the_named_companion_fault` runs `status` against a tree that still defines `live_agents`, so F107 is untested | the same family must strip a read-path name (`live_agents`) and still see `status` exit 0 with no traceback |
| `tests/test_orchestrate_drift_and_adopt.py` `cmd_check` agreement cases (`test_a_clean_run_reports_nothing` and siblings) use a **usable** in-repo launcher | those stay green; they are not F127. Same for agreement assertions in `tests/test_orchestrate_land_clean.py` and `tests/test_orchestrate_run_branch_resolution.py`. F127 is a new ingest-driven case that must fail if agreement+exit 0 returns for missing/unusable companions |
| SKILL.md lists `ComposerState`; `REQUIRED_LAUNCHER_NAMES` does not | either the tuple gains `ComposerState` or SKILL.md drops it; the cross-check test fails if they drift again |

## Version-parity scenarios (release unit)

| Test | File | Expected |
|---|---|---|
| orchestrate metadata | `tests/test_agent_launcher_plugin.py` / marketplace contract tests | `plugin.json` version equals marketplace `orchestrate` version; CHANGELOG has a heading for that version |
| agent-launcher metadata | `test_agent_launcher_metadata_is_marketplace_registered` | marketplace `agent-launcher` version equals `plugin.json`; bump only if SKILL.md's user-facing bound-name list changed |
| Orchestrate floor | `tests/test_plugin_manifest_loader_contract.py` | `AGENT_LAUNCHER_FLOOR_RELEASE` stays `1.4.0` unless a new public name is added (this issue adds none) |

## Explicit non-coverage

- Live Herdr daemon, live vendor CLIs, and production Claude Code install.
- Findings grouped under #908, #909, #910, or #1002.
- Restoring `say()` as a live write path.
- Lockstep bump of the Orchestrate companion floor with an Agent Launcher patch that adds no new public name.
- In-the-wild Orchestrate 4.0.1 that still called `say()`; this tree's Orchestrate no longer calls it. F101 is the pairing guard and the cache-highest-version write refusal, not a compatibility shim for 4.0.1.
