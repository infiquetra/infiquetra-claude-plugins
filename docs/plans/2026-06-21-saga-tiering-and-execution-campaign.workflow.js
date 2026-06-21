export const meta = {
  name: 'saga-tiering-execution-campaign',
  description:
    'Build the saga tiering + execution-mechanism campaign (5 epics, 17 units) with a per-unit {model,effort} tier on every step. ' +
    'Epic-isolated PRs, full hands-off auto-merge when CI is green. Opus for judgment (offer rewrite, recommender split, the spec ' +
    'emitter, degradation, final verify); Sonnet for bounded builds; Haiku for the preflight existence check. Control-flow only — ' +
    'every agent reads the plan as its authoritative spec.',
  phases: [
    { title: 'Preflight' },
    { title: 'Epic 0 - Tiering', model: 'sonnet' },
    { title: 'Epic 1 - Representation', model: 'opus' },
    { title: 'Epic 3 - Hooks', model: 'sonnet' },
    { title: 'Epic 2 - Authoring', model: 'opus' },
    { title: 'Epic 4 - Executor + guards', model: 'sonnet' },
    { title: 'Final', model: 'opus' },
  ],
}

// =============================================================================
// Saga Tiering & Execution-Mechanism Campaign -- execution harness.
//
// Authoritative spec (READ IT, do not re-derive):
//   infiquetra-claude-plugins/docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md
//   (R1-R18, U1-U17, KTD1-KTD10, the per-unit tier table, AE1-AE6).
//
// CONTROL FLOW only. The agents do the real work (edit code, add tests, run the
// gate, open + auto-merge PRs). Each agent is told to read the plan first and
// implement its unit verbatim.
//
// Per-unit model tiering (KTD2, operator-approved): 5 Opus / 11 Sonnet / 1 Haiku.
// INVARIANT mirrored from the reference (context-fleet-audit.workflow.js): a unit's
// tier matches its work shape -- judgment->Opus, bounded build->Sonnet, existence
// check->Haiku. The gate+merge step runs Sonnet/high (mechanical gate-fixing).
//
// Topology (KTD3 full hands-off; dependency barriers from the plan):
//   Preflight (U1, halt-on-drift)
//     -> parallel( Epic0 {U2,U3}, Epic1 {U4,U5,U6}, Epic3 {U7,U8,U9} )   [first wave]
//     -> BARRIER: Epic0 + Epic1 merged (Epic2 needs both; Epic4 needs Epic0)
//     -> parallel( Epic2 {U10,U11,U12,U13}, Epic4 {U14,U15,U16} )         [second wave]
//     -> Final (U17): full gate fleet-wide + journal + R-ID reconciliation.
//
// Each epic runs its units SERIALLY on ONE worktree+branch (no intra-epic race)
// and lands as ONE PR. Epics run in parallel; cross-epic saga.py overlap (U3 vs U4)
// resolves by rebase-before-merge (KTD9). The oracle is the test suite + the two
// validators + the drift-guards -- a red gate blocks the auto-merge.
//
// Resume: re-run with {scriptPath, resumeFromRunId}. Merge agents probe for an
// already-open/merged PR and a pre-existing worktree, so a re-run skips landed epics.
// =============================================================================

const REPO = '/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins'
const PLAN_PATH = REPO + '/docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md'
const WT = REPO + '/.claude/worktrees/campaign'
const BUDGET_FLOOR = 60000 // checkpoint before a new wave when remaining output budget drops below this

// Every agent prompt starts with this so the plan is authoritative and the rules are uniform.
const SPEC =
  'AUTHORITATIVE SPEC: read ' + PLAN_PATH + ' in full FIRST -- it is the spec (R-IDs, U-IDs, KTDs, AEs). ' +
  'Implement your assigned unit EXACTLY as its `### U<N>.` section says. ' +
  'RULES: (1) On any plugin behavior/metadata change, bump the release triad in the SAME change -- the plugin ' +
  "`.claude-plugin/plugin.json` version, `.claude-plugin/marketplace.json`, and the plugin `CHANGELOG.md` (CLAUDE.md section 6); " +
  'validate marketplace.json with `python3 -m json.tool` after editing it. ' +
  '(2) Do NOT edit docs/engineering-journal/ -- U17 writes the campaign DECISIONS/LEARNINGS to avoid cross-epic journal conflicts. ' +
  '(3) Follow repo commit/PR conventions (`type(scope): description`, atomic); NEVER add attribution lines ' +
  '("Generated with", "Co-authored-by") to commits, PRs, or any content. ' +
  '(4) Feature-bearing units add real tests at the repo-relative path the plan names; run them before reporting done. ' +
  'Your final message IS the structured return value -- no human-facing prose.'

// ---- structured-return schemas ----
const PREFLIGHT_SCHEMA = {
  type: 'object',
  required: ['ready', 'drift'],
  properties: {
    ready: { type: 'boolean', description: 'true iff every grounding fact still holds on origin/main' },
    drift: { type: 'array', items: { type: 'string' }, description: 'each fact that no longer holds (empty iff ready)' },
  },
}

const UNIT_SCHEMA = {
  type: 'object',
  required: ['unit', 'done', 'files'],
  properties: {
    unit: { type: 'string' },
    done: { type: 'boolean', description: 'edits committed to the epic worktree + unit tests pass locally' },
    files: { type: 'array', items: { type: 'string' } },
    testAdded: { type: 'string', description: 'repo-relative test path, or "none -- <reason>"' },
    note: { type: 'string' },
  },
}

const EPIC_SCHEMA = {
  type: 'object',
  required: ['epic', 'gatePassed', 'ciGreen', 'merged'],
  properties: {
    epic: { type: 'string' },
    pr: { type: 'string' },
    gatePassed: { type: 'boolean', description: 'full local gate (ruff format+check, both validators, pytest, mypy) green' },
    ciGreen: { type: 'boolean', description: 'all 5 required CI checks SUCCESS' },
    merged: { type: 'boolean', description: 'true ONLY if the squash-merge landed' },
    units: { type: 'array', items: { type: 'string' } },
    reason: { type: 'string' },
  },
}

const FINAL_SCHEMA = {
  type: 'object',
  required: ['gateGreen', 'rIdsCovered', 'rIdsTotal', 'merged'],
  properties: {
    gateGreen: { type: 'boolean' },
    rIdsCovered: { type: 'number' },
    rIdsTotal: { type: 'number' },
    merged: { type: 'boolean' },
    reportPath: { type: 'string' },
    note: { type: 'string' },
  },
}

function budgetExhausted() {
  return budget.total && budget.remaining() < BUDGET_FLOOR
}

// ---- the epic runner: serial tiered units on one worktree, then gate + auto-merge ----
async function runEpic(epicId, phaseTitle, branch, units) {
  const dir = WT + '/' + epicId
  for (let i = 0; i < units.length; i++) {
    const u = units[i]
    const setup =
      i === 0
        ? 'Create the epic worktree FIRST (reuse it if a prior run left it): ' +
          '`git -C ' + REPO + ' fetch origin && git -C ' + REPO + ' worktree add ' + dir + ' -b ' + branch + ' origin/main` ' +
          '(if the branch already exists, `git -C ' + REPO + ' worktree add ' + dir + ' ' + branch + '`). '
        : 'The epic worktree already exists at ' + dir + ' on branch ' + branch + '. '
    const res = await agent(
      SPEC +
        '\n\nWORKTREE: ' + setup +
        'Make ALL edits inside ' + dir + ' and commit there (`git -C ' + dir + ' add -A && git -C ' + dir + ' commit -m "<type(scope): msg>"`). ' +
        'Do NOT push or open a PR -- the epic merge step does that.\n\n' + u.prompt,
      { schema: UNIT_SCHEMA, label: u.label, phase: phaseTitle, model: u.model, effort: u.effort }
    )
    if (!res || !res.done) {
      throw new Error('HALT: ' + epicId + ' unit ' + u.label + ' failed: ' + (res ? res.note || 'not done' : 'dead agent'))
    }
    log(epicId + ': ' + u.label + ' done (' + (res.files || []).length + ' files; test=' + (res.testAdded || '?') + ')')
  }

  // Gate + PR + auto-merge -- FULL HANDS-OFF (KTD3): merge when CI is green, no human checkpoint.
  const merge = await agent(
    SPEC +
      '\n\nEPIC MERGE STEP for ' + epicId + ' (worktree ' + dir + ', branch ' + branch + '). FULL HANDS-OFF -- merge when green.\n' +
      '1) From WITHIN ' + dir + ' run the full local gate: `ruff format --check .`; `ruff check .`; ' +
      '`python3 scripts/validate_plugins.py`; `python3 marketplace/validator/validate.py`; `uv run pytest`; `uv run mypy plugins/`. ' +
      'If any FAILS, fix it in the worktree (small, in-scope fixes only) and re-run until all pass. Set gatePassed accordingly.\n' +
      '2) `git -C ' + dir + ' fetch origin && git -C ' + dir + ' rebase origin/main` -- resolve conflicts by integrating BOTH sides ' +
      '(watch plugins/saga/scripts/saga.py and .claude-plugin/marketplace.json). Re-run the gate if the rebase changed anything.\n' +
      '3) Push and open a PR (`gh pr create`; title "' + epicId + ': <summary>"). Probe first: if a PR for this branch already exists, reuse it; if already MERGED, set merged=true and skip to step 5.\n' +
      '4) Poll the 5 REQUIRED checks (Tests (Python 3.12) / Validate Plugins / Lint / Type Check / Security Scan). "Publish Plugin" SKIPPED is expected and NOT a failure. ' +
      'When all 5 are SUCCESS, squash-merge: `gh pr merge --squash --admin --delete-branch`. If any required check FAILS, do NOT merge -- set ciGreen=false, merged=false, and report the failing check.\n' +
      '5) `git -C ' + REPO + ' worktree remove ' + dir + ' --force` (ignore if already gone).\n' +
      'Return EPIC_SCHEMA. merged=true ONLY if the squash-merge actually landed on origin/main.',
    { schema: EPIC_SCHEMA, label: epicId + ' gate+merge', phase: phaseTitle, model: 'sonnet', effort: 'high' }
  )
  if (!merge) return { epic: epicId, gatePassed: false, ciGreen: false, merged: false, reason: 'merge agent died' }
  log(epicId + ' merge: gate=' + merge.gatePassed + ' ci=' + merge.ciGreen + ' merged=' + merge.merged + (merge.pr ? ' (' + merge.pr + ')' : ''))
  return merge
}

// ---- unit definitions (terse recaps; the plan section is authoritative) ----
const EPIC0 = [
  {
    label: 'U2 agent pins', model: 'sonnet', effort: 'high',
    prompt: 'UNIT U2 -- pin model: on the 4 CALLABLE ecosystem agents: home-lab-ops/homelab-sre->opus, ' +
      'mission-control/sdlc-operator->sonnet, unifi/unifi-network-ops->sonnet, deploy/release-orchestrator->sonnet. ' +
      'Document redis-channel/redis-channel-coach EXEMPT (KTD7: an MCP-instructions pointer, not Agent-dispatched). ' +
      'Bump each touched plugin release triad. Add tests/test_agent_tiering.py asserting the 4 pins + the coach exemption.',
  },
  {
    label: 'U3 choice instrument', model: 'sonnet', effort: 'medium',
    prompt: 'UNIT U3 -- record recommended-vs-chosen backend on each orchestration decision in the saga envelope ' +
      '(backward-compatible: older sagas without the field must still load). Extend tests/test_saga_saga.py + saga-spec.md. ' +
      'No analysis yet (that is U13).',
  },
]
const EPIC1 = [
  {
    label: 'U4 label map', model: 'sonnet', effort: 'high',
    prompt: 'UNIT U4 -- add a display-label map (cc-workflows-ultracode->"dynamic workflows", team-execution->"team execution", ' +
      'inline->"inline"); route every offer surface through it; ASSERT the enum value ORCHESTRATION_MODES is byte-for-byte unchanged ' +
      '(frozen wire contract, KTD5; no "(Claude Code only)" suffix). A map miss falls back to the enum string, never errors. ' +
      'Test in tests/test_saga_saga.py.',
  },
  {
    label: 'U5 offer + drift-guard', model: 'opus', effort: 'high',
    prompt: 'UNIT U5 -- rewrite the /plan (skills/plan/SKILL.md ~:253) AND /code-review offer to name BOTH dynamic-workflow purposes ' +
      '(breadth fan-out AND adversarial confidence) and frame the team<->workflow fork on the GOVERNANCE axis (does the verdict need ' +
      'to stick?), not "review depth". Add tests/test_operator_choice_drift.py asserting every offer surface is a SUPERSET of ' +
      'operator-choice.md section 3.2 purposes (anchor on stable markers, not line numbers).',
  },
  {
    label: 'U6 recommender split', model: 'opus', effort: 'high',
    prompt: 'UNIT U6 (R7 KEYSTONE) -- in recommend_execution_backend (lifecycle_state.py), replace the single needs_consensus with ' +
      'a GATED vs ADVISORY distinction: gated (block/persist)->team-execution; advisory->feed the EXISTING adversarial_confidence ' +
      'ultracode trigger (already at :163); stop the unconditional `or needs_consensus` hard-force (:158). Add the KTD4 interrogation ' +
      'question + work-shape default to skills/plan/SKILL.md. Update operator-choice.md section 3.1. Cover AE1 (advisory->ultracode), ' +
      'AE2 (gated->team), the overlap case (both alternatives listed), and the docs-gating case in tests/test_saga_plugin.py.',
  },
]
const EPIC3 = [
  {
    label: 'U7 marketplace hook', model: 'sonnet', effort: 'high',
    prompt: "UNIT U7 (R13) -- the repo's FIRST hook: a plugin hooks/hooks.json that on edit JSON-parses marketplace.json/plugin.json " +
      'and asserts balanced brackets, BLOCKING on failure (exit 2) with the offending line. Wire it into the plugin that owns ' +
      'marketplace integrity; bump that plugin triad. Add tests/test_marketplace_hook.py (AE5).',
  },
  {
    label: 'U8 journal nudge hook', model: 'sonnet', effort: 'high',
    prompt: 'UNIT U8 (R14) -- a NON-blocking, NON-writing nudge hook: on a feat/fix commit that touches code but stages no ' +
      'docs/engineering-journal/ entry, surface a nudge. Docs-only/chore commits stay silent. Cross-repo-safe (degrade quietly where ' +
      'the journal dir is absent). Co-locate in the U7 hooks.json. Add tests/test_journal_nudge_hook.py (AE6).',
  },
  {
    label: 'U9 pre-push gate hook', model: 'sonnet', effort: 'medium',
    prompt: 'UNIT U9 (R15, KTD10) -- a single-source declarative tools/gate-manifest.* listing the pre-push gate (ruff format --check, ' +
      'ruff check, both validators, pytest) + a hook that runs it and REPORTS BY EXCEPTION (silent on pass). Settle the manifest format ' +
      'here. Add tests/test_pre_push_gate.py.',
  },
]
const EPIC2 = [
  {
    label: 'U10 spec + workflow emitter', model: 'opus', effort: 'high',
    prompt: 'UNIT U10 (R9 KEYSTONE) -- define the structured execution-spec (units, per-unit {model,effort}, return contracts, dependency ' +
      'barriers, escalations, ENUMERATED fan-out targets) and the emitter producing a runnable Claude Code workflow script from it. ' +
      'FAIL EMIT on a fan-out unit without enumerated targets (R10) or a pilot at a different tier than its fan-out (R3). Bake the ' +
      'workflow_structuredoutput_budget lesson (cap output, mandatory emit, skim, batch) into generated cheap-tier agents. This plan' +
      "'s own sibling .workflow.js is the worked reference. Add tests/test_workflow_emitter.py.",
  },
  {
    label: 'U11 team-exec emitter', model: 'sonnet', effort: 'high',
    prompt: 'UNIT U11 (R9 2nd emitter) -- a second emitter from the SAME U10 spec producing the ## Team Structure markdown ' +
      '(mirror team-execution/skills/team-execution/SKILL.md ~:234) + record the saga orchestration_ref pointer (never vendor ' +
      'team-execution machinery). Add tests/test_team_emitter.py.',
  },
  {
    label: 'U12 capability degrade', model: 'opus', effort: 'high',
    prompt: 'UNIT U12 (R11) -- every authored plan carries a runnable inline/serial baseline; on off-host resume re-check the Workflow ' +
      'tool, surface a one-line downgrade, recompile ONLY the orchestration tier down to team-execution/inline with unit specs + ' +
      'per-unit tiers PRESERVED, and record the downgrade. Add tests/test_capability_degrade.py (AE3: never error/silently-run-nothing).',
  },
  {
    label: 'U13 override-rate surface', model: 'sonnet', effort: 'high',
    prompt: 'UNIT U13 (R12 analysis) -- a /retro (or /optimize) pass that reads U3 recorded data and surfaces override-rate + over/under-' +
      'tier + budget-exhaustion signals. Zero-data reports "no data yet" (no divide-by-zero); read-only. Add tests/test_override_rate.py.',
  },
]
const EPIC4 = [
  {
    label: 'U14 cheap executor', model: 'sonnet', effort: 'high',
    prompt: 'UNIT U14 (R16) -- author ONE model:haiku, Bash-only, op-discriminated mechanical executor agent, dispatched by saga commands ' +
      'and INERT until called (no auto-trigger; unknown op rejected, not guessed). Wire the dispatch; bump the owning plugin triad. ' +
      'Add tests/test_mechanical_executor.py (haiku + Bash-only frontmatter; op-discrimination rejects unknown ops).',
  },
  {
    label: 'U15 release-triad guard', model: 'sonnet', effort: 'medium',
    prompt: 'UNIT U15 (R17) -- a guard that FAILS when plugin.json version, .claude-plugin/marketplace.json, and CHANGELOG.md disagree on a ' +
      'version-bearing change (fires only on version-bearing changes; message names the drifting surface). Add tests/test_release_triad.py.',
  },
  {
    label: 'U16 release rituals', model: 'sonnet', effort: 'medium',
    prompt: 'UNIT U16 (R18) -- a SHA-stamp stager + a stale-main-after-squash guard, THIS-REPO-LOCAL only (do not assume cross-repo; do not ' +
      'false-fire on a current main). Add tests/test_release_rituals.py.',
  },
]

// =============================================================================
// PREFLIGHT -- re-verify the grounding facts before fanning out (U1)
// =============================================================================
phase('Preflight')
const pf = await agent(
  SPEC +
    '\n\nUNIT U1 -- PREFLIGHT (read-only). Verify on origin/main of ' + REPO + ' (git fetch first): ' +
    '(a) the 4 agents home-lab-ops/homelab-sre, mission-control/sdlc-operator, unifi/unifi-network-ops, deploy/release-orchestrator ' +
    'have NO model: frontmatter line; (b) plugins/saga/scripts/saga.py:71 still defines ' +
    'ORCHESTRATION_MODES = ("inline", "team-execution", "cc-workflows-ultracode"); (c) plugins/saga/scripts/lifecycle_state.py still ' +
    'has the `or needs_consensus` hard-force (~:158) and the adversarial_confidence ultracode trigger (~:163); (d) the repo has ZERO ' +
    'hooks (no hooks/hooks.json, no "hooks" key in any plugin.json). Return PREFLIGHT_SCHEMA: ready=true iff ALL hold, else list drift.',
  { schema: PREFLIGHT_SCHEMA, label: 'U1 preflight', phase: 'Preflight', model: 'haiku', effort: 'low' }
)
if (!pf || !pf.ready) {
  throw new Error('HALT: preflight drift -- the plan was grounded against a different tree: ' + (pf ? pf.drift.join('; ') : 'no response'))
}
log('Preflight READY -- grounding facts confirmed on origin/main.')

// =============================================================================
// FIRST WAVE -- Epic 0, Epic 1, Epic 3 in parallel (all independent)
// =============================================================================
const wave1 = await parallel([
  () => runEpic('epic0', 'Epic 0 - Tiering', 'feat/campaign-epic0-tiering', EPIC0),
  () => runEpic('epic1', 'Epic 1 - Representation', 'feat/campaign-epic1-representation', EPIC1),
  () => runEpic('epic3', 'Epic 3 - Hooks', 'feat/campaign-epic3-hooks', EPIC3),
])
const [e0, e1, e3] = wave1

// BARRIER: Epic 2 needs Epic 0 + Epic 1 merged; Epic 4 needs Epic 0. Epic 3 is independent (warn, don't halt).
if (!e0 || !e0.merged) throw new Error('HALT: Epic 0 (tiering) did not merge -- Epic 2 and Epic 4 depend on it. ' + (e0 ? e0.reason : 'dead'))
if (!e1 || !e1.merged) throw new Error('HALT: Epic 1 (representation) did not merge -- Epic 2 depends on it. ' + (e1 ? e1.reason : 'dead'))
if (!e3 || !e3.merged) log('WARNING: Epic 3 (hooks) did not merge -- it is independent, so the run continues; review/land its PR: ' + ((e3 && e3.pr) || 'none'))
log('Barrier passed: Epic 0 + Epic 1 merged. Proceeding to authoring (Epic 2) + executor/guards (Epic 4).')

// =============================================================================
// SECOND WAVE -- Epic 2 (authoring) + Epic 4 (executor + guards) in parallel
// =============================================================================
if (budgetExhausted()) {
  log('Budget floor reached after wave 1 -- checkpointing. Resume with resumeFromRunId to run Epic 2 + Epic 4 + Final.')
  return { status: 'checkpointed-budget', wave1: wave1.map((w) => w && { epic: w.epic, merged: w.merged }) }
}
const wave2 = await parallel([
  () => runEpic('epic2', 'Epic 2 - Authoring', 'feat/campaign-epic2-authoring', EPIC2),
  () => runEpic('epic4', 'Epic 4 - Executor + guards', 'feat/campaign-epic4-guards', EPIC4),
])
const [e2, e4] = wave2
if (!e2 || !e2.merged) log('WARNING: Epic 2 (authoring) did not merge -- review its PR before Final: ' + ((e2 && e2.pr) || 'none'))
if (!e4 || !e4.merged) log('WARNING: Epic 4 (executor + guards) did not merge -- review its PR before Final: ' + ((e4 && e4.pr) || 'none'))

// =============================================================================
// FINAL -- full gate fleet-wide + journal + R-ID reconciliation (U17)
// =============================================================================
phase('Final')
const epicsLanded = [e0, e1, e3, e2, e4].filter((x) => x && x.merged).map((x) => x.epic)
const final = await agent(
  SPEC +
    '\n\nUNIT U17 -- FINAL verification + journal. Work in a fresh worktree ' + WT + '/final on branch feat/campaign-final off origin/main.\n' +
    '1) Run the FULL gate fleet-wide from that worktree (ruff format --check, ruff check, both validators, uv run pytest, uv run mypy plugins/) and confirm GREEN.\n' +
    '2) Write the campaign DECISIONS.md + LEARNINGS.md entries this campaign earned (KTD1-KTD10; the dead-wiring/source-fidelity lessons if any surfaced).\n' +
    '3) Write a reconciliation report under docs/analysis/2026-06-21-saga-tiering-execution-campaign-report.md mapping EVERY R-ID (R1-R18) to its landed unit ' +
    'and listing any unit whose epic did not merge (epics merged: ' + JSON.stringify(epicsLanded) + '). NO silent skips.\n' +
    '4) Gate, open a PR, poll the 5 required checks, and squash-merge when green (full hands-off). Remove the worktree.\n' +
    'Return FINAL_SCHEMA (rIdsTotal=18).',
  { schema: FINAL_SCHEMA, label: 'U17 final + journal', phase: 'Final', model: 'opus', effort: 'high' }
)

// ---- summary to the parent session (which notifies the operator) ----
return {
  status: final && final.merged ? 'complete' : 'incomplete-review-final',
  epicsMerged: epicsLanded,
  wave1: wave1.map((w) => w && { epic: w.epic, pr: w.pr, merged: w.merged }),
  wave2: wave2.map((w) => w && { epic: w.epic, pr: w.pr, merged: w.merged }),
  final: final || null,
  rIdCoverage: final ? final.rIdsCovered + '/' + final.rIdsTotal : 'unknown',
  note: 'Full hands-off run. Any epic with merged=false is left as an open PR for review (see wave summaries). ' +
    'Epic 3 is independent of the saga-execution epics. Resume incomplete runs with resumeFromRunId.',
}
