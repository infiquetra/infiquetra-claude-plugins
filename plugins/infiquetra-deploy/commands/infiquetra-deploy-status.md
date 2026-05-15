---
name: infiquetra-deploy-status
description: Report latest nonprod and production deployment states from GitHub Deployments
argument-hint: "[repo] [--format table|json]"
---

Query deployment state using the bundled helper script.

Resolve the helper path as `${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py` when the plugin is installed. In a cloned plugin repository, use `plugins/infiquetra-deploy/scripts/query_deployments.py`.

## Required behavior

1. Parse `$ARGUMENTS` as:
   - `[repo]`: optional repo in `name`, `owner/name`, or git remote URL form
   - `--format table|json`: optional output format, default `table`
2. If repo is omitted, resolve it from the local git `origin` remote.
3. Query the GitHub Deployments API through `gh api` for both default environments:
   - `nonprod`
   - `production`
4. Use public GitHub CLI defaults unless the repo remote resolves to a different host.
5. Do not infer production status from tags alone. Report GitHub Deployment states.

## Commands to run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py" [repo] --format table
```

For JSON output:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py" [repo] --format json
```

## Output expectations

Report the latest deployment state for `nonprod` and `production`, including environment, state, deployment ID, ref, short SHA, timestamp, and target URL when available.
