#!/usr/bin/env python3
"""Bind Team re-ping claims to host-observed SendMessage outcomes (#357).

The hook stores hashes and identifiers only.  Ordinary SendMessage calls with no staged liveness
claim pass silently.  Ambiguous failures produce a local unresolved receipt but no ledger event, so
they can never become retry or timeout authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess  # nosec B404 -- fixed Git argv, no shell
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import liveness_events  # noqa: E402
import run_ledger  # noqa: E402

PENDING_SCHEMA = "liveness.reping-pending.v1"
INFLIGHT_SCHEMA = "liveness.reping-inflight.v1"
RECEIPT_SCHEMA = "liveness.reping-hook-receipt.v1"
STATE_ROOT = Path("saga-liveness")
_PREFIX = "[saga/liveness-reping]"


class RePingHookError(ValueError):
    """A staged binding or host event is malformed or ambiguous."""


def _halt(message: str) -> NoReturn:
    print(f"{_PREFIX} HALT — {message}", file=sys.stderr)
    raise SystemExit(2)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _request_digest(recipient: str, message: str) -> str:
    return hashlib.sha256(_canonical({"recipient": recipient, "message": message})).hexdigest()


def _safe_suffix(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _repo_root(cwd: object) -> Path | None:
    directory = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    completed = subprocess.run(  # nosec B603 B607 -- fixed Git argv, no shell
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()) if completed.returncode == 0 else None


def _common_dir(repo_root: Path) -> Path:
    completed = subprocess.run(  # nosec B603 B607 -- fixed Git argv, no shell
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RePingHookError(f"cannot resolve Git common dir: {completed.stderr.strip()}")
    path = Path(completed.stdout.strip())
    return path if path.is_absolute() else (repo_root / path).resolve()


def _read_record(path: Path, schema: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RePingHookError(f"host binding is unreadable: {path.name}") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise RePingHookError(f"host binding schema is invalid: {path.name}")
    return value


def _write_record(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(value), handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _tool_values(payload: Mapping[str, Any]) -> tuple[str, str] | None:
    if payload.get("tool_name") != "SendMessage":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        raise RePingHookError("SendMessage tool_input must be an object")
    recipient = next(
        (
            value
            for key in ("recipient", "target_agent_id", "target")
            if isinstance((value := tool_input.get(key)), str) and value
        ),
        None,
    )
    message = next(
        (
            value
            for key in ("message", "content")
            if isinstance((value := tool_input.get(key)), str)
        ),
        None,
    )
    if recipient is None or message is None:
        raise RePingHookError("SendMessage requires a recipient and message")
    return recipient, message


def _pending_match(
    state_root: Path,
    *,
    recipient: str,
    request_digest: str,
) -> tuple[Path, dict[str, Any]] | None:
    directory = state_root / "pending"
    if not directory.is_dir():
        return None
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in directory.glob("*.json"):
        record = _read_record(path, PENDING_SCHEMA)
        if record.get("recipient") == recipient and record.get("request_digest") == request_digest:
            matches.append((path, record))
    if len(matches) > 1:
        raise RePingHookError("multiple staged claims match one SendMessage call")
    return matches[0] if matches else None


def _pre_tool_use(payload: Mapping[str, Any], repo_root: Path) -> None:
    values = _tool_values(payload)
    if values is None:
        return
    recipient, message = values
    digest = _request_digest(recipient, message)
    state_root = _common_dir(repo_root) / STATE_ROOT
    matched = _pending_match(state_root, recipient=recipient, request_digest=digest)
    if matched is None:
        return
    pending_path, pending = matched
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        raise RePingHookError("staged SendMessage has no host tool_use_id")
    inflight = {
        "schema": INFLIGHT_SCHEMA,
        "pending_name": pending_path.name,
        "identity": pending.get("identity"),
        "claim_key": pending.get("claim_key"),
        "claim_event_id": pending.get("claim_event_id"),
        "recipient": recipient,
        "request_digest": digest,
        "tool_use_id": tool_use_id,
        "response_window_seconds": pending.get("response_window_seconds"),
    }
    _write_record(state_root / "inflight" / f"{_safe_suffix(tool_use_id)}.json", inflight)


def _observed_monotonic(payload: Mapping[str, Any]) -> float:
    value = payload.get("observed_monotonic")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return time.monotonic()


def _definitive_not_sent(payload: Mapping[str, Any]) -> bool:
    response = payload.get("tool_response")
    return (
        isinstance(response, Mapping) and response.get("delivery_status") == "definitive-not-sent"
    )


def _append_result(
    repo_root: Path,
    inflight: Mapping[str, Any],
    *,
    event: str,
    event_id: str,
    receipt_ref: str,
    observed_monotonic: float,
) -> None:
    identity = liveness_events.SubjectIdentity.from_dict(inflight.get("identity"))
    ledger = run_ledger.RunLedger.resolve(repo_root)
    if event == "reping-sent":
        payload = {
            "claim_key": inflight["claim_key"],
            "receipt_ref": receipt_ref,
            "tool_use_id": inflight["tool_use_id"],
            "recipient": inflight["recipient"],
            "request_digest": inflight["request_digest"],
            "accepted_monotonic": observed_monotonic,
            "response_window_seconds": inflight["response_window_seconds"],
        }
    else:
        payload = {
            "claim_key": inflight["claim_key"],
            "receipt_ref": receipt_ref,
            "definitive_not_sent": True,
            "failed_monotonic": observed_monotonic,
        }
    liveness_events.append_event(
        ledger,
        identity,
        event,
        event_id=event_id,
        at="host-hook",
        payload=payload,
    )


def _post_tool_use(payload: Mapping[str, Any], repo_root: Path, *, failure: bool) -> None:
    if payload.get("tool_name") != "SendMessage":
        return
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        return
    state_root = _common_dir(repo_root) / STATE_ROOT
    inflight_path = state_root / "inflight" / f"{_safe_suffix(tool_use_id)}.json"
    if not inflight_path.is_file():
        return
    inflight = _read_record(inflight_path, INFLIGHT_SCHEMA)
    observed = _observed_monotonic(payload)
    status = "unresolved" if failure else "accepted"
    if failure and _definitive_not_sent(payload):
        status = "definitive-not-sent"
    suffix = _safe_suffix(tool_use_id)
    receipt_ref = f"liveness-hook-receipt-{suffix}"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "claim_key": inflight.get("claim_key"),
        "tool_use_id_sha256": hashlib.sha256(tool_use_id.encode()).hexdigest(),
        "recipient": inflight.get("recipient"),
        "request_digest": inflight.get("request_digest"),
        "observed_monotonic": observed,
    }
    _write_record(state_root / "receipts" / f"{suffix}.json", receipt)
    if status == "accepted":
        _append_result(
            repo_root,
            inflight,
            event="reping-sent",
            event_id=f"reping-sent-{suffix}",
            receipt_ref=receipt_ref,
            observed_monotonic=observed,
        )
    elif status == "definitive-not-sent":
        _append_result(
            repo_root,
            inflight,
            event="reping-send-failed",
            event_id=f"reping-failed-{suffix}",
            receipt_ref=receipt_ref,
            observed_monotonic=observed,
        )
    pending_name = inflight.get("pending_name")
    if isinstance(pending_name, str):
        (state_root / "pending" / pending_name).unlink(missing_ok=True)
    inflight_path.unlink(missing_ok=True)


def dispatch(payload: dict[str, Any]) -> None:
    repo_root = _repo_root(payload.get("cwd"))
    if repo_root is None:
        return
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        _pre_tool_use(payload, repo_root)
    elif event == "PostToolUse":
        _post_tool_use(payload, repo_root, failure=False)
    elif event == "PostToolUseFailure":
        _post_tool_use(payload, repo_root, failure=True)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (OSError, json.JSONDecodeError) as exc:
        _halt(f"invalid hook input: {exc}")
    if not isinstance(payload, dict):
        _halt("hook input must be a JSON object")
    try:
        dispatch(payload)
    except Exception as exc:  # noqa: BLE001 - pre-call binding must fail closed.
        if payload.get("hook_event_name") == "PreToolUse":
            _halt(str(exc))
        print(f"{_PREFIX} retained for recovery: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
