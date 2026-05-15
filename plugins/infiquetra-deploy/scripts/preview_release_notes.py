#!/usr/bin/env python3
"""Preview GitHub generated release notes for production promotion tags."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

mint_tag: Any = importlib.import_module(f"{__package__}.mint_tag" if __package__ else "mint_tag")
Runner = Callable[[list[str], str | None], str]
RepositorySpec = Any


@dataclass(frozen=True)
class ReleaseNotesPreview:
    """Generated release notes title and body."""

    title: str
    body: str
    target_tag: str
    previous_tag: str | None
    target_ref: str | None = None


def gh_api(args: list[str], input_data: str | None = None) -> str:
    """Run gh api with shared command behavior."""
    return cast(str, mint_tag.run_command(["gh", *args], input_data))


def parse_production_tag_version(tag: str) -> tuple[int, ...] | None:
    """Return comparable version parts for production promotion tags only."""
    if not tag.startswith(mint_tag.PRODUCTION_TAG_PREFIX):
        return None
    version = tag.removeprefix(mint_tag.PRODUCTION_TAG_PREFIX)
    try:
        if mint_tag.HOTFIX_RE.fullmatch(version):
            return cast(tuple[int, ...], mint_tag.parse_hotfix_version(version))
        return cast(tuple[int, ...], mint_tag.parse_semver(version))
    except ValueError:
        return None


def build_target_tag(version: str) -> str:
    """Build a production target tag from an N.N.N or N.N.N.N version."""
    if mint_tag.HOTFIX_RE.fullmatch(version):
        mint_tag.parse_hotfix_version(version)
        return f"{mint_tag.PRODUCTION_TAG_PREFIX}{version}"
    return cast(str, mint_tag.build_promotion_tag(version))


def select_previous_production_tag(tags: Sequence[str], *, target_tag: str) -> str | None:
    """Select the highest production tag lower than the target tag."""
    target_version = parse_production_tag_version(target_tag)
    if target_version is None:
        raise ValueError(f"Target tag is not a production promotion tag: {target_tag}")

    candidates: list[tuple[tuple[int, ...], str]] = []
    for tag in tags:
        version = parse_production_tag_version(tag)
        if version is not None and version < target_version:
            candidates.append((version, tag))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def list_tags(
    repository: RepositorySpec,
    *,
    gh_runner: Runner = gh_api,
) -> list[str]:
    """List repository tags through the GitHub API."""
    host_args = mint_tag.gh_hostname_args(repository)
    payload = gh_runner(
        [
            "api",
            f"repos/{repository.full_name}/tags?per_page=100",
            "--paginate",
            "--slurp",
            *host_args,
        ],
        None,
    )
    pages = json.loads(payload or "[]")
    if all(isinstance(page, list) for page in pages):
        data = [item for page in pages for item in page]
    else:
        data = pages
    return [str(item["name"]) for item in data if isinstance(item, dict) and "name" in item]


def generate_release_notes(
    repository: RepositorySpec,
    *,
    target_tag: str,
    previous_tag: str | None,
    target_ref: str | None = None,
    gh_runner: Runner = gh_api,
) -> ReleaseNotesPreview:
    """Ask GitHub to generate release notes without creating a release."""
    host_args = mint_tag.gh_hostname_args(repository)
    body = {"tag_name": target_tag}
    if previous_tag:
        body["previous_tag_name"] = previous_tag
    if target_ref:
        body["target_commitish"] = target_ref
    payload = gh_runner(
        [
            "api",
            f"repos/{repository.full_name}/releases/generate-notes",
            "-X",
            "POST",
            "--input",
            "-",
            *host_args,
        ],
        json.dumps(body),
    )
    data = json.loads(payload or "{}")
    return ReleaseNotesPreview(
        title=str(data.get("name") or target_tag),
        body=str(data.get("body") or ""),
        target_tag=target_tag,
        previous_tag=previous_tag,
        target_ref=target_ref,
    )


def render_release_notes(preview: ReleaseNotesPreview) -> str:
    """Render release notes preview as Markdown."""
    previous = preview.previous_tag or "(none found)"
    target_ref = preview.target_ref or "(GitHub default)"
    return "\n".join(
        [
            f"# {preview.title}",
            "",
            f"Target tag: `{preview.target_tag}`",
            f"Target ref: `{target_ref}`",
            f"Previous production tag: `{previous}`",
            "",
            preview.body,
        ]
    ).rstrip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="N.N.N or explicit N.N.N.N production version")
    parser.add_argument("--repo", help="Repository name, owner/name, or remote URL")
    parser.add_argument(
        "--remote", default=mint_tag.DEFAULT_REMOTE, help="Git remote if repo is omitted"
    )
    parser.add_argument("--from", dest="from_version", help="Previous production version or tag")
    parser.add_argument("--target-ref", help="Git ref used as target_commitish for note preview")
    return parser


def _normalize_previous(value: str | None) -> str | None:
    if value is None:
        return None
    if value.startswith(mint_tag.PRODUCTION_TAG_PREFIX):
        return value
    return build_target_tag(value)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        repository = mint_tag.resolve_repository(repo=args.repo, remote=args.remote)
        target_tag = build_target_tag(args.version)
        previous_tag = _normalize_previous(args.from_version)
        if previous_tag is None:
            previous_tag = select_previous_production_tag(
                list_tags(repository), target_tag=target_tag
            )
        preview = generate_release_notes(
            repository,
            target_tag=target_tag,
            previous_tag=previous_tag,
            target_ref=args.target_ref,
        )
        print(render_release_notes(preview))
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
