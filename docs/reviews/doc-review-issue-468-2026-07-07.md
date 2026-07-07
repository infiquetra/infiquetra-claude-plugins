# Doc review — zero-token fire drill plan (#468)

**Target:** `docs/plans/2026-07-07-zero-token-fire-drill-plan.md`
**Reviewed revision:** working tree (plan uncommitted; repo evidence at main `d3c51a3`)
**Blocked:** NO — all findings fixed in place, every severity (operator standing instruction)
**Saga:** `issue-468` (lifecycle-phase plan, destination merge, backend inline)
**Linked issue:** infiquetra/infiquetra-claude-plugins#468 · **Plan origin:**
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (idea `H-F6-3`)

## Readiness summary

READY. One adversarial readonly-verifier pass (opus, disposable worktree, examined `d3c51a3`)
plus the inline readiness-skeptic pass produced 6 findings (1 P1, 2 P2, 3 P3-class); all 6 were
evidence-backed safe fixes and were applied to the plan in place. The verifier explicitly
confirmed the plan's highest-risk assumptions: the ollama-cloud HTTP lane is wired end-to-end
(resolver → `_build_invocation` `via=="engine-bridge-http"` branch → `engine_bridge_http.runner`),
and `engine_dispatch.dispatch()` disarms the #384 tripwire in a `finally`
(`engine_dispatch.py:227-231`) so the chaperone session is never left write-blocked.

## Findings (all FIXED in place)

| # | Sev | Finding | Evidence | Fix applied |
|---|-----|---------|----------|-------------|
| F1 | P1 | Core loop resolve→dispatch→manifest had no executable recipe: zero in-repo callers of `engine_dispatch.dispatch(`; runner and manifest-write steps unstated — executor would invent the driver, and AC1 receipts would silently not exist | grep `plugins/saga` + `plugins/team-execution`; `engine_dispatch.py:152-165`; `external-engine-workers.md:104,159-176` | Added the "Dispatch recipe (every offload in U2–U5)" section: resolve shape, per-lane runners (`engine_bridge_http.runner` / guarded `/agy:delegate`), explicit persist-receipt step, rows-not-auto-written warning mirrored into R1 |
| F2 | P2 | R1's resolver API shape would TypeError if copied (`resolve(mode=..., role_kind=...)` — `role_kind` is not a parameter; `registry` required) | `engine_resolver.py:191-197,202`; correct shape at `external-engine-workers.md:55` | R1 rewritten to `resolve({"role_kind": "worker", "engine": <sel>}, mode="dispatch", registry=registry)` with signature citation |
| F3 | P2 | Tripwire audit record is a claimed deliverable (KTD4, success metrics) but no unit passed the kwargs that arm it — bare `dispatch()` never arms (`session_id` gate) and can't corroborate (`workspace_root`) | `engine_dispatch.py:217-222,254` | Recipe step 2 requires `session_id=` + `workspace_root=` with `gated=False`, with the arming/corroboration line citations |
| F4 | P3 | KTD6 precedent citation had the wrong date (`2026-06-28-...-277.md`; actual file is `2026-06-29-...-277.md`) | `docs/engineering-journal/narratives/` listing | Citation corrected |
| F5 | P3 | KTD2 overstated the target defect as an "unconditional" append — 5.4 is gated on saga existence; only the missing MODE gate is the defect | `plugins/saga/skills/code-review/SKILL.md:296-299` | Reworded to "appends … in its saga branch with no mode gate" |
| F6 | P3 | Issue's "Release-Surface Checklist: Not applicable" clause is superseded by the chosen drill target (a saga-plugin change) — plan carried the surfaces but never named the deviation | issue #468 body vs plan R8/U3 | R8 now states the supersession explicitly |

## Verified-correct (checked, not padded)

Registry rows/ranks/transport/`key_env` (`engine-registry.yaml:80-90,145-159`); SKILL `:291`/`:296`
contradiction is genuine; `ci.yml:76/:102/:106` guards exist (confirming QUEUED
`{#marketplace-ci-guard}` is stale); `manifest_store.py --saga-id X list` CLI shape
(`manifest_store.py:299-309`); narratives precedent files; requirement mapping AC1–AC5 → R1–R8
complete; no plan content touches the AC5-frozen files.

## Residual risk

- The dispatch recipe is authored from the contract doc + code reading — no in-repo caller
  exists to copy, so U2's first dispatch is the recipe's first live execution (that is partly the
  drill's point; KTD8 makes any recipe-reality gap a recorded disposition).
- `record_dispatch_manifest` naming follows `external-engine-workers.md:159-176`; if the helper's
  actual import path differs at run time, `/work` follows the contract section, not the name.

## Method

Inline readiness-skeptic pass (verification, assumptions, AC mapping, completeness, open-choice,
adversarial) + one `saga:readonly-verifier` (opus, `isolation: worktree`, examined SHA quoted)
adversarial refutation pass. Rubric engine not applicable (plan-phase artifact; rubric phases are
idea/issue/spec). Concurrency cap respected (1 agent in flight).
