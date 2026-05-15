#!/usr/bin/env python3
"""Query GitHub deployment state for Infiquetra promotion environments."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, cast
from urllib.parse import quote

mint_tag: Any = importlib.import_module(f"{__package__}.mint_tag" if __package__ else "mint_tag")
Runner = Callable[[list[str], str | None], str]
RepositorySpec = Any


@dataclass(frozen=True)
class DeploymentStatus:
    """Latest deployment status for one environment."""

    environment: str
    state: str
    deployment_id: int | None
    ref: str | None
    sha: str | None
    created_at: str | None
    description: str | None
    target_url: str | None


def gh_api(args: list[str], input_data: str | None = None) -> str:
    """Run gh api with shared command behavior."""
    return cast(str, mint_tag.run_command(["gh", *args], input_data))


def empty_status(environment: str) -> DeploymentStatus:
    """Return a missing deployment status record for an environment."""
    return DeploymentStatus(
        environment=environment,
        state="none",
        deployment_id=None,
        ref=None,
        sha=None,
        created_at=None,
        description=None,
        target_url=None,
    )


def fetch_environment_status(
    repository: RepositorySpec,
    environment: str,
    *,
    gh_runner: Runner = gh_api,
) -> DeploymentStatus:
    """Fetch the latest GitHub Deployment and status for one environment."""
    encoded_environment = quote(environment, safe="")
    host_args = mint_tag.gh_hostname_args(repository)
    deployments_path = (
        f"repos/{repository.full_name}/deployments?environment={encoded_environment}&per_page=10"
    )
    deployments = json.loads(gh_runner(["api", deployments_path, *host_args], None) or "[]")
    if not deployments:
        return empty_status(environment)

    deployment = deployments[0]
    deployment_id = deployment.get("id")
    statuses_path = f"repos/{repository.full_name}/deployments/{deployment_id}/statuses?per_page=1"
    statuses = json.loads(gh_runner(["api", statuses_path, *host_args], None) or "[]")
    latest_status = statuses[0] if statuses else {}

    return DeploymentStatus(
        environment=environment,
        state=str(latest_status.get("state") or "pending"),
        deployment_id=int(deployment_id) if deployment_id is not None else None,
        ref=deployment.get("ref"),
        sha=deployment.get("sha"),
        created_at=latest_status.get("created_at") or deployment.get("created_at"),
        description=latest_status.get("description") or deployment.get("description"),
        target_url=latest_status.get("target_url"),
    )


def fetch_all_statuses(
    repository: RepositorySpec,
    *,
    gh_runner: Runner = gh_api,
) -> list[DeploymentStatus]:
    """Fetch deployment statuses for default environments."""
    return [
        fetch_environment_status(repository, environment, gh_runner=gh_runner)
        for environment in mint_tag.deployment_environments()
    ]


def render_status_table(statuses: Sequence[DeploymentStatus]) -> str:
    """Render deployment statuses as a simple table."""
    headers = ("Environment", "State", "Deployment", "Ref", "SHA", "Updated", "URL")
    rows = [
        (
            status.environment,
            status.state,
            str(status.deployment_id or "-"),
            status.ref or "-",
            status.sha[:8] if status.sha else "-",
            status.created_at or "-",
            status.target_url or "-",
        )
        for status in statuses
    ]
    widths = [
        max(len(str(cell)) for cell in column) for column in zip(headers, *rows, strict=False)
    ]

    def render_row(row: Sequence[str]) -> str:
        return " | ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=False))

    divider = "-+-".join("-" * width for width in widths)
    return "\n".join([render_row(headers), divider, *(render_row(row) for row in rows)])


def render_status_json(statuses: Sequence[DeploymentStatus]) -> str:
    """Render deployment statuses as JSON."""
    return json.dumps([asdict(status) for status in statuses], indent=2, sort_keys=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", help="Repository name, owner/name, or remote URL")
    parser.add_argument(
        "--remote", default=mint_tag.DEFAULT_REMOTE, help="Git remote if repo is omitted"
    )
    parser.add_argument("--format", choices=("table", "json"), default="table")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        repository = mint_tag.resolve_repository(repo=args.repo, remote=args.remote)
        statuses = fetch_all_statuses(repository)
        if args.format == "json":
            print(render_status_json(statuses))
        else:
            print(f"Repository: {repository.full_name}")
            print(render_status_table(statuses))
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
