#!/usr/bin/env python3
"""Shared agent-file parser + pluggable rule registry (#422).

One parser and one rule registry for every ``plugins/*/agents/*.md`` file in the fleet,
replacing the two independently-hand-rolled ``_parse_frontmatter`` copies that used to live in
``tests/test_agent_tiering.py`` and ``tests/test_agent_registration_drift.py`` (both files now
import ``parse_frontmatter`` / ``parse_frontmatter_file`` from here instead).

Frontmatter is parsed with **real YAML semantics** (``yaml.safe_load`` via a duplicate-key-
rejecting SafeLoader) -- the same resolution the agent runtime applies -- so comments, quoting,
folded/literal block scalars, and multi-line flow lists resolve here exactly as they resolve at
spawn time. A frontmatter block that fails strict parsing (invalid YAML, duplicate keys, or a
non-mapping result) is a BLOCKING ``frontmatter-schema`` violation: the lint fails closed on
anything it cannot resolve, it never guesses.

Rule registry (see ``build_default_rules``):

1. ``frontmatter-schema`` (blocking) -- the file parses as strict YAML frontmatter, its
   ``name:`` field matches the file stem, and the scalar fields the other rules consume
   (``model:``, ``role-tier:``, ``effort:``) resolve to plain strings when present.
2. ``effort-presence`` (warn-only today; see ``docs/engineering-journal/DECISIONS.md`` for the
   flip-to-block condition) -- every agent file should eventually carry an ``effort:`` field.
3. ``role-tier-vocab`` (blocking) -- a ``role-tier:`` value present in frontmatter must be a
   dispatch-resolvable alias: the vocabulary is ``ROLE_TIER_ALIASES`` in
   ``plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`` (the only mechanism the dispatch
   consumer resolves ``role-tier:`` through), classified onto a role class via
   ``agent-role-classes.json``'s ``role_tier_aliases``. A class key (``review``/``tester``/
   ``scanner``/``survey``) is NOT itself a valid ``role-tier:`` value -- the dispatch path would
   not resolve it. ``role_tier_vocabulary_drift`` (run by the CLI on every invocation) fails the
   lint the moment the two alias tables drift apart.
4. ``model-role-class`` (blocking) -- an agent's ``model:`` must fall within its declared role
   class's permitted tier range, per ``agent-role-classes.json`` (sibling file). Role class is
   resolved from the agent's ``role-tier:`` frontmatter value (the existing team-execution
   vocabulary, KTD7 in ``fleet_commons/tier_resolver.py``); agents with no ``role-tier:`` are not
   in scope for this rule (v1 does not invent a taxonomy for the ecosystem-callable agents
   already governed by ``tests/test_agent_tiering.py::PINNED_AGENTS``).
5. ``model-presence`` (warn-only) -- a role-tiered agent with no ``model:`` field is skipped by
   the tier audit; this surfaces that skip as a warning instead of silence.
6. ``tools-shape`` (blocking, fleet-wide) -- when a ``tools:`` key is present, its YAML-resolved
   value must be one of exactly two recognized authored forms: a plain string of comma-separated
   bare tool names, or a YAML list of plain-string bare tool names. ANY other resolved
   type/shape (``None``, empty, dict, nested list, non-string items, malformed tokens) is a
   BLOCKING error. Duplicate ``tools:`` keys in one block are rejected at parse time
   (last-wins vs first-wins ambiguity means a consumer could execute an unaudited roster).
7. ``tool-scope-floor`` (blocking) -- an agent whose role class is marked ``is_review_class`` in
   the policy fails unless its ``tools:`` frontmatter field is present, strictly parseable,
   non-empty, and excludes the direct file-mutation tools (``Edit``/``Write``/``NotebookEdit``).
   The floor is "no direct file-mutation tools", NOT "read-only": ``Bash`` is deliberately
   allowed because review-class agents must run ``artifact_pointer.py deref`` (the required
   verification path) and tests. The guarantee is fail-closed **by construction**: because the
   value is resolved with the same YAML semantics the runtime uses and anything outside the two
   recognized forms is an error, an authoring the lint cannot understand FAILS -- it never passes
   unexamined. There is no punctuation enumeration here to evade. The ``tools:`` frontmatter
   field IS the spawn-time capability roster a dispatcher reads to scope a leaf (the same
   mechanism saga's ``readonly-verifier`` uses); this lint checks that authored contract at CI
   time, which is orthogonal to ``plugins/saga/references/sandbox-spawn-sites.md``'s decision
   not to route team-execution through saga's ``mutation_policy`` sandbox mechanism.

A ``tiering_exempt`` truthy frontmatter value (mirroring ``tests/test_agent_tier_lint.py``'s KTD6
escape hatch) opts a file out of the ``effort-presence`` and ``model-role-class`` rules.

Usage::

    python3 tools/agent_spec.py                      # lint the whole fleet, exit 1 on any
                                                       # blocking violation
    python3 tools/agent_spec.py plugins/foo/agents/bar.md ...   # lint specific files
    python3 tools/agent_spec.py --report              # also print non-blocking warnings
    python3 tools/agent_spec.py --strict              # promote `effort:` absence to blocking
                                                       # (documented flip; not wired into CI today)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = REPO_ROOT / "plugins"
ROLE_CLASSES_PATH = Path(__file__).resolve().parent / "agent-role-classes.json"

# Fleet-core's ordered model vocabulary is the single source of tier ordering
# ({#tier-vocab-ordering}) -- never re-declare a model list here. Matches the established
# repo-root import pattern (tests/test_agent_tier_lint.py).
_FLEET_CORE_SCRIPTS = REPO_ROOT / "plugins" / "fleet-core" / "scripts"
if str(_FLEET_CORE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FLEET_CORE_SCRIPTS))

from fleet_commons.tier_palette import MODELS, model_rank  # noqa: E402
from fleet_commons.tier_resolver import ROLE_TIER_ALIASES  # noqa: E402

# Direct file-mutation tools. The tool-scope floor is "no direct file-mutation tools", NOT
# "read-only": `Bash` is deliberately allowed (review-class agents must run
# `artifact_pointer.py deref` -- the required verification path -- and tests), even though Bash
# can of course mutate files indirectly. The floor guards the authored file-mutation surface a
# dispatcher grants from this roster.
_MUTATING_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})

# A bare tool name: `Read`, `NotebookEdit`, `mcp__server__tool`. Anything else in a tools:
# token (quotes, `#`, brackets, empty) fails closed as unparseable.
_TOOL_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class FrontmatterError(ValueError):
    """An agent file's frontmatter block failed strict YAML parsing."""


class ToolsValueError(ValueError):
    """A ``tools:`` value falls outside the two recognized authored forms (fail closed)."""


class EmptyToolsError(ToolsValueError):
    """A ``tools:`` key is present but resolves to an explicitly empty roster."""


class _StrictLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` that rejects duplicate mapping keys.

    PyYAML's default is silent last-wins; a first-wins consumer reading the same block would
    execute a roster this lint never audited, so a duplicate key is an error, never a merge.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        seen: set[Hashable] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate frontmatter key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


# ---------------------------------------------------------------------------
# The shared parser (AC1: no duplicated _parse_frontmatter definitions elsewhere)
# ---------------------------------------------------------------------------


def parse_frontmatter_strict(text: str) -> dict[str, Any]:
    """Parse the leading ``---``...``---`` frontmatter block with real YAML semantics.

    THE canonical parser (#422, hardened in the #581 fix round): ``yaml.safe_load`` resolution
    (comments stripped, scalars folded, flow/block collections built) via a duplicate-key-
    rejecting loader, so the lint sees exactly the values the agent runtime would grant.

    Raises :class:`FrontmatterError` on a missing/unterminated block, a YAML parse error, a
    duplicate key, a non-mapping result, or a non-string key -- the caller fails closed.
    """
    if not text.startswith("---"):
        raise FrontmatterError("no leading `---` frontmatter block")
    end = text.find("\n---", 3)
    if end == -1:
        raise FrontmatterError("unterminated frontmatter block (no closing `---`)")
    block = text[3:end]
    try:
        # _StrictLoader subclasses yaml.SafeLoader: construction is exactly safe_load's (no
        # arbitrary-object tags), plus duplicate-key rejection. Never a full/unsafe loader.
        data = yaml.load(block, Loader=_StrictLoader)  # noqa: S506
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"frontmatter is not valid YAML: {exc}") from exc
    if data is None:
        raise FrontmatterError("frontmatter block is empty")
    if not isinstance(data, dict):
        raise FrontmatterError(
            f"frontmatter does not resolve to a mapping (got {type(data).__name__})"
        )
    for key in data:
        if not isinstance(key, str):
            raise FrontmatterError(f"frontmatter key {key!r} is not a string")
    return data


def _scalar_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Compatibility surface over :func:`parse_frontmatter_strict`: a stringified view.

    Kept for the shared-parser consumers (``tests/test_agent_tiering.py``,
    ``tests/test_agent_registration_drift.py``) that compare scalar fields as strings.
    Returns ``{}`` when the block fails strict parsing -- lint rules must NOT use this
    (they go through :func:`load_agent`, which preserves the parse error and fails closed).
    """
    try:
        data = parse_frontmatter_strict(text)
    except FrontmatterError:
        return {}
    return {key: _scalar_to_str(value) for key, value in data.items()}


def parse_frontmatter_file(path: Path) -> dict[str, str]:
    """Convenience wrapper: read ``path`` then parse its frontmatter (stringified view)."""
    return parse_frontmatter(path.read_text())


def parse_tools_value(value: Any) -> list[str]:
    """Strictly validate + normalize a YAML-resolved ``tools:`` value into bare tool names.

    Exactly two authored forms are recognized (#581 fix round -- fail closed, never enumerate
    evasions):

    * a plain string of comma-separated bare tool names -- ``Bash, Read, Grep, Glob``
    * a YAML list of plain-string bare tool names -- ``[Bash, Read]`` or a ``- Bash`` block list

    ``yaml.safe_load`` has already resolved comments, quoting, folding, and multi-line forms
    exactly as the runtime would, so what this function validates IS what a dispatcher would
    grant. ANY other resolved type/shape raises :class:`ToolsValueError`: ``None`` (key with no
    value), an explicitly empty roster (``""`` / ``[]``, :class:`EmptyToolsError`), a mapping, a
    nested list, non-string items, or tokens that are not bare tool names (empty token from a
    trailing comma, embedded quotes, etc.). Unrecognized forms FAIL -- they never pass.
    """
    if value is None:
        raise ToolsValueError("`tools:` key is present but has no value")
    if isinstance(value, str):
        if not value.strip():
            raise EmptyToolsError("explicit-empty `tools:` value (empty string)")
        tokens = [token.strip() for token in value.split(",")]
        bad = [token for token in tokens if not _TOOL_NAME_RE.match(token)]
        if bad:
            raise ToolsValueError(
                f"token(s) {bad!r} are not bare tool names -- author `tools:` as plain "
                "comma-separated tool names"
            )
        return tokens
    if isinstance(value, list):
        if not value:
            raise EmptyToolsError("explicit-empty `tools:` list ([])")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or not _TOOL_NAME_RE.match(item.strip()):
                raise ToolsValueError(
                    f"list item {item!r} is not a bare tool name -- author `tools:` as a list "
                    "of plain tool-name strings"
                )
            items.append(item.strip())
        return items
    raise ToolsValueError(
        f"`tools:` resolves to unsupported type {type(value).__name__} -- author as plain "
        "comma-separated tool names or a YAML list of tool names"
    )


@dataclass(frozen=True)
class AgentRecord:
    path: Path
    frontmatter: dict[str, Any]
    parse_error: str | None = None

    @property
    def stem(self) -> str:
        return self.path.stem


def load_agent(path: Path) -> AgentRecord:
    try:
        return AgentRecord(path=path, frontmatter=parse_frontmatter_strict(path.read_text()))
    except FrontmatterError as exc:
        return AgentRecord(path=path, frontmatter={}, parse_error=str(exc))


def iter_agent_paths(root: Path = PLUGINS_ROOT) -> list[Path]:
    """Every agent definition file in the fleet: ``plugins/*/agents/*.md``."""
    return sorted(root.glob("*/agents/*.md"))


def _str_field(agent: AgentRecord, key: str) -> str | None:
    """A frontmatter field as a plain string, or ``None`` when absent or not a string.

    Non-string shapes for the scalar fields rules consume are blocked by
    ``frontmatter-schema``, so returning ``None`` here never silently passes a malformed file.
    """
    value = agent.frontmatter.get(key)
    return value if isinstance(value, str) else None


def _is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "no", "0")
    return bool(value)


def _is_exempt(agent: AgentRecord) -> bool:
    return _is_truthy(agent.frontmatter.get("tiering_exempt"))


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    rule_id: str
    message: str
    blocking: bool


@dataclass(frozen=True)
class Rule:
    id: str
    blocking: bool
    check: Callable[[AgentRecord], list[str]]

    def run(self, agent: AgentRecord) -> list[Violation]:
        return [Violation(self.id, msg, self.blocking) for msg in self.check(agent)]


# --- Rule 1: frontmatter schema --------------------------------------------------

# Scalar fields the other rules consume: each must resolve to a plain YAML string when present,
# or the consuming rule could be silently skipped by an exotic-but-valid YAML shape.
_STRING_SCALAR_FIELDS = ("model", "role-tier", "effort")


def _check_frontmatter_schema(agent: AgentRecord) -> list[str]:
    if agent.parse_error is not None:
        return [f"frontmatter failed strict YAML parsing (fail-closed): {agent.parse_error}"]
    if not agent.frontmatter:
        return ["no parseable YAML frontmatter block (expected a leading `---`...`---` header)"]
    problems: list[str] = []
    name = agent.frontmatter.get("name")
    if not name:
        problems.append("frontmatter is missing a `name:` field")
    elif not isinstance(name, str):
        problems.append(f"frontmatter `name:` must be a plain string (got {type(name).__name__})")
    elif name != agent.stem:
        problems.append(f"frontmatter `name: {name}` does not match file stem `{agent.stem}`")
    for field in _STRING_SCALAR_FIELDS:
        value = agent.frontmatter.get(field)
        if value is not None and not isinstance(value, str):
            problems.append(
                f"frontmatter `{field}:` must resolve to a plain string "
                f"(got {type(value).__name__})"
            )
    return problems


# --- Rule 2: effort presence (warn-only) -----------------------------------------


def _check_effort_presence(agent: AgentRecord) -> list[str]:
    if _is_exempt(agent):
        return []
    if "effort" not in agent.frontmatter:
        return [
            "no `effort:` field in frontmatter (warn-only today; blocks under `--strict`. "
            "Flip condition: when the fleet-wide effort-warning count reaches zero, the CI "
            "invocation gains `--strict` and this becomes blocking -- see "
            "docs/engineering-journal/DECISIONS.md #422)"
        ]
    return []


# --- Role-class policy loading (shared by rules 3 and 4) -------------------------


def load_role_class_policy(path: Path | None = None) -> dict[str, dict]:
    resolved = path if path is not None else ROLE_CLASSES_PATH
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _role_class_lookup(policy: dict[str, dict]) -> dict[str, str]:
    """Map every declared ``role_tier_aliases`` value to its class key.

    Aliases ONLY: a class's own key (``review``/``tester``/``scanner``/``survey``) is
    deliberately NOT selectable as a ``role-tier:`` value, because the dispatch consumer
    (``fleet_commons/tier_resolver.py``) resolves ``role-tier:`` exclusively through
    ``ROLE_TIER_ALIASES`` -- a class key would lint green here yet fail to resolve at dispatch.
    ``role_tier_vocabulary_drift`` keeps the two alias tables identical.
    """
    lookup: dict[str, str] = {}
    for class_name, cfg in policy.items():
        for alias in cfg.get("role_tier_aliases", []):
            lookup[alias] = class_name
    return lookup


def role_tier_vocabulary_drift(policy: dict[str, dict] | None = None) -> list[str]:
    """Drift between this lint's classified aliases and dispatch's ``ROLE_TIER_ALIASES``.

    Returns human-readable messages (empty list = the two vocabularies are identical). Run by
    the CLI on every invocation as a blocking check: an alias only the lint knows would pass CI
    yet fail dispatch resolution; a dispatch alias the lint does not classify would let an agent
    author a dispatch-valid ``role-tier:`` that silently skips the tier audit and tool floor.
    """
    resolved_policy = policy if policy is not None else load_role_class_policy()
    lint_vocab = set(_role_class_lookup(resolved_policy))
    dispatch_vocab = set(ROLE_TIER_ALIASES)
    messages: list[str] = []
    for alias in sorted(lint_vocab - dispatch_vocab):
        messages.append(
            f"alias {alias!r} in tools/agent-role-classes.json is not dispatch-resolvable "
            "(missing from fleet_commons.tier_resolver.ROLE_TIER_ALIASES)"
        )
    for alias in sorted(dispatch_vocab - lint_vocab):
        messages.append(
            f"dispatch alias {alias!r} (fleet_commons.tier_resolver.ROLE_TIER_ALIASES) is "
            "unclassified in tools/agent-role-classes.json -- agents carrying it would "
            "silently skip the tier audit and tool-scope floor"
        )
    return messages


def _permitted_models(min_model: str, max_model: str) -> set[str]:
    """Contiguous MODELS-rank range from ``max_model`` (strongest) to ``min_model`` (weakest)."""
    strongest_rank = model_rank(max_model)
    weakest_rank = model_rank(min_model)
    return {m for m in MODELS if strongest_rank <= model_rank(m) <= weakest_rank}


def _resolve_role_class(agent: AgentRecord, lookup: dict[str, str]) -> str | None:
    role_tier = _str_field(agent, "role-tier")
    if not role_tier:
        return None
    return lookup.get(role_tier)


# --- Rule 3: model-vs-role-class -------------------------------------------------


def make_model_role_class_check(
    policy: dict[str, dict] | None = None,
) -> Callable[[AgentRecord], list[str]]:
    resolved_policy = policy if policy is not None else load_role_class_policy()
    lookup = _role_class_lookup(resolved_policy)

    def _check(agent: AgentRecord) -> list[str]:
        if _is_exempt(agent):
            return []
        class_name = _resolve_role_class(agent, lookup)
        if class_name is None:
            return []
        model = _str_field(agent, "model")
        if not model:
            # No model to audit against -- the tier range cannot be checked. The skip itself is
            # surfaced (warn-only) by the separate `model-presence` rule so it is never silent.
            return []
        cfg = resolved_policy[class_name]
        permitted = _permitted_models(cfg["min_model"], cfg["max_model"])
        if model not in permitted:
            ordered = sorted(permitted, key=model_rank)
            role_tier = _str_field(agent, "role-tier")
            return [
                f"model `{model}` is not permitted for role class {class_name!r} "
                f"(role-tier: {role_tier!r}); permitted tier(s): {ordered}"
            ]
        return []

    return _check


# --- Rule 3b: role-tier vocabulary (blocking) ------------------------------------


def make_role_tier_vocab_check(
    policy: dict[str, dict] | None = None,
) -> Callable[[AgentRecord], list[str]]:
    """A ``role-tier:`` value present in frontmatter must be a dispatch-resolvable alias.

    Without this, an unrecognized ``role-tier:`` value (a typo like ``adversarial-reveiw``)
    resolves to ``None`` in ``_resolve_role_class`` and silently exempts the agent from BOTH the
    model-vs-role-class audit AND the tool-scope floor -- an agent could ship ``Edit``/``Write``
    with a misspelled tier and pass CI green. The allowed vocabulary is exactly the classified
    ``role_tier_aliases`` set, which ``role_tier_vocabulary_drift`` pins to the dispatch path's
    ``ROLE_TIER_ALIASES`` -- so "lints green" and "resolves at dispatch" are the same claim
    (#581 fix round).
    """
    resolved_policy = policy if policy is not None else load_role_class_policy()
    lookup = _role_class_lookup(resolved_policy)

    def _check(agent: AgentRecord) -> list[str]:
        role_tier = _str_field(agent, "role-tier")
        if not role_tier:
            return []
        if role_tier in lookup:
            return []
        allowed = sorted(lookup.keys())
        return [
            f"role-tier: {role_tier!r} is not a dispatch-resolvable role-tier alias "
            f"(allowed values: {allowed}, the ROLE_TIER_ALIASES vocabulary in "
            "fleet_commons/tier_resolver.py as classified by tools/agent-role-classes.json); "
            "an unrecognized tier would silently skip both the tier audit and the tool-scope "
            "floor"
        ]

    return _check


# --- Rule 3c: model presence on role-tiered agents (warn-only) -------------------


def make_model_presence_check(
    policy: dict[str, dict] | None = None,
) -> Callable[[AgentRecord], list[str]]:
    """Warn (never block) when a role-tiered agent has no ``model:`` field.

    Previously ``make_model_role_class_check`` returned ``[]`` silently in this case, so a
    role-tiered agent with no ``model:`` was skipped by the tier audit with zero signal. This
    surfaces that skip as a warn-only warning (same channel as ``effort-presence``) instead of
    silence (#422 fix round).
    """
    resolved_policy = policy if policy is not None else load_role_class_policy()
    lookup = _role_class_lookup(resolved_policy)

    def _check(agent: AgentRecord) -> list[str]:
        if _is_exempt(agent):
            return []
        class_name = _resolve_role_class(agent, lookup)
        if class_name is None:
            return []
        if not _str_field(agent, "model"):
            return [
                f"role-tiered agent (role class {class_name!r}) has no `model:` field, so the "
                "model-vs-role-class tier audit is skipped for it (warn-only)"
            ]
        return []

    return _check


# --- Rule 3d: tools value shape (blocking, fleet-wide) ----------------------------


def _check_tools_shape(agent: AgentRecord) -> list[str]:
    """Any present ``tools:`` key must strictly parse to a non-empty list of bare tool names.

    Fleet-wide (not just review-class): a ``tools:`` value the lint cannot resolve means the
    author granted a roster nobody audited. Fail closed with a rewrite instruction.
    """
    if "tools" not in agent.frontmatter:
        return []
    try:
        parse_tools_value(agent.frontmatter["tools"])
    except ToolsValueError as exc:
        return [
            f"unparseable `tools:` value ({exc}) -- author as plain comma-separated bare tool "
            "names (or a YAML list of bare names); unrecognized forms fail closed"
        ]
    return []


# --- Rule 4: tool-scope floor for review-class agents ----------------------------


def make_tool_scope_floor_check(
    policy: dict[str, dict] | None = None,
) -> Callable[[AgentRecord], list[str]]:
    resolved_policy = policy if policy is not None else load_role_class_policy()
    lookup = _role_class_lookup(resolved_policy)

    def _check(agent: AgentRecord) -> list[str]:
        class_name = _resolve_role_class(agent, lookup)
        if class_name is None:
            return []
        if not resolved_policy[class_name].get("is_review_class"):
            return []
        role_tier = _str_field(agent, "role-tier")
        if "tools" not in agent.frontmatter:
            return [
                f"role class {class_name!r} (role-tier: {role_tier!r}) is review/verify-class "
                "but has no `tools:` frontmatter field (least-privilege floor requires an "
                "explicit tool list free of direct file-mutation tools)"
            ]
        try:
            tools = set(parse_tools_value(agent.frontmatter["tools"]))
        except EmptyToolsError:
            return [
                f"role class {class_name!r} (role-tier: {role_tier!r}) is review/verify-class "
                "but its `tools:` roster is explicitly empty -- an empty roster on a review "
                "agent is an authoring mistake, not a least-privilege win"
            ]
        except ToolsValueError as exc:
            return [
                f"role class {class_name!r} (role-tier: {role_tier!r}) is review/verify-class "
                f"and its `tools:` value could not be strictly validated ({exc}); the "
                "tool-scope floor fails closed on any form it cannot resolve"
            ]
        mutating = tools & _MUTATING_TOOLS
        if mutating:
            return [
                f"role class {class_name!r} (role-tier: {role_tier!r}) is review/verify-class "
                f"but its `tools:` list includes direct file-mutation tool(s) {sorted(mutating)}"
            ]
        return []

    return _check


def build_default_rules(policy: dict[str, dict] | None = None, strict: bool = False) -> list[Rule]:
    """Build the rule registry.

    ``strict=True`` promotes the warn-only ``effort-presence`` rule to blocking (the ``--strict``
    CLI flag). This is the documented flip mechanism for the ``effort:`` grace period: when the
    fleet-wide effort-warning count reaches zero, the CI invocation gains ``--strict`` and
    ``effort:`` absence becomes blocking (see ``docs/engineering-journal/DECISIONS.md`` #422).
    ``--strict`` is NOT wired into CI today.
    """
    resolved_policy = policy if policy is not None else load_role_class_policy()
    return [
        Rule("frontmatter-schema", True, _check_frontmatter_schema),
        Rule("effort-presence", strict, _check_effort_presence),
        Rule("role-tier-vocab", True, make_role_tier_vocab_check(resolved_policy)),
        Rule("model-role-class", True, make_model_role_class_check(resolved_policy)),
        Rule("model-presence", False, make_model_presence_check(resolved_policy)),
        Rule("tools-shape", True, _check_tools_shape),
        Rule("tool-scope-floor", True, make_tool_scope_floor_check(resolved_policy)),
    ]


DEFAULT_RULES: list[Rule] = build_default_rules()


def lint_agent(agent: AgentRecord, rules: list[Rule] | None = None) -> list[Violation]:
    active_rules = rules if rules is not None else DEFAULT_RULES
    violations: list[Violation] = []
    for rule in active_rules:
        violations.extend(rule.run(agent))
    return violations


def lint_paths(paths: list[Path], rules: list[Rule] | None = None) -> list[Violation]:
    violations: list[Violation] = []
    for path in paths:
        violations.extend(lint_agent(load_agent(path), rules))
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="agent .md files to lint (default: the whole fleet, plugins/*/agents/*.md)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="also print non-blocking warnings (e.g. missing `effort:`)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "promote the warn-only `effort:`-presence rule to blocking (the documented flip for "
            "the `effort:` grace period; NOT wired into CI today)"
        ),
    )
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.paths] if args.paths else iter_agent_paths()
    if not paths:
        print("agent_spec: no agent files found", file=sys.stderr)
        return 1

    policy = load_role_class_policy()
    rules = build_default_rules(policy, strict=args.strict)

    blocking: list[str] = []
    warnings: list[str] = []

    # The role-tier vocabulary must stay pinned to the dispatch path's ROLE_TIER_ALIASES --
    # drift between the two tables is itself a blocking lint failure (#581 fix round).
    for drift_msg in role_tier_vocabulary_drift(policy):
        blocking.append(f"{ROLE_CLASSES_PATH}: [role-tier-vocab-drift] {drift_msg}")

    for path in paths:
        for violation in lint_agent(load_agent(path), rules):
            line = f"{path}: [{violation.rule_id}] {violation.message}"
            (blocking if violation.blocking else warnings).append(line)

    if args.report:
        for line in warnings:
            print(f"WARN {line}")

    for line in blocking:
        print(f"FAIL {line}", file=sys.stderr)

    if blocking:
        print(
            f"agent_spec: {len(blocking)} blocking violation(s) across {len(paths)} file(s)",
            file=sys.stderr,
        )
        return 1

    print(
        f"agent_spec: {len(paths)} agent file(s) passed "
        f"({len(warnings)} warning(s); use --report to print them)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
