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
    # Register BEFORE exec (the same order ``_load_ship_undo`` in tests/test_ship_undo.py
    # already uses): ship_ceremony.py carries ``from __future__ import annotations``, so
    # every annotation is a string, and ``@dataclass`` resolves those strings through
    # ``sys.modules[cls.__module__].__dict__``. An unregistered module makes that lookup
    # return None and the decorator raise at import time.
    sys.modules[spec.name] = module
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
                elif field == "headRefName":
                    # Issue #635/U1: the ceremony ref resolver's rung 1 asks for
                    # headRefName,baseRefName. The head is the branch the PR was
                    # created from; the base is whatever `--base` said (default main).
                    payload["headRefName"] = branch
                elif field == "baseRefName":
                    payload["baseRefName"] = pr["base"]
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
    # Issue #635/U3: a real `git clone` of a NON-empty remote auto-configures
    # `refs/remotes/origin/HEAD`. This fixture clones an EMPTY bare origin (the push to
    # `main` happens after), so that symbolic ref is never set — leaving
    # `resolve_default_branch`'s rung 1 with nothing to answer and falling through to
    # `gh repo view`, which `FakeGh` does not implement. Set it explicitly so every
    # ceremony test (existing and new) resolves the default branch locally, exactly as
    # a normal clone would have.
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        ],
        check=True,
        capture_output=True,
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


def _confirm_for(transition: str, *, target: str = "feat/pf-throwaway-345") -> str | None:
    """Operator confirmation for ``transition`` when its tier demands one (#526).

    Issue #635/KTD6: ``branch_delete`` now confirms a NAMED TARGET as well as the
    transition, so the helper emits the qualified ``branch_delete:<head>`` form. Every
    other transition's bare grammar is untouched — which is exactly what the callers of
    this helper (the full-ceremony walk, ``_advance_to``, the already-shipped no-op)
    keep regression-proving."""
    if SC.TRANSITION_TIERS[transition] != SC.CeremonyTier.ALWAYS_OPERATOR:
        return None
    if transition in SC.CONFIRMATION_TARGET_TRANSITIONS:
        return f"{transition}:{target}"
    return transition


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
            operator_confirmed=f"branch_delete:{BRANCH_345}",
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
        operator_confirmed=f"branch_delete:{BRANCH_345}",
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
            operator_confirmed=f"branch_delete:{BRANCH_345}",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "pull"

    with pytest.raises(SC.HazardRefusedError, match="merge_not_landed"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=f"branch_delete:{BRANCH_345}",
            acknowledge_hazard=["merge_not_landed"],
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "pull"
    branches = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "branch"], check=True, capture_output=True, text=True
    ).stdout
    assert BRANCH_345 in branches


# --------------------------------------------------------------------------- #
# Issue #635 (U4): the branch_delete_targets_base hazard (R2) and the KTD6
# `--operator-confirmed branch_delete:<target>` named-target grammar (R8).
# --------------------------------------------------------------------------- #


class _RecordingRunner:
    """Wraps a runner and records every argv it is asked to execute, so a refusal can
    be shown to have happened BEFORE `_RUNNERS[upcoming]` dispatch and before the
    `saga.py save` — the ledger-unadvanced proof shape #526/#346/#347 rely on.

    Note the honest scope of the "nothing ran" claim: `resolve_saga` and
    `resolve_ceremony_refs` both shell out (git/gh) BEFORE any gate can fire, by
    construction. What must not appear is any MUTATING command — no `git branch -d`,
    no `git push`, no `git checkout`, and no `saga.py save`."""

    _MUTATING_GIT = ("branch", "push", "checkout", "merge", "commit", "reset", "revert")
    # Every spelling of a branch deletion. `-d` alone let `git branch -D <b>` and
    # `git branch --delete <b>` slip through the read-only skip below, which would make
    # `mutating_calls() == []` vacuously true for the deletion command if production
    # ever changed the flag — the oracle would stop failing exactly when it mattered.
    _DELETE_FLAGS = ("-d", "-D", "--delete")

    def __init__(self, inner) -> None:  # noqa: ANN001
        self._inner = inner
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        self.calls.append(list(cmd))
        return self._inner(cmd, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout)

    def mutating_calls(self) -> list[list[str]]:
        found = []
        for call in self.calls:
            if call[:1] == ["git"] and len(call) > 1 and call[1] in self._MUTATING_GIT:
                # `git branch --show-current` / `git branch --list` only read.
                if call[1] == "branch" and not any(a in self._DELETE_FLAGS for a in call[2:]):
                    continue
                found.append(call)
            elif "saga.py" in " ".join(call) and "save" in call:
                found.append(call)
        return found


def _local_branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(  # noqa: S607
        ["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _remote_branch_exists(bare_origin: Path, branch: str) -> bool:
    result = subprocess.run(  # noqa: S607
        ["git", "ls-remote", str(bare_origin), f"refs/heads/{branch}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def test_branch_delete_targets_base_refuses_before_dispatch_and_before_save(
    ceremony_repo,
) -> None:
    """R2/KTD3: when the resolved deletion target IS the PR's base branch, the hazard
    refuses ahead of `_RUNNERS[upcoming]` and ahead of `saga.py save` — no mutating git
    command runs, the ledger stays on `pull`, and both refs survive."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    assert _restore(repo)["ceremony_transition"] == "pull"
    # The R2 topology: the ceremony PR's base is the very branch about to be deleted.
    fake_gh._prs[BRANCH_345]["base"] = BRANCH_345  # noqa: SLF001

    recorder = _RecordingRunner(fake_gh)
    with pytest.raises(SC.HazardRefusedError, match="branch_delete_targets_base"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=f"branch_delete:{BRANCH_345}",
            runner=recorder,
        )

    assert recorder.mutating_calls() == []
    assert _restore(repo)["ceremony_transition"] == "pull"
    assert _local_branch_exists(repo, BRANCH_345)
    assert _remote_branch_exists(fake_gh.bare_origin, BRANCH_345)


def test_branch_delete_targets_base_is_not_acknowledgeable(ceremony_repo) -> None:
    """KTD3: `--acknowledge-hazard branch_delete_targets_base` does NOT unlock it —
    there is no legitimate case for deleting the PR base, so there is nothing to
    acknowledge."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    fake_gh._prs[BRANCH_345]["base"] = BRANCH_345  # noqa: SLF001

    with pytest.raises(SC.HazardRefusedError, match="branch_delete_targets_base"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=f"branch_delete:{BRANCH_345}",
            acknowledge_hazard=["branch_delete_targets_base"],
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "pull"
    assert _local_branch_exists(repo, BRANCH_345)


class _BlankHeadRefName:
    """Wraps a runner and blanks ``headRefName`` in the ceremony resolver's rung-1
    query, forcing resolution down to rung 2 while leaving ``baseRefName`` intact.

    This is the only way to exercise ``branch_delete_targets_base`` on the path where
    it can actually fire. Rung 1 returns head and base from a single ``gh pr view``
    record, and GitHub forbids a same-repo PR whose head IS its base, so on that rung
    the two operands can never be equal and the hazard is structurally inert. It exists
    for rung 2, where the head comes from the opened-resource manifest and the base
    from the PR — two independent records that CAN agree wrongly."""

    def __init__(self, inner) -> None:  # noqa: ANN001
        self._inner = inner
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        self.calls.append(list(cmd))
        result = self._inner(
            cmd, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )
        argv = list(cmd)
        if argv[:3] == ["gh", "pr", "view"] and "headRefName,baseRefName" in argv:
            payload = json.loads(result.stdout or "{}")
            payload["headRefName"] = ""
            result.stdout = json.dumps(payload)
        return result

    def mutating_calls(self) -> list[list[str]]:
        return _RecordingRunner.mutating_calls(self)  # type: ignore[arg-type]


def test_branch_delete_targets_base_fires_on_the_rung_2_incident_topology(
    ceremony_repo,
) -> None:
    """R2 on the ONLY path where this hazard is production-reachable, and the shape of
    the `outcome/norns-next-horizon` incident itself.

    The two sibling tests above force `head == base` on the PR record, which proves the
    refusal ORDERING but describes a topology GitHub cannot produce. Here the PR is
    well-formed — its base is a real outcome branch, distinct from its head — and the
    corruption is where it actually was: the opened-resource manifest captured the BASE
    branch as this ceremony's head, so the resolved deletion target became the branch
    the ceremony had just merged into. Rung 1 is made unavailable (blank headRefName),
    rung 2 answers, and the hazard catches what rung 1 never could."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    saga_id = str(_restore(repo)["saga_id"])
    outcome = "outcome/norns-next-horizon"

    # A well-formed PR: head and base genuinely differ, as GitHub guarantees.
    fake_gh._prs[BRANCH_345]["base"] = outcome  # noqa: SLF001
    SC.write_ceremony_base(repo, saga_id, outcome, recorded_by="test-incident")
    # The corruption: the manifest names the BASE as the ceremony head. Registered with
    # a later `opened_at` so `_manifest_head_branch`'s deterministic pick returns it.
    SC.ship_teardown.register(
        repo,
        saga_id,
        SC._branch_resource_id(outcome),  # noqa: SLF001 - reproducing a corrupt record
        kind="branch",
        ref=outcome,
        opened_by="test-incident",
        now="2999-01-01T00:00:00+00:00",
    )

    refs = SC.resolve_ceremony_refs(
        _restore(repo), repo_root=repo, runner=_BlankHeadRefName(fake_gh)
    )
    assert refs.source == SC.CEREMONY_REFS_SOURCE_MANIFEST, "rung 1 must be unavailable here"
    assert refs.head == outcome == refs.base, "the incident: resolved head IS the base"

    recorder = _BlankHeadRefName(fake_gh)
    with pytest.raises(SC.HazardRefusedError, match="branch_delete_targets_base"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=f"branch_delete:{outcome}",
            runner=recorder,
        )

    # Refused before dispatch and before save: nothing mutating ran, and the branch the
    # ceremony would have deleted is still there both locally and on the origin.
    assert recorder.mutating_calls() == []
    assert _restore(repo)["ceremony_transition"] == "pull"
    assert _local_branch_exists(repo, BRANCH_345)
    assert _remote_branch_exists(fake_gh.bare_origin, BRANCH_345)


class _GhRungFlapper:
    """Wraps a runner and lets the resolver's rung-1 query succeed exactly ``allow``
    times, failing every later one — so the gate resolves on rung 1 and any LATER
    resolution is pushed down to rung 2.

    This models one transient ``gh`` failure (token expiry mid-run, secondary rate
    limit, a 5xx) inside a single ``run()``. It is the only fault shape that can make
    two resolutions of the same ceremony disagree, because the resolver degrades
    silently on any non-zero ``gh`` exit."""

    def __init__(self, inner, *, allow: int) -> None:  # noqa: ANN001
        self._inner = inner
        self._allow = allow
        self.calls: list[list[str]] = []
        self.rung1_views = 0

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        argv = list(cmd)
        self.calls.append(argv)
        if argv[:3] == ["gh", "pr", "view"] and "headRefName,baseRefName" in argv:
            self.rung1_views += 1
            if self.rung1_views > self._allow:
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="gh: rate limited")
        return self._inner(cmd, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout)

    def deleted_branches(self) -> list[str]:
        return [c[-1] for c in self.calls if c[:3] == ["git", "branch", "-d"]] + [
            c[-1] for c in self.calls if c[:4] == ["git", "push", "origin", "--delete"]
        ]


def test_branch_delete_deletes_the_branch_the_operator_confirmed_not_a_re_resolution(
    ceremony_repo,
) -> None:
    """The confirmed target and the deleted branch are the SAME resolution.

    `run()` resolves the refs, validates `--operator-confirmed branch_delete:<target>`
    against them, and hands the resolved head to the hazard probe. If the runner then
    re-resolves independently, all three of those checks are computed against a value
    the destructive step never sees — and because the ladder degrades from the PR to
    local evidence on any non-zero `gh` exit, ONE transient failure in that window
    answers from a different rung and can name a different branch.

    Topology: a well-formed PR (head `BRANCH_345`, base `outcome/...`) plus corrupt
    local evidence naming the BASE as the head — the incident shape. `gh` answers the
    gate, then fails. Pre-fix, `_do_branch_delete` re-resolved onto rung 2 and ran
    `git branch -d outcome/...` / `git push origin --delete outcome/...` while
    reporting `operator-confirmed`, reproducing the original data loss THROUGH the
    fix. The hazard could not catch it: it had been evaluated against rung 1's head."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")
    saga_id = str(_restore(repo)["saga_id"])
    outcome = "outcome/norns-next-horizon"
    subprocess.run(  # noqa: S607 - fixture setup, fixed argv
        ["git", "-C", str(repo), "branch", outcome], check=True, capture_output=True
    )

    fake_gh._prs[BRANCH_345]["base"] = outcome  # noqa: SLF001
    SC.write_ceremony_base(repo, saga_id, outcome, recorded_by="test-toctou")
    SC.ship_teardown.register(
        repo,
        saga_id,
        SC._branch_resource_id(outcome),  # noqa: SLF001 - the corrupt record
        kind="branch",
        ref=outcome,
        opened_by="test-toctou",
        now="2999-01-01T00:00:00+00:00",
    )

    # Two rung-1 answers are consumed before dispatch: run()'s gate and the
    # branch_delete_targets_base probe. Everything after that fails.
    flapper = _GhRungFlapper(fake_gh, allow=2)
    SC.run(
        repo_root=repo,
        issue_ref="org/repo#345",
        operator_confirmed=f"branch_delete:{BRANCH_345}",
        runner=flapper,
    )

    assert flapper.deleted_branches() == [BRANCH_345, BRANCH_345], (
        "the deleted branch must be the one the operator confirmed, on both the local "
        f"and the origin delete; got {flapper.deleted_branches()}"
    )
    assert outcome not in flapper.deleted_branches()
    assert _local_branch_exists(repo, outcome), "the base branch must survive"
    # The mechanism, not just the outcome: the runner consumed the gate's refs rather
    # than resolving again, so the third rung-1 query never happened. If a future change
    # reintroduces a second resolution this count moves and the test says so.
    assert flapper.rung1_views == 2


def test_branch_delete_refuses_when_the_resolved_head_is_the_resolved_base(
    leaf_into_outcome_repo,
) -> None:
    """The independent floor, and the one that matters when no PR exists.

    `_probe_branch_delete_targets_base` returns None without a PR number, so on a
    ceremony with empty `pr_refs` the hazard never runs at all and rung 1 is skipped in
    every resolution. If rung 2's head equals rung 2's base the base is deleted with
    zero automated refusal. `refs.base` is already in hand here, so comparing costs
    nothing and needs no network."""
    repo, _bare_origin = leaf_into_outcome_repo
    saga = dict(_restore_saga(repo, SAGA_ID_LEAF), pr_refs=[])
    # Corrupt the manifest so rung 2's head resolves to the base, as the incident did.
    SC.ship_teardown.register(
        repo,
        SAGA_ID_LEAF,
        SC._branch_resource_id(OUTCOME_BASE),  # noqa: SLF001
        kind="branch",
        ref=OUTCOME_BASE,
        opened_by="test-floor",
        now="2999-01-01T00:00:00+00:00",
    )
    runner = GitPassthroughRunner()
    with pytest.raises(SC.TransitionFailedError, match="resolved BASE branch"):
        SC._do_branch_delete(saga, repo_root=repo, runner=runner)  # noqa: SLF001
    assert _local_branch_exists(repo, OUTCOME_BASE)


def test_qualified_target_on_a_transition_that_takes_none_refuses(ceremony_repo) -> None:
    """KTD6, and a pin on the one output change #635 made to the uniform mismatch rule.

    `merge:x` with `merge` upcoming used to reach the MISMATCH refusal, because the rule
    compared the raw confirmation string and `"merge:x" != "merge"`. It now compares the
    parsed transition name, so this input falls through to the "does not take a
    confirmation target" refusal instead — the accurate diagnosis. Both refuse and
    neither advances the ledger; only the wording moved. It was unreachable from the CLI
    before the change (argparse `choices=` rejected the colon form) but reachable via the
    Python API, so it is pinned here rather than left to drift."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    with pytest.raises(SC.OperatorConfirmationError, match="does not take a confirmation target"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="merge:whatever",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "request_review"

    # The mismatch rule itself is untouched: a DIFFERENT transition still refuses as it
    # always did, qualified or bare.
    with pytest.raises(SC.OperatorConfirmationError, match="does not match the upcoming"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed=f"branch_delete:{BRANCH_345}",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "request_review"


def test_bare_branch_delete_confirmation_refuses_naming_the_resolved_target(
    ceremony_repo,
) -> None:
    """KTD6/R8: a bare `--operator-confirmed branch_delete` refuses, and the refusal
    names the resolved target so the operator's next invocation carries a value they
    have actually seen."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")

    with pytest.raises(SC.OperatorConfirmationError) as excinfo:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="branch_delete",
            runner=fake_gh,
        )
    message = str(excinfo.value)
    assert BRANCH_345 in message
    assert f"--operator-confirmed branch_delete:{BRANCH_345}" in message
    assert _restore(repo)["ceremony_transition"] == "pull"
    assert _local_branch_exists(repo, BRANCH_345)


def test_no_confirmation_at_branch_delete_names_the_qualified_form(ceremony_repo) -> None:
    """KTD6: the always_operator gate's own refusal (no confirmation at all) prints the
    qualified command, not the bare one that would just refuse again."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")

    with pytest.raises(SC.OperatorConfirmationError) as excinfo:
        SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)
    assert f"--operator-confirmed branch_delete:{BRANCH_345}" in str(excinfo.value)
    assert _restore(repo)["ceremony_transition"] == "pull"


def test_wrong_qualified_target_refuses_and_the_resolved_one_proceeds(ceremony_repo) -> None:
    """KTD6: a qualified target that is not the resolved head refuses (naming both),
    leaves the ledger unadvanced and `main` intact; the resolved target proceeds."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "branch_delete")

    with pytest.raises(SC.OperatorConfirmationError) as excinfo:
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="branch_delete:main",
            runner=fake_gh,
        )
    message = str(excinfo.value)
    assert "main" in message
    assert BRANCH_345 in message
    assert _restore(repo)["ceremony_transition"] == "pull"
    assert _local_branch_exists(repo, "main")
    assert _local_branch_exists(repo, BRANCH_345)

    status = SC.run(
        repo_root=repo,
        issue_ref="org/repo#345",
        operator_confirmed=f"branch_delete:{BRANCH_345}",
        runner=fake_gh,
    )
    assert "branch_delete" in status
    assert _restore(repo)["ceremony_transition"] == "branch_delete"
    assert not _local_branch_exists(repo, BRANCH_345)
    assert _local_branch_exists(repo, "main")


def test_merge_keeps_the_bare_confirmation_grammar(ceremony_repo) -> None:
    """KTD6 scope: only branch_delete grows a target. `merge` still confirms bare, and
    a qualified confirmation on it refuses rather than being silently accepted."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    with pytest.raises(SC.OperatorConfirmationError, match="does not take"):
        SC.run(
            repo_root=repo,
            issue_ref="org/repo#345",
            operator_confirmed="merge:main",
            runner=fake_gh,
        )
    assert _restore(repo)["ceremony_transition"] == "request_review"

    status = SC.run(
        repo_root=repo, issue_ref="org/repo#345", operator_confirmed="merge", runner=fake_gh
    )
    assert "merge" in status
    assert _restore(repo)["ceremony_transition"] == "merge"


def test_parse_operator_confirmation_splits_only_on_the_first_colon() -> None:
    assert SC._parse_operator_confirmation("merge") == ("merge", None)
    assert SC._parse_operator_confirmation("branch_delete:outcome/demo") == (
        "branch_delete",
        "outcome/demo",
    )
    # A trailing colon carries no target — it must read as bare, not as target "".
    assert SC._parse_operator_confirmation("branch_delete:") == ("branch_delete", None)
    assert SC._parse_operator_confirmation("branch_delete:a:b") == ("branch_delete", "a:b")


def test_parser_accepts_a_qualified_target_and_still_rejects_off_palette_names() -> None:
    parser = SC._build_parser()
    args = parser.parse_args(["run", "--operator-confirmed", "branch_delete:outcome/demo"])
    assert args.operator_confirmed == "branch_delete:outcome/demo"
    assert parser.parse_args(["run", "--operator-confirmed", "merge"]).operator_confirmed == "merge"
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--operator-confirmed", "bogus:outcome/demo"])


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


def test_branch_delete_refuses_when_branch_is_main(ceremony_repo, monkeypatch) -> None:  # noqa: ANN001
    """The empty/``main`` guard survives issue #635 as defense in depth, but it now
    guards the RESOLVED head rather than ``saga['branch']``.

    R9 note — this test changed with U2, deliberately. Its previous body passed
    ``{"branch": "main"}`` / ``{"branch": ""}`` straight into ``_do_branch_delete`` and
    asserted the refusal, which asserted the defect itself: that the deletion target
    comes from the saga's rolling ``branch`` field. Under the fix that field is never a
    destructive-target source, so the guard is driven from the resolver instead —
    rung 2 supplies a ``main`` head here, and a stubbed resolver supplies the empty
    head the real resolver structurally cannot return (both rungs demand a non-empty
    head), keeping both guard branches covered.
    """
    repo, fake_gh = ceremony_repo
    saga_id = "issue-635-guard"
    _register_ceremony_branch(repo, saga_id, "main")
    SC.write_ceremony_base(repo, saga_id, "outcome/demo", recorded_by="test")
    saga = {"saga_id": saga_id, "kind": "issue", "id": "635-guard"}

    with pytest.raises(SC.TransitionFailedError, match="refusing to delete branch"):
        SC._do_branch_delete(saga, repo_root=repo, runner=fake_gh)  # noqa: SLF001

    monkeypatch.setattr(
        SC,
        "resolve_ceremony_refs",
        lambda *_args, **_kwargs: SC.CeremonyRefs(head="", base="main", source="stub"),
    )
    with pytest.raises(SC.TransitionFailedError, match="refusing to delete branch"):
        SC._do_branch_delete(saga, repo_root=repo, runner=fake_gh)  # noqa: SLF001


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
        operator_confirmed=f"branch_delete:{BRANCH_345}",
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


# --------------------------------------------------------------------------- #
# Ceremony ref resolution (issue #635, U1). These are pure-resolver tests: no real
# git, no real gh — a scripted runner answers each argv, and every test asserts on
# what was (and was not) asked. The load-bearing property across all of them is that
# ``saga["branch"]`` never reaches an answer, because that field is re-stamped from
# ``git branch --show-current`` on every save and holds the PR *base* on a
# leaf-into-outcome ceremony whose last tick happened after ``checkout_main``.
# --------------------------------------------------------------------------- #

SAGA_ID_635 = "issue-635"
# Deliberately distinct from every real ref in these fixtures, so "this string appears
# nowhere in the resolved refs or in any argv" is a meaningful assertion.
ROLLING_BRANCH_FIELD = "outcome/rolling-tick-field"


class ScriptedRunner:
    """Records every argv and answers from a handler. Mirrors ``_run``'s call shape
    (``cwd``/``capture_output``/``text``/``timeout`` keywords) so it can be passed as
    ``runner=`` anywhere in ship_ceremony.py."""

    def __init__(self, handler) -> None:  # noqa: ANN001
        self.calls: list[list[str]] = []
        self._handler = handler

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        self.calls.append(parts)
        return self._handler(parts)

    def argv_mentions(self, token: str) -> bool:
        return any(token in part for call in self.calls for part in call)


def _fail(stderr: str = "boom", returncode: int = 1) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


def _register_ceremony_branch(repo_root: Path, saga_id: str, branch: str) -> None:
    SC.ship_teardown.register(
        repo_root,
        saga_id,
        SC._branch_resource_id(branch),  # noqa: SLF001
        kind="branch",
        ref=branch,
        opened_by="commit",
    )


def test_resolve_ceremony_refs_rung_1_wins_and_never_reads_the_branch_field(
    tmp_path: Path,
) -> None:
    """Rung 1: a PR ref exists, so ``gh pr view`` answers — and ``saga['branch']``,
    set to a different value, is neither returned nor passed to any command."""
    saga = {
        "saga_id": SAGA_ID_635,
        "kind": "issue",
        "id": "635",
        "branch": ROLLING_BRANCH_FIELD,
        "pr_refs": ["#77"],
    }
    # Rung 2 is fully stocked with *different* values, so a resolver that silently
    # preferred local state would be caught here too.
    _register_ceremony_branch(tmp_path, SAGA_ID_635, "feat/manifest-head")
    SC.write_ceremony_base(tmp_path, SAGA_ID_635, "outcome/sidecar-base", recorded_by="test")

    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        assert parts[:3] == ["gh", "pr", "view"], f"unexpected call {parts!r}"
        assert parts[3] == "77"
        assert parts[parts.index("--json") + 1] == "headRefName,baseRefName"
        return _ok(json.dumps({"headRefName": "feat/pr-head", "baseRefName": "outcome/pr-base"}))

    runner = ScriptedRunner(handler)
    refs = SC.resolve_ceremony_refs(saga, repo_root=tmp_path, runner=runner)

    assert refs.head == "feat/pr-head"
    assert refs.base == "outcome/pr-base"
    assert refs.source == SC.CEREMONY_REFS_SOURCE_PR
    # The rolling tick field is neither an answer nor an input.
    assert ROLLING_BRANCH_FIELD not in (refs.head, refs.base)
    assert not runner.argv_mentions(ROLLING_BRANCH_FIELD)
    assert len(runner.calls) == 1


def test_resolve_ceremony_refs_rung_2_answers_when_gh_fails(tmp_path: Path) -> None:
    """Rung 2: the PR query fails (offline, rate-limited, deleted PR), so the manifest
    supplies the head and the per-saga sidecar supplies the base — no network, and
    still not the tick field."""
    saga = {
        "saga_id": SAGA_ID_635,
        "kind": "issue",
        "id": "635",
        "branch": ROLLING_BRANCH_FIELD,
        "pr_refs": ["#77"],
    }
    _register_ceremony_branch(tmp_path, SAGA_ID_635, "feat/manifest-head")
    SC.write_ceremony_base(tmp_path, SAGA_ID_635, "outcome/sidecar-base", recorded_by="test")

    runner = ScriptedRunner(lambda parts: _fail("gh: could not reach api.github.com"))
    refs = SC.resolve_ceremony_refs(saga, repo_root=tmp_path, runner=runner)

    assert refs.head == "feat/manifest-head"
    assert refs.base == "outcome/sidecar-base"
    assert refs.source == SC.CEREMONY_REFS_SOURCE_MANIFEST
    assert ROLLING_BRANCH_FIELD not in (refs.head, refs.base)
    assert not runner.argv_mentions(ROLLING_BRANCH_FIELD)


def test_resolve_ceremony_refs_exhausted_ladder_raises_naming_both_sources(
    tmp_path: Path,
) -> None:
    """Rung 3: no PR ref and no manifest entry — refuse, and name every source tried
    so the operator knows what to repair (R7)."""
    saga = {"saga_id": SAGA_ID_635, "kind": "issue", "id": "635", "branch": ROLLING_BRANCH_FIELD}
    runner = ScriptedRunner(lambda parts: pytest.fail(f"no command should run: {parts!r}"))

    with pytest.raises(SC.CeremonyRefsError) as excinfo:
        SC.resolve_ceremony_refs(saga, repo_root=tmp_path, runner=runner)

    message = str(excinfo.value)
    assert "pr_refs" in message
    assert "ceremony-branch:" in message
    assert SC.CEREMONY_BASE_SIDECAR_NAME in message
    assert runner.calls == []


def test_resolve_ceremony_refs_never_returns_the_branch_field_when_it_is_all_there_is(
    tmp_path: Path,
) -> None:
    """The whole point of R7: with the rolling field as the only available value, the
    resolver refuses rather than degrading to it. Anything else here is the data-loss
    defect (issue #635) re-expressed through the new seam."""
    saga = {"saga_id": SAGA_ID_635, "kind": "issue", "id": "635", "branch": ROLLING_BRANCH_FIELD}
    runner = ScriptedRunner(lambda parts: _ok(""))

    with pytest.raises(SC.CeremonyRefsError) as excinfo:
        SC.resolve_ceremony_refs(saga, repo_root=tmp_path, runner=runner)

    assert ROLLING_BRANCH_FIELD not in str(excinfo.value)


def test_resolve_ceremony_refs_refuses_when_only_the_head_rung_answers(tmp_path: Path) -> None:
    """A half-answer is not an answer: the manifest knows the head but no base sidecar
    was ever recorded, so the ladder is exhausted and names the missing sidecar rather
    than pairing a real head with a guessed base."""
    saga = {"saga_id": SAGA_ID_635, "kind": "issue", "id": "635", "branch": ROLLING_BRANCH_FIELD}
    _register_ceremony_branch(tmp_path, SAGA_ID_635, "feat/manifest-head")
    runner = ScriptedRunner(lambda parts: _fail())

    with pytest.raises(SC.CeremonyRefsError, match=SC.CEREMONY_BASE_SIDECAR_NAME):
        SC.resolve_ceremony_refs(saga, repo_root=tmp_path, runner=runner)


def test_resolve_ceremony_refs_prefers_the_still_open_branch_entry(tmp_path: Path) -> None:
    """Two ``ceremony-branch:`` entries (a ceremony that pushed under two names): the
    still-open one wins, deterministically, not whichever the dict happened to yield."""
    saga = {"saga_id": SAGA_ID_635, "kind": "issue", "id": "635", "branch": ROLLING_BRANCH_FIELD}
    _register_ceremony_branch(tmp_path, SAGA_ID_635, "feat/abandoned-head")
    SC.ship_teardown.close(
        tmp_path,
        SAGA_ID_635,
        SC._branch_resource_id("feat/abandoned-head"),  # noqa: SLF001
        evidence="superseded",
    )
    _register_ceremony_branch(tmp_path, SAGA_ID_635, "feat/live-head")
    SC.write_ceremony_base(tmp_path, SAGA_ID_635, "outcome/sidecar-base", recorded_by="test")
    runner = ScriptedRunner(lambda parts: _fail())

    refs = SC.resolve_ceremony_refs(saga, repo_root=tmp_path, runner=runner)
    assert refs.head == "feat/live-head"


def test_ceremony_base_sidecar_round_trips_beside_the_other_sidecars(tmp_path: Path) -> None:
    """KTD4: the base is a per-saga JSON sidecar in the same directory as
    ``merge_expectation.json`` / ``rollback_manifest.json``, never a saga tick field."""
    assert SC.read_ceremony_base(tmp_path, SAGA_ID_635) == ""
    path = SC.write_ceremony_base(tmp_path, SAGA_ID_635, "outcome/demo", recorded_by="start")

    assert path == SC.ceremony_base_path(tmp_path, SAGA_ID_635)
    assert path.parent == SC.ship_teardown.manifest_path(tmp_path, SAGA_ID_635).parent
    assert path.name == SC.CEREMONY_BASE_SIDECAR_NAME
    assert SC.read_ceremony_base(tmp_path, SAGA_ID_635) == "outcome/demo"

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["base"] == "outcome/demo"
    assert payload["recorded_by"] == "start"

    # Rewritable: the site that learns the base authoritatively re-records it.
    SC.write_ceremony_base(tmp_path, SAGA_ID_635, "outcome/next", recorded_by="open_pr")
    assert SC.read_ceremony_base(tmp_path, SAGA_ID_635) == "outcome/next"


def test_write_ceremony_base_refuses_an_empty_base(tmp_path: Path) -> None:
    with pytest.raises(SC.CeremonyRefsError):
        SC.write_ceremony_base(tmp_path, SAGA_ID_635, "", recorded_by="start")


def test_ceremony_base_path_rejects_a_traversing_saga_id(tmp_path: Path) -> None:
    with pytest.raises(SC.CeremonyRefsError, match="invalid saga_id"):
        SC.ceremony_base_path(tmp_path, "../escape")


def test_resolve_default_branch_uses_the_symbolic_ref(tmp_path: Path) -> None:
    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        assert parts == ["git", "symbolic-ref", "refs/remotes/origin/HEAD"]
        return _ok("refs/remotes/origin/trunk\n")

    runner = ScriptedRunner(handler)
    assert SC.resolve_default_branch(tmp_path, runner=runner) == "trunk"
    # No gh call at all when git already knows the answer (no network on the fast path).
    assert len(runner.calls) == 1


def test_resolve_default_branch_falls_back_to_gh(tmp_path: Path) -> None:
    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        if parts[:2] == ["git", "symbolic-ref"]:
            return _fail("fatal: ref refs/remotes/origin/HEAD is not a symbolic ref")
        assert parts == ["gh", "repo", "view", "--json", "defaultBranchRef"]
        return _ok(json.dumps({"defaultBranchRef": {"name": "develop"}}))

    runner = ScriptedRunner(handler)
    assert SC.resolve_default_branch(tmp_path, runner=runner) == "develop"
    assert len(runner.calls) == 2


def test_resolve_default_branch_raises_rather_than_defaulting_to_main(tmp_path: Path) -> None:
    """KTD5: both probes failing must refuse. Replacing one hardcoded ``main`` with
    another hardcoded ``main`` moves the bug rather than fixing it."""
    runner = ScriptedRunner(lambda parts: _fail("no remote"))

    with pytest.raises(SC.CeremonyRefsError) as excinfo:
        SC.resolve_default_branch(tmp_path, runner=runner)

    message = str(excinfo.value)
    assert "git symbolic-ref refs/remotes/origin/HEAD" in message
    assert "gh repo view --json defaultBranchRef" in message


def test_resolve_default_branch_refuses_an_unparseable_symbolic_ref(tmp_path: Path) -> None:
    """A symbolic ref that does not name an origin branch is not an answer — fall
    through to gh rather than returning a mangled ref name."""

    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        if parts[:2] == ["git", "symbolic-ref"]:
            return _ok("refs/heads/something-else\n")
        return _ok(json.dumps({"defaultBranchRef": {"name": "release"}}))

    assert SC.resolve_default_branch(tmp_path, runner=ScriptedRunner(handler)) == "release"


# --------------------------------------------------------------------------- #
# Destructive paths consume the resolver (issue #635, U2 — defects A and E).
#
# A is data-loss class: `_do_branch_delete` derived its delete target from
# `saga["branch"]`, a field re-stamped from `git branch --show-current` on EVERY
# `saga.py save`. On a leaf-into-outcome ceremony whose last tick landed on the base
# branch, that field holds the PR *base* — so the transition deleted the base branch
# local and origin (the real 2026-07-20/21 incident on infiquetra/team-norns), and,
# because the manifest key was derived independently from the same wrong field,
# silently closed nothing while leaving the head's `ceremony-branch:` entry open.
#
# E is the same root cause on the merge path: both SHA probes read the literal
# `refs/heads/main`, so `merge_sha` recorded the default branch's tip rather than the
# squash commit — and that sha is REACHABLE, so ship_undo's SHA_UNREACHABLE guard
# never fires and `git revert` lands on an unrelated healthy commit.
#
# These tests use REAL git against a REAL local bare origin wherever the assertion is
# about a ref actually surviving or disappearing; the pure-argv oracles use the same
# ScriptedRunner rig U1's resolver tests use.
# --------------------------------------------------------------------------- #

LEAF_HEAD = "feat/leaf-635"
OUTCOME_BASE = "outcome/demo"
SAGA_ID_LEAF = "issue-635"


class RecordingRunner:
    """Wraps a base runner, recording every argv while passing the call through
    unchanged. Used where the oracle is 'which commands did this transition issue'
    but the commands themselves must really run."""

    def __init__(self, base) -> None:  # noqa: ANN001
        self.base = base
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN001, ANN003, ANN204
        self.calls.append(list(cmd))
        return self.base(cmd, **kwargs)

    def argv_mentions(self, token: str) -> bool:
        return any(token in part for call in self.calls for part in call)


class GitPassthroughRunner(RecordingRunner):
    """Records argv, runs real ``git`` for real, and answers ``gh`` from a handler."""

    def __init__(self, gh_handler=None) -> None:  # noqa: ANN001
        super().__init__(base=None)
        self._gh = gh_handler
        self._real_run = subprocess.run

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        self.calls.append(parts)
        if parts[0] == "gh":
            assert self._gh is not None, f"unexpected gh call {parts!r}"
            return self._gh(parts)
        return self._real_run(  # nosec B603
            parts, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603, S607
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _remote_sha(bare_origin: Path, ref: str) -> str:
    out = subprocess.run(  # noqa: S603, S607
        ["git", "ls-remote", str(bare_origin), ref], check=True, capture_output=True, text=True
    )
    return out.stdout.split()[0] if out.stdout.strip() else ""


def _commit_reachable(repo: Path, sha: str) -> bool:
    """Mirrors ``ship_undo._sha_reachable``'s probe exactly — the check whose failure
    would raise SHA_UNREACHABLE and stop a bad revert."""
    result = subprocess.run(  # noqa: S603, S607
        ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(  # noqa: S603, S607
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _saga_save(repo: Path, *args: str) -> None:
    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    subprocess.run(  # noqa: S603
        [sys.executable, str(saga_py), "save", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _restore_saga(repo: Path, saga_id: str) -> dict[str, Any]:
    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(saga_py), "restore", "--saga-id", saga_id],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    output: dict[str, Any] = json.loads(result.stdout)
    return output


def _new_leaf_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real clone of a real bare origin carrying a leaf-into-outcome topology:
    ``main`` → ``outcome/demo`` (the PR base) → ``feat/leaf-635`` (the PR head)."""
    bare_origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True)  # noqa: S607
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True)  # noqa: S607
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    _git(repo, "push", "origin", "HEAD:main")
    _git(repo, "checkout", "-B", "main")

    _git(repo, "checkout", "-b", OUTCOME_BASE)
    (repo / "outcome.txt").write_text("outcome scaffold\n")
    _git(repo, "add", "outcome.txt")
    _git(repo, "commit", "-m", "outcome scaffold")
    _git(repo, "push", "-u", "origin", OUTCOME_BASE)

    _git(repo, "checkout", "-b", LEAF_HEAD)
    (repo / "leaf.txt").write_text("leaf work\n")
    _git(repo, "add", "leaf.txt")
    _git(repo, "commit", "-m", "leaf work")
    _git(repo, "push", "-u", "origin", LEAF_HEAD)
    return repo, bare_origin


@pytest.fixture()
def leaf_into_outcome_repo(tmp_path: Path):
    """The exact state ``branch_delete`` runs in on a leaf-into-outcome ceremony that
    already merged: the leaf is merged into ``outcome/demo``, the outcome has already
    landed on ``main`` (so BOTH branches are fully merged and therefore genuinely
    ``git branch -d``-deletable — without that, a mis-targeted delete would merely
    error instead of destroying the base, and the red run would prove far less), the
    last saga tick was saved while sitting on the BASE branch, and HEAD is back on
    ``main`` as ``checkout_main`` leaves it.

    ``saga['branch']`` is poisoned by a REAL ``saga.py save``, not hand-written:
    saga.py refuses to downgrade a recorded work branch only to ``main``/``master``
    (issue #480), so a save on ``outcome/demo`` overwrites it — which is precisely
    the defect.
    """
    repo, bare_origin = _new_leaf_repo(tmp_path)

    _saga_save(
        repo,
        "--kind",
        "issue",
        "--id",
        "635",
        "--issue-ref",
        "org/repo#635",
        "--lifecycle-phase",
        "work",
        "--pr-refs",
        "#77",
    )

    # The ceremony's merge: the leaf lands on the outcome branch, and the outcome
    # branch has itself already landed on main.
    _git(repo, "checkout", OUTCOME_BASE)
    _git(repo, "merge", "--ff-only", LEAF_HEAD)
    _git(repo, "push", "origin", OUTCOME_BASE)
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--ff-only", OUTCOME_BASE)
    _git(repo, "push", "origin", "main")

    # The poisoned tick: a save made while checked out on the BASE branch.
    _git(repo, "checkout", OUTCOME_BASE)
    _saga_save(repo, "--kind", "issue", "--id", "635", "--ceremony-transition", "pull")
    # ...and then `checkout_main` puts HEAD back on main, where branch_delete runs.
    _git(repo, "checkout", "main")

    _register_ceremony_branch(repo, SAGA_ID_LEAF, LEAF_HEAD)
    SC.write_ceremony_base(repo, SAGA_ID_LEAF, OUTCOME_BASE, recorded_by="test")
    return repo, bare_origin


def _leaf_pr_gh_handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
    assert parts[:3] == ["gh", "pr", "view"], f"unexpected gh call {parts!r}"
    assert parts[3] == "77"
    assert parts[parts.index("--json") + 1] == "headRefName,baseRefName"
    return _ok(json.dumps({"headRefName": LEAF_HEAD, "baseRefName": OUTCOME_BASE}))


def test_branch_delete_targets_the_pr_head_not_the_rolling_branch_field(
    leaf_into_outcome_repo,
) -> None:
    """HEADLINE REGRESSION (red-first, issue #635 R1): the last tick save happened on
    the base branch, so ``saga['branch'] == 'outcome/demo'``. Every destructive command
    the transition issues must name the HEAD branch, and nothing anywhere in the
    transition may name the base — which, in this fixture, is genuinely deletable, so
    against the pre-fix code the base really does disappear local and on origin."""
    repo, bare_origin = leaf_into_outcome_repo
    saga = _restore_saga(repo, SAGA_ID_LEAF)
    # Precondition, established by a real saga.py save rather than asserted by fiat.
    assert saga["branch"] == OUTCOME_BASE
    base_sha_before = _remote_sha(bare_origin, f"refs/heads/{OUTCOME_BASE}")
    assert base_sha_before

    runner = GitPassthroughRunner(gh_handler=_leaf_pr_gh_handler)
    fields = SC._do_branch_delete(saga, repo_root=repo, runner=runner)  # noqa: SLF001

    assert fields["branch"] == LEAF_HEAD
    assert ["git", "branch", "-d", LEAF_HEAD] in runner.calls
    assert ["git", "push", "origin", "--delete", LEAF_HEAD] in runner.calls
    assert ["git", "rev-parse", LEAF_HEAD] in runner.calls
    # No command anywhere in the transition names the base branch.
    assert not runner.argv_mentions(OUTCOME_BASE)

    # The head is gone, local and on origin; the base survives, unchanged, on both.
    assert LEAF_HEAD not in _git(repo, "branch")
    assert _remote_sha(bare_origin, f"refs/heads/{LEAF_HEAD}") == ""
    assert OUTCOME_BASE in _git(repo, "branch")
    assert _remote_sha(bare_origin, f"refs/heads/{OUTCOME_BASE}") == base_sha_before


def test_branch_delete_closes_the_head_manifest_entry_not_a_base_derived_id(
    leaf_into_outcome_repo,
) -> None:
    """R3: the manifest key and the delete target come from ONE resolved value, so the
    part-2/part-3 divergence cannot recur — the ``ceremony-branch:<head>`` entry is the
    one that closes, and no ``ceremony-branch:<base>`` id is ever addressed.

    Drives rung 2 (no ``pr_refs``, so no network): the local manifest supplies the head
    and the per-saga sidecar supplies the base. Against the pre-fix code the close
    addressed ``ceremony-branch:outcome/demo``, an id that was never registered, and
    ``_close_if_registered`` no-ops on unknown ids by design — so the head entry stayed
    open forever and ``_do_teardown`` raised TeardownBlockedError on every retry.
    """
    repo, _bare_origin = leaf_into_outcome_repo
    saga = dict(_restore_saga(repo, SAGA_ID_LEAF), pr_refs=[])
    head_id = SC._branch_resource_id(LEAF_HEAD)  # noqa: SLF001
    base_id = SC._branch_resource_id(OUTCOME_BASE)  # noqa: SLF001
    before = dict(SC.ship_teardown.read_manifest(repo, SAGA_ID_LEAF))
    assert before[head_id]["closed_at"] == ""

    runner = GitPassthroughRunner()  # any gh call would fail this test loudly
    SC._do_branch_delete(saga, repo_root=repo, runner=runner)  # noqa: SLF001

    manifest = dict(SC.ship_teardown.read_manifest(repo, SAGA_ID_LEAF))
    assert manifest[head_id]["closed_at"] != ""
    assert "deleted head:" in manifest[head_id]["close_evidence"]
    assert base_id not in manifest


def test_merge_probes_the_resolved_base_ref_for_both_shas(tmp_path: Path) -> None:
    """R6 (red-first): on an outcome-based PR both ``git ls-remote`` probes read
    ``refs/heads/outcome/demo``. ``refs/heads/main`` is never asked for, and the
    default branch's tip appears in neither recorded sha.

    The key name stays ``pre_merge_main_sha`` on purpose — it is a keyword argument of
    ``ship_undo.append_entry`` pinned by four assertions, and ``undo()`` never consumes
    it programmatically, so renaming it changes a cross-module signature for zero
    behavioral gain."""
    saga = {
        "saga_id": SAGA_ID_LEAF,
        "kind": "issue",
        "id": "635",
        "branch": ROLLING_BRANCH_FIELD,
        "pr_refs": ["#77"],
    }
    pre_base_sha = "a" * 40
    post_base_sha = "b" * 40
    main_tip_sha = "c" * 40  # never moves — what the old hardcoded probe would read
    state = {"merged": False}

    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        if parts[:3] == ["gh", "pr", "view"]:
            return _leaf_pr_gh_handler(parts)
        if parts[:3] == ["gh", "pr", "merge"]:
            assert parts[3:] == ["77", "--squash"]
            state["merged"] = True
            return _ok("")
        if parts[:3] == ["git", "ls-remote", "origin"]:
            ref = parts[3]
            if ref == f"refs/heads/{OUTCOME_BASE}":
                sha = post_base_sha if state["merged"] else pre_base_sha
                return _ok(f"{sha}\t{ref}\n")
            if ref == "refs/heads/main":
                return _ok(f"{main_tip_sha}\t{ref}\n")
        raise AssertionError(f"unexpected call {parts!r}")

    runner = ScriptedRunner(handler)
    fields = SC._do_merge(saga, repo_root=tmp_path, runner=runner)  # noqa: SLF001

    assert fields["pre_merge_main_sha"] == pre_base_sha
    assert fields["merge_sha"] == post_base_sha
    assert fields["merge_sha"] != fields["pre_merge_main_sha"]
    assert main_tip_sha not in (fields["pre_merge_main_sha"], fields["merge_sha"])
    assert not runner.argv_mentions("refs/heads/main")
    ls_remotes = [call for call in runner.calls if call[:3] == ["git", "ls-remote", "origin"]]
    assert ls_remotes == [["git", "ls-remote", "origin", f"refs/heads/{OUTCOME_BASE}"]] * 2


def test_merge_records_a_sha_this_merge_introduced_not_the_reachable_default_tip(
    tmp_path: Path,
) -> None:
    """REVERT SAFETY (red-first) — why E is destructive and not merely bad evidence.

    Against the pre-fix code the recorded ``merge_sha`` is ``main``'s *unchanged,
    reachable* tip. ``ship_undo._undo_merge`` guards only on reachability
    (``SHA_UNREACHABLE``, ship_undo.py:360), and a reachable sha sails straight through
    it: ``git revert --no-edit <sha>`` then succeeds against an unrelated healthy
    commit on the default branch and gets pushed. So the assertion here is not "the
    guard fires" — it is that the recorded sha is a commit THIS merge introduced, i.e.
    one that was NOT already reachable from the base ref beforehand. The guard is not
    what stands between a mis-recorded sha and a bad revert."""
    repo, bare_origin = _new_leaf_repo(tmp_path)
    saga = {
        "saga_id": SAGA_ID_LEAF,
        "kind": "issue",
        "id": "635",
        "branch": ROLLING_BRANCH_FIELD,
        "pr_refs": ["#77"],
    }
    pre_base_sha = _remote_sha(bare_origin, f"refs/heads/{OUTCOME_BASE}")
    main_tip_sha = _remote_sha(bare_origin, "refs/heads/main")
    assert pre_base_sha and main_tip_sha and pre_base_sha != main_tip_sha

    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        if parts[:3] == ["gh", "pr", "view"]:
            return _leaf_pr_gh_handler(parts)
        if parts[:3] == ["gh", "pr", "merge"]:
            # The real thing a squash-merge does to the world: the BASE ref on origin
            # advances to carry the head's work. `main` is untouched.
            subprocess.run(  # noqa: S603, S607
                ["git", "-C", str(repo), "push", str(bare_origin), f"{LEAF_HEAD}:{OUTCOME_BASE}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return _ok("")
        raise AssertionError(f"unexpected gh call {parts!r}")

    runner = GitPassthroughRunner(gh_handler=handler)
    fields = SC._do_merge(saga, repo_root=repo, runner=runner)  # noqa: SLF001

    post_base_sha = _remote_sha(bare_origin, f"refs/heads/{OUTCOME_BASE}")
    assert fields["pre_merge_main_sha"] == pre_base_sha
    assert fields["merge_sha"] == post_base_sha
    assert fields["merge_sha"] != main_tip_sha
    # The recorded sha is a commit this merge introduced: it was not reachable from
    # the base ref before the merge ran.
    assert not _is_ancestor(repo, fields["merge_sha"], pre_base_sha)
    assert _is_ancestor(repo, pre_base_sha, fields["merge_sha"])
    # And the undo guard would NOT have caught the pre-fix value: main's tip is a
    # perfectly reachable commit, so `_sha_reachable` returns True for it.
    assert _commit_reachable(repo, main_tip_sha)
    assert _remote_sha(bare_origin, "refs/heads/main") == main_tip_sha


def test_merge_on_a_main_based_pr_is_behaviorally_unchanged(ceremony_repo) -> None:
    """Regression (must pass before and after): for the common main-based PR the merge
    transition issues the same two ``git ls-remote origin refs/heads/main`` probes, in
    the same order, and returns the same field set with the same meanings, plus the
    resolved ``base`` the rollback manifest now records (issue #635, R12 — needed so
    ``ship_undo._undo_merge`` reverts on the branch this merge landed on). The only
    added shell-out is the resolver's read-only ``gh pr view`` query; every git
    mutation is unchanged, and on a main-based PR the recorded base IS ``main``."""
    repo, fake_gh = ceremony_repo
    _advance_to(repo, fake_gh, "merge")
    saga = _restore(repo)
    origin_main_before = _origin_main_sha(fake_gh.bare_origin)

    runner = RecordingRunner(fake_gh)
    fields = SC._do_merge(saga, repo_root=repo, runner=runner)  # noqa: SLF001

    ls_remotes = [call for call in runner.calls if call[:3] == ["git", "ls-remote", "origin"]]
    assert ls_remotes == [["git", "ls-remote", "origin", "refs/heads/main"]] * 2
    assert set(fields) == {"pr_number", "branch", "base", "pre_merge_main_sha", "merge_sha"}
    assert fields["base"] == "main"
    assert fields["pre_merge_main_sha"] == origin_main_before
    assert fields["merge_sha"] == _origin_main_sha(fake_gh.bare_origin)
    assert fields["merge_sha"] != fields["pre_merge_main_sha"]
    assert fields["branch"] == saga["branch"]


# --------------------------------------------------------------------------- #
# Base-aware transitions (issue #635, U3 — defects B, C, D): `_do_checkout_main`
# checks out the resolved base instead of the literal "main"; both `gh pr create`
# call sites (`_do_open_pr`'s fresh-create path and `start()`'s draft-create) pass an
# explicit `--base`, defaulting to `resolve_default_branch()` — never the literal
# "main" by accident.
# --------------------------------------------------------------------------- #


def test_checkout_main_checks_out_the_resolved_base_on_an_outcome_based_pr(
    leaf_into_outcome_repo,
) -> None:
    """R4 (red-first): on a leaf-into-outcome PR, `checkout_main` checks out the
    resolved base (`outcome/demo`), never the literal `main`."""
    repo, _bare_origin = leaf_into_outcome_repo
    saga = _restore_saga(repo, SAGA_ID_LEAF)
    runner = GitPassthroughRunner(gh_handler=_leaf_pr_gh_handler)

    fields = SC._do_checkout_main(saga, repo_root=repo, runner=runner)  # noqa: SLF001

    assert ["git", "checkout", OUTCOME_BASE] in runner.calls
    assert ["git", "checkout", "main"] not in runner.calls
    assert _git(repo, "branch", "--show-current") == OUTCOME_BASE
    # Undo-contract pin, restated here against the real fixture too: the returned
    # branch is still the saga's rolling field, not the branch just checked out.
    assert fields == {"branch": saga.get("branch")}


def test_checkout_main_on_a_main_based_pr_still_checks_out_main(tmp_path: Path) -> None:
    """Regression (must pass before and after): the common main-based PR is
    behaviorally unchanged."""
    saga = {
        "saga_id": SAGA_ID_635,
        "kind": "issue",
        "id": "635",
        "branch": ROLLING_BRANCH_FIELD,
        "pr_refs": ["#77"],
    }

    def handler(parts: list[str]) -> subprocess.CompletedProcess[str]:
        if parts[:3] == ["gh", "pr", "view"]:
            return _ok(json.dumps({"headRefName": "feat/leaf", "baseRefName": "main"}))
        return _ok("")

    runner = ScriptedRunner(handler)
    fields = SC._do_checkout_main(saga, repo_root=tmp_path, runner=runner)  # noqa: SLF001

    checkout_calls = [call for call in runner.calls if call[:2] == ["git", "checkout"]]
    assert checkout_calls == [["git", "checkout", "main"]]
    assert fields == {"branch": ROLLING_BRANCH_FIELD}


def test_checkout_main_return_value_stays_the_saga_branch_field_undo_contract_pin(
    tmp_path: Path,
) -> None:
    """UNDO-CONTRACT PIN (must pass BOTH before and after this change): the value
    `_do_checkout_main` returns as `branch` is `saga["branch"]`, never the resolved
    base — that value becomes the `checkout_main` rollback-manifest entry's `branch`,
    consumed by `ship_undo._restore_pre_ceremony_checkout` to restore the operator's
    PRE-CEREMONY checkout. Returning the resolved base instead would make
    `current == branch` true immediately after this transition runs and turn that
    undo step into a permanent silent no-op."""
    saga = {
        "saga_id": SAGA_ID_635,
        "kind": "issue",
        "id": "635",
        "branch": ROLLING_BRANCH_FIELD,
        "pr_refs": ["#77"],
    }
    runner = ScriptedRunner(
        lambda parts: _ok(json.dumps({"headRefName": "feat/leaf", "baseRefName": OUTCOME_BASE}))
    )

    fields = SC._do_checkout_main(saga, repo_root=tmp_path, runner=runner)  # noqa: SLF001

    assert fields["branch"] == saga["branch"]
    assert fields["branch"] != OUTCOME_BASE


def test_open_pr_fresh_create_argv_contains_the_resolved_base(ceremony_repo) -> None:
    """R5 (red-first): the fresh-create `open_pr` path's `gh pr create` argv carries
    an explicit `--base`, resolved via `resolve_default_branch` — never omitted."""
    repo, fake_gh = ceremony_repo
    runner = RecordingRunner(fake_gh)
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=runner)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=runner)  # open_pr

    create_calls = [
        call for call in runner.calls if call[:2] == ["gh", "pr"] and call[2] == "create"
    ]
    assert len(create_calls) == 1
    argv = create_calls[0]
    assert "--base" in argv
    assert argv[argv.index("--base") + 1] == "main"
    assert fake_gh._prs[BRANCH_345]["base"] == "main"  # noqa: SLF001


def test_open_pr_records_the_resolved_base_to_the_ceremony_sidecar(ceremony_repo) -> None:
    """`_do_open_pr` PERSISTS the base it resolved, as `start()` does.

    Without this the plain-run flow never writes a base sidecar, so the resolver's
    rung 2 can never satisfy its both-or-nothing condition and `checkout_main`,
    `merge`, and `branch_delete` all become hard-dependent on a reachable `gh` — the
    opposite of the ladder's stated reason for existing. An operator finishing a ship
    offline, or on an expired token, could not advance the ceremony at all."""
    repo, fake_gh = ceremony_repo
    saga_id = str(_restore(repo)["saga_id"])
    assert not SC.ceremony_base_path(repo, saga_id).exists()

    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # commit
    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=fake_gh)  # open_pr

    assert SC.read_ceremony_base(repo, saga_id) == "main"
    recorded = json.loads(SC.ceremony_base_path(repo, saga_id).read_text(encoding="utf-8"))
    assert recorded["recorded_by"] == "open_pr"


def test_ceremony_refs_refuses_an_option_like_ref() -> None:
    """A resolved ref becomes git argv, so one opening with `-` is refused at
    construction rather than at whichever consumer remembers to check.

    `git checkout -f` is the sharp case: it is accepted, it silently discards every
    uncommitted change in the tree, and `checkout_main` is REVERSIBLE tier, so nothing
    asks the operator first."""
    assert SC.CeremonyRefs(head="feat/x", base="main", source="t").head == "feat/x"
    for head, base in (("-f", "main"), ("feat/x", "-f"), ("--force", "main")):
        with pytest.raises(SC.CeremonyRefsError, match="begins with '-'"):
            SC.CeremonyRefs(head=head, base=base, source="t")


def test_write_ceremony_base_refuses_an_option_like_base(tmp_path: Path) -> None:
    """Refused at the WRITE too, not only at the read: `start --base=-f` is accepted by
    argparse and lands here before the `gh pr create`, so this is the first point that
    can stop the poison from being persisted for a later, offline ceremony to read."""
    with pytest.raises(SC.CeremonyRefsError, match="begins with '-'"):
        SC.write_ceremony_base(tmp_path, "issue-1", "-f", recorded_by="test")
    assert not SC.ceremony_base_path(tmp_path, "issue-1").exists()


def test_read_ceremony_base_refuses_a_malformed_or_non_object_sidecar(tmp_path: Path) -> None:
    """The sidecar feeds a destructive read path — `_do_merge` probes this base and
    `_undo_merge` reverts on it — so a truncated or hand-edited file must raise, never
    read as an absent-but-fine rung."""
    path = SC.ceremony_base_path(tmp_path, "issue-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"base": "main"', encoding="utf-8")  # torn write
    with pytest.raises(SC.CeremonyRefsError, match="not valid JSON"):
        SC.read_ceremony_base(tmp_path, "issue-1")
    path.write_text('["main"]', encoding="utf-8")
    with pytest.raises(SC.CeremonyRefsError, match="not a JSON object"):
        SC.read_ceremony_base(tmp_path, "issue-1")


def test_ls_remote_sha_refuses_when_origin_carries_no_such_ref(tmp_path: Path) -> None:
    """`git ls-remote` exits 0 with EMPTY stdout for a ref the remote does not have, so
    the bare `.stdout.split()[0]` this guards raised `IndexError` — a type `main()` does
    not catch, surfacing as an uncaught traceback against the module's own contract.

    Reachable now that the probed ref is a resolved base rather than the always-present
    literal `refs/heads/main`: an outcome branch legitimately stops existing once its
    own ceremony has landed."""

    def empty(cmd, **kwargs):  # noqa: ANN001, ANN003
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    with pytest.raises(SC.TransitionFailedError, match="origin has no"):
        SC._ls_remote_sha(  # noqa: SLF001
            "refs/heads/outcome/gone", repo_root=tmp_path, runner=empty
        )


def test_open_pr_existing_draft_path_does_not_create_a_second_pr(ceremony_repo) -> None:
    """The existing-draft path (front-loaded via `start()`) flips the draft ready and
    must not re-create a PR — unchanged by this unit."""
    repo, fake_gh = ceremony_repo
    runner = RecordingRunner(fake_gh)
    SC.start(repo_root=repo, issue_ref="org/repo#345", runner=runner)
    runner.calls.clear()

    SC.run(repo_root=repo, issue_ref="org/repo#345", runner=runner)  # open_pr (existing draft)

    create_calls = [call for call in runner.calls if call[:3] == ["gh", "pr", "create"]]
    assert create_calls == []
    ready_calls = [call for call in runner.calls if call[:3] == ["gh", "pr", "ready"]]
    assert len(ready_calls) == 1
    assert len(fake_gh._prs) == 1  # noqa: SLF001


def test_start_with_explicit_base_records_it_to_the_sidecar_and_passes_it(
    ceremony_repo,
) -> None:
    """R5/KTD4: an explicit `base` passed to `start()` is recorded to the per-saga
    ceremony-base sidecar and passed to the draft `gh pr create --draft`."""
    repo, fake_gh = ceremony_repo
    runner = RecordingRunner(fake_gh)

    SC.start(repo_root=repo, issue_ref="org/repo#345", base=OUTCOME_BASE, runner=runner)

    assert SC.read_ceremony_base(repo, "issue-345") == OUTCOME_BASE
    create_calls = [call for call in runner.calls if call[:3] == ["gh", "pr", "create"]]
    assert len(create_calls) == 1
    argv = create_calls[0]
    assert "--draft" in argv
    assert argv[argv.index("--base") + 1] == OUTCOME_BASE
    assert fake_gh._prs[BRANCH_345]["base"] == OUTCOME_BASE  # noqa: SLF001


def test_start_with_no_explicit_base_uses_resolve_default_branch(tmp_path: Path) -> None:
    """R5/KTD5: `start()` with no explicit base resolves via `resolve_default_branch`
    and does NOT emit the literal string "main" when the resolved default is
    something else — the repo's default branch here is `trunk`."""
    bare_origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True)  # noqa: S607
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True)  # noqa: S607
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    _git(repo, "push", "origin", "HEAD:trunk")
    _git(
        repo,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/trunk",
    )
    _git(repo, "checkout", "-B", "trunk")
    _git(repo, "checkout", "-b", "feat/pf-throwaway-777")
    (repo / "change.txt").write_text("ceremony scaffold\n")
    _git(repo, "add", "change.txt")
    _git(repo, "commit", "-m", "scaffold")

    _saga_save(
        repo,
        "--kind",
        "issue",
        "--id",
        "777",
        "--issue-ref",
        "org/repo#777",
        "--lifecycle-phase",
        "work",
        "--destination",
        "merge",
    )

    fake_gh = FakeGh(repo=repo, bare_origin=bare_origin)
    runner = RecordingRunner(fake_gh)

    status = SC.start(repo_root=repo, issue_ref="org/repo#777", runner=runner)

    assert "draft PR" in status
    assert SC.read_ceremony_base(repo, "issue-777") == "trunk"
    create_calls = [call for call in runner.calls if call[:3] == ["gh", "pr", "create"]]
    assert len(create_calls) == 1
    argv = create_calls[0]
    assert argv[argv.index("--base") + 1] == "trunk"
    assert "main" not in argv
    assert fake_gh._prs["feat/pf-throwaway-777"]["base"] == "trunk"  # noqa: SLF001
