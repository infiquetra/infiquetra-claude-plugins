---
kind: doc-review
target: docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md
classification: plan, issue-derived
reviewed_revision: e2470964e66a37673cd072378e0dc2dd08c75e84
reviewed_revision_plan_sha256: 8031b1de6725c6a53153605baecffd497d2a05a60e265127d974ea1a7d7b4a93
prior_review: docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review-r2.md
prior_review_commit: 1c56e270
authoritative_artifact: docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/907
blocked: false
outcome: ready
applied_fixes: none
pass: findings-closure
---

# Document review r3 — issue 907 terminal-validation repair plan

D9 is closed. The rebound kill-list observers distinguish the mutants they name. The plan can drive implementation.

| field | value |
|-------|-------|
| target path | `docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md` |
| reviewed revision | `e2470964e66a37673cd072378e0dc2dd08c75e84` (clean tree except this artifact) |
| plan SHA-256 | `8031b1de6725c6a53153605baecffd497d2a05a60e265127d974ea1a7d7b4a93` |
| prior review | `docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review-r2.md` at `1c56e270` (byte-identical to that commit) |
| classification | Plan, under `docs/plans/`, issue-derived. Not reclassified. |
| review type | Narrow closure of D9 and of the observer-level rebinding. No external-reviewer panel. Report-only; no dispatch. |
| linked issue | [infiquetra/infiquetra-claude-plugins#907](https://github.com/infiquetra/infiquetra-claude-plugins/issues/907) |
| blocked status | **no** |
| applied fixes | none. Operator contract forbade editing the plan. Round-1 and round-2 artifacts left byte-identical. |
| review artifact path | `docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review-r3.md` |
| readiness verdict | `ready` |
| override rationale | n/a |

## Applied fixes

None in this session. The planner repaired the plan at `e2470964`. That commit touches only the plan file.

## Readiness summary

Ready. D9 is closed in place, not moved. Both halves of `not session_owned(unit) or used_pane` have a named test that fails when that half is dropped. Each rebound mutant was checked against the source it claims to observe; none of those pairs is a green-on-mutant.

No new finding. Nothing advisory that should delay implementation.

## Closure of D9

| id | priority | status | closing evidence |
|---|---|---|---|
| D9 | P1 | closed | Plan:324 replaces the dead ownership-half mutant with `if True:` on the pre-send predicate. `test_freshly_created_pane_takes_no_inspection_path` then records one ANSI read (`plugins/agent-launcher/tests/test_launcher_contract.py:636-649`). The `used_pane` half is not observable on a fresh launch and is bound by U6's `used_pane=False` redelivery mutant (plan:309, :406). |

The two halves, when dropped:

| Dropped half | Remaining predicate | Observer that fails |
|---|---|---|
| `not session_owned(unit)` | `used_pane` | U3: revert to `if used_pane:` fails the unowned-after-agent-prompt test. U4: an unowned first send then does no read, so `test_empty_reused_box_is_prompted_exactly_as_today` records zero. |
| `used_pane` | `not session_owned(unit)` | U3: revert to `if not session_owned(unit):` fails the owned-typed test. U6: `redeliver` seeded `used_pane=False` sends on an owned still-staged pane. |

U4's `if True:` is the kill for "owned fresh stays uninspected." That is the repair D9 asked for, not a relocation of the bind.

## Observer-level sweep

Each rebound pair was tested against the code at this tree, not against the planner's report.

| Mutant | Named observer | Distinguishes from the original? |
|---|---|---|
| U4 `if True:` on pre-send | `test_freshly_created_pane_takes_no_inspection_path` | Yes. Owned create currently asserts zero ANSI reads (`plugins/agent-launcher/tests/test_launcher_contract.py:636-649`). |
| U1 C18 drop rule class | Bordered-box-with-rule edge (`│ ❯ x │` / `│    ──── │` / `│   y │`) | Yes. `─` is not in `_LEADING_BORDER_GLYPHS` (`composer.py:37-39`). Live Claude captures cannot see this; the plan says so. After strip, four spaces put the dashes past the marker column, so without a rule class the row continues and the text becomes `x────y`. |
| U1 C20 drop unbordered column check | `test_first_noncontinuation_terminates_the_composer_block` | Yes. That dump is `❯ draft` then `ordinary output` (`plugins/agent-launcher/tests/test_launcher_contract.py:789-791`). KTD1's bordered continuation no longer distinguishes the artifact's old C20 input. |
| U1 C23 / C2 / C13 | Two-blank idle shape; `test_status_footer_after_blank_is_not_counted_as_staged_input` (`ninechars` vs `ninecharsmodel footer status`); `test_an_empty_live_box_below_an_echo_reads_empty` | Yes. Each named assertion changes under that mutant and not under the repaired rule. |
| U5 restore `abs(hash(path))` | Single-process digest-form assertion | Yes. Two-process identity is not a deterministic kill when `PYTHONHASHSEED` is set. A digest equality fails `hash` in every environment. |
| U7 delete dedup | Two-pass `; ` close | Yes. One writer cannot double-append on a single pass. A second `reap` of the same failed close is the observation. |
| U8 O3 `re.search` | Compound range `>=1.2.1,<2.0.0` | Yes. `re.fullmatch(r">=(\d+\.\d+\.\d+)", …)` is the live parser (`orchestrate.py:1524`). Caret and bare fail both `fullmatch` and `search`. `search` on the compound range yields `1.2.1` and `roster` runs. No existing `>=1.2.1` pin sees this. |
| U8 O16 / O17 | Two-root discovery, `1.9.0` raises, expect `1.10.0` | Yes. Numeric sort then `matches[-1]` is `1.10.0`. `matches[0]` and lexical `sorted` both pick `1.9.0` (`"1.10.0" < "1.9.0"`). The existing single-root test never enters `CLAUDE_PLUGIN_ROOT` (`orchestrate.py:1574-1586`); its parent walk already resolves the sibling. |
| U8 O18 delete `CLAUDE_PLUGIN_ROOT` branch | Same two-root layout | Yes. Parent walk has no sibling. The script returns `None`. `roster` gets the missing message. |
| U8 O21 drop `AGENT_LAUNCHER_ROOT` exit | Bad-override message text | Yes. Exit status stays non-zero. The live missing-file message is `does not contain skills/agent-launcher/scripts/launcher.py` (`orchestrate.py:1563-1566`). Falling through hits `cannot verify agent-launcher manifest` (`orchestrate.py:1548`). |
| U8 O5 return `False` on floor failure | Matrix liveness-route cell | Yes. Below-floor `status` must record `herdr agent list` and print no companion fault. An uningested companion prints the fault and records no `agent list`. Exit 0 alone would not see this. |

U2, U3, U6, U9 and U10 were not rebound in this commit. Their existing named observers still distinguish: visible-versus-unstyled; the three resend predicate reverts; `redeliver` create count and `used_pane=False`; snapshot restore and roster line; unowned-draft versus owned-without-read.

O16 and O17 share one observer and one failure mode (select `1.9.0`). Each is still distinct from the original (`1.10.0`). That is enough.

## Remaining findings

None.

## Residual risk

CORR-01's styled wrap is still constructed. Grok, Agy and Qwen still have no capture. Decision 1 still gates the dispatch-path half of R5. Redelivery's `since=None` floor and the repeated OpenCode picker remain stated trades.

Identifiers `D1`–`D9` are this document-review's keys. The round-1 artifact, the round-2 artifact, every review JSON, cycle state, and the append-only evidence ledger were not modified.
