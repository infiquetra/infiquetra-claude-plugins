"""Guards for the one staffing component in fleet-core (issue #1021).

The component sits on a path every subagent spawn reads, so the properties under test are the
ones a wrong answer would corrupt silently: the work-shape defaults come across unchanged from
the policy they were merged from, the per-repository overlay wins over that policy, and an
off-palette model, an unsupported model-effort pair, an unknown work shape and an unknown role
each fail loud rather than degrading to a default.
"""

from __future__ import annotations

import json
import os
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

#: Named before the autouse fixture uses it, so the isolation reads in one place.
SDLC_ENV_FOR_TESTS = staffing.SDLC_PATH_ENV


@pytest.fixture(autouse=True)
def _isolated_from_machine_state(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """Run every test against constructed state, never against this machine's.

    Two dependencies, both invisible in a diff and both green on a fresh clone:

    The resolver reads ``Path.cwd()/.saga/tier-defaults.json`` whenever a caller omits ``root``.
    That path is gitignored and is where saga writes an operator's confirmed tier overrides, so a
    developer who has ever confirmed one would otherwise see a third of this file go red.

    It also resolves a software-development-lifecycle checkout from ``INFIQUETRA_SDLC_PATH`` or a
    default under the home directory, and asks its lens catalogue whether a lens exists. A
    developer whose catalogue lists different lenses would see the pinned-vendor tests fail on a
    lens the registry does not know. Pointing the variable at an empty directory makes the absent
    checkout the default for every test, which is the documented-policy path; a test that wants a
    catalogue builds one with ``_fake_checkout`` and passes it explicitly.

    A fresh clone hiding either problem is the shape of the flake, not a defence against it.
    """
    cwd = tmp_path_factory.mktemp("isolated")
    monkeypatch.chdir(cwd)
    absent = tmp_path_factory.mktemp("no-sdlc-checkout") / "nowhere"
    monkeypatch.setenv(SDLC_ENV_FOR_TESTS, str(absent))
    return cwd


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the command line under the same isolation the autouse fixture established."""
    environment = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(STAFFING_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=pathlib.Path.cwd(),
        env=environment,
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


def test_supported_runtimes_are_the_six_the_resolver_knew_before_the_move() -> None:
    """Pinned as literals, not recomputed with the implementation's own comprehension.

    Deriving the expectation the way the code derives it cannot detect drift in the vendor data —
    it only proves the comprehension runs. These six names are what tier_resolver carried as a
    module-level literal before issue 1021 moved the palette into data.
    """
    from fleet_commons import tier_resolver

    assert tier_resolver.SUPPORTED_RUNTIMES == ("claude", "codex", "grok", "muse", "qwen", "agy")


def test_accepted_efforts_are_ordered_weakest_first() -> None:
    """``strongest-supported`` returns ``accepted_efforts[-1]``, so the order is load-bearing.

    In Python this order lived in a reviewed literal. As data it is editable, and a list written
    strongest-first would silently make the strongest-supported fallback resolve to the weakest
    rung — which the execution class review-max uses in a live fallback.
    """
    rungs = {name: row["rung"] for name, row in staffing.load_staffing()["scalar_efforts"].items()}
    for name, row in staffing.vendors().items():
        accepted = row["accepted_efforts"]
        ranks = [rungs[effort] for effort in accepted]
        assert ranks == sorted(ranks), (
            f"{name}: accepted_efforts must be weakest-first, got {accepted}"
        )


def test_strongest_supported_resolves_to_each_vendors_top_accepted_rung() -> None:
    from fleet_commons import tier_resolver

    for name, row in staffing.vendors().items():
        if not row["runtime_supported"]:
            continue
        resolved = tier_resolver.collapse_effort_for_runtime(
            name, tier_resolver.STRONGEST_SUPPORTED
        )
        assert resolved == row["accepted_efforts"][-1]


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
    """A reviewing role needs its lens named; every other role resolves on its own."""
    for role in staffing.roles():
        lens = "security" if staffing._is_reviewing_role(role) else None
        decision = staffing.resolve_role(role, lens=lens)
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
    entries: list[object] | None = None,
    lenses: list[object] | None = None,
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


def test_an_empty_ledger_leaves_every_lens_on_documented_policy(tmp_path: pathlib.Path) -> None:
    """The shipped ledger's state, asserted against a constructed copy of it.

    This used to read the operator's own checkout, which made it skip in continuous integration
    and made it red on a developer's machine the day the real ledger recorded its first entry —
    which is the ledger's whole purpose. The property under test is the code's, not the machine's.
    """
    checkout = _fake_checkout(tmp_path, entries=[])
    for lens in ("security", "correctness"):
        qualification = staffing.qualify_lens(
            lens, vendor="claude", model="opus", effort="high", checkout=checkout
        )
        assert qualification.status == staffing.DOCUMENTED_POLICY
        assert "empty" in qualification.reason


def test_the_shipped_ledger_is_still_empty_if_this_host_has_a_checkout() -> None:
    """A separate, explicitly environmental check, so the behavioural test above stays hermetic.

    It skips without a checkout rather than asserting nothing, and it reds the day an executor is
    genuinely qualified — at which point the staffing defaults deserve a fresh look.
    """
    import os as _os

    checkout = staffing.sdlc_root(None) if not _os.environ.get(SDLC_ENV_FOR_TESTS) else None
    if checkout is None:
        pytest.skip("no software-development-lifecycle checkout resolvable on this host")
    assert staffing.verification_ledger(checkout) == []


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


def test_a_vendor_pinned_role_reports_the_pin_without_changing_tier_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vendor is not a tier, so pinning one must not overwrite where the tier came from.

    No shipped role pins a vendor, so the branch is unreachable against the real data and is
    exercised by construction instead — the same pattern the unrated-capability guard uses.
    """
    monkeypatch.setattr(
        staffing,
        "roles",
        lambda registry=None: {
            "pinned": {
                "work_shape": "judgment",
                "capability": "adversarial-review",
                "vendor": "codex",
            }
        },
    )
    decision = staffing.resolve_role("pinned", lens="security")
    assert decision.vendor == "codex"
    assert decision.vendor_pinned_by_role is True
    assert decision.source == "policy"
    assert decision.as_dict()["vendor_pinned_by_role"] is True
    # The pin changes the vendor, so the model must be rendered for that vendor, not left as the
    # Claude-palette name the work shape resolved to.
    assert decision.model == "gpt-5.6-terra"


def test_a_role_row_missing_its_capability_raises_the_modules_own_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed registry must fail with StaffingError, not a bare KeyError."""
    monkeypatch.setattr(
        staffing, "roles", lambda registry=None: {"broken": {"work_shape": "judgment"}}
    )
    with pytest.raises(StaffingError, match="missing a capability"):
        staffing.candidates_for("broken")


# ---------------------------------------------------------------------------
# The qualification decision fails closed (security lens, issue #1021).
#
# qualified is a privilege decision: it is what lets an executor establish a scoring threshold
# for a review lens. Every one of these cases used to be reachable, and two of them granted.
# ---------------------------------------------------------------------------


def test_an_entry_with_no_evidence_fields_does_not_qualify(tmp_path: pathlib.Path) -> None:
    """The fail-open: comparing two absent values with != is false, so a bare identity match
    satisfied both evidence guards and was granted."""
    bare = {"lens": "security", "vendor": "claude", "model": "opus", "effort": "high"}
    checkout = _fake_checkout(tmp_path, entries=[bare])
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_zero_fixtures_out_of_zero_is_not_a_passing_run(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(
        tmp_path, entries=[_qualified_entry(fixtures_passed=0, fixtures_total=0)]
    )
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert "no fixtures" in qualification.reason


@pytest.mark.parametrize(
    "counts",
    [
        {"fixtures_passed": "12", "fixtures_total": "12"},
        {"fixtures_passed": True, "fixtures_total": True},
        {"fixtures_passed": 12.0, "fixtures_total": 12.0},
    ],
)
def test_non_integer_fixture_counts_do_not_qualify(
    tmp_path: pathlib.Path, counts: dict[str, object]
) -> None:
    """A string, a boolean and a float all compare equal to themselves; none is evidence."""
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry(**counts)])
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_a_catalogue_with_no_version_cannot_qualify_anything(tmp_path: pathlib.Path) -> None:
    """Without a version on both sides the qualification is not bound to the fixtures it ran on."""
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry()])
    catalogue = checkout / "config" / "lens-catalogue.json"
    catalogue.write_text(
        json.dumps({"lenses": [{"id": "security", "scorable": True}]}), encoding="utf-8"
    )
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_a_ledger_entry_that_is_not_an_object_is_skipped(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(tmp_path, entries=["not-an-object", _qualified_entry()])
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.QUALIFIED


def test_a_catalogue_lens_that_is_not_an_object_is_skipped(tmp_path: pathlib.Path) -> None:
    """A bare string passes an `"id" in entry` substring test and then fails on the index."""
    checkout = _fake_checkout(tmp_path, lenses=["id", {"id": "security", "scorable": True}])
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_a_ledger_with_non_utf8_bytes_degrades_rather_than_raising(
    tmp_path: pathlib.Path,
) -> None:
    """UnicodeDecodeError is a ValueError, not a JSONDecodeError — the narrower clause let it
    escape the handler written to absorb exactly this."""
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry()])
    (checkout / "config" / "executor-verifications.json").write_bytes(b'{"entries": [\xff\xfe]}')
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_no_absolute_home_path_reaches_a_persisted_reason(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The decision record is handed to a caller to persist, so the operator's username must not
    ride along in it."""
    monkeypatch.setenv(staffing.SDLC_PATH_ENV, str(tmp_path / "nowhere"))
    monkeypatch.setattr(staffing, "DEFAULT_SDLC_PATH", tmp_path / "also-nowhere")
    qualification = staffing.qualify_lens("security", vendor="claude", model="opus", effort="high")
    assert qualification.status == staffing.DOCUMENTED_POLICY
    assert str(pathlib.Path.home()) not in qualification.reason
    assert staffing.SDLC_PATH_ENV in qualification.reason


# ---------------------------------------------------------------------------
# The memoized registry load (security lens, issue #1021).
# ---------------------------------------------------------------------------


def test_the_registry_load_is_memoized_within_a_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """One resolve_role used to read and re-parse the registry five times."""
    reads: list[str] = []
    real_read = pathlib.Path.read_text

    def counting(self: pathlib.Path, *args: object, **kwargs: object) -> str:
        reads.append(self.name)
        return real_read(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pathlib.Path, "read_text", counting)
    staffing.resolve_role("worker")
    assert reads.count("staffing.json") <= 2, f"too many registry reads: {reads}"


def test_an_edited_registry_is_picked_up_rather_than_served_from_cache(
    tmp_path: pathlib.Path,
) -> None:
    """The cache keys on size and modification time, so a rewrite invalidates it."""
    copy = tmp_path / "staffing.json"
    copy.write_text(staffing.STAFFING_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    first = staffing.load_staffing(copy)
    assert first["work_shapes"]["judgment"]["default_model"] == "opus"

    edited = json.loads(copy.read_text(encoding="utf-8"))
    edited["work_shapes"]["judgment"]["default_model"] = "haiku"
    edited["_probe"] = "a value long enough to change the file size as well as its mtime"
    copy.write_text(json.dumps(edited, indent=2), encoding="utf-8")

    second = staffing.load_staffing(copy)
    assert second["work_shapes"]["judgment"]["default_model"] == "haiku"


def test_a_registry_above_the_size_ceiling_is_refused(tmp_path: pathlib.Path) -> None:
    """A registry far larger than the real one is corruption, not an edit."""
    oversized = tmp_path / "staffing.json"
    oversized.write_text("{" + " " * (staffing.MAX_REGISTRY_BYTES + 1) + "}", encoding="utf-8")
    with pytest.raises(StaffingError, match="ceiling"):
        staffing.load_staffing(oversized)


def test_an_unparseable_registry_raises_the_modules_own_error(tmp_path: pathlib.Path) -> None:
    broken = tmp_path / "staffing.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(StaffingError, match="not valid JSON"):
        staffing.load_staffing(broken)


def test_an_absent_registry_raises_the_modules_own_error(tmp_path: pathlib.Path) -> None:
    with pytest.raises(StaffingError, match="unreadable"):
        staffing.load_staffing(tmp_path / "nowhere.json")


# ---------------------------------------------------------------------------
# A vendor-pinned role resolves to a pair that vendor can run (architecture lens, #1021).
#
# The vendor came from the role row and the model from the Claude-only work-shape palette, with
# nothing between them, so a pinned codex role answered "codex opus/high" — a model codex has
# never heard of, with a passing suite.
# ---------------------------------------------------------------------------


def _pinned(vendor: str) -> dict[str, dict[str, str]]:
    return {
        "pinned": {
            "work_shape": "judgment",
            "capability": "adversarial-review",
            "vendor": vendor,
        }
    }


@pytest.mark.parametrize("vendor", ["codex", "grok", "muse", "qwen", "agy"])
def test_a_pinned_vendor_resolves_to_a_model_that_vendor_actually_runs(
    monkeypatch: pytest.MonkeyPatch, vendor: str
) -> None:
    from fleet_commons import tier_resolver

    monkeypatch.setattr(staffing, "roles", lambda registry=None: _pinned(vendor))
    decision = staffing.resolve_role("pinned", lens="security")
    assert decision.vendor == vendor
    assert decision.model in tier_resolver._RUNTIME_MODELS[vendor].values()
    assert decision.effort in staffing.vendors()[vendor]["accepted_efforts"]


def test_a_pinned_vendor_collapses_the_effort_it_cannot_represent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """agy accepts nothing above high, so an xhigh work shape must not answer xhigh.

    Driven through the real path — an overlay pinning the role's work shape to opus/xhigh — rather
    than by patching the resolver that does the translating, which would have tested nothing.
    """
    _write_overlay(tmp_path, {"judgment": {"model": "opus", "effort": "xhigh"}})
    monkeypatch.setattr(staffing, "roles", lambda registry=None: _pinned("agy"))

    claude_tier = staffing.resolve_shape("judgment", root=tmp_path)
    assert claude_tier.effort == "xhigh", "the overlay must supply the effort under test"

    decision = staffing.resolve_role("pinned", lens="security", root=tmp_path)
    assert decision.vendor == "agy"
    assert decision.effort == "high"


def test_translate_for_vendor_collapses_an_effort_the_vendor_cannot_represent() -> None:
    assert staffing.translate_for_vendor("agy", "opus", "xhigh") == (
        "gemini-3.6-flash-high",
        "high",
    )


def test_claude_passes_through_the_translation_unchanged() -> None:
    decision = staffing.resolve_role("worker")
    assert decision.vendor == "claude"
    assert decision.model in staffing.MODELS


def test_a_role_pinning_an_unsupported_runtime_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """opencode is in the palette and deliberately not launchable; an answer naming it would be
    a tier nobody can run."""
    monkeypatch.setattr(staffing, "roles", lambda registry=None: _pinned("opencode"))
    with pytest.raises(StaffingError, match="not a supported runtime"):
        staffing.resolve_role("pinned")


def test_translate_for_vendor_refuses_an_unknown_vendor() -> None:
    with pytest.raises(StaffingError, match="not-a-vendor"):
        staffing.translate_for_vendor("not-a-vendor", "opus", "high")


# ---------------------------------------------------------------------------
# The smaller architecture repairs.
# ---------------------------------------------------------------------------


def test_a_reviewing_role_asked_without_a_lens_is_refused() -> None:
    """The gating field absent is the fail-open shape; ask for the lens instead."""
    with pytest.raises(StaffingError, match="needs a lens"):
        staffing.resolve_role("lens-reviewer")


def test_cli_resolve_of_a_reviewing_role_without_a_lens_exits_non_zero() -> None:
    result = _run("resolve", "--role", "lens-reviewer")
    assert result.returncode == 2
    assert "needs a lens" in result.stderr


def test_a_non_reviewing_role_still_resolves_without_a_lens() -> None:
    assert staffing.resolve_role("worker").qualification is None


def test_a_suggestion_above_the_models_ceiling_is_refused() -> None:
    """The overlay rejected this pair; the suggestion validator accepted it."""
    with pytest.raises(StaffingError, match="unrunnable"):
        staffing.resolve_shape("judgment", suggestion={"model": "haiku", "effort": "xhigh"})


def test_explain_json_carries_candidates_on_the_record_itself() -> None:
    """The dataclass field existed and no producer set it; explain mutated the dict instead."""
    result = _run("explain", "--role", "functional-tester", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["candidates"]
    assert payload["candidates"][0]["rating"] in staffing.RATINGS


# ---------------------------------------------------------------------------
# Repairs from the testing lens: surviving mutants and untested public surface.
# ---------------------------------------------------------------------------


def test_resolve_shape_refuses_an_unknown_vendor() -> None:
    """The sibling entry point took a vendor and neither validated nor translated it."""
    with pytest.raises(StaffingError, match="not-a-vendor"):
        staffing.resolve_shape("judgment", vendor="not-a-vendor")


def test_resolve_shape_refuses_an_unsupported_runtime() -> None:
    with pytest.raises(StaffingError, match="not a supported runtime"):
        staffing.resolve_shape("judgment", vendor="opencode")


@pytest.mark.parametrize(
    ("vendor", "expected_model"),
    [
        ("claude", "opus"),
        ("codex", "gpt-5.6-terra"),
        ("grok", "grok-4.5"),
        ("muse", "muse-spark-1.2-contributor"),
        ("qwen", "qwen3.7-plus"),
        ("agy", "gemini-3.6-flash-high"),
    ],
)
def test_resolve_shape_renders_the_tier_for_the_named_vendor(
    vendor: str, expected_model: str
) -> None:
    """Literal expectations, not a membership test recomputed from the data the code reads.

    A membership assertion passes even when the translation always answers the vendor's cheapest
    model, which is what the lens proved by mutation.
    """
    decision = staffing.resolve_shape("judgment", vendor=vendor)
    assert decision.model == expected_model


@pytest.mark.parametrize(
    ("vendor", "expected_model"),
    [
        ("codex", "gpt-5.6-terra"),
        ("grok", "grok-4.5"),
        ("muse", "muse-spark-1.2-contributor"),
        ("qwen", "qwen3.7-plus"),
        ("agy", "gemini-3.6-flash-high"),
    ],
)
def test_a_pinned_vendor_resolves_to_the_expected_model_not_merely_a_known_one(
    monkeypatch: pytest.MonkeyPatch, vendor: str, expected_model: str
) -> None:
    monkeypatch.setattr(staffing, "roles", lambda registry=None: _pinned(vendor))
    assert staffing.resolve_role("pinned", lens="security").model == expected_model


def test_an_absent_lens_catalogue_degrades_rather_than_raising(tmp_path: pathlib.Path) -> None:
    """The branch that must not raise, on the path whose whole contract is that it never does."""
    config = tmp_path / "config"
    config.mkdir(parents=True)
    (config / "executor-verifications.json").write_text(
        json.dumps({"entries": []}), encoding="utf-8"
    )
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=tmp_path
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_a_catalogue_whose_lenses_is_not_a_list_degrades(tmp_path: pathlib.Path) -> None:
    checkout = _fake_checkout(tmp_path)
    (checkout / "config" / "lens-catalogue.json").write_text(
        json.dumps({"version": CATALOGUE_VERSION, "lenses": "not-a-list"}), encoding="utf-8"
    )
    qualification = staffing.qualify_lens(
        "security", vendor="claude", model="opus", effort="high", checkout=checkout
    )
    assert qualification.status == staffing.DOCUMENTED_POLICY


def test_a_non_claude_executor_qualifies_against_its_own_ledger_entry(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every ledger fixture named claude/opus, so the lookup key itself was unpinned."""
    entry = _qualified_entry(vendor="codex", model="gpt-5.6-terra", effort="high")
    checkout = _fake_checkout(tmp_path, entries=[entry])
    monkeypatch.setattr(staffing, "roles", lambda registry=None: _pinned("codex"))
    decision = staffing.resolve_role("pinned", lens="security", checkout=checkout)
    assert decision.qualification is not None
    assert decision.qualification.status == staffing.QUALIFIED


def test_a_claude_ledger_entry_does_not_qualify_a_codex_executor(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative twin: the vendor and model in the entry are part of the key, not decoration."""
    checkout = _fake_checkout(tmp_path, entries=[_qualified_entry()])
    monkeypatch.setattr(staffing, "roles", lambda registry=None: _pinned("codex"))
    decision = staffing.resolve_role("pinned", lens="security", checkout=checkout)
    assert decision.qualification is not None
    assert decision.qualification.status == staffing.DOCUMENTED_POLICY


def test_an_explicit_checkout_that_is_not_a_directory_does_not_fall_through(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller naming a wrong path must not silently read the operator's real checkout."""
    real = _fake_checkout(tmp_path / "real")
    monkeypatch.setenv(staffing.SDLC_PATH_ENV, str(real))
    assert staffing.sdlc_root(tmp_path / "nowhere") is None


def test_the_cache_notices_a_same_size_rewrite(tmp_path: pathlib.Path) -> None:
    """The modification-time half of the key: the earlier guard changed the size as well."""
    copy = tmp_path / "staffing.json"
    document = json.loads(staffing.STAFFING_PATH.read_text(encoding="utf-8"))
    copy.write_text(json.dumps(document, indent=2), encoding="utf-8")
    assert staffing.load_staffing(copy)["work_shapes"]["judgment"]["default_model"] == "opus"

    document["work_shapes"]["judgment"]["default_model"] = "opus"
    document["work_shapes"]["judgment"]["default_effort"] = "high"
    swapped = json.dumps(document, indent=2)
    document["work_shapes"]["mechanical"]["default_effort"] = "medium"
    assert len(json.dumps(document, indent=2)) == len(swapped)
    copy.write_text(json.dumps(document, indent=2), encoding="utf-8")
    assert staffing.load_staffing(copy)["work_shapes"]["mechanical"]["default_effort"] == "medium"


def test_an_unknown_rating_sorts_last_not_first(monkeypatch: pytest.MonkeyPatch) -> None:
    ratings = json.loads(json.dumps(staffing.capability_ratings()))
    first = next(iter(ratings["engines"]))
    ratings["engines"][first]["capability_profile"]["debug"] = {"rating": "EXCELLENT"}
    monkeypatch.setattr(staffing, "capability_ratings", lambda registry=None: ratings)
    rows = staffing.candidates_for("functional-tester")
    assert rows[-1]["rating"] == "EXCELLENT", "an unrecognised rating must sort last, not first"


def test_a_registry_that_is_not_an_object_raises(tmp_path: pathlib.Path) -> None:
    broken = tmp_path / "staffing.json"
    broken.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(StaffingError, match="must be a JSON object"):
        staffing.load_staffing(broken)


def test_a_registry_missing_a_block_raises(tmp_path: pathlib.Path) -> None:
    document = json.loads(staffing.STAFFING_PATH.read_text(encoding="utf-8"))
    del document["roles"]
    broken = tmp_path / "staffing.json"
    broken.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(StaffingError, match="roles"):
        staffing.roles(staffing.load_staffing(broken))


def test_an_off_palette_effort_is_refused_on_both_validators(tmp_path: pathlib.Path) -> None:
    """Only the model half was covered; the fallback was a bare ValueError without context."""
    _write_overlay(tmp_path, {"judgment": {"model": "opus", "effort": "colossal"}})
    with pytest.raises(StaffingError, match="colossal"):
        staffing.load_overlay(root=tmp_path)
    with pytest.raises(StaffingError, match="colossal"):
        staffing.resolve_shape("judgment", suggestion={"model": "opus", "effort": "colossal"})


def test_cli_suggest_flag_is_parsed_and_recorded() -> None:
    result = _run("resolve", "--shape", "judgment", "--suggest", "sonnet/low", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["suggestion"] == {"model": "sonnet", "effort": "low"}


def test_cli_suggest_flag_rejects_a_malformed_value() -> None:
    result = _run("resolve", "--shape", "judgment", "--suggest", "sonnet-low")
    assert result.returncode == 2
    assert "MODEL/EFFORT" in result.stderr


def test_every_work_shape_resolves_to_a_pair_the_model_can_actually_run() -> None:
    """The membership check the docstring claimed was a runnability check."""
    from fleet_commons import tier_palette

    for shape in staffing.work_shapes():
        decision = staffing.resolve_shape(shape)
        assert tier_palette.supports_effort(decision.model, decision.effort), (
            f"{shape}: {decision.model}/{decision.effort} is above the model's ceiling"
        )


# ---------------------------------------------------------------------------
# role-tier aliases resolve through every path (API contract lens, issue #1021).
#
# Twenty-five team-execution agent definitions carry one of these three aliases in frontmatter.
# A membership check that ran before the alias mapper silently lost all three, and no test in
# either module mentioned an alias, which is why the suite stayed green.
# ---------------------------------------------------------------------------


def _aliases() -> dict[str, str]:
    from fleet_commons import tier_resolver

    return dict(tier_resolver.ROLE_TIER_ALIASES)


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("adversarial-review", ("opus", "high")),
        ("contract-test", ("sonnet", "medium")),
        ("mechanical-scan", ("haiku", "low")),
    ],
)
def test_a_role_tier_alias_resolves_to_its_registry_rows_tier(
    alias: str, expected: tuple[str, str]
) -> None:
    decision = staffing.resolve_shape(alias)
    assert (decision.model, decision.effort) == expected


def test_every_alias_agrees_with_the_resolver_it_delegates_to() -> None:
    """One alias vocabulary, not two: whatever the resolver maps, this module must map."""
    from fleet_commons import tier_resolver

    for alias in _aliases():
        through_staffing = staffing.resolve_shape(alias)
        through_resolver = tier_resolver.resolve(None, alias)
        assert (through_staffing.model, through_staffing.effort) == (
            through_resolver.model,
            through_resolver.effort,
        )


def test_an_alias_reports_the_registry_row_it_canonicalised_to() -> None:
    """The record must name the row that answered, not the alias the caller typed."""
    assert staffing.resolve_shape("adversarial-review").work_shape == "judgment"


def test_the_overlay_wins_over_a_tier_reached_through_an_alias(tmp_path: pathlib.Path) -> None:
    _write_overlay(tmp_path, {"judgment": {"model": "sonnet", "effort": "low"}})
    decision = staffing.resolve_shape("adversarial-review", root=tmp_path)
    assert (decision.model, decision.effort) == ("sonnet", "low")
    assert decision.source == "overlay"


def test_an_unknown_work_shape_still_fails_and_names_the_aliases() -> None:
    with pytest.raises(StaffingError, match="not-a-shape"):
        staffing.resolve_shape("not-a-shape")


def test_the_saga_shim_resolves_every_alias_as_it_did_before_the_merge() -> None:
    """The regression was visible only through saga's chain; pin it there too."""
    saga_scripts = REPO_ROOT / "plugins" / "saga" / "scripts"
    if str(saga_scripts) not in sys.path:
        sys.path.insert(0, str(saga_scripts))
    import tier_defaults

    expected = {
        "adversarial-review": {"model": "opus", "effort": "high"},
        "contract-test": {"model": "sonnet", "effort": "medium"},
        "mechanical-scan": {"model": "haiku", "effort": "low"},
    }
    for alias, tier in expected.items():
        assert tier_defaults.resolve_tier_with_overlay(alias) == tier
