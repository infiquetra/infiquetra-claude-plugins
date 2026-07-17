# Consensus Protocol — team-execution

This file defines the review-revise cycle used in Step B3 of the orchestration protocol.
Read this before running the review cycle to understand scoring, fix routing, and escalation.

---

## Overview

After implementation is complete (Step B2), the **Team Lead** (the main orchestrator agent, Claude/Gemini) coordinates a structured review cycle with all spawned **Reviewers** (the specialized reviewer subagents).

The goal is a mutual consensus agreement between the Team Lead and the Reviewers:
1. **Reviewers** evaluate the implementation and score their dimensions per their own agent prompt's rubric. A reviewer whose prompt defines a dimension with a repo-state precondition (currently: architecture-reviewer's Architecture Documentation Coverage) excludes that dimension when the precondition is absent, rather than scoring it with a fabricated default — see "Non-applicable dimensions". Every other reviewer's dimensions are always-applicable by their own prompt's design; this exclusion mechanism only activates for a reviewer whose prompt defines it. Each reviewer must achieve an overall score of **>= 9.0/10** to signal acceptance.
2. **Team Lead** reviews each reviewer's assessment, verifies that all requested fixes are soundly implemented, and provides the final lead consensus sign-off.
3. The **Human User (Client/Stakeholder)** is **not** part of this consensus loop or the review-revise iterations. They are kept informed of progress and only alerted for severe escalations.

Maximum iterations: **3**. After 3 cycles, proceed with the best available version regardless of scores.

---

## Cycle Structure

```
For iteration 1..3:

  B3a. Spawn all reviewers IN PARALLEL as NAMED, persistent teammates (using Agent `name` + `run_in_background`). The Team Lead MUST record each reviewer's handle/name for later re-engagement (no anonymous one-shot spawns). Provide each with:
        - Full plan context (what was being built)
        - git diff of all changes made — above the SKILL.md Step B1 threshold, an `artifact-pointer` block (see `artifact-pointers.md`) instead of the inlined diff
        - Intended outcome (what success looks like)
        - Path to review-criteria.md for scoring rubrics

        At this fan-out boundary, renew the trusted Claude session through
        `scripts/lease_protocol.py renew`. Saga's `PreToolUse` lifecycle hook then reserves each
        exact reviewer immediately before its Agent provider call. Do not create a second
        team-execution reservation; see `lease-protocol.md`.

        Before any Agent call, the Team Lead runs the packaged `dispatch_settlement_adapter.py
        preflight`; it resolves independently installed Saga and fails loud before the first Agent
        call if unavailable. The adapter writes one canonical dispatch-settlement manifest for the
        complete reviewer roster and appends each reviewer's spawn attempt immediately before that
        reviewer's Agent call, using the stable reviewer idempotency key. The manifest and attempts
        are `run_fact.v1` facts written through Saga's resolved canonical CLI; no mutable queue or
        second ledger is allowed.

  B3b. Each reviewer:
        - Scores each APPLICABLE dimension (0-10) per its own prompt; for a reviewer whose
          prompt defines a precondition-bearing dimension (currently only architecture-reviewer),
          a dimension whose repo-state precondition is absent is EXCLUDED, not scored with a
          fabricated default — see "Non-applicable dimensions" below. A reviewer with no
          precondition-bearing dimension scores all of its dimensions; "applicable" is a no-op
          restriction for it.
        - Produces overall score (average of the applicable dimensions)
        - Issues verdict: ACCEPT (>= 9.0) or NEEDS REVISION (< 9.0)
        - If NEEDS REVISION: provides specific fix requests

  B3c. Collect and display scores:
        Devil's Advocate:      8.7/10 — NEEDS REVISION (2 fixes)
        Security Reviewer:     9.2/10 — ACCEPT
        Architecture Reviewer: 9.4/10 — ACCEPT
        [Optional reviewers if spawned...]
        External Advisory Seat: report-only — PARTICIPATED/HALTED/ABSENT (excluded from gate)
        Claude-vs-external convergence: converged / Claude-only / external-only / conflicting

        Settle every attempted reviewer with `dispatch_settlement_adapter.py settle --kind reviewer`
        from a persisted structured score result. The adapter validates reviewer identity, score,
        non-empty dimension scores, and findings, materializes `dispatch.artifact.v1`, and submits an
        actual-file evidence descriptor to Saga. Missing/empty output, success prose, or an artifact pointer
        without that expected contract is `silent-no-op`. Run the casualty report before B3d;
        `halt_required=true` blocks consensus, and retry-eligible units are claimed from the derived
        DLQ at the next cycle.

  B3d. If ALL gated Claude reviewer scores >= 9.0 → consensus reached → proceed to Step B4

  B3e. Else:
        - Consolidate fix requests from ALL reviewers scoring < 9.0
        - Deduplicate overlapping fixes
        - Route consolidated list to the worker(s) responsible for the affected code
        - Workers implement fixes
        - Re-run B3a..B3d for ONLY the reviewers that scored < 9.0:
          - RE-ENGAGE the same named reviewer via SendMessage (reusing the existing teammate)
          - Do NOT spawn a fresh reviewer. A reviewer who already reviewed once is never re-spawned from cold — they must be messaged to preserve context and residency.
          - (Reviewers who already ACCEPTED do not re-review)

After 3 iterations: proceed with best version, document final scores in completion report
```

---

## Scoring Threshold

| Score | Meaning |
|-------|---------|
| >= 9.0 | ACCEPT — reviewer approves this dimension/overall |
| 7.0 – 8.9 | NEEDS REVISION — issues exist but not blocking if isolated |
| < 7.0 | BLOCKING — dimension must be fixed before proceeding |

**Pass threshold**: Overall score (average of applicable dimensions) >= 9.0 AND no individual
*applicable* dimension < 7.0. An EXCLUDED dimension carries no score and cannot trigger this
rule — see "Non-applicable dimensions" below.

If any applicable dimension scores < 7.0, that reviewer MUST be re-run in the next cycle regardless of overall score.

---

## Non-applicable dimensions (R7/R8/R9)

This mechanism activates only for a reviewer whose own agent prompt defines a
precondition-bearing dimension — currently `architecture-reviewer` only (its Architecture
Documentation Coverage dimension). The other reviewer prompts in this roster define all of
their dimensions as always-applicable and carry no exclusion instruction; extending this
mechanism to a future reviewer requires updating that reviewer's own prompt, not just this
document.

A dimension whose repo-state precondition is absent (e.g. no architecture-decision docs to
check for Architecture Documentation Coverage) is EXCLUDED from that reviewer's overall, not
scored with a fabricated default. Exclusion is dimension-granular: a reviewer whose entire
lens is non-applicable is excluded WHOLE from the consensus denominator, with a logged cause.
The cause vocabulary is shared with the Layer A `execution-spec.md` contract:
`static-non-applicable` (R9) — the two surfaces name the same kind of absence even though
they run on distinct paths (this reference's dimensions are precondition-bearing and
reconciled by prompt; Layer A's verifiers are homogeneous and reconciled by generated code).

A static exclusion is never a failure signal: it does not lower the overall score, does not
count against the "no applicable dimension < 7.0" rule, and does not trigger the re-review
path below — an excluded dimension/reviewer has nothing further to say and is not re-run in
subsequent cycles.

Example: a repo with no `docs/adrs/` and no observable architectural patterns scores the 4
precondition-independent dimensions and excludes Architecture Documentation Coverage; the
overall is the average of those 4, named as such ("avg of 4 applicable") rather than folding
a fabricated N/A default into a 5-dimension average.

## External advisory seat (always excluded)

The external advisory seat is a report-only participant. It is never a base reviewer, never an
optional Claude reviewer, and never part of the consensus denominator. It is an always-excluded
external advisory seat: its score, verdict, halt, absence, or divergent recommendation cannot move
the `>= 9.0` pass threshold, cannot trigger the `< 7.0` blocking-stop rule, and cannot add itself to
the re-review set.

When it participates, the Team Lead attaches a Claude-vs-external convergence report to the verdict
artifact. The first version is key/fingerprint based and has exactly four buckets:

| Bucket | Meaning |
| --- | --- |
| `converged` | Claude and the external seat reported the same keyed finding. |
| `Claude-only` | The Claude panel reported the finding and the external seat did not. |
| `external-only` | The external seat reported the finding and the Claude panel did not. |
| `conflicting` | Both reported the same key but disagreed on summary, severity, or recommendation. |

If the external engine is unavailable, fails preflight, or halts, record the advisory seat as absent
or halted and run the Claude-only consensus flow unchanged. Absence is not a panel failure.

---

## Re-review Scoping

To minimize cost, only re-run reviewers that scored < 9.0 (an EXCLUDED dimension/reviewer has
no score and is never re-run on that basis):

```
Cycle 1 scores:
  Devils Advocate:      8.5 → NEEDS REVISION
  Security:             9.3 → ACCEPT
  Architecture:         8.2 → NEEDS REVISION
  Infra:                9.1 → ACCEPT

Cycle 2: Only re-run Devils Advocate + Architecture
  (Security and Infra already accepted — no need to re-review)
```

---

## Fix Consolidation

When multiple reviewers flag the same file/area, consolidate before routing to workers:

1. Group fix requests by file
2. Within each file, group by section
3. Deduplicate identical fixes
4. Resolve conflicts (if reviewers disagree, use judgment or ask user)
5. Send consolidated list to worker(s) in one message

---

## Score Display Format

Display scores in this format after each review cycle:

```
## Review Cycle [N] Results

| Reviewer | Score | Verdict | Issues |
|----------|-------|---------|--------|
| Devil's Advocate | 8.7/10 | NEEDS REVISION | 2 fixes |
| Security Reviewer | 9.2/10 | ACCEPT | — |
| Architecture Reviewer | 9.4/10 | ACCEPT | — |
| Infra Reviewer | 8.0/10 | NEEDS REVISION | 3 fixes |

Consensus: NOT REACHED — proceeding to fixes
```

---

## After 3 Cycles

If consensus is not reached after 3 iterations:

1. Proceed to Step B4 (Completion) with the current best version
2. Document final scores in the completion report:
   ```
   Note: Consensus not reached after 3 review cycles.
   Final scores: DA=8.8, Security=9.4, Architecture=9.1, Infra=8.3
   Unresolved issues: [list remaining fix requests]
   ```
3. Flag to user: "3-cycle cap reached. The following issues were not resolved and may need follow-up."

---

## Reviewer Context Template

When spawning reviewers in Step B3a (Initial Pass, Iteration 1), provide this context:

`````
You are reviewing the implementation of the following plan:

## Plan Summary
[1-3 sentence description of what was being built]

## Intended Outcome
[What success looks like — what should work after this change]

## Changes Made
Below the SKILL.md Step B1 threshold: inline the git diff or summary of files changed, as today.
Above threshold: an `artifact-pointer` block in place of the inlined diff — dereference it per
`references/artifact-pointers.md` (full read, no per-lens scoping) before scoring. The block is the
JSON emitted by `artifact_pointer.py snapshot` (do not hand-construct it — the `base` field must be a
real base-tree OID or the deref fails):

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch>","hash":"<snapshot-tree-oid>","epoch":"<epoch>","deref":"git diff <base-tree> <snapshot-tree>","base":"<base-tree-oid>"}
```

## Review Instructions
Score the implementation against your 5 dimensions from:
team-execution/skills/team-execution/references/review-criteria.md

Produce your score table, verdict, and fix requests (if NEEDS REVISION).
`````

When re-engaging reviewers in Step B3e (Re-engagement, Iteration N >= 2), send a message carrying only the delta context to preserve conversation history and residency:

`````
The requested fixes have been implemented. Review the specific delta/changes made since your last review pass:

## Implemented Fixes
[Description of specific fixes made in response to your prior fix requests]

## Changes Made (Delta Only)
Below threshold: inline a git diff showing only the changes made since your last pass, NOT the full
diff. Above threshold: an UPDATED `artifact-pointer` block (epoch incremented from your prior pass)
in place of the inlined delta — dereference it per `references/artifact-pointers.md`.

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch+1>","hash":"<snapshot-tree-oid>","epoch":"<epoch+1>","deref":"git diff <base-tree> <snapshot-tree>","base":"<base-tree-oid>"}
```

## Review Instructions
Re-evaluate the implementation, focusing on whether your previous fix requests have been satisfied. Update your scores, verdict, and remaining issues.
`````

---

## Escalation

If a reviewer scores a dimension < 5.0 (severe), immediately:

1. Flag to user (do not wait for cycle to complete)
2. Pause other reviewers if the severe issue would affect their review scope
3. Route the fix to the responsible worker with high priority
4. Resume review cycle after fix is implemented

A score < 5.0 on any security or auth dimension is treated as a **blocking stop** — no
completion until that dimension reaches >= 7.0.
