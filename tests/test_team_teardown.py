"""U2 (#679) — team-run teardown after the lease-broker retirement.

The lease-broker retirement plan's unit U2 re-keys the #358 teardown contract off the
fleet lease authority: resources are enumerated from the per-outcome worktree
registries cross-checked with ``git worktree list`` (never a lease list), and the
disposition surface keeps its closed vocabulary — ``released`` / ``already-absent`` /
``retained`` / ``failed`` — re-keyed on worktree path instead of ``lease_id``.

These tests pin:

* the ledger event family and its transition rules (unchanged by the unwind);
* the census-based projection and the idempotent terminal driver;
* all five R5c disposition rows in their re-keyed form;
* the recovery pass re-keyed onto the git-listed liveness signal;
* **the regression sentinel: teardown removes no worktree from disk under any input**,
  which pins KTD12's finding that reclamation was never teardown's job.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(path: Path, name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # A DISTINCT sys.modules key: team_teardown.py is loaded by other test modules
    # under their own keys, and clobbering a shared key is how the full suite hands a
    # test a foreign exception class (LEARNINGS {#shared-sys-modules-key-test-collision}).
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TT = _load(SCRIPTS / "team_teardown.py", "_test_team_teardown_u2")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True, timeout=60
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repository: the census resolves its common dir and asks git directly."""

    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "seed")
    return path


def _ledger_path(repo: Path) -> Path:
    return repo / ".git" / "saga-run-facts" / "run-facts.jsonl"


def _ledger(repo: Path) -> Any:
    return TT.run_ledger.RunLedger(path=_ledger_path(repo))


def _open_run(ledger: Any, run_id: str, *, session_id: str = "session-1") -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        TT.open_run(
            ledger,
            subplot_id="u2-test",
            session_id=session_id,
            at="2026-08-05T00:00:00Z",
            team_run_id=run_id,
        ),
    )


def _register(repo: Path, outcome_id: str, subplot_id: str, path: Path) -> None:
    """Seed one registry entry the way outcome_worktrees.register would (U3's file stays untouched)."""

    store_dir = repo / ".git" / "saga-outcomes" / outcome_id
    store_dir.mkdir(parents=True, exist_ok=True)
    registry = store_dir / "worktrees.json"
    data = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
    entries = data.get("worktrees", {})
    entries[subplot_id] = {
        "path": str(path),
        "branch": f"saga-outcome-{outcome_id}-{subplot_id}",
        "repo_root": str(repo),
        "outcome_id": outcome_id,
    }
    registry.write_text(
        json.dumps({"worktrees": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _add_live_worktree(repo: Path, outcome_id: str, subplot_id: str) -> Path:
    """A worktree git really lists, registered for it — the 'retained' fixture."""

    path = repo / ".saga-worktrees" / outcome_id / subplot_id
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "--detach", str(path))
    _register(repo, outcome_id, subplot_id, path)
    return path


def _add_absent_worktree(repo: Path, outcome_id: str, subplot_id: str) -> Path:
    """Registered, but git no longer lists it — the re-defined 'already-absent' fixture."""

    path = repo / ".saga-worktrees" / outcome_id / subplot_id
    _register(repo, outcome_id, subplot_id, path)
    return path


class _Clock:
    def __init__(self, start: str = "2026-08-05T00:00:00Z") -> None:
        self.now = start

    def tick(self, to: str) -> None:
        self.now = to

    def __call__(self) -> str:
        return self.now


def _reclaim(
    repo: Path,
    run_id: str,
    *,
    adapters: Any = None,
    terminal_reason: str = "success",
    at_provider: Callable[[], str] | None = None,
    max_actions: int | None = None,
    dry_run: bool = False,
    stats: Any = None,
) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        TT.reclaim_all(
            _ledger(repo),
            adapters if adapters is not None else TT.production_adapters(repo),
            subplot_id="u2-test",
            team_run_id=run_id,
            terminal_reason=terminal_reason,
            at_provider=at_provider if at_provider is not None else _Clock(),
            repo_root=repo,
            max_actions=max_actions,
            dry_run=dry_run,
            stats=stats,
        ),
    )


# --------------------------------------------------------------------------- event family


class TestTeardownEventFamily:
    def test_valid_open_intent_attempt_result_complete_chain(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")
        projection = _reclaim(repo, "team-run-1")
        assert projection["completion_fact_ref"] is not None
        facts = TT.run_ledger.read_facts(ledger)
        events = [f["event"] for f in facts if f.get("team_run_id") == "team-run-1"]
        assert events == [
            "run-opened",
            "teardown-intent",
            "resource-attempt",
            "resource-result",
            "teardown-complete",
        ]

    def test_duplicate_identical_event_is_idempotent(self, repo: Path) -> None:
        ledger = _ledger(repo)
        opened = _open_run(ledger, "team-run-1")
        replay = TT.append_teardown_event(
            ledger,
            TT.build_run_opened(
                subplot_id="u2-test",
                at="2026-08-05T00:00:00Z",
                team_run_id="team-run-1",
                owner_id="team-run-1",
                session_id="session-1",
                root_sha256=opened["root_sha256"],
            ),
        )
        assert replay["this_hash"] == opened["this_hash"]
        facts = TT.run_ledger.read_facts(ledger)
        assert len([f for f in facts if f.get("event") == "run-opened"]) == 1

    def test_conflicting_duplicate_is_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        with pytest.raises(TT.TeardownConflictError):
            TT.append_teardown_event(
                ledger,
                TT.build_run_opened(
                    subplot_id="u2-test",
                    at="2026-08-05T00:01:00Z",
                    team_run_id="team-run-1",
                    owner_id="team-run-1",
                    session_id="session-OTHER",
                    root_sha256=TT.repository_root_sha256(ledger),
                ),
            )

    def test_attempt_without_intent_is_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(
                ledger,
                TT.build_resource_attempt(
                    subplot_id="u2-test",
                    at="2026-08-05T00:00:00Z",
                    team_run_id="team-run-1",
                    intent_id="0" * 64,
                    resource_id="/tmp/wt",
                    resource_kind="outcome-worktree",
                    generation="out-a:sub-1",
                    action="worktree-sweep",
                ),
            )

    def test_result_without_attempt_is_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        TT.append_teardown_event(
            ledger,
            TT.build_teardown_intent(
                subplot_id="u2-test",
                at="2026-08-05T00:00:00Z",
                team_run_id="team-run-1",
                terminal_reason="success",
                close_generation=1,
            ),
        )
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(
                ledger,
                TT.build_resource_result(
                    subplot_id="u2-test",
                    at="2026-08-05T00:00:01Z",
                    team_run_id="team-run-1",
                    action_key_value="f" * 64,
                    disposition="released",
                    evidence_refs=[],
                ),
            )

    def test_complete_with_retained_resource_is_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_live_worktree(repo, "out-a", "sub-live")
        projection = _reclaim(repo, "team-run-1")
        assert projection["completion_fact_ref"] is None
        assert projection["retained_count"] == 1

    def test_complete_with_dangling_attempt_is_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")
        intent = TT.append_teardown_event(
            ledger,
            TT.build_teardown_intent(
                subplot_id="u2-test",
                at="2026-08-05T00:00:00Z",
                team_run_id="team-run-1",
                terminal_reason="success",
                close_generation=1,
            ),
        )
        TT.append_teardown_event(
            ledger,
            TT.build_resource_attempt(
                subplot_id="u2-test",
                at="2026-08-05T00:00:01Z",
                team_run_id="team-run-1",
                intent_id=str(intent["intent_id"]),
                resource_id="/gone/elsewhere",
                resource_kind="outcome-worktree",
                generation="out-x:sub-x",
                action="worktree-sweep",
            ),
        )
        facts = TT.run_ledger.read_facts(ledger)
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(
                ledger,
                TT.build_teardown_complete(
                    subplot_id="u2-test",
                    at="2026-08-05T00:00:02Z",
                    team_run_id="team-run-1",
                    intent_id=str(intent["intent_id"]),
                    close_generation=1,
                    released_count=0,
                    already_absent_count=0,
                ),
            )
        assert facts == TT.run_ledger.read_facts(ledger)  # nothing appended by the refusal

    def test_partial_result_then_retry_converges_on_stable_action_key(self, repo: Path) -> None:
        repo_a = repo
        _add_live_worktree(repo_a, "out-a", "sub-1")
        ledger = _ledger(repo_a)
        _open_run(ledger, "team-run-1")

        first = _reclaim(repo_a, "team-run-1")  # git lists it -> retained, blocked terminal
        assert first["completion_fact_ref"] is None
        assert first["retained_count"] == 1

        # The worktree is removed out-of-band (an operator action, never teardown's):
        path = repo_a / ".saga-worktrees" / "out-a" / "sub-1"
        _git(repo_a, "worktree", "remove", "--force", str(path))
        second = _reclaim(repo_a, "team-run-1", at_provider=_Clock("2026-08-05T00:05:00Z"))
        assert second["completion_fact_ref"] is not None
        assert second["already_absent_count"] == 1

    def test_events_after_complete_are_refused_except_recovery_observation(
        self, repo: Path
    ) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        projection = _reclaim(repo, "team-run-1")  # zero worktrees -> completes immediately
        assert projection["completion_fact_ref"] is not None
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(
                ledger,
                TT.build_teardown_intent(
                    subplot_id="u2-test",
                    at="2026-08-05T01:00:00Z",
                    team_run_id="team-run-1",
                    terminal_reason="operator-abort",
                    close_generation=1,
                ),
            )
        TT.append_teardown_event(
            ledger,
            TT.build_recovery_observation(
                subplot_id="u2-test",
                at="2026-08-05T01:00:00Z",
                team_run_id="team-run-1",
                observed_open=0,
                actions_taken=0,
                reason_code="post-completion-honesty",
            ),
        )

    def test_unknown_kind_and_unknown_event_are_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(ledger, {"kind": "not-teardown", "event": "run-opened"})
        _open_run(ledger, "team-run-1")
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(
                ledger,
                TT.run_ledger.build_fact(
                    "teardown",
                    subplot_id="u2-test",
                    at="2026-08-05T00:00:00Z",
                    event="unknown-event",
                    team_run_id="team-run-1",
                ),
            )

    def test_bounded_ids_and_refs_are_enforced(self) -> None:
        long = "x" * 257
        with pytest.raises(TT.TeardownError):
            TT.build_run_opened(
                subplot_id="s",
                at="2026-08-05T00:00:00Z",
                team_run_id=long,
                owner_id="o",
                session_id="s",
                root_sha256="a" * 64,
            )
        with pytest.raises(TT.TeardownError):
            TT.build_resource_result(
                subplot_id="s",
                at="2026-08-05T00:00:00Z",
                team_run_id="t",
                action_key_value="b" * 64,
                disposition="released",
                evidence_refs=["ok"] * 17,
            )
        outcome = TT.ActionOutcome(disposition="released", reason_code="recovered-after-crash")
        with pytest.raises(TT.TeardownError):
            outcome.validated()  # driver-reserved bookkeeping is refused from adapters

    def test_disposition_and_action_vocabularies_stay_frozen(self) -> None:
        """The closed vocabularies survive the unwind even where a producer retired."""

        assert set(TT.DISPOSITIONS) == {"released", "already-absent", "retained", "failed"}
        assert set(TT.FINAL_DISPOSITIONS) == {"released", "already-absent"}
        assert set(TT.ACTION_KINDS) == {
            "resident-stop",
            "process-stop",
            "lease-release",
            "worktree-sweep",
        }
        assert set(TT.RESOURCE_KINDS) == {
            "resident-agent",
            "owned-subprocess",
            "outcome-worktree",
            "provisional-lease",
        }


# --------------------------------------------------------------------------- census + projection


class TestDecisionInputAndProjection:
    def test_broken_chain_refuses_decisions(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        with _ledger_path(repo).open("a", encoding="utf-8") as handle:
            handle.write('{"kind": "teardown", "corrupt": true}\n')
        with pytest.raises(TT.TeardownError, match="broken run-fact chain"):
            TT.read_decision_input(ledger, repo_root=repo)

    def test_census_enumerates_every_outcome_registry(self, repo: Path) -> None:
        _add_live_worktree(repo, "out-a", "sub-live")
        _add_absent_worktree(repo, "out-b", "sub-gone")
        decision = TT.read_decision_input(_ledger(repo), repo_root=repo)
        census = {(item["outcome_id"], item["subplot_id"]): item for item in decision.worktrees}
        assert set(census) == {("out-a", "sub-live"), ("out-b", "sub-gone")}
        assert census[("out-a", "sub-live")]["live"] is True
        assert census[("out-b", "sub-gone")]["live"] is False

    def test_census_is_empty_without_git_or_registries(self, repo: Path, tmp_path: Path) -> None:
        assert TT.read_decision_input(_ledger(repo), repo_root=repo).worktrees == ()
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        with pytest.raises(TT.TeardownError, match="cannot enumerate worktrees without git"):
            TT.read_decision_input(_ledger(repo), repo_root=plain)

    def test_malformed_registry_reads_as_empty_never_fatal(self, repo: Path) -> None:
        store_dir = repo / ".git" / "saga-outcomes" / "out-broken"
        store_dir.mkdir(parents=True)
        (store_dir / "worktrees.json").write_text("{not json", encoding="utf-8")
        _add_live_worktree(repo, "out-ok", "sub-1")
        decision = TT.read_decision_input(_ledger(repo), repo_root=repo)
        assert [item["outcome_id"] for item in decision.worktrees] == ["out-ok"]

    def test_projection_reports_open_and_disposed_resources(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_live_worktree(repo, "out-a", "sub-live")
        _add_absent_worktree(repo, "out-a", "sub-gone")
        projection = _reclaim(repo, "team-run-1")
        by_resource = {res["resource_id"]: res for res in projection["resources"]}
        live_path = str(repo / ".saga-worktrees" / "out-a" / "sub-live")
        gone_path = str(repo / ".saga-worktrees" / "out-a" / "sub-gone")
        assert by_resource[live_path]["disposition"] == "retained"
        assert by_resource[live_path]["generation"] == "out-a:sub-live"
        assert by_resource[live_path]["kind"] == "outcome-worktree"
        assert by_resource[gone_path]["disposition"] == "already-absent"
        assert projection["open_count"] == 1  # only the retained entry is unsettled
        assert projection["completion_fact_ref"] is None

    def test_projection_is_deterministic_for_one_snapshot(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_live_worktree(repo, "out-a", "sub-1")
        decision = TT.read_decision_input(ledger, repo_root=repo)
        assert TT.project(decision, "team-run-1") == TT.project(decision, "team-run-1")

    def test_open_runs_scopes_by_repository_identity(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-here")
        foreign = TT.build_run_opened(
            subplot_id="u2-test",
            at="2026-08-05T00:00:00Z",
            team_run_id="team-run-elsewhere",
            owner_id="team-run-elsewhere",
            session_id="session-1",
            root_sha256="c" * 64,
        )
        TT.append_teardown_event(ledger, foreign)
        decision = TT.read_decision_input(ledger, repo_root=repo)
        scoped = TT.open_runs(decision, root_sha256=TT.repository_root_sha256(ledger))
        assert scoped == ["team-run-here"]
        assert TT.open_runs(decision, root_sha256=None) == [
            "team-run-here",
            "team-run-elsewhere",
        ]

    def test_no_mutable_summary_exists_anywhere(self, repo: Path) -> None:
        source = (SCRIPTS / "team_teardown.py").read_text(encoding="utf-8")
        assert "open_count" in source  # derived on read, never stored
        for forbidden in ("status.json", "open_runs.json", "reclamation.db"):
            assert forbidden not in source


# --------------------------------------------------------------------------- terminal driver


class TestTerminalDriver:
    @pytest.mark.parametrize("terminal_reason", sorted(TT.TERMINAL_REASONS))
    def test_every_terminal_reason_completes_at_zero_open(
        self, repo: Path, terminal_reason: str
    ) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        projection = _reclaim(repo, "team-run-1", terminal_reason=terminal_reason)
        assert projection["completion_fact_ref"] is not None
        assert projection["terminal_reason"] == terminal_reason

    def test_live_worktree_is_a_blocked_terminal_not_a_completion(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_live_worktree(repo, "out-a", "sub-1")
        projection = _reclaim(repo, "team-run-1")
        assert projection["completion_fact_ref"] is None
        assert projection["retained_count"] == 1
        facts = TT.run_ledger.read_facts(ledger)
        assert not any(f.get("event") == "teardown-complete" for f in facts)

    def test_repeated_b8_is_idempotent(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")
        first = _reclaim(repo, "team-run-1")
        second = _reclaim(repo, "team-run-1", at_provider=_Clock("2026-08-05T01:00:00Z"))
        assert first["completion_fact_ref"] == second["completion_fact_ref"]
        facts = TT.run_ledger.read_facts(ledger)
        assert len([f for f in facts if f.get("event") == "teardown-complete"]) == 1
        assert len([f for f in facts if f.get("event") == "teardown-intent"]) == 1

    def test_action_exception_is_failed_and_blocks_completion(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")

        def _exploding(_resource: Mapping[str, Any]) -> Any:
            raise RuntimeError("adapter exploded")

        adapters = TT.ReclaimAdapters(worktree_sweep=_exploding)
        projection = _reclaim(repo, "team-run-1", adapters=adapters)
        assert projection["completion_fact_ref"] is None
        assert projection["failed_count"] == 1
        (result,) = [
            f for f in TT.run_ledger.read_facts(ledger) if f.get("event") == "resource-result"
        ]
        assert result["disposition"] == "failed"
        assert result["reason_code"] == "action-exception:RuntimeError"

    def test_request_records_intent_without_acting(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")
        recorded = TT.request(
            ledger,
            subplot_id="u2-test",
            team_run_id="team-run-1",
            terminal_reason="operator-abort",
            at="2026-08-05T00:00:00Z",
        )
        assert recorded["complete"] is False
        facts = TT.run_ledger.read_facts(ledger)
        events = [f["event"] for f in facts if f.get("team_run_id") == "team-run-1"]
        assert events == ["run-opened", "teardown-intent"]
        assert recorded["close_generation"] == 1  # the retired fence's vestigial constant

    def test_dry_run_census_changes_nothing(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_live_worktree(repo, "out-a", "sub-1")
        ledger_bytes = _ledger_path(repo).read_bytes()
        worktrees_before = _git(repo, "worktree", "list", "--porcelain")
        projection = _reclaim(repo, "team-run-1", dry_run=True)
        assert projection["completion_fact_ref"] is None
        assert _ledger_path(repo).read_bytes() == ledger_bytes
        assert _git(repo, "worktree", "list", "--porcelain") == worktrees_before

    def test_crash_orphaned_attempt_reconciles_as_already_absent(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")
        # A crashed predecessor recorded the attempt for a worktree whose registry entry
        # is now gone — the driver reconciles trusted reality instead of acting again.
        intent = TT.append_teardown_event(
            ledger,
            TT.build_teardown_intent(
                subplot_id="u2-test",
                at="2026-08-05T00:00:00Z",
                team_run_id="team-run-1",
                terminal_reason="success",
                close_generation=1,
            ),
        )
        TT.append_teardown_event(
            ledger,
            TT.build_resource_attempt(
                subplot_id="u2-test",
                at="2026-08-05T00:00:01Z",
                team_run_id="team-run-1",
                intent_id=str(intent["intent_id"]),
                resource_id="/vanished/entry-path",
                resource_kind="outcome-worktree",
                generation="out-a:sub-vanished",
                action="worktree-sweep",
            ),
        )
        projection = _reclaim(repo, "team-run-1", at_provider=_Clock("2026-08-05T00:05:00Z"))
        assert projection["completion_fact_ref"] is not None
        results = [
            f for f in TT.run_ledger.read_facts(ledger) if f.get("event") == "resource-result"
        ]
        orphan = [r for r in results if r.get("reason_code") == "recovered-after-crash"]
        assert len(orphan) == 1
        assert orphan[0]["disposition"] == "already-absent"
        assert orphan[0]["evidence_refs"] == ["reconciled:resource-absent-at-recovery"]


# --------------------------------------------------------------------------- R5c re-key


class FakeOps:
    """A duck-typed WorktreeOps double: existence is a test-controlled set."""

    def __init__(self, listed: set[str]) -> None:
        self.listed = listed

    def exists(self, path: str) -> bool:
        return path in self.listed


class TestR5cDispositionRekey:
    """All five rows of the plan's R5c table, asserted in their re-keyed form."""

    def _sweep(self, listed: set[str]) -> Any:
        return TT.make_worktree_sweep_adapter(FakeOps(listed))

    def test_rows_3_and_5_git_listed_converge_on_retained(self) -> None:
        """The sweep-retained and not-a-sweep-candidate rows: no sweep engine survives,
        so one deliberate branch reports the worktree git still lists — retained, with
        a reason code and no evidence refs (rows 3 and 5 carried none either)."""
        outcome = self._sweep({"/repo/.saga-worktrees/out-a/sub-1"})(
            {
                "outcome_id": "out-a",
                "subplot_id": "sub-1",
                "path": "/repo/.saga-worktrees/out-a/sub-1",
            }
        )
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "worktree-listed"
        assert outcome.evidence_refs == ()

    def test_rows_1_and_4_git_unlisted_converge_on_already_absent(self) -> None:
        """The lease-absent rows, REDEFINED: already-absent now means 'git no longer
        lists this worktree' — not 'the lease head is gone'."""
        outcome = self._sweep(set())(
            {
                "outcome_id": "out-a",
                "subplot_id": "sub-1",
                "path": "/repo/.saga-worktrees/out-a/sub-1",
            }
        )
        assert outcome.disposition == "already-absent"
        assert outcome.reason_code == "worktree-not-listed"
        assert outcome.evidence_refs == ("worktree:path-absent:out-a:sub-1",)

    def test_row_2_released_by_reap_has_no_successor(self) -> None:
        """The reaped row is deleted with the reaper seam: no input makes the sweep
        return released. The disposition itself stays in the frozen vocabulary."""
        sweep = self._sweep({"/repo/.saga-worktrees/out-a/sub-1"})
        for listed in ({"/repo/.saga-worktrees/out-a/sub-1"}, set()):
            ops_sweep = self._sweep(listed)
            for path in ("/repo/.saga-worktrees/out-a/sub-1", ""):
                outcome = ops_sweep({"outcome_id": "out-a", "subplot_id": "sub-1", "path": path})
                assert outcome.disposition in {"retained", "already-absent"}
        assert "released" in TT.DISPOSITIONS
        assert sweep is not None

    def test_old_lease_namespaced_surface_is_gone(self) -> None:
        source = (SCRIPTS / "team_teardown.py").read_text(encoding="utf-8")
        for retired in (
            "broker:lease-absent",
            "sweep:reaped",
            "sweep:lease-gone",
            "lease-already-released",
            "released-by-sweep",
            "not-a-sweep-candidate",
        ):
            assert retired not in source


# --------------------------------------------------------------------------- disk sentinel


class TestDiskRemovalSentinel:
    """Regression sentinel: teardown removes no worktree from disk under any input.

    Pins KTD12 — reclamation was never teardown's job — and pre-mortem row 4 (someone
    reads 'sweep' and adds removal back).
    """

    @pytest.mark.parametrize("terminal_reason", sorted(TT.TERMINAL_REASONS))
    @pytest.mark.parametrize("dry_run", [False, True])
    def test_no_worktree_removed_under_any_input(
        self, repo: Path, terminal_reason: str, dry_run: bool
    ) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        live = _add_live_worktree(repo, "out-a", "sub-live")
        _add_absent_worktree(repo, "out-b", "sub-gone")
        listing_before = _git(repo, "worktree", "list", "--porcelain")

        _reclaim(
            repo,
            "team-run-1",
            terminal_reason=terminal_reason,
            dry_run=dry_run,
            at_provider=_Clock("2026-08-05T00:01:00Z"),
        )
        # a second pass, and a recovery pass on top — still nothing removed
        _reclaim(repo, "team-run-1", at_provider=_Clock("2026-08-05T00:02:00Z"))
        TT.recover(
            ledger,
            TT.production_adapters(repo),
            subplot_id="u2-test",
            expired_only=False,
            max_actions=8,
            at_provider=_Clock("2026-08-05T00:03:00Z"),
            repo_root=repo,
        )

        assert _git(repo, "worktree", "list", "--porcelain") == listing_before
        assert live.exists()
        assert live.is_dir()

    def test_no_reaper_seam_survives_anywhere(self) -> None:
        """The removal capability is structurally gone, not just unwired."""
        assert list(inspect.signature(TT.make_worktree_sweep_adapter).parameters) == ["ops"]
        assert list(inspect.signature(TT.production_adapters).parameters) == ["repo_root"]
        source = (SCRIPTS / "team_teardown.py").read_text(encoding="utf-8")
        assert "worktree_reaper" not in source
        # No code path may invoke a worktree removal — the only remaining mention of
        # one is the docstring citing #358's R6 prohibition, never a call shape.
        assert 'worktree", "remove' not in source
        assert "worktree remove --force" not in source
        assert not hasattr(TT, "register_subprocess")
        assert not hasattr(TT, "authorize_resident_stop")
        assert not hasattr(TT, "default_broker")


# --------------------------------------------------------------------------- recovery


class TestRecovery:
    def _recover(
        self,
        repo: Path,
        *,
        expired_only: bool = True,
        max_actions: int = 4,
        adapters: Any = None,
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            TT.recover(
                _ledger(repo),
                adapters if adapters is not None else TT.production_adapters(repo),
                subplot_id="u2-test",
                expired_only=expired_only,
                max_actions=max_actions,
                at_provider=_Clock("2026-08-05T00:10:00Z"),
                repo_root=repo,
            ),
        )

    def test_recover_skips_runs_with_live_worktrees_when_expired_only(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-live")
        _add_live_worktree(repo, "out-a", "sub-live")
        result = self._recover(repo, expired_only=True)
        (entry,) = result["recovered_runs"]
        assert entry["skipped"] == "live-worktrees"
        assert entry["actions_taken"] == 0
        facts = TT.run_ledger.read_facts(ledger)
        observations = [f for f in facts if f.get("event") == "recovery-observation"]
        assert observations[0]["reason_code"] == "expired-only-live-worktrees"
        assert not any(f.get("event") == "teardown-complete" for f in facts)

    def test_recover_completes_run_whose_worktrees_are_all_absent(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-crashed")
        _add_absent_worktree(repo, "out-a", "sub-gone")
        result = self._recover(repo, expired_only=True)
        (entry,) = result["recovered_runs"]
        assert entry["actions_taken"] == 1
        assert entry["complete"] is True
        facts = TT.run_ledger.read_facts(ledger)
        assert any(
            f.get("event") == "teardown-complete" and f["team_run_id"] == "team-run-crashed"
            for f in facts
        )

    def test_recover_respects_action_budget(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-a")
        _open_run(ledger, "team-run-b")
        _add_absent_worktree(repo, "out-a", "sub-1")
        _add_absent_worktree(repo, "out-a", "sub-2")
        result = self._recover(repo, expired_only=True, max_actions=1)
        assert result["recovered_runs"][0]["actions_taken"] == 1
        assert result["recovered_runs"][1]["skipped"] == "budget"
        facts = TT.run_ledger.read_facts(ledger)
        reasons = [
            f["reason_code"]
            for f in facts
            if f.get("event") == "recovery-observation" and f["team_run_id"] == "team-run-b"
        ]
        assert reasons == ["recovery-action-budget-exhausted"]

    def test_recover_observes_even_with_nothing_to_do(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-empty")
        result = self._recover(repo, expired_only=True)
        (entry,) = result["recovered_runs"]
        assert entry["actions_taken"] == 0
        assert entry["complete"] is True  # zero worktrees -> zero open -> completed
        facts = TT.run_ledger.read_facts(ledger)
        assert any(f.get("event") == "recovery-observation" for f in facts)

    def test_recover_refuses_negative_budget(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        with pytest.raises(TT.TeardownError):
            TT.recover(
                ledger,
                TT.production_adapters(repo),
                subplot_id="u2-test",
                expired_only=True,
                max_actions=-1,
                at_provider=_Clock(),
                repo_root=repo,
            )


class TestRecoveryIsolation:
    def test_poisoned_run_does_not_block_newer_runs_recovery(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-poisoned")
        _open_run(ledger, "team-run-newer")
        _add_absent_worktree(repo, "out-a", "sub-poison")
        _add_absent_worktree(repo, "out-b", "sub-newer")
        # Wedge the poisoned run's ledger: a teardown-intent under the SAME deterministic
        # intent id but a different subplot_id is a conflict the driver cannot replay —
        # reclaim_all raises for this run, and per-run isolation must keep it contained.
        TT.append_teardown_event(
            ledger,
            TT.build_teardown_intent(
                subplot_id="poison-wedge",
                at="2026-08-05T00:00:00Z",
                team_run_id="team-run-poisoned",
                terminal_reason="recovered-crash",
                close_generation=1,
            ),
        )
        result = TT.recover(
            ledger,
            TT.production_adapters(repo),
            subplot_id="u2-test",
            expired_only=True,
            max_actions=8,
            at_provider=_Clock(),
            repo_root=repo,
        )
        by_run = {entry["team_run_id"]: entry for entry in result["recovered_runs"]}
        assert by_run["team-run-poisoned"]["error"] == "TeardownConflictError"
        assert by_run["team-run-poisoned"]["actions_taken"] == 0
        assert by_run["team-run-newer"]["complete"] is True

    def test_budget_exhausted_skips_later_runs_with_observation(self, repo: Path) -> None:
        ledger = _ledger(repo)
        for run in ("team-run-1", "team-run-2", "team-run-3"):
            _open_run(ledger, run)
        _add_absent_worktree(repo, "out-a", "sub-1")
        _add_absent_worktree(repo, "out-a", "sub-2")
        _add_absent_worktree(repo, "out-a", "sub-3")
        result = TT.recover(
            ledger,
            TT.production_adapters(repo),
            subplot_id="u2-test",
            expired_only=True,
            max_actions=2,
            at_provider=_Clock(),
            repo_root=repo,
        )
        skipped = [entry for entry in result["recovered_runs"] if entry.get("skipped")]
        assert skipped and all(entry["skipped"] == "budget" for entry in skipped)

    def test_crash_reconcile_results_do_not_drain_budget(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        intent = TT.append_teardown_event(
            ledger,
            TT.build_teardown_intent(
                subplot_id="u2-test",
                at="2026-08-05T00:00:00Z",
                team_run_id="team-run-1",
                terminal_reason="recovered-crash",
                close_generation=1,
            ),
        )
        for index in range(3):
            TT.append_teardown_event(
                ledger,
                TT.build_resource_attempt(
                    subplot_id="u2-test",
                    at="2026-08-05T00:00:01Z",
                    team_run_id="team-run-1",
                    intent_id=str(intent["intent_id"]),
                    resource_id=f"/orphan/{index}",
                    resource_kind="outcome-worktree",
                    generation=f"out-a:orphan-{index}",
                    action="worktree-sweep",
                ),
            )
        _add_absent_worktree(repo, "out-a", "sub-real")
        stats = TT.ReclaimStats()
        projection = TT.reclaim_all(
            ledger,
            TT.production_adapters(repo),
            subplot_id="u2-test",
            team_run_id="team-run-1",
            terminal_reason="recovered-crash",
            at_provider=_Clock(),
            repo_root=repo,
            max_actions=1,
            stats=stats,
        )
        assert stats.actions_taken == 1  # only the real census entry charged the budget
        assert projection["completion_fact_ref"] is not None


class TestConcurrentReclaim:
    def test_concurrent_reclaim_invokes_adapter_once_per_action(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        _add_absent_worktree(repo, "out-a", "sub-1")
        _add_absent_worktree(repo, "out-a", "sub-2")
        invocations: list[str] = []
        lock = threading.Lock()

        def _counting(resource: Mapping[str, Any]) -> Any:
            with lock:
                invocations.append(str(resource.get("subplot_id")))
            return TT.ActionOutcome(disposition="already-absent")

        adapters = TT.ReclaimAdapters(worktree_sweep=_counting)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(
                    _reclaim,
                    repo,
                    "team-run-1",
                    adapters=adapters,
                    at_provider=_Clock(f"2026-08-05T00:0{index}:00Z"),
                )
                for index in range(4)
            ]
            projections = [future.result() for future in futures]
        assert sorted(invocations) == ["sub-1", "sub-2"]  # once each, across four racers
        assert all(p["completion_fact_ref"] for p in projections)


# --------------------------------------------------------------------------- guard + refusals


class TestReclaimGuardLifecycle:
    def test_fresh_repo_reclaim_provisions_store_and_fails_typed(self, tmp_path: Path) -> None:
        repo = tmp_path / "bare-repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "test@example.invalid")
        _git(repo, "config", "user.name", "Test")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "seed")
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        projection = _reclaim(repo, "team-run-1")
        assert projection["completion_fact_ref"] is not None
        assert _ledger_path(repo).exists()

    def test_guard_provisioning_failure_surfaces_typed_refusal(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        blocked = _ledger_path(repo).parent
        blocked.mkdir(parents=True, exist_ok=True)
        os.chmod(blocked, 0o500)  # the lock file cannot be created inside
        try:
            with pytest.raises(TT.TeardownError, match="cannot provision the reclaim guard"):
                _reclaim(repo, "team-run-1")
        finally:
            os.chmod(blocked, 0o700)


class TestDefensiveRefusals:
    def test_project_refuses_unknown_run(self, repo: Path) -> None:
        decision = TT.read_decision_input(_ledger(repo), repo_root=repo)
        with pytest.raises(TT.TeardownError):
            TT.project(decision, "team-run-never-opened")

    def test_complete_without_matching_intent_is_refused(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        with pytest.raises(TT.TeardownError):
            TT.append_teardown_event(
                ledger,
                TT.build_teardown_complete(
                    subplot_id="u2-test",
                    at="2026-08-05T00:00:00Z",
                    team_run_id="team-run-1",
                    intent_id="d" * 64,
                    close_generation=1,
                    released_count=0,
                    already_absent_count=0,
                ),
            )

    def test_entry_without_path_reports_absent(self) -> None:
        sweep = TT.make_worktree_sweep_adapter(FakeOps(set()))
        outcome = sweep({"outcome_id": "out-a", "subplot_id": "sub-1", "path": ""})
        assert outcome.disposition == "already-absent"
        assert outcome.reason_code == "worktree-not-listed"

    def test_request_refuses_unknown_terminal_reason(self, repo: Path) -> None:
        ledger = _ledger(repo)
        _open_run(ledger, "team-run-1")
        with pytest.raises(TT.TeardownError):
            TT.request(
                ledger,
                subplot_id="u2-test",
                team_run_id="team-run-1",
                terminal_reason="not-a-reason",
                at="2026-08-05T00:00:00Z",
            )


# --------------------------------------------------------------------------- CLI


class TestCli:
    def _run(self, repo: Path, *argv: str) -> tuple[int, str, str]:
        import contextlib
        import io

        buffer_out, buffer_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buffer_out), contextlib.redirect_stderr(buffer_err):
            code = TT.main(["--repo-root", str(repo), *argv])
        return code, buffer_out.getvalue(), buffer_err.getvalue()

    def test_open_run_status_request_reclaim_recover_roundtrip(self, repo: Path) -> None:
        code, out, _err = self._run(repo, "open-run", "--session-id", "session-cli")
        assert code == 0
        run_id = json.loads(out)["opened"]

        code, out, _err = self._run(repo, "status")
        assert code == 0
        assert json.loads(out)["open_runs"] == [run_id]

        _add_absent_worktree(repo, "out-a", "sub-cli")
        code, out, _err = self._run(repo, "request", "--session-id", "session-cli")
        assert code == 0
        assert json.loads(out)["requested"][0]["team_run_id"] == run_id

        code, out, _err = self._run(
            repo, "reclaim-all", "--team-run-id", run_id, "--reason", "success"
        )
        assert code == 0
        projection = json.loads(out)
        assert projection["completion_fact_ref"] is not None

        code, out, _err = self._run(repo, "recover", "--expired-only")
        assert code == 0
        assert json.loads(out)["recovered_runs"] == []

    def test_status_for_unknown_run_is_a_typed_error(self, repo: Path) -> None:
        code, _out, err = self._run(repo, "status", "--team-run-id", "team-run-never-opened")
        assert code == 2
        assert json.loads(err)["error"] == "team-teardown"
