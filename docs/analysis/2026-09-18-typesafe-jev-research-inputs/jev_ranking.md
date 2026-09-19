| Rank | Idea | Area | Value 0-3 | Effort 0-3 | Risk 0-3 | Fit p(yes) | Composite |
|---|---|---|---|---|---|---|---|
| 1 | `verify-prescreen` | saga verify panels | 2.58 | 1.13 | 1.69 | 0.75 | 0.36 |
| 2 | `global-md` | ~/.claude/CLAUDE.md, AGENTS.md, GEMINI.md | 1.86 | 0.11 | 1.55 | 0.63 | 0.19 |
| 3 | `compaction` | Claude Code context | 2.41 | 1.82 | 1.37 | 0.76 | 0.10 |
| 4 | `claim-triage` | agent-operations operating model | 1.74 | 1.51 | 0.50 | 0.65 | 0.08 |
| 5 | `roster-check` | agent-operations models reference | 1.65 | 0.85 | 1.31 | 0.73 | -0.01 |
| 6 | `journal-route` | agent-operations closeout | 1.80 | 1.41 | 1.24 | 0.78 | -0.04 |
| 7 | `skill-suggest` | Claude Code UserPromptSubmit hook | 1.93 | 1.64 | 1.13 | 0.75 | -0.05 |
| 8 | `ideate-prerank` | saga ideate | 2.80 | 1.45 | 1.82 | 0.62 | -0.08 |
| 9 | `finding-confidence` | saga code-review | 1.96 | 1.53 | 0.84 | 0.60 | -0.09 |
| 10 | `session-status` | agent-operations tooling | 1.40 | 1.13 | 1.09 | 0.76 | -0.16 |
| 11 | `queue-bucket` | agent-operations session queue | 1.75 | 1.49 | 1.16 | 0.72 | -0.18 |
| 12 | `auto-labels` | mission-control sdlc_manager auto_label_rules | 1.80 | 1.71 | 1.26 | 0.78 | -0.21 |
| 13 | `engine-cmd` | fleet-core delegation_audit | 1.93 | 1.65 | 0.31 | 0.40 | -0.24 |
| 14 | `risk-prefill` | mission-control issue create | 1.39 | 1.31 | 0.98 | 0.72 | -0.24 |
| 15 | `issue-type` | mission-control triage | 1.71 | 1.84 | 1.02 | 0.72 | -0.30 |
| 16 | `turn-router` | per-turn model router | 2.60 | 1.98 | 1.73 | 0.65 | -0.34 |
| 17 | `lens-select` | saga/team-execution | 2.42 | 1.90 | 1.77 | 0.68 | -0.37 |
| 18 | `journal-nudge` | saga journal_nudge_hook | 1.61 | 1.51 | 0.87 | 0.53 | -0.42 |
| 19 | `handoff-check` | agent-operations lead handoff | 1.96 | 1.29 | 1.41 | 0.53 | -0.45 |
| 20 | `loop-turn` | saga loop | 1.96 | 1.61 | 1.74 | 0.71 | -0.46 |
| 21 | `spawn-tier-cli` | cross-harness CLI | 2.42 | 1.93 | 1.82 | 0.60 | -0.61 |
| 22 | `tier-choice` | saga plan + fleet-core tier_resolver | 2.37 | 1.98 | 1.93 | 0.63 | -0.65 |
| 23 | `workspace-stale` | agent-operations workspaces | 1.68 | 0.99 | 1.11 | 0.27 | -0.71 |
| 24 | `issue-flags` | saga parse_issue.py | 1.70 | 1.37 | 1.85 | 0.61 | -0.76 |
| 25 | `orch-preflight` | agent-operations unattended orchestration | 2.09 | 1.37 | 1.92 | 0.51 | -0.77 |
| 26 | `objective-field` | mission-control flow | 1.05 | 0.89 | 1.08 | 0.24 | -0.84 |
| 27 | `eval-harness` | fleet-core infrastructure | 2.26 | 2.15 | 1.40 | 0.42 | -0.97 |
| 28 | `review-shaped` | orchestrate orchestrate.py | 1.94 | 1.44 | 1.95 | 0.44 | -1.04 |
| 29 | `client-module` | fleet-core infrastructure | 1.87 | 1.88 | 0.86 | 0.17 | -1.14 |
| 30 | `workflow-shape` | saga/orchestrate workflow generation | 2.16 | 2.10 | 1.98 | 0.43 | -1.31 |
| 31 | `tool-intent-guard` | Claude Code PreToolUse hook | 2.10 | 1.91 | 2.84 | 0.58 | -1.44 |
| 32 | `skill-propagation` | harness skills dirs | 1.72 | 1.94 | 1.55 | 0.21 | -1.54 |

Composite = value × fit − 0.5 × effort − 0.6 × risk (weights are code-owned; changing them needs no re-inference). 32 ideas × 4 questions in 4 requests, 1598 ms total, 14977 input tokens (≈ $0.0006).
