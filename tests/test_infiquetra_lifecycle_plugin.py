"""Contract tests for the infiquetra-lifecycle plugin package."""

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
    assert plugin_json["version"] == "0.14.0"
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
    assert ".claude/infiquetra-lifecycle/" in corpus
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

    # --- MECHANISM FLOOR 9: MERGE-STATE FAILURE ROUTING — pre-merge -> /work, post-merge ->
    # /handoff. /investigate is NOT on a runnable-route line (future prose only). ---
    assert "Pre-merge" in skill_doc and "/work" in skill_doc, "pre-merge failure routes to /work"
    assert "Post-merge" in skill_doc and "/handoff" in skill_doc, (
        "post-merge failure routes to /handoff"
    )
    # /investigate is named only as future prose, never emitted as a runnable route. Assert it is
    # not on a route-arrow / "route ... to /investigate" line, and that its mentions sit inside a
    # not-yet / future / not-a-route window.
    assert not re.search(r"(?:->|→|\broute[sd]?\b[^\n]*\bto\b)[^\n]*/investigate", skill_doc), (
        "/investigate must NOT appear as a runnable route target"
    )
    flat_skill_inv = re.sub(r"\s+", " ", skill_doc)
    for match in re.finditer(r"/investigate", flat_skill_inv):
        window = flat_skill_inv[max(0, match.start() - 90) : match.start() + 90]
        assert re.search(
            r"\b(future|when .*?is built|until then|not a runnable route|never emit|not\b.*\broutable|own)\b",
            window,
            flags=re.IGNORECASE,
        ), (
            f"/investigate must appear only as future/non-route prose, "
            f"found near: {flat_skill_inv[match.start() - 50 : match.start() + 50]!r}"
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
