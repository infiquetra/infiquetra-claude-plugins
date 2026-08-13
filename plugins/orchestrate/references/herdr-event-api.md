# herdr event API contract

The orchestrate subscriber uses herdr protocol 19 over the local Unix socket at
`~/.config/herdr/herdr.sock`. The committed test fixture at
`plugins/orchestrate/tests/fixtures/herdr-api-schema.json` is captured from the installed binary
with:

```bash
herdr api schema --output plugins/orchestrate/tests/fixtures/herdr-api-schema.json
```

## Subscription request

The client writes one newline-delimited JSON request and keeps the connection open:

```json
{
  "id": "orchestrate-subscribe-1",
  "method": "events.subscribe",
  "params": {
    "subscriptions": [
      {"type": "tab.closed"},
      {"type": "pane.exited"},
      {
        "type": "pane.output_matched",
        "pane_id": "w1:p2",
        "source": "recent_unwrapped",
        "match": {"type": "substring", "value": "ORCHESTRATE_SENTINEL {...}"}
      }
    ]
  }
}
```

`pane.output_matched` requires all four fields shown: `type`, `pane_id`, `source`, and `match`.
`match.type` is either `substring` or `regex`; both variants require a string `value`. The socket
API source is `recent_unwrapped` with an underscore. The `herdr pane read` command spells the same
source `recent-unwrapped` with a hyphen, which is not valid in the socket request.

That is the general Herdr protocol. The orchestrate subscriber deliberately accepts only substring
output matches containing a complete sentinel. Regex and ordinary-text matches must use the lower
level event client; passing either to the sentinel-bound subscriber is a startup error, never a
silently inactive subscription. Multiple complete sentinel subscriptions may target one pane.

A successful subscription acknowledgement is:

```json
{"id":"orchestrate-subscribe-1","result":{"type":"subscription_started"}}
```

## Two event vocabularies

Subscription request types are dotted. The 26 general broadcast-event names are underscored. They
are separate schema definitions and are not interchangeable:

| Subscribe with | Receive broadcast envelope |
|---|---|
| `tab.closed` | `tab_closed` |
| `pane.exited` | `pane_exited` |

The exception is the three `SubscriptionEventKind` broadcasts: `pane.output_matched`,
`pane.agent_status_changed`, and `pane.scroll_changed` remain dotted when received. In particular,
`pane.output_matched` carries `matched_line` and a full `read` value, including the pane's current
`revision`.

## Sentinel identity and prompt echo

`make_sentinel()` creates a unique marker containing `run_id`, `child_id`, purpose, and nonce. The
subscriber compares all four fields with the sentinel in the active pane subscription. A marker
from another run, child, purpose, or dispatch is rejected.

Do not compare `pane.output_matched`'s `read.revision` with the pane's revision. A live protocol-19
capture reports `read.revision=0` on a real content match while `pane get` reports a positive,
advancing counter. They are different counters. The captured envelope is committed beside the
schema fixture and validated through the decoder in tests.

The dispatch prompt must also avoid containing the complete sentinel, because terminal echo is
searchable immediately. The session lifecycle sends the marker prefix and JSON payload as separate
parts and asks the child to join them. This prevents prompt echo from matching. It does not prevent
a child from assembling the sentinel too early while reasoning; readiness proves the interaction,
not task completion or predicate success.

## Reconnect catch-up

Protocol 19 has no cursor or replay. After the first accepted subscription and after every
reconnect, the subscriber sends `session.snapshot` on a short-lived socket and compares every
registered pane with the live `panes` and `agents` arrays. It writes the current `observed_state`,
reports disagreement with `expected_state`, and checks whether each declared `artifact_path`
exists. `observed_state_source` records `observed:session_snapshot` for reported agent state and
`inferred:snapshot_absence` when a missing pane is recorded as `exited`.

Herdr returns the snapshot inside `result.snapshot`; `result.type` is `session_snapshot`. Tests
validate that complete response against the committed `success_response` schema and cross a real
Unix socket before catch-up consumes the inner snapshot.

The subscriber itself is an ordinary foreground process, not a coding agent, so its row uses pane
presence as the live `working` signal instead of Herdr's coding-agent detector. The process records
its own `observed_state` as `exited` when its event loop terminates.

Catch-up is attempted once per accepted connection boundary. A catch-up exception is reported but
does not close the accepted event stream, and reconnect limits count accepted connections rather
than successful catch-ups. It is not a scheduled reconciliation loop and does not evaluate
predicates; predicate evaluation is added only when its producer and consumer exist.

An event for an unregistered `pane_id` changes no row and produces one diagnostic for that pane.
A `tab_closed` event resolves registered rows through their `tab_id`; pane and tab terminal events
record `observed_state: exited` before waking. Direct pane terminal events use an `observed:` state
source, while a tab close uses `inferred:tab_closed`. Once-only diagnostics reset at each reconnect. A
missing socket on the first attempt fails the subscriber process non-zero, leaves its row at
`observed_state: exited`, names the socket path, and directs the operator to `herdr status server`.
