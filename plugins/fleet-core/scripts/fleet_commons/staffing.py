#!/usr/bin/env python3
"""The one staffing resolver — "role or work shape, and for review the lens, to a tier" (#1021).

Choosing a subagent's model, a workflow unit's tier, and a herdr role's vendor and model are
one decision whose inputs used to sit in four places: the work-shape tier policy and model
palette here in fleet-core, the per-repository tier overlay in saga's ``tier_defaults.py``, the
capability ratings and trust tiers in saga's ``references/engine-registry.yaml``, and the
software-development-lifecycle repository's ledger of which executor has been qualified against
which review lens. ``staffing.json`` now carries all four, and this module is the only thing that
reads them for a staffing answer.

It answers three questions and nothing else:

* ``resolve_shape(work_shape)`` — the tier for a work shape, honouring the repository overlay.
* ``resolve_role(role)`` — the vendor, model and effort for a named role.
* ``resolve_role(role, lens=...)`` — the same, plus the lens's qualification status.

It composes ``tier_palette`` and ``tier_resolver`` rather than replacing them (KTD2), and it
dispatches nothing: every call returns a :class:`StaffingDecision` describing the answer, the
layer that supplied it, and any advisory suggestion the caller passed in. Persisting that record
belongs to the run record (KTD8), not here.

The advisory tier suggestion (KTD9) is a parameter, never a call: this module never reaches out to
a suggestion service, so a staffing question can never depend on one being reachable.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402

_tier_palette = fleet_commons_shim.load("tier_palette")
_tier_resolver = fleet_commons_shim.load("tier_resolver")

MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

STAFFING_PATH = Path(__file__).resolve().parent / "staffing.json"

#: The committed-per-repository tier overlay, relative to the repository root. In this
#: repository ``.saga/`` is gitignored, so the file is local to one checkout; the resolver
#: reads a path and does not care whether git tracks it.
OVERLAY_PATH = Path(".saga/tier-defaults.json")

#: The software-development-lifecycle checkout holding the qualification ledger, resolved the
#: way ``plugins/mission-control/scripts/sdlc_manager.py`` resolves it: the environment variable
#: first, then the default checkout (KTD4).
SDLC_PATH_ENV = "INFIQUETRA_SDLC_PATH"
DEFAULT_SDLC_PATH = Path.home() / "workspace" / "infiquetra" / "infiquetra-sdlc"
LEDGER_RELATIVE_PATH = Path("config/executor-verifications.json")
LENS_CATALOGUE_RELATIVE_PATH = Path("config/lens-catalogue.json")

#: The outcome for a lens that establishes no threshold — because no executor is qualified for
#: it, because the catalogue marks it unscorable, or because the ledger could not be read. The
#: lens still reports findings; it just cannot set a bar (R12, R13).
DOCUMENTED_POLICY = "documented-policy"
QUALIFIED = "qualified"

#: Rating strength, strongest first. The registry's own three-value vocabulary.
RATINGS: tuple[str, ...] = ("STRONG", "MODERATE", "WEAK")

DEFAULT_VENDOR = "claude"


class StaffingError(ValueError):
    """Raised for an unknown work shape, role, vendor or lens, or an off-palette tier.

    Every one of those is a caller mistake that a silent default would hide on a path every
    spawn reads, so the resolver fails loud with the offending value in the message (R14).
    """


@dataclass(frozen=True)
class Qualification:
    """Whether a lens's resolved executor may establish a threshold, and why."""

    status: str
    reason: str
    lens: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "lens": self.lens}


@dataclass(frozen=True)
class StaffingDecision:
    """One staffing answer, with the inputs and the layer that supplied it.

    ``source`` names where the tier came from: ``overlay`` for the per-repository file,
    ``policy`` for the shared work-shape registry, ``role`` for a vendor pinned on the role.
    ``suggestion`` is the advisory tier the caller passed in, recorded whether or not it agrees
    with the chosen tier and never able to change it.
    """

    vendor: str
    model: str
    effort: str
    source: str
    work_shape: str
    role: str | None = None
    qualification: Qualification | None = None
    suggestion: dict[str, str] | None = None
    candidates: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def tier(self) -> str:
        """The short human form the card's acceptance criteria name, e.g. ``opus/high``."""
        return f"{self.model}/{self.effort}"

    def as_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "vendor": self.vendor,
            "model": self.model,
            "effort": self.effort,
            "tier": self.tier,
            "source": self.source,
            "work_shape": self.work_shape,
        }
        if self.role is not None:
            record["role"] = self.role
        if self.qualification is not None:
            record["qualification"] = self.qualification.as_dict()
        if self.suggestion is not None:
            record["suggestion"] = self.suggestion
        if self.candidates:
            record["candidates"] = list(self.candidates)
        return record


# --------------------------------------------------------------------------- registry


def load_staffing(path: Path | None = None) -> dict[str, Any]:
    """Load the whole staffing registry."""
    registry_path = path if path is not None else STAFFING_PATH
    document: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise StaffingError(f"staffing registry at {registry_path} must be a JSON object")
    return document


def _block(name: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    document = registry if registry is not None else load_staffing()
    block = document.get(name)
    if not isinstance(block, dict) or not block:
        raise StaffingError(f"staffing registry is missing a non-empty {name!r} object")
    return block


def work_shapes(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    return _block("work_shapes", registry)


def vendors(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    return _block("vendors", registry)


def roles(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    return _block("roles", registry)


def capability_ratings(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    return _block("capability_ratings", registry)


# --------------------------------------------------------------------------- overlay


def _overlay_path(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / OVERLAY_PATH


def load_overlay(root: Path | None = None) -> dict[str, dict[str, str]]:
    """Return the per-repository overlay; absent means ``{}``, malformed raises.

    Validation mirrors ``plugins/saga/scripts/tier_defaults.py`` exactly: an unknown work shape,
    an off-palette model or effort, and a model-effort pair above the model's ceiling are each a
    loud failure rather than a silent fall-through to the policy default.
    """
    path = _overlay_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StaffingError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise StaffingError(f"{path}: top level must be an object of work-shape to tier")
    registry = work_shapes()
    return {
        str(shape): _validate_tier(str(shape), tier, registry, f"{path}[{shape}]")
        for shape, tier in data.items()
    }


def _validate_tier(
    work_shape: str, tier: object, registry: dict[str, Any], where: str
) -> dict[str, str]:
    if work_shape not in registry:
        raise StaffingError(
            f"{where}: unknown work-shape {work_shape!r}; expected one of {sorted(registry)}"
        )
    if not isinstance(tier, dict) or "model" not in tier or "effort" not in tier:
        raise StaffingError(f"{where}: tier must be {{'model', 'effort'}}, got {tier!r}")
    model, effort = str(tier["model"]), str(tier["effort"])
    if model not in MODELS:
        raise StaffingError(f"{where}: model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise StaffingError(f"{where}: effort {effort!r} not in {EFFORTS}")
    if not _tier_palette.supports_effort(model, effort):
        raise StaffingError(
            f"{where}: {model}/{effort} is unrunnable ({model}'s ceiling is "
            f"{_tier_palette.effort_ceiling(model)!r})"
        )
    return {"model": model, "effort": effort}


def _validate_suggestion(suggestion: dict[str, str] | None) -> dict[str, str] | None:
    """Validate an advisory tier suggestion without ever letting it change the answer."""
    if suggestion is None:
        return None
    if not isinstance(suggestion, dict) or "model" not in suggestion or "effort" not in suggestion:
        raise StaffingError(f"suggestion must be {{'model', 'effort'}}, got {suggestion!r}")
    model, effort = str(suggestion["model"]), str(suggestion["effort"])
    if model not in MODELS:
        raise StaffingError(f"suggestion model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise StaffingError(f"suggestion effort {effort!r} not in {EFFORTS}")
    return {"model": model, "effort": effort}


# --------------------------------------------------------------------------- shape


def resolve_shape(
    work_shape: str,
    *,
    root: Path | None = None,
    suggestion: dict[str, str] | None = None,
    vendor: str = DEFAULT_VENDOR,
) -> StaffingDecision:
    """Resolve a work shape to a tier: the repository overlay first, then the shared policy."""
    registry = work_shapes()
    if work_shape not in registry:
        raise StaffingError(
            f"unknown work-shape {work_shape!r}; expected one of {sorted(registry)}"
        )
    recorded = _validate_suggestion(suggestion)
    overlay = load_overlay(root)
    if work_shape in overlay:
        tier = overlay[work_shape]
        source = "overlay"
    else:
        resolution = _tier_resolver.resolve(None, work_shape)
        tier = {"model": resolution.model, "effort": resolution.effort}
        source = "policy"
    return StaffingDecision(
        vendor=vendor,
        model=tier["model"],
        effort=tier["effort"],
        source=source,
        work_shape=work_shape,
        suggestion=recorded,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="staffing.py",
        description="Resolve a work shape, a role, or a role and review lens to a tier.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="resolve one staffing question")
    resolve.add_argument("--shape", help="a work shape from the staffing registry")
    resolve.add_argument(
        "--suggest",
        metavar="MODEL/EFFORT",
        help="an advisory tier suggestion, recorded beside the answer and never able to change it",
    )
    resolve.add_argument(
        "--json", action="store_true", help="print the whole decision record instead of the tier"
    )

    return parser


def _parse_suggestion(raw: str | None) -> dict[str, str] | None:
    if raw is None:
        return None
    if raw.count("/") != 1:
        raise StaffingError(f"--suggest must be MODEL/EFFORT, got {raw!r}")
    model, effort = raw.split("/")
    return {"model": model, "effort": effort}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except StaffingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    return _cli_resolve(args)


def _cli_resolve(args: argparse.Namespace) -> int:
    if not args.shape:
        raise StaffingError("pass --shape with a work shape from the staffing registry")
    suggestion = _parse_suggestion(args.suggest)
    decision = resolve_shape(args.shape, suggestion=suggestion)
    if args.json:
        print(json.dumps(decision.as_dict(), indent=2, sort_keys=True))
    else:
        print(_short_form(decision))
    return 0


def _short_form(decision: StaffingDecision) -> str:
    """The short human form the card's acceptance criteria assert, character for character."""
    if decision.role is None:
        return decision.tier
    line = f"{decision.vendor} {decision.model}/{decision.effort}"
    if decision.qualification is not None:
        line += f" {decision.qualification.status}"
    return line


if __name__ == "__main__":
    raise SystemExit(main())
