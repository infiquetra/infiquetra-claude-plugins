#!/usr/bin/env python3
"""Typed reconciliation for external-engine findings (#393).

The controller keeps engine output advisory: it accounts for finding identities,
records Claude's adjudication, and appends bounded typed results to the existing
hash-chained run-fact ledger. Gate authority remains in ``engine_dispatch``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402
import run_ledger  # noqa: E402

_tier_palette = fleet_commons_shim.load("tier_palette")

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_STANDARD_FACT_FIELDS = {
    "schema",
    "kind",
    "subplot_id",
    "at",
    "prev_hash",
    "this_hash",
}
_RECONCILIATION_FACT_FIELDS = {
    "reconciliation_id",
    "execution_id",
    "intent",
    "recipe_id",
    "adjudicator_id",
    "evidence_digest",
    "action",
    "result_hash",
    "source_finding_ids",
    "items",
}
RECIPE_UPDATE_PROPOSAL_SCHEMA = "recipe_update_proposal.v1"
MAX_ID_BYTES = 256
MAX_ITEMS = 256
MAX_RATIONALE_BYTES = 4096
MAX_RESULT_BYTES = 65536
MAX_SOURCE_FINDING_BYTES = 1024 * 1024
MAX_REJECTION_NOTE_BYTES = 1024


class ReconciliationError(ValueError):
    """A reconciliation recipe, result, or ledger fact is malformed."""


class ReconciliationStatus(StrEnum):
    RECONCILED = "reconciled"
    DROPPED = "dropped"
    OVERRIDDEN = "overridden"


class ReconciliationAction(StrEnum):
    RECONCILE = "reconcile"
    APPLY = "apply"


@dataclass(frozen=True)
class SourceFinding:
    """One ordered external finding, identified only by stable content metadata."""

    source_finding_id: str
    digest: str

    def __post_init__(self) -> None:
        _require_id(self.source_finding_id, "source_finding_id")
        _require_digest(self.digest, "source finding digest")
        parts = self.source_finding_id.split(":")
        if (
            len(parts) != 3
            or parts[0] not in {"external-finding", "opaque-artifact"}
            or not parts[1].isdigit()
            or parts[2] != self.digest
        ):
            raise ReconciliationError(
                "source_finding_id must encode its kind, ordinal, and content digest"
            )

    @classmethod
    def from_content(cls, content: str, index: int, *, opaque: bool = False) -> SourceFinding:
        if not isinstance(content, str) or not content:
            raise ReconciliationError("source finding content must be a non-empty string")
        if len(content.encode("utf-8")) > MAX_SOURCE_FINDING_BYTES:
            raise ReconciliationError(
                f"source finding content exceeds {MAX_SOURCE_FINDING_BYTES} bytes"
            )
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ReconciliationError("source finding index must be a non-negative integer")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        kind = "opaque-artifact" if opaque else "external-finding"
        return cls(f"{kind}:{index}:{digest}", digest)


def parse_source_findings(raw: Any) -> tuple[SourceFinding, ...]:
    """Validate the runner's ordered ``findings`` envelope without retaining its prose."""
    if not isinstance(raw, list):
        raise ReconciliationError("runner findings must be an ordered array")
    findings: list[SourceFinding] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping) or set(item) != {"content"}:
            raise ReconciliationError(
                "each runner finding must be an object containing only string content"
            )
        findings.append(SourceFinding.from_content(item["content"], index))
    return tuple(findings)


@dataclass(frozen=True)
class PanelMemberEvidence:
    """One unique advisory-panel output presented to the Claude foreman.

    Duplicate non-empty output is one finding with every producing member retained. Empty output
    is member-specific so every silent member remains an explicit reconciliation obligation.
    The raw ``output`` is in-memory foreman input only; reconciliation ledger facts contain only
    the resulting typed finding IDs and adjudications.
    """

    source_finding_id: str
    member_ids: tuple[str, ...]
    output: str
    empty: bool

    def __post_init__(self) -> None:
        _require_id(self.source_finding_id, "source_finding_id")
        if not self.member_ids:
            raise ReconciliationError("panel evidence requires at least one member identity")
        if len(self.member_ids) != len(set(self.member_ids)):
            raise ReconciliationError("panel evidence member identities must be unique")
        for member_id in self.member_ids:
            _require_id(member_id, "panel member identity")
        if not isinstance(self.output, str):
            raise ReconciliationError("panel member output must be a string")
        if self.empty is not (not self.output.strip()):
            raise ReconciliationError("panel evidence empty marker disagrees with member output")


@dataclass(frozen=True)
class ReconciliationRecipe:
    intent: str
    recipe_id: str
    instruction: str


# Definitions include the approved next canonical intent. Only intents currently
# exported by fleet-core enter RECIPE_REGISTRY, so parity is exact before and after U2.
_RECIPE_DEFINITIONS = (
    ReconciliationRecipe(
        "offload",
        "offload-accept-drop-override-v1",
        "Account for every external finding before Claude applies accepted work.",
    ),
    ReconciliationRecipe(
        "second-opinion",
        "second-opinion-adjudicate-v1",
        "Claude independently adjudicates every external review finding.",
    ),
    ReconciliationRecipe(
        "divergence",
        "divergence-review-agreement-v1",
        "Claude explicitly reviews both agreement and disagreement as advisory signal.",
    ),
)


def _build_registry(
    intents: Iterable[str],
    definitions_source: Iterable[ReconciliationRecipe] = _RECIPE_DEFINITIONS,
) -> Mapping[str, ReconciliationRecipe]:
    definitions: dict[str, ReconciliationRecipe] = {}
    for recipe in definitions_source:
        if recipe.intent in definitions:
            raise ReconciliationError(f"duplicate reconciliation recipe for {recipe.intent!r}")
        definitions[recipe.intent] = recipe
    canonical = tuple(intents)
    if len(set(canonical)) != len(canonical):
        raise ReconciliationError("canonical ENGINE_INTENTS contains duplicates")
    missing = set(canonical) - set(definitions)
    if missing:
        raise ReconciliationError(
            f"canonical intent(s) have no reconciliation recipe: {sorted(missing)}"
        )
    surplus = set(definitions) - set(canonical)
    if surplus:
        raise ReconciliationError(
            f"reconciliation recipe definition(s) are not canonical intents: {sorted(surplus)}"
        )
    return MappingProxyType({intent: definitions[intent] for intent in canonical})


RECIPE_REGISTRY = _build_registry(_tier_palette.ENGINE_INTENTS)


def validate_registry(intents: Iterable[str] | None = None) -> None:
    """Fail unless the public registry maps every canonical intent exactly once."""
    canonical = tuple(_tier_palette.ENGINE_INTENTS if intents is None else intents)
    if set(RECIPE_REGISTRY) != set(canonical) or len(RECIPE_REGISTRY) != len(canonical):
        raise ReconciliationError(
            "reconciliation recipe registry does not exactly match canonical ENGINE_INTENTS"
        )
    if any(intent != recipe.intent for intent, recipe in RECIPE_REGISTRY.items()):
        raise ReconciliationError(
            "reconciliation recipe registry keys disagree with recipe intents"
        )
    if len({recipe.recipe_id for recipe in RECIPE_REGISTRY.values()}) != len(RECIPE_REGISTRY):
        raise ReconciliationError("reconciliation recipe IDs must be unique")


def recipe_for_intent(intent: str) -> ReconciliationRecipe:
    try:
        return RECIPE_REGISTRY[intent]
    except KeyError:
        raise ReconciliationError(
            f"unknown reconciliation intent {intent!r}; expected one of {tuple(RECIPE_REGISTRY)}"
        ) from None


def _require_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ReconciliationError(f"{field} must be a non-empty normalized string")
    if any(ord(char) < 32 for char in value):
        raise ReconciliationError(f"{field} must not contain control characters")
    if len(value.encode("utf-8")) > MAX_ID_BYTES:
        raise ReconciliationError(f"{field} exceeds {MAX_ID_BYTES} bytes")
    return value


def validate_panel_execution_metadata(
    *,
    execution_id: Any,
    intent: Any,
    subplot_id: Any,
    at: Any,
) -> None:
    """Validate required panel persistence metadata before resolution can perform preflight."""
    if not isinstance(intent, str):
        raise ReconciliationError("panel intent must be a canonical intent string")
    recipe_for_intent(intent)
    _require_id(execution_id, "panel execution_id")
    _require_id(subplot_id, "panel subplot_id")
    _require_id(at, "panel at")


def evidence_digest(evidence: str) -> str:
    if not isinstance(evidence, str):
        raise ReconciliationError("external evidence must be a string")
    return hashlib.sha256(evidence.encode("utf-8")).hexdigest()


def source_finding_ids_for_evidence(evidence: str) -> tuple[str, ...]:
    return (SourceFinding.from_content(evidence, 0, opaque=True).source_finding_id,) if evidence else ()


def _require_digest(value: Any, field: str = "evidence_digest") -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ReconciliationError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_claude_id(value: Any, field: str = "adjudicator_id") -> str:
    identity = _require_id(value, field)
    lowered = identity.lower()
    if lowered != "claude" and not lowered.startswith("claude/"):
        raise ReconciliationError(f"{field} must identify Claude (claude or claude/<variant>)")
    return identity


@dataclass(frozen=True)
class ReconciliationItem:
    source_finding_id: str
    status: ReconciliationStatus
    adjudicator_id: str
    rationale: str

    def __post_init__(self) -> None:
        _require_id(self.source_finding_id, "source_finding_id")
        if not isinstance(self.status, ReconciliationStatus):
            raise ReconciliationError("status must be a ReconciliationStatus")
        _require_claude_id(self.adjudicator_id)
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ReconciliationError("every reconciliation item requires a non-empty rationale")
        if any(ord(char) < 32 for char in self.rationale):
            raise ReconciliationError("reconciliation rationale must not contain control characters")
        if len(self.rationale.encode("utf-8")) > MAX_RATIONALE_BYTES:
            raise ReconciliationError(
                f"reconciliation rationale exceeds {MAX_RATIONALE_BYTES} bytes"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "source_finding_id": self.source_finding_id,
            "status": self.status.value,
            "adjudicator_id": self.adjudicator_id,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReconciliationItem:
        expected = {"source_finding_id", "status", "adjudicator_id", "rationale"}
        if set(data) != expected:
            raise ReconciliationError("reconciliation item fields are malformed")
        try:
            status = ReconciliationStatus(data["status"])
        except (TypeError, ValueError) as exc:
            raise ReconciliationError(
                f"invalid reconciliation status {data.get('status')!r}"
            ) from exc
        return cls(
            source_finding_id=data["source_finding_id"],
            status=status,
            adjudicator_id=data["adjudicator_id"],
            rationale=data["rationale"],
        )


@dataclass(frozen=True)
class ReconciliationResult:
    reconciliation_id: str
    execution_id: str
    intent: str
    recipe_id: str
    adjudicator_id: str
    evidence_digest: str
    source_finding_ids: tuple[str, ...]
    items: tuple[ReconciliationItem, ...]

    def __post_init__(self) -> None:
        _require_id(self.reconciliation_id, "reconciliation_id")
        _require_id(self.execution_id, "execution_id")
        adjudicator = _require_claude_id(self.adjudicator_id)
        _require_digest(self.evidence_digest)
        recipe = recipe_for_intent(self.intent)
        if self.recipe_id != recipe.recipe_id:
            raise ReconciliationError(
                f"recipe {self.recipe_id!r} does not match intent {self.intent!r}"
            )
        if not isinstance(self.source_finding_ids, tuple) or not isinstance(self.items, tuple):
            raise ReconciliationError("source_finding_ids and items must be immutable tuples")
        if not all(isinstance(item, ReconciliationItem) for item in self.items):
            raise ReconciliationError("items must contain only ReconciliationItem values")
        if len(self.items) > MAX_ITEMS or len(self.source_finding_ids) > MAX_ITEMS:
            raise ReconciliationError(f"reconciliation result exceeds {MAX_ITEMS} findings")
        source_ids = tuple(
            _require_id(value, "source_finding_id") for value in self.source_finding_ids
        )
        if len(source_ids) != len(set(source_ids)):
            raise ReconciliationError("duplicate source finding IDs are not allowed")
        item_ids = tuple(item.source_finding_id for item in self.items)
        if len(item_ids) != len(set(item_ids)):
            raise ReconciliationError("duplicate reconciliation item finding IDs are not allowed")
        unknown = set(item_ids) - set(source_ids)
        if unknown:
            raise ReconciliationError(
                f"reconciliation items name unknown findings: {sorted(unknown)}"
            )
        expected_item_order = tuple(source_id for source_id in source_ids if source_id in item_ids)
        if item_ids != expected_item_order:
            raise ReconciliationError("reconciliation items must preserve source finding order")
        if any(item.adjudicator_id != adjudicator for item in self.items):
            raise ReconciliationError("item adjudicator_id must match the result adjudicator_id")
        if len(self._unbounded_dict_json()) > MAX_RESULT_BYTES:
            raise ReconciliationError(f"reconciliation result exceeds {MAX_RESULT_BYTES} bytes")

    def _unbounded_dict_json(self) -> bytes:
        data = {
            "reconciliation_id": self.reconciliation_id,
            "execution_id": self.execution_id,
            "intent": self.intent,
            "recipe_id": self.recipe_id,
            "adjudicator_id": self.adjudicator_id,
            "evidence_digest": self.evidence_digest,
            "source_finding_ids": list(self.source_finding_ids),
            "items": [item.to_dict() for item in self.items],
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @property
    def unaccounted_finding_ids(self) -> tuple[str, ...]:
        accounted = {item.source_finding_id for item in self.items}
        return tuple(
            finding_id for finding_id in self.source_finding_ids if finding_id not in accounted
        )

    @property
    def ready(self) -> bool:
        return not self.unaccounted_finding_ids

    def require_ready(self) -> None:
        if not self.ready:
            raise ReconciliationError(
                "unaccounted external finding(s): " + ", ".join(self.unaccounted_finding_ids)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reconciliation_id": self.reconciliation_id,
            "execution_id": self.execution_id,
            "intent": self.intent,
            "recipe_id": self.recipe_id,
            "adjudicator_id": self.adjudicator_id,
            "evidence_digest": self.evidence_digest,
            "source_finding_ids": list(self.source_finding_ids),
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReconciliationResult:
        expected = {
            "reconciliation_id",
            "execution_id",
            "intent",
            "recipe_id",
            "adjudicator_id",
            "evidence_digest",
            "source_finding_ids",
            "items",
        }
        if set(data) != expected:
            raise ReconciliationError("reconciliation result fields are malformed")
        sources = data["source_finding_ids"]
        items = data["items"]
        if not isinstance(sources, list) or not isinstance(items, list):
            raise ReconciliationError("source_finding_ids and items must be arrays")
        if not all(isinstance(item, Mapping) for item in items):
            raise ReconciliationError("every reconciliation item must be an object")
        return cls(
            reconciliation_id=data["reconciliation_id"],
            execution_id=data["execution_id"],
            intent=data["intent"],
            recipe_id=data["recipe_id"],
            adjudicator_id=data["adjudicator_id"],
            evidence_digest=data["evidence_digest"],
            source_finding_ids=tuple(sources),
            items=tuple(ReconciliationItem.from_dict(item) for item in items),
        )


def build_result(
    *,
    reconciliation_id: str,
    execution_id: str,
    intent: str,
    adjudicator_id: str,
    evidence_digest: str | None = None,
    source_finding_ids: Iterable[str],
    items: Iterable[ReconciliationItem],
) -> ReconciliationResult:
    recipe = recipe_for_intent(intent)
    source_ids = tuple(source_finding_ids)
    bound_digest = evidence_digest or hashlib.sha256(
        json.dumps(source_ids, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ReconciliationResult(
        reconciliation_id=reconciliation_id,
        execution_id=execution_id,
        intent=intent,
        recipe_id=recipe.recipe_id,
        adjudicator_id=adjudicator_id,
        evidence_digest=bound_digest,
        source_finding_ids=source_ids,
        items=tuple(items),
    )


def gather_panel_evidence(
    member_outputs: Iterable[tuple[str, str]],
) -> tuple[PanelMemberEvidence, ...]:
    """Deduplicate advisory member output while preserving explicit empty-member evidence."""
    gathered: dict[str, tuple[list[str], str, bool]] = {}
    for member_id, output in member_outputs:
        member = _require_id(member_id, "panel member identity")
        if not isinstance(output, str):
            raise ReconciliationError("panel member output must be a string")
        empty = not output.strip()
        if empty:
            digest = hashlib.sha256(member.encode()).hexdigest()
            finding_id = f"panel-empty:{digest}"
        else:
            digest = hashlib.sha256(output.encode()).hexdigest()
            finding_id = f"panel-evidence:{digest}"

        existing = gathered.get(finding_id)
        if existing is None:
            gathered[finding_id] = ([member], output, empty)
            continue
        members, prior_output, prior_empty = existing
        if prior_output != output or prior_empty != empty:
            raise ReconciliationError("panel evidence digest collision")
        if member not in members:
            members.append(member)

    return tuple(
        PanelMemberEvidence(
            source_finding_id=finding_id,
            member_ids=tuple(members),
            output=output,
            empty=empty,
        )
        for finding_id, (members, output, empty) in gathered.items()
    )


def validate_panel_reconciliation(
    result: ReconciliationResult,
    *,
    execution_id: str,
    intent: str,
    evidence: Iterable[PanelMemberEvidence],
) -> ReconciliationResult:
    """Require the Claude foreman's typed result to account for exactly the gathered evidence."""
    if not isinstance(result, ReconciliationResult):
        raise ReconciliationError("Claude panel foreman must return a typed reconciliation result")
    result.require_ready()
    if result.execution_id != execution_id:
        raise ReconciliationError("panel reconciliation execution_id disagrees with the request")
    if result.intent != intent:
        raise ReconciliationError("panel reconciliation intent disagrees with the request")
    expected_ids = tuple(item.source_finding_id for item in evidence)
    if set(result.source_finding_ids) != set(expected_ids):
        raise ReconciliationError(
            "panel reconciliation must account for exactly the gathered member evidence"
        )
    return result


def normalize_rejection_note(note: Any) -> str:
    """Return the concise single-line chaperone summary required for a rejected offload."""
    if not isinstance(note, str):
        raise ReconciliationError("rejected offload requires a string rejection note")
    normalized = " ".join(note.split())
    if not normalized:
        raise ReconciliationError("rejected offload requires a non-empty rejection note")
    if any(ord(char) < 32 for char in normalized):
        raise ReconciliationError("rejected offload rejection note contains control characters")
    if len(normalized.encode("utf-8")) > MAX_REJECTION_NOTE_BYTES:
        raise ReconciliationError(
            f"rejected offload rejection note exceeds {MAX_REJECTION_NOTE_BYTES} bytes"
        )
    return normalized


def build_rejected_offload_signal(
    *,
    reconciliation_id: str,
    execution_id: str,
    intent: str,
    adjudicator_id: str,
    rejection_note: str,
    bound_evidence_digest: str | None = None,
    bound_source_finding_ids: Iterable[str] | None = None,
) -> ReconciliationResult:
    """Account for a chaperone rejection as one typed, dropped advisory finding.

    The engine output was considered and explicitly rejected, so ``DROPPED`` is the honest
    reconciliation status. The rationale is the normalized rejection note that downstream
    reviewers and validators receive; this function grants it no gate authority.
    """
    note = normalize_rejection_note(rejection_note)
    fallback_id = f"rejected-offload:{_require_id(execution_id, 'execution_id')}"
    source_ids = tuple(bound_source_finding_ids or (fallback_id,))
    return build_result(
        reconciliation_id=reconciliation_id,
        execution_id=execution_id,
        intent=intent,
        adjudicator_id=adjudicator_id,
        evidence_digest=bound_evidence_digest or evidence_digest(note),
        source_finding_ids=source_ids,
        items=(
            *(
                ReconciliationItem(
                    source_finding_id=finding_id,
                    status=ReconciliationStatus.DROPPED,
                    adjudicator_id=adjudicator_id,
                    rationale=note,
                )
                for finding_id in source_ids
            ),
        ),
    )


def reviewer_validator_evidence(result: ReconciliationResult) -> dict[str, Any]:
    """Project a ready result into the advisory reviewer/validator evidence contract."""
    result.require_ready()
    return {
        "kind": "typed-reconciliation",
        "audiences": ["reviewer", "validator"],
        "advisory": True,
        "result": result.to_dict(),
    }


def canonical_result_hash(result: ReconciliationResult) -> str:
    encoded = json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def append_reconciliation_fact(
    ledger: run_ledger.RunLedger,
    result: ReconciliationResult,
    *,
    action: ReconciliationAction | str,
    subplot_id: str,
    at: str,
) -> dict[str, Any]:
    result.require_ready()
    try:
        typed_action = ReconciliationAction(action)
    except ValueError as exc:
        raise ReconciliationError(f"invalid reconciliation action {action!r}") from exc
    result_hash = canonical_result_hash(result)
    fact = run_ledger.build_fact(
        "reconciliation",
        subplot_id=subplot_id,
        at=at,
        reconciliation_id=result.reconciliation_id,
        execution_id=result.execution_id,
        intent=result.intent,
        recipe_id=result.recipe_id,
        adjudicator_id=result.adjudicator_id,
        evidence_digest=result.evidence_digest,
        action=typed_action.value,
        result_hash=result_hash,
        source_finding_ids=list(result.source_finding_ids),
        items=[
            {"source_finding_id": item.source_finding_id, "status": item.status.value}
            for item in result.items
        ],
    )

    def validate_transition(snapshot: run_ledger.LedgerSnapshot) -> None:
        existing = _validated_reconciliation_facts(snapshot.records, snapshot.report)
        same = [row for row in existing if row["reconciliation_id"] == result.reconciliation_id]
        if same and any(row["result_hash"] != result_hash for row in same):
            raise ReconciliationError(
                f"reconciliation identity {result.reconciliation_id!r} already names another result"
            )
        actions = [row["action"] for row in same]
        if typed_action is ReconciliationAction.RECONCILE and actions:
            raise ReconciliationError("duplicate or out-of-order reconcile transition")
        if typed_action is ReconciliationAction.APPLY and actions != ["reconcile"]:
            raise ReconciliationError("apply requires exactly one prior reconcile transition")

    return cast(
        dict[str, Any],
        run_ledger.append_fact_atomic(ledger, fact, validate_snapshot=validate_transition),
    )


def read_reconciliation_facts(ledger: run_ledger.RunLedger) -> list[dict[str, Any]]:
    snapshot = run_ledger.read_snapshot(ledger)
    return _validated_reconciliation_facts(snapshot.records, snapshot.report)


def _validated_reconciliation_facts(
    records: Iterable[dict[str, Any]], report: run_ledger.ChainReport
) -> list[dict[str, Any]]:
    if not report.ok:
        raise ReconciliationError(f"run-fact chain verification failed: {report.reason}")
    validated: list[dict[str, Any]] = []
    identities: dict[str, str] = {}
    transitions: dict[str, list[str]] = {}
    for fact in records:
        if fact.get("kind") != "reconciliation":
            continue
        if set(fact) != _STANDARD_FACT_FIELDS | _RECONCILIATION_FACT_FIELDS:
            raise ReconciliationError("reconciliation fact fields are malformed")
        if fact.get("schema") != run_ledger.RUN_FACT_SCHEMA:
            raise ReconciliationError("reconciliation fact has an unsupported schema")
        _require_id(fact.get("subplot_id"), "subplot_id")
        if not isinstance(fact.get("at"), str):
            raise ReconciliationError("reconciliation fact at must be a string")
        raw_action = fact.get("action")
        if not isinstance(raw_action, str):
            raise ReconciliationError(f"invalid reconciliation action {raw_action!r}")
        try:
            ReconciliationAction(raw_action)
        except ValueError as exc:
            raise ReconciliationError(f"invalid reconciliation action {raw_action!r}") from exc
        for field in (
            "reconciliation_id",
            "execution_id",
            "intent",
            "recipe_id",
            "adjudicator_id",
        ):
            _require_id(fact.get(field), field)
        recipe = recipe_for_intent(cast(str, fact["intent"]))
        if fact["recipe_id"] != recipe.recipe_id:
            raise ReconciliationError("reconciliation fact recipe disagrees with its intent")
        _require_claude_id(fact["adjudicator_id"])
        _require_digest(fact.get("evidence_digest"))
        source_ids = fact.get("source_finding_ids")
        items = fact.get("items")
        if not isinstance(source_ids, list) or not isinstance(items, list):
            raise ReconciliationError("reconciliation structural projection must contain arrays")
        if len(source_ids) > MAX_ITEMS or len(items) > MAX_ITEMS:
            raise ReconciliationError(f"reconciliation fact exceeds {MAX_ITEMS} findings")
        normalized_sources = tuple(_require_id(item, "source_finding_id") for item in source_ids)
        if len(normalized_sources) != len(set(normalized_sources)):
            raise ReconciliationError("reconciliation fact contains duplicate source findings")
        projected_ids: list[str] = []
        for item in items:
            if not isinstance(item, Mapping) or set(item) != {"source_finding_id", "status"}:
                raise ReconciliationError("reconciliation fact item projection is malformed")
            projected_ids.append(_require_id(item["source_finding_id"], "source_finding_id"))
            try:
                ReconciliationStatus(item["status"])
            except (TypeError, ValueError) as exc:
                raise ReconciliationError(
                    f"invalid reconciliation status {item.get('status')!r}"
                ) from exc
        if tuple(projected_ids) != normalized_sources or len(projected_ids) != len(set(projected_ids)):
            raise ReconciliationError("reconciliation fact does not account for each source exactly once")
        result_hash = fact.get("result_hash")
        if not isinstance(result_hash, str) or not _HASH_RE.fullmatch(result_hash):
            raise ReconciliationError("reconciliation fact result_hash must be lowercase SHA-256")
        identity = cast(str, fact["reconciliation_id"])
        previous = identities.setdefault(identity, result_hash)
        if previous != result_hash:
            raise ReconciliationError(
                f"duplicate reconciliation identity {identity!r} has conflicting results"
            )
        prior_actions = transitions.setdefault(identity, [])
        if raw_action == "reconcile" and prior_actions:
            raise ReconciliationError("duplicate or out-of-order reconcile transition")
        if raw_action == "apply" and prior_actions != ["reconcile"]:
            raise ReconciliationError("apply requires exactly one prior reconcile transition")
        prior_actions.append(raw_action)
        validated.append(fact)
    return validated


def derive_recipe_update_proposal(ledger: run_ledger.RunLedger) -> dict[str, Any]:
    """Derive an approval-gated recipe-review proposal from valid reconciliation facts.

    The reconciliation reader verifies the complete ledger chain and validates every selected fact
    before this function aggregates anything. Reconcile/apply facts for the same stable
    ``reconciliation_id`` are one outcome: their actions and fact hashes remain available as evidence,
    but their result contributes to the aggregate exactly once. This function performs no append and
    never changes :data:`RECIPE_REGISTRY`.
    """
    facts = read_reconciliation_facts(ledger)
    if not facts:
        return {
            "schema": RECIPE_UPDATE_PROPOSAL_SCHEMA,
            "status": "no-proposal",
            "approval_required": False,
            "reason": "no reconciliation facts",
            "proposed_updates": [],
            "evidence": [],
        }

    evidence_by_identity: dict[str, dict[str, Any]] = {}
    projections_by_identity: dict[str, dict[str, Any]] = {}
    for fact in facts:
        identity = cast(str, fact["reconciliation_id"])
        evidence = evidence_by_identity.get(identity)
        if evidence is None:
            projections_by_identity[identity] = fact
            evidence = {
                "reconciliation_id": identity,
                "execution_id": fact["execution_id"],
                "intent": fact["intent"],
                "recipe_id": fact["recipe_id"],
                "result_hash": fact["result_hash"],
                "actions": [],
                "ledger_fact_hashes": [],
            }
            evidence_by_identity[identity] = evidence
        action = cast(str, fact["action"])
        if action not in evidence["actions"]:
            evidence["actions"].append(action)
        fact_hash = cast(str, fact["this_hash"])
        if fact_hash not in evidence["ledger_fact_hashes"]:
            evidence["ledger_fact_hashes"].append(fact_hash)

    aggregates: dict[str, dict[str, Any]] = {}
    for identity, projection in projections_by_identity.items():
        aggregate = aggregates.setdefault(
            projection["intent"],
            {
                "intent": projection["intent"],
                "current_recipe_id": projection["recipe_id"],
                "recommended_action": "review-intent-recipe",
                "reconciliation_count": 0,
                "finding_status_counts": {status.value: 0 for status in ReconciliationStatus},
                "evidence_reconciliation_ids": [],
            },
        )
        aggregate["reconciliation_count"] += 1
        aggregate["evidence_reconciliation_ids"].append(identity)
        for item in projection["items"]:
            aggregate["finding_status_counts"][item["status"]] += 1

    proposed_updates = []
    for aggregate in aggregates.values():
        counts = aggregate["finding_status_counts"]
        aggregate["reason"] = (
            f"Review {aggregate['current_recipe_id']} using "
            f"{aggregate['reconciliation_count']} deduplicated reconciliation outcome(s): "
            f"{counts['reconciled']} reconciled, {counts['dropped']} dropped, and "
            f"{counts['overridden']} overridden finding(s)."
        )
        proposed_updates.append(aggregate)

    return {
        "schema": RECIPE_UPDATE_PROPOSAL_SCHEMA,
        "status": "proposal",
        "approval_required": True,
        "reason": "validated reconciliation outcomes are available for recipe review",
        "proposed_updates": proposed_updates,
        "evidence": list(evidence_by_identity.values()),
    }
