---
title: Orchestrate plugin.json declares dependencies as an object; the Claude loader requires an array and rejects the whole plugin
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

# Orchestrate plugin.json declares dependencies as an object; the Claude loader requires an array and rejects the whole plugin

### Objective

Make the Orchestrate plugin load again under the live Claude Code plugin loader, so the
`/orchestrate` command is available and orchestration runs can start.

### Intent

`plugins/orchestrate/.claude-plugin/plugin.json` declares `dependencies` as a JSON **object**:

```json
"dependencies": {
  "agent-launcher": ">=1.0.0"
}
```

The live loader in Claude Code 2.1.246 requires `dependencies` to be an **array**. It does not
degrade or ignore the field — it rejects the entire manifest, so no part of Orchestrate loads and
`/orchestrate` is unavailable.

Reproduced against both the repository source and the installed cache:

```
$ claude plugin validate plugins/orchestrate
Validating plugin manifest: .../plugins/orchestrate/.claude-plugin/plugin.json

✘ Found 1 error:

  ❯ dependencies: Invalid input: expected array, received object

✘ Validation failed
$ echo $?
1
```

The installed 3.0.6 manifest is byte-identical to `origin/main` at `bf66ee5e`, so source and
installed copies fail the same way.

**Regression boundary.** The `dependencies` key was introduced by commit `28a881b3`, pull request
827 for issue 777 ("extract the shared single-session launch contract"), landed 2026-08-25. Every
Orchestrate release from 2.0.0 onward carries the object form and fails to load; 1.20.8 and earlier
omit the key entirely and validate clean.

| Orchestrate version | `dependencies` shape | `claude plugin validate` exit |
| --- | --- | --- |
| 1.20.0 | absent | 0 |
| 1.20.8 | absent | 0 |
| 2.0.0 | object | **1** |
| 3.0.0 | object | **1** |
| 3.0.3 | object | **1** |
| 3.0.6 (installed, and `main` at `bf66ee5e`) | object | **1** |

**Loader contract, established by probing Claude Code 2.1.246.** Three array shapes are accepted and
two forms are rejected:

| `dependencies` value | Result |
| --- | --- |
| `{"agent-launcher": ">=1.0.0"}` | rejected — `expected array, received object` |
| `["agent-launcher@>=1.0.0"]` | rejected — `dependencies.0: Invalid input` |
| `["agent-launcher"]` | accepted |
| `[{"name": "agent-launcher", "version": ">=1.0.0"}]` | accepted, including under `--strict` |
| `[]` | accepted |

Orchestrate is the only plugin in this repository that declares `dependencies` at all; the other
thirteen omit the key, which is why no other plugin is affected.

### Out-of-scope / non-goals

- Do not drop the `agent-launcher >=1.0.0` version floor. Issue 841 established it as a real
  requirement; the bare-name array form `["agent-launcher"]` would silently discard it.
- Do not patch the installed plugin cache directly. The fix belongs in source and must reach the
  cache through the supported install path.
- Do not add a `dependencies` key to any other plugin.
- Do not widen this into a general manifest-schema overhaul or a new CI workflow.
- Do not change Orchestrate behavior, commands, skills, or scripts.

### Files expected to change

- `plugins/orchestrate/.claude-plugin/plugin.json`
- `plugins/orchestrate/CHANGELOG.md`
- `.claude-plugin/marketplace.json`
- `tests/test_plugin_manifest_loader_contract.py` (new)

### Tests to add or update

Add `tests/test_plugin_manifest_loader_contract.py` with coverage that would have failed for the
3.0.6 manifest:

- Assert that every `plugins/*/.claude-plugin/plugin.json` which declares `dependencies` declares it
  as a JSON array, and that each element is either a plain name string or an object carrying a
  `name`. This is a pure-Python schema assertion and fails on the 3.0.6 object form.
- Assert each array element that is a string carries no `@version` suffix, since the loader rejects
  that spelling.
- Validate the packaged manifests against the **actual** loader by shelling out to
  `claude plugin validate --strict <plugin dir>` and requiring exit 0, skipped when the `claude`
  binary is unavailable so the suite still runs in environments without it.
- Prove the pure-Python leg is not vacuous by mutating a manifest copy to the object form in a
  temporary directory and confirming the check rejects it.

### Context library links

- Live loader that rejects the manifest: Claude Code 2.1.246, `claude plugin validate`
- Manifest at fault: `plugins/orchestrate/.claude-plugin/plugin.json`
- Commit that introduced the `dependencies` key: `28a881b3`, pull request 827 for issue 777
- Version floor this must preserve: issue 841, `agent-launcher >=1.0.0`
- Repository release procedure: `CLAUDE.md`, "Development Workflow" step 6
- Repository gate contract: `CLAUDE.md`, "Gate Coverage Contract"
- Completed run whose record must stay intact: issue 847, `.orchestrate/run-orch-2026-08-26-847-FINAL.json`

### Verification

```bash
uv run pytest tests/test_plugin_manifest_loader_contract.py -q
claude plugin validate --strict plugins/orchestrate
uv run ruff check tests/test_plugin_manifest_loader_contract.py
uv run ruff format --check .
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

Live proof, from a fresh company-account Claude process rather than source checks alone: the
installed manifest validates clean and `/orchestrate` is present in the plugin's command inventory.

### Acceptance criteria

- [ ] `plugins/orchestrate/.claude-plugin/plugin.json` declares `dependencies` as an array that
      preserves the `agent-launcher >=1.0.0` floor.
- [ ] `claude plugin validate --strict plugins/orchestrate` exits 0.
- [ ] A regression test fails against the 3.0.6 object form and passes against the fix.
- [ ] The packaged manifest is validated against the live loader contract, not only a hand-written
      schema.
- [ ] `plugin.json`, `.claude-plugin/marketplace.json`, and the newest `CHANGELOG.md` version agree.
- [ ] `bash scripts/gate.sh` exits 0.
- [ ] From a fresh company-account Claude process, Orchestrate loads with no manifest error and
      `/orchestrate` is actually available.

### Notes / conventions

This blocks starting the Auralis orchestration, which is why it is being fixed ahead of the queued
post-run work for issue 847. The completed issue 847 run and its archived final record at
`.orchestrate/run-orch-2026-08-26-847-FINAL.json` must remain intact.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/871
- Number: 871
- Created at: 2026-08-27T00:01:34.150784+00:00

