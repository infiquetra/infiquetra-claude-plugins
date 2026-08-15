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

**The mirror is never *asked* for a verdict through this API, and a verdict it volunteered
would still not be evidence (KTD6, R6b).** Read that sentence carefully, because it is
deliberately weaker than "the validity predicate never runs in the mirror" — which is what an
earlier revision of this module claimed, and which is not true.

A predicate is a bounded mechanical check and the orchestrator runs it inline, where it sees
the bytes. Routing it through the mirror turns verification back into a claim: the mirror
reports a pass, the orchestrator never reads the evidence, and the highest-severity failure
class reappears one layer up with no second reader. What is actually enforced here:

1. :class:`MirrorRequest` accepts a closed vocabulary of *reading* kinds. Deciding kinds are
   enumerated in :data:`DECIDING_KINDS` and refused by name.
2. An instruction carrying a machine-readable predicate *declaration* is refused, in the
   forms :func:`carries_predicate_declaration` documents: an embedded JSON object with an
   ``argv`` key, the same declaration written as a YAML mapping, and either of those wrapped
   in Base64. The scan **fails closed**: an instruction whose scan budget is exhausted before
   the text is fully examined is refused, not passed. "I could not finish looking" is not a
   pass.
3. This module executes no program and does not import ``completion``.

**What none of that establishes, stated plainly because the previous revision got it wrong.**

- Guard 2 detects *declarations*, not *intent*. An instruction that describes a check in
  ordinary English — "run the tests and tell me whether they pass" — is not detectable by any
  scanner, and this module does not pretend otherwise. A mirror so instructed can run the
  check, because the live agent on the far side of ``HerdrControl.send_line`` is itself a
  program executor. Guard 3 constrains *this module*; it does not constrain the session this
  module talks to.
- Not writing ``phase`` is therefore **not** the containment an earlier revision claimed it
  was. It stops a mirror's opinion becoming a ``verified`` row *through this module*; it does
  not stop a mirror producing a claimed verdict, and a claimed verdict with no second reader
  is exactly the failure R6b names.

What genuinely remains true is narrower and worth stating in its own right:
``completion.evaluate_completion`` is the only path to ``verified``; no function here returns
anything completion accepts as evidence; and a mirror return is bounded material the
orchestrator reads with its own eyes rather than a verdict delivered behind its back. The
control for the prose case is the written routing rule in
``references/operator-channel.md`` — a rule, honestly labelled as a rule, not a mechanism
mislabelled as a guarantee.

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

**What the clock asserts depends on which feed is running, and that distinction is the whole
of it.** It asserts that this row has not been *observed* emitting for longer than the operator
declared it should ever be silent. Two things can supply an observation:

- ``last_event_at`` -- written by the subscriber when a ``pane.output_matched`` event carries a
  sentinel matching an active subscription. The mirror's only subscribed sentinel is its return
  marker, so within a single request this never advances. On its own it makes
  ``max_quiet_seconds`` a per-request tolerance rather than a within-request liveness probe.
- ``mirror_pane_activity`` -- herdr's pane-output ``revision`` counter, read from a snapshot by
  :func:`observe_pane_activity`. **This is what distinguishes a mirror that is quiet because it
  is thinking from one that is quiet because it is dead.** An earlier revision of this module
  said nothing could; that was too strong. ``register.py`` names this counter as the feed for
  exactly this and names this unit as its reader, and the journal entry
  ``LEARNINGS.md#pane-revision-is-the-liveness-signal`` carries the measurement behind it.

:class:`MirrorLiveness` reports which feed the answer rested on, so "working" from a stale clock
and "working" from a live one are not the same word.

- A within-request heartbeat *subscription* is still deliberately not built: the subscriber
  wakes the orchestrator on every handled event, so a heartbeat subscription would wake the
  operator's channel on a timer -- the exact channel-load failure this unit exists to prevent.
  A snapshot read goes nowhere near that path, which is why the revision feed is a supervision
  read rather than a subscription.
- Combining the clock with herdr's ``agent_status`` would make it worse, not better. Vendor
  lifecycle detectors are wrong in vendor-specific ways -- one runtime reports ``idle`` while
  working, another reported settled from launch through completion -- so a detector agreeing
  with the clock would supply false confidence rather than a second reader. Pane revision is
  not in that category: it counts output, not opinion.

The alarm is therefore advisory: :func:`check_liveness` reads and raises. It writes nothing,
kills nothing, and demotes nothing. What to do about a quiet mirror -- probe the pane, re-ask,
replace it -- is a decision, and decisions are the orchestrator's.

An *idle* mirror is legitimately silent forever, so the clock is armed only while a request is
outstanding. That is what ``mirror_request`` records.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
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
#:
#: ``mirror_identity`` and ``mirror_subscription`` exist so a restarted orchestrator can rebuild
#: a live mirror from its row alone. Without them the nonce and return markers lived only in an
#: in-memory :class:`MirrorSession`, so an orchestrator that died could not collect from a mirror
#: that was still running — which contradicts R6a's "persistent for the life of the
#: orchestration". ``mirror_subscription`` additionally records whether the subscription this
#: mirror needs was ever confirmed installed, which is what turns a missing wire from a silent
#: void into a raised error (see :func:`acknowledge_subscription`).
#:
#: ``mirror_pane_activity`` is this module's own liveness mark, written from herdr's pane-output
#: ``revision`` counter by :func:`observe_pane_activity`. It is deliberately **not**
#: ``last_event_at``: that column already has a writer in the subscriber, and a second writer of
#: one column with the ownership recorded nowhere checkable is the defect this codebase has paid
#: for most. :func:`check_liveness` reads both and takes the later, so nothing is lost by keeping
#: the two feeds in two columns — and if the register's ownership table later assigns
#: ``last_event_at`` a single owner who is the revision reader, this column folds into it.
OWNED_COLUMNS = (
    "role",
    "max_quiet_seconds",
    "mirror_request",
    "mirror_last_return",
    "mirror_identity",
    "mirror_subscription",
    "mirror_pane_activity",
)

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

#: Upper bound on JSON decode attempts while scanning one text for a predicate declaration, so
#: a pathological instruction of open braces cannot make the scan quadratic. Exhausting it is
#: **not** a pass: :func:`carries_predicate_declaration` reports the scan as incomplete and
#: :class:`MirrorRequest` refuses the instruction. An earlier revision returned "clean" on
#: exhaustion, which turned this denial-of-service bound into the bypass — 512 unmatched braces
#: ahead of a real declaration consumed the budget before the declaration was ever inspected.
_MAX_DECODE_ATTEMPTS = 512

#: Upper bound on Base64 blobs decoded and re-scanned per text, and the shortest run worth
#: decoding. A declaration is small; a long blob is not made safe by being long.
_MAX_BASE64_CANDIDATES = 16
_MIN_BASE64_RUN = 24

#: How deep a wrapped encoding is followed. One level covers "here is the check, Base64'd";
#: beyond that the scan stops and reports itself incomplete rather than recursing.
_MAX_SCAN_DEPTH = 2

#: The predicate schema's own key, bound to a value, in any serialisation that writes a key
#: next to a separator. ``completion.PredicateSpec`` is an object with an ``argv`` argument
#: vector, so ``argv`` immediately followed by ``:`` or ``=`` is the declaration's signature
#: whether it is written as JSON, YAML block or flow, TOML, or a Python literal -- including
#: when it is quoted or backslash-escaped inside another string.
#:
#: The lookbehind is what keeps this from firing on ordinary prose about this codebase:
#: ``permission_argv:`` does not match, because ``argv`` there is preceded by an underscore.
_ARGV_KEY_RE = re.compile(r"(?<![A-Za-z0-9_])argv[\"'\\\s]*[:=]")

#: ``\uXXXX`` escapes, so a declaration written with escaped braces is examined as the text it
#: denotes rather than as the literal backslash sequence.
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")

#: A run of Base64 alphabet long enough to be worth decoding.
_BASE64_RUN_RE = re.compile(rf"[A-Za-z0-9+/=]{{{_MIN_BASE64_RUN},}}")

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


class MirrorSubscriptionMissingError(MirrorError):
    """The subscription this mirror needs is not among those the subscriber was given.

    Without it the mirror's return never reaches the orchestrator and ``last_event_at`` never
    advances, so the mirror looks like it is thinking until the quiet bound trips and then
    reports the wrong cause. Raising here names the real one.
    """


class MirrorSubscriptionUnconfirmedError(MirrorError):
    """A request is outstanding but nothing ever confirmed the mirror's subscription.

    Deliberately distinct from :class:`MirrorQuietTooLongError`. A mirror nobody is listening to
    and a mirror that has hung produce the same silence, and treating the first as the second
    sends the operator hunting a hang that is not there.
    """


class MirrorWroteRepositoryError(MirrorError):
    """Repository-visible paths changed while the mirror held a request.

    Raised only by the explicit assertion helper. :func:`collect_return` records the observation
    and hands it back rather than raising, because the mirror reads the operator's own working
    tree and attribution in a shared checkout is not established — see
    :func:`repository_change_observation`.
    """


# --------------------------------------------------------------------------- request schema


def _safe_token(value: str, *, label: str) -> str:
    if not value or not _SAFE_TOKEN_RE.match(value):
        raise MirrorError(f"{label} {value!r} must be a non-empty [A-Za-z0-9._-]+ token")
    return value


def _finite_seconds(value: Any, *, label: str) -> float:
    """Require a real number of seconds, refusing NaN and the infinities.

    Every ordered comparison with NaN is false, so a NaN threshold makes ``quiet > bound`` false
    forever and a dead mirror reports ``working``; positive infinity does the same thing
    honestly. Either one reaches the affirmative state :class:`MirrorNotArmedError` exists to
    prevent, by a different door. A clock input that is not finite is not a clock input.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MirrorNotArmedError(f"{label} must be a number, not {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise MirrorNotArmedError(
            f"{label} is {number}, which is not a finite number of seconds; a threshold no "
            "silence can exceed is not a threshold, and reporting health from one would be "
            "reporting a state that was never established"
        )
    return number


@dataclass(frozen=True)
class ScanResult:
    """What a predicate-declaration scan found, and whether it finished looking.

    ``complete`` is the field that matters. A scan that ran out of budget has established
    nothing, and reporting it as ``found=False`` would be reporting an absence it never
    verified.
    """

    found: bool
    complete: bool
    form: str | None = None

    @property
    def suspicious(self) -> bool:
        """True when the text must be refused: a declaration was found, or the scan gave up."""
        return self.found or not self.complete


def _decoded_objects(text: str) -> tuple[list[dict[str, Any]], bool]:
    """Every JSON object embedded in ``text``, and whether the scan reached the end.

    The second element is the honest part. Returning only the list made a budget exhaustion
    indistinguishable from a clean text, which is how the bound became the bypass.
    """
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    position = 0
    attempts = 0
    while True:
        start = text.find("{", position)
        if start < 0:
            return found, True
        if attempts >= _MAX_DECODE_ATTEMPTS:
            return found, False
        attempts += 1
        position = start + 1
        try:
            value, _ = decoder.raw_decode(text[start:])
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            found.append(value)


def _base64_payloads(text: str) -> tuple[list[str], bool]:
    """Decoded Base64 runs in ``text``, and whether every candidate run was examined."""
    payloads: list[str] = []
    candidates = _BASE64_RUN_RE.findall(text)
    complete = len(candidates) <= _MAX_BASE64_CANDIDATES
    for run in candidates[:_MAX_BASE64_CANDIDATES]:
        trimmed = run[: len(run) - len(run) % 4]
        if len(trimmed) < _MIN_BASE64_RUN:
            continue
        try:
            raw = base64.b64decode(trimmed, validate=True)
        except (binascii.Error, ValueError):
            continue
        try:
            payloads.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return payloads, complete


def _unescaped(text: str) -> str:
    """``text`` with ``\\uXXXX`` escapes resolved, so escaped braces are examined as braces."""
    return _UNICODE_ESCAPE_RE.sub(lambda match: chr(int(match.group(1), 16)), text)


def scan_for_predicate_declaration(text: str, *, _depth: int = 0) -> ScanResult:
    """Look for a machine-readable predicate declaration, and report whether the look finished.

    A predicate is a closed schema: an object with an ``argv`` argument vector. The detector
    keys on *the declaration's signature* — the name ``argv`` bound to a value — rather than on
    one serialisation of it, because enumerating serialisations is a race the enumerator loses:

    - **key** — ``argv`` immediately followed by ``:`` or ``=``. That is the same declaration
      written as JSON, as a YAML block or flow mapping, as TOML, as a Python literal, or quoted
      and backslash-escaped inside another string's value.
    - **json** — an embedded JSON object whose decoded keys include ``argv``. Kept alongside
      the key form because a decoder resolves an escaped key (``"\\u0061rgv"``) that no textual
      pattern can see.
    - **base64** — either of the above wrapped in Base64, decoded once and re-scanned.

    ``\\uXXXX`` escapes are resolved before any of that, so escaped braces are examined as the
    text they denote.

    Two things it does **not** cover, both named rather than papered over:

    - An instruction that describes a check in ordinary English. No scanner detects intent, and
      this module does not claim to. See the module docstring.
    - A declaration wrapped in **two** layers of encoding. One layer is followed; the second is
      a stated limit, not a claim of absence.

    It deliberately does not import ``completion``. This module must contain no route to the
    code that runs predicates, and a structural test asserts that, so the schema's signature is
    restated here rather than borrowed.
    """
    subject = _unescaped(text) if _UNICODE_ESCAPE_RE.search(text) else text
    if _ARGV_KEY_RE.search(subject):
        return ScanResult(found=True, complete=True, form="key")
    objects, json_complete = _decoded_objects(subject)
    if any("argv" in value for value in objects):
        return ScanResult(found=True, complete=True, form="json")
    if not json_complete:
        return ScanResult(found=False, complete=False)

    if _depth + 1 >= _MAX_SCAN_DEPTH:
        # One encoding level is covered; a declaration wrapped twice is the stated limit above.
        # Reporting *incomplete* here instead would refuse ordinary instructions, because a
        # repository path is itself a run of Base64-alphabet characters and every mention of
        # one would come down this branch.
        return ScanResult(found=False, complete=True)
    payloads, base64_complete = _base64_payloads(subject)
    for payload in payloads:
        inner = scan_for_predicate_declaration(payload, _depth=_depth + 1)
        if inner.found:
            return ScanResult(found=True, complete=True, form="base64")
        if not inner.complete:
            return ScanResult(found=False, complete=False)
    return ScanResult(found=False, complete=base64_complete)


def carries_predicate_declaration(text: str) -> bool:
    """Whether ``text`` must be refused as carrying a predicate declaration.

    True when a declaration was found **or** when the scan could not finish examining the text.
    "I could not finish looking" is not a pass.
    """
    return scan_for_predicate_declaration(text).suspicious


@dataclass(frozen=True)
class MirrorRequest:
    """One unit of the orchestrator's own work, handed to the mirror.

    ``kind`` is validated against a closed vocabulary rather than being free text, so routing
    a judgement to the mirror is refused at the type boundary rather than discovered later.

    Constructing one is necessary but not sufficient: :func:`dispatch_request` re-runs these
    checks on the object it is actually handed. A validation that lives only in a constructor
    is a suggestion, because the function that talks to the pane reads attributes and any
    object with the right attribute names satisfies it.
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
        scan = scan_for_predicate_declaration(self.instruction)
        if scan.found:
            raise PredicateInMirrorError(
                f"request instruction carries a predicate declaration ({scan.form} form: the "
                "name 'argv' bound to a value); a predicate runs inline in the orchestrator's "
                "own process tree, where it reads the evidence, never in the mirror"
            )
        if not scan.complete:
            raise PredicateInMirrorError(
                "request instruction could not be fully examined for a predicate declaration "
                "within the scan budget, so it is refused rather than passed; an instruction "
                "is prose, and prose does not exhaust this budget"
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
    """One accepted distilled return.

    ``repository_changes`` is what the repository-visible boundary observed between this
    request's dispatch and its return. Empty is the ordinary case. Non-empty is a report, not
    an accusation -- see :func:`repository_change_observation` for why it cannot be an
    accusation.
    """

    request_id: str
    material: str
    byte_length: int
    repository_changes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MirrorLiveness:
    """What the clock observed about the mirror row."""

    state: str
    quiet_seconds: float | None
    max_quiet_seconds: float
    request_id: str | None
    reference_source: str | None = None


@dataclass(frozen=True)
class MirrorActivity:
    """One comparison of the mirror pane's output counter against the last one recorded."""

    revision: int | None
    advanced: bool
    advanced_at: float | None


@dataclass(frozen=True)
class MirrorSession:
    """A live mirror: where it runs, how it marks a return, and what watches it.

    Rebuildable from the mirror's register row by :func:`resume_mirror`; an orchestrator that
    died and came back must not need a second durable store to talk to a session that is still
    running.
    """

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
    base_commit: str | None = None


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


def expected_subscription(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """The ``pane.output_matched`` subscription this mirror's returns require, from its row."""
    record = row.get("mirror_subscription")
    if not isinstance(record, Mapping):
        return None
    subscription = record.get("subscription")
    return dict(subscription) if isinstance(subscription, Mapping) else None


def subscription_acknowledged(row: Mapping[str, Any]) -> bool:
    """Whether anything has confirmed the mirror's subscription is actually installed."""
    record = row.get("mirror_subscription")
    if not isinstance(record, Mapping):
        return False
    return isinstance(record.get("acknowledged_at"), int | float) and not isinstance(
        record.get("acknowledged_at"), bool
    )


def acknowledge_subscription(
    session: MirrorSession,
    installed: Sequence[Mapping[str, Any]],
    *,
    now: float,
) -> dict[str, Any]:
    """Confirm the mirror's return subscription is among those the subscriber was given.

    Composition owns the subscriber process and the list it starts with. This is how it tells
    the mirror that the wire exists — and how the mirror refuses to pretend otherwise.

    Without this confirmation :func:`check_liveness` raises
    :class:`MirrorSubscriptionUnconfirmedError` rather than reporting a state. That is the
    whole point: a subscriber started without the mirror's subscription loses every return wake
    and every mid-request clock input, and the failure would otherwise appear much later,
    wearing the costume of a hung mirror. A cross-unit omission that announces itself is worth
    more than one that has to be deduced.
    """
    now = _finite_seconds(now, label="now")
    expected = expected_subscription(
        _mirror_row(session.root, run_id=session.run_id, row_id=session.row_id)
    )
    if expected is None:
        raise MirrorSubscriptionMissingError(
            f"mirror row {session.row_id!r} records no expected subscription; it was never "
            "launched, or its row predates this contract"
        )
    if not any(dict(candidate) == expected for candidate in installed):
        raise MirrorSubscriptionMissingError(
            f"the subscriber was given {len(installed)} subscription(s), none of which is the "
            f"mirror's return subscription on pane {expected.get('pane_id')!r}; its returns "
            "would never wake the orchestrator and its clock would never receive an event"
        )
    _write_owned(
        session.root,
        session.row_id,
        {"mirror_subscription": {"subscription": expected, "acknowledged_at": now}},
        run_id=session.run_id,
    )
    return expected


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

    **Nothing here prevents a mirror from writing to the repository.** ``mutating=False`` keeps
    the session in the ambient checkout; it is not a write fence. Every runtime receives its
    ordinary workspace-write posture, and inside the workspace nothing is contained. What this
    module provides is *detection*, not prevention: :func:`dispatch_request` records a
    repository-visible baseline and :func:`collect_return` reports what changed against it.

    Isolation was considered and rejected on purpose rather than on cost. A worktree would give
    the mirror a tree that is not the operator's -- same commit, none of the uncommitted work --
    and the mirror exists to read the operator's actual working state. Isolating it would make
    its answers describe a repository nobody is working in.
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
    _finite_seconds(max_quiet_seconds, label="max_quiet_seconds")
    if max_quiet_seconds <= 0:
        raise MirrorError("max_quiet_seconds must be positive; the clock is the only detector")
    if isinstance(max_return_bytes, bool) or not isinstance(max_return_bytes, int):
        raise MirrorError("max_return_bytes must be an integer")
    if max_return_bytes <= 0:
        # The charter interpolates this as the session's standing default. Zero would tell the
        # mirror that its default budget is nothing, making every return that honoured the
        # charter oversized.
        raise MirrorError("max_return_bytes must be positive")
    if max_return_bytes > MAX_DECLARABLE_RETURN_BYTES:
        raise DistillationBoundError(
            f"default max_return_bytes {max_return_bytes} exceeds the "
            f"{MAX_DECLARABLE_RETURN_BYTES}-byte ceiling"
        )

    resolved_nonce = nonce or uuid.uuid4().hex
    open_marker, close_marker = _markers(run_id, row_id, resolved_nonce)

    # The identity is durable before the launch side effect, alongside the row itself: it is
    # what a restarted orchestrator needs to talk to a mirror that outlived it. The
    # subscription is not written here because it names a pane the launcher has not returned
    # yet, and a placeholder pane id on the row would be a value that reads as configuration.
    _write_owned(
        root,
        row_id,
        {
            "role": MIRROR_ROLE,
            "max_quiet_seconds": float(max_quiet_seconds),
            "mirror_request": None,
            "mirror_last_return": None,
            "mirror_identity": {
                "nonce": resolved_nonce,
                "open_marker": open_marker,
                "close_marker": close_marker,
            },
            "mirror_subscription": None,
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
    subscription = subscriber.output_match_subscription(identity.pane_id, close_marker)
    _write_owned(
        root,
        row_id,
        {"mirror_subscription": {"subscription": subscription, "acknowledged_at": None}},
        run_id=run_id,
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
        subscriptions=(subscription,),
        base_commit=landing.base_commit,
    )


def resume_mirror(
    root: Path,
    *,
    run_id: str,
    row_id: str | None = None,
) -> MirrorSession:
    """Rebuild a live mirror's session from its register row alone.

    R6a makes the mirror persistent for the life of the orchestration. The pane and the
    subscriber survive an orchestrator that dies; before this existed, the orchestrator that
    came back could not talk to them, because the nonce and return markers lived only in the
    :class:`MirrorSession` that died with it. A session that outlives its only handle is not
    persistent in any useful sense.

    Everything here is read. The substrate columns (``pane_id``, ``tab_id``, ``cwd``,
    ``vendor``, ``base_commit``) belong to ``session_lifecycle`` and are read, never written;
    the identity and subscription come from this module's own columns.

    ``row_id`` may be omitted when the run has exactly one mirror, which is the ordinary case;
    it is located by the ``role`` column. Two mirrors in one run is refused rather than guessed.
    """
    root = register_store.canonical_work_location(root)
    rows = register_store.read_rows(root, run_id=run_id)
    if row_id is None:
        mirrors = find_mirror_rows(rows)
        if not mirrors:
            raise MirrorNotRegisteredError(f"run {run_id!r} has no mirror row to resume")
        if len(mirrors) > 1:
            raise MirrorNotRegisteredError(
                f"run {run_id!r} has {len(mirrors)} mirror rows ({sorted(mirrors)}); name the "
                "one to resume rather than letting this guess"
            )
        row_id = next(iter(mirrors))
    row = _mirror_row(root, run_id=run_id, row_id=row_id)

    identity = row.get("mirror_identity")
    if not isinstance(identity, Mapping):
        raise MirrorNotRegisteredError(
            f"mirror row {row_id!r} records no durable identity; it cannot be resumed"
        )
    values = {key: identity.get(key) for key in ("nonce", "open_marker", "close_marker")}
    missing = sorted(
        key for key, value in values.items() if not isinstance(value, str) or not value
    )
    if missing:
        raise MirrorNotRegisteredError(f"mirror row {row_id!r} identity lacks {missing}")

    substrate = {key: row.get(key) for key in ("pane_id", "tab_id", "cwd", "vendor")}
    absent = sorted(
        key for key, value in substrate.items() if not isinstance(value, str) or not value
    )
    if absent:
        raise MirrorNotRegisteredError(
            f"mirror row {row_id!r} lacks {absent}; the mirror was registered but never "
            "finished launching, so there is no live session to resume"
        )

    subscription = expected_subscription(row)
    base_commit = row.get("base_commit")
    return MirrorSession(
        run_id=run_id,
        row_id=row_id,
        root=root,
        cwd=Path(str(substrate["cwd"])),
        # ``vendor`` is what ``launch_child`` records the runtime as; ``agent`` is overwritten
        # with the launcher's uniquified name, so it is not the runtime.
        runtime=str(substrate["vendor"]),
        pane_id=str(substrate["pane_id"]),
        tab_id=str(substrate["tab_id"]),
        nonce=str(values["nonce"]),
        max_quiet_seconds=_finite_seconds(
            row.get("max_quiet_seconds"), label=f"mirror row {row_id!r} max_quiet_seconds"
        ),
        open_marker=str(values["open_marker"]),
        close_marker=str(values["close_marker"]),
        subscriptions=(subscription,) if subscription is not None else (),
        base_commit=str(base_commit) if isinstance(base_commit, str) else None,
    )


# --------------------------------------------------------------------------- dispatch


def outstanding_request(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """The request the mirror currently has in flight, or ``None`` when it is idle."""
    value = row.get("mirror_request")
    return dict(value) if isinstance(value, Mapping) else None


def _revalidated(request: Any) -> MirrorRequest:
    """Re-run :class:`MirrorRequest`'s checks on the object actually handed to dispatch.

    Rebuilding rather than trusting the instance matters twice: it refuses a look-alike that
    never ran the constructor, and it re-runs the checks even on a genuine instance, which a
    bare ``isinstance`` would not do for one built through ``object.__new__``.
    """
    if not isinstance(request, MirrorRequest):
        raise MirrorError(
            f"dispatch requires a MirrorRequest, not {type(request).__name__}; the kind "
            "vocabulary and the predicate-declaration scan live in its constructor, and an "
            "object that merely has the right attribute names has run neither"
        )
    return MirrorRequest(
        request_id=request.request_id,
        kind=request.kind,
        instruction=request.instruction,
        max_return_bytes=request.max_return_bytes,
    )


def _repository_fingerprint(
    session: MirrorSession, *, git: session_lifecycle.GitLanding
) -> dict[str, Any]:
    """A digest of the repository-visible state of the mirror's checkout, right now."""
    baseline = git.changed_paths_baseline(session.cwd, base_commit=session.base_commit)
    pairs = sorted([path, fingerprint] for path, fingerprint in baseline.fingerprints)
    digest = hashlib.sha256(
        json.dumps(pairs, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    # Both the digest and the pairs are kept: the digest answers "did anything move" in one
    # comparison, the pairs are what let the report name the paths rather than only assert that
    # something changed. A path set alone would miss an edit to a file that was already dirty.
    return {"digest": digest, "paths": sorted(baseline.paths), "fingerprints": pairs}


def repository_change_observation(
    session: MirrorSession,
    baseline: Mapping[str, Any] | None,
    *,
    git: session_lifecycle.GitLanding | None,
) -> frozenset[str]:
    """Repository-visible paths that differ from the baseline taken at dispatch.

    **A report, not an accusation, and the distinction is load-bearing.** The mirror runs in the
    operator's own working tree -- that is the point of it, since a mirror reading an isolated
    worktree would describe a repository nobody is working in. So the operator, another
    read-only child, or an editor open in another window can all produce changes inside this
    window, and attribution to the mirror is not established. ``session_lifecycle`` says the
    same thing about any shared checkout.

    Detection is therefore what this offers, and detection is what was missing: the mirror
    declares no artifact, so it never reaches ``check_completion_scope``, and a violation of its
    read-only contract was previously not merely unprevented but unobserved.
    """
    if git is None or not isinstance(baseline, Mapping):
        return frozenset()
    before = {path for path in baseline.get("paths", []) if isinstance(path, str)}
    current = git.changed_paths_baseline(session.cwd, base_commit=session.base_commit)
    after = set(current.paths)
    changed = after ^ before
    previous = dict(
        pair for pair in baseline.get("fingerprints", ()) if isinstance(pair, list | tuple)
    )
    for path, fingerprint in current.fingerprints:
        if path in before and previous and previous.get(path) not in (None, fingerprint):
            changed.add(path)
    return frozenset(changed)


def dispatch_request(
    session: MirrorSession,
    request: MirrorRequest,
    *,
    herdr: session_lifecycle.HerdrControl,
    now: float,
    git: session_lifecycle.GitLanding | None = None,
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

    **The request is re-validated here, not merely on the way in.** Every load-bearing check --
    the closed kind vocabulary and the predicate-declaration scan -- lives in
    :class:`MirrorRequest`'s constructor, and this is the one function that talks to the pane.
    Reading attributes off whatever object arrived would make those checks a suggestion: any
    object with the right attribute names satisfies attribute access, so a plain namespace with
    ``kind="predicate"`` and a declaration in its instruction would reach the pane with the
    constructor never having run. Re-running the checks on the object actually handed over is
    what makes the constructor a boundary. It closes the class, not one instance of it.

    ``git`` is optional and is how the read-only contract gets *detection*: when supplied, the
    repository-visible state is fingerprinted now so :func:`collect_return` can report what
    changed while the mirror held the request.

    What this function does not prove: that the orchestrator can answer the operator while a
    request is outstanding. That is a property of the calling control flow, not of this
    dispatch, and it is established end to end rather than here.
    """
    checked = _revalidated(request)
    now = _finite_seconds(now, label="now")
    row = _mirror_row(session.root, run_id=session.run_id, row_id=session.row_id)
    existing = outstanding_request(row)
    if existing is not None:
        raise MirrorBusyError(
            f"the mirror already has request {existing.get('request_id')!r} outstanding; "
            "collect its return or park this one with a reason -- it is not dropped"
        )
    record: dict[str, Any] = {
        "request_id": checked.request_id,
        "kind": checked.kind,
        "dispatched_at": now,
        "max_return_bytes": checked.max_return_bytes,
    }
    if git is not None:
        record["repository_baseline"] = _repository_fingerprint(session, git=git)
    _write_owned(session.root, session.row_id, {"mirror_request": record}, run_id=session.run_id)
    herdr.send_line(session.pane_id, _request_prompt(checked), cwd=session.cwd)
    return checked.request_id


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
    git: session_lifecycle.GitLanding | None = None,
) -> MirrorReturn:
    """Read the mirror's return for the outstanding request, enforcing the byte bound.

    A return over its declared bound is rejected, not truncated: the caller receives an
    exception carrying the byte count and never the material, and the request is closed out
    with a durable record of the rejection. The mirror itself is left exactly as it was --
    still ready, still holding its context, phase untouched -- so the orchestrator can re-ask
    with a tighter instruction.

    When ``git`` is supplied and the dispatch recorded a baseline, repository-visible changes
    over the request window are observed, returned on the result, and recorded durably. They
    are **not** raised on, and :func:`repository_change_observation` explains why: this session
    reads the operator's live working tree, so attribution is not established and failing a
    return on the operator's own edit would be a false alarm on the common case. Use
    :func:`assert_no_repository_change` where a caller wants it to be fatal.
    """
    now = _finite_seconds(now, label="now")
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
    repository_changes = repository_change_observation(
        session, request.get("repository_baseline"), git=git
    )
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
                "at": now,
                "repository_changes": sorted(repository_changes),
                "repository_observed": git is not None
                and isinstance(request.get("repository_baseline"), Mapping),
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
    return MirrorReturn(
        request_id=request_id,
        material=material,
        byte_length=byte_length,
        repository_changes=repository_changes,
    )


def assert_no_repository_change(returned: MirrorReturn) -> MirrorReturn:
    """Raise when a return carries observed repository-visible changes.

    Separate from :func:`collect_return` on purpose. Whether a change during the mirror's
    request window should be fatal is a judgement about a shared checkout, and the caller is
    the one holding the context needed to make it -- whether the operator was editing, whether
    another read-only child is live. The observation is always recorded; escalating it is opt-in.
    """
    if returned.repository_changes:
        raise MirrorWroteRepositoryError(
            f"repository-visible paths changed while request {returned.request_id!r} was "
            f"outstanding: {', '.join(sorted(returned.repository_changes))}. The mirror is a "
            "read-only session, but it shares the operator's checkout, so attribution to it is "
            "not established by this observation"
        )
    return returned


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

    The reference instant is the most recent of three, and which one it was is reported in
    ``reference_source`` so an operator can tell what the answer actually rests on:

    - ``dispatch`` — when the request went out. Always present.
    - ``sentinel`` — ``last_event_at``, written by the subscriber when a matching sentinel
      appeared. On a mirror that is only the return marker, so it arrives at the end.
    - ``pane_revision`` — the last time :func:`observe_pane_activity` saw the pane's output
      counter advance. **This is the one that distinguishes a mirror that is thinking from one
      that is dead**, and it only exists if a supervision tick is feeding it. Without it the
      clock is a per-request tolerance and nothing more.

    Every clock input is required to be finite. Raises :class:`MirrorNotArmedError` rather than
    reporting health when the row declares no usable ``max_quiet_seconds``, raises
    :class:`MirrorSubscriptionUnconfirmedError` when a request is outstanding and nothing ever
    confirmed the mirror's subscription, and reports ``idle`` without alarming when no request
    is outstanding, because a mirror between requests is legitimately silent forever.
    """
    now = _finite_seconds(now, label="now")
    row = _mirror_row(root, run_id=run_id, row_id=row_id)
    raw_bound = row.get("max_quiet_seconds")
    if raw_bound is None:
        raise MirrorNotArmedError(
            f"mirror row {row_id!r} declares no max_quiet_seconds; hang detection is not "
            "armed, which is not the same as the mirror being healthy"
        )
    bound = _finite_seconds(raw_bound, label=f"mirror row {row_id!r} max_quiet_seconds")
    request = outstanding_request(row)
    if request is None:
        return MirrorLiveness(
            state="idle", quiet_seconds=None, max_quiet_seconds=bound, request_id=None
        )

    if not subscription_acknowledged(row):
        raise MirrorSubscriptionUnconfirmedError(
            f"mirror row {row_id!r} has request {request.get('request_id')!r} outstanding but "
            "nothing has confirmed that its return subscription is installed; its return "
            "cannot wake anyone and this silence is not a hang. Call "
            "acknowledge_subscription with the subscriptions the subscriber was actually given"
        )

    reference = _finite_seconds(
        request.get("dispatched_at"),
        label=f"mirror row {row_id!r} outstanding request dispatched_at",
    )
    reference_source = "dispatch"
    activity = row.get("mirror_pane_activity")
    candidates = (
        ("sentinel", row.get("last_event_at")),
        ("pane_revision", activity.get("advanced_at") if isinstance(activity, Mapping) else None),
    )
    for source, value in candidates:
        if value is None:
            continue
        observed = _finite_seconds(value, label=f"mirror row {row_id!r} {source} instant")
        if observed > reference:
            reference, reference_source = observed, source

    quiet_seconds = now - reference
    request_id = request.get("request_id")
    if quiet_seconds > bound:
        raise MirrorQuietTooLongError(
            f"the mirror has been silent for {quiet_seconds:.1f}s against a declared tolerance "
            f"of {bound:.1f}s while request {request_id!r} is outstanding (last observed by "
            f"{reference_source}); every child still looks healthy and nothing disagrees, "
            "which is what a hung mirror looks like"
        )
    return MirrorLiveness(
        state="working",
        quiet_seconds=quiet_seconds,
        max_quiet_seconds=bound,
        request_id=str(request_id) if isinstance(request_id, str) else None,
        reference_source=reference_source,
    )


def _pane_revision(snapshot: Mapping[str, Any], pane_id: str) -> int | None:
    """The pane's output counter from one ``session.snapshot``, merged the way catch-up does.

    ``agents`` is the authoritative surface and is merged over ``panes``, matching
    ``subscriber.catch_up`` so the two readers cannot disagree about the same snapshot.
    """
    panes = snapshot.get("panes")
    agents = snapshot.get("agents")
    if not isinstance(panes, list) or not isinstance(agents, list):
        raise MirrorError("session.snapshot requires list 'panes' and 'agents'")
    merged: dict[str, Any] = {}
    for item in (*panes, *agents):
        if isinstance(item, Mapping) and item.get("pane_id") == pane_id:
            merged.update(item)
    revision = merged.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int):
        return None
    return revision


def observe_pane_activity(
    root: Path,
    *,
    run_id: str,
    row_id: str,
    snapshot: Mapping[str, Any],
    now: float,
) -> MirrorActivity:
    """Advance the mirror's liveness mark when its pane has emitted since the last look.

    **This is what tells a mirror that is thinking from one that is dead**, and it is the only
    thing in this module that does.

    The signal is herdr's pane-output ``revision`` counter, which ``register.py`` names as the
    feed ``last_event_at`` must come from and names this unit as the reader of. It is the right
    counter for a first-hand reason recorded in this repository's journal
    (``LEARNINGS.md#pane-revision-is-the-liveness-signal``): measured over one real dispatch
    window, the lifecycle counter ``state_change_seq`` moved twice and then sat still for
    minutes while the child worked hard, while ``revision`` moved roughly 47 times. A detector
    reading the lifecycle counter false-alarms on a healthy session.

    Why a snapshot rather than a subscription: the subscriber wakes the orchestrator on every
    handled event, so attaching this to a heartbeat *subscription* would wake the operator's
    channel on a timer — the exact channel-load failure the mirror exists to prevent. Reading
    a snapshot goes nowhere near ``wake_sender``. The caller supplies the snapshot for the same
    reason ``subscriber.catch_up`` does: so the reader is testable without a live socket.

    Composition owns the *cadence* of these ticks. It does not own the signal, which is why the
    reader, the comparison, and the write are all here.

    Returns what was observed. Writes only when the counter actually advanced: re-observing an
    unchanged counter must not look like activity, or a supervision loop would keep a dead
    mirror alive by asking about it.
    """
    now = _finite_seconds(now, label="now")
    row = _mirror_row(root, run_id=run_id, row_id=row_id)
    pane_id = row.get("pane_id")
    if not isinstance(pane_id, str) or not pane_id:
        raise MirrorNotRegisteredError(
            f"mirror row {row_id!r} has no pane_id; it has not been launched yet"
        )
    revision = _pane_revision(snapshot, pane_id)
    if revision is None:
        # The pane is absent from the snapshot, or reports no counter. Absence is a different
        # failure -- the subscriber records it as an exited pane, which *is* a disagreement the
        # ordinary divergence machinery reaches -- and inventing an advance here would mask it.
        return MirrorActivity(revision=None, advanced=False, advanced_at=None)

    previous = row.get("mirror_pane_activity")
    previous_revision = previous.get("revision") if isinstance(previous, Mapping) else None
    advanced = not isinstance(previous_revision, int) or revision > previous_revision
    if not advanced:
        return MirrorActivity(revision=revision, advanced=False, advanced_at=None)
    _write_owned(
        root,
        row_id,
        {"mirror_pane_activity": {"revision": revision, "advanced_at": now, "observed_at": now}},
        run_id=run_id,
    )
    return MirrorActivity(revision=revision, advanced=True, advanced_at=now)


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
    activity = row.get("mirror_pane_activity")
    return {
        "row_id": row_id,
        "run_id": run_id,
        "role": row.get("role"),
        "max_quiet_seconds": row.get("max_quiet_seconds"),
        "last_event_at": row.get("last_event_at"),
        "pane_activity": dict(activity) if isinstance(activity, Mapping) else None,
        "subscription_acknowledged": subscription_acknowledged(row),
        "outstanding_request": outstanding_request(row),
        "last_return": dict(last_return) if isinstance(last_return, Mapping) else None,
    }
