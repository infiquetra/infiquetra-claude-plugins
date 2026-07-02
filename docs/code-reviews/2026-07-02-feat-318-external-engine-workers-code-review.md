# Code review — feat/318-external-engine-workers

- **Target:** branch diff vs merge-base `e901ae1` (origin/main) · **Reviewed SHA:** `8d48e20`
  (round 1) → `dba707f` (round 2) → `6486726` (round-2 operator-approved scope expansion)
- **Mode:** programmatic (called by /work) · **Backend:** inline, 4 parallel read-only lenses
  (correctness, security, testing, maintainability — Explore agents, no fable subagents)
- **Round 1 model:** Sonnet 5 (session default; `model=` not set on dispatch — flagged post-hoc).
  **Round 2 model:** Opus 4.8 (explicit `model: "opus"` on all 4 lens dispatches, confirmed against
  each agent's raw transcript `"model":"claude-opus-4-8"` field, not self-report)
- **Blocked:** NO — all P1/P2 findings fixed in round 1 (commit `8d48e20`); round 2 re-verified
  both fixes independently correct and complete, and closed every in-diff P3 it surfaced plus the
  one round 1 left residual (commit `dba707f`). Two low-severity hardening findings in
  `engine_dispatch.py`/`engine_resolver.py` (outside #318's own diff scope) were fixed on explicit
  operator approval (commit `6486726`) — see Round 2 below.
- **Linked:** issue infiquetra/infiquetra-claude-plugins#318 · plan
  docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md · work-session
  docs/work-sessions/2026-07-02-team-execution-external-engine-workers.md

## Scope check: CLEAN

Intent (#318 U12 follow-up: chaperone-dispatch discriminator + contract docs for team-execution
external-engine workers) vs delivered: all 24 changed files map to plan units U1-U6 or their test
coverage. `.serena/project.yml` is an uncommitted pre-existing local modification (predates this
session, unrelated Serena tooling config), excluded from scope and from any future PR.

## Plan-completion audit: 6/6 DONE

U1 `bb85ac4` (chaperone protocol reference doc) · U2 `bb85ac4` (SKILL.md discriminator + `/plan`
tier table) · U3 `4f78e36` + `8d48e20` (engine_intent field, segment boundary rework, emitter
rows, review-driven test/resolution fixes) · U4 `111c8cf` (worker-manifest.md engine-worker leg)
· U5 `0bb77cb` (advisory external-second-opinion validator) · U6 `135a8c0` (release surfaces +
DECISIONS entry). All 5 issue acceptance criteria verified: AC1-2, AC4-5 confirmed DONE by diff
(manual CLI verification of the Workers-table rendering for both an explicit-engine and a
capability-routed unit); AC3 (manifest contract) is DONE at the **contract** level (worker-manifest.md
fully specifies attribution/disposition/claim-provenance) — live enforcement is inherently exercised
only when a real chaperone-worker run declares an engine-owned unit, which is outside this plan's
Implementation Units (no chaperone-agent runtime code was in scope; U1-U6 build the discriminator
and contract, matching the plan's explicit Scope Boundaries). Full suite 1635 passed, 0 failed.
ruff check / ruff format --check / mypy (plugins/ and plugins/+scripts/+tests/) clean.
bandit -r plugins/: only pre-existing house-pattern `assert`-based B101 notes, nothing new.

## Findings (validated inline by the driving session against cited evidence)

| # | Sev | File | Issue | Reviewer | Conf | Route | Outcome |
|---|-----|------|-------|----------|------|-------|---------|
| 1 | P1 | tests/test_saga_execution_spec.py (coverage gap) | No test proved two same-engine, different-variant units merge into one chaperone segment (KTD1's own "one resident chaperone per engine, not per variant") — a regression to per-variant or per-unit segmentation would have shipped silently | testing | 100 | safe_auto → review-fixer | **Fixed** — `test_segment_units_engine_and_capability_boundaries` added (`tests/test_workflow_emitter.py`), covering same-engine merge, capability interleaving, and engine-boundary-beats-file-path-boundary in one spec |
| 2 | P2 | plugins/saga/scripts/execution_spec.py:1301 | A same-engine segment's `engine_intent` was taken from `units[0]` only — silently discarding a disagreeing second unit's intent, with undefined behavior on refactor | correctness + testing (independent agreement) | 75 | manual → human | **Fixed** — `engine_intent` now resolves upgrade-only-max like `tier` does (`second-opinion` beats `offload`); `test_segment_units_engine_intent_upgrade_only_max` added |
| 3 | P2 | plugins/team-execution/skills/team-execution/references/external-engine-workers.md:34 | Cited `execution_spec.py:236-260` for `_validate_external_engine_selector`; actual function spans `:241-265` (the cited range starts inside the unrelated `_engine_registry_path` and truncates before the function's final check) | maintainability | 100 | safe_auto → review-fixer | **Fixed** — citation corrected |
| 4 | P3 | tests/test_saga_execution_spec.py | No test combines `engine`+`capability`+`engine_intent` together to confirm mutual-exclusion fires before the intent-vocabulary check; the mutual-exclusion rule itself is already covered by an existing test | testing | 75 | safe_auto → review-fixer | **Left as residual** — marginal value, mutual-exclusion already covered; operator discretion (P3) |

## Coverage

- Security lens: zero findings — every claim in `external-engine-workers.md` cross-checked against
  `engine_resolver.py`/`engine_dispatch.py`/`provenance_manifest.py` and confirmed accurate; no
  injection surface, no dangerous `.team-execution.json` default, engine payload forwarding verified
  byte-preserved (`_assert_payload_preserved`).
- Correctness lens: confirmed the "empty engine string" / "no-slash engine" edge cases are
  unreachable in practice (`Unit.validate()` requires `engine` to resolve against the registry);
  confirmed `emit_workflow_script` does not call `segment_units()` at all (uses `dependency_layers`),
  so the boundary-key rework cannot regress the other emitter; confirmed `to_dict()`/`from_dict()`
  round-trip `engine_intent` correctly in all three states.
- Maintainability lens: all other citations in `external-engine-workers.md`, `worker-manifest.md`,
  and the `/plan` SKILL.md tier rows verified accurate against current code; `WORKER_REFERENCES`
  packaging confirmed present in both `SKILL.md` and `README.md`.
- Suppressed below-75: 0 reported by lenses (self-gated at source).
- Residual risk: finding 4 (P3) left open by operator discretion — no gate impact.

> **Round 1 verdict: NOT BLOCKED.** Findings 1-3 fixed in commit `8d48e20` with new/updated test
> coverage; full suite re-verified green (1635 passed) after the fix round. Finding 4 (P3) left
> residual, non-blocking.

## Round 2 (Opus 4.8, reviewed SHA `453dd97`)

Re-ran the same 4-lens split, this time with `model: "opus"` set explicitly on every dispatch
(round 1 inherited the session default, Sonnet 5 — a miss caught when the operator asked what
model/effort round 1 used). Independent verification confirmed both round-1 fixes (segment-merge
test, `engine_intent` upgrade-only-max) are correct and complete, and the round-1 P2 citation fix
holds. Round 2 surfaced a further tail — all P3, none P0-P2:

| # | Sev | File | Issue | Lens | Conf | Outcome |
|---|-----|------|-------|------|------|---------|
| 5 | P3 | plugins/saga/scripts/execution_spec.py (segment_units comment) | Comment claimed "one resident chaperone per engine" as absolute; grouping is contiguous-only — a non-contiguous re-appearance of the same engine opens a new resident (`worker-agy-2`) | correctness | 50 | **Fixed** — comment corrected to state the contiguous-run scope explicitly |
| 6 | P3 | external-engine-workers.md:156 | Citation `worker-manifest.md:30-36` pointed at the section's lead-in prose, not the fenced `manifest_store.py write` command it quotes (`:37-41`) | maintainability | 60 | **Fixed** — citation corrected |
| 7 | P3 (round-1 residual, now confirmed) | tests/test_saga_execution_spec.py | No test proved `engine`+`capability` mutual-exclusion fires before the `engine_intent` vocabulary check | testing | 100 | **Fixed** — `test_engine_and_capability_mutual_exclusion_fires_before_intent_vocabulary` added, wrapping `from_dict()` (where the error actually surfaces), not `.validate()` |
| 8 | P3 | tests/test_saga_execution_spec.py | `engine_intent` defaults-to-offload was asserted only via the `capability` branch, never `engine` | testing | 90 | **Fixed** — `test_engine_intent_defaults_to_offload_when_omitted_for_engine_selector` added |
| 9 | P3 | tests/test_saga_execution_spec.py | Bad-vocabulary test's `match="engine_intent"` also matches the sibling "requires engine or capability" error — didn't pin the vocabulary branch specifically | testing | 60 | **Fixed** — tightened to `match="not in"`; added the capability-selector negative case too |
| 10 | P3 | plugins/saga/scripts/execution_spec.py (to_dict) | `to_dict()` omitting `engine_intent` for a plain Claude unit was untested | testing | 55 | **Fixed** — `test_engine_intent_omitted_from_to_dict_for_plain_claude_unit` added |
| 11 | P3 | tests/test_workflow_emitter.py | No test proved an all-`offload` same-engine segment stays `offload` (no spurious upgrade), or that the result is order-independent | testing | 40 | **Fixed** — `test_segment_units_engine_intent_agreement_does_not_spuriously_upgrade` added, covering both same-value agreement and reversed member order |
| 12 | P3 | plugins/saga/scripts/engine_dispatch.py:275-277, engine_resolver.py:320-329 | Byte-preservation/type guarantees (`_assert_payload_preserved` etc.) use bare `assert`, stripped under `python -O` | security | 50 | **Fixed** (commit `6486726`, operator-approved scope expansion beyond #318's own diff) — both guards now raise `DispatchError`/`RegistryError` explicitly instead of `assert` |
| 13 | P3 | plugins/saga/scripts/engine_dispatch.py:251-252 | `satisfy_gate`'s per-claim adjudication check is skipped entirely when the caller omits `manifest` (defaults `None`, early-returns) | security | 50 | **Fixed as documentation** (commit `6486726`) — making `manifest` mandatory would break its already-tested optional contract (`test_saga_engine_dispatch.py` asserts `satisfy_gate(verified)` with no manifest returns cleanly) and there is no live call site outside tests today; hardened the docstring to make the caller obligation explicit instead |

Security lens independently re-verified every safety claim in `external-engine-workers.md` against
the current code (no-write containment via hardcoded `mode`/`write_set`/`sandbox` in the dispatch
builders, `verified_by_claude is True` strict-identity gate, no raw `agy`/`codex` shell-out in any
of the three scripts named, selector values validated against the registry before reaching
worker-id construction, no credential contents crossing the chaperone→engine boundary) — all hold.

Full suite re-verified green after the round-2 fix commit (`dba707f`): 1640 passed (up from 1635),
ruff check / ruff format --check / mypy clean, bandit unchanged (only the pre-existing
`team_emitter.py` CLI B101 note).

> **Round 2 verdict: NOT BLOCKED.** Findings 5-11 fixed in commit `dba707f`. Findings 12-13 were
> outside #318's own diff scope; the operator explicitly approved fixing them anyway, closed in
> commit `6486726`. Route: **`/qa`** advisorily after merge, per the clean-review path.

Review complete
