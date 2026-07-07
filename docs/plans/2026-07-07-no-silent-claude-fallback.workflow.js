// ===========================================================================
// no-silent-claude-fallback -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "no-silent-claude-fallback",
  description: "Issue #390 (+#392 facet): fail-loud provenance wiring \u2014 provenance_required becomes a status/exit consumer in agy_delegate, build_dispatch_manifest auto-derives SUBSTITUTED_ENGINE from an expected_identity baseline (KTD4 precedence: integrity > halt > substituted > receipt), satisfy_gate refuses substituted manifests, manifest_reader surfaces fallback reasons, check_empty_delivery gates the chaperone's documented commit step, execution_spec verify panels gain verifier_identity/fallback_depth attribution, release surfaces across agy/saga/team-execution. SERIALIZED unit chain (every unit depends_on its predecessor) deliberately: operator rate-limit cap is max 3 concurrent non-haiku agents; the only parallelism is the n=3 verify panels on U1/U2/U5/U6, so peak concurrency is exactly 3 by construction (precedent: delegation-tripwires, codex-first-party-bridge specs). Serialization also prevents concurrent edits to tests/test_saga_engine_dispatch.py (U2/U4) and external-engine-workers.md (U3/U5). WAVE-A GUARDRAIL (journal {#verify-panels-blind-to-uncommitted-tree}): every worker commits its completed unit on the branch so verify-panel worktrees (cut from main) can materialize committed state; verifier prompts must include mandatory branch materialization (git checkout <branch> -- .) + examined-sha quoting \u2014 verify the emitter includes this or patch post-emit. COORDINATION SEAM: #388 extends the receipt-validation leg BELOW the new substitution branch and rebases over this work; nothing here touches engine_resolver.py or engine-registry.yaml.",
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

// ---- U1: agy — provenance_required becomes a status/exit consumer ----
const U1 = await agent(
  "U1: Wire provenance_required into agy's status/exit decision (plan U1, R1, KTD1). In plugins/agy/scripts/agy_delegate.py, where the result payload is assembled (_result_payload, :1416-1454, called at :415/:474/:612): when envelope.provenance_required is true AND _real_agy_verdict(run_result) (:1627-1635) is 'unproven' AND the status is a passing one (success/patch_ready/applied), coerce the run status to 'fallback_suspected' and record the coercion reason in the payload (e.g. coerced_by='provenance_required'). Do NOT call classify_transcript in the run path \u2014 transcript auditing is the Stop-hook's (#384); the wrapper's only provenance signal is _real_agy_verdict. Do NOT add exit codes or envelope fields \u2014 exit 1 arrives free via the existing mapping at agy_delegate.py:1167 (return 0 only for success/patch_ready/applied). provenance_required=False keeps today's behavior byte-for-byte; a status already fallback_suspected (stdout marker :1374) is not double-coerced. BOUNDARY (#523): do not touch the verdict input side (the wrapper mapping executor-construction failure to success is #523's scope) \u2014 this unit wires the verdict OUTPUT to status/exit. ORACLE DISCIPLINE (R10): write the new tests FIRST and run them against the pre-fix tree to record them red, then land the fix. Tests in tests/test_agy_delegate_contract.py, selector provenance_required_coerces_fallback: unproven+required \u2192 fallback_suspected + exit 1; unproven+not-required \u2192 unchanged + exit 0; real verdict+required \u2192 unchanged; already-fallback_suspected (marker path)+required \u2192 stays fallback_suspected, no double-coercion, still exit 1. Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U1, R1/R10, KTD1) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, red_on_main_evidence, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "agy \u2014 provenance_required becomes a status/exit consumer", model: "sonnet", effort: "high" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "red_on_main_evidence", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U1_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U1 (agy \u2014 provenance_required becomes a status/exit consumer). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "agy \u2014 provenance_required becomes a status/exit consumer verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U1 },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U1 (agy \u2014 provenance_required becomes a status/exit consumer). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "agy \u2014 provenance_required becomes a status/exit consumer verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U1 },
  ), { unitId: "U1", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U1 (agy \u2014 provenance_required becomes a status/exit consumer). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "agy \u2014 provenance_required becomes a status/exit consumer verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U1 },
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

// ---- U2: saga — SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: SUBSTITUTED_ENGINE auto-derivation + gate refusal (plan U2, R2/R3/R4, KTD3/KTD4/KTD5). In plugins/saga/scripts/engine_dispatch.py: (a) dispatch() gains optional expected_identity: str | None = None ('engine/variant' plan-time preview baseline), stamped into evidence provenance \u2014 additive-defaulted, mirroring the runner_receipt precedent (engine_dispatch.py:41-55); (b) build_dispatch_manifest (:443-506) gains the SUBSTITUTED_ENGINE branch at KTD4 precedence \u2014 DELEGATION_INTEGRITY > halt (FELL_BACK_TO_CLAUDE) > SUBSTITUTED_ENGINE (expected_identity set and != f'{engine_id}/{variant}') > receipt check (UNPROVEN/RAN_AS_REQUESTED) \u2014 with disposition_note naming BOTH identities; (c) enforce the R3 invariant: every non-RAN_AS_REQUESTED manifest carries a non-empty disposition_note (fixed fallback string for degenerate empty reasons); (d) satisfy_gate (:585-625) additionally refuses a manifest whose disposition is SUBSTITUTED_ENGINE (DispatchError \u2014 substituted evidence can never satisfy a gate as-approved). PRESERVE: expected_identity=None keeps every existing path byte-for-byte; never modify engine_resolver.py or engine-registry.yaml (#388 seam). ORACLE DISCIPLINE (R10): record the derivation test red on the pre-fix tree first. Tests in tests/test_saga_engine_dispatch.py, selectors substituted_disposition and fallback_reason: expected\u2260resolved \u2192 SUBSTITUTED_ENGINE + both identities in note; expected=resolved \u2192 unchanged; None \u2192 unchanged; halt+mismatch \u2192 halt branch wins; mismatch+schema-valid receipt \u2192 still SUBSTITUTED_ENGINE, never RAN_AS_REQUESTED; satisfy_gate on substituted manifest \u2192 DispatchError; empty halt/note \u2192 fixed non-empty reason. Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U2, R2/R3/R4, KTD3/KTD4/KTD5) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, red_on_main_evidence, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant", model: "opus", effort: "high" },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "red_on_main_evidence", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U2 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U2_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U2 (saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U2 },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U2 (saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U2 },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U2 (saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal + note invariant verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U2 },
  ), { unitId: "U2", maxAttempts: 3 }),
])
const U2_reported = U2_verdicts.filter((v) => v != null && Array.isArray(v.refuted))
const U2_missing_idx = U2_verdicts.map((v, i) => (v == null || !Array.isArray(v.refuted) ? i + 1 : null)).filter((i) => i != null)
const U2_refute_count = U2_reported.filter((v) => v.refuted.length > 0).length
const U2_threshold = Math.max(1, Math.ceil(U2_reported.length / 2))  // majority over reporters
const U2_refuted = U2_refute_count >= U2_threshold
if (U2_missing_idx.length > 0) {
  log(`verify panel over U2: ${U2_missing_idx.length}/3 verifier(s) missing (runtime-failure: #${U2_missing_idx.join(", #")}); verdict computed over ${U2_reported.length}/3` +
      (U2_reported.length < 2 ? " — UNDER-STRENGTH (quorum floor 2)" : ""))
}
if (U2_refuted) {
  throw new Error(`verifier-disagreement: Unit U2 refuted by ${U2_refute_count}/${U2_reported.length} reporting verifiers (${U2_missing_idx.length} missing)`)
}

// ---- U3: team-execution — delete the hand-build manifest path from the chaperone contract ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: One manifest-construction path (plan U3, R5). Rewrite plugins/team-execution/skills/team-execution/references/external-engine-workers.md \u00a75 step 4 to a single-path instruction: record_dispatch_manifest(..., expected_identity=<the \u00a74 preview identity>) for EVERY disposition including substitution; DELETE the documented direct provenance_manifest.Manifest construction (the ':163-176' region \u2014 'build_dispatch_manifest has no way to express this disposition' prose is now false); update \u00a74's 'only reachable substitution path' wording to point at the shared builder's derivation; refresh the stale engine_dispatch.py:124-161 and :153 line citations (the builder now lives at :443+); state the #392 fail-loud discriminator as the worker-slot contract: a substituted run is refused by satisfy_gate and must surface as a HALT, never pass as an external result. Add a doc-guard test asserting the contract file no longer instructs direct Manifest construction and does reference expected_identity (default home: tests/test_manifest_consumer_matrix.py beside the existing manifest-contract guards; place it with the other doc-drift guards if a better home exists). Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U3, R5) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "team-execution \u2014 delete the hand-build manifest path from the chaperone contract", model: "sonnet", effort: "medium" },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U4: saga — fallback reasons reach the manifest_reader roll-up ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Fallback reasons reach the operator surface (plan U4, R6, KTD2). In plugins/saga/scripts/manifest_reader.py, the report gains a reasons section: for each manifest whose disposition != RAN_AS_REQUESTED, render execution id, disposition, and disposition_note. Do NOT invent a new roll-up artifact and do NOT write run-fact-ledger records (#386/#393 own those writers per run_ledger.py's docstring) \u2014 the R18 report in manifest_reader is the surface. Tests in tests/test_manifest_reader.py, selector fallback_reason_propagation: a halted dispatch's manifest renders its resolver reason; substituted and integrity rows render notes; an all-RAN_AS_REQUESTED store renders no reasons section; empty store unchanged. Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U4, R6, KTD2) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga \u2014 fallback reasons reach the manifest_reader roll-up", model: "sonnet", effort: "medium" },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U5: saga — check_empty_delivery() at the delegated-unit boundary ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Empty-delivery HALT at the delegated-unit boundary (plan U5, R7, KTD6). Create plugins/saga/scripts/check_empty_delivery.py: a pure verdict function (inputs: changed paths list, claims_delivery flag; output: a typed HALT verdict when claims_delivery is true and zero paths changed, a proceed verdict otherwise) plus a thin CLI reading `git status --porcelain -z`, exiting non-zero on HALT \u2014 argparse style matching sibling saga scripts. The helper GATES the chaperone's existing documented commit step; it NEVER commits anything itself and mints no new auto-commit machinery (none exists in this repo \u2014 /optimize deliberately shed its own). Keep the file-delivery axis distinct from record-completeness's returned-value missing-output trip (manifest_store.py:249-363) \u2014 do not touch manifest_store. Wire the contract: external-engine-workers.md \u00a75 gains the check between verify and the chaperone-owned commit (ADDITIVE edit \u2014 U3 already rewrote step 4; do not undo it). Tests in NEW tests/test_check_empty_delivery.py, selectors halts_on_empty_delivery and autocommits_on_delivery: claims-delivery + zero paths \u2192 HALT; claims-delivery + paths \u2192 proceed verdict authorizing the documented commit step (the 'autocommits' selector asserts the proceed verdict \u2014 the helper itself never commits); no-delivery-claimed + zero paths \u2192 ok (legitimately read-only unit); CLI outside a git repo \u2192 clean error, not a stack trace. Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U5, R7, KTD6) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga \u2014 check_empty_delivery() at the delegated-unit boundary", model: "sonnet", effort: "high" },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U5 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U5_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (saga \u2014 check_empty_delivery() at the delegated-unit boundary). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 check_empty_delivery() at the delegated-unit boundary verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (saga \u2014 check_empty_delivery() at the delegated-unit boundary). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 check_empty_delivery() at the delegated-unit boundary verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
  ), { unitId: "U5", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U5 (saga \u2014 check_empty_delivery() at the delegated-unit boundary). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 check_empty_delivery() at the delegated-unit boundary verifier", model: "sonnet", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U5 },
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

// ---- U6: saga — attributed verify-spawn fallback in execution_spec panels ----
// depends_on: U5 (barrier)
const U6 = await agent(
  "U6: Attributed verify-spawn fallback (plan U6, R8, KTD7). In plugins/saga/scripts/execution_spec.py: the verifier verdict schema + prompt (:1326-1332 region) gain verifier_identity (emitter-stamped from the agentType the emitter already knows, echoed by the verifier) and fallback_depth (int, default 0); the panel aggregation (:1369-1439 region) renders an explicit 'fallback tier N' marker in the panel summary/throw message when any reporter's fallback_depth exceeds 0, and NO marker when all reporters are depth 0 \u2014 implement the marker formatting as a PURE render helper function so it is unit-testable without emitting a workflow. The ladder itself is untouched (binding decision {#readonly-verifier-fallback-ladder-325}: attribution only, never reorder/redefine rungs). In plugins/saga/references/sandbox-spawn-sites.md, the fallback-ladder section gains the recording rule: an inline spawner descending to rung 2/3 must carry the fallback_depth into whatever verdict/tick it records. Tests: NEW tests/test_verify_spawn_gate_summary.py for the render helper, selectors fallback_tier_2_rendered and no_fallback_marker_on_first_choice (depth 2 \u2192 'fallback tier 2'; all depth 0 \u2192 no marker; mixed panel \u2192 marker names the degraded reporter only), PLUS emitted-JS assertions in tests/test_saga_execution_spec.py (emitted workflow carries the schema fields and stamped identity; existing emission tests stay green). Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U6, R8, KTD7) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "saga \u2014 attributed verify-spawn fallback in execution_spec panels", model: "opus", effort: "high" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U6 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U6_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (saga \u2014 attributed verify-spawn fallback in execution_spec panels). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 attributed verify-spawn fallback in execution_spec panels verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (saga \u2014 attributed verify-spawn fallback in execution_spec panels). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 attributed verify-spawn fallback in execution_spec panels verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (saga \u2014 attributed verify-spawn fallback in execution_spec panels). MANDATORY FIRST STEP (Wave-A guardrail {#verify-panels-blind-to-uncommitted-tree}): your disposable worktree was cut from the DEFAULT branch (main) and does NOT contain this unit's work. Before judging anything run `git checkout fix/390-no-silent-claude-fallback -- .` to materialize the work branch's committed state into your worktree, then run `git rev-parse fix/390-no-silent-claude-fallback` and QUOTE that examined SHA in your verdict. If the checkout fails, say so and emit {refuted: [], upheld: [], examined_sha: null, error: '<why>'} -- NEVER judge main's code as if it were the branch. You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...], examined_sha: '<sha>'}.",
    { label: "saga \u2014 attributed verify-spawn fallback in execution_spec panels verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
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

// ---- U7: release surfaces + journal + full gate ----
// depends_on: U6 (barrier)
const U7 = await agent(
  "U7: Release surfaces (plan U7, R9/R10; repo rule 6: installed-plugin metadata tells the same story as the diff). Minor bumps with description updates: plugins/agy 0.1.2 \u2192 0.2.0 (plugin.json + CHANGELOG \u2014 the entry MUST flag the behavior change: previously-passing unproven runs with provenance_required=True now fail loud, and provenance_required defaults to True); plugins/saga 0.74.1 \u2192 0.75.0 (SUBSTITUTED_ENGINE auto-derivation + satisfy_gate refusal, reader reasons section, check_empty_delivery, verify-panel attribution); plugins/team-execution 2.12.3 \u2192 2.13.0 (single-path manifest contract + empty-delivery gate in \u00a75). Mirror all three in .claude-plugin/marketplace.json and verify with scripts/sync_marketplace.py --check. UPDATE THE DRIFT-GUARD VERSION PINS BY RUNNING THEM, not by assumption (tests/test_saga_plugin.py, tests/test_agy_plugin.py, tests/test_team_execution_plugin.py) \u2014 the #476 round shipped surface bumps but missed pins and the suite went red. Run the R5 grep check: grep -rn 'pm.Disposition.SUBSTITUTED_ENGINE' plugins/ must find only the enum definition and shared-builder/test references (no hand-build instruction). The DECISIONS.md entry for this plan's KTDs already exists ({#no-silent-claude-fallback-390}) \u2014 verify it matches what shipped, amend only if a KTD changed during execution. Full gate: uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports. Read the plan at docs/plans/2026-07-07-no-silent-claude-fallback-plan.md (U7, R9/R10) as your authoritative spec. When done, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, gate_results, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces + journal + full gate", model: "sonnet", effort: "medium" },
)
__gate(U7, { unitId: "U7", expectsOutput: true, returns: ["files_changed", "gate_results", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
