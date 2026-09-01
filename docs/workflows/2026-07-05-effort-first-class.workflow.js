// ===========================================================================
// effort-first-class -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "effort-first-class",
  description: "Issue #363: make effort a first-class validated value fleet-wide, honored by the real knob where the path has it (Workflow/external-engine) and a labeled EFFORT_RIDER proxy only on the native Agent-tool path, behind one inject_effort() seam (KTD1). Frontmatter field + CI lint, EFFORT_RIDER+seam in fleet_commons, A7 tier validation + 3-layer cascade via tier_resolver.resolve() + chaperone exclusion, dispatch wiring + cross-plugin convention, reconciliation, release surfaces. Serialized (max concurrency 1) for API rate-limit safety and to avoid concurrent edits to shared test files (tests/test_team_emitter.py, tests/test_agent_tier_lint.py).",
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

// ---- U1: effort vocab + frontmatter field + CI lint ----
const U1 = await agent(
  "U1: Establish `effort:` as a recognized agent-frontmatter field sourced from tier_palette.EFFORTS, and build the glob+membership lint as a pytest test (tests/test_agent_tier_lint.py) that runs in the EXISTING CI pytest step (no new CI step needed), plus an optional thin scripts/lint_agent_tiers.py wrapper for manual runs. It parses every plugins/*/agents/*.md frontmatter and asserts effort in EFFORTS and model in MODELS, honoring a `tiering_exempt: true` escape hatch. Reuse _parse_frontmatter from tests/test_agent_tiering.py. Note: all 33 existing model: values are already in-palette (verified at plan time), so the lint will not red-CI. Read the plan at docs/plans/2026-07-05-effort-first-class-plan.md (U1, R1/R2/R3, KTD3/KTD6) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "effort vocab + frontmatter field + CI lint", model: "sonnet", effort: "medium" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U2: EFFORT_RIDER + inject_effort() seam in fleet_commons ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Add EFFORT_RIDER (a dict[str,str] mapping each EFFORTS value to a short prompt-preamble directive) and inject_effort(prompt, effort, spawn_kind) to a new plugins/fleet-core/scripts/fleet_commons/effort_rider.py, consumed cross-plugin via fleet_commons_shim.load. The seam pass-throughs spawn_kind 'workflow' and 'external-engine' (effort already rides in agent({effort}) opts per execution_spec.py:982 - do NOT double-inject) and prepends EFFORT_RIDER[effort] for spawn_kind 'agent'; an unknown spawn_kind raises. Mirror the BUDGET_RIDER prepend pattern (execution_spec.py:132, injected :1000/:1247). Add tests/test_effort_rider.py. Read the plan at docs/plans/2026-07-05-effort-first-class-plan.md (U2, R7/R8, KTD1/KTD2) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "EFFORT_RIDER + inject_effort() seam in fleet_commons", model: "opus", effort: "high" },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U3: A7 tier validation + 3-layer cascade + chaperone exclusion ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: In plugins/saga/scripts/team_emitter.py, validate the A7 Tier cell's effort half against EFFORTS (raise on off-palette, R4); implement the three-layer effort cascade (plan-unit tier -> team default -> agent-frontmatter default) that WRAPS tier_resolver.resolve() - resolve() supplies the base agent-default layer, team/plan layers apply above it, most-specific wins (KTD4); record a per-teammate provenance line naming the resolving layer (R5); EXCLUDE chaperone workers (offload -> sonnet/medium, second-opinion -> opus/high) from the cascade, preserving their intent default (R6, KTD5). Add tests to tests/test_team_emitter.py. Read the plan at docs/plans/2026-07-05-effort-first-class-plan.md (U3, R4/R5/R6, KTD4/KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "A7 tier validation + 3-layer cascade + chaperone exclusion", model: "opus", effort: "high" },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U4: wire seam into dispatch + cross-plugin convention ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Wire inject_effort(prompt, resolved_effort, 'agent') into team-execution's dispatch path before the Agent-tool spawn (plugins/team-execution/skills/team-execution/SKILL.md:318). Write the single fleet effort-convention reference doc (once, not per-plugin). Add a validated `effort:` frontmatter field consuming the convention to at least one plugins/agy/agents/*.md and one plugins/deploy/agents/*.md agent (both must pass the U1 lint). Add/extend tests asserting the rider text appears in a teammate's constructed spawn prompt. Read the plan at docs/plans/2026-07-05-effort-first-class-plan.md (U4, R7/R8, KTD1) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "wire seam into dispatch + cross-plugin convention", model: "sonnet", effort: "medium" },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U5: post-run reconciliation (tiering-drift) ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Add the post-run reconciliation that compares each teammate's cascade-resolved effort against the effort recorded for it in the worker manifest (references/worker-manifest.md:48,54, which already records the resolved effort) and emits a named tiering-drift line on mismatch (nothing on match), honest per path (KTD7): on a real-knob path the manifest effort is the value passed to agent()/the engine; on the Agent-tool path confirm only that the EFFORT_RIDER text for the resolved level reached the constructed prompt - the drift line names the path and the compared quantity, never claiming to observe harness reasoning spend. Add tests to tests/test_team_emitter.py. Read the plan at docs/plans/2026-07-05-effort-first-class-plan.md (U5, R9, KTD7) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "post-run reconciliation (tiering-drift)", model: "sonnet", effort: "medium" },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U6: release surfaces ----
// depends_on: U5 (barrier)
const U6 = await agent(
  "U6: Bump plugins/saga, plugins/team-execution, and plugins/fleet-core plugin.json versions; mirror .claude-plugin/marketplace.json; add CHANGELOG entries for all three; flip the QUEUED.md {#team-execution-per-teammate-effort} entry to shipped (noting the honoring-seam resolution, NOT route-onto-Workflow); record KTD1-KTD7 in docs/engineering-journal/DECISIONS.md; update the metadata drift-guard test so installed-plugin metadata matches the diff. Read the plan at docs/plans/2026-07-05-effort-first-class-plan.md (U6, Definition of Done) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces", model: "sonnet", effort: "medium" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "summary"] })
