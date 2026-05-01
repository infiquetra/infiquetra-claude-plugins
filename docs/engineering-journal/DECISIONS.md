# Decisions — Infiquetra Claude Plugins

> **ADR-style records of plugin-pattern / convention / tooling choices.** When you commit a chosen path over alternatives — pick A over B, flip a flag, change a threshold, choose a category, adopt a tool — capture rationale + tradeoff + revisit-when condition + commit hash.
>
> The point is to make **revisit conditions explicit** so a future Claude (or human) reading "why did we pick X?" gets the answer cold, including when it would be right to reconsider.
>
> **Append new entries to the top.** Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short title (commit hash)  {#slug}
>
> **Decision.** What we picked.
> **Rejected alternatives.** What we considered and didn't pick.
> **Rationale.** Why this won.
> **Revisit when.** Condition that would change the calculus.
> **Refs.** Related LEARNINGS / QUEUED / narratives.
> ```
>
> When new evidence invalidates a decision, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**.

---

## 2026-05-01

### Gitignore `.claude/`, do not track `uv.lock` (commit `4da5705`)  {#gitignore-claude-and-no-uv-lock}

**Decision.** Add `.claude/` to `.gitignore`. Do not track `uv.lock`. Stray `swap-pane` (0-byte file from a tmux operation) deleted as one-off cleanup.

**Rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.
- *Track `uv.lock`.* Rejected: `pyproject.toml` declares `requires = ["hatchling"]` with no `[tool.uv]` section. The repo uses hatchling for building and ad-hoc `pip`/`uv` invocations for local dev tooling — there's no reproducible-build promise being made by checking in a uv lockfile. Tracking it would imply uv is part of the build path.

**Rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). `uv.lock` would make a build-tool claim the repo isn't currently making. Both are pure noise in the diff and confuse contributors about what's authoritative.

**Revisit when.**
- The repo adopts uv as the canonical lock-and-install tool (would require a `[tool.uv]` block in `pyproject.toml` and a CI step that installs from the lockfile). Then check it in and remove the gitignore exclusion.
- Claude Code introduces a *shared* settings file under `.claude/` that's intended to be checked in. At that point, narrow the gitignore from `.claude/` to specifically `.claude/settings.local.json` and `.claude/context/`.

**Refs.**
- LEARNINGS [marketplace registry drift](LEARNINGS.md#marketplace-drift) — same PR (#112).
- ARCHIVE [PR #112](ARCHIVE.md#pr-112-marketplace-fix) — shipped record.

---
