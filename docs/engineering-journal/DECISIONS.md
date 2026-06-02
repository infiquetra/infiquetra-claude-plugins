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

**Refs.** `plugins/infiquetra-loop/`, `plugins/infiquetra-deploy/`,
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
- *Add the router as a 4th plugin inside `infiquetra/hermes-extensions`.* Considered seriously after `hermes-extensions` was identified as the canonical external-plugin pattern. Rejected per user preference for independent versioning. The router's expected LoC (~1k+) justifies its own home.
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
