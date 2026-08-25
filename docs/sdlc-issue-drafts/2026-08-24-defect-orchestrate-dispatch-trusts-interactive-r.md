---
title: [DEFECT] Orchestrate dispatch trusts interactive_ready and loses first prompts to startup dialogs
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# [DEFECT] Orchestrate dispatch trusts interactive_ready and loses first prompts to startup dialogs

### Objective

Orchestrate must confirm that a dispatched task prompt was actually accepted by the worker session
and surface a loud failure when it was not, instead of trusting Herdr's readiness signal alone.

## Observed behavior

During Team Mimir orchestration on 2026-08-23 (session b31ec85e-82d5-4a00-aa18-e82cc22b2284,
"Hermes update model design discovery"), a freshly launched worker session repeatedly still showed a
vendor startup dialog — a folder-trust prompt (Claude Opus into a new worktree) or Antigravity's
"Verifying your account" gate (concurrent same-account agy launches) — while Herdr reported the
agent `interactive_ready`. The first task prompt sent in that window disappeared silently: the pane
showed no new input and the token counter stayed at 0/1.0M. At least four separate occurrences in
one session; the session's working tell became "watch the token counter move," not the readiness
flag or the prompt command's exit status.

Orchestrate's own code acknowledges the gap: the comment at
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:1368` states that sending into that
gap "does not fail," and dispatch gates only on `row.get("interactive_ready")`
(`orchestrate.py:1413`).

## Operator impact

A swallowed brief means a worker sits idle believing it was never given work — or later reports
"nothing to do" confidently. Each occurrence cost a manual detection-and-resend round trip. In an
unattended run this is silent work loss.

## Evidence and provenance

- `~/.claude/projects/-Users-jefcox-workspace-infiquetra-team-mimir/b31ec85e-82d5-4a00-aa18-e82cc22b2284.jsonl`
  line 4921 (2026-08-23T14:16:27Z) "Opus is sitting on a folder-trust prompt which likely swallowed my brief";
  line 4947 (14:17:31Z) "second time this session a trust prompt has eaten a first send";
  line 6016 (15:42:40Z) "the session reported interactive_ready before the CLI could actually accept work";
  line 6457 (16:52:02Z) "the tell is the token counter, not the readiness flag";
  line 7560 (22:13:00Z) "Both deliveries were swallowed on first send".
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`, finding D1 (lane1-01).
- Herdr's optimistic readiness (herdr SKILL.md:127) is dependency context only — this issue owns the
  Orchestrate side. Do not file Herdr changes here.

### Intent

Make prompt delivery a verified step of dispatch: after `go` sends a unit its first prompt,
Orchestrate observes an acceptance signal before recording the unit as tasked, and turns
non-acceptance into a named, visible failure state with a bounded retry policy.

### Out-of-scope / non-goals

- Fixing Herdr's readiness detection or vendor CLI startup dialogs (dependency context; routed
  elsewhere).
- The qwen pane-typing fallback (already documented in SKILL.md; excluded by operator triage).
- Token counting, spend ceilings, or any of the archived full-implementation scope.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_delivery.py` (new)
- `plugins/orchestrate/.claude-plugin/plugin.json`, `plugins/orchestrate/CHANGELOG.md`,
  `.claude-plugin/marketplace.json` (release-surface parity)

### Tests to add or update

- `tests/test_orchestrate_delivery.py` (new): a stubbed pane that reports `interactive_ready` but
  does not accept input — assert the unit is never recorded tasked, a named delivery-failure state
  appears, and the bounded retry policy fires; plus the happy path (accepted prompt → tasked).

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/1-orchestrate-prompt-delivery.md`
  (audit task dir — ephemeral; the durable anchors are the transcript paths above)

### Acceptance criteria

- [ ] `uv run pytest tests/test_orchestrate_delivery.py -q` passes — includes a regression case
      simulating a ready-reporting pane that cannot accept input, asserting a loud named failure and
      no tasked state.
- [ ] `python3 plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py status` (exercised in
      the test via stubbed state) shows a named delivery-failure state (for example
      `prompt_undelivered`) for a unit whose first prompt was not accepted — never a silently
      tasked unit.
- [ ] `grep -n "deliver" plugins/orchestrate/skills/orchestrate/SKILL.md` returns at least one hit
      documenting the delivery-confirmation signal and the retry-or-fail policy.

### Verification

```bash
uv run pytest tests/test_orchestrate_delivery.py -q
grep -n "deliver" plugins/orchestrate/skills/orchestrate/SKILL.md
scripts/gate.sh   # full gate green before PR, per repo rule
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24). Related context, not duplicates: #773, #772, closed #390.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/779
- Number: 779
- Created at: 2026-08-24T03:57:33.989938+00:00

