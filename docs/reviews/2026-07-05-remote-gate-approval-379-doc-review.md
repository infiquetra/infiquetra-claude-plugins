---
title: Doc-review — Remote gate approval over the fleet's own channel (#379)
type: doc-review
date: 2026-07-05
target: docs/plans/2026-07-05-remote-gate-approval-379-plan.md
reviewed_revision: working tree (base d32e5a8; safe fixes applied in place, uncommitted at review time)
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/379
linked_plan: docs/plans/2026-07-05-remote-gate-approval-379-plan.md
work_session: (pending — created by /work)
blocked: false
---

# Doc-review: #379 remote gate approval

**Readiness verdict: READY to drive implementation** (with the applied fixes below). No P0; the one
P1 was a real Discord-coverage gap in the delivery mechanism and is resolved in place; residuals are
P3 polish. The security core — a channel prompt-injection must not forge an approval — was verified
sound against the real code on both transports.

## 1. Applied fixes (in place)

| # | Pri | Fix | Evidence |
|---|-----|-----|----------|
| 1 | P1 | **U2 emit reframed to session-driven for both transports.** As written, U2 specified a Python `emit_gate_notice`→`publish_outbound` emit, which is redis-channel-only and cannot run in a bare `outcome advance` CLI gate-hold (no Redis client / `chat_id` / `session_name` in that context). Discord — in scope per the title/R1/DoD — has **no** Python-callable producer at all. Reframed so `compose_gate_notice` is the transport-agnostic core and notice delivery is session-driven (the session holding the gate calls the connected transport's `reply()`), per the plan's own KTD5/KTD6. `emit_gate_notice`/`publish_outbound` retained as a redis-only programmatic seam, explicitly not the v1 hot path. | `publish_outbound(client, session_name, payload, …)` sig (`redis_producer.py:24`); Discord send path is the MCP `reply()` tool only (external `claude-plugins-official/discord@0.0.4`, no in-repo/Python producer). |
| 2 | P2 | **Named the concrete connectedness detector** — `presence.list_live_sessions(client)` / `presence.is_live` — instead of "the existing session registry" (folded into fix 1). | `presence.py:211` `list_live_sessions`; `presence.py:191` `is_live`; `channel.py:87` `is_connected`. |
| 3 | P3 | **U1 signature**: keep `at` **keyword-only** (plan had moved it positional) and named the real call site `outcome.py:1273` in addition to the argparse `outcome.py:1184-1187`. | current sig `approve_frontier(store, spec, *, at="")` (`outcome_decompose.py:337`); call site `approve_frontier(store, spec)` (`outcome.py:1273`). |
| 4 | P3 | **KTD2 mirror clarified** — the permission-reply "mirror" is trust-model only. Discord's permission reply is *router*-intercepted (`server.ts:837`) into a structured `permission` notification that never reaches the session; the gate answer is *session*-recognized as an ordinary `<channel>` inbound (KTD5/KTD6). Added a "do not extend the router's permission intercept" note. | `server.ts:833-849` router intercept → `notifications/claude/channel/permission`; `server.ts:836` trust comment. |

## 2. Anchor verification (every file:line in the plan)

All anchors verified against the live tree. Discord `server.ts` is the **external** first-party
`claude-plugins-official/discord@0.0.4` plugin (cache), **not** in this repo — flagged as residual
risk R-1 below.

| Anchor | Claim | Verified |
|--------|-------|----------|
| `outcome_decompose.py:337-350` | `approve_frontier` writes write-once `approvals/r{rev}.json` `{spec_revision, at}` | ✅ exact |
| `outcome_decompose.py:353-355` | `frontier_approved` = existence check (KTD3 backward-compat) | ✅ exact — `.exists()` only; extra keys safe |
| `outcome.py:1184-1187` | `approve` subparser + `outcome_id` arg | ✅ exact |
| `outcome.py:1273` | call site `approve_frontier(store, spec)` | ✅ (added to plan) |
| `redis_consumer.py:159-194` | `_dispatch` delivers every inbound unconditionally (no allowlist) | ✅ exact — only malformed/JSON drops; KTD5 holds |
| `protocol.py:113-138` | `PermissionRequest`/`PermissionVerdict` models | ✅ exact; `Inbound` (`:84-94`) exposes `text/chat_id/user_id/username/source` for U3 |
| `server.ts:236-294` | Discord `gate()` pre-filters to `allowFrom` | ✅ exact — non-`allowFrom` DM → drop/pair; non-allowlisted group → drop |
| `server.ts:79` | `PERMISSION_REPLY_RE` scoped verdict+code | ✅ exact |
| `server.ts:813` | `handleInbound` returns on `drop` | ✅ exact `if (result.action === 'drop') return` |
| `server.ts:833` | permission-reply intercept | ✅ exact; `:836` comment states the trust model verbatim |
| `server.ts:744-800` | button handler (deferred seam) | ✅ `/^perm:(allow\|deny\|more):…/` |
| `operator-choice.md:169-174` | dual-form offer (AskUserQuestion vs channel-inline) | ✅ exact |

## 3. KTD scrutiny (not just "is it documented")

- **KTD1** (v1 wires only the `/outcome` R20 durable gate; per-skill gates contract-only) — **sound.**
  The R20 gate is the only gate with a durable structured record (`approvals/r{rev}.json`); per-skill
  `AskUserQuestion` gates have no durable record, so wiring them would be a *new* gate mechanism the
  operator-choice framework forbids. Correctly scoped.
- **KTD2** (defer sender-auth to the transport) — **verified sound against real code.** Both transports
  enforce sender access *upstream of the session*: Discord `gate()` drops/diverts non-`allowFrom`
  senders before delivery; redis-channel defers to its router. The answer-capture path records the
  already-authorized `answerer`/`transport` and only resolves a *pending* gate id — it cannot
  re-authorize a sender. **This is the crux of the security feature and it holds.**
- **KTD3** (extend the write-once dict, not a new schema) — **sound.** `frontier_approved` is
  existence-only, so extra keys are backward-compatible; a net-new dataclass would be over-engineering.
- **KTD4** (render via existing `reply()` + gate-id correlation; no new stream pair) — **sound**, now
  with the trust-vs-mechanism clarification from fix 4.
- **KTD5** (gate logic in saga; redis-channel router-agnostic) — **sound.** `_dispatch` has no sender
  logic; the notify/answer logic lives in the new saga module; redis-channel takes a docs-only
  PROTOCOL note. Consistent with `[[feedback_redis_channel_router_agnostic]]`.
- **KTD6** (answer recognition = contract + pure parse helper, not a daemon) — **sound**, and now the
  notice side is symmetric (also session-driven) after fix 1.

## 4. Trust-boundary assessment (remote-approval security feature)

A channel prompt-injection cannot forge an approval, because: (a) the sender is authorized *upstream*
by the transport's access policy before any inbound reaches the session (verified — Discord
`gate()`/`allowFrom`, redis-channel router); (b) `parse_gate_answer` accepts a reply only if it
resolves a **pending** gate id supplied by the trusted caller, never one asserted in the body; and
(c) `answerer`/`transport` provenance is taken from the inbound's authenticated fields
(`user_id`/`username`/`source`), not the message text. The gate id is a **correlation id, not a bearer
capability** — authority is 100% the transport's allowlist (this matches the existing permission-reply
model, where the 5-letter code is likewise a correlation id, not a secret). Adequate for a
solo-operator fleet.

## 5. Remaining findings after fixes

None at P0/P1/P2. Residual P3 polish only:

- **P3** — U2's retained `emit_gate_notice` seam should build the `Outbound` payload shape
  (`protocol.py:100-107`) when wrapping `publish_outbound`; implementer-obvious, not spelled out.

## 6. Residual risk / limited evidence

- **R-1** — KTD2's Discord grounding rests on `claude-plugins-official/discord@0.0.4` `server.ts`,
  which is **external to this repo** and pinned to a cached version. `/work` cannot verify or test it
  from this tree, and a future Discord-plugin update could change `gate()`/intercept behavior. The
  saga-side code stays transport-agnostic (KTD5), so this does not couple the implementation to
  Discord internals — but the *security argument* for the Discord transport depends on an out-of-repo,
  version-pinned artifact. Acceptable given option A defers auth to the transport by design; noted so
  it is not mistaken for in-repo-verified behavior.

## 7. Review-result contract

- **Target:** `docs/plans/2026-07-05-remote-gate-approval-379-plan.md`
- **Reviewed revision:** working tree (base `d32e5a8`; 4 safe fixes applied in place, +45/−17)
- **Blocked:** No — READY for `/work` (no unresolved P0/P1)
- **Findings:** 1×P1 (applied), 1×P2 (applied), 2×P3 (applied), 1×P3 (residual)
- **Applied fixes:** §1 (4 edits)
- **Override rationale:** n/a (nothing blocking)
- **Links:** issue #379; plan (above); work-session pending (`/work` creates)
