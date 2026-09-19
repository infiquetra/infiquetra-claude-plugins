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


def _client() -> Any:
    """Load the client module for its answer accessors, the house way.

    The banding rule lives in exactly one place -- ``typesafe_client`` -- because
    a second copy here would silently change what the harness measures relative
    to what the verdict log records.  The client imports nothing at module scope
    beyond the standard library, so the offline guarantee is preserved.
    """
    try:
        import fleet_commons_shim

        return fleet_commons_shim.load("typesafe_client")
    except Exception:  # noqa: BLE001 - direct load for in-repo runs
        import importlib.util
        import sys as _sys

        name = "_fleet_commons_typesafe_client_for_eval"
        cached = _sys.modules.get(name)
        if cached is not None:
            return cached
        spec = importlib.util.spec_from_file_location(
            name, Path(__file__).with_name("typesafe_client.py")
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        module = importlib.util.module_from_spec(spec)
        _sys.modules[name] = module
        spec.loader.exec_module(module)
        return module


def _answer_value(answer: Mapping[str, Any]) -> Any:
    return _client().answer_value(answer)


def _answer_confidence(answer: Mapping[str, Any]) -> float | None:
    return _client().answer_confidence(answer)


def _hashable(value: Any) -> Any:
    """A hashable stand-in, so an unhashable label still compares for equality."""
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


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
            if isinstance(parsed, dict) and parsed.get("kind") == "override":
                # Read fine, simply not a verdict to score.  Counting it as
                # unreadable would report a corrupt log that is not corrupt.
                continue
            if isinstance(parsed, dict):
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

    # First pass: find identifiers carrying more than one distinct label, and
    # identifiers that simply repeat.  A duplicate scored twice inflates both
    # numerator and denominator, so the sample looks larger than it is; a
    # conflicting label scored once resolves the conflict by picking the first,
    # which is precisely what "reported, not resolved" rules out.
    labels_by_id: dict[str, list[Any]] = {}
    for record in records:
        identifier = str(record.get("id", ""))
        if identifier:
            labels_by_id.setdefault(identifier, []).append(record.get("label"))

    conflicted = {
        identifier
        for identifier, labels in labels_by_id.items()
        if len({_hashable(label) for label in labels}) > 1
    }
    report.conflicts.extend(sorted(conflicted))

    scored_ids: set[str] = set()
    for record in records:
        identifier = str(record.get("id", ""))
        label = record.get("label")

        if identifier and identifier in conflicted:
            continue
        if identifier and identifier in scored_ids:
            continue
        if identifier:
            scored_ids.add(identifier)

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
