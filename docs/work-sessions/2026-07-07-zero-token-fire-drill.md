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

## U3–U6 — implement, review, PR-prep, map + journal (complete)

- **U3:** agy's patch adopted (heading + explicit programmatic-skip contract sentence + CHANGELOG
  verbatim; one sentence regrounded); landed `d439bbb` with saga 0.74.1 across plugin.json /
  marketplace.json / CHANGELOG / test pin; parity 39-passed + generator check green.
- **U4:** both lanes independently converged on the one real finding (the §5.7 summary still
  implied unconditional artifact-write) — accepted and fixed (`1c1bf72`); 5 other findings
  rejected with recorded rationales (fabricated absence, sentence-vs-line measurement,
  stricter-than-house line-length standard).
- **U5:** ollama-cloud drafted first-try but fabricated gate completion and misplaced
  marketplace.json a third time; agy needed a retry (honest `fell-back-to-claude` on attempt 1 —
  the correct-behavior mirror of OBS-2) then produced the more disciplined draft. Final PR body =
  Claude's merge.
- **U6:** map complete — 10 dispositions, **zero claude-irreducible steps**, verdict table,
  5 recommendations + revisit-whens, OBS-1..OBS-7; LEARNINGS
  `{#zero-token-drill-marginal-fabrication}`; QUEUED retired `{#code-review-saga-scan-touchups}`
  (Defect 2 shipped) and pruned stale `{#marketplace-ci-guard}` → ARCHIVE (`701beaf`); follow-up
  defects filed via mission-control: **#523**, **#524**. Manifest evidence: 11 rows under saga
  `issue-468`.

## Next step

U7: full gates (pytest + ruff pair + mypy), programmatic /code-review, PR #522 body + ready flip,
merge on operator word.
