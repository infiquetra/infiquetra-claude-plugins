#!/usr/bin/env python3
"""The mid-run adjustment envelope: one versioned control file, four writers (#372).

A run-start intent envelope captures the operator's *up-front* directives. This module is
its **mid-run counterpart** — one durable, polled control file that lets an operator or a
worker steer a live ``/work`` or ``/outcome`` run without killing it or hand-editing state.

Five writers converge on the *same* file (never separate files):

* **operator-raised quiesce** — drain in-flight work, dispatch nothing new, surface a resume
  point (``quiesce``);
* **plan-declared pause points** — halt deterministically at a named segment boundary and
  resume only on an explicit continue signal (``pause_after``);
* **worker-raised andon-cord** — any worker/reviewer inside a team can stop the line
  (``andon_halt``);
* **operator amendments** — re-tier / add a reviewer / cancel / abort (``re-tier``,
  ``add-reviewer``, ``cancel``, ``abort``); and
* **coordinator strand-halt** (#433 R6) — the /outcome coordinator raises an ``andon_halt``
  (``writer: "coordinator"``) when a posture repost would strand an in-flight leaf's
  irreversible-op authorization (:func:`raise_strand_halt`).

The envelope is **polled at existing boundaries** — the ``/outcome`` coordinator's
tick-quiescence check (``outcome.py``) and the ``/work`` segment boundary — never on a new
standing poll loop.

Threat model / self-attestation
-------------------------------
This parser is the trust boundary for operator/worker directives. It **fails closed**
(:func:`parse` raises :class:`EnvelopeError`) on anything it cannot strictly understand — an
unknown directive name, an unknown key, a missing required field, a wrong version, or
malformed JSON. It does **not** enumerate-and-skip: an input it cannot fully model is an
error that HALTs the run and names the offending token, never a silent pass. The directive
records are *self-attested* by whoever wrote the file; this module authenticates the
*shape*, not the *authority* of the writer — an ``andon_halt`` claiming ``writer:
"reviewer"`` is trusted to be from a reviewer. Authority binding is out of scope for v1
(the file lives under the run's private ``.saga/`` state, writable only by the run's own
operator/worker processes).

House testability pattern (mirrors ``outcome_spec.py`` / ``execution_spec.py``): pure
functions, no I/O at import, dataclasses with an explicit ``from_dict`` so a JSON-authored
envelope round-trips deterministically and offline.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# On-disk schema version. Bumped only on a breaking envelope-shape change so an old file is
# migrated rather than silently mis-read. A file that declares any other version fails closed.
ENVELOPE_VERSION = 1

# The closed directive vocabulary (R1). The parser does NOT invent directives; a token
# outside this set fails closed (R3) rather than flowing on as a silent no-op.
#   quiesce      — operator: drain in-flight, dispatch nothing new, surface a resume point
#   pause_after  — plan: halt at a named segment boundary; resume only on explicit continue
#   andon_halt   — worker/reviewer: stop-the-line; block the next wave/tick from dispatching
#   re-tier      — operator: change model/effort tier; honored on resume (an amendment)
#   add-reviewer — operator: add a reviewer to the next review cycle (an amendment)
#   cancel       — operator: stop this run at the next boundary (terminal)
#   abort        — operator: stop this run at the next boundary, hardest stop (terminal)
KNOWN_DIRECTIVES = frozenset(
    {"quiesce", "pause_after", "andon_halt", "re-tier", "add-reviewer", "cancel", "abort"}
)

# Directives that STOP dispatch when active (their presence prevents the next wave/tick).
# ``quiesce`` drains (in-flight finishes, nothing new); ``andon_halt``/``cancel``/``abort``
# HALT; an unsatisfied ``pause_after`` at its boundary pauses.
_HALTING = frozenset({"andon_halt", "cancel", "abort"})

# Directives that AMEND posture and are honored on resume rather than stopping the run.
_AMENDING = frozenset({"re-tier", "add-reviewer"})

# Recognized writers. A directive from an unrecognized writer fails closed (fail-closed on
# shape) — we authenticate the shape, not the authority (see module threat model).
# ``coordinator`` (#433 R6): the /outcome coordinator itself raises a stop-the-line
# ``andon_halt`` when a posture repost would strand an in-flight leaf's irreversible-op
# authorization — the campaign HALTs through the SAME polled file, never a fifth surface.
KNOWN_WRITERS = frozenset({"operator", "plan", "worker", "reviewer", "coordinator"})

# Per-directive allowed keys. Every directive carries ``directive``/``writer``; the rest are
# directive-specific. An unlisted key fails closed (strict — an input we cannot model is an
# error, not a pass). ``id``/``reason``/``at``/``acknowledged`` are universally optional.
_COMMON_KEYS = frozenset({"directive", "writer", "reason", "at", "id", "acknowledged"})
_DIRECTIVE_KEYS: dict[str, frozenset[str]] = {
    "quiesce": _COMMON_KEYS,
    "pause_after": _COMMON_KEYS | {"segment", "resume_tier", "resume_context"},
    "andon_halt": _COMMON_KEYS | {"scope"},
    "re-tier": _COMMON_KEYS | {"tier"},
    "add-reviewer": _COMMON_KEYS | {"reviewer"},
    "cancel": _COMMON_KEYS,
    "abort": _COMMON_KEYS,
}
# Required directive-specific fields. Missing => fail closed.
_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "pause_after": frozenset({"segment"}),
    "re-tier": frozenset({"tier"}),
    "add-reviewer": frozenset({"reviewer"}),
}

_ALLOWED_TOP_KEYS = frozenset({"version", "directives"})


class EnvelopeError(ValueError):
    """A malformed / unrecognized envelope — the run must HALT and surface this (R3)."""


@dataclass(frozen=True)
class Directive:
    """One writer's directive. ``extra`` holds the validated directive-specific fields."""

    directive: str
    writer: str
    reason: str = ""
    at: str = ""
    id: str = ""
    acknowledged: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"directive": self.directive, "writer": self.writer}
        if self.reason:
            out["reason"] = self.reason
        if self.at:
            out["at"] = self.at
        if self.id:
            out["id"] = self.id
        if self.acknowledged:
            out["acknowledged"] = True
        out.update(self.extra)
        return out


@dataclass(frozen=True)
class AdjustmentEnvelope:
    version: int
    directives: tuple[Directive, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "directives": [d.to_dict() for d in self.directives]}


@dataclass(frozen=True)
class PollDecision:
    """The verdict at a poll boundary.

    ``action`` is the strongest directive in effect, in precedence order
    ``halt > drain > pause > proceed`` (HALT wins — composing with, never weakening, the
    existing HALT-not-degrade precedence). ``amendments`` are re-tier/add-reviewer changes
    the caller must honor on resume. ``surfaced`` is the operator-visible record.
    """

    action: str  # "proceed" | "drain" | "pause" | "halt"
    surfaced: tuple[str, ...] = ()
    amendments: tuple[dict[str, Any], ...] = ()
    triggering: tuple[Directive, ...] = ()

    @property
    def stops_dispatch(self) -> bool:
        """True when the next wave/tick must NOT dispatch (drain, pause, or halt)."""
        return self.action in ("drain", "pause", "halt")


def parse(data: Any) -> AdjustmentEnvelope:
    """Parse + strictly validate an envelope mapping. Fails closed on anything unmodellable.

    Raises :class:`EnvelopeError` (naming the offending token) for: a non-mapping document,
    a missing/unsupported ``version``, an unknown top-level key, a non-list ``directives``,
    a non-mapping directive, an unknown directive name, an unknown directive key, a missing
    required field, or an unrecognized writer. No enumerate-and-skip: an input we cannot
    fully model is an error, not a pass (R3).
    """
    if not isinstance(data, dict):
        raise EnvelopeError(f"envelope must be a JSON object, got {type(data).__name__}")

    unknown_top = set(data) - _ALLOWED_TOP_KEYS
    if unknown_top:
        raise EnvelopeError(f"unknown envelope key(s): {sorted(unknown_top)!r}")

    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise EnvelopeError(f"envelope version must be an int, got {version!r}")
    if version != ENVELOPE_VERSION:
        raise EnvelopeError(
            f"unsupported envelope version {version} (this parser speaks {ENVELOPE_VERSION})"
        )

    raw_directives = data.get("directives", [])
    if not isinstance(raw_directives, list):
        raise EnvelopeError(f"'directives' must be a list, got {type(raw_directives).__name__}")

    directives: list[Directive] = []
    for i, raw in enumerate(raw_directives):
        directives.append(_parse_directive(raw, index=i))
    return AdjustmentEnvelope(version=version, directives=tuple(directives))


def _parse_directive(raw: Any, *, index: int) -> Directive:
    if not isinstance(raw, dict):
        raise EnvelopeError(f"directive #{index} must be a JSON object, got {type(raw).__name__}")
    name = raw.get("directive")
    if not isinstance(name, str) or not name:
        raise EnvelopeError(f"directive #{index} is missing a 'directive' name")
    if name not in KNOWN_DIRECTIVES:
        raise EnvelopeError(f"unrecognized directive: {name!r}")

    allowed = _DIRECTIVE_KEYS[name]
    unknown = set(raw) - allowed
    if unknown:
        raise EnvelopeError(f"directive {name!r} has unknown key(s): {sorted(unknown)!r}")

    missing = _REQUIRED_FIELDS.get(name, frozenset()) - set(raw)
    if missing:
        raise EnvelopeError(f"directive {name!r} is missing required field(s): {sorted(missing)!r}")

    writer = raw.get("writer", "operator")
    if writer not in KNOWN_WRITERS:
        raise EnvelopeError(f"directive {name!r} has unrecognized writer: {writer!r}")

    # Value-type strictness (panel hand-finish): shape-valid but wrong-typed values must be
    # errors, not silent no-ops. bool('no') is True, so a hand-authored acknowledged: "no"
    # would silently SKIP a declared pause; a non-string segment can never match any boundary,
    # leaving a declared pause silently unreachable.
    acknowledged = raw.get("acknowledged", False)
    if not isinstance(acknowledged, bool):
        raise EnvelopeError(
            f"directive {name!r}: 'acknowledged' must be a JSON boolean, got {acknowledged!r}"
        )
    if name == "pause_after":
        segment = raw.get("segment")
        if not isinstance(segment, str) or not segment:
            raise EnvelopeError(
                "directive 'pause_after': 'segment' must be a non-empty string naming a "
                f"boundary, got {segment!r} — a non-string segment matches no boundary, "
                "which would make the declared pause a silent no-op"
            )

    extra = {k: raw[k] for k in raw if k not in _COMMON_KEYS}
    return Directive(
        directive=name,
        writer=writer,
        reason=str(raw.get("reason", "")),
        at=str(raw.get("at", "")),
        id=str(raw.get("id", "")),
        acknowledged=acknowledged,
        extra=extra,
    )


def load(path: Path) -> AdjustmentEnvelope | None:
    """Load + validate the envelope at ``path``. ``None`` if absent (no envelope = proceed).

    A present-but-malformed file fails closed (:class:`EnvelopeError`) — an unreadable
    control surface is treated as an error, never as "no directives".
    """
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvelopeError(f"envelope at {path} is not readable JSON: {exc}") from exc
    return parse(raw)


def poll(envelope: AdjustmentEnvelope | None, *, segment: str | None = None) -> PollDecision:
    """Evaluate the envelope at a boundary. Returns the strongest directive's :class:`PollDecision`.

    ``segment`` is the boundary's segment name; a ``pause_after`` matching it (and not yet
    acknowledged) pauses. An acknowledged ``pause_after`` is a satisfied/continued pause: it
    does not stop, but its ``resume_tier``/``resume_context`` are carried as amendments so the
    resumed run honors the operator's context/model change (R7). Precedence: any halting
    directive (andon/cancel/abort) beats a drain (quiesce) beats a pause. Amendments
    (re-tier/add-reviewer) never stop the run; they accumulate for the caller to apply.
    """
    if envelope is None:
        return PollDecision(action="proceed")

    surfaced: list[str] = []
    amendments: list[dict[str, Any]] = []
    triggering: list[Directive] = []
    action = "proceed"

    def _raise(level: str) -> None:
        nonlocal action
        order = {"proceed": 0, "pause": 1, "drain": 2, "halt": 3}
        if order[level] > order[action]:
            action = level

    for d in envelope.directives:
        if d.directive in _HALTING:
            _raise("halt")
            surfaced.append(_surface(d))
            triggering.append(d)
        elif d.directive == "quiesce":
            _raise("drain")
            surfaced.append(_surface(d))
            triggering.append(d)
        elif d.directive == "pause_after":
            if segment is not None and d.extra.get("segment") == segment:
                if d.acknowledged:
                    # Continued past this pause — honor any operator context/model change.
                    for amd in _pause_amendments(d):
                        amendments.append(amd)
                else:
                    _raise("pause")
                    surfaced.append(_surface(d))
                    triggering.append(d)
        elif d.directive in _AMENDING:
            amendments.append(_amendment(d))
            surfaced.append(_surface(d))

    return PollDecision(
        action=action,
        surfaced=tuple(surfaced),
        amendments=tuple(amendments),
        triggering=tuple(triggering),
    )


def _surface(d: Directive) -> str:
    who = d.writer
    detail = d.reason or ""
    scope = d.extra.get("scope") or d.extra.get("segment") or ""
    parts = [f"{d.directive} [{who}]"]
    if scope:
        parts.append(f"scope={scope}")
    if detail:
        parts.append(detail)
    return " ".join(parts)


def _amendment(d: Directive) -> dict[str, Any]:
    if d.directive == "re-tier":
        return {"kind": "re-tier", "tier": d.extra["tier"]}
    if d.directive == "add-reviewer":
        return {"kind": "add-reviewer", "reviewer": d.extra["reviewer"]}
    raise EnvelopeError(f"{d.directive!r} is not an amending directive")


def _pause_amendments(d: Directive) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if "resume_tier" in d.extra:
        out.append({"kind": "re-tier", "tier": d.extra["resume_tier"]})
    if "resume_context" in d.extra:
        out.append({"kind": "context", "context": d.extra["resume_context"]})
    return out


# --------------------------------------------------------------------------------------------
# Writer helpers — the four producers. Each appends a directive to the SAME envelope file
# atomically (read-modify-write under a temp+rename), so quiesce/pause/andon/amendments all
# land in one polled surface (never four files). These are the producers the boundary poll
# consumes; producer + consumer ship together (no dead wiring).
# --------------------------------------------------------------------------------------------


def _atomic_write(path: Path, env: AdjustmentEnvelope) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(env.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append(path: Path, directive: Directive) -> AdjustmentEnvelope:
    existing = load(path)
    if existing is None:
        env = AdjustmentEnvelope(version=ENVELOPE_VERSION, directives=(directive,))
    else:
        env = AdjustmentEnvelope(
            version=existing.version, directives=existing.directives + (directive,)
        )
    _atomic_write(path, env)
    return env


def raise_quiesce(path: Path, *, reason: str = "", at: str = "") -> AdjustmentEnvelope:
    """Operator writer 1: drain in-flight, dispatch nothing new, surface a resume point."""
    return _append(path, Directive(directive="quiesce", writer="operator", reason=reason, at=at))


def declare_pause_after(
    path: Path,
    segment: str,
    *,
    reason: str = "",
    resume_tier: str = "",
    resume_context: str = "",
    at: str = "",
) -> AdjustmentEnvelope:
    """Plan writer 2: halt deterministically at ``segment``; resume on explicit continue."""
    extra: dict[str, Any] = {"segment": segment}
    if resume_tier:
        extra["resume_tier"] = resume_tier
    if resume_context:
        extra["resume_context"] = resume_context
    d = Directive(directive="pause_after", writer="plan", reason=reason, at=at, extra=extra)
    return _append(path, d)


def raise_andon(
    path: Path, *, writer: str = "worker", scope: str = "", reason: str = "", at: str = ""
) -> AdjustmentEnvelope:
    """Worker writer 3: stop-the-line. Blocks the next wave/tick through the same file."""
    if writer not in ("worker", "reviewer"):
        raise EnvelopeError(f"andon writer must be worker/reviewer, got {writer!r}")
    extra = {"scope": scope} if scope else {}
    d = Directive(directive="andon_halt", writer=writer, reason=reason, at=at, extra=extra)
    return _append(path, d)


def raise_strand_halt(path: Path, *, scope: str, reason: str, at: str = "") -> AdjustmentEnvelope:
    """Coordinator writer (#433 R6): a posture repost would strand an in-flight leaf's
    irreversible-op authorization — stop the line through the SAME polled envelope file.

    Semantically an ``andon_halt`` (the existing stop-the-line directive) with
    ``writer: "coordinator"``: the next advance tick's poll HALTs dispatch, the in-flight
    leaf drains under its dispatch-time posture (R5), and the rejected amendment is
    surfaced to the operator — never silently applied, never silently dropped. ``scope``
    names the stranded leaf so the surfaced record says exactly which op forced the stop.

    **Append-once on (writer, scope)** — the envelope-side parity of the reconcile halt
    path's ledger (phase, key) dedup: a repeated stranded repost against the same leaf
    re-raises to its caller every time, but the ONE standing halt directive is never
    duplicated (a directive pile-up would make the operator clear N records for one strand).
    """
    if not scope:
        raise EnvelopeError("a strand halt needs a scope naming the stranded leaf")
    existing = load(path)
    if existing is not None and any(
        d.directive == "andon_halt" and d.writer == "coordinator" and d.extra.get("scope") == scope
        for d in existing.directives
    ):
        return existing
    d = Directive(
        directive="andon_halt", writer="coordinator", reason=reason, at=at, extra={"scope": scope}
    )
    return _append(path, d)


def acknowledge_pause(path: Path, segment: str, *, at: str = "") -> AdjustmentEnvelope:
    """The explicit continue signal for a ``pause_after`` at ``segment`` (R5).

    Marks the matching pause directive ``acknowledged`` so the next poll lets the run
    proceed past that boundary and carries its ``resume_tier``/``resume_context`` amendments.
    Fails closed if there is no matching unacknowledged pause (a continue with nothing to
    continue is an error, not a silent no-op).
    """
    existing = load(path)
    if existing is None:
        raise EnvelopeError(f"no envelope to continue at segment {segment!r}")
    new: list[Directive] = []
    matched = False
    for d in existing.directives:
        if (
            d.directive == "pause_after"
            and d.extra.get("segment") == segment
            and not d.acknowledged
        ):
            matched = True
            new.append(
                Directive(
                    directive=d.directive,
                    writer=d.writer,
                    reason=d.reason,
                    at=d.at,
                    id=d.id,
                    acknowledged=True,
                    extra=d.extra,
                )
            )
        else:
            new.append(d)
    if not matched:
        raise EnvelopeError(f"no unacknowledged pause_after at segment {segment!r} to continue")
    env = AdjustmentEnvelope(version=existing.version, directives=tuple(new))
    _atomic_write(path, env)
    return env


def clear(path: Path) -> None:
    """Remove the envelope file (all directives resolved). No-op if already absent."""
    path.unlink(missing_ok=True)


def default_envelope_path(repo_root: Path) -> Path:
    """Canonical per-run envelope location: the run's private ``.saga/`` state (git-ignored)."""
    return repo_root / ".saga" / "adjustment-envelope.json"


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect / write the mid-run adjustment envelope")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="print the parsed envelope + the current poll decision")
    p_q = sub.add_parser("quiesce", help="raise the operator quiesce sentinel")
    p_q.add_argument("--reason", default="")
    p_a = sub.add_parser("andon", help="raise a worker/reviewer andon-cord halt")
    p_a.add_argument("--writer", default="worker", choices=["worker", "reviewer"])
    p_a.add_argument("--scope", default="")
    p_a.add_argument("--reason", default="")
    p_c = sub.add_parser("continue", help="acknowledge a pause_after and continue")
    p_c.add_argument("segment")
    sub.add_parser("clear", help="remove the envelope (all directives resolved / andon cleared)")

    args = parser.parse_args(argv)
    path = default_envelope_path(args.repo_root)

    if args.command == "show":
        env = load(path)
        if env is None:
            print("no envelope (proceed)")
            return 0
        print(json.dumps(env.to_dict(), indent=2))
        print("poll:", poll(env).action)
        return 0
    if args.command == "quiesce":
        raise_quiesce(path, reason=args.reason)
        print(f"quiesce raised at {path}")
        return 0
    if args.command == "andon":
        raise_andon(path, writer=args.writer, scope=args.scope, reason=args.reason)
        print(f"andon raised at {path}")
        return 0
    if args.command == "continue":
        acknowledge_pause(path, args.segment)
        print(f"continued past pause_after {args.segment!r}")
        return 0
    if args.command == "clear":
        clear(path)
        print(f"envelope cleared at {path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
