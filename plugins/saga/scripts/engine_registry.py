#!/usr/bin/env python3
"""Load and validate the Saga external-engine capability registry."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

CAPABILITIES = (
    "code-generation",
    "adversarial-review",
    "second-opinion",
    "debug",
    "refactor",
    "scaffold",
    "long-form-writing",
    "bulk-classification",
    "structured-extraction",
    "embedding",
)

RATINGS = ("WEAK", "MODERATE", "STRONG")
_RATING_SCORE = {rating: index for index, rating in enumerate(RATINGS, start=1)}

TRANSPORTS = ("cli", "http")
AUTH_MODES = ("files", "env", "bearer", "secret-ref")
LATENCY_CLASSES = ("fast", "standard", "slow", "batch")
COST_CLASSES = ("metered", "free")
EGRESS_POLICIES = ("local-only", "networked")
TRUST_TIERS = ("probation", "advisory")


class RegistryError(ValueError):
    """A registry row or role violates the external-engine schema."""


def _require_field(data: dict[str, Any], field: str, where: str) -> Any:
    if field not in data:
        raise RegistryError(f"{where}: missing required field {field!r}")
    return data[field]


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"{where}: expected a mapping")
    return value


def _require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise RegistryError(f"{where}: expected a list")
    return value


def _require_string(data: dict[str, Any], field: str, where: str) -> str:
    value = _require_field(data, field, where)
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{where}: {field!r} must be a non-empty string")
    return value


def _require_bool(data: dict[str, Any], field: str, where: str) -> bool:
    value = _require_field(data, field, where)
    if not isinstance(value, bool):
        raise RegistryError(f"{where}: {field!r} must be a boolean")
    return value


def _require_int(data: dict[str, Any], field: str, where: str) -> int:
    value = _require_field(data, field, where)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryError(f"{where}: {field} {value!r} is not an integer")
    return int(value)


def _require_number(data: dict[str, Any], field: str, where: str) -> float:
    value = _require_field(data, field, where)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RegistryError(f"{where}: {field} {value!r} is not a number")
    if value < 0:
        raise RegistryError(f"{where}: {field} must be non-negative")
    return float(value)


def _parse_date(value: Any, where: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise RegistryError(f"{where}: {value!r} is not an ISO date") from exc
    raise RegistryError(f"{where}: {value!r} is not an ISO date")


def _parse_capabilities(data: dict[str, Any]) -> tuple[str, ...]:
    raw = _require_list(_require_field(data, "capabilities", "registry"), "registry capabilities")
    capabilities: list[str] = []
    seen: set[str] = set()
    for capability in raw:
        if not isinstance(capability, str):
            raise RegistryError(f"registry capabilities: capability {capability!r} is not a string")
        if capability not in CAPABILITIES:
            raise RegistryError(f"registry capabilities: unknown capability key {capability!r}")
        if capability in seen:
            raise RegistryError(f"registry capabilities: duplicate capability {capability!r}")
        seen.add(capability)
        capabilities.append(capability)

    missing = [capability for capability in CAPABILITIES if capability not in seen]
    if missing:
        raise RegistryError(
            "registry capabilities: missing closed-vocabulary values "
            f"{', '.join(repr(capability) for capability in missing)}"
        )
    return tuple(capabilities)


def _parse_capability_profile(
    data: dict[str, Any],
    where: str,
) -> dict[str, dict[str, Any]]:
    if not data:
        raise RegistryError(f"{where}: capability_profile needs at least one capability")

    profile: dict[str, dict[str, Any]] = {}
    for capability, raw_claim in data.items():
        if not isinstance(capability, str):
            raise RegistryError(f"{where}: capability key {capability!r} is not a string")
        if capability not in CAPABILITIES:
            raise RegistryError(f"{where}: unknown capability key {capability!r}")

        claim = _require_mapping(
            raw_claim,
            f"{where}: capability_profile[{capability}]",
        )
        rating = _require_string(claim, "rating", f"{where}: capability_profile[{capability}]")
        if rating not in RATINGS:
            raise RegistryError(
                f"{where}: capability_profile[{capability}] rating {rating!r} not in {RATINGS}"
            )

        profile[capability] = dict(claim)
        profile[capability]["rating"] = rating

    return profile


def _parse_cost_per_token(data: dict[str, Any], where: str) -> dict[str, float]:
    raw = _require_mapping(
        _require_field(data, "cost_per_token", where),
        f"{where}: cost_per_token",
    )
    return {
        "input_usd": _require_number(raw, "input_usd", f"{where}: cost_per_token"),
        "output_usd": _require_number(raw, "output_usd", f"{where}: cost_per_token"),
    }


def _parse_latency_class(data: dict[str, Any], where: str) -> str:
    value = _require_string(data, "latency_class", where)
    if value not in LATENCY_CLASSES:
        raise RegistryError(f"{where}: latency_class {value!r} not in {LATENCY_CLASSES}")
    return value


def _parse_cost_class(data: dict[str, Any], where: str) -> str:
    value = _require_string(data, "cost_class", where)
    if value not in COST_CLASSES:
        raise RegistryError(f"{where}: cost_class {value!r} not in {COST_CLASSES}")
    return value


def _parse_egress_policy(data: dict[str, Any], where: str) -> str:
    value = _require_string(data, "egress_policy", where)
    if value not in EGRESS_POLICIES:
        raise RegistryError(f"{where}: egress_policy {value!r} not in {EGRESS_POLICIES}")
    return value


def _parse_trust_tier(data: dict[str, Any], where: str) -> str:
    value = _require_string(data, "trust_tier", where)
    if value not in TRUST_TIERS:
        raise RegistryError(f"{where}: trust_tier {value!r} not in {TRUST_TIERS}")
    return value


def _parse_budget_ceiling_usd(data: dict[str, Any], cost_class: str, where: str) -> float | None:
    if cost_class == "metered":
        return _require_number(data, "budget_ceiling_usd", where)

    if "budget_ceiling_usd" in data:
        raise RegistryError(f"{where}: free cost_class must not declare budget_ceiling_usd")
    return None


def _parse_model_families(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = data.get("model_families", {})
    families = _require_mapping(raw, "registry model_families")
    parsed: dict[str, dict[str, Any]] = {}
    for model_identity, raw_family in families.items():
        if not isinstance(model_identity, str) or not model_identity:
            raise RegistryError(
                f"registry model_families: model identity {model_identity!r} must be a string"
            )
        family = _require_mapping(raw_family, f"model family {model_identity}")
        profile = _require_mapping(
            _require_field(family, "capability_profile", f"model family {model_identity}"),
            f"model family {model_identity}: capability_profile",
        )
        _parse_capability_profile(profile, f"model family {model_identity}")
        parsed[model_identity] = {"capability_profile": deepcopy(profile)}
    return parsed


def _materialize_family_defaults(
    data: dict[str, Any],
    model_families: dict[str, dict[str, Any]],
    where: str,
) -> dict[str, Any]:
    model_identity = _require_string(data, "model_identity", where)
    family = model_families.get(model_identity)
    if family is None:
        return dict(data)

    materialized = dict(data)
    merged_profile = deepcopy(family["capability_profile"])
    row_profile = data.get("capability_profile", {})
    row_profile = _require_mapping(row_profile, f"{where}: capability_profile")
    for capability, claim in row_profile.items():
        merged_profile[capability] = claim
    materialized["capability_profile"] = merged_profile
    return materialized


def _parse_prompting_protocol(data: dict[str, Any], where: str) -> list[str]:
    raw = _require_list(
        _require_field(data, "prompting_protocol", where),
        f"{where}: prompting_protocol",
    )
    protocol: list[str] = []
    for index, line in enumerate(raw):
        if not isinstance(line, str):
            raise RegistryError(f"{where}: prompting_protocol[{index}] must be a string")
        protocol.append(line)
    return protocol


def _validate_invocation_transport(
    invocation: dict[str, Any],
    transport: str,
    where: str,
) -> None:
    """KTD2: http-conditional required invocation fields.

    ``transport: http`` rows must carry ``base_url``, ``model``, and explicit ``effort``.
    Auth validation is shared across transports in ``_parse_auth`` so CLI rows can use the
    same row-authored credential contract.
    """
    if transport != "http":
        return

    _require_string(invocation, "base_url", f"{where}: invocation")
    _require_string(invocation, "model", f"{where}: invocation")
    _require_field(invocation, "effort", f"{where}: invocation")

    if "auth" not in invocation:
        raise RegistryError(f"{where}: invocation missing required field 'auth'")


def _parse_auth(invocation: dict[str, Any], transport: str, where: str) -> dict[str, Any]:
    """Normalize row-authored credential availability metadata."""
    if "auth" not in invocation:
        if transport == "http":
            raise RegistryError(f"{where}: invocation missing required field 'auth'")
        return {}

    if transport == "cli":
        _require_string(invocation, "cli", f"{where}: invocation")

    auth = dict(
        _require_mapping(
            _require_field(invocation, "auth", f"{where}: invocation"),
            f"{where}: invocation.auth",
        )
    )
    mode = _require_string(auth, "mode", f"{where}: invocation.auth")
    if mode not in AUTH_MODES:
        raise RegistryError(
            f"{where}: invocation.auth mode {mode!r} not in closed vocabulary {AUTH_MODES}"
        )
    if transport == "http" and mode != "bearer":
        raise RegistryError(f"{where}: http transport currently requires auth.mode 'bearer'")

    if mode == "files":
        paths = _require_list(
            _require_field(auth, "paths", f"{where}: invocation.auth"),
            f"{where}: invocation.auth.paths",
        )
        if not paths:
            raise RegistryError(f"{where}: invocation.auth.paths must not be empty")
        for index, path in enumerate(paths):
            if not isinstance(path, str) or not path:
                raise RegistryError(
                    f"{where}: invocation.auth.paths[{index}] must be a non-empty string"
                )
        auth["paths"] = list(paths)
    elif mode in {"env", "bearer"}:
        _require_string(auth, "key_env", f"{where}: invocation.auth")
    elif mode == "secret-ref":
        _require_string(auth, "ref", f"{where}: invocation.auth")

    return auth


def _parse_sources(data: dict[str, Any], where: str) -> list[dict[str, Any]]:
    if "sources" not in data:
        raise RegistryError(f"{where}: missing per-row sources")
    raw = _require_list(data["sources"], f"{where}: sources")
    if not raw:
        raise RegistryError(f"{where}: missing per-row sources")

    sources: list[dict[str, Any]] = []
    for index, source in enumerate(raw):
        if not isinstance(source, dict):
            raise RegistryError(f"{where}: sources[{index}] must be a mapping")
        sources.append(dict(source))
    return sources


@dataclass(frozen=True)
class EngineEntry:
    """One engine variant row from ``engine-registry.yaml``."""

    engine_id: str
    variant: str
    substrate: str
    egress_policy: str
    trust_tier: str
    default_for_engine: bool
    invocation: dict[str, Any]
    context_window: int
    cost_speed_rank: int
    cost_per_token: dict[str, float]
    cost_class: str
    budget_ceiling_usd: float | None
    latency_class: str
    model_identity: str
    last_validated: date
    capability_profile: dict[str, dict[str, Any]]
    prompting_protocol: list[str]
    sources: list[dict[str, Any]]
    registry_order: int
    receipt_emitter: str
    auth: dict[str, Any]
    transport: str = "cli"

    @property
    def key(self) -> str:
        return f"{self.engine_id}/{self.variant}"

    @classmethod
    def from_dict(cls, data: dict[str, Any], registry_order: int) -> EngineEntry:
        row = f"engine[{registry_order}]"
        engine_id = _require_string(data, "engine_id", row)
        variant = _require_string(data, "variant", row)
        where = f"engine {engine_id}/{variant}"

        transport = data.get("transport", "cli")
        if not isinstance(transport, str) or transport not in TRANSPORTS:
            raise RegistryError(
                f"{where}: transport {transport!r} not in closed vocabulary {TRANSPORTS}"
            )

        invocation = _require_mapping(
            _require_field(data, "invocation", where),
            f"{where}: invocation",
        )
        _require_string(invocation, "via", f"{where}: invocation")
        _require_string(invocation, "recipe", f"{where}: invocation")
        _require_bool(invocation, "write_capable", f"{where}: invocation")
        _validate_invocation_transport(invocation, transport, where)
        auth = _parse_auth(invocation, transport, where)

        if "cost_speed_rank" not in data:
            raise RegistryError(f"{where}: missing cost_speed_rank")
        cost_speed_rank = _require_int(data, "cost_speed_rank", where)
        cost_class = _parse_cost_class(data, where)
        budget_ceiling_usd = _parse_budget_ceiling_usd(data, cost_class, where)

        if "last_validated" not in data:
            raise RegistryError(f"{where}: missing last_validated")

        receipt_emitter = _require_string(data, "receipt_emitter", where)

        return cls(
            engine_id=engine_id,
            variant=variant,
            substrate=_require_string(data, "substrate", where),
            egress_policy=_parse_egress_policy(data, where),
            trust_tier=_parse_trust_tier(data, where),
            default_for_engine=_require_bool(data, "default_for_engine", where),
            invocation=dict(invocation),
            context_window=_require_int(data, "context_window", where),
            cost_speed_rank=cost_speed_rank,
            cost_per_token=_parse_cost_per_token(data, where),
            cost_class=cost_class,
            budget_ceiling_usd=budget_ceiling_usd,
            latency_class=_parse_latency_class(data, where),
            model_identity=_require_string(data, "model_identity", where),
            last_validated=_parse_date(data["last_validated"], f"{where}: last_validated"),
            capability_profile=_parse_capability_profile(
                _require_mapping(
                    _require_field(data, "capability_profile", where),
                    f"{where}: capability_profile",
                ),
                where,
            ),
            prompting_protocol=_parse_prompting_protocol(data, where),
            sources=_parse_sources(data, where),
            registry_order=registry_order,
            receipt_emitter=receipt_emitter,
            auth=auth,
            transport=transport,
        )


@dataclass(frozen=True)
class CapabilityCandidate:
    """One ranked candidate for a capability route explanation."""

    entry: EngineEntry
    capability: str
    rating: str
    rating_score: int
    cost_speed_rank: int
    registry_order: int
    reason: str
    pinned: bool = False


@dataclass(frozen=True)
class CapabilityExplanation:
    """Deterministic route dry-run result for one capability."""

    capability: str
    selected: CapabilityCandidate
    candidates: tuple[CapabilityCandidate, ...]
    pinned_key: str | None
    deprecated_keys: tuple[str, ...]
    ranking: str = "rating desc, cost_speed_rank asc, registry_order asc"


@dataclass(frozen=True)
class Role:
    """A composing role whose members are engine/variant registry keys."""

    name: str
    members: list[str]
    verdict: str
    verifier: str

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> Role:
        where = f"role {name}"
        raw_members = _require_list(_require_field(data, "members", where), f"{where}: members")
        if not raw_members:
            raise RegistryError(f"{where}: members must not be empty")

        members: list[str] = []
        for index, member in enumerate(raw_members):
            if not isinstance(member, str):
                raise RegistryError(f"{where}: member[{index}] must be an engine/variant string")
            engine, sep, variant = member.partition("/")
            if not sep or not engine or not variant:
                raise RegistryError(f"{where}: member[{index}] must be an engine/variant string")
            members.append(member)

        return cls(
            name=name,
            members=members,
            verdict=_require_string(data, "verdict", where),
            verifier=_require_string(data, "verifier", where),
        )


@dataclass(frozen=True)
class Registry:
    """Validated external-engine registry with deterministic lookup helpers."""

    capabilities: tuple[str, ...]
    engines: list[EngineEntry]
    roles: dict[str, Role]

    @classmethod
    def load(cls, path: str | Path) -> Registry:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RegistryError(f"registry must be a mapping: {path}")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Registry:
        capabilities = _parse_capabilities(data)
        model_families = _parse_model_families(data)

        raw_engines = _require_list(_require_field(data, "engines", "registry"), "registry engines")
        if not raw_engines:
            raise RegistryError("registry engines: needs at least one engine")
        engines: list[EngineEntry] = []
        for index, raw_entry in enumerate(raw_engines):
            entry_data = _require_mapping(raw_entry, f"engine[{index}]")
            materialized = _materialize_family_defaults(
                entry_data,
                model_families,
                f"engine {entry_data.get('engine_id', '<unknown>')}/{entry_data.get('variant', '<unknown>')}",
            )
            engines.append(EngineEntry.from_dict(materialized, index))

        raw_roles = _require_mapping(_require_field(data, "roles", "registry"), "registry roles")
        roles: dict[str, Role] = {}
        for name, raw_role in raw_roles.items():
            if not isinstance(name, str) or not name:
                raise RegistryError(
                    f"registry roles: role name {name!r} must be a non-empty string"
                )
            roles[name] = Role.from_dict(name, _require_mapping(raw_role, f"role {name}"))

        registry = cls(capabilities=capabilities, engines=engines, roles=roles)
        registry.validate()
        return registry

    def validate(self) -> None:
        seen_keys: set[str] = set()
        entries_by_key: dict[str, EngineEntry] = {}
        by_engine: dict[str, list[EngineEntry]] = {}
        for entry in self.engines:
            if entry.key in seen_keys:
                raise RegistryError(f"duplicate engine variant {entry.key!r}")
            seen_keys.add(entry.key)
            entries_by_key[entry.key] = entry
            by_engine.setdefault(entry.engine_id, []).append(entry)

            for capability in entry.capability_profile:
                if capability not in self.capabilities:
                    raise RegistryError(
                        f"{entry.key}: capability {capability!r} not declared in registry"
                    )
            if entry.cost_class == "free" and (
                entry.cost_per_token["input_usd"] != 0.0
                or entry.cost_per_token["output_usd"] != 0.0
            ):
                raise RegistryError(f"{entry.key}: free cost_class requires zero cost_per_token")

        for engine_id, entries in by_engine.items():
            defaults = [entry for entry in entries if entry.default_for_engine]
            if len(defaults) > 1:
                raise RegistryError(f"engine {engine_id!r}: multiple default_for_engine variants")
            if len(entries) > 1 and not defaults:
                raise RegistryError(
                    f"engine {engine_id!r}: ambiguous default; set one default_for_engine variant"
                )
            cost_classes = {entry.cost_class for entry in entries}
            if len(cost_classes) > 1:
                raise RegistryError(f"engine {engine_id!r}: mixed cost_class values")
            if cost_classes == {"metered"}:
                ceilings = {entry.budget_ceiling_usd for entry in entries}
                if len(ceilings) > 1:
                    raise RegistryError(
                        f"engine {engine_id!r}: inconsistent budget_ceiling_usd values"
                    )

        for role in self.roles.values():
            for member in role.members:
                if member not in seen_keys:
                    raise RegistryError(
                        f"role {role.name}: member {member!r} references a non-existent variant"
                    )
                if entries_by_key[member].trust_tier != "advisory":
                    raise RegistryError(
                        f"role {role.name}: member {member!r} has trust_tier "
                        f"{entries_by_key[member].trust_tier!r}; composing roles require 'advisory'"
                    )

    def by_capability(self, capability: str) -> EngineEntry:
        return self.ranked_candidates(capability)[0].entry

    def by_key(self, engine_key: str) -> EngineEntry:
        for entry in self.engines:
            if entry.key == engine_key:
                return entry
        raise RegistryError(f"unknown engine variant {engine_key!r}")

    def ranked_candidates(
        self,
        capability: str,
        *,
        overlay: Any | None = None,
    ) -> tuple[CapabilityCandidate, ...]:
        self._validate_capability(capability)
        pin_key = _overlay_pins(overlay).get(capability)
        deprecated_keys = _overlay_deprecated(overlay)

        supported = [entry for entry in self.engines if capability in entry.capability_profile]
        if not supported:
            raise RegistryError(f"no engine variant supports capability {capability!r}")

        candidates = [entry for entry in supported if entry.key not in deprecated_keys]
        if not candidates:
            raise RegistryError(
                f"no non-deprecated engine variant supports capability {capability!r}"
            )

        ranked = sorted(candidates, key=lambda entry: _capability_sort_key(entry, capability))
        if pin_key is not None:
            pinned = self._validate_pin(capability, pin_key, deprecated_keys)
            ranked = [pinned, *[entry for entry in ranked if entry.key != pin_key]]

        return tuple(
            _candidate_from_entry(
                entry,
                capability,
                pinned=pin_key == entry.key and index == 0,
                selected=index == 0,
            )
            for index, entry in enumerate(ranked)
        )

    def explain_capability(
        self,
        capability: str,
        *,
        overlay: Any | None = None,
    ) -> CapabilityExplanation:
        candidates = self.ranked_candidates(capability, overlay=overlay)
        return CapabilityExplanation(
            capability=capability,
            selected=candidates[0],
            candidates=candidates,
            pinned_key=_overlay_pins(overlay).get(capability),
            deprecated_keys=tuple(sorted(_overlay_deprecated(overlay))),
        )

    def _validate_capability(self, capability: str) -> None:
        if capability not in CAPABILITIES:
            raise RegistryError(f"unknown capability key {capability!r}")
        if capability not in self.capabilities:
            raise RegistryError(f"capability {capability!r} is not declared in this registry")

    def _validate_pin(
        self,
        capability: str,
        pin_key: str,
        deprecated_keys: set[str],
    ) -> EngineEntry:
        pinned = self.by_key(pin_key)
        if pin_key in deprecated_keys:
            raise RegistryError(
                f"overlay pin for capability {capability!r} points to deprecated row {pin_key!r}"
            )
        if capability not in pinned.capability_profile:
            raise RegistryError(
                f"overlay pin for capability {capability!r} points to {pin_key!r}, "
                "which does not declare that capability"
            )
        return pinned

    def by_engine(self, engine_id: str) -> EngineEntry:
        entries = [entry for entry in self.engines if entry.engine_id == engine_id]
        if not entries:
            raise RegistryError(f"unknown engine {engine_id!r}")
        if len(entries) == 1:
            return entries[0]

        defaults = [entry for entry in entries if entry.default_for_engine]
        if len(defaults) == 1:
            return defaults[0]
        if not defaults:
            raise RegistryError(
                f"engine {engine_id!r}: ambiguous default; set one default_for_engine variant"
            )
        raise RegistryError(f"engine {engine_id!r}: multiple default_for_engine variants")

    def by_role(self, role_name: str) -> Role:
        try:
            return self.roles[role_name]
        except KeyError as exc:
            raise RegistryError(f"unknown role {role_name!r}") from exc

    @staticmethod
    def stale(entry: EngineEntry, known_revision_dates: dict[str, Any]) -> bool:
        revision = known_revision_dates.get(entry.model_identity)
        if revision is None:
            return False
        return entry.last_validated < _parse_date(
            revision,
            f"known revision date for {entry.model_identity}",
        )


def _capability_sort_key(entry: EngineEntry, capability: str) -> tuple[int, int, int]:
    rating = str(entry.capability_profile[capability]["rating"])
    return (-_RATING_SCORE[rating], entry.cost_speed_rank, entry.registry_order)


def _candidate_from_entry(
    entry: EngineEntry,
    capability: str,
    *,
    pinned: bool,
    selected: bool,
) -> CapabilityCandidate:
    rating = str(entry.capability_profile[capability]["rating"])
    if pinned:
        reason = "selected by local overlay pin"
    elif selected:
        reason = "selected by rating desc, cost_speed_rank asc, registry_order asc"
    else:
        reason = "ranked fallback by rating desc, cost_speed_rank asc, registry_order asc"
    return CapabilityCandidate(
        entry=entry,
        capability=capability,
        rating=rating,
        rating_score=_RATING_SCORE[rating],
        cost_speed_rank=entry.cost_speed_rank,
        registry_order=entry.registry_order,
        reason=reason,
        pinned=pinned,
    )


def _overlay_pins(overlay: Any | None) -> dict[str, str]:
    if overlay is None:
        return {}
    pins = getattr(overlay, "pins", {})
    if not isinstance(pins, dict):
        return dict(pins)
    return dict(pins)


def _overlay_deprecated(overlay: Any | None) -> set[str]:
    if overlay is None:
        return set()
    return set(getattr(overlay, "deprecated", set()))
