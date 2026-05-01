# Engineering Journal — Infiquetra Claude Plugins

Living documentation for the `infiquetra-claude-plugins` repository — the plugins themselves, the marketplace registry, the development conventions, and the cross-plugin patterns that emerge over time. Prevents knowledge loss across sessions and across contributors.

The journal is the *directory*; the four core files plus `narratives/` are its sections. Pattern adopted 2026-05-01 from `infiquetra/home-lab/docs/engineering-journal/`.

## Files in this folder

| File | What it holds | When to update |
|------|---------------|----------------|
| [LEARNINGS.md](LEARNINGS.md) | Empirical findings + mechanisms + fixes + validations about plugins, the marketplace, hooks, skills, MCP integrations, build tooling | Every time a plugin bug, surprising behavior, or non-obvious truth surfaces during development |
| [DECISIONS.md](DECISIONS.md) | ADR-style records of plugin-pattern / convention / tooling choices | Every time we pick between options + commit to a path (skills-based vs CLI-based, line length, lockfile, marketplace category) |
| [QUEUED.md](QUEUED.md) | Future-work items — prioritized, with "worth it when" triggers | Whenever an idea surfaces that we don't build now but don't want to forget (new plugin, CI guard, refactor) |
| [ARCHIVE.md](ARCHIVE.md) | Shipped + rejected + superseded items | When a QUEUED item lands or is explicitly rejected; when a LEARNING/DECISION is invalidated |
| [narratives/](narratives/) | Self-contained, longer-form companion docs (plugin design walkthroughs, multi-PR post-mortems, migration write-ups) | When you need a doc that's standalone-readable cold by an outside reader (a future maintainer, a plugin consumer, you-six-months-out) |

## How to maintain

**This folder is self-maintaining via the repo's `CLAUDE.md`** — which instructs Claude to update these files as work proceeds, without the user having to ask. Specifically:

- **After fixing a plugin bug or shipping a feature where the mechanism wasn't obvious** (marketplace registry drift, hook timing, skill activation race, MCP env propagation): add a dated entry to `LEARNINGS.md` with evidence + mechanism + **Generalizable rule**.
- **After a plugin-pattern decision** (skills vs CLI, line length, lockfile choice, marketplace category taxonomy, version bump strategy, hook event choice): add an entry to `DECISIONS.md` with rationale + rejected alternatives + revisit-when condition + commit hash.
- **When an idea surfaces but isn't being built now**: add to `QUEUED.md` with priority (P0/P1/P2/P3/Maybe) + "worth it when…" trigger + effort estimate.
- **When a QUEUED item ships**: move the entry to `ARCHIVE.md` with the commit hash + SHIPPED date. Remove from QUEUED.
- **When a QUEUED item is rejected**: move to `ARCHIVE.md` as REJECTED with reason + revisit conditions. Remove from QUEUED.
- **When a decision gets reversed or a learning is invalidated**: update the original entry inline with the correction AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED. Never silently overwrite history.
- **When something needs a longer write-up than fits an entry**: create `narratives/YYYY-MM-DD-short-slug.md` and link from the relevant LEARNINGS / DECISIONS entry.

Each of the four core files has a block-quote intro at the top with its own format spec — read those when adding entries.

## Quick navigation by topic

- Marketplace registry drift (PRs #110/#111 missed registration) → [LEARNINGS](LEARNINGS.md#marketplace-drift)
- `marketplace.json` `Edit` requires `]` in `old_string` → [LEARNINGS](LEARNINGS.md#marketplace-edit-guard)
- Gitignore `.claude/` and skip `uv.lock` → [DECISIONS](DECISIONS.md#gitignore-claude-and-no-uv-lock)
- CI guard for plugins/marketplace drift → [QUEUED](QUEUED.md#marketplace-ci-guard)
- Future `plugins/engineering-journal/` plugin → [QUEUED](QUEUED.md#engineering-journal-plugin)
- PR #112 marketplace fix (SHIPPED) → [ARCHIVE](ARCHIVE.md#pr-112-marketplace-fix)
