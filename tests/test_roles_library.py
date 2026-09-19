"""Structural tests for the roles library (issue 1022).

Globs ``plugins/agent-launcher/roles/*.md`` and holds every prompt to the contract the
directory's own README states: four required headings, four frontmatter keys, an ``emits``
list whose entries are real lifecycle handoff contracts, a ``role_id`` the lifecycle names,
and no vocabulary from the retired ``team-execution`` plugin.

Two properties are worth naming because they are easy to get wrong.

**The expected role set is read from the README, not hard-coded here.** The README's
``## Role to file map`` table is the single list; a row without a file and a file without a
row both fail, so neither half can drift alone.

**The stop-rule check is anchored to a line start.** The README has to quote the heading it
mandates, so a plain substring search matches the README too and a search for files lacking
the heading comes back empty -- passing vacuously. Anchored, it says what it means.

Lens, contract and role identifiers are read live from the sibling ``infiquetra-sdlc``
checkout when one is resolvable, and fall back to lists pinned at the revision named in
``SDLC_PIN`` otherwise, so the suite still runs on a machine that has no sibling checkout.
"""

from __future__ import annotations

import json
import os
import pathlib
import re

import pytest

TESTS_ROOT = pathlib.Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
ROLES_DIR = REPO_ROOT / "plugins" / "agent-launcher" / "roles"

#: The ``infiquetra-sdlc`` revision the pinned fallbacks below were taken from.
SDLC_PIN = "67845cdd"

#: The one file exempt from the per-prompt rules, by name. The README is the directory's
#: contract document: it carries no stop rule and it is the only file allowed to name the
#: retired plugin, because it accounts for where each retired prompt went.
README_NAME = "README.md"

REQUIRED_HEADINGS = (
    "## Role",
    "## Inputs from the run record",
    "## Output contract",
    "### Stop rule",
)

REQUIRED_FRONTMATTER_KEYS = ("role", "role_id", "emits", "source")

#: Vocabulary the retired plugin invented for gate status. The lifecycle records pass-or-fail
#: evidence in the handoff comment instead, so these must not reappear in a role prompt.
#: Only the two discriminating words are listed -- "pass", "warn" and "blocked" are ordinary
#: English and would produce false failures.
FORBIDDEN_STATUS_WORDS = ("hard-fail", "skipped-by-config")

FALLBACK_LENS_IDS = (
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "deployment-infrastructure",
    "reliability",
    "performance",
    "api-contract",
    "adversarial",
    "privacy",
    "documentation-clarity",
    "agent-usability",
    "previous-comments",
    "accessibility-human-usability",
    "experience",
)

FALLBACK_CONTRACT_IDS = (
    "technical-context",
    "issue-review-result",
    "planner-to-orchestrator",
    "plan-review-result",
    "orchestrator-to-controller",
    "dispatch",
    "implementation-result",
    "code-review-result",
    "repair-amendment",
    "investigation-request",
    "diagnosis",
    "release-handoff",
    "release-result",
    "functional-qa-result",
    "product-ruling",
    "run-record",
)

FALLBACK_ROLE_IDS = (
    "product",
    "issue_reviewer",
    "planner",
    "orchestrator",
    "controller",
    "implementer",
    "plan_reviewer",
    "review_controller",
    "lens_reviewer",
    "standard_repair_implementer",
    "expert_repair_implementer",
    "release_worker",
    "functional_tester",
    "investigator",
    "operator",
)


def _sdlc_root() -> pathlib.Path | None:
    """Resolve the sibling lifecycle checkout, or None when there is not one.

    Order: the ``INFIQUETRA_SDLC_ROOT`` environment variable, then a directory named
    ``infiquetra-sdlc`` beside this repository. Never an absolute path baked into the test.
    """
    candidates: list[pathlib.Path] = []
    from_env = os.environ.get("INFIQUETRA_SDLC_ROOT")
    if from_env:
        candidates.append(pathlib.Path(from_env))
    candidates.append(REPO_ROOT.parent / "infiquetra-sdlc")
    for candidate in candidates:
        if (candidate / "config" / "run-model.json").is_file():
            return candidate
    return None


def _live_lens_ids(root: pathlib.Path) -> tuple[str, ...] | None:
    path = root / "config" / "lens-catalogue.json"
    if not path.is_file():
        return None
    catalogue = json.loads(path.read_text(encoding="utf-8"))
    return tuple(lens["id"] for lens in catalogue["lenses"])


def _live_run_model_ids(root: pathlib.Path, key: str) -> tuple[str, ...] | None:
    path = root / "config" / "run-model.json"
    if not path.is_file():
        return None
    model = json.loads(path.read_text(encoding="utf-8"))
    entries = model.get(key)
    if not entries:
        return None
    return tuple(entry["id"] for entry in entries)


def _resolve_ids() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Lens, contract and role identifiers -- live where possible, pinned otherwise."""
    root = _sdlc_root()
    if root is None:
        return FALLBACK_LENS_IDS, FALLBACK_CONTRACT_IDS, FALLBACK_ROLE_IDS
    lenses = _live_lens_ids(root) or FALLBACK_LENS_IDS
    contracts = _live_run_model_ids(root, "contracts") or FALLBACK_CONTRACT_IDS
    roles = _live_run_model_ids(root, "roles") or FALLBACK_ROLE_IDS
    return lenses, contracts, roles


LENS_IDS, CONTRACT_IDS, ROLE_IDS = _resolve_ids()

ALL_ROLE_FILES: list[pathlib.Path] = sorted(ROLES_DIR.glob("*.md"))
PROMPT_FILES: list[pathlib.Path] = [p for p in ALL_ROLE_FILES if p.name != README_NAME]


def parse_frontmatter(path: pathlib.Path) -> dict[str, str | list[str]]:
    """Parse the ``---``-delimited frontmatter block into scalars and lists.

    Deliberately not the scalar-only helper the agent-definition lints share: ``emits`` is a
    YAML list, and a scalar parser would silently read it as an empty value.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}
    block = text[4 : end + 1]

    parsed: dict[str, str | list[str]] = {}
    current_list_key: str | None = None
    for raw in block.splitlines():
        if not raw.strip():
            continue
        if raw.startswith(("  - ", "- ")) and current_list_key is not None:
            item = raw.split("- ", 1)[1].strip()
            target = parsed[current_list_key]
            assert isinstance(target, list)
            target.append(item)
            continue
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "[]":
            # An inline empty list. Without this, it parses as the string "[]" and a role
            # that legitimately emits no contract of its own looks like a malformed scalar.
            parsed[key] = []
            current_list_key = None
        elif value:
            parsed[key] = value
            current_list_key = None
        else:
            parsed[key] = []
            current_list_key = key
    return parsed


def role_map() -> dict[str, tuple[str, str]]:
    """The README's ``## Role to file map`` table, as ``{filename: (role, role_id)}``.

    The first Markdown table after that heading, three columns: readable role name, role
    identifier, filename.
    """
    text = (ROLES_DIR / README_NAME).read_text(encoding="utf-8")
    _, marker, after = text.partition("## Role to file map")
    assert marker, "the README must carry a '## Role to file map' heading"

    mapping: dict[str, tuple[str, str]] = {}
    started = False
    for line in after.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if started:
                break
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if len(cells) != 3:
            continue
        if set(cells[0]) <= {"-", ":"}:
            continue
        if cells[2].lower() == "file":
            started = True
            continue
        started = True
        mapping[cells[2]] = (cells[0], cells[1])
    return mapping


ROLE_MAP = role_map()


def test_roles_glob_finds_files() -> None:
    """Sanity: an empty glob would make every parametrized assertion vacuously true."""
    assert ALL_ROLE_FILES, f"no role files found under {ROLES_DIR}/*.md"
    assert PROMPT_FILES, "the roles directory holds a README but no role prompts"


def test_role_map_is_populated() -> None:
    """The README's map is the expected-set source; an unparsed table would disable the suite."""
    assert len(ROLE_MAP) >= 14, f"expected at least 14 mapped roles, parsed {len(ROLE_MAP)}"


def test_card_acceptance_file_count() -> None:
    """The card's floor: at least fourteen files in the directory."""
    assert len(ALL_ROLE_FILES) >= 14


def test_every_mapped_role_has_a_file() -> None:
    """A row in the README's map with no file on disk."""
    missing = sorted(name for name in ROLE_MAP if not (ROLES_DIR / name).is_file())
    assert not missing, f"README maps roles with no prompt file: {missing}"


def test_every_prompt_file_is_mapped() -> None:
    """A file on disk with no row in the README's map."""
    unmapped = sorted(p.name for p in PROMPT_FILES if p.name not in ROLE_MAP)
    assert not unmapped, f"prompt files missing from the README's map: {unmapped}"


def test_readme_carries_no_stop_rule_heading() -> None:
    """The README's exemption, asserted rather than assumed."""
    text = (ROLES_DIR / README_NAME).read_text(encoding="utf-8")
    assert not re.search(r"^### Stop rule", text, re.MULTILINE)


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_has_required_headings(path: pathlib.Path) -> None:
    """Every prompt states its role, inputs, output contract and stop rule."""
    text = path.read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE), (
            f"{path.name}: missing required heading {heading!r}"
        )


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_frontmatter(path: pathlib.Path) -> None:
    """Four keys, a role identifier the lifecycle names, and ``emits`` as a list."""
    frontmatter = parse_frontmatter(path)
    for key in REQUIRED_FRONTMATTER_KEYS:
        assert key in frontmatter, f"{path.name}: missing frontmatter key {key!r}"

    role_id = frontmatter["role_id"]
    assert isinstance(role_id, str)
    assert role_id in ROLE_IDS, f"{path.name}: role_id {role_id!r} is not a lifecycle role"
    assert ROLE_MAP[path.name][1] == role_id, (
        f"{path.name}: role_id {role_id!r} disagrees with the README's map"
    )

    emits = frontmatter["emits"]
    assert isinstance(emits, list), f"{path.name}: emits must be a YAML list, not a bare string"
    for contract in emits:
        assert contract in CONTRACT_IDS, (
            f"{path.name}: emits {contract!r}, which is not a lifecycle handoff contract"
        )


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_carries_no_retired_vocabulary(path: pathlib.Path) -> None:
    """No prompt names the retired plugin or its gate-status words."""
    text = path.read_text(encoding="utf-8")
    assert "team-execution" not in text, f"{path.name} names the retired plugin"
    for word in FORBIDDEN_STATUS_WORDS:
        assert word not in text, f"{path.name} uses the retired gate-status word {word!r}"


def test_readme_may_name_the_retired_plugin() -> None:
    """The README's other exemption: it accounts for where the retired prompts went."""
    text = (ROLES_DIR / README_NAME).read_text(encoding="utf-8")
    assert "team-execution" in text


@pytest.mark.parametrize("lens_id", LENS_IDS)
def test_lens_reviewer_covers_every_catalogue_lens(lens_id: str) -> None:
    """Every lens in the catalogue has its own section in the Lens Reviewer prompt."""
    text = (ROLES_DIR / "lens-reviewer.md").read_text(encoding="utf-8")
    assert re.search(rf"^#### {re.escape(lens_id)}\s*$", text, re.MULTILINE), (
        f"lens-reviewer.md has no '#### {lens_id}' section"
    )


def test_lens_reviewer_states_no_thresholds() -> None:
    """The catalogue owns the strictness ladder; a copy here would be a second source."""
    text = (ROLES_DIR / "lens-reviewer.md").read_text(encoding="utf-8")
    for threshold in ("8.0", "9.0", "9.5"):
        assert threshold not in text, (
            f"lens-reviewer.md names the threshold {threshold!r}; thresholds live in the catalogue"
        )


def test_no_prompt_declares_a_tier() -> None:
    """Staffing is the staffing component's decision, not a field in these files."""
    for path in PROMPT_FILES:
        frontmatter = parse_frontmatter(path)
        assert "model" not in frontmatter, f"{path.name} declares a model"
        assert "effort" not in frontmatter, f"{path.name} declares an effort"


# --- seeded fixtures: each rule proven to fire ---------------------------------------


def _write(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_seeded_prompt_without_stop_rule_fails(tmp_path: pathlib.Path) -> None:
    fixture = _write(tmp_path, "no-stop.md", "---\nrole: X\n---\n\n## Role\n\nbody\n")
    text = fixture.read_text(encoding="utf-8")
    assert not re.search(r"^### Stop rule", text, re.MULTILINE)


def test_seeded_prompt_quoting_the_heading_is_not_a_heading(tmp_path: pathlib.Path) -> None:
    """The anchoring that makes the stop-rule check mean what it says."""
    fixture = _write(tmp_path, "quotes.md", "---\nrole: X\n---\n\nSee `### Stop rule` above.\n")
    text = fixture.read_text(encoding="utf-8")
    assert "### Stop rule" in text
    assert not re.search(r"^### Stop rule", text, re.MULTILINE)


def test_seeded_bare_string_emits_fails(tmp_path: pathlib.Path) -> None:
    fixture = _write(
        tmp_path,
        "bare.md",
        "---\nrole: X\nrole_id: planner\nemits: dispatch\nsource: s\n---\nbody\n",
    )
    frontmatter = parse_frontmatter(fixture)
    assert not isinstance(frontmatter["emits"], list)


def test_seeded_inline_empty_list_parses(tmp_path: pathlib.Path) -> None:
    """``emits: []`` is a list, not the string "[]"."""
    fixture = _write(
        tmp_path, "empty.md", "---\nrole: X\nrole_id: lens_reviewer\nemits: []\nsource: s\n---\nb\n"
    )
    assert parse_frontmatter(fixture)["emits"] == []


def test_seeded_list_emits_parses(tmp_path: pathlib.Path) -> None:
    fixture = _write(
        tmp_path,
        "listed.md",
        "---\nrole: X\nrole_id: planner\nemits:\n  - dispatch\n  - diagnosis\nsource: s\n---\nb\n",
    )
    frontmatter = parse_frontmatter(fixture)
    assert frontmatter["emits"] == ["dispatch", "diagnosis"]


def test_seeded_unknown_contract_fails(tmp_path: pathlib.Path) -> None:
    fixture = _write(
        tmp_path,
        "unknown.md",
        "---\nrole: X\nrole_id: planner\nemits:\n  - not-a-contract\nsource: s\n---\nbody\n",
    )
    frontmatter = parse_frontmatter(fixture)
    emits = frontmatter["emits"]
    assert isinstance(emits, list)
    assert emits[0] not in CONTRACT_IDS


def test_seeded_missing_emits_fails(tmp_path: pathlib.Path) -> None:
    fixture = _write(tmp_path, "no-emits.md", "---\nrole: X\nrole_id: planner\nsource: s\n---\nb\n")
    frontmatter = parse_frontmatter(fixture)
    assert "emits" not in frontmatter


def test_seeded_missing_lens_section_fails(tmp_path: pathlib.Path) -> None:
    """A lens reviewer missing one catalogue lens must not pass the coverage check."""
    body = "".join(f"#### {lens}\n\ntext\n\n" for lens in LENS_IDS[:-1])
    fixture = _write(tmp_path, "partial-lens-reviewer.md", f"---\nrole: X\n---\n\n{body}")
    text = fixture.read_text(encoding="utf-8")
    absent = LENS_IDS[-1]
    assert not re.search(rf"^#### {re.escape(absent)}\s*$", text, re.MULTILINE)
    assert re.search(rf"^#### {re.escape(LENS_IDS[0])}\s*$", text, re.MULTILINE)


def test_seeded_retired_vocabulary_fails(tmp_path: pathlib.Path) -> None:
    fixture = _write(tmp_path, "retired.md", "---\nrole: X\n---\n\nReport hard-fail on error.\n")
    text = fixture.read_text(encoding="utf-8")
    assert any(word in text for word in FORBIDDEN_STATUS_WORDS)


def test_planner_and_delivery_manager_emit_several_contracts() -> None:
    """The two roles that forced ``emits`` to be a list, asserted on the real files."""
    planner = parse_frontmatter(ROLES_DIR / "planner.md")["emits"]
    delivery_manager = parse_frontmatter(ROLES_DIR / "delivery-manager.md")["emits"]
    assert isinstance(planner, list) and len(planner) == 2
    assert isinstance(delivery_manager, list) and len(delivery_manager) == 5


def test_lens_reviewer_emits_nothing_of_its_own() -> None:
    """Its result is aggregated into the review controller's contract, so the list is empty."""
    assert parse_frontmatter(ROLES_DIR / "lens-reviewer.md")["emits"] == []
