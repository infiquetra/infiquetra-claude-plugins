# Lens Catalog

The canonical lens catalog is the versioned JSON roster at
`plugins/saga/references/lens-roster.json`. That file is the only source of lens identifiers,
selection classes, judgment guidance, dimensions, score anchors, acceptance rules, implementation
mappings, and reviewer authority. This document explains how Code Review executes that contract. It
does not carry a second roster or restate numeric policy.

## Load the canonical roster

Before selecting or running any lens:

1. Read `plugins/saga/references/lens-roster.json` as JSON.
2. Require the exact schema named by that artifact.
3. Refuse an unknown schema rather than guessing at compatibility.
4. Require each lens identifier to be unique.
5. Require each dimension identifier to be unique within its lens.
6. Require both implementation mappings named by the roster.
7. Require every referenced procedure and Team Execution agent path to exist.

A parse, schema, uniqueness, or parity failure blocks review startup. A consumer must not fall back
to a private list, the historical catalog prose, or Team Execution's old keyword registry.

## Select lenses from the diff

Read the full merge-base diff before selection. Auto-run every roster entry whose trigger class is
`always-on` — exactly `architecture-maintainability`, `correctness`, `security`, and `testing`.
Those four launch with no operator question. For a `conditional` entry, use the roster's judgment
guidance and the actual changed behavior, not filename or keyword matching alone, and treat the
result as a **recommendation**, not a launch.

Record one concise reason for each recommended conditional lens. The reason names the material
review surface in this diff. Do not recommend a conditional lens when there is no applicable
dimension merely to increase reviewer count. Do not omit one because another selected lens overlaps
it.

The roster `selection_contract` is the launch gate. Before any conditional Agent call: present one
batched operator choice (`accept-recommended` default / `always-on-only` / `customize`), combined
with backend selection when the client supports it. A caller- or Orchestrate-supplied selection is
approval and is not re-asked. Persist the approved set on the existing review-cycle state against
the reviewed commit and cycle. Reuse it on repair cycles unless applicability changes, then ask
once about only the delta. Dismissal or no answer pauses — no conditional launches, no hidden or
supplemental lenses. Issue #418's selection adapter produces candidates only; it cannot approve.

Keep the stable identifiers from the roster in dispatch requests, results, cycle state, and reports.

## Run a roster scoring lens

`roster-scoring-lens` is the executable Code Review procedure referenced by every roster mapping:

1. Bind the selected lens identifier and reviewed commit before reading findings.
2. Load that lens's focus, dimensions, anchor bands, and Code Review mapping from the roster.
3. Evaluate applicability dimension by dimension against the diff and relevant code outside it.
4. For a non-applicable dimension, record the concrete precondition that is absent.
5. Refuse a selected lens when no dimension remains applicable.
6. Score each applicable dimension using that dimension's complete anchor definitions and evidence.
7. Derive any overall score from applicable dimensions; never ask a reviewer to invent policy.
8. Return findings in `findings-schema.md` form with the lens identifier and dimension identifier.
9. Bind the result to the commit actually reviewed.
10. Preserve unverified facts as unverified; lack of evidence is not a passing score.

The Code Review procedure remains read-only. It reports repairs through structured findings and never
changes the reviewed tree.

## Applicability discipline

Applicability is about whether a dimension's precondition exists in the reviewed change. It is not a
way to hide weak evidence or improve an average. A cause must name the absent precondition, such as
"no persisted personal data" or "no human-operated surface". Bare `N/A`, `none`, or an empty cause is
invalid.

When a dimension is applicable, score it even when another lens covers similar evidence. Independent
overlap is merged later as cross-reviewer agreement, not discarded during selection.

## Implementation parity

The `code_review` mapping names this procedure and its file. The `team_execution` mapping names an
installed Team Execution agent file. Both are required even when several lenses legitimately reuse a
generalist agent. A missing mapping, nonexistent file, or mismatched procedure identifier is a roster
parity failure.

Team Execution may transport and coordinate the mapped agent. It must carry the roster lens and
dimension identifiers unchanged and must not substitute its historical reviewer registry as policy.

## Findings and agreement

Use the roster's fingerprint fields when consolidating findings. Merge matching fingerprints into one
finding and record all agreeing lens identifiers. Agreement strengthens evidence; it does not count
the same defect twice. A disagreement about routing keeps the more conservative supported route until
stronger evidence resolves it.

Finding priority and confidence remain metadata described by `findings-schema.md`. Review acceptance
comes only from the roster's declared acceptance rules.

## Non-scoring participants

Read reviewer authority from `participant_defaults` in the roster. The external advisory seat and a
custom reviewer use their declared defaults; neither silently enters scoring, the consensus
denominator, or acceptance rules. Only an explicit policy grant can change custom-reviewer voting
authority.

Advisory findings still enter normal fingerprint deduplication and adjudication. Advisory authority
does not make the evidence disposable and does not turn an opinion into a score.

## Historical name compatibility

Old prose used `maintainability / conventions` for what the roster now identifies as
`architecture-maintainability`, and `deploy/migration-verification` for
`deployment-infrastructure`. It also used `adversarial / red-team` and `agent-native`; their stable
roster identifiers are `adversarial` and `agent-usability`. The identifiers `correctness`, `security`,
`testing`, `reliability`, `performance`, and `api-contract` remain stable.

These aliases are read-only migration guidance. Never emit them as current lens identifiers and never
construct a roster from this paragraph.

## Policy-source boundary

Live policy consumers point to `lens-roster.json`. Changelogs, engineering-journal entries, and review
artifacts may quote historical policy without becoming live consumers or a second roster. Parity
checks must distinguish those historical records from executable skills, references, scripts, and
agent contracts.

If a live consumer needs a threshold, dimension, anchor, selection rule, or reviewer authority, it
loads that value from the roster. It must not copy the value into prose, code, or another registry.

## Related contracts

- `findings-schema.md` defines finding evidence, fingerprinting, confidence, ownership, and output.
- `validator.md` defines independent per-finding validation.
- `built-vs-planned.md` defines the separate plan-completion audit; it is not a scoring lens.
- The Code Review skill owns fan-out, consolidation, validation, reporting, and routing around this
  roster-driven procedure.
