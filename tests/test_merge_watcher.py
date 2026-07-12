"""merge_watcher.py tests (issue #346, U2).

Test design: a module-local ``FakeRunner`` (distinct from ``test_ship_ceremony.py``'s
``FakeGh`` and ``test_ceremony_hazards.py``'s own ``FakeRunner`` — each ceremony
module gets its own small fake per the plan) drives ``record``/``validate`` against
canned ``gh pr view`` JSON; ``watch`` is exercised entirely through its injected
``poll_source`` callable, never a runner, so the mid-poll-flip fixture is instant and
deterministic (no real ``gh`` calls, no sleeping).

Oracles:

* record — the sidecar is written with SHA/checks/review before any poll exists
  (R3); a plain re-record over an existing sidecar refuses, ``--force`` rebaselines
  (KTD7).
* validate — a clean live snapshot matching the baseline passes; each divergence
  kind (``head_moved``, ``review_regressed``, ``check_missing``, ``check_flipped``,
  ``pr_not_open``) is individually named; a missing sidecar refuses with a remedy
  naming ``record`` (KTD8).
* watch — a pass -> fail -> pass sequence across ticks still raises
  ``check_flipped`` even though the final tick is green again (R4).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
MERGE_WATCHER_PATH = ROOT / "plugins" / "saga" / "scripts" / "merge_watcher.py"


def _load_merge_watcher() -> ModuleType:
    spec = importlib.util.spec_from_file_location("merge_watcher", MERGE_WATCHER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MW = _load_merge_watcher()


def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


class FakeRunner:
    """A tiny, module-local fake ``gh pr view`` runner. Configured with a single
    canned response (or a queue of them, for multi-call tests); records every call."""

    def __init__(
        self,
        *,
        pr_view: dict[str, Any] | None = None,
        pr_view_queue: list[dict[str, Any]] | None = None,
        pr_view_fails: bool = False,
    ) -> None:
        self._pr_view = pr_view
        self._queue = list(pr_view_queue) if pr_view_queue is not None else None
        self._pr_view_fails = pr_view_fails
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        self.calls.append(list(cmd))
        args = list(cmd)[1:]  # drop leading "gh"
        assert args[:2] == ["pr", "view"], f"unhandled fake gh call: {args!r}"
        if self._pr_view_fails:
            return _fail("pr view failed")
        if self._queue is not None:
            payload = self._queue.pop(0)
        else:
            assert self._pr_view is not None
            payload = self._pr_view
        return _ok(json.dumps(payload))


def _raw_pr_view(
    *,
    number: int = 101,
    state: str = "OPEN",
    head_sha: str = "sha-aaa",
    checks: dict[str, str] | None = None,
    review_decision: str | None = "APPROVED",
) -> dict[str, Any]:
    checks = checks if checks is not None else {"lint": "SUCCESS", "tests": "SUCCESS"}
    return {
        "number": number,
        "state": state,
        "headRefOid": head_sha,
        "statusCheckRollup": [
            {"name": name, "conclusion": conclusion} for name, conclusion in checks.items()
        ],
        "reviewDecision": review_decision,
    }


# --------------------------------------------------------------------------- #
# record — R3, KTD1
# --------------------------------------------------------------------------- #


def test_records_expectation_at_open(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    expectation = MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    assert expectation["pr_number"] == 101
    assert expectation["head_sha"] == "sha-aaa"
    assert expectation["required_checks"] == ["lint", "tests"]
    assert expectation["review_state"] == "APPROVED"
    assert "recorded_at" in expectation

    path = MW.sidecar_path(tmp_path, "issue-346")
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk == expectation


def test_record_without_force_refuses_over_existing_sidecar(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)
    with pytest.raises(MW.MergeExpectationAlreadyRecordedError):
        MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)


def test_record_force_rebaselines(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(head_sha="sha-aaa"))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    runner2 = FakeRunner(pr_view=_raw_pr_view(head_sha="sha-bbb"))
    expectation = MW.record(
        saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner2, force=True
    )
    assert expectation["head_sha"] == "sha-bbb"

    on_disk = json.loads(MW.sidecar_path(tmp_path, "issue-346").read_text())
    assert on_disk["head_sha"] == "sha-bbb"


# --------------------------------------------------------------------------- #
# validate — R4, KTD8
# --------------------------------------------------------------------------- #


def test_validate_matches_clean_state_passes(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view())
    expectation = MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert expectation["head_sha"] == "sha-aaa"


def test_missing_expectation_refuses_with_remedy(tmp_path: Path) -> None:
    with pytest.raises(MW.MergeExpectationMissingError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=FakeRunner())
    assert "issue-346" in str(excinfo.value)
    assert "record" in excinfo.value.remedy


def test_head_moved_divergence_named(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(head_sha="sha-aaa"))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(head_sha="sha-ccc"))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "head_moved"


def test_review_regressed_divergence_named(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(review_decision="APPROVED"))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(review_decision="CHANGES_REQUESTED"))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "review_regressed"


def test_check_missing_divergence_named(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "tests": "SUCCESS"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS"}))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "check_missing"
    assert "tests" in excinfo.value.detail["missing_checks"]


def test_check_flipped_divergence_named(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "tests": "SUCCESS"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "tests": "FAILURE"}))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "check_flipped"
    assert "tests" in excinfo.value.detail["non_passing_checks"]


def test_pr_not_open_divergence_named(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(state="OPEN"))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(state="CLOSED"))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "pr_not_open"


def test_validate_probe_failure_raises(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    with pytest.raises(MW.MergeWatcherError):
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=FakeRunner(pr_view_fails=True))


# --------------------------------------------------------------------------- #
# watch — R4, injectable poll source, no sleeping
# --------------------------------------------------------------------------- #


def _normalized(**overrides: Any) -> dict[str, Any]:
    base = {
        "pr_number": 101,
        "state": "OPEN",
        "head_sha": "sha-aaa",
        "checks": {"lint": True, "tests": True},
        "review_state": "APPROVED",
    }
    base.update(overrides)
    return base


def test_midpoll_check_flip_blocks_merge(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "tests": "SUCCESS"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    ticks = [
        _normalized(checks={"lint": True, "tests": True}),  # pass
        _normalized(checks={"lint": True, "tests": False}),  # flip
        _normalized(checks={"lint": True, "tests": True}),  # recovered — still blocks
    ]

    def poll_source(tick: int) -> dict[str, Any]:
        return ticks[tick]

    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=3)
    assert excinfo.value.kind == "check_flipped"
    assert excinfo.value.tick == 1


def test_watch_all_ticks_clean_passes(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    def poll_source(tick: int) -> dict[str, Any]:
        return _normalized()

    result = MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=3)
    assert result["ticks"] == 3


def test_watch_head_moved_raises_immediately(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(head_sha="sha-aaa"))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    calls: list[int] = []

    def poll_source(tick: int) -> dict[str, Any]:
        calls.append(tick)
        return _normalized(head_sha="sha-moved")

    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=5)
    assert excinfo.value.kind == "head_moved"
    # Raised on the first tick — no reason to poll further ticks.
    assert calls == [0]


def test_watch_missing_expectation_refuses(tmp_path: Path) -> None:
    with pytest.raises(MW.MergeExpectationMissingError):
        MW.watch(
            saga_id="issue-346",
            repo_root=tmp_path,
            poll_source=lambda tick: _normalized(),
            ticks=2,
        )


def test_watch_rejects_zero_ticks(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)
    with pytest.raises(MW.MergeWatcherError):
        MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=lambda tick: {}, ticks=0)


def test_watch_never_sleeps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No sleeping in library code (module docstring) — watch()'s own loop must
    never call time.sleep even across multiple ticks."""
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    def _boom(_seconds: float) -> None:
        raise AssertionError("watch() must not sleep")

    monkeypatch.setattr(MW.time, "sleep", _boom)

    def poll_source(tick: int) -> dict[str, Any]:
        return _normalized()

    MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=4)


# --------------------------------------------------------------------------- #
# sidecar path shape (KTD1)
# --------------------------------------------------------------------------- #


def test_sidecar_path_matches_ktd1_layout(tmp_path: Path) -> None:
    path = MW.sidecar_path(tmp_path, "issue-346")
    assert path == tmp_path / ".claude" / "saga" / "sagas" / "issue-346" / "merge_expectation.json"


@pytest.mark.parametrize("bad_id", ["../evil", "..", "a/b", "-x", "", "/abs"])
def test_sidecar_path_rejects_unsafe_saga_id(tmp_path: Path, bad_id: str) -> None:
    """saga_id is a path component — traversal or option-like values refuse loud
    before any filesystem or gh access (code-review F2)."""
    with pytest.raises(MW.MergeWatcherError):
        MW.sidecar_path(tmp_path, bad_id)


def test_record_rejects_unsafe_saga_id_before_gh(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    with pytest.raises(MW.MergeWatcherError):
        MW.record(saga_id="../evil", pr_number=101, repo_root=tmp_path, runner=runner)
    assert runner.calls == []


def test_nonnumeric_pr_number_refused_before_gh(tmp_path: Path) -> None:
    """A pr_number that isn't a plain number never reaches gh argv (code-review F3)."""
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)
    probe = FakeRunner(pr_view=_raw_pr_view())
    with pytest.raises(MW.MergeWatcherError, match="not a plain PR number"):
        MW.validate(saga_id="issue-346", repo_root=tmp_path, pr_number="101 --repo x", runner=probe)
    assert probe.calls == []


def test_corrupt_sidecar_is_named_refusal(tmp_path: Path) -> None:
    """A truncated/garbled sidecar surfaces as MergeWatcherError, never a raw
    JSONDecodeError traceback (code-review F6)."""
    path = MW.sidecar_path(tmp_path, "issue-346")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(MW.MergeWatcherError, match="not valid JSON"):
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=FakeRunner())


def test_sidecar_write_is_atomic_no_tmp_left(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)
    path = MW.sidecar_path(tmp_path, "issue-346")
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


# --------------------------------------------------------------------------- #
# watch — remaining divergence kinds at the watch() level
# --------------------------------------------------------------------------- #


def test_watch_pr_not_open_raises_immediately(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view())
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    calls: list[int] = []

    def poll_source(tick: int) -> dict[str, Any]:
        calls.append(tick)
        return _normalized(state="MERGED")

    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=4)
    assert excinfo.value.kind == "pr_not_open"
    assert calls == [0]


def test_watch_check_missing_raises_immediately(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "tests": "SUCCESS"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    def poll_source(tick: int) -> dict[str, Any]:
        return _normalized(checks={"lint": True})  # "tests" vanished from the rollup

    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=3)
    assert excinfo.value.kind == "check_missing"
    assert excinfo.value.detail["missing_checks"] == ["tests"]


def test_watch_review_regressed_on_final_tick(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(review_decision="APPROVED"))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    def poll_source(tick: int) -> dict[str, Any]:
        return _normalized(review_state="CHANGES_REQUESTED")

    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.watch(saga_id="issue-346", repo_root=tmp_path, poll_source=poll_source, ticks=2)
    assert excinfo.value.kind == "review_regressed"
    assert excinfo.value.tick == 1


# --------------------------------------------------------------------------- #
# check_flipped semantics — R4-literal: only a recorded-PASSING check can flip
# (dogfood-caught on PR #562: a conditionally-SKIPPED workflow, non-passing at
# record time and still non-passing at merge, must not read as a flip)
# --------------------------------------------------------------------------- #


def test_validate_tolerates_recorded_nonpassing_check_still_nonpassing(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "publish": "SKIPPED"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "publish": "SKIPPED"}))
    expectation = MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert expectation["checks"] == {"lint": True, "publish": False}


def test_validate_flips_only_on_recorded_passing_regression(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "publish": "SKIPPED"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "FAILURE", "publish": "SKIPPED"}))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "check_flipped"
    # Only the genuine passing->non-passing regression is named; the baseline
    # non-passing check is not.
    assert excinfo.value.detail["non_passing_checks"] == ["lint"]


def test_validate_recorded_nonpassing_check_may_improve(tmp_path: Path) -> None:
    runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "publish": "SKIPPED"}))
    MW.record(saga_id="issue-346", pr_number=101, repo_root=tmp_path, runner=runner)

    live_runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "publish": "SUCCESS"}))
    expectation = MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert expectation["pr_number"] == 101


def test_legacy_sidecar_without_checks_map_stays_strict(tmp_path: Path) -> None:
    """A pre-map sidecar carries only required_checks names — the fallback treats
    them all as recorded-passing (old strict behavior), so upgrading the module
    never silently weakens an existing baseline."""
    path = MW.sidecar_path(tmp_path, "issue-346")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pr_number": 101,
                "head_sha": "sha-aaa",
                "required_checks": ["lint", "publish"],
                "review_state": "APPROVED",
                "recorded_at": "2026-07-11T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    live_runner = FakeRunner(pr_view=_raw_pr_view(checks={"lint": "SUCCESS", "publish": "SKIPPED"}))
    with pytest.raises(MW.MergeExpectationDivergedError) as excinfo:
        MW.validate(saga_id="issue-346", repo_root=tmp_path, runner=live_runner)
    assert excinfo.value.kind == "check_flipped"
    assert excinfo.value.detail["non_passing_checks"] == ["publish"]


# --------------------------------------------------------------------------- #
# legacy StatusContext shape (context/state instead of name/conclusion)
# --------------------------------------------------------------------------- #


def test_normalize_handles_legacy_status_context_shape() -> None:
    """gh's statusCheckRollup mixes CheckRun (name/conclusion) and legacy
    StatusContext (context/state) entries — both shapes must normalize
    (code-review F8)."""
    raw = {
        "number": 101,
        "state": "OPEN",
        "headRefOid": "sha-aaa",
        "statusCheckRollup": [
            {"name": "tests", "conclusion": "SUCCESS"},
            {"context": "ci/legacy-build", "state": "SUCCESS"},
            {"context": "ci/legacy-flaky", "state": "FAILURE"},
        ],
        "reviewDecision": "APPROVED",
    }
    normalized = MW.normalize_pr_view(raw)
    assert normalized["checks"] == {
        "tests": True,
        "ci/legacy-build": True,
        "ci/legacy-flaky": False,
    }


# --------------------------------------------------------------------------- #
# CLI boundary — record/validate/watch through main() (code-review F4)
# --------------------------------------------------------------------------- #


def _patched_live(monkeypatch: pytest.MonkeyPatch, live: dict[str, Any]) -> None:
    def _fake(pr_number: int | str, *, repo_root: Path, runner: Any) -> dict[str, Any]:
        return dict(live)

    monkeypatch.setattr(MW, "_fetch_live_state", _fake)


def test_cli_record_validate_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live = _normalized()
    _patched_live(monkeypatch, live)
    root = ["--repo-root", str(tmp_path)]

    assert MW.main([*root, "record", "--saga-id", "issue-346", "--pr-number", "101"]) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["head_sha"] == "sha-aaa"

    # Plain re-record refuses (KTD7) through the CLI with the module-prefixed message.
    assert MW.main([*root, "record", "--saga-id", "issue-346", "--pr-number", "101"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("merge_watcher:") and "already recorded" in err

    assert (
        MW.main([*root, "record", "--saga-id", "issue-346", "--pr-number", "101", "--force"]) == 0
    )
    capsys.readouterr()

    assert MW.main([*root, "validate", "--saga-id", "issue-346"]) == 0
    capsys.readouterr()

    live["head_sha"] = "sha-moved"
    assert MW.main([*root, "validate", "--saga-id", "issue-346"]) == 1
    assert "head_moved" in capsys.readouterr().err


def test_cli_watch_clean_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patched_live(monkeypatch, _normalized())
    root = ["--repo-root", str(tmp_path)]
    assert MW.main([*root, "record", "--saga-id", "issue-346", "--pr-number", "101"]) == 0
    capsys.readouterr()
    code = MW.main(
        [
            *root,
            "watch",
            "--saga-id",
            "issue-346",
            "--pr-number",
            "101",
            "--ticks",
            "2",
            "--interval-seconds",
            "0",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["ticks"] == 2


def test_cli_missing_expectation_names_remedy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = MW.main(["--repo-root", str(tmp_path), "validate", "--saga-id", "issue-346"])
    assert code == 1
    err = capsys.readouterr().err
    assert "no merge_expectation.json recorded" in err and "record --saga-id issue-346" in err
