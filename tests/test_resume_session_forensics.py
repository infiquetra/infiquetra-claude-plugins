"""Tests for the /resume Tier-2 forensic session-mining scripts.

Two NEW Claude-only scripts back the ``/resume`` heavy-forensic FALLBACK path
(no saga AND no resolvable issue): ``discover_sessions.py`` (recency-ranked
session discovery) and ``extract_session_skeleton.py`` (file-mediated skeleton
extraction, a slim port of CE ``ce-sessions``).

Both are exercised through their real CLI surface via ``subprocess`` — the
process boundary is the point: ``extract_session_skeleton.py``'s ``--output``
capture-redirect must hold across a genuine stdout, which an in-process import
would not prove.

* ``test_discover_sessions_recency_cap_exclude_current`` pins discovery's
  window filter, exclude-current drop, cap-5, and newest-first ordering.
* ``test_extract_skeleton_output_is_file_mediated`` pins the context-safety
  crux: with ``--output`` the skeleton body lands in the file and stdout carries
  ONLY a one-line ``_meta`` status — the raw content never round-trips stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "plugins" / "infiquetra-lifecycle" / "scripts"
DISCOVER = SCRIPTS_DIR / "discover_sessions.py"
EXTRACT = SCRIPTS_DIR / "extract_session_skeleton.py"


def _set_mtime(path: Path, days_ago: float) -> None:
    """Backdate ``path``'s mtime by ``days_ago`` days."""
    import time

    when = time.time() - days_ago * 86400
    os.utime(path, (when, when))


def test_discover_sessions_recency_cap_exclude_current(tmp_path: Path) -> None:
    repo = "my-repo"
    projects_root = tmp_path / "projects"
    project_dir = projects_root / f"-Users-jeff-workspace-{repo}"
    project_dir.mkdir(parents=True)

    # 7 in-window sessions, staggered so ordering is unambiguous (newest = idx 0).
    in_window: list[str] = []
    for idx in range(7):
        session_id = f"in-{idx:02d}"
        f = project_dir / f"{session_id}.jsonl"
        f.write_text('{"type": "user"}\n', encoding="utf-8")
        # idx 0 = freshest (0.1d old), idx 6 = oldest in-window (~6.1d).
        _set_mtime(f, days_ago=0.1 + idx)
        in_window.append(session_id)

    # 2 out-of-window sessions (well past the 7-day cutoff).
    for idx in range(2):
        f = project_dir / f"old-{idx:02d}.jsonl"
        f.write_text('{"type": "user"}\n', encoding="utf-8")
        _set_mtime(f, days_ago=30 + idx)

    # The "current" session to exclude — make it the freshest so we prove the
    # drop happens BEFORE the cap (otherwise it would survive on recency).
    current = project_dir / "current-session.jsonl"
    current.write_text('{"type": "user"}\n', encoding="utf-8")
    _set_mtime(current, days_ago=0.01)

    result = subprocess.run(
        [
            sys.executable,
            str(DISCOVER),
            "--repo",
            repo,
            "--days",
            "7",
            "--projects-root",
            str(projects_root),
            "--exclude",
            "current-session",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    candidates = payload["candidates"]
    returned_ids = [c["session_id"] for c in candidates]

    # Cap at 5.
    assert payload["count"] == 5
    assert len(candidates) == 5

    # Out-of-window dropped.
    assert not any(sid.startswith("old-") for sid in returned_ids)

    # Excluded current session dropped (even though it was the freshest).
    assert "current-session" not in returned_ids

    # Only in-window ids returned.
    assert all(sid in in_window for sid in returned_ids)

    # Newest-first: the 5 freshest in-window are in-00..in-04 in that order.
    assert returned_ids == ["in-00", "in-01", "in-02", "in-03", "in-04"]

    # Metadata only — never a file body.
    for cand in candidates:
        assert set(cand.keys()) == {"path", "session_id", "mtime"}
        assert cand["path"].endswith(".jsonl")


def test_extract_skeleton_output_is_file_mediated(tmp_path: Path) -> None:
    # A small Claude JSONL session: user msg + assistant text + a tool_use,
    # then a tool_result. Text bodies are long enough to clear the length gates.
    user_text = "Please investigate the failing resume reconstruction path here."
    assistant_text = "I will read the saga engine and trace the latest-tick restore behavior."
    lines = [
        {
            "type": "user",
            "timestamp": "2026-06-02T14:00:00.000Z",
            "message": {"content": user_text},
        },
        {
            "type": "assistant",
            "timestamp": "2026-06-02T14:00:05.000Z",
            "message": {
                "content": [
                    {"type": "text", "text": assistant_text},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Read",
                        "input": {"file_path": "scripts/saga.py"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "timestamp": "2026-06-02T14:00:06.000Z",
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "is_error": False}]
            },
        },
    ]
    session_jsonl = "\n".join(json.dumps(obj) for obj in lines) + "\n"

    out_file = tmp_path / "session.skeleton.txt"
    result = subprocess.run(
        [sys.executable, str(EXTRACT), "--output", str(out_file)],
        input=session_jsonl,
        capture_output=True,
        text=True,
        check=True,
    )

    # The skeleton body was written to the output FILE (non-empty, real content).
    assert out_file.exists()
    body = out_file.read_text(encoding="utf-8")
    assert body.strip() != ""
    assert user_text in body
    assert assistant_text in body
    assert "[tool] Read scripts/saga.py" in body

    # Stdout is EXACTLY one JSON line — the _meta status — and NOT the body.
    stdout_lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(stdout_lines) == 1
    meta = json.loads(stdout_lines[0])
    assert meta["_meta"] is True
    assert meta["wrote"] == str(out_file)
    assert meta["bytes"] == out_file.stat().st_size
    assert meta["bytes"] > 0

    # The raw content did NOT round-trip through stdout.
    assert user_text not in result.stdout
    assert assistant_text not in result.stdout
