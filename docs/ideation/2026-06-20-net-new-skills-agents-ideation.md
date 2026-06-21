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
this run excludes that doc's parked items, `/retro` Phase 5a's new-skill detection, and anything
duplicating an installed external tool.

> **Refined 2026-06-20 (Phase 6).** Operator feedback drove two verification passes that materially
> reshaped the set — see **Refinement log** at the bottom. Headlines: the realizability of every
> non-hook idea was nailed down (a plugin-shipped hook is the cross-repo "obeyed" home; tiering must
> live in dispatch *code* + global `~/.claude/CLAUDE.md`, NOT `DECISIONS.md`); the git-history scan
> was broadened from 3 repos to ~50 across 2 orgs, which **promoted** the journal-nudge to the
> best-supported cross-repo helper and **narrowed** the stale-main / version-triad / SHA-stamp ideas
> to this-repo-local rituals.

## Headline reframe (the load-bearing finding)

The seed framing was "agents that pick a cheaper model." The grounding contradicts it in a useful way:
**the highest-value offloads are deterministic HOOKS that invoke no model at all — and the repo has
zero hooks today.** Four of the top mechanical patterns (gate, JSON guard, journal-omission, stale-main)
are pure determinism that, left inline, flood the *most expensive* tokens for a binary answer. A haiku
subagent is still an LLM call; a hook is free and can't forget to fire.

So the answer to "my agent setup is lacking" is **not more agents**. It is: a handful of hooks, **exactly
one** justified cheap-tier agent (a reusable executor, not a per-chore zoo), and tiering enforced in the
plugin's dispatch code. The single new agent file is justified under the binding convention twice over —
it pins a cheaper tier (haiku) **and** narrows tools (Bash-only).

**Where things have to live to be obeyed (verified, see Refinement log):**
- A **deterministic guard hook** → a plugin's `hooks/hooks.json`, enabled at user scope (like `langfuse`)
  → fires in every repo, run by the harness, can block on exit 2. (Or a repo-local `.claude/settings.json`
  hook when the target only exists in one repo.)
- A **cheap-tier executor agent** → a plugin agent whose frontmatter pins `model: haiku` + `tools: Bash`,
  *dispatched by the saga commands* (the file is inert until something calls the Agent tool). A per-call
  `model` override also works.
- A **tiering policy** → enforced in *code* (the `model:` pin + per-call `model` arg in the dispatching
  skills, shipped in the plugin). Recorded as prose only where it's actually read every session: global
  `~/.claude/CLAUDE.md`. A `DECISIONS.md` entry is **not auto-loaded** and would go unseen.

## Grounding Context

**Repo:** `infiquetra-claude-plugins`, a Claude Code plugin marketplace (17 plugins, imminent 17→7 cut).
Flagship `saga` = 17 lifecycle slash-commands. Strong journal discipline. Conventional commits + a per-PR
artifact ladder. Solo + Claude development. Reusable substrate already present: `validate_plugins.py` and
`marketplace/validator/validate.py` (the gate definitions CI calls), and `handoff_envelope.py` `SOURCE_DIRS`
(the phase→`docs/<phase>/` path map). **No hooks exist anywhere** — `.claude/settings.local.json` is
permissions-only, so every hook proposal is greenfield (verified).

**Binding conventions (constraints — an idea violating these was cut):**
- No bespoke domain agents on the default model. No `agents/` dir → generic agents. An agent earns a file
  ONLY when it pins a cheaper tier or narrower tools. Verified: all 35 existing agent files are
  `model: inherit` (every subagent today runs on the Opus main model — that is the waste this run targets).
- Subagents are invoked via the Agent tool, NOT auto-loaded — an `agents/*.md` file does not auto-trigger.
  Reliable triggering = a SKILL/command dispatch or a hook. "More agents" ≠ "more triggering."
- Don't duplicate installed tools: `commit-commands` (already does git commit/push/PR-open — reshaped SEED 1),
  `agy`, `codex`, `compound-engineering` + `superpowers`, `langfuse-observability` (already traces every
  session via plugin hooks — also the existence proof for cross-repo hook distribution).
- Model-tiering has ZERO journal coverage AND zero code enforcement; the operator hand-manages via `/model`
  (28×), `/effort` (113×), `/fast`, `/compact`.

**Measured work-patterns (the `direct:` basis).** Transcript scan = corpus-wide (1863 files, all repos);
git-history scan broadened to ~50 repos across 2 orgs (infiquetra + the coxauto day-job). Cross-repo verdict
per pattern: conventional-commit + PR-per-change + CI-gate hygiene and **journal-in-commit discipline** are
genuinely cross-repo *and* cross-org (the operator transplants journaling into the day-job — 67 journal
commits he authored in `coxauto/vecu-custody-service`); the heavier **release/metadata/worktree machinery**
(version-triad CHANGELOG co-move, SHA-fill, stale-main-after-squash) is **specific to this marketplace repo**
(or ≤2 repos). Key counts: pre-push gate (pytest 614, uv run 1019); marketplace.json edits 95 (recurring
double-`]` corruption); version-triad 58/300 commits here; stale-main idiom only 2 repos; chore pin-bump churn
clusters on the ansible-collection-pin axis.

**Journal learnings consulted:** `workflow_structuredoutput_budget` (cheap-tier fan-out fails from budget
exhaustion — cap output, mandatory emit, skim, batch); "grep shipped siblings for a convention before a
structural first"; dead-wiring (a routed output is dead unless it lands in the consumer's real input shape).

**Context-libraries:** None consulted — the topic is internal.

## Topic Axes

- A. Git & release plumbing · B. Quality gates & validation runs · C. Knowledge & artifact scaffolding ·
  D. State-truth & safety guards · E. Tiering & dispatch mechanism

## Ranked Survivors

Ranking reflects the verified evidence: certain + cheap + cross-repo first; narrow / most-speculative last.

### 1. marketplace.json validation hook (kill the double-`]` bug class)

A deterministic `PostToolUse` hook that runs `python3 -m json.tool` (+ a bracket-count assertion) on any edit
to `.claude-plugin/marketplace.json` or a `plugin.json`, blocking on parse failure with the offending line.

MEMORY.md carries a hand-written warning that this corruption "has happened multiple times" — a remembered
rule is a paper guard, and a guard you can forget isn't one. Better still: a small `marketplace_add.py` that
mutates the JSON object model instead of hand-appending, making the corruption *unrepresentable*.

Downside: it's net-new hook plumbing (greenfield here), and an over-eager matcher could nag on unrelated JSON.

| field | value |
|-------|-------|
| basis | direct: 95 marketplace edits; MEMORY.md "happened multiple times"; `marketplace/validator/validate.py` exists |
| home | repo-local `.claude/settings.json` PostToolUse hook (target file only exists in this repo) |
| confidence | 92 |
| complexity | Low |
| axis | B |
| status | Unexplored |

### 2. Journal-omission nudge (the strongest cross-repo helper)

A `PostToolUse`/`Stop` hook that fires when a `feat`/`fix` commit touches code but stages no
`docs/engineering-journal/` entry, nudging (not writing) per the same-commit journal mandate.

The broadened scan made this the standout: the operator transplants journal discipline into the **day-job**
(67 journal commits he authored in `coxauto/vecu-custody-service`, more in sibling vecu repos), yet the
journal dir exists but *lapses* in several infiquetra repos (olympus, mimir). That setup-vs-upkeep variance
is exactly what a nudge catches — and it's the one helper warranted cross-repo *and* cross-org.

Downside: a blunt nudge on every `feat` risks crying wolf, since the rule is "where the mechanism wasn't
obvious," not "always" — so the trigger needs a heuristic (e.g. diff size / new-file count) or an easy mute.

| field | value |
|-------|-------|
| basis | direct: journal dir cross-repo+cross-org; 67 Jeff-authored journal commits in coxauto/vecu-custody-service; lapses in olympus/mimir |
| home | a user-enabled plugin shipping `hooks/hooks.json` (cross-repo, like `langfuse`) |
| confidence | 82 |
| complexity | Low |
| axis | C |
| status | Unexplored |

### 3. Pre-push gate runner — one definition, report-by-exception

Lift the gate (`ruff check` · `ruff format --check` · `mypy` · `pytest` · `bandit` · the two validators) into
**one manifest** that CI *and* a local pre-push hook both read, and have the runner return only `PASS` or the
failing lines — never the green flood. (This is SEED 2.)

The aviation-checklist insight: a clean checklist reports "all green," not every nominal reading — so the
multi-hundred-line pytest/mypy dump should never enter main context. The single-source insight: CI already
lists these commands inline, so any *second* local list silently drifts; one definition means local-green *is*
CI-green (the `reference_ci_gates` memory is this drift biting). CI-gate hygiene is genuinely cross-repo.

Downside: `pytest` in a blocking hook can be slow; scope it to push-time, not every turn.

| field | value |
|-------|-------|
| basis | direct: #1 ranked pattern (pytest 614, uv run 1019); CI YAML duplicates the command list; CI gates cross-repo |
| home | gate manifest in-repo (single source) + a `PreToolUse(git push)` hook; shippable as a plugin hook cross-repo |
| confidence | 85 |
| complexity | Med |
| axis | B |
| status | Unexplored |

### 4. Tiering enforced in code + a global CLAUDE.md rule

Pin `model: haiku` (+ restricted `tools:`) in the cheap executor agents and pass a per-call `model` arg where
the saga skills dispatch mechanical work; record the one-paragraph tier-selection rule (mechanical → haiku;
routine edit-test → sonnet; architecture/debug/first-time → opus high-effort) in **`~/.claude/CLAUDE.md`**.

Tiering has zero coverage AND zero enforcement today — every subagent runs on Opus (all 35 agents are
`model: inherit`), and the operator hand-manages with 28× `/model` + 113× `/effort` toggles. The verified fix
is enforcement *in code* (frontmatter `model:` + per-call override both work in this harness), distributed to
all repos via the plugin; the prose belongs in global CLAUDE.md because that is the only doc auto-loaded every
session in every repo. `DECISIONS.md` would not be read.

Downside: a global CLAUDE.md rule is soft (the model may apply it inconsistently); the real teeth are the
in-code pins, so the doc is rationale, not enforcement.

| field | value |
|-------|-------|
| basis | direct: tiering zero coverage; all agents `model: inherit`; /model 28×, /effort 113×; per-call `model` override verified in-harness |
| home | `model:` in agent frontmatter + per-call `model` in dispatching saga skills (plugin = cross-repo); rule prose in `~/.claude/CLAUDE.md` |
| confidence | 80 |
| complexity | Low-Med |
| axis | E |
| status | Unexplored |

### 5. `mechanical-handoff` dispatch substrate (the one justified agent)

A single haiku, **Bash-only** plugin agent behind a stable envelope (`{op, args}` → `{ok, result, evidence_tail}`),
`op` ∈ {run-gate, commit, version-bump, sha-stamp}, **dispatched by the saga commands** at their commit/gate
steps. One agent file, many callers — not a new agent per chore. (This is SEED 1, generalized.)

The frames challenged the original "git agent": `commit-commands` already owns the plumbing, so a standalone
version would duplicate it — but a *separate-context, tier-pinned* executor fixes the real pain (the dance
running on the final 17% of a 1500-line session's tokens), and its `commit` op can *delegate to* commit-commands'
plumbing rather than reimplement. Realizability (verified): the agent file is inert until a saga command
dispatches it, so the obedience lives in the dispatch — exactly why it ships as plugin code, not a loose file.
It earns its file under the convention twice over (cheaper tier AND narrowest tools), and the `evidence_tail`
cap bakes in the `workflow_structuredoutput_budget` lesson structurally.

Downside: the most design-judgment of the set, and an all-haiku committer writes mushy commit messages — so the
message step may need a brief sonnet read, not haiku (the "tier by judgment, not phase" insight, R4).

| field | value |
|-------|-------|
| basis | direct: SEED 1 + commit-at-high-context; `handoff_envelope.py` precedent for the envelope; per-call `model` verified |
| home | a plugin agent (`model: haiku`, `tools: Bash`) dispatched by saga `/work` etc. at their plumbing steps |
| confidence | 74 |
| complexity | Med-High |
| axis | E |
| status | Unexplored |

### 6. Version-triad bump + consistency guard (scoped to the plugin repos)

A deterministic `bump_version.py <plugin> <semver>` that writes `plugin.json` + prepends `CHANGELOG.md` + syncs
the `marketplace.json` entry in one pass, plus a pre-push guard that blocks when the three disagree.

Three sources of truth that must agree by hand is a drift generator — 58 of 300 commits here, all mechanical.
The broadened scan narrowed the warrant: CHANGELOG co-move is real *only* in the marketplace plugin repos (most
infiquetra repos have zero CHANGELOG commits; the day-job is tag-driven). So build it scoped here, don't
distribute.

Downside: CHANGELOG *prose* is light judgment, so the script stubs the entry and the operator fills the line.

| field | value |
|-------|-------|
| basis | direct: triad in 58/300 commits here; cross-repo scan shows CHANGELOG co-move is plugin-repo-specific |
| home | in-repo script + a repo-local pre-push consistency hook (not distributed) |
| confidence | 80 |
| complexity | Med |
| axis | A |
| status | Unexplored |

### 7. SHA-stamp post-merge stager (this-repo-local)

A post-merge hook that reads the real squash SHA from `gh pr view --json mergeCommit`, finds the journal
placeholder, and **stages** the substitution as a reviewable diff — it never blind-applies.

The merge step already holds the SHA; losing it to a later manual chore is the bug. But the operator was burned
blind-filling (PR #194 drift was caught only by *reading* the files), so the design respects that scar:
deterministic lookup, staged diff, human eyes on the confirm. The broadened scan confirmed this ritual is
essentially this-repo-only (zero presence across the day-job).

Downside: it earns its keep mainly during campaign-style placeholder workflows; otherwise dormant.

| field | value |
|-------|-------|
| basis | direct: SHA-fill ~1:1 with feature PRs here; "burned blind-filling," PR #194; cross-repo scan = this-repo-local |
| home | repo-local post-merge hook |
| confidence | 74 |
| complexity | Med |
| axis | A |
| status | Unexplored |

### 8. Stale-main preflight guard (narrow — cheap insurance for bg-worktree sessions)

A `SessionStart`/post-merge hook that runs `git fetch` + `git rev-list --count main..origin/main` and emits one
loud "local main is N behind origin; do NOT trust the tree" line, auto-fast-forwarding when main is clean.

Detection is 100% mechanical and the failure is real (a stale tree silently lies about what shipped — it cost
two builds here). **But broadening the scan weakened, not strengthened, the case:** most "worktree" activity in
home-lab is the agent-fleet's runtime worktree *feature*, not this hazard; the actual stale-tree-after-squash
idiom appears in only 2 repos (here + home-lab) = the 2 logged incidents. Keep it as cheap insurance where
bg-worktree sessions run; don't claim it's a universal need.

Downside: narrow blast radius, and bg-worktree sessions complicate "what is main here," so it must understand
worktrees or it will false-alarm.

| field | value |
|-------|-------|
| basis | direct: "burned 2 builds"; cross-repo scan = idiom in only 2 repos (downgraded from the original "everywhere" implication) |
| home | repo-local (or bg-session) `SessionStart` hook where worktree workflows run |
| confidence | 70 |
| complexity | Low |
| axis | D |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived (which re-enters
the Phase 3 filter with new evidence).

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Standalone git-ops/commit agent | SEED 1 as its own "git agent" returning the SHA | `commit-commands` already owns the plumbing; the residual model step (the message) is too small for a standalone file — folded into #5 as the `commit` op | rejected |
| R2 | Auto-clear confirmation predicate | Suppress rubber-stamp merge confirms on green+clean+allowlisted | Not realizable as a plugin — confirmation prompts are emitted by individual skills/the harness; a plugin can't intercept/auto-answer them. Policy already lives in the auto-merge directive | rejected |
| R3 | Haiku journal-entry drafter | A cheap agent writes the LEARNINGS/DECISIONS prose | Durable-knowledge prose (esp. the Generalizable-rule line) is judgment; the SHA blind-fill burn is the precedent. The *nudge* survives as #2 | rejected |
| R4 | "Tier by judgment, not phase" | Commit message → sonnet, plumbing → haiku | A design *principle*, not a deliverable — absorbed into #4 and #5 | revisited |
| R5 | Chore pin-bump dependabot loop | Cheap agent for repeated one-line pin bumps | The 15× churn clusters on the ansible-collection-pin axis (this repo + team-mimir/home-lab); real dependabot/renovate fits better | rejected |
| R6 | Lifecycle artifact scaffolder | A helper minting `docs/<phase>/DATE-slug.md` + commit subject from `SOURCE_DIRS` | Invisible plumbing, low felt value; the operator couldn't tell what it did. Its useful half (the journal-omission nudge) was promoted to survivor #2 | rejected |

**Rejection summary:** the cuts cluster on four honest lines — *duplication* of `commit-commands` (R1),
*non-realizability* as a plugin artifact (R2), *judgment dressed as mechanical* (R3, the journal-prose trap),
and *low felt value* (R6, the scaffolder). R4 is an insight absorbed rather than killed; R5 is better served by
off-the-shelf tooling. No axis finished with zero survivors (A: #6, #7; B: #1, #3; C: #2; D: #8; E: #4, #5).

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | git-ops/commit offloader (haiku, Bash-only, returns SHA) | challenged (commit-commands overlap) → reshaped into #5 substrate; original form cut to R1 |
| user-seed | Phase 0 | bash-batch gate runner | built on by frames 2/3/5 → survived as #3 with single-source-definition + report-by-exception |
| frame-agent | Phase 2 | deterministic hooks > subagents (frames 2,3,5,6) | became the run's headline reframe; drives #1, #2, #3, #8 |
| frame-agent | Phase 2 | mechanical-handoff contract (frames 3,4) | survived as #5 |
| frame-agent | Phase 2 | tiering doctrine (frames 1,4,6) | survived as #4, reshaped (enforce in code + global CLAUDE.md, not DECISIONS.md) |
| frame-agent | Phase 2 | artifact-scaffold + journal nudge (frames 4,6) | split in Phase 6 — nudge promoted to #2, scaffolder cut to R6 |
| operator | Phase 6 | "where does this live so it's obeyed?" + "did you only scan this repo?" | drove the two verification passes that reshaped #2/#4/#5/#8 |

## Refinement log (Phase 6, 2026-06-20)

Two verification passes, triggered by operator feedback on the survivors:

**(a) Distribution mechanics — verified.** Plugin hooks are real and cross-repo: `langfuse` ships
`hooks/hooks.json` (Stop/SessionEnd), user-enabled in `~/.claude/settings.json`, firing in every repo;
`PreToolUse` can block on exit 2. Plugin agents are inert until dispatched; frontmatter `model:`/`tools:` work,
and the Agent tool exposes a per-call `model` override — but **all 35 infiquetra agents are `model: inherit`**,
so tiering is currently nowhere. `~/.claude/CLAUDE.md` is auto-loaded every session/every repo; `DECISIONS.md`
is not. → fixed the realizability of #4 (substrate ships as a tier-pinned plugin agent, dispatched by saga
commands) and #5 (tiering enforced in code + global CLAUDE.md, not DECISIONS.md).

**(b) Cross-repo git scan — broadened 3 → ~50 repos / 2 orgs.** Conventional commits, PR-per-change, CI gates,
and **journal-in-commit discipline** are genuinely cross-repo *and* cross-org (67 Jeff-authored journal commits
in `coxauto/vecu-custody-service`). The release/metadata/worktree machinery is this-repo-local. →
**promoted** the journal-omission nudge to #2; **narrowed** version-triad (#6) and SHA-stamp (#7) to scoped-here;
**downgraded** stale-main (#8) — the broad scan showed its idiom in only 2 repos, not "everywhere" (most
home-lab "worktree" churn is the agent-fleet feature, not the operator's hazard). New cross-repo theme noted but
NOT a helper candidate: reconcile/self-heal/drift churn in team-mimir/home-lab/olympus (domain logic).

## Notes for the build phase

- Sequence by certainty + reach: **#4 (tiering)** is the cheapest first move and unblocks correct-tier defaults
  for everything else (pin `model:` once + a CLAUDE.md line). Then the **deterministic guards** (#1 repo-local;
  #2 + #3 as a cross-repo plugin) — landing them establishes the hook harness the repo lacks, after which #7/#8
  are incremental.
- **#5** is the keystone but most speculative — pressure-test in `/brainstorm` first (envelope shape, the `op`
  set, the haiku-vs-sonnet split for the commit message).
- Honor `workflow_structuredoutput_budget` in any cheap-tier dispatch: cap `evidence_tail`, make the emit
  explicit, skim not full-read.

## Related ideation — dynamic-workflow representation & authoring

A sibling run (operator seed, 2026-06-20):
[`2026-06-20-execution-backend-representation-ideation.md`](./2026-06-20-execution-backend-representation-ideation.md)
ideates on how saga's `/plan` flow represents, names, defaults toward, and authors the execution
backends — especially Claude Code dynamic (ultracode) workflows. It directly extends the **tiering**
items (#4/#5) above: its survivor **S5** reframes per-agent model+effort tiering as a *plan property*
(judgment→Opus / mechanical→Sonnet-Haiku, with the pilot↔fan-out same-tier invariant), the
authoring-time home for the same tier policy this doc enforces in agent frontmatter. Sequence the two as
one thread; its keystone (S2 — split `needs_consensus` into gated vs advisory so the recommender can
route consensus work to a workflow judge-panel) is the natural first `/brainstorm` seed.
