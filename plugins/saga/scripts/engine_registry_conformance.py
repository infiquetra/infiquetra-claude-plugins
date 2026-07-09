#!/usr/bin/env python3
"""Offline registry-to-dispatch conformance gate for Saga engine providers."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_signatures  # noqa: E402
import engine_dispatch  # noqa: E402
from engine_registry import EngineEntry, Registry, RegistryError  # noqa: E402
from engine_resolver import Resolution  # noqa: E402

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"


@dataclass(frozen=True)
class ConformanceIssue:
    """One row-scoped registry-to-dispatch failure."""

    engine_key: str
    check: str
    reason: str


@dataclass(frozen=True)
class ConformanceReport:
    """Complete offline conformance result for one registry."""

    checked_rows: int
    issues: tuple[ConformanceIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def check_registry(
    registry: Registry,
    *,
    emitter_policies: dict[str, dict[str, Any]] | None = None,
) -> ConformanceReport:
    """Check candidate, exact-key, emitter, and invocation reachability without dispatch."""
    policies = bridge_signatures.load_registry() if emitter_policies is None else emitter_policies
    issues: list[ConformanceIssue] = []

    for entry in registry.engines:
        _check_exact_key(registry, entry, issues)
        _check_capability_reachability(registry, entry, issues)
        _check_emitter(entry, policies, issues)
        _check_invocation(entry, issues)

    return ConformanceReport(checked_rows=len(registry.engines), issues=tuple(issues))


def _check_exact_key(
    registry: Registry,
    entry: EngineEntry,
    issues: list[ConformanceIssue],
) -> None:
    try:
        resolved = registry.by_key(entry.key)
    except RegistryError as exc:
        issues.append(ConformanceIssue(entry.key, "exact-key", str(exc)))
        return
    if resolved is not entry:
        issues.append(
            ConformanceIssue(entry.key, "exact-key", "lookup did not return the registered row")
        )


def _check_capability_reachability(
    registry: Registry,
    entry: EngineEntry,
    issues: list[ConformanceIssue],
) -> None:
    for capability in entry.capability_profile:
        try:
            candidate_keys = {
                candidate.entry.key for candidate in registry.ranked_candidates(capability)
            }
        except RegistryError as exc:
            issues.append(ConformanceIssue(entry.key, f"capability:{capability}", str(exc)))
            continue
        if entry.key not in candidate_keys:
            issues.append(
                ConformanceIssue(
                    entry.key,
                    f"capability:{capability}",
                    "row advertises the capability but is absent from ranked candidates",
                )
            )


def _check_emitter(
    entry: EngineEntry,
    policies: dict[str, dict[str, Any]],
    issues: list[ConformanceIssue],
) -> None:
    if entry.receipt_emitter not in policies:
        issues.append(
            ConformanceIssue(
                entry.key,
                "receipt-emitter",
                f"unknown bridge signature emitter {entry.receipt_emitter!r}",
            )
        )


def _check_invocation(entry: EngineEntry, issues: list[ConformanceIssue]) -> None:
    probe_payload = f"conformance probe for {entry.key}"
    resolution = Resolution(
        engine_id=entry.engine_id,
        variant=entry.variant,
        effort=_entry_effort(entry),
        recipe=str(entry.invocation["recipe"]),
        protocol=list(entry.prompting_protocol),
        payload=probe_payload,
        write_capable=bool(entry.invocation["write_capable"]),
        fallback=None,
        halt=None,
        invocation=dict(entry.invocation),
    )
    try:
        invocation = engine_dispatch._build_invocation(
            resolution,
            model=entry.invocation.get("model"),
        )
    except (engine_dispatch.DispatchError, RegistryError, TypeError, ValueError) as exc:
        issues.append(ConformanceIssue(entry.key, "dispatch-invocation", str(exc)))
        return
    if invocation.get("task") != probe_payload:
        issues.append(
            ConformanceIssue(
                entry.key,
                "dispatch-invocation",
                "invocation did not preserve the synthetic task payload",
            )
        )


def _entry_effort(entry: EngineEntry) -> str:
    effort = entry.invocation.get("effort")
    if isinstance(effort, str) and effort:
        return effort
    return str(entry.variant).rsplit("-", 1)[-1]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--bridge-signatures", default=str(bridge_signatures.DEFAULT_REGISTRY_PATH))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        registry = Registry.load(args.registry)
        policies = bridge_signatures.load_registry(args.bridge_signatures)
        report = check_registry(registry, emitter_policies=policies)
    except (OSError, RegistryError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"engine registry conformance failed: {exc}", file=sys.stderr)
        return 1

    if not report.ok:
        for issue in report.issues:
            print(
                f"{issue.engine_key} [{issue.check}]: {issue.reason}",
                file=sys.stderr,
            )
        return 1

    print(f"engine registry conformance ok: {report.checked_rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
