"""Unit tests for the infiquetra-deploy plugin helper scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "plugins" / "infiquetra-deploy" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import mint_tag  # noqa: E402
import preview_release_notes  # noqa: E402
import query_deployments  # noqa: E402


class TestTagConstruction:
    """Tag construction follows the deployment promotion contract."""

    def test_builds_forward_production_tag(self) -> None:
        """Forward deploys create production-vN.N.N tags only."""
        assert mint_tag.build_promotion_tag("1.2.3") == "production-v1.2.3"

    def test_builds_rollback_production_tag(self) -> None:
        """Rollbacks create rollback-production-vN.N.N tags."""
        assert mint_tag.build_promotion_tag("1.2.3", rollback=True) == "rollback-production-v1.2.3"

    def test_builds_explicit_hotfix_tag(self) -> None:
        """Hotfixes create production-vN.N.N.N tags when explicitly requested."""
        assert mint_tag.build_hotfix_tag("1.2.3", increment=4) == "production-v1.2.3.4"


class TestVersionValidation:
    """Version validation separates normal deploys from hotfix deploys."""

    def test_parse_semver_accepts_three_part_versions(self) -> None:
        """Normal promotion versions use N.N.N SemVer."""
        assert mint_tag.parse_semver("10.20.30") == (10, 20, 30)

    @pytest.mark.parametrize("version", ["1.2", "1.2.3.4", "v1.2.3", "1.2.x"])
    def test_parse_semver_rejects_non_three_part_versions(self, version: str) -> None:
        """Normal promotion rejects malformed and four-part versions."""
        with pytest.raises(ValueError, match="N.N.N"):
            mint_tag.parse_semver(version)

    def test_parse_hotfix_version_accepts_four_parts(self) -> None:
        """Hotfix validation accepts N.N.N.N versions."""
        assert mint_tag.parse_hotfix_version("1.2.3.4") == (1, 2, 3, 4)

    @pytest.mark.parametrize("version", ["1.2.3", "1.2.3.x", "v1.2.3.4"])
    def test_parse_hotfix_version_rejects_non_four_part_versions(self, version: str) -> None:
        """Hotfix validation rejects values that are not explicit four-part versions."""
        with pytest.raises(ValueError, match="N.N.N.N"):
            mint_tag.parse_hotfix_version(version)

    def test_hotfix_increment_must_be_positive(self) -> None:
        """Hotfix increments start at 1."""
        with pytest.raises(ValueError, match="positive"):
            mint_tag.build_hotfix_tag("1.2.3", increment=0)


class TestRepositoryResolution:
    """Repository parsing supports names, owner/name, and git remotes."""

    def test_parse_bare_name_uses_default_owner(self) -> None:
        """Bare repo names resolve to the default owner."""
        spec = mint_tag.parse_repository("service-api")
        assert spec.owner == "infiquetra"
        assert spec.name == "service-api"
        assert spec.full_name == "infiquetra/service-api"
        assert spec.host is None

    def test_parse_owner_name(self) -> None:
        """Explicit owner/name values preserve the owner."""
        spec = mint_tag.parse_repository("team/service-api")
        assert spec.owner == "team"
        assert spec.name == "service-api"
        assert spec.full_name == "team/service-api"

    @pytest.mark.parametrize(
        ("url", "owner", "name"),
        [
            ("git@github.com:team/service-api.git", "team", "service-api"),
            ("https://github.com/team/service-api.git", "team", "service-api"),
            ("ssh://git@github.com/team/service-api.git", "team", "service-api"),
        ],
    )
    def test_parse_github_remote_urls(self, url: str, owner: str, name: str) -> None:
        """Common public GitHub remote URL forms parse correctly."""
        spec = mint_tag.parse_repository(url)
        assert spec.owner == owner
        assert spec.name == name
        assert spec.full_name == f"{owner}/{name}"
        assert mint_tag.gh_hostname_args(spec) == []

    def test_parse_non_default_remote_host(self) -> None:
        """Non-default remote hosts are retained for gh hostname arguments."""
        spec = mint_tag.parse_repository("git@github.example.test:team/service-api.git")
        assert spec.host == "github.example.test"
        assert mint_tag.gh_hostname_args(spec) == ["--hostname", "github.example.test"]

    def test_resolve_repository_reads_configured_remote_when_repo_omitted(
        self, monkeypatch
    ) -> None:
        """Omitted --repo resolves from git remote get-url <remote>."""
        completed = subprocess.CompletedProcess(
            args=["git"],
            returncode=0,
            stdout="git@github.com:team/service-api.git\n",
            stderr="",
        )
        mock_run = MagicMock(return_value=completed)
        monkeypatch.setattr(mint_tag.subprocess, "run", mock_run)

        spec = mint_tag.resolve_repository(repo=None, remote="upstream")

        assert spec.full_name == "team/service-api"
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["git", "remote", "get-url", "upstream"]

    def test_verify_remote_matches_repository_rejects_mismatched_remote(self) -> None:
        """Explicit repo values must match the actual push remote."""

        def fake_runner(args: list[str], input_data: str | None = None) -> str:
            del input_data
            assert args == ["git", "remote", "get-url", "origin"]
            return "git@github.com:other/current-repo.git"

        spec = mint_tag.parse_repository("team/service-api")

        with pytest.raises(RuntimeError, match="current-repo"):
            mint_tag.verify_remote_matches_repository(spec, remote="origin", runner=fake_runner)

    def test_verify_remote_matches_repository_accepts_matching_remote(self) -> None:
        """Matching push remotes are accepted for tag creation."""

        def fake_runner(args: list[str], input_data: str | None = None) -> str:
            del input_data
            assert args == ["git", "remote", "get-url", "origin"]
            return "git@github.com:team/service-api.git"

        spec = mint_tag.parse_repository("team/service-api")

        mint_tag.verify_remote_matches_repository(spec, remote="origin", runner=fake_runner)


class TestEnvironmentMapping:
    """Deployment environments and tag prefixes stay centrally mapped."""

    def test_default_environments_are_nonprod_and_production(self) -> None:
        """Status checks target the two default deployment environments."""
        assert mint_tag.deployment_environments() == ("nonprod", "production")

    @pytest.mark.parametrize(
        ("tag", "environment"),
        [
            ("production-v1.2.3", "production"),
            ("rollback-production-v1.2.3", "production"),
            ("production-v1.2.3.4", "production"),
        ],
    )
    def test_tag_environment_mapping(self, tag: str, environment: str) -> None:
        """Production and rollback production tags map to the production environment."""
        assert mint_tag.environment_for_tag(tag) == environment

    def test_non_matching_tag_has_no_environment(self) -> None:
        """Non-promotion tags are not assigned a deployment environment."""
        assert mint_tag.environment_for_tag("v1.2.3") is None


class TestTagPlanSafety:
    """Non-dry-run safety-sensitive tags require explicit CLI confirmation."""

    def test_non_dry_run_rollback_requires_confirmation(self) -> None:
        """Rollback pushes fail closed without an explicit confirmation flag."""
        args = mint_tag._build_parser().parse_args(["deploy", "1.2.3", "--rollback"])

        with pytest.raises(ValueError, match="--confirm-rollback"):
            mint_tag._plan_from_args(args)

    def test_dry_run_rollback_does_not_require_confirmation(self) -> None:
        """Rollback dry runs can preview without confirmation."""
        args = mint_tag._build_parser().parse_args(["deploy", "1.2.3", "--rollback", "--dry-run"])

        plan = mint_tag._plan_from_args(args)

        assert plan.tag == "rollback-production-v1.2.3"
        assert plan.rollback is True

    def test_non_dry_run_hotfix_requires_back_merge_plan(self) -> None:
        """Hotfix pushes fail closed without an explicit back-merge plan."""
        args = mint_tag._build_parser().parse_args(["hotfix", "1.2.3", "hotfix/ref"])

        with pytest.raises(ValueError, match="--back-merge-plan"):
            mint_tag._plan_from_args(args)

    def test_dry_run_hotfix_does_not_require_back_merge_plan(self) -> None:
        """Hotfix dry runs can preview without back-merge plans."""
        args = mint_tag._build_parser().parse_args(["hotfix", "1.2.3", "hotfix/ref", "--dry-run"])

        plan = mint_tag._plan_from_args(args)

        assert plan.tag == "production-v1.2.3.1"
        assert plan.ref == "hotfix/ref"

    def test_non_dry_run_hotfix_accepts_back_merge_plan(self) -> None:
        """Hotfix pushes require concrete back-merge plan text."""
        args = mint_tag._build_parser().parse_args(
            ["hotfix", "1.2.3", "hotfix/ref", "--back-merge-plan", "main by operator today"]
        )

        plan = mint_tag._plan_from_args(args)

        assert plan.tag == "production-v1.2.3.1"
        assert plan.ref == "hotfix/ref"


class TestDeploymentStatusRendering:
    """Deployment status output covers nonprod and production."""

    def test_render_status_table(self) -> None:
        """Table output includes both environments and their latest states."""
        statuses = [
            query_deployments.DeploymentStatus(
                environment="nonprod",
                state="success",
                deployment_id=101,
                ref="main",
                sha="abcdef1234567890",
                created_at="2026-05-14T10:00:00Z",
                description="nonprod deploy",
                target_url=None,
            ),
            query_deployments.DeploymentStatus(
                environment="production",
                state="failure",
                deployment_id=202,
                ref="production-v1.2.3",
                sha="123456abcdef7890",
                created_at="2026-05-14T11:00:00Z",
                description="production deploy",
                target_url="https://example.invalid/run/202",
            ),
        ]

        output = query_deployments.render_status_table(statuses)

        assert "nonprod" in output
        assert "production" in output
        assert "success" in output
        assert "failure" in output
        assert "production-v1.2.3" in output

    def test_render_status_json(self) -> None:
        """JSON output is machine-readable and environment keyed by records."""
        statuses = [query_deployments.empty_status("nonprod")]

        output = query_deployments.render_status_json(statuses)
        data = json.loads(output)

        assert data == [
            {
                "environment": "nonprod",
                "state": "none",
                "deployment_id": None,
                "ref": None,
                "sha": None,
                "created_at": None,
                "description": None,
                "target_url": None,
            }
        ]

    def test_fetch_environment_status_uses_gh_api(self) -> None:
        """Deployment status lookup uses gh api for deployments and statuses."""
        calls: list[list[str]] = []

        def fake_runner(args: list[str], input_data: str | None = None) -> str:
            del input_data
            calls.append(args)
            if "deployments?environment=production" in args[-1]:
                return json.dumps(
                    [
                        {
                            "id": 42,
                            "ref": "production-v1.2.3",
                            "sha": "abcdef1234567890",
                            "created_at": "2026-05-14T11:00:00Z",
                            "description": "deploy",
                        }
                    ]
                )
            if "deployments/42/statuses" in args[-1]:
                return json.dumps(
                    [
                        {
                            "state": "success",
                            "target_url": "https://example.invalid/run/42",
                            "description": "ok",
                        }
                    ]
                )
            raise AssertionError(f"unexpected gh call: {args}")

        spec = mint_tag.parse_repository("team/service-api")
        status = query_deployments.fetch_environment_status(
            spec, "production", gh_runner=fake_runner
        )

        assert status.environment == "production"
        assert status.state == "success"
        assert status.ref == "production-v1.2.3"
        assert calls[0][:2] == [
            "api",
            "repos/team/service-api/deployments?environment=production&per_page=10",
        ]
        assert calls[1][:2] == ["api", "repos/team/service-api/deployments/42/statuses?per_page=1"]


class TestReleaseNotePreview:
    """Release note previews select the previous production promotion tag."""

    def test_select_previous_production_tag(self) -> None:
        """The previous tag is the highest production promotion below the target."""
        tags = [
            "production-v1.2.0",
            "rollback-production-v1.2.1",
            "production-v1.2.1",
            "production-v1.2.2",
            "production-v1.2.3",
            "production-v1.2.3.1",
            "v1.2.4",
        ]

        previous = preview_release_notes.select_previous_production_tag(
            tags,
            target_tag="production-v1.2.3",
        )

        assert previous == "production-v1.2.2"

    def test_select_previous_production_tag_for_hotfix(self) -> None:
        """Hotfix previews can select an earlier four-part production tag."""
        tags = ["production-v1.2.3", "production-v1.2.3.1", "production-v1.2.3.2"]

        previous = preview_release_notes.select_previous_production_tag(
            tags,
            target_tag="production-v1.2.3.2",
        )

        assert previous == "production-v1.2.3.1"

    def test_list_tags_uses_paginated_api(self) -> None:
        """Tag discovery asks gh to paginate through all repository tags."""
        captured: dict[str, Any] = {}

        def fake_runner(args: list[str], input_data: str | None = None) -> str:
            captured["args"] = args
            captured["input"] = input_data
            return json.dumps(
                [
                    [{"name": "production-v1.2.2"}],
                    [{"name": "production-v1.2.3"}],
                ]
            )

        spec = mint_tag.parse_repository("team/service-api")
        tags = preview_release_notes.list_tags(spec, gh_runner=fake_runner)

        assert tags == ["production-v1.2.2", "production-v1.2.3"]
        assert captured["args"] == [
            "api",
            "repos/team/service-api/tags?per_page=100",
            "--paginate",
            "--slurp",
        ]
        assert captured["input"] is None

    def test_generate_release_notes_payload_uses_previous_tag(self) -> None:
        """Generated release-note requests include the target and previous tag."""
        captured: dict[str, Any] = {}

        def fake_runner(args: list[str], input_data: str | None = None) -> str:
            captured["args"] = args
            captured["input"] = input_data
            return json.dumps({"name": "Release 1.2.3", "body": "Changes"})

        spec = mint_tag.parse_repository("team/service-api")
        notes = preview_release_notes.generate_release_notes(
            spec,
            target_tag="production-v1.2.3",
            previous_tag="production-v1.2.2",
            target_ref="release/ref",
            gh_runner=fake_runner,
        )

        assert notes.title == "Release 1.2.3"
        assert notes.body == "Changes"
        assert notes.target_ref == "release/ref"
        assert captured["args"] == [
            "api",
            "repos/team/service-api/releases/generate-notes",
            "-X",
            "POST",
            "--input",
            "-",
        ]
        assert json.loads(captured["input"]) == {
            "tag_name": "production-v1.2.3",
            "previous_tag_name": "production-v1.2.2",
            "target_commitish": "release/ref",
        }
