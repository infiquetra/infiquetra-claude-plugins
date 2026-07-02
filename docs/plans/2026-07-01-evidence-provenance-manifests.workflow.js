// ===========================================================================
// evidence-provenance-manifests -- emitted Claude Code workflow harness.
// AUTO-EMITTED from a structured execution-spec by execution_spec.py.
// CONTROL FLOW ONLY -- every agent reads the plan as its authoritative spec.
// Per-unit {model, effort} tiers (R2(b)); R3 pilot/fan-out same-tier +
// R10 enumerated-target reconciliation enforced at emit time.
// ===========================================================================

export const meta = {
  name: "evidence-provenance-manifests",
  description: "Issue #285: typed provenance manifest envelope per delegated output \u2014 schema, git-common-dir carrier, producer wiring into the shipped #277/#283 gates, advisory consumers, matrix guard, release surfaces.",
}

const REPO = "infiquetra/infiquetra-claude-plugins"

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
          // ignore
        }
      }
    }
    return val;
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

// ---- U1: manifest schema module ----
const U1 = await agent(
  "U1: Create plugins/saga/scripts/provenance_manifest.py \u2014 the manifest envelope, both subrecords, parroting taxonomy as pure predicates, tier sizing, and tests/test_provenance_manifest.py. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U1, KTD3-KTD5, KTD9) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.",
  { label: "manifest schema module", model: "fable", effort: "xhigh" },
)
__gate(U1, { unitId: "U1", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// verify: refute-3 panel over U1 (pass_rule: majority;
// panel-level: the unit result is refuted when >= 2 of 3 verifiers refute)
const U1_verdicts = await parallel([
  () => agent(
    "REFUTE-N VERIFIER over unit U1 (manifest schema module). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "manifest schema module verifier", model: "fable", effort: "xhigh", input: U1 },
  ),
  () => agent(
    "REFUTE-N VERIFIER over unit U1 (manifest schema module). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "manifest schema module verifier", model: "fable", effort: "xhigh", input: U1 },
  ),
  () => agent(
    "REFUTE-N VERIFIER over unit U1 (manifest schema module). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
    { label: "manifest schema module verifier", model: "fable", effort: "xhigh", input: U1 },
  ),
])
const U1_refute_count = U1_verdicts.filter((v) => v && v.refuted && v.refuted.length > 0).length
const U1_refuted = U1_refute_count >= 2  // majority
if (U1_refuted) {
  throw new Error(`verifier-disagreement: Unit U1 refuted by ${U1_refute_count} verifiers`)
}

// ---- U2: manifest store carrier ----
// depends_on: U1 (barrier)
// RECOVERY (run wf_c34a8d66-b84): U2's agent completed the work on disk but returned
// prose instead of the structured dict, failing __gate. Result below hand-verified by
// the driver: files exist, 31 tests pass, ruff + mypy clean; committed as f2f7160.
const U2 = {
  files_changed: ["plugins/saga/scripts/manifest_store.py", "tests/test_manifest_store.py"],
  tests_added: [
    "test_manifest_store_write_read_round_trip",
    "test_manifest_store_resolves_common_dir_from_worktree",
    "test_manifest_ref_pointer_round_trip",
    "test_manifest_ref_missing_pointer_returns_none",
    "test_manifest_ref_traversal_pointer_returns_none",
    "test_manifest_store_list_empty_tree_returns_empty",
    "test_manifest_store_list_returns_sorted_execution_ids",
    "test_manifest_store_write_overwrites_in_place",
    "test_read_manifest_missing_returns_none",
    "test_read_manifest_malformed_returns_none",
    "test_manifest_store_rejects_path_traversal_ids",
    "test_manifest_store_for_saga_rejects_bad_saga_id",
  ],
  summary: "U2 complete (driver-verified recovery). manifest_store.py: git-common-dir saga-manifests/<saga-id>/<execution-id>.json tree via outcome_store.resolve_common_dir; write/read/list CLI; CompletionEvent.payload manifest_ref pointer helpers; path-traversal guards on saga and execution ids. 31 tests pass with test_provenance_manifest.py; ruff/mypy clean; committed f2f7160.",
}
__gate(U2, { unitId: "U2", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U3: engine producer and gate read ----
// depends_on: U2 (barrier)
// ---- U4: completeness persistence and rename ----
// depends_on: U2 (barrier)
// ---- U5: team-execution worker manifest contract ----
// depends_on: U2 (barrier)
const [U3, U4, U5] = await parallel([
  () =>
    agent(
      "U3: Wire plugins/saga/scripts/engine_dispatch.py to emit typed manifests (claim_provenance, attribution, disposition) via manifest_store and extend satisfy_gate to enforce R11 (gated verdict requires Claude-adjudicated claims); extend tests/test_saga_engine_dispatch.py. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U3, KTD4-KTD5) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.\n\nOUTPUT CONTRACT: your ENTIRE final message must be exactly one JSON object with the keys named above — no prose, no markdown fences, nothing before or after the JSON.",
      { label: "engine producer and gate read", model: "fable", effort: "xhigh" },
    ),
  () =>
    agent(
      "U4: Add record-completeness to manifest_store.py (driver-materialized output_completeness per spec unit via completeness_gate.Contract), rename completeness_gate.check_manifest to check_required_keys, add the /work SKILL post-run persistence step, update tests. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U4, KTD6-KTD7) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.\n\nOUTPUT CONTRACT: your ENTIRE final message must be exactly one JSON object with the keys named above — no prose, no markdown fences, nothing before or after the JSON.",
      { label: "completeness persistence and rename", model: "sonnet", effort: "medium" },
    ),
  () =>
    agent(
      "U5: Define the team-execution worker-exit manifest contract (reference doc + SKILL pointer, complements validator-evidence-state, evidence-only) and the worker-attribution validation test. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U5) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, summary.\n\nOUTPUT CONTRACT: your ENTIRE final message must be exactly one JSON object with the keys named above — no prose, no markdown fences, nothing before or after the JSON.",
      { label: "team-execution worker manifest contract", model: "sonnet", effort: "medium" },
    ),
])
__gate(U3, { unitId: "U3", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })
__gate(U4, { unitId: "U4", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })
__gate(U5, { unitId: "U5", expectsOutput: true, returns: ["files_changed", "summary"] })

// verify: refute-3 panel over U3 (pass_rule: majority;
// panel-level: the unit result is refuted when >= 2 of 3 verifiers refute)
// serialized (was parallel): identical prompt prefixes -> verifiers 2-3 get
// prompt-cache READS on the shared prefix instead of three concurrent cache writes
const U3_v1 = await agent(
  "REFUTE-N VERIFIER over unit U3 (engine producer and gate read). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
  { label: "engine producer and gate read verifier", model: "fable", effort: "xhigh", input: U3 },
)
const U3_v2 = await agent(
  "REFUTE-N VERIFIER over unit U3 (engine producer and gate read). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
  { label: "engine producer and gate read verifier", model: "fable", effort: "xhigh", input: U3 },
)
const U3_v3 = await agent(
  "REFUTE-N VERIFIER over unit U3 (engine producer and gate read). You are an adversarial skeptic: attempt to REFUTE the unit's result, do NOT re-do its work. Read the unit's output and the evidence it cites; for each claimed finding decide REFUTED (with a concrete reason) or UPHELD. Emit a structured verdict {refuted: [...], upheld: [...]}.",
  { label: "engine producer and gate read verifier", model: "fable", effort: "xhigh", input: U3 },
)
const U3_verdicts = [U3_v1, U3_v2, U3_v3]
const U3_refute_count = U3_verdicts.filter((v) => v && v.refuted && v.refuted.length > 0).length
const U3_refuted = U3_refute_count >= 2  // majority
if (U3_refuted) {
  throw new Error(`verifier-disagreement: Unit U3 refuted by ${U3_refute_count} verifiers`)
}

// ---- U6: advisory reader and skill wiring ----
// depends_on: U3, U4, U5 (barrier)
const U6 = await agent(
  "U6: Create plugins/saga/scripts/manifest_reader.py (parroting count, disposition rate, verified ratio; --json) modeled on override_rate_reader.py, wire /code-review R15 skip, /qa R16 ratio, /retro reader invocation; add tests/test_manifest_reader.py. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U6, KTD8) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.\n\nOUTPUT CONTRACT: your ENTIRE final message must be exactly one JSON object with the keys named above — no prose, no markdown fences, nothing before or after the JSON.",
  { label: "advisory reader and skill wiring", model: "sonnet", effort: "medium" },
)
__gate(U6, { unitId: "U6", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U7: saga-spec docs and matrix guard ----
// depends_on: U6 (barrier)
const U7 = await agent(
  "U7: Document the manifest contract and the R17 producer/consumer matrix in plugins/saga/references/saga-spec.md; add tests/test_manifest_consumer_matrix.py enforcing no-orphan-field in both directions. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U7) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, tests_added, summary.\n\nOUTPUT CONTRACT: your ENTIRE final message must be exactly one JSON object with the keys named above — no prose, no markdown fences, nothing before or after the JSON.",
  { label: "saga-spec docs and matrix guard", model: "sonnet", effort: "medium" },
)
__gate(U7, { unitId: "U7", expectsOutput: true, returns: ["files_changed", "tests_added", "summary"] })

// ---- U8: release surfaces and journal ----
// depends_on: U7 (barrier)
const U8 = await agent(
  "U8: Bump saga and team-execution plugin.json versions, mirror marketplace.json, CHANGELOG entries, DECISIONS.md entries for KTD1-KTD9, draft the #285 drift-correction comment. Read the plan at docs/plans/2026-07-01-evidence-provenance-manifests-plan.md (U8 and the drift report) as the authoritative spec.\n\nReturn a structured result with keys: files_changed, summary.\n\nOUTPUT CONTRACT: your ENTIRE final message must be exactly one JSON object with the keys named above — no prose, no markdown fences, nothing before or after the JSON.",
  { label: "release surfaces and journal", model: "sonnet", effort: "low" },
)
__gate(U8, { unitId: "U8", expectsOutput: true, returns: ["files_changed", "summary"] })
