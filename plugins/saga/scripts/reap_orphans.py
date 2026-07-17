#!/usr/bin/env python3
"""Project immutable runtime facts into read-only orphan candidates (#355)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402
import manifest_store  # noqa: E402
import outcome_store  # noqa: E402


class ReapOrphansError(RuntimeError):
    """Projection input or fleet-core resolution failed closed."""


def _load_orphan_evidence() -> ModuleType:
    try:
        return fleet_commons_shim.load("orphan_evidence")
    except RuntimeError as exc:
        raise ReapOrphansError(str(exc)) from exc


def _load_lease_broker() -> ModuleType:
    try:
        return fleet_commons_shim.load("lease_broker")
    except RuntimeError as exc:
        raise ReapOrphansError(str(exc)) from exc


def _canonical_evidence_root() -> Path:
    try:
        audit_store = fleet_commons_shim.load("audit_store")
    except RuntimeError as exc:
        raise ReapOrphansError(str(exc)) from exc
    return Path(audit_store.DEFAULT_AUDIT_STORE_ROOT).expanduser().resolve()


def _matching_close(
    heads: Mapping[str, Any], archived_heads: Mapping[str, Any], run_id: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    matches: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for collection in (archived_heads, heads):
        for head in collection.values():
            if not isinstance(head, Mapping):
                continue
            close = head.get("close_receipt")
            if isinstance(close, Mapping) and close.get("run_id") == run_id:
                matches.append((head, close))
    if len(matches) > 1:
        raise ReapOrphansError(f"canonical stores contain multiple heads for run {run_id!r}")
    return None if not matches else matches[0]


def _projection_fact(
    *, classification: str, close: Mapping[str, Any], evidence_ref: str
) -> dict[str, Any]:
    return {
        "schema": "orphan_projection_fact.v1",
        "classification": classification,
        "producer": close["producer"],
        "run_id": close["run_id"],
        "resource_ref": close["resource_ref"],
        "token": close["token"],
        "lease_id": close["lease_id"],
        "expected_output_sha256": close["expected_output_sha256"],
        "receipt_sha256": close["receipt_sha256"],
        "evidence_refs": sorted({*close["evidence_refs"], evidence_ref}),
        "authoritative_terminal": True,
    }


def _expected_output_contracts(
    orphan_evidence: ModuleType,
    expected_outputs: Sequence[Mapping[str, Any]],
    expected_output_templates: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    outputs_by_run: dict[str, dict[str, Any]] = {}
    templates_by_digest: dict[str, dict[str, Any]] = {}
    try:
        for raw in expected_outputs:
            record = orphan_evidence.validate_record(raw)
            if record["schema"] != "expected_output.v1":
                raise ReapOrphansError("expected-output input must use expected_output.v1")
            run_id = record["run_id"]
            if run_id in outputs_by_run:
                raise ReapOrphansError(f"duplicate expected-output input for run {run_id!r}")
            outputs_by_run[run_id] = record
        for raw in expected_output_templates:
            record = orphan_evidence.validate_record(raw)
            if record["schema"] != "agy.expected-output-template.v1":
                raise ReapOrphansError(
                    "expected-output-template input must use agy.expected-output-template.v1"
                )
            digest = record["expected_output_template_sha256"]
            if digest in templates_by_digest:
                raise ReapOrphansError(f"duplicate expected-output template {digest!r}")
            templates_by_digest[digest] = record
    except orphan_evidence.OrphanEvidenceError as exc:
        raise ReapOrphansError(f"EVIDENCE_INTEGRITY_ERROR: {exc}") from exc
    return outputs_by_run, templates_by_digest


def _empty_artifact_classification(
    *,
    close: Mapping[str, Any],
    completeness: Mapping[str, Any],
    outputs_by_run: Mapping[str, Mapping[str, Any]],
    templates_by_digest: Mapping[str, Mapping[str, Any]],
) -> tuple[str | None, list[str]]:
    expected = outputs_by_run.get(close["run_id"])
    if expected is None:
        return None, []
    template = templates_by_digest.get(expected["expected_output_template_sha256"])
    refs = [f"expected-output:{expected['expected_output_sha256']}"]
    if template is None:
        return "evidence-integrity-error", refs
    refs.append(f"expected-output-template:{template['expected_output_template_sha256']}")
    bindings_match = (
        expected["resource_ref"] == close["resource_ref"]
        and expected["token"] == close["token"]
        and expected["lease_id"] == close["lease_id"]
        and expected["generation"] == close["generation"]
        and expected["producer"] == close["producer"]
        and expected["run_id"] == close["run_id"]
        and expected["expected_output_sha256"] == close["expected_output_sha256"]
    )
    declared = completeness.get("declared_keys")
    target = completeness.get("target_count")
    contract_matches = (
        isinstance(declared, list)
        and sorted(declared) == template["artifact_keys"]
        and target == template["target_count"]
    )
    if not bindings_match or not contract_matches:
        return "evidence-integrity-error", refs
    if template["required"] is not True:
        return None, refs
    return "empty-artifacts", refs


def _load_projection_facts(
    *,
    repo_root: Path | None,
    outcome_id: str | None,
    saga_id: str | None,
    heads: Mapping[str, Any],
    archived_heads: Mapping[str, Any],
    orphan_evidence: ModuleType,
    expected_outputs: Sequence[Mapping[str, Any]],
    expected_output_templates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if repo_root is None:
        if outcome_id is not None or saga_id is not None:
            raise ReapOrphansError("outcome_id and saga_id require repo_root")
        return []
    facts: list[dict[str, Any]] = []
    outputs_by_run, templates_by_digest = _expected_output_contracts(
        orphan_evidence, expected_outputs, expected_output_templates
    )
    resolved_repo = repo_root.expanduser().resolve()
    if outcome_id is not None:
        outcome = outcome_store.Store.for_outcome(outcome_id, resolved_repo)
        latest: dict[str, outcome_store.CompletionEvent] = {}
        if outcome.events_dir.is_dir():
            for path in sorted(outcome.events_dir.glob("*.a*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    event = outcome_store.CompletionEvent.from_dict(raw)
                    event.validate()
                except (OSError, ValueError, outcome_store.OutcomeStoreError) as exc:
                    raise ReapOrphansError(
                        f"invalid canonical outcome event {path}: {exc}"
                    ) from exc
                current = latest.get(event.subplot_id)
                if current is None or event.attempt > current.attempt:
                    latest[event.subplot_id] = event
        for run_id, event in sorted(latest.items()):
            if event.state != "stalled":
                continue
            matched = _matching_close(heads, archived_heads, run_id)
            if matched is not None:
                _head, close = matched
                facts.append(
                    _projection_fact(
                        classification="stalled",
                        close=close,
                        evidence_ref=f"outcome:{outcome_id}:{run_id}:a{event.attempt}",
                    )
                )
    if saga_id is not None:
        manifests = manifest_store.Store.for_saga(saga_id, resolved_repo)
        for execution_id in manifest_store.list_manifests(manifests):
            raw = manifest_store.read_manifest(manifests, execution_id)
            completeness = None if raw is None else raw.get("output_completeness")
            if not isinstance(completeness, Mapping):
                continue
            declared = completeness.get("declared_keys")
            missing = completeness.get("missing_keys")
            target = completeness.get("target_count")
            produced = completeness.get("produced_count")
            required_missing = bool(isinstance(declared, list) and missing) or (
                isinstance(target, int)
                and target > 0
                and isinstance(produced, int)
                and produced < target
            )
            if not required_missing:
                continue
            matched = _matching_close(heads, archived_heads, execution_id)
            if matched is not None:
                _head, close = matched
                classification, contract_refs = _empty_artifact_classification(
                    close=close,
                    completeness=completeness,
                    outputs_by_run=outputs_by_run,
                    templates_by_digest=templates_by_digest,
                )
                if classification is None:
                    continue
                fact = _projection_fact(
                    classification=classification,
                    close=close,
                    evidence_ref=f"manifest:{saga_id}:{execution_id}",
                )
                fact["evidence_refs"] = sorted({*fact["evidence_refs"], *contract_refs})
                facts.append(fact)
    return facts


def snapshot_from_stores(
    *,
    broker_root: Path,
    evidence_root: Path | None = None,
    repo_root: Path | None = None,
    outcome_id: str | None = None,
    saga_id: str | None = None,
    expected_outputs: Sequence[Mapping[str, Any]] = (),
    expected_output_templates: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Read canonical broker/evidence stores and return a closed, immutable projection view."""

    lease_broker = _load_lease_broker()
    orphan_evidence = _load_orphan_evidence()
    try:
        inspected = lease_broker.LeaseBroker(broker_root.expanduser().resolve()).inspect()
    except lease_broker.LeaseBrokerError as exc:
        raise ReapOrphansError(f"cannot read canonical broker store: {exc}") from exc
    heads = inspected.get("resource_fences")
    if not isinstance(heads, Mapping):
        raise ReapOrphansError("canonical broker snapshot lacks resource heads")
    archived_heads = inspected.get("archived_resource_fences", {})
    if not isinstance(archived_heads, Mapping):
        raise ReapOrphansError("canonical broker snapshot has malformed archived resource heads")
    broker_epoch = inspected.get("broker_epoch")
    if not isinstance(broker_epoch, str):
        raise ReapOrphansError("canonical broker snapshot lacks its broker epoch")
    leases_raw = inspected.get("leases")
    if not isinstance(leases_raw, list):
        raise ReapOrphansError("canonical broker snapshot lacks leases")
    leases: list[dict[str, Any]] = []
    for lease in leases_raw:
        if not isinstance(lease, Mapping):
            raise ReapOrphansError("canonical broker snapshot contains a malformed lease")
        if lease.get("pool") != "agent" or lease.get("resource_ref") is None:
            continue
        leases.append(
            {
                "lease_id": lease.get("lease_id"),
                "resource_ref": lease.get("resource_ref"),
                "broker_epoch": broker_epoch,
                "fencing_sequence": lease.get("fencing_sequence"),
                "derived_state": lease.get("derived_state"),
            }
        )
    sources: list[Mapping[str, Any]] = []
    root = (
        _canonical_evidence_root()
        if evidence_root is None
        else evidence_root.expanduser().resolve()
    )
    if root.is_dir():
        events_root = root / orphan_evidence.EVENTS
        if events_root.is_dir():
            for path in sorted(events_root.rglob("*.json")):
                try:
                    event = orphan_evidence.loads_record(path.read_bytes())
                except (OSError, orphan_evidence.OrphanEvidenceError) as exc:
                    raise ReapOrphansError(
                        f"cannot read canonical orphan event {path}: {exc}"
                    ) from exc
                if event["schema"] != "orphan_event.v1":
                    raise ReapOrphansError(
                        f"canonical orphan event path contains {event['schema']}"
                    )
                sources.append(event)
        seals_root = root / orphan_evidence.SEALS
        if seals_root.is_dir():
            for path in sorted(seals_root.rglob("*.json")):
                try:
                    seal = orphan_evidence.loads_record(path.read_bytes())
                except (OSError, orphan_evidence.OrphanEvidenceError) as exc:
                    raise ReapOrphansError(
                        f"cannot read canonical close seal {path}: {exc}"
                    ) from exc
                if seal["schema"] != "settlement_close.v1":
                    raise ReapOrphansError(f"canonical close-seal path contains {seal['schema']}")
                digest = orphan_evidence.resource_sha256(seal["resource_ref"])
                head = heads.get(digest) or archived_heads.get(digest)
                close = head.get("close_receipt") if isinstance(head, Mapping) else None
                if (
                    isinstance(close, Mapping)
                    and close.get("generation") == seal["generation"]
                    and dict(close) != seal
                ):
                    raise ReapOrphansError("audit close seal contradicts canonical broker receipt")
    sources.extend(
        _load_projection_facts(
            repo_root=repo_root,
            outcome_id=outcome_id,
            saga_id=saga_id,
            heads=heads,
            archived_heads=archived_heads,
            orphan_evidence=orphan_evidence,
            expected_outputs=expected_outputs,
            expected_output_templates=expected_output_templates,
        )
    )
    return {
        "schema": "orphan-projection-snapshot.v1",
        "broker_heads": dict(heads),
        "archived_broker_heads": dict(archived_heads),
        "broker_leases": leases,
        "sources": sources,
    }


def scan(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic candidates without mutating an evidence or authority store."""

    orphan_evidence = _load_orphan_evidence()
    try:
        return cast(list[dict[str, Any]], orphan_evidence.project_candidates(snapshot))
    except orphan_evidence.OrphanEvidenceError as exc:
        raise ReapOrphansError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    scan_parser = subcommands.add_parser("scan", help="derive orphan candidates without mutation")
    scan_parser.add_argument(
        "--broker-root", required=True, type=Path, help="Canonical fleet-core broker authority root"
    )
    scan_parser.add_argument("--repo-root", type=Path)
    scan_parser.add_argument("--outcome-id")
    scan_parser.add_argument("--saga-id")
    scan_parser.add_argument(
        "--expected-output", action="append", default=[], type=Path, metavar="PATH"
    )
    scan_parser.add_argument(
        "--expected-output-template", action="append", default=[], type=Path, metavar="PATH"
    )
    recover_parser = subcommands.add_parser(
        "quarantine-recover", help="recover the canonical machine-local quarantine store"
    )
    recover_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "quarantine-recover":
        orphan_evidence = _load_orphan_evidence()
        lease_broker = _load_lease_broker()
        result = orphan_evidence.recover_quarantine(
            orphan_evidence.QuarantineStore.for_root(
                _canonical_evidence_root(), providers=lease_broker.Providers()
            )
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    if args.command != "scan":  # pragma: no cover - argparse owns the closed command set.
        raise ReapOrphansError(f"unknown command: {args.command}")
    orphan_evidence = _load_orphan_evidence()

    def load_contract(path: Path) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], orphan_evidence.loads_record(path.read_bytes()))
        except (OSError, orphan_evidence.OrphanEvidenceError) as exc:
            raise ReapOrphansError(f"EVIDENCE_INTEGRITY_ERROR: {path}: {exc}") from exc

    snapshot = snapshot_from_stores(
        broker_root=args.broker_root,
        repo_root=args.repo_root,
        outcome_id=args.outcome_id,
        saga_id=args.saga_id,
        expected_outputs=[load_contract(path) for path in args.expected_output],
        expected_output_templates=[load_contract(path) for path in args.expected_output_template],
    )
    candidates = scan(snapshot)
    print(json.dumps(candidates, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReapOrphansError as exc:
        print(f"reap-orphans: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
