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

import hashlib
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
    """Turn an idempotency key into a safe filename.

    Replaces the separators used by ``idempotency_key`` (``:``, ``#``, ``/``) with
    underscores.  Falls back to a SHA-1 hex digest for keys that are too long or
    contain other problematic characters after replacement.
    """
    safe = key.replace(":", "_").replace("#", "_").replace("/", "_")
    # SHA-1 fallback: 200-char limit covers all realistic keys; non-alnum guard is a
    # belt-and-suspenders check for exotic values (e.g. a future label with spaces).
    if len(safe) > 200 or not all(c.isalnum() or c in "_-." for c in safe):
        safe = hashlib.sha1(key.encode()).hexdigest()
    return safe + ".json"


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
    3. For each candidate op, calls ``reversibility_certificate.authorize_write`` (R1).
    4. GATE → appends a ``{status:"gated"}`` record; no write, no ledger, no silence (R17).
    5. AUTHORIZED → checks the board-sync ledger for the idempotency key:
       - Key present  → ``{status:"skipped"}`` (AE8 crash/retry safety).
       - Key absent   → attempts ``board_writer`` with bounded retry (AE8); on success
         writes the ledger key and appends ``{status:"written"}``; on all-attempt failure
         appends ``{status:"failed"}`` WITHOUT writing the key so the next tick retries (R18).

    Schema resolution for ``ready``/``dispatched`` statuses is attempted at most once per call,
    and only when at least one leaf is actually in one of those states — a run touching only
    ``done``/negative-terminal leaves never reads the schema file. A resolution failure (missing
    schema, unknown ``project``) does not raise: the affected ``set-field-status`` op records
    ``{status:"failed"}`` with no ledger key (retryable next tick, #326 R5), while the coalesced
    ``ISSUE_PROGRESS_COMMENT`` for the same leaf still proceeds.

    The board-sync ledger lives under ``store.root / "board-sync"`` — NEVER in
    ``events_dir`` (KTD4; that ledger requires terminal COMPLETION_STATES and feeds
    ``derive_states``; a board-op key would crash ``validate`` or pollute the frontier).

    Args:
        spec:         ``OutcomeSpec`` — the DAG of leaf nodes.
        store:        ``outcome_store.Store`` — the per-outcome store handle.
        board_writer: Injected callable ``(*, op_kind, repo, number, payload) -> None``.
                      Drives the matching mission-control verb.  Never imported here.
        now:          Time source (injectable for tests).
        max_attempts: Retry cap per op (default 3 — bounded, not infinite).
        project:      The target board's mission-control project slug — resolves the
                      ``ready``/``dispatched`` status from that project's schema row.
        schema_path:  Override for the SDLC schema location; defaults to the real
                      mission-control config file (module-file-relative, #326 KTD3).
        hold_issues:  ``{(repo, number), ...}`` of issues with a detected board<->saga drift
                      (#295 U5/KTD3). Every candidate op for a held issue is WITHHELD and recorded
                      as ``{status: "drift-hold"}`` instead of driven — the write must not act on a
                      board that moved underneath it until the operator resolves the drift. Other
                      leaves' ops proceed normally (drift-hold, not gate-all).

    Returns:
        A list of record dicts — one per candidate op — with the keys documented above.
    """
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

            # R1: the verdict MUST come from the certificate; never re-derived here.
            verdict = cert.authorize_write(op_kind_str)

            if verdict != cert.AUTHORIZED:
                # R17: surface the gate — no silent write, no silent skip.
                records.append(
                    {
                        "status": "gated",
                        "subplot_id": node.subplot_id,
                        "op_kind": op_kind_str,
                        "repo": repo,
                        "number": number,
                        "target_state": target_state,
                        "verdict": "GATE",
                    }
                )
                continue

            # repo is part of the key: two leaves with the same issue NUMBER in different repos
            # (saga#5 vs mission-control#5 — the v1 two-plugin case) must not collide on one ledger
            # entry, or one would silently skip the other's board write.
            key = cert.idempotency_key(op_kind_str, repo, number, target_state)
            ledger_file = ledger_dir / _safe_ledger_name(key)

            # (i) Check key present → idempotent no-op (AE8 crash/retry safety, AE4 coalescing)
            if ledger_file.exists():
                records.append(
                    {
                        "status": "skipped",
                        "subplot_id": node.subplot_id,
                        "op_kind": op_kind_str,
                        "repo": repo,
                        "number": number,
                        "target_state": target_state,
                        "key": key,
                    }
                )
                continue

            # (ii) Attempt with bounded retry.  Board_writer raises → retry; key only
            #      written on SUCCESS so a failed op is retryable on the next tick (R18).
            payload: dict[str, Any] = {}
            if target_state:
                payload["target_state"] = target_state
            if op_kind_str == str(cert.OpKind.ISSUE_PROGRESS_COMMENT):
                payload["body"] = (
                    f"saga /outcome board-sync: leaf `{node.subplot_id}` reached"
                    f" state `{target_state}`."
                )

            last_exc: Exception | None = None
            attempts_made = 0
            for _ in range(max_attempts):
                attempts_made += 1
                try:
                    board_writer(
                        op_kind=op_kind_str,
                        repo=repo,
                        number=number,
                        payload=payload,
                    )
                    last_exc = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc

            if last_exc is None:
                # (iii) SUCCESS → write ledger key now (sticky, write-once, KTD4). A fault HERE
                #       (ledger I/O / clock) must NOT escape: the board write already committed, so
                #       letting it propagate would wedge the whole tick, discard every record gathered
                #       so far, AND leave a side effect with no recorded key (recovery would re-apply
                #       it). Surface it loudly and keep going; the next tick re-attempts (idempotent
                #       ops no-op; the additive comment is at-least-once).
                try:
                    record_json = json.dumps(
                        {
                            "key": key,
                            "op_kind": op_kind_str,
                            "repo": repo,
                            "number": number,
                            "target_state": target_state,
                            "ts": now(),
                        }
                    )
                    store_module._write_once(ledger_file, record_json)  # noqa: SLF001
                    records.append(
                        {
                            "status": "written",
                            "subplot_id": node.subplot_id,
                            "op_kind": op_kind_str,
                            "repo": repo,
                            "number": number,
                            "target_state": target_state,
                            "key": key,
                            "attempts": attempts_made,
                        }
                    )
                except Exception as ledger_exc:  # noqa: BLE001
                    records.append(
                        {
                            "status": "error",
                            "subplot_id": node.subplot_id,
                            "op_kind": op_kind_str,
                            "repo": repo,
                            "number": number,
                            "target_state": target_state,
                            "key": key,
                            "error": f"board write committed but ledger record failed: {ledger_exc}",
                            "may_reapply": True,
                        }
                    )
            else:
                # All attempts exhausted — surface, do NOT write ledger so next tick retries (R18).
                records.append(
                    {
                        "status": "failed",
                        "subplot_id": node.subplot_id,
                        "op_kind": op_kind_str,
                        "repo": repo,
                        "number": number,
                        "target_state": target_state,
                        "key": key,
                        "error": str(last_exc),
                        "attempts": max_attempts,
                    }
                )

    return records
