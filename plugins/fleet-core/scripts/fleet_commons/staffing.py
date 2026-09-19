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
import os
import sys
from dataclasses import dataclass, field, replace
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

    ``source`` names where the *tier* came from: ``overlay`` for the per-repository file, or
    ``policy`` for the shared work-shape registry. A vendor pinned on a role is not a tier, so it
    is reported separately in ``vendor_pinned_by_role`` rather than overwriting that provenance.
    ``suggestion`` is the advisory tier the caller passed in, recorded whether or not it agrees
    with the chosen tier and never able to change it.
    """

    vendor: str
    model: str
    effort: str
    source: str
    work_shape: str
    role: str | None = None
    vendor_pinned_by_role: bool = False
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
            record["vendor_pinned_by_role"] = self.vendor_pinned_by_role
        if self.qualification is not None:
            record["qualification"] = self.qualification.as_dict()
        if self.suggestion is not None:
            record["suggestion"] = self.suggestion
        if self.candidates:
            record["candidates"] = list(self.candidates)
        return record


# --------------------------------------------------------------------------- registry


#: A staffing registry far larger than the real one (26 KB) is a corrupted or hostile file, not
#: a legitimate edit. Reading it whole into memory on a path meant for every spawn is the cost
#: this ceiling avoids.
MAX_REGISTRY_BYTES = 4 * 1024 * 1024

_REGISTRY_CACHE: dict[Path, tuple[int, int, dict[str, Any]]] = {}


def load_staffing(path: Path | None = None) -> dict[str, Any]:
    """Load the whole staffing registry, memoized on the file's size and modification time.

    One ``resolve_role`` call used to read and re-parse this file five times, because every
    block accessor reloaded it. The cache key is ``(st_size, st_mtime_ns)``, so an edit on disk
    is picked up on the next call and a test that rewrites the registry still sees its own bytes.
    """
    registry_path = path if path is not None else STAFFING_PATH
    try:
        stat = registry_path.stat()
    except OSError as exc:
        raise StaffingError(f"staffing registry at {registry_path} is unreadable: {exc}") from exc
    if stat.st_size > MAX_REGISTRY_BYTES:
        raise StaffingError(
            f"staffing registry at {registry_path} is {stat.st_size} bytes, above the "
            f"{MAX_REGISTRY_BYTES}-byte ceiling"
        )

    cached = _REGISTRY_CACHE.get(registry_path)
    if cached is not None and cached[0] == stat.st_size and cached[1] == stat.st_mtime_ns:
        return cached[2]

    try:
        document: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise StaffingError(
            f"staffing registry at {registry_path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise StaffingError(f"staffing registry at {registry_path} must be a JSON object")
    _REGISTRY_CACHE[registry_path] = (stat.st_size, stat.st_mtime_ns, document)
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


def overlay_path(root: Path | None = None) -> Path:
    """Where the per-repository overlay lives, relative to ``root`` or the working directory.

    Public because saga's ``tier_defaults`` writes the file this module reads; a second copy of
    the path would let the writer and the reader drift onto different files silently.
    """
    return (root or Path.cwd()) / OVERLAY_PATH


def load_overlay(root: Path | None = None) -> dict[str, dict[str, str]]:
    """Return the per-repository overlay; absent means ``{}``, malformed raises.

    Validation mirrors ``plugins/saga/scripts/tier_defaults.py`` exactly: an unknown work shape,
    an off-palette model or effort, and a model-effort pair above the model's ceiling are each a
    loud failure rather than a silent fall-through to the policy default.
    """
    path = overlay_path(root)
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
        str(shape): validate_tier(str(shape), tier, registry=registry, where=f"{path}[{shape}]")
        for shape, tier in data.items()
    }


def validate_tier(
    work_shape: str,
    tier: object,
    *,
    registry: dict[str, Any] | None = None,
    where: str = "tier",
) -> dict[str, str]:
    """Validate one ``{work_shape: {model, effort}}`` pair against the palette.

    Public because saga's ``tier_defaults.write_tier_default`` validates an operator-confirmed
    override before persisting it, and that check must be the same one the overlay reader uses —
    two copies is how a write starts accepting a pair the read would refuse.
    """
    registry = registry if registry is not None else work_shapes()
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
    if not _tier_palette.supports_effort(model, effort):
        raise StaffingError(
            f"suggestion {model}/{effort} is unrunnable ({model}'s ceiling is "
            f"{_tier_palette.effort_ceiling(model)!r})"
        )
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
        # Pass the already-loaded block: tier_resolver.load_policy() re-reads and re-parses the
        # whole registry on every call, which is the read the memoized loader exists to avoid.
        resolution = _tier_resolver.resolve(None, work_shape, policy=registry)
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


def translate_for_vendor(vendor: str, model: str, effort: str) -> tuple[str, str]:
    """Render a Claude-palette tier as a model and effort the given vendor can actually run.

    The route is the portable execution-class vocabulary the vendor palette is already keyed on:
    Claude's own row maps each portable name to a Claude model, so inverting it turns ``opus``
    into ``gpt-5.6-terra``, which every other vendor's row then maps to its own model. The effort
    collapses through the same per-vendor table a launch would use.

    ``claude`` passes through unchanged. A vendor whose launch arguments are unverified
    (``runtime_supported`` false) is refused rather than answered, because an answer naming it
    would be a tier nobody can launch.
    """
    palette = vendors()
    if vendor not in palette:
        raise StaffingError(f"unknown vendor {vendor!r}; expected one of {sorted(palette)}")
    if vendor == DEFAULT_VENDOR:
        return model, effort
    row = palette[vendor]
    if not row.get("runtime_supported"):
        raise StaffingError(
            f"vendor {vendor!r} is in the palette but not a supported runtime "
            f"({row.get('unsupported_reason', 'no reason recorded')})"
        )

    claude_models = palette[DEFAULT_VENDOR]["models"]
    portable = {target: name for name, target in claude_models.items()}
    if model not in portable:
        raise StaffingError(
            f"no portable execution-class name maps to {model!r}, so it cannot be rendered for "
            f"{vendor!r}; {DEFAULT_VENDOR}'s palette covers {sorted(portable)}"
        )
    vendor_model = row["models"].get(portable[model])
    if not vendor_model:
        raise StaffingError(f"vendor {vendor!r} has no model for {portable[model]!r}")

    accepted = row["accepted_efforts"]
    collapsed = row.get("effort_collapse", {}).get(effort, effort)
    if collapsed not in accepted:
        raise StaffingError(
            f"vendor {vendor!r} accepts {accepted}, and {effort!r} collapses to {collapsed!r}"
        )
    return str(vendor_model), str(collapsed)


# --------------------------------------------------------------------------- role


def _role_row(role: str) -> dict[str, Any]:
    table = roles()
    if role not in table:
        raise StaffingError(f"unknown role {role!r}; expected one of {sorted(table)}")
    return dict(table[role])


def _rating_strength(rating: str) -> int:
    """Strength as a sort key: STRONG above MODERATE above WEAK, an unknown rating last."""
    try:
        return RATINGS.index(rating)
    except ValueError:
        return len(RATINGS)


def candidates_for(role: str) -> tuple[dict[str, Any], ...]:
    """Executors that rate the role's capability, strongest rating first.

    Ties break on the cheaper cost-and-speed rank, which is the tie-break rule the engine
    registry's own header states: rating dominates first, and ``cost_speed_rank`` only separates
    variants that rate the requested capability equally.
    """
    row = _role_row(role)
    if "capability" not in row:
        raise StaffingError(f"role {role!r} is missing a capability")
    capability = str(row["capability"])
    ratings = capability_ratings()
    found: list[dict[str, Any]] = []
    engines = ratings.get("engines")
    if not isinstance(engines, dict):
        raise StaffingError("staffing registry's capability_ratings is missing an engines object")
    for key, engine in engines.items():
        profile = engine.get("capability_profile") or {}
        rated = profile.get(capability)
        if not rated:
            continue
        try:
            found.append(
                {
                    "executor": key,
                    "engine_id": engine["engine_id"],
                    "variant": engine["variant"],
                    "model_identity": engine["model_identity"],
                    "capability": capability,
                    "rating": rated["rating"],
                    "note": rated.get("note", ""),
                    "trust_tier": engine["trust_tier"],
                    "cost_speed_rank": engine["cost_speed_rank"],
                    "last_validated": engine["last_validated"],
                }
            )
        except (KeyError, TypeError) as exc:
            raise StaffingError(f"capability_ratings row {key!r} is malformed: {exc}") from exc
    found.sort(
        key=lambda candidate: (_rating_strength(candidate["rating"]), candidate["cost_speed_rank"])
    )
    return tuple(found)


def resolve_role(
    role: str,
    *,
    lens: str | None = None,
    root: Path | None = None,
    suggestion: dict[str, str] | None = None,
    checkout: Path | None = None,
) -> StaffingDecision:
    """Resolve a role to a vendor, model and effort, and for a reviewing role its lens status.

    The tier comes from the role's work shape, so the per-repository overlay still wins where it
    names that shape. A role may pin a vendor; the pin is reported in ``vendor_pinned_by_role``
    and does not change ``source``, which names only where the tier came from.

    A lens only ever narrows the answer: it attaches the qualification status read from the
    ledger, which can downgrade a scoring executor to the documented-policy outcome but never
    promote one.
    """
    row = _role_row(role)
    if "work_shape" not in row:
        raise StaffingError(f"role {role!r} is missing a work_shape")
    work_shape = str(row["work_shape"])
    vendor = str(row.get("vendor", DEFAULT_VENDOR))
    if vendor not in vendors():
        raise StaffingError(f"role {role!r} pins unknown vendor {vendor!r}")
    base = resolve_shape(work_shape, root=root, suggestion=suggestion, vendor=vendor)
    model, effort = translate_for_vendor(vendor, base.model, base.effort)

    qualification: Qualification | None = None
    if lens is None:
        if _is_reviewing_role(role):
            raise StaffingError(
                f"role {role!r} reviews, so it needs a lens: pass one to learn whether this "
                "executor may establish a threshold for it"
            )
    else:
        if not _is_reviewing_role(role):
            raise StaffingError(
                f"a lens applies to a reviewing role; {role!r} reviews nothing "
                f"(its capability is {row['capability']!r})"
            )
        qualification = qualify_lens(
            lens, vendor=vendor, model=model, effort=effort, checkout=checkout
        )

    return StaffingDecision(
        vendor=vendor,
        model=model,
        effort=effort,
        source=base.source,
        work_shape=work_shape,
        role=role,
        vendor_pinned_by_role="vendor" in row,
        qualification=qualification,
        suggestion=base.suggestion,
    )


def _is_reviewing_role(role: str) -> bool:
    """A role reviews when its capability is the registry's adversarial-review one."""
    row = _role_row(role)
    if "capability" not in row:
        raise StaffingError(f"role {role!r} is missing a capability")
    return str(row["capability"]) == "adversarial-review"


# --------------------------------------------------------------------------- lens


def sdlc_root(explicit: Path | None = None) -> Path | None:
    """Resolve the software-development-lifecycle checkout, or report its absence.

    The resolution order is the one ``plugins/mission-control/scripts/sdlc_manager.py`` uses: an
    explicit path, then the ``INFIQUETRA_SDLC_PATH`` environment variable, then the default
    checkout. It deliberately does **not** fall through: an explicit path or a configured variable
    that is not a directory returns ``None`` rather than quietly resolving somewhere the caller
    did not name. (Mission Control's own helper returns the configured path unchecked; this one
    checks, because its ``None`` is a meaningful answer rather than an error.)

    ``None`` means no checkout is there — a documented-policy outcome for a lens, never an error,
    because a missing sibling repository must not break every spawn.
    """
    if explicit is not None:
        return explicit if explicit.is_dir() else None
    configured = os.environ.get(SDLC_PATH_ENV)
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_dir() else None
    return DEFAULT_SDLC_PATH if DEFAULT_SDLC_PATH.is_dir() else None


def _read_json(path: Path) -> Any | None:
    """Read a JSON document, or ``None`` when it is absent or unreadable.

    ``ValueError`` rather than ``json.JSONDecodeError``: a file with non-UTF-8 bytes raises
    ``UnicodeDecodeError``, which is a ``ValueError`` and neither an ``OSError`` nor a decode
    error, so a narrower clause let a corrupted file escape the handler written to absorb it.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def lens_catalogue(root: Path | None = None) -> tuple[dict[str, Any], str | None]:
    """Return ``{lens id: entry}`` and the catalogue version, or ``({}, None)`` when unreadable."""
    checkout = sdlc_root(root)
    if checkout is None:
        return {}, None
    document = _read_json(checkout / LENS_CATALOGUE_RELATIVE_PATH)
    if not isinstance(document, dict):
        return {}, None
    entries = document.get("lenses")
    if not isinstance(entries, list):
        return {}, None
    catalogue = {
        str(entry["id"]): entry for entry in entries if isinstance(entry, dict) and "id" in entry
    }
    return catalogue, document.get("version")


def verification_ledger(root: Path | None = None) -> list[dict[str, Any]]:
    """Return the ledger's entries, or ``[]`` when the checkout or the file is unreadable."""
    checkout = sdlc_root(root)
    if checkout is None:
        return []
    document = _read_json(checkout / LEDGER_RELATIVE_PATH)
    if not isinstance(document, dict):
        return []
    entries = document.get("entries")
    return entries if isinstance(entries, list) else []


def qualify_lens(
    lens: str,
    *,
    vendor: str,
    model: str,
    effort: str,
    checkout: Path | None = None,
) -> Qualification:
    """Whether this executor may establish a threshold for this lens, and why.

    ``qualified`` needs an entry matching the lens, that exact vendor, model and effort, the
    current catalogue version, and every fixture passed. Every other case is the catalogue's
    documented-policy outcome with the reason named: a lens the catalogue marks unscorable, an
    empty ledger, a partial fixture pass, an entry recorded against an older catalogue version,
    an unreadable ledger, and an absent checkout. The ledger can only ever downgrade a scoring
    executor; it never promotes one.
    """
    checkout = sdlc_root(checkout)
    if checkout is None:
        return Qualification(
            DOCUMENTED_POLICY,
            f"no software-development-lifecycle checkout ({SDLC_PATH_ENV} is unset or does not "
            "name a directory, and the default checkout is absent)",
            lens,
        )

    catalogue, version = lens_catalogue(checkout)
    if not catalogue:
        return Qualification(
            DOCUMENTED_POLICY,
            "the lens catalogue in the software-development-lifecycle checkout is absent or "
            "unreadable",
            lens,
        )
    if lens not in catalogue:
        raise StaffingError(f"unknown lens {lens!r}; expected one of {sorted(catalogue)}")
    entry_for_lens = catalogue[lens]
    if not isinstance(entry_for_lens, dict) or not entry_for_lens.get("scorable"):
        return Qualification(
            DOCUMENTED_POLICY,
            f"the catalogue marks {lens!r} unscorable, so there are no fixtures to qualify "
            "against and the ledger is not consulted",
            lens,
        )

    entries = verification_ledger(checkout)
    if not entries:
        return Qualification(
            DOCUMENTED_POLICY,
            "the executor-verification ledger is empty, so no executor has been qualified "
            "against this catalogue and the lens establishes no threshold",
            lens,
        )

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not (
            entry.get("lens") == lens
            and entry.get("vendor") == vendor
            and entry.get("model") == model
            and entry.get("effort") == effort
        ):
            continue

        # Everything below must be present and well formed before the entry can grant. Comparing
        # two absent values with != is how a partial entry used to qualify: None != None is false,
        # so an entry with no evidence fields at all satisfied both guards. Each field is now
        # checked for presence and type first, and the failure direction is closed.
        recorded_version = entry.get("catalogue_version")
        if version is None or recorded_version is None:
            return Qualification(
                DOCUMENTED_POLICY,
                "the entry or the catalogue does not state a catalogue version, so the "
                "qualification cannot be bound to the fixtures it ran against",
                lens,
            )
        if recorded_version != version:
            return Qualification(
                DOCUMENTED_POLICY,
                f"the entry was recorded against catalogue version {recorded_version!r}, not "
                f"the current {version!r}; qualification is re-run, never carried forward",
                lens,
            )

        passed, total = entry.get("fixtures_passed"), entry.get("fixtures_total")
        if not isinstance(passed, int) or not isinstance(total, int) or isinstance(passed, bool):
            return Qualification(
                DOCUMENTED_POLICY,
                "the entry does not state integer fixture counts, so there is no evidence a "
                "qualification run happened",
                lens,
            )
        if total <= 0:
            return Qualification(
                DOCUMENTED_POLICY,
                "the entry records no fixtures, and zero of zero is not a passing run",
                lens,
            )
        if passed != total:
            return Qualification(
                DOCUMENTED_POLICY,
                f"partial qualification ({passed} of {total} fixtures) is recorded and "
                "refused, not rounded up",
                lens,
            )
        return Qualification(
            QUALIFIED,
            f"{vendor} {model}/{effort} passed {passed} of {total} fixtures at catalogue "
            f"version {version}",
            lens,
        )

    return Qualification(
        DOCUMENTED_POLICY,
        f"no ledger entry qualifies {vendor} {model}/{effort} for {lens!r}",
        lens,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="staffing.py",
        description="Resolve a work shape, a role, or a role and review lens to a tier.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="resolve one staffing question")
    resolve.add_argument("--shape", help="a work shape from the staffing registry")
    resolve.add_argument("--role", help="a role from the staffing registry")
    resolve.add_argument("--lens", help="a review lens; only meaningful for a reviewing role")
    resolve.add_argument(
        "--suggest",
        metavar="MODEL/EFFORT",
        help="an advisory tier suggestion, recorded beside the answer and never able to change it",
    )
    resolve.add_argument(
        "--json", action="store_true", help="print the whole decision record instead of the tier"
    )

    explain = sub.add_parser("explain", help="list a role's candidate executors in rating order")
    explain.add_argument("--role", required=True, help="a role from the staffing registry")
    explain.add_argument(
        "--lens",
        help="a review lens; attaches its qualification status to a reviewing role's listing",
    )
    explain.add_argument("--json", action="store_true", help="print the candidates as JSON")

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
    if args.command == "resolve":
        return _cli_resolve(args)
    return _cli_explain(args)


def _cli_resolve(args: argparse.Namespace) -> int:
    if bool(args.shape) == bool(args.role):
        raise StaffingError("pass exactly one of --shape or --role")
    suggestion = _parse_suggestion(args.suggest)
    if args.shape:
        if args.lens:
            raise StaffingError("a lens applies to a reviewing role, not a work shape")
        decision = resolve_shape(args.shape, suggestion=suggestion)
    else:
        decision = resolve_role(args.role, lens=args.lens, suggestion=suggestion)
    if args.json:
        print(json.dumps(decision.as_dict(), indent=2, sort_keys=True))
    else:
        print(_short_form(decision))
    return 0


def _cli_explain(args: argparse.Namespace) -> int:
    rows = candidates_for(args.role)
    decision = resolve_role(args.role, lens=args.lens)
    if args.json:
        listed = replace(decision, candidates=rows)
        print(json.dumps(listed.as_dict(), indent=2, sort_keys=True))
        return 0

    print(f"{args.role}: {_short_form(decision)} (work shape {decision.work_shape})")
    if not rows:
        capability = _role_row(args.role)["capability"]
        print(
            f"  no executor rates {capability!r}; the role runs on the resolved tier "
            "with no rated alternative"
        )
        return 0
    for row in rows:
        print(
            f"  {row['rating']:<9} {row['executor']:<28} "
            f"trust {row['trust_tier']:<9} cost/speed rank {row['cost_speed_rank']} "
            f"validated {row['last_validated']}"
        )
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
