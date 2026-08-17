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
