#!/usr/bin/env python3
"""outcome_reconcile — resume-time board<->saga drift detection over #279's board-sync ledger (#295).

#279's ``outcome_board_sync`` drives autonomous board writes and records each success as an
idempotency-key file in ``store.root/board-sync/``, but never re-reads the live board. So an outside
writer (operator, CI, a review agent) who changes a saga-owned board field while saga is at rest is
never noticed — and because a recorded key makes the next tick *skip* the op, the drift persists
forever. This module closes that loop.

``detect`` is a pure classification over three per-issue views (KTD1):

* **asserted** — the latest of {ledger write record, reconcile-override record} per op family (KTD5),
  i.e. what saga last drove or the operator last accepted.
* **expected** — recomputed from ``derive_states`` -> ``_candidate_ops`` -> the schema status map, so
  a landed-but-unrecorded write (ledger key lost to a crash) is reconciled by recomputation, not
  missed — with zero change to #279's scope-locked writer.
* **live** — the injected ``board_reader`` (board Status) and ``issue_reader`` (open/closed +
  stateReason + close author).

The saga-owned field class is exactly what the writer writes (KTD3): board Status and issue
open/closed. Scope is ledger-bearing issues only (KTD6) — an issue with no recorded write is never
read, so a hand-added label the writer never owned can never be a false positive.

House pattern (mirrors ``outcome_board_sync``): pure functions over explicit values, lazy imports of
heavy saga modules, no I/O at import. Requirement traceability: R1-R9; KTD1-KTD7.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lazy module imports (house pattern — outcome pulls the whole engine graph,
# outcome_store pulls threading/os; defer both to call time).
# ---------------------------------------------------------------------------


def _engine():
    import outcome as _m  # noqa: PLC0415

    return _m


def _store_mod():
    import outcome_store as _m  # noqa: PLC0415

    return _m


def _sync():
    import outcome_board_sync as _m  # noqa: PLC0415

    return _m


def _cert():
    import reversibility_certificate as _m  # noqa: PLC0415

    return _m


# ---------------------------------------------------------------------------
# Op families — the saga-owned field class (KTD3). Values are the ``op_kind``
# strings the certificate/board-sync already use, so ledger records match on the nose.
# ---------------------------------------------------------------------------

_STATUS_FAMILY = "set-field-status"
_CLOSE_FAMILY = "sub-issue-close"

_OVERRIDE_KIND = "reconcile-override"

# Drift kinds a detect() record can carry (the caller drift-holds / surfaces these).
DRIFT_KINDS = ("status-drift", "external-close", "external-reopen")


# ---------------------------------------------------------------------------
# Ledger reading (the baseline half — READ-only; never creates the dir)
# ---------------------------------------------------------------------------


def _read_ledger(store: Any) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """Group every board-sync ledger + override record by ``(repo, number)``.

    Read-only: unlike ``outcome_board_sync._board_sync_dir`` this NEVER creates the directory, so a
    detect() over a store that never board-synced is a silent no-op. #279's write records carry no
    ``kind`` field; override records carry ``kind == "reconcile-override"`` — both land in the same
    per-issue list and are told apart at ``_asserted_value`` time (backward-compat, R2/KTD5).
    """
    by_issue: dict[tuple[str, int], list[dict[str, Any]]] = {}
    d = Path(store.root) / "board-sync"
    if not d.is_dir():
        return by_issue
    for f in sorted(d.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue  # a torn/foreign file is not fatal — treat as absent
        if not isinstance(rec, dict):
            continue
        repo = str(rec.get("repo", ""))
        raw_number = rec.get("number")
        if isinstance(raw_number, bool) or raw_number is None:  # bool is an int subclass — reject
            continue
        if isinstance(raw_number, int):
            number = raw_number
        else:
            try:
                number = int(raw_number)
            except (TypeError, ValueError):
                continue
        by_issue.setdefault((repo, number), []).append(rec)
    return by_issue


def _record_value(rec: dict[str, Any], family: str) -> str:
    """The value a single record asserts for ``family``: an override's accepted ``board_value``, a
    status write's ``target_state``, or the implicit ``"closed"`` for a close write."""
    if rec.get("kind") == _OVERRIDE_KIND:
        return str(rec.get("board_value", ""))
    if family == _CLOSE_FAMILY:
        return "closed"
    return str(rec.get("target_state", ""))


def _asserted_value(records: list[dict[str, Any]], family: str) -> str | None:
    """The latest asserted value for ``family``, override-preferring on a ``ts`` tie (KTD5).

    Ordering is by ``ts``; on an equal ``ts`` an override beats a write record, because an override
    is *causally* later than the write it supersedes (the operator resolved a drift the writer had
    already recorded). Production writes carry distinct wall-clock ``ts``, so an equal-``ts`` tie only
    arises under a frozen/coarse clock — the override-preference keeps that deterministic and sound
    rather than resolving by ledger-file iteration order. ``None`` means saga never asserted this
    family — the signal that a live close/Status is *external*.
    """
    best_key: tuple[float, int] | None = None
    best_val: str | None = None
    for rec in records:
        if rec.get("op_kind") != family:
            continue
        ts = float(rec.get("ts", 0) or 0)
        key = (ts, 1 if rec.get("kind") == _OVERRIDE_KIND else 0)
        if best_key is None or key >= best_key:
            best_key = key
            best_val = _record_value(rec, family)
    return best_val


def _asserted_at_max_ts(records: list[dict[str, Any]], family: str) -> set[str]:
    """Every value asserted for ``family`` at the maximum ``ts`` (usually one — production ``ts`` are
    distinct). A live value matching ANY of these is consistent, so an equal-``ts`` tie between two
    writes never spuriously reports drift when the board actually matches one of them."""
    tss = [float(r.get("ts", 0) or 0) for r in records if r.get("op_kind") == family]
    if not tss:
        return set()
    max_ts = max(tss)
    return {
        _record_value(r, family)
        for r in records
        if r.get("op_kind") == family and float(r.get("ts", 0) or 0) == max_ts
    }


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _close_satisfies_contract(node: Any) -> bool:
    """Whether closing this leaf's issue satisfies its completion contract (mirrors
    ``outcome_orchestrator.barrier_satisfied``).

    A non-code, non-child leaf's contract IS "tracking issue closed", so a close satisfies it. A
    code leaf's contract is "PR merged", so a closed issue does NOT satisfy it — a close there is
    drift regardless of stateReason (KTD4).
    """
    return (not getattr(node, "is_outcome", False)) and getattr(node, "kind", "") != "code"


def _drift_id(kind: str, repo: str, number: int, saga_value: str, board_value: str) -> str:
    """Deterministic short id so the CLI can reference a drift across invocations (KTD5)."""
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


# ---------------------------------------------------------------------------
# Public API — detect
# ---------------------------------------------------------------------------


def detect(
    spec: Any,
    store: Any,
    *,
    board_reader: Callable[[str], str],
    issue_reader: Callable[[str], dict[str, str]],
    project: str = "operations",
    schema_path: Path | None = None,
    now: Callable[[], float] = time.time,
) -> list[dict[str, Any]]:
    """Return drift + recovered records for every ledger-bearing issue whose live board diverges.

    An empty list means "silent" (R4): every saga-owned field matches the baseline. Each returned
    record is one of:

    * a **drift** record (``kind`` in :data:`DRIFT_KINDS`) — the caller drift-holds that issue's
      board ops and surfaces the {field, saga, board, author} conflict for a HITL resolution (R5);
    * a **recovered** record (``kind == "recovered"``) — a landed-but-unrecorded write whose ledger
      key this call rewrote (informational, never a drift, AE3);
    * an **unreadable** note (``kind == "unreadable"``) — one field could not be read this tick;
      never fatal, resurfaces next detection.

    Only ledger-bearing issues are read (KTD6): ``board_reader`` / ``issue_reader`` are called
    strictly for issues with >=1 recorded write or override, so an issue saga never touched is never
    probed and can never be a false positive.

    Args:
        spec / store: the outcome DAG and its per-outcome store (same handles ``reconcile_board`` uses).
        board_reader: injected ``(issue_ref) -> status_name`` ("" when unreadable). Default in the
                      wiring is ``outcome_github.board_status`` bound to ``project``.
        issue_reader: injected ``(issue_ref) -> {state, state_reason, closed_by}``. Default is
                      ``outcome_github.issue_close_info``.
        project / schema_path: thread through to ``_resolve_status_map`` for the expected-Status
                      recomputation (same #326 seam as ``reconcile_board``).
        now: time source for the recovered-record ``ts`` (injectable for tests).
    """
    engine = _engine()
    sync = _sync()
    cert = _cert()

    by_issue = _read_ledger(store)
    if not by_issue:
        return []  # nothing recorded → nothing to contradict (scope discipline, KTD6)

    states: dict[str, str] = engine.derive_states(spec, store)

    # Resolve the schema status map lazily — only if some in-scope leaf is status-bearing, mirroring
    # reconcile_board so a done-only / no-schema run never touches the file. A resolution failure is
    # non-fatal: expected-Status stays "" and the recover branch simply does not fire.
    status_map: dict[str, str] | None = None
    if any(s in ("ready", "dispatched") for s in states.values()):
        try:
            resolved = schema_path if schema_path is not None else sync._default_schema_path()
            status_map = sync._resolve_status_map(resolved, project)
        except Exception:  # noqa: BLE001 — non-fatal; recover just won't fire (R2)
            status_map = None

    records: list[dict[str, Any]] = []

    for node in spec.nodes:
        if getattr(node, "is_outcome", False):
            continue  # child-outcome coordinator nodes carry no tracking issue of their own

        issue_raw = str(node.github.get("issue", "") or node.github.get("sub_issue", ""))
        if not issue_raw:
            continue
        parsed = sync._parse_issue_ref(issue_raw)
        if parsed is None:
            continue
        repo, number = parsed
        issue_records = by_issue.get((repo, number))
        if not issue_records:
            continue  # NOT ledger-bearing → out of scope; board is never read for it (KTD6)

        sid = node.subplot_id
        state = states.get(sid, "blocked")

        # Expected Status from the current derived state (KTD1) — used only for the recover branch.
        expected_status = ""
        for op_kind_str, target in sync._candidate_ops(state, status_map or {}):
            if op_kind_str == _STATUS_FAMILY:
                expected_status = target

        # ---- Status field ---------------------------------------------------
        asserted_status = _asserted_value(issue_records, _STATUS_FAMILY)
        live_status = board_reader(issue_raw)
        if live_status == "":
            if asserted_status is not None:
                records.append(
                    {
                        "kind": "unreadable",
                        "repo": repo,
                        "number": number,
                        "subplot_id": sid,
                        "op_kind": _STATUS_FAMILY,
                        "field": "status",
                    }
                )
        elif asserted_status is not None:
            # Tie-robust: consistent when live matches ANY assertion at the latest ts (a single
            # value for distinct-ts production writes; the set only widens under an equal-ts tie).
            if live_status not in _asserted_at_max_ts(issue_records, _STATUS_FAMILY):
                records.append(
                    _drift_record(
                        "status-drift",
                        repo=repo,
                        number=number,
                        subplot_id=sid,
                        op_kind=_STATUS_FAMILY,
                        saga_value=asserted_status,
                        board_value=live_status,
                    )
                )
            # else: live matches the latest asserted Status → silent
        elif expected_status and live_status == expected_status:
            # Landed-but-unrecorded write (AE3): the board holds saga's expected Status but the
            # ledger key was lost. Rewrite the key so the baseline is whole again — informational.
            key = cert.idempotency_key(_STATUS_FAMILY, repo, number, expected_status)
            ledger_file = Path(store.root) / "board-sync" / sync._safe_ledger_name(key)
            record_json = json.dumps(
                {
                    "key": key,
                    "op_kind": _STATUS_FAMILY,
                    "repo": repo,
                    "number": number,
                    "target_state": expected_status,
                    "ts": now(),
                    "recovered": True,
                }
            )
            _store_mod()._write_once(ledger_file, record_json)  # False on race = benign no-op
            records.append(
                {
                    "kind": "recovered",
                    "repo": repo,
                    "number": number,
                    "subplot_id": sid,
                    "op_kind": _STATUS_FAMILY,
                    "target_state": expected_status,
                    "key": key,
                }
            )

        # ---- Open/closed field ---------------------------------------------
        close_info = issue_reader(issue_raw)
        live_close = str(close_info.get("state", "unknown"))
        asserted_close = _asserted_value(issue_records, _CLOSE_FAMILY)
        if live_close == "unknown":
            records.append(
                {
                    "kind": "unreadable",
                    "repo": repo,
                    "number": number,
                    "subplot_id": sid,
                    "op_kind": _CLOSE_FAMILY,
                    "field": "state",
                }
            )
        elif live_close == "closed" and asserted_close != "closed":
            # External close saga never drove. Contract-aware + stateReason (KTD4): a completed close
            # that satisfies the leaf's contract (or an unreadable reason on such a contract) is the
            # harvester's sanctioned silent path; not_planned, or a close on a contract it does not
            # satisfy, is drift.
            reason = str(close_info.get("state_reason", "unknown"))
            sanctioned = _close_satisfies_contract(node) and reason in ("completed", "unknown")
            if not sanctioned:
                records.append(
                    _drift_record(
                        "external-close",
                        repo=repo,
                        number=number,
                        subplot_id=sid,
                        op_kind=_CLOSE_FAMILY,
                        saga_value="open",
                        board_value="closed",
                        author=str(close_info.get("closed_by", "")),
                    )
                )
        elif live_close == "open" and asserted_close == "closed":
            records.append(
                _drift_record(
                    "external-reopen",
                    repo=repo,
                    number=number,
                    subplot_id=sid,
                    op_kind=_CLOSE_FAMILY,
                    saga_value="closed",
                    board_value="open",
                )
            )

    return records


# ---------------------------------------------------------------------------
# Public API — resolution + the precedence seam (U4)
# ---------------------------------------------------------------------------


def decide(drift: dict[str, Any], *, policy: Callable[[dict[str, Any]], str | None] | None = None):
    """Choose a resolution for a drift, or return ``None`` to defer to the operator (R8 seam).

    v1 is HITL: with no ``policy`` this always returns ``None`` and the skill layer asks the operator
    {accept-board, re-assert, hold}. The single ``policy`` hook is the deferred writer-precedence
    seam — a later "field X's authoritative writer auto-resolves" rule plugs in HERE without touching
    ``detect`` or ``apply_resolution``. A policy returning ``None`` still falls back to the ask.
    """
    if policy is None:
        return None
    return policy(drift)


def apply_resolution(
    drift: dict[str, Any],
    resolution: str,
    *,
    store: Any,
    board_writer: Callable[..., None],
    now: Callable[[], float] = time.time,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Apply an operator resolution, recording it append-only in the board-sync ledger namespace (R7).

    * ``accept-board`` — append a ``reconcile-override`` record fixing the accepted board value as the
      new baseline (KTD5); the filename is derived from the drift id so replaying is idempotent. A
      not_planned external close carries an advisory to ``/outcome prune`` — reconcile never mints a
      completion event (graph edits stay the operator's, R9).
    * ``re-assert`` — ``authorize_write`` FIRST (a GATE refuses, never bypassed), then re-drive the
      write through the INJECTED ``board_writer`` (never a direct gh call, R9) with the same bounded
      retry as ``reconcile_board``, then record the re-asserted value as the baseline.
    * ``hold`` — record nothing; the drift resurfaces on the next detection (level-triggered, KTD5).
    """
    cert = _cert()
    store_mod = _store_mod()
    repo = str(drift["repo"])
    number = int(drift["number"])
    op_kind = str(drift["op_kind"])
    drift_id = str(drift["drift_id"])
    sid = str(drift.get("subplot_id", ""))
    ledger_dir = Path(store.root) / "board-sync"

    if resolution == "hold":
        return {"status": "held", "drift_id": drift_id}

    if resolution == "accept-board":
        board_value = str(drift.get("board_value", ""))
        rec = {
            "kind": _OVERRIDE_KIND,
            "resolution": "accept-board",
            "op_kind": op_kind,
            "repo": repo,
            "number": number,
            "board_value": board_value,
            "drift_id": drift_id,
            "ts": now(),
        }
        wrote = store_mod._write_once(
            ledger_dir / f"override-accept-board-{drift_id}.json", json.dumps(rec)
        )
        result: dict[str, Any] = {"status": "accepted", "drift_id": drift_id, "recorded": wrote}
        if drift.get("kind") == "external-close":
            result["advisory"] = (
                f"leaf {sid!r} is closed on the board; reconcile records the acceptance but mints "
                f"no completion event — run `/outcome prune {sid}` to drop it from the frontier (R9)."
            )
        return result

    if resolution == "re-assert":
        verdict = cert.authorize_write(op_kind)
        if verdict != cert.AUTHORIZED:
            return {"status": "gated", "drift_id": drift_id, "op_kind": op_kind, "verdict": "GATE"}
        saga_value = str(drift["saga_value"])
        payload: dict[str, Any] = {}
        if op_kind == _STATUS_FAMILY:
            payload["target_state"] = saga_value  # close family re-drives with an empty payload
        last_exc: Exception | None = None
        attempts = 0
        for _ in range(max_attempts):
            attempts += 1
            try:
                board_writer(op_kind=op_kind, repo=repo, number=number, payload=payload)
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 — bounded retry, surfaced below (R18-style)
                last_exc = exc
        if last_exc is not None:
            return {
                "status": "failed",
                "drift_id": drift_id,
                "op_kind": op_kind,
                "error": str(last_exc),
                "attempts": max_attempts,
            }
        rec = {
            "kind": _OVERRIDE_KIND,
            "resolution": "re-assert",
            "op_kind": op_kind,
            "repo": repo,
            "number": number,
            "board_value": saga_value,
            "drift_id": drift_id,
            "ts": now(),
        }
        wrote = store_mod._write_once(
            ledger_dir / f"override-re-assert-{drift_id}.json", json.dumps(rec)
        )
        return {
            "status": "reasserted",
            "drift_id": drift_id,
            "attempts": attempts,
            "recorded": wrote,
        }

    raise ValueError(f"unknown resolution {resolution!r}")
