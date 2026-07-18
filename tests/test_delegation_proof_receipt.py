"""Receipt-bound delegation proof command tests (#355)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "delegation_proof_receipt.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delegation_proof_receipt", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["delegation_proof_receipt"] = module
    spec.loader.exec_module(module)
    return module


DPR = _load()


@pytest.fixture
def release_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    checker = repo / "scripts" / "check_delegation_proof.py"
    checker.write_text("# fixed checker\n")
    candidate = repo / "candidate.txt"
    candidate.write_text("release candidate\n")

    proofs = repo / "docs" / "delegation-proofs"
    proofs.mkdir(parents=True)
    proof = proofs / "agy.proof.json"
    transcript = proofs / "agy.transcript.jsonl"
    proof.write_text('{"schema":"delegation-proof.v1"}\n')
    transcript.write_text('{"type":"tool_use"}\n')

    monkeypatch.setattr(DPR, "REPO_ROOT", repo)
    monkeypatch.setattr(DPR, "CHECKER", checker)
    state: dict[str, Any] = {
        "base_ref": "1" * 40,
        "base": "1" * 40,
        "head": "3" * 40,
        "merge_base": "1" * 40,
        "index": "100644 " + "7" * 40 + " 0\tcandidate.txt\0",
        "ls_files_calls": 0,
    }
    candidate_paths = ["candidate.txt", *sorted(DPR.RECEIPT_EXCLUSIONS)]

    def fixed_git(*args: str, **_kwargs: Any) -> str:
        if args == ("ls-files", "-s", "-z"):
            return cast(str, state["index"])
        if args[0] == "ls-files":
            assert args == ("ls-files", "-z", "--cached", "--others", "--exclude-standard")
            state["ls_files_calls"] += 1
            return "\0".join(candidate_paths) + "\0"
        if args[0] == "merge-base":
            return cast(str, state["merge_base"])
        if args == ("rev-parse", "HEAD"):
            return cast(str, state["head"])
        return cast(str, state["base"])

    monkeypatch.setattr(DPR, "_git", fixed_git)
    return {
        "repo": repo,
        "proofs": proofs,
        "proof": proof,
        "transcript": transcript,
        "candidate": candidate,
        "state": state,
    }


def _passing(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, 0, "proof passed\n", "")


def _run(
    release_repository: dict[str, Any],
    *,
    mode: str = "version-gate",
    runner: Any = _passing,
) -> dict[str, Any]:
    proofs = release_repository["proofs"]
    return cast(
        dict[str, Any],
        DPR.run_gate(
            mode=mode,
            base_ref=release_repository["state"]["base_ref"],
            proofs_dir=proofs,
            transcripts_dir=proofs if mode == "fleet-sweep" else None,
            receipt_out=DPR._fixed_receipt_path(mode),
            runner=runner,
        ),
    )


def test_run_and_verify_bind_fixed_command_artifacts_and_candidate_snapshot(
    release_repository: dict[str, Any],
) -> None:
    receipt = _run(release_repository)
    receipt_path = DPR._fixed_receipt_path("version-gate")

    assert receipt["exit_code"] == 0
    assert receipt_path.stat().st_mode & 0o777 == 0o600
    assert receipt["candidate_files"] == [
        {
            "path": "candidate.txt",
            "mode": "100644",
            "sha256": DPR.hashlib.sha256(b"release candidate\n").hexdigest(),
        }
    ]
    assert not DPR.RECEIPT_EXCLUSIONS.intersection(
        row["path"] for row in receipt["candidate_files"]
    )
    assert receipt["proof_artifacts"][0]["path"] == ("docs/delegation-proofs/agy.proof.json")
    assert receipt["transcript_artifacts"][0]["path"] == (
        "docs/delegation-proofs/agy.transcript.jsonl"
    )
    assert DPR.verify_receipt(receipt_path, runner=_passing)["sha256"] == receipt["sha256"]
    assert release_repository["state"]["ls_files_calls"] == 4


@pytest.mark.parametrize("surface", ["head", "index", "candidate", "proof", "transcript"])
def test_run_rejects_any_checker_time_input_drift(
    release_repository: dict[str, Any], surface: str
) -> None:
    state = release_repository["state"]

    def drifting(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if surface == "head":
            state["head"] = "8" * 40
        elif surface == "index":
            state["index"] = "100644 " + "9" * 40 + " 0\tcandidate.txt\0"
        elif surface == "candidate":
            release_repository["candidate"].write_text("changed during checker\n")
        elif surface == "proof":
            release_repository["proof"].write_text('{"changed":true}\n')
        else:
            release_repository["transcript"].write_text('{"changed":true}\n')
        return subprocess.CompletedProcess(argv, 0, "proof passed\n", "")

    with pytest.raises(DPR.ReceiptError, match="changed while the checker ran"):
        _run(release_repository, runner=drifting)


def test_run_and_verify_reject_arbitrary_receipt_paths(
    release_repository: dict[str, Any],
) -> None:
    arbitrary = release_repository["repo"] / "arbitrary.json"
    with pytest.raises(DPR.ReceiptError, match="fixed repository path"):
        DPR.run_gate(
            mode="version-gate",
            base_ref=release_repository["state"]["base_ref"],
            proofs_dir=release_repository["proofs"],
            transcripts_dir=None,
            receipt_out=arbitrary,
            runner=_passing,
        )

    _run(release_repository)
    arbitrary.write_bytes(DPR._fixed_receipt_path("version-gate").read_bytes())
    with pytest.raises(DPR.ReceiptError, match="fixed repository paths"):
        DPR.verify_receipt(arbitrary, runner=_passing)


def test_run_rejects_symlinked_fixed_receipt_parent(
    release_repository: dict[str, Any], tmp_path: Path
) -> None:
    evidence = release_repository["repo"] / "docs" / "evidence"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.symlink_to(tmp_path / "outside", target_is_directory=True)

    with pytest.raises(DPR.ReceiptError, match="must not traverse a symlink"):
        _run(release_repository)


@pytest.mark.parametrize("location", ["external", "alternate"])
def test_run_and_verify_reject_noncanonical_proof_roots(
    release_repository: dict[str, Any], location: str
) -> None:
    receipt = _run(release_repository)
    repo = release_repository["repo"]
    invalid = repo.parent / "external-proofs" if location == "external" else repo / "proofs"
    invalid.mkdir()

    with pytest.raises(DPR.ReceiptError, match="fixed repository proof path"):
        DPR.run_gate(
            mode="version-gate",
            base_ref=release_repository["state"]["base_ref"],
            proofs_dir=invalid,
            transcripts_dir=None,
            receipt_out=DPR._fixed_receipt_path("version-gate"),
            runner=_passing,
        )

    receipt["proofs_dir"] = str(invalid)
    receipt["sha256"] = DPR._digest(receipt)
    DPR._fixed_receipt_path("version-gate").write_bytes(DPR._canonical(receipt) + b"\n")
    with pytest.raises(DPR.ReceiptError, match="fixed repository proof path"):
        DPR.verify_receipt(DPR._fixed_receipt_path("version-gate"), runner=_passing)


def test_run_and_verify_reject_symlinked_canonical_proof_root(
    release_repository: dict[str, Any],
) -> None:
    _run(release_repository)
    proofs = release_repository["proofs"]
    proof = release_repository["proof"]
    transcript = release_repository["transcript"]
    outside = release_repository["repo"].parent / "outside-proofs"
    outside.mkdir()
    proof.unlink()
    transcript.unlink()
    proofs.rmdir()
    proofs.symlink_to(outside, target_is_directory=True)

    with pytest.raises(DPR.ReceiptError, match="must not traverse a symlink"):
        DPR.run_gate(
            mode="version-gate",
            base_ref=release_repository["state"]["base_ref"],
            proofs_dir=proofs,
            transcripts_dir=None,
            receipt_out=DPR._fixed_receipt_path("version-gate"),
            runner=_passing,
        )
    with pytest.raises(DPR.ReceiptError, match="must not traverse a symlink"):
        DPR.verify_receipt(DPR._fixed_receipt_path("version-gate"), runner=_passing)


def test_fleet_sweep_requires_canonical_transcript_root(release_repository: dict[str, Any]) -> None:
    alternate = release_repository["repo"] / "transcripts"
    alternate.mkdir()

    with pytest.raises(DPR.ReceiptError, match="fixed repository proof path"):
        DPR.run_gate(
            mode="fleet-sweep",
            base_ref=release_repository["state"]["base_ref"],
            proofs_dir=release_repository["proofs"],
            transcripts_dir=alternate,
            receipt_out=DPR._fixed_receipt_path("fleet-sweep"),
            runner=_passing,
        )


def test_verify_rejects_artifact_rows_outside_repository_proof_root(
    release_repository: dict[str, Any],
) -> None:
    receipt = _run(release_repository)
    receipt["proof_artifacts"][0]["path"] = "/tmp/agy.proof.json"
    receipt["sha256"] = DPR._digest(receipt)
    receipt_path = DPR._fixed_receipt_path("version-gate")
    receipt_path.write_bytes(DPR._canonical(receipt) + b"\n")

    with pytest.raises(DPR.ReceiptError, match="repository-relative under docs/delegation-proofs"):
        DPR.verify_receipt(receipt_path, runner=_passing)


@pytest.mark.parametrize("base_ref", ["origin/main", "1" * 39, "g" * 40])
def test_run_rejects_mutable_or_non_sha_base_ref(
    release_repository: dict[str, Any], base_ref: str
) -> None:
    with pytest.raises(DPR.ReceiptError, match="full 40-hex immutable SHA"):
        DPR.run_gate(
            mode="version-gate",
            base_ref=base_ref,
            proofs_dir=release_repository["proofs"],
            transcripts_dir=None,
            receipt_out=DPR._fixed_receipt_path("version-gate"),
            runner=_passing,
        )


def test_run_requires_base_ref_to_resolve_and_be_live_merge_base(
    release_repository: dict[str, Any],
) -> None:
    state = release_repository["state"]
    state["base"] = "2" * 40
    with pytest.raises(DPR.ReceiptError, match="resolve exactly"):
        _run(release_repository)

    state["base"] = state["base_ref"]
    state["merge_base"] = "2" * 40
    with pytest.raises(DPR.ReceiptError, match="must equal the live git merge-base"):
        _run(release_repository)


def test_run_cli_requires_explicit_base_ref() -> None:
    with pytest.raises(SystemExit):
        DPR.build_parser().parse_args(
            [
                "run",
                "--mode",
                "version-gate",
                "--proofs-dir",
                "docs/delegation-proofs",
                "--receipt-out",
                "docs/evidence/issue-355/version-gate-command-receipt.json",
            ]
        )


def test_verify_rejects_tampered_artifact(
    release_repository: dict[str, Any],
) -> None:
    _run(release_repository, mode="fleet-sweep")
    release_repository["transcript"].write_text('{"type":"tampered"}\n')

    with pytest.raises(DPR.ReceiptError, match="transcript artifacts"):
        DPR.verify_receipt(DPR._fixed_receipt_path("fleet-sweep"), runner=_passing)


def test_verify_rejects_artifact_mode_drift(
    release_repository: dict[str, Any],
) -> None:
    _run(release_repository)
    release_repository["proof"].chmod(0o755)

    with pytest.raises(DPR.ReceiptError, match="proof artifacts"):
        DPR.verify_receipt(DPR._fixed_receipt_path("version-gate"), runner=_passing)


@pytest.mark.parametrize("drift", ["content", "mode"])
def test_verify_rejects_candidate_content_or_mode_drift(
    release_repository: dict[str, Any], drift: str
) -> None:
    _run(release_repository)
    candidate = release_repository["candidate"]
    if drift == "content":
        candidate.write_text("post-run drift\n")
    else:
        candidate.chmod(0o755)

    with pytest.raises(DPR.ReceiptError, match="candidate files, modes, or digests"):
        DPR.verify_receipt(DPR._fixed_receipt_path("version-gate"), runner=_passing)


def test_nonzero_command_retains_nonpassing_receipt(
    release_repository: dict[str, Any],
) -> None:
    def failing(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "proof failed\n")

    with pytest.raises(DPR.ReceiptError, match="failed with exit 1"):
        _run(release_repository, runner=failing)

    receipt_path = DPR._fixed_receipt_path("version-gate")
    retained = json.loads(receipt_path.read_text())
    assert retained["exit_code"] == 1
    with pytest.raises(DPR.ReceiptError, match="nonzero"):
        DPR.verify_receipt(receipt_path, runner=_passing)


def test_verify_rejects_live_base_or_merge_base_drift(
    release_repository: dict[str, Any],
) -> None:
    state = release_repository["state"]
    _run(release_repository)
    receipt_path = DPR._fixed_receipt_path("version-gate")

    state["base"] = "5" * 40
    with pytest.raises(DPR.ReceiptError, match="base no longer"):
        DPR.verify_receipt(receipt_path, runner=_passing)
    state["base"] = state["base_ref"]
    state["merge_base"] = "6" * 40
    with pytest.raises(DPR.ReceiptError, match="merge base no longer"):
        DPR.verify_receipt(receipt_path, runner=_passing)


def test_verify_accepts_later_commit_changing_only_fixed_receipt_artifacts(
    release_repository: dict[str, Any],
) -> None:
    receipt = _run(release_repository)
    release_repository["state"]["head"] = "4" * 40
    other_receipt = DPR._fixed_receipt_path("fleet-sweep")
    other_receipt.parent.mkdir(parents=True, exist_ok=True)
    other_receipt.write_text("later receipt-only commit artifact\n")

    verified = DPR.verify_receipt(DPR._fixed_receipt_path("version-gate"), runner=_passing)

    assert verified["sha256"] == receipt["sha256"]


def test_verify_rejects_receipt_at_the_other_modes_fixed_path(
    release_repository: dict[str, Any],
) -> None:
    _run(release_repository, mode="fleet-sweep")
    fleet_receipt = DPR._fixed_receipt_path("fleet-sweep")
    version_receipt = DPR._fixed_receipt_path("version-gate")
    version_receipt.write_bytes(fleet_receipt.read_bytes())

    with pytest.raises(DPR.ReceiptError, match="mode does not match"):
        DPR.verify_receipt(version_receipt, runner=_passing)


def test_verify_reruns_fixed_checker_instead_of_trusting_recorded_exit(
    release_repository: dict[str, Any],
) -> None:
    _run(release_repository, mode="fleet-sweep")

    def failing(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 9, "", "checker failed\n")

    with pytest.raises(DPR.ReceiptError, match="cannot be reproduced"):
        DPR.verify_receipt(DPR._fixed_receipt_path("fleet-sweep"), runner=failing)
