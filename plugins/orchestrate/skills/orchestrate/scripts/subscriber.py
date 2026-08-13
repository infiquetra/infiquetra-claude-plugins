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


def output_match_subscription(
    pane_id: str,
    sentinel: str,
    *,
    match_type: str = "substring",
) -> dict[str, Any]:
    """Build herdr's four-field output subscription using the socket API's source spelling."""
    subscription = {
        "type": "pane.output_matched",
        "pane_id": pane_id,
        "source": "recent_unwrapped",
        "match": {"type": match_type, "value": sentinel},
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
    run_id: str | None = None,
) -> list[CatchUpRecord]:
    """Re-read every registered pane from one live snapshot and record observed state.

    A missing pane is recorded as ``exited``. A status mismatch remains a mismatch: catch-up does
    not promote lifecycle phases or trust detector status as a completion verdict.
    """
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
    for row_id, row in register_store.read_rows(root, run_id=run_id).items():
        pane_id = row.get("pane_id")
        if not isinstance(pane_id, str) or not pane_id:
            continue
        pane = live.get(pane_id)
        if pane is None:
            observed_state = "exited"
            revision = None
        elif row.get("agent") == "subscriber":
            # The subscriber is an ordinary foreground process, not a coding agent. Its liveness
            # is pane presence; herdr's coding-agent detector correctly reports this pane as
            # unknown and must not create an immediate false divergence.
            observed_state = "working"
            raw_revision = pane.get("revision")
            revision = (
                raw_revision
                if isinstance(raw_revision, int) and not isinstance(raw_revision, bool)
                else None
            )
        else:
            raw_state = pane.get("agent_status", "unknown")
            observed_state = raw_state if isinstance(raw_state, str) else "unknown"
            raw_revision = pane.get("revision")
            revision = (
                raw_revision
                if isinstance(raw_revision, int) and not isinstance(raw_revision, bool)
                else None
            )

        expected = row.get("expected_state")
        expected_state = expected if isinstance(expected, str) else None
        register_store.upsert_row(root, row_id, {"observed_state": observed_state})
        artifact_path, artifact_exists = _artifact_presence(root, row.get("artifact_path"))
        records.append(
            CatchUpRecord(
                row_id=row_id,
                pane_id=pane_id,
                expected_state=expected_state,
                observed_state=observed_state,
                diverged=expected_state is not None and expected_state != observed_state,
                revision=revision,
                artifact_path=artifact_path,
                artifact_exists=artifact_exists,
            )
        )
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
        return self.client.request("orchestrate-snapshot", "session.snapshot", {})

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
            },
        )

    def run_catch_up(self) -> None:
        """Run the one bounded recovery pass associated with the current connection."""
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

    def _registered_row_for_pane(self, pane_id: str) -> tuple[str, dict[str, Any]] | None:
        for row_id, row in register_store.read_rows(self.root, run_id=self.run_id).items():
            if row.get("pane_id") == pane_id:
                return row_id, row
        return None

    def handle_event(self, event: herdr_events.HerdrEvent) -> None:
        """Update the matching row and wake only for registered, current-run pane events."""
        pane_id = event.pane_id
        if pane_id is None:
            self._diagnostic(
                "event_without_pane",
                "received an event without a pane_id",
                key=event.name,
                once=True,
                event=event.name,
            )
            return
        registered = self._registered_row_for_pane(pane_id)
        if registered is None:
            self._diagnostic(
                "unregistered_pane",
                f"ignored event for unregistered pane_id {pane_id}",
                key=pane_id,
                once=True,
                pane_id=pane_id,
                event=event.name,
            )
            return
        row_id, row = registered

        if event.name == "pane.output_matched":
            payload = _sentinel_payload(event.matched_line or "")
            if (
                payload is None
                or payload.get("run_id") != self.run_id
                or payload.get("child_id") != row_id
            ):
                self._diagnostic(
                    "sentinel_mismatch",
                    "ignored output match whose sentinel does not identify this run and child",
                    pane_id=pane_id,
                    row_id=row_id,
                )
                return
            baseline = row.get("dispatch_revision_baseline")
            if not isinstance(baseline, int) or isinstance(baseline, bool):
                self._diagnostic(
                    "missing_revision_baseline",
                    "ignored output match because the row has no dispatch revision baseline",
                    pane_id=pane_id,
                    row_id=row_id,
                )
                return
            if event.revision is None or event.revision <= baseline:
                self._diagnostic(
                    "stale_output_match",
                    "ignored output match at or before the pre-dispatch revision baseline",
                    pane_id=pane_id,
                    row_id=row_id,
                    baseline=baseline,
                    revision=event.revision,
                )
                return
            register_store.upsert_row(
                self.root, row_id, {"last_event_at": herdr_events.unix_time()}
            )
        elif event.name == "pane_exited":
            register_store.upsert_row(self.root, row_id, {"observed_state": "exited"})
        elif event.name == "pane_agent_status_changed":
            observed = event.data.get("agent_status")
            if isinstance(observed, str):
                register_store.upsert_row(self.root, row_id, {"observed_state": observed})

        self.wake_sender(
            f"Orchestrate event {event.name} for run {self.run_id}, row {row_id}. "
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
            register_store.upsert_row(self.root, self.row_id, {"observed_state": "exited"})


def _parse_subscriptions(raw: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"subscriptions must be valid JSON: {exc}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise argparse.ArgumentTypeError("subscriptions must be a JSON array of objects")
    subscriptions = [dict(item) for item in value]
    # Build once before process startup so malformed entries fail before the register says working.
    herdr_events.build_subscribe_request("orchestrate-validate", subscriptions)
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

    subscriber = Subscriber(
        root=args.root,
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
