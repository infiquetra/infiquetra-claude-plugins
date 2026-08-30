#!/usr/bin/env python3
"""The Claude Code Workflow script emitter — extracted from Saga (#925, U4).

Owns the workflow-script emission path (``emit_workflow_script``), the driver-owned
settlement/lease metadata builders, and the #708 agent-opts guards, at the typed
spec-contract boundary: the spec schema, validation, tier resolution, and the shared
emission substrate stay in Saga's ``execution_spec.py``; this module loads that module
(never a copy) and emits the runnable ``.workflow.js`` from it. Saga's
``execution_spec.py`` delegates its ``emit`` / ``settlement`` / ``lease`` surfaces back
here — the seam is the spec shape, so the two sides can never disagree about it.

The backend stays runnable and explicit-invocation-only (issue #808 NARROW, #840 C5):
nothing here selects the backend — it only emits when the operator's explicit choice
reaches it. Pure functions; no I/O at import (house pattern).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import saga_spec_shim  # noqa: E402  (after the sys.path shim, by design)

# The spec schema and shared emission substrate, loaded from Saga (never copied). The
# shim reuses ``sys.modules["execution_spec"]`` when present, so a host process that
# already loaded the module shares one instance with this emitter.
_ES = saga_spec_shim.load_execution_spec()

import concurrency_governor  # noqa: E402  (saga sibling; on sys.path once the substrate loaded)

# --- substrate bindings (single source of truth — never redefined here).
# Assigned through ``_bind_substrate`` so the delegation on the Saga side can re-bind
# this module to ITS OWN execution_spec instance: several instances coexist in one
# process (test suites each load their own), and ``sys.modules`` names only one winner.
# Names tests monkeypatch on execution_spec stay qualified ``_ES.<name>`` at their call
# sites below, so the patch on the owning instance is always the value emitted against. ---
SpecError = Tier = Unit = ExecutionSpec = None  # type: ignore[assignment]
_js_var = _unit_script_symbols = escalate_tier = None
assert_no_wave_file_conflicts = dependency_layers = wave_file_conflicts = None
clamp_tier_to_ceiling = _effective_verify_tier = _verify_panel_admission_unit = None
_concurrency_policy = EmissionRoutingContext = UnitRouting = None
resolved_concurrency = concurrency_chunks = max_concurrent_agents = None
_build_emission_routing_context = _load_emission_registry = _ROUTING_SNAPSHOT_UNSET = None
_WORKFLOW_RESERVED_IDENTIFIERS = _WORKFLOW_ITERATE_LOCAL_IDENTIFIERS = None
VERIFY_N_CAP = VERIFY_N_WARN = BUDGET_RIDER = PRESENTATION_RIDER = _WORKFLOW_TIER = None


def _bind_substrate(es: ModuleType) -> None:
    """Bind (or re-bind) the substrate names to one execution_spec instance."""
    global _ES
    global SpecError, Tier, Unit, ExecutionSpec
    global _js_var, _unit_script_symbols, escalate_tier
    global assert_no_wave_file_conflicts, dependency_layers, wave_file_conflicts
    global clamp_tier_to_ceiling, _effective_verify_tier, _verify_panel_admission_unit
    global _concurrency_policy, EmissionRoutingContext, UnitRouting
    global resolved_concurrency, concurrency_chunks, max_concurrent_agents
    global _build_emission_routing_context, _load_emission_registry, _ROUTING_SNAPSHOT_UNSET
    global _WORKFLOW_RESERVED_IDENTIFIERS, _WORKFLOW_ITERATE_LOCAL_IDENTIFIERS
    global VERIFY_N_CAP, VERIFY_N_WARN, BUDGET_RIDER, PRESENTATION_RIDER, _WORKFLOW_TIER
    _ES = es
    SpecError = es.SpecError
    Tier = es.Tier
    Unit = es.Unit
    ExecutionSpec = es.ExecutionSpec
    _js_var = es._js_var
    _unit_script_symbols = es._unit_script_symbols
    escalate_tier = es.escalate_tier
    assert_no_wave_file_conflicts = es.assert_no_wave_file_conflicts
    dependency_layers = es.dependency_layers
    wave_file_conflicts = es.wave_file_conflicts
    clamp_tier_to_ceiling = es.clamp_tier_to_ceiling
    _effective_verify_tier = es._effective_verify_tier
    _verify_panel_admission_unit = es._verify_panel_admission_unit
    _concurrency_policy = es._concurrency_policy
    EmissionRoutingContext = es.EmissionRoutingContext
    UnitRouting = es.UnitRouting
    resolved_concurrency = es.resolved_concurrency
    concurrency_chunks = es.concurrency_chunks
    max_concurrent_agents = es.max_concurrent_agents
    _build_emission_routing_context = es._build_emission_routing_context
    _load_emission_registry = es._load_emission_registry
    _ROUTING_SNAPSHOT_UNSET = es._ROUTING_SNAPSHOT_UNSET
    _WORKFLOW_RESERVED_IDENTIFIERS = es._WORKFLOW_RESERVED_IDENTIFIERS
    _WORKFLOW_ITERATE_LOCAL_IDENTIFIERS = es._WORKFLOW_ITERATE_LOCAL_IDENTIFIERS
    VERIFY_N_CAP = es.VERIFY_N_CAP
    VERIFY_N_WARN = es.VERIFY_N_WARN
    BUDGET_RIDER = es.BUDGET_RIDER
    PRESENTATION_RIDER = es.PRESENTATION_RIDER
    _WORKFLOW_TIER = es._WORKFLOW_TIER


_bind_substrate(_ES)

# Claude Code Workflows agent() keys the runtime actually honors. dispatch/engine/
# verifiability are authored on external-engine units but the runtime ignores them;
# emitting them would silently run a native Claude subagent (#708).
WORKFLOW_HONORED_AGENT_OPT_KEYS = frozenset(
    {"label", "model", "effort", "schema", "agentType", "isolation"}
)

# The restricted agent type + isolation every verifier is spawned with (#287 U2, R5/KTD6). The
# ``agentType`` string MUST equal plugins/saga/agents/readonly-verifier.md's ``name:`` frontmatter
# plus the ``saga:`` plugin prefix; the literal-consistency guard test asserts this, so a rename on
# either side fails a test rather than silently spawning verifiers unrestricted (the R9 dead-wiring
# failure). ``isolation: 'worktree'`` is the load-bearing clobber defense (R3): a Bash
# ``git checkout`` needs no Edit/Write tool, so only a throwaway worktree can contain it.
READONLY_VERIFIER_AGENT_TYPE = "saga:readonly-verifier"
READONLY_VERIFIER_ISOLATION = "worktree"

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
    throw __halt(
      `missing-output: Unit ${unitId} expected structured output but received none or empty.`,
      unitId
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
        throw __halt(
          `malformed-output: Unit ${unitId} output is a structurally truncated JSON: ${e.message}`,
          unitId
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
      throw __halt(
        `missing-output: Unit ${unitId} produced fewer items than expected. ` +
        `Expected ${targetCount}, produced ${producedCount}. Shortfall: ${shortfall}.`,
        unitId
      );
    }
  }

  if (opts.returns && opts.returns.length > 0) {
    const parsed = parseResult(result);
    if (parsed === null || parsed === undefined || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw __halt(
        `missing-output: Unit ${unitId} result is not a structured dictionary. ` +
        `Missing required keys: ${opts.returns.join(', ')}.`,
        unitId
      );
    }
    const missing = opts.returns.filter(
      k => !(k in parsed) || parsed[k] === null || parsed[k] === undefined
    );
    if (missing.length > 0) {
      throw __halt(
        `missing-output: Unit ${unitId} output is missing required keys: ${missing.join(', ')}.`,
        unitId
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

# #686 R4 / plan KTD3: the workflow-level NON-GATING correction accumulator. Structurally the
# twin of `__pulledCords` -- one module-level global, one registration site in
# _WORKFLOW_RESERVED_IDENTIFIERS, no per-panel-shape asymmetry (a per-unit binding would need
# registering in BOTH _WORKFLOW_ITERATE_LOCAL_IDENTIFIERS and _unit_reserved_symbols' suffixes,
# each covering only one panel shape). `__logAdvisory` both LOGS during the run and accumulates
# for the final return, which is R4's "reach the driving session" in its two required halves.
_JS_ADVISORY_HELPER = r"""const __advisories = []
const __advisoryRounds = new Map()
const __ADVISORY_ITEM_CAP = 50
const __ADVISORY_ITEM_CHARS = 180
function __renderAdvisory(a) {
  var s
  try {
    if (a === null || a === undefined) s = "(empty advisory entry)"
    else if (typeof a === "string") s = a
    else s = String(a.claim || a.id || JSON.stringify(a))
  } catch (e) {
    s = "(unrenderable advisory entry)"
  }
  // Two passes over two distinct hazards. First: C0, DEL, C1 (NEL included) and the
  // line/paragraph separators -- these forge a second log line. Second: the bidi marks,
  // embeddings, overrides and isolates plus the BOM -- these leave the byte sequence intact
  // but reorder what a human READS in a terminal or log viewer (the Trojan-Source pattern).
  // Advisory text is model-authored by a verifier that read a diff it did not write, so both
  // classes are reachable from repo content.
  var t = s
    .replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]+/g, " ")
    .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]+/g, " ")
    .slice(0, __ADVISORY_ITEM_CHARS)
  // .slice() cuts on UTF-16 code units, so an astral character (any emoji) straddling the cap
  // leaves a lone high surrogate behind. This string is now STORED and returned, not just
  // logged, so ill-formed UTF-16 would cross the harness return boundary -- a consumer that
  // re-encodes it substitutes U+FFFD or raises. Drop the orphan half.
  var tail = t.charCodeAt(t.length - 1)
  if (tail >= 0xd800 && tail <= 0xdbff) t = t.slice(0, -1)
  return t
}
// #691: attach the HALTING unit's advisories, not the run-wide accumulator -- a driver that
// reads this off a halt would otherwise act on advice about units that already settled. Two
// callers, two contracts: pass a REAL unit id for a unit-scoped throw, or omit it entirely for
// the run-level pull-cord batch, which names every unit that pulled a cord and so must stay
// run-wide. Do NOT "complete" this by threading a unit id into that batched throw -- it would
// silently drop every cord-pulling unit's advisories but one, and no test covers it. Omitted is
// the only supported way to ask for the whole list: any truthy non-unit string (`__gate`'s
// `opts.unitId || "unknown"` default) filters to an empty array instead of falling back.
function __halt(message, unitId) {
  var e = new Error(message)
  e.advisory_corrections = unitId
    ? __advisories.filter(function(a) { return a.unit === unitId })
    : __advisories
  return e
}
function __logAdvisory(unitId, reported, refuted) {
  // Counted on EVERY call, before the empty-items early return below -- a panel round that
  // produced no advisories is still a round. Deriving the ordinal from stored entries instead
  // would silently renumber: an iterate_to_consensus unit whose first round was clean would
  // label its second round "round 1", and a driver told to read the last entry would act on
  // advice about a discarded intermediate result. A Map, not an object, so a unit id like
  // `constructor` cannot collide with a prototype member.
  var round = (__advisoryRounds.get(unitId) || 0) + 1
  __advisoryRounds.set(unitId, round)
  var items = []
  try {
    for (var i = 0; i < reported.length; i++) {
      var adv = Array.isArray(reported[i].advisory_corrections) ? reported[i].advisory_corrections : []
      for (var j = 0; j < adv.length; j++) items.push(__renderAdvisory(adv[j]))
    }
  } catch (e) {
    // Through __renderAdvisory, not around it: this marker embeds a model-reachable
    // message and is the one path that would otherwise reach log() unscrubbed.
    items.push(__renderAdvisory("(advisory harvest failed: " + String(e && e.message) + ")"))
  }
  if (items.length === 0) return items
  var dropped = 0
  if (items.length > __ADVISORY_ITEM_CAP) {
    dropped = items.length - __ADVISORY_ITEM_CAP
    items = items.slice(0, __ADVISORY_ITEM_CAP)
  }
  __advisories.push({ unit: unitId, round: round, corrections: items, dropped: dropped })
  try {
    log(`verify panel over ${unitId} (round ${round}): deliverable ${refuted ? "REFUTED" : "UPHELD"} with ${items.length + dropped} advisory correction(s) (narrative/rationale only, non-gating): ` +
        items.join(" | ") + (dropped > 0 ? ` [+${dropped} suppressed]` : ""))
  } catch (e) {
    /* the non-gating accumulator must never be able to halt a run */
  }
  return items
}"""

_JS_VERIFIER_PROMPT_HELPER = r"""function __verifierPrompt(basePrompt, unitResult, passRule) {
  var gatingBar = (passRule === "unanimous")
    ? "EVERY reporting verifier"
    : "a majority of the panel";
  var rendered;
  try {
    rendered = JSON.stringify(unitResult, null, 2);
  } catch (err) {
    rendered = String(unitResult);
  }
  var repoLine = (typeof REPO === "string")
    ? `PRIMARY REPO PATH: ${REPO}`
    : "PRIMARY REPO PATH: not declared by this workflow";
  return `${basePrompt}

VERIFIER VISIBILITY PROTOCOL (#519):
${repoLine}
- You run in a disposable verifier worktree. Before judging file content, capture the primary
  checkout SHA with: git -C <primary repo path> rev-parse HEAD
- Materialize that exact SHA in your verifier worktree with: git checkout <sha> -- .
- If the unit result names uncommitted files or diffs, inspect the primary checkout read-only
  with git -C <primary repo path> status --short and git -C <primary repo path> diff / diff --
  <path>. For named untracked output files, read the primary checkout path directly; never mutate
  the primary checkout.
- Return examined_sha as the SHA you actually materialized or inspected. If you cannot see enough
  evidence to judge, return a refuted_deliverable entry explaining the visibility gap; do not emit
  prose-only "nothing to verify" output.

VERDICT CONTRACT — two separate buckets. Read this before you write anything.

The unit result you are given contains BOTH a deliverable and a narrative. Sort every disagreement
you find into exactly one of these. Getting the bucket right matters more than finding a lot.

\`refuted_deliverable\` — GATING. A finding belongs here only if the unit's actual WORK is wrong:
- A changed file is wrong, incomplete, or breaks something.
- Required behavior is missing, or behavior the unit was told to preserve was destroyed.
- A test is missing, wrong, asserts nothing, or does not test what it claims.
- A claim in \`checks_run\` is FALSE — the command does not actually pass, or was not actually run,
  or its reported result does not reproduce. Re-run the commands and check.
- The unit says \`status: "done"\` but the work is not done.
- You could not see enough to judge (visibility gap).
A non-empty \`refuted_deliverable\` from ${gatingBar} KILLS the unit and HALTS the whole
workflow. Put a finding here only if you would defend stopping the run over it.

\`advisory_corrections\` — NON-GATING. A finding belongs here if the WORK is right but the unit's
own account of it is wrong or misleading:
- Its explanation of WHY something happened is factually incorrect.
- It misattributes a change to the wrong function, file, or line.
- It mischaracterizes a mechanism, or states a rationale that does not hold.
- Its advice to a downstream unit rests on a wrong premise.
These are recorded and handed to the driver. They do NOT stop the run. Report them fully and
precisely — a wrong premise passed downstream causes real damage later, so this bucket is
genuinely valuable, not a consolation prize.

The test: if the unit's code, tests, and check results are all sound, then NOTHING goes in
\`refuted_deliverable\`, no matter how wrong its prose is. Prose errors are advisory. Full stop.

Both keys are REQUIRED and must be arrays. Use \`[]\` for an empty bucket — never omit either one.

UNIT RESULT INPUT (structured evidence — the \`notes\` field is the unit's NARRATIVE, judge it
under \`advisory_corrections\`; the changed files, tests, and \`checks_run\` are the DELIVERABLE):
${rendered}`;
}"""


def _workflow_agent_opt_key(opt: str) -> str:
    return opt.split(":", 1)[0].strip()


def _reject_unhonored_workflow_agent_opts(where: str, opts: Sequence[str]) -> None:
    """Fail emit if any agent() opt key is not honored by the cc-workflows runtime (#708)."""
    unhonored = [
        key
        for key in (_workflow_agent_opt_key(opt) for opt in opts)
        if key not in WORKFLOW_HONORED_AGENT_OPT_KEYS
    ]
    if not unhonored:
        return
    named = ", ".join(dict.fromkeys(unhonored))
    raise SpecError(
        f"{where}: agent() opts key {unhonored[0]!r} is not honored by the "
        f"cc-workflows runtime (unhonored: {named}); route cross-vendor work through "
        f"Herdr/Orchestrate sessions instead (#708 -- fail-loud, never silent native "
        f"fallback)"
    )


def _unsupported_engine_unit_error(unit: Unit) -> SpecError:
    if unit.engine is not None:
        selector = f"engine={unit.engine!r}"
    elif unit.capability is not None:
        selector = f"capability={unit.capability!r}"
    else:
        selector = "external-engine dispatch"
    return SpecError(
        f"unit {unit.unit_id}: {selector} is an external-engine unit; "
        f"the cc-workflows runtime cannot dispatch it. Route this unit through "
        f"a Herdr/Orchestrate session instead (#708 -- fail-loud, never silent "
        f"native fallback)"
    )


def _reject_unsupported_engine_units(spec: ExecutionSpec) -> None:
    """Reject a cc-workflows emit of any unit carrying engine or capability (#708)."""
    for unit in spec.units:
        if unit.engine is not None or unit.capability is not None:
            raise _unsupported_engine_unit_error(unit)


def _js_string(value: str) -> str:
    """Encode a Python string as a single-quoted JS string literal.

    ``json.dumps`` gives a valid JS string (double-quoted, escaped); we keep that --
    it is the safest encoder for arbitrary prompt text.
    """
    return json.dumps(value)


def _js_comment_text(value: str) -> str:
    """Render untrusted text inert inside one generated JavaScript line comment."""

    return (
        value.replace("\r", r"\r")
        .replace("\n", r"\n")
        .replace("\u2028", r"\u2028")
        .replace("\u2029", r"\u2029")
        .replace("${", r"\${")
        .replace("`", r"\`")
        .replace("*/", "* /")
    )


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


def _external_engine_marker(unit: Unit, route: UnitRouting) -> str | None:
    if route.exact_engine is None:
        return None
    raise SpecError(
        f"unit {unit.unit_id}: external-engine dispatch is not honored by the "
        f"cc-workflows runtime; route this unit through a Herdr/Orchestrate "
        f"session instead (#708 -- fail-loud, never silent native fallback)"
    )


def _return_schema(unit: Unit) -> dict[str, object]:
    """Build the StructuredOutput JSON Schema for a unit's declared returns (#503)."""
    return_schema: dict[str, object] = {
        "type": "object",
        "properties": {key: {} for key in unit.returns},
        "required": list(unit.returns),
        "additionalProperties": True,
    }
    if not unit.tier.is_cheap:
        return return_schema
    # #364: cheap-tier units may answer with {"pull_cord": "<reason>"} instead of their declared
    # returns. The Anthropic API rejects a tool input_schema with ANY top-level combinator -- not
    # just a bare {"oneOf": [...]} (which first trips 400 input_schema.type: Field required), but
    # also a fully typed {"type": "object", ..., "oneOf": [...]} (400 input_schema: input_schema
    # does not support oneOf, allOf, or anyOf at the top level -- verified 2026-07-10 on team-norns
    # run wf_758c9923-c2c). So the schema must be a FLAT typed object: the union of the declared
    # returns keys plus an optional pull_cord string, with no required alternation. The either/or
    # (returns keys XOR pull_cord) is enforced downstream by the emitted __gate (which probes
    # pull_cord first, then checks emptiness) and by the unit prompt's RETURN CONTRACT, so the
    # schema does not need to encode it. pull_cord is a reserved key (validate() rejects it in
    # returns), so the property union cannot collide.
    properties: dict[str, object] = {key: {} for key in unit.returns}
    properties["pull_cord"] = {"type": "string"}
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }


def _agent_opts(unit: Unit, route: UnitRouting) -> list[str]:
    if route.exact_engine is not None or unit.engine is not None or unit.capability is not None:
        keys = ["dispatch", "engine"]
        if unit.verifiability is not None:
            keys.append("verifiability")
        named = ", ".join(keys)
        raise SpecError(
            f"unit {unit.unit_id}: agent() opts key {keys[0]!r} is not honored by the "
            f"cc-workflows runtime (unhonored: {named}); route cross-vendor work through "
            f"Herdr/Orchestrate sessions instead (#708 -- fail-loud, never silent native "
            f"fallback)"
        )
    opts = [
        f"label: {_js_string(unit.label)}",
        f"model: {_js_string(unit.tier.model)}",
        f"effort: {_js_string(unit.tier.effort)}",
    ]
    if unit.returns:
        opts.append(f"schema: {json.dumps(_return_schema(unit), sort_keys=True)}")
    _reject_unhonored_workflow_agent_opts(f"unit {unit.unit_id}", opts)
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
        f"concrete reason) or UPHELD, and sort every refutation into the gating bucket or the "
        f"advisory bucket per the VERDICT CONTRACT below. Emit a structured verdict "
        f"{{refuted_deliverable: [...], advisory_corrections: [...], upheld: [...], "
        f"verifier_identity: ..., fallback_depth: ..., examined_sha: ...}}.",
        # U6/R8/KTD7: attributed verify-spawn. The emitter STAMPS the agent identity it knows
        # ({READONLY_VERIFIER_AGENT_TYPE}) and a fallback_depth of 0 -- a workflow agent() call
        # cannot silently descend the #325 fallback ladder (an unresolvable agentType fails the
        # call outright), so the first-choice rung is the only rung reachable from here. Echo BOTH
        # verbatim in your verdict so the panel gate summary can attribute any degraded reporter.
        f"Echo verifier_identity: {READONLY_VERIFIER_AGENT_TYPE} and fallback_depth: 0 "
        f"back in your verdict (do NOT alter them). Include examined_sha as the git SHA you "
        f"actually materialized or inspected.",
    ]
    if unit.tier.is_cheap:
        parts.append(BUDGET_RIDER)
    return "\n\n".join(parts)


def render_fallback_tier_marker(reporters: list[dict[str, object]]) -> str:
    """Pure render of the panel gate-summary 'fallback tier N' marker (U6/R8/KTD7).

    ``reporters`` is the list of reporting verifier verdicts, each carrying ``verifier_identity``
    and ``fallback_depth`` (default 0). Returns an explicit ``" - fallback tier N (<identity>)"``
    marker naming ONLY the degraded reporters (``fallback_depth > 0``), or ``""`` when every
    reporter sat on the first-choice ``saga:readonly-verifier`` rung (all depth 0). Kept a pure
    function -- no workflow emission, no I/O -- so the marker formatting is unit-testable in
    isolation. The #325 ladder itself is untouched by this: attribution only, never a reorder.
    """
    fragments: list[str] = []
    for reporter in reporters:
        raw_depth = reporter.get("fallback_depth", 0)
        if isinstance(raw_depth, bool) or not isinstance(raw_depth, (int, float, str)):
            depth = 0
        else:
            try:
                depth = int(raw_depth)
            except (TypeError, ValueError):
                depth = 0
        if depth <= 0:
            continue
        identity = reporter.get("verifier_identity") or "unknown-verifier"
        fragments.append(f"fallback tier {depth} ({identity})")
    if not fragments:
        return ""
    return " — " + "; ".join(fragments)


def _verifier_agent_opts(unit: Unit) -> list[str]:
    """Build the agent() opts for one verifier call in ``unit``'s refute-N panel (#287 U2).

    Single source of truth for all three verifier-emitting sites (``_emit_thunk``,
    ``_emit_verify_loop_singleton``, ``_emit_verify_panel``) so the enforcement opts cannot drift
    across them -- three hand-maintained copies is exactly the R9 dead-wiring risk. Every verifier
    is spawned read-only-verify UNCONDITIONALLY (KTD6): the restricted ``agentType`` omits
    Edit/Write (mutation_policy: read-only) and ``isolation: 'worktree'`` runs it in a throwaway
    worktree (workspace_isolation: disposable-worktree), so a verifier's Bash ``git checkout``
    cannot clobber the primary tree. No opt-out -- a verifier that needs write access is a design
    smell, and an opt-out would be an escalation channel contradicting R8. The panel runs at its
    EFFECTIVE tier -- the panel's own ``verify.tier`` when authored, else the unit tier (#565
    KTD5, R4 default) -- so an opus/high refute-3 request over a sonnet/medium unit runs the
    verifiers at opus/high without forcing the unit itself up.
    """
    tier = _effective_verify_tier(unit)
    opts = [
        f"label: {_js_string(unit.label + ' verifier')}",
        f"model: {_js_string(tier.model)}",
        f"effort: {_js_string(tier.effort)}",
        f"agentType: {_js_string(READONLY_VERIFIER_AGENT_TYPE)}",
        f"isolation: {_js_string(READONLY_VERIFIER_ISOLATION)}",
    ]
    opts.append(f"schema: {json.dumps(_verifier_schema(), sort_keys=True)}")
    _reject_unhonored_workflow_agent_opts(f"unit {unit.unit_id} verifier", opts)
    return opts


def _verifier_schema() -> dict[str, object]:
    """StructuredOutput schema for refute-N verifier verdicts (#519/#527).

    Attached to EVERY verify-panel ``agent()`` call (all panel forms route through
    ``_emit_panel_reconciliation`` -> ``_verifier_agent_opts``) so a prose/markdown verdict is
    retried/failed at the tool boundary instead of parse-and-hoped (#527: workflow
    wf_ada4ca97-365 aggregated over 0 reporters because verifiers returned prose). The
    constraints mirror the emitted ``<var>_valid_verifier_verdict`` runtime predicate exactly --
    ``minLength: 1`` on the #390 U6 attribution strings matches the predicate's
    ``.length > 0`` checks, so any verdict the schema admits is counted as a reporter. Flat
    typed object only: the API rejects top-level combinators (see ``_return_schema``).

    #686 severity axis: the single ``refuted`` bucket is RENAMED to ``refuted_deliverable``
    (gating) and joined by ``advisory_corrections`` (non-gating). Both are required arrays --
    hard cutover, no legacy-``refuted`` shim (plan KTD2): a tolerant reader would map a legacy
    prose refutation onto the gating bucket and reintroduce the exact bug being fixed.
    """
    return {
        "type": "object",
        "properties": {
            "refuted_deliverable": {"type": "array"},
            "advisory_corrections": {"type": "array"},
            "upheld": {"type": "array"},
            "verifier_identity": {"type": "string", "minLength": 1},
            "fallback_depth": {},
            "examined_sha": {"type": "string", "minLength": 1},
        },
        "required": [
            "refuted_deliverable",
            "advisory_corrections",
            "upheld",
            "verifier_identity",
            "fallback_depth",
            "examined_sha",
        ],
        "additionalProperties": True,
    }


def _emit_parallel_wave[T](
    lines: list[str],
    *,
    binding: str,
    bounded_members: Sequence[T],
    render_member: Callable[[T], None],
    indent: str = "",
) -> None:
    """Emit one bounded ``parallel`` wave over a stable member snapshot."""
    member_snapshot = tuple(bounded_members)
    lines.append(f"{indent}{binding} = await parallel([")
    for member in member_snapshot:
        render_member(member)
    lines.append(f"{indent}])")


def _emit_panel_reconciliation(
    lines: list[str],
    unit: Unit,
    result_var: str,
    name_prefix: str,
    indent: str,
    *,
    max_concurrent: int,
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
    # Quorum floor, baked as a literal per panel (plan KTD3). STRICT majority of the DECLARED
    # panel size -- `n // 2 + 1`, not `ceil(n / 2)`. At even n those differ by one, and the
    # emit-time floor is compared against a runtime majority threshold recomputed over the
    # SURVIVING reporters (`ceil(k / 2)`). With `ceil(n / 2)` the two disagree at even n, so a
    # panel that lost exactly half its verifiers -- to a crash, a timeout, a prose verdict, or
    # any schema-invalid shape -- still met the floor while the refuters it lost were the ones
    # that would have carried the majority. That is a silent HALT->PASS flip. `n // 2 + 1` is a
    # no-op at every odd n (1, 3, 5, 7 -> 1, 2, 3, 4), so no committed panel changes behavior.
    floor = n // 2 + 1
    verifier_prompt = _verifier_prompt(unit)
    verifier_opts = _verifier_agent_opts(unit)

    verdicts_var = f"{name_prefix}verdicts"
    reported_var = f"{name_prefix}reported"
    missing_idx_var = f"{name_prefix}missing_idx"
    refute_count_var = f"{name_prefix}refute_count"
    threshold_var = f"{name_prefix}threshold"
    refuted_var = f"{name_prefix}refuted"

    panel_chunks = concurrency_governor.ordered_chunks(list(range(n)), max_concurrent)
    if len(panel_chunks) == 1:
        verdict_chunk_vars = [verdicts_var]
    else:
        # Keep the first bounded wave on the historical verdicts binding, then append later waves
        # in order so existing consumers still see the COMPLETE reporter set under that name.
        verdict_chunk_vars = [verdicts_var] + [
            f"{verdicts_var}_chunk_{index}" for index in range(2, len(panel_chunks) + 1)
        ]

    def _emit_verifier_member(_index: int) -> None:
        lines.append(f"{indent}  () => {_retry_open()}")
        lines.append(
            f"{indent}    __verifierPrompt({_js_string(verifier_prompt)}, {result_var}, "
            f"{_js_string(panel.pass_rule)}),"
        )
        lines.append(
            f"{indent}    {{ "
            + ", ".join(verifier_opts)
            + f", input: {{ unit_result: {result_var} }} }},"
        )
        lines.append(f"{indent}  {_retry_close(unit)}),")

    for chunk_var, chunk in zip(verdict_chunk_vars, panel_chunks, strict=True):
        _emit_parallel_wave(
            lines,
            binding=f"const {chunk_var}",
            bounded_members=chunk,
            render_member=_emit_verifier_member,
            indent=indent,
        )
    reconciled_verdicts_var = verdicts_var
    if len(panel_chunks) > 1:
        joined_chunks = ", ".join(f"...{name}" for name in verdict_chunk_vars[1:])
        lines.append(f"{indent}{verdicts_var}.push({joined_chunks})")
    # R1/R5: record which verifiers reported vs. runtime-missing; R3: recompute the pass-rule
    # threshold over the reporters, not the declared n (plan KTD1/KTD3). A verdict that is
    # non-null but lacks a usable `.refuted_deliverable` OR `.advisory_corrections` array is a
    # runtime failure too (a verifier that returned a malformed/partial response is not
    # distinguishable from one that returned a legitimate non-refuting verdict unless shape is
    # checked here -- completeness_gate.py's classify() only gates the unit's own result, never
    # verifier verdicts, so this is the only place malformed verdicts get caught). #686 R6/KTD2:
    # requiring BOTH buckets is what makes a legacy single-`refuted` verdict a runtime failure
    # that counts toward the missing-verifier floor instead of being silently read as gating.
    valid_verdict_var = f"{name_prefix}valid_verifier_verdict"
    lines.append(
        f'{indent}const {valid_verdict_var} = (v) => v != null && typeof v === "object" && '
        f"Array.isArray(v.refuted_deliverable) && Array.isArray(v.advisory_corrections) && "
        f"Array.isArray(v.upheld) && "
        f'typeof v.verifier_identity === "string" && v.verifier_identity.length > 0 && '
        f'Object.prototype.hasOwnProperty.call(v, "fallback_depth") && '
        f'typeof v.examined_sha === "string" && v.examined_sha.length > 0'
    )
    lines.append(
        f"{indent}const {reported_var} = "
        f"{reconciled_verdicts_var}.filter((v) => {valid_verdict_var}(v))"
    )
    # U6/R8/KTD7: attribute any reporter that descended the #325 fallback ladder. Each reporter
    # echoes verifier_identity + fallback_depth (default 0); this runtime marker mirrors the pure
    # render_fallback_tier_marker() helper -- empty when every reporter sat on the first-choice
    # rung, else " — fallback tier N (<identity>)" naming ONLY the degraded reporter(s). The
    # marker rides the operator-facing throw so a silent Claude-substituted verifier cannot hide.
    fallback_marker_var = f"{name_prefix}fallback_marker"
    lines.append(f"{indent}const {fallback_marker_var} = (() => {{")
    # Depth coercion mirrors render_fallback_tier_marker()'s Python guard exactly (bool -> 0,
    # non-integer string -> 0, float -> trunc, unparseable -> 0) so the tests that pin the pure
    # helper describe THIS runtime marker too (#390 review F4).
    lines.append(f"{indent}  const depthOf = (v) => {{")
    lines.append(f"{indent}    const raw = v.fallback_depth")
    lines.append(f'{indent}    if (typeof raw === "boolean") return 0')
    lines.append(
        f'{indent}    if (typeof raw === "string" && !/^-?\\d+$/.test(raw.trim())) return 0'
    )
    lines.append(f"{indent}    const d = Math.trunc(Number(raw))")
    lines.append(f"{indent}    return Number.isFinite(d) && d > 0 ? d : 0")
    lines.append(f"{indent}  }}")
    lines.append(f"{indent}  const degraded = {reported_var}.filter((v) => depthOf(v) > 0)")
    lines.append(f'{indent}  if (degraded.length === 0) return ""')
    lines.append(
        f'{indent}  return " — " + degraded.map((v) => '
        f"`fallback tier ${{depthOf(v)}} "
        f'(${{v.verifier_identity || "unknown-verifier"}})`).join("; ")'
    )
    lines.append(f"{indent}}})()")
    lines.append(
        f"{indent}const {missing_idx_var} = {reconciled_verdicts_var}.map((v, i) => "
        f"(!{valid_verdict_var}(v) ? i + 1 : null)).filter((i) => i != null)"
    )
    # #686 R2: the gate counts a verifier as refuting ONLY when its GATING bucket is non-empty.
    # `advisory_corrections` is deliberately absent from this arithmetic -- a panel that found
    # nothing but wrong prose upholds the unit (plan KTD5: this is the single gate site, so the
    # one-shot panel, the iterate-to-consensus loop, and the #364 climb all change together).
    lines.append(
        f"{indent}const {refute_count_var} = {reported_var}.filter((v) => "
        f"v.refuted_deliverable.length > 0).length"
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
    # #686 R4 / plan U1 site 4: harvest the NON-GATING bucket into the workflow-level
    # `__advisories` accumulator and log it. POSITION IS LOAD-BEARING -- this must sit here,
    # after the refuted const and BEFORE the missing-verifier block, because the #364 unattended
    # climb path returns early from this function at the `if (<refuted>) {` line below. A call
    # appended after that point would silently never emit for climb units, leaving advisories
    # absent on exactly that path and nowhere else. Emitting here covers all three panel shapes
    # (one-shot, iterate-to-consensus, climb) with a single insertion.
    lines.append(
        f"{indent}__logAdvisory({_js_string(unit.unit_id)}, {reported_var}, {refuted_var})"
    )
    # R4/R5: annotate missing verifiers and hard-fail below the baked quorum floor before any
    # accept/disagree decision can be computed over too little evidence.
    lines.append(f"{indent}if ({missing_idx_var}.length > 0) {{")
    lines.append(
        f"{indent}  log(`verify panel over {unit.unit_id}: "
        f"${{{missing_idx_var}.length}}/{n} verifier(s) missing "
        f'(runtime-failure: #${{{missing_idx_var}.join(", #")}}); '
        f"verdict computed over ${{{reported_var}.length}}/{n}` +"
    )
    if panel.pass_rule == "majority":
        lines.append(
            f"{indent}      ({reported_var}.length < {floor} ? "
            f'" — UNDER-STRENGTH (quorum floor {floor})" : '
            f"(!{refuted_var} && {refute_count_var} + {missing_idx_var}.length >= {floor} ? "
            f'" — UNDER-STRENGTH (potential-flip-on-missing)" : "")))'
        )
    else:
        lines.append(
            f"{indent}      ({reported_var}.length < {floor} ? "
            f'" — UNDER-STRENGTH (quorum floor {floor})" : ""))'
        )
    lines.append(f"{indent}}}")
    lines.append(f"{indent}if ({reported_var}.length < {floor}) {{")
    lines.append(
        f"{indent}  throw __halt(`verifier-under-strength: Unit {unit.unit_id} reported "
        f"${{{reported_var}.length}}/{n} verifiers (quorum floor {floor}; "
        f"missing #${{{missing_idx_var}.join(', #')}})${{{fallback_marker_var}}}`, {_js_string(unit.unit_id)})"
    )
    lines.append(f"{indent}}}")
    if panel.pass_rule == "majority":
        # #692: Option 3 missing-aware tightening at odd n (pessimistic missing refuter gate).
        # When survivors uphold (!refuted) but refuting survivors + missing verifiers >= floor,
        # missing verifiers could have produced a full-strength majority refutation.
        lines.append(
            f"{indent}if (!{refuted_var} && {refute_count_var} + {missing_idx_var}.length >= {floor}) {{"
        )
        lines.append(
            f"{indent}  throw __halt(`verifier-under-strength: Unit {unit.unit_id} reported "
            f"${{{reported_var}.length}}/{n} verifiers (potential-flip-on-missing)"
            f"${{{fallback_marker_var}}}`, {_js_string(unit.unit_id)})"
        )
        lines.append(f"{indent}}}")

    throw_line = (
        f"throw __halt(`verifier-disagreement: Unit {unit.unit_id} refuted by "
        f"${{{refute_count_var}}}/${{{reported_var}.length}} reporting verifiers "
        f"(${{{missing_idx_var}.length}} missing)${{{fallback_marker_var}}}{throw_suffix}`, {_js_string(unit.unit_id)})"
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
    lines: list[str],
    spec: ExecutionSpec,
    unit: Unit,
    session_ceiling: Tier | None = None,
    *,
    panel_max_concurrent: int,
    routing_context: EmissionRoutingContext,
) -> None:
    """Append one thunk entry for ``unit`` inside a ``parallel([...])``.

    Every thunk carries the unit's per-unit ``{model, effort}`` tier (R2(b)) and the same
    budget-rider / R10 reconciliation prompt as a singleton agent() call.
    """
    if unit.verify is not None and unit.verify.iterate_to_consensus:
        panel = unit.verify
        route = routing_context.for_unit(unit)
        prompt = route.prompt
        opts = _agent_opts(unit, route)
        marker = _external_engine_marker(unit, route)

        lines.append("  async () => {")
        lines.append("    let result;")
        lines.append(f"    for (let iter = 1; iter <= {panel.max_iterations}; iter++) {{")
        if marker is not None:
            lines.append(f"      // external-engine dispatch: {_js_comment_text(marker)}")
        lines.append(f"      result = await {_retry_open()}")
        lines.append(f"        {_js_string(prompt)},")
        lines.append("        { " + ", ".join(opts) + " },")
        lines.append(f"      {_retry_close(unit)})")
        lines.append(f"      {_emit_gate_call(unit, 'result', session_ceiling)}")
        _emit_panel_reconciliation(
            lines,
            unit,
            "result",
            "",
            "      ",
            max_concurrent=panel_max_concurrent,
            direct_throw=False,
        )
        lines.append("    }")
        lines.append("    return result")
        lines.append("  },")
    else:
        route = routing_context.for_unit(unit)
        prompt = route.prompt
        opts = _agent_opts(unit, route)
        marker = _external_engine_marker(unit, route)
        if marker is not None:
            lines.append("  () => {")
            lines.append(f"    // external-engine dispatch: {_js_comment_text(marker)}")
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
    *,
    panel_max_concurrent: int,
    routing_context: EmissionRoutingContext,
) -> None:
    """Emit the iterate-to-consensus loop for a singleton unit."""
    panel = unit.verify
    assert panel is not None
    n = panel.n
    route = routing_context.for_unit(unit)
    prompt = route.prompt
    opts = _agent_opts(unit, route)
    marker = _external_engine_marker(unit, route)

    lines.append(f"let {var};")
    lines.append(
        f"// verify: refute-{n} iterate-to-consensus loop over {unit.unit_id} "
        f"(pass_rule: {panel.pass_rule}, max_iterations: {panel.max_iterations})"
    )
    lines.append(f"for (let iter = 1; iter <= {panel.max_iterations}; iter++) {{")
    if marker is not None:
        lines.append(f"  // external-engine dispatch: {_js_comment_text(marker)}")
    lines.append(f"  {var} = await agent(")
    lines.append(f"    {_js_string(prompt)},")
    lines.append("    { " + ", ".join(opts) + " },")
    lines.append("  )")
    lines.append(f"  {_emit_gate_call(unit, var, session_ceiling)}")
    _emit_panel_reconciliation(
        lines,
        unit,
        var,
        "",
        "  ",
        max_concurrent=panel_max_concurrent,
        direct_throw=False,
    )
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
    panel_max_concurrent: int,
    environment: Mapping[str, str] | None = None,
    run_max_concurrent: int | None = None,
    routing_context: EmissionRoutingContext,
) -> None:
    """Append a refute-N judge-panel + pass-rule reconciliation for ``unit`` to ``lines``.

    Renders a ``parallel([...])`` of ``unit.verify.n`` verifier ``agent()`` calls over the
    unit's result (each at the SAME ``{model, effort}`` tier as the unit per R4), then
    records which verifiers reported vs. runtime-missing (R1/R5) -- a ``null`` verdict slot
    OR a non-null verdict lacking a usable ``.refuted_deliverable`` / ``.advisory_corrections``
    array both count as missing, since neither is a trustworthy signal -- and recomputes the
    pass-rule threshold over the reporters (R3): ``majority`` => ``>= max(1, ceil(k/2))`` of
    the ``k`` reporting verifiers refuted; ``unanimous`` => all ``k`` refuted. #686: "refuted"
    throughout this arithmetic means a non-empty GATING bucket -- a verifier reporting only
    ``advisory_corrections`` is a reporter that did NOT refute. A quorum floor of a STRICT
    majority of the declared ``n`` -- ``n // 2 + 1`` (plan KTD3) -- marks the result
    UNDER-STRENGTH when under-met, but a refutation still acts regardless (plan KTD4). The
    floor must be the strict majority rather than ``ceil(n/2)``: the two differ at even ``n``,
    and a floor that a half-strength panel can still meet lets a lost refuter flip HALT to PASS.
    (This is a panel-level signal, not per-finding survival: a generic emitter cannot match
    findings across verifiers, so it surfaces "did enough skeptics refute anything" for the
    operator/runtime to act on.) The resulting ``<var>_refuted`` boolean is CONSUMED: when
    set, the script THROWS ``verifier-disagreement: ...`` so a refuted unit result halts
    rather than being silently relied upon.
    """
    panel = unit.verify
    assert panel is not None  # caller guards this
    n = panel.n
    # Strict majority of the declared panel size -- must match _emit_panel_reconciliation.
    floor = n // 2 + 1

    lines.append(f"// verify: refute-{n} panel over {unit.unit_id} (pass_rule: {panel.pass_rule};")
    lines.append(
        f"// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is "
        f"met (quorum floor {floor} of {n} declared; runtime-missing verifiers shrink the "
        f"denominator))"
    )
    if not unit.escalate_on_signal:
        _emit_panel_reconciliation(
            lines,
            unit,
            var,
            f"{var}_",
            "",
            max_concurrent=panel_max_concurrent,
            direct_throw=True,
        )
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
            max_concurrent=panel_max_concurrent,
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
            max_concurrent=panel_max_concurrent,
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
    route = routing_context.for_unit(unit)
    _emit_panel_reconciliation(
        lines,
        unit,
        var,
        f"{var}_",
        "",
        max_concurrent=panel_max_concurrent,
        direct_throw=True,
        open_refuted_block=True,
    )
    lines.append(
        f"  log(`escalate_on_signal: {unit.unit_id} refuted at "
        f"{unit.tier.model}/{unit.tier.effort}; climbing ONE rung to "
        f"{climbed.model}/{climbed.effort} and retrying once (unattended, #364 R6)`)"
    )
    marker = _external_engine_marker(retry_unit, route)
    if marker is not None:
        lines.append(f"  // external-engine dispatch: {_js_comment_text(marker)}")
    retry_prompt = _ES._agent_prompt(spec, retry_unit)
    lines.append(f"  {var} = await agent(")
    lines.append(f"    {_js_string(retry_prompt)},")
    lines.append(f"    {{ {', '.join(_agent_opts(retry_unit, route))} }},")
    lines.append("  )")
    lines.append(f"  {_emit_gate_call(retry_unit, var, session_ceiling)}")
    _emit_panel_reconciliation(
        lines,
        retry_unit,
        var,
        f"{var}_retry_",
        "  ",
        max_concurrent=_ES.resolved_concurrency(
            spec,
            [_verify_panel_admission_unit(retry_unit)],
            environment=environment,
            run_override=run_max_concurrent,
            routing_context=routing_context,
        ).width,
        direct_throw=True,
        throw_suffix=(
            f" -- still refuted after the one-rung climb to "
            f"{climbed.model}/{climbed.effort} (HALT -- #364 KTD5: one climb per unit per run)"
        ),
    )
    lines.append("}")
    lines.append("")


def workflow_settlement_metadata(
    spec: ExecutionSpec,
    *,
    invocation_id: str | None = None,
    validate: bool = True,
    engine_registry: Any | None = None,
) -> dict[str, Any]:
    """Export driver-materialized workflow settlement contracts (#351).

    Generated workflow agents remain filesystem-free. The trusted root driver persists this metadata
    before submission, records host handles, and settles returned structured results.  A driver must
    mint one durable ``invocation_id`` before first submission and reuse it only when resuming that
    invocation.  This keeps a crash replay on the same dispatch while separating a later run of the
    unchanged spec.

    ``Unit.returns`` intentionally remains the workflow's original result contract.  Settlement has
    a narrower identifier vocabulary, so ``driver.units`` exposes the original result keys alongside
    their safe deliverable names for the host-side receipt adapter.
    """
    import dispatch_settlement  # noqa: PLC0415 - sibling; avoid wider import-time coupling

    if validate:
        has_external_routes = any(
            unit.engine is not None or unit.capability is not None for unit in spec.units
        )
        registry = (
            _load_emission_registry()
            if has_external_routes and engine_registry is None
            else engine_registry
        )
        spec.validate(engine_registry=registry)
    canonical = json.dumps(spec.to_dict(), sort_keys=True, separators=(",", ":"))
    spec_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if invocation_id is not None and (not isinstance(invocation_id, str) or not invocation_id):
        raise SpecError("workflow invocation_id must be a non-empty string when supplied")
    invocation_digest = (
        hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()[:24]
        if invocation_id is not None
        else ""
    )
    dispatch_id = f"workflow:{spec_digest[:24]}"
    if invocation_digest:
        dispatch_id += f":invocation:{invocation_digest}"
    units: list[dispatch_settlement.UnitSpec] = []
    driver_units: list[dict[str, Any]] = []
    for unit in spec.units:
        settlement_unit_id = dispatch_settlement.safe_contract_identifier(
            unit.unit_id, namespace="workflow-unit"
        )
        deliverables = ["structured-result"]
        settlement_deliverables = {"structured-result"}
        return_keys: list[dict[str, str]] = []
        for name in unit.returns:
            deliverable = "return:" + dispatch_settlement.safe_contract_identifier(
                name, namespace="workflow-return"
            )
            if deliverable not in settlement_deliverables:
                deliverables.append(deliverable)
                settlement_deliverables.add(deliverable)
            return_keys.append({"result_key": name, "deliverable": deliverable})
        idempotency_source = f"{dispatch_id}:{settlement_unit_id}"
        units.append(
            dispatch_settlement.UnitSpec(
                unit_id=settlement_unit_id,
                idempotency_key=dispatch_settlement.safe_contract_identifier(
                    idempotency_source, namespace="workflow-idempotency"
                ),
                deliverables=tuple(deliverables),
            )
        )
        driver_units.append(
            {
                "workflow_unit_id": unit.unit_id,
                "settlement_unit_id": settlement_unit_id,
                "return_keys": return_keys,
            }
        )
    metadata = dispatch_settlement.settlement_metadata(
        dispatch_id=dispatch_id,
        site="workflow",
        units=units,
    )
    metadata["driver"] = {
        "invocation_id": invocation_id,
        "units": driver_units,
    }
    return metadata


def workflow_lease_metadata(
    spec: ExecutionSpec,
    *,
    invocation_id: str | None = None,
    validate: bool = True,
    environment: Mapping[str, str] | None = None,
    run_max_concurrent: int | None = None,
    repo_root: Path | str | None = None,
    routing_overlay: Any = _ROUTING_SNAPSHOT_UNSET,
    routing_calibration: Any = _ROUTING_SNAPSHOT_UNSET,
    routing_context: EmissionRoutingContext | None = None,
) -> dict[str, Any]:
    """Export the driver-owned, all-or-none Workflow reservation contract (#356)."""

    if validate:
        spec.validate()
    if invocation_id is not None and (not isinstance(invocation_id, str) or not invocation_id):
        raise SpecError("workflow invocation_id must be a non-empty string when supplied")
    canonical = json.dumps(spec.to_dict(), sort_keys=True, separators=(",", ":"))
    spec_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    invocation_digest = (
        hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()[:24]
        if invocation_id is not None
        else None
    )
    context = routing_context or _ES._build_emission_routing_context(
        spec,
        repo_root=repo_root,
        routing_overlay=routing_overlay,
        routing_calibration=routing_calibration,
    )
    width = _ES.max_concurrent_agents(
        spec,
        environment=environment,
        run_override=run_max_concurrent,
        routing_context=context,
    )
    limits = _concurrency_policy(spec)
    limits.validate()
    mutation = (
        "none"
        if all(
            unit.sandbox is not None and unit.sandbox.mutation_policy == "read-only"
            for unit in spec.units
        )
        else "read-write"
    )
    batch_id = (
        None if invocation_digest is None else f"workflow:{spec_digest[:24]}:{invocation_digest}"
    )
    execution_ttl = max(900, 300 * spec.multiplicity_aware_unit_count())
    return {
        "schema": "workflow_lease_reservation.v1",
        "batch_id": batch_id,
        "owner_id": None if batch_id is None else f"driver:{batch_id}",
        "invocation_id": invocation_id,
        "spec_sha256": spec_digest,
        "reservation_width": width,
        "session_limit": width,
        "aggregate_limit": limits.aggregate_max_concurrent,
        "policy_sha256": limits.policy_sha256(),
        "mutation": mutation,
        "claim_ttl_seconds": 30,
        "execution_ttl_seconds": execution_ttl,
        "slots": [f"slot-{index:03d}" for index in range(1, width + 1)],
        "workload_unit_ids": [unit.unit_id for unit in spec.units],
        "requires_prelaunch_reservation": True,
        "generated_runtime_filesystem_access": False,
    }


def emit_workflow_script(
    spec: ExecutionSpec,
    session_ceiling: Tier | None = None,
    unattended: bool = False,
    *,
    environment: Mapping[str, str] | None = None,
    run_max_concurrent: int | None = None,
    repo_root: Path | str | None = None,
    routing_overlay: Any = _ROUTING_SNAPSHOT_UNSET,
    routing_calibration: Any = _ROUTING_SNAPSHOT_UNSET,
) -> str:
    """Emit a runnable Claude Code workflow script (.workflow.js) from the spec.

    Validates first (fail emit on R3 / R10 / #708), then renders a control-flow-only harness:
    one ``agent()`` call per unit at its ``{model, effort}`` tier, dependency barriers
    rendered as ``await`` ordering, fan-out reconciliation + cheap-tier budget riders
    baked into prompts. The agents do the real work; this script is control flow only.
    An external-engine unit (``engine`` / ``capability``) or any agent() opts key the
    cc-workflows runtime does not honor is rejected here with a named ``SpecError`` --
    never a silent fallback to a native Claude subagent (#708).

    ``unattended`` (#364 KTD3) is a run property, not spec state: attended emission (default)
    renders every escalate_on_signal refute as a throw-with-proposal ask gate; unattended
    emission renders the one-rung in-script climb retry instead. Attendance never enters the
    durable spec JSON.

    Returns the script source as a string (the caller writes it beside the plan and
    records the path as the saga ``orchestration_ref``).
    """
    _reject_unsupported_engine_units(spec)
    emission_environment = MappingProxyType(
        dict(os.environ if environment is None else environment)
    )
    has_external_routes = any(
        unit.engine is not None or unit.capability is not None for unit in spec.units
    )
    emission_registry = _load_emission_registry() if has_external_routes else None
    spec.validate(engine_registry=emission_registry)
    # #671: two units in one wave declaring the same file race on a shared working tree, and
    # nothing downstream catches it — workflow work units emit at the ambient default
    # (workspace_isolation "ambient"); only verify panels are spawned isolated. Halt here, before
    # any agent is rendered, rather than let the loser's edit disappear at run time.
    assert_no_wave_file_conflicts(spec)
    settlement_metadata = workflow_settlement_metadata(spec, validate=False)

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

    routing_context = _ES._build_emission_routing_context(
        spec,
        registry=emission_registry,
        repo_root=repo_root,
        routing_overlay=routing_overlay,
        routing_calibration=routing_calibration,
    )

    # #350 AC8: resolve and validate every layer/panel bound before emitting any workflow text.
    _ES.max_concurrent_agents(
        spec,
        environment=emission_environment,
        run_override=run_max_concurrent,
        routing_context=routing_context,
    )

    def _panel_max_concurrent(unit: Unit) -> int:
        return _ES.resolved_concurrency(
            spec,
            [_verify_panel_admission_unit(unit)],
            environment=emission_environment,
            run_override=run_max_concurrent,
            routing_context=routing_context,
        ).width

    lines: list[str] = []
    lines.append("// ===========================================================================")
    lines.append(f"// {_js_comment_text(spec.name)} -- emitted Claude Code workflow harness.")
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
    lines.append(
        # NOT `export const`: the Workflow runtime accepts only the leading
        # `export const meta` statement; any later `export` is a parse error.
        "const settlement = "
        + json.dumps(
            settlement_metadata,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    # No `const lease` is emitted (#671). The reservation contract is driver-owned: `/work` runs
    # `execution_spec.py lease` + `workflow_emitter.py reserve|attest|renew|release` against a
    # metadata file. A copy baked into the script could never be acted on -- workflow scripts have
    # no filesystem or Node API access, so the generated code cannot reach the broker at all.
    lines.append("")
    if spec.repo:
        lines.append(f"const REPO = {_js_string(spec.repo)}")
        lines.append("")

    # #364 R7/R8: workflow-level cord collector -- __gate pushes worker-initiated pull_cord
    # dispositions here; the single batched escalation check runs after every layer.
    lines.append("const __pulledCords = []")
    lines.append("")
    # #686 R4: workflow-level advisory collector -- every verify panel's NON-GATING corrections
    # land here (via __logAdvisory at the reconciliation site) and ride out on the final return.
    lines.append(_JS_ADVISORY_HELPER)
    lines.append("")
    lines.append(_JS_GATE_HELPER)
    lines.append("")
    lines.append(_JS_RETRY_HELPER)
    lines.append("")
    lines.append(_JS_VERIFIER_PROMPT_HELPER)
    lines.append("")

    # Topological waves (KTD4): each layer's units are mutually independent and run in one or
    # more bounded parallel() chunks; all chunks finish before the next layer (the dependency
    # barrier). A singleton layer renders as a plain `const x = await agent(...)`. _js_var
    # (module-level)
    # sanitizes the unit_id into the result var; validate() has already rejected any two ids
    # that would collide to the same identifier.
    _var = _js_var

    def _emit_unit_header(unit: Unit) -> None:
        lines.append(f"// ---- {unit.unit_id}: {_js_comment_text(unit.label)} ----")
        if unit.depends_on:
            lines.append(f"// depends_on: {', '.join(unit.depends_on)} (barrier)")
        if unit.pilot:
            lines.append(f"// pilot: {unit.pilot} (R3 same-tier gate)")
        if unit.escalation:
            lines.append(f"// escalation: {_js_comment_text(unit.escalation)}")

    def _emit_worker_member(unit: Unit) -> None:
        _emit_thunk(
            lines,
            spec,
            unit,
            session_ceiling,
            panel_max_concurrent=_panel_max_concurrent(unit),
            routing_context=routing_context,
        )

    for layer in dependency_layers(spec):
        layer_units = [spec.unit_by_id(uid) for uid in layer]
        if len(layer_units) == 1:
            unit = layer_units[0]
            assert unit is not None
            _emit_unit_header(unit)
            var = _var(unit.unit_id)
            if unit.verify is not None and unit.verify.iterate_to_consensus:
                _emit_verify_loop_singleton(
                    lines,
                    spec,
                    unit,
                    var,
                    session_ceiling,
                    panel_max_concurrent=_panel_max_concurrent(unit),
                    routing_context=routing_context,
                )
            else:
                route = routing_context.for_unit(unit)
                prompt = route.prompt
                opts = _agent_opts(unit, route)
                marker = _external_engine_marker(unit, route)
                if marker is not None:
                    lines.append(f"// external-engine dispatch: {_js_comment_text(marker)}")
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
                        panel_max_concurrent=_panel_max_concurrent(unit),
                        environment=emission_environment,
                        run_max_concurrent=run_max_concurrent,
                        routing_context=routing_context,
                    )
            continue

        # A layer of >1 ready unit is split into stable, sequential chunks. Each chunk is one
        # parallel() wave; all chunks finish before any dependent layer or verify panel starts.
        for unit in layer_units:
            assert unit is not None
            _emit_unit_header(unit)
        concrete_units = [cast(Unit, unit) for unit in layer_units]
        layer_chunks = concurrency_chunks(
            spec,
            concrete_units,
            environment=emission_environment,
            run_override=run_max_concurrent,
            routing_context=routing_context,
        )
        layer_width = max(len(chunk) for chunk in layer_chunks)
        for chunk_number, chunk_units in enumerate(layer_chunks, start=1):
            if len(layer_chunks) > 1:
                lines.append(
                    f"// concurrency chunk {chunk_number}/{len(layer_chunks)} "
                    f"(max_concurrent={layer_width})"
                )
            chunk_vars = [_var(unit.unit_id) for unit in chunk_units]
            wave_decl = (
                "let"
                if any(
                    _emits_climb_retry(unit, unattended, session_ceiling) for unit in chunk_units
                )
                else "const"
            )
            _emit_parallel_wave(
                lines,
                binding=f"{wave_decl} [{', '.join(chunk_vars)}]",
                bounded_members=chunk_units,
                render_member=_emit_worker_member,
            )
            for unit in chunk_units:
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
                    panel_max_concurrent=_panel_max_concurrent(unit),
                    environment=emission_environment,
                    run_max_concurrent=run_max_concurrent,
                    routing_context=routing_context,
                )

    # #364 R8: pull-cord batch -- exactly ONE coordinator escalation entry, never one ask per
    # cord. Emitted after every layer so all cords collect before the single batched throw; a
    # cord unit is never marked complete because the run fails here before returning.
    lines.append("if (__pulledCords.length > 0) {")
    lines.append(
        "  throw __halt(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported "
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

    # #686 R4/KTD4: every emitted harness ends with a return value. `advisory_corrections` is the
    # non-gating half of the verify verdict reaching the driving session (the logging half fires
    # during the run); `units` carries each unit's result so the return is useful beyond
    # advisories. Emitted harnesses returned `undefined` before this, so any object is additive
    # for consumers that do not destructure.
    unit_entries = ", ".join(
        f"{_js_string(unit.unit_id)}: {_var(unit.unit_id)}" for unit in spec.units
    )
    lines.append("return {")
    lines.append(f"  units: {{ {unit_entries} }},")
    lines.append("  advisory_corrections: __advisories,")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)
