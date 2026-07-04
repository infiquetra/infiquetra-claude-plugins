---
title: "capability: one agent-file CI lint — frontmatter schema, role-class tier audit, tool-scope floor, cache-prefix stability"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
---

# capability: one agent-file CI lint — frontmatter schema, role-class tier audit, tool-scope floor, cache-prefix stability

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

### Intent

Every agent `.md` file across all 8 plugins is a hand-authored, hand-maintained artifact with
no shared parser and no CI gate over its structural correctness. Today the fleet has 34 agent
files (`find plugins -path "*/agents/*.md" | wc -l`), every one of them hardcoding a `model:`
value in frontmatter (opus/sonnet/haiku) with zero `effort:` fields anywhere
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:18-19`), and no CI check that a `model:`
pin is appropriate for the agent's declared role class, that a review/verify-class agent's
`tools:` list holds to least privilege, or that the two existing narrow drift tests
(`tests/test_agent_tiering.py`, `tests/test_agent_registration_drift.py`) share a parser instead
of each hand-rolling its own copy of `_parse_frontmatter` (verified identical implementations at
`tests/test_agent_tiering.py:18-38` and `tests/test_agent_registration_drift.py:33-50`, the
second file's docstring at line 36 explicitly calling this out as a mirrored — not shared —
routine).

This capability consolidates four independently-surviving ideation facets
(`G-hybrids-13`, `T11-F4-1`, `T11-F3-2`, `T11-F1-2` — see Grounding references) into **one**
agent-lint script with a pluggable rule registry, wired into `.github/workflows/ci.yml`
alongside the existing dependency-free named-signal steps (e.g. the issue-contract vendored
parity check at `.github/workflows/ci.yml` "Issue-contract vendored parity" step). The
consolidation rationale (from the issue-map): the hybrid idea already unifies the lint surface;
the shared agent-spec parser, the role-class tier-appropriateness audit, and the least-privilege
tool floor are rule-registry entries inside the same script, not separate PRs — splitting them
would multiply CI wiring and duplicate the frontmatter parser a third and fourth time.

### Problem frame

- **No shared parser.** `tests/test_agent_tiering.py:18-38` and
  `tests/test_agent_registration_drift.py:33-50` each define their own
  `_parse_frontmatter(path_or_text) -> dict[str, str]` doing the identical regex-based scalar
  extraction over the block between the first and second `---` markers. Any fix to frontmatter
  parsing (e.g. supporting quoted multi-word values, or block scalars) has to land in both
  places or silently diverges.
- **No role-class tier-appropriateness audit.** `tests/test_agent_tiering.py:48-53` pins exactly
  4 "callable ecosystem agents" to specific models by name (`PINNED_AGENTS` list); it says
  nothing about the other 30 agent files in the fleet, including the 24 team-execution
  reviewer/tester agents where `model: opus` is hand-set per file (e.g.
  `plugins/team-execution/agents/api-reviewer.md:11`, `architecture-reviewer.md:16`,
  `code-quality-reviewer.md:16`) alongside `model: haiku` scanners
  (`plugins/team-execution/agents/api-compat-scanner.md:8`, `dependency-scanner.md:8`). There is
  no policy artifact stating which role classes (survey / judgment / scanner / review) may carry
  which model tier, so a survey agent accidentally pinned to `opus`, or a judgment agent pinned
  to `haiku`, would pass every test in the repo today.
- **No least-privilege tool-scope floor.** Review-class and scanner-class agents in
  team-execution declare `tools:` in frontmatter (e.g.
  `plugins/team-execution/agents/api-compat-scanner.md`, `dependency-scanner.md`,
  `security-scanner.md`, `iac-cost-scanner.md`, `api-contract-tester.md` all carry a `tools:`
  field), but nothing in CI asserts that a review/verify-class agent excludes mutating tools
  (`Edit`, `Write`). This is the same class of gap the saga plugin already closed operationally
  for its own readonly-verifier via the sandbox-spawn-sites fallback ladder
  (`plugins/saga/references/sandbox-spawn-sites.md`, guarded by
  `tests/test_agent_registration_drift.py:177-186`) — that guard covers only saga's one agent,
  not the fleet's review-class agents in team-execution.
- **`effort:` absence has no lint surface at all.** Zero of the fleet's 24 team-execution agent
  files carry an `effort:` field (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:19`).
  This capability's scope is to make that fact CI-visible (warn-then-block per the dod_sketch),
  not to retrofit `effort:` onto every agent file — that backfill is out of scope (see Scope
  & non-goals).

## Definition of Done

One agent-lint script — a pluggable rule registry evaluated over every agent definition file in
the fleet (`plugins/*/agents/*.md`) — is wired as a named CI step in `.github/workflows/ci.yml`,
alongside a shared parser module that both existing drift tests are refactored to consume. The
rule registry enforces, at minimum:

1. **Frontmatter schema** — every agent file's frontmatter block parses (has a `name:` field
   matching its file stem, consistent with the existing `_name_matches_stem` contract in
   `tests/test_agent_registration_drift.py:61-63`).
2. **`effort:` presence** — warn (non-blocking) today, with a documented flip date/condition to
   block, once emitted per agent file missing an `effort:` field.
3. **Model-vs-role-class policy** — a new `agent-role-classes.json` (or equivalent) reference
   maps each role class (survey / judgment / scanner / review, etc.) to its permitted model
   tier(s); the lint fails when an agent's `model:` value falls outside its declared role
   class's permitted set.
4. **Tool-scope floor for review-class agents** — any agent classified review/verify-class fails
   the lint if its `tools:` frontmatter list is absent or includes `Edit`/`Write`.
5. **Cache-prefix / registration-drift stability** — `tests/test_agent_tiering.py` and
   `tests/test_agent_registration_drift.py` are refactored to import the shared parser from the
   new registry module rather than each defining `_parse_frontmatter` inline; both test suites
   stay green post-refactor.

Merged artifact: one new script (proposed path
`plugins/saga/scripts/agent_spec.py` or a repo-root `tools/agent_spec.py` — exact placement is
`/plan`'s call, see Files expected to change) implementing the parser + rule registry, one new CI
step in `.github/workflows/ci.yml` invoking it (fails the job on any rule violation once past the
`effort:` warn-only grace period), the two existing test files refactored onto the shared parser,
and a new parametrized rubric test running every rule against every agent `.md` in the fleet.

### Acceptance criteria
- [ ] **Shared parser.** `tests/test_agent_tiering.py` and `tests/test_agent_registration_drift.py`
  both import their frontmatter parser from the new shared module (no duplicated
  `_parse_frontmatter` definitions remain in either file). Check: `grep -n "_parse_frontmatter"
  tests/test_agent_tiering.py tests/test_agent_registration_drift.py` shows an import, not a
  `def`, in both files.
- [ ] **Red-fixture coverage, one per rule.** A fixture agent file with a role-class/model
  mismatch fails the model-vs-role-class rule. Check: `uv run pytest
  tests/test_agent_spec_lint.py -k role_class_mismatch` → fails on the planted red fixture,
  passes once the fixture is corrected (test asserts both directions).
- [ ] **Clean pass on the fixed fleet.** Every current agent file in `plugins/*/agents/*.md`
  passes the full rule registry. Check: `python3 <lint-script-path> plugins/*/agents/*.md` (or
  `uv run pytest tests/test_agent_spec_lint.py -k full_fleet`) → exit 0 / all pass, after any
  flagged agents are corrected as part of this change.
- [ ] **Survey agent pinned to `opus` fails the role-class audit.** Check: a synthetic
  survey-class agent fixture with `model: opus` trips the model-vs-role-class rule. Check:
  `uv run pytest tests/test_agent_spec_lint.py -k survey_opus_mismatch` → fails on the red
  fixture (proves the rule isn't vacuously true).
- [ ] **Review-class agent listing `Edit`/`Write` fails the tool-scope floor.** Check: a
  synthetic review-class agent fixture with `tools: [Read, Edit]` trips the tool-floor rule.
  Check: `uv run pytest tests/test_agent_spec_lint.py -k tool_floor_violation` → fails on the red
  fixture.
- [ ] **`effort:` absence is a warning, not a hard failure, at ship time.** Check:
  `python3 <lint-script-path> --report` on the current fleet (0 of 24 team-execution agents
  carry `effort:`) exits 0 with warnings printed, not a nonzero exit code.
- [ ] **Existing tiering/registration-drift tests still pass post-refactor.** Check: `uv run
  pytest tests/test_agent_tiering.py tests/test_agent_registration_drift.py` → all pass,
  unchanged assertions, parser now imported from the shared module.
- [ ] **CI wiring is live.** Check: `.github/workflows/ci.yml` contains a named step invoking the
  new lint script; a PR with a deliberately-broken agent fixture fails that CI step (verified in
  the PR that ships this capability, not re-checkable after merge — record the failing-run URL
  in the PR description).
- [ ] **Full repo suite stays green.** Check: `uv run pytest && uv run ruff check . && uv run
  mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- One shared parser module + pluggable rule registry over `plugins/*/agents/*.md`.
- Frontmatter schema, `effort:` presence (warn-only), model-vs-role-class audit, tool-scope
  floor for review-class agents, and the CI wiring step.
- Refactoring the two existing drift tests onto the shared parser (no behavior change to their
  existing assertions).

**Non-goals (deliberately excluded from this capability):**
- Backfilling `effort:` onto any of the fleet's 24 agent files — the lint surfaces the gap
  (warn-then-block), it does not retrofit the field.
- Changing any agent's current `model:` pin, even where the audit newly flags one as
  role-class-inappropriate — flagged agents get corrected as part of *this* change only if doing
  so is needed to reach a clean fleet pass (Acceptance criterion 2); broader model re-tiering
  decisions are out of scope.
- Extending the tool-scope floor to non-review-class agents (scanners, testers) — v1 targets
  review/verify-class only, matching the existing saga readonly-verifier precedent.
- Building a new "role class" taxonomy from scratch with no anchor in current agent
  descriptions — the role-class policy file must be derived from each agent's existing
  `description:` framing (e.g. "Optional reviewer for team-execution" in
  `plugins/team-execution/agents/api-reviewer.md`), not invented wholesale.
- Any change to `plugins/saga/scripts/execution_spec.py`'s `MODELS`/`EFFORTS` vocabulary or the
  `/plan` unit-tier table (`plugins/saga/skills/plan/SKILL.md:296-352`) — this capability lints
  agent *files*, it does not touch the dispatch-time model/effort lever itself.

## Grounding References

- **`G-hybrids-13`** (primary, role: primary) — "One agent-file CI lint: frontmatter schema,
  tier/effort fields, prompt rubric, and cache-prefix stability." Basis:
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (theme T11, frame
  `gap-hybrids`, axis `agent-prompt-audit`, tier `structural`, verdict `survive`). Thin seed
  (null body) — intent reconstructed here from its `dod_sketch` plus grounding-brief §1
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:14-21`, the model/effort reality
  section documenting 0-of-24 `effort:` coverage and hardcoded `model:` pins fleet-wide).
- **`T11-F4-1`** (facet) — "Shared agent-spec registry primitive that every agent file is
  CI-validated against." Basis: same survivors file, frame F4. Thin seed; its `dod_sketch`
  names `tools/agent_spec.py` as the shared parser + rubric, with
  `test_agent_tiering`/`test_agent_registration_drift` refactored to consume it and a
  parametrized rubric test over every agent `.md` — reflected directly in this issue's
  Definition of done and Acceptance criteria.
- **`T11-F3-2`** (facet) — "`model:` is not a fixed agent property — audit tier-appropriateness
  against a role-class policy." Basis: same survivors file, frame F3. Thin seed; its
  `dod_sketch` names an `agent-role-classes.json` + an audit failing on model↔role-class
  mismatch (survey agent pinned opus, judgment agent pinned haiku), verified by an oracle test
  with one mis-tiered agent — reflected in Acceptance criterion "Survey agent pinned to `opus`
  fails the role-class audit."
- **`T11-F1-2`** (facet) — "Least-privilege tool-scope guard for review/verify-class agents."
  Basis: same survivors file, frame F1. Thin seed; its `dod_sketch` names
  `scripts/audit_agent_tools.py` + a tool-floor reference doc, failing when a review-class agent
  lacks a least-privilege `tools:` list (or lists `Edit`/`Write`), with `readonly-verifier`
  passing as the positive control — reflected in Acceptance criterion "Review-class agent
  listing `Edit`/`Write` fails the tool-scope floor."
- **Binding decisions this capability must respect** (per
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`):
  - `{#readonly-verifier-fallback-ladder-325}` + `{#verify-agent-git-checkout-clobber}` — the
    tool-scope floor rule must not contradict the existing readonly-verifier fallback-ladder
    precedent (`plugins/saga/references/sandbox-spawn-sites.md`); it extends the same
    least-privilege posture to team-execution's review-class agents rather than inventing a
    conflicting one.
  - `{#tier-vocab-ordering}` — the model-vs-role-class policy must treat tier tuples as ordered
    escalation ladders, not an unordered closed set, when defining "permitted model tier(s) per
    role class."
- **Prior art already in the repo** (do not duplicate): `tests/test_agent_tiering.py` (4
  callable-ecosystem-agent model pins + KTD7 exemption), `tests/test_agent_registration_drift.py`
  (frontmatter-name/stem match, `READONLY_VERIFIER_AGENT_TYPE` constant parity, dangling
  `saga:<name>` spawn-context references, #325 fallback-ladder documentation guard).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none — this is an internal CI-lint authoring task with no external
  advisory-review value; per `{#external-engines-never-gatekeepers}` (#283) any external engine
  use here would be non-gated and additive only, and the work does not warrant it.
- **Justification:** mechanical-but-nontrivial scaffolding work (shared parser extraction, rule
  registry, CI wiring, fixture-based tests) — sonnet at high effort is the fleet's established
  tier for this shape of work; no architectural judgment call rises to opus-level ambiguity once
  the role-class policy is anchored in existing agent `description:` text (see Scope &
  non-goals).

### Release-surface checklist

This capability changes fleet-wide CI behavior (a new blocking gate over every plugin's agent
files) but does not change any single plugin's runtime behavior, schema, command, or prompt
surface on its own. Per CLAUDE.md step 6, confirm for each plugin whose agent files trip a new
rule during the fixing pass:

- [ ] `plugins/<plugin>/.claude-plugin/plugin.json` — bump patch version if any agent file's
  frontmatter is corrected as part of reaching a clean fleet pass (e.g. team-execution, if any
  of its 24 agent files needs a `model:` or `tools:` correction).
- [ ] `.claude-plugin/marketplace.json` — sync version bumps for any plugin touched above.
- [ ] `plugins/<plugin>/CHANGELOG.md` — entry for any plugin whose agent file content changed.
- [ ] Drift-guard tests — `tests/test_agent_tiering.py` and
  `tests/test_agent_registration_drift.py` updated in the same PR to import the shared parser
  (Acceptance criterion 1); no plugin-metadata drift-guard test currently exists for agent-file
  content itself — this capability is that test's first version, so no separate "update the
  existing drift guard" step applies beyond the two files named above.
- [ ] If no plugin's agent files require correction to pass the new lint (i.e. the fleet is
  already clean), explicitly note in the PR description that no plugin.json/marketplace.json/
  CHANGELOG bump is needed, since only new tooling (not plugin behavior) shipped.

### Tier / Type / Wave

- **Tier:** structural
- **Type:** capability
- **Objective:** Gate fleet integrity (agent files, prompts, release surfaces)
- **Wave:** wave-2

### Suggested next action

Use `/plan <issue>` to create an implementation plan — in particular to settle the exact
placement of the shared parser/rule-registry script (`plugins/saga/scripts/agent_spec.py` vs. a
repo-root `tools/agent_spec.py`) and the concrete shape of `agent-role-classes.json`.

### Context library links

_none_

### Files expected to change

- `tests/test_agent_tiering.py`
- `tests/test_agent_registration_drift.py`
- `.github/workflows/ci.yml`
- `plugins/team-execution/agents/api-compat-scanner.md`
- `plugins/saga/references/sandbox-spawn-sites.md`
- `plugins/saga/scripts/agent_spec.py`
- `tools/agent_spec.py`
- `plugins/team-execution/agents/api-reviewer.md`

### Tests to add or update

- `tests/test_agent_registration_drift.py`
- `tests/test_agent_spec_lint.py`
- `tests/test_agent_tiering.py`

### Verification

```bash
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/422
- Number: 422
- Created at: 2026-07-04T08:08:29.479674+00:00

