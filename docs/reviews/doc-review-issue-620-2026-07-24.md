# Doc review — issue #620 board-sync plugin resolution plan

**Verdict: READY / not blocked.** Eleven findings raised, eleven fixed in place; zero unresolved
`P0`/`P1` remain, so `/work` is unblocked.

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-07-24-issue-620-board-sync-plugin-resolution-plan.md` |
| Reviewed revision | working tree at `7e4d2db0` (plan uncommitted) |
| Classification | plan (`docs/plans/` tie-breaker; `origin:`, `Implementation Units`, `KTD`, `U1` signals) |
| Rubrics run | issue-phase cores applied as an added lens (issue-derived plan): `acceptance_criteria_clarity`, `spec_fidelity`, `devils_advocate_issue` |
| Blocked | No |
| Findings | 11 raised — 4 `P1`, 4 `P2`, 3 `P3`; all fixed in place |
| External opinion | Not dispatched — `engine_offer.py` returned `prompt_required: false` (stored preference) |
| Linked issue | infiquetra/infiquetra-claude-plugins#620 |
| Linked saga | `issue-620` |
| Outcome leaf | `sub-620` of `governed-execution-integrity` (Objective #639) |

The rubric engine covers `idea`, `issue`, and `spec` phases only; there is no `plan` phase, so the
readiness-skeptic pass was the primary engine and the issue-phase cores were applied as a secondary
lens rather than as a formal phase review.

## Findings

| ID | Pri | Finding | Status |
|---|---|---|---|
| D1 | P1 | KTD1's fleet-core routing creates a version coupling whose failure mode is the #642 staleness the plan names as its own primary risk — `load("plugin_resolution")` raises on a stale fleet-core, killing board-sync harder than the bug being fixed. No mitigation stated. | Fixed |
| D2 | P1 | U2's file list omits `outcome.py`, which re-exports the signature-changed `default_board_writer` and calls it twice. | Fixed |
| D3 | P1 | KTD3 collapsed two distinct failure modes, regressing existing partial-success behavior. | Fixed |
| D4 | P1 | R10 named no target repo and did not bound the board write — an agent following it literally could mutate a live campaign card. | Fixed |
| D5 | P2 | U1's rung-2 walk-up anchor was unspecified; the layouts disagree on the answer. | Fixed |
| D6 | P2 | `marker` was typed ambiguously — string default, "one or more paths" prose. | Fixed |
| D7 | P2 | R8 referenced a rung-1 env override with no concrete name, so it was not pass/fail testable. | Fixed |
| D8 | P2 | KTD1's rejection of A3 omitted that every present consumer is inside saga, overstating the case. | Fixed |
| D9 | P3 | R2's "no `plugins/` directory" misstated the rung-2 discriminator. | Fixed |
| D10 | P3 | R5/R6 extend past the issue's ask without acknowledging the extension (`spec_fidelity` lens). | Fixed |
| D11 | P3 | U3's "one-line change" was an unverified estimate (`devils_advocate_issue` lens). | Fixed |

### D1 — the fix's own delivery inherits #642 (P1)

`fleet_commons_shim.load()` raises `RuntimeError` when the module is missing at the resolved root
(`fleet_commons_shim.py:154-158`). Saga 0.114.0 would require `plugin_resolution`, which first ships
in fleet-core 0.23.0; #642 has proven four-for-four that the install registry goes stale after every
release. The realistic post-release state is therefore saga 0.114.0 resolving fleet-core 0.22.0 and
raising on import.

**Fix:** added **KTD6** (catch the `RuntimeError` at the single per-tick resolution point and route
it into KTD3's `unavailable` terminal, with the shim's already-actionable root+version message plus a
pointer to the #642 hand-repair), new **R11**, a U2 test scenario, two rejected alternatives (E1 hard
floor assertion, E2 vendoring), and a Risk-section paragraph.

### D2 — `outcome.py` missing from U2 (P1)

`default_board_writer(repo_root, ...)` is re-exported as `_default_board_writer` at
`outcome.py:798-812` and called at `outcome.py:1032` and `outcome.py:2952`. U2 changes that
signature but listed only three files, so an agent following the unit literally would break both
callers.

**Fix:** `outcome.py` added to U2's file list with both call sites cited and an explicit note that it
is not optional collateral.

### D3 — KTD3 collapsed two failure modes (P1)

Verified both directions against source. Every op kind extends one `base = ["python3", sdlc]`
(`board_progression.py:350`), so an **unresolvable root** genuinely kills all ops and cohort
withholding is correct. But a **resolved root with an unreadable schema** kills only status ops —
`outcome_board_sync.py:274-277` deliberately keeps the coalesced `ISSUE_PROGRESS_COMMENT` flowing.
The original KTD3 would have withheld comments in that case: a regression introduced by the fix.

**Fix:** KTD3 rewritten to separate the two modes with the evidence for each, plus a C3 rejected
alternative and a U2 non-regression test asserting a `failed` status record *and* a successful
comment on the same leaf.

### D4 — R10 could mutate a live board (P1)

"A real repo outside `infiquetra-claude-plugins`" plus "confirm the board Status field actually
moved" gave no target and no bound. Followed literally against the issue's named failing repo
(`campps-context-library`), this mutates a real campaign card to satisfy an acceptance criterion.

**Fix:** R10 and the Acceptance Criteria section now require an operator-designated repo, a
disposable issue the operator names, and operator confirmation before the write.

### D5–D8 (P2)

D5: the walk-up anchor now defaults explicitly to `Path(__file__)` (this module's own location inside
fleet-core, matching `fleet_commons_shim.py:110`), with the reasoning stated — a saga-anchored
walk-up would resolve differently in the mixed case, and one substrate must have one answer. A test
pins the installed-cache layout missing to rung 3.

D6: `markers` is now a sequence with the mission-control tuple named explicitly.

D7: R8 now names `MISSION_CONTROL_ROOT`, and provenance reuses `FLEET_COMMONS_DEBUG=1` rather than
inventing a second variable.

D8: KTD1's A3 rejection now concedes that a saga-local resolver would suffice for this PR alone and
rests the case on the anti-sprawl argument instead.

### D9–D11 (P3)

R2 restated in terms of the actual rung-2 discriminator; a Requirements preamble now traces R1–R4 and
R7–R8 to the issue's "Expected" section and flags R5/R6/R11 as an acknowledged extension and R10 as
derived; U3's cost restated concretely against `pulse.py:604-621`.

## Applied fixes

All eleven, in place, in the plan document. Structural side-effect: KTD6 was authored between KTD3
and KTD4 and then moved to the end so the numbering reads in order. No U-IDs or R-IDs were
renumbered.

## Residual risk

The plan's correctness rests on four-site grounding read at `7e4d2db0`; if `/work` starts from a
moved `main`, the cited line numbers need re-verification before edits. The KTD2 vendored-schema
staleness (vendored `2026-06-17` vs upstream `2026-07-18`, `phase_board_map` currently identical)
remains deferred by design rather than resolved.
