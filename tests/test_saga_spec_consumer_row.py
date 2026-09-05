"""Plan documentation facts bind to the engines; generated regions bind to those facts.

Free prose is deliberately outside this contract. Inline mutations exercise the same
validators as live inputs; inventory and scheduled canaries cover guard removal.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import importlib.util
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from saga_plan_contract import plan_phase_53 as _plan_phase_53

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "saga"
PLAN_SKILL = PLUGIN_ROOT / "skills" / "plan" / "SKILL.md"
SAGA_SPEC = PLUGIN_ROOT / "references" / "saga-spec.md"


def _module(name: str, path: Path) -> ModuleType:
    assert path.is_file(), f"{path.relative_to(ROOT)}: missing engine/validator; restore this file"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, str(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def contract_api() -> ModuleType:
    return _module("p5_plan_save_contract", PLUGIN_ROOT / "scripts/plan_save_contract.py")


def _mutated(contract_api: ModuleType, data: dict[str, Any]) -> Any:
    return contract_api.load(text=yaml.safe_dump(data, sort_keys=False))


def _assert_engine_binding(contract: Any) -> None:
    """Independent real engine boundary; no document or renderer supplies expectations."""
    saga = _module("p5_binding_saga", PLUGIN_ROOT / "scripts/saga.py")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    saga._add_save_parser(sub)
    actions = {action.dest: action for action in sub.choices["save"]._actions}
    fields = {field.name for field in dataclasses.fields(saga.Saga)}
    options = sorted(option for action in actions.values() for option in action.option_strings)
    for section in ("identity", "writes", "stored_without_flag"):
        for index, entry in enumerate(contract.data[section]):
            name = entry["name"]
            context = f"{contract.source}: {section}[{index}] ({name!r})"
            if section != "stored_without_flag":
                flag = "--" + name.replace("_", "-")
                assert name in actions and flag in actions[name].option_strings, (
                    f"{context}: {flag} is not an option of saga.py save; "
                    f"the engine's save options are {options}"
                )
            assert name in fields, f"{context}: not a field of saga.Saga; expected {sorted(fields)}"
            if "value" in entry:
                assert entry["value"] in (actions[name].choices or ()), (
                    f"{context}: value must be in engine choices {actions[name].choices}"
                )
            when = entry.get("when", "always")
            if when != "always":
                assert when["equals"] in (actions[when["field"]].choices or ()), (
                    f"{context}: when.equals must be in engine choices "
                    f"{actions[when['field']].choices}"
                )
    effort = contract.data["effort_honoring"]
    # Check the real path before importing: a cached module cannot hide a moved seam.
    path = ROOT / "plugins/fleet-core/scripts/fleet_commons/effort_rider.py"
    rider = _module("p5_binding_effort_rider", path)
    context = f"{contract.source}: effort_honoring"
    assert effort["seam"] == f"fleet_commons.{path.stem}.{rider.inject_effort.__name__}", (
        f"{context}.seam: expected fleet_commons.effort_rider.inject_effort"
    )
    assert effort["parameters"] == list(inspect.signature(rider.inject_effort).parameters), (
        f"{context}.parameters: does not match inject_effort signature"
    )
    assert set(effort["spawn_kinds"]) == set(rider.SPAWN_KINDS), (
        f"{context}.spawn_kinds: expected {sorted(rider.SPAWN_KINDS)}"
    )
    for kind, mechanism in effort["spawn_kinds"].items():
        for level in rider.EFFORTS:
            prompt = "Plan contract behavioral probe."
            observed = rider.inject_effort(prompt, level, kind)
            expected = (
                prompt if mechanism == "native" else rider.EFFORT_RIDER[level] + "\n\n" + prompt
            )
            assert observed == expected, (
                f"{context}.spawn_kinds ({kind!r}): {mechanism!r} disagrees with "
                f"inject_effort observed behavior for {level!r}"
            )
    reference = ROOT / effort["reference"]
    assert reference.is_file(), f"{context}.reference: missing {effort['reference']}"
    assert "inject_effort" in reference.read_text(), (
        f"{context}.reference: {effort['reference']} must mention inject_effort"
    )


def test_plan_save_contract_loads_and_rejects_malformed_entries(
    contract_api: ModuleType, tmp_path: Path
) -> None:
    contract = contract_api.load()
    for renderer in (contract_api.render_consumer_row, contract_api.render_effort_note):
        assert renderer(contract) == renderer(contract), "rendering must be deterministic"
    for template in contract.data["templates"]:
        assert contract_api.render_template(
            contract, template["id"]
        ) == contract_api.render_template(contract, template["id"]), (
            "template rendering must be deterministic"
        )

    # Each case passes through the shipped loader, including its real YAML boundary.
    malformed = []
    data = copy.deepcopy(contract.data)
    del data["writes"][4]["when"]["equals"]
    malformed.append((data, r"writes\[4\].*deploy_autonomy.*equals"))
    data = copy.deepcopy(contract.data)
    data["writes"][1]["placeholder"] = "<status>"
    malformed.append((data, r"writes\[1\].*phase_status.*exactly one"))
    data = copy.deepcopy(contract.data)
    data["writes"][0]["flag"] = "--lifecycle-phase"
    malformed.append((data, r"writes\[0\].*lifecycle_phase.*unknown keys.*flag"))
    data = copy.deepcopy(contract.data)
    data["writes"][0]["when"] = "sometimes"
    malformed.append((data, r"writes\[0\].*when.*mapping"))
    data = copy.deepcopy(contract.data)
    data["effort_honoring"]["spawn_kinds"]["agent"] = "maybe"
    malformed.append((data, r"effort_honoring.spawn_kinds.*agent.*native or proxy"))
    for section, index in (("writes", 2), ("templates", 0)):
        data = copy.deepcopy(contract.data)
        data[section].append(copy.deepcopy(data[section][index]))
        malformed.append((data, rf"{section}\[\d+\].*duplicate.*{section}\[{index}\]"))
    for schema, diagnostic in (
        ("plan_save_contract.v2", "refused whole"),
        ("bridge_signatures.v1", "not a Plan save contract"),
    ):
        data = copy.deepcopy(contract.data)
        data["schema"] = schema
        malformed.append((data, "schema.*" + diagnostic))
    data = copy.deepcopy(contract.data)
    data["writes"][1]["value"] = "done"
    malformed.append((data, r"writes\[1\].*phase_status.*expected one of"))
    data = copy.deepcopy(contract.data)
    data["writes"][4]["when"]["equals"] = "staging"
    malformed.append((data, r"writes\[4\].*deploy_autonomy.*destination.*expected one of"))
    data = copy.deepcopy(contract.data)
    data["writes"] = []
    malformed.append((data, "writes.*nonempty list"))
    for data, message in malformed:
        with pytest.raises(
            contract_api.ContractError, match="plan-save-contract.yaml:.*" + message
        ):
            _mutated(contract_api, data)
    raw = (ROOT / contract_api.CONTRACT).read_text()
    with pytest.raises(
        contract_api.ContractError, match="plan-save-contract.yaml:.*duplicate key.*schema"
    ):
        contract_api.load(text=raw + "\nschema: plan_save_contract.v1\n")
    missing = tmp_path / "missing-contract.yaml"
    result = subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts/plan_save_contract.py"),
            "--contract",
            str(missing),
            "validate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    outcome = json.loads(result.stdout)
    assert outcome["outcome"] == "invalid" and str(missing) in outcome["error"], outcome


def test_plan_save_contract_binds_to_engine(contract_api: ModuleType) -> None:
    contract = contract_api.load()
    _assert_engine_binding(contract)
    phantom = copy.deepcopy(contract.data)
    phantom["writes"].append({"name": "risk_tier", "placeholder": "low", "when": "always"})
    with pytest.raises(AssertionError, match=r"writes\[10\].*risk_tier.*--risk-tier.*save options"):
        _assert_engine_binding(_mutated(contract_api, phantom))
    for kind in contract.data["effort_honoring"]["spawn_kinds"]:
        data = copy.deepcopy(contract.data)
        kinds = data["effort_honoring"]["spawn_kinds"]
        kinds[kind] = "proxy" if kinds[kind] == "native" else "native"
        with pytest.raises(AssertionError, match=f"spawn_kinds.*{kind}.*inject_effort observed"):
            _assert_engine_binding(_mutated(contract_api, data))


def _assert_operator_rule(
    contract: Any, observations: list[tuple[dict[str, str], dict[str, Any], dict[str, Any]]]
) -> None:
    for entry in contract.data["stored_without_flag"]:
        rule = entry["rule"]
        for flags, prior, tick in observations:
            expected = (
                flags.get(rule["explicit_flag"])
                or flags.get(rule["else_from_flag"])
                or prior.get(entry["name"], "")
            )
            assert tick[entry["name"]] == expected, (
                f"{contract.source}: stored_without_flag ({entry['name']!r}): "
                f"rule disagrees with saved tick for {flags}: expected {expected!r}, "
                f"observed {tick[entry['name']]!r}"
            )


def test_operator_choice_rule_matches_engine(contract_api: ModuleType, tmp_path: Path) -> None:
    observations = []
    cases = [
        {},
        {"orchestration_mode": "team-execution"},
        {
            "orchestration_mode": "inline",
            "orchestration_operator_choice": "team-execution",
            "orchestration_downgrade": "contract test exercises explicit choice precedence",
        },
    ]
    for index, flags in enumerate(cases):
        command = [
            sys.executable,
            str(PLUGIN_ROOT / "scripts/saga.py"),
            "save",
            "--id",
            f"p5-probe-{index}",
        ]
        for name, value in flags.items():
            command += ["--" + name.replace("_", "-"), value]
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        envelope = Path(json.loads(result.stdout)["envelope_path"])
        if not envelope.is_absolute():
            envelope = tmp_path / envelope
        tick = yaml.safe_load(envelope.read_text().split("---", 2)[1])
        observations.append((flags, {}, tick))
    # The rule also describes resume: neither flag preserves the previous stored choice.
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts/saga.py"), "save", "--id", "p5-probe-1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    envelope = Path(json.loads(result.stdout)["envelope_path"])
    if not envelope.is_absolute():
        envelope = tmp_path / envelope
    observations.append(
        ({}, observations[1][2], yaml.safe_load(envelope.read_text().split("---", 2)[1]))
    )
    contract = contract_api.load()
    _assert_operator_rule(contract, observations)
    data = copy.deepcopy(contract.data)
    rule = data["stored_without_flag"][0]["rule"]
    rule["explicit_flag"], rule["else_from_flag"] = rule["else_from_flag"], rule["explicit_flag"]
    with pytest.raises(AssertionError, match="stored_without_flag.*rule disagrees with saved tick"):
        _assert_operator_rule(_mutated(contract_api, data), observations)


def _assert_row(api: ModuleType, contract: Any, spec: str) -> None:
    start, end = api.row_span(spec)
    expected = api.render_consumer_row(contract)
    assert spec[start:end] == expected, (
        f"{api.SPEC}: the /plan consumer row differs from its rendering from {contract.source}. "
        f"{api.REMEDY}\n- {spec[start:end]}\n+ {expected}"
    )


def _assert_regions(api: ModuleType, contract: Any, skill: str, phase_53: str) -> None:
    # Preflight includes unknown/overlapping regions; comparisons below name the specific region.
    api.rendered_documents(contract, skill, SAGA_SPEC.read_text())
    regions = [("EFFORT HONORING NOTE", api.render_effort_note(contract))]
    for template in contract.data["templates"]:
        tid = template["id"]
        regions.append((f"PLAN SAVE TEMPLATE: {tid}", api.template_region(contract, tid)))
        start, end = api.region_span(phase_53, f"PLAN SAVE TEMPLATE: {tid}")
        # Retain line count so the diagnostic names the command's Phase 5.3 line.
        phase_53 = phase_53[:start] + "\n" * phase_53[start:end].count("\n") + phase_53[end:]
    for name, expected in regions:
        start, end = api.region_span(skill, name)
        assert skill[start:end] == expected, (
            f"{api.SKILL}: generated region {name!r} differs from its rendering. {api.REMEDY}\n"
            f"- {skill[start:end]}\n+ {expected}"
        )
    command = re.search(r"saga\.py\s+save", phase_53)
    assert command is None, (
        f"{api.SKILL} Phase 5.3: a saga.py save command appears outside a generated template region "
        f"(line {phase_53[: command.start()].count(chr(10)) + 1 if command else '?'}); "
        "add it to the contract's templates and re-render, or remove it"
    )


def test_saga_spec_plan_consumer_row_matches_contract(contract_api: ModuleType) -> None:
    api = contract_api
    contract = api.load()
    spec = SAGA_SPEC.read_text()
    _assert_row(api, contract, spec)
    assert "`phase_status=complete`" in api.render_consumer_row(contract), (
        f"{api.SPEC}: routing test _spec_plan_write_phase_status requires phase_status=complete"
    )
    start, end = api.row_span(spec)
    row = spec[start:end]
    edited = spec[:start] + row.replace("`adr_refs`, ", "") + spec[end:]
    with pytest.raises(AssertionError, match="saga-spec.md:.*consumer row differs"):
        _assert_row(api, contract, edited)
    for value, count in ((spec[:start] + spec[end:], 0), (spec + "\n" + row, 2)):
        with pytest.raises(api.ContractError, match=f"saga-spec.md:.*row.*found {count} times"):
            _assert_row(api, contract, value)
    # Mutating the INPUT contract catches a renderer that reads the output row back.
    data = copy.deepcopy(contract.data)
    conditioned = next(entry for entry in data["writes"] if isinstance(entry["when"], dict))
    conditioned["when"]["equals"] = "pr"
    with pytest.raises(AssertionError, match="saga-spec.md:.*consumer row differs"):
        _assert_row(api, _mutated(api, data), spec)


def _cli_tree(api: ModuleType, root: Path) -> Path:
    """Only real inputs needed by the edit-time CLI; no mocks or shared-file mutations."""
    paths = [
        api.SKILL,
        api.SPEC,
        api.CONTRACT,
        Path("plugins/saga/scripts/plan_save_contract.py"),
        Path("plugins/saga/scripts/saga.py"),
        Path(api.load().data["effort_honoring"]["reference"]),
    ]
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    return root / "plugins/saga/scripts/plan_save_contract.py"


def test_plan_docs_generated_regions_match_contract(
    contract_api: ModuleType, tmp_path: Path
) -> None:
    api = contract_api
    contract = api.load()
    skill = PLAN_SKILL.read_text()
    section = _plan_phase_53()
    _assert_regions(api, contract, skill, section)
    default = api.render_template(contract, "default")
    block = default.split("```", 2)[1]
    assert "#" not in block and "--deploy-autonomy" not in block, (
        f"{api.SKILL}: default command must not contain a shell comment or conditional flag"
    )
    for old, new, message in (
        ("--adr-refs", "--issue-ref", "PLAN SAVE TEMPLATE: default"),
        ("carries effort on a real control", "silently drops the control", "EFFORT HONORING NOTE"),
    ):
        with pytest.raises(AssertionError, match=message + ".*differs"):
            _assert_regions(api, contract, skill.replace(old, new, 1), section.replace(old, new, 1))
    for stray in (
        "```bash\nsaga.py save --id stray\n```",
        "~~~bash\nsaga.py save --id stray\n~~~",
        "```bash titled example\nsaga.py save --id stray\n```",
        "    saga.py save --id stray",
        "`saga.py save --id stray`",
    ):
        with pytest.raises(AssertionError, match=r"SKILL.md Phase 5.3:.*outside.*line \d+"):
            _assert_regions(api, contract, skill, section + "\n" + stray)
    data = copy.deepcopy(contract.data)
    next(entry for entry in data["writes"] if entry["name"] == "plan_path")["placeholder"] = (
        "docs/plans/changed.md"
    )
    with pytest.raises(AssertionError, match="PLAN SAVE TEMPLATE: default.*differs"):
        _assert_regions(api, _mutated(api, data), skill, section)
    data = copy.deepcopy(contract.data)
    data["effort_honoring"]["spawn_kinds"]["agent"] = "native"
    with pytest.raises(AssertionError, match="EFFORT HONORING NOTE.*differs"):
        _assert_regions(api, _mutated(api, data), skill, section)

    script = _cli_tree(api, tmp_path)
    originals = {path: (tmp_path / path).read_bytes() for path in (api.SKILL, api.SPEC)}
    names = [f"PLAN SAVE TEMPLATE: {entry['id']}" for entry in contract.data["templates"]]
    names.append("EFFORT HONORING NOTE")
    for name in names:
        marker = f"<!-- BEGIN GENERATED {name}"
        for modified, count in (
            (skill.replace(marker, "<!-- MISSING", 1), 0),
            (skill + "\n" + marker + " ", 2),
        ):
            with pytest.raises(api.ContractError, match=re.escape(name) + f".*found {count} times"):
                _assert_regions(api, contract, modified, section)
            (tmp_path / api.SKILL).write_text(modified)
            before = {path: (tmp_path / path).read_bytes() for path in originals}
            result = subprocess.run(
                [sys.executable, str(script), "render", "--write"],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 2, result.stdout + result.stderr
            error = json.loads(result.stdout)["error"]
            assert str(api.SKILL) in error and name in error, error
            assert before == {path: (tmp_path / path).read_bytes() for path in originals}, (
                "render --write must preflight both documents before any write"
            )
    for path, content in originals.items():
        (tmp_path / path).write_bytes(content)
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, str(script), "render", "--write"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0 and json.loads(result.stdout)["changed"] == [], result.stdout
    assert originals == {path: (tmp_path / path).read_bytes() for path in originals}


def _reword_outside(text: str, spans: list[tuple[int, int]]) -> str:
    """Change every ordinary line outside the owned regions, preserving structural lines."""
    lines = []
    offset = 0
    for line in text.splitlines(keepends=True):
        owned = any(start <= offset < end for start, end in spans)
        structural = line.startswith(("#", "|", "```", "~~~", "<!--", "-->"))
        lines.append(
            line
            if owned or structural or not line.strip()
            else "A wording-only editorial revision.\n"
        )
        offset += len(line)
    return "".join(lines)


def test_plan_docs_wording_changes_do_not_fail(contract_api: ModuleType) -> None:
    api = contract_api
    contract = api.load()
    skill = PLAN_SKILL.read_text()
    section = _plan_phase_53()
    spec = SAGA_SPEC.read_text()
    names = [f"PLAN SAVE TEMPLATE: {entry['id']}" for entry in contract.data["templates"]]
    edited_skill = _reword_outside(
        skill, [api.region_span(skill, name) for name in [*names, "EFFORT HONORING NOTE"]]
    )
    edited_section = _reword_outside(section, [api.region_span(section, name) for name in names])
    edited_spec = _reword_outside(spec, [api.row_span(spec)])
    assert skill != edited_skill and section != edited_section and spec != edited_spec, (
        "wording proof must actually alter both documents and Phase 5.3"
    )
    _assert_regions(api, contract, edited_skill, edited_section)
    _assert_row(api, contract, edited_spec)
    # Green is limited to prose: an altered fact in the same copy is still red.
    with pytest.raises(AssertionError, match="saga-spec.md:.*consumer row differs"):
        _assert_row(api, contract, edited_spec.replace("`adr_refs`, ", "", 1))
    with pytest.raises(AssertionError, match="PLAN SAVE TEMPLATE: default.*differs"):
        _assert_regions(
            api, contract, edited_skill.replace("--adr-refs", "--issue-ref", 1), edited_section
        )
