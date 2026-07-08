---
title: Normalize mission-control repo arguments — issue #505
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/505
---

# Normalize mission-control repo arguments — issue #505

## Summary

`sdlc_manager.py` accepts many `--repo` arguments but most call sites build API paths as
`infiquetra/{repo}`. Passing `infiquetra/<repo>` therefore produces doubled paths such as
`infiquetra/infiquetra/team-freya`. This plan normalizes matching owner-qualified repo inputs at
the CLI boundary and rejects non-Infiquetra owners clearly.

## Requirements

R1. Every `--repo`, `--parent-repo`, and `--child-repo` argument accepted by mission-control must
support either bare repo names or `infiquetra/<repo>`.

R2. A repo qualified with any owner other than `infiquetra` must fail before GitHub mutation or
network calls with a clear unsupported-owner error.

R3. Bare repo inputs must preserve current behavior.

R4. Tests must cover labels, issue, board, and sub-issue helper paths enough to prove consistent
normalization at the shared boundary.

## Key Technical Decisions

**KTD1: Normalize in argparse with a shared helper.** This keeps downstream helpers on their
existing bare-repo contract and avoids touching dozens of `f"{ORG}/{repo}"` call sites.

**KTD2: Reject foreign owners instead of adding multi-org support.** The issue explicitly excludes
repos outside Infiquetra, so accepting another owner would create a hidden policy expansion.

## Implementation Units

### U1. Add shared repo-name normalization

Add `_normalize_repo_arg(value: str) -> str` near the configuration/helpers section. It returns the
repo name unchanged for bare values, strips `infiquetra/` for matching owner-qualified values, and
raises `argparse.ArgumentTypeError` for empty values or foreign owners.

Test scenarios: unit tests for bare, matching owner-qualified, and foreign-owner values.

### U2. Wire normalization into CLI parsers

Apply `type=_normalize_repo_arg` to every parser argument that represents a repository name:
`--repo`, `--parent-repo`, and `--child-repo`. Leave examples and internal helper signatures bare.

Test scenarios: parser-level tests show `labels audit --repo infiquetra/x` reaches `labels_audit`
as `x`, and `flow link-sub-issue` normalizes both parent and child repo arguments.

### U3. Update release surfaces

Because repo argument parsing is mission-control command behavior, bump `plugins/mission-control`
metadata, add a changelog entry, and regenerate the marketplace registry.

Test scenarios: release-surface parity and marketplace generator checks pass.

### U4. Verify the acceptance path

Run the narrow tests for mission-control CLI parsing and label audit, then run the relevant lint
and release-surface checks.

Test expectation: the release-surface bump lands in the same PR as the command behavior change.

## Scope Boundaries

Out of scope: multi-org support, changing the `ORG` constant, or rewriting existing REST/GraphQL
helpers to carry owner/repo pairs.

## Verification

- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py tests/test_mission_control.py -k "repo or flow" -v`
- `python3 plugins/mission-control/scripts/sdlc_manager.py labels audit --repo infiquetra/infiquetra-claude-plugins`
- `python3 plugins/mission-control/scripts/sdlc_manager.py labels audit --repo infiquetra-claude-plugins`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py tests/test_mission_control.py`
