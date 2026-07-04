---
title: "enhancement: single-source release surfaces — generate marketplace.json from plugin.json, tri-lock parity, diff-aware bump guard, canonical CHANGELOG grammar"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Gate fleet integrity (agent files, prompts, release surfaces)
wave: wave-2
---

# enhancement: single-source release surfaces — generate marketplace.json from plugin.json, tri-lock parity, diff-aware bump guard, canonical CHANGELOG grammar

### Objective

Stop guarding the copies and generate them instead: make each plugin's `plugin.json` the single
source of truth for its release surfaces, mechanically deriving `.claude-plugin/marketplace.json`
entries from it, and back that generator with three enforcement layers — a parity gate proving
`plugin.json` == marketplace entry == top `CHANGELOG.md` heading, a diff-aware guard that fails
any PR touching a plugin's non-doc files without a matching version/CHANGELOG bump, and a single
canonical CHANGELOG heading grammar replacing the fleet's four divergent formats.

### Problem / motivation

The fleet has shipped the exact drift bug this issue prevents at least twice already, and today's
release surfaces are hand-maintained copies with no single source of truth.

- **The drift bug has already shipped twice in a row and required a third PR to fix.**
  `docs/engineering-journal/LEARNINGS.md:1516-1533` (`{#marketplace-drift}`) records that
  `blueprint-reviewer`'s plugin code landed in PR #110 and PR #111 without the corresponding
  one-line `.claude-plugin/marketplace.json` registry entry — "reviewers don't see absences" —
  and a third PR (#112) was needed just to add the missing entry. `docs/engineering-journal/
  QUEUED.md:176-190` (`{#marketplace-ci-guard}`) queues a P1 fix for exactly this: "the bug it
  prevents has shipped twice in a row (PRs #110, #111) ... will recur with every new plugin or
  rename."
- **Every release surface today is a hand-copy, not a generated artifact.** `.claude-plugin/
  marketplace.json:1-40` hand-duplicates each plugin's `name`, `version`, `description`, `author`,
  `keywords`, and `category` — fields that already exist as the source of truth in that plugin's
  own `plugins/<name>/.claude-plugin/plugin.json`. Nothing generates the mirror; nothing asserts
  the mirror still matches its source after either file changes independently.
- **The fleet's own CHANGELOG grammar has already fractured into (at least) four formats.**
  Verified directly across the 8-plugin fleet's `CHANGELOG.md` files: `plugins/agy/CHANGELOG.md`
  uses `## [0.1.0] - 2026-06-30`; `plugins/deploy/CHANGELOG.md` uses `## 0.1.2 - 2026-06-21` (no
  brackets); `plugins/team-execution/CHANGELOG.md` titles itself `# Changelog - team-execution`
  (with a leading plugin-name suffix no other plugin uses); `plugins/redis-channel/CHANGELOG.md`
  links out to Keep a Changelog / SemVer conventions in its header prose that the other seven
  plugins' files don't carry. A parser or lint rule written against any one of these shapes
  silently fails on the other three.
- **`{#marketplace-ci-guard}`'s own spec sketch is a guard, not a generator, and this issue
  explicitly supersedes that framing.** The queued seed (`docs/engineering-journal/
  QUEUED.md:176-190`) proposes walking `plugins/*/` and asserting set-equality against
  `marketplace.json` by hand-authored comparison logic on both sides. This issue's consolidation
  rationale (from the issue-map) is explicit that the keeper idea "subsumes the tri-lock and
  marketplace-guard seed" because guarding two independently hand-maintained copies for parity is
  strictly weaker than making one of them generated: a generator can't drift from its own source
  by construction, whereas a guard over two hand-copies only catches drift after the fact, one
  comparison rule at a time.
- **The fleet has no diff-aware bump guard today.** Nothing in CI or `tests/
  test_marketplace_hook.py` (which validates JSON well-formedness on write, not
  version/CHANGELOG-bump discipline) asserts that a PR touching a plugin's skill, agent, or
  command files also bumps that plugin's `plugin.json` version and `CHANGELOG.md`. A `SKILL.md`
  edit can land with no corresponding release-surface change and nothing fails.
- **This repo's own CLAUDE.md already states the release-surface parity requirement this issue
  operationalizes.** Repo `CLAUDE.md` ("Development Workflow," item 6) requires that "for every
  plugin behavior, schema, command, prompt, or user-facing guidance change," `plugin.json`,
  `marketplace.json`, `CHANGELOG.md`, and "any version/metadata drift guard tests" all update in
  the same PR — today that requirement is enforced by reviewer discipline only, with no
  mechanical check.

## Definition of Done

A generator plus three enforcement layers, replacing hand-maintained release-surface copies and
ad hoc CHANGELOG parsing:

1. `scripts/sync_marketplace.py` — generates each `.claude-plugin/marketplace.json` plugin entry
   (`name`, `source`, `version`, `description`, `author`, `repository`, `license`, `keywords`,
   `category`) from that plugin's own `plugins/<name>/.claude-plugin/plugin.json`, in two modes:
   a write mode that regenerates `marketplace.json` in place, and a `--check` mode that exits
   non-zero if the committed `marketplace.json` disagrees with what generation would produce
   (drift, not just missing entries).
2. `scripts/check_release_surface_parity.py` (or equivalent named CI step) — a parity gate
   asserting, per plugin, `plugin.json` version == generated `marketplace.json` entry version ==
   the version in that plugin's own `CHANGELOG.md` top heading (the tri-lock). Fails naming
   exactly the plugin(s) out of parity, not just "something is wrong."
3. `tools/release_surface_diff_guard.py` (or equivalent named CI step) — a diff-aware, PR-scoped
   guard: for any plugin whose non-doc files (skills, agents, commands, scripts) changed versus
   the PR's base, asserts that plugin's `plugin.json` version and `CHANGELOG.md` both changed in
   the same diff. A doc-only or test-only change to a plugin does not require a bump.
4. A canonical CHANGELOG heading grammar recorded in `docs/engineering-journal/DECISIONS.md` (one
   heading format, one file-title format) plus a lint (pre-commit hook and/or CI step and test)
   that rejects any plugin `CHANGELOG.md` not matching it, replacing today's implicit
   four-format tolerance. Existing plugin CHANGELOGs are reformatted to the canonical grammar as
   part of this same change so the lint starts green, not red, on merge.
5. All of the above run against the current 8-plugin fleet as the passing baseline — this issue
   does not leave any plugin in a failing state on merge.

### Acceptance criteria
- [ ] **Generator produces a marketplace entry from `plugin.json` alone.** Given any one plugin's
      `plugin.json`, `sync_marketplace.py` (write mode) produces a `marketplace.json` entry whose
      `name`, `version`, `description`, `author`, and `keywords` match that `plugin.json` exactly.
      Check: `uv run pytest tests/test_sync_marketplace.py -k generates_entry_from_plugin_json` →
      passes.
- [ ] **`--check` reds when `plugin.json` is bumped without regenerating `marketplace.json`.**
      Given a fixture where one plugin's `plugin.json` version is bumped but `marketplace.json` is
      left stale, `sync_marketplace.py --check` exits non-zero and names that plugin. Check:
      `uv run pytest tests/test_sync_marketplace.py -k check_reds_on_stale_marketplace` → passes.
- [ ] **`--check` is green after regeneration.** Running `sync_marketplace.py` (write mode) then
      `--check` on the same fixture exits `0`. Check: `uv run pytest tests/test_sync_marketplace.py
      -k check_green_after_regenerate` → passes.
- [ ] **Tri-lock parity gate fails on exactly the plugin out of sync.** Given the 8-plugin fleet
      with one plugin's `CHANGELOG.md` top-heading version manually diverged from its
      `plugin.json`/`marketplace.json` version, the parity gate fails and names only that plugin;
      the other 7 plugins are unaffected. Check: `uv run pytest
      tests/test_release_surface_parity.py -k tri_lock_fails_on_single_plugin_drift` → passes.
- [ ] **Diff-aware bump guard fails on a `SKILL.md` edit with no CHANGELOG touch.** Given a
      simulated PR diff that edits a plugin's `SKILL.md` but does not touch that plugin's
      `plugin.json` or `CHANGELOG.md`, the diff-aware guard fails naming the plugin and the
      missing bump. Check: `uv run pytest tests/test_release_surface_diff_guard.py -k
      skill_edit_without_bump_fails` → passes.
- [ ] **Diff-aware bump guard passes when the bump accompanies the change.** The same `SKILL.md`
      edit plus a matching `plugin.json` version bump and `CHANGELOG.md` entry in the same diff
      passes the guard. Check: `uv run pytest tests/test_release_surface_diff_guard.py -k
      skill_edit_with_bump_passes` → passes.
- [ ] **Diff-aware bump guard does not fire on doc-only or test-only changes.** A diff touching
      only a plugin's `README.md` or `tests/` files does not require a version bump. Check: `uv run
      pytest tests/test_release_surface_diff_guard.py -k doc_only_change_not_required_to_bump` →
      passes.
- [ ] **Non-canonical CHANGELOG heading is rejected by the lint.** A `CHANGELOG.md` using any of
      the fleet's current three non-canonical shapes (bare `## x.y.z - date` with no brackets,
      a plugin-name-suffixed `# Changelog - <plugin>` title, or a Keep-a-Changelog-linked header)
      fails the heading lint. Check: `uv run pytest tests/test_changelog_heading_lint.py -k
      rejects_noncanonical_heading` → passes.
- [ ] **Canonical CHANGELOG heading passes the lint.** A `CHANGELOG.md` matching the grammar
      recorded in `docs/engineering-journal/DECISIONS.md` passes. Check: `uv run pytest
      tests/test_changelog_heading_lint.py -k accepts_canonical_heading` → passes.
- [ ] **8-plugin fleet passes as baseline after this change merges.** After reformatting existing
      CHANGELOGs and regenerating `marketplace.json`, all three checks (`sync_marketplace.py
      --check`, the tri-lock parity gate, the CHANGELOG heading lint) pass against the live
      `plugins/*` tree with zero fixture substitution. Check: `python3 scripts/sync_marketplace.py
      --check && python3 scripts/check_release_surface_parity.py && uv run pytest
      tests/test_changelog_heading_lint.py -k fleet_baseline` → all exit `0`.
- [ ] **Full suite, format, lint, types, and security stay green.** Check: `uv run pytest && uv run
      ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
      --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

### Out-of-scope / non-goals
In scope: one generator (`plugin.json` → `marketplace.json` entry), one tri-lock parity gate, one
diff-aware bump guard, and one canonical CHANGELOG heading grammar plus lint, applied to the
current 8-plugin fleet.

Out of scope (do not do in this issue):

- **A `uv-publish` CLI wrapping actual package publication.** `docs/engineering-journal/
  QUEUED.md`-adjacent seed `S-13` ("uv-publish CLI for plugin release surfaces") absorbed a
  version-parity preflight into this issue's scope, but the publish action itself (wrapping `uv
  publish`, dry-run mode, abort-on-drift) is a separate, later capability that can consume this
  issue's parity gate as a precondition rather than being built here.
- **Rewriting CHANGELOG body content or history.** This issue changes only the heading grammar
  (file title + version-heading format) and reformats existing headings to match; it does not
  rewrite, reorder, or edit the substance of any existing changelog entry.
- **A general release-surface CLI for non-plugin-fleet repos.** This issue's scope is this
  repository's `plugins/*` and `.claude-plugin/marketplace.json`; it does not build a
  reusable/vendorable tool for other Infiquetra repos in this issue (that is a candidate
  fast-follow if this pattern proves out).
- **Changing `plugin.json` schema itself** (adding/removing required fields). The generator
  consumes today's `plugin.json` shape as-is; schema evolution is a separate concern.
- **Enforcing bump discipline on `marketplace.json`'s own top-level `metadata.version`**
  (the marketplace-wide version, currently `3.0.0`) — this issue's tri-lock is per-plugin
  (`plugin.json` == plugin's marketplace entry == plugin's own CHANGELOG), not the
  marketplace-file-wide version field.

## Grounding References

- **Absorbed idea `T11-F3-5`** (primary, keeper) — "Don't guard the copies — generate them:
  single-source release surfaces from plugin.json." `dod_sketch`: "Merged `scripts/
  sync_marketplace.py` (generate + `--check`) deriving marketplace entries from `plugin.json` + CI
  `--check` step; verified `--check` red when a `plugin.json` version is bumped without
  regeneration, green after." This is the generator this issue's DoD item 1 and acceptance
  criteria 1-3 implement directly.
- **Absorbed idea `T14-F4-3`** (dedup-merged) — "Release-surface version tri-lock: `plugin.json`
  == `marketplace.json` == CHANGELOG head." `dod_sketch`: "Merged `test_release_surface_versions.py`
  + `release-surfaces.lock`; verified bumping `plugin.json` alone fails the tri-lock, current
  8-plugin fleet passes as baseline." This is DoD item 2 / acceptance criterion 4 and the
  8-plugin-baseline criterion.
- **Absorbed idea `S-5`** (dedup-merged) — "Marketplace CI guard (registry ↔ plugin.json drift)."
  Basis: `QUEUED anchor {#marketplace-ci-guard} (brief §5); CLAUDE.md release-surface parity
  requirement`. `dod_sketch`: "Merged CI check asserting `marketplace.json`, each `plugin.json`,
  and CHANGELOG version/metadata agree. Verify: guard red on an injected version mismatch, green
  when reconciled." The queued seed itself lives at `docs/engineering-journal/QUEUED.md:176-190`
  (`{#marketplace-ci-guard}`), grounded in the shipped-twice `#marketplace-drift` bug
  (`docs/engineering-journal/LEARNINGS.md:1516-1533`); this issue's consolidation rationale
  explicitly supersedes the guard-only framing with the generator (see "Problem / motivation").
- **Absorbed idea `T11-F6-1`** (facet) — "Release-surface parity gate: one source of truth, two
  generated mirrors." `dod_sketch`: "Merged `scripts/check_release_surface_parity.py` asserting
  `plugin.json == marketplace entry == top CHANGELOG heading` per plugin + named CI step + test;
  verified bumping one `plugin.json` in a branch reds CI on exactly that plugin." This is DoD
  item 2 / acceptance criterion 4 (the "exactly that plugin" precision requirement).
- **Absorbed idea `T11-F4-6`** (facet) — "Diff-aware release-surface bump guard: touched a
  plugin's behavior, must bump its surfaces." `dod_sketch`: "Merged `tools/
  release_surface_diff_guard.py` + PR-scoped CI step asserting any plugin with changed non-doc
  files bumped its version and CHANGELOG; verified a `SKILL.md` edit without CHANGELOG touch
  fails." This is DoD item 3 / acceptance criteria 5-7.
- **Absorbed idea `T14-F2-4`** (facet) — "Collapse the four-format CHANGELOG heading parser to
  one canonical format." `dod_sketch`: "Merged CHANGELOG-heading lint (pre-commit + test) +
  `DECISIONS.md` canonical grammar; verified a non-canonical heading is rejected." This is DoD
  item 4 / acceptance criteria 8-9. The "four formats" claim is verified directly in this issue's
  problem statement against `plugins/agy/CHANGELOG.md`, `plugins/deploy/CHANGELOG.md`,
  `plugins/team-execution/CHANGELOG.md`, and `plugins/redis-channel/CHANGELOG.md`.
- **Absorbed idea `S-13`** (facet) — "uv-publish CLI for plugin release surfaces." Basis: "brief
  §8 direct-to-candidate 'uv-publish CLI'." `dod_sketch`: "Merged CLI wrapping `uv publish` for
  the fleet's release surfaces with version-parity preflight." Only the version-parity preflight
  facet is absorbed into this issue's scope (the tri-lock gate this issue builds is exactly that
  preflight); the publish-wrapping CLI itself is explicitly out of scope — see "Scope &
  non-goals."
- **Binding decision this issue operationalizes** — repo `CLAUDE.md`, "Development Workflow" item
  6: "For every plugin behavior, schema, command, prompt, or user-facing guidance change, update
  the plugin release surfaces in the same PR: `plugins/<plugin>/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/<plugin>/CHANGELOG.md`, and any version/metadata
  drift guard tests." This issue turns that reviewer-enforced sentence into a mechanical CI gate.
- **Existing primitive this issue extends, not replaces** — `tests/test_marketplace_hook.py`
  covers JSON well-formedness on `Write`/`Edit` of `marketplace.json`/`plugin.json` (via
  `plugins/saga/hooks/validate_json_hook.py`); it does not check cross-file version/content
  parity. This issue's parity gate and diff-aware guard are a distinct, additive layer.
- **Consolidation rationale (from the issue-map)** — "Keeper `T11-F3-5` (generate-don't-guard)
  subsumes the tri-lock and marketplace-guard seed per dedup-map; the parity gate, diff-aware bump
  guard, one canonical CHANGELOG heading, and the release-surface CLI seed are its enforcement
  faces."

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** the work is a well-scoped set of small, mechanical Python scripts (a field
  generator, a version-parity comparator, a diff-scoped guard, a heading regex/lint) over
  already-fully-specified target shapes (the fleet's own existing `plugin.json`/
  `marketplace.json`/`CHANGELOG.md` fields), with no architectural ambiguity — but effort is set
  to high rather than medium because the change touches all 8 plugins' CHANGELOGs simultaneously
  (reformatting each to the canonical grammar without altering entry substance) and must land the
  fleet in a passing baseline state on merge, which raises the correctness bar for the
  cross-cutting mechanical edit even though no single script is architecturally hard. No
  external-engine involvement is needed; this is a self-contained repo-internal tooling change.

### Release-surface checklist

This issue is itself a change to release-surface tooling and touches every plugin's
`CHANGELOG.md` heading format; the checklist below applies to the tooling's own release surface
(it does not add a new plugin, so no new marketplace entry is created):

- [ ] No `plugins/*/.claude-plugin/plugin.json` functional field changes are required by this
      issue (the generator reads existing fields as-is); if any plugin's own `plugin.json` needs a
      version bump to reflect its reformatted `CHANGELOG.md`, bump it in the same PR.
- [ ] `.claude-plugin/marketplace.json` — regenerated via `sync_marketplace.py` (write mode) as
      part of this PR so the committed file matches the new generator's output byte-for-byte.
- [ ] Every plugin's `CHANGELOG.md` — reformatted to the canonical heading grammar (this issue's
      own deliverable) plus a new entry in each touched plugin's own CHANGELOG describing the
      reformat itself, per repo convention that a plugin-behavior-adjacent change gets a
      CHANGELOG line.
- [ ] Drift-guard tests — this issue is the drift-guard tests; ensure
      `tests/test_sync_marketplace.py`, `tests/test_release_surface_parity.py`,
      `tests/test_release_surface_diff_guard.py`, and `tests/test_changelog_heading_lint.py` are
      wired into the same CI workflow that already runs `tests/test_marketplace_hook.py`.
- [ ] `docs/engineering-journal/DECISIONS.md` — new entry recording the canonical CHANGELOG
      heading grammar choice, the rejected alternatives (the three formats found in the fleet
      today), and a "revisit when" condition (e.g. if a 9th plugin's provenance requires a
      different grammar).
- [ ] `docs/engineering-journal/LEARNINGS.md` — dated entry cross-referencing
      `{#marketplace-drift}` (`:1516-1533`) noting this issue converts that guard-class fix into a
      generator, per this issue's consolidation rationale.

### Files expected to change

Indicative only — the exact set is `/plan`'s to determine.

- `scripts/sync_marketplace.py` — new: generator + `--check` mode (proposed path, alongside
  existing `scripts/validate_plugins.py`).
- `scripts/check_release_surface_parity.py` — new: tri-lock parity gate (proposed path).
- `tools/release_surface_diff_guard.py` — new: PR-scoped diff-aware bump guard (proposed path,
  alongside existing `tools/stale_main_guard.py`).
- `plugins/*/CHANGELOG.md` (all 8 plugins) — reformatted headings to the canonical grammar; no
  entry substance changes.
- `.claude-plugin/marketplace.json` — regenerated in place by `sync_marketplace.py`.
- `docs/engineering-journal/DECISIONS.md` — new entry for the canonical CHANGELOG grammar choice.
- `docs/engineering-journal/LEARNINGS.md` — dated entry per the release-surface checklist above.
- `tests/test_sync_marketplace.py` — new: generator + `--check` red/green cases.
- `tests/test_release_surface_parity.py` — new: tri-lock pass/fail cases.
- `tests/test_release_surface_diff_guard.py` — new: diff-aware bump-required / not-required cases.
- `tests/test_changelog_heading_lint.py` — new: canonical/non-canonical heading cases plus the
  8-plugin fleet baseline check.
- `.github/workflows/` — new or updated CI step(s) wiring the above checks into PR/push runs,
  alongside the existing marketplace-consistency-adjacent checks.

### Tests to add or update

- Generator produces a correct marketplace entry from a given `plugin.json`; `--check` reds on
  stale output and greens after regeneration.
- Tri-lock parity gate fails naming exactly the plugin whose `plugin.json` /marketplace
  entry/CHANGELOG-head versions disagree; passes when all three agree, across the full 8-plugin
  fleet.
- Diff-aware bump guard fails on a non-doc file change with no version/CHANGELOG bump in the same
  diff; passes when the bump accompanies the change; does not fire on doc-only or test-only
  changes.
- CHANGELOG heading lint rejects each of the fleet's three currently-observed non-canonical
  shapes and accepts the canonical grammar; the reformatted 8-plugin fleet passes the lint as a
  baseline with no fixture substitution.
- Existing `tests/test_marketplace_hook.py` JSON-well-formedness coverage stays green and
  unmodified — this issue is additive to it, not a replacement.

### Verification

```bash
# New release-surface tooling unit tests
uv run pytest tests/test_sync_marketplace.py tests/test_release_surface_parity.py \
  tests/test_release_surface_diff_guard.py tests/test_changelog_heading_lint.py -v

# Generator + tri-lock parity + heading lint against the live 8-plugin fleet (no fixtures)
python3 scripts/sync_marketplace.py --check
python3 scripts/check_release_surface_parity.py
uv run pytest tests/test_changelog_heading_lint.py -k fleet_baseline

# Existing marketplace-hook coverage stays green
uv run pytest tests/test_marketplace_hook.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; `sync_marketplace.py --check` and `check_release_surface_parity.py` both
exit `0` against the live fleet with no injected fixtures; the CHANGELOG heading lint passes all
8 reformatted plugin CHANGELOGs.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json
  (`pf-release-surface-single-source`, absorbing `T11-F3-5`, `T14-F4-3`, `S-5`, `T11-F6-1`,
  `T11-F4-6`, `T14-F2-4`, `S-13`)
- Source type: issue-map
- Source title: Single-source release surfaces: generate marketplace from plugin.json, tri-lock
  parity, diff-aware bump guard, canonical CHANGELOG grammar

### Context library links

_none_

### Intent

The fleet has shipped the exact drift bug this issue prevents at least twice already, and today's release surfaces are hand-maintained copies with no single source of truth.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/429
- Number: 429
- Created at: 2026-07-04T08:11:08.547630+00:00

