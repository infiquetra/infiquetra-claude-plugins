#!/usr/bin/env python3
"""Fleet effort-honoring seam — the one place that decides *how* a resolved effort is honored.

`effort` is a first-class value across the fleet (authored in agent frontmatter and the
team-execution A7 worker table, validated against the canonical `tier_palette.EFFORTS`
vocabulary, resolved through the three-layer cascade). Two of the three dispatch paths honor
it with a **real per-call knob** already:

* ``workflow`` (Workflow/ultracode) emits ``agent(prompt, {effort})`` — the knob rides in the
  opts dict (``execution_spec.py:982``); injecting a rider here would double-count it.
* ``external-engine`` passes ``effort=resolution.effort`` straight to the engine
  (``external-engine-workers.md:155``).

The native **Agent-tool teammate** path (``spawn_kind = "agent"``) has no harness knob for
subagent reasoning effort, so the only lever is a **labeled proxy**: a short prompt-preamble
directive (``EFFORT_RIDER``) prepended to the teammate's prompt. This mirrors the
``BUDGET_RIDER`` prepend pattern (``execution_spec.py:132``, injected at ``:1000`` / ``:1247``).

Routing all three kinds through one ``inject_effort()`` seam means "how effort is honored" lives
in exactly one function: when the harness ships a native subagent-effort parameter, the
``agent`` branch flips from "prepend rider" to "pass real knob" and nothing upstream (authoring,
lint, cascade, provenance, reconcile) changes. That single-swap property is the whole point of
KTD1.

Vocabulary is sourced from ``tier_palette.EFFORTS`` (KTD3) — never re-declared here.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402

EFFORTS: tuple[str, ...] = fleet_commons_shim.load("tier_palette").EFFORTS

# The set of spawn kinds the seam understands. Only ``agent`` gets a rider; the other two are
# real-knob pass-throughs. An unknown kind is a programming error and raises.
_PASS_THROUGH_KINDS = ("workflow", "external-engine")
_RIDER_KIND = "agent"
SPAWN_KINDS = (_RIDER_KIND, *_PASS_THROUGH_KINDS)

# One short prompt-preamble directive per canonical EFFORTS value. This is a *labeled proxy* for
# reasoning effort on the native Agent-tool path — an instruction the teammate reads, not a real
# harness knob. Keep one entry per EFFORTS member; the module-load assertion below guards parity.
EFFORT_RIDER: dict[str, str] = {
    "low": (
        "EFFORT (low): this is a light task. Move fast and direct — do the minimum reasoning "
        "the task needs, avoid deep exploration or exhaustive verification, and return promptly."
    ),
    "medium": (
        "EFFORT (medium): apply balanced effort. Reason carefully through the core of the task "
        "and check the obvious failure modes, but do not over-explore tangents or gold-plate."
    ),
    "high": (
        "EFFORT (high): this task warrants deep effort. Reason thoroughly, consider edge cases "
        "and alternative approaches, verify your work, and do not cut the analysis short."
    ),
    "xhigh": (
        "EFFORT (xhigh): apply maximum rigor. Exhaustively explore the problem space, "
        "adversarially stress-test your reasoning, enumerate and check edge cases, and verify "
        "every load-bearing claim before concluding."
    ),
}

# Fail loudly at import time if the rider ever drifts out of sync with the canonical vocabulary.
assert set(EFFORT_RIDER) == set(EFFORTS), (
    f"EFFORT_RIDER keys {sorted(EFFORT_RIDER)} must exactly match tier_palette.EFFORTS "
    f"{sorted(EFFORTS)}"
)


def inject_effort(prompt: str, effort: str, spawn_kind: str) -> str:
    """Return ``prompt`` with the resolved ``effort`` honored for ``spawn_kind``.

    * ``spawn_kind`` in ``{"workflow", "external-engine"}`` → pass-through: ``prompt`` is
      returned unchanged, because the effort already rides as a real per-call knob on that
      path and re-injecting a rider would double-count it.
    * ``spawn_kind == "agent"`` → the ``EFFORT_RIDER[effort]`` directive is prepended to
      ``prompt`` (the labeled proxy for the native Agent-tool teammate path).

    Raises ``ValueError`` for an unknown ``effort`` (not in ``tier_palette.EFFORTS``) or an
    unknown ``spawn_kind``.
    """
    if effort not in EFFORT_RIDER:
        raise ValueError(f"unknown effort {effort!r}; expected one of {EFFORTS}")
    if spawn_kind in _PASS_THROUGH_KINDS:
        return prompt
    if spawn_kind == _RIDER_KIND:
        return EFFORT_RIDER[effort] + "\n\n" + prompt
    raise ValueError(f"unknown spawn_kind {spawn_kind!r}; expected one of {SPAWN_KINDS}")


def reconcile_effort(
    resolved_effort: str,
    spawn_kind: str,
    *,
    manifest_effort: str | None = None,
    spawn_prompt: str | None = None,
) -> str | None:
    """Post-run reconciliation (R9): compare the cascade-resolved effort against what the worker
    manifest recorded for that teammate, honest per path (KTD7).

    Returns ``None`` on a match — R9's "nothing on match". Returns a named ``tiering-drift`` line
    on a mismatch. The comparison is **honest per path**:

    * ``spawn_kind`` in ``{"workflow", "external-engine"}`` (real-knob paths) — ``manifest_effort``
      is the effort value the worker manifest recorded as actually passed to ``agent()`` / the
      engine (``worker-manifest.md:48,54``). Reconciliation compares it directly against
      ``resolved_effort``; a mismatch names both values.
    * ``spawn_kind == "agent"`` (native Agent-tool teammate — no real knob) — reconciliation can
      only confirm the ``EFFORT_RIDER[resolved_effort]`` directive text reached the constructed
      spawn prompt. It never claims to observe actual harness reasoning spend; the drift line
      names the compared quantity as ``rider-text``, not "reasoning spend".

    Raises ``ValueError`` for an unknown ``resolved_effort``/``spawn_kind``, or when the
    path-appropriate evidence argument (``manifest_effort`` for real-knob paths, ``spawn_prompt``
    for the agent path) is omitted.
    """
    if resolved_effort not in EFFORT_RIDER:
        raise ValueError(f"unknown effort {resolved_effort!r}; expected one of {EFFORTS}")
    if spawn_kind in _PASS_THROUGH_KINDS:
        if manifest_effort is None:
            raise ValueError(f"reconcile_effort({spawn_kind!r}) requires manifest_effort")
        if manifest_effort == resolved_effort:
            return None
        return (
            f"tiering-drift[{spawn_kind}]: resolved effort {resolved_effort!r} vs "
            f"manifest-recorded effort {manifest_effort!r}"
        )
    if spawn_kind == _RIDER_KIND:
        if spawn_prompt is None:
            raise ValueError(f"reconcile_effort({spawn_kind!r}) requires spawn_prompt")
        if EFFORT_RIDER[resolved_effort] in spawn_prompt:
            return None
        return (
            f"tiering-drift[{spawn_kind}]: resolved effort {resolved_effort!r} — "
            "compared quantity rider-text not found in constructed spawn prompt "
            "(rider-text, not reasoning spend, is what is compared on this path)"
        )
    raise ValueError(f"unknown spawn_kind {spawn_kind!r}; expected one of {SPAWN_KINDS}")
