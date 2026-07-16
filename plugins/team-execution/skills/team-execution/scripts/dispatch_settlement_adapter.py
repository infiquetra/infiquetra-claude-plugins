#!/usr/bin/env python3
"""Installed-plugin bridge from team-execution evidence to Saga settlement (#351).

This module deliberately does not import or copy Saga's ledger code.  Team-execution is packaged
independently, so it resolves the installed Saga plugin, materializes a coordinator-owned artifact
from a real reviewer result or validator state file, then invokes Saga's canonical CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404 -- resolved Python script, fixed argv, no shell
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAGA_SCRIPT = Path("scripts") / "dispatch_settlement.py"
RUNG_NAMES = {
    1: "SAGA_PLUGIN_ROOT",
    2: "source-checkout",
    3: "installed-plugins",
    4: "cache-sibling",
}


class SettlementAdapterError(ValueError):
    """The independently installed Saga dependency or team evidence is invalid."""


class IncompleteEvidenceError(SettlementAdapterError):
    """Expected team evidence is absent or incomplete and must settle as silent-no-op."""


@dataclass(frozen=True)
class SagaResolution:
    """A verified Saga plugin root and the resolution rung that found it."""

    root: Path
    rung: int

    @property
    def script(self) -> Path:
        return self.root / SAGA_SCRIPT


def _is_saga_root(root: Path) -> bool:
    return (root / SAGA_SCRIPT).is_file()


def _source_checkout_root(script_path: Path) -> Path | None:
    for ancestor in script_path.resolve().parents:
        candidate = ancestor / "plugins" / "saga"
        if (ancestor / ".claude-plugin" / "marketplace.json").is_file() and _is_saga_root(
            candidate
        ):
            return candidate
    return None


def _registry_root(registry_path: Path) -> Path | None:
    try:
        plugins = json.loads(registry_path.read_text(encoding="utf-8"))["plugins"]
        entries = plugins.items()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    for name, records in entries:
        if not isinstance(name, str) or not name.startswith("saga@"):
            continue
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            install_path = record.get("installPath")
            if isinstance(install_path, str) and _is_saga_root(Path(install_path)):
                return Path(install_path)
    return None


def _semver_key(value: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


def _cache_sibling_root(plugin_root: str | None) -> Path | None:
    if not plugin_root:
        return None
    versions = Path(plugin_root).resolve().parent.parent / "saga"
    if not versions.is_dir():
        return None
    candidates = [
        (version, child)
        for child in versions.iterdir()
        if child.is_dir() and (version := _semver_key(child.name)) is not None
    ]
    for _, candidate in sorted(candidates, reverse=True):
        if _is_saga_root(candidate):
            return candidate
    return None


def resolve_saga_plugin(
    *,
    environ: Mapping[str, str] | None = None,
    registry_path: Path | None = None,
    script_path: Path | None = None,
) -> SagaResolution:
    """Resolve the Saga plugin or fail before a reviewer or validator Agent call."""
    environment = os.environ if environ is None else environ
    override = environment.get("SAGA_PLUGIN_ROOT")
    if override:
        root = Path(override)
        if not _is_saga_root(root):
            raise SettlementAdapterError(
                f"SAGA_PLUGIN_ROOT={override!r} is not a Saga plugin root "
                "(expected scripts/dispatch_settlement.py)."
            )
        return SagaResolution(root=root, rung=1)

    checkout = _source_checkout_root(script_path or Path(__file__))
    if checkout is not None:
        return SagaResolution(root=checkout, rung=2)

    registry = registry_path or (Path.home() / ".claude" / "plugins" / "installed_plugins.json")
    installed = _registry_root(registry)
    if installed is not None:
        return SagaResolution(root=installed, rung=3)

    cached = _cache_sibling_root(environment.get("CLAUDE_PLUGIN_ROOT"))
    if cached is not None:
        return SagaResolution(root=cached, rung=4)

    raise SettlementAdapterError(
        "team-execution: Saga dispatch settlement is unavailable; install the Saga plugin, set "
        "SAGA_PLUGIN_ROOT to its root, or run from an Infiquetra source checkout. This preflight "
        "must pass before any reviewer or validator Agent call."
    )


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise IncompleteEvidenceError(f"{label} is absent: {path}") from exc
    except OSError as exc:
        raise SettlementAdapterError(f"{label} is not readable JSON: {path}") from exc
    try:
        value = _strict_json(raw, label=label)
    except json.JSONDecodeError as exc:
        raise SettlementAdapterError(f"{label} contains corrupt JSON: {path}") from exc
    if not isinstance(value, dict):
        raise IncompleteEvidenceError(f"{label} must be a structured JSON object: {path}")
    return value


def _strict_json(raw: str, *, label: str) -> object:
    """Load JSON while rejecting duplicate keys at every object depth."""

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise SettlementAdapterError(f"{label} contains duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=reject_duplicates)


def _nonempty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SettlementAdapterError(f"{field} must be a non-empty string")
    return value


def _validate_reviewer_result(result: Mapping[str, Any], *, unit_id: str) -> None:
    if result.get("reviewer") != unit_id:
        if "reviewer" in result:
            raise SettlementAdapterError(
                "reviewer result reviewer must match the settlement unit_id"
            )
        raise IncompleteEvidenceError("reviewer result has no reviewer identity")
    score = result.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 10:
        raise IncompleteEvidenceError("reviewer result score must be numeric and within 0..10")
    dimensions = result.get("dimension_scores")
    if not isinstance(dimensions, Mapping) or not dimensions:
        raise IncompleteEvidenceError("reviewer result requires non-empty dimension_scores")
    for name, value in dimensions.items():
        _nonempty_string(name, field="reviewer dimension name")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
            raise IncompleteEvidenceError(
                "reviewer dimension scores must be numeric and within 0..10"
            )
    if not isinstance(result.get("findings"), list):
        raise IncompleteEvidenceError("reviewer result requires a findings list")


def _validate_validator_state(state: Mapping[str, Any], *, unit_id: str, repo_root: Path) -> None:
    if state.get("validator") != unit_id:
        if "validator" in state:
            raise SettlementAdapterError(
                "validator state validator must match the settlement unit_id"
            )
        raise IncompleteEvidenceError("validator state has no validator identity")
    if state.get("required") is not True:
        raise IncompleteEvidenceError("validator settlement requires a required validator state")
    if not isinstance(state.get("status"), str) or not state["status"].strip():
        raise IncompleteEvidenceError("validator state requires a non-empty status")
    evidence = state.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise IncompleteEvidenceError("validator state requires non-empty evidence")
    for item in evidence:
        relative = _nonempty_string(item, field="validator evidence path")
        candidate = (repo_root / relative).resolve()
        try:
            candidate.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise SettlementAdapterError(
                "validator evidence path must remain inside repo_root"
            ) from exc
        if not candidate.is_file():
            raise IncompleteEvidenceError(f"validator evidence path does not exist: {relative}")


def materialize_artifact(
    *,
    kind: str,
    unit_id: str,
    source_path: Path,
    receipt_path: Path,
    repo_root: Path,
) -> Path:
    """Validate actual coordinator-collected evidence and write a canonical artifact receipt."""
    value = _load_object(source_path, label=f"{kind} evidence")
    if kind == "reviewer":
        _validate_reviewer_result(value, unit_id=unit_id)
        artifact_kind = "reviewer-result"
    elif kind == "validator":
        _validate_validator_state(value, unit_id=unit_id, repo_root=repo_root)
        artifact_kind = "validator-state"
    else:  # pragma: no cover - argparse enforces this boundary
        raise SettlementAdapterError(f"unsupported team evidence kind {kind!r}")

    artifact = {
        "schema": "dispatch.artifact.v1",
        "kind": artifact_kind,
        "unit_id": unit_id,
        "payload": value,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return receipt_path


def manifest_units(kind: str, roster: object) -> list[dict[str, object]]:
    """Build the complete expected roster without letting a per-call unit shrink it."""
    if kind not in {"reviewer", "validator"}:  # pragma: no cover - argparse enforces this boundary
        raise SettlementAdapterError(f"unsupported team evidence kind {kind!r}")
    if not isinstance(roster, list) or not roster:
        raise SettlementAdapterError("team roster must be a non-empty JSON list")
    names = [_nonempty_string(item, field="team roster member") for item in roster]
    if len(names) != len(set(names)):
        raise SettlementAdapterError("team roster members must be unique")
    deliverable = "scored-review" if kind == "reviewer" else "validator-state"
    return [
        {
            "unit_id": name,
            "idempotency_key": f"team-execution:{kind}:{name}",
            "deliverables": [deliverable],
        }
        for name in names
    ]


def invoke_saga(
    resolution: SagaResolution,
    args: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    """Pass a command through to the independently resolved Saga settlement CLI."""
    completed = runner([sys.executable, str(resolution.script), *args], check=False)
    return completed.returncode


def _json_argument(raw: str, *, label: str) -> object:
    path = Path(raw)
    try:
        if path.is_file():
            return _strict_json(path.read_text(encoding="utf-8"), label=label)
    except OSError as exc:
        raise SettlementAdapterError(f"{label} is not readable JSON: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SettlementAdapterError(f"{label} contains corrupt JSON: {path}") from exc
    try:
        return _strict_json(raw, label=label)
    except json.JSONDecodeError as exc:
        raise SettlementAdapterError(f"{label} must be JSON or a path to JSON") from exc


def _repo_path(repo_root: Path, raw_path: str, *, label: str) -> Path:
    root = repo_root.resolve()
    candidate = Path(raw_path).expanduser()
    candidate = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise SettlementAdapterError(f"{label} must remain inside repo_root") from exc
    return resolved


def _settle_args(args: argparse.Namespace, descriptor_path: Path | None) -> list[str]:
    evidence_root = getattr(args, "evidence_root", "") or args.repo_root
    evidence = (
        "null"
        if descriptor_path is None
        else json.dumps(
            {
                "receipt_type": "artifact",
                "unit_id": args.unit_id,
                "evidence_path": str(descriptor_path),
            }
        )
    )
    return [
        "--repo-root",
        args.repo_root,
        "--subplot-id",
        args.subplot_id,
        "--evidence-root",
        evidence_root,
        "settle",
        "--dispatch-id",
        args.dispatch_id,
        "--unit-id",
        args.unit_id,
        "--attempt",
        str(args.attempt),
        "--at",
        args.at,
        "--evidence-json",
        evidence,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="team-execution adapter for Saga dispatch settlement"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight", help="resolve Saga before any Agent call")
    manifest = sub.add_parser("manifest", help="record one complete reviewer or validator roster")
    manifest.add_argument("--kind", choices=("reviewer", "validator"), required=True)
    manifest.add_argument("--repo-root", required=True)
    manifest.add_argument("--subplot-id", required=True)
    manifest.add_argument("--dispatch-id", required=True)
    manifest.add_argument("--roster-json", required=True)
    manifest.add_argument("--at", required=True)
    manifest.add_argument("--casualty-threshold-percent", type=int, default=0)
    manifest.add_argument("--max-attempts", type=int, default=3)
    saga = sub.add_parser("saga", help="pass a canonical command through to Saga")
    saga.add_argument("args", nargs=argparse.REMAINDER)
    settle = sub.add_parser("settle", help="materialize team evidence and settle through Saga")
    settle.add_argument("--kind", choices=("reviewer", "validator"), required=True)
    settle.add_argument("--repo-root", required=True)
    settle.add_argument("--subplot-id", required=True)
    settle.add_argument("--dispatch-id", required=True)
    settle.add_argument("--unit-id", required=True)
    settle.add_argument("--attempt", type=int, required=True)
    settle.add_argument("--at", required=True)
    settle.add_argument("--source-json", required=True)
    settle.add_argument("--receipt-path", required=True)
    settle.add_argument(
        "--evidence-root",
        default="",
        help="root containing source/receipt state (default repo-root; may be ~/.claude state)",
    )
    args = parser.parse_args(argv)

    try:
        resolution = resolve_saga_plugin()
        if args.command == "preflight":
            print(json.dumps({"root": str(resolution.root), "rung": RUNG_NAMES[resolution.rung]}))
            return 0
        if args.command == "manifest":
            units = manifest_units(args.kind, _json_argument(args.roster_json, label="team roster"))
            return invoke_saga(
                resolution,
                [
                    "--repo-root",
                    args.repo_root,
                    "--subplot-id",
                    args.subplot_id,
                    "manifest",
                    "--dispatch-id",
                    args.dispatch_id,
                    "--site",
                    "team-execution",
                    "--units-json",
                    json.dumps(units, sort_keys=True),
                    "--at",
                    args.at,
                    "--casualty-threshold-percent",
                    str(args.casualty_threshold_percent),
                    "--max-attempts",
                    str(args.max_attempts),
                ],
            )
        if args.command == "saga":
            forwarded = list(args.args)
            if forwarded[:1] == ["--"]:
                forwarded = forwarded[1:]
            if not forwarded:
                raise SettlementAdapterError("saga pass-through requires a Saga settlement command")
            return invoke_saga(resolution, forwarded)
        descriptor: Path | None
        try:
            repo_root = Path(args.repo_root)
            evidence_root = Path(args.evidence_root or args.repo_root)
            receipt = materialize_artifact(
                kind=args.kind,
                unit_id=args.unit_id,
                source_path=_repo_path(evidence_root, args.source_json, label="source JSON path"),
                receipt_path=_repo_path(evidence_root, args.receipt_path, label="receipt path"),
                repo_root=repo_root,
            )
            descriptor = receipt
        except IncompleteEvidenceError:
            # The task did spawn but did not produce contract-bearing delivery evidence. Let Saga
            # append the canonical silent-no-op settlement; agent success prose never changes this.
            descriptor = None
        return invoke_saga(resolution, _settle_args(args, descriptor))
    except SettlementAdapterError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
