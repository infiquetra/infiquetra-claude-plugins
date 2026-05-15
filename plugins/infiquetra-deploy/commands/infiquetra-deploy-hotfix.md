---
name: infiquetra-deploy-hotfix
description: Create an explicit four-part production hotfix promotion tag
argument-hint: "<base-version> <hotfix-ref> [--increment N] [--repo <repo>] [--remote <remote>] [--back-merge-plan <plan>] [--dry-run]"
---

Guide a production hotfix promotion using the bundled helper script.

Resolve the helper path as `${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py` when the plugin is installed. In a cloned plugin repository, use `plugins/infiquetra-deploy/scripts/mint_tag.py`.

## Required behavior

1. Parse `$ARGUMENTS` as:
   - `<base-version>`: required `N.N.N` production base version
   - `<hotfix-ref>`: required git ref to tag
   - `--increment N`: optional positive fourth version part, default `1`
   - `--repo <repo>`: optional repo in `name`, `owner/name`, or git remote URL form
   - `--remote <remote>`: optional git remote, default `origin`
   - `--back-merge-plan <plan>`: required plan text for non-dry-run hotfix pushes
   - `--dry-run`: preview without creating or pushing a tag; still validates the local and remote tag are absent
2. Create an explicit four-part production tag: `production-v<base-version>.<increment>`.
3. Delegate tag creation to `mint_tag.py hotfix` with the explicit hotfix ref.
4. Require a back-merge plan before executing a non-dry-run hotfix.
5. Pass `--back-merge-plan "<plan>"` only after the operator states that plan; the helper rejects non-dry-run hotfixes without it.
6. Reject tag creation when an explicit `--repo` does not match the configured push remote.
7. Never approve GitHub Environment gates programmatically.

## Commands to run

Preview first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" hotfix <base-version> <hotfix-ref> \
  --increment <N> \
  --repo <repo-if-needed> \
  --remote <remote> \
  --dry-run
```

Execute after confirming the back-merge plan:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" hotfix <base-version> <hotfix-ref> \
  --increment <N> \
  --repo <repo-if-needed> \
  --remote <remote> \
  --back-merge-plan "<target branch, owner, and timing>"
```

## Output expectations

Report the hotfix tag, source ref, remote, GitHub Actions URL, and the operator's stated back-merge plan.
