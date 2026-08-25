---
title: [EXPLORATION] Verify the muse skills install --json contract before workflows depend on an installed field
repo: infiquetra-claude-plugins
type: exploration
team: asgard
project: operations
status: Shaping
labels: exploration, research
risk: low
mode: research
handoff_maturity: requirements-ready
---

# [EXPLORATION] Verify the muse skills install --json contract before workflows depend on an installed field

### Objective

Establish, from the installed muse CLI itself, what the supported skills-install command is and
what its `--json` output actually contains — then correct whichever repo surface encodes the
current unverified assumption, instead of preserving it.

## Observed behavior

During unifi plugin staging (session 2cc86ea6-7168-4a88-bc8f-460f60524ff6 in
orch-s9-resync-unifi-201, 2026-08-22T22:17:32Z), a verification harness compared two
`muse skills install … --json` runs from two differently named source directories and crashed with
`KeyError: 'installed'` reading one of the two JSON outputs. The harness assumed an `installed` key
that at least one output did not carry. Not established: whether (a) muse's JSON contract differs
from the assumption, (b) the two runs returned differently shaped JSON because one failed for an
unrelated reason, or (c) the harness's assumption was simply wrong — the raw JSON outputs were not
captured in the transcript window.

## Operator impact

Muse is an integrated vendor across this repo's surfaces (the Orchestrate vendor table maps muse
model/effort flags; `plugins/saga/scripts/engine_session_runner.py` and fleet-core's
`tier_resolver.py` reference it), and skills-staging onto muse is part of the cross-vendor port
workflow. An unverified JSON-shape assumption in that path produces crashes instead of typed
results — and the operator has separately noted needing to know how to use Muse.

## Evidence and provenance

- `~/.claude/projects/-Users-jefcox-workspace-infiquetra-orch-s9-resync-unifi-201/2cc86ea6….jsonl`
  lines 575-576 (2026-08-22T22:17:32.918Z): `KeyError: 'installed'` from the two-install comparison
  harness (`stage.sh muse2 muse skills install … --json` vs `stage.sh muse …`).
- Repo muse touchpoints at HEAD 818fd684: `plugins/orchestrate/skills/orchestrate/SKILL.md` vendor
  table, `plugins/saga/scripts/engine_session_runner.py`,
  `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`. No in-repo file currently invokes
  `muse skills install` (verified by grep) — the observed call sites are session-authored staging
  harnesses in the port workflow.
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`,
  needs-investigation N5 (lane3 NI-2), accepted by operator triage 2026-08-24.

### Intent

Run the muse CLI's own help and one real skills-install against a scratch target, capture the
verbatim `--json` output for both success and failure, record the verified contract in the owning
repo surface, and correct (or declare clean) every repo-side reference to the assumed `installed`
field.

### Out-of-scope / non-goals

- Changing muse itself.
- Broad muse onboarding documentation beyond this command's contract.
- The unifi staging work the harness was serving (already landed).

### Files expected to change

- `docs/analysis/2026-08-muse-skills-install-contract.md` (new — the exploration findings record)
- Owning-surface correction as determined by the exploration (candidates:
  `plugins/orchestrate/skills/orchestrate/SKILL.md` vendor notes, or a port-workflow doc)

### Tests to add or update

- None mandated for the exploration itself; the follow-up correction (if code is touched) carries
  its own test per normal repo rules.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/8-muse-command-contract.md`
  (audit task dir — ephemeral; durable anchor is the transcript path above)

### Acceptance criteria

- [ ] `muse skills --help` output and one real `muse skills install <target> --json` run (success)
      plus one induced failure run are captured verbatim in
      `docs/analysis/2026-08-muse-skills-install-contract.md`.
- [ ] The findings doc states the verified JSON contract (success and failure shapes) and names the
      owning surface for it going forward.
- [ ] `grep -rn "installed" docs/analysis/2026-08-muse-skills-install-contract.md plugins/` shows
      no repo surface asserting an `installed` field unless the capture proves muse emits it.
- [ ] The exploration files the follow-up correction issue or records "no correction needed" in the
      findings doc.

### Verification

```bash
muse skills --help
grep -rn "installed" plugins/ | grep -v test  # post-exploration: only verified-contract references
```

Validation belongs in the exploration itself — no fresh reproduction was required to file (operator
instruction, 2026-08-24).

### Target repo / surface

`infiquetra/infiquetra-claude-plugins`. Findings land in `docs/analysis/2026-08-muse-skills-install-contract.md` (new). Candidate correction surfaces: `plugins/orchestrate/skills/orchestrate/SKILL.md` (muse vendor notes), `plugins/saga/scripts/engine_session_runner.py`, `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py` — plus the installed muse CLI itself as the read-only system under test.

### Mode

research — verify the installed muse CLI's skills-install command and `--json` output contract against a scratch target; record findings; no production code changes inside this exploration.

### Constraints

- Read-only toward muse except a scratch skills-install target; never modify muse itself.
- Repo changes limited to the findings document; any code/doc correction is a follow-up filing.
- Capture the muse CLI version alongside the contract so a later muse upgrade is distinguishable from a wrong capture.
- No fresh reproduction of the original KeyError required before starting (operator instruction, 2026-08-24).

### Risk

low — worst case is documenting a vendor contract that shifts on the next muse release; mitigated by version capture. No live-system or board mutations involved.

### Transfer notes

Origin: transcript audit 2026-08-23/24, needs-investigation N5 (lane3 NI-2), accepted by operator triage. The crashing harness was session-authored (`stage.sh muse2 muse skills install … --json`), not repo code — the KeyError may be the harness's own assumption. Evidence anchor: `~/.claude/projects/-Users-jefcox-workspace-infiquetra-orch-s9-resync-unifi-201/2cc86ea6….jsonl` lines 575-576 (2026-08-22T22:17:32Z). The operator has separately noted needing to know how to use Muse — findings should be written to serve that too.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/786
- Number: 786
- Created at: 2026-08-24T04:00:44.052033+00:00

