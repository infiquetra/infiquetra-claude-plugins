---
date: 2026-06-25
kind: doc-review
target: docs/brainstorms/2026-06-25-operator-outcome-orchestration-requirements.md
reviewed_revision: working tree (uncommitted)
blocked: false
---

# Doc-Review — Operator Outcome-Orchestration Requirements

**Verdict:** Strong, well-grounded requirements doc. The review found two P1 store-architecture gaps
(asserted but undeliverable as written) and five lower findings; **all were resolved in the same
session** (see Resolution below). The doc is now ready to drive `/plan`. The product decisions (scope,
failure, degrade, verb surface, unlock, auto-merge, consolidator) are sound and the team-execution /
tmux finding is verified.

## Findings

| ID | Pri | Finding | Status |
|----|-----|---------|--------|
| F1 | P1 | GitHub-canonical reconstruction is lossy on the "why" — trail/cost/frontier aren't in GitHub | resolved — R26/R27 (canonical by facet, non-lossy) |
| F2 | P1 | Shared completion-log concurrency over-reuses saga's single-writer append model | resolved — R10/R28 (per-leaf immutable files) |
| F3 | P2 | Reuse overstated — `orchestration_ref`→child, living DAG, publish-up are net-new | resolved — Dependencies delineation |
| F4 | P2 | Outcome representation split (GitHub nodes / spec edges) with no reconciliation | resolved — R26 (spec single source; sub-issues projected) |
| F5 | P2 | Draft→prune authoring underspecifies edge review + assumes reliable auto-drafting | resolved — R20 (edge-review + review-before-dispatch) |
| F6 | P2 | Bespoke `OutcomeOrchestrator` vs composing existing tools is not defended | resolved — Key Decisions "bespoke, not composed" |
| F7 | P3 | Auto-merge "clean" bar (CI checks, consensus threshold, pre-push gate) imprecise | resolved — R12 ("clean" bar defined) |

### F1 — Reconstruction is lossy on exactly the value F5/Success-Criteria promise (P1)

R26/R27 make GitHub canonical and claim "any machine reconstructs the outcome from GitHub." But the
decision trail (R19), cost rollup (R24), and in-flight frontier live in the volatile per-worktree
cache/ticks — saga-spec §5.3 is explicit that this state is git-ignored and discarded on cleanup, and
it is not in GitHub.

On a fresh machine with no cache, reconstruction yields the skeleton (nodes via issues, completion via
PR-merge) and **loses the trail + cost + in-flight nuance** — yet F5 and the Success Criteria promise
cold-reentry replays the "why." Resolve by giving the trail + cost a GitHub-durable home (issue
comments, the outcome-spec artifact, or a committed report), or downgrade the promise. This is also the
orchestrator-crash-recovery story.

### F2 — Shared completion log can't inherit saga's single-writer append (P1)

R10 frames the unlock signal as "append-only per-saga completion signals" and R28 as "publish a
completion event up to the shared store" — leaning on saga's tick model. But that model (§5.3/§5.4) is
single-writer-per-saga-dir with same-second `-N` disambiguation; it provides **no multi-writer safety**
for one shared log written concurrently by leaves in different worktrees/processes.

R13 requires "locks / idempotency," but the doc never reconciles R10's reuse-framing with R13's
new-safety requirement. A planner who reuses saga's append for the shared log reintroduces precisely
the lost-event/deadlock failure #14 exists to prevent. Resolve by specifying a multi-writer-safe
mechanism (per-writer event files, atomic `O_APPEND`, or a lock) distinct from per-dir ticks.

### F3 — Reuse overstated; orchestration layer is net build (P2 — fixed in place)

Verified against code: saga scripts carry zero `outcome`/`subplot`/publish-up tokens; `orchestration_ref`
is a single-saga `str` backend pointer (`saga.py:168`), not a parent→child link; the `execution_spec`
DAG is computed at emit time within one run. The Kahn *algorithm* and tick *primitives* are reused; the
living DAG, parent-barrier, publish-up, shared store, and `orchestration_ref`→child recursion (R20) are
net-new. **Safe fix applied** — added an explicit reused-vs-net-new delineation to Dependencies so
planning does not under-scope.

### F4 — Split node/edge representation with no reconciliation (P2)

The outcome is stated as nodes in GitHub sub-issues + `depends_on` edges in the spec artifact (R26).
Nothing specifies how the two stay consistent — adding/removing a sub-issue without updating the spec
(or vice versa) silently drifts the DAG. Define the single source for the node set or a validation step.

### F5 — The realism of "stating an outcome" hinges on unspecified edge review (P2)

This is the second axis flagged for review. R20 has the runner draft and the operator "prune." Removing
nodes is easy; reviewing and correcting the dependency **edges** — the failure-prone part of a DAG — is
unspecified, and R20 assumes an agent reliably drafts a correct `depends_on` graph (an error-prone
decomposition treated as given). Name the operator's edge-review affordance as a requirement, and make
operator-review-before-dispatch the explicit safety net for mis-drafted edges.

### F6 — Bespoke vs compose-existing not defended (P2)

A hostile reader asks why a bespoke `OutcomeOrchestrator` beats composing existing tools (a CI/Actions
DAG + sub-issues + a project board). The differentiation (saga reuse, attention routing, per-subplot
executor recommendation, cost instrumentation) is real but implicit; one paragraph naming it would
harden the framing and pre-empt the scope challenge.

### F7 — Auto-merge "clean" bar imprecise (P3)

R12 auto-merges unattended on "green CI + passing review" (AI-reviewer consensus, no human). Define
which CI checks and which consensus threshold constitute "clean," and how that relates to the existing
saga pre-push gate, so the unattended-merge bar is unambiguous. The decision to auto-merge is the
operator's; this is precision, not objection.

## Applied fixes

- Dependencies / Assumptions — added a verified reused-vs-net-new delineation (addresses F3).
- Outstanding Questions — replaced the false "Resolve before planning: none" with the two P1 store
  decisions (F1, F2), and added F4/F5's items to Deferred-to-planning.

## Review-result contract

- **Target:** `docs/brainstorms/2026-06-25-operator-outcome-orchestration-requirements.md`
- **Reviewed revision:** working tree (uncommitted)
- **Blocked:** no — all findings resolved in the same session (R10/R20/R26/R27/R28/R12 + Key
  Decisions); ready for `/plan`.
- **Findings:** P1 ×2 (resolved), P2 ×4 (resolved), P3 ×1 (resolved)
- **Applied fixes:** 2 safe in-place at review time, then full resolution of all 7 findings (see
  Resolution)
- **Rubrics run:** idea-phase cores — assumption_audit, problem_framing, internal_consistency,
  devils_advocate_blueprint (problem_framing passed clean; the rest fed F1/F2/F5/F6)
- **Linked artifacts:** ideation brief `docs/ideation/2026-06-25-operator-outcome-orchestration-ideation.md`;
  UX walkthrough `docs/ideation/2026-06-25-operator-outcome-orchestration-ux-walkthrough.md`

## Resolution (same session)

All seven findings were resolved in the target doc immediately after review, at requirements altitude
(mechanisms deferred to `/plan`).

- **F1 + F4** — the durable record now splits by facet: the committed, version-controlled outcome-spec
  artifact (+ companion decision/cost log) is canonical for structure + decision trail + cost; GitHub
  issues/PRs are canonical for completion; the cache is performance-only. Sub-issues are *generated
  from* the spec, so structure has one source and cannot drift; cold-reentry pulls the repo + GitHub
  and is non-lossy (R26/R27, Key Decisions).
- **F2** — completion events are now per-leaf immutable files in the shared store (saga's
  one-file-per-tick model lifted up), multi-writer-safe by construction; R13's locks cover only the
  orchestrator's single-writer DAG mutations (R10/R28).
- **F3** — reused-vs-net-new delineation added to Dependencies (the orchestration layer is net build).
- **F5** — R20 now makes edge review (add/remove/redirect `depends_on`, not just node-prune) a named
  step, with operator-review-before-first-dispatch as the safety net for a mis-drafted graph.
- **F6** — a "bespoke, not composed" Key Decision names the four things a CI-DAG + board cannot do
  (executor recommendation, leaf lifecycle, attention routing, cost instrumentation).
- **F7** — R12 now defines "clean" precisely (required CI green + consensus/`/code-review` clean + not
  risky) and notes the merge is a server-side squash (the local pre-push gate already passed at work
  time).

## Residual risk

Verification was against the current saga/team-execution code and real git behavior, so the store-mechanism
and reuse findings are evidence-backed. The realism findings (F5, F6) are judgment calls about operator
UX and positioning that only building a draft will fully settle. The cost-thesis assumption underneath
R6/R24 (forks share the parent prompt cache) was not independently re-verified this pass.
