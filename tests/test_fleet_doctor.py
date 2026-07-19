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
    for fixture in fixtures:
        canonical_ok = canonical.validate_receipt(fixture) == []
        subset_ok = FD._receipt_subset_valid(fixture)
        # Conformance: the doctor's subset never rejects a canonically valid receipt, and
        # rejects every fixture broken in a subset-covered field exactly as the canon does.
        assert subset_ok == canonical_ok, (fixture, canonical.validate_receipt(fixture))


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
