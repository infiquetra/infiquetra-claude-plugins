---
title: "enhancement: check_journal.py — schema-validate engineering-journal ADRs and learnings"
repo: infiquetra-claude-plugins
type: enhancement
tier: quick-win
objective: "Enforce context-library standards at authoring time"
wave: wave-2
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: medium, backend: inline, external_llm: none}
---

# enhancement: check_journal.py — schema-validate engineering-journal ADRs and learnings

### Intent
Add a `check_journal.py` CI lint that schema-validates this repo's own
`docs/engineering-journal/` — anchor uniqueness across `DECISIONS.md`/`LEARNINGS.md`, existence of
every cited cross-reference anchor, and presence of the required `revisit when` condition (in
`DECISIONS.md` entries) and commit/PR hash — turning the journal's own documented entry template
into an enforced schema instead of a convention that depends on the author remembering it.

## Problem / Motivation

- **The journal template is documented but unenforced.** `docs/engineering-journal/DECISIONS.md:3`
  states the required shape of every entry: "capture rationale + tradeoff + revisit-when condition
  + commit hash." `docs/engineering-journal/LEARNINGS.md:1-18` documents an equally explicit
  required-field template (`Context` / `Evidence` / `Mechanism` / `Fix` / `Generalizable rule` /
  `Refs`). Both are prose instructions inside the files they govern — nothing runs them. This is
  the exact shape the grounding brief's context-library survey (§4,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:75-88`) names as this org's convention
  elsewhere (`check_docs.py` schema/frontmatter lint in CI, `context_census.py --check`
  keeping `llms.txt` honest) but flags as **absent** for this repo's own journal: "any reference to
  the library from this repo's CI" is missing, and by extension so is any equivalent self-check on
  this repo's own auto-maintained artifact.
- **Anchor collisions already exist in the live file.** A live scan of
  `docs/engineering-journal/DECISIONS.md` found 94 total `{#slug}` anchors, of which at least 7
  slugs are already duplicated across separate entries (verified via `grep -oE '\{#[a-zA-Z0-9_-]+\}'
  docs/engineering-journal/DECISIONS.md | sort | uniq -d`, e.g. `{#agy-delegated-build-no-jail}`,
  `{#outcome-board-status-schema-resolve-326}`, `{#saga-docs-source-model}`). A duplicated anchor
  means a cross-reference like `` `{#saga-docs-source-model}` `` resolves ambiguously — the reader
  (or a future generator consuming these anchors, e.g. the review-lens-catalog generator work
  tracked separately) cannot tell which entry it points to.
- **Cross-references are hand-typed and never checked against a target.** `DECISIONS.md:65`
  cites `` `{#outcome-board-status-schema-resolve-326}` ``; `DECISIONS.md:215` cites
  `` `{#dead-wiring-needs-producer-and-consumer}` ``; `LEARNINGS.md`'s `Refs.` field
  (`LEARNINGS.md:1-18` template) is explicitly designed to cross-link `DECISIONS` / `QUEUED` /
  `narratives` / other `LEARNINGS` entries. None of these citations is validated against a real
  anchor — a rename, a typo, or a superseded/archived entry silently produces a dead cross-reference
  with no signal at commit time.
- **`revisit when` is required in the template but its presence is not checked.** `DECISIONS.md:3`
  requires a revisit-when condition on every entry; a live scan finds 81 occurrences of the phrase
  across 77 `###` entry headings in the file (`grep -c "###" docs/engineering-journal/DECISIONS.md`)
  — close enough to parity to show the convention mostly holds today by discipline alone, with no
  guard against the next entry that skips it.
- **This is the same failure shape the grounding brief names as the repo's #1 recurring
  consumer-side finding.** §3 of the grounding brief ranks "rename/contract-mirror drift" (a
  hand-maintained artifact silently diverging from its own declared contract, 4 independently
  recurring repos) as the top cross-repo pain. A journal entry silently missing a required field, or
  a cross-reference silently pointing nowhere, is that same failure class applied to the journal
  itself.

## Definition of Done

Merged PR delivering:

1. `plugins/saga/scripts/check_journal.py` (or a repo-root `scripts/check_journal.py` — exact
   location is `/plan`'s to determine) that parses `docs/engineering-journal/DECISIONS.md` and
   `docs/engineering-journal/LEARNINGS.md`, and for each `###`-level entry checks:
   - the entry's `{#slug}` anchor is unique across both files (no duplicate slugs);
   - every `` `{#slug}` `` cross-reference cited anywhere in either file resolves to an existing
     anchor heading;
   - every `DECISIONS.md` entry contains a revisit-when condition (a "revisit when" phrase in its
     body) and a commit/PR hash reference (e.g. a `(#NNN)` or explicit hash token in its heading or
     body).
2. A CI wiring step (this repo's existing test/lint workflow) that runs
   `check_journal.py --check` and fails the build on any violation, mirroring the
   `context_census.py --check` shape named as this org's convention in the grounding brief.
3. `tests/test_check_journal.py` exercising each check against fixture journal content.

Verify: run `check_journal.py --check` against the current `docs/engineering-journal/` tree pre-fix
and observe it reporting the live duplicate-anchor findings above as failures; after the anchors are
deduplicated (in this PR or a follow-up noted in `QUEUED.md`), the same command exits clean; a
scratch fixture with one broken cross-reference anchor and one entry missing "revisit when" reds the
check, and removing the injected fault greens it.

### Acceptance criteria
- [ ] **AC1 (T9-F3-5, primary).** A broken cross-reference anchor (a `` `{#slug}` `` citation with no
  matching heading anchor anywhere in `DECISIONS.md`/`LEARNINGS.md`) reds CI. Check: `uv run pytest
  tests/test_check_journal.py -k broken_cross_ref` → passes (asserts the checker exits non-zero on
  a fixture containing an unresolvable citation).
- [ ] **AC2 (T9-F3-5, primary).** A `DECISIONS.md` entry missing a required `revisit when` condition
  reds CI. Check: `uv run pytest tests/test_check_journal.py -k missing_revisit_when` → passes
  (asserts the checker exits non-zero on a fixture entry lacking the phrase).
- [ ] **AC3.** A `DECISIONS.md` entry missing a commit/PR hash reference reds CI. Check: `uv run pytest
  tests/test_check_journal.py -k missing_commit_hash` → passes.
- [ ] **AC4.** A duplicated `{#slug}` anchor across either file reds CI. Check: `uv run pytest
  tests/test_check_journal.py -k duplicate_anchor` → passes (fixture reproduces the shape of the
  7 live duplicates found in `DECISIONS.md` today).
- [ ] **AC5.** Running the checker against the current, unmodified `docs/engineering-journal/` tree
  surfaces the pre-existing duplicate-anchor findings as real, non-fixture failures (proving the
  checker catches live drift, not only synthetic fixtures) — resolution of those specific
  duplicates may land in this PR or be queued as a separate `QUEUED.md` follow-up item, but the
  checker must report them either way. Check: `python3 plugins/saga/scripts/check_journal.py
  --check docs/engineering-journal/` → reports the known duplicate slugs (or exits `0` if this PR
  also fixes them) with no silent pass while duplicates remain.
- [ ] **AC6.** A clean fixture (unique anchors, all cross-references resolvable, every `DECISIONS.md`
  entry carrying both a revisit-when condition and a commit/PR hash) passes with no false positives.
  Check: `uv run pytest tests/test_check_journal.py -k clean_fixture_passes` → passes.
- [ ] **AC7.** Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff
  format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:** the new `check_journal.py` checker, its CI wiring, its test suite, and (optionally)
fixing the specific live duplicate anchors found during grounding if trivial to resolve in this PR
— otherwise queuing that cleanup as a follow-up.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Pulling infiquetra-context-library content (`llms.txt`, per-topic READMEs) into this repo's
  issue/plan creation flow — a separate gap named in the grounding brief §4, addressed by other
  issues in this wave, not this one.
- Any schema/lint changes to the context-library's own `validate.yml` / `check_docs.py` /
  `context_census.py` — those already exist, already enforce the library's own journal-equivalent
  content, and are out of this repo's blast radius.
- Generating review lenses, an authority-order resolver, or any other consumer built on top of
  journal anchors — this issue only validates the journal's own internal schema; anchor-consuming
  generators (e.g. an ADR-derived review-lens catalog) are separate, already-tracked work.
- Rewriting `QUEUED.md` or `ARCHIVE.md` schemas — the DoD and acceptance criteria scope explicitly
  to `DECISIONS.md` and `LEARNINGS.md`, the two files with a documented required-field template
  today; extending the same checker to `QUEUED.md`/`ARCHIVE.md` is a natural fast-follow but not
  required here.
- A standing/scheduled drift-measurement dashboard — this is a binary CI gate (pass/fail on the
  current tree), not a tracked-over-time metric.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T9-F3-5` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged check_journal.py + CI wiring + engineering-journal frontmatter schema linting anchor-uniqueness, cited-anchor existence, and required revisit-when/commit-hash; verified by breaking one cross-ref anchor and dropping one revisit-when and watching CI go red." — this entry has a null `body`, so intent is reconstructed here from its `dod_sketch` plus the grounding brief §4/§6 context below) | primary |

**Reconstruction basis for this thin seed:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
§4 ("Standards/ADR enforcement (context library)") establishes the org convention this issue
extends to this repo's own journal — schema-validate-in-CI + self-describing index, not
runtime-injected blobs — and names as absent "any reference to the library from this repo's CI,"
which by direct extension includes this repo's own unenforced journal template. §6 ("Recurring-pain
themes") item 3, "Release-surface drift persists despite CLAUDE.md step 6 — room for automation,"
and this repo's own `DECISIONS.md:3` / `LEARNINGS.md:1-18` document the exact required-field
template this checker enforces.

**Binding decisions this issue builds on / must not contradict:**
- Standards/ADR-enforcement org convention (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §4): schema-validate-in-CI + self-describing index, not runtime-injected blobs. `check_journal.py`
  follows this shape (a CI-run static checker) rather than introducing a runtime-injection
  mechanism.
- Consumer-side signal #1, rename/contract-mirror drift (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §3): this issue applies the same "catch the silent hand-maintained drift" fix to the journal's
  own anchor/cross-reference/required-field contract.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** a bounded, mechanical parser/checker over two well-structured markdown files
  with a documented template (anchor regex extraction, cross-reference resolution, required-phrase
  presence) — no novel design or adversarial judgment required. Sonnet/medium matches the fleet's
  own work-shape heuristic for a quick-win, single-file-surface lint tool; no external-LLM chaperone
  dispatch is warranted.

## Release-Surface Checklist

This issue adds a new CI-enforced checker but does not change any plugin's user-facing behavior,
schema, command, or prompt surface — `check_journal.py` is a repo-development-tooling script, not a
skill/agent/command shipped to plugin consumers. Confirm before merge:
- [ ] If `check_journal.py` lands under `plugins/saga/scripts/` (as opposed to a repo-root
      `scripts/` path), bump `plugins/saga/.claude-plugin/plugin.json` and
      `plugins/saga/CHANGELOG.md` to reflect the added script, and keep
      `.claude-plugin/marketplace.json`'s saga entry in sync.
- [ ] If `check_journal.py` lands under a repo-root `scripts/` path instead, no plugin
      `plugin.json`/`marketplace.json`/`CHANGELOG.md` bump is required (it ships no plugin-facing
      behavior) — confirm this placement decision explicitly in the PR description so reviewers
      don't need to re-derive it.
- [ ] Drift-guard/version-metadata tests (this repo's existing marketplace/plugin-metadata drift
      tests) stay green regardless of which placement is chosen.

## Files Expected to Change

- `plugins/saga/scripts/check_journal.py` — new checker (or `scripts/check_journal.py` at repo
  root; final path is `/plan`'s to determine — see Release-Surface Checklist).
- `.github/workflows/` (this repo's existing CI test/lint workflow file) — new
  `check_journal.py --check` step.
- `tests/test_check_journal.py` — new fixture-driven tests.
- `docs/engineering-journal/DECISIONS.md` — only if this PR also resolves the live duplicate
  anchors found during grounding; otherwise a `QUEUED.md` entry noting the deferred cleanup.

## Tests to Add or Update

- `tests/test_check_journal.py::test_broken_cross_ref` — an unresolvable `{#slug}` citation reds
  the checker.
- `tests/test_check_journal.py::test_missing_revisit_when` — a `DECISIONS.md` entry lacking
  "revisit when" reds the checker.
- `tests/test_check_journal.py::test_missing_commit_hash` — a `DECISIONS.md` entry lacking a
  commit/PR hash reference reds the checker.
- `tests/test_check_journal.py::test_duplicate_anchor` — a duplicated `{#slug}` across either file
  reds the checker.
- `tests/test_check_journal.py::test_clean_fixture_passes` — a fully compliant fixture passes with
  no false positives.

### Verification
```bash
# New journal-schema checker suite
uv run pytest tests/test_check_journal.py -v

# Run the checker against the live journal tree (surfaces the known duplicate-anchor findings)
python3 plugins/saga/scripts/check_journal.py --check docs/engineering-journal/

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; a scratch fixture with one broken cross-reference anchor and one entry
missing "revisit when" turns the checker red; removing the injected fault turns it green again; the
live-tree run against `docs/engineering-journal/` surfaces (or, if fixed in this PR, no longer
surfaces) the 7 duplicate-slug findings identified during grounding.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (id `T9-F3-5`)
- Source type: ideation survivor (thin seed, null body) + issue-map consolidation +
  grounding-brief reconstruction
- Source title: check_journal.py — schema-validate engineering-journal ADRs and learnings

### Context library links

_none_

### Files expected to change

- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/scripts/check_journal.py`
- `scripts/check_journal.py`
- `docs/engineering-journal/LEARNINGS.md`
- `tests/test_check_journal.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_check_journal.py`

### Objective

"Enforce context-library standards at authoring time"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/407
- Number: 407
- Created at: 2026-07-04T08:03:44.227209+00:00

