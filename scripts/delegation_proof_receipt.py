#!/usr/bin/env python3
"""Run and verify receipt-bound delegation proof gates for issue #355."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess  # nosec B404 - fixed local checker and git plumbing argv only.
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_delegation_proof.py"
SCHEMA = "delegation-proof-command-receipt.v3"
MODES = ("version-gate", "fleet-sweep")
RECEIPT_RELATIVE_PATHS = {
    "version-gate": Path("docs/evidence/issue-355/version-gate-command-receipt.json"),
    "fleet-sweep": Path("docs/evidence/issue-355/fleet-sweep-command-receipt.json"),
}
RECEIPT_EXCLUSIONS = frozenset(path.as_posix() for path in RECEIPT_RELATIVE_PATHS.values())
PROOFS_RELATIVE_PATH = Path("docs/delegation-proofs")
FULL_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
RECEIPT_KEYS = frozenset(
    {
        "schema",
        "mode",
        "argv",
        "cwd",
        "base_ref",
        "recorded_merge_base",
        "base_sha",
        "head_sha",
        "index_snapshot_sha256",
        "candidate_files",
        "candidate_snapshot_sha256",
        "proofs_dir",
        "transcripts_dir",
        "proof_artifacts",
        "transcript_artifacts",
        "stdout",
        "stderr",
        "exit_code",
        "started_at",
        "ended_at",
        "sha256",
    }
)


class ReceiptError(RuntimeError):
    """A command receipt is malformed, stale, or does not prove a passing gate."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical({key: item for key, item in value.items() if key != "sha256"})
    ).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    completed = subprocess.run(  # nosec B603 - fixed git executable and caller-owned fixed args.
        ["git", *args],
        cwd=cwd,
        text=True,
        errors="surrogateescape",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReceiptError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.rstrip("\n")


def _fixed_receipt_path(mode: str) -> Path:
    try:
        relative = RECEIPT_RELATIVE_PATHS[mode]
    except KeyError as exc:
        raise ReceiptError(f"unsupported receipt mode: {mode!r}") from exc
    return REPO_ROOT / relative


def _fixed_proofs_path() -> Path:
    return REPO_ROOT / PROOFS_RELATIVE_PATH


def _normalized_receipt_path(path: Path) -> Path:
    candidate = path if path.is_absolute() else REPO_ROOT / path
    return Path(os.path.abspath(candidate))


def _require_fixed_receipt_path(path: Path, mode: str) -> Path:
    expected = _normalized_receipt_path(_fixed_receipt_path(mode))
    if _normalized_receipt_path(path) != expected:
        raise ReceiptError(f"{mode} receipt must use fixed repository path {expected}")
    repository_root = _normalized_receipt_path(REPO_ROOT)
    relative = expected.relative_to(repository_root)
    current = repository_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ReceiptError(
                f"fixed repository receipt path must not traverse a symlink: {current}"
            )
    return expected


def _require_fixed_proofs_path(path: Path, *, label: str) -> Path:
    expected = _normalized_receipt_path(_fixed_proofs_path())
    if _normalized_receipt_path(path) != expected:
        raise ReceiptError(f"{label} must use fixed repository proof path {expected}")
    repository_root = _normalized_receipt_path(REPO_ROOT)
    relative = expected.relative_to(repository_root)
    current = repository_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ReceiptError(
                f"fixed repository proof path must not traverse a symlink: {current}"
            )
    return expected


def _canonical_artifact_roots(
    *, mode: str, proofs_dir: Path, transcripts_dir: Path | None
) -> tuple[Path, Path | None]:
    proofs = _require_fixed_proofs_path(proofs_dir, label="proofs_dir")
    if mode == "version-gate":
        if transcripts_dir is not None:
            raise ReceiptError("version-gate transcripts_dir must be omitted")
        return proofs, None
    if mode == "fleet-sweep":
        if transcripts_dir is None:
            raise ReceiptError("fleet-sweep requires transcripts_dir")
        transcripts = _require_fixed_proofs_path(
            transcripts_dir, label="fleet-sweep transcripts_dir"
        )
        return proofs, transcripts
    raise ReceiptError(f"unsupported receipt mode: {mode!r}")


def _immutable_base_state(base_ref: str) -> tuple[str, str]:
    if FULL_SHA_PATTERN.fullmatch(base_ref) is None:
        raise ReceiptError("base_ref must be an explicit full 40-hex immutable SHA")
    base_sha = _git("rev-parse", base_ref)
    if base_sha != base_ref:
        raise ReceiptError("base_ref must resolve exactly to its recorded immutable SHA")
    recorded_merge_base = _git("merge-base", "HEAD", base_ref)
    if recorded_merge_base != base_ref:
        raise ReceiptError("base_ref must equal the live git merge-base of HEAD and base_ref")
    return base_sha, recorded_merge_base


def _mode_for_fixed_receipt_path(path: Path) -> str:
    normalized = _normalized_receipt_path(path)
    for mode in MODES:
        if normalized == _normalized_receipt_path(_fixed_receipt_path(mode)):
            return mode
    expected = ", ".join(str(_fixed_receipt_path(mode)) for mode in MODES)
    raise ReceiptError(f"receipt must use one of the fixed repository paths: {expected}")


def _repository_mode_and_bytes(path: Path) -> tuple[str, bytes]:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        return "120000", os.fsencode(os.readlink(path))
    if stat.S_ISREG(metadata.st_mode):
        mode = "100755" if metadata.st_mode & stat.S_IXUSR else "100644"
        return mode, path.read_bytes()
    raise ReceiptError(f"candidate path has unsupported file type: {path}")


def _candidate_rows() -> list[dict[str, Any]]:
    raw_paths = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    relative_paths = sorted({item for item in raw_paths.split("\0") if item})
    rows: list[dict[str, Any]] = []
    for relative in relative_paths:
        if relative in RECEIPT_EXCLUSIONS:
            continue
        path = REPO_ROOT / relative
        try:
            mode, content = _repository_mode_and_bytes(path)
        except FileNotFoundError:
            rows.append({"path": relative, "mode": "deleted", "sha256": None})
            continue
        rows.append(
            {
                "path": relative,
                "mode": mode,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows


def _candidate_snapshot_digest(
    *,
    base_ref: str,
    base_sha: str,
    recorded_merge_base: str,
    index_snapshot_sha256: str,
    candidate_files: Sequence[Mapping[str, Any]],
) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "base_ref": base_ref,
                "base_sha": base_sha,
                "recorded_merge_base": recorded_merge_base,
                "index_snapshot_sha256": index_snapshot_sha256,
                "candidate_files": list(candidate_files),
            }
        )
    ).hexdigest()


def _candidate_state(*, base_ref: str, base_sha: str, recorded_merge_base: str) -> dict[str, Any]:
    """Capture every mutable Git/candidate surface that the checker can observe."""

    head_sha = _git("rev-parse", "HEAD")
    index_raw = _git("ls-files", "-s", "-z")
    index_rows = sorted(
        row
        for row in index_raw.split("\0")
        if row and row.split("\t", 1)[-1] not in RECEIPT_EXCLUSIONS
    )
    index_snapshot_sha256 = hashlib.sha256(
        json.dumps(index_rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    candidate_files = _candidate_rows()
    return {
        "base_ref": base_ref,
        "base_sha": base_sha,
        "recorded_merge_base": recorded_merge_base,
        "head_sha": head_sha,
        "index_snapshot_sha256": index_snapshot_sha256,
        "candidate_files": candidate_files,
        "candidate_snapshot_sha256": _candidate_snapshot_digest(
            base_ref=base_ref,
            base_sha=base_sha,
            recorded_merge_base=recorded_merge_base,
            index_snapshot_sha256=index_snapshot_sha256,
            candidate_files=candidate_files,
        ),
    }


def _artifact_rows(root: Path, pattern: str) -> list[dict[str, str]]:
    root = _require_fixed_proofs_path(root, label="artifact root")
    if not root.is_dir():
        return []
    rows = []
    for path in sorted(root.rglob(pattern)):
        if "examples" in path.relative_to(root).parts or not path.is_file():
            continue
        if path.is_symlink():
            raise ReceiptError(f"proof artifact must not be a symlink: {path}")
        relative = path.relative_to(root)
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ReceiptError(f"proof artifact must not traverse a symlink: {current}")
        rendered = (PROOFS_RELATIVE_PATH / relative).as_posix()
        mode, content = _repository_mode_and_bytes(path)
        rows.append(
            {
                "path": rendered,
                "mode": mode,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows


def _validate_artifact_rows(value: Any, *, label: str) -> None:
    if not isinstance(value, list):
        raise ReceiptError(f"command receipt {label} are malformed")
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "mode", "sha256"}
            or not isinstance(row["path"], str)
            or row["mode"] not in {"100644", "100755"}
            or not isinstance(row["sha256"], str)
            or len(row["sha256"]) != 64
        ):
            raise ReceiptError(f"command receipt {label} are malformed")
        path = PurePosixPath(row["path"])
        try:
            path.relative_to(PurePosixPath(PROOFS_RELATIVE_PATH.as_posix()))
        except ValueError as exc:
            raise ReceiptError(
                f"command receipt {label} must be repository-relative under "
                f"{PROOFS_RELATIVE_PATH.as_posix()}"
            ) from exc
        if path.is_absolute() or ".." in path.parts:
            raise ReceiptError(
                f"command receipt {label} must be repository-relative under "
                f"{PROOFS_RELATIVE_PATH.as_posix()}"
            )


def _checker_argv(
    *, mode: str, base_ref: str, proofs_dir: Path, transcripts_dir: Path | None
) -> list[str]:
    argv = [
        sys.executable,
        str(CHECKER),
        "--mode",
        mode,
        "--proofs-dir",
        str(proofs_dir),
    ]
    if mode == "version-gate":
        argv.extend(["--base-ref", base_ref])
    elif mode == "fleet-sweep":
        if transcripts_dir is None:
            raise ReceiptError("fleet-sweep requires transcripts_dir")
        argv.extend(["--transcripts-dir", str(transcripts_dir)])
    else:
        raise ReceiptError(f"unsupported receipt mode: {mode!r}")
    return argv


def _write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if path.exists() and stat.S_ISLNK(path.lstat().st_mode):
        raise ReceiptError("receipt output must not be a symlink")
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical(receipt) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        if temp.exists():
            temp.unlink()


def run_gate(
    *,
    mode: str,
    base_ref: str,
    proofs_dir: Path,
    transcripts_dir: Path | None,
    receipt_out: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    receipt_path = _require_fixed_receipt_path(receipt_out, mode)
    proofs, transcripts = _canonical_artifact_roots(
        mode=mode, proofs_dir=proofs_dir, transcripts_dir=transcripts_dir
    )
    base_sha, recorded_merge_base = _immutable_base_state(base_ref)
    argv = _checker_argv(
        mode=mode, base_ref=base_ref, proofs_dir=proofs, transcripts_dir=transcripts
    )
    before_state = _candidate_state(
        base_ref=base_ref,
        base_sha=base_sha,
        recorded_merge_base=recorded_merge_base,
    )
    before_proofs = _artifact_rows(proofs, "*.proof.json")
    before_transcripts = _artifact_rows(
        proofs if transcripts is None else transcripts, "*.transcript.jsonl"
    )
    started = _utc_now()
    completed = runner(  # nosec B603 - argv is closed above and shell is never enabled.
        argv, cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    ended = _utc_now()
    after_base_sha, after_merge_base = _immutable_base_state(base_ref)
    after_state = _candidate_state(
        base_ref=base_ref,
        base_sha=after_base_sha,
        recorded_merge_base=after_merge_base,
    )
    after_proofs = _artifact_rows(proofs, "*.proof.json")
    after_transcripts = _artifact_rows(
        proofs if transcripts is None else transcripts, "*.transcript.jsonl"
    )
    if (
        after_state != before_state
        or after_proofs != before_proofs
        or after_transcripts != before_transcripts
    ):
        raise ReceiptError(
            "repository, index, proof, or transcript state changed while the checker ran"
        )
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "mode": mode,
        "argv": argv,
        "cwd": str(REPO_ROOT),
        "base_ref": base_ref,
        "recorded_merge_base": recorded_merge_base,
        "base_sha": base_sha,
        "head_sha": before_state["head_sha"],
        "index_snapshot_sha256": before_state["index_snapshot_sha256"],
        "candidate_files": before_state["candidate_files"],
        "candidate_snapshot_sha256": before_state["candidate_snapshot_sha256"],
        "proofs_dir": str(proofs),
        "transcripts_dir": None if transcripts is None else str(transcripts),
        "proof_artifacts": before_proofs,
        "transcript_artifacts": before_transcripts,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
        "started_at": started,
        "ended_at": ended,
    }
    receipt["sha256"] = _digest(receipt)
    _write_receipt(receipt_path, receipt)
    if completed.returncode != 0:
        raise ReceiptError(
            f"delegation proof {mode} failed with exit {completed.returncode}; receipt retained"
        )
    return receipt


def _load_receipt(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"cannot load command receipt: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != RECEIPT_KEYS:
        raise ReceiptError("command receipt fields are malformed")
    if raw.get("schema") != SCHEMA or raw.get("mode") not in MODES:
        raise ReceiptError("command receipt schema or mode is invalid")
    if raw.get("sha256") != _digest(raw):
        raise ReceiptError("command receipt self-digest does not match")
    return raw


def verify_receipt(
    path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    expected_mode = _mode_for_fixed_receipt_path(path)
    receipt_path = _require_fixed_receipt_path(path, expected_mode)
    if receipt_path.is_symlink():
        raise ReceiptError("receipt output must not be a symlink")
    receipt = _load_receipt(receipt_path)
    if receipt["mode"] != expected_mode:
        raise ReceiptError("command receipt mode does not match its fixed repository path")
    proofs_raw = receipt["proofs_dir"]
    if not isinstance(proofs_raw, str):
        raise ReceiptError("command receipt proofs_dir is invalid")
    proofs = Path(proofs_raw)
    transcripts_raw = receipt["transcripts_dir"]
    if transcripts_raw is not None and not isinstance(transcripts_raw, str):
        raise ReceiptError("command receipt transcripts_dir is invalid")
    transcripts = None if transcripts_raw is None else Path(transcripts_raw)
    proofs, transcripts = _canonical_artifact_roots(
        mode=receipt["mode"], proofs_dir=proofs, transcripts_dir=transcripts
    )
    expected_argv = _checker_argv(
        mode=receipt["mode"],
        base_ref=receipt["base_ref"],
        proofs_dir=proofs,
        transcripts_dir=transcripts,
    )
    if receipt["argv"] != expected_argv or receipt["cwd"] != str(REPO_ROOT):
        raise ReceiptError("command receipt argv or cwd is not the fixed proof command")
    if receipt["exit_code"] != 0:
        raise ReceiptError("command receipt records a nonzero proof command")
    for field in ("recorded_merge_base", "base_sha", "head_sha"):
        value = receipt[field]
        if not isinstance(value, str) or len(value) != 40:
            raise ReceiptError(f"command receipt {field} is invalid")
    if (
        not isinstance(receipt["index_snapshot_sha256"], str)
        or len(receipt["index_snapshot_sha256"]) != 64
    ):
        raise ReceiptError("command receipt index_snapshot_sha256 is invalid")
    base_ref = receipt["base_ref"]
    if not isinstance(base_ref, str) or FULL_SHA_PATTERN.fullmatch(base_ref) is None:
        raise ReceiptError("command receipt base_ref is not a full 40-hex immutable SHA")
    if receipt["base_sha"] != base_ref:
        raise ReceiptError("command receipt base SHA does not equal its immutable base_ref")
    if receipt["recorded_merge_base"] != base_ref:
        raise ReceiptError("command receipt recorded merge base does not equal its base_ref")
    candidate_files = receipt["candidate_files"]
    if not isinstance(candidate_files, list) or any(
        not isinstance(row, dict)
        or set(row) != {"path", "mode", "sha256"}
        or not isinstance(row["path"], str)
        or row["path"] in RECEIPT_EXCLUSIONS
        or row["mode"] not in {"100644", "100755", "120000", "deleted"}
        or (
            row["sha256"] is not None
            and (not isinstance(row["sha256"], str) or len(row["sha256"]) != 64)
        )
        or (row["mode"] == "deleted") != (row["sha256"] is None)
        for row in candidate_files
    ):
        raise ReceiptError("command receipt candidate file snapshot is malformed")
    expected_snapshot_sha256 = _candidate_snapshot_digest(
        base_ref=receipt["base_ref"],
        base_sha=receipt["base_sha"],
        recorded_merge_base=receipt["recorded_merge_base"],
        index_snapshot_sha256=receipt["index_snapshot_sha256"],
        candidate_files=candidate_files,
    )
    if receipt["candidate_snapshot_sha256"] != expected_snapshot_sha256:
        raise ReceiptError("command receipt candidate snapshot digest does not match")
    _validate_artifact_rows(receipt["proof_artifacts"], label="proof artifacts")
    _validate_artifact_rows(receipt["transcript_artifacts"], label="transcript artifacts")
    live_base = _git("rev-parse", base_ref)
    if receipt["base_sha"] != live_base:
        raise ReceiptError("command receipt base no longer matches the live repository")
    if base_ref != _git("merge-base", "HEAD", base_ref):
        raise ReceiptError("command receipt merge base no longer matches the live repository")
    expected_state = _candidate_state(
        base_ref=receipt["base_ref"],
        base_sha=live_base,
        recorded_merge_base=receipt["recorded_merge_base"],
    )
    expected_candidate_files = expected_state["candidate_files"]
    if (
        receipt["index_snapshot_sha256"] != expected_state["index_snapshot_sha256"]
        or candidate_files != expected_candidate_files
    ):
        raise ReceiptError("command receipt candidate files, modes, or digests do not match")
    if receipt["candidate_snapshot_sha256"] != expected_state["candidate_snapshot_sha256"]:
        raise ReceiptError("command receipt candidate snapshot no longer matches")
    expected_proofs = _artifact_rows(proofs, "*.proof.json")
    expected_transcripts = _artifact_rows(
        proofs if transcripts is None else transcripts, "*.transcript.jsonl"
    )
    if receipt["proof_artifacts"] != expected_proofs:
        raise ReceiptError("command receipt proof artifacts or digests do not match")
    if receipt["transcript_artifacts"] != expected_transcripts:
        raise ReceiptError("command receipt transcript artifacts or digests do not match")
    if not receipt["proof_artifacts"] or not receipt["transcript_artifacts"]:
        raise ReceiptError("command receipt lacks genuine proof or transcript artifacts")
    before_replay_state = expected_state
    completed = runner(  # nosec B603 - expected_argv is reconstructed from the closed receipt.
        expected_argv,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    after_replay_state = _candidate_state(
        base_ref=receipt["base_ref"],
        base_sha=live_base,
        recorded_merge_base=receipt["recorded_merge_base"],
    )
    if (
        after_replay_state != before_replay_state
        or completed.returncode != 0
        or completed.stdout != receipt["stdout"]
        or completed.stderr != receipt["stderr"]
    ):
        raise ReceiptError("command receipt cannot be reproduced by the fixed proof command")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    run_parser = subcommands.add_parser("run")
    run_parser.add_argument("--mode", choices=MODES, required=True)
    run_parser.add_argument("--base-ref", required=True)
    run_parser.add_argument("--proofs-dir", type=Path, required=True)
    run_parser.add_argument("--transcripts-dir", type=Path)
    run_parser.add_argument("--receipt-out", type=Path, required=True)
    verify_parser = subcommands.add_parser("verify")
    verify_parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        run_gate(
            mode=args.mode,
            base_ref=args.base_ref,
            proofs_dir=args.proofs_dir,
            transcripts_dir=args.transcripts_dir,
            receipt_out=args.receipt_out,
        )
    else:
        verify_receipt(args.receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReceiptError as exc:
        print(f"delegation-proof-receipt: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
