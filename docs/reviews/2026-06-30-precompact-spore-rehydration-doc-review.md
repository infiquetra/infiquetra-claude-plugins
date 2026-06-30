---
target: docs/plans/2026-06-30-precompact-spore-rehydration-plan.md
reviewed_revision: working tree (plan untracked)
review_type: doc-review (readiness-skeptic, agy-focused)
date: 2026-06-30
blocked: false
linked_issue: infiquetra/infiquetra-claude-plugins#281
linked_plan: docs/plans/2026-06-30-precompact-spore-rehydration-plan.md
prior_review: docs/reviews/2026-06-27-precompact-spore-rehydration-readiness.md
---

# Doc Review — PreCompact Spore plan (agy-focused readiness pass)

**Verdict: READY to drive `/work`. Not blocked** — 0 P0/P1 open after one safe fix; one P2 model
decision and one P3 memory-staleness note remain, neither blocking.

The operator's steer was specific: verify the `agy` delegation in the plan against the **actual**
`agy` plugin (capability + model), because the cautionary "provenance lesson" carried in auto-memory
belongs to a **deprecated, removed** hand-rolled `agy` tool — not the packaged infiquetra `agy`
plugin. That verification is the spine of this review.

## Applied fixes

| # | Section | Fix | Evidence |
|---|---|---|---|
| FIX-1 | Execution (operator-pinned) | Replaced the stale "Containment protocol" prose (snapshot HEAD, grep transcript for `agy --model`, "agy must not run git commit/push") with the real v0.1.0 contract: `patch-only` coder envelope, disposable-clone + patch-import, per-unit `write_set` + verification command, model default, and wrapper-enforced containment. | `plugins/agy/scripts/agy_delegate.py`, `plugins/agy/skills/agy-delegate/references/delegation-contract.md`, `plugins/agy/agents/agy-coder.md`, `plugins/agy/docs/harness-proof.md` |

## Readiness summary

The feature design (R1–R13, KTD1–KTD8, U1–U6, the seam round-trip) was already gated-reviewed READY
on 2026-06-27 and its grounding citations re-verified green this session; this pass did not disturb
it. The only material defect was that the **agy/Execution section was written against a deprecated
tool's behavior**. The capability the plan depends on is real and proven, so the defect was a stale
*description*, not a stale *plan* — safe-fixed in place.

**Can the agy plugin do what the plan asks? Yes — verified, not assumed.**

- U2/U3/U5 are bounded coding tasks = the `patch-only` coder flow's exact shape. The coder default is
  `mode=patch-only` → agy works in a disposable clone, returns a `diff.patch`, Claude reviews + imports
  (`agy_delegate.py:1164-1165`, `decide_non_apply_status`, contract "Modes").
- A **live harness proof on 2026-06-30** (`plugins/agy/docs/harness-proof.md`) shows the coder flow
  end-to-end: wrapper status `applied`, transcript classifier `real`, `only_expected_changes=true`,
  no Claude file-tool use. This is end-to-end proof, not just unit tests.
- "Claude sole committer/pusher" is **enforced by construction**: the clone has remotes stripped (agy
  cannot push); rogue commits in the clone → `checks_failed`; out-of-scope edits → `out_of_scope_mutation`
  (`agy_delegate.py:527-542,808-854`).

**What model?** The wrapper passes `--model` to `agy` verbatim and defaults to `flash`
(`agy_delegate.py:1109`; contract envelope `"model": "flash"`). The live proof ran `agy 1.0.14` with
default flash and passed, so `flash`→`Gemini 3.5 Flash (High)` is the **only configuration with a
passing harness proof**. **The operator has pinned `Gemini 3.1 Pro (High)`** — a verified-valid string
per `agy 1.0.14 models`, now written into the plan. Because no alias expansion happens, the envelope
must carry the exact canonical string (not `pro`), and the first `/work` delegation should confirm Pro
(High) runs clean end-to-end (it is listed/valid but not yet harness-proven through the wrapper).

**Why the plan's old containment ritual is obsolete (not just redundant).** The deprecated tool needed
manual HEAD-snapshots and transcript-greps because Claude hand-rolled `agy` against the live tree. The
packaged plugin moves containment into the wrapper (disposable clone, write-set gate, `git apply`
gate) and makes provenance a built-in classifier. Notably, "grep the transcript for `agy --model`" is
the **wrong signal** for the new plugin: that string is built *inside* the wrapper and lands in
`agy.log`, not the Claude transcript — the transcript shows a Bash call to `agy_delegate.py`, and the
real provenance signal is the bundle's `agy_launched=true` + `classify_transcript → real`.

## Remaining findings

| # | Priority | Status | Finding |
|---|---|---|---|
| F1 | P1 | Fixed (FIX-1) | Execution/containment section described the deprecated hand-rolled `agy`, not the v0.1.0 plugin contract; it prescribed an obsolete ritual and omitted the real knobs (mode / write_set / verification command / model). |
| F2 | P2 | **Resolved** | Model pinned to **`Gemini 3.1 Pro (High)`** (operator choice). Verified valid via `agy 1.0.14 models`; the wrapper forwards `--model` verbatim (no alias expansion) so the full canonical string is required. Plan carries a first-run check: only `flash`→`Gemini 3.5 Flash (High)` has a live harness proof, so confirm Pro (High) executes clean on the first delegation. |
| F3 | P3 | Open (advisory) | Auto-memory still describes the **deprecated** hand-rolled `agy` and its provenance failure modes (`reference_agy_delegated_coder`, `project_external_agent_delegation`, `project_vecu_port_seeds`, `reference_agy_as_reviewer_stall`, `reference_gemini_prompting_best_practices`). These no longer match the packaged plugin and would mislead a future `/work` that consults memory. Recommend a `/retro` memory-curation pass (propose-diff-and-wait). |

## Residual risk

- The agy capability is verified from source + a today-dated live proof; the only unverified surface
  is **non-flash model strings** on `agy 1.0.14` (F2) — resolvable with a one-line `--model` probe at
  `/work`.
- The memory staleness (F3) sits outside the plan document, so it was not safe-fixed here; flagged for
  `/retro`. Until curated, treat the in-plan agy description (now corrected) as authoritative over the
  memory notes.

## Next step

`/work #281` — not blocked. Build the agy delegations as `patch-only` coder envelopes with the
per-unit write-sets + verification commands now written into the plan's Execution section; set
`model: "Gemini 3.1 Pro (High)"` (exact canonical string) in each envelope, and confirm Pro (High)
runs clean on the first delegation before relying on it.
