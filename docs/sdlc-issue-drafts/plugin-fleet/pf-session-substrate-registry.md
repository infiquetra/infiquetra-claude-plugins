---
title: "capability: session-substrate registry — light up 219 dark codex sessions, PR review threads, and chaperone-emitted skeletons"
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

# capability: session-substrate registry — light up 219 dark codex sessions, PR review threads, and chaperone-emitted skeletons

### Objective
Make the backlog and lifecycle self-improving

### Problem / motivation

`/retro` and its mining tooling (`discover_sessions.py`, `extract_session_skeleton.py`,
`promote_scan.py`) only know how to read one substrate — local Claude Code session
JSONL. Three other substrates that already carry mineable improvement signal are
completely dark to that pipeline today:

- **219 codex sessions sit unmined.** The grounding brief records "219 codex sessions
  in-window with no mining substrate — grounded gap" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:115`).
  `discover_sessions.py` globs only `~/.claude/projects/*<repo>*/*.jsonl` and hardcodes
  `MAX_CANDIDATES = 5` on a recency-only rank (`plugins/saga/scripts/discover_sessions.py:35`,
  `:100`) — there is no `--substrate` switch, no `~/.codex/*.jsonl` glob, and
  `extract_session_skeleton.py` has no codex-shaped handler (its dispatch is
  Claude-only: `handle_claude` at `plugins/saga/scripts/extract_session_skeleton.py:156`,
  with no `handle_codex` sibling). Every codex session run in this window — and every
  future non-Claude engine session — is invisible to `/retro`.
- **Merged PR review threads are an already-durable, already-cross-repo substrate that
  nothing mines.** The grounding brief cites the team-execution consensus review
  catching defects the green suite missed in two independent repos, operator-praised,
  as direct-signal grounding (survivor `T10-F3-2` basis: "grounding brief §3.2
  'team-execution consensus review catching defects green suites missed (2 independent
  repos, operator-praised)'; `discover_sessions.py:35` `MAX_CANDIDATES=5` recency-only
  cap shows the transcript substrate is lossy"). `gh`-resolved PR review comments already
  live durably on GitHub, are already cross-repo, and are never read by any mining path.
- **Delegated (chaperone/agy/codex bridge) work produces no minable record at the write
  side.** There is no neutral, engine-agnostic session-skeleton emitted at delegation
  time — `plugins/agy/scripts/agy_delegate.py` and the codex chaperone dispatch path
  (`{#external-engine-chaperone-dispatch}`, decision #318, cited in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41`) hand off work but leave
  no artifact any read-side parser could later mine — the darkness starts at the write
  side, not just the read side.
- **A prior operator ask already named the read-side gap directly.** Seed `S-35` (this
  repo's `QUEUED.md`) asks for "comprehensive scan of all claude/codex sessions in local
  repos for improvement patterns," grounded the same way (basis: "operator statement
  'comprehensive scan of all claude/codex sessions in local repos for improvement
  patterns'; brief §5 '219 codex sessions in-window with no mining substrate'").
- **A dual-engine reconciled read is prior art, not speculation.** The brief records
  "Claude+Codex independent syntheses converging 15/17, hand-reconciled" as a singleton
  from this repo's own session-mining synthesis (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:151`
  area, theme 5 prior art) — a second-miner reconciliation step is not a novel ask, it
  reproduces a pattern that already worked once by hand.

None of the four gaps above are independent: they all trace back to one seam —
`/retro`'s mining core assumes exactly one substrate shape (Claude JSONL, read-side
only). Fixing the seam once (a substrate registry with adapters) closes all four at
once instead of bolting on four one-off scripts.

## Definition of Done

A `session_substrates.py` registry module (base substrate interface plus a `claude`
adapter and a `codex` adapter) is wired into `/retro`'s mining path so that mining a
repo's sessions walks every registered substrate, not just Claude JSONL. Alongside it:

1. **Registry + codex adapter.** `plugins/saga/scripts/session_substrates.py` (proposed
   path) defines a `Substrate` base interface (discover → extract → normalized
   skeleton) with a `claude` adapter (wrapping today's `discover_sessions.py` /
   `extract_session_skeleton.py` behavior unchanged) and a new `codex` adapter that
   globs `~/.codex/*.jsonl` (or the codex CLI's actual session-log location, confirmed
   during planning) and emits skeletons in the same envelope shape
   `extract_session_skeleton.py` already produces for Claude sessions. Wired into
   `discover_sessions.py` via a `--substrate {claude,codex,all}` flag (default
   preserves today's Claude-only behavior — no behavior change for existing callers).
2. **Review-thread substrate.** `mine_review_threads.py` (proposed path,
   `plugins/saga/scripts/`) pulls resolved `gh` PR review comments across repos into
   repo-tagged findings JSON, registered as a substrate the same registry recognizes.
3. **Write-side chaperone skeleton emission.** The codex and agy chaperone dispatch
   paths emit a neutral, engine-agnostic session-skeleton at delegation time (same
   envelope shape as substrate adapters produce), accepted by `promote_scan.py` /
   `/retro`'s mining input with no read-side parser required to reconstruct it after
   the fact.
4. **Optional dual-engine reconciliation.** An opt-in second-miner pass dispatches a
   codex advisory pass (chaperone dispatch, never a gating decision per
   `{#external-engines-never-gatekeepers}` #283 and `{#external-engine-chaperone-dispatch}`
   #318) over the same skeletons Claude already mined, and Claude reconciles the two
   into a tagged convergent/divergent diff artifact.

Merged PR demonstrates: the codex adapter emits `N > 0` normalized skeletons over a
real codex session where the prior pipeline emitted `0`; a future third engine adapter
can be added by implementing the `Substrate` interface without touching `/retro`'s
mining core; a delegated (chaperone) task produces a minable skeleton with no read-side
parser invoked; review-thread mining surfaces a known reviewer-caught defect from a
fixture repo; and the optional codex second-miner produces a Claude-reconciled diff
artifact tagging convergent vs. divergent findings over one mining window.

### Acceptance criteria
- [ ] **Codex adapter emits real skeletons where the pipeline previously emitted zero.**
  Running the codex adapter (directly, or via `discover_sessions.py --substrate codex`)
  against a fixture (or real) `~/.codex/*.jsonl` session produces `N > 0` normalized
  skeletons in the same envelope shape `extract_session_skeleton.py` emits for Claude
  sessions, where the pre-change pipeline produced `0` for that same session. Check:
  `uv run pytest tests/test_session_substrates.py -k codex_adapter_nonzero` → passes.
- [ ] **Claude-only behavior is unchanged by default.** `discover_sessions.py` invoked
  without `--substrate` (or with `--substrate claude`) produces byte-identical output
  to the pre-change tool over the same fixture set. Check:
  `uv run pytest tests/test_discover_sessions.py -k substrate_default_unchanged` → passes.
- [ ] **A future engine adapter plugs in without touching `/retro` core.** A
  minimal third fixture adapter (e.g. a fake `future_engine` substrate implementing the
  `Substrate` interface) registers and is discoverable by the registry with zero edits
  to `/retro`'s mining-dispatch code path. Check:
  `uv run pytest tests/test_session_substrates.py -k future_adapter_no_core_change` → passes.
- [ ] **Review-thread mining surfaces a known reviewer-caught defect.** Given a fixture
  (or recorded real) merged PR whose review thread contains a known reviewer-caught
  defect comment, `mine_review_threads.py` surfaces that finding, repo-tagged, in its
  output JSON. Check: `uv run pytest tests/test_mine_review_threads.py -k known_defect_surfaced` → passes.
- [ ] **Delegated task yields a minable skeleton with no read-side parser.** Running a
  chaperone-dispatched delegation (codex or agy bridge) against a fixture task emits a
  neutral session-skeleton file at delegation time; `/retro`'s mining input accepts it
  directly (no new read-side parser is invoked to reconstruct it after the fact). Check:
  `uv run pytest tests/test_chaperone_skeleton_emit.py -k emitted_skeleton_accepted` → passes.
- [ ] **Optional codex second-miner produces a reconciled diff artifact.** With the
  optional dual-engine flag enabled, mining one fixture window through both the
  Claude-native miner and the codex advisory second-miner produces a single
  Claude-reconciled diff artifact tagging each finding as convergent or divergent (codex
  never gates the outcome — advisory only, per `{#external-engines-never-gatekeepers}`
  #283). Check: `uv run pytest tests/test_dual_engine_reconcile.py -k reconciled_diff_artifact` → passes.
- [ ] **Full suite, format, lint, types, security stay green.** Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

### Out-of-scope / non-goals
In scope: one substrate-registry abstraction (`Substrate` base interface), a `claude`
adapter (behavior-preserving wrap of existing tooling), a new `codex` adapter, a
`mine_review_threads.py` PR-thread substrate, write-side chaperone skeleton emission
at delegation time, and an optional gated dual-engine reconciliation pass.

Out of scope (do not do in this issue):

- **Backfilling the 219 already-elapsed dark codex sessions into a retroactive mining
  run.** This issue builds the adapter that makes future and currently-present codex
  sessions minable; running a one-time historical backfill over the specific 219-session
  window is a follow-up operational action, not new code this issue must ship.
- **A future-engine adapter for any engine beyond codex.** The registry is built so a
  future engine adapter can be added without touching `/retro` core (verified by a
  fixture adapter in the acceptance criteria above) — this issue does not implement a
  third real adapter.
- **Making the codex second-miner a gating or blocking decision.** Per
  `{#external-engines-never-gatekeepers}` (#283) and
  `{#external-engine-chaperone-dispatch}` (#318), the optional dual-engine pass is
  advisory-only chaperone dispatch; this issue does not give codex or any external
  engine a git-participant, gate-owning, or second-executor role.
- **Building a new PR-comment resolution/authoring workflow.** `mine_review_threads.py`
  reads already-resolved `gh` review comments; it does not add new review tooling,
  comment authoring, or reviewer-assignment logic.
- **Auto-applying mined findings into `LEARNINGS.md` or opening GitHub issues.** This
  issue produces mineable substrate input for `/retro`'s existing downstream pipeline;
  it does not change what `/retro` or `/promote` do with findings once mined.

## Grounding References

- **Absorbed idea `T10-F4-3` (primary)** — "Session-substrate registry — light up 219
  dark codex sessions and every future engine with one seam" (theme T10, frame F4, axis
  `mining-substrates`). `dod_sketch`: "Merged PR: `session_substrates.py` registry
  (base + claude + codex adapters) wired into retro mining; verified by codex adapter
  emitting N>0 normalized skeletons and a future-engine adapter added without touching
  retro core."
- **Absorbed idea `S-35` (dedup-merged)** — "Comprehensive scan of all claude/codex
  local sessions for improvement patterns" (seed). Basis: operator statement
  "comprehensive scan of all claude/codex sessions in local repos for improvement
  patterns"; brief §5 "219 codex sessions in-window with no mining substrate."
  `dod_sketch`: "Merged mining tool that ingests claude + codex local session logs
  across repos and surfaces ranked recurring improvement patterns. Verify: run over the
  219 dark codex sessions + claude sessions produces a ranked pattern report with
  evidence pointers (reproduce the §5 pattern taxonomy)."
- **Absorbed idea `T10-F6-3` (facet)** — "Codex-session dark-substrate bridge into the
  existing skeleton pipeline" (theme T10, frame F6, axis `mining-substrates`).
  `dod_sketch`: "Merged PR: `discover_sessions.py --substrate` flag +
  `~/.codex/*.jsonl` glob and `extract_session_skeleton.py` codex handler; verified by
  mining a real codex session into the same skeleton envelope as a Claude one (N>0
  where previously 0)."
- **Absorbed idea `H-F1-5` (facet)** — "Chaperone-emitted engine-agnostic session
  skeletons: fix mining darkness at the write side" (theme T10, frame F1, axis
  `write-side-provenance`). `dod_sketch`: "Merged PR: chaperone dispatch paths
  (codex/agy bridge) emit a neutral session-skeleton at delegation time, accepted by
  `promote_scan`/retro; verified by a delegated task producing a minable skeleton with
  no read-side parser."
- **Absorbed idea `T10-F3-2` (facet)** — "Mine merged PR review threads as an
  already-durable, already-cross-repo substrate" (theme T10, frame F3, axis
  `mining-substrates`). Basis: "grounding brief §3.2 'team-execution consensus review
  catching defects green suites missed (2 independent repos, operator-praised)';
  `discover_sessions.py:35` `MAX_CANDIDATES=5` recency-only cap shows the transcript
  substrate is lossy." `dod_sketch`: "Merged PR: `mine_review_threads.py` pulls
  resolved `gh` review comments across repos into repo-tagged findings JSON; verified
  over a repo with a known reviewer-caught defect surfacing that finding."
- **Absorbed idea `T10-F6-4` (facet, moonshot-tagged in ideation, folded into this
  structural issue as an optional gated capability)** — "Dual-engine adversarial
  session mining with Claude-reconciled diff" (theme T10, frame F6, axis
  `mining-substrates`). `dod_sketch`: "Merged PR: retro session-mining optionally
  dispatches a codex second-miner (advisory chaperone) over identical skeletons, Claude
  reconciles; verified by a reconciled-diff artifact over one window tagging convergent
  vs divergent findings."
- **Binding decisions this issue must respect:** `{#external-engines-never-gatekeepers}`
  (#283) — codex/agy remain generator / advisory-reviewer / non-gated worker only,
  never verifier-of-record; `{#external-engine-chaperone-dispatch}` (#318) — external
  engines in teams are chaperone dispatch only, never a second executor kind or git
  participant (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41`).
- **Session-mining synthesis grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:111-115`: workflow
  `wf_7e5d77a2-5c0`, 70/70 skeletons distilled, 27 sessions, 175 findings → 10 recurring
  patterns + 8 singletons; "219 codex sessions in-window with no mining substrate —
  grounded gap, feeds theme 10."
- **Existing lossy-substrate evidence** —
  `plugins/saga/scripts/discover_sessions.py:35` (`MAX_CANDIDATES = 5`, recency-only
  rank) and `:100` (the hard cap applied); `plugins/saga/scripts/extract_session_skeleton.py:156`
  (`handle_claude` — the only engine handler that exists today).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** none (the codex second-miner in acceptance criterion 6 runs through
  the existing chaperone-dispatch seam, not as a direct external-LLM call from this
  issue's own execution)
- **Justification:** this issue touches four coupled surfaces (a new registry
  abstraction, a new adapter, a new mining script, and a write-side emission point in
  two existing chaperone dispatch paths) and must preserve exact byte-for-byte backward
  compatibility on the existing Claude-only path while introducing a genuinely new
  abstraction boundary (the `Substrate` interface) that a future engine must be able to
  implement without touching `/retro` core — that is an architectural-seam judgment
  call, not a mechanical transform of an already-fixed target shape, which is why this
  sits above the "sonnet/medium, inline" bar used for issues that only import against an
  already-specified schema (contrast `pf-mining-harvest-writeback`, sonnet/medium/inline,
  which consumes an already-fixed findings-payload and template shape). team-execution
  backend gives it reviewer consensus and validator gates across the four touched
  surfaces instead of a single-pass inline edit.

### Release-surface checklist

This issue adds new script/adapter surface to the `saga` plugin and touches the codex
and agy chaperone dispatch paths (no change to any existing command's default
behavior — `--substrate` defaults preserve current output). Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new
  `session_substrates.py` registry, `codex` adapter, `mine_review_threads.py`,
  `--substrate` flag on `discover_sessions.py`).
- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump if the agy chaperone
  dispatch path (`plugins/agy/scripts/agy_delegate.py`) changes to emit skeletons.
- [ ] `.claude-plugin/marketplace.json` — reflect both version bumps.
- [ ] `plugins/saga/CHANGELOG.md` and `plugins/agy/CHANGELOG.md` entries describing the
  new substrate registry, codex adapter, review-thread mining, and chaperone skeleton
  emission.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. marketplace/
  plugin.json parity test) re-run green after the bump.
- [ ] `docs/engineering-journal/DECISIONS.md` entry recording the substrate-registry
  pattern (why an adapter interface rather than a per-engine branch inside
  `extract_session_skeleton.py`) so future engine adapters follow the same seam.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/session_substrates.py` — new registry module: `Substrate` base
  interface, `claude` adapter (wraps existing behavior unchanged), `codex` adapter
  (proposed path).
- `plugins/saga/scripts/discover_sessions.py` — add `--substrate {claude,codex,all}`
  flag; default path unchanged (`:35`, `:100` today).
- `plugins/saga/scripts/extract_session_skeleton.py` — add a codex-shaped handler
  alongside `handle_claude` (`:156`).
- `plugins/saga/scripts/mine_review_threads.py` — new PR review-thread mining script
  (proposed path).
- `plugins/saga/scripts/promote_scan.py` — accept chaperone-emitted skeletons as valid
  mining input alongside session-derived ones.
- `plugins/agy/scripts/agy_delegate.py` — emit a neutral session-skeleton at delegation
  time.
- codex chaperone dispatch path (exact file confirmed during planning; no
  `plugins/codex/scripts/` directory exists today) — emit the same skeleton shape at
  delegation time.
- `tests/test_session_substrates.py` — codex-adapter-nonzero, future-adapter-no-core-
  change, default-unchanged cases.
- `tests/test_discover_sessions.py` — substrate-flag default-unchanged regression.
- `tests/test_mine_review_threads.py` — known-defect-surfaced case.
- `tests/test_chaperone_skeleton_emit.py` — emitted-skeleton-accepted case.
- `tests/test_dual_engine_reconcile.py` — reconciled-diff-artifact case.
- `tests/fixtures/codex_sessions/` — fixture codex `.jsonl` session(s).
- `tests/fixtures/review_threads/` — fixture merged-PR review-thread payload with a
  known reviewer-caught defect.

### Tests to add or update

- Registry/adapter: codex adapter emits `N > 0` skeletons over a fixture session where
  the pre-change pipeline emitted `0`; a fixture future-engine adapter registers with
  zero edits to `/retro` mining-dispatch code; default (no `--substrate` flag) behavior
  is byte-identical to pre-change output.
- Review-thread mining: known reviewer-caught defect surfaces, repo-tagged, in output
  JSON.
- Chaperone write-side emission: a delegated fixture task emits a skeleton consumable
  with no read-side parser.
- Dual-engine reconciliation: one fixture window produces a single reconciled diff
  artifact tagging convergent vs. divergent findings; codex participation never gates
  the run's success/failure.
- Release-surface drift-guard test (plugin.json/marketplace.json version parity)
  re-run green.

### Verification

```bash
# Substrate registry + codex adapter + future-adapter seam
uv run pytest tests/test_session_substrates.py -v
# discover_sessions.py default-behavior regression
uv run pytest tests/test_discover_sessions.py -v
# Review-thread mining
uv run pytest tests/test_mine_review_threads.py -v
# Chaperone write-side skeleton emission
uv run pytest tests/test_chaperone_skeleton_emit.py -v
# Optional dual-engine reconciliation
uv run pytest tests/test_dual_engine_reconcile.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports \
  && uv run bandit -r plugins/
```

Expected: all green; codex-adapter test reports `N > 0` skeletons over a session where
the pre-change tool reported `0`; dual-engine test's reconciled artifact contains both
a `convergent` and a `divergent` tag category over the fixture window.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json (ids
  `T10-F4-3`, `T10-F6-3`, `H-F1-5`, `T10-F3-2`, `T10-F6-4`) and
  docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json (id `S-35`)
- Source type: issue-map
- Source title: Session-substrate registry: light up 219 dark codex sessions, PR review
  threads, and chaperone-emitted skeletons

### Context library links

_none_

### Intent

`/retro` and its mining tooling (`discover_sessions.py`, `extract_session_skeleton.py`, `promote_scan.py`) only know how to read one substrate — local Claude Code session JSONL. Three other substrates that already carry mineable improvement signal are completely dark to that pipeline today:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/447
- Number: 447
- Created at: 2026-07-04T08:16:48.530310+00:00

