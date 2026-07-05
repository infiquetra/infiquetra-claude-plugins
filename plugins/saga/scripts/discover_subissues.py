#!/usr/bin/env python3
"""Discover GitHub sub-issues for an Infiquetra issue."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from typing import Any

# ``stateReason`` seeds a closed sub-issue's terminal node state (#375 KTD2); ``trackedIssues`` is the
# stable relationship signal for edge inference (#375 KTD1 — a tracker depends on what it tracks). We
# deliberately avoid a speculative ``blockedBy``/dependency field: an unknown field 400s the whole
# query, which would break ingestion rather than degrade it.
GRAPHQL_QUERY = """
query SubIssues($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      number
      title
      state
      subIssues(first: 50) {
        totalCount
        nodes {
          number
          title
          state
          stateReason
          url
          labels(first: 10) { nodes { name } }
          assignees(first: 5) { nodes { login } }
          trackedIssues(first: 50) { nodes { number } }
        }
      }
    }
  }
}
""".strip()


def parse_repo(value: str) -> tuple[str, str]:
    if "/" in value:
        owner, repo = value.split("/", 1)
        return owner, repo
    return "infiquetra", value


def fetch_subissues(
    owner: str, repo: str, number: int, *, runner: Callable[..., Any] | None = None
) -> dict[str, object]:
    """Fetch the parent issue + its sub-issues via ``gh api graphql``.

    ``runner`` defaults to ``subprocess.run``; tests inject a fake that returns fixture GraphQL JSON so
    the ingestion path (#375) is exercised with no live ``gh`` (the conftest no-live-gh guard blocks,
    it does not return fixtures).
    """
    run = runner if runner is not None else subprocess.run
    cmd = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"owner={owner}",
        "-f",
        f"repo={repo}",
        "-F",
        f"number={number}",
        "-f",
        f"query={GRAPHQL_QUERY}",
    ]
    result = run(cmd, capture_output=True, text=True, check=False)  # nosec B603
    if getattr(result, "returncode", 0) != 0:
        print(f"gh api graphql failed: {getattr(result, 'stderr', '')}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(result.stdout)


def fetch_objective(
    owner: str, repo: str, number: int, *, runner: Callable[..., Any] | None = None
) -> dict[str, object]:
    """Library entry point (#375): fetch + normalize a parent Objective's sub-issues in one call."""
    return normalize(fetch_subissues(owner, repo, number, runner=runner))


def normalize(payload: dict[str, object]) -> dict[str, object]:
    issue = payload.get("data", {}).get("repository", {}).get("issue", {})
    subissues = issue.get("subIssues", {}) if isinstance(issue, dict) else {}
    nodes = subissues.get("nodes", []) if isinstance(subissues, dict) else []
    return {
        "parent": {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
        },
        "totalCount": subissues.get("totalCount", 0),
        "subissues": [
            {
                "number": node.get("number"),
                "title": node.get("title"),
                "state": node.get("state"),
                "state_reason": node.get("stateReason"),
                "url": node.get("url"),
                "labels": [
                    label.get("name") for label in (node.get("labels", {}).get("nodes") or [])
                ],
                "assignees": [
                    assignee.get("login")
                    for assignee in (node.get("assignees", {}).get("nodes") or [])
                ],
                # #375 KTD1: a tracker depends on what it tracks; empty when absent (degrade-to-no-edges).
                "blocked_by": [
                    t.get("number")
                    for t in (node.get("trackedIssues", {}).get("nodes") or [])
                    if t.get("number") is not None
                ],
            }
            for node in nodes
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="<owner>/<repo> or repo name")
    parser.add_argument("--issue", type=int, required=True, help="Parent issue number")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    owner, repo = parse_repo(args.repo)
    print(json.dumps(normalize(fetch_subissues(owner, repo, args.issue)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
