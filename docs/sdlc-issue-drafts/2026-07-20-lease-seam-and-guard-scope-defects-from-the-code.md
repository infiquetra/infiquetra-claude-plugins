---
title: Lease seam and guard-scope defects from the codex PA-2 review: supersede-on-acquire overclaim, missing DispatcherError arm, resolve-scope guard bypass, reducer-invisible halt records
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# Lease seam and guard-scope defects from the codex PA-2 review: supersede-on-acquire overclaim, missing DispatcherError arm, resolve-scope guard bypass, reducer-invisible halt records

### Objective

Discharge the upstream-first routings from the codex PA-2 (#43) programmatic code review: three
validated findings, one remediation-discovered defect, and one advisory footnote against code
that is shared with or byte-identical to this repo at origin/main `794b4da6`.

## Where this comes from

Programmatic code review of infiquetra-codex-plugins PR for issue #43 (PA-2 of the
cross-runtime-acceptance plan, outcome lease-safe-runtime-continuity). Three validated findings,
one defect discovered during the remediation, and one advisory footnote indict code that is
shared with or byte-identical to this repo at origin/main `794b4da6` (saga 0.105.0 /
fleet-core 0.16.0). Per the upstream-first discipline (acceptance plan KTD7,
precedent: codex-parity review routing), the root causes are filed here; the codex copies stay
byte-faithful until this repo ships the fix and the port re-freezes.

## Finding 1 — lease admission is supersede-on-acquire, not exclusion (validated P1 in the codex review)

`LeaseBroker.acquire_agent` calls `_drop_superseded_resource_lease` (fleet-core
`fleet_commons/lease_broker.py:2274` codex-side; same code this repo ported from) which
unconditionally `registry.leases.pop(prior.lease_id, None)` for any prior lease on the same
resource digest — a live, unexpired conflicting lease is EVICTED, not refused. Two brokers over
one `INFIQUETRA_FLEET_STATE_DIR`: B's acquire always wins; A learns only when its `renew()`
raises `LeaseNotFoundError` after dispatch preparation already ran. Validator reproduced with a
fresh two-broker probe.

Compounding scope gap (validator-discovered): the outcome ledger — the layer assumed to provide
the one-effect guarantee — is scoped per `git rev-parse --git-common-dir` (`Store.for_outcome`).
Two genuinely separate clones share the lease registry (via the fleet state dir) but NOT the
settlement ledger, and the dispatch lease is released immediately after synchronous prepare
(pinned by test). So a sequential second runtime on a separate clone dispatches cleanly with zero
conflict signal. The claim "with lease authority a codex/claude advance cannot dispatch a leaf
another runtime holds" is false as shipped in both runtimes' prose.

Also: `dispatch_identity` falls back through `getattr(req, "dispatch_id", "")` /
`getattr(req, "attempt", 1)` to the literal `"1"` for the concrete `DispatchRequest` (neither
field exists on it), so the resource key design needs adjudication together with the exclusion
semantics — unique per-attempt refs would silently remove even conflict *detection*.

Ask: decide the intended invariant (refuse-on-live-conflict at admission vs documented
supersede + settlement-layer one-effect), implement it in lease_broker/outcome_dispatcher here,
extend the settlement scope story for cross-clone runtimes (or document the boundary), and fix
the comments/CHANGELOG prose. Then codex re-ports.

## Finding 2 — dispatch hot path catches BackendHaltError but not DispatcherError (validated P1 in the codex review; same shape here)

Claude `outcome.py` reconcile loop wraps `dispatch(request)` with arms at ~:1468
(`BackendRateLimitError`) and ~:1496 (`BackendHaltError`) — `DispatcherError` (raised by the
lease authority on admission refusal/renew failure, i.e. exactly the cross-runtime-conflict
signal) is caught by neither. The durable dispatch intent is appended BEFORE dispatch, so the
uncaught escape aborts the whole tick, leaks the per-subplot dispatch lock until TTL, and (in
codex, reproduced end-to-end) wedges the leaf behind the "dispatch intent already exists without
an acknowledgement" halt. This repo's per-attempt `dispatch_settlement` model may soften the
permanence — verify — but the missing arm is real here.

Ask: add an `except DispatcherError` arm modeled on the transient/retriable
`BackendRateLimitError` arm (release the subplot lock, durable transient receipt, continue the
tick — never abort the tick, never strand the intent).

## Finding 3 — ancestor guards disarmed when resolve() rewrites the path out of home (found against bytes byte-identical to #624's PA-1 remediation)

`_refuse_unsafe_handoff_ancestors` (`outcome_compat.py`) and `_refuse_unsafe_ancestors`
(`fleet_commons/audit_store.py`) return immediately when the candidate is not lexically below
`$HOME`. Both production entry points canonicalize with `.resolve()` BEFORE the walk
(`outcome_store.resolve_common_dir` → `common.resolve()`; `Store.for_root` →
`.expanduser().resolve()`). A symlinked `~/.local` (or any home component) onto another volume —
a routine macOS/dotfiles layout — rewrites the path out of home and the ENTIRE walk is skipped,
including the world-writable refusal whose docstring claims it "covers every caller". Runtime
probe: `~/.bp-XXXX/local -> /var/folders/.../wwroot` (0o777, non-sticky) → store accepted through
a world-writable grandparent; identical shape kept lexically under home → correctly refused.
Out-of-home clones (/opt, /Volumes, shared build roots) get zero ancestor coverage by the same
exemption, and the "system temp roots" justification never tests the sticky bit (S_ISVTX) — plain
0o777 is accepted identically.

Ask: make the scope test the security property — walk every existing component regardless of
location, exempting only world-writable AND sticky components (the actual system-temp shape);
drop the "covers every caller" claim. This is a direct follow-up to #624 / LEARNINGS
`{#resolve-disarms-symlink-guards-624}` — the same resolve-vs-guard mechanism, one level up.

Validator caveats the fix must address explicitly (not silently): because both entry points feed
the guard an already-resolved path, a universal walk will not spuriously flag legitimate system
symlinks (resolve() already collapsed them — a symlink surviving post-resolve is a genuine
time-of-check signal), and stock macOS roots (/, /Users, /opt at 0o755; /private/tmp at 1777
sticky) pass cleanly. But two environments need a documented decision + test coverage:
(a) network-mounted homes (NFS/SMB) where lstat mode bits can diverge from real ACL enforcement
in either direction, and (b) FAT32/exFAT external volumes, which macOS typically synthesizes as
world-writable non-sticky at mount time — a strict universal walk would systematically refuse a
plausible /Volumes/External clone. Decide refuse-vs-exempt for each, and pin it with tests.

## Finding 4 — receipt-spread halt records are invisible to the ledger reducer and the report (discovered during the codex remediation, verified in this repo at 794b4da6)

Every dispatch-halt ledger append that spreads a `HaltReceipt` uses the literal shape
`{"phase": "halt", "kind": "dispatch", "key": ..., **receipt}` — and `HaltReceipt.to_dict()`
itself carries `"kind": "halt"`, which wins the duplicate-key merge (later keys override in a
dict literal). The stored record has `kind="halt"`, but every consumer matches
`kind == "dispatch"`:

- This repo at `794b4da6`: `outcome.py:1263` (`spend:` key), `:1332`, `:1501` all spread the
  receipt; `outcome_report.py`'s `_halted_subplots` filters
  `rec.get("kind") == "dispatch" and rec.get("phase") in ("halt", "commit")` — so a
  receipt-spread HALT never reaches the tier-2 "ambiguity" attention item, and a leaf halted by
  a backend HALT is silently absent from the consolidated operator prompt. Only the ephemeral
  in-tick `advance` return surfaces it.
- Codex mirrors the same append shape; its reducer's halt arm
  (`outcome_store.reduce_dispatch_ledger`, `kind == "dispatch" and phase == "halt"`) is dead
  code for those records for the same reason.

Ask: make the explicit `kind` survive the spread (`{**receipt, "kind": "dispatch"}` or strip
`kind` from the receipt before spreading) at every halt append, and pin reducer/report
visibility with a test (halt → derived report shows the ambiguity item). The codex PR for #43
already writes its NEW `DispatcherError` halt arm in the reducer-visible shape with a comment
warning against "fixing" it to match the sibling sites; the sibling sites themselves stay
byte-faithful to this repo pending this fix.

## Advisory footnote — group-writable ancestors (NOT an ask; validator-rejected as a defect)

The refusal mask is `st_mode & 0o002` (other-writable only) in both copies; on macOS the default
primary group for home content is gid 20 (`staff`, shared by every local human account), so an
0o770 ancestor is accepted while being group-renameable. The PA-2 review's Stage-B validator
adjudicated this **valid-but-accepted-tradeoff**: this exact boundary was deliberately designed
and test-pinned in PA-1 (#624) — `test_ensure_private_dir_accepts_group_writable_ancestor_below_home`,
CHANGELOG 0.16.0 "Group-writable ancestors remain permitted by design, pinned by test" — macOS
defaults never produce group-writable ancestors (home 0750, umask 0022), and a bare `& 0o022`
widening would break legitimate setgid team-directory workflows (02770). Recorded here only as a
macOS staff-gid-breadth footnote for whoever next revisits the #624 boundary. No action requested.

## Cross-references

- Codex-side review artifact: docs/code-reviews/ in infiquetra-codex-plugins PR for #43 (link at file time).
- Codex-local surface repairs shipped in that PR (prose de-overclaim, DispatcherError arm in the
  codex reconcile loop, test hardening); byte-frozen compat copy deliberately NOT diverged.
- Related: #523/#524/#527 follow-up cluster from external-engine-offload; #624 (PA-1).

<!-- session: https://claude.ai/code/session_014s77CGxva8ryGNQFCuYT77 -->

### Intent

Fix the root causes in this repo first so the codex port re-freezes from a merged SHA instead of
diverging its byte-faithful copies (acceptance plan KTD7, precedent: the codex #34 review
routings discharged by #624). Findings 1 and 2 are the highest-value: together they mean the
activated lease seam neither excludes a racing runtime at admission nor recovers cleanly when
the conflict signal finally arrives. Finding 1's ask requires an explicit design decision
(refuse-on-live-conflict vs documented supersede + settlement-layer one-effect) before
implementation — plan first, do not jump to code.

### Out-of-scope / non-goals

- No codex-side changes (codex re-ports after this merges; its PA-2 PR already carries the
  codex-local surface repairs — prose de-overclaim, a reducer-visible `DispatcherError` halt arm
  in its reconcile loop, test hardening).
- No change to the group-writable ancestor boundary (advisory footnote only; deliberately
  test-pinned in #624 — reversing it would break setgid team-directory workflows).
- No acceptance-harness work (that is #605).
- No change to `discover`/`handoff`/`attach` semantics.

### Files expected to change

- plugins/fleet-core/scripts/fleet_commons/lease_broker.py
- plugins/saga/scripts/outcome_dispatcher.py
- plugins/saga/scripts/outcome.py
- plugins/saga/scripts/outcome_compat.py
- plugins/fleet-core/scripts/fleet_commons/audit_store.py
- plugins/saga/scripts/outcome_report.py
- plugins/saga/CHANGELOG.md
- plugins/fleet-core/CHANGELOG.md
- tests/ (per-finding behavior pins; release surfaces per repo convention)

### Tests to add or update

- Two-broker admission test pinning the decided invariant (refusal at acquire, or documented
  supersede with a settlement-layer one-effect proof across clones).
- Reconcile-loop `except DispatcherError` arm test: mid-tick refusal releases the subplot lock,
  appends a durable non-ack receipt, and the tick continues (mirror the codex PA-2 pin
  `test_advance_records_lease_refusal_as_halt_and_continues`).
- Resolve-scope guard test: symlinked home component onto another volume still walks ancestors;
  sticky-bit exemption pinned; NFS/SMB and FAT32/exFAT decisions pinned per the validator
  caveats in Finding 3.
- Halt-record visibility test: a receipt-spread halt append reduces as halted and surfaces in
  the consolidated report's ambiguity tier (Finding 4).

### Context library links
- source_context: docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md (outcome branch; KTD7 upstream-first discipline)

### Acceptance criteria

- [ ] `uv run pytest tests/ -k "lease or dispatcher or outcome" -q` green with the new invariant,
      arm, guard-scope, and halt-visibility pins included.
- [ ] `python3 -c "import ast,pathlib;..."`-style pin (or equivalent test) proves every live
      `make_dispatcher` call and every halt append satisfies the decided contract — no
      text-count pins.
- [ ] `grep -n 'covers every caller' plugins/` returns nothing: the audit-store/compat docstrings
      and CHANGELOGs state the real guard scope after the Finding 3 decision.
- [ ] `uv run python plugins/saga/scripts/outcome.py report <outcome>` (or the pinning test)
      shows a halted leaf in the ambiguity tier after a forced backend HALT — Finding 4 closed
      end-to-end.
- [ ] Release surfaces agree in one PR (plugin.json x2, marketplace.json, both CHANGELOGs) and
      the codex re-port issue is filed or linked before close.

### Verification

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/upstream-issue-draft.md
- Source type: local-file
- Source title: DRAFT — upstream Claude issue (infiquetra/infiquetra-claude-plugins), filed from PA-2 review per KTD7 upstream-first

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/627
- Number: 627
- Created at: 2026-07-20T13:57:05.286097+00:00

