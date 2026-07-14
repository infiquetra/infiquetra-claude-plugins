# Changelog

All notable changes to this plugin are documented here.

---

## [2.15.0] - 2026-07-14

### Added - Step B1 posture check through the fleet IntentEnvelope (#380)

- **`skills/team-execution/scripts/posture_check.py`** — the wired Step B1 consumer of the
  fleet's single run-start posture primitive (canonical schema: fleet-core
  `fleet_commons/intent_envelope.py`, loaded through the newly vendored
  `fleet_commons_shim.py` beside it). Spend decisions at wave spawn / mid-run escalation
  resolve through `resolve_spend_action`: an attended spend increase without an explicit
  operator approval token is a structural `PostureError` (CLI exit `2`, never a silent
  escalation or an ad hoc re-ask); an unattended run returns the cache-tight default silently
  and holds a requested increase at the default. A malformed envelope fails closed (exit `1`).
- **SKILL.md Step B1** documents the check: team-execution READS posture from the envelope
  registry and never defines its own posture question (enforced by the fleet drift-guard test
  in `tests/test_intent_envelope.py`). No envelope -> no new gate (behavior unchanged).

---

## [2.14.6] - 2026-07-14

### Changed - least-privilege `tools:` on review-class agents for the new fleet-wide agent-file lint (#422)

- Added `tools: Bash, Read, Grep, Glob` to the 10 `role-tier: adversarial-review` agent files
  (`ai-usefulness-reviewer`, `api-reviewer`, `architecture-reviewer`, `clarity-reviewer`,
  `code-quality-reviewer`, `devils-advocate-reviewer`, `infra-reviewer`, `privacy-reviewer`,
  `security-reviewer`, `testing-reviewer`). None of these files declared a `tools:` field before
  this change, which meant every one of them would have failed the new repo-wide tool-scope-floor
  lint (`tools/agent_spec.py`, `.github/workflows/ci.yml`'s "Agent-file spec lint" step): a
  review/verify-class agent must carry an explicit tool list free of direct file-mutation tools
  (`Edit`/`Write`/`NotebookEdit`).
- `Bash` is retained deliberately: these reviewers are handed artifact pointers and their own
  prompts (`security-reviewer.md`, `devils-advocate-reviewer.md`, `architecture-reviewer.md`)
  mandate dereferencing them by running
  `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py deref` via `Bash` --
  "the required verification path"
  (`plugins/team-execution/skills/team-execution/references/artifact-pointers.md`, which forbids
  substituting a raw `git diff` read) -- so dropping `Bash` would break the pointer-deref contract.
  The `tools:` frontmatter field IS the spawn-time roster a dispatcher reads to scope a leaf's
  capabilities; the least-privilege floor here forbids only the direct file-mutation tools
  (`Edit`/`Write`/`NotebookEdit`) while keeping the read + `Bash`-deref capabilities these
  reviewers require -- the floor is "no direct file-mutation tools", not "read-only".
- No `model:` pins changed -- all 10 already carried `model: opus`, which the new
  model-vs-role-class audit's `review` role class already permits.

## [2.14.5] - 2026-07-12

### Changed - write-once pre-fix draft snapshot in the chaperone-dispatch path (#396)

- `skills/team-execution/references/external-engine-workers.md` §5 step 1 ("Verify"): the
  chaperone now snapshots the engine's raw, pre-fix returned patch/output write-once to the durable
  delegation audit store (`fleet_commons/audit_store.py`'s `write_once_draft`), keyed by
  `execution_id`, before any review, adjudication, or fix. Captures the immutable measurement
  baseline a later fix-delta diff needs, since only the fixed file survives in the working tree. A
  second snapshot attempt for the same `execution_id` raises rather than silently overwriting.
- `skills/team-execution/references/worker-manifest.md`: cross-references the durable mirror and
  clarifies that the raw `manifest_store.py write` CLI path (ordinary Claude-agent worker manifests)
  has nothing to mirror — only the chaperone's `engine_dispatch.record_dispatch_manifest` path
  carries an external-engine identity and receipt.

## [2.14.4] - 2026-07-10

### Changed - current Codex registry dispatch contract (#559)

- Document explicit GPT-5.6 model/effort propagation for registry-backed Codex chaperone envelopes,
  canonical `<model>-<effort>` receipt/evidence identity, and the direct-delegation default boundary.

## [2.14.3] - 2026-07-09

### Changed - typed external-engine reconciliation contract (#393)

- Document all three external-engine intents and their typed reconciliation recipes, including
  rejected-offload evidence and the `PANEL_N_CAP = 7` Claude-foreman boundary.
- Clarify that reconciliation facts and approval-gated retro proposals remain advisory and never
  give an external engine, panel, manifest, or proposal gate authority.
- Add the cycle-1 normal-build reconciliation sequence, immutable dispatch bindings, structural
  ledger projection/lock contract, canonical rejected-intent retention, and shared panel/byte caps.
- Align cycle-2 chaperone guidance with ordered typed finding envelopes, the offload-only opaque
  singleton, exact multi-finding coverage, capped evidence-bound rejection summaries, `0600` final
  manifests, non-healing reads, and exact ordered panel digest binding.

## [2.14.2] - 2026-07-09

### Changed

- `skills/team-execution/references/external-engine-workers.md`: document Saga bridge
  proof-integrity, output attestation, token proof, and bridge-run liveness as the accepted
  external-engine worker evidence contract for issue #388.

## [2.14.1] - 2026-07-09

### Changed - validator findings reference engine-output trust boundary (#385)

- `skills/team-execution/references/validator-registry.md` and `validator-criteria.md`: clarify that
  advisory validator and reviewer finding text is opaque untrusted data governed by Saga's
  `engine-output-trust-boundary.md`, not a command, path, or gate token source.

## [2.14.0] - 2026-07-09

### Added — non-scoring external advisory consensus seat (#382)

- `skills/team-execution/scripts/consensus_advisory.py`: adds a small executable helper for
  gated-vs-advisory reviewer consensus math and key-based Claude-vs-external convergence reports.
- `skills/team-execution/references/consensus-protocol.md`: documents the external advisory seat as
  always excluded from `>= 9.0` acceptance, `< 7.0` blocking-stop, and re-review math, while attaching
  a convergence report with `converged`, `Claude-only`, `external-only`, and `conflicting` buckets.
- `skills/team-execution/references/reviewer-registry.md` and `external-engine-workers.md`: register
  the advisory seat outside base/optional Claude reviewer tables and bind it to
  `role_kind="advisory-reviewer"` halt-not-fallback chaperone dispatch.

## [2.13.1] - 2026-07-09

### Changed — batch-aware external-engine chaperone contract (#381)

- `skills/team-execution/references/external-engine-workers.md`: documents homogeneous same-engine batching as chaperone context amortization only, with per-unit `unit_contexts[]`, `verifiability`, `test_oracle`, `manifest_identity`, sampling, escalation, and cache hit/miss provenance.
- `skills/team-execution/references/worker-manifest.md`: clarifies that batched external-engine units still write distinct per-unit manifests; batch id and sampling state remain advisory provenance only.

## [2.13.0] - 2026-07-07

### Changed — single-path manifest contract + empty-delivery gate in §5 (#390 U3/U5)

- `skills/team-execution/references/external-engine-workers.md` §5: collapse the chaperone
  contract to exactly one manifest-construction path — `record_dispatch_manifest(...,
  expected_identity=<§4 preview>)` — and delete the documented direct
  `provenance_manifest.Manifest` hand-build instruction; refresh stale `engine_dispatch.py` line
  citations and state the fail-loud discriminator (a substituted manifest is refused at the gate)
  as the worker-slot contract. §5 also now runs saga's `check_empty_delivery` check between verify
  and the chaperone-owned commit step, HALTing on a delegated unit that claims delivery with zero
  changed paths. Documentation-only — the mechanics are enforced entirely on saga's side.

## [2.12.3] - 2026-07-07

### Changed — chaperone contract documents runtime two-signal acceptance + re-queue-once rule (#384, U6)

- `skills/team-execution/references/external-engine-workers.md` §5: documents the additive
  chaperone step — arm via saga's fleet-core-backed `arm`/`disarm`/`status` CLI before dispatch,
  accept a delegation only on two-signal agreement (engine self-report AND independent observer
  corroboration), one re-queue on disagreement then HALT, with `DELEGATION_INTEGRITY` named in
  the halt reason. Documentation-only — no team-execution code changes; the protocol's mechanics
  are enforced entirely on saga's side (dispatch layer + hooks).

## [2.12.2] - 2026-07-06

### Changed — pointer update to codex first-party bridge (#476, R6)

- `skills/team-execution/references/external-engine-workers.md`'s `codex` `ENGINE_INTENTS`
  cross-reference now points at the first-party `codex:delegate` bridge (`plugins/codex/`)
  instead of the retired `codex:codex-rescue` marketplace agent. Documentation-only —
  team-execution's own resolution stays fully declarative and requires no code change.

## [2.12.1] - 2026-07-06

### Changed — pointer update to saga's dispatch-adapter contract (#387, #383)

- `skills/team-execution/references/external-engine-workers.md` (the `ENGINE_INTENTS`
  cross-reference by `<engine-key>` / `cap:<capability>`) now points at the new
  `plugins/saga/references/dispatch-adapter-contract.md`, which documents the `transport: http`
  registry field and generic HTTP bridge added in this pair (#387 keystone). Documentation-only —
  team-execution's own resolution stays fully declarative; new registry rows (`ollama-cloud`,
  `deepseek`) join `ENGINE_INTENTS` resolution automatically with no team-execution code change.

## [2.12.0] - 2026-07-06

### Added — segment-boundary session tier override read (#365)

- The emitted Team Structure now honors a run-scoped tier ceiling / mid-run patch written via `/tier`
  (`.claude/saga/tier-session-override.json`): `team_emitter` clamps each segment's worker tier down to
  the ceiling at emit, before the #369 enforceability halt. Because a mid-run patch touches only
  not-yet-run units, a tier change written between segments affects only the next (not-yet-shed)
  segment's worker spec; an already-shed segment keeps its recorded tier. Documented in SKILL.md
  (Context Shedding / R11). No spawn-path behavior change beyond honoring the override at emit.

---

## [2.11.0] - 2026-07-05

### Wire `inject_effort()` seam into the Agent-tool teammate spawn + cross-plugin convention (#363)
- `SKILL.md`'s persistent-resident-worker spawn step now runs each segment's cascade-resolved
  effort (`team_emitter.resolve_teammate_effort`, saga 0.63.0) through
  `fleet_commons.effort_rider.inject_effort(prompt, resolved_effort, "agent")` before the
  Agent-tool spawn — the only dispatch path with no real per-call effort knob (KTD1/KTD2), so a
  labeled `EFFORT_RIDER[resolved_effort]` proxy directive is prepended to the spawn prompt. The
  `workflow` and `external-engine` spawn kinds already honor effort as a real knob and route
  through the same seam as guarded no-ops so a mistaken call never double-injects the rider.
- Added a post-run reconciliation step (R9, KTD7): compares each teammate's cascade-resolved
  effort against the worker manifest's recorded effort via
  `fleet_commons.effort_rider.reconcile_effort(...)`, emitting a named `tiering-drift[<spawn_kind>]`
  line on mismatch (comparing `manifest_effort` on real-knob paths, `spawn_prompt` rider text on
  the Agent-tool path) and nothing on a match.
- `plugins/agy/agents/agy-coder.md` and `plugins/deploy/agents/release-orchestrator.md` each gained
  a validated `effort:` frontmatter field as the first cross-plugin adopters of the convention
  (R8).
- This closes the standing `{#team-execution-per-teammate-effort}` queue item via the
  `inject_effort()` seam — effort is now a first-class value honored by the real knob on the two
  paths that have one and proxied honestly on the one that doesn't — **not** the rejected
  route-team-execution-onto-Workflow re-architecture (KTD1). A native subagent-effort knob remains
  a tracked residual follow-up: swapping the proxy for a real call is a one-function change behind
  the same seam.

## [2.10.0] - 2026-07-05

### Migrate all 25 agent frontmatters to `role-tier:`, resolved through the shared tier registry (#362)
- Each of the 25 `plugins/team-execution/agents/*.md` frontmatters now declares a `role-tier:` value
  (`adversarial-review` for reviewers, `contract-test` for testers, `mechanical-scan` for
  scanners/monitors/`deploy-watcher`), resolved at dispatch time through
  `fleet_commons/tier_resolver.py` + `tier_policy.json`'s work-shape registry instead of a bare
  hardcoded `model:` literal per agent.
- `model:` is kept in every frontmatter as a documented fallback only — no agent's effective model
  changes; a tier-preservation test asserts each migrated agent still resolves to its pre-migration
  model. Intentional re-tiering is out of scope for this change.
- `skills/team-execution/SKILL.md`, `references/reviewer-registry.md`, and
  `references/validator-registry.md` updated to describe the `role-tier:` migration and point at the
  resolver as the tier-resolution source of truth.

## [2.9.1] - 2026-07-05

### Reformat CHANGELOG title to canonical grammar (#429)
- Drop the plugin-name suffix from the file title (was `# Changelog - team-execution`) as part of
  the release-surface single-source generator work.

## [2.9.0] - 2026-07-03

### Consensus dimension exclusion replaces fabricated N/A default (#293)
- `architecture-reviewer.md` scored a dimension whose repo-state precondition was absent (e.g.
  Architecture Documentation Coverage with no ADRs or observable patterns to check) as a
  fabricated N/A -> 8.0 default, folded into the five-dimension average that feeds the
  unanimous-ACCEPT gate. It now EXCLUDES the dimension from the denominator with a logged
  `static-non-applicable` cause, and reports the overall as the average of the applicable
  dimensions, naming the denominator (e.g. "avg of 4 applicable").
- `consensus-protocol.md` defines the same applicable-dimensions denominator for the `>= 9.0` /
  no-dimension-`< 7.0` pass gate and the re-review path: a static exclusion is never itself a
  NEEDS REVISION signal, does not lower the overall, and does not trigger re-review or
  escalation. The exclusion vocabulary (`static-non-applicable`) is shared with the Layer A
  `saga` `execution-spec.md` contract, even though the two surfaces reconcile on distinct paths
  (prompt-reconciled dimensions here; generated-code-reconciled verifiers there).
- Exclusion is dimension-granular: a reviewer whose entire lens is non-applicable is excluded
  whole from the consensus denominator; the other four dimensions have no repo-state
  precondition and are never excludable.
- New `tests/test_team_execution_consensus.py` drift-guards pin the contract text so a future
  edit cannot silently reintroduce the fabricated default.

## [2.8.0] - 2026-07-02

### Consensus-gate hardening (#291)
- L1 `deref` no longer parses the free-form `deref` command string into git argv: a tampered
  `git diff --output=<path> ...` was an arbitrary-file-write primitive. The base tree is now a
  validated first-class `base` field, and the diff argv is rebuilt deterministically from
  hex-validated OIDs (no option token is representable).
- TTL `gc` now reclaims snapshot refs after `git gc` packs them: refs are created with
  `--create-reflog`, enumerated via `for-each-ref`, and dated by the reflog ENTRY timestamp — which
  survives both ref-packing and `git gc`'s internal `reflog expire` (the reflog FILE mtime does not:
  gc resets it). The prior loose-ref-mtime gc went blind once git packed the ref.
- `deref` on a `symbol` pointer is rejected with a clear error (exit 2); the CLI dereferences only
  `diff` and `file` kinds. Sparse-checkout snapshots fail loudly (KTD7 inline fallback) rather than
  shipping a diff with phantom deletions. CAS reads reject symlinks; run-id/epoch ref segments are
  validated before ref construction.
- `references/artifact-pointers.md` receiver contract now mandates the `deref` CLI as the required
  verification path (the raw `git diff` skips freshness), documents the exit-code contract
  (1 = typed pointer failure, 2 = malformed/git error), the `base` field, and the L2/L3 pointer
  shapes with worked examples.

### Typed artifact-pointer passing (#291)
- New `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` CLI: the pointer
  contract (kind `diff`/`file`/`symbol`, locator, integrity hash, freshness marker) plus four
  subcommands — `snapshot` (Layer 1: a dirty-tree-safe locator via a temp-index `git write-tree`,
  pinned by a holding ref under `refs/team-execution/snapshots/<run-id>/<epoch>`, covering staged,
  unstaged, and untracked files without touching the real index or worktree), `store` (Layer 2: a
  write-once content-addressed store at `.claude/team-execution/artifacts/`, sha256-keyed, with an
  epoch freshness sidecar and TTL-bounded `gc`), `deref` (verifies both hash and freshness, emitting
  typed `POINTER_HASH_MISMATCH` / `POINTER_STALE` errors on mismatch — never a silent review of
  wrong or stale bytes), and `gc` (reclaims snapshot refs and stale CAS entries past the TTL).
- Spawn templates (`references/consensus-protocol.md` B3a fan-out and B3e delta re-engagement,
  `references/validator-spawn-quirks.md`) pass an `artifact-pointer` fenced-JSON block instead of an
  inlined diff once the artifact crosses threshold (> 4 KB solo, > 1 KB with >= 2 recipients; <= 1 KB
  always stays inline). New `references/artifact-pointers.md` states the receiver contract: dereference,
  verify hash and freshness, and always read the FULL artifact in v1 — review invariance is
  preserved, per-lens scoping stays deferred. Base reviewer agents each carry a pointer-dereference
  line referencing the contract.
- Light Layer-3 `symbol` pointer form (`<repo-relative-path>#<symbol-name>`), resolved by the
  receiver's existing grep/read tools — no formal resolver, no feasibility probe.
- KTD7 capability-keyed degradation: git-object pointers resolve for same-cwd resident teammates and
  linked worktrees (shared `.git/objects`) but not inside external-engine disposable clones: those
  paths fall back to inlined content, stated explicitly in the spawn templates and
  `artifact-pointers.md`.
- Security hardening (887f769): confined the Layer-2 `deref` path resolution to the hash-derived CAS
  path only, blocking a path-traversal arbitrary-file-read and an accompanying hash oracle that a
  crafted pointer locator could otherwise exploit.

## [2.7.0] - 2026-07-02

### Capability-scoped sandbox write-mode leg (#287)
- `references/external-engine-workers.md`: documents the write-mode chaperone leg — a
  `sandboxed-mutate` unit lifts agy to `mode: "patch-only"` with `write_set` = the unit's declared
  files (wiring the existing remotes-stripped disposable clone), while a `sandboxed-mutate` codex
  unit HALTS (no write adapter). The leaf's declared sandbox is recorded as pre-hoc
  `attribution.sandbox` on the provenance manifest.

## [2.6.0] - 2026-07-02

### External-engine workers — chaperone dispatch (#318)
- A resident Claude worker (`worker-<engine>` / `worker-<capability>`) can now own an engine's
  (agy, codex) units end-to-end: resolve, dispatch through the existing containment wrappers,
  verify, apply as sole-committer, test, and write the worker-exit manifest. New
  `references/external-engine-workers.md` is the full protocol; `SKILL.md`'s `### Workers` table
  gains Engine/Intent columns (`—` for Claude workers).
- `worker-manifest.md` activates the `fell-back-to-claude` / `substituted-engine` dispositions
  #285 reserved, with `kind=external-engine` attribution and claim-provenance/adjudication
  guidance for engine-returned claims (D5, no self-attestation).
- New advisory `external-second-opinion` validator (`validator-registry.md`): opt-in only via
  `.team-execution.json`'s `external_second_opinion` key, never auto-selected, and structurally
  incapable of gating (Gate Status can never resolve to `hard-fail`/`blocked`; exempt from
  Required-Evidence Absence). External engines still never hold a gated verdict (R13/R15).

## [2.5.0] - 2026-07-01

### Worker-exit provenance manifests (#285)
- Team-execution workers emit a manifest at worker exit via the saga `manifest_store` CLI, attributed
  with worker kind and declared-vs-produced completeness (R2, R3, R21). New
  `references/worker-manifest.md` defines the worker-exit contract, complementing (never duplicating)
  the existing repo-local `validator-evidence-state.md` per-run evidence JSON; `SKILL.md` points at
  it. Evidence-only — a manifest grants no privilege and holds no verdict.

## [2.4.0] - 2026-06-29

### Required-evidence-absence completeness gate (#277)
- Document the exit-time completeness check (Site 2 of the silent-omission gate): at completion, a
  required, non-skipped validator/leaf whose evidence record was never written is a `missing-output`
  omission (a completion block); a `skipped-by-config` validator is not a trip. Added to
  `validator-execution-order.md` (new Required-Evidence Absence section), SKILL.md Step B7, and
  `validator-evidence-state.md`. Mirrors the saga `completeness_gate` FailureClass names (R12).

---

## [2.3.0] - 2026-06-28

### Worker×model cache scheduling (#275)
- Reviewer residency: named reviewers re-engaged via `SendMessage` with delta-only context
  across review iterations (consensus-protocol).
- Resident-worker residency runtime (SKILL.md Step B1): one named persistent teammate per
  resident worker reused via `SendMessage`, cross-segment summary-handoff, TTL-aware shedding,
  and reactive-unblock wave scheduling subordinate to the coordinator `ready_frontier`.
- Step A7 worker-table template updated to the segment-row schema.

---

## [2.2.0] - 2026-06-26

### Changed
- **R8 reshape to a native-agent-teams wrapper.** Removed every tmux reference **in this plugin** (the
  validators run as native agent-team subagents, not tmux panes): deleted `commands/team-setup.md` (the
  entire `/team-setup` command), `docs/example_tmux.conf`, `docs/agent-overflow.sh`, and
  `skills/.../references/validator-pane-behavior.md`. No tmux reference remains in this plugin outside
  this CHANGELOG's history notes. (Pre-existing repo-root tmux dev-tooling under `docs/` is unrelated
  to team-execution and out of R8's plugin-scoped charter.)
- **Re-homed the `.claude/`-git-ignored validator-state safety check** into the execution skill's
  pre-execution phase (new Step B0a preflight) so it survives the `/team-setup` deletion — it now runs
  in BOTH Phase A planning (Step A5) and Phase B preflight. `validator-evidence-state.md` remains the
  state-location contract.
- **First real backend behind the OutcomeOrchestrator dispatcher seam** (R5/R6): team-execution is
  dispatchable as a leaf backend with a return channel; an unavailable backend emits a visible
  HALT-not-degrade receipt rather than silently substituting (R23). (Coordinator wiring lives in the
  saga plugin's `outcome_dispatcher.py`.)
- Replaced the `test_team_setup_references_existing_assets` guard with
  `test_team_setup_and_tmux_assets_are_removed` (KTD13 — the deletion's own guard).

---

## [2.1.0] - 2026-06-20

### Changed
- Teammate agents now run on role-appropriate models instead of all inheriting the
  session model: the 10 reviewers on **Opus** (deep judgment), the 8 testers on
  **Sonnet**, and the 7 scanners/monitors on **Haiku** (mechanical tool-running).
  Set per agent via the `model:` frontmatter; any agent can be returned to `inherit`
  to track the session model. Reasoning effort is unchanged (session-level).

---

## [2.0.0] - 2026-05-27

### Added
- Validators are now a first-class umbrella alongside workers and reviewers.
- Added scanner, tester, monitor, and operational validator roster:
  `deploy-watcher`, `security-scanner`, `iac-cost-scanner`, `api-compat-scanner`,
  `dependency-scanner`, `smoke-tester`, `scenario-tester`, `api-contract-tester`,
  `sdk-regression-tester`, `event-flow-tester`, `ui-regression-tester`,
  `performance-tester`, `concurrency-tester`, `github-actions-monitor`, and
  `runtime-monitor`.
- Added validator reference docs for registry, criteria, execution order, evidence/state
  format, spawn quirks, and pane behavior.
- Added optional `.team-execution.json` guidance for `required_validators`,
  `disabled_validators`, `nonprod_workflows`, `scenario_hints`, and `smoke_targets`.
- Added guarded nonprod automation rules for Infiquetra repositories.
- Added `appsec-audit` skill for URL/input trust-boundary review, SSRF-style risk,
  redirects, metadata endpoints, allowlists, and evidence-backed findings.
- Added packaged `/team-setup` tmux assets:
  `docs/example_tmux.conf` and `docs/agent-overflow.sh`.

### Changed
- Phase A now derives a team plan from repo type, changed files, workflows, contracts,
  docs, tests, and optional `.team-execution.json`.
- Phase B order is now workers, reviewer consensus, scanners, PR/CI/nonprod coordination,
  testers, monitors, then completion.
- Reviewer non-consensus blocks validators unless the user explicitly overrides.
- Hard-fail scanner/tester findings block auto-merge, nonprod deploy, and completion.
- Remediation is capped at 3 loops before escalation.
- Plugin and marketplace metadata bumped to `2.0.0`.

### Removed
- Removed stale migration notes from the initial release entry.

---

## [1.5.0] - 2026-03-29

### Fixed
- Workers pack into 2x2 grids, while reviewers get solo windows.
- Shift+Down and Shift+Up require the tmux prefix, preserving terminal-app behavior.
- Window creation bells are silenced.
- Windows are named after agents.
- Window management with many agents adds prefix+w and prefix+f helpers.

### Changed
- Overflow routing uses a stable tmux window ID and delayed pane-title routing.
- tmux configuration documents the window layout model.

---

## [1.4.0] - 2026-03-29

### Fixed
- Workers no longer prompt the user for permissions; review cycles enforce quality.
- Agent overflow treats the main window differently from agent overflow windows.

### Changed
- Worker rows use `bypassPermissions` mode.
- Step B1 is the worker kickoff step.

---

## [1.3.0] - 2026-03-29

### Changed
- Skill auto-suggests during plan mode for non-trivial plans.
- Natural-language triggers include agent-team phrasing.
- The user can decline team planning for the current session.

---

## [1.2.0] - 2026-03-29

### Added
- Environment pre-flight checks for the handoff rule, tmux environment, and settings.
- `/team-setup` wizard for setup validation and guided fixes.
- Dismissible tmux checks.

---

## [1.1.0] - 2026-03-29

### Changed
- Phase A submits the plan as one atomic artifact.
- Phase B entry constraints require the team handoff as the first action.

---

## [1.0.0] - 2026-03-25

### Added
- Initial release of the `team-execution` plugin.
- Two-phase execution model: Phase A during planning, Phase B direct orchestration.
- `team-execution` skill.
- `/team-execute` slash command.
- 3 base reviewers always present:
  - `devils-advocate-reviewer`: assumptions, edge cases, failure modes.
  - `security-reviewer`: OWASP, secrets, auth/authZ, and PII coverage.
  - `architecture-reviewer`: design patterns, separation of concerns, and conventions.
- 7 optional reviewers triggered by context:
  - `infra-reviewer`: cloud infrastructure.
  - `api-reviewer`: API design, versioning, and deprecation.
  - `testing-reviewer`: test coverage and patterns.
  - `code-quality-reviewer`: DRY, complexity, naming, and patterns.
  - `privacy-reviewer`: privacy by design and PII handling.
  - `clarity-reviewer`: documentation clarity.
  - `ai-usefulness-reviewer`: AI-consumability of specs and issues.
- Reference files for reviewer registry, review criteria, and consensus protocol.
- Plan triage escape hatch for trivial config-only changes.
- Plan type classification for code, docs/specs, and mixed plans.
