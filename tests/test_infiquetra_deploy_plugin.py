"""Contract tests for the infiquetra-deploy plugin package."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "infiquetra-deploy"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_module(script_name: str):
    path = PLUGIN_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter_name(path: Path) -> str:
    lines = _read(path).splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line.startswith("name: "):
            return line.removeprefix("name: ").strip()
    raise AssertionError(f"{path} has no frontmatter name")


def test_infiquetra_deploy_metadata_and_marketplace_entry_match() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "infiquetra-deploy")

    assert plugin_json["name"] == "infiquetra-deploy"
    assert plugin_json["version"] == "0.1.0"
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/infiquetra-deploy"
    assert "tag-promotion" in plugin_json["description"]
    assert {"deploy", "tag-promotion", "rollback", "hotfix"} <= set(plugin_json["keywords"])


def test_infiquetra_deploy_commands_skills_agents_and_scripts_are_packaged() -> None:
    for command in ("deploy", "deploy-status", "deploy-notes", "deploy-hotfix"):
        assert (PLUGIN_ROOT / "commands" / f"{command}.md").exists()

    skill_path = PLUGIN_ROOT / "skills" / "deploy-state" / "SKILL.md"
    assert _frontmatter_name(skill_path) == "deploy-state"
    assert "ADR-0004" in _read(skill_path)

    agent_path = PLUGIN_ROOT / "agents" / "release-orchestrator.md"
    assert _frontmatter_name(agent_path) == "release-orchestrator"

    for script in ("mint_tag.py", "query_deployments.py", "preview_release_notes.py"):
        assert (PLUGIN_ROOT / "scripts" / script).exists()


def test_mint_tag_uses_infiquetra_environments_and_tag_prefixes() -> None:
    mint_tag = _load_module("mint_tag.py")

    assert mint_tag.ENV_TO_PREFIX == {
        "nonprod": "nonprod",
        "staging": "staging",
        "production": "production",
    }
    assert mint_tag.build_tag_name("staging", "1.2.3", rollback=False) == "staging-v1.2.3"
    assert (
        mint_tag.build_tag_name("production", "1.2.3", rollback=True)
        == "rollback-production-v1.2.3"
    )
    assert mint_tag.build_tag_name("production", "1.2.3.1", rollback=False) == "production-v1.2.3.1"


def test_mint_tag_resolves_and_rejects_repository_owners(monkeypatch) -> None:
    mint_tag = _load_module("mint_tag.py")

    assert mint_tag.resolve_repo("campps-service") == "infiquetra/campps-service"
    assert mint_tag.resolve_repo("infiquetra/campps-service") == "infiquetra/campps-service"

    def fake_run(cmd: list[str], *, check: bool = True, capture: bool = True) -> str:
        assert cmd == ["git", "remote", "get-url", "origin"]
        return "git@github.com:other-org/service.git"

    monkeypatch.setattr(mint_tag, "run", fake_run)

    try:
        mint_tag.resolve_repo(None)
    except SystemExit as exc:
        assert "expected github.com/infiquetra/*" in str(exc)
    else:
        raise AssertionError("non-Infiquetra remote should be rejected")


def test_query_deployments_strips_infiquetra_tag_prefixes() -> None:
    query_deployments = _load_module("query_deployments.py")

    assert query_deployments.strip_prefix("v1.2.3") == "1.2.3"
    assert query_deployments.strip_prefix("nonprod-v1.2.3") == "1.2.3"
    assert query_deployments.strip_prefix("staging-v1.2.3") == "1.2.3"
    assert query_deployments.strip_prefix("production-v1.2.3") == "1.2.3"
    assert query_deployments.strip_prefix("rollback-production-v1.2.3") == "1.2.3"


def test_is_tag_ref_accepts_tags_and_rejects_branches() -> None:
    query_deployments = _load_module("query_deployments.py")

    assert query_deployments.is_tag_ref("v0.1.0")
    assert query_deployments.is_tag_ref("nonprod-v1.2.3")
    assert query_deployments.is_tag_ref("staging-v1.2.3")
    assert query_deployments.is_tag_ref("production-v1.2.3")
    assert query_deployments.is_tag_ref("rollback-production-v1.2.3")

    # Branch/SHA refs and loose v-prefixed branch names are rejected.
    assert not query_deployments.is_tag_ref("main")
    assert not query_deployments.is_tag_ref("feature/deploy")
    assert not query_deployments.is_tag_ref("version-bump")
    assert not query_deployments.is_tag_ref("9f8c1de")
    assert not query_deployments.is_tag_ref("")
    assert not query_deployments.is_tag_ref(None)


def test_latest_deployment_issues_get_and_selects_newest_tag_ref(monkeypatch) -> None:
    query_deployments = _load_module("query_deployments.py")

    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], *, check: bool = True) -> str:
        captured["cmd"] = cmd
        # GitHub returns newest-first: a branch-ref CI deployment newer than the real tag.
        return json.dumps(
            [
                {"ref": "main", "sha": "9f8c1de"},
                {"ref": "v0.1.0", "sha": "abc1234"},
            ]
        )

    monkeypatch.setattr(query_deployments, "run", fake_run)

    deployment = query_deployments.latest_deployment("infiquetra/campps-identity-access", "nonprod")

    assert deployment is not None
    assert deployment["ref"] == "v0.1.0"

    # AC6: the gh call must be a GET so the HTTP 422 (POST create) cannot regress.
    cmd = captured["cmd"]
    assert cmd[:2] == ["gh", "api"]
    method_index = cmd.index("--method")
    assert cmd[method_index + 1] == "GET"
    assert "environment=nonprod" in cmd
    assert "per_page=20" in cmd


def test_latest_deployment_returns_none_without_tag_refs(monkeypatch) -> None:
    query_deployments = _load_module("query_deployments.py")

    def fake_run(cmd: list[str], *, check: bool = True) -> str:
        return json.dumps([{"ref": "main"}, {"ref": "dependabot/pip/foo"}])

    monkeypatch.setattr(query_deployments, "run", fake_run)

    assert query_deployments.latest_deployment("infiquetra/x", "nonprod") is None


def test_render_status_reports_and_omits_drift() -> None:
    query_deployments = _load_module("query_deployments.py")

    drifted = query_deployments.render_status(
        "infiquetra/x",
        {
            "nonprod": {"ref": "nonprod-v0.1.1"},
            "staging": {"ref": "staging-v0.1.0"},
            "production": {"ref": "production-v0.1.0"},
        },
    )
    assert "drift:" in drifted
    assert "drift: none detected" not in drifted
    assert "0.1.1" in drifted

    aligned = query_deployments.render_status(
        "infiquetra/x",
        {
            "nonprod": {"ref": "nonprod-v0.1.0"},
            "staging": {"ref": "staging-v0.1.0"},
            "production": {"ref": "production-v0.1.0"},
        },
    )
    assert "drift: none detected" in aligned
