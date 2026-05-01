# Queued — Infiquetra Claude Plugins

> **Future-work items by priority with explicit "worth it when" triggers.** When a promising idea surfaces but we don't build it right now, it goes here. Don't skip the entry just because it feels minor — undocumented good ideas decay into forgotten good ideas.
>
> **Format** (organized by priority section, no date headers — items are durable until they ship or get rejected):
>
> ```markdown
> ### Short title  {#slug}
>
> **Priority.** P0 (must-ship-before-X) / P1 (urgent) / P2 (important) / P3 (nice-to-have) / Maybe.
> **Effort.** Rough estimate (hours / half-day / day / week / multi-day).
> **Worth it when.** Specific trigger that would make this pressing.
> **Context.** What surfaced this; cross-references.
> ```
>
> When a queued item ships, move the entry to [ARCHIVE.md](ARCHIVE.md) as SHIPPED with the commit hash. When rejected, move with REJECTED + reason.

---

## P1 — urgent

### CI guard: assert plugin directories match marketplace.json entries  {#marketplace-ci-guard}

**Priority.** P1.

**Effort.** Half-day. GitHub Actions workflow + a small Python script (~30 lines).

**Worth it when.** Right now — the bug it prevents has shipped twice in a row (PRs #110, #111) and required a third PR (#112) to fix. The class of bug ("file A and file B must stay in sync but reviewers don't notice the absence in B") will recur with every new plugin or rename.

**Context.**
- See [LEARNINGS.md](LEARNINGS.md#marketplace-drift) for the bug's history + mechanism.
- Spec sketch:
  - Walk `plugins/*/` directories that contain `.claude-plugin/plugin.json`.
  - Read `.claude-plugin/marketplace.json`.
  - Assert: `set(plugin dir names) == set(p["name"] for p in marketplace["plugins"])`.
  - Optional v2: assert each entry's `source: ./plugins/<name>` resolves and the entry's `version` equals the plugin's own `plugin.json` version.
- Run on every push + PR via `.github/workflows/marketplace-consistency.yml`.
- Should also run on `main` post-merge so a slip is caught immediately rather than at next-PR time.

---

## P2 — important

### Build the `plugins/engineering-journal/` plugin  {#engineering-journal-plugin}

**Priority.** P2.

**Effort.** Multi-day (1–2 days of focused work for v1, more for the polish + the SDLC-philosophy doc).

**Worth it when.** A second or third Infiquetra repo wants the journal pattern and the manual setup labor (4 template files + CLAUDE.md section) starts to feel repetitive. Right now we have two adopters (home-lab, this repo); the third will be the trigger.

**Context.**
- Decided in `infiquetra/home-lab/docs/engineering-journal/DECISIONS.md` entry dated 2026-05-01: a two-tier split where `infiquetra-sdlc/docs/philosophy/engineering-journal.md` holds the canonical "what + why" and a `plugins/engineering-journal/` plugin in *this* repo holds the operational tooling.
- Five sub-decisions already pinned in that entry: standalone plugin (not folded into `sdlc-manager`); router skill (`using-engineering-journal`), not always-on hook; embedded templates (offline-friendly); `/journal-init` command with `--upgrade` mode for non-canonical existing layouts; naming convention.
- Full design walkthrough lives in `home-lab/docs/engineering-journal/narratives/2026-05-01-engineering-journal-distribution-design.md`.
- This plan's adoption of the journal in `infiquetra-claude-plugins` is **not** the plugin — it's a hand-built journal for this repo's own meta-work. The plugin work is downstream and uses this repo + home-lab as proven references when it's built.

---
