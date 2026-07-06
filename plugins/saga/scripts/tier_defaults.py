#!/usr/bin/env python3
"""Persisted per-repo tier preferences (#368).

A committed ``.saga/tier-defaults.json`` overlay pins repo-tuned work-shape -> tier defaults over the
shared ``tier_policy.json`` registry, so ``/plan`` proposes accreted preferences instead of re-deriving
cold on every run. Precedence (AC7): **repo overlay > issue-carried band > shared registry**. The file
is committed (``.saga/`` is not git-ignored), so the whole repo/team shares the accreted judgment. A
missing file falls back cleanly; a malformed one (bad JSON, unknown work-shape, off-palette or
unrunnable tier) fails loud -- the same halt-not-degrade discipline as the rest of the tier system.
Every persisted override originates from an explicit operator confirmation in ``/plan`` (never a silent
auto-promotion).
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
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

# Committed, per-repo (sibling of the repo's .github/, NOT the git-ignored .claude/saga cache).
DEFAULTS_PATH = Path(".saga/tier-defaults.json")

# The issue-carried band section mission-control stamps at issue-create time (#368 AC5).
# Format contract with sdlc_manager._append_tier_band: an H3 header followed by "model/effort".
TIER_BAND_HEADER = "Recommended Tier Band"

Tier = dict[str, str]


class TierDefaultsError(ValueError):
    """Raised for a malformed ``.saga/tier-defaults.json`` (bad JSON, unknown shape, bad tier)."""


def _defaults_path(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / DEFAULTS_PATH


def _validate_shape_and_tier(
    work_shape: str, tier: object, registry: dict[str, dict], where: str
) -> Tier:
    if work_shape not in registry:
        raise TierDefaultsError(
            f"{where}: unknown work-shape {work_shape!r}; expected one of {sorted(registry)}"
        )
    if not isinstance(tier, dict) or "model" not in tier or "effort" not in tier:
        raise TierDefaultsError(f"{where}: tier must be {{'model', 'effort'}}, got {tier!r}")
    model, effort = str(tier["model"]), str(tier["effort"])
    if model not in MODELS:
        raise TierDefaultsError(f"{where}: model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise TierDefaultsError(f"{where}: effort {effort!r} not in {EFFORTS}")
    if not _tier_palette.supports_effort(model, effort):
        raise TierDefaultsError(
            f"{where}: {model}/{effort} is unrunnable ({model}'s ceiling is "
            f"{_tier_palette.effort_ceiling(model)!r})"
        )
    return {"model": model, "effort": effort}


def _registry_default(work_shape: str) -> Tier:
    res = _tier_resolver.resolve(None, work_shape)
    return {"model": res.model, "effort": res.effort}


def load_tier_defaults(root: Path | None = None) -> dict[str, Tier]:
    """Return the repo overlay ``{work_shape: {model, effort}}``; missing => {}, malformed => raise."""
    path = _defaults_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise TierDefaultsError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise TierDefaultsError(f"{path}: top level must be an object of work-shape -> tier")
    registry = _tier_resolver.load_policy()
    return {
        str(ws): _validate_shape_and_tier(str(ws), tier, registry, f"{path}[{ws}]")
        for ws, tier in data.items()
    }


def resolve_tier_with_overlay(work_shape: str, root: Path | None = None) -> Tier:
    """Repo overlay > shared registry default for ``work_shape`` (AC1)."""
    overlay = load_tier_defaults(root)
    if work_shape in overlay:
        return overlay[work_shape]
    return _registry_default(work_shape)


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
    return _registry_default(work_shape)


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
    registry = _tier_resolver.load_policy()
    tier = _validate_shape_and_tier(
        work_shape, {"model": model, "effort": effort}, registry, f"write[{work_shape}]"
    )
    existing = load_tier_defaults(root)  # re-validates any existing entries too
    existing[work_shape] = tier
    path = _defaults_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
