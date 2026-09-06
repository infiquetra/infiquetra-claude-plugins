"""Independent Plan documentation proof; callable without pytest or a tests directory.

Read rendered commands, bind facts to engine behavior, and compare whole saved ticks.
The renderer never supplies expected outcomes. Test mutations protect this oracle.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import re
import shlex
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

import yaml

PLAN_SKILL = Path("plugins/saga/skills/plan/SKILL.md")
SCRIPT = Path("plugins/saga/scripts/plan_save_contract.py")


class ProofError(AssertionError):
    """A candidate contradicts a fact, including under python -O."""


def require(condition: object, message: str = "Plan documentation proof failed") -> None:
    if not condition:
        raise ProofError(message)


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)$")
_OPTION = re.compile(r"--([a-z][a-z0-9-]*)(?:=(.*))?", re.DOTALL)


def plan_phase_53(*, text: str | None = None) -> str:
    """Read exactly Phase 5.3, failing with the source and missing boundary."""
    if text is None:
        text = (Path(__file__).resolve().parents[3] / PLAN_SKILL).read_text(encoding="utf-8")
    boundaries = []
    for heading in ("5.3", "5.4"):
        matches = list(re.finditer(rf"^### {re.escape(heading)}(?:\s|$)", text, re.MULTILINE))
        require(len(matches) == 1, f"{PLAN_SKILL}: expected exactly one ### {heading} heading")
        boundaries.append(matches[0].start())
    start, end = boundaries
    require(start < end, f"{PLAN_SKILL}: ### 5.3 must precede ### 5.4")
    return text[start:end]


def save_blocks(section: str) -> list[str]:
    """Collect save templates in backtick or tilde fences, including titled ones.

    Only line-start fences open blocks; inline backticks cannot shift the pairing.
    Closing fences must use the opening character and at least its run length.
    """
    blocks = []
    opening = ""
    body: list[str] = []
    for line in section.splitlines():
        if not opening:
            match = _FENCE.fullmatch(line)
            if match and not (match[1][0] == "`" and "`" in match[2]):
                opening = match[1]
                body = []
        elif re.fullmatch(rf" {{0,3}}{re.escape(opening[0])}{{{len(opening)},}}\s*", line):
            block = "\n".join(body)
            if re.search(r"\bsaga\.py\s+save\b", block):
                blocks.append(block)
            opening = ""
        else:
            body.append(line)
    require(not opening, f"{PLAN_SKILL} Phase 5.3: unclosed {opening} fence")
    require(blocks, f"{PLAN_SKILL} Phase 5.3: no fenced saga.py save templates found")
    return blocks


def _without_comments(text: str) -> str:
    """Strip a hash only at an unquoted word boundary, as shell comments require.

    shlex's built-in comments mode also strips hashes inside ordinary words
    such as owner/repo#926, so quoting alone is insufficient here.
    """
    result = []
    quote = ""
    escaped = False
    comment = False
    word_start = True
    for char in text:
        if comment:
            if char != "\n":
                continue
            comment = False
        if escaped:
            escaped = False
            result.append(char)
            word_start = False
            continue
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
        elif char in {"'", '"'}:
            quote = char
        elif char == "#" and word_start:
            comment = True
            continue
        result.append(char)
        word_start = char.isspace() and not quote and not escaped
    return "".join(result)


def save_options(block: str) -> dict[str, list[str]]:
    """Read value-taking long options from a save template, retaining repeats.

    POSIX quoting preserves hashes inside values and ignores shell comments at
    any indentation. Keep line boundaries when removing template continuations
    so a comment cannot consume the next documented line. Values are consumed
    with their option; a quoted value containing a flag is not another option.
    """
    try:
        tokens = shlex.split(_without_comments(block.replace("\\\n", "\n")), posix=True)
    except ValueError as exc:
        raise AssertionError(
            f"{PLAN_SKILL} Phase 5.3: invalid save-template quoting: {exc}"
        ) from exc
    options: dict[str, list[str]] = {}
    index = 0
    while index < len(tokens):
        match = _OPTION.fullmatch(tokens[index])
        index += 1
        if match is None:
            continue
        name, value = match.groups()
        if value is None:
            require(index < len(tokens), f"{PLAN_SKILL} Phase 5.3: --{name} needs a value")
            value = tokens[index]
            index += 1
        options.setdefault(name.replace("-", "_"), []).append(value)
    return options


def assert_engine_binding(api: ModuleType, contract: Any) -> None:
    """One engine binding, used by the edit-time preflight and regression tests."""
    saga = api.module(contract.root, "plugins/saga/scripts/saga.py", "_add_save_parser", "Saga")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    saga._add_save_parser(sub)
    actions = {action.dest: action for action in sub.choices["save"]._actions}
    fields = {field.name for field in dataclasses.fields(saga.Saga)}

    def choice(name: str, value: Any, entry: str) -> None:
        options = actions[name].choices if name in actions else None
        if options is None or value not in options:
            api.fail(entry, f"{name}={value!r} must be one of {options or []}")

    for section in ("identity", "writes"):
        for item in contract.data[section]:
            name = item["name"]
            entry = f"{section} ({name!r})"
            if name not in actions or name not in fields:
                api.fail(entry, f"--{name.replace('_', '-')} is not a saga.py save option")
            if "value" in item:
                choice(name, item["value"], entry + ".value")
            elif actions[name].choices is not None:
                allowed = "<" + "|".join(actions[name].choices or []) + ">"
                if item["placeholder"] != allowed:
                    api.fail(entry + ".placeholder", f"expected engine choices {allowed}")
            when = item.get("when", "always")
            if when != "always":
                choice(when["field"], when["equals"], entry + ".when")
    for template in contract.data["templates"]:
        for name, value in template["fixed"].items():
            choice(name, value, f"templates ({template['id']!r}).fixed")
    observed = probe_effort(api, contract.root)
    for kind, mechanism in contract.data["effort_honoring"]["spawn_kinds"].items():
        if mechanism != observed[kind]:
            api.fail(
                f"effort_honoring.spawn_kinds ({kind!r})",
                "declaration disagrees with inject_effort behavior",
            )


def probe_effort(api: ModuleType, root: Path) -> dict[str, str]:
    rider = api.module(root, api.RIDER, "inject_effort")
    mechanisms = {}
    for kind in sorted(rider.SPAWN_KINDS):
        observed = [rider.inject_effort("probe", level, kind) for level in rider.EFFORTS]
        if all(value == "probe" for value in observed):
            mechanisms[kind] = "native"
        else:
            require(
                observed == [rider.EFFORT_RIDER[level] + "\n\nprobe" for level in rider.EFFORTS],
                "Plan documentation proof failed",
            )
            mechanisms[kind] = "proxy"
    return mechanisms


def assert_row(api: ModuleType, contract: Any, text: str) -> None:
    start, end = api.row_span(text)
    row = text[start:end]
    require(row.split("|")[2].strip() == "`scan` (§2.3)", f"{api.SPEC}: Plan Reads cell differs")
    require(re.search(r"(?m)^### 2\.3\b", text), f"{api.SPEC}: missing scan/resume reference")
    intake = (contract.root / api.SKILL).read_text().split("### 0.3", 1)[1].split("### 0.4", 1)[0]
    require(
        "python3 plugins/saga/scripts/saga.py scan" in intake, "Plan documentation proof failed"
    )
    require("Do not hand-edit the `/plan` row." in text, "Plan documentation proof failed")
    require(
        "`tests/test_saga_spec_consumer_row.py::test_saga_spec_plan_consumer_row_matches_contract`"
        in text,
        "Plan documentation proof failed",
    )
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
    expected.append(("orchestration_operator_choice", "", ""))
    require(
        facts == expected, f"{api.SPEC}: /plan consumer row facts differ: {facts} != {expected}"
    )
    require(
        row == api.render_consumer_row(contract),
        f"{api.SPEC}: /plan consumer row rendering differs",
    )


def assert_regions(api: ModuleType, contract: Any, skill: str, spec: str) -> None:
    rendered = api.rendered_documents(contract, skill, spec)
    require(rendered[api.SKILL] == skill, f"{api.SKILL}: generated region differs; render --write")
    phase = plan_phase_53(text=skill)
    blocks = save_blocks(phase)
    require(
        len(blocks) == len(contract.data["templates"]), f"{api.SKILL}: missing/extra save example"
    )
    ids = re.findall(r"\*\*Example: ([a-z0-9_-]+)\*\*", phase)
    require(
        len(ids) == len(set(ids)) == len(blocks), f"{api.SKILL}: duplicate or missing example ID"
    )
    by_id = dict(zip(ids, blocks, strict=True))
    require(
        set(by_id) == {t["id"] for t in contract.data["templates"]},
        "Plan documentation proof failed",
    )
    for template in contract.data["templates"]:
        block = by_id[template["id"]]
        options = save_options(block)
        expected_options = {}
        for item in contract.data["identity"] + contract.data["writes"]:
            when = item.get("when", "always")
            if when != "always" and template["fixed"].get(when["field"]) != when["equals"]:
                continue
            value = template["fixed"].get(item["name"], item.get("value", item.get("placeholder")))
            expected_options[item["name"]] = [value]
        require(
            options == expected_options,
            f"{api.SKILL}: template {template['id']} lost or changed flags",
        )
    for name in (
        "PLAN SAVE EXAMPLES: default",
        "PLAN SAVE EXAMPLES: workflow",
        "EFFORT HONORING NOTE",
    ):
        start, end = api.region_span(skill, name)
        require(
            f"Source: {api.CONTRACT}; renderer: {SCRIPT}." in skill[start:end],
            "Plan documentation proof failed",
        )
        require(
            "Do not hand-edit; guard: tests/test_saga_spec_consumer_row.py::test_plan_docs_generated_regions_match_contract."
            in skill[start:end],
            "Plan documentation proof failed",
        )
    start, end = api.region_span(skill, "EFFORT HONORING NOTE")
    note = skill[start:end]
    rider = api.module(contract.root, api.RIDER, "inject_effort")
    groups: dict[str, list[str]] = {"native": [], "proxy": []}
    for kind, mechanism in probe_effort(api, contract.root).items():
        groups[mechanism].append(f"`{kind}`")
    # Positive pins bind every generated factual clause to these independent probes.
    expected = [
        f"The honoring seam is `fleet_commons.effort_rider.inject_effort({', '.join(inspect.signature(rider.inject_effort).parameters)})`.",
        "For "
        + ", ".join(groups["native"])
        + ": effort already rides on real controls; injecting a rider would double-count it.",
        "For "
        + ", ".join(groups["proxy"])
        + ": prepend an `EFFORT_RIDER` directive: a labeled proxy because the Agent tool has no per-call effort parameter.",
        "See `plugins/fleet-core/references/effort-convention.md`.",
        "The proposed tier cell is `<model>/<effort>`: use `tier_resolver.resolve(...).model`",
        "and `tier_resolver.resolve(...).effort` verbatim so dispatch receives both resolved values.",
        "Team Execution A7 uses the same pair and splits on `/`; its older note is tracked by #993.",
    ]
    actual = re.findall(r"<!--\n(.*?)\n-->", note, re.S)
    require(
        actual == ["\n".join(expected)],
        f"{api.SKILL}: effort/tier factual clauses differ from runtime proof",
    )


def assert_saved_examples(
    api: ModuleType,
    contract: Any,
    tmp_path: Path,
    destination: str,
    backend: str,
    *,
    probe: Callable[[Path, dict[str, str]], tuple[dict[str, Any], str]] | None = None,
) -> None:
    """Compare the whole saved snapshot with Plan's independently specified outcomes."""
    # Conditions are single equalities. Vary each additional predicate's enum one
    # at a time; destination/backend are already crossed by the parametrized test.
    entries = {i["name"]: i for i in contract.data["identity"] + contract.data["writes"]}
    predicates = {i["when"]["field"] for i in contract.data["writes"] if i["when"] != "always"}
    # Issue IDs use a different filesystem path rule from task slugs.
    variants: list[dict[str, str]] = [{}, {"kind": "issue"}]
    for field in sorted(predicates - {"destination", "orchestration_mode"}):
        placeholder = entries[field].get("placeholder", "")
        if placeholder.startswith("<") and placeholder.endswith(">") and "|" in placeholder:
            variants.extend({field: value} for value in placeholder[1:-1].split("|"))
    probe = probe or SaveProbe(api, contract.root)
    for template in contract.data["templates"]:
        for index, overrides in enumerate(variants):
            assert_saved_example(
                api,
                contract,
                tmp_path / template["id"] / str(index),
                destination,
                backend,
                template,
                overrides,
                probe,
            )


def assert_saved_example(
    api: ModuleType,
    contract: Any,
    tmp_path: Path,
    destination: str,
    backend: str,
    template: dict[str, Any],
    overrides: dict[str, str],
    probe: Callable[[Path, dict[str, str]], tuple[dict[str, Any], str]],
) -> None:
    body = api.render_template(contract, template["id"])
    block = save_blocks(body)[0]
    values = {name: value[0] for name, value in save_options(block).items()}

    def fill(name: str, value: str, template_id: str = template["id"]) -> str:
        # Substitute only enum choices, never replace literal text under test.
        if value.startswith("<") and value.endswith(">") and "|" in value:
            choices = value[1:-1].split("|")
            selected = {
                "destination": destination,
                "orchestration_mode": backend,
                "kind": "task",
                "deploy_autonomy": "auto",
            }.get(name, choices[0])
            selected = overrides.get(name, selected)
            require(selected in choices, f"template {template_id}: {name} lacks {selected}")
            return selected
        return value

    values = {name: fill(name, value) for name, value in values.items()}
    for name, value, field, expected in re.findall(
        r"- `--([a-z-]+) ([^`]+)` only when `--([a-z-]+) ([^`]+)`\.", body
    ):
        if values[field.replace("-", "_")] == expected:
            tokens = shlex.split(value)
            require(
                len(tokens) == 1,
                f"template {template['id']}: conditional value is not one shell argument",
            )
            values[name.replace("-", "_")] = fill(name.replace("-", "_"), tokens[0])
    workspace = tmp_path
    workspace.mkdir(parents=True)
    identity = {name: values[name] for name in ("kind", "id")}
    before, _ = probe(
        workspace, {**identity, "next_step": "prior work", "review_paths": "prior-review.md"}
    )
    tick, text = probe(workspace, values)
    # The expectation names semantic outcomes, not a second list of save flags.
    # Every other stored field must remain unchanged, including fields a new
    # (valid but unrelated) save option might otherwise silently overwrite.
    expected = {
        "lifecycle_phase": "plan",
        "phase_status": "complete",
        "plan_path": values["plan_path"],
        "destination": values["destination"],
        "adr_refs": re.findall(r"\bADR-[A-Za-z0-9]+\b", values["adr_refs"]),
        "orchestration_recommended": values["orchestration_recommended"],
        "orchestration_mode": values["orchestration_mode"],
        "orchestration_operator_choice": values["orchestration_mode"],
        "deploy_autonomy": values["deploy_autonomy"]
        if values["destination"] == "nonprod-deploy"
        else "",
        "orchestration_ref": values["orchestration_ref"]
        if values["orchestration_mode"] == "cc-workflows-ultracode"
        else "",
    }
    require(expected["adr_refs"], "Plan example must demonstrate pipe-separated ADR references")
    require(
        "orchestration_operator_choice" not in values,
        "Plan examples derive operator choice from the mode flag",
    )
    require(
        values.keys() <= expected.keys() | identity.keys() | {"decisions"},
        "Plan example writes unrelated state",
    )
    before.update(expected)
    before.pop("updated_at")
    tick.pop("updated_at")
    require(tick == before, f"template {template['id']}: saved Plan snapshot differs")
    require(
        values["decisions"] in text.split("## Decisions", 1)[1], "Plan documentation proof failed"
    )


class SaveProbe:
    """Use the same parser/build/save chain as saga.py, in an explicit private root."""

    def __init__(self, api: ModuleType, root: Path):
        self.engine = api.module(
            root, "plugins/saga/scripts/saga.py", "_add_save_parser", "_build_save_saga", "save"
        )
        self.parser = argparse.ArgumentParser(exit_on_error=False)
        self.engine._add_save_parser(self.parser.add_subparsers())

    @staticmethod
    def no_git(*args: Any, **kwargs: Any) -> NoReturn:
        # Private proof directories have no repository. The existing engine seam
        # avoids repeated external Git discovery; subprocess tests retain real Git.
        raise FileNotFoundError("documentation proof has no Git repository")

    def __call__(self, workspace: Path, flags: dict[str, str]) -> tuple[dict[str, Any], str]:
        args = ["save"]
        for name, value in flags.items():
            args += ["--" + name.replace("_", "-"), value]
        try:
            incoming, explicit = self.engine._build_save_saga(self.parser.parse_args(args))
        except (argparse.ArgumentError, SystemExit) as exc:
            raise ProofError("Plan example arguments are not accepted by saga.py save") from exc
        target = (workspace / self.engine.SAGAS_DIR / incoming.saga_id).resolve()
        require(
            target.is_relative_to(workspace.resolve()),
            "Plan example saga identity escapes its temporary workspace",
        )
        result = self.engine.save(workspace, incoming, explicit_fields=explicit, runner=self.no_git)
        body = (workspace / result["envelope_path"]).read_text()
        return yaml.safe_load(body.split("---", 2)[1]), body


def verify(api: ModuleType, contract: Any, candidate: dict[Path, str]) -> None:
    """Prove candidate facts and saved semantics without loading tests or launching pytest."""
    assert_engine_binding(api, contract)
    try:
        assert_regions(api, contract, candidate[api.SKILL], candidate[api.SPEC])
    except (AssertionError, KeyError, ValueError) as exc:
        api.fail("generated facts", str(exc), source=api.SKILL, code="verification")
    try:
        assert_row(api, contract, candidate[api.SPEC])
    except (AssertionError, KeyError, ValueError) as exc:
        api.fail("/plan consumer row", str(exc), source=api.SPEC, code="verification")
    engine = api.module(
        contract.root, "plugins/saga/scripts/saga.py", "DESTINATIONS", "ORCHESTRATION_MODES"
    )
    with tempfile.TemporaryDirectory(prefix="plan-save-proof-") as temporary:
        for destination in engine.DESTINATIONS:
            for backend in engine.ORCHESTRATION_MODES:
                try:
                    assert_saved_examples(
                        api, contract, Path(temporary) / destination / backend, destination, backend
                    )
                except Exception as exc:
                    api.fail(
                        "writes / saved examples",
                        f"{destination}/{backend}: {exc}; correct the candidate, not the runtime",
                        code="verification",
                    )
