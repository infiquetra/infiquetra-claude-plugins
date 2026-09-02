// ===========================================================================
// deploy-handoff-ack -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "deploy-handoff-ack",
  description: "Issue #395: positive handoff protocol at the saga -> deploy edge \u2014 deploy_handoff.py sidecar (offer/accept/authorize, write-once ack, token rotation), gate-or-auto intent capture as a saga field defaulting to gate, dropped-baton reconcile read, boundary docs on both sides, release surfaces for saga 0.79.0 + deploy 0.2.0. Concurrency shaped to the operator cap of 3: fully serialized U1->U2->U3->U4->U5 \u2014 U1 and U2 carry refute-3 panels (3 verifiers, at cap) that must never overlap a running unit, and U2/U3 both edit deploy_handoff.py + tests/test_handoff_envelope.py so serialization also avoids write conflicts. Panels ride the unit tier (R4) on the two contract-bearing units only: U1 (write-once ack semantics) and U2 (gate-never-silently-auto-fires propagation, edits saga.py).",
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

// ---- U1: deploy_handoff.py module: offer/accept/authorize + envelope schema + tests ----
const U1 = await agent(
  "U1: Create plugins/saga/scripts/deploy_handoff.py (per-saga sidecar .claude/saga/sagas/<saga_id>/deploy_handoff.json per KTD2 with the established sidecar hardening \u2014 saga-id regex guard, wrapped JSONDecodeError, atomic tmp+os.replace writes; offer mints a secrets.token_hex token, writes payload 'gate' as the default in this unit (the saga-record read that derives it is U2's deliverable), and supersedes any prior unacked envelope per KTD4; accept is write-once with named errors for double-accept, accept-without-offer, token mismatch, and empty --by/--evidence; authorize_promotion per KTD5 \u2014 gate blocks, auto authorizes nonprod only, staging/production always confirm; CLI verbs offer/accept/read with all errors caught at the CLI boundary), a thin build_deploy_handoff_envelope() delegator in plugins/saga/scripts/handoff_envelope.py whose existing build_handoff_envelope output stays byte-identical, and the schema/ack sections of tests/test_handoff_envelope.py (test names must contain ack_envelope_schema and ack_round_trip so the issue's -k selectors collect \u2014 KTD7). Read the plan at docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md (U1, R1/R3, KTD1/KTD2/KTD4/KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "deploy_handoff.py module: offer/accept/authorize + envelope schema + tests", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U1_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (deploy_handoff.py module: offer/accept/authorize + envelope schema + tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "deploy_handoff.py module: offer/accept/authorize + envelope schema + tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (deploy_handoff.py module: offer/accept/authorize + envelope schema + tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "deploy_handoff.py module: offer/accept/authorize + envelope schema + tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (deploy_handoff.py module: offer/accept/authorize + envelope schema + tests). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U1),
    { label: "deploy_handoff.py module: offer/accept/authorize + envelope schema + tests verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
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

// ---- U2: gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Add the optional --deploy-autonomy {gate,auto} flag to saga.py save (persisted saga field, carried forward like destination), document the field row and the /plan consumer row in plugins/saga/references/saga-spec.md, add the Phase 5.1 follow-up question (asked only when destination is nonprod-deploy) to plugins/saga/skills/plan/SKILL.md, and make deploy_handoff.py offer read the payload from the saga record per KTD3 via the read_state(root)['sagas'][saga_id] pattern (precedent handoff_envelope.py:57), sourcing deploy_autonomy and pr_refs from the same record \u2014 saga.deploy_autonomy or 'gate', never an offer-time CLI override (R2), absent always reads gate (R5 safe direction), absent pr_refs reads empty. Extend tests/test_handoff_envelope.py with test names containing gate_or_auto_propagation (KTD7): auto authorizes nonprod and still blocks staging/production; gate blocks pending confirmation; absent field defaults gate; the posture comes from the saga record, not an offer argument. Existing saga.py save tests must stay green. Read the plan at docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md (U2, R2/R5, KTD3) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U2 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U2_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "gate-or-auto intent capture: --deploy-autonomy saga field + payload propagation verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
])
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

// ---- U3: ownership gating + dropped-baton reconcile read + tests ----
// depends_on: U1, U2 (barrier)
const U3 = await agent(
  "U3: Add the read-only reconcile verb to plugins/saga/scripts/deploy_handoff.py per KTD6 \u2014 per-saga and --all sweep across .claude/saga/sagas/*/deploy_handoff.json; offer-without-ack derives handed-off-unacknowledged (never deployed/done) naming the saga and offer age; acked reads accepted; no sidecar reads no-handoff (not an error); exit-code convention follows the ship_receipt.py read precedent \u2014 0 for clean or no-handoff, 1 for unacknowledged or error. Extend tests/test_handoff_envelope.py with test names containing ownership_not_released_without_ack and dropped_baton_detected (KTD7): the merged-then-silence scenario surfaces on a reconcile read rather than silently vanishing or reading done. Read the plan at docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md (U3, R4, KTD6) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "ownership gating + dropped-baton reconcile read + tests", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U4: boundary docs on both sides of the edge (saga handoff + deploy acceptance) ----
// depends_on: U1, U2, U3 (barrier)
const U4 = await agent(
  "U4: Document the contract on both sides \u2014 plugins/saga/skills/handoff/SKILL.md gains a Deploy edge section (offer/ack contract, gate-or-auto carriage) beside the existing mission-control boundary language; plugins/deploy/skills/deploy-state/SKILL.md gains an Accepting a saga handoff section (run deploy_handoff.py accept before promoting on behalf of a saga-tracked item; consult authorize_promotion \u2014 a gate payload never auto-fires; AC6 requires grep -n 'ack' on this file to match); plugins/deploy/commands/deploy.md gains the acceptance step in its Instructions; plugins/saga/skills/work/SKILL.md gains ONLY a one-line routing pointer to the offer step \u2014 the Hard boundary section's substantive language must be preserved verbatim (AC7/R7, verify with git diff on that section). No Python changes in this unit. Read the plan at docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md (U4, R6/R7) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "boundary docs on both sides of the edge (saga handoff + deploy acceptance)", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}}, "required": ["files_changed", "summary"], "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U5: release surfaces: saga 0.79.0 + deploy 0.2.0, marketplace, changelogs, drift pins ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Bump plugins/saga/.claude-plugin/plugin.json to 0.79.0 and plugins/deploy/.claude-plugin/plugin.json to 0.2.0, sync both entries in .claude-plugin/marketplace.json, add the [0.79.0] saga CHANGELOG entry (deploy handoff-ack envelope, --deploy-autonomy intent field, dropped-baton reconcile) and the [0.2.0] deploy CHANGELOG entry (acceptance/ack step, gate-or-auto consumption), and update the drift-guard pins in tests/test_saga_plugin.py (0.78.0 -> 0.79.0) and tests/test_deploy_plugin.py (0.1.4 -> 0.2.0, line 42). The DECISIONS entry {#deploy-handoff-ack-sidecar-395} is already staged in the working tree \u2014 do not duplicate it; add a LEARNINGS entry only if implementation surfaced a non-obvious mechanism. Read the plan at docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md (U5) as your authoritative spec.\n\nBUDGET DISCIPLINE (cheap-tier): you run on a small output budget. (1) CAP OUTPUT -- be terse; no human-facing prose, no recaps of files you read. (2) MANDATORY EMIT -- your FINAL message MUST be the JSON return object (see the RETURN CONTRACT); never end the turn without it, even if the work is partial (return what you have + a note). (3) SKIM, don't read -- open only the exact lines you need, never whole large files. (4) BATCH -- issue independent tool calls in one parallel block, not serially.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).\n\nPULL-CORD (#364, overrides the return contract above when it applies): if you judge this task is genuinely beyond your depth -- not merely hard, but you cannot produce a substantively correct result at your tier -- emit ONLY {\"pull_cord\": \"<one-line reason>\"} as your final message instead of the return contract. The coordinator batches every pulled cord into ONE escalation ask; your unit is never marked complete. Never pull the cord for partial-but-sound work (use the return contract with a note instead).",
  { label: "release surfaces: saga 0.79.0 + deploy 0.2.0, marketplace, changelogs, drift pins", model: "haiku", effort: "low", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "pull_cord": {"type": "string"}, "summary": {}}, "type": "object"} },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "haiku/low -> haiku/medium (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
