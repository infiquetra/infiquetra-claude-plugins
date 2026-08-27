---
title: The agent-launcher skill oversells agents --dry-run as a preflight that validates model effort and account
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# The agent-launcher skill oversells `agents --dry-run` as a preflight that validates model, effort, and account

### Objective

Make the agent-launcher skill state precisely what `agents --dry-run` verifies and what it does not,
so callers stop relying on it to catch a bad model, effort, or account.

### Intent

`plugins/agent-launcher/skills/agent-launcher/SKILL.md` instructs:

> `--dry-run` previews any launch without executing it. **Use it before every creation command.**

Read plainly, that is an instruction to use dry-run as the preflight. It is not one. Verified
against the installed launcher:

```
$ agents --dry-run --task probe --workspace w7M claude -m definitely-not-a-real-model-xyz
command=... --kind claude -- -m definitely-not-a-real-model-xyz && exec herdr
$ echo $?
0
```

```
$ agents --dry-run --task probe2 --workspace w7M claude -m claude-opus-5 \
    --reasoning-effort not-a-real-effort --company-account
command=... -- -m claude-opus-5 --reasoning-effort not-a-real-effort --company-account && exec herdr
$ echo $?
0
```

A deliberately nonexistent model passes. An invalid reasoning effort passes. The account flag is
passed through unchecked. Dry-run echoes the command it *would* run; it does not judge whether that
command is answerable.

**Scope, stated plainly.** The `agents` binary lives at `~/.local/bin/agents` and is **not** source
in this repository, so the missing validation cannot be fixed here. What can be fixed here — and
what actually caused the harm — is the guidance that invites callers to trust it.

The skill already models this honesty correctly two paragraphs earlier, where it explains that
"model and permission stay `requested_only` because `herdr agent list` does not publish them." That
caveat is exactly right and is simply missing from the dry-run guidance.

This matters for unattended runs. A coordinator that dry-runs a fleet, sees exit 0, and dispatches
will discover the bad model only when a worker fails to start — by which time worktrees, branches,
and a run record already exist.

### Out-of-scope / non-goals

- Do not attempt to add validation to the external `agents` binary from this repository.
- Do not remove or discourage `--dry-run`; what it does verify is genuinely useful.
- Do not restate the launcher's full flag surface; correct the specific claim.
- Do not change launch, close, receipt handling, or ownership semantics.

### Files expected to change

- `plugins/agent-launcher/skills/agent-launcher/SKILL.md`
- `plugins/agent-launcher/README.md`
- `plugins/agent-launcher/tests/test_launcher_contract.py`
- Agent Launcher release surfaces required by repository policy

### Tests to add or update

- Assert the dry-run guidance states what is **not** validated: model, reasoning effort, account.
- Assert the guidance no longer implies dry-run is sufficient preflight on its own.
- Assert the README and the skill agree, so the two surfaces cannot drift apart.
- Mutation-prove it: restoring the unqualified "use it before every creation command" wording alone
  must fail the test.

### Context library links

- The overselling claim: `plugins/agent-launcher/skills/agent-launcher/SKILL.md`, the `--dry-run` paragraph
- The correctly-hedged neighbour to imitate: the same file's `requested_only` explanation of model and permission
- Reproduction: `agents --dry-run` with a nonexistent model and an invalid effort, both exit 0
- External binary, out of this repository's reach: `~/.local/bin/agents`
- Discovery context: Auralis preflight on installed Orchestrate 3.0.7
- Launch contract origin: issue 777, pull request 827

### Verification

```bash
uv run pytest plugins/agent-launcher/tests/test_launcher_contract.py -q
uv run pytest tests/test_agent_launcher_plugin.py -q
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] The skill states that `--dry-run` does not validate model, reasoning effort, or account.
- [ ] It names what dry-run **does** verify, so it stays useful rather than merely discredited.
- [ ] The README carries the same statement and a test holds the two surfaces together.
- [ ] The correction is testable and fails if the unqualified wording returns.
- [ ] `bash scripts/gate.sh` exits 0 with Agent Launcher release surfaces aligned.

### Notes / conventions

Recorded deliberately as a **documentation defect in this repository**, not as a launcher product
defect, because the launcher is not ours to change here. If the external launcher later gains real
validation, this guidance should be revisited rather than simply deleted.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/880
- Number: 880
- Created at: 2026-08-27T01:00:46.446946+00:00

