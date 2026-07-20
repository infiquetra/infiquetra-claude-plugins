"""Cross-runtime Outcome acceptance harness — U1 pinning, identity, and evidence (#605).

The harness's real-runtime scenario matrix runs via
``tools/run_cross_runtime_outcome_acceptance.py`` against pinned checkouts; this suite proves
the harness machinery itself hermetically: pin refusal, isolated install/readback, contract
digests, the closed evidence schema, the privacy boundary, and atomic output.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import cast

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_cross_runtime_outcome_acceptance.py"
SCHEMA_PATH = (
    ROOT / "docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.schema.json"
)


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("xr_acceptance", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["xr_acceptance"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return _load_tool()


@pytest.fixture(scope="module")
def schema() -> dict:
    return cast(dict, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- fixture repos


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(repo),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@invalid.example",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@invalid.example",
        },
    )


_COMPAT_STUB = '"""stub compat."""\nRUNTIME_LABEL = "{label}"\nPROTOCOL_VERSION = 1\n'

_OUTCOME_STUB = (
    "import argparse\n"
    "p = argparse.ArgumentParser()\n"
    'p.add_argument("--repo-root")\n'
    "p.parse_known_args()\n"
)


def _mini_runtime_repo(base: Path, *, label: str, manifest_dir: str) -> Path:
    """A minimal pinned-checkout shape: plugins/{saga,fleet-core} + manifests + git identity."""
    repo = base / f"repo-{label}"
    for plugin in ("saga", "fleet-core"):
        (repo / "plugins" / plugin / manifest_dir).mkdir(parents=True)
        (repo / "plugins" / plugin / manifest_dir / "plugin.json").write_text(
            json.dumps({"name": plugin, "version": f"1.0.0-{label}"}), encoding="utf-8"
        )
    scripts = repo / "plugins/saga/scripts"
    scripts.mkdir(parents=True)
    (scripts / "outcome_compat.py").write_text(_COMPAT_STUB.format(label=label), encoding="utf-8")
    (scripts / "outcome.py").write_text(_OUTCOME_STUB, encoding="utf-8")
    (repo / "docs/validation").mkdir(parents=True)
    (repo / "docs/validation/saga-family-target-inventory.json").write_text(
        '{"plugins": []}\n', encoding="utf-8"
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pin")
    return repo


def _head(repo: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _pin(tool: ModuleType, repo: Path, *, name: str, manifest_dir: str, sha: str | None = None):
    return tool.RuntimePin(
        name=name,
        repo=repo,
        sha=sha or _head(repo),
        saga_version=f"1.0.0-{name}",
        fleet_core_version=f"1.0.0-{name}",
        manifest_dir=manifest_dir,
    )


# --------------------------------------------------------------------------- R1 pinning


class TestPinning:
    def test_clean_pinned_repo_passes_and_reports_identity(
        self, tool: ModuleType, tmp_path: Path
    ) -> None:
        repo = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        identity = tool.require_clean_pinned(
            _pin(tool, repo, name="claude", manifest_dir=".claude-plugin")
        )
        assert identity["sha"] == _head(repo)
        assert identity["versions"] == {"saga": "1.0.0-claude", "fleet-core": "1.0.0-claude"}

    def test_dirty_checkout_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        repo = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        (repo / "drift.txt").write_text("x", encoding="utf-8")
        with pytest.raises(tool.HarnessError) as exc:
            tool.require_clean_pinned(
                _pin(tool, repo, name="claude", manifest_dir=".claude-plugin")
            )
        assert exc.value.code == "pin-dirty"

    def test_wrong_sha_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        repo = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        with pytest.raises(tool.HarnessError) as exc:
            tool.require_clean_pinned(
                _pin(tool, repo, name="claude", manifest_dir=".claude-plugin", sha="0" * 40)
            )
        assert exc.value.code == "pin-sha"

    def test_version_mismatch_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        repo = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        pin = tool.RuntimePin(
            name="claude",
            repo=repo,
            sha=_head(repo),
            saga_version="9.9.9",
            fleet_core_version="1.0.0-claude",
            manifest_dir=".claude-plugin",
        )
        with pytest.raises(tool.HarnessError) as exc:
            tool.require_clean_pinned(pin)
        assert exc.value.code == "pin-version"


# --------------------------------------------------------------------------- contract digests


class TestContractDigests:
    def test_label_only_divergence_passes(self, tool: ModuleType, tmp_path: Path) -> None:
        claude = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        codex = _mini_runtime_repo(tmp_path, label="codex", manifest_dir=".codex-plugin")
        digests = tool.contract_digests(
            _pin(tool, claude, name="claude", manifest_dir=".claude-plugin"),
            _pin(tool, codex, name="codex", manifest_dir=".codex-plugin"),
        )
        assert set(digests) == {
            "claude_outcome_compat_sha256",
            "codex_outcome_compat_sha256",
            "codex_target_inventory_sha256",
        }
        assert digests["claude_outcome_compat_sha256"] != digests["codex_outcome_compat_sha256"]

    def test_divergence_beyond_label_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        claude = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        codex = _mini_runtime_repo(tmp_path, label="codex", manifest_dir=".codex-plugin")
        compat = codex / "plugins/saga/scripts/outcome_compat.py"
        compat.write_text(compat.read_text(encoding="utf-8") + "DRIFT = 1\n", encoding="utf-8")
        _git(codex, "add", "-A")
        _git(codex, "commit", "-q", "-m", "drift")
        with pytest.raises(tool.HarnessError) as exc:
            tool.contract_digests(
                _pin(tool, claude, name="claude", manifest_dir=".claude-plugin"),
                _pin(tool, codex, name="codex", manifest_dir=".codex-plugin"),
            )
        assert exc.value.code == "port-digest"


# --------------------------------------------------------------------------- isolated install


class TestIsolatedInstall:
    def test_stage_and_readback_identity(self, tool: ModuleType, tmp_path: Path) -> None:
        repo = _mini_runtime_repo(tmp_path, label="codex", manifest_dir=".codex-plugin")
        runtime = tool.install_isolated(
            _pin(tool, repo, name="codex", manifest_dir=".codex-plugin"), tmp_path / "work"
        )
        assert runtime.identity["runtime_label"] == "codex"
        assert runtime.identity["compat_protocol_version"] == 1
        assert runtime.identity["cli_help_ok"] is True
        assert runtime.install_root != repo  # scenarios drive the staged copy, not the checkout
        assert (runtime.install_root / "plugins/saga/scripts/outcome.py").exists()

    def test_wrong_installed_label_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        repo = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        pin = tool.RuntimePin(
            name="codex",  # expects codex label; repo stubs claude
            repo=repo,
            sha=_head(repo),
            saga_version="1.0.0-claude",
            fleet_core_version="1.0.0-claude",
            manifest_dir=".claude-plugin",
        )
        with pytest.raises(tool.HarnessError) as exc:
            tool.install_isolated(pin, tmp_path / "work")
        assert exc.value.code == "install-readback"

    def test_isolated_home_is_hermetic(self, tool: ModuleType, tmp_path: Path) -> None:
        repo = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
        runtime = tool.install_isolated(
            _pin(tool, repo, name="claude", manifest_dir=".claude-plugin"), tmp_path / "work"
        )
        env = runtime.env(fleet_state_dir=tmp_path / "fleet")
        assert env["HOME"] == str(runtime.home)
        assert env["INFIQUETRA_FLEET_STATE_DIR"] == str(tmp_path / "fleet")
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert str(Path.home()) not in env["HOME"]


# --------------------------------------------------------------------------- R10 privacy


class TestPrivacyBoundary:
    def test_rejects_home_and_absolute_paths(self, tool: ModuleType) -> None:
        assert tool.scrub_check({"a": str(Path.home() / "x")})
        assert tool.scrub_check({"a": {"b": ["/Users/someone/secret"]}})
        assert tool.scrub_check({"a": "/private/var/folders/zz/x"})

    def test_rejects_secret_shapes(self, tool: ModuleType) -> None:
        assert tool.scrub_check({"t": "ghp_" + "a" * 24})
        assert tool.scrub_check({"t": "sk-" + "b" * 30})
        assert tool.scrub_check({"t": "AKIA" + "C" * 16})
        assert tool.scrub_check({"t": "Authorization: Bearer abc123def"})

    def test_accepts_digests_versions_and_summaries(self, tool: ModuleType) -> None:
        clean = {
            "sha": "f" * 64,
            "version": "0.78.0+codex.20260720120109",
            "summary": "one effect, one settlement, zero missing dispatch units",
            "count": 3,
            "flag": True,
        }
        assert tool.scrub_check(clean) == []

    def test_assert_privacy_raises_typed_halt(self, tool: ModuleType) -> None:
        with pytest.raises(tool.HarnessError) as exc:
            tool.assert_privacy({"leak": str(Path.home())})
        assert exc.value.code == "evidence-privacy"


# --------------------------------------------------------------------------- evidence bundle


def _sample_bundle(tool: ModuleType, tmp_path: Path) -> dict:
    claude = _mini_runtime_repo(tmp_path, label="claude", manifest_dir=".claude-plugin")
    codex = _mini_runtime_repo(tmp_path, label="codex", manifest_dir=".codex-plugin")
    claude_pin = _pin(tool, claude, name="claude", manifest_dir=".claude-plugin")
    codex_pin = _pin(tool, codex, name="codex", manifest_dir=".codex-plugin")
    return cast(
        dict,
        tool.build_bundle(
            claude=claude_pin,
            codex=codex_pin,
            claude_identity=tool.require_clean_pinned(claude_pin),
            codex_identity=tool.require_clean_pinned(codex_pin),
            digests=tool.contract_digests(claude_pin, codex_pin),
            broker_root_digest="a" * 64,
            scenarios=[
                tool.ScenarioResult(
                    scenario_id="discovery-claude-created",
                    requirement="R3",
                    verdict="pass",
                    summary="codex discovered the claude-created committed spec",
                    facts={"nodes": 2},
                    duration_ms=10,
                )
            ],
            env_names_set=["HOME", "PATH"],
            started_at_iso="2026-07-20T00:00:00Z",
            halt=None,
        ),
    )


class TestEvidenceBundle:
    def test_bundle_validates_against_the_closed_schema(
        self, tool: ModuleType, schema: dict, tmp_path: Path
    ) -> None:
        bundle = _sample_bundle(tool, tmp_path)
        jsonschema.validate(bundle, schema)

    def test_schema_is_closed_at_every_object_level(self, schema: dict) -> None:
        open_objects: list[str] = []

        def walk(node: object, crumb: str) -> None:
            if not isinstance(node, dict):
                return
            if (
                node.get("type") == "object"
                and "additionalProperties" not in node
                and ("maxProperties" not in node)
            ):
                open_objects.append(crumb)
            for key, child in node.items():
                if isinstance(child, dict):
                    walk(child, f"{crumb}.{key}")
                elif isinstance(child, list):
                    for index, item in enumerate(child):
                        walk(item, f"{crumb}.{key}[{index}]")

        walk(schema, "$")
        assert open_objects == [], f"schema objects without a closure bound: {open_objects}"

    def test_unknown_top_level_key_is_rejected(
        self, tool: ModuleType, schema: dict, tmp_path: Path
    ) -> None:
        bundle = _sample_bundle(tool, tmp_path)
        bundle["surprise"] = 1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bundle, schema)

    def test_halt_bundle_still_validates(
        self, tool: ModuleType, schema: dict, tmp_path: Path
    ) -> None:
        bundle = _sample_bundle(tool, tmp_path)
        bundle["halt"] = {"code": "pin-dirty", "detail": "claude: checkout is not clean"}
        bundle["overall_verdict"] = "halt"
        jsonschema.validate(bundle, schema)

    def test_env_section_is_allowlist_bounded(self, tool: ModuleType, tmp_path: Path) -> None:
        bundle = _sample_bundle(tool, tmp_path)
        assert set(bundle["environment_names_set"]) <= set(tool.ENV_NAME_ALLOWLIST)

    def test_overall_verdict_derivation(self, tool: ModuleType, tmp_path: Path) -> None:
        bundle = _sample_bundle(tool, tmp_path)
        assert bundle["overall_verdict"] == "pass"


# --------------------------------------------------------------------------- atomic output


class TestAtomicOutput:
    def test_write_then_hash_round_trip(self, tool: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "out" / "bundle.json"
        payload = {"schema": "x", "n": 1}
        digest = tool.atomic_write_json(target, payload)
        text = target.read_text(encoding="utf-8")
        assert json.loads(text) == payload
        assert digest == tool._sha256_text(text)

    def test_no_tmp_residue_after_write(self, tool: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "bundle.json"
        tool.atomic_write_json(target, {"k": "v"})
        residue = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert residue == []


# --------------------------------------------------------------------------- R2 gh fixture shim


class TestFakeGhShim:
    def _shim(self, tool: ModuleType, tmp_path: Path) -> Path:
        return cast(
            Path,
            tool.write_fake_gh(
                tmp_path / "bin",
                {
                    "pr:11": {"state": "MERGED", "mergedAt": "2026-07-20T00:00:00Z"},
                    "pr:12": {"state": "OPEN", "mergedAt": None},
                    "issue:7": {"state": "CLOSED"},
                },
            ),
        )

    def _gh(self, bin_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(bin_dir / "gh"), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_serves_merged_pr_fields(self, tool: ModuleType, tmp_path: Path) -> None:
        bin_dir = self._shim(tool, tmp_path)
        out = self._gh(
            bin_dir,
            "pr",
            "view",
            "https://github.com/infiquetra/xr-fixture-target/pull/11",
            "--json",
            "state,mergedAt",
        )
        assert out.returncode == 0
        assert json.loads(out.stdout) == {"state": "MERGED", "mergedAt": "2026-07-20T00:00:00Z"}

    def test_serves_open_pr_and_closed_issue(self, tool: ModuleType, tmp_path: Path) -> None:
        bin_dir = self._shim(tool, tmp_path)
        pr = self._gh(bin_dir, "pr", "view", "12", "--json", "state,mergedAt")
        assert json.loads(pr.stdout)["state"] == "OPEN"
        issue = self._gh(bin_dir, "issue", "view", "7", "--json", "state")
        assert json.loads(issue.stdout) == {"state": "CLOSED"}

    def test_absent_fixture_fails_like_gh(self, tool: ModuleType, tmp_path: Path) -> None:
        bin_dir = self._shim(tool, tmp_path)
        out = self._gh(bin_dir, "pr", "view", "99", "--json", "state,mergedAt")
        assert out.returncode == 1
        assert out.stdout == ""

    def test_never_reaches_the_network_vocabulary(self, tool: ModuleType, tmp_path: Path) -> None:
        bin_dir = self._shim(tool, tmp_path)
        out = self._gh(bin_dir, "api", "graphql")
        assert out.returncode == 1
        assert "unsupported" in out.stderr


class TestBoundedRedaction:
    def test_bounded_redacts_home_and_absolute_paths(self, tool: ModuleType) -> None:
        raw = f"failed at {Path.home()}/x and /private/var/folders/zz/thing.py line 3"
        flat = tool._bounded(raw)
        assert "<home>" in flat and "<path>" in flat
        assert tool.scrub_check({"detail": flat}) == []


class TestEffectSpy:
    def test_absent_tree_is_empty(self, tool: ModuleType, tmp_path: Path) -> None:
        assert tool._tree_state(tmp_path / "nope") == {}

    def test_maps_relative_paths_and_detects_byte_changes(
        self, tool: ModuleType, tmp_path: Path
    ) -> None:
        root = tmp_path / "store"
        (root / "oid" / "handoffs").mkdir(parents=True)
        record = root / "oid" / "handoffs" / "aa.offer.json"
        record.write_text("{}\n", encoding="utf-8")
        before = tool._tree_state(root)
        assert list(before) == ["oid/handoffs/aa.offer.json"]
        record.write_text('{"tampered": true}\n', encoding="utf-8")
        after = tool._tree_state(root)
        assert set(after) == set(before)
        assert after != before


class TestStoreDirs:
    def test_detects_the_real_store_namespace(self, tool: ModuleType, tmp_path: Path) -> None:
        # outcome_store.STORE_NAMESPACE is "saga-outcomes"; the U2 clone-B state-free assertion
        # is vacuous unless this helper matches the real namespace.
        clone = tmp_path / "clone"
        (clone / ".git" / "saga-outcomes" / "xr" / "handoffs").mkdir(parents=True)
        assert ".git/saga-outcomes" in tool._store_dirs(clone)

    def test_clean_clone_reports_nothing(self, tool: ModuleType, tmp_path: Path) -> None:
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)
        assert tool._store_dirs(clone) == []


class TestPrivacyGuardBreadth:
    """The R10 guard must catch absolute paths under ANY root, not a fixed denylist."""

    def test_rejects_paths_under_any_root(self, tool: ModuleType) -> None:
        for leak in (
            "/Library/Keychains/login.keychain",
            "/usr/local/secret/token",
            "/nix/store/abc123-pkg",
            "/data/creds/id_rsa",
            # Colon-immediately-prefixed shapes (macOS temp roots in key:value error text)
            # must flag too — URLs stay safe because "//" fails the segment class.
            "tmpdir:/var/folders/ab/xr-acceptance/T/x",
            "wd:/Users/otheruser/proj/key",
        ):
            assert tool.scrub_check({"k": leak}), leak

    def test_accepts_urls_remotes_and_relative_paths(self, tool: ModuleType) -> None:
        clean = {
            "url": "https://github.com/infiquetra/xr-fixture-target",
            "remote": "git@github.com:infiquetra/other.git",
            "ref": "refs/remotes/origin/outcome/xr-u3",
            "rel": "plugins/saga/scripts/outcome.py",
            "ratio": "3 pass / 2 fail",
        }
        assert tool.scrub_check(clean) == []

    def test_bounded_redacts_any_absolute_root(self, tool: ModuleType) -> None:
        flat = tool._bounded("boom at /usr/local/lib/secret.pem here")
        assert "/usr/local" not in flat
        assert "<path>" in flat

    def test_bounded_redacts_colon_prefixed_paths(self, tool: ModuleType) -> None:
        flat = tool._bounded("boom broker-root:/data/creds/id_rsa done")
        assert "/data/creds" not in flat
        assert "<path>" in flat

    def test_rejects_single_segment_absolute_paths(self, tool: ModuleType) -> None:
        # A bare top-level path (/etc, /root) is still an absolute path leak.
        for leak in ("/etc", "/root", "workdir kept at /tmp"):
            assert tool.scrub_check({"k": leak}), leak

    def test_bounded_redacts_single_segment_paths(self, tool: ModuleType) -> None:
        flat = tool._bounded("workdir retained at /tmp for post-mortem")
        assert "/tmp" not in flat
        assert "<path>" in flat

    def test_urls_stay_clean_with_single_segment_matching(self, tool: ModuleType) -> None:
        assert tool.scrub_check({"u": "https://github.com/infiquetra/x"}) == []


class TestVerdictOracles:
    """Hermetic pins for the load-bearing scenario pass/fail helpers."""

    def _proc(
        self, rc: int, stdout: str = "", stderr: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["x"], returncode=rc, stdout=stdout, stderr=stderr)

    def test_expect_refusal_requires_rc_3(self, tool: ModuleType) -> None:
        with pytest.raises(tool.HarnessError) as exc:
            tool._expect_refusal(
                self._proc(1, stdout='{"code": "handoff-missing"}'),
                case="c",
                code="handoff-missing",
            )
        assert exc.value.code == "handoff-negative-rc"

    def test_expect_refusal_requires_exact_code(self, tool: ModuleType) -> None:
        with pytest.raises(tool.HarnessError) as exc:
            tool._expect_refusal(
                self._proc(3, stdout='{"code": "handoff-expired"}'),
                case="c",
                code="handoff-missing",
            )
        assert exc.value.code == "handoff-negative-code"

    def test_expect_refusal_reads_last_stdout_line(self, tool: ModuleType) -> None:
        stdout = 'noise line\n{"code": "handoff-missing", "unsupported": "x"}'
        observed = tool._expect_refusal(
            self._proc(3, stdout=stdout), case="c", code="handoff-missing"
        )
        assert observed == "handoff-missing"

    def test_expect_refusal_pins_the_mechanism_text(self, tool: ModuleType) -> None:
        stdout = (
            '{"code": "handoff-superseded",'
            ' "unsupported": "a handoff whose broker resource head no longer exists"}'
        )
        assert tool._expect_refusal(
            self._proc(3, stdout=stdout),
            case="c",
            code="handoff-superseded",
            unsupported_contains="no longer exists",
        )
        with pytest.raises(tool.HarnessError) as exc:
            tool._expect_refusal(
                self._proc(3, stdout=stdout),
                case="c",
                code="handoff-superseded",
                unsupported_contains="superseded by another authority",
            )
        assert exc.value.code == "handoff-negative-code"

    def test_expect_unchanged_detects_added_and_mutated_files(self, tool: ModuleType) -> None:
        pre = {"store": {"a.json": "1" * 64}}
        tool._expect_unchanged(pre, {"store": {"a.json": "1" * 64}}, case="c")
        with pytest.raises(tool.HarnessError):
            tool._expect_unchanged(pre, {"store": {"a.json": "2" * 64}}, case="c")
        with pytest.raises(tool.HarnessError):
            tool._expect_unchanged(
                pre, {"store": {"a.json": "1" * 64, "b.json": "3" * 64}}, case="c"
            )


class TestChainSummary:
    """The dual-vocabulary dispatch census that decides every U4 verdict."""

    def _legacy(self, phase: str) -> dict[str, str]:
        return {"kind": "dispatch", "phase": phase, "subplot_id": "race-leaf"}

    def _native(self, phase: str, ack_kind: str | None = None) -> dict[str, str]:
        record = {"kind": "outcome.dispatch.v2", "phase": phase, "subplot_id": "race-leaf"}
        if ack_kind:
            record["ack_kind"] = ack_kind
        return record

    def test_double_settlement_counts_two_chains(self, tool: ModuleType) -> None:
        records = [
            self._native("intent"),
            self._native("ack", "launched"),
            self._legacy("intent"),
            self._legacy("commit"),
        ]
        summary = tool._chain_summary(records, "race-leaf")
        assert summary["settled_chains"] == 2
        assert summary["v2_acks"] == 1
        assert summary["legacy_commits"] == 1
        assert summary["ack_kinds"] == ["launched"]

    def test_dangling_native_intent_is_visible(self, tool: ModuleType) -> None:
        records = [self._native("intent"), self._legacy("intent"), self._legacy("commit")]
        summary = tool._chain_summary(records, "race-leaf")
        assert summary["v2_intents"] == 1
        assert summary["v2_acks"] == 0
        assert summary["settled_chains"] == 1

    def test_other_subplots_are_excluded(self, tool: ModuleType) -> None:
        foreign = {"kind": "dispatch", "phase": "commit", "subplot_id": "other-leaf"}
        summary = tool._chain_summary([foreign], "race-leaf")
        assert summary["settled_chains"] == 0
        assert summary["legacy_commits"] == 0


class TestWorkdirRetention:
    """Failed or halted runs must retain the workdir even without --keep-workdir."""

    def _scenario(self, tool: ModuleType, verdict: str) -> object:
        return tool.ScenarioResult(scenario_id="s", requirement="R5", verdict=verdict, summary="x")

    def test_all_pass_without_flag_is_cleaned(self, tool: ModuleType) -> None:
        assert tool._should_keep(False, [self._scenario(tool, "pass")], None) is False

    def test_failing_scenario_always_retains(self, tool: ModuleType) -> None:
        scenarios = [self._scenario(tool, "pass"), self._scenario(tool, "fail")]
        assert tool._should_keep(False, scenarios, None) is True

    def test_halt_and_flag_retain(self, tool: ModuleType) -> None:
        assert tool._should_keep(False, [], {"code": "x", "detail": "y"}) is True
        assert tool._should_keep(True, [], None) is True


class _StubRuntime:
    """Duck-typed stand-in for InstalledRuntime: only .python() is consumed by
    _resolved_broker_digest, so the halt branches are testable hermetically."""

    def __init__(self, resolved: str, rc: int = 0) -> None:
        self._resolved = resolved
        self._rc = rc

    def python(
        self,
        code: str,
        *argv: str,
        repo_root: Path,
        fleet_state_dir: Path,
        path_prefix: Path | None = None,
        timeout: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["stub"],
            returncode=self._rc,
            stdout=json.dumps({"resolved": self._resolved}) + "\n",
            stderr="stub failure" if self._rc else "",
        )


class TestBrokerRootDigest:
    """R2 agreement evidence: the digest must be run-derived and divergence must halt."""

    def test_agreement_yields_workbench_relative_digest(
        self, tool: ModuleType, tmp_path: Path
    ) -> None:
        broker = tmp_path / "broker-root"
        broker.mkdir()
        runtimes = {
            "claude": _StubRuntime(str(broker)),
            "codex": _StubRuntime(str(broker)),
        }
        digest = tool._resolved_broker_digest(runtimes, broker, tmp_path)
        assert digest == tool._sha256_text("broker-root")

    def test_runtime_divergence_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        broker = tmp_path / "broker-root"
        other = tmp_path / "elsewhere"
        broker.mkdir()
        other.mkdir()
        runtimes = {
            "claude": _StubRuntime(str(broker)),
            "codex": _StubRuntime(str(other)),
        }
        with pytest.raises(tool.HarnessError) as exc:
            tool._resolved_broker_digest(runtimes, broker, tmp_path)
        assert exc.value.code == "broker-root-divergence"

    def test_agreed_but_wrong_root_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        broker = tmp_path / "broker-root"
        wrong = tmp_path / "wrong-root"
        broker.mkdir()
        wrong.mkdir()
        runtimes = {
            "claude": _StubRuntime(str(wrong)),
            "codex": _StubRuntime(str(wrong)),
        }
        with pytest.raises(tool.HarnessError) as exc:
            tool._resolved_broker_digest(runtimes, broker, tmp_path)
        assert exc.value.code == "broker-root-divergence"

    def test_probe_failure_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        broker = tmp_path / "broker-root"
        broker.mkdir()
        runtimes = {"claude": _StubRuntime(str(broker), rc=1)}
        with pytest.raises(tool.HarnessError) as exc:
            tool._resolved_broker_digest(runtimes, broker, tmp_path)
        assert exc.value.code == "broker-root-divergence"


class _StubEnvRuntime:
    """Duck-typed stand-in for InstalledRuntime: only .env() and .install_root are consumed
    by _child_env_names, so the env-name-unlisted halt branch is testable hermetically."""

    def __init__(self, names: list[str], install_root: Path) -> None:
        self._names = names
        self.install_root = install_root

    def env(
        self,
        *,
        fleet_state_dir: Path,
        repo_root: Path,
        path_prefix: Path | None = None,
    ) -> dict[str, str]:
        return dict.fromkeys(self._names, "x")


class TestChildEnvNames:
    """R10 attestation: environment_names_set derives from child truth and unlisted halts."""

    def test_names_return_in_allowlist_order(self, tool: ModuleType, tmp_path: Path) -> None:
        runtimes = {
            "claude": _StubEnvRuntime(["PATH", "HOME"], tmp_path),
            "codex": _StubEnvRuntime(["HOME", "GIT_CONFIG_NOSYSTEM"], tmp_path),
        }
        names = tool._child_env_names(runtimes, tmp_path / "broker")
        expected = {"HOME", "PATH", "GIT_CONFIG_NOSYSTEM"}
        assert names == [n for n in tool.ENV_NAME_ALLOWLIST if n in expected]

    def test_unlisted_child_name_halts(self, tool: ModuleType, tmp_path: Path) -> None:
        runtimes = {"claude": _StubEnvRuntime(["HOME", "OPENAI_API_KEY"], tmp_path)}
        with pytest.raises(tool.HarnessError) as exc:
            tool._child_env_names(runtimes, tmp_path / "broker")
        assert exc.value.code == "env-name-unlisted"
        assert "OPENAI_API_KEY" in exc.value.detail

    def test_allowlist_carries_no_dead_entries(self, tool: ModuleType) -> None:
        # Every allowlisted name must be one a child-env builder can actually emit; a
        # dead entry would silently widen what a future builder may set.
        emittable = {
            "HOME",
            "PATH",
            "PWD",
            "INFIQUETRA_FLEET_STATE_DIR",
            "FLEET_COMMONS_ROOT",
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_NOSYSTEM",
        }
        assert set(tool.ENV_NAME_ALLOWLIST) == emittable


class TestPinProbeEnv:
    """R2 hygiene: the pin-verification git probes must run under the curated harness env,
    never the operator's full environment."""

    def test_pin_probes_pass_curated_git_env(
        self, tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        seen: list[dict[str, str] | None] = []

        def fake_run(
            argv: list[str],
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
            timeout: int = 0,
        ) -> subprocess.CompletedProcess[str]:
            seen.append(env)
            return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(tool, "_run", fake_run)
        pin = tool.RuntimePin(
            name="x",
            repo=tmp_path,
            sha="a" * 40,
            saga_version="0",
            fleet_core_version="0",
            manifest_dir=".claude-plugin",
        )
        with pytest.raises(tool.HarnessError):
            tool.require_clean_pinned(pin)
        assert seen and seen[0] is not None
        assert seen[0].get("GIT_CONFIG_NOSYSTEM") == "1"


class TestUnhandledEscapeHalt:
    """An untyped escape (child timeout, malformed child output) must persist an honest
    halt in the bundle — never halt:null over a partial scenario set — and exit 2."""

    def test_non_harness_error_records_halt_and_rc_2(
        self, tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_mkdtemp = tempfile.mkdtemp
        monkeypatch.setattr(
            tool.tempfile,
            "mkdtemp",
            lambda prefix: real_mkdtemp(prefix=prefix, dir=tmp_path),
        )

        def boom(pin: object) -> dict[str, object]:
            raise subprocess.TimeoutExpired(cmd=["git"], timeout=1)

        monkeypatch.setattr(tool, "require_clean_pinned", boom)
        out = tmp_path / "bundle.json"
        rc = tool.main(
            [
                "--claude-repo",
                str(tmp_path),
                "--claude-sha",
                "a" * 40,
                "--claude-saga-version",
                "0",
                "--claude-fleet-core-version",
                "0",
                "--codex-repo",
                str(tmp_path),
                "--codex-sha",
                "b" * 40,
                "--codex-saga-version",
                "0",
                "--codex-fleet-core-version",
                "0",
                "--output",
                str(out),
            ]
        )
        assert rc == 2
        bundle = json.loads(out.read_text(encoding="utf-8"))
        assert bundle["halt"]["code"] == "unhandled-exception"
        assert "TimeoutExpired" in bundle["halt"]["detail"]
