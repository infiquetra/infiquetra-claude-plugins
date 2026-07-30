---
title: enhancement(fleet-core): U7 delete the lease broker and orphan evidence, add the re-add guard
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: high
handoff_maturity: plan-ready
approval_state: needs_operator_approval
---

# enhancement(fleet-core): U7 delete the lease broker and orphan evidence, add the re-add guard

### Objective
Delete the fleet lease broker and its orphan-evidence companion — 10,203 lines across four files —
add a guard test that prevents the broker being reintroduced, and move all three plugins' release
surfaces in one pull request.

Unit **U7** of seven under parent issue #677 (retire the fleet lease broker). This is the payload unit
and the last to land. Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board
objective: `defects-claude-plugins`.

### Intent
**The deletions** — 10,203 lines out:

| File | Lines |
|---|---|
| `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` | 4,731 |
| `plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py` | 1,578 |
| `tests/test_fleet_lease_broker.py` | 2,709 |
| `tests/test_orphan_fencing.py` | 1,185 |

**The re-add guard is this unit's real product**, and it must scan **resolved module paths, not only
the repository tree.** Defect #642 was `fleet_commons_shim` rung 3 trusting a stale
`installed_plugins.json` and resurrecting an old broker out of a plugin cache. A guard that only greps
`plugins/` would not have caught that, which is the whole reason the guard exists.

**The release surfaces**, all moving together per the repo rule:

| Plugin | Current | Target | Reasoning |
|---|---|---|---|
| `fleet-core` | 0.23.0 | **0.24.0** | Pre-1.0; deletes its largest module. Minor bump is this repo's convention for pre-1.0 capability removal — the same call the agy teardown made at 0.5.1 → 0.6.0. |
| `saga` | 0.122.0 | **0.123.0** | Pre-1.0; deletes a hook and a wrapper. Same convention. |
| `team-execution` | 2.23.0 | **3.0.0** | Post-1.0, and it loses a capability its README advertises at `:20-29` (lease admission, preflight, renewal, release, dead-owner sweep) plus, likely, the whole of `lease_protocol.py`. Under semantic versioning that is a breaking change, not a feature removal behind a flag. |

The `team-execution` major bump is an **overridable decision made at review time, not a measurement.**
If it is unwanted, the only alternative is keeping `lease_protocol.py` as a deprecated no-op shim
through one more minor release — which contradicts the plan's own R1 and R2 and is a scope reversal,
not a version tweak. Decide the version, not the shim.

Edit `fleet-core`'s `plugin.json` `description` to drop the words *"lease and"* — the current text at
`plugins/fleet-core/.claude-plugin/plugin.json:4` advertises *"shared primitives, lease and liveness
decisions…"*, mirrored into `.claude-plugin/marketplace.json:204`. Then **generate**
`marketplace.json` with `scripts/sync_marketplace.py` from the source-of-truth `plugin.json` files.
Never hand-edit it.

**Depends on:** U5 and U6.

### Out-of-scope / non-goals
- **No file in `infiquetra-codex-plugins` is touched and no codex card is filed.** That repository holds
  a deliberate port pinned to *frozen* claude-repo revisions, so deleting from `main` here does not
  break it. Retirement there is declared by adding to the `RETIRED_CURRENT_ARTIFACTS` set in
  `test_lease_safe_substrate_port_contract.py` — operator-owned, out of scope for this card.
- Do not hand-edit `.claude-plugin/marketplace.json`. It is generated.
- Do not start before U5 and U6 have merged.
- Do not add a deprecated no-op `lease_protocol.py` shim as a way to avoid the `team-execution` major
  bump. See above — that is a scope reversal.

### Files expected to change
Deleted:

- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (4,731 lines)
- `plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py` (1,578 lines)
- `tests/test_fleet_lease_broker.py` (2,709 lines)
- `tests/test_orphan_fencing.py` (1,185 lines)

Added:

- `tests/test_no_lease_broker_readd.py` — the re-add guard

Edited:

- `tests/test_fleet_doctor.py` — drop its orphan-evidence probe
- `plugins/fleet-core/.claude-plugin/plugin.json` — version **and** description
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`
- `plugins/fleet-core/CHANGELOG.md`, `plugins/saga/CHANGELOG.md`,
  `plugins/team-execution/CHANGELOG.md`
- `.claude-plugin/marketplace.json` — regenerated, never hand-edited
- Any version drift-guard tests

Agent-facing documentation moves in the same pull request as the behavior it describes (plan
requirement R11). This unit carries the fleet-doctor set plus the two documents whose rows are only
fully emptied once every other unit has landed:

- `plugins/saga/skills/fleet-doctor/SKILL.md` — doctor loses its orphan-evidence probe here
- `plugins/saga/references/fleet-doctor-sources.md` — its source list names the deleted module
- `plugins/saga/commands/fleet-doctor.md`
- `plugins/fleet-core/README.md` — describes the deleted module as a library capability
- `plugins/saga/references/concurrency-spawn-sites.md` — an inventory table whose columns *are* "Lease
  pool / Acquire or reserve seam / Bind seam / Renewal seam / Release seam". Every row goes false. It
  is emptied progressively by U1 through U4, so it is rewritten **once, here**, when the last row goes.
- Incidental references in `plugins/saga/README.md`,
  `plugins/saga/references/outcome-spec.md`, `plugins/saga/references/outcome-cross-runtime.md`,
  `plugins/saga/docs/commands.md`, `plugins/saga/skills/outcome/SKILL.md`

Line counts and versions were measured at revision `ddba53a0`. Re-check versions before bumping.

### Tests to add or update
`tests/test_no_lease_broker_readd.py` (new):

- No file under `plugins/` imports `lease_broker` or `orphan_evidence`.
- The guard **fails** when handed a fixture that does. A guard that has never been seen to fail is not
  known to work.
- The guard inspects **shim-resolved** module paths, not just the repository tree — the #642 failure
  mode.

`tests/test_fleet_doctor.py`:

- Doctor runs with no orphan-evidence module.

`tests/test_agy_run_lease.py`:

- Passes **unmodified**.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U7, requirements R8,
  R11, R11a)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md`
- The re-add failure mode this unit guards against: defect #642
- Defects that close when this unit lands: #645, #646, #647, #661
- Blocked on: U5 and U6

### Inputs inventory
- The four files to delete and their exact line counts, measured at `ddba53a0`.
- `plugins/fleet-core/.claude-plugin/plugin.json:4` — the description string containing *"lease and"*,
  mirrored at `.claude-plugin/marketplace.json:204`.
- Current plugin versions: `fleet-core` 0.23.0, `saga` 0.122.0, `team-execution` 2.23.0.
- `plugins/team-execution/README.md:20-29` — the advertised capability that justifies the major bump.
- `scripts/sync_marketplace.py` — the generator for `marketplace.json`.
- `scripts/check_release_surface_parity.py` — the parity gate.
- Defect #642's mechanism: `fleet_commons_shim` rung 3 trusting a stale `installed_plugins.json`.
- The 11 documents listed above.

### Failure modes / pre-mortem
1. **Most likely: the guard is written against the repository tree only** and would not have caught
   #642, the exact defect it exists to prevent. Mitigation: a test that asserts the guard inspects
   shim-resolved paths, and a fixture that makes the guard fail.
2. **A release surface is missed.** Three plugins, three `plugin.json` files, three CHANGELOGs, one
   generated `marketplace.json`, plus drift-guard tests. Mitigation:
   `scripts/check_release_surface_parity.py` runs before the pull request opens, and it is an
   acceptance criterion.
3. **`marketplace.json` is hand-edited** and then diverges from the `plugin.json` files at the next
   regeneration. Mitigation: stated as a non-goal; parity check catches it.
4. **The `team-execution` major bump is reversed quietly by adding a shim**, reintroducing the module
   this whole issue exists to remove. Mitigation: called out as a scope reversal in both the intent
   and the non-goals.
5. Concurrency documentation is left stale because "someone else's unit already touched it". Mitigation:
   `concurrency-spawn-sites.md` has a single named owner — this unit.

### Stop conditions
Stop and escalate rather than pressing on if:

- U5 or U6 has not merged.
- The re-add guard cannot be made to inspect shim-resolved paths, which would leave the #642 class of
  failure unguarded.
- `scripts/check_release_surface_parity.py` fails and the cause is not a straightforward omission.
- The `team-execution` major bump is contested — that is an operator decision, and the shim workaround
  is not an acceptable substitute for making it.
- Deleting `orphan_evidence.py` turns out to have a surviving consumer outside the four files listed.

### Acceptance criteria
- [ ] All four files are deleted and `git diff --stat` shows at least 10,203 lines removed.
- [ ] `grep -rn "lease_broker\|orphan_evidence" plugins/` returns no matches.
- [ ] `uv run pytest tests/test_no_lease_broker_readd.py -q` passes, and the guard is demonstrated to
      **fail** against a fixture that imports the deleted module.
- [ ] The guard inspects shim-resolved module paths, not only the repository tree.
- [ ] `uv run pytest tests/test_fleet_doctor.py -q` passes with no orphan-evidence probe.
- [ ] `uv run pytest tests/test_agy_run_lease.py -q` passes **unmodified**.
- [ ] `python3 scripts/check_release_surface_parity.py` is clean.
- [ ] `.claude-plugin/marketplace.json` was produced by `scripts/sync_marketplace.py`, not hand-edited,
      and `plugins/fleet-core/.claude-plugin/plugin.json` no longer says "lease".
- [ ] Versions are `fleet-core` 0.24.0, `saga` 0.123.0, `team-execution` 3.0.0 — or the
      `team-execution` target is explicitly overridden by the operator in the pull request.
- [ ] `uv run pytest -q` passes.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.
- [ ] Defects #645, #646, #647 and #661 are closed by this pull request.

### Verification
```bash
rtk proxy uv run pytest -q                      # baseline BEFORE touching anything
uv run pytest tests/test_no_lease_broker_readd.py tests/test_fleet_doctor.py -q
uv run pytest tests/test_agy_run_lease.py -q    # must pass UNMODIFIED
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
python3 scripts/sync_marketplace.py
python3 scripts/check_release_surface_parity.py
grep -rn "lease_broker\|orphan_evidence" plugins/
```

### Notes / conventions
The deletion is the easy half. The guard is the half that has to be right — it is the only thing
standing between this retirement and a future session resurrecting the broker out of a plugin cache,
which is precisely what defect #642 was.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U7)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U7

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/684
- Number: 684
- Created at: 2026-07-30T11:38:56.809607+00:00

