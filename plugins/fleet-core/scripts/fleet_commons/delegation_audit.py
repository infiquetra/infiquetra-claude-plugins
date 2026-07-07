"""Engine-parametrized delegation-transcript classifier + bundle corroborator (#384, U1).

Generalizes the scan at ``plugins/agy/scripts/agy_delegate.py:995-1021``
(``classify_transcript``) into a single algorithm driven by a per-engine config row, so the
same auditor covers both ``agy`` and ``codex`` bridges without a second hand-written scan.
agy's original ``classify_transcript`` is left byte-untouched (R7) — a fixture-parity test
(``tests/test_delegation_audit.py``) pins this module's ``classify(engine="agy")`` output to
``agy_delegate.classify_transcript``'s output on shared fixtures.

Three functions:

* ``classify(transcript_path, engine)`` — streams a JSONL transcript (8 MiB byte cap, KTD8) and
  returns an ``AuditClassification`` (``real`` / ``fallback_suspected`` vocabulary, plus
  per-line evidence and the two seen-flags).
* ``corroborate(engine, since_ts, root=None)`` — reads ``result.json`` launch flags and receipt
  presence under the engine's bundle root. Data contract only: no cross-plugin code import, and
  every error path (missing bundle root, corrupt JSON, unreadable file) degrades to an unproven
  result rather than raising.
* ``reconcile(classification, corroboration, self_report)`` — combines the transcript verdict,
  the bundle corroboration, and the engine's own self-report into ``real`` /
  ``fallback_suspected`` / ``delegation_integrity`` (KTD6: divergence between the two
  independent signals is named, never silently resolved).

Engine config rows live in ``ENGINE_CONFIGS`` below; adding a new subprocess-bridge engine means
adding one row, not a new algorithm.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# KTD8: Stop-hook cost bound — stream transcripts with a byte cap, never read_text a whole file.
TRANSCRIPT_BYTE_CAP = 8 * 1024 * 1024

CLAUDE_FILE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

REAL = "real"
FALLBACK_SUSPECTED = "fallback_suspected"
DELEGATION_INTEGRITY = "delegation_integrity"


@dataclass(frozen=True)
class EngineConfig:
    """One row of the engine-parametrization table."""

    name: str
    bundle_root: str
    launch_key: str
    # Codex writes a standalone ``bridge-receipt.json`` sibling; agy embeds the receipt inline
    # in ``result.json["receipt"]``. ``None`` means "check the embedded key instead".
    receipt_file: str | None = None


ENGINE_CONFIGS: dict[str, EngineConfig] = {
    "agy": EngineConfig(name="agy", bundle_root=".claude/agy/runs", launch_key="agy_launched"),
    "codex": EngineConfig(
        name="codex",
        bundle_root=".claude/codex/runs",
        launch_key="codex_launched",
        receipt_file="bridge-receipt.json",
    ),
}


class UnknownEngineError(ValueError):
    """Raised when ``classify``/``corroborate`` is asked about an unconfigured engine."""


def _engine_config(engine: str) -> EngineConfig:
    try:
        return ENGINE_CONFIGS[engine]
    except KeyError as exc:
        known = ", ".join(sorted(ENGINE_CONFIGS))
        raise UnknownEngineError(f"unknown engine {engine!r}; expected one of {{{known}}}") from exc


@dataclass(frozen=True)
class AuditClassification:
    engine: str
    classification: str
    command_seen: bool
    claude_file_tool_seen: bool
    evidence: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "classification": self.classification,
            "command_seen": self.command_seen,
            "claude_file_tool_seen": self.claude_file_tool_seen,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class BundleCorroboration:
    engine: str
    launched: bool
    receipt_present: bool
    statuses: list[str] = field(default_factory=list)
    run_dirs: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "launched": self.launched,
            "receipt_present": self.receipt_present,
            "statuses": list(self.statuses),
            "run_dirs": list(self.run_dirs),
            "problems": list(self.problems),
        }


def _iter_capped_lines(path: Path, *, byte_cap: int = TRANSCRIPT_BYTE_CAP):
    """Yield decoded lines from ``path`` without ever loading more than ``byte_cap`` bytes.

    Streams in fixed-size chunks; classification runs against the capped prefix rather than
    raising when a transcript exceeds the cap.
    """
    remaining = byte_cap
    buffer = b""
    with path.open("rb") as handle:
        while remaining > 0:
            chunk = handle.read(min(65536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            buffer += chunk
            lines = buffer.split(b"\n")
            buffer = lines.pop()
            for raw_line in lines:
                yield raw_line.decode("utf-8", errors="replace")
    if buffer:
        yield buffer.decode("utf-8", errors="replace")


def _event_tool_name(event: dict[str, Any]) -> str | None:
    """Mirrors ``agy_delegate._event_tool_name`` exactly (kept in lockstep for R7 parity)."""
    for key in ("tool_name", "name"):
        value = event.get(key)
        if isinstance(value, str):
            return value

    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name")
                    if isinstance(name, str):
                        return name
    return None


def _event_command(event: dict[str, Any]) -> str | None:
    """Mirrors ``agy_delegate._event_command`` exactly (kept in lockstep for R7 parity)."""
    for key in ("command", "cmd"):
        value = event.get(key)
        if isinstance(value, str):
            return value

    arguments = event.get("arguments") or event.get("input")
    if isinstance(arguments, dict):
        value = arguments.get("command")
        if isinstance(value, str):
            return value

    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                tool_input = item.get("input")
                if isinstance(tool_input, dict):
                    value = tool_input.get("command")
                    if isinstance(value, str):
                        return value
    return None


def _looks_like_engine_command(command: str, engine: str) -> bool:
    """Generalizes ``agy_delegate._looks_like_agy_command`` to any engine name.

    For ``engine="agy"`` this is byte-for-byte the same predicate as the original (same
    substring shapes, engine name substituted), which is what the R7 parity test pins.
    """
    command_lower = command.lower()
    return (
        f"plugins/{engine}/scripts/{engine}_delegate.py" in command_lower
        or f" --launch-{engine}" in command_lower
        or command_lower.startswith(f"{engine} ")
        or f" {engine} " in command_lower
        or command_lower.endswith(f"/{engine}")
        or f"/{engine} " in command_lower
    )


def classify(transcript_path: Path | str, engine: str) -> AuditClassification:
    """Classify a transcript as ``real`` or ``fallback_suspected`` for the given engine.

    Raises ``UnknownEngineError`` for an unconfigured engine. Never raises on transcript
    content: invalid-JSON lines are recorded as evidence and skipped; an empty transcript
    classifies ``fallback_suspected`` with empty evidence (no command was ever seen).
    """
    _engine_config(engine)  # validates + raises before touching the filesystem
    path = Path(transcript_path)

    evidence: list[str] = []
    command_seen = False
    claude_file_tool_seen = False

    for line_number, line in enumerate(_iter_capped_lines(path), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            evidence.append(f"line {line_number}: invalid json")
            continue
        if not isinstance(event, dict):
            continue

        tool_name = _event_tool_name(event)
        command = _event_command(event)
        if command and _looks_like_engine_command(command, engine):
            command_seen = True
            evidence.append(f"line {line_number}: {engine} command via {tool_name or 'unknown'}")
        if tool_name in CLAUDE_FILE_TOOLS:
            claude_file_tool_seen = True
            evidence.append(f"line {line_number}: Claude file tool {tool_name}")

    classification = REAL if command_seen and not claude_file_tool_seen else FALLBACK_SUSPECTED
    return AuditClassification(
        engine=engine,
        classification=classification,
        command_seen=command_seen,
        claude_file_tool_seen=claude_file_tool_seen,
        evidence=evidence,
    )


def corroborate(engine: str, since_ts: float | None, *, root: Path | str | None = None) -> BundleCorroboration:
    """Corroborate a delegation via bundle artifacts under the engine's bundle root.

    Data contract only (``result.json`` launch flag + receipt presence) — no cross-plugin code
    import. Every error path (missing bundle root, corrupt/missing ``result.json``, unreadable
    run directory) degrades to an unproven ``BundleCorroboration`` rather than raising; problems
    are recorded on the returned object for diagnostics.
    """
    config = _engine_config(engine)
    base = Path(root) if root is not None else Path.cwd()
    bundle_root = base / config.bundle_root

    problems: list[str] = []
    run_dirs: list[str] = []
    statuses: list[str] = []
    launched = False
    receipt_present = False

    if not bundle_root.is_dir():
        return BundleCorroboration(
            engine=engine,
            launched=False,
            receipt_present=False,
            statuses=[],
            run_dirs=[],
            problems=[f"bundle root not found: {bundle_root}"],
        )

    try:
        entries = sorted(bundle_root.iterdir())
    except OSError as exc:
        return BundleCorroboration(
            engine=engine,
            launched=False,
            receipt_present=False,
            statuses=[],
            run_dirs=[],
            problems=[f"could not list bundle root {bundle_root}: {exc}"],
        )

    for entry in entries:
        if not entry.is_dir():
            continue
        if since_ts is not None:
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                problems.append(f"{entry.name}: unreadable run directory")
                continue
            if mtime < since_ts:
                continue

        result_path = entry / "result.json"
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{entry.name}: missing/corrupt result.json ({exc})")
            continue
        if not isinstance(payload, dict):
            problems.append(f"{entry.name}: result.json is not an object")
            continue

        run_dirs.append(str(entry))
        status = payload.get("status")
        if isinstance(status, str):
            statuses.append(status)
        if payload.get(config.launch_key) is True:
            launched = True

        if config.receipt_file is not None:
            if (entry / config.receipt_file).is_file():
                receipt_present = True
        elif isinstance(payload.get("receipt"), dict):
            receipt_present = True

    return BundleCorroboration(
        engine=engine,
        launched=launched,
        receipt_present=receipt_present,
        statuses=statuses,
        run_dirs=run_dirs,
        problems=problems,
    )


def reconcile(
    classification: AuditClassification,
    corroboration: BundleCorroboration,
    self_report: Any,
) -> str:
    """Combine transcript verdict + bundle corroboration + engine self-report into one verdict.

    ``real`` — transcript shows a genuine engine command with no Claude file-tool fallback, and
    the observer (bundle) signal agrees with the engine's own self-report.
    ``fallback_suspected`` — the transcript classification alone already suspects fallback.
    ``delegation_integrity`` (KTD6) — the transcript classified ``real`` but the engine
    self-report and the observer (bundle) signal disagree about whether the run genuinely
    launched; this is a named divergence, never silently resolved in either direction.
    """
    if classification.classification == FALLBACK_SUSPECTED:
        return FALLBACK_SUSPECTED

    observer_says_launched = corroboration.launched and corroboration.receipt_present
    engine_says_ok = self_report in ("ok", "success", True) or (
        isinstance(self_report, str) and self_report.lower() in ("ok", "success", "real")
    )

    if engine_says_ok != observer_says_launched:
        return DELEGATION_INTEGRITY
    return REAL if observer_says_launched else FALLBACK_SUSPECTED
