#!/usr/bin/env python3
"""Shared Saga external-engine offer policy helper (#451)."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

import chaperone_economics as ce
import yaml

STAGES = ("ideate", "brainstorm", "work", "doc-review", "code-review")
INTENTS = ("none", "offload", "second-opinion")
UNIT_SHAPES = ("unknown", "mechanical", "judgment")
_fleet_commons_shim = cast(Any, importlib.import_module("fleet_commons_shim"))
_tier_palette = _fleet_commons_shim.load("tier_palette")
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

PREFS_VERSION = 1
PREFS_PATH = Path(".saga") / "engine-prefs.json"
DEFAULT_SURFACE_INTENT_DEFAULTS = (
    Path(__file__).resolve().parent.parent / "references" / "surface_intent_defaults.yaml"
)

MECHANICAL_TERMS = frozenset(
    {
        "bulk rename",
        "deterministic",
        "generated",
        "mechanical",
        "scaffold",
        "scripted transform",
        "template",
    }
)
JUDGMENT_TERMS = frozenset(
    {
        "adversarial",
        "architecture",
        "architectural",
        "decision",
        "design",
        "judgment",
        "review",
        "trade-off",
        "tradeoff",
    }
)
Intent = Literal["none", "offload", "second-opinion"]
UnitShape = Literal["unknown", "mechanical", "judgment"]
OfferSource = Literal["default", "stored"]


class EngineOfferError(ValueError):
    """Raised when engine-offer policy input or preference state is invalid."""


@dataclass(frozen=True)
class Preference:
    """A persisted repo/stage engine-offer preference."""

    intent: Intent
    model: str | None = None
    effort: str | None = None

    def __post_init__(self) -> None:
        _validate_intent(self.intent)
        if self.intent == "none":
            if self.model is not None or self.effort is not None:
                raise EngineOfferError("'none' preference must not include model or effort")
            return
        _validate_model_effort(self.model, self.effort)

    def to_json(self) -> dict[str, str]:
        data: dict[str, str] = {"intent": self.intent}
        if self.model is not None and self.effort is not None:
            data["model"] = self.model
            data["effort"] = self.effort
        return data


@dataclass(frozen=True)
class EngineOffer:
    """An advisory offer for a lifecycle stage to present or reuse."""

    stage: str
    intent: Intent
    model: str | None
    effort: str | None
    unit_shape: UnitShape
    source: OfferSource
    prompt_required: bool
    choices: tuple[str, ...]
    reason: str
    cost_delta_preview: str | None = None
    advisory_only: bool = True

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["choices"] = list(self.choices)
        return data


@dataclass(frozen=True)
class EnginePreferences:
    """Schema-versioned repo-local engine-offer preferences."""

    stages: dict[str, Preference]

    def to_json(self) -> dict[str, object]:
        return {
            "version": PREFS_VERSION,
            "stages": {stage: pref.to_json() for stage, pref in sorted(self.stages.items())},
        }


@dataclass(frozen=True)
class SurfaceIntentDefaults:
    """Data-authored engine-offer defaults for lifecycle stages and unit shapes."""

    shape_preferences: dict[str, Preference]
    stage_shape_defaults: dict[str, UnitShape]

    def preference_for_shape(self, shape: UnitShape) -> Preference:
        try:
            return self.shape_preferences[shape]
        except KeyError as exc:
            raise EngineOfferError(f"surface defaults missing shape {shape!r}") from exc


def classify_unit_shape(
    *,
    unit_shape: str | None = None,
    labels: list[str] | tuple[str, ...] = (),
    text: str = "",
) -> UnitShape:
    """Return a conservative unit-shape classification for offer defaults."""
    if unit_shape is not None:
        normalized = unit_shape.strip().lower()
        if normalized not in UNIT_SHAPES:
            raise EngineOfferError(f"unit_shape {unit_shape!r} not in {UNIT_SHAPES}")
        return normalized  # type: ignore[return-value]

    haystack = " ".join([*labels, text]).lower()
    if not haystack.strip():
        return "unknown"

    has_judgment = any(term in haystack for term in JUDGMENT_TERMS)
    if has_judgment:
        return "judgment"
    if any(term in haystack for term in MECHANICAL_TERMS):
        return "mechanical"
    return "unknown"


def resolve_offer(
    stage: str,
    *,
    repo_root: Path | str | None = None,
    attended: bool = False,
    unit_shape: str | None = None,
    labels: list[str] | tuple[str, ...] = (),
    text: str = "",
    preferences: EnginePreferences | None = None,
    surface_defaults: SurfaceIntentDefaults | None = None,
    defaults_path: Path | str | None = None,
    economics: dict[str, Any] | None = None,
) -> EngineOffer:
    """Resolve one lifecycle-stage external-engine offer."""
    _validate_stage(stage)
    loaded_preferences = preferences
    if loaded_preferences is None and repo_root is not None:
        loaded_preferences = load_preferences(repo_root)

    if loaded_preferences is not None and stage in loaded_preferences.stages:
        preference = loaded_preferences.stages[stage]
        return _offer_from_preference(stage, preference, economics=economics)

    shape = classify_unit_shape(unit_shape=unit_shape, labels=labels, text=text)
    defaults = surface_defaults
    if defaults is None:
        defaults = load_surface_intent_defaults(defaults_path or DEFAULT_SURFACE_INTENT_DEFAULTS)

    if shape == "unknown":
        shape = defaults.stage_shape_defaults.get(stage, shape)

    default = defaults.preference_for_shape(shape)
    cost_delta_preview = _cost_delta_preview(default, economics)
    return EngineOffer(
        stage=stage,
        intent=default.intent,
        model=default.model,
        effort=default.effort,
        unit_shape=shape,
        source="default",
        prompt_required=attended,
        choices=_choices_for(default.intent),
        reason=_reason_for(stage, shape, default),
        cost_delta_preview=cost_delta_preview,
    )


def load_surface_intent_defaults(
    path: Path | str = DEFAULT_SURFACE_INTENT_DEFAULTS,
) -> SurfaceIntentDefaults:
    """Load data-authored lifecycle-stage intent defaults."""
    defaults_path = Path(path)
    try:
        raw = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EngineOfferError(
            f"{defaults_path}: cannot read surface intent defaults: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise EngineOfferError(
            f"{defaults_path}: malformed surface intent defaults: {exc}"
        ) from exc

    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise EngineOfferError(f"{defaults_path}: expected surface intent defaults version 1")

    shape_preferences = _parse_shape_preferences(raw.get("defaults"), defaults_path)
    stage_shape_defaults = _parse_stage_shape_defaults(
        raw.get("stage_shape_defaults", {}), defaults_path
    )
    return SurfaceIntentDefaults(
        shape_preferences=shape_preferences,
        stage_shape_defaults=stage_shape_defaults,
    )


def load_preferences(repo_root: Path | str) -> EnginePreferences:
    """Load repo-local preferences, returning an empty set when absent."""
    prefs_path = _prefs_path(repo_root)
    if not prefs_path.exists():
        return EnginePreferences(stages={})
    try:
        raw = json.loads(prefs_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EngineOfferError(f"{prefs_path}: malformed JSON: {exc.msg}") from exc
    except OSError as exc:
        raise EngineOfferError(f"{prefs_path}: cannot read preferences: {exc}") from exc

    if not isinstance(raw, dict) or raw.get("version") != PREFS_VERSION:
        raise EngineOfferError(f"{prefs_path}: expected version {PREFS_VERSION}")
    raw_stages = raw.get("stages", {})
    if not isinstance(raw_stages, dict):
        raise EngineOfferError(f"{prefs_path}: 'stages' must be an object")

    stages: dict[str, Preference] = {}
    for stage, data in raw_stages.items():
        _validate_stage(stage)
        if not isinstance(data, dict):
            raise EngineOfferError(f"{prefs_path}: preference for {stage!r} must be an object")
        intent = data.get("intent")
        model = data.get("model")
        effort = data.get("effort")
        if not isinstance(intent, str):
            raise EngineOfferError(f"{prefs_path}: preference for {stage!r} missing string intent")
        if model is not None and not isinstance(model, str):
            raise EngineOfferError(f"{prefs_path}: preference for {stage!r} model must be a string")
        if effort is not None and not isinstance(effort, str):
            raise EngineOfferError(
                f"{prefs_path}: preference for {stage!r} effort must be a string"
            )
        stages[stage] = Preference(
            intent=cast(Intent, intent),
            model=model,
            effort=effort,
        )
    return EnginePreferences(stages=stages)


def save_preference(repo_root: Path | str, stage: str, preference: Preference) -> Path:
    """Persist one stage preference through an atomic local file replace."""
    _validate_stage(stage)
    prefs = load_preferences(repo_root)
    prefs.stages[stage] = preference
    prefs_path = _prefs_path(repo_root)
    prefs_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(prefs.to_json(), indent=2, sort_keys=True) + "\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{prefs_path.name}.",
        suffix=".tmp",
        dir=str(prefs_path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, prefs_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return prefs_path


def _offer_from_preference(
    stage: str, preference: Preference, *, economics: dict[str, Any] | None = None
) -> EngineOffer:
    return EngineOffer(
        stage=stage,
        intent=preference.intent,
        model=preference.model,
        effort=preference.effort,
        unit_shape="unknown",
        source="stored",
        prompt_required=False,
        choices=(),
        reason=f"stored preference for {stage}",
        cost_delta_preview=_cost_delta_preview(preference, economics),
    )


def _choices_for(default_intent: Intent) -> tuple[str, ...]:
    ordered = [default_intent, *[intent for intent in INTENTS if intent != default_intent]]
    return tuple(ordered)


def _reason_for(stage: str, shape: UnitShape, preference: Preference) -> str:
    if preference.intent == "offload":
        return f"{stage} unit classified {shape}; mechanical work can be chaperoned cheaply"
    if preference.intent == "second-opinion":
        return f"{stage} unit classified {shape}; judgment work benefits from advisory review"
    return f"{stage} unit classified {shape}; no engine offer selected by default"


def _prefs_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / PREFS_PATH


def _cost_delta_preview(preference: Preference, economics: dict[str, Any] | None) -> str | None:
    if preference.intent != "offload" or economics is None:
        return None
    if not isinstance(economics, dict):
        raise EngineOfferError("economics must be an object")

    cost_class = _optional_string(economics.get("cost_class"), "cost_class") or "metered"
    _validate_cost_class(cost_class)
    engine_id = _optional_string(economics.get("engine_id"), "engine_id")
    inline_fallback = (
        _optional_string(economics.get("inline_fallback"), "inline_fallback") or "inline"
    )

    external_cost = _optional_non_negative_float(
        economics.get("estimated_external_cost_usd"), "estimated_external_cost_usd"
    )
    budget_ceiling = _optional_non_negative_float(
        economics.get("provider_budget_ceiling_usd"), "provider_budget_ceiling_usd"
    )
    prior_spend = _optional_non_negative_float(
        economics.get("prior_provider_spend_usd"), "prior_provider_spend_usd"
    )
    inline_tokens = _optional_non_negative_int(
        economics.get("claude_inline_tokens_estimate"), "claude_inline_tokens_estimate"
    )
    chaperone_tokens = _optional_non_negative_int(
        economics.get("chaperone_tokens_estimate"), "chaperone_tokens_estimate"
    )

    required = [inline_tokens, chaperone_tokens]
    if cost_class == "metered":
        required.extend([external_cost, budget_ceiling])
    if any(value is None for value in required):
        return None

    try:
        decision = ce.decide_offload_economics(
            ce.OffloadEconomicsInput(
                engine_id=engine_id or preference.model or "offload",
                cost_class=cast(ce.CostClass, cost_class),
                estimated_external_cost_usd=external_cost,
                provider_budget_ceiling_usd=budget_ceiling,
                prior_provider_spend_usd=prior_spend or 0.0,
                claude_inline_tokens_estimate=inline_tokens,
                chaperone_tokens_estimate=chaperone_tokens,
                inline_fallback=inline_fallback,
            )
        )
    except ce.ChaperonePolicyError as exc:
        raise EngineOfferError(f"economics: {exc}") from exc
    return decision.preview


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise EngineOfferError(f"{name} must be a string")
    if not value:
        raise EngineOfferError(f"{name} must be non-empty")
    return value


def _optional_non_negative_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise EngineOfferError(f"{name} must be a number")
    if value < 0:
        raise EngineOfferError(f"{name} must be >= 0")
    return float(value)


def _optional_non_negative_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineOfferError(f"{name} must be an integer")
    if value < 0:
        raise EngineOfferError(f"{name} must be >= 0")
    return value


def _parse_shape_preferences(raw: Any, path: Path) -> dict[str, Preference]:
    if not isinstance(raw, dict):
        raise EngineOfferError(f"{path}: 'defaults' must be an object")

    preferences: dict[str, Preference] = {}
    for shape in UNIT_SHAPES:
        data = raw.get(shape)
        if not isinstance(data, dict):
            raise EngineOfferError(f"{path}: defaults for shape {shape!r} must be an object")
        preferences[shape] = _preference_from_mapping(data, path, f"defaults.{shape}")
    return preferences


def _parse_stage_shape_defaults(raw: Any, path: Path) -> dict[str, UnitShape]:
    if not isinstance(raw, dict):
        raise EngineOfferError(f"{path}: 'stage_shape_defaults' must be an object")

    defaults: dict[str, UnitShape] = {}
    for stage, shape in raw.items():
        if not isinstance(stage, str):
            raise EngineOfferError(f"{path}: stage name {stage!r} must be a string")
        _validate_stage(stage)
        if not isinstance(shape, str) or shape not in UNIT_SHAPES:
            raise EngineOfferError(f"{path}: stage {stage!r} shape {shape!r} not in {UNIT_SHAPES}")
        defaults[stage] = cast(UnitShape, shape)
    return defaults


def _preference_from_mapping(data: dict[str, Any], path: Path, where: str) -> Preference:
    intent = data.get("intent")
    model = data.get("model")
    effort = data.get("effort")
    if not isinstance(intent, str):
        raise EngineOfferError(f"{path}: {where} missing string intent")
    if model is not None and not isinstance(model, str):
        raise EngineOfferError(f"{path}: {where} model must be a string")
    if effort is not None and not isinstance(effort, str):
        raise EngineOfferError(f"{path}: {where} effort must be a string")
    return Preference(intent=cast(Intent, intent), model=model, effort=effort)


def _validate_stage(stage: str) -> None:
    if stage not in STAGES:
        raise EngineOfferError(f"stage {stage!r} not in {STAGES}")


def _validate_intent(intent: str) -> None:
    if intent not in INTENTS:
        raise EngineOfferError(f"intent {intent!r} not in {INTENTS}")


def _validate_model_effort(model: str | None, effort: str | None) -> None:
    if model not in MODELS:
        raise EngineOfferError(f"model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise EngineOfferError(f"effort {effort!r} not in {EFFORTS}")


def _validate_cost_class(cost_class: str) -> None:
    if cost_class not in ce.COST_CLASSES:
        raise EngineOfferError(f"cost_class {cost_class!r} not in {ce.COST_CLASSES}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    offer = subparsers.add_parser("offer", help="resolve a stage engine offer")
    offer.add_argument("--stage", required=True, choices=STAGES)
    offer.add_argument("--repo-root", default=".")
    offer.add_argument("--attended", action="store_true")
    offer.add_argument("--unit-shape", choices=UNIT_SHAPES)
    offer.add_argument("--label", action="append", default=[])
    offer.add_argument("--text", default="")
    offer.add_argument("--engine-id")
    offer.add_argument("--cost-class", choices=ce.COST_CLASSES)
    offer.add_argument("--estimated-external-cost-usd", type=float)
    offer.add_argument("--provider-budget-ceiling-usd", type=float)
    offer.add_argument("--prior-provider-spend-usd", type=float)
    offer.add_argument("--claude-inline-tokens-estimate", type=int)
    offer.add_argument("--chaperone-tokens-estimate", type=int)
    offer.add_argument("--inline-fallback")

    remember = subparsers.add_parser("remember", help="persist a selected stage preference")
    remember.add_argument("--stage", required=True, choices=STAGES)
    remember.add_argument("--repo-root", default=".")
    remember.add_argument("--intent", required=True, choices=INTENTS)
    remember.add_argument("--model", choices=MODELS)
    remember.add_argument("--effort", choices=EFFORTS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "offer":
            offer = resolve_offer(
                args.stage,
                repo_root=args.repo_root,
                attended=args.attended,
                unit_shape=args.unit_shape,
                labels=args.label,
                text=args.text,
                economics=_economics_from_args(args),
            )
            print(json.dumps(offer.to_json(), sort_keys=True))
            return 0

        preference = Preference(intent=args.intent, model=args.model, effort=args.effort)
        path = save_preference(args.repo_root, args.stage, preference)
        print(json.dumps({"saved": str(path), "stage": args.stage, **preference.to_json()}))
        return 0
    except EngineOfferError as exc:
        parser.error(str(exc))
    return 2


def _economics_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    values = {
        "engine_id": args.engine_id,
        "cost_class": args.cost_class,
        "estimated_external_cost_usd": args.estimated_external_cost_usd,
        "provider_budget_ceiling_usd": args.provider_budget_ceiling_usd,
        "prior_provider_spend_usd": args.prior_provider_spend_usd,
        "claude_inline_tokens_estimate": args.claude_inline_tokens_estimate,
        "chaperone_tokens_estimate": args.chaperone_tokens_estimate,
        "inline_fallback": args.inline_fallback,
    }
    if all(value is None for value in values.values()):
        return None
    values["cost_class"] = values["cost_class"] or "metered"
    values["inline_fallback"] = values["inline_fallback"] or "inline"
    return {key: value for key, value in values.items() if value is not None}


if __name__ == "__main__":
    raise SystemExit(main())
