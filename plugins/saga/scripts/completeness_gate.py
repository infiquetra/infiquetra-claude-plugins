#!/usr/bin/env python3
"""Completeness-gate oracle — the single source of 'what is an omission' semantics.

Unit-tested and self-testable. Pure Python, stdlib only, no I/O at import.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FailureClass(StrEnum):
    """The extensible set of completeness gate failure classes (R8)."""

    MISSING_OUTPUT = "missing-output"
    MALFORMED_OUTPUT = "malformed-output"
    VERIFIER_DISAGREEMENT = "verifier-disagreement"


@dataclass(frozen=True)
class Failure:
    """An immutable record of a completeness gate failure trip."""

    failure_class: FailureClass
    message: str
    unit_id: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Contract:
    """Describes what a leaf is expected to emit (R7)."""

    expects_output: bool
    returns: list[str] = field(default_factory=list)
    target_count: int | None = None

    @classmethod
    def derive(
        cls,
        returns: list[str] | None = None,
        fanout: bool = False,
        targets: list[str] | None = None,
    ) -> Contract:
        """Derive expects_output = True when the unit is schema-bearing / non-empty returns /

        is an enumerated fan-out; False for a prose/side-effect-only leaf (R7/AE9).
        """
        ret = list(returns) if returns else []
        tgs = list(targets) if targets else []
        expects_output = bool(ret) or (fanout and bool(tgs))
        target_count = len(tgs) if (fanout and tgs) else None
        return cls(
            expects_output=expects_output,
            returns=ret,
            target_count=target_count,
        )

    @classmethod
    def from_unit(cls, unit: Any) -> Contract:
        """Duck-typed helper to construct a Contract from a Unit object."""
        returns = getattr(unit, "returns", [])
        fanout = getattr(unit, "fanout", False)
        targets = getattr(unit, "targets", [])
        return cls.derive(returns=returns, fanout=fanout, targets=targets)


def _is_empty_or_absent(result: Any) -> bool:
    """Determine if a result is null, absent, or an empty emit."""
    if result is None:
        return True
    if isinstance(result, str):
        return not result.strip()
    if isinstance(result, (dict, list, set, tuple)):
        return len(result) == 0
    return False


def _parse_result(result: Any) -> Any:
    """Helper to parse a result string as JSON if applicable."""
    if isinstance(result, str):
        s = result.strip()
        # Clean markdown code blocks if present
        if s.startswith("```"):
            lines = s.splitlines()
            if len(lines) >= 2:
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                s = "\n".join(lines).strip()
        if s.startswith("{") or s.startswith("["):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
    return result


def check_presence(result: Any, *, contract: Contract, unit_id: str = "") -> Failure | None:
    """Trip when contract.expects_output and result is None/absent/empty-no-emit."""
    if not contract.expects_output:
        return None

    if _is_empty_or_absent(result):
        return Failure(
            failure_class=FailureClass.MISSING_OUTPUT,
            message=f"Unit {unit_id} expected structured output but received none or empty output.",
            unit_id=unit_id,
        )
    return None


def check_truncation(result: Any, *, unit_id: str = "") -> Failure | None:
    """Trip when result is structurally truncated/incomplete JSON."""
    if isinstance(result, str):
        s = result.strip()
        if s.startswith("```"):
            lines = s.splitlines()
            if len(lines) >= 2:
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                s = "\n".join(lines).strip()

        if s.startswith("{") or s.startswith("["):
            try:
                json.loads(s)
            except json.JSONDecodeError as e:
                return Failure(
                    failure_class=FailureClass.MALFORMED_OUTPUT,
                    message=f"Unit {unit_id} output is a structurally truncated JSON: {e}",
                    unit_id=unit_id,
                    detail=str(e),
                )
    return None


def check_fanout_count(result: Any, *, contract: Contract, unit_id: str = "") -> Failure | None:
    """Trip when produced item count < contract.target_count, naming the shortfall."""
    if contract.target_count is None:
        return None

    parsed = _parse_result(result)
    produced_count = 0
    if isinstance(parsed, (list, dict, set, tuple)):
        produced_count = len(parsed)
    elif parsed is not None:
        produced_count = 0 if _is_empty_or_absent(parsed) else 1

    if produced_count < contract.target_count:
        shortfall = contract.target_count - produced_count
        return Failure(
            failure_class=FailureClass.MISSING_OUTPUT,
            message=(
                f"Unit {unit_id} produced fewer items than expected. "
                f"Expected {contract.target_count}, produced {produced_count}. "
                f"Shortfall: {shortfall}."
            ),
            unit_id=unit_id,
            detail=f"shortfall: {shortfall}",
        )
    return None


def check_required_keys(result: Any, *, contract: Contract, unit_id: str = "") -> Failure | None:
    """Trip when any declared key in contract.returns is absent from emitted keys."""
    if not contract.returns:
        return None

    parsed = _parse_result(result)
    if not isinstance(parsed, dict):
        missing = contract.returns
        return Failure(
            failure_class=FailureClass.MISSING_OUTPUT,
            message=(
                f"Unit {unit_id} result is not a structured dictionary. "
                f"Missing required keys: {', '.join(missing)}."
            ),
            unit_id=unit_id,
            detail=f"missing: {', '.join(missing)}",
        )

    missing = [k for k in contract.returns if k not in parsed or parsed[k] is None]
    if missing:
        return Failure(
            failure_class=FailureClass.MISSING_OUTPUT,
            message=f"Unit {unit_id} output is missing required keys: {', '.join(missing)}.",
            unit_id=unit_id,
            detail=f"missing: {', '.join(missing)}",
        )
    return None


def classify(result: Any, *, contract: Contract, unit_id: str = "") -> Failure | None:
    """Runs the predicates in a sensible order, returning the first trip or None."""
    fail = check_presence(result, contract=contract, unit_id=unit_id)
    if fail is not None:
        return fail

    fail = check_truncation(result, unit_id=unit_id)
    if fail is not None:
        return fail

    fail = check_fanout_count(result, contract=contract, unit_id=unit_id)
    if fail is not None:
        return fail

    fail = check_required_keys(result, contract=contract, unit_id=unit_id)
    if fail is not None:
        return fail

    return None


def self_test() -> int:
    """Runs tests on the four canonical omission fixtures (R13/KTD3)."""
    # 1. null-when-expected
    contract_1 = Contract(expects_output=True)
    res_1 = None
    fail_1 = classify(res_1, contract=contract_1, unit_id="U1")
    if not fail_1 or fail_1.failure_class != FailureClass.MISSING_OUTPUT:
        print("UNCAUGHT: null-when-expected", file=sys.stderr)
        return 1
    print(f"caught: {fail_1.failure_class.value}")

    # 2. truncated string
    contract_2 = Contract(expects_output=True)
    res_2 = '{"key": "value'
    fail_2 = classify(res_2, contract=contract_2, unit_id="U2")
    if not fail_2 or fail_2.failure_class != FailureClass.MALFORMED_OUTPUT:
        print("UNCAUGHT: truncated string", file=sys.stderr)
        return 1
    print(f"caught: {fail_2.failure_class.value}")

    # 3. short fan-out count
    contract_3 = Contract(expects_output=True, target_count=3)
    res_3 = [1, 2]
    fail_3 = classify(res_3, contract=contract_3, unit_id="U3")
    if not fail_3 or fail_3.failure_class != FailureClass.MISSING_OUTPUT:
        print("UNCAUGHT: short fan-out count", file=sys.stderr)
        return 1
    print(f"caught: {fail_3.failure_class.value}")

    # 4. missing required key
    contract_4 = Contract(expects_output=True, returns=["key1", "key2"])
    res_4 = {"key1": 1}
    fail_4 = classify(res_4, contract=contract_4, unit_id="U4")
    if not fail_4 or fail_4.failure_class != FailureClass.MISSING_OUTPUT:
        print("UNCAUGHT: missing required key", file=sys.stderr)
        return 1
    print(f"caught: {fail_4.failure_class.value}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Completeness-gate oracle.")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run self-tests on canonical omission fixtures (R13)",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
