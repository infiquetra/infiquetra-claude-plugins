---
name: doc-review
description: Review Infiquetra plans, requirements, and SDLC documents for implementation readiness.
---

# Doc Review

Use this when a plan, requirements document, strategy document, or formal Infiquetra SDLC
artifact is about to guide implementation.

The core question is:

> Can this document safely drive implementation without the agent inventing missing decisions
> or acting on unverified assumptions?

This is not a copy-editing workflow and it is not a replacement for code review.

## Target Resolution

1. If the user supplied a path, read that document.
2. If no path was supplied, look for an obvious active plan or requirements document under
   `docs/plans/` or `docs/brainstorms/`.
3. If the target is still ambiguous, ask for the document path before reviewing.

Do not create a `/ce-doc-review` alias. The Infiquetra command surface is `/doc-review`.

## Classification

Classify by explicit context first, then evidence. Use this precedence:

1. Explicit user command context, such as "review this spec" or "review this issue".
2. Known SDLC paths or identifiers:
   - Blueprint sections or ADRs -> `/blueprint-review`
   - Specs under `specs/` or documents with spec-phase metadata -> `/spec-review`
   - GitHub issue references or issue-derived documents -> `/issue-review`
3. Content-shape signals:
   - Plan signals: `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1`,
     file lists, test scenarios, verification sections.
   - Requirements signals: goals, non-goals, acceptance examples, flows, success criteria,
     problem framing, `docs/brainstorms/`.
   - Strategy/scope signals: `STRATEGY.md`, strategy updates, founder-scope documents,
     scope or ambition decisions that are about to drive implementation.
4. Path tie-breakers:
   - `docs/plans/` -> plan
   - `docs/brainstorms/` -> requirements
   - `STRATEGY.md` -> strategy/scope

When classification remains ambiguous, ask before routing. Do not silently guess on a formal
SDLC artifact because routing determines which review responsibilities run.

## Formal SDLC Routing

Formal SDLC artifacts get the specialized Infiquetra rubric review first:

- Blueprint sections and ADRs: run `/blueprint-review`.
- Specifications: run `/spec-review`.
- GitHub issues and issue-derived documents: run `/issue-review`.

After the delegate finishes, run the readiness-skeptic pass. Re-read the target document,
collect any delegate artifact or appended review log when present, and include unresolved
formal findings in the readiness summary. Do not reclassify formal rubric findings as
readiness findings.

If `blueprint-reviewer` or a delegate command is unavailable, say so clearly and continue with
readiness review where safe.

## Readiness-Skeptic Pass

Always check:

1. **Verification.** Claims, requirements, and actions must be supported by cited evidence,
   the document itself, linked source, or local repository evidence.
2. **Assumptions.** Surface stale, wrong, or unstated assumptions that would affect execution.
3. **Requirement mapping.** Check origin requirements, acceptance criteria, schema requirements,
   implementation units, and gates map correctly.
4. **Completeness.** Detect missing fields, schema requirements, gates, decisions, or review
   artifacts the document already implies.
5. **Open-choice pressure.** Flag implementation choices that should be defaults, decisions, or
   explicit evidence-gathering tasks.
6. **Adversarial failure modes.** Ask what breaks if an agent follows the document literally.

Triggered lenses:

- Use security/ops scrutiny when the document touches secrets, authorization, deployment,
  infrastructure, data, or external integrations.
- Suggest `/founder-review` as an additional lens when strategy, product scope, ambition, or
  user-facing behavior is prominent.
- Use deployment readiness scrutiny when the document includes deploy, rollback, release,
  environment, or CI/CD behavior.

## Safe In-Place Fixes

Safe fixes are enabled by default and edit the reviewed document in place.

Safe means the document itself, linked source, or local repository evidence clearly supports the
change. Examples:

- add missing schema fields already implied elsewhere in the document
- correct origin requirement mappings when the right mapping is evident
- move follow-up work out of canonical schema and into prose or runbook sections
- fill in gates or checklist items already required by the surrounding section
- fix stale internal references, broken headings, wrong counts, or inconsistent naming

Unsafe changes become findings instead of edits:

- inventing acceptance criteria
- choosing architecture without evidence
- changing scope based on preference
- resolving product decisions without user input
- adding requirements not implied by source material

## Findings

Report remaining findings using priorities:

- `P0`: The document would cause unsafe, incorrect, destructive, or materially wrong execution.
- `P1`: The document is not ready to drive implementation because a core assumption, mapping,
  requirement, default, or gate is missing or wrong.
- `P2`: The document can probably drive work, but the issue creates meaningful rework,
  ambiguity, or review risk.
- `P3`: Nice-to-fix clarity, maintainability, or polish issue.

Lead with findings. A short readiness summary is useful, but P-level findings are the primary
output language.

## Durable Review Artifacts

Write a review artifact under `docs/reviews/` when any trigger is true:

- any `P0` or `P1` finding remains
- any safe fix edits the document
- a formal SDLC delegate ran
- an issue-attached lifecycle flow is active
- more than three findings remain after safe fixes

Every significant review artifact should include:

- This review-result contract:
- target path
- reviewed revision when available, such as a commit SHA or explicit "working tree"
- blocked status
- finding priorities and statuses
- applied fixes
- review artifact path
- override rationale when applicable
- linked issue, plan, or work-session path when available

Ignored local state under `.claude/infiquetra-loop/` is not durable review output.

## Loop And Work Integration

`/doc-review` is explicit by default. `/work` should ask whether to run it before executing from
a plan or requirements document.

If `/doc-review` runs and unresolved `P0` or `P1` findings remain, `/work` blocks unless the
user explicitly overrides. `/work` may consume same-session review output or the latest matching
`docs/reviews/` artifact. Overrides need a rationale that can be carried into issue progress or
work-session notes.

For issue-attached work, summarize:

- fixes applied
- remaining findings
- blocked status
- override rationale, when present
- review artifact link

## Output Shape

Use this structure:

1. Applied fixes, if any.
2. Readiness summary.
3. Remaining findings by priority.
4. Review artifact path, when written.
5. Residual risk from limited evidence, if any.

If no issues are found, say so clearly and name any remaining risk from limited evidence.
