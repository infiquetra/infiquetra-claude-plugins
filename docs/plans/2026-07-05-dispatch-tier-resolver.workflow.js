// ===========================================================================
// dispatch-tier-resolver -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "dispatch-tier-resolver",
  description: "Issue #362: fleet_commons tier_resolver + work-shape->tier registry, /plan table render + drift-guard, team-execution role-tier migration (25 agents), effort emission + spawn-site guard, release surfaces. Serialized (max concurrency 1) for API rate-limit safety and to avoid concurrent edits to the shared resolver test file. Effort-honoring deferred to #363; vocab source/ladder ops to #370.",
}

const REPO = "infiquetra/infiquetra-claude-plugins"

function __gate(result, opts) {
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
          // ignore
        }
      }
    }
    return val;
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
}

function __is429(x) {
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
}

// ---- U1: work-shape->tier registry ----
const U1 = await agent(
  "U1: Create plugins/fleet-core/scripts/fleet_commons/tier_policy.json - one object per work-shape key mirroring plan/SKILL.md:298-304, each carrying {default_model, default_effort, rationale}; and the registry test cases in tests/test_tier_resolver.py (parses as JSON; every default_model in MODELS and default_effort in EFFORTS; all five SKILL.md rows present). Read the plan at docs/plans/2026-07-05-dispatch-tier-resolver-plan.md (U1, R2) as your authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.",
  { label: "work-shape->tier registry", model: "sonnet", effort: "medium" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U2: tier_resolver module ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Create plugins/fleet-core/scripts/fleet_commons/tier_resolver.py - resolve(role_kind, work_shape, envelope_ceiling=None, operator_override=None) -> Resolution(model, effort, because, cheaper_fallback, needs_confirm), importing MODELS/EFFORTS/model_rank/effort_rank from tier_palette via fleet_commons_shim (never re-declaring the tuples); a `resolve` CLI subcommand; and the resolver tests (resolve_shapes, cheaper_fallback_one_rung with floor no-op, expensive_tier_confirm_gate, operator_override, envelope_ceiling). Read the plan at docs/plans/2026-07-05-dispatch-tier-resolver-plan.md (U2, R1/R3/R4, KTD2-KTD4) as your authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.",
  { label: "tier_resolver module", model: "sonnet", effort: "high" },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U3: /plan table render + drift-guard ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: Refactor plugins/saga/skills/plan/SKILL.md Step-1 tier table to render from tier_policy.json, and add the skill_registry_sync drift-guard test to tests/test_tier_resolver.py (a seeded divergence between the SKILL.md table and the registry fails). Read the plan at docs/plans/2026-07-05-dispatch-tier-resolver-plan.md (U3, R6) as your authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.",
  { label: "/plan table render + drift-guard", model: "sonnet", effort: "medium" },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U4: team-execution role-tier migration ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Migrate all 25 plugins/team-execution/agents/*.md frontmatters from model: to role-tier: per the plan's KTD7 mapping (reviewers->adversarial-review, scanners->mechanical-scan, testers->contract-test, etc.), keeping each existing model: as a documented last-resort fallback; add role_tier_resolves_for_all_agents and model_fallback_when_registry_absent tests to tests/test_tier_resolver.py. Read the plan at docs/plans/2026-07-05-dispatch-tier-resolver-plan.md (U4, R5, KTD5/KTD7) as your authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.",
  { label: "team-execution role-tier migration", model: "sonnet", effort: "medium" },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U5: effort emission + spawn-site guard ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Emit per-teammate effort into /plan's unit tier table and team-execution's A7 worker table (EMISSION ONLY - honoring is #363; align the A7 column schema with #363's parser), reference the resolver at each enumerated site in plugins/saga/references/sandbox-spawn-sites.md, and add the effort_emitted_into_tables + spawn_site_enumeration drift-guard tests (each dispatch site routes its tier decision through the resolver; a new bare palette literal at an enumerated site fails). Read the plan at docs/plans/2026-07-05-dispatch-tier-resolver-plan.md (U5, R7, KTD6) as your authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.",
  { label: "effort emission + spawn-site guard", model: "sonnet", effort: "high" },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U6: release surfaces ----
// depends_on: U5 (barrier)
const U6 = await agent(
  "U6: Bump plugins/saga and plugins/team-execution plugin.json versions, mirror .claude-plugin/marketplace.json, add CHANGELOG entries for both, record KTD1-KTD7 in docs/engineering-journal/DECISIONS.md, and update the metadata drift-guard test so installed-plugin metadata matches the diff. Read the plan at docs/plans/2026-07-05-dispatch-tier-resolver-plan.md (U6, R8) as your authoritative spec.\n\nReturn a structured result with keys: files_changed, summary.",
  { label: "release surfaces", model: "sonnet", effort: "medium" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "summary"] })
