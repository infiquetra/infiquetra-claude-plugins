"""Fleet delegation-integrity sweep tests (issue #457, acceptance criterion 2).

The fleet sweep classifies recorded bridge proofs/transcripts against the failure taxonomy and
fails on any finding: silent no-op, unrecorded fallback, untokened orphan write, broken proof
chain. A seeded silent-no-op transcript fails; a genuine `agy --model` transcript passes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

TESTS_ROOT = Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import check_delegation_proof as cdp  # noqa: E402

REAL_MANIFEST = REPO_ROOT / "marketplace" / "bridge_plugins.json"
REAL_PROOFS_DIR = REPO_ROOT / "docs" / "delegation-proofs"


def _manifest() -> dict[str, object]:
    return cdp.load_manifest(REAL_MANIFEST)


def _disc() -> re.Pattern[str]:
    return cdp.discriminator_for(_manifest(), "agy")


def _write_transcript(path: Path, events: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


def _seed_proof_with_transcript(
    proofs_dir: Path, name: str, events: list[dict[str, object]], *, version: str = "0.4.0"
) -> None:
    transcript = _write_transcript(proofs_dir / "agy" / f"{name}.jsonl", events)
    sha = hashlib.sha256(transcript.read_bytes()).hexdigest()
    (proofs_dir / "agy" / f"{name}.json").write_text(
        json.dumps(
            {
                "schema": "delegation-proof.v1",
                "plugin": "agy",
                "version": version,
                "run_id": name,
                "bridge_command": "agy --model 'Gemini 3.1 Pro (High)' -p 'x'",
                "external_tool_calls": ["agy --model 'Gemini 3.1 Pro (High)' -p 'x'"],
                "actor": "agy:x",
                "transcript": f"agy/{name}.jsonl",
                "transcript_sha256": sha,
            }
        ),
        encoding="utf-8",
    )


# ------------------------------------------------------------------- AC2 (primary)


def test_silent_no_op_transcript_fails(tmp_path: Path) -> None:
    """A claimed bridge run whose transcript makes zero external-tool calls fails the sweep."""
    proofs_dir = tmp_path / "proofs"
    # Transcript records a bridge spawn intent but no genuine `agy --model` call and no tool calls.
    _seed_proof_with_transcript(
        proofs_dir,
        "silent-no-op",
        [
            {"type": "text", "text": "delegating to the agy teammate now"},
            {"type": "text", "text": "teammate finished"},
        ],
    )
    rc = cdp.main(
        ["--mode", "fleet-sweep", "--manifest", str(REAL_MANIFEST), "--proofs-dir", str(proofs_dir)]
    )
    assert rc == 1


def test_genuine_bridge_transcript_passes(tmp_path: Path) -> None:
    """A transcript with a real `agy --model` Bash call (the LEARNINGS:293 discriminator) passes."""
    proofs_dir = tmp_path / "proofs"
    _seed_proof_with_transcript(
        proofs_dir,
        "genuine",
        [
            {
                "type": "tool_use",
                "tool_name": "Bash",
                "command": "agy --model 'Gemini 3.1 Pro (High)' -p 'implement parser'",
            },
            {"type": "write", "event": "write", "actor": "agy:Gemini", "paths": ["src/p.py"]},
        ],
    )
    rc = cdp.main(
        ["--mode", "fleet-sweep", "--manifest", str(REAL_MANIFEST), "--proofs-dir", str(proofs_dir)]
    )
    assert rc == 0


# --------------------------------------------------------- taxonomy classification


def test_unrecorded_fallback_detected() -> None:
    """Claude file-edit tools + no bridge command == unrecorded fallback."""
    text = "\n".join(
        json.dumps(e)
        for e in [
            {"type": "tool_use", "tool_name": "Write", "input": {"command": "n/a"}},
            {"type": "tool_use", "tool_name": "Edit"},
        ]
    )
    findings = cdp.classify_transcript(text, _disc(), source="t")
    assert any(f.category == "unrecorded_fallback" for f in findings)


def test_silent_no_op_detected() -> None:
    text = json.dumps({"type": "text", "text": "spawned agy, nothing happened"})
    findings = cdp.classify_transcript(text, _disc(), source="t")
    assert [f.category for f in findings] == ["silent_no_op"]


def test_untokened_orphan_write_detected_even_when_bridge_ran() -> None:
    """A write with no actor is flagged even alongside a genuine bridge command."""
    text = "\n".join(
        json.dumps(e)
        for e in [
            {"type": "tool_use", "tool_name": "Bash", "command": "agy --model 'X' -p 'go'"},
            {"type": "write", "event": "write", "paths": ["src/orphan.py"]},  # no actor
        ]
    )
    findings = cdp.classify_transcript(text, _disc(), source="t")
    assert any(f.category == "untokened_orphan_write" for f in findings)
    assert not any(f.category in {"silent_no_op", "unrecorded_fallback"} for f in findings)


def test_genuine_transcript_no_findings() -> None:
    text = "\n".join(
        json.dumps(e)
        for e in [
            {"type": "tool_use", "tool_name": "Bash", "command": "agy --model 'X' -p 'go'"},
            {"type": "write", "event": "write", "actor": "agy:X", "paths": ["src/p.py"]},
        ]
    )
    assert cdp.classify_transcript(text, _disc(), source="t") == []


# --------------------------------------------------------------- proof-chain checks


def test_broken_proof_chain_hash_mismatch_fails(tmp_path: Path) -> None:
    """A proof whose transcript_sha256 does not match the file is a broken chain."""
    proofs_dir = tmp_path / "proofs"
    transcript = _write_transcript(
        proofs_dir / "agy" / "run.jsonl",
        [{"type": "tool_use", "tool_name": "Bash", "command": "agy --model 'X' -p 'go'"}],
    )
    _ = transcript
    (proofs_dir / "agy" / "run.json").write_text(
        json.dumps(
            {
                "schema": "delegation-proof.v1",
                "plugin": "agy",
                "version": "0.4.0",
                "run_id": "run",
                "bridge_command": "agy --model 'X' -p 'go'",
                "external_tool_calls": ["agy --model 'X' -p 'go'"],
                "actor": "agy:X",
                "transcript": "agy/run.jsonl",
                "transcript_sha256": "0" * 64,  # deliberately wrong
            }
        ),
        encoding="utf-8",
    )
    rc = cdp.main(
        ["--mode", "fleet-sweep", "--manifest", str(REAL_MANIFEST), "--proofs-dir", str(proofs_dir)]
    )
    assert rc == 1


def test_proof_for_unregistered_plugin_fails(tmp_path: Path) -> None:
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "ghost").mkdir(parents=True)
    (proofs_dir / "ghost" / "p.json").write_text(
        json.dumps(
            {
                "schema": "delegation-proof.v1",
                "plugin": "ghost-bridge",
                "version": "1.0.0",
                "run_id": "r",
                "bridge_command": "x --model y",
                "external_tool_calls": ["x"],
                "actor": "a",
            }
        ),
        encoding="utf-8",
    )
    rc = cdp.main(
        ["--mode", "fleet-sweep", "--manifest", str(REAL_MANIFEST), "--proofs-dir", str(proofs_dir)]
    )
    assert rc == 1


def test_standalone_transcript_sweep(tmp_path: Path) -> None:
    """Standalone bridge transcripts (no proof) are swept: silent no-op fails, genuine passes."""
    transcripts = tmp_path / "transcripts"
    _write_transcript(transcripts / "bad.jsonl", [{"type": "text", "text": "spawned agy, no work"}])
    rc = cdp.main(
        [
            "--mode",
            "fleet-sweep",
            "--manifest",
            str(REAL_MANIFEST),
            "--proofs-dir",
            str(tmp_path / "empty"),
            "--transcripts-dir",
            str(transcripts),
        ]
    )
    assert rc == 1


# ------------------------------------------------------------- real shipped artifacts


def test_real_proofs_directory_sweeps_clean() -> None:
    """The example proof shipped in docs/delegation-proofs/ verifies and sweeps clean."""
    proofs = cdp.load_proofs(REAL_PROOFS_DIR)
    assert proofs, "expected at least the shipped example proof"
    findings = cdp.sweep(_manifest(), proofs, base_dir=REAL_PROOFS_DIR)
    assert findings == [], [f.render() for f in findings]
