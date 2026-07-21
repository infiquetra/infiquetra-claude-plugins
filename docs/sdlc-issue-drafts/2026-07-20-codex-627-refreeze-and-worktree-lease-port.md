---
title: Codex re-freeze of the #627 seam contract + COR3 worktree lease-authority port
repo: infiquetra-codex-plugins
type: capability
team: asgard
project: operations
status: Shaping
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
approval_state: approved
---

# Codex re-freeze of the #627 seam contract + COR3 worktree lease-authority port

### Objective

Restore codex/claude byte-identity on the frozen cross-runtime seam after
`infiquetra-claude-plugins#627` lands, and complete the COR3 `outcome_worktrees`
lease-authority-threading port that #627's grounding survey re-scoped and re-verified against the
merged SHA.

### Intent

`infiquetra-claude-plugins#627` (saga 0.107.0, fleet-core 0.17.0) intentionally breaks byte
identity between Claude's `outcome_compat.py` and codex's frozen twin: the universal fail-closed
ancestor walk (dropping the under-`$HOME` early return; exempting only world-writable-and-sticky
components) and the refuse-mode lease-admission wiring are upstream-first changes per KTD5 — root
causes land in `infiquetra-claude-plugins` first, codex re-freezes after merge, never the reverse.
Until this issue ships, the cross-runtime acceptance harness's `contract_digests` check halts at
`port-digest` by design (documented, no acceptance run scheduled in the window). This issue is the
re-freeze: pull the merged Claude bytes forward with `RUNTIME_LABEL` as the sole permitted
divergence, re-port the `audit_store` ancestor guard, mirror the refuse-mode admission and
`DispatcherError` arm semantics into the codex-native dispatcher and reconciler, update the
port-manifest's frozen-range pins, and rebuild the port inventory. It also carries the COR3 unit
identified alongside #627's PA-2 review: `outcome_worktrees` lease-authority threading
(`prune`/`reap_worktree`/`advance` parameter surfaces; ~46 references at Claude `794b4da6`) —
re-verify that unit's scope and reference count fresh at the SHA this issue actually merges
against, since Claude's tree kept moving after the count was taken.

### Out-of-scope / non-goals

- Any further change to the Claude-side seam — this issue only re-freezes and ports what
  `infiquetra-claude-plugins#627` already merged; if codex-side review surfaces a new defect in
  the shared mechanism, that is a new upstream-first issue against `infiquetra-claude-plugins`,
  never fixed codex-side first (KTD5).
- Redesigning the refuse-mode admission contract, the `DispatcherError` halt-visibility shape, or
  the ancestor-guard exemption predicate — those are settled by #627's KTD1–KTD4; this issue
  ports them.
- Cross-clone settlement coordination (shared ledger, fleet-doctor cross-clone probe) — #627 R7
  documents the per-clone boundary; building coordination across clones stays future work.
- Any acceptance-harness redesign; only re-running the existing harness once the re-freeze lands.

### Files expected to change

- `outcome_compat.py` (codex-native path) — re-freeze byte-faithful to the Claude
  `infiquetra-claude-plugins#627` merge SHA, `RUNTIME_LABEL` the sole divergence.
- The codex `audit_store` ancestor-guard twin (fleet-core codex port) — re-port the universal
  fail-closed walk.
- The codex-native outcome dispatcher and reconciler — mirror refuse-mode admission
  (`on_conflict="refuse"` equivalent) and the `DispatcherError`/halt-visibility arm, preserving
  codex's own `outcome.dispatch.v2` intent/acknowledgement contract.
- `outcome_worktrees` (codex-native) — thread lease authority through `prune`, `reap_worktree`,
  and `advance` parameter surfaces (COR3; re-verify the ~46-reference count at the actual merge
  SHA, not the `794b4da6` count taken during the #627 review).
- The port manifest that pins Claude's frozen-range SHAs per module.
- The port inventory (rebuild after the manifest update).
- `plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/saga/.claude-plugin/plugin.json` (or
  codex's equivalent release-surface files), `.claude-plugin/marketplace.json`, both
  `CHANGELOG.md`s — release surfaces move in the same PR as #627's own U5 did.
- `docs/engineering-journal/DECISIONS.md` / `LEARNINGS.md` (codex repo) if the re-freeze or the
  COR3 port surfaces a non-obvious mechanism.

### Tests to add or update

- Cross-runtime `contract_digests` / `port-digest` acceptance check returns green against the
  fresh Claude/codex pair (was halting by design since the #627 merge).
- Codex-native equivalents of #627's new test scenarios: refuse-mode admission raises the typed
  conflict and leaves the prior lease's registry bytes untouched; default-mode call sites stay
  unchanged; the reconcile hot path releases the lease, writes a reducer-visible halt, settles the
  attempt, and continues the tick on a lease refusal — pinned under codex's own
  `outcome.dispatch.v2` intent/ack contract, not claude's legacy dispatch shape.
- Universal ancestor-walk twin tests: symlinked/world-writable-non-sticky component anywhere
  refused; sticky world-writable (system temp) accepted; group-writable accepted (#624 boundary,
  unchanged); FAT32/exFAT and NFS/SMB mode-divergent shapes refused (KTD2 pin, codex twin).
- COR3: `outcome_worktrees` lease-authority-threading tests for `prune`, `reap_worktree`, and
  `advance`, at whatever reference count the fresh survey finds at the merge SHA.
- Release-surface parity check (codex repo's equivalent of
  `scripts/check_release_surface_parity.py`) green.

### Context library links

_none_

### Inputs inventory

- `infiquetra-claude-plugins#627` (this issue's prerequisite) — merged PR diff is the byte-source
  for the re-freeze; plan
  `docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md` (KTD1–KTD6, R1–R9) is the
  authoritative spec for what changed and why.
- LEARNINGS `{#resolve-disarms-symlink-guards-624}` — the guard-testing-through-real-entry-points
  rule the ancestor-walk port must preserve.
- DECISIONS `{#lease-refuse-mode-and-universal-guard-627}` — the two operator-adjudicated calls
  (opt-in refuse mode; universal fail-closed walk with sticky-world-writable exemption) this port
  must mirror without redesigning.
- LEARNINGS `{#lease-settlement-window-356}` / DECISIONS on supersede-on-acquire — codex's own
  retry-supersede design, which the refuse-mode port must leave untouched for every consumer
  except the outcome dispatcher.
- codex PA-2 review `2026-07-20-pa2-seam-activation-code-review.md` — the review that
  discovered the four findings #627 discharges and first scoped the COR3 unit.

### Failure modes / pre-mortem

- The re-freeze copies Claude's bytes but misses a codex-native divergence point (something other
  than `RUNTIME_LABEL` differs for a legitimate reason), silently breaking codex's own
  `outcome.dispatch.v2` semantics — mitigate by running codex's full native test suite, not just
  the byte-diff, before declaring the freeze complete.
- The refuse-mode admission port is wired into codex's dispatcher without preserving codex's
  intent/acknowledgement contract, reintroducing the exact "uncaught refusal wedges/hides" defect
  #627 fixed on the Claude side, in codex-native form.
- The COR3 reference count (~46 at Claude `794b4da6`) is stale by the time this issue's PR opens,
  because Claude's tree kept moving; a threading port sized to the old count silently misses new
  call sites — mitigate by re-running the survey fresh at whatever SHA this issue actually merges
  against, not trusting the count carried over from the #627 review.
- The acceptance harness stays red past this issue's merge because the manifest's frozen-range
  update or the inventory rebuild is missed — mitigate by making the harness green a stated
  acceptance criterion, not an assumed side effect.

### Stop conditions

- HALT if the re-freeze requires redesigning any of #627's KTD1–KTD6 decisions rather than porting
  them — that is new upstream-first scope, filed against `infiquetra-claude-plugins`, not fixed
  here.
- HALT if codex's native `outcome.dispatch.v2` intent/acknowledgement contract cannot be preserved
  while mirroring the refuse-mode admission and halt-visibility arms.
- HALT if the COR3 reference-count re-survey finds a materially different scope than ~46
  references — re-scope explicitly rather than porting to a stale count.
- HALT if `contract_digests`/`port-digest` still halts after the manifest and inventory updates —
  find the residual byte divergence before closing.

### Notes / conventions

Filed via mission-control at #627's ship ceremony per that plan's U5/R8, never authored by `/plan`
directly. Upstream-first discipline (KTD5) applies to the whole issue: any defect discovered while
porting is a new `infiquetra-claude-plugins` issue, not a codex-side original fix.

### Acceptance criteria

- [ ] `outcome_compat.py` (codex) is byte-identical to the Claude `infiquetra-claude-plugins#627`
      merge SHA except `RUNTIME_LABEL`. Check: diff against the pinned merge SHA in CI.
- [ ] The codex `audit_store` ancestor guard walks every existing path component fail-closed,
      exempting only world-writable-and-sticky, matching the Claude twin's behavior test-for-test.
- [ ] Codex's outcome dispatcher/reconciler mirrors refuse-mode admission and the
      `DispatcherError`/halt-visibility arm while preserving `outcome.dispatch.v2` intent/ack
      semantics. Check: codex-native equivalents of #627's dispatcher and reconcile-hot-path tests.
- [ ] COR3 `outcome_worktrees` lease-authority threading is complete and re-verified at the actual
      merge SHA's reference count. Check: full-repo grep for the threaded parameter surfaces plus
      passing tests on `prune`/`reap_worktree`/`advance`.
- [ ] The port manifest's frozen-range pins and the port inventory are updated in the same PR.
- [ ] Cross-runtime acceptance `contract_digests`/`port-digest` check is green (no longer halting).
- [ ] Release surfaces (plugin.json versions, marketplace entry, both CHANGELOGs) move in the same
      PR and pass the codex repo's release-surface parity gate.
- [ ] Full codex-repo quality gates pass (pytest, lint, type check, security scan — codex repo's
      equivalents of this repo's battery).

### Verification

```bash
# codex repo equivalents of:
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
# cross-runtime acceptance harness contract_digests / port-digest check
```

### Handoff maturity

requirements-ready

### Suggested next action

Use `saga:plan` on this issue (in `infiquetra-codex-plugins`) once
`infiquetra-claude-plugins#627` is merged, to size the re-freeze diff against the actual merge SHA
and re-survey the COR3 reference count before implementation.
