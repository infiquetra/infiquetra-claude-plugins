---
title: Code review — issue 1003 Orchestrate / Agent Launcher companion contract
type: code-review
status: accepted
date: 2026-09-16
reviewed_revision: 43609af93786c484053f071b97472282ec917e26
cycle: 1
outcome: accepted
plan: docs/plans/2026-09-16-issue-1003-companion-contract-plan.md
---

# Code review — issue 1003 Orchestrate / Agent Launcher companion contract

Cycle 1 accepted. Every selected lens `accepted`, applicable-dimension floor met, `derived_overall >= 9.0`. No remaining P0 or P1.

## Scope check

CLEAN. Ingest classification, `status`/`check` honesty, bound-name agreement, install sentence, gate comments, live helper docstrings, release triad, plans, and tests. No unrelated files.

## Plan completion

| ID | State | Evidence |
|---|---|---|
| U1 | DONE | AST-validate before exec; missing names keep `does not define` + update remedy; `_AGENT_LAUNCHER_AVAILABLE` false when names are stubbed; cache highest dropped-name refuses `go` |
| U2 | DONE | `cmd_check` records `LIVENESS UNCHECKED` and exits 1 when `agents is None`; usable-companion agreement tests stay green |
| U3 | DONE | `ComposerState` in `REQUIRED_LAUNCHER_NAMES`; SKILL.md set-equal test; install sentence names `1.4.0`; gate comments name `PaneWriter`; `PANE_INSPECT_MAX_CHARS` kept |
| U4 | DONE | Orchestrate 4.4.0 and agent-launcher 1.5.2; marketplace and CHANGELOG match; floor stays `>=1.4.0` |

## Lenses

Always-on four plus caller-selected `api-contract`, `documentation-clarity`, and `reliability` (F101/F107/F129, F111/F122/F126, F127).

| Lens | cycle | derived_overall | accepted |
|---|---:|---:|:---:|
| architecture-maintainability | 1 | 9.64 | yes |
| correctness | 1 | 9.40 | yes |
| security | 1 | 9.67 | yes |
| testing | 1 | 9.40 | yes |
| api-contract | 1 | 9.50 | yes |
| documentation-clarity | 1 | 9.33 | yes |
| reliability | 1 | 9.33 | yes |

## Findings

None at P0–P3 after cycle 1.

Residual, not scored: a stub that copies a `pane_input_inspection(...)` call shape can still pass the AST probe. The named F106 scenario is names-as-`return None`, which the probe refuses. Tests drive that scenario.

## Independent gates

- Focused pytest: 145 passed (`tests/test_agent_launcher_plugin.py`, `tests/test_orchestrate_drift_and_adopt.py`, pairing/SKILL/redeliver contract tests).
- Four-state CLI matrix (`--help`, `status`, `check`, `go`) twice; both rounds matched.
- Built-vs-planned: all four units DONE.

Typed result: `docs/code-reviews/2026-09-16-issue-1003-companion-contract-cycle1-result.v1.json`
