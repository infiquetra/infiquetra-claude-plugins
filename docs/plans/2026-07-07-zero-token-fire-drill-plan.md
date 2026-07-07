---
title: Zero-token fire drill — canonical lifecycle loop on the $0 registry entries (#468)
type: docs
status: active
date: 2026-07-07
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json
---

# Zero-token fire drill — canonical lifecycle loop on the $0 registry entries (#468)

## Summary

Run ONE real lifecycle loop — spec-framing → plan → implement → review → PR-prep — on a small real
unit of work (the `/code-review` programmatic-mode append contradiction, QUEUED
`{#code-review-saga-scan-touchups}` Defect 2), attempting every offloadable step through BOTH $0
lanes: `agy/gemini-3.5-flash-high` (cost_speed_rank 1, AC1's named entry) and
`ollama-cloud/gpt-oss-120b` (rank 5, first-ever live dispatch on the newly wired key). Claude
verifies every output (never-gatekeeper). The deliverable is a published **irreducibility map**:
per-step × per-lane verdict + evidence, with recommendations and revisit-when conditions for every
step that stays Claude-irreducible.

This is an **exploration** (evidence + decision doc), not lane construction: zero changes to the
dispatch machinery (R5).

## Problem frame

The external-engine offload lane (#336) is built — registry, resolver, dispatch, receipts, and as
of today the #384 runtime tripwires — but nobody has measured which lifecycle steps the $0 tier can
actually carry. Until a real loop runs end-to-end on the cheapest entries, "offloadable" is a
hypothesis. The drill converts it to evidence, and doubles as the first real exercise of the #384
tripwire machinery (arm → dispatch → stop-audit → two-signal acceptance) under genuine work.

## Requirements

- **R1 (AC1).** Every offloadable step is dispatched through
  `engine_resolver.resolve({"role_kind": "worker", "engine": <selector>}, mode="dispatch",
  registry=registry)` (`role_kind` rides in the request dict — the resolver signature is
  `resolve(request, *, mode, registry)`, `plugins/saga/scripts/engine_resolver.py:191-197`;
  invocation shape per `external-engine-workers.md` §2) + `engine_dispatch.dispatch(...)` per the
  Dispatch recipe below, against the rank-1 entry `agy/gemini-3.5-flash-high`. Receipt rows are
  NOT auto-written — the recipe's persist step produces them; verify via
  `python3 plugins/saga/scripts/manifest_store.py --saga-id issue-468 list`.
- **R2 (KTD1).** Each step is additionally dispatched through `ollama-cloud/gpt-oss-120b`
  (transport `http`, via `plugins/saga/scripts/engine_bridge_http.py`) so the map carries per-lane
  verdicts. A lane failure is a recorded disposition, never a drill abort (KTD8).
- **R3 (AC2).** Minimum five lifecycle steps attempted: S1 spec-framing, S2 plan authoring,
  S3 implementation, S4 review, S5 PR-preparation.
- **R4 (AC3).** The irreducibility map is published with, per step × lane: verdict
  (`offloaded-clean` / `degraded` / `claude-irreducible`, KTD3), evidence link (manifest
  execution_id + tripwire audit record where present), rework fraction, and — for every
  irreducible step — a recommendation and a revisit-when condition.
- **R5 (AC5).** ZERO changes to `plugins/saga/references/engine-registry.yaml`,
  `plugins/saga/scripts/engine_resolver.py`, `plugins/saga/scripts/engine_dispatch.py`, or
  `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`. Bridge
  defects found mid-drill are recorded as dispositions and filed as follow-ups, not fixed in-drill.
- **R6 (AC4).** Never-gatekeeper: all gates (pytest, ruff pair, mypy) are run by Claude; engine
  outputs are advisory inputs Claude verifies before use; no engine output satisfies a gate.
  Dispatches run ungated in-process (no `gated=True` cross-process — #520 F1 constraint).
- **R7.** Key hygiene: `OLLAMA_API_KEY` resolves from the environment at request-build time only —
  never into receipts, dispositions, the map, or logs.
- **R8.** The drill unit lands production-quality: the Defect 2 fix ships with the saga plugin's
  release surfaces updated (plugin.json, marketplace.json, CHANGELOG, drift-guard pins — repo
  rule 6) and full gates green. This deliberately supersedes the issue's "Release-Surface
  Checklist: Not applicable" clause — that clause assumed the drill changes no plugin, but the
  chosen target changes the saga plugin.

## Key Technical Decisions

**KTD1 — Both lanes, agy rank-1 primary (operator-confirmed).** AC1's letter names the rank-1
entry; the operator wired `OLLAMA_API_KEY` expressly for this drill and normal operation, and the
ollama-cloud row has never been live-dispatched (ratings capped at "availability-gated smoke
only"). Dispatching every step down both lanes satisfies AC1 verbatim AND produces first live
receipts for the HTTP-bridge lane, at the marginal cost of a second chaperone pass per step.

**KTD2 — Drill target: `/code-review` Defect 2 (operator-confirmed after stale-draft re-triage).**
The originally recommended `{#marketplace-ci-guard}` is STALE — CI already guards parity three ways
(`.github/workflows/ci.yml:76` validator, `:102` generator `--check`, tri-lock
`tests/test_release_surface_parity.py`); the drill prunes that QUEUED entry. Defect 2 verified
still real: `plugins/saga/skills/code-review/SKILL.md` Phase 5.3 (":291") promises programmatic
mode does zero file writes with the caller owning persistence, while Phase 5.4 (":296") appends
`--review-paths docs/code-reviews/<...>.md` in its saga branch with no mode gate (its only
condition is "if and only if Phase 5.1 found a saga") — a path programmatic mode never created.
Fix shape: mode-gate the 5.4 append (programmatic callers own the saga write, as `/work` already
does in practice).

**KTD3 — Verdict rubric (per step × lane).** `offloaded-clean` = engine output accepted after
Claude verification with only trivial edits (rework < ~10% of the artifact). `degraded` = output
usable only after substantive Claude rework or a retry (rework ≥ ~10%, or a second dispatch
needed). `claude-irreducible` = output unusable, or the lane structurally cannot perform the step
(write capability, tool access, missing repo context). Step-level verdict = the best lane's
verdict; the map still shows both. Rework fraction is estimated as edited-lines / total-lines of
the accepted artifact and stated per disposition.

**KTD4 — Evidence fabric.** Per-dispatch: the manifest row (execution_id) under saga `issue-468`
via `manifest_store.py`, plus the #384 tripwire audit record (`.claude/delegation/audits/`) as
corroboration where the stop-audit fires. Dispositions are embedded in the map itself — one
durable artifact, no side workspace.

**KTD5 — Advisory-ungated dispatch posture.** All dispatches run without `satisfy_gate`
consumption; acceptance is Claude's verification decision recorded in the disposition. This honors
never-gatekeeper (R6) and stays clear of #520 F1 (process-local requeue counter).

**KTD6 — Map location: `docs/engineering-journal/narratives/2026-07-07-zero-token-fire-drill-irreducibility-map.md`.**
Precedent: the agy-as-coder dogfood narratives (`narratives/2026-06-28-agy-as-coder-dogfood-275.md`,
`narratives/2026-06-29-agy-as-coder-dogfood-277.md`) already host exactly this artifact shape
(drill story + evidence + verdicts).

**KTD7 — One branch, one PR, destination merge.** The Defect 2 fix + release surfaces + the map +
journal updates (LEARNINGS entry, QUEUED prune/shipped notes) ride one PR. The saga SKILL change is
a behavior-adjacent skill change → hard test gate applies (pytest, `ruff check .`,
`ruff format --check .`, mypy).

**KTD8 — Dispatch failure is data.** A resolver halt, bridge error, integrity divergence
(DELEGATION_INTEGRITY), or unusable output fails the STEP'S LANE, not the drill: record the
disposition with evidence and continue. Only a defect in the drill unit's own landing (U3 gates
red after Claude repair) blocks shipping.

## Implementation Units

Strictly sequential — each step consumes the verified artifact of the one before, exactly like the
real lifecycle it simulates.

**Dispatch recipe (every offload in U2–U5).** No in-repo driver calls
`engine_dispatch.dispatch()` today — the `/work` executor IS the driver, following
`external-engine-workers.md` §2–§5 exactly:

1. **Resolve:** `resolution = engine_resolver.resolve({"role_kind": "worker", "engine":
   "<agy|ollama-cloud>"}, mode="dispatch", registry=registry)` (§2). Explicit-engine selectors
   halt rather than substitute when unavailable (R26) — a halt is a KTD8 disposition, not an
   abort.
2. **Dispatch:** `evidence = engine_dispatch.dispatch(resolution, runner=<runner>,
   session_id=<this session's id>, workspace_root=<repo root>, gated=False, ...)`.
   `session_id` and `workspace_root` are REQUIRED for the drill's tripwire deliverable: arming
   only happens when `session_id` is passed (`plugins/saga/scripts/engine_dispatch.py:217-222`)
   and stop-audit corroboration needs `workspace_root` (`:254`); `dispatch()` disarms in a
   `finally` (`:227-231`) so the chaperone is never left blocked. `gated=False` keeps KTD5's
   advisory posture. Runner per lane: `engine_bridge_http.runner`
   (`plugins/saga/scripts/engine_bridge_http.py:57`) for ollama-cloud; the guarded
   `/agy:delegate` wrapper — never raw `agy` — for the agy lane
   (`external-engine-workers.md:104`).
3. **Persist the receipt:** write the dispatch manifest for this execution under saga
   `issue-468` per `external-engine-workers.md:159-176` (`record_dispatch_manifest` /
   `manifest_store.py --saga-id issue-468 write`). Rows are NOT written automatically — R1's
   receipts and the AC1 check exist only if this step runs after every dispatch.

### U1. Drill scaffold

**Goal:** branch from main; create the map skeleton (rubric table from KTD3, disposition template,
step roster) at the KTD6 path; align saga `issue-468`.

**Files:** `docs/engineering-journal/narratives/2026-07-07-zero-token-fire-drill-irreducibility-map.md` (new).

**Test expectation:** none — docs scaffold.

### U2. Steps S1 + S2 — spec-framing and plan authoring offloads

**Goal:** dispatch S1 ("write the issue-shaped spec for the Defect 2 fix from the QUEUED entry")
and S2 ("write the mini-plan: files, edit shape, test scenarios, release surfaces") through both
lanes; Claude verifies each output against the actual SKILL text; adjudicated artifacts become the
drill's working spec/plan; record 4 dispositions.

**Files:** map (dispositions + adjudicated spec/plan appendix).

**Test expectation:** none — evidence step; verification is Claude's adjudication recorded per KTD3.

### U3. Step S3 — implementation offload, then land the real fix

**Goal:** dispatch the implementation ("produce the exact SKILL.md 5.4 mode-gate edit + CHANGELOG
entry per the U2 plan") through both lanes under the evidence-only ceiling (engines return patches;
Claude applies — engines are never write-capable); Claude verifies/selects/repairs and lands the
fix plus saga release surfaces (plugin.json version bump, marketplace.json mirror, CHANGELOG,
drift-guard pins re-run); record 2 dispositions.

**Files:** `plugins/saga/skills/code-review/SKILL.md`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, map.

**Test scenarios** (existing suites are the guard-rail; no new test file warranted for a
markdown mode-gate):
- Release-surface tri-lock green after the bump (`tests/test_release_surface_parity.py`).
- Marketplace generator check green (`scripts/sync_marketplace.py --check` path in CI).
- Full suite green — the SKILL edit must not disturb any skill-parsing test.

### U4. Step S4 — review offload

**Goal:** dispatch an adversarial review of the U3 diff through both lanes; Claude adjudicates
every returned finding (accept → fix in-branch; reject → recorded rationale); record 2
dispositions. This step measures reviewer viability, the lane's strongest rated capability.

**Files:** map (+ any accepted-finding fixes to U3's files).

**Test expectation:** gates re-run if any accepted finding changes code.

### U5. Step S5 — PR-preparation offload

**Goal:** dispatch PR title/body drafting (diff summary, closes-refs, artifact links) through both
lanes; Claude verifies factual claims against the diff; record 2 dispositions.

**Files:** map.

**Test expectation:** none — prose artifact, Claude-verified.

### U6. Irreducibility map + journal writebacks

**Goal:** complete the map — 5 steps × 2 lanes = 10 dispositions, per-step verdicts,
recommendations + revisit-when per irreducible step, tripwire-machinery observations; add the
LEARNINGS entry (drill outcomes + any lane defects); prune stale QUEUED
`{#marketplace-ci-guard}` (→ ARCHIVE with the three-guards evidence) and mark
`{#code-review-saga-scan-touchups}` Defect 2 shipped; file follow-up issues for any lane defects
via mission-control.

**Files:** map, `docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/QUEUED.md`,
`docs/engineering-journal/ARCHIVE.md`.

**Test expectation:** none — docs.

### U7. Gates + ship

**Goal:** full hard gate (`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`); programmatic `/code-review` at
the PR-ready boundary; PR via ship ceremony; merge on operator word.

**Test expectation:** the gates themselves.

## Scope boundaries

**Out of scope (true non-goals):** any change to the R5 frozen files; tier/routing/registry-rating
changes (the map RECOMMENDS, `/retro`+operator decide); #520 hardening; changes to
`agy_delegate.py` / `codex_delegate.py` / `engine_bridge_http.py` (bridge defects → follow-up
issues); a second drill iteration; using the map as a gate anywhere.

**Deferred to follow-up work:** acting on the map's recommendations (registry rating adjustments,
tier-default changes); any lane-defect fixes discovered mid-drill.

## Risks

- **Ollama-cloud first live dispatch hits a bridge defect** — likely enough to plan for: the lane
  has only smoke coverage. Treatment: KTD8 (disposition + follow-up issue), drill continues on the
  agy lane.
- **128k context window on gpt-oss-120b** — steps are sized to a single QUEUED entry + one SKILL
  section; the resolver's `_context_window_halt` (R25) is the backstop and a halt is a recorded
  disposition.
- **Measurement contamination** — fixing lane machinery mid-drill would invalidate the map;
  R5/KTD8 pin the freeze.
- **Tripwire friction (#384 machinery, first real exercise)** — an armed-unproven block or
  DELEGATION_INTEGRITY halt mid-drill is EVIDENCE (recorded observation), and the documented
  CLI escape (`delegation_state.py disarm`) is the recovery path.

## Success metrics

- Map published with 10 dispositions, each carrying verdict + evidence ref + rework fraction.
- Every irreducible step has a recommendation + revisit-when.
- Defect 2 fix merged with green gates; both stale QUEUED entries resolved.
- At least one full dispatch per lane shows the complete receipt chain: manifest execution_id +
  tripwire audit record + disposition.
