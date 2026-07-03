---
title: readonly-verifier roster gap — verified reload path, documented fallback ladder, registration drift guard
type: fix
status: active
date: 2026-07-03
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/325
---

# readonly-verifier roster gap — verified reload path, documented fallback ladder, registration drift guard

Issue #325 reports that `saga:readonly-verifier` — mandated by `CLAUDE.md` and
`plugins/saga/references/sandbox-spawn-sites.md` for every ad-hoc verify/review-class spawn — was
not resolvable in a running session (`Agent type 'saga:readonly-verifier' not found`), discovered
during `/saga:work` on #291. This plan verifies the issue's claims (all confirmed; the immediate
gap is already resolved by plugin reload), then delivers the two durable fixes the issue proposes:
a documented fallback ladder for when the agent is unavailable, and a registration drift guard.

## Issue verification (operator-requested)

Every claim in #325 was checked against a direct current source on 2026-07-03:

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Agent def exists with valid frontmatter | CONFIRMED | `plugins/saga/agents/readonly-verifier.md:1-16` — `name: readonly-verifier`, `model: sonnet`, `tools: Bash, Read, Grep, Glob` |
| 2 | Sibling `mechanical-executor` registered, same dir | CONFIRMED | Both in `plugins/saga/agents/`; both resolvable in current session roster |
| 3 | Age gap: readonly-verifier 2026-07-02, mechanical-executor 2026-06-21 | CONFIRMED | `git log --follow`: `697fff1` 2026-07-02 (#287 via #320) vs `9bdf363` 2026-06-21 |
| 4 | CLAUDE.md + sandbox-spawn-sites.md mandate the agent | CONFIRMED | `CLAUDE.md:9`; `plugins/saga/references/sandbox-spawn-sites.md:44-55` (ad-hoc spawn rule) |
| 5 | No documented fallback exists | CONFIRMED | `grep -rn "fallback\|unavailable"` over both files: zero hits |
| 6 | Root cause is a stale plugin/agent roster, not a repo defect | CONFIRMED | Live probe this session: `Agent(subagent_type: saga:readonly-verifier, isolation: worktree)` spawned successfully, ran in a disposable worktree, returned a structured `{refuted, upheld}` verdict |
| 7 | Corroboration of the original failure | CONFIRMED | `.claude/saga/sagas/issue-291` tick records follow-up "register saga:readonly-verifier agent (roster gap)" |

**Proposed-fix #1 ("verify the reload path") is answered at plan time:** the current session's
roster lists the agent and a live spawn succeeds end-to-end. The failure was environmental
staleness (a session whose loaded plugin predated #320's merge), not a registration bug. No code
change exists for fix #1; this table is the evidence the issue can cite on close.

**Refinement to proposed-fix #3:** CI cannot observe a running session's agent roster, so a drift
guard cannot assert runtime registration. It CAN pin every repo-side precondition of
discoverability — and one already exists: `tests/test_saga_plugin.py:1452-1459` pins the
`agents/` dir set to exactly `{mechanical-executor, readonly-verifier}`. The gap is frontmatter
validity, name↔reference cross-checks, and fallback-doc presence (U2).

## Requirements

- R1. Reload-path verification is recorded as evidence (the table above); no code change for
  issue proposed-fix #1.
- R2. `plugins/saga/references/sandbox-spawn-sites.md` gains a "Fallback when
  `saga:readonly-verifier` is unavailable" section defining a two-step ladder (KTD1), each step
  stating explicitly what is preserved and what is lost.
- R3. `CLAUDE.md`'s ad-hoc spawn rule gains only a one-line fallback pointer into that section —
  the ladder is single-sourced in sandbox-spawn-sites.md (KTD3), matching the existing
  pointer pattern (`sandbox-spawn-sites.md:54-55`).
- R4. A drift-guard test asserts static discoverability: (a) every `plugins/saga/agents/*.md` has
  parseable YAML frontmatter whose `name:` matches the file stem; (b)
  `execution_spec.py:93` `READONLY_VERIFIER_AGENT_TYPE` equals `"saga:" + <frontmatter name>`;
  (c) every **spawn-context** `saga:<name>` reference — a line carrying `subagent_type` or
  `agentType` — across `plugins/saga/` and repo-root `CLAUDE.md` resolves to an existing
  `plugins/saga/agents/<name>.md`; (d) the R2 fallback section exists. The (c) pattern is
  deliberately NOT a bare `saga:<name>` grep: skills share the `saga:` namespace (`/saga:work`,
  `saga:plan`), so an unscoped pattern false-positives the day any doc under `plugins/saga/`
  mentions a skill by its namespaced name. Bare unprefixed agent mentions (e.g.
  `mechanical-executor` at `plugins/saga/skills/work/references/execution-strategy.md:80`) are
  out of the guard's scope by design — only namespaced spawn references can hard-fail a session.
- R5. Release surfaces updated in the same PR per repo policy:
  `plugins/saga/.claude-plugin/plugin.json` (0.49.1 → 0.49.2), `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md`.
- R6. Engineering journal captured in the shipping commit: `LEARNINGS.md` entry (stale-roster
  mechanism — evidence/mechanism/generalizable rule) and `DECISIONS.md` entry for KTD1/KTD2.

## Key Technical Decisions

**KTD1 — Fallback is an Explore-first ladder, not `general-purpose`-only:** step 1 is the built-in
`Explore` agent + `isolation: "worktree"` + the verifier prompt — Explore structurally lacks
Edit/Write/NotebookEdit while keeping Bash, so the `mutation_policy: read-only` axis survives by
tool omission, which a prose instruction to `general-purpose` cannot guarantee. Step 2 (only if
Explore is also absent) is `general-purpose` + worktree + explicit read-only prose instruction —
the issue's proposal, demoted to last resort. The saga plugin already depends on Explore for
fan-out grounding, so no new dependency is introduced. *Operator-confirmed at plan time.*

**KTD2 — Drift guard asserts static discoverability, not runtime registration:** the runtime
roster is unobservable from CI; the environmental-staleness failure class is untestable in-repo.
The guard instead pins every repo-side precondition (frontmatter parses, names match, references
resolve, fallback documented) so the only remaining failure mode is the environmental one the
fallback ladder now degrades gracefully.

**KTD3 — CLAUDE.md carries a pointer, not the ladder:** single source of truth in
sandbox-spawn-sites.md; CLAUDE.md stays lean and cannot drift from the reference doc.

**KTD4 — `execution_spec.py`'s emitter stays fail-loud, no fallback there:** spec-driven workflow
runs are deliberate, operator-visible dispatches; a hard `agentType` resolution error at run start
is the correct behavior (reload and re-run) versus silently downgrading the sandbox of an entire
verify panel. The fallback ladder applies to ad-hoc/skill Agent-tool spawns only.

## Implementation Units

### U1 — Fallback ladder documentation

**Files:** `plugins/saga/references/sandbox-spawn-sites.md`, `CLAUDE.md`

**Change:** add a "Fallback when `saga:readonly-verifier` is unavailable" section to
sandbox-spawn-sites.md (after the ad-hoc spawn rule) with the KTD1 two-step ladder, each step
listing preserved vs lost properties; add a one-line pointer to `CLAUDE.md:9`'s spawn rule.
The section states the rung-selection rule explicitly: a rung applies only when its agent type is
present in the current session roster (agent rosters change — the doc must not assume `Explore`
exists any more than it assumed `saga:readonly-verifier` did); `general-purpose` is the terminal
rung because it is the harness default type.

**Test expectation:** covered by U2 assertion (d) — the guard fails if the section is absent or
the CLAUDE.md pointer is dropped.

### U2 — Registration drift guard

**Files:** `tests/test_agent_registration_drift.py` (new, focused-file pattern per
`tests/test_agent_tiering.py`)

**Change:** implement R4's four assertions as helper functions that accept path/content injection
so negative cases run against synthetic content, not repo mutation. Reuse the established
frontmatter-parsing pattern from `tests/test_agent_tiering.py:18` (`_parse_frontmatter`) rather
than introducing a new parser (`pyyaml` is available but the hand-rolled top-level-scalar parser
is the repo convention for agent files).

**Test scenarios** (all in the new file):
- Frontmatter of both `plugins/saga/agents/*.md` parses and `name:` matches file stem (positive).
- Synthetic agent content with `name:` ≠ stem → helper flags drift (negative).
- `READONLY_VERIFIER_AGENT_TYPE` cross-check passes against the real tree (positive); synthetic
  mismatch → flagged (negative).
- Every spawn-context `saga:<name>` reference (lines carrying `subagent_type`/`agentType`) in
  `plugins/saga/**` and `CLAUDE.md` resolves to `plugins/saga/agents/<name>.md` (positive);
  synthetic dangling spawn-context reference → flagged (negative); a skill-name mention like
  `/saga:work` in prose is NOT flagged (namespace false-positive regression case).
- sandbox-spawn-sites.md contains the fallback section heading and CLAUDE.md contains the pointer.

**Depends on:** U1 (assertion (d) targets U1's section).

### U3 — Release surfaces + journal

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `docs/engineering-journal/LEARNINGS.md`,
`docs/engineering-journal/DECISIONS.md`

**Change:** bump saga 0.49.1 → 0.49.2 (or the next free patch version if another PR ships first)
in both registries; CHANGELOG entry summarizing the
verified diagnosis + fallback + guard; LEARNINGS entry (stale plugin roster: a just-merged agent
is invisible to sessions whose plugin loaded pre-merge — evidence #325/#291, generalizable rule:
"after merging a new agent/skill, reload the plugin before relying on it; mandates over runtime
rosters need a documented degrade path"); DECISIONS entry anchoring KTD1/KTD2 with revisit-when
(revisit if the harness ever exposes the roster to hooks/CI, enabling a true runtime guard).

**Test expectation:** existing plugin-metadata drift guards; `uv run pytest` green.

**Depends on:** U1, U2.

## Scope Boundaries

**Out of scope:**
- Any change to `execution_spec.py`'s verifier emission (KTD4 — stays fail-loud, unconditional
  `saga:readonly-verifier`).
- Re-visiting out-of-scope spawn sites in `sandbox-spawn-sites.md` (team-execution registry,
  agy delegated-build loop, mechanical-executor) — their classifications are settled decisions.
- Runtime enforcement of the fallback ladder (hooks cannot read the agent roster today).

**Deferred follow-up work (distinct from non-goals):**
- A SessionStart roster-staleness warning comparing installed plugin version against the repo's
  `plugin.json` when CWD is a plugin-source repo — plausible sibling of
  `plugins/saga/hooks/stale_main_session_hook.py`, but a separate mechanism investigation; file
  as its own issue if the staleness class recurs.
