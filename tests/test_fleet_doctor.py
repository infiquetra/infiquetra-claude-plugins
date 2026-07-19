"""Fleet doctor (#353) — U1 observation-layer oracles.

Fixtures build stores with the REAL producers (run_ledger) so the doctor's raw parsing is proven
against genuine bytes, then corrupt those bytes directly. The doctor itself never imports a
producer; these tests do — that asymmetry is the point (KTD1).
"""

from __future__ import annotations

import errno
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
    assert source["verdict"] == "verified-prefix"
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
    assert source["verdict"] == "verified-prefix"
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
            # Call order for the ledger: pre-stat then post-stat (the absent/symlink guard
            # short-circuits for an existing regular file) — fake only the post-stat so pre
            # and post genuinely disagree.
            if seen["count"] >= 2:
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


# ------------------------------------------------------------------ U2: worktree reconciliation


def _managed_worktree(repo: Path, oid: str, sid: str) -> Path:
    path = repo / ".saga-worktrees" / oid / sid
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "commit", "--allow-empty", "-q", "-m", "seed")
    _git(repo, "worktree", "add", "-q", str(path), "HEAD")
    return path


def _registry_row(repo: Path, oid: str, sid: str, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(repo / ".saga-worktrees" / oid / sid),
        "branch": f"work/{sid}",
        "owner": "owner-a",
        "shared_install_ref": "",
        "at": "2026-07-19T00:00:00Z",
        "repo_root": str(repo),
        "outcome_id": oid,
    }
    row.update(over)
    return row


def _write_worktree_registry(repo: Path, oid: str, rows: dict[str, dict[str, Any]]) -> None:
    reg_dir = repo / ".git" / "saga-outcomes" / oid
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / "worktrees.json").write_text(json.dumps({"worktrees": rows}), encoding="utf-8")


def _broker(stores: dict[str, Path], **over: Any) -> None:
    payload: dict[str, Any] = {
        "schema": "fleet_lease_registry.v1",
        "leases": {},
        "closed_owner_admissions": {},
        "resource_fences": {},
    }
    payload.update(over)
    (stores["lease"] / "registry.json").write_text(json.dumps(payload), encoding="utf-8")


def _worktree_lease(repo: Path, oid: str, sid: str, *, seq: int = 7) -> dict[str, Any]:
    return {
        "pool": "worktree",
        "owner_id": "owner-a",
        "fencing_sequence": seq,
        "resource_ref": {"repo_root": str(repo), "outcome_id": oid, "subplot_id": sid},
    }


def _find(report: dict[str, Any], classification: str) -> list[dict[str, Any]]:
    return [f for f in report["findings"] if f["classification"] == classification]


def test_clean_registered_managed_worktree(repo: Path, stores: dict[str, Path]) -> None:
    _managed_worktree(repo, "out-a", "sub-1")
    _write_worktree_registry(repo, "out-a", {"sub-1": _registry_row(repo, "out-a", "sub-1")})
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert FD.derive_exit(report) == 0
    assert _source(report, "worktree-registries")["record_count"] == 1


def test_stale_worktree_both_git_and_filesystem(repo: Path, stores: dict[str, Path]) -> None:
    _managed_worktree(repo, "out-a", "sub-1")
    report = _scan(repo, stores)
    stale = _find(report, "stale-worktree")
    assert len(stale) == 1
    assert stale[0]["subject_id"] == "out-a/sub-1"
    assert stale[0]["disease"] == "leaked-resource"
    assert len(stale[0]["evidence_refs"]) >= 2
    assert FD.derive_exit(report) == 1


def test_stale_filesystem_only_directory(repo: Path, stores: dict[str, Path]) -> None:
    leftover = repo / ".saga-worktrees" / "out-a" / "sub-9"
    leftover.mkdir(parents=True)
    report = _scan(repo, stores)
    assert [f["subject_id"] for f in _find(report, "stale-worktree")] == ["out-a/sub-9"]


def test_dangling_registry_row(repo: Path, stores: dict[str, Path]) -> None:
    _write_worktree_registry(repo, "out-a", {"sub-1": _registry_row(repo, "out-a", "sub-1")})
    report = _scan(repo, stores)
    dangling = _find(report, "dangling-registry")
    assert len(dangling) == 1
    assert dangling[0]["subject_id"] == "out-a/sub-1"
    assert FD.derive_exit(report) == 1


def test_registry_path_mismatch_is_ownership_drift(repo: Path, stores: dict[str, Path]) -> None:
    _managed_worktree(repo, "out-a", "sub-1")
    row = _registry_row(repo, "out-a", "sub-1", path=str(repo / "elsewhere"))
    _write_worktree_registry(repo, "out-a", {"sub-1": row})
    report = _scan(repo, stores)
    assert any(
        "canonical managed path" in ref
        for f in _find(report, "ownership-drift")
        for ref in f["evidence_refs"]
    )


def test_generation_drift_against_broker(repo: Path, stores: dict[str, Path]) -> None:
    _managed_worktree(repo, "out-a", "sub-1")
    row = _registry_row(repo, "out-a", "sub-1")
    row["lease"] = {
        "lease_id": "L1",
        "token": {"broker_epoch": "e", "fencing_sequence": 3},
        "root_sha256": "r",
    }
    _write_worktree_registry(repo, "out-a", {"sub-1": row})
    _broker(stores, leases={"L1": _worktree_lease(repo, "out-a", "sub-1", seq=9)})
    report = _scan(repo, stores)
    drift = _find(report, "ownership-drift")
    assert any("fencing sequence diverges" in ref for f in drift for ref in f["evidence_refs"])


def test_broker_only_worktree_lease_is_drift(repo: Path, stores: dict[str, Path]) -> None:
    _broker(stores, leases={"L2": _worktree_lease(repo, "out-b", "sub-2")})
    report = _scan(repo, stores)
    drift = _find(report, "ownership-drift")
    assert len(drift) == 1
    assert drift[0]["subject_id"] == "out-b/sub-2"
    assert len(drift[0]["evidence_refs"]) >= 2


def test_teardown_released_but_lease_live_is_terminal_open(
    repo: Path, stores: dict[str, Path]
) -> None:
    path = _ledger_path(repo)
    ledger = RL.RunLedger(path=path)
    RL.append_fact(
        ledger,
        RL.build_fact(
            "teardown",
            subplot_id="team",
            at="t",
            event="resource-attempt",
            action_key="k1",
            resource_id="L3",
            resource_kind="provisional-lease",
            generation="e:5",
            action="lease-release",
            team_run_id="run-1",
        ),
    )
    RL.append_fact(
        ledger,
        RL.build_fact(
            "teardown",
            subplot_id="team",
            at="t",
            event="resource-result",
            action_key="k1",
            disposition="released",
            evidence_refs=[],
            team_run_id="run-1",
        ),
    )
    _broker(stores, leases={"L3": {"pool": "agent", "owner_id": "o", "resource_ref": {}}})
    report = _scan(repo, stores)
    open_findings = _find(report, "terminal-resource-open")
    assert len(open_findings) == 1
    assert open_findings[0]["subject_id"] == "L3"
    assert FD.derive_exit(report) == 1


def test_teardown_retained_is_warning_not_finding(repo: Path, stores: dict[str, Path]) -> None:
    path = _ledger_path(repo)
    ledger = RL.RunLedger(path=path)
    RL.append_fact(
        ledger,
        RL.build_fact(
            "teardown",
            subplot_id="team",
            at="t",
            event="resource-attempt",
            action_key="k2",
            resource_id="L4",
            resource_kind="outcome-worktree",
            generation="e:6",
            action="worktree-sweep",
            team_run_id="run-2",
        ),
    )
    RL.append_fact(
        ledger,
        RL.build_fact(
            "teardown",
            subplot_id="team",
            at="t",
            event="resource-result",
            action_key="k2",
            disposition="retained",
            evidence_refs=[],
            team_run_id="run-2",
        ),
    )
    _broker(stores, leases={"L4": {"pool": "agent", "owner_id": "o", "resource_ref": {}}})
    report = _scan(repo, stores)
    assert _find(report, "terminal-resource-open") == []
    assert any("retained resource L4" in w for w in report["warnings"])
    assert FD.derive_exit(report) == 0


def test_closed_owner_with_live_lease_is_terminal_open(repo: Path, stores: dict[str, Path]) -> None:
    _broker(
        stores,
        leases={"L5": {"pool": "agent", "owner_id": "owner-x", "resource_ref": {}}},
        closed_owner_admissions={
            "owner-x": {"closed_at": "t", "boot_id": "b", "close_generation": 4}
        },
    )
    report = _scan(repo, stores)
    open_findings = _find(report, "terminal-resource-open")
    assert len(open_findings) == 1
    assert open_findings[0]["subject_id"] == "owner-x"


def test_closed_head_with_live_lease_is_terminal_open(repo: Path, stores: dict[str, Path]) -> None:
    _broker(
        stores,
        leases={"L6": {"pool": "agent", "owner_id": "o", "resource_ref": {}}},
        resource_fences={
            "d" * 64: {
                "resource_ref": {},
                "broker_epoch": "e",
                "fencing_sequence": 8,
                "lease_id": "L6",
                "close_receipt": {"schema": "settlement_close.v1"},
            }
        },
    )
    report = _scan(repo, stores)
    assert [f["subject_id"] for f in _find(report, "terminal-resource-open")] == ["L6"]


def test_primary_and_unmanaged_worktrees_are_excluded(
    repo: Path, stores: dict[str, Path], tmp_path: Path
) -> None:
    _git(repo, "commit", "--allow-empty", "-q", "-m", "seed")
    unmanaged = tmp_path / "unmanaged-wt"
    _git(repo, "worktree", "add", "-q", str(unmanaged), "HEAD")
    shared = repo / ".saga-worktrees" / "out-a" / "_shared-install"
    shared.mkdir(parents=True)
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert FD.derive_exit(report) == 0


def test_malformed_worktree_registry_is_incomplete(repo: Path, stores: dict[str, Path]) -> None:
    reg_dir = repo / ".git" / "saga-outcomes" / "out-a"
    reg_dir.mkdir(parents=True)
    (reg_dir / "worktrees.json").write_text('{"worktrees": {"sub-1": {"path": "x"}}}')
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "worktree-registries")["verdict"] == "schema-skew"
    assert FD.derive_exit(report) == 2


# ------------------------------------------------------------------ U3: dispatch + delegation


def _fact_ledger(repo: Path) -> Any:
    return RL.RunLedger(path=_ledger_path(repo))


def _manifest_fact(
    ledger: Any, dispatch_id: str, units: list[str], *, site: str = "outcome"
) -> None:
    RL.append_fact(
        ledger,
        RL.build_fact(
            "dispatch-settlement",
            subplot_id="coord",
            at="t",
            event="manifest",
            dispatch_id=dispatch_id,
            site=site,
            units=[
                {"unit_id": u, "idempotency_key": f"key-{u}", "deliverables": []} for u in units
            ],
            casualty_threshold_percent=50,
            max_attempts=2,
        ),
    )


def _spawn_fact(
    ledger: Any, dispatch_id: str, unit: str, attempt: int = 1, *, key: str | None = None
) -> None:
    RL.append_fact(
        ledger,
        RL.build_fact(
            "dispatch-settlement",
            subplot_id="coord",
            at="t",
            event="spawn",
            dispatch_id=dispatch_id,
            unit_id=unit,
            attempt=attempt,
            idempotency_key=key if key is not None else f"key-{unit}",
        ),
    )


def _settle_fact(ledger: Any, dispatch_id: str, unit: str, attempt: int = 1) -> None:
    RL.append_fact(
        ledger,
        RL.build_fact(
            "dispatch-settlement",
            subplot_id="coord",
            at="t",
            event="settle",
            dispatch_id=dispatch_id,
            unit_id=unit,
            attempt=attempt,
            classification="delivered",
            reason="done",
            evidence_ref="e",
            evidence_sha256="f" * 64,
        ),
    )


def _outcome_commit(repo: Path, oid: str, dispatch_id: str, unit: str, attempt: int = 1) -> None:
    ledger_dir = repo / ".git" / "saga-outcomes" / oid
    ledger_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "phase": "commit",
        "kind": "dispatch",
        "key": f"dispatch:{unit}:{attempt}",
        "subplot_id": unit,
        "settlement": {"dispatch_id": dispatch_id, "unit_id": unit, "attempt": attempt},
    }
    with (ledger_dir / "ledger.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _valid_receipt() -> dict[str, Any]:
    return {
        "schema": "bridge_receipt.v1",
        "engine_id": "codex",
        "variant": "default",
        "transport": "cli",
        "wall_time_s": 1.5,
        "bytes_produced": 42,
        "runner": {"pid": 123, "argv": ["codex", "run"], "exit_code": 0},
    }


def _audit_run(
    stores: dict[str, Path],
    run_id: str,
    *,
    manifest: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
    raw_receipt: str | None = None,
) -> None:
    run_dir = stores["audit"] / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if result is not None:
        (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    if receipt is not None:
        (run_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    if raw_receipt is not None:
        (run_dir / "receipt.json").write_text(raw_receipt, encoding="utf-8")


def test_exact_accounted_spawn_is_clean(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d1", ["u1"])
    _spawn_fact(ledger, "d1", "u1")
    _settle_fact(ledger, "d1", "u1")
    _outcome_commit(repo, "out-a", "d1", "u1")
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert FD.derive_exit(report) == 0


def test_observed_commit_without_spawn_fact(repo: Path, stores: dict[str, Path]) -> None:
    _outcome_commit(repo, "out-a", "d-ghost", "u9")
    report = _scan(repo, stores)
    found = _find(report, "observed-without-spawn-fact")
    assert len(found) == 1
    assert found[0]["disease"] == "unledgered-spawn"
    assert found[0]["subject_id"] == "d-ghost:u9:1"
    assert len(found[0]["evidence_refs"]) >= 2
    assert FD.derive_exit(report) == 1


def test_phantom_spawn_fact_without_observation(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d2", ["u2"])
    _spawn_fact(ledger, "d2", "u2")
    report = _scan(repo, stores)
    assert [f["subject_id"] for f in _find(report, "phantom-spawn-fact")] == ["d2:u2:1"]
    assert FD.derive_exit(report) == 1


def test_unsettled_spawn_with_observation(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d3", ["u3"])
    _spawn_fact(ledger, "d3", "u3")
    _outcome_commit(repo, "out-a", "d3", "u3")
    report = _scan(repo, stores)
    assert [f["subject_id"] for f in _find(report, "unsettled-spawn")] == ["d3:u3:1"]


def test_settle_without_spawn_is_contradictory(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d4", ["u4"])
    _settle_fact(ledger, "d4", "u4")
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _find(report, "contradictory-identity")
    assert FD.derive_exit(report) == 2


def test_duplicate_spawn_fact_is_contradictory(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d5", ["u5"])
    _spawn_fact(ledger, "d5", "u5")
    _spawn_fact(ledger, "d5", "u5")
    report = _scan(repo, stores)
    assert _find(report, "contradictory-identity")
    assert FD.derive_exit(report) == 2


def test_spawn_key_mismatch_is_contradictory(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d6", ["u6"])
    _spawn_fact(ledger, "d6", "u6", key="wrong-key")
    report = _scan(repo, stores)
    assert _find(report, "contradictory-identity")


def test_unsupported_manifest_site(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d7", ["u7"], site="rogue-site")
    report = _scan(repo, stores)
    assert _find(report, "unsupported-site")
    assert FD.derive_exit(report) == 2


def test_outcome_lease_without_spawn_fact(repo: Path, stores: dict[str, Path]) -> None:
    _broker(
        stores,
        leases={
            "LA": {
                "pool": "agent",
                "owner_id": "o",
                "resource_ref": {"logical_unit_id": "outcome:out-a:sub-1:disp-x"},
            }
        },
    )
    report = _scan(repo, stores)
    found = _find(report, "lease-without-spawn-fact")
    assert len(found) == 1
    assert found[0]["disease"] == "unledgered-spawn"
    assert FD.derive_exit(report) == 1


def test_unsupported_outcome_lease_identity_is_warning(repo: Path, stores: dict[str, Path]) -> None:
    _broker(
        stores,
        leases={
            "LB": {
                "pool": "agent",
                "owner_id": "o",
                "resource_ref": {"logical_unit_id": "outcome:bad id:x:y"},
            },
            "LC": {
                "pool": "agent",
                "owner_id": "o",
                "resource_ref": {"logical_unit_id": "team-exec:whatever"},
            },
        },
    )
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert any("outside the supported identity vocabulary" in w for w in report["warnings"])
    assert FD.derive_exit(report) == 0


def test_claimed_without_receipt_is_receiptless(repo: Path, stores: dict[str, Path]) -> None:
    _audit_run(stores, "run-1", manifest={"disposition": "ran-as-requested"})
    report = _scan(repo, stores)
    found = _find(report, "claimed-without-receipt")
    assert len(found) == 1
    assert found[0]["disease"] == "receiptless-delegation"
    assert FD.derive_exit(report) == 1


def test_claimed_with_valid_receipt_is_clean(repo: Path, stores: dict[str, Path]) -> None:
    _audit_run(
        stores, "run-2", manifest={"disposition": "ran-as-requested"}, receipt=_valid_receipt()
    )
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert FD.derive_exit(report) == 0


def test_invalid_receipt_is_evidence_error(repo: Path, stores: dict[str, Path]) -> None:
    bad = _valid_receipt()
    bad["transport"] = "carrier-pigeon"
    _audit_run(stores, "run-3", manifest={"disposition": "ran-as-requested"}, receipt=bad)
    report = _scan(repo, stores)
    assert _find(report, "delegation-evidence-error")
    assert FD.derive_exit(report) == 2


def test_malformed_manifest_is_evidence_error(repo: Path, stores: dict[str, Path]) -> None:
    _audit_run(stores, "run-4", raw_receipt=None)
    run_dir = stores["audit"] / "runs" / "run-4"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text("{broken", encoding="utf-8")
    report = _scan(repo, stores)
    assert _find(report, "delegation-evidence-error")
    assert FD.derive_exit(report) == 2


def test_fallback_without_receipt_is_not_receiptless(repo: Path, stores: dict[str, Path]) -> None:
    _audit_run(stores, "run-5", manifest={"disposition": "fell-back-to-inline"})
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert FD.derive_exit(report) == 0


def test_agy_result_claim_counts_as_claim(repo: Path, stores: dict[str, Path]) -> None:
    _audit_run(stores, "run-6", result={"agy_launched": True})
    report = _scan(repo, stores)
    assert _find(report, "claimed-without-receipt")


def test_receipt_without_claim_is_warning(repo: Path, stores: dict[str, Path]) -> None:
    _audit_run(stores, "run-7", receipt=_valid_receipt())
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert any("receipt present without a claim" in w for w in report["warnings"])


def test_receipt_subset_conforms_to_canonical_validator() -> None:
    spec = importlib.util.spec_from_file_location(
        "_fd_bridge_receipt",
        ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "bridge_receipt.py",
    )
    assert spec is not None and spec.loader is not None
    canonical = importlib.util.module_from_spec(spec)
    sys.modules["_fd_bridge_receipt"] = canonical
    spec.loader.exec_module(canonical)
    fixtures: list[dict[str, Any]] = [_valid_receipt()]
    http = _valid_receipt()
    http["transport"] = "http"
    http["runner"] = {"url": "http://localhost", "status_code": 200, "model": "m"}
    fixtures.append(http)
    broken_transport = _valid_receipt()
    broken_transport["transport"] = "smoke-signal"
    broken_schema = _valid_receipt()
    broken_schema["schema"] = "bridge_receipt.v2"
    broken_runner = _valid_receipt()
    broken_runner["runner"] = {}
    fixtures += [broken_transport, broken_schema, broken_runner]
    # Optional-field corruption: the canon rejects each of these, so the subset must too
    # (no false-clean through fields the gate does not look at).
    for mutation in (
        {"external_tokens": "THIS-IS-CORRUPT"},
        {"external_tokens": True},
        {"run_id": ""},
        {"receipt_emitter": 7},
        {"output_attestation": "not-a-dict"},
        {"output_attestation": {"schema": "output_attestation.v1"}},
        {
            "output_attestation": {
                "schema": "output_attestation.v1",
                "artifact": "out.txt",
                "bytes": 3,
                "sha256": "z" * 64,
                "empty": False,
            }
        },
        {
            "output_attestation": {
                "schema": "output_attestation.v1",
                "artifact": "out.txt",
                "bytes": 3,
                "sha256": "a1" * 32,
                "empty": True,
            }
        },
    ):
        broken = _valid_receipt()
        broken.update(cast("dict[str, Any]", mutation))
        fixtures.append(broken)
    # Optional fields present and valid: both validators must accept.
    rich = _valid_receipt()
    rich.update(
        {
            "receipt_emitter": "bridge",
            "run_id": "run-9",
            "external_tokens": 12,
            "output_attestation": {
                "schema": "output_attestation.v1",
                "artifact": "out.txt",
                "bytes": 3,
                "sha256": "a1" * 32,
                "empty": False,
            },
        }
    )
    fixtures.append(rich)
    # Type-divergent core fields: the canon checks PRESENCE only — the subset must agree
    # rather than be stricter (a canonically valid receipt is never an evidence error).
    stringy = _valid_receipt()
    stringy["wall_time_s"] = "1.5"
    inty = _valid_receipt()
    inty["engine_id"] = 42
    missing_core = _valid_receipt()
    del missing_core["bytes_produced"]
    fixtures += [stringy, inty, missing_core]
    for fixture in fixtures:
        canonical_ok = canonical.validate_receipt(fixture) == []
        subset_ok = FD._receipt_subset_valid(fixture)
        # Conformance: the subset re-derives the canonical verdict exactly — equal
        # accept/reject on every fixture, including optional-field and type-divergent
        # corruption (neither looser nor stricter than the canon).
        assert subset_ok == canonical_ok, (fixture, canonical.validate_receipt(fixture))
    # The ONE enumerated divergence class (fuzz-derived, ceremony r2): the canon's
    # presence-only transport guard accepts `transport: null` — skipping runner-section
    # validation — and its dict-membership check raises on unhashable transports. The doctor
    # stays STRICT and fail-closed on non-string transports: it may over-flag a degenerate
    # receipt, it can never crash or pass one as clean.
    null_transport = _valid_receipt()
    null_transport["transport"] = None
    assert canonical.validate_receipt(null_transport) == []  # the canon's gap
    assert FD._receipt_subset_valid(null_transport) is False  # strict, never false-clean
    unhashables: tuple[Any, ...] = ([], {})
    for unhashable in unhashables:
        crashy = _valid_receipt()
        crashy["transport"] = unhashable
        with pytest.raises(TypeError):
            canonical.validate_receipt(crashy)  # the canon crashes on this input
        assert FD._receipt_subset_valid(crashy) is False  # the doctor must not


def test_thirty_position_matrix_stable_and_exhaustive(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    for index in range(30):
        cls = index % 6
        did, unit = f"d{index}", f"u{index}"
        if cls == 0:
            _manifest_fact(ledger, did, [unit])
            _spawn_fact(ledger, did, unit)
            _settle_fact(ledger, did, unit)
            _outcome_commit(repo, "out-m", did, unit)
        elif cls == 1:
            _outcome_commit(repo, "out-m", did, unit)
        elif cls == 2:
            _manifest_fact(ledger, did, [unit])
            _spawn_fact(ledger, did, unit)
        elif cls == 3:
            _manifest_fact(ledger, did, [unit])
            _spawn_fact(ledger, did, unit)
            _outcome_commit(repo, "out-m", did, unit)
        elif cls == 4:
            _audit_run(stores, f"claim-{index}", manifest={"disposition": "ran-as-requested"})
        else:
            _audit_run(
                stores,
                f"proof-{index}",
                manifest={"disposition": "ran-as-requested"},
                receipt=_valid_receipt(),
            )
    first = _scan(repo, stores)
    second = _scan(repo, stores)
    assert FD.canonical_json(first) == FD.canonical_json(second)
    assert first["complete"] is True
    by_class = {
        "observed-without-spawn-fact": 5,
        "phantom-spawn-fact": 5,
        "unsettled-spawn": 5,
        "claimed-without-receipt": 5,
    }
    for classification, expected in by_class.items():
        assert len(_find(first, classification)) == expected, classification
    assert first["counts"]["findings"] == 20
    assert FD.derive_exit(first) == 1


# ------------------------------------------------------------------ U4: conformance


import ast  # noqa: E402

SAGA_PLUGIN = ROOT / "plugins" / "saga"

_MUTATION_IMPORT_DENYLIST = {
    "outcome_worktrees",
    "outcome_store",
    "outcome",
    "outcome_compat",
    "dispatch_settlement",
    "team_teardown",
    "reap_orphans",
    "audit_store",
    "run_ledger",
    "lease_broker",
    "fleet_commons_shim",
    "orphan_evidence",
    "delegation_audit",
}
_MUTATION_CALL_DENYLIST = {
    "unlink",
    "remove",
    "removedirs",
    "rename",
    "replace",
    "rmdir",
    "mkdir",
    "makedirs",
    "rmtree",
    "write_text",
    "write_bytes",
    "symlink_to",
    "hardlink_to",
    "link",
    "symlink",
    "touch",
    "chmod",
    "chown",
    "quarantine",
}


def test_doctor_imports_no_producer_and_calls_no_mutation() -> None:
    tree = ast.parse(FLEET_DOCTOR.read_text(encoding="utf-8"))
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
            elif isinstance(func, ast.Name):
                called.add(func.id)
    assert imported & _MUTATION_IMPORT_DENYLIST == set()
    assert called & _MUTATION_CALL_DENYLIST == set()
    # The only file-open in the module is os.open with O_RDONLY; no write-mode open exists.
    text = FLEET_DOCTOR.read_text(encoding="utf-8")
    assert "O_RDONLY" in text
    for write_mode in (
        '"w"',
        "'w'",
        '"wb"',
        "'wb'",
        '"a"',
        "'a'",
        '"ab"',
        "'ab'",
        "O_WRONLY",
        "O_RDWR",
        "O_CREAT",
        "O_APPEND",
    ):
        assert write_mode not in text, write_mode


def test_source_matrix_doc_matches_module_and_scan(repo: Path, stores: dict[str, Path]) -> None:
    doc = (SAGA_PLUGIN / "references" / "fleet-doctor-sources.md").read_text(encoding="utf-8")
    doc_kinds = set()
    for line in doc.splitlines():
        if line.startswith("| ") and not line.startswith("| source kind") and "---" not in line:
            cell = line.split("|")[1].strip()
            if cell:
                doc_kinds.add(cell)
    assert doc_kinds == set(FD.SOURCE_KINDS)
    report = _scan(repo, stores)
    emitted = {source["kind"] for source in report["sources"]}
    assert emitted == set(FD.SOURCE_KINDS)


def test_cli_has_no_repair_or_fixture_surface(repo: Path) -> None:
    for forbidden in ("--fix", "--reap", "--retry", "--watch", "--fixture"):
        result = subprocess.run(
            [sys.executable, str(FLEET_DOCTOR), forbidden],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 2, forbidden
        assert "unrecognized arguments" in result.stderr, forbidden


def test_command_doc_loads_exact_skill_and_script() -> None:
    command = (SAGA_PLUGIN / "commands" / "fleet-doctor.md").read_text(encoding="utf-8")
    assert "saga/skills/fleet-doctor/SKILL.md" in command
    assert "plugins/saga/scripts/fleet_doctor.py" in command
    skill = (SAGA_PLUGIN / "skills" / "fleet-doctor" / "SKILL.md").read_text(encoding="utf-8")
    assert "references/fleet-doctor-sources.md" in skill
    assert (SAGA_PLUGIN / "skills" / "fleet-doctor" / "SKILL.md").exists()
    assert FLEET_DOCTOR.exists()


def test_cli_full_fixture_no_write_with_findings(repo: Path, stores: dict[str, Path]) -> None:
    # A findings-bearing scan (exit 1) writes nothing either — not just the clean path.
    _managed_worktree(repo, "out-z", "sub-z")
    _audit_run(stores, "run-z", manifest={"disposition": "ran-as-requested"})
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
    assert result.returncode == 1, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["counts"]["findings"] == 2
    assert _tree_snapshot(repo, stores["lease"], stores["audit"]) == before


# ------------------------------------------------------------------ ceremony r1: strict-read
# hardening oracles (symlinked ledger, truncation bound, OSError fail-closed + redaction)


def test_symlinked_run_facts_ledger_is_unsafe(
    repo: Path, stores: dict[str, Path], tmp_path: Path
) -> None:
    real = tmp_path / "elsewhere.jsonl"
    real.write_bytes(_write_facts(repo, count=2).read_bytes())
    path = _ledger_path(repo)
    path.unlink()
    path.symlink_to(real)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "unsafe-path"
    assert FD.derive_exit(report) == 2


def test_trailing_record_truncation_is_verified_prefix(repo: Path, stores: dict[str, Path]) -> None:
    path = _write_facts(repo, count=4)
    lines = path.read_bytes().split(b"\n")
    path.write_bytes(b"\n".join(lines[:2]) + b"\n")
    report = _scan(repo, stores)
    source = _source(report, "run-facts")
    # Whole-record trailing truncation is undetectable by design (each prefix is an
    # independently valid chain): the verdict claims a verified PREFIX, nothing more.
    assert source["verdict"] == "verified-prefix"
    assert source["record_count"] == 2
    assert report["complete"] is True
    assert FD.derive_exit(report) == 0


def test_open_oserror_fails_closed_not_traceback(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    path = _write_facts(repo, count=2)

    def eloop_open(target: Any, flags: int) -> int:
        raise OSError(errno.ELOOP, "Too many levels of symbolic links", str(target))

    monkeypatch.setattr(FD, "_open", eloop_open)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _source(report, "run-facts")["verdict"] == "unsafe-path"
    assert str(path) not in FD.canonical_json(report)
    assert FD.derive_exit(report) == 2


def test_oserror_evidence_never_leaks_paths(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    real_lstat = os.lstat

    def denying_lstat(target: Any) -> os.stat_result:
        if Path(str(target)) == stores["lease"]:
            raise PermissionError(13, "Permission denied", str(target))
        return real_lstat(target)

    monkeypatch.setattr(FD, "_lstat", denying_lstat)
    report = _scan(repo, stores)
    rendered = FD.canonical_json(report) + FD.render_text(report)
    assert report["complete"] is False
    assert _find(report, "unsafe-path")
    assert str(stores["lease"]) not in rendered
    assert str(Path.home()) not in rendered


@pytest.mark.skipif(os.geteuid() == 0, reason="permission denial is not observable as root")
def test_scandir_oserror_evidence_is_redacted(repo: Path, stores: dict[str, Path]) -> None:
    secret = repo / ".saga-worktrees" / "secret-outcome" / "sub-1"
    secret.mkdir(parents=True)
    outcome_dir = secret.parent
    outcome_dir.chmod(0)
    try:
        report = _scan(repo, stores)
    finally:
        outcome_dir.chmod(0o755)
    assert report["complete"] is False
    assert _find(report, "unsafe-path")
    assert str(repo) not in FD.canonical_json(report)


def test_render_text_neutralizes_control_characters() -> None:
    scan = FD.Scan(repo_identity="r\x1b[31m")
    scan.add_finding(
        FD.Finding(
            disease="leaked-resource",
            classification="stale-worktree",
            subject_id="out\x1b[31m/injected\nsub",
            evidence_refs=("ref\x07one",),
            owner_command="/outcome status",
        )
    )
    scan.warnings.append("warn\x1btext")
    rendered = FD.render_text(FD.build_report(scan))
    assert "\x1b" not in rendered
    assert "\x07" not in rendered
    assert all(ch == "\n" or ch.isprintable() for ch in rendered)


# ------------------------------------------------------------------ ceremony r1: cap matrix
# (every declared cap has a tripping oracle; boundaries are exact)


def test_git_stdout_beyond_cap_fails_closed(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    monkeypatch.setattr(FD, "GIT_STDOUT_CAP", 1)
    report = _scan(repo, stores)
    assert report["complete"] is False
    assert _find(report, "cap-exceeded")
    assert FD.derive_exit(report) == 2


def test_git_stderr_beyond_cap_is_cap_exceeded(repo: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "GIT_STDERR_CAP", 0)
    with pytest.raises(FD.StrictReadError) as info:
        FD.run_git(repo, "rev-parse", "--verify", "no-such-ref-xyz")
    assert info.value.classification == "cap-exceeded"


def test_git_timeout_is_cap_exceeded(repo: Path, monkeypatch: Any) -> None:
    def timing_out_run(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="git", timeout=0.01)

    monkeypatch.setattr(FD.subprocess, "run", timing_out_run)
    with pytest.raises(FD.StrictReadError) as info:
        FD.run_git(repo, "rev-parse", "--show-toplevel")
    assert info.value.classification == "cap-exceeded"


def test_audit_artifact_beyond_cap_is_evidence_error(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    _audit_run(stores, "run-big", manifest={"disposition": "fell-back-to-inline"})
    monkeypatch.setattr(FD, "MAX_ARTIFACT_BYTES", 16)
    report = _scan(repo, stores)
    assert _find(report, "delegation-evidence-error")
    assert report["complete"] is False
    assert FD.derive_exit(report) == 2


def test_output_beyond_cap_withholds_report(
    repo: Path, stores: dict[str, Path], monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setattr(FD, "MAX_OUTPUT_BYTES", 10)
    rc = FD.main(
        [
            "--repo-root",
            str(repo),
            "--lease-store",
            str(stores["lease"]),
            "--audit-store",
            str(stores["audit"]),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "report withheld" in captured.err


def test_depth_cap_managed_scan_fails_closed(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    monkeypatch.setattr(FD, "MAX_DEPTH", 1)
    (repo / ".saga-worktrees" / "out-a" / "sub-1").mkdir(parents=True)
    report = _scan(repo, stores)
    assert _find(report, "cap-exceeded")
    assert report["complete"] is False
    assert FD.derive_exit(report) == 2


def test_depth_cap_audit_runs_fails_closed(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    monkeypatch.setattr(FD, "MAX_DEPTH", 1)
    (stores["audit"] / "runs" / "r1").mkdir(parents=True)
    report = _scan(repo, stores)
    assert _source(report, "audit-store")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_entry_cap_audit_runs(repo: Path, stores: dict[str, Path], monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    for name in ("r1", "r2", "r3"):
        (stores["audit"] / "runs" / name).mkdir(parents=True)
    report = _scan(repo, stores)
    assert _source(report, "audit-store")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_entry_cap_git_worktrees(
    repo: Path, stores: dict[str, Path], tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    _git(repo, "commit", "--allow-empty", "-q", "-m", "seed")
    for name in ("wt1", "wt2"):
        _git(repo, "worktree", "add", "-q", str(tmp_path / name), "HEAD")
    report = _scan(repo, stores)
    assert _source(report, "git-worktrees")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_entry_cap_managed_dirs(repo: Path, stores: dict[str, Path], monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    for name in ("s1", "s2", "s3"):
        (repo / ".saga-worktrees" / "out-a" / name).mkdir(parents=True)
    report = _scan(repo, stores)
    assert any(
        f["classification"] == "cap-exceeded" and "managed worktree" in " ".join(f["evidence_refs"])
        for f in report["findings"]
    )
    assert FD.derive_exit(report) == 2


def test_entry_cap_outcome_dirs(repo: Path, stores: dict[str, Path], monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    for name in ("o1", "o2", "o3"):
        (repo / ".git" / "saga-outcomes" / name).mkdir(parents=True)
    report = _scan(repo, stores)
    assert _source(report, "worktree-registries")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_entry_cap_registry_rows(repo: Path, stores: dict[str, Path], monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    rows = {f"sub-{i}": _registry_row(repo, "out-a", f"sub-{i}") for i in (1, 2, 3)}
    _write_worktree_registry(repo, "out-a", rows)
    report = _scan(repo, stores)
    assert _source(report, "worktree-registries")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_entry_cap_dispatch_records(repo: Path, stores: dict[str, Path], monkeypatch: Any) -> None:
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    for index in range(3):
        _outcome_commit(repo, "out-a", f"d{index}", f"u{index}")
    report = _scan(repo, stores)
    assert _source(report, "outcome-dispatch-events")["verdict"] == "cap-exceeded"
    assert FD.derive_exit(report) == 2


def test_entry_cap_boundary_exact_is_clean(
    repo: Path, stores: dict[str, Path], monkeypatch: Any
) -> None:
    # Exactly cap-many entries stay clean at both normalized guard sites: the cap is a
    # maximum, not an off-by-one.
    monkeypatch.setattr(FD, "MAX_SOURCE_ENTRIES", 2)
    for name in ("r1", "r2"):
        (stores["audit"] / "runs" / name).mkdir(parents=True)
    _write_worktree_registry(
        repo,
        "out-a",
        {f"sub-{i}": _registry_row(repo, "out-a", f"sub-{i}") for i in (1, 2)},
    )
    report = _scan(repo, stores)
    assert _source(report, "audit-store")["verdict"] == "present"
    assert _source(report, "audit-store")["record_count"] == 2
    assert _source(report, "worktree-registries")["record_count"] == 2
    assert report["complete"] is True


# ------------------------------------------------------------------ ceremony r1: uncovered
# reconciliation branches (broker-absent lease, already-absent teardown, late delivery)


def test_registry_lease_absent_from_broker_is_drift(repo: Path, stores: dict[str, Path]) -> None:
    _managed_worktree(repo, "out-a", "sub-1")
    row = _registry_row(repo, "out-a", "sub-1")
    row["lease"] = {
        "lease_id": "L-gone",
        "token": {"broker_epoch": "e", "fencing_sequence": 3},
        "root_sha256": "r",
    }
    _write_worktree_registry(repo, "out-a", {"sub-1": row})
    _broker(stores, leases={"L-other": {"pool": "agent", "owner_id": "o", "resource_ref": {}}})
    report = _scan(repo, stores)
    drift = _find(report, "ownership-drift")
    assert any("absent from the broker" in ref for f in drift for ref in f["evidence_refs"])
    assert FD.derive_exit(report) == 1


def test_teardown_already_absent_but_lease_live_is_terminal_open(
    repo: Path, stores: dict[str, Path]
) -> None:
    ledger = _fact_ledger(repo)
    RL.append_fact(
        ledger,
        RL.build_fact(
            "teardown",
            subplot_id="team",
            at="t",
            event="resource-attempt",
            action_key="k3",
            resource_id="L7",
            resource_kind="provisional-lease",
            generation="e:9",
            action="lease-release",
            team_run_id="run-3",
        ),
    )
    RL.append_fact(
        ledger,
        RL.build_fact(
            "teardown",
            subplot_id="team",
            at="t",
            event="resource-result",
            action_key="k3",
            disposition="already-absent",
            evidence_refs=[],
            team_run_id="run-3",
        ),
    )
    _broker(stores, leases={"L7": {"pool": "agent", "owner_id": "o", "resource_ref": {}}})
    report = _scan(repo, stores)
    open_findings = _find(report, "terminal-resource-open")
    assert [f["subject_id"] for f in open_findings] == ["L7"]
    assert FD.derive_exit(report) == 1


def test_unhashable_transport_receipt_fails_closed(repo: Path, stores: dict[str, Path]) -> None:
    # Ceremony r2 P2: a crafted receipt with a JSON-array transport must be a fail-closed
    # evidence error, never an uncaught TypeError out of run_scan.
    bad = _valid_receipt()
    bad["transport"] = []
    _audit_run(stores, "run-crash", manifest={"disposition": "ran-as-requested"}, receipt=bad)
    report = _scan(repo, stores)
    assert _find(report, "delegation-evidence-error")
    assert report["complete"] is False
    assert FD.derive_exit(report) == 2


def test_null_transport_receipt_is_evidence_error(repo: Path, stores: dict[str, Path]) -> None:
    # The enumerated strict-only divergence end to end: canon accepts transport=null, the
    # doctor flags it — over-flagging a degenerate receipt beats passing it as proof.
    bad = _valid_receipt()
    bad["transport"] = None
    _audit_run(stores, "run-null", manifest={"disposition": "ran-as-requested"}, receipt=bad)
    report = _scan(repo, stores)
    assert _find(report, "delegation-evidence-error")
    assert FD.derive_exit(report) == 2


def test_late_delivery_settlement_is_not_unsettled(repo: Path, stores: dict[str, Path]) -> None:
    ledger = _fact_ledger(repo)
    _manifest_fact(ledger, "d8", ["u8"])
    _spawn_fact(ledger, "d8", "u8")
    RL.append_fact(
        ledger,
        RL.build_fact(
            "dispatch-settlement",
            subplot_id="coord",
            at="t",
            event="late-delivery",
            dispatch_id="d8",
            unit_id="u8",
            attempt=1,
            classification="delivered-late",
            reason="delivered after the settlement deadline",
            evidence_ref="e",
            evidence_sha256="f" * 64,
        ),
    )
    _outcome_commit(repo, "out-a", "d8", "u8")
    report = _scan(repo, stores)
    assert report["findings"] == []
    assert FD.derive_exit(report) == 0
