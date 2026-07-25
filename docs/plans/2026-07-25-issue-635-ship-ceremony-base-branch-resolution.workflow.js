// ===========================================================================
// issue-635-ship-ceremony-base-branch-resolution -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "issue-635-ship-ceremony-base-branch-resolution",
  description: "Issue #635: ship_ceremony assumes every PR is main-based at five sites (A branch_delete deletes the BASE branch local+origin, B checkout_main hardcodes main, C/D both gh pr create calls omit --base, E _do_merge reads refs/heads/main so the rollback manifest records a bogus squash SHA). Replaces five independent guesses with one resolve_ceremony_refs() ladder (PR-authoritative > opened-resource manifest > refuse; saga['branch'] is never a rung), adds a non-acknowledgeable BRANCH_DELETE_TARGETS_BASE hazard that refuses before dispatch and before save, and grows --operator-confirmed into the typed branch_delete:<target> payload that #526's own 'revisit when' clause anticipated. Release surface saga 0.115.0 only (no fleet_commons touch, no mission-control verb). Fully serialized U1->U2->U3->U4->U5 under the operator cap of 3: refute-3 panels on the two behavior-changing units ride at the unit tier and would overlap a running unit otherwise.",
}
const settlement = {"casualty_threshold_percent":0,"dispatch_id":"workflow:3d586c0f00ae862d6015dbda","driver":{"invocation_id":null,"units":[{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U1","workflow_unit_id":"U1"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U2","workflow_unit_id":"U2"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U2b","workflow_unit_id":"U2b"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U2c","workflow_unit_id":"U2c"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U3","workflow_unit_id":"U3"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:tests_added","result_key":"tests_added"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U4","workflow_unit_id":"U4"},{"return_keys":[{"deliverable":"return:files_changed","result_key":"files_changed"},{"deliverable":"return:summary","result_key":"summary"}],"settlement_unit_id":"U5","workflow_unit_id":"U5"}]},"max_attempts":3,"schema":"dispatch_settlement.v1","site":"workflow","units":[{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U1","unit_id":"U1"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U2","unit_id":"U2"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U2b","unit_id":"U2b"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U2c","unit_id":"U2c"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U3","unit_id":"U3"},{"deliverables":["structured-result","return:files_changed","return:tests_added","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U4","unit_id":"U4"},{"deliverables":["structured-result","return:files_changed","return:summary"],"idempotency_key":"workflow:3d586c0f00ae862d6015dbda:U5","unit_id":"U5"}]}
const lease = {"aggregate_limit":7,"batch_id":null,"claim_ttl_seconds":30,"execution_ttl_seconds":300,"generated_runtime_filesystem_access":false,"invocation_id":null,"mutation":"read-write","owner_id":null,"policy_sha256":"b985631b1a874a0817a3cac49b27565875fb5dedd3ad2008cf397dc640d43a0a","requires_prelaunch_reservation":true,"reservation_width":1,"schema":"workflow_lease_reservation.v1","session_limit":1,"slots":["slot-001"],"spec_sha256":"3d586c0f00ae862d6015dbda82c695e4fc3f70413be01a398cc736f8e89d25ac","workload_unit_ids":["U1","U2","U2b","U2c","U3","U4","U5"]}

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

// ---- U1: ceremony ref resolution core: resolve_ceremony_refs ladder + default-branch resolver + base sidecar ----
const U1 = await agent(
  "U1: In plugins/saga/scripts/ship_ceremony.py at base 474fd3cc, add a CeremonyRefs dataclass (head, base, source) plus resolve_ceremony_refs(saga, *, repo_root, runner) implementing KTD2's ladder: (1) when the saga carries a pr_refs entry, `gh pr view <n> --json headRefName,baseRefName`; (2) on failure or no PR, head from the opened-resource manifest's ceremony-branch: entry (ship_teardown.read_manifest, registered at :418 and :863 with kind='branch') and base from the new per-saga sidecar; (3) raise CeremonyRefsError naming both exhausted sources. saga['branch'] is NOT a rung and must never be returned. Add resolve_default_branch(repo_root, runner) using `git symbolic-ref refs/remotes/origin/HEAD` with a `gh repo view --json defaultBranchRef` fallback, raising rather than defaulting to the literal 'main' (KTD5). Add read/write helpers for the base sidecar as a per-saga JSON file beside merge_expectation.json / rollback_manifest.json, following {#ceremony-sidecars-forward-only-undo-346} (KTD4 \u2014 a tick field rolls with the checkout, which IS the defect). Change NO call site in this unit. Tests per the plan's U1 scenarios in tests/test_ship_ceremony.py: rung 1 wins with saga['branch'] deliberately set to a different value and never consulted; rung 2 answers when the gh call fails; exhausted ladder raises and names both missing sources; saga['branch'] is never returned even when it is the only value present; resolve_default_branch returns the symbolic-ref answer, falls back to gh, and raises rather than defaulting to 'main'. Read the plan at docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U1, R1/R7, KTD2/KTD4/KTD5) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "ceremony ref resolution core: resolve_ceremony_refs ladder + default-branch resolver + base sidecar", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U2: destructive paths consume the resolver: branch_delete target + manifest key (A), merge SHA probes (E) ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: In plugins/saga/scripts/ship_ceremony.py (post-U1), make _do_branch_delete (:549) resolve ONCE via resolve_ceremony_refs and use that single value for the git rev-parse, the git branch -d, the git push origin --delete, AND _branch_resource_id() for the _close_if_registered manifest close at :562-564 (KTD1/R3 \u2014 deriving the delete target and the manifest key independently from the same wrong field is why the live incident also silently diverged the teardown ledger). Keep the existing empty/'main' guard as defense in depth. Make _do_merge (:508) probe refs/heads/<resolved base> instead of the hardcoded refs/heads/main for BOTH pre_merge sha and merge sha, keeping the returned key name pre_merge_main_sha EXACTLY as-is (it is a keyword argument of ship_undo.append_entry at ship_undo.py:250, passed at ship_ceremony.py:805 and pinned by four test assertions, and ship_undo.py:14 records it as audit-only forensic context that undo() never consumes programmatically \u2014 renaming buys zero behavior and changes a cross-module signature on the undo path) (R6). Tests per the plan's U2 scenarios in tests/test_ship_ceremony.py, ALL red-first against 474fd3cc: the headline regression \u2014 a leaf-into-outcome fixture where the last tick save happened on the base branch so saga['branch']=='outcome/demo', asserting the git branch -d and git push origin --delete argv name the HEAD branch and that no command in the transition names the base; the closed manifest entry is ceremony-branch:<head> and that entry's status becomes closed; _do_merge on an outcome-based PR probes refs/heads/outcome/demo for BOTH SHAs and records a merge_sha equal to the base ref's post-merge tip, distinct from pre_merge_main_sha where the base advanced; revert-safety (red-first) \u2014 against current code the recorded merge_sha is main's UNCHANGED, REACHABLE tip, so ship_undo._undo_merge's SHA_UNREACHABLE guard (ship_undo.py:360) never fires and git revert --no-edit succeeds against an unrelated healthy commit on the default branch and pushes it; assert the recorded merge_sha is a commit introduced by THIS merge, because the guard is not what stands between a mis-recorded SHA and a bad revert; _do_merge on a main-based PR is behaviorally byte-identical to today. Do not weaken any of the 47 existing branch_delete/checkout_main assertions (R9) \u2014 if one asserts the defective behavior itself, change it and name it explicitly in your summary with justification. Read the plan at docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U2, R1/R3/R6/R9/R10, KTD1) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "destructive paths consume the resolver: branch_delete target + manifest key (A), merge SHA probes (E)", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U2b: the undo path applies the revert to the recorded base (defect F) + R13 docstring corrections ----
// depends_on: U2 (barrier)
const U2b = await agent(
  "U2b: Fix defect F and requirement R13 in plugins/saga/scripts/ship_undo.py and plugins/saga/scripts/ship_ceremony.py. CONTEXT: U1 and U2 are ALREADY COMPLETE in the working tree on branch work/635-ceremony-ref-resolution (uncommitted; 130 ceremony/undo/hazard tests pass). Do NOT redo their work. U2 made _do_merge record the CORRECT squash sha against the PR's resolved base. This unit fixes the other half: the undo path still APPLIES that sha to the wrong branch.\n\nDEFECT F (the fix): ship_undo._undo_merge hardcodes 'main' THREE times at ship_undo.py:363-367 -- `if current != \"main\": git checkout main`, then `git revert --no-edit <merge_sha>`, then `git push origin main` -- regardless of the ceremony's base. So a correctly recorded outcome/demo squash sha is still reverted ON MAIN. When the outcome branch has already landed on main, that revert applies CLEANLY and strips the leaf's work from main. Make all three operations target the ceremony's recorded base, resolved from the rollback-manifest entry (R12). Extend ship_undo.append_entry to record the base on the merge entry -- _do_merge already resolves it under U2, so pass it through; this avoids a network call at undo time. BACKWARD COMPATIBILITY IS MANDATORY: an entry with no recorded base (every manifest written before this ships) MUST fall back to the repo default branch, preserving today's behavior exactly.\n\nDO NOT change ship_undo._sha_reachable (:162-182). It is `git cat-file -e <sha>^{commit}`, a pure EXISTENCE probe, honestly documented as best-effort. F is a wrong-target defect, not a wrong-probe one. Widening it into an ancestry check is out of scope.\n\nR13 (correct two false claims U2 shipped into docstrings in plugins/saga/scripts/ship_ceremony.py): (1) the _do_merge docstring at ~:843-844 asserts 'The guard is not what stands between a mis-recorded sha and a bad revert; recording the right sha is.' The second half is FALSE until this unit's R12 fix lands, because _undo_merge reverts on main regardless. Rewrite it to state the true joint property: recording the right sha (U2) AND applying it to the right branch (U2b) are both required, and the SHA_UNREACHABLE guard is an existence check that catches neither. (2) the same docstring at ~:847 says pre_merge_main_sha is 'pinned by four test assertions'. At 474fd3cc there are four REFERENCES but only TWO assertions (tests/test_ship_ceremony.py:920-921); tests/test_ship_undo.py:596 is a local variable assignment and :619 is a dict literal in a fixture payload. Say 'four references, two of them assertions'. The conclusion (freeze the key name) is correct and stays.\n\nTESTS (tests/test_ship_undo.py), red-first against the pre-U2b tree: the headline -- a merge entry recording base 'outcome/demo', asserting the checkout, the git revert, and the git push argv ALL name outcome/demo and that NO command in the transition names main; the leaf-landed-on-main hazard the refute panel found -- outcome branch already merged to main, undo of the leaf's merge must not touch main; backward compatibility -- a manifest entry with NO recorded base still undoes against the repo default branch, byte-identical to today; a main-based ceremony is behaviorally unchanged. Do not weaken any existing assertion in tests/test_ship_undo.py.\n\nRead the plan at docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U2b, defect F, R12/R13, KTD10) as your authoritative spec. Report your changes accurately and completely: enumerate EVERY hunk in EVERY file you touch, and do not cite a statistic you have not reproduced with the exact command you name.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "the undo path applies the revert to the recorded base (defect F) + R13 docstring corrections", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2b, { unitId: "U2b", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U2c: defect F red-first evidence + accurate change-set enumeration ----
// depends_on: U2b (barrier)
const U2c = await agent(
  "U2c: Establish the R10 red-first evidence for defect F and produce an ACCURATE, fully enumerated account of the shipped F/R12/R13 change set. This unit writes almost no new code -- its deliverable is verified evidence.\n\nSTATE OF THE TREE (do not redo any of it): U1, U2 and U2b are complete and UNCOMMITTED on branch work/635-ceremony-ref-resolution. After U2b's refute panel, the driver repaired two real defects the panel proved, and `uv run pytest -q -p no:randomly tests/test_ship_undo.py tests/test_ship_ceremony.py tests/test_ceremony_hazards.py --no-cov` is green at 136 passed. The two repairs were: (1) ship_ceremony._do_merge's docstring no longer quotes ANY pre_merge_main_sha reference count -- U2b's 'four references (two of them assertions)' was measured at 474fd3cc but ships in a working tree holding twelve, so the number was deleted rather than corrected a third time; (2) ship_undo._merge_entry_base now floors a base-less entry at the literal LEGACY_MERGE_BASE ('main') instead of routing through a refs/remotes/origin/HEAD lookup, and ship_undo._default_branch was DELETED because that was its only production caller. Rationale: a pre-#635 entry's merge_sha was read by a _do_merge that probed refs/heads/main verbatim, so main is provably where it came from; resolving the current default branch would revert on 'trunk' in a trunk-default repo. tests/test_ship_undo.py's backward-compat test was renamed to test_undo_merge_without_recorded_base_floors_at_legacy_main and now asserts symbolic-ref is NOT called, and the two orphaned _default_branch unit tests were replaced by test_base_less_entry_ignores_a_non_main_default_branch.\n\nTASK 1 -- R10 red-first, reproducibly. U2b claimed a red state of '5 failed' that a verifier proved does not exist under any reconstruction. Establish the real evidence: for EACH of the defect-F behavioral tests in tests/test_ship_undo.py (the recorded-base target test, the leaf-landed-on-main hazard test, the legacy-floor test, and test_base_less_entry_ignores_a_non_main_default_branch), demonstrate it FAILS against the pre-F code and PASSES now. Use a reproducible method and record it exactly: copy the current ship_undo.py aside, restore the pre-F body of _undo_merge and _merge_entry_base (git show 474fd3cc:plugins/saga/scripts/ship_undo.py is the pre-F source), run the named tests, capture verbatim output, then restore. Record the EXACT command and its VERBATIM output for both the red and green runs. If a test does not go red, say so plainly -- a test that cannot fail against the old code is not a regression test and you must report it as such rather than manufacturing a red state.\n\nTASK 2 -- verify the two repairs are correct and complete. Confirm _default_branch has no remaining references anywhere in plugins/ or tests/; confirm _merge_entry_base's signature change reached its only call site; confirm no docstring in the F change set quotes a numeric count of anything; confirm the LEGACY_MERGE_BASE rationale comment now matches what the code actually does. Fix anything that does not hold.\n\nTASK 3 -- accurate enumeration. List EVERY hunk in EVERY file the F/R12/R13 change set touches (plugins/saga/scripts/ship_undo.py, plugins/saga/scripts/ship_ceremony.py, tests/test_ship_undo.py), derived from an actual diff against 474fd3cc, with no hunk omitted.\n\nEVIDENCE DISCIPLINE -- three consecutive panels have refuted this plan's units for exactly this, so it is the primary acceptance criterion for this unit. Quote NO number, count, statistic, or pass/fail tally you have not reproduced yourself with a command you name verbatim in your report, run against the WORKING TREE (not against 474fd3cc, unless you explicitly label it as the baseline and say so). Do not describe a test as 'existing' or 'unchanged' relative to 474fd3cc if U1/U2/U2b created it -- those units' work is uncommitted, so git shows it as new. Prefer 'I did not measure this' to an unverified figure. If you cannot reproduce a claim, drop the claim.\n\nRead docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U2b, defect F, R10/R12/R13, KTD10 and KTD10a) as your authoritative spec.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "defect F red-first evidence + accurate change-set enumeration", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U2c, { unitId: "U2c", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U3: base-aware transitions: checkout_main (B) and both gh pr create --base call sites (C, D) ----
// depends_on: U2c (barrier)
const U3 = await agent(
  "U3: In plugins/saga/scripts/ship_ceremony.py (post-U1), make _do_checkout_main (currently :889) check out the resolved base rather than the hardcoded 'main', but KEEP its return value as saga.get('branch') \u2014 DO NOT change it. That value is the checkout_main rollback-manifest entry's branch, consumed by ship_undo._restore_pre_ceremony_checkout (ship_undo.py, currently :432), whose documented contract is restoring the PRE-CEREMONY checkout (the saga's own branch), not the branch that was checked out; returning the resolved base would make current == branch true immediately after checkout_main and turn that undo step into a permanent silent no-op. Add --base <resolved> to BOTH gh pr create invocations \u2014 the fresh-create path in _do_open_pr (currently :746, the gh pr create at :790) and the draft create in start() (currently :1211, the gh pr create at :1245). Give start() an explicit base parameter plus its CLI surface in _build_parser, defaulting to resolve_default_branch(), and record the chosen base to the U1 sidecar so later transitions resolve without a PR query. Leave _do_open_pr's existing-draft path (the pr_refs branch that flips ready via gh pr ready) untouched \u2014 it must not re-create a PR. Do not change the _saga_short_id argument lists in either saga save call (explicit non-goal: that split-brain is out of scope and must not be made worse). Tests per the plan's U3 scenarios in tests/test_ship_ceremony.py, red-first: checkout_main on an outcome-based PR issues git checkout outcome/demo while a main-based PR still issues git checkout main; undo-contract pin (a regression test that must pass BOTH before and after the change) \u2014 checkout_main's returned branch is still saga['branch'], so the checkout_main rollback-manifest entry keeps restoring the operator's pre-ceremony checkout; _do_open_pr fresh-create argv contains --base <resolved>; the existing-draft path is unchanged; start() with an explicit base records it to the sidecar and passes it to gh pr create --draft; start() with no explicit base uses resolve_default_branch() and does not emit the literal 'main' when the resolved default differs. Read the plan at docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U3, R4/R5/R10, KTD5) as your authoritative spec.\n\nANCHOR DISCIPLINE (mandatory, and the reason four consecutive verify panels have refuted units on this plan). Every line number in this prompt was re-derived against the WORKING TREE at dispatch time, NOT against 474fd3cc \u2014 U1/U2/U2b/U2c are complete and uncommitted, and they added 381 lines to ship_ceremony.py, 73 to ship_undo.py, 690 to tests/test_ship_ceremony.py and 264 to tests/test_ship_undo.py. Treat every cited line as ADVISORY and the SYMBOL NAME as authoritative: locate each symbol by name (grep for its `def`), and if the cited line does not hold it, use the real one and say so in your report. Symmetrically, do not quote a coordinate or a count in your own report that you measured BEFORE your own edits shifted it \u2014 re-run the measurement after your last edit, or omit the number. Prefer 'I did not measure this' to a stale figure.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "base-aware transitions: checkout_main (B) and both gh pr create --base call sites (C, D)", model: "sonnet", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// ---- U4: refuse-before-mutation hazard + typed branch_delete:<target> operator confirmation ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Add a BRANCH_DELETE_TARGETS_BASE hazard to plugins/saga/scripts/ceremony_hazards.py following the existing MERGE_NOT_LANDED shape (ceremony_hazards.py, constant at :75, probe at :205): probed only for the branch_delete transition, fires when the resolved head equals the resolved base, acknowledgeable=False (there is no legitimate case for deleting the PR base, so there is nothing to acknowledge), and appended to HAZARD_REGISTRY (:77). This gives R2 the refusal shape #526/#346/#347 rely on \u2014 ceremony_hazards.detect() runs in run() before _RUNNERS[upcoming] dispatch and before saga.py save, so the ledger is provably unadvanced. Then in ship_ceremony.py run() (currently :1089) accept the qualified form --operator-confirmed branch_delete:<target>: a bare 'branch_delete' refuses with a message naming the resolved target so the operator's next invocation carries a value they have actually seen; a qualified target that does not match the resolved target refuses; the existing uniform mismatch rule and every other transition's bare grammar are unchanged (KTD6, honoring #526's own 'revisit when' clause about confirmations needing an argument of their own). Update _build_parser's help text. Tests, red-first, in tests/test_ceremony_hazards.py and tests/test_ship_ceremony.py: the hazard fires when head==base and is NOT acknowledgeable via --acknowledge-hazard; the hazard refusal happens before dispatch and before save (assert no git command ran and ceremony_transition is unchanged); bare --operator-confirmed branch_delete refuses with the resolved target in the error text; a wrong qualified target refuses and the resolved one proceeds; every other transition's bare confirmation grammar regression-passes against the existing gate tests. Read the plan at docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U4, R2/R8/R9/R10, KTD3/KTD6) as your authoritative spec.\n\nANCHOR DISCIPLINE (mandatory, and the reason four consecutive verify panels have refuted units on this plan). Every line number in this prompt was re-derived against the WORKING TREE at dispatch time, NOT against 474fd3cc \u2014 U1/U2/U2b/U2c are complete and uncommitted, and they added 381 lines to ship_ceremony.py, 73 to ship_undo.py, 690 to tests/test_ship_ceremony.py and 264 to tests/test_ship_undo.py. Treat every cited line as ADVISORY and the SYMBOL NAME as authoritative: locate each symbol by name (grep for its `def`), and if the cited line does not hold it, use the real one and say so in your report. Symmetrically, do not quote a coordinate or a count in your own report that you measured BEFORE your own edits shifted it \u2014 re-run the measurement after your last edit, or omit the number. Prefer 'I did not measure this' to a stale figure.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "refuse-before-mutation hazard + typed branch_delete:<target> operator confirmation", model: "opus", effort: "high", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}, "tests_added": {}}, "required": ["files_changed", "tests_added", "summary"], "type": "object"} },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// ---- U5: release surfaces saga 0.115.0, KTD6 doc migration, engineering journal ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Bump plugins/saga/.claude-plugin/plugin.json 0.114.0 -> 0.115.0 and sync .claude-plugin/marketplace.json. Do NOT bump fleet-core (fleet_commons/ is untouched) or mission-control (no verb added). Write the plugins/saga/CHANGELOG.md entry covering all six sub-defects (A-F, including F: ship_undo._undo_merge reverting on main) and the confirmation-grammar change. Update the ONLY saga drift-guard version pin in-commit: tests/test_saga_plugin.py:48. Do NOT touch tests/test_liveness_events.py or tests/test_team_execution_liveness.py \u2014 verified at 474fd3cc, those pin fleet_core_version == '0.23.0' (test_liveness_events.py:698, test_team_execution_liveness.py:179 and :409), NOT the saga version, and this PR ships no fleet-core bump; editing them would assert a saga string against a fleet-core field and fail. Migrate the two documentation surfaces that name the old invocation grammar (KTD6): plugins/saga/skills/work/SKILL.md:750-752 and plugins/saga/skills/work/references/pr-continuation-loop.md:100-102 \u2014 both currently document `run --operator-confirmed branch_delete` and must document the qualified branch_delete:<target> form. Add a DECISIONS.md entry {#ceremony-ref-resolution-635} mirroring KTD1-KTD6 with rejected alternatives and a revisit-when, and a LEARNINGS.md entry recording the non-obvious mechanism: a rolling tick field consumed as ceremony state produced a THREE-part failure (base deleted, wrong manifest key closed silently by _close_if_registered's by-design no-op, real branch entry left open forever because _teardown_attempt_closes handles only scratch and worktree kinds, permanently blocking teardown) \u2014 with the generalizable rule that a destructive target must resolve from write-once ceremony-scoped evidence, never from a field re-derived on every save. Follow the LEARNINGS placement convention actually practiced in the file. Verify `uv run python scripts/check_release_surface_parity.py` exits 0 and re-check sibling-PR version collisions at merge time. Read the plan at docs/plans/2026-07-25-issue-635-ship-ceremony-base-branch-resolution-plan.md (U5, R11) as your authoritative spec.\n\nANCHOR DISCIPLINE (mandatory, and the reason four consecutive verify panels have refuted units on this plan). Every line number in this prompt was re-derived against the WORKING TREE at dispatch time, NOT against 474fd3cc \u2014 U1/U2/U2b/U2c are complete and uncommitted, and they added 381 lines to ship_ceremony.py, 73 to ship_undo.py, 690 to tests/test_ship_ceremony.py and 264 to tests/test_ship_undo.py. Treat every cited line as ADVISORY and the SYMBOL NAME as authoritative: locate each symbol by name (grep for its `def`), and if the cited line does not hold it, use the real one and say so in your report. Symmetrically, do not quote a coordinate or a count in your own report that you measured BEFORE your own edits shifted it \u2014 re-run the measurement after your last edit, or omit the number. Prefer 'I did not measure this' to a stale figure.\n\nDELIVERED STATE AS OF DISPATCH \u2014 write the CHANGELOG and journal entries against THIS, not against the plan's original intent. U1-U4 are complete and uncommitted; the driver then repaired two findings U4's refute panel proved, so the tree is ahead of U4's own report.\n\nFILES IN THE CHANGE SET (five, verified by git status): plugins/saga/scripts/ship_ceremony.py, plugins/saga/scripts/ship_undo.py, plugins/saga/scripts/ceremony_hazards.py, tests/test_ship_ceremony.py, tests/test_ship_undo.py, tests/test_ceremony_hazards.py. Note ceremony_hazards.py IS in the set (U4) \u2014 do not describe it as untouched.\n\nSIX SUB-DEFECTS SHIPPED (A-F). F is the one the plan gained mid-flight: ship_undo._undo_merge checked out, reverted on, and pushed `main` literally, so fixing E (recording the right squash sha) without F would have moved the bug rather than removed it. A base-less legacy rollback entry deliberately floors at the LITERAL 'main' (ship_undo.LEGACY_MERGE_BASE), NOT the repo's resolved default branch \u2014 such an entry's merge_sha was read by a pre-#635 _do_merge that probed refs/heads/main verbatim, so main is provably where it came from. Provenance beats currency; say so in the journal.\n\nTWO POST-PANEL REPAIRS TO REFLECT:\n1. The BRANCH_DELETE_TARGETS_BASE hazard's reachability is RUNG-SCOPED and the CHANGELOG must not overclaim it. On resolver rung 1 the head and base both come from one `gh pr view --json headRefName,baseRefName` record and GitHub forbids head == base on a same-repo PR, so the probe is inert there BY CONSTRUCTION \u2014 correctly, since rung 1 is authoritative. It is a backstop for rung 2, where the head comes from the opened-resource manifest and the base from the PR: two independent records that can agree wrongly, which is the outcome/norns-next-horizon incident shape. New test test_branch_delete_targets_base_fires_on_the_rung_2_incident_topology covers that path and is red-first (remove the probe and the ceremony reaches `git rev-parse` on the base branch).\n2. The typed confirmation changed one output: `--operator-confirmed merge:x` with `merge` upcoming previously hit the uniform MISMATCH refusal (raw-string compare) and now hits the 'does not take a confirmation target' refusal, because the guard compares the parsed transition name. Both refuse; only the wording moved. CLI-unreachable before the change (argparse choices= rejected the colon form), Python-API reachable. Pinned by test_qualified_target_on_a_transition_that_takes_none_refuses. Mention it in the CHANGELOG as a behavior note, not a breaking change.\n\nGATES ALREADY GREEN AT DISPATCH, driver-run after the last edit \u2014 re-run them yourself, do not quote these numbers without reproducing them: full `uv run pytest -q` 5487 passed / 0 failed / 1 skipped; `uv run ruff check .` -> []; `uv run ruff format --check .` -> 439 files already formatted; `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` -> exit 0, Success, no issues in 269 source files. check_release_surface_parity.py is YOUR gate and has not been run yet.\n\nThe LEARNINGS entry's non-obvious mechanism is worth stating carefully: a rolling saga tick field (`branch`, re-stamped from `git branch --show-current` on EVERY save at saga.py:566) was consumed as if it were ceremony state, so on a leaf-into-outcome PR whose last save happened on the base branch it named the base \u2014 and three separate call sites each guessed it independently. The generalizable rule: a field that is re-derived on every write cannot be read as a record of what happened at an earlier moment; ceremony-scoped decisions need ceremony-scoped evidence, written once at the moment the fact becomes true.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces saga 0.115.0, KTD6 doc migration, engineering journal", model: "sonnet", effort: "medium", schema: {"additionalProperties": true, "properties": {"files_changed": {}, "summary": {}}, "required": ["files_changed", "summary"], "type": "object"} },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
