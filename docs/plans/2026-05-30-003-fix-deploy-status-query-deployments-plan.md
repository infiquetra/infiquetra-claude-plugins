---
title: "fix(infiquetra-deploy): query_deployments.py GET + tag-ref selection"
type: "fix"
status: "ready"
date: "2026-05-30"
issue: 161
handoff_maturity: "requirements-ready"
source: "https://github.com/infiquetra/infiquetra-claude-plugins/issues/161"
target: "PR -> merge to main"
---

# fix(infiquetra-deploy): query_deployments.py GET + tag-ref selection

## Summary

`/deploy-status` is non-functional. `latest_deployment()` in
`plugins/infiquetra-deploy/scripts/query_deployments.py` has two defects:

1. **POST-instead-of-GET.** It calls `gh api repos/{repo}/deployments -f environment={env}
   -f per_page=1`. The `-f` flags make `gh` default to **POST** (create a deployment), so the
   API returns `HTTP 422 "ref wasn't supplied"`. Must be a GET.
2. **Newest-record, not newest-tag.** Even as a GET, taking the single newest deployment per
   environment is wrong. GitHub Actions `environment:` job keys auto-create Deployment objects
   whose `ref` is a branch/SHA (`main`, PR branch names). These interleave with the real
   tag-ref records the deploy workflows write (`v0.1.0`, `staging-v*`, `production-v*`). When a
   branch-ref record is newest, the reported version is wrong.

Fix: GET a small page (`per_page=20`) and select the newest record whose `ref` matches a known
tag pattern, reusing the existing `TAG_PREFIXES` / `strip_prefix`.

## Source context

- Issue: [#161](https://github.com/infiquetra/infiquetra-claude-plugins/issues/161) (defect, requirements-ready)
- Original source file: `/Users/jefcox/.claude/jobs/33b54d6c/tmp/deploy-status-defect.md`
- Found while verifying ADR-0005 tag-promotion on `campps-identity-access` (PR #4).
- Issue-review feedback (advisory) sharpened ACs: drift scenarios, fixture-backed branch-ref
  selection, and a multi-record (`per_page=20`) GET check. Folded into ACs below.

## Root cause detail

```python
# current (broken) — defaults to POST because of -f
payload = run(["gh", "api", f"repos/{repo}/deployments",
               "-f", f"environment={env}", "-f", "per_page=1"])
data = json.loads(payload or "[]")
return data[0] if data else None
```

`gh api` issues POST whenever `-f`/`-F` params are present and no `--method` is given. With
`--method GET`, gh moves `-f` params into the query string. The deployments list endpoint
returns records newest-first, so after the GET we still must skip non-tag refs and pick the
first tag-ref record.

## Acceptance criteria

- [ ] AC1 — `latest_deployment()` issues a GET (`gh api --method GET ...`); no HTTP 422.
- [ ] AC2 — `/deploy-status` prints per-env versions for a repo with real deployments.
      Authoritative pass/fail is the unit fixture (AC4); the live command against
      `infiquetra/campps-identity-access` (`nonprod` at `ref=v0.1.0`) is smoke verification only,
      since live deployment state is mutable.
- [ ] AC3 — Records whose `ref` does not match a known tag pattern
      (`v` / `nonprod-v` / `staging-v` / `production-v` / `rollback-*` followed by a version
      digit) are ignored; the newest **tag-ref** record is selected per environment.
- [ ] AC4 — Regression test: fixture where the newest record has `ref=main` (or a SHA/branch)
      and an older record has `ref=v0.1.0`; assert `latest_deployment()` selects `v0.1.0`.
- [ ] AC5 — Drift detection still works. Test: mocked `nonprod=v0.1.1`, `staging=v0.1.0`,
      `production=v0.1.0` → `render_status` emits a drift block; all three `v0.1.0` →
      `drift: none detected`.
- [ ] AC6 — A test asserts the `gh` invocation is a GET (`--method GET` present, no POST body),
      i.e. the 422 cannot regress.

## Scope

In scope:

- `latest_deployment()` GET conversion + tag-ref selection.
- A small `is_tag_ref()` helper (or inline predicate) that reuses `TAG_PREFIXES`, requiring the
  post-prefix remainder to start with a digit so loose `v`-prefix matches (e.g. a `version-bump`
  branch) are rejected.
- Regression tests/fixtures in `tests/test_infiquetra_deploy_plugin.py`.

Out of scope (per issue non-goals):

- Changing how deploy **workflows** write Deployment records.
- Suppressing auto-created `environment:`-key deployments at the workflow level.
- Any change to `mint_tag.py` or `preview_release_notes.py`.

## Files likely to change

- `plugins/infiquetra-deploy/scripts/query_deployments.py` — `latest_deployment()` + helper.
- `tests/test_infiquetra_deploy_plugin.py` — regression tests (monkeypatch `run` to return
  fixture JSON; assert GET, tag-ref selection, drift).

## Implementation notes

1. Add a tag-ref predicate:

   ```python
   def is_tag_ref(ref: str | None) -> bool:
       if not ref:
           return False
       for prefix in TAG_PREFIXES:
           if ref.startswith(prefix):
               remainder = ref[len(prefix):]
               return bool(remainder) and remainder[0].isdigit()
       return False
   ```

   Note `TAG_PREFIXES` is ordered longest-first, so `nonprod-v0.1.0` matches `nonprod-v`
   before the bare `v`. Keep that ordering.

2. Rewrite `latest_deployment()`:

   ```python
   def latest_deployment(repo: str, env: str) -> dict[str, Any] | None:
       payload = run([
           "gh", "api", "--method", "GET",
           f"repos/{repo}/deployments",
           "-f", f"environment={env}",
           "-f", "per_page=20",
       ])
       data = json.loads(payload or "[]")
       for record in data:  # API returns newest-first
           if is_tag_ref(str(record.get("ref") or "")):
               return record
       return None
   ```

   Keep returning the full record dict so `render_status` still reads `ref`/`sha`.

3. Leave `render_status`, `detect_drift`, `strip_prefix`, `resolve_repo` unchanged.

## Checks

```bash
cd /Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins
uv run ruff check plugins/infiquetra-deploy/scripts/query_deployments.py tests/test_infiquetra_deploy_plugin.py
uv run mypy plugins/infiquetra-deploy/scripts/query_deployments.py
uv run bandit plugins/infiquetra-deploy/scripts/query_deployments.py
uv run pytest tests/test_infiquetra_deploy_plugin.py -v
# Live smoke (AC2, requires gh read access; non-blocking):
python3 plugins/infiquetra-deploy/scripts/query_deployments.py --repo campps-identity-access
gh api --method GET repos/infiquetra/campps-identity-access/deployments \
  -f environment=nonprod -f per_page=1 --jq '.[0].ref'   # -> v0.1.0
```

## Review gates

- Self pre-PR review: confirm GET path, tag-ref filtering, no behavior change to drift/render.
- `/code-review` on the diff before opening the PR.

## Issue updates

- Comment plan path + handoff maturity (requirements-ready) + source link on #161 after writing.
- On merge: comment the merged PR/commit and close #161 via PR `Closes #161`.

## Deploy gates

None. `infiquetra-deploy` is a plugin in this marketplace repo, not a deployed service. No
version bump needed (test asserts `0.1.0`; this is a bugfix to script internals, not a packaged
API change — leave `plugin.json`/`marketplace.json` at `0.1.0`).

## Resume notes

- Branch from `main`: `fix/deploy-status-query-deployments`.
- Authoritative validation is `pytest tests/test_infiquetra_deploy_plugin.py`; the live `gh`
  smoke is best-effort and may be skipped if gh lacks read access to campps-identity-access.
- Auto-merge applies (just-Jeff-and-Claude repo): squash-merge once CI is green.
