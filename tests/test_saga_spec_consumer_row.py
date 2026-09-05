"""Issue #926 (unit P5, issue 918 Wave Two): Plan skill <-> saga-spec drift checks.

Two cheap guards against the documentation drift this unit repairs, both derived
from the documents rather than restated beside them:

* ``test_plan_docs_reject_unhonored_effort_claims`` — no Markdown file under
  ``plugins/saga/`` may claim resolved effort is emitted but not consumed,
  honored, dispatched, or enforced. It matches the *class* of claim: a span
  pairing an effort token with the ``emission only`` idiom, a negation
  governing a consume/honor/dispatch/enforce verb (including ``un-`` forms such
  as ``unconsumed``), or a dead-end adjective such as inert, advisory-only, or
  ignored — never one literal sentence. Spans carrying the visible
  ``drift-check-opt-out`` sentinel are skipped: a historical statement opts out
  explicitly rather than by file extension.
* ``test_saga_spec_plan_consumer_row_matches_skill`` — the saga-spec ``/plan``
  consumer row lists exactly the fields Plan's Phase 5.3 save blocks write.
  The expected set is derived from the skill's own fenced ``saga.py save``
  blocks (shared fence reader, union across variants, shell comments stripped,
  minus the ``--kind``/``--id`` identity flags); the row is parsed per the
  convention stated beside it (backticked identifiers outside parentheses).
  No second hardcoded field list lives here.

Mutation proof: restoring the pre-repair effort comment fails the first test,
an ``unconsumed`` claim inside an HTML comment fails it, and adding a flag to
a Phase 5.3 save block (or deleting a field from the row) fails the second. A
check that cannot fail is the defect class this repository has hit before.

Known duplicate outside this scope: a second copy of the stale effort claim
lives at ``plugins/team-execution/skills/team-execution/SKILL.md`` under
follow-up issue #993. The negative check is deliberately scoped to
``plugins/saga/``; widening it to ``plugins/`` belongs to that follow-up.
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
from saga_plan_contract import flags_of as _flags_of
from saga_plan_contract import plan_phase_53 as _plan_phase_53
from saga_plan_contract import save_blocks as _save_blocks

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "saga"
PLAN_SKILL = PLUGIN_ROOT / "skills" / "plan" / "SKILL.md"
SAGA_SPEC = PLUGIN_ROOT / "references" / "saga-spec.md"

# ---------------------------------------------------------------------------
# Negative check: no "effort is emitted but unhonored" claim under plugins/saga/
# ---------------------------------------------------------------------------

_EFFORT_TOKEN = re.compile(r"effort", re.IGNORECASE)
_EMISSION_ONLY = re.compile(r"emission\s+only", re.IGNORECASE)
# Visible opt-out: a span describing the matcher itself (e.g. the CHANGELOG
# bullet below) carries this token and the span builder skips it.
_OPT_OUT = re.compile(r"drift-check-opt-out", re.IGNORECASE)
# `yet` is deliberately not a negation: it pairs with adjectives ("not ready
# yet") that have nothing to do with honoring effort.
_NEGATION = r"no|not|never|nothing|none|lacks|awaits"
# Honor-class verbs, including `un-` denials ("unconsumed" carries its own
# negation, so no separate negation token is required for those). `read` is
# bounded to its verb forms so "ready", "readable", and "reader" never match.
_VERB = (
    r"unconsum\w*|unhonou?r\w*|unenforc\w*|consum\w*|honou?r\w*|"
    r"dispatch\w*|enforc\w*|(?:reads?|reading)\b"
)
_NEGATION_GOVERNS_UNHONORED = re.compile(
    rf"\b({_NEGATION})\b(?:\W+\w+){{0,5}}?\W+({_VERB})",
    re.IGNORECASE,
)
_UNPREFIXED_DENIAL = re.compile(rf"\bun({_VERB})", re.IGNORECASE)
_DEAD_EFFORT = re.compile(r"\b(inert|advisory(?:\s+only)?|ignor(?:e|ed|es|ing))\b", re.IGNORECASE)
# A sentence is split into clauses on [,;:] and dashes before matching, so a
# negation governing an honor-class verb must share one *clause* with the
# effort token — mere co-occurrence across a 700-line file, or across the two
# halves of a "do X, not by reading it" instruction, is not a match. HTML
# comment blocks stay whole: the stale claim spans source lines, which is what
# a line-oriented grep misses.
_CLAUSE_SPLIT = re.compile(r"[,;:—–]\s*")


def _claim_spans(text: str) -> list[str]:
    """Every ``<!-- ... -->`` block plus every prose clause, whitespace-folded.

    Spans carrying the ``drift-check-opt-out`` sentinel are dropped: a span
    that describes this matcher is not a claim about the system.
    """
    spans = re.findall(r"<!--(.*?)-->", text, flags=re.DOTALL)
    prose = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        spans.extend(_CLAUSE_SPLIT.split(sentence))
    return [" ".join(span.split()) for span in spans if span.strip() and not _OPT_OUT.search(span)]


def _unhonored_effort_match(span: str) -> str | None:
    """Name which claim half a span matches, or ``None`` when it is clean."""
    if not _EFFORT_TOKEN.search(span):
        return None
    if _EMISSION_ONLY.search(span):
        return "emission-only idiom"
    branches = (
        ("negation governing honor-class verb", _NEGATION_GOVERNS_UNHONORED, 80),
        ("un- denial verb", _UNPREFIXED_DENIAL, 40),
        ("dead-end adjective", _DEAD_EFFORT, 40),
    )
    for name, pattern, width in branches:
        match = pattern.search(span)
        if match is not None:
            return f"{name}: {match.group(0)[:width]!r}"
    return None


def test_plan_docs_reject_unhonored_effort_claims() -> None:
    """No Saga document claims resolved effort is emitted but unhonored.

    Mutation proof: restoring the pre-repair ``EFFORT-EMISSION MARKER`` comment
    fails this test naming that file and span; an ``unconsumed`` claim inside
    an HTML comment fails it too, proving the pattern catches the class —
    including the exact word of issue 926's criterion — and not the original
    wording.
    """
    failures = [
        (str(path.relative_to(ROOT)), _unhonored_effort_match(span), span)
        for path in sorted(PLUGIN_ROOT.rglob("*.md"))
        for span in _claim_spans(path.read_text(encoding="utf-8"))
        if _unhonored_effort_match(span) is not None
    ]
    assert not failures, "Saga docs claim effort is emitted but unhonored:\n" + "\n".join(
        f"{file}: [{why}] {span}" for file, why, span in failures[:5]
    )

    # Rewording proof: a differently worded relapse is still caught.
    assert _unhonored_effort_match("the effort half is surfaced but nothing honors it")
    # Criterion-word proof: the exact word of issue 926's negative criterion,
    # inside an HTML comment, is caught through span extraction (not the
    # emission-only branch, which this span never touches).
    commented = _claim_spans(
        "<!-- effort note: Plan resolved effort is emitted but unconsumed by any dispatcher. -->"
    )
    assert len(commented) == 1
    assert _unhonored_effort_match(commented[0]) is not None
    assert "unconsumed" in commented[0]
    # Emission-branch proof: this span carries no negation and no un-verb, so
    # only the emission-only branch can catch it — deleting that branch fails
    # this assertion.
    assert (
        _unhonored_effort_match("the tier cell carries effort under emission only")
        == "emission-only idiom"
    )
    # Multi-line proof: a claim split across source lines is one span, not two.
    assert any(
        _unhonored_effort_match(span) is not None
        for span in _claim_spans(
            "<!-- effort note: this is emission only:\nno dispatch mechanism honors it -->"
        )
    )
    # Dead-end-adjective proofs: inert / advisory-only / ignored with effort.
    assert _unhonored_effort_match("The resolved effort is inert.") is not None
    assert _unhonored_effort_match("The effort half is advisory only.") is not None
    assert _unhonored_effort_match("the dispatcher ignores effort") is not None
    # Un-verb control: the legitimate "unconsumed" wording becomes a match the
    # moment an effort token shares its span.
    assert _unhonored_effort_match("resolved effort arrives unconsumed") is not None
    # Read-boundary guards: verb-form bounding keeps "ready", "readable", and
    # "reader" out of the verb class even beside a negation and an effort token.
    assert _unhonored_effort_match("the effort estimate is not ready for review") is None
    assert _unhonored_effort_match("effort values must be readable by the operator") is None
    # False-positive guards: the two legitimate "unconsumed" uses carry no
    # effort token in their span, so the conjunction excludes both.
    assert (
        _unhonored_effort_match(
            "previously-unconsumed engine loophole (the merge queue's tokenless R12 auto-merge)"
        )
        is None
    )
    assert (
        _unhonored_effort_match('errors = [f"proof-integrity: launched-unconsumed {key}"]') is None
    )
    # Opt-out proof: a real claim carrying the sentinel never reaches the
    # matcher — the span builder drops it visibly.
    assert (
        _claim_spans(
            "<!-- effort note: effort is unconsumed "
            "(drift-check-opt-out: describes the matcher itself) -->"
        )
        == []
    )
    # Self-pass guard: the repaired comment pairs "honoring seam" with "no
    # per-call effort parameter" ~40 words apart across clauses, which the
    # proximity-bound pattern must not match.
    repaired = next(
        span
        for span in _claim_spans(PLAN_SKILL.read_text(encoding="utf-8"))
        if "honoring seam" in span
    )
    assert _unhonored_effort_match(repaired) is None


# ---------------------------------------------------------------------------
# Positive check: the /plan consumer row equals what Phase 5.3 writes
# ---------------------------------------------------------------------------

_IDENTITY_FLAGS = frozenset({"kind", "id"})


def _skill_field_set(section: str) -> set[str]:
    """Derive the flag union from explicit skill text; no alternate file-read path."""
    fields = set().union(*(_flags_of(block) for block in _save_blocks(section)))
    return fields - _IDENTITY_FLAGS


def _plan_row_line(spec_text: str) -> str:
    """The ``| **/plan**`` consumer-table row of a saga-spec text."""
    matches = [line for line in spec_text.splitlines() if line.strip().startswith("| **/plan**")]
    assert len(matches) == 1, f"expected exactly one /plan consumer row, found {len(matches)}"
    return matches[0]


def _row_field_set(spec_text: str) -> set[str]:
    """Backticked identifiers outside parentheses in the /plan Writes cell."""
    cells = [cell.strip() for cell in _plan_row_line(spec_text).strip().split("|")[1:-1]]
    assert len(cells) >= 3, "the /plan consumer row must have a Writes cell"
    deparen = re.sub(r"\([^)]*\)", " ", cells[2])
    return set(re.findall(r"`([a-z][a-z_]*)", deparen))


def test_saga_spec_plan_consumer_row_matches_skill() -> None:
    """The /plan consumer row names exactly what Phase 5.3's save blocks write.

    Mutation proof: adding a flag to a Phase 5.3 save block without updating
    the row fails this test naming the skill-side orphan, and deleting a field
    from the row without removing its flag fails it naming the row-side orphan.
    The expected set is derived from the skill, never restated here.
    """
    real_section = _plan_phase_53()
    spec_text = SAGA_SPEC.read_text(encoding="utf-8")
    expected = _skill_field_set(real_section)
    assert expected, "an empty skill-derived field set must never read as agreement"
    row = _row_field_set(spec_text)
    assert row, "an empty row field set must never read as agreement"
    assert expected == row, (
        f"{SAGA_SPEC}: /plan consumer row drifted from {PLAN_SKILL} Phase 5.3: "
        f"in the skill but not the row: {sorted(expected - row)}; "
        f"in the row but not the skill: {sorted(row - expected)}"
    )

    # Exercise the same explicit-input path as the comparison above. Allocate
    # a synthetic name absent from the documents AND the engine's source rather
    # than claiming a real option (formerly --orchestration-downgrade) cannot exist.
    occupied = (
        real_section + spec_text + (PLUGIN_ROOT / "scripts/saga.py").read_text(encoding="utf-8")
    )
    forged_flag = "saga-test-only-nonexistent-field"
    while forged_flag in occupied or forged_flag.replace("-", "_") in occupied:
        forged_flag += "-x"
    forged_field = forged_flag.replace("-", "_")
    forged = real_section + (
        '\n```bash title="derivation probe"\n'
        f"python3 plugins/saga/scripts/saga.py save --{forged_flag} value\n```\n"
    )
    assert _skill_field_set(forged) == expected | {forged_field}, (
        "skill derivation must reflect an added option through the comparison's input path"
    )

    # Titled-fence proof: a save variant with a non-plain info string is still
    # a save block. Under a plain-fence-only pattern this finds nothing and
    # fails, hiding real drift.
    titled = _save_blocks(
        '### 5.3\n```bash title="third variant"\n'
        "python3 plugins/saga/scripts/saga.py save --forged-flag x\n```\n"
    )
    assert any("saga.py save" in block for block in titled)
    for opening, closing in (("~~~bash", "~~~"), ('````bash title="save"', "````")):
        assert _save_blocks(
            f"An inline ``` mention is prose.\n{opening}\n"
            f"python3 plugins/saga/scripts/saga.py save --id probe\n{closing}\n"
        ) == ["python3 plugins/saga/scripts/saga.py save --id probe"]

    # Comment-strip proof: a flag named only inside a `#` shell comment is
    # documentation, not a write.
    assert _flags_of("  --deploy-autonomy <gate|auto>   # ONLY when --forged-flag x") == {
        "deploy_autonomy"
    }

    # Hashes and flag-like text inside values are data. Comments at column 0
    # or after a tab are comments just as they are after a space.
    assert _flags_of(
        '--decisions "KTD: per issue #926" --issue-ref owner/repo#926\n'
        "# --comment-only x\n\t# --tab-comment x\n"
        '--adr-refs "--quoted-value" --plan-path=docs/plans/example.md'
    ) == {"decisions", "issue_ref", "adr_refs", "plan_path"}
    assert _flags_of(
        "--issue-ref owner/repo#926 --decisions '# a quoted value' --adr-refs ADR-1"
    ) == {"issue_ref", "decisions", "adr_refs"}
    assert _flags_of(r"--decisions escaped\ #926 --adr-refs ADR-1") == {"decisions", "adr_refs"}

    # Union-across-variants proof: --deploy-autonomy and --orchestration-ref
    # each live in only one save block, so an intersection would under-specify.
    per_block = [_flags_of(block) for block in _save_blocks(_plan_phase_53())]
    assert any(
        "deploy_autonomy" in flags and "orchestration_ref" not in flags for flags in per_block
    )
    assert any(
        "orchestration_ref" in flags and "deploy_autonomy" not in flags for flags in per_block
    )

    # Parse-stability proof: the auto-derivation note is present in the row,
    # and the parse covers flag-written fields only — `decisions` aside,
    # parenthesized notes are descriptive. In particular
    # `orchestration_operator_choice` is stored. Without an explicit choice,
    # the engine fills it from an explicitly passed --orchestration-mode.
    # When both flags are absent, a new saga starts empty; existing state is
    # carried forward. No Phase 5.3 flag passes the choice directly.
    raw_row = _plan_row_line(SAGA_SPEC.read_text(encoding="utf-8"))
    assert re.search(r"\([^)]*destination=nonprod-deploy[^)]*\)", raw_row)
    assert "orchestration_operator_choice" in raw_row
    assert "orchestration_operator_choice" not in row

    # Error path: a missing row fails naming the row, never silently or with
    # an IndexError on an empty set.
    rowless = "\n".join(
        line
        for line in SAGA_SPEC.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("| **/plan**")
    )
    with pytest.raises(AssertionError, match="exactly one /plan consumer row"):
        _row_field_set(rowless)


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

    # U1-only lossless migration proof; U2 replaces this with durable render pins.
    old_row = next(
        line for line in SAGA_SPEC.read_text().splitlines() if line.startswith("| **/plan** |")
    )
    old_names = _row_field_set(old_row)
    assert old_names == {item["name"] for item in contract.data["writes"]}
    old_block = _save_blocks(_plan_phase_53())[0]
    old_lines = [line for line in old_block.splitlines() if "--deploy-autonomy" not in line]
    new_lines = (
        contract_api.render_template(contract, "default").split("```", 2)[1].splitlines()[1:]
    )
    assert "\n".join(old_lines).strip() == "\n".join(new_lines).strip()


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
    contract = contract_api.load()
    _assert_operator_rule(contract, observations)
    data = copy.deepcopy(contract.data)
    rule = data["stored_without_flag"][0]["rule"]
    rule["explicit_flag"], rule["else_from_flag"] = rule["else_from_flag"], rule["explicit_flag"]
    with pytest.raises(AssertionError, match="stored_without_flag.*rule disagrees with saved tick"):
        _assert_operator_rule(_mutated(contract_api, data), observations)
