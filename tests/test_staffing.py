"""Guards for the one staffing component in fleet-core (issue #1021).

The component sits on a path every subagent spawn reads, so the properties under test are the
ones a wrong answer would corrupt silently: the work-shape defaults come across unchanged from
the policy they were merged from, the per-repository overlay wins over that policy, and an
off-palette model, an unsupported model-effort pair, an unknown work shape and an unknown role
each fail loud rather than degrading to a default.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
FLEET_CORE_SCRIPTS = REPO_ROOT / "plugins" / "fleet-core" / "scripts"
STAFFING_SCRIPT = FLEET_CORE_SCRIPTS / "fleet_commons" / "staffing.py"

sys.path.insert(0, str(FLEET_CORE_SCRIPTS))

from fleet_commons import staffing  # noqa: E402
from fleet_commons.staffing import StaffingError  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STAFFING_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# The policy default per work shape (R5) — the card's first acceptance criterion.
# ---------------------------------------------------------------------------


def test_resolve_shape_returns_the_policy_default() -> None:
    """Judgment work resolves to opus at high effort, read-only survey to sonnet at low."""
    judgment = staffing.resolve_shape("judgment")
    assert (judgment.model, judgment.effort) == ("opus", "high")
    assert judgment.source == "policy"

    survey = staffing.resolve_shape("read-only-survey")
    assert (survey.model, survey.effort) == ("sonnet", "low")
    assert survey.source == "policy"


def test_cli_prints_the_short_tier_form() -> None:
    """The card asserts this exact text, so the default output is the pair, not a JSON object."""
    assert _run("resolve", "--shape", "judgment").stdout.strip() == "opus/high"
    assert _run("resolve", "--shape", "read-only-survey").stdout.strip() == "sonnet/low"


def test_cli_json_carries_the_whole_decision_record() -> None:
    """The short form is a projection of the record, never a separately computed answer."""
    result = _run("resolve", "--shape", "judgment", "--json")
    assert result.returncode == 0
    record = json.loads(result.stdout)
    assert record["model"] == "opus"
    assert record["effort"] == "high"
    assert record["tier"] == "opus/high"
    assert record["source"] == "policy"
    assert record["work_shape"] == "judgment"


def test_every_work_shape_resolves_to_a_runnable_tier() -> None:
    """No shape in the registry resolves to a pair the model cannot run."""
    for shape in staffing.work_shapes():
        decision = staffing.resolve_shape(shape)
        assert decision.model in staffing.MODELS
        assert decision.effort in staffing.EFFORTS


# ---------------------------------------------------------------------------
# The repository overlay wins over the policy default (R6).
# ---------------------------------------------------------------------------


def _write_overlay(root: pathlib.Path, payload: object) -> None:
    saga_dir = root / ".saga"
    saga_dir.mkdir(parents=True, exist_ok=True)
    (saga_dir / "tier-defaults.json").write_text(json.dumps(payload), encoding="utf-8")


def test_overlay_wins_for_the_shapes_it_names(tmp_path: pathlib.Path) -> None:
    """A pinned shape comes from the overlay; an unpinned one still comes from the policy."""
    _write_overlay(tmp_path, {"mechanical": {"model": "haiku", "effort": "low"}})

    pinned = staffing.resolve_shape("mechanical", root=tmp_path)
    assert (pinned.model, pinned.effort) == ("haiku", "low")
    assert pinned.source == "overlay"

    unpinned = staffing.resolve_shape("judgment", root=tmp_path)
    assert (unpinned.model, unpinned.effort) == ("opus", "high")
    assert unpinned.source == "policy"


def test_absent_overlay_resolves_cleanly_from_the_policy(tmp_path: pathlib.Path) -> None:
    """No overlay file is the normal case, not an error."""
    assert staffing.load_overlay(root=tmp_path) == {}
    assert staffing.resolve_shape("judgment", root=tmp_path).source == "policy"


# ---------------------------------------------------------------------------
# Failing loud (R14).
# ---------------------------------------------------------------------------


def test_unknown_work_shape_raises_with_the_offending_value() -> None:
    with pytest.raises(StaffingError, match="not-a-shape"):
        staffing.resolve_shape("not-a-shape")


def test_cli_exits_non_zero_on_an_unknown_work_shape() -> None:
    result = _run("resolve", "--shape", "not-a-shape")
    assert result.returncode == 2
    assert "not-a-shape" in result.stderr


def test_overlay_naming_an_unknown_shape_raises(tmp_path: pathlib.Path) -> None:
    _write_overlay(tmp_path, {"not-a-shape": {"model": "opus", "effort": "high"}})
    with pytest.raises(StaffingError, match="not-a-shape"):
        staffing.load_overlay(root=tmp_path)


def test_overlay_with_an_off_palette_model_raises(tmp_path: pathlib.Path) -> None:
    _write_overlay(tmp_path, {"judgment": {"model": "gpt-9", "effort": "high"}})
    with pytest.raises(StaffingError, match="gpt-9"):
        staffing.load_overlay(root=tmp_path)


def test_overlay_with_an_unsupported_model_effort_pair_raises(tmp_path: pathlib.Path) -> None:
    """haiku's ceiling is high, so haiku/xhigh is not a runnable pair."""
    _write_overlay(tmp_path, {"judgment": {"model": "haiku", "effort": "xhigh"}})
    with pytest.raises(StaffingError, match="unrunnable"):
        staffing.load_overlay(root=tmp_path)


def test_malformed_overlay_raises_rather_than_being_ignored(tmp_path: pathlib.Path) -> None:
    saga_dir = tmp_path / ".saga"
    saga_dir.mkdir(parents=True)
    (saga_dir / "tier-defaults.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(StaffingError, match="not valid JSON"):
        staffing.load_overlay(root=tmp_path)


def test_overlay_whose_top_level_is_not_an_object_raises(tmp_path: pathlib.Path) -> None:
    _write_overlay(tmp_path, ["judgment"])
    with pytest.raises(StaffingError, match="must be an object"):
        staffing.load_overlay(root=tmp_path)


# ---------------------------------------------------------------------------
# The advisory suggestion is recorded and never applied (R15, KTD9).
# ---------------------------------------------------------------------------


def test_an_agreeing_suggestion_is_recorded_beside_the_choice() -> None:
    decision = staffing.resolve_shape("judgment", suggestion={"model": "opus", "effort": "high"})
    assert decision.suggestion == {"model": "opus", "effort": "high"}
    assert (decision.model, decision.effort) == ("opus", "high")


def test_a_disagreeing_suggestion_is_recorded_and_changes_nothing() -> None:
    """This is the property that keeps the typed judgment advisory by construction."""
    decision = staffing.resolve_shape("judgment", suggestion={"model": "haiku", "effort": "low"})
    assert decision.suggestion == {"model": "haiku", "effort": "low"}
    assert (decision.model, decision.effort) == ("opus", "high")


def test_an_off_palette_suggestion_raises() -> None:
    with pytest.raises(StaffingError, match="suggestion model"):
        staffing.resolve_shape("judgment", suggestion={"model": "gpt-9", "effort": "high"})


def test_no_suggestion_leaves_the_field_absent_from_the_record() -> None:
    assert "suggestion" not in staffing.resolve_shape("judgment").as_dict()


# ---------------------------------------------------------------------------
# The registry itself.
# ---------------------------------------------------------------------------


def test_staffing_registry_is_the_one_data_file() -> None:
    """The two files it absorbed are gone, and the blocks they held are present here."""
    fleet_commons = FLEET_CORE_SCRIPTS / "fleet_commons"
    assert not (fleet_commons / "models.json").exists()
    assert not (fleet_commons / "tier_policy.json").exists()

    registry = staffing.load_staffing()
    for block in ("models", "efforts", "scalar_efforts", "work_shapes", "execution_classes"):
        assert block in registry, f"staffing.json is missing the {block!r} block"


# ---------------------------------------------------------------------------
# The vendor palette (R9, R10, KTD5, KTD11).
# ---------------------------------------------------------------------------

LAUNCHER = (
    REPO_ROOT
    / "plugins"
    / "agent-launcher"
    / "skills"
    / "agent-launcher"
    / "scripts"
    / "launcher.py"
)


def _launcher_vendor_flags() -> dict[str, dict[str, str]]:
    """The launcher's own vendor table, read from source without importing the launcher."""
    import ast

    tree = ast.parse(LAUNCHER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "VENDOR_FLAGS":
            return ast.literal_eval(node.value)  # type: ignore[arg-type]
    raise AssertionError("VENDOR_FLAGS not found in the agent-launcher launcher module")


def test_palette_vendor_keys_equal_the_launcher_kind_list() -> None:
    """A set comparison, so adding a kind to the launcher reds this rather than passing silently.

    This is the forcing function for the hermes exclusion too: asserting that hermes is *absent*
    would keep passing after hermes was added, which is why the pin is equality against the
    launcher's own table (KTD5).
    """
    assert set(staffing.vendors()) == set(_launcher_vendor_flags())
    assert "hermes" not in staffing.vendors()


def test_every_vendor_names_at_least_one_model_or_records_why_not() -> None:
    """Every entry is described; only a supported runtime must carry an effort list.

    The effort half is scoped to supported runtimes on purpose: KTD11 refuses to invent an
    accepted-effort list for a vendor whose launch arguments nobody has verified.
    """
    for name, row in staffing.vendors().items():
        if row["runtime_supported"]:
            assert row["models"], f"{name}: a supported runtime must name its models"
            assert row["accepted_efforts"], f"{name}: a supported runtime must name its efforts"
        else:
            assert row["unsupported_reason"], f"{name}: an unsupported vendor must record why"


def test_opencode_is_in_the_palette_but_not_a_supported_runtime() -> None:
    """KTD11: visible in the data, absent from the resolver, and unchanged at the call site."""
    from fleet_commons import tier_resolver

    palette = staffing.vendors()
    assert palette["opencode"]["runtime_supported"] is False
    assert "opencode" not in tier_resolver.SUPPORTED_RUNTIMES
    with pytest.raises(tier_resolver.TierResolverError):
        tier_resolver.collapse_effort_for_runtime("opencode", "high")


def test_supported_runtimes_derive_from_the_palette() -> None:
    from fleet_commons import tier_resolver

    expected = tuple(name for name, row in staffing.vendors().items() if row["runtime_supported"])
    assert expected == tier_resolver.SUPPORTED_RUNTIMES


@pytest.mark.parametrize(
    ("runtime", "requested", "expected"),
    [
        ("claude", "max", "max"),
        ("codex", "max", "max"),
        ("qwen", "max", "max"),
        ("grok", "max", "xhigh"),
        ("muse", "max", "xhigh"),
        ("agy", "max", "high"),
        ("agy", "xhigh", "high"),
        ("grok", "high", "high"),
    ],
)
def test_effort_collapse_is_unchanged_by_the_move_into_data(
    runtime: str, requested: str, expected: str
) -> None:
    """The values recorded in DECISIONS {#effort-collapse-max}, held against the data file."""
    from fleet_commons import tier_resolver

    assert tier_resolver.collapse_effort_for_runtime(runtime, requested) == expected


def test_effort_application_mode_is_unchanged_by_the_move_into_data() -> None:
    """Qwen alone applies effort in session, because it has no launch flag."""
    palette = staffing.vendors()
    assert palette["qwen"]["effort_application"] == "in_session"
    for name in ("claude", "codex", "grok", "muse", "agy"):
        assert palette[name]["effort_application"] == "argv"


def test_an_unknown_vendor_raises_rather_than_clamping() -> None:
    from fleet_commons import tier_resolver

    with pytest.raises(tier_resolver.TierResolverError, match="not-a-vendor"):
        tier_resolver.collapse_effort_for_runtime("not-a-vendor", "high")
