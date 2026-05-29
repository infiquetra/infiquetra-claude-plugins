# Requirements: Infiquetra Loop Doc Review

**Date.** 2026-05-29
**Status.** Ready for planning
**Source idea.** `docs/ideation/2026-05-29-infiquetra-loop-doc-review.md`

## Problem

`infiquetra-loop` is intended to replace daily Superpowers and Compound Engineering
lifecycle use, but it does not yet replace the frequent `/ce-doc-review` workflow.
The missing use case is not generic prose review. It is plan and requirements review
before a document drives implementation.

Without this command, agents can proceed from plans or requirements documents that
contain unverified claims, wrong assumptions, incorrect requirement mappings, missing
contract fields, unresolved implementation choices, or misplaced follow-up work.

## Primary User

The primary user is an Infiquetra founder / tech lead / staff engineer using lifecycle
documents to guide implementation, issue progress, pull requests, and deployments.

## Product Shape

Add `/doc-review` to `infiquetra-loop` as an implementation-readiness skeptic for plans,
requirements documents, and formal SDLC artifacts.

The command should answer:

> Can this document safely drive implementation without the agent inventing missing
> decisions or acting on unverified assumptions?

## Goals

- Review plans and requirements documents for implementation readiness.
- Catch unverified claims, unsupported actions, wrong assumptions, and incorrect
  mappings before execution.
- Apply narrow safe fixes in place by default.
- Report remaining findings using `P0` / `P1` / `P2` / `P3` priorities.
- Block `/work` on unresolved `P0` or `P1` findings unless the user explicitly
  overrides.
- Route formal Infiquetra SDLC artifacts through `blueprint-reviewer` first, then run
  a second readiness-skeptic pass.
- Persist a review artifact under `docs/reviews/` when edits or findings are
  significant.

## Non-Goals

- Do not clone all Compound Engineering document-review behavior.
- Do not add a `/ce-doc-review` compatibility alias.
- Do not replace `blueprint-reviewer` rubrics.
- Do not make document review a generic copy-editing or style-polishing command.
- Do not make `/work` run document review automatically without asking.
- Do not mutate documents when the fix is not clearly supported by document evidence.

## Command Surface

### `/doc-review`

Reviews a provided document path or an obvious current lifecycle document.

Expected examples:

```text
/doc-review docs/plans/example.md
/doc-review docs/brainstorms/example-requirements.md
/doc-review STRATEGY.md
```

No `/ce-doc-review` alias should be added for v1.

## Default Workflow

1. Resolve the target document.
2. Classify the document type.
3. If the document is a formal Infiquetra SDLC artifact, run the appropriate
   `blueprint-reviewer` review first.
4. Run the readiness-skeptic review.
5. Apply safe fixes in place.
6. Report remaining findings using priority levels.
7. Write `docs/reviews/` output when edits or findings are significant.
8. Return a clear summary of fixes applied, findings remaining, and whether the
   document can drive `/work`.

## Document Classification

The command should classify documents by content and path.

### Formal SDLC Artifacts

Examples:

- blueprint sections
- specifications
- GitHub issue drafts or issue-derived documents

Behavior:

- Run the matching `blueprint-reviewer` workflow first.
- Then run `/doc-review`'s readiness-skeptic pass.
- In v1, keep this as sequential composition rather than a merged rubric system.

### Plans And Requirements

Examples:

- `docs/plans/*.md`
- `docs/brainstorms/*requirements*.md`
- implementation plans produced by `/plan`
- requirements documents produced by `/brainstorm`

Behavior:

- Run the readiness-skeptic review directly.
- Focus on whether the document can safely guide implementation.

### Strategy Or Scope Documents

Examples:

- `STRATEGY.md`
- strategy updates
- founder-scope docs

Behavior:

- Run readiness review when the document is about to drive implementation.
- Mention `/founder-review` as an optional additional lens when scope, ambition, or
  product framing risk is prominent.

## Review Lenses

### Always-On

- **Verification.** Identify claims, requirements, and actions that are not supported by
  cited evidence or by the document itself.
- **Assumption audit.** Find wrong, stale, or unstated assumptions that would affect
  implementation.
- **Requirement mapping.** Check that origin requirements, acceptance criteria, schema
  requirements, and implementation requirements map correctly.
- **Completeness.** Detect missing fields, missing schema requirements, missing gates,
  or missing decision points that the document already implies.
- **Open-choice pressure.** Flag implementation choices that should be defaults,
  decisions, or explicit evidence-gathering tasks.
- **Adversarial review.** Ask what would break if the agent followed this document
  literally.

### Triggered

- **Security / ops.** Trigger when the document touches secrets, authorization,
  deployment, infrastructure, data, or external integrations.
- **Founder / product.** Trigger when the document changes user-facing behavior,
  product scope, strategy, or ambition.
- **Deployment readiness.** Trigger when the document includes deploy, rollback,
  release, environment, or CI/CD behavior.

## Safe Auto-Fixes

Safe fixes are enabled by default and should edit the reviewed document in place.

Safe means the document itself, linked source, or local repository evidence clearly
supports the change. Examples:

- add missing schema fields already implied elsewhere in the document
- correct origin requirement mappings when the right mapping is evident
- move follow-up work out of canonical schema and into prose or runbook sections
- fill in missing gates or checklist items already required by the surrounding section
- fix stale internal references, broken headings, or obvious inconsistent naming

Unsafe changes should be reported as findings instead of applied.

Unsafe examples:

- inventing acceptance criteria
- choosing an architecture without evidence
- changing scope based on preference rather than document support
- resolving a product decision without user input
- adding new requirements not implied by the source material

## Finding Priorities

Findings should lead with priority levels.

- **P0.** The document would cause unsafe, incorrect, destructive, or materially wrong
  execution.
- **P1.** The document is not ready to drive implementation because a core assumption,
  mapping, requirement, default, or gate is missing or wrong.
- **P2.** The document can probably drive work, but the issue creates meaningful
  rework, ambiguity, or review risk.
- **P3.** Nice-to-fix clarity, maintainability, or polish issue.

The command may include a one-line readiness summary, but priorities are the primary
output language.

## Loop Integration

`/doc-review` should be explicit by default. `infiquetra-loop` should not silently run it.

When `/work` is about to use a plan or requirements document, the loop should ask whether
to run `/doc-review` first. If review runs and finds unresolved `P0` or `P1` findings,
`/work` should block unless the user explicitly overrides.

For issue-attached work, review summaries should be usable in issue progress comments:

- fixes applied
- remaining `P0` / `P1` / `P2` findings
- whether execution is blocked
- review artifact link when one was written

## Durable Review Artifacts

Inline output is enough for minor safe fixes and small findings.

Write a review artifact under `docs/reviews/` when:

- edits are significant
- remaining findings are significant
- the review blocks `/work`
- the review involved a formal SDLC artifact plus readiness pass
- the review is part of an issue-attached lifecycle flow

Suggested artifact contents:

- reviewed document path
- review type and routed delegates
- safe fixes applied
- remaining findings by priority
- evidence checked
- execution readiness summary
- issue or plan links when available

## Failure And Fallback Behavior

- If `blueprint-reviewer` is unavailable for a formal SDLC artifact, say so clearly and
  run the readiness-skeptic pass only.
- If the target document is ambiguous, ask for the document path.
- If safe fixes require evidence that is not present, do not edit. Emit a finding.
- If no issues are found, say that clearly and report any residual risk from limited
  evidence.

## Future Work

The relationship between `/doc-review` and `blueprint-reviewer` should be revisited after
v1 usage. They may eventually become a joined review flow, but v1 should keep ownership
clear:

- `blueprint-reviewer`: formal Infiquetra SDLC rubric quality
- `/doc-review`: implementation-readiness skepticism for documents that will drive work

## Acceptance Criteria

- `infiquetra-loop` includes a `/doc-review` command and matching skill.
- No `/ce-doc-review` alias is added.
- `/doc-review` can classify formal SDLC artifacts, plans, requirements docs, and
  strategy/scope docs.
- Formal SDLC artifacts run `blueprint-reviewer` first, then the readiness-skeptic pass.
- Safe fixes are applied in place by default.
- Remaining findings are reported as `P0` / `P1` / `P2` / `P3`.
- `P0` and `P1` findings block `/work` unless explicitly overridden.
- Significant reviews produce artifacts under `docs/reviews/`.
- `/work` asks whether to run `/doc-review` before executing from a plan or requirements
  document.
- README, changelog, and marketplace/plugin metadata are updated if command registration
  requires it.
