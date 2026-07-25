"""ship_undo.py tests (issue #346, U3).

Test design: real throwaway git repos + a real local bare "origin" for the
git-mutating reverse steps (merge revert, branch resurrection, remote-ref delete) —
mirrors ``test_ship_ceremony.py``'s ``ceremony_repo`` rig, but the rollback manifest
here is hand-written directly (via ``append_entry``) rather than produced by driving
a real ceremony run, per the plan's U3 scope note: ``test_manifest_written_per_transition``
is the one scenario that requires the real ceremony + U4's hook and is deliberately
NOT part of this module's suite. A module-local ``FakeGh`` intercepts only ``gh pr
close`` (the one GitHub-facing reverse step); every other call is real ``git``.

Oracles:

* reversible-only — a ceremony killed right after PR-open (no merge/branch_delete
  entries) undoes on a bare call, no operator confirmation required (KTD5).
* gated — an in-scope plan that reverses ``merge``/``branch_delete`` refuses without
  ``operator_confirmed='undo'``, and refuses BEFORE any mutation (no git/gh calls at
  all, no manifest entries marked).
* full-completion — reverting a fully completed ceremony produces a revert commit on
  ``main`` and resurrects the deleted branch from its recorded head SHA, from the
  manifest alone (R7, KTD4).
* resumable — a mid-run failure leaves already-reverted entries marked ``undone`` and
  everything else untouched; a second call picks up exactly where it left off.
* empty/no-op — an absent or fully-undone manifest is a no-op success, not an error.
* unreachable SHA — a recorded SHA that doesn't exist in the repo raises a named
  ``SHA_UNREACHABLE`` failure and leaves the entry unmarked (KTD4).
* scope — gating looks only at NOT-YET-UNDONE entries; an already-undone
  always_operator entry does not force operator confirmation on a later call.
* base-targeted revert (issue #635, R12) — the merge revert's checkout and push both
  name the ceremony's RECORDED base and the revert lands on it, never on the literal
  ``main``; an entry written before base recording floors at the literal ``main``
  (``SU.LEGACY_MERGE_BASE``), which is the pre-#635 behavior and is NOT the repo's
  resolved default branch.
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
SHIP_UNDO_PATH = ROOT / "plugins" / "saga" / "scripts" / "ship_undo.py"
SHIP_CEREMONY_PATH = ROOT / "plugins" / "saga" / "scripts" / "ship_ceremony.py"


def _load_ship_undo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ship_undo", SHIP_UNDO_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_ship_ceremony() -> ModuleType:
    """Loaded only for ``test_manifest_written_per_transition`` — the one U3
    manifest oracle that requires driving a REAL ``ship_ceremony.run()`` through
    the U4 hook rather than hand-writing entries via ``append_entry`` (module
    docstring)."""
    spec = importlib.util.spec_from_file_location("ship_ceremony", SHIP_CEREMONY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec, matching ``_load_ship_undo`` above: ship_ceremony.py's
    # ``@dataclass`` declarations resolve their (postponed, string) annotations through
    # ``sys.modules[cls.__module__]``, which is None for an unregistered module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SU = _load_ship_undo()
SC = _load_ship_ceremony()

UNREACHABLE_SHA = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


def _ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


class FakeGh:
    """Real git passthrough; intercepts only ``gh pr close`` (the sole GitHub-facing
    reverse step this module drives). Records every gh call so "no PR mutation on a
    refused/no-op undo" is provable."""

    def __init__(self) -> None:
        self.gh_calls: list[list[str]] = []
        self._real_run = subprocess.run

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        if parts[0] == "gh":
            self.gh_calls.append(parts[1:])
            if parts[1:3] == ["pr", "close"]:
                return _ok("")
            raise AssertionError(f"unhandled fake gh call: {parts[1:]!r}")
        return self._real_run(  # nosec B603
            parts, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )


class FlakyGh(FakeGh):
    """Like ``FakeGh``, but fails the first call matching ``fail_prefix`` once, then
    passes through normally — for the resumable-after-partial-failure fixture."""

    def __init__(self, fail_prefix: list[str]) -> None:
        super().__init__()
        self.fail_prefix = fail_prefix
        self._triggered = False

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        if not self._triggered and parts[: len(self.fail_prefix)] == self.fail_prefix:
            self._triggered = True
            return _fail("simulated push failure")
        return super().__call__(
            cmd, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )


class ExplodingRunner:
    """A runner that raises if called at all — proves a refused/no-op undo() never
    touches git or gh."""

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        raise AssertionError(f"undo() should not have shelled out, but called: {cmd!r}")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603, S607
        ["git", "-C", str(repo), *args], check=check, capture_output=True, text=True
    )


def _rev_parse(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


@pytest.fixture()
def bare_repo(tmp_path: Path):
    """A real throwaway repo cloned from a real local bare 'origin', with an initial
    commit already pushed to origin's main. Returns (repo, bare_origin)."""
    bare_origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True)  # noqa: S607

    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True)  # noqa: S607
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    # Force the local branch name to 'main' regardless of the ambient
    # init.defaultBranch config (older git defaults to 'master' locally) — the rest
    # of this module's helpers (and the manifest entries) assume 'main' by name.
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "origin", "HEAD:main")
    return repo, bare_origin


def _make_feature_branch(repo: Path, name: str = "feat/pf-throwaway-346") -> str:
    """Creates+checks out a feature branch with one commit; returns its head SHA.
    Leaves HEAD on the feature branch."""
    _git(repo, "checkout", "-b", name)
    (repo / "change.txt").write_text("ceremony scaffold\n")
    _git(repo, "add", "change.txt")
    _git(repo, "commit", "-m", "scaffold")
    return _rev_parse(repo, "HEAD")


def _squash_merge_to_main(repo: Path, branch: str) -> str:
    """Squash-merges ``branch`` into main as a single new commit (mirrors the real
    ``gh pr merge --squash`` shape: a single-parent commit, NOT an ancestor-linked
    merge commit). Returns the resulting main-tip SHA. Leaves HEAD on main."""
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--squash", branch)
    _git(repo, "commit", "-m", f"squash merge {branch}")
    return _rev_parse(repo, "HEAD")


def _delete_branch_everywhere(repo: Path, branch: str) -> None:
    _git(repo, "branch", "-D", branch)
    # check=False: some callers set this up without ever having pushed the branch
    # remotely first (a locally-only precondition is still a legitimate fixture) —
    # mirrors ship_ceremony.py's own `_do_branch_delete`, which treats the remote
    # delete as best-effort (check=False) for the same reason.
    _git(repo, "push", "origin", "--delete", branch, check=False)


def _origin_ref_exists(bare_origin: Path, ref: str) -> bool:
    result = _git(Path.cwd(), "ls-remote", str(bare_origin), f"refs/heads/{ref}")
    return bool(result.stdout.strip())


class FakeSagaOnly(dict):
    """A minimal saga mapping — ``undo()`` only reads ``saga['saga_id']``."""


def _saga(saga_id: str) -> dict[str, Any]:
    return {"saga_id": saga_id, "kind": "issue", "id": saga_id.rsplit("-", 1)[-1]}


# --------------------------------------------------------------------------- #
# test_manifest_written_per_transition support: a full gh fake capable of driving
# a REAL ship_ceremony.run() through every transition (mirrors
# test_ship_ceremony.py's own FakeGh — kept module-local here rather than
# imported, so this file's fixtures stay self-contained).
# --------------------------------------------------------------------------- #


class CeremonyFakeGh:
    """Simulates just enough of `gh pr ...` to drive a real ceremony end to end,
    including the ``pr view``/``pr list`` shapes ``ceremony_hazards.py`` and
    ``merge_watcher.py`` probe."""

    def __init__(self, repo: Path, bare_origin: Path) -> None:
        self.repo = repo
        self.bare_origin = bare_origin
        self._next_number = 1
        self._prs: dict[str, dict[str, object]] = {}
        self._real_run = subprocess.run

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        if parts[0] == "gh":
            return self._handle_gh(parts[1:])
        return self._real_run(  # nosec B603
            parts, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )

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
        number = int(ref)
        for branch, pr in self._prs.items():
            if pr["number"] == number:
                return branch, pr
        raise AssertionError(f"unknown pr ref {ref!r}")

    def _handle_gh(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["pr", "create"]:
            branch = args[args.index("--head") + 1]
            body = args[args.index("--body") + 1] if "--body" in args else ""
            number = self._next_number
            self._next_number += 1
            self._prs[branch] = {
                "number": number,
                "body": body,
                "base": "main",
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
                    # Issue #635: ship_ceremony's ceremony-ref resolver (rung 1) asks
                    # for headRefName,baseRefName before the merge / branch_delete
                    # transitions touch anything destructive.
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
        if args[:2] == ["pr", "list"]:
            base = args[args.index("--base") + 1] if "--base" in args else None
            results = []
            for pr in self._prs.values():
                if base is not None and pr.get("base") != base:
                    continue
                results.append({"number": pr["number"], "title": ""})
            return _ok(json.dumps(results))
        if args[:2] == ["pr", "merge"]:
            number = int(args[2])
            branch = next(b for b, pr in self._prs.items() if pr["number"] == number)
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


@pytest.fixture()
def ceremony_bare_repo(tmp_path: Path):
    """Real throwaway repo + bare origin + a saga minted on a feature branch —
    mirrors test_ship_ceremony.py's ``ceremony_repo`` fixture, kept local to this
    file so ``test_manifest_written_per_transition`` doesn't reach across test
    modules."""
    bare_origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True)  # noqa: S607

    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True)  # noqa: S607
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    # NOT `git branch -M main`: on a from-scratch clone of an empty bare repo, that
    # rename keeps the OLD branch.<old-name>.merge value (e.g. "refs/heads/master")
    # under the renamed section — `git pull` then fails with "configured to merge
    # with refs/heads/master, but no such ref was fetched". Pushing straight to
    # `origin HEAD:main` (mirroring test_ship_ceremony.py's own working fixture)
    # avoids the stale tracking config entirely; `_do_checkout_main` + `_do_pull`
    # (this test drives both, unlike this file's other fixtures) need it clean.
    _git(repo, "push", "origin", "HEAD:main")
    # Issue #635/U3: a clone of a non-empty remote auto-configures
    # `refs/remotes/origin/HEAD`; this fixture clones an EMPTY bare origin (the push
    # to `main` happens after), so that symbolic ref is never set on its own — leaving
    # `ship_ceremony.resolve_default_branch`'s rung 1 with nothing to answer and
    # falling through to `gh repo view`, which `CeremonyFakeGh` does not implement.
    # Set it explicitly, mirroring `test_ship_ceremony.py`'s `ceremony_repo` fixture.
    _git(
        repo,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
    )

    branch = "feat/pf-throwaway-346"
    _git(repo, "checkout", "-b", branch)
    (repo / "change.txt").write_text("ceremony scaffold\n")
    _git(repo, "add", "change.txt")
    _git(repo, "commit", "-m", "scaffold")

    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    mint = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(saga_py),
            "save",
            "--kind",
            "issue",
            "--id",
            "346",
            "--issue-ref",
            "org/repo#346",
            "--lifecycle-phase",
            "work",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert mint.returncode == 0, mint.stderr

    return repo, bare_origin, CeremonyFakeGh(repo=repo, bare_origin=bare_origin)


def _confirm_for(transition: str, *, target: str = "feat/pf-throwaway-346") -> str | None:
    """Operator confirmation for ``transition`` when its tier demands one (#526).

    Issue #635/KTD6: ``branch_delete`` confirms a named target as well as the
    transition, so the qualified ``branch_delete:<head>`` form is what the gate accepts
    there. Every other transition keeps the bare grammar."""
    if SC.TRANSITION_TIERS[transition] != SC.CeremonyTier.ALWAYS_OPERATOR:
        return None
    if transition in SC.CONFIRMATION_TARGET_TRANSITIONS:
        return f"{transition}:{target}"
    return transition


def test_manifest_written_per_transition(ceremony_bare_repo) -> None:
    """U3 scope note (module docstring): the one manifest oracle that requires
    driving a REAL ``ship_ceremony.run()`` through the U4 hook — an end-to-end
    throwaway-branch ceremony produces exactly one rollback-manifest entry per
    transition, in order, each starting unmarked (``undone=False``)."""
    repo, _bare_origin, fake_gh = ceremony_bare_repo
    for expected in SC.TRANSITIONS:
        status = SC.run(
            repo_root=repo,
            issue_ref="org/repo#346",
            operator_confirmed=_confirm_for(expected),
            runner=fake_gh,
        )
        assert expected in status

    entries = SU.read_manifest(repo, "issue-346")
    assert [e["transition"] for e in entries] == list(SC.TRANSITIONS)
    assert all(e["undone"] is False for e in entries)
    # Issue #635 (R12): the merge entry carries the ceremony's RESOLVED base, written
    # by ``ship_ceremony.run()`` from ``_do_merge``'s return value — that recording is
    # what lets ``_undo_merge`` target the right branch with no gh round trip at undo
    # time. This fake's PR is based on main, so main is the value under test here.
    merge_entry = next(e for e in entries if e["transition"] == "merge")
    assert merge_entry["base"] == "main"


# --------------------------------------------------------------------------- #
# Manifest append/read helpers (R6/KTD1)
# --------------------------------------------------------------------------- #


def test_manifest_path_matches_ktd1_sidecar_shape(tmp_path: Path) -> None:
    path = SU.manifest_path(tmp_path, "issue-345")
    assert path == tmp_path / ".claude" / "saga" / "sagas" / "issue-345" / "rollback_manifest.json"


def test_read_manifest_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert SU.read_manifest(tmp_path, "issue-999") == []


def test_append_entry_writes_and_reads_back(tmp_path: Path) -> None:
    SU.append_entry(
        repo_root=tmp_path,
        saga_id="issue-345",
        transition="commit",
        tier="reversible",
        branch="feat/x",
        head_sha="abc123",
        remote_created=True,
    )
    entries = SU.read_manifest(tmp_path, "issue-345")
    assert len(entries) == 1
    assert entries[0]["transition"] == "commit"
    assert entries[0]["branch"] == "feat/x"
    assert entries[0]["undone"] is False


def test_append_entry_accumulates_in_order(tmp_path: Path) -> None:
    for transition in ("commit", "open_pr", "request_review"):
        SU.append_entry(
            repo_root=tmp_path, saga_id="issue-345", transition=transition, tier="reversible"
        )
    entries = SU.read_manifest(tmp_path, "issue-345")
    assert [e["transition"] for e in entries] == ["commit", "open_pr", "request_review"]


# --------------------------------------------------------------------------- #
# Empty / fully-undone manifest — no-op success (U3 Behavior)
# --------------------------------------------------------------------------- #


def test_empty_manifest_is_noop_success(tmp_path: Path) -> None:
    status = SU.undo(
        _saga("issue-345"), repo_root=tmp_path, operator_confirmed=None, runner=ExplodingRunner()
    )
    assert "no-op" in status


def test_fully_undone_manifest_is_noop_success(tmp_path: Path) -> None:
    SU.append_entry(repo_root=tmp_path, saga_id="issue-345", transition="commit", tier="reversible")
    entries = SU.read_manifest(tmp_path, "issue-345")
    entries[0]["undone"] = True
    SU._write_manifest(tmp_path, "issue-345", entries)  # noqa: SLF001 - test setup

    status = SU.undo(
        _saga("issue-345"), repo_root=tmp_path, operator_confirmed=None, runner=ExplodingRunner()
    )
    assert "no-op" in status


# --------------------------------------------------------------------------- #
# Reversible-only plan: killed right after PR-open (R7, KTD5 bare-flag path)
# --------------------------------------------------------------------------- #


def test_undo_after_kill_at_pr_open_closes_pr_and_deletes_branch(bare_repo) -> None:
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)
    assert _origin_ref_exists(bare_origin, branch)

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="commit",
        tier="reversible",
        branch=branch,
        head_sha=head_sha,
        remote_created=True,
    )
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="open_pr",
        tier="reversible",
        branch=branch,
        pr_number=7,
    )

    fake_gh = FakeGh()
    status = SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed=None, runner=fake_gh)

    assert "reverted 2" in status
    assert ["pr", "close", "7"] in fake_gh.gh_calls
    assert not _origin_ref_exists(bare_origin, branch)
    # Local commits stay — undo removes the pushed (remote) branch, not the
    # operator's own local work.
    assert _rev_parse(repo, branch) == head_sha

    entries = SU.read_manifest(repo, saga_id)
    assert all(e["undone"] for e in entries)


# --------------------------------------------------------------------------- #
# Gated plan: merge/branch_delete in scope requires operator_confirmed='undo'
# --------------------------------------------------------------------------- #


def test_undo_of_merged_ceremony_requires_operator_confirmed_undo(bare_repo) -> None:
    repo, _bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    head_sha = _make_feature_branch(repo, branch)
    merge_sha = _squash_merge_to_main(repo, branch)

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=branch,
        merge_sha=merge_sha,
        pr_number=7,
    )
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="branch_delete",
        tier="always_operator",
        branch=branch,
        head_sha=head_sha,
    )

    with pytest.raises(SU.UndoOperatorConfirmationError, match="always_operator"):
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed=None, runner=ExplodingRunner())

    # Refused before dispatch: manifest untouched.
    entries = SU.read_manifest(repo, saga_id)
    assert all(e["undone"] is False for e in entries)


def test_undo_gating_ignores_already_undone_entries(bare_repo) -> None:
    """KTD5: gating is computed from IN-SCOPE (not-yet-undone) entries only — an
    already-undone always_operator entry must not force operator confirmation on a
    later call that only has reversible work left to do."""
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)
    merge_sha = _squash_merge_to_main(repo, branch)

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=branch,
        merge_sha=merge_sha,
        pr_number=7,
    )
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="commit",
        tier="reversible",
        branch=branch,
        head_sha=head_sha,
        remote_created=True,
    )
    # Pre-mark the always_operator entry as already undone (simulating a prior,
    # confirmed undo() call that got this far).
    entries = SU.read_manifest(repo, saga_id)
    entries[0]["undone"] = True
    SU._write_manifest(repo, saga_id, entries)  # noqa: SLF001 - test setup

    fake_gh = FakeGh()
    status = SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed=None, runner=fake_gh)
    assert "reverted 1" in status
    assert not _origin_ref_exists(bare_origin, branch)


# --------------------------------------------------------------------------- #
# Full completion: revert commit on main + branch resurrected (R7, KTD4)
# --------------------------------------------------------------------------- #


def test_undo_reverts_completed_ceremony(bare_repo) -> None:
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    pre_merge_main_sha = _rev_parse(repo, "main")
    head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)
    merge_sha = _squash_merge_to_main(repo, branch)
    _git(repo, "push", "origin", "main")
    _delete_branch_everywhere(repo, branch)
    assert not _origin_ref_exists(bare_origin, branch)
    assert (repo / "change.txt").exists()  # the squash landed the file on main

    saga_id = "issue-346"
    # remote_created=False on the 'commit' entry here on purpose: this hand-built
    # manifest models a saga whose branch already existed remotely from an earlier
    # partial run, so undoing 'commit' is a no-op — keeps this test's assertions
    # focused on the merge-revert + branch-resurrection oracle the test name names,
    # without the (legitimate, but separately covered) remote-ref delete/recreate
    # interplay between the 'commit' and 'branch_delete' reverse steps.
    for transition, tier, extra in (
        ("commit", "reversible", {"remote_created": False}),
        ("open_pr", "reversible", {"pr_number": 7}),
        ("request_review", "reversible", {}),
        (
            "merge",
            "always_operator",
            {"merge_sha": merge_sha, "pre_merge_main_sha": pre_merge_main_sha, "pr_number": 7},
        ),
        ("checkout_main", "reversible", {}),
        ("pull", "reversible", {}),
        ("branch_delete", "always_operator", {"head_sha": head_sha}),
    ):
        SU.append_entry(
            repo_root=repo,
            saga_id=saga_id,
            transition=transition,
            tier=tier,
            branch=branch,
            **extra,
        )

    fake_gh = FakeGh()
    status = SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=fake_gh)

    assert "reverted 7" in status
    assert ["pr", "close", "7"] in fake_gh.gh_calls

    # Revert commit landed on main, undoing the squash's file addition.
    assert not (repo / "change.txt").exists()
    log = _git(repo, "log", "--oneline", "main").stdout
    assert "Revert" in log

    # Branch resurrected from its recorded head SHA, both locally and remotely.
    assert _rev_parse(repo, branch) == head_sha
    assert _origin_ref_exists(bare_origin, branch)

    entries = SU.read_manifest(repo, saga_id)
    assert all(e["undone"] for e in entries)


# --------------------------------------------------------------------------- #
# Resumable after partial failure (R7 Behavior)
# --------------------------------------------------------------------------- #


def test_undo_is_resumable_after_partial_failure(bare_repo) -> None:
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)
    merge_sha = _squash_merge_to_main(repo, branch)
    _git(repo, "push", "origin", "main")
    _delete_branch_everywhere(repo, branch)

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=branch,
        merge_sha=merge_sha,
        pr_number=7,
    )
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="branch_delete",
        tier="always_operator",
        branch=branch,
        head_sha=head_sha,
    )

    # branch_delete's reverse (newest, processed first) succeeds; merge's reverse
    # (processed second) fails on its 'git push origin main' — simulating a
    # revert-lands-locally-but-push-rejected failure.
    flaky = FlakyGh(fail_prefix=["git", "push", "origin", "main"])
    with pytest.raises(SU.UndoTransitionFailedError):
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=flaky)

    entries_after_failure = SU.read_manifest(repo, saga_id)
    by_transition = {e["transition"]: e for e in entries_after_failure}
    assert by_transition["branch_delete"]["undone"] is True
    assert by_transition["merge"]["undone"] is False
    assert _origin_ref_exists(bare_origin, branch)  # branch_delete undo did land

    # Resume with a working runner — must complete just the remaining entry.
    fake_gh = FakeGh()
    status = SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=fake_gh)
    assert "reverted 1" in status

    entries_final = SU.read_manifest(repo, saga_id)
    assert all(e["undone"] for e in entries_final)
    log = _git(repo, "log", "--oneline", "main").stdout
    assert "Revert" in log


# --------------------------------------------------------------------------- #
# Unreachable SHA — named failure, not fabricated state (KTD4)
# --------------------------------------------------------------------------- #


def test_unreachable_sha_named_failure(bare_repo) -> None:
    repo, _bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=branch,
        merge_sha=UNREACHABLE_SHA,
        pr_number=7,
    )

    with pytest.raises(SU.SHAUnreachableError) as excinfo:
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=FakeGh())
    assert excinfo.value.kind == "SHA_UNREACHABLE"
    assert UNREACHABLE_SHA in str(excinfo.value)

    entries = SU.read_manifest(repo, saga_id)
    assert entries[0]["undone"] is False


def test_unreachable_branch_delete_head_sha_named_failure(bare_repo) -> None:
    repo, _bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="branch_delete",
        tier="always_operator",
        branch=branch,
        head_sha=UNREACHABLE_SHA,
    )

    with pytest.raises(SU.SHAUnreachableError) as excinfo:
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=FakeGh())
    assert excinfo.value.kind == "SHA_UNREACHABLE"

    entries = SU.read_manifest(repo, saga_id)
    assert entries[0]["undone"] is False


# --------------------------------------------------------------------------- #
# Malformed manifest entries — fail loud with a named message, not a traceback
# from a missing key (defense in depth around U4's manifest writer).
# --------------------------------------------------------------------------- #


def test_undo_merge_entry_missing_merge_sha_raises(bare_repo) -> None:
    repo, _bare_origin = bare_repo
    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch="feat/pf-throwaway-346",
        pr_number=7,
        # merge_sha deliberately omitted.
    )
    with pytest.raises(SU.UndoTransitionFailedError, match="merge_sha"):
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=FakeGh())
    assert SU.read_manifest(repo, saga_id)[0]["undone"] is False


def test_undo_branch_delete_entry_missing_head_sha_raises(bare_repo) -> None:
    repo, _bare_origin = bare_repo
    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="branch_delete",
        tier="always_operator",
        branch="feat/pf-throwaway-346",
        # head_sha deliberately omitted.
    )
    with pytest.raises(SU.UndoTransitionFailedError, match="head_sha"):
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=FakeGh())
    assert SU.read_manifest(repo, saga_id)[0]["undone"] is False


def test_undo_unknown_transition_in_manifest_raises(tmp_path: Path) -> None:
    SU.append_entry(
        repo_root=tmp_path, saga_id="issue-346", transition="bogus_step", tier="reversible"
    )
    with pytest.raises(SU.ShipUndoError, match="no reverse handler"):
        SU.undo(_saga("issue-346"), repo_root=tmp_path, operator_confirmed=None, runner=None)


# --------------------------------------------------------------------------- #
# CLI wiring (KTD6 — a thin standalone wrapper; ship_ceremony.py/U4 calls undo()
# directly as a library function instead of shelling out to this CLI).
# --------------------------------------------------------------------------- #


def test_cli_show_prints_empty_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = SU.main(["--repo-root", str(tmp_path), "show", "--saga-id", "issue-999"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "[]"


def test_cli_undo_dispatches_end_to_end(bare_repo, capsys: pytest.CaptureFixture[str]) -> None:
    """Drives ``main(["undo", ...])`` all the way through ``_saga_cli`` (a real
    ``saga.py restore`` subprocess) and ``undo()`` — the one test exercising the CLI
    boundary rather than calling ``undo()`` as a library function directly."""
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)

    saga_py = ROOT / "plugins" / "saga" / "scripts" / "saga.py"
    mint = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(saga_py),
            "save",
            "--kind",
            "issue",
            "--id",
            "346",
            "--issue-ref",
            "org/repo#346",
            "--lifecycle-phase",
            "work",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert mint.returncode == 0, mint.stderr

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="commit",
        tier="reversible",
        branch=branch,
        head_sha=head_sha,
        remote_created=True,
    )
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="open_pr",
        tier="reversible",
        branch=branch,
        pr_number=7,
    )

    fake_gh = FakeGh()
    original = SU.subprocess.run
    SU.subprocess.run = fake_gh
    try:
        exit_code = SU.main(["--repo-root", str(repo), "undo", "--saga-id", saga_id])
    finally:
        SU.subprocess.run = original

    assert exit_code == 0
    assert "reverted 2" in capsys.readouterr().out
    assert not _origin_ref_exists(bare_origin, branch)


# --------------------------------------------------------------------------- #
# Code-review fix round (653f610 review): F1/F2/F3/F5/F6/F7 regression oracles
# --------------------------------------------------------------------------- #


def test_sha_reachable_fetches_missing_origin_object(bare_repo) -> None:  # noqa: ANN001
    """F1 (P1): a squash SHA that landed on origin but was never pulled locally is
    REACHABLE — _sha_reachable must fetch before declaring SHA_UNREACHABLE."""
    repo, bare_origin = bare_repo
    clone2 = repo.parent / "clone2"
    subprocess.run(  # noqa: S603, S607
        ["git", "clone", str(bare_origin), str(clone2)], check=True, capture_output=True
    )
    _git(clone2, "config", "user.email", "t@example.com")
    _git(clone2, "config", "user.name", "Test")
    # The bare origin's HEAD may not point at 'main' (ambient init.defaultBranch),
    # leaving the clone on an unborn branch — pin to origin/main explicitly.
    _git(clone2, "checkout", "-B", "main", "origin/main")
    (clone2 / "landed.txt").write_text("merged elsewhere\n")
    _git(clone2, "add", "landed.txt")
    _git(clone2, "commit", "-m", "squash landed on origin only")
    sha = _rev_parse(clone2, "HEAD")
    _git(clone2, "push", "origin", "HEAD:main")

    # Sanity: the object is genuinely absent from the local clone before the probe.
    local = _git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False)
    assert local.returncode != 0

    assert SU._sha_reachable(sha, repo_root=repo, runner=None) is True


def test_sha_unreachable_even_after_fetch(bare_repo) -> None:  # noqa: ANN001
    repo, _ = bare_repo
    assert SU._sha_reachable(UNREACHABLE_SHA, repo_root=repo, runner=None) is False


def test_sha_unreachable_error_carries_remedy() -> None:
    """F5 (P2): the named refusal must tell the operator the next step, matching the
    remedy contract of MergeExpectationMissingError / Hazard.remedy."""
    err = SU.SHAUnreachableError(UNREACHABLE_SHA, entry_transition="merge")
    assert err.remedy
    assert err.remedy in str(err)
    assert "git fetch origin" in str(err)


@pytest.mark.parametrize("bad_id", ["../evil", "..", "a/b", "-x", "", "/abs"])
def test_manifest_path_rejects_unsafe_saga_id(tmp_path: Path, bad_id: str) -> None:
    """F2 (P2): saga_id is a path component — traversal or option-like values
    refuse loud before any filesystem access."""
    with pytest.raises(SU.ShipUndoError):
        SU.manifest_path(tmp_path, bad_id)


def test_undo_rejects_unsafe_saga_id_before_anything(bare_repo) -> None:  # noqa: ANN001
    repo, _ = bare_repo
    with pytest.raises(SU.ShipUndoError):
        SU.undo(_saga("../evil"), repo_root=repo, runner=ExplodingRunner())


def test_option_like_branch_refused_before_shellout(bare_repo) -> None:  # noqa: ANN001
    """F3 (P2): a manifest-sourced branch beginning with '-' would parse as a git
    option — refused loud, and provably before any subprocess call."""
    repo, _ = bare_repo
    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="commit",
        tier="reversible",
        branch="--force",
        remote_created=True,
    )
    with pytest.raises(SU.ShipUndoError, match="begins with '-'"):
        SU.undo(_saga(saga_id), repo_root=repo, runner=ExplodingRunner())


def test_option_like_pr_number_refused_before_shellout(bare_repo) -> None:  # noqa: ANN001
    repo, _ = bare_repo
    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="open_pr",
        tier="reversible",
        branch="feat/x",
        pr_number="--repo evil",
    )
    with pytest.raises(SU.ShipUndoError, match="not a plain PR number"):
        SU.undo(_saga(saga_id), repo_root=repo, runner=ExplodingRunner())


def test_corrupt_manifest_is_named_refusal(tmp_path: Path) -> None:
    """F6 (P3): a truncated/garbled manifest surfaces as ShipUndoError, never a raw
    JSONDecodeError traceback."""
    path = SU.manifest_path(tmp_path, "issue-346")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[{not json", encoding="utf-8")
    with pytest.raises(SU.ShipUndoError, match="not valid JSON"):
        SU.read_manifest(tmp_path, "issue-346")


def test_manifest_write_is_atomic_no_tmp_left(tmp_path: Path) -> None:
    SU.append_entry(repo_root=tmp_path, saga_id="issue-346", transition="commit", tier="reversible")
    path = SU.manifest_path(tmp_path, "issue-346")
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


# --------------------------------------------------------------------------- #
# Base-aware merge revert (issue #635, defect F / R12): the undo applies the
# recorded squash sha to the branch the ceremony actually merged into. Recording
# the right sha (ship_ceremony._do_merge, R6) is only half the property — these
# oracles pin the other half.
# --------------------------------------------------------------------------- #


class RecordingRunner(FakeGh):
    """``FakeGh`` plus a transcript of EVERY command it is handed, git included.

    The base-targeting oracles below assert on argv, not only on resulting refs: a
    revert that lands on the wrong branch can still leave plausible-looking refs, so
    "which branch did the checkout/revert/push actually name" is the direct question."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        self.calls.append(list(cmd))
        return super().__call__(
            cmd, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )


OUTCOME_BRANCH = "outcome/demo"
LEAF_BRANCH = "feat/leaf-635"


def _make_leaf_into_outcome(repo: Path) -> tuple[str, str]:
    """The #635 topology: ``main`` → ``outcome/demo`` → ``feat/leaf-635``, with the
    leaf squash-merged into the OUTCOME branch — never into main. Returns
    ``(leaf_head_sha, merge_sha)``; ``merge_sha`` is the squash commit on
    ``outcome/demo``. Leaves HEAD on ``outcome/demo``."""
    _git(repo, "checkout", "main")
    _git(repo, "checkout", "-b", OUTCOME_BRANCH)
    _git(repo, "push", "-u", "origin", OUTCOME_BRANCH)
    _git(repo, "checkout", "-b", LEAF_BRANCH)
    (repo / "change.txt").write_text("leaf work\n")
    _git(repo, "add", "change.txt")
    _git(repo, "commit", "-m", "leaf work")
    head_sha = _rev_parse(repo, "HEAD")
    _git(repo, "push", "-u", "origin", LEAF_BRANCH)
    _git(repo, "checkout", OUTCOME_BRANCH)
    _git(repo, "merge", "--squash", LEAF_BRANCH)
    _git(repo, "commit", "-m", f"squash merge {LEAF_BRANCH}")
    merge_sha = _rev_parse(repo, OUTCOME_BRANCH)
    _git(repo, "push", "origin", OUTCOME_BRANCH)
    return head_sha, merge_sha


def _origin_sha(bare_origin: Path, ref: str) -> str:
    result = _git(Path.cwd(), "ls-remote", str(bare_origin), f"refs/heads/{ref}")
    return result.stdout.split()[0] if result.stdout.strip() else ""


def _append_merge_entry(repo: Path, saga_id: str, merge_sha: str, base: str | None) -> None:
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=LEAF_BRANCH,
        base=base,
        merge_sha=merge_sha,
        pr_number=7,
    )


def test_undo_merge_targets_recorded_base_not_main(bare_repo) -> None:  # noqa: ANN001
    """Headline (R12): with ``outcome/demo`` recorded as the ceremony's base, the
    checkout and the push both name ``outcome/demo`` and the revert runs there — and
    no command in the whole transition names ``main`` at all."""
    repo, _bare_origin = bare_repo
    _head_sha, merge_sha = _make_leaf_into_outcome(repo)
    # Where a real ceremony leaves HEAD by the time an undo runs (checkout_main).
    _git(repo, "checkout", "main")

    saga_id = "issue-635"
    _append_merge_entry(repo, saga_id, merge_sha, OUTCOME_BRANCH)

    runner = RecordingRunner()
    SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=runner)

    assert ["git", "checkout", OUTCOME_BRANCH] in runner.calls
    assert ["git", "revert", "--no-edit", merge_sha] in runner.calls
    assert ["git", "push", "origin", OUTCOME_BRANCH] in runner.calls
    assert [call for call in runner.calls if "main" in call] == []
    # A recorded base is authoritative: no default-branch probe, no gh round trip.
    assert ["git", "symbolic-ref", "refs/remotes/origin/HEAD"] not in runner.calls
    assert runner.gh_calls == []


def test_undo_merge_does_not_touch_main_when_outcome_already_landed(bare_repo) -> None:  # noqa: ANN001
    """The destructive hazard the refute panel found: once the outcome branch has
    itself landed on ``main``, the leaf's squash sha is an ANCESTOR of main, so a
    revert aimed at main applies cleanly and silently strips the leaf's work off the
    default branch. Nothing refuses it — so the target, not the guard, is the fix."""
    repo, bare_origin = bare_repo
    _head_sha, merge_sha = _make_leaf_into_outcome(repo)
    # The outcome branch lands on main (fast-forward, as an outcome PR's squash would).
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--ff-only", OUTCOME_BRANCH)
    _git(repo, "push", "origin", "main")
    main_before = _rev_parse(repo, "main")
    # Precondition that makes this destructive rather than merely wrong: the recorded
    # sha IS reachable from main, so `git revert` there would succeed.
    assert _git(repo, "merge-base", "--is-ancestor", merge_sha, "main", check=False).returncode == 0

    saga_id = "issue-635"
    _append_merge_entry(repo, saga_id, merge_sha, OUTCOME_BRANCH)

    runner = RecordingRunner()
    SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=runner)

    # main is untouched, locally and on origin, and still carries the leaf's work.
    assert _rev_parse(repo, "main") == main_before
    assert _origin_sha(bare_origin, "main") == main_before
    assert _git(repo, "show", "main:change.txt").stdout == "leaf work\n"
    assert "Revert" not in _git(repo, "log", "--oneline", "main").stdout
    # The revert landed where the merge did.
    assert "Revert" in _git(repo, "log", "--oneline", OUTCOME_BRANCH).stdout
    assert _origin_sha(bare_origin, OUTCOME_BRANCH) == _rev_parse(repo, OUTCOME_BRANCH)
    assert [call for call in runner.calls if "main" in call] == []


def test_undo_merge_without_recorded_base_floors_at_legacy_main(bare_repo) -> None:  # noqa: ANN001
    """Backward compatibility (R12): a manifest written before #635 has no ``base``
    key at all. Its ``merge_sha`` was read by a pre-#635 ``_do_merge`` that probed
    ``refs/heads/main`` verbatim, so the revert must land on the *literal* ``main`` —
    the pre-#635 behavior, argv for argv. Resolving the repo's current default branch
    instead is refused by construction; see the sibling trunk-default regression."""
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    _head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)
    merge_sha = _squash_merge_to_main(repo, branch)
    _git(repo, "push", "origin", "main")
    # HEAD off the default branch so the checkout step actually runs and can be asserted.
    _git(repo, "checkout", branch)

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=branch,
        merge_sha=merge_sha,
        pr_number=7,
    )
    # Model a genuinely pre-#635 manifest: the key is absent, not merely null.
    entries = SU.read_manifest(repo, saga_id)
    del entries[0]["base"]
    SU._write_manifest(repo, saga_id, entries)  # noqa: SLF001 - test setup
    assert "base" not in SU.read_manifest(repo, saga_id)[0]

    runner = RecordingRunner()
    SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=runner)

    # The default branch is NOT consulted: provenance, not currency, picks the target.
    assert ["git", "symbolic-ref", "refs/remotes/origin/HEAD"] not in runner.calls
    # ...and the resulting mutations are exactly the pre-#635 ones.
    assert ["git", "checkout", "main"] in runner.calls
    assert ["git", "revert", "--no-edit", merge_sha] in runner.calls
    assert ["git", "push", "origin", "main"] in runner.calls
    assert not (repo / "change.txt").exists()
    assert "Revert" in _git(repo, "log", "--oneline", "main").stdout
    assert _origin_sha(bare_origin, "main") == _rev_parse(repo, "main")


def test_undo_merge_on_main_based_ceremony_is_unchanged(bare_repo) -> None:  # noqa: ANN001
    """The common case stays the common case: a ceremony whose recorded base IS the
    default branch reverts on main exactly as before."""
    repo, bare_origin = bare_repo
    branch = "feat/pf-throwaway-346"
    _head_sha = _make_feature_branch(repo, branch)
    _git(repo, "push", "-u", "origin", branch)
    merge_sha = _squash_merge_to_main(repo, branch)
    _git(repo, "push", "origin", "main")
    _git(repo, "checkout", branch)

    saga_id = "issue-346"
    SU.append_entry(
        repo_root=repo,
        saga_id=saga_id,
        transition="merge",
        tier="always_operator",
        branch=branch,
        base="main",
        merge_sha=merge_sha,
        pr_number=7,
    )

    runner = RecordingRunner()
    SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=runner)

    assert ["git", "checkout", "main"] in runner.calls
    assert ["git", "revert", "--no-edit", merge_sha] in runner.calls
    assert ["git", "push", "origin", "main"] in runner.calls
    assert ["git", "symbolic-ref", "refs/remotes/origin/HEAD"] not in runner.calls
    assert not (repo / "change.txt").exists()
    assert "Revert" in _git(repo, "log", "--oneline", "main").stdout
    assert _origin_sha(bare_origin, "main") == _rev_parse(repo, "main")


def test_option_like_recorded_base_refused_before_shellout(bare_repo) -> None:  # noqa: ANN001
    """The recorded base becomes git argv on the destructive path — a value opening
    with '-' refuses loud, and provably before this handler shells out at all."""
    repo, _bare_origin = bare_repo
    _head_sha, merge_sha = _make_leaf_into_outcome(repo)

    saga_id = "issue-635"
    _append_merge_entry(repo, saga_id, merge_sha, "--exec=touch pwned")

    with pytest.raises(SU.ShipUndoError, match="begins with '-'"):
        SU.undo(_saga(saga_id), repo_root=repo, operator_confirmed="undo", runner=ExplodingRunner())


def test_base_less_entry_ignores_a_non_main_default_branch(bare_repo) -> None:  # noqa: ANN001
    """R12 regression. A base-less (pre-#635) entry must floor at the literal ``main``
    even when the repository's default branch is something else.

    Resolving ``refs/remotes/origin/HEAD`` here would send the revert to whatever the
    default happens to be *today* — a branch the recorded sha was never read from. The
    sha's provenance is ``refs/heads/main``, because that is the ref the pre-#635
    ``_do_merge`` probed verbatim; provenance wins over currency."""
    repo, _bare_origin = bare_repo
    # Make the repo's default branch genuinely not 'main'.
    _git(repo, "checkout", "-b", "trunk")
    _git(repo, "push", "-u", "origin", "trunk")
    _git(repo, "remote", "set-head", "origin", "trunk")
    head = _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD").stdout.strip()
    assert head == "refs/remotes/origin/trunk"

    assert SU._merge_entry_base({"transition": "merge"}) == "main"  # noqa: SLF001 - unit
    assert SU.LEGACY_MERGE_BASE == "main"
    # A recorded base still wins outright — the floor is only for entries without one.
    assert SU._merge_entry_base({"transition": "merge", "base": "outcome/x"}) == "outcome/x"  # noqa: SLF001
