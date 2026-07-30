---
title: enhancement(fleet-core): revisit tier ladder + max effort rung against Claude Opus 5
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# enhancement(fleet-core): revisit tier ladder + max effort rung against Claude Opus 5

# Revisit the fleet tier ladder against Claude Opus 5

### Objective

Re-establish that the fleet's model tier ladder still reflects reality now that Claude Opus 5 has
replaced Opus 4.8, and close the `max` effort-rung gap between the harness and the palette — or
record a reasoned decision to decline each.

### Intent

Claude Opus 5 replaced Opus 4.8 as the model this fleet runs on. The plugin code needed **zero**
changes, verified live on 2026-07-24: there are no versioned model identifiers anywhere under
`plugins/` (0 hits for `claude-opus-4-*` / `opus 4.8` across `.py`/`.md`/`.json`), because the whole
vocabulary is tier *aliases* (`fable`/`opus`/`sonnet`/`haiku`) that the harness resolves at
dispatch. `scripts/lint_agent_tiers.py` + `tests/test_agent_tier_lint.py` already enforce that every
agent frontmatter `model:` is a palette member.

What the release moves is a **decision premise** and a **vocabulary gap**. Neither is urgent and
neither blocks current work — but both need facts that were not available when this was filed, so
they belong in an issue rather than in an ad-hoc session edit.

**1. `{#manifest-fable-xhigh-tiering}` premise has gone stale.**
`docs/engineering-journal/DECISIONS.md:3193` tiers the schema and gate-semantics units on Fable 5
`xhigh`, justified verbatim as *"the highest generally-available capability tier, above Opus 4.8"*,
at a cost premium of *"$10/$50 per MTok vs Opus 4.8's $5/$25"*. Its stated **Revisit when** is
*"Fable-tier costs or availability change materially, or a cheaper tier proves adequate for
schema/gate-semantics work on a future campaign."* The comparator in that rationale no longer
exists, so the revisit condition is arguably tripped by substitution alone. Needed: Opus 5's actual
pricing and its capability position relative to Fable 5 — neither should be guessed.

**2. `models.json` rank ordering may no longer reflect reality. This is the part with teeth.**
`plugins/fleet-core/scripts/fleet_commons/models.json` ranks `fable: 0` (strongest) and `opus: 1`.
That ordering is load-bearing: consumers merge tiers upgrade-only via `min(MODELS.index)`
(`tier_palette.py:13-18`, `{#tier-vocab-ordering}`), so every escalation, clamp, and same-tier
verifier decision reads it. The existing lint enforces *membership*, not *ordering fidelity*. If
Opus 5 changed the fable/opus relationship, the ladder is silently wrong in a direction no current
test can catch — a unit asking to escalate would resolve to the weaker model while reporting
success. `cost_weights.json` is explicitly ordinal rather than dollar-denominated, so it needs
retuning only if the relative shape changed, not because prices moved.

**3. The `max` effort rung exists in the harness but not in the palette.**
The Workflow tool's `effort` parameter accepts `low | medium | high | xhigh | max`, but
`models.json` `efforts` tops out at `xhigh` (rungs 0-3), so a saga-emitted execution spec cannot
express `max` — `execution_spec.py` validates against the closed `EFFORTS` tuple and rejects it.
Adding a rung 4 is additive-only under fleet-core 0.x (KTD5), but `EFFORTS` ordering is load-bearing
for every upgrade-only merge, so it deserves its own change with drift-guard coverage rather than a
drive-by edit. Note: it is **not** established that Opus 5 introduced `max` — it may predate this
release. Confirm before writing that into history.

### Out-of-scope / non-goals

- **Re-tiering individual agents.** The cross-tier case (moving ~33 frontmatter `model:` values
  between tiers) is real but separate. The 2026-07-03 ideation pool designed a fix — agents declare
  a semantic role (`judgment`/`mechanical`/`survey`) resolved through one mapping file at dispatch —
  which was never built and is its own enhancement.
- **Any change to `fleet_commons_shim.py`**, which is byte-frozen and vendored seven times with a
  drift guard.
- **Retuning `cost_weights.json` for absolute prices.** The grid is ordinal by design; only a change
  in relative shape justifies touching it.
- Re-running or re-litigating the #626 settlement work, which is unaffected by the model change.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/models.json` — `rank` ordering confirm/correct; possible
  `max` rung addition plus per-model `effort_ceiling` updates.
- `plugins/fleet-core/references/tier-palette.md` — vocabulary documentation if the rung lands.
- `docs/engineering-journal/DECISIONS.md` — reaffirm or supersede
  `{#manifest-fable-xhigh-tiering}`; new entry for whatever this issue decides.
- Release surfaces **only if** `plugins/fleet-core/` changes: `plugins/fleet-core/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/fleet-core/CHANGELOG.md`, and the `fleet_core_version`
  drift pins in `tests/test_saga_plugin.py`, `tests/test_liveness_events.py`,
  `tests/test_team_execution_liveness.py`.

### Tests to add or update

- `tests/test_cost_weights.py` — monotonicity guard must still hold across any new rung/rank.
- `tests/test_agent_tier_lint.py` — extend if the vocabulary grows.
- New: a guard asserting `EFFORTS` covers the effort values the harness actually accepts, so a
  future harness rung cannot silently become unreachable again (this is the gap that let `max` drift
  unnoticed).
- `scripts/check_release_surface_parity.py` clean if any plugin version moves.

### Context library links

- `docs/engineering-journal/DECISIONS.md` — `{#manifest-fable-xhigh-tiering}` (:3193),
  `{#tier-vocab-ordering}`, `{#fleet-commons-mechanism-463}`, `{#run-scoped-spend-budgets-366}`.
- `plugins/fleet-core/references/tier-palette.md`.
- `docs/plans/plugin-fleet-ideation-2026-07-03/` — the semantic-role design that covers the
  out-of-scope cross-tier case.

### Acceptance criteria

- [ ] Opus 5 pricing and capability position relative to Fable 5 established from a current primary
      source, recorded with the date observed.
- [ ] `{#manifest-fable-xhigh-tiering}` either reaffirmed against the refreshed comparison or
      superseded by a new DECISIONS entry, such that the stale "above Opus 4.8" and "$5/$25" text no
      longer reads as current fact.
- [ ] `models.json` `rank` ordering explicitly confirmed correct, or corrected, against Opus 5.
- [ ] `max` effort rung either adopted (registry + `EFFORTS` + `effort_ceiling` + drift guard) or
      documented as deliberately declined with the reason.
- [ ] If any `plugins/fleet-core/` file changes, all release surfaces move in the same PR and
      `check_release_surface_parity` is clean.

### Verification

```bash
# Repo gates (CI runs check AND format --check; match CI's mypy scope)
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

# The real regression net for any registry edit: tier_palette validates rank
# contiguity, rung contiguity, and effort_ceiling membership at IMPORT time,
# so a malformed models.json fails loudly here rather than at dispatch.
uv run python -c "
import sys; sys.path.insert(0, 'plugins/fleet-core/scripts')
from fleet_commons import tier_palette as t
print('MODELS (strongest-first):', t.MODELS)
print('EFFORTS (weakest-first) :', t.EFFORTS)
"

# Release surfaces, only if plugins/fleet-core/ changed
uv run python scripts/check_release_surface_parity.py
```

- `tier_palette.py` imports without raising `TierPaletteError`; `MODELS` and `EFFORTS` print in the
  intended order (ordering is load-bearing, and no test asserts it matches external reality).
- If a rung lands: an emitted execution spec declaring the new effort validates and dispatches,
  proving the vocabulary is reachable end-to-end rather than merely present in the registry.

### Evidence at filing

Verified live at `main` `f26f4d1c` on 2026-07-24:

- 0 versioned model IDs under `plugins/`; every hit repo-wide is a dated `docs/` artifact plus one
  opaque test fixture string (`tests/test_manifest_reader.py:312`) that is round-tripped as data.
- The harness still accepts all four aliases — the Agent tool `model` enum is
  `sonnet|opus|haiku|fable`.
- `cc-workflows-ultracode` confirmed working on Opus 5: a 2-agent smoke returned schema-valid
  structured output from both agents in 4.4s, and the raw agent transcripts (not self-report) carry
  `"model":"claude-opus-5"` and `"model":"claude-haiku-4-5-20251001"`.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: session investigation on 2026-07-24 during the #626 PR-merge tail, prompted by the Claude Opus 5 release
- Source type: live-verification at `main` `f26f4d1c`
- Source title: Revisit the fleet tier ladder against Claude Opus 5

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/654
- Number: 654
- Created at: 2026-07-24T19:19:32.207466+00:00

