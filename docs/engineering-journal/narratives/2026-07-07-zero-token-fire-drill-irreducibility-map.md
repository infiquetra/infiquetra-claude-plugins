# Zero-token fire drill — irreducibility map (#468)

One real lifecycle loop — spec-framing → plan → implement → review → PR-prep — on a real unit of
work (the `/code-review` programmatic-mode append contradiction, QUEUED
`{#code-review-saga-scan-touchups}` Defect 2), with every step dispatched through BOTH $0 lanes.
Claude verified every output (never-gatekeeper, R6); no engine output satisfied any gate.

- **Plan:** `docs/plans/2026-07-07-zero-token-fire-drill-plan.md` · **Saga:** `issue-468`
- **Lanes:** `agy/gemini-3.5-flash-high` (cost_speed_rank 1) · `ollama-cloud/gpt-oss-120b`
  (rank 5, first-ever live dispatch on the newly wired `OLLAMA_API_KEY`)
- **Machinery frozen (R5):** `engine-registry.yaml`, `engine_resolver.py`, `engine_dispatch.py`,
  `external-engine-workers.md` — zero changes; defects found are dispositions + follow-ups.

## Method

Each dispatch followed the plan's recipe (`external-engine-workers.md` §2–§5): resolve with
`{"role_kind": "worker", "engine": <lane>}` in `mode="dispatch"` → `engine_dispatch.dispatch()`
with `session_id` (arms the #384 delegation tripwire) → Claude verification → manifest row under
saga `issue-468` (`manifest_store.py --saga-id issue-468 list`). Receipts are the manifest rows;
tripwire audit records corroborate where the machinery supports it (see OBS-1).

**Verdict rubric (KTD3), per step × lane:**

| Verdict | Meaning |
|---|---|
| `offloaded-clean` | accepted after Claude verification with only trivial edits (rework < ~10%) |
| `degraded` | usable only after substantive Claude rework or a retry (rework ≥ ~10%, or 2nd dispatch) |
| `claude-irreducible` | output unusable, or the lane structurally cannot perform the step |

Step-level verdict = the best lane's verdict. Rework fraction = edited-lines / total-lines of the
accepted artifact.

## Pre-dispatch machinery observations

**OBS-1 — two-signal corroboration is receipt- and bundle-gated; only the agy lane can carry it.**
`delegation_audit.ENGINE_CONFIGS` has rows for `agy` and `codex` only — `corroborate("ollama-cloud", …)`
raises `UnknownEngineError`, which `_observer_corroborates` conservatively maps to observer-NO.
Because `dispatch()` treats `workspace_root is not None` as opting into two-signal reconciliation,
passing `workspace_root` on the ollama-cloud lane converts every honest `ok` into an advisory
`DELEGATION_INTEGRITY` divergence **that discards the engine's output** (`evidence=""`,
`engine_dispatch.py:292-305`). Driver posture therefore differs by lane — a deviation from the
plan recipe's blanket "session_id + workspace_root REQUIRED", recorded here per KTD8:

| Lane | `session_id` (arm) | `workspace_root` (observer) | Corroboration ceiling |
|---|---|---|---|
| agy | yes | yes | full two-signal (bundle `agy_launched` + embedded receipt) |
| ollama-cloud | yes | **omitted** | single-signal; receipt still schema-valid (`http-bridge` emits `bridge_receipt.v1`) |

Follow-up candidate (out of scope, R5): an `ollama-cloud` row in `ENGINE_CONFIGS` — or receipt-only
corroboration for bundle-less HTTP engines — so the HTTP lane can opt into two-signal without
losing output.

## Dispositions

<!-- One per step × lane, filled as the drill runs. -->

### S1 — spec-framing

Task: write the issue-shaped defect spec for the `/code-review` Defect 2 fix from the QUEUED
entry + SKILL 5.3/5.4 excerpts (identical context package both lanes; sources inline).

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | attempt 1 false-positive `success` with **0 output bytes** (OBS-2); attempt 2 ok, observer-corroborated | `drill-468-s1-agy` ran-as-requested (+ preserved `drill-468-s1-agy-attempt1`) | **degraded** (second dispatch needed, KTD3; attempt-2 content itself clean at ~6% rework) | ~6% (2/33 lines: temper "unconditionally" per plan F5; priority label) | manifests + bundles `drill-468-s1-agy-190129` (failed), `-190558` (good) |
| ollama-cloud | ok first try — **first-ever live dispatch on this lane**, schema-valid `bridge_receipt.v1`, 34s-class latency | `drill-468-s1-ollama-cloud` ran-as-requested | **degraded** (substantive factual repairs) | ~14% (5/36 lines: priority "high" vs source's "not urgent"; invented "causes failed runs" consequence; wrong `marketplace.json` path; inapplicable automated-test AC) | manifest + `evidence/s1-ollama-cloud.md` |

**Step verdict: degraded** (both lanes usable after Claude repair; neither clean). Adjudicated
working spec = agy attempt-2 text with the two trivial repairs (P2 priority restored,
"unconditionally" tempered to "with no mode gate"). Notable: agy alone carried the
`--lifecycle-phase` carry-forward subtlety into its acceptance criteria and got the root-level
`.claude-plugin/marketplace.json` path right; ollama-cloud misplaced it under `plugins/saga/`.

### S2 — plan authoring

Task: mini-plan (files / edit shape / version bump / test scenarios / risks) from the adjudicated
S1 spec + current 5.4 text + release-surface facts.

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | ok first try, observer-corroborated | `drill-468-s2-agy` ran-as-requested | **offloaded-clean** | ~7% (1 wrong claim: ruff lints "JSON and Markdown" — it lints Python) | manifest + `evidence/s2-agy.md` |
| ollama-cloud | ok first try, receipt valid | `drill-468-s2-ollama-cloud` ran-as-requested | **offloaded-clean** | ~7% (1 invented verification: a skill-parsing test asserting 5.4 prose content — no such test) | manifest + `evidence/s2-ollama-cloud.md` |

**Step verdict: offloaded-clean.** Both lanes produced correct four-file plans with the right
patch bump (0.74.0 → 0.74.1) and correct guard mapping (tri-lock parity, generator `--check`).
Each fabricated exactly one plausible-but-false verification claim — the recurring failure shape
this step measures: engines invent test coverage that does not exist, which is precisely why the
never-gatekeeper rule (R6) keeps Claude as verifier-of-record. Adjudicated plan = intersection of
both plans with the two false claims pruned; gate placement locked to "modify/immediately follow
the If-and-only-if sentence".

### S3 — implementation

Task: exact replacement text for SKILL.md §5.4 + the 0.74.1 CHANGELOG entry (evidence-only —
engines return text, the chaperone applies; landed as `d439bbb`).

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | ok first try, observer-corroborated | `drill-468-s3-agy` ran-as-requested | **offloaded-clean** (adopted) | ~7% (lead sentence regrounded to say *why* the skip exists; otherwise adopted incl. heading + CHANGELOG verbatim) | manifest + `evidence/s3-agy.md` |
| ollama-cloud | ok first try, receipt valid | `drill-468-s3-ollama-cloud` ran-as-requested | **degraded** | ~15-20% (gate clause works but omits the required caller-owns-persistence contract sentence; heading left stale; first line re-wrapped to ~135 chars breaking the 100-char house style) | manifest + `evidence/s3-ollama-cloud.md` |

**Step verdict: offloaded-clean.** agy delivered the adoptable artifact: correct restructure
(explicit programmatic-skip sentence mirroring 5.3's contract language, updated heading,
house-style wrap) and a precise CHANGELOG entry adopted verbatim. ollama-cloud produced the
minimal inline gate — functional but under-specified against the stated constraints. Chaperone
additions outside both patches (recorded, not engine rework): the §5.7 summary-line consistency
touch and the `tests/test_saga_plugin.py` drift-guard pin bump — neither lane was shown those
surfaces; the pin was in S2's source material as "tri-lock" only.

### S4 — review

Task: adversarially refute the landed `d439bbb` diff (identical diff + standards package both
lanes). Every returned finding Claude-adjudicated: accept → fixed in-branch, reject → rationale.

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | ok first try, observer-corroborated; findings cite its clone's real line numbers (proof of genuine repo access) | `drill-468-s4-agy` ran-as-requested | **offloaded-clean** | accept-rate 1 real + 3 defensible of 4; calibrated APPROVE-WITH-NITS verdict | manifest + `evidence/s4-agy.md` |
| ollama-cloud | ok first try, receipt valid | `drill-468-s4-ollama-cloud` ran-as-requested | **degraded** | accept-rate 1 of 3; 2 fabrications; verdict miscalibrated (REQUEST-CHANGES on a summary-line nit it inflated to P1) | manifest + `evidence/s4-ollama-cloud.md` |

**Step verdict: offloaded-clean.** Both lanes independently converged on the same genuine
finding — the §5.7 summary line (the chaperone's own consistency touch) still implied
unconditional artifact-write and routing. **Accepted** and fixed in-branch: 5.7 now splits the
closing summary by mode. Rejected with rationale: ollama F2 (claimed the no-saga scan-first guard
vanished — it survives verbatim in the diff context lines; fabricated absence), ollama F3
("~156-char line" — measured a logical sentence, not a physical line), agy F2–F4 line-length P3s
(measured correctly at 101–105 chars but against a stricter standard than the file keeps — 81
pre-existing lines exceed 100; the edit matches the existing wrap distribution). Cross-lane
convergence on the one real defect is the strongest reviewer signal this drill produced —
convergent independent review caught what the chaperone's own consistency pass introduced.

### S5 — PR-preparation

| Lane | Status | Disposition (manifest) | Verdict | Rework | Evidence |
|---|---|---|---|---|---|
| agy | _pending_ | | | | |
| ollama-cloud | _pending_ | | | | |

## Step verdicts + recommendations

_Filled at U6: per-step verdict, and for every `claude-irreducible` step a recommendation and a
revisit-when condition (AC3)._

## Tripwire machinery observations (#384, first real exercise)

**OBS-2 — wrapper false-positive: `success` + corroborating receipt on a zero-output run.**
S1/agy attempt 1: a transient 503 on agy's `loadCodeAssist` left the model table empty at flag
resolution ("model Gemini 3.5 Flash (High) is not recognized" — the string is still valid,
`agy models` lists it), the executor failed to construct, and agy exited cleanly having produced
nothing. `agy_delegate` mapped that to `status=success`, `agy_launched=true`, and emitted a
schema-valid receipt with **`bytes_produced: 0`** — so `dispatch()` returned
`observer_corroborated=true` and the manifest said `ran-as-requested` for a run that produced no
output. The tell was IN the receipt (`bytes_produced: 0`); corroboration checks only launch flag +
schema validity. Follow-up candidates (out of scope, R5): wrapper maps executor-construction
failure to a failure status; observer treats `bytes_produced == 0` as observer-NO for
prose-deliverable dispatches. Preserved evidence: manifest `drill-468-s1-agy-attempt1`, bundle
`drill-468-s1-agy-190129` (`agy.log` lines 97–131).

**OBS-3 — delegation markers are per-session, so lanes must serialize.** `delegation_state.arm()`
keys the liveness marker by session (disarm takes only `session_id`); dispatching both lanes
concurrently from one chaperone session would race arm/disarm and corrupt the audit window. The
drill serialized every lane pair. Same shape as #520 F4 (marker locking).

**OBS-4 — arming worked on both lanes.** `session_id` arming succeeded for `agy` and for
`ollama-cloud` (no `tripwire_unarmed` note on any manifest); `dispatch()` disarmed in its
`finally` every time — no stuck marker, chaperone never write-blocked.
