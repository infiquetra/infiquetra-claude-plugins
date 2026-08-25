---
title: Port the agent-launcher plugin from infiquetra-claude-plugins
repo: infiquetra-agent-plugins
type: capability
team: asgard
project: operations
status: Shaping
labels: capability, needs-plan
risk: medium
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# Port the agent-launcher plugin from infiquetra-claude-plugins

### Objective

Port the accepted `agent-launcher` Claude plugin from `infiquetra-claude-plugins` into `infiquetra-agent-plugins` through the established Agent Plugins portability workflow: the same shared single-session launch contract, the supported-client matrix passed, and adapter-specific limitations documented.

### Intent

Split from infiquetra-claude-plugins#777 by operator ruling G2 on the improve-claude-plugins orchestration contract (infiquetra-claude-plugins#814, 2026-08-24): that orchestration run is limited to the Claude Plugins repository, so the port is tracked here instead of as a closing requirement of #777. The source plugin is built and accepted first in `infiquetra-claude-plugins` under #777's Claude-side acceptance criteria; this port begins only after that acceptance, adapts the shared launch contract rather than copying Claude-specific behavior, and inherits #777's port-relevant stop condition: stop if the accepted plugin behavior cannot be represented without a vendor-specific hidden path.

### Out-of-scope / non-goals

- No Claude-side rework of the accepted plugin — changes to the source plugin route back to `infiquetra-claude-plugins`.
- No new vendor or model registry; the live `agents` wrapper and Herdr state remain authoritative (#777's boundary).
- No Orchestrate behavior changes in either repository.
- Not part of the infiquetra-claude-plugins#814 orchestration run and not a blocker for closing #777 once its Claude-side criteria are met.

### Files expected to change

- `ports/agent-launcher.json` (new port descriptor, following the existing `ports/` descriptor convention)
- `plugins/agent-launcher/` (generated package from the portability workflow)
- `tests/` (portability and client-matrix coverage for the ported plugin)
- Release/metadata surfaces per this repository's conventions in the shipping PR

### Tests to add or update

- Portability and supported-client-matrix tests for the ported plugin per the established porting runbook.
- Packaging smoke coverage for the generated package.

### Context library links

- infiquetra-claude-plugins#777 — the source capability (Claude-side build, acceptance, and shared-contract boundary)
- infiquetra-claude-plugins#814 — the orchestration contract carrying the G2 split ruling (2026-08-24)

### Acceptance criteria

- [ ] Start gate honored: `gh issue view 777 -R infiquetra/infiquetra-claude-plugins --json state -q .state` returns `CLOSED` (Claude-side accepted and released) before port implementation begins.
- [ ] `uv run pytest` — expected: green in this repository with the ported plugin's portability and client-matrix tests included.
- [ ] `test -s ports/agent-launcher.json` — expected: the port descriptor exists and is non-empty, and adapter-specific limitations are documented in it or in the ported plugin's documentation.
- [ ] The shipping PR updates this repository's release/metadata surfaces per its conventions, verified in PR review.

### Verification

```bash
cd /Users/jefcox/workspace/infiquetra/infiquetra-agent-plugins
uv sync --all-extras
uv run pytest
test -s ports/agent-launcher.json && echo descriptor-present
```

### Notes / conventions

Adapt the shared contract; do not copy Claude-specific behavior (the source issue's pre-mortem names this failure mode). Provenance: created 2026-08-24 by the G2 ruling; linked as a native sub-issue of infiquetra-claude-plugins#777 so the decomposition stays visible without blocking it.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-agent-plugins/issues/22
- Number: 22
- Created at: 2026-08-25T04:09:33.818457+00:00

