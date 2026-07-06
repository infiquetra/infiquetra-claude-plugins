#!/usr/bin/env python3
"""Structured execution-spec + Claude Code workflow-script emitter (R9 keystone).

`/plan` authors ONE structured execution-spec and emits from it **either** a runnable
Claude Code workflow script (this module) **or** the team-execution markdown protocol
(``team_emitter.py``, U11). Saga stores only an ``orchestration_ref`` pointer; it never
vendors backend machinery (R9, KTD6). The governance difference is *which emitter runs*,
not the authoring.

The spec is the single source of truth: units carry a per-unit ``{model, effort}`` tier
(R2(b)), a return contract, dependency barriers, escalations, and -- for fan-out units --
an **enumerated** target list with post-run reconciliation (R10, never a silent filter).

Two authoring-time invariants are enforced at EMIT time -- a mis-built spec is an invalid
oracle, so it must fail loudly rather than silently emit a broken script:

* **R10** -- a fan-out unit with an empty / missing enumerated target list FAILS emit.
* **R3** -- a pilot at a different ``{model, effort}`` tier than its fan-out FAILS emit
  (a mis-tiered pilot validates a different cost surface than the fan-out it gates).

The sibling worked reference is
``docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`` -- a hand-authored
ultracode harness whose shape this emitter reproduces: control-flow only, agents do the
work, per-unit tiers, dependency barriers, rebase-before-merge, full hands-off auto-merge.

Cheap-tier (haiku / sonnet-low) generated agents carry the
``workflow_structuredoutput_budget`` lesson baked in (cap output, mandatory final emit,
skim don't read, batch concurrency) -- a budget-exhausted cheap agent that never emits its
StructuredOutput is the failure this prevents.

House testability pattern (mirrors ``saga.py`` / ``handoff_envelope.py``): pure functions,
no I/O at import, dataclasses with explicit ``from_dict`` so a JSON/plan-authored spec
round-trips deterministically and offline.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)

# Tier vocabulary (Epic 0 tier rule R1) is now canonical in fleet-core's
# ``fleet_commons/tier_palette.py`` (fleet-commons first mover, DECISIONS
# ``{#fleet-commons-mechanism-463}``) and re-exported here under the existing names so
# intra-saga importers and tests are untouched. The emitter does not invent tiers; it only
# validates that authored tiers are drawn from these closed sets so a typo
# ("opus-high", "med") fails emit rather than silently producing an un-runnable script.
# ORDERING IS LOAD-BEARING: segment_units() merges tiers upgrade-only via
# min(MODELS.index) / max(EFFORTS.index), so MODELS is strongest-first and
# EFFORTS is weakest-first (the contract is documented at the canonical home).
_tier_palette = fleet_commons_shim.load("tier_palette")

MODELS = _tier_palette.MODELS
EFFORTS = _tier_palette.EFFORTS

# Ordinal cost-weight table (#366). Loaded the same way as the tier palette, from
# fleet_commons/cost_weights.json, and validated against the palette ordering at its own
# import (a drifted table fails loud there, not here). ``to_spend(model, effort)`` prices a
# single agent call; the multiplicity-aware ``ExecutionSpec.spec_spend()`` sums a whole run.
_cost_weights = fleet_commons_shim.load("cost_weights")
to_spend = _cost_weights.to_spend

# Tier resolver (#362), reused for the #367 one-rung-cheaper lever so adjacent_tier's "cheaper"
# direction cannot drift from the shipped cheaper_fallback convention (weaken model first, then effort).
_tier_resolver = fleet_commons_shim.load("tier_resolver")

# Models cheap enough that the structuredoutput-budget lesson MUST be baked into the
# generated agent prompt. An opus/high agent has budget headroom; a haiku or a
# sonnet/low agent over a large surface is exactly the case the lesson guards
# (workflow_structuredoutput_budget: brevity + mandatory emit + skim + batch).
_CHEAP_MODELS = _tier_palette.CHEAP_MODELS

# refute-N pass rules (KTD3 / KTD5). A finding survives unless refuted per this rule:
# majority => >= ceil(N/2) verifiers refute; unanimous => all N refute.
# Deliberately NOT tier vocabulary — stays defined here, not in the fleet palette.
PASS_RULES = ("majority", "unanimous")

# Delegation-intent vocabulary for an engine/capability unit (KTD2, U12). ``offload``
# wants a cheap chaperone (the delegation is net-negative otherwise); ``second-opinion``
# wants an expensive one (adversarial verification IS the product).
ENGINE_INTENTS = _tier_palette.ENGINE_INTENTS

# Sandbox capability axes (issue #287 R1-R3) -- a delegated leaf's declared containment,
# orthogonal to the model/effort tier. ``mutation_policy`` is enforced by tool-set omission at
# spawn (a restricted agentType without Edit/Write); ``workspace_isolation`` by worktree/clone
# routing. Absent on a unit => ambient x read-write, exactly today's behavior (R1).
MUTATION_POLICIES = ("read-only", "read-write")
WORKSPACE_ISOLATIONS = ("ambient", "disposable-worktree", "owned-worktree")

# Named profiles are compositions accepted as authoring shorthand (R2). A profile string
# expands to its exact axis pair at parse; the pair is authoritative thereafter, so ``to_dict``
# emits the expanded axes (canonical + diffable), never the shorthand. NOTE: outcome_spec.py
# mirrors these three names verbatim (deliberate parallel house, different error type) -- a
# cross-module drift-guard test asserts the two copies stay identical.
SANDBOX_PROFILES = {
    "read-only-verify": ("read-only", "disposable-worktree"),
    "sandboxed-mutate": ("read-write", "owned-worktree"),
}

# The restricted agent type + isolation every verifier is spawned with (#287 U2, R5/KTD6). The
# ``agentType`` string MUST equal plugins/saga/agents/readonly-verifier.md's ``name:`` frontmatter
# plus the ``saga:`` plugin prefix; the literal-consistency guard test asserts this, so a rename on
# either side fails a test rather than silently spawning verifiers unrestricted (the R9 dead-wiring
# failure). ``isolation: 'worktree'`` is the load-bearing clobber defense (R3): a Bash
# ``git checkout`` needs no Edit/Write tool, so only a throwaway worktree can contain it.
READONLY_VERIFIER_AGENT_TYPE = "saga:readonly-verifier"
READONLY_VERIFIER_ISOLATION = "worktree"

# Per-backend sandbox enforceability (#287 U3, R4). Each backend can structurally enforce a set of
# NON-default axis values; a restrictive sandbox requiring a value its backend cannot enforce HALTS
# visibly (never downgrades). Keys are NODE_BACKENDS names (kept as string literals so this module
# does not import outcome_spec). Backends NOT listed -- fork, subagent, goal, manual, and any future
# one -- enforce NOTHING, so any restrictive sandbox on them halts: unknown is never permissive (R4).
# inline/cc-workflows enforce read-only (tool omission) + disposable-worktree (harness isolation)
# natively; internal owned-worktree is halt-v1 (no defined internal harvest -- sandboxed-mutate's
# only v1 consumer is the engine path, U5). team-execution enforces neither restrictive axis (KTD3):
# its residents run bypassPermissions with no per-leaf tool restriction.
SANDBOX_ENFORCEABLE_BY_BACKEND: dict[str, frozenset[str]] = {
    "inline": frozenset({"read-only", "disposable-worktree"}),
    "cc-workflows-ultracode": frozenset({"read-only", "disposable-worktree"}),
    "team-execution": frozenset(),
}

# Per-backend tier enforceability (#369 U1, KTD2) -- the tier-axis sibling of
# SANDBOX_ENFORCEABLE_BY_BACKEND. Each backend maps to the set of MODELS it can actually spawn a unit
# at. ``inline`` and ``cc-workflows-ultracode`` set the per-call {model, effort} (the readonly-verifier
# per-call pattern / the Workflow ``agent()`` model+effort opts), so they reach the whole palette.
# ``team-execution`` spawns by ``agentType`` and inherits the agent's frontmatter ``model:`` -- whose
# closed set across all 25 team-execution agents is {opus, sonnet, haiku}; NONE pin ``fable`` (it is
# unreachable outside saga plan vocabulary). So a plan-authored fable/xhigh unit routed to
# team-execution HALTS at emit instead of rendering a cosmetic Tier row it cannot obey. A backend NOT
# listed enforces nothing (frozenset()) -- unknown is never permissive (R3), matching the sandbox
# matrix. v1 enforces the MODEL axis only; per-teammate EFFORT (xhigh) enforceability rides with the
# deferred agent-frontmatter tier-floor mechanism (its per-teammate override is the QUEUED
# {#team-execution-per-teammate-effort} ask).
TIER_ENFORCEABLE_BY_BACKEND: dict[str, frozenset[str]] = {
    "inline": frozenset(MODELS),
    "cc-workflows-ultracode": frozenset(MODELS),
    "team-execution": frozenset({"opus", "sonnet", "haiku"}),
}

# Hard upper bound on a verify panel's verifier count. N above this FAILS validate/emit --
# the bound directly guards the rate-limit overcorrection (R3: the 22/23-judges panel that
# tripped the concurrency cap). N <= CAP is allowed; a soft warn band starts at WARN below.
VERIFY_N_CAP = 7

# Soft threshold: a panel size in (WARN, CAP] validates but emits a stderr warning -- big
# panels are legal but smell like the overcorrection, so they are surfaced, not silently run.
VERIFY_N_WARN = 5

# Soft threshold for the #366 cost_budget: a run whose summed spend lands in
# (WARN_FRACTION * budget, budget] validates but emits a stderr warning -- it is legal but
# close to the ceiling, so it is surfaced, not silently run (mirrors VERIFY_N_WARN).
COST_BUDGET_WARN_FRACTION = 0.9

# The verbatim budget-discipline rider baked into cheap-tier generated agents. This is
# the workflow_structuredoutput_budget lesson as an instruction the emitted agent reads.
BUDGET_RIDER = (
    "BUDGET DISCIPLINE (cheap-tier): you run on a small output budget. "
    "(1) CAP OUTPUT -- be terse; no human-facing prose, no recaps of files you read. "
    "(2) MANDATORY EMIT -- your FINAL message MUST be the JSON return object (see the RETURN "
    "CONTRACT); never end the turn without it, even if the work is partial (return what you have "
    "+ a note). "
    "(3) SKIM, don't read -- open only the exact lines you need, never whole large files. "
    "(4) BATCH -- issue independent tool calls in one parallel block, not serially."
)


_JS_GATE_HELPER = r"""function __gate(result, opts) {
  const unitId = opts.unitId || "unknown";

  function isEmptyOrAbsent(val) {
    if (val === null || val === undefined) return true;
    if (typeof val === 'string') return val.trim() === '';
    if (Array.isArray(val)) return val.length === 0;
    if (val instanceof Map || val instanceof Set) return val.size === 0;
    if (typeof val === 'object') return Object.keys(val).length === 0;
    return false;
  }

  function parseResult(val) {
    if (typeof val === 'string') {
      let s = val.trim();
      if (s.startsWith('```')) {
        const lines = s.split('\n');
        if (lines.length >= 2) {
          if (lines[0].startsWith('```')) {
            lines.shift();
          }
          if (lines.length && lines[lines.length - 1].trim() === '```') {
            lines.pop();
          }
          s = lines.join('\n').trim();
        }
      }
      if (s.startsWith('{') || s.startsWith('[')) {
        try {
          return JSON.parse(s);
        } catch (e) {
          // fall through to embedded-JSON extraction
        }
      }
      // Extract an embedded JSON value when the agent prepends conversational prose
      // before the object (sonnet/opus routinely add a "looks good, tests pass" preamble
      // ahead of the return object). Try object first, then array.
      const pairs = [['{', '}'], ['[', ']']];
      for (let i = 0; i < pairs.length; i++) {
        const start = s.indexOf(pairs[i][0]);
        const end = s.lastIndexOf(pairs[i][1]);
        if (start !== -1 && end > start) {
          try {
            return JSON.parse(s.slice(start, end + 1));
          } catch (e) {
            // try the next delimiter pair
          }
        }
      }
    }
    return val;
  }

  // #364 R7: pull_cord -- the worker-initiated out-of-depth disposition, a valid alternative
  // to the return contract (distinct from success and from the missing/malformed throws).
  // Cords batch into __pulledCords for ONE coordinator escalation entry (R8); the unit is
  // never marked complete because the batched check fails the run before it returns.
  const cordProbe = parseResult(result);
  if (cordProbe && typeof cordProbe === 'object' && !Array.isArray(cordProbe)
      && typeof cordProbe.pull_cord === 'string' && cordProbe.pull_cord.trim() !== '') {
    __pulledCords.push({ unit: unitId, reason: cordProbe.pull_cord.trim(),
                         proposal: opts.cordProposal || null });
    return result;
  }

  if (opts.expectsOutput && isEmptyOrAbsent(result)) {
    throw new Error(
      `missing-output: Unit ${unitId} expected structured output but received none or empty.`
    );
  }

  if (typeof result === 'string') {
    let s = result.trim();
    if (s.startsWith('```')) {
      const lines = s.split('\n');
      if (lines.length >= 2) {
        if (lines[0].startsWith('```')) {
          lines.shift();
        }
        if (lines.length && lines[lines.length - 1].trim() === '```') {
          lines.pop();
        }
        s = lines.join('\n').trim();
      }
    }
    if (s.startsWith('{') || s.startsWith('[')) {
      try {
        JSON.parse(s);
      } catch (e) {
        throw new Error(
          `malformed-output: Unit ${unitId} output is a structurally truncated JSON: ${e.message}`
        );
      }
    }
  }

  let targetCount = null;
  if (opts.targets !== undefined && opts.targets !== null) {
    if (typeof opts.targets === 'number') {
      targetCount = opts.targets;
    } else if (Array.isArray(opts.targets)) {
      targetCount = opts.targets.length;
    }
  }

  if (targetCount !== null) {
    const parsed = parseResult(result);
    let producedCount = 0;
    if (parsed !== null && parsed !== undefined) {
      if (Array.isArray(parsed)) {
        producedCount = parsed.length;
      } else if (parsed instanceof Map || parsed instanceof Set) {
        producedCount = parsed.size;
      } else if (typeof parsed === 'object') {
        producedCount = Object.keys(parsed).length;
      } else {
        producedCount = isEmptyOrAbsent(parsed) ? 0 : 1;
      }
    }
    if (producedCount < targetCount) {
      const shortfall = targetCount - producedCount;
      throw new Error(
        `missing-output: Unit ${unitId} produced fewer items than expected. ` +
        `Expected ${targetCount}, produced ${producedCount}. Shortfall: ${shortfall}.`
      );
    }
  }

  if (opts.returns && opts.returns.length > 0) {
    const parsed = parseResult(result);
    if (parsed === null || parsed === undefined || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(
        `missing-output: Unit ${unitId} result is not a structured dictionary. ` +
        `Missing required keys: ${opts.returns.join(', ')}.`
      );
    }
    const missing = opts.returns.filter(
      k => !(k in parsed) || parsed[k] === null || parsed[k] === undefined
    );
    if (missing.length > 0) {
      throw new Error(
        `missing-output: Unit ${unitId} output is missing required keys: ${missing.join(', ')}.`
      );
    }
  }

  return result;
}"""


# R3/KTD3: emitted-wave 429 retry. The .workflow.js runs as JS, so a parallel([...]) wave thunk
# cannot import the Python `retry_backoff` primitive -- this is the emitted JS mirror of it
# (shared-in-concept, dual-impl). Each wave/panel `agent()` call is wrapped in `__retry(...)` so a
# rate-limited (429-shaped) agent re-queues with bounded exponential backoff instead of counting as
# a wave failure; a genuine non-429 error still throws and HALTs the wave (no silent degrade).
# Written with `function` declarations only (no arrow fns) so it perturbs no emitted-shape golden,
# and backoff is deterministic (no Math.random, which the workflow runtime may forbid). Honors a
# Retry-After hint on the 429 signal when present, mirroring the Python primitive's `retry_after`.
_JS_RETRY_HELPER = r"""function __is429(x) {
  if (x === null || x === undefined) return false;
  if (typeof x === 'number') return x === 429;
  if (typeof x === 'string') return /(^|[^0-9])429([^0-9]|$)/.test(x) || /rate[\s_-]?limit/i.test(x);
  var status = x.status || x.statusCode || x.status_code || x.code;
  if (status === 429 || status === '429') return true;
  if (x.rateLimited === true || x.rate_limited === true) return true;
  var msg = x.message || x.error || '';
  return typeof msg === 'string' && (/(^|[^0-9])429([^0-9]|$)/.test(msg) || /rate[\s_-]?limit/i.test(msg));
}

function __retryAfterMs(signal) {
  if (signal === null || typeof signal !== 'object') return null;
  if (typeof signal.retryAfterMs === 'number') return signal.retryAfterMs;
  if (typeof signal.retryAfter === 'number') return signal.retryAfter * 1000;
  if (typeof signal.retry_after === 'number') return signal.retry_after * 1000;
  return null;
}

function __retryBackoffMs(attempt, baseMs, maxMs, retryAfterMs) {
  if (typeof retryAfterMs === 'number' && retryAfterMs > 0) {
    return Math.min(retryAfterMs, maxMs);
  }
  return Math.min(baseMs * Math.pow(2, attempt - 1), maxMs);
}

async function __retry(thunk, opts) {
  var o = opts || {};
  var maxAttempts = o.maxAttempts || 3;
  var baseMs = o.baseMs || 1000;
  var maxMs = o.maxMs || 60000;
  var sleep = o.sleep || function (ms) {
    return new Promise(function (r) {
      if (typeof setTimeout === 'function') { setTimeout(r, ms); } else { r(); }
    });
  };
  var attempt = 0;
  while (true) {
    attempt++;
    var result;
    var threw = false;
    var caught = null;
    try {
      result = await thunk();
    } catch (err) {
      threw = true;
      caught = err;
    }
    var signal = threw ? caught : result;
    if (__is429(signal) && attempt < maxAttempts) {
      await sleep(__retryBackoffMs(attempt, baseMs, maxMs, __retryAfterMs(signal)));
      continue;
    }
    if (threw) throw caught;
    return result;
  }
}"""


class SpecError(ValueError):
    """A spec that violates an authoring-time invariant (R3 / R10) or is malformed.

    Raised at validate/emit time so a mis-built spec fails loudly. Carrying the
    offending unit id in the message keeps the failure actionable for ``/plan``.
    """


def _engine_registry_module() -> Any:
    module = sys.modules.get("engine_registry")
    if module is not None:
        return module

    path = Path(__file__).resolve().with_name("engine_registry.py")
    spec = importlib.util.spec_from_file_location("engine_registry", path)
    if spec is None or spec.loader is None:
        raise SpecError(f"engine registry module is unavailable: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engine_registry"] = module
    spec.loader.exec_module(module)
    return module


def _engine_registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"


def _validate_external_engine_selector(
    where: str, engine: str | None, capability: str | None
) -> None:
    if engine is not None and capability is not None:
        raise SpecError(f"{where}: engine and capability are mutually exclusive")
    if engine is None and capability is None:
        return

    registry_module = _engine_registry_module()
    if capability is not None and capability not in registry_module.CAPABILITIES:
        raise SpecError(f"{where}: unknown capability {capability!r}")

    registry_path = _engine_registry_path()
    if not registry_path.exists():
        return

    try:
        registry = registry_module.Registry.load(registry_path)
    except registry_module.RegistryError as exc:
        raise SpecError(f"{where}: engine registry invalid: {exc}") from exc

    if engine is not None:
        engine_keys = {entry.key for entry in registry.engines}
        if engine not in engine_keys:
            raise SpecError(f"{where}: unknown engine variant {engine!r}")


@dataclass(frozen=True)
class Tier:
    """A per-unit ``{model, effort}`` tier (R2(b))."""

    model: str
    effort: str

    def validate(self, where: str, *, is_engine_owned: bool = False) -> None:
        if self.model not in MODELS:
            raise SpecError(f"{where}: model {self.model!r} not in {MODELS}")
        if self.effort not in EFFORTS:
            raise SpecError(f"{where}: effort {self.effort!r} not in {EFFORTS}")
        # AC6 (#370): a Claude teammate must not be assigned an effort above the model's
        # ceiling (e.g. haiku/xhigh) -- HALT loudly, never silently clamp or run an
        # un-runnable tier. Engine-owned chaperone-dispatch units are excluded: they stay
        # pinned to their chaperone tiers ({#external-engine-chaperone-dispatch}, #318).
        if not is_engine_owned and not _tier_palette.supports_effort(self.model, self.effort):
            ceiling = _tier_palette.effort_ceiling(self.model)
            raise SpecError(
                f"{where}: effort {self.effort!r} exceeds model {self.model!r} ceiling "
                f"{ceiling!r} -- unsupported {{model, effort}} combination (HALT, not clamp)"
            )

    @property
    def is_cheap(self) -> bool:
        """True iff this tier needs the structuredoutput-budget rider baked in."""
        return self.model in _CHEAP_MODELS

    @classmethod
    def from_dict(cls, data: dict[str, Any], where: str) -> Tier:
        if "model" not in data or "effort" not in data:
            raise SpecError(f"{where}: tier needs both 'model' and 'effort'")
        return cls(model=str(data["model"]), effort=str(data["effort"]))

    def to_dict(self) -> dict[str, str]:
        return {"model": self.model, "effort": self.effort}


@dataclass(frozen=True)
class Verify:
    """An optional refute-N judge-panel over a unit's output (KTD5).

    ``n`` verifier agents (same tier as the unit) review the unit's result; a finding
    survives unless refuted per ``pass_rule`` (majority / unanimous). The panel is
    bounded (KTD3): ``1 <= n <= VERIFY_N_CAP``, with a soft warn band above
    ``VERIFY_N_WARN`` -- the bound guards the rate-limit overcorrection.
    """

    n: int
    pass_rule: str
    iterate_to_consensus: bool = False
    max_iterations: int = 3

    def validate(self, where: str) -> None:
        if self.n < 1:
            raise SpecError(f"{where}: verify n={self.n} must be >= 1")
        if self.n > VERIFY_N_CAP:
            raise SpecError(
                f"{where}: verify n={self.n} exceeds the cap {VERIFY_N_CAP} "
                f"(KTD3 -- a bounded panel guards the rate-limit overcorrection)"
            )
        if self.n > VERIFY_N_WARN:
            print(
                f"WARN {where}: verify n={self.n} is in the warn band "
                f"({VERIFY_N_WARN} < n <= {VERIFY_N_CAP}) -- large panels risk the "
                f"rate-limit overcorrection.",
                file=sys.stderr,
            )
        if self.pass_rule not in PASS_RULES:
            raise SpecError(f"{where}: verify pass_rule {self.pass_rule!r} not in {PASS_RULES}")
        if self.max_iterations < 1:
            raise SpecError(f"{where}: verify max_iterations={self.max_iterations} must be >= 1")

    @classmethod
    def from_dict(cls, data: dict[str, Any], where: str) -> Verify:
        if "n" not in data or "pass_rule" not in data:
            raise SpecError(f"{where}: verify needs both 'n' and 'pass_rule'")
        try:
            n = int(data["n"])
        except (TypeError, ValueError) as exc:
            raise SpecError(f"{where}: verify n {data['n']!r} is not an integer") from exc

        iterate_to_consensus = bool(data.get("iterate_to_consensus", False))
        max_iterations_raw = data.get("max_iterations", 3)
        try:
            max_iterations = int(max_iterations_raw)
        except (TypeError, ValueError) as exc:
            raise SpecError(
                f"{where}: verify max_iterations {max_iterations_raw!r} is not an integer"
            ) from exc

        return cls(
            n=n,
            pass_rule=str(data["pass_rule"]),
            iterate_to_consensus=iterate_to_consensus,
            max_iterations=max_iterations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "pass_rule": self.pass_rule,
            "iterate_to_consensus": self.iterate_to_consensus,
            "max_iterations": self.max_iterations,
        }


@dataclass(frozen=True)
class Sandbox:
    """A delegated leaf's two-axis containment envelope (issue #287 R1-R3, KTD1).

    ``mutation_policy`` (read-only | read-write) is enforced by tool-set omission at spawn -- a
    restricted ``agentType`` without Edit/Write; ``workspace_isolation`` (ambient |
    disposable-worktree | owned-worktree) by worktree/clone routing. The isolation axis is the
    load-bearing clobber defense (R3): a Bash ``git checkout`` needs no Edit/Write tool, so tool
    omission alone cannot contain it -- only running in a throwaway worktree can.

    Absent on a Unit => ambient x read-write, exactly today's behavior. A bare profile string
    ("read-only-verify") is authoring shorthand that expands to its axis pair at ``from_dict``;
    the expanded pair is authoritative, so ``to_dict`` emits axes, not the shorthand. This class
    is mirrored verbatim in outcome_spec.py (deliberate parallel house, different error type).
    """

    mutation_policy: str
    workspace_isolation: str

    def validate(self, where: str) -> None:
        if self.mutation_policy not in MUTATION_POLICIES:
            raise SpecError(
                f"{where}: sandbox mutation_policy {self.mutation_policy!r} "
                f"not in {MUTATION_POLICIES}"
            )
        if self.workspace_isolation not in WORKSPACE_ISOLATIONS:
            raise SpecError(
                f"{where}: sandbox workspace_isolation {self.workspace_isolation!r} "
                f"not in {WORKSPACE_ISOLATIONS}"
            )

    @property
    def is_restrictive(self) -> bool:
        """True iff this sandbox narrows either axis below the ambient x read-write default.

        The enforceability matrix (U3) only needs to probe a backend when the sandbox actually
        constrains something -- a default sandbox is a no-op every backend "enforces".
        """
        return self.mutation_policy != "read-write" or self.workspace_isolation != "ambient"

    @classmethod
    def from_dict(cls, data: Any, where: str) -> Sandbox:
        # Profile-string shorthand (R2): expand to the canonical axis pair.
        if isinstance(data, str):
            if data not in SANDBOX_PROFILES:
                raise SpecError(
                    f"{where}: unknown sandbox profile {data!r} not in {tuple(SANDBOX_PROFILES)}"
                )
            mutation_policy, workspace_isolation = SANDBOX_PROFILES[data]
            return cls(mutation_policy=mutation_policy, workspace_isolation=workspace_isolation)
        if not isinstance(data, dict):
            raise SpecError(
                f"{where}: sandbox must be a profile string or a "
                f"{{mutation_policy, workspace_isolation}} object, got {type(data).__name__}"
            )
        # A profile key mixed with the explicit-axes form is the KTD1 conflict: two shorthands
        # racing. Force the author to pick one -- the bare string OR both axes spelled out.
        if "profile" in data:
            raise SpecError(
                f"{where}: sandbox 'profile' key conflicts with the explicit-axes form -- use a "
                f"bare profile string ('sandbox': 'read-only-verify') OR spell out both axes"
            )
        if "mutation_policy" not in data or "workspace_isolation" not in data:
            raise SpecError(
                f"{where}: sandbox needs both 'mutation_policy' and 'workspace_isolation' "
                f"(or a bare profile string)"
            )
        return cls(
            mutation_policy=str(data["mutation_policy"]),
            workspace_isolation=str(data["workspace_isolation"]),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "mutation_policy": self.mutation_policy,
            "workspace_isolation": self.workspace_isolation,
        }


def unenforceable_sandbox_axis(backend: str, sandbox: Sandbox | None) -> tuple[str, str] | None:
    """Return the (axis, value) ``backend`` cannot enforce for ``sandbox``, or None if it can.

    Only NON-default axis values need enforcing: ``mutation_policy=read-write`` and
    ``workspace_isolation=ambient`` are the ambient default (R1) and always fine. A backend absent
    from ``SANDBOX_ENFORCEABLE_BY_BACKEND`` enforces nothing, so any restrictive value trips (R4 --
    unknown never permissive). ``sandbox`` is duck-typed (execution_spec.Sandbox OR
    outcome_spec.Sandbox -- the two mirrors share this shape), so the one matrix serves both the
    Unit and the Node house. Returns the FIRST offending axis (mutation_policy before
    workspace_isolation) so a halt message can name a concrete axis.
    """
    if sandbox is None or not sandbox.is_restrictive:
        return None
    enforceable = SANDBOX_ENFORCEABLE_BY_BACKEND.get(backend, frozenset())
    if sandbox.mutation_policy != "read-write" and sandbox.mutation_policy not in enforceable:
        return ("mutation_policy", sandbox.mutation_policy)
    if sandbox.workspace_isolation != "ambient" and sandbox.workspace_isolation not in enforceable:
        return ("workspace_isolation", sandbox.workspace_isolation)
    return None


def unenforceable_tier(backend: str, tier: Tier) -> tuple[str, str] | None:
    """Return the (axis, value) ``backend`` cannot honor for ``tier``, or None if it can.

    v1 checks the MODEL axis (#369 KTD2): a backend can spawn only the models in its
    ``TIER_ENFORCEABLE_BY_BACKEND`` set. A backend absent from the matrix enforces nothing, so any
    authored model trips (R3 -- unknown never permissive, matching ``unenforceable_sandbox_axis``).
    Unlike the sandbox helper this is NOT duck-typed across houses: ``tier`` is an execution-spec
    ``Tier``, and ``outcome_spec.Node`` carries no {model, effort} tier to enforce. The EFFORT axis is
    not checked in v1 (it rides with the deferred per-teammate tier-floor mechanism). Returns the
    offending ("model", value) so a halt message can name a concrete model.
    """
    enforceable = TIER_ENFORCEABLE_BY_BACKEND.get(backend, frozenset())
    if tier.model not in enforceable:
        return ("model", tier.model)
    return None


def clamp_tier_to_ceiling(tier: Tier, ceiling: Tier) -> Tier:
    """Return ``tier`` clamped DOWN to ``ceiling`` on both axes (a ceiling never raises a tier).

    #365 U2: the session-ceiling primitive. Reuses the palette's 2-axis ladder ``clamp``
    (``{#tier-vocab-ordering}`` -- "no stronger than" is defined by strength, never raw index), so a
    ceiling weaker than the tier pulls each axis down and a ceiling already at-or-above the tier is a
    no-op. Both emitters (workflow + team) apply this before rendering a unit/segment tier (#365 U3).

    The result is always a RUNNABLE tier. A runnable ceiling can never yield an unrunnable result, but
    ``tier_session`` is not the only caller (the emitters accept a ``session_ceiling`` Tier directly),
    so as a total-function guarantee the clamped effort is finally pulled down to the clamped model's
    own ``effort_ceiling`` -- a no-op on the normal path, a safety net for a direct caller that passes
    an unrunnable ceiling (which ``tier_session`` rejects at write time).
    """
    model = _tier_palette.clamp("model", tier.model, ceiling=ceiling.model)
    effort = _tier_palette.clamp("effort", tier.effort, ceiling=ceiling.effort)
    effort = _tier_palette.clamp("effort", effort, ceiling=_tier_palette.effort_ceiling(model))
    return Tier(model=model, effort=effort)


@dataclass
class Unit:
    """One execution unit -- one ``agent()`` call in the emitted script.

    A *fan-out* unit (``fanout=True``) runs the same operation across many targets;
    it MUST carry an enumerated ``targets`` list (R10) so the run can reconcile what
    actually ran against what was declared -- never a silent filter. A fan-out unit
    MAY name a ``pilot`` unit that gates it (run one target first to de-risk the
    fan-out); the pilot MUST be at the SAME tier as the fan-out (R3).
    """

    unit_id: str
    label: str
    tier: Tier
    prompt: str
    # The structured-return contract: the required keys the agent must emit. Mirrors the
    # reference's UNIT_SCHEMA `required`. Empty list = no enforced contract (a barrier).
    returns: list[str] = field(default_factory=list)
    # Dependency barriers: unit_ids that must complete before this unit runs.
    depends_on: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    # Escalation: a human/operator note surfaced if the unit HALTs (resumable).
    escalation: str = ""
    # Fan-out: same op over many enumerated targets (R10).
    fanout: bool = False
    targets: list[str] = field(default_factory=list)
    # A pilot unit_id that gates this fan-out (run one first). Same-tier required (R3).
    pilot: str = ""
    # An optional refute-N judge-panel over this unit's output (KTD5). Absent => no panel;
    # an absent field round-trips unchanged so team_emitter / existing specs are untouched.
    verify: Verify | None = None
    # External-engine routing selectors (U5). Absent => normal Claude unit.
    engine: str | None = None
    capability: str | None = None
    # Delegation intent for an engine/capability unit (KTD2, U12). Valid only alongside
    # engine/capability; defaults to "offload" on parse when one of those is set (see
    # from_dict) -- tier itself stays a required field, this is a plan-time recommendation
    # input, not a schema default for tier.
    engine_intent: str | None = None
    # Sandbox capability envelope (#287 U1). Absent => ambient x read-write (today's behavior);
    # an absent field emits no new key so existing specs round-trip byte-identical.
    sandbox: Sandbox | None = None
    # Tier floor (#369 U2): the weakest tier this unit may resolve to. segment_units() clamps the
    # merged segment tier UP to this floor (never a silent downgrade). Absent => no floor; an absent
    # field emits no new key so existing specs round-trip byte-identical (R6).
    min_tier: Tier | None = None
    # Runtime ladder climbing (#364 U2): when this unit's verify panel refutes it, propose (attended)
    # or perform (unattended emit) exactly ONE rung of tier escalation via escalate_tier(). Absent /
    # False => today's behavior (refute throws); an absent field emits no new key so existing specs
    # round-trip byte-identical. v1 composition exclusions live in validate().
    escalate_on_signal: bool = False
    # #367 U3: an above-sonnet/medium-baseline tier must justify itself. ``worth_it_because`` is a
    # one-line rationale; ``cheaper_fallback`` names an adjacent strictly-cheaper Tier the operator
    # could pick instead. validate() requires BOTH only when the tier is above baseline (below that,
    # absent is fine). Absent fields emit no key (byte-identical round-trip, R5). NB: this
    # ``cheaper_fallback`` FIELD (an author-declared Tier) is distinct from
    # ``tier_resolver.cheaper_fallback`` the FUNCTION (which computes the one-rung-down default).
    worth_it_because: str = ""
    cheaper_fallback: Tier | None = None

    def validate(self, where: str, *, require_receipts: bool = False) -> None:
        if not self.unit_id:
            raise SpecError(f"{where}: a unit needs a non-empty unit_id")
        # Engine/capability-routed units are engine-owned (chaperone-dispatch); they are
        # excluded from the per-teammate effort-ceiling HALT (#370 AC6, #318).
        self.tier.validate(
            f"unit {self.unit_id}",
            is_engine_owned=self.engine is not None or self.capability is not None,
        )
        _validate_external_engine_selector(f"unit {self.unit_id}", self.engine, self.capability)
        if self.engine_intent is not None:
            if self.engine is None and self.capability is None:
                raise SpecError(f"unit {self.unit_id}: engine_intent requires engine or capability")
            if self.engine_intent not in ENGINE_INTENTS:
                raise SpecError(
                    f"unit {self.unit_id}: engine_intent {self.engine_intent!r} "
                    f"not in {ENGINE_INTENTS}"
                )
        if self.verify is not None:
            self.verify.validate(f"unit {self.unit_id}")
        if self.sandbox is not None:
            self.sandbox.validate(f"unit {self.unit_id}")
        if self.min_tier is not None:
            # Validated as a normal (non-engine) tier: off-palette model/effort fails (R5), and an
            # on-palette-but-unrunnable floor (e.g. haiku/xhigh) also halts via Tier.validate's ceiling
            # check -- a floor you cannot run is nonsense.
            self.min_tier.validate(f"unit {self.unit_id} min_tier")
        # #367 U3: a premium tier must justify itself (worth_it_because) and name a strictly cheaper
        # adjacent fallback, so premium spend is self-documenting and one downgrade away (KTD5). This
        # is gated on ``require_receipts`` -- enforced at the /plan AUTHORING boundary, NOT on the
        # unconditional validate() every emit and every existing spec re-runs (the issue's non-goal
        # forbids retroactively invalidating specs authored before the rule -- KTD8). Engine-owned
        # units are exempt: their tier is pinned by the chaperone-dispatch intent, not an operator
        # choice that needs a justification.
        is_engine_owned = self.engine is not None or self.capability is not None
        if require_receipts and not is_engine_owned and is_escalation(SPEND_BASELINE, self.tier):
            if not self.worth_it_because:
                raise SpecError(
                    f"unit {self.unit_id}: tier {self.tier.model}/{self.tier.effort} is a premium tier "
                    f"(above sonnet/high -- opus/fable model or xhigh effort) but carries no "
                    f"worth_it_because justification (#367)"
                )
            if self.cheaper_fallback is None:
                raise SpecError(
                    f"unit {self.unit_id}: premium tier {self.tier.model}/{self.tier.effort} names no "
                    f"cheaper_fallback (#367 -- premium spend must be one downgrade away)"
                )
            self.cheaper_fallback.validate(f"unit {self.unit_id} cheaper_fallback")
            if spend_delta(self.tier, self.cheaper_fallback) != "cheapen":
                raise SpecError(
                    f"unit {self.unit_id}: cheaper_fallback "
                    f"{self.cheaper_fallback.model}/{self.cheaper_fallback.effort} is not strictly "
                    f"cheaper than tier {self.tier.model}/{self.tier.effort} (#367)"
                )
        if "pull_cord" in self.returns:
            # #364 (verifier P2): pull_cord is the reserved worker-initiated escalation
            # disposition -- a legitimate return field with that name would be silently
            # swallowed as a cord by the gate. Reject at authoring time.
            raise SpecError(
                f"unit {self.unit_id}: 'pull_cord' is a reserved return-disposition key "
                f"(#364) -- rename the return field"
            )
        if self.escalate_on_signal:
            # #364 v1 composition exclusions (doc-review P1s): both would compound the one-rung
            # climb into unbounded spend -- the exact failure the issue forbids.
            if self.verify is None:
                raise SpecError(
                    f"unit {self.unit_id}: escalate_on_signal without a verify panel has no "
                    f"refute signal to react to -- add a verify panel or drop the flag"
                )
            if self.verify.iterate_to_consensus:
                raise SpecError(
                    f"unit {self.unit_id}: escalate_on_signal cannot compose with "
                    f"iterate_to_consensus in v1 -- nesting the consensus loop inside a climb "
                    f"retry compounds retry loops (unbounded spend)"
                )
            if self.fanout:
                raise SpecError(
                    f"unit {self.unit_id}: escalate_on_signal cannot compose with a fan-out "
                    f"unit in v1 -- a climb re-runs ALL targets, silently multiplying "
                    f"higher-tier spend"
                )
        if self.fanout and not self.targets:
            # R10: a fan-out unit MUST enumerate its targets -- never a silent filter.
            raise SpecError(
                f"unit {self.unit_id}: fan-out unit declares no enumerated targets "
                f"(R10 -- a fan-out without an explicit target list is a silent filter)"
            )
        if self.targets and not self.fanout:
            raise SpecError(
                f"unit {self.unit_id}: targets given but fanout=False -- "
                f"mark the unit fanout=True or drop the targets"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Unit:
        unit_id = str(data.get("unit_id", ""))
        where = f"unit {unit_id or '<missing id>'}"
        if "tier" not in data:
            raise SpecError(f"{where}: missing 'tier'")
        engine_raw = data.get("engine")
        capability_raw = data.get("capability")
        engine = str(engine_raw) if engine_raw is not None else None
        capability = str(capability_raw) if capability_raw is not None else None
        _validate_external_engine_selector(where, engine, capability)
        engine_intent_raw = data.get("engine_intent")
        engine_intent = str(engine_intent_raw) if engine_intent_raw is not None else None
        if engine_intent is None and (engine is not None or capability is not None):
            engine_intent = "offload"
        sandbox_raw = data.get("sandbox")
        sandbox = Sandbox.from_dict(sandbox_raw, where) if sandbox_raw else None
        min_tier_raw = data.get("min_tier")
        min_tier = Tier.from_dict(min_tier_raw, where) if min_tier_raw else None
        return cls(
            unit_id=unit_id,
            label=str(data.get("label", unit_id)),
            tier=Tier.from_dict(data["tier"], where),
            prompt=str(data.get("prompt", "")),
            returns=[str(r) for r in data.get("returns", [])],
            depends_on=[str(d) for d in data.get("depends_on", [])],
            files=[str(f) for f in data.get("files", [])],
            escalation=str(data.get("escalation", "")),
            fanout=bool(data.get("fanout", False)),
            targets=[str(t) for t in data.get("targets", [])],
            pilot=str(data.get("pilot", "")),
            verify=(Verify.from_dict(data["verify"], where) if data.get("verify") else None),
            engine=engine,
            capability=capability,
            engine_intent=engine_intent,
            sandbox=sandbox,
            min_tier=min_tier,
            escalate_on_signal=bool(data.get("escalate_on_signal", False)),
            worth_it_because=str(data.get("worth_it_because", "")),
            cheaper_fallback=(
                Tier.from_dict(data["cheaper_fallback"], where)
                if data.get("cheaper_fallback")
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "unit_id": self.unit_id,
            "label": self.label,
            "tier": self.tier.to_dict(),
            "prompt": self.prompt,
            "returns": list(self.returns),
            "depends_on": list(self.depends_on),
            "files": list(self.files),
            "escalation": self.escalation,
            "fanout": self.fanout,
            "targets": list(self.targets),
            "pilot": self.pilot,
        }
        # Only emit verify when present so an absent panel round-trips unchanged --
        # team_emitter and existing specs never gain a new key (R5).
        if self.verify is not None:
            out["verify"] = self.verify.to_dict()
        if self.engine is not None:
            out["engine"] = self.engine
        if self.capability is not None:
            out["capability"] = self.capability
        if self.engine_intent is not None:
            out["engine_intent"] = self.engine_intent
        # Absent sandbox emits no key (existing specs stay byte-identical); a profile-authored
        # sandbox emits its expanded axes -- the canonical form (KTD1).
        if self.sandbox is not None:
            out["sandbox"] = self.sandbox.to_dict()
        # Absent min_tier emits no key (existing specs stay byte-identical, R6); a declared floor
        # emits its {model, effort} pair.
        if self.min_tier is not None:
            out["min_tier"] = self.min_tier.to_dict()
        # False/absent escalate_on_signal emits no key (byte-identical round-trip, #364).
        if self.escalate_on_signal:
            out["escalate_on_signal"] = True
        # #367 U3: absent worth_it_because / cheaper_fallback emit no key (byte-identical, R5).
        if self.worth_it_because:
            out["worth_it_because"] = self.worth_it_because
        if self.cheaper_fallback is not None:
            out["cheaper_fallback"] = self.cheaper_fallback.to_dict()
        return out


def _optional_int_field(data: dict[str, Any], key: str) -> int | None:
    """Parse an optional int spec field (#366), rejecting bool and non-int loudly.

    Absent => None (byte-identical round-trip). ``bool`` is an int subclass, so ``true`` would
    silently coerce to 1 -- reject it explicitly.
    """
    raw = data.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise SpecError(f"spec {key} {raw!r} must be an integer, not a bool")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise SpecError(f"spec {key} {raw!r} is not an integer") from exc


def unit_spend(unit: Unit) -> int:
    """Ordinal spend for one unit's full call footprint (#366 KTD8).

    A unit is not always one agent call: a *fan-out* runs its op once per enumerated target,
    and a *verify* panel adds ``n`` verifier calls at the unit's tier (times ``max_iterations``
    when it iterates to consensus). A ``pilot`` is a SEPARATE declared unit, counted on its own
    row, so it is deliberately NOT re-added here -- that would double-count. A one-weight-per-unit
    sum would undercount exactly the expensive fan-out/panel plans and silently false-negative
    the cost HALT (the HALT-not-degrade violation U2 exists to prevent).
    """
    base = to_spend(unit.tier.model, unit.tier.effort)
    calls = len(unit.targets) if (unit.fanout and unit.targets) else 1
    total = base * calls
    if unit.verify is not None:
        iterations = unit.verify.max_iterations if unit.verify.iterate_to_consensus else 1
        total += unit.verify.n * base * iterations
    return total


@dataclass
class SpendEnvelope:
    """Run-scoped spend accumulator (#366 U3) -- 'ask once, at the crossing'.

    ``consider(delta)`` returns ``True`` (surface a prompt) ONLY on the choice that crosses the
    envelope: cumulative spend was at or under the envelope and this delta pushes it over. Choices
    that stay under are silent; once crossed, cumulative is already over the envelope so later
    choices never re-prompt -- a sequence with a single crossing prompts exactly once. The
    accumulator is pure: it decides prompt-or-silent, it never actually prompts (that surface is
    /plan / /work, not this primitive).
    """

    envelope: int
    _cumulative: int = 0

    def consider(self, delta: int) -> bool:
        """Fold one spend-increasing choice in; return True iff this choice crosses the envelope."""
        crosses = self._cumulative <= self.envelope < self._cumulative + delta
        self._cumulative += delta
        return crosses

    @property
    def cumulative(self) -> int:
        """Total spend folded in so far."""
        return self._cumulative

    @property
    def remaining(self) -> int:
        """Envelope headroom left (negative once the envelope has been crossed)."""
        return self.envelope - self._cumulative


@dataclass
class ExecutionSpec:
    """The structured execution-spec `/plan` authors and the emitters consume.

    One spec, two emitters (R9 / KTD6): ``emit_workflow_script`` (this module) and the
    team-execution markdown emitter (U11). Saga stores only an ``orchestration_ref``
    pointer to the emitted artifact.
    """

    name: str
    description: str
    units: list[Unit]
    # The repo the emitted workflow operates on (the harness `REPO` constant).
    repo: str = ""
    # Run-scoped spend ceiling (#366 U2). When set, validate()/emit HALT if the
    # multiplicity-aware summed spend (spec_spend()) exceeds it -- the emit-time cost HALT,
    # mirroring VERIFY_N_CAP. Absent (None) => no ceiling check; an absent field emits no key
    # so existing specs round-trip byte-identical (R10).
    cost_budget: int | None = None
    # Run-scoped spend envelope (#366 U3). The threshold that collapses "ask before every
    # expensive choice" into "ask once, at the crossing" -- consumed by the `spend` CLI verb
    # /plan surfaces and by /work's #364 between-rounds escalation (consult before proposing a
    # climb). It is a CLI-set field + accumulator primitive (SpendEnvelope), NOT an autonomous
    # runtime gate. Absent (None) emits no key (byte-identical round-trip, R10).
    spend_envelope: int | None = None

    def unit_by_id(self, unit_id: str) -> Unit | None:
        for unit in self.units:
            if unit.unit_id == unit_id:
                return unit
        return None

    def spec_spend(self) -> int:
        """The multiplicity-aware summed ordinal spend across every unit (#366 KTD8)."""
        return sum(unit_spend(u) for u in self.units)

    def validate(self, *, require_receipts: bool = False) -> None:
        """Validate the whole spec, enforcing the R3 + R10 authoring invariants.

        Raises ``SpecError`` on the first violation found (fail emit). Checks, in order:
        non-empty name + units; unique unit ids; per-unit validity (incl. R10 fan-out
        targets); every ``depends_on`` / ``pilot`` resolves to a real unit; and R3 --
        a pilot is at the SAME tier as the fan-out it gates.

        ``require_receipts`` (#367) additionally enforces the premium-tier worth-it hard-block
        (worth_it_because + cheaper_fallback). It is OFF by default so emit and existing specs are
        unaffected; ``/plan`` passes it True at the authoring boundary (KTD8).
        """
        if not self.name:
            raise SpecError("spec needs a non-empty name")
        if not self.units:
            raise SpecError("spec needs at least one unit")

        seen: set[str] = set()
        var_owner: dict[str, str] = {}
        for unit in self.units:
            unit.validate(f"spec {self.name}", require_receipts=require_receipts)
            if unit.unit_id in seen:
                raise SpecError(f"duplicate unit_id {unit.unit_id!r}")
            seen.add(unit.unit_id)
            # The emitted result var is the sanitized unit_id; two ids that sanitize to the
            # same JS identifier would emit a duplicate `const` (a SyntaxError in the ESM the
            # emitter produces). Reject the collision here rather than emit unloadable JS.
            js_var = _js_var(unit.unit_id)
            if js_var in var_owner:
                raise SpecError(
                    f"unit_id {unit.unit_id!r} and {var_owner[js_var]!r} both map to the JS "
                    f"identifier {js_var!r} (- and . both become _); rename one so the emitted "
                    f"script has unique result vars"
                )
            var_owner[js_var] = unit.unit_id

        for unit in self.units:
            for dep in unit.depends_on:
                if dep not in seen:
                    raise SpecError(
                        f"unit {unit.unit_id}: depends_on {dep!r} is not a declared unit"
                    )
            if unit.pilot:
                pilot = self.unit_by_id(unit.pilot)
                if pilot is None:
                    raise SpecError(
                        f"unit {unit.unit_id}: pilot {unit.pilot!r} is not a declared unit"
                    )
                if not unit.fanout:
                    raise SpecError(
                        f"unit {unit.unit_id}: declares a pilot but is not a fan-out unit"
                    )
                # R3: the pilot must be at the SAME tier as the fan-out it gates --
                # a mis-tiered pilot is an invalid oracle (it validates a different
                # cost surface than the fan-out runs on).
                if pilot.tier != unit.tier:
                    raise SpecError(
                        f"unit {unit.unit_id}: pilot {unit.pilot!r} tier "
                        f"{pilot.tier.to_dict()} != fan-out tier {unit.tier.to_dict()} "
                        f"(R3 -- a mis-tiered pilot is an invalid oracle)"
                    )

        # The dependency graph (depends_on + implicit pilot barriers) must be acyclic --
        # a cycle has no valid layering, so it fails validate (KTD4). This also re-checks
        # that every depends_on / pilot id resolves to a declared unit.
        dependency_layers(self)

        # #366 U2: the emit-time cost HALT. When a cost_budget is declared, the summed
        # multiplicity-aware spend must not exceed it -- fail loud naming BOTH sides (exactly
        # like VERIFY_N_CAP), because a silent over-budget run violates the /outcome campaign's
        # HALT-not-degrade rule. A soft warn band surfaces a run that is legal but near the ceiling.
        if self.cost_budget is not None:
            if self.cost_budget < 1:
                raise SpecError(
                    f"spec {self.name}: cost_budget {self.cost_budget} must be >= 1 "
                    f"(a budget below the cheapest call rejects every run)"
                )
            total = self.spec_spend()
            if total > self.cost_budget:
                raise SpecError(
                    f"spec {self.name}: total spend {total} exceeds cost_budget "
                    f"{self.cost_budget} (#366 -- HALT, not silent over-spend)"
                )
            if total > COST_BUDGET_WARN_FRACTION * self.cost_budget:
                headroom_pct = int(round((1 - COST_BUDGET_WARN_FRACTION) * 100))
                print(
                    f"WARN spec {self.name}: total spend {total} is within {headroom_pct}% of "
                    f"cost_budget {self.cost_budget} -- close to the ceiling.",
                    file=sys.stderr,
                )

        # #366 U3: a spend_envelope is a positive threshold; a zero/negative envelope is nonsense.
        if self.spend_envelope is not None and self.spend_envelope < 1:
            raise SpecError(f"spec {self.name}: spend_envelope {self.spend_envelope} must be >= 1")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionSpec:
        if "units" not in data or not isinstance(data["units"], list):
            raise SpecError("spec needs a 'units' list")
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            units=[Unit.from_dict(u) for u in data["units"]],
            repo=str(data.get("repo", "")),
            cost_budget=_optional_int_field(data, "cost_budget"),
            spend_envelope=_optional_int_field(data, "spend_envelope"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "repo": self.repo,
            "units": [u.to_dict() for u in self.units],
        }
        # Absent budget/envelope emit no key so existing specs round-trip byte-identical (R10).
        if self.cost_budget is not None:
            out["cost_budget"] = self.cost_budget
        if self.spend_envelope is not None:
            out["spend_envelope"] = self.spend_envelope
        return out


# ---------------------------------------------------------------------------
# Topological dependency layering (KTD4) -- the input to layer-parallel emission
# ---------------------------------------------------------------------------


def dependency_layers(spec: ExecutionSpec) -> list[list[str]]:
    """Compute topological layers (Kahn) of unit ids ready to run together (KTD4).

    Each returned layer is a list of unit ids whose dependencies are all satisfied by
    earlier layers, so a layer of >1 id renders as one ``parallel([...])`` wave and
    layers are sequenced by ``await``. Edges come from each unit's ``depends_on`` AND --
    so R3 is preserved -- from a fan-out unit's ``pilot``: the pilot is an implicit
    barrier edge (pilot -> fan-out), guaranteeing the pilot lands in an EARLIER layer
    than the fan-out it gates (otherwise both would share a parallel wave and the gate
    would be lost).

    Raises ``SpecError`` on a cycle (the remaining un-layered units are named) or on a
    ``depends_on`` / ``pilot`` id that resolves to no declared unit. Within a layer, ids
    keep declaration order for deterministic emission.
    """
    ids = [u.unit_id for u in spec.units]
    id_set = set(ids)

    # Build edges (predecessor -> successor) and an in-degree per unit. A pilot edge is
    # an IMPLICIT barrier (pilot before fan-out) on top of any explicit depends_on.
    preds: dict[str, set[str]] = {uid: set() for uid in ids}
    for unit in spec.units:
        for dep in unit.depends_on:
            if dep not in id_set:
                raise SpecError(f"unit {unit.unit_id}: depends_on {dep!r} is not a declared unit")
            preds[unit.unit_id].add(dep)
        if unit.pilot:
            if unit.pilot not in id_set:
                raise SpecError(f"unit {unit.unit_id}: pilot {unit.pilot!r} is not a declared unit")
            preds[unit.unit_id].add(unit.pilot)

    layers: list[list[str]] = []
    placed: set[str] = set()
    remaining = list(ids)  # declaration order preserved
    while remaining:
        ready = [uid for uid in remaining if preds[uid] <= placed]
        if not ready:
            # No unit is unblocked -> a cycle among the remaining units.
            raise SpecError(f"dependency cycle among units: {', '.join(sorted(remaining))}")
        layers.append(ready)
        placed.update(ready)
        remaining = [uid for uid in remaining if uid not in placed]

    return layers


# ---------------------------------------------------------------------------
# Emitter -- spec -> runnable Claude Code workflow script
# ---------------------------------------------------------------------------


def _js_string(value: str) -> str:
    """Encode a Python string as a single-quoted JS string literal.

    ``json.dumps`` gives a valid JS string (double-quoted, escaped); we keep that --
    it is the safest encoder for arbitrary prompt text.
    """
    return json.dumps(value)


def _js_var(unit_id: str) -> str:
    """Sanitize a unit_id into a JS identifier used as the emitted result var.

    ``-`` and ``.`` are not legal in JS identifiers, so both map to ``_``. Two distinct
    unit_ids can therefore collide to the same var (``a-b`` and ``a.b`` both -> ``a_b``),
    which would emit a duplicate ``const`` -- a SyntaxError in the ESM the emitter produces.
    ``ExecutionSpec.validate`` rejects that collision up front (fail emit, never emit
    unloadable JS).
    """
    return unit_id.replace("-", "_").replace(".", "_")


def _emit_gate_call(unit: Unit, var: str, session_ceiling: Tier | None = None) -> str:
    """Emit the __gate call for a unit."""
    opts: list[str] = [f"unitId: {_js_string(unit.unit_id)}"]
    expects_output = bool(unit.returns) or (unit.fanout and bool(unit.targets))
    opts.append(f"expectsOutput: {'true' if expects_output else 'false'}")
    if unit.targets:
        opts.append(f"targets: {len(unit.targets)}")
    if unit.returns:
        ret_strs = ", ".join(_js_string(r) for r in unit.returns)
        opts.append(f"returns: [{ret_strs}]")
        # #364 R8: the one-rung proposal a pulled cord carries into the batched escalation
        # entry -- computed at emit time (escalate_tier is pure); null at the top of the ladder
        # OR when the #365 session ceiling blocks the climb (the ceiling is the final word -- a
        # cord must never propose a tier the operator's own cap forbids; verifier P1).
        cord_climb = escalate_tier(unit.tier, ceiling=session_ceiling)
        if cord_climb is not None:
            cord_axis = "effort" if cord_climb.model == unit.tier.model else "model"
            opts.append(
                "cordProposal: "
                + _js_string(
                    f"{unit.tier.model}/{unit.tier.effort} -> "
                    f"{cord_climb.model}/{cord_climb.effort} (+1 {cord_axis} rung)"
                )
            )
    opts_str = ", ".join(opts)
    return f"__gate({var}, {{ {opts_str} }})"


# R3/KTD3: every emitted parallel-wave/panel ``agent()`` call is wrapped in the ``__retry``
# helper. The open/close/opts fragments are single-sourced here so the four wrapped sites
# (``_emit_thunk``'s three forms + the refute-N panel verifiers) cannot drift -- the same
# dead-wiring risk ``_verifier_agent_opts`` exists to kill. Singleton ``await agent(`` calls are
# deliberately NOT wrapped (R3 scopes retry to waves, where the concurrency-driven rate-limit
# pressure lives; a singleton 429 still HALTs).
_RETRY_MAX_ATTEMPTS = 3


def _retry_opts_js(unit: Unit) -> str:
    """Opts object for a ``__retry(...)`` wrapper around a wave/panel ``agent()`` call."""
    return f"{{ unitId: {_js_string(unit.unit_id)}, maxAttempts: {_RETRY_MAX_ATTEMPTS} }}"


def _retry_open() -> str:
    """Open fragment: ``__retry(() => agent(`` -- the wave/panel 429-retry wrapper."""
    return "__retry(() => agent("


def _retry_close(unit: Unit) -> str:
    """Close fragment: ``), <opts>`` -- balances the ``agent(`` and ``__retry(`` parens."""
    return f"), {_retry_opts_js(unit)}"


def _external_engine_selector(unit: Unit) -> tuple[str, str] | None:
    if unit.engine is not None:
        return ("engine", unit.engine)
    if unit.capability is not None:
        return ("capability", unit.capability)
    return None


def _external_engine_marker(unit: Unit) -> str | None:
    selector = _external_engine_selector(unit)
    if selector is None:
        return None
    key, value = selector
    return f"{key}={value}"


def _agent_opts(unit: Unit) -> list[str]:
    opts = [f"label: {_js_string(unit.label)}"]
    selector = _external_engine_selector(unit)
    if selector is not None:
        key, value = selector
        opts.append('dispatch: "external-engine"')
        opts.append(f"{key}: {_js_string(value)}")
        return opts
    opts.append(f"model: {_js_string(unit.tier.model)}")
    opts.append(f"effort: {_js_string(unit.tier.effort)}")
    return opts


def _verifier_prompt(unit: Unit) -> str:
    """Assemble the prompt text a verifier agent in ``unit``'s refute-N panel reads.

    A verifier is an adversarial skeptic over the unit's result: it tries to REFUTE the
    unit's findings, not to re-do the work. Cheap-tier panels (same tier as the unit per
    R4) carry the budget rider so a budget-exhausted verifier still emits its verdict.
    """
    parts: list[str] = [
        f"REFUTE-N VERIFIER over unit {unit.unit_id} ({unit.label}). You are an adversarial "
        f"skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's "
        f"output and the evidence it cites; for each claimed finding decide REFUTED (with a "
        f"concrete reason) or UPHELD. Emit a structured verdict {{refuted: [...], upheld: [...]}}."
    ]
    if unit.tier.is_cheap:
        parts.append(BUDGET_RIDER)
    return "\n\n".join(parts)


def _verifier_agent_opts(unit: Unit) -> list[str]:
    """Build the agent() opts for one verifier call in ``unit``'s refute-N panel (#287 U2).

    Single source of truth for all three verifier-emitting sites (``_emit_thunk``,
    ``_emit_verify_loop_singleton``, ``_emit_verify_panel``) so the enforcement opts cannot drift
    across them -- three hand-maintained copies is exactly the R9 dead-wiring risk. Every verifier
    is spawned read-only-verify UNCONDITIONALLY (KTD6): the restricted ``agentType`` omits
    Edit/Write (mutation_policy: read-only) and ``isolation: 'worktree'`` runs it in a throwaway
    worktree (workspace_isolation: disposable-worktree), so a verifier's Bash ``git checkout``
    cannot clobber the primary tree. No opt-out -- a verifier that needs write access is a design
    smell, and an opt-out would be an escalation channel contradicting R8. The unit's per-tier
    ``model``/``effort`` still ride so the panel runs at the same tier as the unit (R4).
    """
    return [
        f"label: {_js_string(unit.label + ' verifier')}",
        f"model: {_js_string(unit.tier.model)}",
        f"effort: {_js_string(unit.tier.effort)}",
        f"agentType: {_js_string(READONLY_VERIFIER_AGENT_TYPE)}",
        f"isolation: {_js_string(READONLY_VERIFIER_ISOLATION)}",
    ]


def _emit_panel_reconciliation(
    lines: list[str],
    unit: Unit,
    result_var: str,
    name_prefix: str,
    indent: str,
    *,
    direct_throw: bool,
    open_refuted_block: bool = False,
    throw_suffix: str = "",
) -> None:
    """Emit the verdict-collection / threshold / consumer block for a refute-N panel (plan KTD5).

    Single source of truth for the reconciliation shared by ``_emit_thunk``,
    ``_emit_verify_loop_singleton``, and ``_emit_verify_panel`` -- three hand-maintained copies
    is the same drift risk ``_verifier_agent_opts`` was created to kill for verifier opts.
    ``name_prefix`` disambiguates the one-shot panel's top-level ``const`` names (unit-scoped,
    e.g. ``"result_"``) from the iterate sites' block-scoped bare names (``""``). ``direct_throw``
    selects the one-shot panel's immediate throw-if-refuted consumer instead of the iterate
    loop's break-if-accepted / throw-at-max-iterations consumer; callers remain responsible for
    opening/closing their own enclosing loop.

    #364 escalate_on_signal consumers: ``throw_suffix`` (direct_throw only) appends a static
    tail inside the thrown template literal -- the attended escalation-proposal / at-top HALT
    annotation. ``open_refuted_block`` (direct_throw only) replaces the throw with an OPEN
    ``if (<refuted>) {`` block the caller fills (the unattended one-rung climb retry) and must
    close.
    """
    panel = unit.verify
    assert panel is not None
    n = panel.n
    floor = (n + 1) // 2  # plan KTD3: quorum floor, baked as a literal per panel
    verifier_prompt = _verifier_prompt(unit)
    verifier_opts = _verifier_agent_opts(unit)

    verdicts_var = f"{name_prefix}verdicts"
    reported_var = f"{name_prefix}reported"
    missing_idx_var = f"{name_prefix}missing_idx"
    refute_count_var = f"{name_prefix}refute_count"
    threshold_var = f"{name_prefix}threshold"
    refuted_var = f"{name_prefix}refuted"

    lines.append(f"{indent}const {verdicts_var} = await parallel([")
    for _ in range(n):
        lines.append(f"{indent}  () => {_retry_open()}")
        lines.append(f"{indent}    {_js_string(verifier_prompt)},")
        lines.append(f"{indent}    {{ " + ", ".join(verifier_opts) + f", input: {result_var} }},")
        lines.append(f"{indent}  {_retry_close(unit)}),")
    lines.append(f"{indent}])")
    # R1/R5: record which verifiers reported vs. runtime-missing; R3: recompute the pass-rule
    # threshold over the reporters, not the declared n (plan KTD1/KTD3). A verdict that is
    # non-null but lacks a usable `.refuted` array is a runtime failure too (a verifier that
    # returned a malformed/partial response is not distinguishable from one that returned a
    # legitimate non-refuting verdict unless shape is checked here -- completeness_gate.py's
    # classify() only gates the unit's own result, never verifier verdicts, so this is the only
    # place malformed verdicts get caught).
    lines.append(
        f"{indent}const {reported_var} = {verdicts_var}.filter((v) => "
        f"v != null && Array.isArray(v.refuted))"
    )
    lines.append(
        f"{indent}const {missing_idx_var} = {verdicts_var}.map((v, i) => "
        f"(v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)"
    )
    lines.append(
        f"{indent}const {refute_count_var} = {reported_var}.filter((v) => "
        f"v.refuted.length > 0).length"
    )
    if panel.pass_rule == "majority":
        lines.append(
            f"{indent}const {threshold_var} = "
            f"Math.max(1, Math.ceil({reported_var}.length / 2))  // majority over reporters"
        )
    else:
        lines.append(
            f"{indent}const {threshold_var} = "
            f"Math.max(1, {reported_var}.length)  // unanimous over reporters"
        )
    lines.append(f"{indent}const {refuted_var} = {refute_count_var} >= {threshold_var}")
    # R4/R5: annotate missing verifiers and mark UNDER-STRENGTH below the baked quorum floor;
    # this fires on both the accept and refute paths -- plan KTD4 keeps refutation acting
    # regardless of under-strength.
    lines.append(f"{indent}if ({missing_idx_var}.length > 0) {{")
    lines.append(
        f"{indent}  log(`verify panel over {unit.unit_id}: "
        f"${{{missing_idx_var}.length}}/{n} verifier(s) missing "
        f'(runtime-failure: #${{{missing_idx_var}.join(", #")}}); '
        f"verdict computed over ${{{reported_var}.length}}/{n}` +"
    )
    lines.append(
        f"{indent}      ({reported_var}.length < {floor} ? "
        f'" — UNDER-STRENGTH (quorum floor {floor})" : ""))'
    )
    lines.append(f"{indent}}}")

    throw_line = (
        f"throw new Error(`verifier-disagreement: Unit {unit.unit_id} refuted by "
        f"${{{refute_count_var}}}/${{{reported_var}.length}} reporting verifiers "
        f"(${{{missing_idx_var}.length}} missing){throw_suffix}`)"
    )
    if direct_throw:
        if open_refuted_block:
            # #364 unattended climb: the caller fills the refuted block (one-rung retry) and
            # closes it -- the reconciliation stays the single source of the verdict math.
            lines.append(f"{indent}if ({refuted_var}) {{")
            return
        lines.append(f"{indent}if ({refuted_var}) {{")
        lines.append(f"{indent}  {throw_line}")
        lines.append(f"{indent}}}")
        lines.append("")
    else:
        lines.append(f"{indent}if (!{refuted_var}) {{")
        lines.append(f"{indent}  break")
        lines.append(f"{indent}}}")
        lines.append(f"{indent}if (iter === {panel.max_iterations}) {{")
        lines.append(f"{indent}  {throw_line}")
        lines.append(f"{indent}}}")


def _emit_thunk(
    lines: list[str], spec: ExecutionSpec, unit: Unit, session_ceiling: Tier | None = None
) -> None:
    """Append one thunk entry for ``unit`` inside a ``parallel([...])``.

    Every thunk carries the unit's per-unit ``{model, effort}`` tier (R2(b)) and the same
    budget-rider / R10 reconciliation prompt as a singleton agent() call.
    """
    if unit.verify is not None and unit.verify.iterate_to_consensus:
        panel = unit.verify
        prompt = _agent_prompt(spec, unit)
        opts = _agent_opts(unit)
        marker = _external_engine_marker(unit)

        lines.append("  async () => {")
        lines.append("    let result;")
        lines.append(f"    for (let iter = 1; iter <= {panel.max_iterations}; iter++) {{")
        if marker is not None:
            lines.append(f"      // external-engine dispatch: {marker}")
        lines.append(f"      result = await {_retry_open()}")
        lines.append(f"        {_js_string(prompt)},")
        lines.append("        { " + ", ".join(opts) + " },")
        lines.append(f"      {_retry_close(unit)})")
        lines.append(f"      {_emit_gate_call(unit, 'result', session_ceiling)}")
        _emit_panel_reconciliation(lines, unit, "result", "", "      ", direct_throw=False)
        lines.append("    }")
        lines.append("    return result")
        lines.append("  },")
    else:
        prompt = _agent_prompt(spec, unit)
        opts = _agent_opts(unit)
        marker = _external_engine_marker(unit)
        if marker is not None:
            lines.append("  () => {")
            lines.append(f"    // external-engine dispatch: {marker}")
            lines.append(f"    return {_retry_open()}")
            lines.append(f"      {_js_string(prompt)},")
            lines.append("      { " + ", ".join(opts) + " },")
            lines.append(f"    {_retry_close(unit)})")
            lines.append("  },")
        else:
            lines.append("  () =>")
            lines.append(f"    {_retry_open()}")
            lines.append(f"      {_js_string(prompt)},")
            lines.append("      { " + ", ".join(opts) + " },")
            lines.append(f"    {_retry_close(unit)}),")


def _emit_verify_loop_singleton(
    lines: list[str],
    spec: ExecutionSpec,
    unit: Unit,
    var: str,
    session_ceiling: Tier | None = None,
) -> None:
    """Emit the iterate-to-consensus loop for a singleton unit."""
    panel = unit.verify
    assert panel is not None
    n = panel.n
    prompt = _agent_prompt(spec, unit)
    opts = _agent_opts(unit)
    marker = _external_engine_marker(unit)

    lines.append(f"let {var};")
    lines.append(
        f"// verify: refute-{n} iterate-to-consensus loop over {unit.unit_id} "
        f"(pass_rule: {panel.pass_rule}, max_iterations: {panel.max_iterations})"
    )
    lines.append(f"for (let iter = 1; iter <= {panel.max_iterations}; iter++) {{")
    if marker is not None:
        lines.append(f"  // external-engine dispatch: {marker}")
    lines.append(f"  {var} = await agent(")
    lines.append(f"    {_js_string(prompt)},")
    lines.append("    { " + ", ".join(opts) + " },")
    lines.append("  )")
    lines.append(f"  {_emit_gate_call(unit, var, session_ceiling)}")
    _emit_panel_reconciliation(lines, unit, var, "", "  ", direct_throw=False)
    lines.append("}")
    lines.append("")


def _emits_climb_retry(unit: Unit, unattended: bool, session_ceiling: Tier | None) -> bool:
    """True when the emitted script will contain an in-script climb retry for this unit (#364).

    Single predicate shared by the `let`-vs-`const` declaration sites and (implicitly) the
    verify-panel emission -- an at-top or ceiling-blocked unit emits no retry, so its var is
    never reassigned and its declaration stays const (byte-stable for all non-climbing output).
    """
    return (
        unattended
        and unit.escalate_on_signal
        and escalate_tier(unit.tier, ceiling=session_ceiling) is not None
    )


def _emit_verify_panel(
    lines: list[str],
    spec: ExecutionSpec,
    unit: Unit,
    var: str,
    *,
    unattended: bool = False,
    session_ceiling: Tier | None = None,
) -> None:
    """Append a refute-N judge-panel + pass-rule reconciliation for ``unit`` to ``lines``.

    Renders a ``parallel([...])`` of ``unit.verify.n`` verifier ``agent()`` calls over the
    unit's result (each at the SAME ``{model, effort}`` tier as the unit per R4), then
    records which verifiers reported vs. runtime-missing (R1/R5) -- a ``null`` verdict slot
    OR a non-null verdict lacking a usable ``.refuted`` array both count as missing, since
    neither is a trustworthy signal -- and recomputes the pass-rule threshold over the
    reporters (R3): ``majority`` => ``>= max(1, ceil(k/2))`` of the ``k`` reporting verifiers
    refuted; ``unanimous`` => all ``k`` refuted. A quorum floor of ``ceil(n/2)`` of the
    declared ``n`` (plan KTD3) marks the result UNDER-STRENGTH when under-met, but a
    refutation still acts regardless (plan KTD4).
    (This is a panel-level signal, not per-finding survival: a generic emitter cannot match
    findings across verifiers, so it surfaces "did enough skeptics refute anything" for the
    operator/runtime to act on.) The resulting ``<var>_refuted`` boolean is CONSUMED: when
    set, the script THROWS ``verifier-disagreement: ...`` so a refuted unit result halts
    rather than being silently relied upon.
    """
    panel = unit.verify
    assert panel is not None  # caller guards this
    n = panel.n
    floor = (n + 1) // 2

    lines.append(f"// verify: refute-{n} panel over {unit.unit_id} (pass_rule: {panel.pass_rule};")
    lines.append(
        f"// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is "
        f"met (quorum floor {floor} of {n} declared; runtime-missing verifiers shrink the "
        f"denominator))"
    )
    if not unit.escalate_on_signal:
        _emit_panel_reconciliation(lines, unit, var, f"{var}_", "", direct_throw=True)
        return

    # Runtime ladder climbing (#364): a refuted escalate_on_signal unit proposes (attended) or
    # performs (unattended) exactly ONE rung of escalation. The climb is computed at emit time --
    # escalate_tier is pure over the unit's (already ceiling-clamped) tier, so the emitted script
    # stays deterministic. A ceiling-blocked or at-top climb HALTs (KTD2/KTD5), never loops.
    climbed = escalate_tier(unit.tier, ceiling=session_ceiling)
    if climbed is None:
        blocked_by_ceiling = session_ceiling is not None and escalate_tier(unit.tier) is not None
        reason = "climb blocked by session ceiling" if blocked_by_ceiling else "at top of ladder"
        _emit_panel_reconciliation(
            lines,
            unit,
            var,
            f"{var}_",
            "",
            direct_throw=True,
            throw_suffix=(
                f" -- escalate_on_signal: {reason}, no rung above "
                f"{unit.tier.model}/{unit.tier.effort} (HALT, not loop -- #364 R3)"
            ),
        )
        return
    axis = "effort" if climbed.model == unit.tier.model else "model"
    proposal = (
        f"{unit.tier.model}/{unit.tier.effort} -> {climbed.model}/{climbed.effort} (+1 {axis} rung)"
    )
    if not unattended:
        # Attended (KTD4): the ask gate is throw-with-proposal -- the /work operator loop
        # confirms via the existing #365 /tier patch + re-emit; no silent higher-tier re-run.
        _emit_panel_reconciliation(
            lines,
            unit,
            var,
            f"{var}_",
            "",
            direct_throw=True,
            throw_suffix=(
                f" -- escalation-proposal (#364 R5): re-run {unit.unit_id} at "
                f"{proposal}; confirm via /tier patch and re-emit"
            ),
        )
        return

    # Unattended (KTD5): ONE in-script climb retry, then a fresh panel at the climbed tier
    # (R4: the panel matches the unit it verifies), then HALT if still refuted. Never a second
    # climb in the same run -- chained silent climbs are the unbounded-overspend failure.
    retry_unit = replace(unit, tier=climbed)
    _emit_panel_reconciliation(
        lines, unit, var, f"{var}_", "", direct_throw=True, open_refuted_block=True
    )
    lines.append(
        f"  log(`escalate_on_signal: {unit.unit_id} refuted at "
        f"{unit.tier.model}/{unit.tier.effort}; climbing ONE rung to "
        f"{climbed.model}/{climbed.effort} and retrying once (unattended, #364 R6)`)"
    )
    lines.append(f"  {var} = await agent(")
    lines.append(f"    {_js_string(_agent_prompt(spec, retry_unit))},")
    lines.append(f"    {{ {', '.join(_agent_opts(retry_unit))} }},")
    lines.append("  )")
    lines.append(f"  {_emit_gate_call(retry_unit, var, session_ceiling)}")
    _emit_panel_reconciliation(
        lines,
        retry_unit,
        var,
        f"{var}_retry_",
        "  ",
        direct_throw=True,
        throw_suffix=(
            f" -- still refuted after the one-rung climb to "
            f"{climbed.model}/{climbed.effort} (HALT -- #364 KTD5: one climb per unit per run)"
        ),
    )
    lines.append("}")
    lines.append("")


def _agent_prompt(spec: ExecutionSpec, unit: Unit) -> str:
    """Assemble the prompt text for a unit's emitted ``agent()`` call.

    Bakes the budget rider into cheap-tier (haiku) agents (R9 mitigation) and appends
    the enumerated-target reconciliation instruction for fan-out units (R10).
    """
    parts: list[str] = [unit.prompt]
    if unit.tier.is_cheap:
        parts.append(BUDGET_RIDER)
    if unit.fanout:
        targets = ", ".join(unit.targets)
        parts.append(
            f"FAN-OUT TARGETS ({len(unit.targets)}, enumerated -- run the operation across "
            f"EXACTLY these, no silent filter): {targets}. "
            f"RECONCILE after the run: report any declared target you did NOT complete "
            f"(R10 -- a missing target is a reported gap, never silently dropped)."
        )
    if unit.returns:
        parts.append(
            "RETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object "
            "with the keys " + ", ".join(unit.returns) + " -- no prose, no markdown code fences, "
            "no YAML, and nothing before or after the JSON. The workflow gate parses this final "
            "message as JSON and FAILS the unit if it is not a JSON object carrying these keys. "
            "Emit it as your last action even if the work is only partial (fill each key with what "
            "you have plus a short note)."
        )
        if unit.tier.is_cheap:
            # #364 R7: the cord rider rides the cheap-tier return contract (beside BUDGET_RIDER)
            # -- the worker-initiated depth signal only matters where under-tiering is plausible.
            parts.append(
                "PULL-CORD (#364, overrides the return contract above when it applies): if you "
                "judge this task is genuinely beyond your depth -- not merely hard, but you "
                "cannot produce a substantively correct result at your tier -- emit ONLY "
                '{"pull_cord": "<one-line reason>"} as your final message instead of the return '
                "contract. The coordinator batches every pulled cord into ONE escalation ask; "
                "your unit is never marked complete. Never pull the cord for partial-but-sound "
                "work (use the return contract with a note instead)."
            )
    return "\n\n".join(p for p in parts if p)


def escalate_tier(tier: Tier, *, ceiling: Tier | None = None) -> Tier | None:
    """Return the tier exactly one rung stronger, or None when no legal rung exists (#364 R1).

    Effort-first, then model (KTD1): climb the EFFORT axis while the current model supports a
    stronger effort; at the model's effort ceiling, climb the MODEL axis one rung keeping effort
    (runnability validated via ``supports_effort``, never assumed). Built on the named palette ops
    -- raw ``MODELS.index()`` arithmetic is forbidden (see segment_units). The palette's
    ``escalate`` deliberately no-ops at the top rung; the *runtime* at-the-top / blocked-by-ceiling
    signal is ``None`` (KTD2) -- every caller renders it as an explicit HALT/end-clamp, never a
    silent same-tier re-run. A ``ceiling`` (e.g. the #365 session ceiling) blocks any climb that
    would exceed it on either axis.
    """
    cand_effort = _tier_palette.escalate("effort", tier.effort)
    if cand_effort != tier.effort and _tier_palette.supports_effort(tier.model, cand_effort):
        new = Tier(model=tier.model, effort=cand_effort)
    else:
        cand_model = _tier_palette.escalate("model", tier.model)
        if cand_model == tier.model or not _tier_palette.supports_effort(cand_model, tier.effort):
            return None  # top of the ladder (or no runnable one-rung move) -- caller HALTs
        new = Tier(model=cand_model, effort=tier.effort)
    if ceiling is not None and is_escalation(ceiling, new):
        return None  # climb blocked by the ceiling -- caller HALTs/asks, never exceeds
    return new


def is_escalation(old: Tier, new: Tier) -> bool:
    """True iff ``new`` is stronger than ``old`` on either axis -- an up-ladder move (#365 R6).

    Uses the palette's direction-agnostic ``stronger`` so "stronger" is defined by the ladder, never
    raw index. A cheapen-or-lateral move (``new`` no stronger on either axis) returns False and, per
    R6, proceeds without a confirmation prompt.

    NOTE (#367): this is deliberately NOT ``spend_delta(old, new) == "escalate"``. A *mixed* move
    (stronger on one axis, weaker on the other) is an escalation here (returns True -- it raises spend
    on at least one axis, so the /tier gate must ask) while ``spend_delta`` classifies it ``lateral``.
    Both share ``_axis_deltas`` but keep distinct predicates.
    """
    dm, de = _axis_deltas(old, new)
    return dm > 0 or de > 0


# Baseline above which a tier is "premium" and must justify itself (#367 KTD5). A tier is premium iff
# ``is_escalation(SPEND_BASELINE, tier)`` -- stronger than sonnet/high on either axis, i.e. an opus/fable
# model OR xhigh effort (exactly the issue's "opus, fable, xhigh in either axis"). Baseline is sonnet/HIGH
# (not sonnet/medium) so a common sonnet/high unit is NOT retroactively flagged -- the issue's parenthetical
# premium set, not the misleading "sonnet/medium" phrasing, is authoritative (the ACs test opus/high and
# fable/xhigh). The worth-it hard-block and the spend-authority default share this predicate so the two
# levers cannot disagree about what "expensive" means.
SPEND_BASELINE = Tier(model="sonnet", effort="high")


def _axis_deltas(old: Tier, new: Tier) -> tuple[int, int]:
    """Per-axis strength direction ``(dm, de)`` from ``old`` to ``new``, each in ``{-1, 0, +1}``.

    ``+1`` = ``new`` is stronger on that axis, ``-1`` = weaker, ``0`` = same. Direction is defined by
    the palette's ``stronger`` op (never raw ``.index()``), so ``is_escalation`` (two-way) and
    ``spend_delta`` (three-way) reason about the exact same ladder (#367 KTD2).
    """

    def _direction(kind: str, a: str, b: str) -> int:
        if a == b:
            return 0
        return 1 if _tier_palette.stronger(kind, b, a) == b else -1

    return _direction("model", old.model, new.model), _direction("effort", old.effort, new.effort)


def spend_delta(old: Tier, new: Tier) -> Literal["cheapen", "escalate", "lateral"]:
    """Classify a tier change's direction (#367 R1 / KTD1).

    ``escalate`` = stronger on >=1 axis and weaker on none; ``cheapen`` = weaker on >=1 axis and
    stronger on none; ``lateral`` = a sideways trade (stronger on one axis, weaker on the other) or an
    identical tier. Built on per-axis ordering (``_axis_deltas``), NOT on ``to_spend`` magnitude: the
    cost-weight table is injective, so a magnitude reading could never produce ``lateral`` (KTD1).
    ``to_spend`` answers "how much?"; ``spend_delta`` answers "which way?".
    """
    dm, de = _axis_deltas(old, new)
    if dm >= 0 and de >= 0 and (dm > 0 or de > 0):
        return "escalate"
    if dm <= 0 and de <= 0 and (dm < 0 or de < 0):
        return "cheapen"
    return "lateral"


def adjacent_tier(tier: Tier, direction: Literal["cheaper", "dearer"]) -> Tier:
    """Return ``tier`` moved exactly one rung ``cheaper`` or ``dearer`` (#367 R3 / KTD3-KTD4).

    ``cheaper`` reuses ``tier_resolver.cheaper_fallback`` (weaken model first, then effort) so it
    cannot drift from #362's convention; ``dearer`` is the symmetric one-rung-up via the palette
    ``escalate`` op (strengthen model first, then effort). A boundary call -- cheapening the cheapest
    tier or dearer-ing the dearest -- RAISES ``SpecError`` rather than clamping or wrapping (KTD4).
    """
    if direction == "cheaper":
        model, effort = _tier_resolver.cheaper_fallback(tier.model, tier.effort)
        if (model, effort) == (tier.model, tier.effort):
            raise SpecError(
                f"adjacent_tier: {tier.model}/{tier.effort} is already the cheapest tier -- "
                f"cannot go cheaper (#367 -- boundary raises, never clamps)"
            )
        return Tier(model=model, effort=effort)
    if direction == "dearer":
        stronger_model = _tier_palette.escalate("model", tier.model)
        if stronger_model != tier.model:
            return Tier(model=stronger_model, effort=tier.effort)
        stronger_effort = _tier_palette.escalate("effort", tier.effort)
        if stronger_effort != tier.effort:
            return Tier(model=tier.model, effort=stronger_effort)
        raise SpecError(
            f"adjacent_tier: {tier.model}/{tier.effort} is already the dearest tier -- "
            f"cannot go dearer (#367 -- boundary raises, never clamps)"
        )
    raise SpecError(
        f"adjacent_tier: unknown direction {direction!r} (expected 'cheaper' or 'dearer')"
    )


def patch_spec_tiers(
    spec: ExecutionSpec,
    unit_overrides: dict[str, Tier],
    already_run_ids: Iterable[str],
) -> ExecutionSpec:
    """Return a copy of ``spec`` with each NOT-yet-run named unit's tier replaced (#365 U4, R4).

    A unit is patched iff its id is in ``unit_overrides`` and NOT in ``already_run_ids`` -- an
    already-run unit's recorded tier is never edited. Unknown ids in ``unit_overrides`` are ignored
    (the operator may name a unit that does not exist; the caller warns). The returned spec must be
    re-``validate``d before emit (R5) -- this function does not validate, it only rewrites tiers.
    """
    run = set(already_run_ids)
    patched = [
        replace(u, tier=unit_overrides[u.unit_id])
        if (u.unit_id in unit_overrides and u.unit_id not in run)
        else u
        for u in spec.units
    ]
    return replace(spec, units=patched)


def emit_workflow_script(
    spec: ExecutionSpec,
    session_ceiling: Tier | None = None,
    unattended: bool = False,
) -> str:
    """Emit a runnable Claude Code workflow script (.workflow.js) from the spec.

    Validates first (fail emit on R3 / R10), then renders a control-flow-only harness:
    one ``agent()`` call per unit at its ``{model, effort}`` tier, dependency barriers
    rendered as ``await`` ordering, fan-out reconciliation + cheap-tier budget riders
    baked into prompts. The agents do the real work; this script is control flow only.

    ``unattended`` (#364 KTD3) is a run property, not spec state: attended emission (default)
    renders every escalate_on_signal refute as a throw-with-proposal ask gate; unattended
    emission renders the one-rung in-script climb retry instead. Attendance never enters the
    durable spec JSON.

    Returns the script source as a string (the caller writes it beside the plan and
    records the path as the saga ``orchestration_ref``).
    """
    spec.validate()

    # #365 U3: a session tier ceiling clamps every unit DOWN before rendering (the operator's live
    # cap is the final word and never raises a tier). Clamping the spec's units means spec.unit_by_id
    # -- which every render site below reads -- returns clamped tiers, so this is the one injection point.
    ceiling_notes: list[str] = []
    if session_ceiling is not None:
        clamped_units = []
        for _u in spec.units:
            _eff = clamp_tier_to_ceiling(_u.tier, session_ceiling)
            if _eff != _u.tier:
                ceiling_notes.append(
                    f"//   {_u.unit_id}: {_u.tier.model}/{_u.tier.effort}"
                    f" -> {_eff.model}/{_eff.effort}"
                )
            clamped_units.append(replace(_u, tier=_eff))
        spec = replace(spec, units=clamped_units)

    lines: list[str] = []
    lines.append("// ===========================================================================")
    lines.append(f"// {spec.name} -- emitted Claude Code workflow harness.")
    lines.append("// AUTO-EMITTED from a structured execution-spec by execution_spec.py.")
    lines.append("// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.")
    lines.append("// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +")
    lines.append("// R10 enumerated-target reconciliation enforced at emit time.")
    lines.append("// ===========================================================================")
    if ceiling_notes and session_ceiling is not None:
        lines.append(
            f"// SESSION TIER CEILING {session_ceiling.model}/{session_ceiling.effort}"
            f" applied (#365) -- clamped:"
        )
        lines.extend(ceiling_notes)
    lines.append("")
    lines.append("export const meta = {")
    lines.append(f"  name: {_js_string(spec.name)},")
    lines.append(f"  description: {_js_string(spec.description)},")
    lines.append("}")
    lines.append("")
    if spec.repo:
        lines.append(f"const REPO = {_js_string(spec.repo)}")
        lines.append("")

    # #364 R7/R8: workflow-level cord collector -- __gate pushes worker-initiated pull_cord
    # dispositions here; the single batched escalation check runs after every layer.
    lines.append("const __pulledCords = []")
    lines.append("")
    lines.append(_JS_GATE_HELPER)
    lines.append("")
    lines.append(_JS_RETRY_HELPER)
    lines.append("")

    # Topological waves (KTD4): each layer's units are mutually independent and run in a
    # single parallel() wave; layers are sequenced by await (the dependency barrier). A
    # singleton layer renders as a plain `const x = await agent(...)`. _js_var (module-level)
    # sanitizes the unit_id into the result var; validate() has already rejected any two ids
    # that would collide to the same identifier.
    _var = _js_var

    def _emit_unit_header(unit: Unit) -> None:
        lines.append(f"// ---- {unit.unit_id}: {unit.label} ----")
        if unit.depends_on:
            lines.append(f"// depends_on: {', '.join(unit.depends_on)} (barrier)")
        if unit.pilot:
            lines.append(f"// pilot: {unit.pilot} (R3 same-tier gate)")
        if unit.escalation:
            lines.append(f"// escalation: {unit.escalation}")

    for layer in dependency_layers(spec):
        layer_units = [spec.unit_by_id(uid) for uid in layer]
        if len(layer_units) == 1:
            unit = layer_units[0]
            assert unit is not None
            _emit_unit_header(unit)
            var = _var(unit.unit_id)
            if unit.verify is not None and unit.verify.iterate_to_consensus:
                _emit_verify_loop_singleton(lines, spec, unit, var, session_ceiling)
            else:
                prompt = _agent_prompt(spec, unit)
                opts = _agent_opts(unit)
                marker = _external_engine_marker(unit)
                if marker is not None:
                    lines.append(f"// external-engine dispatch: {marker}")
                # #364: an unattended escalate_on_signal retry reassigns the unit's var, so it
                # needs `let`; everything else keeps today's `const` (byte-stable emission).
                # `let` tracks ACTUAL reassignment: an at-top/ceiling-blocked unit emits no
                # retry branch, so its declaration stays const.
                decl = "let" if _emits_climb_retry(unit, unattended, session_ceiling) else "const"
                lines.append(f"{decl} {var} = await agent(")
                lines.append(f"  {_js_string(prompt)},")
                lines.append("  { " + ", ".join(opts) + " },")
                lines.append(")")
                lines.append(_emit_gate_call(unit, var, session_ceiling))
                lines.append("")
                if unit.verify is not None:
                    _emit_verify_panel(
                        lines,
                        spec,
                        unit,
                        var,
                        unattended=unattended,
                        session_ceiling=session_ceiling,
                    )
            continue

        # A layer of >1 ready unit -> one parallel() wave of thunks. The wave's results
        # are destructured back into the per-unit vars so dependents/verify panels read them.
        for unit in layer_units:
            assert unit is not None
            _emit_unit_header(unit)
        layer_vars = [_var(uid) for uid in layer]
        # #364: `let` destructure when any wave unit may reassign its var in an unattended climb.
        wave_decl = (
            "let"
            if any(
                u is not None and _emits_climb_retry(u, unattended, session_ceiling)
                for u in layer_units
            )
            else "const"
        )
        lines.append(f"{wave_decl} [{', '.join(layer_vars)}] = await parallel([")
        for unit in layer_units:
            assert unit is not None
            _emit_thunk(lines, spec, unit, session_ceiling)
        lines.append("])")
        for unit in layer_units:
            assert unit is not None
            lines.append(_emit_gate_call(unit, _var(unit.unit_id), session_ceiling))
        lines.append("")
        for unit in layer_units:
            assert unit is not None
            if unit.verify is not None and not unit.verify.iterate_to_consensus:
                _emit_verify_panel(
                    lines,
                    spec,
                    unit,
                    _var(unit.unit_id),
                    unattended=unattended,
                    session_ceiling=session_ceiling,
                )

    # #364 R8: pull-cord batch -- exactly ONE coordinator escalation entry, never one ask per
    # cord. Emitted after every layer so all cords collect before the single batched throw; a
    # cord unit is never marked complete because the run fails here before returning.
    lines.append("if (__pulledCords.length > 0) {")
    lines.append(
        "  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported "
        "out of depth -- ` +"
    )
    lines.append(
        "    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + "
        "(c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)'))"
        ".join('; ') +"
    )
    lines.append(
        "    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')"
    )
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Capability-portable inline/serial baseline (R11 / U12)
# ---------------------------------------------------------------------------
#
# Every authored plan carries a runnable inline/serial baseline so it executes on ANY
# host, with or without the Workflow tool. The dynamic-workflow layer (emit_workflow_script)
# applies only on a capable host; on an off-host resume the orchestration tier recompiles
# DOWN (lifecycle_state.recheck_orchestration_capability) and this baseline is what the
# inline floor runs. The recompile preserves every unit spec and its per-unit {model,
# effort} tier -- the baseline below annotates each unit with the SAME tier it carried in
# the dynamic script, so a downgrade changes only HOW units are dispatched (serial, inline)
# and never WHICH units run or AT WHAT tier.


def emit_inline_baseline(spec: ExecutionSpec) -> str:
    """Emit the runnable inline/serial baseline plan from the spec (R11 floor).

    Validates first (the same R3/R10 invariants -- a mis-built spec has no valid baseline
    either), then renders a deterministic, host-independent serial checklist: each unit in
    declared order, dependency barriers honored by ordering, the per-unit ``{model, effort}``
    tier PRESERVED on every unit (the recompile preserves tiers -- R11), fan-out targets
    enumerated inline (R10, never a silent filter). This is the always-runnable floor an
    off-host resume degrades to; it requires no Workflow tool.

    Returned as a Markdown checklist string (the inline executor reads it as its serial
    run order). It is NOT a .workflow.js -- by construction it dispatches nothing in
    parallel and calls no agent() harness.
    """
    spec.validate()

    lines: list[str] = []
    lines.append(f"# Inline/serial baseline -- {spec.name}")
    lines.append("")
    lines.append(
        "Runnable on ANY host (no Workflow tool required). The orchestration tier "
        "recompiled DOWN to inline; unit specs and per-unit {model, effort} tiers preserved."
    )
    if spec.description:
        lines.append("")
        lines.append(spec.description)
    if spec.repo:
        lines.append("")
        lines.append(f"Repo: {spec.repo}")
    lines.append("")
    lines.append("Run each unit IN ORDER (serial); honor the declared dependency barriers.")
    lines.append("")

    for idx, unit in enumerate(spec.units, start=1):
        tier = f"{unit.tier.model}/{unit.tier.effort}"
        lines.append(f"## {idx}. {unit.unit_id}: {unit.label}  [tier: {tier}]")
        if unit.depends_on:
            lines.append(f"- depends_on (run after): {', '.join(unit.depends_on)}")
        if unit.pilot:
            lines.append(f"- pilot (run first, same tier): {unit.pilot}")
        if unit.escalation:
            lines.append(f"- escalation: {unit.escalation}")
        if unit.fanout:
            lines.append(
                f"- fan-out over {len(unit.targets)} enumerated targets "
                f"(serial, reconcile after -- report any not completed): "
                f"{', '.join(unit.targets)}"
            )
        prompt = _agent_prompt(spec, unit)
        lines.append("")
        for prompt_line in prompt.splitlines():
            lines.append(f"  {prompt_line}" if prompt_line else "")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# The orchestration tiers, mirrored from lifecycle_state.ORCHESTRATION_TIERS, so the
# emitter can render the correct floor for a given (possibly downgraded) tier without a
# cross-module import at module scope (the scripts load standalone in tests).
_WORKFLOW_TIER = "cc-workflows-ultracode"
_TEAM_TIER = "team-execution"
_INLINE_TIER = "inline"


def _emit_team_structure(spec: ExecutionSpec) -> str:
    """Lazily load ``team_emitter`` and emit the team-execution ``## Team Structure`` markdown.

    Imported by path (not at module scope) so ``execution_spec`` stays importable standalone in
    tests and there is no import cycle with ``team_emitter`` (which lazily loads this module).
    """
    import importlib.util

    path = Path(__file__).parent / "team_emitter.py"
    loaded = importlib.util.spec_from_file_location("team_emitter", path)
    assert loaded is not None and loaded.loader is not None
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module.emit_team_structure(spec)  # type: ignore[no-any-return]


def recompile_for_tier(spec: ExecutionSpec, orchestration_mode: str) -> str:
    """Re-emit the spec for a (possibly downgraded) orchestration tier (R11 recompile).

    ONLY the orchestration tier changes -- every unit survives in every emitter. The inline and
    workflow emitters additionally render each unit's ``{model, effort}`` tier verbatim;
    ``team-execution`` re-emits the ``team_emitter`` ``## Team Structure`` markdown protocol (the R5
    third leg of the by-mode dispatcher seam), which renders the team roles/units but not the
    per-unit ``{model, effort}`` (the team-execution protocol selects models per its own roster).
    ``cc-workflows-ultracode`` re-emits the dynamic ``.workflow.js`` harness; ``inline`` or any
    unknown floor re-emits the inline/serial baseline, the always-runnable floor. This is the
    function an off-host resume calls after ``recheck_orchestration_capability`` decides the new
    tier: it never errors and always returns a runnable artifact (AE3).
    """
    spec.validate()
    if orchestration_mode == _WORKFLOW_TIER:
        return emit_workflow_script(spec)
    if orchestration_mode == _TEAM_TIER:
        return _emit_team_structure(spec)
    # The inline floor and any other/unknown tier emit the host-independent serial baseline --
    # never an empty or un-runnable artifact.
    return emit_inline_baseline(spec)


# ---------------------------------------------------------------------------
# Worker segment derivation (U1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    """One resident worker segment (U1).

    Carries the stable resident agent-id, the covered unit ids, the segment-level
    tier (upgrade-only max), and the collapsed segment-level dependencies. ``engine`` /
    ``capability`` / ``engine_intent`` are set only for a chaperone segment (KTD1/KTD3,
    U12) -- ``None`` for an ordinary Claude segment.
    """

    resident_id: str
    unit_ids: list[str]
    tier: Tier
    depends_on: list[str]
    engine: str | None = None
    capability: str | None = None
    engine_intent: str | None = None


def segment_units(spec: ExecutionSpec) -> list[Segment]:
    """Derive the worker segmentation from the execution spec without mutating it.

    Groups contiguous units sharing a plugin-directory boundary (KTD2), assigns
    a stable resident agent-id + monolithic upgrade-only tier per segment (R6),
    and collapses the unit-level dependencies into segment-level deps (KTD4).
    """
    if not spec.units:
        return []

    # 1. Group contiguous units by boundary key
    segments_data: list[tuple[str, list[Unit]]] = []
    current_key: str | None = None
    current_units: list[Unit] = []

    for unit in spec.units:
        if unit.engine is not None:
            # Chaperone segments never merge with a plain Claude segment or a
            # different engine/capability, regardless of file path (KTD1/KTD3, U12).
            # One resident chaperone per *contiguous run* of the same engine (not per
            # variant) -- "worker-agy", not "worker-agy/gemini-3.5-flash-high" (KTD1's
            # own naming example). Same as the plugin-directory grouping below, this is
            # contiguous-only: a non-contiguous re-appearance of the same engine (e.g.
            # interleaved with a Claude unit) opens a new resident ("worker-agy-2").
            key = f"engine:{unit.engine.split('/', 1)[0]}"
        elif unit.capability is not None:
            key = f"capability:{unit.capability}"
        elif not unit.files:
            key = ""
        else:
            first_file = unit.files[0]
            parts = [p for p in first_file.split("/") if p]
            if len(parts) >= 2 and parts[0] == "plugins":
                key = f"plugins/{parts[1]}"
            elif len(parts) >= 1:
                key = parts[0]
            else:
                key = ""

        if current_key is None:
            current_key = key
            current_units = [unit]
        elif key == current_key:
            current_units.append(unit)
        else:
            segments_data.append((current_key, current_units))
            current_key = key
            current_units = [unit]

    if current_units:
        assert current_key is not None
        segments_data.append((current_key, current_units))

    # 2. Assign resident_ids and map unit_id -> resident_id
    counts: dict[str, int] = {}
    unit_to_resident_id: dict[str, str] = {}
    temp_segments: list[dict[str, Any]] = []

    for key, units in segments_data:
        if key.startswith("engine:"):
            base_id = f"worker-{key[len('engine:') :]}"
        elif key.startswith("capability:"):
            base_id = f"worker-{key[len('capability:') :]}"
        else:
            base_dir = key[len("plugins/") :] if key.startswith("plugins/") else key
            base_id = f"worker-{base_dir}" if base_dir else "worker"

        count = counts.get(base_id, 0) + 1
        counts[base_id] = count

        resident_id = base_id if count == 1 else f"{base_id}-{count}"

        for u in units:
            unit_to_resident_id[u.unit_id] = resident_id

        temp_segments.append(
            {
                "resident_id": resident_id,
                "units": units,
            }
        )

    # 3. Build Segment objects
    result: list[Segment] = []
    for seg in temp_segments:
        resident_id = seg["resident_id"]
        units = seg["units"]
        unit_ids = [u.unit_id for u in units]

        # Calculate max tier: upgrade-only merge of its members' tiers via the named
        # ladder op (#370 U2) — never inline MODELS.index()/EFFORTS.index() arithmetic,
        # which silently mis-tiers if the two opposite-direction tuples are confused.
        seg_tier = Tier(
            model=_tier_palette.strongest("model", (u.tier.model for u in units)),
            effort=_tier_palette.strongest("effort", (u.tier.effort for u in units)),
        )

        # #369 U2: a member unit's declared floor (min_tier) pulls the merged segment tier UP -- never
        # a silent downgrade. A segment collapses to ONE resident spawn, so any member's floor governs
        # the whole segment. Fold each floor in with the SAME ladder op the base merge uses
        # ({#tier-vocab-ordering}: reason in strength, never raw index), so a cheap unit sharing a
        # segment with a floored one resolves to at least the floor.
        floors = [u.min_tier for u in units if u.min_tier is not None]
        if floors:
            seg_tier = Tier(
                model=_tier_palette.strongest(
                    "model", [seg_tier.model, *(f.model for f in floors)]
                ),
                effort=_tier_palette.strongest(
                    "effort", [seg_tier.effort, *(f.effort for f in floors)]
                ),
            )

        # Resolve engine_intent the same way: upgrade-only max ("second-opinion" beats
        # "offload") when a same-engine segment's members disagree, rather than silently
        # taking the first unit's value (KTD1/U12 -- a chaperone is one resident worker, so
        # the more conservative intent should govern its tier recommendation).
        seg_intents = [u.engine_intent for u in units if u.engine_intent is not None]
        seg_engine_intent = (
            ENGINE_INTENTS[max(ENGINE_INTENTS.index(i) for i in seg_intents)]
            if seg_intents
            else None
        )

        # Collapse depends_on graph
        seg_deps: list[str] = []
        for u in units:
            for dep_unit in u.depends_on:
                dep_resident_id = unit_to_resident_id.get(dep_unit)
                if (
                    dep_resident_id
                    and dep_resident_id != resident_id
                    and dep_resident_id not in seg_deps
                ):
                    seg_deps.append(dep_resident_id)

        result.append(
            Segment(
                resident_id=resident_id,
                unit_ids=unit_ids,
                tier=seg_tier,
                depends_on=seg_deps,
                engine=units[0].engine.split("/", 1)[0] if units[0].engine is not None else None,
                capability=units[0].capability,
                engine_intent=seg_engine_intent,
            )
        )

    return result


# ---------------------------------------------------------------------------
# CLI -- validate or emit from a JSON spec file (offline-deterministic)
# ---------------------------------------------------------------------------


def _load_spec(path: Path) -> ExecutionSpec:
    return ExecutionSpec.from_dict(json.loads(path.read_text()))


def _read_session_ceiling(root: Path | None = None) -> Tier | None:
    """Read the #365 session-override ceiling, or None when absent.

    Lazy import keeps this module's "no I/O at import" property intact.
    """
    import tier_session

    ceiling = tier_session.read_session_override(root).get("ceiling")
    if ceiling is None:
        return None
    return Tier(model=str(ceiling["model"]), effort=str(ceiling["effort"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execution-spec validator + workflow emitter.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="validate a spec JSON (R3/R10 invariants)")
    p_val.add_argument("spec", type=Path)
    p_val.add_argument(
        "--require-receipts",
        action="store_true",
        help="also enforce the #367 premium-tier worth-it hard-block (the /plan authoring gate)",
    )

    p_emit = sub.add_parser("emit", help="emit a workflow script from a spec JSON")
    p_emit.add_argument("spec", type=Path)
    p_emit.add_argument("-o", "--out", type=Path, help="write the script here (default: stdout)")
    p_emit.add_argument(
        "--unattended",
        action="store_true",
        help="operator is away (#364 KTD3): escalate_on_signal refutes climb one rung "
        "in-script instead of throwing the attended ask-gate proposal",
    )

    p_base = sub.add_parser(
        "baseline", help="emit the runnable inline/serial baseline (R11 floor) from a spec JSON"
    )
    p_base.add_argument("spec", type=Path)
    p_base.add_argument("-o", "--out", type=Path, help="write the baseline here (default: stdout)")

    p_patch = sub.add_parser(
        "patch",
        help="apply session-override unit tiers to NOT-yet-run units, then re-validate (#365)",
    )
    p_patch.add_argument("spec", type=Path)
    p_patch.add_argument(
        "--already-run", default="", help="comma-separated unit ids already run (never patched)"
    )
    p_patch.add_argument(
        "-o", "--out", type=Path, help="write the patched spec here (default: stdout)"
    )

    p_spend = sub.add_parser(
        "spend",
        help="report per-unit spend, total, cost_budget headroom, and spend_envelope (#366)",
    )
    p_spend.add_argument("spec", type=Path)

    args = parser.parse_args(argv)
    try:
        spec = _load_spec(args.spec)
        if args.cmd == "validate":
            spec.validate(require_receipts=bool(getattr(args, "require_receipts", False)))
            print(f"OK: {spec.name} ({len(spec.units)} units) is a valid execution-spec.")
            return 0
        if args.cmd == "patch":
            import tier_session

            overrides = {
                uid: Tier(model=str(t["model"]), effort=str(t["effort"]))
                for uid, t in tier_session.read_session_override().get("unit_overrides", {}).items()
            }
            already = [x for x in args.already_run.split(",") if x]
            run = set(already)
            # R6: surface up-ladder escalations so the /tier command can gate them (the CLI cannot
            # prompt); a cheapen/lateral move is silent.
            escalations = [
                u.unit_id
                for u in spec.units
                if u.unit_id in overrides
                and u.unit_id not in run
                and is_escalation(u.tier, overrides[u.unit_id])
            ]
            patched = patch_spec_tiers(spec, overrides, already)
            patched.validate()  # R5 hard gate: never emit an invalid spec
            if escalations:
                print(
                    f"NOTE: up-ladder escalation(s) need operator confirmation: {escalations}",
                    file=sys.stderr,
                )
            out_json = json.dumps(patched.to_dict(), indent=2)
            if args.out:
                args.out.write_text(out_json + "\n")
                print(f"wrote {args.out}")
            else:
                print(out_json)
            return 0
        if args.cmd == "spend":
            # Report the priced plan for /plan to surface (R6). Deliberately does NOT run
            # validate() -- it reports even an over-budget spec (showing the overage) rather
            # than HALTing, so the operator sees the numbers before deciding.
            total = spec.spec_spend()
            print(f"spend report: {spec.name} ({len(spec.units)} units)")
            for u in spec.units:
                extras: list[str] = []
                if u.fanout and u.targets:
                    extras.append(f"x{len(u.targets)} targets")
                if u.verify is not None:
                    extras.append(f"verify n={u.verify.n}")
                suffix = f" ({', '.join(extras)})" if extras else ""
                print(f"  {u.unit_id}  {u.tier.model}/{u.tier.effort}{suffix} = {unit_spend(u)}")
            print(f"total spend: {total}")
            if spec.cost_budget is not None:
                delta = spec.cost_budget - total
                headroom = f"headroom {delta}" if delta >= 0 else f"OVER by {-delta}"
                print(f"cost_budget: {spec.cost_budget}  ({headroom})")
            else:
                print("cost_budget: unset")
            print(
                f"spend_envelope: {spec.spend_envelope}"
                if spec.spend_envelope is not None
                else "spend_envelope: unset"
            )
            return 0
        if args.cmd == "baseline":
            script = emit_inline_baseline(spec)
        else:
            script = emit_workflow_script(
                spec,
                session_ceiling=_read_session_ceiling(),
                unattended=bool(getattr(args, "unattended", False)),
            )
    except (SpecError, _cost_weights.CostWeightsError) as exc:
        print(f"SPEC ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.write_text(script)
        print(f"wrote {args.out}")
    else:
        print(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
