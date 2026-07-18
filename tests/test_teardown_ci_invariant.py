"""Hermetic leak invariant and source-aware teardown conformance (#358 U5, R10).

Every fixture here is a temporary Git repository, broker registry, and ledger — the tests
never enumerate, inspect, or mutate the developer's global worktree set or live broker
authority. The invariant is proven both ways: a planted unledgered worktree turns it red,
and production registration + reclamation turns it green.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
BROKER_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
POLICY_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "concurrency_policy.py"
)
TEAM_SKILL = ROOT / "plugins" / "team-execution" / "skills" / "team-execution" / "SKILL.md"
CONSUMER_SITES = ROOT / "plugins" / "saga" / "references" / "teardown-consumer-sites.md"


def _load(path: Path, name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RL = _load(SCRIPTS / "run_ledger.py", "run_ledger_for_ci_invariant")
TT = _load(SCRIPTS / "team_teardown.py", "team_teardown_for_ci_invariant")
B = _load(BROKER_PATH, "fleet_lease_broker_for_ci_invariant")
P = _load(POLICY_PATH, "fleet_concurrency_policy_for_ci_invariant")


def _git(repo: Path, *argv: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *argv],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return completed.stdout


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(repo.parent, "init", "--quiet", str(repo))
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(
        repo,
        "-c",
        "user.email=ci@invariant.test",
        "-c",
        "user.name=CI",
        "commit",
        "-q",
        "-m",
        "seed",
    )
    return repo


def _list_worktrees(repo: Path) -> list[Path]:
    """Worktrees of exactly this fixture repository — never the machine's global set."""

    out = _git(repo, "worktree", "list", "--porcelain")
    paths = [
        Path(line.removeprefix("worktree "))
        for line in out.splitlines()
        if line.startswith("worktree ")
    ]
    return [p for p in paths if p.resolve() != repo.resolve()]


def _leased_worktree_paths(broker: Any, repo: Path) -> set[Path]:
    leased: set[Path] = set()
    for lease in broker.inspect().get("leases", []):
        resource = lease.get("resource_ref")
        if lease.get("pool") != "worktree" or not isinstance(resource, dict):
            continue
        if Path(resource.get("repo_root", "")).resolve() != repo.resolve():
            continue
        leased.add((repo / ".claude" / "worktrees" / str(resource.get("subplot_id"))).resolve())
    return leased


def unexplained_worktrees(broker: Any, repo: Path) -> list[Path]:
    """The leak invariant: every fixture worktree must be explained by a broker lease.

    Scope is the fixture repository alone; an external worktree belonging to another
    repository is out of managed scope by construction (a different ``git worktree list``).
    """

    leased = _leased_worktree_paths(broker, repo)
    return sorted(p for p in _list_worktrees(repo) if p.resolve() not in leased)


def _broker(tmp_path: Path) -> Any:
    return B.LeaseBroker(tmp_path / "authority")


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _worktree_resource(repo: Path, sid: str) -> dict[str, str]:
    return {"repo_root": str(repo), "outcome_id": "ci-outcome", "subplot_id": sid}


def _add_worktree(repo: Path, sid: str) -> Path:
    path = repo / ".claude" / "worktrees" / sid
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--quiet", "--detach", str(path))
    return path


class TestLeakInvariant:
    def test_clean_fixture_has_zero_unexplained(self, tmp_path: Path) -> None:
        repo = _fixture_repo(tmp_path)
        broker = _broker(tmp_path)
        assert unexplained_worktrees(broker, repo) == []

    def test_unledgered_worktree_turns_the_invariant_red_then_production_reclaim_green(
        self, tmp_path: Path
    ) -> None:
        repo = _fixture_repo(tmp_path)
        broker = _broker(tmp_path)
        ledger = _ledger(tmp_path)
        leak = _add_worktree(repo, "leaked-sub")

        red = unexplained_worktrees(broker, repo)
        assert red == [leak]

        # Register through the production broker: the worktree becomes explained.
        lease = broker.acquire_worktree(
            owner_id="team-run-ci",
            session_id="session-ci",
            resource_ref=_worktree_resource(repo, "leaked-sub"),
            owner_pid=999999,  # a PID that provably does not exist -> dead owner
            ttl_seconds=1,
        )
        assert unexplained_worktrees(broker, repo) == []

        # Reclaim through the production driver with a real (fixture-scoped) reaper.
        TT.open_run(
            ledger,
            broker,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-07-18T15:00:00Z",
            team_run_id="team-run-ci",
        )

        def _reaper(resource: Any) -> bool:
            target = repo / ".claude" / "worktrees" / str(resource["subplot_id"])
            _git(repo, "worktree", "remove", "--force", str(target))
            return True

        import time as _time

        _time.sleep(1.2)  # the fixture lease's 1-second TTL derives expired
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker, worktree_reaper=_reaper),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="success",
            at_provider=lambda: "2026-07-18T15:01:00Z",
        )
        assert projection["open_count"] == 0
        assert projection["completion_fact_ref"] is not None
        assert unexplained_worktrees(broker, repo) == []
        assert not leak.exists()
        assert lease.lease_id not in [item["lease_id"] for item in broker.inspect()["leases"]]

    def test_lease_with_missing_path_is_detected_distinctly(self, tmp_path: Path) -> None:
        repo = _fixture_repo(tmp_path)
        broker = _broker(tmp_path)
        broker.acquire_worktree(
            owner_id="team-run-ci",
            session_id="session-ci",
            resource_ref=_worktree_resource(repo, "phantom-sub"),
        )
        # Nothing on disk: not a leak (no unexplained worktree), but the lease's path
        # is visibly absent for the census.
        assert unexplained_worktrees(broker, repo) == []
        missing = [path for path in _leased_worktree_paths(broker, repo) if not path.exists()]
        assert len(missing) == 1

    def test_external_repository_worktree_is_out_of_managed_scope(self, tmp_path: Path) -> None:
        repo = _fixture_repo(tmp_path)
        other = tmp_path / "other-repo"
        other.mkdir()
        _git(other.parent, "init", "--quiet", str(other))
        (other / "x.txt").write_text("x\n", encoding="utf-8")
        _git(other, "add", "x.txt")
        _git(
            other,
            "-c",
            "user.email=ci@invariant.test",
            "-c",
            "user.name=CI",
            "commit",
            "-q",
            "-m",
            "x",
        )
        _git(other, "worktree", "add", "--quiet", "--detach", str(tmp_path / "other-wt"))
        broker = _broker(tmp_path)
        assert unexplained_worktrees(broker, repo) == []

    def test_live_owner_worktree_is_retained_and_still_explained(self, tmp_path: Path) -> None:
        import os as _os

        repo = _fixture_repo(tmp_path)
        broker = _broker(tmp_path)
        ledger = _ledger(tmp_path)
        _add_worktree(repo, "live-sub")
        broker.acquire_worktree(
            owner_id="team-run-ci",
            session_id="session-ci",
            resource_ref=_worktree_resource(repo, "live-sub"),
            owner_pid=_os.getpid(),  # this test process is provably alive
        )
        TT.open_run(
            ledger,
            broker,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-07-18T15:00:00Z",
            team_run_id="team-run-ci",
        )
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="operator-abort",
            at_provider=lambda: "2026-07-18T15:01:00Z",
        )
        assert projection["retained_count"] == 1
        assert projection["completion_fact_ref"] is None
        assert unexplained_worktrees(broker, repo) == []

    def test_failed_cleanup_stays_red_and_retry_converges_green(self, tmp_path: Path) -> None:
        import time as _time

        repo = _fixture_repo(tmp_path)
        broker = _broker(tmp_path)
        ledger = _ledger(tmp_path)
        target = _add_worktree(repo, "flaky-sub")
        broker.acquire_worktree(
            owner_id="team-run-ci",
            session_id="session-ci",
            resource_ref=_worktree_resource(repo, "flaky-sub"),
            owner_pid=999999,
            ttl_seconds=1,
        )
        TT.open_run(
            ledger,
            broker,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-07-18T15:00:00Z",
            team_run_id="team-run-ci",
        )
        _time.sleep(1.2)

        first = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker, worktree_reaper=lambda _r: False),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="hard-fail",
            at_provider=lambda: "2026-07-18T15:01:00Z",
        )
        assert first["retained_count"] == 1
        assert first["completion_fact_ref"] is None
        assert target.exists()

        def _reaper(resource: Any) -> bool:
            _git(
                repo,
                "worktree",
                "remove",
                "--force",
                str(repo / ".claude" / "worktrees" / str(resource["subplot_id"])),
            )
            return True

        second = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker, worktree_reaper=_reaper),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="hard-fail",
            at_provider=lambda: "2026-07-18T15:02:00Z",
        )
        assert second["completion_fact_ref"] is not None
        assert not target.exists()
        assert unexplained_worktrees(broker, repo) == []

    def test_live_census_dry_run_makes_no_file_or_ref_changes(self, tmp_path: Path) -> None:
        repo = _fixture_repo(tmp_path)
        broker = _broker(tmp_path)
        ledger = _ledger(tmp_path)
        TT.open_run(
            ledger,
            broker,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-07-18T15:00:00Z",
            team_run_id="team-run-ci",
        )
        ledger_bytes = ledger.path.read_bytes()
        refs_before = _git(repo, "for-each-ref")
        worktrees_before = _list_worktrees(repo)

        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="success",
            at_provider=lambda: "2026-07-18T15:01:00Z",
            dry_run=True,
        )
        assert projection["completion_fact_ref"] is None
        assert ledger.path.read_bytes() == ledger_bytes
        assert _git(repo, "for-each-ref") == refs_before
        assert _list_worktrees(repo) == worktrees_before
        assert broker.inspect_owner_admission("team-run-ci") is None


# --------------------------------------------------------------- source-aware conformance


def _spawn_conformance_violations(source: str) -> list[str]:
    """Flag spawn shapes that create resources without teardown registration (R10).

    A fixture-grade checker: a source that spawns a subprocess or worktree must name the
    production registration call, and a source that asserts completion must name the B8
    driver. Deliberately shallow — the goal is that an unwired copy of a production
    pattern cannot pass silently.
    """

    violations: list[str] = []
    spawns_subprocess = "subprocess.Popen" in source or "os.fork" in source
    if spawns_subprocess and "register_subprocess" not in source:
        violations.append("subprocess-spawn-without-registration")
    adds_worktree = "worktree add" in source or "acquire_worktree" in source
    if "worktree add" in source and "acquire_worktree" not in source:
        violations.append("worktree-spawn-without-registration")
    claims_complete = "teardown-complete" in source or "run complete" in source
    if claims_complete and ("reclaim_all" not in source and "reclaim-all" not in source):
        violations.append("completion-claim-without-b8")
    assert adds_worktree or spawns_subprocess or claims_complete or not violations
    return violations


class TestSourceConformance:
    def test_negative_fixture_unregistered_spawn_fails(self) -> None:
        fixture = "child = subprocess.Popen([sys.executable, worker])\n"
        assert "subprocess-spawn-without-registration" in _spawn_conformance_violations(fixture)
        fixture_wt = 'run(["git", "worktree add", path])\n'
        assert "worktree-spawn-without-registration" in _spawn_conformance_violations(fixture_wt)

    def test_negative_fixture_terminal_branch_bypassing_b8_fails(self) -> None:
        fixture = 'print("run complete")\n'
        assert "completion-claim-without-b8" in _spawn_conformance_violations(fixture)

    def test_registered_spawn_and_b8_completion_pass(self) -> None:
        fixture = (
            "child = subprocess.Popen(argv)\n"
            "team_teardown.register_subprocess(broker, team_run_id=run, ...)\n"
            "projection = team_teardown.reclaim_all(...)  # emits teardown-complete\n"
        )
        assert _spawn_conformance_violations(fixture) == []

    def test_team_skill_wires_run_open_registration_and_b8(self) -> None:
        skill = TEAM_SKILL.read_text(encoding="utf-8")
        assert "lease_protocol.py open-run" in skill
        assert "lease_protocol.py reclaim-all" in skill
        assert "B7 cannot assert" in skill

    def test_consumer_inventory_names_every_required_column_and_seam(self) -> None:
        inventory = CONSUMER_SITES.read_text(encoding="utf-8")
        for column in (
            "run-open",
            "register",
            "renewal",
            "terminal driver",
            "action owner",
            "release",
            "recovery",
            "proof",
        ):
            assert f"| {column} " in inventory or f" {column} |" in inventory
        for seam in (
            "lease_protocol.py open-run",
            "register_subprocess",
            "reclaim-all",
            "recover --expired-only --max-actions 4",
            "request",
            "SessionEnd",
            "SessionStart",
        ):
            assert seam in inventory
        assert "enumerates, inspects, or deletes the developer's global worktree set" in inventory

    def test_no_second_reclamation_store_exists(self) -> None:
        saga_scripts = sorted(p.name for p in SCRIPTS.glob("*.py"))
        assert "reclamation_ledger.py" not in saga_scripts
        assert "worktree_reaper.py" not in saga_scripts
        teardown_source = (SCRIPTS / "team_teardown.py").read_text(encoding="utf-8")
        # The module projects state; it never persists a mutable open/closed summary.
        assert "open_count" in teardown_source
        for forbidden in ("status.json", "open_runs.json", "reclamation.db"):
            assert forbidden not in teardown_source
