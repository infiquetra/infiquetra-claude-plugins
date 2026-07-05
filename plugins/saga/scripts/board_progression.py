#!/usr/bin/env python3
"""board_progression — plugin-agnostic certificate-gated autonomous board writer (#344).

Extracted from ``outcome_board_sync.reconcile_board`` (merged #279/#295): the reusable per-op
*mechanism* — authorize via ``reversibility_certificate`` (default-GATE), idempotency-key into a
separate ledger, drive an injected ``board_writer`` with bounded retry, record fail-loud — with the
``/outcome``-specific *policy* (leaf-state derivation, schema resolution, drift-hold) left in the
caller. Consumers: ``/outcome`` (via ``reconcile_board``), ``/work`` (post-merge), ``/loop``.

Because every op routes through ``reversibility_certificate.authorize_write``, a new consumer
CANNOT widen the autonomously-writable set: merge/deploy op-kinds are absent from the certificate
registry (default-GATE) and ``PARENT_ISSUE_CLOSE`` is ``ALWAYS_OPERATOR``. The allowlist lives in
the certificate, not here (#344 KTD2).

House pattern (mirrors other saga scripts): pure functions over explicit values, lazy imports of
heavy modules, no I/O at import.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _cert():
    import reversibility_certificate as _m  # noqa: PLC0415

    return _m


# ---------------------------------------------------------------------------
# Ledger helpers (owned here; re-exported by outcome_board_sync for its readers)
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


def _write_once(path: Path, content: str) -> bool:
    """Create ``path`` atomically, refusing to clobber an existing file (write-once).

    Returns True if this call created the file, False if it already existed. Uses temp + ``os.link``
    so a crash mid-write leaves only the temp file, never a torn final file (mirrors
    ``outcome_store._write_once`` but kept local so the module is plugin-agnostic, #344 KTD1).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    try:
        os.link(tmp, path)  # atomic create; raises FileExistsError if path is taken
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


# ---------------------------------------------------------------------------
# The per-op primitive (the extracted mechanism)
# ---------------------------------------------------------------------------


def authorize_and_write(
    op_kind: str,
    repo: str,
    number: int,
    target_state: str,
    *,
    board_writer: Callable[..., None],
    ledger_dir: Path,
    now: Callable[[], float] = time.time,
    max_attempts: int = 3,
    payload: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    write_once: Callable[[Path, str], bool] = _write_once,
) -> dict[str, Any]:
    """Authorize, idempotently write, and record ONE candidate board op.

    Routes ``op_kind`` through ``reversibility_certificate.authorize_write`` (R1/R3); a non-AUTHORIZED
    verdict returns ``{status:"gated"}`` with no write and no ledger entry (fail-loud, never silent).
    An AUTHORIZED op is idempotency-keyed into ``ledger_dir``: a present key returns
    ``{status:"skipped"}``; an absent key drives ``board_writer`` with bounded retry, writing the
    ledger key only on success (``{status:"written"}``) so a failed op is retryable next tick
    (``{status:"failed"}``, no key). A ledger fault after a committed write surfaces as
    ``{status:"error", may_reapply:True}`` rather than escaping.

    ``extra`` is merged into every record (callers pass e.g. ``{"subplot_id": ...}`` so ``/outcome``
    records keep their existing shape — zero behavior diff, #344 R2). Returns one record dict.
    """
    cert = _cert()
    base: dict[str, Any] = dict(extra or {})
    base.update(op_kind=op_kind, repo=repo, number=number, target_state=target_state)

    # R1: the verdict MUST come from the certificate; never re-derived here (#344 KTD2).
    verdict = cert.authorize_write(op_kind)
    if verdict != cert.AUTHORIZED:
        # R17: surface the gate — no silent write, no silent skip.
        return {"status": "gated", **base, "verdict": "GATE"}

    key = cert.idempotency_key(op_kind, repo, number, target_state)
    ledger_file = ledger_dir / _safe_ledger_name(key)

    # (i) Key present → idempotent no-op (crash/retry safety, coalescing).
    if ledger_file.exists():
        return {"status": "skipped", **base, "key": key}

    pay: dict[str, Any] = dict(payload or {})
    if target_state and "target_state" not in pay:
        pay["target_state"] = target_state

    # (ii) Bounded retry.  board_writer raises → retry; key written only on SUCCESS.
    last_exc: Exception | None = None
    attempts_made = 0
    for _ in range(max_attempts):
        attempts_made += 1
        try:
            board_writer(op_kind=op_kind, repo=repo, number=number, payload=pay)
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

    if last_exc is not None:
        # All attempts exhausted — surface, do NOT write the ledger so the next tick retries.
        return {
            "status": "failed",
            **base,
            "key": key,
            "error": str(last_exc),
            "attempts": max_attempts,
        }

    # (iii) SUCCESS → write the ledger key (sticky, write-once). A fault HERE must NOT escape: the
    #       board write already committed, so propagating would leave a side effect with no recorded
    #       key (recovery would re-apply it). Surface loudly and let the next tick reconcile.
    try:
        record_json = json.dumps(
            {
                "key": key,
                "op_kind": op_kind,
                "repo": repo,
                "number": number,
                "target_state": target_state,
                "ts": now(),
            }
        )
        write_once(ledger_file, record_json)
        return {"status": "written", **base, "key": key, "attempts": attempts_made}
    except Exception as ledger_exc:  # noqa: BLE001
        return {
            "status": "error",
            **base,
            "key": key,
            "error": f"board write committed but ledger record failed: {ledger_exc}",
            "may_reapply": True,
        }


# ---------------------------------------------------------------------------
# The production board_writer (moved from outcome.py:_default_board_writer, #344 KTD6)
# ---------------------------------------------------------------------------


def default_board_writer(
    repo_root: Path,
    *,
    project: str = "operations",
    runner: Callable[..., Any] | None = None,
) -> Callable[..., None]:
    """The production board_writer (#279/#344): drive a reversibility-authorized op via mission-control.

    Maps each enumerated ``OpKind`` to its ``sdlc_manager.py`` subcommand. Tests inject a recording
    fake (or the ``--runner`` seam) instead; the nested ``gh`` child runs ONLY under a real
    ``--autonomous`` campaign. A non-zero exit raises so the consumer's bounded-retry / fail-loud
    path engages.
    """
    import subprocess  # noqa: PLC0415

    sdlc = str(repo_root / "plugins" / "mission-control" / "scripts" / "sdlc_manager.py")
    run = runner if runner is not None else subprocess.run

    def _writer(*, op_kind: str, repo: str, number: int, payload: dict[str, Any]) -> None:
        base = ["python3", sdlc]
        n = str(number)
        # The mission-control verbs prepend ORG to build ``repos/{ORG}/{repo}/...``, so they need the
        # BARE repo name. The caller passes an owner-qualified repo ("infiquetra/saga") for the
        # idempotency-key namespace; strip the owner here so the REST path is not doubled.
        repo = repo.rsplit("/", 1)[-1]
        if op_kind == "set-field-status":
            cmd = base + [
                "flow",
                "set-field",
                "--project",
                project,
                "--repo",
                repo,
                "--number",
                n,
                "--field",
                "Status",
                "--option",
                str(payload.get("target_state", "")),
            ]
        elif op_kind == "sub-issue-close":
            cmd = base + ["issue", "close", "--repo", repo, "--number", n]
        elif op_kind == "sub-issue-reopen":
            cmd = base + ["issue", "reopen", "--repo", repo, "--number", n]
        elif op_kind == "issue-progress-comment":
            cmd = base + [
                "issue",
                "comment",
                "--repo",
                repo,
                "--number",
                n,
                "--body",
                str(payload.get("body", "")),
            ]
        elif op_kind == "issue-label-add":
            cmd = base + [
                "issue",
                "label-add",
                "--repo",
                repo,
                "--number",
                n,
                "--label",
                str(payload.get("label", "")),
            ]
        elif op_kind == "issue-label-remove":
            cmd = base + [
                "issue",
                "label-remove",
                "--repo",
                repo,
                "--number",
                n,
                "--label",
                str(payload.get("label", "")),
            ]
        else:
            raise ValueError(f"no mission-control verb mapping for op_kind {op_kind!r}")
        result = run(cmd, capture_output=True, text=True, timeout=60)
        if getattr(result, "returncode", 0) != 0:
            raise RuntimeError(
                f"board write {op_kind} on {repo}#{number} failed: {getattr(result, 'stderr', '')!r}"
            )

    return _writer


def _default_ledger_dir(repo_root: Path) -> Path:
    """Default write-record ledger for skill consumers — git-ignored, machine-local, shared.

    A single dir is safe: ``idempotency_key`` namespaces every entry by op_kind+repo+number+state,
    so entries never collide across issues.
    """
    return repo_root / ".claude" / "saga" / "board-progression"


# ---------------------------------------------------------------------------
# CLI (so markdown skills /work and /loop can invoke the writer, #344 KTD6)
# ---------------------------------------------------------------------------


def _repo_root_default() -> Path:
    # plugins/saga/scripts/board_progression.py → parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Certificate-gated autonomous board writer (#344)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="authorize + idempotently write one board op")
    p_write.add_argument(
        "--op", required=True, help="OpKind, e.g. set-field-status | sub-issue-close"
    )
    p_write.add_argument(
        "--repo", required=True, help="owner/repo (owner used only for the key namespace)"
    )
    p_write.add_argument("--number", required=True, type=int)
    p_write.add_argument("--target-state", default="", help="e.g. Done (for set-field-status)")
    p_write.add_argument("--project", default="operations")
    p_write.add_argument("--payload", default="", help='JSON object, e.g. {"body": "..."}')
    p_write.add_argument(
        "--ledger-dir", default="", help="override the default board-progression ledger dir"
    )
    p_write.add_argument(
        "--repo-root", default="", help="override the repo root (default: derived from __file__)"
    )

    args = parser.parse_args(argv)

    if args.cmd == "write":
        repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_default()
        ledger_dir = (
            Path(args.ledger_dir).resolve() if args.ledger_dir else _default_ledger_dir(repo_root)
        )
        payload = json.loads(args.payload) if args.payload else None
        writer = default_board_writer(repo_root, project=args.project)
        record = authorize_and_write(
            args.op,
            args.repo,
            args.number,
            args.target_state,
            board_writer=writer,
            ledger_dir=ledger_dir,
            payload=payload,
        )
        print(json.dumps(record))
        # A gate is a normal, expected outcome (exit 0); only a hard write failure is non-zero.
        return 0 if record.get("status") in ("written", "skipped", "gated") else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
