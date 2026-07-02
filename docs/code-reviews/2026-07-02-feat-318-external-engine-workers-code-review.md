# Code review — feat/318-external-engine-workers

- **Target:** branch diff vs merge-base `e901ae1` (origin/main) · **Reviewed SHA:** `8d48e20`
- **Mode:** programmatic (called by /work) · **Backend:** inline, 4 parallel read-only lenses
  (correctness, security, testing, maintainability — Explore agents, no fable subagents)
- **Blocked:** NO — all P1/P2 findings fixed in the same work thread (commit `8d48e20`); one P3
  left as residual by operator-discretion
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

> **Verdict: NOT BLOCKED.** Findings 1-3 fixed in commit `8d48e20` with new/updated test coverage;
> full suite re-verified green (1635 passed) after the fix round. Finding 4 (P3) is residual,
> non-blocking. Route: **`/qa`** advisorily after merge, per the clean-review path.

Review complete
