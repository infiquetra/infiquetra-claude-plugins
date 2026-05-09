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

### No `uv.lock` while uv is not canonical  {#superseded-no-uv-lock-decision}

**SUPERSEDED 2026-05-08** by DECISIONS [uv canonical sync](DECISIONS.md#uv-canonical-sync).

**Original decision.** Add `.claude/` to `.gitignore`. Do not track `uv.lock`. Stray `swap-pane` (0-byte file from a tmux operation) deleted as one-off cleanup.

**Original rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.
- *Track `uv.lock`.* Rejected: `pyproject.toml` declares `requires = ["hatchling"]` with no `[tool.uv]` section. The repo uses hatchling for building and ad hoc `pip`/`uv` invocations for local dev tooling, so there was no reproducible-build promise being made by checking in a uv lockfile. Tracking it would imply uv was part of the build path.

**Original rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). `uv.lock` would make a build-tool claim the repo was not making at the time. Both were pure noise in the diff and confused contributors about what was authoritative.

**Why superseded.** The repo now adopts uv as the canonical dependency sync path and CI installs from `uv.lock` with `uv sync --locked --extra dev`.

---
