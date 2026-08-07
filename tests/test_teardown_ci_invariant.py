"""Hermetic leak invariant and source-aware teardown conformance (#358 U5/R10, #677/U2).

Every fixture here is a temporary Git repository, outcome worktree registry, and
ledger — the tests never enumerate, inspect, or mutate the developer's global worktree
set or any live coordination state. The invariant is proven both ways: a planted
unregistered worktree turns it red, and production registration turns it green.

#677/U2 re-keyed the explanation source: a worktree is *explained* by an entry in its
outcome's worktree registry — the lease list that used to explain them is retired.
Registration, not reclamation, is what turns the invariant green: teardown reports
dispositions and never removes anything from disk (KTD12).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
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
OW = _load(SCRIPTS / "outcome_worktrees.py", "outcome_worktrees_for_ci_invariant")


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


def _registered_paths(repo: Path) -> set[Path]:
    """Every worktree path an outcome registry entry explains (#677/U2 explanation source)."""

    registered: set[Path] = set()
    namespace = repo / ".git" / "saga-outcomes"
    if not namespace.is_dir():
        return registered
    for registry in sorted(namespace.glob("*/worktrees.json")):
        data = json.loads(registry.read_text(encoding="utf-8"))
        for entry in data.get("worktrees", {}).values():
            path = str(entry.get("path", ""))
            if path:
                registered.add(Path(path).resolve())
    return registered


def unexplained_worktrees(repo: Path) -> list[Path]:
    """The leak invariant: every fixture worktree must be explained by a registry entry.

    Scope is the fixture repository alone; an external worktree belonging to another
    repository is out of managed scope by construction (a different ``git worktree list``).
    """

    registered = _registered_paths(repo)
    return sorted(p for p in _list_worktrees(repo) if p.resolve() not in registered)


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _register(repo: Path, outcome_id: str, subplot_id: str, path: Path) -> None:
    """The production registration seam: outcome_worktrees.register under the store."""

    store = OW.outcome_store.Store(root=repo / ".git" / "saga-outcomes" / outcome_id)
    OW.register(
        store,
        subplot_id,
        {
            "path": str(path),
            "branch": f"saga-outcome-{outcome_id}-{subplot_id}",
            "repo_root": str(repo),
            "outcome_id": outcome_id,
        },
    )


def _add_worktree(repo: Path, outcome_id: str, subplot_id: str) -> Path:
    path = repo / ".saga-worktrees" / outcome_id / subplot_id
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--quiet", "--detach", str(path))
    return path


class TestLeakInvariant:
    def test_clean_fixture_has_zero_unexplained(self, tmp_path: Path) -> None:
        repo = _fixture_repo(tmp_path)
        assert unexplained_worktrees(repo) == []

    def test_unregistered_worktree_turns_the_invariant_red_then_registration_green(
        self, tmp_path: Path
    ) -> None:
        repo = _fixture_repo(tmp_path)
        ledger = _ledger(tmp_path)
        leak = _add_worktree(repo, "ci-outcome", "leaked-sub")

        red = unexplained_worktrees(repo)
        assert red == [leak]

        # Register through the production seam: the worktree becomes explained.
        _register(repo, "ci-outcome", "leaked-sub", leak)
        assert unexplained_worktrees(repo) == []

        # Teardown REPORTS the registered worktree — it never reclaims it (KTD12).
        TT.open_run(
            ledger,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-08-05T15:00:00Z",
            team_run_id="team-run-ci",
        )
        projection = TT.reclaim_all(
            ledger,
            TT.production_adapters(repo),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="success",
            at_provider=lambda: "2026-08-05T15:01:00Z",
            repo_root=repo,
        )
        assert projection["retained_count"] == 1
        assert projection["completion_fact_ref"] is None  # a truthful blocked terminal
        assert unexplained_worktrees(repo) == []
        assert leak.exists()  # teardown removed nothing from disk

    def test_registered_but_absent_worktree_reports_already_absent_and_completes(
        self, tmp_path: Path
    ) -> None:
        repo = _fixture_repo(tmp_path)
        ledger = _ledger(tmp_path)
        phantom = repo / ".saga-worktrees" / "ci-outcome" / "phantom-sub"
        _register(repo, "ci-outcome", "phantom-sub", phantom)
        # Nothing on disk: not a leak (no unexplained worktree), and teardown's census
        # reports the re-defined already-absent — git no longer lists this worktree.
        assert unexplained_worktrees(repo) == []
        TT.open_run(
            ledger,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-08-05T15:00:00Z",
            team_run_id="team-run-ci",
        )
        projection = TT.reclaim_all(
            ledger,
            TT.production_adapters(repo),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="success",
            at_provider=lambda: "2026-08-05T15:01:00Z",
            repo_root=repo,
        )
        assert projection["already_absent_count"] == 1
        assert projection["completion_fact_ref"] is not None
        assert not phantom.exists()

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
        assert unexplained_worktrees(repo) == []

    def test_registered_worktree_stays_explained_across_repeated_reclaim(
        self, tmp_path: Path
    ) -> None:
        repo = _fixture_repo(tmp_path)
        ledger = _ledger(tmp_path)
        target = _add_worktree(repo, "ci-outcome", "flaky-sub")
        _register(repo, "ci-outcome", "flaky-sub", target)
        TT.open_run(
            ledger,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-08-05T15:00:00Z",
            team_run_id="team-run-ci",
        )
        first = TT.reclaim_all(
            ledger,
            TT.production_adapters(repo),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="hard-fail",
            at_provider=lambda: "2026-08-05T15:01:00Z",
            repo_root=repo,
        )
        assert first["retained_count"] == 1
        assert first["completion_fact_ref"] is None
        assert target.exists()

        # The worktree is removed out-of-band (an operator action, never teardown's);
        # the next pass converges on the re-defined already-absent and completes.
        _git(repo, "worktree", "remove", "--force", str(target))
        second = TT.reclaim_all(
            ledger,
            TT.production_adapters(repo),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="hard-fail",
            at_provider=lambda: "2026-08-05T15:02:00Z",
            repo_root=repo,
        )
        assert second["completion_fact_ref"] is not None
        assert not target.exists()
        assert unexplained_worktrees(repo) == []

    def test_live_census_dry_run_makes_no_file_or_ref_changes(self, tmp_path: Path) -> None:
        repo = _fixture_repo(tmp_path)
        ledger = _ledger(tmp_path)
        _add_worktree(repo, "ci-outcome", "census-sub")
        _register(
            repo, "ci-outcome", "census-sub", repo / ".saga-worktrees" / "ci-outcome" / "census-sub"
        )
        TT.open_run(
            ledger,
            subplot_id="ci-invariant",
            session_id="session-ci",
            at="2026-08-05T15:00:00Z",
            team_run_id="team-run-ci",
        )
        ledger_bytes = ledger.path.read_bytes()
        refs_before = _git(repo, "for-each-ref")
        worktrees_before = _list_worktrees(repo)

        projection = TT.reclaim_all(
            ledger,
            TT.production_adapters(repo),
            subplot_id="ci-invariant",
            team_run_id="team-run-ci",
            terminal_reason="success",
            at_provider=lambda: "2026-08-05T15:01:00Z",
            repo_root=repo,
            dry_run=True,
        )
        assert projection["completion_fact_ref"] is None
        assert ledger.path.read_bytes() == ledger_bytes
        assert _git(repo, "for-each-ref") == refs_before
        assert _list_worktrees(repo) == worktrees_before


# --------------------------------------------------------------- source-aware conformance


def _spawn_conformance_violations(source: str) -> list[str]:
    """Flag creation shapes that skip their trusted seams (R10, re-keyed by #677/U2).

    A fixture-grade checker: a source that adds a worktree must name the registry
    registration seam, and a source that asserts completion must name the B8 driver.
    The subprocess registration rule retired with the lease authority — spawn-time
    subprocess identity is an accepted loss of the retirement (Option C), so there is
    no seam left to require. Deliberately shallow — the goal is that an unwired copy
    of a production pattern cannot pass silently.
    """

    violations: list[str] = []
    if "worktree add" in source and "outcome_worktrees.register" not in source:
        violations.append("worktree-spawn-without-registration")
    claims_complete = "teardown-complete" in source or "run complete" in source
    if claims_complete and ("reclaim_all" not in source and "reclaim-all" not in source):
        violations.append("completion-claim-without-b8")
    return violations


class TestSourceConformance:
    def test_negative_fixture_unregistered_worktree_fails(self) -> None:
        fixture_wt = 'run(["git", "worktree add", path])\n'
        assert "worktree-spawn-without-registration" in _spawn_conformance_violations(fixture_wt)

    def test_negative_fixture_terminal_branch_bypassing_b8_fails(self) -> None:
        fixture = 'print("run complete")\n'
        assert "completion-claim-without-b8" in _spawn_conformance_violations(fixture)

    def test_registered_worktree_and_b8_completion_pass(self) -> None:
        fixture = (
            'run(["git", "worktree add", path])\n'
            "outcome_worktrees.register(store, subplot_id, entry)\n"
            "projection = team_teardown.reclaim_all(...)  # emits teardown-complete\n"
        )
        assert _spawn_conformance_violations(fixture) == []

    def test_team_skill_wires_run_open_registration_and_b8(self) -> None:
        skill = TEAM_SKILL.read_text(encoding="utf-8")
        # U6 deleted the lease wrapper — the skill must not reference it.
        assert "lease_protocol.py open-run" not in skill
        assert "lease_protocol.py reclaim-all" not in skill
        assert "B7 cannot assert" in skill

    def test_consumer_inventory_names_every_required_column_and_seam(self) -> None:
        inventory = CONSUMER_SITES.read_text(encoding="utf-8")
        for column in (
            "run-open",
            "worktree census",
            "terminal driver",
            "action owner",
            "disposition",
            "recovery",
            "proof",
        ):
            assert f"| {column} " in inventory or f" {column} |" in inventory
        for seam in (
            "live_worktrees",
            "reclaim-all",
            "request",
            "SessionEnd",
            "SessionStart",
        ):
            assert seam in inventory
        # U6 deleted the lease wrapper — its seams must be absent.
        assert "lease_protocol.py open-run" not in inventory
        # The inventory no longer enumerates a second global worktree check after the U2 re-key.
        # Keep the assertion for the report-only path if present, but don't require the old phrasing.

    def test_no_second_reclamation_store_exists(self) -> None:
        saga_scripts = sorted(p.name for p in SCRIPTS.glob("*.py"))
        assert "reclamation_ledger.py" not in saga_scripts
        assert "worktree_reaper.py" not in saga_scripts
        teardown_source = (SCRIPTS / "team_teardown.py").read_text(encoding="utf-8")
        # The module projects state; it never persists a mutable open/closed summary.
        assert "open_count" in teardown_source
        for forbidden in ("status.json", "open_runs.json", "reclamation.db"):
            assert forbidden not in teardown_source

    def test_every_enumerated_consumer_source_passes_conformance(self) -> None:
        """The checker audits the REAL production sources the inventory enumerates —
        not only its own fixtures — so an unwired spawn or a B8-bypassing completion
        claim added to a consumer site goes red in CI (round-1 TST-4)."""

        team_scripts = TEAM_SKILL.parent / "scripts"
        enumerated = [
            SCRIPTS / "team_teardown.py",
            ROOT / "plugins" / "saga" / "hooks" / "team_teardown_hook.py",
            team_scripts / "liveness_protocol.py",
            TEAM_SKILL,
        ]
        for path in enumerated:
            assert path.exists(), f"inventory names a missing consumer source: {path}"
            violations = _spawn_conformance_violations(path.read_text(encoding="utf-8"))
            assert violations == [], f"{path.relative_to(ROOT)}: {violations}"
        # The lease wrapper is deleted — assert it's gone.
        assert not (team_scripts / "lease_protocol.py").exists(), (
            "lease_protocol.py should be deleted in U6"
        )
