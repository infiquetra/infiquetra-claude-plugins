"""Contract tests for the saga plugin package."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "saga"


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
    entry = next(p for p in marketplace["plugins"] if p["name"] == "saga")

    assert plugin_json["name"] == "saga"
    assert plugin_json["version"] == "0.49.2"  # readonly-verifier fallback + drift guard (#325)
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/saga"
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
        "promote",
        "resume",
        "founder-review",
        "ceo-review",
        "doc-review",
        "code-review",
        "optimize",
        "investigate",
        "spec",
        "outcome",
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
        "promote",
        "resume",
        "founder-review",
        "doc-review",
        "code-review",
        "optimize",
        "investigate",
        "spec",
        "outcome",
    }
    for skill in expected_skills:
        skill_path = PLUGIN_ROOT / "skills" / skill / "SKILL.md"
        assert _frontmatter_name(skill_path) == skill

    # The rebuilt /loop (0.11.0) router/resume-substrate contract is asserted by the
    # dedicated test_loop_engine_merge_contract against the new SKILL.md + its two
    # references; the old inline loop_doc token block here was superseded by it.

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
    # FOLD: the standalone /blueprint-review, /spec-review, /issue-review commands were
    # folded into doc-review. It now runs the rubric engine inline against the rubric tree
    # instead of delegating to those commands.
    for required in (
        "references/rubrics",
        "lifecycle_review",
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
    for folded_away in ("/blueprint-review", "/spec-review", "/issue-review"):
        assert folded_away not in doc_review_doc
    # The folded rubric tree lives under saga/references/rubrics/{idea,spec,issue}/{core,extras}/.
    rubrics_root = PLUGIN_ROOT / "references" / "rubrics"
    for phase in ("idea", "spec", "issue"):
        for tier in ("core", "extras"):
            assert (rubrics_root / phase / tier).is_dir()
    # The rubric engine script lives under saga/scripts/.
    assert (PLUGIN_ROOT / "scripts" / "lifecycle_review.py").exists()
    assert not (PLUGIN_ROOT / "commands" / "ce-doc-review.md").exists()

    handoff_doc = _read(PLUGIN_ROOT / "skills" / "handoff" / "SKILL.md")
    assert "mission-control" in handoff_doc
    assert "Do not copy SDLC issue templates" in handoff_doc
    assert "/issue --prepare" in handoff_doc
    assert "Do not suggest `/loop`" in handoff_doc

    plan_doc = _read(PLUGIN_ROOT / "skills" / "plan" / "SKILL.md")
    work_doc = _read(PLUGIN_ROOT / "skills" / "work" / "SKILL.md")
    assert "`idea-ready` or `requirements-ready`" in plan_doc
    assert "`plan-ready` or `resume-ready`" in work_doc
    assert "/plan <issue>" in work_doc


def test_outcome_skill_documents_autonomous_board_sync() -> None:
    """#279 U5 doc-contract: the /outcome SKILL documents the autonomous board-sync envelope.

    Mutation-proof — each assertion pins a distinct, load-bearing claim of the reversibility-gated
    autonomy contract, so deleting or weakening the prose makes the test go red. No vacuous absence
    assertions (a token that never existed): every check requires substantive prose to be present.
    """
    raw = _read(PLUGIN_ROOT / "skills" / "outcome" / "SKILL.md")
    # Normalize whitespace: markdown wraps prose across lines, so multi-word phrases must be matched
    # against a collapsed-whitespace view (a literal "defaults to GATE" can straddle a line break).
    doc = " ".join(raw.split())
    low = doc.lower()

    # It is opt-in and default-deny (the certificate defaults to GATE).
    assert "--autonomous" in doc
    assert "defaults to GATE" in doc or "default-deny" in low
    assert "authorize_write" in doc

    # The enumerated autonomous ops are documented (semantic content, not one keyword).
    assert "In Progress" in doc  # set-field status target
    assert "sub-issue" in doc and "reopen" in doc  # close + its inverse
    assert "coalesc" in doc  # one coalesced progress comment, no duplicate spam

    # The never-autonomous guarantees are each named.
    assert "Merging a PR" in doc or "Merging" in doc
    assert "deploy" in low
    assert "parent-issue-close" in doc or "parent issue" in low
    assert "ALWAYS_OPERATOR" in doc

    # Fail-loud + idempotent + recorded.
    assert "no silent write" in doc
    assert "idempotency key" in doc
    assert "bounded" in doc  # bounded retry
    assert "board_synced" in doc  # auditable record of each autonomous write


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
    assert "deploy" in corpus  # deploy mutation is delegated, not owned
    assert "mission-control" in corpus  # issue comments routed out, not filed by /work
    assert "Parallel Safety Check" in corpus  # CE execution mechanics carried
    assert "requires_hard_test_gate" in corpus  # the canonical change-kind gate is named
    assert "merge-base" in corpus.lower()  # gstack merge-base-before-tests carried
    # qa/resume routing is advisory and lifecycle does not advance past work.
    assert "advisor" in corpus.lower()  # advisory qa/resume routing
    assert "lifecycle_phase" in corpus  # the phase the engine deliberately does not advance


def test_loop_engine_merge_contract() -> None:
    """Mechanism FLOORS for the rebuilt /loop router + resume substrate (0.11.0).

    These floors prove the SKILL/refs EMIT the real runnable lines the router stands on
    (saga scan/restore, the routing-tick save with both routing flags, the offload
    orchestration pointer, the runnable recommend-backend CLI, the inline cold path) and
    that the boundary prose is present. They do NOT prove the routing LOGIC is correct —
    only that the contract tokens are authored, not vibes-reskinned away. `/loop` is the
    one native rebuild (no upstream engine to port), so the floors track the designed
    contract: it routes/sequences/resumes and never executes a phase or its mutations.

    Tokens are taken from the actual E1-authored SKILL.md + its 2 references on disk.
    """
    loop = PLUGIN_ROOT / "skills" / "loop"
    skill_doc = _read(loop / "SKILL.md")
    dispatch_doc = _read(loop / "references" / "dispatch-table.md")
    resume_doc = _read(loop / "references" / "drive-and-resume.md")
    corpus = "\n".join((skill_doc, dispatch_doc, resume_doc))

    # --- saga resume substrate: scan at entry + restore a thread by id ---
    assert "saga.py scan" in corpus
    assert "saga.py restore --saga-id" in corpus

    # --- the routing-tick saga write carries BOTH the destination class and the resume
    # anchor (--next-step). A bare "ticks the saga" mention cannot satisfy this floor. ---
    save_blocks = re.findall(r"saga\.py save.*?(?=\n#|\n```|\Z)", corpus, flags=re.DOTALL)
    assert any("--destination" in block and "--next-step" in block for block in save_blocks), (
        "a runnable routing-tick `saga.py save` must carry both --destination and --next-step"
    )

    # --- the offload pointer: orchestration mode + ref (only on a /loop-owned offload) ---
    assert "--orchestration-mode" in corpus
    assert "--orchestration-ref" in corpus

    # --- the runnable backend-recommendation CLI with at least one --flag (the helper /loop
    # uses ONLY for its own Drive/router-owned offload, not for routed commands). ---
    assert re.search(
        r"recommend-backend(?:[^\n]*\\\n[^\n]*|[^\n]*)--\w",
        corpus,
    ), "engine must emit a runnable `recommend-backend` CLI invocation with at least one flag"

    # --- the inline cold path: load_saga_context.py reconstructs from committed artifacts. ---
    assert "load_saga_context.py" in corpus

    # --- the across-vs-within boundary with /work (robust: substring + either word). ---
    assert "/work" in skill_doc
    assert ("across" in skill_doc.lower()) and ("within" in skill_doc.lower())

    # --- the opt-in /resume discipline: advisory/opt-in, never auto-route / never block. ---
    assert "/resume" in skill_doc
    assert ("opt-in" in skill_doc) or ("advisory" in skill_doc)
    assert ("never" in skill_doc.lower()) and (
        ("block" in skill_doc.lower()) or ("auto-route" in skill_doc)
    )

    # --- durability statement: the volatile cache path AND the committed-artifacts notion. ---
    assert ".claude/saga/" in corpus
    assert "docs/" in corpus

    # --- boundary negatives: /loop does NOT implement / file issues / deploy. ---
    assert "does **NOT**" in skill_doc
    assert "implement" in skill_doc
    assert "file SDLC issues" in skill_doc
    assert "deploy" in skill_doc

    # --- blunt thin-port tripwire: each of the 2 reference files carries real content. ---
    for ref in ("dispatch-table.md", "drive-and-resume.md"):
        ref_path = loop / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60


def test_resume_engine_merge_contract() -> None:
    """Presence FLOORS for the rebuilt /resume heavy forensic engine (0.12.0).

    HONEST SCOPE: these are presence floors over the authored SKILL + 2 refs. Each floor
    proves the SKILL/refs EMIT a runnable line or boundary sentence the engine stands on —
    NOT that the logic is correct and NOT that the dig is actually context-safe at runtime.
    Token-presence != runtime context-safety. The real mitigation for the Tier-2 dig is the
    generic-agent-reads-paths pattern (the orchestrator never holds bulk session content) +
    the parent E6 grounding pass; this test only checks the contract was authored, not
    reskinned away. Tokens are taken from the actual E1-authored files on disk.
    """
    resume = PLUGIN_ROOT / "skills" / "resume"
    skill_doc = _read(resume / "SKILL.md")
    forensic_doc = _read(resume / "references" / "forensic-reconstruction.md")
    sessions_doc = _read(resume / "references" / "session-forensics.md")
    corpus = "\n".join((skill_doc, forensic_doc, sessions_doc))

    # --- Tier-1 saga reconstruction CLI lines: scan + restore + the NEW all-ticks read. ---
    assert "saga.py scan" in corpus
    assert "saga.py restore --saga-id" in corpus
    # The all-ticks reader is the differentiator /loop's latest-tick-only restore cannot see.
    assert "saga.py ticks --saga-id" in corpus

    # --- the shared issue-backed archaeology substrate: both context loaders, with --repo/--issue. ---
    context_lines = [
        line
        for line in corpus.splitlines()
        if ("load_saga_context.py" in line or "saga.py context" in line)
    ]
    assert any("load_saga_context.py" in line for line in context_lines)
    assert any("saga.py context" in line for line in context_lines)
    assert any("--repo" in line and "--issue" in line for line in context_lines)

    # --- the one re-entry tick: a runnable `saga.py save` carrying --status paused + --next-step. ---
    save_blocks = re.findall(r"saga\.py save.*?(?=\n#|\n```|\Z)", skill_doc, flags=re.DOTALL)
    assert any("--status paused" in block and "--next-step" in block for block in save_blocks), (
        "SKILL must emit a runnable re-entry `saga.py save` with --status paused AND --next-step"
    )

    # --- the reuse-saga_id rule: the re-entry tick REUSES the restored id, never a paraphrase.
    # save() mints a new dir unconditionally for a new id, so a paraphrase forks a phantom thread. ---
    assert "REUSE" in skill_doc
    assert "saga_id" in skill_doc
    # The rule sits near the re-entry tick (Phase 5) — assert the reuse prose mentions the restored id.
    assert re.search(r"REUSE the\s+restored `saga_id`", skill_doc) or (
        "REUSE the restored `saga_id`" in skill_doc
    )

    # --- Tier-2 context-safety set (the fallback dig over local JSONL). ---
    assert "discover_sessions.py" in corpus
    # extraction is file-mediated to scratch via --output (never read into the orchestrator).
    assert re.search(r"extract_session_skeleton\.py[^\n]*--output", corpus)
    # throwaway machine-local scratch dir.
    assert "mktemp -d" in corpus
    # GENERIC agent dispatch (Explore / Task) — this plugin has NO agents/ dir.
    assert "Explore" in skill_doc and "Task" in skill_doc
    assert "GENERIC" in skill_doc or "generic" in skill_doc
    # cap of 5 sessions + exclude the current session.
    assert "5" in skill_doc  # the cap appears ("Cap 5" / "capped at 5")
    assert ("Cap 5" in skill_doc) or ("capped at 5" in skill_doc)
    assert "current session" in skill_doc

    # --- named-agent guardrail (DA convention): NO custom subagent, mirror /code-review line 164.
    # ce-session-historian must be ABSENT entirely. resume-session-historian + ce-* appear ONLY
    # inside the negation prose ("do **not** reference a named `ce-*` / `resume-session-historian`"),
    # so a flat token-absence assertion would fail a FAITHFUL SKILL (the founder-review no-saga-write
    # pattern). Pin the mechanism: the negation is present AND there is no POSITIVE dispatch-to-a-
    # named-agent instruction. ---
    assert "ce-session-historian" not in corpus
    assert "do **not** reference a named" in skill_doc
    # Every occurrence of the named agent is part of the "(do NOT) reference a named <agent>"
    # negation — never a POSITIVE "Dispatch <named-agent>" / "use the <named-agent>" / "spawn
    # <named-agent>" instruction. The negation "NOT" can wrap to the previous line ("do **NOT**\n
    # reference a named ..."), so normalize whitespace and check a small window before each match
    # rather than line-by-line.
    flat = re.sub(r"\s+", " ", corpus)
    for match in re.finditer(r"resume-session-historian", flat):
        window = flat[max(0, match.start() - 60) : match.start()]
        assert re.search(r"\bnot\b", window, flags=re.IGNORECASE), (
            f"named agent must only appear inside a negation, found positive use near: "
            f"{flat[match.start() - 60 : match.start() + 40]!r}"
        )
    # No positive dispatch verb immediately targets the named agent.
    assert not re.search(
        r"(?:Dispatch|spawn|use the|invoke)\s+(?:a\s+)?[`']?resume-session-historian",
        flat,
        flags=re.IGNORECASE,
    )
    # And the dispatch step names a GENERIC agent, not a custom one.
    assert "Dispatch a GENERIC synthesis agent" in skill_doc

    # --- NEGATIVE context-safety assertion (DA-M1): the orchestrator-never-reads-bulk guardrail
    # is PRESENT, and there is NO orchestrator step that Reads/cats a $SCRATCH skeleton file
    # (only the generic agent reads skeletons, via paths). ---
    assert "orchestrator NEVER Reads or cats" in skill_doc  # the guardrail sentence is present
    assert not re.search(r"(?:Read|cat)\s+\"?\$SCRATCH", corpus), (
        "the orchestrator must NEVER Read/cat a $SCRATCH skeleton file (only the generic agent does)"
    )

    # --- dispatch table is REFERENCED but NOT restated (one source of truth, no /loop<->/resume
    # duplication). The path is cited; the table's own unique title/header (which lives ONLY in
    # loop/references/dispatch-table.md) must NOT appear in the resume corpus. ---
    assert "dispatch-table.md" in corpus
    # "# Dispatch Table" (the H1 title) and the table's lead sentence live only in the loop ref.
    assert "# Dispatch Table" not in corpus
    assert "The designed routing map for `/loop`" not in corpus

    # --- boundary negatives: read-only on the world; no build/test/PR, no file-issues, no deploy,
    # and NO ping-pong back to /loop. ---
    assert "does **NOT**" in skill_doc
    assert "open / merge a PR" in skill_doc or "merge a PR" in skill_doc
    assert "file SDLC issues" in skill_doc
    assert "deploy" in skill_doc.lower()
    assert "read-only on the world" in skill_doc.lower()
    # never route back to /loop (the no-ping-pong rule).
    assert "ping-pong" in skill_doc
    assert ("never route back to" in skill_doc.lower()) and ("/loop" in skill_doc)

    # --- ref-floor: both reference files exist and carry real content (>= 60 lines). ---
    for ref in ("forensic-reconstruction.md", "session-forensics.md"):
        ref_path = resume / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60


def test_qa_engine_merge_contract() -> None:
    """Mechanism FLOORS for the rebuilt engine-merge /qa acceptance-evidence gate (0.13.0).

    HONEST SCOPE: presence proves the contract was AUTHORED, not that runtime is mutation-free.
    "Never fix / never commit / never deploy" is enforced only by Claude reading the prose at
    runtime — the SKILL emits no runnable mutation command, but token presence cannot prove a
    given run respects the boundary. These floors prove the SKILL/refs EMIT the runnable lines
    the gate stands on (saga restore/advance, issue-progress with evidence, the diff mechanic),
    that the gate-only boundary prose is present (and mutation verbs appear ONLY inside negation
    windows, like /resume and /founder-review), that failures route by merge state, that the
    ce-debug falsifiable-prediction graft is grafted, and that the 0-100 health score is the
    deterministic gstack-formula PORT (via the runnable `qa_health_score.py` CLI) reported alongside
    the banded verdict — a real score, not faked. A thin port of the prior 19-line stub (a 9-way
    router + "store notes", no severity model / verdict / saga wiring / routing) fails these floors.

    Tokens are taken from the actual E1-authored SKILL.md + its 2 references on disk.
    """
    qa = PLUGIN_ROOT / "skills" / "qa"
    skill_doc = _read(qa / "SKILL.md")
    risk_doc = _read(qa / "references" / "risk-taxonomy.md")
    report_doc = _read(qa / "references" / "qa-report.md")
    corpus = "\n".join((skill_doc, risk_doc, report_doc))

    # --- MECHANISM FLOOR 1: the saga restore CLI (qa is a pure consumer — restore, never mint). ---
    assert "saga.py restore --saga-id" in corpus, (
        "the gate must restore the work-thread saga (`saga.py restore --saga-id`)"
    )

    # --- MECHANISM FLOOR 2: the qa-track ADVANCE write — a runnable `saga.py save` carrying the
    # qa lifecycle phase AND --qa-paths. A bare "ticks the saga" mention cannot satisfy this; the
    # block must carry both flags (the deferred work->qa advance /work left to this rebuild). ---
    save_blocks = re.findall(r"saga\.py save.*?(?=\n#|\n```\s|\Z)", corpus, flags=re.DOTALL)
    assert any(
        "--lifecycle-phase qa" in block and "--qa-paths" in block for block in save_blocks
    ), (
        "the PASS tick must be a runnable `saga.py save` carrying --lifecycle-phase qa AND --qa-paths"
    )
    # The advance pins --phase to the restored integer (so --phase-status complete cannot advertise
    # a phantom counter advance) and sets --phase-status complete.
    assert any(
        "--phase " in block and "--phase-status complete" in block for block in save_blocks
    ), "the qa advance must pin --phase to the restored value and mark --phase-status complete"
    # The never-mint guard must be pinned at the dangerous save call-site (not only in Phase 0.2),
    # mirroring the shipped /code-review which states `saga.py save mints unconditionally` right at
    # its save block: `saga.py save` mints an unknown id unconditionally, so the SKILL must reinforce
    # the scan-first / never-mint guard near the qa-advance save block, not just upstream in restore.
    assert "mints unconditionally" in skill_doc, (
        "the SKILL must pin the never-mint guard at the save call-site "
        "(`saga.py save` mints unconditionally — only tick when a saga was restored)"
    )
    save_idx = skill_doc.find("saga.py save")
    mints_idx = skill_doc.find("mints unconditionally")
    assert save_idx != -1 and mints_idx != -1 and abs(mints_idx - save_idx) <= 600, (
        "the `mints unconditionally` never-mint caveat must sit next to the `saga.py save` block "
        "(the /code-review call-site-guard pattern), not in a distant section"
    )

    # --- MECHANISM FLOOR 3: the issue-progress evidence emission with BOTH evidence flags. ---
    progress_blocks = re.findall(
        r"issue_progress\.py.*?(?=\n#|\n```\s|\Z)", corpus, flags=re.DOTALL
    )
    assert any(
        "--checks-run" in block and "--evidence-link" in block for block in progress_blocks
    ), "the gate must emit `issue_progress.py` with --checks-run AND --evidence-link"

    # --- MECHANISM FLOOR 4: the diff-aware mechanic — merge-base + diff (reused from /code-review,
    # fetch-first, two-dot to avoid the empty post-merge three-dot diff). ---
    assert "git merge-base" in corpus, "the diff-aware scope must use `git merge-base`"
    assert re.search(r"git diff[^\n]*DIFF_BASE", corpus), (
        "the diff-aware scope must run `git diff` against the computed merge-base"
    )

    # --- MECHANISM FLOOR 5: the ce-debug falsifiable-PREDICTION graft (the distinct ce-debug
    # import — the rest of evidence discipline already lives in /code-review principle 2). ---
    assert "falsifiable prediction" in corpus.lower(), (
        "the ce-debug falsifiable-prediction mechanic must be grafted"
    )
    assert "if this is the real cause" in corpus, (
        "the prediction must be the concrete ce-debug shape ('if this is the real cause, X ...')"
    )

    # --- MECHANISM FLOOR 6: the 9-way risk router + browser-as-ONE-MCP-class fold. ---
    nine_classes = (
        "behavior",
        "security",
        "infra",
        "API",
        "deployment",
        "data",
        "docs",
        "config",
        "trivial",
    )
    for klass in nine_classes:
        assert klass in risk_doc, f"risk class {klass!r} must be in the 9-way router"
    # The gstack 7-web-categories fold: browser is ONE MCP-driven class under behavior, not a
    # separate 7-category surface, and uses the installed MCP (no gstack $B/browse daemon).
    assert "one MCP" in risk_doc or "ONE MCP" in risk_doc, (
        "browser must fold into a single MCP-driven class (the gstack 7-category fold)"
    )
    assert "chrome-devtools" in risk_doc and "playwright" in risk_doc, (
        "the browser class is driven by the installed chrome-devtools / playwright MCP"
    )

    # --- MECHANISM FLOOR 7: the SEVERITY-BANDED verdict (ship / ship-with-deferred / no-ship +
    # critical/high/medium/low) AND the deterministic gstack-PORTED health score (re-added in
    # 0.13.x: Jeff re-opened Q2 to port gstack's REAL formula, not invent one). ---
    for verdict in ("ship-with-deferred", "no-ship"):
        assert verdict in corpus, f"the ship verdict {verdict!r} must be named"
    assert re.search(r"\bship\b", corpus), "the ship verdict 'ship' must be named"
    for severity in ("critical", "high", "medium", "low"):
        assert severity in corpus, f"severity band {severity!r} must be named"
    # The P0-P3 cross-walk to /code-review is documented.
    for prio in ("P0", "P1", "P2", "P3"):
        assert prio in risk_doc, f"the severity <-> {prio} cross-walk must be documented"
    # The deterministic scorer is wired: the SKILL emits a runnable `qa_health_score.py` CLI line
    # carrying --findings-json, and the report ref documents the model. A bare "compute the score"
    # mention cannot satisfy this — the runnable line must be present.
    assert "qa_health_score.py" in skill_doc, (
        "the SKILL must emit the runnable deterministic scorer `qa_health_score.py`"
    )
    assert "qa_health_score.py" in report_doc, (
        "the report ref must carry the runnable `qa_health_score.py` line + the score model"
    )
    score_blocks = re.findall(r"qa_health_score\.py.*?(?=\n#|\n```\s|\Z)", corpus, flags=re.DOTALL)
    assert any("--findings-json" in block for block in score_blocks), (
        "the scorer invocation must pass --findings-json (the per-class severity counts)"
    )
    # Baseline-from-prior-report: the score is regression-aware via --baseline-score (read from the
    # prior report the saga's qa_paths points at — no baseline.json, no saga field).
    assert "--baseline-score" in corpus, (
        "the scorer must support baseline-from-prior-report via --baseline-score"
    )
    assert "baseline" in skill_doc.lower() and "qa_paths" in skill_doc, (
        "the SKILL must read the prior overall from the saga's qa_paths as the baseline"
    )
    # The score is reported alongside the verdict, with the honest LLM-assigned-inputs caveat (the
    # score is a signal, the verdict is the gate decision).
    assert "Health Score Rubric" in corpus or "Health Score" in corpus, (
        "the health score must be named (the gstack-ported model)"
    )
    flat = re.sub(r"\s+", " ", corpus)
    assert re.search(r"signal[^.]*?verdict|verdict[^.]*?(?:decision|gate)", flat, re.IGNORECASE), (
        "the score is one signal; the verdict is the gate decision — both must be reported"
    )

    # --- MECHANISM FLOOR 8: gate-only negatives via POSITIVE-BOUNDARY-PROSE + NEGATION-WINDOW.
    # The positive boundary prose (E1 bolds the NOT). ---
    for negative in (
        "does **NOT** fix",
        "does **NOT** commit",
        "does **NOT** push",
        "does **NOT** deploy",
    ):
        assert negative in skill_doc, f"gate-only boundary prose {negative!r} must be present"
    assert "merge a PR" in skill_doc and "does **NOT**" in skill_doc

    # Negation-window: a FAITHFUL gate-only SKILL mentions mutation VERBS only inside "does NOT"
    # clauses (the /resume + /founder-review pattern), so a flat token-absence assert would fail it.
    # "push" is the unambiguous mutation verb here — it never appears as a benign noun in this
    # corpus — so every "push" occurrence must sit inside a negation window. ("commit" is excluded
    # from this window check because it doubles as the benign noun "merge commit"; the commit
    # boundary is pinned by the positive prose above + the no-runnable-`git commit` assert below,
    # exactly the founder-review pattern for a token that doubles as an innocent word.) ---
    flat_skill = re.sub(r"\s+", " ", skill_doc)
    for match in re.finditer(r"\bpushe?[sd]?\b", flat_skill, flags=re.IGNORECASE):
        window = flat_skill[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no)\b", window, flags=re.IGNORECASE), (
            f"mutation verb 'push' must only appear inside a negation window, "
            f"found positive use near: {flat_skill[match.start() - 50 : match.start() + 30]!r}"
        )

    # No runnable mutation command anywhere. `git add` appears ONLY inside "Never `git add`"
    # negations, so pin the mechanism: no positive git-mutation / gh-PR-mutation invocation.
    assert not re.search(r"(?<!Never )(?<!never )`?git commit", skill_doc)
    assert "git push" not in skill_doc
    assert "gh pr merge" not in skill_doc and "gh pr create" not in skill_doc
    # Every `git add` occurrence is a "Never git add" negation (saga state is git-ignored).
    for match in re.finditer(r"git add", flat):
        window = flat[max(0, match.start() - 30) : match.start()]
        assert re.search(r"\bNever\b", window), (
            "any `git add` mention must be inside a 'Never git add' negation"
        )

    # --- MECHANISM FLOOR 9: MERGE-STATE FAILURE ROUTING. Pre-merge -> /work; post-merge SPLITS into
    # a two-target branch: a clear/trackable defect -> /handoff, and a DEEP / uncertain root cause ->
    # /investigate (NOW LIVE — /investigate shipped this rebuild, so /qa's FLOOR-9 FLIPPED from the
    # 0.13.0 "future prose only" form to a live post-merge root-cause route). The earlier
    # negative-route-arrow + future-prose-window loop are GONE; /investigate is now asserted PRESENT
    # as a routable post-merge destination. ---
    assert "Pre-merge" in skill_doc and "/work" in skill_doc, "pre-merge failure routes to /work"
    assert "Post-merge" in skill_doc and "/handoff" in skill_doc, (
        "post-merge clear/trackable defect failure routes to /handoff"
    )
    # /investigate is now a LIVE post-merge root-cause route. Assert (a) it appears as a route-arrow /
    # routing target for a deep/uncertain root-cause failure, and (b) the SKILL frames it as a real
    # routable target that ships and is on the dispatch-table's routable list.
    flat_skill_inv = re.sub(r"\s+", " ", skill_doc)
    assert re.search(
        r"(?:->|→|\broute[sd]?\b[^\n]*\bto\b|root cause[^\n]*?)[^\n]*?/investigate", flat_skill_inv
    ), "/investigate must now appear as a LIVE post-merge root-cause route target"
    assert re.search(
        r"/investigate[^\n]*?(?:real routable target|routable|ships|systematic-debugging engine)",
        flat_skill_inv,
        re.IGNORECASE,
    ), "the SKILL must frame /investigate as a real, shipped, routable target"
    # The deep/uncertain root-cause failure is the discriminator that sends a post-merge thread to
    # /investigate rather than /handoff.
    assert re.search(
        r"Deep / uncertain root cause|deep[^\n]*root cause", skill_doc, re.IGNORECASE
    ), "the post-merge split must route DEEP / uncertain root-cause failures to /investigate"
    # But there is still NO /investigate -> /qa verify loop (/qa routes root-cause work TO
    # /investigate, never the reverse, and /investigate does its OWN verification).
    assert re.search(
        r"no\b[^\n]*/investigate[^\n]*?(?:->|→)[^\n]*/qa[^\n]*verify", flat_skill_inv, re.IGNORECASE
    ) or ("no `/investigate` → `/qa` verify" in skill_doc), (
        "there must be no /investigate -> /qa verify loop (/qa routes TO /investigate, never reverse)"
    )
    # PASS routes to /handoff or /retro (the clean-exit route).
    assert "/handoff" in skill_doc and "/retro" in skill_doc

    # --- MECHANISM FLOOR 10: dispatch-table is REFERENCED, never restated (one source of truth,
    # no /qa<->/loop duplication). The path is cited; the table's own unique H1 title + lead
    # sentence (which live ONLY in loop/references/dispatch-table.md) must NOT appear in the qa
    # corpus. ---
    assert "loop/references/dispatch-table.md" in skill_doc, (
        "outbound routing must REFERENCE the dispatch-table by path"
    )
    assert "# Dispatch Table" not in corpus, (
        "the dispatch-table H1 title must not be restated in /qa"
    )
    assert "The designed routing map for `/loop`" not in corpus

    # --- MECHANISM FLOOR 11: own durable artifact dir (docs/qa/), no classifier collision. ---
    assert "docs/qa/" in skill_doc and "docs/qa/" in report_doc

    # --- Operator-choice citation at the plugin-root path + the 3 backend enums (large/parallel
    # verification is OFFERED, never auto-spawned; generic agents only — no agents/ dir). ---
    assert "references/operator-choice.md" in skill_doc
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in skill_doc
    assert "Explore" in skill_doc and "Task" in skill_doc  # generic-agent dispatch

    # --- ref-floor: both reference files exist and carry real content (>= 60 lines). ---
    for ref in ("risk-taxonomy.md", "qa-report.md"):
        ref_path = qa / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60


def test_strategy_engine_merge_contract() -> None:
    """Mechanism FLOORS for the rebuilt engine-merge /strategy direction anchor (0.14.0).

    HONEST SCOPE: presence proves the contract was AUTHORED, not that runtime is mutation-free.
    /strategy's identity is that it RECORDS direction (the records member of the
    record-vs-challenge-vs-readiness trio) — so the engine-identity verbs "record"/"anchor" are
    NEVER negation-windowed; the whole positive point of the engine is that it records direction.
    The records-not-implements boundary is enforced only by Claude reading the prose at runtime —
    the SKILL emits no runnable mutation command, but token presence cannot prove a given run
    respects the boundary. These floors prove the SKILL/refs EMIT the prose the engine stands on
    (Phase-0 file-state routing, the locked-template constraints, the pushback discipline, the
    Infiquetra agent-as-customer / tracks-are-not-actors deltas, the downstream routing), that the
    boundary prose is present (with mutation verbs only inside negation windows, like /qa,
    /resume, and /founder-review), that the ce-* downstream names appear ONLY inside a faithful
    attribution window, and that the dispatch table is referenced not restated. A thin port that
    transcribes weak answers (no pushback, no anti-patterns, no locked constraints) fails these.

    Tokens are taken from the actual E1-authored SKILL.md + its 2 references on disk.
    """
    strategy = PLUGIN_ROOT / "skills" / "strategy"
    skill_doc = _read(strategy / "SKILL.md")
    interview_doc = _read(strategy / "references" / "interview.md")
    template_doc = _read(strategy / "references" / "strategy-template.md")
    corpus = "\n".join((skill_doc, interview_doc, template_doc))

    # --- MECHANISM FLOOR 1: Phase-0 file-state routing — the 3 distinct paths. The engine
    # branches on the root STRATEGY.md's existence (first-run / targeted-section / ask-which),
    # not a single linear interview. A stub has no routing. ---
    assert "Phase 0" in skill_doc, "the engine must route by file state in a Phase 0"
    assert re.search(r"(?:does not exist|not found|first run)", skill_doc, re.IGNORECASE), (
        "Phase 0 must route the file-absent path (first run)"
    )
    assert re.search(r"File exists.*?argument", skill_doc, re.DOTALL), (
        "Phase 0 must route the file-exists + named-section path (targeted update)"
    )
    assert re.search(r"File exists.*?no argument", skill_doc, re.DOTALL), (
        "Phase 0 must route the file-exists + no-argument path (ask which section to revisit)"
    )

    # --- MECHANISM FLOOR 2: the 8 section names live in the interview / template corpus (the
    # locked document structure), NOT in a generated STRATEGY.md (the engine writes that at
    # runtime; the contract is over the AUTHORED skill, not its output). ---
    sections = (
        "Target problem",
        "Our approach",
        "Who it's for",
        "Key metrics",
        "Tracks",
        "Milestones",
        "Not working on",
        "Marketing",
    )
    for section in sections:
        assert section in interview_doc or section in template_doc, (
            f"section {section!r} must be present in the interview/template corpus"
        )

    # --- MECHANISM FLOOR 3: the pushback discipline — the 2-round rule, >= 3 named anti-patterns,
    # and the core-of-the-skill / do-not-skip enforcement. A passive transcription has none of it. ---
    assert re.search(r"two rounds?|two-round", corpus, re.IGNORECASE), (
        "the interview must cap pushback at two rounds per section"
    )
    # >= 3 named anti-patterns (one per family the interview names: vanity / feature-list /
    # goal-as-problem). These are the canonical bad-strategy shapes Rumelt flags.
    for anti_pattern in ("vanity", "feature-list", "goal-as-problem"):
        assert anti_pattern in interview_doc, (
            f"the interview must name the {anti_pattern!r} anti-pattern"
        )
    # The two-round pushback is explicitly framed as the core of the skill that must not be skipped.
    assert "core of the skill" in interview_doc, (
        "the interview must frame the pushback as the core of the skill"
    )
    assert re.search(r"do not skip|don't skip|never .*skip", interview_doc, re.IGNORECASE), (
        "the interview must forbid skipping the pushback / a question"
    )

    # --- MECHANISM FLOOR 4: the locked-template constraints — 3-5 metrics AND 2-4 tracks. The
    # template is constrained on purpose (short is a feature); a vibes port drops the ceilings. ---
    assert "3-5 metrics" in corpus or re.search(r"3-5\b[^\n]*metric", corpus), (
        "the locked template must constrain metrics to 3-5"
    )
    assert "2-4 tracks" in corpus or re.search(r"2-4\b[^\n]*track", corpus), (
        "the locked template must constrain tracks to 2-4"
    )

    # --- MECHANISM FLOOR 5: the artifact is the ROOT STRATEGY.md, and `docs/STRATEGY.md` must
    # NOT appear as a write target (the file is a repo-root well-known peer of README.md, not a
    # docs/ artifact — getting the path wrong breaks every downstream grounding read). ---
    assert "root `STRATEGY.md`" in skill_doc or "repository root `STRATEGY.md`" in skill_doc, (
        "the durable artifact must be the repository-root STRATEGY.md"
    )
    assert "docs/STRATEGY.md" not in corpus, (
        "STRATEGY.md is a repo-root well-known file, never a docs/ artifact"
    )

    # --- MECHANISM FLOOR 6: the Infiquetra deltas — the agent-as-customer persona adaptation AND
    # tracks-are-investment-areas (no actor-naming). These are the two adaptations the port adds
    # on top of the ported ce-strategy rulebook; a faithful port carries both. ---
    assert "agent-as-customer" in corpus, (
        "the persona section must carry the agent-as-customer adaptation"
    )
    assert re.search(r"AI-agent consumer", corpus), (
        "the persona adaptation must allow an AI-agent consumer as the primary persona"
    )
    # Tracks are investment areas / domains of work, NOT the actor (agent) that does the work.
    assert re.search(r"investment area", corpus), (
        "tracks must be framed as investment areas / domains of work"
    )
    assert re.search(r"not\b[^.\n]*actor|NOT actors|not an actor", corpus, re.IGNORECASE), (
        "tracks must be explicitly distinguished from actors (no actor-naming in tracks)"
    )

    # --- MECHANISM FLOOR 7: positive Infiquetra downstream routing — /ideate, /brainstorm, /plan
    # pick STRATEGY.md up as grounding. This is the POSITIVE downstream edge (distinct from the
    # ce-* attribution window below). ---
    for route in ("/ideate", "/brainstorm", "/plan"):
        assert route in skill_doc, (
            f"the downstream handoff must name the Infiquetra route {route!r}"
        )

    # --- MECHANISM FLOOR 8: CE-NAMES attribution window. E1's faithful attribution names the CE
    # downstream commands inside a single attribution sentence (the canonical engine-merge graft),
    # so a flat `ce-ideate not in corpus` assertion would fail a FAITHFUL port (the /resume
    # named-agent + /founder-review no-saga-write pattern). Pin the mechanism: every ce-*
    # downstream-name occurrence sits inside an attribution/negation window (within ~80 chars of an
    # attribution keyword — "Ported"/"CE"/"map to"); the SINGLE hard-absence is that the
    # commands/ce-strategy.md file does NOT exist (mirror resume's ce-doc-review.md non-existence). ---
    flat = re.sub(r"\s+", " ", corpus)
    for name in ("ce-ideate", "ce-brainstorm", "ce-plan"):
        for match in re.finditer(re.escape(name), flat):
            window = flat[max(0, match.start() - 80) : match.start()]
            assert re.search(
                r"\b(Ported|ported|CE|map to|maps? to|Compound-Engineering)\b", window
            ), (
                f"CE downstream name {name!r} must only appear inside an attribution window, "
                f"found near: {flat[max(0, match.start() - 60) : match.start() + 40]!r}"
            )
    # ce-strategy is the porting-attribution name (not a downstream command); it too must only
    # appear inside a "ported from Compound-Engineering" attribution window.
    for match in re.finditer(r"ce-strategy", flat):
        window = flat[max(0, match.start() - 80) : match.start()]
        assert re.search(r"\b(Ported|ported|Compound-Engineering)\b", window), (
            f"ce-strategy must only appear inside a porting-attribution window, "
            f"found near: {flat[max(0, match.start() - 60) : match.start() + 40]!r}"
        )
    # The SINGLE hard-absence: no ce-strategy command shim was created in this plugin.
    assert not (PLUGIN_ROOT / "commands" / "ce-strategy.md").exists(), (
        "no ce-strategy.md command shim must exist (the port is /strategy, not a ce-* alias)"
    )

    # --- MECHANISM FLOOR 9: BOUNDARY NEGATIVES via POSITIVE-BOUNDARY-PROSE + NEGATION-WINDOW.
    # The positive boundary prose (E1 bolds the NOT): /strategy records, it does not implement,
    # file SDLC issues, prioritize, or compute metric values. ---
    for negative in (
        "does **NOT** implement",
        "does **NOT** prioritize",
        "does **NOT** compute metric values",
        "does **NOT** file SDLC issues",
    ):
        assert negative in skill_doc, f"boundary prose {negative!r} must be present"

    # Negation-window ONLY for the unambiguous mutation verb "deploy" — it appears exactly once
    # in this corpus (inside the gate negation) and never as a benign noun, so every occurrence
    # must sit inside a negation window. "push" is DELIBERATELY EXCLUDED from this window check
    # (the /qa pattern for a token that doubles as an innocent word — "commit" -> "merge commit"):
    # here "push"/"pushes" is the engine's CORE verb ("pushes back on weak answers", "push back",
    # "pushback", Rumelt's "push past bad strategy"), so the push boundary is pinned instead by the
    # positive prose above + the no-runnable-`git push` assert below. The engine IDENTITY verbs
    # "record" and "anchor" are NEVER windowed — the engine's whole positive identity is that it
    # records direction. ---
    flat_skill = re.sub(r"\s+", " ", skill_doc)
    for match in re.finditer(r"\bdeploys?\b|\bdeployed\b", flat_skill, flags=re.IGNORECASE):
        window = flat_skill[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no)\b", window, flags=re.IGNORECASE), (
            f"mutation verb 'deploy' must only appear inside a negation window, found positive use "
            f"near: {flat_skill[max(0, match.start() - 50) : match.start() + 30]!r}"
        )

    # No runnable mutation command anywhere: no git commit, no git push, no gh-PR merge/create.
    assert "git commit" not in skill_doc, "/strategy must emit no runnable `git commit`"
    assert "git push" not in skill_doc, "/strategy must emit no runnable `git push`"
    assert not re.search(r"gh pr\s+\w+", skill_doc), (
        "/strategy must emit no runnable `gh pr ...` command (no merge/create)"
    )

    # --- MECHANISM FLOOR 10: NO-SAGA-WRITE. /strategy runs upstream of the work thread and is
    # advisory — it never writes the saga. E1 mentions the saga tokens only inside explicit
    # negations ("never writes the saga ... no `saga.py` invocation, no `--review-paths`"), so a
    # flat `saga.py not in corpus` would fail a FAITHFUL engine (the /founder-review pattern). Pin
    # the mechanism: no `saga.py save` string AND no runnable `python saga.py` invocation. ---
    assert "saga.py save" not in corpus, "/strategy must never emit a `saga.py save` write"
    assert not re.search(r"python3?\s+\S*saga\.py", corpus), (
        "/strategy must emit no runnable `python saga.py` invocation (it never writes the saga)"
    )

    # --- MECHANISM FLOOR 11: dispatch-table is REFERENCED but NOT restated (one source of truth,
    # no /strategy<->/loop duplication). The path is cited; the table's own unique H1 title + lead
    # sentence (which live ONLY in loop/references/dispatch-table.md) must NOT appear here. ---
    assert "loop/references/dispatch-table.md" in skill_doc, (
        "cross-command routing must REFERENCE the dispatch-table by path"
    )
    assert "# Dispatch Table" not in corpus, (
        "the dispatch-table H1 title must not be restated in /strategy"
    )
    assert "The designed routing map for" not in corpus, (
        "the dispatch-table lead sentence must not be restated in /strategy"
    )

    # --- MECHANISM FLOOR 12: the interaction model — AskUserQuestion for routing, free-form for
    # substance, and the channel-inline fallback when redis-channel is active. ---
    assert "AskUserQuestion" in skill_doc, "routing decisions must use AskUserQuestion"
    assert re.search(r"routing", skill_doc), "AskUserQuestion is reserved for routing decisions"
    assert "free-form" in skill_doc, "substantive sections must use free-form responses"
    assert "redis-channel" in skill_doc and "inline" in skill_doc, (
        "the channel-inline fallback must be named for redis-channel sessions"
    )

    # --- ref-floor: both reference files exist and carry real content (>= 60 lines). A vibes
    # reskin would leave the refs as stubs. ---
    for ref in ("interview.md", "strategy-template.md"):
        ref_path = strategy / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60


def test_retro_engine_merge_contract() -> None:
    """Mechanism FLOORS for the rebuilt engine-merge /retro meta-improvement engine (0.15.0).

    HONEST SCOPE: presence proves the contract was AUTHORED, not that runtime is mutation-free.
    /retro's whole identity is to CURATE / PRUNE / PROPOSE / RECORD — so the engine-identity verbs
    "curate"/"prune"/"propose"/"record"/"anchor"/"edit"/"refine"/"improve" are NEVER
    negation-windowed; the engine's positive point is that it edits the journal and proposes edits.
    The load-bearing safety contract (AUTO-APPLY only for a pure-additive new-journal-entry append;
    everything else propose-diff-and-wait) is enforced only by Claude READING the prose at runtime —
    the SKILL emits no runnable destructive self-edit and no runnable saga/gh mutation, but token
    presence cannot prove a given run respects the gate. These floors prove the SKILL/refs EMIT the
    contract the engine stands on (the 6 net-new passes, the curation sweeps, the lean solo-framed
    metrics, the stale-base BLOCK guard, the tiered self-edit gate, saga READ-ONLY with the dropped
    ->retro advance, the reuse-not-reimplement substrate, gh read-only, the operator-choice offer,
    the docs/retros artifact + journal promotion, the dispatch reference-not-restate, and the
    CE/gstack attribution window), that the boundary prose is present (with unambiguous mutation
    VERBS only inside negation windows, like /qa, /resume, /founder-review, and /strategy), and that
    the single hard-absence (no ce-*/gstack-* command shim) holds. A thin reskin that drops the
    self-edit gate, the curation sweeps, or the net-new passes fails these floors.

    Tokens are taken from the actual E1-authored SKILL.md + its 3 references on disk.
    """
    retro = PLUGIN_ROOT / "skills" / "retro"
    skill_doc = _read(retro / "SKILL.md")
    passes_doc = _read(retro / "references" / "retro-passes.md")
    safety_doc = _read(retro / "references" / "self-edit-safety.md")
    report_doc = _read(retro / "references" / "retro-report.md")
    corpus = "\n".join((skill_doc, passes_doc, safety_doc, report_doc))
    flat = re.sub(r"\s+", " ", corpus)

    # --- MECHANISM FLOOR 1: the 6 net-new passes neither source had. Each is named in the corpus;
    # a thin port that only re-runs gstack's forensics has none of these. ---
    assert "interview" in corpus.lower(), "the structured-interview pass must be present"
    assert "transcript" in corpus.lower(), "the transcript-review fan-out pass must be present"
    assert "new-skill" in corpus, "the new-skill / plugin detection pass must be present"
    assert "refine-lifecycle" in corpus, (
        "the refine-lifecycle (self-refinement) pass must be present"
    )
    assert "refine-directives" in corpus, "the refine-directives pass must be present"
    assert re.search(r"memory[ -]pruning|prune .*memory", corpus, re.IGNORECASE), (
        "the memory-pruning pass must be present"
    )

    # --- MECHANISM FLOOR 2: the gstack-`learn` curation sweeps (staleness + contradiction), with
    # dedup framed as an INFIQUETRA addition to the sweep set (in gstack it was a Stats display op,
    # here it is a real Prune sweep). Plus the lean, solo-framed git metrics. ---
    assert "staleness" in corpus.lower(), "the staleness curation sweep must be named"
    assert "contradiction" in corpus.lower(), "the contradiction curation sweep must be named"
    assert "dedup" in corpus.lower(), "the dedup curation sweep must be named"
    assert "infiquetra addition" in corpus.lower(), (
        "dedup must be framed as the infiquetra addition to the gstack sweep set"
    )
    assert re.search(r"lean[^\n]*metric|lean[^\n]*forensic", corpus, re.IGNORECASE), (
        "the lean git-metrics pass must be named"
    )
    # solo-framed: the gstack team-performance framing (leaderboard / streaks / tweetable) is SHED.
    assert "solo-framed" in corpus, "the lean metrics must be solo-framed (team-perf framing shed)"
    assert re.search(r"\bshed\b", corpus), "the team-performance framing must be explicitly shed"

    # --- MECHANISM FLOOR 3: the stale-base / wrong-today BLOCK guard, scoped to the time-windowed
    # mode, keyed on validation discipline + compute-today-from-the-session-reminder (NOT `date`). ---
    assert "BLOCK" in corpus, "the stale-base guard must BLOCK (not silently fabricate)"
    assert "wrong-today" in corpus, "the guard must name the wrong-today failure mode"
    assert "time-windowed" in corpus.lower(), "the guard is scoped to the time-windowed mode"
    assert "validation discipline" in flat.lower(), (
        "validation discipline must be load-bearing for the guard"
    )
    # Today is computed from the session reminder's currentDate, NEVER from the `date` command.
    assert "currentDate" in corpus, "today must be computed from the session reminder's currentDate"
    assert re.search(r"NEVER from (?:the )?`?date`?|never from .*\bdate\b", corpus), (
        "the guard must forbid computing today from the `date` command (clock drift)"
    )
    # Thread-scoped retros skip the window guard (they compute no window).
    assert "thread-scoped" in corpus.lower(), "the thread-scoped mode (no window) must be named"

    # --- MECHANISM FLOOR 4 (HIGHEST-VALUE): THE TIERED SELF-EDIT GATE. AUTO-APPLY is named ONLY for
    # a pure-additive NEW-journal-entry append; everything else (delete/modify/move + auto-memory +
    # directives + lifecycle SKILLs) is PROPOSE-DIFF-AND-WAIT. This is the load-bearing safety
    # contract; a flat-absence assert cannot prove it. ---
    assert "AUTO-APPLY" in corpus, "the AUTO-APPLY tier must be named"
    assert "PROPOSE-DIFF-AND-WAIT" in corpus, "the PROPOSE-DIFF-AND-WAIT tier must be named"
    # The AUTO rule is scoped to a PURE ADDITIVE APPEND of a NEW journal entry ONLY.
    assert "AUTO-APPLY is ONLY a PURE ADDITIVE APPEND of a NEW journal entry" in corpus, (
        "AUTO-APPLY must be scoped to a pure-additive new-journal-entry append ONLY"
    )
    # ANY delete / modify / move of existing lines is propose-diff-and-wait.
    assert "ANY delete, modify, or move of existing lines is PROPOSE-DIFF-AND-WAIT" in corpus, (
        "any delete/modify/move of existing lines must be propose-diff-and-wait"
    )
    # The propose tier explicitly covers auto-memory, directives, and the lifecycle SKILLs
    # (including retro's OWN skill — never self-applied).
    assert "auto-memory" in corpus.lower(), "the .claude auto-memory must be a propose-tier target"
    assert re.search(r"directive", corpus, re.IGNORECASE), (
        "directive files must be a propose-tier target"
    )
    assert "skills/retro/SKILL.md" in corpus, (
        "retro's own SKILL must be a propose-only target (proposed, never self-applied)"
    )
    assert "never self-applies" in corpus.lower() or "never self-applied" in corpus.lower(), (
        "/retro may propose a diff to its own skill but never self-applies one"
    )
    # The QUEUED -> ARCHIVE move is propose (it DELETES from QUEUED even though ARCHIVE is an append).
    assert re.search(r"QUEUED\s*(?:->|→)\s*ARCHIVE", corpus), (
        "the QUEUED -> ARCHIVE move must be named (it deletes from QUEUED, so propose not auto)"
    )
    # The in-repo vs global/cross-project directive distinction + the cross-project warning.
    assert "IN-REPO" in corpus, "the in-repo directive bucket must be named"
    assert re.search(r"GLOBAL ?/ ?CROSS-PROJECT|cross-project", corpus, re.IGNORECASE), (
        "the global / cross-project directive bucket must be named"
    )
    assert "~/.claude" in corpus, "the global directive path (~/.claude) must be named"
    assert re.search(r"affects? (?:\*\*)?(?:ALL|EVERY) project", corpus), (
        "a global/cross-project edit must carry the affects-EVERY-project warning"
    )
    # never-auto-launch a destructive self-edit or a backend.
    assert re.search(r"[Nn]ever\*{0,2} auto-launch", corpus), (
        "/retro must never auto-launch a destructive self-edit or an execution backend"
    )
    # Mechanism-pinned NO runnable destructive self-edit: no runnable git commit/push, no rm of a
    # tracked file. (Mirrors test_qa's no-runnable-mutation pins ~:911-921.)
    assert "git commit" not in corpus, "/retro must emit no runnable `git commit` (self-edit)"
    assert "git push" not in corpus, "/retro must emit no runnable `git push`"
    assert not re.search(r"\brm\s+-|\brm\s+`", corpus), (
        "/retro must emit no runnable `rm` of a tracked file (no destructive self-edit)"
    )

    # --- MECHANISM FLOOR 5: saga is READ-ONLY — restore + ticks are evidence reads; the ->retro
    # advance is dropped dead wiring. `saga.py save` appears ONLY inside a negation window (E1 writes
    # "`saga.py save` is never called"), so a flat token-absence assert would FAIL the faithful
    # engine (the /strategy + /qa pattern). Pin the mechanism: no RUNNABLE save invocation, and every
    # `saga.py save` mention sits inside a never/no/dead-wiring negation window. ---
    assert "saga.py restore --saga-id" in corpus, "the saga restore (read-only) CLI must be emitted"
    assert "saga.py ticks" in corpus, "the saga ticks (read-only trajectory) CLI must be emitted"
    assert "dead wiring" in corpus.lower(), (
        "the dropped ->retro advance must be named as dead wiring"
    )
    assert not re.search(r"python3?\s+\S*saga\.py save", corpus), (
        "/retro must emit no runnable `python saga.py save` invocation (saga READ-ONLY)"
    )
    for match in re.finditer(r"saga\.py save", flat):
        window = flat[max(0, match.start() - 60) : match.end() + 40]
        assert re.search(r"\b(not|never|no)\b|dead wiring|read-only", window, re.IGNORECASE), (
            f"every `saga.py save` mention must sit inside a negation window (saga READ-ONLY), "
            f"found near: {flat[max(0, match.start() - 50) : match.end() + 30]!r}"
        )

    # --- MECHANISM FLOOR 6: reuse-not-reimplement — the /resume forensic substrate is referenced by
    # NAME (not duplicated), and zero new .py lands under skills/retro (only the test file changes). ---
    assert "discover_sessions.py" in corpus, "the windowed session-discovery script must be reused"
    assert "extract_session_skeleton.py" in corpus, "the skeleton-extraction script must be reused"
    assert not list((retro).glob("**/*.py")), (
        "no new .py may land under skills/retro — the engine reuses existing scripts by name"
    )

    # --- MECHANISM FLOOR 7: gh is READ-ONLY. The mutation commands appear ONLY inside "Never ..."
    # negations, so a flat absence assert would fail the faithful engine. Pin: no runnable
    # `gh issue create` / `gh pr merge`, and every mention sits inside a negation window. ---
    assert not re.search(r"(?<!ever )(?<!ever `)gh issue create", corpus), (
        "/retro must emit no runnable `gh issue create` (mission-control owns the SDLC)"
    )
    assert not re.search(r"(?<!ever )(?<!ever `)gh pr merge", corpus), (
        "/retro must emit no runnable `gh pr merge` (read-only on the world)"
    )
    for tok in (r"gh issue create", r"gh pr merge"):
        for match in re.finditer(tok, flat):
            window = flat[max(0, match.start() - 50) : match.start()]
            assert re.search(r"\b(not|never|no)\b", window, re.IGNORECASE), (
                f"every {tok!r} mention must sit inside a negation window (gh READ-ONLY)"
            )
    # The read-only gh evidence commands ARE emitted (the engine reads the PR/issue/check state).
    assert "gh pr view" in corpus and "gh issue view" in corpus and "gh pr checks" in corpus, (
        "the read-only gh evidence commands must be emitted"
    )

    # --- MECHANISM FLOOR 8: the operator-choice offer — a big multi-file refactor is OFFERED with a
    # backend, never auto-run (references operator-choice.md + the 3 backend enums). ---
    assert "operator-choice.md" in corpus, "the operator-choice contract must be cited by path"
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in corpus, f"the operator-choice backend {backend!r} must be named"
    # generic-agent fan-out for non-mechanical work; the agents/ dir now exists but must contain
    # ONLY the mechanical-executor (the cheap-tier Bash-only agent added by U14/R16).
    # General Explore/Task fan-out still uses generic agents, not named ce-* agents.
    assert "Explore" in corpus and "Task" in corpus, "the transcript fan-out uses generic agents"
    if (PLUGIN_ROOT / "agents").exists():
        agent_files = list((PLUGIN_ROOT / "agents").glob("*.md"))
        agent_names = {f.stem for f in agent_files}
        assert agent_names == {"mechanical-executor", "readonly-verifier"}, (
            f"plugins/saga/agents/ must contain ONLY the structural saga agents "
            f"mechanical-executor.md (U14/R16) and readonly-verifier.md (#287 U2 sandbox agent); "
            f"found: {sorted(agent_names)}. Named ce-* or judgment personas belong outside this dir."
        )

    # --- MECHANISM FLOOR 9: the durable artifact dir (docs/retros/) + journal promotion into the
    # four core files (the markdown journal is the durable sink). ---
    assert "docs/retros" in corpus, "the per-thread retro doc must live under docs/retros/"
    for journal_file in ("LEARNINGS", "DECISIONS", "QUEUED", "ARCHIVE"):
        assert journal_file in corpus, f"journal promotion must name {journal_file}.md"

    # --- MECHANISM FLOOR 10: dispatch-table is REFERENCED by path, never restated (one source of
    # truth, no /retro<->/loop duplication). The table's unique H1 + lead sentence (which live ONLY
    # in loop/references/dispatch-table.md) must NOT appear in the retro corpus. ---
    assert "loop/references/dispatch-table.md" in skill_doc, (
        "outbound routing must REFERENCE the dispatch-table by path"
    )
    assert "# Dispatch Table" not in corpus, "the dispatch-table H1 must not be restated in /retro"
    assert "The designed routing map for" not in corpus, (
        "the dispatch-table lead sentence must not be restated in /retro"
    )

    # --- MECHANISM FLOOR 11: CE/gstack ATTRIBUTION WINDOW. E1's faithful attribution names the
    # gstack `retro`/`learn` sources and CE `ce-compound` ONLY inside an attribution window, so a
    # flat `ce-compound not in corpus` assert would fail a FAITHFUL port (the /strategy ce-* +
    # /resume named-agent pattern). Key it on the REAL attribution keywords E1 uses (ported / comes
    # from / frame / sweep / forensic / CE / Compound-Engineering / first time / next time), within
    # ~80 chars. The SINGLE hard-absence: no commands/ce-*.md and no commands/gstack-*.md shim. ---
    attr_kw = re.compile(
        r"(Ported|ported|comes? from|come from|\bframe\b|Compound-Engineering|\bCE\b|"
        r"sweep|forensic|team-perf|parallel-research|first time|next time)",
        re.IGNORECASE,
    )
    for match in re.finditer(r"gstack[- ]`(?:retro|learn)`|ce-compound", flat):
        window = flat[max(0, match.start() - 80) : match.end() + 50]
        assert attr_kw.search(window), (
            f"gstack/CE source name must only appear inside an attribution window, "
            f"found near: {flat[max(0, match.start() - 60) : match.end() + 20]!r}"
        )
    # The CE compounding FRAME is keyed on the REAL ce-compound tokens (first time / next time /
    # knowledge compounds), NOT the paraphrase "leave the system smarter".
    assert "first time you solve" in corpus and "next time is a lookup" in corpus, (
        "the CE ce-compound frame must be ported with its real tokens (first time -> next time)"
    )
    assert "knowledge compounds" in corpus, "the compounding mechanism must be named"
    # The SINGLE hard-absence: no ce-* / gstack-* command shim was created.
    commands_dir = PLUGIN_ROOT / "commands"
    assert not list(commands_dir.glob("ce-*.md")), "no commands/ce-*.md shim must exist"
    assert not list(commands_dir.glob("gstack-*.md")), "no commands/gstack-*.md shim must exist"

    # --- MECHANISM FLOOR 12: BOUNDARY NEGATIVES via POSITIVE-BOUNDARY-PROSE + NEGATION-WINDOW.
    # The positive boundary prose (E1's Hard boundary names the NOTs). ---
    assert "does **NOT**" in skill_doc, "the Hard boundary must bold the does-NOT clauses"
    assert "read-only on the world" in skill_doc.lower() or "read-only" in skill_doc.lower(), (
        "the read-only-on-the-world boundary must be present"
    )
    # Negation-window ONLY for the unambiguous mutation VERBS that never double as a benign noun in
    # this corpus: the plural verb forms "deploys" / "merges" / "mutate(s)" (the Hard boundary's
    # "never opens / edits / merges ... never deploys ... mutate the world" prose). "commit" /
    # "deploy" (bare) / "push" are DELIBERATELY EXCLUDED — here "commit(s)" doubles as the benign
    # noun (git commits in scope / commit date), bare "deploy" appears as a benign TRIGGER ("end of
    # a ... PR / deploy"), and "push" is absent — exactly the /qa + /strategy carve-out for tokens
    # that double as innocent words. The engine IDENTITY verbs curate / prune / propose / record /
    # anchor / edit / refine / improve are NEVER windowed (the engine's positive identity). ---
    flat_skill = re.sub(r"\s+", " ", skill_doc)
    for verb in (r"\bdeploys\b", r"\bmerges\b", r"\bmutate[sd]?\b"):
        for match in re.finditer(verb, flat_skill, re.IGNORECASE):
            window = flat_skill[max(0, match.start() - 70) : match.start()]
            assert re.search(r"\b(not|never|without|no)\b", window, re.IGNORECASE), (
                f"mutation verb {verb!r} must only appear inside a negation window, found positive "
                f"use near: {flat_skill[max(0, match.start() - 50) : match.start() + 25]!r}"
            )
    # The engine-identity verbs ARE present as positive identity (windowing them would fail the
    # faithful engine) — assert their positive presence as the inverse tripwire.
    for identity_verb in ("curate", "prune", "propose", "record", "anchor", "refine", "improve"):
        assert identity_verb in corpus.lower(), (
            f"engine-identity verb {identity_verb!r} must be present as positive identity"
        )

    # --- MECHANISM FLOOR 13: the interaction model — AskUserQuestion for routing/choices, free-form
    # for substance, and the channel-inline fallback when redis-channel is active. ---
    assert "AskUserQuestion" in skill_doc, "routing / choices must use AskUserQuestion"
    assert "free-form" in skill_doc.lower(), "substantive interview questions must be free-form"
    assert "redis-channel" in skill_doc, (
        "the channel-inline fallback must be named for redis-channel"
    )
    assert re.search(r"inline the choices|channel-inline", corpus, re.IGNORECASE), (
        "in a channel session the choices must be inlined instead of AskUserQuestion"
    )

    # --- MECHANISM FLOOR 14: thin-port tripwire — each of the 3 reference files carries real
    # content (>= 60 lines). A vibes reskin would leave the refs as stubs. ---
    for ref in ("retro-passes.md", "self-edit-safety.md", "retro-report.md"):
        ref_path = retro / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60

    # --- /retro stays in the packaged-commands list (terminal lifecycle phase). ---
    assert (PLUGIN_ROOT / "commands" / "retro.md").exists(), "/retro must stay packaged"


def test_investigate_engine_merge_contract() -> None:
    """Mechanism FLOORS for the engine-merge /investigate systematic-debugging engine (0.16.0).

    HONEST SCOPE: presence proves the contract was AUTHORED, not that runtime is mutation-free.
    /investigate's whole identity is to INVESTIGATE / DIAGNOSE / TRACE / REPRODUCE / HYPOTHESIZE /
    PREDICT and (gated) FIX — so those engine-identity verbs are NEVER negation-windowed; the engine
    exists to do them. The load-bearing contracts (the Iron Law of no-fix-before-root-cause, the TWO
    distinct numeric gates, diagnosis-as-deliverable, saga READ-ONLY, the hard no-mutation boundary)
    are enforced only by Claude READING the prose at runtime — the SKILL emits no runnable mutation
    and no runnable `saga.py save`, but token presence cannot prove a given run respects the gate.
    These floors prove the SKILL/refs EMIT the contract the engine stands on (the ce-debug spine, the
    gstack grafts, the superpowers Iron Law + boundary instrumentation, the two numeric gates kept
    SEPARATE, the own-minimal-verification that does NOT route to /qa, real-fix->/work vs trivial
    inline, saga read-only with no runnable save, the hard-boundary no-mutation pins, the both-split
    learning capture that never feeds the report path to the classifier, operator-choice, the
    docs/investigations artifact, the dispatch reference-not-restate, and the ce-debug / gstack /
    superpowers attribution window), and that the single hard-absence (no ce-*/gstack-* shim) holds.
    A thin reskin that drops the causal-chain gate, collapses the two numeric gates, or routes to /qa
    to verify fails these floors.

    Tokens are taken from the actual E1-authored SKILL.md + its 3 references on disk.
    """
    investigate = PLUGIN_ROOT / "skills" / "investigate"
    skill_doc = _read(investigate / "SKILL.md")
    methodology_doc = _read(investigate / "references" / "methodology.md")
    taxonomy_doc = _read(investigate / "references" / "pattern-taxonomy.md")
    report_doc = _read(investigate / "references" / "debug-report.md")
    corpus = "\n".join((skill_doc, methodology_doc, taxonomy_doc, report_doc))
    flat = re.sub(r"\s+", " ", corpus)

    # --- MECHANISM FLOOR 1: the CE `ce-debug` SPINE — the causal-chain gate (no gaps),
    # predictions-for-uncertain-links, the assumption audit, one-change-at-a-time, smart-escalation,
    # and the trivial fast-path. A symptom-patching reskin has none of the gate discipline. ---
    assert re.search(r"no gaps|without gaps", corpus, re.IGNORECASE), (
        "the causal-chain gate must require the chain have no gaps (the ce-debug spine)"
    )
    assert "uncertain links" in corpus or "uncertain or non-obvious link" in corpus, (
        "predictions are formed for UNCERTAIN links only (the ce-debug prediction discipline)"
    )
    assert re.search(r"\bprediction\b", corpus, re.IGNORECASE), (
        "the prediction mechanic (a different-path observable) must be present"
    )
    assert "assumption audit" in corpus.lower(), (
        "the assumption audit (verified-vs-assumed) must be present (evidence before hypothesis)"
    )
    assert "one change at a time" in corpus.lower(), (
        "one-change-at-a-time (no shotgun debugging) must be present"
    )
    assert re.search(r"smart[- ]escalation", corpus, re.IGNORECASE), (
        "the smart-escalation table (when stuck, diagnose why) must be present"
    )
    assert re.search(
        r"trivial[- ]bug fast-path|trivial.* fast-path|fast-path", corpus, re.IGNORECASE
    ), "the trivial-bug fast-path must be present"

    # --- MECHANISM FLOOR 2: the gstack GRAFTS — the 6 pattern signatures + >= 1 serverless token,
    # and the enum'd DEBUG REPORT status (all three enum members). A thin port drops the taxonomy. ---
    for pattern_tok in ("race", "null", "state", "integration", "config", "cache"):
        assert pattern_tok in corpus.lower(), (
            f"gstack pattern signature {pattern_tok!r} must be in the pattern taxonomy"
        )
    assert re.search(r"cold-start|IAM|eventual-consistency|throttl|SSM", corpus, re.IGNORECASE), (
        "the infiquetra serverless row must add >= 1 serverless signature (cold-start/IAM/...)"
    )
    # The DEBUG REPORT status is an ENUM — all three members must be named (the gstack graft).
    for enum_member in ("DONE", "DONE_WITH_CONCERNS", "BLOCKED"):
        assert enum_member in corpus, (
            f"the DEBUG REPORT status enum must name {enum_member!r} (the gstack graft)"
        )

    # --- MECHANISM FLOOR 3: the superpowers BORROWS — the Iron Law (no fix before root cause) and
    # the boundary instrumentation that captures ACTUAL (observed, not assumed) values. ---
    assert re.search(r"Iron Law", corpus, re.IGNORECASE), (
        "the Iron Law (no fixes before root-cause investigation) must be named"
    )
    assert re.search(r"no fix", corpus, re.IGNORECASE), (
        "the Iron Law must be the no-fix-before-root-cause rule"
    )
    assert re.search(
        r"instrument the boundaries|boundary instrumentation", corpus, re.IGNORECASE
    ), "the superpowers boundary-instrumentation technique must be borrowed"
    assert re.search(r"\bactual\b[^\n]*value|capture the[^\n]*actual", corpus, re.IGNORECASE), (
        "boundary instrumentation must capture the ACTUAL (observed) values, not assumed ones"
    )

    # --- MECHANISM FLOOR 4 (HIGHEST-VALUE): THE TWO NUMERIC GATES, ASSERTED SEPARATELY. The engine
    # keeps two DISTINCT counters that must NOT collapse into one "3-strike" rule: the Phase-2
    # HYPOTHESIS-exhaustion gate (counts hypotheses) and the Phase-3 3-FAILED-FIX-attempts gate
    # (counts applied fixes). A thin port that conflates them fails one of these two asserts. ---
    # Gate A: hypothesis-exhaustion — exhausted hypotheses trigger STOP / escalate / architectural.
    hyp_gate = re.search(
        r"hypothes[ei]s[^\n]*exhaust|exhaust[^\n]*hypothes|2-3 hypotheses[^\n]*exhaust|"
        r"\d+ hypotheses fail",
        flat,
        re.IGNORECASE,
    )
    assert hyp_gate is not None, (
        "the HYPOTHESIS-exhaustion gate (Phase 2's numeric gate) must exist"
    )
    hyp_window = flat[hyp_gate.start() : min(len(flat), hyp_gate.end() + 200)]
    assert re.search(r"\bSTOP\b|escalat|architectur", hyp_window, re.IGNORECASE), (
        "the hypothesis-exhaustion gate must STOP / escalate / flag architectural"
    )
    # Gate B: 3 failed FIX attempts -> question the architecture (a DISTINCT counter from Gate A).
    fix_gate = re.search(
        r"3[^\n]*(?:applied )?fix(?:es|[- ]?attempts?)?[^\n]*fail|"
        r"3-failed-fix|3 applied fixes",
        flat,
        re.IGNORECASE,
    )
    assert fix_gate is not None, (
        "the 3-failed-fix-attempts gate (Phase 3's numeric gate) must exist, distinct from Gate A"
    )
    fix_window = flat[fix_gate.start() : min(len(flat), fix_gate.end() + 220)]
    assert re.search(
        r"architectur|root[- ]cause|root cause|question the", fix_window, re.IGNORECASE
    ), "after 3 failed fixes the engine must question the architecture / return to root cause"

    # --- MECHANISM FLOOR 5: DIAGNOSIS-PRIMARY + OWN-MINIMAL verification. The DEBUG REPORT is the
    # deliverable; the engine runs its OWN verification (regression test fails-without/passes-with,
    # full suite, fresh-reproduce) and does NOT route to /qa to verify. Real fixes route to /work;
    # only trivial/single-concern fixes apply inline. ---
    assert re.search(
        r"diagnosis is the primary deliverable|diagnosis[- ]primary|diagnosis as the deliverable",
        corpus,
        re.IGNORECASE,
    ), "the diagnosis (the DEBUG REPORT) must be the primary deliverable"
    assert re.search(r"failing regression test", corpus, re.IGNORECASE), (
        "own verification must write a failing regression test (fails-without)"
    )
    assert re.search(r"fails for the[^\n]*RIGHT reason|the test passes", corpus, re.IGNORECASE), (
        "the regression test must fail for the right reason then pass (passes-with)"
    )
    assert re.search(r"full[^\n]*suite", corpus, re.IGNORECASE), (
        "own verification must run the full suite for regressions"
    )
    assert "fresh-reproduce" in corpus or re.search(r"fresh-\*?\*?reproduce", corpus), (
        "own verification must fresh-reproduce the original bug to confirm the fix"
    )
    # MECHANISM: the engine does NOT route to /qa to verify — its verification is its OWN.
    assert re.search(
        r"does \*\*NOT\*\* route to[^\n]*/qa|not route to[^\n]*/qa|NOT[^\n]*route[^\n]*/qa to verify",
        corpus,
        re.IGNORECASE,
    ), "the engine must do its OWN verification, NOT route to /qa to verify"
    # Real fixes route to /work; only trivial/single-concern fixes apply inline.
    assert re.search(r"routes? to[^\n]*`?/work`?|route to[^\n]*`?/work`?", corpus, re.IGNORECASE), (
        "real implementation work must route to /work"
    )
    assert re.search(
        r"trivial\s*/\s*single-concern|trivial/single-concern", corpus, re.IGNORECASE
    ), "only a trivial / single-concern fix is applied inline (the inline-vs-route discriminator)"

    # --- MECHANISM FLOOR 6: saga is READ-ONLY — `restore` + `ticks` are evidence reads; there is NO
    # runnable `saga.py save` and NO --lifecycle-phase advance (the engine is off-chain). A flat
    # token-absence assert is avoided: the read-only CLIs ARE emitted (positive presence), and the
    # mechanism is that no runnable save / phase-advance exists. ---
    assert "saga.py restore --saga-id" in corpus, "the read-only saga restore CLI must be emitted"
    assert re.search(r"saga\.py ticks|\bticks\b", corpus), (
        "the read-only saga ticks (evidence trajectory) must be emitted"
    )
    assert not re.search(r"python3?\s+\S*saga\.py[^\n]*save", corpus), (
        "/investigate must emit no runnable `python saga.py ... save` (saga READ-ONLY, off-chain)"
    )
    assert "--lifecycle-phase" not in corpus, (
        "/investigate is off-chain — it must emit no --lifecycle-phase advance"
    )
    # Zero-new-.py: the engine reuses existing forensic scripts by name (no new script under the dir).
    assert not list(investigate.glob("**/*.py")), (
        "no new .py may land under skills/investigate — the engine reuses existing scripts by name"
    )
    assert re.search(r"discover_sessions\.py|extract_session_skeleton\.py", corpus), (
        "the prior-session forensic substrate must be reused by name (not reimplemented)"
    )

    # --- MECHANISM FLOOR 7: HARD-BOUNDARY negatives. POSITIVE boundary prose (E1 bolds the NOTs),
    # then a NEGATION-WINDOW for ONLY the unambiguous mutation verbs `push` and `deploy` (every
    # occurrence must sit inside a not/never/without/no window). `commit` and `merge` are
    # DELIBERATELY EXCLUDED from windowing (they hit "merge base" / "commit history" / "merged to
    # main" traps) — instead the commit/merge boundary is pinned by the no-runnable-mutation asserts
    # below. The engine-identity verbs investigate/diagnose/trace/reproduce/hypothesize/predict/fix
    # are NEVER windowed — the engine's positive identity is to do them. ---
    assert "does **NOT**" in skill_doc or "It does **NOT**" in skill_doc, (
        "the Hard boundary must bold the does-NOT clauses"
    )
    assert re.search(r"read-only", skill_doc, re.IGNORECASE), (
        "the read-only-on-the-world-and-saga boundary must be present"
    )
    flat_skill = re.sub(r"\s+", " ", skill_doc)
    for verb in (r"\bpushe?[sd]?\b", r"\bdeploys?\b|\bdeployed\b"):
        for match in re.finditer(verb, flat_skill, re.IGNORECASE):
            window = flat_skill[max(0, match.start() - 70) : match.start()]
            assert re.search(r"\b(not|never|without|no)\b", window, re.IGNORECASE), (
                f"mutation verb {verb!r} must only appear inside a negation window, found positive "
                f"use near: {flat_skill[max(0, match.start() - 50) : match.start() + 25]!r}"
            )
    # NO runnable mutation command anywhere (the commit/merge boundary, plus push/deploy/PR/issue).
    assert not re.search(r"(?<!Never )(?<!never )`?git commit", skill_doc), (
        "/investigate must emit no runnable `git commit`"
    )
    assert "git push" not in skill_doc, "/investigate must emit no runnable `git push`"
    assert not re.search(r"(?<!Never )(?<!never )`?gh pr create", skill_doc), (
        "/investigate must emit no runnable `gh pr create`"
    )
    assert not re.search(r"(?<!Never )(?<!never )`?gh pr merge", skill_doc), (
        "/investigate must emit no runnable `gh pr merge`"
    )
    assert not re.search(r"(?<!Never )(?<!never )`?gh issue create", skill_doc), (
        "/investigate must file no SDLC issue (`gh issue create`) — defects route via /handoff"
    )
    # The identity verbs ARE present as positive identity (windowing them would fail the engine).
    for identity_verb in (
        "investigate",
        "diagnose",
        "trace",
        "reproduce",
        "hypothes",
        "predict",
        "fix",
    ):
        assert identity_verb in corpus.lower(), (
            f"engine-identity verb {identity_verb!r} must be present as positive identity"
        )

    # --- MECHANISM FLOOR 8: LEARNING CAPTURE — BOTH-SPLIT. A non-obvious root cause promotes to the
    # journal LEARNINGS; a trackable defect routes to /handoff; the DEBUG REPORT lands under
    # docs/investigations/. The report is EVIDENCE — it is NEVER passed to handoff_envelope as a
    # source (the classifier does not recognize docs/investigations/). ---
    assert "LEARNINGS" in corpus, "a non-obvious root cause promotes to the journal LEARNINGS.md"
    assert "/handoff" in corpus, "a trackable defect routes to /handoff (descriptive DEFECT mode)"
    assert "docs/investigations/" in corpus, (
        "the DEBUG REPORT artifact must live under docs/investigations/"
    )
    # MECHANISM: no runnable handoff_envelope invocation that carries the docs/investigations report
    # path (the report is linked as evidence, never path-classified by handoff_envelope).
    assert not re.search(
        r"handoff_envelope\.py[^\n]*docs/investigations|docs/investigations[^\n]*handoff_envelope\.py",
        corpus,
    ), "the report path must NEVER be passed to a runnable handoff_envelope.py (it mis-classifies)"
    assert re.search(r"NEVER pass the report path to[^\n]*handoff_envelope", corpus), (
        "the both-split must forbid passing the report to handoff_envelope's classifier"
    )

    # --- MECHANISM FLOOR 9: operator-choice — the SKILL cites the plugin-root path from its own
    # depth, the refs cite the deeper path, the 3 backends + the >5-file blast-radius FLAG + the
    # parallel read-only dispatch (OFFERED, never auto-spawned) are present. ---
    assert "../../references/operator-choice.md" in skill_doc, (
        "the SKILL must cite operator-choice.md at its own depth (../../references/)"
    )
    assert "../../../references/operator-choice.md" in corpus, (
        "the refs must cite operator-choice.md at the deeper depth (../../../references/)"
    )
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in corpus, f"the operator-choice backend {backend!r} must be named"
    assert re.search(r">5 files|>5-file|blast-radius", corpus, re.IGNORECASE), (
        "the >5-file blast-radius FLAG must be present (a FLAG, not the inline-vs-route discriminator)"
    )
    assert re.search(r"parallel read-only", corpus, re.IGNORECASE), (
        "parallel read-only sub-agent dispatch must be OFFERED for evidence-bottlenecked subsystems"
    )
    # generic-agent fan-out for non-mechanical work; the agents/ dir now exists but must contain
    # ONLY the mechanical-executor (the cheap-tier Bash-only agent added by U14/R16).
    assert "Explore" in corpus and "Task" in corpus, (
        "parallel probes use generic Explore/Task agents"
    )
    if (PLUGIN_ROOT / "agents").exists():
        agent_files = list((PLUGIN_ROOT / "agents").glob("*.md"))
        agent_names = {f.stem for f in agent_files}
        assert agent_names == {"mechanical-executor", "readonly-verifier"}, (
            f"plugins/saga/agents/ must contain ONLY the structural saga agents "
            f"mechanical-executor.md (U14/R16) and readonly-verifier.md (#287 U2 sandbox agent); "
            f"found: {sorted(agent_names)}. Named ce-* or judgment personas belong outside this dir."
        )

    # --- MECHANISM FLOOR 10: docs/investigations/ artifact + dispatch REFERENCED not restated +
    # /brainstorm route (no /ce-brainstorm). The dispatch-table is one source of truth. ---
    assert "loop/references/dispatch-table.md" in corpus, (
        "outbound routing must REFERENCE the dispatch-table by path"
    )
    assert "# Dispatch Table" not in corpus, (
        "the dispatch-table H1 title must not be restated in /investigate"
    )
    assert "The designed routing map for" not in corpus, (
        "the dispatch-table lead sentence must not be restated in /investigate"
    )
    assert "/brainstorm" in corpus, "a design problem routes to /brainstorm"
    assert "/ce-brainstorm" not in corpus, (
        "the route is the Infiquetra /brainstorm, never a ce-* alias"
    )

    # --- MECHANISM FLOOR 11: ATTRIBUTION WINDOW. E1's faithful attribution names ce-debug, gstack
    # `investigate`, and superpowers `systematic-debugging` ONLY inside an attribution window, so a
    # flat absence assert would fail a FAITHFUL port (the /strategy ce-* + /retro CE/gstack pattern).
    # Key it on the REAL attribution keywords E1 uses (Ported / port / PORT / CE / gstack /
    # superpowers / borrow / BORROWED / GRAFT). The combined `superpowers systematic-debugging` form
    # is windowed (the bare `systematic-debugging` in the frontmatter is IDENTITY prose, not an
    # attribution claim, so it is not windowed). The SINGLE hard-absence: no ce-*/gstack-* shim. ---
    attr_kw = re.compile(
        r"(Ported|ported|\bport\b|\bPORT\b|\bCE\b|gstack|superpowers|borrow|BORROWED|GRAFT|GRAFTED)",
        re.IGNORECASE,
    )
    for name in ("ce-debug", r"gstack `investigate`", r"superpowers `?systematic-debugging`?"):
        matches = list(re.finditer(name, flat))
        assert matches, f"the attribution must name {name!r}"
        for match in matches:
            window = flat[max(0, match.start() - 90) : match.end() + 50]
            assert attr_kw.search(window), (
                f"source name {name!r} must only appear inside an attribution window, "
                f"found near: {flat[max(0, match.start() - 60) : match.end() + 20]!r}"
            )
    # The SINGLE hard-absence: no ce-* / gstack-* command shim was created.
    commands_dir = PLUGIN_ROOT / "commands"
    assert not list(commands_dir.glob("ce-*.md")), "no commands/ce-*.md shim must exist"
    assert not list(commands_dir.glob("gstack-*.md")), "no commands/gstack-*.md shim must exist"

    # --- MECHANISM FLOOR 12: thin-port tripwire — each of the 3 reference files carries real
    # content (>= 60 lines). A vibes reskin would leave the refs as stubs. ---
    for ref in ("methodology.md", "pattern-taxonomy.md", "debug-report.md"):
        ref_path = investigate / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60

    # --- /investigate is packaged as a command (the new routable diagnostic lens). ---
    assert (PLUGIN_ROOT / "commands" / "investigate.md").exists(), "/investigate must be packaged"


def test_spec_engine_merge_contract() -> None:
    """Mechanism FLOORS for the gstack `spec` WHAT-interrogation port /spec (0.17.0).

    HONEST SCOPE: presence proves the contract was AUTHORED, not that a given run is mutation-free.
    /spec's whole identity is to INTERROGATE / SPECIFY / SCOPE / SHARPEN / QUANTIFY / CLARIFY the
    WHAT — so those engine-identity verbs are NEVER negation-windowed; the engine's positive point
    is that it interrogates a vague ask into a sharp spec. The off-chain saga-UNTOUCHED contract is
    enforced only by Claude reading the prose at runtime — the SKILL emits no runnable mutation and
    no runnable `python saga.py`, but token presence cannot prove a given run respects the boundary.
    These floors prove the SKILL/refs EMIT the prose the engine stands on (the HARD GATE, the
    five-Why with anti-hand-waving bars, the scope-lock five, read-code-first with the non-code
    escape, quantify-everything, the principal-engineer persona), that the durable artifact is a
    docs/specs/ spec, that the boundary prose is present (mutation verbs only inside negation
    windows, like /strategy / /qa / /founder-review), that gstack is the SINGLE honestly-attributed
    source (NO fabricated ce-spec, NO /ideate or /brainstorm porting graft), and that the dispatch
    table is referenced not restated. A thin transcribe-the-scaffold port fails these.

    This is the OFF-CHAIN twin of test_strategy (saga UNTOUCHED), NOT test_investigate
    (saga READ-ONLY) — so there is no `saga.py restore` present-assert here.

    Tokens are taken from the actual E1-authored SKILL.md + its 2 references on disk.
    """
    spec = PLUGIN_ROOT / "skills" / "spec"
    skill_doc = _read(spec / "SKILL.md")
    interrogation_doc = _read(spec / "references" / "interrogation.md")
    template_doc = _read(spec / "references" / "spec-template.md")
    corpus = "\n".join((skill_doc, interrogation_doc, template_doc))
    flat = re.sub(r"\s+", " ", corpus)
    flat_skill = re.sub(r"\s+", " ", skill_doc)

    # --- MECHANISM FLOOR 1: the HARD GATE — no spec artifact after the first message. A thin port
    # that drafts on message 1 has no gate. E1 phrases it "Do NOT produce a spec artifact after
    # message 1"; pin the do-not-produce-after-the-first-message mechanism, not a bare token. ---
    assert re.search(r"[Dd]o NOT produce.{0,60}after message 1", flat_skill), (
        "the HARD GATE must forbid producing the spec artifact after the first message"
    )
    assert re.search(r"[Ii]nterrogate first", flat), (
        "the HARD GATE must require interrogating before drafting"
    )

    # --- MECHANISM FLOOR 2: the five-Why (Phase 1) — all five questions present. A vibes port
    # collapses these into one "tell me more". The WHAT/WHY lock is the spine. ---
    assert re.search(r"\*\*Who\*\* is affected|Who is affected", corpus), (
        "five-Why: who is affected"
    )
    assert "current behavior" in corpus, "five-Why: what is the current behavior"
    assert re.search(r"should the behavior be|target state", corpus), (
        "five-Why: what should the behavior be (target)"
    )
    assert "Why now" in corpus, "five-Why: why now (the forcing function)"
    assert re.search(r"How will we know|done-signal|it's done", corpus), (
        "five-Why: how will we know it's done"
    )
    # The anti-hand-waving bar — the interrogation refuses vague answers and pushes twice. A thin
    # transcription has no bar; it just records whatever weak answer it's handed.
    assert re.search(r"anti-hand-waving|hand-waving|hand-wav", interrogation_doc, re.IGNORECASE), (
        "the five-Why must carry an anti-hand-waving bar per question"
    )

    # --- MECHANISM FLOOR 3: the scope-lock five (Phase 2). Locking the boundary early is the
    # highest-leverage anti-creep move; a stub drops it. ---
    assert "out of scope" in corpus, "scope-lock: what is explicitly out of scope"
    assert re.search(r"existing systems does this touch|systems does this touch", corpus), (
        "scope-lock: what existing systems does this touch"
    )
    assert re.search(r"[Oo]rdering constraints", corpus), "scope-lock: ordering constraints"
    assert re.search(r"MVP|smallest version", corpus), "scope-lock: the MVP / smallest-version cut"
    assert re.search(r"[Ff]ailure mode", corpus) and re.search(r"[Rr]ollback", corpus), (
        "scope-lock: failure modes + rollback (the native gstack register)"
    )

    # --- MECHANISM FLOOR 4: read-code-first (Phase 3, HARD) — the magical-moment grounding rule.
    # Evidence before ANY Phase-3 question, cite `path:line`, the six categories, the non-code
    # escape. A port that asks "what file should I look at?" first fails this. ---
    assert re.search(
        r"before .{0,40}any .{0,40}question|before asking ANY", corpus, re.IGNORECASE
    ), "read-code-first must require reading evidence BEFORE any Phase-3 question"
    assert re.search(r"\bread\b", corpus, re.IGNORECASE), "read-code-first must require reading"
    assert re.search(r"path:line|cite", corpus), "read-code-first must require citing `path:line`"
    for category in (
        "data model",
        "API",
        "background",
        "UI",
        "infrastructure",
        "testing",
    ):
        assert category in corpus, f"read-code-first must name the {category!r} category"
    # The non-code / greenfield escape — without it the HARD gate would deadlock a greenfield ask.
    assert re.search(r"no code surface", corpus) and re.search(r"greenfield", corpus), (
        "read-code-first must carry the non-code / greenfield escape"
    )

    # --- MECHANISM FLOOR 5: quantify-everything. The "Several files" anti-example + metric/target.
    # A weak port accepts vague magnitudes; this engine demands exact counts and numeric targets. ---
    assert "exact count" in corpus or "Several files" in corpus, (
        "quantify-everything must reject vague magnitudes (exact count / 'Several files')"
    )
    assert "metric" in corpus and re.search(r"\btarget\b", corpus), (
        "quantify-everything must demand a metric and a target"
    )

    # --- MECHANISM FLOOR 6: the persona — a principal engineer for whom ambiguity is a bug. A thin
    # reskin has a neutral note-taker; this engine refuses ambiguity. ---
    assert "principal engineer" in corpus, "the persona must be a principal engineer"
    assert re.search(r"[Aa]mbiguity is a bug", corpus) or re.search(
        r"refuses to let an ambiguous", corpus
    ), "the persona must treat ambiguity as a bug / refuse ambiguous WHATs"

    # --- MECHANISM FLOOR 7: the durable artifact is a docs/specs/ spec with the locked template
    # sections + frontmatter `origin`. The artifact is the only durable output; getting its path or
    # shape wrong breaks the /handoff -> mission-control source mapping. ---
    assert "docs/specs/" in corpus, "the durable artifact must live under docs/specs/"
    for section in (
        "## Acceptance Criteria",
        "## Scope Boundaries",
        "## Failure Modes & Rollback",
    ):
        assert section in template_doc, f"the spec template must carry the {section!r} section"
    assert re.search(r"^origin:", template_doc, re.MULTILINE), (
        "the spec template frontmatter must carry an `origin` field"
    )

    # --- MECHANISM FLOOR 8: SAGA UNTOUCHED — /spec runs off-chain and never writes the work thread.
    # This MIRRORS test_strategy (the off-chain twin), NOT test_investigate (saga READ-ONLY): there
    # is NO `saga.py restore` present-assert. E1 names the saga tokens ONLY inside negations ("it is
    # saga-untouched: no `saga.py`", "does **NOT** write or advance the saga (no `saga.py`, no
    # `--lifecycle-phase`)"), so a flat `saga.py not in corpus` would fail a FAITHFUL off-chain
    # engine. Pin the mechanism: no `saga.py save` string AND no runnable `python saga.py`. The
    # `--lifecycle-phase` token (which the task brief asked to flat-absence) is, on the real E1
    # file, present ONLY inside the boundary negation `no `--lifecycle-phase``; a flat
    # absence-assert contradicts the shipped SKILL, so it is pinned by a negation-window instead
    # (#spec-adaptation-is-a-hypothesis — the brief's flat-absence was written from the label, the
    # file writes it in the off-chain negation exactly like /strategy writes `saga.py`). ---
    assert "saga.py save" not in corpus, "/spec must never emit a `saga.py save` write"
    assert not re.search(r"python3?\s+\S*saga\.py", corpus), (
        "/spec must emit no runnable `python saga.py` invocation (it never writes the saga)"
    )
    for match in re.finditer(r"--lifecycle-phase", flat):
        window = flat[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no)\b", window, flags=re.IGNORECASE), (
            "`--lifecycle-phase` must only appear inside a negation window (off-chain, no saga "
            f"write), found positive use near: {flat[max(0, match.start() - 50) : match.start() + 30]!r}"
        )
    # The bare `saga.py` token also appears only inside off-chain negations ("saga-untouched: no
    # `saga.py`"); window it the same way (the /strategy off-chain pattern).
    for match in re.finditer(r"\bsaga\.py\b", flat, flags=re.IGNORECASE):
        window = flat[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no|untouched)\b", window, flags=re.IGNORECASE), (
            "`saga.py` must only appear inside an off-chain negation window, found positive use "
            f"near: {flat[max(0, match.start() - 50) : match.start() + 30]!r}"
        )

    # --- MECHANISM FLOOR 9: ZERO new Python. /spec is a skills-only port (gstack spec is a SKILL;
    # there is no scorer to port). A stray .py under skills/spec means scope crept into code. ---
    assert not list((PLUGIN_ROOT / "skills" / "spec").glob("**/*.py")), (
        "/spec must add no new Python under skills/spec (it is a skills-only port)"
    )

    # --- MECHANISM FLOOR 10: BOUNDARY NEGATIVES via POSITIVE-BOUNDARY-PROSE + NEGATION-WINDOW.
    # The positive boundary prose (E1 bolds the NOT): /spec interrogates the WHAT and reads the repo
    # read-only; it does not file an SDLC issue, write the saga, offer operator-choice, or do
    # /plan's HOW job. ---
    assert "does **NOT**" in skill_doc, "boundary prose must bold what /spec does NOT do"
    assert "read-only" in skill_doc, "/spec must declare it reads the repo read-only"

    # Negation-window ONLY for the unambiguous mutation verb "deploy" (it appears once, inside the
    # gate negation "It never commits, pushes, ... or deploys"). "push" is DELIBERATELY EXCLUDED
    # from this window check — the persona "pushes back" / "pushback" is the engine's CORE verb (the
    # /strategy pattern), so the push boundary is pinned by the positive prose above + the
    # no-runnable-`git push` assert below. The identity verbs interrogate/spec/specify/scope/
    # sharpen/quantify/clarify are NEVER windowed — they are the engine's positive identity. ---
    for match in re.finditer(r"\bdeploys?\b|\bdeployed\b", flat_skill, flags=re.IGNORECASE):
        window = flat_skill[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no)\b", window, flags=re.IGNORECASE), (
            "mutation verb 'deploy' must only appear inside a negation window, found positive use "
            f"near: {flat_skill[max(0, match.start() - 50) : match.start() + 30]!r}"
        )

    # No runnable mutation command anywhere in the SKILL: no git commit, no git push, no gh-PR
    # create/merge. (Pinned as substring/regex absence on skill_doc, per the /strategy model.)
    assert "git commit" not in skill_doc, "/spec must emit no runnable `git commit`"
    assert "git push" not in skill_doc, "/spec must emit no runnable `git push`"
    assert not re.search(r"gh pr\s+\w+", skill_doc), (
        "/spec must emit no runnable `gh pr ...` command (no merge/create)"
    )
    # THE HIGHEST-VALUE BOUNDARY: /spec never files an issue — mission-control owns issue creation.
    assert "gh issue create" not in corpus, (
        "/spec must never file an SDLC issue (`gh issue create`); mission-control owns issue creation"
    )

    # --- MECHANISM FLOOR 11: routing — /handoff, /plan, /doc-review are the named onward routes,
    # and the dispatch table is REFERENCED by path, NOT restated (one source of truth, no
    # /spec<->/loop duplication). operator-choice is NOT asserted (decision (c) — /spec never offers
    # it). ---
    for route in ("/handoff", "/plan", "/doc-review"):
        assert route in skill_doc, f"the onward routing must name {route!r}"
    assert "loop/references/dispatch-table.md" in skill_doc, (
        "cross-command routing must REFERENCE the dispatch-table by path"
    )
    assert "# Dispatch Table" not in corpus, (
        "the dispatch-table H1 title must not be restated in /spec"
    )

    # --- MECHANISM FLOOR 12: HONEST ATTRIBUTION / ANTI-FABRICATION. gstack is the SINGLE source,
    # named near a port/source token. E1 wrote the explicit honesty line ruling out a CE engine.
    # The single hard-absence: no ce-spec command shim and no gstack-spec command shim exists (the
    # port is /spec, not a ce-* or gstack-* alias). Anti-graft: /ideate and /brainstorm are NOT
    # required as porting sources (the assumption-challenge + failure-mode register is NATIVE to
    # gstack's persona, not an /ideate+/brainstorm graft). ---
    assert re.search(r"gstack", corpus, re.IGNORECASE), "attribution must name gstack"
    assert re.search(r"(?:Ported|ported) from gstack|from gstack `spec`|gstack `spec`", corpus), (
        "gstack must be named near a port/source token (the single-source attribution)"
    )
    assert "No CE spec engine exists" in corpus, (
        "the honesty line must explicitly state no CE spec engine exists (anti-fabrication)"
    )
    assert not (PLUGIN_ROOT / "commands" / "ce-spec.md").exists(), (
        "no ce-spec.md command shim must exist (the port is /spec, not a ce-* alias)"
    )
    assert not (PLUGIN_ROOT / "commands" / "gstack-spec.md").exists(), (
        "no gstack-spec.md command shim must exist (the port is /spec, not a gstack-* alias)"
    )

    # --- MECHANISM FLOOR 13: AskUserQuestion routing + the channel-inline fallback. AskUserQuestion
    # is reserved for ROUTING; substance is free-form; in a redis-channel session the choices are
    # inlined (citing brainstorm/SKILL.md for the canonical convention, not duplicating it). ---
    assert "AskUserQuestion" in skill_doc, "routing decisions must use AskUserQuestion"
    assert re.search(r"routing", skill_doc), "AskUserQuestion is reserved for routing decisions"
    assert "free-form" in skill_doc, "substantive interrogation must use free-form responses"
    assert "redis-channel" in skill_doc and "inline" in skill_doc, (
        "the channel-inline fallback must be named for redis-channel sessions"
    )
    assert "brainstorm/SKILL.md" in skill_doc, (
        "the channel-inline convention must cite brainstorm/SKILL.md (not duplicate it)"
    )

    # --- ref-floor: both reference files exist and carry real content (>= 60 lines). A vibes
    # reskin would leave the refs as stubs. ---
    for ref in ("interrogation.md", "spec-template.md"):
        ref_path = spec / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60

    # --- /spec is packaged as a command (the new routable WHAT-interrogation lens). ---
    assert (PLUGIN_ROOT / "commands" / "spec.md").exists(), "/spec must be packaged"


def test_optimize_engine_merge_contract() -> None:
    """Mechanism FLOORS for the CE `ce-optimize` SINGLE-SOURCE PORT /optimize engine (0.18.0).

    HONEST SCOPE: presence proves the contract was AUTHORED, not that a given run is mutation-free.
    /optimize's whole identity is to OPTIMIZE / MEASURE / BASELINE / EXPERIMENT / TUNE / KEEP /
    REVERT toward a measurable target — so those engine-identity verbs are NEVER negation-windowed;
    the engine's positive point is that it runs the bounded experiment loop. The off-chain
    saga-UNTOUCHED contract is enforced only by Claude reading the prose at runtime — the SKILL emits
    no runnable mutation and no runnable `python saga.py`, but token presence cannot prove a given
    run respects the boundary. These floors prove the SKILL/refs EMIT the spine the engine stands on
    (the ce-optimize loop discipline, the 8 metric classes with the infiquetra-native agent-usability
    class, the hard-vs-judge three-tier model, the flat-file loop home + the durable split, the
    operator-choice OFFER for independent experiment fan-out recorded narratively — the floor that
    distinguishes /optimize from /strategy — and the never-auto-spawn/never-auto-commit boundary),
    that the boundary prose is present (mutation verbs only inside negation windows, like /strategy /
    /spec / /qa), that ce-optimize is the SINGLE honestly-attributed source (NOT a merge; gstack
    plan-tune contributed nothing; agent-usability is infiquetra-native, Jeff's angle), and that the
    dispatch table is referenced not restated.

    This is the OFF-CHAIN twin of test_strategy / test_spec (saga UNTOUCHED — no `saga.py restore`
    present-assert, unlike test_investigate which is saga READ-ONLY) — but UNLIKE /strategy and /spec
    it OFFERS operator-choice for independent-experiment fan-out, which is the distinguishing floor.

    Tokens are taken from the actual E1-authored SKILL.md + its 2 references on disk.
    """
    optimize = PLUGIN_ROOT / "skills" / "optimize"
    skill_doc = _read(optimize / "SKILL.md")
    taxonomy_doc = _read(optimize / "references" / "metric-taxonomy.md")
    loop_doc = _read(optimize / "references" / "experiment-loop.md")
    corpus = "\n".join((skill_doc, taxonomy_doc, loop_doc))
    flat = re.sub(r"\s+", " ", corpus)
    flat_skill = re.sub(r"\s+", " ", skill_doc)

    # --- MECHANISM FLOOR 1: the ce-optimize SPINE — the autoresearch loop discipline. The log is the
    # single source of truth; write-IMMEDIATELY then verify-by-reread; hard degenerate gates run
    # BEFORE the expensive judge; baseline first; one variable at a time; the strategy digest; the
    # hypothesis backlog; the stopping-rules cluster. A symptom-tuning reskin has none of this. ---
    assert "single source of truth" in corpus, (
        "the log-on-disk must be named the single source of truth (autoresearch discipline)"
    )
    assert re.search(r"immediately", corpus, re.IGNORECASE), (
        "the write-IMMEDIATELY-after-each-experiment rule must be present"
    )
    assert re.search(r"re-read|read .* back|verify", corpus, re.IGNORECASE), (
        "the verify-by-reread rule must be present (a results table not written to disk is a bug)"
    )
    assert re.search(r"gate.*before.*judg|before .* expensive", corpus, re.IGNORECASE), (
        "the cheap-hard-gates-BEFORE-expensive-judgment cost discipline must be present"
    )
    assert "baseline" in corpus, "baseline-first discipline must be present"
    assert "hypothesis backlog" in corpus, "the hypothesis backlog must be named"
    assert re.search(r"one variable|one-variable", corpus), "one-variable-at-a-time must be present"
    assert "strategy digest" in corpus, "the cross-batch strategy digest must be named"
    assert re.search(r"max_iterations|plateau|stopping", corpus), (
        "the stopping-rules cluster (max_iterations / plateau / stopping) must be present"
    )

    # --- MECHANISM FLOOR 2: the 8 metric classes ALL named, with agent-usability's sub-metrics. A
    # thin port drops a class or the infiquetra-native sub-metrics. ---
    assert "perf" in corpus, "metric class: perf"
    assert "cost" in corpus, "metric class: cost"
    assert "reliability" in corpus, "metric class: reliability"
    assert "agent-usability" in corpus, (
        "metric class: agent-usability (the infiquetra-native class)"
    )
    assert "security" in corpus, "metric class: security"
    assert re.search(r"quality/accuracy|quality |\bquality\b", corpus), "metric class: quality"
    assert re.search(r"developer-experience|developer experience|\bDX\b", corpus), (
        "metric class: developer-experience / DX"
    )
    assert "maintainability" in corpus, "metric class: maintainability"
    # agent-usability sub-metrics (Jeff's angle, all four named).
    assert re.search(r"token cost|\btoken\b", corpus), "agent-usability sub-metric: token cost"
    assert "steps-to-success" in corpus, "agent-usability sub-metric: steps-to-success"
    assert "retry rate" in corpus, "agent-usability sub-metric: retry rate"
    assert re.search(r"plan-readability|plan readability", corpus), (
        "agent-usability sub-metric: plan-readability"
    )

    # --- MECHANISM FLOOR 3: the hard-vs-judge THREE-TIER model. Both "hard" and "judge" present, and
    # the three-tier ordering: degenerate gates (tier 1) -> LLM-as-judge / judge (tier 2) ->
    # diagnostics (tier 3). A thin port flattens these into one undifferentiated check. ---
    assert "hard" in corpus.lower() and "judge" in corpus.lower(), (
        "the hard-vs-judge model must name both 'hard' and 'judge'"
    )
    assert "LLM-as-judge" in corpus or "LLM-as-judge" in corpus.replace("\n", " "), (
        "the judge tier must be the LLM-as-judge model"
    )
    assert "diagnostic" in corpus.lower(), "the three-tier model must name the diagnostics tier"
    # The three-tier ordering inside the model section (degenerate < judge < diagnostic).
    sec_start = corpus.find("hard-vs-judge three-tier model")
    assert sec_start != -1, "the hard-vs-judge three-tier model section must exist"
    body = corpus[sec_start : sec_start + 1500]
    body = body[body.find("\n") :].lower()  # drop the header line itself
    d_idx, j_idx, g_idx = (
        body.find("degenerate"),
        body.find("judge"),
        body.find("diagnostic"),
    )
    assert -1 < d_idx < j_idx < g_idx, (
        "the three-tier order must be degenerate gates -> judge -> diagnostics, cheapest first"
    )

    # --- MECHANISM FLOOR 4: the flat-file LOOP HOME + the DURABLE SPLIT. Run state is machine-local
    # scratch under .claude/...; the two durable sinks are docs/optimize/ + the journal LEARNINGS. ---
    assert ".claude/saga/optimize/" in corpus, (
        "run state must live under the flat-file loop home .claude/saga/optimize/"
    )
    assert "docs/optimize/" in corpus, (
        "the durable shareable summary must live under docs/optimize/"
    )
    assert "LEARNINGS" in corpus, "the durable journal sink (LEARNINGS.md) must be named"

    # --- MECHANISM FLOOR 5 (THE DISTINGUISHING FLOOR vs /strategy & /spec): operator-choice is
    # OFFERED for independent experiment fan-out, recorded NARRATIVELY (which is what makes "offers a
    # backend" consistent with "saga-untouched"). The SKILL cites operator-choice.md (relative path),
    # names the 3 backend enums, justifies the OFFER by independent-experiment fan-out, and NEVER
    # auto-spawns. A flat /strategy clone (which never offers operator-choice) fails this floor. ---
    assert "operator-choice.md" in skill_doc, (
        "the SKILL must cite the operator-choice contract by relative path"
    )
    for backend in ("inline", "team-execution", "cc-workflows-ultracode"):
        assert backend in corpus, f"the operator-choice backend {backend!r} must be named"
    assert re.search(
        r"independent.*experiment|experiment.*fan-out|parallel.*experiment", corpus, re.IGNORECASE
    ), "the OFFER must be justified by independent-experiment fan-out (the distinguishing trigger)"
    assert re.search(r"OFFER|offered|never auto", corpus), (
        "the backend is OFFERED, never auto-spawned"
    )
    # NARRATIVE recording is what reconciles "offers a backend" with "saga-untouched": a non-saga
    # writer records the chosen backend in prose (the strategy digest), not via saga.save.
    assert re.search(r"narrativ", corpus, re.IGNORECASE), (
        "the chosen backend must be recorded NARRATIVELY (a non-saga-writer records the choice in "
        "prose) — this is what makes 'offers a backend' consistent with 'saga-untouched'"
    )

    # --- MECHANISM FLOOR 6: SAGA UNTOUCHED — the off-chain twin of /strategy & /spec (saga UNTOUCHED),
    # NOT /investigate (saga READ-ONLY): there is NO `saga.py restore` present-assert here. /optimize
    # runs off-chain and never writes the work thread. The two strict pins mirror test_strategy
    # EXACTLY (no `saga.py save` string, no runnable `python saga.py`). The bare `saga.py` and
    # `--lifecycle-phase` tokens are, on the real E1 file, present ONLY inside the off-chain boundary
    # negation ("it is off-chain: no `saga.py` invocation, no `--lifecycle-phase`"), so a flat
    # `--lifecycle-phase not in corpus` assert (the task brief, written from the LABEL) contradicts
    # the shipped SKILL — exactly the #spec-adaptation-is-a-hypothesis case test_spec already hit.
    # Pin them with a negation-window instead (the test_spec off-chain pattern), keeping the strict
    # no-runnable-save mechanism. ---
    assert "saga.py save" not in corpus, "/optimize must never emit a `saga.py save` write"
    assert not re.search(r"python3?\s+\S*saga\.py", corpus), (
        "/optimize must emit no runnable `python saga.py` invocation (it never writes the saga)"
    )
    for match in re.finditer(r"--lifecycle-phase", flat):
        window = flat[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no)\b", window, flags=re.IGNORECASE), (
            "`--lifecycle-phase` must only appear inside an off-chain negation window (no saga "
            f"write), found positive use near: {flat[max(0, match.start() - 50) : match.start() + 30]!r}"
        )
    for match in re.finditer(r"\bsaga\.py\b", flat, flags=re.IGNORECASE):
        window = flat[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no|untouched)\b", window, flags=re.IGNORECASE), (
            "`saga.py` must only appear inside an off-chain negation window, found positive use "
            f"near: {flat[max(0, match.start() - 50) : match.start() + 30]!r}"
        )

    # --- MECHANISM FLOOR 7: ZERO new Python. /optimize is a skills-only single-source port (the
    # agent parses the YAML natively; no /qa-style risk-weighted scorer is ported). A stray .py under
    # skills/optimize means scope crept into code. ---
    assert not list((PLUGIN_ROOT / "skills" / "optimize").glob("**/*.py")), (
        "/optimize must add no new Python under skills/optimize (it is a skills-only port)"
    )

    # --- MECHANISM FLOOR 8: HARD-BOUNDARY negatives. The winner is ROUTED to /work to ship — the
    # engine never auto-commits or auto-merges experiment branches, and never deploys. POSITIVE
    # boundary prose first; then a NEGATION-WINDOW for ONLY the unambiguous mutation verb `deploy`
    # (mirror test_strategy's deploy finditer — every `deploy`/`deployed` occurrence must sit within
    # ~70 chars after a not/never/without/no). `push`/`commit`/`merge` are DELIBERATELY EXCLUDED from
    # windowing — faithful prose uses them as benign nouns ("git commit", "merge a PR", "becomes a
    # real commit") — so those boundaries are pinned by the no-runnable substring-absence asserts
    # below instead. The engine-IDENTITY verbs optimize / measure / baseline / experiment / tune /
    # keep / revert are NEVER windowed — the engine's positive identity is to do them. ---
    assert "does **NOT**" in skill_doc, "the Hard boundary must bold the does-NOT clauses"
    # Winners are routed to /work (never auto-committed / auto-merged inside the engine).
    assert re.search(
        r"never[^\n]*auto-(commit|merge)|not[^\n]*auto-(commit|merge)|"
        r"auto-(commit|merge)[^\n]*(routed|/work)",
        corpus,
        re.IGNORECASE,
    ) or re.search(r"routed to[^\n]*/work|routes? .* to[^\n]*/work", corpus, re.IGNORECASE), (
        "the engine must never auto-commit/auto-merge experiment branches — winners route to /work"
    )
    for match in re.finditer(r"\bdeploys?\b|\bdeployed\b", flat_skill, flags=re.IGNORECASE):
        window = flat_skill[max(0, match.start() - 70) : match.start()]
        assert re.search(r"\b(not|never|without|no)\b", window, flags=re.IGNORECASE), (
            "mutation verb 'deploy' must only appear inside a negation window, found positive use "
            f"near: {flat_skill[max(0, match.start() - 50) : match.start() + 30]!r}"
        )
    # No runnable mutation command anywhere in the SKILL: no git commit/push/merge, no gh-PR
    # create/merge. These are flat substring-absence (faithful prose does not emit them).
    assert "git push" not in skill_doc, "/optimize must emit no runnable `git push`"
    assert "git commit" not in skill_doc, "/optimize must emit no runnable `git commit`"
    assert "git merge" not in skill_doc, "/optimize must emit no runnable `git merge`"
    assert "gh pr create" not in skill_doc, "/optimize must emit no runnable `gh pr create`"
    assert "gh pr merge" not in skill_doc, "/optimize must emit no runnable `gh pr merge`"
    # /optimize never files an SDLC issue. `gh issue create` appears ONLY inside negations ("Never
    # run `gh issue create`", "does **NOT** run `gh issue create`"), so a flat token-absence assert
    # would fail the FAITHFUL engine — pin the no-runnable mechanism (the /retro pattern): every
    # occurrence sits inside a negation window.
    assert not re.search(r"(?<!Never run )(?<!NOT\*\* run )gh issue create", corpus) or all(
        re.search(
            r"\b(not|never)\b",
            flat[max(0, m.start() - 50) : m.start()],
            re.IGNORECASE,
        )
        for m in re.finditer(r"gh issue create", flat)
    ), (
        "/optimize must file no SDLC issue (`gh issue create` only inside a negation; mission-control owns it)"
    )

    # --- MECHANISM FLOOR 9: ROUTING — /handoff, /work, /brainstorm are the named onward routes, and
    # the dispatch table is REFERENCED by path, NOT restated (one source of truth, no
    # /optimize<->/loop duplication). Infiquetra-name purity: the route is /optimize, never /ce-*. ---
    for route in ("/handoff", "/work", "/brainstorm"):
        assert route in corpus, f"the onward routing must name {route!r}"
    assert "loop/references/dispatch-table.md" in skill_doc, (
        "cross-command routing must REFERENCE the dispatch-table by path"
    )
    assert "# Dispatch Table" not in corpus, (
        "the dispatch-table H1 title must not be restated in /optimize"
    )
    assert "/ce-optimize" not in corpus, (
        "the command is the Infiquetra /optimize, never a /ce-* alias (name purity)"
    )

    # --- MECHANISM FLOOR 10: ATTRIBUTION HONESTY. ce-optimize is the SINGLE honestly-attributed
    # source: it appears inside an attribution window, the explicit non-merge claim is present, and
    # agent-usability is framed infiquetra-native (Jeff's angle / not a gstack port). No "gstack
    # insight" prose is required (gstack plan-tune contributed nothing). The single hard-absence: no
    # command shim — neither a ce-* alias nor the gstack plan-tune.md. ---
    attr_kw = re.compile(
        r"(Ported|ported|\bCE\b|Compound-Engineering|source|grounded|SHED|SHEDS|adapt)",
        re.IGNORECASE,
    )
    ce_matches = list(re.finditer(r"ce-optimize", flat))
    assert ce_matches, "the attribution must name the source engine `ce-optimize`"
    assert any(attr_kw.search(flat[max(0, m.start() - 90) : m.end() + 50]) for m in ce_matches), (
        "ce-optimize must appear inside an attribution window (named near a port/source token)"
    )
    assert re.search(r"single-source|not a balanced|not a .{0,20}merge", corpus), (
        "the explicit non-merge claim must be present (single-source port, NOT a balanced merge)"
    )
    assert re.search(r"infiquetra-native|infiquetra native", corpus) or re.search(
        r"Jeff's angle|not a gstack", corpus
    ), "agent-usability must be framed infiquetra-native (Jeff's angle / not a gstack port)"
    # Single hard-absence: no command shim was created — neither a ce-* alias nor gstack plan-tune.
    assert not list((PLUGIN_ROOT / "commands").glob("ce-*.md")), (
        "no commands/ce-*.md shim must exist (the port is /optimize, not a ce-* alias)"
    )
    assert not (PLUGIN_ROOT / "commands" / "plan-tune.md").exists(), (
        "no plan-tune.md command shim must exist (gstack plan-tune is not ported)"
    )

    # --- MECHANISM FLOOR 11: lane boundaries vs /pulse and /qa. /pulse is the CONTINUOUS / live
    # telemetry sibling — /optimize is BOUNDED; /qa GATES (one-shot ship verdict) while /optimize
    # LOOPS toward a target. A thin port has no lane discrimination. ---
    assert re.search(r"/pulse|live telemetry|continuous", corpus) and "bounded" in corpus.lower(), (
        "the /pulse boundary must pair continuous-vs-bounded (the BOUNDED experiment loop)"
    )
    assert re.search(r"GATES|gate.*loop|one-shot", skill_doc) and re.search(
        r"LOOPS|loop", skill_doc
    ), "the /qa boundary must state gate-vs-loop (/qa gates one-shot, /optimize loops to a target)"

    # --- MECHANISM FLOOR 12: the interaction model — AskUserQuestion for choices, free-form for
    # substance, and the channel-inline fallback citing brainstorm when redis-channel is active. ---
    assert "AskUserQuestion" in skill_doc, "choices from a known set must use AskUserQuestion"
    assert "free-form" in skill_doc, "substantive content must use free-form responses"
    assert "redis-channel" in skill_doc and "inline" in skill_doc, (
        "the channel-inline fallback must be named for redis-channel sessions"
    )
    assert "brainstorm/SKILL.md" in skill_doc, (
        "the channel-inline convention must cite brainstorm/SKILL.md (not duplicate it)"
    )

    # --- MECHANISM FLOOR 13: thin-port tripwire — both reference files exist and carry real content
    # (>= 60 lines), and the SKILL is a real engine (>= 200 lines), not a transcribed stub. ---
    for ref in ("metric-taxonomy.md", "experiment-loop.md"):
        ref_path = optimize / "references" / ref
        assert ref_path.exists()
        assert len(_read(ref_path).splitlines()) >= 60
    assert len(skill_doc.splitlines()) >= 200, (
        "the /optimize SKILL must be a real engine (>= 200 lines), not a thin transcribed stub"
    )

    # --- /optimize is packaged as a command (the campaign's final routable optimization lens). ---
    assert (PLUGIN_ROOT / "commands" / "optimize.md").exists(), "/optimize must be packaged"


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


def test_recommend_execution_backend_adversarial_confidence() -> None:
    """adversarial_confidence is the SECOND ultracode trigger beside broad fan-out.

    Prove-by-refutation / judge-panel work with no deploy/security signal is an
    ultracode shape (deterministic INDEPENDENT verification), not an inline one.
    It rides the same risk gate and the same capability gate as broad fan-out.
    """
    lifecycle = _load_module("lifecycle_state.py")
    rec = lifecycle.recommend_execution_backend

    # adversarial_confidence alone, no risk -> cc-workflows-ultracode.
    assert rec(adversarial_confidence=True)["recommended"] == "cc-workflows-ultracode"

    # The risk gate still suppresses it: an elevated-risk signal routes to team.
    assert rec(adversarial_confidence=True, has_security=True)["recommended"] == "team-execution"

    # Capability gate: with the Workflow tool absent it degrades to inline and
    # drops ultracode from the offer (mirrors the broad-fanout degrade).
    gated = rec(adversarial_confidence=True, workflow_available=False)
    assert gated["recommended"] == "inline"
    assert gated["omit_ultracode"] is True

    # Overlap: adversarial_confidence (ultracode) AND needs_consensus (team wins)
    # still lists ultracode as a one-keystroke alternative.
    overlap = rec(adversarial_confidence=True, needs_consensus=True)
    assert overlap["recommended"] == "team-execution"
    assert "cc-workflows-ultracode" in overlap["alternatives"]


def test_recommend_execution_backend_gated_vs_advisory_consensus() -> None:
    """R7 keystone: needs_consensus splits on the GOVERNANCE axis (gated vs advisory).

    The old behavior hard-forced team-execution on EVERY consensus signal
    (``or needs_consensus``). U6 replaces that with consensus_is_gated:

    * GATED (default) -> team-execution: the verdict must block/persist.
    * ADVISORY        -> cc-workflows-ultracode: throwaway in-session votes
      ride the existing adversarial_confidence ultracode branch.

    A contested-but-not-gated job must reach the ADVISORY ultracode branch and
    NEVER regress to inline. The docs-gating (has_code_surface) and the overlap
    alternatives behavior are preserved.
    """
    lifecycle = _load_module("lifecycle_state.py")
    rec = lifecycle.recommend_execution_backend

    # AE2 — GATED consensus (the default) -> team-execution. A bare
    # needs_consensus=True keeps the legacy behavior (default consensus_is_gated=True).
    gated = rec(needs_consensus=True)
    assert gated["recommended"] == "team-execution"
    assert rec(needs_consensus=True, consensus_is_gated=True)["recommended"] == "team-execution"

    # AE1 — ADVISORY consensus, no risk -> cc-workflows-ultracode (the judge-panel),
    # NOT team-execution and NOT inline.
    advisory = rec(needs_consensus=True, consensus_is_gated=False)
    assert advisory["recommended"] == "cc-workflows-ultracode"

    # The hard-force is gone: advisory consensus alone no longer routes to team.
    assert advisory["recommended"] != "team-execution"
    # team-execution stays a one-keystroke alternative for the advisory pick.
    assert "team-execution" in advisory["alternatives"]

    # consensus_is_gated is INERT when there is no consensus signal at all:
    # a bare job stays inline whether the flag is set or not.
    assert rec(consensus_is_gated=False)["recommended"] == "inline"
    assert rec(consensus_is_gated=True)["recommended"] == "inline"

    # Advisory consensus rides the SAME risk gate as the other ultracode triggers:
    # an elevated-risk code surface suppresses the ultracode branch -> team-execution.
    assert (
        rec(needs_consensus=True, consensus_is_gated=False, has_security=True)["recommended"]
        == "team-execution"
    )

    # Advisory consensus rides the SAME capability gate: absent the Workflow tool
    # it degrades to inline and drops ultracode from the offer.
    no_wf = rec(needs_consensus=True, consensus_is_gated=False, workflow_available=False)
    assert no_wf["recommended"] == "inline"
    assert no_wf["omit_ultracode"] is True
    assert "cc-workflows-ultracode" not in no_wf["alternatives"]

    # OVERLAP — gated consensus AND broad fan-out: team wins precedence, but
    # cc-workflows-ultracode is still listed as a one-keystroke escalation.
    overlap = rec(needs_consensus=True, consensus_is_gated=True, broad_independent_fanout=True)
    assert overlap["recommended"] == "team-execution"
    assert "cc-workflows-ultracode" in overlap["alternatives"]
    assert "team-execution" not in overlap["alternatives"]

    # DOCS-GATING preserved. Advisory consensus on a pure-docs change (no code
    # surface) still reaches the ultracode judge-panel — has_code_surface gates the
    # code-shaped proxies, not the governance-shaped consensus routing.
    docs_advisory = rec(needs_consensus=True, consensus_is_gated=False, has_code_surface=False)
    assert docs_advisory["recommended"] == "cc-workflows-ultracode"
    # GATED consensus survives the docs neutralizer (it is governance, not code).
    docs_gated = rec(needs_consensus=True, consensus_is_gated=True, has_code_surface=False)
    assert docs_gated["recommended"] == "team-execution"


def test_recommend_backend_cli_advisory_consensus(capsys: pytest.CaptureFixture[str]) -> None:
    """--advisory-consensus round-trips through main(): the new branch is CLI-reachable.

    Without a runnable flag the gated/advisory split is unreachable from the
    markdown caller, so the flag must flow end-to-end. Omitting it keeps the
    gated default (team-execution); setting it routes to the ultracode judge-panel.
    """
    lifecycle = _load_module("lifecycle_state.py")

    # Default (gated): --needs-consensus alone -> team-execution.
    assert lifecycle.main(["recommend-backend", "--needs-consensus"]) == 0
    gated = json.loads(capsys.readouterr().out)
    assert gated["recommended"] == "team-execution"

    # --advisory-consensus flips it to the ultracode judge-panel.
    assert lifecycle.main(["recommend-backend", "--needs-consensus", "--advisory-consensus"]) == 0
    advisory = json.loads(capsys.readouterr().out)
    assert advisory["recommended"] == "cc-workflows-ultracode"
    assert "team-execution" in advisory["alternatives"]


def test_recommend_execution_backend_docs_no_code_surface() -> None:
    """has_code_surface=False neutralizes the OUTPUT-BLIND proxies for docs.

    team-execution's scanners + deploy gate are code-shaped and inert on pure
    docs/spec/research. So size (file/phase) and the parse_issue.py keyword flags
    (has_infra/has_security/deployment_sensitive) must NOT force team-execution on
    a docs change. The two output-AGNOSTIC governance signals survive: cross_repo
    (ownership boundary) and needs_consensus (contested).
    """
    lifecycle = _load_module("lifecycle_state.py")
    rec = lifecycle.recommend_execution_backend

    # Default (has_code_surface=True): the size proxy still trips team-execution.
    assert rec(file_count=12)["recommended"] == "team-execution"

    # Docs: the size/sequencing proxies are voided -> inline.
    assert rec(file_count=12, has_code_surface=False)["recommended"] == "inline"
    assert rec(phase_count=6, has_code_surface=False)["recommended"] == "inline"

    # Docs: the keyword risk proxies are voided too (mention != touch). An infra
    # runbook or a threat-model doc must not be conscripted into team-execution.
    assert rec(has_infra=True, has_code_surface=False)["recommended"] == "inline"
    assert rec(has_security=True, has_code_surface=False)["recommended"] == "inline"
    assert rec(deployment_sensitive=True, has_code_surface=False)["recommended"] == "inline"

    # Broad docs (many files) fan out via ultracode even with a keyword risk flag
    # set, because the suppressor is itself gated by has_code_surface.
    assert (
        rec(file_count=12, broad_independent_fanout=True, has_code_surface=False)["recommended"]
        == "cc-workflows-ultracode"
    )
    assert (
        rec(has_infra=True, broad_independent_fanout=True, has_code_surface=False)["recommended"]
        == "cc-workflows-ultracode"
    )

    # The output-AGNOSTIC governance signals SURVIVE the neutralizer: cross_repo
    # (ownership boundary) and needs_consensus (contested) still fire on docs.
    assert rec(cross_repo=True, has_code_surface=False)["recommended"] == "team-execution"
    assert rec(needs_consensus=True, has_code_surface=False)["recommended"] == "team-execution"

    # Overlap still lists ultracode: docs breadth + consensus -> team recommended,
    # ultracode an alternative.
    overlap = rec(
        file_count=12,
        broad_independent_fanout=True,
        needs_consensus=True,
        has_code_surface=False,
    )
    assert overlap["recommended"] == "team-execution"
    assert "cc-workflows-ultracode" in overlap["alternatives"]


def test_recommend_backend_cli_new_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """--adversarial-confidence and --no-code-surface round-trip through main().

    Without a runnable CLI surface the new triggers are unreachable from the
    markdown callers, so the flags must flow end-to-end, not just exist in Python.
    """
    lifecycle = _load_module("lifecycle_state.py")

    # --adversarial-confidence -> cc-workflows-ultracode.
    assert lifecycle.main(["recommend-backend", "--adversarial-confidence"]) == 0
    adv = json.loads(capsys.readouterr().out)
    assert adv["recommended"] == "cc-workflows-ultracode"

    # --no-code-surface voids the size proxy: a 12-file docs change -> inline.
    assert lifecycle.main(["recommend-backend", "--file-count", "12", "--no-code-surface"]) == 0
    docs = json.loads(capsys.readouterr().out)
    assert docs["recommended"] == "inline"

    # --no-code-surface keeps cross_repo live (the ownership-boundary signal).
    assert lifecycle.main(["recommend-backend", "--cross-repo", "--no-code-surface"]) == 0
    cross = json.loads(capsys.readouterr().out)
    assert cross["recommended"] == "team-execution"


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
    assert envelope["lifecycle_owner"] == "saga"
    assert envelope["issue_artifact_owner"] == "mission-control"
    assert envelope["body_template_owner"] == "mission-control"
    assert envelope["suggested_command"].startswith("/issue --prepare")
    assert "--from docs/plans/example.md" in envelope["suggested_command"]
    assert "--maturity plan-ready" in envelope["suggested_command"]
    assert "/loop" not in envelope["suggested_command"]

    # A /spec artifact under docs/specs/ is a sharp WHAT (requirements-ready) and OFF-CHAIN:
    # it carries no lifecycle phase (the saga-untouched /spec produces a backlog source, not a
    # work-thread tick). These pin the docs/specs/ handoff inference E1 wired for the /spec port.
    assert handoff.infer_maturity("docs/specs/x-spec.md") == "requirements-ready"
    assert handoff.infer_lifecycle_phase("docs/specs/x-spec.md") == "unknown"


def test_handoff_envelope_discovers_active_plan_from_loop_state(tmp_path) -> None:
    handoff = _load_module("handoff_envelope.py")
    state = tmp_path / ".claude" / "saga" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps({"current_work": {"plan_path": "docs/plans/active.md"}}),
        encoding="utf-8",
    )

    envelope = handoff.build_handoff_envelope(root=tmp_path)

    assert envelope["source"] == "docs/plans/active.md"
    assert envelope["handoff_maturity"] == "plan-ready"


def _load_saga_module():
    """Load saga.py REGISTERED in sys.modules.

    saga.py defines a frozen @dataclass; on Python 3.12+ the dataclass build
    looks the class's __module__ up in sys.modules, so an unregistered import
    raises during exec. (The module-level ``_load_module`` here does not
    register, so it cannot load saga.py.)
    """
    path = PLUGIN_ROOT / "scripts" / "saga.py"
    spec = importlib.util.spec_from_file_location("saga", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["saga"] = module
    spec.loader.exec_module(module)
    return module


def test_scan_exposes_picker_fields(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """scan() candidates surface the five groundable picker fields /loop needs.

    Mirrors the `saga save --kind task --id loop-picker-probe ...` CLI call by
    building the same Saga the CLI would and driving save/scan directly (the way
    the engine tests do), then asserts the candidate dict carries the saved
    destination / issue_ref / plan_path / orchestration_mode / orchestration_ref.
    """
    saga = _load_saga_module()
    # Stub the git seam so the offline test never shells out and the cached git
    # snapshot stays empty (deterministic). Patch both the attribute and the
    # keyword-only ``runner`` default captured on save/current_git_state. Use
    # monkeypatch so every patch reverts on teardown: ``saga.subprocess`` is the
    # shared global ``subprocess`` module singleton, so an unrestored
    # ``subprocess.run`` reassignment leaks into every other module that calls
    # ``subprocess.run`` (e.g. redis-channel presence.detect_git_branch).
    no_git = lambda *_a, **_k: SimpleNamespace(returncode=1, stdout="", stderr="")  # noqa: E731
    monkeypatch.setattr(saga.subprocess, "run", no_git)
    for fn_name in ("save", "current_git_state"):
        fn = getattr(saga, fn_name)
        new_kwdefaults = dict(fn.__kwdefaults__ or {})
        new_kwdefaults["runner"] = no_git
        monkeypatch.setattr(fn, "__kwdefaults__", new_kwdefaults)

    probe = saga.Saga(
        saga_id=saga.derive_saga_id("task", "loop-picker-probe"),
        kind="task",
        id="loop-picker-probe",
        destination="pr",
        issue_ref="owner/repo#7",
        plan_path="docs/plans/x.md",
        branch="feat/loop-probe",
        orchestration_mode="cc-workflows-ultracode",
        orchestration_ref="wf_probe123",
    )
    saga.save(tmp_path, probe, now=datetime(2026, 6, 2, 14, 5, 10, tzinfo=UTC))

    candidates = saga.scan(tmp_path)
    candidate = next(c for c in candidates if c["saga_id"] == "task-loop-picker-probe")

    assert candidate["destination"] == "pr"
    assert candidate["issue_ref"] == "owner/repo#7"
    assert candidate["plan_path"] == "docs/plans/x.md"
    # branch is the third #code-review-saga-scan-touchups match key (Defect 1).
    assert candidate["branch"] == "feat/loop-probe"
    assert candidate["orchestration_mode"] == "cc-workflows-ultracode"
    assert candidate["orchestration_ref"] == "wf_probe123"


def test_ae10_status_card_single_emitter_routing() -> None:
    """AE10: each of the five saga surfaces routes its operator-facing status-summary
    through the shared status_card renderer (R14 — retire per-surface prose emissions).

    Tokens chosen from the actual authored SKILL.md prose — these are load-bearing
    contract assertions, not fragile grep guards. KTD5 evidence detail is kept as
    drill-down body below the card; per-finding tables and verdict values remain.
    """
    work_doc = _read(PLUGIN_ROOT / "skills" / "work" / "SKILL.md")
    cr_doc = _read(PLUGIN_ROOT / "skills" / "code-review" / "SKILL.md")
    qa_doc = _read(PLUGIN_ROOT / "skills" / "qa" / "SKILL.md")
    outcome_doc = _read(PLUGIN_ROOT / "skills" / "outcome" / "SKILL.md")
    resume_doc = _read(PLUGIN_ROOT / "skills" / "resume" / "SKILL.md")

    # --- /work ---
    # PRESENT: card renderer and per-surface function name.
    assert "status_card" in work_doc
    assert "project_work" in work_doc
    # PRESENT: U2 producer flag — gate_verdicts written by /work Phase-3 tick.
    assert "--gate-verdict" in work_doc
    # PRESENT: the producer example uses a CANONICAL gate state — a passing gate is `tests:done:<ref>`.
    assert "tests:done:<ref>" in work_doc
    # ABSENT: the non-canonical `pass|fail|skip` vocab would parse to *unknown* and silently drop the
    # verdict (the Tests card cell would render not-reached) — guard against that regression.
    assert "tests:<pass|fail|skip>" not in work_doc
    # PRESENT (substantive): the card render is the LEAD status step (step 1) of §5.4 — proving the
    # card is the operator status HEADER, not an afterthought — and the continuation-routing step that
    # was step 3 is pushed to step 4 by the insertion (proves a real reorder, not a keyword sprinkle).
    assert "1. **Render the operator status header**" in work_doc
    assert "4. **Present continuation routing**" in work_doc
    # STILL PRESENT (KTD5): detailed work-session evidence reference.
    assert "work-session" in work_doc

    # --- /code-review ---
    # PRESENT: card renderer and per-surface function name.
    assert "status_card" in cr_doc
    assert "project_code_review" in cr_doc
    # ABSENT: old standalone "blockquote verdict" status-summary phrasing (retired by card).
    assert "blockquote verdict" not in cr_doc
    # STILL PRESENT (KTD5): per-finding evidence table header (drill-down body kept).
    assert "# | File | Issue | Reviewer | Confidence | Route" in cr_doc

    # --- /qa ---
    # PRESENT: card renderer and per-surface function name.
    assert "status_card" in qa_doc
    assert "project_qa" in qa_doc
    # ABSENT: old bold "**health-score block**" as standalone operator-facing presentation element.
    assert "**health-score block**" not in qa_doc
    # STILL PRESENT (KTD5): verdict values are the card's data source; remain in artifact spec.
    assert "ship-with-deferred" in qa_doc
    assert "no-ship" in qa_doc

    # --- /outcome ---
    # PRESENT: card renderer and per-surface function name.
    assert "status_card" in outcome_doc
    assert "project_outcome" in outcome_doc
    # ABSENT: old terse status-verb description without card routing
    # ("cockpit snapshot (states, counts, frontier)" was the entire verb description pre-migration).
    assert "cockpit snapshot (states, counts, frontier)" not in outcome_doc
    # STILL PRESENT (KTD5): derived-on-read principle (R17) and spec/completion-event sources.
    assert "derived on read" in outcome_doc

    # --- /resume ---
    # PRESENT: card renderer and per-surface function name.
    assert "status_card" in resume_doc
    assert "project_resume" in resume_doc
    # PRESENT (substantive, not keyword): the card-render DIRECTIVE is wired into the Phase 3a
    # reconstruction flow. /resume's migration is ADDITIVE (it previously emitted no status card), so
    # the contract is proven by the directive's presence — a no-op draft would lack this exact prose.
    assert "render the operator status header via the shared card renderer" in resume_doc
    # STILL PRESENT (KTD5): durable state fields that the card derives its cells from.
    assert "next-step" in resume_doc
    assert "blockers" in resume_doc
