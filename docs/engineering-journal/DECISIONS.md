# Decisions — Infiquetra Claude Plugins

> **ADR-style records of plugin-pattern / convention / tooling choices.** When you commit a chosen path over alternatives — pick A over B, flip a flag, change a threshold, choose a category, adopt a tool — capture rationale + tradeoff + revisit-when condition + commit hash.
>
> The point is to make **revisit conditions explicit** so a future Claude (or human) reading "why did we pick X?" gets the answer cold, including when it would be right to reconsider.
>
> **Append new entries to the top.** Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short title (commit hash)  {#slug}
>
> **Decision.** What we picked.
> **Rejected alternatives.** What we considered and didn't pick.
> **Rationale.** Why this won.
> **Revisit when.** Condition that would change the calculus.
> **Refs.** Related LEARNINGS / QUEUED / narratives.
> ```
>
> When new evidence invalidates a decision, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**.

---

## 2026-06-21

### Parallel-layer emitter, refute-N judge-panels, /plan author-validate-approve-persist-emit, /work halt-not-degrade, and provenance guard at save() (PR pending — SHA-fill on merge)  {#parallel-refuteN-emitter-plan-work-wiring}

**Decision.** Seven key design calls that together close the R9 keystone:

- **KTD1 — direct spec authoring.** `/plan` authors the spec directly (no code generation, no LLM-to-spec translation). The hand-authored campaign harness dogfooded the spec shape before the emitter automated it; authoring by hand validated that thin prompts + structured fields are the right abstraction.
- **KTD2 — thin prompts.** Each unit prompt is a one-line thin pointer to the plan doc, not a prose transcription. The emitter appends fan-out reconciliation, budget riders, and return contracts automatically; depth comes from the agent reading the plan.
- **KTD3 — refute-N defaults n=3/majority/cap 7.** Default `verify` panel: `n=3`, `pass_rule="majority"` — a finding survives unless ≥2 of 3 verifiers refute it. Hard cap at `VERIFY_N_CAP=7` (guards the rate-limit overcorrection that occurred at 22-23 verifiers); soft warn band above 5.
- **KTD4 — topological-layer parallelism.** `dependency_layers(spec)` (Kahn) computes independent layers; a layer of >1 unit emits one `parallel([...])` wave. Pilot implicit barriers are included in the layer computation so the gate survives complex topologies. Cycles fail emit.
- **KTD5 — `verify` as an optional Unit field.** Present → emits a refute-N judge-panel in the generated script; absent → round-trips unchanged (existing specs and `team_emitter.py` never gain a spurious key). Verifiers run at the same `{model, effort}` tier as the parent unit (R4).
- **KTD6 (was KD3) — `/work` halts off-host, not recompile-down.** A `cc-workflows-ultracode` choice is guarantee-bearing (parallel fan-out + refute-N). When the Workflow tool is absent or the spec/ref is missing, `/work` halts with a recovery line — it never silently substitutes hand-rolled serial subagents (the campps issue-38 failure). This is explicitly NOT the off-host recompile-down path (`recheck_orchestration_capability`), which is reserved for `/loop`/`/resume` in operator-absent polling contexts.
- **KTD7 — guard at the `save()` chokepoint.** `saga.py save` rejects a tick that newly asserts `orchestration_mode != orchestration_operator_choice` without an `orchestration_downgrade` note justifying THAT divergence — `/work` cannot cover a secret backend substitution by rewriting `operator_choice`. The guard is precise: a no-op when no `operator_choice` is asserted, and it lets an *unchanged* byte-identical carry-forward of a prior already-vetted divergence through (a stale note from a *different* divergence cannot launder a fresh one). The only legitimate paths: operator picks a backend, `/work` records it via `--orchestration-mode` (choice derives equal, no divergence); or a genuine degrade carries its `orchestration_downgrade` note WITH the divergence.

**Dogfooding fix (operator_choice auto-derive).** The `_build_save_saga` auto-derive of `operator_choice` from `--orchestration-mode` must not fire on a tick that carries NO orchestration args at all (a plain progress tick). An auto-derived `operator_choice` on a no-orchestration-args tick was triggering a false-divergence rejection of normal progress ticks by the provenance guard. Fix: the auto-derive only applies when `--orchestration-mode` is explicitly set; an absent flag leaves both `operator_choice` and `recommended` as empty strings and the guard does not fire.

**`orchestration_ref` lifecycle for `cc-workflows-ultracode`.** At `/plan` time the ref is set to the **spec JSON path** (the canonical artifact — the `.workflow.js` is regenerable and is NOT the durable ref). After `/work` launches the Workflow and receives a workflow id, it overwrites the ref with that id via a second tick. The spec JSON is always the authoring artifact; the workflow id is the transient execution handle.

**Rejected alternatives.** (a) Use the `.workflow.js` as the `orchestration_ref` — rejected: the script is derived; a re-plan that edits the spec would leave the ref pointing at a stale script; the spec JSON is the single source of truth. (b) Allow `/work` to fall back to inline when the Workflow tool is absent — rejected: this loses exactly the parallel fan-out and refute-N guarantees the operator chose ultracode for; the campps issue-38 post-mortem is the evidence. (c) Verify panel verifiers at a cheaper tier than the unit — rejected (R4): a mis-tiered verifier validates a different cost surface; same-tier keeps the oracle honest. (d) Check for divergence on every tick (not just orchestration ticks) — rejected: over-fires on normal progress ticks; the guard must be scoped to ticks that carry an explicit `orchestration_mode`. (e) Place the guard in the `Saga` dataclass constructor or in `render_envelope`/`parse_envelope` (KTD7) — rejected: that would reject an unsaved render→parse round-trip with `operator_choice != mode` (e.g. `tests/test_saga_saga.py:1259`); the guard must be `save()`-scoped so pure (de)serialization stays valid.

**Rationale.** Thin prompts + spec-as-contract give the emitter clean separation from the plan body; the emitter handles all the boilerplate (budget riders, reconciliation, return contracts). The verify cap at 7 and the halt-not-degrade rule are both grounded in observed failure modes (rate-limit overcorrection; campps #38 silent substitution). The dogfooding fix is a one-condition guard that narrows the auto-derive to exactly the ticks where it is meaningful.

**Revisit when.** Real override-rate data (R12) shows the halt-not-degrade rule is too conservative (operators frequently switch backends mid-session because the Workflow tool is unavailable — then reconsider a softer fallback path); the verify panel's same-tier rule proves too expensive on large opus/high specs (then consider a tiered verifier vocab); the `VERIFY_N_CAP` value needs recalibrating based on observed rate-limit behavior.

**Refs.** `plugins/saga/scripts/execution_spec.py` (`dependency_layers`, `Verify`, `_emit_verify_panel`, `emit_workflow_script`); `plugins/saga/scripts/saga.py` (save provenance guard); `plugins/saga/skills/plan/SKILL.md` §5.2a; `plugins/saga/skills/work/SKILL.md` §1.5; `plugins/saga/references/execution-spec.md`; `plugins/saga/references/operator-choice.md` §6; saga 0.37.0.

### Stale-main SessionStart hook generalized to run in ANY git repo, self-contained in the plugin (PR pending — SHA-fill on merge)  {#stale-main-hook-generalized}

**Decision.** The saga `SessionStart` hook (`plugins/saga/hooks/stale_main_session_hook.py`) now runs in **ANY git repo with an `origin` remote** — there is no repo-presence gate. It is **self-contained in the plugin**: it no longer invokes `tools/stale_main_guard.py` (which remains the repo-local manual tool / R18 artifact). It detects the default branch generically (`git symbolic-ref --short refs/remotes/origin/HEAD` → strip `origin/`, fall back to probing `origin/main` then `origin/master`), never hardcoding `main`. The operator chose **auto-fast-forward when safe**: if the local default branch is behind `origin/<default>` AND the current branch IS the default branch AND the tree is clean → `git merge --ff-only origin/<default>`; otherwise (feature branch, dirty, or a linked worktree) → WARN only. Preconditions (not-a-repo, no `origin`, undeterminable default) → exit 0 silent. Always non-blocking; emits the standard SessionStart `additionalContext` shape only when there is a message. Supersedes [#stale-main-sessionstart-hook](#stale-main-sessionstart-hook).

**Rejected alternatives.** (a) Warn-only everywhere (no auto-FF) — rejected: the operator wants the stale local default branch fixed automatically in the common safe case, not just flagged. (b) Opt-in-per-repo (keep some presence/marker gate so the behaviour only activates where explicitly enabled) — rejected: defeats the point of a user-scope distributed hook; the safety is intrinsic (auto-FF only when cleanly ON the default branch, which git guarantees is the holding checkout — never a linked worktree).

**Rationale.** Saga installs at user scope, so the old repo-presence gate made the hook inert in every repo except this one. Auto-FF is worktree-safe by construction: being ON the default branch means you hold its checkout (git forbids the same branch in two worktrees), so the auto-FF never mutates another worktree's branch. Generic default-branch detection avoids hardcoding `main` and handles `master`-default repos. The small git-logic overlap with `tools/stale_main_guard.py` is accepted for now (the plugin hook must be self-contained; the repo tool stays as the manual R18 path).

**Revisit when.** Auto-fast-forwarding in arbitrary repos proves surprising to users (then reconsider warn-only-default or an opt-out), or the duplicated git logic across the plugin hook and `tools/stale_main_guard.py` drifts (then consider consolidating to one source).

**Refs.** `plugins/saga/hooks/stale_main_session_hook.py`, `plugins/saga/hooks/hooks.json`, `tests/test_stale_main_session_hook.py`; `tools/stale_main_guard.py` (left intact, R18); saga 0.36.0. Supersedes [#stale-main-sessionstart-hook](#stale-main-sessionstart-hook).

### Stale-main guard ships as a repo-guarded SessionStart hook in the distributed saga plugin (PR pending — SHA-fill on merge)  {#stale-main-sessionstart-hook}

> **Superseded 2026-06-21 by [#stale-main-hook-generalized](#stale-main-hook-generalized)** — the hook is now self-contained and runs in any git repo (no repo-presence gate, no dependency on `tools/stale_main_guard.py`).

**Decision.** Install the existing `tools/stale_main_guard.py` (R18) as a `SessionStart` hook (matcher `startup|resume`) wired through the **saga plugin's** `hooks/hooks.json` via a thin wrapper `plugins/saga/hooks/stale_main_session_hook.py`. Because saga is distributed to other repos, the wrapper carries a **repo-presence guard**: it resolves the CWD repo root (`git rev-parse --show-toplevel`) and only runs the guard if `<root>/tools/stale_main_guard.py` exists — otherwise it exits 0 silently (no `git fetch`, no subprocess). It invokes the repo's OWN guard copy (not `${CLAUDE_PLUGIN_ROOT}`'s) and surfaces output as SessionStart `additionalContext` (`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`), always exit 0.

**Rejected alternatives.** (a) A project-level `.claude/settings.json` SessionStart hook — rejected: `.claude/` is gitignored here, so the hook config can't be committed/shared. The committable home is the saga plugin's `hooks.json`. (b) Hardcoding a repo-name check inside the wrapper — rejected: brittle and fork-hostile; presence of the guard tool at the repo root IS the signal, so any fork that ships the tool gets the behaviour for free and every other repo stays inert.

**Rationale.** The guard already exists and is non-blocking; the only missing piece was an install point that (1) is committable and (2) cannot fire in the many other repos where saga is installed. The presence-of-tool guard satisfies both without coupling the distributed plugin to this repo's identity.

**Revisit when.** Saga grows a repo-agnostic SessionStart behaviour that should run everywhere (then the presence guard becomes the wrong default and the wrapper needs an explicit opt-in/opt-out), or Claude Code changes the SessionStart stdin/`additionalContext` contract.

**Refs.** `plugins/saga/hooks/stale_main_session_hook.py`, `plugins/saga/hooks/hooks.json`, `tools/stale_main_guard.py`, `tests/test_stale_main_session_hook.py`; saga 0.35.0.

### Saga tiering + execution-mechanism campaign — shipped, all 5 epics merged (#241–#245)  {#saga-tiering-execution-campaign-shipped}

**Decision.** The campaign planned in [#saga-tiering-execution-campaign-plan](#saga-tiering-execution-campaign-plan) **shipped in full** — all 5 epics merged to `main` as their own squashed PRs, in the planned barrier order, with the per-unit `{model, effort}` tier intact: **epic0** (U2, U3) `#241` `27ec81c`; **epic1** (U4, U5, U6) `#242` `1575907`; **epic3** (U7, U8, U9) `#243` `c9757e3`; **epic4** (U14, U15, U16) `#244` `9bdf363`; **epic2** (U10–U13) `#245` `9e9f29c`. The locked KTDs held: **KTD2** per-unit tiering (4 callable agents pinned — `homelab-sre`→opus, `sdlc-operator`/`unifi-network-ops`/`release-orchestrator`→sonnet, `mechanical-executor`→haiku); **KTD5/R8** display-label map renders "dynamic workflows" while the enum `cc-workflows-ultracode` stays byte-for-byte frozen (`saga.py:79`); **KTD7** `redis-channel-coach` documented `tiering_exempt` (MCP-`instructions=` pointer, not Agent-dispatched); **R7** gated-vs-advisory recommender split (`lifecycle_state.py`, `consensus_is_gated` default `True`); **R9** one execution-spec → two emitters (`team_emitter.py` + the workflow-script emitter), saga stores only the `orchestration_ref` pointer. The full gate is green on the post-merge tree (926 tests, both validators, ruff format+check, mypy 67 files, issue-contract parity). **R4** (global `~/.claude/CLAUDE.md` tier rule) is applied-inline per KTD8 — **operator confirms out of band**, tracked in the U17 reconciliation report, not built by any unit.

**Rejected alternatives.** Force-merging a non-green epic to "finish the run" (rejected — the autonomous oracle is the gate; KTD3 forbids weakening it); auto-resolving a cross-epic `saga.py` rebase conflict (none occurred, but KTD9 forbids it regardless — load-bearing-code conflicts HALT for review); folding R4 into the workflow (KTD8 — a global out-of-repo file must never be edited in an unattended fan-out).

**Rationale.** Hand-authoring the one ultracode harness dogfooded R9 and validated the execution-spec by walking it before Epic 2 automated it; epic-grouped PRs (~5 CI runs) kept isolation without per-unit churn; the merge gate stayed honest because the gate-fix loop was capped and barred from weakening tests/assertions. The campaign also retro-hardened the merge gate: `main` was branch-protected (the 5 checks + strict) *before* the run, so GitHub enforced the gate rather than leaning on poll discipline alone.

**Revisit when.** Real override-rate data (R12, surfaced by `override_rate_reader.py`) justifies re-weighting a recommender default; a future rebuild needs the `cc-workflows-ultracode` enum actually renamed (then do the migration the display-label map deferred); the Workflow tool's `model`/`effort`/`budget` API changes under the harness.

**Refs.** Reconciliation report `docs/analysis/2026-06-21-saga-tiering-execution-campaign-report.md` (every R-ID → landed unit); plan + sibling `.workflow.js`; [#saga-tiering-execution-campaign-plan](#saga-tiering-execution-campaign-plan); LEARNINGS [#display-label-map-decouples-enum-from-prose](#display-label-map-decouples-enum-from-prose), [#gated-vs-advisory-consensus-is-a-governance-split](#gated-vs-advisory-consensus-is-a-governance-split), [#validate-plugins-only-scans-top-level-md](#validate-plugins-only-scans-top-level-md).

### Plan the saga tiering + execution-mechanism campaign as one workflow-built, per-unit-tiered build (plan PR pending — SHA-fill on merge)  {#saga-tiering-execution-campaign-plan}

**Decision.** Plan the **whole** campaign (5 epics, 17 units U1-U17, requirements R1-R18) in one Deep plan and execute it through **one hand-authored ultracode workflow** (`docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`) with a per-unit `{model, effort}` tier on every step (**5 Opus / 11 Sonnet / 1 Haiku**, operator-approved). Topology: `Preflight → parallel(Epic0, Epic1, Epic3) → barrier(E0+E1 merged) → parallel(Epic2, Epic4) → Final`, each epic an isolated worktree+branch landing as one PR, **full hands-off auto-merge** when the 5 required CI checks are green. Four operator/derived locks: **R7** gated-vs-advisory consensus via an explicit `/plan` interrogation question with a work-shape default (advisory → the existing `adversarial_confidence` ultracode branch); **R8** decouple-not-rename (display-label map → "dynamic workflows", enum `cc-workflows-ultracode` frozen); **R9** one spec, two emitters, saga points; **Epic 0** pins **4** callable agents (`redis-channel-coach` exempt — an MCP-instructions pointer, not Agent-dispatched).

**Rejected alternatives.** (a) Plan epic-by-epic as separate docs (the brainstorm's KD6) — the operator chose to plan the whole thing; each epic still lands as its own PR, so independent execution is preserved. (b) Per-unit PRs — rejected for CI volume (~16 CI runs); epic-grouped PRs (~5 runs) with serial intra-epic units keep isolation without the churn. (c) Rename the enum to `dynamic-workflows` — rejected: the enum is a stored contract carried in persisted sagas; a display-label map is cheaper and reversible. (d) Infer R7 purely from work-shape, or always-ask with no default — rejected for explicit-question-**with**-default: the governance call ("does the verdict need to stick?") is the operator's, but the default removes friction. (e) Edit `~/.claude/CLAUDE.md` (R4) from inside the autonomous workflow — rejected: a global file outside the repo must not be in an unattended fan-out; applied inline with confirmation (KTD8).

**Rationale.** Tiering is the genuine cross-doc seam, so it is the spine and lands first. Building the campaign **via** the workflow dogfoods R9 and validates the execution-spec by walking it manually before Epic 2 automates it. The autonomous oracle is sound — the test suite + the two plugin validators + the drift-guards gate every PR, and a red gate blocks the auto-merge — so full hands-off is safe behind green CI. R7 is a *surgical* split, not new plumbing: `adversarial_confidence` already exists as an ultracode trigger one branch from the `or needs_consensus` hard-force (`lifecycle_state.py:163` vs `:158`).

**Revisit when.** Real override-rate data (R12) justifies re-weighting a recommender default; a second workflow-built campaign shows epic-PR auto-merge is too coarse (drop to per-unit checkpoints); the Workflow tool's `model`/`effort`/`budget` API changes; or a future rebuild needs the enum renamed after all (then do the migration the display-label map deferred).

**Refs.** Plan `docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md` + sibling `.workflow.js`; requirements `docs/brainstorms/2026-06-20-saga-tiering-and-execution-campaign-requirements.md`; reference harness `infiquetra-context-library/scripts/context-fleet-audit.workflow.js`; [#operator-choice-docs-and-confidence](#operator-choice-docs-and-confidence); Track-1 builds queued under [#plugin-portfolio-groom-17-to-7](#plugin-portfolio-groom-17-to-7). Campaign-level LEARNINGS land at build time (U17).

## 2026-06-20

### Plugin portfolio groomed 17 → 7; marketplace version majors on plugin removal (04fa93e)  {#plugin-portfolio-groom-17-to-7}

**Decision.** Cut the marketplace from 17 plugins to **7 keepers** (`saga`, `team-execution`, `mission-control`, `redis-channel`, `home-lab-ops`, `unifi`, `deploy`). Removed 9 zero-fire plugins (`slack`, `pagerduty`, `splunk`, `identity-toolkit`, `sdk-lifecycle`, `python-toolkit`, `test-suite`, `docs-generator`, `todoist-manager`) and relocated `marketplace-lister` → `infiquetra-hermes-plugins` (removed here; **registration there is a separate follow-up**). Bumped the registry version **2.4.0 → 3.0.0 (major)** and aligned the stale nested `metadata.version` (2.1.0 → 3.0.0). Removed each plugin's `marketplace.json` entry + 7 client test files; repointed every doc that named a cut plugin (README table/examples, CLAUDE.md/AGENTS.md examples, MARKETPLACE_GUIDE, the `/ideate` worked example) to survivors; pruned the orphaned pagerduty/splunk/slack conftest fixtures.

**Rejected alternatives.** (a) Keep the thicker dev plugins (`python-toolkit`/`test-suite`/`docs-generator`) — rejected: zero fires; current LLMs subsume the knowledge-only ones; rebuild later if a real need appears (git history is the archive). (b) Minor bump (2.5.0) to match the rename campaign's precedent — rejected: removing 10 of 17 plugins breaks installs of those plugins, which is exactly what a major signals; a minor would bury the largest-ever portfolio change. (c) Hand-edit `marketplace.json` entry-by-entry — rejected for the double-`]` footgun; regenerated programmatically (load → filter to keep-set → dump → trailing newline) instead.

**Rationale.** The 17-plugin registry was mostly zero-fire service wrappers and knowledge-only plugins. Both validators are **structural, not enumerative** (`validate.py` requires each entry's `source` path to exist and validates whatever dirs are present; `validate_plugins.py` globs `plugins/*.md` = no-op), so a consistent dir+entry removal stays green with **no drift-guard rewrite** — the per-plugin metadata tests are match-tests for kept plugins only. Convention set: **marketplace registry version majors on plugin removal, minors on additions/metadata.**

**Revisit when.** A cut plugin is needed again (revive from git history + re-register), `marketplace-lister` lands in `infiquetra-hermes-plugins` (closes the relocate follow-up), or a "generate `marketplace.json` + README from `plugin.json`" survivor ships (fold the programmatic-regen into it).

**Refs.** Ideation: `docs/ideation/2026-06-19-plugin-ecosystem-grooming-ideation.md` + `2026-06-19-plugin-grooming-next-steps.md`. Track 1 survivor builds (tiering pins, hook harness, mechanical-handoff substrate) remain queued. Shipped via PR #232 (squash 04fa93e).

## 2026-06-17

### Mission-control issue-contract consumer sync (planned; issue #222)  {#mission-control-issue-contract-consumer-sync}

**Decision.** Plan issue #222 as a consumer-sync fix, not as a wholesale validator rewrite. `infiquetra-sdlc`
`issue_fields` remains the contract source; `mission-control` vendors generated data and keeps local
control flow hand-maintained. `validate_card_body(body)` stays body-only for compatibility, and a
context-aware prepared-readiness path should enforce issue-type/risk conditional fields when those
values are known. Prepared actionable issue bodies should be compiled from contract data rather than
from separate freehand Asgard/Olympus strings. Saga remains template-free and delegates issue body
ownership to `mission-control`.

**Rejected alternatives.** *Generate or vendor the home-lab validator algorithm into mission-control* —
rejected because the established boundary is generated data plus hand-maintained consumer algorithms.
*Replace `validate_card_body(body)` with a signature that requires type/risk* — rejected because
existing body-only callers such as `flow validate-card` should keep working. *Copy SDLC issue templates
into Saga* — rejected because the handoff boundary already says `mission-control` owns issue artifacts.

**Rationale.** Current `main` already enforces the always-required body surface through the generated shim,
so redoing that work would churn the wrong layer. The live gaps are prepared body compilation, risk-aware
readiness, stale template docs, and vendored schema/data parity.

**Revisit when.** The validator algorithm is relocated into `infiquetra-sdlc`; GitHub issue forms become
the only authoring path again; or Asgard starts accepting actionable Hermes task cards through a distinct
non-Olympus runtime gate.

**Refs.** Issue #222; plan
[`docs/plans/2026-06-17-mission-control-issue-contract-sync-plan.md`](../plans/2026-06-17-mission-control-issue-contract-sync-plan.md).

## 2026-06-13

### Correct the operator-choice ultracode framing; add `adversarial_confidence` + `has_code_surface` to the backend recommender (PR #215, squash `331505a`)  {#operator-choice-docs-and-confidence}

**Decision.** (1) Document `cc-workflows-ultracode` as deterministic fan-out **and** independent/adversarial
verification; the line to `team-execution` is **governance** (consensus + named scanner gates + guarded
deploy), framed as *artifact kind* — a throwaway signal vs a standing blocking verdict (operator-choice §3.2).
(2) Add `adversarial_confidence` as a second ultracode trigger beside `broad_independent_fanout` (default
False). (3) Add `has_code_surface` (default True): pure docs/spec/research neutralizes the output-blind
code-shaped proxies (`file_count`, `phase_count`, `has_infra`, `has_security`, `deployment_sensitive`);
`cross_repo` + `needs_consensus` survive as output-agnostic governance signals; the ultracode risk-suppressor
is itself gated by it. (4) Keep the lean precedence `team-execution > cc-workflows-ultracode > inline`
unchanged.

**Rejected alternatives.** *Plain reaffirm* — the §3.2 sentence is provably false against the Workflow tool
spec + official docs, and the `inline` reachability gap is real. *A new decision mechanism (rebuild the
ladder)* — it maps onto the existing `if/elif` and would churn the locked assertions for no behavioral gain.
*An `output_kind` enum (code|docs|research) as a primary chooser* — the code/docs correlation breaks (trivial
code, contested specs, broad code migrations); keying on the label misroutes those. *Keep a docs size-backstop
to team-execution* (Agent 1's caution) — the real governance docs go off-chain (`/strategy`, `/spec` don't
call the recommender); a governance doc that reaches it carries `needs_consensus` or breadth; forcing consensus
ceremony on uncontested docs is the misfire being fixed. *Names `no_deploy_surface` / `is_docs`* —
double-negative / too narrow; `has_code_surface` (positive, default True) names the real discriminator and
makes the safe default the conservative one.

**Rationale.** The routing was ~80% right (the code's risk gate already encoded governance); this makes the
prose true and reaches the two shapes the helper couldn't — adversarial confidence, and docs de-escalation.
Minimal blast radius: two default-safe kwargs + one predicate clause; every locked assertion is unchanged.

**Revisit when.** `has_code_surface` gets mis-set often in practice (it is a looser caller judgment than the
others — revisit toward deriving it, or folding `cross_repo` into the neutralizer); OR `parse_issue.py` gains a
real file-touch signal for infra/security (then neutralizing those two for docs is redundant); OR
`adversarial_confidence` over-routes to ultracode in practice (PR #216 gated it to an **explicit**
many-attempts request, but it still lacks a true magnitude gate — add one if it fires too readily).

**Refs.** LEARNINGS [#operator-choice-ultracode-framing-and-docs-proxies](LEARNINGS.md#operator-choice-ultracode-framing-and-docs-proxies);
refines [#operator-choice-framework](#operator-choice-framework).

## 2026-06-09

### Saga documentation source model and generated SVG visual kit (commit `2f9f2f2`)  {#saga-docs-source-model}

**Decision.** Maintain Saga's comprehensive user documentation from a curated docs model at
`plugins/saga/docs/model/saga-docs-model.yaml`, with generated SVG assets under
`plugins/saga/docs/assets/` rendered by `plugins/saga/scripts/render_docs_visuals.py`. The README is
the atlas/index; detailed manual pages live under `plugins/saga/docs/`.

**Rejected alternatives.**
- *Hand-maintained Mermaid or PNG diagrams as the primary visual source.* Rejected: the user explicitly
  wanted presentation-worthy visuals, and hand-maintained images drift from command/state reality.
- *Graphviz/D2/Python Diagrams as a new dependency.* Rejected: Saga's first four visuals are simple
  enough for deterministic direct SVG, and a new renderer dependency would make docs maintenance heavier.
- *Fully generated manual prose.* Rejected: command selection needs curated operator judgment; the model
  guards coverage while the manual carries human-readable decisions.

**Rationale.** Saga's facts were already present but scattered across wrappers, SKILL files,
dispatch-table references, saga state docs, and sibling Codex-port docs. A curated model gives reviewers
one coverage surface for commands, routes, readiness, scenarios, owners, and visuals; deterministic SVG
keeps the visual layer reviewable in git and reusable in README/manual/presentation contexts.

**Revisit when.** The visual set grows beyond simple fixed-layout diagrams, a docs site becomes a real
product surface, or the source model starts duplicating source-of-truth behavior instead of documenting
selection and coverage.

**Refs.** `docs/plans/2026-06-09-saga-comprehensive-documentation-plan.md`;
`plugins/saga/docs/model/saga-docs-model.yaml`; `plugins/saga/scripts/render_docs_visuals.py`;
LEARNINGS {#visual-docs-need-rendered-sanity-check}.

### Track renamed Hermes plugin repo in Mission Control (commit `75aae9e`)  {#mission-control-hermes-plugin-repo-rename}

**Decision.** Update the vendored Mission Control repository mapping to use
`infiquetra-hermes-plugins`, and update current journal references that point readers at the
Hermes-facing plugin repository.

**Rejected alternatives.**
- *Rely on GitHub redirects.* Rejected: project mapping data is not a clone URL and must match the
  canonical repository name used for board routing.
- *Leave journal references under the old name.* Rejected: the affected entries are current
  guidance for where to inspect Hermes plugin examples, not only historical evidence.

**Rationale.** This repo remains an active Mission Control source and reference lineage for the
Codex/Antigravity ports. Keeping the repo mapping and current guidance aligned avoids drift across
the plugin-family variants during the cutover.

**Revisit when.** Mission Control discovers repositories live instead of using vendored canonical
sets, or this repo no longer carries Mission Control as an active source plugin.

**Refs.** `plugins/mission-control/config/project-mappings.json`;
`plugins/mission-control/tests/test_project_mappings_resolution.py`.

## 2026-06-07

### Saga document formatting contract — one shared reference, table-rendered schema (squash `abcc06b`, PR #205, #201)  {#saga-doc-formatting-contract}

**Decision.** All nine saga doc-writing skills (ideate, plan, brainstorm, spec, strategy, retro, doc-review, code-review, founder-review) link one shared reference, `saga/references/formatting-style.md`, which mandates: ≤3-sentence blank-line-separated paragraphs; a one-line summary opening each ranked item/section; comparative or ranked data as a table; the compact engineer-facing schema fields (basis/confidence/complexity/axis/status, findings severity/file/line) rendered as a table while narrative fields stay prose; no-hard-wrap soft-wrap for generated output; and dropping a field a heading already carries. A pytest (`tests/test_saga_doc_formatting.py`) enforces the no-stacked-bold-label rule and the link-presence rule across the templates.
**Rejected alternatives.** Per-template duplication (drifts — `plan` fixed the CommonMark collapse once at `plan-sections.md` and `ideate` regressed into the stack anyway); a two-file `.fields.yaml` sidecar or a full doc serializer (both serve a field-level parser that does not exist, and a serializer cannot author narrative prose); fenced-block-for-all-fields (loses the at-a-glance scannability of the compact fields).
**Rationale.** A single referenced contract means one edit improves every skill and the next new one; the table render kills the CommonMark collapse, scans at a glance, and — since the schema consumer is an LLM reader plus a human, not a regex — is *more* legible, not a parse risk; the pytest makes the format unable to silently regress.
**Revisit when.** A real field-level parser is introduced for ideation/review schemas (a structured sidecar like the rejected R1 may then earn its place), or the pytest's stacked-bold-label heuristic proves too narrow or too noisy in practice.
**Refs.** `docs/plans/2026-06-07-saga-doc-readability-plan.md`; `docs/ideation/2026-06-07-saga-doc-readability-ideation.md`; `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`; LEARNINGS {#saga-doc-schema-no-field-parser}.

---

## 2026-06-05

### Whole-family plugin rename — Scheme Y: functional names + a shared `saga` category, drop the `infiquetra-` prefix, fold `blueprint-reviewer` into `saga` (squash `b6a03e0`, PR #199)  {#plugin-family-rename-scheme-y}

**Decision.** Rename the lifecycle/SDLC/deploy plugin family to short **functional names** and consolidate it under a shared marketplace **category `saga`** — "Scheme Y" of the rename options. The renames: `infiquetra-lifecycle` -> **`saga`**, `sdlc-manager` -> **`mission-control`**, `infiquetra-deploy` -> **`deploy`**. Drop the `infiquetra-` prefix (it was carried by only 2 of 18 plugins — this family — so prefix-consistency was never real). **Fold `blueprint-reviewer` into `saga`** rather than keeping it standalone: its idea/spec/issue rubric libraries move to `plugins/saga/references/rubrics/{idea,spec,issue}/{core,extras}/` and its reviewer script to `plugins/saga/scripts/lifecycle_review.py`. Rebrand the SDLC command/skill surface off the `sdlc-` prefix (`/issue`, `/board`, `/metrics`, `/triage`, `/flow`, `/labels`, `/milestones`, plus `/rollout` for deploy) and **drop the `/sdlc-create` compatibility alias**. Net marketplace: **17 plugins**, metadata **2.1.0**. This repo is **Phase 1** of a coordinated multi-repo migration.

**Kept on purpose (NOT renamed).** The SDLC-domain tokens are **externally anchored to the `infiquetra-sdlc` repo** (its issue taxonomy / schema / vocabulary), so renaming them here would desync from the source of truth. Retained as-is: the `sdlc_manager.py` module filename, `config/sdlc-schema.json`, `agents/sdlc-operator.md`, `docs/sdlc-issue-drafts/`, and the `INFIQUETRA_SDLC_PATH` env var. The directory prefix + the user-facing command/skill brand changed; the SDLC vocabulary inside `mission-control` did not. Also kept separate on purpose: `team-execution` and `deploy` are **NOT vendored into `saga`** — they stay standalone plugins that `saga` routes to, preserving their own boundaries (validator/nonprod automation for team-execution; tag-promotion/deploy mutation for deploy).

**Rejected alternatives.**
- *Prefix-consistency (rename everything TO `infiquetra-*`).* REJECTED — only 2 of 18 plugins carried the prefix, so "consistency" meant adding noise to 16 plugins to match 2; dropping it from the 2 is the cheaper, cleaner direction.
- *A `saga-*` sub-brand (`saga-lifecycle`, `saga-sdlc`, `saga-deploy`).* REJECTED — re-introduces a prefix we just removed and buries the functional name; the shared **category** `saga` groups the family in the marketplace without prefixing every name.
- *Consolidate the whole family into one `saga` plugin.* REJECTED — collapses three distinct boundaries (lifecycle engine, SDLC issue/board ownership, deploy mutation) into one plugin, losing the ownership seams the engine-merge campaign deliberately preserved; `mission-control` and `deploy` stay separate.
- *Descope to a `saga`-only rename (the DA's recommendation — leave `sdlc-manager` + `infiquetra-deploy` alone).* REJECTED — **Jeff overrode** the devil's-advocate descope: the family reads as one unit, so a half-rename (rename lifecycle, leave the prefix on deploy + the `sdlc-` brand on the SDLC commands) would leave the inconsistency the rename exists to fix. Whole-family in Phase 1.

**Rationale.** The lifecycle plugin's 13-command engine-merge campaign made `infiquetra-lifecycle` the spine of a tightly-coupled trio (lifecycle routes to SDLC handoff and to deploy). Short functional names (`saga` / `mission-control` / `deploy`) + a shared `saga` category make the family legible at a glance; the `infiquetra-` prefix added length without grouping value (2 of 18). Folding `blueprint-reviewer` in removes a fourth plugin whose rubric-based review is squarely lifecycle review work — it belongs under `saga`, not beside it. The SDLC tokens stay because they answer to an external contract (`infiquetra-sdlc`), and team-execution/deploy stay standalone because their boundaries are real, not cosmetic.

**Revisit when.** A fourth repo consumes these plugins and the short names collide with another `saga`/`deploy` in its namespace (revisit prefixing); OR `infiquetra-sdlc` itself renames its SDLC vocabulary (re-sync the kept-on-purpose tokens then); OR the `mission-control`/`deploy` boundaries stop earning their separateness (revisit the consolidation rejection). The follow-on migration phases (home-lab, the antigravity fork, dotfiles, infiquetra-sdlc) each have their own revisit triggers tracked with that phase.

**Refs.** Ship record: ARCHIVE [#plugin-family-rename-shipped](ARCHIVE.md#plugin-family-rename-shipped). The campaign whose engine now lives under `plugins/saga/` — [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign), ARCHIVE [#lifecycle-engine-merge-campaign-complete](ARCHIVE.md#lifecycle-engine-merge-campaign-complete). Squash `b6a03e0`, PR #199.

---

## 2026-06-04

### Rebuild `/optimize` as the lifecycle's metric-driven optimization engine — CE `ce-optimize` SINGLE-SOURCE port + infiquetra-native agent-usability metric class (NOT a merge), off-chain, saga UNTOUCHED (PR #197, squash d00a506)  {#optimize-engine-rebuild}

**Decision.** Rebuild `/optimize` from a 20-line stub into a **metric-driven optimization engine** — the **thirteenth and FINAL command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`, `/spec`). It runs a **bounded-experiment loop** toward a measurable target: pick a metric, baseline it, hypothesize, run a bounded experiment, measure the delta, keep or discard, repeat until the target is hit or the budget is spent. The five settled interview answers:

- **(Q1) Saga UNTOUCHED.** `/optimize` writes no saga, advances no `lifecycle_phase`, and makes **no `saga.py` edit at all** — mirrors `/strategy` / `/spec`. It is **off-chain** (advisory, never blocks `/loop`). It records the run **narratively**.
- **(Q2) ZERO new Python.** No new script ships; the engine is SKILL-resident. (Contrast `/qa`, which shipped one ported scorer — `/optimize` needs none.)
- **(Q3) Eight metric classes** — the **maximal v1 taxonomy**: performance, cost, reliability, **agent-usability**, security, quality, developer-experience, maintainability.
- **(Q4) Handoff DEFERRED.** No `docs/optimize/` is added to `handoff_envelope.py`'s `SOURCE_DIRS`, and **no `handoff_envelope.py` edit** ships. An optimization run's durable output is narrative, not a `/handoff`-discoverable artifact yet; wire it only when a run routinely needs to become an SDLC issue.
- **(Q5) Operator-choice OFFERS.** `/optimize` **does** cite operator-choice — independent experiments fan out cleanly across backends (default **serial inline**). The choice is recorded **narratively** (saga-untouched), not via an `orchestration_mode` saga field.

The five decisions a–e:

- **(a) One engine, no profile-coach sibling.** `/optimize` is a single metric-loop engine. There is **no** developer-psychographic question-coach sibling (gstack `plan-tune`'s shape) — that supplies nothing portable.
- **(b) Serial default + shed CE's worktree/parallel machinery.** Experiments run serial inline by default; CE `ce-optimize`'s in-engine worktree spawn / parallel-runner plumbing is **shed** (parallelism is offered via operator-choice, not baked into the engine).
- **(c) OFFERS operator-choice, recorded narratively** (see Q5).
- **(d) `/qa` boundary = gate vs loop.** `/qa` **gates a shipped change** (ship-or-not); `/optimize` **loops toward a measurable target** by bounded experiment. "Good / secure enough to ship?" → `/qa`; "drive this metric toward a target?" → `/optimize`.
- **(e) `/pulse` boundary = bounded vs continuous, and not a gate.** `/optimize` is a **bounded** experiment loop with a target and a budget; a future `/pulse` would be **continuous live telemetry**, not a one-shot loop and not a gate. The optimize-side boundary is settled; `/pulse` stays a separate queued item.

**Honest attribution (load-bearing).** `/optimize` is a **CE `ce-optimize` SINGLE-SOURCE PORT**. The **agent-usability** metric class is an **infiquetra-native** angle (Jeff's) — **NOT a gstack contribution**: a **full-file grep of gstack `plan-tune` for the agent-usability terms returned ZERO**. gstack `plan-tune` is a developer-psychographic question-coach that supplies **nothing portable** and is **not ported**. This is **NOT a merge** of any kind; gstack is credited with **no insight**.

**Rejected alternatives.**
- *Frame as a balanced CE+gstack merge.* REJECTED — gstack `plan-tune` supplies nothing portable; a grep for the agent-usability terms returned zero. Single-source CE port is the honest provenance.
- *Port ce-plan / a benchmark harness.* REJECTED — `ce-optimize` is the metric-loop engine to port; ce-plan is `/plan`'s engine.
- *Add a gstack profile-coach sibling command.* REJECTED — one engine; the question-coach shape is not what `/optimize` is for.
- *Bake in-engine worktree parallelism (CE's runner).* REJECTED — shed it; parallel fan-out is offered via operator-choice (default serial inline), not hardwired.
- *Add `docs/optimize/` to handoff `SOURCE_DIRS`.* REJECTED — deferred; an optimization run's output is narrative, not yet a `/handoff` source. No `handoff_envelope.py` edit.
- *Make the saga read-only (read the work-thread for evidence).* REJECTED — there is no real downstream consumer for an `/optimize` saga write or read; saga UNTOUCHED is the cleaner off-chain stance (the recurring dead-wiring guard).

**Rationale.** Metric improvement work kept lacking a repeatable engine — "make it faster / cheaper / more reliable" routed nowhere with discipline. `/optimize` is that engine: a bounded-experiment loop with an explicit target, a baseline, and a budget, across 8 metric classes. Off-chain + saga-untouched keeps it from blocking the loop or dead-wiring a saga write; narrative recording avoids a saga field with no consumer. The agent-usability class is the infiquetra-native angle that makes the engine fit a 1-human + agents shop — earned honestly, not borrowed.

**Revisit when.** The 8-class taxonomy proves unwieldy in practice (it is the **maximal v1 set** — trim if classes go unused); OR an optimization run routinely needs to become an SDLC issue (revisit Q4 handoff-deferred); OR the prose-only experiment log demonstrably drifts/corrupts across context compaction (revisit ZERO-new-Python — see QUEUED [#optimize-log-helper](QUEUED.md)); OR a `/pulse` continuous-telemetry command is built (settle the shared boundary from the pulse side).

**Refs.** ARCHIVE [#optimize-engine-rebuild-shipped](ARCHIVE.md#optimize-engine-rebuild-shipped) + the campaign-complete capstone; LEARNINGS [#shipped-on-origin-not-in-stale-local-tree](LEARNINGS.md#shipped-on-origin-not-in-stale-local-tree), [#campaign-brief-merge-is-a-provenance-hypothesis](LEARNINGS.md#campaign-brief-merge-is-a-provenance-hypothesis) (its third firing); the off-chain / saga-untouched twins — [#strategy-engine-rebuild](#strategy-engine-rebuild), [#spec-interrogation-engine-rebuild](#spec-interrogation-engine-rebuild); the gate sibling — [#investigate-systematic-debugging-engine-rebuild](#investigate-systematic-debugging-engine-rebuild) (the `/qa`-boundary pattern); operator-choice — [#operator-choice-framework](#operator-choice-framework). Campaign — [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign) (now COMPLETE). Consumed QUEUED [#optimize-engine-merge](QUEUED.md); added QUEUED [#optimize-log-helper](QUEUED.md).

### Add `/spec` as the lifecycle's spec-interrogation engine — gstack `spec` SINGLE-SOURCE WHAT-interrogation port (the WHAT-rigor sibling of `/plan`'s HOW-rigor), off-chain, saga UNTOUCHED (PR #195)  {#spec-interrogation-engine-rebuild}

**Decision.** Add `/spec` — the **twelfth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`) and the campaign's **spec-interrogation engine**: the pass that owns relentless **WHAT-rigor** — the sibling of `/plan`'s HOW-rigor. A **gstack `spec` SINGLE-SOURCE port** of the WHAT-interrogation half: the principal-engineer-who-refuses-ambiguous-work persona, the HARD GATE (no spec after message 1 — always start the interview), Phase-1 five-Why, Phase-2 scope / MVP / out-of-scope / failure-mode lock, Phase-3 read-code-first grounding, quantify-everything, and a draft-review pass. The four settled Qs + decisions a–d:

- **(Q1) Saga UNTOUCHED.** `/spec` writes no saga, advances no `lifecycle_phase`, and makes **no `saga.py` edit at all** — mirrors `/strategy`. It is **off-chain** (advisory, never blocks `/loop`). Its only durable output is a sharp WHAT artifact under `docs/specs/`.
- **(Q2) Handoff = add `docs/specs/` to the handoff source set.** `handoff_envelope.py` now treats `docs/specs/` as an auto-discoverable handoff SOURCE: `Path("docs/specs")` added to `SOURCE_DIRS` (the **functional** edit — a fresh spec becomes discoverable). `infer_maturity()` maps `docs/specs/` → `requirements-ready` — this **equals the existing default**; it is set for consistency with the other source dirs, **NOT a behavior change and NOT dead-wiring**: a spec is a sharp WHAT, **not** plan-ready. `infer_lifecycle_phase()` leaves `docs/specs/` returning `"unknown"` (off-chain — no lifecycle phase); **no `spec` member is added to `LIFECYCLE_PHASES`**.
- **(Q3) Read-code-first = HARD with a non-code escape.** Phase-3 grounding requires citing `path:line` before asking design questions; a non-code ask (pure product/process) takes the documented escape rather than fabricating a citation.
- **(Q4) Exec gate = OPTIONAL `/doc-review` pass.** A spec may be routed through `/doc-review` for readiness; the `docs/specs/ → requirements` path tie-breaker steers that pass to the **requirements** lens, not the blueprint `/spec-review` route.
- **(c) Operator-choice NEVER OFFERS.** `/spec` does not cite operator-choice: a single durable spec artifact has no parallelism to escalate; size/risk lives in its scope sections, and the downstream executor (`/plan` / `/work`) owns backend selection. (Mirrors `/strategy`'s never-offers row; also consistent with saga-untouched.)
- **(d) Brainstorm-seam resolved in favor of a standalone `/spec`** (option b of `#brainstorm-spec-interrogation-seam`): `/spec` owns WHAT-rigor; `/brainstorm` stays the divergent explorer and now offers **Sharpen with `/spec`** in its Phase-4 menu (divergent `/brainstorm` → convergent `/spec`).

**Honest attribution (load-bearing).** Single source = gstack `spec`, WHAT-interrogation half only. There is **NO CE spec engine** (ce-plan is `/plan`'s planning engine — not ported, not fabricated as a "ce-spec"). There is **NO /ideate+/brainstorm graft** — the assumption-challenge + failure-mode register is **native to gstack's persona**; the failure-mode bank already lives in `/plan/references/interrogation.md` (itself a gstack port). No superpowers borrow. `/spec` and `/plan` split one gstack source along the **WHAT vs HOW** altitude axis; the `/spec` SKILL does **not** duplicate `/plan`'s interrogation register. Sheds the entire gstack preamble (telemetry/gbrain/plan-mode/vendoring/routing-injection/writing-style/Boil-the-Lake/feature prompts), the dedupe machinery, the codex quality gate, the two-layer redaction, `--execute` worktree spawn, gh issue authoring/filing, and the `~/.gstack` store.

**Rejected alternatives.**
- *Map `docs/specs/` to `plan-ready` maturity.* REJECTED — a spec is a sharp WHAT, not an implementation plan; `requirements-ready` is correct (and `/plan` consumes it).
- *Graft ce-plan into `/spec`.* REJECTED — ce-plan is the planning engine `/plan` already ported; there is no CE spec engine to port.
- *Graft the /ideate+/brainstorm assumption-challenge register.* REJECTED — that rigor is native to gstack's persona and already present in `/plan/references/interrogation.md`; grafting it would duplicate, not add.
- *Offer operator-choice.* REJECTED — no parallelism to escalate; the downstream executor owns backend selection.
- *Fold the WHAT-interrogation into `/brainstorm`* (option a of the seam). REJECTED — keep `/brainstorm` divergent; relentless WHAT-rigor lands in exactly one place, the standalone `/spec`.

**Rationale.** Vague asks keep reaching `/handoff` and `/plan` and producing under-specified issues agents bounce back. `/plan` deliberately took only gstack `spec`'s HOW-interrogation and left the WHAT-rigor upstream with a one-way bounce to `/brainstorm`; that WHAT-rigor had no settled owner. `/spec` is that owner — the convergent WHAT-sharpening pass that turns a vague ask into a precise, agent-runnable `docs/specs/` artifact, then routes the work OUT (`/handoff` as a `requirements-ready` source, `/plan` for the HOW, or an optional `/doc-review`). Off-chain + saga-untouched keeps it from blocking the loop or dead-wiring a saga write; sdlc-manager keeps sole ownership of issue bodies.

**Revisit when.** A spec routinely needs a backend choice before handoff (revisit (c) operator-choice never-offers); OR `/brainstorm` and `/spec` start competing for the same interrogation in practice (revisit the (d) standalone-vs-fold split); OR a `docs/specs/` artifact needs to participate in the saga chain (revisit Q1 saga-untouched + the `LIFECYCLE_PHASES` decision).

**Refs.** ARCHIVE [#spec-interrogation-engine-shipped](ARCHIVE.md#spec-interrogation-engine-shipped), [#brainstorm-spec-interrogation-seam-resolved](ARCHIVE.md#brainstorm-spec-interrogation-seam-resolved); LEARNINGS [#campaign-brief-merge-is-a-provenance-hypothesis](LEARNINGS.md#campaign-brief-merge-is-a-provenance-hypothesis); the seam it closed — [#plan-engine-rebuild](#plan-engine-rebuild) (where `/plan` took HOW and left WHAT upstream); the off-chain / saga-untouched twin — [#strategy-engine-rebuild](#strategy-engine-rebuild). Campaign — [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Consumed QUEUED [#spec-interrogation-engine](QUEUED.md) + [#brainstorm-spec-interrogation-seam](QUEUED.md).

### Add `/investigate` as the lifecycle's systematic-debugging engine — CE `ce-debug` spine + gstack `investigate` grafts + superpowers borrow, diagnosis-primary, saga READ-ONLY, full `/qa` cross-engine rewire (PR #193)  {#investigate-systematic-debugging-engine-rebuild}

**Decision.** Add `/investigate` — the **eleventh command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`) and the campaign's **net-new systematic-debugging engine**: the diagnostic brain that answers "what is actually broken, and why?" — the causal-chain work `/qa` (the gate) deliberately does not own. A **CE `ce-debug` SPINE** + **gstack `investigate` grafts** + a **superpowers systematic-debugging borrow**:

- **(Q1) Saga READ-ONLY.** `/investigate` reads saga context for evidence (the work-thread's prior ticks, `pr_refs`, plan path) but **writes no saga** and advances no `lifecycle_phase`. It is **off-chain** — advisory, never blocks `/loop`. Like `/retro` (saga read-only) and `/founder-review` / `/strategy` (off-chain, no saga), a diagnostic pass is not a saga-track artifact. Confirmed there is no real downstream CONSUMER for an `/investigate` saga write before adding one (the recurring dead-wiring guard — see `/work`, `/founder-review`, and `/retro`'s dropped `→retro` advance).
- **(Q2) Verification OWN-MINIMAL — NOT a call into `/qa`.** This **overrode the pre-decision** in the QUEUED brief, which read "`/investigate`'s verification phase CALLS `/qa` rather than reimplementing test discipline." `/investigate` carries its **own minimal verification** (confirm the causal chain reproduces, the falsifiable prediction holds, the fix/diagnosis is sound) and routes the heavier acceptance gate OUT. There is **no `/investigate` → `/qa` verify loop`** — `/qa` routes deep failures INTO `/investigate` (the one-directional wiring), and a back-call would create a cycle (`/qa` → `/investigate` → `/qa` → …).
- **(Q3) `/qa` FULL all-refs rewire.** Building `/investigate` closes `/qa`'s deferred "when `/investigate` is built" route at **every site**, not one: the rewire touched **5 `/qa` SKILL mentions** (principle-1 fixer list, the post-merge FAIL branch, the deferral block, the hard-boundary line) + **2 other-file notes** (`operator-choice.md`, office-hours `frame-diagnostic.md`). `/qa`'s post-merge FAIL branch is now a **two-target branch**: deep/uncertain root cause → `/investigate`; clear/trackable defect → `/handoff`. Pre-merge still → `/work`. Routing still **reads** `loop/references/dispatch-table.md`.
- **(Q4) Learning-capture BOTH-SPLIT.** Non-obvious root causes → journal LEARNINGS; a confirmed trackable bug → an sdlc-manager defect issue (via `/handoff` — describe the defect with the DEBUG REPORT **linked as evidence**, never passed to `handoff_envelope`'s path-classifier) — both, with a split by what the finding is. `/investigate` does not create issues itself (sdlc-manager owns that).

**Key design points.**
- **CE `ce-debug` is the SPINE** (252L, all engine, the cleaner port base): causal-chain gate, **falsifiable predictions for uncertain links** (predict something in a *different* code path that must also be true; a wrong prediction but a "working" fix = symptom not cause — the same mechanic `/qa` grafts), assumption audit, Phase-0 triage with issue-tracker fetch + trivial fast-path, smart-escalation, parallel read-only sub-agent dispatch.
- **gstack `investigate` GRAFTS:** the pattern-signature table (race / null / state / integration / config / cache), the two distinct numeric stop gates (hypothesis-exhaustion + 3-failed-fix), the DEBUG REPORT Status enum. Dropped: gstack scope-lock/freeze (CE's minimal-diff + workspace-check covers it), the GSTACK REVIEW REPORT gate, the ~755L preamble, gstack-learnings bins, and all gstack runtime bins.
- **Diagnosis-primary, never a fixer.** Output is a DEBUG REPORT (file:line, causal chain, regression-test path, Status enum) — agent-consumable **evidence**; the fix reaches `/work` via a `/handoff` issue (not by `/work` reading `docs/investigations/`). Routes the work OUT by what it finds: a **real fix** → `/work` (via a `/handoff` issue); an **applied inline fix** → `/work` or `/code-review` to ship; a **trackable defect** → `/handoff`; a **design-level root cause** → `/brainstorm`. It does not commit, push, open/merge a PR, or deploy.
- **ZERO new Python, ZERO `saga.py` / `handoff_envelope.py` / `saga-spec.md` edits.** `/investigate` is a markdown engine (SKILL + references + command) reusing existing helpers. Operator-choice offered (saga read-only) for large/parallel fixes + parallel hypothesis-probes; default single-hypothesis/single-file inline.

**Rejected alternatives.**
- *Fold debugging into `/qa`.* REJECTED — `/qa` is gate-only by its own settled boundary (0.13.0); a diagnostic fix-loop brain is a distinct job. ADOPT standalone was the brief's verdict.
- *`/investigate`'s verification CALLS `/qa` (the brief's pre-decision).* REJECTED/OVERRIDDEN — own-minimal verification instead; a back-call into `/qa` creates a routing cycle (`/qa` already routes INTO `/investigate`).
- *Write a saga / advance `lifecycle_phase`.* REJECTED — off-chain, saga read-only; no real downstream consumer, the recurring dead-wiring trap.
- *Close `/qa`'s deferral at only the one obvious site.* REJECTED — a deferred cross-engine route leaves notes at multiple sites; closing one and missing four leaves stale "future" framing live (LEARNINGS [#deferred-cross-engine-wiring-must-close-on-build](LEARNINGS.md#deferred-cross-engine-wiring-must-close-on-build)).
- *Keep gstack scope-lock/freeze + the runtime bins.* REJECTED — CE's minimal-diff/workspace-check covers scope; the bins are dead weight (campaign shed pattern).

**Rationale.** Debugging today is unstructured ad-hoc whack-a-mole; `/qa` surfaces failures (with a falsifiable prediction for uncertain causes) but is gate-only and cannot do root-cause work. `/investigate` owns the causal-chain brain `/qa` routes to, with CE's prediction discipline as the spine and gstack's pattern table / stop rule / report enum grafted on. Diagnosis-primary keeps it from colliding with `/work` (which fixes) — it produces the agent-consumable DEBUG REPORT and routes the fix out. Saga read-only + off-chain keeps it from blocking the loop and avoids a dead-wired saga write. Own-minimal verification (not a `/qa` back-call) avoids a routing cycle.

**Revisit when.** A real prod incident-response surface appears (revisit whether `/investigate` should read live telemetry/logs beyond the repo); the pattern-signature table needs tuning to infiquetra's serverless/Lambda/DynamoDB stack (queued tuning); or own-minimal verification proves too thin and a structured `/qa` handoff (artifact, not a call) becomes worth the seam.

**Refs.** Plugin `0.16.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). The `/qa` gate-only boundary this engine complements (and the falsifiable-prediction graft `/qa` carried for it) — DECISIONS [#qa-engine-rebuild](#qa-engine-rebuild). Off-chain / saga-read-only siblings — DECISIONS [#retro-engine-rebuild](#retro-engine-rebuild), [#founder-review-engine-rebuild](#founder-review-engine-rebuild), [#strategy-engine-rebuild](#strategy-engine-rebuild). The deferred-wiring lesson + the routed-output dead-wiring axis — LEARNINGS [#deferred-cross-engine-wiring-must-close-on-build](LEARNINGS.md#deferred-cross-engine-wiring-must-close-on-build). Consumed from QUEUED [#investigate-systematic-debugging-engine](QUEUED.md#investigate-systematic-debugging-engine). Ship record: ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped). Shipped via PR #193, squash 5079d8f.

---

## 2026-06-03

### Rebuild `/retro` as the meta-improvement engine — a real 3-source merge (gstack `retro`+`learn` + CE `ce-compound`) behind a tiered self-edit gate, saga READ-ONLY (PR #191, squash f6faae2)  {#retro-engine-rebuild}

**Decision.** Rebuild `/retro` — the **tenth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`) — from a 19-line stub into the lifecycle's **meta-improvement engine**: the engine that captures lifecycle learnings, curates durable journal knowledge, and proposes improvements to the workflow itself (up to and including the lifecycle plugin's own SKILLs). A **real 3-source merge**: gstack `retro` (forensics + the stale-base/wrong-"today" BLOCK guard) + gstack `learn` (the knowledge-curation loop) + CE `ce-compound` (the "leave the system smarter" framing). The four interview answers settled with Jeff:

- **(Q1) FULL engine in v1 — all 6 net-new passes + lean metrics, nothing deferred.** All six net-new passes neither source has — (1) structured interview of Jeff, (2) session-transcript review as evidence, (3) "do we need a NEW skill/plugin?", (4) refine `infiquetra-lifecycle` ITSELF, (5) refine claude/agent/antigravity directive files, (6) memory updates/pruning across the journal + auto-memory — ship in v1, with a **lean** metrics snapshot (not gstack's full quantitative forensics). The QUEUED brief's "MVP = interview + curation + pruning; defer metrics + self-refinement to v2" split was rejected: Jeff wants the whole meta-improvement engine now.
- **(Q2) Single `/retro` command + an optional pass argument.** One command runs all passes; a focused sub-pass can be invoked directly via an optional arg (e.g. a curate-only or prune-only run). Not separate `/retro interview` / `/retro curate` / `/retro prune` commands — one engine, selectable passes.
- **(Q3) Tiered self-edit gate.** Pure-append, additive-only journal writes **auto-apply**; **everything else** — every delete / modify / move of existing durable state — is **propose-diff-and-wait**. This is the safety contract for a self-modifying engine (LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate)).
- **(Q4) Full self-modification blast radius — including the lifecycle SKILLs.** The gate's reach is the **complete** self-modification surface: the journal, `.claude` memory, the claude/agent/antigravity directive files, AND `infiquetra-lifecycle`'s own SKILLs. The engine can propose edits to itself. Reach is **full**; safety comes from the hard gate (Q3), not from narrowing what the engine may touch.

**Key design points.**
- **Saga READ-ONLY — the planned `->retro` advance is dead wiring, dropped, so NO `saga-spec.md §11` row.** `/retro` reads saga context for evidence but writes **no** saga and advances **no** `lifecycle_phase`. The pre-rebuild plan's `work`/`qa`→`retro` saga advance was **dead wiring** — `/retro` is a terminal, off-chain reflection pass whose durable sink is the journal, not a saga track; a retro tick would just record "a retro happened" with no consumer. So `/retro` is saga read-only: `saga.py` is untouched AND `saga-spec.md` gets **no §11 change** (the campaign's first command consumer that deliberately writes nothing to the saga).
- **In-repo vs global/cross-project directive disambiguation, with a cross-project warning.** The directive-refinement pass (Q4 reach) distinguishes a **repo-local** directive (this repo's `CLAUDE.md`, this repo's journal) from a **global / cross-project** one (`~/.claude/CLAUDE.md`, auto-memory, the antigravity directive class). A repo-local edit follows the normal tiered gate; a global / cross-project edit carries an **extra cross-project-impact warning** before the propose-diff, because the blast radius spans every repo (LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate)).
- **3-source merge frame: gstack `retro` + `learn` + CE `ce-compound`.** gstack `retro` contributes the lean metrics snapshot + the stale-base/wrong-"today" BLOCK guard; gstack `learn` contributes the typed/confidence/source curation loop (staleness + contradiction + dedup) as the memory-pruning mechanism; CE `ce-compound` contributes only the compounding frame (leave the system smarter, output agent-consumable findings → journal entries + concrete edit proposals, not a 4500-word essay).
- **ZERO new Python — reuse only.** `/retro` is a markdown engine (SKILL + references + command) that reuses existing helpers (read-only `gh` evidence, the journal sink, existing saga readers); it adds **no** `.py`. `saga.py` is untouched.
- **Stale-base guard scoped to the windowed mode.** gstack's stale-base/wrong-"today" BLOCK guard (which maps onto Jeff's validation-discipline rule) is kept but **scoped to the windowed/metrics mode** — the mode that reads a time-window of git history — not applied to every pass (a pure interview pass has no base to be stale against).

**Folded-in deferred sub-items (from the consumed QUEUED brief — nothing silently dropped).**
- **Antigravity directive class — a global/cross-project surface.** The directive-refinement pass's reach explicitly includes the **antigravity directive files** as one more **global / cross-project** directive surface (alongside `~/.claude/CLAUDE.md` and auto-memory) — so it gets the same cross-project-impact warning. Folded here from the QUEUED brief's directive-files pass so it is not lost when the brief entry is removed.
- **Output-routing of surfaced follow-ups — OPEN.** When a pass decides "new skill/plugin needed" or "refine command X," whether the output is a QUEUED entry, a `/handoff`, or a ready-to-run ultracode/team-execution plan is **left open** for the build to settle per-case (a retro proposing a large multi-file self-edit offers to hand EXECUTION to team-execution or an ultracode workflow; it proposes + names the tool, never auto-launches a destructive self-edit). Recorded here so the open routing question survives the QUEUED removal.

**Rejected alternatives.**
- *The dead-wiring saga advance (`work`/`qa`→`retro` `lifecycle_phase` transition).* REJECTED — `/retro` is a terminal off-chain reflection pass; a saga advance to a `retro` phase has no downstream consumer and would record "a retro happened" with nothing reading it. `/retro` is saga read-only; no `saga.py` edit, no `saga-spec.md §11` row.
- *MVP-then-v2 split (defer metrics + self-refinement).* REJECTED — Jeff wants the full meta-improvement engine in v1: all 6 net-new passes + lean metrics, nothing deferred (Q1).
- *Narrow the self-modification reach (exclude the lifecycle SKILLs / directive files) instead of gating it.* REJECTED — full reach + a hard tiered gate beats narrow reach; the engine must be able to improve itself, and safety comes from propose-diff-and-wait + the cross-project warning, not from forbidding the edit (Q3/Q4, LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate)).
- *Flat-absence contract floors (treat an absent pass / absent finding as a hard failure).* REJECTED — a pass with no evidence (e.g. no transcripts to review, no directive drift) is a graceful no-op, not a contract violation; floors assert mechanism presence, not that every optional pass fired.
- *Auto-apply directive / memory / lifecycle-SKILL edits like journal appends.* REJECTED — only pure-additive journal appends auto-apply; every delete/modify/move of existing durable state is propose-diff-and-wait, and a global/cross-project edit needs the extra warning.
- *Sub-mode commands (`/retro interview`, `/retro curate`, …).* REJECTED — one `/retro` command with an optional pass arg (Q2); separate commands fragment the engine.

**Rationale.** `/retro` is the meta-improvement engine — the pass that makes the whole lifecycle (and Claude itself) smarter after each loop — and it had only a 19-line stub. The three sources each contribute a distinct mechanic (gstack `retro` forensics + guard, gstack `learn` curation, CE `ce-compound` framing), merged into one engine we own. The danger is that a meta-engine that can edit its own plugin, memory, and directive files is a foot-gun; the answer is full reach behind a **tiered self-edit gate** (auto-apply pure-additive journal appends; propose-diff-and-wait everything else; extra cross-project warning for global edits). Saga read-only because retro is a terminal off-chain reflection pass, not a saga-track step — so zero `saga.py` edits and no §11 change. No new Python.

**Revisit when.** A retro's auto-applied journal append turns out to need human review too (tighten the auto-apply tier); the windowed-metrics mode's stale-base guard fires falsely on a legitimately old base; the output-routing open question (QUEUED vs `/handoff` vs ready-to-run plan) needs a settled default rather than per-case judgment; or a real `/investigate` / `/pulse` lands and overlaps the metrics/curation passes.

**Refs.** Plugin `0.15.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). The self-modifying-engine safety lesson (tiered gate + cross-project warning) — LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate). Saga read-only / off-chain siblings (write no saga) — DECISIONS [#founder-review-engine-rebuild](#founder-review-engine-rebuild), [#strategy-engine-rebuild](#strategy-engine-rebuild). Consumed the QUEUED brief `#retro-meta-improvement-engine` (removed; its deferred sub-items folded in above). Ship record: ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped). Commit: f6faae2 (PR #191, squash f6faae2).

### Rebuild `/strategy` as the interview-driven STRATEGY.md engine — a faithful single-source CE `ce-strategy` PORT (PR #189, squash a9d4c90)  {#strategy-engine-rebuild}

**Decision.** Rebuild `/strategy` — the **ninth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`) — from a 21-line stub into the lifecycle's **interview-driven STRATEGY.md engine**. A **faithful single-source PORT of CE `ce-strategy`**, NOT a merge: it is the campaign's second single-source port (after `/founder-review`'s gstack port), but here the single source is **CE**. The four interview answers settled with Jeff:

- **(Q1) CE-only source — gstack has no strategy engine.** Jeff's pre-audit intent named "gstack cso (Chief Strategy Officer)", but that file is the Chief **SECURITY** Officer — a 14-phase security audit, the **wrong officer**. The `cso` ≈ "Chief Strategy Officer" name-match was a mixup, not a verified mapping (LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic)). gstack has **nothing** strategy-specific to steal; CE `ce-strategy` is the sole engine source. This makes `/strategy` a single-source PORT, not a two-engine merge.
- **(Q2) Keep all 8 sections + the Rumelt kernel.** Port the whole engine: the Rumelt-grounded kernel (diagnosis / guiding-policy / coherent-action), the Phase-1 8-section interview, and the locked template — no trimming. CE's structure is the proven engine; reducing it would re-stub the command.
- **(Q3) Agent-as-customer is persona-only — tracks stay pure investment areas.** Personas may name **AI-agent actors when the product is agent-consumed**; **tracks remain pure investment areas / domains of work, NOT actors.** The QUEUED brief's pre-written adaptation ("personas/tracks must name AI-agent actors") was **half a category error** — tracks are domains of work, not actors — caught by reading the real CE `interview.md` section semantics + a Jeff challenge (LEARNINGS [#spec-adaptation-is-a-hypothesis](LEARNINGS.md#spec-adaptation-is-a-hypothesis)). Only the persona-as-agent-customer half is sound.
- **(Q4) Keep the mandatory 2-round pushback per section.** CE's relentless 2-round-pushback-per-section discipline is kept verbatim, not softened — it is the mechanism that turns shapeless prose into a real strategy.

**Key design points.**
- **Artifact home = the repository-root `STRATEGY.md`.** The durable direction lives at the repo root (a single locked-template doc: 3-5 metrics, 2-4 tracks), rerunnable update-in-place via Phase-0 file-state routing (new doc vs targeted-section update vs pick-a-section).
- **ZERO `saga.py` edits — off-chain / pre-saga.** `/strategy` runs **upstream of the work loop** and writes **no saga**, the same off-chain position as `/founder-review` (DECISIONS [#founder-review-engine-rebuild](#founder-review-engine-rebuild)): the saga's `review_paths`/`lifecycle_phase` are the wrong home for a durable direction doc, and the guard would skip ~always. Cross-session persistence = the committed `STRATEGY.md` + the journal ADR.
- **No new Python.** `/strategy` is a markdown engine (SKILL + references + command); `saga.py` is untouched. No team-execution / workflows offer (a single durable doc, no parallelism).
- **Strategy records, founder-review challenges.** The two are complementary on a STRATEGY.md: `/strategy` is the *direction-recording* engine; `/founder-review` is the *ambition lens* that challenges it (and `/doc-review` the readiness lens). Not a collision.

**Rejected alternatives.**
- *Merge a gstack strategy engine in (the pre-audit "gstack cso" mapping).* REJECTED — `cso/` is the Chief SECURITY Officer; there is no gstack strategy engine to merge. A plausible name match is not a verified mapping.
- *Trim CE's 8 sections / drop the Rumelt kernel.* REJECTED — reducing the structure re-stubs the command; the whole engine is the value.
- *Name AI-agent actors in tracks too (the QUEUED brief's blanket adaptation).* REJECTED — tracks are investment areas / domains of work, not actors; only persona-as-agent-customer is a sound adaptation, and only for agent-consumed products. The blanket note was half a category error.
- *Soften the mandatory 2-round pushback to a lighter touch.* REJECTED — the relentless pushback is the mechanism that produces a real strategy; softening it reverts toward facilitation.
- *Write a saga / advance `lifecycle_phase`.* REJECTED — `/strategy` is off-chain/pre-saga; a durable direction doc is not a saga-track artifact. Zero `saga.py` edits.

**Rationale.** `/strategy` owns the durable repository direction — "where are we pointed, and why?" — and it had only a stub. CE `ce-strategy` is the sole real engine source (gstack's `cso` is the wrong officer), so this is a faithful single-source port: keep the Rumelt kernel, the 8-section interview, the 2-round pushback, and the locked template; record direction off-chain in `STRATEGY.md` (no saga, like `/founder-review`); name AI-agent actors only in personas for agent-consumed products, never in tracks (which are domains of work). No new Python — `/strategy` is a markdown engine.

**Revisit when.** A repo's `STRATEGY.md` needs metrics wired to live telemetry (revisit the qualitative-only stance — overlaps the queued `/pulse` / `/optimize` metric loops); a real gstack (or other) strategy engine appears worth merging; or strategy starts needing to write durable cross-session state beyond the committed doc (revisit the no-saga position).

**Refs.** Plugin `0.14.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Off-chain/pre-saga sibling (no saga write, records-vs-challenges) — [#founder-review-engine-rebuild](#founder-review-engine-rebuild). Source-mapping correction (gstack `cso` = SECURITY, not Strategy; name-match ≠ verified mapping) — LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic). The spec-adaptation-is-a-hypothesis lesson (the brief's blanket tracks-as-actors note was half a category error) — LEARNINGS [#spec-adaptation-is-a-hypothesis](LEARNINGS.md#spec-adaptation-is-a-hypothesis), which pairs with [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways). Ship record: ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped). Shipped via PR #189 (squash a9d4c90).

### Rebuild `/qa` as the gate-only acceptance-evidence engine — a real gstack `/qa`+`/qa-only` merge + ce-debug graft, severity-banded verdict + ported deterministic health score, saga qa-track consumer (PR #187, squash fb2c1b3)  {#qa-engine-rebuild}

**Decision.** Rebuild `/qa` — the **eighth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`) — from a 19-line stub into the lifecycle's **gate-only acceptance-evidence engine**: the gate downstream of `/work` + `/code-review` that answers "does the shipped thing actually work?". A **real two-engine merge** against the **cloned** gstack source (`/qa` 354L `.tmpl` + `/qa-only` 114L + `/investigate` 259L) plus a CE `ce-debug` graft — **not** a phantom (gstack was first absent from the local install cache, then cloned from GitHub; see LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways)). `/qa` adopts gstack's own report-only **`/qa-only` model**: it classifies the change into risk classes, runs acceptance checks (browser folded under behavior as one MCP class), gathers evidence, assigns severity, derives a ship verdict, writes a durable artifact, advances the saga qa-track on pass, and routes — and **never fixes, commits, pushes, opens/merges a PR, deploys, files SDLC issues, or sets readiness labels**. The four interview answers settled with Jeff:

- **(Q1) Gate + route, NEVER fix.** The `/qa-only` model. Campaign-consistent (every shipped review/verify command is gate-only), faithful to gstack's own report/fix split, and zero git-mutation surface. `/work` (round-N) and the future `/investigate` own all fixing. gstack's fix half — Phase 8, the WTF-likelihood guard, atomic fix commits, regression-test generation-as-action — is **dropped**; regression tests are **recommended** in the report, not generated.
- **(Q2) Severity-banded verdict + a PORTED deterministic health score, reported ALONGSIDE each other [RE-OPENED, final].** This question moved twice. Jeff **initially said keep gstack's score**; an interim review then wrongly claimed gstack had "no formula" (LLM-eyeballed) and on that basis the score was briefly slated to be **dropped → zero new Python**. That "no formula" claim was a one-hop-short source read and is corrected — the formula **is real**: `scripts/resolvers/utility.ts:286-321` is a deterministic weighted **Health Score Rubric** (per-finding deductions Critical -25 / High -15 / Medium -8 / Low -3, explicit category weights, `score = Σ (category_score × weight)`), exported as `generateQAMethodology` and injected as the `{{QA_METHODOLOGY}}` macro `qa/SKILL.md.tmpl:122` (the interim "no formula" reading stopped at `gen-skill-docs.ts`; corrected in LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways)). Once the real formula was located, **Jeff chose to PORT it, not drop it** — a deterministic scorer (`scripts/qa_health_score.py`) that ports gstack's deduction values **verbatim** (critical -25 / high -15 / medium -8 / low -3), swaps gstack's web-only category weights (Console/Links/Visual/Functional/UX/Performance/Content/Accessibility — which don't map onto serverless / SDK / Ansible / plugin work) for **documented infiquetra 9-way ship-risk-class weights** (behavior 20, security 20, data 15, api 15, deployment 10, infra 10, config 5, docs 3, trivial 2 — ranked by ship blast radius), **re-normalizes the weights over only the in-scope classes** (a class absent from findings is N/A and excluded; present-but-clean scores 100), and emits a **delta against a baseline-from-prior-report** score. The 0-100 number is reported **ALONGSIDE** the severity-banded verdict — pass/fail per risk class + critical/high/medium/low findings + a ship verdict (`ship` / `ship-with-deferred` / `no-ship`) from the tier threshold. **Honest caveat (in the scorer's own docstring):** the scorer's inputs are LLM-assigned severities, so the score is **one signal, not the gate decision** — the severity-banded verdict remains the gate. Severity uses gstack's vocab with a documented ↔ P0-P3 cross-walk to `/code-review`. **This adds one new script: `qa_health_score.py` (the scorer) + its oracle test.**
- **(Q3) Saga qa-track consumer (advance), zero `saga.py` edits.** `restore` the work-thread → run the gates → write `qa_paths` + on PASS advance `lifecycle_phase` from `work` to `qa` (the advance `/work` 0.10.0 explicitly deferred to this rebuild); on FAIL keep `lifecycle_phase=work` and record evidence. Every flag already exists — `qa` @ `LIFECYCLE_PHASES` (`saga.py:56`), `--lifecycle-phase qa` (`:1057`), `--qa-paths` (`:1075`), `qa_paths` field (`:155`) — and there is no phase-transition validation in `_merge`, so the advance is unblocked with **zero `saga.py` edits**. No fix sub-saga. Adds the missing `/qa` (and the also-missing `/code-review`) row to `saga-spec.md §11`.
- **(Q4) Ship a durable risk-class reference.** A 9-way risk router (PRIMARY) + per-class acceptance/evidence checklists; gstack's 7 web categories + per-page browser checklist fold under behavior/browser as **one MCP-driven class** (chrome-devtools/playwright, graceful no-op off-UI); the file-pattern → risk-class map (diff-aware); severity defs + the P0-P3 cross-walk; the ship-verdict derivation + tier → blocking-threshold table.

**Key design points.**
- **ce-debug graft = the falsifiable-prediction mechanic specifically [DA-M3].** The single distinct ce-debug import (the rest of "evidence discipline" already lives in `/code-review` principle 2): for each failure whose **cause is uncertain**, state a falsifiable prediction — "if this is the real cause, X in a different path must also fail." A wrong prediction means symptom, not cause; a right one gives the routed fixer a head start. Obvious-cause findings skip it.
- **Merge-state failure routing [DA-H3, the big correctness catch].** PASS → `/handoff` or `/retro`. FAIL routes by **merge state**: pre-merge (PR open) → `/work` (re-enter the round-N loop, wired via `/work` Phase 0.4 `pr_refs`); post-merge (merged to `main`) → `/handoff` to open a **new defect thread** (NOT `/work` round-N — a merged saga's PR would cycle the merged PR straight back to `/qa`). `/investigate` is **future-prose only** — it is not on the dispatch-table's routable list, so `/qa` never emits it as a runnable route. Routing **reads** `loop/references/dispatch-table.md` (never restated).
- **Diff-aware mode reuses `/code-review`'s stale-base mechanic [DA-H4].** Pre-merge: `git fetch origin <base> --quiet; DIFF_BASE=$(git merge-base origin/<base> HEAD); git diff --name-only "$DIFF_BASE"` (two-dot merge-base, not three-dot, which is empty post-merge on `main`). Post-merge: read the merge commit's changeset via `gh pr view <N> --json files`.
- **Browser is one MCP-driven risk class, not seven web categories.** gstack's `$B`/`browse` daemon, bun build, and CDP coupling are dropped; the browser check uses the installed MCP and is a graceful no-op for serverless / SDK / Ansible / plugin repos.
- **Pin `--phase` on the PASS tick [DA-M4].** The qa-advance tick reuses the restored integer `phase` so `--phase-status complete` does not advertise a phantom counter advance.
- **`docs/qa/` collision with `/optimize` resolved in-PR [DA-M2].** The shipped `/optimize` stub also wrote `docs/qa/`; resolved here with a one-line change of `/optimize` to `docs/optimize/` (not deferred). `handoff_envelope.py` does not classify `docs/qa/`, so no handoff/sdlc classifier collision.
- **One new script (the ported scorer), no `agents/` dir.** The Q2 final lands one new Python file — `scripts/qa_health_score.py` (the deterministic health scorer) + its oracle test; otherwise `/qa` is a markdown engine (SKILL + 2 refs + command + the scorer + tests). Parallel/large risk-class verification offers an operator-choice backend and uses **generic `Explore`/`Task` agents** (the `/code-review:164` convention — no plugin `agents/` dir).

**Rejected alternatives.**
- *Gate + opt-in fix, or fix-by-default.* REJECTED — `/qa` owning any fix path adds a git-mutation surface and competes with `/work`/`/investigate`; gstack itself ships the report-only `/qa-only` as a separate command. Gate-only is campaign-consistent.
- *Drop gstack's 0-100 health score entirely.* REJECTED (the interim "no formula → drop" position was itself superseded). The score's deduction formula **is real** (`scripts/resolvers/utility.ts:286-321`, the `{{QA_METHODOLOGY}}` macro); the honest move once it was located was to PORT it — a deterministic, reproducible scorer — and report it **alongside** the banded verdict, with the explicit caveat that its inputs are LLM-assigned severities (so it is one signal, not the gate). Dropping a real, deterministic formula would have thrown away reproducible signal. See LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways).
- *Invent the scorer's weights from scratch.* REJECTED — fabricating deduction values would be net-new false precision (and a tautological test). Instead we **port gstack's deduction values verbatim** (critical -25 / high -15 / medium -8 / low -3) and only **document the infiquetra class weights** (the one deliberate adaptation, because gstack's weights are web-only categories that don't map onto infiquetra work), re-normalized over the in-scope classes — porting a proven formula, not inventing one.
- *Fix sub-saga for failures.* REJECTED — `/qa` is gate-only; a fix sub-saga is a fix loop by another name. Failures route to the merge-state-correct fixer.
- *Read-only saga consumer (no phase advance).* REJECTED — `/work` deferred the `work`→`qa` advance specifically to this rebuild; declining it would leave the deferred advance permanently unlanded.
- *Edit `saga.py` to add a qa-specific path.* REJECTED — every flag already exists and the advance is unblocked; `/qa` is a pure consumer (zero `saga.py` edits).
- *Custom `/qa` subagent / an `agents/` dir.* REJECTED — contradicts the shipped `/code-review:164` no-`agents/`-dir convention; parallel verification uses generic agents.
- *Browser-coupled (port gstack's `browse`/CDP daemon).* REJECTED — most infiquetra repos are non-UI; browser is one risk-driven MCP class behind the router, a graceful no-op off-UI.

**Rationale.** `/qa` is the acceptance-evidence GATE — "is the shipped thing actually shippable?". Keeping it gate-only matches gstack's own `/qa-only` split and every shipped lifecycle review/verify command, and keeps all fixing in `/work` + the future `/investigate`. On the score: its formula (`scripts/resolvers/utility.ts:286-321`) is real and deterministic, so the honest move once it was located was to **PORT it** (deduction values verbatim, documented infiquetra class weights, re-normalized) and report the 0-100 number **alongside** the severity-banded verdict — with the explicit caveat that its inputs are LLM-assigned severities, so the score is one signal and the banded verdict stays the gate. That keeps reproducible signal instead of discarding a proven formula; it lands one new script (`qa_health_score.py` + its oracle test). The saga qa-track consumer lands the advance `/work` deferred without touching `saga.py`, and the merge-state failure routing is grounded in the actual `/work` Phase 0.4 re-entry + the dispatch-table's routable list rather than an aspirational `/investigate` route.

**Revisit when.** `/investigate` ships (then deep post-merge failures route there for root-cause work instead of `/handoff`); a real UI product makes the browser class high-frequency enough to warrant more than one MCP-driven check; or a health signal becomes available whose **inputs** are deterministically measured (not LLM-assigned counts) and genuinely additive over the banded verdict (revisit the dropped score — gstack's formula is real, but only re-adopt a number when its inputs are measured, not eyeballed).

**Refs.** Plugin `0.13.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Consumes the saga foundation as the qa-track consumer (zero edits) — [#saga-schema-foundation](#saga-schema-foundation), spec `plugins/saga/references/saga-spec.md` §11. Lands the advance deferred by — [#work-engine-rebuild](#work-engine-rebuild) (`work/SKILL.md:354`). Gate-only + no-`agents/`-dir conventions from — [#code-review-engine-rebuild](#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`; the `git merge-base` diff mechanic). No-false-precision posture from — [#founder-review-engine-rebuild](#founder-review-engine-rebuild). The future debugging engine `/qa` routes to — QUEUED [#investigate-systematic-debugging-engine](QUEUED.md#investigate-systematic-debugging-engine). Source-fidelity lesson (clone the repo; read the engine, not the scaffold) — LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways), the counterpart to LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Ship record: ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped). Shipped via PR #187 (squash fb2c1b3).

### Rebuild `/resume` as the lifecycle's heavy forensic reconstruction engine — a real CE `ce-sessions` PORT (PR #185, squash 73975ec)  {#resume-engine-rebuild}

**Decision.** Rebuild `/resume` — the **seventh command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`) — from a 23-line "read committed docs first" doc into the lifecycle's **heavy forensic reconstruction engine**, the **unblocked heavy partner** the `/loop` rebuild (0.11.0) explicitly deferred to it. The lightweight/heavy split is now both halves shipped: `/loop` owns the **lightweight** scan → restore → route + inline cold-reconstruction; `/resume` owns the **heavy** forensic dig. Unlike `/loop` (the campaign's native rebuild against a phantom brief source), `/resume` is a **real CE `ce-sessions` PORT** — its named upstream was verified to exist and be portable, the **opposite** of the `/loop` phantom. Two tiers: **Tier 1** (saga-anchored deep reconstruction — the common path) = a NEW saga **all-ticks reader** walking the full append-only tick-chain trajectory + PR archaeology + conflict reconciliation; **Tier 2** (FALLBACK ONLY, no saga AND no resolvable issue) = a slim Claude-only port of CE `ce-sessions` (discover → file-mediated skeleton extract to scratch → generic-agent synthesis). The four interview answers settled with Jeff:

- **(Q1) Port CE `ce-sessions` now, staged behind Tier 1.** Yes, port the CE forensic session-log reconstruction — but as **Tier 2 fallback only**, behind the saga-anchored Tier 1. The brief source was verified TRUE + portable (the positive counterpart to the `/loop` phantom — see LEARNINGS [#resume-port-source-verified-true](LEARNINGS.md#resume-port-source-verified-true)).
- **(Q2) Drop the `[gstack-context]` WIP-commit trailer.** `/resume` does NOT adopt gstack's `[gstack-context]` save-trailer. The saga's append-only tick log already IS the durable trajectory; a parallel commit trailer would duplicate the saga it would have to reconcile against.
- **(Q3) Route to any phase via the REFERENCED shared dispatch-table — no ping-pong.** `/resume` routes to any lifecycle phase via the **shared** `loop/references/dispatch-table.md` (referenced, never duplicated — single source of truth). It does NOT route back through `/loop` (no `/loop` ↔ `/resume` ping-pong) and does not maintain its own copy of the table.
- **(Q4) Write one git-ignored re-entry tick reusing the restored `saga_id`.** On a successful Tier-1 reconstruction `/resume` writes **exactly one** git-ignored re-entry saga tick, **reusing the restored `saga_id`** — never minting a new saga. `/resume` is a reader/restorer, not a saga primary writer.

**Key design points.**
- **A real port — the opposite of `/loop`.** The `/loop` rebuild's lesson was "verify a brief's source claims before building" (LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact)). Applying that same verification to `/resume` confirmed CE `ce-sessions` exists and is portable — verification cuts both ways. `/resume` is a genuine CE port (file-mediated extraction discipline + generic-agent synthesis), not a native author-from-scratch.
- **Two-tier, Tier-2 context-safe by construction.** Tier 1 is the common path (a saga exists or an issue resolves to one); Tier 2 fires ONLY when there is **no saga AND no resolvable issue** — same-machine work that never wrote a saga (NOT a fresh clone — corrected from the DA's H3). Tier 2 never reads multi-MB session JSONL into context: it discovers candidates, extracts a file-mediated skeleton to scratch, and hands the skeleton to a generic agent for synthesis. Context-safety is structural, not a budget guess.
- **Generic-agent synthesis — no `agents/` dir [C1].** Tier-2 synthesis uses **generic** agents, honoring the convention the shipped `/code-review` encodes (no plugin `agents/` dir → generic agents, `skills/code-review/SKILL.md:164`). Adding an `agents/` dir would have been a structural first against a settled sibling convention.
- **The all-ticks `read_ticks` lives in `saga.py`, NOT `load_saga_context.py` [brief deviation].** The brief implied extending `load_saga_context.py`. But that wrapper is **issue-locked** — its `--issue` argument is required — so it is structurally the wrong layer for a cold, no-issue trajectory read. The all-ticks capability belongs in the saga engine itself (`saga.py read_ticks`); `load_saga_context.py` stays the shared issue-keyed substrate `/loop` and `/resume` both use. See LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer).
- **Tier 1 is not a `/loop` echo [DA-H1].** `/loop`'s lightweight restore reads only the **latest** tick; `/resume`'s Tier-1 all-ticks reader walks the **full** append-only log (the trajectory `/loop` cannot see). `load_saga_context.py` is the **shared substrate** both consume — `/resume`'s value-add over `/loop` is the all-ticks trajectory + PR archaeology + conflict reconciliation, not a re-implementation of `/loop`'s restore.
- **Reuse-`saga_id` never-mint discipline [C2].** `/resume` reuses the restored `saga_id` for its one re-entry tick. `saga.py save` mints unconditionally, so never-mint is SKILL-prose discipline (reuse the resolved id) + verified by test, the same shape `/code-review`'s append-only/never-mint used.
- **Boundary.** `/resume` reconstructs + restores + routes; it does NOT mint a new saga, does NOT own a phase's execution loop, and does NOT duplicate the dispatch table.

**Rejected alternatives.**
- *Saga-anchored-only (drop the CE port).* REJECTED — leaves the lifecycle with **no** cold-recovery path when no saga and no issue exist (the verified hole — LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer)). Tier 2 fills exactly that gap.
- *Adopt the `[gstack-context]` commit trailer.* REJECTED — duplicates the saga's append-only log; a parallel durable trajectory to reconcile against is churn, not value.
- *Section-11-literal routing (a `/resume` copy of the routing table).* REJECTED — the dispatch table is `loop/references/dispatch-table.md`; reference it, do not fork it (single source of truth, no drift).
- *Pure read-only (no re-entry tick).* REJECTED — a resumed thread that records nothing leaves the next resumer blind; one git-ignored re-entry tick (reusing the saga_id) marks the resume without minting.
- *Extend `load_saga_context.py` for the all-ticks read.* REJECTED — the wrapper's `--issue` is required, so it is issue-locked and cannot serve a cold no-issue read; the capability belongs in `saga.py`.
- *Re-port gstack context-save/restore.* REJECTED — that engine is the already-shipped saga; there is nothing left to port.
- *Custom `/resume` subagent (an `agents/` dir).* REJECTED — contradicts the shipped `/code-review:164` no-`agents/`-dir convention; use generic agents.
- *Port CE's keyword/branch relevance ranking now.* REJECTED for v1 — recency-MVP ranking is enough until a no-saga forensic returns >5 candidates; deferred to QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking).

**Rationale.** `/resume` is the lifecycle's cold-recovery engine — "I lost context, rebuild the work-thread and continue." The `/loop` rebuild deliberately deferred the heavy half here, and the saga foundation gave it a durable trajectory to reconstruct from. Tier 1 (saga all-ticks) is the common, high-value path; the CE `ce-sessions` Tier-2 port is the last-resort fallback for same-machine work that never wrote a saga — the only path that previously had **no** recovery (the issue-locked `load_saga_context.py` could not serve it). Keeping the all-ticks read in `saga.py` (not the issue-locked wrapper), using generic agents (the `/code-review` convention), referencing the shared dispatch table (no fork, no ping-pong), and reusing the restored `saga_id` for one re-entry tick all keep `/resume` aligned with the conventions the campaign already settled.

**Revisit when.** Codex/Cursor forensics become a real recovery source (revisit the Claude-only Tier-2 port); a no-saga forensic routinely returns >5 candidate sessions and recency-only mis-ranks (revisit the deferred keyword/branch relevance ranking — QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking)); or a fresh-clone (cross-machine) recovery path becomes a real need (Tier 2 is scoped to same-machine today).

**Refs.** Plugin `0.12.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Consumes the saga foundation (adds the all-ticks `read_ticks` reader) — [#saga-schema-foundation](#saga-schema-foundation), spec `plugins/saga/references/saga-spec.md`. Heavy partner of the lightweight half — [#loop-engine-rebuild](#loop-engine-rebuild) (Q4, the lightweight/heavy split it deferred). Verification-cuts-both-ways counterpart to the phantom-source lesson — LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact), [#resume-port-source-verified-true](LEARNINGS.md#resume-port-source-verified-true). No-`agents/`-dir convention catch — DECISIONS [#code-review-engine-rebuild](#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`). Wrapper-wrong-layer learning — LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer). Ship record: ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). Deferred relevance ranking: QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking). Shipped via PR #185 (squash 73975ec).

### Rebuild `/loop` as the campaign's one NATIVE router engine — no upstream to port or merge (PR #183, squash 1fca13a)  {#loop-engine-rebuild}

**Decision.** Rebuild `/loop` — the **sixth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) — from a router stub into a **self-contained native router engine**. This is the campaign's **ONE native rebuild**: unlike every prior rebuild, there is **no upstream engine to port or merge**. CE ships no router; the gstack "dispatch table SKILL" the QUEUED brief named is **phantom** (verified — gstack's root SKILL is browser-testing, there is no router dir; see LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact)); and gstack's context-save/restore is the shipped **saga** plus the queued `/resume`'s engine, **not** `/loop`'s. So `/loop` is authored fresh against the lifecycle's own primitives (saga + operator-choice). Three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive** (inline phase walk with a per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan → restore → route a durable work-thread, with inline cold-reconstruction). The four interview answers settled with Jeff:

- **(Q1) Offload model: inline phase walk + per-decision operator-choice offer; offload pointer scoped to `/loop`-OWNED work only; `/loop` does NOT instruct a routed command's backend.** In Drive mode `/loop` walks the lifecycle phases inline and offers the three execution backends (`inline`/`team-execution`/`cc-workflows-ultracode`) **per decision point** for work it owns. The offload pointer is recorded **only for `/loop`-owned offloads**. When `/loop` *routes* to another command (e.g. `/work`), it does **not** instruct that command's backend — `/work` writes but never reads `orchestration_mode` (verified — SKILL:174,190), so any instruction would have no receiver. Each command owns its own backend decision.
- **(Q2) Routing tick: existing fields + offload pointer only; no schema change.** A routing event ticks the saga carrying the **existing** fields (kind/id/phase/round/status) plus the offload pointer **only for `/loop`-owned offloads**. No new saga schema field — the offload pointer rides existing envelope structure. Avoids foundation churn against the shipped saga spec.
- **(Q3) Durable substrate: volatile `.claude/infiquetra-lifecycle/` + committed artifacts.** `/loop`'s re-entry reads from the volatile session dir `.claude/infiquetra-lifecycle/` for in-flight state plus the committed artifacts (plans, reviews, work-sessions) as the durable substrate. Same split the rest of the lifecycle uses; `/loop` adds no new persistence location.
- **(Q4) Resume split: `/loop` owns lightweight, `/resume` (queued) owns heavy.** `/loop` owns a **lightweight** scan→restore→route plus **inline cold-reconstruction** via `load_saga_context.py` when re-entering without a live session. The **heavy forensic** reconstruction (commit-trailer archaeology, CE forensic reconstruction) belongs to the then-queued `/resume` rebuild — **since SHIPPED 0.12.0**, ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). The `/resume` route from `/loop` is **opt-in advisory**, not a hard handoff.

**Key design points.**
- **No upstream port/merge — authored native.** This is the load-bearing distinction from every prior rebuild. The QUEUED brief (produced by a budget-exhausted brief workflow — see LEARNINGS [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget)) asserted a "gstack dispatch table SKILL" source that does not exist. Verifying that before building (rather than trusting the brief) is what kept the rebuild from chasing a phantom merge — see LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). `/loop` is built directly on the saga (storage) + operator-choice (decision) contracts.
- **Additive saga picker-field extension — closes Defect 1 of `#code-review-saga-scan-touchups`.** `saga.py` `scan()` / `_saga_summary` gained the `issue_ref` / `plan_path` / `branch` match keys (plus `destination` + the `orchestration_mode`/`orchestration_ref` pair the `/loop` picker needs) so a resuming `/loop` (and a standalone `/code-review`) can match the right thread **without** `restore`-ing every candidate. This is the additive, no-schema-churn fix for **Defect 1** of the cross-skill defect the `/work` rebuild surfaced (scan-dict omitted the match keys) — shipped here with the `/loop` rebuild, asserted by `test_scan_exposes_picker_fields`. **Defect 2 (the `/code-review` Phase-5.4 programmatic-mode append contradiction) is a `/code-review` SKILL change, out of scope for this rebuild — which touched no other skill — and REMAINS queued.**
- **Boundary.** `/loop` classifies + routes + (in Drive) walks phases for work it owns; it does NOT override a routed command's own loop (`/work` keeps owning its execution + PR loop), does NOT do heavy forensic reconstruction (`/resume`), and does NOT instruct a destination command's backend.

**Rejected alternatives.**
- *Full hand-to-Workflow (offload the whole loop to a Claude Code Workflow).* REJECTED — overrides `/work`'s own execution loop; each command owns its backend, `/loop` only offers it per decision for work it owns.
- *Router-only (drop the Drive inline-walk value-add).* REJECTED — Route alone makes `/loop` a thin dispatcher with no value over invoking the command directly; the Drive inline phase walk + per-decision backend offer is the value-add.
- *Fold `/resume` into `/loop`.* REJECTED — scope-creeps the queued `/resume` P1 (heavy forensic reconstruction); `/loop` owns only lightweight scan→restore→route + inline cold-reconstruction.
- *Committed offload pointer (a new committed index file).* REJECTED — duplicates the saga index; the routing tick carries the pointer on existing envelope structure.
- *Extend the saga schema for the offload pointer.* REJECTED — foundation churn against the shipped saga spec for a `/loop`-only field; ride existing fields.
- *Instruct the destination command's backend.* REJECTED — no receiver (`/work` never reads `orchestration_mode`, SKILL:174,190); the instruction would silently no-op.
- *Port a gstack "dispatch table".* REJECTED — it does not exist (phantom brief source; root gstack SKILL is browser-testing, no router dir).
- *Re-port gstack context-save/restore.* REJECTED — that engine is the already-shipped saga + the queued `/resume`'s scope, not `/loop`'s.

**Rationale.** `/loop` is the lifecycle's front door — the command that decides where work goes — and it had only a stub. There was no engine to inherit (CE has no router; the named gstack source is phantom), so it had to be authored native against the lifecycle's own saga + operator-choice contracts. Keeping the Route/Drive/Resume split — and scoping the offload pointer + backend offer to `/loop`-owned work only — keeps `/loop` from overriding the per-command backend ownership the campaign already settled (`/work` reads no `orchestration_mode`). Shipping the additive saga picker-field extension here closes **Defect 1** of the cross-skill scan defect the `/work` rebuild surfaced without a schema change; Defect 2 (a `/code-review` SKILL change) remains queued.

**Revisit when.** The `/resume` rebuild lands the heavy forensic reconstruction (revisit the lightweight/heavy split + the advisory `/resume` route); a routed command starts reading `orchestration_mode` (revisit the "do not instruct destination backend" decision); the offload pointer needs to survive across sessions in a queryable way (revisit the no-new-persistence + ride-existing-fields decision); or a real upstream router engine appears worth porting.

**Refs.** Plugin `0.11.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Built native on the saga foundation — [#saga-schema-foundation](#saga-schema-foundation) — and the operator-choice contract — [#operator-choice-framework](#operator-choice-framework). Backend-ownership partner (writes but never reads `orchestration_mode`) — [#work-engine-rebuild](#work-engine-rebuild). Closes Defect 1 of the scan touch-up — ARCHIVE [#code-review-saga-scan-touchups-shipped](ARCHIVE.md#code-review-saga-scan-touchups-shipped); Defect 2 remains QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups). Heavy-resume partner (since SHIPPED 0.12.0): DECISIONS [#resume-engine-rebuild](#resume-engine-rebuild), ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). Phantom-source learning: LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Ship record: ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped). Shipped via PR #183 (squash 1fca13a).

### Rebuild `/work` by merging CE `ce-work` execution engine + gstack `ship`/`land-and-deploy` into a saga-primary-writer execution-loop engine (PR #181, squash d398055)  {#work-engine-rebuild}

**Decision.** Rebuild `/work` — the **fifth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`) and the **execution-loop track** — from a 39-line facilitator stub into a **self-contained infiquetra execution engine that merges CE's `ce-work` execution engine (Jeff-preferred spine) with gstack `ship`/`land-and-deploy`'s autonomy + readiness/staleness gates**. This is a genuine **two-source merge** (like `/code-review`), not a single-source port (like `/founder-review`). It is the **most architecturally entangled** rebuild of the campaign because it lands two deferred foundations at once: the saga becomes first-class (`/work` is its **primary writer**) and the deferred `recommend_execution_backend()` CLI helper finally gets a real caller. Five numbered phases: enter + scan saga + triage + detect round-N → setup + task-list + backend → execute phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready + continuation routing. The four interview answers settled with Jeff:

- **(Q1) Boundary: PR-ready execution + own the round-N PR continuation loop; merge is a confirmed git op `/work` owns; only deploy is delegated.** `/work` executes the build loop to PR-ready, then **owns the PR→review→merge→qa continuation loop** (Jeff's elaboration: "would want to trigger request for review/approval, pickup and /qa after approval and merge, or handle PR requested changes"). `/work` performs the merge itself when destination ⊇ merge, but **only as an explicitly operator-confirmed `gh pr merge`, never silent** — there is no separate "git/human" skill, merge is a git op `/work` owns under confirmation. Only **deploy mutation** is delegated to `infiquetra-deploy`. gstack's canary-verify + offer-revert are **relocated** to `infiquetra-deploy` (a deliberate brief deviation — read to relocate knowingly, not dropped silently; the capability is queued there). Honors saga-spec §1.1/§10 (deploy is deploy's hard boundary).
- **(Q2) Backend offer: recommend + confirm (land `recommend_execution_backend()`).** The deferred CLI helper gets its first real caller: auto-compute the recommendation from size/risk (reusing `should_offer_team_execution`'s six signals), pre-select it, always surface alternatives so escalation is one keystroke, operator confirms. Exactly operator-choice §2. A library-only helper would be uncallable from markdown — the CLI subcommand resolves the deferral.
- **(Q3) Saga role: first-class round-N state spine (primary writer).** `/work` is saga's **primary writer** (saga-spec §11): `restore`-on-resume (rehydrate round/phase/checks_run/next_step), mint/advance `lifecycle_phase` plan→work, a tick per phase boundary, `issue_ref` adoption, `status=done` at completion. It **mints the *findable* saga a standalone `/code-review` appends to** — it sets `issue_ref`/`plan_path`/branch (the match keys), and for its own pre-PR gate calls `/code-review` programmatically and reads the returned envelope **directly** (programmatic mode hands persistence to the caller). The old `load_saga_context.py`/`find_inflight_work.py` become thin read helpers/fallbacks. Resume is deterministic.
- **(Q4) Review gate: hard + override-with-rationale + computed staleness.** Block PR-ready on unresolved P0/P1 (read `/code-review`'s programmatic envelope **directly**) **OR** a stale review (commits since a `/work`-captured reviewed SHA — `git rev-parse HEAD` at review time, `git rev-list <sha>..HEAD --count`). Allow explicit operator override with a **recorded** rationale (never silent). Matches the current stub + `/loop` intent.

**Key design points.**
- **Saga primary-writer; forward-coupling via findable identity, gate via direct envelope.** `/code-review` (shipped 0.8.0) is append-only/never-mint and, when run **standalone**, matches the work-thread saga on `issue_ref`/`plan_path`/`branch`. `/work`'s job is to mint a **findable** saga: it sets `--issue-ref` (the saga-spec §11 issue_ref-adoption write), `--plan-path` when a plan exists, and saves **on the work branch** — the three match keys. For its **own** in-loop pre-PR gate `/work` does **not** depend on code-review finding or writing the saga: it calls `/code-review` programmatically and reads the **returned envelope directly** (programmatic mode = caller owns persistence — code-review writes nothing in that mode). This was a correction folded after the build's adversarial review caught the original "name the identity into the programmatic call so code-review appends" design as **one-sided**: shipped `/code-review` has no arg to receive a caller-named identity and writes no artifact in programmatic mode, so the gate could not read a saga `review_paths` that was never written. Reading the envelope directly + a self-captured reviewed SHA removes that dependency entirely; the standalone-code-review coupling is preserved by the match keys.
- **Round-N saga ownership.** `/work` owns mint + phase tick + round bump (`--rounds-seen`, never `next_round` — it is derived, saga-spec §6.1) + `issue_ref` adoption; a **standalone** `/code-review` appends `review_paths` + preserves `lifecycle_phase`. The two halves of the round-N saga ownership the journal said to settle, now settled. (Residual: `saga.py scan()` does not surface `issue_ref`/`plan_path`/`branch`, so even standalone code-review must `restore` each candidate to match — a cross-skill defect queued for the `/code-review` touch-up, QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups).)
- **`recommend_execution_backend()` lands in `lifecycle_state.py` + a CLI subcommand.** A pure function next to `should_offer_team_execution` (reused, all 6 kwargs passed, plus a `needs_consensus` branch) with an `ultracode` branch and `inline` default. **`alternatives` is computed independently of the precedence winner** so operator-choice §3.3 "offer BOTH on overlap" survives as a one-keystroke escalation. `main()` refactored from the bare positional into `normalize` + `recommend-backend` subcommands (verified no script/test/CI/hook invoked the positional CLI, so the refactor breaks nothing). A deliberate `or needs_consensus` divergence from §3.1's "PLUS" is documented in the docstring.
- **`issue_progress.py` CLI extension.** The *function* `render_issue_comment()` already accepted `work_session_path`/`commit_sha`/`checks_run`/`blockers`/`pr_url`/`review_status`/`doc_review_*`/`deploy_status`/`workflow_url`/`evidence_link`, but the CLI exposed only 8 of those fields — so `/work`'s Phase-4 comment was uninvokable from markdown (dead wiring). This rebuild extends `parse_args`/`main` to forward the full field set (pipe-separated for the list fields). Same "consumer rebuild extends the CLI" pattern as the helper.
- **Computed staleness from a self-captured SHA (the saga has no `reviewed_sha` field).** `/work` captures `REVIEWED_SHA=$(git rev-parse HEAD)` at the moment it runs `/code-review`, then `git rev-list <REVIEWED_SHA>..HEAD --count > 0` ⇒ stale. No parse of a code-review artifact (programmatic mode writes none) and no stored field. Pinned in `test-and-gates.md`. (Corrected from the original artifact-parse design after the adversarial review flagged that programmatic mode writes no artifact to parse.)
- **qa/resume routing is advisory; the qa-phase-advance is honestly deferred.** `/qa` is still a 19-line stub with zero saga awareness (verified). So on merge `/work` sets `phase_status=complete` + `next_step="run /qa"` and routes to `/qa` **advisorily**, but **leaves `lifecycle_phase=work`** — it does NOT claim "/qa owns/advances the qa slot" as if wired. The saga legitimately sits at `work` post-merge until the `/qa` rebuild lands the `qa` advance (`/handoff` deriving `resume-ready` for that state is correct). Likewise `/resume` routing is advisory — `/work`'s own Phase-0 re-entry is the load-bearing "come back later" mechanism, independent of the `/resume` stub.
- **Boundary.** `/work` builds, gates, records, coordinates the PR loop (merge only under explicit confirmation); it does NOT silently mutate GitHub, own deploy/canary (`infiquetra-deploy`), file SDLC issues (`sdlc-manager`), or advance `lifecycle_phase` past `work`.
- **Three new references + own `docs/work-sessions/` artifact dir.** `references/{execution-strategy,test-and-gates,pr-continuation-loop}.md` — the PR-loop transition table got its own ref so the new surface doesn't crowd the SKILL. Work-session artifacts → the canonical `docs/work-sessions/` (no new dir; `handoff_envelope.py` already classifies it).

**Rejected alternatives.**
- *Own canary-verify + offer-revert inside `/work`.* REJECTED — deploy/canary is `infiquetra-deploy`'s hard boundary (saga-spec §1.1/§10); gstack's canary/revert is read-then-relocated to `infiquetra-deploy` (queued there), recorded as a deliberate brief deviation, not dropped silently.
- *Advisory review gate (CE-style, no teeth).* REJECTED — no teeth lets P0/P1 or stale reviews through to PR; the hard gate + honest recorded override matches the stub + `/loop` intent and Jeff's no-lies rule.
- *Load-context-only saga (not a primary writer).* REJECTED — the round-N spine + the standalone-code-review coupling demand `/work` be the first-class minter/writer (setting the findable `issue_ref`/`plan_path`/branch identity), not a read helper.
- *Library-only `recommend_execution_backend()` helper.* REJECTED — uncallable from markdown skills + would drift against the operator-choice doc (the exact reason the 0.5.0 foundation deferred it); ship it with a runnable CLI subcommand, resolved here.
- *Port all of gstack `ship`/`land-and-deploy`.* REJECTED — drags in gbrain, telemetry, VERSION/CHANGELOG/TODOS/Greptile steps, the section-file split, `~/.gstack` persistence, and template machinery irrelevant to infiquetra; extract the autonomy/readiness/staleness/merge-base mechanics, shed the rest.

**Rationale.** `/work` is the loop's execution hub — every real build runs through it — and it had no engine. CE `ce-work` is the proven execution engine (complexity triage, U-ID task-lists, parallel safety, test discipline); gstack `ship` carries the autonomy + readiness/staleness gates CE lacks. Merging both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained and adapted to a 1-human + agents shop. Making `/work` the saga primary-writer is what turns the saga from an unconsumed primitive (and `/code-review`'s append-only write from a no-op) into a real deterministic round-N spine, and landing `recommend_execution_backend()` here gives the deferred operator-choice helper its first real caller. The PR-ready boundary + round-N continuation loop is what makes "PR-ready" not a dead-end while keeping deploy/canary on the right side of the boundary.

**Revisit when.** The `/qa` rebuild lands the `qa` `lifecycle_phase` advance (revisit the post-merge "sits at work" deferral + the advisory routing); the `/resume` rebuild changes who owns cross-session re-entry; `infiquetra-deploy` ships the relocated canary-verify/offer-revert capability (revisit the deploy handoff shape); code-review emits a greppable `reviewed-sha:` token (revisit the staleness parse regex); or the merge-under-confirmation flow proves awkward on real PRs.

**Refs.** Plugin `0.10.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Lands the deferred operator-choice helper — [#operator-choice-framework](#operator-choice-framework). Saga primary-writer against the spec — [#saga-schema-foundation](#saga-schema-foundation). Forward-coupling partner (append-only/never-mint) — [#code-review-engine-rebuild](#code-review-engine-rebuild). Ship record: ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped). Relocated canary capability: QUEUED [#infiquetra-deploy-canary-verify-revert](QUEUED.md#infiquetra-deploy-canary-verify-revert). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. Shipped via PR #181 (squash d398055).

### Port `/founder-review` (alias `/ceo-review`) from gstack `plan-ceo-review` as the scope/ambition review lens (PR #179, squash e4eedf2)  {#founder-review-engine-rebuild}

**Decision.** Rebuild `/founder-review` (alias `/ceo-review`) — the **fourth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`) — from a 20-line stub into a **self-contained infiquetra scope/ambition/direction review engine ported from gstack `plan-ceo-review`** (the 4 scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted pre-review system audit). Unlike `/code-review`'s genuine two-source merge, this is a **PORT, not a merge**: the brief scopes THIS command as **gstack-sole-engine + a single CE posture steal** (the sharpened no-false-precision fragment of `ce-product-pulse`), not a reduced merge. (The brief's "ceo-review" label is loose — the real gstack path is `plan-ceo-review`, verified.) Position in the lifecycle: `/founder-review` is the third member of the review trio — `/doc-review` = plan-readiness, `/code-review` = code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?** — firing **upstream of execution** on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc scope question. Its output is a **scope decision** (challenge direction; `/strategy` records it). The four interview answers settled with Jeff:

- **(Q1) product-pulse: steal the posture only (sharpened); QUEUE a standalone `/pulse`.** Lift only the *transplantable* fragment of CE `ce-product-pulse`'s posture — **no false precision** (when founder-review cites a number — effort, file count, scope size — present it and let the operator judge) + **no hardcoded "too big/too small" thresholds**. Do NOT lift the full telemetry "present the numbers, reader judges" posture wholesale — founder-review is qualitative, not a numbers report. A standalone `/pulse` live-telemetry component is QUEUED (worth-it-when a live product has real telemetry; Infiquetra is pre-revenue greenfield with no data yet).
- **(Q2) Scope modes: keep all 4 (the engine's spine).** SCOPE EXPANSION (cathedral) / SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon) — each distinct, all relevant pre-traction. The operator selects one via `AskUserQuestion` and it is **committed for the whole review — no silent drift**. Context-defaults retained (greenfield→Expansion, enhancement→Selective, bugfix/refactor→Hold, >15 files→suggest Reduction). Trimming re-opens the thin-reskin gap.
- **(Q3) System audit: keep, adapted to infiquetra.** Re-source the pre-review audit to infiquetra inputs — plan artifact + journal + `docs/office-hours/` design notes + `STRATEGY.md` + git context + retrospective + landscape WebSearch (skip gracefully if unavailable); DROP the `~/.gstack`/gbrain/remote-slug/`ceo-plans` machinery. The audit makes the critique grounded (founder-review's analog of code-review's built-vs-planned audit).
- **(Q4) Opt-in flow: per-expansion, capped (+ channel digest).** Keep individual `AskUserQuestion` opt-in per expansion (the "100% in control" guarantee), options A) add / B) defer-to-journal / C) skip, **capped** (gstack's "top 5-6 if >8"). In a redis-channel session `AskUserQuestion` is unavailable → inline + trim aggressively (collapse 0C-bis to a single confirm; present expansions as a digest) so the channel UX stays usable. References `skills/brainstorm/SKILL.md`'s channel-inline convention.

**Key design points.**
- **Scope-layer engine + deep rigor routed in a REAL closed loop.** The engine owns the scope/ambition layer and applies the 9 Prime Directives + 18 CEO patterns as internalized scope-level lenses producing **named scope findings** — it does NOT reproduce gstack's 11 deep-rigor review sections (Architecture, Error-&-Rescue-Map, Security, Data-flow, Code-quality, Test, Performance, Observability, Deployment, Long-Term-Trajectory, Design-&-UX) because infiquetra splits the review lenses (doc/code/founder). Deep rigor is **routed** in a real closed loop: `/doc-review:86` routes *inbound* (suggest founder-review when scope/ambition is prominent); founder-review closes it *outbound* by **writing/updating the (re-)expanded plan artifact and handing it back with the concrete path** (`/doc-review docs/plans/<file>` for readiness; `/code-review` once built). Without the concrete handback, expanding scope then "recommending /doc-review" drops the rigor.
- **founder-review ↔ doc-review boundary stated in the SKILL.** Both can target a `STRATEGY.md`/scope doc; they are complementary lenses — founder-review = *challenge the direction* (ambitious? coherent? worth doing?), doc-review = *check readiness* (can this drive implementation?). The SKILL states this; doc-review already cross-suggests founder-review (`:86`). No doc-review edit (verify-only).
- **Target-conditional Step-0 ceremonies.** gstack's 0C-bis (implementation alternatives) + 0E (HOUR-by-HOUR temporal interrogation) are plan-specific and incoherent on a strategy/scope-question, so they are **conditional on target type** (plan → run both; strategy/brainstorm/scope-question → skip/recast). 0A/0B/0C/0F generalize and always run.
- **No saga write.** founder-review runs upstream/pre-saga and its output is a scope decision, not a readiness/code-review artifact — `saga.py`'s `review_paths` is the wrong home and the "if saga exists" guard would skip ~always. Cross-session persistence = the `docs/founder-reviews/` artifact + the journal ADR. founder-review is NOT a saga review-track consumer.
- **`docs/founder-reviews/` scope-decision dir.** Its own dir (the office-hours/code-review precedent), but the rationale is a scope decision captured for `/plan`/`/strategy` + a journal ADR — deliberately separate from the readiness-review (`docs/reviews/`) and code-review (`docs/code-reviews/`) tracks, and intentionally NOT a `/handoff` artifact source.
- **Office-hours mid-session escape.** Ported as a prose offer in 0A (vague/unframed session → offer `/office-hours`, re-read `docs/office-hours/` notes on return). The gstack `{{INVOKE_SKILL:office-hours}}` inline hack is shed; the detection+offer behavior is kept.

**Rejected alternatives.**
- *Port all 11 deep-rigor sections.* REJECTED — duplicates `/doc-review` + `/code-review`; infiquetra splits the review lenses, so founder-review owns the scope layer and routes deep rigor (closed loop) rather than reproducing the section machinery.
- *Hand-wave the routing ("recommend /doc-review" with no artifact).* REJECTED — the rigor evaporates; gstack bundled all 11 sections precisely to re-rigor expanded scope in-session, so the routing must be a real artifact handback (expanded-plan path → `/doc-review`).
- *Write a saga (append `review_paths`).* REJECTED — dead wiring (the guard skips ~always upstream of the work thread) + wrong field; founder-review is not a saga review-track consumer.
- *Trim the 4 scope modes to 2-3.* REJECTED — re-opens the thin-reskin gap; the 4 modes are the engine's spine, each distinct and pre-traction-relevant.
- *Build `/pulse` now (or fold the analytics artifact in).* REJECTED — premature; Infiquetra is pre-revenue greenfield with no telemetry. Steal the posture, QUEUE the component.
- *Run 0C-bis/0E unconditionally.* REJECTED — they are plan-specific and break on a strategy/scope target; made target-conditional instead.

**Rationale.** gstack `plan-ceo-review` IS the engine for this lens — the 4 committed scope modes + internalized CEO cognition + grounded pre-review audit are the whole point, and there is no CE counterpart engine (CE `product-pulse` is a different artifact — a live-telemetry report). So this is a faithful port + a single posture steal, not a merge. Splitting the review lenses (doc/code/founder) is what lets founder-review own the scope layer and route deep rigor in a closed loop rather than re-implementing 11 sections that already live in its sibling engines. The no-saga-write, scope-decision-dir, and target-conditional ceremonies keep the engine coherent for its actual upstream-of-execution position.

**Revisit when.** A real mid-work-thread founder-review need emerges (revisit no-saga-write); Infiquetra reaches a live product with real telemetry (build the queued `/pulse` and revisit whether founder-review should consume it); the closed-loop handback to `/doc-review`/`/code-review` proves awkward on real expansions; or `/strategy` and founder-review's boundary blurs in practice.

**Refs.** Plugin `0.9.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Sibling review-lens rebuild: [#code-review-engine-rebuild](#code-review-engine-rebuild). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Ship record: ARCHIVE [#founder-review-engine-rebuild-shipped](ARCHIVE.md#founder-review-engine-rebuild-shipped). Queued `/pulse` component: QUEUED [#pulse-live-telemetry-component](QUEUED.md#pulse-live-telemetry-component). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. Shipped via PR #179 (squash e4eedf2).

### Rebuild `/code-review` by merging CE `ce-code-review` spine + gstack `/review` scope/plan audit (PR #177, squash 0a9d8cd)  {#code-review-engine-rebuild}

**Decision.** Rebuild `/code-review` — the third command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`) — from a 20-line stub into a **self-contained infiquetra pre-PR review engine that merges CE's `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories**. Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) → review fan-out → merge + validate → report + route + saga. Position in the lifecycle: `/code-review` is a **within-work gate at the work→PR boundary** (after `/work` produces code, before PR/merge) — it is a code-quality review LENS, a sibling of `/doc-review` and `/founder-review`, but NOT the saga `LIFECYCLE_PHASES` `review` slot (that slot is `/doc-review`'s plan→work gate). The four interview answers settled with Jeff:

- **(Q1) Lens model: CE judgment-based lenses, lean infiquetra set — NOT gstack fixed specialists.** The orchestrator reads the diff and spawns only lenses with real work (CE model, matching `/doc-review`'s triggered-lenses pattern). Always-on (4): correctness, security, testing, maintainability/conventions. Conditional-by-judgment: a **distinct deploy/migration-verification lens** (NOT folded away — its own DynamoDB/IaC/Ansible checklist), plus reliability, performance, api-contract, adversarial/red-team, agent-native, previous-comments. Rails/Swift/Stimulus reviewers dropped. gstack's high-signal checklist categories (enum-completeness-reads-OUTSIDE-the-diff, LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the correctness/security lens checklists.
- **(Q2) Fix behavior: gate-only; adopt the full schema as routing metadata.** Adopt CE's full findings schema NOW (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` / `pre_existing` / `evidence`) so findings are agent-consumable — but `/code-review` itself reports + classifies + routes; it never mutates code, commits, pushes, opens PRs, or files SDLC issues. Fixer dispatch (review-fixer agent / `/work` / team-execution) is OFFERED via operator-choice; the safe-autofix *apply* mode is a later add. The programmatic mode (for `/work`'s future call) is **zero-write to reviewed code** — built from CE's `report-only` BEHAVIOR + `headless` ENVELOPE, deliberately NOT CE's mutating `headless` behavior.
- **(Q3) Validator pass: keep, right-sized by MODE (not severity).** Run CE's independent per-finding validator (a fresh agent re-checks each survivor: real in code? introduced by THIS diff? handled elsewhere? → `{validated, reason}`). Right-sizing is **mode-based** (CE's actual mechanism): programmatic/headless → validate all Stage-A survivors (capped 15, ordered P0→P3, failure → drop); interactive → the operator is the per-finding validator (skip the pre-dispatch pass). The cost control is the upstream suppress-<75 confidence gate + the 15-cap, NOT a severity carve-out.
- **(Q4) Fan-out + saga: all three backends + journal audit + saga review-track (append-only, never mint).** Offer `inline` / `team-execution` / `cc-workflows-ultracode` for the lens fan-out + validator pass, cited at the plugin-root path (`../../references/operator-choice.md`). The plan-completion audit reads the `docs/plans/` artifact + the journal (built-vs-planned, faithful to both engines). `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread saga (found via `saga.py scan`): append the artifact path to `review_paths` + record the backend in `orchestration_mode`, preserving `lifecycle_phase` (code-review does NOT advance the phase). If no saga exists → skip the saga write, never mint, never invent `--kind/--id`.

**Key design points.**
- **Gate-only boundary.** code-review reviews + classifies + routes; it does NOT implement fixes, commit/push/PR, or file SDLC issues — the same lifecycle boundary `/plan` enforces. The programmatic mode carries an explicit "ZERO file writes to reviewed code" rule.
- **Saga append-only, never mint.** `saga.py save` mints unconditionally, so the never-mint guard lives in SKILL prose (scan-first; append to the found saga's exact `--kind` + `--id`; preserve `lifecycle_phase`; skip if absent) + a negative smoke test. No `saga.py` changes (fields/flags already exist).
- **Own-dir `docs/code-reviews/`.** Durable artifacts get their own dir (NOT `docs/reviews/`) to avoid the `handoff_envelope.py` / `sdlc_manager.py` "any file in `docs/reviews/` → plan-ready" classifier misclassification — the office-hours-dir precedent.
- **Scope-drift is informational.** gstack scope-drift produces findings but does not itself block; infiquetra keeps it informational — the normal P0/P1 findings gate is what blocks the PR.
- **Lens-as-judgment lean set with a distinct deploy/migration lens.** The lens set is judgment-selected and lean, but the deploy/migration-verification lens and the reliability lens are kept distinct (sub-domains enumerated in `lens-catalog.md`) so no lens ships as a one-liner.

**Rejected alternatives.**
- *gstack fixed-specialist list with scope gates.* REJECTED — re-opens "spawn reviewers that find nothing on this diff"; CE's judgment-based selection matches `/doc-review` and the agent-team philosophy.
- *Safe-autofix-now (apply fixes in this rebuild).* REJECTED — blurs the gate/work boundary; the apply mode is a future add, fixer dispatch is offered not auto-run.
- *Drop the validator (trust first-pass confidence).* REJECTED — re-opens false positives; a review that cries wolf is worse than none (Jeff's no-lies rule).
- *Severity-carved validator (trust anchor for P2/P3).* REJECTED — a no-op after the suppress-<75 gate already removed low-confidence findings, AND falsely attributed to CE (which has no severity-based validator exemption); mode-based right-sizing is CE's actual mechanism.
- *Saga mint-on-absent.* REJECTED — would create phantom sagas with invented `--kind/--id`; append-only never-mint with a negative smoke test instead.
- *`docs/reviews/`-shared artifact dir.* REJECTED — collides with the `handoff_envelope.py` / `sdlc_manager.py` plan-ready classifier predicate; own `docs/code-reviews/` dir instead.
- *Folded operational lens (deploy-verify folded into a generic lens).* REJECTED — loses deploy-verify specificity; the deploy/migration-verification lens stays distinct.

**Rationale.** CE's `ce-code-review` is the strongest findings/validator engine of either source (rich agent-consumable schema, independent per-finding re-verification, judgment-based lens selection); gstack `/review` contributes the scope-drift + plan-completion audit + high-signal checklist army CE lacks. Merging the two — CE's spine + gstack's audit/checklist — gives an infiquetra-owned review engine that is agent-consumable, grounded in the plan + journal, and honest (verify-don't-guess), without inheriting either source's runtime boilerplate or auto-apply behavior. Gate-only keeps it inside the lifecycle's review-not-execute boundary; the saga append-only wiring makes it the first review-track consumer without re-minting the work thread `/work` owns.

**Revisit when.** A real PR run shows the gate-only stance is too passive and the safe-autofix *apply* mode earns its weight (add the apply mode behind operator-choice); the mode-based validator cap (15) proves too tight or too loose on real diffs; the `/work` rebuild lands and wants code-review to mint/advance the saga rather than append-only (revisit the never-mint guard); or the distinct deploy/migration lens proves redundant with a rebuilt `/qa`.

**Refs.** Plugin `0.8.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Builds on the `/plan` rebuild [#plan-engine-rebuild](#plan-engine-rebuild), the operator-choice contract [#operator-choice-framework](#operator-choice-framework), and the saga foundation [#saga-schema-foundation](#saga-schema-foundation). Ship record: ARCHIVE [#code-review-engine-rebuild-shipped](ARCHIVE.md#code-review-engine-rebuild-shipped). `/work` forward-coupling (now closed — `/work` is saga's primary writer): DECISIONS [#work-engine-rebuild](#work-engine-rebuild), ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped). Shipped via PR #177 (squash 0a9d8cd).

## 2026-06-02

### Rebuild `/plan` by merging CE `ce-plan` artifact engine + gstack `spec` HOW-interrogation (PR #175, squash a13ba68)  {#plan-engine-rebuild}

**Decision.** Rebuild `/plan` — the second command rebuild of the engine-merge campaign — from a 27-line stub into a **self-contained infiquetra plan engine that merges CE's `ce-plan` structured-artifact engine (Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end**. Six numbered phases: enter + warranted-gate → ground (HOW) → interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route + operator-choice. Position in the lifecycle: `/plan` answers **"How should it be built?"** (the WHAT is assumed settled upstream). The four interview answers settled:

- **(Q1) Adopt CE's full artifact skeleton + right-size it.** Take CE's R-ID/KTD/U-ID + per-unit test-scenario shape wholesale (the canonical plan shape, three-audience: human + agent + `/work` consumer), but right-size the engine to infiquetra rather than porting CE's heaviest machinery verbatim — concretely, a CONDENSED deepening pass rather than CE's full 248-line deepening.
- **(Q2) HOW-only interrogation; assume the WHAT upstream.** `/plan` interrogates *how to build it*, grounding in code (cite `path:line`) before asking. It does NOT re-litigate requirements/scope — that's `/ideate` → `/brainstorm` → `/office-hours` territory. Open WHAT-ambiguity triggers a **one-way bounce**: recommend the operator run `/brainstorm` first (with an explicit guard: do NOT claim `/brainstorm` "accepts" a handoff).
- **(Q3) One plan saga via the CLI; epic split → sdlc-manager.** `/plan` emits a single durable **plan saga** via `scripts/saga.py save --lifecycle-phase plan` (runnable, with a hard "never `git add` the tick" boundary). It does NOT mint per-U-ID sagas; multi-unit/epic splits hand to `sdlc-manager`.
- **(Q4) All three backends via the operator-choice doc.** Offer `inline` | `team-execution` | `cc-workflows-ultracode`, cited by path (`references/operator-choice.md`), offered not defaulted — implements the shipped operator-choice contract.

**Key design points.**
- **Review-phase rationale (the gauntlet is NOT dropped).** The full review gauntlet — `/doc-review` + `/code-review` + `/founder-review` — IS the `review` phase, a separate lifecycle stage. `/plan` keeps a CONDENSED deepening self-review and **routes to `/doc-review` (the recommended next exit) before `/work`**. Folding the gauntlet into `/plan` would break the phase model.
- **Doc-frontmatter vs saga-tick split.** The durable plan doc carries human-facing frontmatter (`title`/`type`/`status`/`date`/`origin`) plus the artifact markers (`Implementation Units` / `Key Technical Decisions` / `U1`) so `/doc-review` recognizes it; the machine work-state (lifecycle phase, destination, ADR/KTD refs, orchestration mode) lives in the saga tick. Two surfaces, deliberately not conflated.
- **One-way `/plan`→`/brainstorm` route.** The bounce is a recommendation only, in one direction; `/plan` never claims a handoff contract on the brainstorm side.

**Rejected alternatives.**
- *Lighter agent-consumable variant (thin reskin of the stub).* REJECTED — the stub is exactly the thin-reskin disease the campaign exists to cure; the artifact skeleton is what makes a plan traceable + agent-consumable.
- *Full gstack interrogation in `/plan`.* REJECTED — gstack `spec`'s five-Why + scope/MVP/failure-mode lock is WHAT-rigor that duplicates `/brainstorm`; `/plan` takes only the HOW-interrogation + code-grounding front end. (Seam between the two left as a queued decision-point — see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).)
- *Per-U-ID sagas.* REJECTED — over-reach; one plan saga is the durable record, the U-IDs are slices inside it, and epic splitting belongs to `sdlc-manager`.
- *Defer the saga (plan writes a doc only).* REJECTED — contradicts the saga foundation's §11 consumer contract; `/plan` is a saga consumer and emits one plan saga.
- *Run the full review gauntlet inside `/plan`.* REJECTED — breaks the phase model; the gauntlet is the `review` phase, `/plan` only does a condensed self-review + routes to `/doc-review`.
- *CE's full 248-line deepening pass.* REJECTED — over-heavy for infiquetra; ship a condensed confidence pass instead.

**Rationale.** CE's `ce-plan` is the strongest artifact engine of either source (stable IDs, traceability, per-unit test scenarios, three-audience, already agent-consumable); gstack `spec` contributes the code-grounded interrogation discipline CE lacks at the front. Merging the two — taking CE's skeleton wholesale and grafting gstack's HOW-interrogation — gives an infiquetra-owned plan engine that is traceable, agent-runnable, and grounded, without inheriting either source's runtime boilerplate or duplicating the WHAT-rigor that lives upstream. Right-sizing (condensed deepening, one saga, HOW-only) keeps it proportional to a 1-human + agents shop.

**Revisit when.** A real multi-PR epic shows the one-plan-saga + sdlc-manager epic-split seam is awkward (revisit per-slice saga emission); the `/brainstorm` ↔ `spec` interrogation seam gets resolved and changes where HOW vs WHAT interrogation lives (see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam)); or the condensed deepening pass proves too thin and CE's fuller confidence pass earns its weight.

**Refs.** Plugin `0.7.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#plan-engine-rebuild-shipped](ARCHIVE.md#plan-engine-rebuild-shipped). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Saga foundation: [#saga-schema-foundation](#saga-schema-foundation). Interrogation seam: QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).

### Rebuild `/office-hours` as a faithful two-mode gstack port adapted to infiquetra (PR `#173`, squash `aec888c`)  {#office-hours-engine-rebuild}

**Decision.** Rebuild `/office-hours` — the first command rebuild of the engine-merge campaign — as a **faithful two-mode gstack diagnostic port**, adapted to infiquetra and merged with the CE boundary contract (front-door framing + the `/ideate`↔`/brainstorm` handshake). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE. It is the Think-phase **frame-finding front door** — `/ideate` routes unframed asks here; `/brainstorm` bounces open thought-partner work back. The four interview answers settled:

- **(Q1) KEEP both modes** — Startup mode + Builder mode, not collapsed to one diagnostic. **Jeff override:** Infiquetra is a real startup heading toward paying customers, currently pre-revenue greenfield, so the startup forcing-questions earn their place.
- **(Q2) Route always / frame-note optional** — every session closes by naming a next command; writing a frame note is optional.
- **(Q3) Re-target pushback** — hard on vagueness and ungrounded assumptions, **not** on the operator's judgment; push-twice with escape hatches.
- **(Q4) Frame-finding only + plural exits** — stop the moment you can name the problem and a route; clean exits to `/brainstorm`, `/plan`, `/strategy`. HARD GATE (absolute): never implement, plan, or file an SDLC issue.

**Key adaptations.**
- **Stage-aware startup mode** with a **PRE-TRACTION hypothesis-forming register** — a pre-revenue greenfield operator gets hypothesis-forming questions, not an evidence-audit of customers/traction that don't exist yet.
- **Builder-mode DEPTH FLOOR** — Builder mode is infiquetra's high-frequency mode (infra/workflow/internal-tooling), so it carries real discovery/shaping rigor, not a one-liner.
- **Mid-session mode-switch** — startup↔builder can flip within a session.
- **Frame note in its OWN `docs/office-hours/` dir** (frontmatter `kind: frame-note`), NOT `docs/ideation/` — avoids colliding with the `/ideate` resume-scan (`skills/ideate/SKILL.md:56`).

**Rejected alternatives.**
- *Collapse to one "is the frame settled?" diagnostic.* REJECTED — a review recommended it, **OVERRIDDEN** because Infiquetra is a real startup heading to paying customers; the startup forcing-questions matter.
- *Frame note under `docs/ideation/`.* REJECTED — resume collision with the `/ideate` resume scan (`skills/ideate/SKILL.md:56`); the frame note gets its own `docs/office-hours/` home.
- *Thin builder mode (one-liner).* REJECTED — Builder mode is the high-frequency path and must carry depth.
- *Literal evidence-audit startup questions for a pre-traction operator.* REJECTED — wrong register for pre-revenue greenfield; ported stage-aware to hypothesis-forming instead.

**Rationale.** Faithful gstack port keeps the engine that makes the front door repeatable, shedding gstack's runtime boilerplate per the campaign's port model. The two-mode split survives because infiquetra is genuinely both a startup and a builder shop; the stage-aware + depth-floor adaptations make each mode fit the actual operator rather than a generic YC founder or a throwaway builder check.

**Revisit when.** Infiquetra reaches PMF (revisit the pre-traction register — startup questions can shift back toward evidence-audit); `/investigate` + `/spec` ship (add them as routes).

**Refs.** Plugin `0.6.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#office-hours-engine-rebuild-shipped](ARCHIVE.md#office-hours-engine-rebuild-shipped). Frame-note home: `docs/office-hours/`.

### Operator-choice framework ships doc-only; CLI helper deferred to `/work` (PR `#171`)  {#operator-choice-framework}

> **Update (2026-06-13).** The §3.2 "deterministic fan-out, not review depth" framing introduced here was
> corrected, and `adversarial_confidence` + `has_code_surface` were added to the recommender — see
> [#operator-choice-docs-and-confidence](#operator-choice-docs-and-confidence). The doc-only-then-helper
> sequencing, the three-backend enum, and the always-confirm/capability-gate properties below all stand.

**Decision.** Ship the operator-choice framework as a **DOC-ONLY foundation**: `references/operator-choice.md` — the decision contract for the three execution backends `inline` | `team-execution` | `cc-workflows-ultracode` (these enum strings are the contract; prose labels like "CC workflows"/"ultracode" are not) — plus short prose **offer hooks** in `/loop` and `/work`. Lifecycle owns the **choice**, not execution. No code/helper ships this PR. The four interview answers settled:

- **(a) Who decides** — auto-recommend + **always confirm**. Inline-by-default; escalation is cheap. The agent proposes a backend; the operator confirms.
- **(b) Triggers** — `team-execution` when any `should_offer_team_execution` constant trips (`file_count>=8`, `phase_count>=4`, `has_security`, `has_infra`, `cross_repo`, `deployment_sensitive`) **or** the work needs reviewer consensus; `cc-workflows-ultracode` for broad-independent-parallel-fan-out / exhaustive-sweep work (Claude-Code-only). On **OVERLAP, offer BOTH** — no hard precedence rule.
- **(c) Capability gate** — document all three backends always; **hide** the ultracode option only when the Workflow tool is observably absent; **always graceful-fallback** at execution time.
- **(d) Scope** — `/loop` and `/work` only this PR. The other command rebuilds wire their own offers as they land.

**Rejected alternatives.**
- *Add a library-only `recommend_execution_backend()` helper now.* REJECTED — skills are markdown the agent reads, so a Python helper with no caller would be uncallable and would drift against the doc. This is the verified state of the existing `should_offer_team_execution` (defined in `lifecycle_state.py` but never called outside its own test). The CLI-backed helper is **DEFERRED to the `/work` rebuild**, where it gets a real caller.
- *Silent auto-pick.* REJECTED — violates always-confirm; the operator must see and accept the escalation.
- *Show-but-disable the ultracode option when unavailable.* REJECTED — hide it instead (cleaner; capability is observable).
- *Wire all lifecycle commands now.* REJECTED — scope is `/loop` + `/work`; the rest cite the doc as they rebuild.
- *A hard "risk dominates fan-out" precedence rule on overlap.* REJECTED — cosmetic given always-confirm; offering BOTH lets the operator decide.
- *Copy the brainstorm channel-inline wording verbatim.* REJECTED — reference `skills/brainstorm/SKILL.md`'s canonical channel-inline convention (redis-channel sessions cannot call AskUserQuestion) instead of duplicating it.

**Rationale.** Matches the queue's "no scripts" sizing — one shared reference doc + 2-3 line offer hooks. The doc is the consumed source of truth (the decision contract, complementing `saga-spec.md`'s storage contract). An honest unconsumed-style foundation in the same spirit as the saga ship: settle the contract before consumers calcify it.

**Revisit when.** The `/work` rebuild — wire the CLI-backed execution-backend helper against this doc (or decide the prose offer suffices and no helper is needed).

**Refs.** Plugin `0.5.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Decision contract: `plugins/saga/references/operator-choice.md`; complements storage contract `references/saga-spec.md`. Ship record: ARCHIVE [#operator-choice-framework-shipped](ARCHIVE.md#operator-choice-framework-shipped). Channel-inline convention: `plugins/saga/skills/brainstorm/SKILL.md`. Shipped via PR `#171` (squash `e935bd4`).

### Saga schema: derived `kind-id` identity + append-only envelope log + three-axis state (PR `#170`)  {#saga-schema-foundation}

**Decision.** Define `saga` — the durable, resumable work-state envelope — as the first foundation of the engine-merge campaign, with this schema:

- **Identity: derived `kind-id`** (`issue-<N>` / `task-<slug>`), minted at birth and **sticky**. `round` and `phase` are *fields*, not identity. A task-saga that later gets an issue keeps its id and gains an `issue_ref` (the index cross-references `issue_ref → saga_id` so it stays findable by issue#). Human-legible dirs (`sagas/issue-42/`), deterministic, backward-compatible with the old `{kind}-{id}`.
- **Storage: append-only timestamped envelope log (canonical) + derived `state.json` index (rebuildable).** Each tick is an immutable file `sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`; ordering is **always by filename string, never mtime** (same-second collision → `-1` suffix). The index is `{last_updated, active_saga_id, sagas:{...}, current_work:{…legacy fields…, saga_id}}`, written atomically (temp+rename); a corrupt index is never fatal because `scan` rebuilds from the log.
- **File format: gstack envelope** — YAML frontmatter (machine fields incl. `extra:` for unknown-key round-trip) + `## Summary` / `## Decisions` (KTDs) / `## Remaining` / `## Notes / Tried` body. Cold-resume reads from frontmatter; matches the shipped CE-artifact house style.
- **Three stored state axes, one derived:** `lifecycle_phase` (CE flow: `ideation|brainstorm|plan|review|work|qa|retro`), `phase_status` (`pending|in_progress|complete`; authoritative, drives `next_phase` = phase+1 if complete else phase), `status` (thread disposition: `active|blocked|paused|handed-off|done|abandoned`; MUST NOT take `pending`/`in_progress`). **`maturity` is derived at `/handoff` time** from `lifecycle_phase` (the existing `infer_maturity` mapping), not stored.
- **List merge: full-snapshot semantics** — a tick's lists replace; absent carries forward; empty clears. Not union.
- **Full unify now:** one `saga.py` engine (`save`/`restore`/`scan`/`context`) with the 3 legacy scripts refactored into thin wrappers.
- **Spec home: plugin-level** `plugins/saga/references/saga-spec.md` (a new convention — no plugin-level `references/` existed before); each consuming SKILL links to it.

**Rejected alternatives.**
- *Minted opaque saga-id (UUID/counter).* Rejected: not human-legible, not deterministic, requires a lookup to resume issue-born work. Derived `kind-id` is self-describing and backward-compatible.
- *Engine-only, migrate the storage format later (PR1 engine+wrappers / PR2 format).* Considered as a de-risk fallback; rejected for this ship in favor of one PR — the user chose "full unify now," and characterize-first tests make the format migration safe in a single change.
- *mtime ordering.* Rejected: mtime is not stable across rsync/backup/snapshot-restore; filename-as-order is deterministic and copy-safe. (Note: the win is for rsync/backup, NOT git worktrees — those don't carry git-ignored state at all.)
- *Union list merge.* Rejected: union-only lists accumulate stale `open_questions`/files and mislead cold resume; gstack ticks are full snapshots, so resume payloads must be able to shrink.
- *Stored `maturity` axis.* Rejected: redundant with `lifecycle_phase`; deriving it at `/handoff` removes a constant axis and the `status`↔`phase_status` ambiguity.
- *Round/phase in the identity.* Rejected: would re-mint a saga id every round, breaking sticky resume; round and phase are mutable fields of a single sticky-id thread.

**Rationale.** Saga is **gstack-dominant** (CE has no saga primitive — single-session assumption — so only its artifact-discipline framing is borrowed): gstack supplies the envelope mechanics (frontmatter+body, filename-as-order, branch-agnostic restore); the payload richness (issue+PR rounds, journal/ADR linkage) is lifecycle's own scripts; CE's contribution is the implied flow recorded in `lifecycle_phase`. Settling the contract semantics (axes, snapshot lists, `current_work`) in the spec **before** consumers calcify them is the whole point of building this foundation first. This ships an **unconsumed primitive** — after this PR no command calls `restore`/`scan`; the 3 legacy CLIs keep working as wrappers and the engine is validated by its own unit tests + manual smoke. Consumer wiring (`/work`, `/resume`, `/loop`, `/plan`) is each consumer's own queued item.

**Revisit when.** A consumer rebuild surfaces a missing/awkward field or enum (extend via `schema_version` + the `extra:` preserve-unknown seam, not a breaking change); append-only growth needs a GC policy (the spec leaves a `max_ticks` seam); or a second identity collision pattern emerges that the derived-id guards don't cover.

**Refs.** Plugin `0.4.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Spec: `plugins/saga/references/saga-spec.md`. Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. ARCHIVE [saga foundation shipped](ARCHIVE.md#saga-foundation-shipped) — consumers remain queued in [QUEUED.md](QUEUED.md).

### Rebuild lifecycle commands by merging gstack + CE engines into self-contained infiquetra engines (commit pending)  {#lifecycle-engine-merge-campaign}

**Decision.** Rebuild each diverged `infiquetra-lifecycle` command — and adopt two missing ones (`/investigate`, `/spec`) — by **merging the best of compound-engineering (CE) and gstack into a new, self-contained infiquetra engine**, worked **1-by-1 via an interview-driven merge**. Port model = the shipped `/ideate` rebuild: extract the engine, adapt to infiquetra (1-human + multi-agent team; `sdlc-manager` owns SDLC issues/boards/readiness; `infiquetra-deploy` owns deploy; the engineering journal; context-libraries), and shed gstack's ~780-line runtime boilerplate **with Jeff's per-item sign-off**. Neither source has priority — Jeff leans CE. Build two foundations first: a first-class `saga` durable/resumable work-state envelope (P0) and a shared inline / team-execution / Claude-Code-workflows operator-choice framework (P1), because the command rebuilds read them. Full per-command queue: [QUEUED.md](QUEUED.md) engine-merge initiative.

**Rejected alternatives.**
- *Adopt one upstream wholesale (just gstack, or just CE).* Rejected — Jeff: "otherwise I would just use one or the other and forget about all this." The value is a merged engine infiquetra owns and evolves, taking bits of both.
- *Vendor gstack / runtime-depend on CE.* Rejected — same standalone-boundary rationale as the `/ideate` ADR ([#ce-ideation-engine-restore](#ce-ideation-engine-restore)); gstack also carries ~780 lines of runtime plumbing (telemetry, gbrain, `~/.gstack`, model overlays) irrelevant to infiquetra.
- *Leave the thin stubs.* Rejected — they bias toward facilitation; the engine is what makes a command repeatable. See LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic).
- *Auto-shed gstack boilerplate without review.* Rejected — Jeff wants input on what's shed; each rebuild surfaces shed candidates for sign-off.

**Rationale.** CE and gstack each have engine mechanics worth keeping (CE: structured artifacts, causal-chain debugging, persona/findings/validator review; gstack: scope-mode reviews, risk-gated QA, multi-specialist fan-out, save/restore checkpoints). Merging the best of both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained, evolvable, and adapted to a 1-human + agents shop where artifacts must be agent-consumable. Worked 1-by-1 so each merge is a deliberate, interview-settled design, not a bulk port that would re-introduce the stub-disease at engine level.

**Revisit when.** A command's interview shows the merged engine is more than infiquetra needs (ship a lighter version), or CE/gstack ship a materially better engine worth re-syncing, or the parallel-fork maintenance cost exceeds the value of self-containment.

**Refs.** QUEUED engine-merge initiative; LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic), [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget), [#stub-port-drops-engine](LEARNINGS.md#stub-port-drops-engine); DECISIONS [#ce-ideation-engine-restore](#ce-ideation-engine-restore), [#sdlc-handoff-ownership-boundary](#sdlc-handoff-ownership-boundary).

## 2026-06-01

### Restore the CE ideation engine into `/ideate` + `/brainstorm`, self-contained (commit `30c9099`)  {#ce-ideation-engine-restore}

**Decision.** Rebuild `infiquetra-lifecycle`'s `/ideate` and `/brainstorm` from thin facilitative
stubs into full divergent→convergent engines ported from compound-engineering (CE) and adapted to the
infiquetra world — self-contained, no runtime dependency on CE. `/ideate` generates many candidates
across parallel frame agents, critiques all, and presents only survivors; cut ideas stay revivable.
Two deliberate improvements over CE: (1) a two-way partnership — operator seeds feed *into* the frame
agents and face the same critique; (2) a revival state machine that re-enters the filter with new
evidence (and adjudicates novelty) so revival cannot soft-promote a categorically-cut idea. Added
infiquetra grounding CE never had: context-library reader (`*-context-library` via `gh`), named-repo
reader, grounding-fit gate, read-only `gh` issue-theme clustering. Dropped CE's Proof/HITL,
HTML/output-mode, elsewhere/non-software modes, Slack, and web-research-cache.

**Rejected alternatives.**
- *Delegate to CE at runtime (load `ce-ideate` when present).* Rejected: couples lifecycle to CE
  being installed at a compatible version and drags in CE's ecosystem (Proof, modes, conventions);
  contradicts the plugin's standalone Boundaries.
- *Keep the thin facilitative stubs.* Rejected: "produce a small option set; lead the user through
  choices" biases toward facilitation, which is why ideation felt like the operator supplied all the
  ideas. See LEARNINGS `{#stub-port-drops-engine}`.
- *Issue themes via `sdlc-manager`.* Rejected: `sdlc-manager` has no theme-clustering and issue
  *reads* are not its boundary (it owns mutation). `/ideate` reads issues read-only via `gh` and
  clusters them itself.

**Rationale.** The operator wanted CE's generative engine + survivors back, plus a genuine
partnership where their ideas also enter the pool and rejected ideas are revivable. Self-contained
keeps the plugin's ownership boundaries clean. Forked from CE 3.9.2; authored and adversarially
verified via an ultracode workflow (13 agents; 5 major findings remediated, 0 blocking).

**Revisit when.** CE ships a materially better ideation engine worth re-syncing, or the parallel-fork
maintenance cost exceeds the value of staying self-contained.

**Refs.** Plugin `0.3.0`, marketplace metadata `2.4.0`. LEARNINGS `{#stub-port-drops-engine}`. Plan
`.claude/plans/can-you-review-the-inherited-lantern.md`.

## 2026-05-31

### Rename `infiquetra-loop` → `infiquetra-lifecycle` (commit `0ed70f2`)  {#rename-loop-to-lifecycle}

**Decision.** Rename the plugin to `infiquetra-lifecycle`. "Loop" named only the `/loop` router
command, not the idea-to-ship lifecycle the plugin actually spans (Think → Plan & execute → Hand
off → Review → Improve & route). Renamed the ignored runtime-state dir to
`.claude/infiquetra-lifecycle/` and the handoff-envelope field `loop_owner` → `lifecycle_owner`,
with `sdlc-manager` updated in lockstep (its 4 hardcoded state-path references). Kept the `/loop`
command name unchanged — it's one verb in the lifecycle, not the whole thing. Surfaced the
five-phase command grouping in the plugin description, both READMEs, and the changelog so users see
the categorization.

**Rejected alternatives.**
- *`infiquetra-flow`.* Rejected: still reads too close to "loop" and is vaguer about scope.
- *`infiquetra-sdlc`.* Rejected: collides conceptually with the existing `sdlc-manager` plugin,
  blurring the boundary (lifecycle workflow vs GitHub issue/board ownership).
- *`infiquetra-cadence` / `-forge` / `-workbench`.* Rejected: evocative but less self-describing
  than "lifecycle".
- *Rewrite the old name in dated historical docs (brainstorms, ideation, plans, reviews,
  work-sessions, `ARCHIVE.md`).* Rejected per the journal rule "never silently overwrite history" —
  those artifacts record what the plugin was called at the time.

**Rationale.** The name should describe what the plugin does to a first-time user. "Lifecycle"
matches the description and command taxonomy; "loop" undersold it.

**Revisit when.** The plugin's scope narrows back to pure routing/iteration, or a clearer
single-word name for "full engineering lifecycle" emerges.

**Refs.** Plugin `0.2.0`, `sdlc-manager` `1.6.1`, marketplace metadata `2.3.0`.

### SDLC handoff issue artifacts belong to `sdlc-manager` (commit `2fc317e`)  {#sdlc-handoff-ownership-boundary}

**Decision.** Put handoff issue drafting, source artifact resolution, handoff maturity metadata,
prepared-draft sidecars, mutation plans, labels, board placement, and create-after-confirmation in
`sdlc-manager`. Keep `infiquetra-loop` responsible for lifecycle context and future `/handoff`
routing only.

**Rejected alternatives.**
- *Generate handoff issue bodies inside `infiquetra-loop`.* Rejected: it would duplicate SDLC
  issue semantics and make two plugins responsible for labels, project fields, and readiness.
- *Add a separate handoff artifact format.* Rejected: prepared issue drafts already provide the
  markdown plus JSON sidecar boundary needed for review before mutation.
- *Require recipient teams to have `infiquetra-loop` installed.* Rejected: handoff issues must be
  self-contained for agent teams or humans working only from GitHub.

**Rationale.** This keeps the lifecycle plugin thin at the exit point while centralizing SDLC
mutation rules in the plugin that already owns issue readiness. The prepared draft remains useful
without mutation, and `issue create-prepared` remains the single place where side effects are
rendered and confirmed.

**Revisit when.** Multiple non-SDLC destinations need the same handoff source resolver, or
`infiquetra-loop` grows durable lifecycle state that cannot be represented cleanly in the
prepared issue sidecar.

**Refs.** Plan [Add SDLC handoff flow](../plans/2026-05-30-002-feat-sdlc-handoff-flow-plan.md);
requirements [Infiquetra Loop SDLC Handoff](../brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md).

### Prepared issue workflow uses draft/sidecar boundary plus confirmed mutation (commit `74cd372`)  {#prepared-issue-workflow-boundary}

**Decision.** Add `sdlc-manager issue prepare` and `issue create-prepared` as separate steps.
`issue prepare` writes a markdown draft and JSON sidecar; `issue create-prepared` re-runs
readiness, renders a mutation plan, asks for confirmation, repairs repo prerequisites, handles
mapping PRs, creates the issue, and records the result back onto the draft.

**Rejected alternatives.**
- *Direct source-text to `gh issue create`.* Rejected: bypasses review and makes readiness failures
  visible only after the external issue exists.
- *Put LLM interpretation inside `sdlc_manager.py`.* Rejected: the CLI should stay deterministic;
  skills and agents own rough-source interpretation.
- *Create new issue types for Asgard/Olympus.* Rejected: the six SDLC issue types remain
  canonical; team differences belong in readiness profiles and board/status routing.

**Rationale.** The split gives operators a durable review point before GitHub mutation while still
letting the final create flow perform repo repair and board placement as one visible plan.
Sidecars keep deterministic metadata and lifecycle state out of prose-only markdown, and
re-validation prevents stale edited drafts from bypassing team readiness.

**Revisit when.** Multiple non-agent callers need deterministic text-to-body generation inside the
CLI, or when prepared drafts become common enough to justify a richer review UI or batch create
surface.

**Refs.** LEARNINGS [prepared issue artifact boundary](LEARNINGS.md#prepared-issue-artifact-boundary).

## 2026-05-29

### Split Infiquetra lifecycle orchestration from deployment mutation (commit pending)  {#infiquetra-loop-deploy-boundary}

**Decision.** Add `infiquetra-loop` as the daily lifecycle orchestration plugin and
`infiquetra-deploy` as a separate deployment plugin. `infiquetra-loop` owns office-hours,
strategy, ideation, brainstorm, planning, work execution, code review, optimization, QA, SDLC
issue progress, engineering-journal prompts, retro, and resume. `infiquetra-deploy` owns
tag-promotion deployment, status, release notes, rollback, and hotfix helpers. `team-execution`
remains independent and is offered only when risk, size, or parallelism justify the cost.

**Rejected alternatives.**
- *One merged super-plugin.* Rejected: deployment mutation has a higher blast radius than
  lifecycle coaching and should keep a hard operational boundary.
- *Copy Superpowers, Compound Engineering, gstack, and VECU workflows wholesale.* Rejected:
  the useful pieces need to be adapted to Infiquetra docs, SDLC, and context-library references;
  generic cleanup, GitHub helper, and plugin-management utilities are intentionally out of scope.
- *Version raw loop state as repo artifacts.* Rejected: durable plans and work-session summaries
  belong in repo docs, but raw checkpoint state, API caches, validator JSON, and resume scratch
  are local session data and already covered by the `.claude/` ignore convention.

**Rationale.** The split lets the daily loop replace recurring Superpowers and Compound
Engineering lifecycle use while still enforcing a clear deployment safety boundary. Durable docs
give session-to-session continuity without committing stale runtime state. Keeping `team-execution`
separate preserves its validator and nonprod automation contract without forcing every loop to pay
that token or coordination cost.

**Revisit when.** Deployment policy moves out of tag-promotion, loop usage shows deployment
handoff friction dominates safety value, or `team-execution` becomes cheap enough to run by
default on normal work.

**Refs.** `plugins/infiquetra-loop/`, `plugins/deploy/`,
[team-execution v2 decision](#team-execution-v2-validators).

---

## 2026-05-27

### `team-execution` v2 uses context-selected validators and guarded nonprod automation (commit pending)  {#team-execution-v2-validators}

**Decision.** Evolve `team-execution` from reviewer-only orchestration into a reviewer plus
validator workflow. Validators are a maximum available roster, selected by repository context,
changed files, workflows, contracts, docs, tests, and optional `.team-execution.json`. Automation
is allowed only for `github.com/infiquetra/*`, only after gates pass, and only for nonprod or
publish-nonprod workflows.

**Rejected alternatives.**
- *Spawn every validator on every plan.* Rejected: creates noise, cost, and false blockers for
  validators unrelated to the change.
- *Let validators run before reviewer consensus.* Rejected: reviewer non-consensus means the
  implementation is still unstable; validator findings would be stale or duplicated.
- *Allow generic deployment automation once checks pass.* Rejected: production, staging, branch
  deletion, force-push, and credential changes carry a higher operational risk than this plugin
  should automate.

**Rationale.** Context selection keeps validator evidence proportional to risk while still making
the approved roster available. Gating validators after reviewer consensus creates a stable artifact
to scan and test. Nonprod-only automation gives useful end-to-end validation without turning a
planning plugin into a production deployment system.

**Revisit when.** We have repeated evidence that a validator category is always selected together
with another category and should be merged, or when production deployment safety is owned by a
separate audited release plugin.

**Refs.** LEARNINGS [team setup asset drift](LEARNINGS.md#team-setup-asset-drift).

---

## 2026-05-25

### `redis-channel` plugin: Hermes-agnostic Claude Code channel over Redis Streams (commit pending)  {#redis-bridge-decoupled}

**Decision.** Build the `redis-channel` plugin as a generic Claude Code channel that speaks a documented Redis-streams protocol — no Hermes-specific knowledge in the plugin. The Hermes-side counterpart (`hermes-claude-code-router`) lives in its own public GitHub repo so the protocol is reusable by any future consumer.

**Rejected alternatives.**
- *Embed Hermes/Discord logic directly into the plugin.* Rejected: would reimplement Discord voice-receive that already works (battle-tested) in `hermes-agent`. Verification confirmed the voice-receive code is **not** in `home-lab/asgard_voice_arbiter` (where the initial design assumed it lived) — the arbiter is routing-only; the sink/decode lives in closed-source `hermes-agent.gateway.platforms.discord`. Rebuilding would have been 3–5 days of unknown work.
- *Add the router as a 4th plugin inside `infiquetra/infiquetra-hermes-plugins`.* Considered seriously after `infiquetra-hermes-plugins` was identified as the canonical external-plugin pattern. Rejected per user preference for independent versioning. The router's expected LoC (~1k+) justifies its own home.
- *Use HTTP transport between plugin and router.* Rejected: Redis already runs on Mac mini for `voice_coordinator`; Streams give durable + ordered + consumer-group resume; no port-binding on either side; matches existing Hermes infra patterns.

**Rationale.** Decoupling means: (a) any future consumer (web UI, mobile app, CLI test harness) can drive a Claude Code session by speaking the protocol; (b) the plugin is testable without Hermes infrastructure; (c) protocol changes are version-gated, not implicit. The protocol spec (PROTOCOL.md) and pydantic models (`server/protocol.py`) are copied verbatim into both repos; synchronized PRs enforce drift detection at review time.

**Revisit when.** A second router consumer materializes and surfaces protocol shortcomings, OR the multi-session registry proves unused after 1 month of production data (then collapse to 1:1 lock and merge the router back into a more direct architecture).

**Refs.** [voice-only-permission-approval](#voice-only-permission-approval), [askuserquestion-interception](#askuserquestion-interception), [redis-bridge-verification](LEARNINGS.md#redis-bridge-verification), plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

### Permission approval is voice-only in v1 with destructive echo-confirm (commit pending)  {#voice-only-permission-approval}

**Decision.** Tool-permission relay over the channel accepts only voice approval ("yes <id>" / "no <id>"). Discord button approval (ephemeral DM Allow/Deny) is deferred to v2. Destructive operations (Write/Edit/NotebookEdit + Bash regex matches in `is_destructive`) trigger an echo-confirm safety net: "Approving destructive Bash. Say 'cancel' within 3 seconds."

**Rejected alternatives.**
- *Voice + Discord buttons in parallel (first-wins).* Rejected for v1: adds discord.py interaction handling, ephemeral message lifecycle, race-cancel logic — and the parallel-path UX optimizes for a scenario that doesn't actually exist (you're either hands-free in voice OR at Discord text; rarely both). v2 candidate if usage shows demand.
- *Tool-class allowlist (voice can approve read-only, never destructive).* Rejected by user: they want full hands-free. Mitigated by destructive echo-confirm + audit logging from day 1; revisit if false-positive rate is non-trivial.
- *Always require terminal approval.* Rejected: defeats the hands-free use case.

**Rationale.** Whisper false-positive rate (~1.4% on clean audio, higher in noise) is a real risk for destructive commands. 5-char random IDs (~11.8M space, generated by Claude Code core) make accidental triggering unlikely; 30s window bounds exposure; echo-confirm provides a "did you really mean it" beat. Audit logging from day 1 produces the data needed to tighten or relax this later.

**Revisit when.** Audit logs show ≥1 false-positive destructive approval in a month, OR usage data shows users prefer Discord-button approval to voice approval (would justify the parallel-path build cost). See [Discord button approval](QUEUED.md#discord-button-approval).

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `is_destructive` classifier at `plugins/redis-channel/server/protocol.py`.

### `AskUserQuestion` interception over agent-file coaching (commit pending)  {#askuserquestion-interception}

**Decision.** When Claude calls `AskUserQuestion` from a `redis-channel` channel session, the CC plugin's MCP server intercepts the tool call and converts the structured question to an inline-choice reply ("Which? A) ..., B) ..., C) ..."). The user's free-text response is parsed against the options and returned as the tool result. Agent-file coaching (in `agents/redis-channel-coach.md`) is provided as a friction-reducing hint but is **not** the enforcement layer.

**Rejected alternatives.**
- *Coach Claude via `agents/redis-channel-coach.md` to avoid AskUserQuestion when source is a channel.* Rejected as primary mechanism: Claude's training pulls it toward AskUserQuestion for clarification; coaching is probabilistic, not deterministic. Verified the channel protocol has no native facility by reading the official Discord channel plugin source + `https://code.claude.com/docs/en/channels-reference`.
- *Wait for the Claude Code channels protocol to add structured-question support.* Rejected: not on the published roadmap; would block v1.
- *Fail the AskUserQuestion call with an error so Claude retries with inline text.* Rejected: poor UX (user sees a tool error, not a question).

**Rationale.** Interception is deterministic. The MCP server sees every tool call before it reaches the user; converting it to a `reply` + parsing the next inbound is a finite-state interaction the server fully controls. Removes a category of "Claude ignored the coach" failures.

**Revisit when.** Claude Code adds a native `notifications/claude/channel/question_request` / `question_verdict` pair to the channel protocol — then replace interception with passthrough. Tracked in `plugins/redis-channel/PROTOCOL.md` "Reserved future expansion."

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `plugins/redis-channel/PROTOCOL.md` AskUserQuestion section.

---

## 2026-05-08

### Adopt uv as canonical dependency sync (commit pending)  {#uv-canonical-sync}

**Decision.** Use uv as the canonical repository dependency sync tool. Track `uv.lock`, install CI dependencies with `uv sync --locked --extra dev`, and run local and CI checks through `uv run`.

**Rejected alternatives.**
- *Keep using pip in CI.* Rejected: it contradicts the desired repository standard and leaves installs unreproducible.
- *Use `uv pip install` without a lockfile.* Rejected: it is still an ad hoc install path and does not satisfy the existing revisit condition for tracking `uv.lock`.
- *Move all dev dependencies to `[dependency-groups]` now.* Rejected: the existing `dev` extra maps directly from the prior `pip install -e ".[dev]"` workflow, so moving dependency ownership would add churn without improving the conversion.

**Rationale.** The repository already has `pyproject.toml` metadata and had a documented revisit condition to track `uv.lock` once uv became canonical. A checked lockfile plus `uv sync --locked --extra dev` makes CI and local development use the same dependency graph.

**Revisit when.** uv stops being the repository development standard, or the project intentionally changes from extras-based dev dependencies to uv dependency groups.

**Refs.** Supersedes the `uv.lock` portion of [gitignore `.claude/` + no `uv.lock`](#gitignore-claude-and-no-uv-lock); archived pre-correction version in [ARCHIVE](ARCHIVE.md#superseded-no-uv-lock-decision).

---

## 2026-05-01

### Gitignore `.claude/`; `uv.lock` decision superseded (commit `4da5705`)  {#gitignore-claude-and-no-uv-lock}

**Decision.** Add `.claude/` to `.gitignore`. The prior decision not to track `uv.lock` is superseded by [Adopt uv as canonical dependency sync](#uv-canonical-sync).

**Rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.

**Rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). The earlier `uv.lock` rationale was correct when the repo used ad hoc pip/uv installs, but no longer applies now that uv is the canonical lock-and-install path.

**Revisit when.** Claude Code introduces a *shared* settings file under `.claude/` that's intended to be checked in. At that point, narrow the gitignore from `.claude/` to specifically `.claude/settings.local.json` and `.claude/context/`.

**Refs.**
- DECISIONS [uv canonical sync](#uv-canonical-sync) — supersedes the lockfile portion of this decision.
- LEARNINGS [marketplace registry drift](LEARNINGS.md#marketplace-drift) — same PR (#112).
- ARCHIVE [PR #112](ARCHIVE.md#pr-112-marketplace-fix) — shipped record.
- ARCHIVE [superseded no-uv-lock decision](ARCHIVE.md#superseded-no-uv-lock-decision) — pre-correction record.

---
