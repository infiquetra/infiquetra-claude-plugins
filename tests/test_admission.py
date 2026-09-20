"""Tests for the admission questionnaire (issue #1023, plan U3).

Every test passes an explicit ``tmp_path`` store root and an explicit repository root. Nothing here
may create or modify anything under the primary checkout's ``.claude/saga/`` store, and nothing
here reaches the network: the card validator and the staffing component are injected.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "plugins" / "saga" / "scripts"
LIVE_PROFILE = REPO_ROOT / ".saga-profile.json"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def adm() -> ModuleType:
    return _load("admission")


@pytest.fixture
def store(tmp_path: Path) -> Path:
    root = tmp_path / "store" / "runs"
    root.mkdir(parents=True)
    return root


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    root.mkdir()
    return root


def _good_card() -> str:
    return "\n".join(
        [
            "### Objective",
            "One JSON run record per issue.",
            "### Intent",
            "Saga keeps state in six stores.",
            "### Out-of-scope / non-goals",
            "- No board write.",
            "### Files expected to change",
            "- `plugins/saga/scripts/run_record.py`",
            "### Tests to add or update",
            "- `tests/test_run_record.py`",
            "### Context library links",
            "- coding_standards: _none_",
            "### Acceptance criteria",
            "- [ ] `uv run pytest tests/test_run_record.py -q` passes.",
            "### Verification",
            "```bash",
            "uv run pytest tests/test_run_record.py -q",
            "```",
            "### Risk",
            "medium",
        ]
    )


def _passing_validator(_body: str) -> tuple[bool, list[str]]:
    return True, []


def _failing_validator(_body: str) -> tuple[bool, list[str]]:
    return False, ["Missing required H3 sections: ['Acceptance criteria']"]


def _fake_staffing() -> SimpleNamespace:
    """A staffing component that records that it was asked."""
    calls: list[str] = []

    def roles() -> dict[str, Any]:
        return {"planner": {}, "lens_reviewer": {}}

    def resolve_role(role: str, **_kwargs: Any) -> SimpleNamespace:
        calls.append(role)
        return SimpleNamespace(vendor="claude", model="opus", effort="high")

    def lens_catalogue(**_kwargs: Any) -> tuple[dict[str, Any], None]:
        return {
            "lenses": {"correctness": {"always_on": True}, "security": {"always_on": True}},
            "strictness_ladder": {"baseline": 8.0},
        }, None

    return SimpleNamespace(
        roles=roles, resolve_role=resolve_role, lens_catalogue=lens_catalogue, calls=calls
    )


def _write_profile(repo_root: Path) -> None:
    (repo_root / ".saga-profile.json").write_text(
        json.dumps(
            {
                "schema": "repository_profile.v1",
                "concurrency_allocation": 10,
                "nonproduction_destination": "none",
                "branch_preview": False,
                "main_consumed_directly": False,
                "mechanical_tool_baseline": ["uv run ruff check ."],
                "preflight_checks": ["the plan cleared /doc-review"],
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# The card validator is a gate (plan R6)
# ---------------------------------------------------------------------------


def test_a_card_that_fails_the_validator_stops_and_names_the_missing_field(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    with pytest.raises(adm.CardNotReadyError) as excinfo:
        adm.admit(
            1023,
            "infiquetra/infiquetra-claude-plugins",
            store_root=store,
            repo_root=repo_root,
            body="### Objective\nx\n",
            validator=_failing_validator,
        )
    assert "Acceptance criteria" in str(excinfo.value)


def test_a_card_that_fails_the_validator_writes_no_record(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    with pytest.raises(adm.CardNotReadyError):
        adm.admit(
            1023,
            "infiquetra/infiquetra-claude-plugins",
            store_root=store,
            repo_root=repo_root,
            body="### Objective\nx\n",
            validator=_failing_validator,
        )
    assert list(store.glob("*.json")) == []


def test_the_real_validator_accepts_a_well_formed_card(adm: ModuleType) -> None:
    """The injected validators above must not be the only thing this is ever run against."""
    passed, errors = adm.load_card_validator()(_good_card())
    assert passed, errors


def test_only_the_first_of_the_six_issue_review_checks_is_performed(adm: ModuleType) -> None:
    block = adm.issue_review_block(card_passed=True)
    assert len(block) == 6
    assert block[adm.ISSUE_REVIEW_CHECKS[0]] == "passed"
    assert [block[check] for check in adm.ISSUE_REVIEW_CHECKS[1:]] == ["not_performed"] * 5


# ---------------------------------------------------------------------------
# Defaults are filled without a question (plan R7)
# ---------------------------------------------------------------------------


def test_every_defaultable_parameter_is_filled_without_a_question(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    _write_profile(repo_root)
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        staffing=_fake_staffing(),
    )
    run_record = _load("run_record")
    filled = {
        name
        for name in run_record.RUN_CONFIGURATION_PARAMETERS
        if record.run_configuration[name]["source"] != "unset"
    }
    # Eleven of the thirteen fill themselves; only the two the operator must choose remain.
    assert filled == set(run_record.RUN_CONFIGURATION_PARAMETERS) - {
        "unfinished_testing_response",
        "repair_custody",
    } | {"repair_custody"}
    asked = {question.key for question in outstanding}
    assert "concurrency_allocation" not in asked
    assert "mechanical_tool_baseline" not in asked
    assert "preflight_checks" not in asked


def test_each_filled_value_records_where_it_came_from(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    _write_profile(repo_root)
    record, _ = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        staffing=_fake_staffing(),
    )
    assert record.run_configuration["standard_cycle_allowance"] == {
        "value": 3,
        "chosen_by": "delivery_manager",
        "source": "lifecycle-default",
    }
    assert record.run_configuration["concurrency_allocation"]["source"] == "profile"
    assert record.run_configuration["staffing_models_and_efforts"]["source"] == "staffing"


def test_staffing_comes_from_the_component_not_a_local_table(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    staffing = _fake_staffing()
    adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        staffing=staffing,
    )
    assert sorted(staffing.calls) == ["lens_reviewer", "planner"]


def test_an_unreachable_staffing_component_degrades_to_asking_not_refusing(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    record, _ = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        staffing=None,
    )
    assert record.run_configuration["staffing_models_and_efforts"]["source"] == "unset"


def test_a_missing_profile_is_not_an_error(adm: ModuleType, store: Path, repo_root: Path) -> None:
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    assert record.run_configuration["concurrency_allocation"]["source"] == "unset"
    assert "branch_preview" in {question.key for question in outstanding}


def test_this_repositorys_own_profile_parses_and_fills_what_it_claims(adm: ModuleType) -> None:
    """The tracked `.saga-profile.json` is real configuration, so it is checked like one."""
    profile = adm.load_profile(REPO_ROOT)
    assert LIVE_PROFILE.is_file()
    assert profile["schema"] == "repository_profile.v1"
    for key in adm.PROFILE_PARAMETERS.values():
        assert key in profile, f"the tracked profile does not supply {key}"
    for key in adm.PROFILE_ADMISSION_ANSWERS:
        assert key in profile, f"the tracked profile does not supply {key}"


# ---------------------------------------------------------------------------
# The one message, asked exactly once (plan R8, R9)
# ---------------------------------------------------------------------------


def test_the_question_set_on_a_fresh_record_with_no_profile_is_the_cards_ten(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    _, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    assert [question.key for question in outstanding] == [
        "risk_tier",
        "approval_scope",
        "destination",
        "staffing_overrides",
        "lens_declaration",
        "repair_allowances",
        "unfinished_testing_response",
        "branch_preview",
        "main_consumed_directly",
        "change_shape",
    ]
    assert len(outstanding) == 10


def test_a_profile_removes_the_two_repository_facts_from_the_question_set(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    _write_profile(repo_root)
    _, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    asked = {question.key for question in outstanding}
    assert "branch_preview" not in asked
    assert "main_consumed_directly" not in asked
    assert len(outstanding) == 8


def _all_answers() -> dict[str, Any]:
    run_record = _load("run_record")
    return {
        "risk_tier": "medium",
        "risk_justification": "every other child reads this record",
        "approval_scope": dict.fromkeys(run_record.APPROVAL_CATEGORIES, "none"),
        "destination": "pr",
        "staffing_overrides": "none",
        "lens_declaration": {"always_on": ["correctness"], "conditional": []},
        "repair_allowances": {"standard": 3, "escalated": 2},
        "unfinished_testing_response": "bring the result to the operator",
        "branch_preview": False,
        "main_consumed_directly": False,
        "change_shape": "code",
    }


def test_answers_persist_and_are_not_re_asked(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    run_record = _load("run_record")
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        answers=_all_answers(),
    )
    assert outstanding == []
    run_record.save(store, record)

    _, second_pass = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    assert second_pass == []


def test_an_operator_answer_is_never_overwritten_by_a_default(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    _write_profile(repo_root)
    record, _ = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        answers={"repair_allowances": {"standard": 1, "escalated": 1}},
    )
    assert record.run_configuration["standard_cycle_allowance"] == {
        "value": 1,
        "chosen_by": "delivery_manager",
        "source": "operator",
    }


def test_answers_land_in_the_seven_approval_boundaries(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    run_record = _load("run_record")
    record, _ = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        answers={"approval_scope": dict.fromkeys(run_record.APPROVAL_CATEGORIES, "none")},
    )
    assert set(record.approval_scope) == set(run_record.APPROVAL_CATEGORIES)
    assert all(value == "none" for value in record.approval_scope.values())


def test_an_answer_that_is_not_an_admission_question_is_refused(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    run_record = _load("run_record")
    with pytest.raises(adm.AdmissionError) as excinfo:
        adm.apply_answers(run_record.RunRecord(issue=1023), {"roster_hash": "abc"})
    assert "roster_hash" in str(excinfo.value)


def test_admission_leaves_a_next_step_naming_what_happens_now(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    """A record that says nothing about the next step is a record a cold session cannot resume."""
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    assert str(len(outstanding)) in record.next_step
    assert "admission question" in record.next_step

    answered, remaining = adm.admit(
        1024,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        answers=_all_answers(),
    )
    assert remaining == []
    assert answered.next_step == "plan"


def test_admission_never_overwrites_a_next_step_a_later_step_set(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    run_record = _load("run_record")
    run_record.set_next_step(store, 1023, "U4 the spore hooks")
    record, _ = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    assert record.next_step == "U4 the spore hooks"


def test_pending_questions_are_written_onto_the_record(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    assert record.admission["pending_questions"] == [q.key for q in outstanding]


# ---------------------------------------------------------------------------
# --dry-run writes nothing (plan R9)
# ---------------------------------------------------------------------------


def test_the_rendered_summary_names_the_defaults_and_the_questions(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    _write_profile(repo_root)
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
    )
    text = adm.render(record, outstanding, None)
    assert "Filled without asking:" in text
    assert "concurrency_allocation" in text
    assert "not written (--dry-run)" in text
    assert "Questions to answer, once (8)" in text


def test_the_summary_says_so_when_nothing_is_outstanding(
    adm: ModuleType, store: Path, repo_root: Path
) -> None:
    record, outstanding = adm.admit(
        1023,
        "infiquetra/infiquetra-claude-plugins",
        store_root=store,
        repo_root=repo_root,
        body=_good_card(),
        validator=_passing_validator,
        answers=_all_answers(),
    )
    assert "Questions to answer: none" in adm.render(record, outstanding, None)


def test_dry_run_creates_no_file(
    adm: ModuleType, store: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adm, "load_card_validator", lambda: _passing_validator)
    monkeypatch.setattr(adm, "load_staffing", lambda: None)
    monkeypatch.setattr(
        adm, "fetch_issue", lambda *_a, **_k: {"number": 1023, "body": _good_card()}
    )
    exit_code = adm.main(
        [
            "--issue",
            "1023",
            "--repo",
            "infiquetra/infiquetra-claude-plugins",
            "--store-root",
            str(store),
            "--repo-root",
            str(repo_root),
            "--dry-run",
        ]
    )
    assert exit_code == 0
    assert list(store.glob("*.json")) == []


def test_a_failing_card_exits_2_from_the_command_line(
    adm: ModuleType,
    store: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(adm, "load_card_validator", lambda: _failing_validator)
    monkeypatch.setattr(adm, "load_staffing", lambda: None)
    monkeypatch.setattr(adm, "fetch_issue", lambda *_a, **_k: {"number": 1023, "body": "x"})
    exit_code = adm.main(
        [
            "--issue",
            "1023",
            "--repo",
            "infiquetra/infiquetra-claude-plugins",
            "--store-root",
            str(store),
            "--repo-root",
            str(repo_root),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Acceptance criteria" in captured.err
    assert "Traceback" not in captured.err


def test_without_dry_run_the_record_is_written_to_the_temporary_store(
    adm: ModuleType, store: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_record = _load("run_record")
    monkeypatch.setattr(adm, "load_card_validator", lambda: _passing_validator)
    monkeypatch.setattr(adm, "load_staffing", lambda: None)
    monkeypatch.setattr(
        adm, "fetch_issue", lambda *_a, **_k: {"number": 1023, "body": _good_card()}
    )
    exit_code = adm.main(
        [
            "--issue",
            "1023",
            "--repo",
            "infiquetra/infiquetra-claude-plugins",
            "--store-root",
            str(store),
            "--repo-root",
            str(repo_root),
        ]
    )
    assert exit_code == 0
    assert run_record.load(store, 1023, warn=None) is not None


# ---------------------------------------------------------------------------
# U5: the plan skill names the step it now runs
# ---------------------------------------------------------------------------


def test_the_plan_skill_names_admission_and_the_record_path(adm: ModuleType) -> None:
    """A rename of the script or the store path must not leave the instruction dangling."""
    skill = (REPO_ROOT / "plugins" / "saga" / "skills" / "plan" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "plugins/saga/scripts/admission.py" in skill
    assert "--dry-run" in skill
    assert "--answers" in skill
    assert ".claude/saga/runs/issue-<N>.json" in skill
    assert "plugins/saga/references/run-record.md" in skill


def test_the_plan_skill_forbids_inventing_an_approval_boundary_answer(adm: ModuleType) -> None:
    skill = (REPO_ROOT / "plugins" / "saga" / "skills" / "plan" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    section = skill.split("### 0.1b")[1].split("### 0.2")[0]
    assert "Never invent an answer" in section


def test_default_repo_reads_the_origin_remote(adm: ModuleType, tmp_path: Path) -> None:
    def _runner(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0, stdout="git@github.com:infiquetra/infiquetra-claude-plugins.git\n"
        )

    assert adm.default_repo(tmp_path, runner=_runner) == "infiquetra/infiquetra-claude-plugins"
