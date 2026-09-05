#!/usr/bin/env python3
"""Check or render Plan documentation in an explicit repository checkout.

Usage and ownership: plugins/saga/references/plan-save-contract.md.
Every invocation except --help returns JSON: 0 success, 1 drift, 2 refusal.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import importlib.util
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = Path("plugins/saga/references/plan-save-contract.yaml")
SKILL = Path("plugins/saga/skills/plan/SKILL.md")
SPEC = Path("plugins/saga/references/saga-spec.md")
SCHEMA = "plan_save_contract.v3"


class ContractError(ValueError):
    """Refusal with file, entry, and a repair specific to the failed operation."""

    def __init__(self, source: object, entry: str, reason: str, code: str = "invalid_contract"):
        self.source, self.entry, self.code = (
            str(source) if source is not None else None,
            entry,
            code,
        )
        super().__init__(f"{source}: {entry}: {reason}")


def fail(source: object, entry: str, reason: str, code: str = "invalid_contract") -> NoReturn:
    raise ContractError(source, entry, reason, code)


def keys(value: Any, expected: set[str], entry: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        actual = list(value)[:12] if isinstance(value, dict) else type(value).__name__
        fail(
            CONTRACT,
            entry,
            f"expected exactly these keys: {sorted(expected)}; got {str(actual)[:240]}",
        )


def module(root: Path, path: str, *members: str) -> Any:
    try:
        spec = importlib.util.spec_from_file_location("p5_" + Path(path).stem, root / path)
        if spec is None or spec.loader is None:
            raise ImportError("no Python loader")
        result = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = result
        spec.loader.exec_module(result)
        for member in members:
            getattr(result, member)
        return result
    except Exception as exc:
        fail(
            path,
            "engine import",
            f"{exc}; restore this checkout and its Python dependencies",
            "engine",
        )


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                fail(
                    CONTRACT,
                    f"line {key_node.start_mark.line + 1} key {key!r}",
                    "mapping keys must be unique strings; remove the duplicate/invalid entry",
                )
            result[key] = self.construct_object(value_node, deep=deep)
        return result


@dataclass
class Contract:
    data: dict[str, Any]
    root: Path


def load(*, root: Path = ROOT, text: str | None = None) -> Contract:
    raw = (root / CONTRACT).read_text() if text is None else text
    # Aliases earn nothing in this small carrier. Reject before constructing any graph.
    for token in yaml.scan(raw):
        if isinstance(token, yaml.AliasToken):
            fail(
                CONTRACT,
                f"line {token.start_mark.line + 1} alias {token.value}",
                "aliases are unsupported; spell out this entry",
            )
    data = yaml.load(raw, Loader=UniqueLoader)  # nosec B506: subclass of SafeLoader; no object constructors
    schema = data.get("schema") if isinstance(data, dict) else None
    if schema != SCHEMA:
        fail(
            CONTRACT,
            "schema",
            f"observed {str(schema)[:80]!r}, expected {SCHEMA}; use the matching tool/schema revision: "
            "restore an obsolete carrier with its tool, or upgrade the tool for a newer carrier",
            code="schema_version"
            if isinstance(schema, str) and schema.startswith("plan_save_contract.")
            else "schema_family",
        )
    keys(data, {"schema", "identity", "writes", "templates", "effort_honoring"}, "contract")
    saga = module(
        root, "plugins/saga/scripts/saga.py", "_add_save_parser", "Saga", "derive_saga_id"
    )
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    saga._add_save_parser(sub)
    actions = {a.dest: a for a in sub.choices["save"]._actions}
    names: set[str] = set()
    for section in ("identity", "writes", "templates"):
        items = data[section]
        if not isinstance(items, list) or not items:
            fail(CONTRACT, section, "expected a nonempty list")
        seen: set[str] = set()
        for index, item in enumerate(items):
            entry = f"{section}[{index}]"
            if not isinstance(item, dict):
                fail(CONTRACT, entry, "expected a mapping")
            name = item.get("id" if section == "templates" else "name")
            entry += f" ({name!r})"
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
                fail(CONTRACT, entry, "expected an identifier")
            if name in seen or (section != "templates" and name in names):
                fail(CONTRACT, entry, "duplicate entry; keep exactly one")
            seen.add(name)
            if section == "templates":
                keys(item, {"id", "fixed"}, entry)
                if not isinstance(item["fixed"], dict):
                    fail(CONTRACT, entry + ".fixed", "expected a mapping of fields to choices")
                for field, value in item["fixed"].items():
                    if field not in names:
                        fail(CONTRACT, entry + ".fixed", f"unknown field {field!r}")
                    choice(actions, field, value, entry + ".fixed")
                    source = next(
                        i for i in data["identity"] + data["writes"] if i["name"] == field
                    )
                    if "value" in source and value != source["value"]:
                        fail(
                            CONTRACT,
                            entry + ".fixed",
                            f"{field} has a contract constant; remove the conflicting override",
                        )
                continue
            names.add(name)
            value_key = "value" if "value" in item else "placeholder"
            keys(item, {"name", value_key} | ({"when"} if section == "writes" else set()), entry)
            if name not in actions or name not in {f.name for f in dataclasses.fields(saga.Saga)}:
                fail(CONTRACT, entry, f"--{name.replace('_', '-')} is not a saga.py save option")
            value = item[value_key]
            if (
                not isinstance(value, str)
                or not value
                or any(c in value for c in ("\n", "\r", "\x00", "<!--", "-->"))
            ):
                fail(
                    CONTRACT,
                    entry + "." + value_key,
                    "expected a nonempty single-line string without HTML comment markers",
                )
            choices = actions[name].choices
            if choices is not None:
                allowed = "<" + "|".join(choices) + ">"
                if value_key == "placeholder" and value != allowed:
                    fail(CONTRACT, entry + ".placeholder", f"expected engine choices {allowed}")
            if value_key == "value":
                choice(actions, name, value, entry + ".value")
    for item in data["writes"]:
        when = item["when"]
        if when != "always":
            entry = f"writes ({item['name']!r}).when"
            keys(when, {"field", "equals"}, entry)
            if (
                not isinstance(when["field"], str)
                or when["field"] not in names
                or when["field"] == item["name"]
            ):
                fail(CONTRACT, entry, "condition must reference another declared field")
            choice(actions, when["field"], when["equals"], entry)
            for template in data["templates"]:
                fixed = template["fixed"]
                if (
                    item["name"] in fixed
                    and when["field"] in fixed
                    and fixed[when["field"]] != when["equals"]
                ):
                    fail(
                        CONTRACT,
                        f"templates ({template['id']!r}).fixed",
                        f"{item['name']} is fixed while its condition is false; remove that fixed value",
                    )
    identity = {name.rstrip("_") for name in inspect.signature(saga.derive_saga_id).parameters}
    if {item["name"] for item in data["identity"]} != identity:
        fail(
            CONTRACT,
            "identity",
            f"must match derive_saga_id inputs {sorted(identity)}; place payload fields in writes",
        )
    effort = data["effort_honoring"]
    keys(effort, {"seam", "parameters", "spawn_kinds", "reference"}, "effort_honoring")
    rider = module(
        root,
        "plugins/fleet-core/scripts/fleet_commons/effort_rider.py",
        "inject_effort",
        "SPAWN_KINDS",
        "EFFORTS",
        "EFFORT_RIDER",
    )
    if effort["seam"] != "fleet_commons.effort_rider." + rider.inject_effort.__name__ or effort[
        "parameters"
    ] != list(inspect.signature(rider.inject_effort).parameters):
        fail(CONTRACT, "effort_honoring.seam/parameters", "must match inject_effort signature")
    keys(effort["spawn_kinds"], set(rider.SPAWN_KINDS), "effort_honoring.spawn_kinds")
    for kind, mechanism in effort["spawn_kinds"].items():
        for level in rider.EFFORTS:
            observed = rider.inject_effort("probe", level, kind)
            expected = {"native": "probe", "proxy": rider.EFFORT_RIDER[level] + "\n\nprobe"}
            if (
                not isinstance(mechanism, str)
                or mechanism not in expected
                or observed != expected[mechanism]
            ):
                fail(
                    CONTRACT,
                    f"effort_honoring.spawn_kinds ({kind!r})",
                    "native/proxy declaration disagrees with inject_effort behavior",
                )
    reference = effort["reference"]
    if (
        not isinstance(reference, str)
        or any(c in reference for c in ("\x00", "\n", "\r", "<!--", "-->"))
        or Path(reference).is_absolute()
        or not (root / reference).resolve().is_relative_to(root.resolve())
        or not (root / reference).is_file()
    ):
        fail(CONTRACT, "effort_honoring.reference", "use an existing file inside --root")
    return Contract(data, root)


def choice(actions: dict[str, Any], name: str, value: Any, entry: str) -> None:
    action = actions.get(name)
    if action is None or action.choices is None or value not in action.choices:
        fail(
            CONTRACT,
            entry,
            f"{name}={value!r} must be one of {list(action.choices or []) if action else []}",
        )


def render_consumer_row(contract: Contract) -> str:
    cells = []
    for item in contract.data["writes"]:
        token = item["name"] + ("=" + item["value"] if "value" in item else "")
        cell = f"`{token}`"
        if item["when"] != "always":
            when = item["when"]
            cell += f" (only when `{when['field']}={when['equals']}`)"
        cells.append(cell)
    cells.append(
        "`orchestration_operator_choice` (derived from an explicit mode flag unless an explicit "
        "choice is supplied; omitting both preserves the prior choice or starts empty)"
    )
    return "| **/plan** | `scan` (§2.3, resume before minting) | " + ", ".join(cells) + ". |"


def render_template(contract: Contract, template_id: str) -> str:
    template = next(t for t in contract.data["templates"] if t["id"] == template_id)
    flags, bullets = [], []
    for item in contract.data["identity"] + contract.data["writes"]:
        name = item["name"]
        value = template["fixed"].get(name, item.get("value", item.get("placeholder")))
        flag = f"--{name.replace('_', '-')} {shlex.quote(value)}"
        when = item.get("when", "always")
        if when != "always":
            fixed = template["fixed"].get(when["field"])
            if fixed is None:
                bullets.append(
                    f"- `{flag}` only when `--{when['field'].replace('_', '-')} {when['equals']}`."
                )
                continue
            if fixed != when["equals"]:
                continue
        flags.append(flag)
    lines = [
        f"**Example: {template_id}**",
        "",
        "```bash",
        "python3 plugins/saga/scripts/saga.py save \\",
    ]
    lines += ["  " + flag + (" \\" if i < len(flags) - 1 else "") for i, flag in enumerate(flags)]
    return "\n".join(lines + ["```", "", *bullets]).rstrip()


def render_effort_note(contract: Contract) -> str:
    effort = contract.data["effort_honoring"]
    lines = [f"The honoring seam is `{effort['seam']}({', '.join(effort['parameters'])})`."]
    for kind, mechanism in effort["spawn_kinds"].items():
        lines.append(
            f"`{kind}` "
            + (
                "carries effort on a real control."
                if mechanism == "native"
                else "prepends an `EFFORT_RIDER` directive: a labeled proxy because the Agent tool has no per-call effort parameter."
            )
        )
    lines += [
        f"See `{effort['reference']}`.",
        "The proposed tier cell is `<model>/<effort>`: use `tier_resolver.resolve(...).model`",
        "and `tier_resolver.resolve(...).effort` verbatim so dispatch receives both resolved values.",
        "Team Execution A7 uses the same pair and splits on `/`; its older note is tracked by #993.",
    ]
    return region("EFFORT HONORING NOTE", "\n".join(lines))


def markers(name: str) -> tuple[str, str]:
    if name == "EFFORT HONORING NOTE":
        return f"<!-- BEGIN GENERATED {name}", f"END GENERATED {name} -->"
    return f"<!-- BEGIN GENERATED {name} -->", f"<!-- END GENERATED {name} -->"


def region(name: str, body: str) -> str:
    begin, end = markers(name)
    return f"{begin}\n{body}\n{end}"


def region_span(text: str, name: str, path: Path = SKILL) -> tuple[int, int]:
    begin, end = markers(name)
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
        fail(
            path,
            name,
            "expected one ordered marker pair; restore markers from git, "
            "or resolve the merge conflict using the maintainer runbook before rendering",
        )
    return text.index(begin), text.index(end) + len(end)


def row_span(text: str) -> tuple[int, int]:
    rows = list(re.finditer(r"^\| \*\*/plan\*\* \|[^\n]*", text, re.MULTILINE))
    if len(rows) != 1:
        fail(SPEC, "/plan consumer row", f"found {len(rows)}; restore exactly one row from git")
    return rows[0].span()


def rendered_documents(contract: Contract, skill: str, spec: str) -> dict[Path, str]:
    for path, text in ((SKILL, skill), (SPEC, spec)):
        if re.search(r"(?m)^(?:<{7}|={7}|>{7}|\|{7})(?: |$)", text):
            fail(
                path,
                "merge conflict",
                "resolve the entire conflict, including its delimiters, before rendering",
            )
    replacements = []
    for group in ("default", "workflow"):
        name = "PLAN SAVE EXAMPLES: " + group
        examples = [
            render_template(contract, t["id"])
            for t in contract.data["templates"]
            if (t["fixed"].get("orchestration_mode") == "cc-workflows-ultracode")
            == (group == "workflow")
        ]
        replacements.append((*region_span(skill, name), region(name, "\n\n".join(examples))))
    replacements.append((*region_span(skill, "EFFORT HONORING NOTE"), render_effort_note(contract)))
    replacements.sort()
    for left, right in zip(replacements, replacements[1:], strict=False):
        if left[1] > right[0]:
            fail(SKILL, "generated regions", "overlap; restore the markers from git")
    outside = skill
    for start, end, replacement in reversed(replacements):
        skill = skill[:start] + replacement + skill[end:]
        outside = outside[:start] + "\n" * outside[start:end].count("\n") + outside[end:]
    if re.search(r"(?m)(?:^\s*|`)(?:python3?\s+)?(?:[\w./-]+/)?saga\.py\s+save\b", outside):
        fail(
            SKILL,
            "save example outside generated regions",
            "add examples to templates in YAML; remove the extra command from the document",
        )
    start, end = row_span(spec)
    return {SKILL: skill, SPEC: spec[:start] + render_consumer_row(contract) + spec[end:]}


def write_documents(
    root: Path, originals: dict[Path, str], rendered: dict[Path, str], changed: list[Path]
) -> None:
    """Stage both files first; replace atomically per file and roll back a failed batch.

    This is a solo maintainer tool, not a crash-safe multi-file transaction. A failed
    rollback retains backup paths in the diagnostic rather than claiming no changes.
    """
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    written: list[Path] = []
    try:
        for path in changed:
            for target, content in ((staged, rendered[path]), (backups, originals[path])):
                with tempfile.NamedTemporaryFile(
                    mode="w", dir=(root / path).parent, prefix=".plan-contract-", delete=False
                ) as handle:
                    target[path] = Path(handle.name)
                    handle.write(content)
                target[path].chmod((root / path).stat().st_mode)
        try:
            for path in changed:
                os.replace(staged[path], root / path)
                written.append(path)
        except OSError as exc:
            failed_path = path
            failures = []
            for path in reversed(written):
                try:
                    os.replace(backups[path], root / path)
                except OSError:
                    failures.append(f"{path}: restore {backups.pop(path)} manually")
            fail(
                root / failed_path,
                "filesystem",
                f"{exc}; "
                + (
                    "rollback incomplete: " + "; ".join(failures)
                    if failures
                    else "all changes rolled back; fix filesystem access and retry"
                ),
                "filesystem",
            )
    finally:
        for path in [*staged.values(), *backups.values()]:
            path.unlink(missing_ok=True)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        fail(None, "usage", message + "; run --help", "usage")


def verify_saved_examples(root: Path) -> None:
    """Require the existing real-save oracle, without a second policy validator.

    This is a repository maintenance tool: use the checkout's dev environment.
    The selected test renders in memory and saves only into pytest's temporary paths.
    """
    tool = Path("plugins/saga/scripts/plan_save_contract.py")
    if (root / tool).read_bytes() != Path(__file__).read_bytes():
        fail(
            tool,
            "tool revision",
            "run the tool from the target checkout so its tested renderer is the one that writes",
            "verification",
        )
    guard = "tests/test_saga_spec_consumer_row.py::test_plan_examples_save_the_intended_tick"
    with tempfile.TemporaryDirectory(prefix="plan-save-proof-") as temporary:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                guard,
                "-q",
                "-o",
                "addopts=",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(Path(temporary) / "run"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode:
        fail(
            CONTRACT,
            "writes / saved examples",
            f"{guard} failed (exit {result.returncode}); inspect the example/contract and restore the checkout's test dependencies; do not change the runtime to satisfy this check.\n"
            + result.stdout[-1200:]
            + result.stderr[:300],
            "verification",
        )


def main(argv: list[str] | None = None) -> int:
    root = ROOT
    try:
        parser = Parser(description=__doc__)
        parser.add_argument(
            "--root", default=str(ROOT), help="target checkout (code, YAML and docs together)"
        )
        sub = parser.add_subparsers(dest="command", required=True)
        sub.add_parser(
            "validate", help="validate YAML against this checkout’s producer and Python code"
        )
        render = sub.add_parser("render", help="check or update generated documentation")
        mode = render.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--check", action="store_true", help="report drift as JSON; exit 1 if different"
        )
        mode.add_argument(
            "--write", action="store_true", help="update both docs; roll back on write failure"
        )
        args = parser.parse_args(argv)
        if not args.root.strip():
            parser.error("--root must name a checkout")
        root = Path(args.root).resolve()
        contract = load(root=root)
        verify_saved_examples(root)
        if args.command == "validate":
            print(json.dumps({"outcome": "valid", "schema": SCHEMA, "root": str(root)}))
            return 0
        originals = {p: (root / p).read_text() for p in (SKILL, SPEC)}
        rendered = rendered_documents(contract, originals[SKILL], originals[SPEC])
        changed = [p for p in originals if originals[p] != rendered[p]]
        if args.check:
            diff = "".join(
                "".join(
                    difflib.unified_diff(
                        originals[p].splitlines(True),
                        rendered[p].splitlines(True),
                        fromfile=str(p),
                        tofile=str(p),
                    )
                )
                for p in changed
            )
            print(
                json.dumps(
                    {
                        "outcome": "drift" if changed else "clean",
                        "root": str(root),
                        "diff": diff,
                        "changed": [str(p) for p in changed],
                    }
                )
            )
            return int(bool(changed))
        write_documents(root, originals, rendered, changed)
        print(
            json.dumps(
                {"outcome": "rendered", "root": str(root), "changed": [str(p) for p in changed]}
            )
        )
        return 0
    except Exception as exc:
        code = "filesystem" if isinstance(exc, OSError) else "syntax"
        detail = {
            "outcome": "invalid",
            "root": str(root),
            "error": str(exc)[:2000]
            + (
                ""
                if isinstance(exc, ContractError)
                else "; restore readable, valid checkout inputs before retrying"
            ),
            "code": exc.code if isinstance(exc, ContractError) else code,
            "file": exc.source
            if isinstance(exc, ContractError)
            else str(getattr(exc, "filename", None) or CONTRACT),
            "entry": exc.entry if isinstance(exc, ContractError) else "load/render",
        }
        print(json.dumps(detail))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
