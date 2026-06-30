---
date: 2026-06-30
topic: antigravity-teammate-plugin
focus: narrow implementation-shape ideation for a new Infiquetra Claude Code plugin that provides Antigravity-backed teammates
scope: narrow
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Antigravity Teammate Plugin

## Grounding Context

**Repo:** `infiquetra-claude-plugins` packages Claude Code plugins under `plugins/`, with root marketplace metadata, plugin manifests, commands, agents, skills, changelogs, and repo-root tests. Plugin behavior, schema, command, prompt, or guidance changes must update release surfaces and drift tests together.

**Context-libraries:** None consulted; this is a repo-local plugin design topic.

**User-named references:** [docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md) is authoritative where it names locked constraints: new plugin, write-capable v1, preconfigured `agy-coder` and `agy-reviewer`, shared wrapper/evidence schema, and a quick command as secondary surface.

**Journal and delegation docs:** External-agent delegation evidence shows Claude-clone fallback with zero `agy` call, `--background` zero-byte hangs, named-runner liveness quirks, wander, rogue commit/push, test-gaming, overclaim, silent no-op, and orphan late writes. The durable rule is authority/provenance first: read broad, write narrow, make the orchestrator sole committer, and re-derive truth from evidence.

## Topic Axes

- Agent/Command Affordance
- Wrapper Liveness & Provenance
- Write Boundary & Apply Policy
- Evidence & Verification Schema
- Harness Proof & Testability

## Ranked Survivors

### 1. Delegation Envelope Contract

Make a structured delegation envelope the internal primitive for both preconfigured teammates and `/agy:delegate`.

The envelope carries `role`, `mode`, `lens`, `model`, `write_set`, `apply_policy`, `evidence_level`, checks, timeout, and provenance requirements. `agy-coder`, `agy-reviewer`, and the quick command become affordances that fill or validate the same envelope instead of separate flows.

This directly targets the top failure: Claude misusing the plugin because the surface invites the wrong action. The downside is that the schema becomes the real product API and must be versioned/tested from day one.

| field | value |
|-------|-------|
| basis | direct: seed locked constraints require `agy-coder`, `agy-reviewer`, quick command, and shared wrapper/evidence schema ([seed](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md:586)) |
| confidence | 93 |
| complexity | Med |
| axis | Agent/Command Affordance |
| status | Unexplored |

### 2. Patch Inbox Importer With Write-Set Capability

Route write-capable output through a managed patch inbox/importer instead of letting Antigravity mutate the live checkout by default.

The explicit write-set becomes a capability token: compiled to a matcher, hashed into the evidence bundle, and required for `auto-if-clean`. The delegate may read broadly and write in the scratch boundary, but only in-scope patches cross into the live tree after path, git-state, and verification gates.

This preserves write-capable v1 while containing wander, rogue git behavior, late writes, and over-broad diffs. The downside is implementation weight: patch import, untracked files, binary diffs, and conflict reporting must be handled carefully.

| field | value |
|-------|-------|
| basis | direct: seed requires write-capable v1 and local evidence, while blueprint requires read broad/write narrow and `PLAN_GAP` for out-of-scope needs ([seed](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md:588), [blueprint](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/external-agent-delegation/blueprint.md:34)) |
| confidence | 88 |
| complexity | High |
| axis | Write Boundary & Apply Policy |
| status | Unexplored |

### 3. Run Lease And Provenance Receipt

Treat every `agy` invocation as a leased process with a preflight receipt and liveness proof.

Before sending or trusting task output, the wrapper records the resolved `agy` binary, argv, cwd, pid, start time, transcript path, heartbeat/transcript growth, timeout class, and shutdown proof. The run can only return `success` or `applied` if the receipt links to a real `agy` process and non-empty transcript evidence.

This turns “did Antigravity actually run?” into a file-backed verdict rather than a transcript archaeology exercise. The downside is platform/process fragility: pid tracking and transcript heartbeat behavior must be proven on the user’s actual Claude Code/Antigravity setup.

| field | value |
|-------|-------|
| basis | direct: delegation docs distinguish real agy from Claude-clone fallback by actual `agy --model` Bash call, and fork notes record the 21-minute zero-byte hang ([README](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/external-agent-delegation/README.md:15), [fork decision](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/external-agent-delegation/agy-plugin-fork-decision.md:44)) |
| confidence | 90 |
| complexity | Med |
| axis | Wrapper Liveness & Provenance |
| status | Unexplored |

### 4. Evidence Bundle Status Machine

Make the local evidence bundle the authoritative return value, with chat output derived from it.

Every run writes the full bundle: original prompt, rendered `agy` prompt, sanitized command shape, process result, transcript path, changed paths, git proof, verification commands, real-agy-vs-fallback verdict, and apply decision. Claude receives `full`, `summary`, or `minimal` projection, but the durable bundle stays complete.

This prevents confident prose from becoming the interface and gives downstream team-execution or ultracode workflows a stable machine-readable contract. The downside is schema discipline: status enums and evidence projections must be kept backward-compatible.

| field | value |
|-------|-------|
| basis | direct: seed requires command, transcript, changed paths, git proof, verification commands, and explicit real-agy verdict ([seed](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md:593)) |
| confidence | 86 |
| complexity | Med |
| axis | Evidence & Verification Schema |
| status | Unexplored |

### 5. Thin Bridge Agent Pack

Ship `agy-coder` and `agy-reviewer` as preconfigured bridge agents, not general workers with a suggestion to use `agy`.

The agents should have minimal tools and instructions that forbid solving directly: receive the Claude/team prompt, build the delegation envelope, call the wrapper, and return the evidence projection. `agy-reviewer` defaults to adversarial with explicit lenses; `agy-coder` fills write-capable envelopes and never edits via Claude tools.

This is the main affordance-level defense against misuse. The downside is a hard feasibility dependency: Claude Code must actually allow plugin-packaged agents to be constrained enough, and live transcript proof must verify they do not use Read/Edit/Write as the worker.

| field | value |
|-------|-------|
| basis | direct: seed primary surface is preconfigured Antigravity-backed teammates, not runtime flags ([seed](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md:590)) |
| confidence | 82 |
| complexity | Med |
| axis | Agent/Command Affordance |
| status | Unexplored |

### 6. Agy-Coder Task Packet Library

Package a strong Gemini-oriented coder protocol as reusable prompt templates layered over the hard envelope.

The template should combine expert software engineer framing with the existing task packet: write-set closed, read broad/write narrow, `PLAN_GAP`, `TEST_CONFLICT`, `PATH_MISSING`, no git, exact verification commands, and run report. This makes `agy-coder` more than a transport shim while keeping persona guidance subordinate to enforceable wrapper checks.

This addresses the observed Flash flakiness without pretending prompt quality replaces authority control. The downside is prompt maintenance: every template change is user-facing guidance and must update version/changelog/drift tests.

| field | value |
|-------|-------|
| basis | direct: blueprint says the delegate may read/search the repo but must write only declared allow-set and escalate out-of-scope needs via `PLAN_GAP` ([blueprint](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/external-agent-delegation/blueprint.md:34)) |
| confidence | 78 |
| complexity | Med |
| axis | Evidence & Verification Schema |
| status | Unexplored |

### 7. Harness Proof Matrix

Make v1’s proof a three-layer matrix: static repo tests, direct wrapper tests, and live Claude Code harness runs.

Static tests cover manifest/marketplace/changelog/schema drift. Wrapper tests prove long-run handling, work boundary, patch import, statuses, and evidence bundles without Claude. Live harness tests run one tiny `agy-reviewer` and one tiny `agy-coder` fixture, then audit transcripts to prove the packaged agents called the wrapper/`agy` and did not solve with Claude tools.

This prevents the plugin from looking correct in source while failing at the actual Claude-to-Antigravity boundary. The downside is operational: live Claude Code harness proof may be slower and partially manual until the repo has a stable smoke path.

| field | value |
|-------|-------|
| basis | direct: seed requires reviewer and coder live Claude harness proof plus transcript audit before trusting the agent surface ([seed](/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/docs/ideation/2026-06-29-antigravity-plugin-socratic-seeds.md:500)) |
| confidence | 91 |
| complexity | High |
| axis | Harness Proof & Testability |
| status | Unexplored |

## Did not survive (revivable)

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Fork existing agy plugin | Patch `antigravity-cc/agy` instead of creating a new plugin. | Violates locked seed direction and inherits ambiguous command surface. | rejected |
| R2 | Direct live-tree write default | Let `agy` write directly into the active checkout. | Too risky for v1 default; late writes and rogue git are harder to contain. | rejected |
| R3 | Reviewer agent zoo | Ship separate named agents for each review lens. | Duplicates stronger single reviewer with lens field; noisy surface invites misuse. | rejected |
| R4 | Stateful conversations by default | Preserve `agy --conversation` identity per teammate. | Conflicts with fresh-by-default seed and increases liveness/recovery risk. | rejected |
| R5 | Raw runner quick command | Expose a low-level runner for convenience/debug. | Recreates current misuse class; keep raw runner internal only. | rejected |
| R6 | Provider-neutral v1 | Build a Codex+Antigravity delegate-agent platform first. | Prior background idea, but too broad and conflicts with Antigravity teammate focus. | rejected |
| R7 | Read-only-first v1 | Ship reviewer/explorer only, defer write-capable coder. | Directly conflicts with locked v1 requirement for write-capable delegation. | rejected |

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | New plugin, write-capable v1, `agy-coder` and `agy-reviewer`, quick command through same wrapper. | Survived as #1, #5, #7. |
| user-seed | Phase 0 | No explicit write-set means no automatic live-tree mutation. | Survived as #2. |
| user-seed | Phase 0 | Fresh `agy` invocation by default; stateful only after proof. | Cut stateful default to R4; informs #3. |
| user-seed | Phase 0 | Configurable evidence levels with full local bundle. | Survived as #4. |
| frame-agent | Phase 2 | Run ticket / provenance receipt / transcript heartbeat. | Merged into #3. |
| frame-agent | Phase 2 | Patch inbox, quarantine worktree, write-set manifest. | Merged into #2. |
| frame-agent | Phase 2 | Tiny live reviewer/coder harness fixtures. | Survived as #7. |
