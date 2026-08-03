---
title: Give the refute-N verify panel a severity axis (#686)
type: fix
status: active
date: 2026-08-02
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/686
---

# Give the refute-N verify panel a severity axis (#686)

## Summary

Split the refute-N verifier verdict into two rejection buckets — one that gates the unit and one
that does not — so a panel kills a unit for broken work, never for a wrong sentence about the work.

The fix lands entirely in `plugins/saga/scripts/execution_spec.py`, the emitter for
`cc-workflows-ultracode` harnesses, plus its two test modules, its reference doc, and a read-only
re-emit check that clears a recorded divergence in `infiquetra-codex-plugins`.

## Problem Frame

The emitted verify gate has exactly one rejection bucket and no way to say *what kind* of thing was
refuted. A verifier doing exactly what its prompt asks — reading the unit's output, finding one
sentence of its self-description wrong, and saying so — trips the same gate as a verifier who found
the code broken.

Measured on `main` at saga 0.122.0, the gate arithmetic is one line:
`execution_spec.py:2748-2751` counts a verifier as refuting when `v.refuted.length > 0`, whatever is
in the array. There is no vocabulary anywhere in the contract for "the work is right, the
explanation is wrong."

This has already cost a real run. `infiquetra/infiquetra-codex-plugins#71` ran a seven-unit workflow
with three-verifier panels and died at the Unit 1 gate with
`verifier-disagreement: Unit U1 refuted by 3/3 reporting verifiers (0 missing)`. All three verifiers
had upheld 45 claims about the unit's code and its check results; all five refutations targeted the
unit's `notes` field. Every check the unit claimed was independently re-run by the driving session
and passed. The gate discarded a correct unit and dead-lettered the five units downstream of it.

That run was rescued by hand-patching the *emitted* harness, and the patch earned its keep on the
second run: two verifiers flagged a real downstream blocker as advisories that the old contract
would have turned into unit kills, while one genuine gating refutation still caught a false sentence
in a permanent decision record. But a hand-patched harness no longer matches `execution_spec.py emit`
output for its spec, so any re-emit silently reverts it. The fix has to live in the emitter.

## Requirements

**R1.** The emitted verdict schema carries two distinct rejection buckets — one gating, one
non-gating. Both are required and both are arrays.

**R2.** The emitted gate arithmetic counts a verifier as refuting only when its **gating** bucket is
non-empty. A bare `v.refuted.length > 0` must not survive anywhere in an emitted harness.

**R3.** Both emitted verifier-prompt surfaces define the two buckets with concrete examples and state
the "sound code, wrong prose" test explicitly.

**R4.** Non-gating corrections reach the driving session: logged during the run **and** present in
the emitted workflow's return value.

**R5.** The quorum floor, the missing-verifier hard-fail, and the `verifier_identity` /
`fallback_depth` / `examined_sha` attestation fields behave exactly as they do today.

**R6.** A verifier that omits either bucket is still a runtime failure and still counts toward the
missing-verifier floor.

**R7.** Both `majority` and `unanimous` pass rules are covered by tests over the new arithmetic.

**R8.** The `#364` `escalate_on_signal` one-rung ladder climb fires only on a **gating** refutation.
An advisory-only panel must not burn a tier escalation.

**R9.** Emitted-harness identifier reservation stays complete — every new emitted global is
registered so the emitter's identifier scanner does not drift.

**R10.** The downstream divergence recorded in `infiquetra-codex-plugins` is cleared: re-emitting its
committed spec produces a gate that behaves like the hand patch.

## Key Technical Decisions

**KTD1 — Port the prototype's bucket names verbatim: `refuted_deliverable` (gating) and
`advisory_corrections` (non-gating).** The issue leaves naming open, but the prompt wording that
empirically worked is written against these names, and the downstream repo's committed harness
already uses them. Renaming would force a re-validation of the prompt and would guarantee a textual
diff in R10's acceptance check, which compares the regenerated harness against the hand patch.

**KTD2 — Hard cutover, no back-compatibility shim.** The validator predicate requires **both**
arrays; a verdict carrying only the legacy `refuted` key is a runtime failure that counts toward the
missing-verifier floor.

A tolerant reader that mapped legacy `refuted` onto the gating bucket would silently treat a legacy
prose refutation as gating — reintroducing the exact bug for precisely the cached verdicts most
likely to carry it. R6 also states the strict behavior as an acceptance criterion.

*Accepted cost:* a `resumeFromRunId` workflow that is mid-run when this lands re-runs every verifier
call, because the schema change invalidates cached verdicts. This is a one-time cost with no
in-flight runs known today.

**KTD3 — Advisories ride the existing `__pulledCords` pattern, not a per-unit binding.** Add a
module-level `__advisories` array and a `__logAdvisory(unitId, reported)` helper, registered once in
`_WORKFLOW_RESERVED_IDENTIFIERS` (`execution_spec.py:349-365`) — structurally identical to how
`__pulledCords` is declared at `:3549` and surfaced at `:3691`.

*Rejected: a per-unit `<prefix>advisories` binding.* It would have to be registered in **two**
places — `_WORKFLOW_ITERATE_LOCAL_IDENTIFIERS` (`:432-444`) and the `suffixes` set in
`_unit_reserved_symbols` (`:2368-2377`) — and each covers only one panel shape. Missing one drifts
silently on exactly the other shape. The module-level global has one registration site and no such
asymmetry.

**KTD4 — Every emitted harness gains a final `return { units, advisory_corrections }`.** Emitted
harnesses return `undefined` today, so any object is additive for consumers that do not destructure.
The `units` map makes the return useful beyond advisories and matches the shape the prototype
settled on. This is an operator decision taken during planning, not an inference.

**KTD5 — The gate arithmetic changes in exactly one place.** `_emit_panel_reconciliation`
(`:2623`) is the single source of truth for all three panel forms — `_emit_thunk`,
`_emit_verify_loop_singleton`, and `_emit_verify_panel` — so the one-line predicate change at
`:2748-2751` fixes the one-shot panel, the iterate-to-consensus loop, and the `#364` climb together.
Do not add a second gate path; the function exists specifically to prevent three hand-maintained
copies.

**KTD6 — Both prompt surfaces change, not one.** The Python-assembled `_verifier_prompt()`
(`:2492-2516`) states the verdict shape. The emitted JavaScript `__verifierPrompt` helper
(`:685-712`) carries the visibility protocol, whose clause *"return a refuted entry explaining the
visibility gap"* (`:707`) must route to the **gating** bucket — a verifier that cannot see enough to
judge must still be able to stop the unit. The ~30-line VERDICT CONTRACT block goes into the JS
helper, where the unit-result rendering it references already lives.

**KTD7 — This plan's own units carry no verify panel.** A panel authored now is emitted from current
`main` and therefore runs the pre-fix single-bucket gate: the very failure being fixed could kill the
unit fixing it. Dogfooding the corrected gate is a follow-up run after this lands, not a
precondition for it.

**KTD8 — `execution_spec.py:438` and `:2372` are a different contract and stay unchanged.** The issue
asks which of these share the verdict contract; the answer is neither. Both are sets of emitted
JavaScript *variable names* (`<prefix>refuted`) used for binding-collision detection, unrelated to the
verdict field of the same spelling. Editing them would rename emitted bindings for no reason.

## Implementation Units

### U1. Split the verdict contract in the emitter and pin it with tests

Change the verdict schema, the validator predicate, the gate arithmetic, both prompt surfaces, the
advisory accumulator, and the final return — then pin every one of them in the emitter tests.

**Files:** `plugins/saga/scripts/execution_spec.py`, `tests/test_workflow_emitter.py`,
`tests/test_saga_execution_spec.py`

**Covers:** R1, R2, R3, R4, R5, R6, R7, R8, R9

**Approach:** All six emitter edits live in one file and one coherent contract, so they land as one
unit rather than sequenced same-file units. Work through the sites in this order — schema, predicate,
arithmetic, prompts, accumulator, return — because each later site reads the names the earlier one
establishes.

**Sites:**

1. `_verifier_schema()` `:2575-2604`. The target key set is exactly
   `refuted_deliverable`, `advisory_corrections`, `upheld`, `verifier_identity`, `fallback_depth`,
   `examined_sha` — all six `required`. `refuted` is **renamed** to `refuted_deliverable`, not
   supplemented: the key `refuted` disappears from both `properties` and `required`. `upheld`
   survives unchanged.
2. The `<var>_valid_verifier_verdict` predicate `:2706-2712` — all three arrays checked
   (`refuted_deliverable`, `advisory_corrections`, `upheld`).
3. The `<var>_refute_count` arithmetic `:2748-2751` — gating bucket only.
4. **The advisory call site**, `:2762`, immediately after
   `const {refuted_var} = {refute_count_var} >= {threshold_var}` and **before** the
   missing-verifier `if` block. This position is load-bearing: `_emit_panel_reconciliation`
   returns early on the `#364` unattended-climb path (at the `if ({refuted_var}) {` line), so a
   call appended after that point would silently never emit for climb units. Emitting it here
   covers all three panel shapes with one insertion.
5. `_verifier_prompt()` `:2492-2516` — verdict shape.
6. `_JS_VERIFIER_PROMPT_HELPER` `:685-712` — VERDICT CONTRACT block + the `:707` visibility clause.
7. `_WORKFLOW_RESERVED_IDENTIFIERS` `:349-365` — `__advisories`, `__logAdvisory`.
8. The preamble near `:3549` and the tail near `:3691` — declare the accumulator and the
   `__logAdvisory` helper, emit the final return.

Site 4 is the one a naive reading drops. Sites 7 and 8 only *declare* and *return* the
accumulator; without site 4 nothing ever pushes into it, `advisory_corrections` returns `[]` on
every run, and R4 fails silently — which is exactly the failure mode named in Risk Analysis below.

**Prompt wording — both surfaces have a source; port both verbatim.** The reference file is
`docs/plans/2026-08-01-verified-workflows-capability-policy-removal.workflow.js` in
`infiquetra-codex-plugins` at commit `1327c31` (verified 2026-08-03 to be an ancestor of that repo's
`origin/main`, so the citation is durable). Read it with
`git show 1327c31:<path>`. Three passages, three destinations:

- **Lines 265-300 → the JS `__verifierPrompt` helper.** The VERDICT CONTRACT block, verbatim.
- **Line 263 → the `:707` visibility clause.** The reference reads "…return a
  `refuted_deliverable` entry explaining the visibility gap; do not emit prose-only 'nothing to
  verify' output." Only the bucket name changes; keep the rest of the sentence as the emitter has
  it today.
- **Line 330's prompt string → the Python `_verifier_prompt()`.** The reference sentence is "…and
  sort every refutation into the gating bucket or the advisory bucket per the VERDICT CONTRACT
  below. Emit a structured verdict `{refuted_deliverable: [...], advisory_corrections: [...],
  upheld: [...], verifier_identity: ..., fallback_depth: ..., examined_sha: ...}`."

Do not paraphrase any of the three. That exact wording is the only version with evidence behind it,
and the issue's top pre-mortem is a vague boundary causing verifiers to dump everything into the
gating bucket. The reference is a *hand-patched* harness, so it is a wording source only — do not
treat its non-prompt text as an emitter target.

**Test scenarios** (`tests/test_workflow_emitter.py` for emitted text, `tests/test_saga_execution_spec.py`
for spec/validate):

- A panel whose verifiers return only non-gating corrections and an empty gating bucket does **not**
  refute the unit — asserted at both `majority` and `unanimous`.
- A panel whose verifiers return a non-empty gating bucket **does** refute, unchanged from today.
- A mixed panel where one verifier gates and two do not: `majority` upholds, `unanimous` upholds.
- Non-gating corrections survive into the emitted return value and into a `log()` call — losing them
  is the failure mode of a naive fix.
- A verifier that omits either bucket fails `<var>_valid_verifier_verdict` and counts toward the
  missing-verifier floor.
- Round-trip: emitting a spec with `verify` produces a harness whose gate reads only the gating
  bucket. Assert `v.refuted.length > 0` appears zero times in the emitted text.
- An advisory-only panel does **not** trigger the `#364` `escalate_on_signal` one-rung climb (R8) —
  the second consumer of the refuted boolean, which the issue does not mention.
- A unit with `escalate_on_signal: true` **still emits its `__logAdvisory(...)` call.** This is the
  scenario that catches site 4 being placed after `_emit_panel_reconciliation`'s early `return`
  instead of before it — a placement error that would leave advisory logging silently absent on
  exactly the climb path and nowhere else.
- `__advisories` and `__logAdvisory` are reserved identifiers; the emitted harness passes the
  existing identifier/collision checks unchanged.

**Verification:**

```bash
uv run python -m pytest -q tests/test_workflow_emitter.py tests/test_saga_execution_spec.py
uv run python -m pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Then emit a probe spec carrying a `verify` panel and confirm the gate directly:

```bash
python3 plugins/saga/scripts/execution_spec.py emit <probe-spec.json> -o /tmp/harness.js
grep -c 'v\.refuted\.length > 0' /tmp/harness.js        # must be 0
grep -nE 'refuted_deliverable|advisory_corrections' /tmp/harness.js
```

Note the issue's own verification block cites `pytest plugins/saga/tests`; that directory does not
exist. The emitter tests are at repo root, as written above.

### U2. Update the reference doc and the plugin release surfaces

Bring the written verify contract and the installed-plugin metadata in line with the new two-bucket
shape.

**Files:** `plugins/saga/references/execution-spec.md`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`,
`docs/engineering-journal/DECISIONS.md`

**Depends on:** U1

**Covers:** the doc half of R3; the repo's release-surface rule

**Approach:** `execution-spec.md` describes the single-bucket contract at lines 96, 105-106 and
114-123 — the `pass_rule` semantics, the "Consumption" paragraph, and the `escalate_on_signal`
section. Update each to name the gating bucket, and add the return-value shape from KTD4. Bump the
saga plugin version in `plugin.json` and mirror it in `marketplace.json` and `CHANGELOG.md`, per the
repo rule that installed-plugin metadata must tell the same story as the diff. Record KTD1-KTD8 in
`DECISIONS.md`.

**Test expectation:** the repo's existing version/metadata drift-guard tests cover the release
surfaces; no new test is warranted for prose.

**Verification:** `uv run python -m pytest -q` (drift guards), and confirm the version appears
identically in all three metadata files.

### U3. Clear the recorded divergence in infiquetra-codex-plugins

Re-emit the downstream repo's committed spec with the fixed emitter and confirm the regenerated gate
behaves like the hand patch.

**Files:** none in this repo — a read-only check against `~/workspace/infiquetra/infiquetra-codex-plugins`

**Depends on:** U1

**Covers:** R10

**Approach:** This is the acceptance signal for the downstream repo, whose work-session record
carries an explicit "Verifier contract divergence — do not re-emit this harness" warning. Re-emit
from the committed spec and confirm the **gate mechanics** match the hand patch.

**An empty diff is NOT the pass condition, and chasing one will waste the unit.** Measured
2026-08-03: the committed harness carries hand-authored prompt corrections written mid-run
("CORRECTED PREMISE …", "MANDATORY AFTER THE RE-RENDER …") that appear in **zero** of the committed
spec's seven unit prompts. No re-emit can ever reproduce them, so at least one unit-prompt line
differs permanently, for reasons with nothing to do with this fix. A whole-file `diff` of
`refuted|advisory` lines run against today's unfixed emitter returns 87 lines, exactly 1 of which is
unit-prompt text. Expect that 1 line to survive the fix and **do not report it as a U1 defect.**

Read both files from `origin/main` via `git show`, not the working tree — the downstream checkout is
not a repo this work commits to, so its working tree is not a current source.

**Verification:** four behavioral facts about the re-emitted harness, each independently true or
false. Run from this repo's root:

```bash
S=$(mktemp -d); D=~/workspace/infiquetra/infiquetra-codex-plugins
git -C "$D" fetch --quiet origin
B=docs/plans/2026-08-01-verified-workflows-capability-policy-removal
git -C "$D" show "origin/main:$B-spec.json"  > "$S/spec.json"
git -C "$D" show "origin/main:$B.workflow.js" > "$S/handpatch.js"
python3 plugins/saga/scripts/execution_spec.py emit "$S/spec.json" -o "$S/reemitted.js"

# 1. no legacy gate survives anywhere
grep -c 'v\.refuted\.length > 0' "$S/reemitted.js"                    # must be 0
# 2-4. each of these must return the SAME count for both files
for f in "$S/reemitted.js" "$S/handpatch.js"; do
  echo "$f"
  grep -c 'Array.isArray(v.refuted_deliverable) && Array.isArray(v.advisory_corrections)' "$f"
  grep -c 'filter((v) => v\.refuted_deliverable\.length > 0)\.length' "$f"
  grep -c '__logAdvisory(' "$f"
done
```

Then confirm the residual difference is prompt text only:

```bash
diff <(grep -E 'refuted|advisory' "$S/reemitted.js") \
     <(grep -E 'refuted|advisory' "$S/handpatch.js") | grep -vE 'Implement Unit U'
```

**Pass condition:** check 1 returns `0`; checks 2-4 return matching counts across both files; the
final command prints nothing. **Fail condition:** any count mismatch in checks 2-4, or a non-prompt
line in the final diff — that is a genuine U1 defect. Report it with the exact output and HALT.

**Test expectation:** none in this repo — this is a cross-repo acceptance probe, and it mutates
nothing.

## Scope Boundaries

**Explicit non-goals** (carried forward from the issue, unchanged):

- Do **not** remove or weaken the quorum floor, the missing-verifier hard-fail, or the
  `verifier_identity` / `fallback_depth` / `examined_sha` attestation fields.
- Do **not** make prose errors invisible. They must still be reported and returned to the driver —
  just not gate.
- Do **not** change `VERIFY_N_CAP`, the panel-size bounds, or the cheap-tier budget rider.
- Do **not** add a third `pass_rule` value as the mechanism. The missing axis is *what* was refuted,
  not *how many* refuted.
- Do **not** commit the hand-patched harness in `infiquetra-codex-plugins`. U3 is read-only.

**Deferred to follow-up work:**

- Dogfooding the corrected gate — running a real workflow with verify panels emitted from the fixed
  emitter (KTD7). Worth doing, but after this lands.
- Any change to how `/work` consumes the new workflow return value. KTD4 makes the value available;
  teaching a consumer to read it is separate work with no card yet.

## Risk Analysis

**Most likely failure: the split lands but verifiers put everything in the gating bucket anyway.**
This is the issue's own top pre-mortem, and a vague boundary is the cause. Mitigated by KTD1 and U1's
verbatim-port instruction — the prototype's wording states the test explicitly ("if the unit's code,
tests, and check results are all sound, then NOTHING goes in `refuted_deliverable`, no matter how
wrong its prose is") and enumerates both sides with concrete examples. Paraphrasing is the risk;
porting is the mitigation.

**A too-narrow gating definition lets a real defect through as advice.** The gating bucket must
include false claims about verification itself — a `checks_run` entry that does not reproduce, a
`status: "done"` that is not — and the visibility gap at `:707`. The ported wording covers all three
explicitly; U1's site list names `:707` so it cannot be missed.

**Advisories silently vanish, making the panel weaker than the single bucket it replaced.** Mitigated
by R4 requiring both a `log()` and a return-value entry, by U1 site 4 naming the one place the
accumulator is actually populated, and by two dedicated U1 test scenarios (advisories present in the
return; the climb path still logging them). This is named as the failure mode of a naive fix, and
declaring `__advisories` without ever pushing to it is precisely how a naive fix passes review.

**Schema change invalidates cached verdicts for in-flight resumes.** Accepted under KTD2 with no
mitigation beyond timing — land it when no `resumeFromRunId` workflow is mid-run.

**The `#364` climb is a second, unmentioned consumer of the refuted boolean.** Changing the
arithmetic in `_emit_panel_reconciliation` fixes it for free (KTD5), but "for free" is exactly how a
regression hides. R8 makes it an explicit requirement with its own test scenario rather than a
side effect nobody asserted.
