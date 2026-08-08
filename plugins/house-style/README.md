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

## Status

The style file (`output-styles/house-style.md`) and the canonical preamble
(`references/subagent-presentation-preamble.md`) are both present. Marketplace registration and the
version bookkeeping for the `0.1.0` release land in the plan's closing unit.

Selecting the style is the operator's choice: this plugin deliberately omits `force-for-plugin`, so
it never overrides a style selected in `/config`. Changes under `output-styles/` are not picked up
live — they need `/reload-plugins` or a new session.

Whether the style is active is confirmable rather than assumed: it emits the literal string
`::house-style::` on the first line of every closing block, so `grep -F '::house-style::'` over a
transcript answers the question.

## Related work

Style enforcement and propagation across the fleet — the saga emitter rider, the 36-agent preamble
duplication, and the visual-gating scorer measurements — are tracked in
`docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md`.
