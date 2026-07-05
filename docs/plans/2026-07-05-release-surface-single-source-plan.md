---
title: Single-source release surfaces — generate marketplace.json from plugin.json, tri-lock parity, diff-aware bump guard, canonical CHANGELOG grammar
type: feat
status: active
date: 2026-07-05
origin: infiquetra/infiquetra-claude-plugins#429
---

# Single-source release surfaces

## Summary

Replace the fleet's hand-maintained `.claude-plugin/marketplace.json` copy with a generator
(`scripts/sync_marketplace.py`) that derives each plugin's marketplace entry from its own
`plugin.json`, back it with a tri-lock parity gate and a diff-aware bump guard, and collapse the
fleet's divergent `CHANGELOG.md` heading grammars to one canonical format — closing the drift class
that has already shipped twice (`{#marketplace-drift}`, PRs #110/#111/#112).

## Problem frame

Today `marketplace.json` is a hand-copy of fields that already live in each plugin's own
`plugin.json`; nothing generates it and nothing asserts the two stay in sync after either changes
independently. `docs/engineering-journal/LEARNINGS.md:1516-1533` documents this drifting exactly
once already (a plugin shipped with no matching registry entry, needing a third PR to fix), and
`docs/engineering-journal/QUEUED.md:176-190` queues a guard-class fix. This issue supersedes the
guard-only framing: generate the mirror instead of comparing two hand-copies.

## Grounding corrections (issue vs current repo state)

The issue is unusually well-specified (issue-map sourced, `requirements-ready`), but grounding
surfaced two real gaps between its stated DoD and the current repo that this plan resolves as KTDs
rather than carrying forward silently:

- **Plugin count is 9, not 8.** The issue's problem statement and acceptance criteria repeatedly say
  "8-plugin fleet." Verified directly: `ls -d plugins/*/` → 9 (`agy`, `deploy`, `fleet-core`,
  `home-lab-ops`, `mission-control`, `redis-channel`, `saga`, `team-execution`, `unifi`), and
  `.claude-plugin/marketplace.json` already carries 9 entries. `fleet-core` landed via #463/PR #473
  the day before this issue was filed — the issue's source snapshot predates it. Every acceptance
  criterion and script in this plan targets "the current plugin fleet" (verified by directory scan
  at run time), never a hardcoded count.
- **`license` and `category` cannot come from `plugin.json` — no plugin's `plugin.json` has them.**
  Verified by inspecting all 9 `plugin.json` files: none carries a `license` or `category` field
  (confirmed on `agy`, `saga`, `mission-control`). Only the existing hand-maintained
  `marketplace.json` entries carry these two fields. The issue's DoD item 1 says the generator
  derives `license`/`category` "from `plugin.json`" — that's not possible without a `plugin.json`
  schema change, which the issue explicitly rules out of scope ("Changing `plugin.json` schema
  itself... is a separate concern"). See KTD2 for the resolution.

## Requirements

- R1. `scripts/sync_marketplace.py` generates each plugin's marketplace entry
  (`name`/`source`/`version`/`description`/`author`/`repository`/`keywords`) from that plugin's own
  `plugins/<name>/.claude-plugin/plugin.json`, in a write mode (regenerates `marketplace.json` in
  place) and a `--check` mode (exits non-zero, naming the plugin, if the committed file disagrees
  with generated output).
- R2. `scripts/check_release_surface_parity.py` asserts, per plugin, `plugin.json` version ==
  generated marketplace entry version == that plugin's own `CHANGELOG.md` top version-heading,
  failing and naming exactly the plugin(s) out of parity.
- R3. `tools/release_surface_diff_guard.py` asserts that any plugin whose non-doc files changed in a
  PR diff (versus its base ref) also bumped that plugin's `plugin.json` version and touched its
  `CHANGELOG.md` in the same diff; doc-only (`README.md`, `docs/**`) or test-only (`tests/**`)
  changes are exempt.
- R4. One canonical `CHANGELOG.md` heading grammar is recorded in `docs/engineering-journal/
  DECISIONS.md` and enforced by a lint; all 9 plugins' CHANGELOGs are reformatted to it (heading
  only — no entry-substance rewrites).
- R5. All of the above pass against the current plugin fleet as a merge-time baseline — this issue
  does not leave any plugin in a failing state.
- R6. CI (`.github/workflows/ci.yml`) runs `sync_marketplace.py --check`, the parity gate, and the
  CHANGELOG heading lint on every push/PR; the diff-aware bump guard runs PR-scoped (needs a base
  ref, so it is CI-only, not part of the general `uv run pytest` gate).

## Key Technical Decisions

**KTD1 — Canonical CHANGELOG heading grammar.** File title is exactly `# Changelog` (no plugin-name
suffix — rejects `team-execution`'s `# Changelog - team-execution` and `mission-control`'s
`# Changelog — mission-control`). Version headings are `## [X.Y.Z] - YYYY-MM-DD` — bracketed
version, hyphen-minus date separator (rejects `deploy`'s and `saga`'s unbracketed `## X.Y.Z - date`,
and `mission-control`'s em-dash-separated `## [X.Y.Z] — date`). An optional leading `## [Unreleased]`
heading (no date) is permitted before the first dated entry. This is the plurality format already
in use (`agy`, `fleet-core`, `home-lab-ops`, `redis-channel`, `unifi` — 5 of 9 — already match it
exactly for the title; `agy`/`fleet-core`/`home-lab-ops`/`redis-channel`/`unifi`/`team-execution`
already match it for the version-heading shape), minimizing the number of plugins whose CHANGELOG
body needs more than a heading-line edit. Rejected alternative: Keep-a-Changelog's own recommended
`## [X.Y.Z] - YYYY-MM-DD` is what this already is — no divergence to reconcile there; the prose
Keep-a-Changelog links some files carry (`redis-channel`, `fleet-core`) are left as-is (the issue
scopes reformatting to headings only, not header prose).

**KTD2 — `license`/`category` are marketplace-owned fields, not plugin.json-derived.** Since no
`plugin.json` carries these fields and adding them is an explicit non-goal (schema change), the
generator treats `license` and `category` as pass-through fields: when regenerating an existing
plugin's entry, it preserves that entry's current `license`/`category` verbatim; it never sources
them from `plugin.json`. `sync_marketplace.py --check` therefore only flags drift on the
plugin.json-derived fields (R1's list) — it is not a mechanism for auditing `license`/`category`
correctness. A plugin with no prior marketplace entry (a genuinely new plugin) has no
`license`/`category` to preserve; the generator defaults `license` to `"MIT"` (the value every
existing entry already carries — verified: all 9) and requires `category` to be passed explicitly
via a `--category` CLI flag for that one entry (fails loudly rather than guessing an infrastructure
category for an unknown-shape new plugin). This is scoped explicitly in the plan so `/doc-review`
and the reviewer see it as a deliberate call, not an oversight of DoD item 1's literal wording.

**KTD3 — Entry ordering is stable, not regenerated from a fresh sort.** `marketplace.json`'s
existing plugin order (`home-lab-ops, unifi, deploy, saga, team-execution, mission-control,
redis-channel, agy, fleet-core` — historical add-order, not alphabetical) is preserved on
regeneration; the generator updates each existing entry in place by matching on `name`, and appends
any plugin present in `plugins/*/` but absent from the array (in `plugins/*/` scan order) at the
end. Rejected alternative: regenerating in alphabetical order was considered but rejected — it would
produce an unrelated full-file reorder diff on this PR's first run, obscuring the actual field
changes under review.

**KTD4 — Diff-aware guard's base ref and file classification.** The guard takes the base ref as a
CLI argument (`--base-ref <sha-or-ref>`, defaulting to `origin/main` when unset) rather than
resolving it internally — CI supplies `github.event.pull_request.base.sha` explicitly; this keeps
the script testable against fixture git repos without faking GitHub Actions' event context. A file
belongs to plugin `<name>` when its path starts with `plugins/<name>/`; within that, "non-doc" means
everything except `plugins/<name>/README.md`, `plugins/<name>/CHANGELOG.md` itself, and any path
matching `plugins/<name>/**/tests/**` or `tests/test_<name>*` at the repo root (the two doc/test
carve-outs the acceptance criteria name explicitly). The guard checks that the diff touches both
`plugins/<name>/.claude-plugin/plugin.json` (any change, not just the `version` field — this is a
cheap presence check, not a semver-diff) and `plugins/<name>/CHANGELOG.md`; it does not itself
parse or validate the CHANGELOG content (U2's lint owns that).

## Implementation Units

### U1. `scripts/sync_marketplace.py` — generator + `--check` mode

**Approach:** A single script with two subcommands (or a `--check` flag) sharing one core function
`build_entry(plugin_json: dict, existing_entry: dict | None) -> dict` that applies R1 (generated
fields) and KTD2 (pass-through `license`/`category`, with the `--category` fallback for new
entries). Write mode reads every `plugins/*/.claude-plugin/plugin.json`, builds each entry per
KTD3's ordering rule, and writes the file with the same `json.dumps(..., indent=2)` + trailing
newline convention `marketplace.json` already uses (verified: 2-space indent, matches
`plugins/*/.claude-plugin/plugin.json`'s own formatting). `--check` builds the same target output
in memory and diffs it against the committed file's parsed JSON (structural compare, not
byte-for-byte, so key-order-insensitive tooling doesn't false-positive) — on mismatch, prints the
plugin name(s) whose entry differs and exits 1.

**Files:** `scripts/sync_marketplace.py` (new), `tests/test_sync_marketplace.py` (new).

**Test scenarios** (`tests/test_sync_marketplace.py`):
- `generates_entry_from_plugin_json` — given a fixture `plugin.json`, the generated entry's
  `name`/`version`/`description`/`author`/`keywords` match it exactly.
- `check_reds_on_stale_marketplace` — a fixture `plugin.json` version bumped with
  `marketplace.json` left stale → `--check` exits non-zero, names the plugin.
- `check_green_after_regenerate` — write mode then `--check` on the same fixture → exit 0.
- `preserves_license_and_category_on_regenerate` (KTD2) — an existing entry's `license`/`category`
  survive regeneration unchanged even though `plugin.json` has neither field.
- `new_plugin_without_category_flag_fails_loudly` (KTD2) — a `plugin.json` with no corresponding
  existing marketplace entry and no `--category` flag → non-zero exit with a clear "category
  required for new plugin" message, not a silent default guess.
- `preserves_existing_entry_order` (KTD3) — regenerating a 3-entry fixture array with one plugin's
  description changed does not reorder the other two entries.

### U2. Canonical CHANGELOG grammar + heading lint

**Approach:** Record KTD1's grammar in `docs/engineering-journal/DECISIONS.md` (rationale, the 3
rejected shapes found in the fleet, "revisit when: a 9th-plus plugin's provenance requires a
different grammar"). Implement `scripts/changelog_heading_lint.py` — a regex-based check (title line
== `^# Changelog$`, each version-heading line matches `^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$`
or `^## \[Unreleased\]$`) run per `plugins/*/CHANGELOG.md`, reporting every non-conforming heading
line with its file and line number.

**Files:** `scripts/changelog_heading_lint.py` (new), `tests/test_changelog_heading_lint.py` (new),
`docs/engineering-journal/DECISIONS.md` (new entry).

**Test scenarios:**
- `rejects_noncanonical_heading` — three fixture files, one per non-canonical shape found in the
  fleet (unbracketed version, plugin-name-suffixed title, em-dash date separator) → each fails with
  the specific offending line identified.
- `accepts_canonical_heading` — a fixture matching KTD1's grammar exactly, including an
  `[Unreleased]` heading with no date → passes.
- `fleet_baseline` — run against the live `plugins/*/CHANGELOG.md` (post-U3 reformat, so this test
  is written against U1-3's combined output, not run standalone before U3 lands) → all 9 pass, no
  fixture substitution.

### U3. Reformat all 9 plugin CHANGELOGs + regenerate `marketplace.json`

**Approach:** Mechanical, per-plugin heading-only edits (no entry-substance changes, per the issue's
explicit non-goal): `deploy` and `saga` gain brackets around their version numbers;
`team-execution`'s title drops its `- team-execution` suffix; `mission-control`'s title drops its
`— mission-control` suffix and its version-heading date separator changes from em-dash to
hyphen-minus. The other 5 plugins (`agy`, `fleet-core`, `home-lab-ops`, `redis-channel`, `unifi`)
already conform per KTD1 and need no edit. Each touched plugin gets one new CHANGELOG entry
documenting the reformat itself (per the release-surface checklist's own requirement that a
plugin-behavior-adjacent change gets a CHANGELOG line) — this is the one substance addition,
distinct from the heading-only reformat of prior entries.

**This new entry must land under a new version heading, paired with a patch-level `plugin.json`
version bump on that same plugin** — not appended under the existing top heading. If it went in
unbumped, the CHANGELOG's top heading version would stay unchanged while `plugin.json` also stays
unchanged, so parity (R2) would hold trivially — but a new-heading-with-no-bump instead breaks
U4's tri-lock the moment it lands (top CHANGELOG version would disagree with `plugin.json`).
Bumping is also what the issue's own release-surface checklist calls for ("if any plugin's own
`plugin.json` needs a version bump to reflect its reformatted `CHANGELOG.md`, bump it in the same
PR") and what root `CLAUDE.md` item 6 requires for any user-facing/documentation-surface change.
So: `deploy` 0.1.2→0.1.3, `saga` 0.54.0→0.54.1, `team-execution` 2.9.0→2.9.1, `mission-control`
2.5.0→2.5.1 (each plugin's own next patch version), each with a matching new CHANGELOG heading
under KTD1's grammar. Run U1's generator (write mode) once afterward to regenerate
`marketplace.json` from the now-current `plugin.json` set (this also resolves KTD2's
`license`/`category` preservation in practice for the first time).

**Files:** `plugins/deploy/{.claude-plugin/plugin.json,CHANGELOG.md}`,
`plugins/saga/{.claude-plugin/plugin.json,CHANGELOG.md}`,
`plugins/team-execution/{.claude-plugin/plugin.json,CHANGELOG.md}`,
`plugins/mission-control/{.claude-plugin/plugin.json,CHANGELOG.md}` (heading edits + version bump +
new entry each), `.claude-plugin/marketplace.json` (regenerated).

**Test expectation:** none — mechanical text edits over fixed target shapes (KTD1's grammar), and
tests already assert the outcome (U2's `fleet_baseline`, U1's generator tests). Verified manually
via `python3 scripts/changelog_heading_lint.py` and `python3 scripts/sync_marketplace.py --check`
both exiting 0 against the live tree at the end of this unit.

### U4. `scripts/check_release_surface_parity.py` — tri-lock gate

**Approach:** For each plugin (scanned from `plugins/*/`), read `plugin.json`'s `version`, the
freshly-generated marketplace entry's `version` (calls U1's `build_entry` in memory — does not shell
out to `sync_marketplace.py`), and the top dated version-heading in `CHANGELOG.md` (first line
matching U2's `## [X.Y.Z] - ...` regex, skipping a leading `[Unreleased]`). Fails, printing exactly
the plugin(s) whose three values disagree; exits 0 when all plugins agree.

**Files:** `scripts/check_release_surface_parity.py` (new), `tests/test_release_surface_parity.py`
(new).

**Test scenarios:**
- `tri_lock_fails_on_single_plugin_drift` — one plugin's `CHANGELOG.md` top-heading version
  manually diverged from its `plugin.json`/marketplace version in a fixture tree of the full fleet →
  gate fails, names only that plugin; the other plugins pass.
- `tri_lock_passes_on_agreement` — all three values equal → exits 0.

### U5. `tools/release_surface_diff_guard.py` — diff-aware bump guard

**Approach:** Per KTD4. Shells `git diff --name-only <base-ref>...HEAD` (or accepts a pre-computed
file list for testability — the test scenarios construct a real fixture git repo with a base commit
and a diverging branch, per this repo's existing house convention for git-shelling scripts, e.g.
`ship_ceremony.py`'s test suite). Groups changed paths by owning plugin (KTD4's `plugins/<name>/`
prefix rule), classifies each as doc/test-exempt or bump-required, and for each plugin with a
bump-required change, asserts both `plugins/<name>/.claude-plugin/plugin.json` and
`plugins/<name>/CHANGELOG.md` are also in the changed-files set. Fails naming the plugin(s) missing
either file.

**Files:** `tools/release_surface_diff_guard.py` (new), `tests/test_release_surface_diff_guard.py`
(new).

**Test scenarios:**
- `skill_edit_without_bump_fails` — a fixture diff touching only a plugin's `SKILL.md` → guard
  fails, names the plugin and the missing bump.
- `skill_edit_with_bump_passes` — same `SKILL.md` edit plus a `plugin.json` and `CHANGELOG.md`
  change in the same diff → passes.
- `doc_only_change_not_required_to_bump` — a diff touching only `README.md` or a path under
  `tests/` → does not fail (no bump-required file in the diff).
- `multi_plugin_diff_isolates_correctly` — a diff spanning two plugins, one compliant and one not →
  fails naming only the non-compliant one.

### U6. CI wiring + journal writeback

**Approach:** Add the four new checks to `.github/workflows/ci.yml` alongside the existing test/
lint/type/security steps: `uv run pytest tests/test_sync_marketplace.py
tests/test_release_surface_parity.py tests/test_release_surface_diff_guard.py
tests/test_changelog_heading_lint.py`, then the three live-fleet baseline commands
(`sync_marketplace.py --check`, `check_release_surface_parity.py`,
`changelog_heading_lint.py` fleet run) as their own step so a baseline regression fails distinctly
from a unit-test regression. The diff-aware guard runs as a separate PR-triggered step (needs
`github.event.pull_request.base.sha`, per KTD4) — not part of the push-triggered baseline step,
since it has no meaning on a direct push to `main`. Close the loop on
`docs/engineering-journal/LEARNINGS.md` with a dated entry cross-referencing `{#marketplace-drift}`
(`:1516-1533`), noting this issue converts that guard-class fix into a generator.

**Files:** `.github/workflows/ci.yml`, `docs/engineering-journal/LEARNINGS.md`.

**Test expectation:** none -- CI wiring is verified by the workflow actually running green on this
PR itself (observable in the PR's checks tab), not a unit test of YAML.

## Scope Boundaries

Out of scope (per the issue, carried forward unchanged): a `uv-publish` CLI wrapping actual package
publication; rewriting CHANGELOG body/entry substance beyond the one reformat-announcement entry per
touched plugin (U3); a general release-surface CLI for non-fleet repos; changing `plugin.json`
schema (KTD2 resolves the `license`/`category` gap without a schema change); enforcing bump
discipline on `marketplace.json`'s own top-level `metadata.version` field (currently `3.0.0` —
untouched by this plan).

Deferred to follow-up work: auditing whether existing `license`/`category` values are themselves
correct (KTD2 makes the generator pass-through, not a correctness auditor for those two fields) —
a future issue could add a small explicit per-plugin category/license source file if that audit is
ever wanted.
