---
title: Session handoff — agy delegation + #277 build (start fresh)
date: 2026-06-28
status: handoff
purpose: Carry forward the verified learnings; drop the wasted-effort path. Start a new session from here.
---

# Session handoff — 2026-06-28

This session set out to dogfood agy as a delegated coder on issue **#277** and got derailed for hours
because I (Claude) **hand-rolled bash to invoke agy instead of using the installed plugins.** Everything
below is written so the next session skips that entirely.

## THE ONE RULE FOR NEXT TIME

**Use the plugins. Do not write bash to invoke agy or codex.**

- agy → the **`agy:runner`** subagent (Agent tool, `subagent_type: "agy:runner"`). It runs `agy` correctly
  and returns the result. The smoke test of it worked first try: `AGY_PLUGIN_OK` in 9s, headless.
  (Plugin script, if ever needed directly: `~/.claude/plugins/cache/antigravity-cc/agy/<ver>/scripts/agy-run.sh`,
  e.g. `agy-run.sh ask --model flash "<prompt>" --dangerously-skip-permissions`.)
- codex → the **codex plugin** / `codex:codex-rescue` agent for independent review or a second implementation pass.

I instead wrote raw `agy --model … -p … > file 2>&1` commands, wrapped in `timeout`, backgrounded, etc.
That is what burned the session. Don't.

## Why agy "looked like it was hanging" (it never was)

Two harness artifacts stacked to perfectly mimic a hang. Both vanish if you use the `agy:runner` subagent.

1. **The Claude Code Bash tool's default 120s timeout** SIGTERM-ed raw agy at exactly **2m0s** (exit 143).
   agy reasoning runs take ~30–480s, so any raw call where I didn't raise the *tool's* `timeout` got killed
   at 2:00 and left 0/truncated bytes — which I misread as "agy hung." When I raised the Bash timeout to
   900000ms, the same agy run finished clean (e.g. U1 at 263s, rc=0).
2. **The neuralmind PostToolUse hook compresses/mangles Bash stdout** — it dropped 46 lines and ate a `>`
   redirect in front of me. agy's `rc=0` exit markers and real output never reached me cleanly, fueling
   wrong theories. `NEURALMIND_BYPASS=1` set *inside* a command does NOT stop the hook. The fix: redirect to
   a file and **Read the file** (the Read tool is not hooked).

## Verified facts (keep)

- **agy works headless.** ~30 successful runs this session with real output + `rc=0` (confirmed by auditing
  every agy output file on disk). Only ONE review (the #277 plan's 25 KB Pro prompt, `agy_out*.md`) was
  genuinely 0 bytes; cause not isolated, size alone isn't it (21 KB review prompts succeeded).
- **`--model` IS a real agy flag** (`agy --help`: "Model for the current CLI session"). The plugin patches
  the model into `~/.gemini/antigravity-cli/settings.json` instead, but raw `--model` is valid.
- **agy resolves paths against its OWN project/cwd, not a shell `cd`.** A raw `cd $JAIL && agy …` did NOT
  write the U1 files into the clone-jail — they landed neither in the jail, the real repo, nor agy's scratch
  (location undetermined). **The clone-jail containment is unproven with raw agy.** Next time, contain via the
  plugin/subagent and/or `agy --add-dir`/`--project`, and VERIFY where agy actually writes before trusting it.
- **DISPROVEN — do not revisit:** no-TTY/no-controlling-terminal, SQLite store-migration wedge, running
  Antigravity-IDE shared-store contention, "`--model` is not a flag." All were generated from hook-mangled output.
- Memory `reference-agy-as-reviewer-stall` has been corrected to the above (loads automatically next session).

## What shipped this session (durable — already on origin/main)

- **#277 plan** — `docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md` (PR #300, merged).
- **#277 doc-review** — `docs/reviews/2026-06-28-silent-omission-completeness-gate-readiness.md`, verdict
  **READY**, no blocking findings (PR #301, merged).
- **Distributed-delegation doc** — `docs/external-agent-delegation/distributed-delegation.md` + blueprint/README
  cross-links (PR #299).
- **Memory corrections** — `reference_agy_as_reviewer_stall.md` + its `MEMORY.md` pointer.

## #277 build state — NOT done

- The build is a 5-unit delegated build: **U1** completeness-gate oracle + `--self-test` →
  **U2** emitted-workflow `__gate` guards → **U3** verify-panel iteration cap → **U4** team-execution
  evidence-absence prose → **U5** release surfaces + version-pin tests. Full spec + the Delegated Build
  Protocol (clone-jail + validation floor, KTD1–KTD7) are in the plan above. Plan is READY.
- **Real repo is CLEAN at baseline `40ba8fe`.** Nothing from the build was committed; no breach of the real tree.
- **U1 was attempted via raw agy and FAILED containment** (files didn't land in the jail). The jail at
  `…/scratchpad/jail-277-u1` is session-scratch and disposable — nothing to salvage from it.
- A ready-made U1 packet (closed allow-set, read-broad/write-narrow, escalation channels) was written this
  session and is sound — its content is reproducible from the plan's U1 section. Reuse the plan, not the
  scratch file (scratch is session-specific and won't survive).

## How to start the next session

1. `/work docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md`
2. Delegate each unit's coding to agy via the **`agy:runner`** subagent (NOT bash). Hand it the unit's
   write-set as a closed allow-set; read broad, write narrow.
3. **Verify where agy writes** (jail vs real repo) on the very first unit before trusting containment.
4. Use **codex** (codex plugin / `codex:codex-rescue`) for independent review.
5. Claude stays **sole committer**; run the full gate (`uv run pytest && ruff format --check && ruff check && mypy plugins/`)
   before any commit; squash-merge clean PRs.

## The honest postmortem (one line)

A great dogfooding session was wasted because I insisted on writing and debugging bash wrappers around a CLI
that two installed plugins already drive correctly. The lesson is not subtle: **use the plugins.**
