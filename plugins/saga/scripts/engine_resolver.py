#!/usr/bin/env python3
"""Resolve Saga external-engine requests into concrete engine dispatch plans."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_registry import EngineEntry, Registry, RegistryError  # noqa: E402

MODES = ("advisory", "dispatch")
ROLE_KINDS = ("worker", "generator", "advisory-reviewer", "panel")
FALLBACK_ROLE_KINDS = frozenset({"worker", "generator"})
HALT_ROLE_KINDS = frozenset({"advisory-reviewer", "panel"})


@dataclass(frozen=True)
class Resolution:
    engine_id: str
    variant: str
    effort: str
    recipe: str
    protocol: list[str]
    payload: str
    write_capable: bool
    fallback: str | None
    halt: str | None
    # Row-driven invocation data (base_url/model/auth/effort/via) for transport-keyed dispatch.
    # Additive and defaulted (R11): existing callers/tests that construct a Resolution without it
    # stay byte-identical; ``transport: http`` dispatch reads it in ``engine_dispatch._build_invocation``.
    invocation: dict[str, Any] | None = None


@dataclass(frozen=True)
class _CapabilityDecision:
    """Cached outcome of capability -> entry selection (KTD5, R5).

    Captures only the selection/fit-check outcome -- not the built Resolution
    (whose payload embeds caller-supplied context text) -- so cached decisions
    stay correct across calls with differing ``task_context['context']``.
    """

    entry: EngineEntry | None
    no_capability_reason: str | None
    no_fit_reason: str | None


class RunMemo:
    """Explicit, run-scoped memoization object (KTD5).

    Not module state: callers own an instance's lifetime, so memoized results
    are invalidated simply by discarding the instance at a run boundary.
    Threading ``memo=None`` (the default everywhere) is byte-identical to
    today's uncached behavior (R5/R11) -- this is strictly opt-in.

    Keys: ``engine_id`` for legacy preflight probes, ``entry.key`` for row-backed
    probes, and ``(capability, token_estimate)`` for capability resolution decisions.
    """

    def __init__(self) -> None:
        self._preflight: dict[str, dict[str, bool | str]] = {}
        self._capability: dict[tuple[str, int | None], _CapabilityDecision] = {}

    def preflight(self, cache_key: str) -> dict[str, bool | str] | None:
        return self._preflight.get(cache_key)

    def store_preflight(self, cache_key: str, result: dict[str, bool | str]) -> None:
        self._preflight[cache_key] = result

    def capability_decision(
        self, capability: str, token_estimate: int | None
    ) -> _CapabilityDecision | None:
        return self._capability.get((capability, token_estimate))

    def store_capability_decision(
        self,
        capability: str,
        token_estimate: int | None,
        decision: _CapabilityDecision,
    ) -> None:
        self._capability[(capability, token_estimate)] = decision


def preflight(
    engine_id: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    config_exists: Callable[[str], bool] | None = None,
    file_exists: Callable[[str], bool] | None = None,
    env_get: Callable[[str], str | None] | None = None,
    secret_ref_resolves: Callable[[str], bool] | None = None,
    entry: EngineEntry | None = None,
    memo: RunMemo | None = None,
) -> dict[str, bool | str]:
    """Return cheap engine availability without making live API calls.

    Row-backed calls use ``entry.invocation["cli"]`` and ``entry.auth``.
    Legacy callers that omit ``entry`` keep the old CLI + ``config_exists`` seam.

    When ``memo`` is supplied, row-backed calls cache by ``entry.key`` while legacy
    calls cache by ``engine_id``; ``memo=None`` performs the probe on every call.
    """
    cache_key = _preflight_cache_key(engine_id, entry)
    if memo is not None:
        cached = memo.preflight(cache_key)
        if cached is not None:
            return cached

    if entry is not None and entry.transport == "http":
        result = _http_preflight(
            engine_id,
            entry,
            file_exists=file_exists,
            env_get=env_get,
            secret_ref_resolves=secret_ref_resolves,
        )
    else:
        result = _cli_preflight(
            engine_id,
            which=which,
            config_exists=config_exists,
            file_exists=file_exists,
            env_get=env_get,
            secret_ref_resolves=secret_ref_resolves,
            entry=entry,
        )

    if memo is not None:
        memo.store_preflight(cache_key, result)
    return result


def _preflight_cache_key(engine_id: str, entry: EngineEntry | None) -> str:
    return entry.key if entry is not None else engine_id


def _cli_preflight(
    engine_id: str,
    *,
    which: Callable[[str], str | None],
    config_exists: Callable[[str], bool] | None,
    file_exists: Callable[[str], bool] | None,
    env_get: Callable[[str], str | None] | None,
    secret_ref_resolves: Callable[[str], bool] | None,
    entry: EngineEntry | None,
) -> dict[str, bool | str]:
    cli = _cli_name(engine_id, entry)
    if which(cli) is None:
        return {
            "available": False,
            "reason": f"{engine_id} is not installed: {cli!r} not found",
        }

    if entry is not None and entry.auth:
        return _auth_preflight(
            engine_id,
            entry.auth,
            file_exists=file_exists,
            env_get=env_get,
            secret_ref_resolves=secret_ref_resolves,
        )

    return _legacy_config_preflight(engine_id, config_exists=config_exists)


def _cli_name(engine_id: str, entry: EngineEntry | None) -> str:
    if entry is not None:
        cli = entry.invocation.get("cli")
        if isinstance(cli, str) and cli:
            return cli
    return engine_id


def _legacy_config_preflight(
    engine_id: str,
    *,
    config_exists: Callable[[str], bool] | None,
) -> dict[str, bool | str]:
    exists = config_exists or _default_config_exists
    if not exists(engine_id):
        return {
            "available": False,
            "reason": f"{engine_id} is not configured: credential/config file not found",
        }

    return {
        "available": True,
        "reason": f"{engine_id} available: CLI and config present; no live API call made",
    }


def _http_preflight(
    engine_id: str,
    entry: EngineEntry,
    *,
    file_exists: Callable[[str], bool] | None,
    env_get: Callable[[str], str | None] | None,
    secret_ref_resolves: Callable[[str], bool] | None,
) -> dict[str, bool | str]:
    if not entry.auth:
        return {
            "available": True,
            "reason": f"{engine_id} available: http row well-formed; no live API call made",
        }
    return _auth_preflight(
        engine_id,
        entry.auth,
        file_exists=file_exists,
        env_get=env_get,
        secret_ref_resolves=secret_ref_resolves,
    )


def _auth_preflight(
    engine_id: str,
    auth: Mapping[str, Any],
    *,
    file_exists: Callable[[str], bool] | None,
    env_get: Callable[[str], str | None] | None,
    secret_ref_resolves: Callable[[str], bool] | None,
) -> dict[str, bool | str]:
    mode = auth.get("mode")
    if mode == "files":
        paths = [str(path) for path in auth.get("paths", [])]
        exists = file_exists or _default_file_exists
        if any(exists(path) for path in paths):
            return {
                "available": True,
                "reason": (
                    f"{engine_id} available: credential file path present among {paths!r}; "
                    "no live API call made"
                ),
            }
        return {
            "available": False,
            "reason": f"{engine_id} is not configured: credential file paths {paths!r} absent",
        }

    if mode in {"env", "bearer"}:
        key_env = str(auth.get("key_env", ""))
        get_env = env_get or os.environ.get
        if key_env and get_env(key_env):
            return {
                "available": True,
                "reason": (
                    f"{engine_id} available: {mode} key env {key_env!r} present; "
                    "no live API call made"
                ),
            }
        return {
            "available": False,
            "reason": f"{engine_id} is not configured: {mode} key env {key_env!r} absent",
        }

    if mode == "secret-ref":
        ref = str(auth.get("ref", ""))
        if secret_ref_resolves is None:
            return {
                "available": False,
                "reason": f"{engine_id} is not configured: secret ref {ref!r} has no resolver",
            }
        if secret_ref_resolves(ref):
            return {
                "available": True,
                "reason": f"{engine_id} available: secret ref {ref!r} resolvable; no live API call made",
            }
        return {
            "available": False,
            "reason": f"{engine_id} is not configured: secret ref {ref!r} unresolved",
        }

    return {
        "available": False,
        "reason": f"{engine_id} is not configured: auth mode {mode!r} is unsupported",
    }


def resolve(
    request: dict[str, Any],
    *,
    mode: str,
    registry: Registry,
    memo: RunMemo | None = None,
) -> Resolution:
    """Resolve a capability or explicit engine request into the U2 contract."""
    if mode not in MODES:
        raise RegistryError(f"mode {mode!r} not in {MODES}")

    role_kind = _role_kind(request)
    task_context = _task_context(request)
    capability, engine = _request_target(request)

    if capability is not None:
        return _resolve_capability(
            capability,
            role_kind=role_kind,
            task_context=task_context,
            registry=registry,
            memo=memo,
        )

    if engine is None:
        raise RegistryError("request must set exactly one of 'capability' or 'engine'")

    entry = _entry_for_engine_request(engine, registry=registry, task_context=task_context)
    return _resolve_entry(
        entry,
        role_kind=role_kind,
        task_context=task_context,
        registry=registry,
        explicit_engine=True,
        memo=memo,
    )


def resolve_role(
    role_name: str,
    *,
    registry: Registry,
    task_context: dict[str, Any] | None = None,
    memo: RunMemo | None = None,
) -> list[Resolution]:
    """Expand a composing role into one advisory Resolution per member (R16/F3).

    Each member is resolved as an ``advisory-reviewer`` so an unavailable member
    yields a Resolution with ``halt`` set rather than a Claude substitution (R17);
    the caller halts the whole panel when ``panel_halt`` is non-None. The role's
    verdict stays advisory and Claude remains verifier-of-record (R13/R15).
    """
    role = registry.by_role(role_name)
    resolutions: list[Resolution] = []
    for member in role.members:
        request: dict[str, Any] = {"engine": member, "role_kind": "advisory-reviewer"}
        if task_context is not None:
            request["task_context"] = task_context
        resolutions.append(resolve(request, mode="advisory", registry=registry, memo=memo))
    return resolutions


def panel_halt(resolutions: list[Resolution]) -> str | None:
    """Return the first member halt in a resolved panel, or None if all are usable (R17)."""
    for resolution in resolutions:
        if resolution.halt is not None:
            return resolution.halt
    return None


def _default_config_exists(engine_id: str) -> bool:
    return (Path.home() / f".{engine_id}" / "config").exists()


def _default_file_exists(path: str) -> bool:
    return Path(path).expanduser().exists()


def _role_kind(request: Mapping[str, Any]) -> str:
    role_kind = request.get("role_kind")
    if role_kind not in ROLE_KINDS:
        raise RegistryError(f"role_kind {role_kind!r} not in {ROLE_KINDS}")
    return str(role_kind)


def _task_context(request: Mapping[str, Any]) -> dict[str, Any]:
    raw = request.get("task_context", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RegistryError("request task_context must be a mapping when supplied")
    return dict(raw)


def _request_target(request: Mapping[str, Any]) -> tuple[str | None, str | None]:
    has_capability = "capability" in request and request["capability"] is not None
    has_engine = "engine" in request and request["engine"] is not None
    if has_capability == has_engine:
        raise RegistryError("request must set exactly one of 'capability' or 'engine'")

    if has_capability:
        return _require_string_value(request["capability"], "capability"), None
    return None, _require_string_value(request["engine"], "engine")


def _require_string_value(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryError(f"request {field!r} must be a non-empty string")
    return value


def _resolve_capability(
    capability: str,
    *,
    role_kind: str,
    task_context: dict[str, Any],
    registry: Registry,
    memo: RunMemo | None = None,
) -> Resolution:
    token_estimate = _token_estimate(task_context)
    decision = memo.capability_decision(capability, token_estimate) if memo is not None else None
    if decision is None:
        decision = _decide_capability(capability, registry)
        if memo is not None:
            memo.store_capability_decision(capability, token_estimate, decision)

    if decision.no_capability_reason is not None:
        return _no_fit_resolution(
            capability,
            role_kind=role_kind,
            task_context=task_context,
            reason=decision.no_capability_reason,
        )

    if decision.entry is None:
        raise RegistryError(f"capability decision for {capability!r} has no engine entry")
    if decision.no_fit_reason is not None:
        return _no_fit_resolution(
            capability,
            role_kind=role_kind,
            task_context=task_context,
            reason=decision.no_fit_reason,
            entry=decision.entry,
        )

    return _resolve_entry(
        decision.entry,
        role_kind=role_kind,
        task_context=task_context,
        registry=registry,
        explicit_engine=False,
        memo=memo,
    )


def _decide_capability(capability: str, registry: Registry) -> _CapabilityDecision:
    try:
        entry = registry.by_capability(capability)
    except RegistryError as exc:
        if "no engine variant supports capability" not in str(exc):
            raise
        reason = f"no external engine supports capability {capability!r}"
        return _CapabilityDecision(entry=None, no_capability_reason=reason, no_fit_reason=None)

    fit_failure = _capability_fit_failure(entry, capability)
    if fit_failure is not None:
        return _CapabilityDecision(
            entry=entry, no_capability_reason=None, no_fit_reason=fit_failure
        )

    return _CapabilityDecision(entry=entry, no_capability_reason=None, no_fit_reason=None)


def _resolve_entry(
    entry: EngineEntry,
    *,
    role_kind: str,
    task_context: dict[str, Any],
    registry: Registry,
    explicit_engine: bool,
    memo: RunMemo | None = None,
) -> Resolution:
    context_halt = _context_window_halt(entry, task_context)
    if context_halt is not None:
        return _resolution_from_entry(entry, task_context=task_context, halt=context_halt)

    if role_kind == "panel":
        panel_halt = _panel_availability_halt(registry, task_context, memo=memo)
        if panel_halt is not None:
            return _resolution_from_entry(entry, task_context=task_context, halt=panel_halt)

    availability = preflight(entry.engine_id, entry=entry, memo=memo)
    if not bool(availability["available"]):
        reason = f"{entry.key} is unavailable: {availability['reason']}"
        if explicit_engine or role_kind in HALT_ROLE_KINDS:
            return _resolution_from_entry(entry, task_context=task_context, halt=reason)
        return _fallback_resolution(
            "external-engine",
            task_context=task_context,
            reason=reason,
        )

    return _resolution_from_entry(entry, task_context=task_context)


def _no_fit_resolution(
    capability: str,
    *,
    role_kind: str,
    task_context: dict[str, Any],
    reason: str,
    entry: EngineEntry | None = None,
) -> Resolution:
    if role_kind in FALLBACK_ROLE_KINDS:
        return _fallback_resolution(capability, task_context=task_context, reason=reason)

    halt = f"external capability {capability!r} cannot run for {role_kind}: {reason}"
    if entry is not None:
        return _resolution_from_entry(entry, task_context=task_context, halt=halt)
    return Resolution(
        engine_id="unresolved",
        variant="unresolved",
        effort="unresolved",
        recipe="unresolved",
        protocol=[],
        payload=_context_text(task_context),
        write_capable=False,
        fallback=None,
        halt=halt,
    )


def _fallback_resolution(
    capability: str,
    *,
    task_context: dict[str, Any],
    reason: str,
) -> Resolution:
    return Resolution(
        engine_id="claude",
        variant="default",
        effort="default",
        recipe="claude fallback",
        protocol=[],
        payload=_context_text(task_context),
        write_capable=True,
        fallback=f"external capability {capability!r} fell back to Claude: {reason}",
        halt=None,
    )


def _resolution_from_entry(
    entry: EngineEntry,
    *,
    task_context: dict[str, Any],
    fallback: str | None = None,
    halt: str | None = None,
) -> Resolution:
    protocol = list(entry.prompting_protocol)
    payload = _assemble_payload(protocol, _context_text(task_context))
    return Resolution(
        engine_id=entry.engine_id,
        variant=entry.variant,
        effort=_effort(entry),
        recipe=str(entry.invocation["recipe"]),
        protocol=protocol,
        payload=payload,
        write_capable=bool(entry.invocation["write_capable"]),
        fallback=fallback,
        halt=halt,
        invocation=dict(entry.invocation),
    )


def _assemble_payload(protocol: list[str], context: str) -> str:
    protocol_block = "\n".join(protocol)
    payload = protocol_block if not context else f"{protocol_block}\n\n{context}"
    _assert_protocol_preserved(protocol, payload)
    return payload


def _assert_protocol_preserved(protocol: list[str], payload: str) -> None:
    # Explicit checks, not `assert` -- this is the R11 byte-preservation guarantee the
    # dispatch contract advertises to callers; it must still hold under `python -O`,
    # which strips `assert` statements.
    encoded = payload.encode("utf-8")
    offset = 0
    for index, line in enumerate(protocol):
        expected = line.encode("utf-8")
        if encoded[offset : offset + len(expected)] != expected:
            raise RegistryError("assembled payload does not preserve the protocol verbatim")
        offset += len(expected)
        if index < len(protocol) - 1:
            if encoded[offset : offset + 1] != b"\n":
                raise RegistryError("assembled payload does not preserve the protocol verbatim")
            offset += 1


def _context_text(task_context: Mapping[str, Any]) -> str:
    raw = task_context.get("context", "")
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise RegistryError("task_context['context'] must be a string when supplied")
    return raw


def _capability_fit_failure(entry: EngineEntry, capability: str) -> str | None:
    rating = str(entry.capability_profile[capability]["rating"])
    if rating != "WEAK":
        return None
    return f"best external fit is {entry.key} with WEAK rating"


def _context_window_halt(entry: EngineEntry, task_context: Mapping[str, Any]) -> str | None:
    estimate = _token_estimate(task_context)
    if estimate is None or estimate <= entry.context_window:
        return None
    return (
        f"context fitness failed for {entry.key}: token_estimate {estimate} exceeds "
        f"context_window {entry.context_window}; refusing to truncate silently"
    )


def _token_estimate(task_context: Mapping[str, Any]) -> int | None:
    for key in ("token_estimate", "estimated_tokens", "tokens"):
        if key not in task_context:
            continue
        value = task_context[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise RegistryError(f"task_context[{key!r}] must be an integer token estimate")
        return int(value)
    return None


def _entry_for_engine_request(
    engine: str,
    *,
    registry: Registry,
    task_context: Mapping[str, Any],
) -> EngineEntry:
    if "/" in engine:
        return _entry_by_key(registry, engine)

    variant = task_context.get("variant") or task_context.get("engine_variant")
    if variant is not None:
        variant_value = _require_string_value(variant, "task_context.variant")
        key = variant_value if "/" in variant_value else f"{engine}/{variant_value}"
        entry = _entry_by_key(registry, key)
        if entry.engine_id != engine:
            raise RegistryError(f"variant {key!r} does not belong to engine {engine!r}")
        return entry

    effort = task_context.get("effort")
    if effort is not None:
        effort_value = _require_string_value(effort, "task_context.effort")
        matches = [
            entry
            for entry in registry.engines
            if entry.engine_id == engine and _effort(entry) == effort_value
        ]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise RegistryError(f"engine {engine!r} effort {effort_value!r} is ambiguous")
        raise RegistryError(f"engine {engine!r} has no variant for effort {effort_value!r}")

    return registry.by_engine(engine)


def _entry_by_key(registry: Registry, key: str) -> EngineEntry:
    for entry in registry.engines:
        if entry.key == key:
            return entry
    raise RegistryError(f"unknown engine variant {key!r}")


def _panel_availability_halt(
    registry: Registry,
    task_context: Mapping[str, Any],
    *,
    memo: RunMemo | None = None,
) -> str | None:
    role_name = (
        task_context.get("role") or task_context.get("role_name") or task_context.get("panel")
    )
    if role_name is None:
        return None
    role = registry.by_role(_require_string_value(role_name, "task_context.role"))
    for member in role.members:
        entry = _entry_by_key(registry, member)
        availability = preflight(entry.engine_id, entry=entry, memo=memo)
        if not bool(availability["available"]):
            return f"role {role.name!r} member {member!r} is unavailable: {availability['reason']}"
    return None


def _effort(entry: EngineEntry) -> str:
    raw = entry.invocation.get("effort")
    if isinstance(raw, str) and raw:
        return raw
    return entry.variant.rsplit("-", 1)[-1]
