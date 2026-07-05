---
title: Remote gate approval over the fleet's own channel (redis-channel/Discord)
type: feat
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/379
---

# Remote gate approval over the fleet's own channel (redis-channel/Discord)

Phase 0 item 8. Give a durable lifecycle approval gate a second, unattended delivery transport: the
fleet's own redis-channel/Discord bridge. When a gate fires while the terminal is unattended, its
prompt travels over the channel and the operator's reply becomes the durable approval — recording
**who answered** and **over which transport** — with sender authorization **deferred to the
transport's existing access policy** (option A, Jeff 2026-07-05), never a new allowlist.

## Problem Frame

Today an `AskUserQuestion`-shaped gate's only delivery surface is the interactive terminal;
`AskUserQuestion` cannot even be called in a redis-channel session (the per-skill inline-choice
fallback at `operator-choice.md:169-174` still needs the operator at the keyboard). A gate that fires
while the session is unattended cannot reach the operator at all. The transport for the round-trip
already exists (redis-channel `reply()`/inbound + Discord's DM path); this capability wires an
existing gate to it. Reach, not new timeout semantics, is the gap (`{#operator-choice-framework}`
binds this to *transport, not a new gate mechanism*).

## Requirements

- **R1.** When an `/outcome` R20 approval gate holds a frontier AND a redis-channel session is
  connected, the gate's prompt + lettered options are emitted over the channel (via the redis
  producer / `reply()` path). Producing the outbound is asserted in the run's gate-notify path.
- **R2.** An operator's channel reply that answers a pending gate is captured as the gate's durable
  approval, with `answerer` and `transport` recorded on the gate record
  (`approvals/r{rev}.json`). The polling run observes the answer and proceeds.
- **R3.** Sender authorization is **deferred to the transport's existing access policy** — Discord
  pre-filters inbound to `allowFrom` (`server.ts:236-294`); redis-channel defers to its router. The
  answer-capture path does **not** reimplement an allowlist and only resolves a **specific pending
  gate id**; a reply that matches no pending gate — or that a caller cannot attribute to an
  access-approved sender — is **not accepted** and the rejection is surfaced (AC4: no injection-driven
  approval).
- **R4.** No-answer parity: the channel transport is **purely additive**. An unanswered gate follows
  its existing HOLD behavior unchanged (an `/outcome` gate holds leaves in `gated` until an explicit
  `approve`; no new timeout, no auto-proceed-on-silence).
- **R5.** Disconnected fallback: with no channel session connected, gate behavior is exactly today's
  interactive/inline — no behavior change for sessions that never use this transport.
- **R6.** The gate-transport contract is documented: `operator-choice.md` (channel-delivery contract
  alongside the inline-choice fallback) + `redis-channel/PROTOCOL.md` (the gate notify/answer message
  convention).
- **R7.** Release surfaces for every touched plugin (saga + redis-channel): plugin.json bump,
  marketplace regen, per-plugin CHANGELOG, version-literal drift-guard tests.

## Key Technical Decisions

**KTD1 — v1 wires the `/outcome` R20 gate (the only durable-record gate); the per-skill
`AskUserQuestion` gates are contract-only.** Grounding: the `/outcome` `dispatch_gate` has a real
durable answer record — `approve_frontier` writes write-once `approvals/r{rev}.json`
(`outcome_decompose.py:337-350`). The per-skill gates (`/work` merge-confirmation, `/plan`, etc.) are
prose conventions with no durable structured record (only saga `gate_verdicts` strings), and building
one would be a *new gate mechanism* that `{#operator-choice-framework}` forbids. So v1 delivers the
concrete durable path (`/outcome`) and **documents** the channel contract for the AskUserQuestion
gates. (A durable per-skill gate record is deferred follow-up work, not this issue.)

**KTD2 — defer sender-auth to the transport; never reimplement an allowlist (option A).** Discord's
`gate()` (`server.ts:236-294`) drops non-`allowFrom` senders **before the session ever sees them**
(`handleInbound` returns on `drop`, `:813`); redis-channel has no in-plugin allowlist and defers to
its router (`redis_consumer.py:159-194` delivers every inbound unconditionally). So AC4's
"access-policy-approved sender" is enforced **upstream of the session** on both transports. The
answer-capture path records the (already-authorized) `answerer`/`transport` as provenance and resolves
only a specific pending gate id — it does not, and cannot, re-authorize a sender. This mirrors the
existing scoped permission-reply pattern (Discord `PERMISSION_REPLY_RE` `server.ts:79`; redis
`permission_request`/`permission_verdict` `protocol.py:113-138`) where authority derives from the
already-passed gate, never from a self-asserted field in the message body.

**KTD3 — provenance extends the existing write-once `approvals/rN.json` dict, not a new schema.**
Add `answerer` + `transport` keys to the dict `approve_frontier` already writes
(`outcome_decompose.py:347-349`). `frontier_approved` only checks file existence (`:353-355`), so
extra keys are backward-compatible; a net-new dataclass would be over-engineering.

**KTD4 — render the gate via the existing `reply()` inline-choice transport + a gate-id correlation;
do NOT add a new permission-style stream pair.** `{#operator-choice-framework}` constrains this to a
transport for an existing gate. The gate renders as an inline lettered-choice `reply()` message
(the established channel fallback shape) carrying a short **gate id** (the `outcome_id`@`spec_revision`
the approval keys on). The answer is captured by matching an inbound reply back to that pending gate
id. This adds no new Redis stream and no new protocol verb — only a documented message convention.

**KTD5 — the gate logic lives in `saga`; `redis-channel` stays router-agnostic.** The issue's
indicative `notifier.py` change is reconsidered: redis-channel is a generic bridge that must not learn
about saga gates ([[feedback_redis_channel_router_agnostic]]). The notify-compose and answer-capture
logic live in a new saga module using redis-channel's **generic** `reply()`/inbound transport. The
only redis-channel change is a PROTOCOL.md note documenting the (transport-agnostic) gate message
convention. Net: redis-channel likely takes a **docs-only** change; the code lands in saga.

**KTD6 — inbound answer recognition is contract + a CLI affordance, not a background parser.** A
channel reply arrives as a `<channel …>` **notification to the session** (Claude), not to a Python
daemon. So the operator-choice contract instructs the session to recognize a gate-answer reply and
run `outcome approve --answerer <sender> --transport <src>`; a small pure **parse helper** turns a
lettered reply + gate id into the approve call's arguments (unit-testable without a live channel).
This keeps operator-choice "doc-only, CLI-driven" per `{#operator-choice-framework}`.

## Implementation Units

### U1. Gate-answer provenance on the durable record

Extend `approve_frontier(store, spec, at="", *, answerer=None, transport=None)`
(`outcome_decompose.py`) to write `answerer`/`transport` into `approvals/r{rev}.json` when provided;
`frontier_approved` unchanged (existence check). Thread `--answerer` / `--transport` through the
`outcome approve` CLI subcommand (`outcome.py:1184-1187`).

**Test scenarios** (`tests/test_outcome_gate_transport.py`): approve with answerer/transport →
record round-trips both fields; approve without them → record unchanged from today (backward-compat);
`frontier_approved` still true regardless.

### U2. Channel gate-notify composer (saga)

New saga module `plugins/saga/scripts/outcome_gate_transport.py`: a pure `compose_gate_notice(spec,
spec_revision, gated_subplots) -> str` that renders the pending-approval prompt + inline lettered
choices + the gate id, and a thin `emit_gate_notice(session_name, chat_id, text, *, producer=…)` that
publishes it over redis-channel's generic transport (`publish_outbound` / the `reply` shape), injected
for tests. Only emit when a channel session is connected (detected via the existing session registry);
no-op otherwise (R5).

**Test scenarios:** compose produces the gate id + lettered choices deterministically; emit calls the
injected producer once when "connected"; emit is a no-op when disconnected.

### U3. Gate-answer parse + access deferral (saga)

In `outcome_gate_transport.py`: `parse_gate_answer(inbound, pending_gate_ids) -> GateAnswer | None`
— match an inbound channel reply (`text`, `chat_id`, `user_id`/`username`, `source`) to a **pending
gate id**; return a `GateAnswer(gate_id, verdict, answerer, transport)` when it resolves a real
pending gate, else `None` (reject: no pending match → not accepted, surfaced). Authority is the
transport's (KTD2): the parser records `answerer` from the already-authorized inbound and never
consults an allowlist. The verdict maps the lettered/`y|n` reply to approve/reject.

**Test scenarios:** a valid reply matching a pending gate id → `GateAnswer` with answerer/transport
populated; a reply matching no pending gate → `None` (rejected, no answer written); a malformed reply
→ `None`; the `answerer`/`transport` come from the inbound fields, not the body text.

### U4. No-answer parity + disconnected fallback (integration)

Wire U2/U3 as an **additive** layer around the existing `/outcome` gate: an unanswered gate still
holds in `gated` (unchanged); a disconnected session takes no channel path. Add an integration test
asserting the gate's hold behavior is byte-identical with the channel transport enabled-but-unanswered
vs. disabled, and that a disconnected session never emits.

**Test scenarios:** enabled-but-unanswered gate == disabled gate (same `gated`/quiescence); disconnected
→ no emit, no record change; the whole path is opt-in on session-connected.

### U5. Documented gate-transport contract

`operator-choice.md` — a "channel-transport gate delivery" subsection alongside the inline-choice
fallback: how a gate renders via `reply()` (the gate id + lettered choices), how the session
recognizes a gate-answer reply and runs `outcome approve --answerer --transport`, and the KTD2
access-deferral / no-self-escalation rule. `redis-channel/PROTOCOL.md` — a note documenting the
(transport-agnostic) gate notify/answer message convention. **Test expectation: none** (docs);
covered by the drift-guard + the code tests above.

### U6. Release surfaces + writeback

saga plugin.json bump + CHANGELOG; redis-channel plugin.json bump + CHANGELOG (docs-only PROTOCOL
change still versions the contract); regen `marketplace.json`; version-literal drift-guard tests;
DECISIONS `{#remote-gate-approval-379}` (KTD1-KTD6); execution-order row 8 `[x]`; work-session. **Test
expectation: none** (release metadata; drift-guard tests assert the versions).

## Scope Boundaries

**In:** `/outcome` R20 gate delivered + answered over redis-channel/Discord with answerer/transport
provenance; access deferred to the transport; no-answer parity; disconnected fallback; documented
contract; release surfaces.

**Out (true non-goals):**
- New no-answer/timeout semantics (additive reach only).
- A new execution backend, fan-out kind, or external-engine gatekeeper (`{#operator-choice-framework}`,
  `{#external-engines-never-gatekeepers}` — Claude stays verifier-of-record).
- Changing/bypassing the redis-channel/Discord access policy — read from it, never grant authority.
- A generic multi-transport notification bus for non-gate events.
- Voice-transport gates (TTS constraints make lettered choices awkward; text/dm/channel/thread only).

**Deferred to Follow-Up Work:**
- A durable structured answer record for the **per-skill** `AskUserQuestion` gates (`/work` merge,
  `/plan`, …) — v1 documents the contract for them but only wires the `/outcome` durable path (KTD1).
- `react()`/button-equivalent answers where the transport supports it (v1 = lettered text reply;
  the Discord button handler `server.ts:744-800` is the future seam).

## Definition of Done

- An `/outcome` approval gate, with a connected redis-channel session, emits its prompt over the
  channel; an allowlisted operator reply is captured as the durable approval with `answerer`/`transport`
  recorded; a non-matching/unauthorized reply is rejected and surfaced; an unanswered gate holds
  exactly as today; a disconnected session is unchanged.
- Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy
  plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`; release surfaces in
  lockstep (saga + redis-channel).
