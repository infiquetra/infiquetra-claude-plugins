#!/usr/bin/env python3
"""Gate-divergence reader: per-gate rubber-stamp rate (issue #399).

Generalizes ``override_rate_reader.py``'s R12 reader shape from one gate
(orchestration-backend choice) to the fleet's interactive decision gates broadly, without
modifying that reader or its consumption in ``/retro`` Phase 1.6
(docs/plans/2026-07-04-gate-divergence-telemetry-plan.md).

Scans all saga envelopes and, for every ``gate_id`` seen in any recorded ``gate_divergence``
entry, reports:

* **rubber_stamp_rate** — ``1 - divergence_rate`` for that gate id (fraction of interactions
  where the operator's answer matched the offered default/recommendation).
* **interaction_count** — how many recorded interactions back that rate.
* **mean_latency_seconds** — average of the entries' non-null ``latency_seconds`` values, or
  ``None`` if no entry recorded a latency.

Zero-data contract (no sagas / no recorded ``gate_divergence`` entries for a gate id):
  A gate id with zero recorded interactions is reported as ``"no data yet"`` (``rate=None``),
  never a fabricated ``0%`` — same discipline as ``override_rate_reader.py``.

Unlike ``override_rate_reader.py`` (which reads a lightweight frontmatter line parser, since it
only needs single-line scalar fields), this reader imports ``saga.py``'s ``parse_envelope`` and
``parse_gate_divergence_entry`` directly: ``gate_divergence`` is a full-snapshot YAML list field
(multi-line) whose entries are base64-wrapped JSON (KTD1), which a simple line-based parser
cannot decode correctly.

CLI::

    python3 gate_divergence_reader.py [--root <path>]
    python3 gate_divergence_reader.py [--root <path>] --json

Pure functions + injectable ``root`` follow the ``saga.py`` house pattern so offline tests never
touch the real filesystem. Read-only: never writes to the saga store or filesystem it scans.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saga as _saga_engine  # noqa: E402

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateInteraction:
    """One recorded gate-divergence interaction, tagged with its source saga."""

    saga_id: str
    gate_id: str
    offered: str
    answer: str
    divergence: bool
    latency_seconds: float | int | None


@dataclass(frozen=True)
class GateSummary:
    """Per-gate-id rubber-stamp summary. ``rubber_stamp_rate`` is ``None`` when
    ``interaction_count`` is 0 (zero-data contract)."""

    gate_id: str
    interaction_count: int
    divergence_count: int
    latencies: tuple[float, ...]

    @property
    def rubber_stamp_rate(self) -> float | None:
        if self.interaction_count == 0:
            return None
        return 1 - (self.divergence_count / self.interaction_count)

    @property
    def mean_latency_seconds(self) -> float | None:
        if not self.latencies:
            return None
        return sum(self.latencies) / len(self.latencies)

    def as_dict(self) -> dict[str, Any]:
        rate = self.rubber_stamp_rate
        return {
            "gate_id": self.gate_id,
            "interaction_count": self.interaction_count,
            "rubber_stamp_rate": rate,
            "rubber_stamp_rate_display": ("no data yet" if rate is None else f"{rate:.0%}"),
            "mean_latency_seconds": self.mean_latency_seconds,
        }


# ---------------------------------------------------------------------------
# Saga envelope scan (reuses saga.py's real parser — full-snapshot list fields
# and base64+JSON gate_divergence entries need more than a line-based parser)
# ---------------------------------------------------------------------------

_SAGAS_DIR = Path(".claude/saga/sagas")


def _all_latest_envelopes(root: Path) -> list[Path]:
    """Return the newest envelope file for every saga directory under *root*.

    Uses filename ordering (same lexicographic contract as ``saga.py`` and
    ``override_rate_reader.py``) — mtime is never consulted.
    """
    sagas_dir = root / _SAGAS_DIR
    if not sagas_dir.is_dir():
        return []
    envelopes: list[Path] = []
    for saga_dir in sagas_dir.iterdir():
        if not saga_dir.is_dir():
            continue
        candidates = [p for p in saga_dir.iterdir() if p.is_file() and p.suffix == ".md"]
        if not candidates:
            continue
        envelopes.append(max(candidates, key=lambda p: p.name))
    return envelopes


def _read_interactions(root: Path) -> list[GateInteraction]:
    """Scan all saga envelopes under *root* and return every recorded interaction.

    Malformed ``gate_divergence`` entries (bad base64/JSON/missing keys) are skipped rather
    than raising — a single corrupt tick must not take down the whole reader.
    """
    interactions: list[GateInteraction] = []
    for env_path in _all_latest_envelopes(root):
        try:
            text = env_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            envelope = _saga_engine.parse_envelope(text)
        except Exception:  # noqa: BLE001 -- a corrupt/foreign envelope must not crash the
            # reporting reader; skip it and let other envelopes still contribute (matches
            # override_rate_reader.py's read_override_rate, which silently skips an OSError
            # per-envelope for the same reason).
            continue
        entries = envelope.gate_divergence
        if isinstance(entries, _saga_engine._Absent):
            continue
        for raw_entry in entries:
            try:
                parsed = _saga_engine.parse_gate_divergence_entry(raw_entry)
            except ValueError:
                continue
            interactions.append(
                GateInteraction(
                    saga_id=envelope.saga_id,
                    gate_id=parsed["gate_id"],
                    offered=parsed["offered"],
                    answer=parsed["answer"],
                    divergence=bool(parsed["divergence"]),
                    latency_seconds=parsed.get("latency_seconds"),
                )
            )
    return interactions


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------


def read_gate_divergence(root: Path) -> dict[str, GateSummary]:
    """Scan all saga envelopes under *root* and return per-gate-id summaries.

    Returns an empty dict when no ``gate_divergence`` entries exist anywhere (zero-data
    contract — callers must render "no data yet" rather than iterate zero gates as "0%").
    """
    interactions = _read_interactions(root)
    by_gate: dict[str, list[GateInteraction]] = {}
    for interaction in interactions:
        by_gate.setdefault(interaction.gate_id, []).append(interaction)

    summaries: dict[str, GateSummary] = {}
    for gate_id, records in by_gate.items():
        divergence_count = sum(1 for r in records if r.divergence)
        latencies = tuple(
            float(r.latency_seconds) for r in records if r.latency_seconds is not None
        )
        summaries[gate_id] = GateSummary(
            gate_id=gate_id,
            interaction_count=len(records),
            divergence_count=divergence_count,
            latencies=latencies,
        )
    return summaries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _render_text(summaries: dict[str, GateSummary]) -> str:
    if not summaries:
        return "gate_divergence: no data yet (no recorded interactions across any saga)"
    lines = ["Gate-divergence rubber-stamp rates:"]
    for gate_id in sorted(summaries):
        d = summaries[gate_id].as_dict()
        latency = (
            "no data yet"
            if d["mean_latency_seconds"] is None
            else f"{d['mean_latency_seconds']:.1f}s avg"
        )
        lines.append(
            f"  {gate_id}: {d['rubber_stamp_rate_display']} rubber-stamp "
            f"({d['interaction_count']} interactions, {latency})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repo root to scan (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    root = Path(args.root)
    summaries = read_gate_divergence(root)

    if args.json:
        print(json.dumps({gid: s.as_dict() for gid, s in summaries.items()}, indent=2))
    else:
        print(_render_text(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
