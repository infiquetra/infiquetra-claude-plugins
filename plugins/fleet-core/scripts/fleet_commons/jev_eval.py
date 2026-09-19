"""The evaluation harness (plan U6).

Turns "the suggestion seems good" into agreement per confidence band, scored
against labels this repository owns.  It reads recorded answers -- never the
network -- so a run costs nothing and is reproducible.

Input format (requirement R18b): a JSON file whose top level is a list of
records, each carrying ``id``, ``state``, ``questions``, ``answer`` (the recorded
response), ``label`` (the known-correct value) and ``resolved_model``.  Answers
join to labels on ``id``, which is the same identifier the verdict log calls
``decision_id``, so the log itself is accepted as a second input format with no
conversion step.

Bands default to the literals in :data:`DEFAULT_BANDS` rather than a constant
buried in code, because a threshold nobody can see is a threshold nobody can
revise -- and the whole point of this harness is that thresholds come from
measurement rather than from a cookbook.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# (lower bound inclusive, upper bound exclusive, label)
DEFAULT_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.6, "low (<0.6)"),
    (0.6, 0.8, "medium (0.6-0.8)"),
    (0.8, 1.0001, "high (>=0.8)"),
)


class EvalInputError(RuntimeError):
    """The harness could not read what it was pointed at."""


@dataclass
class BandTally:
    band: str
    scored: int = 0
    agreed: int = 0

    @property
    def agreement(self) -> float | None:
        return (self.agreed / self.scored) if self.scored else None


@dataclass
class EvalReport:
    scored: int = 0
    agreed: int = 0
    unlabeled: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    skipped_lines: int = 0
    bands: list[BandTally] = field(default_factory=list)
    question_key: str = ""

    @property
    def agreement(self) -> float | None:
        return (self.agreed / self.scored) if self.scored else None

    def render(self) -> str:
        if not self.scored:
            lines = ["No records were scored."]
            if self.unlabeled:
                lines.append(f"{len(self.unlabeled)} record(s) carried no label.")
            if self.skipped_lines:
                lines.append(f"{self.skipped_lines} line(s) were unreadable and skipped.")
            return "\n".join(lines)

        lines = [f"Agreement: {self.agreed} of {self.scored}"]
        for tally in self.bands:
            if tally.scored:
                lines.append(
                    f"  {tally.band}: {tally.agreed} of {tally.scored} ({tally.agreement:.0%})"
                )
            else:
                lines.append(f"  {tally.band}: no records")
        if self.unlabeled:
            lines.append(
                f"Unscored (no label): {len(self.unlabeled)} -- "
                + ", ".join(sorted(self.unlabeled)[:10])
            )
        if self.conflicts:
            lines.append(
                f"Labeling conflicts: {len(self.conflicts)} -- "
                + ", ".join(sorted(self.conflicts)[:10])
            )
        if self.skipped_lines:
            lines.append(f"Unreadable lines skipped: {self.skipped_lines}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scored": self.scored,
            "agreed": self.agreed,
            "agreement": self.agreement,
            "unlabeled": self.unlabeled,
            "conflicts": self.conflicts,
            "skipped_lines": self.skipped_lines,
            "question_key": self.question_key,
            "bands": [
                {"band": t.band, "scored": t.scored, "agreed": t.agreed, "agreement": t.agreement}
                for t in self.bands
            ],
        }


def _answer_value(answer: Mapping[str, Any]) -> Any:
    kind = answer.get("type")
    if kind == "noul":
        return answer.get("noul")
    if kind == "choice":
        return answer.get("choice")
    if kind == "score":
        return answer.get("score")
    return None


def _answer_confidence(answer: Mapping[str, Any]) -> float | None:
    """A yes/no answer has no confidence field; its distance from 0.5 stands in."""
    if answer.get("type") == "noul":
        probability = answer.get("noul")
        if isinstance(probability, (int, float)):
            return abs(float(probability) - 0.5) * 2.0
        return None
    value = answer.get("confidence")
    return float(value) if isinstance(value, (int, float)) else None


def load_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read either input format: a JSON list, or the verdict log's JSON Lines."""
    if not path.exists():
        raise EvalInputError(f"no such evaluation input: {path}")

    if path.is_dir():
        candidates = sorted(path.glob("*_answers.json")) + sorted(path.glob("*.jsonl"))
        if not candidates:
            raise EvalInputError(
                f"{path} holds no recorded answers (looked for *_answers.json and *.jsonl). "
                "Seed the cache first -- see the plan's unit U6."
            )
        records: list[dict[str, Any]] = []
        skipped = 0
        for candidate in candidates:
            found, missed = load_records(candidate)
            records.extend(found)
            skipped += missed
        return records, skipped

    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        records = []
        skipped = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(parsed, dict) and parsed.get("kind") != "override":
                records.append(_from_verdict(parsed))
            else:
                skipped += 1
        return records, skipped

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvalInputError(f"{path} is not valid JSON: {exc}") from None
    if not isinstance(parsed, list):
        raise EvalInputError(f"{path} must hold a list of records at its top level")
    return [r for r in parsed if isinstance(r, dict)], 0


def _from_verdict(record: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt a verdict-log line onto the record shape, joining on decision_id."""
    return {
        "id": record.get("decision_id", ""),
        "answer": record.get("answer", {}),
        "label": record.get("label"),
        "resolved_model": record.get("resolved_model", ""),
    }


def evaluate(
    records: Sequence[Mapping[str, Any]],
    *,
    question_key: str | None = None,
    bands: Sequence[tuple[float, float, str]] = DEFAULT_BANDS,
    skipped_lines: int = 0,
) -> EvalReport:
    """Score recorded answers against labels, overall and per confidence band."""
    report = EvalReport(
        skipped_lines=skipped_lines,
        bands=[BandTally(band=name) for _, _, name in bands],
        question_key=question_key or "",
    )

    seen_labels: dict[str, Any] = {}
    for record in records:
        identifier = str(record.get("id", ""))
        label = record.get("label")

        if identifier and identifier in seen_labels and seen_labels[identifier] != label:
            report.conflicts.append(identifier)
            continue
        if identifier:
            seen_labels[identifier] = label

        if label is None:
            report.unlabeled.append(identifier or "<unidentified>")
            continue

        answer = record.get("answer")
        if not isinstance(answer, Mapping):
            report.unlabeled.append(identifier or "<unidentified>")
            continue

        # Which question this record's label scores.  The flag wins; otherwise the
        # record names its own, so the bare `jev eval --cached <dir>` in the card's
        # acceptance criterion works without the caller knowing the question set.
        key = question_key or record.get("question_key")
        if key:
            nested = answer.get(key)
            answer = nested if isinstance(nested, Mapping) else {}
            if not answer:
                report.unlabeled.append(identifier or "<unidentified>")
                continue

        value = _answer_value(answer)
        agreed = value == label
        report.scored += 1
        report.agreed += int(agreed)

        confidence = _answer_confidence(answer)
        if confidence is not None:
            for tally, (low, high, _name) in zip(report.bands, bands, strict=False):
                if low <= confidence < high:
                    tally.scored += 1
                    tally.agreed += int(agreed)
                    break

    return report


def evaluate_path(
    path: Path,
    *,
    question_key: str | None = None,
    bands: Sequence[tuple[float, float, str]] = DEFAULT_BANDS,
) -> EvalReport:
    records, skipped = load_records(path)
    return evaluate(records, question_key=question_key, bands=bands, skipped_lines=skipped)


__all__: Sequence[str] = (
    "DEFAULT_BANDS",
    "BandTally",
    "EvalInputError",
    "EvalReport",
    "evaluate",
    "evaluate_path",
    "load_records",
)
