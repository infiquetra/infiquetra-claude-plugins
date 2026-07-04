---
title: Code Review — Gate-Divergence Telemetry (#399)
target: branch docs/pf-gate-divergence-telemetry-399 vs main
reviewed_revision: 046f84da5ca9a63e4e5499fa03fcf6d00fb72816 (pre-fix); fixes applied after review
blocked: false
mode: programmatic
---

# Code Review — Gate-Divergence Telemetry (#399)

**Verdict: not blocked.** Zero P0/P1 findings from any of the 4 dispatched lenses. Two P2s and
two P3s were confirmed and fixed in place; one P3 (SKILL.md phrasing inconsistency) is accepted
as-is (purely cosmetic, no governing formatting rule applies to skill instruction prose).

## Scope

- Target: `docs/pf-gate-divergence-telemetry-399` vs `main` (merge-base `ae0c4465`)
- Reviewed revision: `046f84d` (2 commits: `5f9b656` feat, `046f84d` docs); fixes below landed in
  a third commit after this review
- 23 files changed, +1346/-20 (`.serena/project.yml` excluded — pre-existing unrelated local
  state, not part of this diff, same exclusion as issue #461's review)
- Scope check: **CLEAN** — every changed file traces to the plan's U1-U6 or the shared kickoff
  contract's release-surface/checklist obligations. No drift, no missing requirements.

## Lenses run

4 always-on: correctness, security, testing, maintainability. No conditional lens warranted —
no deploy/infra/data-migration surface touched. Each lens dispatched as `saga:readonly-verifier`
in an isolated worktree per `plugins/saga/references/sandbox-spawn-sites.md`.

## Built-vs-planned audit

| Unit | Status | Evidence |
|---|---|---|
| U1 (field + CLI plumbing) | DONE | `saga.py` diff; 12/12 tests in `test_gate_divergence.py` |
| U2 (instrumentation doc) | DONE | `plugins/saga/references/gate-divergence-instrumentation.md` |
| U3 (reader) | DONE, CHANGED from plan's literal wording | reused `saga.parse_envelope` instead of a lightweight line parser — verified necessary (multi-line YAML list + base64), noted in work-session |
| U4 (5 gate sites) | DONE | 5/5 files reference the instrumentation doc |
| U5 (retro wiring) | DONE | `retro/SKILL.md` 1.6a |
| U6 (tests/fixtures/release surfaces) | DONE, 2 citation corrections | real test names differ from issue's suggested names (documented) |

## Findings

| # | File | Issue | Lens | Confidence | Route | Outcome |
|---|---|---|---|---|---|---|
| 1 | `plugins/saga/scripts/saga.py` (KTD1 docstring) | Rationale stated the base64 wrapping protects against `_split_list`'s pipe-split, but `gate_divergence` is a repeatable `action="append"` CLI arg — it never passes through `_split_list`. `_yaml_scalar` already safely quotes/escapes the actual rendering path (verified: pipe, newline, leading-dash all handled correctly). | correctness | 100 | fixed | **Fixed** — docstring now states the real mechanism (defense-in-depth against `_yaml_scalar` escaping bugs, not a live corruption fix) |
| 2 | `plugins/saga/scripts/gate_divergence_reader.py:141` | Bare `except Exception` with no `# noqa: BLE001` + justification, deviating from the repo's own house convention (every other broad except in `plugins/saga/scripts/` carries one) | maintainability | 100 | fixed | **Fixed** — added noqa tag + inline rationale citing the `override_rate_reader.py` precedent |
| 3 | `tests/test_gate_divergence.py` | Missing REPLACE-vs-accumulate regression test for full-snapshot list semantics (acceptance-criterion gap, not a live bug — manually verified correct) | testing | 100 | fixed | **Fixed** — added `test_second_save_replaces_not_accumulates` |
| 4 | `plugins/saga/scripts/saga.py` `parse_gate_divergence_entry` | Deeply-nested JSON (~200k levels) raises `RecursionError`, uncaught by `except json.JSONDecodeError`, crashing the reader's `main()` (DoS, requires local write access to an envelope) | security | 100 | fixed | **Fixed** — broadened to `except (json.JSONDecodeError, RecursionError)`; regression test added |
| 5 | `tests/test_gate_divergence.py` | Untested edge cases: empty-string answer, unicode answer, negative latency | testing | 75 | fixed | **Fixed** — 3 tests added |
| 6 | 6 `SKILL.md` gate-divergence notes | Inconsistent bold/inline emphasis style across the 6 instrumentation notes — purely cosmetic, no governing rule | maintainability | 75 | advisory | **Accepted as-is** — no formatting-style.md rule applies to skill instruction prose; not worth the churn |

No P0, no P1. Findings 1-5 fixed in a follow-up commit on this branch; finding 6 accepted.

## Coverage

- No residual risk from limited evidence beyond what each lens explicitly named (correctness:
  did not construct an adversarial newline/frontmatter-delimiter fixture beyond the pipe case —
  now moot given finding 1's fix confirms `_yaml_scalar` already handles this; testing: the
  reader's "newest file by filename" tie-break across multiple envelope files per saga directory
  isn't exercised by either committed fixture, both of which have exactly one envelope file).
- All 4 lenses independently reproduced/falsified their own claims rather than asserting from a
  read — no unverified claims accepted.

## Review artifact

This file: `docs/code-reviews/2026-07-04-pf-gate-divergence-telemetry-399-code-review.md`

## Route

`/qa` — clean review, ready for PR.
