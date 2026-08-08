// ===========================================================================
// house-style-output-style-plugin -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "house-style-output-style-plugin",
  description: "Ship the house-style output-style plugin (#704) and its two subagent reach levers, gated on an experiment that proves both levers work.",
}
const settlement = {"casualty_threshold_percent":0,"dispatch_id":"workflow:46ed1c1f3f68a5cef38cb314","driver":{"invocation_id":null,"units":[{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:lever_a_result","result_key":"lever_a_result"},{"deliverable":"return:lever_b_result","result_key":"lever_b_result"},{"deliverable":"return:evidence_path","result_key":"evidence_path"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U1","workflow_unit_id":"U1"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U2","workflow_unit_id":"U2"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:baseline_untouched","result_key":"baseline_untouched"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U7","workflow_unit_id":"U7"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tell_literal","result_key":"tell_literal"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U3","workflow_unit_id":"U3"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:baseline_suite_green_before","result_key":"baseline_suite_green_before"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U5","workflow_unit_id":"U5"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:file_count","result_key":"file_count"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U6","workflow_unit_id":"U6"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:plain_english_rules_unchanged","result_key":"plain_english_rules_unchanged"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U8","workflow_unit_id":"U8"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:mutation_results","result_key":"mutation_results"},{"deliverable":"return:checks_run","result_key":"checks_run"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U4","workflow_unit_id":"U4"},{"return_keys":[{"deliverable":"return:status","result_key":"status"},{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:plugin_count","result_key":"plugin_count"},{"deliverable":"return:gate_results","result_key":"gate_results"},{"deliverable":"return:notes","result_key":"notes"}],"settlement_unit_id":"U9","workflow_unit_id":"U9"}]},"max_attempts":3,"schema":"dispatch_settlement.v1","site":"workflow","units":[{"deliverables":["structured-result","return:status","return:lever_a_result","return:lever_b_result","return:evidence_path","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U1","unit_id":"U1"},{"deliverables":["structured-result","return:status","return:files_changed","return:checks_run","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U2","unit_id":"U2"},{"deliverables":["structured-result","return:status","return:files_changed","return:checks_run","return:baseline_untouched","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U7","unit_id":"U7"},{"deliverables":["structured-result","return:status","return:files_changed","return:tell_literal","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U3","unit_id":"U3"},{"deliverables":["structured-result","return:status","return:files_changed","return:checks_run","return:baseline_suite_green_before","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U5","unit_id":"U5"},{"deliverables":["structured-result","return:status","return:files_changed","return:file_count","return:checks_run","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U6","unit_id":"U6"},{"deliverables":["structured-result","return:status","return:files_changed","return:plain_english_rules_unchanged","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U8","unit_id":"U8"},{"deliverables":["structured-result","return:status","return:files_changed","return:mutation_results","return:checks_run","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U4","unit_id":"U4"},{"deliverables":["structured-result","return:status","return:files_changed","return:plugin_count","return:gate_results","return:notes"],"idempotency_key":"workflow:46ed1c1f3f68a5cef38cb314:U9","unit_id":"U9"}]}

const REPO = "infiquetra/infiquetra-claude-plugins"

const __pulledCords = []

const __advisories = []
const __advisoryRounds = new Map()
const __ADVISORY_ITEM_CAP = 50
const __ADVISORY_ITEM_CHARS = 180
function __renderAdvisory(a) {
  var s
  try {
    if (a === null || a === undefined) s = "(empty advisory entry)"
    else if (typeof a === "string") s = a
    else s = String(a.claim || a.id || JSON.stringify(a))
  } catch (e) {
    s = "(unrenderable advisory entry)"
  }
  // Two passes over two distinct hazards. First: C0, DEL, C1 (NEL included) and the
  // line/paragraph separators -- these forge a second log line. Second: the bidi marks,
  // embeddings, overrides and isolates plus the BOM -- these leave the byte sequence intact
  // but reorder what a human READS in a terminal or log viewer (the Trojan-Source pattern).
  // Advisory text is model-authored by a verifier that read a diff it did not write, so both
  // classes are reachable from repo content.
  var t = s
    .replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]+/g, " ")
    .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]+/g, " ")
    .slice(0, __ADVISORY_ITEM_CHARS)
  // .slice() cuts on UTF-16 code units, so an astral character (any emoji) straddling the cap
  // leaves a lone high surrogate behind. This string is now STORED and returned, not just
  // logged, so ill-formed UTF-16 would cross the harness return boundary -- a consumer that
  // re-encodes it substitutes U+FFFD or raises. Drop the orphan half.
  var tail = t.charCodeAt(t.length - 1)
  if (tail >= 0xd800 && tail <= 0xdbff) t = t.slice(0, -1)
  return t
}
function __halt(message) {
  var e = new Error(message)
  e.advisory_corrections = __advisories
  return e
}
function __logAdvisory(unitId, reported, refuted) {
  // Counted on EVERY call, before the empty-items early return below -- a panel round that
  // produced no advisories is still a round. Deriving the ordinal from stored entries instead
  // would silently renumber: an iterate_to_consensus unit whose first round was clean would
  // label its second round "round 1", and a driver told to read the last entry would act on
  // advice about a discarded intermediate result. A Map, not an object, so a unit id like
  // `constructor` cannot collide with a prototype member.
  var round = (__advisoryRounds.get(unitId) || 0) + 1
  __advisoryRounds.set(unitId, round)
  var items = []
  try {
    for (var i = 0; i < reported.length; i++) {
      var adv = Array.isArray(reported[i].advisory_corrections) ? reported[i].advisory_corrections : []
      for (var j = 0; j < adv.length; j++) items.push(__renderAdvisory(adv[j]))
    }
  } catch (e) {
    // Through __renderAdvisory, not around it: this marker embeds a model-reachable
    // message and is the one path that would otherwise reach log() unscrubbed.
    items.push(__renderAdvisory("(advisory harvest failed: " + String(e && e.message) + ")"))
  }
  if (items.length === 0) return items
  var dropped = 0
  if (items.length > __ADVISORY_ITEM_CAP) {
    dropped = items.length - __ADVISORY_ITEM_CAP
    items = items.slice(0, __ADVISORY_ITEM_CAP)
  }
  __advisories.push({ unit: unitId, round: round, corrections: items, dropped: dropped })
  try {
    log(`verify panel over ${unitId} (round ${round}): deliverable ${refuted ? "REFUTED" : "UPHELD"} with ${items.length + dropped} advisory correction(s) (narrative/rationale only, non-gating): ` +
        items.join(" | ") + (dropped > 0 ? ` [+${dropped} suppressed]` : ""))
  } catch (e) {
    /* the non-gating accumulator must never be able to halt a run */
  }
  return items
}

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
    throw __halt(
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
        throw __halt(
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
      throw __halt(
        `missing-output: Unit ${unitId} produced fewer items than expected. ` +
        `Expected ${targetCount}, produced ${producedCount}. Shortfall: ${shortfall}.`
      );
    }
  }

  if (opts.returns && opts.returns.length > 0) {
    const parsed = parseResult(result);
    if (parsed === null || parsed === undefined || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw __halt(
        `missing-output: Unit ${unitId} result is not a structured dictionary. ` +
        `Missing required keys: ${opts.returns.join(', ')}.`
      );
    }
    const missing = opts.returns.filter(
      k => !(k in parsed) || parsed[k] === null || parsed[k] === undefined
    );
    if (missing.length > 0) {
      throw __halt(
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

function __verifierPrompt(basePrompt, unitResult, passRule) {
  var gatingBar = (passRule === "unanimous")
    ? "EVERY reporting verifier"
    : "a majority of the panel";
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
  evidence to judge, return a refuted_deliverable entry explaining the visibility gap; do not emit
  prose-only "nothing to verify" output.

VERDICT CONTRACT — two separate buckets. Read this before you write anything.

The unit result you are given contains BOTH a deliverable and a narrative. Sort every disagreement
you find into exactly one of these. Getting the bucket right matters more than finding a lot.

\`refuted_deliverable\` — GATING. A finding belongs here only if the unit's actual WORK is wrong:
- A changed file is wrong, incomplete, or breaks something.
- Required behavior is missing, or behavior the unit was told to preserve was destroyed.
- A test is missing, wrong, asserts nothing, or does not test what it claims.
- A claim in \`checks_run\` is FALSE — the command does not actually pass, or was not actually run,
  or its reported result does not reproduce. Re-run the commands and check.
- The unit says \`status: "done"\` but the work is not done.
- You could not see enough to judge (visibility gap).
A non-empty \`refuted_deliverable\` from ${gatingBar} KILLS the unit and HALTS the whole
workflow. Put a finding here only if you would defend stopping the run over it.

\`advisory_corrections\` — NON-GATING. A finding belongs here if the WORK is right but the unit's
own account of it is wrong or misleading:
- Its explanation of WHY something happened is factually incorrect.
- It misattributes a change to the wrong function, file, or line.
- It mischaracterizes a mechanism, or states a rationale that does not hold.
- Its advice to a downstream unit rests on a wrong premise.
These are recorded and handed to the driver. They do NOT stop the run. Report them fully and
precisely — a wrong premise passed downstream causes real damage later, so this bucket is
genuinely valuable, not a consolation prize.

The test: if the unit's code, tests, and check results are all sound, then NOTHING goes in
\`refuted_deliverable\`, no matter how wrong its prose is. Prose errors are advisory. Full stop.

Both keys are REQUIRED and must be arrays. Use \`[]\` for an empty bucket — never omit either one.

UNIT RESULT INPUT (structured evidence — the \`notes\` field is the unit's NARRATIVE, judge it
under \`advisory_corrections\`; the changed files, tests, and \`checks_run\` are the DELIVERABLE):
${rendered}`;
}

// ---- U1: prove-both-levers-by-experiment ----
// escalation: HALT and report if either lever's marker does not reach the output. Do not substitute a different mechanism, do not lower the reach claim to compensate, and do not proceed to U2.
const U1 = await agent(
  "U1: Prove BOTH subagent reach levers work by direct experiment, before any other unit runs. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U1.` section. LEVER A (agent definition files): create a throwaway agent definition under plugins/<some-plugin>/agents/ carrying a distinctive marker string, spawn that agent type, and check whether the marker reaches its output. LEVER B (saga emitter): add a throwaway rider inside _agent_prompt() at plugins/saga/scripts/execution_spec.py:3244, emit a workflow script from any existing spec, and confirm the rider text appears in the emitted agent() prompts. Record the exact spawn invocation, the raw output excerpt, and a PASS/FAIL for each lever in docs/evidence/issue-704/lever-experiment.md. REMOVE every throwaway file and revert the throwaway rider before you finish -- the evidence document is the only artifact that survives. HARD STOP: if either marker fails to appear, do NOT adapt the plan around it and do NOT proceed. Report the failure, state that the requirements document's R27 blocker reopens, and stop. A lever that cannot be observed working is a failed premise, not a smaller number.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, lever_a_result, lever_b_result, evidence_path, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "prove-both-levers-by-experiment", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"evidence_path": {}, "lever_a_result": {}, "lever_b_result": {}, "notes": {}, "status": {}}, "required": ["status", "lever_a_result", "lever_b_result", "evidence_path", "notes"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["status", "lever_a_result", "lever_b_result", "evidence_path", "notes"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U2: scaffold-plugin-and-manifest ----
// depends_on: U1 (barrier)
// ---- U7: extend-scorer-visual-gating-and-relay-quality ----
// depends_on: U1 (barrier)
// escalation: HALT if either metric cannot be computed without a change to how existing metrics are derived -- a silent shift in the nine committed figures would invalidate the baseline comparison this whole project rests on.
// concurrency chunk 1/2 (max_concurrent=1)
const [U2] = await parallel([
  () =>
    __retry(() => agent(
      "U2: Scaffold the house-style plugin's manifest and documentation, but NOT its style file. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U2.` section. Create plugins/house-style/.claude-plugin/plugin.json (name house-style, version 0.1.0), plugins/house-style/README.md, and plugins/house-style/CHANGELOG.md, matching the shape of plugins/deploy/.claude-plugin/plugin.json. TWO CONSTRAINTS A NAIVE READING DROPS. (a) Do NOT add an `outputStyles` key -- the default `output-styles/` location is auto-discovered, and that key exists only to OVERRIDE the location. (b) The repository caps plugin.json keywords at 10; exceeding it fails a validator. Do NOT create plugins/house-style/output-styles/ or any file inside it -- U3 owns that path exclusively, and creating it here is a concurrent-write collision.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, checks_run, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "scaffold-plugin-and-manifest", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"checks_run": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "checks_run", "notes"], "type": "object"} },
    ), { unitId: "U2", maxAttempts: 3 }),
])
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["status", "files_changed", "checks_run", "notes"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// concurrency chunk 2/2 (max_concurrent=1)
const [U7] = await parallel([
  () =>
    __retry(() => agent(
      "U7: Add a visual-gating measurement and a relay-quality measurement to tools/output_style_scorer.py, then produce their pre-style values. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U7.` section. Label each new metric heuristic where it is heuristic, matching the honesty of the existing bare_identifier_rate. Produce pre-style values by running the scorer over the SAME archived window (--since 2026-07-03 --until 2026-08-07) to a NEW output path: docs/measurements/2026-08-08-extended-metrics.json plus a .md companion. THE ONE THING THAT MUST NOT HAPPEN: docs/measurements/2026-08-07-baseline.json is write-once and is NEVER the --out target. It records behaviour before any custom style existed and that window closed permanently. Before you report done, run `git diff --exit-code docs/measurements/2026-08-07-baseline.json` and include its result in your notes. Also confirm the nine existing metrics are unchanged on the same input.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, checks_run, baseline_untouched, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "extend-scorer-visual-gating-and-relay-quality", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"baseline_untouched": {}, "checks_run": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "checks_run", "baseline_untouched", "notes"], "type": "object"} },
    ), { unitId: "U7", maxAttempts: 3 }),
])
__gate(U7, { unitId: "U7", expectsOutput: true, returns: ["status", "files_changed", "checks_run", "baseline_untouched", "notes"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U3: author-style-file-and-canonical-preamble ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: Author the house-style output style file AND the canonical subagent presentation preamble. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U3.` section, and read docs/brainstorms/2026-08-07-output-styles-requirements.md for the rules themselves (its R1-R16 turn-shape and visual rules, R19-R21 enforcement pointers, R28/R29 contract, R31 tell). Write plugins/house-style/output-styles/house-style.md and plugins/house-style/references/subagent-presentation-preamble.md. FOUR THINGS A NAIVE READING DROPS. (a) `keep-coding-instructions: true` must appear LITERALLY in the frontmatter -- the documented default is false, which silently removes Claude Code's built-in engineering guidance. (b) `force-for-plugin` must be ABSENT, not set to false -- the plugin does not override the operator's own style selection. (c) The tell must contain NO box-drawing characters and must not collide with the existing `\u2605 Insight` marker, which docs/engineering-journal/LEARNINGS.md still uses as one of three conjoined provenance signals. (d) The preamble file is CANONICAL: U5 stamps it into saga's emitter and U6 copies it into 36 agent definition files, and a byte-identity test compares both against this one file -- so write it as standalone text that reads correctly with no surrounding context.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, tell_literal, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "author-style-file-and-canonical-preamble", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "notes": {}, "status": {}, "tell_literal": {}}, "required": ["status", "files_changed", "tell_literal", "notes"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["status", "files_changed", "tell_literal", "notes"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U5: stamp-preamble-into-saga-emitter ----
// depends_on: U3 (barrier)
// escalation: HALT if any existing execution_spec.py test fails after the change and the cause is not obviously the new rider -- do not adjust an existing test to accommodate the stamp.
// ---- U6: duplicate-preamble-into-36-agent-definitions ----
// depends_on: U3 (barrier)
// ---- U8: claude-md-annotation-and-provenance-update ----
// depends_on: U3 (barrier)
// concurrency chunk 1/3 (max_concurrent=1)
const [U5] = await parallel([
  () =>
    __retry(() => agent(
      "U5: Stamp the canonical presentation preamble into every emitted agent() prompt in saga's workflow emitter. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U5.` section. Add a module-level PRESENTATION_RIDER beside BUDGET_RIDER (plugins/saga/scripts/execution_spec.py:464), sourced from plugins/house-style/references/subagent-presentation-preamble.md, and append it in _agent_prompt() at line 3244 -- unconditionally, the same way BUDGET_RIDER and the fan-out reconciliation rider are appended. THREE THINGS A NAIVE READING DROPS. (a) _agent_prompt() is the SINGLE funnel, called from lines 2241, 3215, and 3953 -- do NOT also stamp _emit_thunk, _emit_parallel_wave, or _emit_verify_panel; that would double-apply the rider. (b) Verify panels are deliberately NOT stamped here: saga spawns every verifier as saga:readonly-verifier, which has a definition file and is covered by U6's lever instead. (c) RUN THE EXISTING execution_spec.py TEST SUITE FIRST to establish a green baseline before you change anything -- this file's blast radius is every workflow in every repository, and you need to know which failures you caused. Write tests/test_execution_spec_presentation_rider.py asserting the rider appears in every emitted agent() prompt and is byte-identical to the canonical preamble file.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, checks_run, baseline_suite_green_before, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "stamp-preamble-into-saga-emitter", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"baseline_suite_green_before": {}, "checks_run": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "checks_run", "baseline_suite_green_before", "notes"], "type": "object"} },
    ), { unitId: "U5", maxAttempts: 3 }),
])
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["status", "files_changed", "checks_run", "baseline_suite_green_before", "notes"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// concurrency chunk 2/3 (max_concurrent=1)
const [U6] = await parallel([
  () =>
    __retry(() => agent(
      "U6: Duplicate the canonical presentation preamble into all 36 agent definition files and write the byte-identity test that polices the copies. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U6.` section. The 36 files are exactly those matching plugins/*/agents/*.md, spread across 9 plugins with 25 of them in team-execution. Source the text from plugins/house-style/references/subagent-presentation-preamble.md. TWO THINGS A NAIVE READING DROPS. (a) The test must assert the file count is EXACTLY 36 against an enumerated expectation -- a test that globs its own population at run time cannot detect a 37th agent file that was never given the preamble, which is the drift the test exists to catch. (b) Each file's existing frontmatter (name, description, tools) is load-bearing for agent registration -- insert the preamble into the body without disturbing frontmatter, and confirm tests/test_agent_registration_drift.py still passes. Write tests/test_agent_preamble_identity.py. Do NOT touch any plugin.json or CHANGELOG.md -- U9 owns every release surface, and editing one here is a concurrent-write collision.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, file_count, checks_run, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "duplicate-preamble-into-36-agent-definitions", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"checks_run": {}, "file_count": {}, "files_changed": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "file_count", "checks_run", "notes"], "type": "object"} },
    ), { unitId: "U6", maxAttempts: 3 }),
])
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["status", "files_changed", "file_count", "checks_run", "notes"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// concurrency chunk 3/3 (max_concurrent=1)
const [U8] = await parallel([
  () =>
    __retry(() => agent(
      "U8: Add the reach annotation to ~/.claude/CLAUDE.md and update the provenance procedure for the new tell. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U8.` section. Add a short annotation to the Communication section of ~/.claude/CLAUDE.md stating that its rules live there rather than in a style because CLAUDE.md reaches every subagent while a style reaches only the main thread, and giving the test for any future move: does this rule mean anything to an agent whose output is read by another agent? THREE THINGS A NAIVE READING DROPS. (a) All seven Plain English rules must be BYTE-IDENTICAL before and after -- the annotation is additive, and nothing in that section is pruned, reworded, or reordered. (b) ~/.claude is NOT a git repository, so also commit the annotation's exact text to plugins/house-style/references/claude-md-annotation.md so it can be reconstructed if lost. (c) Update the provenance entry in docs/engineering-journal/LEARNINGS.md (the entry establishing `\u2605 Insight` as one of three conjoined signals) to reference the new tell U3 authored, so the Claude-clone diagnostic keeps working -- do NOT delete the \u2605 Insight signal; it is one of three and the other two still stand.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, plain_english_rules_unchanged, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
      { label: "claude-md-annotation-and-provenance-update", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "notes": {}, "plain_english_rules_unchanged": {}, "status": {}}, "required": ["status", "files_changed", "plain_english_rules_unchanged", "notes"], "type": "object"} },
    ), { unitId: "U8", maxAttempts: 3 }),
])
__gate(U8, { unitId: "U8", expectsOutput: true, returns: ["status", "files_changed", "plain_english_rules_unchanged", "notes"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U4: style-file-contract-tests ----
// depends_on: U3, U5, U6, U8 (barrier)
const U4 = await agent(
  "U4: Write the style-file contract tests. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U4.` section. Write tests/test_house_style_contract.py asserting: plugins/house-style/output-styles/house-style.md exists at the plugin ROOT (not under .claude-plugin/); its frontmatter sets keep-coding-instructions to the literal true; force-for-plugin is absent; a placard section naming what the style suppresses exists; the tell is present as a single literal string and contains no character in the box-drawing Unicode block (U+2500-U+257F); plugin.json parses, carries the required fields, has at most 10 keywords, and has no outputStyles key. THE THING THAT MAKES THIS TEST WORTH WRITING: demonstrate each assertion actually fails when its target is removed. Mutate the frontmatter, the placard, and the tell one at a time, confirm the corresponding test goes red, and restore. A contract test that passes on a file with the contract stripped out is worse than no test, because it reports safety that is not there. Record the three mutation results in your notes.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, mutation_results, checks_run, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "style-file-contract-tests", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"checks_run": {}, "files_changed": {}, "mutation_results": {}, "notes": {}, "status": {}}, "required": ["status", "files_changed", "mutation_results", "checks_run", "notes"], "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["status", "files_changed", "mutation_results", "checks_run", "notes"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U9: release-surfaces-journal-and-ceiling-sweep ----
// depends_on: U2, U3, U4, U5, U6, U7, U8 (barrier)
// escalation: HALT if the full local gate does not go green -- a red gate is the finding, not something to route around by narrowing the test scope.
const U9 = await agent(
  "U9: Land every release surface, write the journal entries, and sweep for inflated reach claims. Read the plan at docs/plans/2026-08-08-issue-704-house-style-output-style-plugin-plan.md as your authoritative spec; work its `### U9.` section. Bump plugin.json version and add a CHANGELOG.md entry for house-style and for each of the 9 plugins U6 touched; add the house-style entry to .claude-plugin/marketplace.json with a version matching its plugin.json. FOUR THINGS A NAIVE READING DROPS. (a) marketplace.json editing footgun: when adding the new entry, the replaced text must include the previous entry's closing brace, the array's closing bracket, AND the trailing top-level version line, so the new entry lands INSIDE the plugins array -- a double-`]` has broken this file's parse more than once. Run `python3 -m json.tool .claude-plugin/marketplace.json` immediately after editing. (b) Plugin count becomes 12, up from 11. (c) Write a LEARNINGS entry for whatever the lever experiment (U1) actually showed, and a DECISIONS entry recording the plan's KTDs -- the journal lands in the SAME commit as the change, never deferred. (d) CEILING SWEEP: grep every artifact this run produced for a subagent-reach claim above 45.7%, and for the literal 89.4. The only permitted occurrences of 89.4 are the ones explicitly labelled as the superseded figure. Then run the full local gate: ruff check, ruff format --check, mypy plugins/ scripts/ tests/ --ignore-missing-imports, bandit -r plugins/, pytest --cov=plugins.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys status, files_changed, plugin_count, gate_results, notes -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release-surfaces-journal-and-ceiling-sweep", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "gate_results": {}, "notes": {}, "plugin_count": {}, "status": {}}, "required": ["status", "files_changed", "plugin_count", "gate_results", "notes"], "type": "object"} },
)
__gate(U9, { unitId: "U9", expectsOutput: true, returns: ["status", "files_changed", "plugin_count", "gate_results", "notes"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw __halt(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}

return {
  units: { "U1": U1, "U2": U2, "U7": U7, "U3": U3, "U5": U5, "U6": U6, "U8": U8, "U4": U4, "U9": U9 },
  advisory_corrections: __advisories,
}
