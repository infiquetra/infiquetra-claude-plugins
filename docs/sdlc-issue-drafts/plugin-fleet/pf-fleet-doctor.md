---
title: "capability: fleet doctor — one derived-on-read audit for leaked resources, dead wiring, and receiptless delegations"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
tier: quick-win
objective: Govern fleet concurrency and reclaim leaked resources
wave: wave-1
---

# capability: fleet doctor — one derived-on-read audit for leaked resources, dead wiring, and receiptless delegations

### Objective

Ship one read-only diagnostic command — `fleet doctor` — that scans the fleet's existing
worktree registry, dispatch/provenance manifests, and delegation-receipt records and prints a
single derived-on-read health report naming three disease classes the fleet's own teardown and
reclamation machinery is supposed to prevent but has no independent auditor for today: stale
worktrees, unledgered spawns, and receiptless bridge delegations. The auditor performs zero
mutations and exits non-zero when it finds a problem, so it is usable from CI or cron as a
tripwire, not just an interactive command.

### Problem / motivation

The fleet has several mechanisms that are each supposed to prevent a specific leak, but no
single place reports whether any of them actually held — and there is direct, dated evidence
that at least one has already failed silently.

- **A live instance of the disease this issue targets, found during this repo's own grounding
  pass.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88` records "15 stale
  abandoned saga worktrees in `.worktrees/` inflating the repo 10x+" — the exact
  stale-worktree failure mode, discovered by manual inspection, not by any standing check.
  The same line calls this "the same disease as team-execution's missing Step B8"
  (teardown/reclamation), i.e. it is not an isolated incident but a recurring pattern.
- **The worktree registry exists and is inspectable, but nothing audits it end-to-end.**
  `plugins/saga/scripts/outcome_worktrees.py` already has `read_registry()` (`:124`),
  `live_worktrees()` (`:162`), and `reap_worktree()` (`:254`) — the primitives a doctor needs
  already exist as a registry-vs-filesystem reconciliation, but they are only ever invoked from
  inside `/outcome`'s own lifecycle (`harvest_worktrees()`, `:297`), never as a standalone,
  independently-runnable audit a human or CI job can call without running an outcome.
- **Dispatch/provenance manifests exist per-call, not fleet-wide.** `build_dispatch_manifest()`
  and `record_dispatch_manifest()` (`plugins/saga/scripts/engine_dispatch.py:163-233`) write a
  `provenance_manifest.Manifest` (`plugins/saga/scripts/provenance_manifest.py`) for each engine
  dispatch, and `satisfy_gate()` (`:281-303`) already refuses to let unverified advisory evidence
  satisfy a gate — but nothing walks the set of manifests fleet-wide to ask "does every spawn we
  can see have a matching, well-formed manifest, or are there unledgered spawns this reconciler
  never learned about?"
- **Delegation receipts are a recognized, recurring pain with no independent checker.**
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-104` names "silent no-ops in
  delegation & dead wiring" as recurring-pain theme 1 (5+ journal learnings: agy silent
  Claude-fallback, dead-wiring producer+consumer, test-shape-masks-dead-wiring, fake-adapter
  mismatch) and explicitly calls for "did it actually run/persist" verification on any
  bridge/delegation idea. No standing command answers that question today; each incident so far
  was caught by an operator noticing after the fact.
- **The auditor must stay independent of what it audits, by design.** This issue's
  consolidation rationale (from the issue-map) is explicit: fleet doctor is "deliberately not
  merged into" the teardown/reclamation or manifest-writing mechanisms themselves, "so the
  auditor is independent of the mechanisms it audits" — a doctor that shares code with the thing
  that might be leaking cannot be trusted to catch that leak.

## Definition of Done

A CLI/skill command (`fleet doctor`, proposed as a new script callable from `saga` or as a
standalone repo-root script) that, in one pass and with zero mutations:

1. Reconciles the worktree registry (`outcome_worktrees.read_registry()` /
   `live_worktrees()`) against the actual filesystem state under `.worktrees/` and reports any
   worktree that is registry-absent-but-filesystem-present (stale/orphaned) or
   registry-present-but-filesystem-absent (dangling registry entry).
2. Walks recorded dispatch/provenance manifests (`provenance_manifest.Manifest` records written
   by `engine_dispatch.record_dispatch_manifest()`) against the set of spawns the fleet can
   independently observe (e.g. active/recent saga or team-execution runs) and reports any spawn
   with no matching manifest ("unledgered spawn").
3. Walks recorded delegation records for bridge/engine calls (e.g. `agy`/`codex` dispatch calls)
   and reports any delegation with no corresponding receipt — "did it actually run and persist"
   — as a receiptless delegation.
4. Prints one derived-on-read report (never a committed/stored status — consistent with the
   fleet's existing `/outcome` derived-on-read decision) naming every finding across the three
   classes, with zero writes to any registry, manifest, or worktree during the scan.
5. Exits `0` when clean and a distinct non-zero code when any finding exists, so the same
   command works as an interactive tool and as a CI/cron tripwire.

### Acceptance criteria
- [ ] **Stale-worktree detection (disease class 1).** Given a `.worktrees/` directory containing
      a worktree with no matching registry entry (reproducing the 15-stale-worktree finding at
      `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`), `fleet doctor` reports it by
      name and path. Check: `uv run pytest tests/test_fleet_doctor.py -k stale_worktree` → passes.
- [ ] **Dangling-registry detection (disease class 1, inverse case).** Given a registry entry
      whose worktree path no longer exists on disk, `fleet doctor` reports the dangling entry
      separately from the stale-worktree case (they are opposite-direction reconciliation
      failures and must not be collapsed into one message).
      Check: `uv run pytest tests/test_fleet_doctor.py -k dangling_registry_entry` → passes.
- [ ] **Unledgered-spawn detection (disease class 2).** Given a simulated spawn with no matching
      `provenance_manifest.Manifest` record, `fleet doctor` reports it as an unledgered spawn
      naming the spawn identifier; given a spawn with a matching, well-formed manifest, it is not
      reported. Check: `uv run pytest tests/test_fleet_doctor.py -k unledgered_spawn` → passes.
- [ ] **Receiptless-delegation detection (disease class 3).** Given a simulated bridge/engine
      delegation call with no corresponding receipt record, `fleet doctor` reports it as a
      receiptless delegation; given a delegation with a persisted receipt, it is not reported.
      Check: `uv run pytest tests/test_fleet_doctor.py -k receiptless_delegation` → passes.
- [ ] **Read-only by construction.** A test asserts the registry file, manifest files, and
      `.worktrees/` filesystem state are byte-identical before and after a `fleet doctor` run
      against a fixture with findings in all three classes — the scan itself never mutates
      anything it inspects. Check: `uv run pytest tests/test_fleet_doctor.py -k read_only_scan` →
      passes.
- [ ] **Exit code reflects findings for CI/cron use.** A clean fixture (no findings) exits `0`;
      a fixture with at least one finding in any class exits a distinct non-zero code, and the
      printed report names every finding (no swallowed/truncated findings).
      Check: `python3 plugins/saga/scripts/fleet_doctor.py --fixture tests/fixtures/fleet_doctor_clean` → exit `0`;
      `python3 plugins/saga/scripts/fleet_doctor.py --fixture tests/fixtures/fleet_doctor_dirty` → exit `1`, output names all three finding classes.
- [ ] **Derived-on-read only — no new committed status field.** A test/code-review check
      confirms `fleet doctor` writes no new status field to any store; its report is computed
      fresh on every invocation, consistent with the fleet's existing `/outcome`
      derived-on-read-status decision.
      Check: `uv run pytest tests/test_fleet_doctor.py -k no_persisted_status` → passes.
- [ ] **Full suite, format, lint, types, and security stay green.**
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

### Out-of-scope / non-goals
In scope: one new read-only audit command reconciling three existing data sources (worktree
registry + filesystem, dispatch/provenance manifests, delegation receipts) into one derived
report with a CI/cron-usable exit code.

Out of scope (do not do in this issue):

- **Any reclamation or teardown action.** `fleet doctor` never reaps a worktree, never deletes a
  stale registry entry, never retries a receiptless delegation. It only reports. Actually
  fixing what it finds (e.g. `reap_worktree()`, `plugins/saga/scripts/outcome_worktrees.py:254`)
  is existing, separate machinery this issue does not modify or invoke destructively.
- **Building or hardening the teardown/reclamation gate itself** (team-execution's Step B8 /
  non-skippable exit-invariant work). That is a distinct, already-identified capability
  (`T6-F2-1`, kept separately in the same theme) — fleet doctor is deliberately independent of
  it, not a replacement for it.
- **A standing/scheduled monitoring loop.** v1 is an on-demand command runnable from a shell,
  CI job, or cron entry an operator configures; this issue does not add a new scheduler,
  dashboard, or alerting channel.
- **New delegation-receipt schema design.** If a formal delegation-receipt contract does not yet
  exist as a first-class schema, this issue consumes whatever receipt/record shape the fleet
  already persists for bridge calls (extending `record_dispatch_manifest()`'s existing shape if
  needed) rather than designing a new receipt contract from scratch — that is a separate,
  narrower concern if it turns out no receipt exists to check at all.
- **Any change to `satisfy_gate()`'s existing external-engine verification behavior**
  (`plugins/saga/scripts/engine_dispatch.py:281-303`) — referenced as prior art for
  "structural refusal, not prompt discipline," not modified here.

## Grounding References

- **Absorbed idea `G-hybrids-7`** (primary) — "fleet doctor: one derived-on-read audit of leaked
  resources, dead wiring, and receiptless delegations." `dod_sketch`: "A CLI/skill command that
  scans worktrees, lease/reclamation ledgers, spawn manifests, and delegation receipts and prints
  a derived-on-read health report; zero mutations." Basis: theme T6 (teardown/reclamation +
  liveness), frame `gap-hybrids`, axis `fleet-doctor`; consolidation rationale explicit in the
  issue map: "Stands alone: a read-only diagnostic that reports what the teardown/lease
  machinery should have prevented — deliberately not merged into them so the auditor is
  independent of the mechanisms it audits."
- **Subsumed duplicate `T6-F1-7`** — "fleet ps — one-shot inventory of running/held/leaked"
  (theme T6, frame F1, axis `state-visibility`), killed as a duplicate with
  `kept_duplicate_of: G-hybrids-7`: "Duplicate read-only cross-source inventory; the kept
  fleet-doctor hybrid subsumes it with three lenses over the same evidence pass." Its
  state-visibility intent is fully carried by this issue's three-class report.
- **Hygiene finding grounding disease class 1** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`: "15 stale abandoned saga
  worktrees in `.worktrees/` inflating the repo 10x+ → direct evidence for theme 6
  (teardown/reclamation), same disease as team-execution's missing Step B8."
- **Recurring-pain theme grounding disease classes 2 and 3** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-104` (recurring-pain theme 1,
  "silent no-ops in delegation & dead wiring," 5+ journal learnings) — any bridge/delegation idea
  needs "did it actually run/persist" verification, which is exactly what disease classes 2 and
  3 check for.
- **Existing primitives this issue reuses without modifying:**
  `plugins/saga/scripts/outcome_worktrees.py` (`read_registry()` `:124`, `live_worktrees()`
  `:162`, `reap_worktree()` `:254`) for disease class 1;
  `plugins/saga/scripts/engine_dispatch.py` (`build_dispatch_manifest()` `:163`,
  `record_dispatch_manifest()` `:205`, `satisfy_gate()` `:281-303`) and
  `plugins/saga/scripts/provenance_manifest.py` for disease classes 2 and 3.
- **Binding decision this issue must respect** — `/outcome` campaign's derived-on-read-status
  (never committed status fields) decision, referenced in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:44` and `:48`: `fleet doctor`'s report is
  computed fresh on every run, never written back as a persisted status field.
- **`{#plugin-portfolio-groom-17-to-7}`** — plugin sprawl carries a consolidation burden of
  proof; this issue ships as a script/skill inside the existing `saga` plugin (reusing its
  existing worktree/manifest modules) rather than as a new plugin.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** this is a read-only reconciliation command over three already-existing,
  well-understood data sources (worktree registry, provenance manifests, delegation records) with
  a fully specified target shape (three finding classes, one report, exit-code contract) and no
  architectural judgment call — sonnet at medium effort is sufficient; no external-engine
  involvement is needed since the work is a straight import-and-reconcile task against modules
  already in this repo.

### Release-surface checklist

This issue adds a new command surface to the `saga` plugin (no change to any existing command's
behavior). Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new `fleet doctor` command
      surface).
- [ ] `.claude-plugin/marketplace.json` — reflect the version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new read-only fleet-doctor audit command.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. a marketplace/plugin.json
      parity test) re-run green after the bump.
- [ ] `docs/engineering-journal/LEARNINGS.md` — dated entry recording the 15-stale-worktree
      hygiene finding as the concrete evidence this capability was built to catch going forward,
      with a pointer to the new `fleet doctor` command as the durable fix (not just a one-time
      manual cleanup).

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/fleet_doctor.py` — new read-only audit command (proposed path); imports
  `outcome_worktrees.read_registry()` / `live_worktrees()`, `engine_dispatch.record_dispatch_manifest()`-written
  `provenance_manifest.Manifest` records, and existing delegation-receipt records without
  modifying any of those modules.
- `plugins/saga/skills/fleet-doctor/SKILL.md` — new skill wiring the command as an operator-facing
  entry point (proposed path; naming/placement TBD by `/plan`).
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version sync.
- `plugins/saga/CHANGELOG.md` — entry for the new command.
- `tests/test_fleet_doctor.py` — new: stale-worktree, dangling-registry-entry, unledgered-spawn,
  receiptless-delegation, read-only-scan, exit-code, and no-persisted-status cases.
- `tests/fixtures/fleet_doctor_clean/`, `tests/fixtures/fleet_doctor_dirty/` — fixture directories
  for the CI/cron exit-code check.
- `docs/engineering-journal/LEARNINGS.md` — dated entry per the release-surface checklist above.

### Tests to add or update

- Stale-worktree and dangling-registry-entry reconciliation, both directions, reported as
  distinct finding classes.
- Unledgered-spawn detection against `provenance_manifest.Manifest` records.
- Receiptless-delegation detection against existing delegation/receipt records.
- Read-only invariant: registry/manifest/filesystem state byte-identical before and after a scan.
- Exit-code contract: `0` on clean, distinct non-zero on any finding.
- No new persisted/committed status field is written anywhere by the scan.
- Release-surface drift-guard test (plugin.json/marketplace.json version parity) re-run green.

### Verification

```bash
# New fleet-doctor unit tests
uv run pytest tests/test_fleet_doctor.py -v

# Exit-code contract against fixtures
python3 plugins/saga/scripts/fleet_doctor.py --fixture tests/fixtures/fleet_doctor_clean; echo "exit: $?"
python3 plugins/saga/scripts/fleet_doctor.py --fixture tests/fixtures/fleet_doctor_dirty; echo "exit: $?"

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; clean fixture exits `0`; dirty fixture exits non-zero and names findings in
all three disease classes (stale worktree, unledgered spawn, receiptless delegation).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json (`G-hybrids-7`)
- Source type: issue-map
- Source title: fleet doctor: one derived-on-read audit command for leaked resources, dead wiring, and receiptless delegations

### Context library links

_none_

### Intent

The fleet has several mechanisms that are each supposed to prevent a specific leak, but no single place reports whether any of them actually held — and there is direct, dated evidence that at least one has already failed silently.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/353
- Number: 353
- Created at: 2026-07-04T07:47:25.830546+00:00

