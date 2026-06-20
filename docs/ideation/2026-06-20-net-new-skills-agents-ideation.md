---
date: 2026-06-20
topic: net-new-skills-agents
focus: offload recurring mechanical work off the high-context main session onto the right tier (skills, hooks, cheap-tier subagents)
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Net-New Skills & Cheap-Tier Subagents (Track 1)

This is the **Track 1** run set up in `2026-06-19-plugin-grooming-next-steps.md`: generate
net-new, well-triggered skills and *justified* cheap-tier subagents, grounded in how the operator
actually works — mined from commit history and `~/.claude` transcripts for recurring **work-patterns**,
not plugin fire-counts. Companion to the portfolio-grooming run (`2026-06-19-plugin-ecosystem-grooming-ideation.md`);
this run deliberately excludes that doc's parked items, `/retro` Phase 5a's new-skill detection, and
anything duplicating an installed external tool.

## Headline reframe (the load-bearing finding)

The seed framing was "agents that pick a cheaper model." The grounding contradicts it in a useful way:
**the highest-value offloads are deterministic HOOKS that invoke no model at all — and the repo has
zero hooks today.** Four of the top five mechanical patterns (gate run, JSON guard, stale-main, SHA
capture) are pure determinism flooding the *most expensive* tokens for a binary answer. A haiku
subagent is still an LLM call; a hook is free and can't forget to fire.

So the answer to "my agent setup is lacking" is **not more agents**. It is: a handful of hooks, **exactly
one** justified cheap-tier agent (a reusable substrate, not a per-chore zoo), and a written tiering
doctrine where there is currently none. The single new agent file is justified under the binding
convention twice over — it pins a cheaper tier (haiku) **and** narrows tools (Bash-only).

## Grounding Context

**Repo:** `infiquetra-claude-plugins`, a Claude Code plugin marketplace (17 plugins, imminent 17→7 cut).
Flagship `saga` = 17 lifecycle slash-commands. Strong journal discipline (LEARNINGS/DECISIONS/QUEUED/ARCHIVE,
same-commit). Conventional commits + a per-PR artifact ladder. Solo + Claude development ("it's just me and
you... always merge it"). Key reusable substrate already present: `validate_plugins.py` and
`marketplace/validator/validate.py` (the gate definitions CI calls), and `handoff_envelope.py` `SOURCE_DIRS`
(the phase→`docs/<phase>/` path map). **No hooks exist anywhere** — `.claude/settings.local.json` is
permissions-only, so every hook proposal is greenfield.

**Binding conventions (constraints — an idea violating these was cut):**
- No bespoke domain agents on the default model. No `agents/` dir → generic Explore/Task agents. An agent
  earns a file ONLY when it pins a cheaper tier or narrower tools. Custom `agents/*.md` were rejected twice
  (qa + resume rebuilds). The existing default-model agent files are scheduled for deletion.
- Subagents are invoked via the Agent tool, NOT auto-loaded — an `agents/*.md` file does not auto-trigger.
  Reliable triggering = a SKILL (frontmatter) or explicit dispatch. "More agents" ≠ "more triggering."
- Don't duplicate installed tools: `commit-commands` (already does git commit/push/PR-open — the overlap that
  reshaped SEED 1), `agy`, `codex`, `compound-engineering` + `superpowers` (upstream saga sources),
  `langfuse-observability` (already traces every session: tool calls + tokens + skill tags).
- Model-tiering has ZERO journal coverage; the operator hand-manages via `/model` (28×), `/effort` (113×),
  `/fast`, `/compact`.

**Measured work-patterns (the `direct:` basis), ranked by frequency × mechanical-ness × inline context-cost:**
pre-push quality gate (pytest 614, uv run 1019, ruff 190, mypy 88 — floods context for a binary verdict);
git→PR→squash-merge plumbing (147 squash-merges; runs in the final ~17% of ≥1500-line sessions, the priciest
tokens); marketplace.json edit + validate guard (95 edits; recurring double-`]` corruption); version-bump
triad (plugin.json + CHANGELOG + marketplace.json agree; 58/300 commits); SHA-fill follow-up (~1:1 with feature
PRs; operator burned blind-filling, drift caught by reading files); stale-main / worktree guard (burned 2
builds; detection 100% mechanical); chore pin-bump churn (15× identical, in sibling repos). Flagged
NON-candidates: the Read→Edit→pytest build loop (real reasoning) and Explore/general-purpose dispatch (already
the good offload pattern).

**Journal learnings consulted:** `workflow_structuredoutput_budget` (cheap-tier schema fan-out fails from
budget exhaustion, not rate limits — cap output, mandatory explicit emit, skim-not-read, batch concurrency);
"grep shipped siblings for a convention before adding a structural first"; "machine-parseable is a hypothesis —
grep for the parser"; dead-wiring (a routed output is dead unless it lands in the consumer's real input shape).

**Context-libraries:** None consulted — the topic is internal to this repo.

## Topic Axes

- A. Git & release plumbing (commit/PR/merge, ff-main, version triad, SHA-fill)
- B. Quality gates & validation runs (pre-push lint/type/test/security, marketplace/JSON validation)
- C. Knowledge & artifact scaffolding (journal-omission nudge, lifecycle artifact boilerplate, commit-subject templating)
- D. State-truth & safety guards (stale-main, verify-before-asserting, worktree preflight)
- E. Tiering & dispatch mechanism (the meta-infrastructure that routes work to a cheaper tier / separate context)

## Ranked Survivors

### 1. marketplace.json validation hook (kill the double-`]` bug class)

A deterministic `PostToolUse` / pre-commit hook that runs `python3 -m json.tool` (+ a bracket-count assertion)
on any edit to `.claude-plugin/marketplace.json` or a `plugin.json`, blocking on parse failure with the offending
line.

MEMORY.md carries a hand-written warning that this corruption "has happened multiple times" — a remembered rule
is a paper guard, and a guard you can forget isn't one. A structural validator (better: a small `marketplace_add.py`
that mutates the JSON object model instead of hand-appending) makes the corruption *unrepresentable*.

Downside: a hook harness is net-new plumbing, and an over-eager matcher could nag on unrelated JSON edits.

| field | value |
|-------|-------|
| basis | direct: 95 marketplace edits; MEMORY.md "happened multiple times"; `marketplace/validator/validate.py` exists |
| confidence | 92 |
| complexity | Low |
| axis | B |
| status | Unexplored |

### 2. Stale-main preflight guard (SessionStart hook)

A `SessionStart` (and post-merge) hook that runs `git fetch` + `git rev-list --count main..origin/main` and emits
one loud line — "local main is N behind origin; do NOT trust the tree" — before the session reasons, auto-fast-forwarding
when main is clean.

This exact stale-tree condition burned two real builds (the `/optimize` Explore agents read a stale checkout and
concluded `/spec` hadn't shipped). Detection is 100% mechanical; the fix is moving the check *upstream* of model
reasoning, so the wrong premise never loads.

Downside: bg-worktree sessions complicate "what is main here," so the guard must understand worktrees or it will
false-alarm.

| field | value |
|-------|-------|
| basis | direct: "burned 2 builds"; MEMORY.md `#shipped-on-origin-not-in-stale-local-tree` |
| confidence | 90 |
| complexity | Low |
| axis | D |
| status | Unexplored |

### 3. Pre-push gate runner — one definition, report-by-exception

Lift the gate (`ruff check` · `ruff format --check` · `mypy` · `pytest` · `bandit` · the two validators) into **one
manifest** that CI *and* a local pre-push hook both read, and have the runner return only `PASS` or the failing lines —
never the green flood. (This is SEED 2.)

The aviation-checklist insight: a clean checklist reports "all green," not every nominal reading — so the
multi-hundred-line pytest/mypy dump should never enter main context. The single-source insight: CI already lists these
commands inline, so any *second* local list silently drifts; one definition means local-green *is* CI-green (the
`reference_ci_gates` memory is exactly this drift biting).

Downside: `pytest` in a blocking hook can be slow; you may want it push-time only, not every turn.

| field | value |
|-------|-------|
| basis | direct: #1 ranked pattern (pytest 614, uv run 1019); CI YAML duplicates the command list |
| confidence | 85 |
| complexity | Med |
| axis | B |
| status | Unexplored |

### 4. `mechanical-handoff` dispatch substrate (the one justified agent)

A single haiku, **Bash-only** subagent behind a stable envelope (`{op, args}` → `{ok, result, evidence_tail}`), where
`op` ∈ {run-gate, commit, version-bump, sha-stamp}. One agent file, many callers — not a new agent per chore. (This is
SEED 1, generalized.)

The frames challenged the original "git agent": `commit-commands` already owns the plumbing, so a standalone version
would duplicate it — but a *separate-context* executor fixes the real pain (the dance running on the final 17% of a
1500-line session's tokens), and its `commit` op can *delegate to* commit-commands' plumbing rather than reimplement.
It earns its file under the convention twice over (cheaper tier AND narrowest tools). The `evidence_tail` cap bakes in
the `workflow_structuredoutput_budget` lesson structurally — the output shape IS the parent's input shape, satisfying
the dead-wiring rule by construction.

Downside: it is the most design-judgment of the set, and an all-haiku committer writes mushy commit messages (the
"tier by judgment, not phase" catch, R4) — so the message step may need a brief sonnet read, not haiku.

| field | value |
|-------|-------|
| basis | direct: SEED 1 + commit-at-high-context; `handoff_envelope.py` precedent for the envelope shape |
| confidence | 72 |
| complexity | Med-High |
| axis | E |
| status | Unexplored |

### 5. Tiering policy + dispatch doctrine

Write the **first** `DECISIONS.md` entry on model tiering — a decision table mapping task-class → tier (mechanical →
haiku subagent/hook; routine edit-test → sonnet; architecture/debug/first-time → opus high-effort) — and a thin skill
the offloaders consult.

Tiering has zero journal coverage today; the operator hand-manages it with 28× `/model` + 113× `/effort` toggles.
Those 141 manual flips are the symptom of a missing policy layer. This is what makes survivors 1–8 land on the right
tier by default instead of by memory — and it is the cheapest to write (a doctrine, not code).

Downside: a policy nobody enforces decays; it needs a real consumer (the substrate in #4) to stay honest, not just a doc.

| field | value |
|-------|-------|
| basis | direct: tiering ZERO journal coverage; /model 28×, /effort 113× |
| confidence | 78 |
| complexity | Low-Med |
| axis | E |
| status | Unexplored |

### 6. Version-triad bump + consistency guard

A deterministic `bump_version.py <plugin> <semver>` that writes `plugin.json` + prepends `CHANGELOG.md` + syncs the
`marketplace.json` entry in one pass, plus a pre-push guard that blocks when the three disagree.

Three sources of truth that must agree by hand is a drift generator — it appears in 58 of 300 commits, all mechanical.
Bump once, propagate; never let them diverge.

Downside: CHANGELOG *prose* is light judgment, so the script stubs the entry and the operator fills the line — full
automation would ship empty changelogs.

| field | value |
|-------|-------|
| basis | direct: triad in 58/300 commits; plugin.json + CHANGELOG + marketplace.json co-move per release |
| confidence | 82 |
| complexity | Med |
| axis | A |
| status | Unexplored |

### 7. SHA-stamp post-merge stager

A post-merge hook that reads the real squash SHA from `gh pr view --json mergeCommit`, finds the journal placeholder,
and **stages** the substitution as a reviewable diff — it never blind-applies.

The merge step already holds the SHA; losing it to a later manual chore is the bug. But the operator was burned
blind-filling (PR #194 drift was caught only by *reading* the files), so the design respects that scar: deterministic
lookup, staged diff, human eyes on the one-line confirm.

Downside: it earns its keep mainly during campaign-style placeholder workflows; in quieter periods it is dormant.

| field | value |
|-------|-------|
| basis | direct: SHA-fill ~1:1 with feature PRs; "burned blind-filling," PR #194 drift caught by reading |
| confidence | 76 |
| complexity | Med |
| axis | A |
| status | Unexplored |

### 8. Lifecycle artifact + journal scaffolding

A small substrate that, given `(phase, slug, issue)`, mints the canonical `docs/<phase>/YYYY-MM-DD-slug.md` path +
frontmatter + the `docs(<phase>): … (#N)` commit subject — reusing the phase→path map **that already lives in
`handoff_envelope.py` `SOURCE_DIRS`** — and a nudge when a `feat`/`fix` commit touches code but no journal file.

The per-PR ladder repeats the same scaffolding across ~7 commands; centralizing it means a future convention change is
one edit, not seven. The journal *nudge* (detect omission) is the safe, cheap half; the haiku *drafter* was deliberately
cut (writing LEARNINGS prose is judgment the operator has been burned trusting to autopilot — see R3).

Downside: a blunt nudge on every `feat` risks crying wolf, since the rule is "where the mechanism wasn't obvious," not
"always."

| field | value |
|-------|-------|
| basis | direct: ladder "mechanical & identical across commands"; `SOURCE_DIRS` map already exists |
| confidence | 68 |
| complexity | Med |
| axis | C |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived (which re-enters the
Phase 3 filter with new evidence).

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Standalone git-ops/commit agent | SEED 1 as its own "git agent" returning the SHA | `commit-commands` already owns the plumbing; the residual model step (the message) is too small for a standalone file — folded into #4 as the `commit` op | rejected |
| R2 | Auto-clear confirmation predicate | Suppress rubber-stamp merge confirms on green+clean+allowlisted | Not realizable as a plugin — confirmation prompts are emitted by individual skills/the harness; a plugin can't intercept/auto-answer them. Policy already lives in the auto-merge directive | rejected |
| R3 | Haiku journal-entry drafter | A cheap agent writes the LEARNINGS/DECISIONS prose | Durable-knowledge prose (esp. the Generalizable-rule line) is judgment; the SHA blind-fill burn is the precedent. The *nudge* survives in #8 | rejected |
| R4 | "Tier by judgment, not phase" | Commit message → sonnet, plumbing → haiku | A design *principle*, not a deliverable — absorbed into #4 and #5 | revisited |
| R5 | Chore pin-bump dependabot loop | Cheap agent for repeated one-line pin bumps | The 15× churn lives in *sibling* repos (ansible/team-scaffold), not this one; real dependabot/renovate fits better | rejected |

**Rejection summary:** the cuts cluster on three honest lines — *duplication* of `commit-commands` (R1),
*non-realizability* as a plugin artifact (R2), and *judgment dressed as mechanical* (R3, the journal-prose trap). R4 is
an insight that got absorbed rather than killed. No axis finished with zero survivors (A: #6, #7; B: #1, #3; C: #8;
D: #2; E: #4, #5).

## Co-ideation log

Records partnership provenance: both operator seeds were passed into the frame agents, entered the merged pool, and
faced the identical critique — neither rubber-stamped, neither silently dropped.

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | git-ops/commit offloader (haiku, Bash-only, returns SHA) | challenged (commit-commands overlap) → reshaped into #4 substrate; original form cut to R1 |
| user-seed | Phase 0 | bash-batch gate runner | built on by frames 2/3/5 → survived as #3 with single-source-definition + report-by-exception added |
| frame-agent | Phase 2 | deterministic hooks > subagents (frames 2,3,5,6) | became the run's headline reframe; drives #1, #2, #7 |
| frame-agent | Phase 2 | mechanical-handoff contract (frames 3,4) | survived as #4 |
| frame-agent | Phase 2 | tiering doctrine (frames 1,4,6) | survived as #5 |
| frame-agent | Phase 2 | artifact-scaffold reusing SOURCE_DIRS (frame 4) | survived as #8 |

## Notes for the build phase

- Sequence by certainty: #1 and #2 are Low-complexity, high-confidence deterministic guards that also **establish the
  hook harness** the repo lacks — once it exists, #3's runner and #7's stager are incremental additions to the same
  config. Land the harness first.
- #5 (tiering doctrine) is the cheapest and unblocks correct-tier defaults for everything else; it can be written
  immediately as a `DECISIONS.md` entry independent of any code.
- #4 is the keystone but the most speculative — pressure-test it in `/brainstorm` before building (the envelope shape,
  the `op` set, and the haiku-vs-sonnet split for the commit message are the open questions).
- Honor `workflow_structuredoutput_budget` in any cheap-tier dispatch: cap `evidence_tail`, make the emit explicit,
  skim not full-read.
