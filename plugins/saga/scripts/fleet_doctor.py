#!/usr/bin/env python3
"""Fleet doctor — strict, bounded, read-only cross-source fleet audit (#353).

One repo-scoped point-in-time report (``fleet_doctor_report.v1``), derived fresh on every call
(R1): the doctor never appends facts, creates caches, heals tails, quarantines files, persists
status, settles, acknowledges, releases, tears down, retries, or removes anything. Findings name
the owning recovery command but never call it.

Independence is the design (KTD1): this module reads the documented raw on-disk contracts of the
#351/#355/#356/#357/#358 producers through its own strict readers and owns every join. It must
never import the tolerant or mutating readers whose failure modes it audits — no
``outcome_worktrees``, ``outcome_store``, ``dispatch_settlement``, ``team_teardown``,
``reap_orphans``, ``audit_store``, or broker mutation APIs (R2); the U4 conformance denylist makes
that executable.

Absence, corruption, and incompleteness are three different verdicts (KTD2): a corrupt file,
unsafe path, mid-scan source change, or capacity overflow yields an incomplete report and exit 2 —
it can never degrade to an empty source and return clean. Exit 0 requires a complete scan with
zero findings and zero evidence errors; exit 1 is a complete scan with disease findings (R8).
"""

from __future__ import annotations

import sys

# R2: observation must not shed bytecode into the repositories and stores it audits.
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import stat as stat_mod  # noqa: E402
import subprocess  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

SCHEMA = "fleet_doctor_report.v1"

DISEASES = ("leaked-resource", "unledgered-spawn", "receiptless-delegation", "evidence-error")

# Bounded-input caps (R8). Hitting a cap is scan-incomplete and exit 2, never truncation-to-clean.
MAX_STATE_BYTES = 8 * 1024 * 1024  # registry / single-state JSON
MAX_ARTIFACT_BYTES = 1 * 1024 * 1024  # each audit or bundle artifact
MAX_LEDGER_BYTES = 64 * 1024 * 1024  # run-fact ledger
GIT_STDOUT_CAP = 8 * 1024 * 1024
GIT_STDERR_CAP = 64 * 1024
GIT_TIMEOUT_SECONDS = 10
MAX_SOURCE_ENTRIES = 10_000
MAX_FINDINGS = 10_000
MAX_DEPTH = 6
MAX_OUTPUT_BYTES = 16 * 1024 * 1024

# Producer path constants (documented raw contracts; see references/fleet-doctor-sources.md).
RUN_FACTS_RELPATH = Path("saga-run-facts") / "run-facts.jsonl"
LEASE_REGISTRY_NAME = "registry.json"
LEASE_REGISTRY_SCHEMA = "fleet_lease_registry.v1"
AUDIT_RUNS_DIRNAME = "runs"

_SAFE_COMPONENT = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")

# Injectable seams for deterministic tests (monkeypatched; never mutated in production).
_lstat = os.lstat
_geteuid = os.geteuid


class StrictReadError(Exception):
    """A strict-read failure: classification plus a bounded, redacted subject."""

    def __init__(self, classification: str, subject_id: str, evidence: list[str]) -> None:
        super().__init__(f"{classification}: {subject_id}")
        self.classification = classification
        self.subject_id = subject_id
        self.evidence = evidence


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def parse_strict_json(data: bytes, *, what: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_pairs)
    except (ValueError, UnicodeDecodeError) as exc:
        raise StrictReadError("malformed-json", what, [f"{what}: {exc}"]) from None


@dataclass(frozen=True)
class Source:
    kind: str
    identity: str
    digest: str
    record_count: int
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "identity": self.identity,
            "digest": self.digest,
            "record_count": self.record_count,
            "verdict": self.verdict,
        }


@dataclass(frozen=True)
class Finding:
    disease: str
    classification: str
    subject_id: str
    evidence_refs: tuple[str, ...]
    owner_command: str

    @property
    def finding_id(self) -> str:
        identity = {
            "disease": self.disease,
            "classification": self.classification,
            "subject_id": self.subject_id,
        }
        return sha256_hex(canonical_json(identity).encode("utf-8"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "disease": self.disease,
            "classification": self.classification,
            "subject_id": self.subject_id,
            "evidence_refs": list(self.evidence_refs),
            "owner_command": self.owner_command,
        }


# Owner guidance is bounded, static text (R7): it names the owning surface and is never executed.
_EVIDENCE_OWNER_COMMANDS = {
    "config-error": "fleet-doctor --help",
    "malformed-json": "/delegation-audit",
    "unsafe-path": "/delegation-audit",
    "nonregular-file": "/delegation-audit",
    "chain-broken": "/delegation-audit",
    "schema-skew": "/delegation-audit",
    "source-changed": "fleet-doctor (re-run when the fleet is quiescent)",
    "cap-exceeded": "fleet-doctor (raise no cap; scope the store)",
    "traversal-identity": "/delegation-audit",
}


def evidence_error(classification: str, subject_id: str, evidence: list[str]) -> Finding:
    return Finding(
        disease="evidence-error",
        classification=classification,
        subject_id=subject_id,
        evidence_refs=tuple(sorted(set(evidence))),
        owner_command=_EVIDENCE_OWNER_COMMANDS.get(classification, "/delegation-audit"),
    )


@dataclass
class Scan:
    """Mutable in-memory accumulation for one derivation. Never persisted (R1)."""

    repo_identity: str = ""
    complete: bool = True
    sources: list[Source] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_source(self, source: Source) -> None:
        self.sources.append(source)

    def add_finding(self, finding: Finding) -> None:
        if len(self.findings) >= MAX_FINDINGS:
            self.mark_incomplete(f"finding cap {MAX_FINDINGS} reached; further findings dropped")
            return
        self.findings.append(finding)

    def add_problem(self, problem: StrictReadError) -> None:
        self.add_finding(
            evidence_error(problem.classification, problem.subject_id, problem.evidence)
        )
        self.complete = False

    def mark_incomplete(self, warning: str) -> None:
        self.complete = False
        if warning not in self.warnings:
            self.warnings.append(warning)


@dataclass(frozen=True)
class Redactor:
    """Path presentation policy (R7): repo paths relative, machine-local roots labeled."""

    repo_root: Path
    labeled_roots: tuple[tuple[str, Path], ...]
    show_local_paths: bool

    def present(self, path: Path) -> str:
        resolved = Path(path)
        if self.show_local_paths:
            return str(resolved)
        try:
            return str(resolved.relative_to(self.repo_root))
        except ValueError:
            pass
        for label, root in self.labeled_roots:
            try:
                relative = resolved.relative_to(root)
            except ValueError:
                continue
            head = relative.parts[:2]
            return f"{label}:{'/'.join(head)}" if head else label
        return "<external-path-redacted>"


def safe_component(name: str) -> bool:
    return bool(name) and name not in (".", "..") and all(ch in _SAFE_COMPONENT for ch in name)


def _require_regular(path: Path, presented: str) -> os.stat_result:
    try:
        st = _lstat(path)
    except FileNotFoundError:
        raise StrictReadError("config-error", presented, [f"{presented}: does not exist"]) from None
    except OSError as exc:
        raise StrictReadError("unsafe-path", presented, [f"{presented}: {exc}"]) from None
    if stat_mod.S_ISLNK(st.st_mode):
        raise StrictReadError("unsafe-path", presented, [f"{presented}: is a symlink"])
    if not stat_mod.S_ISREG(st.st_mode):
        raise StrictReadError("nonregular-file", presented, [f"{presented}: not a regular file"])
    return st


def require_owned_dir(path: Path, presented: str) -> None:
    """Configured store roots must be pre-existing, effective-user-owned, non-symlink dirs (R3)."""
    try:
        st = _lstat(path)
    except FileNotFoundError:
        raise StrictReadError("config-error", presented, [f"{presented}: does not exist"]) from None
    except OSError as exc:
        raise StrictReadError("unsafe-path", presented, [f"{presented}: {exc}"]) from None
    if stat_mod.S_ISLNK(st.st_mode):
        raise StrictReadError("unsafe-path", presented, [f"{presented}: is a symlink"])
    if not stat_mod.S_ISDIR(st.st_mode):
        raise StrictReadError("unsafe-path", presented, [f"{presented}: not a directory"])
    if st.st_uid != _geteuid():
        raise StrictReadError(
            "unsafe-path", presented, [f"{presented}: not owned by effective user"]
        )


def read_bounded_file(path: Path, *, cap: int, presented: str) -> bytes:
    """Pre-stat, capped read, post-stat: a mid-read change is incomplete, never retried (R3)."""
    before = _require_regular(path, presented)
    if before.st_size > cap:
        raise StrictReadError(
            "cap-exceeded", presented, [f"{presented}: {before.st_size} bytes exceeds cap {cap}"]
        )
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        data = os.read(fd, cap + 1)
    finally:
        os.close(fd)
    if len(data) > cap:
        raise StrictReadError("cap-exceeded", presented, [f"{presented}: grew beyond cap {cap}"])
    after = _require_regular(path, presented)
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise StrictReadError(
            "source-changed", presented, [f"{presented}: changed during scan; report incomplete"]
        )
    return data


def run_git(repo_root: Path, *args: str) -> str:
    """One fixed-argv read-only git command with the R3 timeout and output caps."""
    presented = f"git {args[0]}" if args else "git"
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell, bounded by timeout
            ["git", "-C", str(repo_root), "--no-pager", *args],
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        raise StrictReadError("config-error", presented, ["git executable not found"]) from None
    except subprocess.TimeoutExpired:
        raise StrictReadError(
            "cap-exceeded", presented, [f"{presented}: exceeded {GIT_TIMEOUT_SECONDS}s timeout"]
        ) from None
    if len(result.stdout) > GIT_STDOUT_CAP or len(result.stderr) > GIT_STDERR_CAP:
        raise StrictReadError("cap-exceeded", presented, [f"{presented}: output beyond cap"])
    if result.returncode != 0:
        raise StrictReadError("config-error", presented, [f"{presented}: exit {result.returncode}"])
    return result.stdout.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RepoContext:
    repo_root: Path
    common_dir: Path


def resolve_repo(repo_root: Path) -> RepoContext:
    toplevel = Path(run_git(repo_root, "rev-parse", "--show-toplevel").strip())
    common_raw = run_git(repo_root, "rev-parse", "--git-common-dir").strip()
    common = Path(common_raw)
    if not common.is_absolute():
        common = toplevel / common
    return RepoContext(repo_root=toplevel, common_dir=common.resolve())


def default_lease_store_root() -> Path:
    env = os.environ.get("INFIQUETRA_FLEET_STATE_DIR")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "infiquetra" / "fleet-leases"


def default_audit_store_root() -> Path:
    return Path.home() / ".claude" / "delegation-audit"


def verify_run_fact_chain(data: bytes, *, presented: str, scan: Scan) -> list[dict[str, Any]]:
    """Independently re-derive the #351 hash chain over ``run_fact.v1`` records.

    ``this_hash`` is sha256 of the canonical record including ``prev_hash`` and excluding
    ``this_hash``; ``prev_hash`` links to the prior record ("" at genesis). A torn trailing
    line is the producers' documented crash artifact: the valid prefix stands, with a warning.
    Any earlier malformed line, hash mismatch, or link break is a broken chain (KTD2).
    """
    records: list[dict[str, Any]] = []
    lines = data.split(b"\n")
    torn = b""
    if lines and lines[-1] != b"":
        torn = lines[-1]
        lines = lines[:-1]
    else:
        lines = lines[:-1] if lines else lines
    prev_hash = ""
    for index, line in enumerate(lines):
        what = f"{presented}#{index + 1}"
        record = parse_strict_json(line, what=what)
        if not isinstance(record, dict):
            raise StrictReadError("chain-broken", what, [f"{what}: record is not an object"])
        claimed = record.get("this_hash")
        body = {key: value for key, value in record.items() if key != "this_hash"}
        derived = sha256_hex(canonical_json(body).encode("utf-8"))
        if claimed != derived:
            raise StrictReadError("chain-broken", what, [f"{what}: this_hash mismatch"])
        if record.get("prev_hash") != prev_hash:
            raise StrictReadError("chain-broken", what, [f"{what}: prev_hash link break"])
        prev_hash = derived
        records.append(record)
        if len(records) > MAX_SOURCE_ENTRIES:
            raise StrictReadError(
                "cap-exceeded",
                presented,
                [f"{presented}: more than {MAX_SOURCE_ENTRIES} records"],
            )
    if torn:
        try:
            parse_strict_json(torn, what=f"{presented}#torn-tail")
        except StrictReadError:
            scan.warnings.append(f"{presented}: torn trailing line ignored (valid-prefix chain)")
        else:
            raise StrictReadError(
                "chain-broken",
                f"{presented}#torn-tail",
                [f"{presented}: complete trailing record missing newline is a torn append"],
            )
    return records


def collect_run_facts(scan: Scan, context: RepoContext, redactor: Redactor) -> list[dict[str, Any]]:
    path = context.common_dir / RUN_FACTS_RELPATH
    presented = redactor.present(path)
    if not path.exists() or _is_symlink(path):
        scan.add_source(
            Source(
                kind="run-facts", identity=presented, digest="", record_count=0, verdict="absent"
            )
        )
        return []
    try:
        data = read_bounded_file(path, cap=MAX_LEDGER_BYTES, presented=presented)
        records = verify_run_fact_chain(data, presented=presented, scan=scan)
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="run-facts",
                identity=presented,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return []
    scan.add_source(
        Source(
            kind="run-facts",
            identity=presented,
            digest=sha256_hex(data),
            record_count=len(records),
            verdict="verified-chain",
        )
    )
    return records


def _is_symlink(path: Path) -> bool:
    try:
        return stat_mod.S_ISLNK(_lstat(path).st_mode)
    except OSError:
        return False


def collect_lease_registry(
    scan: Scan, redactor: Redactor, lease_root: Path, *, explicit: bool
) -> dict[str, Any] | None:
    presented = redactor.present(lease_root / LEASE_REGISTRY_NAME)
    root_presented = redactor.present(lease_root)
    if not lease_root.exists() and not explicit:
        scan.add_source(
            Source(
                kind="lease-registry",
                identity=presented,
                digest="",
                record_count=0,
                verdict="absent",
            )
        )
        return None
    try:
        require_owned_dir(lease_root, root_presented)
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="lease-registry",
                identity=presented,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return None
    registry_path = lease_root / LEASE_REGISTRY_NAME
    if not registry_path.exists() and not _is_symlink(registry_path):
        scan.add_source(
            Source(
                kind="lease-registry",
                identity=presented,
                digest="",
                record_count=0,
                verdict="absent",
            )
        )
        return None
    try:
        data = read_bounded_file(registry_path, cap=MAX_STATE_BYTES, presented=presented)
        registry = parse_strict_json(data, what=presented)
        if not isinstance(registry, dict) or registry.get("schema") != LEASE_REGISTRY_SCHEMA:
            raise StrictReadError(
                "schema-skew",
                presented,
                [f"{presented}: schema is not {LEASE_REGISTRY_SCHEMA}"],
            )
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="lease-registry",
                identity=presented,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return None
    leases = registry.get("leases")
    count = len(leases) if isinstance(leases, dict) else 0
    scan.add_source(
        Source(
            kind="lease-registry",
            identity=presented,
            digest=sha256_hex(data),
            record_count=count,
            verdict="present",
        )
    )
    return registry


def collect_audit_store(
    scan: Scan, redactor: Redactor, audit_root: Path, *, explicit: bool
) -> list[str]:
    runs_dir = audit_root / AUDIT_RUNS_DIRNAME
    presented = redactor.present(runs_dir)
    root_presented = redactor.present(audit_root)
    if not audit_root.exists() and not explicit:
        scan.add_source(
            Source(
                kind="audit-store", identity=presented, digest="", record_count=0, verdict="absent"
            )
        )
        return []
    try:
        require_owned_dir(audit_root, root_presented)
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="audit-store",
                identity=presented,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return []
    if not runs_dir.exists() and not _is_symlink(runs_dir):
        scan.add_source(
            Source(
                kind="audit-store", identity=presented, digest="", record_count=0, verdict="absent"
            )
        )
        return []
    run_ids: list[str] = []
    try:
        require_owned_dir(runs_dir, presented)
        with os.scandir(runs_dir) as entries:
            for entry in entries:
                if len(run_ids) >= MAX_SOURCE_ENTRIES:
                    raise StrictReadError(
                        "cap-exceeded",
                        presented,
                        [f"{presented}: more than {MAX_SOURCE_ENTRIES} runs"],
                    )
                if not safe_component(entry.name):
                    raise StrictReadError(
                        "traversal-identity",
                        f"{presented}:<unsafe-run-id>",
                        [f"{presented}: run id fails the safe-component charset"],
                    )
                if not entry.is_dir(follow_symlinks=False):
                    raise StrictReadError(
                        "nonregular-file",
                        f"{presented}:{entry.name}",
                        [f"{presented}: run entry is not a directory"],
                    )
                run_ids.append(entry.name)
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="audit-store",
                identity=presented,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return []
    run_ids.sort()
    digest = sha256_hex(canonical_json(run_ids).encode("utf-8"))
    scan.add_source(
        Source(
            kind="audit-store",
            identity=presented,
            digest=digest,
            record_count=len(run_ids),
            verdict="present",
        )
    )
    return run_ids


# --------------------------------------------------------------- U2: worktree reconciliation

MANAGED_WORKTREES_DIRNAME = ".saga-worktrees"
SHARED_INSTALL_DIRNAME = "_shared-install"
OUTCOMES_DIRNAME = "saga-outcomes"
WORKTREE_REGISTRY_NAME = "worktrees.json"
_REGISTRY_ENTRY_REQUIRED = frozenset(
    {"path", "branch", "owner", "shared_install_ref", "at", "repo_root", "outcome_id"}
)
_REGISTRY_ENTRY_OPTIONAL = frozenset({"lease"})


def collect_git_worktrees(scan: Scan, context: RepoContext, redactor: Redactor) -> list[Path]:
    """One capped ``git worktree list --porcelain`` snapshot (R4). Returns worktree paths."""
    try:
        output = run_git(context.repo_root, "worktree", "list", "--porcelain")
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="git-worktrees",
                identity="git worktree list",
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return []
    paths: list[Path] = []
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree ") :]))
            if len(paths) > MAX_SOURCE_ENTRIES:
                scan.add_problem(
                    StrictReadError(
                        "cap-exceeded",
                        "git worktree list",
                        [f"git worktree list: more than {MAX_SOURCE_ENTRIES} worktrees"],
                    )
                )
                scan.add_source(
                    Source(
                        kind="git-worktrees",
                        identity="git worktree list",
                        digest="",
                        record_count=0,
                        verdict="cap-exceeded",
                    )
                )
                return []
    digest = sha256_hex(canonical_json(sorted(redactor.present(p) for p in paths)).encode())
    scan.add_source(
        Source(
            kind="git-worktrees",
            identity="git worktree list",
            digest=digest,
            record_count=len(paths),
            verdict="present",
        )
    )
    return paths


def _managed_key(context: RepoContext, path: Path) -> tuple[str, str] | None:
    """(outcome_id, subplot_id) when ``path`` is a canonical managed worktree path (KTD4)."""
    managed_root = context.repo_root / MANAGED_WORKTREES_DIRNAME
    try:
        relative = path.relative_to(managed_root)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) != 2 or parts[1] == SHARED_INSTALL_DIRNAME:
        return None
    if not (safe_component(parts[0]) and safe_component(parts[1])):
        return None
    return parts[0], parts[1]


def _scan_managed_dirs(scan: Scan, context: RepoContext) -> set[tuple[str, str]]:
    managed_root = context.repo_root / MANAGED_WORKTREES_DIRNAME
    found: set[tuple[str, str]] = set()
    if not managed_root.is_dir() or _is_symlink(managed_root):
        return found
    try:
        with os.scandir(managed_root) as outcomes:
            for outcome in outcomes:
                if not outcome.is_dir(follow_symlinks=False) or not safe_component(outcome.name):
                    continue
                with os.scandir(outcome.path) as subplots:
                    for subplot in subplots:
                        if subplot.name == SHARED_INSTALL_DIRNAME:
                            continue
                        if subplot.is_dir(follow_symlinks=False) and safe_component(subplot.name):
                            found.add((outcome.name, subplot.name))
                        if len(found) > MAX_SOURCE_ENTRIES:
                            raise StrictReadError(
                                "cap-exceeded",
                                MANAGED_WORKTREES_DIRNAME,
                                ["managed worktree enumeration beyond entry cap"],
                            )
    except StrictReadError as problem:
        scan.add_problem(problem)
        return set()
    except OSError as exc:
        scan.add_problem(StrictReadError("unsafe-path", MANAGED_WORKTREES_DIRNAME, [str(exc)]))
        return set()
    return found


def collect_outcome_registries(
    scan: Scan, context: RepoContext, redactor: Redactor
) -> dict[tuple[str, str], dict[str, Any]]:
    """Strictly read every outcome ``worktrees.json`` (R4): closed shape, no healing, no writes."""
    outcomes_dir = context.common_dir / OUTCOMES_DIRNAME
    identity = f"{OUTCOMES_DIRNAME}/*/{WORKTREE_REGISTRY_NAME}"
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    if not outcomes_dir.is_dir() or _is_symlink(outcomes_dir):
        scan.add_source(
            Source(
                kind="worktree-registries",
                identity=identity,
                digest="",
                record_count=0,
                verdict="absent",
            )
        )
        return rows
    try:
        with os.scandir(outcomes_dir) as entries:
            outcome_ids = sorted(
                entry.name
                for entry in entries
                if entry.is_dir(follow_symlinks=False) and safe_component(entry.name)
            )
        if len(outcome_ids) > MAX_SOURCE_ENTRIES:
            raise StrictReadError(
                "cap-exceeded", identity, [f"{identity}: more than {MAX_SOURCE_ENTRIES} outcomes"]
            )
        for outcome_id in outcome_ids:
            registry_path = outcomes_dir / outcome_id / WORKTREE_REGISTRY_NAME
            if not registry_path.exists() and not _is_symlink(registry_path):
                continue
            presented = redactor.present(registry_path)
            data = read_bounded_file(registry_path, cap=MAX_STATE_BYTES, presented=presented)
            document = parse_strict_json(data, what=presented)
            if not isinstance(document, dict) or set(document) != {"worktrees"}:
                raise StrictReadError(
                    "schema-skew", presented, [f"{presented}: not closed to one 'worktrees' key"]
                )
            worktrees = document["worktrees"]
            if not isinstance(worktrees, dict):
                raise StrictReadError(
                    "schema-skew", presented, [f"{presented}: 'worktrees' is not an object"]
                )
            for subplot_id, entry in worktrees.items():
                if not safe_component(subplot_id):
                    raise StrictReadError(
                        "traversal-identity",
                        presented,
                        [f"{presented}: subplot id fails the safe-component charset"],
                    )
                if not isinstance(entry, dict):
                    raise StrictReadError(
                        "schema-skew", presented, [f"{presented}: entry is not an object"]
                    )
                keys = set(entry)
                if not keys >= _REGISTRY_ENTRY_REQUIRED or not (
                    keys <= _REGISTRY_ENTRY_REQUIRED | _REGISTRY_ENTRY_OPTIONAL
                ):
                    raise StrictReadError(
                        "schema-skew",
                        f"{presented}:{subplot_id}",
                        [f"{presented}: entry fields diverge from the registry contract"],
                    )
                rows[(outcome_id, subplot_id)] = entry
                if len(rows) > MAX_SOURCE_ENTRIES:
                    raise StrictReadError(
                        "cap-exceeded", identity, [f"{identity}: row count beyond entry cap"]
                    )
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="worktree-registries",
                identity=identity,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return {}
    digest_rows = {f"{oid}/{sid}": row for (oid, sid), row in rows.items()}
    scan.add_source(
        Source(
            kind="worktree-registries",
            identity=identity,
            digest=sha256_hex(canonical_json(digest_rows).encode("utf-8")),
            record_count=len(rows),
            verdict="present",
        )
    )
    return rows


def _teardown_view(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Correlate #358 teardown facts: action_key -> {resource_id, disposition, team_run_id}."""
    attempts: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("kind") != "teardown":
            continue
        event = record.get("event")
        if event == "resource-attempt":
            key = str(record.get("action_key"))
            attempts.setdefault(key, {}).update(
                {
                    "resource_id": str(record.get("resource_id")),
                    "action": str(record.get("action")),
                    "team_run_id": str(record.get("team_run_id")),
                }
            )
        elif event == "resource-result":
            key = str(record.get("action_key"))
            attempts.setdefault(key, {})["disposition"] = str(record.get("disposition"))
    return attempts


def reconcile_worktrees(
    scan: Scan,
    context: RepoContext,
    *,
    porcelain_paths: list[Path],
    registry_rows: dict[tuple[str, str], dict[str, Any]],
    broker_registry: dict[str, Any] | None,
    run_fact_records: list[dict[str, Any]],
) -> None:
    """R4: both drift directions plus terminal-resource-open, from independent observations."""
    exclusions = {context.repo_root, Path.cwd()}
    observed: dict[tuple[str, str], list[str]] = {}
    for path in porcelain_paths:
        if path in exclusions:
            continue
        key = _managed_key(context, path)
        if key is not None:
            observed.setdefault(key, []).append("git-worktree-porcelain")
    for key in _scan_managed_dirs(scan, context):
        managed_path = context.repo_root / MANAGED_WORKTREES_DIRNAME / key[0] / key[1]
        if managed_path in exclusions or managed_path == Path.cwd():
            continue
        observed.setdefault(key, []).append("managed-filesystem")

    leases: dict[str, dict[str, Any]] = {}
    closed_owners: dict[str, Any] = {}
    fences: dict[str, dict[str, Any]] = {}
    if isinstance(broker_registry, dict):
        raw_leases = broker_registry.get("leases")
        if isinstance(raw_leases, dict):
            leases = {k: v for k, v in raw_leases.items() if isinstance(v, dict)}
        raw_closed = broker_registry.get("closed_owner_admissions")
        if isinstance(raw_closed, dict):
            closed_owners = raw_closed
        raw_fences = broker_registry.get("resource_fences")
        if isinstance(raw_fences, dict):
            fences = {k: v for k, v in raw_fences.items() if isinstance(v, dict)}

    worktree_leases: dict[tuple[str, str], str] = {}
    for lease_id, lease in leases.items():
        ref = lease.get("resource_ref")
        if (
            lease.get("pool") == "worktree"
            and isinstance(ref, dict)
            and str(ref.get("repo_root")) == str(context.repo_root)
        ):
            worktree_leases[(str(ref.get("outcome_id")), str(ref.get("subplot_id")))] = lease_id

    for key in sorted(observed):
        if key not in registry_rows:
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="stale-worktree",
                    subject_id=f"{key[0]}/{key[1]}",
                    evidence_refs=tuple(
                        sorted(set(observed[key])) + ["worktree-registries: no row"]
                    ),
                    owner_command="/outcome status",
                )
            )

    for key, row in sorted(registry_rows.items()):
        subject = f"{key[0]}/{key[1]}"
        canonical_path = context.repo_root / MANAGED_WORKTREES_DIRNAME / key[0] / key[1]
        if key not in observed and not Path(str(row.get("path"))).is_dir():
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="dangling-registry",
                    subject_id=subject,
                    evidence_refs=(
                        "git-worktree-porcelain: absent",
                        "managed-filesystem: absent",
                        "worktree-registries: row present",
                    ),
                    owner_command="/outcome status",
                )
            )
            continue
        if str(row.get("path")) != str(canonical_path):
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="ownership-drift",
                    subject_id=subject,
                    evidence_refs=(
                        "worktree-registries: path diverges from the canonical managed path",
                        f"expected: {MANAGED_WORKTREES_DIRNAME}/{key[0]}/{key[1]}",
                    ),
                    owner_command="/outcome status",
                )
            )
        row_lease = row.get("lease")
        if isinstance(row_lease, dict) and leases:
            lease_id = str(row_lease.get("lease_id"))
            broker_lease = leases.get(lease_id)
            row_token = row_lease.get("token")
            row_seq = row_token.get("fencing_sequence") if isinstance(row_token, dict) else None
            if broker_lease is None:
                scan.add_finding(
                    Finding(
                        disease="leaked-resource",
                        classification="ownership-drift",
                        subject_id=subject,
                        evidence_refs=(
                            "lease-registry: lease id absent from the broker",
                            f"worktree-registries: lease {lease_id} recorded",
                        ),
                        owner_command="lease-broker inspect",
                    )
                )
            elif broker_lease.get("fencing_sequence") != row_seq:
                scan.add_finding(
                    Finding(
                        disease="leaked-resource",
                        classification="ownership-drift",
                        subject_id=subject,
                        evidence_refs=(
                            "lease-registry: fencing sequence diverges",
                            "worktree-registries: stale lease generation recorded",
                        ),
                        owner_command="lease-broker inspect",
                    )
                )

    for key, lease_id in sorted(worktree_leases.items()):
        if key not in registry_rows and key not in observed:
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="ownership-drift",
                    subject_id=f"{key[0]}/{key[1]}",
                    evidence_refs=(
                        f"lease-registry: live worktree lease {lease_id}",
                        "worktree-registries: no row",
                        "managed-filesystem: absent",
                    ),
                    owner_command="lease-broker inspect",
                )
            )

    for action_key, view in sorted(_teardown_view(run_fact_records).items()):
        disposition = view.get("disposition")
        resource_id = str(view.get("resource_id"))
        team_run = str(view.get("team_run_id"))
        if disposition == "retained":
            scan.warnings.append(
                f"teardown retained resource {resource_id} (team run {team_run})"
                " remains open by design"
            )
            continue
        if disposition in ("released", "already-absent") and resource_id in leases:
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="terminal-resource-open",
                    subject_id=resource_id,
                    evidence_refs=(
                        f"run-facts: teardown {disposition} at action {action_key[:16]}",
                        "lease-registry: lease still present",
                    ),
                    owner_command="B8 status/recover",
                )
            )

    for owner_id in sorted(closed_owners):
        live = sorted(
            lease_id for lease_id, lease in leases.items() if str(lease.get("owner_id")) == owner_id
        )
        if live:
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="terminal-resource-open",
                    subject_id=owner_id,
                    evidence_refs=(
                        "lease-registry: closed owner admission recorded",
                        f"lease-registry: live leases remain ({', '.join(live)})",
                    ),
                    owner_command="B8 status/recover",
                )
            )

    for digest, fence in sorted(fences.items()):
        if fence.get("close_receipt") is not None and str(fence.get("lease_id")) in leases:
            scan.add_finding(
                Finding(
                    disease="leaked-resource",
                    classification="terminal-resource-open",
                    subject_id=str(fence.get("lease_id")),
                    evidence_refs=(
                        f"lease-registry: resource head {digest[:16]} carries a close receipt",
                        "lease-registry: lease still present",
                    ),
                    owner_command="lease-broker inspect",
                )
            )


# --------------------------------------------------------------- U3: dispatch + delegation

OUTCOME_LEDGER_NAME = "ledger.jsonl"
SETTLEMENT_SITES = frozenset({"outcome", "team-execution", "workflow"})
_RECEIPT_RUNNER_FIELDS = {
    "cli": frozenset({"pid", "argv", "exit_code"}),
    "http": frozenset({"url", "status_code", "model"}),
}


def _read_jsonl_tolerant_tail(
    path: Path, *, cap: int, presented: str, scan: Scan
) -> list[dict[str, Any]]:
    """Strict JSONL read with the producers' torn-trailing-line crash-artifact tolerance."""
    data = read_bounded_file(path, cap=cap, presented=presented)
    lines = data.split(b"\n")
    torn = b""
    if lines and lines[-1] != b"":
        torn = lines[-1]
        lines = lines[:-1]
    else:
        lines = lines[:-1] if lines else lines
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        record = parse_strict_json(line, what=f"{presented}#{index + 1}")
        if not isinstance(record, dict):
            raise StrictReadError(
                "malformed-json",
                f"{presented}#{index + 1}",
                [f"{presented}: record is not an object"],
            )
        records.append(record)
        if len(records) > MAX_SOURCE_ENTRIES:
            raise StrictReadError(
                "cap-exceeded", presented, [f"{presented}: record count beyond entry cap"]
            )
    if torn:
        try:
            parse_strict_json(torn, what=f"{presented}#torn-tail")
        except StrictReadError:
            scan.warnings.append(f"{presented}: torn trailing line ignored")
        else:
            raise StrictReadError(
                "malformed-json",
                f"{presented}#torn-tail",
                [f"{presented}: complete trailing record missing newline is a torn append"],
            )
    return records


def collect_outcome_dispatch_events(
    scan: Scan, context: RepoContext, redactor: Redactor
) -> dict[tuple[str, str, int], list[str]]:
    """Observed dispatch positions from the Outcome coordinators' replay ledgers (R5).

    A ``phase=commit, kind=dispatch`` record carrying a ``settlement`` handle is an independent
    coordinator observation keyed by exact (dispatch_id, unit_id, attempt).
    """
    outcomes_dir = context.common_dir / OUTCOMES_DIRNAME
    identity = f"{OUTCOMES_DIRNAME}/*/{OUTCOME_LEDGER_NAME}"
    observed: dict[tuple[str, str, int], list[str]] = {}
    if not outcomes_dir.is_dir() or _is_symlink(outcomes_dir):
        scan.add_source(
            Source(
                kind="outcome-dispatch-events",
                identity=identity,
                digest="",
                record_count=0,
                verdict="absent",
            )
        )
        return observed
    count = 0
    digest_parts: list[str] = []
    try:
        with os.scandir(outcomes_dir) as entries:
            outcome_ids = sorted(
                entry.name
                for entry in entries
                if entry.is_dir(follow_symlinks=False) and safe_component(entry.name)
            )
        for outcome_id in outcome_ids:
            ledger_path = outcomes_dir / outcome_id / OUTCOME_LEDGER_NAME
            if not ledger_path.exists() and not _is_symlink(ledger_path):
                continue
            presented = redactor.present(ledger_path)
            records = _read_jsonl_tolerant_tail(
                ledger_path, cap=MAX_LEDGER_BYTES, presented=presented, scan=scan
            )
            digest_parts.append(sha256_hex(canonical_json(records).encode("utf-8")))
            for record in records:
                if record.get("kind") != "dispatch" or record.get("phase") != "commit":
                    continue
                settlement = record.get("settlement")
                if not isinstance(settlement, dict):
                    continue
                dispatch_id = settlement.get("dispatch_id")
                unit_id = settlement.get("unit_id")
                attempt = settlement.get("attempt")
                if (
                    not isinstance(dispatch_id, str)
                    or not isinstance(unit_id, str)
                    or isinstance(attempt, bool)
                    or not isinstance(attempt, int)
                ):
                    raise StrictReadError(
                        "contradictory-identity",
                        f"{presented}:{record.get('key')}",
                        [f"{presented}: dispatch commit settlement handle is malformed"],
                    )
                observed.setdefault((dispatch_id, unit_id, attempt), []).append(
                    f"outcome-ledger: {outcome_id} commit {record.get('key')}"
                )
                count += 1
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.add_source(
            Source(
                kind="outcome-dispatch-events",
                identity=identity,
                digest="",
                record_count=0,
                verdict=problem.classification,
            )
        )
        return {}
    scan.add_source(
        Source(
            kind="outcome-dispatch-events",
            identity=identity,
            digest=sha256_hex(canonical_json(sorted(digest_parts)).encode("utf-8")),
            record_count=count,
            verdict="present",
        )
    )
    return observed


def _parse_outcome_lease_identity(logical_unit_id: str) -> tuple[str, str] | None:
    """(unit_id, dispatch_identity) for the two supported outcome agent-lease vocabularies."""
    if logical_unit_id.startswith("outcome:"):
        parts = logical_unit_id.split(":", 3)
        if len(parts) == 4 and safe_component(parts[1]) and safe_component(parts[2]):
            return parts[2], parts[3]
        return None
    if logical_unit_id.startswith("outcome-dispatch:"):
        parts = logical_unit_id.split(":")
        if len(parts) >= 3 and parts[-1].isdigit():
            return parts[-2], logical_unit_id
        return None
    return None


@dataclass(frozen=True)
class SettlementView:
    manifests: dict[str, dict[str, Any]]
    spawns: dict[tuple[str, str, int], dict[str, Any]]
    settles: dict[tuple[str, str, int], dict[str, Any]]


def settlement_view(scan: Scan, records: list[dict[str, Any]]) -> SettlementView:
    """Index the #351 dispatch-settlement facts from the chain-verified snapshot."""
    manifests: dict[str, dict[str, Any]] = {}
    spawns: dict[tuple[str, str, int], dict[str, Any]] = {}
    settles: dict[tuple[str, str, int], dict[str, Any]] = {}
    for record in records:
        if record.get("kind") != "dispatch-settlement":
            continue
        event = record.get("event")
        dispatch_id = str(record.get("dispatch_id"))
        if event == "manifest":
            site = record.get("site")
            if site not in SETTLEMENT_SITES:
                scan.add_problem(
                    StrictReadError(
                        "unsupported-site",
                        dispatch_id,
                        [f"run-facts: manifest site {site!r} outside the closed vocabulary"],
                    )
                )
                continue
            manifests[dispatch_id] = record
        elif event == "spawn":
            key = (dispatch_id, str(record.get("unit_id")), int(record.get("attempt", 0)))
            if key in spawns:
                scan.add_problem(
                    StrictReadError(
                        "contradictory-identity",
                        f"{key[0]}:{key[1]}:{key[2]}",
                        ["run-facts: duplicate spawn fact for one dispatch identity"],
                    )
                )
                continue
            spawns[key] = record
        elif event in ("settle", "late-delivery"):
            key = (dispatch_id, str(record.get("unit_id")), int(record.get("attempt", 0)))
            if event == "settle" and key not in spawns:
                scan.add_problem(
                    StrictReadError(
                        "contradictory-identity",
                        f"{key[0]}:{key[1]}:{key[2]}",
                        ["run-facts: settlement without a spawn fact"],
                    )
                )
                continue
            settles[key] = record
    return SettlementView(manifests=manifests, spawns=spawns, settles=settles)


def reconcile_dispatch(
    scan: Scan,
    context: RepoContext,
    *,
    run_fact_records: list[dict[str, Any]],
    observed_commits: dict[tuple[str, str, int], list[str]],
    broker_registry: dict[str, Any] | None,
) -> None:
    """R5: unledgered needs an independent observation; one fact never proves a launch (KTD3)."""
    view = settlement_view(scan, run_fact_records)

    observed: dict[tuple[str, str, int], list[str]] = {
        key: list(refs) for key, refs in observed_commits.items()
    }
    unsupported_leases = 0
    if isinstance(broker_registry, dict):
        raw_leases = broker_registry.get("leases")
        if isinstance(raw_leases, dict):
            for lease_id, lease in sorted(raw_leases.items()):
                if not isinstance(lease, dict) or lease.get("pool") != "agent":
                    continue
                ref = lease.get("resource_ref")
                logical = ref.get("logical_unit_id") if isinstance(ref, dict) else None
                if not isinstance(logical, str):
                    continue
                parsed = _parse_outcome_lease_identity(logical)
                if parsed is None:
                    if logical.startswith("outcome"):
                        unsupported_leases += 1
                    continue
                unit_id, dispatch_identity = parsed
                matched = False
                for key in view.spawns:
                    if key[1] == unit_id and (
                        key[0] == dispatch_identity or dispatch_identity.endswith(str(key[2]))
                    ):
                        matched = True
                        observed.setdefault(key, []).append(
                            f"lease-registry: agent lease {lease_id}"
                        )
                        break
                if not matched:
                    scan.add_finding(
                        Finding(
                            disease="unledgered-spawn",
                            classification="lease-without-spawn-fact",
                            subject_id=logical,
                            evidence_refs=(
                                f"lease-registry: live agent lease {lease_id}",
                                "run-facts: verified chain has no matching spawn fact",
                            ),
                            owner_command="/delegation-audit",
                        )
                    )
    if unsupported_leases:
        scan.warnings.append(
            f"lease-registry: {unsupported_leases} outcome-labeled agent lease(s) outside the"
            " supported identity vocabulary (not correlated)"
        )

    for key, refs in sorted(observed.items()):
        if key not in view.spawns:
            scan.add_finding(
                Finding(
                    disease="unledgered-spawn",
                    classification="observed-without-spawn-fact",
                    subject_id=f"{key[0]}:{key[1]}:{key[2]}",
                    evidence_refs=tuple(sorted(set(refs)) + ["run-facts: no manifest/spawn fact"]),
                    owner_command="/delegation-audit",
                )
            )

    for key, spawn in sorted(view.spawns.items()):
        subject = f"{key[0]}:{key[1]}:{key[2]}"
        manifest = view.manifests.get(key[0])
        if manifest is None:
            scan.add_problem(
                StrictReadError(
                    "contradictory-identity",
                    subject,
                    ["run-facts: spawn fact without a dispatch manifest"],
                )
            )
            continue
        declared = {
            str(unit.get("unit_id")): str(unit.get("idempotency_key"))
            for unit in manifest.get("units", [])
            if isinstance(unit, dict)
        }
        if key[1] not in declared or declared[key[1]] != str(spawn.get("idempotency_key")):
            scan.add_problem(
                StrictReadError(
                    "contradictory-identity",
                    subject,
                    ["run-facts: spawn identity disagrees with its manifest"],
                )
            )
            continue
        settled = key in view.settles
        was_observed = key in observed
        if not was_observed and not settled:
            scan.add_finding(
                Finding(
                    disease="unledgered-spawn",
                    classification="phantom-spawn-fact",
                    subject_id=subject,
                    evidence_refs=(
                        "run-facts: spawn fact recorded",
                        "no independent observation (no commit event, lease, or audit run)",
                    ),
                    owner_command="/delegation-audit",
                )
            )
        elif was_observed and not settled:
            scan.add_finding(
                Finding(
                    disease="unledgered-spawn",
                    classification="unsettled-spawn",
                    subject_id=subject,
                    evidence_refs=(
                        "run-facts: spawn fact without a terminal settlement",
                        *sorted(set(observed.get(key, []))),
                    ),
                    owner_command="/delegation-audit",
                )
            )


def _read_audit_artifact(
    audit_root: Path, run_id: str, name: str, redactor: Redactor
) -> dict[str, Any] | None:
    """Strict bounded read of one audit artifact; absent is None, malformed raises (KTD5)."""
    path = audit_root / AUDIT_RUNS_DIRNAME / run_id / name
    if not path.exists() and not _is_symlink(path):
        return None
    presented = redactor.present(path)
    data = read_bounded_file(path, cap=MAX_ARTIFACT_BYTES, presented=presented)
    document = parse_strict_json(data, what=presented)
    if not isinstance(document, dict):
        raise StrictReadError(
            "malformed-json", presented, [f"{presented}: artifact is not an object"]
        )
    return document


def _receipt_subset_valid(receipt: dict[str, Any]) -> bool:
    """The doctor's independent minimal ``bridge_receipt.v1`` subset (conformance-tested)."""
    if receipt.get("schema") != "bridge_receipt.v1":
        return False
    if not isinstance(receipt.get("engine_id"), str) or not isinstance(receipt.get("variant"), str):
        return False
    transport = receipt.get("transport")
    if transport not in _RECEIPT_RUNNER_FIELDS:
        return False
    if not isinstance(receipt.get("wall_time_s"), (int, float)) or isinstance(
        receipt.get("wall_time_s"), bool
    ):
        return False
    if isinstance(receipt.get("bytes_produced"), bool) or not isinstance(
        receipt.get("bytes_produced"), int
    ):
        return False
    runner = receipt.get("runner")
    if not isinstance(runner, dict):
        return False
    return _RECEIPT_RUNNER_FIELDS[transport] <= set(runner)


def reconcile_delegation(
    scan: Scan,
    redactor: Redactor,
    audit_root: Path,
    run_ids: list[str],
) -> None:
    """R6: a claimed real execution needs a durable, schema-valid receipt; corruption is never
    absence. Admitted fallback is not receiptless; a valid receipt with no claim is a warning."""
    for run_id in run_ids:
        subject = f"audit-store:runs/{run_id}"
        try:
            manifest = _read_audit_artifact(audit_root, run_id, "manifest.json", redactor)
            result = _read_audit_artifact(audit_root, run_id, "result.json", redactor)
            receipt = _read_audit_artifact(audit_root, run_id, "receipt.json", redactor)
        except StrictReadError as problem:
            scan.add_finding(evidence_error("delegation-evidence-error", subject, problem.evidence))
            scan.complete = False
            continue
        disposition = str(manifest.get("disposition")) if manifest else ""
        claimed = disposition == "ran-as-requested" or bool(
            result and result.get("agy_launched") is True
        )
        receipt_valid = receipt is not None and _receipt_subset_valid(receipt)
        if receipt is not None and not receipt_valid:
            scan.add_finding(
                evidence_error(
                    "delegation-evidence-error",
                    subject,
                    [f"{subject}: receipt fails the bridge_receipt.v1 subset"],
                )
            )
            scan.complete = False
            continue
        if claimed and receipt is None:
            scan.add_finding(
                Finding(
                    disease="receiptless-delegation",
                    classification="claimed-without-receipt",
                    subject_id=subject,
                    evidence_refs=(
                        f"{subject}: manifest/result claims real execution"
                        f" (disposition={disposition or 'n/a'})",
                        f"{subject}: no durable receipt.json",
                    ),
                    owner_command="/delegation-audit",
                )
            )
        elif receipt_valid and not claimed:
            scan.warnings.append(f"{subject}: durable receipt present without a claim")


def run_scan(
    repo_root: Path,
    *,
    lease_store: Path | None = None,
    audit_store: Path | None = None,
    show_local_paths: bool = False,
) -> dict[str, Any]:
    """Derive one complete ``fleet_doctor_report.v1`` dict. Pure observation; no writes (R1)."""
    scan = Scan()
    try:
        context = resolve_repo(repo_root)
    except StrictReadError as problem:
        scan.add_problem(problem)
        scan.repo_identity = "<unresolved>"
        return build_report(scan)

    lease_root = lease_store if lease_store is not None else default_lease_store_root()
    audit_root = audit_store if audit_store is not None else default_audit_store_root()
    redactor = Redactor(
        repo_root=context.repo_root,
        labeled_roots=(("lease-store", lease_root), ("audit-store", audit_root)),
        show_local_paths=show_local_paths,
    )
    scan.repo_identity = str(context.repo_root) if show_local_paths else context.repo_root.name
    scan.add_source(
        Source(
            kind="git-repo",
            identity=scan.repo_identity,
            digest=sha256_hex(canonical_json(scan.repo_identity).encode("utf-8")),
            record_count=1,
            verdict="present",
        )
    )

    run_fact_records = collect_run_facts(scan, context, redactor)
    broker_registry = collect_lease_registry(
        scan, redactor, lease_root, explicit=lease_store is not None
    )
    audit_run_ids = collect_audit_store(
        scan, redactor, audit_root, explicit=audit_store is not None
    )
    porcelain_paths = collect_git_worktrees(scan, context, redactor)
    registry_rows = collect_outcome_registries(scan, context, redactor)
    observed_commits = collect_outcome_dispatch_events(scan, context, redactor)
    reconcile_worktrees(
        scan,
        context,
        porcelain_paths=porcelain_paths,
        registry_rows=registry_rows,
        broker_registry=broker_registry,
        run_fact_records=run_fact_records,
    )
    reconcile_dispatch(
        scan,
        context,
        run_fact_records=run_fact_records,
        observed_commits=observed_commits,
        broker_registry=broker_registry,
    )
    reconcile_delegation(scan, redactor, audit_root, audit_run_ids)
    return build_report(scan)


def build_report(scan: Scan) -> dict[str, Any]:
    sources = sorted(scan.sources, key=lambda s: (s.kind, s.identity))
    findings = sorted(
        scan.findings, key=lambda f: (f.disease, f.classification, f.subject_id, f.finding_id)
    )
    by_disease = dict.fromkeys(DISEASES, 0)
    for finding in findings:
        by_disease[finding.disease] += 1
    return {
        "schema": SCHEMA,
        "repo": scan.repo_identity,
        "complete": scan.complete,
        "sources": [source.to_dict() for source in sources],
        "findings": [finding.to_dict() for finding in findings],
        "counts": {
            "sources": len(sources),
            "findings": len(findings),
            "by_disease": by_disease,
            "evidence_errors": by_disease["evidence-error"],
        },
        "warnings": sorted(scan.warnings),
    }


def derive_exit(report: dict[str, Any]) -> int:
    if not report["complete"] or report["counts"]["evidence_errors"] > 0:
        return 2
    return 1 if report["counts"]["findings"] > 0 else 0


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"fleet doctor — {report['schema']}",
        f"repo: {report['repo']}",
        f"complete: {str(report['complete']).lower()}",
        "",
        "sources:",
    ]
    for source in report["sources"]:
        lines.append(
            f"  {source['kind']:16} {source['verdict']:16} records={source['record_count']}"
            f" {source['identity']}"
        )
    lines.append("")
    lines.append("findings:")
    if not report["findings"]:
        lines.append("  none")
    for finding in report["findings"]:
        lines.append(
            f"  [{finding['disease']}] {finding['classification']} {finding['subject_id']}"
        )
        for ref in finding["evidence_refs"]:
            lines.append(f"    evidence: {ref}")
        lines.append(f"    owner: {finding['owner_command']}")
    lines.append("")
    lines.append("warnings:")
    if not report["warnings"]:
        lines.append("  none")
    for warning in report["warnings"]:
        lines.append(f"  {warning}")
    lines.append("")
    counts = report["counts"]
    lines.append(
        f"counts: sources={counts['sources']} findings={counts['findings']}"
        f" evidence_errors={counts['evidence_errors']}"
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fleet-doctor",
        description="Strict read-only cross-source fleet audit (report only; never repairs).",
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--lease-store", default=None)
    parser.add_argument("--audit-store", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--show-local-paths", action="store_true")
    args = parser.parse_args(argv)

    report = run_scan(
        Path(args.repo_root),
        lease_store=Path(args.lease_store) if args.lease_store else None,
        audit_store=Path(args.audit_store) if args.audit_store else None,
        show_local_paths=args.show_local_paths,
    )
    rendered = canonical_json(report) + "\n" if args.format == "json" else render_text(report)
    if len(rendered.encode("utf-8")) > MAX_OUTPUT_BYTES:
        print(
            canonical_json(
                {
                    "schema": SCHEMA,
                    "complete": False,
                    "warnings": ["rendered output beyond cap; report withheld"],
                }
            ),
            file=sys.stderr,
        )
        return 2
    sys.stdout.write(rendered)
    return derive_exit(report)


if __name__ == "__main__":
    raise SystemExit(main())
