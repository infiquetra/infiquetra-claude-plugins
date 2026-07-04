# Intake Brief — Plugin-Fleet Ideation → Backlog (Gate A)

- **Date:** 2026-07-03
- **Process:** Socratic ideation → gated GitHub-issue materialization (Phases A–H)
- **Status:** Awaiting Gate A approval
- **Operator:** Jeff Cox

## Intent

Produce a comprehensive, grounded, multi-Objective backlog that turns the
infiquetra-claude-plugins fleet from "working" into spectacular. Every issue is
outcome-generating (a merged, verifiable result) per the Issue Quality Contract; all GitHub
writes happen only after Gate E (issue-plan) and Gate F (mutation plan) approval, executed by
cheap-tier agents through mission-control.

## Appetite

Comprehensive, multi-Objective, no survivor cap. Convergence rejects on quality only:
ungrounded / not outcome-generating / duplicate / contradicts a binding journal DECISION
without engaging its revisit condition / subject-replacement.

## Resolved tensions

### 1. Time vs money (decomposition posture)

Mode-dependent default with an **asymmetric approval rule**:

- Unattended runs (/outcome, /loop, overnight workflows) → cache-tight serial; may proceed
  silently.
- Attended runs → throughput *recommended*, but any spend-increasing choice (parallel
  fan-out, cache churn, tier escalation) **always requires an explicit operator yes**.
  Cache-first is the only silent default.
- Asked once per run at start, with a mode-based recommendation. This lever is itself a
  design requirement for the resulting issues — plugins encode the question, not a
  hard-coded cache-first mandate.

### 2. External-LLM purpose per lifecycle stage

Split by work shape; always operator-choosable, never assumed:

- Judgment stages (/ideate, /brainstorm, /doc-review, /code-review) → default
  **second-opinion**, reconciled by Claude.
- Mechanical stages (/work implementation units, /plan grounding research) → default
  **offload** with a Claude chaperone.
- Per-stage override offered at the prompt in both directions; "none" always available.

### 3. Autonomy posture (/outcome-style loop)

Envelope autonomy with gates **configured at intent capture, not hard-coded**:

- One dialog at start settles lifecycle steps (derived from input shape: a structured
  parent + sub-issues skips ideation; raw text earns a /spec pass) and posture.
- Required intent questions: **"Are PR reviews required for this outcome?"** and
  **"Gate or auto at merge / deploy-to-nonprod?"** Merge/deploy is NOT unconditionally
  gated; the operator decides per outcome, once, at start.
- Everything reversible (status moves, issue closures, labels, branches, PRs opened,
  reviews run) proceeds without asking.

### 4. Fable-5 spend levers

The lever is always surfaced: every Fable-tier line in any plan or issue carries a
recommendation plus a cheaper fallback; expensive is never a silent default (mirrors
tension 1).

**Phase D reshaped** (operator counter-proposal + refinement):

| Layer | Model / effort | Count | Role |
|---|---|---|---|
| Per-theme frame agents | Opus 4.8 / max | ~72 (12 themes × 6 frames) | Wide net — full coverage, no arena consolidation |
| Fleet-wide novelty hunters | Fable 5 / xhigh | 6 (one per frame) | Blind to the Opus fleet; hunt only what an obvious pass won't find |
| Gap synthesis | Fable 5 / xhigh | 1–2 | Post-merge: cross-cutting hybrids; what the pool implies but nobody wrote |
| Convergent critique / clustering | Opus 4.8 / high | as needed | Basis-contract enforcement, dedup, clustering |

No Fable validation layer — validation cannot recover an idea that was never generated;
the named fear (losing a good idea) is a false-negative risk, so premium spend sits at
the generative margins.

### 5. Provider reach

In scope as a theme. Shape: **one router plugin, registry-driven** — extend the existing
engine-registry seam (`engine_resolver.py` / `engine_registry.py`); each provider is a
registry entry + bridge script. Ollama → $0 offload target; DeepSeek → cheap second
opinion.

### 6. Dogfooding

Yes — **codex runs live in Phase D** as one additional blind adversarial-novelty hunter,
reconciled by Claude at convergence. Observed friction (prompt shape, output
reconciliation, envelope limits) becomes direct-basis issue material.

## Added constraint (operator, mid-intake): concurrency cap

**Maximum 3 concurrent agents at any moment, across all phases** (4 permitted only for
short, read-only scans such as Phase B greps). Rationale: rate-limit avoidance; 3 has
been ideal historically.

- Enforcement: workflow scripts chunk every fan-out into batches of ≤3 (explicit
  sequential loop over `parallel()` batches); direct Agent-tool spawns batched ≤3.
- Stated honestly: Phase D (~80 max-effort agents at concurrency 3) becomes a long,
  mostly-unattended run — hours, not minutes. This matches the unattended→cache-first
  posture from tension 1. Exact sizing appears in the Gate C table.
- Promoted to an operator-seed candidate: **fleet-wide rate-limit-aware concurrency
  governance** (team-execution reviewer fan-out, workflow emitters, and /outcome dispatch
  currently have no shared cap policy — to be verified in Phase B).

## Phase B scope (discovery & grounding)

1. Current-repo scan — plugin inventory, agent definitions, model/effort decision points,
   §9 seam re-verification. (Sonnet 5, read-only.)
2. Journal learnings — this repo's LEARNINGS/DECISIONS; binding DECISIONS collected with
   their revisit conditions.
3. Cross-repo journal scan — /promote substrate (`promote_scan.py scan --workspace-root
   ~/workspace/infiquetra`).
4. Cross-repo session mining — **all infiquetra workspace repos, ~60-day window (May 2026
   onward), capped sessions per repo**, /retro substrate, one cheap agent per session.
5. Context library — infiquetra-context-library conventions/standards (feeds the
   ADR/standards-enforcement theme).

## Materialization shape (Gate F policy, agreed early)

**All at once, wave-tagged.** Wave-1 = bandwidth multipliers (lifecycle autonomy,
external offload, tiering levers) so the backlog partially funds its own execution.
Native sub-issues under multiple parent Objectives; Initiative/Objective as project
fields, never colon labels.

## Theme seed list (Phase D — per-theme dispatch, not consolidated)

The 12 themes from the process spec, plus:

13. Rate-limit-aware concurrency governance (operator seed, this session).

The operator's raw-notes appendix carries into Phase D as user-seed candidates verbatim.

## Verification notes

Spot-checked 2026-07-03 before intake: `MODELS`/`EFFORTS` enums
(`plugins/saga/scripts/execution_spec.py:52-53`), `ENGINE_INTENTS`
(`execution_spec.py:68`), cc-workflows-ultracode backend reference
(`lifecycle_state.py:160`), 0 of 25 team-execution agents carry an effort field,
`docs/plans/` convention confirmed. Remaining §9 claims are re-verified in Phase B before
any idea builds on them.

## Pre-mortems recorded

1. **Backlog rot** — generation outpaces execution bandwidth; the fleet churns under open
   issues. Mitigation: wave tagging, wave-1 bandwidth multipliers.
2. **Phase D cost blowout** — original spec ≈ 72 Fable agents. Mitigation: Opus wide net +
   Fable generative edges (~8 Fable total).
3. **Rate limits** — mitigation: global concurrency cap of 3 (above).
4. **Novelty anchoring** — hunters seeing the Opus pool would converge toward it.
   Mitigation: hunters run blind; only gap-synthesis reads the pool, and only after dedup.
