"""The lifecycle's issue comment is rendered, and it has to actually be posted.

For a long time `work/SKILL.md` §4.3 said only "render and hand the comment to mission-control",
which is prose with no command in it — so nothing ran. Two complete lifecycles merged and closed
with **zero comments** on their issues, and GitHub's own auto-close from the pull request stood in
for the update the whole time.

Everything else had been built: the op is in the certificate allowlist, `board_progression` stamps an
idempotency marker into the body, and mission-control's `issue comment` verb performs the write. The
only missing piece was the instruction to run it, so what is pinned here is that the instruction
exists and still names something real.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"

OP = "issue-progress-comment"


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL.read_text()


@pytest.fixture(scope="module")
def certificate() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_reversibility_certificate", SCRIPTS / "reversibility_certificate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(module)
    return module


def test_the_phase_comment_step_names_a_command(skill_text: str) -> None:
    """Rendering is not posting. A sentence about handing it over is not a step."""
    assert OP in skill_text, "§4.3 must name the op that posts the comment"
    assert "reconcile_controller.py reconcile" in skill_text


def test_the_op_it_names_is_a_real_allowlisted_operation(certificate: ModuleType) -> None:
    """Guards the other direction: a renamed op would leave §4.3 quietly pointing at nothing."""
    kinds = {str(k) for k in certificate.OpKind}
    assert OP in kinds


def test_that_op_needs_no_operator_prompt(certificate: ModuleType) -> None:
    """A phase comment that waits for an operator is the same stall in a different costume."""
    facts = certificate._REGISTRY[certificate.OpKind.ISSUE_PROGRESS_COMMENT]
    assert facts.always_operator is False


def test_it_is_routed_through_the_ledger_rather_than_the_bare_verb(skill_text: str) -> None:
    """`issue comment` is a plain POST — its docstring puts idempotency on the caller, and
    orchestrate retries units by design."""
    section = skill_text.split("### 4.3")[1].split("### 4.4")[0]
    assert "reconcile_controller.py" in section
    assert "idempotency" in section


PLAN_SKILL = ROOT / "plugins" / "saga" / "skills" / "plan" / "SKILL.md"

# The operations board's ladder, read from the live project rather than assumed.
LADDER = ["Idea", "Shaping", "Ready", "Active", "Verify", "Done"]


@pytest.fixture(scope="module")
def plan_text() -> str:
    return PLAN_SKILL.read_text()


class TestTheCardMovesAtPhaseBoundaries:
    """A card that only moves at merge says nothing while nine units build against it.

    `set-field-status` was always reversible, prompt-free, and keyed by target state — so moving the
    card mid-lifecycle needed no new machinery, only the instruction. Same shape as the phase comment
    that was rendered and never posted.
    """

    def test_planning_moves_the_card_to_shaping_and_then_ready(self, plan_text: str) -> None:
        assert "--target-state Shaping" in plan_text
        assert "--target-state Ready" in plan_text

    def test_building_moves_the_card_to_active_and_then_verify(self, skill_text: str) -> None:
        assert "--target-state Active" in skill_text
        assert "--target-state Verify" in skill_text

    def test_done_is_still_owned_by_the_post_merge_path(self, skill_text: str) -> None:
        """Phase 4.4 has always driven Done; the new moves must not duplicate it."""
        assert "--target-state Done" in skill_text
        assert skill_text.count("--target-state Done") == 1

    def test_every_state_named_is_on_the_real_board_ladder(
        self, skill_text: str, plan_text: str
    ) -> None:
        """A typo'd state is a silent no-op, not an error."""
        import re

        named = set(re.findall(r"--target-state (\w+)", skill_text + plan_text))
        assert named <= set(LADDER), named - set(LADDER)

    def test_a_plan_with_no_issue_does_not_try_to_move_a_card(self, plan_text: str) -> None:
        assert "no issue" in plan_text
