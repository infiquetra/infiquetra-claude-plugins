#!/usr/bin/env python3
"""Detect Infiquetra deployment strategy from workflow filenames."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
import time
from collections.abc import Sequence
from pathlib import Path

ENV_ORDER = ("nonprod", "staging", "production")
CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_DIR = Path(".claude/infiquetra-lifecycle")


def _detect_env(workflow: str) -> str | None:
    lowered = workflow.lower()
    if "deploy" not in lowered and "promotion" not in lowered:
        return None
    for env in ENV_ORDER:
        if env in lowered:
            return env
    return None


def classify(workflows: Sequence[str]) -> dict[str, object]:
    """Classify tag-promotion coverage from workflow filenames."""

    envs = sorted(
        {env for workflow in workflows if (env := _detect_env(workflow))},
        key=ENV_ORDER.index,
    )
    if set(envs) == set(ENV_ORDER):
        strategy = "tag-promotion"
    elif envs:
        strategy = "tag-promotion-partial"
    else:
        strategy = "unknown"

    return {
        "strategy": strategy,
        "envs_available": envs,
        "workflows": list(workflows),
    }


def get_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo if "/" in explicit_repo else f"infiquetra/{explicit_repo}"
    result = subprocess.run(  # nosec B603 B607
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def cache_path(repo_slug: str) -> Path:
    return CACHE_DIR / f"deploy-strategy-{repo_slug.replace('/', '_')}.json"


def read_cache(repo_slug: str) -> dict[str, object] | None:
    path = cache_path(repo_slug)
    if not path.exists() or time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_cache(repo_slug: str, payload: dict[str, object]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(repo_slug).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def list_workflow_files(repo_slug: str) -> list[str]:
    result = subprocess.run(  # nosec B603 B607
        ["gh", "api", f"repos/{repo_slug}/contents/.github/workflows", "--jq", ".[].name"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflows", nargs="*")
    parser.add_argument("--repo", help="Infiquetra repo slug or name")
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workflows:
        print(json.dumps(classify(args.workflows), indent=2, sort_keys=True))
        return 0

    repo_slug = get_repo_slug(args.repo)
    if not args.no_cache:
        cached = read_cache(repo_slug)
        if cached is not None:
            cached["_cache_hit"] = True
            print(json.dumps(cached, indent=2, sort_keys=True))
            return 0

    result = classify(list_workflow_files(repo_slug))
    result["repo"] = repo_slug
    result["_cache_hit"] = False
    write_cache(repo_slug, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
