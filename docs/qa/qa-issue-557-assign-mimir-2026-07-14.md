# QA: Mission Control assign-to-Mimir

Date: 2026-07-14

Issue: `infiquetra/infiquetra-claude-plugins#557`

Implementation PR: `infiquetra/infiquetra-claude-plugins#600`

Merged commit: `9adb971020df9eb5928595760b5e9c75e498ef2c`

Installed plugin: `mission-control@infiquetra-plugins` 2.10.0, user scope, enabled

## Verdict

PASS. The installed command fails closed for an unsupported repository, applies the existing pilot trigger exactly once for a live-covered repository, reports stable idempotent state on repeat, and reaches the deployed Team Mimir pilot gateway. The canary was restored to closed with no intake label.

## Evidence

| Check | Receipt |
|---|---|
| Focused command contract | `18 passed` after the code-review fix |
| Full repository suite | `3,988 passed, 1 skipped` |
| Static gates | Ruff check and format, mypy, strict plugin and marketplace validation, release-surface parity, marketplace generation check, `git diff --check`, and high-severity Bandit gate passed |
| Code review | `docs/code-reviews/2026-07-14-issue-557-assign-mimir-code-review.md`, PASS; effective-permission handling for custom GitHub roles was fixed before PR |
| Required CI | PR #600 completed all eight checks successfully: tests, lint, type check, security, release parity, plugin validation, delegation proof, and fleet delegation integrity |
| Merge truth | PR #600 squash-merged as `9adb971020df9eb5928595760b5e9c75e498ef2c`; issue #557 closed automatically |
| Release parity | Mission Control plugin manifest, marketplace entry, and top dated changelog heading all read `2.10.0` |
| Installation readback | Marketplace refresh succeeded; installed plugin updated `2.9.0 -> 2.10.0`, scope `user`, `enabled=true`, cache path version `2.10.0` |
| Installed negative proof | Installed cache command against closed `infiquetra/infiquetra-claude-plugins#557` exited 1 with `Repository ... is not uniquely covered by Team Mimir; no mutation performed`; issue remained closed without `intake:mimir` |
| Installed covered proof | Installed cache command against reopened pilot canary #9 returned `trigger.state=applied`, `policy_version=repository-coverage/v1`, `route=pilot`, actor `namredips`, authority `admin`, and issue URL |
| Installed idempotency proof | Immediate repeat returned `trigger.state=already-triggered`; GitHub still showed one `intake:mimir` label and no command-authored comment |
| Provider delivery | Pilot hook `650388056` delivery `3831214935371784000`, GUID `a13b8580-7fa5-11f1-889b-be828756d8a3`, completed `OK` with HTTP `202` |
| Deployed runtime receipt | Mimir generated profile log recorded `POST event=issues route=pilot ... delivery=a13b8580-7fa5-11f1-889b-be828756d8a3` and created the corresponding webhook session |
| Runtime health | Local Mimir webhook health on `127.0.0.1:8654` and public `https://webhooks.infiquetra.com/mimir/health` both returned HTTP 200 with `status=ok` |
| Canary cleanup | `infiquetra/mimir-pilot-claude-plugins#9` is closed and has no labels |

Claude reports that a running session must restart before newly installed skill metadata is loaded. That does not weaken the CLI proof: the command was executed directly from the installed 2.10.0 cache path, and installation registry readback confirms the enabled version. A fresh Claude session will load the same cache entry.

## Rollback

Revert merge commit `9adb971020df9eb5928595760b5e9c75e498ef2c`, refresh the Infiquetra marketplace, update Mission Control back to the resulting prior version, and rerun the unsupported-repository and pilot-canary checks. No Team Mimir coverage or repository label policy was changed by this release.
