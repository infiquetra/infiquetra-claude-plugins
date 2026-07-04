---
title: "enhancement: extend source-stale claim provenance from delegated outputs to standing docs"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Make the backlog and lifecycle self-improving"
wave: wave-3
---

# enhancement: extend source-stale claim provenance from delegated outputs to standing docs

## Problem / motivation

`plugins/saga/scripts/provenance_manifest.py` already carries a `mismatch_reason` vocabulary
for claims made about *delegated execution outputs*: `not-adjudicated | scope-excluded |
source-stale | unsupported | refuted` (`provenance_manifest.py:79-86`, `MismatchReason`
enum). `source-stale` specifically exists to mark a claim whose supporting anchor moved out
from under it (`provenance_manifest.py:24`, "`not-adjudicated`, `scope-excluded`, and
`source-stale` never count [as parroting]"). Today this vocabulary is scoped to one
producer-vs-adjudicated claim pair per delegated unit — it has no reach into the repo's
*standing* documents (`CLAUDE.md`, `SKILL.md` files, `docs/engineering-journal/*.md`), which
make load-bearing claims about file:line anchors, versions, and behavior that also go stale
over time, with no mechanism to detect it:

- `docs/engineering-journal/DECISIONS.md:438-444` (`{#manifest-parroting-pure-predicate}`)
  states its own revisit condition: "the taxonomy grows a case that depends on runtime state
  (e.g. a live source-freshness check) — then `is_parroting` needs an injectable
  clock/fetcher seam instead of staying pure." Standing-doc staleness is exactly that case —
  a claim like "see `X.py:180`" is only true as long as `X.py:180` still says what the claim
  asserts, which is runtime state, not a fixed fact.
- `docs/engineering-journal/LEARNINGS.md:588` (`{#plugin-release-metadata-is-a-release-surface}`)
  records a concrete moved-anchor failure: PR #224 moved the vendored schema from a Mount
  Olympus model to a Jeff Intent / Asgard / CAMPPS model, but `plugin.json`,
  `marketplace.json`, and `CHANGELOG.md` kept describing the old model — nothing caught the
  drift until a follow-up PR (#225) fixed it manually.
- `docs/engineering-journal/LEARNINGS.md:101-112` (`{#issue-premises-drift-314}`) records the
  inverse failure: an open issue's premise ("`assert leaked == []`" needs a
  `pytest_sessionstart` baseline) had already been satisfied by unrelated work
  (`tests/test_saga_saga.py:1346-1364`, landed in commit `e901ae1`) — the issue's own claim
  went stale and nothing flagged it, so it stayed open describing code that no longer
  existed.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 6, point 2: "Provenance/status
  claims must be re-verified against current state (4 learnings)" — a named recurring-pain
  theme distinct from delegation-output provenance, which is already covered by
  `provenance_manifest.py`.

No component today stamps a standing-doc claim (a CLAUDE.md instruction, a SKILL.md
reference, a journal entry's `file:line` citation) with a source anchor and a freshness
check, so these claims silently rot exactly the way delegated-output claims used to before
`provenance_manifest.py` existed.

## Definition of Done

A merged PR that ships `provenance_lint.py`, extending the existing
`provenance_manifest.py` `mismatch_reason` vocabulary (`not-adjudicated | scope-excluded |
source-stale | unsupported | refuted`) to standing-doc claims:

1. A **claim-extraction pass** that scans `CLAUDE.md`, `**/SKILL.md`, and
   `docs/engineering-journal/{LEARNINGS,DECISIONS}.md` for anchor-bearing claims — at
   minimum, `` `path/to/file.py:NNN` `` and `` `path/to/file.py:NNN-MMM` `` style citations —
   and stamps each with the source anchor it depends on.
2. A **TTL field** on each stamped claim (a claim age past which it must be re-verified even
   if the anchor still resolves, matching the `source-stale` semantics already defined at
   `provenance_manifest.py:79-86` rather than inventing a parallel vocabulary).
3. A **CI/pre-commit hook** that runs `provenance_lint.py` and fails loud (non-zero exit,
   named reason per claim) on any claim whose anchor no longer resolves at the cited
   location, or whose TTL has expired.
4. Reuse, not duplication, of the `MismatchReason` enum and its `source-stale` value as the
   classification a lint failure reports — a standing-doc claim flagged by this lint reports
   `mismatch_reason=source-stale`, the same vocabulary a delegated-output claim already uses.

### Acceptance criteria
- [ ] AC1. A seeded claim whose cited anchor has moved (the cited `file:line` no longer contains
  the text the claim depends on, analogous to the `docs/engineering-journal/LEARNINGS.md:588`
  moved-schema case) is flagged by `provenance_lint.py` with `mismatch_reason=source-stale`.
  Check: `uv run pytest tests/test_provenance_lint.py -k moved_anchor` → passes, asserting the
  lint's reported reason equals `source-stale` for the fixture claim.
- [ ] AC2. A seeded claim whose TTL has expired (anchor still resolves, but the claim is older
  than its declared re-verification window) is flagged, distinct from a moved-anchor flag.
  Check: `uv run pytest tests/test_provenance_lint.py -k ttl_expired` → passes, asserting the
  lint flags the fixture and reports a TTL-expiry reason.
- [ ] AC3. A seeded claim whose anchor is live (resolves at the cited location, TTL not expired)
  passes the lint with no flag. Check: `uv run pytest tests/test_provenance_lint.py -k
  live_anchor_passes` → passes, asserting zero flags for the fixture.
- [ ] AC4. `provenance_lint.py` imports and reuses `provenance_manifest.MismatchReason` (or an
  equivalent shared enum) rather than defining its own parallel vocabulary. Check: `grep -n
  "from.*provenance_manifest import\|import provenance_manifest" plugins/saga/scripts/provenance_lint.py`
  → non-empty match.
- [ ] AC5. The lint is wired into CI or pre-commit (at least one enforcement point, not merely a
  script that exists unused). Check: `grep -rn "provenance_lint" .pre-commit-config.yaml
  .github/workflows/*.yml 2>/dev/null` → non-empty match.

### Out-of-scope / non-goals
In scope:
- Extending the existing `mismatch_reason` vocabulary (`provenance_manifest.py`) to
  standing-doc claims — reusing `source-stale` and its sibling values, not inventing a new
  taxonomy.
- Claim extraction and anchor/TTL checking for `CLAUDE.md`, `SKILL.md` files, and the
  engineering-journal `LEARNINGS.md` / `DECISIONS.md` files specifically (the files named in
  the slug and in the grounding brief's recurring-pain theme).
- One CI/pre-commit enforcement point that fails loud on a flagged claim.

Out of scope (deliberately deferred — do not build in this issue):
- Auto-fixing or auto-rewriting stale claims — this issue only detects and flags; repair
  stays a human/agent follow-up action.
- Extending the lint to every markdown file in the repo (README, plan docs, brainstorms) —
  v1 scopes to the standing-doc surfaces named above; broadening coverage is a fast-follow.
- Changing `provenance_manifest.py`'s delegated-output semantics or its parroting-detection
  logic (`is_parroting`, KTD5/R7) — this issue is additive (new consumer of the existing
  vocabulary), not a rework of the delegated-output path.
- A live, continuously running staleness daemon — the lint runs at CI/pre-commit time
  (event-triggered), not as a standing schedule, matching the repo's stated preference for
  derive-on-read over committed/scheduled state (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  section 6, point 5).

## Grounding References

- T10-F3-5 (primary, absorbed) — "Extend the source-stale provenance status from delegated
  outputs to standing docs." Basis: direct extension of the existing
  `provenance_manifest.py` `mismatch_reason` vocabulary; the DoD sketch specifies
  `provenance_lint.py` stamping claims with source anchors + TTL, run in CI/precommit,
  verified by a seeded moved-anchor claim and a TTL-expired claim both flagged while a
  live-anchor claim passes.
- `{#manifest-parroting-pure-predicate}` (DECISIONS.md:438-444, #285 KTD5) — binding decision
  this issue builds on: the `is_parroting` predicate stays pure only until the taxonomy
  needs a runtime-state check; this issue is that revisit condition, applied to standing
  docs rather than to `is_parroting` itself, so it must not retrofit a runtime clock/fetcher
  seam into the delegated-output predicate as a side effect.
- `{#plugin-release-metadata-is-a-release-surface}` (LEARNINGS.md:588, PR #224/#225) —
  concrete moved-anchor precedent motivating AC1.
- `{#issue-premises-drift-314}` (LEARNINGS.md:101-112) — concrete stale-issue-premise
  precedent motivating the standing-doc scope (issue bodies and journal claims rot the same
  way source-code citations do).
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 6, point 2 — "Provenance/status
  claims must be re-verified against current state (4 learnings)," the named recurring-pain
  theme this issue closes.

## Recommended executor profile

- Model: sonnet. Effort: medium. Backend: inline. External LLM: none.
- Justification: this is a bounded, mechanical extension of an existing, already-tested
  enum and vocabulary (`provenance_manifest.MismatchReason`) into a new consumer (a
  standalone lint script) with well-specified fixture-driven acceptance criteria — no
  open-ended design or adversarial judgment call that would justify stepping above sonnet.

## Release-surface checklist

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump if `provenance_lint.py`
      ships as part of the `saga` plugin's scripts and changes its installed behavior.
- [ ] `.claude-plugin/marketplace.json` — entry updated to match any `saga` version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the new `provenance_lint.py`
      standing-doc claim check and its CI/pre-commit wiring.
- [ ] Any drift-guard test (marketplace-metadata-vs-plugin.json parity test) still green
      after the version bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording the choice to reuse
      `MismatchReason`/`source-stale` for standing-doc claims rather than mint a parallel
      vocabulary, and the rejected alternative (a separate doc-staleness enum).

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.

- `plugins/saga/scripts/provenance_lint.py` (new) — claim extraction, anchor/TTL check,
  CLI entry point.
- `plugins/saga/scripts/provenance_manifest.py` — no semantic change expected; imported by
  the new lint for its `MismatchReason` enum.
- `tests/test_provenance_lint.py` (new) — moved-anchor, TTL-expired, live-anchor-passes
  fixtures.
- `.pre-commit-config.yaml` and/or `.github/workflows/*.yml` — wiring the lint into an
  enforcement point.
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface parity per the checklist above.

### Verification
```bash
# New lint unit tests
uv run pytest tests/test_provenance_lint.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the moved-anchor fixture reports `mismatch_reason=source-stale`, the
TTL-expired fixture is flagged with a distinct expiry reason, and the live-anchor fixture
passes with zero flags.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json (id T10-F3-5)
- Source type: ideation survivor map
- Source title: Extend the source-stale provenance status from delegated outputs to standing docs

### Intent

`plugins/saga/scripts/provenance_manifest.py` already carries a `mismatch_reason` vocabulary for claims made about *delegated execution outputs*: `not-adjudicated | scope-excluded | source-stale | unsupported | refuted` (`provenance_manifest.py:79-86`, `MismatchReason` enum). `source-stale` specifically exists to mark a claim whose supporting anchor moved out from under it (`provenance_manifest.py:24`, "`not-adjudicated`, `scope-excluded`, and `source-stale` never count [as parroting]"). Today this vocabulary is scoped to one producer-vs-adjudicated claim pair per delegated unit — it has no reach into the repo's *standing* documents (`CLAUDE.md`, `SKILL.md` files, `docs/engineering-journal/*.md`), which make load-bearing claims about file:line anchors, versions, and behavior that also go stale over time, with no mechanism to detect it:

### Context library links

_none_

### Tests to add or update

- `tests/test_provenance_lint.py`
- `tests/test_saga_saga.py`

### Objective

"Make the backlog and lifecycle self-improving"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/448
- Number: 448
- Created at: 2026-07-04T08:17:05.107812+00:00

