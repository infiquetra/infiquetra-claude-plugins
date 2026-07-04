---
title: "capability: mining-harvest writeback and a durable /mine-to-backlog harness"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Make the backlog and lifecycle self-improving
wave: wave-3
---

# capability: mining-harvest writeback and a durable /mine-to-backlog harness

### Objective

Make the backlog and lifecycle self-improving

### Problem / motivation

This repo already runs a session-mining pass and a promotion pass, but the pipe between
"we found something" and "the backlog/journal actually changed" does not exist yet — both
halves currently dead-end in a one-off report that nobody rereads.

- **The mining synthesis already happened once, and it evaporated.** This repo's own
  grounding pass ran workflow `wf_7e5d77a2-5c0`: 70/70 session skeletons distilled (0
  dropped), 27 sessions yielded 175 findings distilled into 10 recurring patterns plus 8
  singletons (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:120-121`). That
  synthesis lives only in a workflow journal today — there is no writeback path that turns
  a finding into a durable `LEARNINGS.md` entry or a backlog-ready issue draft, so the next
  mining pass starts from zero instead of compounding on the last one.
- **The promotion ledger already proves the "runs but nothing lands" failure mode at the
  cross-repo tier.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:76` records "0
  learnings ever promoted; no genuine ≥3-repo transcendent cluster... cross-repo learning
  loop exists but never fired." `/promote`'s scanner (`plugins/saga/scripts/promote_scan.py`)
  is a fully working deterministic backbone — `scan()`/`Candidate`/`ScanResult`
  (`:118`, `:230`), `source_key()` content-addressed identity (`:344`), the `Promotion`
  ledger record (`:352`), and a `scan`/`key` CLI (`parse_args` `:543`, `main` `:572`) — but it
  only fires when a human runs `/promote` by hand against `**Transcendent.**` markers
  someone already wrote. There is no equivalent gated writeback for the much larger, more
  frequent single-repo mining pass that produced the 175 findings above.
  `docs/engineering-journal/LEARNINGS.md:1-30` defines the target entry shape (Context /
  Evidence / Mechanism / Fix / Validation / Generalizable rule / `{#slug}` anchor) that any
  writeback must emit into, but nothing today emits into it automatically.
- **A second, related gap has no committed backlog counterpart either.** Theme 10 in this
  repo's ideation ("Cross-repo learning-mining & provenance discipline" —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:140`) names the promote loop never
  firing and 219 codex sessions with no mining substrate as the grounded gap. A synthesis
  report (the same shape `wf_7e5d77a2-5c0` produced) is exactly the kind of artifact
  `mission-control:issue` / `saga:handoff` already knows how to turn into a prepared draft,
  but no command wires a mining synthesis report to that handoff path today — each pattern
  becomes a backlog issue only if a human manually copies it over, which is how this very
  issue-map had to be produced by hand.
- **The lifecycle already has a halt point this harness must respect, not reinvent.**
  `docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md:13` states "writes happen
  only after Gate E (issue-plan) and Gate F (mutation plan) approval." Any harness that
  turns mined findings into backlog material must stop at Gate E and produce a draft for
  human approval — it must not open GitHub issues or write board items on its own.

## Definition of Done

Two writeback exits off one shared mining-payload shape, both gated, both read-only on
GitHub/board state:

1. **Gated LEARNINGS writeback.** A new script (proposed
   `plugins/saga/scripts/mining_harvest.py`) that accepts a findings payload (the same shape
   `wf_7e5d77a2-5c0`-style synthesis produces: pattern text, repo-spread count, evidence
   pointers) and, for any pattern whose repo-spread meets a configurable threshold, emits a
   candidate `LEARNINGS.md` entry draft in the exact format defined at
   `docs/engineering-journal/LEARNINGS.md:1-30` (Context / **Evidence.** / **Mechanism.** /
   **Generalizable rule.** / `{#slug}` anchor) — Evidence-stamped with the finding's own
   source pointers, never fabricated. Drafts are written to disk for human review; nothing
   is auto-appended to `LEARNINGS.md` without an explicit apply step. Merged PR must
   demonstrate that feeding the 10-pattern / 175-finding payload shape produces valid draft
   entries that `plugins/saga/scripts/promote_scan.py`'s legacy `**Generalizable rule.**`
   parser (`:118`-`:230` area) successfully detects once a human applies them — i.e. the
   harvest output is not just LEARNINGS-shaped prose, it is real input to the existing
   downstream scanner.
2. **Durable `/mine-to-backlog` harness.** A new saga command/skill (proposed
   `plugins/saga/commands/mine-to-backlog.md` + `plugins/saga/skills/mine-to-backlog/`)
   that consumes a synthesis report (the same report shape section 7 of the grounding brief
   describes) and emits `mission-control:issue`-ready prepared drafts (matching this
   directory's existing `pf-*.md`/`.json` sidecar convention), halting at Gate E. It must
   make zero GitHub API writes and zero board mutations — it produces draft files only.
   Merged PR must demonstrate that running the harness against this session's own synthesis
   report (or an equivalent fixture) regenerates the candidate drafts, and that a full run
   makes zero outbound GitHub writes.

### Acceptance criteria
- [ ] **10-pattern payload produces valid LEARNINGS drafts.** Given a findings payload
  shaped like the `wf_7e5d77a2-5c0` output (10 recurring patterns + 8 singletons, 175
  findings total), `mining_harvest` emits one candidate `LEARNINGS.md` entry per pattern
  whose repo-spread is at or above the configured threshold, each with a non-empty
  `**Evidence.**` line sourced from the finding's own pointers (never invented). Check:
  `uv run pytest tests/test_mining_harvest.py -k ten_pattern_payload` → passes.
- [ ] **Emitted drafts are detected by the existing promotion scanner.** After a human
  applies one emitted draft's `**Generalizable rule.**` line into a fixture
  `LEARNINGS.md`, `promote_scan.py scan` (or its `Candidate`/`ScanResult` parsing path)
  recognizes it as a legacy-format candidate. Check:
  `uv run python plugins/saga/scripts/promote_scan.py scan --workspace-root tests/fixtures/mining_harvest_applied --json | uv run python -c "import json,sys; d=json.load(sys.stdin); assert d['candidates'] or d['marked']"` → passes.
- [ ] **Below-threshold findings are not drafted.** A finding whose repo-spread is below the
  configured threshold produces no `LEARNINGS.md` draft (only recorded in a non-actionable
  summary). Check: `uv run pytest tests/test_mining_harvest.py -k below_threshold_no_draft`
  → passes.
- [ ] **No autonomous write to the real `LEARNINGS.md`.** Running `mining_harvest` against
  the fixture payload never modifies `docs/engineering-journal/LEARNINGS.md` in place; it
  only writes candidate files under a drafts directory. Check:
  `uv run pytest tests/test_mining_harvest.py -k no_inplace_learnings_write` → passes.
- [ ] **`/mine-to-backlog` regenerates this session's candidate drafts from its synthesis
  report.** Feeding the harness this session's synthesis-report fixture (or an equivalent
  captured fixture standing in for `wf_7e5d77a2-5c0`) reproduces prepared-draft `.md`/`.json`
  pairs matching this directory's existing `pf-*` schema. Check:
  `uv run pytest tests/test_mine_to_backlog.py -k regenerates_session_drafts` → passes.
- [ ] **Zero autonomous GitHub writes.** A full `/mine-to-backlog` run against a fixture
  synthesis report makes no `gh` CLI calls and no GitHub API requests — verified by mocking
  or intercepting the relevant client and asserting zero calls. Check:
  `uv run pytest tests/test_mine_to_backlog.py -k zero_github_writes` → passes.
- [ ] **Halts at Gate E.** The harness's terminal state after emitting drafts is
  "prepared, awaiting approval" — it does not call any board-add, issue-create, or milestone
  helper. Check: `uv run pytest tests/test_mine_to_backlog.py -k halts_at_gate_e` → passes.
- [ ] **Full suite, format, lint, types, security stay green.** Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`
  → all pass.

### Out-of-scope / non-goals
In scope: one gated LEARNINGS-writeback script consuming a mining-findings payload, and one
gated `/mine-to-backlog` harness consuming a synthesis report and emitting mission-control
prepared drafts — both halting before any GitHub/board write.

Out of scope (do not do in this issue):

- **Building or scheduling the mining pass itself.** This issue consumes a findings/synthesis
  payload as input; it does not build the session-skeleton distillation or synthesis
  workflow that produces `wf_7e5d77a2-5c0`-shaped output. That workflow already exists
  outside this repo's committed surface; this issue only wires its output to two writeback
  exits.
- **Auto-applying LEARNINGS drafts.** Applying a candidate entry into the real
  `docs/engineering-journal/LEARNINGS.md` remains a human action (or a separate,
  explicitly-gated apply step) — this issue emits drafts, it does not merge them.
- **Opening GitHub issues or moving board items.** `/mine-to-backlog` halts at Gate E by
  design; wiring the approved draft onward into an actual `gh issue create` /
  `mission-control:board` add is a separate, already-covered lifecycle step
  (`saga:handoff` / `mission-control:issues`), not new work for this issue.
- **Changing `/promote`'s contract, marker format, or ledger.** This issue's LEARNINGS
  drafts must be consumable by the existing `**Generalizable rule.**` / `**Transcendent.**`
  contract (`plugins/saga/skills/promote/references/promotion-contract.md`) unchanged; it
  does not modify that frozen contract.
- **Building a codex/external-engine session-skeleton parser.** The 219-dark-codex-sessions
  gap named in the grounding brief (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:140`)
  is a separate, related idea (chaperone-emitted neutral session skeletons at dispatch
  time) — this issue takes a findings/synthesis payload as given input regardless of which
  engine produced the underlying sessions, and does not build that producer-side capability.

## Grounding References

- **Absorbed idea `T10-F4-4`** (primary) — "Mining-harvest writeback — stop letting 175
  mined findings evaporate into a workflow journal" (theme T10, frame F4, axis
  `feedback-pipeline`). `dod_sketch`: "Merged PR: mining_harvest writeback emitting gated
  Evidence-stamped LEARNINGS.md draft entries from a findings payload; verified by feeding
  the 10-pattern payload and producing valid drafts that promote_scan then detects."
- **Absorbed idea `T10-F6-8`** (facet) — "Durable /mine-to-backlog harness so
  pattern-to-issue stops being a one-off" (theme T10, frame F6, axis `feedback-pipeline`).
  `dod_sketch`: "Merged PR: plugins/saga/skills/mine-to-backlog command consuming a
  synthesis report and emitting mission-control:issue-ready drafts halting at Gate E;
  verified by regenerating this session's candidate drafts from its synthesis report with
  no GitHub writes."
- **Consolidation rationale (issue-map):** "Both stop mined findings from evaporating: gated
  writeback drafts LEARNINGS entries; the harness turns a synthesis report into
  Gate-E-halting issue drafts. One pipeline, two exits." — the two absorbed ideas share one
  findings-payload shape and one gating discipline; this issue keeps them as a single
  pipeline with two writeback destinations rather than splitting into two issues.
- **Session-mining synthesis grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:120-121`: workflow `wf_7e5d77a2-5c0`,
  70/70 skeletons distilled, 27 sessions, 175 findings → 10 recurring patterns + 8
  singletons; 219 codex sessions in-window with no mining substrate.
- **Promote-loop-never-fired grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:76`: "Promote ledger: 0 learnings
  ever promoted; no genuine ≥3-repo transcendent cluster... cross-repo learning loop exists
  but never fired."
- **Theme 10 grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:140`: "Cross-repo learning-mining &
  provenance discipline (promote loop never fired; 219 codex sessions dark; stale-claim
  pattern; evidence integrity)."
- **Gate E binding decision** —
  `docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md:13`: "writes happen only
  after Gate E (issue-plan) and Gate F (mutation plan) approval."
- **Existing promotion backbone this issue must interoperate with (not modify):**
  `plugins/saga/scripts/promote_scan.py` — `Candidate`/`ScanResult` (`:118`, `:230`),
  `source_key()` (`:344`), `Promotion` ledger record (`:352`), CLI `scan`/`key` subcommands
  (`:543`-`:611`); `plugins/saga/skills/promote/references/promotion-contract.md` (frozen
  §1-§5 contract for markers, source keys, legacy-rule parsing).
- **LEARNINGS entry-shape contract this issue's drafts must match:**
  `docs/engineering-journal/LEARNINGS.md:1-30` (Context / Evidence / Mechanism / Fix /
  Validation / Generalizable rule / `{#slug}` anchor template).
- **Plugin-portfolio consolidation-burden decision** —
  `{#plugin-portfolio-groom-17-to-7}`: new-capability additions to the saga plugin carry a
  consolidation burden of proof; this issue lands as new scripts/commands inside the
  existing `saga` plugin rather than a new plugin, satisfying that constraint.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** both halves are import-and-transform work over already-specified
  target shapes — a findings payload to a documented LEARNINGS entry template, and a
  synthesis report to the existing `pf-*.md`/`.json` prepared-draft schema this very
  directory demonstrates dozens of times over. No architectural judgment call is required
  (the gating discipline, entry format, and Gate-E halt point are all already fixed by
  upstream decisions cited above), so sonnet at medium effort is sufficient; no
  external-engine involvement is needed since the work is a straight consume-transform-emit
  task against existing, well-understood contracts.

## Release-Surface Checklist

This issue adds new command/script surface to the `saga` plugin (no change to any existing
command's behavior). Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new `mining_harvest` script
  and `mine-to-backlog` command/skill surface).
- [ ] `.claude-plugin/marketplace.json` — reflect version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new gated LEARNINGS-writeback
  script and the new `/mine-to-backlog` harness.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. marketplace/plugin.json
  parity test) re-run green after the bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording that mining writeback is
  gated-draft-only (never auto-applies to `LEARNINGS.md`, never auto-opens GitHub issues),
  matching this repo's existing propose-diff-and-wait pattern for `/promote`.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/mining_harvest.py` — new gated LEARNINGS-draft writeback script
  (proposed path); consumes a findings payload, emits candidate entries matching
  `docs/engineering-journal/LEARNINGS.md:1-30`'s template.
- `plugins/saga/commands/mine-to-backlog.md` — new command entry point (proposed path).
- `plugins/saga/skills/mine-to-backlog/SKILL.md` — new skill definition (proposed path);
  consumes a synthesis report, emits `mission-control:issue`-ready prepared drafts, halts at
  Gate E.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version bump.
- `plugins/saga/CHANGELOG.md` — new-capability entry.
- `tests/test_mining_harvest.py` — ten-pattern-payload, below-threshold, no-inplace-write,
  promote-scan-detects cases.
- `tests/test_mine_to_backlog.py` — regenerates-session-drafts, zero-github-writes,
  halts-at-gate-e cases.
- `tests/fixtures/mining_harvest_payload/` — fixture findings payload (10-pattern shape).
- `tests/fixtures/mine_to_backlog_synthesis_report/` — fixture synthesis report fixture.

### Tests to add or update

- `mining_harvest`: ten-pattern payload produces valid drafts; below-threshold findings
  produce no draft; emitted draft is detected by `promote_scan.py` once applied; no in-place
  write to the real `LEARNINGS.md`.
- `mine-to-backlog`: regenerates this session's candidate drafts from a synthesis-report
  fixture; makes zero GitHub API/`gh` calls; terminal state is "awaiting approval" (Gate E),
  never board-add or issue-create.
- Release-surface drift-guard test (plugin.json/marketplace.json version parity) re-run
  green.

### Verification

```bash
# Mining-harvest writeback unit tests
uv run pytest tests/test_mining_harvest.py -v

# Mine-to-backlog harness unit tests
uv run pytest tests/test_mine_to_backlog.py -v

# Promote-scan detects an applied draft (fixture round-trip)
uv run python plugins/saga/scripts/promote_scan.py scan \
  --workspace-root tests/fixtures/mining_harvest_applied --json

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports \
  && uv run bandit -r plugins/
```

Expected: all green; promote-scan output contains at least one detected candidate/marked
entry from the applied draft; no GitHub write calls observed during
`test_mine_to_backlog.py`.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json (ids `T10-F4-4`,
  `T10-F6-8`)
- Source type: issue-map
- Source title: Mining-harvest writeback and a durable /mine-to-backlog harness

### Context library links

_none_

### Intent

This repo already runs a session-mining pass and a promotion pass, but the pipe between "we found something" and "the backlog/journal actually changed" does not exist yet — both halves currently dead-end in a one-off report that nobody rereads.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/444
- Number: 444
- Created at: 2026-07-04T08:15:58.561710+00:00

