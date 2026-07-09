# Dispatch-adapter contract: transport-keyed adapters + bridge_receipt.v1

How a registry row's `transport` field selects an invocation-building adapter inside
`engine_dispatch.py`, how the generic HTTP bridge (`engine_bridge_http.py`) fits beside the
existing CLI adapters, and how every adapter — CLI or HTTP — proves it actually ran by emitting a
`bridge_receipt.v1`. This reference governs the *contract*; `plugins/saga/references/engine-dispatch.md`
covers dispatch policy, advisory evidence, trust standing, and override semantics.

## Transport is a closed-vocab registry field, not a bridge decision

Every registry row declares `transport: cli | http` (default `cli` — every pre-existing row is
unchanged). `_build_invocation` (`engine_dispatch.py`) branches on it:

- **`transport: cli`** — the existing codex/agy invocation builders, byte-identical to before this
  pair landed.
- **`transport: http`** — a single generic invocation builder driven entirely by the row's own
  data (`base_url`, `model`, `auth.mode`, `auth.key_env` when `auth.mode: bearer`, `effort`). There
  is zero per-provider branching inside the bridge itself — a new HTTP-transport provider is a new
  registry row, not a new code path (#387 AC1).

Add an OpenAI-compatible Chat Completions provider through
[`tools/add-engine.sh`](../../../docs/adding-a-provider.md). The scaffolder validates a compact JSON
specification, derives the generic bridge and receipt wiring, inserts only the probationary row, and
runs offline registry-to-dispatch conformance. Verify the base URL and model id against provider
documentation, and add an availability-gated smoke test when live proof is warranted. No
`engine_dispatch.py` change or provider-specific HTTP bridge is needed.

The offline conformance gate proves exact-key and capability-candidate reachability, real invocation
materialization, and receipt-emitter registration for every row. It deliberately does not call
provider preflight, read credentials, or perform network I/O.

## The generic HTTP bridge (`engine_bridge_http.py`)

- Stdlib `urllib.request` only (no new dependency) behind a `Runner`-shaped seam: `runner()` returns
  a callable with the same `dict -> dict` contract `dispatch()` already uses for every other engine
  (`{status, output, tokens, latency_seconds, receipt}`).
- Unit tests inject `FakeHttpRunner` (shared fixture, `tests/test_engine_bridge_http.py`) — the
  contract is fully testable without live network. A dead/no-op adapter (one that returns without
  invoking the runner) reds the contract test; a conformant one greens it (#387 AC2).
- A resolved bearer token exists **only** in the request headers at call time. It is never written
  into the invocation dict (which flows into run-ledger telemetry), a receipt, `AdvisoryEvidence`,
  or a log line. A receipt or error message may carry the env var *name* (`auth.key_env`), never
  its value.
- HTTP error / timeout / malformed-body responses map onto the existing `FAILURE_STATUSES`
  vocabulary with a downgrade note — never a fabricated `ok` result.

## `bridge_receipt.v1` — proof of execution

Canonical home: `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py` (fleet-commons — the
established cross-plugin shared-primitive mechanism, `{#fleet-commons-mechanism-463}`). Vendored
byte-identical into `plugins/agy/scripts/fleet_commons_shim.py`, covered by the existing
vendored-copy drift guard. A cross-plugin import from saga into fleet-core/agy at runtime would
break at install time (`{#marketplace-install-layout-no-import-path}`) — that is why the vendored
shim exists rather than a direct import.

Schema:

```python
{
    "schema": "bridge_receipt.v1",
    "engine_id": str,
    "variant": str,
    "transport": "cli" | "http",
    "wall_time_s": float,
    "bytes_produced": int,
    "runner": {...},  # transport-discriminated, see below
}
```

`runner` is transport-discriminated:

- `transport: cli` → `{"pid": int, "argv": list[str], "exit_code": int}`
- `transport: http` → `{"url": str, "status_code": int, "model": str}`

`emit_receipt(...)` stamps `schema`/version itself, so a caller cannot mislabel a receipt.
`validate_receipt(dict) -> list[str]` returns typed errors (empty list = valid).

## Receipt gating: `RAN_AS_REQUESTED` vs `UNPROVEN`

`AdvisoryEvidence` gains an additive `runner_receipt: dict | None = None` field (frozen dataclass —
no signature break for any existing caller). `dispatch()` populates it from the runner result's
`receipt` key. `build_dispatch_manifest` (`engine_dispatch.py`) then assigns:

- `Disposition.RAN_AS_REQUESTED` — only when a schema-valid receipt is present.
- `Disposition.UNPROVEN` (new) — ok-looking evidence with no receipt, or a receipt that fails
  `validate_receipt`. Receipt-less success is never silently upgraded to "proven."
- `Disposition.FELL_BACK_TO_CLAUDE` — unchanged; a halted/fallback path carries no receipt because
  there is nothing to prove.

## Never a gatekeeper (R6/#387 AC6, restated for the bridge)

No code path in the bridge table lets an engine result set or override a gate/verdict field. A
runner result carrying a gate-shaped key (`verdict`, `gate_status`, `adjudicated`) is **structurally
rejected** — `dispatch()` raises `DispatchError` — not merely policy-rejected. This is the same
binding decision as the CLI paths (`{#external-engines-never-gatekeepers}` #283), now enforced
identically across both transports.

## `receipt_emitter` is a required registry key

Every row — CLI or HTTP — must declare `receipt_emitter`. The registry loader raises `RegistryError`
naming the row if it is missing; a row without receipt wiring cannot be dispatched to (#383 AC3). A
committed drift guard (`tests/test_bridge_receipt_drift.py`) enumerates every registry
`receipt_emitter` value and proves each in-repo emitter actually emits through the shared path — a
test-double bridge that skips the emit call reds the guard. Not-yet-landed emitters are tracked
explicitly (`PENDING_EMITTERS = {"codex-bridge": "#476"}`); the guard reds if a pending entry's
issue closes while the entry is still marked pending, so a shipped bridge can never silently skip
wiring.

## What this pair does not change

- team-execution's `ENGINE_INTENTS` resolution (by `<engine-key>` / `cap:<capability>`,
  `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`) is
  untouched — new HTTP-transport rows join resolution automatically, no team-execution code change.
- The pre-existing CLI dispatch policy in `engine-dispatch.md` (Codex/agy wrapper contracts,
  override semantics, provenance/downgrade notes) is unchanged.
- Local/keyless Ollama (`localhost:11434`) is explicitly deferred to a follow-up row; the first
  HTTP-transport rows are cloud-first (Ollama Cloud, DeepSeek), both bearer-auth from an env var.
