// ===========================================================================
// delegation-tripwires -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "delegation-tripwires",
  description: "Issue #384: runtime delegation tripwires \u2014 engine-parametrized fleet-core auditor (agy's classify_transcript untouched, fixture-parity pinned), arm/disarm delegation-state protocol, saga PreToolUse block hook (Write|Edit|MultiEdit|NotebookEdit, armed-unproven only, fail-open), saga Stop/SubagentStop audit hook (hard-block exit 2, stop_hook_active loop guard), dispatch-layer two-signal acceptance with DELEGATION_INTEGRITY disposition and re-queue-once-then-HALT, chaperone contract doc, release surfaces across fleet-core/saga/team-execution. SERIALIZED unit chain (every unit depends_on its predecessor) deliberately: operator rate-limit cap is max 3 concurrent non-haiku agents; the only parallelism is the n=3 verify panels on U1/U3/U4/U5, so peak concurrency is exactly 3 by construction (precedent: #476 and http-bridge-receipt-pair specs). Serialization also prevents concurrent edits to plugins/saga/hooks/hooks.json (U3/U4) and tests/test_delegation_tripwire.py (U3/U4/U5/U6). WAVE-A GUARDRAIL (journal {#verify-panels-blind-to-uncommitted-tree}): every worker commits its completed unit on the branch so verify-panel worktrees (cut from main) can materialize committed state; verifier prompts must include mandatory branch materialization (git checkout <branch> -- .) + examined-sha quoting \u2014 verify the emitter includes this or patch post-emit.",
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

// ---- U1: fleet-core delegation_audit.py — engine-parametrized classifier + corroborator ----
const U1 = await agent(
  "U1: Create plugins/fleet-core/scripts/fleet_commons/delegation_audit.py \u2014 the engine-parametrized transcript classifier + bundle corroborator every tripwire consumes. classify(transcript_path, engine) generalizes the scan at plugins/agy/scripts/agy_delegate.py:995-1021 (engine Bash-command seen vs Claude file-tool seen; vocabulary real|fallback_suspected; per-line evidence) with per-engine config rows {command_re, bundle_root, launch_key} for agy (.claude/agy/runs, agy_launched) and codex (.claude/codex/runs, codex_launched); claude-file-tool set is Write|Edit|MultiEdit|NotebookEdit; stream lines with an 8 MiB byte cap, never read_text a whole transcript. corroborate(engine, since_ts) reads result.json launch flags + bridge-receipt.json presence under the bundle root \u2014 data contract only, NO cross-plugin code import. reconcile(classification, corroboration, self_report) returns real|fallback_suspected|delegation_integrity. HARD CONSTRAINT (R7): plugins/agy/scripts/agy_delegate.py is NOT modified \u2014 add a fixture-parity test that runs every fixture transcript through BOTH classify(engine='agy') and agy_delegate.classify_transcript (importlib-load it like plugins/agy/scripts/audit_harness_transcript.py:20 does) and asserts identical classification + seen-flags. Fixtures under tests/fixtures/delegation/. Tests in tests/test_delegation_audit.py, PLUS the DoD-named test_codex_bridge_untested_run_classified_false in tests/test_delegation_tripwire.py (create the file): Claude-finished run, no codex launch, bundle codex_launched=false \u2192 flagged. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U1, R4/R5/R7, KTD5/KTD8) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator", model: "sonnet", effort: "high" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U1_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U1 (fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U1 },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U1 (fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U1 },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U1 (fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "fleet-core delegation_audit.py \u2014 engine-parametrized classifier + corroborator verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U1 },
  ), { unitId: "U1", maxAttempts: 3 }),
])
const U1_reported = U1_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U1_missing_idx = U1_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U1_refute_count = U1_reported.filter((v) => v.refuted.length > 0).length
const U1_threshold = Math.max(1, Math.ceil(U1_reported.length / 2))  // majority over reporters
const U1_refuted = U1_refute_count >= U1_threshold
if (U1_missing_idx.length > 0) {
  log(`verify panel over U1: ${U1_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U1_missing_idx.join(", #")}); verdict computed over ${U1_reported.length}/3` +
      (U1_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U1_refuted) {
  throw new Error(`verifier-disagreement: Unit U1 refuted by ${U1_refute_count}/${U1_reported.length} reporting verifiers (${U1_missing_idx.length} missing)`)
}

// ---- U2: fleet-core delegation_state.py — arm/disarm marker protocol + CLI ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: Create plugins/fleet-core/scripts/fleet_commons/delegation_state.py \u2014 the liveness channel (KTD4). arm(engine, session_id, armed_by) / disarm(...) / active(session_id) over .claude/delegation/active.json: atomic tmp+rename writes (mirror codex_delegate's _write_json), entries {engine, session_id, armed_at, armed_by}, arm-twice supersedes in place, reads ignore AND reap entries older than a 4h TTL constant. CLI verbs arm/disarm/status (argparse, same style as sibling fleet-core scripts). FAIL-OPEN CONTRACT: active() NEVER raises \u2014 corrupt/missing/unreadable marker file is treated as unarmed (hooks depend on this); arm() MAY raise for the dispatcher (read-only fs). Extend tests/test_delegation_audit.py: arm\u2192status\u2192disarm round trip, stale-TTL invisibility + reap, two concurrent sessions isolated, arm-twice supersession, corrupt-JSON unarmed fail-open, CLI round trip via subprocess. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U2, R1/R2/R8, KTD4) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "fleet-core delegation_state.py \u2014 arm/disarm marker protocol + CLI", model: "sonnet", effort: "medium" },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U3: saga PreToolUse delegation tripwire hook + registration ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: Create plugins/saga/hooks/delegation_tripwire_hook.py and register it in plugins/saga/hooks/hooks.json under PreToolUse with matcher Write|Edit|MultiEdit|NotebookEdit (a NEW entry beside the existing validate_json entry \u2014 do not touch existing entries). Contract copied from plugins/saga/hooks/pre_push_gate_hook.py EXACTLY: stdin JSON tool_name/tool_input, block = exit 2 + stderr (name the armed engine, the expected evidence path, and the arm/disarm CLI), every other path silent exit 0, every error path fail-open exit 0 (malformed stdin, unreadable marker, missing bundle roots). Logic: marker check FIRST via delegation_state.active(session_id) (unarmed \u2192 exit 0 with zero further I/O); armed \u2192 evidence check per KTD5: any run dir under the armed engine's bundle_root containing prompt.txt with mtime >= armed_at passes; no such evidence \u2192 exit 2. Load fleet-core modules via saga's vendored fleet_commons_shim (insert ../scripts on sys.path relative to the hook file); if the shim or fleet-core module is unavailable, fail open. Tests: DoD-named test_zero_engine_call_write_blocks and test_genuine_agy_run_passes in tests/test_delegation_tripwire.py plus the edge matrix (unarmed no-marker exit 0, stale-TTL exit 0, evidence older than armed_at blocked, each of Edit/MultiEdit/NotebookEdit blocked when armed-unproven) using the repo hook-test convention (importlib spec_from_file_location + stdin-mocked main). Extend tests/test_spore_hooks_registration.py for the new hooks.json entry. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U3, R1/R2, KTD3/KTD4/KTD5) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga PreToolUse delegation tripwire hook + registration", model: "sonnet", effort: "high" },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U3 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U3_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U3 (saga PreToolUse delegation tripwire hook + registration). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga PreToolUse delegation tripwire hook + registration verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U3 },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U3 (saga PreToolUse delegation tripwire hook + registration). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga PreToolUse delegation tripwire hook + registration verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U3 },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U3 (saga PreToolUse delegation tripwire hook + registration). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga PreToolUse delegation tripwire hook + registration verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U3 },
  ), { unitId: "U3", maxAttempts: 3 }),
])
const U3_reported = U3_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U3_missing_idx = U3_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U3_refute_count = U3_reported.filter((v) => v.refuted.length > 0).length
const U3_threshold = Math.max(1, Math.ceil(U3_reported.length / 2))  // majority over reporters
const U3_refuted = U3_refute_count >= U3_threshold
if (U3_missing_idx.length > 0) {
  log(`verify panel over U3: ${U3_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U3_missing_idx.join(", #")}); verdict computed over ${U3_reported.length}/3` +
      (U3_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U3_refuted) {
  throw new Error(`verifier-disagreement: Unit U3 refuted by ${U3_refute_count}/${U3_reported.length} reporting verifiers (${U3_missing_idx.length} missing)`)
}

// ---- U4: saga Stop/SubagentStop audit hook + registration ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Create plugins/saga/hooks/delegation_stop_audit_hook.py and register it in plugins/saga/hooks/hooks.json under BOTH Stop and SubagentStop (verified contract: input carries transcript_path + stop_hook_active, SubagentStop adds agent_id/agent_type and its transcript_path IS the subagent's own; exit 2 + stderr blocks the stop and feeds the reason to Claude). Logic: marker stat FIRST (unarmed \u2192 exit 0 without opening the transcript); armed \u2192 delegation_audit.classify (8 MiB streaming cap) + corroborate + reconcile. Clean real+corroborated pass \u2192 disarm + exit 0. fallback_suspected OR transcript-vs-bundle divergence \u2192 HALT: exit 2 with stderr instructing Claude to surface the audit failure and re-run the delegation genuinely \u2014 name DELEGATION_INTEGRITY for the divergence flavor. LOOP GUARD (KTD2, operator-confirmed): when stop_hook_active is true and the audit still fails, write an audit record to .claude/delegation/audits/<ts>.json, print a banner to stderr, exit 0 \u2014 exactly one forced continuation, never an infinite block. Fail-open on every error path (missing transcript while armed \u2192 banner + exit 0, never crash). Tests: DoD-named test_stop_hook_classifies_fallback_suspected and test_stop_hook_passes_real_classification in tests/test_delegation_tripwire.py plus: stop_hook_active loop-guard case (audit record written, exit 0), divergence case (transcript real but bundle launch=false \u2192 exit 2 naming DELEGATION_INTEGRITY), unarmed turn never opens the transcript (prove via a nonexistent transcript path that would error if opened), disarm-on-pass. Extend tests/test_spore_hooks_registration.py for both event registrations. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U4, R3/R4/R8, KTD2/KTD8) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga Stop/SubagentStop audit hook + registration", model: "fable", effort: "xhigh" },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// verify: refute-3 panel over U4 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U4_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U4 (saga Stop/SubagentStop audit hook + registration). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga Stop/SubagentStop audit hook + registration verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U4 },
  ), { unitId: "U4", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U4 (saga Stop/SubagentStop audit hook + registration). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga Stop/SubagentStop audit hook + registration verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U4 },
  ), { unitId: "U4", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U4 (saga Stop/SubagentStop audit hook + registration). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga Stop/SubagentStop audit hook + registration verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U4 },
  ), { unitId: "U4", maxAttempts: 3 }),
])
const U4_reported = U4_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U4_missing_idx = U4_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U4_refute_count = U4_reported.filter((v) => v.refuted.length > 0).length
const U4_threshold = Math.max(1, Math.ceil(U4_reported.length / 2))  // majority over reporters
const U4_refuted = U4_refute_count >= U4_threshold
if (U4_missing_idx.length > 0) {
  log(`verify panel over U4: ${U4_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U4_missing_idx.join(", #")}); verdict computed over ${U4_reported.length}/3` +
      (U4_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U4_refuted) {
  throw new Error(`verifier-disagreement: Unit U4 refuted by ${U4_refute_count}/${U4_reported.length} reporting verifiers (${U4_missing_idx.length} missing)`)
}

// ---- U5: dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Two-signal acceptance at the dispatch layer (R4/R6, KTD6/KTD7). In plugins/saga/scripts/provenance_manifest.py add DELEGATION_INTEGRITY to the Disposition StrEnum (:54). In plugins/saga/scripts/engine_dispatch.py: (a) arm via delegation_state before the adapter run and disarm in a finally (arming failure \u2192 dispatch still runs, manifest records tripwire_unarmed \u2014 fail-open, named); (b) after the run, corroborate via delegation_audit (launch_key true + _receipt_problems()-clean receipt = observer-yes); (c) self-report ok + observer-no \u2192 Disposition.DELEGATION_INTEGRITY, dispatch returns a typed requeue disposition ONCE (attempt counter in the manifest record), a second consecutive divergence raises DispatchError HALT; (d) advisory (non-gated) divergence keeps the existing downgrade_note mechanism with the integrity reason attached \u2014 NO requeue loop; (e) satisfy_gate() (:409-435) additionally requires observer corroboration beside verified_by_claude. PRESERVE: _reject_gatekeeper_keys posture, existing FAILURE_STATUSES downgrade behavior, and every existing engine-dispatch test's advisory semantics (update expected values deliberately where acceptance changed, never as collateral). Tests: DoD-named test_reconciliation_flags_divergence and test_two_signal_disagreement_requeues in tests/test_delegation_tripwire.py (first divergence \u2192 requeue disposition; corroborating retry \u2192 accepted; second divergence \u2192 HALT; both-signals-agree \u2192 RAN_AS_REQUESTED and gate satisfiable; receipt-valid-but-launch-flag-missing \u2192 observer-no conservative). Extend the existing engine-dispatch suites as needed. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U5, R4/R6, KTD6/KTD7) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY", model: "fable", effort: "xhigh" },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// verify: refute-3 panel over U5 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U5_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout feat/384-delegation-tripwires -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse feat/384-delegation-tripwires` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} — NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
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

// ---- U6: chaperone contract doc + end-to-end integration scenarios ----
// depends_on: U5 (barrier)
const U6 = await agent(
  "U6: Make the runtime contract legible to team-execution's chaperone (R6/R8). Update plugins/team-execution/skills/team-execution/references/external-engine-workers.md \u00a75 ADDITIVELY: the chaperone arms via the delegation_state CLI before dispatch, accepts only on two-signal agreement, re-queues at most once then HALTs, and DELEGATION_INTEGRITY appears in the halt reason \u2014 no team-execution CODE changes (issue non-goal). Then add the cross-mechanism integration scenarios to tests/test_delegation_tripwire.py that no single unit proves: full arc in a scratch repo \u2014 arm \u2192 fake genuine bundle (prompt.txt + result.json launch=true + receipt) \u2192 PreToolUse hook passes \u2192 Stop hook passes and disarms; full zero-engine-call arc \u2014 arm \u2192 no bundle \u2192 PreToolUse blocks \u2192 Stop hook (invoked as if the block were bypassed) exits 2. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U6) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "chaperone contract doc + end-to-end integration scenarios", model: "sonnet", effort: "medium" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U7: release surfaces + journal ----
// depends_on: U6 (barrier)
const U7 = await agent(
  "U7: Release surfaces (repo rule 6: installed-plugin metadata tells the same story as the diff). Bump plugins/fleet-core (0.7.0 \u2192 0.8.0, two new commons modules), plugins/saga (0.73.1 \u2192 0.74.0, two new hooks + dispatch acceptance change), plugins/team-execution (patch bump, \u00a75 contract) \u2014 plugin.json + CHANGELOG.md each, mirrored in .claude-plugin/marketplace.json. UPDATE THE DRIFT-GUARD VERSION PINS by RUNNING them, not by assumption (tests/test_saga_plugin.py, tests/test_team_execution_plugin.py, any fleet-core pin/vendored-copy tests) \u2014 the #476 round shipped surface bumps but missed pins and the suite went red. Journal: DECISIONS.md entries for KTD1 (hooks live in saga, auditor in fleet-core \u2014 rejected agy-hosted mirror, cite {#unit-panels-vs-whole-diff-lenses-476}) and KTD6 (DELEGATION_INTEGRITY lives at the dispatch layer, not wrapper STATUSES \u2014 the two fallback_suspected taxonomies stay separate), each with rationale + revisit-when. Confirm release-surface-parity and drift-guard tests green. Read the plan at docs/plans/2026-07-07-delegation-tripwires-plan.md (U7, R9) as your authoritative spec. When done, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces + journal", model: "sonnet", effort: "medium" },
)
__gate(U7, { unitId: "U7", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
