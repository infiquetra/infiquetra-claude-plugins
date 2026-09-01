"""Coverage guard for the Saga documentation model and manual.

The comprehensive Saga docs are curated, but their coverage should not drift from
the command surface, readiness model, or generated visual inventory. These tests
check structure and references rather than prose style.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SAGA_ROOT = REPO_ROOT / "plugins" / "saga"
MODEL_PATH = SAGA_ROOT / "docs" / "model" / "saga-docs-model.yaml"
RENDERER_PATH = SAGA_ROOT / "scripts" / "render_docs_visuals.py"

REQUIRED_CARD_FIELDS = {
    "command",
    "phase",
    "lifecycle_role",
    "source_refs",
    "purpose",
    "use_when",
    "do_not_use_when",
    "inputs",
    "outputs",
    "durable_artifacts",
    "saga_state_behavior",
    "routes_in",
    "routes_out",
    "gates",
    "ownership_boundary",
    "common_mistakes",
    "example_invocation",
}

REQUIRED_ADJACENT_PAIRS = {
    ("/office-hours", "/ideate"),
    ("/ideate", "/brainstorm"),
    ("/brainstorm", "/spec"),
    ("/plan", "/doc-review"),
    ("/qa", "/optimize"),
    ("/strategy", "/founder-review"),
    ("/loop", "/resume"),
}

REQUIRED_SCENARIOS = {
    "vague-idea",
    "chosen-idea",
    "vague-what",
    "requirements-ready-handoff",
    "plan-review",
    "pr-boundary",
    "post-merge-qa",
    "qa-failure",
    "root-cause-investigation",
    "metric-optimization",
    "strategy-refresh",
    "cross-team-handoff",
    "cold-resume",
    "retro-learning",
}

REQUIRED_VISUALS = {
    "lifecycle-atlas",
    "state-readiness-ladder",
    "command-matrix",
    "ownership-boundary-map",
}

MANUAL_PAGES = [
    SAGA_ROOT / "README.md",
    SAGA_ROOT / "docs" / "README.md",
    SAGA_ROOT / "docs" / "commands.md",
    SAGA_ROOT / "docs" / "lifecycle.md",
    SAGA_ROOT / "docs" / "state-readiness.md",
    SAGA_ROOT / "docs" / "scenarios.md",
    SAGA_ROOT / "docs" / "boundaries.md",
    SAGA_ROOT / "docs" / "visuals.md",
]


def _load_model() -> dict[str, Any]:
    assert MODEL_PATH.is_file(), f"missing docs model: {MODEL_PATH}"
    data = yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_docs_visuals", RENDERER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _command_wrapper_names() -> set[str]:
    return {path.stem for path in (SAGA_ROOT / "commands").glob("*.md")}


def _resolve_repo_path(path_text: str) -> Path:
    return (REPO_ROOT / path_text).resolve()


def test_docs_model_matches_command_surface() -> None:
    model = _load_model()
    wrappers = _command_wrapper_names()
    commands = set(model["commands"])
    aliases = set(model["aliases"])

    # 24/23 after /undo was removed in #666 -- its ledger never held an entry, so the
    # command could only ever report "nothing to undo". /ship --undo (ship_undo.py, 16 real
    # rollback manifests) is the surviving, working undo path.
    assert model["command_surface"]["command_files"] == 24
    assert model["command_surface"]["routable_commands"] == 23
    assert wrappers == commands | aliases
    assert aliases == {"ceo-review"}
    assert model["aliases"]["ceo-review"]["aliases"] == "/founder-review"


def test_every_command_card_has_required_fields_and_existing_sources() -> None:
    model = _load_model()

    for command_id, card in model["commands"].items():
        missing = REQUIRED_CARD_FIELDS - set(card)
        assert not missing, f"{command_id} missing card fields: {sorted(missing)}"
        assert card["command"] == f"/{command_id}"
        for field in ("use_when", "do_not_use_when", "common_mistakes"):
            assert isinstance(card[field], list) and card[field], f"{command_id}.{field} empty"
        for source_ref in card["source_refs"]:
            path = _resolve_repo_path(source_ref)
            assert path.exists(), f"{command_id} source_ref missing: {source_ref}"

    for alias_id, alias in model["aliases"].items():
        for source_ref in alias["source_refs"]:
            path = _resolve_repo_path(source_ref)
            assert path.exists(), f"{alias_id} source_ref missing: {source_ref}"


def test_readiness_is_derived_not_stored() -> None:
    model = _load_model()
    state_axes = set(model["state_axes"])
    maturity = model["maturity"]

    assert state_axes == {"lifecycle_phase", "phase_status", "status"}
    assert "maturity" not in state_axes
    assert maturity["derived_not_stored"] == "saga_ticks_only"
    assert set(maturity["values"]) >= {
        "idea-ready",
        "requirements-ready",
        "plan-ready",
        "resume-ready",
        "pending-confirmation",
    }
    assert "docs/specs/" in maturity["values"]["requirements-ready"]["from"]
    assert "docs/brainstorms/" in str(maturity["values"]["pending-confirmation"]["from"])
    assert set(maturity["values"]["pending-confirmation"]["consumed_by"]) == {"/brainstorm"}
    assert set(maturity["values"]["pending-confirmation"]["read_by"]) == {
        "/resume",
        "/loop",
        "/handoff",
    }


def test_required_scenarios_pairs_and_visual_inventory_are_present() -> None:
    model = _load_model()

    assert set(model["scenarios"]) >= REQUIRED_SCENARIOS
    assert set(model["visuals"]) >= REQUIRED_VISUALS
    assert {tuple(pair) for pair in model["adjacent_pairs"]} >= REQUIRED_ADJACENT_PAIRS

    for scenario_id, scenario in model["scenarios"].items():
        for field in (
            "starting_statement",
            "selected_command",
            "effect",
            "stop_condition",
            "next_route",
        ):
            assert scenario.get(field), f"{scenario_id} missing {field}"


def test_manual_pages_exist_and_reference_model_coverage() -> None:
    model = _load_model()
    for page in MANUAL_PAGES:
        assert page.is_file(), f"missing manual page: {page.relative_to(REPO_ROOT)}"

    commands_text = (SAGA_ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
    for command_id, card in model["commands"].items():
        assert f"### {card['command']}" in commands_text, f"missing card for {command_id}"
    assert "### /ceo-review" in commands_text

    scenarios_text = (SAGA_ROOT / "docs" / "scenarios.md").read_text(encoding="utf-8")
    for scenario_id in REQUIRED_SCENARIOS:
        assert scenario_id in scenarios_text

    visuals_text = (SAGA_ROOT / "docs" / "visuals.md").read_text(encoding="utf-8")
    for visual in model["visuals"].values():
        assert Path(visual["file"]).name in visuals_text


def test_manual_relative_links_resolve() -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")

    for page in MANUAL_PAGES:
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            target_without_anchor = raw_target.split("#", maxsplit=1)[0]
            if not target_without_anchor:
                continue
            target = (page.parent / target_without_anchor).resolve()
            assert target.exists(), f"{page.relative_to(REPO_ROOT)} has broken link: {raw_target}"


def test_generated_visual_assets_match_model() -> None:
    model = _load_model()
    renderer = _load_renderer()
    rendered = renderer.render_all(model)

    for visual_id, svg in rendered.items():
        visual = model["visuals"][visual_id]
        path = REPO_ROOT / visual["file"]
        assert path.is_file(), f"missing generated visual: {visual['file']}"
        assert path.read_text(encoding="utf-8") == svg, (
            f"{visual['file']} is stale; run "
            "uv run python plugins/saga/scripts/render_docs_visuals.py"
        )
        assert f'<title id="title">{visual["title"]}</title>' in svg
        assert "Do not edit by hand" in svg


def test_ladder_renderer_rows_equal_model_maturity_values() -> None:
    """CORR-12: the state-readiness ladder's maturity rows must equal the model's vocabulary.

    The renderer's row list is separate from the model's maturity map, so a new maturity
    value added to the model without a renderer row produces a diagram that disagrees with
    the very document embedding it. This guard compares the row labels directly against the
    model so the next vocabulary change fails here instead of shipping a stale asset.
    """
    model = _load_model()
    renderer = _load_renderer()
    rows = renderer.maturity_rows(model)
    row_labels = {maturity for _, maturity, _ in rows}
    # All three columns, not just the name: source and consumer text must equal what the model
    # declares, so a label cannot drift from its declared source (DOC-34).
    for source, maturity, consumer in rows:
        declared = model["maturity"]["values"][maturity]
        assert source == " + ".join(declared["from"]), (
            f"ladder source for {maturity!r} is {source!r}, model declares {declared['from']!r}"
        )
        assert consumer == " / ".join(declared["consumed_by"]), (
            f"ladder consumer for {maturity!r} is {consumer!r}, "
            f"model declares {declared['consumed_by']!r}"
        )
    model_values = set(model["maturity"]["values"])
    assert row_labels == model_values, (
        f"ladder rows {row_labels!r} != model values {model_values!r}; "
        "add the missing maturity to render_docs_visuals.py's LADDER_ORDER and regenerate the asset"
    )
    # Secondary: the rows must have reached the asset (not just the list)
    svg = renderer.render_all(model)["state-readiness-ladder"]
    for value in model_values:
        assert value in svg


def test_state_readiness_table_matches_model() -> None:
    """DOC-20: the maturity table in the manual page must match the model exactly.

    The model README declares the model the maintained source for readiness mappings,
    so the page that embeds the diagram must not diverge from it. This guard parses
    the page's markdown table and asserts its (maturity, consumed) pairs are exactly
    the model's, so the divergent row that predated this change cannot recur.
    """
    model = _load_model()
    text = (SAGA_ROOT / "docs" / "state-readiness.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "| Source" in line and "Derived maturity" in line:
            start = i
            break
    assert start is not None, "maturity table header not found in state-readiness.md"
    rows: list[tuple[str, str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 3:
            continue
        source, maturity_raw, consumed_raw = parts[0], parts[1], parts[2]
        maturity = maturity_raw.strip("`").strip()
        rows.append((source, maturity, consumed_raw))
    # Build expected pairs from model: each maturity value and its consumed_by
    expected_maturities = set(model["maturity"]["values"])
    table_maturities = {m for _, m, _ in rows}
    assert table_maturities == expected_maturities, (
        f"table maturities {table_maturities!r} != model {expected_maturities!r}"
    )
    for _source, maturity, consumed in rows:
        assert maturity in expected_maturities, f"table maturity {maturity!r} not in model"
        expected_consumers = set(model["maturity"]["values"][maturity]["consumed_by"])
        consumed_tokens = set(re.findall(r"/[a-z-]+", consumed))
        assert consumed_tokens == expected_consumers, (
            f"table row for {maturity!r} has consumers {consumed_tokens!r} != model's {expected_consumers!r} "
            f"from cell {consumed!r}"
        )


def test_model_maturity_values_match_runtime_vocabulary() -> None:
    """The docs model claims to own the readiness mappings, so bind it to the runtime constant.

    Without this the model and `HANDOFF_MATURITIES` can drift apart silently: the model is
    prose-checked for structure, and nothing compared its maturity keys to the vocabulary the
    envelope actually routes on.
    """
    spec = importlib.util.spec_from_file_location(
        "handoff_envelope", SAGA_ROOT / "scripts" / "handoff_envelope.py"
    )
    assert spec is not None and spec.loader is not None
    he: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(he)
    model: dict[str, Any] = yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))
    model_values = set(model["maturity"]["values"])
    runtime_values = set(he.HANDOFF_MATURITIES)
    assert model_values == runtime_values, (
        f"docs model maturity values {sorted(model_values)} != runtime "
        f"HANDOFF_MATURITIES {sorted(runtime_values)}"
    )
