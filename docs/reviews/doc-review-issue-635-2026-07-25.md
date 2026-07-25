---
title: "doc-review: #635 ship-ceremony base-branch resolution plan"
target: docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md
reviewed_revision: working tree at 474fd3cc
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/635
date: 2026-07-25
blocked: false
---

# doc-review — issue #635 ship-ceremony base-branch resolution

**Verdict: ready to drive `/work`.** Five findings, all fixed in place; nothing unresolved at P0 or
P1. The plan's core design — one resolver, ladder PR-then-manifest-then-refuse, refusal as a
pre-dispatch hazard — verified sound against live code. Every one of its ~20 `file:line` anchors is
true at `474fd3cc`, including the two claims most likely to be stale (`TRANSITIONS` ordering makes
`branch_delete` unreachable before `open_pr`, and `tests/test_ship_ceremony.py` carries exactly 47
`branch_delete`/`checkout_main` references).

Three of the five findings had propagated into
`…-spec.json`, which is what `/work` actually executes. Fixing the plan prose alone would have left
the executable artifact wrong, so the spec was patched, re-validated, and the workflow re-emitted.

## Findings

| ID | P | Finding | Status |
|---|---|---|---|
| D1 | P0 | U3 instructs changing `_do_checkout_main`'s return from `saga.get("branch")` to the resolved base, calling the current value "separately wrong". It is correct by design: that value is the `checkout_main` rollback-manifest entry's `branch`, consumed by `ship_undo._restore_pre_ceremony_checkout` (`ship_undo.py:370-395`), whose contract is restoring *the pre-ceremony checkout — the saga's own branch*. The change would make `current == branch` true immediately after `checkout_main` and turn that undo step into a permanent silent no-op. | fixed |
| D2 | P1 | U5 lists `tests/test_liveness_events.py` and `tests/test_team_execution_liveness.py` as saga drift pins to bump. They pin `fleet_core_version == "0.23.0"` (`:698`, `:179`, `:409`), not the saga version; only `tests/test_saga_plugin.py:48` pins saga. U5 declares no fleet-core bump, so both files must stay unmodified — editing them would assert a saga string against a fleet-core field and fail. | fixed |
| D3 | P1 | R6 and the U2 spec prompt name `pre_merge_sha` and instruct "rename the returned key accordingly". The real key is `pre_merge_main_sha`, a keyword argument of `ship_undo.append_entry` (`ship_undo.py:250`, passed at `ship_ceremony.py:805`) pinned by four test assertions. Renaming changes a cross-module signature on the undo path for zero behavioral gain — `ship_undo.py:14` records the field as audit-only forensic context `undo()` never consumes programmatically. | fixed |
| D4 | P1 | Defect E was scoped as corrupt rollback *evidence*, and its only test scenario asserted evidence shape. E is destructive: on a non-main-based PR the recorded `merge_sha` is `main`'s **unchanged, reachable** tip, so `ship_undo._undo_merge`'s `SHA_UNREACHABLE` guard (`ship_undo.py:360`) never fires — `git revert --no-edit` succeeds against an unrelated healthy commit on the default branch and pushes it. A red-first revert-safety scenario was added. | fixed |
| D5 | P3 | KTD3 cited the pre-dispatch gate span as `run()` `:770-786`; the `_RUNNERS[upcoming]` dispatch is at `:794`, outside the cited range. Corrected to name `detect()` `:773`, dispatch `:794`, `ship_undo.append_entry` `:796`, `saga.py save` `:809` — which strengthens KTD3 rather than weakening it, since the manifest append is also downstream of the refusal. | fixed |

## Applied fixes

**Plan** (`…-plan.md`): defect-table row E severity; U2 preamble and its E test scenarios (revert-safety
added); R6 field name plus an explicit no-rename decision; U3 behavior paragraph inverted to
preserve the return value, with an undo-contract regression pin added to its scenarios; U5 file list
and test expectation corrected with an explicit do-not-touch; KTD3 line anchors.

**Spec** (`…-spec.json`): five prompt patches across U2/U3/U5 (each asserted to match exactly once)
and two files dropped from U5's file list. Re-validated with `--require-receipts` → `OK … (5 units)`,
exit 0. Spend unchanged at 306.

**Workflow** (`…-workflow.js`): re-emitted. Six `parallel()` blocks of one agent each → **peak
concurrency 1**, inside the operator cap of 3. All six verifier spawns carry
`agentType: "saga:readonly-verifier"` + `isolation: "worktree"` + explicit `model: "opus"` /
`effort: "high"`.

## Verified sound (no finding)

- Resolution ladder (KTD2) — `_register_branch` writes `ceremony-branch:<branch>` at both push sites
  (`:418` `_do_commit`, `:863` `start()`) from push-time state, never re-stamped, so rung 2 is real.
- KTD3's refusal proof shape — `ceremony_hazards.detect()` at `:773` precedes dispatch, manifest
  append, and save. `acknowledgeable=False` matches the existing `MERGE_NOT_LANDED` precedent.
- KTD6's precedent — `{#ship-ceremony-operator-gate-526}`'s own "Revisit when" clause anticipates the
  typed confirmation payload. Migration surfaces confirmed at `work/SKILL.md:750-752` and
  `pr-continuation-loop.md:100-102`; no code callers outside `ship_ceremony.py` / `ship_undo.py`.
- KTD7's no-migration claim — `TRANSITIONS` (`:129-138`) orders `open_pr` at index 1 and
  `branch_delete` at index 6, so the refusal path is unreachable by a legitimate in-flight ceremony.
- R9's count — exactly 47 `branch_delete`/`checkout_main` references in `tests/test_ship_ceremony.py`.
- `tests/test_ceremony_hazards.py` and `scripts/check_release_surface_parity.py` both exist.

## Residual risk

The `_do_merge` return also carries `"branch": saga.get("branch")` (`:529`) into the rollback
manifest. Traced: no reverse handler consumes the `merge` entry's `branch` (`_undo_merge` uses
`merge_sha` and `_current_branch` only), so it is inert today — but it is a sixth rolling-field read
that would become load-bearing if a future undo handler reads it. Noted, not fixed; out of scope for
this plan.

R-live remains the thinnest leg by construction: KTD8's disposable local bare-repo origin exercises
real `git branch -d` and `git push origin --delete` against real refs, but `gh` stays stubbed, so the
rung-1 PR-authoritative path is proven only hermetically.
