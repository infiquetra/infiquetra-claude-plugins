"""Structural tests for the roles library (issue 1022).

Globs ``plugins/agent-launcher/roles/*.md`` and holds every prompt to the contract the
directory's own README states: four required headings in order, four non-empty frontmatter keys,
an ``emits`` list whose entries are handoff contracts the lifecycle says this very role produces,
a ``role_id`` the lifecycle names, and no vocabulary from the retired ``team-execution`` plugin.

Three properties are worth naming because each one was got wrong first.

**Every rule is a named checker function, called by both the real test and its seeded fixture.**
A seeded fixture that re-types the production regex proves a property of ``re``, not that the rule
fires. When a checker changes, both callers change with it.

**The stop-rule check is anchored to a line start.** The README has to quote the heading it
mandates, so an unanchored substring search matches the README too and a search for files
*lacking* the heading comes back empty -- passing vacuously.

**``emits`` is checked for producership, not just membership.** Membership alone would accept
``product.md`` claiming ``run-record``. The lifecycle carries ``sender_role`` per contract, so the
test asserts the emitting role is the contract's sender of record.

Lens, contract and role identifiers are read live from the sibling ``infiquetra-sdlc`` checkout
when one is resolvable, and fall back to lists pinned at ``SDLC_PIN`` otherwise.
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

#: The ``infiquetra-sdlc`` revision the pinned fallbacks and the prompts' ``source:`` were taken
#: from. Asserted against every prompt, so a prompt cannot drift to another revision unnoticed.
SDLC_PIN = "67845cdd"

#: The one file exempt from the per-prompt rules, by name. The README is the directory's contract
#: document: it carries no stop rule and it is the only file allowed to name the retired plugin,
#: because it accounts for where each retired prompt went.
README_NAME = "README.md"

#: The only prompt allowed an empty ``emits`` list: its result is aggregated into the Review
#: Controller's contract rather than posted as its own.
AGGREGATED_PROMPT = "lens-reviewer.md"

#: The two roles the lifecycle licenses to reuse another role's contract. The
#: ``implementation-result`` contract's own ``sender_note`` says a repair implementer produces the
#: same contract for the batch it finishes.
REUSED_CONTRACT = "implementation-result"
REUSE_LICENSED_ROLES = ("standard_repair_implementer", "expert_repair_implementer")

REQUIRED_HEADINGS = (
    "## Role",
    "## Inputs from the run record",
    "## Output contract",
    "### Stop rule",
)

REQUIRED_FRONTMATTER_KEYS = ("role", "role_id", "emits", "source")

#: Vocabulary the retired plugin invented, as discriminating tokens. "pass", "warn" and "blocked"
#: are deliberately absent -- they are ordinary English and would produce false failures.
FORBIDDEN_STATUS_WORDS = (
    "hard-fail",
    "soft-fail",
    "skipped-by-config",
    "skipped-by-policy",
    "team-execute",
    "appsec-audit",
    "validator-criteria",
    "review-criteria",
)

#: The lifecycle roles that get a prompt: all of them except the Human Operator, who is a person.
NON_STAFFABLE_ROLE = "operator"

#: A strictness value from the catalogue's ladder, in any spelling. The catalogue owns the ladder;
#: a copy in a prompt would be a second source.
THRESHOLD_PATTERN = re.compile(r"\b(?:8|8\.0|8\.5|9|9\.0|9\.5|0\.8|0\.9)\b")

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

#: contract id -> the role id the lifecycle names as its sender of record.
FALLBACK_CONTRACT_SENDERS = {
    "technical-context": "orchestrator",
    "issue-review-result": "issue_reviewer",
    "planner-to-orchestrator": "planner",
    "plan-review-result": "plan_reviewer",
    "orchestrator-to-controller": "controller",
    "dispatch": "controller",
    "implementation-result": "implementer",
    "code-review-result": "review_controller",
    "repair-amendment": "planner",
    "investigation-request": "controller",
    "diagnosis": "investigator",
    "release-handoff": "controller",
    "release-result": "release_worker",
    "functional-qa-result": "functional_tester",
    "product-ruling": "product",
    "run-record": "controller",
}

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


class FrontmatterError(ValueError):
    """A frontmatter block that cannot be parsed unambiguously.

    Raised rather than swallowed: a silently dropped list item turns a role that emits two
    contracts into one that appears to emit none, which every downstream check then accepts.
    """


def _sdlc_root() -> pathlib.Path | None:
    """Resolve the sibling lifecycle checkout, or None when there is not one.

    Order: the ``INFIQUETRA_SDLC_ROOT`` environment variable, then a directory named
    ``infiquetra-sdlc`` beside this repository or beside any of its ancestors.

    The ancestor walk matters in a git worktree: ``REPO_ROOT`` is then
    ``<checkout>/.claude/worktrees/agent-XXX``, whose parent is ``worktrees/``, so looking only one
    level up finds nothing and the suite silently falls back to the pinned lists -- making the
    drift this design exists to catch invisible exactly where the gate runs.
    """
    candidates: list[pathlib.Path] = []
    from_env = os.environ.get("INFIQUETRA_SDLC_ROOT")
    if from_env:
        candidates.append(pathlib.Path(from_env))
    for ancestor in [REPO_ROOT, *REPO_ROOT.parents]:
        candidates.append(ancestor.parent / "infiquetra-sdlc")
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


def _live_role_ids(root: pathlib.Path) -> tuple[str, ...] | None:
    model = json.loads((root / "config" / "run-model.json").read_text(encoding="utf-8"))
    roles = model.get("roles")
    if not roles:
        return None
    return tuple(role["id"] for role in roles)


def _live_contract_senders(root: pathlib.Path) -> dict[str, str] | None:
    model = json.loads((root / "config" / "run-model.json").read_text(encoding="utf-8"))
    contracts = model.get("contracts")
    if not contracts:
        return None
    return {contract["id"]: contract["sender_role"] for contract in contracts}


def _resolve() -> tuple[tuple[str, ...], dict[str, str], tuple[str, ...], bool]:
    """Lens ids, contract senders, role ids -- live where possible, pinned otherwise."""
    root = _sdlc_root()
    if root is None:
        return FALLBACK_LENS_IDS, FALLBACK_CONTRACT_SENDERS, FALLBACK_ROLE_IDS, False
    lenses = _live_lens_ids(root) or FALLBACK_LENS_IDS
    senders = _live_contract_senders(root) or FALLBACK_CONTRACT_SENDERS
    roles = _live_role_ids(root) or FALLBACK_ROLE_IDS
    return lenses, senders, roles, True


LENS_IDS, CONTRACT_SENDERS, ROLE_IDS, READ_LIVE = _resolve()
CONTRACT_IDS = tuple(CONTRACT_SENDERS)

#: Named in every assertion message, because a verdict that differs between a developer machine
#: and a continuous-integration runner has to say which source produced it.
ID_SOURCE = f"live@{_sdlc_root()}" if READ_LIVE else f"pinned@{SDLC_PIN}"

ALL_ROLE_FILES: list[pathlib.Path] = sorted(ROLES_DIR.glob("*.md"))
PROMPT_FILES: list[pathlib.Path] = [p for p in ALL_ROLE_FILES if p.name != README_NAME]

#: Everything in the directory, at any depth and any extension -- used to catch a prompt hidden
#: in a subdirectory or under an extension the glob above does not see.
EVERY_FILE: list[pathlib.Path] = sorted(p for p in ROLES_DIR.rglob("*") if p.is_file())


# --- the parser -----------------------------------------------------------------------


def parse_frontmatter(path_or_text: pathlib.Path | str) -> dict[str, str | list[str]]:
    """Parse the ``---``-delimited frontmatter block into scalars and lists, strictly.

    Returns ``{}`` when the file carries no frontmatter block at all -- the absence is then
    caught by the required-key check, loudly. Inside a block, anything that is neither a
    ``key:`` line nor a list item raises, because the alternative is a silently truncated list.

    Deliberately not the scalar-only helper the agent-definition lints share: ``emits`` is a
    list, and a scalar parser reads it as an empty value.
    """
    if isinstance(path_or_text, pathlib.Path):
        text = path_or_text.read_text(encoding="utf-8")
        label = path_or_text.name
    else:
        text = path_or_text
        label = "<text>"

    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}
    block = text[4 : end + 1]

    parsed: dict[str, str | list[str]] = {}
    current_list_key: str | None = None
    for lineno, raw in enumerate(block.splitlines(), start=2):
        if not raw.strip():
            continue

        stripped = raw.strip()
        if stripped.startswith("- "):
            if current_list_key is None:
                raise FrontmatterError(f"{label}:{lineno}: list item with no preceding key")
            target = parsed[current_list_key]
            assert isinstance(target, list)
            target.append(stripped[2:].strip())
            continue

        if ":" not in raw:
            raise FrontmatterError(f"{label}:{lineno}: not a key or a list item: {raw!r}")
        if raw != raw.lstrip():
            raise FrontmatterError(f"{label}:{lineno}: indented key; nesting is not supported")

        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if key in parsed:
            raise FrontmatterError(f"{label}:{lineno}: duplicate key {key!r}")

        if value == "[]":
            # An inline empty list. Without this it parses as the string "[]", and a role that
            # legitimately emits no contract of its own looks like a malformed scalar.
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
    identifier, filename. A table that is not three columns raises rather than being skipped --
    skipping walks the reader on into the next table in the file and returns an unrelated map.
    """
    text = (ROLES_DIR / README_NAME).read_text(encoding="utf-8")
    _, marker, after = text.partition("## Role to file map")
    if not marker:
        raise AssertionError("the README must carry a '## Role to file map' heading")

    mapping: dict[str, tuple[str, str]] = {}
    started = False
    for line in after.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if started:
                break
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if set(cells[0]) <= {"-", ":"}:
            continue
        if len(cells) != 3:
            raise AssertionError(
                f"the role map table must have exactly three columns, found {len(cells)}: {cells}"
            )
        if not started:
            if [c.lower() for c in cells] != ["role", "role_id", "file"]:
                raise AssertionError(f"unexpected role map header row: {cells}")
            started = True
            continue
        if cells[2] in mapping:
            raise AssertionError(f"duplicate role map row for {cells[2]!r}")
        mapping[cells[2]] = (cells[0], cells[1])
    if not started:
        raise AssertionError("no role map table found after the heading")
    return mapping


ROLE_MAP = role_map()


# --- the rules, each a named checker both callers use -----------------------------------


def strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks, keeping line count so positions stay meaningful.

    Every prompt embeds a fenced example of its handoff comment, and those examples contain
    heading-shaped lines. Without this, a heading that exists only inside an example would
    satisfy the structural check.
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def missing_headings(text: str) -> list[str]:
    """Required headings absent, out of order, or present with nothing under them."""
    body = strip_fenced_blocks(text)
    spans: list[tuple[int, str]] = []
    missing: list[str] = []
    for heading in REQUIRED_HEADINGS:
        match = re.search(rf"^{re.escape(heading)}\s*$", body, re.MULTILINE)
        if match is None:
            missing.append(heading)
        else:
            spans.append((match.end(), heading))
    if missing:
        return missing
    if [s for s, _ in spans] != sorted(s for s, _ in spans):
        return ["<out of order>"]

    empty: list[str] = []
    ordered = sorted(spans)
    for index, (start, heading) in enumerate(ordered):
        end = ordered[index + 1][0] if index + 1 < len(ordered) else len(body)
        section = body[start:end]
        # Drop the next heading's own line before judging emptiness.
        section = re.sub(r"^#{1,6} .*$", "", section, flags=re.MULTILINE)
        if len(section.strip()) < 40:
            empty.append(f"{heading} <empty>")
    return empty


def has_stop_rule_heading(text: str) -> bool:
    """A stop-rule *heading*, not a mention of one, and not one inside a fenced example."""
    return re.search(r"^### Stop rule\s*$", strip_fenced_blocks(text), re.MULTILINE) is not None


def retired_vocabulary(text: str) -> list[str]:
    """Names of the retired plugin or its gate-status words found in the text."""
    found = [word for word in FORBIDDEN_STATUS_WORDS if word in text]
    if "team-execution" in text:
        found.append("team-execution")
    return found


def missing_lens_sections(text: str, lens_ids: tuple[str, ...]) -> list[str]:
    """Catalogue lenses with no ``#### <lens-id>`` section."""
    return [
        lens
        for lens in lens_ids
        if re.search(rf"^#### {re.escape(lens)}\s*$", text, re.MULTILINE) is None
    ]


def emits_violations(role_id: str, emits: object, filename: str) -> list[str]:
    """Everything wrong with one prompt's ``emits``: shape, membership, producership, emptiness."""
    problems: list[str] = []
    if not isinstance(emits, list):
        return [f"emits must be a list, not {type(emits).__name__}"]
    if not emits and filename != AGGREGATED_PROMPT:
        return [f"emits is empty; only {AGGREGATED_PROMPT} may emit nothing of its own"]
    for contract in emits:
        if contract not in CONTRACT_SENDERS:
            problems.append(f"{contract!r} is not a lifecycle handoff contract")
            continue
        sender = CONTRACT_SENDERS[contract]
        if sender == role_id:
            continue
        if contract == REUSED_CONTRACT and role_id in REUSE_LICENSED_ROLES:
            continue
        problems.append(f"{contract!r} is produced by {sender!r}, not by {role_id!r}")
    return problems


# --- the suite ------------------------------------------------------------------------


def test_roles_glob_finds_files() -> None:
    """Sanity: an empty glob would make every parametrized assertion vacuously true."""
    assert ALL_ROLE_FILES, f"no role files found under {ROLES_DIR}/*.md"
    assert PROMPT_FILES, "the roles directory holds a README but no role prompts"


def test_role_map_is_populated() -> None:
    """The README's map is the expected-set source; an unparsed table would disable the suite."""
    assert len(ROLE_MAP) >= 14, f"expected at least 14 mapped roles, parsed {len(ROLE_MAP)}"


def test_card_acceptance_prompt_count() -> None:
    """The card's floor, counted as the card means it: role prompts beside the README.

    Counted on ``PROMPT_FILES``, not on every file in the directory: the README is one of the
    files, so a floor of fourteen over the whole directory would still hold after a prompt was
    deleted.
    """
    assert len(PROMPT_FILES) >= 14


def test_map_and_files_agree_exactly() -> None:
    """Set equality in both directions, so neither an orphan file nor an orphan row survives."""
    assert {p.name for p in PROMPT_FILES} == set(ROLE_MAP), (
        f"role map {sorted(ROLE_MAP)} disagrees with files {sorted(p.name for p in PROMPT_FILES)}"
    )


def test_prompts_cover_every_staffable_lifecycle_role() -> None:
    """R7's first clause, and its converse: exactly the staffable roles, no more and no fewer.

    This is what stops a file the lifecycle does not name -- a scanner, a validator, a monitor --
    from passing by reusing a legitimate role identifier: the identifiers must be distinct and
    must cover the staffable set exactly.
    """
    declared = [parse_frontmatter(p)["role_id"] for p in PROMPT_FILES]
    assert len(declared) == len(set(declared)), f"duplicate role_id among prompts: {declared}"
    expected = {r for r in ROLE_IDS if r != NON_STAFFABLE_ROLE}
    assert set(declared) == expected, (
        f"prompts cover {sorted(set(declared))}, lifecycle staffable roles are {sorted(expected)}"
        f" (ids from {ID_SOURCE})"
    )


def test_roles_directory_holds_nothing_unexpected() -> None:
    """R7's second clause: no prompt hidden in a subdirectory or under another extension."""
    unexpected = sorted(str(p.relative_to(ROLES_DIR)) for p in EVERY_FILE if p.parent != ROLES_DIR)
    assert not unexpected, f"files nested below the roles directory: {unexpected}"
    wrong_extension = sorted(p.name for p in EVERY_FILE if p.suffix != ".md")
    assert not wrong_extension, f"non-Markdown files in the roles directory: {wrong_extension}"


def test_release_surfaces_agree_and_advanced() -> None:
    """R9: the three release surfaces tell one story, and it is past the version before this."""
    manifest = json.loads(
        (REPO_ROOT / "plugins" / "agent-launcher" / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    version = manifest["version"]
    marketplace = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    entry = next(p for p in marketplace["plugins"] if p["name"] == "agent-launcher")
    assert entry["version"] == version, (
        f"marketplace says {entry['version']}, manifest says {version}"
    )
    changelog = (REPO_ROOT / "plugins" / "agent-launcher" / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    assert re.search(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M
    ), f"CHANGELOG has no dated heading for {version}"
    assert tuple(int(p) for p in version.split(".")) > (1, 5, 2), (
        f"agent-launcher {version} does not advance past the version this work started from"
    )


def test_readme_accounts_for_every_retired_prompt_group() -> None:
    """R10: the accounting names each retired group and its destination, not just the plugin."""
    text = (ROLES_DIR / README_NAME).read_text(encoding="utf-8")
    for token in ("Reviewers", "Testers", "Scanners", "Monitors", "deploy watcher"):
        assert token in text, f"the README's retired-prompt accounting omits {token!r}"
    counted = [int(n) for n in re.findall(r"^\| [^|]+ \| (\d+) \|", text, re.MULTILINE)]
    assert sum(counted) == 25, (
        f"the retired-prompt accounting sums to {sum(counted)}, not the 25 prompts that existed"
    )


def test_every_contract_has_a_producing_prompt() -> None:
    """Consumer completeness in the other direction: no lifecycle contract is unowned."""
    claimed: set[str] = set()
    for path in PROMPT_FILES:
        emits = parse_frontmatter(path).get("emits", [])
        if isinstance(emits, list):
            claimed.update(emits)
    unowned = sorted(set(CONTRACT_SENDERS) - claimed)
    assert not unowned, f"lifecycle contracts no prompt produces: {unowned}"


def test_readme_carries_no_stop_rule_heading() -> None:
    """The README's exemption, asserted positively rather than read off an empty result."""
    assert not has_stop_rule_heading((ROLES_DIR / README_NAME).read_text(encoding="utf-8"))


def test_readme_may_name_the_retired_plugin() -> None:
    """The README's other exemption: it accounts for where the retired prompts went."""
    assert "team-execution" in (ROLES_DIR / README_NAME).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_has_required_headings(path: pathlib.Path) -> None:
    problems = missing_headings(path.read_text(encoding="utf-8"))
    assert not problems, f"{path.name}: heading problems: {problems}"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_has_stop_rule_heading(path: pathlib.Path) -> None:
    assert has_stop_rule_heading(path.read_text(encoding="utf-8")), (
        f"{path.name}: no '### Stop rule' heading at a line start"
    )


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_frontmatter(path: pathlib.Path) -> None:
    """Four non-empty keys, a lifecycle role id, and an ``emits`` this role really produces."""
    frontmatter = parse_frontmatter(path)
    for key in REQUIRED_FRONTMATTER_KEYS:
        assert key in frontmatter, f"{path.name}: missing frontmatter key {key!r}"
    for key in ("role", "role_id", "source"):
        assert frontmatter[key], f"{path.name}: frontmatter key {key!r} is empty"

    role_id = frontmatter["role_id"]
    assert isinstance(role_id, str)
    assert role_id in ROLE_IDS, f"{path.name}: role_id {role_id!r} is not a lifecycle role"

    mapped = ROLE_MAP.get(path.name)
    assert mapped is not None, f"{path.name} is not in the README's role map"
    assert mapped[1] == role_id, (
        f"{path.name}: role_id {role_id!r} disagrees with the README's map ({mapped[1]!r})"
    )

    problems = emits_violations(role_id, frontmatter["emits"], path.name)
    assert not problems, f"{path.name}: {problems}"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_source_names_the_pinned_revision(path: pathlib.Path) -> None:
    """A prompt cannot quietly claim a different lifecycle revision than the README does."""
    source = parse_frontmatter(path)["source"]
    assert isinstance(source, str)
    assert SDLC_PIN in source, f"{path.name}: source {source!r} does not name {SDLC_PIN}"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_carries_no_retired_vocabulary(path: pathlib.Path) -> None:
    found = retired_vocabulary(path.read_text(encoding="utf-8"))
    assert not found, f"{path.name} uses retired vocabulary: {found}"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=[p.name for p in PROMPT_FILES])
def test_prompt_declares_no_tier(path: pathlib.Path) -> None:
    """Staffing is decided elsewhere; a tier here would be a second source for one decision."""
    frontmatter = parse_frontmatter(path)
    assert frontmatter, f"{path.name}: no frontmatter block, so this check would be vacuous"
    assert "model" not in frontmatter, f"{path.name} declares a model"
    assert "effort" not in frontmatter, f"{path.name} declares an effort"


def test_lens_reviewer_covers_every_catalogue_lens() -> None:
    text = (ROLES_DIR / AGGREGATED_PROMPT).read_text(encoding="utf-8")
    assert LENS_IDS, "the lens id list is empty, which would make this check vacuous"
    missing = missing_lens_sections(text, LENS_IDS)
    assert not missing, f"{AGGREGATED_PROMPT} has no section for: {missing}"


def test_lens_reviewer_states_no_thresholds() -> None:
    """The catalogue owns the strictness ladder; a copy here would be a second source.

    Matched as a pattern rather than three exact strings, so ``8``, ``8.5`` and ``0.8`` are
    caught too -- the earlier form checked only the three spellings the catalogue happens to use
    today.
    """
    text = (ROLES_DIR / AGGREGATED_PROMPT).read_text(encoding="utf-8")
    found = THRESHOLD_PATTERN.findall(text)
    assert not found, (
        f"{AGGREGATED_PROMPT} names strictness values {found}; the ladder lives in the catalogue"
    )


def test_planner_and_delivery_manager_emit_several_contracts() -> None:
    """The two roles that forced ``emits`` to be a list, asserted on the real files."""
    planner = parse_frontmatter(ROLES_DIR / "planner.md")["emits"]
    delivery_manager = parse_frontmatter(ROLES_DIR / "delivery-manager.md")["emits"]
    assert isinstance(planner, list) and len(planner) == 2
    assert isinstance(delivery_manager, list) and len(delivery_manager) == 5


def test_lens_reviewer_emits_nothing_of_its_own() -> None:
    assert parse_frontmatter(ROLES_DIR / AGGREGATED_PROMPT)["emits"] == []


# --- seeded fixtures: each one calls the same checker the real test calls ----------------


def test_seeded_missing_stop_rule_fires() -> None:
    assert not has_stop_rule_heading("---\nrole: X\n---\n\n## Role\n\nbody\n")


def test_seeded_quoted_heading_is_not_a_heading() -> None:
    """The anchoring that makes the stop-rule check mean what it says."""
    text = "---\nrole: X\n---\n\nSee `### Stop rule` above, and | `### Stop rule` | in a table.\n"
    assert "### Stop rule" in text
    assert not has_stop_rule_heading(text)


def test_seeded_headings_out_of_order_fires() -> None:
    text = "## Output contract\n\n### Stop rule\n\n## Role\n\n## Inputs from the run record\n"
    assert missing_headings(text) == ["<out of order>"]


def test_seeded_headings_in_order_pass() -> None:
    filler = "Enough prose under the heading to count as a real section, not a bare heading.\n"
    text = (
        f"## Role\n\n{filler}\n## Inputs from the run record\n\n{filler}\n"
        f"## Output contract\n\n{filler}\n### Stop rule\n\n{filler}"
    )
    assert missing_headings(text) == []


def test_seeded_empty_section_fires() -> None:
    """A file of four headings with nothing under them must not pass R2."""
    text = "## Role\n\n## Inputs from the run record\n\n## Output contract\n\n### Stop rule\n"
    assert missing_headings(text) == [
        "## Role <empty>",
        "## Inputs from the run record <empty>",
        "## Output contract <empty>",
        "### Stop rule <empty>",
    ]


def test_seeded_heading_inside_a_fence_does_not_count() -> None:
    """Every prompt embeds a fenced handoff example; a heading there is not a real section."""
    text = "# Title\n\n```markdown\n### Stop rule\n```\n"
    assert "### Stop rule" in text
    assert not has_stop_rule_heading(text)


def test_seeded_retired_vocabulary_fires() -> None:
    assert retired_vocabulary("Report hard-fail on error.") == ["hard-fail"]
    assert retired_vocabulary("See the team-execution plugin.") == ["team-execution"]
    assert retired_vocabulary("A clean prompt that passes and warns.") == []


def test_seeded_missing_lens_section_fires() -> None:
    body = "".join(f"#### {lens}\n\ntext\n\n" for lens in LENS_IDS[:-1])
    assert missing_lens_sections(body, LENS_IDS) == [LENS_IDS[-1]]
    assert missing_lens_sections(body, LENS_IDS[:-1]) == []


def test_seeded_emits_rules_fire() -> None:
    """Shape, membership, producership and the empty-list rule, each proven to fire."""
    assert emits_violations("planner", "dispatch", "planner.md")[0].startswith("emits must be")
    assert emits_violations("planner", [], "planner.md")[0].startswith("emits is empty")
    assert emits_violations("lens_reviewer", [], AGGREGATED_PROMPT) == []
    assert "not a lifecycle handoff contract" in emits_violations("planner", ["nope"], "p.md")[0]
    assert "produced by" in emits_violations("product", ["run-record"], "product.md")[0]
    assert emits_violations("planner", ["planner-to-orchestrator"], "planner.md") == []


def test_seeded_repair_reuse_is_licensed() -> None:
    """Both repair roles may claim the initial worker's contract; nobody else may."""
    for role in REUSE_LICENSED_ROLES:
        assert emits_violations(role, [REUSED_CONTRACT], "r.md") == []
    assert emits_violations("release_worker", [REUSED_CONTRACT], "r.md") != []


def test_seeded_parser_keeps_oddly_indented_list_items() -> None:
    """The defect that made a mis-indented list look like a legitimately empty one.

    The fix is to accept the item at any indent rather than to reject the file: dropping it
    silently turned a role that emits one contract into one that appears to emit none, and the
    empty-``emits`` rule then accepted it.
    """
    for spelling in ("---\nemits:\n    - a\n---\nb\n", "---\nemits:\n\t- a\n---\nb\n"):
        assert parse_frontmatter(spelling)["emits"] == ["a"]


def test_seeded_parser_rejects_a_list_item_with_no_key() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\n- orphan\n---\nbody\n")


def test_seeded_parser_rejects_duplicate_key() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nemits:\n  - a\nemits:\n  - b\n---\nbody\n")


def test_seeded_parser_rejects_junk_line() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nrole: X\njust some prose\n---\nbody\n")


def test_seeded_parser_accepts_both_empty_list_spellings() -> None:
    assert parse_frontmatter("---\nemits: []\n---\nb\n")["emits"] == []
    assert parse_frontmatter("---\nemits:\nsource: s\n---\nb\n")["emits"] == []


def test_seeded_parser_keeps_colons_in_values() -> None:
    parsed = parse_frontmatter("---\nsource: sdlc@67845cdd docs/a.md: the thing\n---\nb\n")
    assert parsed["source"] == "sdlc@67845cdd docs/a.md: the thing"


def test_seeded_parser_returns_empty_for_no_frontmatter() -> None:
    """Absence is not an error here -- the required-key check reports it, loudly."""
    assert parse_frontmatter("# Just a heading\n") == {}
