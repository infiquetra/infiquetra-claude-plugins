"""Contract tests for the U2 agy delegation envelope wrapper."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
WRAPPER = ROOT / "plugins" / "agy" / "scripts" / "agy_delegate.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("agy_delegate", WRAPPER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agy_delegate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def agy_delegate() -> ModuleType:
    return _load_module()


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "agy.delegation.v1",
        "role": "coder",
        "mode": "patch-only",
        "task": "Implement a bounded validation-only change.",
        "model": "flash",
        "review_lens": None,
        "write_set": ["plugins/agy/scripts/agy_delegate.py"],
        "apply_policy": "preserve-patch",
        "evidence": "summary",
        "verification": {
            "commands": ["PYTHONPATH=. python3 -m pytest -q tests/test_agy_delegate_contract.py"],
            "required": True,
            "run_scope": "clone",
        },
        "timeout_seconds": 900,
        "no_output_seconds": 180,
        "provenance_required": True,
    }
    payload.update(overrides)
    return payload


def test_valid_envelope_normalizes_defaults(agy_delegate: ModuleType) -> None:
    envelope = agy_delegate.Envelope.from_mapping(
        {
            "schema": "agy.delegation.v1",
            "role": "reviewer",
            "task": "Review this bounded change.",
        }
    )

    assert envelope.role == "reviewer"
    assert envelope.mode == "no-write"
    assert envelope.model == "flash"
    assert envelope.write_set == []
    assert envelope.apply_policy == "preserve-patch"
    assert envelope.evidence == "summary"
    assert envelope.verification.commands == []
    assert envelope.verification.required is False
    assert envelope.verification.run_scope == "clone"
    assert envelope.timeout_seconds == 900
    assert envelope.no_output_seconds == 180
    assert envelope.provenance_required is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("role", "planner"),
        ("mode", "auto"),
        ("review_lens", "friendliness"),
        ("apply_policy", "apply-now"),
        ("evidence", "verbose"),
    ],
)
def test_invalid_enum_rejection(
    agy_delegate: ModuleType, field: str, value: object
) -> None:
    payload = _valid_payload(**{field: value})

    with pytest.raises(agy_delegate.EnvelopeError):
        agy_delegate.Envelope.from_mapping(payload)

    with pytest.raises(agy_delegate.EnvelopeError):
        agy_delegate.parse_status("unknown_status")


def test_auto_if_clean_without_write_set_rejected_before_bundle(
    agy_delegate: ModuleType, tmp_path: Path
) -> None:
    with pytest.raises(agy_delegate.EnvelopeError):
        agy_delegate.Envelope.from_mapping(_valid_payload(mode="auto-if-clean", write_set=[]))

    assert not (tmp_path / ".claude").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"write_set": ["/absolute/path.py"]},
        {"verification": {"commands": [], "required": True, "run_scope": "clone"}},
        {"verification": {"commands": ["pytest"], "required": False, "run_scope": "remote"}},
        {"timeout_seconds": 0},
        {"no_output_seconds": 901},
        {"provenance_required": "yes"},
    ],
)
def test_invalid_shape_rejection(agy_delegate: ModuleType, overrides: dict[str, object]) -> None:
    with pytest.raises(agy_delegate.EnvelopeError):
        agy_delegate.Envelope.from_mapping(_valid_payload(**overrides))


def test_bundle_creation_writes_validation_files_and_projection(
    agy_delegate: ModuleType, tmp_path: Path
) -> None:
    envelope = agy_delegate.Envelope.from_mapping(_valid_payload())
    result = agy_delegate.create_validation_bundle(
        envelope,
        repo_root=tmp_path,
        run_id="unit-run",
        argv=["--role", "coder"],
    )

    bundle = tmp_path / ".claude" / "agy" / "runs" / "unit-run"
    assert result.status == "success"
    assert result.bundle_path == bundle

    for filename in (
        "envelope.json",
        "prompt.txt",
        "command.json",
        "run-lease.json",
        "result.json",
        "projection.md",
    ):
        assert (bundle / filename).exists(), f"missing bundle file: {filename}"

    projection = (bundle / "projection.md").read_text(encoding="utf-8")
    result_payload = json.loads((bundle / "result.json").read_text(encoding="utf-8"))
    command_payload = json.loads((bundle / "command.json").read_text(encoding="utf-8"))

    assert "Status: success" in projection
    assert f"Bundle: {bundle}" in projection
    assert result_payload["validation_only"] is True
    assert result_payload["agy_launched"] is False
    assert command_payload["agy_launch_planned"] is False


def test_projection_names_bundle_path(agy_delegate: ModuleType, tmp_path: Path) -> None:
    envelope = agy_delegate.Envelope.from_mapping(_valid_payload(evidence="minimal"))
    result = agy_delegate.create_validation_bundle(envelope, repo_root=tmp_path, run_id="named")

    assert str(tmp_path / ".claude" / "agy" / "runs" / "named") in result.projection


def test_bundle_write_failure_reports_bundle_failed(
    agy_delegate: ModuleType, tmp_path: Path
) -> None:
    repo_root = tmp_path / "not-a-directory"
    repo_root.write_text("blocks bundle parent creation", encoding="utf-8")
    envelope = agy_delegate.Envelope.from_mapping(_valid_payload())

    result = agy_delegate.create_validation_bundle(envelope, repo_root=repo_root, run_id="blocked")

    assert result.status == "bundle_failed"
    assert "Status: bundle_failed" in result.projection


def test_cli_flags_normalize_to_envelope(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(tmp_path),
            "--run-id",
            "flags-run",
            "--role",
            "reviewer",
            "--task",
            "Review the scoped diff.",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    envelope = json.loads(
        (
            tmp_path / ".claude" / "agy" / "runs" / "flags-run" / "envelope.json"
        ).read_text(encoding="utf-8")
    )
    assert completed.returncode == 0
    assert envelope["role"] == "reviewer"
    assert envelope["mode"] == "no-write"


def test_cli_envelope_dry_validation_outputs_projection(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(tmp_path),
            "--run-id",
            "cli-run",
            "--envelope",
            str(envelope_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    bundle = tmp_path / ".claude" / "agy" / "runs" / "cli-run"
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "Status: success" in completed.stdout
    assert f"Bundle: {bundle}" in completed.stdout
    assert completed.stdout == (bundle / "projection.md").read_text(encoding="utf-8")


def test_cli_rejects_invalid_envelope_without_bundle(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(
        json.dumps(_valid_payload(mode="auto-if-clean", write_set=[])),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(tmp_path),
            "--run-id",
            "bad-run",
            "--envelope",
            str(envelope_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "auto-if-clean requires a non-empty write_set" in completed.stderr
    assert not (tmp_path / ".claude").exists()
