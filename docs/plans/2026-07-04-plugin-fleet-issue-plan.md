# Plugin-Fleet Issue Plan (Gate E)

- **Date:** 2026-07-04
- **Status:** Awaiting Gate E approval — no GitHub writes have occurred
- **Provenance:** 796 ideas generated (Phase D, 120 agents) → 445 survived convergent
  critique → 403 after dedup → **125 consolidated issues** under **12 Objectives**
  (Phase E, 145 agents; partition-verified: every surviving idea id placed exactly once)
  **+ 1 operator-sourced Gate E amendment (`OP-gateE-1`) = 126 issues** — see Amendment
  log below
- **Draft bodies:** `docs/sdlc-issue-drafts/plugin-fleet/<slug>.md` + `.json` sidecars —
  126 pairs, mission-control prepared-draft format, contract-linted (deterministic local
  lint: 126/126 clean as of 2026-07-04; the LLM repair pass was finished by a local
  script after grader drift was found in both directions)
- **Corpus archive:** `docs/plans/plugin-fleet-ideation-2026-07-03/` (all 796 ideas,
  verdicts, kill reasons, dedup map, issue map)
- **Companions:** [Intake Brief](2026-07-03-plugin-fleet-ideation-intake-brief.md) ·
  [Grounding Brief](2026-07-03-plugin-fleet-grounding-brief.md) ·
  [Workflow Design](2026-07-03-plugin-fleet-ideation-workflow-design.md) ·
  [Phase E Decision Brief](2026-07-03-phase-e-decision-brief.md)

## How to review this plan

1. The wave/Objective table below is the program shape — confirm the missions and wave
   assignments match your intent.
2. The per-Objective index lists every issue with tier, type, and executor profile —
   strike or amend any line; strikes remove the issue from Gate F, they don't delete the
   draft.
3. Spot-check draft bodies (the wave-1 structural issues are the highest-leverage reads).
4. Gate E approval authorizes ONLY the assembly of the Gate F mutation plan (a dry-run
   preview of exact GitHub objects). Issue creation happens in Phase G, after Gate F.

## What Gate F will propose (preview of shape, not yet the plan)

- 12 Objective issues (mission-control `objective` type) in infiquetra-claude-plugins.
- 126 sub-issues via `issue create-prepared` from the draft pairs, linked to their parent
  Objective with native sub-issue links (`flow link-sub-issue`).
- Initiative/Objective as project fields (never colon labels), wave tags, milestone
  linkage per your mission-control conventions.

<!-- GENERATED INDEX BELOW — regenerate with the script in session, do not hand-edit -->

## Program shape

| Wave | Objective | Issues | Mission |
|---|---|---|---|
| wave-1 | Ship run-start intent envelope for lifecycle autonomy | 14 | One committed intent envelope at run start makes autonomy, spend, and ceremony posture explicit, durable, and consumed by every gate. |
| wave-1 | Make tier+effort a first-class priced resolvable lever | 9 | Tier and effort become authored, resolved, priced, and enforced fields with one palette, one resolver, and halt-not-degrade guarantees. |
| wave-1 | Stand up the external-engine offload lane | 20 | External engines become a registry-driven, receipt-proven, economically-guarded advisory lane that can never silently substitute or gatekeep. |
| wave-1 | Govern fleet concurrency and reclaim leaked resources | 11 | Concurrency becomes declared policy with leases, retry, settlement, and liveness so nothing leaks, dies silently, or sums past the cap. |
| wave-1 | Automate the ship ceremony end-to-end | 5 | One resumable guarded ship primitive replaces the manual commit-to-cleanup ritual, with hazard preflight, undo, and teardown reconciliation. |
| wave-1 | Make cache economics an engineered, measured win | 6 | Prompt-cache reuse becomes designed, scheduled, and benchmarked instead of accidental: stable prefixes, residency scheduling, and proven savings. |
| wave-2 | Build the fleet telemetry and ledger substrate | 10 | One append-only run-fact ledger under all telemetry: spend, cache, evidence, delegation, and the reports that make claims falsifiable. |
| wave-2 | Enforce context-library standards at authoring time | 7 | Standards become machine-readable contracts enforced at authoring and CI time, with authority resolution and enforcement-coverage gates. |
| wave-2 | Establish single-source-of-truth for shared primitives | 14 | Shared vocabularies, contracts, and vendored artifacts get one source, one parity registry, and guarded propagation instead of hand copies. |
| wave-2 | Gate fleet integrity (agent files, prompts, release surfaces) | 15 | Agent files, prompts, tests, CI parity, and release surfaces are linted, audited, and generated so drift cannot land silently. |
| wave-3 | Make the backlog and lifecycle self-improving | 10 | Mining, promotion, liveness tripwires, and admission control close the loop from finished work back into a healthier backlog. |
| wave-3 | Expand saga+deploy capability breadth (misc/quick-wins) | 5 | Capability-breadth extensions and grooming quick wins that ride on the wave-1/2 substrates. |

**Tiers:** {'structural': 109, 'moonshot': 7, 'quick-win': 10} · **Types:** {'capability': 67, 'enhancement': 48, 'defect': 2, 'exploration': 7, 'context-update': 2}

**Executor models:** {'sonnet': 119, 'opus': 7} · **Backends:** {'team-execution': 39, 'inline': 86, 'cc-workflows-ultracode': 1} · **External-LLM posture:** {'none': 112, 'second-opinion': 10, 'offload': 4}

## Full issue index by Objective

### [wave-1] Ship run-start intent envelope for lifecycle autonomy (14 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-board-progression-shared-writer](../sdlc-issue-drafts/plugin-fleet/pf-board-progression-shared-writer.md): board_progression.py: certificate-gated autonomous status writer shared by /outcome, /work | structural | capability | 4 | sonnet/high · team-execution |
| [pf-durable-gate-records](../sdlc-issue-drafts/plugin-fleet/pf-durable-gate-records.md): Gates as durable approval records with a linted operator-absence contract, decoupled from  | structural | capability | 2 | sonnet/xhigh · team-execution |
| [pf-envelope-authorized-merge](../sdlc-issue-drafts/plugin-fleet/pf-envelope-authorized-merge.md): Envelope-authorized merge: AUTONOMOUS_UNDER_ENVELOPE write class with token check, revocat | moonshot | capability | 1 | opus/high · team-execution · ext:second-opinion |
| [pf-midrun-adjustment-envelope](../sdlc-issue-drafts/plugin-fleet/pf-midrun-adjustment-envelope.md): Mid-run operator control surface: one polled adjustment-envelope file carrying quiesce, pl | structural | capability | 6 | sonnet/xhigh · team-execution |
| [pf-outcome-backend-spend-envelope](../sdlc-issue-drafts/plugin-fleet/pf-outcome-backend-spend-envelope.md): Backend + degrade posture and spend envelope captured once, enforced at the dispatch seam | structural | enhancement | 2 | sonnet/medium · inline |
| [pf-outcome-draft-unstructured](../sdlc-issue-drafts/plugin-fleet/pf-outcome-draft-unstructured.md): outcome draft: refine raw text into a clarity-checked node skeleton, with a $0 determinist | structural | capability | 3 | sonnet/medium · inline |
| [pf-outcome-from-objective-ingestion](../sdlc-issue-drafts/plugin-fleet/pf-outcome-from-objective-ingestion.md): /outcome start --from-objective: seed the DAG from a parent Objective with edge inference  | structural | capability | 4 | sonnet/high · inline |
| [pf-outcome-ingest-reconcile-drift](../sdlc-issue-drafts/plugin-fleet/pf-outcome-ingest-reconcile-drift.md): Ingest provenance reconcile: structural drift detection and idempotent in-flight Objective | structural | enhancement | 2 | sonnet/medium · inline |
| [pf-outcome-intent-capture-ux](../sdlc-issue-drafts/plugin-fleet/pf-outcome-intent-capture-ux.md): Intent-capture ergonomics: start --preview, blast-radius render, body-proposed defaults, s | structural | enhancement | 4 | sonnet/medium · inline |
| [pf-outcome-intent-renegotiation](../sdlc-issue-drafts/plugin-fleet/pf-outcome-intent-renegotiation.md): Mid-run posture renegotiation: repost/set_intent with overlap-safe amendment, monotonic ga | structural | capability | 4 | sonnet/high · team-execution |
| [pf-outcome-step-profiles](../sdlc-issue-drafts/plugin-fleet/pf-outcome-step-profiles.md): Declarative lifecycle step-profile registry: input shape derives which steps each leaf run | structural | capability | 2 | sonnet/medium · inline |
| [pf-reconcile-controller](../sdlc-issue-drafts/plugin-fleet/pf-reconcile-controller.md): One level-triggered reconcile controller for /work, /loop, /outcome | moonshot | capability | 1 | sonnet/xhigh · inline |
| [pf-remote-gate-approval](../sdlc-issue-drafts/plugin-fleet/pf-remote-gate-approval.md): Remote gate approval over the fleet's own channel: gates delivered and answered through re | structural | capability | 3 | sonnet/high · inline |
| [pf-runstart-intent-envelope](../sdlc-issue-drafts/plugin-fleet/pf-runstart-intent-envelope.md): One committed IntentEnvelope: run-start posture interview, issue-carried ship policy, shar | structural | capability | 14 | opus/high · team-execution · ext:second-opinion |

### [wave-1] Make tier+effort a first-class priced resolvable lever (9 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-dispatch-tier-resolver](../sdlc-issue-drafts/plugin-fleet/pf-dispatch-tier-resolver.md): Dispatch-time tier resolver: one seam mapping (role-class, work-shape, overrides) to {mode | structural | capability | 9 | sonnet/high · team-execution |
| [pf-effort-first-class](../sdlc-issue-drafts/plugin-fleet/pf-effort-first-class.md): Effort becomes a real, authored, injected, and honored field fleet-wide | structural | capability | 8 | sonnet/high · team-execution |
| [pf-escalation-on-failure](../sdlc-issue-drafts/plugin-fleet/pf-escalation-on-failure.md): Runtime ladder climbing: gated one-rung escalation on failure signals, titrate-to-effect,  | structural | capability | 4 | sonnet/high · inline |
| [pf-midrun-tier-lever](../sdlc-issue-drafts/plugin-fleet/pf-midrun-tier-lever.md): /tier mid-run lever: session ceiling plus re-emit from the canonical spec, no restart | structural | capability | 3 | sonnet/medium · inline |
| [pf-spend-budget-envelope](../sdlc-issue-drafts/plugin-fleet/pf-spend-budget-envelope.md): Run-scoped spend budgets: threshold envelope, emit-time cost HALT, cost-weight table, and  | structural | enhancement | 5 | sonnet/high · inline |
| [pf-spend-gate-asymmetry](../sdlc-issue-drafts/plugin-fleet/pf-spend-gate-asymmetry.md): Spend-delta machinery: silent-cheap/ask-expensive classifier, worth-it receipts, relative  | structural | enhancement | 4 | sonnet/medium · inline |
| [pf-tier-defaults-persistence](../sdlc-issue-drafts/plugin-fleet/pf-tier-defaults-persistence.md): Persisted tier preferences: per-repo defaults with remembered overrides, and issue-carried | structural | enhancement | 2 | sonnet/medium · inline |
| [pf-tier-floors-halt-not-degrade](../sdlc-issue-drafts/plugin-fleet/pf-tier-floors-halt-not-degrade.md): Tier floors and backend enforceability: halt, never silently degrade or under-tier | structural | enhancement | 3 | sonnet/medium · inline |
| [pf-tier-vocab-single-source](../sdlc-issue-drafts/plugin-fleet/pf-tier-vocab-single-source.md): Single-source tier palette: tier_vocab module, models.json registry, ladder operations, an | structural | capability | 8 | sonnet/high · inline |

### [wave-1] Stand up the external-engine offload lane (20 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-chaperone-economics](../sdlc-issue-drafts/plugin-fleet/pf-chaperone-economics.md): Cheap chaperoning: batched same-engine dispatch, evidence-size-adaptive and verifiability- | structural | enhancement | 5 | sonnet/high · inline |
| [pf-consensus-external-advisory-seat](../sdlc-issue-drafts/plugin-fleet/pf-consensus-external-advisory-seat.md): Non-scoring external-engine advisory seat in the consensus panel, with automated Claude-vs | structural | enhancement | 2 | sonnet/high · inline · ext:second-opinion |
| [pf-delegation-receipt-contract](../sdlc-issue-drafts/plugin-fleet/pf-delegation-receipt-contract.md): bridge_receipt.v1: one proof-of-execution contract every bridge emits, enforced at registr | structural | capability | 3 | sonnet/high · inline |
| [pf-delegation-tripwires-audit](../sdlc-issue-drafts/plugin-fleet/pf-delegation-tripwires-audit.md): Runtime delegation tripwires: PreToolUse hook, Stop-hook transcript audit, live agy audit, | structural | enhancement | 5 | sonnet/high · team-execution |
| [pf-engine-offer-helper](../sdlc-issue-drafts/plugin-fleet/pf-engine-offer-helper.md): Shared engine_offer helper: one per-stage offer primitive with remembered per-repo prefs a | structural | capability | 3 | sonnet/medium · inline |
| [pf-engine-output-trust-boundary](../sdlc-issue-drafts/plugin-fleet/pf-engine-output-trust-boundary.md): External-engine output is untrusted input: injection containment for advisory text crossin | structural | capability | 1 | sonnet/medium · inline |
| [pf-engine-registry-schema](../sdlc-issue-drafts/plugin-fleet/pf-engine-registry-schema.md): Engine-registry schema currency: capability vocabulary, profile inheritance, cost metadata | structural | enhancement | 7 | sonnet/medium · inline |
| [pf-engines-meta-command](../sdlc-issue-drafts/plugin-fleet/pf-engines-meta-command.md): /engines meta-command + route-explain dry-run for operator-facing engine visibility | quick-win | enhancement | 2 | sonnet/low · inline |
| [pf-ideate-engine-lane](../sdlc-issue-drafts/plugin-fleet/pf-ideate-engine-lane.md): Blind external-engine divergent-generator lane in /ideate | structural | enhancement | 1 | sonnet/medium · inline |
| [pf-offload-economics-guards](../sdlc-issue-drafts/plugin-fleet/pf-offload-economics-guards.md): Offload economics: break-even halt, per-provider budget ceiling, cost-delta preview, net-s | structural | enhancement | 6 | sonnet/medium · inline |
| [pf-openai-http-bridge](../sdlc-issue-drafts/plugin-fleet/pf-openai-http-bridge.md): One OpenAI-compatible HTTP bridge: providers become registry rows, Ollama as first $0 row | structural | capability | 5 | sonnet/high · inline |
| [pf-output-attestation-liedetector](../sdlc-issue-drafts/plugin-fleet/pf-output-attestation-liedetector.md): Output must prove its origin: server-authoritative attestation, external-token accounting, | structural | enhancement | 5 | sonnet/medium · inline |
| [pf-provider-auth-preflight](../sdlc-issue-drafts/plugin-fleet/pf-provider-auth-preflight.md): Data-driven provider credential resolution (env/secret-ref) with redaction-safe preflight | structural | capability | 1 | sonnet/medium · inline |
| [pf-provider-onboarding-conformance](../sdlc-issue-drafts/plugin-fleet/pf-provider-onboarding-conformance.md): Provider onboarding: scaffolder, CI conformance gate, and shadow-mode standing | structural | enhancement | 3 | sonnet/medium · inline |
| [pf-silent-fallback-elimination](../sdlc-issue-drafts/plugin-fleet/pf-silent-fallback-elimination.md): No silent Claude-fallback: fail-loud provenance_required, SUBSTITUTED disposition, fallbac | structural | defect | 5 | sonnet/medium · inline |
| [pf-task-provider-recommend](../sdlc-issue-drafts/plugin-fleet/pf-task-provider-recommend.md): recommend(): ranked task→provider routing with cheapest-sufficient ladder, prompting proto | structural | capability | 4 | sonnet/high · team-execution |
| [pf-team-engine-worker-slot](../sdlc-issue-drafts/plugin-fleet/pf-team-engine-worker-slot.md): Activate the team-execution external-engine worker slot as the fleet's delegation surface  | structural | capability | 4 | sonnet/high · team-execution · ext:offload |
| [pf-typed-reconciliation](../sdlc-issue-drafts/plugin-fleet/pf-typed-reconciliation.md): Typed second-opinion reconciliation: reconcile.py, intent→recipe map, divergence intent, f | structural | capability | 6 | sonnet/high · team-execution |
| [pf-work-review-second-opinion](../sdlc-issue-drafts/plugin-fleet/pf-work-review-second-opinion.md): Second-opinion triggers inside /work and reviews: stuck-signal offer, round-N finding adju | structural | enhancement | 4 | sonnet/medium · inline · ext:second-opinion |
| [pf-zero-token-fire-drill](../sdlc-issue-drafts/plugin-fleet/pf-zero-token-fire-drill.md): Zero-token fire drill: run one canonical lifecycle loop entirely on the $0 registry entry  | structural | exploration | 1 | sonnet/medium · inline · ext:offload |

### [wave-1] Govern fleet concurrency and reclaim leaked resources (11 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-429-retry-primitive](../sdlc-issue-drafts/plugin-fleet/pf-429-retry-primitive.md): One shared 429 retry/backoff primitive: emitted-wave auto-retry, engine-bridge circuit bre | structural | capability | 4 | sonnet/high · inline |
| [pf-adaptive-admission-governor](../sdlc-issue-drafts/plugin-fleet/pf-adaptive-admission-governor.md): Adaptive admission control: AIMD wave-width governor with a requeue ledger, shed-over-cap  | moonshot | capability | 5 | opus/high · team-execution · ext:second-opinion |
| [pf-concurrency-policy-spec](../sdlc-issue-drafts/plugin-fleet/pf-concurrency-policy-spec.md): Concurrency policy as a first-class ExecutionSpec block: wave-width cap, resolution ladder | structural | capability | 9 | sonnet/high · inline |
| [pf-dispatch-settlement](../sdlc-issue-drafts/plugin-fleet/pf-dispatch-settlement.md): Dispatch settlement: fan-out manifest with casualty reconciliation, double-entry spawn-set | structural | capability | 3 | sonnet/high · inline |
| [pf-fanout-dispatch-economics](../sdlc-issue-drafts/plugin-fleet/pf-fanout-dispatch-economics.md): Cache-aware fan-out dispatch: stagger-warm release, within-run wave queue, fork_is_cheap p | structural | capability | 4 | sonnet/high · team-execution |
| [pf-fleet-doctor](../sdlc-issue-drafts/plugin-fleet/pf-fleet-doctor.md): fleet doctor: one derived-on-read audit command for leaked resources, dead wiring, and rec | quick-win | capability | 1 | sonnet/medium · inline |
| [pf-optimize-concurrency-knob](../sdlc-issue-drafts/plugin-fleet/pf-optimize-concurrency-knob.md): Re-add a rescoped, defaulted-off max_concurrent to /optimize that engages the original rem | quick-win | enhancement | 3 | sonnet/medium · inline |
| [pf-orphan-fencing-liveness](../sdlc-issue-drafts/plugin-fleet/pf-orphan-fencing-liveness.md): Orphan runner containment: epoch fencing on evidence writes, lease quarantine, heartbeat r | structural | capability | 3 | sonnet/high · inline |
| [pf-resource-lease-broker](../sdlc-issue-drafts/plugin-fleet/pf-resource-lease-broker.md): TTL-lease broker: concurrency slots, worktree/teardown reclamation, and orphan write-fenci | structural | capability | 6 | sonnet/xhigh · team-execution |
| [pf-subagent-liveness-engine](../sdlc-issue-drafts/plugin-fleet/pf-subagent-liveness-engine.md): Fleet-shared liveness engine: extract outcome_liveness, phi-accrual staleness scoring, art | structural | enhancement | 4 | sonnet/high · inline |
| [pf-teardown-reclamation-contract](../sdlc-issue-drafts/plugin-fleet/pf-teardown-reclamation-contract.md): Non-skippable teardown: Step B8 run-exit Teardown & Reclaim contract, register-on-spawn re | structural | capability | 5 | sonnet/high · team-execution |

### [wave-1] Automate the ship ceremony end-to-end (5 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-positive-handoff-ack](../sdlc-issue-drafts/plugin-fleet/pf-positive-handoff-ack.md): Positive handoff protocol at the saga / mission-control / deploy boundary — no dropped bat | structural | capability | 1 | sonnet/medium · inline |
| [pf-ship-ceremony-primitive](../sdlc-issue-drafts/plugin-fleet/pf-ship-ceremony-primitive.md): ship_ceremony.py — one composable, resumable guarded ship primitive replacing the 8-repo m | structural | capability | 3 | sonnet/high · team-execution |
| [pf-ship-hazard-preflight-and-undo](../sdlc-issue-drafts/plugin-fleet/pf-ship-hazard-preflight-and-undo.md): Ceremony hazard preflight, deterministic merge-watcher, and ship --undo rollback | structural | enhancement | 3 | sonnet/high · inline |
| [pf-ship-teardown-reconciliation](../sdlc-issue-drafts/plugin-fleet/pf-ship-teardown-reconciliation.md): Ship ends in teardown: opened-resource manifest, closing-count reconciliation, immutable s | structural | capability | 4 | sonnet/high · inline |
| [pf-stacked-pr-cascade-guard](../sdlc-issue-drafts/plugin-fleet/pf-stacked-pr-cascade-guard.md): Stacked-PR auto-close cascade guard with automatic child rebase-and-reopen | moonshot | capability | 2 | sonnet/xhigh · inline |

### [wave-1] Make cache economics an engineered, measured win (6 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-cache-prefix-stability](../sdlc-issue-drafts/plugin-fleet/pf-cache-prefix-stability.md): Cache-prefix stability: silent-invalidator lint, stable-first context-package primitive, a | structural | enhancement | 3 | sonnet/medium · inline |
| [pf-crossleaf-resident-crew](../sdlc-issue-drafts/plugin-fleet/pf-crossleaf-resident-crew.md): Cross-leaf resident crew and crew-pairing: warm workers across the /outcome DAG, evidence- | moonshot | capability | 5 | opus/high · team-execution · ext:second-opinion |
| [pf-recon-memoization](../sdlc-issue-drafts/plugin-fleet/pf-recon-memoization.md): Kill the 400k-token recon fan-out: shared context pack, tree-hash memoization with $0 loca | structural | capability | 4 | sonnet/high · team-execution · ext:offload |
| [pf-residency-derived-scheduling](../sdlc-issue-drafts/plugin-fleet/pf-residency-derived-scheduling.md): Derived residency scheduling: emitted shed/boundary actions, dependency-preserving segment | structural | capability | 5 | sonnet/high · team-execution |
| [pf-residency-evidence](../sdlc-issue-drafts/plugin-fleet/pf-residency-evidence.md): Prove the cache claim: residency A/B benchmark and warm-reuse benefit regression guard | quick-win | exploration | 2 | sonnet/medium · inline |
| [pf-review-delta-packets](../sdlc-issue-drafts/plugin-fleet/pf-review-delta-packets.md): Review-round delta packets: reviewers receive a derived delta via typed artifact pointer i | structural | enhancement | 1 | sonnet/medium · inline |

### [wave-2] Build the fleet telemetry and ledger substrate (10 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-delegation-evidence-durability](../sdlc-issue-drafts/plugin-fleet/pf-delegation-evidence-durability.md): Delegation evidence survives teardown: durable audit store, write-once draft snapshots, /d | structural | enhancement | 3 | sonnet/medium · inline |
| [pf-evidence-gated-closure](../sdlc-issue-drafts/plugin-fleet/pf-evidence-gated-closure.md): Closure gate: /outcome refuses to close a leaf on missing, stale-SHA, or unsuperseded-FAIL | structural | enhancement | 2 | sonnet/medium · inline |
| [pf-evidence-immutability](../sdlc-issue-drafts/plugin-fleet/pf-evidence-immutability.md): Content-addressed append-only verification evidence: custody log, pre-registered pass crit | structural | capability | 7 | sonnet/medium · inline |
| [pf-fleet-baseline-metrics](../sdlc-issue-drafts/plugin-fleet/pf-fleet-baseline-metrics.md): Freeze the before picture: baseline pain metrics with executable re-measurement recipes | quick-win | context-update | 1 | sonnet/low · inline |
| [pf-gate-divergence-telemetry](../sdlc-issue-drafts/plugin-fleet/pf-gate-divergence-telemetry.md): Rubber-stamp telemetry: record operator gate decisions vs recommendations to ground future | quick-win | enhancement | 1 | sonnet/low · inline |
| [pf-panel-economics-exploration](../sdlc-issue-drafts/plugin-fleet/pf-panel-economics-exploration.md): Exploration: panel economics — measured reviewer independence, consensus elasticity, and a | structural | exploration | 3 | sonnet/high · inline · ext:second-opinion |
| [pf-pulse-live-telemetry](../sdlc-issue-drafts/plugin-fleet/pf-pulse-live-telemetry.md): Pulse live-telemetry component: board/agent/run state rendered from real signals | structural | capability | 1 | sonnet/medium · inline |
| [pf-registry-calibration-loop](../sdlc-issue-drafts/plugin-fleet/pf-registry-calibration-loop.md): Earned ratings: dispatch/benchmark evidence drives retro-gated registry calibration (SPC d | moonshot | capability | 6 | sonnet/high · team-execution |
| [pf-run-fact-ledger](../sdlc-issue-drafts/plugin-fleet/pf-run-fact-ledger.md): One append-only leaf-produced run-fact ledger substrate for spend, cache, engine, delegati | structural | capability | 6 | sonnet/high · team-execution |
| [pf-spend-observability-reports](../sdlc-issue-drafts/plugin-fleet/pf-spend-observability-reports.md): Spend observability on the ledger: estimate-reconcile, itemized receipts with counterfactu | structural | enhancement | 6 | sonnet/high · team-execution · ext:offload |

### [wave-2] Enforce context-library standards at authoring time (7 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-adr-derived-review-lenses](../sdlc-issue-drafts/plugin-fleet/pf-adr-derived-review-lenses.md): One shared review-lens catalog for both consensus loci, with ADR-derived and ADR-pattern l | structural | enhancement | 3 | sonnet/high · inline |
| [pf-authority-resolver-stop-surface](../sdlc-issue-drafts/plugin-fleet/pf-authority-resolver-stop-surface.md): Executable authority-order resolver + stop-and-surface conflict primitive | structural | capability | 2 | sonnet/medium · inline |
| [pf-checkable-surface-census](../sdlc-issue-drafts/plugin-fleet/pf-checkable-surface-census.md): Checkable-surface census + always-on mermaid CI gate | quick-win | enhancement | 2 | sonnet/medium · inline |
| [pf-enforcement-coverage-gates](../sdlc-issue-drafts/plugin-fleet/pf-enforcement-coverage-gates.md): Enforcement coverage: classify every convention, guard binding-but-unenforced decisions, f | structural | capability | 4 | sonnet/high · team-execution |
| [pf-journal-schema-lint](../sdlc-issue-drafts/plugin-fleet/pf-journal-schema-lint.md): check_journal.py — schema-validate engineering-journal ADRs and learnings | quick-win | enhancement | 1 | sonnet/medium · inline |
| [pf-standards-index-machine-contract](../sdlc-issue-drafts/plugin-fleet/pf-standards-index-machine-contract.md): Machine-readable standards index: llms.json sidecar, per-topic loader, staleness hashes, f | structural | capability | 4 | sonnet/high · team-execution |
| [pf-standards-preflight-issue-authoring](../sdlc-issue-drafts/plugin-fleet/pf-standards-preflight-issue-authoring.md): Standards preflight at issue-authoring time (mission-control:issue + saga:handoff) | structural | capability | 3 | sonnet/high · inline |

### [wave-2] Establish single-source-of-truth for shared primitives (14 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-abolish-contract-mirrors](../sdlc-issue-drafts/plugin-fleet/pf-abolish-contract-mirrors.md): Forbid hand-copied validators: consumers exec the source-of-truth surface; behavior locked | structural | capability | 3 | sonnet/high · team-execution |
| [pf-consensus-kernel](../sdlc-issue-drafts/plugin-fleet/pf-consensus-kernel.md): Portable consensus kernel: consensus_spec.py extraction, portable invocation contract and  | structural | capability | 10 | sonnet/xhigh · team-execution |
| [pf-consensus-thresholds-convergence](../sdlc-issue-drafts/plugin-fleet/pf-consensus-thresholds-convergence.md): Consensus threshold and convergence policy: risk-tiered plan-authored profiles, HALT on no | structural | enhancement | 6 | sonnet/high · inline |
| [pf-contract-consumer-graph](../sdlc-issue-drafts/plugin-fleet/pf-contract-consumer-graph.md): Contract-consumer manifest, self-registering consumer graph, and blast-radius ranking | structural | capability | 3 | sonnet/medium · inline |
| [pf-contract-coupling-policy](../sdlc-issue-drafts/plugin-fleet/pf-contract-coupling-policy.md): Machine-checkable contract-coupling policy: what pins, what floats, additive auto-adopt, g | structural | enhancement | 4 | sonnet/high · inline |
| [pf-execution-substrate-decoupling](../sdlc-issue-drafts/plugin-fleet/pf-execution-substrate-decoupling.md): Execution-substrate decoupling: mechanism-neutral review/ceremony substrate on both backends, inherent-property chooser, rigor-preserving degrade ladder — **Gate E amendment, OP-gateE-1** | structural | capability | 1 | opus/high · team-execution |
| [pf-fleet-commons-decision](../sdlc-issue-drafts/plugin-fleet/pf-fleet-commons-decision.md): Name the import mechanism: where cross-plugin shared primitives live and how a plugin gets | structural | exploration | 1 | opus/medium · inline · ext:second-opinion |
| [pf-producer-push-propagation](../sdlc-issue-drafts/plugin-fleet/pf-producer-push-propagation.md): Producer-push contract propagation: source repo opens refresh PRs; consumer-driven contrac | structural | capability | 3 | sonnet/high · inline |
| [pf-rename-campaign-executor](../sdlc-issue-drafts/plugin-fleet/pf-rename-campaign-executor.md): Guarded rename-campaign executor: manifest-driven, aliasable deprecation windows, positive | structural | capability | 4 | sonnet/high · team-execution |
| [pf-retired-vocabulary-guards](../sdlc-issue-drafts/plugin-fleet/pf-retired-vocabulary-guards.md): Retired-vocabulary guards: reverse CI guard + executable retirement invariants | quick-win | enhancement | 2 | sonnet/medium · inline |
| [pf-reviewer-lens-registry](../sdlc-issue-drafts/plugin-fleet/pf-reviewer-lens-registry.md): One shared lens/reviewer registry feeding both consensus loci, with judgment-selected dive | structural | enhancement | 2 | sonnet/high · inline |
| [pf-single-vocab-source](../sdlc-issue-drafts/plugin-fleet/pf-single-vocab-source.md): Collapse the deliberate parallel houses: one ordered vocabulary module, declarative mirror | structural | enhancement | 3 | sonnet/high · team-execution |
| [pf-upstream-drift-sweep](../sdlc-issue-drafts/plugin-fleet/pf-upstream-drift-sweep.md): Continuous upstream drift detection: cron parity vs live source, fleet-wide sweep, halt-on | structural | capability | 4 | sonnet/high · inline |
| [pf-vendored-parity-registry](../sdlc-issue-drafts/plugin-fleet/pf-vendored-parity-registry.md): One vendored-artifact parity registry: contracts, standards index, provenance sidecars, dr | structural | capability | 7 | sonnet/high · team-execution |

### [wave-2] Gate fleet integrity (agent files, prompts, release surfaces) (15 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-agent-file-ci-lint](../sdlc-issue-drafts/plugin-fleet/pf-agent-file-ci-lint.md): One agent-file CI lint: frontmatter schema, tier/effort fields, role-class tier audit, too | structural | capability | 4 | sonnet/high · team-execution |
| [pf-agent-prompt-audit](../sdlc-issue-drafts/plugin-fleet/pf-agent-prompt-audit.md): Agent-prompt quality: scored rubric over all agents, prompt-contract auditor, scheduled ad | structural | exploration | 4 | opus/high · inline · ext:second-opinion |
| [pf-authorship-provenance](../sdlc-issue-drafts/plugin-fleet/pf-authorship-provenance.md): Engine-vs-chaperone authorship: computed ledger, artifact provenance trailer, /retro claim | structural | enhancement | 4 | sonnet/medium · inline |
| [pf-board-live-schema-pagination](../sdlc-issue-drafts/plugin-fleet/pf-board-live-schema-pagination.md): mission-control live-schema resolution and pagination exhaustion: no hardcoded board vocab | structural | defect | 5 | sonnet/high · team-execution |
| [pf-ci-local-parity](../sdlc-issue-drafts/plugin-fleet/pf-ci-local-parity.md): Local-vs-CI parity: one data-defined runner, locked-env simulator, fingerprint doctor, doc | structural | enhancement | 6 | sonnet/high · team-execution |
| [pf-contract-reachability-parity](../sdlc-issue-drafts/plugin-fleet/pf-contract-reachability-parity.md): Declared-but-unwired seam audit + producer/consumer paired-test and parity guards | structural | enhancement | 3 | sonnet/medium · inline |
| [pf-delegation-ci-integrity](../sdlc-issue-drafts/plugin-fleet/pf-delegation-ci-integrity.md): CI-level delegation integrity: marketplace proof gate on bridge version bumps + continuous | structural | enhancement | 2 | sonnet/medium · inline |
| [pf-fake-adapter-integrity](../sdlc-issue-drafts/plugin-fleet/pf-fake-adapter-integrity.md): Fake-adapter integrity: shape lint, golden fixtures, fakes registry with real-contract sha | structural | enhancement | 5 | sonnet/high · team-execution |
| [pf-fleet-review-campaign](../sdlc-issue-drafts/plugin-fleet/pf-fleet-review-campaign.md): One-time comprehensive fleet code-review campaign with a risk-tiered scope manifest | structural | exploration | 3 | sonnet/high · cc-workflows-ultracode |
| [pf-guard-mutation-canary](../sdlc-issue-drafts/plugin-fleet/pf-guard-mutation-canary.md): Chaos-monkey mutation canary proving drift guards have teeth | moonshot | capability | 1 | sonnet/medium · inline |
| [pf-lever-site-census](../sdlc-issue-drafts/plugin-fleet/pf-lever-site-census.md): Lever-site census: inventory every tier/gate decision point, cite the tier-lever contract  | structural | context-update | 5 | sonnet/medium · inline |
| [pf-lifecycle-regression-harness](../sdlc-issue-drafts/plugin-fleet/pf-lifecycle-regression-harness.md): End-to-end lifecycle regression harness on a fixture repo | structural | capability | 1 | sonnet/high · inline |
| [pf-release-surface-single-source](../sdlc-issue-drafts/plugin-fleet/pf-release-surface-single-source.md): Single-source release surfaces: generate marketplace from plugin.json, tri-lock parity, di | structural | enhancement | 7 | sonnet/high · inline |
| [pf-review-ledger-incremental](../sdlc-issue-drafts/plugin-fleet/pf-review-ledger-incremental.md): Standing per-plugin review ledger + incremental changed-plugin review | structural | enhancement | 2 | sonnet/medium · inline |
| [pf-write-ownership-lanes-ci-lint](../sdlc-issue-drafts/plugin-fleet/pf-write-ownership-lanes-ci-lint.md): Write-ownership lane manifest + marketplace-CI lint across saga / mission-control / deploy | structural | enhancement | 1 | sonnet/medium · inline |

### [wave-3] Make the backlog and lifecycle self-improving (10 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-backlog-admission-governor](../sdlc-issue-drafts/plugin-fleet/pf-backlog-admission-governor.md): Backlog admission governor: pace materialization against measured execution throughput | structural | capability | 1 | sonnet/medium · inline |
| [pf-ideate-program-foldback](../sdlc-issue-drafts/plugin-fleet/pf-ideate-program-foldback.md): Fold this ideation program's architecture back into saga:ideate | structural | enhancement | 1 | sonnet/medium · inline |
| [pf-journal-query-join](../sdlc-issue-drafts/plugin-fleet/pf-journal-query-join.md): Cross-repo learning consumption as a query-time join at /plan and /investigate | structural | capability | 1 | sonnet/medium · inline |
| [pf-learning-capture-nomination](../sdlc-issue-drafts/plugin-fleet/pf-learning-capture-nomination.md): Capture-time transcendence marking, nightly nominate-only accumulation, promote-ledger bac | structural | enhancement | 4 | sonnet/medium · inline |
| [pf-liveness-tripwire-engine](../sdlc-issue-drafts/plugin-fleet/pf-liveness-tripwire-engine.md): One predicate engine for revisit-when tripwires, basis decay, and never-fired machinery | structural | capability | 4 | sonnet/high · team-execution |
| [pf-mining-harvest-writeback](../sdlc-issue-drafts/plugin-fleet/pf-mining-harvest-writeback.md): Mining-harvest writeback and a durable /mine-to-backlog harness | structural | capability | 2 | sonnet/medium · inline |
| [pf-mining-ledger-closed-loop](../sdlc-issue-drafts/plugin-fleet/pf-mining-ledger-closed-loop.md): Mined-session ledger, pattern lineage, and closed-loop retirement of resolved findings | structural | enhancement | 3 | sonnet/medium · inline |
| [pf-promote-scan-recall-fixes](../sdlc-issue-drafts/plugin-fleet/pf-promote-scan-recall-fixes.md): Fix promote_scan recall: diagnose mode, lexical clustering, subject scoping, capture-time  | structural | enhancement | 4 | sonnet/high · inline |
| [pf-session-substrate-registry](../sdlc-issue-drafts/plugin-fleet/pf-session-substrate-registry.md): Session-substrate registry: light up 219 dark codex sessions, PR review threads, and chape | structural | capability | 6 | sonnet/high · team-execution |
| [pf-standing-doc-provenance](../sdlc-issue-drafts/plugin-fleet/pf-standing-doc-provenance.md): Extend source-stale claim provenance from delegated outputs to standing docs | structural | enhancement | 1 | sonnet/medium · inline |

### [wave-3] Expand saga+deploy capability breadth (misc/quick-wins) (5 issues)

| Issue | Tier | Type | Absorbed | Executor |
|---|---|---|---|---|
| [pf-dark-plugin-parity](../sdlc-issue-drafts/plugin-fleet/pf-dark-plugin-parity.md): The dark half of the fleet: in-or-out verdict and primitive-parity pass for deploy, home-l | structural | exploration | 1 | sonnet/medium · inline · ext:second-opinion |
| [pf-deploy-canary-verify-revert](../sdlc-issue-drafts/plugin-fleet/pf-deploy-canary-verify-revert.md): Deploy canary + verify + auto-revert flow for the deploy plugin | structural | capability | 1 | sonnet/high · inline |
| [pf-misc-quick-wins](../sdlc-issue-drafts/plugin-fleet/pf-misc-quick-wins.md): Misc quick wins: resume relevance ranking, scaffold gitignore for saga scratch, headless A | quick-win | enhancement | 3 | sonnet/low · inline |
| [pf-outcome-multi-repo-arc](../sdlc-issue-drafts/plugin-fleet/pf-outcome-multi-repo-arc.md): Saga multi-repo arc: one /outcome DAG spanning repos with per-repo saga state | structural | capability | 1 | sonnet/high · team-execution |
| [pf-team-park-resume](../sdlc-issue-drafts/plugin-fleet/pf-team-park-resume.md): Park & resume a running team across sessions | structural | capability | 1 | sonnet/xhigh · team-execution |


## Amendment log (Gate E review)

### A1 — pf-execution-substrate-decoupling (2026-07-04, operator-sourced, id `OP-gateE-1`)

Added during Gate E review from operator direction: team-execution's reviewers, scanners, and
ship ceremony are provisioned content, not properties of the agent-team mechanism — they should be
declared once and rendered onto either coordination mechanism (agent teams or the Workflow tool),
with backend choice made on inherent properties only (compiled vs interpreted coordination:
durability, budget governance, dispatch precision vs negotiation density, interactivity, context
inheritance). The idea did not survive from the pool in this general form — seed `S-29` carried
the consensus-scoped version and is absorbed by `pf-consensus-kernel` — so a new provenance id
family (`OP-` = operator-sourced at a gate) was minted and registered in
`issue-map-final.json`. Placed under "Establish single-source-of-truth for shared primitives"
(wave-2) beside its kin (`pf-reviewer-lens-registry`, `pf-consensus-kernel`,
`pf-fleet-commons-decision`).

### Known review finding — executor-profile Effort lines on team-execution backends

Raised and verified during Gate E review: the 39 profiles naming the team-execution backend also
state an Effort value, but team-execution threads no effort today (verified 2026-07-04: zero
effort references in `plugins/team-execution/`; the Agent tool has no per-call effort parameter).
Those Effort lines are **target posture**, inert until `pf-effort-first-class` /
`pf-dispatch-tier-resolver` (wave-1) land. **Disposition (b) chosen and applied 2026-07-04:**
all 39 team-execution pairs now carry the dependency caveat on the `.md` Effort line and in the
sidecar `executor_profile.justification`. A backend re-triage of existing drafts against the A1
chooser rubric remains a follow-on after that issue ships — not a Gate E blocker.

### A2 — sidecar executor_profile backfill (2026-07-04, found during the (b) pass)

The caveat sweep exposed 9 sidecars whose `executor_profile` was `null` despite a complete
profile in the `.md` (the contract lint only checked the `.md` section):
`pf-spend-observability-reports` (team-execution — the reason the tally briefly read 38),
`pf-guard-mutation-canary`, `pf-lifecycle-regression-harness`,
`pf-provider-onboarding-conformance`, `pf-pulse-live-telemetry`, `pf-remote-gate-approval`,
`pf-review-ledger-incremental`, `pf-spend-budget-envelope`, `pf-write-ownership-lanes-ci-lint`.
All 9 rebuilt deterministically from their `.md` profile blocks; fleet-wide check now shows all
126 sidecars complete (model/effort/backend/external_llm/justification populated). Lint remains
126/126 clean.
