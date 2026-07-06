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
