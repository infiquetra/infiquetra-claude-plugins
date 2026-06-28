---
title: Doc-review readiness — Silent-Omission Completeness Gate plan (#277)
date: 2026-06-28
target: docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md
reviewed_revision: working tree (post-PR#300 merge + the safe fixes recorded below)
issue: infiquetra/infiquetra-claude-plugins#277
blocked: false
---

# Readiness review — Silent-Omission Completeness Gate plan (#277)

**Verdict: READY to drive implementation. No P0/P1. Six precision/alignment findings were safe-fixed in
place; two residuals are documented and non-blocking. `/work` is not blocked.**

The plan is structurally sound: the one-vocabulary-three-sites design holds, the code claims it rests on
were verified against the repo, and the write-sets are complete — including the version-pin tests whose
omission broke CI on the n=1 (#275) build. The findings were all *precision* gaps appropriate to a plan
that will be executed by a delegate (agy) rather than a human, which is exactly where this review focused.

## Review inputs

- **Claude** readiness-skeptic pass + the deployment-readiness and security-of-containment lenses the plan
  triggers (release bumps; clone-jail + credential + FS handling).
- **codex gpt-5.5 (xhigh, read-only with repo access)** — independent reviewer; verified the plan's
  `file:line` claims and judged alignment against `blueprint.md`. First attempt timed out (15-min wall,
  reading files line-by-line); a budget-disciplined retry delivered a clean verdict. It independently
  re-derived F2 and F3 that Claude found on its own pass — that convergence raised confidence both are real.
- **agy (subject-as-reviewer lens) — attempted, did not deliver.** Pro (High) on the 25 KB prompt timed out
  with 0 bytes (print mode buffers until done, so a kill-before-finish leaves nothing); a Flash retry did not
  return within the window. agy itself is healthy (smoke-tested at 6.2s). This is an operational finding, not
  an agy hang — recorded so it is not mislabeled. The independent alignment review was carried by codex.

## Applied fixes (safe, evidence-backed, edited in the plan in place)

| ID | Pri | Axis | Finding | Resolution |
|---|---|---|---|---|
| F1 | P2 | readiness | U2 did not pin `__gate` placement for the `parallel([...])` layer | U2 *Approach* now specifies one guard per var after the `const […] = await parallel([…])` destructure |
| F2 | P2 | readiness | U2's "after every `agent()` site" ambiguously swept in the verify-panel's verifier agents (U3's domain) | U2 *Goal*/*Tests* now scope to **unit-result** sites and explicitly exclude verifier agents (their null is already tolerated by `v && v.refuted`) |
| F3 | P2 | readiness | Python-oracle ↔ emitted-JS `__gate` parity is untested → silent-drift risk | KTD1 now has `completeness_gate.py` **own the `__gate` JS as a string the emitter imports** (single-source); executable (Node) parity test documented as a deferred residual |
| F4 | P2 | alignment | "no searching" in the packet contradicted the blueprint's read-broad principle | Per-unit packet now reads *read broad / write narrow* — search freely, write only the allow-set, escalate `PLAN_GAP` |
| F5 | P3 | alignment | containment prose risked reading `--sandbox`/git-shim as the boundary | KTD6 now names the boundary (clone-without-origin + orchestrator diff/full-gate); shim + sandbox are defense/probe only |
| F6 | P2 | alignment | remote-drift `git ls-remote` underspecified — the jail removes `origin`, so the check is meaningless inside it | Validation floor now runs the remote snapshot/recompare **in the real repo, orchestrator-side**, before launch and after agy exits |

## Verifications (checked, no finding)

- **V1 — U5 write-set complete.** The release write-set includes both version-pin tests
  (`test_saga_plugin.py`, `test_team_execution_plugin.py`) plus the plugin.json / marketplace / CHANGELOG
  files the release-triad guard covers. Directly addresses the #275 U6 under-scope. (Corroborated by codex.)
- **V2 — U3 `Verify`-change blast radius contained.** `tests/test_workflow_emitter.py` is the *only* test
  file that constructs a verify panel; `team_emitter.py` and `outcome_spec.py` embed zero `Verify`
  references — so adding `iterate_to_consensus`/`max_iterations` cannot silently break a test the write-set
  omits. The round-trip tests assert attributes, not exact-dict equality, so symmetric `to_dict`/`from_dict`
  stays green.
- **V3 — plan code claims accurate.** `Unit.returns` at `execution_spec.py:180`; the emitter binds each
  result with no null-check; the verify panel `log()`s-and-proceeds at `:514-518` (the R4 fix U3 makes).

## Remaining findings (non-blocking)

| ID | Pri | Finding | Status |
|---|---|---|---|
| F7 | P2 | U4 (R12) enforcement is prose-only — team-execution has no Python, so the only test is a doc-contract assertion, weaker than the JS path | **Accepted residual** (operator decision: good enough to start; revisit if it fails in practice) |
| F3-r | P2 | oracle ↔ JS executable parity not tested (no Node runtime) | **Accepted residual** — mitigated by KTD1 single-sourcing + the Python self-test pinning semantics; a Node parity test is the way to fully close it |

## Residual risk from limited evidence

- The oracle↔JS `__gate` parity is single-sourced but not *executed* in a test; a faithful-port error could
  let the emitted gate mis-classify silently. This is the one place the gate could be quietly wrong.
- U4/R12 enforcement leans on the team-execution skill reading and obeying the protocol prose.
- The delegated build (agy) still carries the F1–F5 behavioral risks the harness contains *reactively*; this
  review hardened the containment spec, but the n=2 run is the real test of whether it holds.

## Routing

`/work docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md` — not blocked. The agy-delegated
build runs per the plan's Delegated Build Protocol (now hardened by F4/F5/F6). Record the n=2 result in
`docs/external-agent-delegation/README.md`'s results matrix.
