---
title: Doc Review — Gate-Divergence Telemetry Plan
date: 2026-07-04
target: docs/plans/2026-07-04-gate-divergence-telemetry-plan.md
reviewed_revision: working tree
blocked: false
---

# Doc Review — Gate-Divergence Telemetry Plan

**Verdict: not blocked.** The plan is ready to drive `/work`. Two safe fixes were applied in
place after this review surfaced a real data-corruption bug in the original encoding choice;
one completeness gap and one open-choice gap were also fixed. Zero findings remain.

## Target and scope

- Target: `docs/plans/2026-07-04-gate-divergence-telemetry-plan.md`
- Reviewed revision: working tree (uncommitted)
- Classification: plan document (content-shape signals — `origin:`, `Implementation Units`,
  `Key Technical Decisions`, `U1` — plus path tie-breaker `docs/plans/`). Same track as the
  #461 plan review: not routed to the idea/issue rubric engine.
- Linked issue: infiquetra/infiquetra-claude-plugins#399
- Linked saga: `issue-399` (plan phase, active, destination `merge`, backend `inline`)

## Applied fixes

| # | Fix | Evidence supporting the change |
|---|---|---|
| 1 | KTD1 changed from raw pipe-joined JSON blobs (matching `--artifact-pointers`'s help text) to base64-wrapped JSON blobs, pipe-joined | Verified live: `grep -rn json.loads plugins/saga/scripts/*.py` shows no caller ever parses an `artifact_pointers` entry as JSON — the "JSON blocks" phrasing in `saga.py:1295-1298` is help text, not a proven consumer. `_split_list` (`saga.py:1177-1184`) is a raw `value.split("|")` with no escaping, so a gate `answer` containing a literal `|` would have silently corrupted the entry list under the original design. Base64's alphabet contains no `|`, so the fix eliminates the corruption mode without touching `_split_list`. |
| 2 | U6 now names the actual version-parity test (`tests/test_release_triad.py`) and the hardcoded literal at `tests/test_saga_plugin.py:48` (`assert plugin_json["version"] == "0.51.0"`) that must be bumped in the same PR | The issue's own suggested test name (`test_marketplace_drift.py`) does not exist in this repo (verified: `find tests -iname "*drift*" -o -iname "*marketplace*"` returns `test_agent_registration_drift.py`, `test_marketplace_hook.py`, `test_operator_choice_drift.py` — none of them). `test_saga_plugin.py:48` is a literal string assertion, not a computed read, so leaving it unbumped would silently fail CI after the version change. |
| 3 | U4 clarified that one issue-cited `SKILL.md` line range can fire more than one distinct gate, using `founder-review/SKILL.md` as a concrete counter-example (0F mode selection at `:133`, per-expansion opt-in at `:144`, both reachable from the issue's single `:80-85` citation) | Verified live by reading `founder-review/SKILL.md:125-150` during this review — two structurally distinct `AskUserQuestion` decision points exist under one citation. Left unaddressed, `/work` would have had to invent whether that citation means one `gate_id` or two — exactly the "open-choice pressure" the doc-review lens exists to catch. |

## Readiness-skeptic pass

**Verification.** All five `AskUserQuestion` citations (`brainstorm/SKILL.md:31`,
`founder-review/SKILL.md:80-85`, `investigate/SKILL.md:91-98`, `loop/SKILL.md:72-74`,
`outcome/SKILL.md:154-161`) and both `saga.py` field citations (`:174-175`, `:217`) were
independently re-grepped during this review and matched the plan's citations exactly — unlike
#461, this issue was drafted the same day as this review and shows no citation drift.

**Assumptions.** The original KTD1 assumed the `--artifact-pointers` help-text convention was a
working precedent without checking for a real consumer — this was a stale assumption, corrected
by Applied Fix #1. The plugin.json minor-bump reasoning (`0.51.0` → `0.52.0`, new field + new
script, no breaking change) is a reasonable default and not itself risky; no other unstated
assumptions found in the core path (U1/U3/U5/U6).

**Requirement mapping.** All seven of issue #399's Definition-of-Done items map cleanly onto
R1–R7 and the Implementation Units: R1→U1, R2→U1/U2, R3→U3, R4→U5, R5→U2/U4, R6→U6 (regression),
R7→U6 (release surface). No gaps, no orphaned DoD items.

**Completeness.** Fixed by Applied Fix #2 (the real drift-guard test and the hardcoded version
literal, both absent from the original draft's generic "existing version-parity drift-guard
test" phrasing).

**Open-choice pressure.** Fixed by Applied Fix #3 (gate-id-per-decision-point, not per-file).

**Adversarial failure modes.** Checked what breaks if `/work` follows the plan literally: without
Fix #1, the first gate answer containing a `|` character would have corrupted saga state
silently (no exception, just misaligned list entries) — the worst kind of bug, since
`gate_divergence_reader.py` would then report plausible-looking but wrong numbers rather than
erroring. With the base64 fix, a malformed entry raises `ValueError` loudly instead (U1's
`parse_gate_divergence_entry`). No other P0/P1-shaped failure mode found.

## Remaining findings

None. No P0, P1, P2, or P3 findings remain after the three applied fixes.

## Review artifact

This file: `docs/reviews/2026-07-04-gate-divergence-telemetry-plan-review.md`

## Residual risk from limited evidence

Low. U4 now flags (rather than resolves) that `brainstorm/SKILL.md`, `investigate/SKILL.md`,
`loop/SKILL.md`, and `outcome/SKILL.md` were not individually re-checked in this review for the
same one-citation-may-mean-multiple-gates pattern found in `founder-review/SKILL.md` — the plan
correctly defers that enumeration to `/work`'s own grounding pass rather than guessing here, so
this is a deferred verification step, not an unaddressed gap.
