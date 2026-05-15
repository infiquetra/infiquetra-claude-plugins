---
name: infiquetra-deploy-notes
description: Preview GitHub generated release notes for a production promotion tag
argument-hint: "<version> [--repo <repo>] [--from <previous-version>] [--target-ref <ref>]"
---

Preview release notes using the bundled helper script.

Resolve the helper path as `${CLAUDE_PLUGIN_ROOT}/scripts/preview_release_notes.py` when the plugin is installed. In a cloned plugin repository, use `plugins/infiquetra-deploy/scripts/preview_release_notes.py`.

## Required behavior

1. Parse `$ARGUMENTS` as:
   - `<version>`: required production version, `N.N.N` or explicit hotfix `N.N.N.N`
   - `--repo <repo>`: optional repo in `name`, `owner/name`, or git remote URL form
   - `--from <previous-version>`: optional previous production version or tag
   - `--target-ref <ref>`: optional source ref for GitHub generated notes previews
2. Build the target tag as `production-v{version}`.
3. If `--from` is omitted, select the highest previous `production-v*` tag lower than the target.
4. Pass `--target-ref` when the production tag does not exist yet or the preview source is not the default branch.
5. Use GitHub's generated release notes API through `gh api`.
6. Do not publish a release. This command previews notes only.

## Commands to run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preview_release_notes.py" <version> \
  --repo <repo-if-needed> \
  --target-ref <ref>
```

With an explicit previous production version:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preview_release_notes.py" <version> \
  --repo <repo-if-needed> \
  --from <previous-version>
```

## Side effects

The helper uses the GitHub `releases/generate-notes` endpoint and does not create, view, or delete a draft release. If a future implementation uses a draft release create/view/delete flow, treat it as side-effectful and explain that to the operator before running it.

## Output expectations

Show the generated title, target tag, selected previous production tag, and generated release notes body.
