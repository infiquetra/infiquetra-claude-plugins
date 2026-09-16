---
title: Mission Control alignment — finite independent test plan
type: test
status: active
date: 2026-09-13
origin: docs/plans/2026-09-13-mission-control-alignment-test-scenarios.md
candidate: ea7963a4bbf735b7179bd2d2605af740a1f8c2e7
scenario_count: 23
---

# Mission Control alignment — finite independent test plan

## Summary and authority

This is the independent, finite test contract for Mission Control alignment in
`infiquetra-claude-plugins` at candidate commit
`ea7963a4bbf735b7179bd2d2605af740a1f8c2e7`. It covers all **23** Test Author scenarios:
four for issue #999, nine for issue #1000, and ten for issue #942. The detailed source cases are in
[Test Author scenarios](2026-09-13-mission-control-alignment-test-scenarios.md); the corresponding
code sequence is in [the implementation plan](2026-09-13-mission-control-alignment-implementation-plan.md).
This document neither changes production code nor accepts its own plan.

The Test Author seat `w86:p8` authors the new tests before the Dev seat `w86:p9` changes production.
The Dev updates old fixtures and pinned oracles only after taking explicit file custody. The
independent Test seat `w86:p5` later judges actual installed-plugin behavior under separate
acceptance authority; a pytest pass alone is not that judgment. No test here calls live GitHub,
mutates a board, or runs label synchronization.

## Pinned inputs and test harness

| Input | Pin or fixture | Evidence rule |
| --- | --- | --- |
| Plugin base | `ea7963a4bbf735b7179bd2d2605af740a1f8c2e7` | Keep candidate identity in every run report; rebase requires retesting. |
| SDLC schema | `infiquetra-sdlc` commit `67845cdd19948c9c10608436174d11a9b80d43ca`, schema version `2026-09-07.5` | Source JSON SHA-256 `5a8c0c93e022b8f48f0e10745f0a7871e636a07458892985501cfb6216de65b7`; generated modules use the same commit. |
| F-CORE | Always-required actionable body from `test_issue_prepare.py`, without Risk | Must fail after U2 specifically because `### Risk` is absent. |
| F-RISK and F-VALID | `### Risk`, exact first-line tier and one sentence; add conditional trio for high and very-high | Labels or sidecar metadata cannot substitute for the body field. |
| F-BRAINSTORM-PENDING | Real `docs/brainstorms/*.md` with YAML frontmatter `maturity: pending-confirmation` | Read from disk through actual prepare/source path. |
| F-DRAFT-BARE | Real `docs/sdlc-issue-drafts/*.md` with sidecar missing `handoff_maturity` | Saga owner must return undeclared, not path-derived readiness. |
| F-STATE-BARE | Real `.claude/saga/state.json` without top-level `handoff_maturity` | Saga owner must return undeclared, regardless of `current_work`. |
| F-CITE-FAIL / F-CITE-PASS | Literal failing/passing result references in the Test Author source | Simulated only; never use them to mutate a live issue. |
| Schema resolution isolation | Tests that call `load_config`, especially count-only WIP row T999-04 | Monkeypatch `_resolve_sdlc_schema` to deterministic fixture data from the worktree version under test and `_VENDORED_SDLC_SCHEMA_PATH` to its temporary copy; patch `_gh` so no live API call can escape. |

Create temporary roots and real document bytes for source tests. Patch `_rest_post`, `_rest_delete`,
`_create_github_issue`, and unrelated `flow_set_field` calls; use the existing
`_intake_exit_patches` pattern in `test_issue_create_prepared.py`. For **every** test that calls
`load_config`, isolate its remote-first schema path: monkeypatch `_resolve_sdlc_schema` to return
the intended schema fixture, monkeypatch `_VENDORED_SDLC_SCHEMA_PATH` to a temporary copy of the
**worktree's vendored schema under test** when testing vendored behavior, and patch `_gh` to raise on
an unexpected call. At the red baseline this copy is `2026-08-29`; after U1 it must be
`2026-09-07.5`. Never substitute the already-current remote source for the pre-U1 vendored copy.
A test of `_resolve_sdlc_schema` itself leaves that function real but patches both the vendored path and
`_gh` to controlled results. Follow `plugins/mission-control/tests/test_project_mappings_resolution.py`:
its line 37 patches the vendored path and lines 160–217 isolate resolver cases. The repository-root
`tests/conftest.py` guard does not cover `plugins/mission-control/tests`; these local patches are
required even when the root suite also runs. Test errors and emitted evidence, not only helper
return constants. For installed-plugin tests, create a temporary Claude plugin layout, scrub
`PYTHONPATH`, run outside the monorepo, and prove the resolver's installed-plugin rung. Do not fetch
live issues or depend on the user's current plugin installation.

Every ID has exactly one disposition: `pass`, `fail`, or `blocked`, with a test command, candidate
commit, and evidence path. A blocked row needs a cause and owner; it is never dropped from the
denominator. T999-03 is a final plugin-suite command row, not a pytest test that shells out during
collection. During U1, the complete suite may remain red because the pre-authored #1000 and #942
tests are intentionally red; report U1-scoped results and defer T999-03's final disposition until
all units land.

## Oracle reconciliations for independent review

The Test Author source and Architect grounding differ on several exact mechanics. The **scenario
IDs and behavioral intents are retained**; these are the planned oracles that need Plan Reviewer
acceptance before Test Author finalizes executable tests.

1. **T1000-04, `UNKNOWN`:** Follow the pinned SDLC `docs/process/card-schema.md` and the independent
   Plan Reviewer's blocking finding B1. Field-shape validation accepts `UNKNOWN`, and
   `_readiness_for_prepared_issue` passes the issue creation gate with a warning naming the missing
   Architect assessment. With all other gates satisfied, create-prepared proceeds through the mocked
   GitHub create exactly once. The created body's Risk stays `UNKNOWN` for the later
   Planning-to-Active gate, which the pinned SDLC contract refuses. This corrects the Test Author's
   creation-blocking oracle.
2. **T1000-06–08, label writer:** Exercise the public `flow repair-window` verb. The source scenario
   names `flow set-field` or a helper, but the schema says the marker is a label and the Architect
   correctly keeps it off the project-field writer. Preserve every citation, mutation, and no-GraphQL
   assertion. Incompatibility with an old schema is a refusal case within T1000-08.
3. **T942-02–03 and T942-09, blocked source:** A blank or `unknown:*` assessment writes no draft under
   the shared-owner creation table. Assert the owner/prepare diagnostic and absence of a live route or
   draft; do not require a `### Suggested next action` section in a draft that must not exist.
4. **T942-05–06, external source:** A bare outside file, parent traversal, or escaping symlink is
   refused before read. A declared in-root marker twin may be selected and then both read and
   published as the twin. The existing explicit external choices are a GitHub issue/pull-request URL
   or branch reference; their read and published identities must agree. The source scenario's
   suggested arbitrary external-file read is not an existing explicit choice and would weaken the
   named-root boundary. T942-06 tests both existing choices and selected-twin identity, without a
   new override flag.
5. **T942-07–08, dependency contract:** Inject failure at the lazy fleet-core/Saga resolver and
   versioned owner API, rather than a monorepo import. Missing contract constant, wrong major,
   missing required method, or a declared compatible API with an incomplete vocabulary are
   incompatible. All must have a dependency diagnostic and no local fallback.
6. **T942-10, vocabulary:** Assert that `_HANDOFF_MATURITY_CHOICES` is **removed** and the six values
   come from Saga. The source scenario's instruction to add `pending-confirmation` to the old tuple
   conflicts with Jeff's settled one-owner decision. Preserve the parity and no-second-parser
   assertions.
7. **T942-04/10, routability:** Saga's `ROUTABLE_MATURITIES` includes `deferred-context` for its
   classification contract, but that state's next action is clarification text, not a live
   `/plan` or `/work` command. Assert classification separately from command liveness. Four ready
   states offer a live command; deferred-context and pending-confirmation do not.

## Closed scenario matrix

The table gives the minimum input, action, and expected outcome for each row. The Test Author source
contains the full fixture text. New test files remain Test Author custody; unit mapping is to the
future production change, not a license for the Dev to rewrite the tests.

| ID | Unit and test file | Input and action | Required outcome |
| --- | --- | --- | --- |
| T999-01 | U1 · `plugins/mission-control/tests/test_schema_resync.py` | Load vendored JSON and scan its version occurrence. | Exactly `2026-09-07.5`; prior `2026-08-29` pin fails. |
| T999-02 | U1 · `test_schema_resync.py` | Scan plugin production identifiers and schema keys for `wip_limits` / `component_slices`. | No live reads or removed keys; `work_hierarchy.components` exists; path:line on any violation. Historical prose is allowed. |
| T999-03 | U6 · plugin-suite command | Run `uv run pytest plugins/mission-control/tests -q` on integrated candidate. | Summary says `passed`, zero failed; do not pin a collection count. |
| T999-04 | U1 · existing-oracle files | Run version, count-only WIP output, and field-lag tests after re-vendor; patch `_resolve_sdlc_schema`, `_VENDORED_SDLC_SCHEMA_PATH`, and `_gh` around `load_config`. | Version pin moved; count-only WIP behavior and dated Risk lag asserted from worktree vendored bytes, never live GitHub; lag removed by U2. |
| T1000-01 | U2 · `plugins/mission-control/tests/test_issue_risk_field.py` | Prepare F-CORE without Risk, also with `--risk=medium` and with a `risk:medium` label. | Draft blocked; field validation and blocking gap name `Risk`; neither seed nor label fills a supplied missing section. |
| T1000-02 | U2 · `test_issue_risk_field.py` | Call create-prepared on T1000-01 draft with `_intake_exit_patches`. | Blocking-readiness error names Risk; `_create_github_issue` never called; state is not post-create-pending. |
| T1000-03 | U2 · `test_issue_risk_field.py` | Parametrize four exact tier tokens in F-VALID; omit conditional trio for high tiers in a negative subcase. | Valid bodies pass and sidecar projects body tier; high/very-high without trio fail on those headers. |
| T1000-04 | U2 · `test_issue_risk_field.py` | Prepare `UNKNOWN` with one-sentence justification and otherwise ready inputs; use `_intake_exit_patches`, then call create-prepared with `_create_github_issue` mocked. | Field shape and creation readiness pass; warning names Risk, UNKNOWN, and missing Architect assessment; mocked create runs once; created body retains UNKNOWN for the later Planning-to-Active gate. |
| T1000-05 | U2 · `test_issue_risk_field.py` | Prepare Asgard prose, `medium` without sentence, `extreme`, and empty Risk section. | All block with a Risk-specific diagnostic; none become valid by metadata. |
| T1000-06 | U3 · `plugins/mission-control/tests/test_repair_window_label.py` | Open repair window with F-CITE-FAIL, mocked REST and comment helper; repeat open. | Schema marker label added once, one event/citation comment, repeat is no-op, no project-field GraphQL write. |
| T1000-07 | U3 · `test_repair_window_label.py` | Close with F-CITE-PASS; repeat close or simulate idempotent 404. | Label removed once, passing citation recorded once, no GraphQL project-field write. |
| T1000-08 | U3 · `test_repair_window_label.py` | Open/close with absent or blank citation; separately use schema lacking marker. | Refuse before REST and comment calls; diagnostic names citation or old schema; no state change. |
| T1000-09 | U3 · `plugins/mission-control/tests/test_technical_risk_retirement.py` | Scan live mapping, prompt, queue note, schema Risk entry; exclude historical drafts. | No active Technical Risk project-field producer; E1 retirement note; schema Risk required and matrix includes it. |
| T942-01 | U4–U5 · `plugins/mission-control/tests/test_saga_readiness_alignment.py` | Write F-BRAINSTORM-PENDING and prepare from its real path. | Saga and Mission Control both say pending-confirmation; created draft/sidecar preserve it; no `/plan` or `/work`. |
| T942-02 | U4–U5 · `test_saga_readiness_alignment.py` | Resolve F-DRAFT-BARE and prepare without override. | Both owners report undeclared draft; no route or published draft; diagnostic names draft class. |
| T942-03 | U4–U5 · `test_saga_readiness_alignment.py` | Resolve F-STATE-BARE and prepare without override. | Both owners report undeclared Saga state; no route or published draft; location alone cannot become resume-ready. |
| T942-04 | U4–U5 · `test_saga_readiness_alignment.py` | Parametrize all six declared maturities under brainstorm, plan, and draft paths with proper carriers. | Declaration wins over folder; both entry points agree; only the four ready states offer `/plan` or `/work`. |
| T942-05 | U4–U5 · `test_saga_readiness_alignment.py` | Resolve absolute escape, `../` escape, escaping symlink, and undeclared in-root twin. | Outside original is never read; refused/non-routable diagnostic; undeclared twin cannot authorize it. |
| T942-06 | U4–U5 · `test_saga_readiness_alignment.py` | Choose a valid in-root twin, an explicit GitHub URL, and a branch reference; compare read and published identities. | Each publishes the exact selected source; original outside file remains unread without explicit supported choice. |
| T942-07 | U5 · `test_saga_readiness_alignment.py` | Remove Saga from fake installed layout; invoke readiness path, then unrelated `board view`. | Repairable missing-dependency diagnostic; no draft/route or local fallback; board command works. |
| T942-08 | U5 · `test_saga_readiness_alignment.py` | Supply fake old/incompatible Saga owner: absent contract/API, wrong major, incomplete vocabulary. | Each is an incompatibility diagnostic, no draft/route or legacy inference. |
| T942-09 | U4–U5 · `test_saga_readiness_alignment.py` | Real files: bogus, duplicate, outside fence, unterminated fence, unreadable bytes, blank declaration. | Saga and Mission Control agree on bounded unknown/blank outcome; no draft or live route; no path fallback. |
| T942-10 | U4–U5 · `test_saga_readiness_alignment.py` | Reuse T942-01–06/09 files; inspect source and both assessments. | Maturity, routability, and source identity agree; no Mission Control parser or local tuple remains. |

## Existing-test and file custody ledger

The Test Author creates `test_schema_resync.py`, `test_issue_risk_field.py`,
`test_repair_window_label.py`, `test_technical_risk_retirement.py`, and
`test_saga_readiness_alignment.py` before production edits. The Test Author also adds Saga-owner
parity examples to `tests/test_handoff_envelope_maturity.py`, then hands that file to Dev for any
necessary existing-oracle adjustment. New tests should fail for the intended candidate behavior,
not because a helper import or fixture setup is broken. The Test Author reports each row's initial
red or already-green state and the exact test file revision to the Lead.

| Existing file | Dev update required after Test Author handoff | Child |
| --- | --- | --- |
| `plugins/mission-control/tests/test_prompt_alignment.py` | Pin `2026-09-07.5`. | #999 |
| `tests/test_mission_control.py` | Replace retired `TestWipLimitsConfigurable` mocks with count-only Stage board behavior; do not retain a live removed-key reader. | #999 |
| `plugins/mission-control/tests/test_issue_contract_parity.py` | Add dated one-field lag guard in U1; in U2 update field/header and SHA-256 oracles and delete lag allowance. | #999 → #1000 |
| `plugins/mission-control/tests/test_template_sync.py` | Required actionable field list gains Risk; stale Technical Risk denylist stays. | #1000 |
| `plugins/mission-control/tests/test_issue_prepare.py` | Add Risk to passing bodies, replace Asgard free prose, and keep blocking missing-field assertion. | #1000 |
| `plugins/mission-control/tests/test_issue_create_prepared.py` | Add Risk to ready drafts; preserve no-GitHub-call failures. | #1000 |
| `plugins/mission-control/tests/test_issue_prepare_compile_approve.py` | Stop asserting a live Technical Risk project field. | #1000 |
| `plugins/mission-control/tests/test_card_validator.py` and `test_card_validator_agreement.py` | Update required-header agreement without weakening validator checks. | #1000 |
| `plugins/mission-control/tests/test_flow_subcommands.py` | Keep existing project-field behavior and add public label-verb coverage. | #1000 |
| `plugins/mission-control/tests/test_issue_source_artifacts.py` | Replace path-only maturity expectations with Saga assessment and source identity. | #942 |
| `tests/test_handoff_envelope_maturity.py` | After Test Author handoff, remove the pending-confirmation exclusion and the Mission Control tuple oracle; keep Saga vocabulary and owner parity. | #942 |
| `tests/test_fleet_commons_install_time.py` | Add fake installed Saga and missing/old dependency cases with scrubbed import path. | #942 |

Historical `docs/sdlc-issue-drafts/**` sidecars are fixtures of past output, not rewrite targets.
No test may remove a file from the existing suite to get a green result. A production change that
requires a new behavior oracle is reported to the Test Author and Lead before the Dev alters the
independent test file.

## Execution order and gates

1. **Plan review:** Plan Reviewer `w86:p4` checks both artifacts against the pinned source and all
   seven oracle reconciliations. Planner repairs within document custody; the same reviewer rechecks.
   Its accepted verdict is not implementation permission.
2. **Test authoring:** Test Author `w86:p8` writes the finite files and Saga parity cases, runs the
   focused tests on `ea7963a4`, and records red baseline or already-green per T-ID. No Dev production
   edits precede this gate.
3. **#999:** Dev `w86:p9` implements U1. Run T999-01, T999-02, T999-04 and affected old tests. Do
   not call the intentionally red full suite T999-03 a #999 failure caused by future #1000/#942
   rows; report the scoped result and retain the red denominator.
4. **#1000:** The same Dev implements U2 then U3 on the shared file. Run T1000-01–09, the generated
   parity and template checks, and affected old tests. No #942 writer edits `sdlc_manager.py` until
   this phase is complete.
5. **#942:** The same Dev implements Saga owner U4, then Mission Control consumer U5. Run T942-01–10,
   owner parity, fake install-time resolution, and affected old tests. No second parser is allowed.
6. **Integration:** Run all 23 rows and the plugin suite (T999-03). Run targeted root Saga tests and
   `bash scripts/gate.sh` under the repository's background gate procedure. Record exact candidate
   commit, exit status, summary, and artifacts. A failed row is a failed gate; a timeout without a
   terminal result is `blocked`, not a pass.

Suggested commands after the future code change, from the repository root:

```bash
uv run pytest plugins/mission-control/tests/test_schema_resync.py \
  plugins/mission-control/tests/test_issue_risk_field.py \
  plugins/mission-control/tests/test_repair_window_label.py \
  plugins/mission-control/tests/test_technical_risk_retirement.py \
  plugins/mission-control/tests/test_saga_readiness_alignment.py -q
uv run pytest plugins/mission-control/tests -q
uv run pytest tests/test_handoff_envelope_maturity.py \
  tests/test_handoff_envelope.py tests/test_fleet_commons_install_time.py -q
GATE_LOG_DIR=/tmp/mission-control-alignment-gate bash scripts/gate.sh \
  > /tmp/mission-control-alignment-gate.log 2>&1 &
gate_pid=$!
wait "$gate_pid"
cat /tmp/mission-control-alignment-gate/result.txt
```

The gate's background process must be awaited and its `result.txt` and log inspected; starting it
is not success. Use a fresh, task-specific log directory, preserve other gate processes, and capture
the actual exit status. The root gate is required by issue #942 and repository contract; narrow
pytest runs are diagnostic, not substitutes for it.

## Exit criteria and report shape

Completion requires 23/23 `pass`, zero failed in the Mission Control suite, green relevant Saga and
install-time tests, a successful full repository gate, and no unresolved independent review finding.
The report must identify the exact plugin and SDLC commits, generated module hashes, plugin versions,
every T-ID's disposition, and any excluded external acceptance work. A Plan Reviewer can reject this
plan before those later execution gates; an implementation pass never approves the plan retroactively.

The independent Test seat later checks installed plugin behavior, including missing/incompatible
Saga and named-root source handling, under its separately authorized acceptance assignment. Live
GitHub labels, board changes, merge, deployment, and card closure are outside this finite automated
plan and require separate authority and proof.
