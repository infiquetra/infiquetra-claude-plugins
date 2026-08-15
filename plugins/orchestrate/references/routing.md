# Routing

Planning chooses a vendor, model, and effort for each child before anyone
launches. The operator sees that choice. This document is the map, not the
launcher.

## Two vocabularies, one resolution

`tier_policy.json` still names the Claude-facing work shapes (`judgment`,
`mechanical`, `purely-mechanical`, and the role-tier aliases). `resolve()`
reads that file and returns a `{model, effort}` pair on the Claude ladder.

`execution_classes` in `models.json` is the portable vocabulary
(`review-high`, `work-medium`, `scan-low`, …). `resolve_for_runtime(class,
runtime)` translates the preferred pair and the ordered `fallbacks` into
that runtime's own model names and collapsed effort.

Planning maps a work shape onto an execution class (`SHAPE_TO_EXECUTION_CLASS`
in `planning.py`), then calls `resolve_for_runtime`. A name that is already
an execution class passes through. An unknown name is an error, not a
default.

The same execution class therefore resolves to different concrete models
for Claude and for Grok. That is the point of the sibling resolver.

## Vendor order

The declared vendor walk is `claude`, `codex`, `grok`, `qwen`, `muse`,
`agy`. The first available vendor in that walk, starting from the
preferred vendor (the operator override if one was given, otherwise
`claude`), is selected.

An unavailable preferred vendor is not a rejection. The next name in the
walk is tried, and the substitution is recorded on the planned child
(`from`, `to`, `reason`). An explicit operator vendor, model, or effort
is recorded as an override even when it happens to match the default.

Availability is injected. Planning does not probe `PATH` on its own:
a missing binary on the operator's laptop is not a reason for a unit
test, or a dry plan, to reroute.

Model `fallbacks` from the execution class travel with the child. They
are the in-vendor ladder. They are not a second vendor walk.

## What this does not do

Routing does not launch. It does not reserve a slot. It does not decide
that a vendor with a full work-in-progress bound is "unavailable" —
that is admission, and the outcome is a queue, not a substitution.

It does not invent a third model table. A new vendor is a
`resolve_for_runtime` mapping, not a new file in this plugin.
