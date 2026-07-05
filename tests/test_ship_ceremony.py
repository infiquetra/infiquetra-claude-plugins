"""ship_ceremony.py tests (issue #345).

Test design (mirrors the house pattern in ``outcome_store.py`` — runner injectable,
never shell out unmocked): git-only transitions (``commit``, ``checkout_main``,
``pull``, ``branch_delete``) and the alias install/uninstall run against a REAL
throwaway git repo under ``tmp_path`` with a REAL local bare "origin" — these are
local-only, no network, and this module is registered in ``tests/conftest.py``'s
``_GH_WRITE_TEST_MODULES`` no-live-gh hard floor (#279) as defense in depth anyway.
GitHub-facing transitions (``open_pr``, ``request_review``, ``merge``) go through a
``FakeGh`` that simulates just enough of the real CLI's behavior — including pushing
the branch's commit to the bare origin's ``main`` ref on a faked "merge" — that the
downstream real ``checkout_main`` / ``pull`` transitions see a genuinely changed
repo, not a no-op.

Oracles:

* happy — a full ceremony run on a throwaway branch drives all seven transitions in
  order, each recorded on the saga tick with the tier from ``TRANSITION_TIERS``.
* resume — killing after transition 3 and re-invoking continues at transition 4,
  never re-running (or re-opening a second PR for) an already-complete transition.
* edge — a already-complete ceremony is a no-op; an unrecognized branch/ambiguous
  match refuses to guess; ``install`` refuses to clobber an unrelated alias.
* parity — the git-surface (``git ship``) entry point and direct invocation drive
  the identical next transition for the same saga.
* front-loaded — ``start`` opens a draft PR immediately; a later ``run`` reaching
  ``open_pr`` flips it ready rather than opening a second one.
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
SHIP_CEREMONY_PATH = ROOT / "plugins" / "saga" / "scripts" / "ship_ceremony.py"


def _load_ship_ceremony() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ship_ceremony", SHIP_CEREMONY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SC = _load_ship_ceremony()


# --------------------------------------------------------------------------- #
# Pure-logic tests (no subprocess at all)
# --------------------------------------------------------------------------- #


def test_next_transition_from_scratch_is_first_entry() -> None:
    assert SC.next_transition("") == "commit"


def test_next_transition_advances_one_step() -> None:
    assert SC.next_transition("commit") == "open_pr"
    assert SC.next_transition("checkout_main") == "pull"


def test_next_transition_none_when_complete() -> None:
    assert SC.next_transition("branch_delete") is None


def test_next_transition_rejects_unknown_name() -> None:
    with pytest.raises(SC.ShipCeremonyError, match="unrecognized ceremony_transition"):
        SC.next_transition("bogus")


def test_every_transition_has_a_declared_tier() -> None:
    assert set(SC.TRANSITIONS) == set(SC.TRANSITION_TIERS)


def test_merge_and_branch_delete_are_always_operator_tier() -> None:
    assert SC.TRANSITION_TIERS["merge"] == SC.CeremonyTier.ALWAYS_OPERATOR
    assert SC.TRANSITION_TIERS["branch_delete"] == SC.CeremonyTier.ALWAYS_OPERATOR


# --------------------------------------------------------------------------- #
# Throwaway-repo fixture: a real git repo + a real local bare "origin".
# --------------------------------------------------------------------------- #


class FakeGh:
    """Simulates just enough of `gh pr ...` for ceremony tests. Real git calls
    (passed through here unchanged) are the only thing that touch disk."""

    def __init__(self, repo: Path, bare_origin: Path) -> None:
        self.repo = repo
        self.bare_origin = bare_origin
        self._next_number = 1
        self._prs: dict[str, dict[str, object]] = {}  # branch -> {number, draft}
        # Captured at construction time, NOT looked up as `subprocess.run` inside
        # __call__ — a test that monkeypatches the global `subprocess.run` to this
        # FakeGh instance (to exercise the CLI's real fallback path) would otherwise
        # make this passthrough call itself recursively.
        self._real_run = subprocess.run

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        if parts[0] == "gh":
            return self._handle_gh(parts[1:])
        real = self._real_run(  # nosec B603
            parts, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )
        return real

    def _handle_gh(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["pr", "create"]:
            draft = "--draft" in args
            branch = args[args.index("--head") + 1]
            number = self._next_number
            self._next_number += 1
            self._prs[branch] = {"number": number, "draft": draft}
            return _ok(str(number))
        if args[:2] == ["pr", "view"]:
            branch = args[2]
            pr = self._prs[branch]
            return _ok(json.dumps({"number": pr["number"]}))
        if args[:2] == ["pr", "ready"]:
            for pr in self._prs.values():
                if pr["number"] == int(args[2]):
                    pr["draft"] = False
            return _ok("")
        if args[:2] == ["pr", "edit"]:
            return _ok("")
        if args[:2] == ["pr", "merge"]:
            number = int(args[2])
            branch = next(b for b, pr in self._prs.items() if pr["number"] == number)
            # Simulate the merge landing on origin's main — pushes the branch's
            # commit(s) to the bare origin's main ref, exactly what the later real
            # `checkout_main` + `pull` transitions expect to observe.
            self._real_run(  # nosec B603
                ["git", "push", str(self.bare_origin), f"{branch}:main"],
                cwd=self.repo,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            return _ok("")
        raise AssertionError(f"unhandled fake gh call: {args!r}")


def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture()
def ceremony_repo(tmp_path: Path):
    """A real throwaway repo cloned from a real local bare origin, with a saga
    already minted (via the real saga.py CLI) on a feature branch — the state
    `resolve_saga` needs to find it by branch."""
    bare_origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True)  # noqa: S607

    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True)  # noqa: S607
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)  # noqa: S607
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)  # noqa: S607
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)  # noqa: S607
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True
    )  # noqa: S607
    subprocess.run(
        ["git", "-C", str(repo), "push", "origin", "HEAD:main"], check=True, capture_output=True
    )  # noqa: S607

    branch = "feat/pf-throwaway-345"
    subprocess.run(
        ["git", "-C", str(repo), "checkout", "-b", branch], check=True, capture_output=True
    )  # noqa: S607
    (repo / "change.txt").write_text("ceremony scaffold\n")
    subprocess.run(["git", "-C", str(repo), "add", "change.txt"], check=True)  # noqa: S607
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "scaffold"], check=True, capture_output=True
    )  # noqa: S607

    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    mint = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(saga_py),
            "save",
            "--kind",
            "issue",
            "--id",
            "345",
            "--issue-ref",
            "org/repo#345",
            "--lifecycle-phase",
            "work",
            "--plan-path",
            "docs/plans/x-plan.md",
            "--destination",
            "merge",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert mint.returncode == 0, mint.stderr

    fake_gh = FakeGh(repo=repo, bare_origin=bare_origin)
    return repo, fake_gh


def _restore(repo: Path) -> dict[str, Any]:
    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(saga_py), "restore", "--saga-id", "issue-345"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    output: dict[str, Any] = json.loads(result.stdout)
    return output


# --------------------------------------------------------------------------- #
# Integration tests
# --------------------------------------------------------------------------- #


def test_full_ceremony_throwaway_branch(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
        assert expected in status

    saga = _restore(repo)
    assert saga["ceremony_transition"] == "branch_delete"
    assert saga["ceremony_tier"] == SC.CeremonyTier.ALWAYS_OPERATOR
    # checkout_main + pull actually landed the merged commit locally.
    assert (repo / "change.txt").exists()
    branches = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "branch"], check=True, capture_output=True, text=True
    ).stdout
    assert "feat/pf-throwaway-345" not in branches


def test_resume_from_state(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    for _ in range(3):  # commit, open_pr, request_review
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert _restore(repo)["ceremony_transition"] == "request_review"

    # "Re-invoking" — a fresh call against the same saga state — must continue at
    # `merge`, not re-run request_review or re-open a second PR.
    status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "merge" in status
    assert len(fake_gh._prs) == 1  # noqa: SLF001 - test introspection of the fake


def test_already_complete_ceremony_is_a_noop(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    for _ in SC.TRANSITIONS:
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "already shipped" in status


def test_git_surface_entry_point(ceremony_repo) -> None:
    """AC3: `run` resolved by branch (no --issue-ref) is the terminal `git ship` path."""
    repo, fake_gh = ceremony_repo
    status = SC.run(repo_root=repo, issue_ref=None, runner=fake_gh)
    assert "commit" in status
    assert _restore(repo)["ceremony_transition"] == "commit"


def test_parity_git_surface_vs_work(ceremony_repo) -> None:
    """AC4: resolving by branch (git-surface) vs by --issue-ref (/work) picks the
    identical next transition for the same saga."""
    repo, fake_gh = ceremony_repo
    by_branch = SC.resolve_saga(repo_root=repo, issue_ref=None, runner=fake_gh)
    by_ref = SC.resolve_saga(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert by_branch["ceremony_transition"] == by_ref["ceremony_transition"]
    assert SC.next_transition(by_branch["ceremony_transition"]) == SC.next_transition(
        by_ref["ceremony_transition"]
    )


def test_ambiguous_branch_match_refuses_to_guess(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(saga_py),
            "save",
            "--kind",
            "task",
            "--id",
            "decoy-same-branch",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    # Force the decoy saga's cached branch to match by saving again on this branch.
    subprocess.run(  # noqa: S603
        [sys.executable, str(saga_py), "save", "--kind", "task", "--id", "decoy-same-branch"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    with pytest.raises(SC.AmbiguousSagaError, match="multiple sagas match branch"):
        SC.resolve_saga(repo_root=repo, issue_ref=None, runner=fake_gh)


def test_front_loaded_draft_pr(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    status = SC.start(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "draft PR #1" in status
    saga = _restore(repo)
    assert saga["pr_refs"] == ["#1"]
    assert saga["ceremony_transition"] == "commit"

    # The later ceremony run reaching `open_pr` must flip the existing draft ready,
    # not open a second PR.
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    assert len(fake_gh._prs) == 1  # noqa: SLF001
    assert fake_gh._prs["feat/pf-throwaway-345"]["draft"] is False  # noqa: SLF001


def test_start_refuses_when_ceremony_already_progressed(ceremony_repo) -> None:
    """Code-review correctness finding: start() must not create a second PR or
    regress ceremony_transition when the ceremony already has state."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    with pytest.raises(SC.ShipCeremonyError, match="already in progress"):
        SC.start(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    # State must be untouched by the refused call.
    assert _restore(repo)["ceremony_transition"] == "commit"
    assert fake_gh._prs == {}  # noqa: SLF001 - no PR was created


def test_open_pr_pushes_pending_commits_on_existing_pr_path(ceremony_repo) -> None:
    """Issue #478: on the front-loaded/existing-PR path, open_pr must push the commits
    accumulated since start() before flipping the draft ready — otherwise CI validates a
    stale HEAD. start() pre-records ceremony_transition="commit", so _do_commit (the only
    other push site) is skipped; the push has to happen in open_pr itself."""
    repo, fake_gh = ceremony_repo
    branch = "feat/pf-throwaway-345"

    # Front-loaded start: pushes the scaffold, opens draft #1, records commit + pr_refs.
    SC.start(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)

    # Simulate implementation work landing locally *after* the draft PR was opened.
    (repo / "impl.txt").write_text("real work done after start()\n")
    subprocess.run(["git", "-C", str(repo), "add", "impl.txt"], check=True)  # noqa: S607
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "impl after start"],
        check=True,
        capture_output=True,
    )  # noqa: S607

    def _rev(ref: str) -> str:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), "rev-parse", ref],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    # Pre-fix bug state: the tracked remote ref is behind local HEAD.
    assert _rev(f"origin/{branch}") != _rev("HEAD")

    # The ceremony run reaching open_pr (next after start's recorded "commit").
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)

    # After the fix the remote ref matches local HEAD (the accumulated commit is pushed),
    # and the draft was still flipped ready rather than a second PR being opened.
    assert _rev(f"origin/{branch}") == _rev("HEAD")
    assert len(fake_gh._prs) == 1  # noqa: SLF001
    assert fake_gh._prs[branch]["draft"] is False  # noqa: SLF001


class FailingRunner:
    """Wraps a base runner and fails one specific command (matched by prefix),
    passing everything else through unchanged."""

    def __init__(self, base, *, fail_prefix: list[str]) -> None:
        self.base = base
        self.fail_prefix = fail_prefix

    def __call__(self, cmd, **kwargs):
        parts = list(cmd)
        if parts[: len(self.fail_prefix)] == self.fail_prefix:
            return subprocess.CompletedProcess(
                args=parts, returncode=1, stdout="", stderr="simulated failure"
            )
        return self.base(cmd, **kwargs)


def test_transition_failure_does_not_advance_state(ceremony_repo) -> None:
    """A failing subprocess call (git push) must raise and leave ceremony_transition
    untouched — the next invocation must retry the same transition, not skip it."""
    repo, fake_gh = ceremony_repo
    failing = FailingRunner(fake_gh, fail_prefix=["git", "push", "-u", "origin"])
    with pytest.raises(SC.TransitionFailedError, match="simulated failure"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=failing)
    assert _restore(repo)["ceremony_transition"] == ""

    # Retrying with a working runner picks up exactly where it left off.
    status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "commit" in status


def test_request_review_is_a_noop(ceremony_repo) -> None:
    """Issue #477: request_review must complete without touching the network at all —
    a runner that raises on any call proves no subprocess was attempted."""
    repo, _fake_gh = ceremony_repo

    def _raising_runner(cmd, **kwargs):  # noqa: ANN001
        raise AssertionError(f"request_review must not shell out, but tried: {cmd!r}")

    SC._do_request_review({}, repo_root=repo, runner=_raising_runner)


def test_no_saga_error_when_branch_has_no_match(ceremony_repo) -> None:
    repo, _fake_gh = ceremony_repo
    subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "checkout", "-b", "some-other-unrelated-branch"],
        check=True,
        capture_output=True,
    )
    with pytest.raises(SC.NoSagaError, match="no saga found for branch"):
        SC.resolve_saga(repo_root=repo, issue_ref=None)


def test_merge_before_open_pr_is_a_named_failure(ceremony_repo) -> None:
    """_current_pr_number's guard: reaching merge with no pr_refs recorded (open_pr
    was skipped or its save was lost) is a named failure, not a crash or a silent
    no-op. (request_review no longer exercises this guard — issue #477 made it a
    deliberate no-op, since this repo has no second maintainer to request review
    from; merge is the next GitHub-facing transition that still needs pr_refs.)"""
    repo, fake_gh = ceremony_repo
    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(saga_py),
            "save",
            "--kind",
            "issue",
            "--id",
            "345",
            "--ceremony-transition",
            "request_review",
            "--ceremony-tier",
            "reversible",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    with pytest.raises(SC.TransitionFailedError, match="no pr_refs recorded"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)


def test_branch_delete_refuses_when_branch_is_main(ceremony_repo) -> None:
    """`branch` is only ever set once on a saga (saga.py's merge logic never
    overwrites a populated field), so this guard is exercised directly against the
    saga dict shape rather than through a full mint-on-main round trip."""
    repo, fake_gh = ceremony_repo
    with pytest.raises(SC.TransitionFailedError, match="refusing to delete branch"):
        SC._do_branch_delete({"branch": "main"}, repo_root=repo, runner=fake_gh)  # noqa: SLF001
    with pytest.raises(SC.TransitionFailedError, match="refusing to delete branch"):
        SC._do_branch_delete({"branch": ""}, repo_root=repo, runner=fake_gh)  # noqa: SLF001


def test_cli_main_run_dispatches(ceremony_repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo, fake_gh = ceremony_repo
    original = SC.subprocess.run
    SC.subprocess.run = fake_gh
    try:
        exit_code = SC.main(["--repo-root", str(repo), "run", "--issue-ref", "org/repo#345"])
    finally:
        SC.subprocess.run = original
    assert exit_code == 0
    assert "commit" in capsys.readouterr().out


def test_cli_main_reports_error_and_exits_nonzero(
    bare_repo_clone: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = SC.main(["--repo-root", str(bare_repo_clone), "uninstall"])
    assert exit_code == 0  # uninstall with no alias is success, not an error path
    subprocess.run(  # noqa: S607
        ["git", "-C", str(bare_repo_clone), "config", "--local", "alias.ship", "!echo mine"],
        check=True,
    )
    exit_code = SC.main(["--repo-root", str(bare_repo_clone), "install"])
    assert exit_code == 1
    assert "alias.ship already set" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Alias install/uninstall — real git config, local scope only.
# --------------------------------------------------------------------------- #


@pytest.fixture()
def bare_repo_clone(tmp_path: Path) -> Path:
    bare_origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True)  # noqa: S607
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True)  # noqa: S607
    return repo


def test_install_sets_local_alias_only(bare_repo_clone: Path) -> None:
    status = SC.install(repo_root=bare_repo_clone)
    assert "installed" in status
    result = subprocess.run(  # noqa: S607
        ["git", "-C", str(bare_repo_clone), "config", "--local", "--get", "alias.ship"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "ship_ceremony.py" in result.stdout


def test_install_refuses_to_overwrite_unrelated_alias(bare_repo_clone: Path) -> None:
    subprocess.run(  # noqa: S607
        ["git", "-C", str(bare_repo_clone), "config", "--local", "alias.ship", "!echo mine"],
        check=True,
    )
    with pytest.raises(SC.ShipCeremonyError, match="alias.ship already set"):
        SC.install(repo_root=bare_repo_clone)


def test_install_is_idempotent_on_same_target(bare_repo_clone: Path) -> None:
    SC.install(repo_root=bare_repo_clone)
    status = SC.install(repo_root=bare_repo_clone)
    assert "no-op" in status


def test_install_force_overwrites(bare_repo_clone: Path) -> None:
    subprocess.run(  # noqa: S607
        ["git", "-C", str(bare_repo_clone), "config", "--local", "alias.ship", "!echo mine"],
        check=True,
    )
    status = SC.install(repo_root=bare_repo_clone, force=True)
    assert "installed" in status


def test_uninstall_when_no_alias_is_idempotent(bare_repo_clone: Path) -> None:
    status = SC.uninstall(repo_root=bare_repo_clone)
    assert "removed" in status or "absent" in status


def test_uninstall_leaves_no_residue(bare_repo_clone: Path) -> None:
    SC.install(repo_root=bare_repo_clone)
    SC.uninstall(repo_root=bare_repo_clone)
    result = subprocess.run(  # noqa: S607
        ["git", "-C", str(bare_repo_clone), "config", "--local", "--get", "alias.ship"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


# --------------------------------------------------------------------------- #
# Skill-doc drift guard (R6/AC6): no raw ceremony git/gh commands may remain in
# work/SKILL.md once it delegates to ship_ceremony.py.
# --------------------------------------------------------------------------- #

WORK_SKILL_PATH = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"


def test_skill_doc_no_raw_ceremony_commands() -> None:
    import re

    text = WORK_SKILL_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"git (checkout|pull|branch -d)|gh pr (create|merge)")
    assert not pattern.search(text), "raw ceremony git/gh commands leaked back into work/SKILL.md"


def test_skill_doc_references_ship_ceremony() -> None:
    text = WORK_SKILL_PATH.read_text(encoding="utf-8")
    assert "ship_ceremony.py" in text
