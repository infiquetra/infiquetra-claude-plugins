# Work session — zero-token fire drill (#468)

**Saga:** `issue-468` · **Plan:** `docs/plans/2026-07-07-zero-token-fire-drill-plan.md` ·
**Branch:** `feat/468-zero-token-fire-drill` · **Draft PR:** #522 (ceremony front-loaded, R7) ·
**Destination:** merge · **Backend:** inline (operator-confirmed)

## U1 — scaffold (complete)

Plan + doc-review artifact + DECISIONS committed (`0ecd073`); map skeleton at
`docs/engineering-journal/narratives/2026-07-07-zero-token-fire-drill-irreducibility-map.md`
(`b237d9e`); saga advanced to `lifecycle_phase=work` on-branch; draft PR #522 opened.

Driver: scratchpad `drill_dispatch.py` — the plan's Dispatch recipe made executable
(resolve → `dispatch(session_id=…)` → Claude verification → `record_dispatch_manifest` under
saga `issue-468`). Lane posture per map OBS-1: `workspace_root` (observer corroboration) on the
agy lane only — `ENGINE_CONFIGS` has no `ollama-cloud` row, so the observer would discard
honest HTTP-lane output as an integrity divergence.

## U2 — S1 spec-framing + S2 plan offloads (complete)

4 dispositions recorded (manifests `drill-468-s1-*`, `drill-468-s2-*`, plus preserved
`drill-468-s1-agy-attempt1`):

- **S1 degraded** both lanes: ollama-cloud usable at ~14% rework (priority inflation, invented
  consequence, wrong marketplace path); agy needed a retry after the OBS-2 false-positive
  (transient 503 → zero output → wrapper `success` + corroborated receipt with
  `bytes_produced: 0`) — attempt 2 near-clean (~6%).
- **S2 offloaded-clean** both lanes: correct four-file plans, correct 0.74.1 bump; one
  fabricated verification claim each (pruned at adjudication).

Machinery observations OBS-2 (zero-output false positive), OBS-3 (per-session marker ⇒ lanes
serialize; #520 F4 shape), OBS-4 (arming + finally-disarm clean on both lanes) recorded in the
map. Checks run: none yet (docs-only units; hard gate lands with U3/U7).

## Next step

U3: adjudicate the S3 patches (both lanes dispatched), land the Defect 2 fix + release surfaces,
run the U3 test scenarios.
