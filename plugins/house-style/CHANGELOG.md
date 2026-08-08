# Changelog

## [0.1.0] - 2026-08-08

### Added

Initial release (issue #704). This ships the whole plugin at once — the plan built it across several
units, but nothing prior to this shipped, so there is no earlier version to diff against.

- `output-styles/house-style.md`, an output style enforcing Infiquetra's house presentation rules on
  Claude Code's main thread: lead with the answer, report state rather than activity, situate before
  detailing, name the thing rather than gesturing at a bare identifier, and the other main-thread rules
  a human operator reads directly. `keep-coding-instructions: true` is set literally; `force-for-plugin`
  is not set, so the operator's own style selection is never overridden. A "Placard" section states
  plainly what the style suppresses. A single-line tell, `::house-style::`, is emitted on the main
  thread only (never by subagents) as a machine-checkable marker that the style is active on a given
  transcript.
- `references/subagent-presentation-preamble.md`, the canonical presentation-contract text, authored
  once and consumed twice: copied verbatim into 36 plugin agent definition files (Lever A, the reach
  path this plan calls the agent-definition route) and read by saga's workflow emitter to stamp the
  same text onto every emitted `agent()` prompt (Lever B, the emitter-funnel route). The two levers are
  two delivery paths for one piece of text, not two different texts.
- `references/claude-md-annotation.md`, recording why the seven Plain English rules stay in
  `~/.claude/CLAUDE.md` rather than moving into this style: `CLAUDE.md` reaches every subagent a
  session spawns, while an output style reaches only the main thread.
- `plugin.json` manifest and `README.md`. No `outputStyles` key is set — the default `output-styles/`
  location is auto-discovered by Claude Code and that key exists only to override it.

### Not in this release

- Route (c), the main-thread stamp that would additionally cover the largest block of subagent output
  written directly by the main thread rather than relayed from a subagent — deferred to follow-up work
  by the plan's KTD5 (a Key Technical Decision, a recorded design choice with its rejected
  alternatives), not cancelled.
- A concrete size threshold or target reach percentage — both are open questions in the requirements
  document and are not invented here.
