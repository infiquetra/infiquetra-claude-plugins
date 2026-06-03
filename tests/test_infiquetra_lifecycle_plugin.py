"""Contract tests for the infiquetra-lifecycle plugin package."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "infiquetra-lifecycle"


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


def test_infiquetra_lifecycle_metadata_and_marketplace_entry_match() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "infiquetra-lifecycle")

    assert plugin_json["name"] == "infiquetra-lifecycle"
    assert plugin_json["version"] == "0.8.0"
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/infiquetra-lifecycle"
    assert "lifecycle" in plugin_json["description"]
    assert {"lifecycle", "strategy", "handoff", "doc-review", "code-review"} <= set(
        plugin_json["keywords"]
    )


def test_infiquetra_lifecycle_commands_are_packaged() -> None:
    for command in (
        "loop",
        "office-hours",
        "strategy",
        "ideate",
        "brainstorm",
        "handoff",
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


def test_infiquetra_lifecycle_skills_document_required_lifecycle_behavior() -> None:
    expected_skills = {
        "loop",
        "office-hours",
        "strategy",
        "ideate",
        "brainstorm",
        "handoff",
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
        ".claude/infiquetra-lifecycle/",
        "team-execution",
        "infiquetra-deploy",
        "sdlc-manager",
        "/handoff",
        "issue progress",
        "doc-review",
        "engineering-journal",
    ):
        assert required in loop_doc

    for script in (
        "parse_issue.py",
        "saga.py",
        "scaffold_checkpoint.py",
        "find_inflight_work.py",
        "load_saga_context.py",
        "discover_subissues.py",
        "issue_progress.py",
        "handoff_envelope.py",
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

    handoff_doc = _read(PLUGIN_ROOT / "skills" / "handoff" / "SKILL.md")
    assert "sdlc-manager" in handoff_doc
    assert "Do not copy SDLC issue templates" in handoff_doc
    assert "/create-issue --prepare" in handoff_doc
    assert "Do not suggest `/loop`" in handoff_doc

    plan_doc = _read(PLUGIN_ROOT / "skills" / "plan" / "SKILL.md")
    work_doc = _read(PLUGIN_ROOT / "skills" / "work" / "SKILL.md")
    assert "`idea-ready` or `requirements-ready`" in plan_doc
    assert "`plan-ready` or `resume-ready`" in work_doc
    assert "/plan <issue>" in work_doc


def test_office_hours_two_mode_and_hard_gate_contract() -> None:
    """Structural contract for the rebuilt two-mode frame-finding office-hours engine.

    Tokens are chosen from the actual authored SKILL.md / frame-diagnostic.md so the
    assertions track the contract, not fragile prose. See E1-authored office-hours skill.
    """
    skill_doc = _read(PLUGIN_ROOT / "skills" / "office-hours" / "SKILL.md")
    diagnostic_doc = _read(
        PLUGIN_ROOT / "skills" / "office-hours" / "references" / "frame-diagnostic.md"
    )
    combined = skill_doc + "\n" + diagnostic_doc

    # Both modes are present as named modes in the SKILL or its reference.
    assert "Startup mode" in combined
    assert "Builder mode" in combined

    # HARD GATE intent: office-hours diagnoses and routes; it never implements/plans/
    # scaffolds/files an SDLC issue. Both the stable token and the no-implementation
    # phrasing the author used must be present.
    assert "HARD GATE" in skill_doc
    assert "never file an SDLC issue" in skill_doc

    # Office-hours must NOT name "SDLC issue" as one of ITS outputs (the old 23-line stub
    # did: "End with the next useful artifact: ... SDLC issue"). The rebuild must not carry
    # that artifact-list phrasing.
    assert "next useful artifact" not in skill_doc

    # Routing targets are present (these are not the only exits, but all must appear).
    for route in ("/ideate", "/brainstorm", "/plan", "/strategy"):
        assert route in skill_doc

    # Frame-note home is its own directory.
    assert "docs/office-hours/" in skill_doc


def test_plan_engine_merge_contract() -> None:
    """Structural contract for the rebuilt engine-merge /plan engine.

    Tokens are chosen from the actual authored SKILL.md / plan-sections.md / interrogation.md
    so the assertions track the contract, not fragile prose. See E1-authored plan skill (0.7.0).
    """
    skill_doc = _read(PLUGIN_ROOT / "skills" / "plan" / "SKILL.md")
    sections_doc = _read(PLUGIN_ROOT / "skills" / "plan" / "references" / "plan-sections.md")
    interrogation_doc = _read(PLUGIN_ROOT / "skills" / "plan" / "references" / "interrogation.md")

    # Position-in-lifecycle: /plan owns the HOW.
    assert '`/plan` answers: "How should it be built?"' in skill_doc

    # CE plan skeleton: the durable artifact carries the hard-floor section markers and IDed units.
    # /doc-review and /work parse these tokens, so they must appear verbatim in SKILL + contract ref.
    for marker in ("Implementation Units", "Key Technical Decisions", "Requirements"):
        assert marker in skill_doc
        assert marker in sections_doc
    # Stable U-ID prefix (the marker /doc-review keys on to recognize the doc as a plan).
    assert "U1" in skill_doc
    assert "U-ID" in sections_doc

    # Warranted-gate: not every invocation produces a plan doc; the gate is named in both files.
    assert "warranted" in skill_doc
    assert "warranted" in sections_doc
    assert "Warranted-gate" in skill_doc or "warranted-gate" in skill_doc

    # HOW-only interrogation: the register pins the HOW and assumes the WHAT is settled upstream.
    assert "HOW-interrogation" in skill_doc or "HOW register" in interrogation_doc
    assert "Failure-mode" in skill_doc and "failure-mode" in interrogation_doc.lower()

    # /brainstorm bounce: when interrogation reveals the WHAT is unsettled, route back to /brainstorm,
    # without claiming /brainstorm "accepts" a handoff (the explicit guard).
    assert "recommend the operator run `/brainstorm` first" in skill_doc
    assert "recommend the operator run\n`/brainstorm` first" in interrogation_doc or (
        "recommend the operator run `/brainstorm` first" in interrogation_doc
    )
    assert '`/brainstorm` "accepts" a handoff' in skill_doc

    # Saga CLI write: Phase 5 emits a runnable saga save with the orchestration-mode flag.
    assert "saga.py" in skill_doc
    assert "--orchestration-mode" in skill_doc
    assert "--lifecycle-phase plan" in skill_doc

    # Operator-choice citation: the doc-only decision contract plus the 3 backend enum strings.
    assert "references/operator-choice.md" in skill_doc
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in skill_doc

    # Deepening / confidence pass: Phase 4 conditional strengthening, with the rubric in the ref.
    assert "confidence" in skill_doc.lower()
    assert "Confidence pass (deepening)" in sections_doc

    # Routing: /plan recommends /doc-review (the review phase) before /work, and emits the origin:
    # frontmatter token so the review phase can trace the plan to its source.
    assert "/doc-review" in skill_doc
    assert "/work" in skill_doc
    assert "origin:" in skill_doc


def test_code_review_engine_merge_contract() -> None:
    """Richness-floor contract for the rebuilt engine-merge /code-review engine (0.8.0).

    Floors are calibrated to E1's actual authored tokens but structural enough that a thin
    port (the prior 20-line stub) fails: a stub names neither the 5 plan-completion states,
    the 5 confidence anchors, the 4 autofix classes / owners, nor the judgment-lens roster.
    See E1-authored code-review skill + its 4 references.
    """
    review = PLUGIN_ROOT / "skills" / "code-review"
    skill_doc = _read(review / "SKILL.md")
    built_doc = _read(review / "references" / "built-vs-planned.md")
    schema_doc = _read(review / "references" / "findings-schema.md")
    lens_doc = _read(review / "references" / "lens-catalog.md")

    # built-vs-planned.md: all 5 plan-completion states + all 3 verification modes.
    # E1 used the hyphenated "NOT-DONE" token (not "NOT DONE").
    for state in ("DONE", "PARTIAL", "NOT-DONE", "CHANGED", "UNVERIFIABLE"):
        assert state in built_doc
    for mode in ("DIFF", "CROSS-REPO", "EXTERNAL-STATE"):
        assert mode in built_doc

    # findings-schema.md: all 5 confidence anchors + all 4 autofix_class + all 4 owner.
    for anchor in ("0", "25", "50", "75", "100"):
        assert f"**{anchor}**" in schema_doc
    for klass in ("safe_auto", "gated_auto", "manual", "advisory"):
        assert klass in schema_doc
    for owner in ("review-fixer", "downstream-resolver", "human", "release"):
        assert owner in schema_doc

    # lens-catalog.md: the 4 always-on lenses + >= 4 conditional lenses, incl.
    # the distinct deploy/migration-verification lens (never folded away).
    for always_on in ("correctness", "security", "testing", "maintainability"):
        assert always_on in lens_doc
    conditional = (
        "deploy/migration-verification",
        "reliability",
        "performance",
        "api-contract",
        "adversarial",
        "agent-native",
    )
    assert sum(1 for lens in conditional if lens in lens_doc) >= 4
    assert "deploy/migration-verification" in lens_doc

    # SKILL.md: gate-only negatives (does not commit / push / file). E1 bolds the NOT.
    for negative in ("does **NOT** commit", "does **NOT** push", "does **NOT** file"):
        assert negative in skill_doc
    # Saga literals: an append-only review-track write with both flags.
    assert "saga.py" in skill_doc
    assert "--review-paths" in skill_doc
    assert "--orchestration-mode" in skill_doc
    # Own-dir durable artifact path (NOT docs/reviews/).
    assert "docs/code-reviews/" in skill_doc
    # Operator-choice citation at the plugin-root path + the 3 backend enums.
    assert "references/operator-choice.md" in skill_doc
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in skill_doc

    # Blunt thin-port tripwire: each of the 4 reference files carries real content.
    for ref in ("lens-catalog.md", "findings-schema.md", "validator.md", "built-vs-planned.md"):
        ref_path = review / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60


def test_operator_choice_framework_is_documented_and_cited() -> None:
    operator_choice_path = PLUGIN_ROOT / "references" / "operator-choice.md"
    assert operator_choice_path.exists()
    operator_choice_doc = _read(operator_choice_path)
    for enum_value in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert enum_value in operator_choice_doc

    loop_doc = _read(PLUGIN_ROOT / "skills" / "loop" / "SKILL.md")
    work_doc = _read(PLUGIN_ROOT / "skills" / "work" / "SKILL.md")
    assert "references/operator-choice.md" in loop_doc
    assert "references/operator-choice.md" in work_doc


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
        handoff_maturity="plan-ready",
        handoff_source="docs/plans/example.md",
        next_action="/work <issue>",
        doc_review_artifact="docs/reviews/2026-05-29-doc-review.md",
        doc_review_blocked=True,
        doc_review_fixes=["Added missing gate."],
        doc_review_findings=["P1 Missing rollback evidence."],
        doc_review_override="Proceeding after owner accepted risk.",
    )
    assert "doc review artifact: docs/reviews/2026-05-29-doc-review.md" in review
    assert "handoff maturity: plan-ready" in review
    assert "handoff source: docs/plans/example.md" in review
    assert "next action: /work <issue>" in review
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
    assert extracted["handoff"]["maturity"] == ""


def test_issue_parser_extracts_handoff_maturity_and_source_context() -> None:
    parse_issue = _load_module("parse_issue.py")

    body = """### Objective
Build the thing.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: docs/plans/example.md
- Source type: plan
- Source title: Example Plan
"""

    extracted = parse_issue.extract(body)

    assert extracted["handoff"] == {
        "maturity": "plan-ready",
        "suggested_next_action": "Use `/work <issue>` to execute from the plan-grade context.",
        "source": "docs/plans/example.md",
        "source_type": "plan",
        "source_title": "Example Plan",
        "can_plan": False,
        "can_work": True,
        "requires_clarification": False,
    }


def test_handoff_envelope_routes_to_sdlc_manager_without_issue_body_ownership(tmp_path) -> None:
    handoff = _load_module("handoff_envelope.py")
    plan = tmp_path / "docs" / "plans" / "example.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Example Plan\n")

    envelope = handoff.build_handoff_envelope(
        "docs/plans/example.md",
        target_team="Asgard",
        target_repo="infiquetra-claude-plugins",
        issue_type="capability",
        reason="another team should pick this up",
        root=tmp_path,
    )

    assert envelope["source"] == "docs/plans/example.md"
    assert envelope["lifecycle_phase"] == "plan"
    assert envelope["handoff_maturity"] == "plan-ready"
    assert envelope["lifecycle_owner"] == "infiquetra-lifecycle"
    assert envelope["issue_artifact_owner"] == "sdlc-manager"
    assert envelope["body_template_owner"] == "sdlc-manager"
    assert envelope["suggested_command"].startswith("/create-issue --prepare")
    assert "--from docs/plans/example.md" in envelope["suggested_command"]
    assert "--maturity plan-ready" in envelope["suggested_command"]
    assert "/loop" not in envelope["suggested_command"]


def test_handoff_envelope_discovers_active_plan_from_loop_state(tmp_path) -> None:
    handoff = _load_module("handoff_envelope.py")
    state = tmp_path / ".claude" / "infiquetra-lifecycle" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps({"current_work": {"plan_path": "docs/plans/active.md"}}),
        encoding="utf-8",
    )

    envelope = handoff.build_handoff_envelope(root=tmp_path)

    assert envelope["source"] == "docs/plans/active.md"
    assert envelope["handoff_maturity"] == "plan-ready"
