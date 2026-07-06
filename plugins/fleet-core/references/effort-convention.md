# Fleet effort convention (#363)

The single reference for how `effort` is authored, validated, resolved, and honored across the
Infiquetra plugin fleet. Any plugin's agent frontmatter or team-execution's A7 worker table may
declare an `effort:` value — this doc is the one place that explains what happens to it. Do not
re-declare this convention per-plugin; link here instead.

## Vocabulary

Canonical vocabulary is `fleet_commons.tier_palette.EFFORTS = ("low", "medium", "high", "xhigh")`
(KTD3). Never hand-copy this tuple — resolve it via `fleet_commons_shim.load("tier_palette")`.

## Authoring

Any `plugins/*/agents/*.md` file MAY carry an `effort:` frontmatter field. If present, its value
MUST be one of `EFFORTS`. A required CI lint (`tests/test_agent_tier_lint.py`, reused by
`scripts/lint_agent_tiers.py`) globs every agent file and fails the build on an out-of-vocabulary
`effort:` (or `model:`) value. A file can opt out with `tiering_exempt: true` frontmatter,
mirroring the existing redis-channel-coach exemption.

Example (from `plugins/agy/agents/agy-coder.md`):

```yaml
---
name: agy-coder
tools: Bash
model: sonnet
effort: medium
---
```

## Resolution: the three-layer cascade

Most-specific wins, in this order:

1. Plan-authored per-unit tier (from `/plan`'s per-unit tier authoring).
2. Team-level default (an optional team-wide effort override; usually absent today).
3. Per-teammate agent-frontmatter default (`effort:`, layer 1 above).

The cascade wraps `fleet_commons.tier_resolver.resolve(role_kind, work_shape, envelope_ceiling,
operator_override)` (KTD4) — it is not a fourth standalone resolver. A plan-unit tier maps to
`operator_override={"effort": …}` when present, short-circuiting the wrap. Chaperone workers
(`Intent` = `offload` / `second-opinion` in the A7 worker table) are excluded from the cascade
entirely — their effort is an intent-driven default (`sonnet/medium` for offload, `opus/high` for
second-opinion), not a value to resolve or override (KTD5).

## Honoring: one seam, three spawn kinds

`fleet_commons.effort_rider.inject_effort(prompt, effort, spawn_kind)` is the single seam that
decides *how* a resolved effort is honored (KTD1). It understands three `spawn_kind` values:

| `spawn_kind`      | Mechanism                                                        | Real knob? |
|-------------------|-------------------------------------------------------------------|------------|
| `workflow`        | Pass-through — effort already rides in `agent(prompt, {effort})` (`execution_spec.py:982`) | Yes |
| `external-engine` | Pass-through — effort already passed as `effort=resolution.effort` (`external-engine-workers.md:155`) | Yes |
| `agent`           | `EFFORT_RIDER[effort]` directive string prepended to the prompt (native Agent-tool teammate spawn — team-execution `SKILL.md` Step B1, "Persistent Resident Workers") | No — labeled proxy |

The `agent` branch exists because the native Agent-tool teammate path has no harness-level
reasoning-effort parameter today; `EFFORT_RIDER` is a labeled proxy (a prompt-preamble directive
the teammate reads), not a real per-call knob. When the harness ships a native subagent-effort
parameter, only the `agent` branch of `inject_effort()` changes — from "prepend rider" to "pass
real knob" — and nothing upstream (authoring, lint, cascade, provenance, reconciliation) needs to
change. That single-swap property is the whole point of KTD1/KTD2.

Calling `inject_effort()` with an unknown `effort` or an unknown `spawn_kind` raises `ValueError`
rather than silently no-op'ing.

## Reconciliation

Post-run, each teammate's cascade-resolved effort is compared against the effort recorded for it
in the worker manifest (`team-execution/skills/team-execution/references/worker-manifest.md`,
`:48,54`) via `fleet_commons.effort_rider.reconcile_effort(resolved_effort, spawn_kind,
manifest_effort=..., spawn_prompt=...)`. A mismatch returns a named `tiering-drift[<spawn_kind>]`
line; a match returns `None` (nothing emitted). The comparison is honest per path (KTD7): on a
real-knob path (`workflow` / `external-engine`) pass `manifest_effort` — the manifest's effort
value is what was actually passed to `agent()` / the engine, so a mismatch names both the
resolved and manifest-recorded efforts; on the `agent` path pass `spawn_prompt` instead —
reconciliation only confirms the `EFFORT_RIDER` text for the resolved effort reached the
constructed prompt, and a mismatch names the compared quantity as `rider-text` (never "reasoning
spend") since the seam has no way to observe actual harness reasoning spend on that path.

## Where to look

- Vocabulary: `plugins/fleet-core/scripts/fleet_commons/tier_palette.py`
- Cascade: `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`
- Honoring seam: `plugins/fleet-core/scripts/fleet_commons/effort_rider.py`
- CI lint: `tests/test_agent_tier_lint.py`
- team-execution dispatch wiring: `plugins/team-execution/skills/team-execution/SKILL.md`,
  Step B1 "Persistent Resident Workers"
- Chaperone dispatch / intent defaults: `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- Worker manifest / provenance: `plugins/team-execution/skills/team-execution/references/worker-manifest.md`
