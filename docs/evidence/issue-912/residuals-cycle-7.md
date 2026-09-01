# Issue 912 — recorded residuals after cycle 7

Cycle 7 repaired eleven of the twelve fix requests the terminal validation raised. This file
records the twelfth, which was **not** repaired, with the evidence that establishes it and the
reason it was left. It is recorded so the next reader does not rediscover it, and so no closure
claims more than was done.

## `API-23` — mission-control bypasses the fail-closed maturity contract

**Severity:** P1 · **Lens:** api-contract · **Location:**
`plugins/mission-control/scripts/sdlc_manager.py:4475`

**What is wrong.** Mission Control infers handoff maturity from the artifact path alone. It never
reads the artifact's declared frontmatter, so every fail-closed shape saga now enforces is invisible
to it, and an unconfirmed brainstorm boundary is prepared as `requirements-ready` with a live
`/plan` route.

**Reproduced by the reviewing controller at `3995ae18`,** running both implementations against the
same fixtures:

| Artifact | mission-control | saga |
|---|---|---|
| declares `pending-confirmation` | `requirements-ready` | `pending-confirmation` |
| declares an invalid value | `requirements-ready` | `unknown:unrecognized:bogus-value` |
| declaration outside a fence | `requirements-ready` | `unknown:carrier:plan-ready` |

Mission Control's `_HANDOFF_MATURITY_CHOICES` carries five values and does not contain
`pending-confirmation`; saga's `HANDOFF_MATURITIES` carries all six. The controller confirmed the
end-to-end render: `_render_handoff_context` for the `pending-confirmation` file emits
`### Handoff maturity / requirements-ready` and `### Suggested next action / Use /plan <issue> to
create an implementation plan`.

**Why it was not repaired here.** The fix requires editing
`plugins/mission-control/scripts/sdlc_manager.py`. This run is barred from touching
`plugins/mission-control/`. The operator was shown the finding and the three available paths, and
ruled that the eleven in-scope fix requests be repaired with `API-23` recorded here as a residual
rather than the scope bar being lifted mid-run. That is an operator scope decision, not an
engineering judgement made inside the run, and it was not worked around.

**What is and is not safe about leaving it.** Saga's own contract is closed and mutation-proven
across every frontmatter shape: only a top-level YAML mapping key declares, containment refuses
out-of-root sources, and every other shape fails closed. What remains open is that a *second*
consumer reaches the same artifacts by a different route and does not apply that contract. So the
guarantee holds for anything routed through saga and does not hold for anything routed through
Mission Control. Anyone reading the cycle-7 release note should understand the fail-closed claim as
scoped to saga's own reader.

**Tracked as issue 950** — "Mission Control bypasses saga's fail-closed handoff maturity contract (API-23)", filed against this repository so the residual is not only recorded in run-scoped evidence.

**Recommended next step.** A separate change against `plugins/mission-control/`, with its own
review, teaching `sdlc_manager.py` to read declared frontmatter through saga's
`handoff_envelope.infer_maturity` rather than maintaining a second, narrower vocabulary. Two
implementations of one contract is the same defect shape as `AM-28`, which cycle 7 closed inside
saga by giving re-anchoring a single owner.
