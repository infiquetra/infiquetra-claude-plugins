"""Contract tests for the infiquetra-lifecycle plugin package."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

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
    assert plugin_json["version"] == "0.10.0"
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


def test_founder_review_engine_port_contract() -> None:
    """Mechanism-floor contract for the ported /founder-review engine (0.9.0).

    Floors are calibrated to E1's actual authored tokens but structural enough that a
    vibes-y reskin (the prior 20-line stub) fails: a stub names neither the 4 committed
    scope modes, the 18 CEO patterns / 9 Prime Directives, the commit-no-drift rule, the
    FLAT->EXPANSIVE framing, the A/B/C capped opt-in, the target-conditional ceremonies,
    nor the CLOSED-LOOP artifact handback. It also pins the no-saga-write mechanism (the
    one thing that separates /founder-review from its saga-writing sibling /code-review).
    See E1-authored founder-review skill + its 2 references.
    """
    review = PLUGIN_ROOT / "skills" / "founder-review"
    skill_doc = _read(review / "SKILL.md")
    cognition_doc = _read(review / "references" / "ceo-cognition.md")
    modes_doc = _read(review / "references" / "review-modes.md")

    # All 4 committed scope-mode names (the engine spine) — present in SKILL + modes ref.
    for mode in ("SCOPE EXPANSION", "SELECTIVE EXPANSION", "HOLD SCOPE", "SCOPE REDUCTION"):
        assert mode in skill_doc
        assert mode in modes_doc

    # >= 8 of the 18 CEO cognitive patterns named in ceo-cognition.md (internalized roster).
    ceo_patterns = (
        "Classification instinct",
        "Paranoid scanning",
        "Inversion reflex",
        "Focus as subtraction",
        "People-first sequencing",
        "Speed calibration",
        "Proxy skepticism",
        "Narrative coherence",
        "Temporal depth",
        "Founder-mode bias",
        "Wartime awareness",
        "Courage accumulation",
        "Willfulness as strategy",
        "Leverage obsession",
        "Hierarchy as service",
        "Edge case paranoia",
        "Subtraction default",
        "Design for trust",
    )
    assert sum(1 for p in ceo_patterns if p in cognition_doc) >= 8

    # >= 6 of the 9 Prime Directives named in ceo-cognition.md (scope-level lenses).
    prime_directives = (
        "Zero silent failures",
        "Every error has a name",
        "shadow paths",
        "Interactions have edge cases",
        "Observability is scope",
        "Diagrams are mandatory",
        "deferred must be written",
        "6-month future",
        'permission to say "scrap it',
    )
    assert sum(1 for d in prime_directives if d in cognition_doc) >= 6

    # Commit-no-drift literal: once a mode is chosen it is committed for the whole review.
    assert "commit" in skill_doc
    assert "no silent drift" in skill_doc

    # Expansion-framing mechanism: lead with felt experience, close with effort + impact.
    assert "FLAT" in skill_doc and "EXPANSIVE" in skill_doc
    assert "felt experience" in skill_doc
    assert "FLAT" in modes_doc and "EXPANSIVE" in modes_doc

    # The 3 opt-in options (A add / B defer / C skip) + the cap (top 5-6 if > 8 candidates).
    for option in ("A) add", "B) defer", "C) skip"):
        assert option in skill_doc
    assert "top 5-6" in skill_doc
    assert "than 8" in skill_doc

    # Target-conditional gating: 0C-bis + 0E conditional on plan vs strategy/scope-question.
    assert "0C-bis" in skill_doc
    assert "0E" in skill_doc
    assert "TARGET-CONDITIONAL" in skill_doc
    assert "TARGET-CONDITIONAL" in modes_doc
    # The conditional pivots on the target type the gating keys off.
    for target in ("plan", "strategy", "scope-question"):
        assert target in skill_doc

    # CLOSED-LOOP handback token: the expanded-plan PATH is handed to /doc-review, not just
    # a bare "/doc-review" mention. This is the mechanism that prevents the rigor evaporating.
    assert "/doc-review docs/plans/" in skill_doc
    assert "/doc-review docs/plans/" in modes_doc
    assert "/code-review" in skill_doc

    # Own-dir scope-decision artifact (NOT docs/reviews/, NOT docs/code-reviews/).
    assert "docs/founder-reviews/" in skill_doc
    assert "docs/founder-reviews/" in modes_doc

    # Boundary: it CHALLENGES direction (not "records" it — /strategy records).
    assert "challenges" in skill_doc
    assert "record" in skill_doc  # the "does not record strategy" / "/strategy records" boundary
    # Gate-only negatives — E1 bolds the NOT.
    for negative in (
        "does **NOT** implement",
        "does **NOT** commit",
        "does **NOT** file",
        "does **NOT** make code",
    ):
        assert negative in skill_doc

    # Operator-choice citation at the plugin-root path + the 3 backend enums.
    assert "references/operator-choice.md" in skill_doc
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in skill_doc

    # NO SAGA WRITE (the mechanism that separates /founder-review from /code-review):
    # /founder-review runs upstream of the work thread and must NOT emit a runnable saga
    # write. E1 mentions the tokens only inside explicit negations ("never writes the saga
    # (no saga.py call, no --review-paths)"), so a literal token-absence assertion would
    # fail a FAITHFUL engine. Pin the mechanism instead: no runnable `saga.py save` command
    # and no `--review-paths <value>` assignment (the exact pattern /code-review uses).
    assert "saga.py save" not in skill_doc
    assert not re.search(r"--review-paths\s+\S", skill_doc)
    assert not re.search(r"python3?\s+\S*saga\.py", skill_doc)

    # Blunt thin-port tripwire: each reference file carries real content (>= 60 lines).
    for ref in ("ceo-cognition.md", "review-modes.md"):
        ref_path = review / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60


def test_work_engine_merge_contract() -> None:
    """Mechanism-floor contract for the rebuilt engine-merge /work engine (0.10.0).

    These are MECHANISM floors, not noun-lists (DA-M10): a vibes reskin of the prior
    39-line facilitator stub MUST fail. Each floor pins a runnable wiring the rebuild
    exists to land — a literal saga write with the work-phase + round flags, the runnable
    backend-recommendation CLI, the total PR-state read, the computed staleness command,
    the extended issue-progress CLI call, and the saga-identity handoff into /code-review.
    Presence-of-phrase checks are demoted to a secondary block at the end.

    Tokens are taken from the actual E1-authored SKILL.md + its 3 references on disk.
    """
    work = PLUGIN_ROOT / "skills" / "work"
    skill_doc = _read(work / "SKILL.md")
    exec_doc = _read(work / "references" / "execution-strategy.md")
    gates_doc = _read(work / "references" / "test-and-gates.md")
    loop_doc = _read(work / "references" / "pr-continuation-loop.md")
    # The runnable backend CLI line lives in the execution-strategy ref; the SKILL points
    # at it. Mechanism floors are asserted against whichever surface actually carries them.
    corpus = "\n".join((skill_doc, exec_doc, gates_doc, loop_doc))

    # --- MECHANISM FLOOR 1: a literal runnable saga write minting the work-thread saga ---
    # /work is the saga's primary writer; the minted thread must carry the work lifecycle
    # phase AND the round axis (--rounds-seen, never the derived next_round). A stub names
    # neither. Pin a single literal `saga.py save` invocation that contains both flags so a
    # bare "writes a saga" mention cannot satisfy the floor.
    save_blocks = re.findall(r"saga\.py save.*?(?=\n#|\n```|\Z)", skill_doc, flags=re.DOTALL)
    assert any(
        "--lifecycle-phase work" in block and "--rounds-seen" in block for block in save_blocks
    ), (
        "SKILL must contain a runnable `saga.py save` carrying --lifecycle-phase work AND --rounds-seen"
    )

    # --- MECHANISM FLOOR 2: a literal recommend-backend CLI invocation with >= 1 flag ---
    # The deferred helper lands here; the engine must EMIT a runnable CLI call, not just name
    # the function. Require the subcommand followed (same or continued line) by >= 1 --flag.
    assert re.search(
        r"recommend-backend(?:[^\n]*\\\n[^\n]*|[^\n]*)--\w",
        corpus,
    ), "engine must emit a runnable `recommend-backend` CLI invocation with at least one flag"

    # --- MECHANISM FLOOR 3: the total PR --json read (state + reviewDecision + check status) ---
    # The round-N loop is driven by a TOTAL read of live PR state. A `gh pr view --json` that
    # omits reviewDecision or the check-status field cannot drive the transition table.
    pr_json_lines = [
        line for line in corpus.splitlines() if "gh pr view" in line and "--json" in line
    ]
    assert pr_json_lines, "engine must read live PR state via `gh pr view --json`"
    assert any("state" in line for line in pr_json_lines)
    assert any("reviewDecision" in line for line in pr_json_lines)
    assert any(
        ("mergeStateStatus" in line or "statusCheckRollup" in line) for line in pr_json_lines
    ), (
        "the PR --json read must include a check-status field (mergeStateStatus or statusCheckRollup)"
    )

    # --- MECHANISM FLOOR 4: the computed staleness check (git rev-list ...HEAD) ---
    # Staleness is computed, not stored (DA-H6): commits since the reviewed SHA via
    # `git rev-list <sha>..HEAD`. A stub has no such computation.
    assert re.search(r"git rev-list\s+\S*\.\.HEAD", corpus), (
        "engine must compute review staleness via `git rev-list <reviewed_sha>..HEAD`"
    )

    # --- MECHANISM FLOOR 5: the EXTENDED issue_progress.py CLI call (--commit-sha + --checks-run) ---
    # DA-C1: the Phase-4 comment must invoke the now-extended CLI with the real evidence flags.
    progress_blocks = re.findall(r"issue_progress\.py.*?(?=\n#|\n```|\Z)", corpus, flags=re.DOTALL)
    assert any("--commit-sha" in block and "--checks-run" in block for block in progress_blocks), (
        "engine must call the extended issue_progress.py CLI with --commit-sha AND --checks-run"
    )

    # --- MECHANISM FLOOR 6: the forward-coupling write + the in-loop gate ---
    # The corrected coupling (DA-C3, hardened after the build review): /work mints a FINDABLE saga
    # (sets --issue-ref, the saga-spec §11 issue_ref-adoption write + a code-review match key) that a
    # standalone /code-review can append to; for its OWN gate /work runs /code-review programmatically and
    # reads the envelope directly, capturing the reviewed SHA itself (git rev-parse HEAD) — no dependency
    # on code-review writing an artifact (it writes none in programmatic mode).
    assert any("--issue-ref" in block for block in save_blocks), (
        "the mint must set --issue-ref (the saga-spec §11 issue_ref-adoption write + code-review match key)"
    )
    assert "/code-review" in skill_doc
    assert "programmatic" in skill_doc, (
        "the /code-review call must be the programmatic/report-only mode"
    )
    assert "git rev-parse HEAD" in corpus, (
        "/work must capture the reviewed SHA itself (git rev-parse HEAD) for the staleness gate"
    )

    # --- MECHANISM FLOOR 7: each of the 3 reference files carries real content (>= 60 lines) ---
    # Blunt thin-port tripwire — a vibes reskin would leave the refs as stubs.
    for ref in ("execution-strategy.md", "test-and-gates.md", "pr-continuation-loop.md"):
        ref_path = work / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60

    # --- SECONDARY (presence-of-phrase, demoted): boundary + adapted-source markers ---
    # Hard boundary negatives: merge under confirmation, no deploy/canary ownership, no
    # lifecycle advance past work. These are intent markers, not mechanism floors.
    assert "infiquetra-deploy" in corpus  # deploy mutation is delegated, not owned
    assert "sdlc-manager" in corpus  # issue comments routed out, not filed by /work
    assert "Parallel Safety Check" in corpus  # CE execution mechanics carried
    assert "requires_hard_test_gate" in corpus  # the canonical change-kind gate is named
    assert "merge-base" in corpus.lower()  # gstack merge-base-before-tests carried
    # qa/resume routing is advisory and lifecycle does not advance past work.
    assert "advisor" in corpus.lower()  # advisory qa/resume routing
    assert "lifecycle_phase" in corpus  # the phase the engine deliberately does not advance


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


def test_recommend_execution_backend_precedence_and_overlap() -> None:
    """Unit-level contract for the deferred-from-0.5.0 backend helper that lands with /work.

    Precedence is the lean operator-choice section 3.3 ladder: a size/risk OR consensus
    signal -> team-execution; broad independent fan-out without elevated risk ->
    cc-workflows-ultracode; neither -> inline. The load-bearing case is the OVERLAP one:
    alternatives is computed independently of which backend won precedence, so a job that
    is both contested AND broadly parallel recommends team-execution yet still LISTS
    cc-workflows-ultracode as a one-keystroke escalation.
    """
    lifecycle = _load_module("lifecycle_state.py")

    # Precedence: a size/risk trigger (file_count >= 8) -> team-execution. The helper
    # reuses should_offer_team_execution's thresholds, so the >= 8 boundary must carry.
    risky_by_size = lifecycle.recommend_execution_backend(file_count=9)
    assert risky_by_size["recommended"] == "team-execution"
    risky_by_security = lifecycle.recommend_execution_backend(has_security=True)
    assert risky_by_security["recommended"] == "team-execution"

    # Reuses should_offer_team_execution thresholds: file_count == 8 trips, 7 does not.
    assert lifecycle.recommend_execution_backend(file_count=8)["recommended"] == "team-execution"
    assert lifecycle.recommend_execution_backend(file_count=7)["recommended"] == "inline"

    # Precedence: broad independent fan-out without elevated risk -> cc-workflows-ultracode.
    fanout = lifecycle.recommend_execution_backend(broad_independent_fanout=True)
    assert fanout["recommended"] == "cc-workflows-ultracode"

    # An elevated-risk signal suppresses the ultracode branch (it must not run risky
    # work through deterministic fan-out) and falls back to team-execution.
    risky_fanout = lifecycle.recommend_execution_backend(
        broad_independent_fanout=True, has_infra=True
    )
    assert risky_fanout["recommended"] == "team-execution"

    # Precedence: neither signal -> inline.
    assert lifecycle.recommend_execution_backend()["recommended"] == "inline"

    # OVERLAP: consensus (-> team wins precedence) AND broad fan-out (-> ultracode reachable).
    # Recommended is team-execution, but cc-workflows-ultracode MUST still be an alternative.
    overlap = lifecycle.recommend_execution_backend(
        broad_independent_fanout=True, needs_consensus=True
    )
    assert overlap["recommended"] == "team-execution"
    assert "cc-workflows-ultracode" in overlap["alternatives"]
    # The recommended backend is never echoed back into its own alternatives.
    assert "team-execution" not in overlap["alternatives"]

    # omit_ultracode when the Workflow tool is unavailable: the flag is set AND
    # cc-workflows-ultracode is dropped from alternatives (it is no longer reachable).
    no_workflow = lifecycle.recommend_execution_backend(
        broad_independent_fanout=True, needs_consensus=True, workflow_available=False
    )
    assert no_workflow["omit_ultracode"] is True
    assert "cc-workflows-ultracode" not in no_workflow["alternatives"]
    # With ultracode capability-gated out, a pure-fan-out job degrades to inline.
    assert (
        lifecycle.recommend_execution_backend(
            broad_independent_fanout=True, workflow_available=False
        )["recommended"]
        == "inline"
    )
    # When workflow IS available, omit_ultracode stays false.
    assert lifecycle.recommend_execution_backend()["omit_ultracode"] is False


def test_lifecycle_state_cli_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    """The main() subcommand refactor: normalize + recommend-backend exist; bare positional fails.

    The CLI was refactored from a bare positional ``destination`` into subcommands so the
    deferred helper gets a real markdown caller. recommend-backend emits JSON; normalize
    preserves today's behavior; a bare ``deploy`` (the old positional usage) must now exit
    non-zero via argparse instead of silently succeeding.
    """
    lifecycle = _load_module("lifecycle_state.py")

    # recommend-backend subcommand -> JSON on stdout, parsed and asserted.
    assert lifecycle.main(["recommend-backend", "--file-count", "9"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["recommended"] == "team-execution"

    # The overlap escalation survives the CLI surface end-to-end.
    assert lifecycle.main(["recommend-backend", "--broad-fanout", "--needs-consensus"]) == 0
    overlap = json.loads(capsys.readouterr().out)
    assert overlap["recommended"] == "team-execution"
    assert "cc-workflows-ultracode" in overlap["alternatives"]

    # --no-workflow flows through to omit_ultracode via the CLI.
    assert lifecycle.main(["recommend-backend", "--broad-fanout", "--no-workflow"]) == 0
    no_workflow = json.loads(capsys.readouterr().out)
    assert no_workflow["omit_ultracode"] is True

    # normalize subcommand preserves the legacy alias resolution.
    assert lifecycle.main(["normalize", "deploy"]) == 0
    assert capsys.readouterr().out.strip() == "nonprod-deploy"

    # The bare positional (old behavior) is now an invalid subcommand: argparse raises
    # SystemExit instead of silently succeeding. This is the M8 caller-safety contract.
    with pytest.raises(SystemExit) as exc_info:
        lifecycle.main(["deploy"])
    assert exc_info.value.code != 0


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


def test_issue_progress_cli_renders_extended_work_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """DA-C1: the CLI must expose the fields /work's Phase-4 comment passes.

    render_issue_comment() already accepted these fields, but the argparse surface only
    exposed 8 — so /work's markdown call was uninvokable. The rebuild extends parse_args/main
    to forward the function's full field set. Drive main() with a faked argv (the helper's
    main() takes argv directly) and assert each new flag's value lands in the rendered output.
    """
    issue_progress = _load_module("issue_progress.py")

    rc = issue_progress.main(
        [
            "--event",
            "phase",
            "--issue-ref",
            "infiquetra/campps-service#42",
            "--destination",
            "pr",
            "--work-session-path",
            "docs/work-sessions/2026-06-03-phase-2.md",
            "--commit-sha",
            "deadbeef",
            "--checks-run",
            "pytest|ruff",
            "--blockers",
            "None",
            "--pr-url",
            "https://github.com/infiquetra/campps-service/pull/7",
            "--review-status",
            "APPROVED",
            "--doc-review-artifact",
            "docs/reviews/2026-06-03-doc-review.md",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0

    # Each new CLI flag's value renders into the comment.
    assert "docs/work-sessions/2026-06-03-phase-2.md" in out
    assert "deadbeef" in out
    # --checks-run is pipe-split; each check renders on its own indented bullet.
    assert "`pytest`" in out
    assert "`ruff`" in out
    assert "blockers: None" in out
    assert "https://github.com/infiquetra/campps-service/pull/7" in out
    assert "review status: APPROVED" in out
    assert "doc review artifact: docs/reviews/2026-06-03-doc-review.md" in out


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
