"""ship_teardown.py tests (issue #347, U1 — manifest + reality-checked closing count).

Test design: a module-local ``FakeRunner`` (distinct from every other ceremony
module's own fake, per house convention) drives ``git`` / ``gh`` calls that
``reconcile``'s per-kind probes shell out to; tests never touch the real network or
a real worktree. Test names follow ``test_AC_<n>_<scenario>`` for the issue's
numbered acceptance criteria, plain ``test_<scenario>`` for supporting coverage.

Oracles (U1 scope — manifest register/close/read + reconcile):

* register/close — idempotent register (refreshes ``opened_at`` only while open,
  no-ops once closed), close refuses on an unknown id, both round-trip through the
  atomic sidecar.
* reconcile — closing count 0 on a fully-closed manifest (CLEAN); non-zero count
  names every open/discrepancy entry (HALT); a closed-but-still-alive worktree is
  flagged ``discrepancy`` and counts as open (AC4, R5); corrupt JSON / traversal
  saga_id / atomic-write oracles mirror ``test_merge_watcher.py``'s hardening
  suite.

U3/U4-level scenarios (reclaim, ceremony wiring, receipt) are out of scope for this
file section per the plan — they land in their own U2-U4 sections.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SHIP_TEARDOWN_PATH = ROOT / "plugins" / "saga" / "scripts" / "ship_teardown.py"


def _load_ship_teardown() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ship_teardown", SHIP_TEARDOWN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ST = _load_ship_teardown()

SHIP_RECEIPT_PATH = ROOT / "plugins" / "saga" / "scripts" / "ship_receipt.py"


def _load_ship_receipt() -> ModuleType:
    # ship_receipt.py does `import ship_teardown as ST` via a sys.path.insert of its
    # own directory (mirrors ship_ceremony.py's sibling-import pattern) — importing
    # it here after ST is already loaded reuses that same module object rather than
    # re-executing ship_teardown.py a second time.
    spec = importlib.util.spec_from_file_location("ship_receipt", SHIP_RECEIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SR = _load_ship_receipt()


def _ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


class FakeRunner:
    """A tiny, module-local fake for the ``git`` / ``gh`` calls ``reconcile``'s
    per-kind probes issue. Configured per-kind so a single reconcile pass covering
    branch + worktree + scratch + draft_pr entries can be driven from one fixture.
    """

    def __init__(
        self,
        *,
        alive_branches: set[str] | None = None,
        worktree_list_stdout: str = "",
        worktree_list_fails: bool = False,
        pr_states: dict[str, str] | None = None,
        gh_fails: bool = False,
    ) -> None:
        self.alive_branches = alive_branches or set()
        self.worktree_list_stdout = worktree_list_stdout
        self.worktree_list_fails = worktree_list_fails
        self.pr_states = pr_states or {}
        self.gh_fails = gh_fails
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        args = list(cmd)
        self.calls.append(args)
        if args[:2] == ["git", "rev-parse"]:
            ref = args[-1]
            if ref in self.alive_branches:
                return _ok(ref)
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")
        if args[:3] == ["git", "worktree", "list"]:
            if self.worktree_list_fails:
                return _fail("git worktree list failed")
            return _ok(self.worktree_list_stdout)
        if args[:3] == ["gh", "pr", "view"]:
            if self.gh_fails:
                return _fail("gh pr view failed")
            pr_number = args[3]
            state = self.pr_states.get(pr_number, "MERGED")
            return _ok(json.dumps({"state": state}))
        raise AssertionError(f"unhandled fake call: {args!r}")


# --------------------------------------------------------------------------- #
# register / close (R1)
# --------------------------------------------------------------------------- #


def test_register_creates_open_entry(tmp_path: Path) -> None:
    entry = ST.register(
        tmp_path,
        "issue-347",
        "wt-1",
        kind="worktree",
        ref="/tmp/wt-1",
        opened_by="ship_ceremony.start",
    )
    assert entry["kind"] == "worktree"
    assert entry["closed_at"] == ""
    manifest = ST.read_manifest(tmp_path, "issue-347")
    assert "wt-1" in manifest


def test_register_rejects_invalid_kind(tmp_path: Path) -> None:
    with pytest.raises(ST.InvalidResourceKindError):
        ST.register(tmp_path, "issue-347", "x", kind="bogus", ref="x", opened_by="test")


def test_register_is_idempotent_refreshes_while_open(tmp_path: Path) -> None:
    ST.register(
        tmp_path,
        "issue-347",
        "branch-1",
        kind="branch",
        ref="issue-347",
        opened_by="start",
        now="2026-01-01T00:00:00+00:00",
    )
    second = ST.register(
        tmp_path,
        "issue-347",
        "branch-1",
        kind="branch",
        ref="issue-347",
        opened_by="start",
        now="2026-01-02T00:00:00+00:00",
    )
    assert second["opened_at"] == "2026-01-02T00:00:00+00:00"


def test_register_no_ops_once_closed(tmp_path: Path) -> None:
    ST.register(
        tmp_path, "issue-347", "branch-1", kind="branch", ref="issue-347", opened_by="start"
    )
    ST.close(tmp_path, "issue-347", "branch-1", evidence="deleted sha-abc")
    reopened = ST.register(
        tmp_path,
        "issue-347",
        "branch-1",
        kind="branch",
        ref="issue-347",
        opened_by="start",
        now="2099-01-01T00:00:00+00:00",
    )
    assert reopened["closed_at"] != ""
    assert reopened["opened_at"] != "2099-01-01T00:00:00+00:00"


def test_close_records_evidence(tmp_path: Path) -> None:
    ST.register(tmp_path, "issue-347", "pr-1", kind="draft_pr", ref="12", opened_by="_do_open_pr")
    closed = ST.close(tmp_path, "issue-347", "pr-1", evidence="merged sha-xyz")
    assert closed["close_evidence"] == "merged sha-xyz"
    assert closed["closed_at"] != ""


def test_close_unknown_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ST.UnknownResourceError):
        ST.close(tmp_path, "issue-347", "does-not-exist", evidence="whatever")


# --------------------------------------------------------------------------- #
# reconcile — happy path + AC1/AC4
# --------------------------------------------------------------------------- #


def test_happy_path_all_closed_reports_clean(tmp_path: Path) -> None:
    ST.register(
        tmp_path, "issue-347", "branch-1", kind="branch", ref="issue-347", opened_by="start"
    )
    ST.register(
        tmp_path, "issue-347", "wt-1", kind="worktree", ref="/tmp/wt-1", opened_by="reclaim"
    )
    ST.register(
        tmp_path,
        "issue-347",
        "scratch-1",
        kind="scratch",
        ref=str(tmp_path / "scratch"),
        opened_by="work",
    )
    ST.close(tmp_path, "issue-347", "branch-1", evidence="deleted sha-abc")
    ST.close(tmp_path, "issue-347", "wt-1", evidence="removed")
    ST.close(tmp_path, "issue-347", "scratch-1", evidence="rmtree'd")

    runner = FakeRunner(alive_branches=set(), worktree_list_stdout="")
    report = ST.reconcile(tmp_path, "issue-347", runner=runner)

    assert report.closing_count == 0
    assert report.clean is True


def test_AC_1_blocks_on_nonzero_closing_count(tmp_path: Path) -> None:
    # Two orphan worktree entries + one open background_session entry (AC1 seed shape).
    ST.register(
        tmp_path,
        "issue-347",
        "wt-orphan-1",
        kind="worktree",
        ref="/tmp/orphan-1",
        opened_by="reclaim",
    )
    ST.register(
        tmp_path,
        "issue-347",
        "wt-orphan-2",
        kind="worktree",
        ref="/tmp/orphan-2",
        opened_by="reclaim",
    )
    ST.register(
        tmp_path,
        "issue-347",
        "session-1",
        kind="background_session",
        ref="sess-abc123",
        opened_by="skill-spawn",
    )

    runner = FakeRunner()
    report = ST.reconcile(tmp_path, "issue-347", runner=runner)

    assert report.closing_count == 3
    ids = {e.resource_id for e in report.blockers}
    assert ids == {"wt-orphan-1", "wt-orphan-2", "session-1"}
    assert report.clean is False


def test_AC_4_flags_surviving_worktree_despite_claim(tmp_path: Path) -> None:
    worktree_path = tmp_path / "still-here"
    worktree_path.mkdir()
    ST.register(
        tmp_path,
        "issue-347",
        "wt-1",
        kind="worktree",
        ref=str(worktree_path),
        opened_by="reclaim",
    )
    ST.close(tmp_path, "issue-347", "wt-1", evidence="claimed removed but was not")

    runner = FakeRunner(worktree_list_stdout=f"worktree {worktree_path}\nHEAD abc123\n\n")
    report = ST.reconcile(tmp_path, "issue-347", runner=runner)

    assert report.closing_count == 1
    entry = report.entries[0]
    assert entry.status == ST.STATUS_DISCREPANCY
    assert entry.resource_id == "wt-1"


def test_reconcile_branch_still_resolvable_is_discrepancy(tmp_path: Path) -> None:
    ST.register(
        tmp_path, "issue-347", "branch-1", kind="branch", ref="issue-347", opened_by="start"
    )
    ST.close(tmp_path, "issue-347", "branch-1", evidence="claimed deleted")

    runner = FakeRunner(alive_branches={"issue-347"})
    report = ST.reconcile(tmp_path, "issue-347", runner=runner)

    assert report.closing_count == 1
    assert report.entries[0].status == ST.STATUS_DISCREPANCY


def test_reconcile_open_draft_pr_still_open_is_discrepancy(tmp_path: Path) -> None:
    ST.register(tmp_path, "issue-347", "pr-1", kind="draft_pr", ref="42", opened_by="open_pr")
    ST.close(tmp_path, "issue-347", "pr-1", evidence="claimed merged")

    runner = FakeRunner(pr_states={"42": "OPEN"})
    report = ST.reconcile(tmp_path, "issue-347", runner=runner)

    assert report.closing_count == 1
    assert report.entries[0].status == ST.STATUS_DISCREPANCY


def test_reconcile_closed_draft_pr_merged_is_verified(tmp_path: Path) -> None:
    ST.register(tmp_path, "issue-347", "pr-1", kind="draft_pr", ref="42", opened_by="open_pr")
    ST.close(tmp_path, "issue-347", "pr-1", evidence="merged sha-xyz")

    runner = FakeRunner(pr_states={"42": "MERGED"})
    report = ST.reconcile(tmp_path, "issue-347", runner=runner)

    assert report.closing_count == 0
    assert report.entries[0].status == ST.STATUS_CLOSED_VERIFIED


def test_reconcile_scratch_dir_still_present_is_discrepancy(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch-dir"
    scratch.mkdir()
    ST.register(
        tmp_path, "issue-347", "scratch-1", kind="scratch", ref=str(scratch), opened_by="work"
    )
    ST.close(tmp_path, "issue-347", "scratch-1", evidence="claimed rmtree'd")

    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())

    assert report.closing_count == 1
    assert report.entries[0].status == ST.STATUS_DISCREPANCY


def test_reconcile_closed_background_session_is_trusted(tmp_path: Path) -> None:
    # KTD4: no liveness oracle exists for background_session; an explicit close with
    # evidence is trusted (there is nothing left to probe).
    ST.register(
        tmp_path,
        "issue-347",
        "session-1",
        kind="background_session",
        ref="sess-1",
        opened_by="skill-spawn",
    )
    ST.close(tmp_path, "issue-347", "session-1", evidence="observed exit 0")

    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())

    assert report.closing_count == 0
    assert report.entries[0].status == ST.STATUS_CLOSED_VERIFIED


# --------------------------------------------------------------------------- #
# Edges: empty manifest, corrupt JSON, traversal saga_id, atomicity
# --------------------------------------------------------------------------- #


def test_reconcile_empty_manifest_is_clean(tmp_path: Path) -> None:
    report = ST.reconcile(tmp_path, "issue-999", runner=FakeRunner())
    assert report.closing_count == 0
    assert report.clean is True
    assert report.entries == []


def test_corrupt_manifest_json_raises_wrapped_error(tmp_path: Path) -> None:
    path = ST.manifest_path(tmp_path, "issue-347")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ST.ShipTeardownError, match="not valid JSON"):
        ST.read_manifest(tmp_path, "issue-347")


def test_traversal_saga_id_rejected(tmp_path: Path) -> None:
    with pytest.raises(ST.ShipTeardownError, match="invalid saga_id"):
        ST.register(tmp_path, "../evil", "x", kind="branch", ref="x", opened_by="test")


def test_traversal_saga_id_rejected_on_reconcile(tmp_path: Path) -> None:
    with pytest.raises(ST.ShipTeardownError, match="invalid saga_id"):
        ST.reconcile(tmp_path, "../../etc", runner=FakeRunner())


def test_manifest_write_is_atomic_no_tmp_left(tmp_path: Path) -> None:
    ST.register(
        tmp_path, "issue-347", "branch-1", kind="branch", ref="issue-347", opened_by="start"
    )
    path = ST.manifest_path(tmp_path, "issue-347")
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


# --------------------------------------------------------------------------- #
# CLI reconcile verb — CLEAN / HALT, read-only
# --------------------------------------------------------------------------- #


def test_cli_reconcile_prints_clean_on_empty_manifest(tmp_path: Path, capsys: Any) -> None:
    exit_code = ST.main(["--repo-root", str(tmp_path), "reconcile", "--saga-id", "issue-347"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "CLEAN"


def test_cli_reconcile_prints_halt_with_named_blockers(tmp_path: Path, capsys: Any) -> None:
    ST.register(
        tmp_path, "issue-347", "wt-orphan", kind="worktree", ref="/tmp/orphan", opened_by="reclaim"
    )
    exit_code = ST.main(["--repo-root", str(tmp_path), "reconcile", "--saga-id", "issue-347"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "HALT" in captured.out
    assert "wt-orphan" in captured.out


def test_AC_2_dry_run_halt_on_surviving_worktree(tmp_path: Path, capsys: Any) -> None:
    """AC2: the read-only ``reconcile`` verb against a seeded surviving-worktree scenario
    (an entry marked closed whose worktree still exists on disk — a discrepancy) prints
    HALT, names the blocker, mutates nothing, and mints no receipt. This is the dry-run
    that halts the ceremony before any teardown side effect."""
    worktree_path = tmp_path / "survivor"
    worktree_path.mkdir()
    ST.register(
        tmp_path, "issue-347", "wt-1", kind="worktree", ref=str(worktree_path), opened_by="reclaim"
    )
    ST.close(tmp_path, "issue-347", "wt-1", evidence="claimed removed but survives")

    manifest_before = ST.manifest_path(tmp_path, "issue-347").read_text(encoding="utf-8")

    runner = FakeRunner(worktree_list_stdout=f"worktree {worktree_path}\nHEAD abc\n\n")
    # Drive the CLI's reconcile verb through the same probe path (monkeypatch the module
    # subprocess.run so the CLI, which does not take a runner, still uses the fake).
    original = ST.subprocess.run
    ST.subprocess.run = runner
    try:
        exit_code = ST.main(["--repo-root", str(tmp_path), "reconcile", "--saga-id", "issue-347"])
    finally:
        ST.subprocess.run = original
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "HALT" in captured.out
    assert "wt-1" in captured.out
    # Dry-run: the manifest is untouched and no receipt was minted.
    assert ST.manifest_path(tmp_path, "issue-347").read_text(encoding="utf-8") == manifest_before
    assert not SR.receipt_path(tmp_path, "issue-347").exists()


def test_cli_reconcile_never_mutates_manifest(tmp_path: Path, capsys: Any) -> None:
    ST.register(
        tmp_path, "issue-347", "branch-1", kind="branch", ref="issue-347", opened_by="start"
    )
    path = ST.manifest_path(tmp_path, "issue-347")
    before = path.read_text(encoding="utf-8")
    ST.main(["--repo-root", str(tmp_path), "reconcile", "--saga-id", "issue-347"])
    capsys.readouterr()
    after = path.read_text(encoding="utf-8")
    assert before == after


# --------------------------------------------------------------------------- #
# ship_receipt.py — immutable receipt (U2, R4, KTD5)
# --------------------------------------------------------------------------- #


def _closed_manifest(tmp_path: Path, saga_id: str = "issue-347") -> None:
    ST.register(tmp_path, saga_id, "branch-1", kind="branch", ref=saga_id, opened_by="start")
    ST.register(tmp_path, saga_id, "wt-1", kind="worktree", ref="/tmp/wt-1", opened_by="reclaim")
    ST.close(tmp_path, saga_id, "branch-1", evidence="deleted sha-abc")
    ST.close(tmp_path, saga_id, "wt-1", evidence="removed")


def test_AC_3_immutable_receipt_recorded(tmp_path: Path) -> None:
    _closed_manifest(tmp_path)
    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())
    assert report.clean is True

    path = SR.mint(
        tmp_path,
        "issue-347",
        report,
        {"pr": 42, "merge_sha": "sha-final", "branch": "issue-347", "final_transition": "teardown"},
    )

    assert path.exists()
    mode = path.stat().st_mode
    assert stat.S_IMODE(mode) == 0o444

    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["saga_id"] == "issue-347"
    assert set(receipt["opened"].keys()) == {"branch-1", "wt-1"}
    for resource_id in ("branch-1", "wt-1"):
        assert receipt["opened"][resource_id]["closed_at"] != ""
    closed_ids = {e["resource_id"] for e in receipt["closed"]["entries"]}
    assert closed_ids == {"branch-1", "wt-1"}
    assert receipt["closed"]["closing_count"] == 0
    assert receipt["ceremony"]["merge_sha"] == "sha-final"

    # A second mint against the same saga_id raises rather than silently overwriting.
    with pytest.raises(SR.ReceiptExistsError):
        SR.mint(
            tmp_path,
            "issue-347",
            report,
            {"pr": 42, "merge_sha": "sha-final", "branch": "issue-347"},
        )

    # An in-place write attempt via the writer API (not mint) raises rather than
    # silently overwriting — the filesystem enforces this, not just convention.
    with pytest.raises(OSError):
        path.write_text("tampered", encoding="utf-8")


def test_mint_against_nonzero_count_creates_no_file(tmp_path: Path) -> None:
    ST.register(
        tmp_path, "issue-347", "wt-orphan", kind="worktree", ref="/tmp/orphan", opened_by="reclaim"
    )
    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())
    assert report.clean is False

    with pytest.raises(SR.TeardownBlockedError):
        SR.mint(tmp_path, "issue-347", report, {"pr": 1})

    path = SR.receipt_path(tmp_path, "issue-347")
    assert not path.exists()


def test_read_missing_receipt_raises_not_minted(tmp_path: Path) -> None:
    with pytest.raises(SR.ReceiptNotMintedError):
        SR.read(tmp_path, "issue-347", reprobe=False)


def test_read_corrupt_receipt_raises_wrapped_error(tmp_path: Path) -> None:
    path = SR.receipt_path(tmp_path, "issue-347")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SR.InvalidReceiptError, match="not valid JSON"):
        SR.read(tmp_path, "issue-347", reprobe=False)


def test_read_receipt_missing_schema_keys_raises(tmp_path: Path) -> None:
    path = SR.receipt_path(tmp_path, "issue-347")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"saga_id": "issue-347"}), encoding="utf-8")

    with pytest.raises(SR.InvalidReceiptError, match="missing required keys"):
        SR.read(tmp_path, "issue-347", reprobe=False)


def test_read_empty_opened_receipt_is_valid(tmp_path: Path) -> None:
    # A ceremony that opened zero resources still mints a valid, empty receipt.
    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())
    assert report.clean is True
    SR.mint(tmp_path, "issue-347", report, {"pr": 7})

    receipt = SR.read(tmp_path, "issue-347", reprobe=False)
    assert receipt["opened"] == {}
    assert receipt["closed"]["closing_count"] == 0
    assert receipt["anomalies"] == []


def test_read_never_writes_receipt(tmp_path: Path) -> None:
    _closed_manifest(tmp_path)
    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())
    path = SR.mint(tmp_path, "issue-347", report, {"pr": 42})
    before = path.read_bytes()

    SR.read(tmp_path, "issue-347", runner=FakeRunner(), reprobe=True)

    after = path.read_bytes()
    assert before == after
    assert stat.S_IMODE(path.stat().st_mode) == 0o444


def test_read_surfaces_anomaly_when_reality_contradicts_receipt(tmp_path: Path) -> None:
    # Mint a clean receipt, then make the worktree it claimed as closed reappear on
    # disk before read() re-probes — read() must name the anomaly, not edit the
    # receipt.
    worktree_path = tmp_path / "still-here"
    ST.register(
        tmp_path, "issue-347", "wt-1", kind="worktree", ref=str(worktree_path), opened_by="reclaim"
    )
    ST.close(tmp_path, "issue-347", "wt-1", evidence="removed")
    clean_report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())
    assert clean_report.clean is True
    path = SR.mint(tmp_path, "issue-347", clean_report, {"pr": 42})
    before = path.read_bytes()

    worktree_path.mkdir()
    runner = FakeRunner(worktree_list_stdout=f"worktree {worktree_path}\nHEAD abc123\n\n")
    receipt = SR.read(tmp_path, "issue-347", runner=runner, reprobe=True)

    assert receipt["anomalies"]
    assert any("wt-1" in anomaly for anomaly in receipt["anomalies"])
    # Still never written back.
    assert path.read_bytes() == before


def test_cli_receipt_read_reports_anomaly_exit_code(tmp_path: Path, capsys: Any) -> None:
    report = ST.reconcile(tmp_path, "issue-347", runner=FakeRunner())
    SR.mint(tmp_path, "issue-347", report, {"pr": 42})

    exit_code = SR.main(
        ["--repo-root", str(tmp_path), "read", "--saga-id", "issue-347", "--no-reprobe"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["saga_id"] == "issue-347"


# --------------------------------------------------------------------------- #
# reclaim — certificate-gated merged-worktree reclamation (U3, R6/R7, KTD6-8)
#
# Real-git fixtures over a bare "origin" clone (mirrors test_ship_undo.py's rig).
# Merged-ness is real: a worktree branch pinned at main's tip becomes a strict
# ancestor of main once main advances, so `git merge-base --is-ancestor` decides it
# exactly as reclaim does — no probe faking. The certificate/registry/idle oracles
# below pin AC5 (merged-vs-unmerged), the GATE monkeypatch, the dirty skip, the
# recent-activity idle guard, .saga-worktrees deregister, and --if-idle fresh/aged.
# --------------------------------------------------------------------------- #


def _wt_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603, S607
        ["git", "-C", str(repo), *args], check=check, capture_output=True, text=True
    )


@pytest.fixture()
def wt_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real throwaway repo cloned from a real local bare 'origin', main pushed."""
    bare_origin = tmp_path / "origin.git"
    subprocess.run(  # noqa: S607
        ["git", "init", "--bare", str(bare_origin)], check=True, capture_output=True
    )
    repo = tmp_path / "repo"
    subprocess.run(  # noqa: S607
        ["git", "clone", str(bare_origin), str(repo)], check=True, capture_output=True
    )
    _wt_git(repo, "config", "user.email", "t@example.com")
    _wt_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _wt_git(repo, "add", "README.md")
    _wt_git(repo, "commit", "-m", "init")
    _wt_git(repo, "branch", "-M", "main")
    _wt_git(repo, "push", "origin", "HEAD:main")
    return repo, bare_origin


def _advance_main(repo: Path, name: str = "adv.txt", msg: str = "advance main") -> None:
    """One more commit on main so any worktree pinned at the prior tip is a strict
    ancestor (merged) rather than equal."""
    (repo / name).write_text("advance\n")
    _wt_git(repo, "add", name)
    _wt_git(repo, "commit", "-m", msg)


def _live_worktree_paths(repo: Path) -> set[str]:
    out = _wt_git(repo, "worktree", "list", "--porcelain").stdout
    return {
        os.path.realpath(line[len("worktree ") :].strip())
        for line in out.splitlines()
        if line.startswith("worktree ")
    }


def _rp(path: Path) -> str:
    return os.path.realpath(str(path))


def _load_scripts_module(name: str) -> ModuleType:
    # ship_teardown.py puts the scripts dir on sys.path at load, so a bare
    # import_module resolves; loading under the canonical name means reclaim's own
    # lazy `import outcome_worktrees` reuses THIS object (shared registry state).
    return importlib.import_module(name)


class _FailRemoveRunner:
    """Passes every git call through to the real binary EXCEPT ``git worktree
    remove``, which it fails once-and-always — to drive the registry keep-on-failure
    path (reap_worktree returns False, the entry stays)."""

    def __init__(self) -> None:
        self._real = subprocess.run

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        if "worktree" in parts and "remove" in parts:
            return subprocess.CompletedProcess(parts, 1, "", "simulated remove failure")
        return self._real(  # nosec B603
            parts, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )


class _FailCommonDirRunner:
    """Pass real Git probes except the outcome store's common-dir resolution."""

    def __call__(self, cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001
        parts = list(cmd)
        if parts == ["git", "rev-parse", "--git-common-dir"]:
            return subprocess.CompletedProcess(parts, 1, "", "simulated common-dir failure")
        return subprocess.run(  # nosec B603
            parts, cwd=cwd, capture_output=capture_output, text=text, timeout=timeout
        )


def _lease_bound_outcome_worktree(
    repo: Path, *, outcome_id: str, subplot_id: str
) -> tuple[Any, Any, Any, Any, Path]:
    """Create a real Git outcome worktree carrying a real broker receipt."""
    outcome_spec = _load_scripts_module("outcome_spec")
    outcome_store = _load_scripts_module("outcome_store")
    outcome_worktrees = _load_scripts_module("outcome_worktrees")
    spec = outcome_spec.OutcomeSpec.from_dict(
        {
            "outcome_id": outcome_id,
            "objective": "lease teardown regression",
            "nodes": [
                {
                    "subplot_id": subplot_id,
                    "title": subplot_id,
                    "kind": "code",
                    "child_spec_ref": f"child-{subplot_id}",
                    "github": {"issue": "42"},
                },
                {
                    "subplot_id": "dependent",
                    "title": "dependent",
                    "kind": "code",
                    "depends_on": [subplot_id],
                },
            ],
        }
    )
    store = outcome_store.Store.for_outcome(outcome_id, repo).ensure()
    broker = outcome_worktrees.fleet_leases.authority.LeaseBroker(repo / ".test-fleet")
    ops = outcome_worktrees.git_worktree_ops(repo)
    created = outcome_worktrees.ensure_worktree(
        repo,
        spec,
        store,
        spec.nodes[0],
        ops,
        owner="teardown-regression",
        lease_authority=broker,
    )
    assert created.state == "created"
    return outcome_worktrees, spec, store, broker, Path(created.path)


def _managed_merged_worktree(repo: Path, *, outcome_id: str, subplot_id: str) -> Path:
    path = repo / ".saga-worktrees" / outcome_id / subplot_id
    path.parent.mkdir(parents=True, exist_ok=True)
    _wt_git(
        repo,
        "worktree",
        "add",
        "-b",
        f"saga-outcome-{outcome_id}-{subplot_id}",
        str(path),
        "main",
    )
    _advance_main(repo)
    return path


def _issue_closer(sink: list[str]) -> Any:
    def close(issue: str) -> bool:
        sink.append(issue)
        return True

    return close


def test_AC_5_reclaim_merged_only(wt_repo: tuple[Path, Path], tmp_path: Path) -> None:
    repo, _bare = wt_repo
    merged = tmp_path / "wt-merged"
    unmerged = tmp_path / "wt-unmerged"
    _wt_git(repo, "worktree", "add", "-b", "feat/merged", str(merged), "main")
    _advance_main(repo)  # feat/merged head is now a strict ancestor of main
    _wt_git(repo, "worktree", "add", "-b", "feat/unmerged", str(unmerged), "main")
    (unmerged / "x.txt").write_text("x\n")
    _wt_git(unmerged, "add", "x.txt")
    _wt_git(unmerged, "commit", "-m", "unmerged work")

    report = ST.reclaim(repo, main_ref="main")

    live = _live_worktree_paths(repo)
    assert _rp(merged) not in live, "merged worktree should have been removed"
    assert _rp(unmerged) in live, "unmerged worktree must be left untouched"

    removed_paths = {_rp(Path(e.path)) for e in report.removed}
    assert _rp(merged) in removed_paths
    unmerged_entry = next(e for e in report.entries if _rp(Path(e.path)) == _rp(unmerged))
    assert unmerged_entry.action == ST.ACTION_SKIP_UNMERGED


def test_reclaim_certificate_gate_removes_nothing(
    wt_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    repo, _bare = wt_repo
    merged = tmp_path / "wt-merged"
    _wt_git(repo, "worktree", "add", "-b", "feat/merged", str(merged), "main")
    _advance_main(repo)

    report = ST.reclaim(repo, main_ref="main", authorize=lambda _op: "GATE")

    assert report.removed == []
    assert _rp(merged) in _live_worktree_paths(repo)
    gated = [e for e in report.entries if e.action == ST.ACTION_SKIP_GATED]
    assert gated and _rp(Path(gated[0].path)) == _rp(merged)


def test_reclaim_dirty_merged_worktree_skipped(wt_repo: tuple[Path, Path], tmp_path: Path) -> None:
    repo, _bare = wt_repo
    merged = tmp_path / "wt-merged"
    _wt_git(repo, "worktree", "add", "-b", "feat/merged", str(merged), "main")
    _advance_main(repo)
    (merged / "dirty.txt").write_text("uncommitted\n")  # untracked → dirty

    report = ST.reclaim(repo, main_ref="main")

    assert report.removed == []
    entry = next(e for e in report.entries if _rp(Path(e.path)) == _rp(merged))
    assert entry.action == ST.ACTION_SKIP_DIRTY
    assert _rp(merged) in _live_worktree_paths(repo)


def test_reclaim_detached_head_ancestor_treated_as_merged(
    wt_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    repo, _bare = wt_repo
    wt = tmp_path / "wt-detached"
    _wt_git(repo, "worktree", "add", "--detach", str(wt), "main")
    _advance_main(repo)  # the detached commit is now a strict ancestor of main

    report = ST.reclaim(repo, main_ref="main")

    removed_paths = {_rp(Path(e.path)) for e in report.removed}
    assert _rp(wt) in removed_paths
    assert _rp(wt) not in _live_worktree_paths(repo)


def test_reclaim_registered_worktree_deregisters(wt_repo: tuple[Path, Path]) -> None:
    repo, _bare = wt_repo
    outcome_store = _load_scripts_module("outcome_store")
    outcome_worktrees = _load_scripts_module("outcome_worktrees")
    outcome_id, subplot_id = "o1", "s1"
    wt_path = repo / ".saga-worktrees" / outcome_id / subplot_id
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    _wt_git(repo, "worktree", "add", "-b", "saga-outcome-o1-s1", str(wt_path), "main")
    _advance_main(repo)

    store = outcome_store.Store.for_outcome(outcome_id, repo).ensure()
    outcome_worktrees.register(
        store, subplot_id, {"path": str(wt_path), "branch": "saga-outcome-o1-s1", "owner": "t"}
    )

    report = ST.reclaim(repo, main_ref="main")

    assert not wt_path.exists(), "registered worktree should have been reaped"
    assert outcome_worktrees.read_registry(store).get(subplot_id) is None, "entry must deregister"
    assert any("reap_worktree" in e.note for e in report.removed)


def test_reclaim_registered_removal_failure_keeps_entry(wt_repo: tuple[Path, Path]) -> None:
    repo, _bare = wt_repo
    outcome_store = _load_scripts_module("outcome_store")
    outcome_worktrees = _load_scripts_module("outcome_worktrees")
    outcome_id, subplot_id = "o2", "s2"
    wt_path = repo / ".saga-worktrees" / outcome_id / subplot_id
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    _wt_git(repo, "worktree", "add", "-b", "saga-outcome-o2-s2", str(wt_path), "main")
    _advance_main(repo)

    store = outcome_store.Store.for_outcome(outcome_id, repo).ensure()
    outcome_worktrees.register(
        store, subplot_id, {"path": str(wt_path), "branch": "saga-outcome-o2-s2", "owner": "t"}
    )

    report = ST.reclaim(repo, main_ref="main", runner=_FailRemoveRunner())

    assert wt_path.exists(), "a failed removal must leave the worktree on disk"
    assert outcome_worktrees.read_registry(store).get(subplot_id) is not None, "entry kept"
    assert report.failures, "the failed removal must be reported, never silently dropped"


def test_reclaim_refuses_lease_bound_registered_worktree_without_broker(
    wt_repo: tuple[Path, Path],
) -> None:
    repo, _bare = wt_repo
    outcome_worktrees, _spec, store, broker, wt_path = _lease_bound_outcome_worktree(
        repo, outcome_id="leased-ship", subplot_id="s1"
    )
    lease_id = outcome_worktrees.read_registry(store)["s1"]["lease"]["lease_id"]
    _advance_main(repo)

    report = ST.reclaim(repo, main_ref="main", authorize=lambda _op: "AUTHORIZED")

    assert wt_path.exists(), "generic teardown must not remove a lease-bound worktree"
    assert "s1" in outcome_worktrees.read_registry(store), "generic teardown must not deregister it"
    assert [lease["lease_id"] for lease in broker.inspect()["leases"]] == [lease_id]
    failure = next(entry for entry in report.entries if _rp(Path(entry.path)) == _rp(wt_path))
    assert failure.action == ST.ACTION_REMOVAL_FAILED
    assert "canonical lease-aware reap" in failure.note
    assert "retained" in failure.note

    assert outcome_worktrees.reap_worktree(
        store,
        "s1",
        outcome_worktrees.git_worktree_ops(repo),
        lease_authority=broker,
    )
    assert outcome_worktrees.read_registry(store) == {}
    assert broker.inspect()["leases"] == [], "the failed generic attempt remains retryable"


def test_reclaim_managed_path_with_missing_registry_fails_closed(
    wt_repo: tuple[Path, Path],
) -> None:
    repo, _bare = wt_repo
    wt_path = _managed_merged_worktree(repo, outcome_id="missing-registry", subplot_id="s1")

    report = ST.reclaim(repo, main_ref="main", authorize=lambda _op: "AUTHORIZED")

    assert wt_path.exists()
    failure = next(entry for entry in report.entries if _rp(Path(entry.path)) == _rp(wt_path))
    assert failure.action == ST.ACTION_REMOVAL_FAILED
    assert "registry entry 's1' is missing" in failure.note


def test_reclaim_managed_path_with_unresolvable_store_fails_closed(
    wt_repo: tuple[Path, Path],
) -> None:
    repo, _bare = wt_repo
    wt_path = _managed_merged_worktree(repo, outcome_id="unresolved-store", subplot_id="s1")

    report = ST.reclaim(
        repo,
        main_ref="main",
        authorize=lambda _op: "AUTHORIZED",
        runner=_FailCommonDirRunner(),
    )

    assert wt_path.exists()
    failure = next(entry for entry in report.entries if _rp(Path(entry.path)) == _rp(wt_path))
    assert failure.action == ST.ACTION_REMOVAL_FAILED
    assert "cannot resolve store" in failure.note


def test_reclaim_managed_path_with_malformed_registry_fails_without_repair(
    wt_repo: tuple[Path, Path],
) -> None:
    repo, _bare = wt_repo
    wt_path = _managed_merged_worktree(repo, outcome_id="malformed-registry", subplot_id="s1")
    outcome_store = _load_scripts_module("outcome_store")
    outcome_worktrees = _load_scripts_module("outcome_worktrees")
    store = outcome_store.Store.for_outcome("malformed-registry", repo).ensure()
    registry_path = outcome_worktrees._registry_path(store)
    registry_path.write_text("{broken\n", encoding="utf-8")
    before = registry_path.read_bytes()

    report = ST.reclaim(repo, main_ref="main", authorize=lambda _op: "AUTHORIZED")

    assert wt_path.exists()
    assert registry_path.read_bytes() == before, "strict teardown read must not quarantine/repair"
    assert list(store.quarantine_dir.iterdir()) == []
    failure = next(entry for entry in report.entries if _rp(Path(entry.path)) == _rp(wt_path))
    assert failure.action == ST.ACTION_REMOVAL_FAILED
    assert "unreadable or corrupt" in failure.note


def test_reclaim_managed_path_with_unreadable_registry_fails_closed(
    wt_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _bare = wt_repo
    outcome_id = "unreadable-registry"
    wt_path = _managed_merged_worktree(repo, outcome_id=outcome_id, subplot_id="s1")
    outcome_store = _load_scripts_module("outcome_store")
    outcome_worktrees = _load_scripts_module("outcome_worktrees")
    store = outcome_store.Store.for_outcome(outcome_id, repo).ensure()
    registry_path = outcome_worktrees._registry_path(store)
    outcome_worktrees.register(
        store,
        "s1",
        {"path": str(wt_path), "branch": "saga-outcome-unreadable-registry-s1"},
    )
    original_read_text = Path.read_text

    def fail_registry_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == registry_path:
            raise PermissionError("simulated unreadable registry")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_registry_read)

    report = ST.reclaim(repo, main_ref="main", authorize=lambda _op: "AUTHORIZED")

    assert wt_path.exists()
    failure = next(entry for entry in report.entries if _rp(Path(entry.path)) == _rp(wt_path))
    assert failure.action == ST.ACTION_REMOVAL_FAILED
    assert "simulated unreadable registry" in failure.note


def test_prune_refuses_lease_bound_worktree_without_broker(wt_repo: tuple[Path, Path]) -> None:
    repo, _bare = wt_repo
    outcome_worktrees, spec, store, broker, wt_path = _lease_bound_outcome_worktree(
        repo, outcome_id="leased-prune", subplot_id="s1"
    )
    outcome_decompose = _load_scripts_module("outcome_decompose")
    registry_path = outcome_worktrees._registry_path(store)
    before_spec = spec.to_dict()
    before_registry = registry_path.read_bytes()
    before_authority = broker.inspect()
    closed: list[str] = []

    with pytest.raises(outcome_decompose.DecomposeError, match="requires both worktree_ops"):
        outcome_decompose.prune(
            spec,
            store,
            "s1",
            issue_close=_issue_closer(closed),
            lease_authority=broker,
        )

    assert spec.to_dict() == before_spec, (
        "missing worktree_ops must not mutate revision/nodes/edges"
    )
    assert closed == [], "failed preflight must not close the generated issue"
    assert wt_path.exists()
    assert registry_path.read_bytes() == before_registry
    assert broker.inspect() == before_authority


def test_prune_wrong_authority_is_atomic(wt_repo: tuple[Path, Path]) -> None:
    repo, _bare = wt_repo
    outcome_worktrees, spec, store, broker, wt_path = _lease_bound_outcome_worktree(
        repo, outcome_id="wrong-authority", subplot_id="s1"
    )
    outcome_decompose = _load_scripts_module("outcome_decompose")
    wrong_broker = outcome_worktrees.fleet_leases.authority.LeaseBroker(repo / ".wrong-fleet")
    registry_path = outcome_worktrees._registry_path(store)
    before_spec = spec.to_dict()
    before_registry = registry_path.read_bytes()
    before_authority = broker.inspect()
    closed: list[str] = []

    with pytest.raises(outcome_decompose.DecomposeError, match="prevalidation failed"):
        outcome_decompose.prune(
            spec,
            store,
            "s1",
            issue_close=_issue_closer(closed),
            worktree_ops=outcome_worktrees.git_worktree_ops(repo),
            lease_authority=wrong_broker,
        )

    assert spec.to_dict() == before_spec
    assert closed == []
    assert wt_path.exists()
    assert registry_path.read_bytes() == before_registry
    assert broker.inspect() == before_authority
    assert wrong_broker.inspect()["leases"] == []


def test_prune_invalid_fencing_token_is_atomic(wt_repo: tuple[Path, Path]) -> None:
    repo, _bare = wt_repo
    outcome_worktrees, spec, store, broker, wt_path = _lease_bound_outcome_worktree(
        repo, outcome_id="invalid-token", subplot_id="s1"
    )
    outcome_decompose = _load_scripts_module("outcome_decompose")
    entry = outcome_worktrees.read_registry(store)["s1"]
    entry["lease"]["token"]["fencing_sequence"] += 1
    outcome_worktrees.register(store, "s1", entry)
    registry_path = outcome_worktrees._registry_path(store)
    before_spec = spec.to_dict()
    before_registry = registry_path.read_bytes()
    before_authority = broker.inspect()
    closed: list[str] = []

    with pytest.raises(outcome_decompose.DecomposeError, match="prevalidation failed"):
        outcome_decompose.prune(
            spec,
            store,
            "s1",
            issue_close=_issue_closer(closed),
            worktree_ops=outcome_worktrees.git_worktree_ops(repo),
            lease_authority=broker,
        )

    assert spec.to_dict() == before_spec
    assert closed == []
    assert wt_path.exists()
    assert registry_path.read_bytes() == before_registry
    assert broker.inspect() == before_authority


def test_canonical_reap_releases_exact_lease_before_deregister(
    wt_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _bare = wt_repo
    outcome_worktrees, _spec, store, broker, _wt_path = _lease_bound_outcome_worktree(
        repo, outcome_id="leased-canonical", subplot_id="s1"
    )
    lease_id = outcome_worktrees.read_registry(store)["s1"]["lease"]["lease_id"]
    original_deregister = outcome_worktrees.deregister

    def assert_release_before_deregister(target_store: Any, subplot_id: str) -> None:
        assert broker.inspect()["leases"] == [], "exact lease must release before deregistration"
        original_deregister(target_store, subplot_id)

    monkeypatch.setattr(outcome_worktrees, "deregister", assert_release_before_deregister)

    assert (
        outcome_worktrees.reap_worktree(
            store,
            "s1",
            outcome_worktrees.git_worktree_ops(repo),
            lease_authority=broker,
        )
        is True
    )
    assert outcome_worktrees.read_registry(store) == {}
    assert lease_id not in {lease["lease_id"] for lease in broker.inspect()["leases"]}


def test_reclaim_if_idle_fresh_sidecar_noops(tmp_path: Path) -> None:
    # A just-written sidecar means the fleet is NOT idle → the whole call no-ops.
    ST.register(tmp_path, "issue-347", "b1", kind="branch", ref="issue-347", opened_by="start")
    report = ST.reclaim(tmp_path, if_idle="24h")
    assert report.idle_noop is True


def test_cli_reclaim_if_idle_fresh_exits_zero(tmp_path: Path, capsys: Any) -> None:
    ST.register(tmp_path, "issue-347", "b1", kind="branch", ref="issue-347", opened_by="start")
    exit_code = ST.main(["--repo-root", str(tmp_path), "reclaim", "--if-idle", "24h"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "not idle" in captured.out


def test_reclaim_bad_idle_duration_raises(tmp_path: Path) -> None:
    with pytest.raises(ST.ShipTeardownError, match="invalid --if-idle duration"):
        ST.reclaim(tmp_path, if_idle="soon")


def _utime_tree(path: Path, when: float) -> None:
    os.utime(path, (when, when))
    gitfile = path / ".git"
    if gitfile.exists():
        os.utime(gitfile, (when, when))


def test_reclaim_if_idle_aged_removes_cold_skips_recent(
    wt_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    repo, _bare = wt_repo
    now_ts = time.time()
    aged = now_ts - 200_000  # well past a 24h bound

    # Aged global activity so the global idle gate passes (fleet is idle overall).
    ST.register(repo, "issue-347", "b1", kind="branch", ref="issue-347", opened_by="start")
    os.utime(ST.manifest_path(repo, "issue-347"), (aged, aged))

    cold = tmp_path / "wt-cold"
    hot = tmp_path / "wt-hot"
    _wt_git(repo, "worktree", "add", "-b", "feat/cold", str(cold), "main")
    _wt_git(repo, "worktree", "add", "-b", "feat/hot", str(hot), "main")
    _advance_main(repo)  # both branch heads are now strict ancestors of main

    _utime_tree(cold, aged)  # cold: no recent activity → reclaimable in idle mode
    # hot: just created (fresh mtime) → the sibling-session guard must skip it

    report = ST.reclaim(repo, main_ref="main", if_idle="24h", now=now_ts)

    assert report.idle_noop is False
    removed = {_rp(Path(e.path)) for e in report.removed}
    assert _rp(cold) in removed, "a merged, clean, cold worktree is reclaimed in idle mode"
    recent = [e for e in report.entries if e.action == ST.ACTION_SKIP_RECENT]
    assert recent and _rp(Path(recent[0].path)) == _rp(hot), (
        "a merged+clean worktree with recent activity is skipped (sibling-session guard, KTD8)"
    )
    assert _rp(hot) in _live_worktree_paths(repo)


def test_reclaim_reports_prunable_worktree_without_crash(
    wt_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    """Code-review P1: a prunable worktree (working dir deleted out-of-band — the exact
    stale-agent-worktree state reclaim targets) must be reported, never crash the
    SessionStart hook, and must not stop the sweep from reclaiming healthy candidates."""
    repo, _bare = wt_repo
    prunable = tmp_path / "wt-prunable"
    healthy = tmp_path / "wt-healthy"
    _wt_git(repo, "worktree", "add", "-b", "feat/prunable", str(prunable), "main")
    _wt_git(repo, "worktree", "add", "-b", "feat/healthy", str(healthy), "main")
    _advance_main(repo)  # both heads become strict ancestors of main
    shutil.rmtree(prunable)  # out-of-band delete: git still lists it as prunable

    report = ST.reclaim(repo, main_ref="main")  # must not raise (FileNotFoundError before fix)

    pruned = [e for e in report.entries if e.action == ST.ACTION_SKIP_PRUNABLE]
    assert pruned and _rp(Path(pruned[0].path)) == _rp(prunable)
    assert "prune" in pruned[0].note
    removed = {_rp(Path(e.path)) for e in report.removed}
    assert _rp(healthy) in removed, "sweep must continue past the prunable entry"
    assert _rp(prunable) not in removed


def test_worktree_is_dirty_degrades_to_dirty_on_oserror() -> None:
    """TOCTOU backstop for the same P1: a probe whose cwd vanishes between the isdir
    guard and the status call degrades to dirty (skip), never an escaped OSError."""

    def exploding_runner(cmd, *, cwd, capture_output, text, timeout):  # noqa: ANN001, ANN202
        raise FileNotFoundError(f"[Errno 2] No such file or directory: {cwd!r}")

    assert ST._worktree_is_dirty("/nonexistent/worktree-path", exploding_runner) is True


def test_AC_6_terminal_transition_not_skippable() -> None:
    """AC6 (structural half, co-located so the issue's own -k selector collects here —
    testing-lens finding): teardown is TRANSITIONS[-1], next_transition demands it after
    branch_delete, and every table carries it. The behavioral half (partial-failure path
    still reaching an explicit terminal state) lives in tests/test_ship_ceremony.py with
    its FakeGh rig."""
    sc = _load_scripts_module("ship_ceremony")
    assert sc.TRANSITIONS[-1] == "teardown"
    assert sc.next_transition("branch_delete") == "teardown"
    assert sc.next_transition("teardown") is None
    assert "teardown" in sc._RUNNERS
    assert sc.TRANSITION_TIERS["teardown"] == sc.CeremonyTier.REVERSIBLE


def test_teardown_scratch_ref_outside_sanctioned_roots_refused(
    wt_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    """Security-review F2: the ceremony's scratch close must refuse to rmtree a manifest
    ref outside the sanctioned roots (system tempdir / repo) — the victim dir survives
    and the entry stays open, while a contained scratch ref is removed and closed."""
    repo, _bare = wt_repo
    sc = _load_scripts_module("ship_ceremony")

    sanctioned = tmp_path / "sanctioned-tmp"
    sanctioned.mkdir()
    victim = tmp_path / "victim"  # outside both sanctioned roots (tempdir is patched)
    victim.mkdir()
    (victim / "keep.txt").write_text("precious\n")
    contained = sanctioned / "scratch-ok"
    contained.mkdir()

    real_gettempdir = sc.tempfile.gettempdir
    sc.tempfile.gettempdir = lambda: str(sanctioned)
    try:
        assert sc._scratch_ref_contained(str(contained), repo) is True
        assert sc._scratch_ref_contained(str(victim), repo) is False
        assert sc._scratch_ref_contained(str(sanctioned), repo) is False, "a root itself"
        assert sc._scratch_ref_contained(str(repo), repo) is False, "the repo root itself"
        assert sc._scratch_ref_contained(str(repo / "sub"), repo) is True

        ST.register(repo, "issue-347", "scr-out", kind="scratch", ref=str(victim), opened_by="t")
        ST.register(repo, "issue-347", "scr-in", kind="scratch", ref=str(contained), opened_by="t")
        report = ST.reconcile(repo, "issue-347")
        sc._teardown_attempt_closes({"saga_id": "issue-347"}, report, repo_root=repo, runner=None)
    finally:
        sc.tempfile.gettempdir = real_gettempdir

    assert victim.exists() and (victim / "keep.txt").exists(), "uncontained ref must survive"
    assert not contained.exists(), "contained scratch ref is removed"
    manifest = ST.read_manifest(repo, "issue-347")
    assert manifest["scr-out"]["closed_at"] == "", "refused entry stays open (HALT names it)"
    assert manifest["scr-in"]["closed_at"] != ""
