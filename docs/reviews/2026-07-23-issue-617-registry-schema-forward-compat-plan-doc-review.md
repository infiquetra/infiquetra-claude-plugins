# Doc review — issue #617 registry schema forward-compatibility plan

**Verdict: ready** — the plan can safely drive implementation via `/work`. Two safe fixes applied
in place; two P3 advisories remain; zero P0/P1/P2.

## Review-result contract

- **Target:** `docs/plans/2026-07-23-issue-617-registry-schema-forward-compat-plan.md` (+ spec
  `docs/plans/2026-07-23-issue-617-registry-schema-forward-compat-spec.json`)
- **Reviewed revision:** working tree at main `4eb2fe15` (plan/spec uncommitted, authored this
  session)
- **Blocked:** no
- **Linked:** issue infiquetra/infiquetra-claude-plugins#617, saga `issue-issue-617`
  (lifecycle `plan`, destination `merge`, orchestration `cc-workflows-ultracode`), outcome
  `governed-execution-integrity` leaf sub-617
- **Mode:** readiness-skeptic pass, driver-side verification (no agent spawns needed — every
  anchor re-checked against the tree at `4eb2fe15`). The rubric engine has no `plan` phase
  (idea/spec/issue only), so no formal rubric pass applies to a plan-classified document.

## Applied fixes

1. **LEARNINGS anchor slug corrected** — plan and spec cited
   `{#registry-schema-forward-poisoning-616}`; the actual heading anchor in
   `docs/engineering-journal/LEARNINGS.md:30` is `{#broker-schema-forward-poisoning-616}`.
   Fixed at 3 sites (2 plan, 1 spec U3 prompt); spec re-validated (`--require-receipts`) and
   `.workflow.js` re-emitted after the edit.
2. **R10 backup-before-inject** — the live-acceptance leg mutates the live machine-wide
   registry; added an explicit backup step before the synthetic-field injection, consistent
   with the plan's own backup-before-mutation discipline (R8/KTD4).

## Verification highlights (driver-side, this session)

- Every cited `path:line` anchor re-confirmed at `4eb2fe15` (SCHEMA `:29`, `_TOP_KEYS` `:51-63`,
  `_closed_mapping` `:363-374`, `_record_sha256` `:629-631` + receipt checks `:703-705`/`:774-778`,
  `Registry.from_dict` `:1255-1360`, `to_dict` `:1362-1381`, `_write_registry` `:1639-1670`,
  adapter verbs `:443-474`).
- **KTD1 is forced, not just principled:** `validate_settlement_close` rebuilds a fixed-key
  `normalized` dict and recomputes both digests over it (`:683-706`) — an unknown key inside a
  close record makes the stored digest mismatch the recompute regardless, so commitment records
  physically cannot be opened without a schema rev. The plan's carve-out is the only coherent
  choice.
- **Outer settlement records are safe to open:** `_record_sha256` is called only in the two
  settlement-close validation paths; `SettlementRecord.from_dict` (`:990`) carries no
  self-digest. U1's tolerance scoping is correct.
- `FLEET_COMMONS_ROOT` is rung 1 in `fleet_commons_shim.py` (`:11`, `:100`) — honesty-note claim
  correct.
- Version targets correct: repo currently fleet-core 0.21.0 / saga 0.112.0 → 0.22.0 / 0.113.0.
- Adapter CLI today returns only 0 (`plugins/saga/scripts/lease_broker.py:556`); doctor's
  proposed exit codes 3/4 collide with nothing (hook-halt exit 2 lives in the hook file, not the
  adapter CLI).
- Scope adjudication verified: the #644 D2 "claim-policy territory" note does not match issue
  #617's body; the plan explicitly rules it out with a fresh-issue pointer. #642/#645/#646/#647
  boundaries all named.
- Spec/plan consistency: U-IDs match, depends_on U1→U2→U3, verify n=3 on U1/U2, worth-it
  receipts present on both opus units (U2's operator-escalated), spend 262, tiers as
  operator-locked.

## Remaining findings

| ID | Priority | Finding | Status |
|----|----------|---------|--------|
| D1 | P3 | FencingToken's open-vs-closed status is deferred to U1's in-unit digest audit (default closed). Acceptable — bounded, default-safe — but the audit outcome must land in the U1 code comments so the carve-out inventory is complete. | open (informational) |
| D2 | P3 | The doctor/repair exit-code contract (0/3/4, `--strip-unknown`) is new operator-facing CLI surface; U3's CHANGELOG entry should state the codes explicitly, not just name the verbs. | open (advisory) |

## Residual risk from limited evidence

The 64 KiB extras cap (KTD5) is a reasoned bound, not a measured one — no real additive-field
payload exists yet to size against. The cap is generous relative to any plausible field addition
and fails closed, so the risk is a too-tight bound surfacing as a loud error, not silent damage.
