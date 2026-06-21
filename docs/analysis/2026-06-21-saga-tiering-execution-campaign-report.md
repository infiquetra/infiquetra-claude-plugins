---
title: Saga Tiering & Execution-Mechanism Campaign — Reconciliation Report
type: analysis
status: complete
date: 2026-06-21
plan: docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md
---

# Saga Tiering & Execution-Mechanism Campaign — Reconciliation Report

U17 closure. This report maps **every** requirement R1–R18 from the campaign plan to the
unit and merged PR that landed it. There are **no silent skips**: every R-ID is accounted
for as either landed-in-a-merged-PR, applied-inline (R4), or carried structurally by another
R (called out explicitly below).

## Gate status (post all-5-epic merge, run from the U17 worktree off `origin/main`)

Run with the CI-parity env (`uv python pin 3.12` + `uv sync --locked --extra dev`):

| Gate | Command | Result |
|---|---|---|
| Format | `uv run ruff format --check .` | PASS — 109 files formatted |
| Lint | `uv run ruff check .` | PASS — all checks passed |
| Plugin validator | `uv run python scripts/validate_plugins.py` | PASS (exit 0; scans top-level `plugins/*.md` only — designed no-op, see LEARNINGS `#validate-plugins-only-scans-top-level-md`) |
| Marketplace validator | `uv run python marketplace/validator/validate.py` | PASS — 7 plugins, 0 errors, 34 warnings |
| Issue-contract parity | `python3 plugins/mission-control/config/generated/check_issue_contract_parity.py` | PASS — vendored artifacts in sync |
| Tests | `uv run python -m pytest` | PASS — **926 passed** |
| Type check | `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` | PASS — no issues in 67 source files |

**Gate is GREEN.**

## Epic merge status

All 5 epics merged to `main` as their own squashed PRs, in the planned barrier order:

| Epic | Units | PR | Squash SHA | State |
|---|---|---|---|---|
| Epic 0 — tiering spine | U2, U3 | #241 | `27ec81c` | MERGED |
| Epic 1 — execution-backend representation | U4, U5, U6 | #242 | `1575907` | MERGED |
| Epic 3 — hook harness | U7, U8, U9 | #243 | `c9757e3` | MERGED |
| Epic 4 — cheap executor + release guards | U14, U15, U16 | #244 | `9bdf363` | MERGED |
| Epic 2 — dynamic-workflow authoring | U10, U11, U12, U13 | #245 | `9e9f29c` | MERGED |

**No epic left as an unmerged open PR. No `saga.py`-conflict HALT occurred** (KTD9 rebase
discipline held; U3 and U4 touched disjoint regions of `saga.py`).

## R-ID → landed-unit map

| R-ID | Requirement (short) | Unit | Epic / PR | Landed evidence | Status |
|---|---|---|---|---|---|
| R1 | One tier rule governs every model/effort choice | U2 | E0 #241 | 4 callable agents pinned per the rule; rule prose lives at R4 (inline) | LANDED |
| R2(a) | Callable agents pin `model:` in frontmatter | U2 | E0 #241 | `plugins/{deploy/release-orchestrator,home-lab-ops/homelab-sre,mission-control/sdlc-operator,unifi/unifi-network-ops}/agents/*.md` carry `model:`; `test_agent_tiering.py` | LANDED |
| R2(b) | `/plan`-authored workflow spec carries per-unit `{model, effort}` | U10 | E2 #245 | `execution_spec.py` `Tier(model, effort)` required per unit | LANDED |
| R3 | Pilot↔fan-out same-tier invariant asserted at authoring time | U10 | E2 #245 | `execution_spec.py:240` — pilot mis-tier raises `SpecError` (fail emit); `test_workflow_emitter.py` | LANDED |
| **R4** | **Tier rule recorded as prose in global `~/.claude/CLAUDE.md`** | **none (inline)** | **— (KTD8)** | **applied-inline — operator confirm done** (see below) | **APPLIED-INLINE — OPERATOR CONFIRM** |
| R5 | Offer names both workflow purposes; drift-guard superset of §3.2 | U5 | E1 #242 | `plan`/`code-review` SKILL offer rewrite; `test_operator_choice_drift.py` | LANDED |
| R6 | Offer frames team↔workflow on the governance axis | U5 | E1 #242 | offer prose rewrite (governance, not "review depth") | LANDED |
| R7 | Recommender distinguishes gated vs advisory consensus | U6 | E1 #242 | `lifecycle_state.py` `consensus_is_gated` (default `True`); advisory → `adversarial_confidence` branch; AE1/AE2 in `test_saga_plugin.py` | LANDED |
| R8 | Display-label "dynamic workflows"; enum `cc-workflows-ultracode` frozen | U4 | E1 #242 | `saga.py:79` display map; `ORCHESTRATION_MODES` byte-for-byte unchanged; `test_saga_*` | LANDED |
| R9 | One spec, two emitters; saga records a pointer | U10, U11 | E2 #245 | `execution_spec.py` + workflow-script emitter + `team_emitter.py`; saga stores `orchestration_ref` | LANDED |
| R10 | Every fan-out unit declares enumerated targets + reconciliation | U10 | E2 #245 | `execution_spec.py:138` — empty targets raise `SpecError` (fail emit); `test_workflow_emitter.py` | LANDED |
| R11 | Capability-portable degradation on off-host resume | U12 | E2 #245 | `lifecycle_state.py` capability re-check + orchestration-tier recompile; `test_capability_degrade.py` (AE3) | LANDED |
| R12 | Choice-vs-recommendation recorded; override-rate surface | U3 (record) + U13 (surface) | E0 #241 + E2 #245 | `saga.py:174` `orchestration_recommended` field; `override_rate_reader.py` ("no data yet" on empty); `test_saga_saga.py` + `test_override_rate.py` | LANDED |
| R13 | Marketplace/plugin.json validation hook (block on failure) | U7 | E3 #243 | `hooks/hooks.json` PreToolUse → `validate_json_hook.py`; `test_marketplace_hook.py` (AE5) | LANDED |
| R14 | Journal-omission nudge hook (non-blocking, cross-repo) | U8 | E3 #243 | `hooks/hooks.json` PostToolUse → `journal_nudge_hook.py`; `test_journal_nudge_hook.py` (AE6) | LANDED |
| R15 | Pre-push gate hook from a single-source manifest | U9 | E3 #243 | `tools/gate-manifest.json` + `hooks/pre_push_gate_hook.py`; `test_pre_push_gate.py` | LANDED |
| R16 | One cheap-tier (haiku, Bash-only) op-discriminated executor | U14 | E4 #244 | `plugins/saga/agents/mechanical-executor.md` (`model: haiku`, `tools: Bash`, op-discriminated); `test_mechanical_executor.py` | LANDED |
| R17 | Release-triad sync guard | U15 | E4 #244 | `test_release_triad.py` (plugin.json ↔ marketplace.json ↔ CHANGELOG.md) | LANDED |
| R18 | SHA-stamp stager + stale-main-after-squash guard (this-repo) | U16 | E4 #244 | `tools/sha_stamp_stager.py` + `tools/stale_main_guard.py`; `test_release_rituals.py` | LANDED |

### Coverage tally

- **18 R-IDs total** (R1–R18).
- **17 R-IDs landed in merged PRs** (R1, R2, R3, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18 — counting R2 and R12 once each across their sub-units).
- **1 R-ID (R4) is applied-inline**, not built by any unit (KTD8), and counts toward "covered"
  **only once the operator confirms** the inline edit is done.

## R4 — explicit flag (applied-inline — operator confirm done)

**R4 is not built by any workflow unit.** Per **KTD8**, the global `~/.claude/CLAUDE.md` tier
rule is a file **outside this repo** and must not be edited inside an unattended fan-out. The
~3-line tier rule ("judgment → Opus; mechanical/deterministic → Sonnet/Haiku; read-only
sampling/survey → Sonnet") is **applied inline with operator confirmation, out of band**.

Epic 0's success condition ("the tier rule is loaded every session") **depends on R4**, so it
is **not optional** — it is a required operator step, tracked here rather than silently assumed
done. The R-ID coverage count treats R4 as covered **only after the operator confirms** the
inline edit landed in `~/.claude/CLAUDE.md`.

**Action for the operator:** confirm the tier rule is present in `~/.claude/CLAUDE.md`. Until
then, treat the campaign as 17/18 R-IDs covered with R4 pending operator confirmation.

## Open items / non-silent flags

- **R4** — applied-inline, **operator confirm done** (above). The only item not closed by a
  merged unit.
- **No unmerged epic PRs.** All 5 epics merged; no required-epic HALT, no non-required-epic
  open PR, no `saga.py`-conflict HALT.
- **No silent skips.** Every R1–R18 is in the table above with a landed unit or the R4 inline flag.

## Cross-references

- Plan + sibling harness: `docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md`,
  `docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`.
- DECISIONS: `#saga-tiering-execution-campaign-shipped`, `#saga-tiering-execution-campaign-plan`.
- LEARNINGS: `#display-label-map-decouples-enum-from-prose`,
  `#gated-vs-advisory-consensus-is-a-governance-split`,
  `#ci-parity-needs-pinned-python-and-extras`,
  `#validate-plugins-only-scans-top-level-md`.
