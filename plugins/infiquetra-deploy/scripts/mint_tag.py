#!/usr/bin/env python3
"""Mint deployment promotion tags for the infiquetra-deploy plugin."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_OWNER = "infiquetra"
DEFAULT_REMOTE = "origin"
ENVIRONMENTS = ("nonprod", "production")
PRODUCTION_ENVIRONMENT = "production"
PRODUCTION_TAG_PREFIX = "production-v"
ROLLBACK_TAG_PREFIX = "rollback-production-v"
WORKFLOW_NAMES = ("deploy.yml", "deployment.yml", "release.yml")
GITHUB_HOST = "github.com"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
HOTFIX_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
Runner = Callable[[list[str], str | None], str]


@dataclass(frozen=True)
class RepositorySpec:
    """Normalized GitHub repository coordinates."""

    owner: str
    name: str
    host: str | None = None

    @property
    def full_name(self) -> str:
        """Return owner/name."""
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class TagPlan:
    """Details for a tag creation operation."""

    tag: str
    ref: str
    remote: str
    repository: RepositorySpec
    dry_run: bool
    rollback: bool = False


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse an N.N.N version string."""
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise ValueError(f"Version must use N.N.N SemVer format: {version}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def parse_hotfix_version(version: str) -> tuple[int, int, int, int]:
    """Parse an N.N.N.N hotfix version string."""
    match = HOTFIX_RE.fullmatch(version)
    if not match:
        raise ValueError(f"Hotfix version must use explicit N.N.N.N format: {version}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def build_promotion_tag(version: str, *, rollback: bool = False) -> str:
    """Build a production promotion or rollback tag for an N.N.N version."""
    parse_semver(version)
    prefix = ROLLBACK_TAG_PREFIX if rollback else PRODUCTION_TAG_PREFIX
    return f"{prefix}{version}"


def build_hotfix_tag(base_version: str, *, increment: int = 1) -> str:
    """Build a production hotfix tag from an N.N.N base and positive increment."""
    parse_semver(base_version)
    if increment <= 0:
        raise ValueError("Hotfix increment must be positive")
    return f"{PRODUCTION_TAG_PREFIX}{base_version}.{increment}"


def deployment_environments() -> tuple[str, str]:
    """Return default deployment environments in reporting order."""
    return ENVIRONMENTS


def environment_for_tag(tag: str) -> str | None:
    """Return the deployment environment implied by a promotion tag."""
    production_patterns = (
        rf"^{re.escape(PRODUCTION_TAG_PREFIX)}\d+\.\d+\.\d+(?:\.\d+)?$",
        rf"^{re.escape(ROLLBACK_TAG_PREFIX)}\d+\.\d+\.\d+$",
    )
    if any(re.fullmatch(pattern, tag) for pattern in production_patterns):
        return PRODUCTION_ENVIRONMENT
    return None


def _strip_dot_git(value: str) -> str:
    return value[:-4] if value.endswith(".git") else value


def parse_repository(value: str, *, default_owner: str = DEFAULT_OWNER) -> RepositorySpec:
    """Parse repo name, owner/name, or common git remote URL forms."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Repository value cannot be empty")

    if "://" in cleaned:
        parsed = urlparse(cleaned)
        host = parsed.hostname
        parts = [part for part in _strip_dot_git(parsed.path).strip("/").split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Could not parse repository from URL: {value}")
        return RepositorySpec(owner=parts[-2], name=parts[-1], host=host)

    scp_match = re.match(r"^(?:[^@]+@)?([^:]+):(.+)$", cleaned)
    if scp_match:
        host = scp_match.group(1)
        path = _strip_dot_git(scp_match.group(2).strip("/"))
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Could not parse repository from remote: {value}")
        return RepositorySpec(owner=parts[-2], name=parts[-1], host=host)

    path = _strip_dot_git(cleaned.strip("/"))
    parts = [part for part in path.split("/") if part]
    if len(parts) == 1:
        return RepositorySpec(owner=default_owner, name=parts[0])
    if len(parts) == 2:
        return RepositorySpec(owner=parts[0], name=parts[1])
    raise ValueError(f"Could not parse repository: {value}")


def run_command(args: list[str], input_data: str | None = None) -> str:
    """Run a command and return stdout, raising RuntimeError on failure."""
    try:
        result = subprocess.run(  # nosec B603
            args,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"Command not found: {args[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Command timed out: {' '.join(args)}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed ({' '.join(args)}): {detail}")
    return result.stdout.strip()


def resolve_repository(
    *,
    repo: str | None,
    remote: str = DEFAULT_REMOTE,
    runner: Runner = run_command,
) -> RepositorySpec:
    """Resolve repository from an explicit value or local git remote."""
    if repo:
        return parse_repository(repo)
    remote_url = runner(["git", "remote", "get-url", remote], None)
    return parse_repository(remote_url)


def verify_remote_matches_repository(
    repository: RepositorySpec,
    *,
    remote: str,
    runner: Runner = run_command,
) -> None:
    """Raise if the push remote does not match the planned repository."""
    remote_url = runner(["git", "remote", "get-url", remote], None)
    remote_repository = parse_repository(remote_url)
    repository_host = repository.host or GITHUB_HOST
    remote_host = remote_repository.host or GITHUB_HOST
    if remote_repository.full_name != repository.full_name or remote_host != repository_host:
        raise RuntimeError(
            f"Remote {remote} resolves to {remote_repository.full_name}, not {repository.full_name}"
        )


def gh_hostname_args(repository: RepositorySpec) -> list[str]:
    """Return gh hostname flags only for non-default hosts."""
    if repository.host and repository.host != GITHUB_HOST:
        return ["--hostname", repository.host]
    return []


def build_actions_url(repository: RepositorySpec) -> str:
    """Build the GitHub Actions URL to inspect after a promotion tag push."""
    host = repository.host or GITHUB_HOST
    return f"https://{host}/{repository.full_name}/actions"


def ensure_tag_missing(tag: str, *, remote: str, runner: Runner = run_command) -> None:
    """Raise if a tag already exists locally or on the configured remote."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Command not found: git")

    try:
        local_exists = subprocess.run(  # nosec B603
            [git, "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Command timed out: git rev-parse tag check") from error

    if local_exists.returncode == 0:
        raise RuntimeError(f"Local tag already exists: {tag}")
    if local_exists.returncode != 1:
        detail = local_exists.stderr.strip() or local_exists.stdout.strip() or "unknown error"
        raise RuntimeError(f"Local tag check failed for {tag}: {detail}")

    remote_result = runner(["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}"], None)
    if remote_result.strip():
        raise RuntimeError(f"Remote tag already exists on {remote}: {tag}")


def create_and_push_tag(plan: TagPlan, *, runner: Runner = run_command) -> None:
    """Create an annotated tag and push it to the configured remote."""
    message = f"Promote {plan.repository.full_name} to {plan.tag}"
    if plan.rollback:
        message = f"Rollback {plan.repository.full_name} with {plan.tag}"

    verify_remote_matches_repository(plan.repository, remote=plan.remote, runner=runner)
    ensure_tag_missing(plan.tag, remote=plan.remote, runner=runner)

    if plan.dry_run:
        print("DRY RUN: tag absence validated")
        print(f"DRY RUN: git tag -a {plan.tag} {plan.ref} -m {message!r}")
        print(f"DRY RUN: git push {plan.remote} refs/tags/{plan.tag}")
        return
    runner(["git", "tag", "-a", plan.tag, plan.ref, "-m", message], None)
    runner(["git", "push", plan.remote, f"refs/tags/{plan.tag}"], None)


def print_plan(plan: TagPlan) -> None:
    """Print a human-readable tag promotion plan."""
    action = "rollback" if plan.rollback else "production promotion"
    print(f"Repository: {plan.repository.full_name}")
    print(f"Action: {action}")
    print(f"Tag: {plan.tag}")
    print(f"Ref: {plan.ref}")
    print(f"Remote: {plan.remote}")
    print(f"Environment: {environment_for_tag(plan.tag) or 'unknown'}")
    print(f"Actions: {build_actions_url(plan.repository)}")
    print("Note: GitHub Environment approvals are not approved by this helper.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy = subparsers.add_parser("deploy", help="Create a production promotion tag")
    deploy.add_argument("version", help="N.N.N production version")
    deploy.add_argument("--rollback", action="store_true", help="Create a rollback promotion tag")
    deploy.add_argument("--repo", help="Repository name, owner/name, or remote URL")
    deploy.add_argument(
        "--remote", default=DEFAULT_REMOTE, help="Git remote for tag checks and push"
    )
    deploy.add_argument("--ref", default="HEAD", help="Git ref to tag")
    deploy.add_argument(
        "--dry-run", action="store_true", help="Print actions without creating a tag"
    )
    deploy.add_argument(
        "--confirm-rollback",
        action="store_true",
        help="Confirm non-dry-run rollback tag creation",
    )

    hotfix = subparsers.add_parser("hotfix", help="Create a four-part production hotfix tag")
    hotfix.add_argument("base_version", help="N.N.N production base version")
    hotfix.add_argument("hotfix_ref", help="Git ref to tag for the hotfix")
    hotfix.add_argument("--increment", type=int, default=1, help="Fourth version part")
    hotfix.add_argument("--repo", help="Repository name, owner/name, or remote URL")
    hotfix.add_argument(
        "--remote", default=DEFAULT_REMOTE, help="Git remote for tag checks and push"
    )
    hotfix.add_argument(
        "--dry-run", action="store_true", help="Print actions without creating a tag"
    )
    hotfix.add_argument(
        "--back-merge-plan",
        help="Back-merge plan for non-dry-run hotfix tag creation",
    )
    return parser


def _plan_from_args(args: argparse.Namespace) -> TagPlan:
    repository = resolve_repository(repo=args.repo, remote=args.remote)
    if args.command == "deploy":
        if args.rollback and not args.dry_run and not args.confirm_rollback:
            raise ValueError("Non-dry-run rollback requires --confirm-rollback")
        tag = build_promotion_tag(args.version, rollback=args.rollback)
        return TagPlan(
            tag=tag,
            ref=args.ref,
            remote=args.remote,
            repository=repository,
            dry_run=args.dry_run,
            rollback=args.rollback,
        )
    if args.command == "hotfix":
        if not args.dry_run and not (args.back_merge_plan or "").strip():
            raise ValueError("Non-dry-run hotfix requires --back-merge-plan")
        tag = build_hotfix_tag(args.base_version, increment=args.increment)
        parse_hotfix_version(tag.removeprefix(PRODUCTION_TAG_PREFIX))
        return TagPlan(
            tag=tag,
            ref=args.hotfix_ref,
            remote=args.remote,
            repository=repository,
            dry_run=args.dry_run,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        plan = _plan_from_args(args)
        print_plan(plan)
        create_and_push_tag(plan)
        if plan.dry_run:
            print("Dry run complete. No tag was created or pushed.")
        else:
            print(
                f"Pushed tag {plan.tag}. Watch workflow progress at {build_actions_url(plan.repository)}"
            )
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
