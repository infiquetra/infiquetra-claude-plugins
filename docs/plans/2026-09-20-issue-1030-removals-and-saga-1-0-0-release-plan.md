---
title: Issue 1030 — the removals, the team-execution archive, and the saga 1.0.0 release
type: refactor
status: active
date: 2026-09-20
origin: docs/analysis/2026-09-19-saga-simplification-review.md
backend: inline
---

# Issue 1030 — the removals, the team-execution archive, and the saga 1.0.0 release

## Summary

This plan removes eleven saga commands and the script families behind them, archives the
team-execution plugin, retires four hooks and two agents, deletes the tests of every removed
module, and ships the result as saga 1.0.0. It is the closing child of parent issue 1018: after its
own merge onto the integration branch `parent/1018` it opens the single pull request from
`parent/1018` to `main`, carries the one code review for the whole parent there, merges it, and
installs the release into both plugin trees.

The work is a deletion, but it is not only a deletion. The dependency graph inside
`plugins/saga/scripts/` is dense enough that six modules which survive today reach into machinery
that goes, so the card cannot be satisfied by removing whole files: six surviving modules must have
those reaches cut. That severance work, not the file deletion, is where this card's risk lives.

## Problem frame

The saga plugin enforces a lifecycle the source of truth does not require and the operator does not
run. Its 105 script files carry 60,133 lines at this plan's base commit, and more than half of that
belongs to subsystems the September operating record never invokes. Issues 1021 through 1029 and
issue 938 have now landed the replacements — the run record, the admission questionnaire, the roles
library, the roster helper, the slim run driver, the build loop, the integrate-and-release step, and
the continuation mechanics. Each of those cards deliberately left the old machinery in place so that
no card would remove a module another card still imported. This card is where the old machinery goes.

**Base for this plan.** Commit `61da4b1c` on the integration branch `parent/1018`, which is
`parent/1018` immediately after issue 1028 merged. Plugin versions there, read from each
`plugin.json` rather than taken on trust: saga 0.171.0, orchestrate 6.0.0, fleet-core 0.29.0,
cc-workflows 1.0.1, mission-control 2.19.0, agent-launcher 1.7.0, team-execution 3.2.0, deploy 0.2.1.

**Measured starting state**, all at `61da4b1c`:

| Measure | Value at the base | Target |
|---|---:|---|
| Files in `plugins/saga/commands/` | 24 | 14 |
| Directories in `plugins/saga/skills/` | 22 | 13 |
| Python files in `plugins/saga/scripts/` | 105 | about 34 |
| Lines in `plugins/saga/scripts/` | 60,133 | under 15,000 |
| Files in `plugins/saga/hooks/` (excluding `hooks.json`) | 12 | 8 |
| Files in `plugins/saga/agents/` | 2 | 0 |
| Test files in `tests/` | 302 | about 210 |

## Requirements

**R1.** Eleven commands are removed with their skill directories: `/outcome`, `/loop`, `/resume`,
`/handoff`, `/optimize`, `/pulse`, `/delegation-audit`, `/promote`, `/engines`, `/tier`,
`/fleet-doctor`. Fourteen command files remain — the thirteen commands the review keeps plus the
`/ceo-review` alias of `/founder-review`.

**R2.** The script families behind those commands are removed: the outcome coordinator, the engine
registry and dispatch family, the concurrency, lease, envelope, ceremony, receipt, teardown and undo
family, the reversibility certificate, the ledgers, the closure and completeness gates except the
consensus scorer, the spend readers, the delegation audit, and the session-forensics readers.

**R3.** Every surviving module that reaches into removed machinery has that reach cut, and every
surviving skill that names a removed script stops naming it. No surviving command may import a
module this card deletes.

**R4.** The four hooks the card names are removed with their registrations in
`plugins/saga/hooks/hooks.json`: the delegation tripwire, the delegation stop audit, the team-spawn
residency check, and the team teardown.

**R5.** Both saga agents are removed — `saga:mechanical-executor` and `saga:readonly-verifier` —
together with every registration, canary row, and drift test that names them.

**R6.** The team-execution plugin is archived: a final changelog entry pointing at the roles library,
then the directory and its marketplace entry go, and its vendored fleet-commons shim goes with it.

**R7.** The project instruction in `CLAUDE.md` that review-class agent spawns must use
`saga:readonly-verifier` with a worktree is replaced by "review roles run as roster sessions in their
own worktrees", and `plugins/saga/references/sandbox-spawn-sites.md` is deleted.

**R8.** `plugins/fleet-core/scripts/fleet_commons/` is shrunk to the modules still imported plus the
staffing component that issue 1021 landed.

**R9.** Every test of a removed module is deleted with it. No test is marked advisory, skipped, or
`xfail` to make the suite pass, and the gate's coverage contract against `.github/workflows/ci.yml`
stays intact.

**R10.** Every touched plugin's release surfaces move in the same pull request: the plugin manifest,
the marketplace registry, the changelog, and any version drift guard. saga goes to 1.0.0.

**R11.** The release is installed into both plugin trees, `~/.claude` and `~/.claude-company`, and
both are verified to report the same versions as the repository.

**R12.** The lines in `plugins/saga/scripts/` fall below 15,000 and the full gate exits 0 at the
release commit.

## Key technical decisions

**KTD1 — The card's "orchestrate 5.0.0" is stale twice over, and orchestrate takes no bump at all.**
The card was written when orchestrate was 4.5.0; issue 1025 has since taken it to 5.0.0 and issue
1028 to 6.0.0, both for subcommand removals, under the precedent recorded in DECISIONS as
`{#1028-orchestrate-subcommand-removal-is-major}`. More to the point, this card changes no
orchestrate file. The only saga script `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
names is `admission.py` (at `:1034`), which survives. A version bump on an untouched plugin is a
false signal to anyone reading the changelog, so orchestrate stays at 6.0.0. The same test applies to
agent-launcher: its only mention of anything removed is a historical line in its own changelog, so it
stays at 1.7.0. The rule this card follows is "the version moves when the plugin's files move", and
the version is re-read from `plugin.json` after every merge because identical version strings merge
silently.

**KTD2 — The Workflow emission trio moves to cc-workflows rather than being deleted.**
`plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py` loads saga's `execution_spec.py`
through `saga_spec_shim.py` at import time and imports `concurrency_governor` at `:41` and
`dispatch_settlement` at `:1396`. Deleting those three modules from saga would leave the
cc-workflows plugin unloadable. The simplification review says to remove the execution spec, and
issue 808 ruled that the Workflow backend is narrowed to explicit operator invocation but *not*
retired; both hold only if the three modules stop being saga's. They therefore move into
`plugins/cc-workflows/skills/cc-workflows/scripts/` as that plugin's own modules, the shim that
reached across the plugin boundary is deleted, and saga loses 5,496 lines and the whole
Workflow-emission surface. Nothing the card does not name is deleted. **This is the plan's
recommendation and the operator may overrule it** — see the open question at the end of this
document.

**KTD3 — The under-15,000-line criterion cannot be met by deleting whole files, and that is the
card's real content.** A transitive closure over the imports of the thirteen surviving commands,
their skills, the surviving hooks, `scripts/gate.sh` and `.github/workflows/ci.yml` pulls 78 of the
105 script files, because six surviving modules import removed machinery. Summing the recorded line
counts of exactly the modules U2 lists as kept, with no severance at all, still leaves about 15,800
lines — above the criterion before a single behaviour has been cut. The card is therefore
satisfied only by cutting those six reaches, which is unit U3 and is where the review effort should
go. If the count is still above 15,000 after every severance in U3 is done, the build stops and
reports to the operator; it does not reach for a module the card does not name.

**KTD4 — "Archived" means the final changelog entry is written before the directory is deleted, in
two commits within the same pull request.** A changelog that is deleted in the commit that would
carry its final entry says nothing to anyone. So: the first commit writes
`plugins/team-execution/CHANGELOG.md` at version 4.0.0 with the entry "Archived. The 25 reviewer,
tester and scanner prompts live on as roles in `plugins/agent-launcher/roles/`; the appsec-audit
content is the Investigator role's security variant", and bumps `plugin.json` to match. The second
commit deletes `plugins/team-execution/` and its `.claude-plugin/marketplace.json` entry. The entry
is then permanently retrievable at the first commit, and a durable pointer to it is written into
`docs/engineering-journal/DECISIONS.md` under today's heading, naming the commit, so a reader who
never thinks to run `git log` on a deleted path still finds it.

**KTD5 — `deploy_handoff.py` stays, though nothing in saga calls it any more.** The deploy plugin
reaches into it by path from `plugins/deploy/commands/deploy.md:16` and
`plugins/deploy/skills/deploy-state/SKILL.md:61-101`. It is the saga-to-deploy seam and its only
caller now lives in another plugin; removing it with `/handoff` would break the deploy plugin, which
this card does not name. `detect_deploy_strategy.py` stays with it for the same reason.

**KTD6 — The two engine-registry gate steps leave `ci.yml` and `gate.sh` together.**
`check_engine_registry.py` and `engine_registry_conformance.py` are invoked from
`.github/workflows/ci.yml` and `scripts/gate.sh`, and both are engine-registry family modules this
card removes. The step is removed from the workflow *first* and from the gate script second, so the
gate's coverage check against `ci.yml` — the property that makes a shortfall fail loudly rather than
report green — is never the thing that has to be relaxed. No step is marked advisory at any point.
`scripts/gate.sh` invokes exactly three saga scripts, at lines 185, 186 and 217. The first two are
the engine-registry pair this card removes; the third is
`plugins/saga/scripts/lint_gate_absence_contract.py`, which **stays**. An implementer removing gate
steps by grepping for "a saga script" would take the third with the first two, so the two engine
steps are removed by name, not by pattern.

**KTD7 — Three surviving skills instruct an agent to run scripts this card deletes, and all three are
repaired here rather than in a follow-up.** A surviving skill that tells an agent to run a deleted
script is the exact failure the importability guard cannot catch, because prose is not an import.
A grep of the thirteen surviving skills at this plan's base finds precisely three offenders, and no
others:

- **`/plan`.** `plugins/saga/skills/plan/SKILL.md` §5.2 and §5.2a name `spend_estimate.py`,
  `tier_defaults.py`, `tier_session.py` (as `/tier`), `engine_resolver.resolve`,
  `intent_envelope.seeded_tier` and the `cc-workflows-ultracode` backend. Issue 1026 explicitly left
  this prose for this card. Note that two of these sections are **generated regions** rendered from
  `plugins/saga/references/plan-save-contract.yaml` by `plan_save_contract.py`, guarded by
  `tests/test_saga_spec_consumer_row.py` — the contract file is edited and the region re-rendered,
  never hand-edited, or the guard fails.
- **`/retro`.** `SKILL.md` names `gate_divergence_reader.py` at `:215`, `outcome_costs.py` at `:239`
  and `override_rate_reader.py` at `:189`; `references/retro-passes.md` names `discover_sessions.py`
  at `:87` and `extract_session_skeleton.py` at `:88`. All five are removed by U2, and the review's
  R7 says `/retro` reads the run record and the journal instead. Its other four script references —
  `load_saga_context.py`, `manifest_reader.py`, `run_record.py` and `saga.py` — all survive.
- **`/work`.** `SKILL.md:521-524` tells an agent to store typed artifact pointers with
  `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`, a script that goes with
  the archived plugin in U6. The paragraph and the `--artifact-pointers` guidance around it go with
  it. Every other script `/work` names survives.

`/code-review` is clean: its five script references are `review_consensus.py`, `review_result.py`,
`review_roster.py`, `run_record.py` and agent-launcher's `roster.py`, all of which survive.

**KTD8 — The board vocabulary in this run follows what mission-control's allowed list permits, and
the discrepancy issue 1028 recorded is not re-litigated here.** Issue 1028 found that `Ready to
merge` and `Closeout` are live Operations options absent from `allowed_submissions`, and that review
acceptance has no row at all. That is the operator's to settle. This card submits only moves the
allowed list permits and records any move it could not submit.

## Implementation units

Each unit is independently landable on the branch `issue/1030` and runs the repository's mechanical
baseline before the next unit starts. Units U1 through U9 land in this worktree; U10 through U13 are
the later stages this card also owns.

### U1. The command and skill surface

**What:** Delete the eleven command files and the nine skill directories behind them, leaving
fourteen command files and thirteen skill directories.

**Files:** the eleven removed commands are carried by **ten** command files, not eleven: delete
`plugins/saga/commands/{outcome,loop,resume,handoff,optimize,pulse,promote,engines,tier,fleet-doctor}.md`.
`/delegation-audit` has no command file at the base — it is reached through its skill directory
alone — so twenty-four files minus ten leaves the fourteen the acceptance criterion asks for, and an
implementer who assumes eleven deletions will delete one file too many. Delete
`plugins/saga/skills/{outcome,loop,resume,handoff,optimize,pulse,delegation-audit,promote,fleet-doctor}/`
whole.

**Test scenarios:** `tests/test_command_surface.py` — a case asserting the command directory holds
exactly fourteen files and that each names a skill directory that exists; a case asserting none of
the eleven removed command names resolves. The guard names the removed commands in the same spelling
the acceptance criterion uses, so a partially reverted deletion fails on the name rather than on a
count.

**Test expectation:** the new cases fail on the base commit before any deletion — run them there and
watch them fail before making them pass.

### U2. The script families

**What:** Delete the script families behind the removed commands, and move the Workflow emission trio
to cc-workflows per KTD2.

**Families, by the card's own naming, with the module list each covers:**

| Family | Modules |
|---|---|
| Outcome coordinator | `outcome.py`, `outcome_board_sync`, `outcome_compat`, `outcome_costs`, `outcome_decompose`, `outcome_dispatcher`, `outcome_edges`, `outcome_gate_transport`, `outcome_github`, `outcome_intent`, `outcome_liveness`, `outcome_merge`, `outcome_orchestrator`, `outcome_projection`, `outcome_reconcile`, `outcome_report`, `outcome_spec`, `outcome_store`, `outcome_worktrees` |
| Engine registry and dispatch | `engine_benchmark`, `engine_bridge_http`, `engine_calibration`, `engine_dispatch`, `engine_onboarding`, `engine_overlay`, `engine_promotion`, `engine_recommend`, `engine_registry`, `engine_registry_cli`, `engine_registry_conformance`, `engine_resolver`, `engine_stale_report`, `check_engine_registry`, `capability_elo`, `provider_control_chart`, `bridge_signatures`, `chaperone_economics` |
| Concurrency, lease, envelope, ceremony, receipt, teardown, undo | `envelope_token`, `adjustment_envelope`, `handoff_envelope`, `team_teardown`, `liveness_events`, `reconcile`, `merge_watcher` — `concurrency_governor` is in this family but moves rather than being deleted, per KTD2 |
| Reversibility certificate | `reversibility_certificate` |
| Ledgers | `run_ledger`, `evidence_ledger`, `dispatch_settlement` |
| Closure and completeness gates, except the consensus scorer | `closure_gate`, `completeness_gate` — `review_consensus.py` is kept |
| Spend readers | `spend_authority`, `spend_estimate`, `spend_receipt`, `spend_retro`, `tier_efficacy`, `override_rate_reader`, `gate_divergence_reader` |
| Delegation audit | `delegation_audit_query` |
| Session forensics, with `/resume` | `discover_sessions`, `extract_session_skeleton`, `find_inflight_work` |
| Tier policy, migrated to fleet-core's staffing component by issue 1021 | `tier_defaults`, `tier_session` |
| Standalone command scripts | `fleet_doctor`, `pulse`, `promote_scan`, `render_docs_visuals`, `scaffold_checkpoint` |
| Moved to cc-workflows, not deleted (KTD2) | `execution_spec`, `concurrency_governor`, `dispatch_settlement` |

**Kept, and why, where it is not obvious:** `review_consensus.py` (the card keeps the consensus
scorer), `deploy_handoff.py` and `detect_deploy_strategy.py` (KTD5), `intent_envelope.py` (the
admission comment keeps the schema), `manifest_reader.py` / `manifest_store.py` /
`provenance_manifest.py` (the surviving `/qa` and `/retro` read manifests — confirm against the
`/qa` rewrite at the merge turn, see U11), `qa_health_score.py` (issue 1039 owns its removal, not
this card), `board_progression.py`, `reconcile_controller.py`, `merge_turn.py`, `release_step.py`,
`build_loop.py`, `run_record.py`, `admission.py`, `saga.py`, `saga_spore.py`,
`lint_gate_absence_contract.py`, `fleet_commons_shim.py`, the four plan-contract modules
(`plan_pre_answers.py`, `plan_save_contract.py`, `plan_save_proof.py`,
`plan_artifact_conformance.py`), the three review modules other than the scorer
(`review_roster.py`, `review_result.py`, and `review_consensus.py` above), `shaping_judgments.py`,
`status_card.py`, `lifecycle_state.py`, `lifecycle_review.py`, `issue_progress.py`,
`next_step_context.py`, `load_saga_context.py`, `parse_issue.py`, `discover_subissues.py`,
`journal_triggers.py`.

**Test scenarios:** `tests/test_removed_modules_are_gone.py` (new, the sibling the card names next to
`tests/test_no_lease_broker_readd.py`) — one parametrized case over every module name in the table
asserting the file does not exist and that `importlib` cannot import it from the scripts directory;
one case asserting the kept list above is still importable, so the guard cannot be satisfied by
deleting too much. Delete every `tests/test_*` file whose subject is a removed module, in the same
commit as the module.

**The new guard copies two patterns this repository already proved, rather than inventing a third.**
From `tests/test_no_lease_broker_readd.py`: scan the **shim-resolved** paths, not only the working
tree, because defect 642 showed a stale installed tree can resurrect a module a repository check
calls gone. From `tests/test_team_emitter_and_spec_table_removed.py`: check each module name in
**every syntax a caller could use** — a file that exists, an `import` statement, a
`spec_from_file_location` by path, and a bare mention on a command line in a skill — because a
removal test that only checks `not path.exists()` passes while a surviving skill still tells an
agent to run the script. That file also carries a self-test proving the scanner fires on each
actionable syntax and does not fire on a historical mention in a changelog; the new guard carries
the same pair, and the implementer watches both fail on the base before making them pass.

**Test expectation:** the new file fails on the base for every module before the deletions land.

### U3. The severances in surviving modules

**What:** Cut the reaches from surviving modules into removed machinery. This is the unit the plan
expects to take the most judgment and the one the code review should read first.

**The six reaches, each with the module that holds it:**

| Surviving module | What it reaches into | The cut |
|---|---|---|
| `review_consensus.py` (2,325 lines) | `outcome`, `evidence_ledger` | The scorer keeps its rubric and verdict arithmetic; the outcome-gate transport and the evidence-custody write path go |
| `saga.py` (1,906 lines) | `outcome`, the `ceremony_transition` and `ceremony_tier` fields issue 1027 recorded as deferred here | The ceremony fields and their readers go; the tick keeps its lifecycle phases |
| `status_card.py` (964 lines) | `outcome`, the ledger readers | The card renders from the run record alone |
| `board_progression.py` (1,119 lines) | `reversibility_certificate`, the legacy single-field path `tests/test_board_progression.py:577` records as this card's to remove | Both go; the pair submission stays |
| `lifecycle_state.py` (665 lines) | `run_ledger`, and `requires_hard_test_gate`, which issue 1027 recorded as deferred here with `/loop`'s two references | Both go |
| `reconcile_controller.py` (635 lines) | `reversibility_certificate`, `outcome_github`, `reconcile` | The certificate gate and the outcome-side reconciliation go; the idempotency ledger and replay key stay, because Phase 0.6 and 5.5 of `/plan` submit through them |

Two further reaches are smaller and belong here: `run_record.py` borrows `outcome_store`'s atomic
write primitive and must define its own (fleet-core's `audit_store.py` already made exactly this
choice, and says so in its own docstring at `:24`), and `saga_spore.py` reads `outcome_store` for the
freeze path and reads the run record instead.

**Checkpoint, measured not assumed:** after this unit, run
`find plugins/saga/scripts -name '*.py' | xargs cat | wc -l` and record the number in this card's
work-session note at `docs/work-sessions/2026-09-20-issue-1030-removals-and-release.md`. Under 15,000
continues; at or above 15,000 stops and reports (KTD3).

**Test scenarios:** the existing test files for each of the six modules keep their cases for the
behaviour that survives and lose the cases for the behaviour that goes; `tests/test_ledger_removal.py`
loses its `DEFERRED_TO_1030` block, whose whole subject is that these three ledgers are still present.

### U4. Hooks and agents

**What:** Delete `plugins/saga/hooks/{delegation_tripwire_hook.py,delegation_stop_audit_hook.py,team_spawn_residency_hook.py,team_teardown_hook.py}`
and their registrations in `plugins/saga/hooks/hooks.json` — the `Stop` and `SubagentStop` events lose
their only hook and the event keys go with them; `SessionStart` loses its team-residency matcher;
`SessionEnd` loses its only hook; `PreToolUse` loses the `Agent|Task` matcher. Delete
`plugins/saga/agents/{mechanical-executor.md,readonly-verifier.md}` and every registration of them in
`tools/canary_registry.json` and `tools/agent_spec.py`.

**Test scenarios:** `tests/test_agent_registration_drift.py` and `tests/test_wiring_canary.py` are
updated to assert the saga plugin registers no agents, and that the hook manifest carries exactly the
eight surviving hook files. Delete `tests/test_delegation_tripwire.py`,
`tests/test_team_spawn_residency_hook.py`, `tests/test_team_teardown.py` and the stop-audit tests.

**Test expectation:** the hook-manifest case fails on the base with twelve files before the deletions.

### U5. References, the documentation model, and the assets

**What:** Delete the reference documents of the removed families —
`adjustment-envelope.md`, `benchmark-loop.md`, `benchmark-suite.yaml`, `bridge-signatures.json`,
`concurrency-spawn-sites.md`, `dispatch-adapter-contract.md`, `engine-dispatch.md`,
`engine-output-trust-boundary.md`, `engine-registry.yaml`, `envelope-token.md`,
`evidence-write-sites.md`, `execution-spec.md`, `fleet-doctor-sources.md`,
`gate-divergence-instrumentation.md`, `liveness-consumer-sites.md`, `outcome-cross-runtime.md`,
`outcome-spec.md`, `run-fact-ledger.md`, `teardown-consumer-sites.md`, `worktree-reclamation.md`,
and `workflow-backend.md` (which moves to cc-workflows with the trio, per KTD2). The card also names
saga's private lens roster: issue 1001 has already deleted `lens-roster.json` and the scoring-policy
loader beside it, and a search of `plugins/saga/` at this plan's base finds no file with either name,
so this card's remaining work on the roster is only to remove the prose that still refers to it.
Delete the four SVG assets under `plugins/saga/docs/assets/` and the rows of
`plugins/saga/docs/model/saga-docs-model.yaml` that describe the removed commands and the old atlas.
`render_docs_visuals.py` goes with the assets (U2).

**Test scenarios:** `tests/test_saga_docs_coverage.py` is the guard over
`plugins/saga/docs/model/saga-docs-model.yaml`; it asserts the model names exactly the fourteen
surviving command files and no asset that no longer exists. `tests/test_saga_spec_consumer_row.py`
also reads generated regions rendered from `plugins/saga/references/plan-save-contract.yaml`, so
changes to `/plan`'s generated blocks (KTD7) are checked there.

### U6. The team-execution archive

**What:** Per KTD4, one commit writes the final changelog entry at version 4.0.0 and the next deletes
`plugins/team-execution/` whole — including its vendored
`skills/team-execution/scripts/fleet_commons_shim.py` — removes its entry from
`.claude-plugin/marketplace.json`, and writes the durable pointer into DECISIONS.

**Tests:** delete the `tests/test_team_execution_*.py` files and
`tests/test_team_spawn_residency_hook.py` and `tests/test_team_teardown.py`, which between them carry
the twenty-two tests already skipped with a reason naming this card's archive step — fourteen in
`tests/test_team_execution_consensus_advisory.py` and eight in
`tests/test_team_execution_consensus.py`. Add one case to the marketplace guard asserting no
marketplace entry names `team-execution` and that `plugins/team-execution` does not exist.

**One file whose name matches the pattern must NOT be deleted.**
`tests/test_team_emitter_and_spec_table_removed.py` is a re-add guard issue 1026 wrote: its subject
is that `team_emitter.py` and `spec_table.py` stay gone, not that the team-execution plugin exists.
A blanket `git rm tests/test_team_*.py` would delete the guard that stops the very modules this
release removes from coming back, which is the failure mode defect 642 named. It stays.

### U7. The sandbox-spawn rule

**What:** Replace the paragraph at `CLAUDE.md:9` with a sentence saying review roles run as roster
sessions in their own worktrees, naming `plugins/agent-launcher/roles/` as where those roles live and
the roster helper as what stands them up. Delete
`plugins/saga/references/sandbox-spawn-sites.md` and `tests/test_sandbox_spawn_sites.py`. Remove the
`saga:readonly-verifier` and `saga:mechanical-executor` mentions from the five surviving skills that
carry them: `plugins/saga/skills/{brainstorm,investigate,code-review,qa}/SKILL.md` and
`plugins/saga/skills/work/references/execution-strategy.md`.

**Test scenario:** a case asserting `grep -c readonly-verifier CLAUDE.md` is zero and that no file
under `plugins/saga/` names either agent. The guard spells both agent names exactly as the
acceptance criterion does.

### U8. The fleet-core shrink

**What:** Reduce `plugins/fleet-core/scripts/fleet_commons/` to the modules still imported after U2
plus the staffing component issue 1021 landed. `audit_store.py` (whose subject is the delegation and
evidence audit), `bridge_receipt.py`, `delegation_audit.py`, `delegation_state.py`,
`liveness_engine.py`, `output_attestation.py` and `concurrency_policy.py` are candidates for removal;
the implementer proves each by grep before deleting it, because fleet-commons is consumed by six
plugins and by both installed trees, not only by saga. `typesafe_client.py` keeps its behaviour and
loses only the docstring cross-reference to saga's deleted `engine_bridge_http.py`; `tier_palette.py`
loses the same kind of reference to `execution_spec.py`.

**Test scenarios:** the fleet-commons module-inventory test asserts the surviving set; the six
consuming plugins' shim tests stay green unchanged, which is the real evidence that nothing load
bearing left.

### U9. The release surfaces

**What:** Move every release surface in this pull request. Versions, each re-read from `plugin.json`
at the moment of the bump because identical version strings merge silently:

| Plugin | At the base | This release | Why |
|---|---|---|---|
| saga | 0.171.0 | **1.0.0** | The card names it; eleven commands and about 45,000 script lines leave a public surface |
| team-execution | 3.2.0 | **4.0.0**, then archived | KTD4 |
| fleet-core | 0.29.0 | **0.30.0** | The plugin's own precedent: version 0.24.0 deleted `lease_broker.py` and `orphan_evidence.py` whole — 10,203 lines with their suites — and took a minor bump, recorded under a `### Removed` heading in `plugins/fleet-core/CHANGELOG.md:311`. This is the same class of change |
| mission-control | 2.19.0 | **2.20.0** | `sdlc_manager.py` loses its readers for saga's `handoff_envelope.py` and `reversibility_certificate.py`; its own command surface is unchanged |
| cc-workflows | 1.0.1 | **2.0.0**, conditional | It gains the three modules and loses the cross-plugin shim; the emitter's import path changes, which is a break for anyone who loaded it (KTD2). **This row depends on the operator's answer to the second open question** — if cc-workflows is archived instead, it takes the team-execution treatment of KTD4 and leaves the marketplace |
| orchestrate | 6.0.0 | unchanged | This card changes no orchestrate file (KTD1) |
| agent-launcher | 1.7.0 | unchanged | Same test (KTD1) |
| deploy | 0.2.1 | unchanged | `deploy_handoff.py` stays (KTD5) |

Also: `.claude-plugin/marketplace.json` loses team-execution and carries the new versions; each
touched plugin's `CHANGELOG.md` gains an entry; the version drift guard tests are updated; and the
changelog records the measured before-and-after line and test counts, as the review's R26 asks.

**Test scenario:** the existing release-surface parity guard. Note the known trap: splitting one
release across two stacked pull requests makes the diff-aware guard demand a second version bump, and
`scripts/gate.sh` cannot catch it because the check needs a base commit. This card opens one pull
request, so the trap should not fire; if it does, bump again rather than weakening the guard.

### U10. The merge turn onto `parent/1018`

**What:** This card is the last child to merge. The coordinator continues this worktree; the merge
turn re-reads `origin/parent/1018`, merges `main` back into the branch if the integration branch has
moved, resolves ordinary conflicts, and merges `issue/1030` onto `parent/1018`. Issue 1039, the
`/qa` strategy catalogue, merges first and owns `plugins/saga/skills/qa/`, every `qa_*` script,
`plugins/saga/references/qa-catalogue.yaml`, and every `tests/test_qa_*` file.

**The one check this unit owes to issue 1039:** the `/qa` skill at this plan's base names
`scripts/manifest_reader.py` (`SKILL.md:254`), `scripts/issue_progress.py`
(`references/qa-report.md:174`), `scripts/run_record.py`, `scripts/saga.py`,
`scripts/status_card.py` and `scripts/qa_health_score.py`. All of those survive this card, so no
conflict is expected — but issue 1039 rewrites that skill, so after the merge, grep the merged `/qa`
skill for every module this card removed and repair any hit there rather than in issue 1039's files.

**Test expectation:** the full suite and `scripts/gate.sh` run by the coordinator after the merge, not
by this card.

### U11. The single pull request from `parent/1018` to `main`

**What:** Open one pull request from `parent/1018` to `main` carrying every child of parent issue
1018. Its body names each child issue and its unit, the measured before-and-after counts, the
hand-repair step for the two plugin trees, and the one open operator question this plan records.
No attribution lines of any kind.

### U12. The one code review, at that pull request

**What:** Run the installed `saga:code-review` at the parent pull request — one review for the whole
parent, which is what issues 1001, 1025, 1026, 1029 and 938 each deferred here. The lens declaration
admission recorded governs: the four always-on lenses plus `api-contract`, `agent-usability`,
`documentation-clarity`, `adversarial`, `reliability` and `deployment-infrastructure`.

**The acceptance rule, as the operator set it:** the review runs under a two-cycle cap. A score above
8.0 after three rounds is accepted, with one final repair round and no re-review. If there is no score
after three rounds, two rounds run at a higher tier and the result is then accepted. The reviewer is
never re-asked and the operator is never asked to adjudicate a score.

### U13. The merge, the release, and both plugin trees

**What:** Merge the parent pull request to `main`. Then install the release into both plugin trees and
verify both, because they are distinct directories that have diverged before — a release has updated
`~/.claude` within two minutes and left `~/.claude-company` stale, so hand repair is a mandatory step,
not a contingency.

```bash
for r in ~/.claude ~/.claude-company; do
  jq -r .version "$r/plugins/marketplaces/infiquetra-plugins/plugins/saga/.claude-plugin/plugin.json"
done
```

Both must print `1.0.0` and match every other bumped plugin. A version bump also silently re-arms
hand-neutralized hooks, so the environment variable `INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off` is the
control to use, never a patch of a cache file.

## Scope boundaries

**Out of scope, permanently.** The thirteen surviving commands' behaviour, `/qa`'s redesign (issue
1039), `/retro`, `/strategy`, `/founder-review`, and the sdlc amendments in
infiquetra/infiquetra-sdlc#170.

**Out of scope, deliberately not weakened.** The gate's coverage contract against `ci.yml`. No step
is marked advisory, no test is skipped or marked `xfail`, and no module is deleted without its tests.

**Deferred to follow-up work.** The board vocabulary discrepancy issue 1028 recorded (KTD8). The
sdlc crosswalk regeneration and the saga pin bump named in the review's R23, which live in the
lifecycle repository, not here.

**Not touched because the card does not name it.** Any file under `plugins/saga/skills/qa/`, any
`qa_*` script, `plugins/saga/references/qa-catalogue.yaml`, any `tests/test_qa_*` file — issue 1039
owns all of these and runs in parallel from the same base.

## Risk analysis and mitigation

**A surviving skill instructs an agent to run a deleted script.** The importability guard in U2 tests
modules, not prose, so it cannot catch this. Mitigation: KTD7 names the known prose sites, and the
check is a grep over the surviving skills for every removed module name, run as the last step of U9.

**The severance in U3 changes behaviour rather than removing it.** Cutting `review_consensus.py`'s
evidence-ledger write path is not the same as deleting a file. Mitigation: the existing tests for
each of the six modules keep every case for surviving behaviour, and the code review at U12 reads
this unit first.

**The two plugin trees diverge on install.** Recorded six times. Mitigation: U13 verifies both by
reading each tree's own `plugin.json`, and treats hand repair as a step rather than a contingency.

**The line-count criterion is not reached.** Mitigation: KTD3 makes it a measured checkpoint with a
stop, not an assumption.

## Questions answered from the card and the code

The `AskUserQuestion` tool is unavailable in this session, so every question the installed chain
would have put to the operator was answered from the card, the simplification review, or the code,
and each answer is recorded here. The one exception is named in the next section.

| Question | Answer | Where it came from |
|---|---|---|
| Admission: risk tier | `high` | The card's own Risk section |
| Admission: destination | `pr` | The pre-answer carrier from the run driver, validated by `plan_pre_answers.py`, and the work-session notes of issues 1001, 1025, 1026 and 938 |
| Admission: staffing overrides | none — the staffing component's defaults stand | No card names an override |
| Admission: lens declaration | Four always-on plus six conditional; five conditional lenses left out with a reason each | The change shape read against the eleven conditions in `plugins/saga/skills/code-review/references/lens-execution.md:50` |
| Admission: repair allowances | The default, 3 standard and 2 escalated | The documented default |
| Admission: response to unfinished functional testing | Bring the result to the operator | The card's Stop conditions say stop and report |
| Admission: change shape | `mixed` | The card changes code, tests, documentation and registry files |
| Plan Phase 0.4, is a plan document warranted | Yes | Thirteen units, eight recorded decisions, and the largest deletion in the repository's history |
| Plan Phase 0.5, scope class | Deep | Cross-cutting, high risk, and high blast radius |
| Plan Phase 5.1, destination | `pr`, applied from the carrier and not re-asked | The carrier |
| Plan Phase 5.2, execution backend | `inline`, applied from the carrier | The carrier; the skill's own rule that a Workflow backend is reachable only by explicit operator invocation |
| Plan Phase 5.2a, per-unit tiers | Not derived through `spend_estimate.py` or `tier_defaults.py` | Both are modules this card removes; admission already recorded the staffing plan, which the skill says is the authority for the roles it names |
| The card's "orchestrate 5.0.0" | Stale; orchestrate takes no bump | KTD1 |
| What "archived" means for team-execution | KTD4 | The card's own wording plus the fact that a deleted changelog carries nothing |

## The one operator decision this plan does not make

**The seven approval boundaries have no answer, and the build does not start until they do.**
Admission recorded twelve of the thirteen run-configuration parameters and seven of its eight
questions; `approval_scope` is outstanding. It is a grant only the operator can make — production
changes, destructive operations, secrets or credential changes, IAM or permission changes, billing or
cost-impacting actions, external commitments, and major team or process authority changes — and the
`/plan` skill says in as many words that a recorded grant nobody made is worse than a missing one.
Note that this card plausibly needs two of the seven: **destructive operations**, because it deletes
about 45,000 lines and a whole plugin, and **major team or process authority changes**, because it
retires the project instruction that governs how every review-class agent spawn in this repository is
sandboxed.

**The question to put:** for each of the seven approval boundaries, what scope is granted for issue
1030, or none?

**A second question the operator may want to answer at the same time:** KTD2 proposes moving the
three Workflow-emission modules into cc-workflows rather than deleting them, because deleting them
would make the cc-workflows plugin unloadable and the card does not name that plugin. The alternative
is to archive cc-workflows in this release the way team-execution is archived. The plan's
recommendation is the move; the alternative is one sentence away if the operator prefers it.

**What happens if neither question is answered when the build reaches them.** Both stop and report;
neither is answered by an implementer's judgment. For the approval boundaries, the `/plan` skill
already states the rule and this plan does not soften it: a recorded grant nobody made is worse than
a missing one. For the cc-workflows question, the build may land units U1 and U3 through U9 in full,
because none of them touches the three modules, and stops at the point in U2 where the trio would
move — with everything else green and the one decision named. That ordering is deliberate: it keeps
the card's work available to the operator rather than blocking all of it behind one answer.

## Verification

```bash
ls plugins/saga/commands | wc -l                                  # 14
find plugins/saga/scripts -name '*.py' | xargs cat | wc -l        # under 15000
test ! -d plugins/team-execution
jq -r '.plugins[].name' .claude-plugin/marketplace.json | grep -c team-execution   # 0
grep -c "readonly-verifier" CLAUDE.md                             # 0
test ! -f plugins/saga/references/sandbox-spawn-sites.md
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh; cat /tmp/gate-run/result.txt
for r in ~/.claude ~/.claude-company; do
  jq -r .version "$r/plugins/marketplaces/infiquetra-plugins/plugins/saga/.claude-plugin/plugin.json"
done
```
