#!/usr/bin/env python3
"""Tracked process that holds herdr subscriptions and wakes an orchestrator pane.

The event stream is only a hint: herdr protocol 19 has no replay cursor. This process therefore
runs one bounded snapshot catch-up after each accepted subscription, including the first one.
Catch-up records lifecycle disagreement and artifact presence only. Predicate evaluation belongs
to the later unit that supplies a real predicate producer and consumer.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import accounting
import herdr_events
import register as register_store

SENTINEL_MARKER = "ORCHESTRATE_SENTINEL "


@dataclass(frozen=True)
class CatchUpRecord:
    """One registered row compared with the latest live snapshot."""

    row_id: str
    pane_id: str
    expected_state: str | None
    observed_state: str
    observed_state_source: str
    diverged: bool
    revision: int | None
    artifact_path: str | None
    artifact_exists: bool | None


def make_sentinel(
    run_id: str,
    child_id: str,
    purpose: str,
    *,
    nonce: str | None = None,
) -> str:
    """Return a unique, parseable marker bound to one run, child, and interaction."""
    if not run_id or not child_id or not purpose:
        raise ValueError("run_id, child_id, and purpose must be non-empty")
    payload = {
        "run_id": run_id,
        "child_id": child_id,
        "purpose": purpose,
        "nonce": nonce or uuid.uuid4().hex,
    }
    return SENTINEL_MARKER + json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sentinel_assembly_instructions(sentinel: str, *, when: str) -> str:
    """Build producer instructions that never expose an assembled sentinel to prompt echo.

    All readiness and completion producers must use this helper rather than interpolating a
    sentinel directly into dispatch input. A child can still assemble the marker too early while
    reasoning, so the resulting match proves interaction, not task completion.
    """
    if not sentinel.startswith(SENTINEL_MARKER):
        raise ValueError("sentinel lacks the orchestrate marker")
    if not when.strip():
        raise ValueError("sentinel assembly timing must be non-empty")
    payload = sentinel[len(SENTINEL_MARKER) :]
    prompt = (
        "Print one line formed by joining the following two parts with no separator. Do not print "
        "the assembled line while explaining or reasoning; print it only when "
        f"{when.strip()}.\n"
        f"part 1: {SENTINEL_MARKER!r}\n"
        f"part 2: {payload!r}"
    )
    if sentinel in prompt:
        raise AssertionError("assembled sentinel must not appear in dispatch input")
    return prompt


def output_match_subscription(
    pane_id: str,
    sentinel: str,
) -> dict[str, Any]:
    """Build herdr's four-field output subscription using the socket API's source spelling."""
    subscription = {
        "type": "pane.output_matched",
        "pane_id": pane_id,
        "source": "recent_unwrapped",
        "match": {"type": "substring", "value": sentinel},
    }
    herdr_events.validate_subscription(subscription)
    return subscription


def usage_match_subscription(pane_id: str) -> dict[str, Any]:
    """Subscribe to a vendor usage line on one pane.

    The match is the closed accounting needle, not a free-text pattern and not
    a regex. Identity-bound sentinels stay on :func:`output_match_subscription`.
    """
    subscription = {
        "type": "pane.output_matched",
        "pane_id": pane_id,
        "source": "recent_unwrapped",
        "match": {"type": "substring", "value": accounting.USAGE_SUBSTRING},
    }
    herdr_events.validate_subscription(subscription)
    return subscription


def _sentinel_payload(line: str) -> dict[str, Any] | None:
    marker_at = line.find(SENTINEL_MARKER)
    if marker_at < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(line[marker_at + len(SENTINEL_MARKER) :])
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _sentinel_expectations(
    subscriptions: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    expectations: dict[str, list[dict[str, Any]]] = {}
    identity_fields = ("run_id", "child_id", "purpose", "nonce")
    for subscription in subscriptions:
        if subscription.get("type") != "pane.output_matched":
            continue
        pane_id = subscription.get("pane_id")
        match = subscription.get("match")
        if not isinstance(pane_id, str) or not isinstance(match, Mapping):
            raise herdr_events.SubscriptionError(
                "pane.output_matched requires pane_id and a match object"
            )
        if match.get("type") != "substring" or not isinstance(match.get("value"), str):
            raise herdr_events.SubscriptionError(
                "the orchestrate subscriber requires pane.output_matched to use a substring "
                "sentinel match"
            )
        value = str(match["value"])
        payload = _sentinel_payload(value)
        if payload is not None and not any(
            not isinstance(payload.get(field), str) or not payload[field]
            for field in identity_fields
        ):
            expectations.setdefault(pane_id, []).append(payload)
            continue
        if accounting.is_usage_match_value(value):
            continue
        raise herdr_events.SubscriptionError(
            "pane.output_matched substring must contain a complete orchestrate sentinel"
        )
    return expectations


def _artifact_presence(root: Path, value: Any) -> tuple[str | None, bool | None]:
    if not isinstance(value, str) or not value:
        return None, None
    path = Path(value)
    resolved = path if path.is_absolute() else root / path
    return value, resolved.exists()


def catch_up(
    root: Path,
    snapshot: Mapping[str, Any],
    *,
    run_id: str,
) -> list[CatchUpRecord]:
    """Re-read every registered pane from one live snapshot and record observed state.

    A missing pane is recorded as ``exited``. A status mismatch remains a mismatch: catch-up does
    not promote lifecycle phases or trust detector status as a completion verdict.

    ``root`` must be this run's work location. It is also the base for a relative
    ``artifact_path``. A disagreeing directory is refused before any row is written.
    """
    register_store.assert_root_belongs_to_run(root, run_id, require_binding=False)
    panes_value = snapshot.get("panes")
    agents_value = snapshot.get("agents")
    if not isinstance(panes_value, list) or not isinstance(agents_value, list):
        raise herdr_events.ProtocolError("session.snapshot requires list 'panes' and 'agents'")

    live: dict[str, dict[str, Any]] = {}
    for item in panes_value:
        if isinstance(item, Mapping) and isinstance(item.get("pane_id"), str):
            live[str(item["pane_id"])] = dict(item)
    # AgentInfo is the authoritative snapshot surface for agent_status; merge it over PaneInfo.
    for item in agents_value:
        if isinstance(item, Mapping) and isinstance(item.get("pane_id"), str):
            live_pane_id = str(item["pane_id"])
            live.setdefault(live_pane_id, {}).update(item)

    records: list[CatchUpRecord] = []
    updates: dict[str, tuple[str, str]] = {}
    for row_id, row in register_store.read_rows(root, run_id=run_id).items():
        pane_id = row.get("pane_id")
        if not isinstance(pane_id, str) or not pane_id:
            continue
        pane = live.get(pane_id)
        if pane is None:
            observed_state = "exited"
            observed_state_source = "inferred:snapshot_absence"
            revision = None
        elif row.get("agent") == "subscriber":
            # The subscriber is an ordinary foreground process, not a coding agent. Its liveness
            # is pane presence; herdr's coding-agent detector correctly reports this pane as
            # unknown and must not create an immediate false divergence.
            observed_state = "working"
            observed_state_source = "inferred:pane_presence"
            raw_revision = pane.get("revision")
            revision = (
                raw_revision
                if isinstance(raw_revision, int) and not isinstance(raw_revision, bool)
                else None
            )
        else:
            raw_state = pane.get("agent_status", "unknown")
            observed_state = raw_state if isinstance(raw_state, str) else "unknown"
            observed_state_source = "observed:session_snapshot"
            raw_revision = pane.get("revision")
            revision = (
                raw_revision
                if isinstance(raw_revision, int) and not isinstance(raw_revision, bool)
                else None
            )

        expected = row.get("expected_state")
        expected_state = expected if isinstance(expected, str) else None
        updates[row_id] = (observed_state, observed_state_source)
        artifact_path, artifact_exists = _artifact_presence(root, row.get("artifact_path"))
        records.append(
            CatchUpRecord(
                row_id=row_id,
                pane_id=pane_id,
                expected_state=expected_state,
                observed_state=observed_state,
                observed_state_source=observed_state_source,
                diverged=expected_state is not None and expected_state != observed_state,
                revision=revision,
                artifact_path=artifact_path,
                artifact_exists=artifact_exists,
            )
        )
    if updates:
        register_store.record_observed_states(root, updates, run_id=run_id)
    return records


class Subscriber:
    """Register-aware event dispatcher and reconnect catch-up owner."""

    def __init__(
        self,
        *,
        root: Path,
        run_id: str,
        row_id: str,
        pane_id: str,
        orchestrator_pane: str,
        subscriptions: Sequence[Mapping[str, Any]],
        client: herdr_events.HerdrEventClient,
        snapshot_reader: Callable[[], Mapping[str, Any]] | None = None,
        wake_sender: Callable[[str], None] | None = None,
        diagnostic_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.root = root
        self.run_id = run_id
        self.row_id = row_id
        self.pane_id = pane_id
        self.orchestrator_pane = orchestrator_pane
        self.subscriptions = [dict(item) for item in subscriptions]
        self.client = client
        self.snapshot_reader = snapshot_reader or self._read_snapshot
        self.wake_sender = wake_sender or self._send_wake
        self.diagnostic_sink = diagnostic_sink or self._print_diagnostic
        self._reported_once: set[tuple[str, str]] = set()
        self._sentinel_expectations = self._read_sentinel_expectations()

    def _read_sentinel_expectations(self) -> dict[str, list[dict[str, Any]]]:
        return _sentinel_expectations(self.subscriptions)

    @staticmethod
    def _print_diagnostic(payload: dict[str, Any]) -> None:
        print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)

    def _diagnostic(
        self,
        code: str,
        message: str,
        *,
        key: str = "",
        once: bool = False,
        **details: Any,
    ) -> None:
        identity = (code, key)
        if once and identity in self._reported_once:
            return
        if once:
            self._reported_once.add(identity)
        self.diagnostic_sink(
            {
                "type": "orchestrate_subscriber_diagnostic",
                "code": code,
                "message": message,
                **details,
            }
        )

    def _read_snapshot(self) -> Mapping[str, Any]:
        result = self.client.request("orchestrate-snapshot", "session.snapshot", {})
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, Mapping):
            raise herdr_events.ProtocolError(
                "session.snapshot response requires an object result.snapshot"
            )
        return snapshot

    def _send_wake(self, text: str) -> None:
        self.client.request(
            "orchestrate-wake",
            "agent.prompt",
            {"target": self.orchestrator_pane, "text": text},
        )

    def register_self(self) -> None:
        """Create or refresh the subscriber's ordinary tracked register row."""
        register_store.upsert_row(
            self.root,
            self.row_id,
            {
                "run_id": self.run_id,
                "agent": "subscriber",
                "pane_id": self.pane_id,
                "cwd": str(self.root),
                "phase": "working",
                "expected_state": "working",
                "observed_state": "working",
                "observed_state_source": "observed:subscriber_start",
            },
            run_id=self.run_id,
        )

    def run_catch_up(self) -> None:
        """Run the one bounded recovery pass associated with the current connection."""
        self._reported_once.clear()
        records = catch_up(self.root, self.snapshot_reader(), run_id=self.run_id)
        attention = [
            record for record in records if record.diverged or record.artifact_exists is False
        ]
        for record in attention:
            self._diagnostic(
                "catch_up_attention",
                "catch-up found lifecycle divergence or a missing run-bound artifact",
                row=asdict(record),
            )
        if attention:
            rows = ", ".join(record.row_id for record in attention)
            self.wake_sender(
                f"Orchestrate catch-up for run {self.run_id} needs attention in rows: {rows}. "
                "Re-read the run register before continuing."
            )

    def _registered_rows_for_event(
        self, event: herdr_events.HerdrEvent
    ) -> list[tuple[str, dict[str, Any]]]:
        pane_id = event.pane_id
        tab_id = event.data.get("tab_id")
        rows = register_store.read_rows(self.root, run_id=self.run_id)
        if pane_id is not None:
            return [(row_id, row) for row_id, row in rows.items() if row.get("pane_id") == pane_id]
        if isinstance(tab_id, str):
            return [(row_id, row) for row_id, row in rows.items() if row.get("tab_id") == tab_id]
        return []

    def _report_unregistered_event(self, event: herdr_events.HerdrEvent) -> None:
        pane_id = event.pane_id
        tab_id = event.data.get("tab_id")
        if pane_id is not None:
            self._diagnostic(
                "unregistered_pane",
                f"ignored event for unregistered pane_id {pane_id}",
                key=pane_id,
                once=True,
                pane_id=pane_id,
                event=event.name,
            )
            return
        if isinstance(tab_id, str):
            self._diagnostic(
                "unregistered_tab",
                f"ignored event for unregistered tab_id {tab_id}",
                key=tab_id,
                once=True,
                tab_id=tab_id,
                event=event.name,
            )
            return
        self._diagnostic(
            "event_without_handle",
            "received an event without a registered pane_id or tab_id",
            key=event.name,
            once=True,
            event=event.name,
        )

    def _sentinel_matches_active_subscription(
        self, pane_id: str, payload: Mapping[str, Any] | None
    ) -> bool:
        expected_values = self._sentinel_expectations.get(pane_id)
        if expected_values is None or payload is None:
            return False
        fields = ("run_id", "child_id", "purpose", "nonce")
        return any(
            all(payload.get(field) == expected.get(field) for field in fields)
            for expected in expected_values
        )

    def _handle_registered_event(
        self, event: herdr_events.HerdrEvent, row_id: str, row: Mapping[str, Any]
    ) -> bool:
        pane_id = event.pane_id
        if event.name == "pane.output_matched":
            if pane_id is None:
                return False
            line = event.matched_line or ""
            recorded = accounting.apply_output_match(self.root, row_id, line, run_id=self.run_id)
            payload = _sentinel_payload(line)
            if payload is None:
                if recorded is not None:
                    return True
                if pane_id in self._sentinel_expectations:
                    self._diagnostic(
                        "sentinel_mismatch",
                        "ignored output match whose sentinel is not the active run-child interaction",
                        pane_id=pane_id,
                        row_id=row_id,
                    )
                return False
            if not self._sentinel_matches_active_subscription(pane_id, payload):
                self._diagnostic(
                    "sentinel_mismatch",
                    "ignored output match whose sentinel is not the active run-child interaction",
                    pane_id=pane_id,
                    row_id=row_id,
                )
                return recorded is not None
            # Protocol 19's live pane.output_matched envelope reports read.revision=0 even when
            # pane.get reports a positive, advancing pane revision. They are not comparable
            # counters. Freshness comes from the complete run/child/purpose/nonce identity above;
            # producers enforce echo ordering through sentinel_assembly_instructions().
            register_store.upsert_row(
                self.root,
                row_id,
                {"last_event_at": herdr_events.unix_time()},
                run_id=self.run_id,
            )
            return True
        elif event.name in {"pane_exited", "pane_closed", "tab_closed"}:
            source_prefix = "inferred" if event.name == "tab_closed" else "observed"
            register_store.record_observed_state(
                self.root,
                row_id,
                "exited",
                source=f"{source_prefix}:{event.name}",
                run_id=self.run_id,
            )
            return True
        elif event.name == "pane_agent_status_changed":
            observed = event.data.get("agent_status")
            if isinstance(observed, str):
                register_store.record_observed_state(
                    self.root,
                    row_id,
                    observed,
                    source="observed:pane_agent_status_changed",
                    run_id=self.run_id,
                )
                return True
        return False

    def handle_event(self, event: herdr_events.HerdrEvent) -> None:
        """Update matching current-run rows before waking the orchestrator."""
        registered = self._registered_rows_for_event(event)
        if not registered:
            self._report_unregistered_event(event)
            return
        handled_rows: list[str] = []
        for row_id, row in registered:
            if self._handle_registered_event(event, row_id, row):
                handled_rows.append(row_id)
        if handled_rows:
            rows = ", ".join(handled_rows)
            self.wake_sender(
                f"Orchestrate event {event.name} for run {self.run_id}, rows {rows}. "
                "Re-read the run register before continuing."
            )

    def run(self) -> None:
        """Register this process, then hold and recover the subscription indefinitely."""
        self.register_self()
        try:
            self.client.run_forever(
                self.subscriptions,
                self.handle_event,
                self.run_catch_up,
                diagnostic=lambda message: self._diagnostic("socket", message),
            )
        finally:
            register_store.record_observed_state(
                self.root,
                self.row_id,
                "exited",
                source="observed:subscriber_stop",
                run_id=self.run_id,
            )


def _parse_subscriptions(raw: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"subscriptions must be valid JSON: {exc}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise argparse.ArgumentTypeError("subscriptions must be a JSON array of objects")
    subscriptions = [dict(item) for item in value]
    # Build once before process startup so malformed entries fail before the register says working.
    try:
        herdr_events.build_subscribe_request("orchestrate-validate", subscriptions)
        _sentinel_expectations(subscriptions)
    except herdr_events.SubscriptionError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return subscriptions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hold herdr events for one orchestrate run.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--row-id", required=True)
    parser.add_argument("--pane-id", required=True, help="pane hosting this subscriber process")
    parser.add_argument("--orchestrator-pane", required=True)
    parser.add_argument("--socket", type=Path, default=herdr_events.DEFAULT_SOCKET_PATH)
    parser.add_argument("--subscriptions-json", required=True, type=_parse_subscriptions)
    args = parser.parse_args(argv)
    root = register_store.canonical_work_location(args.root)
    try:
        register_store.assert_root_belongs_to_run(root, args.run_id, require_binding=False)
    except register_store.RegisterError as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 1

    subscriber = Subscriber(
        root=root,
        run_id=args.run_id,
        row_id=args.row_id,
        pane_id=args.pane_id,
        orchestrator_pane=args.orchestrator_pane,
        subscriptions=args.subscriptions_json,
        client=herdr_events.HerdrEventClient(args.socket),
    )
    try:
        subscriber.run()
    except (herdr_events.HerdrEventError, register_store.RegisterError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
