#!/usr/bin/env python3
"""Per-repository tier preferences (#368) — a thin shim over fleet-core's staffing resolver.

A ``.saga/tier-defaults.json`` overlay pins repo-tuned work-shape -> tier defaults over the shared
work-shape registry, so ``/plan`` proposes accreted preferences instead of re-deriving cold on every
run. Precedence (AC7): **repo overlay > issue-carried band > shared registry**. A missing file falls
back cleanly; a malformed one (bad JSON, unknown work-shape, off-palette or unrunnable tier) fails
loud -- the same halt-not-degrade discipline as the rest of the tier system. Every persisted override
originates from an explicit operator confirmation in ``/plan`` (never a silent auto-promotion).

Since issue #1021 the overlay reading, its validation and the registry lookup live once, in
``fleet_commons.staffing``. The five public functions below keep their signatures and their
behaviour and delegate; only the duplicated half moved. ``parse_tier_band`` stays here, because it
parses a GitHub issue body, which is saga's concern rather than fleet-core's.

Note on the word "committed": this module reads a path and does not care whether git tracks it. In
this repository ``.gitignore`` ignores ``.saga/`` outright, so the overlay is local to one checkout.
Whether that should change is an open question recorded in the issue #1021 plan, and it is not this
module's to answer.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)

_tier_palette = fleet_commons_shim.load("tier_palette")
_tier_resolver = fleet_commons_shim.load("tier_resolver")
try:
    _staffing = fleet_commons_shim.load("staffing")
except RuntimeError as exc:  # pragma: no cover - exercised by the install-obligation test
    # saga 0.160.0 requires fleet-core 0.27.0 or later: the overlay read moved there (issue
    # #1021). This repository has two installed plugin roots and a release has updated one and
    # not the other six times, so say which version is needed and which was found rather than
    # letting a bare "module not found" reach the operator.
    _resolved = getattr(fleet_commons_shim, "resolved_version", lambda: "unknown")()
    raise RuntimeError(
        "saga requires fleet-core 0.27.0 or later for fleet_commons.staffing; the resolved "
        f"fleet-core is {_resolved}. Update the fleet-core plugin in this root, and check BOTH "
        f"installed roots — they have diverged before. Underlying error: {exc}"
    ) from exc
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

# Per-repository, beside the repo's .github/ and distinct from the .claude/saga cache. Whether
# this path is tracked is the repository's choice; this module only reads it.
#
# Bound to fleet-core's constant rather than re-declared (#1021): the read goes through
# staffing.load_overlay and the write goes through _defaults_path below, so two independently
# edited copies of this path would silently point the writer and the reader at different files —
# the exact duplicate-source class this component exists to remove.
DEFAULTS_PATH: Path = _staffing.OVERLAY_PATH

# The issue-carried band section mission-control stamps at issue-create time (#368 AC5).
# Format contract with sdlc_manager._append_tier_band: an H3 header followed by "model/effort".
TIER_BAND_HEADER = "Recommended Tier Band"

Tier = dict[str, str]


class TierDefaultsError(ValueError):
    """Raised for a malformed ``.saga/tier-defaults.json`` (bad JSON, unknown shape, bad tier)."""


def _defaults_path(root: Path | None = None) -> Path:
    """The overlay path the writer targets — the same one ``staffing.load_overlay`` reads."""
    return _staffing.overlay_path(root)


def load_tier_defaults(root: Path | None = None) -> dict[str, Tier]:
    """Return the repo overlay ``{work_shape: {model, effort}}``; missing => {}, malformed => raise.

    Delegates to ``fleet_commons.staffing.load_overlay``, which owns the one implementation of the
    read and its validation. ``StaffingError`` is re-raised as ``TierDefaultsError`` so callers that
    already catch the saga exception keep working.
    """
    try:
        return _staffing.load_overlay(root=root)
    except _staffing.StaffingError as exc:
        raise TierDefaultsError(str(exc)) from exc


def resolve_tier_with_overlay(work_shape: str, root: Path | None = None) -> Tier:
    """Repo overlay > shared registry default for ``work_shape`` (AC1)."""
    try:
        decision = _staffing.resolve_shape(work_shape, root=root)
    except _staffing.StaffingError as exc:
        raise TierDefaultsError(str(exc)) from exc
    return {"model": decision.model, "effort": decision.effort}


def resolve_tier_for_plan(
    work_shape: str, issue_band: Tier | None = None, root: Path | None = None
) -> Tier:
    """Precedence (AC7): repo overlay > issue band > shared registry.

    The repo override is closest to execution and wins the coarser issue-time band; the band, when
    present and unoverridden, seeds the work-shape's proposed tier instead of the cold registry default.
    """
    overlay = load_tier_defaults(root)
    if work_shape in overlay:
        return overlay[work_shape]
    if issue_band is not None:
        return {"model": str(issue_band["model"]), "effort": str(issue_band["effort"])}
    return resolve_tier_with_overlay(work_shape, root)


def _unfenced_lines(body: str) -> list[str]:
    """Lines of ``body`` outside fenced code blocks (``` / ~~~), fence markers excluded.

    Header detection must be fence-aware on BOTH sides of the stamp/parse contract: a Verification
    section showing example output, or prose demonstrating the format, must neither parse as a real
    band nor suppress the compile-time stamp. Mirrored by ``sdlc_manager._has_tier_band_section``.
    """
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return out


def parse_tier_band(body: str) -> Tier | None:
    """Extract the issue-carried ``### Recommended Tier Band`` from an issue body (AC6).

    Absence is tolerant (an issue without a band is normal — returns None, callers fall through to
    the registry). A band that is *present but invalid* (unparseable value, off-palette or unrunnable
    tier, or duplicated sections) fails loud with ``TierDefaultsError`` — it claims to be a band, so
    a silent fall-through would quietly discard a bad stamp instead of surfacing it
    (halt-not-degrade). Only a real H3 header line outside a fenced code block counts as the band.
    """
    header_re = re.compile(rf"###\s+{re.escape(TIER_BAND_HEADER)}\s*")
    lines = _unfenced_lines(body)
    header_indexes = [i for i, line in enumerate(lines) if header_re.fullmatch(line)]
    if not header_indexes:
        return None
    if len(header_indexes) > 1:
        raise TierDefaultsError(
            f"issue band: {len(header_indexes)} '### {TIER_BAND_HEADER}' sections; expected one"
        )
    # First non-empty unfenced line after the header, up to the next H3 (or end of body).
    value = ""
    for line in lines[header_indexes[0] + 1 :]:
        if line.startswith("### "):
            break
        if line.strip():
            value = line.strip()
            break
    parts = value.split("/")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise TierDefaultsError(
            f"issue band: expected 'model/effort' under '### {TIER_BAND_HEADER}', got {value!r}"
        )
    model, effort = parts[0].strip(), parts[1].strip()
    if model not in MODELS:
        raise TierDefaultsError(f"issue band: model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise TierDefaultsError(f"issue band: effort {effort!r} not in {EFFORTS}")
    if not _tier_palette.supports_effort(model, effort):
        raise TierDefaultsError(
            f"issue band: {model}/{effort} is unrunnable ({model}'s ceiling is "
            f"{_tier_palette.effort_ceiling(model)!r})"
        )
    return {"model": model, "effort": effort}


def write_tier_default(work_shape: str, model: str, effort: str, root: Path | None = None) -> Path:
    """Persist one confirmed override (read-merge-write); validated; never clobbers other keys (AC2)."""
    try:
        tier = _staffing.validate_tier(
            work_shape, {"model": model, "effort": effort}, where=f"write[{work_shape}]"
        )
    except _staffing.StaffingError as exc:
        raise TierDefaultsError(str(exc)) from exc
    existing = load_tier_defaults(root)  # re-validates any existing entries too
    existing[work_shape] = tier
    path = _defaults_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
