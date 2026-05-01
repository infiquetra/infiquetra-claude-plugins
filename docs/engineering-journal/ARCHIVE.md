# Archive — Infiquetra Claude Plugins

> **The graveyard of QUEUED, LEARNINGS, and DECISIONS items.** When something from `QUEUED.md` ships, it moves here as **SHIPPED**. When something is consciously rejected, it moves here as **REJECTED** with the reason + revisit conditions. When a `LEARNINGS.md` or `DECISIONS.md` entry is invalidated by new evidence, the pre-correction version moves here as **SUPERSEDED**.
>
> **Never silently delete.** History is the point — a future Claude (or human) reading "did we ever consider X?" or "why did we change our mind on Y?" gets the answer.
>
> **Append new entries to the top** within each section.

---

## Shipped

### PR #112 — register `blueprint-reviewer` in marketplace + gitignore `.claude/`  {#pr-112-marketplace-fix}

**SHIPPED 2026-05-01** (commit `4da5705`, squash-merged from `fix/marketplace-register-blueprint-reviewer`).

**Summary.** Two-commit PR that:
1. Added the missing `blueprint-reviewer` entry to `.claude-plugin/marketplace.json` (15 plugins after the change, was 14).
2. Added `.claude/` to `.gitignore` and removed stray files `swap-pane` (0 bytes) and `uv.lock` (242 KB, unused — see DECISIONS).

**Why this matters in the archive.** This is the originating ship for the journal's first three real entries — the LEARNING about marketplace drift, the LEARNING about the `Edit` guard pattern, and the DECISION about repo hygiene. Future readers tracing those entries' "fixed in commit X" / "shipped via Y" links land here.

**Refs.**
- LEARNINGS: [marketplace drift](LEARNINGS.md#marketplace-drift), [marketplace edit guard](LEARNINGS.md#marketplace-edit-guard).
- DECISIONS: [gitignore `.claude/` + no `uv.lock`](DECISIONS.md#gitignore-claude-and-no-uv-lock).

---

## Rejected

*(none yet — this section will populate as ideas in `QUEUED.md` get explicitly declined with their reason.)*

---

## Superseded

*(none yet — this section will populate when a `LEARNINGS.md` or `DECISIONS.md` entry is invalidated by new evidence and its pre-correction version is preserved here.)*

---
