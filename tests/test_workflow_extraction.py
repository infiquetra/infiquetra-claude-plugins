"""Claude Code Workflow capability extraction — issue #925 (issue #918 wave 1, U4).

Sub-part A: the #808 counterfactual "if recommended is cc-workflows-ultracode" branches are
gone from the four offer files; the recommender never returns the Workflow backend as
recommended. Sub-part B: the generated-artifact write-path convention is docs/workflows/,
not docs/plans/. Sub-part C: the workflow-script emitter lives in the cc-workflows plugin
behind the typed spec contract; Saga keeps the integration contract, and the team/outcome
paths still resolve the spec schema from Saga.

No end-to-end Workflow tool launch is claimed: the pin is emit-from-spec against the
extracted emitter's real emit path (review-cycle-2 disposition).
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
CC_WORKFLOWS_SCRIPTS = ROOT / "plugins" / "cc-workflows" / "skills" / "cc-workflows" / "scripts"
EMITTER_PATH = CC_WORKFLOWS_SCRIPTS / "emitter.py"
PLUGIN_SKILL = ROOT / "plugins" / "cc-workflows" / "skills" / "cc-workflows" / "SKILL.md"
PLUGIN_PROTOCOL = (
    ROOT / "plugins" / "cc-workflows" / "skills" / "cc-workflows" / "references" / "protocol.md"
)

PLAN_SKILL = ROOT / "plugins" / "saga" / "skills" / "plan" / "SKILL.md"
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
OPERATOR_CHOICE = ROOT / "plugins" / "saga" / "references" / "operator-choice.md"
EXECUTION_STRATEGY = (
    ROOT / "plugins" / "saga" / "skills" / "work" / "references" / "execution-strategy.md"
)
EXECUTION_SPEC_DOC = ROOT / "plugins" / "saga" / "references" / "execution-spec.md"


def _load_module(name: str, path: Path) -> ModuleType:
    """Load by path, reusing the canonical sys.modules entry when one exists.

    Several suites load execution_spec instances into one process; reusing the registered
    module (the team_emitter.py convention) keeps the spec classes one set.
    """
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load_module("execution_spec", SAGA_SCRIPTS / "execution_spec.py")
LIFECYCLE = _load_module("lifecycle_state", SAGA_SCRIPTS / "lifecycle_state.py")
EMITTER = _load_module("workflow_extraction_emitter", EMITTER_PATH)


def _spec_dict() -> dict[str, object]:
    return {
        "name": "extraction-pin",
        "description": "U4 emit-from-spec pin",
        "repo": "/tmp/repo",
        "units": [
            {
                "unit_id": "U1",
                "label": "first",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "implement first",
            },
            {
                "unit_id": "U2",
                "label": "second",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "implement second",
                "depends_on": ["U1"],
            },
        ],
    }


# --- Sub-part A: the counterfactual branches are gone (#808, #840 C5) -----------------


def test_no_counterfactual_preselect_branches_remain() -> None:
    counterfactuals = (
        "if `recommended` is `cc-workflows-ultracode`",
        "if the helper's `recommended` value is `cc-workflows-ultracode`",
        "if the helper recommends it",
    )
    for path in (PLAN_SKILL, WORK_SKILL, OPERATOR_CHOICE, EXECUTION_STRATEGY):
        # Collapse whitespace runs before matching: the branch this guard hunts wraps
        # across a line break in half these files, and a flat literal comparison passes
        # vacuously against the wrapped form (review F02).
        collapsed = " ".join(path.read_text(encoding="utf-8").lower().split())
        for phrase in counterfactuals:
            assert phrase not in collapsed, f"{path.name} still carries {phrase!r}"


def test_each_offer_file_keeps_an_unconditional_never_pre_select_sentence() -> None:
    for path in (PLAN_SKILL, WORK_SKILL, OPERATOR_CHOICE, EXECUTION_STRATEGY):
        collapsed = " ".join(path.read_text(encoding="utf-8").lower().split())
        assert "never pre-select" in collapsed or "do not pre-select" in collapsed, (
            f"{path.name} lost its unconditional never-pre-select sentence"
        )


def test_recommend_never_returns_ultracode_as_recommended() -> None:
    # Positive: across the trigger matrix the Workflow backend is never the
    # recommendation — it stays an explicit-invocation-only alternative.
    sizes = ({"file_count": 2, "phase_count": 1}, {"file_count": 30, "phase_count": 6})
    consensus = (
        {"needs_consensus": False},
        {"needs_consensus": True, "consensus_is_gated": True},
        {"needs_consensus": True, "consensus_is_gated": False},
    )
    matrix = itertools.product(
        sizes,
        consensus,
        (False, True),  # broad_independent_fanout
        (False, True),  # adversarial_confidence
        (True, False),  # workflow_available
        ((), ("review",)),  # workflow_shapes
    )
    for size, cons, fanout, adversarial, available, shapes in matrix:
        result = LIFECYCLE.recommend_execution_backend(
            **size,
            **cons,
            broad_independent_fanout=fanout,
            adversarial_confidence=adversarial,
            workflow_available=available,
            workflow_shapes=shapes,
        )
        assert result["recommended"] in {"inline", "team-execution"}, (
            f"recommender returned {result['recommended']!r} for "
            f"fanout={fanout} adversarial={adversarial} consensus={cons}"
        )

    # Still selectable: with the Workflow tool available, ultracode remains a reachable
    # alternative for a broad independent fan-out — never the recommendation.
    overlap = LIFECYCLE.recommend_execution_backend(
        file_count=30,
        phase_count=6,
        needs_consensus=True,
        consensus_is_gated=False,
        broad_independent_fanout=True,
        workflow_available=True,
    )
    assert "cc-workflows-ultracode" in overlap["alternatives"]
    assert overlap["recommended"] != "cc-workflows-ultracode"


# --- Sub-part B: docs/workflows/ is the write-path convention (P-D3) ------------------


_ARTIFACT_IN_PLANS_RE = re.compile(r"docs/plans/[^\s`'\"]*(-spec\.json|\.workflow\.js)")


def _plugin_markdown_guard_files() -> list[Path]:
    # Review F18: scan every markdown file under plugins/ — the earlier six-path
    # allowlist let saga-spec.md escape. Changelogs are history, never live
    # conventions, so they are excluded.
    return [p for p in sorted((ROOT / "plugins").rglob("*.md")) if p.name != "CHANGELOG.md"]


def test_no_live_write_path_convention_targets_docs_plans_for_artifacts() -> None:
    for path in _plugin_markdown_guard_files():
        text = path.read_text(encoding="utf-8")
        assert not _ARTIFACT_IN_PLANS_RE.search(text), (
            f"{path.relative_to(ROOT)} still points generated artifacts at docs/plans/"
        )


def test_no_docs_plans_pointer_resolves_to_a_moved_artifact() -> None:
    # Review F17 (inverted): rather than spot-checking one of forty-one pointers, fail
    # on ANY docs/plans artifact reference whose target moved to docs/workflows/ — a
    # stale pointer is a reference migration the move owed. Relational, never a count.
    name_re = re.compile(r"docs/plans/([A-Za-z0-9._-]+(?:-spec\.json|\.workflow\.js))")
    scanned = [
        *_plugin_markdown_guard_files(),
        *sorted((ROOT / "plugins").rglob("*.py")),
    ]
    stale: list[tuple[Path, str]] = []
    for path in scanned:
        for name in name_re.findall(path.read_text(encoding="utf-8")):
            if (ROOT / "docs" / "workflows" / name).is_file():
                stale.append((path.relative_to(ROOT), name))
    assert not stale, f"stale docs/plans pointers to moved artifacts: {stale}"


def test_artifacts_moved_and_plans_directory_retained() -> None:
    plans = ROOT / "docs" / "plans"
    workflows = ROOT / "docs" / "workflows"

    assert not list(plans.glob("*.workflow.js")), "top-level .workflow.js left in docs/plans/"
    assert not list(plans.glob("*-spec.json")), "top-level -spec.json left in docs/plans/"

    assert workflows.is_dir(), "docs/workflows/ missing"
    assert list(workflows.glob("*.workflow.js")), "no .workflow.js landed in docs/workflows/"
    assert list(workflows.glob("*-spec.json")), "no -spec.json landed in docs/workflows/"
    # Same-stem pairing survived the move for every spec that carries an emitted sibling.
    specs = {p.name.removesuffix("-spec.json") for p in workflows.glob("*-spec.json")}
    scripts = {p.name.removesuffix(".workflow.js") for p in workflows.glob("*.workflow.js")}
    assert specs <= scripts, "a spec lost its emitted sibling in the move"

    # docs/plans/ is still the plan-doc home (plan docs and the ideation subtree stay).
    assert list(plans.glob("*-plan.md")), "plan docs disappeared from docs/plans/"
    assert (plans / "plugin-fleet-ideation-2026-07-03").is_dir(), "ideation subtree moved"


def test_live_references_to_moved_artifacts_resolve() -> None:
    # Live pointers — code AND prose — must resolve on disk. Cycle 2 narrowed this
    # scan to Python because the spec doc's worked example named an artifact that
    # never existed; the worked example now points at a real artifact (review
    # D05/T03), so markdown is back in the scan with no exemption. Changelogs are
    # history, never live conventions.
    scanned = [*_plugin_markdown_guard_files(), *sorted((ROOT / "plugins").rglob("*.py"))]
    full_re = re.compile(r"docs/workflows/[A-Za-z0-9._-]+(?:-spec\.json|\.workflow\.js)")
    references = {
        rel for path in scanned for rel in full_re.findall(path.read_text(encoding="utf-8"))
    }
    assert references, "no live pointer to a moved artifact found — the scan drifted"
    for rel in references:
        assert (ROOT / rel).is_file(), f"dangling pointer to {rel}"


# --- Sub-part C: the emitter lives in the cc-workflows plugin --------------------------


def test_emitter_module_lives_in_the_cc_workflows_plugin() -> None:
    assert EMITTER_PATH.is_file(), "extracted emitter missing from the cc-workflows plugin"
    assert not (SAGA_SCRIPTS / "workflow_emitter.py").exists(), (
        "workflow_emitter.py was not moved out of Saga"
    )
    assert (CC_WORKFLOWS_SCRIPTS / "workflow_emitter.py").is_file(), (
        "the lease-contract CLI did not land in the cc-workflows plugin"
    )


def test_workflow_backend_still_emits_from_spec_against_the_extracted_emitter() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    script = EMITTER.emit_workflow_script(spec, environment={})
    # A runnable control-flow script: both units dispatched through the agent harness,
    # dependency barrier intact.
    assert "U1" in script and "U2" in script
    assert "agent(" in script
    assert "await " in script


def test_saga_delegation_produces_the_same_script_as_the_extracted_emitter() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    via_contract = ES.emit_workflow_script(spec, environment={})
    direct = EMITTER.emit_workflow_script(spec, environment={})
    assert via_contract == direct, (
        "Saga's typed integration contract and the extracted emitter disagree"
    )


def test_saga_keeps_the_integration_contract_and_not_the_detailed_protocol() -> None:
    plan_skill = PLAN_SKILL.read_text(encoding="utf-8")
    work_skill = WORK_SKILL.read_text(encoding="utf-8")

    # Recognise the backend, record the explicit selection, gate availability, consume
    # the structured result.
    assert "cc-workflows-ultracode" in plan_skill
    assert "--orchestration-mode cc-workflows-ultracode" in plan_skill
    assert "cc-workflows-ultracode" in work_skill
    assert "spec-check" in work_skill
    assert "execution_spec.py settlement" in work_skill

    # The detailed authoring protocol and the lease-retirement commentary live with the
    # capability now, not in Saga's skill files.
    assert "Step 2 — Author thin per-unit prompts" not in plan_skill
    assert "retired admission" not in work_skill
    plugin_skill = PLUGIN_SKILL.read_text(encoding="utf-8")
    protocol = PLUGIN_PROTOCOL.read_text(encoding="utf-8")
    assert "Step 2 — Author thin per-unit prompts" in plugin_skill
    assert "retired admission" in protocol


def test_team_and_outcome_paths_still_resolve_the_spec_schema_from_saga() -> None:
    team_emitter = _load_module("team_emitter", SAGA_SCRIPTS / "team_emitter.py")
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    markdown = team_emitter.emit_team_structure(spec)
    assert "## Team Structure" in markdown

    outcome_spec = _load_module("outcome_spec", SAGA_SCRIPTS / "outcome_spec.py")
    # The outcome house mirrors the sandbox vocabulary from execution_spec; the mirror
    # still matches after the extraction.
    assert outcome_spec.MUTATION_POLICIES == ES.MUTATION_POLICIES
    assert outcome_spec.WORKSPACE_ISOLATIONS == ES.WORKSPACE_ISOLATIONS
    assert outcome_spec.SANDBOX_PROFILES == ES.SANDBOX_PROFILES


# --- Sub-part D: the lease close-out blocks are fresh-shell self-contained (A01/U01) ---


def _work_skill_bash_blocks() -> list[str]:
    return re.findall(r"```bash\n(.*?)```", WORK_SKILL.read_text(encoding="utf-8"), re.DOTALL)


def test_every_scripts_dir_consumer_block_assigns_the_scripts_dir() -> None:
    # Review A01/U01: an agent runs each fenced block in a NEW shell, so a block that
    # consumes $CC_WORKFLOWS_SCRIPTS_DIR must carry its own assignment before the first
    # use — the pre-submit block's assignment is out of scope after the Workflow tool
    # returns. Removing the repeated assignment from the release or renew block fails
    # here, which is the regression the cycle-1 repair introduced.
    consumers = [b for b in _work_skill_bash_blocks() if "$CC_WORKFLOWS_SCRIPTS_DIR" in b]
    assert consumers, "scan drifted: no fenced block consumes the scripts-dir variable"
    for block in consumers:
        before_first_use, _, _ = block.partition("$CC_WORKFLOWS_SCRIPTS_DIR")
        assert "CC_WORKFLOWS_SCRIPTS_DIR=" in before_first_use, (
            "a fenced block consumes $CC_WORKFLOWS_SCRIPTS_DIR without assigning it — "
            "in a fresh shell the expansion is empty and the lease protocol never closes"
        )


def test_release_and_renew_blocks_resolve_in_a_fresh_shell() -> None:
    # Review A01/U01, proven the way the defect actually bites: run the release and
    # renew blocks AS WRITTEN in a fresh bash that never ran the pre-submit block,
    # substituting only the invocation-id placeholder and stripping every inherited
    # variable. The scripts-dir variable must resolve to the real lease CLI — proven
    # by the CLI's own loud HALT on the absent metadata file; an unresolved variable
    # dies as python's "can't open file '/workflow_emitter.py'" instead.
    placeholder = "<the invocation id recorded in the saga tick for this launch>"
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"CC_WORKFLOWS_SCRIPTS_DIR", "CLAUDE_CODE_SESSION_ID"}
        and not key.startswith("WORKFLOW_")
    }
    for verb in ("release", "renew"):
        block = next(b for b in _work_skill_bash_blocks() if f'workflow_emitter.py" {verb}' in b)
        invocation_id = f"cp918-fresh-shell-{uuid.uuid4().hex}"
        script = block.replace(placeholder, invocation_id)
        proc = subprocess.run(  # nosec B603 - a literal block from the shipped skill
            ["bash", "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert "can't open file" not in proc.stderr, (
            f"the {verb} block's scripts-dir variable expanded empty in a fresh shell"
        )
        assert proc.returncode == 2 and "workflow-lease: HALT" in proc.stderr, (
            f"the {verb} block did not reach the real lease CLI in a fresh shell: "
            f"rc={proc.returncode}, stderr={proc.stderr!r}"
        )
        assert invocation_id in proc.stderr, (
            f"the {verb} block did not re-derive the lease-metadata path from the "
            "invocation id it re-established"
        )
