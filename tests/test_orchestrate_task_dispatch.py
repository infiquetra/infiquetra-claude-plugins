"""What a dispatched saga unit is actually told, at the moment orchestrate sends it.

The task text is the only lever this plugin has over a session it does not share a process with, so
every quiet failure it has had lands here: a command in the wrong vendor's spelling arriving as
prose, a stage stopping to ask a question in a tab nobody is watching, a builder reviewing its own
work. These exercise ``normalize_task`` directly -- it is pure, so the real function is under test
rather than a stand-in for it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "orchestrate"
    / "skills"
    / "orchestrate"
    / "scripts"
    / "orchestrate.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _unit(orchestrate: ModuleType, name: str, task: str) -> Any:
    return orchestrate.Unit(name=name, vendor="claude", task=task)


def _run(orchestrate: ModuleType, *tasks: str) -> Any:
    return orchestrate.Run(
        run_id="r",
        source="issue 1",
        base="0" * 40,
        units=[_unit(orchestrate, f"u{i}", t) for i, t in enumerate(tasks)],
    )


class TestVendorSpelling:
    def test_codex_gets_a_dollar_prefix(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task("codex", "/saga:plan docs/plans/x.md")
        assert sent.startswith("$saga:plan docs/plans/x.md")

    def test_grok_gets_a_bare_slash(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task("grok", "/saga:doc-review docs/plans/x.md")
        assert sent.startswith("/doc-review docs/plans/x.md")

    def test_prose_is_left_alone(self, orchestrate: ModuleType) -> None:
        task = "read the plan and summarise it"
        assert orchestrate.normalize_task("codex", task) == task


class TestBackendIsNotAsked:
    """Both /plan and /work offer a backend, and an offer in a background tab waits forever."""

    def test_plan_is_told_to_record_it(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task("claude", "/saga:plan docs/plans/x.md")
        assert "already decided: inline" in sent
        assert "frontmatter" in sent

    def test_work_is_told_it_is_already_in_the_plan(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task("claude", "/saga:work docs/plans/x.md")
        assert "already decided: inline" in sent

    def test_a_review_stage_is_told_nothing_about_backends(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task("claude", "/saga:doc-review docs/plans/x.md")
        assert "already decided" not in sent


class TestTheVendorMappingSaysWhatTheVendorDoes:
    """Every entry here was wrong on a live machine until it was checked against the tool itself.

    Deliberately asserted against the tables rather than the filesystem: the two escapes this plugin
    has had were both a green local run on a machine that happened to have the thing installed.
    """

    def test_asking_muse_for_the_constrained_mode_does_not_get_bypass(
        self, orchestrate: ModuleType
    ) -> None:
        """`--yolo` disables approval *and* the sandbox, so it was never the constrained mode."""
        muse = orchestrate.VENDOR_PERMISSION["muse"]
        assert muse["auto"] != muse["bypass"]
        assert "--yolo" not in muse["auto"]
        assert "--yolo" in muse["bypass"]

    def test_qwen_can_actually_escalate(self, orchestrate: ModuleType) -> None:
        """`--yolo` is absent from `qwen --help` and works; qwen rejects unknown flags loudly."""
        assert orchestrate.VENDOR_PERMISSION["qwen"]["bypass"] == ["--yolo"]

    def test_qwen_is_never_given_safe_mode(self, orchestrate: ModuleType) -> None:
        """It reads like a permission flag and disables the customizations saga needs loaded."""
        for mode in orchestrate.VENDOR_PERMISSION["qwen"].values():
            assert "--safe-mode" not in mode

    def test_every_vendor_with_a_permission_entry_has_both_modes(
        self, orchestrate: ModuleType
    ) -> None:
        for vendor, modes in orchestrate.VENDOR_PERMISSION.items():
            assert set(modes) == {"auto", "bypass"}, vendor

    def test_agy_can_be_given_saga_work(self, orchestrate: ModuleType) -> None:
        """Its plugin is a symlink into the operator's own checkout, so a directory search misses it."""
        assert "agy" in orchestrate.SAGA_INSTALL
        assert orchestrate.saga_command("agy", "plan") == "/saga:plan"

    def test_every_vendor_that_can_run_saga_knows_how_to_name_it(
        self, orchestrate: ModuleType
    ) -> None:
        """An install with no syntax entry sends a command the vendor reads as prose."""
        for vendor in orchestrate.SAGA_INSTALL:
            assert vendor in orchestrate.SAGA_SYNTAX, vendor


class TestALongTaskSurvivesBeingTypedIntoAPane:
    """A task past a pane's typing limit arrives as an attachment, not an instruction.

    Measured against qwen through `herdr pane run`: 859 characters arrive as text, 1660 arrive as
    `[Pasted Content N chars]` and the agent answers "I'm not sure what you'd like me to do with
    it." The unit then sits idle, `settle` marks it done, and only `land` notices it committed
    nothing — a phase later.
    """

    def test_a_short_task_is_typed_verbatim(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        unit = orchestrate.Unit(name="u", vendor="qwen", task="x")
        assert orchestrate.pane_text(unit, "/plan do the thing") == "/plan do the thing"

    def test_a_long_task_is_replaced_by_something_a_pane_will_carry(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        unit = orchestrate.Unit(name="u", vendor="qwen", task="x")
        long_task = "/plan " + ("word " * 400)
        typed = orchestrate.pane_text(unit, long_task)
        assert len(typed) <= orchestrate.PANE_TYPING_LIMIT

    def test_the_whole_task_is_in_the_file_the_line_points_at(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        unit = orchestrate.Unit(name="u", vendor="qwen", task="x")
        long_task = "/plan " + ("word " * 400)
        typed = orchestrate.pane_text(unit, long_task)
        written = [w for w in typed.split() if w.endswith(".md")]
        assert written, typed
        assert Path(written[0]).read_text().strip() == long_task.strip()

    def test_the_saga_command_stays_in_the_typed_part(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Inside a file it is prose; typed, it is what makes the vendor load the skill."""
        monkeypatch.chdir(tmp_path)
        unit = orchestrate.Unit(name="u", vendor="qwen", task="x")
        typed = orchestrate.pane_text(unit, "/work " + ("word " * 400))
        assert typed.startswith("/work ")

    def test_the_handover_is_recorded_on_the_unit(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        unit = orchestrate.Unit(name="u", vendor="qwen", task="x")
        orchestrate.pane_text(unit, "/plan " + ("word " * 400))
        assert "too long to type" in unit.note


class TestAUnitNeverBlocksOnAQuestion:
    """Saga names four known-set choices; pre-answering one left the other three to hang a run.

    A `/plan` unit stopped on the destination question minutes into a live run, in a background tab,
    with the rest of the run queued behind it — the same shape the backend note had already fixed
    once.
    """

    def test_every_saga_capability_is_told(self, orchestrate: ModuleType) -> None:
        for cap in ("plan", "work", "doc-review", "code-review", "qa"):
            sent = orchestrate.normalize_task("claude", f"/saga:{cap} x")
            assert "unattended" in sent, cap

    def test_it_names_the_choices_saga_asks_from_a_known_set(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task("claude", "/saga:plan docs/plans/x.md")
        for choice in ("destination", "execution backend", "scope class", "resume-vs-mint"):
            assert choice in sent, choice

    def test_a_real_question_is_written_down_rather_than_guessed(
        self, orchestrate: ModuleType
    ) -> None:
        """Silently answering a question about the work is worse than stopping on it."""
        sent = orchestrate.normalize_task("claude", "/saga:work docs/plans/x.md")
        assert "do not guess" in sent
        assert "write the question into your output and stop" in sent

    def test_prose_gets_no_note(self, orchestrate: ModuleType) -> None:
        """Only a recognised saga command is rewritten; a plain prompt is left exactly alone."""
        task = "read the plan and summarise it"
        assert orchestrate.normalize_task("claude", task) == task


class TestTheBuilderDoesNotReviewItself:
    """saga's /work calls /code-review as its own pre-PR gate, which under orchestration is a
    self-review -- and its §5.3 block on P0/P1 exits only through an operator override, i.e. a
    question in a background tab."""

    def test_suppressed_when_the_run_reviews_separately(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task(
            "claude", "/saga:work docs/plans/x.md", review_elsewhere=True
        )
        assert "Skip the Phase 5 code-review gate" in sent

    def test_left_alone_when_there_is_no_review_phase(self, orchestrate: ModuleType) -> None:
        """Without a review phase the in-loop gate is the only review there is."""
        sent = orchestrate.normalize_task("claude", "/saga:work docs/plans/x.md")
        assert "Skip the Phase 5 code-review gate" not in sent

    def test_the_reviewer_is_never_told_to_skip_reviewing(self, orchestrate: ModuleType) -> None:
        sent = orchestrate.normalize_task(
            "grok", "/saga:code-review the build", review_elsewhere=True
        )
        assert "Skip the Phase 5 code-review gate" not in sent


class TestRunSeesItsOwnReviewPhase:
    def test_true_when_a_unit_reviews_code(self, orchestrate: ModuleType) -> None:
        run = _run(orchestrate, "/saga:work docs/plans/x.md", "/saga:code-review the build")
        assert run.reviews_separately() is True

    def test_true_in_another_vendors_spelling(self, orchestrate: ModuleType) -> None:
        run = _run(orchestrate, "$saga:code-review the build")
        assert run.reviews_separately() is True

    def test_false_when_only_the_document_is_reviewed(self, orchestrate: ModuleType) -> None:
        run = _run(orchestrate, "/saga:work docs/plans/x.md", "/saga:doc-review docs/plans/x.md")
        assert run.reviews_separately() is False


class TestASessionIsReadyBeforeItIsSent:
    """The wrapper returns when the tab exists, which is earlier than the agent can read anything.

    Sending into that gap does not fail — `herdr agent prompt` reports success, the agent finishes
    booting, and the prompt is gone. Three times across two vendors on one live run.
    """

    def test_it_waits_for_the_agent_to_say_it_is_ready(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unit = orchestrate.Unit(name="u", vendor="agy", task="x", pane_id="w1:p1")
        answers = [
            [{"pane_id": "w1:p1", "interactive_ready": None}],
            [{"pane_id": "w1:p1", "interactive_ready": None}],
            [{"pane_id": "w1:p1", "interactive_ready": True}],
        ]
        monkeypatch.setattr(orchestrate, "live_agents", lambda: answers.pop(0) if answers else [])
        monkeypatch.setattr(orchestrate.time, "sleep", lambda _s: None)

        assert orchestrate.await_ready(unit, seconds=30) is True
        assert answers == [], "should have polled until the agent said it was ready"

    def test_it_gives_up_for_an_agent_that_never_reports_readiness(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """qwen never reports it, which is why `say` has a pane fallback — do not hang on it."""
        unit = orchestrate.Unit(name="u", vendor="qwen", task="x", pane_id="w1:p1")
        monkeypatch.setattr(
            orchestrate, "live_agents", lambda: [{"pane_id": "w1:p1", "interactive_ready": None}]
        )
        monkeypatch.setattr(orchestrate.time, "sleep", lambda _s: None)

        assert orchestrate.await_ready(unit, seconds=2) is False

    def test_a_session_that_started_working_counts_as_delivered(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unit = orchestrate.Unit(name="u", vendor="agy", task="x", pane_id="w1:p1")
        monkeypatch.setattr(
            orchestrate, "live_agents", lambda: [{"pane_id": "w1:p1", "agent_status": "working"}]
        )
        monkeypatch.setattr(orchestrate.time, "sleep", lambda _s: None)

        assert orchestrate.took_the_task(unit, seconds=2) is True

    def test_a_session_still_idle_after_being_sent_is_not_delivered(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The observed failure: idle right after launch, having consumed nothing."""
        unit = orchestrate.Unit(name="u", vendor="agy", task="x", pane_id="w1:p1")
        monkeypatch.setattr(
            orchestrate, "live_agents", lambda: [{"pane_id": "w1:p1", "agent_status": "idle"}]
        )
        monkeypatch.setattr(orchestrate.time, "sleep", lambda _s: None)

        assert orchestrate.took_the_task(unit, seconds=2) is False

    def test_an_unknown_pane_is_not_delivered(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unit = orchestrate.Unit(name="u", vendor="agy", task="x", pane_id="w1:p1")
        monkeypatch.setattr(orchestrate, "live_agents", lambda: [])
        monkeypatch.setattr(orchestrate.time, "sleep", lambda _s: None)

        assert orchestrate.took_the_task(unit, seconds=2) is False
