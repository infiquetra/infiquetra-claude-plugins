---
title: "capability: continuous upstream drift detection — cron parity vs live source, fleet-wide sweep, halt-on-divergence, library-side mirror audit"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
slug: pf-upstream-drift-sweep
---

# capability: continuous upstream drift detection — cron parity vs live source, fleet-wide sweep, halt-on-divergence, library-side mirror audit

### Objective

Close the #222 blind spot for good: today's contract gate (`check_issue_contract_parity.py`) can only detect a *hand-edited* vendored copy, never a *moved* upstream source, so a fleet-wide silent-drift incident (343 "clean" cards passing a stale mirror) can recur indefinitely with the gate green the whole time. Add a scheduled, out-of-band sweep that (1) checks vendored artifacts against upstream HEAD on a cron, (2) walks every consumer repo in the fleet and files one scoped defect per drift found, (3) halts hard — files exactly one blocking issue — on the first checksum divergence rather than degrading or auto-reconciling, and (4) gives infiquetra-context-library's own CI a registry of fleet mirror sites so enforcement can also fire from the side that owns the source of truth. All four mechanisms attack the same blind spot from different angles; this issue merges them into one scheduled, opt-in (never PR-blocking) drift-detection surface.

### Intent

`plugins/mission-control/config/generated/check_issue_contract_parity.py:15-21` states its own design limit in the docstring: "Design (deliberately does NOT run the sdlc generator)... A match means the vendored bytes equal what the source generator LAST produced and pinned." That is structurally blind to the direction of drift that actually caused an incident: `infiquetra-sdlc`'s `gen_issue_contract.py` moving ahead of the pin while the vendored SHA256 manifest stays validly self-consistent. The recorded failure (grounding brief §3, item 1: "`validate_card_body` stale hand-copy [of the] real `card_validator.py` (343 'clean' cards failed [the] live contract, → #222), re-vendored `sdlc-schema.json`") happened across 4 independent repos and was caught only by a live incident, never by CI. Grounding brief §3 item 5 further notes the cross-repo learning loop that should have generalized this "never fired" — reinforcing that detection must be mechanized, not left to operator recall (grounding brief §3, pattern 7 in §7: "Stale memory/doc claims asserted fact, caught only by operator recall or lucky re-verification").

Four survivor ideas converge on this same gap and are absorbed here as facets:

- **`T14-F1-1`** (primary): a scheduled CI job that checks out `infiquetra-sdlc` at HEAD, runs the generator, and diffs its output against the vendored artifacts here — the direct fix for the docstring's stated blind spot.
- **`T14-F6-3`**: generalizes the same mechanism fleet-wide — a cron sweep that walks every consumer repo (not just this one), diffs each vendored contract copy against its source, and files one mission-control defect issue per drift, naming the offending file, pinned SHA, and live SHA.
- **`T14-F5-7`**: borrows the RTS lockstep-networking posture (halt on first desync rather than let clients silently diverge) and applies it here as `contract_checksum_lockstep.py` — on the *first* checksum mismatch it halts by opening one blocking issue naming the diverged repo, never auto-reconciling or warning-and-continuing. This deliberately mirrors the `/outcome` campaign's binding HALT-not-degrade decision, extending that posture from run status to contract integrity.
- **`H-F3-8`**: inverts the enforcement locus — instead of every consumer repo separately auditing itself, infiquetra-context-library's own CI (which already runs `context_census.py --check`, grounding brief §4) gains a mirror-site registry and audits registered fleet consumer mirrors directly, firing enforcement where authority over the source of truth actually lives, at zero added prompt-token cost to consumer repos.

This is deliberately opt-in and never blocks a PR: none of the four mechanisms run in the fast path (no `infiquetra-sdlc` or context-library checkout on every PR), preserving the existing hermetic consumer-side gate design while finally covering the drift direction the fast-path gate cannot see.

### Definition of Done

A scheduled (never PR-blocking) upstream-drift detection surface exists: a cron workflow diffs vendored contract artifacts against `infiquetra-sdlc` HEAD, a fleet-wide sweep files one scoped defect per drifted consumer repo, a lockstep checksum job halts on first divergence with exactly one blocking issue, and a mirror-site registry lets infiquetra-context-library's CI audit registered fleet mirrors. All four ship alongside — not in place of — the existing `check_issue_contract_parity.py` fast-path gate, with fixture-driven tests proving each detection path and confirming no workflow carries a `pull_request` trigger.

### Acceptance criteria
- [ ] A scheduled workflow (`.github/workflows/contract-upstream-drift.yml`, cron-triggered, never PR-triggered) plus `check_upstream_parity.py` clone `infiquetra-sdlc` at HEAD, run `gen_issue_contract.py`, and diff its output against this repo's vendored `issue_contract_data.py` / `issue_contract_shim.py`. Check: deliberately reverting a vendored artifact to a stale version and running the workflow opens a labeled drift issue naming the artifact and both SHAs; running it again with artifacts back in sync stays green.
- [ ] A fleet-wide drift-sweep script enumerates all consumer repos and diffs each one's vendored contract copy (`sdlc-schema.json`, `card_validator.py` mirrors, etc.) against its source, filing exactly one mission-control defect issue per detected drift naming the offending file, pinned SHA, and live SHA. Check: seeding a deliberate one-field drift in a fixture consumer repo and running the sweep produces exactly one correctly-scoped defect issue naming that repo and file; a fixture with no drift produces zero issues.
- [ ] `contract_checksum_lockstep.py` computes a normalized checksum of each consumer's effective contract, compares it against the canonical upstream source, and on the *first* mismatch halts by opening a single blocking issue naming the diverged repo — it does not auto-reconcile, does not warn-and-continue, and does not open more than one issue per run. Check: injecting a one-field divergence into a fixture consumer and running the job produces exactly one blocking issue naming that repo; an all-match fixture set stays green with zero issues opened.
- [ ] A mirror-site registry file in this repo lists every registered consumer mirror site (vendored `sdlc-schema.json`, `validate_card_body`, vocabulary tuples, etc.) with enough metadata (repo, path, source-of-truth path) for an external CI job to audit them without checking out this repo's full tree. Check: the registry file validates against a schema/lint (e.g. `python3 -m json.tool` plus a required-keys check) and lists at least the two known drift-prone artifacts named in grounding brief §3 item 1 (`card_validator.py` mirror, `sdlc-schema.json` mirror).
- [ ] infiquetra-context-library's existing census-job CI (`context_census.py --check`, grounding brief §4) is extended (via a follow-on PR to that repo, or a documented interface contract in this repo if cross-repo CI changes are out of scope for this PR — see Scope & non-goals) to walk this repo's mirror-site registry, diff each registered mirror against its source, and file a drift issue via mission-control on divergence. Check: seeding a drifted mirror entry and running the extended census job (or its local-simulation harness if the actual context-library CI change ships in a separate PR) opens a drift issue naming the drifted mirror.
- [ ] None of the four mechanisms run in any PR-triggered workflow — all are cron-scheduled or manually dispatched only. Check: `grep -L "pull_request" .github/workflows/contract-upstream-drift.yml` (and the sweep/lockstep workflow files) shows no `pull_request` trigger, only `schedule` and/or `workflow_dispatch`.

### Out-of-scope / non-goals
- Do NOT make any of these checks PR-blocking — they are scheduled/opt-in only, preserving the existing hermetic fast-path gate (`check_issue_contract_parity.py`) unchanged.
- Do NOT auto-reconcile or auto-re-vendor drifted artifacts — every mechanism here only detects and files an issue; a human or a separate follow-on fixes the drift.
- Do NOT replace or modify the existing byte-parity fast-path gate (`check_issue_contract_parity.py`) — this issue adds a slower, upstream-aware layer alongside it, per `T14-F1-1`'s framing.
- Do NOT build the "abolish contract mirrors" behavioral-parity migration (`H-F1-8`/`T14-F3-7`, tracked separately as `pf-abolish-contract-mirrors`) — this issue is about *detecting* drift in whatever mirrors exist today, not eliminating the mirror pattern itself.
- Do NOT implement the full context-library-side CI change in this PR if it requires write access to that repo's workflow files outside this session's scope — in that case, ship the registry file plus a documented, testable interface contract here, and open a follow-on issue in infiquetra-context-library referencing this issue's registry schema.
- Do NOT open more than one issue per sweep run per drifted artifact/repo — lockstep halt-on-first-divergence (`T14-F5-7`) and the sweep's per-drift emitter (`T14-F6-3`) must each be idempotent against re-runs (an already-open drift issue for the same artifact should be updated, not duplicated).

### Files expected to change

- `.github/workflows/contract-upstream-drift.yml` (new) — cron-scheduled workflow running the upstream-vs-vendored diff.
- `plugins/mission-control/scripts/check_upstream_parity.py` (new) — clones `infiquetra-sdlc`, runs `gen_issue_contract.py`, diffs against vendored artifacts.
- `plugins/mission-control/scripts/contract_checksum_lockstep.py` (new) — fleet-wide checksum computation and halt-on-first-mismatch issue filer.
- `plugins/mission-control/scripts/drift_sweep.py` or similar (new) — fleet-wide consumer-repo walk + per-drift defect emitter.
- `plugins/mission-control/config/mirror-site-registry.json` (new) — registry of registered consumer mirror sites consumable by context-library CI.
- `.github/workflows/contract-drift-sweep.yml` (new) — cron-scheduled workflow running the fleet sweep and lockstep checksum job.
- `plugins/mission-control/tests/test_upstream_parity.py`, `test_drift_sweep.py`, `test_checksum_lockstep.py` (new) — fixture-driven tests per acceptance criterion.
- `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/mission-control/CHANGELOG.md` — release-surface updates (see checklist below).

### Tests to add or update

- `plugins/mission-control/tests/test_upstream_parity.py::test_reverted_artifact_opens_drift_issue` — reverts a vendored artifact to a stale fixture, asserts a labeled drift issue is opened naming both SHAs.
- `plugins/mission-control/tests/test_upstream_parity.py::test_in_sync_stays_green` — asserts no issue opens when vendored artifacts match a fixture upstream HEAD.
- `plugins/mission-control/tests/test_drift_sweep.py::test_seeded_drift_files_scoped_defect` — seeds a one-field drift in a fixture consumer repo, asserts exactly one correctly-scoped defect issue naming that repo and file.
- `plugins/mission-control/tests/test_drift_sweep.py::test_no_drift_files_nothing` — asserts zero issues for an all-in-sync fixture set.
- `plugins/mission-control/tests/test_checksum_lockstep.py::test_one_field_divergence_halts_with_one_issue` — injects a one-field divergence, asserts exactly one blocking issue naming the diverged repo.
- `plugins/mission-control/tests/test_checksum_lockstep.py::test_all_match_stays_green` — asserts zero issues when all fixture checksums match.
- `plugins/mission-control/tests/test_mirror_registry.py::test_registry_schema_valid` — validates the registry file against its required-keys schema and asserts the two known drift-prone artifacts are present.

### Verification

```bash
# Upstream-vs-vendored parity (T14-F1-1)
uv run pytest plugins/mission-control/tests/test_upstream_parity.py -v

# Fleet-wide drift sweep (T14-F6-3)
uv run pytest plugins/mission-control/tests/test_drift_sweep.py -v

# Lockstep halt-on-first-divergence (T14-F5-7)
uv run pytest plugins/mission-control/tests/test_checksum_lockstep.py -v

# Mirror-site registry schema (H-F3-8)
uv run pytest plugins/mission-control/tests/test_mirror_registry.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; each fixture-seeded-drift test produces exactly the issue count and naming specified in its acceptance criterion; no workflow file added in this PR carries a `pull_request` trigger.

### Release-surface checklist

Because this changes `mission-control` plugin behavior (new scheduled scripts, new registry file, new workflows consumers may need to be aware of), update in the same PR:

- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the new drift-detection surface.
- [ ] `.claude-plugin/marketplace.json` entry synced to plugin.json version.
- [ ] `plugins/mission-control/CHANGELOG.md` entry documenting the four new drift-detection mechanisms and the mirror-site registry.
- [ ] Any existing version/metadata drift-guard tests (e.g. plugin.json vs marketplace.json parity tests) pass with the bumped version.

### Grounding References

- Absorbed ideas (survivors file `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` for `T14-F1-1`, `T14-F6-3`, `T14-F5-7`; `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` for `H-F3-8`):
  - `T14-F1-1` (primary) — "Upstream-live parity job: close the #222 disease the current gate leaves open." Basis: `plugins/mission-control/config/generated/check_issue_contract_parity.py:15-21` docstring — "Design (deliberately does NOT run the sdlc generator)... A match means the vendored bytes equal what the source generator LAST produced and pinned" — upstream advance is undetectable. Origin pain: grounding brief §3, `card_validator.py` 343 cards / #222 stale hand-mirror.
  - `T14-F6-3` (facet) — "Continuous cross-repo drift sweep: contract drift hunted, not stumbled upon." Basis: grounding brief §7 pattern 7: "Stale memory/doc claims asserted fact, caught only by operator recall or lucky re-verification (2 repos)"; grounding brief §3.3: "mission-control/saga contract copies drifting from source truth (2 repos)." Grounding brief §3 scanned 19 repos reactively to find this.
  - `T14-F5-7` (facet) — "RTS lockstep desync checksum: halt the fleet on first contract divergence, do not degrade." Basis: external — RTS lockstep networking desync detection (per-frame world-state checksums that halt on first divergence; Bettner & Terrano, "GDC 2001: 1500 Archers on a 28.8"), applied to align with the binding `/outcome` campaign HALT-not-degrade decision rather than contradict it.
  - `H-F3-8` (facet) — "Enforcement-locus inversion: the context library's CI audits the fleet's vendored mirrors, not the other way around." Basis (thin seed, reconstructed from grounding brief §4-6): grounding brief §4 — "Enforcement already exists *inside library*: `validate.yml` CI runs `check_docs.py` ... + `context_census.py --check` (keeps `llms.txt` honest)"; §4 notes what's "Absent: pull library into `mission-control:issue` / `saga:plan` creation; any ADR↔code-pattern lint; library repo's CI [auditing consumers]." This facet closes that absence by extending the existing census-job pattern to audit registered fleet mirror sites, firing enforcement where source-of-truth authority lives.
- Consolidation rationale (issue map, `issue-map-final.json`): "Four mechanisms for the same blind spot (#222: source moved ahead of the pin): scheduled upstream parity, cross-repo hunt filing defects, lockstep halt-on-first-divergence, and the context-library CI auditing registered fleet mirrors."
- Binding decision engaged: `/outcome` campaign's HALT-not-degrade posture (grounding brief §2) — `T14-F5-7`'s halt-on-first-mismatch design is explicitly framed as extending this decision from run status to contract integrity, not contradicting it.

### Executor Profile

- **Model**: sonnet
- **Effort**: high
- **Backend**: inline

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3, §4, §7, plus `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json` (`T14-F1-1`, `T14-F6-3`, `T14-F5-7`) and `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`H-F3-8`)
- Source type: ideation-survivor-consolidation
- Source title: pf-upstream-drift-sweep (issue-map-final.json)

### Context library links

_none_

### Inputs inventory

- `.github/workflows/contract-upstream-drift.yml`
- `plugins/mission-control/scripts/check_upstream_parity.py`
- `plugins/mission-control/scripts/contract_checksum_lockstep.py`
- `plugins/mission-control/scripts/drift_sweep.py`
- `plugins/mission-control/config/mirror-site-registry.json`
- `.github/workflows/contract-drift-sweep.yml`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/420
- Number: 420
- Created at: 2026-07-04T08:07:57.895170+00:00

