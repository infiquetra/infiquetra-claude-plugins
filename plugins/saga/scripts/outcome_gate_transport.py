"""Remote gate-approval transport for the ``/outcome`` R20 approval gate (#379).

Give the durable ``/outcome`` frontier-approval gate a second, unattended delivery surface: the
fleet's own channel (redis-channel / Discord). When a gate holds while the terminal is unattended,
its prompt travels over the channel and the operator's reply becomes the durable approval — recording
**who** answered and over **which transport** as provenance on ``approvals/r{rev}.json`` (option A,
2026-07-05).

Design (KTD1-KTD6 of the #379 plan):

* **Transport-agnostic core.** ``compose_gate_notice`` renders the pending-approval prompt as plain
  text (gate id + pending subplots + lettered choices). It is pure and duck-typed on the spec, so it
  serves both transports and is trivially unit-testable.
* **Notice delivery is session-driven.** The session holding the gate calls the *connected*
  transport's ``reply()`` with this text (redis-channel ``reply()`` for a redis session, the Discord
  ``reply()`` MCP tool for Discord). ``emit_gate_notice`` is a **redis-channel-only** programmatic
  seam for a future Python driver that already holds a Redis client; it is not the v1 hot path and is
  a no-op for Discord (which has no Python-callable producer).
* **Authority is the transport's, never the message body.** ``parse_gate_answer`` accepts a reply
  only if it resolves a gate id that is in the caller-supplied ``pending_gate_ids`` set, and it reads
  ``answerer`` / ``transport`` from the router-set inbound fields — never from the body text. An
  ambiguous or unattributable reply returns ``None`` (rejected, surfaced) — the parser never defaults
  to *approve*. Sender authorization is enforced **upstream of the session** by the transport's access
  policy (Discord ``gate()`` pre-filters to ``allowFrom``; redis-channel defers to its router), so
  this module records provenance and correlates a pending gate — it does not, and cannot, authorize a
  sender.

This module is stdlib-only and imports neither ``outcome_spec`` nor the redis-channel plugin.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# A gate id is ``<outcome_id>@r<spec_revision>`` — it mirrors the ``approvals/r{rev}.json`` key the
# R20 approval is stored under. ``outcome_id`` is a slug (``[A-Za-z0-9._-]+``, enforced by
# ``OutcomeSpec`` validation); the ``@r<digits>`` suffix pins the exact revision being approved so a
# stale reply (answering an already-superseded frontier) cannot match the current pending gate.
_GATE_ID_RE = re.compile(r"[A-Za-z0-9._-]+@r\d+")

# Verdict tokens. Matched case-insensitively as whole words in the reply. Deliberately explicit and
# closed: anything not clearly approve or clearly reject leaves the verdict ambiguous, which
# ``parse_gate_answer`` treats as "not accepted" rather than guessing.
_APPROVE_TOKENS = frozenset({"a", "approve", "approved", "y", "yes", "ok", "okay", "👍", "✅"})
_REJECT_TOKENS = frozenset({"b", "hold", "n", "no", "reject", "rejected", "deny", "👎", "❌"})

_WORD_RE = re.compile(r"[^\W_]+|[👍✅👎❌]", re.UNICODE)


def gate_id(outcome_id: str, spec_revision: int) -> str:
    """The correlation id a gate notice carries and an answer must quote: ``<outcome_id>@r<rev>``."""
    return f"{outcome_id}@r{spec_revision}"


def compose_gate_notice(spec: Any, spec_revision: int, gated_subplots: Iterable[str]) -> str:
    """Render the pending-approval prompt for a held frontier — transport-agnostic, pure, deterministic.

    ``spec`` is duck-typed: only ``.outcome_id`` and ``.node_by_id(subplot_id) -> node|None`` (with
    ``node.title``) are used, so a ``SimpleNamespace`` suffices in tests. ``gated_subplots`` is the
    frontier's held ``subplot_id`` list (``AdvanceResult.gated``). Output is a single text block
    suitable for a dm/channel ``reply()``; it carries the gate id the answer must quote.
    """
    gid = gate_id(spec.outcome_id, spec_revision)
    lines = [
        f"🔒 Approval gate — outcome `{spec.outcome_id}` (frontier r{spec_revision})",
        "",
    ]
    subplots = list(gated_subplots)
    if subplots:
        noun = "subplot awaits" if len(subplots) == 1 else "subplots await"
        lines.append(f"{len(subplots)} {noun} your approval before dispatch:")
        for sid in subplots:
            node = spec.node_by_id(sid) if hasattr(spec, "node_by_id") else None
            title = getattr(node, "title", "") if node is not None else ""
            lines.append(f"  • `{sid}` — {title}" if title else f"  • `{sid}`")
    else:  # defensive: a gate holds a frontier, but render a coherent notice even if the list is empty
        lines.append("The current frontier awaits your approval before dispatch.")
    lines += [
        "",
        "Reply with the gate id to answer:",
        f"  A) approve — dispatch this frontier   (`y {gid}`)",
        f"  B) hold — leave it gated, no dispatch  (`n {gid}`)",
        "",
        f"gate: `{gid}`",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class GateAnswer:
    """A parsed, transport-authorized answer to a specific pending gate.

    ``verdict`` is ``"approve"`` or ``"reject"``. ``answerer`` / ``transport`` are provenance taken
    from the *router-set* inbound fields, ready to pass to ``approve_frontier(..., answerer=,
    transport=)`` (only an ``"approve"`` verdict writes the durable record; ``"reject"`` is a no-op
    hold).
    """

    gate_id: str
    verdict: str  # "approve" | "reject"
    answerer: str
    transport: str


def _resolve_verdict(text: str) -> str | None:
    """Map a reply to ``"approve"`` / ``"reject"`` / ``None``. Never defaults to approve (fail-closed)."""
    tokens = {t.lower() for t in _WORD_RE.findall(text)}
    approve = bool(tokens & _APPROVE_TOKENS)
    reject = bool(tokens & _REJECT_TOKENS)
    if approve == reject:  # neither, or both (contradictory) -> ambiguous
        return None
    return "approve" if approve else "reject"


def _first_pending(text: str, pending: Iterable[str]) -> str | None:
    """The first gate id in ``text`` that is a member of ``pending`` (a real, current pending gate)."""
    pending_set = set(pending)
    for candidate in _GATE_ID_RE.findall(text):
        if candidate in pending_set:
            return candidate
    return None


def parse_gate_answer(
    inbound: Mapping[str, Any], pending_gate_ids: Iterable[str]
) -> GateAnswer | None:
    """Turn an inbound channel reply into a ``GateAnswer`` iff it resolves a pending gate; else ``None``.

    Acceptance requires **all** of: (1) the reply quotes a gate id that is in ``pending_gate_ids``
    (a forged/guessed/stale gate cannot match); (2) the verdict is unambiguous; (3) the sender is
    attributable — ``answerer`` (``username`` or ``user_id``) and ``transport`` (``source`` or
    ``router``) are present on the *inbound*, not the body. Any miss returns ``None`` (rejected, to be
    surfaced). Authority is the transport's (it authorized the sender upstream); this function records
    provenance and correlates a pending gate — it never authorizes a sender.
    """
    text = str(inbound.get("text", "") or "")
    if not text.strip():
        return None

    gid = _first_pending(text, pending_gate_ids)
    if gid is None:  # no reply→pending-gate correlation: not accepted
        return None

    # Resolve the verdict from the operator's *intent* words only, with every gate-id-shaped token
    # stripped first. The gate id embeds the operator-chosen ``outcome_id``, so a name like
    # ``no-op-migration`` would otherwise inject a spurious ``no`` (reject) token and read every reply
    # as ambiguous — un-approvable over the channel. Stripping is fail-safe: it only removes tokens,
    # so it can never manufacture an approve token that was not the operator's word.
    verdict = _resolve_verdict(_GATE_ID_RE.sub(" ", text))
    if verdict is None:  # ambiguous -> never guess an approval
        return None

    # Provenance from router-set fields only — never from the message body.
    answerer = str(inbound.get("username") or inbound.get("user_id") or "").strip()
    transport = str(inbound.get("source") or inbound.get("router") or "").strip()
    if not answerer or not transport:  # unattributable -> not accepted (R3)
        return None

    return GateAnswer(gate_id=gid, verdict=verdict, answerer=answerer, transport=transport)


def emit_gate_notice(
    session_name: str,
    chat_id: str,
    text: str,
    *,
    producer: Callable[[Mapping[str, Any]], Any],
    is_connected: Callable[[], bool] | None = None,
) -> Any | None:
    """Redis-channel-only programmatic seam: publish a composed gate notice over the outbound stream.

    This is **not** the v1 hot path (that is session-driven: the session calls the connected
    transport's ``reply()`` — see the module docstring), and it is a no-op for Discord. It exists for
    a future Python driver that already holds a Redis client, e.g. a cron-driven ``outcome advance``.

    ``producer`` is injected (tests pass a fake). The real redis binding is
    ``producer=lambda p: redis_producer.publish_outbound(client, session_name, _as_outbound(p))``.
    ``is_connected`` gates emission on a live session; the real detector is
    ``lambda: session_name in presence.list_live_sessions(client)`` (``presence.py``). When it reports
    no live session, emission is a no-op returning ``None`` (R5 disconnected fallback).
    """
    if is_connected is not None and not is_connected():
        return None
    return producer(
        {"session_name": session_name, "chat_id": chat_id, "text": text, "voice": False}
    )
