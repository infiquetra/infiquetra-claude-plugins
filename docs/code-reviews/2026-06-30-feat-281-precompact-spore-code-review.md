---
target: branch feat/281-precompact-spore vs main (merge-base diff)
reviewed_revision: b97e0a9 (findings fixed in 6f50d14)
review_type: code-review (pre-PR gate, programmatic — called by /work)
date: 2026-06-30
blocked: false
linked_issue: infiquetra/infiquetra-claude-plugins#281
linked_plan: docs/plans/2026-06-30-precompact-spore-rehydration-plan.md
linked_doc_review: docs/reviews/2026-06-30-precompact-spore-rehydration-doc-review.md
backend: cc-workflows-ultracode (3-lens fan-out + adversarial verify)
---

# Code Review — PreCompact spore (#281) pre-PR gate

**Verdict: CLEAN — not blocked.** Zero P0/P1/P2. Two P3 findings surfaced, both adversarially
verified, both fixed in `6f50d14` before this artifact. 16 files / 2224 insertions across 6 commits
(U1 `6e19dae` → U6 `b97e0a9`).

## Scope check: CLEAN

**Intent:** add the two-hook PreCompact spore so a continuing session re-grounds on structured saga
facts after auto-compaction (#281). **Delivered:** exactly that + its release surfaces. No unrelated
files, no "while I was in there" changes, no scope creep.

## Built-vs-planned audit: all DONE

R1–R13 each map to a shipped unit and a test; KTD1–8 are all reflected in the code:

| Req | Where | Status |
|---|---|---|
| R1 structured (not prose) | `saga_spore.serialize` | DONE |
| R2 saga box (5 fields + blockers/oq, checks_run dropped) | `resolve_active_saga` | DONE |
| R3 DAG (frontier + per-leaf state/gated/event-ref) | `freeze_dag` | DONE |
| R4 pointers not contents | `build_spore` | DONE |
| R5 ≤budget, frontier never dropped, counted pointer, F3 spill | `serialize` + `test_serialize_*` | DONE |
| R6 PreCompact auto\|manual → git-common-dir | hook + `hooks.json` | DONE |
| R7 SessionStart(compact) reads + emits | compact hook + `hooks.json` | DONE |
| R8 unlink-before-emit, at-most-once | compact hook + `test_no_double_inject` | DONE |
| R9 session-keyed + saga_id/repo_root mismatch skip | `load_and_validate` + `test_mismatch` | DONE |
| R10 self-describing + conflict instruction | `serialize` `_AUTHORITY` | DONE |
| R11 nothing on /resume path changes | additive (no edits to saga core) | DONE |
| R12 degrade silent + 1.5s deadline | both hooks + `test_deadline_exceeded` | DONE |
| R13 seam round-trip | `test_spore_seam_roundtrip` (real subprocesses) | DONE |

## Findings

| # | Pri | Status | File | Issue |
|---|---|---|---|---|
| 1 | P3 | **Fixed** (`6f50d14`) | `precompact_spore_hook.py:97` | A `.tmp` file stranded between `write_text` and `os.replace` if the deadline fired mid-write was never reclaimed (sweep globbed `*.json` only). Fixed: immediate cleanup in the except + broadened TTL sweep to all stale files. |
| 2 | P3 | **Fixed** (`6f50d14`) | `test_compact_spore_session_hook.py:143` | `test_unlink_before_emit_crash` proved "unlink survives an emit failure", not the literal R8 ordering (independent suppress blocks). Fixed: docstring corrected; consume-once is genuinely proven by `test_no_double_inject`. |

## Verification method

3 lenses (correctness, robustness/reliability, testing adequacy) fanned out over the ~700-line code
surface, then each surviving finding was adversarially re-verified by an independent agent (real /
introduced-by-diff / not-handled-elsewhere). The verifiers confirmed: the `serialize` budget/trim
loop has no off-by-one and keeps the ready frontier in the never-trimmed core (R5 holds); the
`resolve_outcome_id` leaf-id longest-prefix parse is hyphen-safe and the ≥2-non-complete ambiguity
short-circuit returns None; `load_and_validate` mismatch paths (schema/session_id/repo_root/saga_id)
are correct; the SessionStart unlink-before-emit gives at-most-once and leaves foreign spores intact;
both hooks catch every external-call failure and exit 0. The never-stall-compaction contract holds on
every traced path.

## Coverage / residual risk

- Full feature suite 42/42; whole repo 1530 passed (1 deselected = local-only `.claude`-leak false
  positive from this issue's own saga; green in CI).
- Acknowledged R9 limitation (carried from the plan): same-cwd concurrent sessions with no session→saga
  map fall back to per-repo last-writer-wins. Deferred follow-up, documented in the plan.
- The literal unlink-before-emit ORDERING (vs hard-kill SIGKILL) is not exercisable by an
  exception-based mock; consume-once is proven by `test_no_double_inject`. Acceptable.

## Route

`/qa` (clean gate) — ship-readiness is the next gate after merge. No P0/P1 to hand back to `/work`.
