---
title: "capability: one predicate engine for revisit-when tripwires, backlog basis-decay, and never-fired lifecycle machinery"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Make the backlog and lifecycle self-improving"
wave: wave-3
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: one predicate engine for revisit-when tripwires, backlog basis-decay, and never-fired lifecycle machinery

### Objective
Make the backlog and lifecycle self-improving

### Intent

Three checkable-liveness gaps in this repo's own lifecycle machinery are the same shape — an
anchor (a claim about the world), a predicate (a checkable condition over that anchor), a probe
(something that evaluates the predicate against current reality), and an action (surface, comment,
propose, or sunset) — and none of the three currently runs:

1. **`DECISIONS.md` revisit-when conditions are prose, never checked.** 81 `**Revisit when.**`
   lines exist in `docs/engineering-journal/DECISIONS.md` (verified count via
   `grep -c "Revisit when" docs/engineering-journal/DECISIONS.md`), each stating a condition
   under which a binding decision should re-open — e.g. `docs/engineering-journal/DECISIONS.md:130`
   ("harness grows a per-agent timeout or scripts get a timer primitive"). None of them is wired to
   anything that evaluates whether the condition has come true; they are re-discovered only if a
   human happens to reread the file.
2. **Backlog issues carry a basis (grounding citation) that can go stale with no re-verification.**
   Issue-drafting practice (this very draft's own "Grounding references" section, and the exemplar
   at `docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.md`
   "Sources / Research" section) anchors every issue to specific `file:line` citations at draft
   time. Nothing re-checks, at board-review time, whether that anchor moved, was deleted, or was
   fixed by an unrelated PR — a stale-basis issue can sit open indefinitely pointing at code that no
   longer has the problem it names.
3. **Lifecycle machinery itself can silently never fire and nobody notices.** The promote pipeline
   is the concrete, already-verified instance: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`
   states "Promote ledger: 0 learnings ever promoted; no genuine ≥3-repo transcendent cluster. The
   cross-repo learning loop exists but has never fired," and the grounding brief's theme roster
   (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:172`) names this as unresolved. The
   `saga:promote` skill (`plugins/saga/skills/promote/SKILL.md`) has a fully specified,
   idempotency-ledger-backed mechanism (`plugins/saga/skills/promote/references/promotion-contract.md:16`,
   `:129`) that has simply never been exercised end to end — there is no standing check that would
   have surfaced that fact on its own.

The gap-synthesis pass that produced this repo's ideation backlog already recognized frames 1 and 2
share one machine: `G-hybrids-11` (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`)
explicitly merges "Checkable liveness for decisions AND backlog: revisit-when tripwires and
basis-decay share one predicate engine," absorbing `H-F3-10` (revisit-when → checkable predicates,
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`) and `H-F1-9` (basis-anchor
decay → self-re-verifying issues, same file). The never-fired detector (`H-F1-4`,
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`) is the identical machine pointed
at lifecycle machinery instead of decisions/issues: an anchor ("this pipeline is wired to fire"),
a predicate ("has it ever appended to its own ledger/log"), a probe (read the ledger), an action
(flag for sunset-or-fix at `/retro`).

This issue builds one shared tripwire registry + read-only scheduled evaluator + digest that all
three anchor types (decision revisit-when, issue basis, lifecycle-machinery firing-ledger) register
against, rather than three bespoke one-off scripts.

### Problem Frame

- `docs/engineering-journal/DECISIONS.md` has 81 revisit-when conditions and zero machinery that
  evaluates any of them (verified: `grep -rn "revisit-when\|Revisit when" plugins/` returns no
  script matches, only prose in `DECISIONS.md`).
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73` is a concrete, already-observed
  never-fired case: the promote pipeline's cross-repo learning loop "exists but has never fired."
  This is not hypothetical risk — it is a verified zero-firing fact about existing lifecycle
  machinery today.
- `saga:promote`'s own contract already has the durable, idempotency-ledger primitive this issue's
  firing-ledger needs a working example of: `plugins/saga/skills/promote/references/promotion-contract.md:16`
  ("idempotency ledger — is the frozen contract"), `:40-41` ("Promotion upsert keyed on a
  drift-stable source-key ... ledger each entry carries"). The append-only, source-keyed pattern
  used there is the pattern this issue's firing-ledger hooks should reuse, not reinvent.
- `plugins/saga/skills/retro/references/retro-passes.md` already runs an ordered, read-only,
  propose-diff-and-wait multi-pass procedure (`Pass 0` through `Pass 7`, headers at lines 8, 40, 63,
  78, 100, 114, 155, 175) with `Pass 5 — Journal promotion + curation` (line 114) as the natural
  place a sunset-or-fix audit step slots in without inventing a new invocation surface.
- No existing mechanism re-verifies an issue's basis after draft time. The issue-drafting convention
  (this document, the exemplar) treats `file:line` citations as write-once; nothing walks open
  issues and checks whether the cited anchor still exists / still says what the issue claims.

### Out-of-scope / non-goals
- Backfilling revisit-when checkability onto all 81 existing `DECISIONS.md` entries — v1 ships the
  engine and seeds it with a small number of real revisit-when rows (at least one already-checkable
  condition, e.g. the timer-primitive condition at `docs/engineering-journal/DECISIONS.md:130`) plus
  the promote-pipeline never-fired row; broad backfill is a follow-up.
- Building a new promotion mechanism, ledger schema, or clustering algorithm for `saga:promote` —
  this issue only adds a firing-ledger append hook to the *existing* contract
  (`plugins/saga/skills/promote/references/promotion-contract.md`) and reads it; it does not change
  promote's clustering, upsert, or gate logic.
- Auto-closing or auto-editing decayed issues or stale decisions — action is limited to surfacing
  (digest entry, `/retro` sunset-or-fix proposal, board-review comment); anything that mutates an
  issue, a decision entry, or lifecycle code stays propose-diff-and-wait per existing self-edit-safety
  convention (`plugins/saga/skills/retro/references/self-edit-safety.md`).
- A new standing scheduled service/daemon — the evaluator runs on-demand (wired into `/retro` and
  optionally a board-review pass), not as a background cron process; this repo's precedent is
  on-demand self-test over standing calibration harnesses (see the sibling silent-omission-gate
  issue's `--self-test`-not-calibration-loop precedent,
  `docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.md`).
- Wiring firing-ledger hooks into every lifecycle skill in the fleet — v1 wires the three explicitly
  named paths (promote, retro, and one fallback-ladder path); broader coverage is a follow-up
  informed by what the promote-pipeline case teaches.
- Changing the `DECISIONS.md` / `QUEUED.md` entry format itself beyond adding one optional
  machine-checkable field — this issue does not redesign the engineering-journal schema.

### Files expected to change
Indicative only; `/plan` determines exact set.
- `plugins/saga/scripts/liveness_tripwire.py` — new predicate engine: tripwire registry (anchor,
  predicate, probe, action), evaluator, digest emitter (proposed path).
- `plugins/saga/skills/promote/references/promotion-contract.md` — add firing-ledger append-hook
  contract note, reusing the existing drift-stable source-key ledger pattern (`:16`, `:40-41`).
- `plugins/saga/scripts/promote_scan.py` (or wherever `saga:promote`'s scan lives) — append-only
  firing-ledger write on every promote-pipeline invocation, including no-op runs.
- `plugins/saga/skills/retro/references/retro-passes.md` — extend `Pass 5 — Journal promotion +
  curation` (`:114`) with a sunset-or-fix audit step reading the firing-ledger and tripwire digest.
- `docs/engineering-journal/DECISIONS.md` — add the optional `revisit-check:` field to the schema
  documented at `:17` (the `> **Revisit when.**` blockquote), backfilled on at least one seeded row.
- `tests/test_liveness_tripwire.py` — new engine tests (repo-root collected).

### Tests to add or update
- `test_liveness_tripwire.py::test_fixture_tripwire_fires_and_appears_in_digest` — a fixture
  tripwire with a satisfied predicate fires and its entry appears in the evaluator's digest output.
- `test_liveness_tripwire.py::test_fixture_tripwire_does_not_fire_when_predicate_unsatisfied` —
  same fixture with an unsatisfied predicate does not appear in the digest (no false positive).
- `test_liveness_tripwire.py::test_promote_pipeline_surfaces_as_zero_firing_case` — the
  promote-pipeline firing-ledger row, seeded with zero entries (mirroring the real, already-verified
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73` state), is surfaced by the evaluator
  as the first zero-firing adjudicated case in the digest.
- `test_liveness_tripwire.py::test_stale_issue_basis_probe_flags_moved_anchor` — a fixture issue
  whose cited basis anchor (a `file:line`) has moved or been deleted is flagged by the basis-decay
  probe; an issue whose anchor still holds is not flagged.
- `test_liveness_tripwire.py::test_revisit_when_predicate_evaluates_seeded_decision` — the seeded
  `DECISIONS.md` revisit-when row's predicate evaluates correctly against both a
  condition-not-yet-true fixture and a condition-now-true fixture.
- `test_liveness_tripwire.py::test_evaluator_is_read_only` — running the evaluator makes no writes
  outside its own digest/ledger output paths (no mutation of `DECISIONS.md`, issue files, or promote
  ledger content).
- Full suite, format, lint, types stay green.

## Definition of Done
A shared tripwire registry, read-only scheduled evaluator, and digest cover all three anchor types
— decision revisit-when, issue basis-decay, and lifecycle firing-ledger — and are seeded with at
least one real revisit-when row plus the promote-pipeline's already-observed zero-firing case.
Firing-ledger append hooks are wired into the promote and retro paths, reusing the existing
drift-stable source-key ledger pattern rather than a new one, and every action stays surface-only
(digest entry, `/retro` sunset-or-fix proposal) with no auto-mutation of `DECISIONS.md`, issues, or
lifecycle code. Full suite, format, lint, and types stay green.

### Acceptance criteria
- [ ] A fixture tripwire with a satisfied predicate fires and appears in the digest; an
      unsatisfied one does not. Check: `uv run pytest tests/test_liveness_tripwire.py -k fixture_tripwire` → passes.
- [ ] The promote pipeline's real zero-firing state surfaces as the first zero-firing adjudicated
      case in the digest output. Check: `uv run pytest tests/test_liveness_tripwire.py -k promote_pipeline_surfaces_as_zero_firing_case` → passes.
- [ ] A stale open-issue basis probe flags a fixture whose cited anchor moved, and does not flag one
      whose anchor still holds. Check: `uv run pytest tests/test_liveness_tripwire.py -k stale_issue_basis_probe` → passes.
- [ ] A seeded real `DECISIONS.md` revisit-when row evaluates correctly against both a true and a
      false fixture condition. Check: `uv run pytest tests/test_liveness_tripwire.py -k revisit_when_predicate` → passes.
- [ ] The evaluator is read-only end to end (no `DECISIONS.md`, issue, or promote-ledger content
      mutation from a run). Check: `uv run pytest tests/test_liveness_tripwire.py -k evaluator_is_read_only` → passes.
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# New engine tests
uv run pytest tests/test_liveness_tripwire.py -v

# Manual smoke: run the evaluator against the real repo state and confirm the
# promote-pipeline zero-firing row surfaces in the digest
python3 plugins/saga/scripts/liveness_tripwire.py --evaluate --digest

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the manual smoke digest names the promote pipeline's zero-firing state as an
adjudicated case, sourced from the real `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73`
observation, not a synthetic fixture.

## Grounding References

- Absorbed ideas (from `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` and
  `.../survivors/OTHER.json`):
  - `G-hybrids-11` (primary, theme T10, frame `gap-hybrids`, axis `decision-and-basis-liveness`) —
    "Checkable liveness for decisions AND backlog: revisit-when tripwires and basis-decay share one
    predicate engine." Parents recorded as `H-F4-6`, `H-F3-10`, `H-F1-9`, `T10-F5-4`. dod_sketch:
    tripwire registry + read-only scheduled evaluator + digest, seeded with real revisit-whens and a
    basis-decay row; firing-ledger hooks in promote/retro/fallback paths feed a `/retro`
    sunset-or-fix audit.
  - `H-F1-9` (dedup-merged, theme `NEW:backlog-basis-decay`, frame F1, axis
    `provenance-expiry`) — "Basis-anchor decay: stale open issues re-verify their own grounding or
    close themselves." dod_sketch: basis-anchor re-verification script + scheduled mission-control
    pass that comments/labels decayed issues and surfaces close proposals at board review; verified
    when a seeded issue with a moved/fixed anchor emits a "basis decayed" comment + close proposal
    while an issue with holding anchors is re-stamped green. (This issue implements the
    re-verification *probe and surfacing* half; the mission-control comment/label/close-proposal
    wiring is a natural fast-follow once the probe exists — see non-goals.)
  - `H-F3-10` (dedup-merged, theme `NEW:revisit-when-machinery`, frame F3, axis `novel`) —
    "Revisit-when conditions become checkable predicates: decisions re-open on evidence, not
    memory." dod_sketch: `DECISIONS.md` entry schema gains an optional `revisit-check` field + a
    sweep script wired into `/retro` (and optionally CI) that evaluates predicates and emits a
    came-true report, with existing register entries backfilled where checkable.
  - `H-F1-4` (facet, theme T10, frame F1, axis `dead-machinery-audit`) — "Never-fired detector:
    lifecycle machinery must prove it has ever produced output or face sunset." dod_sketch: merged
    PR: firing-ledger append hooks in promote/retro/fallback code paths + a `/retro` audit step that
    emits sunset-or-fix proposals for never-fired machinery, verified by the promote pipeline
    surfacing as the first zero-firing adjudicated case.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72-73` — verified, already-observed
  zero-firing fact grounding `H-F1-4`'s acceptance case: "Promote ledger: 0 learnings ever promoted;
  no genuine ≥3-repo transcendent cluster. The cross-repo learning loop exists but has never fired."
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:172` — theme-roster line naming this gap as
  unresolved ("promote loop never fired").
- `docs/engineering-journal/DECISIONS.md:17` — the `> **Revisit when.**` schema line this issue's
  optional `revisit-check` field extends.
- `docs/engineering-journal/DECISIONS.md:130` — one concrete, already-checkable revisit-when
  condition ("harness grows a per-agent timeout or scripts get a timer primitive") usable as a seed
  row.
- `plugins/saga/skills/promote/references/promotion-contract.md:16`, `:40-41` — the existing
  drift-stable source-key idempotency-ledger pattern this issue's firing-ledger reuses rather than
  reinventing.
- `plugins/saga/skills/retro/references/retro-passes.md:114` (`Pass 5 — Journal promotion +
  curation`) — the existing ordered, read-only, propose-diff-and-wait pass this issue's
  sunset-or-fix audit step extends.
- `plugins/saga/skills/retro/references/self-edit-safety.md` — binding constraint: every edit that
  is not a pure-append new journal entry is propose-diff-and-wait; this issue's action side (surface,
  don't mutate) is designed to that constraint.
- Binding decision built on: the org-wide `revisit-when` convention itself (`DECISIONS.md`'s own
  frontmatter note, `docs/engineering-journal/DECISIONS.md:3`, "capture rationale + tradeoff +
  revisit-when condition + commit hash") — this issue is the first machinery that actually checks
  the condition half of that convention instead of leaving it as prose.

### Recommended executor profile
- Model: sonnet
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution
- External LLM: none
- Justification: this is mechanical predicate-engine plumbing (registry, evaluator, digest, ledger
  append hooks) reusing an already-existing, already-tested ledger pattern
  (`promotion-contract.md`'s drift-stable source-key ledger) — no architectural judgment call large
  enough to warrant opus. High effort reflects that it must land three coordinated anchor types
  (decision revisit-when, issue basis, lifecycle firing-ledger) behind one shared engine without
  breaking `saga:promote`'s or `saga:retro`'s existing read-only/propose-diff-and-wait contracts.
  Team-execution backend because the change spans `plugins/saga/skills/promote/`,
  `plugins/saga/skills/retro/`, and `docs/engineering-journal/`, benefiting from validator-gated
  review across that split.

### Release-surface checklist
Required in the same PR because this changes `saga:promote` and `saga:retro` skill-visible behavior:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + changelog pointer for the new
      firing-ledger hooks and revisit-check field support.
- [ ] `.claude-plugin/marketplace.json` — updated if the saga plugin's manifest entry changes.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the new liveness tripwire engine, the
      firing-ledger hooks in promote/retro, and the `DECISIONS.md` `revisit-check` field.
- [ ] Any drift-guard / metadata tests in `tests/` that assert plugin.json/marketplace.json/CHANGELOG
      stay in sync — updated to cover the new engine module and reference files.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording the predicate-engine pattern
      (anchor/predicate/probe/action) as the shared convention for future liveness/decay checks,
      including its revisit-when condition (e.g. "revisit when a fourth anchor type needs the same
      engine, or when auto-action beyond surfacing is proposed").

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan — in particular resolve the exact
`revisit-check` predicate DSL (or scripted-callback shape), the firing-ledger's on-disk format, and
where the sunset-or-fix audit step slots into `Pass 5` of `retro-passes.md` at implementation time.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (ids `G-hybrids-11`,
  `H-F1-4`), `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json` (ids `H-F1-9`,
  `H-F3-10`)
- Source type: ideation survivor set (Gate B, gap-hybrid + themes T10 / NEW:backlog-basis-decay /
  NEW:revisit-when-machinery)
- Source title: One predicate engine for revisit-when tripwires, basis decay, and never-fired
  machinery

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/443
- Number: 443
- Created at: 2026-07-04T08:15:42.107666+00:00

