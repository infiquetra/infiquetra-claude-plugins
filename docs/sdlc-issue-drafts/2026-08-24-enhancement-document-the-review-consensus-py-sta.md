---
title: [ENHANCEMENT] Document the review_consensus.py state API or expose a supported command
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, needs-plan
risk: low
handoff_maturity: requirements-ready
---

# [ENHANCEMENT] Document the review_consensus.py state API or expose a supported command

### Objective

A session (or developer) driving saga's review-consensus state machine directly should succeed from
the documentation alone — inputs, outputs, valid call order, and one worked example — instead of
trial-and-erroring against exception messages.

## Observed behavior

While scoring a completed review cycle, the live agent-plugins orchestrator (session
939e7ee5-181f-4f11-a2fd-7ec978d73517, 2026-08-23T17:10-17:13Z) drove
`plugins/saga/scripts/review_consensus.py` directly and needed six failed attempts to discover the
calling convention: `inspect.signature(rc.record_cycle)` → `AttributeError: module
'review_consensus' has no attribute 'record_cycle'` (it is a method on `ReviewCycleState`);
`inspect.getdoc(...)` → `TypeError: 'NoneType' object is not subscriptable` (no docstring to
return); then four wrong-keyword constructions of `ReviewFinding`/`record_cycle` against
`ReviewConsensusError` messages before a working call. At repo HEAD 818fd684,
`ReviewCycleState.record_cycle` (review_consensus.py:1176-1186), `ReviewFinding` (:204), and
`evaluate_review_readiness` (:1706) carry no docstrings.

## Operator impact

Every session that must drive the state machine outside the skill's own emitter rediscovers the
parameter shapes by trial and error — six wasted tool calls in the observed case.

## Evidence and provenance

- `~/.claude/projects/-Users-jefcox-workspace-infiquetra-infiquetra-agent-plugins/939e7ee5….jsonl`
  line 1525 (2026-08-23T17:10:18Z) AttributeError; line 1536 (17:10:26Z) TypeError; four further
  failed constructions through 17:12:48Z.
- `plugins/saga/scripts/review_consensus.py` at HEAD 818fd684 (verified by direct read during the
  audit): no docstring on the three entry points above.
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`, finding E6 (lane2-02).

### Intent

Either (a) add docstrings to the public state entry points naming required inputs, valid call
order, and return types, plus one worked end-to-end example (record cycle → evaluate readiness); or
(b) expose a supported CLI subcommand for recording/evaluating cycles and make private internals
unmistakably private. Guard the chosen shape with a test so it cannot drift.

### Out-of-scope / non-goals

- Changing scoring or consensus behavior in any way.
- The separate saga:code-review behavior tracked in #778 (conditional lenses without approval).
- The consensus-kernel roadmap items (#403/#411/#412).

### Files expected to change

- `plugins/saga/scripts/review_consensus.py`
- `tests/test_review_consensus_docs.py` (new; or a doctest wired into the existing suite)
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
  `.claude-plugin/marketplace.json` (release-surface parity)

### Tests to add or update

- `tests/test_review_consensus_docs.py` (new): asserts the three entry points carry docstrings (or
  the supported command exists), and executes the worked example exactly as documented.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/6-review-consensus-api.md`
  (audit task dir — ephemeral; durable anchors are the transcript paths above)

### Acceptance criteria

- [ ] `python3 -c "import sys; sys.path.insert(0,'plugins/saga/scripts'); import review_consensus as rc; assert rc.ReviewCycleState.record_cycle.__doc__ and rc.ReviewFinding.__doc__ and rc.evaluate_review_readiness.__doc__"`
      exits 0 (option a), or the supported subcommand's `--help` documents record/evaluate (option b).
- [ ] `uv run pytest tests/test_review_consensus_docs.py -q` passes — the worked example runs
      exactly as documented.
- [ ] Anything not intended for direct use is unmistakably private (leading underscore or module
      docstring statement) — verifiable via `grep -n "private" plugins/saga/scripts/review_consensus.py`
      or the naming itself.

### Verification

```bash
python3 -c "import sys; sys.path.insert(0,'plugins/saga/scripts'); import review_consensus as rc; assert rc.ReviewCycleState.record_cycle.__doc__"
uv run pytest tests/test_review_consensus_docs.py -q
scripts/gate.sh
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

sonnet/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/784
- Number: 784
- Created at: 2026-08-24T03:59:08.805959+00:00

