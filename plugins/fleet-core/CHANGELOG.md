# Changelog

All notable changes to the fleet-core plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.25.3] - 2026-08-24

### Fixed

- **A negative `Retry-After` delta-seconds header now clamps to `0.0` (issue #770).**
  `parse_retry_after` in `fleet_commons.retry_backoff` returned negative float values for
  negative delta-seconds headers, contradicting its documented contract ("never a negative
  delay"). The HTTP-date path already clamped past dates to `0.0`; finite delta-seconds
  values are now clamped to `max(0.0, seconds)` at `_usable_delay`, ensuring callers that
  present rate-limit delay advice to operators never display negative wait times.

## [0.25.2] - 2026-08-22

### Fixed

- **A non-finite `Retry-After` no longer costs the caller its typed rate-limit surface.**
  `float()` accepts `inf`, `-inf`, `nan`, and any overlarge literal such as `1e400`, so
  `parse_retry_after` reduced a header carrying one of those to a non-finite "delay" and handed it
  back as though the server had given a usable hint. The sleep path hid the problem — `inf` clamped
  to `max_delay` and `nan` failed its `> 0` test — so the retries themselves looked correct. The
  damage surfaced only once retries were exhausted and the caller reduced the hint to whole seconds:
  `math.ceil(inf)` raises `OverflowError` and `math.ceil(nan)` raises `ValueError`, both UniFi
  clients caught that in their broad handler, and the operator was told `Unexpected error: cannot
  convert float infinity to integer` instead of how long to wait. `1e400` is the shape that matters
  in practice — an ordinary overlarge integer in a header, nothing exotic.
- A non-finite value is exactly the "no usable hint" case `parse_retry_after` already documents, so
  it now yields `None` and the caller falls back to computed jittered backoff. The rule covers the
  numeric path as well as the string one, because a caller that parses its own header hands the
  number straight in. A postcondition test asserts that every hint the function returns survives
  being turned into whole seconds, for every header shape at once — a listing of non-finite
  spellings is only ever as complete as the imagination of whoever wrote it.

## [0.25.1] - 2026-08-22

### Fixed

- **A `Retry-After` HTTP-date now backs the request off instead of killing it (review finding O3).**
  RFC 7231 section 7.1.3 allows `Retry-After` in two forms — delta-seconds and an absolute HTTP-date —
  and real controllers send the date form. `retry_backoff.py` only ever understood a number, so a
  caller that reduced the header to seconds itself raised `ValueError` inside the wrapped call. That
  error carries no `status_code`, `retry_with_backoff` therefore judged it non-retryable and
  propagated it immediately, and the caller's typed rate-limit handler never saw it: one request, no
  backoff, a generic error — the exact opposite of what the rate-limit primitive exists to do.
- New public `parse_retry_after(value, *, now=time.time)` reduces either form to a non-negative delay
  in seconds. It accepts an already-numeric hint unchanged, a delta-seconds string, and all three
  date forms `email.utils.parsedate_to_datetime` covers (IMF-fixdate, the obsolete RFC 850 form, and
  asctime, whose missing zone is read as GMT per the specification). An absent, empty, or unparseable
  value returns `None` — "no usable hint" — so the caller answers with computed jittered backoff.
- A date already in the past parses to `0.0`, never a negative delay. The non-positive-hint rule from
  0.8.1 then applies unchanged, so a stale date falls back to computed backoff rather than becoming a
  zero-sleep retry loop. Clamping stays where it was, in `_retry_delay`, so an absurd date and an
  absurd number are both bounded by `max_delay` on the same line of code. Jitter is untouched.
- `retry_with_backoff` gains a keyword-only `now` seam (epoch seconds, default `time.time`) so an
  HTTP-date resolves deterministically under test. It is distinct from `CircuitBreaker`'s monotonic
  `clock`; `bridge_call` forwards it through `**retry_kwargs`. The `retry_after` callable's type
  widens to `float | str | None` — additive, so every existing caller keeps working.
- **Consumer note, not yet actioned here:** both UniFi clients still call
  `int(resp.headers.get("Retry-After", 60))` before raising, so they keep converting the header
  themselves and remain exposed to this defect until they pass the raw value through. That change
  lands with the UniFi plugin, not with fleet-core; `tests/test_retry_backoff.py::
  test_a_caller_that_pre_parses_with_int_still_loses_the_retry` pins the boundary.

## [0.25.0] - 2026-08-13

### Added

- **Portable execution-class vocabulary and a runtime sibling of `resolve()`.** `models.json` grows `schema_version`, `scalar_efforts`, `execution_classes`, and `root_orchestration_profiles` (Codex version-2 shape). Existing `models` / `efforts` keys are unchanged. `resolve_for_runtime(work_shape, runtime)` maps an execution class onto a runtime-owned `{model, effort, fallbacks, workspace_boundary, effort_application}` for all six plugin runtimes (`claude`, `codex`, `grok`, `muse`, `qwen`, `agy`). `adapt_runtime_argv` is the only place that pair becomes vendor CLI flags. Collapse: grok/muse `max`→`xhigh`; agy `max`/`xhigh`→`high`. Effort application is structured data: argv for the five runtimes that take a launch flag; qwen is `{"mode": "in_session", "command": "/effort <rung>"}`. Confirming the directive took is U4, not this unit. See DECISIONS `{#effort-collapse-max}`.

## [0.24.0] - 2026-08-08

### Removed

- **Fleet lease broker and orphan evidence, deleted whole — campaign #677 unit U7 (#684).** `scripts/fleet_commons/lease_broker.py` (4,731 lines) and `scripts/fleet_commons/orphan_evidence.py` (1,578 lines) are gone, with their test suites `tests/test_fleet_lease_broker.py` (2,709) and `tests/test_orphan_fencing.py` (1,185) — 10,203 lines. This is the payload deletion the seven-unit unwind built toward; the emit-time file-disjointness check (`wave_file_conflicts()`) that replaced the fencing third shipped in #673, and U1–U6 unwound the remaining callers. No shim-resurrected broker survives: the U7 re-add guard (`tests/test_no_lease_broker_readd.py`) scans shim-resolved paths, not just the tree, per defect #642.

### Changed

- **Plugin description drops “lease and” (R11a, #684).** `plugin.json:4` now advertises “shared primitives, liveness decisions, …” — regenerated into `marketplace.json` via `scripts/sync_marketplace.py`.

## [0.23.1] - 2026-08-07

### Fixed

- **Audit-store directory creation is process-idempotent (#681, campaign #677 unit U4).**
  `_ensure_private_dir` walked `exists()`-then-`mkdir` — a TOCTOU — so two concurrent dispatches
  mirroring to one shared store root (both proceed per plan #677 Scope Decision row 1) raced, and
  the losing process died on `FileExistsError`. The mkdir is now `exist_ok=True`; the final
  lstat validation still enforces ownership, 0o700 mode, and not-a-symlink whoever created the
  directory. Surfaced by the U3 two-process claim-race pin under CI load; pinned by
  `test_ensure_private_dir_is_process_safe_when_two_creators_race`.

## [0.23.0] - 2026-07-24

### Added - generic plugin-root resolver `fleet_commons/plugin_resolution.py` (#620)

- `resolve_plugin_root(name, *, markers, env_var, anchor)` generalizes the byte-frozen
  `fleet_commons_shim` ladder — which only ever answers "where is fleet-core?" — to an arbitrary
  sibling plugin, returning `(root, rung)` with rung provenance under `FLEET_COMMONS_DEBUG=1`.
- Five rungs, identical in spirit to the shim: env override (raises on an explicit-but-invalid
  value), repo walk-up (an ancestor holding both `.claude-plugin/marketplace.json` and
  `plugins/<name>/`), `~/.claude/plugins/installed_plugins.json` by `<name>@` prefix with per-record
  tolerance, cache-sibling highest-semver scan, then fail loud naming every rung.
- `markers` is a SEQUENCE and every entry must exist for a candidate root to be valid, so a
  half-usable install (CLI present but schema missing, or vice-versa) is a rung miss, not a partial
  success. The default `anchor` is the module's own file, so callers never thread `__file__` and one
  substrate gives one answer in mixed cache/monorepo layouts.
- First consumer: saga's `/outcome` board-sync + `/pulse` (see saga 0.114.0). The bootstrap
  `fleet_commons_shim.py` is byte-unchanged; this is the additive-only 0.x growth
  `{#fleet-commons-mechanism-463}` anticipated when "a fourth consumer appears."

## [0.22.0] - 2026-07-23

### Fixed - Registry reader forward-compatibility: tolerate-and-preserve unknown fields, doctor/repair verbs (#617)

- `_closed_mapping` gains a tolerant sibling, `_tolerant_mapping`, used at every tolerance-scoped
  container boundary — the registry top level and the per-lease, per-fence, per-admission, and
  per-settlement-outer-record `from_dict`s. Known keys are still validated exactly as before
  (value/type/invariant checks unchanged); unknown additive keys are captured into a per-dataclass
  `extras` mapping instead of raising `RegistryCorruptError`, and `to_dict` merges `extras` back in
  last so the read → mutate → write round-trip preserves them byte-faithfully, even after the
  typed-dataclass rebuild. Fixes the 2026-07-17 (`recovery_capability_sha256`/`settlements`/
  `close_receipt`) and 2026-07-22 (`Lease.isolation`) incident shapes: a schema-newer writer no
  longer bricks every older reader fleet-wide.
- Digest-covered commitment records (settlement-close receipts verified by `_record_sha256`,
  including `FencingToken`) keep the strict closed vocabulary — unknown keys there still fail
  closed, per the KTD1 audit pinned in code comments at each carve-out site, because every byte
  participates in the hash commitment.
- Preserved extras are capped at 64 KiB serialized per document (`_MAX_EXTRAS_BYTES`); above the
  cap the read fails closed with `RegistryCorruptError` rather than becoming an unbounded
  unknown-blob channel in a shared 0600 state file. Archived closed-fence sidecars, which parse
  outside `Registry.from_dict`, enforce the same cap per record and bound the raw read at
  `_MAX_ARCHIVED_FENCE_BYTES` (4x the cap, to EOF — no single-read truncation of legitimate
  near-cap records), so the archive directory is not an uncapped side channel.
- Settlement commit closes the CAS-verified live fence in place via `replace(head,
  close_receipt=...)`, preserving per-fence extras through the close instead of rebuilding the
  fence and silently dropping a newer writer's state.
- Zero new registry fields are written: for an extras-free document, `to_dict` output is
  byte-identical to pre-#617 serialization (same keys, same `sort_keys=True` ordering). The schema
  string stays `fleet_lease_registry.v1`, and `schema != "fleet_lease_registry.v1"` still fails
  closed unchanged. Shipping this fix cannot itself brick a pre-#617 reader.
- New broker methods `doctor()` (read-only; reports `valid` | `tolerated-unknowns` | `corrupt`
  plus a JSON-path extras inventory and invariant status; never mutates, never raises on a corrupt
  document) and `repair()` (explicit down-migration: backs the registry up to a timestamped 0600
  sibling, strips extras, strict-revalidates, writes atomically under the existing single
  `_locked()` write path; refuses — leaving the registry untouched — if strict revalidation still
  fails after stripping, or if there is nothing to strip). `repair` replaces the manual
  hand-editing recovery used on 2026-07-17 with a shipped operator path.

## [0.21.0] - 2026-07-23

### Fixed - Unclaimed reservation survives async PostToolUse launch-return, defers to spawn_failed or claim TTL (#644)

- `record_parent_completed` gains a keyword-only `spawn_failed: bool = False` parameter. The
  unclaimed-reservation branch at the parent-completed kill site now completes (removes/recycles)
  an unclaimed lease only when `spawn_failed=True`; otherwise the reservation falls through to the
  existing stamp-and-keep path, surviving with `parent_completed_at` set, still claimable, with the
  session admission left intact. Fixes the async-launch race where the harness fires PostToolUse at
  spawn launch-return (~100-156 ms after PreToolUse, well before SubagentStart can claim), which
  previously deleted the still-unclaimed reservation and made direct Agent/Task spawns fail
  ~50% of the time under armed hooks ("expected exactly one fleet lease bound; found 0").
- `settle_batch` gains one release arm for stamped batch slots: an unclaimed slot whose parent
  signal already landed (`agent_id is None and parent_completed_at is not None`) is released at
  settlement so the registry still drains to zero leases when a batch child's spawn never claims
  its slot. Mid-run stamped slots awaiting their child (no parent signal yet) are unaffected.
- All claimed-lease paths, the admission guard, and the `record_parent_completed` return contract
  (tuple of removed lease ids) are unchanged — this is a single-branch change scoped to the
  unclaimed arm. Zero registry schema change.
- Abandoned reservations (parent-completed stamped, child never arrives) stop counting as live
  once the existing 30-second claim TTL expires — no new grace-window clock introduced.

## [0.20.0] - 2026-07-22

### Fixed - Worktree write-fence scoped to declared isolation, not spawn cwd (#616)

- `isolation` is now a first-class nullable `Lease` field (not a `resource_ref` key —
  `_AGENT_RESOURCE_KEYS` stays closed at `{logical_unit_id, worktree_root}`), reservation-carried
  from the PreToolUse payload's `tool_input.isolation` and forwarded through `acquire_agent` and
  `prepare_batch_call`. The adapter normalizes: only the exact string `worktree` is stored, any
  other declared value (e.g. `remote`) or absence stores `None`.
- `claim` replaces the unconditional cwd stamp with a three-way branch on reservation state:
  `isolation == "worktree"` stamps `worktree_root` from the child cwd (fenced, unchanged
  containment check); a PreToolUse-stamped reservation with no worktree isolation claims with no
  `worktree_root` (unfenced — admission, `read-write` mutation mode, and hook verification still
  apply); an unstamped attested batch slot (`tool_use_id is None`, #615's Workflow-runtime
  children) keeps today's cwd stamp byte-for-byte. `assert_write_target` changes zero lines — the
  fence trigger stays "is `worktree_root` present."
- Batch-slot recycle (`_complete_foreground_lease`) resets `isolation` to `None` alongside
  `agent_id`/`tool_use_id`, so a recycled slot re-claimed by a workflow child gets the conservative
  unstamped-slot behavior, never the prior occupant's declaration.
- Registry compatibility uses the existing backfill-before-closed-mapping idiom: a pre-#616
  (0.19.0-shaped) `leases.*` dict with no `isolation` key backfills to `None` before validation —
  no migration machinery.
- **Privilege-widening note (operator-pinned, D1):** a non-isolated `Agent|Task` spawn now writes
  cross-repo with no cwd fence. This is inert unless the parent's spawn was PreToolUse-stamped
  without `isolation: 'worktree'` — exactly the declared-intent case — and admission caps,
  `read-write` mutation gating, and hook verification are all unchanged.

## [0.19.0] - 2026-07-22

### Fixed - Workflow children bind attested unstamped batch slots (#615)

- `claim` accepts an attested-but-unstamped batch slot: Workflow-runtime children never emit a
  `PreToolUse Agent|Task` event, so no slot is ever stamped for them — the old candidate filter
  refused exactly the prelaunch state the driver `attest` step guarantees. Selection is
  stamped-first (`(unstamped-last, fencing_sequence, lease_id)`), so existing stamped claims are
  byte-identical and unstamped binding activates only where the old filter raised
  `LeaseNotFoundError`. Non-batch claims are unchanged.
- `record_child_terminal` recycles an unstamped batch slot on the child signal alone (it provably
  has no parent tool call, so the dual-signal contract cannot complete); stamped slots keep the
  dual-signal release unchanged.
- Batch keep-alive: `claim` and `record_child_terminal` renew live sibling slots in-lock, and
  `assert_write_target` opportunistically renews a mutating batch-member lease plus its live
  siblings — renewal scales with real child activity, a wedged child stops renewing and TTL
  reaps (fail-closed preserved; expired slots are never resurrected). Non-batch leases keep
  today's mutation-verification behavior byte-identical.

## [0.18.0] - 2026-07-22

### Fixed - Pid-liveness at the refuse-mode admission gate (#637)

- The refuse-mode admission branch in `_drop_superseded_resource_lease` (`acquire_agent`,
  `on_conflict="refuse"`) now consults the broker's existing `_owner_state` pid-liveness check
  on a live-unexpired conflicting prior lease, not just `_expired` (TTL + boot-id). A provably
  **dead** prior owner (stale boot-id, missing pid, or process-start identity mismatch) falls
  through to supersede immediately instead of blocking re-dispatch for the full 300s dispatch
  lease TTL — closing the crash-orphan window `#627` left behind. A **live** or **unknown**
  owner state still refuses, fail-closed, matching the posture the recovery gate
  (`lease_broker.py:4202`) already enforces; same-owner live conflicts still refuse (#627 KTD1
  unchanged, no same-owner bypass). Supersede-mode call sites and `_owner_state`'s other
  consumers (`sweep()`, the recovery gate) are byte-unchanged.

## [0.17.0] - 2026-07-20

### Fixed - Refuse-mode lease admission; universal fail-closed ancestor walk (#627)

- `LeaseBroker.acquire_agent` gains an opt-in `on_conflict` parameter (`"supersede"` default |
  `"refuse"`). `"supersede"` is byte-for-byte today's behavior for every existing consumer — the
  #356 retry-supersede design and its pinned test are untouched. `"refuse"` is the new mode: a
  live, unexpired prior lease on the same resource digest raises the typed `LeaseConflictError`
  (a `LeaseOwnershipError` subclass, so existing broad handlers keep working) naming the current
  holder, instead of superseding it. Expired or canonically-settled priors behave identically in
  both modes; the settlement-retained and canonically-closed precedence checks run unchanged,
  above the new liveness check. Saga's outcome dispatcher is the first (and so far only) caller
  to opt in, closing a cross-runtime double-preparation window on the outcome-dispatch resource
  class.
- `audit_store._ensure_private_dir` / `_refuse_unsafe_ancestors` now walk **every existing
  component from the filesystem root down**, not only components strictly below the user's home
  — the previous home-scoped walk silently exempted every out-of-home store location. The only
  mode exemption is world-writable **and** sticky (`S_ISVTX`, the system-temp shape, e.g. `/tmp`
  at 1777); a plain world-writable component is refused fail-closed wherever it sits, which now
  correctly catches NFS/SMB mounts whose mode bits diverge from local expectations and
  FAT32/exFAT volumes that `lstat` every entry `0o777`. Group-writable ancestors remain accepted
  by design (the #624 pinned boundary — unchanged, now with an explicit acceptance-twin test).
- **Correction to the record**: the 0.16.0 entry below claimed the world-writable refusal
  "covers every caller" via `Store.for_root`'s pre-walk `resolve()`. That claim was never
  accurate scope language for a guard that only inspected components below `$HOME` — the
  guard's actual reach is now the universal walk described above, and the source docstrings no
  longer make a caller-coverage claim of any kind. The 0.16.0 entry itself is left as written,
  as a historical record of what shipped then.

## [0.16.0] - 2026-07-20

### Security - Audit-store ancestor hardening (#624, PA-1 of #605)

- `audit_store._ensure_private_dir` now refuses symlinked, world-writable, or uninspectable
  existing path components strictly below the user's home (typed `AuditStoreError`, no silent
  fallback) before creating anything — closing the walk that could previously `mkdir` through a
  symlinked ancestor. The scope test is lexical on the expanded absolute path; home itself and
  out-of-home roots (e.g. sticky system temp directories used by test fixtures) are exempt.
  Group-writable ancestors remain permitted by design, now pinned by test.
- Reach differs per branch because `Store.for_root` canonicalizes the root with `resolve()`:
  mode bits survive resolution so the world-writable refusal covers every caller, while symlink
  identity does not, so the symlink refusal covers direct callers and the post-resolve window.
  The docstring states this rather than promising blanket symlink protection.

## [0.15.0] - 2026-07-18

### Added

- Monotonic `close_owner_admission` / `inspect_owner_admission` on the lease broker (#358 R2):
  one committed close under the authority lock refuses every subsequent acquire, reserve,
  claim, and retry for that exact owner (`OwnerAdmissionClosedError`) while existing leases
  stay inspectable and releasable. Repeating close is idempotent; there is no reopen
  operation. The `close_generation` is issued from the registry's one fencing sequence so a
  teardown driver can re-verify the still-closed generation before emitting a zero-open
  completion receipt — the fence that prevents a spawn racing `teardown-complete`.
- Registry schema gains the bounded `closed_owner_admissions` map (pre-#358 authorities
  migrate to an empty map). Overflow evicts the lowest-generation record, which lapses that
  owner's admission back open until re-closed — the fence is scoped to record retention, a
  liveness ceiling, not unbounded history. The teardown driver re-closes at pass start,
  snapshots after the close, and refuses its receipt unless the pass-local generation is
  still the closed one, so eviction can cost a retry but never a false completion.

## [0.14.0] - 2026-07-17

### Added
- Added the pure shared liveness engine with bounded phi scoring, five-interval cold start,
  attribution-safe signal fusion, closed decisions, and Team-only terminal authority after three
  receipt-proven response windows.
- Kept lease renewal/expiry out of liveness evidence and made skew, boot drift, malformed numbers,
  unresolved sends, and exhausted delivery fail closed without granting destructive authority.

## [0.13.0] - 2026-07-17

### Added
- Added broker-owned prepare, commit, abort, conservative retained-authority inspection, canonical
  close receipts, and exact-receipt successor CAS for accepted external-runtime writes. Automatic
  restart-safe producer replay remains lifecycle work for #358.
- Added closed orphan-evidence schemas, bounded write-once quarantine, immutable refusal events and
  close-seal mirrors, plus deterministic read-only candidate projection.
- Kept authority and audit state owner-only, added Darwin process identity, and made generic release
  fail closed while settlement authority is retained. These are cooperative local-plugin safeguards,
  not a hostile same-user security boundary.
- Advanced the lease protocol to version 2 for the incompatible prepare/commit/abort settlement
  contract. Exact archived heads remain authoritative even after they leave bounded inspection.

## [0.12.0] - 2026-07-16

### Added
- Added the process-locked `lease_broker.py` fleet authority with separate agent and outcome-
  worktree pools, all-or-nothing batch reservation, trusted child binding, cooperative renewal,
  two-signal foreground release, owner/session teardown, fencing-token supersession, and safe
  dead-owner sweep. Registry writes are closed-schema, permission-checked, atomic, and rooted in a
  runtime-neutral state directory.
- Added closed concurrency admission records and shared defaults of three normal agents, four
  read-only agents, and seven aggregate agents. The broker records the resolved policy digest and
  refuses mixed live policy snapshots instead of re-resolving consumer policy.
- Published lease broker protocol version 1 so armed consumers reject a missing or skewed
  fleet-core installation before dispatch.
- Hardened the authority boundary after whole-diff review: renew and single-lease release require
  the exact fencing token, delegated parent validation and child grant share one transaction,
  abandoned pre-spawn admission pins expire and remain inspectable, owner teardown trusts only
  broker-recorded terminal evidence, and closed resource heads move to permission-checked cold
  archives when the hot registry reaches its bound without losing closed/superseded classification.
- Made the restricted-host boot identity fallback stable across processes and calls, so a denied
  kernel boot-time query falls back to Darwin's persistent boot record instead of making a newly
  acquired lease expire before its first renewal.

## [0.11.0] - 2026-07-14

### Added
- `intent_envelope.py` (#373): three OPTIONAL, additive schema-v1 fields on the canonical
  `IntentEnvelope` — `backends_permitted` (a type-strict unique backend list; the consuming
  dispatch seam owns the vocabulary), `degrade_policy` (closed vocabulary `halt` /
  `operator_away_one_rung`; absent means "not captured" → HALT by default when a backend
  posture is engaged), and `spend_envelope` (`SpendEnvelope`: `tier_ceiling` validated
  against the fleet `tier_palette.MODELS` ladder and/or `cost_ceiling_tokens`, a finite
  positive token budget; an empty object is an authoring error). Absent fields emit no keys,
  so every pre-#373 v1 envelope round-trips byte-identical — no forced migration; the
  closed-schema rule is unchanged (unknown keys still fail).
- `authorize_spend(spend, *, actual_tokens, requested_tier)` (#373): the pure, HALT-only
  pre-dispatch spend decision (`SpendAuthorization`) — a tier stronger than the ceiling or
  actuals at/past the cost ceiling deny for explicit step-up; an un-rankable tier denies
  (fail closed); wrong-typed actuals raise loudly. `None` actuals ("no data yet") and an
  undeclared tier do not engage their gate — leaf-produced actuals are self-attested, and the
  module threat model now says exactly that, plus the narrowing guarantee: the #373 fields
  only ever narrow dispatch relative to the uncaptured default, never grant a write path.

## [0.10.0] - 2026-07-14

### Added
- Issue-fence extraction is CRLF-safe: `` ```intent-envelope `` blocks on GitHub-web-authored
  bodies (CRLF line endings) extract identically to LF — adoption on the consumer side and the
  BLOCKING validity gate on the capture side both see the envelope (#380).
- `scripts/fleet_commons/intent_envelope.py` (#380): the canonical fleet `IntentEnvelope` —
  one committed run-start posture schema (`run_mode` + a `ceremony_gates` block of
  `reviews_required` / `merge` / `deploy_nonprod`, each `gate`|`auto` defaulting to `gate`),
  the single composed run-start posture interview (`INTERVIEW`, a typed challenge-response
  manifest with closed options), the mode-keyed machinery (`recommend_tier(work_shape,
  run_mode)` — unattended is exactly one ladder rung cheaper; `spend_posture(run_mode)` —
  cache-tight/silent vs interactive/ask-on-spend-increase; `resolve_spend_action` raising
  `PostureError` on an attended spend increase without an approval token;
  `self_select_posture` for unattended defaults from the same matrix), and the issue-carried
  envelope block (`render_issue_block` / `envelope_from_issue_body` /
  `outcome_start_decision`). The schema is closed per `schema_version` — unknown keys and
  off-vocabulary values fail loudly; provenance fields are documented self-attested and the
  envelope authorizes nothing by itself (the token-checked write class is #449's mechanism).
  Consumers: saga (`OutcomeSpec.intent` / `ExecutionSpec.intent` / `/outcome start`),
  team-execution (Step B1 `posture_check.py`), mission-control (issue-capture block).

## [0.9.0] - 2026-07-13

### Added
- `scripts/fleet_commons/delegation_state.py` grows the durable delegation-integrity attempt
  counter (#520 F1): `record_integrity_divergence` / `integrity_attempts` /
  `clear_integrity_attempts` over `.claude/delegation/integrity.json`, keyed session + engine with
  the same 4h TTL and fail-open-read posture as `active.json`. This is where the dispatch layer's
  re-queue-once-then-HALT count (KTD7, #384) now lives, so it survives one-process-per-attempt
  consumers.

### Fixed
- `delegation_state.arm()` / `disarm()` read-modify-write is now serialized under an exclusive
  `fcntl.flock` on a sibling `<name>.lock` file (#520 F4): two sessions arming concurrently could
  previously lose an entry last-writer-wins — a silent, fail-open loss of tripwire protection.
  Reads stay lock-free and fail-open.

## [0.8.5] - 2026-07-12

### Added
- Add `scripts/fleet_commons/audit_store.py`, the durable delegation audit store
  (`~/.claude/delegation-audit` by default): mirrors receipts, agy result snapshots, and provenance
  manifests keyed by run id/execution id, plus a write-once pre-fix draft snapshot primitive for the
  chaperone-dispatch path (#396). Deliberately machine-local and uncommitted, unlike
  `evidence_ledger.py`'s committed-per-saga store — different durability requirement, different home.
- Extend `scripts/fleet_commons/delegation_audit.py` with `reconcile_store(...)`, reconciling the
  durable audit store against claimed dispositions and flagging exactly the delegations whose
  disposition claims real execution but carry no schema-valid receipt as no-ops.

## [0.8.4] - 2026-07-09

### Added
- Add `divergence` to the canonical external-engine intent vocabulary with the high-tier
  Claude-chaperone posture used when agreement and disagreement both require explicit review.

## [0.8.3] - 2026-07-09

### Added
- Add `scripts/fleet_commons/output_attestation.py`, the shared `output_attestation.v1` helper
  for byte count, SHA-256, and empty-output proof over bridge-produced artifacts.
- Extend `bridge_receipt.emit_receipt(...)` with optional `receipt_emitter`, `run_id`,
  `external_tokens`, and `output_attestation` fields while keeping `bridge_receipt.v1` base
  validation backward-compatible for historical receipts.

## [0.8.2] - 2026-07-09

### Added
- Add the `offload-test-gated` tier-policy row so Saga can resolve cheap, ratify-only
  chaperone defaults for test-gated external-engine offloads from the shared fleet table.

## [0.8.1] - 2026-07-08

### Fixed
- Clamp positive `Retry-After` hints in `fleet_commons/retry_backoff.py` to `max_delay`, and treat
  zero or negative hints as absent so retry loops use computed jittered backoff instead of sleeping
  forever or retrying immediately.

## [0.8.0] - 2026-07-07

### Added — `delegation_audit.py` engine-parametrized classifier + corroborator, `delegation_state.py` arm/disarm liveness channel (#384, U1/U2)

- `scripts/fleet_commons/delegation_audit.py` — one auditor, two engine configs (agy, codex):
  `classify(transcript_path, engine=None) -> AuditClassification` (`real` / `fallback_suspected`
  vocabulary, generalizing the scan at `agy_delegate.py:995-1021`), `corroborate(engine, since_ts)
  -> BundleCorroboration` (launch flag + receipt presence under the engine's bundle root), and
  `reconcile(classification, corroboration, self_report) -> verdict` (`real` /
  `fallback_suspected` / `delegation_integrity`). Streams transcripts line-by-line under an 8 MiB
  cap (matching codex's `MAX_LAST_MESSAGE_BYTES` precedent). agy's original `classify_transcript`
  stays untouched as a parity tripwire (R7).
- `scripts/fleet_commons/delegation_state.py` — `arm(engine, session_id)` / `disarm(...)` /
  `active(session_id)` over `.claude/delegation/active.json`, atomic tmp+rename writes (codex
  `_write_json` precedent), TTL-reaped stale entries (default 4h), plus an `arm`/`disarm`/`status`
  CLI. Reads never raise — corrupt or missing state is always treated as unarmed (fail-open).
- Both modules live under `scripts/fleet_commons/` per the vendored-shim placement rule
  (`{#fleet-commons-mechanism-463}`); saga's hooks and dispatch layer load them the same way
  `engine_dispatch.py` already loads `bridge_receipt`.

## [0.7.0] - 2026-07-06

### Added — bridge_receipt.v1 schema module (#387, #383)

- `scripts/fleet_commons/bridge_receipt.py` — the `bridge_receipt.v1` proof-of-execution schema:
  `emit_receipt(...)` builder and `validate_receipt(dict) -> list[str]` (empty list = valid). Common
  core (`schema`, `engine_id`, `variant`, `transport`, `wall_time_s`, `bytes_produced`) plus
  transport-discriminated `runner` evidence — `{pid, argv, exit_code}` for `transport: cli`,
  `{url, status_code, model}` for `transport: http`. The emit helper stamps `schema`/version itself
  so a caller cannot mislabel a receipt.
- Canonical home for the schema per the fleet-commons + vendored-shim distribution mechanism
  (`{#fleet-commons-mechanism-463}`) — `plugins/agy/scripts/fleet_commons_shim.py` carries a
  byte-identical vendored copy, covered by the existing vendored-copy drift guard.

## [0.6.0] - 2026-07-06

### Added — ordinal cost-weight table beside the tier palette (#366)

- `scripts/fleet_commons/cost_weights.json` + `cost_weights.py` — a 16-cell ordinal weight grid and
  `to_spend(model, effort)`, co-located with `models.json` (the ordering it prices). Validated against
  the live `tier_palette` MODELS/EFFORTS ordering at import: completeness, per-axis strict monotonicity,
  and off-palette rejection all raise `CostWeightsError`, so a drifted table fails loud rather than
  silently mis-pricing a run (closes the `{#tier-vocab-ordering}` two-contracts gap for the cost axis).
- Weights are ordinal/relative, not dollar prices — hand-authored non-linear so premium tiers
  (opus/fable, xhigh) cost disproportionately more. Consumed by saga's `#366` `cost_budget` HALT and
  `spend_envelope`; additive-only, no change to existing fleet_commons modules.

## [0.5.0] - 2026-07-06

### Added — single-source tier palette: models.json registry + ladder ops (#370)

- `scripts/fleet_commons/models.json` — canonical model/effort registry with explicit per-model
  `rank`, per-effort `rung`, and per-model `effort_ceiling`. `tier_palette.py` now derives the
  ordered `MODELS`/`EFFORTS` tuples from these indices at import instead of hand-ordering them;
  import-time validation rejects duplicate/gapped rank and a missing/unknown `effort_ceiling`.
- `tier_palette.py` — `escalate` / `downgrade` / `clamp` / `stronger` / `strongest` ladder ops that
  reason in *strength* (so the opposite-direction MODELS strongest-first / EFFORTS weakest-first
  tuples can't be confused), plus `effort_ceiling` / `supports_effort` / `clamp_effort_to_model`
  (the AC5 surfaced-note clamp).
- `references/tier-palette.md` — onboarding runbook for adding a model/effort, encoding the
  `{#tier-vocab-ordering}` "grep `.index(` before extending a closed vocabulary" rule.

## [0.4.0] - 2026-07-05

### Added
- `scripts/fleet_commons/effort_rider.py` (#363): `inject_effort(prompt, effort, spawn_kind)` —
  the one swappable seam honoring a resolved `effort` value on every dispatch path. On the
  `workflow`/`external-engine` spawn kinds (which already accept effort as a real per-call knob)
  it is a guarded no-op pass-through; on the `agent` spawn kind — the native Agent-tool teammate
  path with no real per-call effort knob — it prepends a labeled `EFFORT_RIDER[effort]` proxy
  directive to the prompt. Also ships `reconcile_effort(resolved_effort, spawn_kind, ...)`,
  emitting a named `tiering-drift[<spawn_kind>]` line when a post-run actual (manifest-recorded
  effort, or rider text on the `agent` path) disagrees with the resolved value.
- References: `plugins/fleet-core/references/` gained the effort-convention documentation
  consumed by team-execution's `SKILL.md` (R8) — the single fleet-wide place `effort:`
  frontmatter's meaning and cascade precedence are documented once, not re-declared per plugin.

## [0.3.0] - 2026-07-05

### Added
- `scripts/fleet_commons/tier_resolver.py` — dispatch-time tier resolver (#362):
  `resolve(work_shape, role_kind, envelope_ceiling, operator_override) -> {model, effort,
  because, cheaper_fallback, needs_confirm}`, reading defaults from `tier_policy.json` and the
  ladder ops from `tier_palette` (never re-declaring `MODELS`/`EFFORTS`). Consumed cross-plugin
  via `fleet_commons_shim.load("tier_resolver")`; `fable`/`xhigh` reachable behind a
  `needs_confirm` gate.
- `scripts/fleet_commons/tier_policy.json` — machine-readable work-shape → tier registry
  (6 keys incl. the `mechanical`/`purely-mechanical` split).
- `scripts/fleet_commons/render_tier_table.py` — renders the `/plan` Step-1 tier table from the
  registry, drift-guarded against `plan/SKILL.md`.

## [0.2.0] - 2026-07-05

### Added
- `fleet_commons/retry_backoff.py` shared primitive (#348): `retry_with_backoff` (jittered
  exponential backoff, attempt cap, non-429 pass-through, injectable RNG/clock/sleep + a
  `retry_after` seam), a `CircuitBreaker` (CLOSED→OPEN→HALF_OPEN→CLOSED over an injected clock),
  and `bridge_call`. Stdlib-only; import-ready for engine-bridge (agy/codex) adoption. Consumers
  vendor the byte-identical `fleet_commons_shim.py` and call
  `fleet_commons_shim.load("retry_backoff")`.

## [0.1.0] - 2026-07-04

### Added
- Initial release: fleet-commons distribution mechanism (issue #463, DECISIONS
  `{#fleet-commons-mechanism-463}`).
- `scripts/fleet_commons/tier_palette.py` — canonical tier palette (`MODELS`, `EFFORTS`,
  `CHEAP_MODELS`, `ENGINE_INTENTS`, `model_rank()`, `effort_rank()`), moved verbatim from
  saga's `execution_spec.py` as the first-mover primitive.
- `scripts/fleet_commons_shim.py` — canonical resolution shim (five-rung ladder with rung
  provenance, `FLEET_COMMONS_DEBUG=1` stderr diagnostics, fail-loud); consumers vendor
  byte-identical copies guarded by a repo drift test.
