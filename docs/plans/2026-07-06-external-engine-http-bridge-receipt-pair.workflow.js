// ===========================================================================
// external-engine-http-bridge-receipt-pair -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "external-engine-http-bridge-receipt-pair",
  description: "Issues #387 + #383 (keystone pair, one PR): generic OpenAI-compatible HTTP bridge (cloud-first: Ollama Cloud + DeepSeek registry rows, use-time selectable) receipt-proven from day one via bridge_receipt.v1 in fleet-commons, receipt-gated Disposition.UNPROVEN, receipt_emitter required registry key, forcing-function-verified drift guard. SERIALIZED unit chain (every unit depends_on its predecessor) deliberately: operator rate-limit cap is max 3 concurrent non-haiku agents / 6 haiku; the only parallelism is the n=3 verify panels on U5/U6/U7, so peak concurrency is exactly 3 by construction (precedent: 2026-07-05 effort-first-class spec, serialized for the same reason). Serialization also prevents concurrent edits to the shared working tree and shared test files (tests/test_saga_engine_dispatch.py touched by three units).",
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

// ---- U1: bridge_receipt.v1 schema module in fleet-commons ----
const U1 = await agent(
  "U1: Create plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py \u2014 bridge_receipt.v1 schema constants, emit_receipt(...) builder, validate_receipt(dict) -> list[str] (empty = valid), with the transport-discriminated runner section (cli: pid/argv/exit_code; http: url/status_code/model) plus common core (schema, engine_id, variant, transport, wall_time_s, bytes_produced). Add tests/test_bridge_receipt.py per the unit's test scenarios. Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U1, R7, KTD6/KTD7) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "bridge_receipt.v1 schema module in fleet-commons", model: "sonnet", effort: "high" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// ---- U3: registry: transport field, http validation, receipt_emitter required, two cloud rows ----
// depends_on: U1 (barrier)
const U3 = await agent(
  "U3: In plugins/saga/scripts/engine_registry.py add EngineEntry.transport (closed vocab cli|http, default cli), http-conditional required invocation fields (base_url, model, auth.mode, auth.key_env when bearer, explicit effort), and receipt_emitter as a required key on EVERY row. Update plugins/saga/references/engine-registry.yaml: receipt_emitter on the four existing rows (codex rows -> codex-bridge, agy rows -> agy-delegate), new ollama-cloud and deepseek transport=http rows with conservative (<= MODERATE) seed ratings and cost_speed_rank 5-6. VERIFY base URLs and wire model ids against provider docs before authoring the rows \u2014 do not trust memory. Extend tests/test_saga_engine_registry.py including the by_capability routing-stability regression (winners unchanged for every capability). Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U3, R9/R11, KTD2/KTD3/KTD9) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "registry: transport field, http validation, receipt_emitter required, two cloud rows", model: "sonnet", effort: "high" },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// ---- U4: transport-aware preflight + run-scoped RunMemo ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: In plugins/saga/scripts/engine_resolver.py make preflight transport-aware (cli keeps shutil.which + config checks; http checks the auth key env var presence, NO live network) and add the opt-in run-scoped RunMemo object threaded through resolve/resolve_role/_resolve_entry/preflight (keys: engine_id for preflight, (capability, token_estimate) for resolution; memo=None is byte-identical to today). Extend tests/test_saga_engine_resolver.py and add the call-counting resolve_memoization cases (10 resolves -> 1 probe) to tests/test_saga_engine_dispatch.py. Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U4, R5/R11, KTD4/KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "transport-aware preflight + run-scoped RunMemo", model: "sonnet", effort: "medium" },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U5: OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Create plugins/saga/scripts/engine_bridge_http.py \u2014 a Runner-contract (dict -> dict) OpenAI chat/completions bridge driven entirely by registry row invocation data (base_url, model, auth), stdlib urllib.request, returning {status, output, tokens, latency_seconds, receipt} with a schema-valid http bridge_receipt.v1; bearer header present iff auth.mode bearer and NEVER logged or echoed into evidence/receipts (env var name at most, never the value). In plugins/saga/scripts/engine_dispatch.py add the transport-keyed branch to _build_invocation (http -> generic row-driven invocation with byte-preserved payload; cli arm unchanged), add the AdvisoryEvidence.runner_receipt field (dict | None = None, additive \u2014 the field lands in THIS unit), and thread result['receipt'] into it in dispatch(). SECRET LIFECYCLE: resolve the API key from auth.key_env only at request-build time inside the bridge \u2014 never into the invocation dict (it flows to run-ledger facts), the receipt, evidence, or logs; env var NAME at most. Add tests/test_engine_bridge_http.py with the shared FakeHttpRunner fixture, dispatch-equivalence parametrized over Ollama-Cloud-shaped and DeepSeek-shaped rows, dead-adapter red / conformant green contract cases, failure-status mapping (HTTP error/timeout/malformed never fabricate ok), and the availability-gated Ollama Cloud smoke (skip, never fail, without OLLAMA_API_KEY). Keep the issue-named selectors transport_http_bridge working. Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U5, R1/R2/R3/R4, KTD1/KTD10) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch", model: "opus", effort: "high" },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U5 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U5_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "OpenAI-compatible HTTP bridge + transport-keyed adapter dispatch verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
])
const U5_reported = U5_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U5_missing_idx = U5_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U5_refute_count = U5_reported.filter((v) => v.refuted.length > 0).length
const U5_threshold = Math.max(1, Math.ceil(U5_reported.length / 2))  // majority over reporters
const U5_refuted = U5_refute_count >= U5_threshold
if (U5_missing_idx.length > 0) {
  log(`verify panel over U5: ${U5_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U5_missing_idx.join(", #")}); verdict computed over ${U5_reported.length}/3` +
      (U5_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U5_refuted) {
  throw new Error(`verifier-disagreement: Unit U5 refuted by ${U5_refute_count}/${U5_reported.length} reporting verifiers (${U5_missing_idx.length} missing)`)
}

// ---- U6: receipt-gated disposition + never-gatekeeper structural guard ----
// depends_on: U5 (barrier)
const U6 = await agent(
  "U6: Add Disposition.UNPROVEN ('unproven') in plugins/saga/scripts/provenance_manifest.py; build_dispatch_manifest in plugins/saga/scripts/engine_dispatch.py assigns RAN_AS_REQUESTED only with a schema-valid receipt on the runner_receipt field U5 added (validate via fleet_commons bridge_receipt), else UNPROVEN with a note naming what was missing; halted evidence keeps FELL_BACK_TO_CLAUDE. Add the structural never-gatekeeper rejection: a runner result carrying gate/verdict keys (verdict, gate_status, adjudicated) raises DispatchError. Extend tests/test_saga_engine_dispatch.py (selectors fabricated_evidence_no_receipt, never_gatekeeper_guard) and update every existing test asserting RAN_AS_REQUESTED to supply a valid receipt \u2014 each flip is deliberate, not collateral. Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U6, R6/R8, KTD8) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "receipt-gated disposition + never-gatekeeper structural guard", model: "sonnet", effort: "high" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U6 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U6_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (receipt-gated disposition + never-gatekeeper structural guard). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "receipt-gated disposition + never-gatekeeper structural guard verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (receipt-gated disposition + never-gatekeeper structural guard). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "receipt-gated disposition + never-gatekeeper structural guard verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (receipt-gated disposition + never-gatekeeper structural guard). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "receipt-gated disposition + never-gatekeeper structural guard verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
])
const U6_reported = U6_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U6_missing_idx = U6_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U6_refute_count = U6_reported.filter((v) => v.refuted.length > 0).length
const U6_threshold = Math.max(1, Math.ceil(U6_reported.length / 2))  // majority over reporters
const U6_refuted = U6_refute_count >= U6_threshold
if (U6_missing_idx.length > 0) {
  log(`verify panel over U6: ${U6_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U6_missing_idx.join(", #")}); verdict computed over ${U6_reported.length}/3` +
      (U6_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U6_refuted) {
  throw new Error(`verifier-disagreement: Unit U6 refuted by ${U6_refute_count}/${U6_reported.length} reporting verifiers (${U6_missing_idx.length} missing)`)
}

// ---- U2: agy delegate emits the shared receipt (vendored shim) ----
// depends_on: U6 (barrier)
const U2 = await agent(
  "U2: Vendor plugins/fleet-core/scripts/fleet_commons_shim.py byte-identically into plugins/agy/scripts/, extend the hardcoded vendored-copy list at tests/test_fleet_commons_resolution.py:28-29 with the agy copy, and map SupervisedRunResult (pid, argv, return_code, stdout_bytes, started/ended \u2014 already captured at plugins/agy/scripts/agy_delegate.py:660-790) through the shared emit_receipt into the delegate's result envelope. Launch-failure paths (agy missing, OSError) emit NO receipt and the envelope still validates. Extend tests/test_agy_delegate_contract.py. Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U2, R7, KTD6) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "agy delegate emits the shared receipt (vendored shim)", model: "sonnet", effort: "medium" },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U7: bridge-enumeration drift guard, forcing-function verified ----
// depends_on: U2 (barrier)
const U7 = await agent(
  "U7: Create tests/test_bridge_receipt_drift.py \u2014 enumerate registry receipt_emitter values; every in-repo emitter (http-bridge, agy-delegate) provably emits through the shared path; PENDING_EMITTERS = {'codex-bridge': '#476'} as an explicit dated entry that reds if plugins/codex/ appears without emit wiring. ALL red conditions must be hermetic \u2014 filesystem and registry state only, NO network or GitHub-issue-state checks inside tests. Commit forcing-function red tests: the guard reds when the emit call is stubbed out of one emitter, and the matcher is probed against a realistic evasion (aliased import / renamed local). Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U7, R10, KTD9; journal {#verify-the-guard-reds}) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "bridge-enumeration drift guard, forcing-function verified", model: "opus", effort: "high" },
)
__gate(U7, { unitId: "U7", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U7 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U7_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U7 (bridge-enumeration drift guard, forcing-function verified). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "bridge-enumeration drift guard, forcing-function verified verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U7 },
  ), { unitId: "U7", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U7 (bridge-enumeration drift guard, forcing-function verified). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "bridge-enumeration drift guard, forcing-function verified verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U7 },
  ), { unitId: "U7", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U7 (bridge-enumeration drift guard, forcing-function verified). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "bridge-enumeration drift guard, forcing-function verified verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U7 },
  ), { unitId: "U7", maxAttempts: 3 }),
])
const U7_reported = U7_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U7_missing_idx = U7_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U7_refute_count = U7_reported.filter((v) => v.refuted.length > 0).length
const U7_threshold = Math.max(1, Math.ceil(U7_reported.length / 2))  // majority over reporters
const U7_refuted = U7_refute_count >= U7_threshold
if (U7_missing_idx.length > 0) {
  log(`verify panel over U7: ${U7_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U7_missing_idx.join(", #")}); verdict computed over ${U7_reported.length}/3` +
      (U7_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U7_refuted) {
  throw new Error(`verifier-disagreement: Unit U7 refuted by ${U7_refute_count}/${U7_reported.length} reporting verifiers (${U7_missing_idx.length} missing)`)
}

// ---- U8: release surfaces, contract doc, journal + queued proposals ----
// depends_on: U7 (barrier)
const U8 = await agent(
  "U8: Bump plugins/saga, plugins/agy, plugins/fleet-core, AND plugins/team-execution plugin.json versions (team-execution's external-engine-workers.md reference is user-facing guidance \u2014 same-PR release-surface rule applies); mirror .claude-plugin/marketplace.json for all four; CHANGELOG entries for all four; new plugins/saga/references/dispatch-adapter-contract.md; pointer update in plugins/team-execution/skills/team-execution/references/external-engine-workers.md; DECISIONS.md entry (KTD1/KTD3/KTD6/KTD8/KTD9 with rejected alternatives + revisit-whens); QUEUED.md: (a) execution_spec emitter concurrency cap \u2014 spec-level concurrency {default: 3, cheap: 6} field emitting a bounded pool, replacing serialize-by-construction (operator rate-limit discipline, 2026-07-04 incident); (b) recommend_execution_backend has no reachable cc-workflows-ultracode path for security-touching code >= 8 files (size trigger ORs past the gated/advisory answer AND elevated_risk suppresses ultracode) \u2014 revisit the suppressor so backend choice is decoupled from gate existence. Confirm metadata drift-guard tests green. Read the plan at docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md (U8, R12) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces, contract doc, journal + queued proposals", model: "sonnet", effort: "medium" },
)
__gate(U8, { unitId: "U8", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
