#!/usr/bin/env python3
"""Validate Plan's documentation contract and render its owned regions.

Facts come from plan-save-contract.yaml; rendered documents are outputs only.
validate exits 0/2. render --check exits 0/1 for agreement/drift, 2 for invalid
input or structure. render --write preflights both documents before any write.
No command executes a saga save or changes the saga runtime.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = Path("plugins/saga/references/plan-save-contract.yaml")
SKILL = Path("plugins/saga/skills/plan/SKILL.md")
SPEC = Path("plugins/saga/references/saga-spec.md")
SCHEMA = "plan_save_contract.v1"
REMEDY = (
    "Edit the contract and run `python3 plugins/saga/scripts/plan_save_contract.py "
    "render --write`; do not hand-edit generated regions."
)


class ContractError(ValueError):
    """A complete refusal, naming the source and offending entry."""


@dataclass(frozen=True)
class Contract:
    data: dict[str, Any]
    source: str


def _error(source: str, entry: str, reason: str) -> NoReturn:
    raise ContractError(f"{source}: {entry}: {reason}")


def _mapping(
    value: Any, source: str, entry: str, required: set[str], optional: set[str] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        _error(source, entry, "expected a mapping with string keys")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        _error(
            source,
            entry,
            f"missing keys {sorted(missing)}; unknown keys {sorted(extra)}; expected {sorted(required)}",
        )
    return value


def _string(value: Any, source: str, entry: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(source, entry, "expected a nonempty string")
    return value


def _list(value: Any, source: str, entry: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        _error(source, entry, "expected a nonempty list")
    return value


def _yaml_keys(
    node: yaml.Node, source: str, entry: str = "contract", active: set[int] | None = None
) -> None:
    """Reject duplicate YAML keys before safe_load can silently discard one."""
    active = set() if active is None else active
    if id(node) in active:
        _error(source, entry, "recursive YAML aliases are not contract entries")
    active.add(id(node))
    if isinstance(node, yaml.MappingNode):
        seen: dict[str, int] = {}
        for key, value in node.value:
            if not isinstance(key, yaml.ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                _error(source, entry, "expected string mapping keys")
            if key.value in seen:
                _error(
                    source,
                    entry,
                    f"duplicate key {key.value!r} at lines {seen[key.value]} and {key.start_mark.line + 1}",
                )
            seen[key.value] = key.start_mark.line + 1
            _yaml_keys(value, source, f"{entry}.{key.value}", active)
    elif isinstance(node, yaml.SequenceNode):
        for index, child in enumerate(node.value):
            _yaml_keys(child, source, f"{entry}[{index}]", active)
    active.remove(id(node))


def _save_actions(root: Path, source: str) -> dict[str, argparse.Action]:
    path = root / "plugins/saga/scripts/saga.py"
    if not path.is_file():
        _error(source, "engine", f"missing {path}; restore the saga engine")
    name = "plan_save_contract_saga_engine"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        _error(source, "engine", f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    module._add_save_parser(sub)
    return {action.dest: action for action in sub.choices["save"]._actions}


def _choice(
    actions: dict[str, argparse.Action], name: str, value: Any, source: str, entry: str
) -> None:
    action = actions.get(name)
    choices = None if action is None else action.choices
    if not isinstance(value, str) or choices is None or value not in choices:
        _error(
            source,
            entry,
            f"{value!r} is not a choice of --{name.replace('_', '-')}; expected one of {list(choices or [])}",
        )


def load(path: Path | None = None, *, text: str | None = None, root: Path = ROOT) -> Contract:
    """Read and validate the whole carrier; text permits real in-memory mutation proofs."""
    path = root / CONTRACT if path is None else path
    source = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    try:
        raw = path.read_text(encoding="utf-8") if text is None else text
        node = yaml.compose(raw, Loader=yaml.SafeLoader)
        if node is not None:
            _yaml_keys(node, source)
        data = yaml.safe_load(raw)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        _error(source, "contract", f"cannot read valid YAML: {exc}")
    data = _mapping(
        data,
        source,
        "contract",
        {
            "schema",
            "producer",
            "owner",
            "reads",
            "identity",
            "writes",
            "stored_without_flag",
            "templates",
            "effort_honoring",
        },
    )
    schema = data["schema"]
    if schema != SCHEMA:
        family = isinstance(schema, str) and (
            schema.lower() == "plan_save_contract"
            or schema.lower().startswith("plan_save_contract.")
        )
        _error(
            source,
            "schema",
            f"{schema!r} {'refused whole' if family else 'is not a Plan save contract'}; expected {SCHEMA}",
        )
    for key, expected in (("producer", "/plan"), ("owner", str(SKILL))):
        if data[key] != expected:
            _error(source, key, f"expected {expected!r}")
    _string(data["reads"], source, "reads")
    positions: dict[str, str] = {}
    for section in ("identity", "writes", "stored_without_flag"):
        for index, item in enumerate(_list(data[section], source, section)):
            entry = (
                f"{section}[{index}] ({item.get('name')!r})"
                if isinstance(item, dict)
                else f"{section}[{index}]"
            )
            required = (
                {"name", "placeholder"}
                if section == "identity"
                else {"name", "when"}
                if section == "writes"
                else {"name", "rule"}
            )
            item = _mapping(
                item,
                source,
                entry,
                required,
                {"value", "placeholder", "note"} if section == "writes" else set(),
            )
            name = _string(item["name"], source, entry)
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                _error(source, entry, "name must be a snake_case field identifier")
            if name in positions:
                _error(source, entry, f"duplicate name also at {positions[name]}")
            positions[name] = entry
            if section == "writes" and (("value" in item) == ("placeholder" in item)):
                _error(source, entry, "expected exactly one of value or placeholder")
            for key in ("value", "placeholder", "note"):
                if key in item:
                    _string(item[key], source, f"{entry}.{key}")
            if section == "stored_without_flag":
                rule = _mapping(
                    item["rule"],
                    source,
                    entry + ".rule",
                    {"explicit_flag", "else_from_flag", "else"},
                )
                for key in rule:
                    _string(rule[key], source, entry + ".rule." + key)
                if rule["else"] != "preserve-prior-or-empty":
                    _error(source, entry + ".rule.else", "expected preserve-prior-or-empty")
    actions = _save_actions(root, source)
    writes = {item["name"]: item for item in data["writes"]}
    for item in data["writes"]:
        entry = positions[item["name"]]
        if "value" in item:
            _choice(actions, item["name"], item["value"], source, entry + ".value")
        when = item["when"]
        if when != "always":
            when = _mapping(when, source, entry + ".when", {"field", "equals"})
            field = _string(when["field"], source, entry + ".when.field")
            if field not in writes or field == item["name"]:
                _error(source, entry + ".when.field", "expected another entry in writes")
            _choice(actions, field, when["equals"], source, entry + ".when.equals")
    for item in data["stored_without_flag"]:
        for key in ("explicit_flag", "else_from_flag"):
            name = item["rule"][key]
            if name not in actions:
                _error(
                    source,
                    positions[item["name"]] + ".rule." + key,
                    f"--{name.replace('_', '-')} is not an option of saga.py save",
                )
    ids: dict[str, str] = {}
    conditioned = {name for name, item in writes.items() if item["when"] != "always"}
    for index, item in enumerate(_list(data["templates"], source, "templates")):
        entry = (
            f"templates[{index}] ({item.get('id')!r})"
            if isinstance(item, dict)
            else f"templates[{index}]"
        )
        item = _mapping(item, source, entry, {"id", "fixed", "omit"})
        tid = _string(item["id"], source, entry + ".id")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", tid):
            _error(source, entry, "id must be a kebab-case identifier")
        if tid in ids:
            _error(source, entry, f"duplicate id also at {ids[tid]}")
        ids[tid] = entry
        fixed = item["fixed"]
        if not isinstance(fixed, dict) or any(not isinstance(k, str) for k in fixed):
            _error(source, entry + ".fixed", "expected a mapping of writes to enum choices")
        for name, value in fixed.items():
            if name not in writes:
                _error(source, entry + ".fixed", f"{name!r} is not a write")
            _choice(actions, name, value, source, entry + ".fixed." + name)
        omit = item["omit"]
        if not isinstance(omit, list) or any(not isinstance(n, str) for n in omit):
            _error(source, entry + ".omit", "expected a list of conditioned write names")
        if len(set(omit)) != len(omit) or not set(omit) <= conditioned or set(omit) & fixed.keys():
            _error(source, entry + ".omit", "expected unique conditioned writes, none also fixed")
    effort = _mapping(
        data["effort_honoring"],
        source,
        "effort_honoring",
        {"seam", "parameters", "spawn_kinds", "reference", "notes"},
    )
    _string(effort["seam"], source, "effort_honoring.seam")
    for key in ("parameters", "notes"):
        for index, value in enumerate(_list(effort[key], source, "effort_honoring." + key)):
            _string(value, source, f"effort_honoring.{key}[{index}]")
    kinds = effort["spawn_kinds"]
    if not isinstance(kinds, dict) or not kinds:
        _error(source, "effort_honoring.spawn_kinds", "expected a nonempty mechanism mapping")
    for kind, mechanism in kinds.items():
        _string(kind, source, "effort_honoring.spawn_kinds")
        if mechanism not in ("native", "proxy"):
            _error(source, f"effort_honoring.spawn_kinds ({kind!r})", "expected native or proxy")
    reference = Path(_string(effort["reference"], source, "effort_honoring.reference"))
    if (
        reference.is_absolute()
        or not (root / reference).resolve().is_relative_to(root.resolve())
        or not (root / reference).is_file()
    ):
        _error(
            source,
            "effort_honoring.reference",
            f"expected an existing repo-relative file; got {str(reference)!r}",
        )
    return Contract(data, source)


def _rule_sentence(rule: dict[str, str]) -> str:
    return (
        f"an explicit `--{rule['explicit_flag'].replace('_', '-')}` wins; otherwise an explicitly "
        f"passed `--{rule['else_from_flag'].replace('_', '-')}` fills it; with neither flag, "
        "preserve the prior choice or start empty"
    )


def render_consumer_row(contract: Contract) -> str:
    """Render facts in declared order, without reading any document."""
    data = contract.data
    cells = []
    for item in data["writes"]:
        token = item["name"] + ("=" + item["value"] if "value" in item else "")
        cell = f"`{token}`"
        notes = []
        if item["when"] != "always":
            when = item["when"]
            notes.append(f"only when `{when['field']}={when['equals']}`")
        if item.get("note"):
            notes.append(item["note"])
        if notes:
            cell += " (" + "; ".join(notes) + ")"
        cells.append(cell)
    tail = "; also stored: " + "; ".join(
        f"`{item['name']}` ({_rule_sentence(item['rule'])})" for item in data["stored_without_flag"]
    )
    return f"| **{data['producer']}** | {data['reads']} | {', '.join(cells)}{tail}. |"


def render_template(contract: Contract, template_id: str) -> str:
    """Render one fenced command and its conditional additions."""
    data = contract.data
    template = next((t for t in data["templates"] if t["id"] == template_id), None)
    if template is None:
        _error(contract.source, "templates", f"unknown template id {template_id!r}")
    flags = [f"--{i['name'].replace('_', '-')} {i['placeholder']}" for i in data["identity"]]
    bullets = []
    for item in data["writes"]:
        name = item["name"]
        if name in template["omit"]:
            continue
        value = template["fixed"].get(name, item.get("value", item.get("placeholder")))
        flag = f"--{name.replace('_', '-')} {value}"
        when = item["when"]
        if when != "always":
            fixed = template["fixed"].get(when["field"])
            if fixed is None:
                bullet = (
                    f"- `{flag}` — only when `--{when['field'].replace('_', '-')} {when['equals']}`"
                )
                bullets.append(bullet + ("; " + item["note"] if item.get("note") else ""))
                continue
            if fixed != when["equals"]:
                continue
        flags.append(flag)
    lines = ["```bash", "python3 plugins/saga/scripts/saga.py save \\"]
    lines += ["  " + flag + (" \\" if i < len(flags) - 1 else "") for i, flag in enumerate(flags)]
    lines.append("```")
    if bullets:
        lines += ["", "Add when the condition holds:", *bullets]
    return "\n".join(lines)


def render_effort_note(contract: Contract) -> str:
    """Render the complete HTML comment, including its ownership markers."""
    effort = contract.data["effort_honoring"]
    lines = [
        "<!-- BEGIN GENERATED EFFORT HONORING NOTE "
        "(rendered from references/plan-save-contract.yaml by scripts/plan_save_contract.py — "
        "do not hand-edit; pinned by tests/test_saga_spec_consumer_row.py::test_plan_docs_generated_regions_match_contract)",
        f"The honoring seam is `{effort['seam']}({', '.join(effort['parameters'])})`.",
    ]
    mechanism = {
        "native": "carries effort on a real control",
        "proxy": "prepends an `EFFORT_RIDER` directive, a labeled proxy, because the Agent tool has no per-call effort parameter",
    }
    lines += [f"`{kind}` {mechanism[value]}." for kind, value in effort["spawn_kinds"].items()]
    lines += [
        f"See `{effort['reference']}`.",
        *effort["notes"],
        "END GENERATED EFFORT HONORING NOTE -->",
    ]
    return "\n".join(lines)


def template_region(contract: Contract, template_id: str) -> str:
    return (
        f"<!-- BEGIN GENERATED PLAN SAVE TEMPLATE: {template_id} "
        "(rendered from references/plan-save-contract.yaml by scripts/plan_save_contract.py — "
        "do not hand-edit; a divergence fails "
        "tests/test_saga_spec_consumer_row.py::test_plan_docs_generated_regions_match_contract) -->\n"
        + render_template(contract, template_id)
        + f"\n<!-- END GENERATED PLAN SAVE TEMPLATE: {template_id} -->"
    )


def region_span(text: str, name: str, path: Path = SKILL) -> tuple[int, int]:
    """Locate exactly one complete, ordered pair; never repair ambiguous ownership."""
    begin = f"<!-- BEGIN GENERATED {name}"
    end = f"END GENERATED {name} -->"
    starts = list(re.finditer(re.escape(begin) + r"(?=\s|$)", text))
    ends = list(re.finditer(re.escape(end), text))
    for label, matches in (("begin", starts), ("end", ends)):
        if len(matches) != 1:
            _error(
                str(path),
                f"generated region {name!r}",
                f"{label} found {len(matches)} times; expected exactly once. {REMEDY}",
            )
    start, finish = starts[0].start(), ends[0].end()
    if ends[0].start() <= start:
        _error(str(path), f"generated region {name!r}", f"end precedes begin. {REMEDY}")
    return start, finish


def row_span(text: str) -> tuple[int, int]:
    rows = list(re.finditer(r"^\| \*\*/plan\*\* \|[^\n]*", text, re.MULTILINE))
    if len(rows) != 1:
        _error(
            str(SPEC),
            "/plan consumer row",
            f"found {len(rows)} times; expected exactly once. {REMEDY}",
        )
    return rows[0].span()


def rendered_documents(contract: Contract, skill: str, spec: str) -> dict[Path, str]:
    """Preflight every owned region before returning either document's replacement."""
    replacements = []
    for template in contract.data["templates"]:
        tid = template["id"]
        start, end = region_span(skill, f"PLAN SAVE TEMPLATE: {tid}")
        replacements.append((start, end, template_region(contract, tid)))
    start, end = region_span(skill, "EFFORT HONORING NOTE")
    replacements.append((start, end, render_effort_note(contract)))
    replacements.sort()
    for left, right in zip(replacements, replacements[1:], strict=False):
        if left[1] > right[0]:
            _error(str(SKILL), "generated regions", f"overlapping regions. {REMEDY}")
    # Unknown template markers cannot remain as undocumented generated commands.
    actual = re.findall(r"<!-- BEGIN GENERATED PLAN SAVE TEMPLATE: ([^\s]+)", skill)
    expected = [item["id"] for item in contract.data["templates"]]
    if sorted(actual) != sorted(expected):
        _error(
            str(SKILL),
            "generated template inventory",
            f"found {actual!r}; expected {expected!r}. {REMEDY}",
        )
    row_start, row_end = row_span(spec)
    for start, end, replacement in reversed(replacements):
        skill = skill[:start] + replacement + skill[end:]
    return {SKILL: skill, SPEC: spec[:row_start] + render_consumer_row(contract) + spec[row_end:]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=ROOT / CONTRACT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    render = sub.add_parser("render")
    mode = render.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        contract = load(args.contract)
        if args.command == "validate":
            print(json.dumps({"schema": SCHEMA, "outcome": "valid", "path": contract.source}))
            return 0
        originals = {path: (ROOT / path).read_text(encoding="utf-8") for path in (SKILL, SPEC)}
        rendered = rendered_documents(contract, originals[SKILL], originals[SPEC])
        changed = [path for path in originals if originals[path] != rendered[path]]
        if args.check:
            for path in changed:
                print(f"{path}: generated content differs from {contract.source}. {REMEDY}")
                print(
                    "".join(
                        difflib.unified_diff(
                            originals[path].splitlines(True),
                            rendered[path].splitlines(True),
                            fromfile=str(path),
                            tofile=f"{path} (rendered)",
                        )
                    ),
                    end="",
                )
            return int(bool(changed))
        for path in changed:
            (ROOT / path).write_text(rendered[path], encoding="utf-8")
        print(json.dumps({"outcome": "rendered", "changed": [str(p) for p in changed]}))
        return 0
    except (ContractError, OSError, UnicodeError) as exc:
        print(json.dumps({"outcome": "invalid", "error": str(exc), "remedy": REMEDY}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
