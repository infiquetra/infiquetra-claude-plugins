---
title: "enhancement: /outcome start intent-capture ergonomics (--preview, blast-radius render, body-proposed defaults, suppressed forced questions)"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
wave: wave-1
objective: "Ship run-start intent envelope for lifecycle autonomy"
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# enhancement: /outcome start intent-capture ergonomics (--preview, blast-radius render, body-proposed defaults, suppressed forced questions)

### Objective

Ship run-start intent envelope for lifecycle autonomy

## Summary

`/outcome start` today takes only two positional arguments — `outcome_id` and
`objective` (`plugins/saga/scripts/outcome.py:1090`-ish, `p_start.add_argument("outcome_id")` /
`p_start.add_argument("objective")`) — and calls straight into `start(root, args.outcome_id,
args.objective)` (`plugins/saga/scripts/outcome.py:244`, `:1187`), which writes the branch-local
spec and store immediately. There is no dry-run path, no rendering of what the run is about to
authorize, no reuse of the Objective issue body operators already write, and no mechanism to avoid
asking a question whose answer the host already forces. This issue ships four UX facets of the
same start-time dialog as one coherent PR: a no-write `--preview`, a blast-radius render instead of
an abstract yes/no, body-derived confirmed defaults, and suppression of host-forced questions with
a recorded reason — the run-start half of the intent-capture story (its mid-run counterpart is
tracked separately as `pf-midrun-adjustment-envelope`).

## Problem Frame

- **`start` writes immediately, with no preview.** `p_start` is wired straight to
  `start(root, args.outcome_id, args.objective)` (`plugins/saga/scripts/outcome.py:1187`), which
  creates `docs/outcomes/<id>/outcome-spec.json` and its store (per the outcome SKILL's
  `start <id> <objective>` verb table entry, `plugins/saga/skills/outcome/SKILL.md`). There is no
  way today to see the intent the run will act on, or the DAG it derives, before any file is
  written.
- **The operator-gate model already distinguishes reversible-and-authorized from
  always-gated, but nothing renders that distinction at start time.** `reversibility_certificate.py`
  defines a `Tier.ALWAYS_OPERATOR` tier that "Gates even if otherwise reversible"
  (`plugins/saga/scripts/reversibility_certificate.py:73`), with `parent-issue-close` pinned to it
  regardless of mechanical reversibility (`plugins/saga/scripts/outcome_projection.py:81`,
  `plugins/saga/skills/outcome/SKILL.md:108`). The outcome SKILL enumerates the authorized-write
  allowlist (Status field, sub-issue close, label add/remove, one coalesced progress comment) versus
  the never-autonomous class (merge, deploy, parent-issue-close) in prose only
  (`plugins/saga/skills/outcome/SKILL.md`, "Performed autonomously" / "Never autonomous" sections).
  An operator starting a run has no single rendered surface showing which authorized-blast-radius
  class applies before dispatch begins.
- **The Objective issue body is unstructured input the operator already wrote, and it goes
  unused at start time.** `start` only accepts a free-text `objective` string
  (`plugins/saga/scripts/outcome.py:1090`); nothing reads the Objective issue's acceptance criteria
  to propose posture or leaf kinds, so the operator re-enters, by hand, information already captured
  in the issue body.
- **The host-capability probe that would let the dialog skip forced questions does not
  exist.** There is no `probe_host_capabilities()` function and no `decision_trail` /
  `suppressed` concept anywhere in `plugins/saga/scripts/outcome*.py` (verified absent by grep at
  grounding time). Today an operator on a host with no configured deploy target is still asked the
  merge/deploy posture question, even though the answer is mechanically forced to `gate` by the
  absence of a target.
- **Binding decisions this issue must compose with, not re-derive:** the `/outcome` campaign's
  settled architecture — "Derived-on-read status, never committed status fields; HALT-not-degrade;
  backend menu off-by-default with host-conditional degrade; cost ledger = leaf-produced fact"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`) — and the coordinator's own stated
  principle that "The committed spec is the canonical structure... deleting the git-common-dir cache
  loses nothing" (`plugins/saga/skills/outcome/SKILL.md`). A `--preview` path must not commit or
  cache anything; it renders a projection of what `start` *would* do.

## Key Decisions

- **`--preview` is additive to `start`, not a new verb.** It reuses the existing
  `status_card.py` renderer (`plugins/saga/scripts/status_card.py`, already the single emitter of
  operator-facing status headers for `resume`, `work`, `code-review`, `qa`, and `outcome status`
  via `project_outcome`) rather than inventing a second rendering path.
  Corresponds to `T8-F1-4`, tier `quick-win`.
- **Blast-radius rendering reuses the existing tier vocabulary, it does not invent a new
  one.** The preview must render the same `ALWAYS_OPERATOR` / authorized-allowlist distinction
  already coded in `reversibility_certificate.py:73` and already documented in prose in the outcome
  SKILL, not a new abstract yes/no gate. Corresponds to `T8-F3-2`, tier `quick-win`.
- **Body-derived defaults are proposals, never silent writes.** Reading the Objective issue
  body's acceptance criteria to pre-fill posture and leaf kinds (`T8-F2-8`, tier `structural`) must
  compose with the campaign's HALT-not-degrade stance: a proposed default is confirmed by the
  operator before it becomes part of the committed spec, never applied silently.
- **Suppression is recorded, not silent.** `probe_host_capabilities()` pins a forced answer with
  a `decision_trail` reason rather than simply not asking — an operator reviewing the run later can
  see *why* a question never appeared. Corresponds to `T8-F2-4`, tier `quick-win`.
- **Four facets, one PR.** All four are UX facets of the identical start-time dialog on the
  `/outcome start` path; consolidating them avoids four small PRs touching the same entry point in
  sequence, per the issue map's consolidation rationale (see Grounding References).

## Requirements

**No-write preview (T8-F1-4, primary)**

R1. `/outcome start` gains a `--preview` flag. When passed, `start` computes the intent envelope
and derives the DAG exactly as a normal `start` would, but performs zero filesystem writes under
`docs/outcomes/<id>/` and creates no store.

R2. `--preview` renders its output through the existing `status_card.py` renderer (the same
renderer `project_outcome` uses for `outcome status`), not a bespoke print path, so the preview and
the post-start `status` view share one visual vocabulary.

R3. The preview render includes both the intent (objective, proposed posture, proposed leaf kinds)
and the derived DAG (nodes, edges, ready frontier) in one view — an operator confirms both together,
not the intent alone.

**Blast-radius render (T8-F3-2, facet)**

R4. The preview additionally renders, for the run about to start, the concrete list of
`ALWAYS_OPERATOR`-tier operations (`reversibility_certificate.py:73`) applicable to this run's
declared leaf kinds and the concrete list of authorized-allowlist operations (Status-field set,
sub-issue close, label add/remove, one coalesced progress comment — per
`plugins/saga/skills/outcome/SKILL.md`'s "Performed autonomously" enumeration) — not an abstract
"proceed y/n" prompt.

R5. The rendered blast-radius list is exhaustive over every posture combination accepted by
`start`: an operator must not be able to construct a posture where an `ALWAYS_OPERATOR` item is
omitted from, or misclassified in, the rendered list.

**Body-proposed defaults (T8-F2-8, facet)**

R6. When `start` is invoked with a reference to an Objective issue (or the existing
`--from-objective` ingestion path referenced in `plugins/saga/scripts/outcome.py` /
`plugins/saga/skills/outcome/SKILL.md`), the dialog reads the Objective issue body's acceptance
criteria and proposes a default posture and a default set of leaf kinds derived from that text.

R7. A body-derived proposal is rendered as a labeled default in the preview/dialog and requires
explicit operator confirmation before it is written into the committed `outcome-spec.json`. An
unconfirmed proposal never reaches the spec.

**Suppressed forced questions (T8-F2-4, facet)**

R8. A new `probe_host_capabilities()` function inspects the current host for a configured deploy
target (and other host-forced conditions the dialog would otherwise ask about).

R9. When the probe finds no deploy target configured, the dialog does not prompt the
merge/deploy posture question at all; it pins `merge_deploy=gate` directly and appends a
`decision_trail` entry naming the reason (`no_deploy_target_configured`, or equivalent) so the
suppression is auditable after the fact.

R10. `decision_trail` entries are additive/append-only, following the existing append-only ledger
pattern already established elsewhere in the fleet (`docs/engineering-journal/DECISIONS.md:960`,
"append-only canonical log") rather than a mutable field that can be silently overwritten.

## Key Flows

F1. **Dry-run before commit.** Trigger: operator runs `/outcome start <id> <objective> --preview`.
The dialog computes intent + DAG, renders both via `status_card.py`, and the command exits having
written nothing under `docs/outcomes/<id>/`. Covers R1–R3.

F2. **Blast-radius confirmation.** Trigger: same preview render. The operator sees the concrete
`ALWAYS_OPERATOR` and authorized-allowlist lists for this run's leaf kinds, not a bare confirm
prompt, before deciding to actually run `start` without `--preview`. Covers R4–R5.

F3. **Objective-derived defaults, operator-confirmed.** Trigger: `start --from-objective <issue>`
(or equivalent) is invoked. The dialog proposes posture + leaf kinds parsed from the issue body's
acceptance criteria; the operator confirms or overrides before the spec is written. Covers R6–R7.

F4. **Forced answer suppressed and logged.** Trigger: `start` runs on a host with no configured
deploy target. The dialog never asks the merge/deploy question; `merge_deploy` is pinned to `gate`
and a `decision_trail` entry records why. Covers R8–R10.

## Scope Boundaries

- **Extends `/outcome start` only** — this issue does not touch `advance`, `attend`, `resume`,
  `graph`, `report`, `commit`, `export`/`import`, `approve`, or `prune` verb behavior.
- **Does not add new autonomous-write kinds.** The blast-radius render (R4–R5) surfaces the
  existing `reversibility_certificate.py` tier classification; it does not add, remove, or
  reclassify any operation in the authorized allowlist or the `ALWAYS_OPERATOR` set.
- **Body-parsing is best-effort proposal, not a new spec-ingestion pipeline.** R6's acceptance-
  criteria read is scoped to producing labeled *default proposals*; it is not a general-purpose
  Objective-body-to-spec compiler and does not replace the existing sub-issue reader / decompose
  path.
- **`probe_host_capabilities()` v1 scope is the deploy-target check only.** Other potential
  host-forced conditions (e.g. missing credentials for a given backend) are not required in v1;
  the function and `decision_trail` mechanism must be structured so additional probes can be added
  later without rework, but only the deploy-target probe ships in this issue.
- **Does not touch the mid-run adjustment-envelope work** (`pf-midrun-adjustment-envelope`) — that
  issue's quiesce/pause/andon-cord/undo-ledger primitives are a separate, later-lifecycle surface;
  this issue is start-time only.
- **No new CLI verb.** `--preview` is a flag on the existing `start` subcommand
  (`plugins/saga/scripts/outcome.py:1090`), not a new `p_start`-sibling subparser.

## Dependencies / Assumptions

- Assumes `status_card.py` (`plugins/saga/scripts/status_card.py`) is reusable for a pre-write
  projection, not only post-write status — verified as the fleet's established single-emitter
  pattern for operator-facing renders (`resume`, `work`, `code-review`, `qa`,
  `outcome status`/`project_outcome`).
- Assumes `reversibility_certificate.py`'s `Tier.ALWAYS_OPERATOR` enum
  (`plugins/saga/scripts/reversibility_certificate.py:73`) and its `authorize_write` gate
  (`:213`-`:262`) are the correct, and only, source of truth for the blast-radius render — the
  render must not hardcode a second copy of the allowlist that can drift from
  `reversibility_certificate.py`.
- Assumes the existing sub-issue reader (`discover_subissues`, referenced from the T8 survivor set
  as already wired into `start --from-objective`) is the ingestion point R6's acceptance-criteria
  read attaches to, rather than a new issue-fetch path.
- Verified absent at grounding time: `probe_host_capabilities`, `decision_trail`, and
  `merge_deploy` do not exist anywhere in `plugins/saga/scripts/outcome*.py` today (checked via
  grep). This issue introduces all three as new, minimal constructs — it is not wiring to an
  existing-but-unused mechanism.
- Builds on, and must not contradict, the `/outcome` campaign's binding decision: "Derived-on-read
  status, never committed status fields; HALT-not-degrade; backend menu off-by-default with
  host-conditional degrade; cost ledger = leaf-produced fact"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`). A `--preview` run must derive its
  projection the same way `status`/`project_outcome` derive theirs — never from a second,
  divergent computation path.

## Grounding References

| Absorbed id | Role | Title | Basis |
|---|---|---|---|
| `T8-F1-4` | primary | `start --preview`: confirm intent + derived DAG before any branch/spec/store is written | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — dod_sketch: merged PR adding a no-write `--preview` path reusing `status_card`; verified by a test asserting `--preview` renders the intent+DAG and leaves zero files under `docs/outcomes/<id>/` |
| `T8-F3-2` | facet | Intent dialog renders blast-radius, not abstract yes/no | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — `dod_sketch` field is a thin-seed pointer (`<<ccr:83db17ce3c02...>>`); intent reconstructed from the entry's `title`/`axis` (`intent-dialog-design`) plus the outcome SKILL's existing prose enumeration of authorized-vs-`ALWAYS_OPERATOR` operations and the grounding brief's `/outcome` binding-decision register (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`) |
| `T8-F2-8` | facet | Read the Objective issue body's acceptance criteria to pre-fill posture + kinds | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — `dod_sketch` field is a thin-seed pointer (`<<ccr:7b16460157a4...>>`); intent reconstructed from the entry's `title`/`axis` (`unstructured-to-structured`) and the sibling `T8-F1-1` survivor already wiring `discover_subissues` into `start --from-objective` |
| `T8-F2-4` | facet | Ask nothing the host already forces — suppress the deploy-gate question when no deploy target exists | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` — dod_sketch: merged PR adding `probe_host_capabilities()` + a `suppressed` list that pins forced answers and appends a `decision_trail` reason; verified by a test asserting a no-deploy-target host yields `merge_deploy=gate` with a recorded suppression and never prompts |

Binding decisions this issue must engage: the `/outcome` campaign's derived-on-read-status /
HALT-not-degrade stance (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`); the
`ALWAYS_OPERATOR` tier semantics already coded in `reversibility_certificate.py:73` and documented
in `plugins/saga/skills/outcome/SKILL.md`.

## Recommended Executor Profile

- **Model:** Sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** Sonnet at medium effort matches the issue-map's own executor recommendation
  for this slug. The work is UX/wiring shaped — a preview flag, a render reuse, a body-text
  parse-and-propose step, and a host probe — against one existing entry point (`outcome.py`'s
  `start` subcommand) rather than open-ended architectural judgment; inline is sufficient because
  all four facets land in the same file/module boundary and do not require cross-subsystem reviewer
  consensus the way a multi-subsystem capability would.

### Out-of-scope / non-goals
See Scope Boundaries above. In short: one `--preview` flag plus three dialog facets on the existing
`/outcome start` entry point — no new verb, no new autonomous-write kinds, no general Objective-body
compiler, no mid-run control surface, and `probe_host_capabilities()` ships the deploy-target probe
only (structured for, but not shipping, additional probes).

## Definition of Done

- Merged PR adding a no-write `--preview` path to `/outcome start` that reuses `status_card.py`,
  rendering intent + derived DAG together and leaving zero files under `docs/outcomes/<id>/`.
- The preview additionally renders the concrete authorized-blast-radius lists (`ALWAYS_OPERATOR`
  vs. authorized-allowlist operations, sourced from `reversibility_certificate.py`) for every
  posture combination `start` accepts.
- `start --from-objective` (or equivalent) proposes a default posture and leaf-kind set derived
  from the Objective issue body's acceptance criteria, rendered as a labeled default that requires
  explicit operator confirmation before it is written to the spec.
- A new `probe_host_capabilities()` suppresses the merge/deploy posture question on a host with no
  configured deploy target, pinning `merge_deploy=gate` and appending a `decision_trail` entry
  naming the reason.
- Full suite, lint, format, and type checks stay green.

### Acceptance criteria
- [ ] `/outcome start <id> <objective> --preview` renders intent + derived DAG and leaves zero
  files under `docs/outcomes/<id>/`. Check:
  `uv run pytest tests/test_outcome_start_preview.py -k preview_no_write` → passes.
- [ ] The preview lists exactly the `ALWAYS_OPERATOR` items (per
  `reversibility_certificate.py:73`) as gated under every posture combination `start` accepts — no
  posture omits or misclassifies an `ALWAYS_OPERATOR` item. Check:
  `uv run pytest tests/test_outcome_start_preview.py -k blast_radius_always_operator_exhaustive`
  → passes.
- [ ] A body-derived posture/kinds proposal never applies to the committed spec without explicit
  operator confirmation. Check:
  `uv run pytest tests/test_outcome_start_preview.py -k body_proposal_requires_confirm` → passes.
- [ ] A host with no configured deploy target yields `merge_deploy=gate` with a recorded
  `decision_trail` suppression entry and never prompts the merge/deploy question. Check:
  `uv run pytest tests/test_outcome_start_preview.py -k no_deploy_target_suppressed` → passes.
- [ ] `probe_host_capabilities()` is unit-testable in isolation (host-capability probe returns a
  structured result independent of the dialog). Check:
  `uv run pytest tests/test_outcome_start_preview.py -k probe_host_capabilities_unit` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

## Out-of-scope / non-goals

- Any change to `advance`, `attend`, `resume`, `graph`, `report`, `commit`, `export`/`import`,
  `approve`, or `prune` behavior.
- Adding, removing, or reclassifying any operation in the `ALWAYS_OPERATOR` set or the authorized
  allowlist — the render surfaces the existing classification, it does not change it.
- A general-purpose Objective-issue-body-to-spec compiler; R6/R7 scope to proposing labeled
  defaults only.
- Additional `probe_host_capabilities()` checks beyond the deploy-target probe (e.g. backend
  credential probes) — deferred; the function is structured to accept them later.
- The mid-run adjustment-envelope work (quiesce, pause points, andon-cord, undo ledger) — tracked
  separately as `pf-midrun-adjustment-envelope`.
- A new CLI subcommand — `--preview` is a flag on the existing `start` subparser.

### Files expected to change
Indicative only; exact set is `/plan`'s to determine.

- `plugins/saga/scripts/outcome.py` — `--preview` flag on `p_start`; wiring to
  `probe_host_capabilities()` and the body-proposal path.
- `plugins/saga/scripts/status_card.py` — render support for a no-write intent+DAG preview
  projection alongside the existing post-write status render.
- `plugins/saga/scripts/reversibility_certificate.py` — read-only consumption point for the
  blast-radius render (no new tiers added; existing `Tier.ALWAYS_OPERATOR` classification is
  surfaced, not changed).
- `plugins/saga/scripts/outcome_spec.py` — new `decision_trail` / `merge_deploy` fields on the
  intent envelope, if not already modeled elsewhere in the spec.
- `plugins/saga/references/outcome-spec.md` — documentation of the new `--preview` flag,
  blast-radius render, body-proposal flow, and `decision_trail`/suppression mechanism.
- `plugins/saga/skills/outcome/SKILL.md` — verb-table and flow documentation update for
  `start --preview`.
- `tests/test_outcome_start_preview.py` — new test file: preview no-write, blast-radius
  exhaustiveness, body-proposal confirm-gate, suppression/`decision_trail`, probe unit test.
- `plugins/saga/.claude-plugin/plugin.json` — version bump (new flag + dialog behavior).
- `.claude-plugin/marketplace.json` — metadata sync for `saga`.
- `plugins/saga/CHANGELOG.md` — entry for `--preview`, blast-radius render, body-proposed
  defaults, and suppressed forced questions.

## Release-surface checklist

Because this issue changes `/outcome start`'s user-facing behavior and adds a new flag/dialog
surface, update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — metadata sync for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry for `--preview`, blast-radius render, body-proposed
  defaults, and the `probe_host_capabilities()`/`decision_trail` suppression mechanism.
- [ ] Version/metadata drift-guard tests updated to reflect the new flag/behavior (per CLAUDE.md
  step 6 — installed-plugin metadata must tell the same story as the diff).

### Verification
```bash
# New start-dialog tests
uv run pytest tests/test_outcome_start_preview.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```

Expected: all green; `--preview` writes zero files; blast-radius render is exhaustive over every
posture combination; body-proposal test asserts no unconfirmed write reaches the spec; suppression
test asserts a `decision_trail` entry is recorded and the merge/deploy question is never prompted
when no deploy target is configured.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`,
  slug `pf-outcome-intent-capture-ux`
- Source type: ideation issue-map (Gate B consolidation)
- Source title: Intent-capture ergonomics: start --preview, blast-radius render, body-proposed
  defaults, suppressed forced questions

### Intent

`/outcome start` today takes only two positional arguments — `outcome_id` and `objective` (`plugins/saga/scripts/outcome.py:1090`-ish, `p_start.add_argument("outcome_id")` / `p_start.add_argument("objective")`) — and calls straight into `start(root, args.outcome_id, args.objective)` (`plugins/saga/scripts/outcome.py:244`, `:1187`), which writes the branch-local spec and store immediately. There is no dry-run path, no rendering of what the run is about to authorize, no reuse of the Objective issue body operators already write, and no mechanism to avoid asking a question whose answer the host already forces. This issue ships four UX facets of the same start-time dialog as one coherent PR: a no-write `--preview`, a blast-radius render instead of an abstract yes/no, body-derived confirmed defaults, and suppression of host-forced questions with a recorded reason — the run-start half of the intent-capture story (its mid-run counterpart is tracked separately as `pf-midrun-adjustment-envelope`).

### Context library links

_none_

### Tests to add or update

- `tests/test_outcome_start_preview.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/377
- Number: 377
- Created at: 2026-07-04T07:54:22.912650+00:00

