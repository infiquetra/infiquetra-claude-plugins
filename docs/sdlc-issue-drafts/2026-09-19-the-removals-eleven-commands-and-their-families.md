---
title: The removals: eleven commands and their families, team-execution archived, hooks and rules retired, tests shrunk, release as saga 1.0.0
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: high
mode: execute
handoff_maturity: requirements-ready
---

# The removals: eleven commands and their families, team-execution archived, hooks and rules retired, tests shrunk, release as saga 1.0.0

### Objective

In one release with the chain: remove `/outcome`, `/loop`, `/resume`, `/handoff`, `/optimize`, `/pulse`, `/delegation-audit`, `/promote`, `/engines`, `/tier`, and `/fleet-doctor` with their script families (the outcome coordinator, the engine registry family after its ratings migrate to A3, the concurrency, lease, envelope, ceremony, receipt, teardown, and undo family, the reversibility certificate, the ledgers, the closure and completeness gates except the consensus scorer, the execution spec and team emission, the spend readers, the delegation audit), the delegation tripwire and stop-audit hooks, the team-spawn residency and team-teardown hooks, the mechanical-executor and readonly-verifier agents, saga's private lens roster, the four SVG assets and the docs model of the old atlas, and the tests of every removed module; archive the team-execution plugin with a final changelog entry pointing at the roles library and remove its vendored shim; replace the project instruction that review-class spawns must use `saga:readonly-verifier` with a worktree (and delete `references/sandbox-spawn-sites.md`) by "review roles run as roster sessions in their own worktrees"; shrink fleet-core to the modules still imported plus the staffing component; bump every release surface (saga 1.0.0, orchestrate 5.0.0, agent-launcher, fleet-core, mission-control, the marketplace, changelogs, drift-guard tests); install into both plugin trees and verify both.

### Intent

Thirteen commands remain: `/plan`, `/doc-review`, `/work`, `/code-review`, `/qa`, `/retro`, `/office-hours`, `/ideate`, `/brainstorm`, `/spec`, `/investigate`, `/strategy`, `/founder-review` with its alias. Decided 2026-09-19 (SR R10, R11, R14, R15, R26, R28, question 3): everything goes in the same release, nothing deferred. About 50,000 of saga's 61,856 script lines and 5,300 of team-execution's 8,877 lines are removed or archived.

### Inputs inventory

- A3 through A12 (A3, A5, A6, A7, A8, A9, A10, A11, A12) — every command and script family this release removes must first have its replacement landed in these cards; A13 is the closing release, not a standalone change.
- `research-plugin-census.md` sections 1, 5, 6, 7 in the inputs folder — the line-count and command-surface inventory this card's acceptance criteria check against.
- The plugin-install registry skew memory — both installed plugin trees must be verified after this release, per the acceptance criteria.

### Out-of-scope / non-goals

- No removal of the shaping commands, `/qa`, `/retro`, `/strategy`, or `/founder-review`.
- No weakening of the gate's coverage contract; tests are deleted with their modules, not marked advisory.
- No phased rollout.

### Files expected to change

- `plugins/saga/commands/` (24 files to 14), `plugins/saga/skills/{outcome,loop,resume,handoff,optimize,pulse,delegation-audit,promote,fleet-doctor}/` (removed), `plugins/saga/scripts/` (the families listed), `plugins/saga/hooks/` (four hook files and their registrations), `plugins/saga/agents/`, `plugins/saga/references/` (lens roster, engine registry, sandbox-spawn-sites), `plugins/saga/docs/assets/`
- `plugins/team-execution/` (archived), `plugins/fleet-core/scripts/fleet_commons/` (shrunk)
- `CLAUDE.md` (the sandbox-spawn rule), `.claude-plugin/marketplace.json`, every touched plugin's `plugin.json` and `CHANGELOG.md`
- `tests/` (every test of a removed module)

### Tests to add or update

- `tests/test_command_surface.py`: exactly the thirteen commands (fourteen files) exist and each loads its skill.
- `tests/test_no_lease_broker_readd.py` stays; a sibling asserts none of the removed script modules is importable.
- The gate's coverage check against `ci.yml` stays green; coverage stays at or above 80 percent on the remaining code.

### Context library links

- coding_standards: _none_

General references:
- SR sections 6A, 7; `research-plugin-census.md` sections 1, 5, 6, 7 in the inputs folder; the plugin-install registry skew memory (both trees must be verified)

### Acceptance criteria

- [ ] `ls plugins/saga/commands | wc -l` prints 14, and `for c in outcome loop resume handoff optimize pulse delegation-audit promote engines tier fleet-doctor; do test ! -e plugins/saga/commands/$c.md || echo "$c still present"; done` prints nothing.
- [ ] `test ! -d plugins/team-execution` and `jq -r '.plugins[].name' .claude-plugin/marketplace.json | grep -c team-execution` prints 0.
- [ ] `grep -c "readonly-verifier" CLAUDE.md` prints 0 and `test ! -f plugins/saga/references/sandbox-spawn-sites.md`.
- [ ] `find plugins/saga/scripts -name '*.py' | xargs cat | wc -l` prints under 15,000.
- [ ] `GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh` exits 0, and both installed trees report the same versions as the repository.

### Verification

```bash
ls plugins/saga/commands | wc -l
find plugins/saga/scripts -name '*.py' | xargs cat | wc -l
cat /tmp/gate-run/result.txt
for r in ~/.claude ~/.claude-company; do jq -r .version $r/plugins/marketplaces/infiquetra-plugins/plugins/saga/.claude-plugin/plugin.json; done
```

### Failure modes / pre-mortem

A surviving skill imports a removed module (the importability test catches it); the release-surface drift guard demands a second bump when the work splits across stacked pull requests (bump again); one plugin tree self-updates and the other does not (hand-repair, then verify both).

### Stop conditions

Stop if the gate cannot stay green without marking a step advisory, or if a surviving command needs a removed module and no thin replacement exists.

### Risk

high

the largest deletion in the repository's history; every removal is tied to a decision in SR section 0 and guarded by the command-surface, importability, and gate checks.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1030
- Number: 1030
- Created at: 2026-09-19T14:47:30.239137+00:00

