#!/usr/bin/env python3
"""Unified Infiquetra-lifecycle saga engine.

A *saga* is the durable, resumable work-state envelope for a single thread of
lifecycle work (one issue or one ad-hoc task). It is the spine the four
execution-loop commands (``/work``, ``/resume``, ``/loop``, ``/plan``) read and
write against once they are rebuilt; this module is that engine.

Storage (under git-ignored ``.claude/saga/``)::

    sagas/
      issue-42/                  # one dir per derived saga_id
        20260602-140510.md       # tick 1 (append-only, immutable)
        20260602-141233.md       # tick 2 — newest FILENAME = current state
    state.json                   # DERIVED index (rebuildable from scan)
    checkpoints/                 # LEGACY pre-0.4.0 — scan reads as fallback

Canonical ordering is ALWAYS by filename string, never ``mtime`` — so that
rsync / backup / snapshot-restore preserve order deterministically. The
``state.json`` index is derived and best-effort: a corrupt index is never
fatal because ``scan`` rebuilds the picture from the envelope log.

House testability pattern (mirrors ``handoff_envelope.py``): every filesystem
function takes ``root: Path`` as its first argument, and ``now`` / ``runner``
are injectable so offline tests are deterministic and never shell out.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess  # nosec B404
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
STATE_DIR = Path(".claude/saga")
_LEGACY_STATE_DIR = Path(".claude/infiquetra-lifecycle")


def _migrate_legacy_state_dir() -> None:
    """One-time: the plugin was renamed infiquetra-lifecycle -> saga (0.19.0). Move pre-existing state."""
    if _LEGACY_STATE_DIR.exists() and not STATE_DIR.exists():
        with contextlib.suppress(OSError):
            _LEGACY_STATE_DIR.rename(STATE_DIR)


SAGAS_DIR = STATE_DIR / "sagas"
LEGACY_CHECKPOINT_DIR = STATE_DIR / "checkpoints"

ENVELOPE_RE = re.compile(r"^(?P<ts>\d{8}-\d{6})(?:-(?P<seq>\d+))?\.md$")
ROUND_RE = re.compile(r"round-(\d+)", re.IGNORECASE)
LEGACY_CHECKPOINT_RE = re.compile(
    r"^(?P<kind>issue|task)-(?P<id>[a-zA-Z0-9_-]+?)"
    r"(?:-round-(?P<round>\d+))?"
    r"-phase(?P<phase>\d+)(?:-(?P<status>complete|pending|in_progress))?\.md$"
)

# Enum domains (the spec states each axis as a MUST).
LIFECYCLE_PHASES = ("ideation", "brainstorm", "plan", "review", "work", "qa", "retro")
PHASE_STATUSES = ("pending", "in_progress", "complete")
STATUSES = ("active", "blocked", "paused", "handed-off", "done", "abandoned")
DESTINATIONS = ("plan-only", "pr", "merge", "nonprod-deploy")
ORCHESTRATION_MODES = ("inline", "team-execution", "cc-workflows-ultracode")

# Display-label map (R8 / KTD5).  Maps the stored enum string to the human-readable
# label surfaced in every offer.  The enum values in ORCHESTRATION_MODES are the
# frozen wire contract (carried in persisted sagas and CLI --orchestration-mode);
# this map is additive and never changes their meaning.  A key miss falls back to
# the raw enum string — never errors.
ORCHESTRATION_MODE_LABELS: dict[str, str] = {
    "cc-workflows-ultracode": "dynamic workflows",
    "team-execution": "team execution",
    "inline": "inline",
}


def display_orchestration_mode(mode: str) -> str:
    """Return the human-readable label for *mode*; fall back to the raw string on a miss."""
    return ORCHESTRATION_MODE_LABELS.get(mode, mode)


# maturity is DERIVED at /handoff time from lifecycle_phase — never stored and never
# surfaced by the generic engine (restore/scan). This is the contract mapping the future
# /handoff rebuild imports; see references/saga-spec.md §3.3.
PHASE_TO_MATURITY = {
    "ideation": "idea-ready",
    "brainstorm": "requirements-ready",
    "plan": "plan-ready",
    "review": "plan-ready",
    "work": "resume-ready",
    "qa": "resume-ready",
    "retro": "resume-ready",
}


class _Absent:
    """Sentinel for a list field the caller did not supply.

    Full-snapshot list semantics need three distinguishable states:
    ``ABSENT`` (carry the prior tick's list forward), ``[]`` (explicitly
    clear), and a populated list (replace). A bare default of ``[]`` cannot
    tell "carry forward" from "clear", so ``save`` defaults list fields to this
    sentinel. A persisted/parsed envelope always holds a concrete list (a
    stored tick is a full snapshot), never ``ABSENT``.
    """

    _instance: _Absent | None = None

    def __new__(cls) -> _Absent:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return "ABSENT"

    def __bool__(self) -> bool:
        return False


ABSENT = _Absent()
ListOrAbsent = list[Any] | _Absent


# ---------------------------------------------------------------------------
# Saga dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Saga:
    """One thread of lifecycle work. Frozen — ``save`` derives a new instance.

    ``extra`` preserves any unknown frontmatter keys read off disk so a
    round-trip (parse -> render) never drops a field a newer writer added.
    List fields use full-snapshot semantics at ``save`` time (a tick's list
    REPLACES the prior tick's). They default to the ``ABSENT`` sentinel so
    ``save`` can tell "carry forward" (``ABSENT``) from "clear" (``[]``); a
    persisted/parsed envelope always carries concrete lists, never ``ABSENT``.
    """

    # Identity (sticky, derived at birth).
    saga_id: str
    kind: str  # issue | task
    id: str  # issue number (as str) or task slug
    schema_version: str = SCHEMA_VERSION

    # Timestamps.
    created_at: str = ""
    updated_at: str = ""

    # The three stored state axes (one derived: maturity, not stored).
    lifecycle_phase: str = "ideation"  # CE-flow position
    phase_status: str = "pending"  # pending | in_progress | complete
    status: str = "active"  # active|blocked|paused|handed-off|done|abandoned

    # Resume anchor + orchestration.
    next_step: str = ""
    orchestration_mode: str = "inline"
    orchestration_ref: str = ""
    # Choice-vs-recommendation recording (R12 — enables override-rate computation in /retro+/optimize).
    # orchestration_recommended = what the recommender suggested;
    # orchestration_operator_choice = what the operator actually picked.
    # Either can differ from orchestration_mode when the operator overrides the recommendation.
    # Both default to "" so older sagas that lack these fields still parse without error.
    orchestration_recommended: str = ""
    orchestration_operator_choice: str = ""

    # Pointers (link, never duplicate, another owner's state).
    issue_ref: str = ""  # owner/repo#N (empty for plan-only)
    destination: str = "plan-only"  # plan-only|pr|merge|nonprod-deploy

    # Round / phase / progress.
    round: int = 0
    phase: int = 0
    progress_pct: int = 0

    # Artifact pointers.
    plan_path: str = ""
    work_session_paths: ListOrAbsent = ABSENT
    review_paths: ListOrAbsent = ABSENT
    qa_paths: ListOrAbsent = ABSENT

    # Git snapshot (cached for offline display; never the authority).
    branch: str = ""
    head_sha: str = ""
    last_commit_sha: str = ""
    files_modified: ListOrAbsent = ABSENT

    # Round history.
    rounds_seen: ListOrAbsent = ABSENT
    next_round: int = 1

    # Cross-owner pointers.
    pr_refs: ListOrAbsent = ABSENT
    adr_refs: ListOrAbsent = ABSENT
    journal_refs: ListOrAbsent = ABSENT

    # Disposition detail.
    blockers: str = ""
    open_questions: ListOrAbsent = ABSENT
    checks_run: ListOrAbsent = ABSENT
    source: str = ""

    # Body sections (free-form prose).
    summary: str = ""
    decisions: str = ""
    remaining: str = ""
    notes: str = ""

    # Unknown-key round-trip preservation.
    extra: dict[str, Any] = field(default_factory=dict)


# Frontmatter machine fields, in stable render order. Body sections (summary,
# decisions, remaining, notes) and ``extra`` are handled separately.
FRONTMATTER_FIELDS: tuple[str, ...] = (
    "schema_version",
    "saga_id",
    "kind",
    "id",
    "created_at",
    "updated_at",
    "lifecycle_phase",
    "phase_status",
    "status",
    "next_step",
    "orchestration_mode",
    "orchestration_ref",
    "orchestration_recommended",
    "orchestration_operator_choice",
    "issue_ref",
    "destination",
    "round",
    "phase",
    "progress_pct",
    "plan_path",
    "work_session_paths",
    "review_paths",
    "qa_paths",
    "branch",
    "head_sha",
    "last_commit_sha",
    "files_modified",
    "rounds_seen",
    "next_round",
    "pr_refs",
    "adr_refs",
    "journal_refs",
    "blockers",
    "open_questions",
    "checks_run",
    "source",
)

_BODY_FIELDS = ("summary", "decisions", "remaining", "notes")
_LIST_FIELDS = {
    "work_session_paths",
    "review_paths",
    "qa_paths",
    "files_modified",
    "rounds_seen",
    "pr_refs",
    "adr_refs",
    "journal_refs",
    "open_questions",
    "checks_run",
}


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    """Lowercase, hyphen-join alphanumeric runs (stable, filesystem-safe)."""
    parts = re.findall(r"[a-z0-9]+", value.lower())
    return "-".join(parts) or "saga"


def derive_saga_id(kind: str, id_: str) -> str:
    """Mint the sticky, human-legible saga id: ``issue-<N>`` / ``task-<slug>``.

    Issue ids keep their number verbatim; task ids are slugified for a stable,
    filesystem-safe directory name. The id is derived from ``kind`` + ``id``
    only — ``round`` / ``phase`` are FIELDS, never part of identity.
    """
    if kind == "issue":
        return f"issue-{str(id_).strip()}"
    return f"task-{slugify(str(id_))}"


# ---------------------------------------------------------------------------
# Envelope render / parse (round-trip preserves extra)
# ---------------------------------------------------------------------------


def _yaml_scalar(value: Any) -> str:
    """Render a scalar for frontmatter; double-quote strings that need it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = "" if value is None else str(value)
    if text == "":
        return '""'
    needs_quote = (
        text != text.strip()
        or text[0] in "!&*?|>%@`\"'#-[]{},:"
        or ": " in text
        or text.endswith(":")
        or "\n" in text
        or text.lower() in {"null", "true", "false", "yes", "no", "~"}
    )
    if needs_quote:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _render_value(key: str, value: Any) -> str:
    if isinstance(value, _Absent):
        value = []
    if isinstance(value, list):
        if not value:
            return f"{key}: []"
        lines = [f"{key}:"]
        lines.extend(f"  - {_yaml_scalar(item)}" for item in value)
        return "\n".join(lines)
    return f"{key}: {_yaml_scalar(value)}"


def render_envelope(saga: Saga) -> str:
    """Render a saga to a gstack-style frontmatter + body envelope (str)."""
    lines: list[str] = ["---"]
    for key in FRONTMATTER_FIELDS:
        lines.append(_render_value(key, getattr(saga, key)))
    for key in sorted(saga.extra):
        lines.append(_render_value(key, saga.extra[key]))
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(saga.summary.strip())
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    lines.append(saga.decisions.strip())
    lines.append("")
    lines.append("## Remaining")
    lines.append("")
    lines.append(saga.remaining.strip())
    lines.append("")
    lines.append("## Notes / Tried")
    lines.append("")
    lines.append(saga.notes.strip())
    lines.append("")
    return "\n".join(lines)


def _coerce(name: str, raw: Any) -> Any:
    """Coerce a parsed frontmatter value to the dataclass field's type."""
    if name in _LIST_FIELDS:
        if raw is None:
            return []
        if isinstance(raw, list):
            if name == "rounds_seen":
                return [int(item) for item in raw]
            return [str(item) for item in raw]
        return [raw]
    if name in {"round", "phase", "progress_pct", "next_round"}:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return "" if raw is None else str(raw)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body) splitting on the leading ``---`` fence."""
    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        return "", text
    rest = stripped[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end == -1:
        return "", text
    front = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return front, body


def _parse_frontmatter(block: str) -> dict[str, Any]:
    """Parse a minimal YAML frontmatter block (scalars + ``- `` lists)."""
    parsed: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith(("  - ", "- ")) and current_key is not None:
            item = raw_line.split("- ", 1)[1].strip()
            existing = parsed.setdefault(current_key, [])
            if isinstance(existing, list):
                existing.append(_unquote(item))
            continue
        if ":" not in raw_line:
            continue
        key, _, value = raw_line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            parsed[key] = []
            current_key = key
        elif value == "[]":
            parsed[key] = []
            current_key = None
        else:
            parsed[key] = _unquote(value)
            current_key = None
    return parsed


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BODY_KEY_BY_HEADING = {
    "summary": "summary",
    "decisions": "decisions",
    "remaining": "remaining",
    "notes / tried": "notes",
    "notes": "notes",
}


def _parse_body(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for index, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        key = _BODY_KEY_BY_HEADING.get(heading)
        if key is None:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[key] = body[start:end].strip()
    return sections


def parse_envelope(text: str) -> Saga:
    """Parse an envelope back into a ``Saga``, preserving unknown keys in ``extra``."""
    front_block, body = _split_frontmatter(text)
    front = _parse_frontmatter(front_block)
    body_sections = _parse_body(body)

    known = {f.name for f in fields(Saga)}
    kwargs: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, value in front.items():
        if key in known and key not in _BODY_FIELDS and key != "extra":
            kwargs[key] = _coerce(key, value)
        else:
            extra[key] = value

    kwargs.setdefault("saga_id", str(front.get("saga_id", "")))
    kwargs.setdefault("kind", str(front.get("kind", "")))
    kwargs.setdefault("id", str(front.get("id", "")))
    for body_key in _BODY_FIELDS:
        kwargs[body_key] = body_sections.get(body_key, "")
    kwargs["extra"] = extra
    return Saga(**kwargs)


# ---------------------------------------------------------------------------
# Git snapshot (guarded; empty strings on any failure)
# ---------------------------------------------------------------------------


def current_git_state(root: Path, *, runner: Callable[..., Any] = subprocess.run) -> dict[str, str]:
    """Best-effort git snapshot. Returns empty strings if git is unavailable."""

    def run(args: list[str]) -> str:
        try:
            result = runner(  # nosec B603
                args, cwd=root, capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if getattr(result, "returncode", 1) != 0:
            return ""
        return (result.stdout or "").strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "head": run(["git", "rev-parse", "--short", "HEAD"]),
        "last_commit": run(["git", "rev-parse", "HEAD"]),
    }


# ---------------------------------------------------------------------------
# save / update_index
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp(now: datetime) -> str:
    return now.strftime("%Y%m%d-%H%M%S")


def _next_phase(phase: int, phase_status: str) -> int:
    return phase + 1 if phase_status == "complete" else phase


def _materialize(value: ListOrAbsent) -> list[Any]:
    """Resolve a list-or-ABSENT field to a concrete list (ABSENT -> [])."""
    return [] if isinstance(value, _Absent) else list(value)


def _merge(prior: Saga | None, incoming: Saga, now: datetime) -> Saga:
    """Full-snapshot merge: lists in ``incoming`` REPLACE prior; ABSENT carries forward.

    Scalar fields left at their dataclass default carry forward from the prior
    tick. List fields never union: an incoming populated list replaces, ``[]``
    clears, and the ``ABSENT`` sentinel carries the prior tick's list forward.
    The persisted result always holds concrete lists (never ``ABSENT``).
    """
    created = prior.created_at if prior and prior.created_at else (incoming.created_at or "")
    if not created:
        created = now.isoformat()

    data: dict[str, Any] = {}
    defaults = {f.name: f.default for f in fields(Saga)}
    for f in fields(Saga):
        name = f.name
        inc_value = getattr(incoming, name)
        if name == "extra":
            merged_extra = dict(prior.extra) if prior else {}
            merged_extra.update(inc_value)
            data[name] = merged_extra
            continue
        if name in _LIST_FIELDS:
            if isinstance(inc_value, _Absent):
                # Carry the prior tick's list forward (or [] for a new saga).
                data[name] = _materialize(getattr(prior, name)) if prior else []
            else:
                # Snapshot-replace: populated list replaces, [] clears.
                data[name] = list(inc_value)
            continue
        if prior is None:
            data[name] = inc_value
            continue
        # Scalar carry-forward: if incoming left the default, inherit prior.
        if inc_value == defaults.get(name):
            data[name] = getattr(prior, name)
        else:
            data[name] = inc_value

    data["created_at"] = created
    data["updated_at"] = now.isoformat()
    rounds = data["rounds_seen"]
    data["next_round"] = (max(rounds) + 1) if rounds else 1
    return Saga(**data)


def _allocate_envelope_path(saga_dir: Path, timestamp: str) -> Path:
    """Pick a non-colliding filename; same-second collision -> ``-1`` suffix."""
    candidate = saga_dir / f"{timestamp}.md"
    if not candidate.exists():
        return candidate
    seq = 1
    while True:
        candidate = saga_dir / f"{timestamp}-{seq}.md"
        if not candidate.exists():
            return candidate
        seq += 1


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def save(
    root: Path,
    saga: Saga,
    *,
    now: datetime | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Persist a new immutable tick + refresh the derived index.

    Merges with the latest prior tick (full-snapshot list semantics, scalar
    carry-forward), captures git state (guarded), writes a new immutable
    ``sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`` (``-N`` suffix on same-second
    collision), and atomically rewrites ``state.json`` via ``update_index``.
    """
    moment = now or _utc_now()
    prior = restore(root, saga.saga_id)
    merged = _merge(prior, saga, moment)

    git = current_git_state(root, runner=runner)
    if not merged.branch and git["branch"]:
        merged = _replace(merged, branch=git["branch"])
    if not merged.head_sha and git["head"]:
        merged = _replace(merged, head_sha=git["head"])
    if not merged.last_commit_sha and git["last_commit"]:
        merged = _replace(merged, last_commit_sha=git["last_commit"])

    saga_dir = root / SAGAS_DIR / merged.saga_id
    saga_dir.mkdir(parents=True, exist_ok=True)
    envelope_path = _allocate_envelope_path(saga_dir, _timestamp(moment))
    envelope_path.write_text(render_envelope(merged), encoding="utf-8")

    state_path = update_index(root, merged, now=moment)
    return {
        "saga_id": merged.saga_id,
        "envelope_path": str(envelope_path),
        "state_path": str(state_path),
        "phase": merged.phase,
        "status": merged.status,
        "next_phase": _next_phase(merged.phase, merged.phase_status),
        "next_round": merged.next_round,
    }


def _replace(saga: Saga, **changes: Any) -> Saga:
    data = {f.name: getattr(saga, f.name) for f in fields(Saga)}
    data.update(changes)
    return Saga(**data)


def _saga_summary(saga: Saga) -> dict[str, Any]:
    return {
        "saga_id": saga.saga_id,
        "kind": saga.kind,
        "id": saga.id,
        "lifecycle_phase": saga.lifecycle_phase,
        "phase_status": saga.phase_status,
        "status": saga.status,
        "phase": saga.phase,
        "round": saga.round,
        "next_phase": _next_phase(saga.phase, saga.phase_status),
        "next_round": saga.next_round,
        "destination": saga.destination,
        "issue_ref": saga.issue_ref,
        "plan_path": saga.plan_path,
        "branch": saga.branch,
        "orchestration_mode": saga.orchestration_mode,
        "orchestration_ref": saga.orchestration_ref,
        "next_step": saga.next_step,
        "updated_at": saga.updated_at,
    }


def _tick_snapshot(saga: Saga) -> dict[str, Any]:
    """A per-tick dict for the ``ticks`` reader: the summary fields PLUS the

    trajectory fields that differ across the chain (blockers / summary /
    open_questions / rounds_seen), so the full work-state evolution is visible
    where ``restore`` (latest-only) would only surface the final values. Builds
    on ``_saga_summary`` so the two readers share the machine-field shape.
    """
    snapshot = _saga_summary(saga)
    snapshot.update(
        {
            "blockers": saga.blockers,
            "summary": saga.summary,
            "open_questions": _materialize(saga.open_questions),
            "rounds_seen": _materialize(saga.rounds_seen),
        }
    )
    return snapshot


def update_index(root: Path, saga: Saga, *, now: datetime | None = None) -> Path:
    """Refresh the derived ``state.json`` index atomically.

    Shape::

        {last_updated, active_saga_id, sagas:{<saga_id>:{...summary...}},
         current_work:{...legacy fields..., saga_id}}

    ``current_work`` mirrors the most-recently-saved saga (carrying its
    ``saga_id`` so multi-saga readers can detect a mismatch) and keeps the
    legacy key set ``handoff_envelope`` and its test read unchanged.
    """
    moment = now or _utc_now()
    state_path = root / STATE_DIR / "state.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except json.JSONDecodeError:
            state = {}

    sagas = state.get("sagas")
    if not isinstance(sagas, dict):
        sagas = {}
    sagas[saga.saga_id] = _saga_summary(saga)

    state["last_updated"] = moment.isoformat()
    state["active_saga_id"] = saga.saga_id
    state["sagas"] = sagas
    work_sessions = _materialize(saga.work_session_paths)
    state["current_work"] = {
        "kind": saga.kind,
        "id": saga.id,
        "round": saga.round,
        "phase": saga.phase,
        "phase_status": saga.phase_status,
        "destination": saga.destination,
        "plan_path": saga.plan_path,
        "work_session_path": work_sessions[0] if work_sessions else "",
        "next_steps": [saga.next_step] if saga.next_step else [],
        "saga_id": saga.saga_id,
    }
    _atomic_write(state_path, json.dumps(state, indent=2) + "\n")
    return state_path


# ---------------------------------------------------------------------------
# restore / latest_envelope_for / scan
# ---------------------------------------------------------------------------


def envelope_sort_key(name: str) -> tuple[str, int]:
    """Structured FILENAME ordering key: ``(timestamp, seq)``.

    The base tick ``<ts>.md`` is seq 0; a same-second collision ``<ts>-N.md``
    is seq N, so the suffixed file always sorts AFTER its base (naive string
    compare would wrongly place ``<ts>-1.md`` before ``<ts>.md`` because ``-``
    < ``.``). Ordering is still derived purely from the filename — never mtime.
    """
    match = ENVELOPE_RE.match(name)
    if match is None:
        return (name, -1)
    return (match.group("ts"), int(match.group("seq") or 0))


def _envelope_files(saga_dir: Path) -> list[Path]:
    if not saga_dir.is_dir():
        return []
    return [p for p in saga_dir.iterdir() if p.is_file() and ENVELOPE_RE.match(p.name)]


def latest_envelope_for(root: Path, saga_id: str) -> Path | None:
    """Return the newest tick for a saga, ordered by FILENAME (never mtime)."""
    files = _envelope_files(root / SAGAS_DIR / saga_id)
    if not files:
        return None
    return max(files, key=lambda p: envelope_sort_key(p.name))


def restore(root: Path, saga_id: str) -> Saga | None:
    """Cold-reconstruct a saga from its latest tick. NEVER calls git/subprocess.

    Branch-agnostic: reads the envelope frontmatter + body only, so a saga
    restores identically regardless of the current checkout.
    """
    latest = latest_envelope_for(root, saga_id)
    if latest is None:
        return None
    return parse_envelope(latest.read_text(encoding="utf-8"))


def read_ticks(root: Path, saga_id: str) -> list[Saga]:
    """Return EVERY tick of a saga, oldest -> newest by FILENAME (never mtime).

    The full tick-chain trajectory that ``restore`` (latest-tick-only) cannot
    see: ``/resume``'s heavy forensic tier reads this to replay how the work
    state evolved (early ``next_step``s, blockers that later cleared, etc.).
    Reuses ``_envelope_files`` + ``envelope_sort_key`` + ``parse_envelope`` —
    same ordering contract as ``restore``, just the whole chain instead of the
    tail. Returns ``[]`` for an unknown/empty saga (NEVER calls git/subprocess).
    """
    files = sorted(
        _envelope_files(root / SAGAS_DIR / saga_id),
        key=lambda p: envelope_sort_key(p.name),
    )
    return [parse_envelope(p.read_text(encoding="utf-8")) for p in files]


def _scan_legacy(root: Path) -> list[dict[str, Any]]:
    """Read pre-0.4.0 ``checkpoints/`` as a low-priority, flagged fallback."""
    legacy_dir = root / LEGACY_CHECKPOINT_DIR
    if not legacy_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in legacy_dir.glob("*.md"):
        match = LEGACY_CHECKPOINT_RE.match(path.name)
        if not match:
            continue
        status = match.group("status") or "pending"
        phase = int(match.group("phase"))
        records.append(
            {
                "saga_id": derive_saga_id(match.group("kind"), match.group("id")),
                "path": str(path),
                "name": path.name,
                "kind": match.group("kind"),
                "id": match.group("id"),
                "round": int(match.group("round")) if match.group("round") else None,
                "phase": phase,
                "phase_status": status,
                "next_phase": _next_phase(phase, status),
                "legacy": True,
            }
        )
    return sorted(records, key=lambda r: r["name"], reverse=True)


def scan(root: Path, *, max_candidates: int | None = None) -> list[dict[str, Any]]:
    """List one candidate per saga (latest tick each), newest FIRST by filename.

    Groups per saga directory, reads the latest tick of each, sorts the group
    by envelope filename descending, then appends flagged legacy checkpoints
    (one version of back-compat). Non-matching files/dirs are skipped.
    """
    sagas_root = root / SAGAS_DIR
    candidates: list[dict[str, Any]] = []
    if sagas_root.is_dir():
        for saga_dir in sagas_root.iterdir():
            if not saga_dir.is_dir():
                continue
            latest = latest_envelope_for(root, saga_dir.name)
            if latest is None:
                continue
            saga = parse_envelope(latest.read_text(encoding="utf-8"))
            candidates.append(
                {
                    "saga_id": saga.saga_id or saga_dir.name,
                    "path": str(latest),
                    "name": latest.name,
                    "kind": saga.kind,
                    "id": saga.id,
                    "round": saga.round,
                    "phase": saga.phase,
                    "phase_status": saga.phase_status,
                    "status": saga.status,
                    "lifecycle_phase": saga.lifecycle_phase,
                    "next_phase": _next_phase(saga.phase, saga.phase_status),
                    "next_step": saga.next_step,
                    "updated_at": saga.updated_at,
                    "destination": saga.destination,
                    "issue_ref": saga.issue_ref,
                    "plan_path": saga.plan_path,
                    "branch": saga.branch,
                    "orchestration_mode": saga.orchestration_mode,
                    "orchestration_ref": saga.orchestration_ref,
                    "legacy": False,
                }
            )
    candidates.sort(key=lambda c: envelope_sort_key(c["name"]), reverse=True)
    candidates.extend(_scan_legacy(root))
    if max_candidates is not None:
        return candidates[:max_candidates]
    return candidates


# ---------------------------------------------------------------------------
# aggregate_context (lifted from load_saga_context.py)
# ---------------------------------------------------------------------------


def adr_refs_from_text(content: str | None) -> list[str]:
    """Extract normalized ``ADR-NNNN`` refs from free text."""
    if not content:
        return []
    matches = re.findall(r"\bADR[-\s]?(\d{2,4})\b", content, flags=re.IGNORECASE)
    return [f"ADR-{int(number):04d}" for number in matches]


def parse_repo(value: str) -> tuple[str, str]:
    """Split ``owner/repo`` (defaulting owner to ``infiquetra``)."""
    if "/" in value:
        owner, repo = value.split("/", 1)
        return owner, repo
    return "infiquetra", value


def prior_prs(
    owner: str, repo: str, issue: int, *, runner: Callable[..., Any] = subprocess.run
) -> list[dict[str, Any]]:
    """Round-tagged prior PRs for an issue (empty if ``gh`` missing/fails)."""
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--state",
        "all",
        "--search",
        f"in:title #{issue} round",
        "--json",
        "number,title,state,mergedAt,url,reviewDecision,body",
        "--limit",
        "50",
    ]
    try:
        result = runner(cmd, capture_output=True, text=True, check=False)  # nosec B603
    except (FileNotFoundError, OSError):
        return []
    if getattr(result, "returncode", 1) != 0:
        return []
    records: list[dict[str, Any]] = []
    for pr in json.loads(result.stdout or "[]"):
        round_match = ROUND_RE.search(pr.get("title", "") or "")
        records.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "mergedAt": pr.get("mergedAt"),
                "url": pr.get("url"),
                "reviewDecision": pr.get("reviewDecision"),
                "round": int(round_match.group(1)) if round_match else None,
                "body_preview": (pr.get("body") or "")[:500],
            }
        )
    return sorted(records, key=lambda record: int(record.get("round") or 0))


def journal_entries(root: Path, issue: int, adr_refs: list[str]) -> dict[str, list[dict[str, str]]]:
    """Find journal sections referencing the issue or its ADRs."""
    output: dict[str, list[dict[str, str]]] = {"learnings": [], "decisions": []}
    journal_dir = root / "docs" / "engineering-journal"
    if not journal_dir.exists():
        return output

    refs_to_search = [f"#{issue}", *adr_refs]
    for filename, key in (("LEARNINGS.md", "learnings"), ("DECISIONS.md", "decisions")):
        path = journal_dir / filename
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        sections = re.split(r"^## ", content, flags=re.MULTILINE)
        for section in sections[1:]:
            if any(ref in section for ref in refs_to_search):
                output[key].append(
                    {
                        "file": str(path),
                        "title": section.splitlines()[0].strip() if section else "",
                        "preview": section[:600],
                    }
                )
    return output


def aggregate_context(
    root: Path,
    owner: str,
    repo: str,
    issue: int,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Aggregate prior PRs, saga context, ADR refs, and journal entries.

    A missing ``gh`` never raises — ``prior_prs`` swallows ``FileNotFoundError``
    / ``OSError`` and returns an empty list, so offline resume still works.
    """
    saga_id = derive_saga_id("issue", str(issue))
    saga = restore(root, saga_id)
    prs = prior_prs(owner, repo, issue, runner=runner)

    saga_adrs = _materialize(saga.adr_refs) if saga is not None else []
    seed_text = ""
    if saga is not None:
        seed_text = "\n".join(
            [saga.summary, saga.decisions, saga.remaining, saga.notes, " ".join(saga_adrs)]
        )
    adrs = sorted(set(adr_refs_from_text(seed_text)) | set(saga_adrs))
    rounds_seen = sorted({int(pr["round"]) for pr in prs if pr.get("round") is not None})
    saga_summary = None
    if saga is not None:
        saga_summary = {
            "saga_id": saga.saga_id,
            "name": (latest := latest_envelope_for(root, saga_id)) and latest.name,
            "path": str(latest) if latest else None,
            "lifecycle_phase": saga.lifecycle_phase,
            "phase": saga.phase,
            "phase_status": saga.phase_status,
            "status": saga.status,
            "next_step": saga.next_step,
            "content_preview": render_envelope(saga)[:2000],
        }

    return {
        "repo": f"{owner}/{repo}",
        "issue": issue,
        "rounds_seen": rounds_seen,
        "next_round": (max(rounds_seen) + 1) if rounds_seen else 1,
        "saga": saga_summary,
        "prior_prs": prs,
        "adr_refs": adrs,
        "journal": journal_entries(root, issue, adrs),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _split_list(value: str | None) -> ListOrAbsent:
    """A missing flag (``None``) -> ABSENT (carry forward); a value -> a list.

    An explicit empty string clears (``[]``), matching snapshot semantics.
    """
    if value is None:
        return ABSENT
    return [item.strip() for item in value.split("|") if item.strip()]


def _split_int_list(value: str | None) -> ListOrAbsent:
    parsed = _split_list(value)
    if isinstance(parsed, _Absent):
        return ABSENT
    return [int(item) for item in parsed]


def _build_save_saga(args: argparse.Namespace) -> Saga:
    saga_id = args.saga_id or derive_saga_id(args.kind, args.id)
    return Saga(
        saga_id=saga_id,
        kind=args.kind,
        id=str(args.id),
        lifecycle_phase=args.lifecycle_phase,
        phase_status=args.phase_status,
        status=args.status,
        next_step=args.next_step,
        orchestration_mode=args.orchestration_mode,
        orchestration_ref=args.orchestration_ref,
        issue_ref=args.issue_ref,
        destination=args.destination,
        round=args.round or 0,
        phase=args.phase,
        progress_pct=args.progress_pct,
        plan_path=args.plan_path,
        work_session_paths=_split_list(args.work_session_paths),
        review_paths=_split_list(args.review_paths),
        qa_paths=_split_list(args.qa_paths),
        files_modified=_split_list(args.files_modified),
        rounds_seen=_split_int_list(args.rounds_seen),
        pr_refs=_split_list(args.pr_refs),
        adr_refs=_split_list(args.adr_refs),
        journal_refs=_split_list(args.journal_refs),
        blockers=args.blockers,
        open_questions=_split_list(args.open_questions),
        checks_run=_split_list(args.checks_run),
        source=args.source,
        summary=args.summary,
        decisions=args.decisions,
        remaining=args.remaining,
        notes=args.notes,
    )


def _add_save_parser(sub: Any) -> None:
    p = sub.add_parser("save", help="Write a new immutable saga tick")
    p.add_argument("--saga-id", default="", help="Override derived saga id")
    p.add_argument("--kind", choices=["issue", "task"], default="issue")
    p.add_argument("--id", required=True, help="Issue number or task slug")
    p.add_argument("--lifecycle-phase", choices=list(LIFECYCLE_PHASES), default="ideation")
    p.add_argument("--status", choices=list(STATUSES), default="active", help="thread disposition")
    p.add_argument(
        "--phase-status", choices=list(PHASE_STATUSES), default="pending", help="phase completion"
    )
    p.add_argument("--phase", type=int, default=0)
    p.add_argument("--round", type=int, default=0)
    p.add_argument("--progress-pct", type=int, default=0)
    p.add_argument("--destination", choices=list(DESTINATIONS), default="plan-only")
    p.add_argument("--orchestration-mode", choices=list(ORCHESTRATION_MODES), default="inline")
    p.add_argument("--orchestration-ref", default="")
    p.add_argument("--issue-ref", default="")
    p.add_argument("--next-step", default="")
    p.add_argument("--plan-path", default="")
    p.add_argument(
        "--work-session-paths", default=None, help="pipe-separated; omit = carry forward"
    )
    p.add_argument("--review-paths", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--qa-paths", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--files-modified", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--rounds-seen", default=None, help="pipe-separated ints; omit = carry forward")
    p.add_argument("--pr-refs", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--adr-refs", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--journal-refs", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--open-questions", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--checks-run", default=None, help="pipe-separated; omit = carry forward")
    p.add_argument("--blockers", default="")
    p.add_argument("--source", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--decisions", default="")
    p.add_argument("--remaining", default="")
    p.add_argument("--notes", default="")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    _add_save_parser(sub)

    restore_p = sub.add_parser("restore", help="Read the latest tick for a saga")
    restore_p.add_argument("--saga-id", required=True)

    ticks_p = sub.add_parser("ticks", help="Read EVERY tick for a saga (oldest->newest)")
    ticks_p.add_argument("--saga-id", required=True)

    scan_p = sub.add_parser("scan", help="List one candidate per saga (newest first)")
    scan_p.add_argument("--max-candidates", type=int, default=None)

    ctx_p = sub.add_parser("context", help="Aggregate issue/PR/journal context")
    ctx_p.add_argument("--repo", required=True)
    ctx_p.add_argument("--issue", type=int, required=True)

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _migrate_legacy_state_dir()
    args = parse_args(argv)
    root = Path.cwd()

    if args.command == "save":
        result = save(root, _build_save_saga(args))
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "restore":
        saga = restore(root, args.saga_id)
        if saga is None:
            print(json.dumps({"saga_id": args.saga_id, "found": False}, indent=2))
            return 0
        payload = {}
        for f in fields(saga):
            value = getattr(saga, f.name)
            payload[f.name] = _materialize(value) if f.name in _LIST_FIELDS else value
        payload["found"] = True
        # maturity is intentionally NOT emitted here: per saga-spec.md it is DERIVED
        # at /handoff time (via PHASE_TO_MATURITY) and never surfaced by the generic engine.
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "ticks":
        chain = read_ticks(root, args.saga_id)
        ticks = [_tick_snapshot(tick) for tick in chain]
        print(json.dumps({"ticks": ticks, "count": len(ticks)}, indent=2))
        return 0

    if args.command == "scan":
        candidates = scan(root, max_candidates=args.max_candidates)
        print(json.dumps({"candidates": candidates, "count": len(candidates)}, indent=2))
        return 0

    if args.command == "context":
        owner, repo = parse_repo(args.repo)
        print(json.dumps(aggregate_context(root, owner, repo, args.issue), indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
