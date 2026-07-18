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
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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
