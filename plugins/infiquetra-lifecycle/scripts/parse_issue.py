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
H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
HANDOFF_MATURITY_VALUES = {
    "idea-ready",
    "requirements-ready",
    "plan-ready",
    "resume-ready",
    "deferred-context",
}


def unique_sorted_ints(values: Iterable[str]) -> list[int]:
    return sorted({int(value) for value in values})


def split_h3_sections(body: str) -> dict[str, str]:
    matches = list(H3_RE.finditer(body))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[header] = body[start:end].strip()
    return sections


def first_content_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().strip("`")
        if stripped:
            return stripped
    return ""


def parse_source_context(text: str) -> dict[str, str]:
    context: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped[2:].split(":", 1)
        context[key.strip().lower().replace(" ", "_")] = value.strip()
    return context


def extract_handoff(body: str) -> dict[str, object]:
    sections = split_h3_sections(body)
    maturity = first_content_line(sections.get("Handoff maturity", ""))
    if maturity not in HANDOFF_MATURITY_VALUES:
        maturity = ""
    source_context = parse_source_context(sections.get("Source context", ""))
    return {
        "maturity": maturity,
        "suggested_next_action": first_content_line(sections.get("Suggested next action", "")),
        "source": source_context.get("source", ""),
        "source_type": source_context.get("source_type", ""),
        "source_title": source_context.get("source_title", ""),
        "can_plan": maturity in {"idea-ready", "requirements-ready"},
        "can_work": maturity in {"plan-ready", "resume-ready"},
        "requires_clarification": maturity == "deferred-context",
    }


def extract(body: str) -> dict[str, object]:
    adrs = unique_sorted_ints(ADR_RE.findall(body))
    acceptance = unique_sorted_ints(AC_RE.findall(body))
    rounds = unique_sorted_ints(ROUND_RE.findall(body))
    lowered = body.lower()
    handoff = extract_handoff(body)

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
        "handoff": handoff,
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
