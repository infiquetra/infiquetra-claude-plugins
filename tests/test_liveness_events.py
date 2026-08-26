"""Canonical Team liveness fact and projection contract (#357)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"test_liveness_{name}", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RL = _load("run_ledger")
LV = _load("liveness_events")

# Old field name for negative tests — intentionally split so the code-only grep
# for the old name stays green. Search for OLD_LEASE_TTL_KEY to find all
# uses (code-review P3-1).
OLD_LEASE_TTL_KEY = "lease" + "_ttl_seconds"


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _identity(**changes: object) -> Any:
    values: dict[str, object] = {
        "session_id": "session-1",
        "subplot_id": "sub-357",
        "dispatch_id": "dispatch-1",
        "unit_id": "unit-1",
        "attempt": 1,
        "resident_id": "worker-1",
        "agent_id": "agent-1",
        "lease_id": "lease-1",
        "resource_sha256": _digest("resource"),
        "broker_epoch": "epoch-1",
        "fencing_sequence": 1,
        "boot_id": "boot-1",
        "manifest_sha256": _digest("manifest"),
        "spawn_sha256": _digest("spawn"),
        "token_sha256": _digest("token"),
        "ttl_seconds": 50.0,
        "baseline_sha256": _digest("baseline"),
        "path_set_sha256": _digest("paths"),
    }
    values.update(changes)
    return LV.SubjectIdentity.from_dict(values)


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(tmp_path / "run-facts.jsonl")


def _subject(ledger: Any, **changes: object) -> Any:
    existing = RL.read_facts(ledger)
    manifest = next(
        (record for record in existing if record.get("event") == "manifest"),
        None,
    )
    if manifest is None:
        manifest = RL.append_fact_atomic(
            ledger,
            RL.build_fact(
                "dispatch-settlement",
                subplot_id="sub-357",
                at="2026-07-17T00:00:00Z",
                event="manifest",
                dispatch_id="dispatch-1",
                site="team-execution",
                units=[{"unit_id": "unit-1", "idempotency_key": "unit-1-key", "deliverables": []}],
                casualty_threshold_percent=0,
                max_attempts=3,
            ),
        )
    existing = RL.read_facts(ledger)
    spawn = next(
        (record for record in existing if record.get("event") == "spawn"),
        None,
    )
    if spawn is None:
        spawn = RL.append_fact_atomic(
            ledger,
            RL.build_fact(
                "dispatch-settlement",
                subplot_id="sub-357",
                at="2026-07-17T00:00:00Z",
                event="spawn",
                dispatch_id="dispatch-1",
                unit_id="unit-1",
                attempt=1,
                idempotency_key="unit-1-key",
            ),
        )
    return _identity(
        manifest_sha256=manifest["this_hash"],
        spawn_sha256=spawn["this_hash"],
        **changes,
    )


def _append(
    ledger: Any,
    identity: Any,
    event: str,
    event_id: str,
    payload: dict[str, object],
) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        LV.append_event(
            ledger,
            identity,
            event,
            event_id=event_id,
            at="2026-07-17T00:00:00Z",
            payload=payload,
        ),
    )


def _open(ledger: Any, identity: Any, *, at: float = 0.0) -> dict[str, Any]:
    return _append(
        ledger,
        identity,
        "subject-open",
        "open-1",
        {"observed_monotonic": at, "source_ref": "manifest-spawn-lease-1"},
    )


def _claim(ledger: Any, identity: Any, *, now: float, event_id: str) -> dict[str, Any]:
    decision = LV.poll_subject(ledger, identity.subject_id, now=now)
    candidate = decision["reping"]
    assert isinstance(candidate, dict)
    generation = decision["generation"]
    return _append(
        ledger,
        identity,
        "reping-intent",
        event_id,
        {
            "generation_id": candidate["generation_id"],
            "cause": candidate["cause"],
            "anchor_ref": generation["anchor_ref"],
            "opened_monotonic": now,
            "liveness_attempt": candidate["liveness_attempt"],
            "retry_ordinal": candidate["retry_ordinal"],
            "predecessor_failure_ref": candidate["predecessor_failure_ref"],
            "claim_key": candidate["claim_key"],
        },
    )


def _sent(
    ledger: Any,
    identity: Any,
    claim: dict[str, Any],
    *,
    at: float,
    event_id: str,
    window: float = 10.0,
) -> dict[str, Any]:
    return _append(
        ledger,
        identity,
        "reping-sent",
        event_id,
        {
            "claim_key": claim["claim_key"],
            "receipt_ref": f"receipt-{event_id}",
            "tool_use_id": f"tool-{event_id}",
            "recipient": identity.agent_id,
            "request_digest": _digest(event_id),
            "accepted_monotonic": at,
            "response_window_seconds": window,
        },
    )


def test_subject_identity_is_closed_and_content_addressed() -> None:
    first = _identity()
    assert first.subject_id.startswith("subject:sha256:")
    assert len(first.subject_id) == len("subject:sha256:") + 64
    assert first.subject_id == _identity().subject_id
    assert first.subject_id != _identity(agent_id="agent-2").subject_id
    with pytest.raises(LV.LivenessEventError, match="not closed"):
        LV.SubjectIdentity.from_dict({**first.to_dict(), "unknown": "x"})


def test_subject_open_requires_exact_manifest_and_spawn_bindings(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(LV.LivenessEventError, match="exact #351 Team manifest"):
        _open(ledger, _identity())


def test_subject_open_replay_is_idempotent_and_drift_is_rejected(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    first = _open(ledger, identity)
    replay = _open(ledger, identity)
    assert replay["this_hash"] == first["this_hash"]
    assert (
        len([record for record in RL.read_facts(ledger) if record.get("kind") == "liveness"]) == 1
    )
    with pytest.raises(LV.LivenessEventError, match="replay changes"):
        _append(
            ledger,
            identity,
            "subject-open",
            "open-1",
            {"observed_monotonic": 1.0, "source_ref": "manifest-spawn-lease-1"},
        )


def test_every_event_repeats_the_exact_closed_subject_identity(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    beat = _append(
        ledger,
        identity,
        "heartbeat",
        "heartbeat-1",
        {"observed_monotonic": 10.0, "host_evidence_ref": "host-beat-1"},
    )
    assert {key: beat[key] for key in LV.IDENTITY_KEYS} == {
        "subject_schema": LV.SUBJECT_SCHEMA,
        "subject_id": identity.subject_id,
        **identity.to_dict(),
    }
    assert set(beat) == LV.BASE_KEYS | LV.PAYLOAD_KEYS["heartbeat"] | {
        "prev_hash",
        "this_hash",
    }


def test_cross_subject_and_extra_payload_fields_fail_closed(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    with pytest.raises(LV.LivenessEventError, match="matching subject-open"):
        _append(
            ledger,
            _subject(ledger, agent_id="agent-2"),
            "heartbeat",
            "heartbeat-cross",
            {"observed_monotonic": 10.0, "host_evidence_ref": "host-beat-1"},
        )
    with pytest.raises(LV.LivenessEventError, match="not closed"):
        _append(
            ledger,
            identity,
            "heartbeat",
            "heartbeat-extra",
            {
                "observed_monotonic": 10.0,
                "host_evidence_ref": "host-beat-1",
                "agent_claim": "alive",
            },
        )


def test_heartbeat_time_is_monotonic_and_rotates_only_heartbeat_generation(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    before = LV.poll_subject(ledger, identity.subject_id, now=60)
    _append(
        ledger,
        identity,
        "scoped-activity-unattributed",
        "activity-1",
        {
            "baseline_digest": identity.baseline_sha256,
            "current_digest": _digest("current"),
            "interval_start": 0.0,
            "interval_end": 55.0,
        },
    )
    after_activity = LV.poll_subject(ledger, identity.subject_id, now=60)
    assert after_activity["generation"] == before["generation"]
    _append(
        ledger,
        identity,
        "heartbeat",
        "heartbeat-1",
        {"observed_monotonic": 70.0, "host_evidence_ref": "host-beat-1"},
    )
    after_beat = LV.poll_subject(ledger, identity.subject_id, now=130)
    assert after_beat["generation"]["generation_id"] != before["generation"]["generation_id"]
    with pytest.raises(LV.LivenessEventError, match="moved backward"):
        _append(
            ledger,
            identity,
            "heartbeat",
            "heartbeat-old",
            {"observed_monotonic": 69.0, "host_evidence_ref": "host-beat-old"},
        )


def test_poll_of_absent_ledger_is_read_only_evidence_error(tmp_path: Path) -> None:
    ledger = RL.RunLedger(tmp_path / "absent" / "facts.jsonl")
    result = LV.poll_subject(ledger, _digest("missing"), now=10)
    assert result["classification"] == "evidence-error"
    assert not ledger.path.parent.exists()


def test_claim_without_send_is_unresolved_and_starts_no_window(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    _claim(ledger, identity, now=60, event_id="claim-0")
    result = LV.poll_subject(ledger, identity.subject_id, now=10_000)
    assert result["classification"] == "reping-send-unresolved"
    assert result["terminal_authority"] == "none"
    assert result["reping"] is None


def test_atomic_claim_has_one_winner(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    barrier = threading.Barrier(2)

    def compete(event_id: str, pre_poll_delay: float = 0.0) -> str:
        if pre_poll_delay > 0:
            time.sleep(pre_poll_delay)
        decision = LV.poll_subject(ledger, identity.subject_id, now=60)
        candidate = decision["reping"]
        assert isinstance(candidate, dict)
        generation = decision["generation"]
        barrier.wait(timeout=5.0)
        try:
            _append(
                ledger,
                identity,
                "reping-intent",
                event_id,
                {
                    "generation_id": candidate["generation_id"],
                    "cause": candidate["cause"],
                    "anchor_ref": generation["anchor_ref"],
                    "opened_monotonic": 60,
                    "liveness_attempt": candidate["liveness_attempt"],
                    "retry_ordinal": candidate["retry_ordinal"],
                    "predecessor_failure_ref": candidate["predecessor_failure_ref"],
                    "claim_key": candidate["claim_key"],
                },
            )
        except LV.LivenessEventError:
            return "lost"
        return "won"

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(compete, "claim-a", 0.0)
        fut_b = pool.submit(compete, "claim-b", 0.02)
        results = [fut_a.result(timeout=5.0), fut_b.result(timeout=5.0)]
    assert sorted(results) == ["lost", "won"]
    assert sum(record["event"] == "reping-intent" for record in RL.read_facts(ledger)) == 1


def test_definitive_initial_failure_allows_one_predecessor_bound_retry(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    initial = _claim(ledger, identity, now=60, event_id="claim-0")
    failure = _append(
        ledger,
        identity,
        "reping-send-failed",
        "failed-0",
        {
            "claim_key": initial["claim_key"],
            "receipt_ref": "receipt-failed-0",
            "definitive_not_sent": True,
            "failed_monotonic": 60.0,
        },
    )
    candidate = LV.poll_subject(ledger, identity.subject_id, now=61)["reping"]
    assert candidate["retry_ordinal"] == 1
    assert candidate["liveness_attempt"] == 0
    assert candidate["predecessor_failure_ref"] == failure["event_id"]
    retry = _claim(ledger, identity, now=61, event_id="claim-1")
    assert retry["predecessor_failure_ref"] == "failed-0"


def test_second_definitive_failure_is_nonterminal_delivery_blocked(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    initial = _claim(ledger, identity, now=60, event_id="claim-0")
    _append(
        ledger,
        identity,
        "reping-send-failed",
        "failed-0",
        {
            "claim_key": initial["claim_key"],
            "receipt_ref": "receipt-failed-0",
            "definitive_not_sent": True,
            "failed_monotonic": 60.0,
        },
    )
    retry = _claim(ledger, identity, now=61, event_id="claim-1")
    _append(
        ledger,
        identity,
        "reping-send-failed",
        "failed-1",
        {
            "claim_key": retry["claim_key"],
            "receipt_ref": "receipt-failed-1",
            "definitive_not_sent": True,
            "failed_monotonic": 61.0,
        },
    )
    result = LV.poll_subject(ledger, identity.subject_id, now=1000)
    assert result["classification"] == "reping-delivery-blocked"
    assert result["terminal_authority"] == "none"
    assert result["reping"] is None


def test_accepted_send_ends_retry_and_only_expiry_advances_attempt(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    claim = _claim(ledger, identity, now=60, event_id="claim-0")
    _sent(ledger, identity, claim, at=60, event_id="sent-0")
    assert LV.poll_subject(ledger, identity.subject_id, now=69)["reping"] is None
    next_candidate = LV.poll_subject(ledger, identity.subject_id, now=71)["reping"]
    assert next_candidate["liveness_attempt"] == 1
    assert next_candidate["retry_ordinal"] == 0
    with pytest.raises(LV.LivenessEventError, match="already has a send result"):
        _append(
            ledger,
            identity,
            "reping-send-failed",
            "failed-after-send",
            {
                "claim_key": claim["claim_key"],
                "receipt_ref": "receipt-failed",
                "definitive_not_sent": True,
                "failed_monotonic": 61.0,
            },
        )


def test_three_proven_expired_windows_confirm_and_two_do_not(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    moments = (60.0, 71.0, 82.0)
    for attempt, moment in enumerate(moments):
        claim = _claim(ledger, identity, now=moment, event_id=f"claim-{attempt}")
        _sent(ledger, identity, claim, at=moment, event_id=f"sent-{attempt}")
        if attempt == 1:
            two = LV.poll_subject(ledger, identity.subject_id, now=81.5)
            assert two["terminal_authority"] == "none"
    result = LV.poll_subject(ledger, identity.subject_id, now=93)
    assert result["classification"] == "confirmed-stalled"
    assert result["terminal_authority"] == "team-reping-confirmed"


def test_reping_ack_closes_only_its_named_generation(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    claim = _claim(ledger, identity, now=60, event_id="claim-0")
    sent = _sent(ledger, identity, claim, at=60, event_id="sent-0")
    _append(
        ledger,
        identity,
        "reping-ack",
        "ack-0",
        {
            "sent_event_id": sent["event_id"],
            "response_ref": "host-response-1",
            "correlation_digest": _digest("response"),
            "covered_generation_ids": [claim["generation_id"]],
            "observed_monotonic": 65.0,
        },
    )
    result = LV.poll_subject(ledger, identity.subject_id, now=1000)
    assert result["classification"] == "healthy"
    assert result["terminal_authority"] == "none"


def test_idle_ack_closes_notice_delivery_but_not_worker_suspicion(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    _append(
        ledger,
        identity,
        "idle-notice",
        "notice-event-1",
        {
            "notice_id": "notice-1",
            "signal_ref": "host-idle-1",
            "signal_digest": _digest("idle"),
            "observed_monotonic": 55.0,
        },
    )
    _append(
        ledger,
        identity,
        "idle-ack",
        "notice-ack-1",
        {
            "notice_id": "notice-1",
            "ack_ref": "host-idle-ack-1",
            "ack_digest": _digest("idle-ack"),
            "observed_monotonic": 56.0,
        },
    )
    result = LV.poll_subject(ledger, identity.subject_id, now=60)
    assert result["pending_notice_ids"] == []
    assert result["classification"] == "reping-required"


def test_idle_notice_allocates_and_deduplicates_under_ledger_lock(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    first = LV.append_idle_notice(
        ledger,
        identity,
        event_id="idle-event-1",
        at="2026-07-17T00:00:55Z",
        host_notice_id=None,
        signal_ref="host-idle-1",
        signal_digest=_digest("idle-1"),
        observed_monotonic=55.0,
    )
    replay = LV.append_idle_notice(
        ledger,
        identity,
        event_id="idle-event-replay",
        at="2026-07-17T00:00:56Z",
        host_notice_id=None,
        signal_ref="host-idle-1",
        signal_digest=_digest("idle-1"),
        observed_monotonic=55.0,
    )
    assert first["notice_id"] == "notice-1"
    assert replay["this_hash"] == first["this_hash"]

    def allocate(index: int) -> str:
        record = LV.append_idle_notice(
            ledger,
            identity,
            event_id=f"idle-event-{index}",
            at="2026-07-17T00:01:00Z",
            host_notice_id=None,
            signal_ref=f"host-idle-{index}",
            signal_digest=_digest(f"idle-{index}"),
            observed_monotonic=60.0 + index,
        )
        return str(record["notice_id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        allocated = sorted(pool.map(allocate, (2, 3)))
    assert allocated == ["notice-2", "notice-3"]
    assert RL.verify_chain(ledger).ok


def test_scoped_activity_never_becomes_progress_without_provenance(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    _append(
        ledger,
        identity,
        "scoped-activity-unattributed",
        "activity-1",
        {
            "baseline_digest": identity.baseline_sha256,
            "current_digest": _digest("current"),
            "interval_start": 0.0,
            "interval_end": 55.0,
        },
    )
    result = LV.poll_subject(ledger, identity.subject_id, now=60)
    assert result["classification"] == "scoped-activity-unattributed"
    assert result["last_progress"] is None
    assert result["reping"] is not None


def test_progress_closure_requires_named_generation_and_strict_interval(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    _append(
        ledger,
        identity,
        "heartbeat",
        "heartbeat-1",
        {"observed_monotonic": 50.0, "host_evidence_ref": "host-beat-1"},
    )
    claim = _claim(ledger, identity, now=110, event_id="claim-0")
    _sent(ledger, identity, claim, at=110, event_id="sent-0", window=20)
    sibling = LV.generation_id(identity.subject_id, "artifactless", "open-1")
    _append(
        ledger,
        identity,
        "artifact-progress",
        "progress-equal",
        {
            "baseline_digest": identity.baseline_sha256,
            "current_digest": _digest("equal"),
            "interval_start": 50.0,
            "interval_end": 110.0,
            "provenance_receipt": "provenance-equal",
            "covered_generation_ids": [claim["generation_id"], sibling],
        },
    )
    equal = LV.poll_subject(ledger, identity.subject_id, now=111)
    assert equal["classification"] != "healthy"
    _append(
        ledger,
        identity,
        "artifact-progress",
        "progress-after",
        {
            "baseline_digest": identity.baseline_sha256,
            "current_digest": _digest("after"),
            "interval_start": 50.0,
            "interval_end": 111.0,
            "provenance_receipt": "provenance-after",
            "covered_generation_ids": [claim["generation_id"]],
        },
    )
    after = LV.poll_subject(ledger, identity.subject_id, now=112)
    assert after["classification"] == "healthy"
    assert after["last_progress"] == 111.0


def test_wrong_receipt_identity_and_missing_notice_are_rejected(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    with pytest.raises(LV.LivenessEventError, match="no matching re-ping claim"):
        _append(
            ledger,
            identity,
            "reping-sent",
            "sent-wrong",
            {
                "claim_key": _digest("wrong"),
                "receipt_ref": "receipt-wrong",
                "tool_use_id": "tool-wrong",
                "recipient": "agent-1",
                "request_digest": _digest("request"),
                "accepted_monotonic": 60.0,
                "response_window_seconds": 10.0,
            },
        )
    with pytest.raises(LV.LivenessEventError, match="no matching notice"):
        _append(
            ledger,
            identity,
            "idle-ack",
            "idle-ack-wrong",
            {
                "notice_id": "notice-missing",
                "ack_ref": "ack-missing",
                "ack_digest": _digest("ack"),
                "observed_monotonic": 60.0,
            },
        )


def test_malformed_stored_liveness_history_returns_evidence_error(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    malformed = RL.build_fact(
        "liveness",
        subplot_id=identity.subplot_id,
        at="t",
        event="heartbeat",
        event_id="malformed",
        subject_id=identity.subject_id,
    )
    RL.append_fact(ledger, malformed)
    result = LV.poll_subject(ledger, identity.subject_id, now=60)
    assert result["classification"] == "evidence-error"
    assert result["terminal_authority"] == "none"


def test_broken_chain_returns_evidence_error(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    identity = _subject(ledger)
    _open(ledger, identity)
    records = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    records[-1]["agent_id"] = "tampered"
    ledger.path.write_text("".join(f"{json.dumps(record)}\n" for record in records))
    result = LV.poll_subject(ledger, identity.subject_id, now=60)
    assert result["classification"] == "evidence-error"
    assert result["reason_code"] == "liveness-history-error:broken-chain"


def test_cli_describes_closed_protocol(capsys: Any) -> None:
    assert LV.main(["describe"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["subject_schema"] == "liveness.subject.v1"
    assert result["decision_schema"] == "liveness_decision.v1"
    assert result["engine_protocol_version"] == 1
    assert result["fleet_core_version"] == "0.25.3"
    assert len(result["engine_sha256"]) == 64
    assert result["max_definitive_not_sent_retries_per_attempt"] == 1


def test_identity_round_trips_through_serialize_then_parse_under_new_key() -> None:
    """The rename must not half-land: serialize then parse with ``ttl_seconds`` survives."""
    old_key = OLD_LEASE_TTL_KEY
    identity = _identity(ttl_seconds=77.0)
    payload = identity.to_dict()
    assert "ttl_seconds" in payload
    assert old_key not in payload
    assert payload["ttl_seconds"] == 77.0
    # Parse path is the wire contract — it must accept the new key.
    restored = LV.SubjectIdentity.from_dict(payload)
    assert restored.ttl_seconds == 77.0
    assert restored.to_dict() == payload
    # Event-level round-trip: every stored record carries the new key.
    assert "ttl_seconds" in LV.IDENTITY_KEYS
    assert old_key not in LV.IDENTITY_KEYS
    ledger_event = {
        "subject_schema": LV.SUBJECT_SCHEMA,
        "subject_id": identity.subject_id,
        **payload,
    }
    assert ledger_event["ttl_seconds"] == 77.0


def test_identity_keys_no_longer_name_old_ttl() -> None:
    old_key = OLD_LEASE_TTL_KEY
    assert old_key not in LV.IDENTITY_KEYS
    assert "ttl_seconds" in LV.IDENTITY_KEYS
    assert old_key not in LV.SubjectIdentity.__dataclass_fields__  # type: ignore[attr-defined]
    assert "ttl_seconds" in LV.SubjectIdentity.__dataclass_fields__  # type: ignore[attr-defined]


def test_old_field_name_does_not_parse() -> None:
    """Previously written events must not be assumed to parse — old key is gone."""
    old_key = OLD_LEASE_TTL_KEY
    payload = _identity().to_dict()
    # Simulate an old event still carrying the old key.
    payload[old_key] = payload.pop("ttl_seconds")
    with pytest.raises(LV.LivenessEventError, match="not closed|ttl_seconds"):
        LV.SubjectIdentity.from_dict(payload)
