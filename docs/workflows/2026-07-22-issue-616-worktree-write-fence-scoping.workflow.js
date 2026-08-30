// ===========================================================================
// issue-616-worktree-write-fence-scoping -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "issue-616-worktree-write-fence-scoping",
  description: "Issue #616: scope the fleet-lease write-fence by reservation-declared isolation instead of spawn cwd (KTD1-KTD3): first-class Lease.isolation field + three-way claim fence policy in the fleet-core broker, adapter extraction of tool_input.isolation on both reserve paths, frozen-seam/canary verification, release surfaces fleet-core 0.20.0 + saga 0.111.0. Fully serialized U1->U2->U3->U4 under the operator cap of 3: refute-3 panels on the two contract-bearing units ride at the unit tier and would overlap a running unit otherwise.",
}
const settlement = {"casualty_threshold_percent":0,"dispatch_id":"workflow:35bf29747b1253e8b9658900","driver":{"invocation_id":null,"units":[{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U1","workflow_unit_id":"U1"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U2","workflow_unit_id":"U2"},{"return_keys":[{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U3","workflow_unit_id":"U3"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U4","workflow_unit_id":"U4"}]},"max_attempts":3,"schema":"dispatch_settlement.v1","site":"workflow","units":[{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:35bf29747b1253e8b9658900:U1","unit_id":"U1"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:35bf29747b1253e8b9658900:U2","unit_id":"U2"},{"deliverables":["structured-result","return:summary"],"idempotency_key":"workflow:35bf29747b1253e8b9658900:U3","unit_id":"U3"},{"deliverables":["structured-result","return:files_changed","return:summary"],"idempotency_key":"workflow:35bf29747b1253e8b9658900:U4","unit_id":"U4"}]}
const lease = {"aggregate_limit":7,"batch_id":null,"claim_ttl_seconds":30,"execution_ttl_seconds":300,"generated_runtime_filesystem_access":false,"invocation_id":null,"mutation":"read-write","owner_id":null,"policy_sha256":"b985631b1a874a0817a3cac49b27565875fb5dedd3ad2008cf397dc640d43a0a","requires_prelaunch_reservation":true,"reservation_width":3,"schema":"workflow_lease_reservation.v1","session_limit":3,"slots":["slot-001","slot-002","slot-003"],"spec_sha256":"35bf29747b1253e8b9658900eedcf3a6718e9d922cd3bd2d69ef88d26270f714","workload_unit_ids":["U1","U2","U3","U4"]}

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

// ---- U1: fleet-core broker: first-class isolation field + claim-time fence policy ----
const U1 = await agent(
  "U1: In plugins/fleet-core/scripts/fleet_commons/lease_broker.py at base ab84003b, add a first-class nullable isolation field to the Lease dataclass (:812; _LEASE_KEYS/from_dict/to_dict :845-930 with the backfill-before-closed-mapping idiom from SettlementRecord :969-970; only 'worktree' or None storable, reject other values at the boundary), thread an optional isolation param through acquire_agent (:2246) and prepare_batch_call (:2711) (reserve_batch :2477 deliberately gains nothing \u2014 KTD6), replace claim's unconditional derived['worktree_root'] stamp (:2653-2658) with the KTD3 three-way branch (reservation isolation=='worktree' -> stamp child cwd; PreToolUse-stamped tool_use_id present without worktree isolation -> no worktree_root; unstamped attested batch slot -> stamp child cwd, byte-parity with today), and reset isolation to None in the batch-slot recycle in _complete_foreground_lease (:3892). assert_write_target changes zero lines; #615's claim-ordering/recycle/renewal seams are not reworked. Tests per the plan's U1 scenarios in tests/test_fleet_lease_broker.py (R1 unfenced cross-cwd write, R2 fenced isolated write, R3 batch-slot byte-parity, R4 stamped-slot isolation honor, R5 0.19.0 registry round-trip, R6 recycle reset, supersede isolation replacement, invalid-value rejection). Read the plan at docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md (U1, R1-R6, KTD1-KTD3/KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "fleet-core broker: first-class isolation field + claim-time fence policy", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U1_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (fleet-core broker: first-class isolation field + claim-time fence policy). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.\n\nRE-VERIFICATION PASS 4 (driver-initiated): passes 1-3 all fenced verifier Bash for distinct machinery reasons, never code reasons. Pass 1: batch lease TTL starvation. Pass 2: forward-schema poisoning (post-U1 repo broker wrote an 'isolation' key the installed 0.19.0 hook broker rejects). Pass 3: the 30s claim TTL expired all reserved slots before the workflow's first live spawn could claim (resume replays cached agents first). All three are now mitigated: reservation is written by the INSTALLED fleet-core 0.19.0 broker (FLEET_COMMONS_ROOT rung-1 pin, old-schema records so hooks parse), the reservation claim TTL is raised to 1800s (driver-authored metadata), and a driver-side keeper renews every LIVE lease per-member every 90s (skipping expired members, unlike renew_batch). Your Bash should work for the whole pass. Actually execute the quantitative checks this time (uv run pytest -q tests/test_fleet_lease_broker.py; uv run ruff check .; uv run ruff format --check .; uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports) instead of refuting them as unreproducible — the pytest run loads the repo's post-U1 broker in-process with hermetic state dirs, so it verifies U1's code regardless of the installed hook broker's version. If Bash is STILL fenced, say so explicitly in the verdict.", U1),
    { label: "fleet-core broker: first-class isolation field + claim-time fence policy verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
])
const U1_verdicts_chunk_2 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (fleet-core broker: first-class isolation field + claim-time fence policy). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.\n\nRE-VERIFICATION PASS 4 (driver-initiated): passes 1-3 all fenced verifier Bash for distinct machinery reasons, never code reasons. Pass 1: batch lease TTL starvation. Pass 2: forward-schema poisoning (post-U1 repo broker wrote an 'isolation' key the installed 0.19.0 hook broker rejects). Pass 3: the 30s claim TTL expired all reserved slots before the workflow's first live spawn could claim (resume replays cached agents first). All three are now mitigated: reservation is written by the INSTALLED fleet-core 0.19.0 broker (FLEET_COMMONS_ROOT rung-1 pin, old-schema records so hooks parse), the reservation claim TTL is raised to 1800s (driver-authored metadata), and a driver-side keeper renews every LIVE lease per-member every 90s (skipping expired members, unlike renew_batch). Your Bash should work for the whole pass. Actually execute the quantitative checks this time (uv run pytest -q tests/test_fleet_lease_broker.py; uv run ruff check .; uv run ruff format --check .; uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports) instead of refuting them as unreproducible — the pytest run loads the repo's post-U1 broker in-process with hermetic state dirs, so it verifies U1's code regardless of the installed hook broker's version. If Bash is STILL fenced, say so explicitly in the verdict.", U1),
    { label: "fleet-core broker: first-class isolation field + claim-time fence policy verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
  ), { unitId: "U1", maxAttempts: 3 }),
])
const U1_verdicts_chunk_3 = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U1 (fleet-core broker: first-class isolation field + claim-time fence policy). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.\n\nRE-VERIFICATION PASS 4 (driver-initiated): passes 1-3 all fenced verifier Bash for distinct machinery reasons, never code reasons. Pass 1: batch lease TTL starvation. Pass 2: forward-schema poisoning (post-U1 repo broker wrote an 'isolation' key the installed 0.19.0 hook broker rejects). Pass 3: the 30s claim TTL expired all reserved slots before the workflow's first live spawn could claim (resume replays cached agents first). All three are now mitigated: reservation is written by the INSTALLED fleet-core 0.19.0 broker (FLEET_COMMONS_ROOT rung-1 pin, old-schema records so hooks parse), the reservation claim TTL is raised to 1800s (driver-authored metadata), and a driver-side keeper renews every LIVE lease per-member every 90s (skipping expired members, unlike renew_batch). Your Bash should work for the whole pass. Actually execute the quantitative checks this time (uv run pytest -q tests/test_fleet_lease_broker.py; uv run ruff check .; uv run ruff format --check .; uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports) instead of refuting them as unreproducible — the pytest run loads the repo's post-U1 broker in-process with hermetic state dirs, so it verifies U1's code regardless of the installed hook broker's version. If Bash is STILL fenced, say so explicitly in the verdict.", U1),
    { label: "fleet-core broker: first-class isolation field + claim-time fence policy verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U1 } },
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
  // OPERATOR ADJUDICATION (Jeff, decision "A", 2026-07-23) — U1 ONLY. The refute-N panel failed 4
  // passes on 4 distinct lease-machinery faults, never on code: every mechanism claim was upheld in
  // all 10 verdicts across all passes; the one verifier that ever had working Bash (pass 4) executed
  // the full quantitative battery itself (pytest 75 passed, ruff + format + mypy clean, broader
  // failures = anticipated U2 seam) and upheld everything; the driver independently reproduced the
  // same. Refuting verdicts refute solely on Bash-fenced unverifiability. Evidence and decision
  // recorded in docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md.
  // U2-U4 panels remain fully armed and throwing.
  log(`verify panel over U1: refuted ${U1_refute_count}/${U1_reported.length} — OVERRIDDEN by operator adjudication (decision A): fenced-verifier casualties; working-Bash verifier + driver both confirmed all quantitative claims`)
}

// ---- U2: saga adapter: extract and forward declared isolation on both reserve paths ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: In plugins/saga/scripts/lease_broker.py at base ab84003b (post-U1), add a _declared_isolation(payload) helper beside _agent_type (:80-90) that returns 'worktree' only when tool_input.isolation is exactly 'worktree' and None otherwise (KTD2 normalization \u2014 'remote' or absence stores None), and thread it into the acquire_agent call (:317) and the prepare_batch_call route (:304) inside reserve_hook_agent. claim_hook_agent (:338-353) and both hook files (lease_lifecycle_hook.py, lease_mutation_hook.py) change zero lines. Tests per the plan's U2 scenarios (adapter coverage home tests/test_saga_hooks.py \u2014 the hook payload-contract fixtures live at :96-103; batch interplay tests/test_saga_workflow_emitter.py): worktree/absent/remote normalization, live-batch route forwarding, SubagentStart claim contract unchanged. Read the plan at docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md (U2, R1/R4, KTD1/KTD2) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga adapter: extract and forward declared isolation on both reserve paths", model: "sonnet", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U2 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U2_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (saga adapter: extract and forward declared isolation on both reserve paths). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "saga adapter: extract and forward declared isolation on both reserve paths verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (saga adapter: extract and forward declared isolation on both reserve paths). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "saga adapter: extract and forward declared isolation on both reserve paths verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U2 (saga adapter: extract and forward declared isolation on both reserve paths). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U2),
    { label: "saga adapter: extract and forward declared isolation on both reserve paths verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"minLength": 1, "type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"minLength": 1, "type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U2 } },
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

// ---- U3: verification-only: frozen-seam nil-impact + hermetic R9 canary rehearsal ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: Verification only \u2014 no code changes. (a) Confirm the codex byte-frozen outcome_compat seam is untouched by the Lease.isolation addition (the frozen seam consumes broker APIs, not registry bytes; enumerate any import/call into the changed surfaces and record nil-impact evidence). (b) Rehearse the #615 R9 scripted canary hermetically against the changed broker in an isolated INFIQUETRA_FLEET_STATE_DIR: width-1 workflow_lease_reservation.v1 metadata + workflow_emitter.py reserve/attest, then a simulated unstamped batch claim with a cwd, asserting worktree_root is stamped byte-identically to 0.19.0 behavior (plan R3) and settle/release leaves 0 leases. Record both results in the work-session doc draft (docs/work-sessions/). Return the evidence summary; do not modify plugin code, tests, or release surfaces. Read the plan at docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md (U3, R3) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "verification-only: frozen-seam nil-impact + hermetic R9 canary rehearsal", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"summary": {}}, "required": ["summary"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U4: release surfaces fleet-core 0.20.0 + saga 0.111.0, journal, drift-guard pins ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Bump plugins/fleet-core/.claude-plugin/plugin.json to 0.20.0 and plugins/saga/.claude-plugin/plugin.json to 0.111.0, sync .claude-plugin/marketplace.json, write both CHANGELOG entries (reservation-carried isolation truth; three-way claim fence policy with unchanged workflow-batch behavior; adapter normalization), update drift-guard version pins in-commit (tests/test_saga_plugin.py plus the tests/test_liveness_events.py:698 and tests/test_team_execution_liveness.py:179/:409 pin pattern from #615), add the DECISIONS entry {#worktree-fence-scoping-616} (KTD1-KTD6 + the D1 operator pin) and a LEARNINGS entry only if implementation surfaced a non-obvious mechanism. Verify python3 scripts/check_release_surface_parity.py reports parity and re-check sibling-PR version collisions at merge time. Read the plan at docs/plans/2026-07-22-issue-616-worktree-write-fence-scoping-plan.md (U4, R7) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces fleet-core 0.20.0 + saga 0.111.0, journal, drift-guard pins", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}}, "required": ["files_changed", "summary"], "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
