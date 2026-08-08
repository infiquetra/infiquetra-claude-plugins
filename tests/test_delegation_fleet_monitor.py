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

import pytest

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


def test_standalone_transcript_swept_by_default_from_proofs_dir(tmp_path: Path) -> None:
    """FIX-C: a bare silent-no-op .jsonl under the proofs dir is swept even when the invocation
    omits --transcripts-dir (the standalone leg must not depend on CI-invocation discipline)."""
    proofs_dir = tmp_path / "proofs"
    _write_transcript(
        proofs_dir / "agy" / "orphaned.jsonl", [{"type": "text", "text": "spawned agy, no work"}]
    )
    rc = cdp.main(
        ["--mode", "fleet-sweep", "--manifest", str(REAL_MANIFEST), "--proofs-dir", str(proofs_dir)]
    )
    assert rc == 1


# ------------------------------------------------------- fail-closed proof chain (#457 fix)


def test_dangling_transcript_proof_fails_sweep(tmp_path: Path) -> None:
    """Refute-panel red fixture: a proof attesting a NONEXISTENT transcript with a bogus
    transcript_sha256 is a broken proof chain, not a clean verify."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    (proofs_dir / "agy" / "phantom.json").write_text(
        json.dumps(
            {
                "schema": "delegation-proof.v1",
                "plugin": "agy",
                "version": "0.4.0",
                "run_id": "phantom",
                "bridge_command": "agy --model 'X' -p 'go'",
                "external_tool_calls": ["agy --model 'X' -p 'go'"],
                "actor": "agy:X",
                "transcript": "agy/phantom.jsonl",  # does not exist
                "transcript_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    proofs = cdp.load_proofs(proofs_dir)
    findings = cdp.sweep(_manifest(), proofs, base_dir=proofs_dir)
    assert any(f.category == "broken_proof_chain" for f in findings)
    rc = cdp.main(
        ["--mode", "fleet-sweep", "--manifest", str(REAL_MANIFEST), "--proofs-dir", str(proofs_dir)]
    )
    assert rc == 1


def test_transcriptless_proof_is_unverifiable_finding(tmp_path: Path) -> None:
    """A proof with NO transcript at all emits the distinct unverifiable_proof finding: the
    artifact is entirely self-attested, and the sweep makes that visible (and red)."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    (proofs_dir / "agy" / "bare.json").write_text(
        json.dumps(
            {
                "schema": "delegation-proof.v1",
                "plugin": "agy",
                "version": "0.4.0",
                "run_id": "bare",
                "bridge_command": "agy --model 'X' -p 'go'",
                "external_tool_calls": ["agy --model 'X' -p 'go'"],
                "actor": "agy:X",
            }
        ),
        encoding="utf-8",
    )
    proofs = cdp.load_proofs(proofs_dir)
    findings = cdp.sweep(_manifest(), proofs, base_dir=proofs_dir)
    assert [f.category for f in findings] == ["unverifiable_proof"]


def test_hash_without_transcript_reference_fails_sweep(tmp_path: Path) -> None:
    """A recorded transcript_sha256 with no transcript reference is a broken chain."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    (proofs_dir / "agy" / "hash-only.json").write_text(
        json.dumps(
            {
                "schema": "delegation-proof.v1",
                "plugin": "agy",
                "version": "0.4.0",
                "run_id": "hash-only",
                "bridge_command": "agy --model 'X' -p 'go'",
                "external_tool_calls": ["agy --model 'X' -p 'go'"],
                "actor": "agy:X",
                "transcript_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    findings = cdp.sweep(_manifest(), cdp.load_proofs(proofs_dir), base_dir=proofs_dir)
    assert [f.category for f in findings] == ["broken_proof_chain"]


def test_non_object_json_proof_is_a_finding_not_a_silent_skip(tmp_path: Path) -> None:
    """FIX-G: a proof file whose JSON parses to a non-object (list/string/number) is a
    broken_proof_chain finding, never silently ignored."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    (proofs_dir / "agy" / "weird.json").write_text("[1, 2, 3]", encoding="utf-8")
    proofs = cdp.load_proofs(proofs_dir)
    assert len(proofs) == 1 and proofs[0].error
    findings = cdp.sweep(_manifest(), proofs, base_dir=proofs_dir)
    assert [f.category for f in findings] == ["broken_proof_chain"]


# ------------------------------------------------- discriminator execution shape (FIX-D)


def test_reading_the_bridge_script_is_not_a_bridge_run() -> None:
    """Refute-panel red fixture: a transcript whose only path-matching event merely READS the
    bridge script (cat/grep) plus Claude edits classifies as unrecorded_fallback, not genuine."""
    text = "\n".join(
        json.dumps(e)
        for e in [
            {
                "type": "tool_use",
                "tool_name": "Bash",
                "command": "cat plugins/agy/scripts/agy_delegate.py",
            },
            {"type": "tool_use", "tool_name": "Edit"},
        ]
    )
    findings = cdp.classify_transcript(text, _disc(), source="t")
    assert any(f.category == "unrecorded_fallback" for f in findings)


def test_executing_the_bridge_script_is_a_bridge_run() -> None:
    """The execution shape (python/uv run invoking the wrapper) still counts as genuine."""
    text = json.dumps(
        {
            "type": "tool_use",
            "tool_name": "Bash",
            "command": "python3 plugins/agy/scripts/agy_delegate.py submit envelope.json",
        }
    )
    assert cdp.classify_transcript(text, _disc(), source="t") == []


# ------------------------------------------------------- multi-bridge accumulation (FIX-E)


def _two_bridge_manifest() -> dict[str, object]:
    return {
        "schema": "bridge-plugins.v1",
        "bridges": {
            "aaa": {"discriminator": r"alpha-bridge\s+--model"},
            "zzz": {"discriminator": r"zulu-bridge\s+--model"},
        },
    }


def test_standalone_transcript_matching_first_bridge_is_genuine(tmp_path: Path) -> None:
    """A standalone transcript matched by the FIRST bridge (iteration-order probe) is genuine."""
    t = _write_transcript(
        tmp_path / "t.jsonl",
        [{"type": "tool_use", "tool_name": "Bash", "command": "alpha-bridge --model X -p go"}],
    )
    findings = cdp.sweep(_two_bridge_manifest(), [], base_dir=tmp_path, standalone_transcripts=[t])
    assert findings == [], [f.render() for f in findings]


def test_standalone_transcript_matching_last_bridge_is_genuine(tmp_path: Path) -> None:
    """Same probe from the other side: matched by the LAST bridge only."""
    t = _write_transcript(
        tmp_path / "t.jsonl",
        [{"type": "tool_use", "tool_name": "Bash", "command": "zulu-bridge --model X -p go"}],
    )
    findings = cdp.sweep(_two_bridge_manifest(), [], base_dir=tmp_path, standalone_transcripts=[t])
    assert findings == [], [f.render() for f in findings]


def test_standalone_transcript_matching_no_bridge_reports_once(tmp_path: Path) -> None:
    """A transcript unmatched by ALL bridges is the orphan case: exactly one no-op finding and
    one orphan-write finding — no per-bridge duplicates, no iteration-order dependence."""
    t = _write_transcript(
        tmp_path / "t.jsonl",
        [
            {"type": "text", "text": "nothing external happened"},
            {"type": "write", "event": "write", "paths": ["src/orphan.py"]},  # no actor
        ],
    )
    findings = cdp.sweep(_two_bridge_manifest(), [], base_dir=tmp_path, standalone_transcripts=[t])
    assert sorted(f.category for f in findings) == ["silent_no_op", "untokened_orphan_write"]


# ------------------------------------------------------------- real shipped artifacts


def test_real_proofs_directory_excludes_examples_and_sweeps_clean() -> None:
    """Examples stay documentation-only while shipped release proofs remain enforced."""
    proofs = cdp.load_proofs(REAL_PROOFS_DIR)
    # Deliberate allowlist, in `sorted(rglob)` filename order, NOT a count assertion: it names
    # every genuine delegated run whose proof ships in this repo, so an artifact nobody added on
    # purpose fails here. It grows by exactly one entry per real bridge run — adding a line when
    # you land a new proof is expected; a diff that adds one you cannot trace to a run bundle is
    # the thing this catches.
    assert [proof.data["run_id"] for proof in proofs] == [
        "cmux-bypass-0.5.1-20260719",
        "agy-0-6-1-proof",
        "issue-355-genuine-20260717",
        "agy-0-6-0-proof",
    ]
    assert all("examples" not in proof.path.parts for proof in proofs)
    findings = cdp.sweep(_manifest(), proofs, base_dir=REAL_PROOFS_DIR)
    assert findings == [], [f.render() for f in findings]
    rc = cdp.main(
        [
            "--mode",
            "fleet-sweep",
            "--manifest",
            str(REAL_MANIFEST),
            "--proofs-dir",
            str(REAL_PROOFS_DIR),
            "--transcripts-dir",
            str(REAL_PROOFS_DIR),
        ]
    )
    assert rc == 0


# --------------------------------------------- discriminator anchoring (round-3 hardening)


@pytest.mark.parametrize(
    "command",
    [
        "rg 'agy --model' docs/engineering-journal/LEARNINGS.md",
        'grep -c "agy --model" transcript.jsonl',
        "echo 'use agy --model X to delegate'",
        "python3 -c \"print(open('plugins/agy/scripts/agy_delegate.py').read())\"",
        "sed -n '1,50p' plugins/agy/scripts/agy_delegate.py",
        "grep -n 'agy.*--model' plugins/agy/scripts/agy_delegate.py",
    ],
)
def test_non_execution_mentions_are_not_bridge_runs(command: str) -> None:
    """Panel red fixtures: quoted/read-only mentions of the bridge vocabulary must not
    classify as genuine — a fallback teammate grepping the journal for 'agy --model'
    (a string that literally appears there) is the realistic silent-fallback shape."""
    text = "\n".join(
        json.dumps(e)
        for e in [
            {"type": "tool_use", "tool_name": "Bash", "command": command},
            {"type": "tool_use", "tool_name": "Edit"},
        ]
    )
    findings = cdp.classify_transcript(text, _disc(), source="t")
    assert any(f.category == "unrecorded_fallback" for f in findings), command


@pytest.mark.parametrize(
    "command",
    [
        'agy --model "Gemini 3.1 Pro (High)" -p "task"',
        "cd /tmp/x && agy --model flash -p y",
        "FOO=1 agy --model flash -p y",
        "python3 plugins/agy/scripts/agy_delegate.py --task t",
        "python3 /Users/someone/repo/plugins/agy/scripts/agy_delegate.py --task t",
        "uv run python plugins/agy/scripts/agy_delegate.py --task t",
        "uv run --frozen python3 plugins/agy/scripts/agy_delegate.py --task t",
    ],
)
def test_genuine_execution_shapes_still_classify_genuine(command: str) -> None:
    text = "\n".join(
        json.dumps(e)
        for e in [
            {"type": "tool_use", "tool_name": "Bash", "command": command},
            {"type": "tool_use", "tool_name": "Edit"},
        ]
    )
    findings = cdp.classify_transcript(text, _disc(), source="t")
    assert not any(f.category == "unrecorded_fallback" for f in findings), command


def test_symlink_aliased_transcript_stays_on_the_sweep_surface(tmp_path: Path) -> None:
    """A .jsonl visible at the enforcement root cannot be excluded from the standalone sweep
    by symlinking it into examples/ — _in_examples judges the surface path, not the target."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "examples").mkdir(parents=True)
    target = proofs_dir / "examples" / "noop.jsonl"
    target.write_text("", encoding="utf-8")
    (proofs_dir / "agy").mkdir()
    alias = proofs_dir / "agy" / "alias.jsonl"
    alias.symlink_to(target)
    found = cdp.discover_standalone_transcripts(proofs_dir, exclude=set())
    assert alias in found
