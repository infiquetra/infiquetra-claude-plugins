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

    collect_run_facts(scan, context, redactor)
    collect_lease_registry(scan, redactor, lease_root, explicit=lease_store is not None)
    collect_audit_store(scan, redactor, audit_root, explicit=audit_store is not None)
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
