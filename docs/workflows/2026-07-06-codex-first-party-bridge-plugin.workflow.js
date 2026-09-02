// ===========================================================================
// codex-first-party-bridge-plugin -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "codex-first-party-bridge-plugin",
  description: "Issue #476: first-party plugins/codex/ guarded delegate (agy-grammar mirror, codex.delegation.v1), synchronous supervised codex exec runner with evidence bundle + bridge_receipt.v1 emission, enforced read-only review / patch-capture task modes, registry+dispatch rewire off codex:codex-rescue, marketplace-plugin retirement dereference, lifecycle proof. SERIALIZED unit chain (every unit depends_on its predecessor) deliberately: operator rate-limit cap is max 3 concurrent non-haiku agents / 6 haiku; the only parallelism is the n=3 verify panels on U2/U3/U6, so peak concurrency is exactly 3 by construction (precedent: 2026-07-06 http-bridge-receipt-pair spec, serialized for the same reason). Serialization also prevents concurrent edits to plugins/codex/scripts/codex_delegate.py (touched by U1/U2/U3) and the shared saga test files. WAVE-A GUARDRAIL (journal {#verify-panels-blind-to-uncommitted-tree}): every worker commits its completed unit on the branch so verify-panel worktrees (cut from main) can materialize committed state; verifier prompts are patched post-emit with mandatory branch materialization + examined-sha quoting.",
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

// ---- U1: plugin scaffold + codex.delegation.v1 envelope schema + drift-guard move ----
const U1 = await agent(
  "U1: Create plugins/codex/ \u2014 .claude-plugin/plugin.json (name codex, version 0.1.0, Infiquetra author block per repo CLAUDE.md), README.md, CHANGELOG.md, commands/delegate.md, skills/codex-delegate/SKILL.md, agents/codex-coder.md + agents/codex-reviewer.md (mirror plugins/agy/ structure), vendor plugins/fleet-core/scripts/fleet_commons_shim.py BYTE-IDENTICALLY into plugins/codex/scripts/ and extend the hardcoded vendored-copy list in tests/test_fleet_commons_resolution.py with the codex copy. Create plugins/codex/scripts/codex_delegate.py with the codex.delegation.v1 envelope schema (roles coder|reviewer, modes, review lenses, evidence levels, status vocabulary mirroring agy.delegation.v1 minus inapplicable members), Envelope dataclass + validation (EnvelopeError, fail loud), and the receipt builder calling fleet_commons_shim.load('bridge_receipt').emit_receipt(engine_id='codex', transport='cli', ...) with emit-only-when-launched semantics (agy _supervised_receipt parity, plugins/agy/scripts/agy_delegate.py:1390-1412). SAME COMMIT (KTD6): move 'codex-bridge' from PENDING_EMITTERS to IN_REPO_EMITTERS -> plugins/codex/scripts/codex_delegate.py in tests/test_bridge_receipt_drift.py and update its pending-entry assertions \u2014 the guard sentinels on plugins/codex/ existing, so the tree reds if these land apart. Add tests/test_codex_delegate_contract.py (envelope round-trip valid/invalid) and tests/test_codex_plugin.py (plugin.json required fields). Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U1, R1/R8, KTD1/KTD6) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "plugin scaffold + codex.delegation.v1 envelope schema + drift-guard move", model: "sonnet", effort: "high" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// ---- U2: supervised synchronous runner + evidence bundle + receipt ----
// depends_on: U1 (barrier)
const U2 = await agent(
  "U2: In plugins/codex/scripts/codex_delegate.py implement the supervised synchronous runner: launch codex exec --json -o <bundle>/last-message.txt -s <sandbox> -m <model> -c model_reasoning_effort=<effort> --ephemeral (KTD3, verified live on codex-cli 0.142.5 \u2014 --effort is NOT a flag), prompt delivered via stdin then EXPLICITLY closed (codex appends piped stdin as a <stdin> block and blocks reading an open pipe), --codex-bin override for hermetic tests (mirror agy's --agy-bin). Supervise with wall-clock --timeout-seconds (default 900) + no-output watchdog; on expiry KILL the process tree and record a terminal status \u2014 on-disk state must NEVER say running (R4). Install a SIGTERM/SIGINT die-clean handler with the SAME semantics: kill the codex process tree, finalize a terminal bundle, exit nonzero \u2014 a caller's Bash-tool timeout is the expected delivery vector (R4). Omit -m when the envelope names no model (codex falls back to the user config default). Write the evidence bundle at .claude/codex/runs/<run-id>/: envelope.json, prompt.txt, command.json, transcript.jsonl (raw JSONL from stdout, tolerant of malformed lines), last-message.txt, result.json, projection.md; best-effort token accounting parsed from JSONL usage events (degrade to nulls, never fail the run). Build the bridge_receipt.v1 iff the process actually launched (pid/argv/exit_code runner section); launch failure (missing bin, OSError) -> fail-loud status, codex_launched=false, NO receipt, result still validates. Support --validate-only/--dry-run stopping after the bundle skeleton. Extend tests/test_codex_delegate_contract.py per the plan's U2 scenarios (fake-bin success/launch-failure/timeout/SIGTERM-mid-run die-clean/malformed-JSONL). Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U2, R1/R3/R4/R8, KTD2/KTD3) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "supervised synchronous runner + evidence bundle + receipt", model: "opus", effort: "high" },
)
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U2 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U2_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U2 (supervised synchronous runner + evidence bundle + receipt). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "supervised synchronous runner + evidence bundle + receipt verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U2 },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U2 (supervised synchronous runner + evidence bundle + receipt). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "supervised synchronous runner + evidence bundle + receipt verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U2 },
  ), { unitId: "U2", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U2 (supervised synchronous runner + evidence bundle + receipt). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "supervised synchronous runner + evidence bundle + receipt verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U2 },
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

// ---- U3: modes: enforced read-only review, patch-capture task ----
// depends_on: U2 (barrier)
const U3 = await agent(
  "U3: In plugins/codex/scripts/codex_delegate.py implement the mode surfaces (R2, KTD5): reviewer role (review / second-opinion lenses) runs -s read-only against the live repo with a post-run diff scan proving non-mutation against a pre-run `git status --porcelain` snapshot \u2014 any NEW dirt relative to the baseline maps to status out_of_scope_mutation with the diff evidence in the bundle; a PRE-DIRTY operator tree must NOT false-positive (test this case); coder role (task) runs -s workspace-write inside a disposable remotes-stripped clone (--cd <clone> --skip-git-repo-check), captures the resulting diff as a patch artifact (apply_policy preserve-patch \u2014 never auto-apply to the live tree in v1), honors write_set scoping (out-of-set mutation flagged), and tears the clone down on success AND failure paths. The live primary tree must be untouched by every coder run (assert its git status is unchanged from the pre-run snapshot in tests). Add tests/test_codex_delegate_modes.py per the plan's U3 scenarios. Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U3, R2, KTD5) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "modes: enforced read-only review, patch-capture task", model: "opus", effort: "high" },
)
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "opus/high -> opus/xhigh (+1 effort rung)" })

// verify: refute-3 panel over U3 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U3_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U3 (modes: enforced read-only review, patch-capture task). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "modes: enforced read-only review, patch-capture task verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U3 },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U3 (modes: enforced read-only review, patch-capture task). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "modes: enforced read-only review, patch-capture task verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U3 },
  ), { unitId: "U3", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U3 (modes: enforced read-only review, patch-capture task). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "modes: enforced read-only review, patch-capture task verifier", model: "opus", effort: "high", agentType: "saga:readonly-verifier", isolation: "worktree", input: U3 },
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

// ---- U4: registry + dispatch rewire off codex:codex-rescue ----
// depends_on: U3 (barrier)
const U4 = await agent(
  "U4: Rewire the codex lane to the first-party delegate (R5, KTD4/KTD5). In plugins/saga/references/engine-registry.yaml update BOTH codex rows (lines ~27 and ~58): invocation.via -> codex:delegate (pinned; mirrors the agy:delegate convention at registry :85/:116), recipe corrected to the verified 0.142.5 shape (codex exec -s read-only -c model_reasoning_effort=<high|xhigh> \u2014 the --effort flag does NOT exist on this CLI version), last_validated: 2026-07-06; receipt_emitter stays codex-bridge; write_capable stays false. Rewrite build_codex_invocation in plugins/saga/scripts/engine_dispatch.py to emit via: 'codex:delegate' PRESERVING the halt-on-write guard (sandboxed-mutate routed to codex still HALTS, #287 R4/R6) and _assert_payload_preserved byte-preservation. Update plugins/saga/references/engine-dispatch.md and plugins/team-execution/skills/team-execution/references/external-engine-workers.md to name the new bridge. Update the existing suites (tests/test_saga_engine_dispatch.py, tests/test_saga_engine_registry.py, tests/test_saga_engine_resolver.py) \u2014 the registry routing-stability regression pins row literals, so update its expected values deliberately, not as collateral. Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U4, R5, KTD4/KTD5) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "registry + dispatch rewire off codex:codex-rescue", model: "sonnet", effort: "high" },
)
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"], cordProposal: "sonnet/high -> sonnet/xhigh (+1 effort rung)" })

// ---- U5: retirement dereference + operator runbook ----
// depends_on: U4 (barrier)
const U5 = await agent(
  "U5: Complete the retirement dereference (R6). Grep-sweep the repo for codex:codex-rescue and codex-rescue \u2014 zero live references may remain outside historical CHANGELOG/journal entries (docs/engineering-journal and CHANGELOG history are records, not live wiring; leave them). Write the operator runbook section in plugins/codex/README.md: uninstalling the openai-codex marketplace plugin, and the codex: namespace-collision note (both plugins claim the codex: agent prefix, so the marketplace copy must be uninstalled before this plugin's agents resolve cleanly). Add the retirement note to plugins/saga/CHANGELOG.md. Report the final grep-sweep output in your summary as verification evidence. Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U5, R6) as your authoritative spec. When done, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "retirement dereference + operator runbook", model: "sonnet", effort: "medium" },
)
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

// ---- U6: lifecycle proof + availability-gated live smoke ----
// depends_on: U5 (barrier)
const U6 = await agent(
  "U6: Create tests/test_codex_delegate_lifecycle.py (R7). Prove: (a) a completed run's bundle is terminal and self-contained \u2014 a launcher process that exits immediately after the delegate returns leaves no live children and no non-terminal state; (b) a fake-bin that sleeps past --timeout-seconds gets its WHOLE process tree killed within the grace window (poll the fake bin's child pid) with terminal timeout status and no 'running' string anywhere in the bundle's state files; (c) a delegate killed mid-run leaves a dead process tree and a diagnosable bundle, never a running record. Every red condition hermetic (fake codex bin, no network). Add the availability-gated live smoke: one real codex exec round-trip through the delegate asserting receipt + transcript + last-message, SKIP (never fail) when `codex login status` exits nonzero (verified live: exits 0 when authenticated) \u2014 mirror the Ollama smoke posture in tests/test_engine_bridge_http.py. Prove your tests red: for at least the timeout case, demonstrate the test fails against a deliberately-broken variant (e.g. kill only the direct child, not the tree) and say so in your summary. Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U6, R7) as your authoritative spec. When the unit's tests pass, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines) so verify panels can materialize committed state.\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, tests_added, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "lifecycle proof + availability-gated live smoke", model: "fable", effort: "xhigh" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// verify: refute-3 panel over U6 (pass_rule: majority;
// panel-level: refuted when the pass-rule threshold over REPORTING verifiers is met (quorum floor 2 of 3 declared; runtime-missing verifiers shrink the denominator))
const U6_verdicts = await parallel([
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (lifecycle proof + availability-gated live smoke). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "lifecycle proof + availability-gated live smoke verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (lifecycle proof + availability-gated live smoke). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "lifecycle proof + availability-gated live smoke verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
  ), { unitId: "U6", maxAttempts: 3 }),
  () => __retry(() => agent(
    "REFUTE-N VERIFIER over unit U6 (lifecycle proof + availability-gated live smoke). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. MANDATORY FIRST STEP (your worktree is cut from MAIN, not the work branch — evaluating without this step produces false refutations of the wrong revision): materialize the committed work branch with `git checkout feat/476-codex-first-party-bridge -- .` then sanity-grep for a symbol the unit claims to have added (e.g. `grep -rn codex.delegation.v1 plugins/codex/scripts/` ) and abort with verdict INVALID-ENVIRONMENT if absent. Record the exact sha you examined (`git rev-parse feat/476-codex-first-party-bridge`) and QUOTE it in your verdict. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "lifecycle proof + availability-gated live smoke verifier", model: "fable", effort: "xhigh", agentType: "saga:readonly-verifier", isolation: "worktree", input: U6 },
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

// ---- U7: release surfaces + journal ----
// depends_on: U6 (barrier)
const U7 = await agent(
  "U7: Release surfaces (repo rule: installed-plugin metadata tells the same story as the diff). Add the codex plugin (0.1.0) to .claude-plugin/marketplace.json; bump plugins/saga (registry + dispatch + reference docs changed) and plugins/team-execution (reference doc changed) plugin.json versions and mirror both in marketplace.json; CHANGELOG entries for codex, saga, team-execution. Journal: the DECISIONS entry {#codex-first-party-bridge-476} already exists on the branch \u2014 verify it and do NOT duplicate; add a dated LEARNINGS.md entry for the stale-recipe catch if it generalizes (registry recipe named a nonexistent --effort flag; the registry is machine-consumed truth \u2014 generalizable rule: validate registry recipes against the live CLI version at rewire time). Confirm the metadata drift-guard / release-surface-parity tests are green. Read the plan at docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md (U7) as your authoritative spec. When done, commit ALL of the unit's work on the current branch in ONE conventional commit (no attribution lines).\n\nRETURN CONTRACT (all tiers): your FINAL message MUST be ONLY a single JSON object with the keys files_changed, summary -- no prose, no markdown code fences, no YAML, and nothing before or after the JSON. The workflow gate parses this final message as JSON and FAILS the unit if it is not a JSON object carrying these keys. Emit it as your last action even if the work is only partial (fill each key with what you have plus a short note).",
  { label: "release surfaces + journal", model: "sonnet", effort: "medium" },
)
__gate(U7, { unitId: "U7", expectsOutput: true, returns: ["files_changed", "summary"], cordProposal: "sonnet/medium -> sonnet/high (+1 effort rung)" })

if (__pulledCords.length > 0) {
  throw new Error(`pull-cord (#364): ${__pulledCords.length} unit(s) self-reported out of depth -- ` +
    __pulledCords.map((c) => `${c.unit}: ${c.reason}` + (c.proposal ? ` (propose ${c.proposal})` : ' (no legal climb: top of ladder or session ceiling -- HALT)')).join('; ') +
    '. ONE batched escalation ask -- confirm climbs via /tier patch and re-emit.')
}
