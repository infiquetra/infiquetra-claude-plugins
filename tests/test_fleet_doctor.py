"""Fleet doctor (#353) — U1 observation-layer oracles.

Fixtures build stores with the REAL producers (run_ledger) so the doctor's raw parsing is proven
against genuine bytes, then corrupt those bytes directly. The doctor itself never imports a
producer; these tests do — that asymmetry is the point (KTD1).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
FLEET_DOCTOR = SCRIPTS / "fleet_doctor.py"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FD = _load("fleet_doctor")
RL = _load("run_ledger")


# ------------------------------------------------------------------ fixtures


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    return repo


@pytest.fixture
def stores(tmp_path: Path) -> dict[str, Path]:
    lease = tmp_path / "lease-store"
    audit = tmp_path / "audit-store"
    lease.mkdir(mode=0o700)
    audit.mkdir(mode=0o700)
    return {"lease": lease, "audit": audit}


def _scan(repo: Path, stores: dict[str, Path], **kw: Any) -> dict[str, Any]:
    return dict(FD.run_scan(repo, lease_store=stores["lease"], audit_store=stores["audit"], **kw))


def _ledger_path(repo: Path) -> Path:
    path = repo / ".git" / "saga-run-facts" / "run-facts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_facts(repo: Path, count: int = 3) -> Path:
    path = _ledger_path(repo)
    ledger = RL.RunLedger(path=path)
    for index in range(count):
        RL.append_fact(
            ledger,
            RL.build_fact(
                "spend",
                subplot_id=f"sub-{index}",
                at="2026-07-19T00:00:00Z",
                tokens=10,
                tokens_cached=5,
                tokens_fresh=5,
                wall_seconds=1.0,
            ),
        )
    return path


def _source(report: dict[str, Any], kind: str) -> dict[str, Any]:
    matches = [s for s in report["sources"] if s["kind"] == kind]
    assert len(matches) == 1, f"expected one {kind} source, got {matches}"
    return cast("dict[str, Any]", matches[0])


def _tree_snapshot(*roots: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                path = Path(dirpath) / name
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                rows.append((str(path.relative_to(root.parent)), digest))
    return rows


# ------------------------------------------------------------------ no-write + exits


def test_import_and_empty_scan_write_nothing(repo: Path, stores: dict[str, Path]) -> None:
    before = _tree_snapshot(repo, stores["lease"], stores["audit"])
    report = _scan(repo, stores)
    assert report["complete"] is True
    assert _tree_snapshot(repo, stores["lease"], stores["audit"]) == before
    assert not (SCRIPTS / "__pycache__").exists()


def test_cli_scan_writes_nothing_and_exits_zero(repo: Path, stores: dict[str, Path]) -> None:
    before = _tree_snapshot(repo, stores["lease"], stores["audit"])
    result = subprocess.run(
        [
            sys.executable,
            str(FLEET_DOCTOR),
            "--repo-root",
            str(repo),
            "--lease-store",
            str(stores["lease"]),
            "--audit-store",
            str(stores["audit"]),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["schema"] == "fleet_doctor_report.v1"
    assert _tree_snapshot(repo, stores["lease"], stores["audit"]) == before
    assert not (SCRIPTS / "__pycache__").exists()


def test_clean_empty_scan_exit_zero(repo: Path, stores: dict[str, Path]) -> None:
    report = _scan(repo, stores)
    assert report["complete"] is True
    assert report["counts"]["findings"] == 0
    assert FD.derive_exit(report) == 0


def test_absent_optional_sources_are_absent_not_errors(repo: Path, tmp_path: Path) -> None:
    report = FD.run_scan(
        repo,
        lease_store=None,
        audit_store=tmp_path / "never-created-audit",
    )
    # An explicitly configured but missing root is a config error (R3)...
    assert FD.derive_exit(report) == 2
    assert any(f["classification"] == "config-error" for f in report["findings"])


def test_default_roots_absent_scan_clean(repo: Path, monkeypatch: Any, tmp_path: Path) -> None:
    # ...while an absent DEFAULT root is simply an absent optional source.
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(tmp_path / "no-lease-root"))
    monkeypatch.setattr(FD, "default_audit_store_root", lambda: tmp_path / "no-audit-root")
    report = FD.run_scan(repo)
    assert _source(report, "lease-registry")["verdict"] == "absent"
    assert _source(report, "audit-store")["verdict"] == "absent"
    assert FD.derive_exit(report) == 0


def test_missing_repo_is_config_error_exit_two(tmp_path: Path) -> None:
    report = FD.run_scan(tmp_path / "not-a-repo")
    assert report["complete"] is False
    assert FD.derive_exit(report) == 2
    assert any(f["classification"] == "config-error" for f in report["findings"])


def test_disease_finding_maps_to_exit_one() -> None:
    scan = FD.Scan(repo_identity="r")
    scan.add_finding(
        FD.Finding(
            disease="leaked-resource",
            classification="stale-worktree",
            subject_id="outcome/sub",
            evidence_refs=("a", "b"),
            owner_command="/outcome status",
        )
    )
    report = FD.build_report(scan)
    assert FD.derive_exit(report) == 1
    assert "stale-worktree" in FD.render_text(report)


# ------------------------------------------------------------------ run-fact chain


def test_valid_ledger_verifies_chain(repo: Path, stores: dict[str, Path]) -> None:
    _write_facts(repo, count=3)
    report = _scan(repo, stores)
    source = _source(report, "run-facts")
    assert source["verdict"] == "verified-chain"
    assert source["record_count"] == 3
    assert FD.derive_exit(report) == 0


def test_middle_mutated_ledger_breaks_chain(repo: Path, stores: dict[str, Path]) -> None:
    path = _write_facts(repo, count=3)
    lines = path.read_bytes().split(b"\n")
    lines[1] = lines[1].replace(b'"tokens":10', b'"tokens":9999')
    path.write_bytes(b"\n".join(lines))
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "chain-broken"
    assert FD.derive_exit(report) == 2


def test_malformed_middle_line_is_incomplete(repo: Path, stores: dict[str, Path]) -> None:
    path = _write_facts(repo, count=3)
    lines = path.read_bytes().split(b"\n")
    lines[1] = b"{not json"
    path.write_bytes(b"\n".join(lines))
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "malformed-json"
    assert FD.derive_exit(report) == 2


def test_torn_trailing_line_is_tolerated_with_warning(repo: Path, stores: dict[str, Path]) -> None:
    path = _write_facts(repo, count=2)
    with path.open("ab") as handle:
        handle.write(b'{"schema":"run_fact.v1","kind":"spe')
    report = _scan(repo, stores)
    assert report["complete"] is True
    source = _source(report, "run-facts")
    assert source["verdict"] == "verified-chain"
    assert source["record_count"] == 2
    assert any("torn trailing line" in w for w in report["warnings"])
    assert FD.derive_exit(report) == 0


def test_complete_record_without_newline_is_torn_append(
    repo: Path, stores: dict[str, Path]
) -> None:
    path = _write_facts(repo, count=2)
    data = path.read_bytes()
    assert data.endswith(b"\n")
    path.write_bytes(data[:-1])
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "chain-broken"


def test_ledger_beyond_cap_is_incomplete(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    _write_facts(repo, count=2)
    monkeypatch.setattr(FD, "MAX_LEDGER_BYTES", 16)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_record_count_beyond_entry_cap_is_incomplete(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    _write_facts(repo, count=3)
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "cap-exceeded"


def test_source_changed_between_reads_is_incomplete(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    path = _write_facts(repo, count=2)
    real_lstat = os.lstat
    seen: dict[str, int] = {"count": 0}

    def flapping_lstat(target: Any) -> os.stat_result:
        st = real_lstat(target)
        if Path(str(target)) == path:
            seen["count"] += 1
            # Call order for the ledger: symlink probe, pre-stat, post-stat — fake only the
            # post-stat so pre and post genuinely disagree.
            if seen["count"] >= 3:
                fake = list(st)
                fake[8] = st.st_mtime + 5
                return os.stat_result(fake, {"st_mtime_ns": st.st_mtime_ns + 5_000_000})
        return st

    monkeypatch.setattr(FD, "_lstat", flapping_lstat)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "source-changed"
    assert FD.derive_exit(report) == 2


# ------------------------------------------------------------------ lease registry


def _write_registry(stores: dict[str, Path], payload: dict[str, Any]) -> Path:
    path = stores["lease"] / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_lease_registry_present_counts_leases(repo: Path, stores: dict[str, Path]) -> None:
    _write_registry(
        stores,
        {"schema": "fleet_lease_registry.v1", "leases": {"a": {}, "b": {}}},
    )
    report = _scan(repo, stores)
    source = _source(report, "lease-registry")
    assert source["verdict"] == "present"
    assert source["record_count"] == 2


def test_lease_registry_schema_skew_is_incomplete(repo: Path, stores: dict[str, Path]) -> None:
    _write_registry(stores, {"schema": "fleet_lease_registry.v99"})
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "lease-registry")["verdict"] == "schema-skew"


def test_duplicate_json_key_is_malformed(repo: Path, stores: dict[str, Path]) -> None:
    path = stores["lease"] / "registry.json"
    path.write_text('{"schema": "fleet_lease_registry.v1", "schema": "x"}', encoding="utf-8")
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "lease-registry")["verdict"] == "malformed-json"


def test_registry_directory_is_nonregular(repo: Path, stores: dict[str, Path]) -> None:
    (stores["lease"] / "registry.json").mkdir()
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "lease-registry")["verdict"] == "nonregular-file"


def test_registry_beyond_cap_is_incomplete(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    _write_registry(stores, {"schema": "fleet_lease_registry.v1", "leases": {}})
    monkeypatch.setattr(FD, "MAX_STATE_BYTES", 4)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "lease-registry")["verdict"] == "cap-exceeded"


# ------------------------------------------------------------------ unsafe roots + audit store


def test_symlink_store_root_is_unsafe(repo: Path, tmp_path: Path) -> None:
    real = tmp_path / "real-audit"
    real.mkdir(mode=0o700)
    link = tmp_path / "link-audit"
    link.symlink_to(real)
    lease = tmp_path / "lease"
    lease.mkdir(mode=0o700)
    report = FD.run_scan(repo, lease_store=lease, audit_store=link)
    assert report["complete"] is False
    assert _source(report, "audit-store")["verdict"] == "unsafe-path"
    assert FD.derive_exit(report) == 2


def test_audit_runs_enumerated_and_digested(repo: Path, stores: dict[str, Path]) -> None:
    runs = stores["audit"] / "runs"
    runs.mkdir(mode=0o700)
    for run_id in ("run-b", "run-a"):
        (runs / run_id).mkdir(mode=0o700)
    report = _scan(repo, stores)
    source = _source(report, "audit-store")
    assert source["verdict"] == "present"
    assert source["record_count"] == 2
    again = _scan(repo, stores)
    assert _source(again, "audit-store")["digest"] == source["digest"]


def test_unsafe_run_id_is_traversal_identity(repo: Path, stores: dict[str, Path]) -> None:
    runs = stores["audit"] / "runs"
    runs.mkdir(mode=0o700)
    (runs / "ok-run").mkdir(mode=0o700)
    (runs / "bad run id").mkdir(mode=0o700)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "audit-store")["verdict"] == "traversal-identity"


def test_run_entry_file_is_nonregular(repo: Path, stores: dict[str, Path]) -> None:
    runs = stores["audit"] / "runs"
    runs.mkdir(mode=0o700)
    (runs / "stray-file").write_text("x", encoding="utf-8")
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "audit-store")["verdict"] == "nonregular-file"


# ------------------------------------------------------------------ determinism + redaction


def test_repeated_scan_equality(repo: Path, stores: dict[str, Path]) -> None:
    _write_facts(repo, count=2)
    runs = stores["audit"] / "runs"
    runs.mkdir(mode=0o700)
    (runs / "run-1").mkdir(mode=0o700)
    first = FD.canonical_json(_scan(repo, stores))
    second = FD.canonical_json(_scan(repo, stores))
    assert first == second


def test_default_output_redacts_machine_local_paths(repo: Path, stores: dict[str, Path]) -> None:
    _write_facts(repo, count=1)
    report = _scan(repo, stores)
    rendered = FD.canonical_json(report)
    assert str(stores["audit"]) not in rendered
    assert str(stores["lease"]) not in rendered
    assert "audit-store:runs" in rendered
    assert "lease-store:registry.json" in rendered
    # Repo-owned paths stay repo-relative, never absolute.
    assert str(repo) not in rendered


def test_show_local_paths_opt_in(repo: Path, stores: dict[str, Path]) -> None:
    report = _scan(repo, stores, show_local_paths=True)
    rendered = FD.canonical_json(report)
    assert str(stores["audit"]) in rendered


def test_finding_identity_is_stable_digest() -> None:
    finding = FD.Finding(
        disease="unledgered-spawn",
        classification="observed-without-fact",
        subject_id="dispatch:unit:1",
        evidence_refs=("x",),
        owner_command="/delegation-audit",
    )
    expected = hashlib.sha256(
        FD.canonical_json(
            {
                "disease": "unledgered-spawn",
                "classification": "observed-without-fact",
                "subject_id": "dispatch:unit:1",
            }
        ).encode("utf-8")
    ).hexdigest()
    assert finding.finding_id == expected


def test_finding_cap_marks_incomplete(monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "MAX_FINDINGS", 1)
    scan = FD.Scan(repo_identity="r")
    for index in range(3):
        scan.add_finding(
            FD.Finding(
                disease="leaked-resource",
                classification="stale-worktree",
                subject_id=f"s{index}",
                evidence_refs=(),
                owner_command="/outcome status",
            )
        )
    report = FD.build_report(scan)
    assert report["complete"] is False
    assert report["counts"]["findings"] == 1
    assert FD.derive_exit(report) == 2


def test_text_and_json_render_same_findings(repo: Path, stores: dict[str, Path]) -> None:
    _write_facts(repo, count=1)
    report = _scan(repo, stores)
    text = FD.render_text(report)
    for source in report["sources"]:
        assert source["kind"] in text
    assert "counts:" in text


def test_cli_unknown_option_exits_two(repo: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(FLEET_DOCTOR), "--fix"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_default_lease_root_resolution(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(tmp_path / "override"))
    assert FD.default_lease_store_root() == tmp_path / "override"
    monkeypatch.delenv("INFIQUETRA_FLEET_STATE_DIR")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert FD.default_lease_store_root() == tmp_path / "xdg" / "infiquetra" / "fleet-leases"
