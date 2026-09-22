---
title: Amend the sdlc for the run: working-software exit criterion, role hosting, element count, crosswalk, and pin
repo: infiquetra-sdlc
type: enhancement
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: enhancement, needs-plan
risk: low
mode: execute
handoff_maturity: requirements-ready
---

# Amend the sdlc for the run: working-software exit criterion, role hosting, element count, crosswalk, and pin

### Objective

Make the source of truth say what the simplified plugins will do: the implement step's exit criterion includes a branch preview deployment and scenario smoke where a repository declares a preview (the narrow reading decided 2026-09-19); roles are hosted as separate agent sessions by default with the roles library as the hosting contract; the scanner, validator, and monitor rows of the gate catalogue give way to the mechanical baseline; the run model's element count is made consistent (133 versus 117); the saga crosswalk is regenerated for the 14-command set; the saga pin moves from 0.157.1 to the release that ships this; and the gates table records the multi-lens code review as the authoritative pre-merge gate once the plugin consumes the generated roster.

### Intent

ADR-001 warns that the plugin must not get ahead of the sdlc. The plugin work in the parent card changes step 5, role hosting, and gate authority, so the sdlc moves first or in the same window (SR R21 to R23).

### Out-of-scope / non-goals

- No change to the post-merge functional test as the Verify entry.
- No change to the lens catalogue, thresholds, or the fifteen roles' names.
- No new open questions; the register stays empty or gains only what this card cannot settle.

### Files expected to change

- `docs/lifecycle/run-model.md` (step 5 text, the element-count table)
- `docs/roles/run-roles.md` (hosting default and the roles library reference)
- `docs/process/gate-catalogue.md` (scanner, validator, monitor rows)
- `docs/process/gates.md` (code review authority note)
- `docs/lifecycle/saga-crosswalk.md` (regenerated)
- `config/saga-plugin-pin.yaml`, `config/saga-docs-model.yaml`

### Tests to add or update

The documentation gate workflow (frontmatter, links, schema parity, generated regions) must stay green; the crosswalk generator's check must pass against the new command set.

### Context library links

- architecture_decisions: https://github.com/infiquetra/infiquetra-sdlc/blob/main/docs/adrs/adr-001-code-review-executor-boundary.md
- coding_standards: _none_

General references:
- SR sections 3, 6E, and 9 (question 1)

### Acceptance criteria

- [ ] `grep -n "preview" docs/lifecycle/run-model.md` shows the step 5 exit criterion naming a branch preview deployment and scenario smoke where a repository declares a preview.
- [ ] `grep -c "133" docs/lifecycle/run-model.md` and the coverage table agree on one total.
- [ ] `grep -n "plugin_version" config/saga-plugin-pin.yaml` shows the new saga version.
- [ ] The documentation gate workflow is green on the pull request.

### Verification

```bash
git -C ~/workspace/infiquetra/infiquetra-sdlc grep -n "preview" docs/lifecycle/run-model.md
git -C ~/workspace/infiquetra/infiquetra-sdlc grep -n "plugin_version" config/saga-plugin-pin.yaml
gh pr checks --repo infiquetra/infiquetra-sdlc <PR>
```

### Risk

low

documentation edits behind a documentation gate; the only consequence of error is a stale sentence.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium
