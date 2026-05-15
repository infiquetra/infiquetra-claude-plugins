---
name: deploy-state
description: This skill should be used when the user asks to "promote to production", "deploy to prod", "cut a production tag", "promote version 1.2.3", "check deployment status", "what deployed to production", "check rollout", "preview release notes for version 1.2.3", "rollback production", "create a hotfix deploy", "handle manual GitHub Environment approval gates", or mentions Infiquetra promotion tags like production-v1.2.3, rollback-production-v1.2.3, or production-v1.2.3.1.
version: 0.1.0
---

# Deploy State Skill

Use this skill to guide Infiquetra greenfield deployment promotions safely and consistently.

## Core Contract

Apply these rules before running any helper:

- Default owner: `infiquetra`.
- Default environments: `nonprod` and `production`.
- Forward production promotion tag: `production-v{N.N.N}`.
- Rollback tag: `rollback-production-v{N.N.N}`.
- Hotfix tag: `production-v{N.N.N.N}` only when the user explicitly requests a hotfix.
- Status source of truth: GitHub Deployments API for `nonprod` and `production`.
- Production environment approvals stay manual in GitHub. Do not call approval APIs, bypass protection, or report pending approval as success or failure.
- Use public GitHub CLI defaults unless a local git remote resolves to a different host.
- Never hardcode secrets or credentials.

## Helper Scripts

Use the plugin helper scripts unless the helper is unavailable:

- `${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py` — validate versions, build promotion tags, create annotated tags, push tags, and print the GitHub Actions URL.
- `${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py` — query latest GitHub Deployment state for `nonprod` and `production`.
- `${CLAUDE_PLUGIN_ROOT}/scripts/preview_release_notes.py` — preview GitHub generated release notes for `production-v{version}` without publishing a release.

Prefer dry-run commands before tag creation:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy 1.2.3 --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy 1.2.3 --rollback --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" hotfix 1.2.3 <hotfix-ref> --increment 1 --dry-run
```

## Promotion Workflow

For a forward production promotion:

1. Confirm the target version is exactly `N.N.N`.
2. Resolve the repository from `--repo`, or from `git remote get-url origin` when omitted.
3. Confirm an explicit `--repo` matches the configured push remote before tag creation.
4. Check current `nonprod` deployment status with `query_deployments.py`; compare the requested ref or version against the reported deployment ref or SHA, and stop if it cannot be verified.
5. Run a dry-run and show the planned tag, ref, remote, Actions URL, and tag absence checks.
6. Ask the operator to confirm the promotion.
7. Run the non-dry-run tag push only after confirmation.
8. Remind the operator that GitHub Environment approval must be completed manually.
9. Offer to run deployment status after workflows start.

Command forms:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py" <repo> --format table
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> --repo <repo> --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> --repo <repo>
```

## Rollback Workflow

For rollback:

1. Confirm the rollback target version is exactly `N.N.N`.
2. Explain that the helper creates `rollback-production-v{version}`.
3. Check current production deployment status before tagging.
4. Run a rollback dry-run first.
5. Require explicit human confirmation before any non-dry-run rollback.
6. Create and push the rollback tag only after confirmation, passing `--confirm-rollback`.
7. Query deployment status after the rollback workflow starts; a pushed rollback tag is not a completed rollback.
8. Do not approve any deployment gate.

Command forms:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py" <repo> --format table
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> --rollback --repo <repo> --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" deploy <version> --rollback --repo <repo> --confirm-rollback
```

## Status Workflow

For deployment status:

1. Query both `nonprod` and `production`.
2. Use `query_deployments.py`; it wraps the GitHub Deployments API through `gh api`.
3. Report latest state, ref, short SHA, timestamp, target URL, and pending approval states when available.
4. Use JSON output when the user asks for machine-readable status.

Command form:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/query_deployments.py" <repo> --format table
```

## Release Notes Workflow

For release-note previews:

1. Build target tag `production-v{version}`.
2. If `--from` is absent, select the previous production tag lower than the target.
3. Pass `--target-ref` when previewing notes for a tag that does not exist yet or a non-default source ref.
4. Use GitHub generated release notes API.
5. Do not publish a release.
6. Show the target tag, target ref when supplied, and previous tag used for comparison.

Command form:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preview_release_notes.py" <version> --repo <repo> --target-ref <ref>
```

## Hotfix Workflow

For hotfix promotions:

1. Require explicit hotfix intent from the user.
2. Accept base version `N.N.N` plus positive `--increment N`.
3. Create `production-v{base}.{increment}` from the explicit hotfix ref.
4. Run a dry-run and show the planned tag, source ref, remote, and Actions URL.
5. Require a back-merge plan before non-dry-run execution.
6. Treat an acceptable back-merge plan as the target branch, responsible operator, and timing for merging the hotfix back to the trunk branch.
7. Ask the operator to confirm the hotfix after stating that plan.
8. Pass `--back-merge-plan "<plan>"` only after the operator states that plan.
9. Remind the operator that production approval remains manual.

Command forms:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" hotfix <base-version> <hotfix-ref> --increment <N> --repo <repo> --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mint_tag.py" hotfix <base-version> <hotfix-ref> --increment <N> --repo <repo> --back-merge-plan "<target branch, owner, and timing>"
```

## Safety Checks

Before reporting success:

- Verify the helper surfaced the GitHub Actions URL.
- Confirm the command did not attempt to approve production gates.
- Confirm every tag-creating flow had human confirmation before non-dry-run execution.
- Confirm rollback or hotfix flows had rollback or back-merge context.
- If a helper fails, report the exact error and stop rather than inventing deployment state.
