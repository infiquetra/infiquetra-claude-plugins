#!/usr/bin/env python3
"""Load and validate the Saga external-engine capability registry."""

from __future__ import annotations

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
)

RATINGS = ("WEAK", "MODERATE", "STRONG")
_RATING_SCORE = {rating: index for index, rating in enumerate(RATINGS, start=1)}


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
    default_for_engine: bool
    invocation: dict[str, Any]
    context_window: int
    cost_speed_rank: int
    model_identity: str
    last_validated: date
    capability_profile: dict[str, dict[str, Any]]
    prompting_protocol: list[str]
    sources: list[dict[str, Any]]
    registry_order: int

    @property
    def key(self) -> str:
        return f"{self.engine_id}/{self.variant}"

    @classmethod
    def from_dict(cls, data: dict[str, Any], registry_order: int) -> EngineEntry:
        row = f"engine[{registry_order}]"
        engine_id = _require_string(data, "engine_id", row)
        variant = _require_string(data, "variant", row)
        where = f"engine {engine_id}/{variant}"

        invocation = _require_mapping(
            _require_field(data, "invocation", where),
            f"{where}: invocation",
        )
        _require_string(invocation, "via", f"{where}: invocation")
        _require_string(invocation, "recipe", f"{where}: invocation")
        _require_bool(invocation, "write_capable", f"{where}: invocation")

        if "cost_speed_rank" not in data:
            raise RegistryError(f"{where}: missing cost_speed_rank")
        cost_speed_rank = _require_int(data, "cost_speed_rank", where)

        if "last_validated" not in data:
            raise RegistryError(f"{where}: missing last_validated")

        return cls(
            engine_id=engine_id,
            variant=variant,
            substrate=_require_string(data, "substrate", where),
            default_for_engine=_require_bool(data, "default_for_engine", where),
            invocation=dict(invocation),
            context_window=_require_int(data, "context_window", where),
            cost_speed_rank=cost_speed_rank,
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
        )


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

        raw_engines = _require_list(_require_field(data, "engines", "registry"), "registry engines")
        if not raw_engines:
            raise RegistryError("registry engines: needs at least one engine")
        engines: list[EngineEntry] = []
        for index, raw_entry in enumerate(raw_engines):
            engines.append(
                EngineEntry.from_dict(_require_mapping(raw_entry, f"engine[{index}]"), index)
            )

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
        by_engine: dict[str, list[EngineEntry]] = {}
        for entry in self.engines:
            if entry.key in seen_keys:
                raise RegistryError(f"duplicate engine variant {entry.key!r}")
            seen_keys.add(entry.key)
            by_engine.setdefault(entry.engine_id, []).append(entry)

            for capability in entry.capability_profile:
                if capability not in self.capabilities:
                    raise RegistryError(
                        f"{entry.key}: capability {capability!r} not declared in registry"
                    )

        for engine_id, entries in by_engine.items():
            defaults = [entry for entry in entries if entry.default_for_engine]
            if len(defaults) > 1:
                raise RegistryError(f"engine {engine_id!r}: multiple default_for_engine variants")
            if len(entries) > 1 and not defaults:
                raise RegistryError(
                    f"engine {engine_id!r}: ambiguous default; set one default_for_engine variant"
                )

        for role in self.roles.values():
            for member in role.members:
                if member not in seen_keys:
                    raise RegistryError(
                        f"role {role.name}: member {member!r} references a non-existent variant"
                    )

    def by_capability(self, capability: str) -> EngineEntry:
        if capability not in CAPABILITIES:
            raise RegistryError(f"unknown capability key {capability!r}")
        if capability not in self.capabilities:
            raise RegistryError(f"capability {capability!r} is not declared in this registry")

        candidates = [entry for entry in self.engines if capability in entry.capability_profile]
        if not candidates:
            raise RegistryError(f"no engine variant supports capability {capability!r}")

        return min(
            candidates,
            key=lambda entry: (
                -_RATING_SCORE[str(entry.capability_profile[capability]["rating"])],
                entry.cost_speed_rank,
                entry.registry_order,
            ),
        )

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
