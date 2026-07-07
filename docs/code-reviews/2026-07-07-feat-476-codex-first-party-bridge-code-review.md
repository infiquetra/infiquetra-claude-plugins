# Code review: feat/476-codex-first-party-bridge (#476)

**Target:** branch `feat/476-codex-first-party-bridge` vs merge base `40c8915` (origin/main)
**Reviewed revision:** `2e2b9dce1993cc3922fbdba988005c3a704da182` (9 commits: 7 workflow units + plan artifacts + drift-guard pin fix)
**Mode:** programmatic (called from the `/work` issue-476 continuation)
**Blocked:** YES — 1 P1 finding remains (docs-only fix)
**Linked:** issue `infiquetra/infiquetra-claude-plugins#476` · saga `issue-476` · plan `docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md` · doc-review `docs/reviews/doc-review-issue-476-2026-07-06.md` · execution `docs/plans/2026-07-06-codex-first-party-bridge-plugin-spec.json` (workflow run `wf_678f493b-524`, 16/16 agents, 9/9 verify-panel verdicts upheld)

**Verdict:** CLEAN after round 2 — the round-1 verdict was BLOCKED on finding #1 (P1); the operator directed fix-all, all 10 findings were fixed in-PR and re-verified (see "Round 2" below). Zero findings remain open.

## Scope check

Scope Check: CLEAN

- **Intent:** first-party `plugins/codex/` guarded delegate (agy-grammar mirror, `codex.delegation.v1`), supervised synchronous `codex exec` runner with evidence bundle + `bridge_receipt.v1` emission, enforced read-only reviewer / patch-capture coder modes, registry+dispatch rewire off `codex:codex-rescue`, marketplace retirement dereference, lifecycle proof (issue #476).
- **Delivered:** exactly that surface — 35 files, +4434/−43, all within plan scope. The saga/team-execution version-pin test update (`2e2b9dc`) is required by repo rule 6 (same-PR drift-guard consistency), not creep.

## Built-vs-planned audit (plan-completion)

All eight requirements and all seven implementation units verified in DIFF mode against the merge-base diff; the R7 live smoke additionally verified in EXTERNAL-STATE mode (it executed — codex auth present — rather than skipping).

| Item | State | Evidence |
|------|-------|----------|
| R1 first-party guarded delegate | DONE | `plugins/codex/scripts/codex_delegate.py` (1390 lines), schema `codex.delegation.v1` at `:42` |
| R2 enforced reviewer/coder modes | DONE | `MODES` `:48`, mode→sandbox argv `:306`, disposable clone `:14,:47`; `tests/test_codex_delegate_modes.py` 8 tests incl. pre-dirty no-false-positive |
| R3 evidence bundle + receipt seam | DONE | bundle writers `:835-1287`, `_bridge_receipt.emit_receipt` `:282`, `_USAGE_KEYS` token accounting `:311` |
| R4 timeout kill-tree + SIGTERM die-clean | DONE | `killpg` SIGTERM→SIGKILL `:470/:477`, die-clean handler `:489` (Bash-tool delivery vector noted `:491`); real-subprocess lifecycle tests |
| R5 registry + dispatch rewire | DONE | `engine-registry.yaml:27/:58` `via: codex:delegate`, corrected recipe `-c model_reasoning_effort=high\|xhigh`, `write_capable: false` retained |
| R6 retirement dereference | DONE | zero live `codex-rescue` references; 3 README mentions are the retirement runbook itself; `openai-codex` marketplace entry removed |
| R7 lifecycle + gated live conformance | DONE | `tests/test_codex_delegate_lifecycle.py` 4 tests (terminal bundles, whole-tree kill via grandchild-pid poll, killed-mid-run); live smoke gated on `codex login status` exit 0 — ran and passed locally |
| R8 shim + drift-guard move | DONE | `cmp` byte-identical with agy shim; `codex-bridge` in `IN_REPO_EMITTERS` (`tests/test_bridge_receipt_drift.py:40`); emit-only-when-launched `_supervised_receipt` `:269-282`; moved in the same commit as the scaffold (`bcfa42a`, KTD6) |
| U1–U7 | DONE | 1:1 commit mapping `bcfa42a`/`f01b95d`/`985788f`/`51bdbe9`/`ad433f1`/`813a9a5`/`3c2fc22`; refute-panels on U2/U3/U6 upheld 9/9 with examined-SHA quoting |

## Gates at review time

pytest 2472 passed / 1 skipped (the skip is Wave A's pre-existing `OLLAMA_API_KEY`-gated smoke, `tests/test_engine_bridge_http.py:378`) · ruff clean · mypy clean (156 files) · bandit: no findings introduced by this diff (new `plugins/codex/` contributes 6 LOW subprocess advisories, same class as agy).

## Review lenses and validation

Six lenses ran as read-only sandboxed reviewers (fan-out capped at 3 concurrent): correctness, security, testing, maintainability, reliability, adversarial. Every lens materialized and quoted the examined SHA `2e2b9dc`. Stage-A merge deduped one cross-reviewer agreement (correctness + reliability on finding #2). Stage-B independent per-finding validators: 10 dispatched (≤15 cap), **10 confirmed, 0 rejected/dropped**.

## Findings

### P1 — must fix before PR

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 1 | plugins/codex/scripts/codex_delegate.py:7 (+README.md:23-25, CHANGELOG.md 0.1.0) | Docstring/README/CHANGELOG still claim the supervised runner "lands in follow-on units" and the wrapper "exits nonzero rather than launching" — but `main()` (`:1377`) launches a live `codex exec` subprocess by default. A reader treats invocation as a safe no-op. | maintainability (validated) | 90 | manual -> human |

### P2 — should fix

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 2 | plugins/codex/scripts/codex_delegate.py:485 | `_kill_process_tree` return (`shutdown_incomplete`) discarded at all call sites (`:499,:630,:650,:654`); an unkillable tree is recorded as clean `timeout`/`no_output` and a receipt is emitted as if shutdown succeeded. agy captures and maps it (`agy_delegate.py:785-786`) — parity omission; the status is dead vocabulary. | correctness + reliability (validated) | 90 | manual -> human |
| 3 | plugins/codex/scripts/codex_delegate.py:452 | No test asserts `-m` presence/absence keyed off `envelope.model`; the only model-bearing test checks `command.json` exists, not its argv. A `-m` regression passes the suite. | testing (validated) | 85 | safe_auto -> review-fixer |
| 4 | plugins/codex/scripts/codex_delegate.py:502 | No large-prompt stress test for the stdin pipe-buffer deadlock the `_feed_stdin` thread exists to prevent; every fake-codex fixture reads stdin first, so a synchronous-write regression passes. | testing (validated) | 80 | safe_auto -> review-fixer |
| 5 | plugins/codex/scripts/codex_delegate.py:579 | Die-clean SIGTERM/SIGINT handler installed only inside `run_codex_supervised`; a signal during clone setup, token parse, diff-scan, or bundle writes hits default disposition — no `result.json`, clone teardown `finally` skipped (default SIGTERM does not unwind). agy has no signal handling at all (codex leads; span too narrow). | reliability (validated) | 80 | manual -> human |
| 6 | plugins/codex/scripts/codex_delegate.py:332 | `_write_json` is bare `write_text` — no tmp+`os.replace` — for all bundle files incl. `result.json`; SIGKILL/OOM mid-write leaves torn JSON with no distinct downstream handling. Test fixtures write pidfiles atomically; production does not. Same pattern in agy (`:1220`). | reliability (validated) | 75 | safe_auto -> review-fixer |
| 7 | plugins/codex/scripts/codex_delegate.py:744 | Transcript streamed to disk with byte counters but no cumulative cap (only wall-clock/no-output timers, and spam resets no-output), then `parse_token_usage` slurps the whole file into memory. 1–10 MB/s for the 900s ceiling = 0.9–9 GB on disk then in RAM. Same unguarded pattern in agy (`:1369`). | adversarial (validated) | 75 | manual -> human |
| 8 | plugins/codex/scripts/codex_delegate.py:961 | Reviewer non-mutation scan excludes the entire `.claude` tree (`:(exclude).claude`), not just this run's bundle dir — the sandbox-drift defense is blind to `.claude/settings.json`, hooks, other runs' evidence. Docstring justifies excluding only the run's own bundle. | adversarial (validated) | 75 | manual -> human |
| 9 | plugins/codex/scripts/codex_delegate.py:1290 | `except OSError` is the only guard around the post-launch span; a non-OSError from receipt emission (e.g. `bridge_receipt.py:75` `ValueError`) or JSON serialization crashes uncaught → launched run ends with a non-terminal bundle. Identical narrow pattern in agy — fleet-wide, unmitigated. | reliability (validated) | 75 | gated_auto -> review-fixer |

### P3 — discretionary

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 10 | plugins/codex/scripts/codex_delegate.py:1095 | `new_paths` is a pure path-set difference — a fail-open run that REVERTS pre-existing operator dirt (or changes its content while still dirty) evades the auto-flag. Mitigated: both porcelain snapshots persist in `diff-scan.json`, so it is auditable after the fact. | adversarial (validated) | 75 | advisory -> human |

## Coverage

- **Suppressed below the confidence gate:** 10 across lenses (security 1: operator-sourced `--run-id ..`; correctness 2: dead `fallback_suspected`/`checks_failed` vocabulary, receipt argv unsanitized-but-secret-free; reliability 1: `_run_git` timeout; testing 3: file-existence-assertion nitpicks, unsubstantiated order-dependence; adversarial 3: submodule/LFS clone edge, codex sandbox home-dir scope, old-codex flag rejection indistinguishable from task failure).
- **Attack paths verified defended (with defending lines):** run-id collision → `exist_ok=False` fails clean (`:1153`); missing codex binary → error status (`:543-557`); clone strips all remotes + clones committed HEAD only (`:1019-1030,:992`); coder never gets the live tree as workdir (`:566,:1216`); no shell=True/eval anywhere; prompt via stdin never argv; no secret material in any persisted artifact.
- **Testing gaps:** the unkillable-tree path (`:485`) is uncovered — exactly finding #2's subject; `-m` argv and large-prompt stdin (findings #3–4).
- **Fleet-parity note:** findings #6, #7, #9 (and #2's inverse) are shared with or inherited from `plugins/agy/scripts/agy_delegate.py` — fixing them only in codex creates intentional divergence; an agy parity follow-up issue is the clean route.
- **Not deep-verified:** `engine_dispatch.py` `_assert_payload_preserved` / via-keying (adversarial lens explicitly declined to assert a defense it did not run); codex `--json` usage-event field shapes beyond the tolerant-parse contract (carried from doc-review).

## Routing

- Finding #1 (P1, docs-only): fix in this PR before opening it — `/work` gates hard on P1.
- Findings #3, #4, #6 (safe_auto) and #9 (gated_auto): concrete minimal fixes exist; operator chooses fix-now vs follow-up.
- Findings #2, #5, #7, #8 (manual -> human): design decisions (status mapping, handler span, byte caps, exclusion narrowing) — operator scopes this PR vs follow-up issues; agy parity applies to #2/#6/#7/#9.
- Finding #10 (advisory): report-only.

## Round 2 — operator-directed fix-all (2026-07-07)

Operator chose "fix all 10 in this PR" + an agy-parity follow-up issue. Every finding fixed and re-verified:

| # | Fix | Verified by |
|---|-----|-------------|
| 1 | Module docstring, README Current Status, and CHANGELOG rewritten to the shipped surface; launch-by-default called out explicitly in all three | doc read-back; CHANGELOG now documents U1–U7 |
| 2 | `shutdown_outcome = _kill_process_tree(...)` captured at all loop kill sites; `shutdown_incomplete` overrides the timeout class and reaches `result.json` + the projection summary | `test_unreapable_tree_surfaces_as_shutdown_incomplete` |
| 3 | `-m` presence/absence asserted against `command.json` argv keyed off `envelope.model` | `test_supervised_command_includes_model_flag_only_when_set`, `..._omits_model_flag_when_absent` |
| 4 | Large-prompt (256 KiB) vs stdout-flood-first fake proves the threaded stdin writer prevents the pipe deadlock | `test_supervised_large_prompt_does_not_deadlock_stdin` |
| 5 | `DieCleanInterrupt` + `_bundle_die_clean_handler` installed across the whole `create_supervised_bundle` span (restored in `finally`); signal outside the launch window now unwinds through clone teardown and writes a terminal `result.json` | `test_signal_in_post_run_window_still_ends_terminal` (delivers a real SIGTERM from the post-run seam; asserts handler restoration) |
| 6 | `_write_json` writes tmp + `os.replace` (atomic) for every bundle JSON | full suites re-run green |
| 7 | `MAX_OUTPUT_BYTES` (128 MiB) cumulative cap kills the tree with a named error; `parse_token_usage` streams line-by-line; last-message read bounded by `MAX_LAST_MESSAGE_BYTES` | `test_output_byte_cap_kills_runaway_spam` |
| 8 | Porcelain exclude narrowed from `.claude` to `.claude/codex/runs` (any run — concurrent siblings must not false-positive); settings/hooks/other-plugin state now visible to the scan | `test_reviewer_dot_claude_mutation_outside_runs_is_flagged` |
| 9 | `except OSError` joined by `except Exception` (and the dedicated `DieCleanInterrupt` arm), all funneled through `_finalize_failed_bundle` which best-effort writes a terminal `result.json` | `test_receipt_emission_failure_still_ends_terminal` |
| 10 | `reverted_paths` + `reversion_suspected` audit signals added to `diff-scan.json`, `ReviewerScan`, and the command `mode_surface`; deliberately NOT folded into `mutation_detected` | `test_reviewer_reversion_of_operator_dirt_is_surfaced` |

Design notes: #8 excludes the runs ROOT (not the single run-id the round-1 suggestion named) so concurrent sibling runs cannot false-positive each other; #10 stays an audit signal because an operator cleaning their own tree mid-run must not hard-fail a legitimate review.

**Gates after round 2:** pytest 2481 passed / 1 skipped (pre-existing Ollama-keyed smoke) / 0 failed; ruff clean; mypy clean (156 files); bandit `plugins/codex/` LOW 6 / MEDIUM 0 / HIGH 0. One transient live-smoke failure during a loaded full-suite run did not reproduce (passed twice in isolation and in the clean full re-run); CI is unaffected (the smoke skips without codex auth).

Review complete
