#!/usr/bin/env python3
"""Mutation canary — prove the repo's drift guards have teeth (#427).

The repo carries a growing family of drift-guard tests (agent-registration drift, release-triad
lockstep, provenance-manifest consumer matrix, artifact-pointer integrity). CI only ever proves a
guard did *not* fire on today's clean tree — it can never distinguish "the tree is clean" from "the
guard is dead" (a loosened regex, a stale glob, a swallowed exception). This canary closes that gap.

For every guard named in ``tools/canary_registry.json`` it:

1. copies the repo into a throwaway checkout (a system tempdir — never the live working tree),
2. applies that entry's deliberate mutation to the copy, breaking the guarded invariant,
3. runs the target guard against the mutated copy,
4. classifies the guard's result:
   - ``caught``    — the guard went red on the broken invariant (it has teeth),
   - ``toothless`` — the guard stayed green on the broken invariant (it has regressed),
   - ``error``     — the guard could not be evaluated (bad mutation anchor / collection error).

The process exits non-zero if any guard is toothless or errored (R3). No mutation ever touches the
real working tree (R2): every edit happens inside the tempdir copy, which is removed afterwards.

Usage::

    python3 tools/wiring_canary.py                    # full registry (scheduled job)
    python3 tools/wiring_canary.py --target release-triad   # one guard (local debugging)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess  # noqa: S404 - runs pytest against a throwaway checkout, no shell, args are static
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "tools" / "canary_registry.json"
DEFAULT_LOG = REPO_ROOT / "docs" / "engineering-journal" / "canary-log.jsonl"

# The three canary outcomes (R3). ``caught`` is the only healthy result — a guard that fires red on
# a deliberately broken invariant. ``toothless`` and ``error`` both drive a non-zero exit.
CAUGHT = "caught"
TOOTHLESS = "toothless"
ERROR = "error"

# Directories never copied into a throwaway checkout: VCS metadata, virtualenvs, caches, and
# per-user state. None of them hold a guarded invariant, and all are large or machine-local.
_COPY_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    ".claude",
    ".saga-worktrees",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".neuralmind",
    "graphify-out",
    "dist",
    "build",
}


class CanaryError(RuntimeError):
    """A canary entry could not be evaluated (mutation anchor missing, unknown mutation kind)."""


@dataclass(frozen=True)
class Mutation:
    """A single deliberate edit applied to a throwaway checkout to break a guarded invariant."""

    kind: str
    file: str
    find: str | None = None
    replace: str | None = None
    key: str | None = None
    value: object | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Mutation:
        return cls(
            kind=str(data["kind"]),
            file=str(data["file"]),
            find=None if data.get("find") is None else str(data["find"]),
            replace=None if data.get("replace") is None else str(data["replace"]),
            key=None if data.get("key") is None else str(data["key"]),
            value=data.get("value"),
        )

    def describe(self) -> str:
        if self.kind == "replace_text":
            return f"replace_text in {self.file}: {self.find!r} -> {self.replace!r}"
        if self.kind == "set_json_field":
            return f"set_json_field in {self.file}: {self.key}={self.value!r}"
        return f"{self.kind} in {self.file}"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds")


def load_registry(path: Path) -> list[dict[str, object]]:
    """Load the canary registry, validating that each entry carries the required fields (R1)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise CanaryError(f"{path} must contain a JSON array of guard entries")
    required = {"id", "guard", "invariant", "mutation"}
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise CanaryError(f"{path} entry {i} is not an object")
        missing = required - entry.keys()
        if missing:
            raise CanaryError(
                f"{path} entry {i} ({entry.get('id')}) missing fields: {sorted(missing)}"
            )
    return data


def _copy_ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in _COPY_EXCLUDES}


def copy_repo(src: Path, dst: Path) -> None:
    """Copy the working tree into ``dst`` (a throwaway checkout), skipping VCS/venv/cache dirs."""
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_copy_ignore, symlinks=True)


def apply_mutation(checkout: Path, mutation: Mutation) -> None:
    """Apply ``mutation`` to the throwaway ``checkout`` only. Raises CanaryError on a stale anchor."""
    target = checkout / mutation.file
    if not target.is_file():
        raise CanaryError(f"mutation target does not exist in checkout: {mutation.file}")

    if mutation.kind == "replace_text":
        if mutation.find is None or mutation.replace is None:
            raise CanaryError(
                f"replace_text mutation on {mutation.file} needs 'find' and 'replace'"
            )
        text = target.read_text(encoding="utf-8")
        if mutation.find not in text:
            raise CanaryError(
                f"replace_text anchor not found in {mutation.file}: {mutation.find!r} "
                "(the guarded file changed — update tools/canary_registry.json)"
            )
        target.write_text(text.replace(mutation.find, mutation.replace, 1), encoding="utf-8")
        return

    if mutation.kind == "set_json_field":
        if mutation.key is None:
            raise CanaryError(f"set_json_field mutation on {mutation.file} needs 'key'")
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or mutation.key not in data:
            raise CanaryError(
                f"set_json_field key not present in {mutation.file}: {mutation.key!r} "
                "(the guarded file changed — update tools/canary_registry.json)"
            )
        data[mutation.key] = mutation.value
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return

    raise CanaryError(f"unknown mutation kind: {mutation.kind!r}")


def _guard_target(checkout: Path, guard_ref: str) -> str:
    """Resolve a ``tests/foo.py::node`` guard reference against the throwaway ``checkout``."""
    file_part, sep, node = guard_ref.partition("::")
    resolved = str(checkout / file_part)
    return f"{resolved}::{node}" if sep else resolved


def run_guard(checkout: Path, guard_ref: str) -> subprocess.CompletedProcess[str]:
    """Run the target guard (a pytest node) against the mutated ``checkout``.

    ``-o addopts=`` clears the repo's default ``--cov`` addopts so the guard runs standalone, and the
    checkout is the cwd so any ``__file__``-relative path resolution reads the mutated copy.
    """
    target = _guard_target(checkout, guard_ref)
    return subprocess.run(  # noqa: S603 - fixed argv (interpreter + pytest), no shell, no user input
        [sys.executable, "-m", "pytest", target, "-o", "addopts=", "-p", "no:cacheprovider", "-q"],
        cwd=str(checkout),
        capture_output=True,
        text=True,
        check=False,
    )


def classify(exit_code: int) -> str:
    """Map a pytest exit code to a canary outcome.

    pytest exit codes: 0 = all passed, 1 = tests failed. Any other code (2 interrupted, 3 internal
    error, 4 usage error, 5 no tests collected) means the guard could not be meaningfully evaluated.
    A deliberately broken invariant that leaves the guard green (exit 0) is ``toothless``.
    """
    if exit_code == 0:
        return TOOTHLESS
    if exit_code == 1:
        return CAUGHT
    return ERROR


def run_entry(entry: dict[str, object], repo_root: Path) -> dict[str, object]:
    """Copy the repo, apply the entry's mutation, run its guard, and return a structured record."""
    mutation = Mutation.from_dict(entry["mutation"])  # type: ignore[arg-type]
    checkout = Path(tempfile.mkdtemp(prefix="wiring-canary-"))
    detail = ""
    try:
        copy_repo(repo_root, checkout)
        apply_mutation(checkout, mutation)
        proc = run_guard(checkout, str(entry["guard"]))
        result = classify(proc.returncode)
        if result == ERROR:
            detail = (proc.stdout + proc.stderr).strip()[-500:]
    except CanaryError as exc:
        result = ERROR
        detail = str(exc)
    finally:
        shutil.rmtree(checkout, ignore_errors=True)

    return {
        "guard": str(entry["id"]),
        "guard_ref": str(entry["guard"]),
        "mutation": mutation.describe(),
        "result": result,
        "detail": detail,
        "timestamp": _now_iso(),
    }


def append_log(log_path: Path, record: dict[str, object]) -> None:
    """Append one structured record to the canary log (R6), creating parent dirs as needed."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def run_registry(
    entries: list[dict[str, object]],
    repo_root: Path,
    log_path: Path | None,
) -> list[dict[str, object]]:
    """Run every entry, append each record to the log (when ``log_path`` is set), return records."""
    records: list[dict[str, object]] = []
    for entry in entries:
        record = run_entry(entry, repo_root)
        if log_path is not None:
            append_log(log_path, record)
        records.append(record)
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mutation canary: break one guarded invariant in a throwaway checkout, run the guard, "
            "and prove it goes red. A guard that stays green is reported toothless."
        )
    )
    parser.add_argument(
        "--target",
        metavar="GUARD_ID",
        help="Run a single registered guard by id (default: the full registry).",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Path to the canary registry JSON (default: {DEFAULT_REGISTRY}).",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG,
        help=f"Path to the append-only canary log (default: {DEFAULT_LOG}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=f"Repo tree to copy into each throwaway checkout (default: {REPO_ROOT}).",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not append records to the canary log (used by the canary's own tests).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    entries = load_registry(args.registry)

    if args.target:
        entries = [e for e in entries if e.get("id") == args.target]
        if not entries:
            print(f"error: no registered guard with id {args.target!r}", file=sys.stderr)
            return 2

    log_path = None if args.no_log else args.log_path
    records = run_registry(entries, args.repo_root, log_path)

    for record in records:
        print(f"{record['guard']}: {record['result']}")

    toothless = [r for r in records if r["result"] == TOOTHLESS]
    errored = [r for r in records if r["result"] == ERROR]
    for record in errored:
        print(
            f"error: {record['guard']} could not be evaluated: {record['detail']}", file=sys.stderr
        )
    for record in toothless:
        print(
            f"TOOTHLESS: {record['guard']} stayed green against a broken invariant "
            f"({record['mutation']})",
            file=sys.stderr,
        )

    return 1 if (toothless or errored) else 0


if __name__ == "__main__":
    raise SystemExit(main())
