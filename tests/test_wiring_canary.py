"""Tests for the mutation canary (#427, R7).

The canary's own ``caught`` / ``toothless`` classification is proven here against *fixture guards*
built entirely inside ``tmp_path`` — never against the four real registered guards. This is the
point of R7: a fixture guard that is known-effective must be reported ``caught``, and a fixture guard
that is deliberately toothless (always green) must be reported ``toothless`` and drive a non-zero
process exit. That logic has to be correct independent of which real guards happen to be registered.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_CANARY_PATH = REPO_ROOT / "tools" / "wiring_canary.py"


def _load_canary():
    spec = importlib.util.spec_from_file_location("wiring_canary", _CANARY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses.dataclass() looks its defining module up in sys.modules by name; register
    # before exec so wiring_canary.py's frozen Mutation dataclass builds cleanly.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


canary = _load_canary()


# ---------------------------------------------------------------------------
# Fixture-repo builders — a tiny throwaway "repo" with one guard + one target file
# ---------------------------------------------------------------------------


def _make_effective_guard_repo(root: Path) -> None:
    """A guard that actually checks the invariant: marker.txt must contain GOOD."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "marker.txt").write_text("GOOD\n", encoding="utf-8")
    (root / "test_guard_effective.py").write_text(
        "from pathlib import Path\n\n\n"
        "def test_marker_is_good():\n"
        "    text = (Path(__file__).parent / 'marker.txt').read_text()\n"
        "    assert text.strip() == 'GOOD'\n",
        encoding="utf-8",
    )


def _make_toothless_guard_repo(root: Path) -> None:
    """A guard that never checks the invariant: it always passes regardless of marker.txt."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "marker.txt").write_text("GOOD\n", encoding="utf-8")
    (root / "test_guard_toothless.py").write_text(
        "def test_always_passes():\n    assert True\n",
        encoding="utf-8",
    )


_BREAK_MARKER = {
    "kind": "replace_text",
    "file": "marker.txt",
    "find": "GOOD",
    "replace": "BAD",
}


# ---------------------------------------------------------------------------
# R7 / AC9 — caught outcome (effective guard fires on a planted mutation)
# ---------------------------------------------------------------------------


def test_caught_outcome(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_effective_guard_repo(repo)
    entry = {
        "id": "fixture-effective",
        "guard": "test_guard_effective.py",
        "invariant": "marker.txt contains GOOD",
        "mutation": dict(_BREAK_MARKER),
    }
    record = canary.run_entry(entry, repo)
    assert record["result"] == canary.CAUGHT, record


# ---------------------------------------------------------------------------
# R3 / R7 / AC4 / AC9 — toothless outcome (green guard on a broken invariant)
# ---------------------------------------------------------------------------


def test_toothless_outcome(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_toothless_guard_repo(repo)
    entry = {
        "id": "fixture-toothless",
        "guard": "test_guard_toothless.py",
        "invariant": "marker.txt contains GOOD",
        "mutation": dict(_BREAK_MARKER),
    }
    record = canary.run_entry(entry, repo)
    assert record["result"] == canary.TOOTHLESS, record


def test_toothless_guard_drives_nonzero_exit(tmp_path: Path) -> None:
    """A toothless guard makes the whole canary process exit non-zero (R3)."""
    repo = tmp_path / "repo"
    _make_toothless_guard_repo(repo)
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-toothless",
                    "guard": "test_guard_toothless.py",
                    "invariant": "marker.txt contains GOOD",
                    "mutation": dict(_BREAK_MARKER),
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = canary.main(["--registry", str(registry), "--repo-root", str(repo), "--no-log"])
    assert rc == 1


def test_caught_guard_drives_zero_exit(tmp_path: Path) -> None:
    """An effective (caught) guard lets the canary process exit 0."""
    repo = tmp_path / "repo"
    _make_effective_guard_repo(repo)
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-effective",
                    "guard": "test_guard_effective.py",
                    "invariant": "marker.txt contains GOOD",
                    "mutation": dict(_BREAK_MARKER),
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = canary.main(["--registry", str(registry), "--repo-root", str(repo), "--no-log"])
    assert rc == 0


# ---------------------------------------------------------------------------
# error outcome — a stale mutation anchor is reported loudly, never as toothless
# ---------------------------------------------------------------------------


def test_stale_mutation_anchor_reports_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_effective_guard_repo(repo)
    entry = {
        "id": "fixture-stale-anchor",
        "guard": "test_guard_effective.py",
        "invariant": "marker.txt contains GOOD",
        "mutation": {
            "kind": "replace_text",
            "file": "marker.txt",
            "find": "THIS-STRING-IS-NOT-IN-THE-FILE",
            "replace": "x",
        },
    }
    record = canary.run_entry(entry, repo)
    assert record["result"] == canary.ERROR, record


# ---------------------------------------------------------------------------
# R2 / AC5 — no mutation ever leaks to the real working tree
# ---------------------------------------------------------------------------


def test_no_mutation_leaks_to_working_tree() -> None:
    """Running a real registry entry must not change the real working tree's git status (R2).

    We compare ``git status --porcelain`` before and after rather than asserting emptiness, so the
    test is robust to unrelated in-progress edits in the working copy.

    Cross-surface coupling note (#588, S3 F11):
    This test executes the live registry entry ``agent-registration-drift`` from
    ``tools/canary_registry.json`` against the repository. That canary entry targets the saga agent
    file ``plugins/saga/agents/readonly-verifier.md`` and mutates its literal frontmatter anchor
    ``name: readonly-verifier`` (expecting the mutation to be caught without modifying the working tree).
    If ``plugins/saga/agents/readonly-verifier.md`` or its frontmatter anchor ``name: readonly-verifier``
    is renamed or relocated, this test and the canary entry must be updated in lockstep.
    Both ends of this coupling are documented here to make the rename hazard explicit without
    cross-lane writes to lane B's saga agent surface.
    """

    def _status() -> str:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    entries = canary.load_registry(REPO_ROOT / "tools" / "canary_registry.json")
    entry = next(e for e in entries if e["id"] == "agent-registration-drift")

    before = _status()
    record = canary.run_entry(entry, REPO_ROOT)
    after = _status()

    assert record["result"] == canary.CAUGHT, record
    assert before == after, (
        f"canary run changed the working tree:\nbefore:\n{before}\nafter:\n{after}"
    )


# ---------------------------------------------------------------------------
# R1 / AC1 — seed registry loads and names the four Problem-Frame guards
# ---------------------------------------------------------------------------


def test_registry_loads_seed_entries() -> None:
    entries = canary.load_registry(REPO_ROOT / "tools" / "canary_registry.json")
    assert len(entries) >= 4
    ids = {e["id"] for e in entries}
    assert {
        "agent-registration-drift",
        "release-triad",
        "manifest-consumer-matrix",
        "team-execution-pointers",
    } <= ids
    for entry in entries:
        assert entry["invariant"].strip(), entry
        assert entry["mutation"].get("file"), entry


def test_classify_maps_pytest_exit_codes() -> None:
    assert canary.classify(0) == canary.TOOTHLESS
    assert canary.classify(1) == canary.CAUGHT
    assert canary.classify(5) == canary.ERROR
    assert canary.classify(2) == canary.ERROR


# ---------------------------------------------------------------------------
# Baseline control (panel hardening): a guard that is red on the UNMUTATED copy
# must be `error`, never a vacuous `caught` — this is also what catches a
# pytest-less interpreter (its exit 1 happens at baseline, not post-mutation).
# ---------------------------------------------------------------------------


def _make_baseline_red_guard_repo(root: Path) -> None:
    """A guard that fails regardless of the invariant (environmentally red)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "marker.txt").write_text("GOOD\n", encoding="utf-8")
    (root / "test_guard_baseline_red.py").write_text(
        "def test_always_fails():\n    raise AssertionError('red before any mutation')\n",
        encoding="utf-8",
    )


def test_baseline_red_guard_is_error_not_caught(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_baseline_red_guard_repo(repo)
    entry = {
        "id": "fixture-baseline-red",
        "guard": "test_guard_baseline_red.py",
        "invariant": "marker.txt contains GOOD",
        "mutation": dict(_BREAK_MARKER),
    }
    record = canary.run_entry(entry, repo)
    assert record["result"] == canary.ERROR, record
    assert "baseline" in str(record["detail"]), record
    assert record["baseline_exit"] == 1, record


def test_caught_record_carries_green_baseline(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_effective_guard_repo(repo)
    entry = {
        "id": "fixture-effective",
        "guard": "test_guard_effective.py",
        "invariant": "marker.txt contains GOOD",
        "mutation": dict(_BREAK_MARKER),
    }
    record = canary.run_entry(entry, repo)
    assert record["result"] == canary.CAUGHT, record
    assert record["baseline_exit"] == 0, record
