---
date: 2026-06-28
target: docs/brainstorms/2026-06-28-team-spawn-residency-guard-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review)
verdict: READY
blocked: false
---

# Readiness Review — Team-Spawn Residency Guard

## Verdict

**READY for `/plan`** after a heavy reframe. As first written the doc rested on a false premise — that
the reviewer/tester residency the hook guards is "live today, independent of S-1." It is not: today's
consensus loop re-spawns sub-threshold reviewers fresh (`consensus-protocol.md:51`), and the
named-teammate residency the hook assumes is introduced by the **unbuilt** S-1 plan (U3 workers, U4
reviewers). Codex (repo access) put the P0 bluntly, and source verification confirmed it. Eleven
evidence-backed fixes were applied in place. No `P0`/`P1` remains: the hook is reframed as the runtime
**observability** layer for S-1 U3/U4's residency protocol (structurally standalone, sequenced after
U4 — operator-confirmed), the persistence signal is corrected to `name` + `run_in_background` (S-1 U3,
not "name alone"), the trigger set is sourced from the existing reviewer/validator registries (not a
new dead-wired manifest), "enforce" is replaced by "observe" throughout (KTD4 respect), and the
spawn-tool feasibility probe is elevated to a resolve-before-planning go/no-go gate.

## Method

Reviewed as a requirements artifact (readiness-skeptic pass). Adversarial depth came from **codex as a
gated generator under Claude-side verification** — every finding verified against repo source before
adoption:

- **Codex / gpt-5.5** at `xhigh`, read-only, repo access — verified every `file:line` citation directly
  and surfaced the load-bearing P0.
- **Claude-side pre-registered critique** — three findings were predicted before codex returned (the
  D6 "live today" overclaim, the feasibility-as-go/no-go gate, and the "first spawn has nothing to
  reuse" objection); codex converged on the first two, which raised confidence they were real and not
  artifacts of a single engine.

**Coverage caveat — agy was operationally unavailable.** The pipeline normally adds two cross-family
agy engines (Gemini 3.1 Pro + 3.5 Flash, hermetic) for design-logic diversity. Both hung at 0 bytes for
26 minutes and were killed; they contributed nothing. The review proceeded on codex (repo verification)
+ Claude-side source verification + the pre-registered critique. Because codex's findings were all
repo-fact and independently source-verified, agy's absence removed a design-logic cross-check, not a
verification layer — but cross-family diversity is genuinely reduced this run (see Residual risk). This
is itself a live instance of the degrade-when-preferred-engine-unavailable orchestration reality
(captured on S-4 #283).

## Applied fixes

All evidence-backed; the doc was edited in place.

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | D6 reframed: not "live today / independent of S-1" → standalone hook that **observes** S-1 U3/U4's residency protocol, sequenced after U4 | Codex P0 + Claude (pre-registered) | `consensus-protocol.md:51` (fresh re-spawn today); `worker-model-cache-scheduling-plan.md` U3/U4 (residency is unbuilt) |
| 2 | Persistence predicate corrected: `name` alone → `name` + `run_in_background` (D2, R2, R7) | Codex P1 | S-1 plan U3: "one named persistent teammate — `Agent` `name` + `run_in_background`" |
| 3 | Feasibility probe elevated to a resolve-before-planning go/no-go gate (was "Resolve before planning — none") | Codex P1 + Claude (pre-registered) | doc claimed zero blocking questions while R1/R2/R12 assumed the matcher+fields |
| 4 | Trigger-set source = existing `reviewer-registry.md` + `validator-registry.md` (`## Testers`), not a new manifest (R4) | Codex P1 (dead-wiring) | registries already maintained; a standalone manifest has no producer |
| 5 | "enforce/enforcement" → "observe/surface" throughout (Summary, Problem Frame, D6, R6, Scope) | Codex P2 + Claude | KTD4 (`DECISIONS.md:1312`) keeps residency deliberately un-enforced prose |
| 6 | Scanner/monitor exclusion justified by **low residency value**, not "inherently one-shot/never re-run" (D3) | Codex P2 | `validator-spawn-quirks.md:42` — scanners can re-run |
| 7 | False-positive honesty: only sub-9.0 reviewers re-enter, so first-pass reviewers are genuine one-shots; accepted noise documented (D4) | Codex P2 + Claude | `consensus-protocol.md:51-52` |
| 8 | R1 softened: existing hooks *read* `tool_name`+`tool_input`; not claimed exhaustive or spawn-shape-known | Codex P2 | `pre_push_gate_hook.py:122-128` |
| 9 | Review-cycle vs validator-loop cited separately (Problem Frame) | Codex P2 | `consensus-protocol.md:54` (reviewers) vs `validator-spawn-quirks.md:42` (validators) |
| 10 | Warn-only precedent citation corrected to `stale_main_session_hook.py:238-245` (additionalContext + non-blocking exit) | Codex P3 | the exit-0 evidence was omitted |
| 11 | R13 specifies the desired pure decision function for *this* hook, not a claim existing hooks use a "decision-table" | Codex P3 | existing hooks isolate predicates (`_is_git_push_command`) but not a table |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P0 | D6 "live today" residency premise false (today re-spawns; residency is unbuilt S-1) | Codex + Claude | Fixed (reframe + sequence-after-U4) |
| P1 | Feasibility treated as both open and decided | Codex + Claude | Fixed (go/no-go gate, resolve-before-planning) |
| P1 | Persistence predicate ignores `run_in_background` | Codex | Fixed (D2/R2 = name + run_in_background) |
| P1 | Tunable trigger surface = dead-wiring risk | Codex | Fixed (R4 sources existing registries) |
| P2 | False-positive scoping still noisy | Codex | Addressed (D4 documents accepted noise; sub-9.0-only re-entry) |
| P2 | Scanner exclusion overclaims "inherently one-shot" | Codex | Fixed (low residency value) |
| P2 | KTD4 respected by behavior, contradicted by "enforces" | Codex | Fixed (observe/surface) |
| P2 | PreToolUse envelope authority overstated | Codex | Fixed (R1 softened) |
| P2 | Team-cycle citation conflates reviewers/testers | Codex | Fixed (cited separately) |
| P3 | Warn-only precedent omits exit-0 evidence | Codex | Fixed (:238-245) |
| P3 | Test-pattern claim too broad | Codex | Fixed (R13 names the pure fn) |
| CHECK 6 | Warn-only is the right severity (efficiency, not safety) | Codex | Confirmed — validates D1 |

## Residual risk

- **Single-external-engine review.** agy's outage means only one external engine (codex) ran this pass.
  Codex's findings were all repo-fact and source-verified, so the verdict is sound, but a second
  independent design-logic voice did not run. Cheap to re-run agy on the revised doc when it is back, if
  the operator wants the cross-family redundancy before `/plan`.
- **The go/no-go probe is genuinely unresolved.** If the spawn tool the hook actually sees carries
  neither `name` nor `subagent_type` in `tool_input`, the hook is not buildable as specified and the
  design must change. This is correctly the first `/plan` task, not a hidden assumption — but it is a
  real gate, not a formality.
- **Sequencing dependency on unbuilt S-1 U4.** The hook adds little value before U4 (reviewer
  residency) lands; filed now with that dependency recorded (mirrors R1 gated by S-2). If S-1 stalls,
  R6 waits.
- **Stateless false positives remain by design** (D4) — a first-pass reviewer warned needlessly. Bounded
  to one ignorable advisory line; acceptable for a solo dogfood guard.

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`), same pipeline as S-1 (#275) … R14 (#287). Recipient action: `/plan`, whose
first task is the spawn-tool feasibility probe (the go/no-go gate), then enumerate the trigger set from
the registries. Sequence the build after S-1 U4.
