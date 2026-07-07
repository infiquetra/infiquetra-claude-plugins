"""Contract tests for the codex.delegation.v1 envelope (plugins/codex/scripts/codex_delegate.py)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "codex" / "scripts" / "codex_delegate.py"


def _load_module():
    scripts_dir = MODULE_PATH.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("codex_delegate_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


codex_delegate = _load_module()


def _base_coder_payload(**overrides):
    payload = {
        "schema": codex_delegate.SCHEMA,
        "role": "coder",
        "mode": "task",
        "task": "Fix the bug in the parser.",
        "write_set": ["plugins/example/file.py"],
    }
    payload.update(overrides)
    return payload


def _base_reviewer_payload(**overrides):
    payload = {
        "schema": codex_delegate.SCHEMA,
        "role": "reviewer",
        "task": "Review the diff for correctness.",
    }
    payload.update(overrides)
    return payload


# --- Valid round-trips -----------------------------------------------------------------------


def test_valid_coder_envelope_round_trips() -> None:
    envelope = codex_delegate.Envelope.from_mapping(_base_coder_payload())
    assert envelope.role == "coder"
    assert envelope.mode == "task"
    assert envelope.write_set == ["plugins/example/file.py"]
    assert envelope.apply_policy == "preserve-patch"
    payload = envelope.to_jsonable()
    assert payload["schema"] == codex_delegate.SCHEMA
    round_tripped = codex_delegate.Envelope.from_mapping(payload)
    assert round_tripped == envelope


def test_valid_reviewer_envelope_defaults() -> None:
    envelope = codex_delegate.Envelope.from_mapping(_base_reviewer_payload())
    assert envelope.role == "reviewer"
    assert envelope.mode == "read-only"
    assert envelope.review_lens == "adversarial"
    assert envelope.write_set == []


def test_reviewer_lens_may_be_overridden() -> None:
    envelope = codex_delegate.Envelope.from_mapping(
        _base_reviewer_payload(review_lens="security-ops")
    )
    assert envelope.review_lens == "security-ops"


def test_model_and_effort_are_optional() -> None:
    envelope = codex_delegate.Envelope.from_mapping(_base_reviewer_payload())
    assert envelope.model is None
    assert envelope.effort is None
    envelope_with = codex_delegate.Envelope.from_mapping(
        _base_reviewer_payload(model="gpt-5", effort="high")
    )
    assert envelope_with.model == "gpt-5"
    assert envelope_with.effort == "high"


# --- Invalid envelopes -------------------------------------------------------------------------


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(role="architect"))


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(mode="auto-if-clean"))


def test_unknown_schema_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(schema="agy.delegation.v1"))


def test_reviewer_with_write_set_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(
            _base_reviewer_payload(write_set=["plugins/example/file.py"])
        )


def test_task_mode_requires_write_set() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(write_set=[]))


def test_empty_task_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(task="   "))


def test_missing_role_is_rejected() -> None:
    payload = _base_coder_payload()
    del payload["role"]
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(payload)


def test_unknown_review_lens_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_reviewer_payload(review_lens="vibes"))


def test_unknown_apply_policy_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(apply_policy="apply-if-clean"))


def test_no_output_seconds_must_not_exceed_timeout() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(
            _base_coder_payload(timeout_seconds=10, no_output_seconds=20)
        )


def test_non_boolean_provenance_required_is_rejected() -> None:
    with pytest.raises(codex_delegate.EnvelopeError):
        codex_delegate.Envelope.from_mapping(_base_coder_payload(provenance_required="yes"))


# --- Receipt emission seam (R8/KTD6) -----------------------------------------------------------


def test_supervised_receipt_is_none_when_codex_did_not_launch() -> None:
    envelope = codex_delegate.Envelope.from_mapping(_base_reviewer_payload())
    now = datetime.now(UTC)
    run_result = codex_delegate.SupervisedRunResult(
        status="error",
        codex_launched=False,
        resolved_codex=None,
        argv=[],
        process_id=None,
        return_code=None,
        started_at=now,
        ended_at=now,
        stdout_bytes=0,
        stderr_bytes=0,
        error="codex binary not found",
    )
    assert codex_delegate._supervised_receipt(run_result, envelope=envelope) is None


def test_supervised_receipt_is_emitted_when_codex_launched() -> None:
    envelope = codex_delegate.Envelope.from_mapping(_base_reviewer_payload(model="gpt-5"))
    started = datetime.now(UTC)
    ended = started
    run_result = codex_delegate.SupervisedRunResult(
        status="success",
        codex_launched=True,
        resolved_codex="/usr/local/bin/codex",
        argv=["codex", "exec", "--json"],
        process_id=4242,
        return_code=0,
        started_at=started,
        ended_at=ended,
        stdout_bytes=128,
        stderr_bytes=0,
    )
    receipt = codex_delegate._supervised_receipt(run_result, envelope=envelope)
    assert receipt is not None
    assert receipt["schema"] == "bridge_receipt.v1"
    assert receipt["engine_id"] == "codex"
    assert receipt["variant"] == "gpt-5"
    assert receipt["transport"] == "cli"
    assert receipt["runner"]["pid"] == 4242
    assert receipt["runner"]["exit_code"] == 0

    bridge_receipt = codex_delegate._bridge_receipt
    assert bridge_receipt.validate_receipt(receipt) == []


def test_validate_only_cli_prints_envelope_and_exits_zero(capsys) -> None:
    exit_code = codex_delegate.main(
        [
            "--role",
            "reviewer",
            "--task",
            "Review the diff.",
            "--validate-only",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"schema": "codex.delegation.v1"' in captured.out


def test_cli_rejects_invalid_envelope_with_nonzero_exit(capsys) -> None:
    exit_code = codex_delegate.main(
        [
            "--role",
            "reviewer",
            "--mode",
            "task",
            "--task",
            "Review the diff.",
            "--validate-only",
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "envelope error" in captured.err
