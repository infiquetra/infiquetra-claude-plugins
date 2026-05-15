# Infiquetra Deploy Plugin

Claude Code helpers for Infiquetra greenfield deployment promotion workflows.

## Features

- Create forward production promotion tags: `production-v{N.N.N}`.
- Create rollback tags: `rollback-production-v{N.N.N}`.
- Create explicit hotfix tags: `production-v{N.N.N.N}`.
- Query GitHub Deployment state for `nonprod` and `production`.
- Preview GitHub generated release notes for production promotion tags.
- Provide a release orchestration agent for multi-step release planning.

## Commands

### `/infiquetra-deploy <version> [--rollback] [--repo <repo>] [--remote <remote>] [--ref <ref>] [--dry-run]`

Creates an annotated production promotion tag and pushes it to the configured remote. Rollbacks require human confirmation before non-dry-run execution; the helper requires `--confirm-rollback` for rollback pushes.

```bash
/infiquetra-deploy 1.2.3 --repo service-api --ref main --dry-run
/infiquetra-deploy 1.2.3 --repo infiquetra/service-api --ref main
/infiquetra-deploy 1.2.3 --rollback --repo service-api --dry-run
```

### `/infiquetra-deploy-status [repo] [--format table|json]`

Reports the latest GitHub Deployment states for `nonprod` and `production`.

```bash
/infiquetra-deploy-status service-api
/infiquetra-deploy-status infiquetra/service-api --format json
```

### `/infiquetra-deploy-notes <version> [--repo <repo>] [--from <previous-version>] [--target-ref <ref>]`

Previews generated release notes for `production-v{version}` without publishing a release.

```bash
/infiquetra-deploy-notes 1.2.3 --repo service-api --target-ref main
/infiquetra-deploy-notes 1.2.3 --repo service-api --from 1.2.2 --target-ref main
```

### `/infiquetra-deploy-hotfix <base-version> <hotfix-ref> [--increment N] [--repo <repo>] [--remote <remote>] [--back-merge-plan <plan>] [--dry-run]`

Creates `production-v<base-version>.<increment>` from an explicit ref. Hotfixes require a back-merge plan before execution; the helper requires `--back-merge-plan "<plan>"` for hotfix pushes.

```bash
/infiquetra-deploy-hotfix 1.2.3 hotfix/urgent-fix --increment 1 --repo service-api --dry-run
```

## Helper Scripts

Use `${CLAUDE_PLUGIN_ROOT}` when the plugin is installed. From this repository clone, replace it with `plugins/infiquetra-deploy`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy 1.2.3 --repo service-api --ref main --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py" service-api --format table
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preview_release_notes.py" 1.2.3 --repo service-api --target-ref main
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" hotfix 1.2.3 hotfix/urgent-fix --increment 1 --repo service-api --dry-run
```

## Repository Resolution

`--repo` accepts:

- `name` → defaults to `infiquetra/name`
- `owner/name`
- common git remote URLs

When `--repo` is omitted, helpers resolve the repository from `git remote get-url <remote>`. Tag creation rejects an explicit `--repo` that does not match the configured push remote.

## Safety Notes

- GitHub Environment approval is never approved programmatically.
- Forward and rollback deploy versions must be `N.N.N`.
- Hotfix versions are four-part production tags only when explicitly requested.
- Tag creation requires a local git checkout and uses annotated tags.
- Use `--dry-run` before pushing promotion tags; dry runs do not create tags but still check local and remote tag absence.

## Components

- Skill: `deploy-state`
- Agent: `release-orchestrator`
- Scripts: `mint_tag.py`, `query_deployments.py`, `preview_release_notes.py`
