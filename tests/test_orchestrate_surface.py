"""Tests for the `/orchestrate` Claude command loader and `/outcome`'s mechanical deprecation.

`/outcome` is deprecated by rewriting its `description:` frontmatter, never by deleting anything.
`description` is the field a model matches a user's intent against when picking a command — a
deprecation notice in the command body changes nothing about that decision, so the description
itself has to stop reading like the thing a user wants when they want cross-vendor orchestration.

The vocabulary a rewritten description must avoid is enumerated below rather than left to a vague
"doesn't sound like orchestration anymore" assertion, and each stem's rationale is stated at its
declaration. A test that only checks a vocabulary list is declared, without checking it against real
description text, would keep passing after the check it names stopped doing anything — this file
proves the checker is behavioural by running it against the ORIGINAL, pre-rewrite description text
(`test_vocabulary_checker_flags_the_original_pre_rewrite_description`) and asserting every declared
stem is caught.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent

ORCHESTRATE_CMD = ROOT / "plugins" / "orchestrate" / "commands" / "orchestrate.md"
ORCHESTRATE_SKILL = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "SKILL.md"
ORCHESTRATE_PLUGIN_JSON = ROOT / "plugins" / "orchestrate" / ".claude-plugin" / "plugin.json"

OUTCOME_CMD = ROOT / "plugins" / "saga" / "commands" / "outcome.md"
OUTCOME_SKILL = ROOT / "plugins" / "saga" / "skills" / "outcome" / "SKILL.md"
SAGA_SCRIPTS_DIR = ROOT / "plugins" / "saga" / "scripts"

MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

REPLACEMENT_COMMAND = "/orchestrate"

# The ORIGINAL description this unit replaced (captured verbatim, not re-derived from the current
# file), used only to prove the checker below is behavioural — see the module docstring.
ORIGINAL_OUTCOME_DESCRIPTION = (
    "Coordinate a whole outcome as a durable DAG of leaf sagas — start, advance the ready "
    "frontier, attend a leaf, resume, graph, export/import. The coordinator routes and "
    "dispatches to executors; it never runs leaf work itself, and status is derived on read."
)

# Orchestration-intent vocabulary `/outcome`'s description must no longer contain. Each entry is a
# word STEM, matched as a lowercase substring, so one entry catches every inflection (verb, noun,
# plural) without hand-listing each form. A word that legitimately describes what `/outcome` itself
# still does is deliberately NOT here — see the "kept" note after the list.
#
# - "coordinat"  — coordinate / coordinator. The generic verb for cross-vendor orchestration work;
#                  that job now belongs to /orchestrate, whose own description uses it instead.
# - "dispatch"   — dispatch / dispatches / dispatched. /orchestrate's register dispatches vendor
#                  children (R1/R4 of the orchestrate plan); reusing it in /outcome's description
#                  would describe the same product twice.
# - "executor"   — executor / executors. /orchestrate's whole model is vendor children being routed
#                  and dispatched to; /outcome hands a leaf to its own native saga command
#                  (`/resume`, `/work`, `/code-review`, `/qa`), never to an abstract executor pool.
# - "route"      — route / routes / routing / router. Vendor selection and routing for capacity and
#                  capability is /orchestrate's job (R8); /outcome doesn't choose among vendors at
#                  all, so this word never described a capability /outcome has.
#
# Kept (deliberately absent from the banned list) because /outcome genuinely still does or is this:
# "outcome" (the object both commands act on — it's literally /outcome's own name), "DAG" / "leaf
# saga(s)" / "frontier" (the specific data structure /outcome manages — a graph-theory term, not a
# generic pitch for orchestration), and the verbs it still runs: start, advance, attend, resume,
# graph, export/import.
BANNED_ORCHESTRATION_VOCABULARY = ("coordinat", "dispatch", "executor", "route")

# Scripts the outcome skill documents by name (`plugins/saga/skills/outcome/SKILL.md`), plus every
# outcome_*.py module in the same scripts directory — globbed rather than hand-enumerated so this
# stays accurate without being re-edited every time an unrelated /outcome change adds one.
OUTCOME_DOCUMENTED_SCRIPTS = ("outcome.py", "intent_envelope.py", "spec_table.py", "status_card.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_frontmatter(text: str) -> dict:
    """Parse a ``---``-delimited YAML frontmatter block. Raises if the block is missing or
    malformed, unlike a permissive "treat missing as empty" helper — a command file with broken
    frontmatter is a build defect, not a legitimate state to silently tolerate here."""
    assert text.startswith("---\n"), "file has no frontmatter block"
    end = text.find("\n---", 4)
    assert end != -1, "frontmatter block is not closed"
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict), "frontmatter did not parse to a mapping"
    return parsed


def _vocabulary_hits(description: str) -> list[str]:
    """Return every banned stem that is present (case-insensitive substring) in `description`."""
    lowered = description.lower()
    return [stem for stem in BANNED_ORCHESTRATION_VOCABULARY if stem in lowered]


# ---------------------------------------------------------------------------
# 1. The /orchestrate loader's frontmatter
# ---------------------------------------------------------------------------


def test_orchestrate_loader_frontmatter_carries_name_description_argument_hint():
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))

    assert front.get("name") == "orchestrate"
    assert isinstance(front.get("description"), str) and front["description"].strip()
    assert isinstance(front.get("argument-hint"), str) and front["argument-hint"].strip()


def test_orchestrate_loader_frontmatter_mutation_is_detected():
    """Deletion proof, in memory: a frontmatter block missing `argument-hint` must fail the same
    assertion the real file passes, proving the check reads the field rather than the file's mere
    existence."""
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))
    mutated = dict(front)
    del mutated["argument-hint"]

    assert "argument-hint" not in mutated
    assert not (
        isinstance(mutated.get("argument-hint"), str) and mutated.get("argument-hint", "").strip()
    )


def test_orchestrate_loader_loads_the_skill_and_forwards_arguments():
    body = _read(ORCHESTRATE_CMD)

    assert "orchestrate/skills/orchestrate/SKILL.md" in body
    assert "$ARGUMENTS" in body


def test_orchestrate_loader_argument_hint_takes_the_outcome_as_its_argument():
    """KTD1: orchestrate is a verb taking the outcome as its argument, not the other way round —
    the argument-hint should read as the outcome forms it accepts, not as sub-verbs of a noun
    command (contrast `/outcome`'s `start <id> | advance <id> | ...` shape)."""
    front = _split_frontmatter(_read(ORCHESTRATE_CMD))
    hint = front["argument-hint"]

    assert "issue" in hint.lower()
    assert "requirements doc" in hint.lower()
    assert "prose prompt" in hint.lower()


# ---------------------------------------------------------------------------
# 2. `/outcome`'s description no longer matches orchestration intent, and names /orchestrate
# ---------------------------------------------------------------------------


def test_outcome_description_contains_none_of_the_banned_vocabulary():
    front = _split_frontmatter(_read(OUTCOME_CMD))
    description = front["description"]

    hits = _vocabulary_hits(description)

    assert hits == [], f"description still contains orchestration-intent vocabulary: {hits}"


def test_outcome_description_names_orchestrate_as_the_replacement():
    front = _split_frontmatter(_read(OUTCOME_CMD))

    assert REPLACEMENT_COMMAND in front["description"]


def test_outcome_description_still_describes_what_outcome_actually_does():
    """The rewrite must not have swung so far it stopped describing /outcome. Its own domain words
    (not on the banned list — see the list's own comment) must survive."""
    front = _split_frontmatter(_read(OUTCOME_CMD))
    description = front["description"].lower()

    for still_true in ("dag", "leaf saga", "outcome", "status is derived on read"):
        assert still_true in description, (
            f"rewrite dropped a real /outcome property: {still_true!r}"
        )


def test_vocabulary_checker_flags_the_original_pre_rewrite_description():
    """The behavioural proof this file's docstring promises: run the SAME checker function the
    tests above use against the description this unit actually replaced, captured verbatim as a
    module constant (not re-derived from the current file — that would make this test trivially
    circular). Every declared stem must be caught, or the vocabulary list is decorative."""
    hits = _vocabulary_hits(ORIGINAL_OUTCOME_DESCRIPTION)

    assert set(hits) == set(BANNED_ORCHESTRATION_VOCABULARY)


def test_outcome_argument_hint_and_body_are_unchanged():
    """This change is a description rewrite, not a behaviour change: `/outcome` must keep working,
    invoked explicitly, exactly as it did before. Its sub-verbs (argument-hint) and its explanatory
    body are a second, independent read on "nothing deleted" beyond the skill/script check below."""
    text = _read(OUTCOME_CMD)
    front = _split_frontmatter(text)

    for verb in (
        "start",
        "advance",
        "approve",
        "commit",
        "attend",
        "resume",
        "graph",
        "export",
        "import",
    ):
        assert verb in front["argument-hint"]
    assert "Load `saga/skills/outcome/SKILL.md`" in text
    assert "**The coordinator routes, it never executes**" in text  # body invariant, untouched


# ---------------------------------------------------------------------------
# 3. `/outcome`'s skill and scripts are untouched
# ---------------------------------------------------------------------------


def test_outcome_skill_still_exists_and_is_named_outcome():
    front = _split_frontmatter(_read(OUTCOME_SKILL))

    assert front.get("name") == "outcome"


def test_outcome_documented_scripts_still_exist_and_are_valid_python():
    for script_name in OUTCOME_DOCUMENTED_SCRIPTS:
        path = SAGA_SCRIPTS_DIR / script_name
        assert path.exists(), f"{script_name} referenced by outcome's SKILL.md is missing"
        ast.parse(_read(path), filename=str(path))  # real parse, not just "the file has bytes"


def test_every_outcome_prefixed_script_still_exists_and_is_valid_python():
    """Glob rather than a hand-maintained list, so a script this unit did not touch (and has no
    reason to know the full name of) still gets a real parse check instead of silent coverage
    gaps. This only inspects files already present on disk — it cannot itself delete anything."""
    outcome_scripts = sorted(SAGA_SCRIPTS_DIR.glob("outcome*.py"))

    assert len(outcome_scripts) >= 15, (
        "far fewer outcome_*.py scripts than expected — the outcome engine may have been pruned"
    )
    for path in outcome_scripts:
        ast.parse(_read(path), filename=str(path))


# ---------------------------------------------------------------------------
# 4. The marketplace entries validate
# ---------------------------------------------------------------------------


def test_orchestrate_and_saga_marketplace_entries_are_in_release_surface_parity():
    """Reuses the repository's own tri-lock checker (plugin.json version == marketplace entry
    version == CHANGELOG top heading version) rather than re-deriving the comparison, and asserts
    neither plugin this unit touched is reported drifted. Deliberately does not hardcode either
    plugin's version number: two other units bump `plugins/orchestrate`'s release surfaces on their
    own branches, so a literal version string here would be reconciled-away noise rather than a
    real regression signal."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "check_release_surface_parity",
        ROOT / "scripts" / "check_release_surface_parity.py",
    )
    assert spec is not None and spec.loader is not None
    parity = importlib.util.module_from_spec(spec)
    sys.modules["check_release_surface_parity"] = parity
    spec.loader.exec_module(parity)

    drifted = parity.check_parity()

    assert "orchestrate" not in drifted
    assert "saga" not in drifted


def test_orchestrate_marketplace_entry_matches_its_plugin_json():
    import json

    plugin_json = json.loads(_read(ORCHESTRATE_PLUGIN_JSON))
    marketplace = json.loads(_read(MARKETPLACE))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "orchestrate")

    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/orchestrate"
    assert entry["description"] == plugin_json["description"]
