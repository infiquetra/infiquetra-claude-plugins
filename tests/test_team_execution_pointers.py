"""Unit tests for team-execution typed artifact pointers — Layer 1 (U1) and template wiring (U2).

All git behavior is exercised against real scratch repos built in ``tmp_path`` fixtures; git is
never mocked (KTD1's temp-index guarantee and the holding-ref retention can only be shown against a
real object store).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
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
