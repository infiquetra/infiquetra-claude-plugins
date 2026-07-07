# Doc-review: external-engine HTTP bridge + bridge_receipt.v1 keystone pair plan

**Target:** `docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md`
**Companion artifacts reviewed/synced:** `docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-spec.json`, `...workflow.js` (re-emitted)
**Reviewed revision:** working tree on branch `feat/387-383-http-bridge-receipt-pair` (plan not yet committed)
**Linked:** issues #387 + #383, saga `issue-387`, outcome `external-engine-offload` (`sub-387`, `sub-383`)
**Blocked:** no — all findings fixed in place (operator directed fixing ALL priorities, not just P0/P1)
**Review type:** plan-phase readiness-skeptic pass + security lens (secrets, external integrations). Formal idea/issue rubrics not applicable to a plan artifact.

## Readiness summary

The plan is ready to drive implementation. All eight findings were evidence-backed and fixed
in place; the execution spec was synced and re-validated/re-emitted with tiers, control flow,
agent counts, and spend (346) unchanged — the R8 operator confirmation of 2026-07-07 remains
valid. No open product decisions remain.

## Findings

| # | Pri | Finding | Status |
|---|-----|---------|--------|
| F1 | P1 | Dependency-order defect: `AdvisoryEvidence.runner_receipt` consumed by U5 but created in U6, which runs after U5 in the serialized chain — U5 could not land green as specced. | Fixed — field + threading moved to U5; U6 keeps gating + `Disposition.UNPROVEN` + gatekeeper guard. Plan (U5/U6/KTD8) + spec prompts updated. |
| F2 | P1 | Release-surface gap: U8 edits team-execution's `external-engine-workers.md` (user-facing guidance) but omitted team-execution's plugin.json/CHANGELOG/marketplace bumps — violates the repo's same-PR release-surface rule. | Fixed — four-plugin surface set in plan U8 + spec U8 prompt/files. |
| F3 | P2 | U7's "red if pending issue #476 is closed" check requires network inside a unit test — non-hermetic, flaky in CI/offline. | Fixed — red conditions constrained to filesystem/registry state only; staleness caught by the `plugins/codex/`-exists condition. Plan + spec updated. |
| F4 | P2 | KTD3's "≤ MODERATE ratings cannot reroute" is false where the current per-capability winner is WEAK (`long-form-writing`, verified `engine-registry.yaml:41,126`) — a MODERATE row would hijack routing. | Fixed — exact rule stated (never rate at/above current winner; omit or WEAK), regression test bakes current winners as literals. |
| F5 | P2 | Issue ACs name greenfield test files the plan re-homes into the existing suite; unstated mapping would send /qa to missing paths. | Fixed — explicit re-homing map added to the Verification section; selectors preserved verbatim. |
| F6 | P2 | Secret lifecycle under-specified: invocation dict flows into run-ledger facts (`engine_dispatch.py:190-230`), so a key resolved too early would leak into telemetry. | Fixed — constraint added to U5 goal, spec U5 prompt, and Risk Analysis: key resolved from `auth.key_env` only at request-build time inside the bridge; env var name at most in receipts/errors. |
| F7 | P3 | U3 didn't state new rows must satisfy the full loader-enforced row schema (`capability_profile` ≥1, `prompting_protocol`, `sources` — `engine_registry.py:106-161`). | Fixed — stated in U3 goal; honest seed values, never placeholders. |
| F8 | P3 | Branch name absent from KTD11; #387 AC4's "role field is advisory" not mapped to the actual structure. | Fixed — branch named in KTD11; AC4 mapping stated in U6 (advisory by construction: `verified_by_claude=False`, no gate fields, plus the structural guard). |

## Applied fixes

All eight, in place, in the plan; F1/F2/F3 also propagated to the spec JSON (U5/U6/U7/U8
prompts + U8 files). Spec re-validated with `--require-receipts` (OK) and `.workflow.js`
re-emitted: 3 panel `parallel([` sites, 8 opus calls, 17 total agents, peak concurrency 3,
total spend 346 — byte-level tier/control-flow parity with the R8-confirmed configuration.

## Residual risk / limited evidence

- Provider base URLs / wire model ids remain to-verify-at-implementation (U3 mandates
  checking provider docs; the availability-gated smoke is the live proof). A wrong seed URL
  cannot fail CI by design (skip-not-fail) — accepted, same posture as the 2026-06-27 seed
  rows.
- The `Disposition(value)` enum round-trip for the new `UNPROVEN` value is asserted by U6's
  round-trip test scenario rather than pre-verified here (StrEnum standard behavior).
