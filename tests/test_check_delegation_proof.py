"""Version-bump delegation-proof gate tests (issue #457, acceptance criterion 1).

The version-gate fires red when a bridge-carrying plugin's ``marketplace.json`` version changes
without a valid delegation-proof artifact, and green when a verifying proof for the new version is
present. Also covers the real shipped manifest/proofs directory, the distinct-modes acceptance
(both modes independently invocable via ``--dry-run``), and the CI-wiring drift guard.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
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
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "delegation-integrity.yml"


# --------------------------------------------------------------------------- helpers


def _marketplace(agy_version: str) -> dict[str, object]:
    return {
        "name": "infiquetra-plugins",
        "plugins": [
            {"name": "saga", "version": "1.0.0"},
            {"name": "agy", "version": agy_version},
        ],
    }


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _valid_proof(version: str, *, transcript_rel: str, transcript_sha: str) -> dict[str, object]:
    return {
        "schema": "delegation-proof.v1",
        "plugin": "agy",
        "version": version,
        "run_id": "run-xyz",
        "bridge_command": "agy --model 'Gemini 3.1 Pro (High)' -p 'do the task'",
        "external_tool_calls": ["agy --model 'Gemini 3.1 Pro (High)' -p 'do the task'"],
        "actor": "agy:Gemini 3.1 Pro (High)",
        "transcript": transcript_rel,
        "transcript_sha256": transcript_sha,
    }


def _seed_valid_proof(proofs_dir: Path, version: str) -> None:
    transcript = proofs_dir / "agy" / f"run-{version}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            "type": "tool_use",
            "tool_name": "Bash",
            "command": "agy --model 'Gemini 3.1 Pro (High)' -p 'do the task'",
        },
        {"type": "write", "event": "write", "actor": "agy:x", "paths": ["src/a.py"]},
    ]
    transcript.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    sha = hashlib.sha256(transcript.read_bytes()).hexdigest()
    _write_json(
        proofs_dir / "agy" / f"proof-{version}.json",
        _valid_proof(version, transcript_rel=f"agy/run-{version}.jsonl", transcript_sha=sha),
    )


def _run_gate(
    tmp_path: Path,
    *,
    base_version: str,
    head_version: str,
    with_proof: bool,
) -> int:
    base = _write_json(tmp_path / "base_marketplace.json", _marketplace(base_version))
    head = _write_json(tmp_path / "head_marketplace.json", _marketplace(head_version))
    proofs_dir = tmp_path / "proofs"
    proofs_dir.mkdir()
    if with_proof:
        _seed_valid_proof(proofs_dir, head_version)
    return cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )


# --------------------------------------------------------------------- AC1 (primary)


def test_version_bump_without_proof_fails(tmp_path: Path) -> None:
    """Fixture 1: agy marketplace version bumped, no proof artifact -> CI red."""
    rc = _run_gate(tmp_path, base_version="0.4.0", head_version="0.4.1", with_proof=False)
    assert rc == 1


def test_version_bump_with_proof_passes(tmp_path: Path) -> None:
    """Fixture 2: identical bump but with a valid proof for the new version -> CI green."""
    rc = _run_gate(tmp_path, base_version="0.4.0", head_version="0.4.1", with_proof=True)
    assert rc == 0


def test_no_version_change_passes_without_proof(tmp_path: Path) -> None:
    """No bridge-plugin version change means the gate has nothing to enforce."""
    rc = _run_gate(tmp_path, base_version="0.4.0", head_version="0.4.0", with_proof=False)
    assert rc == 0


def test_proof_for_wrong_version_does_not_satisfy_gate(tmp_path: Path) -> None:
    """A proof attesting an older version does not back the new bump."""
    base = _write_json(tmp_path / "base.json", _marketplace("0.4.0"))
    head = _write_json(tmp_path / "head.json", _marketplace("0.5.0"))
    proofs_dir = tmp_path / "proofs"
    proofs_dir.mkdir()
    _seed_valid_proof(proofs_dir, "0.4.0")  # proof is for the OLD version
    rc = cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )
    assert rc == 1


def test_invalid_proof_bridge_command_does_not_satisfy_gate(tmp_path: Path) -> None:
    """A proof whose bridge_command fails the discriminator is not a valid proof."""
    base = _write_json(tmp_path / "base.json", _marketplace("0.4.0"))
    head = _write_json(tmp_path / "head.json", _marketplace("0.4.1"))
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    proof = _valid_proof("0.4.1", transcript_rel="", transcript_sha="")
    proof["bridge_command"] = "echo pretending to be a bridge"  # no --model, fails discriminator
    _write_json(proofs_dir / "agy" / "proof.json", proof)
    rc = cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )
    assert rc == 1


def test_dangling_transcript_proof_does_not_satisfy_gate(tmp_path: Path) -> None:
    """Fail closed: a proof attesting a NONEXISTENT transcript never backs a version bump.

    Red fixture from the #457 refute panel: before the fix, a proof naming a phantom transcript
    with a bogus transcript_sha256 verified cleanly because the hash was only compared when the
    file happened to exist.
    """
    base = _write_json(tmp_path / "base.json", _marketplace("0.4.0"))
    head = _write_json(tmp_path / "head.json", _marketplace("0.4.1"))
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    proof = _valid_proof("0.4.1", transcript_rel="agy/phantom.jsonl", transcript_sha="a" * 64)
    _write_json(proofs_dir / "agy" / "phantom.json", proof)
    rc = cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )
    assert rc == 1


def test_bogus_transcript_hash_does_not_satisfy_gate(tmp_path: Path) -> None:
    """Fail closed: an existing attested transcript with a mismatched sha256 fails the gate."""
    base = _write_json(tmp_path / "base.json", _marketplace("0.4.0"))
    head = _write_json(tmp_path / "head.json", _marketplace("0.4.1"))
    proofs_dir = tmp_path / "proofs"
    _seed_valid_proof(proofs_dir, "0.4.1")
    proof_path = proofs_dir / "agy" / "proof-0.4.1.json"
    data = json.loads(proof_path.read_text(encoding="utf-8"))
    data["transcript_sha256"] = "0" * 64  # deliberately wrong
    _write_json(proof_path, data)
    rc = cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )
    assert rc == 1


def test_transcriptless_proof_does_not_satisfy_gate(tmp_path: Path) -> None:
    """Documented decision (#457 fix round): a proof with NO transcript is unverifiable —
    entirely self-attested — and does not back a version bump."""
    base = _write_json(tmp_path / "base.json", _marketplace("0.4.0"))
    head = _write_json(tmp_path / "head.json", _marketplace("0.4.1"))
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    proof = _valid_proof("0.4.1", transcript_rel="", transcript_sha="")
    del proof["transcript"], proof["transcript_sha256"]
    _write_json(proofs_dir / "agy" / "bare.json", proof)
    rc = cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )
    assert rc == 1


def test_examples_proof_never_satisfies_gate(tmp_path: Path) -> None:
    """Red fixture from the #457 refute panel: a fully valid proof under examples/ must never
    satisfy the version gate — examples/ is documentation, not enforcement surface."""
    base = _write_json(tmp_path / "base.json", _marketplace("0.4.0"))
    head = _write_json(tmp_path / "head.json", _marketplace("0.4.1"))
    proofs_dir = tmp_path / "proofs"
    examples = proofs_dir / "examples"
    transcript = examples / "run.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(
            {
                "type": "tool_use",
                "tool_name": "Bash",
                "command": "agy --model 'Gemini 3.1 Pro (High)' -p 'do the task'",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sha = hashlib.sha256(transcript.read_bytes()).hexdigest()
    _write_json(
        examples / "proof.json",
        _valid_proof("0.4.1", transcript_rel="examples/run.jsonl", transcript_sha=sha),
    )
    assert cdp.load_proofs(proofs_dir) == []  # examples/ is never even loaded
    rc = cdp.main(
        [
            "--mode",
            "version-gate",
            "--manifest",
            str(REAL_MANIFEST),
            "--marketplace",
            str(head),
            "--base-marketplace",
            str(base),
            "--proofs-dir",
            str(proofs_dir),
        ]
    )
    assert rc == 1


def test_shipped_example_proof_cannot_collide_with_a_real_version() -> None:
    """Belt and suspenders: the shipped example is version-pinned to 0.0.0-example, which no
    real marketplace entry can carry."""
    example = (
        REPO_ROOT / "docs" / "delegation-proofs" / "examples" / "agy-genuine-example.proof.json"
    )
    data = json.loads(example.read_text(encoding="utf-8"))
    assert data["version"] == "0.0.0-example"


# ----------------------------------------------------------- pure-function coverage


def test_detect_bridge_version_bumps_pure() -> None:
    bumps = cdp.detect_bridge_version_bumps(_marketplace("0.4.0"), _marketplace("0.4.1"), {"agy"})
    assert [(b.plugin, b.old_version, b.new_version) for b in bumps] == [("agy", "0.4.0", "0.4.1")]


def test_detect_ignores_non_bridge_plugins() -> None:
    base = {"plugins": [{"name": "saga", "version": "1.0.0"}]}
    head = {"plugins": [{"name": "saga", "version": "1.1.0"}]}
    assert cdp.detect_bridge_version_bumps(base, head, {"agy"}) == []


# ----------------------------------------------------------------- real manifest


def test_real_manifest_is_valid_and_lists_agy() -> None:
    manifest = cdp.load_manifest(REAL_MANIFEST)
    assert "agy" in cdp.bridge_names(manifest)
    # the discriminator must match a genuine `agy --model` call and reject a bare spawn label
    disc = cdp.discriminator_for(manifest, "agy")
    assert disc.search("agy --model 'Gemini 3.1 Pro (High)' -p 'x'")
    assert not disc.search("spawned the agy teammate to do the work")


def test_malformed_manifest_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "bridge-plugins.v1", "bridges": {}}), encoding="utf-8")
    with pytest.raises(cdp.ManifestError):
        cdp.load_manifest(bad)


def test_missing_manifest_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(cdp.ManifestError):
        cdp.load_manifest(tmp_path / "nope.json")


# ------------------------------------------------------ AC3: modes independently run


def test_both_modes_dry_run_exit_zero() -> None:
    """AC3: version-gate and fleet-sweep are separately invocable smoke checks."""
    assert cdp.main(["--mode", "version-gate", "--dry-run"]) == 0
    assert cdp.main(["--mode", "fleet-sweep", "--dry-run"]) == 0


def test_cli_modes_invocable_via_subprocess() -> None:
    for mode in ("version-gate", "fleet-sweep"):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_ROOT / "check_delegation_proof.py"),
                "--mode",
                mode,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


# --------------------------------------------------------- AC4: CI wiring drift guard


def test_workflow_wires_both_jobs_on_correct_paths() -> None:
    """AC4: the delegation-integrity workflow triggers both guards on the correct paths."""
    assert WORKFLOW.exists(), "expected .github/workflows/delegation-integrity.yml"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "version-gate" in text
    assert "fleet-sweep" in text
    assert "check_delegation_proof.py" in text
    # version gate keys off marketplace.json; fleet sweep keys off recorded proof artifacts
    assert "marketplace.json" in text
    assert "delegation-proofs" in text
    # the sweep must run the standalone-transcript leg in CI (#457 fix round, FIX-C)
    assert "--transcripts-dir docs/delegation-proofs" in text


# ------------------------------------------- attestation containment (round-3 hardening)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_proof_borrowing_examples_transcript_fails(tmp_path: Path) -> None:
    """Panel probe: the checked-in example transcript's bytes and sha256 are public, so a
    live proof attesting it must fail the chain check — an illustrative artifact can never
    back a real proof, no matter how valid the hash is."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "examples").mkdir(parents=True)
    example_transcript = proofs_dir / "examples" / "genuine.jsonl"
    example_transcript.write_text(
        json.dumps(
            {
                "type": "tool_use",
                "tool_name": "Bash",
                "command": "agy --model 'Gemini 3.1 Pro (High)' -p 'do the task'",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (proofs_dir / "agy").mkdir()
    _write_json(
        proofs_dir / "agy" / "reuse.json",
        _valid_proof(
            "0.4.0",
            transcript_rel="examples/genuine.jsonl",
            transcript_sha=_sha(example_transcript),
        ),
    )
    proofs = cdp.load_proofs(proofs_dir)
    assert len(proofs) == 1
    reasons = cdp.verify_proof(
        proofs[0],
        cdp.discriminator_for(cdp.load_manifest(REAL_MANIFEST), "agy"),
        base_dir=proofs_dir,
    )
    assert any("examples/" in r for r in reasons), reasons


def test_proof_attesting_out_of_tree_transcript_fails(tmp_path: Path) -> None:
    """Attestation surface is the proofs directory: ../ traversal to a real file with a
    matching hash is a broken chain, not a verified proof."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    outside = tmp_path / "outside.jsonl"
    outside.write_text(
        json.dumps(
            {
                "type": "tool_use",
                "tool_name": "Bash",
                "command": "agy --model 'Gemini 3.1 Pro (High)' -p 'do the task'",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        proofs_dir / "agy" / "traversal.json",
        _valid_proof("0.4.0", transcript_rel="../outside.jsonl", transcript_sha=_sha(outside)),
    )
    proofs = cdp.load_proofs(proofs_dir)
    reasons = cdp.verify_proof(
        proofs[0],
        cdp.discriminator_for(cdp.load_manifest(REAL_MANIFEST), "agy"),
        base_dir=proofs_dir,
    )
    assert any("outside the proofs directory" in r for r in reasons), reasons


def test_chain_valid_proof_with_noop_transcript_fails(tmp_path: Path) -> None:
    """Chain-valid is necessary but not sufficient: a proof attesting a zero-event transcript
    (matching empty-bytes sha) must not verify — the attested CONTENT must itself evidence a
    genuine delegated run, or the version gate alone would accept it."""
    proofs_dir = tmp_path / "proofs"
    (proofs_dir / "agy").mkdir(parents=True)
    empty = proofs_dir / "agy" / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    _write_json(
        proofs_dir / "agy" / "noop.json",
        _valid_proof("0.4.0", transcript_rel="agy/empty.jsonl", transcript_sha=_sha(empty)),
    )
    proofs = cdp.load_proofs(proofs_dir)
    reasons = cdp.verify_proof(
        proofs[0],
        cdp.discriminator_for(cdp.load_manifest(REAL_MANIFEST), "agy"),
        base_dir=proofs_dir,
    )
    assert any("does not evidence a genuine delegated run" in r for r in reasons), reasons
