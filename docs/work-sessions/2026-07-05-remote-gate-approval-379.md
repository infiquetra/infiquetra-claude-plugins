# Work session — Remote gate approval over the fleet's own channel (#379)

- **Date:** 2026-07-05
- **Issue:** [#379](https://github.com/infiquetra/infiquetra-claude-plugins/issues/379) — Phase 0 item 8
- **Plan:** `docs/plans/2026-07-05-remote-gate-approval-379-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-remote-gate-approval-379-doc-review.md` (READY; 4 safe fixes applied in-plan; no unresolved P0/P1)
- **Backend:** inline (option A = build the issue as specified; mechanical two-plugin integration)
- **Branch:** `feat/pf-remote-gate-approval-379`
- **Destination:** merge

## What was built (by U-ID)

- **U1 — gate-answer provenance on the durable record.** `outcome_decompose.approve_frontier(...)`
  gains keyword-only `answerer` / `transport` (written into `approvals/r{rev}.json` only when supplied;
  terminal approval stays byte-identical; `frontier_approved` existence-check unchanged, KTD3).
  `outcome approve` CLI gains `--answerer` / `--transport`, forwarded at the call site.
- **U2 — channel gate-notify composer (saga).** New `plugins/saga/scripts/outcome_gate_transport.py`:
  transport-agnostic `compose_gate_notice(spec, spec_revision, gated_subplots)` (gate id
  `<outcome_id>@r<rev>` + pending subplots + lettered A/B choices). Redis-only `emit_gate_notice`
  programmatic seam (injected `producer` + `is_connected`; the real detector is
  `presence.list_live_sessions`) — not the v1 hot path (session-driven delivery, KTD6).
- **U3 — gate-answer parse + access deferral (saga).** `parse_gate_answer(inbound, pending_gate_ids)`
  → `GateAnswer | None`. Fail-closed trust boundary: accepts only when the reply quotes a gate id in
  `pending_gate_ids`; `answerer`/`transport` read from router-set inbound fields, never the body;
  ambiguous/unattributable/no-match → `None`, never a default *approve*.
- **U4 — no-answer parity + disconnected fallback.** End-to-end tests: an unanswered gate holds
  byte-identically with the transport enabled-but-unanswered vs disabled; a disconnected session never
  emits; a valid answer records provenance and lifts the gate; a reject is a no-op hold.
- **U5 — documented contract.** `references/operator-choice.md` §5.1 (channel-transport gate delivery)
  + `redis-channel/PROTOCOL.md` (transport-agnostic notice/answer convention; router-agnostic, docs-only).
- **U6 — release surfaces.** saga 0.59.0 → **0.60.0**; redis-channel 0.5.0 → **0.5.1** (docs-only
  PROTOCOL note); `marketplace.json` regenerated (9 entries); per-plugin CHANGELOGs; drift-guard literal
  `tests/test_saga_plugin.py`; DECISIONS `{#remote-gate-approval-379}` (KTD1-KTD6); execution-order
  row 8 `[x]`.

## Key decisions

- Option A (KTD2): sender-auth deferred to the transport's access policy (verified upstream-of-session
  on both transports against the real Discord `server.ts` + redis `_dispatch`); provenance, not a new
  allowlist. redis-channel stays router-agnostic (KTD5) — code lands in saga, redis-channel docs-only.
- Notice delivery is session-driven for both transports (doc-review P1); the Python emit seam is
  redis-only and not the hot path.

## Files modified

- `plugins/saga/scripts/outcome_gate_transport.py` (new)
- `plugins/saga/scripts/outcome_decompose.py` (approve_frontier provenance)
- `plugins/saga/scripts/outcome.py` (approve CLI args + call site)
- `tests/test_outcome_gate_transport.py` (new, 21 tests)
- `plugins/saga/references/operator-choice.md`, `plugins/redis-channel/PROTOCOL.md` (contract)
- release surfaces: both `plugin.json`, `.claude-plugin/marketplace.json`, both `CHANGELOG.md`,
  `tests/test_saga_plugin.py`
- `docs/engineering-journal/DECISIONS.md`, `docs/plans/2026-07-04-plugin-fleet-execution-order.md`
- `docs/plans/2026-07-05-remote-gate-approval-379-plan.md` (+ doc-review artifact) — carried from the review

## Checks run

- `tests/test_outcome_gate_transport.py`: 21 passed (module coverage 98%).
- Full gate: pending (pytest + ruff format --check + ruff check + mypy + bandit) before PR.

## Next step

Full-repo gate → programmatic `/code-review` gate → ship ceremony to MERGED.
