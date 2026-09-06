"""Exercise documentation sinks and refusal envelopes across the real CLI boundary."""

from __future__ import annotations

import copy
import json
import shlex
import shutil
import subprocess
import venv
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from saga_plan_contract import SaveProbe, save_blocks
from test_saga_spec_consumer_row import ROOT, cli, contract_api, mutated, save_tick, tree

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
    with pytest.raises(api.ContractError, match="effort_honoring.*reference"):
        api.load(root=tmp_path, text=yaml.safe_dump(data))
    skill, spec = (ROOT / api.SKILL).read_text(), (ROOT / api.SPEC).read_text()
    begin, end = api.markers("EFFORT HONORING NOTE")
    start, stop = api.region_span(skill, "EFFORT HONORING NOTE")
    nested = skill[:start] + skill[stop:]
    default_end = api.markers("PLAN SAVE EXAMPLES: default")[1]
    nested = nested.replace(default_end, begin + "\n" + end + "\n" + default_end)
    with pytest.raises(api.ContractError, match="generated regions.*overlap"):
        api.rendered_documents(api.load(), nested, spec)

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
    assert "migrate this obsolete carrier" in observed[0]
    assert "matching tool revision" in observed[1]
    assert "migrate" not in observed[1]
    for bad in (raw + "\nextra: " + "x" * 200_000, "[" * 2000 + "]" * 2000):
        (tmp_path / api.CONTRACT).write_text(bad)
        result = cli(api, tmp_path, "validate")
        assert result.returncode == 2 and not result.stderr
        detail = json.loads(result.stdout)
        assert detail["file"] == str(api.CONTRACT) and len(result.stdout) < 1000
        assert "x" * 1000 not in result.stdout
    (tmp_path / api.CONTRACT).write_text(raw)
    for path in (api.SKILL, api.SPEC):
        original = (tmp_path / path).read_bytes()
        (tmp_path / path).write_bytes(b"\xff invalid UTF-8")
        result = cli(api, tmp_path, "render", "--write")
        detail = json.loads(result.stdout)
        assert result.returncode == 2 and detail["code"] == "syntax"
        assert detail["file"] == str(path) and detail["entry"] == "encoding"
        (tmp_path / path).write_bytes(original)
    engine.unlink()
    engine.symlink_to(ROOT / "plugins/saga/scripts/saga.py")
    result = cli(api, tmp_path, "validate")
    detail = json.loads(result.stdout)
    assert result.returncode == 2 and detail["code"] == "engine"
    assert "escapes" in detail["error"]
    engine.unlink()
    engine.write_text(original_engine)
    (tmp_path / api.CONTRACT).unlink()
    result = cli(api, tmp_path, "validate")
    detail = json.loads(result.stdout)
    assert result.returncode == 2 and detail["code"] == "filesystem"
    assert detail["file"] == str(tmp_path / api.CONTRACT) and "restore" in detail["error"]


def test_contract_conflict_recovery(contract_api: ModuleType, tmp_path: Path) -> None:
    """Following the runbook removes the entire conflict before a successful render."""
    api = contract_api
    tree(api, tmp_path)
    path = tmp_path / api.SKILL
    original = path.read_text()
    begin, end = api.region_span(original, "PLAN SAVE EXAMPLES: default")
    region = original[begin:end]
    conflict = "<<<<<<< ours\n" + region + "\n=======\n" + region + "\n>>>>>>> theirs\n"
    path.write_text(original[:begin] + conflict + original[end:])
    result = cli(api, tmp_path, "render", "--write")
    assert result.returncode == 2 and "entire conflict" in json.loads(result.stdout)["error"]
    assert conflict in path.read_text()
    # Resolve the entire hunk to one region; surrounding prose remains byte-identical.
    path.write_text(path.read_text().replace(conflict, region))
    result = cli(api, tmp_path, "render", "--write")
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_text() == original
    result = cli(api, tmp_path, "render", "--check")
    assert result.returncode == 0 and json.loads(result.stdout)["outcome"] == "clean"


def test_contract_save_workspace_is_contained(contract_api: ModuleType, tmp_path: Path) -> None:
    api = contract_api
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    direct = SaveProbe(api, ROOT)

    def forbidden_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("save was reached before rejecting an escaping identity")

    # A deliberately bypassed containment guard must fail without performing the
    # very out-of-workspace write this negative control is designed to prevent.
    direct.engine.save = forbidden_save
    for flags in (
        {"kind": "issue", "id": "../../../../../../escaped"},
        {"id": "../../../../../../escaped"},
        {"kind": "task", "id": "safe", "saga_id": str(outside / "escaped")},
    ):
        with pytest.raises(AssertionError, match="identity escapes its temporary workspace"):
            save_tick(workspace, flags)
        with pytest.raises(AssertionError, match="identity escapes its temporary workspace"):
            direct(workspace, flags)
        assert not (tmp_path / "escaped").exists() and not list(outside.iterdir())
    # Slugified task IDs stay valid; this is path containment, not a text ban.
    tick, _ = save_tick(workspace, {"kind": "task", "id": "area/topic"})
    assert tick["id"] == "area/topic" and tick["saga_id"] == "task-area-topic"
    linked_workspace = tmp_path / "linked"
    linked_workspace.mkdir()
    engine = api.module(ROOT, "plugins/saga/scripts/saga.py", "SAGAS_DIR")
    target = linked_workspace / engine.SAGAS_DIR
    target.parent.mkdir(parents=True)
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(AssertionError, match="identity escapes its temporary workspace"):
        save_tick(linked_workspace, {"kind": "task", "id": "safe"})
    with pytest.raises(AssertionError, match="identity escapes its temporary workspace"):
        direct(linked_workspace, {"kind": "task", "id": "safe"})
    assert not list(outside.iterdir())
    # The edit-time tool must exercise issue IDs even when the example kind is an enum.
    checkout = tmp_path / "checkout"
    tree(api, checkout)
    data = api.load().data
    next(i for i in data["identity"] if i["name"] == "id")["placeholder"] = (
        "../../../../../../escaped"
    )
    (checkout / api.CONTRACT).write_text(yaml.safe_dump(data, sort_keys=False))
    before = {p: (checkout / p).read_bytes() for p in (api.SKILL, api.SPEC)}
    for mode in (("validate",), ("render", "--write")):
        result = cli(api, checkout, *mode)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "identity escapes" in json.loads(result.stdout)["error"]
        assert before == {p: (checkout / p).read_bytes() for p in before}


def test_contract_cli_without_pytest(contract_api: ModuleType, tmp_path: Path) -> None:
    """Offline docs editing uses only Python/PyYAML, including optimized Python."""
    api = contract_api
    checkout = tmp_path / "checkout"
    tree(api, checkout)
    assert not (checkout / "tests").exists()
    environment = tmp_path / "python"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python = environment / "bin/python"
    site = Path(
        subprocess.check_output(
            [str(python), "-I", "-c", 'import sysconfig; print(sysconfig.get_path("purelib"))'],
            text=True,
        ).strip()
    )
    shutil.copytree(Path(yaml.__file__).parent, site / "yaml")
    absent = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            'import importlib.util; import yaml; assert importlib.util.find_spec("pytest") is None',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert absent.returncode == 0, absent.stdout + absent.stderr
    script = checkout / "plugins/saga/scripts/plan_save_contract.py"

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(python), "-I", "-O", str(script), "--root", str(checkout), *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    for args in (("validate",), ("render", "--check"), ("render", "--write")):
        result = run(*args)
        assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
        assert json.loads(result.stdout)["root"] == str(checkout.resolve())
    assert not (checkout / ".claude").exists(), "proof wrote Saga state into the checkout"
    originals = {path: (checkout / path).read_bytes() for path in (api.SKILL, api.SPEC)}
    contract_path = checkout / api.CONTRACT
    raw = contract_path.read_text()
    for old, new in (
        ("name: orchestration_recommended", "name: next_step"),
        ("equals: nonprod-deploy", "equals: pr"),
        ("agent: proxy", "agent: native"),
        ("value: complete", "value: pending"),
    ):
        assert old in raw
        contract_path.write_text(raw.replace(old, new))
        result = run("render", "--write")
        assert result.returncode == 2, result.stdout + result.stderr
        if old == "value: complete":
            detail = json.loads(result.stdout)
            assert detail["file"] == str(api.CONTRACT)
            assert (
                detail["entry"] == "writes / saved examples" and "phase_status" in detail["error"]
            )
        assert originals == {path: (checkout / path).read_bytes() for path in originals}
    contract_path.write_text(raw)
    # Factual sentences are checked independently even if renderer and output agree.
    code = script.read_text()
    for old, new, diagnostic in (
        (
            "effort already rides on real controls",
            "effort never rides on real controls",
            "factual clauses differ",
        ),
        (
            "derived from an explicit mode flag",
            "derived on every save",
            "operator-choice derivation",
        ),
        (
            "python3 plugins/saga/scripts/saga.py save",
            "python3 /tmp/not-the-checkout/saga.py save",
            "canonical saga.py save command",
        ),
    ):
        false = code.replace(old, new)
        assert false != code
        script.write_text(false)
        result = run("render", "--write")
        assert result.returncode == 2 and diagnostic in result.stdout, result.stdout
        assert originals == {path: (checkout / path).read_bytes() for path in originals}
        script.write_text(code)
    result = run("validate")
    assert result.returncode == 0, result.stdout + result.stderr
