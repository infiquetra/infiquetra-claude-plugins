"""Tests for the cross-runtime Outcome compatibility contract (#604, U1 surface).

These oracles pin the discovery/identity/schema layer the Codex consumer ports verbatim:

* happy — identity normalization across origin spellings; envelope build + deterministic
  serialization; committed-spec binding; protocol negotiation on the supported range;
* edge — linked-worktree identity; local/remote ref agreement; clean-vs-dirty working tree;
  bool-as-int and duplicate-key strictness; oversize and non-regular-file caps;
* error — foreign host, credentialed URL, missing origin, ambiguous refs, embedded-id
  mismatch, protocol skew, unknown capability/field — every path a closed HALT receipt;
* integration — real temporary git repositories (init, commit, branch, worktree), no network.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPTS / "outcome_compat.py"


def _load() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("outcome_compat", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["outcome_compat"] = module
    spec.loader.exec_module(module)
    return module


OC = _load()

OUTCOME_ID = "lease-demo"
ORIGIN_HTTPS = "https://github.com/infiquetra/demo-repo.git"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _spec_dict(outcome_id: str = OUTCOME_ID, *, revision: int = 3) -> dict[str, Any]:
    return {
        "outcome_id": outcome_id,
        "objective": "demo",
        "nodes": [],
        "spec_revision": revision,
        "schema_version": 1,
        "decision_trail": [],
        "cost_rollup": {},
        "created_at": "2026-07-18T00:00:00Z",
        "updated_at": "2026-07-18T00:00:00Z",
    }


@pytest.fixture
def outcome_repo(tmp_path: Path) -> Path:
    """A real git repo with one committed outcome spec and a canonical origin remote."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    spec_file = repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text(json.dumps(_spec_dict(), indent=1), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed outcome spec")
    _git(repo, "remote", "add", "origin", ORIGIN_HTTPS)
    return repo


# ---------------------------------------------------------------------------
# Repository identity (R2)
# ---------------------------------------------------------------------------


class TestRepositoryIdentity:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/infiquetra/demo-repo.git",
            "https://github.com/infiquetra/demo-repo",
            "git@github.com:infiquetra/demo-repo.git",
            "git@github.com:infiquetra/demo-repo",
            "ssh://git@github.com/infiquetra/demo-repo.git",
        ],
    )
    def test_accepted_origin_spellings_normalize_identically(
        self, outcome_repo: Path, url: str
    ) -> None:
        _git(outcome_repo, "remote", "set-url", "origin", url)
        assert OC.repository_identity(outcome_repo) == "github.com/infiquetra/demo-repo"

    def test_linked_worktree_resolves_the_same_identity(
        self, outcome_repo: Path, tmp_path: Path
    ) -> None:
        wt = tmp_path / "wt"
        _git(outcome_repo, "worktree", "add", "-q", str(wt))
        assert OC.repository_identity(wt) == OC.repository_identity(outcome_repo)

    def test_foreign_host_halts(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "remote", "set-url", "origin", "https://gitlab.com/infiquetra/x.git")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.repository_identity(outcome_repo)
        assert exc.value.code == "repo-identity-foreign-host"

    def test_credentialed_url_halts(self, outcome_repo: Path) -> None:
        _git(
            outcome_repo,
            "remote",
            "set-url",
            "origin",
            "https://user:token@github.com/infiquetra/demo-repo.git",
        )
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.repository_identity(outcome_repo)
        assert exc.value.code == "repo-identity-credentialed-url"

    def test_missing_origin_halts(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "remote", "remove", "origin")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.repository_identity(outcome_repo)
        assert exc.value.code == "repo-identity-missing-origin"

    def test_local_path_remote_halts_malformed(self, outcome_repo: Path, tmp_path: Path) -> None:
        _git(outcome_repo, "remote", "set-url", "origin", str(tmp_path / "elsewhere"))
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.repository_identity(outcome_repo)
        assert exc.value.code == "repo-identity-malformed"

    def test_only_terminal_dot_git_is_stripped(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "remote", "set-url", "origin", "https://github.com/infiquetra/x.git.git")
        assert OC.repository_identity(outcome_repo) == "github.com/infiquetra/x.git"

    def test_git_timeout_maps_to_git_unavailable_halt(self, outcome_repo: Path) -> None:
        def timing_out(*args: Any, **kwargs: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd="git", timeout=OC.GIT_TIMEOUT_SECONDS)

        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.repository_identity(outcome_repo, runner=timing_out)
        assert exc.value.code == "git-unavailable"


# ---------------------------------------------------------------------------
# Committed-spec discovery (R3/R4)
# ---------------------------------------------------------------------------


class TestCommittedSpecDiscovery:
    def test_binding_carries_exact_committed_identity(self, outcome_repo: Path) -> None:
        binding = OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        assert binding["spec_path"] == f"docs/outcomes/{OUTCOME_ID}/outcome-spec.json"
        assert binding["spec_revision"] == 3
        assert binding["schema_version"] == 1
        head_blob = _git(outcome_repo, "rev-parse", f"HEAD:{binding['spec_path']}")
        assert binding["blob_oid"] == head_blob
        assert binding["commit_oid"] == _git(outcome_repo, "rev-parse", "HEAD")
        import hashlib

        assert binding["sha256"] == hashlib.sha256(binding["blob"]).hexdigest()

    def test_agreeing_outcome_branch_is_not_ambiguous(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "branch", f"outcome/{OUTCOME_ID}")
        binding = OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        assert binding["spec_revision"] == 3

    def test_git_nonzero_exit_halts_git_failed(self, tmp_path: Path) -> None:
        def failing(*args: Any, **kwargs: Any) -> Any:
            return subprocess.CompletedProcess(args, 128, b"", b"fatal: boom")

        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC._git(["rev-parse", "HEAD"], cwd=tmp_path, runner=failing)
        assert exc.value.code == "git-failed"

    def test_git_output_beyond_cap_halts(self, tmp_path: Path) -> None:
        def oversized(*args: Any, **kwargs: Any) -> Any:
            return subprocess.CompletedProcess(args, 0, b"x" * (OC.GIT_STDOUT_CAP + 1), b"")

        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC._git(["cat-file", "blob", "HEAD:x"], cwd=tmp_path, runner=oversized)
        assert exc.value.code == "git-output-cap"

    def test_spec_beyond_node_cap_halts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _single_node_repo(tmp_path)
        monkeypatch.setattr(OC, "MAX_SPEC_NODES", 0)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.resolve_committed_spec(repo, OUTCOME_ID)
        assert exc.value.code == "discovery-node-cap"

    def test_disagreeing_refs_halt_ambiguous(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "checkout", "-q", "-b", f"outcome/{OUTCOME_ID}")
        spec_file = outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        spec_file.write_text(json.dumps(_spec_dict(revision=4), indent=1), encoding="utf-8")
        _git(outcome_repo, "commit", "-aqm", "bump revision on outcome branch")
        _git(outcome_repo, "checkout", "-q", "main")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        assert exc.value.code == "discovery-ambiguous-refs"

    def test_remote_ref_disagreement_halts_ambiguous(self, outcome_repo: Path) -> None:
        spec_file = outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        spec_file.write_text(json.dumps(_spec_dict(revision=9), indent=1), encoding="utf-8")
        _git(outcome_repo, "commit", "-aqm", "newer spec on main")
        older = _git(outcome_repo, "rev-parse", "HEAD~1")
        _git(outcome_repo, "update-ref", f"refs/remotes/origin/outcome/{OUTCOME_ID}", older)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        assert exc.value.code == "discovery-ambiguous-refs"

    def test_absent_spec_halts(self, outcome_repo: Path) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.resolve_committed_spec(outcome_repo, "unknown-outcome")
        assert exc.value.code == "discovery-spec-absent"

    def test_embedded_id_mismatch_halts(self, outcome_repo: Path) -> None:
        spec_file = outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        spec_file.write_text(json.dumps(_spec_dict("other-id"), indent=1), encoding="utf-8")
        _git(outcome_repo, "commit", "-aqm", "wrong embedded id")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        assert exc.value.code == "discovery-outcome-id-mismatch"

    def test_dirty_working_tree_does_not_change_committed_binding(self, outcome_repo: Path) -> None:
        binding = OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        spec_file = outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        assert OC.working_tree_matches(outcome_repo, binding) is True
        spec_file.write_text(json.dumps(_spec_dict(revision=99), indent=1), encoding="utf-8")
        rebinding = OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        assert rebinding["spec_revision"] == 3  # committed blob, not working tree (KTD3)
        assert OC.working_tree_matches(outcome_repo, rebinding) is False

    def test_missing_working_tree_file_never_matches(self, outcome_repo: Path) -> None:
        binding = OC.resolve_committed_spec(outcome_repo, OUTCOME_ID)
        (outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json").unlink()
        assert OC.working_tree_matches(outcome_repo, binding) is False


# ---------------------------------------------------------------------------
# Discovery envelope build + closed validation
# ---------------------------------------------------------------------------


class TestDiscoveryEnvelope:
    def test_envelope_builds_validates_and_serializes_deterministically(
        self, outcome_repo: Path
    ) -> None:
        first = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        second = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        assert OC.canonical_json(first) == OC.canonical_json(second)
        assert first["schema"] == OC.SCHEMA_DISCOVERY
        assert first["repository"]["identity"] == "github.com/infiquetra/demo-repo"
        assert first["authority"]["cross_clone_mutation"] == "forbidden"
        assert first["producer"] == {"runtime": "claude", "saga_version": "0.103.0"}

    def test_envelope_never_serializes_local_paths(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        text = OC.canonical_json(envelope)
        assert str(outcome_repo) not in text
        assert str(outcome_repo.parent) not in text
        assert "/Users/" not in text and "/tmp/" not in text and "/private/" not in text

    def test_round_trip_parse_accepts_own_output(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        parsed = OC.parse_discovery_envelope(OC.canonical_json(envelope))
        assert parsed["committed"] == envelope["committed"]

    def test_unknown_top_level_field_halts(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        envelope["extra"] = "x"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_discovery_envelope(envelope)
        assert exc.value.code == "schema-field-unknown"

    def test_unknown_security_subobject_field_halts(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        envelope["committed"]["hint"] = "x"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_discovery_envelope(envelope)
        assert exc.value.code == "schema-field-unknown"

    def test_bool_as_int_revision_halts(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        envelope["outcome"]["spec_revision"] = True
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_discovery_envelope(envelope)
        assert exc.value.code == "schema-field-type"

    def test_wrong_schema_name_halts_unknown(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.parse_discovery_envelope(json.dumps({"schema": "outcome.discovery.v9"}))
        assert exc.value.code in ("schema-unknown", "schema-field-missing", "schema-field-unknown")

    def test_duplicate_json_key_halts(self) -> None:
        raw = '{"schema": "outcome.discovery.v1", "schema": "outcome.discovery.v1"}'
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.parse_discovery_envelope(raw)
        assert exc.value.code == "schema-duplicate-key"

    def test_oversize_input_halts(self) -> None:
        raw = '{"pad": "' + "x" * OC.MAX_ENVELOPE_BYTES + '"}'
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.parse_discovery_envelope(raw)
        assert exc.value.code == "input-oversize"

    def test_traversing_spec_path_halts(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        envelope["outcome"]["spec_path"] = "../outside/outcome-spec.json"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_discovery_envelope(envelope)
        assert exc.value.code == "schema-field-type"

    def test_authority_block_must_match_the_frozen_model(self, outcome_repo: Path) -> None:
        envelope = OC.build_discovery_envelope(outcome_repo, OUTCOME_ID, saga_version="0.103.0")
        envelope["authority"]["cross_clone_mutation"] = "allowed"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_discovery_envelope(envelope)
        assert exc.value.code == "schema-field-type"


# ---------------------------------------------------------------------------
# Reference-file reading (R12)
# ---------------------------------------------------------------------------


class TestReferenceFileReading:
    def test_symlink_halts(self, tmp_path: Path) -> None:
        target = tmp_path / "real.json"
        target.write_text("{}", encoding="utf-8")
        link = tmp_path / "link.json"
        link.symlink_to(target)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.read_reference_file(link, what="envelope")
        assert exc.value.code == "input-not-regular-file"

    def test_directory_halts(self, tmp_path: Path) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.read_reference_file(tmp_path, what="envelope")
        assert exc.value.code == "input-not-regular-file"

    def test_malformed_json_bytes_halt(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.parse_strict_json(b"{not json", what="envelope")
        assert exc.value.code == "schema-malformed-json"

    def test_oversize_file_halts(self, tmp_path: Path) -> None:
        big = tmp_path / "big.json"
        big.write_bytes(b"x" * (OC.MAX_ENVELOPE_BYTES + 1))
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.read_reference_file(big, what="envelope")
        assert exc.value.code == "input-oversize"

    def test_regular_file_reads(self, tmp_path: Path) -> None:
        path = tmp_path / "ok.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        assert OC.read_reference_file(path, what="envelope") == b'{"a": 1}'


# ---------------------------------------------------------------------------
# Protocol negotiation (R9)
# ---------------------------------------------------------------------------


def _peer(version: int = 1, lo: int = 1, hi: int = 1, caps: list[str] | None = None) -> dict:
    return {
        "version": version,
        "min_supported": lo,
        "max_supported": hi,
        "required_capabilities": caps if caps is not None else [],
    }


class TestProtocolNegotiation:
    def test_supported_peer_negotiates_the_shared_version(self) -> None:
        assert OC.negotiate(_peer(caps=["github-completion"])) == 1

    def test_future_only_peer_halts_skew(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(_peer(version=2, lo=2, hi=3))
        assert exc.value.code == "protocol-version-skew"

    def test_past_only_peer_halts_skew(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(_peer(version=0, lo=0, hi=0))
        assert exc.value.code == "protocol-version-skew"

    def test_unknown_required_capability_halts(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(_peer(caps=["quantum-entanglement"]))
        assert exc.value.code == "capability-missing"

    def test_malformed_range_halts(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(_peer(version=1, lo=2, hi=1))
        assert exc.value.code == "protocol-range-malformed"

    def test_bool_version_halts_type(self) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(_peer(version=True))  # type: ignore[arg-type]
        assert exc.value.code == "schema-field-type"

    def test_unknown_protocol_field_halts(self) -> None:
        peer = _peer()
        peer["compat_mode"] = "loose"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(peer)
        assert exc.value.code == "schema-field-unknown"


# ---------------------------------------------------------------------------
# Canonical-status / handoff-reference / halt-receipt closed validation
# ---------------------------------------------------------------------------


def _status_doc() -> dict[str, Any]:
    return {
        "schema": OC.SCHEMA_CANONICAL_STATUS,
        "repository_identity": "github.com/infiquetra/demo-repo",
        "outcome_id": OUTCOME_ID,
        "committed": {"commit_oid": "a" * 40, "blob_oid": "b" * 40, "sha256": "c" * 64},
        "completed": ["sub-1"],
        "candidate_frontier": ["sub-2"],
        "unknown": [],
        "node_completion": [
            {
                "subplot_id": "sub-1",
                "contract": "pr-merged",
                "canonical_state": "complete",
                "evidence_digest": "d" * 64,
            }
        ],
        "mutation_allowed": False,
    }


class TestCanonicalStatusValidation:
    def test_valid_document_passes(self) -> None:
        assert OC.validate_canonical_status(_status_doc())["mutation_allowed"] is False

    def test_mutation_allowed_true_halts(self) -> None:
        doc = _status_doc()
        doc["mutation_allowed"] = True
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_canonical_status(doc)
        assert exc.value.code == "schema-field-type"

    def test_transient_state_vocabulary_is_rejected(self) -> None:
        doc = _status_doc()
        doc["node_completion"][0]["canonical_state"] = "dispatched"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_canonical_status(doc)
        assert exc.value.code == "schema-field-type"

    def test_unknown_field_halts(self) -> None:
        doc = _status_doc()
        doc["leases"] = []
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_canonical_status(doc)
        assert exc.value.code == "schema-field-unknown"


def _handoff_doc() -> dict[str, Any]:
    return {
        "schema": OC.SCHEMA_HANDOFF_REFERENCE,
        "handoff_id": "0" * 32,
        "digest": "e" * 64,
        "protocol": _peer(),
        "operation": "advance-one",
        "subplot_id": "sub-2",
    }


class TestHandoffReferenceValidation:
    def test_valid_reference_passes(self) -> None:
        assert OC.validate_handoff_reference(_handoff_doc())["operation"] == "advance-one"

    def test_unscoped_operation_halts(self) -> None:
        doc = _handoff_doc()
        doc["operation"] = "advance-frontier"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_handoff_reference(doc)
        assert exc.value.code == "schema-field-type"

    def test_short_handoff_id_halts(self) -> None:
        doc = _handoff_doc()
        doc["handoff_id"] = "abc"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_handoff_reference(doc)
        assert exc.value.code == "schema-field-type"

    def test_extra_field_halts(self) -> None:
        doc = _handoff_doc()
        doc["repo_root"] = "/somewhere"
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_handoff_reference(doc)
        assert exc.value.code == "schema-field-unknown"


class TestHaltReceipts:
    def test_receipts_round_trip_their_own_schema(self) -> None:
        try:
            OC.negotiate(_peer(version=5, lo=5, hi=5))
        except OC.CompatibilityHaltError as halt:
            receipt = halt.receipt()
        assert OC.validate_halt_receipt(receipt) is receipt
        assert receipt["schema"] == OC.SCHEMA_COMPATIBILITY_HALT
        assert receipt["code"] == "protocol-version-skew"

    def test_receipts_never_leak_paths(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "remote", "remove", "origin")
        try:
            OC.repository_identity(outcome_repo)
        except OC.CompatibilityHaltError as halt:
            text = json.dumps(halt.receipt())
        assert str(outcome_repo) not in text
        assert "/Users/" not in text and "/tmp/" not in text and "/private/" not in text


# ---------------------------------------------------------------------------
# Canonical cross-clone reconstruction (R8, U2)
# ---------------------------------------------------------------------------


def _node(sid: str, kind: str = "code", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"subplot_id": sid, "title": sid, "kind": kind}
    base.update(overrides)
    return base


def _dag_spec_dict() -> dict[str, Any]:
    spec = _spec_dict()
    spec["nodes"] = [
        _node("sub-a", github={"pr": "infiquetra/demo-repo#1"}),
        _node("sub-b", github={"pr": "infiquetra/demo-repo#2"}, depends_on=["sub-a"]),
        _node("sub-c", kind="non-code", github={"issue": "infiquetra/demo-repo#3"}),
        _node(
            "sub-d",
            kind="non-code",
            github={"issue": "infiquetra/demo-repo#4"},
            depends_on=["sub-a", "sub-c"],
        ),
        _node("sub-e", github={"pr": "infiquetra/demo-repo#5"}, depends_on=["sub-a"]),
        _node("sub-f", kind="non-code"),
    ]
    return spec


def _gh_fixture() -> Any:
    """A deterministic gh stand-in: PR 1 merged, PR 2 open, issue 3 closed, issue 4 open,
    PR 5 a transient read failure (unknown)."""
    from types import SimpleNamespace

    canned = {
        "/pull/1": {"state": "MERGED", "mergedAt": "2026-07-18T00:00:00Z"},
        "/pull/2": {"state": "OPEN", "mergedAt": None},
        "/issues/3": {"state": "CLOSED"},
        "/issues/4": {"state": "OPEN"},
    }

    def runner(argv: list[str], **_kw: Any) -> Any:
        ref = argv[3]
        for key, payload in canned.items():
            if key in ref:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 500 transient")

    return runner


@pytest.fixture
def dag_repo(tmp_path: Path) -> Path:
    """A real git repo committing the seven-node DAG spec used by the R8 oracles."""
    repo = tmp_path / "dag"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    spec_file = repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text(json.dumps(_dag_spec_dict(), indent=1), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed dag spec")
    _git(repo, "remote", "add", "origin", ORIGIN_HTTPS)
    return repo


def _store_namespace_absent(repo: Path) -> bool:
    common = Path(_git(repo, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = repo / common
    return not (common / "saga-outcomes").exists()


class TestCanonicalReconstruction:
    def test_partition_completed_frontier_unknown(self, dag_repo: Path) -> None:
        status = OC.build_canonical_status(dag_repo, OUTCOME_ID, github_runner=_gh_fixture())
        assert status["completed"] == ["sub-a", "sub-c"]
        assert status["unknown"] == ["sub-e", "sub-f"]
        assert status["candidate_frontier"] == ["sub-b", "sub-d"]
        assert status["mutation_allowed"] is False
        by_id = {row["subplot_id"]: row for row in status["node_completion"]}
        assert by_id["sub-a"]["canonical_state"] == "complete"
        assert by_id["sub-b"]["canonical_state"] == "open"
        assert by_id["sub-e"]["canonical_state"] == "unknown"
        assert by_id["sub-f"]["contract"] == "non-code:tick+canonical-marker"

    def test_unknown_reduces_never_fabricates(self, dag_repo: Path) -> None:
        from types import SimpleNamespace

        def all_unknown(argv: list[str], **_kw: Any) -> Any:
            return SimpleNamespace(returncode=1, stdout="", stderr="offline")

        status = OC.build_canonical_status(dag_repo, OUTCOME_ID, github_runner=all_unknown)
        assert status["completed"] == []
        assert status["candidate_frontier"] == []
        assert set(status["unknown"]) == {"sub-a", "sub-b", "sub-c", "sub-d", "sub-e", "sub-f"}

    def test_two_clones_serialize_byte_identically(self, dag_repo: Path, tmp_path: Path) -> None:
        clone = tmp_path / "clone-b"
        _git(dag_repo.parent, "clone", "-q", str(dag_repo), str(clone))
        _git(clone, "remote", "set-url", "origin", ORIGIN_HTTPS)
        first = OC.build_canonical_status(dag_repo, OUTCOME_ID, github_runner=_gh_fixture())
        second = OC.build_canonical_status(clone, OUTCOME_ID, github_runner=_gh_fixture())
        assert OC.canonical_json(first) == OC.canonical_json(second)
        assert _store_namespace_absent(dag_repo) and _store_namespace_absent(clone)

    def test_reconstruction_never_creates_the_cache(self, dag_repo: Path) -> None:
        OC.build_canonical_status(dag_repo, OUTCOME_ID, github_runner=_gh_fixture())
        assert _store_namespace_absent(dag_repo)

    def test_fork_with_copied_spec_carries_its_own_identity(
        self, dag_repo: Path, tmp_path: Path
    ) -> None:
        fork = tmp_path / "fork"
        _git(dag_repo.parent, "clone", "-q", str(dag_repo), str(fork))
        _git(fork, "remote", "set-url", "origin", "https://github.com/attacker/demo-repo.git")
        envelope = OC.build_discovery_envelope(dag_repo, OUTCOME_ID, saga_version="0.103.0")
        status = OC.build_canonical_status(fork, OUTCOME_ID, github_runner=_gh_fixture())
        assert status["repository_identity"] != envelope["repository"]["identity"]

    def test_projection_never_serializes_local_paths(self, dag_repo: Path) -> None:
        status = OC.build_canonical_status(dag_repo, OUTCOME_ID, github_runner=_gh_fixture())
        text = OC.canonical_json(status)
        assert str(dag_repo) not in text
        assert "/Users/" not in text and "/tmp/" not in text and "/private/" not in text

    def test_invalid_committed_spec_halts(self, dag_repo: Path) -> None:
        spec_file = dag_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        bad = _dag_spec_dict()
        bad["nodes"].append(_node("sub-a"))  # duplicate subplot_id
        spec_file.write_text(json.dumps(bad, indent=1), encoding="utf-8")
        _git(dag_repo, "commit", "-aqm", "duplicate node id")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.build_canonical_status(dag_repo, OUTCOME_ID, github_runner=_gh_fixture())
        assert exc.value.code == "discovery-spec-invalid"


# ---------------------------------------------------------------------------
# Protected same-clone handoff (R5/R6, U3) — against the REAL fleet broker
# ---------------------------------------------------------------------------

FLEET_COMMONS = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons"


def _load_broker_module() -> ModuleType:
    if str(FLEET_COMMONS) not in sys.path:
        sys.path.insert(0, str(FLEET_COMMONS))
    # A distinct sys.modules key: plugins/saga/scripts/ has its OWN lease_broker.py (the session
    # admission CLI), and clobbering that name breaks unrelated outcome CLI tests in-session.
    spec = importlib.util.spec_from_file_location(
        "_test_fleet_lease_broker", FLEET_COMMONS / "lease_broker.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_test_fleet_lease_broker"] = module
    spec.loader.exec_module(module)
    return module


LB = _load_broker_module()

IDENTITY = "github.com/infiquetra/demo-repo"
SUBPLOT = "sub-2"
ADMISSION = {
    "session_id": "sess-receiver",
    "policy_sha256": "b" * 64,
    "session_limit": 3,
    "aggregate_limit": 6,
}


# ------------------------------------------------------------------ handoff-store privacy (#624)


def test_write_once_creates_private_handoffs_dir(tmp_path: Path) -> None:
    """PA-1 (#624): missing handoff-store directories are created owner-only (0o700)."""
    target = tmp_path / "store" / "handoffs" / "h1.offer.json"
    assert OC._write_once(target, {"schema": "x"}) is True
    for directory in (target.parent, target.parent.parent):
        assert stat.S_IMODE(directory.lstat().st_mode) == 0o700
    assert stat.S_IMODE(target.lstat().st_mode) == 0o600


def test_write_once_refuses_permissive_preexisting_dir(tmp_path: Path) -> None:
    """PA-1 (#624): a pre-existing permissive handoffs directory is refused, never adopted."""
    handoffs = tmp_path / "handoffs"
    handoffs.mkdir()
    os.chmod(handoffs, 0o755)
    with pytest.raises(OC.CompatibilityHaltError) as exc:
        OC._write_once(handoffs / "h1.offer.json", {"schema": "x"})
    assert exc.value.receipt()["code"] == "handoff-store-unsafe"
    assert not (handoffs / "h1.offer.json").exists()


def test_write_once_refuses_symlinked_handoffs_dir(tmp_path: Path) -> None:
    """PA-1 (#624): a symlinked handoffs directory is refused before any record write."""
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "handoffs"
    link.symlink_to(real)
    with pytest.raises(OC.CompatibilityHaltError) as exc:
        OC._write_once(link / "h1.offer.json", {"schema": "x"})
    assert exc.value.receipt()["code"] == "handoff-store-unsafe"
    assert list(real.iterdir()) == []


@pytest.fixture
def broker(tmp_path: Path) -> Any:
    root = tmp_path / "fleet-leases"
    root.mkdir(mode=0o700)
    return LB.LeaseBroker(root)


def _issuer_lease(broker: Any, *, attempt: int = 1) -> Any:
    return broker.acquire_agent(
        owner_id="issuer-claude",
        session_id="sess-issuer",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=6,
        mutation="read-write",
        resource_ref=OC.outcome_dispatch_resource(IDENTITY, OUTCOME_ID, SUBPLOT, attempt),
    )


def _offer(repo: Path, broker: Any, lease: Any, **kw: Any) -> tuple[dict, dict]:
    defaults: dict[str, Any] = {
        "operation": "advance-one",
        "attempt": 1,
        "broker": broker,
        "lease": lease,
        "dispatch_id": "outcome:demo:frontier:abc",
    }
    defaults.update(kw)
    return cast("tuple[dict, dict]", OC.offer_handoff(repo, OUTCOME_ID, SUBPLOT, **defaults))


def _accept(repo: Path, broker: Any, handoff_id: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "operation": "advance-one",
        "subplot_id": SUBPLOT,
        "receiver_owner_id": "receiver-codex",
        "receiver_runtime": "codex",
        "admission": dict(ADMISSION),
        "broker": broker,
    }
    defaults.update(kw)
    return cast("dict[str, Any]", OC.accept_handoff(repo, OUTCOME_ID, handoff_id, **defaults))


class TestProtectedHandoff:
    def test_offer_accept_transfers_broker_authority_once(
        self, outcome_repo: Path, broker: Any
    ) -> None:
        lease = _issuer_lease(broker)
        offer, reference = _offer(outcome_repo, broker, lease)
        assert reference["schema"] == OC.SCHEMA_HANDOFF_REFERENCE
        assert reference["digest"] == offer["sha256"]
        assert offer["issuer_owner_id"] == "issuer-claude"
        result = _accept(outcome_repo, broker, offer["handoff_id"])
        successor = result["lease"]
        assert successor.owner_id == "receiver-codex"
        assert successor.token.fencing_sequence > lease.token.fencing_sequence
        assert result["commit"]["successor_lease_id"] == successor.lease_id

    def test_public_reference_carries_no_paths_or_cache_facts(
        self, outcome_repo: Path, broker: Any
    ) -> None:
        _offer_record, reference = _offer(outcome_repo, broker, _issuer_lease(broker))
        text = json.dumps(reference)
        assert str(outcome_repo) not in text
        assert "/Users/" not in text and "/tmp/" not in text and "/private/" not in text
        assert set(reference) == {
            "schema",
            "handoff_id",
            "digest",
            "protocol",
            "operation",
            "subplot_id",
        }

    def test_same_receiver_reacceptance_is_idempotent(
        self, outcome_repo: Path, broker: Any
    ) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        first = _accept(outcome_repo, broker, offer["handoff_id"])
        second = _accept(outcome_repo, broker, offer["handoff_id"])
        assert second["commit"] == first["commit"]
        assert second["lease"].owner_id == "receiver-codex"

    def test_crash_between_grant_and_commit_resumes_for_same_receiver(
        self, outcome_repo: Path, broker: Any
    ) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        first = _accept(outcome_repo, broker, offer["handoff_id"])
        commit_path = OC._handoffs_dir(outcome_repo, OUTCOME_ID) / (
            f"{offer['handoff_id']}.commit.json"
        )
        commit_path.unlink()  # simulate the crash window after grant, before commit
        resumed = _accept(outcome_repo, broker, offer["handoff_id"])
        assert resumed["commit"]["successor_lease_id"] == first["lease"].lease_id

    def test_second_receiver_halts_on_bound_intent(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        _accept(outcome_repo, broker, offer["handoff_id"])
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(
                outcome_repo,
                broker,
                offer["handoff_id"],
                receiver_owner_id="receiver-two",
            )
        assert exc.value.code == "handoff-receiver-conflict"

    def test_expired_offer_halts(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker), ttl_seconds=60)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(
                outcome_repo,
                broker,
                offer["handoff_id"],
                now=lambda: float(offer["expires_at_epoch"] + 1),
            )
        assert exc.value.code == "handoff-expired"

    def test_future_issued_offer_halts_clock_skew(self, outcome_repo: Path, broker: Any) -> None:
        import time as _time

        future = _time.time() + 1000
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker), now=lambda: future)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, broker, offer["handoff_id"])
        assert exc.value.code == "handoff-clock-skew"

    def test_ttl_above_cap_halts(self, outcome_repo: Path, broker: Any) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _offer(outcome_repo, broker, _issuer_lease(broker), ttl_seconds=301)
        assert exc.value.code == "handoff-ttl-too-long"

    def test_byte_tamper_halts_seal(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        path = OC._handoffs_dir(outcome_repo, OUTCOME_ID) / f"{offer['handoff_id']}.offer.json"
        record = json.loads(path.read_text())
        record["subplot_id"] = "sub-other"
        path.write_text(json.dumps(record))
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, broker, offer["handoff_id"])
        assert exc.value.code == "handoff-seal-invalid"

    def test_advance_one_offer_requires_dispatch_id(self, outcome_repo: Path, broker: Any) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _offer(outcome_repo, broker, _issuer_lease(broker), dispatch_id="")
        assert exc.value.code == "schema-field-type"
        assert "dispatch" in exc.value.receipt()["unsupported"]

    def test_attend_offer_permits_empty_dispatch_id(self, outcome_repo: Path, broker: Any) -> None:
        # Pins the guard's operation scope: attend derives a resume pointer and may omit the
        # #351 dispatch identity, so the advance-one requirement must not leak onto it.
        offer, reference = _offer(
            outcome_repo, broker, _issuer_lease(broker), operation="attend", dispatch_id=""
        )
        assert offer["operation"] == "attend"
        assert offer["dispatch_id"] == ""
        assert reference["operation"] == "attend"

    def test_unclosed_source_lease_halts(self, outcome_repo: Path, broker: Any) -> None:
        # A validly sealed offer pointing at a live lease that never went through the
        # settlement close: seal passes, but the head carries no canonical close receipt.
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        live = _issuer_lease(broker, attempt=2)
        path = OC._handoffs_dir(outcome_repo, OUTCOME_ID) / f"{offer['handoff_id']}.offer.json"
        record = json.loads(path.read_text())
        record["lease_id"] = live.lease_id
        record["resource_ref"] = dict(live.resource_ref)
        record["token"] = {
            "broker_epoch": live.token.broker_epoch,
            "fencing_sequence": live.token.fencing_sequence,
        }
        del record["sha256"]
        path.write_text(OC.canonical_json(OC._seal(record)) + "\n", encoding="utf-8")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, broker, offer["handoff_id"])
        assert exc.value.code == "handoff-source-not-closed"

    def test_wrong_repository_halts(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        _git(outcome_repo, "remote", "set-url", "origin", "https://github.com/other/repo.git")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, broker, offer["handoff_id"])
        assert exc.value.code == "handoff-wrong-repository"

    def test_wrong_revision_halts(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        spec_file = outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        spec_file.write_text(json.dumps(_spec_dict(revision=4), indent=1), encoding="utf-8")
        _git(outcome_repo, "commit", "-aqm", "supersede revision")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, broker, offer["handoff_id"])
        assert exc.value.code == "handoff-wrong-revision"

    def test_wrong_operation_and_subplot_halt(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        with pytest.raises(OC.CompatibilityHaltError) as wrong_op:
            _accept(outcome_repo, broker, offer["handoff_id"], operation="attend")
        assert wrong_op.value.code == "handoff-wrong-operation"
        with pytest.raises(OC.CompatibilityHaltError) as wrong_sub:
            _accept(outcome_repo, broker, offer["handoff_id"], subplot_id="sub-9")
        assert wrong_sub.value.code == "handoff-wrong-subplot"

    def test_already_settled_dispatch_halts(self, outcome_repo: Path, broker: Any) -> None:
        offer, _ = _offer(outcome_repo, broker, _issuer_lease(broker))
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(
                outcome_repo,
                broker,
                offer["handoff_id"],
                settled_lookup=lambda _d, _u, _a: True,
            )
        assert exc.value.code == "handoff-already-settled"

    def test_dirty_working_tree_blocks_offer(self, outcome_repo: Path, broker: Any) -> None:
        spec_file = outcome_repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
        spec_file.write_text(json.dumps(_spec_dict(revision=42), indent=1), encoding="utf-8")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _offer(outcome_repo, broker, _issuer_lease(broker))
        assert exc.value.code == "working-tree-divergent"

    def test_released_issuer_lease_cannot_offer(self, outcome_repo: Path, broker: Any) -> None:
        lease = _issuer_lease(broker)
        broker.release(lease.lease_id, token=lease.token, owner_id=lease.owner_id)
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _offer(outcome_repo, broker, lease)
        assert exc.value.code == "handoff-issuer-not-current"

    def test_missing_offer_record_halts(self, outcome_repo: Path, broker: Any) -> None:
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            _accept(outcome_repo, broker, "0" * 32)
        assert exc.value.code == "handoff-missing"

    def test_offer_closes_the_issuer_lease_with_a_receipt(
        self, outcome_repo: Path, broker: Any
    ) -> None:
        lease = _issuer_lease(broker)
        offer, _ = _offer(outcome_repo, broker, lease)
        head = broker.inspect_resource_head(offer["resource_ref"])
        assert head is not None
        assert head["close_receipt"] is not None
        state = broker.classify_token(offer["resource_ref"], lease.token)
        assert state == "closed"


# ---------------------------------------------------------------------------
# CLI verbs + attached advance (R5/R7/R11, U4)
# ---------------------------------------------------------------------------

OUTCOME_CLI = SCRIPTS / "outcome.py"


def _load_outcome_module() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("outcome", OUTCOME_CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["outcome"] = module
    spec.loader.exec_module(module)
    return module


OCLI = _load_outcome_module()


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OUTCOME_CLI), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _single_node_repo(tmp_path: Path, *, depends_on: list[str] | None = None) -> Path:
    repo = tmp_path / "single"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    spec = _spec_dict()
    node = _node(SUBPLOT, backend="inline")
    if depends_on:
        node["depends_on"] = list(depends_on)
        spec["nodes"] = [_node(dep, backend="inline") for dep in depends_on] + [node]
    else:
        spec["nodes"] = [node]
    spec_file = repo / "docs" / "outcomes" / OUTCOME_ID / "outcome-spec.json"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text(json.dumps(spec, indent=1), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed single-node spec")
    _git(repo, "remote", "add", "origin", ORIGIN_HTTPS)
    return repo


class TestCliVerbs:
    def test_cli_discover_emits_a_valid_envelope(self, outcome_repo: Path) -> None:
        result = _cli(outcome_repo, "discover", OUTCOME_ID)
        assert result.returncode == 0, result.stderr
        envelope = OC.parse_discovery_envelope(result.stdout)
        assert envelope["outcome"]["id"] == OUTCOME_ID

    def test_cli_discover_halts_with_receipt_and_exit_3(self, outcome_repo: Path) -> None:
        _git(outcome_repo, "remote", "remove", "origin")
        result = _cli(outcome_repo, "discover", OUTCOME_ID)
        assert result.returncode == 3
        receipt = OC.validate_halt_receipt(json.loads(result.stdout))
        assert receipt["code"] == "repo-identity-missing-origin"

    def test_cli_attach_readonly_emits_canonical_status(self, tmp_path: Path) -> None:
        repo = _single_node_repo(tmp_path)
        result = _cli(repo, "attach", OUTCOME_ID)
        assert result.returncode == 0, result.stderr
        status = OC.validate_canonical_status(json.loads(result.stdout))
        assert status["mutation_allowed"] is False

    def test_cli_handoff_emits_a_public_reference(self, outcome_repo: Path, tmp_path: Path) -> None:
        broker_root = tmp_path / "cli-broker"
        broker_root.mkdir(mode=0o700)
        result = _cli(
            outcome_repo,
            "handoff",
            OUTCOME_ID,
            SUBPLOT,
            "--operation",
            "advance-one",
            "--dispatch-id",
            "outcome:cli:frontier:demo",
            "--session-id",
            "sess-cli",
            "--policy-sha256",
            "c" * 64,
            "--session-limit",
            "2",
            "--aggregate-limit",
            "4",
            "--broker-root",
            str(broker_root),
        )
        assert result.returncode == 0, result.stderr
        reference = OC.validate_handoff_reference(json.loads(result.stdout))
        assert reference["operation"] == "advance-one"

    def test_cli_handoff_broker_rejection_is_structured(
        self, outcome_repo: Path, tmp_path: Path
    ) -> None:
        # An ordinary broker rejection (capacity, policy, registry) is an operational error,
        # not a compatibility halt: exit 1 with the standard structured stderr line, never a
        # bare traceback.
        broker_root = tmp_path / "cli-broker-full"
        broker_root.mkdir(mode=0o700)
        seed = LB.LeaseBroker(broker_root)
        seed.acquire_agent(
            owner_id="seed-occupant",
            session_id="sess-cli",
            policy_sha256="c" * 64,
            session_limit=1,
            aggregate_limit=4,
            mutation="read-write",
            resource_ref=OC.outcome_dispatch_resource(IDENTITY, OUTCOME_ID, SUBPLOT, 7),
        )
        result = _cli(
            outcome_repo,
            "handoff",
            OUTCOME_ID,
            SUBPLOT,
            "--operation",
            "advance-one",
            "--dispatch-id",
            "outcome:cli:frontier:demo",
            "--session-id",
            "sess-cli",
            "--policy-sha256",
            "c" * 64,
            "--session-limit",
            "1",
            "--aggregate-limit",
            "4",
            "--broker-root",
            str(broker_root),
        )
        assert result.returncode == 1
        assert result.stdout == ""
        assert "Traceback" not in result.stderr
        err = json.loads(result.stderr)
        assert err["ok"] is False
        assert "CapacityExhaustedError" in err["error"]

    def test_cli_attach_advance_requires_handoff_flags(self, outcome_repo: Path) -> None:
        result = _cli(outcome_repo, "attach", OUTCOME_ID, "--advance")
        assert result.returncode == 1
        assert "requires --handoff-id and --subplot" in result.stderr

    def test_cli_attach_advance_and_attend_are_mutually_exclusive(self, outcome_repo: Path) -> None:
        result = _cli(outcome_repo, "attach", OUTCOME_ID, "--advance", "--attend")
        assert result.returncode == 2
        assert "not allowed with" in result.stderr


class TestAttachedAdvance:
    def test_attached_advance_dispatches_exactly_the_offered_subplot(
        self, tmp_path: Path, broker: Any
    ) -> None:
        repo = _single_node_repo(tmp_path)
        lease = _issuer_lease(broker)
        offer, _ = _offer(repo, broker, lease)
        result = OCLI.attached_advance(
            repo,
            OUTCOME_ID,
            SUBPLOT,
            handoff_id=offer["handoff_id"],
            receiver_owner_id="receiver-codex",
            admission=dict(ADMISSION),
            broker=broker,
        )
        assert result["advance"]["dispatched"] == [SUBPLOT]
        assert result["subplot_id"] == SUBPLOT

    def test_replayed_attached_advance_never_double_dispatches(
        self, tmp_path: Path, broker: Any
    ) -> None:
        repo = _single_node_repo(tmp_path)
        offer, _ = _offer(repo, broker, _issuer_lease(broker))
        first = OCLI.attached_advance(
            repo,
            OUTCOME_ID,
            SUBPLOT,
            handoff_id=offer["handoff_id"],
            receiver_owner_id="receiver-codex",
            admission=dict(ADMISSION),
            broker=broker,
        )
        assert first["advance"]["dispatched"] == [SUBPLOT]
        replay = OCLI.attached_advance(
            repo,
            OUTCOME_ID,
            SUBPLOT,
            handoff_id=offer["handoff_id"],
            receiver_owner_id="receiver-codex",
            admission=dict(ADMISSION),
            broker=broker,
        )
        assert replay["advance"]["dispatched"] == []  # settled dispatch record dedups (R7)

    def test_frontier_change_halts_rather_than_broadening(
        self, tmp_path: Path, broker: Any
    ) -> None:
        repo = _single_node_repo(tmp_path, depends_on=["sub-dep"])
        offer, _ = _offer(repo, broker, _issuer_lease(broker))
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OCLI.attached_advance(
                repo,
                OUTCOME_ID,
                SUBPLOT,
                handoff_id=offer["handoff_id"],
                receiver_owner_id="receiver-codex",
                admission=dict(ADMISSION),
                broker=broker,
            )
        assert exc.value.code == "handoff-frontier-changed"

    def test_two_receivers_race_one_successor(self, tmp_path: Path, broker: Any) -> None:
        import threading

        repo = _single_node_repo(tmp_path)
        offer, _ = _offer(repo, broker, _issuer_lease(broker))
        barrier = threading.Barrier(2)
        outcomes: dict[str, Any] = {}

        def contend(receiver: str) -> None:
            barrier.wait()
            try:
                outcomes[receiver] = _accept(
                    repo, broker, offer["handoff_id"], receiver_owner_id=receiver
                )
            except OC.CompatibilityHaltError as halt:
                outcomes[receiver] = halt

        threads = [
            threading.Thread(target=contend, args=(name,))
            for name in ("receiver-one", "receiver-two")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        wins = [value for value in outcomes.values() if isinstance(value, dict)]
        halts = [
            value for value in outcomes.values() if isinstance(value, OC.CompatibilityHaltError)
        ]
        assert len(wins) == 1 and len(halts) == 1
        assert halts[0].code in ("handoff-receiver-conflict", "handoff-superseded")
        winner = wins[0]["lease"]
        commit_path = OC._handoffs_dir(repo, OUTCOME_ID) / f"{offer['handoff_id']}.commit.json"
        committed = json.loads(commit_path.read_text())
        assert committed["successor_lease_id"] == winner.lease_id


# ---------------------------------------------------------------------------
# Golden fixtures + legacy export alias (R9/R10/R11, U5)
# ---------------------------------------------------------------------------

FIXTURES = ROOT / "tests" / "fixtures" / "outcome-cross-runtime" / "v1"


class TestGoldenFixtures:
    @pytest.mark.parametrize(
        ("name", "validator"),
        [
            ("discovery-envelope.json", "validate_discovery_envelope"),
            ("canonical-status.json", "validate_canonical_status"),
            ("handoff-reference.json", "validate_handoff_reference"),
            ("compatibility-halt.json", "validate_halt_receipt"),
        ],
    )
    def test_fixture_round_trips_byte_identically(self, name: str, validator: str) -> None:
        raw = (FIXTURES / name).read_text(encoding="utf-8")
        parsed = OC.parse_strict_json(raw, what=name)
        validated = getattr(OC, validator)(parsed)
        assert OC.canonical_json(validated) + "\n" == raw

    def test_unknown_field_fixture_halts(self) -> None:
        raw = (FIXTURES / "invalid" / "unknown-field-envelope.json").read_text(encoding="utf-8")
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.validate_discovery_envelope(OC.parse_strict_json(raw, what="fixture"))
        assert exc.value.code == "schema-field-unknown"

    def test_future_protocol_fixture_halts(self) -> None:
        raw = (FIXTURES / "invalid" / "future-protocol-envelope.json").read_text(encoding="utf-8")
        doc = OC.parse_strict_json(raw, what="fixture")
        OC.validate_discovery_envelope(doc)  # structurally valid...
        with pytest.raises(OC.CompatibilityHaltError) as exc:
            OC.negotiate(doc["protocol"])  # ...but unsupported at negotiation (R9)
        assert exc.value.code == "protocol-version-skew"

    def test_fixtures_carry_no_local_paths(self) -> None:
        for path in sorted(FIXTURES.glob("*.json")):
            text = path.read_text(encoding="utf-8")
            assert "/Users/" not in text and "/home/" not in text and "/tmp/" not in text


class TestLegacyExportAlias:
    def test_cli_export_is_a_byte_identical_discover_alias(self, outcome_repo: Path) -> None:
        discover = _cli(outcome_repo, "discover", OUTCOME_ID)
        export = _cli(outcome_repo, "export", OUTCOME_ID)
        assert discover.returncode == 0 and export.returncode == 0
        assert export.stdout == discover.stdout  # same outcome.discovery.v1 bytes (R10)
        assert "deprecated alias" in export.stderr
        assert "outcome-bundle/1" not in export.stdout

    def test_cli_import_refuses_bundles_without_writes(
        self, outcome_repo: Path, tmp_path: Path
    ) -> None:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(
            json.dumps({"schema": "outcome-bundle/1", "spec": {"outcome_id": OUTCOME_ID}}),
            encoding="utf-8",
        )
        result = _cli(outcome_repo, "import", str(bundle_path))
        assert result.returncode == 1
        assert "retired" in result.stderr and "discover" in result.stderr
        assert _store_namespace_absent(outcome_repo)
