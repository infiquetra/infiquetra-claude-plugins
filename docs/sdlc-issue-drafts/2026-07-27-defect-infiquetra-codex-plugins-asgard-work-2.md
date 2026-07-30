---
title: "defect(portability,tests): frozen-source port oracles skip silently in the one run that is authoritative"
repo: infiquetra-codex-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: high
mode: implement
handoff_maturity: requirements-ready
---

# defect(portability,tests): frozen-source port oracles skip silently in the one run that is authoritative

### Objective

Stop every cross-repo port oracle from disappearing from the authoritative full-suite gate. Today the
strongest tests in the port-contract suite — the ones that re-derive a port's frozen inventory from
the upstream Claude checkout — skip without comment in exactly the run this CI-free repository treats
as proof, and a green `0 failed` is reported over them.

### Intent

Two port-contract modules resolve the upstream Claude checkout the same way:

```
tests/test_lease_registry_forward_compat_port_contract.py:61-62
tests/test_codex_627_seam_refreeze_port_contract.py:64-65
    SOURCE_REPO_ENV     = "CODEX_PORT_SOURCE_REPO"
    DEFAULT_SOURCE_REPO = ROOT.parent / "infiquetra-claude-plugins"
```

`_source_repo()` returns the configured path if `CODEX_PORT_SOURCE_REPO` is set, else the sibling
directory, and returns `None` when the candidate has no `.git`. Every test gated on it then skips.

The failure is the interaction between that default and the repo's own gating rule. Because codex#56
leaves `.claude/` untracked, `scripts/build_legacy_workflow_inventory.py` refuses to run in the
primary tree, so **full-suite gates are mandated to run in a clean detached worktree**. A detached
worktree lives under the repo's own `.git/worktrees` path, or wherever `git worktree add` placed it —
never beside `infiquetra-claude-plugins`. So `ROOT.parent / "infiquetra-claude-plugins"` resolves only
in the primary tree, which is the one place the runbook forbids gating in. The default path is
therefore dead in every authoritative run by construction.

Measured on the `#54` port at `ec523cc`, clean detached worktree, whole repository:

| Invocation | Result |
|---|---|
| `PYTHONPATH=. uv run pytest -q` | `2781 passed, 8 skipped` |
| `CODEX_PORT_SOURCE_REPO=<claude-clone> PYTHONPATH=. uv run pytest -q` | `2789 passed, 0 skipped` |

All eight skips were frozen-source oracles. Four belonged to the `#54` port alone: the
`expected_count` / `inventory_sha256` re-derivation guard, the every-changed-path-has-a-row guard, the
range-not-stale guard, and the drift-predates-the-range guard. Those four are the module's entire
defense against the codex#45 P1 #5 defect — a file ported under zero contract rows — and they are
precisely the ones that vanish.

Two properties make this worse than an ordinary skip. First, it is **silent**: no skip reason names
the env var, so the run reports `8 skipped` with nothing telling the reader that the port's own
correctness oracles were among them. Second, it **fails open**: an unset variable weakens the gate
instead of stopping it, so every future port inherits the same hole and the omission compounds
per-port rather than being caught once.

Planning must choose the posture deliberately and state the rationale: fail loudly when the source
repo cannot be resolved (strongest, but breaks any environment without the sibling clone), skip with a
reason string that names `CODEX_PORT_SOURCE_REPO` and is surfaced in `-rs` output (weakest, preserves
today's behavior), or resolve through a recorded location — a repo-level config value, or the
manifest's own `source.repository_id` — so a detached worktree resolves correctly without operator
action. The third option removes the operator step entirely and is the one to beat.

### Out-of-scope / non-goals

- Fixing codex#56 (`.gitignore` omits `.claude/`). It is the reason clean worktrees are mandatory, but
  it is a separate one-line change and is separately owned.
- Adding CI to this repository. Real, and much larger; do not bundle it.
- Changing `scripts/port_contract.py`, the sealed CLI validator (KTD6). This defect lives in the
  per-port pytest gates and their source-repo resolution, not in the validator.
- The pre-existing collection-order failure in `tests/test_outcome_cross_runtime.py`. Same run,
  different mechanism, filed separately.
- Re-running or re-litigating any completed port's evidence. Ports already validated stay valid; this
  changes how future runs resolve the oracle, not what past runs concluded.

### Files expected to change

- `tests/test_lease_registry_forward_compat_port_contract.py` — the `_source_repo()` resolution and
  its skip posture.
- `tests/test_codex_627_seam_refreeze_port_contract.py` — the identical resolution, kept in step.
- `tests/conftest.py` — only if planning chooses a shared resolver rather than two per-module copies.
- `docs/portability/claude-to-codex-plugin-port-runbook.md` — the gate command every future port
  copies; it must state the resolution the fix lands on.
- `tests/test_port_contract.py` — the `"../infiquetra-claude-plugins"` reference at line 423, if the
  resolution mechanism moves.

### Tests to add or update

- Red-first: a test asserting that a run which cannot resolve the source repo does not silently pass —
  failing against the current tree, where it silently does.
- A test that the skip or failure message, whichever posture is chosen, contains the literal
  `CODEX_PORT_SOURCE_REPO`, so a reader of the output learns the remedy at the moment it matters.
- A guard that both port-contract modules resolve the source repo through one mechanism, so the next
  port cannot copy a third divergent resolver.
- Characterization (passes before and after): with `CODEX_PORT_SOURCE_REPO` correctly set, all twelve
  tests in the `#54` module still pass and the five per-port contracts still total 69 passed.

### Context library links

_none_

### Inputs inventory

- `tests/test_lease_registry_forward_compat_port_contract.py` and
  `tests/test_codex_627_seam_refreeze_port_contract.py` — the two modules carrying the resolver.
- `docs/portability/ports/*.json` — every existing port manifest; each one's `source.repository_id`
  is the candidate authoritative pointer for the resolve-through-a-recorded-location option.
- `docs/portability/claude-to-codex-plugin-port-runbook.md` and `docs/portability/provenance.md` —
  the governing runbook and its mandate.
- `scripts/port_contract.py` — read-only input. Sealed per KTD6; consulted for the manifest schema,
  never edited.
- An upstream `infiquetra-claude-plugins` clone — required by any posture that still re-derives from
  frozen source. Its absence is exactly the condition under test.
- Baseline measurement at `ec523cc`, clean detached worktree: `2781 passed, 8 skipped` unset versus
  `2789 passed, 0 skipped` set.

### Failure modes / pre-mortem

- **Most likely failure: the fix trades a silent skip for a broken gate.** Choosing fail-loud without
  a resolution path makes every environment lacking the sibling clone unable to run the suite at all,
  including a fresh clone on another host. Mitigation: pair any fail-loud posture with a resolution
  that works unattended, and prove it from a worktree created outside the workspace directory.
- **The resolver is fixed in two places and diverges again.** Two modules already carry byte-identical
  copies; a third port copies whichever it sees first. Mitigation: the guard asserting a single shared
  mechanism is an acceptance criterion, not an optional extra.
- **A recorded-location fix silently reads a stale pointer.** Resolving through the manifest's
  `source.repository_id` yields a repository name, not a local path; mapping name to path needs a rule
  that cannot quietly resolve to the wrong clone. Mitigation: verify the resolved checkout's origin
  remote before trusting it, and fail on mismatch.
- **Changing the gate retro-invalidates a completed port.** If the new resolution disagrees with what
  a past port recorded, a previously green contract turns red and the temptation is to weaken it.
  Mitigation: prior-port contracts are run unchanged before and after; any new red is a stop condition,
  not an edit target.
- **The measurement does not reproduce.** The 8-skip count is specific to `ec523cc` and shifts as ports
  are added. Mitigation: assert the property (no source-repo-gated test skips silently), never the
  count.

### Stop conditions

- Any change would touch `scripts/port_contract.py`. That validator is sealed under KTD6 — stop and
  re-scope rather than unfreeze it.
- A previously passing per-port contract turns red under the new resolution. Stop and re-derive; a
  passing gate that the fix breaks means the diagnosis is wrong.
- The chosen posture cannot be demonstrated from a worktree created outside
  `/Users/jefcox/workspace/infiquetra/`. That is the condition the defect is about; a fix that only
  works beside the sibling clone has not fixed it.
- Scope reaches into adding CI, fixing codex#56, or editing any `docs/validation/*` frozen evidence.
  All three are out of scope by construction; stop and file separately.
- Red-first cannot be demonstrated for the new assertion. Without an observed pre-fix failure there is
  no evidence the test binds anything.

### Acceptance criteria

- [ ] The authoritative gate no longer hides the oracles. In a clean detached worktree,
      `PYTHONPATH=. uv run pytest -q` reports `0 skipped` for both port-contract modules, or fails
      loudly naming `CODEX_PORT_SOURCE_REPO` — never a silent skip.
- [ ] The remedy is stated at the point of failure. `PYTHONPATH=. uv run pytest -q -rs 2>&1 | grep -c CODEX_PORT_SOURCE_REPO`
      returns non-zero whenever any source-repo-gated test does not run.
- [ ] Red-first is demonstrated. The new assertion is run against the pre-fix tree via
      `git stash && PYTHONPATH=. uv run pytest tests/test_lease_registry_forward_compat_port_contract.py -q; git stash pop`
      and shown failing, with the output pasted into the work-session record.
- [ ] Both modules resolve identically. `PYTHONPATH=. uv run pytest tests/ -q -k "port_contract"` reports
      `69 passed` with the source repo resolvable, and `git diff` shows the same resolution mechanism
      applied to both files.
- [ ] Prior ports are unaffected. `python3 scripts/port_contract.py validate --stage classification`
      exits `0` for every manifest under `docs/portability/ports/`.
- [ ] The runbook matches the code. `docs/portability/claude-to-codex-plugin-port-runbook.md` states
      the gate command that actually resolves the oracle, and `grep -c CODEX_PORT_SOURCE_REPO` on that
      file is non-zero if the chosen posture still requires the variable.
- [ ] Full gate green. In a clean detached worktree `PYTHONPATH=. uv run pytest -q` reports `0 failed`,
      and `python3 scripts/validate_codex_plugins.py` exits `0`.

### Verification

Only `PYTHONPATH=. uv run pytest` collects in this repo. The contrast below is the whole defect: the
same command, same commit, differing only by an environment variable that nothing in the run tells you
to set.

```bash
git worktree add --detach /tmp/codex-oracle ec523cc017e2f68716428ed6417e2194962d497b
cd /tmp/codex-oracle

# Default gate — the mandated one. Oracles skip, and nothing says so.
PYTHONPATH=. uv run pytest -q 2>&1 | tail -3
# Observed: 2781 passed, 8 skipped

# Same commit, variable set. The eight skips were all frozen-source oracles.
CODEX_PORT_SOURCE_REPO=/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins \
  PYTHONPATH=. uv run pytest -q 2>&1 | tail -3
# Observed: 2789 passed, 0 skipped

# Narrow it to the #54 port's own module.
PYTHONPATH=. uv run pytest tests/test_lease_registry_forward_compat_port_contract.py -q -rs
# Observed: 8 passed, 4 skipped — and no skip reason mentions CODEX_PORT_SOURCE_REPO
```

Evidence anchors, verified live at `main` `8fdbe36`:

```
tests/test_lease_registry_forward_compat_port_contract.py:61   SOURCE_REPO_ENV = "CODEX_PORT_SOURCE_REPO"
tests/test_lease_registry_forward_compat_port_contract.py:62   DEFAULT_SOURCE_REPO = ROOT.parent / "infiquetra-claude-plugins"
tests/test_lease_registry_forward_compat_port_contract.py:68-71 _source_repo() -> None when no .git
tests/test_codex_627_seam_refreeze_port_contract.py:64-65      the identical pair
tests/test_port_contract.py:423                                 "../infiquetra-claude-plugins"
```

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-codex-plugins/issues/67
- Number: 67
- Created at: 2026-07-27T00:56:44.872835+00:00

