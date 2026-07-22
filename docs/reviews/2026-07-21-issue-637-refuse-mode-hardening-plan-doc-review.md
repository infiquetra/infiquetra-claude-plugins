---
target: docs/plans/2026-07-21-issue-637-refuse-mode-hardening-plan.md
reviewed_revision: working tree at origin/main 47dacede
classification: plan
verdict: READY
blocked: false
linked_issue: infiquetra/infiquetra-claude-plugins#637
linked_spec: docs/plans/2026-07-21-issue-637-refuse-mode-hardening-spec.json
date: 2026-07-21
---

# Doc review — issue #637 refuse-mode hardening plan

**Verdict: READY.** Zero findings remain; three findings (1 P2, 2 P3) were found and all were
safe-fixed in place with repo evidence. No P0/P1 at any point. The plan can drive implementation
without the executing agent inventing missing decisions.

## Review scope

Readiness-skeptic pass (plan classification — `docs/plans/` path, `origin:`/Implementation
Units/KTD shape; no idea/issue rubric phase applies). Every code anchor, test name, version pin,
and precedence claim in the plan was re-verified against the working tree at `47dacede`. External
engine offer: stored preference `none` (`engine_offer.py offer --stage doc-review` →
`intent: none`, no prompt required) — Claude-only review.

## Anchor verification (all confirmed)

| Claim | Evidence |
| --- | --- |
| Refuse branch `:2168-2178`, raise in `_drop_superseded_resource_lease` | `lease_broker.py:2135` def, raise at `:2173` |
| Settlement-retained + canonically-closed arms above the liveness gate | method docstring says the refuse gate sits "*below* the settlement-retained and canonically-closed precedence"; arms at `:2154-2166` |
| `_owner_state` tri-state at `:3901`; sweep consumer `:3957` | matches R1/R2 exactly: stale boot-id → dead, `owner_pid=None` → unknown, missing process → dead, unreadable identity → unknown, identity mismatch → dead |
| `DEFAULT_TTL_SECONDS = 300` | `lease_broker.py:36` |
| Dispatcher anchors `:268` (owner_pid), `:283-284` (normalize), `:290`/`:292-296` (lost-authority/renew), `:303/:316/:325` (cleanup), `:822` (CLI consumer) | all present at the cited lines |
| `outcome.py:1589` arm + `:1590-1592` transient-set comment | present; closed `LEDGER_CLASSIFICATIONS` vocabulary at `:1603` |
| Test pins | `test_retry_supersedes_at_full_capacity` (`tests/test_fleet_lease_broker.py:734`), `test_advance_records_lease_refusal_as_halt_and_continues` (`tests/test_outcome_command.py:910`) |
| Release surfaces | fleet-core 0.17.0 / saga 0.107.0 in both plugin.json and marketplace.json; drift pin `tests/test_saga_plugin.py:49`; `scripts/check_release_surface_parity.py` present |
| DECISIONS entry staged | `{#refuse-liveness-and-loud-abort-637}` at `docs/engineering-journal/DECISIONS.md:5` |

## Findings and dispositions

| ID | Priority | Finding | Status |
| --- | --- | --- | --- |
| D1 | P2 | R6/U2 left the loud-abort lock consequence unstated: re-raise before release leaves the `dispatch-{sid}` store lock held until the 900 s stale-reclaim (`DEFAULT_LEASE_TTL`, `outcome.py:66`; reclaim at `outcome_store.py:612`); coordinator lock is `finally`-protected (`outcome.py:1072-1073`). U2's "lease state consistent" test wording was ambiguous. | fixed (safe) |
| D2 | P3 | KTD1 missed the in-repo precedent that recovery already requires a provably dead owner (`lease_broker.py:4202`); U1 didn't pin that `_owner_state` itself is unmodified (consumers `:3957`/`:4202` unaffected). | fixed (safe) |
| D3 | P3 | Two distinct TTLs (store lock 900 s vs broker dispatch lease 300 s) risked conflation in U2's comment rewrite. | fixed (safe) |

## Applied fixes

1. R6: named the abort-path lock consequence (held `dispatch-{sid}` lock, TTL stale-reclaim,
   coordinator lock safe via `finally`).
2. U2 test scenario: replaced "lease state consistent" with the explicit pin (assert no release;
   coordinator lock released by the outer `finally`).
3. KTD1: added the `:4202` recovery-path proven-dead precedent.
4. U1 approach: pinned `_owner_state` as unmodified with its existing consumers unaffected.
5. U2 approach: TTL-disambiguation parenthetical for the comment rewrite.

## Residual risk

The dispatcher line anchors (`:283-325`) sit inside one function and will shift once U1/U2 edit
the files; the spec already treats the plan as authoritative and instructs site-by-site review,
so drift risk is low. No other residual evidence gaps.
