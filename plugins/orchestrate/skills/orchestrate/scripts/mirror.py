#!/usr/bin/env python3
"""The mirror: the orchestrator's paired session, and the clock that watches it.

The orchestrator session routes, decides, records, and answers the operator. It does not
perform substantive work in the operator's channel (R4). Substantive work still has to
happen, so it needs a home, and the mirror is it: a persistent paired session that does the
*orchestrator's* own work -- synthesis, comparison, bulk reading -- as distinct from
children, which do the *outcome's* work (R5).

Three mechanical contracts, each with a documented reason it erodes.

**The return is distilled, and the bound is enforced twice (R6).** A return larger than the
request's declared bound is *rejected*, never truncated into apparent success, and the
rejection carries the byte count without the material -- an error message that quoted the
oversized return would defeat the requirement it reports. The declaration itself is capped
at :data:`MAX_DECLARABLE_RETURN_BYTES`, because the way a byte bound erodes is not that
somebody deletes it, it is that somebody raises it.

**The validity predicate never runs here (KTD6, R6b).** A predicate is a bounded mechanical
check and the orchestrator runs it inline, where it sees the bytes. Routing it through the
mirror turns verification back into a claim: the mirror reports a pass, the orchestrator
never reads the evidence, and the highest-severity failure class reappears one layer up with
no second reader. Three independent guards, in ascending order of how hard they are to
defeat by accident:

1. :class:`MirrorRequest` accepts a closed vocabulary of *reading* kinds. Deciding kinds are
   enumerated in :data:`DECIDING_KINDS` and refused by name.
2. An instruction carrying a predicate *declaration* -- a JSON object with an ``argv`` key,
   which is what a predicate literally is -- is refused.
3. This module executes no program and does not import ``completion``. There is no code path
   here that could run a predicate even if a request asked for one.

   What the third guard does **not** establish: this module drives Herdr through an injected
   adapter, and that adapter runs programs. A caller that hands the mirror an adapter which
   executes arbitrary argv has defeated it. Nor can any guard here detect an instruction that
   *describes* a check in English. The control for that is the written routing rule in
   ``references/operator-channel.md`` plus the fact that this module never writes ``phase``:
   ``completion.evaluate_completion`` is the only path to ``verified``, so a mirror that
   says "the tests pass" changes no register state and gates nothing.

**The mirror has its own register row, from creation (R6c).** It is the only long-lived
session that would otherwise have no liveness representation, and the one whose failure is
least visible. :func:`create_mirror` writes the row *before* the launch side effect, so a
launch that fails still leaves a registered mirror rather than an invisible one.

Column ownership
----------------
This module writes exactly the columns in :data:`OWNED_COLUMNS`, and only on the mirror's own
row. Every register write goes through :func:`_write_owned`, which refuses any other column
at runtime -- ownership that is checkable rather than merely documented. In particular it
does not write ``artifact_path`` (the mirror produces a distilled return, not a settled
artifact), does not write ``observed_state`` (owned by the subscriber, and rewritten by every
catch-up pass, so a failure recorded there would be erased while the pane is still open), and
never promotes ``phase`` to a terminal value on the strength of its own claim. ``agent``,
``pane_id`` and the rest of the substrate group are written by ``session_lifecycle`` when the
mirror is launched through the same path as any other session; ``role`` is this module's own
column and is how a mirror row is identified, because ``agent`` carries the launcher's actual
agent name for every launched row.

Hang detection needs a clock, and that is the whole difficulty
--------------------------------------------------------------
Every other failure in this system shows up as a *disagreement*: expected state against
observed state, declared artifact against artifact on disk, claimed completion against a
predicate that runs. A hung mirror produces no disagreement at all. Its expected state and its
observed state agree perfectly and every child still looks healthy, while the operator channel
is dead -- precisely the failure the mirror exists to prevent, arriving through the mirror.

So the only detector is a clock: ``last_event_at`` exceeding a declared ``max_quiet_seconds``.
:func:`check_liveness` takes an explicit ``now`` rather than reading the system clock, so the
test for it does not sleep.

**What the clock actually asserts, and what it does not.** It asserts that this row has not
been observed emitting for longer than the operator declared it should ever be silent. It is a
declared-tolerance alarm, not a liveness proof. Nothing here distinguishes a mirror that is
quiet because it is thinking from one that is quiet because it is dead, and this is worth
stating rather than papering over:

- ``last_event_at`` is fed by the subscriber, which writes it when a ``pane.output_matched``
  event carries a sentinel matching an active subscription. The mirror's only subscribed
  sentinel is its return marker. So within a single request ``last_event_at`` does not
  advance, and ``max_quiet_seconds`` on a mirror row is in practice a per-request tolerance
  rather than a within-request liveness probe.
- A within-request heartbeat would close that gap, and is deliberately not built: the
  subscriber wakes the orchestrator on every matched event, so a heartbeat subscription would
  wake the operator's channel on a timer -- the exact channel-load failure this unit exists to
  prevent. It becomes reachable if the subscriber gains a subscription that advances
  ``last_event_at`` without waking the orchestrator.
- Combining the clock with herdr's ``agent_status`` would make it worse, not better. Vendor
  lifecycle detectors are wrong in vendor-specific ways -- one runtime reports ``idle`` while
  working, another reported settled from launch through completion -- so a detector agreeing
  with the clock would supply false confidence rather than a second reader.

The alarm is therefore advisory: :func:`check_liveness` reads and raises. It writes nothing,
kills nothing, and demotes nothing. What to do about a quiet mirror -- probe the pane, re-ask,
replace it -- is a decision, and decisions are the orchestrator's.

An *idle* mirror is legitimately silent forever, so the clock is armed only while a request is
outstanding. That is what ``mirror_request`` records.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import register as register_store
import session_lifecycle
import subscriber

# --------------------------------------------------------------------------- vocabulary

MIRROR_ROLE = "mirror"

#: The only columns this module writes, and only on the mirror's own row. ``max_quiet_seconds``
#: is an existing register column whose meaning is a per-row hang strategy the dispatching
#: caller sets; this module is its writer for the mirror row and for no other row.
OWNED_COLUMNS = ("role", "max_quiet_seconds", "mirror_request", "mirror_last_return")

#: Request kinds the mirror accepts. Every member is *reading*: the mirror consumes material
#: and returns a conclusion about it. A new member may be added only if it is also reading.
READING_KINDS = ("synthesis", "comparison", "bulk_read", "survey", "recall")

#: Request kinds refused by name, so the refusal says why rather than "unknown kind". The
#: mirror does unbounded reading; it does not do deciding (KTD6).
DECIDING_KINDS = ("predicate", "verify", "verdict", "decide", "completion", "gate", "approve")

#: The tier registry key the mirror is launched under. ``work-medium`` and deliberately not a
#: ``review-*`` shape: "review" names deciding, and the mirror never decides. It is the tier a
#: session that reads and distils needs -- a mirror that has quietly degraded is worse than no
#: mirror, because the orchestrator will still believe its answers (R6a). An operator who wants
#: a different one passes ``work_shape`` to :func:`create_mirror`; this module does not choose
#: the tier for them, it only picks a defensible default.
DEFAULT_WORK_SHAPE = "work-medium"

#: Default distillation bound for one return. Roughly a page of conclusions.
DEFAULT_MAX_RETURN_BYTES = 4 * 1024

#: The largest bound a request may declare. The mirror protects the orchestrator's *time*, not
#: its context: the orchestrator still reads whatever comes back, so a mirror handing back
#: 50 KB degrades the main session anyway. A bound is not eroded by deletion, it is eroded by
#: being raised, so the declaration itself is capped.
MAX_DECLARABLE_RETURN_BYTES = 16 * 1024

#: Instructions are prose, not payloads. The cap also bounds the predicate-declaration scan.
MAX_INSTRUCTION_BYTES = 32 * 1024

#: Upper bound on JSON decode attempts while scanning an instruction for a predicate
#: declaration, so a pathological instruction of open braces cannot make the scan quadratic.
_MAX_DECODE_ATTEMPTS = 512

#: Context-management commands, per runtime. Only Claude Code's are established in this
#: repository (``docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md``).
#: Every other runtime is refused rather than guessed: sending an unrecognised slash command
#: to a coding agent puts prose in its input, which is a silent no-op that looks like a reset.
CONTEXT_COMMANDS: dict[str, dict[str, str]] = {
    "claude": {"compact": "/compact", "clear": "/clear"},
}

CONTEXT_ACTIONS = ("compact", "clear")

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_REQUEST_LINE_RE = re.compile(r"^[ \t]*request:[ \t]*([A-Za-z0-9._-]+)[ \t]*$", re.MULTILINE)


# --------------------------------------------------------------------------- errors


class MirrorError(RuntimeError):
    """Base error for mirror operations."""


class PredicateInMirrorError(MirrorError):
    """A request would route a validity judgement through the mirror (KTD6, R6b)."""


class DistillationBoundError(MirrorError):
    """A return exceeded its declared bound, or a declaration exceeded the ceiling (R6).

    The message carries the byte count and never the material: an error that quoted the
    oversized return would put it in the orchestrator's context, which is the absorption the
    rejection exists to prevent.
    """


class MirrorBusyError(MirrorError):
    """A request was submitted while another is outstanding.

    An explicit refusal, not a silent drop (R8): the caller decides whether to wait, park the
    operator's question with a reason, or collect the outstanding return first.
    """


class NoReturnAvailableError(MirrorError):
    """No complete return for the outstanding request is present in the mirror's pane yet."""


class MirrorQuietTooLongError(MirrorError):
    """The mirror has been silent past its declared tolerance while a request is outstanding.

    This is the divergence a hung mirror produces. It is advisory: raising it changes no
    register state.
    """


class MirrorNotArmedError(MirrorError):
    """The mirror row declares no quiet bound, so hang detection is not armed.

    Distinct from "healthy" on purpose. A detector that reports healthy when it was never
    given a threshold is how a hang detector rots into decoration.
    """


class MirrorNotRegisteredError(MirrorError):
    """The named row does not exist, or is not a mirror row."""


class UnsupportedContextCommandError(MirrorError):
    """This runtime's context-management commands are not established in this repository."""


class ColumnOwnershipError(MirrorError):
    """This module attempted to write a column it does not own."""


# --------------------------------------------------------------------------- request schema


def _safe_token(value: str, *, label: str) -> str:
    if not value or not _SAFE_TOKEN_RE.match(value):
        raise MirrorError(f"{label} {value!r} must be a non-empty [A-Za-z0-9._-]+ token")
    return value


def _decoded_objects(text: str) -> list[dict[str, Any]]:
    """Every JSON object embedded in ``text``, up to a bounded number of decode attempts."""
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    position = 0
    attempts = 0
    while attempts < _MAX_DECODE_ATTEMPTS:
        start = text.find("{", position)
        if start < 0:
            break
        attempts += 1
        position = start + 1
        try:
            value, _ = decoder.raw_decode(text[start:])
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            found.append(value)
    return found


def carries_predicate_declaration(text: str) -> bool:
    """Whether ``text`` embeds a predicate declaration.

    A predicate *is* a JSON object with an ``argv`` key -- that is its whole schema -- so this
    detects the thing itself rather than words about it. It deliberately does not import
    ``completion``: this module must contain no route to the code that runs predicates, and a
    structural test asserts that.
    """
    return any("argv" in value for value in _decoded_objects(text))


@dataclass(frozen=True)
class MirrorRequest:
    """One unit of the orchestrator's own work, handed to the mirror.

    ``kind`` is validated against a closed vocabulary rather than being free text, so routing
    a judgement to the mirror is refused at the type boundary rather than discovered later.
    """

    request_id: str
    kind: str
    instruction: str
    max_return_bytes: int = DEFAULT_MAX_RETURN_BYTES

    def __post_init__(self) -> None:
        _safe_token(self.request_id, label="request_id")
        if self.kind in DECIDING_KINDS:
            raise PredicateInMirrorError(
                f"request kind {self.kind!r} asks the mirror for a judgement; the mirror does "
                "unbounded reading and never decides. Run the validity predicate inline with "
                "completion.evaluate_completion, where the orchestrator reads the evidence "
                "itself"
            )
        if self.kind not in READING_KINDS:
            raise MirrorError(
                f"request kind {self.kind!r} is not one of {list(READING_KINDS)}; the "
                "vocabulary is closed and every member is reading work"
            )
        if not self.instruction.strip():
            raise MirrorError("request instruction must be non-empty")
        instruction_bytes = len(self.instruction.encode("utf-8"))
        if instruction_bytes > MAX_INSTRUCTION_BYTES:
            raise MirrorError(
                f"request instruction is {instruction_bytes} bytes, over the "
                f"{MAX_INSTRUCTION_BYTES}-byte cap; an instruction is prose, not a payload"
            )
        if carries_predicate_declaration(self.instruction):
            raise PredicateInMirrorError(
                "request instruction carries a predicate declaration (a JSON object with an "
                "'argv' key); a predicate runs inline in the orchestrator's own process tree, "
                "never in the mirror"
            )
        if isinstance(self.max_return_bytes, bool) or not isinstance(self.max_return_bytes, int):
            raise MirrorError("max_return_bytes must be an integer")
        if self.max_return_bytes <= 0:
            raise MirrorError("max_return_bytes must be positive")
        if self.max_return_bytes > MAX_DECLARABLE_RETURN_BYTES:
            raise DistillationBoundError(
                f"declared max_return_bytes {self.max_return_bytes} exceeds the "
                f"{MAX_DECLARABLE_RETURN_BYTES}-byte ceiling; the mirror returns distilled "
                "conclusions, and a bound that can be raised without limit is not a bound"
            )


@dataclass(frozen=True)
class MirrorReturn:
    """One accepted distilled return."""

    request_id: str
    material: str
    byte_length: int


@dataclass(frozen=True)
class MirrorLiveness:
    """What the clock observed about the mirror row."""

    state: str
    quiet_seconds: float | None
    max_quiet_seconds: float
    request_id: str | None


@dataclass(frozen=True)
class MirrorSession:
    """A live mirror: where it runs, how it marks a return, and what watches it."""

    run_id: str
    row_id: str
    root: Path
    cwd: Path
    runtime: str
    pane_id: str
    tab_id: str
    nonce: str
    max_quiet_seconds: float
    open_marker: str
    close_marker: str
    subscriptions: tuple[dict[str, Any], ...]


# --------------------------------------------------------------------------- owned writes


def _write_owned(
    root: Path, row_id: str, fields: Mapping[str, Any], *, run_id: str
) -> dict[str, Any]:
    """The single register-write seam for this module, refusing any column it does not own.

    Every write this module performs goes through here. A shared column written by more than
    one module, with the ownership recorded nowhere checkable, is the defect this guards
    against, so the ownership is asserted at runtime rather than described in a comment.
    """
    foreign = sorted(set(fields) - set(OWNED_COLUMNS))
    if foreign:
        raise ColumnOwnershipError(
            f"the mirror module does not own {foreign}; it writes only {list(OWNED_COLUMNS)} "
            "and only on the mirror's own row"
        )
    return register_store.upsert_row(root, row_id, dict(fields), run_id=run_id)


def _mirror_row(root: Path, *, run_id: str, row_id: str) -> dict[str, Any]:
    row = register_store.read_rows(root, run_id=run_id).get(row_id)
    if row is None:
        raise MirrorNotRegisteredError(f"run {run_id!r} has no row {row_id!r}")
    if row.get("role") != MIRROR_ROLE:
        raise MirrorNotRegisteredError(
            f"row {row_id!r} has role {row.get('role')!r}, not {MIRROR_ROLE!r}; the mirror row "
            "is identified by 'role', because 'agent' carries the launcher's agent name"
        )
    return row


def find_mirror_rows(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Select the mirror rows from a register read, by the column this module owns."""
    return {row_id: dict(row) for row_id, row in rows.items() if row.get("role") == MIRROR_ROLE}


# --------------------------------------------------------------------------- the charter


def _markers(run_id: str, row_id: str, nonce: str) -> tuple[str, str]:
    open_marker = subscriber.make_sentinel(run_id, row_id, "mirror-return-open", nonce=nonce)
    close_marker = subscriber.make_sentinel(run_id, row_id, "mirror-return-close", nonce=nonce)
    return open_marker, close_marker


def mirror_charter(open_marker: str, close_marker: str, *, max_return_bytes: int) -> str:
    """The mirror's standing instruction, dispatched once when the session is confirmed ready.

    Both markers are described as parts to be joined at print time rather than written out,
    so an echo of this text cannot itself satisfy a return match. The final assertion is not
    decoration: if a future edit interpolates an assembled marker, the charter would make
    every echo look like a completed return.
    """
    charter = (
        "You are the orchestrator's mirror. You do the orchestrator's own work -- synthesis, "
        "comparison, and bulk reading -- so that the orchestrator's channel with its operator "
        "stays answerable. You are not one of the children; children do the outcome's work.\n"
        "\n"
        "Standing rules, which hold for every request you will be given:\n"
        "\n"
        "1. You never address the operator. Your reader is the orchestrator, always. There is "
        "one voice on the operator's channel and it is not yours.\n"
        "2. You never evaluate a validity predicate and never return a verdict on whether "
        "work is complete, correct, or acceptable. The orchestrator runs those checks itself, "
        "where it reads the evidence. If a request asks you for one, say that you are "
        "refusing it and why, inside the return block, and return nothing else.\n"
        "3. You return distilled conclusions, never raw material. Each request names a byte "
        f"bound; the current default is {max_return_bytes} bytes. A return over its bound is "
        "rejected whole, not truncated, so a long answer is not a partial success -- it is a "
        "lost round trip. Distil first.\n"
        "4. You handle one request at a time, and you print exactly one return block per "
        "request.\n"
        "\n"
        "The return protocol. When you have an answer, print, in this order and nothing "
        "else between them:\n"
        "  (a) the OPEN line, assembled as described below;\n"
        "  (b) a line reading `request: ` followed by the request id you were given;\n"
        "  (c) your distilled conclusion;\n"
        "  (d) the CLOSE line, assembled as described below.\n"
        "\n"
        "OPEN line -- "
        + subscriber.sentinel_assembly_instructions(
            open_marker, when="you begin printing a return block"
        )
        + "\n\nCLOSE line -- "
        + subscriber.sentinel_assembly_instructions(
            close_marker, when="you have finished printing a return block"
        )
    )
    for marker in (open_marker, close_marker):
        if marker in charter:
            raise AssertionError("an assembled return marker must not appear in the charter")
    return charter


def _request_prompt(request: MirrorRequest) -> str:
    return (
        f"Mirror request {request.request_id} ({request.kind}). "
        f"Return bound: {request.max_return_bytes} bytes, enforced by rejection.\n"
        f"Print `request: {request.request_id}` as the first line inside the return block.\n"
        "\n" + request.instruction
    )


# --------------------------------------------------------------------------- creation


def mirror_spec(
    *,
    run_id: str,
    row_id: str,
    runtime: str,
    workspace: str,
    charter: str,
    work_shape: str = DEFAULT_WORK_SHAPE,
    readiness_timeout: float = 30.0,
    environment_command: Sequence[str] = (),
) -> session_lifecycle.ChildSpec:
    """The mirror's launch specification.

    ``mutating=False`` and an empty scope: the mirror reads. It stays in the ambient checkout
    rather than taking a worktree, and it declares no artifact, so ``check_completion_scope``
    -- which runs from completion, on children that produce artifacts -- never runs on it.
    What that means in practice is that nothing here *prevents* a mirror from writing to the
    repository; the containment is its runtime's ordinary workspace-write posture, the same
    one every child gets, plus the charter.
    """
    return session_lifecycle.ChildSpec(
        run_id=run_id,
        row_id=row_id,
        runtime=runtime,
        work_shape=work_shape,
        instruction=charter,
        scope=(),
        mutating=False,
        workspace=workspace,
        readiness_timeout=readiness_timeout,
        environment_command=tuple(environment_command),
    )


def create_mirror(
    root: Path,
    *,
    run_id: str,
    row_id: str,
    runtime: str,
    workspace: str,
    max_quiet_seconds: float,
    wrapper: session_lifecycle.AgentWrapper,
    herdr: session_lifecycle.HerdrControl,
    git: session_lifecycle.GitLanding,
    interaction: session_lifecycle.HerdrInteraction,
    work_shape: str = DEFAULT_WORK_SHAPE,
    max_return_bytes: int = DEFAULT_MAX_RETURN_BYTES,
    nonce: str | None = None,
    readiness_timeout: float = 30.0,
    environment_command: Sequence[str] = (),
    sentinel_nonce: str | None = None,
) -> MirrorSession:
    """Register the mirror, then launch and confirm it through the ordinary session path.

    The register write comes **first**, before any launch side effect, so the mirror has a row
    from creation rather than from first use (R6c). A launch that fails therefore leaves a
    registered mirror the operator can see, not an invisible one.

    The mirror is launched through ``session_lifecycle.launch_child`` and confirmed through
    ``confirm_ready`` -- the same write-ahead ordering, label recovery, trust-prompt check and
    nonce-bound readiness sentinel every child gets. It is a session; it does not get a
    private launch path.
    """
    root = register_store.canonical_work_location(root)
    _safe_token(run_id, label="run_id")
    _safe_token(row_id, label="row_id")
    if not isinstance(max_quiet_seconds, int | float) or isinstance(max_quiet_seconds, bool):
        raise MirrorError("max_quiet_seconds must be a number")
    if max_quiet_seconds <= 0:
        raise MirrorError("max_quiet_seconds must be positive; the clock is the only detector")
    if max_return_bytes > MAX_DECLARABLE_RETURN_BYTES:
        raise DistillationBoundError(
            f"default max_return_bytes {max_return_bytes} exceeds the "
            f"{MAX_DECLARABLE_RETURN_BYTES}-byte ceiling"
        )

    resolved_nonce = nonce or uuid.uuid4().hex
    open_marker, close_marker = _markers(run_id, row_id, resolved_nonce)

    _write_owned(
        root,
        row_id,
        {
            "role": MIRROR_ROLE,
            "max_quiet_seconds": float(max_quiet_seconds),
            "mirror_request": None,
            "mirror_last_return": None,
        },
        run_id=run_id,
    )

    spec = mirror_spec(
        run_id=run_id,
        row_id=row_id,
        runtime=runtime,
        workspace=workspace,
        charter=mirror_charter(open_marker, close_marker, max_return_bytes=max_return_bytes),
        work_shape=work_shape,
        readiness_timeout=readiness_timeout,
        environment_command=environment_command,
    )
    identity, landing, resolution = session_lifecycle.launch_child(
        root, spec, wrapper=wrapper, herdr=herdr, git=git
    )
    session_lifecycle.confirm_ready(
        root,
        spec,
        identity,
        landing,
        resolution,
        herdr=herdr,
        interaction=interaction,
        git=git,
        sentinel_nonce=sentinel_nonce,
    )
    return MirrorSession(
        run_id=run_id,
        row_id=row_id,
        root=root,
        cwd=landing.cwd,
        runtime=runtime,
        pane_id=identity.pane_id,
        tab_id=identity.tab_id,
        nonce=resolved_nonce,
        max_quiet_seconds=float(max_quiet_seconds),
        open_marker=open_marker,
        close_marker=close_marker,
        subscriptions=(subscriber.output_match_subscription(identity.pane_id, close_marker),),
    )


# --------------------------------------------------------------------------- dispatch


def outstanding_request(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """The request the mirror currently has in flight, or ``None`` when it is idle."""
    value = row.get("mirror_request")
    return dict(value) if isinstance(value, Mapping) else None


def dispatch_request(
    session: MirrorSession,
    request: MirrorRequest,
    *,
    herdr: session_lifecycle.HerdrControl,
    now: float,
) -> str:
    """Send one request to the mirror and return immediately.

    Nothing here waits for a return: there is no subscription held open, no pane read, and no
    timeout parameter, because a dispatch that could block is a dispatch that will eventually
    block the operator's channel. The return arrives later, as a ``pane.output_matched`` event
    on the subscription :func:`create_mirror` built, and is picked up by :func:`collect_return`.

    The register write is **write-ahead**: the outstanding request is durable before the line
    is sent. If the send then fails, the record stays and the quiet clock is armed, which is
    correct -- a failed send does not establish that nothing was delivered, and a mirror whose
    state is unknown should raise an alarm rather than look idle.

    What this function does not prove: that the orchestrator can answer the operator while a
    request is outstanding. That is a property of the calling control flow, not of this
    dispatch, and it is established end to end rather than here.
    """
    row = _mirror_row(session.root, run_id=session.run_id, row_id=session.row_id)
    existing = outstanding_request(row)
    if existing is not None:
        raise MirrorBusyError(
            f"the mirror already has request {existing.get('request_id')!r} outstanding; "
            "collect its return or park this one with a reason -- it is not dropped"
        )
    _write_owned(
        session.root,
        session.row_id,
        {
            "mirror_request": {
                "request_id": request.request_id,
                "kind": request.kind,
                "dispatched_at": float(now),
                "max_return_bytes": request.max_return_bytes,
            }
        },
        run_id=session.run_id,
    )
    herdr.send_line(session.pane_id, _request_prompt(request), cwd=session.cwd)
    return request.request_id


# --------------------------------------------------------------------------- collection


def _extract_block(text: str, open_marker: str, close_marker: str) -> str | None:
    """The most recent complete return block, or ``None`` if there is not one yet."""
    close_at = text.rfind(close_marker)
    if close_at < 0:
        return None
    open_at = text.rfind(open_marker, 0, close_at)
    if open_at < 0:
        return None
    return text[open_at + len(open_marker) : close_at]


def _bound_block_to_request(block: str, request_id: str) -> str | None:
    """The block's material when it names ``request_id``, else ``None``.

    The markers are stable for the mirror's life, so a previous request's block is still in
    the pane buffer. Without this binding the orchestrator would read a stale answer as the
    current one, which is the same class of error as an artifact left over from an earlier
    run satisfying a predicate.
    """
    match = _REQUEST_LINE_RE.search(block)
    if match is None or match.group(1) != request_id:
        return None
    return block[match.end() :].strip()


def collect_return(
    session: MirrorSession,
    *,
    herdr: session_lifecycle.HerdrControl,
    now: float,
) -> MirrorReturn:
    """Read the mirror's return for the outstanding request, enforcing the byte bound.

    A return over its declared bound is rejected, not truncated: the caller receives an
    exception carrying the byte count and never the material, and the request is closed out
    with a durable record of the rejection. The mirror itself is left exactly as it was --
    still ready, still holding its context, phase untouched -- so the orchestrator can re-ask
    with a tighter instruction.
    """
    row = _mirror_row(session.root, run_id=session.run_id, row_id=session.row_id)
    request = outstanding_request(row)
    if request is None:
        raise NoReturnAvailableError(
            f"the mirror row {session.row_id!r} has no outstanding request to collect"
        )
    request_id = str(request.get("request_id"))
    bound = request.get("max_return_bytes", DEFAULT_MAX_RETURN_BYTES)
    max_return_bytes = (
        int(bound)
        if isinstance(bound, int) and not isinstance(bound, bool)
        else (DEFAULT_MAX_RETURN_BYTES)
    )

    text = herdr.pane_text(session.pane_id, cwd=session.cwd)
    block = _extract_block(text, session.open_marker, session.close_marker)
    if block is None:
        raise NoReturnAvailableError(
            f"the mirror has not printed a complete return block for {request_id!r} yet"
        )
    material = _bound_block_to_request(block, request_id)
    if material is None:
        raise NoReturnAvailableError(
            f"the most recent return block does not name request {request_id!r}; it belongs to "
            "an earlier request"
        )

    byte_length = len(material.encode("utf-8"))
    accepted = byte_length <= max_return_bytes
    _write_owned(
        session.root,
        session.row_id,
        {
            "mirror_request": None,
            "mirror_last_return": {
                "request_id": request_id,
                "outcome": "accepted" if accepted else "rejected_oversized",
                "byte_length": byte_length,
                "max_return_bytes": max_return_bytes,
                "at": float(now),
            },
        },
        run_id=session.run_id,
    )
    if not accepted:
        raise DistillationBoundError(
            f"the mirror's return for request {request_id!r} is {byte_length} bytes against a "
            f"declared bound of {max_return_bytes}; it is rejected whole rather than "
            "truncated, and its content is deliberately not reproduced here"
        )
    return MirrorReturn(request_id=request_id, material=material, byte_length=byte_length)


# --------------------------------------------------------------------------- the clock


def check_liveness(
    root: Path,
    *,
    run_id: str,
    row_id: str,
    now: float,
) -> MirrorLiveness:
    """Compare the mirror's silence against its declared tolerance.

    Reads only. Raising changes no register state, closes no tab, and demotes no phase: what
    to do about a quiet mirror is a decision, and this module does not decide.

    Raises :class:`MirrorNotArmedError` rather than reporting health when the row declares no
    ``max_quiet_seconds``, and reports ``idle`` without alarming when no request is
    outstanding, because a mirror between requests is legitimately silent forever.
    """
    row = _mirror_row(root, run_id=run_id, row_id=row_id)
    bound = row.get("max_quiet_seconds")
    if isinstance(bound, bool) or not isinstance(bound, int | float):
        raise MirrorNotArmedError(
            f"mirror row {row_id!r} declares no max_quiet_seconds; hang detection is not "
            "armed, which is not the same as the mirror being healthy"
        )
    request = outstanding_request(row)
    if request is None:
        return MirrorLiveness(
            state="idle", quiet_seconds=None, max_quiet_seconds=float(bound), request_id=None
        )

    dispatched_at = request.get("dispatched_at")
    reference = float(dispatched_at) if isinstance(dispatched_at, int | float) else None
    last_event_at = row.get("last_event_at")
    if isinstance(last_event_at, int | float) and not isinstance(last_event_at, bool):
        reference = (
            float(last_event_at) if reference is None else max(reference, float(last_event_at))
        )
    if reference is None:
        raise MirrorNotArmedError(
            f"mirror row {row_id!r} has a request outstanding with no dispatch instant and no "
            "observed event; there is nothing to measure silence from"
        )

    quiet_seconds = float(now) - reference
    request_id = request.get("request_id")
    if quiet_seconds > float(bound):
        raise MirrorQuietTooLongError(
            f"the mirror has been silent for {quiet_seconds:.1f}s against a declared tolerance "
            f"of {float(bound):.1f}s while request {request_id!r} is outstanding; every child "
            "still looks healthy and nothing disagrees, which is what a hung mirror looks like"
        )
    return MirrorLiveness(
        state="working",
        quiet_seconds=quiet_seconds,
        max_quiet_seconds=float(bound),
        request_id=str(request_id) if isinstance(request_id, str) else None,
    )


# --------------------------------------------------------------------------- context, status


def request_context_reset(
    session: MirrorSession,
    action: str,
    *,
    herdr: session_lifecycle.HerdrControl,
) -> str:
    """Direct the mirror to compact or clear its context, deliberately rather than by drift.

    R6a: the mirror's context is a managed resource, because a mirror that has silently
    degraded is worse than no mirror -- the orchestrator will still believe its answers.

    Refused while a request is outstanding: resetting context mid-request discards the work
    that request is paying for, and the return would never arrive.
    """
    if action not in CONTEXT_ACTIONS:
        raise MirrorError(f"context action {action!r} is not one of {list(CONTEXT_ACTIONS)}")
    commands = CONTEXT_COMMANDS.get(session.runtime)
    if commands is None:
        raise UnsupportedContextCommandError(
            f"context-management commands for runtime {session.runtime!r} are not established "
            "here; sending a slash command a runtime does not recognise puts prose in its "
            "input, which is a silent no-op that looks like a reset"
        )
    row = _mirror_row(session.root, run_id=session.run_id, row_id=session.row_id)
    if outstanding_request(row) is not None:
        raise MirrorBusyError(
            "the mirror has a request outstanding; resetting its context now would discard "
            "the work in flight"
        )
    command = commands[action]
    herdr.send_line(session.pane_id, command, cwd=session.cwd)
    return command


def mirror_status(root: Path, *, run_id: str, row_id: str) -> dict[str, Any]:
    """The mirror-owned view of one mirror row, for an operator report or a resumed run.

    Surfaces the durable record of the last return -- including a rejected one. A rejection
    that left no trace would be indistinguishable from a return that never happened, which is
    how "rejected, not absorbed" quietly becomes "silently dropped".
    """
    row = _mirror_row(root, run_id=run_id, row_id=row_id)
    last_return = row.get("mirror_last_return")
    return {
        "row_id": row_id,
        "run_id": run_id,
        "role": row.get("role"),
        "max_quiet_seconds": row.get("max_quiet_seconds"),
        "last_event_at": row.get("last_event_at"),
        "outstanding_request": outstanding_request(row),
        "last_return": dict(last_return) if isinstance(last_return, Mapping) else None,
    }
