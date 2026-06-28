# Dogfood narrative — agy as coder for #275 (worker×model cache scheduling)

**Date:** 2026-06-28
**Issue:** [#275](https://github.com/infiquetra/infiquetra-claude-plugins/issues/275) — worker×model cache scheduling, cost-first worker residency
**Plan:** `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md` (doc-reviewed READY, 11/11 findings fixed)
**Branch:** `feat/worker-cache-scheduling`

## Why this log exists

We are dogfooding **agy (Antigravity / Gemini)** as the *implementer* on a real, load-bearing change,
to gather concrete input for our plugins that wrap agy and codex (`agy:*`, `codex:*`). The goal is not
just to ship #275 — it is to learn **how to prompt agy well, where it breaks, and which model/effort
tier fits which task shape**, so the plugin guidance reflects evidence, not guesses.

## Experiment design

- **Division of labor:** agy writes implementation **and** tests per unit, in-repo on the feature
  branch. Claude (the carrier) verifies every diff — runs `uv run pytest` / `ruff` / `mypy`, reads
  the change, runs a red-before-green check on the two Python units, and only then commits. Claude
  carries the saga and owns PR / merge / close / cleanup.
- **Model strategy:** start every unit on **Gemini 3.5 Flash (High)**; escalate that unit to
  **Gemini 3.1 Pro (High)** only on visible failure after a couple of iterations — and record the
  escalation here as a data point.
- **Invocation:** `timeout <N> agy --model "<model>" --dangerously-skip-permissions -p "<task>"`
  run foreground from the repo root on the feature branch; Claude reviews the diff before any commit.
- **Gate:** per-unit. A unit is committed only when its tests + lint + type-check are green and the
  diff matches the plan's intent.

## Unit suitability (pre-registered expectation)

| Unit | File(s) | Shape | Pre-registered difficulty |
|---|---|---|---|
| U4 | `consensus-protocol.md` | markdown, no tests, independent | easy — warm-up |
| U1 | `execution_spec.py` | Python + pytest, KTD4/KTD5 subtle | **hard — crux** |
| U2 | `team_emitter.py` | Python + pytest, schema-breaking | **hard — crux** |
| U3 | `SKILL.md` | markdown, no tests | medium |
| U5 | `SKILL.md` (waves) | markdown, no tests | medium |
| U6 | release surfaces | version/CHANGELOG/marketplace.json | mechanical-precise |

Pre-registered hypothesis: Flash (High) clears the markdown + mechanical units unaided; the Python
crux units (U1/U2) are where Flash is most likely to need iteration or escalation, especially the
*do-not-mutate-the-shared-spec* (KTD5) and *segment-dependency-graph collapse* (KTD4) subtleties.

## Per-unit run log

> Filled in as each unit runs. Capture: model used, # of agy iterations, what the prompt needed,
> what agy got wrong, whether escalation was triggered, file-edit reliability, test quality
> (tautological? did red-before-green hold?), and a one-line takeaway.

### U4 — review-loop reviewer residency
- **Model:** Gemini 3.5 Flash (High). **Iterations:** 1 (first try, no rework). **Wall:** 19s. **Escalation:** none.
- **Prompt shape:** plan-pointer (read the U4 section + R5) + an explicit 3-item change checklist. Scaffolded but not line-dictated.
- **Result:** all three required changes correct — B3a named/recorded teammates, B3e SendMessage re-engage (no cold re-spawn), and a new "Re-engagement (N≥2)" delta-only context template (R5). Isolated to the one target file; markdown + code-fences preserved; no step renumbering.
- **Quality notes:** B3a became a long run-on line (verbose but accurate); agy added a helpful "(Initial Pass, Iteration 1)" disambiguation — minor positive, not scope creep. agy's self-summary matched the actual diff.
- **File-edit reliability:** clean — touched only the named file, created nothing extra, ran no git.
- **Takeaway:** Flash (High) is fully adequate for a well-specified **markdown protocol** edit driven by a plan pointer; a thin-but-structured checklist prompt was sufficient, no hand-holding. Pre-registered "easy" confirmed.

### U1 — Unit.files + segmentation / dep-derivation / tiering
_pending_

### U2 — segment-row emit
_pending_

### U3 — worker residency runtime protocol
_pending_

### U5 — reactive-unblock waves
_pending_

### U6 — release surfaces + drift guards
_pending_

## Cross-cutting observations (distilled at the end → LEARNINGS.md)
_pending_
