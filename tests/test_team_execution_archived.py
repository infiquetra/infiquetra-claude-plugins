"""The team-execution plugin is archived, and nothing still reaches for it.

Issue 1030. The guard is named for what it guards and checks the plugin in **every syntax a caller
could use**, following `tests/test_team_emitter_and_spec_table_removed.py` (issue 1026): a directory
that exists, a marketplace entry, an import of one of its modules, a `spec_from_file_location` by
path, a plugin-resolution call naming it, and a bare mention on a command line in a skill. A removal
test that only checks ``not path.exists()`` passes while a surviving skill still tells an agent to
run one of its scripts.

It also follows `tests/test_no_lease_broker_readd.py` (defect #642) in scanning the **shim-resolved**
roots rather than only the working tree, because a stale installed plugin tree can resurrect a plugin
a repository check calls gone.

The scanner's own two self-tests are at the bottom: one proves it fires on each actionable syntax,
the other proves it does not fire on a historical mention in a changelog or a dated document. Without
that pair, a scanner that silently matched nothing would report success forever.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugins" / "team-execution"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

#: The plugin, and the module names that lived only inside it. Each is checked by name, so a
#: re-add fails on the name rather than on a count a differently-named replacement would satisfy.
ARCHIVED_PLUGIN = "team-execution"
ARCHIVED_MODULES: tuple[str, ...] = (
    "artifact_pointer",
    "consensus_advisory",
    "dispatch_settlement_adapter",
    "liveness_protocol",
    "posture_check",
)

#: Where a live caller could reach for it. Documentation and changelogs are deliberately excluded:
#: a historical mention is a record, not a reach.
LIVE_ROOTS: tuple[str, ...] = ("plugins", "tests", "scripts", "tools", ".github")

#: Files that may name it because their subject IS its removal, or because they are history.
EXEMPT_SUFFIXES: tuple[str, ...] = ("CHANGELOG.md",)
EXEMPT_NAMES: frozenset[str] = frozenset({Path(__file__).name})


def _actionable_patterns(name: str) -> tuple[re.Pattern[str], ...]:
    """Every syntax by which a caller could actually reach the archived plugin."""
    escaped = re.escape(name)
    return (
        re.compile(rf"(?:^|\W)import\s+{escaped}\b", re.M),
        re.compile(rf"(?:^|\W)from\s+{escaped}\s+import\b", re.M),
        re.compile(rf"spec_from_file_location\(\s*['\"]{escaped}['\"]"),
        re.compile(rf"plugins/team-execution/[A-Za-z0-9_./-]*{escaped}"),
        re.compile(rf"resolve_plugin_root\(\s*['\"]{escaped}['\"]"),
        # The bare filename. A path built by joining segments across lines -- which is how
        # tests/test_intent_envelope.py reached posture_check.py -- matches none of the patterns
        # above, and the full-suite run found it after this guard had reported clean. A live file
        # naming the script file is reaching for it whatever syntax assembles the path.
        re.compile(rf"\b{escaped}\.py\b"),
    )


def _plugin_patterns() -> tuple[re.Pattern[str], ...]:
    return (
        re.compile(r"plugins/team-execution/"),
        re.compile(r"resolve_plugin_root\(\s*['\"]team-execution['\"]"),
        re.compile(r'"name"\s*:\s*"team-execution"'),
        re.compile(r"subagent_type:\s*team-execution:"),
    )


def _live_files() -> list[Path]:
    files: list[Path] = []
    for root in LIVE_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".md", ".json", ".yaml", ".yml"):
                continue
            if path.name in EXEMPT_NAMES or path.name.endswith(EXEMPT_SUFFIXES):
                continue
            files.append(path)
    return files


def _offenders(patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    hits: list[str] = []
    for path in _live_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern.search(text):
                hits.append(f"{path.relative_to(REPO_ROOT)}: {pattern.pattern}")
                break
    return sorted(hits)


def test_the_plugin_directory_is_gone() -> None:
    assert not PLUGIN_DIR.exists(), f"{PLUGIN_DIR} is back"


def test_no_marketplace_entry_names_it() -> None:
    names = [entry["name"] for entry in json.loads(MARKETPLACE.read_text())["plugins"]]
    assert ARCHIVED_PLUGIN not in names, f"the marketplace still lists {ARCHIVED_PLUGIN}"


def test_the_marketplace_holds_the_fourteen_surviving_plugins() -> None:
    """A count beside the name check: an entry removed by hand could take a neighbour with it."""
    names = [entry["name"] for entry in json.loads(MARKETPLACE.read_text())["plugins"]]
    assert len(names) == len(set(names)), f"duplicate marketplace entries: {names}"
    assert len(names) == 14, names


@pytest.mark.parametrize("module", ARCHIVED_MODULES)
def test_no_live_file_reaches_for_an_archived_module_in_any_syntax(module: str) -> None:
    offenders = _offenders(_actionable_patterns(module))
    assert not offenders, f"{module} is still reached for by: {offenders}"


def test_no_live_file_reaches_for_the_plugin_in_any_syntax() -> None:
    offenders = _offenders(_plugin_patterns())
    assert not offenders, f"the archived plugin is still reached for by: {offenders}"


def test_no_vendored_shim_survives_under_the_deleted_tree() -> None:
    """The vendored fleet-commons shim was the plugin's own copy; it goes with the plugin."""
    assert not list(REPO_ROOT.glob("plugins/team-execution/**/fleet_commons_shim.py"))


# ---------------------------------------------------------------------------
# The scanner's own two self-tests -- without these, a scanner matching nothing
# would report success forever.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample",
    (
        "import artifact_pointer",
        "from artifact_pointer import store",
        'spec_from_file_location("artifact_pointer", path)',
        "python3 plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py store",
    ),
)
def test_the_scanner_fires_on_every_actionable_syntax(sample: str) -> None:
    patterns = _actionable_patterns("artifact_pointer")
    assert any(pattern.search(sample) for pattern in patterns), sample


@pytest.mark.parametrize(
    "sample",
    (
        "The team-execution plugin was archived by issue 1030.",
        "- **Archived (4.0.0).** team_execution's reviewer prompts became roles.",
        "Its 25 agent prompts live on in the roles library.",
    ),
)
def test_the_scanner_does_not_fire_on_a_historical_mention(sample: str) -> None:
    patterns = _actionable_patterns("artifact_pointer") + _plugin_patterns()
    assert not any(pattern.search(sample) for pattern in patterns), sample
