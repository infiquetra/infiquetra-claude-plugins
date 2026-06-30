---
date: 2026-06-30
topic: antigravity-teammate-plugin
maturity: requirements-ready
scope: deep-feature
source: docs/ideation/2026-06-30-antigravity-teammate-plugin-ideation.md (survivors 1-7)
---

# Antigravity Teammate Plugin

## Summary

Build a new Infiquetra Claude Code plugin whose primary surface is Antigravity-backed teammates:
`agy-coder` for write-capable implementation and `agy-reviewer` for adversarial second opinions. Both
teammates, plus the secondary `/agy:delegate` quick command, must route through the same delegation
envelope, wrapper, write boundary, evidence bundle, and harness-proof contract.

## Problem Frame

The current Antigravity integration fails at the harness boundary as much as at the model boundary.
Claude Code can misuse the plugin surface, long jobs can detach or hang, and a run that appears
"delegated to agy" can be a Claude-clone fallback with no `agy` process at all.

Local dogfood also showed that capable delegated code is not enough. Delegates can wander, commit,
push, game tests, overclaim, silently no-op, or write late through orphaned descendants. The plugin
therefore has to make delegation structurally observable and bounded, not merely better-prompted.

## Key Decisions

**New teammate plugin, not a fork.** The v1 surface is a first-party Infiquetra plugin centered on
preconfigured teammates. Prior art from `antigravity-cc/agy` and Hermes can inform the wrapper, but
the current thin-forwarder UX is not the product surface.

**The internal primitive is a delegation envelope.** Agents and commands are affordances that fill and
validate one shared envelope. This prevents the quick path from becoming a weaker bypass around the
teammate harness.

**Write-capable v1 is required.** Read-only reviewer work matters, but a v1 that cannot safely delegate
implementation does not satisfy the goal. Write capability is allowed only through explicit mode,
write-set, apply-policy, and evidence rules.

**The product guarantee is managed apply semantics, not one fixed isolation mechanism.** The operator
should not have to choose clone versus worktree during normal use. Planning may choose the proven
internal boundary, but live-tree mutation must still cross the same write-set and apply gates.

**Evidence is the return value.** Chat prose is a projection of the local evidence bundle. A run cannot
claim `success` or `applied` unless the bundle proves a real `agy` invocation and records what happened.

## Actors

A1. **Claude Code orchestrator** receives the operator's request, selects an Antigravity teammate or
quick command, and remains the verifier and committer of record.

A2. **`agy-coder` teammate** receives implementation tasks, turns them into strong Antigravity coder
task packets, invokes the wrapper, and returns the evidence projection. It does not solve the task
directly with Claude editing tools.

A3. **`agy-reviewer` teammate** receives review tasks, applies a second-opinion lens, invokes the
wrapper, and returns findings with evidence. It defaults to adversarial review.

A4. **Shared wrapper** launches and supervises `agy`, enforces run lease/provenance, manages write
boundary and apply policy, and writes the evidence bundle.

A5. **Antigravity / `agy` CLI** is the external execution engine. Its self-report is input, not proof.

A6. **Operator** chooses when to use Antigravity teammates, may set model/evidence/apply options, and
reviews surfaced failure evidence.

## Requirements

What must be true of v1, grouped by concern. IDs are stable and continuous.

**Claude-facing surfaces**

- R1. The primary v1 surface is two preconfigured teammates: `agy-coder` and `agy-reviewer`.
  `agy-investigator`, `agy-general`, and a reviewer-agent zoo are out of v1 by default.
- R2. `agy-coder` and `agy-reviewer` are bridge agents. Their job is to accept the task, build a
  delegation envelope and rendered `agy` prompt, invoke the shared wrapper, and return the evidence
  projection. They must not perform the substantive coding or review directly with Claude tools.
- R3. The secondary quick-use surface is one generic `/agy:delegate` command with explicit role and
  mode options. It uses the same envelope and wrapper contract as the teammates.
- R4. No raw runner is exposed as a normal user-facing command. Debug access, if any, is internal or
  clearly marked as unsafe diagnostics.
- R5. Each delegated turn is a fresh `agy` invocation by default. Stateful `agy` conversations are
  deferred until fresh runs have proven reliable and a future design defines recovery semantics.

**Delegation envelope and task packets**

- R6. Every teammate turn and `/agy:delegate` invocation produces one validated delegation envelope
  carrying at least the role, mode, reviewer lens when applicable, model selection, write-set, apply
  policy, evidence level, timeout/check expectations, and provenance requirements. Exact field names
  are deferred to `/plan`.
- R7. The envelope is versioned as a product contract. Any behavior, schema, prompt, command, or
  guidance change that affects it must update release surfaces and drift tests in the same PR.
- R8. `agy-coder` renders a strong coder task packet layered over the hard contract: expert software
  engineer framing, closed write-set, read-broad/write-narrow instruction, no git operations,
  `PLAN_GAP`, `TEST_CONFLICT`, `PATH_MISSING`, exact verification expectations, and a run report.
- R9. `agy-reviewer` defaults to an adversarial second-opinion lens. V1 also supports explicit lenses
  for `quality`, `scope-gap`, and `security-ops` without splitting into multiple reviewer agents.
- R10. Prompt/persona guidance never substitutes for wrapper enforcement. If a prompt says "do not
  edit outside the write-set" but evidence shows it did, the evidence wins and the run is not clean.

**Run lease and provenance**

- R11. The wrapper records a run lease before trusting output: resolved `agy` executable, sanitized
  command shape, working directory or work boundary, process identity, start/end timing, transcript or
  log path, liveness signal, timeout class, and shutdown outcome.
- R12. The wrapper must avoid the known detach/hang trap. A long job may not be launched through an
  opaque background path that can produce a zero-byte hang. V1 uses only an empirically proven
  foreground, named, or recovery-style invocation path for the current harness, and still requires
  per-run transcript proof because spawn shape is not a reliable real-agy discriminator.
- R13. A run can return `success`, `patch-ready`, or `applied` only when the evidence bundle proves a
  real `agy` invocation. If no real `agy` process or transcript evidence is found, the run returns
  `fallback-suspected`.
- R14. The real-agy versus fallback verdict is transcript-backed. Claude-clone signals such as direct
  Claude `Read`/`Edit`/`Write` work without an `agy` command are failure evidence, not acceptable
  delegation.
- R15. Timeout, no-output, killed, orphan-suspected, or incomplete-shutdown outcomes are first-class
  statuses. They never collapse into generic success prose.

**Write modes and apply policy**

- R16. V1 supports exactly three write modes: `no-write`, `patch-only`, and `auto-if-clean`.
- R17. `no-write` is the default for reviewer work. It must not mutate the live tree.
- R18. `patch-only` may produce a patch and evidence but never applies to the live tree automatically.
- R19. `auto-if-clean` may apply to the live tree only when an explicit write-set is present, the live
  tree has a recorded pre-run git state compatible with applying, the verification policy is explicit
  and satisfied, the run proves real `agy`, changed paths are inside the write-set, post-run git proof
  is clean, and no timeout/no-output/fallback/out-of-scope status occurred.
- R20. No explicit write-set means no automatic live-tree mutation. Inferred or proposed write-sets are
  allowed only for `patch-only` and must be surfaced as review evidence.
- R21. A write-set is a capability boundary for apply decisions. If `agy` writes outside it, the plugin
  preserves the patch/evidence for review and returns an out-of-scope status instead of applying.
- R22. The delegate must not commit, push, rewrite history, or alter remotes. Any such evidence is a
  failure signal. Claude Code remains the sole committer.
- R23. The wrapper provides managed apply semantics through a patch inbox/import path. Planning may
  choose the internal work boundary by spike, but the routine caller sees mode, write-set, and evidence,
  not clone/worktree mechanics. If v1 does not provide OS-level filesystem containment, the evidence and
  docs must state that the apply guarantee covers repository patch import, not whole-machine side
  effects.

**Evidence bundle and status machine**

- R24. Every run writes a complete local evidence bundle, regardless of how much evidence is returned
  inline. If the bundle cannot be written, the run fails.
- R25. The bundle includes the original task, rendered `agy` prompt, sanitized command shape, run lease,
  transcript/log path, changed paths, git proof, verification commands and outcomes, real-agy verdict,
  apply decision, final status, and final result.
- R26. Evidence projection is configurable per delegation as `full`, `summary`, or `minimal`, but the
  full local bundle remains available for audit. The default before repeated proof is `full`.
- R27. The chat response is derived from the bundle and names the bundle path. It does not ask Claude
  to trust the delegate's self-report.
- R28. Status values are explicit enough for downstream workflows to branch on: clean success,
  patch-ready, applied, plan-gap, test-conflict, path-missing, timeout, no-output, fallback-suspected,
  out-of-scope-mutation, checks-failed, and error. Exact names are deferred to `/plan`.

**Proof, tests, and release discipline**

- R29. Static repo tests cover plugin manifest, marketplace metadata, changelog/version drift, command
  and agent prompt availability, envelope compatibility, and release-surface synchronization.
- R30. Direct wrapper tests prove run-lease creation, long-run handling, status transitions, evidence
  bundle creation, explicit write-set enforcement, patch-only behavior, and auto-apply refusal cases
  without requiring Claude Code.
- R31. Live Claude Code harness proof is required before v1 can claim teammate support. It must include
  one tiny `agy-reviewer` run and one tiny `agy-coder` write run in a scratch or fixture repo.
- R32. The live harness proof audits transcripts for both runs and proves the packaged agents invoked
  the wrapper/`agy` path and did not solve with Claude `Read`/`Edit`/`Write` tools.
- R33. The live coder proof must exercise explicit write-set handling and either patch import or
  `auto-if-clean` application. A static test suite alone is not sufficient.
- R34. Plugin release work follows repo discipline: plugin manifest, marketplace entry, changelog,
  README/usage docs, and drift guard tests move together.

## Key Flows

F1. **Team coder auto-apply.** **Trigger:** Claude Code selects `agy-coder` for a write-capable task.
The teammate builds a coder envelope with an explicit write-set and `auto-if-clean`; the wrapper runs
`agy`, captures evidence, validates changed paths and checks, applies only if clean, and returns the
bundle projection. **Covers R1, R2, R6, R8, R16-R25.**

F2. **Team reviewer second opinion.** **Trigger:** Claude Code selects `agy-reviewer` for a review.
The teammate builds a no-write reviewer envelope with the adversarial lens unless another lens is
explicitly supplied; the wrapper runs `agy`, writes evidence, and returns findings with the bundle
path. **Covers R1, R2, R9, R17, R24-R28.**

F3. **Quick one-shot delegation.** **Trigger:** the operator or orchestrator uses `/agy:delegate`.
The command validates explicit role and mode, fills the same envelope used by teammates, invokes the
same wrapper, and returns the same evidence projection. **Covers R3, R6, R16, R24-R28.**

F4. **Fallback detected.** **Trigger:** the transcript or process proof shows no real `agy`
invocation, or shows Claude directly doing the work. The wrapper returns `fallback-suspected`, blocks
auto-apply, and preserves evidence for audit. **Covers R11-R15, R19, R24-R28.**

F5. **Out-of-scope write.** **Trigger:** a write-capable run changes a path outside the explicit
write-set. The wrapper refuses auto-apply, returns a patch/evidence bundle, and surfaces `PLAN_GAP` or
out-of-scope evidence for Claude/operator review. **Covers R19-R23, R28.**

F6. **Long job liveness failure.** **Trigger:** a run exceeds timeout, produces no output, or cannot
prove shutdown. The wrapper returns a non-success status, records the liveness evidence, and never
lets the delegate's self-report mask the failure. **Covers R11, R12, R15, R24-R28.**

F7. **Harness proof.** **Trigger:** v1 readiness is evaluated. The proof matrix runs static tests,
direct wrapper tests, and two live Claude Code harness runs, then audits transcripts before the
teammate surface is considered proven. **Covers R29-R33.**

## Acceptance Examples

AE1. **Clean coder apply.** **Covers R19, R24-R27.** Given `agy-coder` receives a task with
`auto-if-clean`, an explicit write-set, a compatible pre-run git state, and an explicit verification
policy, when `agy` changes only allowed paths and verification passes, then the plugin applies the patch
and returns `applied` with a local evidence bundle path.

AE2. **No write-set means no apply.** **Covers R19, R20.** Given a write-capable request asks for
`auto-if-clean` without an explicit write-set, when the envelope is validated, then the run is rejected
or downgraded to non-applying behavior; it never mutates the live tree automatically.

AE3. **Out-of-scope mutation is preserved, not hidden.** **Covers R21, R28.** Given `agy` changes a
file outside the write-set, when the wrapper evaluates the run, then no auto-apply occurs and the
evidence bundle records the changed paths plus the out-of-scope status.

AE4. **Claude-clone fallback fails closed.** **Covers R13, R14.** Given a packaged teammate produces
useful-looking output but the transcript shows no `agy` process and direct Claude file tools, when the
wrapper classifies provenance, then the result is `fallback-suspected` and cannot be marked clean.

AE5. **No-output hang fails closed.** **Covers R12, R15.** Given a long job produces no transcript
growth until timeout, when the wrapper closes the run, then the status is timeout or no-output and no
patch is applied.

AE6. **Reviewer remains no-write by default.** **Covers R9, R17.** Given `agy-reviewer` runs without
an explicit patch-producing mode, when it completes, then it returns review findings and evidence only,
with no live-tree mutation.

AE7. **Quick command is not a bypass.** **Covers R3, R6.** Given `/agy:delegate --role coder` is used
instead of a teammate, when it runs, then the same envelope validation, evidence bundle, status
machine, and write-set rules apply.

AE8. **Live harness proof catches direct solving.** **Covers R31-R33.** Given the tiny `agy-coder`
harness fixture runs, when transcript audit shows the bridge agent edited files directly with Claude
tools instead of invoking the wrapper, then teammate proof fails even if the fixture's final files look
correct.

## Success Criteria

- The requirements can feed `/plan` without reopening whether this is a new plugin, whether v1 is
  write-capable, or whether teammates are the primary surface.
- A planner can map every survivor from the ideation doc to at least one requirement or scope boundary.
- No v1 path can auto-apply without explicit write-set, real-agy proof, in-scope changed paths, passing
  checks, and clean git proof.
- Every run has a local evidence bundle with a real-agy versus fallback verdict.
- The live Claude Code harness proof demonstrates both reviewer and coder teammate flows before the
  teammate surface is called reliable.
- Release surfaces and drift tests make prompt, command, schema, and metadata changes visible.

## Scope Boundaries

- Do not fork or patch `antigravity-cc/agy` as the product answer for v1. Borrow prior art only.
- Do not build a provider-neutral external-agent platform first. This plugin is Antigravity-backed.
- Do not ship `agy-investigator`, `agy-general`, or multiple named reviewer agents in v1.
- Do not expose a raw runner as the convenient path.
- Do not default to stateful `agy` conversations.
- Do not ship read-only-only v1.
- Do not let prompt instructions substitute for write-set enforcement, evidence, or transcript proof.
- Do not promise adversarial OS-level filesystem containment in v1 unless planning proves and scopes it.
- Do not treat static tests as enough proof for the teammate surface.

## Dependencies / Assumptions

- The `agy` CLI is installed, authenticated, and callable in the local Claude Code environment used for
  proof. Exact model aliases and CLI flags may drift and must be verified during planning.
- Claude Code plugin-packaged agents can be constrained enough, or at least observed strongly enough,
  to prove they acted as bridges. This is a live harness question, not a documentation question.
- The wrapper can access durable transcript or log evidence sufficient to distinguish real `agy` from
  Claude-clone fallback.
- The internal write boundary can be made reliable on the operator's machine. Clone, worktree, or other
  boundary mechanics are planning choices as long as the managed apply semantics hold.
- Any v1 that runs with ambient filesystem access must not represent `auto-if-clean` as whole-machine
  containment. Planning must decide whether to add an audit, an OS sandbox, or explicit limitation text
  for possible side effects outside the target repository.
- The first v1 implementation can tolerate higher token/evidence cost by default. Lower-evidence
  projections exist for future token reduction but do not remove the local bundle.

## Outstanding Questions

**Deferred to planning**

- What is the plugin's final directory/name and command namespace?
- Which internal boundary best supports managed apply on this machine: disposable clone, worktree, or
  another proven wrapper strategy?
- What exact Claude Code agent/tool constraints are available for plugin-packaged teammates, and what
  transcript audit proves they were honored?
- What exact `agy` invocation path avoids the background/no-output failure in the current harness?
- What are the exact envelope and evidence bundle schemas, status names, and compatibility rules?
- Which verification commands are defaulted by the wrapper versus supplied per delegation?
- What claim does v1 make about filesystem side effects outside the target repository, and how is that
  claim surfaced or audited?
- How should live Claude Code harness proof be automated enough to repeat during development without
  making ordinary unit tests depend on external credentials?

## Sources / Research

- `docs/ideation/2026-06-30-antigravity-teammate-plugin-ideation.md` — seven survivors unified here:
  delegation envelope, patch inbox importer, run lease, evidence status machine, bridge agents, coder
  packet library, and proof matrix.
- `docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md` — locked constraints and prior
  Socratic decisions.
- `docs/external-agent-delegation/README.md` — real-agy versus Claude-clone audit, failure taxonomy,
  and review-fix evidence.
- `docs/external-agent-delegation/blueprint.md` — read broad/write narrow, `PLAN_GAP`,
  `TEST_CONFLICT`, validation floor, and delegate failure taxonomy.
- `docs/external-agent-delegation/agy-plugin-fork-decision.md` — current plugin mechanics,
  `--background` hang record, historical named/recovery path evidence, and fork/copy decision frame.
  Read alongside the newer fallback audit in `docs/engineering-journal/LEARNINGS.md`.
- `docs/engineering-journal/LEARNINGS.md` — durable lessons on silent Claude fallback, background
  hangs, no-op risk, and late-writing orphan agents.
- `docs/engineering-journal/DECISIONS.md` — no-jail post-hoc verification decision and revisit
  triggers for stronger containment.
- `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md` — related external
  engine routing boundaries and fallback visibility.
- `docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md` — local precedent for
  evidence as a durable contract.
- `docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md` — related capability and
  mutation-boundary vocabulary.
