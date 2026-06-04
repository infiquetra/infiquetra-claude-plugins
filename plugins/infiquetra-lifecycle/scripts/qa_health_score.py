#!/usr/bin/env python3
"""Deterministic QA health score for the /qa acceptance-evidence gate.

This is a faithful PORT of gstack's "Health Score Rubric"
(gstack/scripts/resolvers/utility.ts:286-321). The per-finding DEDUCTION values are
gstack's verbatim:

    critical -25, high -15, medium -8, low -3   (each, with a per-class floor of 0)

DELIBERATE ADAPTATION — the class weights are NOT gstack's. gstack weights its WEB
categories (Console 15 / Links 10 / Visual 10 / Functional 20 / UX 15 / Performance 10 /
Content 5 / Accessibility 15), which do not map onto infiquetra work (most of which is
serverless / SDK / Ansible / plugin code with no browser surface). We replace them with
documented infiquetra 9-way SHIP-RISK-class weights, ranked by blast radius if a finding
ships:

    behavior 20, security 20, data 15, api 15, deployment 10, infra 10,
    config 5, docs 3, trivial 2

The overall score is the weighted average of per-class scores, with the weights
RE-NORMALIZED over only the in-scope classes (a class absent from the findings input is
N/A and excluded; a class present with an empty severity map is checked-but-clean and
scores 100). Empty input is vacuously healthy (100).

HONEST CAVEAT: the per-class severity counts fed in here are LLM-assigned by /qa, so the
0-100 number is one *signal*, not the gate decision. The severity-banded ship verdict
remains the decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ported verbatim from gstack utility.ts:300-305 (per-finding deduction, floor 0).
DEDUCTIONS: dict[str, int] = {"critical": 25, "high": 15, "medium": 8, "low": 3}

# infiquetra ship-risk class weights — a DELIBERATE adaptation of gstack's web-category
# weights (see module docstring), ranked by ship blast radius.
CLASS_WEIGHTS: dict[str, int] = {
    "behavior": 20,
    "security": 20,
    "data": 15,
    "api": 15,
    "deployment": 10,
    "infra": 10,
    "config": 5,
    "docs": 3,
    "trivial": 2,
}


def class_score(severity_counts: dict[str, int]) -> int:
    """Score one risk class: 100 minus the summed per-finding deductions, floored at 0."""
    deducted = sum(DEDUCTIONS[sev] * count for sev, count in severity_counts.items())
    return max(0, 100 - deducted)


def score_findings(
    findings: dict[str, dict[str, int]],
    baseline: int | None = None,
) -> dict[str, object]:
    """Compute per-class scores + the re-normalized weighted overall.

    in-scope = the classes present as keys in ``findings`` (an empty severity map still
    counts as in-scope and scores 100). Overall re-normalizes CLASS_WEIGHTS over the
    in-scope classes only; empty input is vacuously healthy (100).
    """
    in_scope = list(findings.keys())
    per_class = {cls: class_score(findings[cls]) for cls in in_scope}

    weight_sum = sum(CLASS_WEIGHTS[cls] for cls in in_scope)
    if weight_sum == 0:
        overall = 100
    else:
        weighted = sum(per_class[cls] * CLASS_WEIGHTS[cls] for cls in in_scope)
        overall = round(weighted / weight_sum)

    delta = overall - baseline if baseline is not None else None
    return {
        "per_class": per_class,
        "overall": overall,
        "in_scope": in_scope,
        "baseline": baseline,
        "delta": delta,
    }


def _load_findings(raw: str) -> dict[str, dict[str, int]]:
    """Accept a file path OR an inline JSON string for --findings-json."""
    candidate = Path(raw)
    text = candidate.read_text(encoding="utf-8") if candidate.is_file() else raw
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("--findings-json must be a JSON object of {class: {severity: count}}")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--findings-json",
        required=True,
        help='File path OR inline JSON, shape {"behavior": {"critical": 1}, "api": {}}.',
    )
    parser.add_argument(
        "--baseline-score",
        type=int,
        default=None,
        help="Prior run's overall score; emits delta = overall - baseline.",
    )
    args = parser.parse_args(argv)

    findings = _load_findings(args.findings_json)
    result = score_findings(findings, baseline=args.baseline_score)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
