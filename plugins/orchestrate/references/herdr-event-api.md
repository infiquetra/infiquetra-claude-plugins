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

A successful subscription acknowledgement is:

```json
{"id":"orchestrate-subscribe-1","result":{"type":"subscription_started"}}
```

## Two event vocabularies

Subscription request types are dotted. Broadcast envelope names are underscored. They are separate
schema definitions and are not interchangeable:

| Subscribe with | Receive broadcast envelope |
|---|---|
| `tab.closed` | `tab_closed` |
| `pane.exited` | `pane_exited` |

`pane.output_matched`, `pane.agent_status_changed`, and `pane.scroll_changed` are the three dotted
subscription-event names. `pane.output_matched` carries `matched_line` and a full `read` value,
including the pane's current `revision`.

## Sentinel and revision guard

`make_sentinel()` creates a unique marker containing `run_id`, `child_id`, purpose, and nonce. The
subscriber verifies both identities, then reads the row's `dispatch_revision_baseline`. It honours
the match only when `read.revision` is greater than that baseline. A matching marker already present
in scrollback remains at or before the sampled revision and cannot wake the orchestrator.

## Reconnect catch-up

Protocol 19 has no cursor or replay. After the first accepted subscription and after every
reconnect, the subscriber sends `session.snapshot` on a short-lived socket and compares every
registered pane with the live `panes` and `agents` arrays. It writes the current `observed_state`,
reports disagreement with `expected_state`, and checks whether each declared `artifact_path`
exists. A missing pane is recorded as `exited`.

The subscriber itself is an ordinary foreground process, not a coding agent, so its row uses pane
presence as the live `working` signal instead of Herdr's coding-agent detector. The process records
its own `observed_state` as `exited` when its event loop terminates.

Catch-up runs once per connection boundary. It is not a scheduled reconciliation loop and does not
evaluate predicates; predicate evaluation is added only when its producer and consumer exist.

An event for an unregistered `pane_id` changes no row and produces one diagnostic for that pane.
A missing socket error names the socket path and directs the operator to `herdr status server`.
