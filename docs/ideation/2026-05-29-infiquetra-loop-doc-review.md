# Ideation: Infiquetra Loop Doc Review

**Date.** 2026-05-29
**Status.** Ready for brainstorm
**Source.** User feedback after the initial `infiquetra-loop` command set: `/ce-doc-review`
is used often and was not carried forward as a first-class command.

## Prompt

`infiquetra-loop` is meant to replace daily Superpowers and Compound Engineering
lifecycle use. The current command set covers ideation, brainstorming, planning, work,
QA, code review, founder review, optimization, retro, and resume. It does not yet
cover CE's generic document review workflow.

The missing question:

> What should an Infiquetra-native `/doc-review` do so that `/ce-doc-review` can be
> retired without losing useful review behavior?

## Grounding

- `plugins/infiquetra-loop/skills/ideate/SKILL.md` says selected ideas persist under
  `docs/ideation/`.
- `plugins/infiquetra-loop/skills/brainstorm/SKILL.md` says requirement discovery
  persists under `docs/brainstorms/`.
- `plugins/infiquetra-loop/skills/code-review/SKILL.md` covers diffs, PRs, and
  pre-shipping gates, not prose documents.
- `blueprint-reviewer` already owns formal Infiquetra SDLC rubric review for
  blueprint sections, specs, and GitHub issues.
- No `plugins/infiquetra-loop/commands/doc-review.md` or matching skill currently
  exists.

## Problem

Without a generic document-review surface, uninstalling Compound Engineering removes
a frequent review primitive for plans, requirements, strategy updates, brainstorm
outputs, ADR-like proposals, and other markdown documents.

The adjacent commands do not fully cover the need:

- `/code-review` is too implementation- and diff-oriented.
- `blueprint-reviewer` is valuable, but intentionally phase-specific and rubric-driven.
- `/founder-review` is scope and ambition oriented, not a structured document review.
- `/qa` is verification oriented, not document coherence review.

## Candidate Directions

### 1. Add a thin `/doc-review` wrapper around existing commands

Route formal SDLC docs to `blueprint-reviewer`, route code-like requests to
`/code-review`, and otherwise give a short manual review.

**Pros.**
- Smallest implementation.
- Avoids overlapping too much with `blueprint-reviewer`.

**Cons.**
- Does not preserve the CE-style multi-lens review value.
- Easy for the command to feel shallow.
- Still leaves no durable generic review rubric inside `infiquetra-loop`.

### 2. Add CE-style generic document review inside `infiquetra-loop`

Create `/doc-review` with document classification, multi-lens review, headless mode,
and optional durable output under `docs/reviews/`.

Suggested lenses:

- coherence and internal consistency
- feasibility and operational realism
- scope and sequencing
- product or founder lens when user-facing or strategic
- security and deployment lens when relevant
- adversarial lens for hidden failure modes

**Pros.**
- Best replacement for `/ce-doc-review`.
- Useful across plans, brainstorms, strategy docs, ADR-like proposals, and specs.
- Can become a gate inside `/plan`, `/work`, `/qa`, and `/loop`.

**Cons.**
- Needs careful boundaries so it does not duplicate `blueprint-reviewer`.
- More command and skill surface to maintain.

### 3. Make `/doc-review` a router with specialized delegates

Use `/doc-review` as the user-facing entry point, but route based on document type:

- blueprint section, spec, or issue: delegate to `blueprint-reviewer`
- code diff or PR: delegate to `/code-review`
- strategy or founder-scope document: offer `/founder-review` as an additional lens
- plan, brainstorm, requirements doc, ADR-like proposal, or arbitrary markdown:
  run the generic document-review workflow

**Pros.**
- Preserves a single memorable command.
- Keeps formal SDLC review owned by the plugin that already has the rubrics.
- Lets generic doc review focus on documents that have no better specialized owner.

**Cons.**
- Router behavior must be explicit so users understand which review they received.
- Requires good fallback behavior when `blueprint-reviewer` is unavailable.

### 4. Add compatibility aliases for high-frequency CE commands

For users migrating from Compound Engineering, add aliases such as `/ce-doc-review`
and possibly `/ce-ideate`, `/ce-brainstorm`, `/ce-plan`, `/ce-work`, and
`/ce-strategy` where command aliasing is supported.

**Pros.**
- Reduces migration friction and muscle-memory loss.
- Makes uninstalling CE safer.

**Cons.**
- May blur the boundary between Infiquetra-native workflows and CE compatibility.
- Alias support and command collision behavior need verification.

## Recommended Survivor

The strongest direction is **candidate 3 with candidate 2 as the generic fallback**:

`/doc-review` should be a router that delegates to existing specialized Infiquetra
review surfaces when they are clearly right, and otherwise runs an Infiquetra-adapted
CE-style multi-lens document review.

Add `/ce-doc-review` as a compatibility alias if the command system supports it
cleanly after Compound Engineering is uninstalled.

## Non-Goals

- Do not clone all CE review utilities.
- Do not replace `blueprint-reviewer` rubrics.
- Do not make document review mutate files by default.
- Do not make this a generic GitHub helper or cleanup workflow.
- Do not embed long context-library content. Link to the context library as the
  durable source of truth.

## Brainstorm Seeds

Use these as the opening decision surface for `/brainstorm`:

1. Should `/doc-review` be primarily a router, a standalone generic reviewer, or both?
2. Which document classes deserve specialized handling on day one?
3. Should `/ce-doc-review` be a real compatibility alias, or should migration push users
   to `/doc-review` only?
4. What findings should block `/plan`, `/work`, or `/qa` in headless mode?
5. When should the command write `docs/reviews/` artifacts versus reporting inline only?
6. Which review lenses are mandatory, optional, or trigger-based?
7. How should issue progress comments reference a document review when work is attached
   to an SDLC issue?

## Next Step

Run a brainstorm on this question:

> Design the Infiquetra-native `/doc-review` command so it replaces the useful parts of
> `/ce-doc-review`, routes formal SDLC documents to `blueprint-reviewer`, and can act as
> a review gate inside `infiquetra-loop`.
