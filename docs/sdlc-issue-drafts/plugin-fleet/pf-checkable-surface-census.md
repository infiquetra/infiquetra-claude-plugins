---
title: "enhancement: checkable-surface census + always-on mermaid CI gate"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
tier: quick-win
objective: Enforce context-library standards at authoring time
wave: wave-2
---

# enhancement: checkable-surface census + always-on mermaid CI gate

### Intent
This repository's CI (`.github/workflows/ci.yml`) validates plugin manifests, the marketplace
registry, lint, and types, but nothing in the pipeline ever parses the mermaid fences embedded in
plugin docs (for example `plugins/redis-channel/ARCHITECTURE.md:13`) or systematically enumerates
which *other* embedded-content classes (JSON/YAML fences, bash snippets, cross-repo anchor
references) are validated versus silently trusted. The recurring-pain record for this ideation
cycle is explicit: "mermaid syntax never validated by check_docs.py (13 broken diagrams shipped)"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:187`, section 7 singleton list), and the
sister context-library repo's own enforcement pattern is "schema-validate-in-CI + self-describing
index" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`, section 4) — a pattern this
repo does not yet apply to its embedded diagrams or to any other checkable surface.

Today the gap is not just "mermaid is unvalidated" — it is that nobody has enumerated *which*
embedded-content classes in this repo's docs are validated and which are not, so new unvalidated
classes can be introduced silently and nobody notices until something breaks in production (a
broken diagram, a copy-pasted bash snippet with a typo, a cross-repo anchor link that 404s). This
issue ships both: (1) mermaid as the first always-validated class (closing the specific 13-diagram
blind spot), and (2) a committed, machine-readable census (`checkable-surface.json`) that
classifies every embedded checkable surface as `validated` or `unvalidated`, so future PRs that
introduce a new unvalidated fence class are flagged by CI rather than discovered later.

## Problem Frame

- CI today (`.github/workflows/ci.yml:53-75`) runs `scripts/validate_plugins.py`,
  `marketplace/validator/validate.py`, ruff lint, ruff format, and mypy — none of these touch
  markdown-embedded content.
- At least one mermaid fence exists in tracked, non-worktree docs today (for example
  `plugins/redis-channel/ARCHITECTURE.md:13`), and there is no static pre-parse step confirming it
  is syntactically valid mermaid.
- The grounding brief's recurring-pain synthesis names this exact blind spot as a singleton finding
  carried forward from prior sessions: "mermaid syntax never validated by check_docs.py (13 broken
  diagrams shipped)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:187`).
- The brief also documents that the sibling context-library repo already enforces the general
  principle this issue extends — "org convention is schema-validate-in-CI + self-describing index,
  not runtime-injected blobs" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`) — but
  this repo (infiquetra-claude-plugins) has no equivalent mechanism for embedded checkable content,
  and no census of what its own checkable surfaces even are.
- Without an enumerated census, the mermaid fix only ever closes today's known gap; the next novel
  embedded-content class (a new fenced language, a new cross-repo anchor convention) has no
  drift-detection mechanism and will silently ship broken until someone notices by hand, repeating
  the same failure mode.

## Requirements

R1. A `checkable_surface_census.py` script exists that scans repository markdown for embedded
content classes (at minimum: mermaid fences, JSON/YAML fences, bash/shell fences, and cross-repo
anchor references) and classifies each discovered class as `validated` or `unvalidated`.

R2. The census's output is committed as `checkable-surface.json`, a versioned artifact enumerating
every discovered checkable-surface class with its validation status, so drift (a new unvalidated
class appearing) is visible in diff review, not just in a CI log.

R3. Mermaid fences are promoted to `validated` in the census and enforced via a non-opt-in
(always-on, not nightly-only, not label-gated) CI step that statically pre-parses every mermaid
fence in tracked markdown and fails the build on syntax error.

R4. CI re-generates the census on each run and diffs it against the committed
`checkable-surface.json`; if a newly discovered checkable-surface class is not already marked
`validated` in the committed file, the CI step reports it as unvalidated drift (a visible warning
or failure, per the chosen enforcement mode — see Scope Boundaries) rather than silently passing.

R5. A deliberately broken mermaid diagram (introduced as a test fixture or a self-test mode) fails
the default CI path — not a nightly-only or opt-in path.

## Definition of Done

`checkable_surface_census.py` scans repository markdown, classifies each discovered embedded-content
class (mermaid, JSON/YAML fences, bash/shell fences, cross-repo anchor references) as `validated` or
`unvalidated`, and commits its output as `checkable-surface.json`. Mermaid is promoted to `validated`
and enforced via a non-opt-in CI step that pre-parses every tracked mermaid fence and fails the
default CI path on syntax error. CI regenerates the census on each run and flags any newly
discovered, not-yet-validated class as drift rather than silently passing.

## Key Flows

F1. **Normal PR, no new checkable-surface class.** A PR touches docs but introduces no new fenced
content type. CI regenerates the census, diffs it against the committed file, finds no new
unvalidated classes, runs the mermaid pre-parse over all fences, and passes. **Covers R1, R2, R4.**

F2. **PR introduces a broken mermaid diagram.** A PR adds or edits a `` ```mermaid `` fence with
invalid syntax. The always-on mermaid pre-parse step fails the default CI path (not a nightly-only
path). **Covers R3, R5.**

F3. **PR introduces a novel unvalidated fence class.** A PR adds a new kind of embedded checkable
content that the census has never seen before (for example a new templating-language fence). The
regenerated census disagrees with the committed `checkable-surface.json`, and CI flags the new
class as unvalidated drift for the author to either validate or explicitly waive/commit as a known
unvalidated class. **Covers R1, R2, R4.**

### Acceptance criteria
- [ ] AC1. **Covers R3, R5.** Given a markdown file containing a deliberately malformed
  `` ```mermaid `` fence (for example unbalanced brackets), running the CI mermaid pre-parse step
  fails with a non-zero exit code on the default (non-opt-in) CI path. Check:
  `uv run python plugins/<owning-plugin-or-scripts>/checkable_surface_census.py --check-mermaid
  tests/fixtures/broken-mermaid.md` → exits non-zero, output names the offending file/fence.
- [ ] AC2. **Covers R1, R3.** Given the current tracked mermaid fences (for example
  `plugins/redis-channel/ARCHITECTURE.md:13`), running the mermaid pre-parse step over the full
  repository exits zero. Check: `uv run pytest tests/test_checkable_surface_census.py -k
  mermaid_valid_repo_passes` → passes.
- [ ] AC3. **Covers R1, R2.** Running `checkable_surface_census.py` against the repository produces a
  `checkable-surface.json` enumerating at minimum mermaid fences, JSON/YAML fences, bash/shell
  fences, and cross-repo anchor references, each tagged `validated` or `unvalidated`. Check:
  `uv run python scripts/checkable_surface_census.py --write checkable-surface.json && python3 -c
  "import json; d=json.load(open('checkable-surface.json')); assert 'mermaid' in
  [c['class'] for c in d['classes']]"` → succeeds.
- [ ] AC4. **Covers R1, R2, R4.** Given a novel fenced-content class not present in the committed
  `checkable-surface.json` (introduced via a test fixture), regenerating the census and diffing
  against the committed file flags the new class as unvalidated drift. Check: `uv run pytest
  tests/test_checkable_surface_census.py -k novel_class_flagged_as_drift` → passes.
- [ ] AC5. **Covers R2.** The committed `checkable-surface.json` is present in the repository root (or
  the agreed location) and is checked into version control, not generated-and-discarded at CI time
  only. Check: `git ls-files checkable-surface.json` → returns the path.
- [ ] AC6. **Covers R4.** CI wires the census-diff step into the default `validate` job in
  `.github/workflows/ci.yml` (non-opt-in), alongside the existing `validate_plugins.py` and
  marketplace-validator steps. Check: `grep -n "checkable_surface_census" .github/workflows/ci.yml`
  → matches found in the `validate` job.

### Out-of-scope / non-goals
- v1 ships mermaid as the *only* fully `validated` (enforced-failure) class. JSON/YAML fences, bash
  snippets, and cross-repo anchor references are enumerated by the census but may remain
  `unvalidated` in v1 — the census's job is visibility and drift-detection, not validating every
  class in one pass. Promoting additional classes to `validated` is explicit future work.
- v1 does not backfill or retroactively validate every historical mermaid diagram beyond confirming
  the current tracked set parses; it establishes the always-on gate going forward.
- v1 does not attempt heavy mermaid rendering (`mmdc`/Puppeteer-based render-to-image); it performs
  a fast static syntax pre-parse only. A heavier nightly render pass, if wanted, is out of scope
  here.
- v1 does not build a generic pluggable-validator framework for arbitrary future fence types beyond
  what's needed to enumerate and diff the census; it wires mermaid's validator and leaves the
  census extensible for future classes to plug in.
- This issue does not touch the context-library repo's own `check_docs.py`; it establishes the
  equivalent enforcement inside infiquetra-claude-plugins's own CI, independently.

### Files expected to change
- `scripts/checkable_surface_census.py` — new script: scans markdown, classifies embedded checkable
  surfaces, emits/diffs `checkable-surface.json`.
- `checkable-surface.json` — new committed artifact enumerating checkable-surface classes and their
  validated/unvalidated status.
- `.github/workflows/ci.yml` — new non-opt-in step in the `validate` job wiring the mermaid
  pre-parse and census-diff check.
- `tests/test_checkable_surface_census.py` — new test file: broken-mermaid fixture fails,
  valid-repo mermaid passes, novel-class drift is flagged.
- `tests/fixtures/broken-mermaid.md` — new fixture: deliberately malformed mermaid fence.

### Tests to add or update
- `tests/test_checkable_surface_census.py::test_mermaid_valid_repo_passes` — the current tracked
  mermaid fences (for example `plugins/redis-channel/ARCHITECTURE.md:13`) parse cleanly.
- `tests/test_checkable_surface_census.py::test_broken_mermaid_fails_default_ci_path` — a
  deliberately malformed mermaid fixture fails the check on the default (non-opt-in) path.
- `tests/test_checkable_surface_census.py::test_novel_class_flagged_as_drift` — introducing a fence
  class absent from the committed `checkable-surface.json` is flagged rather than silently passing.

### Verification
```bash
# New census + mermaid gate tests
uv run pytest tests/test_checkable_surface_census.py -v

# Broken-mermaid fixture must fail the default (non-opt-in) path
uv run python scripts/checkable_surface_census.py --check-mermaid tests/fixtures/broken-mermaid.md; test $? -ne 0

# Census enumerates classes and is committed
uv run python scripts/checkable_surface_census.py --write checkable-surface.json
git diff --stat checkable-surface.json

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the broken-mermaid fixture check exits non-zero; `checkable-surface.json`
exists and enumerates mermaid as `validated`.

## Release-surface checklist

This issue adds a new CI-enforced behavior (embedded-content validation) but does not change any
plugin's runtime skill/agent/command behavior, so most plugin release surfaces are not implicated.
Confirm before merge:

- [ ] No `plugins/*/​.claude-plugin/plugin.json` version bump required — this change lives in
      repo-root `scripts/` and `.github/workflows/ci.yml`, not inside a versioned plugin package.
      If the census script is instead placed inside an existing plugin (for example as a
      `mission-control` or `saga` utility), bump that plugin's `plugin.json` version and update
      `.claude-plugin/marketplace.json` accordingly.
  - [ ] If placed inside a plugin: `plugins/<plugin>/CHANGELOG.md` gets an entry describing the new
        census script and CI gate.
  - [ ] If placed inside a plugin: any version/metadata drift-guard tests (for example
        `tests/test_issue_contract_parity.py`-style parity checks) are updated to cover the new
        file.
- [ ] `checkable-surface.json` is committed at repo root (or documented location) and reviewed as
      part of the PR diff, not auto-generated and gitignored.

## Grounding References

- Absorbed idea `T9-F3-7` — "Checkable-surface census — guard the blind spot, not just mermaid"
  (role: primary). Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`. DoD
  sketch: "Merged `checkable_surface_census.py` + committed `checkable-surface.json` enumerating
  every embedded content class (mermaid, json/yaml fences, bash snippets, cross-repo anchor refs)
  as validated|unvalidated + CI wire; verified by introducing a novel fenced-block class and
  watching the census flag it unvalidated-drift until validated or waived." This drives R1, R2, R4
  and AC3, AC4.
- Absorbed idea `T9-F1-6` — "Make mermaid render a non-opt-in CI gate (close the 13-diagram blind
  spot)" (role: facet). Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`. DoD
  sketch: "Merged `check_docs.py` fast static mermaid pre-parse wired always-on in CI (heavy `mmdc`
  render kept nightly) + a mirrored guard in plugins-repo CI; verified by a deliberately broken
  diagram failing the default CI path." This drives R3, R5 and AC1, AC2, AC6.
- Consolidation rationale (issue map): "The 13-broken-diagram mermaid gap is one instance of the
  general blind spot the census enumerates; ship the census with mermaid as its first
  always-validated class." — hence this issue ships both facets together rather than as two
  separate issues.
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:187` (section 7,
  recurring singleton finding) — "mermaid syntax never validated by check_docs.py (13 broken
  diagrams shipped)."
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77` (section 4) — binding
  convention this issue extends into infiquetra-claude-plugins: "org convention is
  schema-validate-in-CI + self-describing index, not runtime-injected blobs."
- Existing CI baseline this issue extends: `.github/workflows/ci.yml:53-75` (the `validate` job
  running `scripts/validate_plugins.py` and `marketplace/validator/validate.py`), confirmed via
  direct read of the workflow file during grounding for this draft.
- Existing tracked mermaid fence confirmed present at grounding time:
  `plugins/redis-channel/ARCHITECTURE.md:13`.

## Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is a quick-win, mechanically scoped change — a new static-analysis script,
  a committed JSON artifact, and one CI wiring step — with no architectural ambiguity or
  cross-repo coordination. It matches the fleet's tiering guidance (mechanical/deterministic work →
  sonnet, no elevated model needed) and does not require opus-level judgment or an external-LLM
  posture.

## Handoff maturity

requirements-ready

## Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (ids `T9-F3-7`,
  `T9-F1-6`)
- Source type: ideation survivor absorption (issue-map)
- Source title: Checkable-surface census + always-on mermaid CI gate

### Context library links

_none_

### Objective

Enforce context-library standards at authoring time

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/405
- Number: 405
- Created at: 2026-07-04T08:03:05.621479+00:00

