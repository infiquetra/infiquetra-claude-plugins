"""Exercise documentation sinks and refusal envelopes across the real CLI boundary."""

from __future__ import annotations

import copy
import json
import shlex
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from saga_plan_contract import save_blocks
from test_saga_spec_consumer_row import ROOT, cli, contract_api, mutated, tree

__all__ = ["contract_api"]


def test_contract_values_are_shell_data(contract_api: ModuleType, tmp_path: Path) -> None:
    api = contract_api
    original = api.load().data
    marker = tmp_path / "must-not-execute"
    for value in (
        "docs/plans/plan.md #topic",
        "KTD1: repair #926. --issue-ref is text.",
        f"$(touch {marker})",
        f"`touch {marker}`",
        "a 'single' and \"double\" quote; | & > < * ?",
        "ADR-NNNN|ADR-MMMM",
    ):
        data = copy.deepcopy(original)
        next(i for i in data["writes"] if i["name"] == "decisions")["placeholder"] = value
        block = save_blocks(api.render_template(mutated(api, data), "default"))[0]
        prefix = "python3 plugins/saga/scripts/saga.py save"
        assert block.startswith(prefix), "rendered example changed the executable"
        # Only our controlled fixture is interpreted. The function records arguments;
        # it neither selects a documentation-supplied executable nor runs Saga.
        command = "capture() { printf '%s\\0' \"$@\"; };\n" + block.replace(prefix, "capture", 1)
        result = subprocess.run(["bash", "-c", command], capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        args = result.stdout.decode().split("\0")[:-1]
        assert args == shlex.split(block.replace("\\\n", " "))[3:]
        assert args[args.index("--decisions") + 1] == value
        assert "--orchestration-recommended" in args
        assert not marker.exists(), "placeholder executed shell code"


def test_contract_rejects_corrupting_structure(contract_api: ModuleType, tmp_path: Path) -> None:
    api = contract_api
    original = api.load().data
    for value in (api.markers("PLAN SAVE EXAMPLES: default")[1], "<!--", "-->"):
        data = copy.deepcopy(original)
        next(i for i in data["writes"] if i["name"] == "plan_path")["placeholder"] = value
        with pytest.raises(api.ContractError, match="plan_path.*HTML"):
            mutated(api, data)
    data = copy.deepcopy(original)
    data["templates"].append(
        {"id": "contradiction", "fixed": {"destination": "pr", "deploy_autonomy": "auto"}}
    )
    with pytest.raises(api.ContractError, match="contradiction.*condition is false"):
        mutated(api, data)
    data = copy.deepcopy(original)
    moved = next(i for i in data["writes"] if i["name"] == "destination")
    data["writes"].remove(moved)
    moved.pop("when")
    data["identity"].append(moved)
    with pytest.raises(api.ContractError, match="identity.*derive_saga_id"):
        mutated(api, data)
    tree(api, tmp_path)
    reference = "comment --> leak.md"
    (tmp_path / reference).write_text("exists")
    data = copy.deepcopy(original)
    data["effort_honoring"]["reference"] = reference
    with pytest.raises(api.ContractError, match="effort_honoring.reference"):
        api.load(root=tmp_path, text=yaml.safe_dump(data))
    skill, spec = (ROOT / api.SKILL).read_text(), (ROOT / api.SPEC).read_text()
    for delimiter in ("<<<<<<< ours", "=======", ">>>>>>> theirs", "||||||| base"):
        for path in (api.SKILL, api.SPEC):
            with pytest.raises(api.ContractError, match="merge conflict.*entire conflict"):
                api.rendered_documents(
                    api.load(),
                    skill + ("\n" + delimiter if path == api.SKILL else ""),
                    spec + ("\n" + delimiter if path == api.SPEC else ""),
                )


def test_contract_cli_reports_operation_and_checkout(
    contract_api: ModuleType, tmp_path: Path
) -> None:
    api = contract_api
    tree(api, tmp_path)
    for command in (("validate",), ("render", "--check"), ("render", "--write")):
        result = cli(api, tmp_path, *command)
        assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
        assert json.loads(result.stdout)["root"] == str(tmp_path.resolve())
    for args in ((), ("render",), ("--root", "", "validate")):
        result = cli(api, tmp_path, *args)
        detail = json.loads(result.stdout)
        assert result.returncode == 2 and not result.stderr
        assert detail["code"] == "usage" and detail["file"] is None and "--help" in detail["error"]
    engine = tmp_path / "plugins/saga/scripts/saga.py"
    original_engine = engine.read_text()
    for content in (
        "undefined_name",
        "raise RuntimeError('broken import')",
        "raise ValueError('broken import')",
        original_engine.replace("class Saga:", "class RemovedSaga:"),
    ):
        engine.write_text(content)
        result = cli(api, tmp_path, "validate")
        detail = json.loads(result.stdout)
        assert result.returncode == 2 and not result.stderr
        assert detail["code"] == "engine" and detail["file"] == str(engine.relative_to(tmp_path))
        assert "restore" in detail["error"]
    engine.write_text(original_engine)
    raw = (tmp_path / api.CONTRACT).read_text()
    observed = []
    for schema in ("plan_save_contract.v1", "plan_save_contract.v99"):
        (tmp_path / api.CONTRACT).write_text(raw.replace(api.SCHEMA, schema))
        result = cli(api, tmp_path, "validate")
        detail = json.loads(result.stdout)
        assert result.returncode == 2 and detail["code"] == "schema_version"
        assert schema in detail["error"]
        observed.append(detail["error"])
    assert observed[0] != observed[1]
    for bad in (raw + "\nextra: " + "x" * 200_000, "[" * 2000 + "]" * 2000):
        (tmp_path / api.CONTRACT).write_text(bad)
        result = cli(api, tmp_path, "validate")
        assert result.returncode == 2 and not result.stderr
        detail = json.loads(result.stdout)
        assert detail["file"] == str(api.CONTRACT) and len(result.stdout) < 1000
        assert "x" * 1000 not in result.stdout
    (tmp_path / api.CONTRACT).unlink()
    result = cli(api, tmp_path, "validate")
    detail = json.loads(result.stdout)
    assert result.returncode == 2 and detail["code"] == "filesystem"
    assert detail["file"] == str(tmp_path / api.CONTRACT) and "restore" in detail["error"]
