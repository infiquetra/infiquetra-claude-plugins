"""Plan facts have three independent boundaries: producer/code, rendered facts, saved ticks.

Inline negative controls fail when a helper is bypassed; inventory outside this file
and scheduled canaries independently protect guard removal. No English classifier.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from saga_plan_contract import plan_phase_53, save_blocks, save_options

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path("plugins/saga/scripts/plan_save_contract.py")


@pytest.fixture
def contract_api() -> ModuleType:
    spec = importlib.util.spec_from_file_location("p5_contract", ROOT / SCRIPT)
    assert spec and spec.loader, f"{SCRIPT}: restore the missing validator"
    api = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = api
    spec.loader.exec_module(api)
    return api


def mutated(api: ModuleType, data: dict[str, Any]) -> Any:
    return api.load(text=yaml.safe_dump(data, sort_keys=False))


def cli(api: ModuleType, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / SCRIPT), "--root", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def tree(api: ModuleType, root: Path) -> None:
    # Copy actual code, including fleet shim dependencies, without copying a .saga directory.
    import shutil

    for folder in ("plugins/saga/scripts", "plugins/fleet-core/scripts"):
        shutil.copytree(ROOT / folder, root / folder, ignore=shutil.ignore_patterns("__pycache__"))
    for path in (
        api.CONTRACT,
        api.SKILL,
        api.SPEC,
        Path(api.load().data["effort_honoring"]["reference"]),
    ):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes((ROOT / path).read_bytes())


def assert_row(api: ModuleType, contract: Any, text: str) -> None:
    start, end = api.row_span(text)
    row = text[start:end]
    # Parse emitted technical facts independently; a renderer dropping a field after
    # re-rendering must fail even if output equals that renderer's own output.
    facts = re.findall(r"`([a-z_]+)(?:=([^`]+))?`(?: \(only when `([^`]+)`\))?", row.split("|")[3])
    expected = [
        (
            i["name"],
            i.get("value", ""),
            "" if i["when"] == "always" else i["when"]["field"] + "=" + i["when"]["equals"],
        )
        for i in contract.data["writes"]
    ]
    assert facts == expected, f"{api.SPEC}: /plan consumer row facts differ: {facts} != {expected}"
    assert row == api.render_consumer_row(contract), (
        f"{api.SPEC}: /plan consumer row rendering differs"
    )


def assert_regions(api: ModuleType, contract: Any, skill: str, spec: str) -> None:
    rendered = api.rendered_documents(contract, skill, spec)
    assert rendered[api.SKILL] == skill, f"{api.SKILL}: generated region differs; render --write"
    blocks = save_blocks(plan_phase_53() if skill == (ROOT / api.SKILL).read_text() else skill)
    assert len(blocks) == len(contract.data["templates"]), (
        f"{api.SKILL}: missing/extra save example"
    )
    ids = re.findall(r"\*\*Example: ([a-z0-9-]+)\*\*", skill)
    assert len(ids) == len(set(ids)) == len(blocks), f"{api.SKILL}: duplicate or missing example ID"
    by_id = dict(zip(ids, blocks, strict=True))
    assert set(by_id) == {t["id"] for t in contract.data["templates"]}
    for template in contract.data["templates"]:
        block = by_id[template["id"]]
        options = save_options(block)
        expected = {}
        for item in contract.data["identity"] + contract.data["writes"]:
            when = item.get("when", "always")
            if when != "always" and template["fixed"].get(when["field"]) != when["equals"]:
                continue
            value = template["fixed"].get(item["name"], item.get("value", item.get("placeholder")))
            # Use the shared quote-aware option reader for individual values as well.
            expected[item["name"]] = save_options("--probe " + value)["probe"]
        assert options == expected, f"{api.SKILL}: template {template['id']} lost or changed flags"
    note_start, note_end = api.region_span(skill, "EFFORT HONORING NOTE")
    note = skill[note_start:note_end]
    assert "tier_resolver.resolve(...).model" in note, f"{api.SKILL}: proposed tier lost model"
    assert "tier_resolver.resolve(...).effort" in note, f"{api.SKILL}: proposed tier lost effort"
    assert "`<model>/<effort>`" in note, f"{api.SKILL}: proposed tier must carry the resolved pair"


def test_plan_save_contract_loads_and_rejects_malformed_entries(contract_api: ModuleType) -> None:
    api = contract_api
    original = api.load().data
    cases: list[tuple[dict[str, Any], str]] = []

    def case(section: str, key: str, value: Any, message: str) -> None:
        data = copy.deepcopy(original)
        data[section][0][key] = value
        cases.append((data, message))

    value: Any
    for value in ([], {}, None, "sometimes"):
        case("writes", "when", value, "when")
    for value in ("", "\x00", "one\ntwo", 3):
        case("identity", "placeholder", value, "placeholder")
    case("writes", "when", {"field": [], "equals": "pr"}, "when")
    case("writes", "when", {"field": "lifecycle_phase", "equals": "plan"}, "another declared")
    case("writes", "when", {"field": "destination", "equals": "staging"}, "destination")
    case("writes", "value", "done", "lifecycle_phase")
    case("writes", "placeholder", "<phase>", "keys")
    case("templates", "fixed", {"no_such_p5_field": "x"}, "unknown field")
    case("templates", "fixed", {"destination": "staging"}, "destination")
    case("templates", "fixed", [], "fixed")
    case("templates", "omit", ["deploy_autonomy"], "keys")
    case("writes", "name", "not an identifier", "identifier")
    case("writes", "name", "help", "save option")
    for section in ("writes", "identity", "templates"):
        for value in (
            [],
            [None],
            [copy.deepcopy(original[section][0]), copy.deepcopy(original[section][0])],
        ):
            data = copy.deepcopy(original)
            data[section] = value
            cases.append((data, section))
    for field, value in [
        ("seam", "missing"),
        ("parameters", ["x"]),
        ("spawn_kinds", {}),
        ("spawn_kinds", {"agent": []}),
        ("reference", "\x00"),
        ("reference", "../outside"),
        ("reference", "missing.md"),
    ]:
        data = copy.deepcopy(original)
        data["effort_honoring"][field] = value
        cases.append((data, "effort_honoring"))
    for schema in ("plan_save_contract.v3", "bridge_signatures.v1", None):
        data = copy.deepcopy(original)
        data["schema"] = schema
        cases.append((data, "schema.*matching tool/schema"))
    for data, diagnostic in cases:
        with pytest.raises(api.ContractError, match="plan-save-contract.yaml:.*" + diagnostic):
            mutated(api, data)
    raw = (ROOT / api.CONTRACT).read_text()
    for suffix, diagnostic in [
        ("\nschema: duplicate\n", "duplicate"),
        ("\nx: &x [*x]\n", "alias"),
        ("\nx: &a [1]\ny: &b [*a, *a]\nz: [*b, *b]\n", "alias"),
    ]:
        with pytest.raises(api.ContractError, match="plan-save-contract.yaml:.*" + diagnostic):
            api.load(text=raw + suffix)


def test_plan_save_contract_binds_to_engine(contract_api: ModuleType, tmp_path: Path) -> None:
    api = contract_api
    original = api.load().data
    tree(api, tmp_path)
    for old, new in [("adr_refs", "p5_impossible_926"), ("orchestration_recommended", "next_step")]:
        data = copy.deepcopy(original)
        next(i for i in data["writes"] if i["name"] == old)["name"] = new
        (tmp_path / api.CONTRACT).write_text(yaml.safe_dump(data, sort_keys=False))
        before = {p: (tmp_path / p).read_bytes() for p in (api.SKILL, api.SPEC)}
        for command in [("validate",), ("render", "--write")]:
            result = cli(api, tmp_path, *command)
            assert result.returncode == 2, result.stdout + result.stderr
            assert "writes" in json.loads(result.stdout)["error"], result.stdout
            assert before == {p: (tmp_path / p).read_bytes() for p in before}
    for name in (
        "kind",
        "destination",
        "deploy_autonomy",
        "orchestration_mode",
        "orchestration_recommended",
    ):
        data = copy.deepcopy(original)
        next(i for i in data["identity"] + data["writes"] if i["name"] == name)["placeholder"] = (
            "<bogus>"
        )
        with pytest.raises(api.ContractError, match=name + ".*placeholder.*engine choices"):
            mutated(api, data)
    for kind in original["effort_honoring"]["spawn_kinds"]:
        data = copy.deepcopy(original)
        mechanisms = data["effort_honoring"]["spawn_kinds"]
        mechanisms[kind] = "proxy" if mechanisms[kind] == "native" else "native"
        with pytest.raises(api.ContractError, match="spawn_kinds.*" + kind):
            mutated(api, data)


def save_tick(
    tmp_path: Path, flags: dict[str, str], *, ok: bool = True
) -> tuple[dict[str, Any], str]:
    args = [sys.executable, str(ROOT / "plugins/saga/scripts/saga.py"), "save"]
    for name, value in flags.items():
        args += ["--" + name.replace("_", "-"), value]
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, check=False)
    if not ok:
        assert result.returncode != 0 and "downgrade" in result.stdout + result.stderr, result
        return {}, result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    path = Path(json.loads(result.stdout)["envelope_path"])
    body = (tmp_path / path).read_text()
    return yaml.safe_load(body.split("---", 2)[1]), body


def test_operator_choice_rule_matches_engine(tmp_path: Path) -> None:
    tick, _ = save_tick(tmp_path, {"id": "fresh"})
    assert tick["orchestration_mode"] == "inline" and tick["orchestration_operator_choice"] == ""
    tick, _ = save_tick(tmp_path, {"id": "resume", "orchestration_mode": "team-execution"})
    assert tick["orchestration_operator_choice"] == "team-execution"
    tick, _ = save_tick(tmp_path, {"id": "resume"})
    assert tick["orchestration_operator_choice"] == "team-execution"
    flags = {
        "id": "override",
        "orchestration_mode": "inline",
        "orchestration_operator_choice": "team-execution",
    }
    save_tick(tmp_path, flags, ok=False)
    tick, _ = save_tick(
        tmp_path, {**flags, "orchestration_downgrade": "explicit operator exception"}
    )
    assert (
        tick["orchestration_operator_choice"] == "team-execution"
        and tick["orchestration_mode"] == "inline"
    )
    note = (ROOT / "plugins/saga/references/plan-save-contract.md").read_text()
    assert "--orchestration-downgrade" in note and "with neither flag" in note


def test_saga_spec_plan_consumer_row_matches_contract(contract_api: ModuleType) -> None:
    api = contract_api
    contract = api.load()
    text = (ROOT / api.SPEC).read_text()
    assert_row(api, contract, text)
    start, end = api.row_span(text)
    # Derive the mutant token from the actual field sequence; no copied row or fixed index.
    name = contract.data["writes"][0]["name"]
    broken = text[:start] + text[start:end].replace(name, "p5_missing_fact", 1) + text[end:]
    assert broken != text
    with pytest.raises(AssertionError, match="consumer row facts differ"):
        assert_row(api, contract, broken)
    for broken in (text[:start] + text[end:], text + "\n" + text[start:end]):
        with pytest.raises(api.ContractError, match="consumer row"):
            assert_row(api, contract, broken)


def test_plan_docs_generated_regions_match_contract(contract_api: ModuleType) -> None:
    api = contract_api
    contract = api.load()
    skill, spec = (ROOT / api.SKILL).read_text(), (ROOT / api.SPEC).read_text()
    assert_regions(api, contract, skill, spec)
    broken = skill.replace("--phase-status complete", "--phase-status pending", 1)
    with pytest.raises(AssertionError, match="generated region differs"):
        assert_regions(api, contract, broken, spec)
    for command in (
        "```bash titled\nsaga.py save --id stray\n```",
        "~~~bash\nsaga.py save --id stray\n~~~",
        "    saga.py save --id stray",
        "`saga.py save --id stray`",
    ):
        with pytest.raises(api.ContractError, match="outside generated regions"):
            assert_regions(api, contract, skill + "\n### Later section\n" + command, spec)
    # Renderer must consume new inputs, never derive them from the output document.
    data = copy.deepcopy(contract.data)
    next(i for i in data["writes"] if i["name"] == "plan_path")["placeholder"] = (
        "docs/plans/revised.md"
    )
    revised = mutated(api, data)
    hash_data = copy.deepcopy(contract.data)
    next(i for i in hash_data["writes"] if i["name"] == "decisions")["placeholder"] = (
        "'repair #926'"
    )
    hashed = api.render_template(mutated(api, hash_data), contract.data["templates"][0]["id"])
    parsed = save_options(save_blocks(hashed)[0])
    assert parsed["decisions"] == ["repair #926"] and "orchestration_recommended" in parsed
    output = api.rendered_documents(revised, skill, spec)[api.SKILL]
    assert "docs/plans/revised.md" in output and output != skill


def test_plan_docs_wording_changes_do_not_fail(contract_api: ModuleType) -> None:
    api = contract_api
    contract = api.load()
    skill, spec = (ROOT / api.SKILL).read_text(), (ROOT / api.SPEC).read_text()
    revised = skill.replace("Emit a **runnable** saga", "Produce an **executable** saga")
    revised_spec = spec.replace("Each command below implements", "Every listed command implements")
    assert revised != skill and revised_spec != spec
    assert_regions(api, contract, revised, revised_spec)
    assert_row(api, contract, revised_spec)
    heading = next(line[3:] for line in spec.splitlines() if line.startswith("## 11. "))
    anchor = re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
    for source in ("plugins/saga/docs/commands.md", "plugins/saga/docs/model/saga-docs-model.yaml"):
        path = ROOT / source
        match = re.search(
            r"\[/plan consumer row in saga-spec §11\]\(([^)#]+)#([^)]*)\)", path.read_text()
        )
        assert match, f"{source}: missing Plan contract pointer"
        assert (path.parent / match[1]).resolve() == (ROOT / api.SPEC).resolve(), source
        assert match[2] == anchor, f"{source}: broken consumer-row anchor"
    runbook = (ROOT / "plugins/saga/references/plan-save-contract.md").read_text()
    for path in re.findall(r"`(plugins/[^`]+\.py)`", runbook):
        assert (ROOT / path).is_file(), f"maintainer runbook: missing {path}"


@pytest.mark.parametrize("destination", ["pr", "nonprod-deploy"])
@pytest.mark.parametrize("backend", ["inline", "cc-workflows-ultracode"])
def test_plan_examples_save_the_intended_tick(
    contract_api: ModuleType, tmp_path: Path, destination: str, backend: str
) -> None:
    api = contract_api
    contract = api.load()
    for template in contract.data["templates"]:
        body = api.render_template(contract, template["id"])
        block = save_blocks(body)[0]
        values = {name: value[0] for name, value in save_options(block).items()}
        # Fill placeholders as a Plan operator would; never add a missing unconditional flag.
        samples = {
            "kind": "task",
            "id": "example-" + template["id"],
            "plan_path": "docs/plans/plan.md",
            "destination": destination,
            "orchestration_mode": backend,
            "orchestration_recommended": "inline",
            "adr_refs": "ADR-0926",
            "decisions": "KTD1: repair #926. --issue-ref is prose.",
            "orchestration_ref": "docs/workflows/spec.json",
        }
        for name in values:
            if name not in template["fixed"] and name in samples:
                values[name] = samples[name]
        # Conditional additions come from emitted bullets, not a duplicate contract.
        for name, _value, field, expected in re.findall(
            r"- `--([a-z-]+) ([^`]+)` only when `--([a-z-]+) ([^`]+)`\.", body
        ):
            if values[field.replace("-", "_")] == expected:
                values[name.replace("-", "_")] = (
                    "auto" if name == "deploy-autonomy" else samples[name.replace("-", "_")]
                )
        tick, text = save_tick(tmp_path, values)
        assert tick["lifecycle_phase"] == "plan" and tick["phase_status"] == "complete"
        assert tick["plan_path"] == samples["plan_path"] and tick["destination"] == destination
        assert (
            tick["adr_refs"] == ["ADR-0926"]
            and samples["decisions"] in text.split("## Decisions", 1)[1]
        )
        assert tick["orchestration_recommended"] == "inline"
        assert (
            tick["orchestration_operator_choice"]
            == tick["orchestration_mode"]
            == template["fixed"].get("orchestration_mode", backend)
        )
        assert tick["deploy_autonomy"] == ("auto" if destination == "nonprod-deploy" else "")
        assert tick["orchestration_ref"] == (
            samples["orchestration_ref"]
            if tick["orchestration_mode"] == "cc-workflows-ultracode"
            else ""
        )


def test_plan_renderer_edit_workflow(contract_api: ModuleType, tmp_path: Path) -> None:
    api = contract_api
    tree(api, tmp_path)
    data = api.load().data
    data["templates"].append({"id": "deploy", "fixed": {"destination": "nonprod-deploy"}})
    (tmp_path / api.CONTRACT).write_text(yaml.safe_dump(data, sort_keys=False))
    result = cli(api, tmp_path, "render", "--check")
    assert result.returncode == 1 and json.loads(result.stdout)["outcome"] == "drift"
    assert "deploy" in json.loads(result.stdout)["diff"]
    result = cli(api, tmp_path, "render", "--write")
    assert result.returncode == 0 and str(api.SKILL) in json.loads(result.stdout)["changed"]
    result = cli(api, tmp_path, "render", "--check")
    assert result.returncode == 0 and json.loads(result.stdout)["outcome"] == "clean"
    result = cli(api, tmp_path, "render", "--write")
    assert result.returncode == 0 and json.loads(result.stdout)["changed"] == []
    assert_regions(
        api,
        api.load(root=tmp_path),
        (tmp_path / api.SKILL).read_text(),
        (tmp_path / api.SPEC).read_text(),
    )
    # Original checkout is not the target even when running an installed/cached script.
    assert "Example: deploy" not in (ROOT / api.SKILL).read_text()


def test_plan_renderer_refusals_and_rollback(
    contract_api: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = contract_api
    tree(api, tmp_path)
    originals = {p: (tmp_path / p).read_text() for p in (api.SKILL, api.SPEC)}
    for path, name in (
        (api.SKILL, "PLAN SAVE EXAMPLES: default"),
        (api.SKILL, "EFFORT HONORING NOTE"),
    ):
        marker = api.markers(name)[0]
        for text in (
            originals[path].replace(marker, "<!-- MISSING -->"),
            originals[path] + "\n" + marker,
        ):
            (tmp_path / path).write_text(text)
            result = cli(api, tmp_path, "render", "--write")
            assert result.returncode == 2 and name in json.loads(result.stdout)["error"]
            assert (tmp_path / api.SPEC).read_text() == originals[api.SPEC]
        (tmp_path / path).write_text(originals[path])
    for args in [
        (),
        ("render",),
        ("render", "--check", "--write"),
        ("--contract", "foreign.yaml", "validate"),
    ]:
        result = cli(api, tmp_path, *args)
        assert result.returncode == 2 and json.loads(result.stdout)["outcome"] == "invalid"
    # Invalid schema and missing/renamed Python interfaces have a JSON refusal, never a traceback.
    raw = (tmp_path / api.CONTRACT).read_text()
    for schema, code in [
        ("plan_save_contract.v99", "schema_version"),
        ("unrelated.v1", "schema_family"),
    ]:
        (tmp_path / api.CONTRACT).write_text(raw.replace(api.SCHEMA, schema))
        result = cli(api, tmp_path, "validate")
        assert result.returncode == 2 and json.loads(result.stdout)["code"] == code
    (tmp_path / api.CONTRACT).write_text(raw)
    engine = tmp_path / "plugins/saga/scripts/saga.py"
    original_engine = engine.read_text()
    for content in [
        "import p5_module_that_cannot_exist_926",
        original_engine.replace("def _add_save_parser(", "def _removed_save_parser("),
    ]:
        engine.write_text(content)
        result = cli(api, tmp_path, "validate")
        assert result.returncode == 2 and json.loads(result.stdout)["outcome"] == "invalid"
        assert "Traceback" not in result.stderr
    engine.write_text(original_engine)
    # Force actual second-replacement failure after both files were successfully staged.
    replacement = {p: text + "\nchanged\n" for p, text in originals.items()}
    real_replace = api.os.replace

    def fail_second(src: Path, dst: Path) -> None:
        if dst == tmp_path / api.SPEC:
            raise PermissionError("injected second-document replace failure")
        real_replace(src, dst)

    monkeypatch.setattr(api.os, "replace", fail_second)
    with pytest.raises(api.ContractError, match="all changes rolled back"):
        api.write_documents(tmp_path, originals, replacement, list(originals))
    assert originals == {p: (tmp_path / p).read_text() for p in originals}
    assert not list(tmp_path.rglob(".plan-contract-*"))

    # A staging failure happens before either destination is replaced.
    monkeypatch.setattr(api.os, "replace", real_replace)
    real_temp = api.tempfile.NamedTemporaryFile
    calls = 0

    def fail_stage(**kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PermissionError("injected staging failure")
        return real_temp(**kwargs)

    monkeypatch.setattr(api.tempfile, "NamedTemporaryFile", fail_stage)
    with pytest.raises(PermissionError, match="staging failure"):
        api.write_documents(tmp_path, originals, replacement, list(originals))
    assert originals == {p: (tmp_path / p).read_text() for p in originals}
    assert not list(tmp_path.rglob(".plan-contract-*"))
    monkeypatch.setattr(api.tempfile, "NamedTemporaryFile", real_temp)
    # If even rollback is denied, report the retained backup, never claim no changes.
    calls = 0

    def fail_rollback(src: Path, dst: Path) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise PermissionError("injected replacement and rollback failure")
        real_replace(src, dst)

    monkeypatch.setattr(api.os, "replace", fail_rollback)
    with pytest.raises(api.ContractError, match="rollback incomplete") as error:
        api.write_documents(tmp_path, originals, replacement, list(originals))
    backups = list(tmp_path.rglob(".plan-contract-*"))
    assert len(backups) == 1 and str(backups[0]) in str(error.value)
    assert backups[0].read_text() == originals[api.SKILL]
    real_replace(backups[0], tmp_path / api.SKILL)
    assert originals == {p: (tmp_path / p).read_text() for p in originals}
    monkeypatch.setattr(api.os, "replace", real_replace)
    # The callable CLI uses the same result envelope as the subprocess interface.
    assert api.main(["--root", str(tmp_path), "render", "--check"]) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "clean"
