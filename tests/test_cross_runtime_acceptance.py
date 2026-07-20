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
from pathlib import Path
from types import ModuleType

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
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


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
    return tool.build_bundle(
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
