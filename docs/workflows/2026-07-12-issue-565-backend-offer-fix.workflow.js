// ===========================================================================
// backend-offer-fix -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "backend-offer-fix",
  description: "Issue #565: fix the /plan Phase 5.2 execution-backend recommendation + offer flow (functional-surface size signal, widened workflow-shape vocabulary, availability provenance, full three-backend enumeration with omit_ultracode deleted) plus the Verify per-panel tier with its own receipts. Concurrency shaped to the operator cap of 3: fully serialized U1->U2->U3->U4 - U1 and U3 carry refute-3 panels (3 verifiers, at cap) that must never overlap a running unit; serialization also keeps tests/test_saga_plugin.py edits (U1, U4) from conflicting. Panels ride the unit tier (R4 - this run predates its own U3 fix) on the two contract-bearing code units only: U1 (the recommender contract reshape) and U3 (Verify schema + emitter + spend with the byte-identical-emission constraint).",
}

const REPO = "infiquetra/infiquetra-claude-plugins"

const __pulledCords = []

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

function __verifierPrompt(basePrompt, unitResult) {
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
  evidence to judge, return a refuted entry explaining the visibility gap; do not emit prose-only
  "nothing to verify" output.

UNIT RESULT INPUT (authoritative structured evidence):
${rendered}`;
}

// ---- U1: lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests ----
const U1 = await agent(
  "U1: Rework recommend_execution_backend/should_offer_team_execution in plugins/saga/scripts/lifecycle_state.py per KTD1-KTD4 (subtractive release_surface_file_count; frozen validated WORKFLOW_SHAPES vocabulary understand/design/research/review/migrate tripping the ultracode branch under the same elevated-risk suppressor; workflow_availability_source probed|asserted echoed as workflow_availability {available, source}; new backends key always enumerating all three backends with per-backend status recommended|alternative|unavailable and provenance note; omit_ultracode DELETED; alternatives retained reachable-only; CLI flags --release-surface-file-count, repeatable --workflow-shape, --workflow-availability-source). Honor KTD4's compat contract for the direct consumer outcome_dispatcher.py:411-425: new kwargs stay default-valued, recommended/rationale/alternatives keep their semantics, AND the frontier-budget downgrade path re-stamps the backends statuses (team-execution -> recommended, ultracode -> alternative with the budget_note reason) with a regression test in tests/test_outcome_dispatcher.py. Update the existing recommender tests in tests/test_saga_plugin.py (block at ~:2600 pins the defective behaviors - update, never leave asserting the defect) and add the U1 scenarios from the plan (the #526-shape regression, shape triggers + ValueError, suppressor precedence, three-entry backends under workflow_available=False, CLI e2e, dispatcher downgrade consistency). Read the plan at docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U1_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "lifecycle_state.py recommender rework: functional surface, workflow shapes, availability provenance, backends enumeration + lockstep tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
])
const U1_valid_verifier_verdict = (v) => v != null && typeof v === "object" && Array.isArray(v.refuted) && Array.isArray(v.upheld) && typeof v.verifier_identity === "string" && v.verifier_identity.length > 0 && Object.prototype.hasOwnProperty.call(v, "fallback_depth") && typeof v.examined_sha === "string" && v.examined_sha.length > 0
const U1_reported = U1_verdicts.filter((v) => U1_valid_verifier_verdict(v))
const U1_fallback_marker = (() => {
  const depthOf = (v) => {
    const raw = v.fallback_depth
    if (typeof raw === "boolean") return 0
    if (typeof raw === "string" && !/^-?\d+$/.test(raw.trim())) return 0
    const d = Math.trunc(Number(raw))
    return Number.isFinite(d) && d > 0 ? d : 0
  }
  const degraded = U1_reported.filter((v) => depthOf(v) > 0)
  if (degraded.length === 0) return ""
  return " — " + degraded.map((v) => `fallback tier ${depthOf(v)} (${v.verifier_identity || "unknown-verifier"})`).join("; ")
})()
const U1_missing_idx = U1_verdicts.map((v, i) => (!U1_valid_verifier_verdict(v) ? i + 1 : null)).filter((i) => i != null)
const U1_refute_count = U1_reported.filter((v) => v.refuted.length > 0).length
const U1_threshold = Math.max(1, Math.ceil(U1_reported.length / 2))  // majority over reporters
const U1_refuted = U1_refute_count >= U1_threshold
if (U1_missing_idx.length > 0) {
  log(`verify panel over U1: ${U1_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U1_missing_idx.join(", #")}); verdict computed over ${U1_reported.length}/3` +
      (U1_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U1_reported.length < 2) {
  throw new Error(`verifier-under-strength: Unit U1 reported ${U1_reported.length}/3 verifiers (quorum floor 2; missing #${U1_missing_idx.join(', #')})${U1_fallback_marker}`)
}
if (U1_refuted) {
  throw new Error(`verifier-disagreement: Unit U1 refuted by ${U1_refute_count}/${U1_reported.length} reporting verifiers (${U1_missing_idx.length} missing)${U1_fallback_marker}`)
}

// ---- U2: Prose lockstep: offer contract across plan SKILL, operator-choice, loop SKILL, execution-strategy ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Rewrite the six prose sites that instruct backend omission, document the old recommender JSON shape, or render the offer from alternatives-only, per R2-R4 and KTD2-KTD4: plugins/saga/skills/plan/SKILL.md Phase 5.2 (omit sentence at ~:286, widen the two-purpose framing at ~:269-277 to the five workflow shapes, mandate the ToolSearch availability probe - the word ToolSearch must appear in Phase 5.2 per AC4), plugins/saga/references/operator-choice.md (section 3.2 vocabulary, section 4 omit rule at ~:153 becomes always-name-and-mark-with-provenance, section 5 offer form if it echoes omission), plugins/saga/skills/loop/SKILL.md ~:268, plugins/saga/skills/work/references/execution-strategy.md ~:166 and ~:181-182 (new JSON shape: backends + workflow_availability, no omit_ultracode, new CLI flags), plugins/saga/skills/work/SKILL.md ~:50 and ~:229-232 plus plugins/saga/skills/loop/references/drive-and-resume.md ~:52-56 (both say surface-the-alternatives - reword to render the offer from the full backends enumeration so every offer site names all three). Match U1's landed output shape exactly - read plugins/saga/scripts/lifecycle_state.py after U1 before writing. Read the plan at docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "Prose lockstep: offer contract across plan SKILL, operator-choice, loop SKILL, execution-strategy", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}}, "required": ["files_changed", "summary"], "type": "object"} },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U3: Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: Add the optional per-panel tier to Verify in plugins/saga/scripts/execution_spec.py per KTD5 (Verify.tier: Tier | None defaulting to the unit tier; Verify.worth_it_because + Verify.cheaper_fallback mirroring the unit receipt fields; palette-ceiling validation HALTs haiku/xhigh; from_dict/to_dict omit absent keys byte-identically; the single verifier-opts emit site uses the effective tier verify.tier or unit.tier; unit_spend prices the n x iterations verifier calls at the effective panel tier; Unit.validate threads require_receipts into verify.validate so a premium panel without receipts fails only validate --require-receipts). Add the U3 test scenarios from the plan to tests/test_saga_execution_spec.py (panel-tier emission, byte-identical omission, receipts gate both ways, not-strictly-cheaper fallback SpecError, palette HALT, panel-tier spend arithmetic). Read the plan at docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U3 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U3_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U3 (Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U3),
    { label: "Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U3 } },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U3 (Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U3),
    { label: "Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U3 } },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U3 (Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U3),
    { label: "Verify per-panel tier + receipts in execution_spec.py: schema, effective-tier emission, panel-tier spend + tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U3 } },
  ), { unitId: "U3", maxAttempts: 3 }),
])
const U3_valid_verifier_verdict = (v) => v != null && typeof v === "object" && Array.isArray(v.refuted) && Array.isArray(v.upheld) && typeof v.verifier_identity === "string" && v.verifier_identity.length > 0 && Object.prototype.hasOwnProperty.call(v, "fallback_depth") && typeof v.examined_sha === "string" && v.examined_sha.length > 0
const U3_reported = U3_verdicts.filter((v) => U3_valid_verifier_verdict(v))
const U3_fallback_marker = (() => {
  const depthOf = (v) => {
    const raw = v.fallback_depth
    if (typeof raw === "boolean") return 0
    if (typeof raw === "string" && !/^-?\d+$/.test(raw.trim())) return 0
    const d = Math.trunc(Number(raw))
    return Number.isFinite(d) && d > 0 ? d : 0
  }
  const degraded = U3_reported.filter((v) => depthOf(v) > 0)
  if (degraded.length === 0) return ""
  return " — " + degraded.map((v) => `fallback tier ${depthOf(v)} (${v.verifier_identity || "unknown-verifier"})`).join("; ")
})()
const U3_missing_idx = U3_verdicts.map((v, i) => (!U3_valid_verifier_verdict(v) ? i + 1 : null)).filter((i) => i != null)
const U3_refute_count = U3_reported.filter((v) => v.refuted.length > 0).length
const U3_threshold = Math.max(1, Math.ceil(U3_reported.length / 2))  // majority over reporters
const U3_refuted = U3_refute_count >= U3_threshold
if (U3_missing_idx.length > 0) {
  log(`verify panel over U3: ${U3_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U3_missing_idx.join(", #")}); verdict computed over ${U3_reported.length}/3` +
      (U3_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U3_reported.length < 2) {
  throw new Error(`verifier-under-strength: Unit U3 reported ${U3_reported.length}/3 verifiers (quorum floor 2; missing #${U3_missing_idx.join(', #')})${U3_fallback_marker}`)
}
if (U3_refuted) {
  throw new Error(`verifier-disagreement: Unit U3 refuted by ${U3_refute_count}/${U3_reported.length} reporting verifiers (${U3_missing_idx.length} missing)${U3_fallback_marker}`)
}

// ---- U4: Release surfaces: saga version bump, marketplace, CHANGELOG, drift pin ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Release surfaces for the #565 change per R7: bump plugins/saga/.claude-plugin/plugin.json to the next minor version, mirror it in .claude-plugin/marketplace.json, prepend a plugins/saga/CHANGELOG.md entry describing the new offer contract (backends enumeration with availability provenance, omit_ultracode removed, release_surface_file_count, workflow_shapes vocabulary) and the Verify per-panel tier + receipts, and update the saga version drift pin in tests/test_saga_plugin.py. Read the plan at docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md as your authoritative spec.\n\nBUDGET DISCIPLINE (cheap-tier): you run on a small output budget. (1) CAP OUTPUT -- be terse; no human-facing prose, no recaps of files you read. (2) MANDATORY EMIT -- your FINAL message MUST be the JSON return object (see the RETURN CONTRACT); never end the turn without it, even if the work is partial (return what you have + a note). (3) SKIM, don't read -- open only the exact lines you need, never whole large files. (4) BATCH -- issue independent tool calls in one parallel block, not serially.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).\n\nPULL-CORD (#364, overrides the return contract above when it applies): if you judge this task is genuinely beyond your depth -- not merely hard, but you cannot produce a substantively correct result at your tier -- emit ONLY {\"pull_cord\": \"<one-line reason>\"} as your final message instead of the return contract. The coordinator batches every pulled cord into ONE escalation ask; your unit is never marked complete. Never pull the cord for partial-but-sound work (use the return contract with a note instead).",
  { label: "Release surfaces: saga version bump, marketplace, CHANGELOG, drift pin", model: "haiku", effort: "low", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "pull_cord": {"type": "string"}, "summary": {}}, "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "haiku/low -> haiku/medium (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
