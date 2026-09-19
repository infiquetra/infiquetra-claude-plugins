"""The named-verb registry (plan U5, requirement R14).

Each verb is declarative data -- its question set, criteria, policy text and
confidence floor -- not a code branch.  Adding a verb is a registry entry plus a
test, which is what makes "the policy lives in exactly one place" enforceable
rather than aspirational: the command-line tool builds its subcommands from this
mapping, so a verb that exists here and nowhere else still works, and a verb that
exists only in the tool reds the registry-completeness test.

Nothing here consumes the confidence floor yet.  The first consumer is the
staffing card (issue 1033); it is recorded here so every caller reads the same
number rather than inventing one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

TIER_POLICY = (
    "Tiering rule: judgment, design, architecture, root-cause investigation, or "
    "adversarial review -> opus. Mechanical or deterministic work (scaffolding, "
    "fixed transforms, mechanical edits, running commands) -> haiku. Read-only "
    "survey, search, sampling, summarising -> sonnet."
)


@dataclass(frozen=True)
class Verb:
    """One named judgment point."""

    name: str
    summary: str
    state_help: str
    questions: dict[str, Any] = field(default_factory=dict)
    confidence_floor: float = 0.6

    def question_set(self) -> dict[str, Any]:
        return {key: dict(value) for key, value in self.questions.items()}


def _noul(instructions: str, policy: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"type": "noul"}
    body["instructions"] = {"question": instructions, "policy": policy} if policy else instructions
    return body


def _choice(instructions: str, criteria: Mapping[str, str], policy: str | None = None) -> dict:
    body: dict[str, Any] = {"type": "choice", "criteria": dict(criteria)}
    body["instructions"] = {"question": instructions, "policy": policy} if policy else instructions
    return body


def _score(instructions: str, levels: Sequence[str]) -> dict[str, Any]:
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


VERBS: dict[str, Verb] = {
    "tier": Verb(
        name="tier",
        summary="Which model tier and effort should run a task",
        state_help='the task description, as {"task": "..."}',
        questions={
            "model": _choice(
                "Which model tier should run `task`?",
                {
                    "haiku": "cheapest; mechanical or deterministic work",
                    "sonnet": "mid; survey, search, summarising, moderate coding",
                    "opus": "most capable; judgment, design, adversarial review, root cause",
                },
                TIER_POLICY,
            ),
            "effort": _choice(
                "How much reasoning effort does `task` need?",
                {
                    "low": "obvious steps, little ambiguity",
                    "medium": "some judgment",
                    "high": "substantial ambiguity or many interacting constraints",
                    "max": "consequential architectural or strategic decision",
                },
            ),
        },
    ),
    "triage": Verb(
        name="triage",
        summary="What kind of issue a body describes",
        state_help='the issue body, as {"issue": "..."}',
        questions={
            "type": _choice(
                "Which issue type does `issue` describe?",
                {
                    "capability": "new user-facing capability that does not exist yet",
                    "enhancement": "improves something that already works",
                    "defect": "something is broken and must be repaired",
                    "exploration": "open question needing research before it can be planned",
                    "context-update": "documentation, prose, or instruction change",
                },
            ),
            "risk": _score("How risky is the change `issue` describes?", ["low", "medium", "high"]),
        },
    ),
    "lenses": Verb(
        name="lenses",
        summary="Which conditional review lenses a diff warrants",
        state_help='the diff and any guidance, as {"diff": "..."}',
        questions={
            "security": _noul("Does `diff` warrant a security review lens?"),
            "api_contract": _noul("Does `diff` change an API contract?"),
            "testing": _noul("Does `diff` warrant a test-coverage lens?"),
            "docs_clarity": _noul("Does `diff` warrant a documentation-clarity lens?"),
            "infra": _noul("Does `diff` touch infrastructure or deployment?"),
        },
    ),
    "bucket": Verb(
        name="bucket",
        summary="Which working bucket an item belongs in",
        state_help='the item, as {"item": "..."}',
        questions={
            "bucket": _choice(
                "Which bucket does `item` belong in?",
                {
                    "now": "actionable immediately",
                    "next": "actionable once something in flight lands",
                    "later": "worth keeping, not worth scheduling",
                    "drop": "no longer worth carrying",
                },
            )
        },
    ),
    "status": Verb(
        name="status",
        summary="What lifecycle status an item has reached",
        state_help='the item and its evidence, as {"item": "..."}',
        questions={
            "status": _choice(
                "What status has `item` reached?",
                {
                    "not-started": "no work has begun",
                    "in-progress": "work is underway",
                    "blocked": "work cannot proceed without something external",
                    "done": "the work is complete and evidenced",
                },
            )
        },
    ),
    "journal-route": Verb(
        name="journal-route",
        summary="Which engineering-journal file an entry belongs in",
        state_help='the candidate entry, as {"entry": "..."}',
        questions={
            "file": _choice(
                "Which journal file does `entry` belong in?",
                {
                    "LEARNINGS": "a non-obvious mechanism discovered by doing the work",
                    "DECISIONS": "a choice made, with alternatives rejected",
                    "QUEUED": "a follow-up not yet acted on",
                    "none": "not durable enough to record",
                },
            )
        },
    ),
    "preflight": Verb(
        name="preflight",
        summary="Whether a change is ready to run against a live system",
        state_help='the change and its checks, as {"change": "..."}',
        questions={
            "ready": _noul("Is `change` ready to run against a live system?"),
            "reversible": _noul("Can `change` be reversed without data loss?"),
        },
    ),
    "handoff-check": Verb(
        name="handoff-check",
        summary="Whether a handoff carries what its receiver needs",
        state_help='the handoff text, as {"handoff": "..."}',
        questions={
            "complete": _noul(
                "Does `handoff` carry everything its receiver needs to act without asking?"
            ),
            "names_evidence": _noul("Does `handoff` cite evidence rather than assert?"),
        },
    ),
    "roster-check": Verb(
        name="roster-check",
        summary="Whether a named agent or model still exists in the roster",
        state_help='the roster and the name, as {"roster": [...], "name": "..."}',
        questions={
            "present": _noul("Does `name` appear in `roster`?"),
        },
    ),
    "dedupe": Verb(
        name="dedupe",
        summary="Whether two findings or items are the same thing",
        state_help='the pair, as {"left": "...", "right": "..."}',
        questions={
            "same": _noul("Do `left` and `right` describe the same underlying thing?"),
        },
    ),
    "readiness": Verb(
        name="readiness",
        summary="Whether an idea is ready to be planned",
        state_help='the idea, as {"idea": "..."}',
        questions={
            "ready": _noul("Is `idea` settled enough to plan without more discovery?"),
            "scope_clear": _noul("Is the scope of `idea` unambiguous?"),
        },
    ),
}


def verb_names() -> tuple[str, ...]:
    return tuple(sorted(VERBS))


__all__: Sequence[str] = ("TIER_POLICY", "VERBS", "Verb", "verb_names")
