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
    # Issue #347: teardown is the new terminal transition appended after branch_delete,
    # so branch_delete is no longer the end — teardown is, and only after teardown does
    # next_transition report the ceremony complete (AC6, structurally non-skippable).
    assert SC.next_transition("branch_delete") == "teardown"
    assert SC.next_transition("teardown") is None


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
    (passed through here unchanged) are the only thing that touch disk.

    Extended for issue #346/U4: ``pr view <number-or-branch>`` now answers whatever
    subset of ``--json`` fields is requested (``ceremony_hazards.py`` asks for
    ``state,mergedAt``; ``merge_watcher.py`` asks for
    ``number,state,headRefOid,statusCheckRollup,reviewDecision``) — ``headRefOid``
    is resolved live against the real branch HEAD in ``self.repo`` so a commit
    pushed between ``record`` and ``validate`` genuinely shows up as ``head_moved``.
    ``pr list --base <branch> --state open`` answers from the same PR table,
    filtered by each entry's recorded ``base`` (default ``"main"``) — the probe
    ``ceremony_hazards.py`` uses to detect a stacked-PR topology.
    """

    def __init__(self, repo: Path, bare_origin: Path) -> None:
        self.repo = repo
        self.bare_origin = bare_origin
        self._next_number = 1
        self._prs: dict[str, dict[str, object]] = {}  # branch -> pr record
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

    def add_stacked_pr(self, *, base_branch: str, head_branch: str, title: str = "") -> int:
        """Test-setup helper (not reachable via ship_ceremony's own gh argv shapes,
        which never pass ``--base``): register an open PR whose base is
        ``base_branch``, so ``ceremony_hazards.py``'s ``pr list --base`` probe finds
        it. The head branch need not exist as a real git ref — the stacked-PR probe
        only reads ``number``/``title`` from ``pr list``, never ``pr view``."""
        number = self._next_number
        self._next_number += 1
        self._prs[head_branch] = {
            "number": number,
            "draft": False,
            "body": "",
            "base": base_branch,
            "title": title,
            "state": "OPEN",
            "mergedAt": None,
            "checks": [],
            "reviewDecision": None,
        }
        return number

    def _head_ref_oid(self, branch: str) -> str:
        result = self._real_run(  # nosec B603
            ["git", "rev-parse", branch],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()

    def _pr_by_ref(self, ref: str) -> tuple[str, dict[str, object]]:
        if ref in self._prs:
            return ref, self._prs[ref]
        try:
            number = int(ref)
        except ValueError:
            raise AssertionError(f"unknown pr ref {ref!r}") from None
        for branch, pr in self._prs.items():
            if pr["number"] == number:
                return branch, pr
        raise AssertionError(f"unknown pr ref {ref!r}")

    def _handle_gh(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["pr", "create"]:
            draft = "--draft" in args
            branch = args[args.index("--head") + 1]
            body = args[args.index("--body") + 1] if "--body" in args else ""
            base = args[args.index("--base") + 1] if "--base" in args else "main"
            number = self._next_number
            self._next_number += 1
            self._prs[branch] = {
                "number": number,
                "draft": draft,
                "body": body,
                "base": base,
                "state": "OPEN",
                "mergedAt": None,
                "checks": [],
                "reviewDecision": None,
            }
            return _ok(str(number))
        if args[:2] == ["pr", "view"]:
            ref = args[2]
            branch, pr = self._pr_by_ref(ref)
            fields = args[args.index("--json") + 1].split(",")
            payload: dict[str, object] = {}
            for field in fields:
                if field == "number":
                    payload["number"] = pr["number"]
                elif field == "state":
                    payload["state"] = pr["state"]
                elif field == "mergedAt":
                    payload["mergedAt"] = pr["mergedAt"]
                elif field == "headRefOid":
                    payload["headRefOid"] = self._head_ref_oid(branch)
                elif field == "statusCheckRollup":
                    payload["statusCheckRollup"] = pr["checks"]
                elif field == "reviewDecision":
                    payload["reviewDecision"] = pr["reviewDecision"]
            return _ok(json.dumps(payload))
        if args[:2] == ["pr", "ready"]:
            for pr in self._prs.values():
                if pr["number"] == int(args[2]):
                    pr["draft"] = False
            return _ok("")
        if args[:2] == ["pr", "edit"]:
            return _ok("")
        if args[:2] == ["pr", "list"]:
            list_base = args[args.index("--base") + 1] if "--base" in args else None
            state = args[args.index("--state") + 1] if "--state" in args else None
            results = []
            for pr in self._prs.values():
                if list_base is not None and pr.get("base") != list_base:
                    continue
                if state == "open" and pr.get("state") != "OPEN":
                    continue
                results.append({"number": pr["number"], "title": pr.get("title", "")})
            return _ok(json.dumps(results))
        if args[:2] == ["pr", "close"]:
            number = int(args[2])
            for pr in self._prs.values():
                if pr["number"] == number:
                    pr["state"] = "CLOSED"
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
            self._prs[branch]["state"] = "MERGED"
            self._prs[branch]["mergedAt"] = "2026-07-11T00:00:00Z"
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


def _confirm_for(transition: str) -> str | None:
    """Operator confirmation for ``transition`` when its tier demands one (#526)."""
    if SC.TRANSITION_TIERS[transition] == SC.CeremonyTier.ALWAYS_OPERATOR:
        return transition
    return None


def _origin_main_sha(bare_origin: Path) -> str:
    out = subprocess.run(  # noqa: S607
        ["git", "ls-remote", str(bare_origin), "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.split()[0]


# --------------------------------------------------------------------------- #
# Integration tests
# --------------------------------------------------------------------------- #


def test_full_ceremony_throwaway_branch(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        status = SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )
        assert expected in status

    saga = _restore(repo)
    # Issue #347: the ceremony now ends at teardown (tier reversible), not branch_delete.
    assert saga["ceremony_transition"] == "teardown"
    assert saga["ceremony_tier"] == SC.CeremonyTier.REVERSIBLE
    # teardown reconciled the opened-resource manifest clean (branch + PR both closed by
    # their transitions) and minted the immutable receipt.
    receipt = repo / ".claude" / "saga" / "sagas" / "issue-345" / "ship_receipt.json"
    assert receipt.exists()
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
    status = SC.run(
        repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh
    )
    assert "merge" in status
    assert len(fake_gh._prs) == 1  # noqa: SLF001 - test introspection of the fake


def test_already_complete_ceremony_is_a_noop(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )
    status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "already shipped" in status


# --------------------------------------------------------------------------- #
# Operator-confirmation gate (issue #526) — R1-R4/KTD2-KTD4.
# --------------------------------------------------------------------------- #


def _advance_to(repo: Path, fake_gh: FakeGh, target: str) -> None:
    """Drive ``run`` up to (not including) ``target``, passing operator confirmation
    for any always_operator-tier transition in the prefix so the helper itself never
    trips the gate it exists to set up a precondition for."""
    for expected in SC.TRANSITIONS:
        if expected == target:
            return
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )


def test_bare_run_at_merge_refuses_and_names_the_transition(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    origin_main_before = _origin_main_sha(fake_gh.bare_origin)
    with pytest.raises(SC.OperatorConfirmationError, match="merge"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert _restore(repo)["ceremony_transition"] == "request_review"
    # The merge runner's only observable side effect is pushing the branch to the
    # origin's main ref — prove the runner never ran (R1), not just that no save landed.
    assert _origin_main_sha(fake_gh.bare_origin) == origin_main_before


def test_bare_run_at_branch_delete_refuses_and_names_the_transition(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    assert _restore(repo)["ceremony_transition"] == "pull"
    with pytest.raises(SC.OperatorConfirmationError, match="branch_delete"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert _restore(repo)["ceremony_transition"] == "pull"
    branches = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "branch"], check=True, capture_output=True, text=True
    ).stdout
    assert "feat/pf-throwaway-345" in branches  # R1: the delete runner never ran


def test_operator_confirmed_merge_executes_and_records_tier(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    status = SC.run(
        repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh
    )
    assert "merge" in status
    saga = _restore(repo)
    assert saga["ceremony_transition"] == "merge"
    assert saga["ceremony_tier"] == SC.CeremonyTier.ALWAYS_OPERATOR


def test_operator_confirmed_mismatch_refuses_even_on_a_reversible_step(ceremony_repo) -> None:
    """KTD4: the mismatch rule is uniform across tiers — a confirmation naming a
    transition other than the upcoming one refuses even when the upcoming transition
    is itself reversible."""
    repo, fake_gh = ceremony_repo
    with pytest.raises(SC.OperatorConfirmationError, match="merge"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh)
    assert _restore(repo)["ceremony_transition"] == ""


def test_operator_confirmed_mismatch_between_two_gated_steps_refuses(ceremony_repo) -> None:
    """KTD4 from the gated side: a confirmation naming ``branch_delete`` while the
    upcoming transition is ``merge`` (both always_operator-tier) refuses, names both
    transitions, and leaves the ledger unadvanced."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    with pytest.raises(SC.OperatorConfirmationError, match=r"branch_delete.*merge"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="branch_delete",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "request_review"


def test_bare_run_over_reversible_prefix_is_unchanged(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    for expected in ("commit", "open_pr", "request_review"):
        status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
        assert expected in status
    assert _restore(repo)["ceremony_transition"] == "request_review"


def test_operator_confirmed_flag_on_already_shipped_ceremony_is_still_a_noop(
    ceremony_repo,
) -> None:
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )
    status = SC.run(
        repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh
    )
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
    with pytest.raises(SC.AmbiguousSagaError, match="multiple live sagas match branch"):
        SC.resolve_saga(repo_root=repo, issue_ref=None, runner=fake_gh)


def test_resolve_by_saga_id_ignores_current_branch(ceremony_repo) -> None:
    """An explicit ``--saga-id`` resolves the saga regardless of the current branch — the fix that
    lets a task-kind ceremony finish cleanup after ``checkout_main`` moves off the work branch,
    where by-branch resolution can no longer find the saga (its recorded branch is the feature
    branch, not ``main``)."""
    repo, fake_gh = ceremony_repo
    subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "checkout", "-b", "somewhere-else"],
        check=True,
        capture_output=True,
    )
    resolved = SC.resolve_saga(repo_root=repo, saga_id="issue-345", runner=fake_gh)
    assert resolved["saga_id"] == "issue-345"


def test_by_branch_fallback_ignores_terminal_sagas(ceremony_repo) -> None:
    """A ``done``/``abandoned`` saga left on the branch is never a live ceremony target, so
    by-branch resolution skips it instead of raising ambiguous — the pile of terminal sagas
    frozen on ``main`` was what forced the manual cleanup on this campaign's ceremonies."""
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
            "terminal-decoy",
            "--status",
            "done",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    # The terminal decoy shares the branch but must not make resolution ambiguous.
    resolved = SC.resolve_saga(repo_root=repo, issue_ref=None, runner=fake_gh)
    assert resolved["saga_id"] == "issue-345"


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


def test_open_pr_body_autocloses_issue_via_fixes_line(ceremony_repo) -> None:
    """The fresh-create ``open_pr`` path injects ``Fixes #N`` (from the saga's ``issue_ref``) into
    the PR body, so merging auto-closes the tracked issue instead of leaving the easy-to-forget
    manual close (the #477 miss). The plan link is preserved alongside it."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    body = fake_gh._prs["feat/pf-throwaway-345"]["body"]  # noqa: SLF001
    assert "Fixes #345" in body
    assert "Plan: docs/plans/x-plan.md" in body


# --------------------------------------------------------------------------- #
# Issue #346 (U4): hazard preflight, merge-watcher preflight, rollback manifest,
# and `run --undo` wiring.
# --------------------------------------------------------------------------- #

BRANCH_345 = "feat/pf-throwaway-345"


def test_branch_delete_refused_on_stacked_pr_until_acknowledged(ceremony_repo) -> None:
    """R1/KTD3: an open PR based on the branch about to be deleted refuses
    branch_delete until acknowledged; the refusal leaves origin's main SHA and the
    ledger unchanged, and `--acknowledge-hazard stacked_pr` unlocks it."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    assert _restore(repo)["ceremony_transition"] == "pull"
    origin_main_before = _origin_main_sha(fake_gh.bare_origin)

    fake_gh.add_stacked_pr(
        base_branch=BRANCH_345, head_branch="feat/child-of-345", title="child work"
    )

    with pytest.raises(SC.HazardRefusedError, match="stacked_pr"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="branch_delete",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "pull"
    assert _origin_main_sha(fake_gh.bare_origin) == origin_main_before
    branches = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "branch"], check=True, capture_output=True, text=True
    ).stdout
    assert BRANCH_345 in branches  # the delete runner never ran

    status = SC.run(
        repo_root=repo,
        issue_ref="org/repo#345",
        operator_confirmed="branch_delete",
        acknowledge_hazard=["stacked_pr"],
        runner=fake_gh,
    )
    assert "branch_delete" in status
    assert _restore(repo)["ceremony_transition"] == "branch_delete"


def test_merge_not_landed_blocks_branch_delete_and_is_not_acknowledgeable(ceremony_repo) -> None:
    """R2/KTD3: a delete request arriving before the ceremony PR's state is
    confirmably MERGED is refused and CANNOT be bypassed via
    --acknowledge-hazard — it resolves only by the merge actually landing."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # request_review
    assert fake_gh._prs[BRANCH_345]["state"] == "OPEN"  # noqa: SLF001 - never merged

    # Force the ledger straight to "pull" without ever running merge/checkout_main
    # — models the R2 reorder hazard (a delete request racing ahead of a merge that
    # has not confirmably landed), without needing a real `gh pr merge --auto`.
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
            "pull",
            "--ceremony-tier",
            "reversible",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(SC.HazardRefusedError, match="merge_not_landed"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="branch_delete",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "pull"

    with pytest.raises(SC.HazardRefusedError, match="merge_not_landed"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="branch_delete",
            acknowledge_hazard=["merge_not_landed"],
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "pull"
    branches = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "branch"], check=True, capture_output=True, text=True
    ).stdout
    assert BRANCH_345 in branches


def test_merge_preflight_validates_expectation_and_diverged_blocks(ceremony_repo) -> None:
    """R4: a commit pushed after review — moving HEAD past the recorded baseline —
    is a named `head_moved` divergence that blocks merge before dispatch, leaving
    origin's main SHA and the ledger unchanged (ledger-unadvanced proof)."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # request_review
    origin_main_before = _origin_main_sha(fake_gh.bare_origin)

    (repo / "late_change.txt").write_text("late\n")
    subprocess.run(["git", "-C", str(repo), "add", "late_change.txt"], check=True)  # noqa: S607
    subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "commit", "-m", "late change"], check=True, capture_output=True
    )

    with pytest.raises(SC.MergePreflightError, match="head_moved"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh)
    assert _restore(repo)["ceremony_transition"] == "request_review"
    assert _origin_main_sha(fake_gh.bare_origin) == origin_main_before


def test_missing_merge_expectation_refuses_before_dispatch(ceremony_repo) -> None:
    """KTD8: reaching merge with no merge_expectation.json sidecar (an in-flight
    ceremony predating this feature, or a deleted sidecar) is a named refusal
    naming the `record` remedy, never a silent pass."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # request_review
    sidecar = repo / ".claude" / "saga" / "sagas" / "issue-345" / "merge_expectation.json"
    assert sidecar.exists()
    sidecar.unlink()

    with pytest.raises(SC.MergePreflightError, match="no merge_expectation.json"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh)
    assert _restore(repo)["ceremony_transition"] == "request_review"


def test_open_pr_and_start_both_record_expectation(ceremony_repo) -> None:
    """R3: both record sites — the `run()` path reaching `open_pr` and the
    front-loaded `start()` path — write the merge-watcher sidecar before any poll
    loop exists."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr

    sidecar_a = repo / ".claude" / "saga" / "sagas" / "issue-345" / "merge_expectation.json"
    assert sidecar_a.exists()
    expectation_a = json.loads(sidecar_a.read_text())
    head_sha = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "rev-parse", BRANCH_345],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert expectation_a["head_sha"] == head_sha
    assert expectation_a["pr_number"] == fake_gh._prs[BRANCH_345]["number"]  # noqa: SLF001

    # A fresh saga on a new branch, driven through start() — avoids both start()'s
    # "already in progress" refusal and a by-branch ambiguous match against 345.
    subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "checkout", "main"], check=True, capture_output=True
    )
    subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "checkout", "-b", "feat/pf-throwaway-999"],
        check=True,
        capture_output=True,
    )
    (repo / "second.txt").write_text("second saga scaffold\n")
    subprocess.run(["git", "-C", str(repo), "add", "second.txt"], check=True)  # noqa: S607
    subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "commit", "-m", "second scaffold"],
        check=True,
        capture_output=True,
    )
    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(saga_py),
            "save",
            "--kind",
            "issue",
            "--id",
            "999",
            "--issue-ref",
            "org/repo#999",
            "--lifecycle-phase",
            "work",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    SC.start(repo_root=repo, issue_ref="org/repo#999", runner=fake_gh)
    sidecar_b = repo / ".claude" / "saga" / "sagas" / "issue-999" / "merge_expectation.json"
    assert sidecar_b.exists()


def test_manifest_appended_per_transition_in_full_ceremony(ceremony_repo) -> None:
    """R6: every successful ceremony transition appends one rollback-manifest entry,
    in order, each starting unmarked (undone=False)."""
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )

    manifest = repo / ".claude" / "saga" / "sagas" / "issue-345" / "rollback_manifest.json"
    entries = json.loads(manifest.read_text())
    assert [e["transition"] for e in entries] == list(SC.TRANSITIONS)
    assert all(e["undone"] is False for e in entries)

    by_transition = {e["transition"]: e for e in entries}
    assert by_transition["commit"]["remote_created"] is True
    assert by_transition["commit"]["head_sha"]
    assert by_transition["open_pr"]["pr_number"] == str(fake_gh._prs[BRANCH_345]["number"])  # noqa: SLF001, E501
    assert by_transition["merge"]["merge_sha"]
    assert by_transition["merge"]["pre_merge_main_sha"]
    assert by_transition["merge"]["merge_sha"] != by_transition["merge"]["pre_merge_main_sha"]
    assert by_transition["branch_delete"]["head_sha"]


def test_run_undo_dispatches_to_ship_undo_and_gh_ship_alias_shape_unchanged(
    ceremony_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    """KTD6: `--undo` is a flag on the existing `run` subcommand, so it dispatches
    straight to `ship_undo.undo()` and the installed `git ship` alias
    (`!python3 <script> run`, which appends trailing args unchanged) keeps working
    unmodified as `git ship --undo` — no reinstall, no second subcommand."""
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    assert fake_gh._prs[BRANCH_345]["state"] == "OPEN"  # noqa: SLF001

    status = SC.run(repo_root=repo, issue_ref="org/repo#345", undo=True, runner=fake_gh)
    assert "reverted 2" in status
    assert fake_gh._prs[BRANCH_345]["state"] == "CLOSED"  # noqa: SLF001

    alias_status = SC.install(repo_root=repo)
    assert "installed" in alias_status
    alias = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "config", "--local", "--get", "alias.ship"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert alias.endswith(" run")
    assert "undo" not in alias

    original = SC.subprocess.run
    SC.subprocess.run = fake_gh
    try:
        exit_code = SC.main(
            [
                "--repo-root",
                str(repo),
                "run",
                "--issue-ref",
                "org/repo#345",
                "--operator-confirmed",
                "undo",
                "--undo",
            ]
        )
    finally:
        SC.subprocess.run = original
    assert exit_code == 0
    assert "no-op" in capsys.readouterr().out  # already fully undone above


def test_full_ceremony_green_path_unchanged_when_no_hazards(ceremony_repo) -> None:
    """Regression: a clean topology with no hazards completes the whole ceremony
    exactly as the pre-#346 four-invocation #526 flow did — the new preflights are
    silent additions on the happy path, and both new sidecars exist as evidence the
    hooks actually engaged rather than being silently skipped."""
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        status = SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )
        assert expected in status

    saga = _restore(repo)
    # Issue #347: teardown is the terminal transition now (tier reversible).
    assert saga["ceremony_transition"] == "teardown"
    assert saga["ceremony_tier"] == SC.CeremonyTier.REVERSIBLE

    sidecar = repo / ".claude" / "saga" / "sagas" / "issue-345" / "merge_expectation.json"
    manifest = repo / ".claude" / "saga" / "sagas" / "issue-345" / "rollback_manifest.json"
    assert sidecar.exists()
    entries = json.loads(manifest.read_text())
    assert [e["transition"] for e in entries] == list(SC.TRANSITIONS)


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
    with pytest.raises(SC.NoSagaError, match="no live saga found for branch"):
        SC.resolve_saga(repo_root=repo, issue_ref=None)


def test_merge_before_open_pr_is_a_named_failure(ceremony_repo) -> None:
    """Reaching merge with no merge-watcher expectation recorded (open_pr was
    skipped or its save was lost, so ``merge_watcher.record`` never ran) is a named
    failure, not a crash or a silent no-op. (issue #346/KTD8: the merge preflight's
    ``merge_watcher.validate`` call — which runs before ``_RUNNERS['merge']``
    dispatch — now catches this case earlier than ``_current_pr_number``'s own
    'no pr_refs recorded' guard inside ``_do_merge`` ever gets a chance to; request_review
    no longer exercises this path at all — issue #477 made it a deliberate no-op,
    since this repo has no second maintainer to request review from.)"""
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
    with pytest.raises(SC.MergePreflightError, match="no merge_expectation.json"):
        SC.run(repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh)


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


def test_cli_main_run_at_gated_step_exits_nonzero_without_confirmation(
    ceremony_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, fake_gh = ceremony_repo
    original = SC.subprocess.run
    SC.subprocess.run = fake_gh
    try:
        for _ in range(3):  # commit, open_pr, request_review
            SC.main(["--repo-root", str(repo), "run", "--issue-ref", "org/repo#345"])
        capsys.readouterr()
        exit_code = SC.main(["--repo-root", str(repo), "run", "--issue-ref", "org/repo#345"])
    finally:
        SC.subprocess.run = original
    assert exit_code == 1
    assert "merge" in capsys.readouterr().err
    assert _restore(repo)["ceremony_transition"] == "request_review"


def test_cli_main_run_with_operator_confirmed_proceeds(
    ceremony_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, fake_gh = ceremony_repo
    original = SC.subprocess.run
    SC.subprocess.run = fake_gh
    try:
        for _ in range(3):  # commit, open_pr, request_review
            SC.main(["--repo-root", str(repo), "run", "--issue-ref", "org/repo#345"])
        capsys.readouterr()
        exit_code = SC.main(
            [
                "--repo-root",
                str(repo),
                "run",
                "--issue-ref",
                "org/repo#345",
                "--operator-confirmed",
                "merge",
            ]
        )
    finally:
        SC.subprocess.run = original
    assert exit_code == 0
    assert "merge" in capsys.readouterr().out
    assert _restore(repo)["ceremony_transition"] == "merge"


def test_cli_main_rejects_off_palette_operator_confirmed_value(
    ceremony_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    """An off-palette --operator-confirmed value is argparse's error, not the gate's:
    usage message + exit code 2 (vs the ShipCeremonyError boundary's
    ship_ceremony:-prefixed stderr + exit 1) — pinned so the distinct shape is
    intentional, not accidental."""
    repo, _fake_gh = ceremony_repo
    with pytest.raises(SystemExit) as excinfo:
        SC.main(
            [
                "--repo-root",
                str(repo),
                "run",
                "--issue-ref",
                "org/repo#345",
                "--operator-confirmed",
                "bogus",
            ]
        )
    assert excinfo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


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
# Issue #347 (U4): terminal `teardown` transition, immutable receipt mint, and the
# register-on-open / close-on-close manifest wiring at the ceremony's own call sites.
# These ride the same ceremony_repo + FakeGh rig — teardown reconciles the
# opened-resource manifest (a real ship_teardown sidecar under the saga dir), so the
# oracles below assert real sidecar state, not a fake.
# --------------------------------------------------------------------------- #


def _opened_manifest(repo: Path) -> dict[str, Any]:
    # SC is importlib-loaded, so its attributes are Any to mypy — dict() restores the type.
    return dict(SC.ship_teardown.read_manifest(repo, "issue-345"))


def test_AC_6_terminal_transition_not_skippable(ceremony_repo) -> None:
    """AC6: teardown is appended last, so it is structurally the terminal transition —
    ``TRANSITIONS[-1]`` is teardown and ``next_transition('branch_delete')`` is teardown,
    not ``None``. A partial-failure path (the remote branch-delete leg failing on its
    ``check=False`` call) still reaches teardown and lands at an explicit terminal state
    (the receipt), never skipping the gate to 'already shipped'."""
    assert SC.TRANSITIONS[-1] == "teardown"
    assert SC.next_transition("branch_delete") == "teardown"

    repo, fake_gh = ceremony_repo
    # Fail exactly the remote branch-delete leg (the check=False call in
    # _do_branch_delete) — branch_delete still succeeds locally and the ceremony must
    # still reach teardown rather than stalling.
    failing = FailingRunner(fake_gh, fail_prefix=["git", "push", "origin", "--delete"])
    for expected in SC.TRANSITIONS:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=failing,
        )

    saga = _restore(repo)
    assert saga["ceremony_transition"] == "teardown"
    receipt = repo / ".claude" / "saga" / "sagas" / "issue-345" / "ship_receipt.json"
    assert receipt.exists(), "teardown must reach the receipt even on the partial-delete path"


def test_AC_1_blocks_on_nonzero_closing_count(ceremony_repo) -> None:
    """AC1: two orphan worktree entries + one open background_session on the manifest
    make the closing count non-zero; teardown refuses, names all three, leaves the saga's
    ceremony_transition unadvanced (still branch_delete), and mints no receipt."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "teardown")  # drives commit..branch_delete
    assert _restore(repo)["ceremony_transition"] == "branch_delete"

    # Seed the AC1 blocker shape onto the ceremony's own opened-resource manifest.
    SC.ship_teardown.register(
        repo,
        "issue-345",
        "wt-orphan-1",
        kind="worktree",
        ref="/tmp/pf-orphan-1",
        opened_by="reclaim",
    )
    SC.ship_teardown.register(
        repo,
        "issue-345",
        "wt-orphan-2",
        kind="worktree",
        ref="/tmp/pf-orphan-2",
        opened_by="reclaim",
    )
    SC.ship_teardown.register(
        repo, "issue-345", "sess-1", kind="background_session", ref="sess-abc", opened_by="spawn"
    )

    with pytest.raises(SC.ship_receipt.TeardownBlockedError) as excinfo:
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)

    message = str(excinfo.value)
    assert "/tmp/pf-orphan-1" in message
    assert "/tmp/pf-orphan-2" in message
    assert "sess-abc" in message
    # Ledger provably unadvanced: teardown raised before append_entry + save.
    assert _restore(repo)["ceremony_transition"] == "branch_delete"
    receipt = repo / ".claude" / "saga" / "sagas" / "issue-345" / "ship_receipt.json"
    assert not receipt.exists()


def test_teardown_happy_path_mints_receipt_then_already_shipped(ceremony_repo) -> None:
    """Happy path: a fully-closed manifest reconciles clean, teardown mints the receipt
    recording what opened and closed, records ceremony_transition=teardown, and a
    subsequent run reports 'already shipped'."""
    repo, fake_gh = ceremony_repo
    for expected in SC.TRANSITIONS:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "teardown"

    receipt = SC.ship_receipt.read(repo, "issue-345", reprobe=False)
    # The branch + PR the ceremony opened are recorded, both closed.
    opened = receipt["opened"]
    branch_id = SC._branch_resource_id(BRANCH_345)
    assert branch_id in opened
    assert opened[branch_id]["closed_at"] != ""
    assert any(entry["kind"] == "draft_pr" for entry in opened.values())
    assert receipt["closed"]["closing_count"] == 0
    assert receipt["ceremony"]["final_transition"] == "teardown"

    status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "already shipped" in status


def test_pre_0_78_0_saga_at_branch_delete_reports_teardown_pending(ceremony_repo) -> None:
    """Compat (KTD3): a saga whose last recorded transition is branch_delete (an
    in-flight or completed pre-0.78.0 ceremony) regains exactly one pending transition —
    teardown — rather than reporting 'already shipped'. The old ceremony gets the gate."""
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
            "branch_delete",
            "--ceremony-tier",
            "always_operator",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    saga = _restore(repo)
    assert SC.next_transition(saga["ceremony_transition"]) == "teardown"

    # A bare run runs teardown (no operator confirm — reversible), not "already shipped".
    # The pre-0.78.0 saga has no opened_resources manifest, so reconcile is trivially
    # clean and the receipt mints.
    status = SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert "teardown" in status
    assert "already shipped" not in status
    assert _restore(repo)["ceremony_transition"] == "teardown"


def test_undo_teardown_entry_is_forward_only_noop(ceremony_repo) -> None:
    """Undo: a rollback manifest carrying a teardown entry is a forward-only no-op —
    undo reverts it (marks it undone) without crashing on the new transition name and
    without any git/gh side effect (a raising runner proves nothing was shelled out)."""
    repo, _fake_gh = ceremony_repo
    SC.ship_undo.append_entry(
        repo_root=repo, saga_id="issue-345", transition="teardown", tier="reversible"
    )

    def _raising_runner(cmd, **kwargs):  # noqa: ANN001
        raise AssertionError(f"teardown undo must not shell out, but tried: {cmd!r}")

    status = SC.ship_undo.undo({"saga_id": "issue-345"}, repo_root=repo, runner=_raising_runner)
    assert "reverted 1" in status


# ---- Per-call-site register/close oracles (KTD9) ---------------------------- #


def test_commit_registers_branch_on_manifest(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    manifest = _opened_manifest(repo)
    branch_id = SC._branch_resource_id(BRANCH_345)
    assert branch_id in manifest
    assert manifest[branch_id]["kind"] == "branch"
    assert manifest[branch_id]["closed_at"] == ""  # opened, not yet closed


def test_open_pr_registers_pr_on_manifest(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr
    pr_number = str(fake_gh._prs[BRANCH_345]["number"])  # noqa: SLF001
    pr_id = SC._pr_resource_id(pr_number)
    manifest = _opened_manifest(repo)
    assert pr_id in manifest
    assert manifest[pr_id]["kind"] == "draft_pr"
    assert manifest[pr_id]["closed_at"] == ""


def test_merge_closes_pr_entry_with_merge_evidence(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    pr_number = str(fake_gh._prs[BRANCH_345]["number"])  # noqa: SLF001
    SC.run(repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh)
    manifest = _opened_manifest(repo)
    pr_entry = manifest[SC._pr_resource_id(pr_number)]
    assert pr_entry["closed_at"] != ""
    assert "merged:" in pr_entry["close_evidence"]


def test_branch_delete_closes_branch_entry_with_head_evidence(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    SC.run(
        repo_root=repo,
        issue_ref="org/repo#345",
        operator_confirmed="branch_delete",
        runner=fake_gh,
    )
    manifest = _opened_manifest(repo)
    branch_entry = manifest[SC._branch_resource_id(BRANCH_345)]
    assert branch_entry["closed_at"] != ""
    assert "deleted head:" in branch_entry["close_evidence"]


def test_start_registers_branch_and_pr(ceremony_repo) -> None:
    repo, fake_gh = ceremony_repo
    SC.start(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    manifest = _opened_manifest(repo)
    branch_id = SC._branch_resource_id(BRANCH_345)
    pr_number = str(fake_gh._prs[BRANCH_345]["number"])  # noqa: SLF001
    pr_id = SC._pr_resource_id(pr_number)
    assert branch_id in manifest and manifest[branch_id]["kind"] == "branch"
    assert pr_id in manifest and manifest[pr_id]["kind"] == "draft_pr"


def test_close_if_registered_no_ops_on_absent_entry(ceremony_repo) -> None:
    """A close call for a resource the ceremony never registered (a pre-wiring saga, or
    a forced-state jump straight to merge) is a silent no-op — it must not raise the
    fail-loud UnknownResourceError that ship_teardown.close would on a bare call."""
    repo, _fake_gh = ceremony_repo
    saga = {"saga_id": "issue-345"}
    # No manifest entry exists for this id; the guarded helper must not raise.
    SC._close_if_registered(saga, SC._pr_resource_id("999"), repo_root=repo, evidence="x")


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
