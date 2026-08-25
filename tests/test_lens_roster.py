"""Contract tests for the canonical Code Review lens roster (U4)."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROSTER_PATH = ROOT / "plugins" / "saga" / "references" / "lens-roster.json"
CATALOG_PATH = (
    ROOT / "plugins" / "saga" / "skills" / "code-review" / "references" / "lens-catalog.md"
)

ALWAYS_ON = {
    "correctness",
    "security",
    "testing",
    "architecture-maintainability",
}
CONDITIONAL = {
    "deployment-infrastructure",
    "reliability",
    "performance",
    "api-contract",
    "adversarial",
    "privacy",
    "documentation-clarity",
    "agent-usability",
    "previous-comments",
    "accessibility-human-usability",
}
ANCHOR_BANDS = {"10", "9", "7-8", "5-6", "0-4"}

EXPECTED_DIMENSIONS = {
    "correctness": {
        "intent-behavior-completeness",
        "state-data-invariants-transactions-concurrency",
        "boundary-types-serialization-numeric-time",
        "side-effects-errors-resource-lifecycle",
        "caller-enum-consumer-completeness",
    },
    "security": {
        "authentication-authorization-tenant-isolation",
        "input-trust-boundaries-injection",
        "secrets-cryptography-session-handling",
        "dependency-supply-chain",
        "confidentiality-logs-errors-egress",
    },
    "testing": {
        "requirements-regression-coverage",
        "negative-edge-state-concurrency-time",
        "behavior-sensitive-assertions",
        "realistic-seams-mocks-integration-evidence",
        "determinism-isolation-diagnostics-maintainability",
    },
    "architecture-maintainability": {
        "architectural-fit-ownership-single-sources",
        "separation-of-concerns",
        "dependency-direction",
        "simplicity-abstraction-duplication-changeability",
        "readability-naming-error-contracts",
        "conventions-portability-configuration",
        "significant-decision-documentation",
    },
    "deployment-infrastructure": {
        "infrastructure-configuration-least-privilege",
        "migrations-backfills-compatibility-rollout-order",
        "rollback-reversibility-drift",
        "cost-resilience",
        "deployed-state-verification-observability",
    },
    "reliability": {
        "timeouts-retries-circuit-breakers-idempotency",
        "queues-jobs-dead-letters-ordering-backpressure",
        "concurrency-partial-failure-recovery",
        "graceful-degradation-cancellation-cleanup",
        "health-signals-observability-runbooks",
    },
    "performance": {
        "measured-latency-throughput",
        "algorithm-query-index-cost",
        "io-batching-concurrency-waterfalls",
        "memory-resource-use",
        "cache-correctness-invalidation",
        "capacity-cost-tradeoffs",
    },
    "api-contract": {
        "interface-contract-compatibility",
        "versioning-deprecation",
        "serialization-errors",
        "retry-idempotency-semantics",
        "pagination-rate-limits",
        "sdk-generated-client-impact",
        "specification-documentation-parity",
    },
    "adversarial": {
        "load-bearing-assumptions",
        "abuse-edge-cases",
        "failure-amplification-silent-green",
        "environment-operator-failure",
        "scope-creep-risk",
        "alternatives-considered",
        "recovery",
    },
    "privacy": {
        "data-flow-inventory-classification",
        "data-minimization-purpose-consent",
        "personal-data-protection-sharing-third-parties",
        "retention-deletion-all-copies",
        "portability-residency-legal-flags",
        "ai-telemetry-training-reidentification",
    },
    "documentation-clarity": {
        "shipped-behavior-parity",
        "completeness-audience-prerequisites",
        "structure-navigation",
        "terminology-cross-document-consistency",
        "runnable-examples-actionability",
        "runbook-safety-rollback-links-generated-drift",
    },
    "agent-usability": {
        "capability-parity-reachability",
        "discoverability-invocation-schemas",
        "context-constraints-acceptance-examples",
        "machine-readable-output-actionable-errors",
        "safe-bounded-idempotent-resumable-context-cost",
    },
    "previous-comments": {"resolution-completeness"},
    "accessibility-human-usability": {
        "semantics-assistive-technology",
        "keyboard-focus",
        "contrast-zoom-motion-responsiveness",
        "labels-forms-loading-empty-error-states",
        "localization-content-resilience",
        "discoverability-defaults-error-recovery-command-surfaces",
    },
}

EXPECTED_LEGACY_FOCUS = {
    "DRY / Duplication",
    "Complexity & Readability",
    "Pattern Consistency",
    "Naming & Abstraction",
    "Error Handling Quality",
    "Data Minimization",
    "Consent & Purpose Limitation",
    "PII Handling & Classification",
    "Retention & Deletion",
    "Cross-Border & Compliance",
    "IaC Correctness",
    "IAM Least Privilege",
    "Cost Awareness",
    "Resilience",
    "Observability",
    "API Contract Correctness",
    "Versioning & Deprecation",
    "Error Response Design",
    "Idempotency",
    "SDK Impact",
    "Coverage Adequacy",
    "Test Quality",
    "Edge Case Testing",
    "Mock/Fixture Appropriateness",
    "Test Maintainability",
    "Structure & Navigation",
    "Precision of Language",
    "Completeness",
    "Understandability",
    "Actionability",
    "Context Completeness",
    "Unambiguous Acceptance Criteria",
    "Example Coverage",
    "Constraint Explicitness",
    "Machine-Parseable Structure",
}

# SHA-256 of the 15 detailed anchor tables ported from the former Review Criteria source,
# normalized as sorted JSON keyed by their source rubric. The two legacy below-five `BLOCKING`
# labels are deliberately absent because the operator deleted that terminal stop. This freezes the
# remaining port without keeping a second prose copy after the old policy document becomes a pointer.
PORTED_ANCHOR_DIGEST = "18941f3880953e72133de1c1e73ba35f9d7957b065c34d00b99af45ed601fcb3"


def _load_roster() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(ROSTER_PATH.read_text(encoding="utf-8")))


def _lens_map(roster: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {lens["id"]: lens for lens in roster["lenses"]}


def _validate_roster(roster: dict[str, Any], root: Path = ROOT) -> None:
    if roster.get("schema") != "lens_roster.v1":
        raise ValueError("unsupported lens roster schema")

    lenses = roster.get("lenses")
    if not isinstance(lenses, list) or len(lenses) != 14:
        raise ValueError("roster must declare fourteen lenses")

    lens_ids = [lens.get("id") for lens in lenses]
    if len(set(lens_ids)) != len(lens_ids):
        raise ValueError("lens identifiers must be unique")

    for lens in lenses:
        trigger = lens.get("trigger")
        if not isinstance(trigger, dict) or trigger.get("class") not in {
            "always-on",
            "conditional",
        }:
            raise ValueError(f"{lens.get('id')} has an invalid trigger")
        if trigger["class"] == "conditional":
            if not trigger.get("judgment_required"):
                raise ValueError(f"{lens['id']} must require judgment")
            if not trigger.get("recorded_reason_required"):
                raise ValueError(f"{lens['id']} must require a recorded reason")
            if trigger.get("reason_format") != "one-line":
                raise ValueError(f"{lens['id']} must require a one-line reason")
        if trigger.get("keyword_match_sufficient") is not False:
            raise ValueError(f"{lens['id']} cannot use keyword matching as sufficient selection")

        dimensions = lens.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            raise ValueError(f"{lens['id']} must declare at least one dimension")
        dimension_ids = [dimension.get("id") for dimension in dimensions]
        if len(set(dimension_ids)) != len(dimension_ids):
            raise ValueError(f"{lens['id']} dimension identifiers must be unique")
        for dimension in dimensions:
            if not isinstance(dimension.get("focus"), str) or not dimension["focus"].strip():
                raise ValueError(f"{lens['id']}/{dimension.get('id')} must declare focus")
            anchors = dimension.get("anchors")
            if not isinstance(anchors, dict) or set(anchors) != ANCHOR_BANDS:
                raise ValueError(f"{lens['id']}/{dimension.get('id')} anchors are incomplete")
            if any(not isinstance(value, str) or not value.strip() for value in anchors.values()):
                raise ValueError(f"{lens['id']}/{dimension.get('id')} has an empty anchor")

        implementations = lens.get("implementations")
        if not isinstance(implementations, dict):
            raise ValueError(f"{lens['id']} lacks implementation mappings")
        if set(implementations) != {"code_review", "team_execution"}:
            raise ValueError(f"{lens['id']} requires both implementation mappings")

        code_review = implementations["code_review"]
        if code_review.get("procedure") != "roster-scoring-lens":
            raise ValueError(f"{lens['id']} has an unknown Code Review procedure")
        code_review_path = root / code_review.get("path", "")
        if not code_review_path.is_file():
            raise ValueError(f"{lens['id']} Code Review procedure path does not exist")
        expected_heading = f"## {code_review.get('section', '')}"
        if expected_heading not in code_review_path.read_text(encoding="utf-8"):
            raise ValueError(f"{lens['id']} Code Review procedure section does not exist")

        team_execution = implementations["team_execution"]
        agent_path = root / team_execution.get("path", "")
        if not agent_path.is_file():
            raise ValueError(f"{lens['id']} Team Execution agent path does not exist")
        if team_execution.get("agent") != agent_path.stem:
            raise ValueError(
                f"{lens['id']} Team Execution agent identifier does not match its path"
            )


def _discover_rosters(root: Path) -> list[Path]:
    plugin_root = root / "plugins"
    if not plugin_root.is_dir():
        return []

    found: list[Path] = []
    for path in plugin_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and str(payload.get("schema", "")).startswith("lens_roster."):
            found.append(path)
    return sorted(found)


def _require_single_roster(root: Path) -> Path:
    rosters = _discover_rosters(root)
    if len(rosters) != 1:
        raise ValueError(f"expected one lens roster, found {len(rosters)}")
    return rosters[0]


def _is_historical_policy_record(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if path.name == "CHANGELOG.md":
        return True
    parts = set(relative.parts)
    return "docs" in parts and bool(parts & {"reviews", "code-reviews", "engineering-journal"})


def _live_threshold_declarations(root: Path, canonical: Path) -> list[Path]:
    threshold = re.compile(r"(?:overall\s*>=\s*9\.0|dimension\s*<\s*7\.0)", re.IGNORECASE)
    declarations: list[Path] = []
    for suffix in ("*.md", "*.py", "*.json"):
        for path in root.rglob(suffix):
            if path == canonical or _is_historical_policy_record(path, root):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if threshold.search(text):
                declarations.append(path)
    return sorted(set(declarations))


def test_roster_parses_with_exact_schema_and_lens_set() -> None:
    roster = _load_roster()
    lenses = _lens_map(roster)

    assert roster["schema"] == "lens_roster.v1"
    assert set(lenses) == ALWAYS_ON | CONDITIONAL
    assert {
        lens_id for lens_id, lens in lenses.items() if lens["trigger"]["class"] == "always-on"
    } == ALWAYS_ON
    assert {
        lens_id for lens_id, lens in lenses.items() if lens["trigger"]["class"] == "conditional"
    } == CONDITIONAL
    assert len(ALWAYS_ON) == 4
    assert len(CONDITIONAL) == 10


def test_all_seventy_six_dimensions_and_anchor_bands_are_explicit() -> None:
    roster = _load_roster()
    lenses = _lens_map(roster)

    assert {
        lens_id: {dimension["id"] for dimension in lens["dimensions"]}
        for lens_id, lens in lenses.items()
    } == EXPECTED_DIMENSIONS
    assert sum(len(lens["dimensions"]) for lens in lenses.values()) == 76

    _validate_roster(roster)


def test_detailed_legacy_anchors_and_optional_focuses_are_preserved() -> None:
    roster = _load_roster()
    dimensions = [dimension for lens in roster["lenses"] for dimension in lens["dimensions"]]

    ported = {
        dimension["anchor_source"]: dimension["anchors"]
        for dimension in dimensions
        if "anchor_source" in dimension
    }
    serialized = json.dumps(ported, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert len(ported) == 15
    assert hashlib.sha256(serialized).hexdigest() == PORTED_ANCHOR_DIGEST

    legacy_focus = {
        focus for dimension in dimensions for focus in dimension.get("legacy_focus", [])
    }
    assert legacy_focus == EXPECTED_LEGACY_FOCUS


def test_selection_contract_requires_operator_approval_for_conditionals() -> None:
    roster = _load_roster()
    contract = roster["selection_contract"]
    lenses = _lens_map(roster)

    assert contract["always_on_auto_run"] is True
    assert set(contract["always_on_ids"]) == ALWAYS_ON
    assert set(contract["always_on_ids"]) == {
        lens_id for lens_id, lens in lenses.items() if lens["trigger"]["class"] == "always-on"
    }
    assert contract["conditional_requires_operator_approval"] is True
    assert contract["batched_choices"] == [
        "accept-recommended",
        "always-on-only",
        "customize",
    ]
    assert contract["recommended_is_default"] is True
    assert contract["caller_or_orchestrate_selection_is_approval"] is True
    assert contract["persist_against"] == ["reviewed_commit", "review_cycle"]
    assert contract["reuse_on_repair_cycles_unless_applicability_delta"] is True
    assert contract["pause_on_dismissal_or_no_answer"] is True
    assert contract["no_hidden_or_supplemental_lenses"] is True
    assert contract["selection_adapter_cannot_approve"] is True


def test_conditional_selection_is_judgment_with_a_recorded_one_line_reason() -> None:
    lenses = _lens_map(_load_roster())

    for lens_id in CONDITIONAL:
        trigger = lenses[lens_id]["trigger"]
        assert trigger["judgment_required"] is True
        assert trigger["recorded_reason_required"] is True
        assert trigger["reason_format"] == "one-line"
        assert trigger["keyword_match_sufficient"] is False
        assert trigger["guidance"].strip()


def test_api_contract_keeps_its_identifier_and_covers_all_interface_types() -> None:
    lens = _lens_map(_load_roster())["api-contract"]
    guidance = lens["trigger"]["guidance"]

    assert lens["id"] == "api-contract"
    for interface_type in (
        "Hypertext Transfer Protocol",
        "events",
        "command-line interfaces",
        "configuration",
        "exported types",
        "file formats",
    ):
        assert interface_type in guidance


def test_only_the_two_operator_settled_acceptance_thresholds_exist() -> None:
    roster = _load_roster()
    acceptance = roster["acceptance"]
    serialized = json.dumps(roster)

    assert acceptance["only_acceptance_thresholds"] is True
    assert acceptance["combiner"] == "all"
    assert acceptance["rules"] == [
        {
            "id": "derived-overall-minimum",
            "metric": "derived_overall",
            "operator": ">=",
            "value": 9.0,
        },
        {
            "id": "applicable-dimension-floor",
            "metric": "applicable_dimension",
            "operator": ">=",
            "value": 7.0,
        },
    ]
    assert acceptance["finding_priority_is_gate"] is False
    assert acceptance["finding_confidence_is_gate"] is False
    assert "BLOCKING" not in serialized
    assert "below-5" not in serialized
    assert "terminal stop" not in serialized


def test_external_advisory_and_custom_reviewer_defaults_are_non_scoring() -> None:
    participants = _load_roster()["participant_defaults"]

    advisory = participants["external_advisory_seat"]
    assert advisory == {
        "id": "external-reviewer",
        "scoring": False,
        "consensus_denominator": False,
        "applies_acceptance_rules": [],
    }

    custom = participants["custom_reviewer"]
    assert custom["scoring"] is False
    assert custom["consensus_denominator"] is False
    assert custom["applies_acceptance_rules"] == []
    assert custom["voting_authority"] == "requires-explicit-policy-grant"


def test_fingerprint_deduplication_and_cross_reviewer_agreement_are_canonical() -> None:
    assert _load_roster()["finding_policy"] == {
        "fingerprint_fields": ["path", "line", "category"],
        "duplicate_action": "merge",
        "record_cross_reviewer_agreement": True,
    }


@pytest.mark.parametrize("missing_mapping", ["code_review", "team_execution"])
def test_every_lens_requires_both_executable_implementation_mappings(
    missing_mapping: str,
) -> None:
    roster = _load_roster()
    _validate_roster(roster)

    broken = copy.deepcopy(roster)
    del broken["lenses"][0]["implementations"][missing_mapping]

    with pytest.raises(ValueError, match="requires both implementation mappings"):
        _validate_roster(broken)


def test_catalog_is_an_executable_pointer_not_a_second_policy_copy() -> None:
    catalog = CATALOG_PATH.read_text(encoding="utf-8")

    assert "plugins/saga/references/lens-roster.json" in catalog
    assert "## Run a roster scoring lens" in catalog
    assert "roster-scoring-lens" in catalog
    assert "9.0" not in catalog
    assert "7.0" not in catalog
    assert len(catalog.splitlines()) >= 60


def test_repository_contains_exactly_one_machine_readable_roster(tmp_path: Path) -> None:
    assert _require_single_roster(ROOT).resolve() == ROSTER_PATH.resolve()

    first = tmp_path / "plugins" / "saga" / "references" / "lens-roster.json"
    second = tmp_path / "plugins" / "team-execution" / "references" / "other-roster.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    roster_bytes = ROSTER_PATH.read_bytes()
    first.write_bytes(roster_bytes)
    second.write_bytes(roster_bytes)

    with pytest.raises(ValueError, match="expected one lens roster, found 2"):
        _require_single_roster(tmp_path)


def test_parity_scan_ignores_historical_threshold_quotes(tmp_path: Path) -> None:
    canonical = tmp_path / "plugins" / "saga" / "references" / "lens-roster.json"
    live = tmp_path / "plugins" / "team-execution" / "skills" / "policy.md"
    changelog = tmp_path / "plugins" / "saga" / "CHANGELOG.md"
    review = tmp_path / "docs" / "code-reviews" / "review.md"
    journal = tmp_path / "docs" / "engineering-journal" / "DECISIONS.md"

    for path in (canonical, live, changelog, review, journal):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "Historical or live quote: overall >= 9.0 and dimension < 7.0.\n",
            encoding="utf-8",
        )

    assert _live_threshold_declarations(tmp_path, canonical) == [live]
