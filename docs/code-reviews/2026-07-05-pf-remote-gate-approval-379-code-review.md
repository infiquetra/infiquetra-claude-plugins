---
title: Code review — Remote gate approval over the fleet's own channel (#379)
type: code-review
date: 2026-07-05
target: branch feat/pf-remote-gate-approval-379 (diff origin/main...HEAD)
reviewed_sha: 392fd20183edc20d7fcfcacefa08fffe9defd1c1
base: origin/main (d32e5a8)
mode: programmatic
blocked: false
verdict: CLEAN
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/379
linked_plan: docs/plans/2026-07-05-remote-gate-approval-379-plan.md
doc_review: docs/reviews/2026-07-05-remote-gate-approval-379-doc-review.md
work_session: docs/work-sessions/2026-07-05-remote-gate-approval-379.md
---

# Code review: #379 remote gate approval — CLEAN

**Verdict: CLEAN — not blocked. 0 surviving findings** (1 issue surfaced by the adversarial panel was
fixed inline during review and re-verified). Reviewed SHA `392fd20`.

## Scope

18 files, ~850 insertions, committed on `feat/pf-remote-gate-approval-379` vs `origin/main` (d32e5a8).
Diff is exactly the 6-unit #379 change (saga code + saga/redis-channel docs + release surfaces + tests).
No untracked files in scope. Full local gate green at review time: pytest 2057, ruff format+check, mypy
136 files, bandit no issues on touched files, release-surface parity + marketplace regen.

## Scope check: CLEAN

- **Intent:** deliver the `/outcome` R20 approval gate over redis-channel/Discord with answerer/transport
  provenance; access deferred to the transport (option A).
- **Delivered:** exactly that. No scope creep; no unrelated files. The one code change outside the new
  module (`approve_frontier` provenance + `outcome approve` CLI) is required by U1.

## Plan-completion audit (5-state)

| Unit | Status | Evidence |
|------|--------|----------|
| U1 provenance + CLI | **DONE** | `outcome_decompose.py:337-372` (keyword-only answerer/transport, conditional write); `outcome.py:1188-1197` (argparse) + `:1283-1284` (call site threads both). |
| U2 compose + emit seam | **DONE** | `outcome_gate_transport.py` `compose_gate_notice` (pure, deterministic) + `emit_gate_notice` (redis-only, documented non-hot-path). |
| U3 parse + access deferral | **DONE** | `parse_gate_answer` fail-closed; provenance from router-set fields; pending-set membership gate. |
| U4 no-answer parity + fallback | **DONE** | `test_outcome_gate_transport.py` end-to-end + disconnected-noop tests. |
| U5 documented contract | **DONE** | `operator-choice.md` §5.1; `redis-channel/PROTOCOL.md` gate-notice section (router-agnostic). |
| U6 release surfaces | **DONE** | saga 0.60.0 / redis-channel 0.5.1; marketplace regen (parity OK); CHANGELOGs; drift-guard literal; DECISIONS `{#remote-gate-approval-379}`; execution-order row 8 `[x]`. |

## Lenses (judgment-selected)

security/trust-boundary (core), correctness (backward-compat + gate-id correlation),
architecture/decoupling (KTD5), completeness (dead-wiring + release parity). No infra/migration/deploy
lens — the diff touches none.

## Adversarial verification (4 read-only verifiers, disposable worktrees)

All returned **UPHELD**. Each attempted to *refute*.

1. **Trust boundary (forge an approval):** 8 attacks — body-injected provenance, gate-id forgery, regex
   boundary quirks, substring/emoji ambiguity, blank-provenance, stale-revision. **None forged an
   approval.** Provenance comes only from router-set inbound fields; a reply must quote a gate id in the
   caller-supplied `pending_gate_ids`; ambiguous/unattributable/empty → `None`; never defaults to approve.
2. **Backward-compat + decoupling + CLI wiring:** terminal approval writes byte-identical
   `{spec_revision, at}` (2 keys, verified by direct run); `frontier_approved` existence-check unaffected;
   module imports are stdlib-only (AST-verified, no `outcome_spec`/redis-channel); `compose_gate_notice`
   deterministic; CLI call site threads `--answerer`/`--transport`.
3. **Completeness + release parity:** `emit_gate_notice` is documented redis-only non-hot-path (not
   orphan); `check_release_surface_parity` exit 0; CHANGELOG grammar exact; journal/tick present; 4
   scenario categories covered.
4. **Hardening delta (below):** 13 forge/flip attempts on the amended parser — all fail-closed.

## Issue found and fixed inline during review

- **Gate-id-token verdict pollution (fail-closed correctness, fixed).** `_resolve_verdict` originally
  tokenized the whole reply *including the quoted gate id*. Because the gate id embeds the
  operator-chosen `outcome_id`, a name like `no-op-migration` injected a spurious `no` (reject) token,
  reading every reply as ambiguous → that gate was **un-approvable over the channel**. Fail-closed (never
  forged an approval — the panel confirmed no security hole), but a real limitation for plausible
  `outcome_id`s. **Fix (`392fd20`):** strip every gate-id-shaped token before verdict resolution
  (`_GATE_ID_RE.sub(" ", text)`) — a strict subtraction that runs *after* pending-set membership is
  verified, so it cannot inject a token, flip a verdict, or bypass authorization. +1 regression test.
  Re-verified by a dedicated adversarial verifier (13 inputs incl. gate-ids that are literally verdict
  tokens like `n@r3`, `a@r4`): all fail-closed, 22 tests pass.

## Residual risk

- KTD2's Discord grounding lives in the external `claude-plugins-official/discord@0.0.4` (out of this
  repo, version-pinned) — carried from the doc-review as R-1. The saga code stays transport-agnostic
  (KTD5), so no coupling to Discord internals; noted, not blocking.

## Review-result contract

- **Target / reviewed revision:** `feat/pf-remote-gate-approval-379` @ `392fd20`
- **Blocked:** No (CLEAN)
- **Findings:** 0 surviving (1 fixed inline during review, re-verified)
- **Plan completion:** 6/6 DONE
- **Scope check:** CLEAN
- **Coverage:** full local gate green; module coverage 98% (one defensive branch uncovered)
- **Links:** issue #379; plan; doc-review; work-session (front-matter)
