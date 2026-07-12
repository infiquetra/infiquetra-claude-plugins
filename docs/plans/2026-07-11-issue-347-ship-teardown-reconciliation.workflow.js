// ===========================================================================
// ship-teardown-reconciliation -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "ship-teardown-reconciliation",
  description: "Issue #347: teardown as the ship ceremony's terminal gate \u2014 opened-resource manifest + reality-checked closing count (ship_teardown.py), immutable receipt (ship_receipt.py), certificate-gated merged-worktree reclaim with --if-idle, wired as the non-skippable terminal 'teardown' transition; release surfaces follow. Concurrency shaped to the operator cap of 3: U2 waits behind U1 (receipt embeds the reconcile report), U3 waits behind U1 AND U2 so its refute-3 panel (3 verifiers, at cap) never overlaps a running unit, U4's panel likewise runs alone; U5 is a lone haiku closer. Panels ride the unit tier (R4) on the two risky units only: U3 (removes worktrees \u2014 destructive semantics under the certificate) and U4 (wiring inside the #526-gated run() path, appends a transition to the canonical table).",
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

// ---- U1: ship_teardown.py manifest + reality-checked closing count + tests ----
const U1 = await agent(
  "U1: Create plugins/saga/scripts/ship_teardown.py (per-saga sidecar .claude/saga/sagas/<saga_id>/opened_resources.json per KTD2 with the #346 hardening \u2014 saga-id traversal guard, wrapped JSONDecodeError, atomic tmp+os.replace writes; register/close/read; reconcile() deriving the closing count with per-kind reality probes per KTD4, closed-but-alive entries flagged as discrepancies that count open; read-only 'reconcile' CLI verb printing CLEAN or HALT + named blockers) and the manifest/reconcile sections of tests/test_ship_teardown_reconciliation.py (test names follow test_AC_<n>_<scenario>). Read the plan at docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md (U1, R1/R2/R5, KTD2/KTD4) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "ship_teardown.py manifest + reality-checked closing count + tests", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U2: ship_receipt.py immutable writer/reader + tests ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Create plugins/saga/scripts/ship_receipt.py (mint() refusing on a non-zero closing count and creating .claude/saga/sagas/<saga_id>/ship_receipt.json via O_CREAT|O_EXCL then chmod 0444 per KTD5; ReceiptExistsError on re-mint; read() validates schema, never writes, and surfaces a named anomaly when recorded entries contradict a fresh reality probe) and the receipt section of tests/test_ship_teardown_reconciliation.py (AC3: mint-once, in-place mutation raises, receipt records every opened resource and its closed state; mint against non-zero count creates NO file). Read the plan at docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md (U2, R4, KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "ship_receipt.py immutable writer/reader + tests", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U3: reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook ----
// depends_on: U1, U2 (barrier)
const U3 = await agent(
  "U3: Add the reclaim subcommand to plugins/saga/scripts/ship_teardown.py (sweep git worktree list --porcelain excluding the primary and the worktree it runs in per KTD6; skip dirty trees and unmerged heads with a report line; merged-ness via git merge-base --is-ancestor; removals require reversibility_certificate.authorize_write(WORKTREE_RECLAIM_MERGED) == AUTHORIZED per KTD7 \u2014 add that OpKind + OpFacts entry additively WITH its inverse descriptor (tests/test_reversibility_certificate.py's test_every_reversible_op_kind_has_registered_inverse iterates the registry); .saga-worktrees registry paths route through outcome_worktrees.reap_worktree; failed removals are kept and reported, never silently dropped; --if-idle <duration> no-ops while sidecar/registry mtimes are fresh AND applies the same bound per candidate worktree per KTD8 \u2014 a merged+clean worktree with recent activity is skipped in idle mode, the sibling-session guard), one additive SessionStart entry in plugins/saga/hooks/hooks.json invoking reclaim --if-idle 24h --quiet, and the reclaim section of tests/test_ship_teardown_reconciliation.py using real-git bare-origin fixtures (AC5 merged-vs-unmerged; certificate GATE monkeypatch removes nothing; dirty skip; recent-activity skip in idle mode; registry deregister; --if-idle fresh/aged). Existing tests/test_outcome_worktrees.py must stay green. Read the plan at docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md (U3, R6/R7, KTD6/KTD7/KTD8) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U3 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U3_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U3 (reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U3),
    { label: "reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U3 } },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U3 (reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U3),
    { label: "reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U3 } },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U3 (reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U3),
    { label: "reclaim subcommand: porcelain sweep, certificate gate, --if-idle + hook verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U3 } },
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

// ---- U4: ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint ----
// depends_on: U1, U2, U3 (barrier)
const U4 = await agent(
  "U4: Wire teardown into plugins/saga/scripts/ship_ceremony.py \u2014 append 'teardown' to TRANSITIONS and TRANSITION_TIERS (tier reversible, KTD3); _do_teardown in _RUNNERS runs reconcile with reality probes, attempts authorized closes for still-open ceremony-owned entries, re-reconciles, raises TeardownBlockedError naming every blocker BEFORE ship_undo.append_entry and the saga.py save on non-zero count (ledger provably unadvanced), and mints the receipt via ship_receipt on zero; register-on-open wiring per KTD9 (start() registers branch + draft PR, _do_open_pr registers the PR it creates, _do_merge closes the draft_pr entry, _do_branch_delete closes the branch entry); ship_undo gets a forward-only no-op handler for the teardown transition so undo never crashes on it. Extend tests: AC1 blocks_on_nonzero_closing_count, AC2 dry_run_halt_on_surviving_worktree, AC6 terminal_transition_not_skippable (TRANSITIONS[-1], next_transition('branch_delete'), seeded remote-delete-failed partial path), happy-path receipt mint + 'already shipped', pre-0.78.0 compat (saga at branch_delete reports teardown pending), undo no-op, and per-call-site register/close oracles; existing test_ship_ceremony.py assertions that end at branch_delete are updated deliberately. Read the plan at docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md (U4, R3/R4, KTD3/KTD9) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U4 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U4_verdicts = await parallel([
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U4 (ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U4),
    { label: "ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U4 } },
  ), { unitId: "U4", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U4 (ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U4),
    { label: "ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U4 } },
  ), { unitId: "U4", maxAttempts: 3 }),
  () => __retry(() => agent(
    __verifierPrompt("REFUTE-N VERIFIER over unit U4 (ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}.\n\nEcho verifier_identity: saga:readonly-verifier and fallback_depth: 0 back in your verdict (do NOT alter them). Include examined_sha as the git SHA you actually materialized or inspected.", U4),
    { label: "ship_ceremony.py wiring: terminal teardown transition + register-on-open + receipt mint verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", schema: {"additionalProperties": true, "properties": {"examined_sha": {"type": "string"}, "fallback_depth": {}, "refuted": {"type": "array"}, "upheld": {"type": "array"}, "verifier_identity": {"type": "string"}}, "required": ["refuted", "upheld", "verifier_identity", "fallback_depth", "examined_sha"], "type": "object"}, input: { unit_result: U4 } },
  ), { unitId: "U4", maxAttempts: 3 }),
])
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

// ---- U5: release surfaces + journal (0.78.0) ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Bump plugins/saga/.claude-plugin/plugin.json to 0.78.0, sync the saga entry in .claude-plugin/marketplace.json, add the [0.78.0] CHANGELOG entry (opened-resource manifest, closing-count teardown gate, immutable ship receipt, certificate-gated reclaim with --if-idle; call out that pre-0.78.0 ceremonies sitting at branch_delete regain one pending teardown transition), and update the drift-guard pin in tests/test_saga_plugin.py. The DECISIONS entry {#ship-teardown-terminal-gate-347} is already staged in the working tree \u2014 do not duplicate it; add a LEARNINGS entry only if implementation surfaced a non-obvious mechanism. Read the plan at docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md (U5, R8) as your authoritative spec.\n\nBUDGET DISCIPLINE (cheap-tier): you run on a small output budget. (1) CAP OUTPUT -- be terse; no human-facing prose, no recaps of files you read. (2) MANDATORY EMIT -- your FINAL message MUST be the JSON return object (see the RETURN CONTRACT); never end the turn without it, even if the work is partial (return what you have + a note). (3) SKIM, don't read -- open only the exact lines you need, never whole large files. (4) BATCH -- issue independent tool calls in one parallel block, not serially.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).\n\nPULL-CORD (#364, overrides the return contract above when it applies): if you judge this task is genuinely beyond your depth -- not merely hard, but you cannot produce a substantively correct result at your tier -- emit ONLY {\"pull_cord\": \"<one-line reason>\"} as your final message instead of the return contract. The coordinator batches every pulled cord into ONE escalation ask; your unit is never marked complete. Never pull the cord for partial-but-sound work (use the return contract with a note instead).",
  { label: "release surfaces + journal (0.78.0)", model: "haiku", effort: "low", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "pull_cord": {"type": "string"}, "summary": {}}, "type": "object"} },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "haiku/low -> haiku/medium (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
