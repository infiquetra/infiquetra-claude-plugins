#!/usr/bin/env python3
"""Operator CLI for Saga external-engine registry visibility and local overlays."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_overlay import (  # noqa: E402
    EngineOverlay,
    EngineOverlayError,
    clear_all,
    clear_deprecated,
    clear_pin,
    deprecate_engine,
    load_overlay,
    pin_engine,
    save_overlay,
)
from engine_registry import (  # noqa: E402
    CapabilityCandidate,
    CapabilityExplanation,
    EngineEntry,
    Registry,
    RegistryError,
)

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"
DEFAULT_RELEASES = Path(__file__).resolve().parent.parent / "references" / "model-releases.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_args = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(["engines", "list"] if raw_args == [] else raw_args)
    try:
        return _run(args)
    except (EngineOverlayError, RegistryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repository root for .saga overlay state")
    parser.add_argument(
        "--registry", default=str(DEFAULT_REGISTRY), help="engine registry YAML path"
    )
    parser.add_argument(
        "--releases", default=str(DEFAULT_RELEASES), help="model releases YAML path"
    )

    families = parser.add_subparsers(dest="family", required=True)
    engines = families.add_parser("engines", help="inspect or mutate local engine overlay state")
    engine_commands = engines.add_subparsers(dest="engine_command", required=True)

    list_parser = engine_commands.add_parser("list", help="list registry rows")
    list_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    pin_parser = engine_commands.add_parser("pin", help="pin a capability to engine_id/variant")
    pin_parser.add_argument("capability")
    pin_parser.add_argument("engine_key")

    deprecate_parser = engine_commands.add_parser("deprecate", help="locally deprecate a row")
    deprecate_parser.add_argument("engine_key")

    clear_parser = engine_commands.add_parser("clear", help="clear local overlay state")
    clear_commands = clear_parser.add_subparsers(dest="clear_command", required=True)
    clear_pin_parser = clear_commands.add_parser("pin", help="clear a capability pin")
    clear_pin_parser.add_argument("capability")
    clear_deprecate_parser = clear_commands.add_parser("deprecate", help="clear a row deprecation")
    clear_deprecate_parser.add_argument("engine_key")
    clear_commands.add_parser("all", help="clear all local overlay state")

    route = families.add_parser("route", help="dry-run route decisions")
    route_commands = route.add_subparsers(dest="route_command", required=True)
    explain = route_commands.add_parser(
        "explain", help="explain capability routing without dispatch"
    )
    explain.add_argument("capability")
    explain.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    return parser


def _run(args: argparse.Namespace) -> int:
    registry = Registry.load(args.registry)
    repo_root = Path(args.repo_root)
    overlay = load_overlay(repo_root)

    if args.family == "engines":
        if args.engine_command == "list":
            releases = _load_release_dates(args.releases)
            rows = [_row_payload(entry, registry, overlay, releases) for entry in registry.engines]
            _emit(rows, args.json, _format_rows(rows))
            return 0
        if args.engine_command == "pin":
            updated = pin_engine(overlay, args.capability, args.engine_key)
            registry.explain_capability(args.capability, overlay=updated)
            save_overlay(repo_root, updated)
            print(f"pinned {args.capability} -> {args.engine_key}")
            return 0
        if args.engine_command == "deprecate":
            registry.by_key(args.engine_key)
            updated = deprecate_engine(overlay, args.engine_key)
            save_overlay(repo_root, updated)
            print(f"deprecated {args.engine_key}")
            return 0
        if args.engine_command == "clear":
            if args.clear_command == "pin":
                updated = clear_pin(overlay, args.capability)
                save_overlay(repo_root, updated)
                print(f"cleared pin for {args.capability}")
                return 0
            if args.clear_command == "deprecate":
                updated = clear_deprecated(overlay, args.engine_key)
                save_overlay(repo_root, updated)
                print(f"cleared deprecation for {args.engine_key}")
                return 0
            if args.clear_command == "all":
                save_overlay(repo_root, clear_all())
                print("cleared engine overlay")
                return 0

    if args.family == "route" and args.route_command == "explain":
        explanation = registry.explain_capability(args.capability, overlay=overlay)
        payload = _explanation_payload(explanation)
        _emit(payload, args.json, _format_explanation(explanation))
        return 0

    raise RegistryError("unhandled engine registry CLI command")


def _row_payload(
    entry: EngineEntry,
    registry: Registry,
    overlay: EngineOverlay,
    releases: Mapping[str, Any],
) -> dict[str, object]:
    pinned = sorted(
        capability
        for capability, engine_key in dict(overlay.pins).items()
        if engine_key == entry.key
    )
    capabilities = {
        capability: str(claim["rating"])
        for capability, claim in sorted(entry.capability_profile.items())
    }
    return {
        "key": entry.key,
        "engine_id": entry.engine_id,
        "variant": entry.variant,
        "trust_tier": entry.trust_tier,
        "capabilities": capabilities,
        "cost_speed_rank": entry.cost_speed_rank,
        "cost_class": entry.cost_class,
        "budget_ceiling_usd": entry.budget_ceiling_usd,
        "latency_class": entry.latency_class,
        "stale": registry.stale(entry, dict(releases)),
        "overlay": {
            "pinned": pinned,
            "deprecated": entry.key in overlay.deprecated,
        },
    }


def _format_rows(rows: list[dict[str, object]]) -> str:
    lines = [
        "key | trust_tier | capabilities | cost_speed_rank | cost_class | budget_ceiling_usd | "
        "latency_class | currency | overlay",
    ]
    for row in rows:
        capabilities = row["capabilities"]
        assert isinstance(capabilities, dict)
        capability_text = ",".join(f"{key}:{value}" for key, value in capabilities.items())
        overlay = row["overlay"]
        assert isinstance(overlay, dict)
        overlay_parts: list[str] = []
        pinned = overlay["pinned"]
        if pinned:
            assert isinstance(pinned, list)
            overlay_parts.append("pinned:" + ",".join(str(item) for item in pinned))
        if overlay["deprecated"]:
            overlay_parts.append("deprecated")
        overlay_text = ",".join(overlay_parts) if overlay_parts else "active"
        currency = "stale" if row["stale"] else "current"
        budget = row["budget_ceiling_usd"]
        budget_text = f"{budget:.2f}" if isinstance(budget, int | float) else "none"
        lines.append(
            f"{row['key']} | {row['trust_tier']} | {capability_text} | "
            f"{row['cost_speed_rank']} | "
            f"{row['cost_class']} | {budget_text} | {row['latency_class']} | "
            f"{currency} | {overlay_text}"
        )
    return "\n".join(lines)


def _explanation_payload(explanation: CapabilityExplanation) -> dict[str, object]:
    return {
        "capability": explanation.capability,
        "selected": _candidate_payload(explanation.selected),
        "ranking": explanation.ranking,
        "pinned_key": explanation.pinned_key,
        "deprecated_keys": list(explanation.deprecated_keys),
        "candidates": [_candidate_payload(candidate) for candidate in explanation.candidates],
    }


def _candidate_payload(candidate: CapabilityCandidate) -> dict[str, object]:
    data = asdict(candidate)
    data["entry"] = {
        "key": candidate.entry.key,
        "engine_id": candidate.entry.engine_id,
        "variant": candidate.entry.variant,
    }
    return data


def _format_explanation(explanation: CapabilityExplanation) -> str:
    lines = [
        f"capability: {explanation.capability}",
        f"selected: {explanation.selected.entry.key}",
        f"ranking: {explanation.ranking}",
        f"pin: {explanation.pinned_key or 'none'}",
        "deprecated: "
        + (",".join(explanation.deprecated_keys) if explanation.deprecated_keys else "none"),
        "candidates:",
    ]
    for candidate in explanation.candidates:
        marker = "*" if candidate.entry.key == explanation.selected.entry.key else "-"
        lines.append(
            f"{marker} {candidate.entry.key} rating={candidate.rating} "
            f"cost_speed_rank={candidate.cost_speed_rank} "
            f"registry_order={candidate.registry_order} reason={candidate.reason}"
        )
    return "\n".join(lines)


def _emit(payload: object, as_json: bool, text: str) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(text)


def _load_release_dates(path: str | Path) -> dict[str, Any]:
    release_path = Path(path)
    if not release_path.exists():
        return {}
    data = yaml.safe_load(release_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    releases = data.get("model_releases", data)
    if not isinstance(releases, dict):
        return {}
    return dict(releases)


if __name__ == "__main__":
    raise SystemExit(main())
