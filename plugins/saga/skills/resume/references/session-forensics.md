# Tier 2 — Zero-Save Session Forensics (fallback only)

Tier 2 is `/resume`'s **last resort**: a slim, Claude-only port of CE's session forensics over local JSONL
session logs. It runs **only** when Tier 1 found **no saga AND no resolvable issue**. It is context-safe by
construction — the orchestrator never reads session content; a generic synthesis agent does, file-mediated.

## The corrected trigger — same-machine work that never wrote a saga

Tier 2 fires for **same-machine work that left session logs but no saga**:

- raw sessions before any lifecycle command ran;
- pre-saga-adoption work (before the saga model existed for this thread);
- a session that crashed before writing its first tick.

It is **NOT** "a fresh clone on a new machine." On a fresh machine the local `~/.claude/projects/` session
logs are simply **absent** — there is nothing to forensically read. That case falls back to the durable
committed `docs/*` (Tier 1's substrate), not to Tier 2.

## The discovery pipeline (MVP — recency only)

```bash
python3 plugins/saga/scripts/discover_sessions.py --repo <repo-folder> --days <N> --exclude <current-session-id> [--projects-root <path>]
```

`discover_sessions.py` finds this repo's session files, **recency-ranks** them, **caps at 5**, and
drops any id passed via `--exclude`. It returns the path list plus a one-line `_meta` summary —
**paths and metadata only, never session content**.

`--exclude <current-session-id>` is **mandatory**, not optional: the script has **no** auto-detection of
the current session, so exclusion depends entirely on the flag being passed. Omit it and the current
session is returned, its skeleton extracted to scratch, and synthesized — violating the
"Never analyze the current session" guardrail (below) and wasting one of the 5 cap slots.
`<current-session-id>` is this session's own `*.jsonl` basename under `~/.claude/projects/<repo>/` (without
the `.jsonl` suffix); the flag is repeatable / comma-separated to drop more than one. This MVP ranks by recency alone: **no keyword or
branch ranking** (that is queued — see the keyword note at the bottom). Pick a `--days` window from the
ask's time signal (today = 1, recent / this week / no signal = 7, this month = 30, broad = 90); start
narrow, widen only if a narrow scan finds nothing.

## The context-safety contract — paths, not content

This is the load-bearing rule of Tier 2, ported from CE's guardrails:

- **The orchestrator NEVER Reads or cats a raw `.jsonl` or a skeleton file.** Discovery returns paths;
  extraction writes to scratch; only the synthesis agent reads the extracts.
- **Extraction is file-mediated.** `--output` writes the skeleton straight to a scratch file; the
  orchestrator sees only a one-line `_meta` status (`wrote` / `bytes` / `parse_errors`), never the bytes.
- **The generic synthesis agent reads the extracts; the orchestrator does not.** The agent has its own
  context window — bulk session content lives there, never in the orchestrator's working state.
- **Never paste extract content into the dispatch prompt.** Pass scratch **paths**, never skeleton text.

## The CE synthesis guardrails (verbatim — bake into the dispatch prompt)

- **Never read entire session files into context.** Session files are 1-7 MB; always extract first, reason
  over the filtered skeleton.
- **Never extract or reproduce tool call inputs/outputs verbatim.** Summarize what was attempted and what
  happened.
- **Never include thinking or reasoning block content.** Internal reasoning is not actionable.
- **Never analyze the current session.** Its history is already available to the caller (hence `--exclude`).
- **Surface technical content, not personal content.** Sessions hold everything; use judgment.
- **Fail fast on access errors.** If discovery fails on permissions, report it and stop — do not retry the
  same operation with different tools.

## The recipe — scratch dir + file-mediated extract + generic-agent dispatch

```bash
SCRATCH=$(mktemp -d -t resume-sessions-XXXXXX)
```

For each discovered session, extract its skeleton file-mediated to scratch:

```bash
python3 plugins/saga/scripts/extract_session_skeleton.py --output "$SCRATCH/<id>.skeleton.txt" < <session-file>
```

`extract_session_skeleton.py` reads one JSONL session on **stdin** and writes the filtered skeleton to
`--output`; stdout carries only the one-line `_meta` status.

Then dispatch a **generic** `Explore` / `Task` agent (this plugin has **no** `agents/` dir — do **NOT**
reference a named `resume-session-historian` or any `ce-*` agent; mirror `/code-review` SKILL line 164).
Run it on a mid-tier model — the synthesizer needs no frontier reasoning. The dispatch prompt:

- names the problem topic in one sentence;
- lists the scratch **paths** (one per session) with their platform / timestamp metadata — **paths only,
  never content**;
- embeds the synthesis guardrails above (read ONLY these paths, never read raw `~/.claude/projects/`,
  never invoke `Skill`, never reproduce tool I/O or thinking, never analyze the current session);
- asks for prose under: *What was tried before / What didn't work / Key decisions / Related context*;
- adds the filter rule: surface only findings relevant to this specific problem; ignore unrelated work
  from the same sessions.

The agent reads each skeleton via its native file-read tool and returns prose. Optional explicit cleanup
(the OS reclaims it regardless):

```bash
rm -rf "$SCRATCH"
```

The synthesized prose feeds the route decision (`/resume` Phase 4) and the Phase 5 re-entry tick — Tier 2
is the **one** branch where minting a **new** saga is correct (there is no restored id to reuse).

## Queued — keyword / branch ranking (cap 10)

This MVP ranks by recency only. The future ranking derives 2-4 keywords from the ask's topic
(cap **10** keywords), filters sessions by `match_count`, and breaks ties by per-keyword counts — plus a
branch filter for Claude Code sessions (with the keyword-fallback caveat that `gitBranch` is captured at
the first user message, so a mid-session `git checkout` is invisible to branch-match). Until then,
recency + the 5-session cap bound the dig.
