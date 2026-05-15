---
name: infiquetra-deploy
description: Create production promotion or rollback tags for Infiquetra deployment workflows
argument-hint: "<version> [--rollback] [--repo <repo>] [--remote <remote>] [--ref <ref>] [--dry-run]"
---

Guide a production deployment promotion using the bundled helper script.

Resolve the helper path as `${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py` when the plugin is installed. In a cloned plugin repository, use `plugins/infiquetra-deploy/scripts/mint_tag.py`.

## Required behavior

1. Parse `$ARGUMENTS` as:
   - `<version>`: required `N.N.N` SemVer production version
   - `--rollback`: optional rollback mode
   - `--repo <repo>`: optional repo in `name`, `owner/name`, or git remote URL form
   - `--remote <remote>`: optional git remote, default `origin`
   - `--ref <ref>`: optional git ref to tag, default `HEAD`
   - `--dry-run`: preview without creating or pushing a tag; still validates the local and remote tag are absent
2. If `--rollback` is present, require explicit human confirmation before executing a non-dry-run rollback.
3. Pass `--confirm-rollback` only after that confirmation; the helper rejects non-dry-run rollback without it.
4. Never approve GitHub Environment gates programmatically. Remind the operator that production environment approval remains a manual GitHub approval step.
5. Use public GitHub CLI defaults unless the local repo remote resolves to a different host.
6. If `--repo` is omitted, resolve it from `git remote get-url <remote>`.
7. Require a local git checkout for creating and pushing tags.
8. Reject tag creation when an explicit `--repo` does not match the configured push remote.

## Commands to run

Preview first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> \
  --repo <repo-if-needed> \
  --remote <remote> \
  --ref <ref> \
  --dry-run
```

Execute forward production promotion after review:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> \
  --repo <repo-if-needed> \
  --remote <remote> \
  --ref <ref>
```

Execute rollback only after human confirmation:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> \
  --rollback \
  --confirm-rollback \
  --repo <repo-if-needed> \
  --remote <remote> \
  --ref <ref>
```

## Tag contract

- Forward production deploys create annotated tags named `production-v{semver}`.
- Rollbacks create annotated tags named `rollback-production-v{semver}`.
- Normal deploy and rollback versions must be `N.N.N` only.
- The helper pushes `refs/tags/<tag>` to the configured remote.

## Output expectations

Report:

- Repository
- Tag to be created
- Source ref
- Remote
- Dry-run or pushed status
- GitHub Actions URL to monitor
- Reminder that GitHub Environment approval is manual
