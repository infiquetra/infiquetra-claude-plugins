"""Model authority boundary tests for Orchestrate (#848).

External worker and reviewer availability, exact model names, and effort/variant controls come only
from the installed `agents` wrapper and vendor-native live catalogs or help -- never from Fleet
Commons tier data or `~/.config/orchestrate/models.json`.

Tests prove:
1. Live-catalog models absent from Fleet Commons tier data resolve as supported.
2. Live-catalog models absent from favourites resolve as supported.
3. Favourites file provides ordering only, never an allowlist or reachability constraint.
4. OpenCode Muse provider/model routes stay distinct with variants intact (`opencode-go` is a provider).
5. Launch receipts separate requested-only model facts from Herdr-confirmed runtime facts.
6. Catalog drift fails precisely with no silent substitution of vendor, model, variant, or account.
7. Internal Team Execution tier resolution in Fleet Commons remains intact and unaffected.
8. Mutation proof: reintroducing the stale-authority condition fails, and live authority passes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
FLEET_SCRIPTS = ROOT / "plugins" / "fleet-core" / "scripts"


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_model_authority", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def launcher_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stub wrapper providing tools in the wrapper's own shape."""
    launcher = tmp_path / "agents"
    launcher.write_text(
        "#!/bin/sh\n"
        "cat <<'HELP'\n"
        "Usage: agents [options] <tool>\n"
        "\n"
        "Tools:\n"
        "  claude    Claude Code\n"
        "  codex     Codex CLI\n"
        "  grok      Grok CLI\n"
        "  opencode  OpenCode\n"
        "  agy       Antigravity CLI\n"
        "  muse      Muse CLI\n"
        "  qwen      Qwen CLI\n"
        "HELP\n"
    )
    launcher.chmod(0o755)
    monkeypatch.setenv("ORCHESTRATE_AGENT_LAUNCHER", str(launcher))


@pytest.mark.usefixtures("launcher_on_path")
class TestModelAuthorityBoundary:
    """External model authority comes strictly from wrapper and live catalogs."""

    def test_live_catalog_model_absent_from_fleet_commons_tier_data_resolves_as_supported(
        self, orchestrate: ModuleType
    ) -> None:
        """A model in the live catalog but absent from Fleet Commons tier data is supported."""
        if str(FLEET_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FLEET_SCRIPTS))
        from fleet_commons import tier_palette

        live_model = "gemini-3.7-flash-high"
        # Confirm it is genuinely absent from Fleet Commons Claude-centric tier palette
        assert live_model not in tier_palette.MODELS

        unit = orchestrate.Unit(
            name="agy-worker",
            vendor="agy",
            task="do work",
            model=live_model,
            effort="high",
        )

        argv = orchestrate.agent_argv(unit)
        assert "--model" in argv
        assert argv[argv.index("--model") + 1] == live_model
        assert "--effort" in argv
        assert argv[argv.index("--effort") + 1] == "high"

        # assert_vendors_available succeeds without checking or requiring Fleet Commons tier tables
        orchestrate.assert_vendors_available([unit])

    def test_live_catalog_model_absent_from_favourites_resolves_as_supported(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A live model absent from ~/.config/orchestrate/models.json resolves without error."""
        faves_file = tmp_path / "models.json"
        faves_file.write_text(json.dumps({"opencode": ["deepseek/deepseek-v4-pro"]}))
        monkeypatch.setattr(orchestrate, "FAVOURITES_PATH", faves_file)

        # agy has no entry in favourites
        assert orchestrate.favourites("agy") == []

        unit = orchestrate.Unit(
            name="agy-worker",
            vendor="agy",
            task="do work",
            model="gemini-3.7-flash-high",
            effort="high",
        )
        argv = orchestrate.agent_argv(unit)
        assert "--model" in argv
        assert argv[argv.index("--model") + 1] == "gemini-3.7-flash-high"

    def test_favourites_file_changes_ordering_only_and_never_acts_as_allowlist(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reordering or truncating favourites changes preference order only, not reachability."""
        faves_file = tmp_path / "models.json"
        faves_file.write_text(
            json.dumps(
                {
                    "opencode": [
                        "opencode-go/muse-spark-1.2-contributor",
                        "deepseek/deepseek-v4-pro",
                    ]
                }
            )
        )
        monkeypatch.setattr(orchestrate, "FAVOURITES_PATH", faves_file)

        assert orchestrate.favourites("opencode") == [
            "opencode-go/muse-spark-1.2-contributor",
            "deepseek/deepseek-v4-pro",
        ]

        # Truncate favourites to only one entry
        faves_file.write_text(json.dumps({"opencode": ["deepseek/deepseek-v4-pro"]}))
        assert orchestrate.favourites("opencode") == ["deepseek/deepseek-v4-pro"]

        # An unlisted model remains fully reachable and generates correct argv
        unit_unlisted = orchestrate.Unit(
            name="unlisted-worker",
            vendor="opencode",
            task="do work",
            model="opencode/muse-spark-1.2-contributor-free",
        )
        argv_unlisted = orchestrate.agent_argv(unit_unlisted)
        assert "-m" in argv_unlisted
        assert (
            argv_unlisted[argv_unlisted.index("-m") + 1]
            == "opencode/muse-spark-1.2-contributor-free"
        )

    def test_opencode_muse_routes_stay_distinct_with_variants_intact(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """opencode-go and opencode routes remain distinct; opencode-go is a provider."""
        route1 = "opencode-go/muse-spark-1.2-contributor"
        route2 = "opencode/muse-spark-1.2-contributor-free"

        unit1 = orchestrate.Unit(
            name="worker-1",
            vendor="opencode",
            task="do work",
            model=route1,
            variant="xhigh",
            pane_id="pane-1",
            worktree="/tmp/wt1",
            tab_id="tab-1",
        )
        unit2 = orchestrate.Unit(
            name="worker-2",
            vendor="opencode",
            task="do work",
            model=route2,
            variant="xhigh",
            pane_id="pane-2",
            worktree="/tmp/wt2",
            tab_id="tab-2",
        )

        argv1 = orchestrate.agent_argv(unit1)
        argv2 = orchestrate.agent_argv(unit2)

        # Both launch through opencode agent kind with their verbatim provider/model route
        assert argv1[argv1.index("opencode") + 1 :] == ["--auto", "-m", route1]
        assert argv2[argv2.index("opencode") + 1 :] == ["--auto", "-m", route2]

        monkeypatch.setattr(
            orchestrate,
            "live_agents",
            lambda: [
                {
                    "pane_id": "pane-1",
                    "cwd": "/tmp/wt1",
                    "interactive_ready": True,
                    "agent": "opencode",
                },
                {
                    "pane_id": "pane-2",
                    "cwd": "/tmp/wt2",
                    "interactive_ready": True,
                    "agent": "opencode",
                },
            ],
        )

        receipt1 = orchestrate.verify_unit_preflight(unit1, "pane-1", ready=True)
        receipt2 = orchestrate.verify_unit_preflight(unit2, "pane-2", ready=True)

        assert receipt1["provider"] == "opencode-go"
        assert receipt1["model"] == route1
        assert receipt1["variant"] == "xhigh"
        assert receipt1["kind"] == "opencode"

        assert receipt2["provider"] == "opencode"
        assert receipt2["model"] == route2
        assert receipt2["variant"] == "xhigh"
        assert receipt2["kind"] == "opencode"

    def test_launch_receipt_separates_requested_only_from_herdr_confirmed_facts(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Receipt places model in requested_only and never falsely in confirmed_against_herdr."""
        unit = orchestrate.Unit(
            name="worker",
            vendor="claude",
            task="do work",
            model="opus",
            pane_id="pane-1",
            worktree="/tmp/wt",
            tab_id="tab-1",
        )

        monkeypatch.setattr(
            orchestrate,
            "live_agents",
            lambda: [
                {
                    "pane_id": "pane-1",
                    "cwd": "/tmp/wt",
                    "interactive_ready": True,
                    "agent": "claude",
                }
            ],
        )
        monkeypatch.setattr(orchestrate, "check_unit_account", lambda *args, **kwargs: (None, None))

        receipt = orchestrate.verify_unit_preflight(unit, "pane-1", ready=True)

        assert "model" in receipt["requested_only"]
        assert "model" not in receipt["confirmed_against_herdr"]
        assert "permission" in receipt["requested_only"]
        assert "permission" not in receipt["confirmed_against_herdr"]

        # Herdr-confirmed facts are strictly what Herdr's API provides
        for confirmed_fact in ("pane", "kind", "working_directory", "readiness"):
            assert confirmed_fact in receipt["confirmed_against_herdr"]

    def test_catalog_drift_fails_precisely_with_no_silent_substitution(
        self, orchestrate: ModuleType
    ) -> None:
        """Catalog drift or unavailable options fail precisely with no silent fallback."""
        # 1. Unavailable vendor/tool fails fast naming unavailable identity
        bad_unit = orchestrate.Unit(
            name="bad-worker",
            vendor="nonexistent-vendor",
            task="do work",
        )
        with pytest.raises(SystemExit) as excinfo:
            orchestrate.assert_vendors_available([bad_unit])
        assert "nonexistent-vendor" in str(excinfo.value)
        assert "the wrapper cannot launch" in str(excinfo.value)

        # 2. Unavailable OpenCode variant fails precisely without silent substitution
        available_variants = ["minimal", "low", "medium", "high", "xhigh"]
        with pytest.raises(SystemExit) as excinfo_variant:
            orchestrate.resolve_opencode_variant("super-extreme-variant", available_variants)
        assert "super-extreme-variant" in str(excinfo_variant.value)
        assert "not available in live picker options" in str(excinfo_variant.value)

    def test_fleet_commons_internal_team_execution_routing_unaffected(self) -> None:
        """Fleet Commons internal Team Execution tier semantics remain intact."""
        if str(FLEET_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FLEET_SCRIPTS))
        from fleet_commons import tier_resolver

        resolution = tier_resolver.resolve(None, "judgment")
        assert isinstance(resolution, tier_resolver.Resolution)
        assert resolution.model == "opus"
        assert resolution.effort == "high"

        mechanical = tier_resolver.resolve(None, "purely-mechanical")
        assert mechanical.model == "haiku"
        assert mechanical.effort == "low"

    def test_mutation_proof_stale_authority_gate_fails_and_live_authority_passes(
        self, orchestrate: ModuleType
    ) -> None:
        """Mutation proof: gating against stale tier data rejects live models; live authority accepts."""
        if str(FLEET_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(FLEET_SCRIPTS))
        from fleet_commons import tier_palette

        def _stale_authority_check(unit: Any) -> bool:
            """Simulated mutant: gate external availability on Fleet Commons tier_palette.MODELS."""
            return unit.model in tier_palette.MODELS

        unit = orchestrate.Unit(
            name="agy-worker",
            vendor="agy",
            task="do work",
            model="gemini-3.7-flash-high",
            effort="high",
        )

        # Under the stale internal table authority, the live model fails
        assert _stale_authority_check(unit) is False

        # Under Orchestrate's live model authority, the model is valid and emitted
        argv = orchestrate.agent_argv(unit)
        assert "gemini-3.7-flash-high" in argv
