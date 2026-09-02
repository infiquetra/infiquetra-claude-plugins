---
title: issue 912 Saga Brainstorm improvement — run-wide implementation plan
type: feat
status: active
date: 2026-08-30
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/912
backend: inline
---

# issue 912 Saga Brainstorm improvement — run-wide implementation plan

## Summary

One bounded serial run gives Saga Brainstorm a unified continuity contract, an adaptive judgment
model, a layered behavioural evidence suite, and a maintenance cleanup — while Brainstorm stays a
creative conversation with no visible checklist, no questionnaire, no prescribed sequence, no
persisted score, and no live completeness gate.

This is the single plan for all four units. It is planned once, reviewed once, repaired once, then
executed strictly B1 → B2 → B3 → B4 by one OpenCode worker, landed as four child-scoped commits
plus one shared release commit through one integrated pull request.

## Problem Frame

Brainstorm's peripheral mechanics are tested and its behavioural core is not, and four continuity
facts do not hold at the pinned base. An artifact records its *source* but not its *producer*, so a
document can exist on disk and stay invisible to the normal resume path. The Phase 2.5
scope-confirmation stop is a gate in behaviour but is not declared, so nothing downstream can tell a
legitimate operator wait from a stalled session. Artifact-free exploration is not distinguished from
a durable handoff. And `plugins/saga/skills/brainstorm/SKILL.md:46-50` instructs a
`brainstorm-interrogation-choice` gate-divergence record "on the next `saga.py save` call" — a save
Brainstorm deliberately never performs, so the measurement vanishes with no observable failure and
has no demonstrated consumer.

Beyond continuity, Brainstorm sizes ceremony by product complexity (Lightweight / Standard / Deep)
but never measures consequence, so a technically small change that handles credentials gets less
rigor than a large low-consequence application. Its parallel work is bounded by kind but not by
count: `plugins/saga/skills/brainstorm/SKILL.md:17` and `:139-140` permit a Phase 1 context scan
running parallel `Explore` agents with no ceiling and no distinct-question requirement, and
Brainstorm has no row in `plugins/saga/references/sandbox-spawn-sites.md` where every other Saga
fan-out site is recorded.

## Authoritative inputs

- **Run contract:** issue 912 body — settled decisions D1 through D7, the governing principle, the
  dependency graph, the board transition contract, the stop conditions, the proportionality
  guardrail, and the run-level acceptance criteria. Binding.
- **Unit contracts:** issues 913 (B1), 914 (B2), 915 (B3), 916 (B4). Each card's own acceptance
  criteria and its "Out-of-scope / non-goals" section govern its unit.
- **Coordinator preflight receipt:** base commit `3b2b7083fdda8e39e213b5f4acf9f8301d60dd52`,
  identical to `origin/main`, worktree clean; Saga on `main` is 0.148.0 (issue 912 recorded 0.147.0
  at shaping, so the base advanced one minor after shaping); the installed Saga surface is pinned at
  0.148.0 and must not be replaced during this run.
- **Live surfaces at the pinned base**, which win over the approved design record everywhere they
  disagree. The design record
  (`docs/operations/saga-brainstorm-change-candidates.md` in `infiquetra/infiquetra-agent-operations`)
  is discussion authority only and reviewed an older Saga version.

## Preflight findings — recorded, not planned around

Five findings where a described gap does not match the live 0.148.0 code. Each is recorded here
because issue 912's stop conditions explicitly want them surfaced.

| # | Finding | Effect on the plan |
|---|---|---|
| F1 | **The volatile dispatch line count has no live target.** `plugins/saga/references/sandbox-spawn-sites.md` carries four in-scope rows — Code Review, QA, Investigate, Resume — and no Brainstorm row. No `~line`, `line N`, or source-line count appears anywhere in `plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/commands/brainstorm.md`, or `plugins/saga/skills/brainstorm/references/requirements-sections.md`. | B4 records the finding and removes nothing. B2's new row carries phase names, never a line reference. |
| F2 | **The duplicated lifecycle block appears in exactly four skills, and issue 912's stated set is wrong in both directions.** The duplicated construct is the near-identical block reading `/ideate answers: … /brainstorm answers: … /plan answers: …`. It appears in exactly four files: `ideate/SKILL.md:15`, `loop/SKILL.md:26`, `office-hours/SKILL.md:27`, and `plan/SKILL.md:19`. `founder-review/SKILL.md:30` carries a differently worded **variant** — no `/ideate` line, and different answer text — not the block. `strategy/SKILL.md` carries only inline ordering mentions at lines 3, 9, and 117, not the block. Issue 912 and issue 916 both name Ideate, Office Hours, and Strategy: that set **wrongly includes Strategy** and **wrongly omits Loop and Plan**. Verified three independent ways at the pinned base. | The mechanical check is written against the verified set of four. Resolution in KTD6; OQ1 is settled. |
| F3 | **Deleting the interaction-rules gate-record marker fails the live lint.** `plugins/saga/skills/brainstorm/SKILL.md:52` carries `<!-- gate-record: id=brainstorm-interrogation-choice absence=HALT transport=ask-user-question -->`. Markdown coverage in `plugins/saga/scripts/lint_gate_absence_contract.py` is **section-scoped**, and that marker covers the `AskUserQuestion` mentions at lines 31 and 43 in the same section. Deleting it was measured on a scratch copy: the production lint reports `VIOLATIONS: 2` naming both lines. | Issue 913 asks for the marker's removal. B1 keeps the marker and repoints its id instead (KTD2). |
| F4 | **`handoff_envelope.infer_maturity` would promote an unconfirmed checkpoint.** `plugins/saga/scripts/handoff_envelope.py:28-29` maps any `docs/brainstorms/` path to `requirements-ready` from the path alone. A `pending-confirmation` checkpoint under that directory would hand off as ready. That file is not in issue 913's expected-change list. | B1 owns the file and makes the inference frontmatter-aware (KTD7). Settled by the OQ4 ruling. |
| F5 | **`tests/test_lint_gate_absence_contract.py` needs no edit.** Issue 913 lists it as changing. Its `MIGRATED_SKILLS` tuple names the Brainstorm skill, and `test_scan_saga_skills_passes_and_lists_all_six_migrated_sites` plus `test_default_ci_scan_passes_and_surfaces_pending_migrations` already assert the live lint stays clean. Neither test keys on a gate id. | B1 adds nothing there. The "gate-absence contract agrees" half of issue 913's telemetry test is satisfied by invoking the production lint from B1's own new module. |

## Requirements

Grouped by concern. R-IDs are continuous across groups and never restart.

**Governing principle — binding on every unit.**

- R1. Brainstorm presents no visible checklist, fixed questionnaire, prescribed question sequence,
  persisted score, or live completeness gate during exploration.
- R2. No Brainstorm state store, queue, save boundary, or new write path is added.
- R3. Free exploration requires no artifact, claims no readiness, and exposes no durable downstream
  route.
- R4. Architecture and implementation design remain `/plan`'s responsibility; the private gap map is
  never persisted and never surfaces as a document section.

**Continuity (B1).**

- R5. Scope confirmation durably records the exact proposed boundary together with the producing
  Saga capability, the producing activity identity, and `pending-confirmation` maturity, before any
  readiness-claiming artifact exists.
- R6. Confirmation promotes that checkpoint into the minimum requirements artifact carrying exactly
  four parts — confirmed scope and material decisions, rationale, intended acceptance outcome, and
  unresolved planning questions — and only then do durable downstream routes appear.
- R7. Revision returns to creative dialogue and requires fresh confirmation; it cannot inherit the
  earlier approval.
- R8. Resume restores the latest unambiguous checkpoint directly, never replaying settled questions;
  two or more plausible matches is an explicit stop, never a recency, filename, or broad-content
  guess.
- R9. Legacy provenance inference is labelled inferred and operator-confirmed, and discovery never
  rewrites, migrates, or reformats the file on disk.
- R10. The unreachable telemetry instruction is gone, no Brainstorm instruction references a
  deferred `saga.py save`, and the production gate-absence lint still reports zero violations.

**Adaptive judgment (B2).**

- R11. Consequence-based assurance is calibrated from concrete trust-boundary and failure factors,
  separately from product size, and never from a domain label. No named assurance levels exist.
- R12. Assurance rigor rises and falls as material consequences enter or leave scope.
- R13. Concerns material to the current idea are privately classified as Clear, Partial, Missing, or
  Not material; `Not material` is a permitted outcome; no classifier state is ever exposed.
- R14. Repository-discoverable facts are grounded before the operator is asked, and a question is
  asked only when its answer could materially change scope, acceptance, consequence-based
  safeguards, or route — one at a time, preferring greatest consequence and uncertainty.
- R15. Lightweight work launches zero helpers. Standard and Deep are capped at one read-only
  repository-grounding scout and one independent claim verifier, each requiring a distinct evidence
  question. These are ceilings, not required launches.
- R16. Helpers are read-only by tool omission, cannot write files, choose requirements, or address
  the operator; the primary process retains synthesis, creativity, the private model, and every
  operator exchange.

**Layered evidence (B3).**

- R17. Deterministic tests cover deterministic mechanics only, and no deterministic test asserts
  which question is asked, its wording, or the order of the dialogue — proven mechanically over the
  test sources, not by reviewer promise.
- R18. The scenario set varies product size and consequence independently and includes at minimum a
  premature-convergence case, a missed-material-gap case, a consequence-calibration case, and a
  checklist-overengineering case.
- R19. Scenario results are reported per material dimension, and no aggregate quality number is
  produced or consumed anywhere.
- R20. A single model-judged finding cannot block alone; blocking requires a reproducible scenario
  plus a second independent grader agreeing or a recorded operator adjudication, and that gating
  logic is asserted directly.
- R21. A small fixed calibration set runs and reports grader agreement, making drift visible.
- R22. Every safeguard B1 and B2 declare critical carries a mutation case that fails when the
  safeguard is weakened and passes when it is restored.
- R23. The harness runs offline, writes nothing under `docs/brainstorms/`, mutates no Saga state, and
  needs no network access.

**Maintenance (B4).**

- R24. No retired runner filename remains in the live Brainstorm contract, and the behavioural
  ownership rule — Brainstorm owns the interactive creative dialogue and does not delegate its
  judgment or its operator exchange to an unrelated runner — is preserved and asserted through the
  current routing contract, never through the absence of a historical string.
- R25. Every pre-existing Orchestrate review-transport assertion still passes and Orchestrate
  behaviour is unchanged.
- R26. The lifecycle ordering is consistent across every Saga skill that states it, proven by a
  mechanical check, and Brainstorm's placement between Ideate and Plan is unchanged.
- R27. The Shaping distinction is stated exactly once, introduces no `/saga:shaping` command, and
  adds no automatic Brainstorm-to-board transition.
- R28. The dispatch-line-count preflight finding is recorded and nothing was removed for it.

**Run level.**

- R29. Four child-scoped commits land strictly in the order B1 → B2 → B3 → B4, followed by one
  shared Saga release commit, all through one integrated pull request.
- R30. `bash scripts/gate.sh` exits 0 at the final commit, and the Saga release triad
  (`plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`) stays aligned.
- R31. The final merged state runs every Brainstorm-related module green together, not merely each
  child green in isolation.

---

## Key Technical Decisions

**KTD1 — The durable checkpoint is the artifact file itself, written early at
`pending-confirmation` maturity.** At Phase 2.5 Path B, before posing the confirmation question,
Brainstorm writes `docs/brainstorms/YYYY-MM-DD-<topic>-requirements.md` carrying
`maturity: pending-confirmation` and the exact proposed boundary. Confirmation rewrites the same
path in place at `requirements-ready`. Rationale: Phase 3 already writes exactly that path, so this
adds no write path, no state store, no queue, and no save boundary (R2) — it moves the first write
earlier and adds one maturity value. Rejected: a checkpoint under `.claude/saga/`, which is a
Brainstorm state store by any reading and is forbidden by D3; and a separate sidecar file, which
doubles the surface resume must reconcile and creates a second ambiguity source.

**KTD2 — The interaction-rules gate-record marker is kept and repointed, not deleted.** F3 measured
that deleting it produces two live lint violations, and the paragraph beneath it
(`plugins/saga/skills/brainstorm/SKILL.md:53-57`) declares the issue-371 operator-absence contract
against it. B1 deletes the telemetry paragraph at lines 46-50 and changes the marker's `id` from
`brainstorm-interrogation-choice` to `brainstorm-interrogation-gate`. Rationale: the marker family
is the absence declaration, which is independent of the removed telemetry; only the id was minted as
the issue-399 `gate_id`, and that consumer is gone. The id appears in no other file. Rejected:
replacing it with `gate-exempt`, which would falsely claim the interrogation mentions fire no gate.

**KTD3 — Every Markdown contract assertion is a pure predicate function over text.** Each contract
test module exposes a module-level `check_<rule>(text) -> list[str]` returning violation messages,
and the tests call it twice: once on the real file (expect empty) and once on a copy of that same
text with the rule string removed (expect non-empty). Rationale: this is what makes mutation proof
real rather than ceremonial — the function that guards the live file is the function the mutation
case weakens. It mirrors the in-memory string-surgery pattern already proven in
`tests/test_concurrency_conformance.py` (`_mutate_source`). Rejected: rewriting the skill to a
throwaway tree per case, which is slower and lets the real file drift out of the assertion path.

**KTD4 — Helpers are read-only by tool omission, never by prose — but only the verifier is a
sandbox in-scope site.** B2 names the grounding scout as `subagent_type: Explore` (structurally
lacks `Edit`/`Write`/`NotebookEdit` while retaining `Bash`) and the claim verifier as
`subagent_type: saga:readonly-verifier` with `isolation: "worktree"`, with the two-rung fallback
ladder in `plugins/saga/references/sandbox-spawn-sites.md`. Rationale: "the helper may not write
files" enforced by an instruction is a request; enforced by tool omission it is a constraint, and the
repository already mandates that mechanism for every verify-class spawn.

**Only the claim verifier joins the in-scope table.** That table's stated class contract is
verify/review-class spawns carrying the `read-only-verify` profile — `saga:readonly-verifier` plus
`isolation: "worktree"` — and `tests/test_sandbox_spawn_sites.py::test_in_scope_skills_reference_readonly_verifier`
enforces exactly that for each listed skill. A survey-class `Explore` scout in that table would
contradict the class it is filed under, and the test would not catch it because
`IN_SCOPE_SKILLS` hardcodes only the four existing skills. The grounding scout is therefore recorded
outside the table, in its own short subsection, as a read-only-by-tool-omission survey spawn that is
deliberately not worktree-isolated. Rejected: rewriting the in-scope table's class contract to admit
mixed spawn types, which would weaken a shared contract four other skills depend on for the sake of
one new row.

**KTD5 — The evidence layer is offline data plus a deterministic grader plus an injectable runner.**
Scenario cases, rubric dimensions, and calibration cases live as data files under `tests/data/`; the
grader is a pure function; live model grading is opt-in behind an environment variable and never
runs in CI. Rationale: this mirrors the repository's proven pattern in
`plugins/saga/scripts/engine_benchmark.py` plus `plugins/saga/references/benchmark-suite.yaml`,
whose own header states graders are deterministic checks and never model-graded, and it satisfies
R23 without pretending CI proves conversational quality. Rejected: a live-judge harness in CI, which
needs network access and makes the suite non-reproducible.

**KTD6 — The lifecycle consistency check is a test carrying the canonical chain, not a prose
single-sourcing edit.** Settled by coordinator ruling on OQ1, on the authority of D6's "a minimal
mechanical consistency check without moving the lifecycle". B4 adds one test module holding the
canonical Think-phase command ordering as a module constant and asserting that every `SKILL.md`
rendering the `/ideate … /brainstorm … /plan` block renders a consistent sub-sequence of it.
**No skill's lifecycle prose is edited.** The check is written against the verified set of four —
`ideate/SKILL.md:15`, `loop/SKILL.md:26`, `office-hours/SKILL.md:27`, `plan/SKILL.md:19` (F2) — and
treats `founder-review/SKILL.md:30` as an out-of-set variant, not a block member. Rationale: the real
duplication set includes `plan/SKILL.md` and `loop/SKILL.md`, the two highest-traffic Saga skills, so
single-sourcing them contradicts D6's requirement that maintenance be a separate **low-risk** unit;
and the repository already uses a hardcoded expected-set constant for exactly this job
(`REQUIRED_ADJACENT_PAIRS` in `tests/test_saga_docs_coverage.py`). Rejected: citing
`plugins/saga/skills/loop/references/dispatch-table.md` from the four block-carrying skills — the
proven single-source-and-cite pattern, but a prose edit to four files for a cleanup unit.

**KTD7 — `handoff_envelope.infer_maturity` becomes frontmatter-aware.** When the source resolves to
an existing file whose frontmatter declares a `maturity`, that declared value wins; otherwise the
existing path-based inference is unchanged. Rationale: F4 — without this, a `pending-confirmation`
checkpoint hands off as `requirements-ready` and R3 is violated by a path rule the plan never
touched. Rejected: leaving the inference alone and gating only in the skill prose, which puts the
guarantee in an instruction rather than in the code every consumer calls.

**KTD8 — The shared release update is a fifth commit, not folded into B4.** Rationale: each child
commit stays genuinely child-scoped and traceable, and issue 912's release shape asks for **one**
shared Saga release update at the end. `tools/release_surface_diff_guard.py` evaluates the whole
pull-request diff against the base ref, so one bump at the end satisfies it — but it also means the
full gate can only be green at that final commit, never at B1, B2, or B3 alone. Settled by the OQ7 ruling.

**KTD9 — The runtime checkpoint loads the candidate through a session-scoped `--plugin-dir`, never
through the machine-global marketplace cache.** Settled by coordinator ruling on OQ6. The disposable
tab launches as:

```bash
claude --plugin-dir /Users/jefcox/workspace/infiquetra/orch-claude-plugins-912/plugins/saga
```

That loads the candidate Saga plugin for that one session only. The machine-global marketplace cache
stays at the pinned 0.148.0, so issue #907's reviews keep running against the version they depend on
while this run exercises the unmerged candidate. Rationale: it gives the checkpoint a genuine plugin
load — the real `/saga:brainstorm` command surface, its skills, and its hooks — rather than a
by-path file read that would exercise the prose without the plugin wiring around it. Rejected:
`/plugin marketplace update`, which is machine-global and would replace the pinned runtime issue 912
forbids replacing; and telling the tab to read `plugins/saga/skills/brainstorm/SKILL.md` by path,
which proves the contract text but not the command surface.

**KTD10 — Brainstorm gets rows in `sandbox-spawn-sites.md` only, never
`concurrency-spawn-sites.md`.** Rationale: the concurrency inventory's conformance test discovers
**executable** Workflow, external-runner, outcome-dispatch, and worktree-add calls in Python
sources; Brainstorm's helpers are prose-directed agent spawns with no executable seam, so a row
there would be an unbacked entry in a machine-verified table.

**KTD11 — Saga bumps 0.148.0 → 0.149.0.** Minor, because the run adds behaviour to Brainstorm,
Resume, and the handoff maturity inference. Orchestrate stays at 3.0.8: B4 changes only
`tests/test_orchestrate_review_transport.py`, and `tools/release_surface_diff_guard.py` exempts
`tests/**`, so no Orchestrate behaviour changes and no Orchestrate bump is warranted.

---

## Run topology

Strict serial execution, one active unit at a time, one worker, one pull request.

| Item | Value |
|---|---|
| Base | `3b2b7083fdda8e39e213b5f4acf9f8301d60dd52`, branch `work/cp912-brainstorm-improvement` |
| Order | B1 → B2 → B3 → B4 → release. No parallel pairing exists |
| Writer | One OpenCode worker, `opencode/muse-spark-1.2-contributor-free`, extra-high, Build Auto, reused across all four units |
| Commits | Four child-scoped commits plus one `chore(saga)` release commit |
| Review | One integrated Saga Code Review wave after all commits are frozen — seven lenses, at most three concurrent |
| Runtime proof | One checkpoint after B2 integrates (see "Runtime checkpoint" below) |
| Backend | `inline`, fixed by issue 912's run declaration; no workflow backend |

**Why the order is what it is.** B1 establishes the confirmed-artifact boundary that B2's question
selection and B3's scenario outcomes are both defined against. B2 must precede B3 because
specifying premature-convergence and checklist-overengineering scenarios before the judgment model
exists would test behaviour that is not there. B4 is last because D6 requires maintenance to follow
behavioural work, and because B4's positive ownership-rule test keys off the helper policy B2
writes.

**Shared surfaces and who may touch them.** `plugins/saga/skills/brainstorm/SKILL.md` is edited by
B1, B2, and B4 in that order and by nobody else. The Saga release triad is touched only by the
release commit. The engineering journal is appended by every unit, each into the same newest date
section — `scripts/lint_journal_order.py --base-ref` fails an entry filed anywhere else.

---

## Implementation Units

### U1. B1 — issue 913: unified continuity contract and telemetry removal

Give Brainstorm one continuity contract so an interrupted session recovers exactly where it stopped,
a confirmed scope is durably recorded before any readiness claim, and the unreachable telemetry
promise is gone.

**Goal.** Make the four continuity facts hold — producer identity on the artifact, a declared
scope-confirmation gate, artifact-free exploration distinguished from a durable handoff, and no
promise Brainstorm cannot keep — without adding a state store, a queue, or a save boundary.

**Requirements.** R1, R2, R3, R4, R5, R6, R7, R8, R9, R10.

**Dependencies.** None. This is the first unit.

**Files owned and editable by this unit.**

`plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/skills/brainstorm/references/requirements-sections.md`,
`plugins/saga/skills/resume/SKILL.md`, `plugins/saga/references/saga-spec.md`,
`plugins/saga/references/gate-divergence-instrumentation.md`,
`plugins/saga/scripts/handoff_envelope.py`, `tests/test_brainstorm_continuity_contract.py` (new),
`tests/test_handoff_envelope_maturity.py` (new), `docs/engineering-journal/LEARNINGS.md`,
`docs/engineering-journal/DECISIONS.md`.

**Files this unit must not touch, because another unit owns them.**

`plugins/saga/references/sandbox-spawn-sites.md` (U2). `tests/test_orchestrate_review_transport.py`
(U4). Every scenario, rubric, calibration, and mutation module under `tests/` (U3). The Saga release
triad (the release commit). `tests/test_lint_gate_absence_contract.py` — no unit edits it (F5).

**Approach — the concrete changes.**

*Interaction rules.* Delete `plugins/saga/skills/brainstorm/SKILL.md:46-50`, the whole
"Gate-divergence telemetry (optional, issue #399)" paragraph. Keep the marker on line 52 and change
only its id to `brainstorm-interrogation-gate` (KTD2, F3). Leave the operator-absence paragraph
beneath it unchanged.

*Phase 0.2 — provenance capture.* Extend the existing capture to record three producer facts
alongside the existing `source`: the producing capability, fixed as `brainstorm`; the producing
activity identity, formed as `brainstorm-<topic-slug>-<UTC timestamp, `YYYYMMDDTHHMMSSZ`>` at the
moment the checkpoint is first written; and, when `.orchestrate/run.json` exists in the working
tree, that file's `run_id` as an optional run identity. State that a missing run identity is
recorded as absent, never invented.

*Phase 0.1 — resume without guessing.* Replace "a recent matching `docs/brainstorms/*-requirements.md`
exists" with an explicitly ordered three-tier rule. Write the order into the skill as an ordered
sequence, not as three independent conditions — every historical artifact under `docs/brainstorms/`
predates the producer facts, so a rule that only matches on them would never reach the legacy path
issue 913 requires.

Scan `docs/brainstorms/*-requirements.md` and read each file's frontmatter, then apply in this order:

1. **Exact match.** Among files that carry the producer facts, match on `topic` plus `capability`.
   Exactly one match restores directly: summarize the restored boundary and continue from it without
   re-presenting settled decisions. Two or more plausible matches stop and ask the operator to
   choose, explicitly never by recency, filename, or broad content match. A match at
   `maturity: pending-confirmation` re-enters at the Phase 2.5 confirmation, not at Phase 1.
2. **Legacy inference.** Only when tier 1 produced no match, consider the files that exist but lack
   the producer facts. These enter the labelled-inference path below rather than being treated as
   absent. A file missing `capability` is a legacy artifact, never a miss.
3. **Empty scan.** Only a genuinely empty scan — no file matched in tier 1 and no file qualified for
   tier 2 — starts fresh.

State the tiers in that order and state that tier 3 is reachable only after both earlier tiers found
nothing, so a worker cannot collapse "no exact match" into "start fresh".

*Phase 2.5 — the declared gate and the checkpoint.* On Path B only, before posing the confirmation
question, write the checkpoint to `docs/brainstorms/YYYY-MM-DD-<topic>-requirements.md` with
frontmatter `date`, `topic`, `capability: brainstorm`, `activity`, optional `run`, optional `source`,
and `maturity: pending-confirmation`, and a body carrying the exact proposed boundary — what is
being built, what is in scope, what is explicitly out, and the open questions. Then ask. Add
`<!-- gate-record: id=brainstorm-scope-confirmation absence=HALT transport=ask-user-question -->`
immediately above the Path B paragraph. Path A stays exactly as it is: it has no confirmation to
declare, and issue 913 forbids adding a second approval step.

**The marker census after B1 is three, and this is the authoritative statement of it.** The live file
carries exactly two markers — `brainstorm-interrogation-choice` at line 52 and
`brainstorm-handoff-routing` at line 356. B1 leaves the file with three: the interrogation marker
**survives, repointed** to `brainstorm-interrogation-gate` (KTD2); the handoff-routing marker
**survives untouched**; and `brainstorm-scope-confirmation` is **added**. No marker is deleted. Every
B1 assertion about marker counts keys off this census, not off the pre-B1 count of two.

*Phase 3 — promotion, minimum artifact, and revision.* Confirmation rewrites the same path in place
with `maturity: requirements-ready`. State that the minimum artifact carries exactly four parts —
confirmed scope and material decisions, rationale, intended acceptance outcome, and unresolved
planning questions — and no architecture or implementation plan. State that any change to the
boundary after confirmation rewrites the file back to `pending-confirmation` and requires a fresh
Phase 2.5 confirmation before it can return to `requirements-ready`. State that an exploratory-only
outcome writes no file at all.

*Phase 4 — routes gated on declared readiness.* Show options 1 through 4 (Plan, `/spec`,
`/handoff`, `/doc-review`) only when the artifact on disk declares `maturity: requirements-ready`.
A `pending-confirmation` checkpoint or no artifact at all leaves only options 5, 6, and 7 visible,
and "Done for now" says plainly that no durable forward route exists yet.

*Legacy artifacts — tier 2 of the Phase 0.1 order.* Add one short paragraph, and cross-reference it
from the Phase 0.1 tier list so the two read as one rule rather than two. For an artifact missing the
producer facts, provenance may be inferred from durable document evidence; the inference is labelled
inferred in what the operator is shown; the operator confirms it before it is used; multiple
plausible matches are a hard stop, never a recency or filename guess; and discovery never writes to
the file. State that operator confirmation of an inference does **not** backfill the producer facts
into the legacy file — the confirmation governs this session only, and the file on disk is left
exactly as found.

*The section contract.* In `requirements-sections.md`, extend the Metadata list with `capability`,
`activity`, and optional `run`; describe `maturity` as taking `pending-confirmation` (boundary
recorded, not confirmed, no durable route) or `requirements-ready` (confirmed, routes available);
and add a short "Minimum artifact" subsection naming the four required parts. Field names stay
stable per that file's own rule.

Also **replace the topic-only resume sentence** at `requirements-sections.md:70`, which today says
`topic` is "the resume-detection key when Phase 0.1 scans `docs/brainstorms/`". After B1, resume
matches on `topic` **plus** `capability`, and a file carrying `topic` alone is a legacy artifact
routed to tier 2 of the Phase 0.1 order, not a match. Say both things in that sentence, so the
section contract and the skill cannot disagree about how resume finds a file.

*Resume.* In `plugins/saga/skills/resume/SKILL.md` Phase 0, add a document-scan step beside the
existing `saga.py scan`: for capabilities that write no Saga state, scan
`docs/brainstorms/*-requirements.md` and read frontmatter for `capability`, `activity`, `topic`, and
`maturity`. Apply the **same three-tier order** Phase 0.1 uses, stated in the same sequence: exact
producer-fact match first; then files lacking the producer facts, which route to the labelled
inference path rather than counting as absent; and only a genuinely empty scan reports no candidate.
One unambiguous match is a matched candidate that routes to `/brainstorm`; two or more plausible
matches stop and ask, reusing the existing Phase 1 disambiguation shape; a `pending-confirmation`
match is restored as a proposed boundary awaiting confirmation, never as finished work. This is a
read-only addition — Brainstorm still writes no Saga state.

*The spec — two edits in one pass, not one.* First, **scope the absolute sentence in §3.2**
(`plugins/saga/references/saga-spec.md:183-184`). It currently reads that maturity is derived, never
stored, and that no `maturity` key ever appears in frontmatter. Qualify it to **saga-tick**
frontmatter, which is what it has always meant — `requirements-sections.md:71` already documents a
stored artifact `maturity` today, so the sentence is over-broad before B1 touches anything. Leaving
it unqualified while B1 stores an artifact maturity would leave the canonical contract asserting both
"never stored" and "artifacts declare maturity".

Second, in §3.3 add a short note carrying the distinction the §3.2 edit now makes room for: the
derived-never-stored rule governs saga-tick frontmatter, while an off-chain artifact declares its own
`maturity` in its own frontmatter; `pending-confirmation` is a valid artifact maturity meaning the
boundary is recorded, unconfirmed, and carries no durable route; and name the declared
`brainstorm-scope-confirmation` gate. Both edits land in the same commit — the §3.3 note alone does
not repair the §3.2 sentence.

*Telemetry convention.* In `plugins/saga/references/gate-divergence-instrumentation.md:65`, remove
`brainstorm-<decision>` from the `gate_id` naming examples.

*Handoff maturity.* In `plugins/saga/scripts/handoff_envelope.py`, make `infer_maturity` read a
declared frontmatter `maturity` when the source resolves to an existing file that declares one, and
otherwise fall through to the existing path-based inference unchanged (KTD7).

**Patterns to follow.**

The gate-record marker grammar and its section-scoped coverage rule, per
`plugins/saga/scripts/lint_gate_absence_contract.py`. The existing frontmatter field discipline in
`plugins/saga/skills/brainstorm/references/requirements-sections.md` ("Field names are stable").
Resume's existing several-candidates disambiguation in `plugins/saga/skills/resume/SKILL.md` Phase 1.
Test conventions: `from __future__ import annotations`, module-level `ROOT = Path(__file__).parent.parent`,
the `_load()` importlib helper, full type annotations, long descriptive test names.

**Test scenarios.**

New module `tests/test_brainstorm_continuity_contract.py`. Every assertion runs through a
module-level `check_*(text)` predicate so U3 can mutate it (KTD3).

- *Provenance, positive.* Given the section contract's Metadata list, the three producer facts —
  producing capability, producing activity identity, and maturity — are all declared required. Expect
  all three present.
- *Checkpoint, positive.* Given the Phase 2.5 text, the checkpoint is written with
  `pending-confirmation` maturity and the exact proposed boundary before the confirmation question is
  posed, and no readiness-claiming artifact exists at that point. Expect the ordering stated
  explicitly.
- *Declared gate, positive.* Given `brainstorm/SKILL.md`, a `gate-record` marker with id
  `brainstorm-scope-confirmation`, `absence=HALT`, `transport=ask-user-question` sits in the Phase
  2.5 section. Expect exactly one such marker.
- *Resume restore, positive.* Given the resume rules in both `brainstorm/SKILL.md` Phase 0.1 and
  `resume/SKILL.md` Phase 0, an unambiguous match restores the proposed boundary and does not
  re-present settled decisions. Expect both statements present. Assert the rule, never a question.
- *Ambiguity stop, negative.* Given two or more plausible matches, the contract states a stop and
  forbids selection by recency, filename, or broad content match. Expect the stop stated and all
  three guess-modes explicitly refused. Assert the stop, never a chosen candidate.
- *Revision, negative.* Given a boundary revised after confirmation, writing at
  `requirements-ready` without fresh confirmation is refused and maturity returns to
  `pending-confirmation`. Expect the refusal stated.
- *Artifact-free outcome, negative.* Given an exploratory-only run, no file is written, no route
  from options 1 through 4 is shown, and nothing is labelled `requirements-ready`. Expect the
  route-gating tied to declared maturity, not to file existence.
- *Minimum artifact, positive.* Given the section contract, the minimum artifact names exactly the
  four parts and explicitly excludes architecture and implementation plan. Expect four parts and the
  exclusion.
- *Legacy inference, positive.* Given an artifact without producer facts, inference is labelled
  inferred, is operator-confirmed, and leaves the file on disk unchanged. Expect all three.
- *Telemetry, negative.* Given `brainstorm/SKILL.md`, no instruction references `saga.py save` or
  gate-divergence, and no new write path was introduced. Expect zero matches for both.
- *Marker census, positive.* Given `brainstorm/SKILL.md` after B1, exactly three `gate-record`
  markers exist and their ids are exactly `brainstorm-interrogation-gate` (the repointed survivor),
  `brainstorm-handoff-routing` (untouched), and `brainstorm-scope-confirmation` (added). Assert the
  id set, not just the count — a count alone would pass if the wrong marker were deleted and a
  different one added. Expect the old id `brainstorm-interrogation-choice` to appear nowhere.
- *Gate-absence agreement, integration.* Run the production lint
  (`plugins/saga/scripts/lint_gate_absence_contract.py`) as a subprocess against the real tree and
  expect exit 0 with `VIOLATIONS: 0`. This is the "the gate-absence contract agrees" half of issue
  913's telemetry criterion (F5).

New module `tests/test_handoff_envelope_maturity.py`.

- *Frontmatter wins, positive.* Given a `tmp_path` file under `docs/brainstorms/` declaring
  `maturity: pending-confirmation`, `infer_maturity` returns `pending-confirmation`.
- *Path inference preserved, positive.* Given a `docs/brainstorms/` path with no declared maturity
  and given each of `docs/ideation/`, `docs/plans/`, `docs/specs/`, `docs/work-sessions/`, and a
  `branch:` source, the pre-existing return values are unchanged.
- *Missing file, edge.* Given a source path that does not exist on disk, inference falls back to the
  path rule and raises nothing.

**Critical safeguards this unit declares** (U3 must carry a mutation case for each): the ambiguity
stop, the fresh-confirmation rule, the route-gating on declared readiness, and the
no-deferred-`saga.py save` rule.

**Verification.**

The twelve continuity assertions and the three maturity assertions pass. The production gate-absence
lint reports zero violations against the real tree. `grep -nE "saga\.py save|gate-divergence"
plugins/saga/skills/brainstorm/SKILL.md` returns nothing.
`grep -nEi "pending-confirmation|producing capability|producing activity"` on the same file returns
matches. Ruff check, ruff format check, and mypy over `plugins/ scripts/ tests/` are clean. No file
outside this unit's owned list appears in `git diff --name-only`.

**Commit message.**

```
feat(saga): unify the Brainstorm continuity contract and drop the unreachable telemetry promise

Brainstorm now records the producing capability and activity on its artifact, declares its
scope-confirmation gate through the existing gate-record mechanism, writes a durable
pending-confirmation checkpoint before any readiness claim, requires fresh confirmation after a
revision, and stops rather than guessing when resume finds more than one plausible match.
Artifact-free exploration writes nothing and exposes no durable route.

The gate-divergence telemetry instruction is removed: it deferred the record to a `saga.py save`
Brainstorm never performs, and it had no demonstrated consumer. The interaction-rules gate-record
marker is kept and repointed rather than deleted -- Markdown coverage in the gate-absence lint is
section-scoped, and deleting the marker leaves two AskUserQuestion sites uncovered.

`handoff_envelope.infer_maturity` now honours an artifact's declared frontmatter maturity, so an
unconfirmed checkpoint under docs/brainstorms/ can no longer hand off as requirements-ready.

No Brainstorm state store, queue, or save boundary was added.

Re #913
```

---

### U2. B2 — issue 914: adaptive judgment model and bounded helpers

Give Brainstorm one adaptive judgment model that measures consequence separately from product size,
tracks material concerns privately, and bounds its optional helpers by count as well as by kind.

**Goal.** Make rigor follow the actual trust boundary and failure consequences, make question
selection deliberate rather than incidental, and put a real ceiling on Phase 1 fan-out — with none
of it ever surfacing as a checklist.

**Requirements.** R1, R2, R4, R11, R12, R13, R14, R15, R16.

**Dependencies.** U1 (the confirmed-artifact boundary that question selection is defined against).

**Files owned and editable by this unit.**

`plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/references/sandbox-spawn-sites.md`,
`tests/test_brainstorm_judgment_contract.py` (new), `tests/test_sandbox_spawn_sites.py`,
`docs/engineering-journal/LEARNINGS.md`,
`docs/engineering-journal/DECISIONS.md`.

**Files this unit must not touch, because another unit owns them.**

`plugins/saga/skills/brainstorm/references/requirements-sections.md`,
`plugins/saga/skills/resume/SKILL.md`, `plugins/saga/references/saga-spec.md`,
`plugins/saga/references/gate-divergence-instrumentation.md`,
`plugins/saga/scripts/handoff_envelope.py` (all U1).
`tests/test_orchestrate_review_transport.py` (U4). The scenario, rubric, calibration, and mutation
modules under `tests/` (U3). `plugins/saga/references/concurrency-spawn-sites.md` — no unit touches
it (KTD10). The Saga release triad (the release commit).

**Approach — the concrete changes.**

*Consequence calibration, beside Phase 0.4.* Add a short subsection after the scope assessment,
marked internal. It states that product size and assurance need are different signals, and that
rigor is calibrated from the concrete factors actually present in scope: data sensitivity, granted
authority, exposure to untrusted input, reversibility and blast radius, safety, financial, legal or
operational consequence, recovery expectations, and auditability or consent obligations. It states
that rigor rises and falls as those enter or leave scope, that the trigger is never a domain name
alone, and that no named assurance level is used — the factors themselves are named.

*The private concern model, inside Phase 1.2.* Phase 1.2 is already marked "internal analysis, not a
user-facing checklist", so the model extends it rather than creating a new phase. Add: for each
concern material to the current idea, privately classify current understanding as Clear, Partial,
Missing, or Not material; `Not material` is a legitimate outcome and needs no follow-up; the map is
a changing heuristic for choosing the next valuable question, re-evaluated as the idea changes.
State the privacy rule explicitly and adjacently — the map is never written to the artifact, never
persisted, never rendered as a document section, never shown as a score, and never surfaced to the
operator in any form.

*Question selection, inside Phase 1.3.* Add the selection rule: ground repository-discoverable facts
before asking the operator; ask a question only when its answer could materially change scope,
acceptance behaviour, consequence-based safeguards, or the downstream route; among the candidates,
prefer the greatest combination of consequence and uncertainty; one at a time, per interaction rule
1. State that the primary process keeps synthesis, creativity, the private model, and every
operator-facing exchange.

**Say explicitly how the new rule composes with the live must-probe rule, in the same edit.** Live
Phase 1.3 (`plugins/saga/skills/brainstorm/SKILL.md:216-217`) requires one probe per rigor gap Phase
1.2 actually found and forbids Phase 1 ending with an un-probed gap that is present. The new rule
**orders and filters idle questions only** — it decides which of the questions Brainstorm might
otherwise volunteer are worth the operator's turn, and in what order. A rigor gap Phase 1.2 actually
found is still probed, one at a time, and is never filtered out by the consequence test. Write that
sentence into the skill. Without it the skill ships two question policies and the worker has to pick
one; reading the new rule as a filter would silently drop probes the current contract requires.

*The helper policy, inside Phase 1.1.* Replace the unbounded "This scan may run parallel `Explore`
agents" with the ceiling. Lightweight work, and work whose repository context is already available,
launches zero helpers. Standard and Deep work may launch at most one read-only repository-grounding
scout and at most one independent claim verifier, and may launch either only when it has a distinct
evidence question — two helpers on the same question is one helper too many. These are ceilings, not
required launches. Name the mechanisms: the grounding scout is `subagent_type: Explore`; the claim
verifier is `subagent_type: saga:readonly-verifier` with `isolation: "worktree"`, degrading through
the fallback ladder in `plugins/saga/references/sandbox-spawn-sites.md` when the agent type is absent
from the session roster. State that helpers may not write files, may not choose requirements, and
may not address the operator.

*The line-17 summary.* Update "The only parallel work allowed is the Phase 1 context scan
(`Explore` agents)" to name the bounded helper set instead, so the skill's opening summary and its
Phase 1.1 policy agree.

*The spawn-site inventory — one table row, one subsection, per KTD4.* Add **one** row to the
in-scope table in `plugins/saga/references/sandbox-spawn-sites.md`, starting `| \`brainstorm\` |`,
for the Phase 1.1 **claim verifier** only. Its Spawn site cell names the phase rather than any line
reference (F1); its Resolver work-shape cell holds `judgment`, a real registry key. That row is
truthful in its class: the claim verifier is verify-class and does carry
`subagent_type: saga:readonly-verifier` plus `isolation: "worktree"`.

Record the Phase 1.1 **grounding scout** outside that table, in a new short subsection beside the
existing "Ad-hoc spawn rule". It is a survey-class spawn, read-only by tool omission
(`subagent_type: Explore`), deliberately **not** worktree-isolated because it only reads the
repository. Describe its read-only posture exactly as the fallback ladder already does — read-only
by omission of `Edit`/`Write`/`NotebookEdit`, with `Bash` retained — and name that Bash retention as
the residual, the same one the `Explore` rung documents. Do **not** write "structurally cannot
write" into the inventory: it is a guarantee `Explore` does not give, and it would sit next to a
ladder that says otherwise. State the not-worktree-isolated rationale in the same subsection, so the
omission reads as a decision rather than a gap. Do not give it a `read-only-survey` row in the in-scope
table — that table's class contract is the `read-only-verify` profile, and a survey spawn filed
there would be false.

Also change the table preamble's "Each of these four skills" to "Each of these skills" — the count is
itself the hand-maintained volatile figure this run is retiring, and adding a row makes it wrong.

*The inventory guard.* Add `"brainstorm": ROOT / "plugins/saga/skills/brainstorm/SKILL.md"` to
`IN_SCOPE_SKILLS` in `tests/test_sandbox_spawn_sites.py`. Both of that module's existing assertions
then cover the new row for free: the inventory must name the skill and its file path, and
`brainstorm/SKILL.md` must reference `readonly-verifier` at its spawn site. Without this the new row
is decorative — the reviewer's D6 finding was precisely that the hardcoded four-skill dict would let
a class contradiction ship green.

**Patterns to follow.**

The in-scope table's exact column shape and the parser in
`tests/test_tier_resolver.py::_parse_spawn_site_work_shapes`, which reads the first and fourth cells
of every row starting `| \``. The valid work-shape keys are the registry keys in
`plugins/fleet-core/scripts/fleet_commons/tier_policy.json` plus the `role-tier:` aliases; a bare
model literal fails `test_spawn_site_enumeration_routes_through_resolver`. The existing
internal-analysis framing of Phase 1.2. The same `check_*(text)` predicate discipline as U1 (KTD3).

**Test scenarios.**

New module `tests/test_brainstorm_judgment_contract.py`.

- *Privacy, negative — the load-bearing one.* Given `requirements-sections.md`, none of the four
  state names appears as a section, a metadata field, or required content; given
  `brainstorm/SKILL.md`, the privacy rule is stated and the state names appear only inside the
  internal Phase 1.2 block. Expect zero operator-facing occurrences.
- *Named assurance levels, negative.* Given `brainstorm/SKILL.md`, the patterns
  `\b(low|standard|high)[ -]assurance\b` and `assurance level` match nothing, while the concrete
  consequence factors are all present by name. Expect zero level matches and every factor found.
- *Lightweight helpers, positive.* Given the helper policy, Lightweight work launches zero helpers.
  Expect that stated explicitly.
- *Helper ceiling, negative.* Given the helper policy, Standard and Deep cannot exceed one grounding
  scout and one claim verifier, and neither may launch without a distinct evidence question. Expect
  both the count ceiling and the distinct-question requirement stated.
- *Helper capability, negative.* Given the helper policy, helpers cannot write files, choose
  requirements, or address the operator, and the two named subagent types are the read-only ones.
  Expect all three prohibitions and both agent types.
- *One question at a time, positive.* Given `brainstorm/SKILL.md`, the one-question-per-turn boundary
  is stated. Expect it present, with no assertion about which question, its wording, or its position.
- *Spawn-site row, positive.* Given `sandbox-spawn-sites.md`, exactly **one** Brainstorm row exists
  in the in-scope table, its work-shape cell is `judgment`, and it contains no `~line`, no
  digit-bearing line reference, and no other hand-maintained location value. Expect one row and zero
  line references.
- *Scout is outside the verifier class, negative.* Given `sandbox-spawn-sites.md`, the Phase 1.1
  grounding scout is documented outside the in-scope table and no in-scope row names `Explore`.
  Expect the scout subsection present and zero `Explore` occurrences among in-scope rows — this is
  the assertion that keeps the inventory's class contract truthful (D6).
- *Inventory guard covers Brainstorm, integration.* `tests/test_sandbox_spawn_sites.py` now lists
  Brainstorm in `IN_SCOPE_SKILLS`, and both of its assertions pass: the inventory names the skill and
  its path, and `brainstorm/SKILL.md` references `readonly-verifier`. Run it, do not reimplement it.
- *Resolver routing, integration.* The pre-existing
  `tests/test_tier_resolver.py::test_spawn_site_enumeration_routes_through_resolver` still passes
  with the one new in-scope row present. Run it, do not reimplement it. The scout carries no
  resolver work-shape, because it is not a row in the enumerated table.
- *Grounding before asking, positive.* Given Phase 1.3, repository-discoverable facts are grounded
  before the operator is asked. Expect that stated.
- *Must-probe rule survives, positive.* Given Phase 1.3, the live one-probe-per-found-gap rule and
  the no-un-probed-gap exit condition are both still present, and the skill states that the new
  consequence test orders idle questions rather than filtering a found rigor gap. Expect all three —
  this is the assertion that stops the new rule from silently narrowing the old one (D7).

**Critical safeguards this unit declares** (U3 must carry a mutation case for each): the helper
ceiling, the map-privacy rule, the no-named-assurance-level rule, and the helper read-only
capability rule.

**Verification.**

All twelve judgment assertions pass, and the tier-resolver enumeration test and
`tests/test_sandbox_spawn_sites.py` both still pass.
`grep -nEi "\b(low|standard|high)[ -]assurance|assurance level" plugins/saga/skills/brainstorm/SKILL.md`
returns nothing. `grep -nEi "brainstorm" plugins/saga/references/sandbox-spawn-sites.md` returns
**one** in-scope table row plus the scout subsection — never two table rows. A second in-scope row
means D6 was undone; the Approach is the authority here, not a grep habit carried over from the
pre-review draft. U1's continuity assertions still pass unchanged — B2 must not disturb
them. Ruff, format, and mypy are clean. No file outside this unit's owned list appears in
`git diff --name-only` against the B1 commit.

**Commit message.**

```
feat(saga): adaptive judgment model and bounded read-only helpers for Brainstorm

Brainstorm now calibrates assurance rigor from the concrete trust-boundary and failure factors
actually in scope -- data sensitivity, granted authority, untrusted input, reversibility and blast
radius, consequence, recovery, auditability -- separately from product size and never from a domain
label. No named assurance levels were introduced.

Concerns material to the idea are privately classified Clear / Partial / Missing / Not material and
used only to choose the next valuable question. The map is never persisted, never rendered as a
document section, and never shown to the operator.

Phase 1 fan-out is bounded by count as well as kind: Lightweight launches no helpers; Standard and
Deep may launch at most one read-only grounding scout (Explore) and at most one claim verifier
(saga:readonly-verifier in a disposable worktree), each requiring a distinct evidence question.
Helpers are read-only by tool omission, not by instruction, and may not write files, choose
requirements, or address the operator.

The claim verifier joins the sandbox spawn-site inventory's in-scope table as one row with work-shape
judgment and no hand-maintained line reference, and Brainstorm joins IN_SCOPE_SKILLS so that row is
enforced rather than decorative. The grounding scout is recorded outside that table: it is a
survey-class Explore spawn, read-only by omission of Edit/Write/NotebookEdit with Bash retained, and
deliberately not worktree-isolated. Filing it in the in-scope table would have made the inventory
claim a readonly-verifier profile it does not carry.

Re #914
```

---

### U3. B3 — issue 915: layered behavioural evidence

Build the three-layer evidence model — deterministic contract tests, scenario evaluations scored per
dimension, and mutation proof — plus the evaluator-trust rule that stops one model judge from
blocking alone.

**Goal.** Give the behaviour B1 and B2 shipped an oracle that is honest about what it can and cannot
prove, runs offline, and never turns a conversational judgment into a unit-test fact.

**Requirements.** R17, R18, R19, R20, R21, R22, R23.

**Dependencies.** U1, U2 (the behaviour being evaluated, and their declared critical safeguards).

**Files owned and editable by this unit.**

`tests/test_brainstorm_evidence_model.py` (new), `tests/test_brainstorm_scenarios.py` (new),
`tests/test_brainstorm_mutation_proofs.py` (new), `tests/data/brainstorm/scenarios.json` (new),
`tests/data/brainstorm/rubric.json` (new), `tests/data/brainstorm/calibration.json` (new),
`plugins/saga/references/brainstorm-evidence-model.md` (new),
`docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`.

**Files this unit must not touch, because another unit owns them.**

`plugins/saga/skills/brainstorm/SKILL.md` and everything else U1 and U2 own — B3 adds evidence over
settled behaviour and changes none of it. `tests/test_orchestrate_review_transport.py` (U4). The
Saga release triad (the release commit).

**Approach — the concrete changes.**

*Prior art, reviewed and recorded.* Before designing, record the fit of the four candidates already
in the repository. `plugins/saga/scripts/engine_benchmark.py` plus
`plugins/saga/references/benchmark-suite.yaml` — a data-file case suite with an injectable runner and
deterministic graders, whose own header states graders are never model-graded. **Reuse the shape.**
`plugins/saga/references/rubrics/` plus `plugins/saga/scripts/lifecycle_review.py` — Markdown rubrics
with narrative scoring bands, read by a CLI and applied by a reasoning agent. **Reuse the dimension
vocabulary, decline the Markdown carrier** because R19's per-dimension reporting needs the rubric as
data. `scripts/lint_test_shape.py` plus `tests/test_lint_test_shape.py` — a standalone AST visitor
plus fixtures plus a whole-suite invariant. **Reuse the mechanism** for the R17 mechanical check.
`tests/test_concurrency_conformance.py::_mutate_source` — in-memory string surgery feeding a pure
analyzer. **Reuse the mechanism** for mutation proof. Record each verdict in
`plugins/saga/references/brainstorm-evidence-model.md`.

*Layer 1 — the deterministic boundary, mechanically enforced.* In
`tests/test_brainstorm_evidence_model.py`, add an `ast`-based check over the sources of every
`tests/test_brainstorm_*.py` module: collect the string literals appearing in `assert` statements
and fail on any that ends with `?` or opens with an interrogative (`what`, `how`, `why`, `who`,
`when`, `which`, `can you`, `could you`), and on any assertion comparing an ordered sequence of two
or more such literals. Walk the AST; never substring-search the file. This proves R17 over the test
sources rather than by reviewer promise.

*Layer 2 — scenario evaluations as data.* `tests/data/brainstorm/scenarios.json` holds the case set.
Each case carries an id, an idea seed, `product_size` and `consequence` as **independent** fields, the
material dimensions in play, and the expected outcome per dimension. The set includes at minimum a
premature-convergence case, a missed-material-gap case, a consequence-calibration case, and a
checklist-overengineering case. `tests/data/brainstorm/rubric.json` holds the dimensions and their
band descriptions as data, never inlined in assertions. `tests/test_brainstorm_scenarios.py` proves
the set's shape and coverage offline: both variables vary independently across the set, all four
required cases exist, and every case names dimensions the rubric defines.

*The grader and the transcript boundary — case data is authored, transcripts are captured, and the
two are labelled apart.* `grade(transcript, rubric) -> dict[dimension, Result]` is a pure function
returning one result per material dimension. The runner is injectable exactly as
`engine_benchmark.run_suite` takes one, so live grading is opt-in behind an environment variable and
never runs in CI.

**Authored case data is expected and permitted.** `scenarios.json`, `rubric.json`, and
`calibration.json` are authored by the unit: they define the idea seed, the two independent
variables, the material dimensions, and the expected outcome per dimension. That is design input,
not evidence, and the four required failure-mode cases — premature convergence, missed material gap,
consequence calibration, checklist overengineering — are authored this way. They must be: the post-B2
checkpoint exercises a working Brainstorm and will not produce four failure modes on demand.

**Captured transcripts are optional and additive.** Where a checkpoint transcript exists for a case,
`grade()` runs against it and the case records `transcript: captured`. Where none exists, the case
records `transcript: none` and the offline suite still proves everything it claims to prove — the set's
shape and coverage, the grader's determinism, the per-dimension reporting, the absence of an
aggregate, the gating rule, and calibration agreement. A missing failure-mode transcript never blocks
U3.

**The one thing that stays forbidden is mislabelling.** No case may carry a synthesized transcript
labelled `captured`. That is the harness-substitution failure this constraint exists to prevent: a
fabricated conversation presented as evidence of real behaviour. Record all three rules in
`brainstorm-evidence-model.md`, alongside the plain statement that the offline suite proves the
grading and gating machinery rather than proving any given brainstorm was good.

*No aggregate number.* Assert directly that the result object exposes no `score`, `total`,
`aggregate`, `overall`, or `quality` key at any level, and that no consumer computes one.

*Layer 3 — the evaluator-trust rule.* A pure function
`is_blocking(finding, *, reproducible, second_grader_agrees, operator_adjudicated) -> bool` returns
`True` unconditionally for a deterministic contract failure, and for a model-judged finding returns
`True` only when the scenario is reproducible **and** either a second independent grader agrees or an
operator adjudication is recorded. Assert every combination directly — this is R20's "assert the
gating logic directly".

*Calibration.* `tests/data/brainstorm/calibration.json` holds a small fixed set of cases with their
expected grades. The test runs the grader over them and reports agreement per case, failing when
agreement drops below the recorded floor. Assert that the calibration set produces no aggregate
target of its own.

*Mutation proof.* `tests/test_brainstorm_mutation_proofs.py` carries one case per safeguard U1 and U2
declared critical — eight in total: the ambiguity stop, the fresh-confirmation rule, the
route-gating on declared readiness, the no-deferred-save rule, the helper ceiling, the map-privacy
rule, the no-named-assurance-level rule, and the helper read-only capability rule. Each case reads
the real file, removes the rule's text in memory, calls the same `check_*` predicate the contract
test calls, asserts it reports a violation, then asserts the unmutated text reports none. It also
carries a meta-assertion: every safeguard named in the declared-critical list has a case, so adding
a safeguard without a mutation case fails.

*The reference document.* `plugins/saga/references/brainstorm-evidence-model.md` records the three
layers, the evaluator-trust rule, the calibration set and its drift floor, the prior-art verdicts,
and — explicitly — what this suite does not prove. It states that formal completeness and
contradiction review stay after the confirmed artifact, in Document Review or a narrow post-write
validator, never in the live dialogue.

**Patterns to follow.**

`plugins/saga/scripts/engine_benchmark.py` for the data-suite plus injectable-runner plus
deterministic-grader shape. `scripts/lint_test_shape.py` for the `ast.NodeVisitor` plus dataclass
report plus whole-suite invariant shape. `tests/test_concurrency_conformance.py::_mutate_source` for
in-memory mutation. The `_load()` importlib idiom for reaching production modules.

**A hard constraint on every new module in this unit.** `scripts/lint_test_shape.py` runs over the
whole `tests/` directory in CI and fails any `test_*.py` that shows a fake signal without a
production signal. Any module here that defines a stub, fake, or synthetic grader **must** also
genuinely import or path-load real production code — the `_load()` idiom against
`plugins/saga/scripts/` satisfies this. A bare string constant naming a production path does not.

**Test scenarios.**

- *Deterministic coverage, positive.* The deterministic layer covers artifact metadata, resume
  lookup, the declared gate, scope-confirmation state, terminal routing, and helper ceilings. Expect
  each named area to have at least one passing assertion, discovered from the modules rather than
  hardcoded twice.
- *No dialogue assertions, negative — the load-bearing one.* Given the AST walk over every
  `tests/test_brainstorm_*.py`, no assert-statement string literal is question-shaped and no
  assertion compares an ordered sequence of them. Expect zero findings on the real tree; expect a
  seeded question-shaped literal in an inline source string to be found.
- *Scenario independence, positive.* Given the case set, `product_size` and `consequence` each take
  more than one value and their combinations are not collinear. Expect both varied independently.
- *Required cases, positive.* The four required case kinds are present. Expect all four, and expect
  each to carry an explicit `transcript` label of either `captured` or `none` — never absent.
- *Transcript labelling, negative.* No case labelled `transcript: captured` lacks a stored
  transcript, and no stored transcript is attached to a case labelled `none`. Expect zero
  mismatches — this is the assertion that stops a synthesized conversation being presented as
  captured evidence (D8).
- *Offline suite is complete without captured transcripts, positive.* With every case set to
  `transcript: none`, the shape, coverage, per-dimension reporting, no-aggregate, gating, and
  calibration assertions all still pass. Expect a green run — a missing failure-mode transcript
  must never block U3.
- *Per-dimension reporting, positive.* `grade()` returns one entry per material dimension named by
  the case. Expect a one-to-one mapping.
- *No aggregate, negative.* The result object exposes no aggregate key at any level and no consumer
  computes one. Expect zero matches.
- *Gating logic, negative and positive.* `is_blocking` returns `True` for a deterministic failure;
  `False` for a model-judged finding that is reproducible but has neither second-grader agreement nor
  operator adjudication; `False` for one that has agreement but is not reproducible; `True` for
  reproducible plus agreement; `True` for reproducible plus recorded adjudication. Expect all five.
- *Calibration drift, positive.* The calibration set runs and reports per-case agreement, and a
  seeded disagreeing grade drops the reported agreement. Expect drift surfaced, not absorbed.
- *Mutation completeness, positive.* Every safeguard in the declared-critical list has a mutation
  case, and each case fails on the weakened text and passes on the restored text. Expect eight cases
  and a meta-assertion that the list and the case set match.
- *Offline and side-effect-free, negative.* The harness writes nothing under `docs/brainstorms/`,
  touches no path under `.claude/saga/`, and opens no socket. Expect the tree unchanged after a full
  run.

**Verification.**

All scenario, calibration, mutation, and evidence-model assertions pass offline with no network. The
AST check reports zero findings on the real tree and finds a seeded violation. `git status --short`
is clean of any generated artifact after the suite runs.
`uv run pytest tests/ -q -k "brainstorm"` passes as one set, proving R31 for the Brainstorm modules.
`scripts/lint_test_shape.py` over `tests/` still exits 0. Ruff, format, and mypy are clean.

**Commit message.**

```
test(saga): layered behavioural evidence for Brainstorm -- scenarios, calibration, mutation proof

Three layers, each matched to what it can honestly prove. Deterministic contract tests cover the
mechanics with exactly one correct result. Scenario evaluations, stored as data with product size
and consequence as independent variables, score judgment per material dimension -- with no aggregate
quality number anywhere. Mutation cases weaken each safeguard #913 and #914 declared critical and
prove the named test goes red.

A model-judged finding cannot block alone: blocking needs a reproducible scenario plus either a
second independent grader agreeing or a recorded operator adjudication, and that logic is asserted
directly rather than described. A fixed calibration set surfaces grader drift instead of letting it
become policy.

An AST check over the Brainstorm test sources proves mechanically that no deterministic test asserts
a question, its wording, or the order of the dialogue. The harness runs offline, writes no brainstorm
artifacts, and mutates no Saga state; live grading is opt-in and never runs in CI. What this suite
does not prove is recorded alongside what it does.

Re #915
```

---

### U4. B4 — issue 916: maintenance cleanup

Retire the stale contract data around Brainstorm without changing behaviour, and pin the lifecycle
ordering mechanically instead of by hand.

**Goal.** Drop the retired runner names while keeping the behavioural ownership rule they were
standing in for, stop the lifecycle description drifting across skills, state the Shaping
distinction once, and record the dispatch-line-count finding without manufacturing a removal.

**Requirements.** R24, R25, R26, R27, R28.

**Dependencies.** U1, U2, U3. This unit is last by the run contract, and its ownership-rule test keys
off the helper policy U2 writes.

**Files owned and editable by this unit.**

`plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/references/saga-spec.md`,
`tests/test_orchestrate_review_transport.py` (cross-plugin),
`tests/test_saga_lifecycle_consistency.py` (new),
`tests/test_brainstorm_dialogue_ownership.py` (new), `docs/engineering-journal/LEARNINGS.md`,
`docs/engineering-journal/DECISIONS.md`.

**Files this unit must not touch.**

`plugins/saga/skills/{ideate,office-hours,strategy,loop,plan,founder-review}/SKILL.md` — under KTD6
no skill's lifecycle prose is edited, and that holds for the four block-carrying skills and the two
out-of-set files alike. `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` — its
retired-transport guard stays exactly as it is, which is why no Orchestrate release bump is
warranted. Everything U1, U2, and U3 own beyond the two files shared with U1 above. The Saga release
triad (the release commit).

**Approach — the concrete changes.**

*Retired runner names.* Replace the "Reviewer-session transport" section
(`plugins/saga/skills/brainstorm/SKILL.md:59-64`) with a "Dialogue ownership" section that states
the behavioural rule and names no retired file. Brainstorm owns the interactive creative dialogue:
the synthesis, the judgment, the private concern model, and every operator-facing exchange stay in
this session and are never delegated to another vendor session or runner. Its only permitted
delegated work is the bounded read-only helper set B2 defined. Any cross-vendor session transport is
Orchestrate's, and a required session that is not in the Orchestrate run record is a HALT, never an
invented review.

*The cross-plugin test.* Remove `ROOT / "plugins" / "saga" / "skills" / "brainstorm" / "SKILL.md"`
from the `STAGE_SKILLS` tuple in `tests/test_orchestrate_review_transport.py:25-31`. That entry is
precisely the Brainstorm-motivated name pinning: the loop in
`test_stage_skills_do_not_invoke_retired_transport_as_launch_path` asserts each listed file contains
`engine-registry.yaml` and `capability metadata`, which the rewritten section no longer does. Change
nothing else in that file — the four remaining stage skills, the retired-file-nonexistence checks at
lines 167-168, the `_RETIRED_TRANSPORT` refusal tests, and every other review-transport assertion
stay exactly as they are.

*The lifecycle consistency check.* Add `tests/test_saga_lifecycle_consistency.py` holding the
canonical Think-phase command ordering as one module-level constant and asserting that each of the
four block-carrying skills renders a consistent sub-sequence of it. The verified membership is
`plugins/saga/skills/ideate/SKILL.md` (block opens at line 15),
`plugins/saga/skills/loop/SKILL.md` (line 26), `plugins/saga/skills/office-hours/SKILL.md`
(line 27), and `plugins/saga/skills/plan/SKILL.md` (line 19). Discover the set by matching the block
shape, not by hardcoding those line numbers — they drift, and F1 is this run's own lesson about
hand-maintained line references.

Two files are deliberately outside the set and the test must say so in a comment rather than
silently skipping them. `plugins/saga/skills/founder-review/SKILL.md:30` carries a differently
worded variant with no `/ideate` line; it is not the duplicated block, and asserting against it
would pin answer wording rather than ordering. `plugins/saga/skills/strategy/SKILL.md` carries only
inline ordering mentions at lines 3, 9, and 117.

Consistency means ordering, not answer text. Also assert Brainstorm's placement is unchanged:
`/ideate` precedes `/brainstorm` and `/brainstorm` precedes `/plan` in every block. **No skill's
lifecycle prose is edited** (KTD6; OQ1 settled).

*The Shaping distinction — one new statement, against a named pre-existing mention.* Add one short
paragraph to `plugins/saga/references/saga-spec.md` §4, beside the authoritative enum domains:
`Shaping` is an Operations **board** Status, not a Saga lifecycle phase, not a Saga command, and not
an automatic consequence of any Saga capability completing. Mission Control is the only routine
writer of that field. Cross-reference `plugins/saga/skills/plan/SKILL.md` §0.6, which already states
the same derivation boundary, and note that Office Hours' lowercase "discovery / shaping" (lines 3,
19, and 149) is ordinary English for its own activity, unrelated to the board column.

**"Exactly once" means exactly one *new* authoritative statement, not one mention repo-wide.** The
live tree already carries the distinction at `plugins/saga/skills/plan/SKILL.md:123-132`, and KTD6
forbids B4 from editing that file — so a check demanding a single repo-wide mention cannot pass and
would push the worker either into a failing test or into a vacuous one. `saga-spec.md` currently
contains **zero** occurrences of "shaping", verified at the pinned base, which is also why the
original verification recipe was wrong before the new paragraph existed. Define the assertion as: `saga-spec.md` gains exactly one Shaping statement; every pre-existing
mention is **named and expected**, asserted present rather than forbidden; and no Saga surface
outside that named set gains a new one.

The complete pre-existing inventory under `plugins/saga/references/` and `plugins/saga/skills/`, at
the pinned base, is six hits across three files — enumerate all three in the test, not two:

| File | Hits | Kind |
|---|---|---|
| `plugins/saga/skills/plan/SKILL.md` | lines 123, 130 | The board-Status derivation boundary. B4 cannot edit it (KTD6) |
| `plugins/saga/skills/office-hours/SKILL.md` | lines 3, 19, 149 | Lowercase "discovery / shaping", ordinary English for Builder mode |
| `plugins/saga/skills/office-hours/references/frame-diagnostic.md` | line 153 | The same lowercase Builder-mode heading, in Office Hours' own reference |

The reference-file hit is the one an earlier draft of this plan missed. A closed-world check that
inventoried only the two `SKILL.md` files would fail on the live tree, which is exactly the class of
error round 1 caught one file higher up.

*The preflight finding.* Record F1 in the commit message and in a dated `LEARNINGS.md` entry: the
design record described a volatile hand-maintained source-line count in a Brainstorm dispatch table;
at 0.148.0 the target does not exist, `sandbox-spawn-sites.md` has no Brainstorm row and no
Brainstorm surface carries a line count, and nothing was removed. Record F2 in the same entry: the
duplicated lifecycle block lives in four skills — ideate, loop, office-hours, plan — so the set named
in the run contract wrongly included Strategy and wrongly omitted Loop and Plan, and the resolution
taken was a mechanical check rather than a prose edit.

**Patterns to follow.**

`REQUIRED_ADJACENT_PAIRS` in `tests/test_saga_docs_coverage.py` — the repository's existing idiom of
a hardcoded expected-set constant checked against real files. The positive-assertion discipline of
issue 916: assert the ownership rule is present, never that a historical string is absent. The
`check_*(text)` predicate discipline from KTD3 so U3's mutation harness can reach these rules too.

**Test scenarios.**

New module `tests/test_brainstorm_dialogue_ownership.py`.

- *Ownership rule, positive — the one that must survive.* Given `brainstorm/SKILL.md`, the skill
  states that synthesis, judgment, the private model, and every operator exchange stay in this
  session and are not delegated to an unrelated runner, and names the bounded read-only helper set as
  the only permitted delegation. Expect both statements present. Assert presence, never string
  absence.
- *No retired filename, negative.* Given `brainstorm/SKILL.md`, no retired runner filename appears.
  Expect zero matches for `engine_offer`, `engine_session_runner`, and "the retired runner". This is
  the one negative issue 916 explicitly asks for, and it is paired with the positive above so it
  cannot stand alone.
- *No growing blacklist, negative.* The rewritten section names no implementation filename at all.
  Expect zero `.py` filenames in the Dialogue ownership section.
- *Routing contract intact, integration.* Orchestrate's `plan_units` still refuses a unit naming a
  retired transport. Run the existing
  `tests/test_orchestrate_review_transport.py::test_review_transport_refuses_every_retired_transport_name`;
  do not reimplement it.

New module `tests/test_saga_lifecycle_consistency.py`.

- *Block membership, positive.* Discovering the block by shape across `plugins/saga/skills/*/SKILL.md`
  finds exactly the four verified files — ideate, loop, office-hours, and plan. Expect four, and
  expect `founder-review` and `strategy` absent from the discovered set. A fifth file appearing means
  a new copy was added and the check should say so rather than absorb it.
- *Block consistency, positive.* Each of the four renders a sub-sequence of the canonical ordering.
  Expect all four consistent.
- *Placement unchanged, negative.* In each of the four blocks, `/ideate` precedes `/brainstorm` and
  `/brainstorm` precedes `/plan`. Expect no inversion.
- *Drift is caught, control.* A seeded block with `/plan` before `/brainstorm`, fed to the same
  predicate as an inline source string, is reported. Expect a finding — proving the assertion is not
  vacuous.
- *Out-of-set files, negative.* The predicate reports nothing for `founder-review/SKILL.md` and
  `strategy/SKILL.md`, and the test records why each is out of set. Expect no finding, and expect the
  reason stated rather than the files silently skipped.
- *Shaping, positive.* `plugins/saga/references/saga-spec.md` carries exactly one Shaping
  statement — it carries zero today, so this assertion is doing real work. Expect one.
- *Shaping pre-existing mentions, positive.* All three pre-existing files still carry their hits:
  `plan/SKILL.md` §0.6 (the derivation boundary), `office-hours/SKILL.md` (three lowercase generic
  uses), and `office-hours/references/frame-diagnostic.md:153` (the same Builder-mode heading in
  Office Hours' reference). Assert all three are **present**; do not forbid them. B4 can edit none of
  them, so a test that forbade any would fail on the live tree (round-1 D3, round-2 D2).
- *Shaping, negative.* No `plugins/saga/commands/*.md` declares a `shaping` command, no Saga surface
  states an automatic Brainstorm-to-board transition, and no Saga surface outside the named set above
  adds a fourth Shaping mention. Expect zero commands, zero transitions, zero new mentions.

Pre-existing coverage that must still pass unchanged: every test in
`tests/test_orchestrate_review_transport.py` except the removed `STAGE_SKILLS` member, and the four
remaining stage skills' assertions within the loop.

**Verification.**

`uv run pytest tests/test_orchestrate_review_transport.py -q` passes with no assertion weakened
beyond the one removed tuple member. `grep -nE "engine_offer|engine_session_runner|retired runner"
plugins/saga/skills/brainstorm/SKILL.md` returns nothing. The lifecycle check discovers exactly the
four block-carrying skills, passes on the real tree, and fires on the seeded inversion.
`grep -cin "shaping" plugins/saga/references/saga-spec.md`
returns 1 where it returned 0 before the change, and
`grep -rniE "shaping" plugins/saga/references/ plugins/saga/skills/` shows that one new statement
plus exactly the six named pre-existing hits across three files — `plan/SKILL.md` lines 123 and 130,
`office-hours/SKILL.md` lines 3, 19, and 149, and
`office-hours/references/frame-diagnostic.md` line 153 — and nothing beyond that enumerated set. `git diff --name-only` names no file under
`plugins/saga/skills/{ideate,office-hours,strategy,loop,plan,founder-review}/`, and no file under
`plugins/orchestrate/`. Ruff, format, and mypy are clean.

**Commit message.**

```
chore(saga): retire stale Brainstorm contract data and pin lifecycle-order consistency

The Brainstorm contract no longer names deleted scripts. The prose that told the agent not to run
engine_offer.py and not to launch engine_session_runner.py is replaced by the behavioural rule it
was standing in for: Brainstorm owns the interactive creative dialogue -- synthesis, judgment, the
private model, and every operator exchange stay in this session, and its only permitted delegation
is the bounded read-only helper set. Cross-vendor session transport stays Orchestrate's, and a
session absent from the run record is a HALT.

The Brainstorm entry is removed from the Orchestrate review-transport test's STAGE_SKILLS tuple --
that entry was the Brainstorm-motivated name pinning. Every other Orchestrate assertion, including
the checks that the deleted runner files do not exist and the retired-transport refusals, is
untouched, and orchestrate.py is unchanged.

A new mechanical check pins the lifecycle ordering across every skill carrying the duplicated
block, rather than single-sourcing prose into the highest-traffic skills. Preflight found that block
in exactly four skills -- ideate, loop, office-hours, and plan. The set named in #912 and #916 was
wrong in both directions: it included strategy, which carries only inline mentions, and omitted loop
and plan. founder-review carries a differently worded variant and is out of set. Brainstorm's
placement between Ideate and Plan is unchanged.

Shaping gains exactly one new authoritative statement, in the Saga specification's enum-domain
section, as an Operations board Status -- not a Saga phase, not a Saga command, and never an
automatic consequence of a Brainstorm completing. plan/SKILL.md section 0.6 already stated the same
derivation boundary and is left untouched; the new paragraph cross-references it rather than
duplicating or replacing it.

Preflight finding, recorded and acted on by removing nothing: the volatile dispatch line count the
design record describes has no live target at 0.148.0. sandbox-spawn-sites.md carries no Brainstorm
row and no Brainstorm surface carries a source-line count.

Re #916
```

---

### U5. Release — one shared Saga release update

One commit brings the Saga release triad into agreement at 0.149.0 after all four child commits are
frozen.

**Goal.** Satisfy the tri-lock parity gate and the diff-aware bump guard once, at the end, rather
than four times.

**Requirements.** R29, R30.

**Dependencies.** U1, U2, U3, U4.

**Files owned.**

`plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`.

**Approach.** Set the Saga version to `0.149.0` in `plugin.json` and in the Saga entry of
`.claude-plugin/marketplace.json`, and add a `## [0.149.0] - <merge date>` section to
`plugins/saga/CHANGELOG.md` at the top, matching the bracketed heading convention the file already
uses. Group the entry under `### Added` and `### Changed` covering all four units. Leave the
Orchestrate surfaces at 3.0.8 (KTD11).

**Patterns to follow.** The existing `## [0.148.0] - 2026-08-29` heading shape. Both
`tests/test_release_triad.py` and `scripts/check_release_surface_parity.py` compare the same triad
independently, so all three surfaces must agree exactly.

**Test expectation: none — this unit ships no behaviour.** Its correctness is proven by the existing
release-surface gates rather than by new tests.

**Verification.** `uv run python scripts/sync_marketplace.py --check` passes.
`uv run python scripts/check_release_surface_parity.py` passes.
`uv run python tools/release_surface_diff_guard.py --base-ref origin/main` passes for `saga` and
raises nothing for `orchestrate`. The CHANGELOG heading lint's fleet baseline passes. This is the
first commit in the run at which `bash scripts/gate.sh` can exit 0.

**Commit message.**

```
chore(saga): release 0.149.0 -- Brainstorm continuity, judgment, evidence, and maintenance

One shared release update for the four-unit Brainstorm improvement run (#913, #914, #915, #916).
Orchestrate is unchanged at 3.0.8: only its review-transport test changed, and tests are exempt from
the release-surface bump guard.

Re #912
```

---

## Runtime checkpoint — after U2 integrates

The only runtime proof before the final review. A disposable Claude tab loads the unmerged candidate
for that session alone, never through the machine-global marketplace cache (KTD9):

```bash
claude --plugin-dir /Users/jefcox/workspace/infiquetra/orch-claude-plugins-912/plugins/saga
```

The installed marketplace surface stays pinned at 0.148.0 throughout, so issue #907's reviews keep
running against the version they depend on. Exercise the candidate through its real command surface
— `/saga:brainstorm <topic>` — not by reading the skill file. Seven things must be observable for B1
and B2 to count as genuinely working.

| # | What must be observable | Fails if |
|---|---|---|
| 1 | A Standard or Deep brainstorm reaching scope confirmation writes `docs/brainstorms/<date>-<topic>-requirements.md` with `maturity: pending-confirmation`, `capability: brainstorm`, and an `activity` identity — **before** the confirmation question is posed | The file appears only after the answer, or carries `requirements-ready` at that point |
| 2 | Interrupting at that point and re-running `/saga:brainstorm <topic>` restores the proposed boundary and continues without re-asking any settled decision | Any settled question is re-presented, or the run starts fresh |
| 3 | With two plausible matching documents on disk, resume stops and asks which to use | It picks one by recency, filename, or content similarity |
| 4 | Confirming rewrites the same path at `requirements-ready` with the four required parts and no architecture or implementation content | A second file appears, or the artifact carries schemas, endpoints, or file layouts |
| 5 | Revising the boundary after confirmation returns maturity to `pending-confirmation` and refuses a `requirements-ready` write without fresh confirmation | The revised boundary inherits the earlier approval |
| 6 | An exploratory-only run that declines the artifact writes no file and offers no Plan, `/spec`, `/handoff`, or `/doc-review` route | Any durable route is offered, or a readiness claim is made |
| 7 | A Lightweight low-consequence ask launches zero helpers; a high-consequence ask (handles credentials, or takes a hard-to-reverse action) raises safeguard questions without any named assurance level, without a visible checklist, and without any of the four private state names appearing in operator-facing text | Helpers launch on Lightweight, more than one scout or one verifier launches, or a state name or level name is shown |

Record the transcripts. Where one covers a U3 scenario case, that case grades against it and is
labelled `transcript: captured`. The checkpoint exercises a working Brainstorm, so it will not
produce U3's four failure-mode cases — those are authored case data, which is expected and
permitted. What U3 must never do is label a synthesized transcript as captured.

---

## Scope Boundaries

**Explicitly out of scope — this run does not do these.**

- No Brainstorm state store, queue, save boundary, or new write path.
- No named assurance levels, no fixed adversarial convergence loop, no preset number of self-critique
  rounds.
- No new Saga command, and specifically no `/saga:shaping`.
- No automatic Brainstorm-to-board mutation and no board write from any Saga capability.
- No installed-plugin cache cleanup, and no marketplace registry refresh until immediately before the
  integrated pull request.
- No change to Brainstorm's lifecycle placement, its no-issue boundary, its no-board boundary, or its
  no-Saga-state boundary.
- No movement of architecture or implementation design out of `/plan`.
- No persistence of the private gap map, and no exposure of it as document sections.
- No rewriting, migrating, or reformatting of historical artifacts under `docs/brainstorms/`.
- No hardcoded model names for helpers; current launcher and run policy governs.
- No redesign of unrelated Saga capabilities, and no dispatch-table redesign.

**Deferred to follow-up work.**

- A demonstrated consumer for gate-divergence telemetry from an artifact-only capability. D3 permits a
  future consumer to use the confirmed artifact; that is out of scope now.
- Consolidating the two independent implementations of the release-triad parity check
  (`tests/test_release_triad.py` and `scripts/check_release_surface_parity.py`), noticed during
  preflight and unrelated to Brainstorm.
- Single-sourcing the lifecycle ordering into `plugins/saga/skills/loop/references/dispatch-table.md`
  and citing it from the four block-carrying skills. Declined for this run by the OQ1 ruling; kept
  here as the alternative should the block spread further.

---

## Document-review disposition

Two Saga Document Review rounds ran against this plan. Round 1, against the 1,207-line revision,
returned three P1 findings plus six improvements. Round 2, against the repaired 1,372-line revision,
returned **READY** — no P0 or P1 remains — plus four cleanup findings, all repaired here. Round 2
endorsed the round-1 D6 repair as the smaller truthful change and directed that the rejected
alternative not be reopened.

Artifacts: `docs/reviews/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan-doc-review.md`
(round 1) and `…-doc-review-r2.md` (round 2).

**Eight of the nine round-1 findings were repaired in this plan; D4 was repaired on issue 913 by the
coordinator.** Round 2 audited the table below and corrected two overclaims in it, both fixed here.

| id | priority | where it was repaired |
|---|---|---|
| D1 | P1 | U1 Phase 0.1 now states an ordered three-tier rule — exact match, then legacy inference, then empty scan — and Resume Phase 0 repeats the same order |
| D2 | P1 | U1 Phase 2.5 carries an authoritative post-B1 marker census of three, and the telemetry scenario is split into a telemetry assertion plus an id-set census assertion |
| D3 | P1 | U4 redefines "exactly once" as one *new* saga-spec statement and fixes the verification grep, which was wrong even before the change. **Corrected in round 2:** the pre-existing inventory is six hits across three files, not two — the earlier "nothing further" claim missed `office-hours/references/frame-diagnostic.md:153`. All three files are now enumerated |
| D4 | P2 | **Not repaired in this plan.** The plan was already correct; the stale card was. The coordinator amended issue 913 directly — the marker is retained and repointed, and `handoff_envelope.py` is on its owned list. Round 2 notes the card's verification grep still includes `gate-record`, which will match after B1; that is a card leftover and never a reason to delete the marker |
| D5 | P2 | U1's spec bullet now requires scoping the absolute §3.2 sentence to saga-tick frontmatter in the same commit as the §3.3 note |
| D6 | P2 | KTD4 and U2 put only the claim verifier in the in-scope table, record the `Explore` scout in its own subsection outside that class, and add Brainstorm to `IN_SCOPE_SKILLS` in `tests/test_sandbox_spawn_sites.py` so the row is enforced rather than decorative. **Corrected in round 2:** the design was repaired but U2's Verification, resolver bullet, and commit message still described two in-scope rows; all three now say one row plus the scout subsection |
| D7 | P2 | U2's Phase 1.3 bullet states that the consequence test orders idle questions only and never filters a found rigor gap, with a test asserting the live must-probe rule survives |
| D8 | P2 | U3 separates authored case data from captured transcripts, permits the four failure-mode cases to be authored, and forbids only mislabelling a synthesized transcript as captured |
| D9 | P3 | U1's section-contract bullet replaces the topic-only resume sentence with topic-plus-capability and points leftover files at the D1 legacy tier |

**Round-2 cleanup findings, all repaired.**

| id | priority | where it was repaired |
|---|---|---|
| R2-D1 | P2 | U2's Verification, resolver bullet, and commit message now all say one in-scope row plus the scout subsection; the scout is stated to carry no resolver work-shape; `sandbox_spawn_sites` joins the run-level pytest `-k` filter |
| R2-D2 | P2 | U4's Shaping inventory enumerates all six pre-existing hits across three files, adding `office-hours/references/frame-diagnostic.md:153`; the Approach, the test scenario, and the verification grep all match |
| R2-D3 | P3 | U1's verification says twelve continuity assertions (was eleven); U2's says twelve judgment assertions (was nine). Both now match their own lists |
| R2-D4 | P3 | The scout subsection no longer claims `Explore` "structurally cannot write". It states read-only by omission of `Edit`/`Write`/`NotebookEdit` with `Bash` retained, naming the same residual the fallback ladder documents |

---

## Operator rulings — settled, not reopened by any unit

All seven questions the plan raised are closed. A unit that needs one changed stops and surfaces
rather than deciding for itself.

**OQ1 — SETTLED: the mechanical consistency check, not prose single-sourcing.** D6 explicitly
permits "a minimal mechanical consistency check without moving the lifecycle", and that is what B4
builds. **No skill's lifecycle prose is edited.** The coordinator verified membership a third way and
it is narrower than either earlier count: the duplicated block appears in exactly four skills —
`ideate/SKILL.md:15`, `loop/SKILL.md:26`, `office-hours/SKILL.md:27`, `plan/SKILL.md:19`.
`founder-review/SKILL.md:30` carries a differently worded variant, not the block; `strategy` carries
only inline ordering mentions. **Issue 912's stated set — Ideate, Office Hours, Strategy — is wrong
in both directions: it wrongly includes Strategy and wrongly omits Loop and Plan.** Recorded in F2
and implemented in KTD6 and U4.

**OQ2 — SETTLED: keep the gate-record marker and repoint its id; delete only the unreachable
telemetry paragraph.** The scratch measurement in F3 — two live lint violations from deleting the
marker — is accepted. Implemented in KTD2 and U1.

**OQ3 — SETTLED as planned.** Phase 2.5 Path A (Lightweight, announce mode) has no confirmation to
declare, and issue 913's non-goals forbid adding a second approval step, so Lightweight writes
`requirements-ready` directly with no `pending-confirmation` stage. No change.

**OQ4 — SETTLED: `plugins/saga/scripts/handoff_envelope.py` joins B1's owned surface.** Its line-28
path-based maturity rule defeats issue 913's own artifact-free-exploration criterion, so 913 cannot
be true without it. No other unit owns that file. Implemented in KTD7 and U1.

**OQ5 — SETTLED as planned.** The offline layer proves the case set's coverage, the grader's
determinism, calibration agreement, and the gating rule — not that any given brainstorm was good.
Live grading stays opt-in and never runs in CI. No change.

**OQ6 — SETTLED with a session-scoped plugin load.** The disposable tab launches as
`claude --plugin-dir /Users/jefcox/workspace/infiquetra/orch-claude-plugins-912/plugins/saga`, which
loads the candidate for one session only and leaves the machine-global marketplace cache at 0.148.0
for issue #907. Implemented in KTD9 and the runtime-checkpoint section.

**OQ7 — SETTLED as planned.** The shared release update is a fifth `chore(saga)` commit, so each
child commit stays child-scoped, at the cost that the full gate is green only at that final commit.
No change.

---

## Verification (run-level)

Run at the final commit, on the integrated branch.

```bash
# Governing-principle guards: none of these may appear as live Brainstorm structure
grep -nEi "checklist|questionnaire|completeness gate" plugins/saga/skills/brainstorm/SKILL.md
grep -nE "saga\.py save|gate-divergence" plugins/saga/skills/brainstorm/SKILL.md
grep -nEi "\b(low|standard|high)[ -]assurance|assurance level" plugins/saga/skills/brainstorm/SKILL.md
grep -nE "engine_offer|engine_session_runner|retired runner" plugins/saga/skills/brainstorm/SKILL.md

# Positive contract markers
grep -nEi "pending-confirmation|producing capability|producing activity" plugins/saga/skills/brainstorm/SKILL.md
grep -nEi "brainstorm" plugins/saga/references/sandbox-spawn-sites.md

# Every Brainstorm-related module green TOGETHER, not each in isolation
uv run pytest tests/ -q -k "brainstorm or lint_gate_absence or orchestrate_review_transport or tier_resolver or sandbox_spawn_sites or saga_lifecycle_consistency or handoff_envelope"

# Release surfaces
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
uv run python tools/release_surface_diff_guard.py --base-ref origin/main

# The gate — backgrounded, per CLAUDE.md; result.txt is absent while it runs
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
tail -5 /tmp/gate.log
cat /tmp/gate-run/result.txt

git status --short --branch
```

**Definition of done for the run.** Every unit's own definition of done is met from evidence rather
than assertion; `bash scripts/gate.sh` exits 0 at the final commit; the seven runtime-checkpoint
observables were recorded; the five preflight findings are recorded in the journal and in the
relevant commit messages; and no unit manufactured a change for a gap that does not exist.
