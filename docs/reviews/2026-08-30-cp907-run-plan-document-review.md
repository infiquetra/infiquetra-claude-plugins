---
kind: doc-review
target: docs/plans/2026-08-30-agent-launcher-907-run-plan.md
classification: plan, issue-derived
reviewed_revision_commit: 3b2b7083fdda8e39e213b5f4acf9f8301d60dd52
reviewed_revision_plan_sha256_cycle1: adcf013948d37153c45e58b81da3bfcfd28c35ee9f0d7c6ccf13b7d15e1f15fb
reviewed_revision_plan_sha256_closure: ffc78817c3d32a250fb9a7e6a180f7d6793395fa1033d9d7dd753ddf6ce67558
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/907
blocked: false
outcome: ready
applied_fixes: none-in-this-session
pass: findings-closure
---

# Document review — issue 907 Agent Launcher run plan

All fourteen cycle-1 findings are closed. The repaired plan can drive implementation without the implementer inventing a write path, a receipt channel, or a discriminator.

This file is the same review artifact. The block below is a findings-closure pass over `D1`–`D14`, not a second broad review. No new findings. No plan, source, or test edits.

| field | value |
|---|---|
| target path | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md` |
| cycle-1 revision | working-tree HEAD `3b2b7083fdda8e39e213b5f4acf9f8301d60dd52` (exactly `origin/main`); plan SHA-256 `adcf013948d37153c45e58b81da3bfcfd28c35ee9f0d7c6ccf13b7d15e1f15fb` |
| closure revision | same HEAD `3b2b7083`; repaired plan SHA-256 `ffc78817c3d32a250fb9a7e6a180f7d6793395fa1033d9d7dd753ddf6ce67558` (87.3 KB) |
| classification | Plan, under `docs/plans/`, issue-derived. Not reclassified. |
| review type | Cycle 1: one broad Saga Document Review. This pass: findings-closure only. No external-reviewer panel. |
| linked issue | [infiquetra/infiquetra-claude-plugins#907](https://github.com/infiquetra/infiquetra-claude-plugins/issues/907) |
| children | 890, 897, 896, 889, 888, 887, 880 |
| blocked status | **no** — every P1 is closed |
| applied fixes | none in this session. Planning role repaired the plan. This pass only updates statuses. |
| review artifact path | `docs/reviews/2026-08-30-cp907-run-plan-document-review.md` |
| readiness verdict | `ready` |
| override rationale | n/a |

## Closure summary

Fourteen of fourteen closed. Two original counts were short and are corrected below; the repairs already used the wider counts.

| id | priority | status | closing evidence (one line of specified behaviour) |
|---|---|---|---|
| D1 | P1 | closed | Plan:124–142 and stop 1: the guard keys on `session_owned(unit)` being false; amendment recorded at issue 897 comment 5469528122 |
| D2 | P1 | closed | Plan:471–500: `"permission"` stays in `unconfirmed`; argv confirmation is `permission_resolved.confirmed_from`; `SKILL.md:32` is rewritten in L3 and L7 must preserve it |
| D3 | P1 | closed | Plan:710–712: `account_confirmed, account_evidence = verify_unit_account(...)` then `receipt["account_evidence"] = account_evidence` |
| D4 | P1 | closed | Plan:620–623: omitted `since` keeps today's fallback; `launch` is the only path that passes a floor. Five exposed tests, not four — see correction |
| D5 | P1 | closed | Plan:905–919: inline JSON is `lstrip()[:1] in ("{", "[")`, so `_load_receipt("[1, 2]")` still reaches `"must be a JSON object"` |
| D6 | P1 | closed | Plan:1151–1157: pre-L4 checkpoint row runs `pane_account_label` on the throwaway Claude tab and stops if it returns `None` |
| D7 | P1 | closed | Plan:1193–1229: three live `>=1.0.0` floor pins move; three `"1.0.0"` literals are named as non-pins — see correction |
| D8 | P2 | closed | Plan:164, :430, :800–802: 124 is at `:288`; `--permission` at `:1284`; close sites at `:894`, `:927`, `:936`, `:949`, `:1257` |
| D9 | P2 | closed | Plan:311–316: `PANE_INPUT_READ_SECONDS = 5.0` is the pane-read timeout |
| D10 | P2 | closed | Plan:1148: L3 checkpoint accepts `permission_resolved.confirmed_from == "launch_argv"` and forbids a Herdr posture read-back |
| D11 | P2 | closed | Plan:1204–1206 and the release file list: Orchestrate `SKILL.md:84` rises to `>=1.1.0` |
| D12 | P3 | closed | Plan:67: "whose six tests check plugin metadata" |
| D13 | P3 | closed | Plan:268–273: `read_pane` returns raw text; `strip_ansi` is the caller's job at `:652` |
| D14 | P3 | closed | Plan:800–802: five call sites at 894, 927, 936, 949, and 1257 |

No P0 findings. No finding left open.

## Corrections to the original counts

**D4 affects five tests, not the four cycle-1 named.** Cycle 1 cited `TestPostLaunchAccountVerification` at `tests/test_orchestrate_account.py:310-501` (four cases: 310, 350, 401, 449). That set is right and incomplete. The fifth is `test_cmd_go_marks_unit_account_mismatch_on_verified_mismatch` at line 554: it drives the real `launch` through `cmd_go`, uses `pane_reads_nothing`, and its fake wrapper writes `session.jsonl` during the create. Verified against the test body at 573–580. The compatible `since=None` default keeps the four direct `verify_unit_preflight` cases green; `TRANSCRIPT_MTIME_SLACK_SECONDS` is what keeps the fifth from comparing a same-instant write below the floor. The repaired plan already names all five (plan:626–629, :701–704, :1314–1316).

**D7's non-pins are three, not one.** Cycle 1 correctly named the missed live pin (`test_orchestrate_keeps_its_agent_launcher_floor`) and correctly excluded `_install_plugin(..., "1.0.0")` as a cache directory name. Two further `"1.0.0"` literals are also non-pins and must not be moved: `tests/test_sync_marketplace.py:68` asserts the version of a synthetic fixture plugin named `alpha` written at line 59; `tests/test_release_triad.py:211-212` assert the version of a synthetic fixture plugin named `myplugin` written at line 188. Neither reads the agent-launcher manifest. The two `>=1.0.0` dictionaries at `tests/test_plugin_manifest_loader_contract.py:81` and `:95` are likewise shape-check fixtures, not live pins. Live pins remain: two version-equality assertions plus three floor assertions.

## Four planner claims

1. **D4's fifth test is real.** `test_cmd_go_marks_unit_account_mismatch_on_verified_mismatch` calls `orchestrate.cmd_go`, which reaches `launch`. The fake `run` writes `personal_root / slug / "session.jsonl"` inside the wrapper arm, after `created_at` would have been captured. A same-instant or 1-second-floored mtime can compare below a strict floor. Accepted.

2. **`TRANSCRIPT_MTIME_SLACK_SECONDS = 1.0` is the right smallest portable fix.** The same-instant failure is real on a filesystem that stores mtime at 1-second granularity: `created_at` at `T.9` and a create-time write stored as `T.0` fail `st_mtime >= since`. A tighter slack (0.5) still loses that case. `>= since` with no slack already accepts an exact equality and a nanosecond-later write; it does not absorb flooring. One second of lookback does not re-open the defect, which is leftover transcripts minutes or hours old. The worker is forbidden to raise the constant (stop 3). Proportional for a single-operator tool. Accepted; not a new finding.

3. **D7's extra non-pins are real.** `alpha` and `myplugin` fixtures confirmed. Accepted. See the count correction above.

4. **D2's receipt channel is coherent.** `"permission"` stays in `requested_only` and never enters `confirmed_against_herdr`, so `test_herdr_readback_receipt_separates_confirmed_from_requested` (`assert "permission" in receipt["requested_only"]`, `assert "permission" not in receipt["confirmed_against_herdr"]`) stays green on the no-argv path. `permission_resolved.confirmed_from` is `"launch_argv"` only when argv was supplied, else `None`. `SKILL.md:32` is rewritten in L3 so permission is no longer grouped with model as Herdr-`requested_only`, and L7 is told to preserve that sentence. The skill and the receipt no longer contradict.

## D2, D3, D4, D6 together

The four repairs describe one verification block, not two incompatible receipts.

`verify_unit_preflight` gains both keyword-only defaults (`argv` from L3, `since` from L4). The receipt keeps `"permission"` as the request and puts argv confirmation in `permission_resolved`; it keeps `"account"` as the request and puts proof in `account_evidence`. Account may still enter `confirmed_against_herdr` when statusline or a qualified transcript proves it; permission may not. The L3 checkpoint row asks for `confirmed_from == "launch_argv"` and forbids a Herdr posture read-back. The D6 row is a different observation on the same throwaway Claude tab, taken before L4 lands. `check_unit_account` keeps its pinned two-tuple; evidence leaves through `evidence_out` and `verify_unit_account`'s `(confirmed, evidence)` return. No two repairs write the same key two ways.

## Findings (cycle-1 text, closure status)

Cycle-1 recommended repairs are retained so the ledger stays traceable. Status and closing evidence are authoritative.

### D1 — Issue 897's `reused=true` AC is wrong; the plan's ownership key is right; the amendment text is missing

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:124` |
| closing evidence | Guard keys on `session_owned(unit)` being false. Amendment recorded: https://github.com/infiquetra/infiquetra-claude-plugins/issues/897#issuecomment-5469528122. Stop 1 is SETTLED. |

### D2 — L3 records argv-confirmed permission as `confirmed_against_herdr` and leaves `SKILL.md:32` claiming `requested_only`

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:471` |
| closing evidence | `"permission"` stays in `unconfirmed`. Channel is `permission_resolved.confirmed_from`. `SKILL.md:32` rewritten in L3; L7 must preserve it. |

### D3 — L4 never specifies how `account_evidence` reaches the receipt

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:710` |
| closing evidence | `account_confirmed, account_evidence = verify_unit_account(...)` then `receipt["account_evidence"] = account_evidence`. No ad-hoc `unit` attribute. `check_unit_account` keeps its two-tuple via `evidence_out`. |

### D4 — L4's `since=None` default breaks `tests/test_orchestrate_account.py`; coexistence omitted that file

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:620` |
| closing evidence | Omitted `since` keeps today's fallback. Floor is passed only from `launch`. File is in coexistence and in the green check. Five tests, not four. |

### D5 — L6's loader and `test_non_object_json_keeps_its_message` cannot both be true

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:919` |
| closing evidence | `elif raw.lstrip()[:1] in ("{", "[")` so `[1, 2]` still hits `"must be a JSON object"`. |

### D6 — L4's blast-radius gate runs before L4 and does not observe whether the statusline paints

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:1151` |
| closing evidence | Checkpoint row "Account statusline paints (pre-L4 gate)": `pane_account_label` on the throwaway Claude tab; `None` stops the run before L4. Worker may not widen `since` or raise the slack constant. |

### D7 — Release commit misses the live `>=1.0.0` pin in `tests/test_plugin_manifest_loader_contract.py`

| field | value |
|---|---|
| priority | P1 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:1198` |
| closing evidence | Three floor pins listed, including `:108`. Three `"1.0.0"` literals named as non-pins (`_install_plugin`, `alpha`, `myplugin`). |

### D8 — Several `path:line` citations do not land where the plan says they land

| field | value |
|---|---|
| priority | P2 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:164` |
| closing evidence | 124 at `:288`; `--permission` at `:1284`; closes at `:894`, `:927`, `:936`, `:949`, `:1257`. |

### D9 — L2's pane-read timeout is an unnamed "short timeout"

| field | value |
|---|---|
| priority | P2 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:311` |
| closing evidence | `PANE_INPUT_READ_SECONDS = 5.0` passed as `timeout=` on the pane read. |

### D10 — L3 checkpoint asks for Herdr statusline bypass evidence the plan itself says Herdr does not publish

| field | value |
|---|---|
| priority | P2 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:1148` |
| closing evidence | Passing evidence is `permission_resolved` tokens plus `confirmed_from == "launch_argv"`. No Herdr posture read-back. Visual bypass glance is optional, not evidence. |

### D11 — Orchestrate `SKILL.md` still documents `>=1.0.0` and is not on the release file list

| field | value |
|---|---|
| priority | P2 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:1204` |
| closing evidence | `SKILL.md:84` rises to `>=1.1.0` and is on the release-commit file list. |

### D12 — Finding 1 is correct; the release-surface file has six tests, not five

| field | value |
|---|---|
| priority | P3 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:67` |
| closing evidence | "whose six tests check plugin metadata". Behaviour stays in the contract module. |

### D13 — `read_pane` does not strip styling; its OpenCode caller does

| field | value |
|---|---|
| priority | P3 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:268` |
| closing evidence | `read_pane` returns raw text; `confirm_opencode_variant_selected` strips via `strip_ansi`. |

### D14 — L5's close-call line numbers and "two failure paths" count are wrong

| field | value |
|---|---|
| priority | P3 |
| status | closed |
| source anchor | `docs/plans/2026-08-30-agent-launcher-907-run-plan.md:800` |
| closing evidence | Five sites: 894, 927, 936, 949, 1257. L5 edits none of them. |

## Cycle-1 rubric review (unchanged; not re-run)

Issue-phase cores and extras were scored in cycle 1. This pass did not re-score them. Residual rubric notes from cycle 1 are closed by the repairs above (L4 write path, L6 array payload, 897 amendment, receipt channel, missed test files).

## Residual risk

Issue 900 remains a live stop: it still adds a field to the same `Unit` dataclass. That is a named plan stop, not an open review finding.

The one-second transcript slack admits a file at most one second older than `created_at`. That is not the stale-worktree defect. Stop 3 forbids the worker from raising the constant.

No source, test, release surface, or the plan file was edited in this pass. No commit or push was made.
