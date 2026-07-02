"""Unit tests for team-execution typed artifact pointers — Layer 1 (U1) and template wiring (U2).

All git behavior is exercised against real scratch repos built in ``tmp_path`` fixtures; git is
never mocked (KTD1's temp-index guarantee and the holding-ref retention can only be shown against a
real object store).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "team-execution"
SCRIPT = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "artifact_pointer.py"
)
SKILL_MD = PLUGIN_ROOT / "skills" / "team-execution" / "SKILL.md"
CONSENSUS_PROTOCOL = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "consensus-protocol.md"
)
VALIDATOR_SPAWN_QUIRKS = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "validator-spawn-quirks.md"
)
ARTIFACT_POINTERS_DOC = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "artifact-pointers.md"
)
README = PLUGIN_ROOT / "README.md"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load():
    spec = importlib.util.spec_from_file_location("artifact_pointer", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["artifact_pointer"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "initial")
    return path


def test_contract_round_trips_all_kinds() -> None:
    """Construct -> serialize -> parse round-trips every field for diff/file/symbol kinds."""
    ap = _load()
    for kind, locator in (
        ("diff", "refs/team-execution/snapshots/run-1/0"),
        ("file", "src/app.py"),
        ("symbol", "src/app.py#handler"),
    ):
        pointer = ap.ArtifactPointer(
            kind=kind, locator=locator, hash="deadbeef", epoch="3", deref="git diff A B"
        )
        parsed = ap.ArtifactPointer.from_json(pointer.to_json())
        assert parsed == pointer
        assert parsed.kind == kind


def test_from_json_rejects_unknown_kind_and_missing_fields() -> None:
    ap = _load()
    import json

    good = {
        "kind": "diff",
        "locator": "r",
        "hash": "h",
        "epoch": "0",
        "deref": "git diff A B",
    }
    try:
        ap.ArtifactPointer.from_json(json.dumps({**good, "kind": "bogus"}))
        raise AssertionError("expected ValueError for unknown kind")
    except ValueError:
        pass
    incomplete = dict(good)
    del incomplete["hash"]
    try:
        ap.ArtifactPointer.from_json(json.dumps(incomplete))
        raise AssertionError("expected ValueError for missing field")
    except ValueError:
        pass


def test_snapshot_captures_staged_unstaged_untracked(tmp_path: Path) -> None:
    """The tree OID covers staged + unstaged + untracked files (KTD1)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "tracked.txt").write_text("unstaged change\n", encoding="utf-8")  # unstaged
    (repo / "staged.txt").write_text("staged new\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")  # staged
    (repo / "untracked.txt").write_text("untracked new\n", encoding="utf-8")  # untracked

    pointer = ap.snapshot("run-1", "0", repo_root=repo)
    diff = ap.deref(pointer, repo_root=repo)

    assert "unstaged change" in diff
    assert "staged new" in diff
    assert "untracked new" in diff


def test_snapshot_leaves_real_index_and_worktree_untouched(tmp_path: Path) -> None:
    """The real index and working tree are byte-identical before and after snapshot (KTD1)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "tracked.txt").write_text("unstaged change\n", encoding="utf-8")
    (repo / "staged.txt").write_text("staged new\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")
    (repo / "untracked.txt").write_text("untracked new\n", encoding="utf-8")

    status_before = _git(repo, "status", "--porcelain=v1")
    index_tree_before = _git(repo, "write-tree")  # OID of the *real* index

    ap.snapshot("run-1", "0", repo_root=repo)

    assert _git(repo, "status", "--porcelain=v1") == status_before
    assert _git(repo, "write-tree") == index_tree_before
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "unstaged change\n"


def test_holding_ref_survives_gc(tmp_path: Path) -> None:
    """The snapshot tree survives ``git gc --prune=now`` via its holding ref (issue Q1)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("keep me\n", encoding="utf-8")
    pointer = ap.snapshot("run-1", "0", repo_root=repo)

    _git(repo, "gc", "--prune=now")

    assert _git(repo, "cat-file", "-t", pointer.hash) == "tree"
    diff = ap.deref(pointer, repo_root=repo)
    assert "keep me" in diff


def test_byte_drift_raises_hash_mismatch(tmp_path: Path) -> None:
    """Moving the holding ref to a different tree while keeping the pointer -> HASH_MISMATCH."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("original\n", encoding="utf-8")
    pointer = ap.snapshot("run-1", "0", repo_root=repo)

    other_tree = _git(repo, "rev-parse", "HEAD^{tree}")  # a different, valid tree OID
    _git(repo, "update-ref", pointer.locator, other_tree)

    try:
        ap.deref(pointer, repo_root=repo)
        raise AssertionError("expected PointerError")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_HASH_MISMATCH


def test_superseding_epoch_raises_stale(tmp_path: Path) -> None:
    """A newer epoch ref for the same run-id makes an older pointer STALE (freshness)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("epoch 0\n", encoding="utf-8")
    old_pointer = ap.snapshot("run-1", "0", repo_root=repo)

    (repo / "untracked.txt").write_text("epoch 1\n", encoding="utf-8")
    ap.snapshot("run-1", "1", repo_root=repo)  # supersedes epoch 0

    # Integrity still holds for the old pointer (its ref + tree are intact)...
    assert _git(repo, "rev-parse", old_pointer.locator) == old_pointer.hash
    try:
        ap.deref(old_pointer, repo_root=repo)
        raise AssertionError("expected PointerError")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_STALE


def test_deref_resolves_from_linked_worktree(tmp_path: Path) -> None:
    """A pointer snapshotted in the main repo dereferences from a linked worktree (KTD7)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("shared object\n", encoding="utf-8")
    pointer = ap.snapshot("run-1", "0", repo_root=repo)

    worktree = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(worktree), "HEAD")

    diff = ap.deref(pointer, repo_root=worktree)
    assert "shared object" in diff


def test_cli_deref_prints_typed_code_to_stderr(tmp_path: Path) -> None:
    """The CLI exits non-zero and prints the typed code to stderr on a stale pointer."""
    repo = _init_repo(tmp_path / "repo")

    (repo / "untracked.txt").write_text("epoch 0\n", encoding="utf-8")
    snap0 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "snapshot",
            "--run",
            "r",
            "--epoch",
            "0",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    pointer_json = snap0.stdout.strip()
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "snapshot",
            "--run",
            "r",
            "--epoch",
            "1",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo), "deref", pointer_json],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "POINTER_STALE" in result.stderr


# --- U2: spawn templates pass pointers, receivers dereference ------------------------------


def test_b3a_spawn_template_carries_pointer_block_not_mandatory_inline_diff() -> None:
    """The B3a initial-pass template offers an `artifact-pointer` block above threshold and no
    longer mandates an inlined full-diff body (R3/R7)."""
    doc = _read_text(CONSENSUS_PROTOCOL)
    assert "```artifact-pointer" in doc
    assert '"kind":"diff"' in doc
    # The old unconditional instruction ("git diff or summary of files changed") is replaced by a
    # threshold-conditional one.
    assert "[git diff or summary of files changed]" not in doc
    assert "Below the SKILL.md Step B1 threshold" in doc


def test_b3e_reengagement_template_passes_updated_pointer() -> None:
    """The B3e re-engagement (delta) template carries an UPDATED pointer with an incremented
    epoch above threshold, alongside the still-live below-threshold inline path (R7)."""
    doc = _read_text(CONSENSUS_PROTOCOL)
    delta_section = doc[doc.index("Changes Made (Delta Only)") :]
    assert "artifact-pointer" in delta_section
    assert "epoch incremented" in delta_section
    assert "UPDATED" in delta_section


def test_validator_context_package_reuses_layer1_pointer_with_stat_deref() -> None:
    """Above threshold, validators get the same Layer-1 tree pointer with a `git diff --stat`
    deref command — no Layer-2 dependency (U2 self-contained)."""
    doc = _read_text(VALIDATOR_SPAWN_QUIRKS)
    assert "git diff --stat" in doc
    assert "artifact-pointers.md" in doc


def test_artifact_pointers_doc_is_packaged_and_linked() -> None:
    """`artifact-pointers.md` exists, is linked from SKILL.md and README.md (packaging parity
    with the existing VALIDATOR_REFERENCES/WORKER_REFERENCES doc-guard pattern)."""
    assert ARTIFACT_POINTERS_DOC.exists()
    skill_doc = _read_text(SKILL_MD)
    readme = _read_text(README)
    assert "artifact-pointers.md" in skill_doc
    assert "artifact-pointers.md" in readme


def test_artifact_pointers_doc_states_full_dereference_and_ktd7_fallback() -> None:
    """The receiver contract mandates full-artifact dereference (R5/R14 review invariance, no
    per-lens scoping) and states the KTD7 capability-keyed fallback to inlined content verbatim."""
    doc = _read_text(ARTIFACT_POINTERS_DOC)
    assert "always dereference and read the FULL artifact" in doc
    assert "not allowed" in doc  # per-lens scoping is explicitly not allowed in v1
    assert "capability-keyed" in doc
    assert "falls back to inlined content" in doc
    assert "POINTER_HASH_MISMATCH" in doc
    assert "POINTER_STALE" in doc


def test_threshold_rule_stated_once_in_skill_and_referenced_elsewhere() -> None:
    """The 4 KB / >= 2 recipient / <= 1 KB threshold numbers are the authoritative text in
    SKILL.md; other files reference the rule instead of restating the numbers."""
    skill_doc = _read_text(SKILL_MD)
    assert "> 4 KB" in skill_doc
    assert ">= 2 recipients" in skill_doc
    assert "<= 1 KB" in skill_doc

    for path in (CONSENSUS_PROTOCOL, VALIDATOR_SPAWN_QUIRKS, ARTIFACT_POINTERS_DOC):
        doc = _read_text(path)
        assert "> 4 KB" not in doc, f"{path} restates the threshold instead of referencing SKILL.md"
        assert "SKILL.md" in doc or "Step B1" in doc


def test_base_reviewer_agents_reference_artifact_pointers_doc() -> None:
    """Each base reviewer agent gains a short pointer-dereference instruction pointing at the
    receiver contract (U2 scope: minimal edits, no restructuring)."""
    agents_dir = PLUGIN_ROOT / "agents"
    for agent_file in (
        "devils-advocate-reviewer.md",
        "architecture-reviewer.md",
        "security-reviewer.md",
    ):
        doc = _read_text(agents_dir / agent_file)
        assert "artifact-pointers.md" in doc
        assert "artifact-pointer" in doc


# --- U3: Layer-2 content-addressed store ----------------------------------------------------


def _make_ignored_claude_repo(path: Path) -> Path:
    """A scratch repo whose ``.claude/`` is git-ignored (Step B0a's safe path)."""
    repo = _init_repo(path)
    (repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore .claude")
    return repo


def test_store_write_once_dedups_identical_bytes(tmp_path: Path) -> None:
    """Storing the same bytes twice (even under a different run/epoch) reuses one CAS path."""
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    artifact = tmp_path / "a.txt"
    artifact.write_text("same content\n", encoding="utf-8")

    p1 = ap.store("run-1", "0", artifact, repo_root=repo)
    p2 = ap.store("run-2", "5", artifact, repo_root=repo)

    assert p1.hash == p2.hash
    assert p1.locator == p2.locator
    store_root = ap.resolve_store_root(repo)
    cas_files = list((store_root / "objects").rglob("*"))
    cas_files = [f for f in cas_files if f.is_file()]
    assert len(cas_files) == 1


def test_store_different_bytes_get_different_paths(tmp_path: Path) -> None:
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    a = tmp_path / "a.txt"
    a.write_text("content A\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("content B\n", encoding="utf-8")

    p1 = ap.store("run-1", "0", a, repo_root=repo)
    p2 = ap.store("run-1", "1", b, repo_root=repo)

    assert p1.hash != p2.hash
    assert p1.locator != p2.locator


def test_store_deref_round_trips_content(tmp_path: Path) -> None:
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    artifact = tmp_path / "a.txt"
    artifact.write_text("stored content\n", encoding="utf-8")
    pointer = ap.store("run-1", "0", artifact, repo_root=repo)

    assert ap.deref(pointer, repo_root=repo) == "stored content\n"


def test_store_falls_back_to_home_when_claude_dir_not_ignored(tmp_path: Path, monkeypatch) -> None:
    """When ``.claude`` is NOT git-ignored, the store falls back to the home-dir namespace
    (Step B0a safety) rather than writing under the repo's ``.claude/``."""
    repo = _init_repo(tmp_path / "repo")  # no .gitignore for .claude/
    ap = _load()

    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(ap.Path, "home", classmethod(lambda cls: fake_home))

    store_root = ap.resolve_store_root(repo)
    assert str(fake_home) in str(store_root)
    assert not (repo / ".claude" / "team-execution" / "artifacts").exists()


def test_tampered_stored_file_raises_hash_mismatch(tmp_path: Path) -> None:
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    artifact = tmp_path / "a.txt"
    artifact.write_text("original\n", encoding="utf-8")
    pointer = ap.store("run-1", "0", artifact, repo_root=repo)

    store_root = ap.resolve_store_root(repo)
    cas_path = store_root / pointer.locator
    cas_path.write_text("tampered\n", encoding="utf-8")

    try:
        ap.deref(pointer, repo_root=repo)
        raise AssertionError("expected PointerError")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_HASH_MISMATCH


def test_l2_deref_rejects_path_traversal_locator(tmp_path: Path) -> None:
    """A pointer is untrusted (it travels inside spawn prompts). A hostile ``locator`` that names a
    file outside the store — absolute or ``..``-escaping — must be rejected, never followed, even
    when the pointer carries that file's real sha256. Otherwise deref is an arbitrary-file read and
    the mismatch error a hash-disclosure oracle."""
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET\n", encoding="utf-8")
    secret_digest = hashlib.sha256(secret.read_bytes()).hexdigest()

    hostile_locators = [
        str(secret),  # absolute path — pathlib join lets the RHS win outright
        f"../../../../{secret.name}",  # dotdot escape
    ]
    for locator in hostile_locators:
        pointer = ap.ArtifactPointer(
            kind="file", locator=locator, hash=secret_digest, epoch="0", deref="cat"
        )
        try:
            ap.deref(pointer, repo_root=repo)
            raise AssertionError(f"expected PointerError for hostile locator {locator!r}")
        except ap.PointerError as exc:
            assert exc.code == ap.ERR_HASH_MISMATCH
            assert "TOP SECRET" not in exc.detail  # no content or path leaked back


def test_l2_deref_rejects_non_hex_hash(tmp_path: Path) -> None:
    """A non-sha256 ``hash`` cannot address the CAS — it is rejected before any path is built."""
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    pointer = ap.ArtifactPointer(
        kind="file", locator="objects/xx/not-a-digest", hash="not-a-digest", epoch="0", deref="cat"
    )
    try:
        ap.deref(pointer, repo_root=repo)
        raise AssertionError("expected PointerError for non-hex hash")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_HASH_MISMATCH


def test_superseded_l2_epoch_raises_stale(tmp_path: Path) -> None:
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    a0 = tmp_path / "a0.txt"
    a0.write_text("epoch 0 content\n", encoding="utf-8")
    old_pointer = ap.store("run-1", "0", a0, repo_root=repo)

    a1 = tmp_path / "a1.txt"
    a1.write_text("epoch 1 content\n", encoding="utf-8")
    ap.store("run-1", "1", a1, repo_root=repo)  # supersedes epoch 0

    try:
        ap.deref(old_pointer, repo_root=repo)
        raise AssertionError("expected PointerError")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_STALE


def test_gc_reclaims_stale_cas_entries_and_snapshot_refs_younger_survive(tmp_path: Path) -> None:
    """``gc`` removes CAS entries and snapshot refs older than the TTL; younger entries survive."""
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    ap = _load()

    old_artifact = tmp_path / "old.txt"
    old_artifact.write_text("old artifact\n", encoding="utf-8")
    old_pointer = ap.store("run-old", "0", old_artifact, repo_root=repo)

    ap.snapshot("run-old", "0", repo_root=repo)

    new_artifact = tmp_path / "new.txt"
    new_artifact.write_text("new artifact\n", encoding="utf-8")
    new_pointer = ap.store("run-new", "0", new_artifact, repo_root=repo)
    new_snapshot = ap.snapshot("run-new", "0", repo_root=repo)

    store_root = ap.resolve_store_root(repo)
    old_cas_path = store_root / old_pointer.locator
    old_ref_path = repo / ".git" / "refs" / "team-execution" / "snapshots" / "run-old" / "0"
    stale_ts = time.time() - (10 * 86400)
    os.utime(old_cas_path, (stale_ts, stale_ts))
    os.utime(old_ref_path, (stale_ts, stale_ts))

    result = ap.gc(repo_root=repo, max_age_days=7)

    assert result["artifacts_removed"] == 1
    assert result["snapshot_refs_removed"] == 1
    assert not old_cas_path.exists()
    assert not old_ref_path.exists()

    # Younger entries survive and remain fully usable.
    new_store_root = ap.resolve_store_root(repo)
    assert (new_store_root / new_pointer.locator).exists()
    assert ap.deref(new_pointer, repo_root=repo) == "new artifact\n"
    assert _git(repo, "rev-parse", "--verify", new_snapshot.locator) == new_snapshot.hash

    # The stale run's freshness-index entry is pruned too.
    index = ap._read_index(store_root)
    assert "run-old" not in index


def test_cli_store_and_gc_round_trip(tmp_path: Path) -> None:
    """The ``store`` and ``gc`` CLI subcommands work end-to-end (no direct module import)."""
    repo = _make_ignored_claude_repo(tmp_path / "repo")
    artifact = tmp_path / "cli.txt"
    artifact.write_text("cli content\n", encoding="utf-8")

    store_result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "store",
            "--run",
            "cli-run",
            "--epoch",
            "0",
            str(artifact),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    pointer_json = store_result.stdout.strip()
    assert '"kind":"file"' in pointer_json

    deref_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo), "deref", pointer_json],
        capture_output=True,
        text=True,
        check=True,
    )
    assert deref_result.stdout == "cli content\n"

    gc_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo), "gc", "--max-age-days", "7"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(gc_result.stdout)
    assert payload["artifacts_removed"] == 0  # too fresh to reclaim
    assert payload["snapshot_refs_removed"] == 0
