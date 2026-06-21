---
date: 2026-06-20
topic: execution-backend-representation
focus: how saga's /plan flow represents, names, defaults toward, and authors the execution backends — esp. Claude Code dynamic (ultracode) workflows
scope: standard
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Execution-Backend Representation & Dynamic-Workflow Authoring

Part of the plugin-grooming campaign (a sibling to
[`2026-06-20-net-new-skills-agents-ideation.md`](./2026-06-20-net-new-skills-agents-ideation.md) —
Track 1). This run deepens that doc's tiering item (#4/#5): survivor **S5** here is the per-agent
model+effort tiering reframed as a *plan property*, and the build sequencing should treat the two docs
as one thread. Operator drives `/brainstorm` next (the keystone, S2, is the natural first seed).

## Grounding Context

**Repo:** saga is the lifecycle *engine* — it CHOOSES an execution backend, surfaces it, and records a
pointer (`orchestration_mode` enum + `orchestration_ref`); it never vendors backend machinery
(`operator-choice.md` "offered, not vendored"). Three backends: `inline` (serial, the default),
`team-execution` (a `## Team Structure` plan section + reviewer consensus ≥9.0/10 + scanner/deploy
gates, run as a human-orchestrated tmux protocol), and `cc-workflows-ultracode` (the Claude Code
Workflow tool — deterministic multi-agent orchestration; Claude Code only). The selection contract is
`plugins/saga/references/operator-choice.md`; the recommender is
`plugins/saga/scripts/lifecycle_state.py` (`recommend_execution_backend` / `should_offer_team_execution`);
the enum is `ORCHESTRATION_MODES` at `saga.py:71`.

**Verified gaps (the seed's substance):** the offer prose *undersells* dynamic workflows —
`plan/SKILL.md:253` pitches `cc-workflows-ultracode` as only "broad independent fan-out without
elevated risk," dropping the adversarial-confidence / judge-panel half the contract already grants at
`operator-choice.md:101-104`. The recommender *structurally forbids* the workflow path for contested
work — `team = should_offer_team_execution(...) or needs_consensus` (`lifecycle_state.py:158`) hard-forces
team-execution on any consensus signal. The Workflow tool's own documentation names judge-panel /
adversarial-refutation / perspective-diverse verification as first-class "confidence" purposes — so the
operator's claim ("consensus can be done with workflows") is correct and verifiable. team-execution
today emits a markdown table + tmux protocol, never a runnable `.workflow.js` — so "team-execution
generates scripts" is net-new *and* a category shift. The recorded decision (`DECISIONS.md`
`#operator-choice-framework` + `LEARNINGS.md` 2026-06-13) fixes the team↔workflow line as **governance**
(standing recorded verdict that blocks scanners/deploy vs throwaway confidence), not "review depth" —
any "use workflows for consensus" idea must engage that boundary or be cut.

**Context-libraries:** `infiquetra-context-library` — the `context-fleet-audit` session
(`scripts/context-fleet-audit.workflow.js` authored from `docs/plans/2026-06-20-context-fleet-audit-plan.md`)
is the reference plan→script bridge: EC contracts → agent SPEC preamble verbatim, plan phases →
`phase()`, units → `agent()`, return contracts → per-agent JSON schemas, dependencies → hard barriers,
escalations → boolean throws; the tiering rule "every JUDGMENT clause → Opus; mechanical
census/link/existence → Sonnet/Haiku"; the pilot↔fan-out same-tier invariant; pilot-before-fan-out +
circuit-breaker + ledger-resume safety; and the retro's silent-skip lesson (a fan-out unit's target set
was a *filter* not an enumerated list → a repo got no PR and no error).

**External prior art (Frame 5):** GitHub Actions matrix + reusable workflows; orchestrator
author-graph/runtime-schedule split with per-task tiers as task queues/pools (Temporal/Airflow);
build-graph critical-path scheduling (Make/Bazel/Nx); Nextflow/Snakemake implicit parallelism from I/O
declarations + resource labels + content-hash resume; SQL cost-based per-operator implementation choice;
FJSP tiering=assignment vs ordering=sequencing; military MDMP→OPORD sync matrix + decentralized
execution.

## Topic Axes

1. **Representation & framing** — how the offer describes each backend; conveying workflows' consensus/confidence capability, not just fan-out.
2. **Naming & vocabulary** — the enum + prose labels; the "dynamic workflows" rename and its migration cost.
3. **Defaulting & recommendation** — which backend is pre-selected; the consensus→team-execution reflex vs leaning into workflows.
4. **Plan→workflow authoring** — generating a runnable, model/effort-tiered workflow script from a plan; team-execution as a script generator; the missing bridge.
5. **Cross-host availability & graceful degradation** — the Claude Code-only gate; what "more default" means off-host.

## Ranked Survivors

### 1. Stop underselling dynamic workflows at the /plan offer

Rewrite the `/plan` offer line so it names workflows' *two* real purposes — and lock it with a test.

`plan/SKILL.md:253` sells `cc-workflows-ultracode` as only "broad independent fan-out without elevated
risk," dropping the adversarial-confidence / judge-panel half the contract already states. Rewrite the
offer to name both purposes, reframe the team↔workflow fork as "does the verdict need to **stick**
(block a deploy + persist) or is it throwaway?", and add a drift-guard test asserting offer surfaces
stay a superset of the `operator-choice.md` §3.2 purpose list.

The basis is a direct contradiction between two files in the same plugin — the offer the operator sees
contradicts the contract it cites. The downside is small: prose-only at the offer site, but it must be
applied at every offer surface (`/plan`, and confirm `/work` / `/loop` which defer to the contract)
and the guard test is what stops the under-sell returning on the next rebuild.

| field | value |
|-------|-------|
| basis | `direct:` plan/SKILL.md:253 vs operator-choice.md:101-104 |
| confidence | 88 |
| complexity | Low |
| axis | Representation & framing |
| status | Unexplored |

### 2. Split needs_consensus into gated vs advisory (the keystone)

Make the recommender able to route contested work to a workflow judge-panel — by splitting the signal
along the governance line the contract already draws.

`recommend_execution_backend()` does `team = should_offer_team_execution(...) or needs_consensus`
(`lifecycle_state.py:158`): any consensus signal hard-forces team-execution, so a workflow judge-panel
is never recommended. Split the boolean into `gated_consensus` (must block a merge/deploy + persist as
evidence → team-execution) vs `advisory_consensus` (N independent votes you act on yourself → eligible
for a dynamic-workflow judge-panel).

This is the only way "consensus is achievable with workflows" becomes true in the recommender, and it
engages the recorded governance boundary head-on instead of flattening it (it splits *along* the line,
not across it). The downside is signal-acquisition: saga may not have enough at `/plan` time to tell
"consensus for confidence" from "consensus to gate a deploy" without a new interrogation question —
that design tension is the crux to settle in `/brainstorm`.

| field | value |
|-------|-------|
| basis | `direct:` lifecycle_state.py:158 + operator-choice.md:105-110 |
| confidence | 80 |
| complexity | Med |
| axis | Defaulting & recommendation |
| status | Unexplored |

### 3. Decouple the display label from the stored enum

Satisfy "dynamic workflows" with a display-label map and freeze the wire value — don't migrate the enum.

`operator-choice.md` §1 already declares "prose labels people say out loud are not the contract; only
the enum strings are." So introduce a single display-label map (`cc-workflows-ultracode` → "dynamic
workflows") consumed by every offer surface, and leave the persisted enum value frozen.

The basis is the contract's own stated separation, which no code currently enforces; this is strictly
cheaper than the ~33-site rename + stored-saga migration the literal rename demands, and it codifies a
distinction worth having. The downside is a thin indirection layer and the discipline to keep using the
canonical string in code/tests — and a small naming call (does "dynamic workflows" want to encode
"Claude-Code-only" so the capability gate is legible from the label?).

| field | value |
|-------|-------|
| basis | `direct:` operator-choice.md §1; saga.py:71 |
| confidence | 85 |
| complexity | Low |
| axis | Naming & vocabulary |
| status | Unexplored |

### 4. One execution-spec, two emitters

Have `/plan` author one structured execution-spec and *emit* either a runnable workflow script or the
team-execution markdown protocol from it.

Today `/plan` records only a backend pointer; team-execution emits a `## Team Structure` markdown table
+ a tmux human protocol, never a script. Author one spec (units, tiers, return schemas, barriers,
escalations) and emit a `.workflow.js` for dynamic-workflows (phases→`phase()`, units→`agent()`,
contracts→schemas, deps→barriers, escalations→throws) or the markdown protocol for team-execution —
with the audit-retro's silent-skip guard baked in (every fan-out unit declares an *enumerated* target
list + post-run reconciliation, never a filter).

This synthesizes the operator's "team-execution creates scripts" (S4) and "plan writes the workflow"
(S5) into one move, and it resolves the script-vs-contract fork: the spec is the portable contract, the
`.workflow.js` is one host's loader. The downside is real scope — it's the highest-complexity survivor,
must stay on the right side of saga's "never vendors machinery" boundary (the script is a plan
*artifact* / `orchestration_ref` target), and the generator has to earn trust against the audit run's
authoring lessons (grep≠correctness, mechanized resume, no silent skips).

| field | value |
|-------|-------|
| basis | `direct:` context-fleet-audit plan→script mapping; team-execution/SKILL.md:234; seeds S4+S5 |
| confidence | 70 |
| complexity | High |
| axis | Plan→workflow authoring |
| status | Unexplored |

### 5. Per-agent model + effort tiering as a plan property

Tag each plan unit with `{model, effort}` at authoring time, defaulted by the judgment-vs-mechanical
rule and guarded by the pilot↔fan-out same-tier invariant.

Per-agent model AND effort are settable when authoring a workflow; make them a per-unit annotation on
the *plan*, defaulted by the audit-proven rule ("every JUDGMENT clause → Opus; mechanical
census/link/existence → Sonnet/Haiku; sampling → Sonnet") and enforced with the pilot↔fan-out same-tier
invariant as a generation-time assertion (a mis-tiered pilot is a lying oracle).

Tiering is a property of the unit's cognitive demand — which the plan already characterizes — so
deciding it once at plan-time (where judgment-vs-mechanical is legible) beats hand-setting it later in a
script nobody reviews, and it compounds with the in-flight agent-frontmatter tiering work. The downside
is the classifier needs a default policy and an inspectable per-unit `tier_reason`, and the
assignment (tier) vs sequencing (barriers) decisions should stay separable (FJSP) so a tiering pass
can't silently violate the invariant.

| field | value |
|-------|-------|
| basis | `direct:` context-fleet-audit KTD10 tiering rule + pilot/fan-out invariant; seed S6 |
| confidence | 78 |
| complexity | Med |
| axis | Plan→workflow authoring |
| status | Unexplored |

### 6. Capability-portable degradation

Make every plan carry a runnable baseline and treat the workflow as an enhancement layer that
re-checks capability on resume.

The capability gate is offer-time only, but an ultracode-pointer saga can be *resumed* off-host
(redis-channel, other runners) where the workflow can never run, with no re-check. Carry a runnable
inline/serial baseline in every plan, apply the dynamic-workflow as an enhancement layer on a capable
host, and on off-host resume re-check capability, emit a one-line downgrade note, and recompile only the
orchestration tier down to team-execution/inline (keeping unit specs + tiers), recording the downgrade
pointer.

The basis is first-principles: the gate is specified at the offer (`operator-choice.md:129-141`) but the
enum value persists (`saga.py:71`) and sagas resume cross-host, so a choice valid at author-time goes
stale at resume-time with no equivalent check. The downside is that "always carry a baseline" is extra
authoring work, and the recompile-down path needs the one-spec foundation (S4) to be clean.

| field | value |
|-------|-------|
| basis | `reasoned:` offer-time gate vs persisted enum + cross-host resume; `external:` web progressive enhancement |
| confidence | 68 |
| complexity | Med-High |
| axis | Cross-host availability & graceful degradation |
| status | Unexplored |

### 7. Measure before re-defaulting

Instrument recorded backend choices and surface the override-rate before re-weighting any default.

"Lean into workflows more" is currently unmeasured — we don't know how often operators override the
recommendation, in which direction, or whether declined workflows were later regretted. saga already
records `orchestration_mode` per work-thread; add a lightweight `/retro` or `/optimize` pass that reads
recorded choice-vs-recommendation and surfaces the override-rate (plus over/under-tiering and
budget-exhaustion flags as a tier-policy feedback loop).

The basis is direct: every saga writer already records the mode (`operator-choice.md` §6), and the
global directive forbids behavior claims without measurement — so "workflows should be the default" is
exactly the kind of assertion to measure first. The downside is it's a counterweight, not a feature: it
slows the gratifying default-flip, and it only pays off once enough runs are recorded to be
representative.

| field | value |
|-------|-------|
| basis | `direct:` operator-choice.md §6 (writers record the mode); global CLAUDE.md no-unmeasured-claims |
| confidence | 72 |
| complexity | Med |
| axis | Defaulting & recommendation |
| status | Unexplored |

## Did not survive (revivable)

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Exception-driven offer | Auto-select when signals are unambiguous; interrupt only on genuinely contested (§3.3 both-fire) cases | Strong, but widens scope to the whole offer-cadence beyond the workflow-representation focus; revisit after S2 lands | rejected |
| R2 | Two-axis execution vocabulary | Name the choice as orchestration{workflow\|human\|serial} × verdict{standing\|throwaway}; legacy enum values become points in that 2D space | Ambitious reframe, brainstorm-grade; the actionable nucleus (make governance legible) is already in S1+S3 | rejected |
| R3 | Enum as a continuous spectrum | inline = a 1-agent workflow; the three enum values are one axis (agent count × verification depth) sampled at 3 points | Elegant mental model, no distinct actionable move beyond S1/S3; revisit if the enum is redesigned | rejected |
| R4 | Pure-contract pole | team-execution keeps the markdown contract and never emits scripts; "compile to .workflow.js" is just one runner's loader | A genuine design fork that S4 resolves in favor of both; preserved if the operator prefers contract-only | rejected |
| R5 | Workflow-template library | A library of parameterized templates (pilot-then-fan-out, judge-panel, discover-per-target) + matrix fan-out + content-hash resume | Implementation tactics for S4, below the ideate altitude; promote into S4's /brainstorm or /plan | rejected |
| R6 | Route-to-capable-host | Off-host, ship the compiled workflow as a portable payload to a host that can run it, rather than degrade | Speculative (needs a remote runner); S6's downgrade path is the pragmatic near-term | rejected |
| R7 | Confidence-target knob | Expose a budget-bounded "spend up to N tokens to reach confidence C" knob at the offer instead of an agent-count knob | A feature on top of S1; nice but secondary; revisit when S1's representation lands | rejected |

Rejection summary: ~52 raw candidates → 7 survivors. Biggest cuts: (a) every full-rename variant,
dominated by S3's cheaper label-decouple; (b) ~6 authoring tactics folded into S4 as "how"; (c) the
assumption-break flips (zero-choice, off-host-primary, continuous-spectrum) preserved as R's but not
promoted — mental models or speculative infra, not near-term moves. All five axes carry ≥1 survivor
(defaulting and authoring carry 2 each — where the operator's energy and the core logic + build live).
No zero-survivor axis.

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | S1 — the offer doesn't represent workflows' consensus capability | survived as #1 (validated against the Workflow-tool docs + the contract) |
| user-seed | Phase 0 | S2 — rename `cc-workflows-ultracode` → "dynamic workflows" | challenged → survived as #3 (decouple the display label; don't migrate the enum) |
| user-seed | Phase 0 | S3 — lean into workflows more; team-create more specialized | split → survived as #2 (recommender) + #7 (measure first) + #6 (portability) |
| user-seed | Phase 0 | S4 — team-execution should generate workflow scripts from a plan | synthesized → survived as #4 (one-spec-two-emitters) |
| user-seed | Phase 0 | S5 — /plan suggests + writes the workflow with model/effort | synthesized → survived as #4 |
| user-seed | Phase 0 | S6 — per-agent model AND effort are settable when authoring | survived as #5 (tiering as a plan property) |
| frame-agent | Phase 2 | drift-guard test on offer surfaces (frame 3) | folded into #1 |
| frame-agent | Phase 2 | silent-skip enumerated-target guard (frame 2) | folded into #4 |
| frame-agent | Phase 2 | measure-the-override-rate (frame 4, leverage) | survived as #7 |
