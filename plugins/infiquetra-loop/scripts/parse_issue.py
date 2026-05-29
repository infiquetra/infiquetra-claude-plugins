#!/usr/bin/env python3
"""Parse an issue body for context refs, acceptance criteria, and scope hints."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

ADR_RE = re.compile(r"\bADR[-\s]?(\d{2,4})\b", re.IGNORECASE)
AC_RE = re.compile(r"\bAC[-\s]?(\d{1,3})\b", re.IGNORECASE)
ROUND_RE = re.compile(r"\b[Rr]ound[-\s]?(\d+)\b")
SECURITY_RE = re.compile(
    r"\b(auth|jwt|oauth|secret|credential|crypto|kms|iam|encrypt|decrypt|signing)\b",
    re.IGNORECASE,
)
API_RE = re.compile(r"\b(endpoint|rest|openapi|api/|/api|handler|route|sdk|contract)\b")
INFRA_RE = re.compile(r"\b(cdk|cloudformation|terraform|lambda|dynamodb|s3|vpc)\b")
PRIVACY_RE = re.compile(r"\b(pii|gdpr|consent|retention|personal data|anonymize|hipaa)\b")
REFACTOR_RE = re.compile(r"\b(refactor|dry|solid|complexity|technical debt|cleanup)\b")


def unique_sorted_ints(values: Iterable[str]) -> list[int]:
    return sorted({int(value) for value in values})


def extract(body: str) -> dict[str, object]:
    adrs = unique_sorted_ints(ADR_RE.findall(body))
    acceptance = unique_sorted_ints(AC_RE.findall(body))
    rounds = unique_sorted_ints(ROUND_RE.findall(body))
    lowered = body.lower()

    test_name_parts: list[str] = []
    if adrs:
        test_name_parts.append(f"ADR_{adrs[0]:03d}")
    if acceptance:
        test_name_parts.append(f"AC_{acceptance[0]}")

    test_naming_pattern = "test_<module>_<scenario>"
    if test_name_parts:
        test_naming_pattern = f"test_{'_'.join(test_name_parts)}_<scenario>"

    return {
        "adr_refs": [f"ADR-{number:04d}" for number in adrs],
        "ac_refs": [f"AC-{number}" for number in acceptance],
        "round_refs": rounds,
        "flags": {
            "has_security": bool(SECURITY_RE.search(body)),
            "has_api": bool(API_RE.search(lowered)),
            "has_infra": bool(INFRA_RE.search(lowered)),
            "has_privacy": bool(PRIVACY_RE.search(lowered)),
            "has_refactor": bool(REFACTOR_RE.search(lowered)),
        },
        "test_naming_pattern": test_naming_pattern,
        "first_line": body.splitlines()[0].strip()[:200] if body else "",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", default="-", help='Path to issue body, or "-" for stdin')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.body_file == "-":
        body = sys.stdin.read()
    else:
        body = Path(args.body_file).read_text(encoding="utf-8")
    print(json.dumps(extract(body), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
