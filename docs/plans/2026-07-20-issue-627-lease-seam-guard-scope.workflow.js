// ===========================================================================
// issue-627-lease-seam-guard-scope -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "issue-627-lease-seam-guard-scope",
  description: "Issue #627: the four validated PA-2 upstream routings at 83a170ff \u2014 refuse-mode lease admission (opt-in, KTD1), DispatcherError arm on the reconcile hot path (KTD3), reducer-visible halt records (KTD4), universal fail-closed ancestor walk (KTD2), release surfaces + codex follow-up definition. Concurrency shaped to the operator cap of 3: fully serialized U1->U2->U3->U4->U5 (U2 and U3 both edit outcome.py; serialization avoids write conflicts and keeps the refute-3 panels \u2014 at cap \u2014 from overlapping a running unit). Panels ride the unit tier on the three contract-bearing units: U1 (admission semantics on the shared broker), U2 (the reduction seam that produced #631), U4 (security guard scope on the byte-frozen seam).",
}
export const settlement = {"casualty_threshold_percent":0,"dispatch_id":"workflow:2bf3fabdaa93188cd90a3d06","driver":{"invocation_id":null,"units":[{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U1","workflow_unit_id":"U1"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U2","workflow_unit_id":"U2"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U3","workflow_unit_id":"U3"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U4","workflow_unit_id":"U4"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U5","workflow_unit_id":"U5"}]},"max_attempts":3,"schema":"dispatch_settlement.v1","site":"workflow","units":[{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:2bf3fabdaa93188cd90a3d06:U1","unit_id":"U1"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:2bf3fabdaa93188cd90a3d06:U2","unit_id":"U2"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:2bf3fabdaa93188cd90a3d06:U3","unit_id":"U3"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:2bf3fabdaa93188cd90a3d06:U4","unit_id":"U4"},{"deliverables":["structured-result","return:files_changed","return:summary"],"idempotency_key":"workflow:2bf3fabdaa93188cd90a3d06:U5","unit_id":"U5"}]}
export const lease = {"aggregate_limit":7,"batch_id":null,"claim_ttl_seconds":30,"execution_ttl_seconds":300,"generated_runtime_filesystem_access":false,"invocation_id":null,"mutation":"read-write","owner_id":null,"policy_sha256":"b985631b1a874a0817a3cac49b27565875fb5dedd3ad2008cf397dc640d43a0a","requires_prelaunch_reservation":true,"reservation_width":1,"schema":"workflow_lease_reservation.v1","session_limit":1,"slots":["slot-001"],"spec_sha256":"2bf3fabdaa93188cd90a3d0695488784091732c1839b84040408f2a55c01f57c","workload_unit_ids":["U1","U2","U3","U4","U5"]}

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

// ---- U1: refuse-mode lease admission + dispatcher wiring + prose de-overclaim ----
const U1 = await agent(
  "U1: Add the opt-in on_conflict admission mode (supersede default | refuse) to fleet_commons lease_broker acquire_agent/_drop_superseded_resource_lease with a liveness check via the existing _expired predicate, a typed conflict error subclassing LeaseOwnershipError naming the holder, unchanged precedence for the settlement-retained and canonically-closed arms, and wire the outcome dispatcher (make_dispatcher in outcome_dispatcher.py) to pass refuse; de-overclaim the dispatcher/broker prose. Tests per the plan's U1 scenarios including the two-broker refusal with zero registry mutation, expired-prior reclaim, test_retry_supersedes_at_full_capacity untouched-and-green, and the KTD6 dispatch-identity determinism pin. Read the plan at docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md (U1, R1/R2/R7, KTD1/KTD6) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "refuse-mode lease admission + dispatcher wiring + prose de-overclaim", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U1_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (refuse-mode lease admission + dispatcher wiring + prose de-overclaim). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "refuse-mode lease admission + dispatcher wiring + prose de-overclaim verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
])
const U1_verdicts_chunk_2 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (refuse-mode lease admission + dispatcher wiring + prose de-overclaim). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "refuse-mode lease admission + dispatcher wiring + prose de-overclaim verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
])
const U1_verdicts_chunk_3 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (refuse-mode lease admission + dispatcher wiring + prose de-overclaim). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "refuse-mode lease admission + dispatcher wiring + prose de-overclaim verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
])
U1_verdicts.push(...U1_verdicts_chunk_2, ...U1_verdicts_chunk_3)
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

// ---- U2: DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Add the except DispatcherError arm to _reconcile_once in plugins/saga/scripts/outcome.py beside the BackendRateLimitError/BackendHaltError arms: release the per-subplot lease exactly as the siblings, append a durable reducer-visible halt record ({**receipt, \"kind\": \"dispatch\"}, phase halt, the same key as the intent append so the orphaned-intent lane is paired, never an ack), settle the attempt as SILENT_NOOP (the LEDGER_CLASSIFICATIONS vocabulary is closed \u2014 no new member; the BackendHaltError arm's no-backend-effect precedent applies), append sid to halted, continue the tick. Mirror the codex pin name test_advance_records_lease_refusal_as_halt_and_continues. Tests per the plan's U2 scenarios (lock released without TTL wait, reduce_dispatch_ledger derives halted=True settled=False, second ready leaf still dispatches, renew-failure flavor takes the same arm). Read the plan at docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md (U2, R3, KTD3/KTD4) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U2 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U2_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
])
const U2_verdicts_chunk_2 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
])
const U2_verdicts_chunk_3 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "DispatcherError arm in _reconcile_once: release lock, durable visible halt, continue tick verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
])
U2_verdicts.push(...U2_verdicts_chunk_2, ...U2_verdicts_chunk_3)
const U2_valid_verifier_verdict = (v) => v != null && typeof v === "object" && Array.isArray(v.refuted) && Array.isArray(v.upheld) && typeof v.verifier_identity === "string" && v.verifier_identity.length > 0 && Object.prototype.hasOwnProperty.call(v, "fallback_depth") && typeof v.examined_sha === "string" && v.examined_sha.length > 0
const U2_reported = U2_verdicts.filter((v) => U2_valid_verifier_verdict(v))
const U2_fallback_marker = (() => {
  const depthOf = (v) => {
    const raw = v.fallback_depth
    if (typeof raw === "boolean") return 0
    if (typeof raw === "string" && !/^-?\d+$/.test(raw.trim())) return 0
    const d = Math.trunc(Number(raw))
    return Number.isFinite(d) && d > 0 ? d : 0
  }
  const degraded = U2_reported.filter((v) => depthOf(v) > 0)
  if (degraded.length === 0) return ""
  return " — " + degraded.map((v) => `fallback tier ${depthOf(v)} (${v.verifier_identity || "unknown-verifier"})`).join("; ")
})()
const U2_missing_idx = U2_verdicts.map((v, i) => (!U2_valid_verifier_verdict(v) ? i + 1 : null)).filter((i) => i != null)
const U2_refute_count = U2_reported.filter((v) => v.refuted.length > 0).length
const U2_threshold = Math.max(1, Math.ceil(U2_reported.length / 2))  // majority over reporters
const U2_refuted = U2_refute_count >= U2_threshold
if (U2_missing_idx.length > 0) {
  log(`verify panel over U2: ${U2_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U2_missing_idx.join(", #")}); verdict computed over ${U2_reported.length}/3` +
      (U2_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U2_reported.length < 2) {
  throw new Error(`verifier-under-strength: Unit U2 reported ${U2_reported.length}/3 verifiers (quorum floor 2; missing #${U2_missing_idx.join(', #')})${U2_fallback_marker}`)
}
if (U2_refuted) {
  throw new Error(`verifier-disagreement: Unit U2 refuted by ${U2_refute_count}/${U2_reported.length} reporting verifiers (${U2_missing_idx.length} missing)${U2_fallback_marker}`)
}

// ---- U3: halt-record visibility: kind survives the spread at all three sites, end-to-end report pin ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: At the three receipt-spread halt appends in plugins/saga/scripts/outcome.py (spend-gate, backend-menu, BackendHaltError arm \u2014 currently :1314/:1383/:1552) make the final kind \"dispatch\" (spread first, literal last), preserving the receipt's own kind under receipt_kind; retire the outcome_dispatcher.py:632-634 self-acknowledgment docstring; leave the three settlement-halt sites untouched; update the tests/test_outcome_report.py _halt fixture to spread a real HaltReceipt so it matches production shape. Tests per the plan's U3 scenarios (end-to-end forced BackendHaltError and spend/backend-menu halts through advance() -> reducer halted=True -> _halted_subplots -> consolidated report ambiguity item on a fresh read; halt-then-recovered stays non-sticky). Read the plan at docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md (U3, R4, KTD4) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "halt-record visibility: kind survives the spread at all three sites, end-to-end report pin", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U4: universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Rewrite _refuse_unsafe_handoff_ancestors (plugins/saga/scripts/outcome_compat.py) and _refuse_unsafe_ancestors (plugins/fleet-core/scripts/fleet_commons/audit_store.py) as the universal walk: every existing component from the filesystem root, lstat never resolve, refusing symlinked / world-writable-non-sticky / uninspectable components anywhere; sole mode exemption world-writable AND sticky (S_ISVTX); fail closed on NFS/SMB and FAT32/exFAT shapes per KTD2 with relocate guidance in the typed halts; keep FileNotFoundError/PermissionError arm semantics; rewrite both docstrings honestly (delete the audit_store 'covers every caller' claim); modules stay import-free of each other. Flip test_ensure_private_dir_exempts_paths_outside_home to a refusal pin; drive the symlinked-home-component and out-of-home probes through the REAL entry points (Store.for_root(...).ensure(), resolve_common_dir-derived _write_once); add the sticky-1777 acceptance, stock-root pass, FAT32-shape refusal, and the missing group-writable acceptance twin in the compat suite; keep the no-absolute-path receipt pin green. Read the plan at docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md (U4, R5/R6/R7, KTD2/KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U4 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U4_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U4 (universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U4),
    { label: "universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U4 } },
  ), { unitId: "U4", maxAttempts: 3 }),
])
const U4_verdicts_chunk_2 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U4 (universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U4),
    { label: "universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U4 } },
  ), { unitId: "U4", maxAttempts: 3 }),
])
const U4_verdicts_chunk_3 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U4 (universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U4),
    { label: "universal fail-closed ancestor walk in outcome_compat + audit_store, entry-point tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U4 } },
  ), { unitId: "U4", maxAttempts: 3 }),
])
U4_verdicts.push(...U4_verdicts_chunk_2, ...U4_verdicts_chunk_3)
const U4_valid_verifier_verdict = (v) => v != null && typeof v === "object" && Array.isArray(v.refuted) && Array.isArray(v.upheld) && typeof v.verifier_identity === "string" && v.verifier_identity.length > 0 && Object.prototype.hasOwnProperty.call(v, "fallback_depth") && typeof v.examined_sha === "string" && v.examined_sha.length > 0
const U4_reported = U4_verdicts.filter((v) => U4_valid_verifier_verdict(v))
const U4_fallback_marker = (() => {
  const depthOf = (v) => {
    const raw = v.fallback_depth
    if (typeof raw === "boolean") return 0
    if (typeof raw === "string" && !/^-?\d+$/.test(raw.trim())) return 0
    const d = Math.trunc(Number(raw))
    return Number.isFinite(d) && d > 0 ? d : 0
  }
  const degraded = U4_reported.filter((v) => depthOf(v) > 0)
  if (degraded.length === 0) return ""
  return " — " + degraded.map((v) => `fallback tier ${depthOf(v)} (${v.verifier_identity || "unknown-verifier"})`).join("; ")
})()
const U4_missing_idx = U4_verdicts.map((v, i) => (!U4_valid_verifier_verdict(v) ? i + 1 : null)).filter((i) => i != null)
const U4_refute_count = U4_reported.filter((v) => v.refuted.length > 0).length
const U4_threshold = Math.max(1, Math.ceil(U4_reported.length / 2))  // majority over reporters
const U4_refuted = U4_refute_count >= U4_threshold
if (U4_missing_idx.length > 0) {
  log(`verify panel over U4: ${U4_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U4_missing_idx.join(", #")}); verdict computed over ${U4_reported.length}/3` +
      (U4_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U4_reported.length < 2) {
  throw new Error(`verifier-under-strength: Unit U4 reported ${U4_reported.length}/3 verifiers (quorum floor 2; missing #${U4_missing_idx.join(', #')})${U4_fallback_marker}`)
}
if (U4_refuted) {
  throw new Error(`verifier-disagreement: Unit U4 refuted by ${U4_refute_count}/${U4_reported.length} reporting verifiers (${U4_missing_idx.length} missing)${U4_fallback_marker}`)
}

// ---- U5: release surfaces saga 0.107.0 + fleet-core 0.17.0, journal entries, codex follow-up draft ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Bump plugins/saga/.claude-plugin/plugin.json to 0.107.0 and plugins/fleet-core/.claude-plugin/plugin.json to 0.17.0, sync .claude-plugin/marketplace.json, write both CHANGELOG entries (refuse-mode admission with the honest seam description, universal fail-closed guard walk with the FAT32/exFAT boundary, DispatcherError arm, halt-record visibility), update the drift-guard version pins in-commit, commit the already-staged DECISIONS entry {#lease-refuse-mode-and-universal-guard-627} (do not duplicate it) and add a LEARNINGS entry if implementation surfaced a non-obvious mechanism, and author docs/sdlc-issue-drafts/2026-07-20-codex-627-refreeze-and-worktree-lease-port.md defining the codex follow-up (outcome_compat byte-faithful re-freeze at the merged SHA with RUNTIME_LABEL sole divergence, audit_store guard re-port, refuse-mode + arm mirroring, port-manifest frozen-range update, inventory rebuild, release surfaces, plus the COR3 outcome_worktrees lease-authority threading port unit re-verified at the merged SHA). Read the plan at docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md (U5, R8, KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces saga 0.107.0 + fleet-core 0.17.0, journal entries, codex follow-up draft", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}}, "required": ["files_changed", "summary"], "type": "object"} },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
