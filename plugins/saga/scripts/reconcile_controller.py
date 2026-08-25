#!/usr/bin/env python3
"""reconcile_controller — the ONE level-triggered board-reconcile controller (#450).

Kubernetes-style level-triggered convergence, shared by ``/outcome``, ``/work``, and ``/loop``.
Before #450 the two halves of board consistency lived in two ``/outcome``-only modules and were
unavailable to the other two commands:

* the **idempotency-key write** half — extracted to ``board_progression.authorize_and_write``
  (#344): authorize via ``reversibility_certificate`` (default-GATE), key into a separate ledger,
  drive an injected ``board_writer`` with bounded retry, record fail-loud. This module *composes*
  that primitive; it does not re-derive it.
* the **drift-detect/decide** half — the vocabulary and record shape (:data:`DRIFT_KINDS`,
  :func:`_drift_record`, :func:`_drift_id`, :func:`_close_satisfies_contract`) that ``/outcome``'s
  resume-time detector (``outcome_reconcile``, #295) used to own privately. #450 moves that
  vocabulary HERE and ``outcome_reconcile`` re-exports it, so the drift classification is
  single-sourced (zero behavior change to ``/outcome`` — regression-tested).

On top of those two shared halves this module adds the piece ``/work`` and ``/loop`` were missing: a
per-op **level-triggered reconcile tick** (:func:`reconcile_op`, driven in bulk by :func:`reconcile`)
that, every tick, recomputes the expected board value from durable saga fields and re-reads the live
board, so a rapid double tick converges on one write and an outside edit to a saga-owned field is
re-detected and either corrected or surfaced as a named HALT — regardless of which command drives it.

Threat model / self-attestation (the panel probes exact wording):

* The correcting write is **fail-closed and doubly gated**: it fires only when the certificate
  returns ``AUTHORIZED`` *and* the op is in the explicit :data:`AUTO_CORRECT_OP_KINDS` allowlist
  (today exactly ``set-field-status`` — the saga-owned, derived-on-read board Status field). Any op
  outside that allowlist, and any GATE verdict, HALTs; the controller never widens the
  autonomously-writable set (that lives in ``reversibility_certificate``, #344 KTD2).
* The controller **never reverses an outside issue open/closed change**. A drift whose correction
  would re-drive ``sub-issue-close`` / ``sub-issue-reopen`` is HALTed, not silently overwritten,
  because reversing an external close/reopen would destroy a human/CI lifecycle decision. This is a
  self-attested policy line, not a mathematical property of the certificate (which marks both those
  ops mechanically reversible); the allowlist is the enforcement, this paragraph is the claim.
* Idempotency is only as strong as the injected ``write_once`` (``os.link`` atomic create) and the
  caller serializing ticks (``/outcome`` runs under the coordinator lease). Under true simultaneous
  ticks the ledger dedups to one file; the *board* write is idempotent by nature (re-setting a field
  to the same value is a no-op).

House pattern (mirrors the other saga scripts): pure functions over explicit values, lazy imports of
heavy modules, no I/O at import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _cert():
    import reversibility_certificate as _m  # noqa: PLC0415

    return _m


def _bp():
    import board_progression as _m  # noqa: PLC0415

    return _m


# ---------------------------------------------------------------------------
# Drift vocabulary (single-sourced here; re-exported by outcome_reconcile, #450)
# ---------------------------------------------------------------------------

# Drift kinds a detection can carry (the caller drift-holds / surfaces these).
DRIFT_KINDS = ("status-drift", "external-close", "external-reopen")

# The ONLY op kinds the controller auto-corrects on outside drift (fail-closed allowlist). Today
# exactly the saga-owned board Status field: derived-on-read, cheap, fully reversible, and not an
# override of any human issue-lifecycle action. Everything else HALTs. Widening this set is a
# deliberate, reviewed change — never an accident of a new op_kind slipping through.
AUTO_CORRECT_OP_KINDS = frozenset({"set-field-status"})

#: The one correction field :func:`default_live_reader` can actually read back — it calls
#: ``outcome_github.board_status``, which has no field parameter, and :func:`_expected_live`
#: likewise takes no field. #812 admits ``Stage`` to the certificate's correction allowlist by
#: name, so the drift half of this controller must refuse to judge a field it cannot read.
#: Widening this needs a field-aware live reader, not a bigger set.
LIVE_READABLE_CORRECTION_FIELD = "Status"


def _drift_id(kind: str, repo: str, number: int, saga_value: str, board_value: str) -> str:
    """Deterministic short id so a CLI can reference a drift across invocations."""
    raw = f"{kind}:{repo}#{number}:{saga_value}->{board_value}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]  # nosec B324 — id, not a secret


def _drift_record(
    kind: str,
    *,
    repo: str,
    number: int,
    subplot_id: str,
    op_kind: str,
    saga_value: str,
    board_value: str,
    author: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "repo": repo,
        "number": number,
        "subplot_id": subplot_id,
        "op_kind": op_kind,
        "saga_value": saga_value,
        "board_value": board_value,
        "author": author,
        "drift_id": _drift_id(kind, repo, number, saga_value, board_value),
    }


def _close_satisfies_contract(node: Any) -> bool:
    """Whether closing this leaf's issue satisfies its completion contract (mirrors
    ``outcome_orchestrator.barrier_satisfied``).

    A non-code, non-child leaf's contract IS "tracking issue closed", so a close satisfies it. A
    code leaf's contract is "PR merged", so a closed issue does NOT satisfy it — a close there is
    drift regardless of stateReason.
    """
    return (not getattr(node, "is_outcome", False)) and getattr(node, "kind", "") != "code"


# ---------------------------------------------------------------------------
# Level-triggered expected/live helpers
# ---------------------------------------------------------------------------


def _expected_live(op_kind: str, target_state: str) -> str:
    """The live value a converged board holds for ``op_kind`` — "" when the op has no readable live
    field (fail-closed: an unknown op never claims a match, so its drift is never auto-corrected)."""
    if op_kind == str(_cert().OpKind.SET_FIELD_STATUS):
        return target_state
    if op_kind == str(_cert().OpKind.SUB_ISSUE_CLOSE):
        return "closed"
    if op_kind == str(_cert().OpKind.SUB_ISSUE_REOPEN):
        return "open"
    return ""


def _drift_kind_for(op_kind: str) -> str:
    """Map a drifting op to its :data:`DRIFT_KINDS` label (the human name for the surfaced conflict)."""
    if op_kind == str(_cert().OpKind.SET_FIELD_STATUS):
        return "status-drift"
    if op_kind == str(_cert().OpKind.SUB_ISSUE_CLOSE):
        # saga asserted closed; live shows open → someone reopened it.
        return "external-reopen"
    if op_kind == str(_cert().OpKind.SUB_ISSUE_REOPEN):
        return "external-close"
    return "status-drift"


# ---------------------------------------------------------------------------
# The per-op level-triggered reconcile primitive
# ---------------------------------------------------------------------------


def reconcile_op(
    op_kind: str,
    repo: str,
    number: int,
    target_state: str,
    *,
    board_writer: Callable[..., None],
    ledger_dir: Path,
    live_reader: Callable[[str, str, int], str] | None = None,
    now: Callable[[], float] = time.time,
    max_attempts: int = 3,
    payload: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    write_once: Callable[[Path, str], bool] | None = None,
) -> dict[str, Any]:
    """Reconcile ONE board op against durable saga intent, level-triggered.

    The tick recomputes ``target_state`` fresh from durable fields (the caller's job) and re-reads the
    live board every call — it never trusts a cached "already handled" flag, so a crash between
    compute and ledger write is retried, not skipped (R3/F3).

    Decision order (fail-closed):

    1. Certificate GATE on ``op_kind`` → ``{"status":"gated","halt":True}`` — no read, no write.
    2. **Ledger key absent** (never driven, or the key was lost to a crash) → delegate to
       ``board_progression.authorize_and_write``: it drives the writer if absent and records the key
       on success. A rapid second tick that finds the key present no-ops (R4/F1); a landed-but-
       unrecorded write is safely re-driven (idempotent) then recorded (F3).
    3. **Ledger key present** (saga asserted ``target_state``) → re-read live:
       * no ``live_reader`` / unreadable / live matches expected → ``{"status":"skipped"}`` (converged).
       * live diverges and ``op_kind`` ∈ :data:`AUTO_CORRECT_OP_KINDS` → re-drive ``target_state``
         with bounded retry → ``{"status":"corrected"}`` (R5, reversible board-field drift).
       * live diverges and ``op_kind`` ∉ the allowlist → ``{"status":"halt","halt":True}`` with a
         named ``halt_reason`` — the outside issue open/closed change is surfaced, never overwritten.

    Returns one record dict. ``extra`` is merged into every record (e.g. ``{"subplot_id": ...}``).
    """
    cert = _cert()
    bp = _bp()
    wo = write_once if write_once is not None else bp._write_once  # noqa: SLF001
    base: dict[str, Any] = dict(extra or {})
    base.update(op_kind=op_kind, repo=repo, number=number, target_state=target_state)

    # (1) The verdict MUST come from the certificate; never re-derived here. A GATE on the expected
    #     op is a fail-closed HALT — the op needs a human, so no autonomous read or write happens.
    verdict = cert.authorize_write(op_kind)
    if verdict != cert.AUTHORIZED:
        return {
            "status": "gated",
            "halt": True,
            "halt_reason": f"certificate-gate:{op_kind}",
            "verdict": "GATE",
            **base,
        }

    field_kw: str | None = None
    if op_kind == "set-field-status":
        field_kw = str((payload or {}).get("field") or "Status")
        base["field"] = field_kw
        if cert.authorize_correction_field(field_kw) != cert.AUTHORIZED:
            return {
                "status": "gated",
                "halt": True,
                "halt_reason": f"certificate-gate:correction-field:{field_kw}",
                "verdict": "GATE",
                **base,
            }

    key = cert.idempotency_key(op_kind, repo, number, target_state, field=field_kw)
    ledger_file = ledger_dir / bp._safe_ledger_name(key)  # noqa: SLF001

    # (2) Absent key → normal idempotent write / crash-safe resume, via the shared write mechanism.
    if not ledger_file.exists():
        pay: dict[str, Any] = dict(payload or {})
        if field_kw is not None:
            pay.setdefault("field", field_kw)
        return bp.authorize_and_write(
            op_kind,
            repo,
            number,
            target_state,
            board_writer=board_writer,
            ledger_dir=ledger_dir,
            now=now,
            max_attempts=max_attempts,
            payload=pay or payload,
            extra=extra,
            write_once=wo,
        )

    # (3) Present key → level-triggered drift check against live.
    if live_reader is None:
        return {"status": "skipped", "key": key, **base}
    # Fail closed on a field this controller cannot read back (#812). Comparing the live Status
    # against another field's target_state would manufacture a false drift, and because
    # `set-field-status` is in AUTO_CORRECT_OP_KINDS that false drift would be auto-corrected —
    # a write driven by a reading that was never about this field. Skip instead of guessing.
    if field_kw is not None and field_kw != LIVE_READABLE_CORRECTION_FIELD:
        return {
            "status": "skipped",
            "key": key,
            "note": (f"live drift-check reads {LIVE_READABLE_CORRECTION_FIELD}, not {field_kw}"),
            **base,
        }
    live = live_reader(op_kind, repo, number)
    if not live:
        return {"status": "skipped", "key": key, "note": "live unreadable", **base}

    expected_live = _expected_live(op_kind, target_state)
    if expected_live and live == expected_live:
        return {"status": "skipped", "key": key, **base}

    # OUTSIDE DRIFT: the board moved away from what saga asserted.
    drift_kind = _drift_kind_for(op_kind)
    drift_id = _drift_id(drift_kind, repo, number, target_state, live)
    if op_kind not in AUTO_CORRECT_OP_KINDS:
        # Reversing an outside issue open/closed change would destroy a human/CI lifecycle decision.
        return {
            "status": "halt",
            "halt": True,
            "halt_reason": f"{drift_kind}:{live}",
            "drift_id": drift_id,
            "board_value": live,
            "key": key,
            **base,
        }

    # Auto-correct: the certificate AUTHORIZED (checked above) and op is in the allowlist — re-drive
    # the saga-asserted target_state with the same bounded retry the writer path uses.
    pay = dict(payload or {})
    if target_state and "target_state" not in pay:
        pay["target_state"] = target_state
    if field_kw is not None:
        pay.setdefault("field", field_kw)
    last_exc: Exception | None = None
    attempts = 0
    for _ in range(max_attempts):
        attempts += 1
        try:
            board_writer(op_kind=op_kind, repo=repo, number=number, payload=pay)
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001 — bounded retry, surfaced below (fail-loud)
            last_exc = exc
    if last_exc is not None:
        return {
            "status": "failed",
            "key": key,
            "drift_id": drift_id,
            "board_value": live,
            "error": str(last_exc),
            "attempts": max_attempts,
            **base,
        }
    return {
        "status": "corrected",
        "key": key,
        "drift_id": drift_id,
        "board_value_was": live,
        "attempts": attempts,
        **base,
    }


# ---------------------------------------------------------------------------
# The multi-intent driver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReconcileIntent:
    """One board intent the controller should converge — recomputed fresh from durable saga fields.

    ``payload`` carries op-specific extras (e.g. an ``issue-progress-comment`` body); ``extra`` is
    merged into the emitted record (e.g. ``{"subplot_id": ...}``) so consumers keep their own shape.
    """

    op_kind: str
    repo: str
    number: int
    target_state: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


def reconcile(
    intents: list[ReconcileIntent],
    *,
    board_writer: Callable[..., None],
    ledger_dir: Path,
    live_reader: Callable[[str, str, int], str] | None = None,
    now: Callable[[], float] = time.time,
    max_attempts: int = 3,
    write_once: Callable[[Path, str], bool] | None = None,
) -> list[dict[str, Any]]:
    """Reconcile every intent, returning one record per op. Command-agnostic: ``/work``, ``/loop``,
    and ``/outcome`` all pass their own recomputed intents + injected readers/writer."""
    return [
        reconcile_op(
            it.op_kind,
            it.repo,
            it.number,
            it.target_state,
            board_writer=board_writer,
            ledger_dir=ledger_dir,
            live_reader=live_reader,
            now=now,
            max_attempts=max_attempts,
            payload=it.payload or None,
            extra=it.extra or None,
            write_once=write_once,
        )
        for it in intents
    ]


# ---------------------------------------------------------------------------
# Production wiring (composed from the modules that already pass the gh-lane lint)
# ---------------------------------------------------------------------------


def default_live_reader(
    *, project: str = "operations", runner: Callable[..., Any] | None = None
) -> Callable[[str, str, int], str]:
    """The production ``live_reader``: read the live board Status / issue state via ``outcome_github``.

    Returns ``(op_kind, repo, number) -> live_value`` ("" on any unreadable field). No ``gh`` literal
    lives in this module — the reads route through ``outcome_github`` (already lane-linted), so the
    controller stays inside saga's write-ownership lane.
    """
    import outcome_github as _gh  # noqa: PLC0415

    cert = _cert()

    def _reader(op_kind: str, repo: str, number: int) -> str:
        ref = f"{repo}#{number}" if repo else str(number)
        if op_kind == str(cert.OpKind.SET_FIELD_STATUS):
            return _gh.board_status(ref, project=project, runner=runner)
        if op_kind in (str(cert.OpKind.SUB_ISSUE_CLOSE), str(cert.OpKind.SUB_ISSUE_REOPEN)):
            return str(_gh.issue_close_info(ref, runner=runner).get("state", ""))
        return ""

    return _reader


def _repo_root_default() -> Path:
    # plugins/saga/scripts/reconcile_controller.py → parents[3] == repo root
    return Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# CLI (so the /work and /loop markdown skills can invoke a reconcile tick, #450 R2)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Level-triggered board-reconcile controller (#450)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("reconcile", help="reconcile one board op (idempotent write + drift check)")
    p.add_argument("--op", required=True, help="OpKind, e.g. set-field-status | sub-issue-close")
    p.add_argument(
        "--repo", required=True, help="owner/repo (owner used only for the key namespace)"
    )
    p.add_argument("--number", required=True, type=int)
    p.add_argument("--target-state", default="", help="e.g. Done (for set-field-status)")
    p.add_argument("--project", default="operations")
    p.add_argument("--payload", default="", help='JSON object, e.g. {"body": "..."}')
    p.add_argument(
        "--ledger-dir", default="", help="override the default board-progression ledger dir"
    )
    p.add_argument(
        "--repo-root", default="", help="override the repo root (default: from __file__)"
    )
    p.add_argument(
        "--no-drift-check",
        action="store_true",
        help="skip the live re-read (write-only tick; no outside-drift detection)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "reconcile":
        bp = _bp()
        cert = _cert()
        repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_default()
        ledger_dir = (
            Path(args.ledger_dir).resolve()
            if args.ledger_dir
            else bp._default_ledger_dir(repo_root)  # noqa: SLF001
        )
        payload = json.loads(args.payload) if args.payload else None
        # #652: the certificate decides BEFORE mission-control is resolved. A gated op reads
        # nothing and writes nothing, so an unresolvable install must not turn an expected GATE
        # verdict (exit 0) into a resolution error (exit 1) for the callers that key on the exit
        # status. ``bp._gated_writer`` raises if it is ever reached, so a verdict divergence would
        # be a loud failed record rather than a silent no-op write.
        writer: Callable[..., None] = bp._gated_writer  # noqa: SLF001
        reader: Callable[[str, str, int], str] | None = None
        if cert.authorize_write(args.op) == cert.AUTHORIZED:
            try:
                mission_control_root, _rung = bp.resolve_mission_control_root()
            except RuntimeError as exc:
                print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
                return 1
            writer = bp.default_board_writer(
                mission_control_root=mission_control_root, project=args.project
            )
            reader = None if args.no_drift_check else default_live_reader(project=args.project)
        record = reconcile_op(
            args.op,
            args.repo,
            args.number,
            args.target_state,
            board_writer=writer,
            ledger_dir=ledger_dir,
            live_reader=reader,
            payload=payload,
        )
        print(json.dumps(record))
        # written / skipped / corrected are all healthy convergence; a gate/halt needs the operator
        # (exit 0 — expected, not a crash); only a hard write failure is non-zero.
        status = record.get("status")
        if status in ("written", "skipped", "corrected"):
            return 0
        if status in ("gated", "halt"):
            return 0
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
