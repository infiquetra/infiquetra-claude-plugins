"""Legacy filename identity must survive the noncryptographic hash designation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/saga/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "_ledger_hash_board_progression", SCRIPTS / "board_progression.py"
)
assert SPEC and SPEC.loader
BP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BP)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("issue-progress-comment:org/repo#1:work", "issue-progress-comment_org_repo_1_work.json"),
        ("x" * 201, "4b18791347c9db92f62f44a2dfe9c51a9cd2b11d.json"),
        ("a key with spaces", "db0872922c7155ff6f4bf982275fff66ad2467c6.json"),
        (
            "set-field-status:org/repo#1:Stage+Status:Implementing+Active",
            "set-field-status_org_repo_1_Stage+Status_Implementing+Active.json",
        ),
    ],
)
def test_exact_legacy_filename_oracles(key: str, expected: str) -> None:
    assert BP._safe_ledger_name(key) == expected


def test_existing_legacy_ledger_suppresses_write_and_new_record_keeps_attribution(
    tmp_path: Path,
) -> None:
    state = "x" * 210
    key = "issue-progress-comment:org/repo#1:" + state
    legacy = tmp_path / "a168722b57d6af11bf5714922200d67a9d0c1349.json"
    old = {"key": key, "repo": "org/repo", "number": 1, "ts": 100}
    legacy.write_text(json.dumps(old))
    before = legacy.read_bytes()
    writes: list[dict] = []

    def writer(**kwargs: object) -> None:
        writes.append(kwargs)

    kwargs = {
        "board_writer": writer,
        "ledger_dir": tmp_path,
        "now": lambda: 123,
        "provenance": {"resolution_root": "fixture/plugin", "resolution_rung": "override"},
    }
    repeated = BP.authorize_and_write("issue-progress-comment", "org/repo", 1, state, **kwargs)
    assert repeated["status"] == "skipped" and repeated["key"] == key
    assert writes == [] and legacy.read_bytes() == before
    legacy.unlink()
    created = BP.authorize_and_write("issue-progress-comment", "org/repo", 1, state, **kwargs)
    assert created["status"] == "written" and created["key"] == key
    assert len(writes) == 1
    record = json.loads(legacy.read_text())
    assert record == {
        "key": key,
        "op_kind": "issue-progress-comment",
        "repo": "org/repo",
        "number": 1,
        "target_state": state,
        "ts": 123,
        "resolution_root": "fixture/plugin",
        "resolution_rung": "override",
    }
    assert (
        BP.authorize_and_write("issue-progress-comment", "org/repo", 1, state, **kwargs)["status"]
        == "skipped"
    )
    assert len(writes) == 1
