#!/usr/bin/env python3
"""Detect likely Infiquetra engineering-journal update targets."""

from __future__ import annotations

from collections.abc import Sequence

LEARNING_TERMS = {"surprise", "root cause", "mechanism", "validation", "gotcha"}
DECISION_TERMS = {"decision", "adopt", "choose", "reject", "revisit", "standard"}
QUEUED_TERMS = {"defer", "later", "future", "queue", "not now", "follow-up"}


def detect_targets(summary: str, changed_files: Sequence[str]) -> list[str]:
    """Return engineering-journal files likely needing updates."""

    text = " ".join([summary, *changed_files]).lower()
    targets: list[str] = []
    if any(term in text for term in LEARNING_TERMS):
        targets.append("docs/engineering-journal/LEARNINGS.md")
    if any(term in text for term in DECISION_TERMS):
        targets.append("docs/engineering-journal/DECISIONS.md")
    if any(term in text for term in QUEUED_TERMS):
        targets.append("docs/engineering-journal/QUEUED.md")
    return targets
