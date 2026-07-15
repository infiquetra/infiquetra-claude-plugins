---
title: Lease-safe runtime continuity capstone - independent fleet doctor
type: feat
status: active
date: 2026-07-15
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json
deepened: 2026-07-15
---

# Lease-safe runtime continuity capstone - independent fleet doctor

## Summary

Implement issue #353 only after #351, #355, #357, and #358 merge. Add one Saga `/fleet-doctor`
skill and `fleet_doctor.py` CLI that observes the broker, outcome worktree registries, Git's actual
worktree list, run-fact dispatch/teardown history, and durable bridge audit store through strict,
bounded, non-mutating readers. It independently correlates those sources into leaked-resource,
unledgered-spawn, and receiptless-delegation findings, plus explicit evidence errors. It never
repairs, settles, retries, releases, kills, quarantines, or reaps.

The source issue predates most of the outcome substrate and the existing `/delegation-audit` command.
Fleet doctor does not duplicate that tolerant single-store query. It adds the missing cross-source
auditor: a malformed file is not silently equivalent to absence, an observed runtime position is
cross-checked against independently persisted facts, and incomplete scans can never return clean.

Destination is merge. Execution uses an operator-approved Verified Workflow. Root owns
implementation, Git, tests, integration, PR, merge, issue closure, and board reconciliation.
Agent-lens roles authorize no repository or external mutation.

---

## Problem Frame and Current State

The issue's proposed inputs are stale but the three disease classes remain valuable:

| original assumption | live/post-outcome authority | planning consequence |
|---|---|---|
| worktrees live under `.worktrees/` | Outcome-managed paths are `.saga-worktrees/<outcome>/<subplot>` and registries are under the Git common dir | scope reconciliation to canonical managed roots; never flag arbitrary linked worktrees |
| `read_registry()` is safe for audit | it quarantines malformed JSON and returns empty, which mutates and can false-clean | doctor uses a strict capped raw reader and never calls tolerant/healing readers |
| provenance manifests are the spawn set | #351 `dispatch-settlement` facts record manifest/spawn/settle positions; #356 broker heads provide independent runtime ownership evidence | correlate independent observations; do not infer real launch from a single producer claim |
| no delegation checker exists | `/delegation-audit` already reconciles one durable store but deliberately turns corrupt files into no signal and always exits 0 | preserve it; doctor adds strict cross-source tripwire semantics |
| stale-worktree count is fifteen | the 2026-07-15 live census has nine total worktrees with no proof that any is abandoned | historical count is motivation, not a test fixture or cleanup instruction |

The doctor must remain independent of the mechanisms it audits. Independence here means it does not
import producer mutation modules or their tolerant projection/reconciliation functions. It reads
documented on-disk contracts with a small stdlib-only observation layer and performs its own joins.
Runtime imports no producer validator; conformance tests compare the independent subset against
canonical validators on shared fixtures so schema drift blocks release instead of weakening runtime
independence.

The doctor also needs an honest observation boundary. A #351 `spawn` fact means the coordinator
committed an attempt immediately before submission, not that a process definitely launched. The
doctor therefore calls a spawn unledgered only when an independent observed position - a #356
resource head/lease, Outcome dispatch event, durable audit run, or supported bridge bundle - lacks
the matching #351 manifest/spawn identity. A fact with no independent observation is a phantom or
unsettled position, not proof that an agent ran.

---

## Traceability and Dependencies

- **Parent outcome/spec:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` and `sub-353` in
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`.
- **Source issue:** `infiquetra/infiquetra-claude-plugins#353`; all eight published acceptance rows
  remain covered, with stale paths/fixtures replaced by production-shaped inputs.
- **Hard upstream:** #351 supplies dispatch manifest/spawn/settle facts; #355 supplies strict
  orphan-evidence/seal contracts; #356 supplies broker leases/resource heads; #357 supplies liveness
  classifications; #358 supplies teardown facts and the closed-owner generation. #353 starts only
  after all exact schemas are merged and refreshed into this plan.
- **Downstream:** cross-runtime acceptance consumes a clean doctor report after Claude/Codex parity.
- **Existing sibling:** `/delegation-audit` remains a focused advisory query. Fleet doctor may point
  to it for detail but does not change its exit code or tolerant behavior.
- **External prerequisites:** none. No credential, deployment, scheduler, production data, remote
  host scan, or destructive cleanup is required.

| published acceptance | plan contract | primary proof |
|---|---|---|
| stale managed worktree | R4; U2 | real temporary Git worktree absent from strict registries/leases |
| dangling registry entry | R4; U2 | strict registry path absent from Git porcelain and filesystem |
| unledgered spawn | R5; U3 | independent broker/audit/outcome observation missing #351 identity |
| receiptless delegation | R6; U3 | claimed bridge execution missing or invalid durable receipt |
| read-only by construction | R2-R3, R8; U1-U4 | repo/audit snapshots and mutation-import conformance |
| exit code/report completeness | R7-R8; U1, U4 | clean=0, findings=1, incomplete/error=2, deterministic report |
| no persisted status | R1-R3; U1-U4 | repeated scan equality and no-write audit |
| full quality/security gates | R9-R10; U5 | focused/full/static/security/release checks |

---

## Requirements

R1. **One report, no authority.** `fleet_doctor_report.v1` is derived fresh on every call. The doctor
does not append run facts, create caches, heal tails, quarantine files, persist scan status,
settle dispatches, acknowledge liveness, release leases, invoke teardown, retry a bridge, or remove a
path. Findings name the owning recovery command but never call it.

R2. **Strict read-only source adapters.** The implementation uses stdlib plus fixed-argv read-only Git
commands and sets `sys.dont_write_bytecode = True` before optional imports. It does not import
`outcome_worktrees`, `outcome_store`, `dispatch_settlement`, `team_teardown`, `reap_orphans`,
`audit_store`, or broker mutation APIs. Strict readers open regular files without following symlinks,
cap bytes/records/depth, distinguish absent from malformed/partial/unsafe, and never create a root,
lock, `__pycache__`, quarantine, or temporary file.

R3. **Repository and path trust is closed.** `--repo-root` resolves through read-only
`git rev-parse --show-toplevel` and `--git-common-dir`; configured audit-store roots must already
exist, be effective-user-owned directories, and not be symlinks. Registry paths, resource refs, and
bundle IDs are treated as untrusted data. The doctor reports escaping paths, unexpected file kinds,
unsafe ownership/mode, duplicate identities, and schema/version skew as evidence errors without
following or reading outside the allowed roots. Git runs fixed argv with the pager disabled, a
ten-second timeout, an 8 MiB stdout cap, and a 64 KiB stderr cap; overflow or timeout makes the scan
incomplete.

R4. **Managed-resource reconciliation is independent.** Enumerate actual worktrees from one capped
`git worktree list --porcelain` snapshot, restrict stale detection to canonical
`.saga-worktrees/<outcome>/<subplot>` paths, strictly read every outcome `worktrees.json`, and
cross-check #356 lease/resource-head plus #358 teardown observations. Report distinct
`stale-worktree`, `dangling-registry`, `ownership-drift`, and `terminal-resource-open` findings.
Primary/current-cwd, unmanaged linked worktrees, and shared-install paths are outside stale detection;
their presence is not a finding.

R5. **Unledgered spawn needs independent observation.** Build the expected dispatch/unit/attempt set
from one chain-verified #351 run-fact snapshot. Build observed positions independently from supported
broker resource heads/live leases, Outcome dispatch events, durable audit run directories, and
supported bridge bundles. Report `unledgered-spawn` only for an observed position with no matching
manifest/spawn fact. Report `unsettled-spawn`, `phantom-spawn-fact`, contradictory identity, broken
chain, and unsupported site/schema separately; never call any one producer claim proof that a process
ran.

R6. **Receiptless delegation is stricter than the existing query.** For bridge/engine attempts,
correlate #351 identity, durable `manifest.json`/`result.json`, `receipt.json`, #355 close seal, and
bundle evidence when still present. A claimed real execution with no receipt is
`receiptless-delegation`; a present receipt must have exact `bridge_receipt.v1`, matching run/execution
identity, required bounded fields, and proof digest references. Corrupt/unsafe/contradictory evidence
is `delegation-evidence-error`, not absent and never clean. Admitted fallback is not receiptless.

R7. **Deterministic closed report.** The schema contains source snapshot digests, `complete`, counts,
sorted findings, and scan warnings. Finding identity is a SHA-256 of class plus canonical bounded
identity, never prose or raw absolute secrets. Human output uses stable sections; `--format json`
emits the complete schema. Paths under the repository may be repo-relative; machine-local audit
paths are redacted to root label plus run ID unless `--show-local-paths` is explicitly selected.

R8. **Exit and capacity semantics fail closed.** Exit 0 means a complete scan with zero findings and
zero evidence errors; exit 1 means a complete scan with one or more disease findings; exit 2 means
configuration error, unsafe/corrupt evidence, broken chain, capacity overflow, source change during
scan, or otherwise incomplete proof. Defaults cap registry/single-state JSON at 8 MiB, each audit or
bundle artifact at 1 MiB, the run-fact ledger at 64 MiB, Git stdout at 8 MiB, source entries at
10,000, findings at 10,000, traversal depth at 6, and rendered output at 16 MiB. Hitting a cap emits
`scan-incomplete` and exit 2; it never truncates to a false clean.

R9. **CLI and skill are production-shaped.** Add `plugins/saga/scripts/fleet_doctor.py`,
`plugins/saga/skills/fleet-doctor/SKILL.md`, and `plugins/saga/commands/fleet-doctor.md`. The CLI
accepts `--repo-root`, optional `--lease-store`, optional `--audit-store`, `--format text|json`, and
`--show-local-paths`; it has no production `--fixture`, `--fix`, `--reap`, `--retry`, or `--watch`.
Tests construct temporary real Git/common-dir/lease/audit roots through fixtures and invoke the
production arguments.

R10. **Release integrity is atomic.** From the expected post-#358 base, bump Saga 0.102.0 to 0.103.0.
Fleet-core 0.15.0 and team-execution 2.20.0 remain unchanged because the doctor consumes their
published contracts without modifying them. Update Saga manifest, marketplace row, changelog, skill
and command inventories, version/drift guards, operator docs, and engineering journal in the same PR.
Refresh and reapprove exact versions/schemas if the base differs.

---

## High-Level Technical Design

```text
strict observation snapshots (no producer mutation imports)

 Git porcelain + raw worktree registries + broker registry + teardown facts
                                      |
                                      +--> resource reconciliation
                                      |
 run-fact dispatch positions ---------+--> spawn reconciliation
                                      |
 audit runs + bundles + close seals --+--> receipt reconciliation
                                      |
                                      v
                         fleet_doctor_report.v1
                         complete + source digests
                         sorted findings/errors
                                      |
                         exit 0 clean / 1 disease / 2 incomplete
```

### Report contract

```text
schema: fleet_doctor_report.v1
repo: canonical repo identity
complete: boolean
sources[]: {kind, identity, digest, record_count, verdict}
findings[]:
  finding_id
  disease: leaked-resource | unledgered-spawn | receiptless-delegation | evidence-error
  classification
  subject_id
  evidence_refs[]
  owner_command
counts: {sources, findings, by_disease, evidence_errors}
warnings[]
```

The owner command is bounded guidance such as `/outcome status`, lease-broker `inspect`, B8
`status/recover`, or `/delegation-audit`; it carries no shell interpolation and is never executed.

### Independent-source matrix

| question | expected/claimed source | independent observed source | clean requires |
|---|---|---|---|
| managed worktree exists | strict outcome registry + broker resource | Git porcelain + contained filesystem stat | identity/path/generation agree |
| spawn was accounted | #351 manifest/spawn/settle facts | broker head/lease, Outcome event, audit run, supported bundle | observed position has exact fact identity and valid transition |
| delegation ran durably | claimed manifest/result + #351 attempt | schema-valid durable receipt plus matching IDs/digests; optional bundle/close seal consistency | claim and proof agree |
| terminal resources closed | #358 intent/result/complete facts | closed broker generation + no live managed observation | zero unexplained open resource |

---

## Key Technical Decisions

- **KTD1 - independent correlation, not shared projection.** The doctor reads documented raw
  contracts and owns joins; it does not call the tolerant/mutating readers whose failures it audits.
- **KTD2 - absence, corruption, and incompleteness differ.** A corrupt file or capped scan exits 2;
  it cannot degrade to an empty source and return clean.
- **KTD3 - actual launch is never inferred from one spawn fact.** Unledgered requires an independent
  observed position; fact-only and unsettled positions retain their own classifications.
- **KTD4 - managed scope is explicit.** Only canonical Outcome-managed worktrees participate in the
  leak invariant. Arbitrary developer worktrees are neither owned nor condemned by this tool.
- **KTD5 - strict receipt auditing complements `/delegation-audit`.** The existing query stays
  tolerant and advisory; doctor turns malformed/cross-source disagreement into a tripwire result.
- **KTD6 - exit 2 protects CI truth.** Findings and inability to prove clean are operationally
  distinct, but both block a green tripwire.
- **KTD7 - no test-only production schema.** Real temporary Git/audit roots replace the issue's
  proposed `--fixture`, avoiding a second artificial input contract.
- **KTD8 - one Saga release only.** The doctor consumes prior plugin schemas and adds no fleet-core
  or team behavior, so only Saga's command/skill surface advances.

These decisions are recorded under `{#fleet-doctor-independent-audit-353}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

---

## Implementation Units

### U1. Strict bounded observation and report contracts

**Goal:** Build the non-mutating stdlib observation layer, closed report schema, source snapshots, and
exit/cap semantics.

**Requirements:** R1-R3, R7-R8.

**Dependencies:** merged exact #351/#355/#356/#358 schemas.

**Files:** `plugins/saga/scripts/fleet_doctor.py` (new), `tests/test_fleet_doctor.py` (new).

**Approach:** Define frozen source/finding/report values, safe open/stat helpers, capped JSON/JSONL
readers, Git porcelain parser, chain verifier, canonical identities, redaction, source pre/post stat
checks, and deterministic renderers. No producer module is imported. Return an incomplete report on
source change rather than retrying invisibly.

**Test scenarios:** absent optional source; missing required source; corrupt/torn/middle-mutated
ledger; unsafe symlink/root/mode/owner; traversal IDs; nonregular files; source changes between reads;
every byte/record/depth/finding/output boundary; stable ordering/digests; redacted/default and explicit
local paths; 0/1/2 exit mapping; repeated scan equality.

**Verification:** Import and empty scan create no file or directory; before/after snapshots include
repo worktree/index/refs/config, Git common dir, and audit root.

### U2. Managed worktree and terminal-resource reconciliation

**Goal:** Detect both directions of managed worktree drift and resources left open after terminal
teardown without invoking any owner action.

**Requirements:** R3-R4, R7-R8.

**Dependencies:** U1 and merged #356/#358.

**Files:** `plugins/saga/scripts/fleet_doctor.py`, `tests/test_fleet_doctor.py`.

**Approach:** Parse strict registry rows across outcomes, Git porcelain, broker leases/heads/closed
owners, and teardown facts into independent observations. Restrict paths to the deterministic
managed root and join on canonical repo/outcome/subplot/resource generation. Keep primary,
current-cwd, shared-install, and unmanaged worktrees explicitly out of findings.

**Test scenarios:** clean managed worktree; stale filesystem/Git entry; dangling registry; registry
path mismatch; broker/registry generation drift; terminal resource still open; expired-live-owner;
dirty/unmerged retained worktree reported as open but not called stale; malformed registry; primary,
self, shared-install, and unrelated linked worktrees ignored. A real temporary Git repo proves both
stale and dangling directions.

**Verification:** No call or import path reaches `register`, `deregister`, `reap`, `sweep`,
`release`, `quarantine`, or a healing reader.

### U3. Dispatch and delegation correlation

**Goal:** Identify independently observed attempts missing dispatch facts and real-execution claims
missing durable receipt proof.

**Requirements:** R2-R3, R5-R8.

**Dependencies:** U1 and merged #351/#355.

**Files:** `plugins/saga/scripts/fleet_doctor.py`, `tests/test_fleet_doctor.py`, existing bridge
receipt/provenance fixture data used read-only where suitable.

**Approach:** Strictly parse #351 facts, broker heads, Outcome events, audit run directories, supported
bundle summaries, manifests/results/receipts, and close seals. Join by closed dispatch/unit/attempt and
run/execution identities. Runtime validates the minimal required schema independently; conformance
tests compare that subset with canonical pure-validator results on shared fixtures and fail on drift.
Do not scan transcripts or raw diffs.

**Test scenarios:** observed lease/audit/bundle with no spawn fact; exact accounted spawn; fact-only
pre-submit crash; unsettled attempt; settled silent-no-op; retry generations; duplicate IDs;
claimed-real with absent receipt; invalid/mismatched/corrupt receipt; fallback without receipt;
receipt with no claim; deleted bundle with durable proof; close-seal disagreement; unsupported engine
or schema; broken chain; one mixed 30-position matrix with stable exhaustive findings.

**Verification:** Every disease finding has at least two independently sourced evidence refs; a
self-report alone cannot create or clear it.

### U4. Production CLI, skill, and read-only conformance

**Goal:** Expose the report safely to operators and make no-mutation/dead-wiring properties
executable.

**Requirements:** R1-R3, R7-R9.

**Dependencies:** U1-U3.

**Files:** `plugins/saga/scripts/fleet_doctor.py`,
`plugins/saga/skills/fleet-doctor/SKILL.md` (new),
`plugins/saga/commands/fleet-doctor.md` (new),
`plugins/saga/references/fleet-doctor-sources.md` (new),
`tests/test_fleet_doctor.py`, `tests/test_saga_plugin.py`.

**Approach:** Wire exact CLI arguments and exit contract. Add an AST/source-aware denylist for
mutation imports/calls, a source matrix whose every row maps to a real collector/test, and command/
skill inventory tests. Run the CLI in a clean subprocess with bytecode writing disabled and hash the
entire fixture roots plus Git control state before/after.

**Test scenarios:** text/JSON parity; every finding rendered; empty clean; findings; incomplete;
unknown option; unsafe audit root; path redaction; no `--fix/--watch/--fixture`; imported module and
CLI both write nothing; injected dead collector/unused source row/mutation call fails conformance;
command loads the exact skill and script.

**Verification:** A report is useful interactively and in CI/cron, but no scheduler, alert, status
store, or automatic owner command exists.

### U5. Release surfaces and full gate

**Goal:** Publish the new Saga command coherently and prove installed behavior.

**Requirements:** R9-R10.

**Dependencies:** U1-U4.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, Saga metadata/version tests, `docs/engineering-journal/DECISIONS.md`,
`docs/engineering-journal/LEARNINGS.md`, and relevant Saga README/operator index.

**Approach:** Bump Saga to 0.103.0 from the expected post-#358 base. Record that the historical
fifteen-worktree snapshot motivated the capability while the pre-build live census was nine and did
not prove abandonment. Validate installed command/skill/script resolution and minimum compatible
fleet-core contract.

**Test scenarios:** manifest/marketplace/changelog parity; command/skill inventory; installed/local
script equivalence; old/missing fleet schema exits 2 with update guidance; a producer schema change
without source-matrix update fails conformance.

**Verification:** Full repository and release gates pass from a clean refreshed branch.

---

## Requirement Coverage

| requirement | units | primary proof |
|---|---|---|
| R1-R3 | U1-U4 | strict readers, path trust, source snapshots, no-write audits |
| R4 | U2 | real-Git worktree/broker/teardown reconciliation matrix |
| R5-R6 | U3 | two-source spawn and claim/receipt correlation |
| R7-R8 | U1, U3-U4 | closed schema, capacity/incomplete behavior, exits 0/1/2 |
| R9 | U4-U5 | production CLI/skill/dead-wiring conformance |
| R10 | U5 | installed resolution and release parity |

---

## Scope Boundaries

### In scope

- One repo-scoped point-in-time audit over merged lease, worktree, dispatch, teardown, manifest,
  receipt, and supported bundle contracts.
- Three disease classes plus evidence errors, deterministic text/JSON, exits 0/1/2.
- Saga `/fleet-doctor` command/skill, strict read-only conformance, release surfaces.

### Non-goals

- Repair, reaping, release, kill, retry, settlement, quarantine, acknowledgment, dispatch, cleanup,
  issue/board mutation, or automatic follow-up.
- Replacing `/delegation-audit`, #355 orphan projection, #358 status/recovery, #351 casualty/DLQ, or
  #356 broker inspection.
- Arbitrary linked-worktree hygiene, scanning other repositories/hosts, remote GitHub truth, a daemon,
  cron installer, watcher, dashboard, alert, metrics store, retention policy, or historical report DB.
- Transcript/raw-diff scanning, new receipt/manifest/fact schema, test-only production fixture format,
  output with secrets/raw prompts, or compatibility guesses for unknown versions.

---

## Risks and Mitigations

| risk | impact | mitigation/proof |
|---|---|---|
| tolerant reader turns corruption into empty/clean | false green | independent strict readers; corrupt/incomplete exit 2 |
| doctor shares producer bug | missed disease | raw documented subset plus independent joins; validator disagreement is error |
| one fact is mistaken for real launch | false unledgered/clean | require independent observed position; separate phantom/unsettled classes |
| arbitrary worktree is called leaked | unsafe cleanup pressure | canonical managed-root scope; primary/self/unmanaged exclusions |
| scan changes state through helper/import | violates core promise | stdlib observation layer, bytecode off, import/call denylist, full root snapshots |
| source grows without bound | CI hang/output loss | explicit byte/record/depth/finding/output caps; incomplete exits 2 |
| machine-local paths leak | privacy/security | default redaction; explicit opt-in for local paths; no raw prompt/output |
| merged schema differs from plans | wrong joins | hard wait for upstream merges, refresh/reapproval, schema conformance |

---

## Verification

```bash
uv run pytest tests/test_fleet_doctor.py -v
uv run pytest tests/test_run_ledger.py tests/test_dispatch_settlement.py -v
uv run pytest tests/test_outcome_worktrees.py tests/test_reap_orphans.py tests/test_team_teardown.py -v
uv run pytest tests/test_saga_plugin.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
git diff --check
```

The event-flow validator traces each expected/observed pair through classification and ensures no
finding or evidence error is swallowed. The scenario validator runs clean, each disease alone, all
diseases, corrupt/unsafe/incomplete sources, retries/generations, and installed command cases while
checking the no-write snapshot. Both use gpt-5.6-terra medium; the four judgment reviewers use
gpt-5.6-sol high.

Manual acceptance runs `/fleet-doctor --format json` against the live repository in no-write mode,
retains the source digests and exit, and does not clean any result. Cross-runtime acceptance later
requires Claude and Codex to produce equivalent classification over the same captured fixture and a
clean report over the fully settled outcome.

---

## Failure Modes and Stop Conditions

- Any scan imports/calls a producer mutation, creates/heals/quarantines a file, or changes Git/common/
  audit-root evidence: stop as a P0 read-only violation.
- Missing, corrupt, unsafe, changed, capped, or unknown evidence returns exit 0: stop as a false-green
  defect.
- An unledgered-spawn finding relies only on a spawn/self-report fact with no independent observation,
  or a single producer signal clears a contradiction: stop and restore independent correlation.
- Arbitrary developer worktrees outside `.saga-worktrees/<outcome>/<subplot>` are flagged stale, or
  owner guidance executes automatically: stop at the ownership boundary.
- The doctor duplicates `/delegation-audit`, #355/#358 projection/action logic, adds a daemon/status
  store, or invents a new evidence schema: stop for scope correction.
- A raw local path, transcript, prompt, diff, token, or unbounded evidence enters default output:
  stop at the privacy/cap boundary.
- Any P0-P3 document/code-review finding remains, a required validator lacks gate-capable evidence,
  full gates fail, or release metadata drifts: no PR/merge.

---

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-scenarios | implement | validate | scenario-tester | agent-lens | preferred | test-medium | test_medium | auto | none | scenario-matrix,command-results | 8167b31e38f328eca0bf4cfc4ad782ee3a85669af7b08be8aa422b8edbc46f68 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-event-flow,validate-scenarios | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's implementation paths plus exact Saga release surfaces. Root
  records the pre-existing Git baseline before `implement`; unrelated worktree paths are excluded.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; validators assess captured
  evidence and semantics.
- `vehicle=auto` requests the named profiles above. The runtime receipt must confirm model, effort,
  role-lens hash, and profile hash before the attempt counts. Mismatch is stopped and rerun in a fresh
  bounded context with the approved profile; missing independence/evidence blocks the gate.
- Root fixes every P0-P3 finding and creates a fresh follow-up attempt for affected roles. Three
  unsuccessful remediation cycles halt and page the operator. Any model, effort, lens, validator, or
  execution-class change requires a newly approved workflow candidate.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No doctor
  owner command, cleanup, deployment, credential, production-data, force-push, or branch deletion is
  authorized.
- Workflow intents, receipts, findings, command logs, workspace/no-write audits, source-digest
  reports, PR URL, merge SHA, issue close, and board reconciliation are retained in the Verified
  Workflow evidence root and issue/PR.

---

## Completion Gate

Completion requires every published acceptance outcome plus strict corruption/incompleteness,
privacy, independent-correlation, and real-Git proofs; zero open P0-P3 doc/code-review findings; both
required validators passing with gate-capable evidence; full verification green; one atomic issue PR
merged; issue #353 closed and its Operations card reconciled; dependent acceptance node refreshed;
and the outcome worktree clean except for the next planned leaf. A live doctor finding is evidence for
the owning issue or acceptance gate, never implicit authority for this PR to repair it.
