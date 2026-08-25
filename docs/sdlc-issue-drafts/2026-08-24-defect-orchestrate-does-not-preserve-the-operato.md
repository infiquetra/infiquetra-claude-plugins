---
title: [DEFECT] Orchestrate does not preserve the operator company-account choice across worker launches
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# [DEFECT] Orchestrate does not preserve the operator company-account choice across worker launches

### Objective

An explicit operator account selection must survive into every worker launch and be verified after
launch, without changing global defaults — today it silently reverts to the personal account.

## Observed behavior

With the coordinator session running under the company account (`CLAUDE_CONFIG_DIR` →
`~/.claude-company`, jeff@infiquetra.com), four worker sessions launched through the `agents`
wrapper on 2026-08-23 (~23:55Z, coordinator session 308ed475-2221-4f97-893d-2c9904c521ec, Herdr
workspace w7M) all came up on the PERSONAL account: their transcripts were created under
`~/.claude/projects/` (default root, `~/.claude.json` → namredips@gmail.com). The launched pane
receives a fresh login environment, so the caller's `CLAUDE_CONFIG_DIR` never reaches it. Recovery
required tearing down all four tabs and relaunching with the wrapper-private `--company-account`
flag, after which all four transcripts landed under `~/.claude-company/projects/` (verified, plus
`jefcox [company]` in each pane statusline).

Orchestrate knows the flag exists —
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:330` documents that
`--company-account` "swaps the configuration directory before the tool starts" — but nothing in the
plan schema, launch argv assembly (`orchestrate.py:327-343`), or post-launch checks carries or
verifies an operator account selection for launched units.

## Operator impact

Workers on the wrong account mean the wrong billing and rate-limit pool, a different plugin tree
(`~/.claude` and `~/.claude-company` diverge on this machine), and transcripts persisted under the
wrong identity — silently. Invisible until someone checks transcript locations.

## Evidence and provenance

- Coordinator session
  `~/.claude-company/projects/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/308ed475-2221-4f97-893d-2c9904c521ec.jsonl`
  (2026-08-23): first-launch account check found all four worker session IDs only under
  `~/.claude/projects/`; post-relaunch check found all four only under `~/.claude-company/projects/`.
- Wrapper mechanics: `~/.local/bin/agent-herdr` — `COMPANY_ACCOUNT_FLAGS` (line ~84),
  `_company_account_args` (lines ~361-392).
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`, finding E2 (C-1).
- The wrapper's own undocumented flag surface is dependency context routed to Home Lab System
  Updates — this issue owns the Orchestrate side only.

### Intent

Add an explicit account selection to the run/unit plan schema, translate it into the correct
launcher flags for every worker launch (for claude: `--company-account`), and verify the launched
account post-launch, failing the unit loudly on mismatch.

### Out-of-scope / non-goals

- Changing global account defaults, machine login environments, or the `agents`/`agent-herdr`
  wrapper's flag surface and help text (routed to Home Lab System Updates).
- Non-claude vendors' account semantics beyond passing through whatever selection the plan makes
  expressible for them.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_account.py` (new)
- `plugins/orchestrate/.claude-plugin/plugin.json`, `plugins/orchestrate/CHANGELOG.md`,
  `.claude-plugin/marketplace.json` (release-surface parity)

### Tests to add or update

- `tests/test_orchestrate_account.py` (new): argv emission includes the account flag for a plan
  selecting the company account; omission when no selection; the post-launch verification path
  marks a simulated mismatch (worker transcript under the personal root) as a launch failure.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/3-orchestrate-account-propagation.md`
  (audit task dir — ephemeral; durable anchors are the session paths above)

### Acceptance criteria

- [ ] `uv run pytest tests/test_orchestrate_account.py -q` passes — argv emission and
      mismatch-detection paths covered.
- [ ] `python3 plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py go` with a
      company-account plan (stubbed launcher in tests) emits `--company-account` for every claude
      unit launched under that selection.
- [ ] A verified account mismatch marks the unit launch failed with a named state — never a
      silently personal worker (asserted in tests).
- [ ] `grep -n "account" plugins/orchestrate/skills/orchestrate/SKILL.md` documents the plan-level
      account field and the post-launch verification behavior.

### Verification

```bash
uv run pytest tests/test_orchestrate_account.py -q
grep -n "account" plugins/orchestrate/skills/orchestrate/SKILL.md
scripts/gate.sh
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24). The 2026-08-23 coordinator incident is the reference reproduction.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/781
- Number: 781
- Created at: 2026-08-24T03:58:16.684716+00:00

