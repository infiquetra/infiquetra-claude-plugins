# Archive — Infiquetra Claude Plugins

> **The graveyard of QUEUED, LEARNINGS, and DECISIONS items.** When something from `QUEUED.md` ships, it moves here as **SHIPPED**. When something is consciously rejected, it moves here as **REJECTED** with the reason + revisit conditions. When a `LEARNINGS.md` or `DECISIONS.md` entry is invalidated by new evidence, the pre-correction version moves here as **SUPERSEDED**.
>
> **Never silently delete.** History is the point — a future Claude (or human) reading "did we ever consider X?" or "why did we change our mind on Y?" gets the answer.
>
> **Append new entries to the top** within each section.

---

## Shipped

### Operator-choice framework — execution-backend decision contract (doc-only)  {#operator-choice-framework-shipped}

**SHIPPED 2026-06-02** (`infiquetra-lifecycle` `0.5.0`, PR `#171`, squash `e935bd4`). Was QUEUED P1 `#operator-choice-orchestration-framework`.

**Summary.** Shipped the operator-choice framework as a **doc-only foundation** of the engine-merge campaign: the canonical decision contract for the three execution backends — `inline` | `team-execution` | `cc-workflows-ultracode` — that lifecycle commands cite when they ask the operator which backend to run work through. Lifecycle owns the **choice**, not execution. Schema and rationale (auto-recommend + always-confirm, the `should_offer_team_execution`-plus-consensus / parallel-fan-out triggers, offer-BOTH-on-overlap, the hide-when-Workflow-absent capability gate, `/loop` + `/work` scope) recorded in DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework).

**Scope — a consumed doc + two offer hooks (deliberate).** This ships the reference doc, the two prose offer hooks, and a `saga-spec` cross-reference fix. The CLI-backed `recommend_execution_backend()` helper is **DEFERRED to the `/work` rebuild**, where it gets a real caller — adding it now would create an uncallable helper that drifts against the doc (the verified state of the existing `should_offer_team_execution`, defined but never called outside its test). The originally-queued sizing was "M / no scripts"; this ship honors that.

**What shipped.**
- `plugins/infiquetra-lifecycle/references/operator-choice.md` — the decision contract (the three backend enum strings, when each is offered, the always-confirm posture, the capability gate, graceful fallback). Complements `references/saga-spec.md` (storage contract).
- Short prose offer hooks in `/loop` and `/work` SKILLs that cite the doc and inline the choices (referencing the brainstorm channel-inline convention — redis-channel sessions cannot call AskUserQuestion — rather than copying it).
- `saga-spec.md` cross-reference fix tying `orchestration_mode` storage to the decision contract.
- Version bumps: plugin `0.5.0`, marketplace entry `0.5.0`; CHANGELOG.

**Consumers.** `/loop` and `/work` carry the offer hooks now; the other command rebuilds cite this doc as they land. The CLI-backed helper lands with the `/work` rebuild — see QUEUED [#rebuild-work-engine-merge](QUEUED.md#rebuild-work-engine-merge).

**Refs.** DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Decision contract: `plugins/infiquetra-lifecycle/references/operator-choice.md`.

### Saga foundation — durable, resumable work-state envelope (P0)  {#saga-foundation-shipped}

**SHIPPED 2026-06-02** (`infiquetra-lifecycle` `0.4.0`, PR `#170`). Was QUEUED P0 `#saga-concept-vecu-durable-resumable-work-state`.

**Summary.** Shipped the first foundation of the engine-merge campaign: a unified `saga` durable/resumable work-state primitive — a stable-id `save`/`restore`/`scan` engine writing gstack-style timestamped envelope files, plus the canonical spec the four consumers implement against when they're rebuilt. Schema and rationale (derived `kind-id` identity, append-only envelope log + derived index, three stored state axes + derived maturity, snapshot list semantics, plugin-level `references/` convention) recorded in DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation).

**Scope — an unconsumed primitive (deliberate).** This ships the engine, the three legacy scripts refactored into thin wrappers, and the spec. **No command actually calls `restore`/`scan` after this PR** — consumer wiring is each consumer's own queued item. The new engine is validated by its own unit tests + manual smoke; the wrappers keep every legacy CLI flag and JSON key. The originally-queued sizing was "M / spec-only"; the user chose full-unify-now + characterize-first testing, making it realistically effort L — an accepted, deliberate growth, one PR not a doc.

**What shipped.**
- `plugins/infiquetra-lifecycle/scripts/saga.py` — the engine: derived `kind-id` (`issue-<N>`/`task-<slug>`, sticky), append-only `sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md` envelope log (filename-as-order, never mtime), derived atomic `state.json` index, gstack frontmatter+body envelope, `save`/`restore`/`scan`/`context` ops with `root:Path` + `now`/`runner` injection.
- The three legacy scripts (`scaffold_checkpoint.py`, `find_inflight_work.py`, `load_saga_context.py`) refactored into thin wrappers delegating to `saga.py` (zero CLI-flag/JSON-key removals).
- `plugins/infiquetra-lifecycle/references/saga-spec.md` — the canonical contract (new plugin-level `references/` convention).
- Tests `tests/test_infiquetra_lifecycle_saga.py` (characterize-first → intended-behavior); plugin-version + `saga.py`-existence updates in `tests/test_infiquetra_lifecycle_plugin.py`.
- Version bumps: plugin `0.4.0`, marketplace entry `0.4.0`; CHANGELOG with the behavior-change + upgrade warning (complete in-flight loops before upgrading; legacy `checkpoints/` read as fallback for one version).

**Consumers remain queued.** `/plan`, `/work`, `/resume`, `/loop` implement against this spec when rebuilt — see QUEUED [#rebuild-plan-engine-merge](QUEUED.md#rebuild-plan-engine-merge), [#rebuild-work-engine-merge](QUEUED.md#rebuild-work-engine-merge), [#resume-engine-merge-saga](QUEUED.md#resume-engine-merge-saga), [#loop-engine-merge-saga-workflow-offload](QUEUED.md#loop-engine-merge-saga-workflow-offload).

**Refs.** DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`.

### Correct Asgard/Olympus model before SDLC handoff work  {#asgard-olympus-model-before-handoff}

**SHIPPED 2026-05-30** (`infiquetra-sdlc` commit `5fe5d91`; plugin sync commit `90956a4`).

**Summary.** Removed the stale assumption that Asgard feeds or promotes work into Mount Olympus
before building the SDLC handoff flow.

**What shipped.**
- Canonical `infiquetra-sdlc` docs and schema now define Asgard and Olympus as sibling target
  boards.
- Cross-team movement is explicit operator transfer, route, clone, or link action only.
- `sdlc-manager` now vendors the corrected schema, renders Asgard transfer notes, and no longer
  warns that every Asgard draft has Olympus readiness gaps.
- Prompt-alignment tests now reject the stale Asgard-to-Olympus promotion language in active
  plugin surfaces.

**Refs.**
- Requirements: [Infiquetra Loop SDLC Handoff](../brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md).
- Plan: [Add SDLC handoff flow](../plans/2026-05-30-002-feat-sdlc-handoff-flow-plan.md).

### Asgard/Olympus issue readiness workflow for `sdlc-manager`  {#asgard-olympus-issue-readiness}

**SHIPPED 2026-05-30** (PR #159, commit `74cd372`).

**Summary.** Added a prepared issue workflow that turns source text into reviewable Asgard or
Mount Olympus drafts, then creates issues only after readiness checks and a confirmed mutation
plan.

**What shipped.**
- `issue prepare` writes markdown drafts and JSON sidecars under `docs/sdlc-issue-drafts/`.
- `issue create-prepared` re-runs readiness, shows a mutation plan, repairs missing
  labels/templates, handles missing project mappings through PR flow, and records created issue
  state back onto drafts.
- Asgard and Mount Olympus readiness profiles with safe starting statuses.
- Natural-language skill/command/operator guidance for Asgard/Olympus issue creation from text.
- Plugin and marketplace metadata bumped to `1.6.0`.
- Unit, mocked mutation, and prompt alignment tests.

**Refs.**
- Ideation doc: [SDLC Manager Asgard/Olympus issue readiness](../ideation/2026-05-30-sdlc-manager-asgard-olympus-issue-readiness.md).
- Requirements: [SDLC Manager Issue Prepare Requirements](../brainstorms/2026-05-30-sdlc-manager-issue-prepare-requirements.md).
- Plan: [Add SDLC issue prepare workflow](../plans/2026-05-30-001-feat-sdlc-issue-prepare-workflow-plan.md).
- Learning: [Prepared issue creation needs an artifact boundary before mutation](LEARNINGS.md#prepared-issue-artifact-boundary).

### Align sdlc-manager prompts with current SDLC schema and release metadata  {#sdlc-manager-prompt-alignment}

**SHIPPED 2026-05-30** (PR #159, commit `74cd372`).

**Summary.** Aligned `sdlc-manager` operator prompts, command docs, issue/label references,
release metadata, and marketplace registration with the current Jeff Intent, Asgard, and Mount
Olympus operating model.

**What shipped.**
- Updated handwritten prompt/reference docs to use current actionable labels:
  `hermes-task`, `needs-plan`, and the type label.
- Kept `needs-analysis` and `needs-triage` documented only as legacy auto-label fallback labels.
- Fixed `sdlc-operator` Hermes-actionability wording and output examples.
- Bumped `sdlc-manager` plugin and marketplace metadata to `1.5.0`.
- Added prompt/reference drift guards for metadata, labels, and actionability claims.

**Refs.**
- Ideation doc: [2026-05-30-sdlc-manager-alignment-pass.md](../ideation/2026-05-30-sdlc-manager-alignment-pass.md).
- Learning: [Prompt docs need their own drift guards](LEARNINGS.md#prompt-docs-need-drift-guards).

### Add Infiquetra loop `/doc-review` command  {#infiquetra-loop-doc-review}

**SHIPPED 2026-05-29** (commit pending).

**Summary.** Added `/doc-review` to `infiquetra-loop` as an implementation-readiness review
surface for plans, requirements documents, formal SDLC artifacts, and strategy/scope documents
that are about to drive implementation.

**What shipped.**
- `/doc-review` command and skill.
- Safe in-place fixes, P-level findings, durable `docs/reviews/` artifact triggers, and a
  review-result contract.
- Formal SDLC routing through `blueprint-reviewer` delegates followed by readiness review.
- `/work` prompt/block guidance and issue-progress rendering fields for doc-review summaries.
- README, changelog, marketplace/plugin metadata, and contract tests.

**Refs.**
- Idea doc: [2026-05-29-infiquetra-loop-doc-review.md](../ideation/2026-05-29-infiquetra-loop-doc-review.md).
- Requirements: [2026-05-29-infiquetra-loop-doc-review-requirements.md](../brainstorms/2026-05-29-infiquetra-loop-doc-review-requirements.md).
- Plan: [2026-05-29-001-feat-infiquetra-doc-review-plan.md](../plans/2026-05-29-001-feat-infiquetra-doc-review-plan.md).
- Plan review: [2026-05-29-infiquetra-doc-review-plan-review.md](../reviews/2026-05-29-infiquetra-doc-review-plan-review.md).

### PR #112 — register `blueprint-reviewer` in marketplace + gitignore `.claude/`  {#pr-112-marketplace-fix}

**SHIPPED 2026-05-01** (commit `4da5705`, squash-merged from `fix/marketplace-register-blueprint-reviewer`).

**Summary.** Two-commit PR that:
1. Added the missing `blueprint-reviewer` entry to `.claude-plugin/marketplace.json` (15 plugins after the change, was 14).
2. Added `.claude/` to `.gitignore` and removed stray files `swap-pane` (0 bytes) and `uv.lock` (242 KB, unused — see DECISIONS).

**Why this matters in the archive.** This is the originating ship for the journal's first three real entries — the LEARNING about marketplace drift, the LEARNING about the `Edit` guard pattern, and the DECISION about repo hygiene. Future readers tracing those entries' "fixed in commit X" / "shipped via Y" links land here.

**Refs.**
- LEARNINGS: [marketplace drift](LEARNINGS.md#marketplace-drift), [marketplace edit guard](LEARNINGS.md#marketplace-edit-guard).
- DECISIONS: [gitignore `.claude/` + no `uv.lock`](DECISIONS.md#gitignore-claude-and-no-uv-lock).

---

## Rejected

### `/ce-doc-review` compatibility alias for `infiquetra-loop`  {#rejected-ce-doc-review-alias}

**REJECTED 2026-05-29.**

**Reason.** During requirements discussion, the user chose not to preserve the CE command name.
The Infiquetra command surface should be `/doc-review`.

**Revisit when.** Multiple users migrate from Compound Engineering and repeatedly fail to find
the Infiquetra command after normal README and marketplace documentation.

---

## Superseded

### No `uv.lock` while uv is not canonical  {#superseded-no-uv-lock-decision}

**SUPERSEDED 2026-05-08** by DECISIONS [uv canonical sync](DECISIONS.md#uv-canonical-sync).

**Original decision.** Add `.claude/` to `.gitignore`. Do not track `uv.lock`. Stray `swap-pane` (0-byte file from a tmux operation) deleted as one-off cleanup.

**Original rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.
- *Track `uv.lock`.* Rejected: `pyproject.toml` declares `requires = ["hatchling"]` with no `[tool.uv]` section. The repo uses hatchling for building and ad hoc `pip`/`uv` invocations for local dev tooling, so there was no reproducible-build promise being made by checking in a uv lockfile. Tracking it would imply uv was part of the build path.

**Original rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). `uv.lock` would make a build-tool claim the repo was not making at the time. Both were pure noise in the diff and confused contributors about what was authoritative.

**Why superseded.** The repo now adopts uv as the canonical dependency sync path and CI installs from `uv.lock` with `uv sync --locked --extra dev`.

---
