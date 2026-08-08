# house-style

An output-style plugin that enforces Infiquetra's house presentation rules for Claude Code turns —
turn shape, visual formatting, and how subagent work gets relayed back to the operator.

## What this plugin does

- Ships an output style at `output-styles/house-style.md` (the default, auto-discovered location —
  this plugin does not set the `outputStyles` key in `plugin.json`, since that key exists only to
  override the default location, not to declare it).
- Sets `keep-coding-instructions: true` in the style's frontmatter, so house presentation rules layer
  on top of Claude Code's normal coding behavior instead of replacing it.
- Provides a canonical subagent presentation preamble
  (`references/subagent-presentation-preamble.md`) that other levers in this repository — saga's
  workflow emitter and the 36 agent definitions across the other plugins — consume so every spawned
  agent and every saga workflow carries the same presentation rules.

## Deploying this: four steps, and the fourth is the one people miss

**The subagent preamble governs nothing until a NEW SESSION starts.** Claude Code reads every agent
definition once, at session start, and holds it in the running process. Editing a definition on disk
— or installing a newer version of a plugin that contains one — changes nothing in a session that is
already running.

This was measured rather than inferred, on 2026-08-08. The installed copy of
`saga:mechanical-executor` was edited to add an invented sixth approved operation to the block its
body tells it to emit on an unknown request. The next spawn in the same session returned the **old
five-operation block, verbatim**, while the file on disk carried six. The evidence is in
`docs/evidence/issue-704/lever-experiment.md`.

So the chain from merge to effect is:

1. Merge the pull request.
2. Bump the plugin versions (already done in the merge commit).
3. `/plugin marketplace update infiquetra-plugins` — refreshes the installed cache.
4. **Start a new session.** Until this happens, every subagent spawned is still running the previous
   definitions.

**Any measurement taken before step 4 is invalid and will understate the effect**, because the levers
this plugin ships are not yet in force. Re-running `tools/output_style_scorer.py` on a session that
began before the update measures the old behaviour wearing the new version number. Take the "after"
measurement only from sessions started after step 4, and write it to a new output path — never to
`docs/measurements/2026-08-07-baseline.json`, which is the write-once record of behaviour before any
custom style existed.

## Status

The style file (`output-styles/house-style.md`) and the canonical preamble
(`references/subagent-presentation-preamble.md`) are both present, and the `0.1.0` release is
registered in the marketplace.

Selecting the style is the operator's choice: this plugin deliberately omits `force-for-plugin`, so
it never overrides a style selected in `/config`. Changes under `output-styles/` are not picked up
live either — they need `/reload-plugins` or a new session.

Whether the style is active is confirmable rather than assumed: it emits the literal string
`::house-style::` on the first line of every closing block, so `grep -F '::house-style::'` over a
transcript answers the question.

## Related work

Style enforcement and propagation across the fleet — the saga emitter rider, the 36-agent preamble
duplication, and the visual-gating scorer measurements — are tracked in
`docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md`.
