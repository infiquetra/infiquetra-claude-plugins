#!/usr/bin/env python3
"""outcome_board_sync — autonomous /outcome board-sync consumer (U4, R16-R19).

Maps each leaf node's live derived state to a bounded set of reversibility-authorized
mission-control board ops, records idempotency keys in a SEPARATE board-sync ledger
(never the completion events_dir — KTD4), and surfaces all gate decisions and write
failures to the caller (fail-loud; no silent skip — R17/R18).

House pattern (mirrors the other ``outcome_*`` modules): pure functions over explicit
values, lazy imports for the heavy saga modules, no I/O at import.

Requirement traceability: R1, R6, R9, R15–R19; KTD4, KTD6, KTD8.

Wiring note (KTD8): this module is the consumer that makes ``reversibility_certificate``
a live producer+consumer.  The entrypoint (``reconcile_board``) is called from the
``advance`` reconcile tick in ``outcome.py`` — where leaf states actually change.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lazy module imports (house pattern: no I/O at import — outcome_store pulls
# threading/os, outcome pulls the entire engine graph; defer both).
# ---------------------------------------------------------------------------


def _engine():
    import outcome as _m  # noqa: PLC0415

    return _m


def _store_mod():
    import outcome_store as _m  # noqa: PLC0415

    return _m


def _cert():
    import reversibility_certificate as _m  # noqa: PLC0415

    return _m


# ---------------------------------------------------------------------------
# Issue-ref parser
# ---------------------------------------------------------------------------

# Matches "owner/repo#N" or "repo#N"
_ISSUE_RE = re.compile(r"^(?:(?P<owner>[^/]+)/)?(?P<repo>[^#]+)#(?P<number>\d+)$")
# Matches a bare integer
_BARE_RE = re.compile(r"^\d+$")


def _parse_issue_ref(ref: str) -> tuple[str, int] | None:
    """Parse an issue ref into (repo, number).

    Accepts:
      - ``"owner/repo#N"``  → ``("owner/repo", N)``
      - ``"repo#N"``         → ``("repo", N)``
      - bare ``"N"``         → ``("", N)``

    Returns ``None`` if the ref cannot be parsed; caller records a note and moves on.
    """
    ref = ref.strip()
    if not ref:
        return None
    if _BARE_RE.fullmatch(ref):
        return ("", int(ref))
    m = _ISSUE_RE.fullmatch(ref)
    if m:
        owner = m.group("owner")
        repo = m.group("repo")
        number = int(m.group("number"))
        full_repo = f"{owner}/{repo}" if owner else repo
        return (full_repo, number)
    return None


# ---------------------------------------------------------------------------
# Ledger helpers (KTD4 — separate namespaced dir, never events_dir)
# ---------------------------------------------------------------------------


def _safe_ledger_name(key: str) -> str:
    """Re-export of ``board_progression._safe_ledger_name`` (#344 helper-surface preservation).

    The ledger-name logic moved to ``board_progression`` with the writer mechanism; this thin
    delegate is kept so ``outcome_reconcile`` (`sync._safe_ledger_name`) and the existing test
    suite (`SYNC_MOD._safe_ledger_name`) still resolve, single-sourced against the new owner.
    """
    import board_progression as _m  # noqa: PLC0415

    return _m._safe_ledger_name(key)


def _board_sync_dir(store: Any) -> Path:
    """Return (and create) the namespaced board-sync ledger dir under store.root."""
    d = Path(store.root) / "board-sync"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# State → candidate ops mapping (KTD6), status resolution (KTD1/KTD2/KTD3, #326)
# ---------------------------------------------------------------------------


def _default_schema_path() -> Path:
    """The default ``sdlc-schema.json`` location, derived from this module's own file path.

    Module-file-relative, not ``repo_root``-relative (KTD3) — so ``reconcile_board``'s existing
    test call sites (no ``schema_path`` passed, ``tmp_path`` stores) keep resolving correctly
    without threading a repo root through the test seam.
    """
    return Path(__file__).resolve().parents[2] / "mission-control" / "config" / "sdlc-schema.json"


def _resolve_status_map(schema_path: Path, project: str) -> dict[str, str]:
    """Resolve ``{"ready": <status>, "dispatched": <status>}`` for ``project`` (KTD1/KTD2).

    Reads ``saga_lifecycle.phase_board_map`` from the canonical mission-control SDLC schema.
    ``ready`` (pre-dispatch, approved-awaiting-start) resolves through the ``review`` phase row;
    ``dispatched`` (routed-and-running, ``outcome_dispatcher.py`` sets ``status="dispatched"``)
    resolves through the ``work`` phase row — both rows are single-element lists per project.
    Raises on a missing/unreadable schema file or a project absent from either row; the caller
    (``reconcile_board``) converts any exception into a per-op ``failed`` record (KTD4) rather than
    letting it propagate.
    """
    schema = json.loads(schema_path.read_text())
    phase_board_map = schema["saga_lifecycle"]["phase_board_map"]
    return {
        "ready": phase_board_map["review"][project][0],
        "dispatched": phase_board_map["work"][project][0],
    }


def _candidate_ops(state: str, status_map: dict[str, str]) -> list[tuple[str, str]]:
    """Return ``[(op_kind_str, target_state), ...]`` for the given derived leaf state.

    ``ready``/``dispatched`` target states come from the schema-resolved ``status_map`` (KTD1) —
    never a hardcoded literal. Negative terminals (failed/rejected/stalled) and blocked → empty
    list (deferred non-goal per Scope Boundaries). The ``ISSUE_PROGRESS_COMMENT`` is always
    coalesced alongside a status change so one comment is posted per meaningful state reached (R6).
    """
    cert = _cert()
    if state in ("ready", "dispatched"):
        return [
            (str(cert.OpKind.SET_FIELD_STATUS), status_map.get(state, "")),
            (str(cert.OpKind.ISSUE_PROGRESS_COMMENT), state),
        ]
    if state == "done":
        return [
            (str(cert.OpKind.SUB_ISSUE_CLOSE), ""),
            (str(cert.OpKind.ISSUE_PROGRESS_COMMENT), state),
        ]
    # blocked / failed / rejected / stalled → no autonomous board op in v1
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def reconcile_board(
    spec: Any,
    store: Any,
    *,
    board_writer: Callable[..., None],
    now: Callable[[], float] = time.time,
    max_attempts: int = 3,
    project: str = "operations",
    schema_path: Path | None = None,
    hold_issues: set[tuple[str, int]] | None = None,
) -> list[dict[str, Any]]:
    """Reconcile the board for all leaf nodes against their live derived states.

    For each leaf node with a resolvable issue ref this function:

    1. Derives the node's current state via ``outcome_engine.derive_states``.
    2. Maps the state to candidate board ops (KTD6), resolving ``ready``/``dispatched`` target
       states from the schema for ``project`` (#326 KTD1/KTD2) — never a hardcoded literal.
    3. Delegates each candidate op's authorize/idempotency/retry/record to
       ``board_progression.authorize_and_write`` (the shared mechanism extracted in #344) — the
       ``/outcome``-specific policy (leaf-state derivation, schema resolution, drift-hold) stays here.

    The board-sync ledger lives under ``store.root / "board-sync"`` — NEVER in
    ``events_dir`` (KTD4). ``write_once`` is injected as ``outcome_store._write_once`` so the sticky
    ledger write keeps its exact atomicity and test-patchability (#344 R2 — zero behavior diff).

    Args:
        spec:         ``OutcomeSpec`` — the DAG of leaf nodes.
        store:        ``outcome_store.Store`` — the per-outcome store handle.
        board_writer: Injected callable ``(*, op_kind, repo, number, payload) -> None``.
        now:          Time source (injectable for tests).
        max_attempts: Retry cap per op (default 3 — bounded, not infinite).
        project:      The target board's mission-control project slug.
        schema_path:  Override for the SDLC schema location (module-file-relative, #326 KTD3).
        hold_issues:  ``{(repo, number), ...}`` of issues with a detected board<->saga drift
                      (#295 U5/KTD3) — every candidate op for a held issue is WITHHELD as
                      ``{status:"drift-hold"}`` instead of driven.

    Returns:
        A list of record dicts — one per candidate op.
    """
    import board_progression as _bp  # noqa: PLC0415

    engine = _engine()
    store_module = _store_mod()
    cert = _cert()

    states: dict[str, str] = engine.derive_states(spec, store)
    ledger_dir = _board_sync_dir(store)
    records: list[dict[str, Any]] = []

    # Lazy, at-most-once-per-call resolution (#326 KTD3) — skipped entirely when no leaf is in a
    # status-bearing state, so a done-only / no-schema-file test run never touches the schema.
    status_map: dict[str, str] | None = None
    status_map_error: str | None = None
    if any(s in ("ready", "dispatched") for s in states.values()):
        try:
            resolved_path = schema_path if schema_path is not None else _default_schema_path()
            status_map = _resolve_status_map(resolved_path, project)
        except Exception as exc:  # noqa: BLE001
            status_map_error = str(exc)

    for node in spec.nodes:
        if node.is_outcome:
            continue  # skip child-outcome coordinator nodes (KTD10)

        issue_raw = str(node.github.get("issue", "") or node.github.get("sub_issue", ""))
        if not issue_raw:
            continue

        parsed = _parse_issue_ref(issue_raw)
        if parsed is None:
            records.append(
                {
                    "status": "note",
                    "subplot_id": node.subplot_id,
                    "issue_ref": issue_raw,
                    "message": "unparseable issue_ref — skipped without crashing the tick",
                }
            )
            continue

        repo, number = parsed
        state = states.get(node.subplot_id, "blocked")
        candidate_ops = _candidate_ops(state, status_map or {})

        # #295 U5/KTD3: a detected drift on this issue withholds ALL its board ops for the tick —
        # never write against a board that moved underneath saga until the operator resolves it.
        if hold_issues and (repo, number) in hold_issues:
            for op_kind_str, target_state in candidate_ops:
                records.append(
                    {
                        "status": "drift-hold",
                        "subplot_id": node.subplot_id,
                        "op_kind": op_kind_str,
                        "repo": repo,
                        "number": number,
                        "target_state": target_state,
                    }
                )
            continue

        for op_kind_str, target_state in candidate_ops:
            # #326 R5/KTD4: schema resolution failed for a ready/dispatched leaf — the status op
            # has no status to write. Fail loud + retryable (no ledger key); the coalesced
            # ISSUE_PROGRESS_COMMENT for this same leaf is unaffected and proceeds below.
            if (
                op_kind_str == str(cert.OpKind.SET_FIELD_STATUS)
                and state in ("ready", "dispatched")
                and status_map is None
            ):
                records.append(
                    {
                        "status": "failed",
                        "subplot_id": node.subplot_id,
                        "op_kind": op_kind_str,
                        "repo": repo,
                        "number": number,
                        "target_state": "",
                        "error": f"board status schema resolution failed: {status_map_error}",
                    }
                )
                continue

            # The coalesced additive comment payload is /outcome-specific; the mechanism is shared.
            payload: dict[str, Any] = {}
            if op_kind_str == str(cert.OpKind.ISSUE_PROGRESS_COMMENT):
                payload["body"] = (
                    f"saga /outcome board-sync: leaf `{node.subplot_id}` reached"
                    f" state `{target_state}`."
                )

            records.append(
                _bp.authorize_and_write(
                    op_kind_str,
                    repo,
                    number,
                    target_state,
                    board_writer=board_writer,
                    ledger_dir=ledger_dir,
                    now=now,
                    max_attempts=max_attempts,
                    payload=payload,
                    extra={"subplot_id": node.subplot_id},
                    write_once=store_module._write_once,  # noqa: SLF001
                )
            )

    return records
