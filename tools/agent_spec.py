#!/usr/bin/env python3
"""Shared agent-file parser + pluggable rule registry (#422).

One parser and one rule registry for every ``plugins/*/agents/*.md`` file in the fleet,
replacing the two independently-hand-rolled ``_parse_frontmatter`` copies that used to live in
``tests/test_agent_tiering.py`` and ``tests/test_agent_registration_drift.py`` (both files now
import ``parse_frontmatter`` / ``parse_frontmatter_file`` from here instead).

Rule registry (see ``build_default_rules``):

1. ``frontmatter-schema`` (blocking) -- the file parses as YAML-lite frontmatter and its
   ``name:`` field matches the file stem.
2. ``effort-presence`` (warn-only today; see ``docs/engineering-journal/DECISIONS.md`` for the
   flip-to-block condition) -- every agent file should eventually carry an ``effort:`` field.
3. ``role-tier-vocab`` (blocking) -- a ``role-tier:`` value present in frontmatter must be a
   recognized class or alias in ``agent-role-classes.json``. Guards against a typo'd tier silently
   resolving to "no role class" and thereby escaping both the tier audit and the tool-scope floor.
4. ``model-role-class`` (blocking) -- an agent's ``model:`` must fall within its declared role
   class's permitted tier range, per ``agent-role-classes.json`` (sibling file). Role class is
   resolved from the agent's ``role-tier:`` frontmatter value (the existing team-execution
   vocabulary, KTD7 in ``fleet_commons/tier_resolver.py``); agents with no ``role-tier:`` are not
   in scope for this rule (v1 does not invent a taxonomy for the ecosystem-callable agents
   already governed by ``tests/test_agent_tiering.py::PINNED_AGENTS``).
5. ``model-presence`` (warn-only) -- a role-tiered agent with no ``model:`` field is skipped by
   the tier audit; this surfaces that skip as a warning instead of silence.
6. ``tool-scope-floor`` (blocking) -- an agent whose role class is marked ``is_review_class`` in
   the policy fails unless its ``tools:`` frontmatter field is present and excludes ``Edit``/
   ``Write``. The ``tools:`` scalar is normalized (flow-list brackets, single/double quotes) so a
   mutating tool cannot hide behind valid-YAML punctuation. Extends the same least-privilege
   posture saga's ``readonly-verifier`` already uses operationally
   (``plugins/saga/references/sandbox-spawn-sites.md``) to team-execution's review-class agents, as
   a CI-time authored-contract lint -- it does not route team-execution's dispatch through the saga
   sandbox mechanism (team-execution runs `bypassPermissions` with no per-leaf tool-restriction
   consumer; see the sandbox-spawn-sites.md "out-of-scope" table).

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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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

# Key charclass includes `-` (not just `_`) so hyphenated fields like `role-tier:` and
# `tiering_exempt:` both parse -- the two pre-#422 hand-rolled copies this replaces only
# supported `_`, which meant `role-tier:` silently never matched under either of them.
FRONTMATTER_KEY_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)")

_MUTATING_TOOLS = frozenset({"Edit", "Write"})


def _parse_tool_list(tools_raw: str) -> set[str]:
    """Normalize a raw ``tools:`` scalar into a set of tool names.

    Handles all three authored forms the tool-scope-floor rule must police, so a mutating tool
    can never hide behind valid-YAML punctuation (#422 fix round):

    * bare comma list -- ``Read, Grep, Glob``
    * YAML flow-list form -- ``[Read, Edit]`` (surrounding ``[`` / ``]`` stripped before split)
    * quoted scalar -- ``'Read, Edit'`` / ``"Read, Edit"`` (single AND double quotes stripped per
      token, since ``parse_frontmatter`` only strips a surrounding double-quote pair off the whole
      value and leaves single quotes intact)

    Without this normalization, ``tools: [Read, Edit]`` splits into ``"[Read"`` and ``"Edit]"`` --
    neither equals ``"Edit"`` -- so a review-class agent could carry ``Edit`` and pass the floor.
    """
    s = tools_raw.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    tokens: set[str] = set()
    for raw in s.split(","):
        token = raw.strip().strip("'\"").strip()
        if token:
            tokens.add(token)
    return tokens


# ---------------------------------------------------------------------------
# The shared parser (AC1: no duplicated _parse_frontmatter definitions elsewhere)
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract top-level YAML-lite frontmatter key/value scalar pairs from agent .md content.

    THE canonical parser (#422). Scalar top-level fields only (no multi-line/block values);
    returns ``{}`` when there is no frontmatter block. Identical logic to the two pre-#422
    hand-rolled copies this module replaces.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    result: dict[str, str] = {}
    for line in block.splitlines():
        m = FRONTMATTER_KEY_RE.match(line)
        if m:
            result[m.group(1)] = m.group(2).strip().strip('"')
    return result


def parse_frontmatter_file(path: Path) -> dict[str, str]:
    """Convenience wrapper: read ``path`` then parse its frontmatter."""
    return parse_frontmatter(path.read_text())


@dataclass(frozen=True)
class AgentRecord:
    path: Path
    frontmatter: dict[str, str]

    @property
    def stem(self) -> str:
        return self.path.stem


def load_agent(path: Path) -> AgentRecord:
    return AgentRecord(path=path, frontmatter=parse_frontmatter_file(path))


def iter_agent_paths(root: Path = PLUGINS_ROOT) -> list[Path]:
    """Every agent definition file in the fleet: ``plugins/*/agents/*.md``."""
    return sorted(root.glob("*/agents/*.md"))


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in ("", "false", "no", "0")


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


def _check_frontmatter_schema(agent: AgentRecord) -> list[str]:
    if not agent.frontmatter:
        return ["no parseable YAML frontmatter block (expected a leading `---`...`---` header)"]
    name = agent.frontmatter.get("name")
    if not name:
        return ["frontmatter is missing a `name:` field"]
    if name != agent.stem:
        return [f"frontmatter `name: {name}` does not match file stem `{agent.stem}`"]
    return []


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


def load_role_class_policy(path: Path = ROLE_CLASSES_PATH) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _role_class_lookup(policy: dict[str, dict]) -> dict[str, str]:
    """Map every alias -- and each class's own canonical name -- to its class key."""
    lookup: dict[str, str] = {}
    for class_name, cfg in policy.items():
        lookup[class_name] = class_name
        for alias in cfg.get("role_tier_aliases", []):
            lookup[alias] = class_name
    return lookup


def _permitted_models(min_model: str, max_model: str) -> set[str]:
    """Contiguous MODELS-rank range from ``max_model`` (strongest) to ``min_model`` (weakest)."""
    strongest_rank = model_rank(max_model)
    weakest_rank = model_rank(min_model)
    return {m for m in MODELS if strongest_rank <= model_rank(m) <= weakest_rank}


def _resolve_role_class(agent: AgentRecord, lookup: dict[str, str]) -> str | None:
    role_tier = agent.frontmatter.get("role-tier")
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
        model = agent.frontmatter.get("model")
        if not model:
            # No model to audit against -- the tier range cannot be checked. The skip itself is
            # surfaced (warn-only) by the separate `model-presence` rule so it is never silent.
            return []
        cfg = resolved_policy[class_name]
        permitted = _permitted_models(cfg["min_model"], cfg["max_model"])
        if model not in permitted:
            ordered = sorted(permitted, key=model_rank)
            role_tier = agent.frontmatter.get("role-tier")
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
    """A ``role-tier:`` value present in frontmatter must be a recognized class or alias.

    Without this, an unrecognized ``role-tier:`` value (a typo like ``adversarial-reveiw``)
    resolves to ``None`` in ``_resolve_role_class`` and silently exempts the agent from BOTH the
    model-vs-role-class audit AND the tool-scope floor -- an agent could ship ``Edit``/``Write``
    with a misspelled tier and pass CI green. This rule makes an out-of-vocabulary tier a blocking
    error (#422 fix round).
    """
    resolved_policy = policy if policy is not None else load_role_class_policy()
    lookup = _role_class_lookup(resolved_policy)

    def _check(agent: AgentRecord) -> list[str]:
        role_tier = agent.frontmatter.get("role-tier")
        if not role_tier:
            return []
        if role_tier in lookup:
            return []
        allowed = sorted(lookup.keys())
        return [
            f"role-tier: {role_tier!r} is not a recognized value in "
            f"tools/agent-role-classes.json (allowed role-tier values: {allowed}); an "
            "unrecognized tier would silently skip both the tier audit and the tool-scope floor"
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
        if not agent.frontmatter.get("model"):
            return [
                f"role-tiered agent (role class {class_name!r}) has no `model:` field, so the "
                "model-vs-role-class tier audit is skipped for it (warn-only)"
            ]
        return []

    return _check


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
        role_tier = agent.frontmatter.get("role-tier")
        tools_raw = agent.frontmatter.get("tools")
        if not tools_raw:
            return [
                f"role class {class_name!r} (role-tier: {role_tier!r}) is review/verify-class "
                "but has no `tools:` frontmatter field (least-privilege floor requires an "
                "explicit, non-mutating tool list)"
            ]
        tools = _parse_tool_list(tools_raw)
        mutating = tools & _MUTATING_TOOLS
        if mutating:
            return [
                f"role class {class_name!r} (role-tier: {role_tier!r}) is review/verify-class "
                f"but its `tools:` list includes mutating tool(s) {sorted(mutating)}"
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

    rules = build_default_rules(strict=args.strict)

    blocking: list[str] = []
    warnings: list[str] = []
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
