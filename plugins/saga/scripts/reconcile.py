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
    "action",
    "result_hash",
    "result",
}


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


def _build_registry(intents: Iterable[str]) -> Mapping[str, ReconciliationRecipe]:
    definitions: dict[str, ReconciliationRecipe] = {}
    for recipe in _RECIPE_DEFINITIONS:
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
    source_finding_ids: tuple[str, ...]
    items: tuple[ReconciliationItem, ...]

    def __post_init__(self) -> None:
        _require_id(self.reconciliation_id, "reconciliation_id")
        _require_id(self.execution_id, "execution_id")
        adjudicator = _require_claude_id(self.adjudicator_id)
        recipe = recipe_for_intent(self.intent)
        if self.recipe_id != recipe.recipe_id:
            raise ReconciliationError(
                f"recipe {self.recipe_id!r} does not match intent {self.intent!r}"
            )
        if not isinstance(self.source_finding_ids, tuple) or not isinstance(self.items, tuple):
            raise ReconciliationError("source_finding_ids and items must be immutable tuples")
        if not all(isinstance(item, ReconciliationItem) for item in self.items):
            raise ReconciliationError("items must contain only ReconciliationItem values")
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
        if any(item.adjudicator_id != adjudicator for item in self.items):
            raise ReconciliationError("item adjudicator_id must match the result adjudicator_id")

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
            source_finding_ids=tuple(sources),
            items=tuple(ReconciliationItem.from_dict(item) for item in items),
        )


def build_result(
    *,
    reconciliation_id: str,
    execution_id: str,
    intent: str,
    adjudicator_id: str,
    source_finding_ids: Iterable[str],
    items: Iterable[ReconciliationItem],
) -> ReconciliationResult:
    recipe = recipe_for_intent(intent)
    return ReconciliationResult(
        reconciliation_id=reconciliation_id,
        execution_id=execution_id,
        intent=intent,
        recipe_id=recipe.recipe_id,
        adjudicator_id=adjudicator_id,
        source_finding_ids=tuple(source_finding_ids),
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
    """Return the single-line advisory note required for a rejected offload."""
    if not isinstance(note, str):
        raise ReconciliationError("rejected offload requires a string rejection note")
    normalized = " ".join(note.split())
    if not normalized:
        raise ReconciliationError("rejected offload requires a non-empty rejection note")
    if any(ord(char) < 32 for char in normalized):
        raise ReconciliationError("rejected offload rejection note contains control characters")
    return normalized


def build_rejected_offload_signal(
    *,
    reconciliation_id: str,
    execution_id: str,
    adjudicator_id: str,
    rejection_note: str,
) -> ReconciliationResult:
    """Account for a chaperone rejection as one typed, dropped advisory finding.

    The engine output was considered and explicitly rejected, so ``DROPPED`` is the honest
    reconciliation status. The rationale is the normalized rejection note that downstream
    reviewers and validators receive; this function grants it no gate authority.
    """
    note = normalize_rejection_note(rejection_note)
    finding_id = f"rejected-offload:{_require_id(execution_id, 'execution_id')}"
    return build_result(
        reconciliation_id=reconciliation_id,
        execution_id=execution_id,
        intent="offload",
        adjudicator_id=adjudicator_id,
        source_finding_ids=(finding_id,),
        items=(
            ReconciliationItem(
                source_finding_id=finding_id,
                status=ReconciliationStatus.DROPPED,
                adjudicator_id=adjudicator_id,
                rationale=note,
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
    for existing in read_reconciliation_facts(ledger):
        if (
            existing["reconciliation_id"] == result.reconciliation_id
            and existing["result_hash"] != result_hash
        ):
            raise ReconciliationError(
                f"reconciliation identity {result.reconciliation_id!r} already names another result"
            )
    fact = run_ledger.build_fact(
        "reconciliation",
        subplot_id=subplot_id,
        at=at,
        reconciliation_id=result.reconciliation_id,
        execution_id=result.execution_id,
        intent=result.intent,
        recipe_id=result.recipe_id,
        adjudicator_id=result.adjudicator_id,
        action=typed_action.value,
        result_hash=result_hash,
        result=result.to_dict(),
    )
    return cast(dict[str, Any], run_ledger.append_fact(ledger, fact))


def read_reconciliation_facts(ledger: run_ledger.RunLedger) -> list[dict[str, Any]]:
    report = run_ledger.verify_chain(ledger)
    if not report.ok:
        raise ReconciliationError(f"run-fact chain verification failed: {report.reason}")
    validated: list[dict[str, Any]] = []
    identities: dict[str, str] = {}
    for fact in run_ledger.read_facts(ledger):
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
        raw_result = fact.get("result")
        if not isinstance(raw_result, Mapping):
            raise ReconciliationError("reconciliation fact result must be an object")
        result = ReconciliationResult.from_dict(raw_result)
        result.require_ready()
        result_hash = fact.get("result_hash")
        if not isinstance(result_hash, str) or not _HASH_RE.fullmatch(result_hash):
            raise ReconciliationError("reconciliation fact result_hash must be lowercase SHA-256")
        if canonical_result_hash(result) != result_hash:
            raise ReconciliationError("reconciliation fact result_hash does not match its result")
        for field in (
            "reconciliation_id",
            "execution_id",
            "intent",
            "recipe_id",
            "adjudicator_id",
        ):
            if fact.get(field) != getattr(result, field):
                raise ReconciliationError(f"reconciliation fact {field} disagrees with its result")
        previous = identities.setdefault(result.reconciliation_id, result_hash)
        if previous != result_hash:
            raise ReconciliationError(
                f"duplicate reconciliation identity {result.reconciliation_id!r} has conflicting results"
            )
        validated.append(fact)
    return validated
