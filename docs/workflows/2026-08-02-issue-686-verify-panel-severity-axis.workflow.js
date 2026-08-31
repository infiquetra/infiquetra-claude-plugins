// ===========================================================================
// issue-686-verify-panel-severity-axis -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "issue-686-verify-panel-severity-axis",
  description: "Split the refute-N verifier verdict into a gating and a non-gating bucket in the emitter",
}
const settlement = {"casualty_threshold_percent":0,"dispatch_id":"workflow:29276cd44abf5b51e4467fe0","driver":{"invocation_id":null,"units":[{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U1","workflow_unit_id":"U1"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U2","workflow_unit_id":"U2"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U3","workflow_unit_id":"U3"}]},"max_attempts":3,"schema":"dispatch_settlement.v1","site":"workflow","units":[{"deliverables":["structured-result","return:status","return:files_changed","return:checks_run","return:notes"],"idempotency_key":"workflow:29276cd44abf5b51e4467fe0:U1","unit_id":"U1"},{"deliverables":["structured-result","return:status","return:files_changed","return:checks_run","return:notes"],"idempotency_key":"workflow:29276cd44abf5b51e4467fe0:U2","unit_id":"U2"},{"deliverables":["structured-result","return:status","return:files_changed","return:checks_run","return:notes"],"idempotency_key":"workflow:29276cd44abf5b51e4467fe0:U3","unit_id":"U3"}]}

const REPO = "/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins"

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

// ---- U1: split-verdict-contract-in-emitter ----
// escalation: HALT if the split cannot be made without weakening the missing-verifier hard-fail or the quorum floor -- re-scope rather than trading one control for another.
const U1 = await agent(
  "U1: Split the refute-N verifier verdict into a gating bucket (refuted_deliverable) and a non-gating bucket (advisory_corrections) in plugins/saga/scripts/execution_spec.py, and pin every change in tests/test_workflow_emitter.py and tests/test_saga_execution_spec.py. Read the plan at docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md as your authoritative spec; work its `### U1.` numbered site list 1-8 in order. TWO THINGS A NAIVE READING DROPS. (a) SITE 4, the `__logAdvisory` call at execution_spec.py:2762 -- sites 7 and 8 only declare and return the accumulator, so without site 4 `advisory_corrections` is `[]` on every run and R4 fails silently. Its position matters: it must go immediately after the `refuted` const and BEFORE the missing-verifier block, because `_emit_panel_reconciliation` returns early on the #364 climb path. (b) SITE 1 is a RENAME, not an addition: the key `refuted` disappears from both `properties` and `required`; `upheld` survives. Port all three prompt passages VERBATIM from the sources the plan names -- do not paraphrase any of them.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, checks_run, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "split-verdict-contract-in-emitter", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"checks_run": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "checks_run", "notes"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["status", "files_changed", "checks_run", "notes"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U2: update-doc-and-release-surfaces ----
// depends_on: U1 (barrier)
// escalation: HALT if the drift-guard tests disagree with the version you wrote -- the metadata must tell the same story as the diff.
// ---- U3: clear-downstream-divergence ----
// depends_on: U1 (barrier)
// escalation: HALT and report as a U1 defect ONLY on a behavioral mismatch -- a count mismatch in the plan's checks 2-4, or a non-unit-prompt line in the residual diff. Do NOT halt on unit-prompt differences; those are expected and permanent. Never patch the downstream file.
const [U2, U3] = await parallel([
  () =>
    __retry(() => agent(
      "U2: Update plugins/saga/references/execution-spec.md to describe the two-bucket verify contract and the new workflow return shape, bump the saga plugin version across plugins/saga/.claude-plugin/plugin.json, .claude-plugin/marketplace.json and plugins/saga/CHANGELOG.md, and record the plan's KTD1-KTD8 in docs/engineering-journal/DECISIONS.md. Read the plan at docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md as your authoritative spec; its `### U2.` section names the exact doc lines to change.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, checks_run, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "update-doc-and-release-surfaces", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"checks_run": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "checks_run", "notes"], "type": "object"} },
    ), { unitId: "U2", maxAttempts: 3 }),
  () =>
    __retry(() => agent(
      "U3: Re-emit the committed spec in ~/workspace/infiquetra/infiquetra-codex-plugins with the fixed emitter and confirm the regenerated GATE MECHANICS match its hand-patched harness. Read the plan at docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md as your authoritative spec; its `### U3.` section carries the exact commands and the pass/fail conditions -- run them as written. AN EMPTY DIFF IS NOT THE PASS CONDITION: the committed harness carries hand-authored mid-run prompt corrections that appear in ZERO of the committed spec's unit prompts, so at least one unit-prompt line differs permanently and is NOT a defect. The pass condition is the four behavioral checks in the plan. Read both downstream files from `origin/main` via `git show` after `git fetch`, never from the working tree. This unit is READ-ONLY: mutate nothing in that repository and commit nothing.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, checks_run, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "clear-downstream-divergence", model: "sonnet", effort: "low", schema: {"additionalProperties": true, "properties": {"checks_run": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "checks_run", "notes"], "type": "object"} },
    ), { unitId: "U3", maxAttempts: 3 }),
])
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["status", "files_changed", "checks_run", "notes"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["status", "files_changed", "checks_run", "notes"], cordProposal: "sonnet/low -> sonnet/medium (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
