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
            flags: dict[str, dict[str, str]] = ast.literal_eval(node.value)  # type: ignore[arg-type]
            return flags
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


# ---------------------------------------------------------------------------
# Roles, capability ratings and the explain view (R8, R11, KTD6, KTD10).
# ---------------------------------------------------------------------------

ENGINE_REGISTRY = REPO_ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"

KTD10_ROLES = {
    "planner": "long-form-writing",
    "plan-reviewer": "long-form-writing",
    "worker": "code-generation",
    "lens-reviewer": "adversarial-review",
    "functional-tester": "debug",
    "release-worker": "code-generation",
    "merging-worker": "code-generation",
}


def test_the_seven_roles_and_their_capabilities_are_the_ones_the_plan_fixed() -> None:
    table = staffing.roles()
    assert set(table) == set(KTD10_ROLES)
    for role, capability in KTD10_ROLES.items():
        assert table[role]["capability"] == capability


def test_every_role_resolves_to_a_vendor_model_and_effort() -> None:
    for role in staffing.roles():
        decision = staffing.resolve_role(role)
        assert decision.vendor in staffing.vendors()
        assert decision.model in staffing.MODELS
        assert decision.effort in staffing.EFFORTS
        assert decision.role == role


def test_explain_lists_candidates_strongest_rating_first() -> None:
    """The card's third acceptance criterion, as the ordering the ranking must produce."""
    rows = staffing.candidates_for("functional-tester")
    assert len(rows) >= 2
    strengths = [staffing.RATINGS.index(row["rating"]) for row in rows]
    assert strengths == sorted(strengths)
    for row in rows:
        assert row["rating"] in staffing.RATINGS
        assert row["trust_tier"]


def test_equal_ratings_break_on_the_cheaper_cost_and_speed_rank() -> None:
    """The registry's own tie-break rule: rating dominates, cost and speed only separates ties."""
    rows = staffing.candidates_for("functional-tester")
    for earlier, later in zip(rows, rows[1:], strict=False):
        if earlier["rating"] == later["rating"]:
            assert earlier["cost_speed_rank"] <= later["cost_speed_rank"]


def test_no_role_produces_an_empty_candidate_list() -> None:
    """Every role maps onto a capability the registry actually rates (KTD10)."""
    for role in staffing.roles():
        assert staffing.candidates_for(role), f"{role}: no executor rates its capability"


def test_every_declared_capability_is_rated_by_at_least_one_engine_row() -> None:
    """The migrated ratings leave no capability declared but unrated."""
    ratings = staffing.capability_ratings()
    rated = {
        capability
        for engine in ratings["engines"].values()
        for capability in (engine.get("capability_profile") or {})
    }
    unrated = [capability for capability in ratings["capabilities"] if capability not in rated]
    assert unrated == [], f"declared but unrated capabilities: {unrated}"


def test_a_role_whose_capability_nobody_rates_yields_an_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data, not a raise — the path an unrated role would take if the registry ever had one.

    Exercised directly rather than asserted about the shipped data, because every capability the
    registry declares is currently rated by at least one row.
    """
    monkeypatch.setattr(
        staffing,
        "roles",
        lambda registry=None: {"orphan": {"work_shape": "judgment", "capability": "telepathy"}},
    )
    assert staffing.candidates_for("orphan") == ()
    decision = staffing.resolve_role("orphan")
    assert (decision.model, decision.effort) == ("opus", "high")


def test_unknown_role_raises_with_the_offending_value() -> None:
    with pytest.raises(StaffingError, match="not-a-role"):
        staffing.resolve_role("not-a-role")


def test_cli_explain_exits_non_zero_on_an_unknown_role() -> None:
    result = _run("explain", "--role", "not-a-role")
    assert result.returncode == 2
    assert "not-a-role" in result.stderr


def test_cli_explain_prints_the_candidates_in_rating_order() -> None:
    result = _run("explain", "--role", "functional-tester")
    assert result.returncode == 0
    prefixes = ("  STRONG", "  MODERATE", "  WEAK")
    ratings = [line.split()[0] for line in result.stdout.splitlines() if line.startswith(prefixes)]
    assert ratings
    assert ratings == sorted(ratings, key=staffing.RATINGS.index)


def test_cli_resolve_rejects_passing_both_a_shape_and_a_role() -> None:
    result = _run("resolve", "--shape", "judgment", "--role", "planner")
    assert result.returncode == 2
    assert "exactly one" in result.stderr


def test_migrated_ratings_match_the_engine_registry_while_both_exist() -> None:
    """KTD6: the ratings are copied, so a parity test is what stops the copy drifting.

    This test is deleted together with engine-registry.yaml when issue 1030 removes it.
    """
    yaml = pytest.importorskip("yaml")
    registry = yaml.safe_load(ENGINE_REGISTRY.read_text(encoding="utf-8"))
    migrated = staffing.capability_ratings()

    assert migrated["capabilities"] == list(registry["capabilities"])

    for name, row in registry["model_families"].items():
        assert migrated["model_families"][name]["capability_profile"] == row["capability_profile"]

    for row in registry["engines"]:
        key = f"{row['engine_id']}/{row['variant']}"
        copied = migrated["engines"][key]
        assert copied["trust_tier"] == row["trust_tier"]
        assert copied["cost_speed_rank"] == row["cost_speed_rank"]
        assert copied["model_identity"] == row["model_identity"]
        assert copied["capability_profile"] == row.get("capability_profile", {})


# ---------------------------------------------------------------------------
# Lens staffing and the qualification ledger (R7, R12, R13, KTD4).
# ---------------------------------------------------------------------------

CATALOGUE_VERSION = "1.0.0"


def _fake_checkout(
    root: pathlib.Path,
    *,
    entries: list[dict[str, object]] | None = None,
    lenses: list[dict[str, object]] | None = None,
    catalogue_version: str = CATALOGUE_VERSION,
) -> pathlib.Path:
    """A software-development-lifecycle checkout holding just the two files the resolver reads."""
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "executor-verifications.json").write_text(
        json.dumps({"schema": "executor_verifications.v1", "entries": entries or []}),
        encoding="utf-8",
    )
    (config / "lens-catalogue.json").write_text(
        json.dumps(
            {
                "version": catalogue_version,
                "lenses": lenses
                or [
                    {"id": "security", "scorable": True, "always_on": True},
                    {"id": "correctness", "scorable": True, "always_on": True},
                    {"id": "privacy", "scorable": False, "always_on": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def _qualified_entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "lens": "security",
        "vendor": "claude",
        "model": "opus",
        "effort": "high",
        "catalogue_version": CATALOGUE_VERSION,
        "fixtures_passed": 12,
        "fixtures_total": 12,
    }
    entry.update(overrides)
    return entry


def test_a_full_fixture_entry_at_the_current_version_qualifies(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry()])
    decision = staffing.resolve_role("lens-reviewer", lens="security", checkout=checkout)
    assert decision.qualification is not None
    assert decision.qualification.status == staffing.QUALIFIED
    assert decision.vendor == "claude"
    assert (decision.model, decision.effort) == ("opus", "high")


def test_the_real_ledger_is_empty_so_every_lens_reads_documented_policy() -> None:
    """Against the shipped ledger, which records that it is empty on purpose."""
    entries = staffing.verification_ledger()
    catalogue, _ = staffing.lens_catalogue()
    if not catalogue:
        pytest.skip("no software-development-lifecycle checkout on this host")
    assert entries == [], "this test describes an empty ledger; it has entries now"
    for lens in ("security", "correctness"):
        qualification = staffing.qualify_lens(lens, vendor="claude", model="opus", effort="high")
        assert qualification.status == staffing.DOCUMENTED_POLICY
        assert "empty" in qualification.reason


def test_a_partial_fixture_pass_is_refused_not_rounded_up(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(
        tmp_path, entries=[_qualified_entry(fixtures_passed=11, fixtures_total=12)]
    )
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert "11 of 12" in qualification.reason


def test_an_entry_against_an_older_catalogue_version_is_not_carried_forward(
    tmp_path: pathlib.Path,
) -> None:
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry(catalogue_version="0.9.0")])
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert "never carried forward" in qualification.reason


def test_an_unscorable_lens_never_consults_the_ledger(tmp_path: pathlib.Path) -> None:
    """A lens the catalogue marks unscorable has no fixtures, so there is nothing to qualify."""
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry(lens="privacy")])
    qualification = staffing.qualify_lens(
        "privacy", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert "unscorable" in qualification.reason


def test_an_entry_for_a_different_executor_does_not_qualify(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry(model="sonnet")])
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert "no ledger entry qualifies" in qualification.reason


def test_a_checkout_with_no_ledger_reads_documented_policy(tmp_path: pathlib.Path) -> None:
    """Absent files are data, not an exception: a missing sibling must not break every spawn."""
    config = tmp_path / "config"
    config.mkdir(parents=True)
    (config / "lens-catalogue.json").write_text(
        json.dumps(
            {"version": CATALOGUE_VERSION, "lenses": [{"id": "security", "scorable": True}]}
        ),
        encoding="utf-8",
    )
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=tmp_path
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert "empty" in qualification.reason


def test_an_unparseable_ledger_reads_documented_policy(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(tmp_path)
    (checkout / "config" / "executor-verifications.json").write_text("{not json", encoding="utf-8")
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert qualification.reason


def test_an_absent_checkout_reads_documented_policy_and_never_raises(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R13: the resolver sits on a path every spawn reads, so absence cannot be fatal."""
    monkeypatch.setenv(staffing.SDLC_PATH_ENV, str(tmp_path / "nowhere"))
    monkeypatch.setattr(staffing, "DEFAULT_SDLC_PATH", tmp_path / "also-nowhere")
    qualification = staffing.qualify_lens("security", vendor="claude", model="opus", effort="high")
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert staffing.SDLC_PATH_ENV in qualification.reason


def test_the_checkout_ladder_prefers_the_environment_variable(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ladder mission-control already uses: explicit, then the variable, then the default."""
    configured = _fake_checkout(tmp_path / "configured")
    monkeypatch.setenv(staffing.SDLC_PATH_ENV, str(configured))
    assert staffing.sdlc_root() == configured

    explicit = _fake_checkout(tmp_path / "explicit")
    assert staffing.sdlc_root(explicit) == explicit


def test_an_unknown_lens_raises_with_the_offending_value(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(tmp_path)
    with pytest.raises(StaffingError, match="not-a-lens"):
        staffing.qualify_lens(
            "not-a-lens", vendor="claude", model="opus", effort="high", checkout=checkout
        )


def test_a_lens_on_a_non_reviewing_role_raises() -> None:
    with pytest.raises(StaffingError, match="reviews nothing"):
        staffing.resolve_role("worker", lens="security")


def test_cli_resolve_role_with_a_lens_prints_vendor_tier_and_status() -> None:
    """The card's second acceptance criterion."""
    result = _run("resolve", "--role", "lens-reviewer", "--lens", "security")
    assert result.returncode == 0
    parts = result.stdout.split()
    assert parts[0] in staffing.vendors()
    assert "/" in parts[1]
    assert parts[2] in {staffing.QUALIFIED, staffing.DOCUMENTED_POLICY}


def test_cli_explain_accepts_the_lens_the_card_verification_block_uses() -> None:
    """The card runs explain --role lens-reviewer --lens correctness; it must not be rejected."""
    result = _run("explain", "--role", "lens-reviewer", "--lens", "correctness")
    assert result.returncode == 0, result.stderr
    assert "lens-reviewer" in result.stdout


def test_cli_rejects_a_lens_on_a_work_shape() -> None:
    result = _run("resolve", "--shape", "judgment", "--lens", "security")
    assert result.returncode == 2
    assert "reviewing role" in result.stderr
