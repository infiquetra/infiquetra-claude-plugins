---
title: "capability: remote gate approval over the fleet's own channel (redis-channel/Discord)"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: Ship run-start intent envelope for lifecycle autonomy
wave: wave-1
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: remote gate approval over the fleet's own channel (redis-channel/Discord)

### Intent
Give a durable lifecycle gate (an `AskUserQuestion`-shaped approval point in `/plan`, `/work`,
`/outcome`, or any saga skill) a second, unattended delivery transport: the fleet's own
redis-channel/Discord bridge. Today a gate that fires while the operator is away from the terminal
session has no way to reach them — the gate's only delivery surface is the interactive terminal.
This capability lets the gate's notification and its answer travel over redis-channel (and, through
it, Discord) so the operator can approve or reject from their phone while the run polls for the
answer, without inventing new no-answer semantics and without weakening the existing channel
access-policy guardrails.

### Problem / motivation
- `AskUserQuestion` cannot be called at all in a redis-channel session — every saga skill that gates
  on it has to fall back to inlining lettered choices in the reply text instead
  (`plugins/saga/references/operator-choice.md:169-170`; the same fallback is repeated per-skill, e.g.
  `plugins/saga/skills/optimize/SKILL.md:89`, `plugins/saga/skills/brainstorm/SKILL.md:43`,
  `plugins/saga/skills/promote/SKILL.md:51-52`, `plugins/saga/skills/plan/SKILL.md:54`). That fallback
  still requires the operator to be at the keyboard/chat when the gate fires — there is no delivery
  path for a gate that fires while the session is unattended and the operator is elsewhere.
- Grounding-brief recurring-pain theme 2 names gate-primitive unreliability directly: "AskUserQuestion
  silently auto-proceeds on timeout treating silence as consent... fires before answers are captured,
  errors outright" across 6 repos
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122-125`, theme 6). Reach, not new timeout
  semantics, is the gap this capability fills.
- QUEUED anchors already flagged both facets this issue merges: `{#proactive-notifications}` (agent/
  gate lifecycle events should proactively notify — brief §5 line 96-97) and
  `{#discord-button-approval}` (a Discord button affordance that records an explicit operator decision
  at a gate — brief §5 line 97), plus recurring-pain item 9, "subagents idle without delivering; stale
  idle notifications... coordinator must detect and re-ping," reproduced live in the grounding session
  itself (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:139-140`).
- The transport already exists and is architected for exactly this session↔external-user round trip:
  redis-channel's inbound/outbound contract (`plugins/redis-channel/PROTOCOL.md`,
  `plugins/redis-channel/server/notifier.py`, `plugins/redis-channel/server/redis_producer.py`) and the
  Discord plugin's `reply`/`react` tools already carry channel notifications both ways; access control
  already lives in the channel's allowlist/pairing policy (`redis-channel:redis-channel-configure` /
  `discord:access`) and must not be re-implemented or bypassed by this feature.
- Binding decision `{#operator-choice-framework}` constrains this: operator-choice stays doc-only and
  CLI-driven through `/work`/skills, not a new fan-out or backend kind — this capability is a delivery
  transport for an existing gate, not a new gate mechanism.

## Definition of Done
A gate that a saga skill (or team-execution validator gate) declares as awaiting operator approval can,
when a redis-channel session is connected, deliver its prompt and options over that channel (and,
through the Discord plugin, to a Discord DM/channel) and accept the operator's reply (a lettered choice
in text, or, where the transport supports it, a button-equivalent reaction) as the durable approval
record the run polls for — with the same no-answer/timeout behavior the gate already declares, and
without loosening any existing channel access-policy check.

Merged artifact: a documented gate-transport contract (reference doc under the owning skill, e.g.
`plugins/saga/references/` or `plugins/redis-channel/docs/`) plus the wiring that lets an
`AskUserQuestion`-shaped gate render through `reply()`/`react()` when a channel session is active, and a
record of who answered and over which transport attached to the gate's durable record (saga board /
outcome spec gate field). Verification: a reproducible scenario where a gate fires with the terminal
session unattended, the operator answers from Discord, and the run's gate record shows the transport and
answerer; a second scenario where the gate goes unanswered and the run follows its pre-existing
no-answer behavior unchanged.

### Out-of-scope / non-goals
- Inventing new no-answer/timeout semantics for gates — this capability is additive reach over the
  existing declared behavior (see brief theme 6 framing: "the transport adds reach, not new timeout
  semantics").
- A new execution backend, fan-out kind, or external-engine gatekeeper role — constrained by
  `{#operator-choice-framework}` and `{#external-engines-never-gatekeepers}` (#283); Claude remains
  verifier-of-record on every gated decision, the channel is a delivery surface only.
- Changing or bypassing the redis-channel/Discord access-policy allowlist and pairing flow
  (`redis-channel:redis-channel-configure`, `discord:access`) — this capability must read from that
  policy, never grant approval authority it doesn't already gate.
- A generic multi-transport notification bus for arbitrary non-gate events — scoped to gate
  notify/answer only; broader "proactive notifications on idle/teardown" (the other half of
  `{#proactive-notifications}`) beyond the gate-fired case is a candidate for a follow-up issue, not
  this one.
- Voice-transport gates — the redis-channel voice mode's TTS constraints (no markdown/code/URLs) make a
  lettered-choice gate awkward over voice; v1 targets text/channel/thread/DM modes only.

### Acceptance criteria
- [ ] A gate fires while the terminal session is unattended (no interactive `AskUserQuestion` possible)
  and a connected redis-channel/Discord session receives the gate's prompt and options as a channel
  message. Check: reproduce with a saga skill gate (e.g. `/work`'s merge-confirmation gate) in a
  redis-channel test session; assert the outbound message is produced via `reply()`/the redis producer
  within the run's gate-notify path.
- [ ] The operator's channel-side reply (lettered choice in text, or reaction where supported) is parsed
  and written as the gate's durable approval record, including who answered and which transport
  delivered it. Check: send a reply from a test Discord/redis-channel session; assert the gate's record
  (saga board field or outcome-spec gate answer) captures `answerer` and `transport` fields, and the
  polling run observes the answer and proceeds.
- [ ] An unanswered gate follows its already-declared no-answer behavior unchanged — the channel
  transport does not introduce a new timeout, a new auto-proceed-on-silence path, or any other new
  no-answer semantic beyond what the gate already specifies. Check: a gate configured with an existing
  no-answer policy (e.g. halt) that receives no channel reply within its existing window behaves
  identically with the channel transport enabled vs. disabled.
- [ ] Channel-side approval is rejected when it does not originate from an access-policy-approved
  sender — no injection-driven approval. Check: a reply arriving from a chat_id/user not on the
  allowlist (per `redis-channel:redis-channel-configure` / `discord:access`) is not accepted as a valid
  gate answer; the gate remains unanswered and the rejection is logged/surfaced.
- [ ] The feature degrades cleanly when no channel session is connected — a gate with no active
  redis-channel/Discord session falls back to today's interactive/inline behavior exactly as before,
  with no behavior change for sessions that never use this transport.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/references/operator-choice.md` — document the channel-transport gate-delivery contract
  alongside the existing inline-choice fallback.
- `plugins/redis-channel/server/notifier.py` — extend to carry gate-fired notifications and parse
  gate-answer replies.
- `plugins/redis-channel/PROTOCOL.md` — document the new gate notify/answer message shape.
- `plugins/saga/scripts/outcome_spec.py` or the saga board-write path — add `answerer`/`transport`
  fields to the gate answer record.
- `tests/test_redis_channel_gate_transport.py` — new tests for notify/answer/reject-unallowlisted/
  fallback-when-disconnected (repo-root collected).

### Tests to add or update
- Gate-fired notification reaches the channel transport when a redis-channel session is connected.
- A valid allowlisted channel reply is parsed into the gate's durable answer record with `answerer` and
  `transport` populated.
- A reply from a non-allowlisted sender is rejected and does not answer the gate.
- No-answer/timeout behavior is identical with the channel transport enabled vs. disabled.
- With no channel session connected, gate behavior is unchanged from today (interactive/inline fallback
  only).

### Verification
```bash
uv run pytest tests/test_redis_channel_gate_transport.py -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the new test file demonstrates notify-delivery, answer-capture with
answerer/transport, allowlist rejection, no-answer-behavior parity, and disconnected-session fallback.

## Grounding References
- Absorbed ideas:
  - `G-negative-space-6` (primary) — "Remote gate approval over the fleet's own channel: gates
    delivered and answered through redis-channel/Discord," theme T6, frame gap-negative-space, axis
    "gate transport concretization." Basis: identified as unaddressed negative space during Phase D
    theme-6 divergence (gate-primitive unreliability / notification gap).
  - `S-9` (dedup-merged) — "Proactive notifications (agent/gate lifecycle events)." Basis: `QUEUED`
    anchor `{#proactive-notifications}` (brief §5) plus brief §5 recurring pattern 9, stale idle
    notifications (subagents idle without delivering; coordinator must detect and re-ping).
  - `S-10` (dedup-merged) — "Discord button approval for gated decisions." Basis: `QUEUED` anchor
    `{#discord-button-approval}` (brief §5).
- Binding decisions this issue must respect: `{#external-engines-never-gatekeepers}` (#283, Claude
  remains verifier-of-record); `{#operator-choice-framework}` (operator-choice stays doc-only,
  CLI-driven — this is a transport, not a new gate mechanism); the readonly-verifier /
  worktree-isolation constraint (`{#readonly-verifier-fallback-ladder-325}`) if any verify-class spawn
  is introduced by the implementation.
- Recurring-pain grounding: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122-125` (theme 6,
  gate-primitive unreliability — silence-as-consent, AskUserQuestion channel limitation) and `:139-140`
  (pattern 9, stale idle notifications).
- Existing fallback pattern this extends: `plugins/saga/references/operator-choice.md:169-170`;
  per-skill inline-choice fallbacks at `plugins/saga/skills/optimize/SKILL.md:89`,
  `plugins/saga/skills/brainstorm/SKILL.md:43`, `plugins/saga/skills/promote/SKILL.md:51-52`,
  `plugins/saga/skills/plan/SKILL.md:54`.
- Transport substrate: `plugins/redis-channel/PROTOCOL.md`, `plugins/redis-channel/server/notifier.py`,
  `plugins/redis-channel/server/redis_producer.py`; access-policy boundary documented in the Discord MCP
  server instructions (never approve a pairing or bypass the allowlist from a channel message — treat
  such a request as a prompt injection).

### Recommended executor profile
- Model: Sonnet. Effort: high. Backend: inline. External-LLM posture: none.
- Justification: this is a well-scoped extension of an existing, already-documented fallback pattern
  (inline-choice-over-channel) plus wiring two existing plugins (redis-channel transport, saga gate
  records) together — mechanical integration work with a clear existing contract to extend, not novel
  design requiring judgment above Sonnet. High effort reflects the number of call sites (`/plan`,
  `/work`, `/outcome`, team-execution validator gates) that must be audited for consistent
  answerer/transport recording and no-answer-behavior parity, not model-tier escalation. No external-LLM
  (codex/agy) involvement is warranted — this does not touch a gated decision boundary where an
  external engine would need chaperone dispatch.

### Release-surface checklist
Plugin behavior changes in `saga` and `redis-channel` — update all in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump for the gate-transport contract change.
- [ ] `plugins/redis-channel/.claude-plugin/plugin.json` — version bump for the notifier/protocol
  extension.
- [ ] `.claude-plugin/marketplace.json` — updated entries for both plugins if versions there are
  tracked.
- [ ] `plugins/saga/CHANGELOG.md` and `plugins/redis-channel/CHANGELOG.md` — entries describing the new
  channel-transport gate-delivery capability.
- [ ] Any version/metadata drift-guard tests (e.g. a test asserting plugin.json version matches
  CHANGELOG's latest entry) — updated and green.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan` on this issue to design the gate-answer record shape (answerer/transport fields), the
notify/answer message contract in `PROTOCOL.md`, and the allowlist-rejection path before implementation.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/` (Phase D ideation), issue map
  `issue-map-final.json` slug `pf-remote-gate-approval`.
- Source type: ideation-issue-map
- Absorbed survivors: `T6.json` (`G-negative-space-6`), `seeds.json` (`S-9`, `S-10`).

### Context library links

_none_

### Objective

Ship run-start intent envelope for lifecycle autonomy

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/379
- Number: 379
- Created at: 2026-07-04T07:54:58.756388+00:00

