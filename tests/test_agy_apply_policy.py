"""Tests for U4 agy clone execution and apply policy."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
WRAPPER = ROOT / "plugins" / "agy" / "scripts" / "agy_delegate.py"
FAKE_AGY = ROOT / "tests" / "fixtures" / "agy" / "fake_agy.py"
LEASE_BROKER = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
AUDIT_HARNESS = ROOT / "plugins" / "agy" / "scripts" / "audit_harness_transcript.py"


def _load_wrapper_module() -> Any:
    spec = importlib.util.spec_from_file_location("agy_delegate_verification_test", WRAPPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AGY = _load_wrapper_module()


def _load_lease_broker() -> Any:
    spec = importlib.util.spec_from_file_location("agy_apply_policy_lease_broker", LEASE_BROKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_audit_harness() -> Any:
    spec = importlib.util.spec_from_file_location("agy_apply_policy_harness_audit", AUDIT_HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    (repo / "allowed.txt").write_text("before\n", encoding="utf-8")
    _git(repo, "add", "README.md", "allowed.txt")
    _git(repo, "commit", "-m", "initial")
    return repo


def _payload(task: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "agy.delegation.v1",
        "role": "coder",
        "mode": "patch-only",
        "task": task,
        "model": "flash",
        "review_lens": None,
        "write_set": ["allowed.txt"],
        "apply_policy": "preserve-patch",
        "evidence": "summary",
        "verification": {
            "commands": [],
            "required": False,
            "run_scope": "clone",
        },
        "timeout_seconds": 5,
        "no_output_seconds": 3,
        "provenance_required": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("mode", "validation_only"),
    [("patch-only", True), ("patch-only", False), ("no-write", False)],
)
def test_non_apply_modes_do_not_load_live_apply_containment_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    validation_only: bool,
) -> None:
    repo = _init_repo(tmp_path)
    envelope = repo / "envelope.json"
    envelope.write_text(json.dumps(_payload("no live apply", mode=mode)), encoding="utf-8")
    loaded: list[str] = []

    def unavailable(name: str) -> Any:
        loaded.append(name)
        raise RuntimeError(f"old fleet-core lacks {name}")

    monkeypatch.setattr(
        AGY,
        "agy_lease_admission",
        AGY._LazyModule(lambda: unavailable("agy_lease_admission")),
    )
    monkeypatch.setattr(
        AGY,
        "_orphan_evidence",
        AGY._LazyModule(lambda: unavailable("orphan_evidence")),
    )
    argv = [
        "--envelope",
        str(envelope),
        "--repo-root",
        str(repo),
        "--run-id",
        f"lazy-{mode}-{validation_only}",
        "--audit-store",
        str(tmp_path / "audit"),
    ]
    if validation_only:
        argv.append("--validation-only")
    else:
        argv.extend(["--launch-agy", "--agy-bin", str(FAKE_AGY)])

    assert AGY.main(argv) == 0
    assert loaded == []


def test_agy_live_apply_rejects_old_lease_protocol_at_module_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shim = SimpleNamespace(
        load=lambda name: (
            SimpleNamespace(PROTOCOL_VERSION=1) if name == "lease_broker" else SimpleNamespace()
        )
    )
    monkeypatch.setitem(sys.modules, "fleet_commons_shim", shim)
    spec = importlib.util.spec_from_file_location(
        "agy_lease_admission_old_protocol_test",
        ROOT / "plugins" / "agy" / "scripts" / "agy_lease_admission.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(RuntimeError, match="lease protocol 2.*install/update fleet-core"):
        spec.loader.exec_module(module)


def _run_wrapper(
    tmp_path: Path,
    repo: Path,
    payload: dict[str, object],
    run_id: str,
    *,
    resource_key: str | None = None,
) -> subprocess.CompletedProcess[str]:
    envelope_dir = tmp_path / "envelopes"
    envelope_dir.mkdir(exist_ok=True)
    envelope_path = envelope_dir / f"{run_id}.json"
    envelope_path.write_text(json.dumps(payload), encoding="utf-8")

    argv = [
        sys.executable,
        str(WRAPPER),
        "--repo-root",
        str(repo),
        "--run-id",
        run_id,
        "--envelope",
        str(envelope_path),
        "--launch-agy",
        "--agy-bin",
        str(FAKE_AGY),
        "--audit-store",
        str(tmp_path / "audit-store"),
    ]
    if payload.get("mode") == "auto-if-clean":
        key_file = tmp_path / f"{run_id}.lease-key"
        key_file.write_text(resource_key or f"test-{run_id}", encoding="utf-8")
        key_file.chmod(0o600)
        argv.extend(["--lease-resource-key-file", str(key_file)])
    environment = dict(os.environ)
    environment["INFIQUETRA_FLEET_STATE_DIR"] = str(tmp_path / "fleet-state")
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _bundle(repo: Path, run_id: str) -> Path:
    return repo / ".claude" / "agy" / "runs" / run_id


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _assert_no_live_agy_authority(state_root: Path) -> None:
    registry = _json(state_root / "registry.json")
    assert registry["leases"] == {}
    assert registry["settlements"] == {}
    assert registry["session_admissions"] == {}


def test_clone_verification_renews_lease_and_fences_on_renewal_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(AGY, "LEASE_RENEWAL_INTERVAL_SECONDS", 0.01)
    envelope = AGY.Envelope.from_mapping(
        _payload(
            "verify renewal",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={"commands": ["sleep 1.2"], "required": True, "run_scope": "clone"},
            timeout_seconds=3,
        )
    )
    renewals: list[str] = []

    passing = AGY.run_verification_commands(
        envelope,
        clone_path=tmp_path,
        renew_callback=lambda: renewals.append("renewed"),
    )

    assert passing["passed"] is True
    assert renewals

    def refuse() -> None:
        raise RuntimeError("lease superseded")

    refused = AGY.run_verification_commands(
        envelope,
        clone_path=tmp_path,
        renew_callback=refuse,
    )

    assert refused["passed"] is False
    assert "lease superseded" in refused["commands"][0]["lease_renewal_error"]


def test_patch_only_preserves_clone_patch_without_live_mutation(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload("FAKE_AGY_WRITE allowed.txt::after\n"),
        "patch-only-run",
    )
    bundle = _bundle(repo, "patch-only-run")

    assert completed.returncode == 0
    assert _json(bundle / "result.json")["status"] == "patch_ready"
    assert _json(bundle / "run-lease.json")["real_agy_verdict"] == "real"
    assert _json(bundle / "changed-paths.json")["changed_paths"] == ["allowed.txt"]
    assert "after" in (bundle / "diff.patch").read_text(encoding="utf-8")
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"

    proof = _json(bundle / "git-proof.json")
    assert proof["base_sha"] == _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert proof["clone_path"] == str(bundle / "worktree")
    assert proof["removed_remotes"] == ["origin"]
    assert proof["clone_remotes_after"] == []
    assert proof["rogue_commits"] == []
    assert proof["clone_post_status"]["entries"]
    assert _git(bundle / "worktree", "remote").stdout == ""


def test_relative_repo_root_does_not_make_bundle_logs_clone_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    envelope_path = tmp_path / "relative-envelope.json"
    envelope_path.write_text(json.dumps(_payload("FAKE_AGY_MODE=success")), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            repo.name,
            "--run-id",
            "relative-root-run",
            "--envelope",
            str(envelope_path),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
            "--audit-store",
            str(tmp_path / "audit-store"),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    bundle = _bundle(repo, "relative-root-run")

    assert completed.returncode == 0
    assert _json(bundle / "result.json")["status"] == "success"
    assert _json(bundle / "changed-paths.json")["changed_paths"] == []
    assert (bundle / "agy.log").exists()
    assert (bundle / "diff.patch").read_text(encoding="utf-8") == ""


def test_auto_if_clean_applies_in_scope_patch_after_required_checks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ['test "$(cat allowed.txt)" = after'],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "apply-run",
    )
    bundle = _bundle(repo, "apply-run")
    proof = _json(bundle / "git-proof.json")

    assert completed.returncode == 0
    assert _json(bundle / "result.json")["status"] == "applied"
    assert _json(bundle / "run-lease.json")["real_agy_verdict"] == "real"
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "after"
    assert proof["post_apply"]["live_changed_paths"] == ["allowed.txt"]
    assert proof["post_apply"]["only_expected_changes"] is True
    assert _json(bundle / "checks.json")["passed"] is True
    result = _json(bundle / "result.json")
    assert result["write_disposition"] == "accepted"
    assert result["settlement_close"]["phase"] == "closed"
    command = (bundle / "command.json").read_text(encoding="utf-8")
    assert "test-apply-run" not in command
    assert "<redacted>" in command
    seals = list((tmp_path / "audit-store" / "close-seals").rglob("*.json"))
    assert len(seals) == 1
    assert _json(seals[0])["receipt_sha256"] == result["settlement_close"]["receipt_sha256"]


def test_auto_if_clean_closed_resource_head_acquires_exact_successor(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    policy = {
        "mode": "auto-if-clean",
        "apply_policy": "apply-if-clean",
        "verification": {"commands": ["true"], "required": True, "run_scope": "clone"},
    }
    first = _run_wrapper(
        tmp_path,
        repo,
        _payload("FAKE_AGY_WRITE allowed.txt::first\\n", **policy),
        "first-generation",
        resource_key="same-logical-resource",
    )
    assert first.returncode == 0, first.stderr
    first_result = _json(_bundle(repo, "first-generation") / "result.json")
    _git(repo, "add", "allowed.txt")
    _git(repo, "commit", "-m", "settle first generation")

    second = _run_wrapper(
        tmp_path,
        repo,
        _payload("FAKE_AGY_WRITE allowed.txt::second\\n", **policy),
        "second-generation",
        resource_key="same-logical-resource",
    )
    assert second.returncode == 0, second.stderr
    second_result = _json(_bundle(repo, "second-generation") / "result.json")

    assert first_result["status"] == second_result["status"] == "applied"
    assert first_result["run_id"] != second_result["run_id"]
    assert (
        first_result["settlement_close"]["token"]["fencing_sequence"]
        < second_result["settlement_close"]["token"]["fencing_sequence"]
    )


def test_invalid_run_id_is_rejected_before_direct_admission_or_bundle(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    envelope = tmp_path / "invalid-run-id.json"
    envelope.write_text(
        json.dumps(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        encoding="utf-8",
    )
    key_file = tmp_path / "invalid-run-id.key"
    key_file.write_text("invalid-run-id-resource", encoding="utf-8")
    key_file.chmod(0o600)
    state_root = tmp_path / "fleet-state"
    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            "../invalid",
            "--envelope",
            str(envelope),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
            "--audit-store",
            str(tmp_path / "audit-store"),
            "--lease-resource-key-file",
            str(key_file),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "INFIQUETRA_FLEET_STATE_DIR": str(state_root)},
    )

    assert completed.returncode == 2
    assert "run_id must be a non-empty path segment" in completed.stderr
    assert not (repo / ".claude" / "agy" / "runs").exists()
    assert not state_root.exists()
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"


def test_post_acquisition_binding_and_handoff_validation_drain_authority(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo = _init_repo(tmp_path)
    state_root = tmp_path / "fleet-state"
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(state_root))
    admission_module = AGY.agy_lease_admission

    def fail_binding(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("injected binding failure")

    original_bind = admission_module._evidence_module.bind_expected_output
    monkeypatch.setattr(admission_module._evidence_module, "bind_expected_output", fail_binding)
    try:
        admission_module.resolve_direct_agy_admission(repo, "binding-resource", "binding-failure")
    except RuntimeError as exc:
        assert "injected binding failure" in str(exc)
    else:
        raise AssertionError("binding failure should escape after authority cleanup")
    _assert_no_live_agy_authority(state_root)

    monkeypatch.setattr(admission_module._evidence_module, "bind_expected_output", original_bind)
    admission = admission_module.resolve_direct_agy_admission(repo, "handoff-resource", "handoff")
    admission.expected_output["run_id"] = "different-run"
    result = AGY.create_supervised_bundle(
        AGY.Envelope.from_mapping(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        repo_root=repo,
        run_id="handoff",
        agy_bin=str(FAKE_AGY),
        audit_store_root=tmp_path / "audit-store",
        lease_admission=admission,
    )

    assert result.status == "bundle_failed"
    assert not (repo / ".claude" / "agy" / "runs" / "handoff").exists()
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"
    _assert_no_live_agy_authority(state_root)


def test_pre_settlement_cleanup_failure_is_terminal_and_retains_authority_truth(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo = _init_repo(tmp_path)
    state_root = tmp_path / "fleet-state"
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(state_root))
    admission = AGY.agy_lease_admission.resolve_direct_agy_admission(
        repo, "cleanup-failure-resource", "cleanup-failure"
    )
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")

    def fail_release(*_args: Any, **_kwargs: Any) -> bool:
        raise RuntimeError("injected release failure")

    monkeypatch.setattr(admission.broker, "release", fail_release)
    result = AGY.create_supervised_bundle(
        AGY.Envelope.from_mapping(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        repo_root=repo,
        run_id="cleanup-failure",
        agy_bin=str(FAKE_AGY),
        audit_store_root=tmp_path / "audit-store",
        lease_admission=admission,
    )

    payload = _json(_bundle(repo, "cleanup-failure") / "result.json")
    assert result.status == "bundle_failed"
    assert payload["status"] == "bundle_failed"
    assert payload["retain_authority"] is True
    assert "live repo is dirty before auto-if-clean launch" in payload["error"]
    assert "injected release failure" in payload["error"]
    registry = _json(state_root / "registry.json")
    assert registry["leases"]
    assert registry["session_admissions"]


def test_final_registry_close_failure_keeps_durable_result_pending_and_auditor_fails(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo = _init_repo(tmp_path)
    state_root = tmp_path / "fleet-state"
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(state_root))
    admission = AGY.agy_lease_admission.resolve_direct_agy_admission(
        repo, "close-failure-resource", "close-failure"
    )
    original_write = admission.broker._write_registry
    writes = 0

    def fail_close_once(registry: Any) -> None:
        nonlocal writes
        writes += 1
        # prepare, then durable ``committing``, then the final close linearization.
        if writes == 3:
            raise OSError("injected final registry close failure")
        original_write(registry)

    monkeypatch.setattr(admission.broker, "_write_registry", fail_close_once)
    result = AGY.create_supervised_bundle(
        AGY.Envelope.from_mapping(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        repo_root=repo,
        run_id="close-failure",
        agy_bin=str(FAKE_AGY),
        audit_store_root=tmp_path / "audit-store",
        lease_admission=admission,
    )

    bundle_payload = _json(_bundle(repo, "close-failure") / "result.json")
    mirrored = AGY._audit_store.resolve_result(
        AGY._audit_store.Store.for_root(tmp_path / "audit-store"), "close-failure"
    )
    assert result.status == "bundle_failed"
    assert bundle_payload["status"] == "acceptance_pending"
    assert mirrored is not None and mirrored["status"] == "acceptance_pending"
    assert _load_audit_harness()._is_passing_result(mirrored) is False


def test_resource_key_is_digested_and_bundle_artifacts_are_owner_private(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    raw_key = "raw-resource-key-never-persist"
    key_file = tmp_path / "private-resource-key"
    key_file.write_text(raw_key, encoding="utf-8")
    key_file.chmod(0o600)
    envelope = tmp_path / "private-key-envelope.json"
    envelope.write_text(
        json.dumps(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        encoding="utf-8",
    )
    state_root = tmp_path / "fleet-state"
    audit_root = tmp_path / "audit-store"

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            "private-key-run",
            "--envelope",
            str(envelope),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
            "--audit-store",
            str(audit_root),
            "--lease-resource-key-file",
            str(key_file),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "INFIQUETRA_FLEET_STATE_DIR": str(state_root)},
    )

    assert completed.returncode == 0, completed.stderr
    bundle = _bundle(repo, "private-key-run")
    assert bundle.stat().st_mode & 0o777 == 0o700
    artifact_files = [path for path in bundle.iterdir() if path.is_file()]
    assert artifact_files
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in artifact_files)
    persisted_paths = [*artifact_files, state_root / "registry.json"]
    persisted_paths.extend(path for path in audit_root.rglob("*") if path.is_file())
    assert all(raw_key not in path.read_text(encoding="utf-8") for path in persisted_paths)
    assert raw_key not in completed.stdout
    assert raw_key not in completed.stderr
    assert "--lease-resource-key-file" in (bundle / "command.json").read_text(encoding="utf-8")
    assert str(key_file) not in (bundle / "command.json").read_text(encoding="utf-8")


def test_group_readable_resource_key_file_is_rejected_before_bundle(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    key_file = tmp_path / "unsafe-resource-key"
    key_file.write_text("unsafe-resource", encoding="utf-8")
    key_file.chmod(0o640)
    envelope = tmp_path / "unsafe-key-envelope.json"
    envelope.write_text(
        json.dumps(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            "unsafe-key-run",
            "--envelope",
            str(envelope),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
            "--lease-resource-key-file",
            str(key_file),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "INFIQUETRA_FLEET_STATE_DIR": str(tmp_path / "fleet-state")},
    )

    assert completed.returncode == 2
    assert "unreadable by group or other users" in completed.stderr
    assert not _bundle(repo, "unsafe-key-run").exists()


def test_validation_bundle_artifacts_are_owner_private(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    envelope = tmp_path / "validation-envelope.json"
    envelope.write_text(json.dumps(_payload("validate only")), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            "private-validation-run",
            "--envelope",
            str(envelope),
            "--validation-only",
            "--audit-store",
            str(tmp_path / "audit-store"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    bundle = _bundle(repo, "private-validation-run")
    assert bundle.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in bundle.iterdir())


def test_patch_only_with_explicit_write_set_flags_out_of_scope_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload("FAKE_AGY_WRITE outside.txt::oops\n"),
        "patch-out-of-scope-run",
    )
    bundle = _bundle(repo, "patch-out-of-scope-run")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "out_of_scope_mutation"
    assert _json(bundle / "checks.json")["out_of_scope_paths"] == ["outside.txt"]
    assert not (repo / "outside.txt").exists()


def test_no_write_clone_mutation_is_not_successful_patch_ready(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            role="reviewer",
            mode="no-write",
            write_set=[],
        ),
        "no-write-mutated-run",
    )
    bundle = _bundle(repo, "no-write-mutated-run")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "out_of_scope_mutation"
    assert _json(bundle / "checks.json")["out_of_scope_paths"] == ["allowed.txt"]
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"


def test_auto_if_clean_refuses_out_of_scope_clone_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE outside.txt::oops\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["true"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "out-of-scope-run",
    )
    bundle = _bundle(repo, "out-of-scope-run")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "out_of_scope_mutation"
    assert not (repo / "outside.txt").exists()
    assert _json(bundle / "checks.json")["out_of_scope_paths"] == ["outside.txt"]


def test_auto_if_clean_refuses_when_required_verification_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["exit 9"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "checks-failed-run",
    )
    bundle = _bundle(repo, "checks-failed-run")
    checks = _json(bundle / "checks.json")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "checks_failed"
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"
    assert checks["passed"] is False
    assert checks["commands"][0]["return_code"] == 9


def test_auto_if_clean_dirty_live_repo_refuses_before_launch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")

    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["true"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "dirty-run",
    )
    bundle = _bundle(repo, "dirty-run")
    result = _json(bundle / "result.json")
    proof = _json(bundle / "git-proof.json")

    assert completed.returncode == 1
    assert result["status"] == "checks_failed"
    assert result["agy_launched"] is False
    assert not (bundle / "worktree").exists()
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"
    assert proof["live_preflight"]["clean"] is False
    assert proof["live_preflight"]["changed_paths"] == ["README.md"]
    assert "UnboundLocalError" not in completed.stderr
    registry = _json(tmp_path / "fleet-state" / "registry.json")
    assert registry["leases"] == {}
    assert registry["settlements"] == {}


def test_resource_key_required_for_auto_apply_before_bundle_or_runner(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    envelope = tmp_path / "missing-key.json"
    envelope.write_text(
        json.dumps(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::after\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={"commands": ["true"], "required": True, "run_scope": "clone"},
            )
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            "missing-key",
            "--envelope",
            str(envelope),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
            "--audit-store",
            str(tmp_path / "audit-store"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "INFIQUETRA_FLEET_STATE_DIR": str(tmp_path / "fleet-state")},
    )

    assert completed.returncode == 2
    assert "--lease-resource-key-file is required" in completed.stderr
    assert not _bundle(repo, "missing-key").exists()
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"


def test_armed_mirror_failure_is_nonpassing_and_retains_authority(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    audit = tmp_path / "audit-store"
    audit.write_text("not-a-private-directory\n", encoding="utf-8")
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={"commands": ["true"], "required": True, "run_scope": "clone"},
        ),
        "mirror-failure",
    )

    assert completed.returncode == 1
    result = _json(_bundle(repo, "mirror-failure") / "result.json")
    assert result["write_disposition"] == "acceptance-pending"
    assert "settlement_close" not in result
    registry = _json(tmp_path / "fleet-state" / "registry.json")
    [settlement] = registry["settlements"].values()
    assert settlement["phase"] == "ambiguous"
    assert registry["leases"]
    assert audit.is_file()


def test_superseded_lease_rejected_at_production_wrapper_seam(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    run_id = "superseded-wrapper"
    envelope = tmp_path / "superseded.json"
    envelope.write_text(
        json.dumps(
            _payload(
                "FAKE_AGY_WRITE allowed.txt::stale\n",
                mode="auto-if-clean",
                apply_policy="apply-if-clean",
                verification={
                    "commands": ["touch ../settlement-ready && sleep 2"],
                    "required": True,
                    "run_scope": "clone",
                },
            )
        ),
        encoding="utf-8",
    )
    state_root = tmp_path / "fleet-state"
    audit_root = tmp_path / "audit-store"
    key_file = tmp_path / "superseded-wrapper.lease-key"
    key_file.write_text("shared-wrapper-resource", encoding="utf-8")
    key_file.chmod(0o600)
    process = subprocess.Popen(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            run_id,
            "--envelope",
            str(envelope),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
            "--audit-store",
            str(audit_root),
            "--lease-resource-key-file",
            str(key_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "INFIQUETRA_FLEET_STATE_DIR": str(state_root)},
    )
    ready = _bundle(repo, run_id) / "settlement-ready"
    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ready.exists(), process.communicate(timeout=5)

    broker_module = _load_lease_broker()
    broker = broker_module.LeaseBroker(state_root)
    registry = broker.inspect()
    stale = next(iter(registry["leases"]))
    stale_record = next(
        item for item in registry["leases"] if item["lease_id"] == stale["lease_id"]
    )
    successor = broker.acquire_agent(
        owner_id="retry-owner",
        session_id="retry-session",
        policy_sha256=stale_record["policy_sha256"],
        session_limit=stale_record["session_limit"],
        aggregate_limit=stale_record["aggregate_limit"],
        mutation="read-write",
        resource_ref=stale_record["resource_ref"],
        agent_type="agy-direct",
    )
    stdout, stderr = process.communicate(timeout=10)

    assert process.returncode == 1, (stdout, stderr)
    result = _json(_bundle(repo, run_id) / "result.json")
    assert result["write_disposition"] == "ORPHAN_WRITE_BLOCKED"
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"
    assert broker.classify_token(successor.resource_ref, successor.token) == "current"
    events = list((audit_root / "orphan-events").rglob("*.json"))
    assert len(events) == 1
    assert _json(events[0])["classification"] == "superseded-write-blocked"
    assert not (audit_root / "quarantine").exists()
