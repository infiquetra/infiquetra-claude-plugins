"""Contract tests for the infiquetra-loop plugin package."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "infiquetra-loop"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_module(script_name: str):
    path = PLUGIN_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter_name(path: Path) -> str:
    lines = _read(path).splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line.startswith("name: "):
            return line.removeprefix("name: ").strip()
    raise AssertionError(f"{path} has no frontmatter name")


def test_infiquetra_loop_metadata_and_marketplace_entry_match() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "infiquetra-loop")

    assert plugin_json["name"] == "infiquetra-loop"
    assert plugin_json["version"] == "0.1.0"
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/infiquetra-loop"
    assert "lifecycle" in plugin_json["description"]
    assert {"loop", "lifecycle", "strategy", "doc-review", "code-review", "optimize"} <= set(
        plugin_json["keywords"]
    )


def test_infiquetra_loop_commands_are_packaged() -> None:
    for command in (
        "loop",
        "office-hours",
        "strategy",
        "ideate",
        "brainstorm",
        "plan",
        "work",
        "qa",
        "retro",
        "resume",
        "founder-review",
        "ceo-review",
        "doc-review",
        "code-review",
        "optimize",
    ):
        assert (PLUGIN_ROOT / "commands" / f"{command}.md").exists()


def test_infiquetra_loop_skills_document_required_lifecycle_behavior() -> None:
    expected_skills = {
        "loop",
        "office-hours",
        "strategy",
        "ideate",
        "brainstorm",
        "plan",
        "work",
        "qa",
        "retro",
        "resume",
        "founder-review",
        "doc-review",
        "code-review",
        "optimize",
    }
    for skill in expected_skills:
        skill_path = PLUGIN_ROOT / "skills" / skill / "SKILL.md"
        assert _frontmatter_name(skill_path) == skill

    loop_doc = _read(PLUGIN_ROOT / "skills" / "loop" / "SKILL.md")
    for required in (
        "STRATEGY.md",
        "docs/work-sessions/",
        ".claude/infiquetra-loop/",
        "team-execution",
        "infiquetra-deploy",
        "sdlc-manager",
        "issue progress",
        "doc-review",
        "engineering-journal",
    ):
        assert required in loop_doc

    for script in (
        "parse_issue.py",
        "scaffold_checkpoint.py",
        "find_inflight_work.py",
        "load_saga_context.py",
        "discover_subissues.py",
        "issue_progress.py",
    ):
        assert (PLUGIN_ROOT / "scripts" / script).exists()

    doc_review_doc = _read(PLUGIN_ROOT / "skills" / "doc-review" / "SKILL.md")
    for required in (
        "/blueprint-review",
        "/spec-review",
        "/issue-review",
        "/founder-review",
        "classification",
        "review-result contract",
        "target path",
        "reviewed revision",
        "blocked status",
        "override rationale",
        "any `P0` or `P1`",
        "safe fixes",
        "docs/reviews/",
    ):
        assert required in doc_review_doc
    assert not (PLUGIN_ROOT / "commands" / "ce-doc-review.md").exists()


def test_destination_selector_and_escalation_helpers() -> None:
    lifecycle = _load_module("lifecycle_state.py")

    assert lifecycle.normalize_destination("plan") == "plan-only"
    assert lifecycle.normalize_destination("nonprod deploy") == "nonprod-deploy"
    assert lifecycle.destination_includes_deploy("nonprod-deploy")
    assert not lifecycle.destination_includes_deploy("pr")

    assert (
        lifecycle.should_offer_team_execution(
            file_count=2,
            phase_count=2,
            has_security=False,
            has_infra=False,
            cross_repo=False,
            deployment_sensitive=False,
        )
        is False
    )
    assert (
        lifecycle.should_offer_team_execution(
            file_count=1,
            phase_count=1,
            has_security=True,
            has_infra=False,
            cross_repo=False,
            deployment_sensitive=False,
        )
        is True
    )


def test_issue_progress_comments_include_required_evidence() -> None:
    issue_progress = _load_module("issue_progress.py")

    start = issue_progress.render_issue_comment(
        event="start",
        issue_ref="infiquetra/campps-service#42",
        destination="nonprod-deploy",
        plan_path="docs/plans/2026-05-29-campps-service.md",
        summary="Add deployment status endpoint.",
    )
    assert "selected destination: nonprod-deploy" in start
    assert "docs/plans/2026-05-29-campps-service.md" in start

    phase = issue_progress.render_issue_comment(
        event="phase",
        issue_ref="infiquetra/campps-service#42",
        destination="nonprod-deploy",
        work_session_path="docs/work-sessions/2026-05-29-phase-1.md",
        commit_sha="abc1234",
        checks_run=["uv run pytest tests/test_service.py -q"],
        blockers="None",
    )
    assert "docs/work-sessions/2026-05-29-phase-1.md" in phase
    assert "abc1234" in phase
    assert "uv run pytest tests/test_service.py -q" in phase

    review = issue_progress.render_issue_comment(
        event="phase",
        issue_ref="infiquetra/campps-service#42",
        destination="pr",
        doc_review_artifact="docs/reviews/2026-05-29-doc-review.md",
        doc_review_blocked=True,
        doc_review_fixes=["Added missing gate."],
        doc_review_findings=["P1 Missing rollback evidence."],
        doc_review_override="Proceeding after owner accepted risk.",
    )
    assert "doc review artifact: docs/reviews/2026-05-29-doc-review.md" in review
    assert "doc review blocked: yes" in review
    assert "doc review override: Proceeding after owner accepted risk." in review
    assert "doc review fixes:" in review
    assert "Added missing gate." in review
    assert "doc review findings:" in review
    assert "P1 Missing rollback evidence." in review


def test_deploy_strategy_detection_matches_infiquetra_policy() -> None:
    deploy_strategy = _load_module("detect_deploy_strategy.py")

    assert (
        deploy_strategy.classify(
            ["deploy-nonprod.yml", "deploy-staging.yml", "deploy-production.yml"]
        )["strategy"]
        == "tag-promotion"
    )
    partial = deploy_strategy.classify(["post-merge.yml", "deploy-staging.yml"])
    assert partial["strategy"] == "tag-promotion-partial"
    assert partial["envs_available"] == ["staging"]


def test_issue_parser_extracts_infiquetra_context_and_risk_flags() -> None:
    parse_issue = _load_module("parse_issue.py")

    extracted = parse_issue.extract("ADR-0004 Round 2\n\nAC-1 Add OpenAPI endpoint with IAM auth.")

    assert extracted["adr_refs"] == ["ADR-0004"]
    assert extracted["ac_refs"] == ["AC-1"]
    assert extracted["round_refs"] == [2]
    assert extracted["flags"]["has_api"] is True
    assert extracted["flags"]["has_security"] is True
