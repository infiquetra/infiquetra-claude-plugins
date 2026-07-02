---
title: Code review — Team-spawn residency guard (#289)
date: 2026-07-02
issue: infiquetra/infiquetra-claude-plugins#289
branch: feat/289-team-spawn-residency-guard
plan: docs/plans/2026-07-02-team-spawn-residency-guard-plan.md
work-session: docs/work-sessions/2026-07-02-team-spawn-residency-guard.md
mode: programmatic (called by /work)
---

# Code review — Team-spawn residency guard (#289)

Two Opus 4.8 review rounds (operator-directed model), plus one self-applied follow-up fix
verified inline. Persisted by `/work` per the programmatic-mode contract (the review itself
writes zero files).

## Round 1 — full review, reviewed SHA `a08ed87`

**Verdict: NOT BLOCKED — 0 P0, 0 P1, 2 P2, 0 P3.**

Built-vs-planned: Scope Check CLEAN. All three Implementation Units (U1 hook+tests, U2
hooks.json registration, U3 release triad) classified DONE. R1–R13 and KTD1–KTD6 honored;
`load_trigger_set` against the real registries confirmed exactly 18 agents, none of the 7
excluded roles.

Findings (both `safe_auto`, confidence 100, reliability):

| # | Priority | Finding |
|---|---|---|
| F1 | P2 | `main()` crashed (`AttributeError`, exit 1) on valid-JSON-non-object stdin (`123`, `[1,2,3]`, `null`) — `payload.get()` ran unguarded after a successful parse. Violated the hook's own R9 "malformed envelope → exit 0" contract. Non-blocking: exit 1, not 2, so the spawn still proceeded — the core "never block/deny/mutate" invariant held throughout. |
| F2 | P2 | `load_trigger_set` read registries under `contextlib.suppress(OSError)`, but invalid UTF-8 raises `UnicodeDecodeError` (a `ValueError` subclass, not `OSError`) — uncaught. Violated R10/D5 "unreadable registry contributes nothing." |

Core safety invariant ("warn-only, never blocks/denies/mutates") empirically verified HELD:
every reachable `main()` exit path is `sys.exit(0)`; the advisory carries only
`hookSpecificOutput.additionalContext` — no `permissionDecision`, no `deny`, no `updatedInput`.

## Round 2 — delta review, `a08ed87..17eafc7`

**Verdict: PASS.** Both F1/F2 fixes confirmed exact (one-line guard + broadened exception
suppression), two new regression tests added, no scope creep, no new P0–P3 in the delta. Full
suite 1751 passed; ruff/format/mypy clean.

Flagged one **out-of-delta, non-blocking** observation: `main()` passes `payload.get("cwd")`
straight to `_find_references_dir`, which called `Path(cwd)` unconditionally when truthy — a
non-string `cwd` (int/list/dict) would raise `TypeError`, uncaught. Pre-existing since U1, not
introduced by the F1/F2 fix commit, explicitly framed as "flag for a future hardening pass"
rather than a blocking finding.

## Follow-up fix (self-applied, same pattern, not re-reviewed by a third Opus round)

Fixed immediately — same bug class as F1/F2 (an envelope field reaching a type-sensitive
call unguarded), same one-line-guard shape, found by the same review lineage:
`isinstance(cwd, str)` required before constructing `Path(cwd)` in `_find_references_dir`.
One parametrized regression test added (`123`, `["a"]`, `{"x": 1}` as `cwd`). Self-verified
via the full gate rather than a third Opus spawn — two full Opus passes already covered this
file end-to-end and the fix is a direct instance of an already-approved fix pattern.

**Reviewed SHA for this fix: `fdffed2`** (one commit past the delta review's `17eafc7`) — this
commit has not itself been reviewed by a fresh Opus pass. Flagged transparently to the operator
rather than silently declared clean or silently re-spawning a third review round.

## Overall gate status

**Blocked: NO.** 0 P0/P1 across both formal review rounds. All findings from both rounds are
fixed, tested, and gate-verified (pytest full suite, ruff, ruff-format, mypy, `test_release_triad`).
The one unreviewed commit (`fdffed2`) is a single isinstance guard, self-verified, same shape as
two already-Opus-approved fixes.

## Test evidence (as of `fdffed2`)

Full suite: **1754 passed**. `ruff check` + `ruff format --check` clean on
`plugins/saga/hooks/`. `mypy plugins/ scripts/ tests/ --ignore-missing-imports` clean (115
source files, confirmed at round 1; hook+test files reconfirmed clean at each subsequent fix).
`test_release_triad.py -k saga`: 3 passed.

## Route

No P0/P1 → not blocking. Recommended: PR-open under operator confirmation, then `/qa`
advisorily post-merge.
