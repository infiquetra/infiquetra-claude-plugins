---
title: Cross-runtime Outcome coordination: shared authority, discovery, resume, and lease-safe handoff
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Shaping
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
approval_state: approved
---

# Cross-runtime Outcome coordination: shared authority, discovery, resume, and lease-safe handoff

### Objective

Allow one Saga Outcome to be discovered, reconciled, advanced, and attended safely from Claude Company and Codex without either runtime creating a competing source of truth.

### Intent

Define and ship a cross-runtime Outcome coordination contract. The committed outcome branch and GitHub completion evidence remain canonical. Same-clone runtimes share the git-common-dir coordination store; different clones or hosts reconstruct from the committed specification plus GitHub. Runtime-local Claude and Codex directories may hold caches, transcripts, or protected launch receipts, but never canonical Outcome status. Discovery by Outcome ID, version compatibility, lease and idempotency behavior, and explicit handoff receipts must prevent duplicate dispatch when both runtimes operate on the same Outcome.

### Out-of-scope / non-goals

- Making `~/.claude-company` or `~/.codex` a second canonical Outcome store.
- Copying mutable coordination caches between hosts.
- Giving either runtime authority to overwrite GitHub completion evidence.
- Replacing repository worktrees, GitHub issues, or Operations board state.
- Changing Outcome business semantics unrelated to cross-runtime coordination.

### Files expected to change

- `plugins/saga/scripts/outcome.py`
- `plugins/saga/scripts/outcome_store.py`
- `plugins/saga/scripts/outcome_worktrees.py`
- `plugins/saga/scripts/outcome_dispatcher.py`
- `plugins/saga/skills/outcome/SKILL.md`
- `tests/test_outcome_cross_runtime.py`
- `plugins/saga/CHANGELOG.md`
- `docs/engineering-journal/DECISIONS.md`

The implementation plan must identify the corresponding `infiquetra-codex-plugins` parity and release surfaces rather than hiding cross-repository work in one pull request.

### Tests to add or update

- Cross-runtime Outcome discovery by repository and Outcome ID.
- Claude-to-Codex and Codex-to-Claude resume and attend fixtures.
- Same-clone shared coordination-store behavior.
- Different-clone deterministic reconstruction from spec plus GitHub.
- Concurrent advance protection using leases and idempotency keys.
- Version-skew and stale-receipt fail-closed cases.

### Context library links

_none_

### Inputs inventory

- `plugins/saga/scripts/outcome.py` and `outcome_store.py` in `infiquetra-claude-plugins` — upstream authority, storage, reconciliation, and dispatch behavior.
- The corresponding Saga implementation and compatibility vocabulary in `infiquetra-codex-plugins` — Codex runtime parity surface.
- `team-mimir` Outcome `team-mimir-autonomous-delivery` — live cross-runtime fixture with a committed Outcome branch, shared git-common-dir state, and observed Claude/Codex history.
- GitHub issues, pull requests, and Operations project fields — canonical completion and operator-visible state.
- `~/.claude-company` and `~/.codex` runtime-local histories and protected receipt locations — evidence and local authority boundaries, never canonical Outcome status.
- Related but non-duplicative issues: #376 (Objective ingestion drift), #437 (team-execution park/resume), #447 (session-substrate mining), and #450 (shared board reconciliation controller).

### Failure modes / pre-mortem

- Claude and Codex both advance the same ready leaf and create duplicate dispatches because leases or idempotency keys are scoped to runtime-local state.
- One runtime treats its transcript, report, or cache as authoritative and overwrites newer committed specification or GitHub evidence.
- Schema or plugin-version skew causes one runtime to accept state the other cannot safely interpret.
- A copied cross-host launch receipt is trusted outside its repository identity or freshness boundary.
- Outcome discovery creates a second branch, worktree, or Outcome ID instead of attaching to the existing durable identity.
- Cross-repository delivery is hidden in one issue or pull request, leaving the Codex port or release surface incomplete.

### Stop conditions

- HALT if the design requires `~/.claude-company`, `~/.claude`, or `~/.codex` to become a canonical Outcome-status store.
- HALT if cross-runtime resume cannot preserve one committed specification plus GitHub completion as the authority model.
- HALT if compatibility requires weakening repository-identity, filesystem-ownership, receipt-freshness, lease, or idempotency checks.
- HALT if concurrent-runtime tests can produce duplicate dispatch or completion side effects.
- HALT and split explicit linked work if Claude and Codex release units cannot be delivered and verified independently.

### Notes / conventions

Treat the git-common-dir store as a rebuildable coordination substrate, not portable canonical data. The plan must separate same-clone sharing from different-clone or different-host reconstruction and must name the upstream Claude unit plus the downstream Codex parity unit.

### Acceptance criteria

- [ ] A Claude-created Outcome can be discovered and read by Codex from the same repository without copying runtime-local state. Check: `uv run pytest tests/test_outcome_cross_runtime.py -k claude_to_codex_discovery`.
- [ ] A Codex-created Outcome can be discovered and read by Claude Company with the same derived state. Check: `uv run pytest tests/test_outcome_cross_runtime.py -k codex_to_claude_discovery`.
- [ ] Two runtimes advancing the same ready leaf cannot produce duplicate dispatch or completion events. Check: `uv run pytest tests/test_outcome_cross_runtime.py -k concurrent_advance_single_dispatch`.
- [ ] A second clone or host reconstructs equivalent status from the committed Outcome specification and GitHub evidence without importing the first clone coordination cache. Check: `uv run pytest tests/test_outcome_cross_runtime.py -k cross_clone_reconstruction`.
- [ ] Runtime-local Claude and Codex paths are rejected as canonical status stores while protected launch receipts retain explicit local authority and reconciliation semantics. Check: `uv run pytest tests/test_outcome_cross_runtime.py -k runtime_local_not_canonical`.
- [ ] Version skew between Claude and Codex Saga schemas fails closed with an actionable compatibility receipt. Check: `uv run pytest tests/test_outcome_cross_runtime.py -k version_skew_halts`.
- [ ] The Claude plugin change and required Codex parity or port work are represented as explicit release surfaces and linked work, not one hidden cross-repository change. Check: plan and release checklist review.
- [ ] Full repository quality gates pass. Check: `uv run pytest` and the repository lint, type, and security commands.

### Verification

```bash
uv run pytest tests/test_outcome_cross_runtime.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```

### Handoff maturity

requirements-ready

### Suggested next action

Use `saga:plan` on this issue to define the shared-authority protocol, compatibility envelope, migration path, and separate Claude and Codex release units.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/579
- Number: 579
- Created at: 2026-07-14T04:00:45.569054+00:00

