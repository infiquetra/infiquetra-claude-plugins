#!/usr/bin/env python3
"""Discover GitHub sub-issues for an Infiquetra issue."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys

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
          url
          labels(first: 10) { nodes { name } }
          assignees(first: 5) { nodes { login } }
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


def fetch_subissues(owner: str, repo: str, number: int) -> dict[str, object]:
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
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # nosec B603
    if result.returncode != 0:
        print(f"gh api graphql failed: {result.stderr}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(result.stdout)


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
                "url": node.get("url"),
                "labels": [
                    label.get("name") for label in (node.get("labels", {}).get("nodes") or [])
                ],
                "assignees": [
                    assignee.get("login")
                    for assignee in (node.get("assignees", {}).get("nodes") or [])
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
