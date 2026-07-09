#!/usr/bin/env python3
"""Validate Saga engine-registry schema and authored model-release currency."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_registry import EngineEntry, Registry, RegistryError  # noqa: E402

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"
DEFAULT_RELEASES = Path(__file__).resolve().parent.parent / "references" / "model-releases.yaml"


class EngineRegistryLintError(ValueError):
    """The registry is schema-valid but stale against known model-release dates."""


def load_known_revision_dates(path: Path | str = DEFAULT_RELEASES) -> dict[str, Any]:
    releases_path = Path(path)
    data = yaml.safe_load(releases_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EngineRegistryLintError(f"{releases_path}: expected a mapping")
    releases = data.get("model_releases", data)
    if not isinstance(releases, dict):
        raise EngineRegistryLintError(f"{releases_path}: model_releases must be a mapping")
    return dict(releases)


def stale_entries(
    registry: Registry,
    known_revision_dates: dict[str, Any],
) -> list[EngineEntry]:
    return [entry for entry in registry.engines if Registry.stale(entry, known_revision_dates)]


def lint_registry(
    registry_path: Path | str = DEFAULT_REGISTRY,
    releases_path: Path | str = DEFAULT_RELEASES,
) -> Registry:
    registry = Registry.load(registry_path)
    known_revision_dates = load_known_revision_dates(releases_path)
    stale = stale_entries(registry, known_revision_dates)
    if stale:
        details = "; ".join(_stale_detail(entry, known_revision_dates) for entry in stale)
        raise EngineRegistryLintError(f"stale engine-registry rows: {details}")
    return registry


def _stale_detail(entry: EngineEntry, known_revision_dates: dict[str, Any]) -> str:
    known = known_revision_dates.get(entry.model_identity)
    return (
        f"{entry.key} last_validated={entry.last_validated.isoformat()} "
        f"predates {entry.model_identity} release {known!s}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--releases", default=str(DEFAULT_RELEASES))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        registry = lint_registry(args.registry, args.releases)
    except (OSError, RegistryError, EngineRegistryLintError, yaml.YAMLError) as exc:
        print(f"engine registry validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"engine registry ok: {len(registry.engines)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
