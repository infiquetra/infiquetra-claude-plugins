# Changelog

## [0.127.0] - 2026-08-05

### Changed

- **`already-absent` changed meaning in team teardown — campaign #677 unit U2 (#679).** The
  disposition now means "git no longer lists this worktree" (the census is the per-outcome
  worktree registry cross-checked with `git worktree list`). Pre-retirement it meant "the
  lease head is gone", which said nothing about disk. Its evidence-ref namespace moved with
  it: the lease-namespaced `broker:`/`sweep:` strings plus `{lease_id}` are redefined as
  `worktree:path-absent:<outcome-id>:<subplot-id>`. The retained branch reports
  `worktree-listed`. `released` keeps its place in the closed disposition vocabulary, but the
  sweep no longer produces it — its only producer was the reap branch, deleted with the reaper
  seam (see Removed). `open_count` in the `team_teardown.v1` projection now counts census
  entries not yet at a final disposition ("still open" = "still unsettled"); the registry does
  not shrink on its own, and completion was re-gated to match. Recovery's `--expired-only`
  skip re-keyed from lease liveness onto "a git-listed worktree exists" (observation reason
  `expired-only-live-worktrees`). DECISIONS `{#u2-rekeys-teardown-onto-worktree-registry-679}`.

### Removed

- **Fleet lease broker retired from the non-skippable teardown contract — campaign #677 unit
  U2 (#679).** Teardown enumerates worktrees via `outcome_worktrees.live_worktrees` over every
  `saga-outcomes/*/worktrees.json` registry instead of a lease list, threading `repo_root`
  through the hook and CLI (the census spans all outcome stores; a single store handle was the
  wrong seam shape). Deleted outright: `default_broker`, `_current_head`,
  `make_resident_stop_adapter`, `make_process_stop_adapter`, `register_subprocess` (the
  spawn-time registration seam), `authorize_resident_stop` (the idle-eviction gate — its
  post-retirement story is queued for U6, QUEUED
  `{#teardown-eviction-gate-retired-needs-u6-story}`), the owner-admission close fence and its
  still-closed recheck (`close_generation` stays in the fact shape as the vestigial constant
  1), and the worktree sweep's reaper seam — teardown is report-only and removes no worktree
  from disk under any input (KTD12: it never did). A regression sentinel pins both the disk
  guarantee and the seam's structural absence. The closed event family, the projection schema,
  and the CLI verb/flag surface are unchanged; the action-kind/resource-kind vocabularies stay
  frozen so lease-era ledger facts remain valid reads. Agent docs moved in the same PR (R11):
  `teardown-reclamation.md` and `teardown-consumer-sites.md` rewritten for the broker-free
  contract. Release surfaces move per-PR under the #429 diff guard.

## [0.126.0] - 2026-08-05

### Removed

- **Fleet lease broker retired from the cross-runtime handoff protocol — campaign #677 unit U1
  (#678).** All six broker call sites in `outcome_compat.py` (`verify`,
  `prepare_agent_settlement`, `commit_agent_settlement`, `inspect_resource_head`,
  `acquire_successor`, `verify`) are gone: `offer_handoff` writes the sealed offer record via
  the store's write-once path with a caller-asserted (but REQUIRED — an anonymous offer HALTs)
  `issuer_owner_id`, and `accept_handoff` completes on the write-once intent/commit pair alone
  — no successor lease, no close-receipt CAS. Deleted outright as token-threading-only:
  `_acquire_successor_or_resume`, `_broker_module`, `_lease_broker_mod`,
  `outcome_dispatch_resource`, `_HANDOFF_PRODUCER`. Absorbed coupled callers in `outcome.py`
  (handoff/attach CLI branches, `attached_advance`/`attended_handoff` signatures, the
  `_cli_broker`/`_cli_broker_error`/`_cli_admission` helpers); the CLI admission flags stay
  accepted for cross-runtime compatibility but no longer feed a broker. Issuer identity
  becoming caller-asserted is an accepted loss of the plan's Option C scope decision —
  DECISIONS `{#u1-absorbs-outcome-handoff-callers-678}`. The discovery envelope's
  `fleet-broker-fencing` capability string and `fleet-broker` authority value are unchanged
  pending the cross-runtime vocabulary decision (QUEUED
  `{#handoff-negotiation-vocabulary-escapee}`). Release surfaces move per-PR under the #429
  diff guard; the campaign's final module deletion lands in U7.

## [0.125.0] - 2026-08-04


### Fixed

- **`/work` no longer overwrites the saga field it later reads (#693).** `orchestration_ref`
  was overloaded with two incompatible values: the durable spec JSON path `/work` reads to locate
  the canonical spec (and passes as a file path to `spec_table.py` / `execution_spec.py emit` /
  `execution_spec.py lease`), and the transient workflow run id recorded post-launch. The launch
  step always runs after the read step, so every saga that launched a Workflow lost its spec path.
  The failure was quiet: the resume halt tested only field PRESENCE, so a saga carrying a run id
  cleared the guard that exists precisely to catch a missing ref, then handed a workflow id to a
  script expecting a filename. Measured at filing: 15 of 93 local sagas held a run-id-shaped ref.
  The overload is retired with a discriminating guard, not a deleted one.

### Added

- New saga envelope field `orchestration_run_id` (+ `saga.py save --orchestration-run-id`) — the
  dedicated home for the workflow run handle the Workflow tool returns at launch. The spec path and
  the run handle now coexist on one saga; a run-handle-only tick carries the spec ref forward
  instead of clobbering it. Mirrored into `_saga_summary` (restore/state.json index/ticks) and
  `scan` candidates; documented in `saga-spec.md` §3.1/§3.4 (the example envelope no longer shows a
  run-id-shaped `orchestration_ref`), `operator-choice.md` §6, and the docs model + boundaries map.
  Additive optional field — no `schema_version` bump (saga-spec §9).
- `saga.py spec-check --saga-id <id>` — the discriminating pre-launch/resume gate over the ref:
  `ok` / `missing` / `run-id` / `file-missing`, exit 0 only on `ok`. `/work` now gates the ultracode
  launch on it mechanically instead of testing presence in prose. A run handle held BESIDE the ref
  never satisfies the guard (the case that passed pre-fix and must not), and a run-id-shaped value
  IN the ref is flagged with its own recovery line rather than silently accepted.

### Changed

- `/work` §1.5: the post-launch tick records `--orchestration-run-id <workflow-id>` and never
  `--orchestration-ref <workflow-id>`; the HALT conditions route through the `spec-check` verdicts
  with per-verdict recovery lines. The 15 sagas already holding run-id refs are NOT migrated —
  backfill is a separate call (#693 out-of-scope).

## [0.124.0] - 2026-08-03

### Fixed

- **Quorum floor is now a strict majority of the declared panel size** (`n // 2 + 1`, was
  `ceil(n / 2)`). The floor is baked at emit time over the declared `n`, but the majority threshold
  it guards is recomputed at runtime over the verdicts that actually reported. Those two formulas
  agree at odd `n` and differ by one at even `n`, so an even-sized panel that lost exactly half its
  verifiers still met the floor — and because the lost verdicts were the refuting ones, a
  `verifier-disagreement` HALT silently became a PASS. Reproducible with any cause of a dropped
  verdict (crash, timeout, prose reply, schema-invalid shape), so it predates the 0.123.0 severity
  split rather than being introduced by it. The change is a **no-op at every odd `n`**, so all 36
  committed `n=3` panels are unaffected. Changed at both computation sites plus the docstring and
  emitted comment that described the old formula.
- `__logAdvisory` no longer logs `deliverable UPHELD` unconditionally. The call is emitted before the
  gate's enforcement throw on every path, so a refuting panel printed "deliverable UPHELD" and then
  threw `verifier-disagreement` on the next statement — two contradictory lines, the false one first.
  The verdict is now passed in and the wording branches (`REFUTED` / `UPHELD`).
- A `null` element in `advisory_corrections` no longer halts a run. The schema types the bucket as a
  bare array with no `items` constraint, so a JSON `null` crosses the tool boundary; `typeof null` is
  `"object"`, so the renderer dereferenced `null.claim` and threw — aborting runs whose gate found
  zero gating refutations, and on a degraded panel preempting the correct diagnostic throw with an
  opaque null dereference. Elements are now null-guarded and the whole accumulate-and-log body is
  wrapped, so the non-gating accumulator can never halt a run.
- Control and invisible formatting characters in advisory text are collapsed to spaces before the
  text is logged or stored. Advisory content is model-authored by a verifier that read a diff it did
  not write, and reached `log()` verbatim. Two passes over two hazards: the C0 controls, DEL, the C1
  block (NEL at U+0085) and the line/paragraph separators, any of which forges a second, more
  alarming log line; then the bidi marks, embeddings, overrides and isolates (U+200E/F,
  U+202A–U+202E, U+2066–U+2069) plus the BOM, which leave the byte sequence intact while reordering
  what a human reads in a terminal or log viewer — the Trojan-Source pattern. The channel is
  non-gating, so the exposure is misleading display, never a flipped verdict.
- The harvest-failure marker is scrubbed like any other advisory. It embeds an exception message —
  model-reachable text — and was the one path that built an entry without going through
  `__renderAdvisory`, reopening the newline forgery above on the path least likely to be audited.
- Truncation never stores half of a surrogate pair. `.slice()` cuts on UTF-16 code units, and the
  cap now bounds the value **stored and returned**, not just the logged line, so an emoji straddling
  the boundary would have put ill-formed UTF-16 across the harness return — substituted or rejected
  by any consumer that re-encodes it.
- Advisory entries carry a `round` ordinal, and `advisory_corrections` entries are capped per panel
  with a `dropped` count. An `iterate_to_consensus` unit or a `#364` tier climb pushes one entry per
  round under the same `unit`, so without a round marker corrections about a discarded intermediate
  result were indistinguishable from those about the accepted one. The ordinal counts **panel
  rounds**, incremented on every round including one that produced nothing; deriving it from stored
  entries instead renumbered silently, so a unit whose first round came back clean labelled its
  second round "round 1".
- Advisories survive a halt. A bare `throw` skips the harness's final `return`, which is their only
  structured exit — stranding advisories from units that had already delivered. Every emitted throw
  now routes through `__halt`, which attaches the accumulator to the error as
  `err.advisory_corrections`.
- The verifier prompt states the panel's actual gating bar. The VERDICT CONTRACT hardcoded "a
  majority of the panel KILLS the unit" and was emitted verbatim into `unanimous` panels, so a
  verifier applying the prompt's own calibration test reasoned against a bar of 2/4 when the real bar
  was 4/4. `pass_rule` is now threaded into `__verifierPrompt`.
- `references/sandbox-spawn-sites.md` — the **fourth** verdict-shape surface — no longer tells
  out-of-saga verify spawns to restate the retired `{refuted, upheld}` contract. This repo's
  CLAUDE.md routes every such spawn through that fallback ladder, so the documented degradation path
  rebuilt the severity-blind gate by hand. A drift guard now covers it.
- `references/execution-spec.md` described `advisory_corrections` as a flat list of corrections; it
  is a list of per-panel `{unit, round, corrections, dropped}` objects. The doc is the contract for
  the deferred `/work` consumer, so a consumer written from it would have rendered `[object Object]`.

### Tests

- Panel-size coverage widened from `n=3` only to `n=1..7` for the quorum floor and `n=1..4` for the
  split-bucket gate arithmetic. The defect above lived entirely at even `n`, which the previous
  matrix never emitted — the test parameters and the bug occupied disjoint halves of the space.
- Reserved harness identifiers are now proven to be rejected as unit ids by emission, rather than
  asserted to be present in a Python set. A refactor that dropped them from the collision path while
  leaving them in the set would have kept the old membership assertion green.
- New runtime tests execute whole emitted harnesses under node for: the even-`n` half-strength halt,
  a `null` advisory element, control-character stripping, invisible formatting characters
  (bidi/NEL/BOM), the harvest-failure marker, surrogate-safe truncation, the refuted-panel log
  wording, advisory survival across a halt in a multi-unit run, per-round advisory labelling under
  `iterate_to_consensus` including a round that produced nothing, and the per-panel item cap.
- The verifier prompt's gating-bar wording is pinned by **executing** the emitted harness and reading
  the prompt the panel handed its verifiers. The previous assertion grepped the emitted source for
  `${gatingBar}` — the helper's own un-interpolated template literal, present verbatim in every
  emitted script regardless of what the ternary computes, or whether it exists. Deleting the
  branching logic outright left the suite green. The harness stub now records verifier prompts
  instead of discarding them, so no future prompt-contract test inherits that blind spot.

## [0.123.0] - 2026-08-03

### Fixed - the refute-N verify panel now has a severity axis (#686)

The emitted verify-panel verdict schema carried exactly one rejection bucket. A verifier that read
a unit's code, tests, and check results correctly, then found one wrong sentence in the unit's own
self-description, tripped the same gate as a verifier who found the code itself broken — and did,
in a real seven-unit workflow run (`infiquetra/infiquetra-codex-plugins#71`), where a false-negative
gate discarded a correct unit and dead-lettered five downstream units.

- `execution_spec.py::_verifier_schema()`: the single `refuted` key is renamed to
  `refuted_deliverable` (gating — the unit's actual work is wrong, or the verifier could not see
  enough evidence to judge) and joined by a new required `advisory_corrections` key (non-gating —
  the work is right but the unit's prose about it is wrong). A verdict missing either bucket is a
  runtime failure that counts toward the missing-verifier quorum floor; there is no legacy-`refuted`
  compatibility shim.
- `_emit_panel_reconciliation()` — the single gate-arithmetic site shared by the one-shot panel, the
  `iterate_to_consensus` retry loop, and the `#364` `escalate_on_signal` tier climb — now counts a
  verifier as refuting only when its gating bucket is non-empty. An advisory-only panel upholds the
  unit and never burns a tier escalation.
- Non-gating corrections are logged during the run and collected into a new module-level
  `__advisories` accumulator, surfaced in every emitted harness's final
  `return { units, advisory_corrections }` (harnesses previously returned `undefined`).
- Both emitted prompt surfaces — the Python-assembled `_verifier_prompt()` and the emitted JavaScript
  `__verifierPrompt` helper — state the two-bucket VERDICT CONTRACT with concrete examples and the
  "sound code, wrong prose" test, ported verbatim from the hand-validated prototype wording in
  `infiquetra-codex-plugins`.
- `agents/readonly-verifier.md` — the verifier's own system prompt, and the third verdict-shape
  surface — no longer instructs the legacy `{refuted, upheld}` shape. Left stale it would have
  contradicted the schema attached at spawn: a verifier following its own definition would emit a
  verdict the schema rejects, classifying as runtime-missing and pushing the panel toward the quorum
  floor. A drift guard in `tests/test_saga_execution_spec.py` now pins all three surfaces.

## [0.122.0] - 2026-07-27

### Removed - the write fence and the emitted lease contract, both unreachable (#671)

0.121.0 moved concurrent-writer prevention to emit time. That left the runtime write fence with
nothing to defend, and measurement showed it had never been defending it: `assert_write_target`
performs a containment check only when the claim carries a `worktree_root`, and the #616 privilege
change stamps one only for spawns declaring `isolation: "worktree"`. Agent-tool residents declare
none, so the fence returned without a check. Separately,
`INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off` meant the hook exited before reaching the broker at all.

- Deleted `hooks/lease_mutation_hook.py` and its `PreToolUse`
  `Bash|Write|Edit|MultiEdit|NotebookEdit` registration. That is 20ms off every Bash and every file
  edit. Saga's `PreToolUse` registrations go 6 -> 5; the five `lease_lifecycle_hook.py`
  registrations are untouched.
- Deleted `scripts/lease_broker.py::verify_hook_mutation`, the hook's only entry point and the only
  caller of the saga-side `assert_write_target` wrapper.
- `emit_workflow_script` no longer emits `const lease = {...}`. Nothing ever read it: a workflow
  script has no filesystem or Node API access, so the generated code could not reach the broker
  under any circumstance.

Unchanged: `workflow_lease_metadata()`, the `execution_spec.py lease` CLI, and the driver-owned
`/work` ceremony (`reserve|attest|renew|release`). The reservation contract still exists — only the
inert copy inside the generated JavaScript is gone.

**If you re-arm `INFIQUETRA_FLEET_LEASE_ENFORCEMENT`, read DECISIONS `{#fence-carried-batch-renewal-671}`
first.** `assert_write_target` doubled as the only within-wave batch-renewal heartbeat.

## [0.121.0] - 2026-07-27

### Added - concurrent units declaring the same file halt at emit (#671)

Two units scheduled into the same dependency wave that declare the same path race on a shared
working tree. Nothing caught it: workflow work units emit at the ambient default
(`workspace_isolation` `"ambient"` — only verify panels are spawned isolated, KTD6), team-execution
residents are same-cwd by construction, and the fleet lease never fenced either. The lease's
`assert_write_target` only performs a containment check when the claim carries a `worktree_root`,
and a PreToolUse-stamped, non-worktree reservation is stamped without one — the deliberate #616
privilege change, pinned by `test_stamped_non_isolated_claim_leaves_write_unfenced`.

- `wave_file_conflicts(spec)` — pure; returns every same-wave unit pair sharing a declared path.
- `assert_no_wave_file_conflicts(spec)` — raises `SpecError` naming each pair, the shared paths,
  and the repair. Called from `emit_workflow_script` and `team_emitter` before anything renders.
- `spec_table.py` gains a **Concurrent-writer safety** section, so the collision is visible at the
  approval gate rather than discovered at emit. A clean parallel wave says so explicitly — silence
  would not distinguish "checked and safe" from "not checked".
- `/plan` Step 5 now states the splitting rule: same file means one unit, not two sequenced ones.
  Merging reuses the prompt cache; splitting pays to load the same file twice and risks a lost write.

Three deliberate differences from `segment_units()`, which groups units into resident workers on
the team backend and is the closest existing logic: every declared path participates (not just
`files[0]`), paths compare exactly (not by `plugins/<name>` prefix, so two units in different
directories both touching `tests/conftest.py` are caught), and comparison is per-wave rather than
over contiguous declaration runs.

Measured before shipping: across the 18 specs in `docs/plans/` — 97 units, all declaring `files`,
92 waves — only 4 waves run more than one unit and **zero** same-wave pairs share a file. The check
is prophylactic against today's corpus, and a regression test pins that it stays quiet on it.
## [0.120.0] - 2026-07-27

### Fixed - the journal's only mechanical writer appended to the bottom of a newest-first file (#659)

`spend_retro.py`'s `append_to_journal` opened `LEARNINGS.md` with `open("a")`, so its section
landed at the very end — under whatever stale date heading happened to sit there — in a file whose
own header says "append new entries to the top, most-recent first". It also emitted
`## <date> Spend Retro`, which is neither a date section (`## YYYY-MM-DD`) nor an entry (`###`),
so no reader keyed on either shape would classify it correctly.

The function has never run against a real journal (no `Spend Retro` section exists in this repo's
history), so this fixed a latent writer rather than an active one — but it was the only mechanism
capable of reintroducing the drift that #659 was raised for, so it goes with the cleanup.

- Renamed to `write_to_journal` and reimplemented as a top-insert: the entry is spliced in above
  the current newest section, reusing that section's heading when the dates match and opening a new
  one when they do not. Existing content is still never edited.
- `render_journal_section` now emits `### Spend Retro {#spend-retro-<date>}` — an entry, under a
  date section, matching every other entry in the file.
- Tests pin the direction (new section lands above the old one), same-day reuse (no duplicate
  heading), and that every `##` heading in the output is a bare date.

## [0.119.0] - 2026-07-27

### Fixed - pre-push gate reasons about the git invocation, not the command text (#663)

`_is_git_push_command` matched `(?:^|[|;&])\s*git\b[^|;&]*\bpush\b` — the *word* anywhere in a
git command's argument span — and `_parse_git_dash_c` recognized only the `git -C <path>` form.
Two faults followed from that one design choice, both observed live.

- **Fault (a), wrong-repo gating.** Any targeting form other than `git -C` fell back to the
  session cwd, so a push aimed elsewhere ran the *session* repo's manifest and suite. The
  missing-manifest cross-repo exit could not save it — the session repo has a manifest. Observed:
  a push in another repo ran this repo's ~5500-test suite and blocked on 17 unrelated failures.
- **Fault (b), spurious full-suite runs.** `git add docs/push-notes.md`,
  `git log --grep=push`, `git show HEAD:docs/how-to-push.md`, and
  `git commit -m "... push ..."` all ran the entire gate. A several-minute suite on a `git log`,
  and under CPU contention the gate hit its own step timeout — turning a read-only git command
  into a hard failure. This reproduced *during the fix*: a `python3 -c` diagnostic whose string
  contained `&& git push` ran the full suite.

Now: `shlex` tokenizes the command into segments (quoting honored, so a commit message is one
token), `_git_invocations` finds real `git` command heads, and `_git_subcommand` walks git's
global options — skipping an option's value where it takes one — to identify the **actual
subcommand**. Only `push` gates. The target repo is resolved from the invocation
(`-C` / `--git-dir` / `--work-tree`), then a leading `cd <path>`, and only then the session cwd.

Unknown options before the subcommand are skipped rather than guessed, and an unparseable command
yields no segments — the gate stays off by default rather than firing on a guess. Not a weakening:
a real push on a failing suite still blocks.

**Two bypasses caught in review (#670) before merge**, both of which let a *real* push skip the
gate — a false negative on a safety gate, strictly worse than the over-firing this change fixes:

- **Shell operators without whitespace.** `shlex.split` only separates an operator that already
  has whitespace around it, so `git push&&echo ok` tokenized as `['git', 'push&&echo', 'ok']` —
  the subcommand read as `push&&echo`, never matched `push`, and the push went through ungated.
  Same for `git add -A&&git push`, `git commit -m x;git push`, `git push|cat`, `git push||echo`.
  Now uses `shlex.shlex(..., punctuation_chars=True)`, which splits operators while still keeping
  a quoted commit message as one token — so the fault-(b) fix is preserved.
- **`--git-dir` resolved to no repo.** `--git-dir` names the git directory, not a working tree.
  Passing `<repo>/.git` as `cwd` to `git rev-parse --show-toplevel` fails, `_find_repo_root`
  returned `None`, and `main()` exited 0 before reading the manifest — the exact targeting form
  the fix claimed to support. `_as_worktree_dir` now resolves a `.git` path to its parent.
- **Newline separators.** `\n` is ordinary whitespace to the lexer, so `git add -A\ngit push`
  tokenized to one flat run whose subcommand read as `add` — a second-line push bypassed the
  gate. Lines are now split before lexing.
- **`env` option prefixes.** The prefix walk handled `env VAR=value` but not `env`'s own options,
  so `env -i git push` and `env -u GIT_CONFIG git push` found no git invocation at all.
  `_skip_env_prefix` now walks `-i` / `-u NAME` / `--unset=NAME` / `-S` / `-C` and assignments.

The full behavior matrix — 14 forms that must gate, 8 that must not — is pinned in
`tests/test_pre_push_gate.py` (32 tests).


## [0.118.0] - 2026-07-27

### Added - `spec_table.py`: the execution-spec approval table, at every backend approval (#668)

- New `scripts/spec_table.py` renders a spec as the artifact an operator actually approves:
  summary (backend, unit count, spend vs budget, resolved concurrency), a per-unit table (tier,
  `depends_on`, shape — fan-out/pilot/verify panel/engine/sandbox/escalation — and ordinal spend),
  the dependency waves showing what genuinely runs in parallel, and **what the chosen backend can
  and cannot enforce**.
- The enforceability section is the reason this exists. `SANDBOX_ENFORCEABLE_BY_BACKEND` and
  `TIER_ENFORCEABLE_BY_BACKEND` (`execution_spec.py:401-424`) say that `cc-workflows-ultracode`
  and `inline` enforce read-only + disposable-worktree and reach every model, while
  `team-execution` enforces **neither** axis and cannot reach `fable`. A spec whose verify panels
  need a sandbox the backend cannot enforce HALTs at emit — the operator now sees that *before*
  approving instead of after the run fails.
- Read from those registries directly, never a second copy: a registry edit is the only way to
  change what the table reports, and a test pins that coupling.
- Unknown backends enforce nothing, matching the emitter's own R3/R4 stance that unknown is never
  permissive.

### Changed - approval is one artifact in one format, wherever the decision is made

- `skills/plan/SKILL.md` Step 5 now renders the table instead of asking Claude to hand-build one.
- `commands/tier.md` re-surfaces it after a mid-run patch — a re-tier changes what was already
  approved.
- `skills/work/SKILL.md` renders it before emitting and executing.
- `skills/outcome/SKILL.md` renders it at leaf backend approval. `outcome.py` previously had 25
  `json.dumps` calls and no table at all.


## [0.117.0] - 2026-07-27

### Removed - five never-fired guard modules (#666)

Each had **zero production Python importers** and had **never written a runtime artifact** on any
machine. Verified two ways per module: import-graph grep, and a filesystem search for the artifacts
each claims to produce.

- `scripts/gate_record.py` (926 lines) — durable operator-absence approval records. No
  `record.json`, `resolution.json`, or `absence.jsonl` has ever existed. It was CLI-invoked from six
  skills, but the CI gate with teeth (`lint_gate_absence_contract.py`) checks only the
  `<!-- gate-record: ... -->` declaration marker in skill prose, never a `gate_record.py`
  invocation. All six markers are retained; the lint still reports `VIOLATIONS: 0`. The six skills
  now state the absence behavior as a rule instead of a CLI ceremony.
- `scripts/undo_ledger.py` (370 lines) + `commands/undo.md` — the act-log-inverse path.
  `references/adjustment-envelope.md` already documented why it could not work: the path was
  prompt-mediated and *no production mutation site was ever mechanically wired to the ledger*. No
  `undo-ledger.jsonl` was ever written, so `/undo` could only ever report an empty ledger.
  `scripts/ship_undo.py` is the surviving, working rollback path (16 real `rollback_manifest.json`
  files on disk).
- `scripts/shadow_audit.py` (420 lines) — sampled tier-sufficiency replay. Zero `shadow-audit:`
  entries in any evidence ledger.
- `scripts/check_empty_delivery.py` (150 lines) — its job is already done by
  `dispatch_settlement`'s `silent-no-op` classification, which has fired for real (2026-07-23,
  issue-617 units U2/U3).
- `scripts/reap_orphans.py` (419 lines) — zero importers; `fleet_doctor` denylists it by design.
- `references/gate-record.md` and the five modules' test files.

### Changed

- Command surface: 25 command files → 24, 24 routable → 23. `/undo` is gone. This is the only
  user-visible capability change.
- `references/adjustment-envelope.md`, `references/sandbox-spawn-sites.md`,
  `references/evidence-write-sites.md`, `references/envelope-token.md`, `skills/work/SKILL.md`, and
  the six gate-declaring skills updated to match.


## [0.116.0] - 2026-07-27

### Removed - `liveness_reping_hook.py` hard-blocked every `SendMessage` call

- Deleted `hooks/liveness_reping_hook.py` and its three `hooks.json` registrations
  (`PreToolUse`, `PostToolUse`, `PostToolUseFailure` on `SendMessage`).
- The hook read the recipient from `tool_input` keys `recipient`/`target_agent_id`/`target`.
  The host `SendMessage` schema is `{to, message, summary}`, so extraction always returned
  `None`, `_tool_values` raised, and the `PreToolUse` leg exited 2 — blocking **all**
  inter-agent messaging, not just the staged-claim calls the docstring scoped it to. The
  recipient parse ran at `_pre_tool_use` line 1, before the pending-claim lookup, so the
  documented "ordinary calls pass silently" path was unreachable.
- Agent teams could not exchange messages in any session with saga enabled.
- `scripts/liveness_events.py` is retained: team-execution's `liveness_protocol.py` probes
  for `scripts/liveness_events.py` to resolve the installed saga root, and `lease_protocol.py`
  depends on that resolution for the #358 teardown CLI. Removing the ceremony wholesale is
  deferred until that resolver is rehomed.
- `tests/test_liveness_consumer_conformance.py::test_sendmessage_hook_is_registered_for_pre_post_and_failure`
  is replaced by `test_no_hook_gates_sendmessage`, a regression guard asserting no saga hook
  matches `SendMessage` on any event.

**Operator action required:** update the installed saga plugin. The cached copy at
`plugins/cache/infiquetra-plugins/saga/<version>/` still carries the blocking hook until reinstalled.

## [0.115.1] - 2026-07-26

### Fixed - unmanaged sessions arm fleet-lease admission from policy defaults instead of being refused

The `PreToolUse` hook on matcher `Agent|Task` is registered unconditionally for every
session (`hooks/hooks.json`), but `session_admission_snapshot()` admitted only when the
session already had a pinned snapshot or carried all four `INFIQUETRA_FLEET_*` variables.
A session that never invoked a Saga command had neither, so **every** subagent spawn in
**every** ordinary Claude Code session halted with "normal Agent/Task admission requires a
configured resolved session snapshot" — and the only way forward was to run a Saga command
the operator never wanted. The lease registry was healthy throughout (`doctor` reported
`status: valid`, `leases: []`); the gate was simply fail-closed against sessions it was
never meant to govern.

`session_admission_snapshot()` now separates the two cases it had been conflating:

- **No fleet environment at all** — the session was never Saga-managed, so it arms from
  `admission_snapshot()`'s policy defaults (`session_limit=3`, `aggregate_limit=7`,
  `mutation=read-write`) and admits. Enforcement stays on: the lease is still recorded and
  the concurrency ceiling still applies.
- **Some but not all fleet variables** — a preflight ran and did not finish. That is a real
  fault and still halts, now naming the missing variables instead of giving generic advice.

Fully-armed environments and pinned snapshots are unchanged.

The partial-environment guard runs **before** the pinned snapshot is trusted, not inside the
`configured is None` branch. Gated on `configured is None` it was skipped for exactly the
sessions that already had limits to ride on: a half-resolved environment was neither complete
enough to trip the explicit-mismatch check nor empty enough to read as unmanaged, so a broken
preflight proceeded on the earlier snapshot's limits instead of halting. Reproduced on a
configured session with only `INFIQUETRA_FLEET_SESSION_LIMIT` set, which returned
`ADMITTED (…, 3, 7, 'read-write')` rather than raising. The complete explicit-env mismatch
check still runs after, unchanged.

Tests were also made hermetic: they strip every `INFIQUETRA_FLEET_`-prefixed key from the
inherited environment, so an operator's own fleet settings can no longer decide the assertion.
The filter is by prefix rather than a list of names — an enumerated denylist holds only until
the next fleet variable is added and stops protecting the tests at that moment, which is how
`INFIQUETRA_FLEET_BATCH_ID=ghost` failed the unmanaged-session case with "workflow batch
'ghost' has no available reserved slot" while all four admission names were already cleared.

## [0.115.0] - 2026-07-25

### Fixed - ship ceremony resolves head and base from ceremony-scoped evidence, not the rolling `branch` tick field (#635)

`ship_ceremony.py` treated `saga["branch"]` — a field re-stamped from `git branch --show-current` on
every tick save (`saga.py:566`) — as if it recorded the ceremony's own branch. On a leaf-into-outcome
PR whose last save happened on the base branch, that field names the base, and five call sites
consumed it (or the literal string `main`) as ceremony state. All five are fixed by routing through
one new resolver, `resolve_ceremony_refs()`: PR-authoritative (`gh pr view --json
headRefName,baseRefName`) first, the `ceremony-branch:` opened-resource manifest entry plus a
per-saga base sidecar second, and a raise — never a fallback to `saga["branch"]` — when both are
exhausted.

- **A — `branch_delete` no longer targets the base.** The deletion target, the `git rev-parse`
  existence check, and the `ceremony-branch:<id>` manifest close all derive from the one resolved
  head value, so the deletion target and the manifest key can never diverge again. Previously a
  mistargeted delete both destroyed the base branch (local + origin) and silently no-op'd the real
  manifest close (`_close_if_registered`'s by-design behavior on an unregistered id), leaving the
  real branch's `ceremony-branch:` entry open forever — `_teardown_attempt_closes` closes only
  `scratch` and `worktree` kinds, never `branch`, so teardown stayed permanently blocked.
- **B — `checkout_main` checks out the resolved base**, not the literal `main`. Its return value is
  unchanged (`saga.get("branch")`) — that value feeds the `checkout_main` rollback-manifest entry
  consumed by `ship_undo._restore_pre_ceremony_checkout`, whose contract is to restore the
  pre-ceremony checkout, not the branch just checked out.
- **C, D — both `gh pr create` call sites** (`_do_open_pr` and `start()`) pass an explicit `--base`
  from ceremony context, defaulting to the dynamically resolved repo default branch
  (`resolve_default_branch()`: `git symbolic-ref refs/remotes/origin/HEAD`, falling back to
  `gh repo view --json defaultBranchRef`) rather than the literal `main`.
- **E — `_do_merge` probes the ceremony's resolved base** for both `pre_merge_main_sha` and
  `merge_sha`, instead of `refs/heads/main`. The key name `pre_merge_main_sha` is kept as-is — it is
  a keyword argument of `ship_undo.append_entry` referenced by the test suite, and the field is
  audit-only forensic context that `undo()` never consumes programmatically. Before this fix, an
  outcome-based ceremony recorded `main`'s unrelated, fully reachable tip as `merge_sha`; the undo
  path's `SHA_UNREACHABLE` guard never fired on that value, so a bad revert was one `ship --undo`
  away from landing on the default branch.
- **F — `ship_undo._undo_merge` now applies the revert to the ceremony's recorded base**, not the
  literal `main`, on all three commands it issues: the checkout, the revert (which runs on whatever
  branch the checkout left `HEAD` on), and the push. `append_entry` records the resolved base on the
  `merge` rollback-manifest entry at merge time, so undo needs no network call to recover it. A
  rollback-manifest entry written before this ships (no recorded base) floors at the **literal**
  `main` (`ship_undo.LEGACY_MERGE_BASE`) — deliberately not the repo's current resolved default
  branch, since such an entry's `merge_sha` was read by the pre-#635 `_do_merge`, which probed
  `refs/heads/main` verbatim. Provenance beats currency: resolving the current default for a legacy
  entry could send the revert to a branch the sha was never read from.
- **New hazard `BRANCH_DELETE_TARGETS_BASE`** (`ceremony_hazards.py`), `acknowledgeable=False`,
  probed only for the `branch_delete` transition: fires when the resolved head equals the resolved
  base, and refuses before the runner dispatches and before the saga tick save, so the ledger is
  provably unadvanced on a refusal. The probe is a backstop on the resolver's fallible rung: on rung
  1 the head and base come from one `gh pr view` record, and GitHub forbids a same-repo PR whose
  head equals its base, so the check is inert there by construction, correctly — rung 1 is
  authoritative. It guards rung 2, where the head comes from the opened-resource manifest and the
  base from the PR — two independent records that can agree wrongly, the shape of the originating
  `outcome/norns-next-horizon` incident.
- **Confirmation grammar — `branch_delete` now requires a qualified target
  (`--operator-confirmed branch_delete:<branch>`)**, naming the resolved head branch, instead of the
  bare transition name. A bare `--operator-confirmed branch_delete` refuses with a message naming the
  resolved target; a qualified target that does not match the resolved value also refuses. Every
  other transition's bare confirmation grammar is unchanged. Behavior note: this also moved one
  previously-uniform outcome — `--operator-confirmed merge:x` with `merge` upcoming used to hit the
  raw-string mismatch refusal and now hits the "does not take a confirmation target" refusal, because
  the guard now compares the parsed transition name rather than the raw string. Both paths still
  refuse; only the wording changed. This was unreachable via the CLI before the change (`argparse`
  `choices=` rejected the colon form) and reachable only via the Python API.
- Two documentation surfaces migrated to the qualified grammar: `plugins/saga/skills/work/SKILL.md`
  and `plugins/saga/skills/work/references/pr-continuation-loop.md`.
- **Code-review repairs, same release.** The pre-PR review found that the fix had closed the
  divergence *inside* `_do_branch_delete` and reopened the same class of split *across* the operator
  gate, plus four smaller gaps:
  - **The confirmed target is now the deleted target.** `run()` resolved the refs, validated
    `--operator-confirmed branch_delete:<target>` against them, handed the resolved head to the
    hazard probe — and then dispatched a runner signature carrying none of it, so
    `_do_branch_delete` re-resolved from scratch. Because the ladder degrades from the PR to local
    evidence on any non-zero `gh` exit, one transient failure in that window answers from a
    different rung and can name a different branch, reproducing the original data loss *through the
    fix* with the non-acknowledgeable hazard reporting clean. `run()` now hands the validated
    `CeremonyRefs` to the runner; the authorization and the deletion are the same object by
    construction, and a redundant `gh pr view` goes away with it.
  - **An independent base floor.** `_do_branch_delete` bound `refs.base` and never used it; its only
    floor was the literal `"main"`. It now refuses when the resolved head IS the resolved base. This
    is the check that matters when no PR exists at all, because
    `_probe_branch_delete_targets_base` returns `None` without a PR number and the hazard never runs.
  - **Option-safe refs.** A resolved ref becomes git argv, and `git checkout -f` is accepted, silently
    discards every uncommitted change in the tree, and sits on a REVERSIBLE-tier transition that asks
    no one. `CeremonyRefs` now validates on construction and `write_ceremony_base` refuses at the
    write, matching `ship_undo._require_option_safe`'s long-standing contract.
  - **`_do_open_pr` persists the base it resolves**, as `start()` already did. Without it the
    plain-run flow never wrote a sidecar, so rung 2 could never answer and the later transitions were
    hard-dependent on a reachable `gh` — the opposite of the ladder's stated purpose.
  - **`_probe_stacked_pr` asks about the resolved head**, not the rolling `branch` field. Its own
    summary line says "the branch about to be deleted", and on this topology the rolling field is the
    base — so a child PR stacked on the real head went undetected while sibling leaf PRs fired
    spurious, acknowledgeable hazards.
  - `git ls-remote` exits 0 with empty output for an absent ref, so `_do_merge`'s sha read raised a
    bare `IndexError` that `main()` does not catch; it now refuses with a diagnosis.
  - Two docstrings corrected under R13: `detect()` described the hazard as comparing "two derivation
    paths" without the rung qualification that makes it true, and `_manifest_head_branch` claimed
    manifest entries are "never re-stamped" when `ship_teardown.register` refreshes a still-open
    entry by design.
- **Pre-push gate step timeouts move into the manifest (#658).** `pre_push_gate_hook.py` hardcoded a
  300-second budget for every step, which broke its own SINGLE SOURCE property — retuning the gate
  meant editing the hook rather than `tools/gate-manifest.json`. It also failed in the worst
  direction: the suite grew past 300 s while still passing (measured 325 s green on an idle machine),
  so the gate blocked **every** push in the repo while reporting a timeout that reads exactly like a
  red at the call site. Steps may now declare `timeout_seconds`; the default stays 300 for every step
  that does not, and the `pytest` step declares 600. The refusal message now names the budget that
  was actually applied instead of a hardcoded 300. Carried in this release because it blocked
  shipping #635 itself.
- No `fleet-core` bump (`fleet_commons/` untouched) and no `mission-control` bump (no verb added).

## [0.114.0] - 2026-07-24

### Fixed - `/outcome` board-sync + `/pulse` resolve mission-control via the plugin ladder (#620)

- Board-sync located mission-control at `<repo_root>/plugins/mission-control/scripts/sdlc_manager.py`
  and read the schema at `Path(__file__).parents[2]/mission-control/config/sdlc-schema.json` — both
  correct only inside the plugins monorepo, so every board write failed from a consumer repo (24
  failed `board_synced` records in one live tick). All four sites — `board_progression.py`,
  `outcome_board_sync.py`, `outcome.py`'s re-export, and `outcome_reconcile.py`'s schema seam — now
  resolve through `fleet_commons.plugin_resolution.resolve_plugin_root` (fleet-core 0.23.0).
- Resolution happens ONCE per reconcile tick and feeds both the CLI path and the schema read, so the
  two can never name different installations. `/pulse`'s sibling `default_sdlc_manager` shares the
  same resolver while keeping its soft-failure telemetry contract.
- An unresolvable mission-control — including a fleet-core too old to carry `plugin_resolution`, the
  realistic state while the install registry stays stale (#642) — withholds the whole cohort with a
  single loud `unavailable` record instead of N ops × retries of the same terminal error, and never
  retries. A resolved-but-unreadable schema keeps the prior per-op `failed`-status behavior while the
  coalesced progress comment still posts. Every driven record carries the resolved root and rung.
- Escape hatch: `MISSION_CONTROL_ROOT` forces a known-good install (rung 1), mirroring
  `FLEET_COMMONS_ROOT`.

## [0.113.0] - 2026-07-23

### Added - `doctor` and `repair` adapter CLI verbs for registry forward-compatibility (#617)

- `plugins/saga/scripts/lease_broker.py` gains two subcommands beside `inspect`/`sweep`, routed
  through the shim-resolved broker (no direct import bypass): `doctor` (read-only; prints the
  fleet-core 0.22.0 broker's structured report and exits with a distinct code — 0 clean, 3
  tolerated-unknowns-present, 4 corrupt; an unmapped future status fails closed to 4 rather than
  defaulting to clean — never raising for a corrupt document) and `repair`
  (requires the explicit `--strip-unknown` flag; performs no default action, since stripping
  additive fields from shared fenced state is a deliberate rollback operation, not routine
  maintenance). Both ship the operator path for the registry read-tolerance layer landed in
  fleet-core 0.22.0, replacing the manual hand-editing recovery used on 2026-07-17.
- Requires fleet-core >= 0.22.0.

## [0.112.0] - 2026-07-23

### Fixed - Adapter routes PostToolUseFailure distinctly from PostToolUse for parent-completed signal (#644)

- `record_hook_parent` (`plugins/saga/scripts/lease_broker.py`) now derives `spawn_failed` from the
  hook payload's `hook_event_name` — `True` exactly when `hook_event_name == "PostToolUseFailure"`
  — and forwards it as the new keyword-only `spawn_failed` argument to the fleet-core 0.21.0
  broker's `record_parent_completed`. A genuine launch failure still cleans up its reservation
  eagerly; an ordinary async `PostToolUse` launch-return no longer does, closing the #644 race.
  `hooks/lease_lifecycle_hook.py` and `hooks/hooks.json` are unchanged — both events already
  carried the full payload including `hook_event_name`.
- No compatibility shim against an older fleet-core: against pre-0.21.0 the new keyword argument
  raises `TypeError` on the observational `PostToolUse` path (retained-for-retry posture), so
  version skew degrades to TTL-bounded release instead of signal-bounded release — soft, bounded,
  and exactly what the #642 provenance check exists to catch.
- Requires fleet-core 0.21.0.

## [0.111.0] - 2026-07-22

### Fixed - Worktree write-fence scoping — adapter forwards declared isolation (#616)

- `reserve_hook_agent` reads `tool_input.isolation` via a new `_declared_isolation(payload)`
  helper beside `_agent_type`, threaded into both the `acquire_agent` and `prepare_batch_call`
  reserve paths so the fleet-core 0.20.0 broker's three-way claim-time fence policy has a real
  pre-spawn isolation signal to act on. `claim_hook_agent` is unchanged — it still passes the
  actual child cwd; the broker now decides whether to stamp it as `worktree_root`.
- Hooks (`lease_lifecycle_hook.py`, `lease_mutation_hook.py`) change zero lines — event routing
  and fail-closed postures are untouched by this leaf.
- Requires fleet-core 0.20.0.

## [0.110.0] - 2026-07-22

### Added - Fleet-lease emergency kill-switch (#615)

- Both lease hooks (`lease_lifecycle_hook.py`, `lease_mutation_hook.py`) honor
  `INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off`: the exact string `off` disarms enforcement with a
  loud per-event stderr notice and touches no broker state; any other value or absence leaves
  the hooks armed (fail-safe direction). Emergency use only — with fleet-core 0.19.0 binding
  Workflow children to attested batch slots, routine runs no longer need any neutralization.

## [0.109.0] - 2026-07-22

### Added - Settlement-gate operator waiver (#618)

- New `dispatch-waiver` run-fact kind (`dispatch_settlement.record_waiver` /
  `active_waiver_covers` / `blocking_roster`): a provenance-stamped, append-only operator waiver
  for a halt-required dispatch cohort. The waiver snapshots the blocking roster
  `(unit_id, attempt, state)` at grant time and covers only while the current roster stays a
  subset of it — deliveries never invalidate; any new casualty, attempt cohort, or open unit
  re-halts with no operator action. Grants validate loudly (manifest + currently halt-required)
  and are idempotent on the roster digest. A new kind, never a `dispatch-settlement` event, so
  readers predating it (including the byte-frozen codex runtime) keep halting, fail-closed.
- `outcome.py waive <outcome-id> --dispatch-id --reason --answerer [--transport] [--at]`:
  operator verb with `approve`-style provenance (`--answerer` maps to the fact's `waived_by`).
  Site-agnostic `dispatch_settlement.py waive` subcommand uses the fact's own field names.
- The frontier settlement gate partitions halt-required reports by waiver coverage: uncovered
  reports halt exactly as before (reason names only uncovered dispatch ids); a fully covered
  gate dispatches and appends one durable `settlement-waived` receipt per newly dispatched unit,
  naming every covered dispatch id and its waiver provenance.
- No settlement truth is mutated: classifications, `halt_required`, and every existing fact
  schema stay byte-identical.

## [0.108.0] - 2026-07-22

### Fixed - Typed dispatcher lease-transient contract; loud abort on permanent faults (#637)

- `outcome_dispatcher` now exports `DispatcherLeaseTransientError(DispatcherError)`, raised at
  exactly the lease-lifecycle sites the #627 halt-and-continue arm was already scoped to:
  admission `LeaseConflictError` (classified against the shim-loaded broker authority class,
  checked in-place — `outcome_dispatcher` never leaks that classification to `outcome.py`), the
  renew-failure raise, and the lost-authority raises. Every other `DispatcherError` cause (shim
  load failure, protocol skew, and any other fleet-core resolution failure) stays a plain
  `DispatcherError`.
- `_reconcile_once`'s `except DispatcherError` arm now branches on `DispatcherLeaseTransientError`
  with one `isinstance` check — `outcome.py` still imports no fleet-core types. The transient
  branch is #627's existing body unchanged: release the per-subplot lease, append the
  reducer-visible `(dispatch, halt)` record (spread-first, literal-last, `receipt_kind`
  preserved), settle `SILENT_NOOP`, continue the tick — `test_advance_records_lease_refusal_as_
  halt_and_continues` stays green (its dispatcher raise updated to the transient subclass to
  match the type production now emits at that admission site). A non-transient
  `DispatcherError` now **re-raises and
  aborts the tick loudly** (the pre-#627 posture for permanent faults): no backoff state, no new
  ledger classification; the per-subplot `dispatch-{sid}` store lock is left held and self-heals
  via `acquire_lease`'s stale-reclaim after the 900s store-lock TTL, while the coordinator lock
  is released by the existing outer `finally` — an aborted tick never wedges the coordinator.

## [0.107.0] - 2026-07-20

### Fixed - Cross-runtime lease refusal, dispatcher halt visibility, universal ancestor guard (#627)

- The outcome dispatcher's `make_dispatcher` now acquires its per-leaf lease in the new opt-in
  `on_conflict="refuse"` admission mode (`fleet-core` 0.17.0): a live, unexpired prior lease on
  the same content-derived resource digest — a concurrent runtime preparing the same leaf —
  refuses at admission with a typed `DispatcherError` instead of being silently superseded and
  double-prepared. Every other lease-broker consumer keeps the existing supersede-on-acquire
  default unchanged (the #356 retry-supersede design and its pinned test are untouched). The
  seam this closes is real but narrow: admission exclusion for the outcome-dispatch resource
  class, scoped to one clone's settlement ledger (per `git-common-dir`) and to the
  dispatch-preparation window only — it is not a cross-clone sequencing guarantee, and prose
  claiming otherwise has been removed.
- `_reconcile_once` now catches `DispatcherError` on the dispatch hot path (mirroring the
  existing `BackendRateLimitError`/`BackendHaltError` arms): the per-subplot lease is released,
  a durable **reducer-visible** `(dispatch, halt)` record is appended paired to the same intent
  `key`, the attempt settles as a no-backend-effect `SILENT_NOOP`, and the tick continues. Before
  this fix, an uncaught refusal left the legacy `kind: dispatch, phase: intent` record matching
  no reducer branch — the orphaned intent was invisible, the per-subplot lease leaked until TTL
  (900s), and the leaf silently re-dispatched with no halt and no operator page.
- All three receipt-spread halt appends (`spend:<sid>`, `dispatch:<sid>` backend-menu halt, and
  the backend-halt lane) now store a final `"kind": "dispatch"` after the receipt spread, so
  `reduce_dispatch_ledger`'s halt arm and `outcome_report._halted_subplots` both see them and a
  halted leaf reaches the consolidated report's ambiguity tier end-to-end. The receipt's own
  `kind` (`halt`/`spend-halt`) moves to a non-colliding `receipt_kind` field — no receipt data is
  lost.
- Both ancestor guards (`outcome_compat._refuse_unsafe_handoff_ancestors` here; the ported
  fleet-core twin below) now walk **every existing path component from the filesystem root**,
  not just components strictly below `$HOME` — the previous under-home scope silently exempted
  every out-of-home clone location. The only mode exemption is world-writable **and** sticky
  (the system-temp shape, e.g. macOS `/private/tmp` at 1777); a plain world-writable component
  anywhere is refused fail-closed, which now correctly catches NFS/SMB homes with divergent mode
  bits and FAT32/exFAT volumes that `lstat` every entry `0o777`. Group-writable ancestors remain
  accepted (the #624 pinned boundary, unchanged, now with an explicit acceptance-twin test).

## [0.106.1] - 2026-07-20

### Fixed - Handoff settled-guard refusal-precedence parity (#631)

- The `accept_handoff` already-settled guard (`_settled_lookup`) now consults the shared v1/v2
  dispatch reduction ONLY for the receipt-authoritative `dispatched` state (a codex-native
  launched acknowledgement — the one settlement the #351 lane cannot see). Legacy commits and
  operator handoffs fall through to the #351 dispatch-settlement lane, matching the codex
  runtime's accept-path lookup. The 0.106.0 form consulted every settled state, which reordered
  refusal codes in the byte-frozen `outcome_compat` accept flow: a handoff replayed by a second
  receiver refused `handoff-already-settled` where the cross-runtime contract (and codex, given
  identical state) refuses `handoff-receiver-conflict`.

## [0.106.0] - 2026-07-20

### Fixed - Outcome advance and handoff settled-guard read codex-native dispatch records (#628)

- Ported the codex runtime's version-aware dispatch reducer (`reduce_dispatch_ledger`) into
  `outcome_store.py`: legacy `{kind: dispatch, phase: commit}` records and codex-native
  `outcome.dispatch.v2` intent/ack records now reduce through one shared path, so both runtimes
  read a shared clone's ledger identically.
- `advance` dedup (`_dispatch_records` / `_reconcile_once`) now counts a receipt-authoritative
  native `ack_kind=launched` acknowledgement as SETTLED (no re-dispatch — restoring the
  cross-runtime "exactly one dispatch side effect" invariant, R5/R6), and reads a live native
  intent without an acknowledgement as IN FLIGHT: the leaf is refused with a visible halt
  receipt directing to launch-evidence/operator-handoff reconciliation, never silently
  re-driven under legacy crash-recovery semantics.
- The handoff acceptance already-settled guard (`_settled_lookup`) additionally consults the
  shared reduction, so `accept_handoff` refuses a natively-settled leaf with
  `handoff-already-settled`.
- `replay_pending` mirrors the codex arms: an authoritatively acknowledged native dispatch
  counts as committed; a live native intent surfaces as pending only while unsettled.
- `status`/`derive_states` surfaces a live native intent as `intent-created` instead of
  `ready` (a `ready` reading invited the exact double dispatch the acceptance harness caught).

## [0.105.0] - 2026-07-20

### Fixed - Outcome CLI retired-bundle surface (#624, PA-1 of #605)

- `outcome export`/`import` `--help` strings no longer describe the retired `outcome-bundle/1`
  flow: `export` is named a deprecated read-only alias of `discover`, `import` is named
  always-refusing with `discover`/`attach` migration guidance (#604 R10).
- Removed the unreachable success print after the unconditional `import_bundle` refusal — the
  top-level refusal receipt (`{"ok": false, "error": ...}`, exit 1) is the import arm's only
  output.
- `outcome import` now refuses without reading its path argument, so a missing or malformed
  bundle file yields the `#604 R10` migration guidance instead of an uncaught `FileNotFoundError`
  traceback or a bare JSON parse error.

### Security - Protected handoff-store directory (#624, PA-1 of #605)

- `outcome_compat._write_once` now creates missing handoff-store directories `0o700` and refuses
  a pre-existing handoffs directory that is a symlink, not owned by the effective uid, or not
  mode `0o700` — a fail-closed `handoff-store-unsafe` compatibility halt (`chmod 700` remedy in
  the receipt) instead of silently adopting a permissive directory. Sealed records stay `0o600`.
- The same refusal now also walks existing path components strictly below the user's home and
  rejects symlinked, world-writable, or uninspectable ancestors before any `mkdir` traverses
  them — the fleet-core `audit_store` guard, ported (never imported: this module is the frozen
  cross-runtime seam). Previously a symlinked intermediate parent was traversed silently and
  only the leaf directory was checked.
- `handoff-store-unsafe` receipts carry no absolute path, restoring the documented R12 invariant
  that callers may print a receipt verbatim; the remedy names the git-common-dir store instead.

## [0.104.0] - 2026-07-19

### Added - Fleet doctor cross-source audit (#353)

- `/fleet-doctor` command + skill + `fleet_doctor.py`: one strict, bounded, read-only
  point-in-time audit (`fleet_doctor_report.v1`) independently correlating Git worktree
  porcelain, the outcome worktree registries, the #356 broker registry (leases, fences,
  closed-owner admissions), the chain-verified #351 run-fact ledger (including #358 teardown
  facts), outcome dispatch commit events, and the durable delegation audit store.
- Three disease classes plus explicit evidence errors: `leaked-resource` (stale-worktree,
  dangling-registry, ownership-drift, terminal-resource-open), `unledgered-spawn`
  (observed/lease positions without spawn facts, phantom-spawn-fact, unsettled-spawn), and
  `receiptless-delegation` (claimed real execution without a schema-valid durable
  `bridge_receipt.v1`; corrupt evidence is an error, never absence).
- Exit contract fails closed: 0 complete+clean, 1 complete+findings, 2 incomplete proof
  (config error, corruption, unsafe path, broken chain, cap overflow, mid-scan source
  change). Caps never truncate to a false clean.
- Read-only by construction: no producer imports (AST-conformance-tested denylist), bytecode
  writing disabled, `os.open(O_RDONLY)` the only file-open, machine-local paths redacted
  behind `--show-local-paths`, and the machine-checked source matrix at
  `references/fleet-doctor-sources.md` fails the build when collectors and documentation
  drift. No `--fix`, `--reap`, `--retry`, `--watch`, or fixture surface exists.
- Hardened under the six-lens review ceremony: redaction now covers OS error text (errno
  and message only — never an absolute path) and neutralizes control characters in the text
  rendering; `os.open`/`os.scandir` failures fail closed to exit 2 instead of raising; a
  symlinked run-fact ledger is `unsafe-path`, never a clean "absent"; the receipt gate
  re-derives fleet-core's canonical `validate_receipt` verdict (conformance matrix covers
  optional-field and type-divergent corruption; one enumerated deliberate divergence — every
  non-string transport is rejected fail-closed where the canon accepts `null` and crashes on
  unhashables); the traversal depth cap is enforced;
  every declared cap carries a tripping oracle; and the run-facts source verdict is named
  `verified-prefix` (trailing whole-record truncation is undetectable by design and is now
  documented as such).
- Code-review remediations: the receiptless claim predicate covers the producer's full
  disposition partition (`substituted-engine`/`unproven`/etc. now demand receipts;
  conformance-pinned against `provenance_manifest.Disposition`; unknown dispositions warn),
  the lease registry gains the source entry cap and a linear spawn-correlation index, and
  dangling-registry existence checks no longer follow symlinks.

## [0.103.0] - 2026-07-18

### Added - Claude-side cross-runtime Outcome contract (#604)

- `outcome_compat.py`: the runtime-neutral compatibility seam — exact `github.com/<owner>/<repo>`
  repository identity from `remote.origin.url` (foreign host / credentialed / missing origin
  HALT), committed-spec discovery via git blobs with ref-ambiguity HALT, four closed
  `outcome.*.v1` schemas (duplicate-key / bool-as-int / unknown-field rejection, 256 KiB cap),
  narrow protocol negotiation with named required capabilities, deterministic serialization,
  and redacted `outcome.compatibility-halt.v1` receipts raised before any mutation.
- Canonical cross-clone reconstruction: `build_canonical_status` derives
  `outcome.canonical-status.v1` from exactly the committed spec blob + per-node GitHub
  contracts; unknown evidence reduces completion and candidacy, never fabricates; two clones
  serialize byte-identically; `mutation_allowed` is always false.
- Protected same-clone handoff: the sealed offer record is written INSIDE the #356 broker's
  settlement-close protected write (#355 linearization) so offering and relinquishing are one
  receipt-bearing transition; acceptance binds one receiver via write-once accept-intent, takes
  the successor through the close-receipt CAS, and appends the accept-commit; expiry, clock
  skew, tamper, wrong repo/revision/operation/subplot, settled attempts, and supersession all
  fail closed with distinct halt codes.
- `/outcome` verbs: `discover` (committed envelope), `handoff` (issuer offer under session
  admission), `attach` (read-only canonical status; `--advance` enters ONE one-subplot tick
  behind the validated handoff with revision + frontier re-checks; `--attend` derives the
  native resume command after validation); halts exit 3 with the closed receipt; a fleet-broker
  rejection (capacity, policy, registry) exits 1 with the standard structured error, never a
  bare traceback.
- Legacy `outcome-bundle/1` retired as an authority path (R10): `export` is a deprecated alias
  emitting the same `outcome.discovery.v1` bytes; `import` refuses every bundle with the exact
  `discover`/`attach` migration and writes nothing.
- Golden fixtures at `tests/fixtures/outcome-cross-runtime/v1/` (plus negative
  unknown-field/future-protocol fixtures) — the exact producer vocabulary the Codex consumer
  (infiquetra-codex-plugins#34) ports verbatim.
- Reference: `plugins/saga/references/outcome-cross-runtime.md`; outcome SKILL.md documents the
  new verb surface and the retirement.


## [0.102.0] - 2026-07-18

### Added - non-skippable team teardown and reclamation (#358)

- New `scripts/team_teardown.py`: the closed `run_fact.v1 kind=teardown` event family
  (`run-opened`, `teardown-intent`, `resource-attempt`, `resource-result`,
  `recovery-observation`, `teardown-complete`) with transition validation under the
  ledger's exclusive lock, stable action idempotency keys, and the derived
  `team_teardown.v1` projection over one chain-verified ledger snapshot plus one
  lock-consistent broker snapshot. No second registry, mutable status store, TTL clock, or
  reaper decision engine.
- The idempotent Step B8 terminal driver (`reclaim_all`): close owner admission, verified
  snapshot, crash-orphan reconcile (`already-absent` on the existing action key), typed
  actions, re-reconcile, still-closed generation recheck, and a `teardown-complete`
  receipt only at zero open resources. `request` records intent without acting; `recover`
  is a budgeted expired-only pass that always appends an observation, isolated per run —
  one run's refused pass (any exception family, the broker's included) records a
  `recovery-run-error` observation and never blocks recovery of newer runs. Budget and
  `actions_taken` evidence are counted at the source: `reclaim_all` reports each call's
  completed budgeted actions through a `ReclaimStats` object incremented inside the
  per-run reclaim lock and readable even when the call raises mid-flight — never
  inferred from before/after ledger snapshots, which could fail independently, diff
  against a fabricated baseline when the first read failed, and attribute a concurrent
  racer's results to the recovering pass. The only best-effort bookkeeping left is the
  observation append itself, which degrades to the run's in-memory pass entry
  (`evidence_error`) instead of aborting the batch. The action budget bounds real
  adapter invocations only — crash-orphan reconciles never increment the counter by
  construction — and the reconcile reason code stays driver-reserved:
  `ActionOutcome.validated()` refuses `recovered-after-crash` from the adapter surface
  so no adapter outcome can impersonate driver bookkeeping in the durable evidence. Concurrent physical B8 passes for one run serialize on an
  exclusive per-run reclaim lock so each logical action invokes its adapter exactly once,
  and a broker-evicted-then-re-closed admission generation replays the run's one recorded
  intent instead of poisoning the run (`close_generation` is not intent identity).
- Typed action adapters: terminal-receipt-gated resident release, exact-identity process
  stop (PID + process-start + boot + run ownership, TERM first, KILL only under the
  lease-recorded `term-then-kill` escalation, absence proof without signaling), the
  canonical #356 worktree sweep, and identity-checked provisional lease release. Every
  ambiguity fails safe as `retained`.
- `authorize_resident_stop`: only a #357 `confirmed-stalled` decision carrying
  `team-reping-confirmed` authority or an explicit segment shed, with current ownership,
  authorizes a resident stop intent.
- New `hooks/team_teardown_hook.py`: `SessionEnd` (5 s) records teardown requests for the
  trusted session's open runs; `SessionStart startup|resume` (15 s) runs one
  `recover --expired-only --max-actions 4` pass. Hook receipts are request evidence, never
  closure.
- `references/teardown-consumer-sites.md`: the source-aware run-open / register / driver /
  recovery inventory, enforced by the hermetic CI leak invariant
  (`tests/test_teardown_ci_invariant.py`).

## [0.101.0] - 2026-07-17

### Added - shared fleet liveness facts and adapters (#357)

- Added the closed `run_fact.v1 kind=liveness` subject/event family, lock-scoped idempotent
  transitions, cause-stable generations, atomic re-ping claims, and read-only decision projection.
- Preserved Outcome's exact heartbeat-first then absolute-timeout R31 authority while exposing phi
  suspicion only as additive evidence.
- Added hash-only SendMessage hook receipts that distinguish accepted, definitive-not-sent, and
  unresolved outcomes. Only accepted sends start response windows; #357 performs no teardown.

## [0.100.0] - 2026-07-17

### Added - orphan runner containment and receipt-chained evidence (#355)

- Registered dispatch and advisory-panel facts now use broker prepare/commit close receipts, and
  retries require the exact predecessor receipt for the stable execution resource.
- Team Execution manifest claims and adjudications use successor CAS, strict mirrored commit, and
  canonical receipt checks before a manifest may satisfy a gate.
- Added the read-only `reap_orphans.py scan` projector and the canonical/noncanonical evidence-write
  inventory.
- Raw and completeness manifest commands now write only the noncanonical namespace. Empty-artifact
  projection requires a matching bound output record and trusted template; malformed bindings are
  integrity evidence rather than empty-output claims.
- Advanced every Saga lease consumer to fleet-core protocol 2.

## [0.99.1] - 2026-07-17

### Fixed - lease-bound worktree teardown retains broker authority (#356)

- Refused authority-free reaping of registry entries carrying a worktree lease receipt. Generic ship
  teardown now treats every canonical `.saga-worktrees/<outcome>/<subplot>` path as managed: missing,
  corrupt, unreadable, or mismatched registry evidence retains the worktree with a retryable operator
  message instead of falling through to raw Git removal. Positively identified legacy unleased and
  unmanaged worktrees retain their existing teardown behavior.
- Made `/outcome prune` strictly prevalidate the exact receipt root, broker lease id, structured
  resource, fencing token, and managed path before mutating revision, nodes, edges, or generated issue
  state. Lease-bound pruning requires both the Git adapter and authority; the production CLI threads
  the canonical broker into that path.

## [0.99.0] - 2026-07-16

### Added - fleet-wide TTL lease admission and fencing (#356)

- Installed Agent/Task lifecycle hooks that reserve capacity before provider launch, bind trusted
  child identity on `SubagentStart`, require independent parent-return and child-terminal signals
  before foreground release, and fence delegated Bash and file mutations against the current live
  resource token.
- Added atomic Workflow wave reservation, prelaunch attestation, cooperative renewal, and exact
  owner release around the existing bounded concurrency policy. Generated leaves claim the named
  batch through the same installed hooks; a partial reservation never launches.
- Wrapped registered external-engine and production outcome dispatch paths in agent leases and
  carried redacted lease provenance into evidence. Missing or protocol-skewed fleet-core installs
  halt with install/update guidance instead of dispatching unleased.
- Bound outcome-owned worktrees to durable worktree-pool receipts. Reconcile renews live owners,
  adopts legacy live entries, reaps only expired dead or reboot-invalidated owners through Saga's
  canonical reaper, and retains ambiguous, escaping, mismatched, or failed resources for retry.
- Expanded the concurrency inventory into a machine-readable lease lifecycle map covering acquire,
  bind, renewal, and release. Conformance now rejects newly injected executable spawn calls without
  an inventory row and parses the installed hook metadata.
- Registered advisory-panel members now consume the caller's exact session admission and stable
  aggregate fence. A newer retry supersedes the entire stale panel before it can persist; both
  reconciliation facts append inside exact-token settlement. Engine post-run validation, integrity
  accounting, reconciliation, and fact persistence execute inside exact-token settlement; the CLI
  requires fencing credentials for renew/release and owner teardown accepts no caller-authored
  terminal assertion.
- Bound advisory second-opinion dispatches to their originating Saga session as well as its pinned
  admission policy, so per-session capacity remains authoritative across the external-engine path.
- **Compatibility:** the #433 `/outcome repost` verb and its `intent_revision` contract remain
  unchanged; leases enforce runtime admission without redefining operator posture or revision eras.

## [0.98.0] - 2026-07-16

### Added - dispatch settlement and casualty reconciliation (#351)

- Added a shared append-only settlement contract on the canonical run-fact ledger. Every dispatch
  records a manifest, a durable pre-call spawn, and one evidence-derived terminal classification;
  reports expose open positions and exact integer casualty thresholds without trusting agent
  self-reports.
- Added derived-on-read dead-letter and retry claims with stable idempotency keys. Retries increment
  attempts atomically, late deliveries remain explicit facts, and reconciliation never reaps,
  repairs, or mutates worktree state.
- Wired outcome dispatch and canonical GitHub harvest evidence into settlement. Workflow emission
  now publishes deterministic expected-unit metadata while the driving `/work` session remains the
  only ledger writer; generated agents receive no ledger or filesystem capability.
- Outcome settlement uses one complete ready-frontier cohort, binds every result to its exact
  attempt, reconciles already-canonical completions after crashes, and blocks new cohorts while an
  earlier cohort has missing evidence or unresolved casualties. Successful bounded retry clears the
  live gate without erasing the earlier casualty history.
- Added `dispatch_settlement.py` operations for manifests, spawns, settlements, late delivery,
  reports, dead-letter inspection, retry claims, and leak reconciliation. The public `settle` verb
  accepts only a descriptor for a persisted, schema-validated receipt, computes its digest from the
  actual bytes, and derives classification. Team artifacts expose only closed reviewer-result and
  validator-state payloads; Saga validates them and derives their deliverables instead of trusting a
  caller-authored output list. Exact manifest replay is idempotent; terminal views also have
  deterministic text output. This release does not change fan-out concurrency limits or introduce a
  background reaper.
- Retry thresholds use each attempt's own cohort, negative outcome terminals become retry-eligible,
  runtime requests carry their stable dispatch identity, and pre-submit spawn appends are synced to
  storage before the host call. Workflow drivers bind metadata to one persisted invocation identity
  and safely map legacy result names into the settlement vocabulary.
- **Compatibility:** the #433 `/outcome repost` verb and its `intent_revision` contract remain
  unchanged; settlement records the committed outcome dispatch without redefining operator posture.

## [0.97.0] - 2026-07-15

### Added - one bounded concurrency policy for Saga workflow fan-out (#350)

- Added the optional, closed `ExecutionSpec.concurrency` policy with fleet defaults of three normal,
  four explicit-read-only, and seven aggregate agents. Resolution now composes environment, shared
  fleet tier weights, exact external-engine lane limits, and an explicit run override without
  silently clamping invalid inputs.
- Dependency layers and refute-N panels now share stable ordered chunking. Panel verdicts retain
  their original order through concatenation, dependency barriers remain sequential, and emission
  fails when the conservative worker-width times verifier-width product exceeds the aggregate
  ceiling.
- External-engine registry variants may declare an optional positive `max_concurrent` lane limit.
  Exact-engine and capability selectors resolve to the selected registry lane before admission, so
  both forms share that lane's cap while ordinary units keep their own limit. The new source-aware
  concurrency inventory fails CI for unbounded executable fan-out sites or stale inventory rows
  while ignoring documentation-only examples.
- Workflow emission now rejects unsafe, reserved, generated-symbol-colliding, or runtime-global-
  shadowing unit identifiers, including iterate-to-consensus loop locals, and renders free-form
  comment text inert before producing executable JavaScript. The runtime-global boundary is
  reserved independently of current harness syntax. Conformance tests normalize whitespace and
  statically resolve constant f-string, concatenation, binding, and `.format()` fan-out emitters;
  unresolved formatted callee slots fail closed. Static raw delimiter assignments outside the sole
  framing helper also fail closed, so a local binding cannot hide an emitter from sink inspection.
  JavaScript block and line comments cannot hide a fan-out call, and AST checks prove governor-result
  dataflow through both chunk loops to emission. The runtime-global test oracle is independent of
  production and cross-checks Node `globalThis`.
- Unattended tier-climb retries now render the prompt contract for the climbed tier while retaining
  the unit's frozen exact engine route. A cheap-to-non-cheap retry therefore drops the budget and
  pull-cord riders and emits the non-cheap return schema expected by its gate.
- **Compatibility:** capability-routed `recompile_for_tier(..., "cc-workflows-ultracode")` now
  requires the authoritative `repo_root=` used for overlay and calibration loading. Exact-engine
  workflow recompilation and non-workflow tiers retain the existing two-argument call.
- **Compatibility:** the #433 `/outcome repost` verb and its `intent_revision` contract remain
  unchanged; bounded admission affects emitted workflow fan-out only.

## [0.96.0] - 2026-07-14

### Added - envelope-authorized merge: the `AUTONOMOUS_UNDER_ENVELOPE` write class (#449)

- **`scripts/envelope_token.py` — the revocable merge-authorization credential.** A durable,
  expiring token (closed exact-keys schema v1, merge-only scope) bound to one outcome AND one
  exact committed envelope era: content fingerprint (`sha256:` of the canonical envelope JSON)
  plus `intent_revision` — a #433 repost, or even an A→B→A posture round trip, ends the era and
  the token stops authorizing. Status is derived on every read (active / expired / revoked /
  malformed), never cached: `check_token` re-reads the token file AND the write-once revocation
  marker per call, so `revoke` is effective on the very next authorization attempt (R4; the
  honest freshness bound: a revocation cannot recall a single already-in-flight GitHub call —
  every write after it GATEs). `resolve_merge_token` requires EXACTLY one active matching
  token (ambiguity GATEs; a malformed document fails the whole lane closed). Operator CLI:
  `mint` (refuses an envelope-less spec, any non-`merge: "auto"` posture, and the reserved
  `.revoked` id suffix that would collide with a sibling's revocation-marker file — the write
  seam enforces what the read seam enforces) / `revoke` / `check` / `list`. Threat model documented in-module: minting
  is SELF-ATTESTED (local-filesystem trust boundary, same as every store artifact); the token
  adds expiry, immediate revocation, era binding, and attribution — it does not authenticate
  the minter. Gate records (#371) are deliberately not consulted in v1; an attended
  mint-from-gate-answer flow is the issuance companion (classify with `is_operator_answerer`).
- **`scripts/reversibility_certificate.py` — `Tier.AUTONOMOUS_UNDER_ENVELOPE` +
  `OpKind.MERGE_UNDER_ENVELOPE`, inert without a token (R1).** Plain `authorize_write` GATEs
  the new class unconditionally and gained NO token parameter (R2 — zero regression for every
  existing caller; bare `merge`/`deploy` stay absent, R20 untouched). The new pure sibling
  `authorize_write_under_envelope(op_kind, token_check, *, other_gates_green)` AUTHORIZEs only
  a fresh valid token check AND an explicit all-other-gates-green attestation (necessary but
  not sufficient, AC2); it can never widen a non-envelope op, and wrong-TYPED attestations
  raise rather than coerce. The composed I/O surface is
  `envelope_token.authorize_merge_under_envelope` (fresh disk reads at authorization time, R3).
- **`scripts/outcome_merge.py` — the merge queue now CONSUMES `ceremony_gates.merge` (the #433
  "recorded posture with no engine consumer" honesty note is closed).** Every GitHub WRITE the
  queue can perform — `update_branch` (rebase) and `squash_merge` — is ceremony-gated, fresh
  per attempt: committed `merge: "auto"` posture AND one active envelope token, or the leaf
  records `waits-operator` with a precise, operator-actionable reason. **Behavior change,
  deliberate (fail closed):** the pre-#449 tokenless auto-merge default is GONE — an
  envelope-less campaign, a `merge: "gate"` posture, and a token-less `merge: "auto"` posture
  all wait for the operator's keystroke. Read-only classification (dirty→conflict,
  blocked/unknown→defer) still runs for every campaign, so conflict recording and /work
  re-engagement never depend on merge authority. Revocation mid-tick stops the very next
  squash, including a later leaf in the same tick. `production_merge_processor(repo_root=...)`
  reads the ON-DISK committed intent per authorization so a mid-tick repost's tightened posture
  is honored within the tick; direct callers without a reader fall back to the tick's in-memory
  posture (residual documented in the module docstring, not claimed away).
- **`scripts/board_progression.py` — board-sync ledger attribution (R5).**
  `record_envelope_authorized_merge` writes two write-once phases per merge —
  `authorized` BEFORE the squash (a merge that cannot be pre-attributed is NOT performed) and
  `merged` after — both carrying `authorizing_envelope_id` + `token_id`, keyed
  `merge-under-envelope:{outcome}:{subplot}:{pr}:{phase}:{token_id}`: the token era coordinate
  means a stale `authorized` record from a dead envelope era (a capped or gated-later attempt)
  never stands as — or write-once-suppresses — the pre-attribution of a merge performed under
  a later era, so both phases of one merge always name the same token. Non-merge ledger
  records are untouched (the field is merge-record-specific). A crash between squash and the
  `merged` record loses only that record and is never backfilled — post-hoc attribution would
  assert a pre-merge authorization nobody re-verified (documented honest bound).
- **Reference:** `references/envelope-token.md` — token contract, era binding, threat model,
  honest bounds, and the enforcement matrix. `references/gate-record.md` consumer item 4 and
  `references/intent-envelope.md` forward notes updated to what actually landed;
  `skills/outcome/SKILL.md`'s "Never autonomous" section now names the single scoped,
  revocable, attributed exception (default stays GATE — intake §3 revisit engaged by #449).

## [0.95.0] - 2026-07-14

### Added - gates as durable approval records with a linted operator-absence contract (#371)

- **`scripts/gate_record.py` — a gate is a record, not an `AskUserQuestion` call:** question,
  options, machine-readable `absence_behavior` (`HALT` / `safe-default-with-record` / `escalate`,
  default `HALT` per the fleet's HALT-not-degrade posture), answer, answerer, timestamps, and
  transport, persisted BEFORE any transport is invoked under `.saga/gates/<gate_id>/`. Storage is
  derived-on-read with write-once commits (`os.link` declaration + resolution, append-only absence
  audit that records repeat silence rather than deduplicating it): a restarted session resumes the
  same pending record (`open` on an identical declaration; a mismatch errors), status is never
  held in memory, and of two concurrent satisfies exactly one wins. `poll` never returns a
  consumable answer for a silent gate; `resolve-absent` applies the DECLARED behavior only — the
  caller cannot pick one at resolution time — so silence never resolves to an implicit yes.
- **Pluggable transports, `AskUserQuestion` demoted:** `ask-user-question` (push — the session
  relays the widget answer via `satisfy`) and `file-sentinel` (pull — `poll` ingests a dropped
  `answer.json` through the SAME satisfy path) share one schema and one validation path; a
  sentinel dropped for a push gate is a transport-mismatch error, a malformed sentinel is
  surfaced, never skipped. Late live answers over `redis-channel`/`discord` are accepted with the
  real arrival transport recorded (the escalate flow).
- **Operator-absence contract (binding on #449): derived provenance is not operator presence.**
  `satisfy` rejects reserved-prefix answerers (`carried-forward:` — the #433 tightening-repost
  approval provenance, drift-guarded against the production literal — and `absence:`) in both
  directions of the seam; `classify_answerer` / `is_operator_answerer` are the exported
  predicates for forward consumers. The #598 item-2 set-intent/repost carry-forward asymmetry is
  deliberately COMPOSED WITH (presence-conservative), not closed — rationale in
  `references/gate-record.md`. The closed `binding` vocabulary (`outcome_id` / `saga_id` /
  `leaf_id` / `spec_revision` / `intent_revision`) gives #449 dispatch-era binding, filterable
  via `gate_record.py list --binding`.
- **`scripts/lint_gate_absence_contract.py` + CI wiring:** "we forgot to say what silence means"
  is now a build failure for new sections and files. Every `AskUserQuestion` mention in scanned
  markdown must sit in a
  section carrying a `<!-- gate-record: id=... absence=... transport=... -->` or
  `<!-- gate-exempt: ... -->` marker (malformed markers fail closed); coverage granularity is
  the section, so an addition beside an existing marker rides it (named in the lint's
  residuals); every Python `open_gate`
  call must declare a literal in-vocabulary `absence_behavior` (the defining module is excluded
  by documented rule and reported). Legacy debt is pinned exact-count in
  `scripts/gate_absence_baseline.json` — surfaced as `pending migration (applied: false)`,
  shrink-only, any drift fails.
- **Six gate sites migrated** (`brainstorm`, `code-review`, `founder-review`, `ideate`,
  `investigate`, `loop`): each declares gate-record markers (ids aligned with the #399
  gate-divergence `gate_id` vocabulary) and instructs open-before-ask / satisfy-after /
  resolve-absent-on-silence, reading decisions from the persisted record, never the widget's raw
  return. `engine_dispatch.satisfy_gate()` (the external-engine gate precedent) is untouched.
- **`references/gate-record.md`:** the full contract — schema, absence semantics, transport seam,
  the operator-presence position, enumerated consumers per record phase, honest bounds
  (self-attested answerer seams; the #597 report-tier kind-filter bug deliberately NOT inherited —
  gate records stay out of the consolidated report until that filter is fixed).

## [0.94.0] - 2026-07-14

### Added - mid-run posture renegotiation: the /outcome `repost`/set_intent verb (#433)

- **`scripts/outcome_intent.py` + `outcome.py repost <id> [--scope <subplot>] --set FIELD=VALUE
  --reason <why>`:** the ONE verb that changes a LIVE campaign's posture mid-run — the
  renegotiation `set-intent` explicitly reserved for #433. Reuses the existing vocabularies
  (campaign posture = the #380 intent envelope's `run_mode` + `ceremony_gates`; node posture =
  the existing `degrade_policy`/`sandbox` fields) and the existing atomic mutation shape:
  snapshot → validate → `bump_revision` → one structured `decision_trail` entry. A rejected
  repost (unknown field, off-vocabulary value, wrong value TYPE, no-op value, monotonic
  violation, strand) leaves `spec_revision`, `decision_trail`, and every posture field
  byte-identical (R2, the R26 invariant). Never touches DAG structure.
- **`intent_revision` dispatch-time overlap (R4/R5):** every accepted repost tags the spec with
  `intent_revision` (the revision it introduced; absent key = the run-start baseline, so every
  pre-existing spec round-trips byte-identical). Each leaf's dispatch records — the
  pre-dispatch `intent` record AND the settled `commit` record, so a leaf stranded in the
  crash-after-intent window still carries its era — capture
  the `intent_revision` + posture snapshot active at its dispatch — including the campaign
  envelope itself (`posture.intent`; `null` = explicitly dispatched envelope-less) — and
  `DispatchRequest` carries `intent_revision` to the backend. An in-flight leaf finishes under
  its dispatch-time posture at BOTH ends of the flight: `outcome_orchestrator.harvest` and
  `barrier_report` evaluate an in-flight leaf's intent-implied closure checks (e.g.
  `code-review` under `reviews_required: "gate"`) against its dispatch-era envelope, so a
  loosening repost never retroactively releases an in-flight completion gate and a tightening
  never retroactively imposes one; a pending leaf picks the new posture up at its next
  dispatch. `set-intent` (first attach) tags `intent_revision` too.
- **A committed repost survives a concurrent advance tick:** `save_spec` is now
  compare-and-swap on the load-time revision (`OutcomeSpec.loaded_revision`, runtime-only) —
  a save built on a superseded spec raises the new typed `StaleSpecError` instead of silently
  reverting the repost's revision bump, envelope change, and trail entry. The production cost
  processor (the one spec-persisting seam in the advance path) reloads-and-reapplies on top of
  the newer revision, loudly (`reapplied_over_stale_revision` in the tick's cost record); the
  reconcile loop re-checks the on-disk revision at every tick boundary AND per leaf after the
  dispatch lock, stopping a stale pass before it can dispatch under a revoked posture
  (`AdvanceResult.spec_reloads` reports each reload). The precisely-bounded sub-windows that
  remain — the dispatch-side interleave AND `save_spec`'s own lockless check→write gap (a
  writer landing inside it is still silently overwritten) — are documented in
  `references/outcome-spec.md`, not claimed away.
- **Strand HALT (R6):** a repost scoped to a `destructive` leaf that is in flight — where "in
  flight" fail-closed includes a bare intent-phase dispatch record (the mid-dispatch TOCTOU
  window) — and that would TIGHTEN its sandbox (revoking irreversible-op authorization the
  leaf already carries) HALTs the campaign instead of resolving silently in either direction:
  the amendment is rejected (spec untouched), ONE `coordinator`-writer `andon_halt` lands in
  the #372 adjustment envelope append-once on `(writer, scope)`
  (`adjustment_envelope.raise_strand_halt` is the new fifth writer; the next advance tick
  stops dispatching), and ONE durable `phase: halt / kind: repost` ledger record — append-once
  on `(phase, key)`, the reconcile-halt-path parity — names the stranded leaf. Repeats
  re-raise, never duplicate.
- **Monotonic merge/deploy gating (R7):** `ceremony_gates.merge` / `deploy_nonprod` may only
  move toward MORE gating (`auto` → `gate`); any repost relaxing either from gated toward
  autonomous is rejected outright — including against a campaign with no committed envelope
  (effective gates default to `gate`), and equally through the sibling `set-intent` verb: a
  first attach on a LIVE campaign (any dispatch record) passes the SAME monotonic validation
  (`outcome_intent.validate_live_attach`), and every accepted attach writes a `set-intent`
  decision-trail entry with classified deltas — one rule, one trail, no second-verb side door
  (AC5). Pre-dispatch attaches keep the #380 interview-fallback contract (any posture).
  One-directional by design; loosening takes a new campaign. Consumer honesty: `merge` /
  `deploy_nonprod` are recorded posture with no engine consumer yet (only `reviews_required`
  is consumed, via the implied closure checks) — the #449 token-checked write class is the
  consumer this integrity guarantee is held for.
- **Approval interplay (R3):** every repost bumps `spec_revision`, so the revision-keyed R20
  frontier approval re-closes automatically on a loosening repost (affected leaves stay gated
  until re-approval); a PURE-tightening repost carries an existing approval forward with
  explicit `carried-forward:tightening-repost:r<old>` provenance — tightening never re-asks a
  settled approval.
- **HALT as a renegotiation point (R8/R9):** a gate HALT carries a `scoped_repose` option on
  its `HaltReceipt` ONLY where the offered verb can actually resolve it — the guarantee class
  when the guarantee is borne by the leaf's own `degrade_policy: "halt"` (a scoped
  `repost --set degrade_policy=operator_away_one_rung` lifts it). Attending halts (the
  operator is present; no repost value changes `attending`), `guarantee_tags`-borne
  guarantees (spec-authored, not a repost axis), destructive/side-effected halts
  (HALT-not-degrade by design), and availability halts are honestly offer-less. The option is
  an offer, not a mechanism that acts: the leaf stays halted, re-derived every tick, until the
  operator explicitly selects — no default, no timeout, silence is never consent. Composes
  with, never overrides, HALT-not-degrade.
- **Scope note (re #594 R2):** #372's standalone `re-tier`/`add-reviewer` envelope amendments
  are still surfaced with `applied: false` — routing them through this overlap machinery so
  `applied` can become true remains the #594 follow-up; tier is not a #433 posture axis.
- **Tests:** `tests/test_outcome_intent.py` — rejected-repost-untouched (byte-identical, engine
  + CLI), loosening-repost-recloses-approval + tightening-carries-forward control,
  dispatch-time-posture-overlap, amendment-strands-irreversible-op-halts (+ non-destructive /
  not-in-flight / terminal-flight controls), merge-deploy-gate-monotonic (+ no-envelope
  baseline), live-set-intent-attach-monotonic (+ pre-dispatch interview-fallback control +
  mid-dispatch-intent-record-counts-as-live), midtick-repost-survives-cost-processor-save
  (+ save_spec-refuses-to-clobber baseline control), stale-spec-mid-pass-stops-dispatch,
  strand-check-sees-mid-dispatch-intent-record, repeated-stranded-repost-appends-once
  (+ different-scope control), reviews_required-overlap-gates-in-flight-completion (+
  tightening-never-retroactively-imposes control), scoped-repose-no-timeout-default (+
  availability-halt / attending-halt / guarantee-tag-halt controls), intent_revision
  round-trip fail-closed, and a release-surface drift guard tying plugin.json ↔ CHANGELOG ↔
  documented verb; `tests/test_outcome_command.py` — set-intent trail entry + live CLI
  rejection parity.

## [0.93.0] - 2026-07-14

### Added - run-start intent envelope enforced at the /outcome dispatch seam (#373)

- **Captured backend/degrade posture consumed at the seam (T8-F6-8):** the committed intent
  envelope's new optional `backends_permitted` + `degrade_policy` fields are enforced inside
  every `advance` reconcile pass (`outcome._reconcile_once` via the new
  `outcome_dispatcher.captured_posture` / `effective_available` / `captured_degrade_decision`
  consumers). The effective backend menu is captured ∩ runtime (`--host-capable` /
  `--workflow-available` stay the runtime half — KTD9); an unmet backend HALTs by default
  (no captured degrade posture is never a permission), and `operator_away_one_rung` feeds the
  UNCHANGED presence-conditional `degrade_decision` an availability set restricted to the
  immediate `DEGRADE_LADDER` rung — at most one rung, a two-rung-unavailable scenario HALTs
  instead of silently cascading. Specs with no intent, or a #380 intent carrying none of the
  #373 fields, behave byte-identically to before.
- **HALT-only pre-dispatch spend authorization (T8-F5-7):** a captured
  `spend_envelope` (`tier_ceiling` from the fleet model ladder and/or `cost_ceiling_tokens`)
  is checked BEFORE any backend resolution against `outcome_costs`'s leaf-produced actuals
  (the same R24 rollup producer `materialize` uses, read pre-dispatch). Dispatch is authorized
  while actuals stay strictly below the cost ceiling; an at/over-ceiling or tier-escalating
  leaf raises the new typed `outcome_dispatcher.SpendHaltError` (deliberately NOT a
  `BackendHaltError` subclass) and records a visible `spend-halt` receipt in `result.halted`
  on its own append-once `spend:<sid>` ledger lane — never a silent degrade to a cheaper
  tier. Actuals are leaf-produced and self-attested (documented in the envelope threat model).
- **`Node.tier` (optional):** a leaf's declared execution tier — a model name validated
  against the fleet ladder at spec-validate time (a typo fails before any dispatch) — read by
  the tier-ceiling gate; absent emits no key so every pre-existing spec round-trips
  byte-identical. `OutcomeSpec.validate` also binds the intent's `backends_permitted` to the
  `NODE_BACKENDS` executor menu (the fleet schema owns shape; the spec house owns vocabulary).
- `intent_envelope.py` (saga glue) re-exports the new canonical names: `SpendEnvelope`,
  `SpendAuthorization`, `authorize_spend`, `INTENT_DEGRADE_POLICIES`, `SPEND_ENVELOPE_FIELDS`.
  The capture surface is unchanged (`start --intent-file` / issue-carried / `set-intent`) —
  the run-start envelope simply gained the three optional fields; no new interview questions
  (an interactive authoring flow stays a fast-follow, per the issue's out-of-scope).

## [0.92.0] - 2026-07-14

### Added - mid-run adjustment envelope + reversible-mutation undo ledger (#372)

- **`references/adjustment-envelope.md` + `scripts/adjustment_envelope.py`:** one documented,
  versioned (`ENVELOPE_VERSION = 1`) control-file schema — the mid-run counterpart to the
  run-start intent envelope — polled at the existing `/outcome` tick boundary and the `/work`
  segment boundary (no new poll loop). Four writers converge on ONE file: an operator-raised
  `quiesce` (drain in-flight, dispatch nothing new, surface a resume point), plan-declared
  `pause_after: <segment>` points (deterministic halt + explicit-continue resume, honoring a
  `resume_tier`/`resume_context` change), a worker/reviewer-raised `andon_halt`, and operator
  `re-tier`/`add-reviewer`/`cancel`/`abort` directives. Poll precedence `halt > drain > pause >
  proceed` composes with — never weakens — the existing HALT-not-degrade stance
  (`{#outcome-backend-degrade-stance}`).
- **Fail-closed parser (R3):** an unknown directive, unknown key, missing required field, wrong
  version, unrecognized writer, or malformed/unreadable file raises `EnvelopeError` and HALTs the
  run naming the offending token — never an enumerate-and-skip silent proceed. An absent file
  means "no directives, proceed".
- **`scripts/outcome.py` `advance`:** polls the envelope each tick after the in-flight harvest
  drains and before dispatch; a halting/draining/pausing decision (or a fail-closed error) stops
  the next tick from dispatching and is surfaced on the new `AdvanceResult.adjustment` field
  (producer + consumer ship together — no dead wiring).
- **`scripts/undo_ledger.py` + `/undo` command (`commands/undo.md`):** the reversible-mutation
  default (R6/R10/R11) — registered reversible ops (`board_move`, `label_change`, `issue_edit`,
  `saga_branch`, `saga_pr`) proceed under act-log-inverse-notify (write a proven round-trip
  inverse, notify the operator) instead of pausing; `/undo` replays the inverse (LIFO). An op with
  no registered inverse is definitionally irreversible and falls back to the gated pause
  (`mutation_disposition` returns `"pause"`). Deliberately gh-free (computes/records inverses; the
  mutation-owning subsystem replays them) so the gh write-ownership lane stays intact.
- **Tests:** `tests/test_adjustment_envelope.py` (quiesce-drain, pause-after boundary,
  pause-context/model-change, andon-blocks-next-wave, unknown-directive fail-closed — driving the
  production `advance` wiring) and `tests/test_undo_ledger.py` (per-op round-trip inverse,
  no-inverse-falls-back-to-pause). Envelope + ledger live under the git-ignored `.saga/` run state.
## [0.91.0] - 2026-07-14

### Added - one level-triggered reconcile controller for /work and /loop (#450)

- **`plugins/saga/scripts/reconcile_controller.py`** (new): the ONE Kubernetes-style
  level-triggered board-reconcile controller. Composes the extracted idempotency-key write
  mechanism (`board_progression.authorize_and_write`, #344) with a per-op **level-triggered drift
  check** — every tick it recomputes the expected board value from durable saga fields and re-reads
  the live board. A rapid double tick converges on exactly one applied write and one ledger entry
  (`reconcile_op` → `authorize_and_write` on an absent key, no-op on a present one); an outside edit
  to the saga-owned Status field made while a command was at rest is re-detected and **corrected**
  (`{"status":"corrected"}`); an irreversible outside open/closed change, or any certificate-GATE op,
  **HALTs** with a named `halt_reason` and never overwrites. Fail-closed and doubly gated:
  auto-correction fires only when `reversibility_certificate` returns `AUTHORIZED` AND the op is in
  the explicit `AUTO_CORRECT_OP_KINDS` allowlist (today exactly `set-field-status`). Ships a
  `reconcile` CLI (`--no-drift-check` for a write-only tick) so the markdown skills can invoke it.
- **`plugins/saga/scripts/outcome_reconcile.py`**: the drift vocabulary + record shape
  (`DRIFT_KINDS`, `_drift_record`, `_drift_id`, `_close_satisfies_contract`) is now single-sourced in
  `reconcile_controller` and re-exported here — zero behavior change to `/outcome`'s detect/decide
  call sites (regression-tested; the existing `test_outcome_reconcile` / `test_outcome_board_sync`
  suites stay green).
- **`plugins/saga/skills/work/SKILL.md`** (§4.4): post-merge board moves now route through
  `reconcile_controller.py reconcile` instead of the raw `board_progression.py write`, gaining the
  outside-drift detection `/work` previously lacked.
- **`plugins/saga/skills/loop/SKILL.md`** (§0.5): `/loop` gains a level-triggered reconcile tick over
  the already-asserted, allowlisted Status field (refining the #344 boundary) — it reconciles drift over
  already-asserted fields; the no-new-forward-progression boundary is documented convention
  enforced by the skill's instructions, not (yet) mechanically by the controller.

## [0.90.0] - 2026-07-14

### Added - one committed IntentEnvelope for run-start posture (#380)

- **`outcome.py set-intent <id> --intent-file <envelope.json>`** — attaches an
  interview-captured envelope to an ALREADY-started outcome (`start` is non-idempotent, so the
  post-start interview needs its own landing verb). Validates exactly like
  `start --intent-file`, refuses to overwrite a committed envelope (mid-run renegotiation is
  #433's contract), bumps `spec_revision`.
- **`barrier_report` enforcement/observability parity** — the operator-facing report now
  evaluates the closure gate with the SAME intent-implied checks `harvest()` enforces, so a
  merged-but-review-gated leaf never reads "satisfied" in the cockpit while its done
  transition is actually gated.
- **`scripts/intent_envelope.py`** — saga's surface over the canonical fleet envelope
  (fleet-core `fleet_commons/intent_envelope.py`, re-exported exactly as `execution_spec.py`
  re-exports `tier_palette` — never a second schema), plus the saga-only glue:
  `compute_stakes` (parallel width + unit-weight `critical_path_wall` critical-path depth, the
  data-backed interview numbers), `implied_required_checks` (the `reviews_required` consumer),
  `seeded_tier` (per-unit tier defaults from the committed posture), and the CLI
  (`interview` / `capture` / `from-issue` / `recommend` / `spend`). Contract doc:
  `references/intent-envelope.md`.
- **`OutcomeSpec.intent`** and **`ExecutionSpec.intent`** — the committed run-start envelope,
  schema-validated in `validate()` (fail closed on off-vocabulary values / unknown keys);
  absent emits no key so every pre-existing spec round-trips byte-identical.
- **`/outcome start` reads the issue-carried envelope** (S-22): `start --from-objective` now
  fetches the parent Objective's body, and a valid `intent-envelope` block skips the run-start
  interview (ask-once — the operator already answered at issue capture); absent or invalid
  falls back to the interview with the reason surfaced (an invalid envelope is never adopted).
  New `start --intent-file <envelope.json>` commits an interview-captured envelope; the start
  output reports `intent_source` / `interview_required` / `interview_reason`.
  `nodes_from_objective` now returns `(nodes, dropped, title, parent_body)`.
- **`reviews_required` gates a leaf `done` transition** (T8-F1-3): when the committed intent
  declares `ceremony_gates.reviews_required: "gate"`, `outcome_orchestrator.harvest` implies a
  `code-review` closure check on every code leaf — a merged-but-unreviewed leaf stays undone
  until `code-review` evidence is recorded at the close SHA (`closure_gate.evaluate` grew an
  `implied_checks` parameter; empty = byte-identical behavior). Specs without an intent are
  unchanged.
- **Single-asker rule, drift-guarded** (G-negative-space-1): no saga skill or script defines a
  run-start posture question outside the envelope registry; `tests/test_intent_envelope.py`'s
  fleet drift guard (with baseline red controls) enforces it. `/plan` Step 1 seeds its tier
  table defaults via `seeded_tier`; `/work` resolves between-rounds spend decisions through
  `intent_envelope.py spend` (attended increases need an explicit approval token —
  `PostureError` otherwise; unattended holds cache-tight silently).

## [0.89.1] - 2026-07-14

### Changed - docs-only: corrected the stale `sandbox-spawn-sites.md` out-of-scope wording (#422)

- **`references/sandbox-spawn-sites.md`** out-of-scope table, team-execution row: the old text
  claimed team-execution runs "with no per-leaf tool-restriction consumer", which contradicts the
  corrected #422 record (`docs/engineering-journal/DECISIONS.md` KTD4, team-execution CHANGELOG
  2.14.6): the authored `tools:` frontmatter IS the spawn-time capability roster a dispatcher
  reads to scope a leaf, and `tools/agent_spec.py`'s tool-scope floor CI-lints it. The row now
  says precisely what is out of scope — routing team-execution through saga's
  `mutation_policy`/`workspace_isolation` sandbox mechanism — not the existence or consumption
  of `tools:` rosters. No code, schema, command, or hook changes.

## [0.89.0] - 2026-07-13

### Added - /pulse live fleet-telemetry surface (#400)

- **`plugins/saga/scripts/pulse.py` + `skills/pulse/SKILL.md` + `commands/pulse.md`:** a
  strictly read-only live-telemetry surface rendering four panels from REAL signals only —
  board state through mission-control's own `sdlc_manager.py --format json board view` read
  path (subprocess, runner-injectable, `--sdlc-manager` override), agent/run state derived on
  read from the saga tick history (`saga.scan`/`read_ticks`, projecting exactly the scanner's
  fields — no pulse-owned status field anywhere), the hash-chained run-fact ledger via its own
  reducers (`rollup`/`reuse_ratio`, chain verdict always shown), and outcome economics via
  `outcome_costs.rollup` over the newest `docs/outcomes/*/outcome-spec.json`. Every panel is
  tri-state `ok` / `no-data` / `unavailable` (ledger adds `chain-broken`): an absent or empty
  source renders an explicit "no data yet" / "unavailable (<reason>)" label — never a silent
  zero — and a broken hash chain suppresses every aggregate and renders the break banner
  instead. No hardcoded judgment thresholds (numbers cited, operator judges), no experiment
  primitives (the bounded target/baseline/budget loop stays `/optimize`'s — settled boundary,
  no programmatic feed), zero writes (byte-hash-enforced by test). `--watch` is a bounded
  refresh loop (`--iterations` required), not a daemon. Human render reuses the `status_card`
  summary-projection card; `--json` emits `pulse_snapshot.v1`. Manual drive-a-run recipe in
  `skills/pulse/references/manual-verification.md`; the automated end-to-end proof is
  `tests/test_pulse_telemetry.py::test_drives_real_run_and_surface_updates`.
## [0.88.0] - 2026-07-13

### Added - Earned ratings: dispatch/benchmark evidence drives retro-gated registry calibration (#459)

One evidence-to-proposal pipeline over the hash-chained run-fact ledger. The non-negotiable seam
everywhere: nothing edits `engine-registry.yaml` autonomously — every signal terminates in a
`registry_calibration_proposal.v1` a human applies via `/retro`
({#external-engines-never-gatekeepers}, #283).

- **Dispatch-fact registry-cell join fields (R1):** `engine_resolver.Resolution` gains additive
  `capability` / `rating_claimed` (stamped AT RESOLUTION TIME, so ledger joins stay
  self-contained history), and `engine_dispatch._record_advisory_facts` stamps
  `capability` / `rating_claimed` / `execution_id` onto every `engine` run fact. The run-fact
  ledger (`run_ledger.py`, already append-only + hash-chained with `verify_chain`) gains a sixth
  `benchmark` fact kind. AE1's mutation/deletion chain-verification is proven through the real
  dispatch write path in `tests/test_engine_dispatch_ledger.py`.
- **Panel-member attribution (R4 substrate):** `reconcile.append_reconciliation_fact` accepts an
  optional, validated `member_index` (`{source_finding_id: [engine_key, ...]}`);
  `dispatch_advisory_panel` records it on both RECONCILE and APPLY facts. Legacy facts without it
  stay valid; it never enters `canonical_result_hash`.
- **`engine_benchmark.py` + `references/benchmark-suite.yaml` + `references/benchmark-loop.md`
  (R2):** an ACTIVE fixed-suite harness (operator-invoked, deterministic string graders only —
  never LLM-judged) measuring a registry claim; a measured-vs-claimed contradiction emits a
  proposal cell, never a write. Suites are versioned by immutable `suite_id`.
- **`engine_stale_report.py` (R3):** per-(engine, capability) staleness verdicts —
  `corroborated` / `contradicted` / `unexercised` — joining ledger evidence strictly newer than
  each row's `last_validated`. Chain break RAISES; empty ledger reports "no dispatch evidence
  yet", never a fabricated verdict.
- **`capability_elo.py` (R4):** derive-on-read Elo per (engine, capability) folded from live
  reconciliation win/loss outcomes (head-to-head `member_index` evidence only; solo
  reconciliations produce no match; unmapped intents are skipped and counted). No persisted score
  file. Divergences only ever propose `revalidate` — never a rating value.
- **`provider_control_chart.py` (R5):** XmR control charts (rule 1 beyond-limit, rule 4
  run-of-8) over per-provider cost/latency series; thin series are `no-data`, zero metric values
  are excluded as unmeasured. Drift flags deprioritize at resolution time — never exclude — and
  surface as `revalidate` proposals. Distinct signal from R3 staleness by design.
- **`engine_calibration.py` + `/retro` Phase 1.11 / Phase 5(f) (R6):** the aggregator mirrors
  `tier_efficacy.py` — `report` emits `registry_calibration_proposal.v1` (benchmark contradiction
  -> rating-change; contradicted/Elo/SPC -> revalidate; corroborated -> last-validated-bump;
  zero data -> `no-proposal`), `render_diff_preview` reads the YAML read-only, and
  `approval_required` is always true. `/retro` gains the read-only Phase 1.11 evidence pass and
  the Phase 5(f) propose-diff-and-wait pass; the pass never writes the registry
  (byte-identity guarded by `tests/test_saga_retro_calibration.py`).
- **Opt-in runtime consumption (R4/R5):** `Registry.ranked_candidates` / `explain_capability` /
  `engine_resolver.resolve` accept a duck-typed `calibration` signals object
  (`CalibrationSignals`: Elo map + drift flags) that reorders WITHIN an authored rating band only
  (deprioritize, never exclude; overlay pins still win; `RunMemo` keys carry a calibration
  fingerprint). `calibration=None` — the default everywhere — is byte-identical to before.
  Committed consumer: `engines route explain <capability> --calibration`.

## [0.87.0] - 2026-07-13

### Fixed - HTTP-bridge lanes corroborate receipt-only instead of structurally failing (#524)

- **`plugins/saga/scripts/engine_dispatch.py`:** two-signal dispatch through an HTTP-transport
  lane (ollama-cloud, deepseek — any `via: engine-bridge-http` registry row) no longer discards
  honest ok output as a `DELEGATION_INTEGRITY` divergence. `fleet_commons.delegation_audit`'s
  `ENGINE_CONFIGS` has no row for HTTP engines (they write no `runs/` bundle directory), so
  `corroborate()` raised `UnknownEngineError` and the observer answered NO on every HTTP
  dispatch that supplied `workspace_root` — the exact discard observed in the #468 drill
  (narrative OBS-1). HTTP lanes now corroborate receipt-only (`_http_receipt_corroborates`):
  the bridge's `bridge_receipt.v1` is the observer artifact, and observer-yes requires the
  full receipt schema (proof extensions included), the `http-bridge` signature policy, the
  output attestation binding the receipt to the ACTUAL returned output, and engine/variant/
  transport identity matching the resolution. A receipt attesting different bytes than the
  returned output, a missing or zero-token receipt, or an identity mismatch is still
  observer-NO and still trips the KTD7 requeue-once-then-HALT tripwire. The lane is keyed
  off the registry-built invocation's `transport`, never the runner-controlled receipt's own
  claim; the agy/codex bundle-corroboration path is byte-identical (issue non-goal).

## [0.86.0] - 2026-07-13

### Fixed - delegation tripwires hardening: durable requeue counter, skew-safe dispatch imports (#520; #384 review F1/F5)

- **`plugins/saga/scripts/engine_dispatch.py`:** the KTD7 re-queue-once-then-HALT consecutive-
  divergence counter is now read from and written to the durable delegation-state marker family
  (`fleet_commons.delegation_state.record_integrity_divergence`,
  `.claude/delegation/integrity.json`, keyed session + engine) instead of a module-level dict, so
  a consumer driving `dispatch(gated=True)` one-process-per-attempt genuinely HALTs on the second
  consecutive divergence instead of requeueing forever (#384 review F1, plan KTD7). The
  in-process dict survives only as a fallback when the durable store is unavailable.
- **`plugins/saga/scripts/engine_dispatch.py`:** the `delegation_audit` / `delegation_state` /
  `audit_store` fleet-core modules load lazily with a named `delegation-audit-unavailable`
  degradation (the `tripwire_unarmed` pattern) instead of crashing every `engine_dispatch` import
  under version skew (saga >= 0.74.0 against fleet-core < 0.8.0; #384 review F5). Observer
  corroboration stays conservative (observer-NO) under skew — degraded, named, never a silent
  accept. Back-compat module attributes (`_delegation_audit` etc.) resolve via PEP 562.
- **`plugins/saga/hooks/delegation_stop_audit_hook.py`:** audit-record filenames sanitize the
  harness-supplied `session_id` through `Path(...).name`, closing the `../` path-traversal window
  from the #384 review's suppressed hardening note.

## [0.85.0] - 2026-07-13

### Changed - verify-panel verdict schema: tool-boundary enforcement aligned with the reporter predicate (#527)

- **`plugins/saga/scripts/execution_spec.py` (`_verifier_schema`)**: the verdict schema attached
  to every verify-panel `agent()` call now carries `minLength: 1` on the #390 U6 attribution
  strings (`verifier_identity`, `examined_sha`), mirroring the emitted
  `<var>_valid_verifier_verdict` runtime predicate's `.length > 0` checks exactly. Closes the
  remaining gap where a schema-admitted verdict (empty attribution string) could still be
  classified runtime-missing by the panel — any verdict the tool boundary admits is now counted
  as a reporter, and a prose/malformed return is retried/failed at the tool boundary instead of
  parse-and-hoped (evidence: workflow wf_ada4ca97-365 aggregated every panel over 0 reporters;
  LEARNINGS `{#verify-panel-prose-verdicts-vacuous-aggregation}`).
- **Tests**: emitted-JS assertions now prove the schema opt is present on EVERY verify-panel
  call across all panel-emitting sites (plain one-shot panel, iterate-to-consensus singleton
  loop, escalate_on_signal attended panel, and the unattended one-rung climb's retry panel);
  a node-executed aggregation test runs the emitted reporter predicate + reported-filter lines
  against a schema-valid verdict (counted as a reporter, refutations tallied) and the prose /
  null / partial failure modes (classified runtime-missing); a jsonschema test pins that the
  schema rejects prose and empty attribution fields at the tool boundary.

## [0.84.0] - 2026-07-12

### Added - spend observability on the ledger: estimate-reconcile, itemized receipts, spend retro, tier-efficacy and shadow-audit evidence (#402)

- **`plugins/saga/scripts/spend_estimate.py` (new):** a pre-run ordinal estimate column that joins
  onto `/plan`'s Phase 5.2a tier table (`plugins/saga/skills/plan/SKILL.md`), a payoff-at-stake x
  remaining-spend-envelope tier-value scoring helper, and a post-run `reconcile` reader over
  `outcome_costs.py`'s rollup. The reconcile deltas only the commensurable fields
  (`operator_touches`/`retries`); `tokens`/`wall_seconds` render as labeled real-world context —
  never a fabricated token-to-ordinal exchange rate. Also carries `resolve_node_tier`, a read-time
  fallback-tier lookup for `outcome_spec.Node` (which has no tier field of its own): the node's
  committed GitHub issue's stamped tier band, else the shared `SPEND_BASELINE` default — sourced
  from durable committed/GitHub state only, never the git-ignored saga cache.
- **`plugins/saga/scripts/spend_receipt.py` (new):** an itemized per-unit/per-tier receipt (over a
  single-session `ExecutionSpec`) whose cheap-fallback counterfactual total sums each unit's
  declared fallback tier (`Unit.cheaper_fallback` when set, else `adjacent_tier`'s one-rung-down),
  naming the tradeoff (`Unit.worth_it_because`) for every unit that ran above its fallback. An
  outcome-DAG node-level receipt is deferred to follow-up work — not in this PR's scope.
- **`plugins/saga/scripts/spend_retro.py` (new):** a cross-run aggregator over every committed
  `docs/outcomes/*/outcome-spec.json`'s materialized `cost_rollup`, emitting a repo-wide tier-mix /
  premium-spend-share / spend-vs-outcome summary appended as a new dated section to
  `docs/engineering-journal/LEARNINGS.md` — the mechanism that makes "xhigh-Opus is wasteful" a
  checkable claim instead of an assertion.
- **`/retro` tier-efficacy pass** (`plugins/saga/skills/retro/SKILL.md`, new Phase 1.10 reader +
  Phase 5(e) propose-diff-and-wait step) and **`plugins/saga/scripts/tier_efficacy.py` (new)**:
  mines completed-run cost-vs-outcome history and, for a work-shape running consistently above
  baseline tier with zero marginal findings across enough runs, proposes a one-rung-cheaper
  `.saga/tier-defaults.json` diff — rendered for operator review, never applied by the pass itself.
- **`plugins/saga/scripts/shadow_audit.py` (new):** a sampled 1-in-N shadow audit that replays a
  completed unit one tier down (`execution_spec.adjacent_tier`), records a sufficient/insufficient
  verdict into the evidence ledger (#398) under a namespaced `shadow-audit:<stage>:<unit-id>`
  `check_id` (reusing `evidence_ledger.py` rather than a new ledger format), and renders per-stage
  tier-sufficiency rates. Off by default in attended mode absent an explicit `--yes` or a committed
  `.saga/shadow-audit.json` `{"enabled": true}`; budget-capped via a mandatory `--max-samples` in
  unattended mode. The module never spawns an Agent itself — the replay dispatch site is documented
  in `plugins/saga/references/sandbox-spawn-sites.md`'s ad-hoc-spawn table.
- Every module here is a reader or a leaf-appender only: none writes a cost/status field back into
  `outcome_costs.py`'s ledger or an `outcome-spec.json` in place, and none auto-applies a
  tier-default change — mirroring the binding `/outcome` campaign decision that the cost ledger is
  a leaf-produced fact, derived-on-read.
- **Pre-merge review hardening (same PR):** `spend_retro.py report`/`append` gain
  `--issue-bodies` (a `{issue-ref: fetched body}` JSON object) so the CLI can reach the
  issue-tier-band resolution path — previously every node structurally defaulted to
  `SPEND_BASELINE` and the CLI's premium share could never exceed 0%; the JSON output now carries
  per-row `tier_provenance` plus a top-level `tiers_defaulted` flag, and the table labels an
  all-default premium share as a floor rather than a derived fact (`retro/SKILL.md` Phase 1.10
  updated to fetch issue bodies first). `shadow_audit.py` wraps a missing scalar key
  (`unit_id`/`stage`/`tier.*`) into `ShadowAuditError`/exit-2 as its docstring promised, and all
  five CLIs now map a corrupt JSON input file to their clean `X ERROR:`/exit-2 path instead of an
  uncaught `JSONDecodeError` traceback.
- `tests/test_spend_estimate.py`, `tests/test_spend_receipt.py`, `tests/test_spend_retro.py`,
  `tests/test_tier_efficacy_retro.py`, `tests/test_shadow_audit.py` — 50 tests covering the
  estimate/reconcile no-write guarantee, the tier-value scoring matrix, the counterfactual-total
  invariant, the golden cross-run spend summary, the gated downgrade proposal (with a byte-unchanged
  fixture-file assertion and an above/at/below-baseline-tier regression guard), the
  off-by-default/budget-capped shadow-audit gate, the `--issue-bodies` premium-share derivation and
  defaulted-floor labeling, and malformed-/corrupt-input CLI error-path coverage across all five
  scripts.

## [0.83.0] - 2026-07-12

### Added - durable delegation-audit store mirroring + /delegation-audit reconciliation (#396)

- **`plugins/saga/scripts/engine_dispatch.py`:** `record_dispatch_manifest` and
  `adjudicate_manifest` gained an `audit_store_root: Path | None = None` parameter. When given, the
  provenance manifest — and the raw `bridge_receipt.v1` when the dispatched evidence carries one —
  mirror to the durable delegation audit store (`~/.claude/delegation-audit` by default), keyed by
  `execution_id`, independent of `manifest_store.py`'s own git-common-dir cache. Defaults to `None`
  (skip) so every existing direct caller, including every test, is unaffected; the real-world
  default lives at the documented chaperone call site
  (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` §5 step 5),
  since this module has no CLI layer of its own.
- **`plugins/saga/scripts/delegation_audit_query.py` (new):** the `/delegation-audit` CLI. Reads
  the durable store and reports every run's reconciled verdict — a delegation whose disposition
  claims real execution but has no receipt backing it is flagged as a no-op.
- **`plugins/saga/skills/delegation-audit/SKILL.md` (new):** the `/delegation-audit` skill —
  read-only, advisory, on-demand; never a gate, never a background job; complements (does not
  replace) the always-on Stop-hook tripwire (`delegation_stop_audit_hook.py`).
- Consumes `plugins/fleet-core/scripts/fleet_commons/audit_store.py` (new, fleet-core 0.8.5) and
  the extended `fleet_commons/delegation_audit.py`'s new `reconcile_store` function.

## [0.82.0] - 2026-07-12

### Added - closure gate: /outcome refuses to close a leaf on missing, stale-SHA, or unsuperseded-FAIL evidence (#397)

- **`plugins/saga/scripts/closure_gate.py` (new):** reads the evidence ledger (#398) for a node's
  declared `evidence.required_checks` and derives a typed verdict every reconcile tick — pure
  read-time derivation, no new committed or cached closure-status field. A node with no
  `required_checks` declared is trivially satisfied, so every existing outcome spec is unaffected.
  Named HALT reasons: `missing-evidence:<check_id>` (no evidence anywhere), `stale-sha:<check_id>`
  (evidence exists, but not at the outcome's current close SHA), `unresolved-fail:<check_id>` (the
  latest verdict at the close SHA is a failing verdict), `unsuperseded-fail:<check_id>` (a failing
  verdict was followed by a passing one with no `payload["supersession_reason"]` justifying the
  transition — an unexplained PASS never silently clears a FAIL), `unrecognized-verdict:<check_id>`
  (a verdict string outside the known vocabulary HALTs rather than being treated as a pass),
  `unresolvable-close-sha`, and `invalid-identity:<subplot_id>` (a malformed `leaf_saga_id` or
  `check_id` HALTs cleanly instead of an uncaught exception crashing the reconcile loop).
  Close-SHA resolution: an explicit `evidence.reviewed_sha` override
  wins; otherwise a `code` node derives it from the PR's pre-merge head commit SHA
  (`outcome_github.head_ref_oid`), never the post-squash merge-commit SHA on `main`. Calls the
  already-shipped `evidence_ledger.verify_chain()` once per evaluation so a tampered chain HALTs
  rather than trusting a compromised read. Classifies each verdict against its own closed
  vocabulary rather than `evidence_ledger.latest()`'s literal-`"FAIL"`-only flag, so the real
  producer verdicts (`/qa`'s `ship` / `ship-with-deferred` / `no-ship`, `/code-review`'s `clean` /
  `blocked`) are correctly recognized as passing or failing.
- **`evidence_ledger.py` gains one additive read helper, `history(store, check_id=...)`:** every
  evidence entry for a check across every reviewed SHA — needed to distinguish "this check never
  ran" from "this check ran, but only at a different SHA". No change to any existing signature or
  storage format.
- **`outcome_orchestrator.harvest()`/`barrier_report()` wire the gate in:** `harvest()` never
  writes a `done` completion event until the closure gate is satisfied for every declared required
  check; `barrier_report()` surfaces the gate's named HALT reason per node under a `closure_gate`
  key. Both gain a new keyword-only `repo_root: Path = Path(".")` (the ledger is a committed
  repo-tree path, distinct from the git-common-dir cache `store` already resolves), defaulted so
  every pre-existing caller and outcome spec is unaffected.
- **`plugins/saga/references/outcome-spec.md`** documents the new `Node.evidence` schema
  (`required_checks` / `reviewed_sha`) and the full HALT-reason vocabulary.

## [0.81.0] - 2026-07-12

### Added - content-addressed, append-only evidence ledger for /qa and /code-review verdicts (#398)

- **`plugins/saga/scripts/evidence_ledger.py` (new):** a content-addressed (sha256), write-once
  custody store for verification evidence, committed per-saga at `docs/evidence/<saga-id>/`
  (not the git-common-dir cache `outcome_store.py`/`manifest_store.py` use — evidence needs to
  survive a fresh clone and be auditable in PR history). Identity is
  `(check_id, reviewed_sha, attempt)`: a retry appends a new attempt rather than mutating a prior
  one, and `latest()` flags a FAIL-then-PASS transition as a supersession instead of a silent
  green. Each custody entry chains to the previous via a hash over its canonical JSON, plus a
  `ledger.head` pointer that closes the one gap a pure hash chain has (an undetectable edit to
  the *last* entry, with no successor to check it against) — exactly the grounded incident this
  module exists to prevent (a probe script silently overwriting a FAIL artifact with a later
  PASS). `freeze_criteria()` pre-registers a run's pass/fail contract once, before its first
  attempt, so it cannot be redefined by a later attempt. `close_verify()` re-hashes every
  referenced artifact and criteria file and HALTs on any mismatch, and rejects a verifier whose
  role matches the check's producer (no self-certification). Reuses
  `outcome_store._write_once` / `_atomic_write` / `_safe_name` rather than duplicating them
  (mirroring the existing `manifest_store` precedent).
- **`/qa` (Phase 2, 5.1)** and **`/code-review` (Phase 1.5, 5.3)** now persist their durable
  verdict artifacts through the ledger instead of a bare file write, with a criteria-freeze step
  at each gate's intent-capture point. A no-saga interactive run falls back to
  `docs/evidence/adhoc-<branch-slug>/` — the saga *tick* is skipped in that case, never the
  ledger write. `/code-review`'s programmatic/report-only mode is unchanged (zero file writes of
  any kind, by contract).
- `tests/test_evidence_ledger.py` — 19 tests covering no-clobber, custody-chain validation
  (including a hand-edited entry, a deleted artifact, and a torn trailing line), FAIL-then-PASS
  supersession, frozen-criteria immutability across attempts, tamper-HALT at closure,
  producer/verifier role separation, and the CLI write-through path (including the adhoc
  fallback).

## [0.80.0] - 2026-07-12

### Fixed - backend offer contract in /plan Phase 5.2: enumeration, availability provenance, functional surface signal, verified shapes (#565)

- **Offer enumeration:** `recommend_execution_backend` now returns `backends`: an ordered list of all three backends
  (`inline` / `team-execution` / `cc-workflows-ultracode`) with per-backend status (`recommended` / `alternative` /
  `unavailable`) and availability notes. The deprecated `omit_ultracode` key is removed; all offer sites now name all
  three backends. Related prose in `plan/SKILL.md` (Phase 5.2), `operator-choice.md` (§3.2/§4),
  `loop/SKILL.md`, `work/SKILL.md`, `work/references/execution-strategy.md`, and
  `loop/references/drive-and-resume.md` rewritten to render from the full enumeration.
- **Availability provenance:** new `workflow_availability_source: "probed" | "asserted"` kwarg (default `"asserted"`)
  records whether availability was ToolSearch-probed at offer time or caller-asserted; output mirrors the source so
  asserted-absent backends render with "unverified; probe before trusting". Probe mandate documented in `/plan`
  prose (Phase 5.2, U2).
- **Functional surface signal:** new `release_surface_file_count: int = 0` kwarg (CLI `--release-surface-file-count`)
  subtracts release-surface files (plugin.json, marketplace.json, CHANGELOG.md, version drift tests) from the
  team-execution size trigger; `file_count - release_surface_file_count >= 8` compares functional files only. Fixes
  #526-shape regressions where 9 total files (6 bookkeeping + 3 functional) wrongly recommended team-execution.
- **Workflow shapes vocabulary:** new `workflow_shapes: Sequence[str]` kwarg (CLI `--workflow-shape`, repeatable)
  validated against `WORKFLOW_SHAPES = ("understand", "design", "research", "review", "migrate")`; any entry triggers
  the ultracode branch alongside `broad_independent_fanout` / `adversarial_confidence`. Unknown shapes raise `ValueError`
  (fail loud). Rationale string names the shape(s) so the offer explains itself.
- **Verify per-panel tier + receipts:** new optional `Verify.tier: {model, effort}` field (default None → unit tier)
  carries a separate tier for verifier runs, enabling a premium-panel escalation independent of unit tier. Panel tier
  requires `worth_it_because` / `cheaper_fallback` justification under `--require-receipts` (mirrors unit machinery).
  Emitted verifier opts carry effective tier (`verify.tier or unit.tier`); `unit_spend` prices verifier calls at the
  effective panel tier. Byte-identical round-trip when panel tier absent (R4 default preserved).
- Dispatcher frontier-budget downgrade (`outcome_dispatcher.py`) re-stamps `backends` statuses on ultracode →
  team-execution downgrade per KTD4's compat contract — enumeration never contradicts the downgraded
  `recommended` key.
- New test scenarios in `tests/test_saga_plugin.py`: functional-surface boundary regression at `file_count=9 -
  release_surface_file_count=6` → `inline`; shape validation + CLI round-trip; ultracode unavailability enumerated
  with provenance; backend enumeration always present, never silent omission.

## [0.79.0] - 2026-07-12

### Added - positive handoff protocol at saga -> deploy boundary: ack envelope, autonomy posture, dropped-baton reconcile (#395)

- `deploy_handoff.py`: new sidecar module minting handoff-ack envelopes at the saga -> deploy edge
  (distinct from mission-control envelope). Envelope schema carries ack token, gate-or-auto payload,
  offer timestamp/saga-id/pr-refs; ack side records acknowledgment token + timestamp + identity +
  evidence. Mint via `offer` (token via `secrets.token_hex`), accept via `accept` (write-once, raises
  named errors for double-accept / no-offer / token mismatch / empty identity or evidence);
  `authorize_promotion` consults the payload (gate blocks auto-promotion pending explicit confirmation,
  auto authorizes nonprod promotion only, gate payloads never silently overridden to auto-fire).
  Sidecar storage at `.claude/saga/sagas/<saga_id>/deploy_handoff.json` per KTD2. `reconcile` reads
  per-saga or `--all` sweep, derives `handed-off-unacknowledged` for offers without acks (dropped
  baton detection), lists acked or no-handoff scenarios. Exit-code convention: 0 = clean/no-handoff,
  1 = unacknowledged/error.
- `handoff_envelope.py` gains a thin `build_deploy_handoff_envelope()` delegator calling
  `deploy_handoff.build_envelope()` — it builds the envelope dict and writes nothing to disk
  (`offer` owns sidecar persistence). Existing `build_handoff_envelope` output is byte-unchanged
  (KTD1 — keeps the mission-control envelope untouched, avoids cross-plugin Python import).
- `saga.py` field: new optional `--deploy-autonomy {gate,auto}` flag on `save` (persisted in saga
  record). Captured once at `/plan` Phase 5.1 as a follow-up only when destination is
  `nonprod-deploy`; absent -> `gate` (safe direction — a missing posture can never auto-fire, per
  R5). Envelope reads `saga.deploy_autonomy or "gate"` at offer time and never re-asks (R2, KTD3).
- Handoff skill docs gain "Deploy edge" section documenting the offer/ack contract and gate-or-auto
  carriage alongside the existing mission-control boundary language; `/work` hard boundary language
  preserved — merge stays a confirmed git op `/work` owns, advisory `/qa` routing intact (AC7).

## [0.78.0] - 2026-07-12

### Added - ship ends in teardown: opened-resource manifest, closing-count gate, immutable receipt, worktree reclaim (#347)

- `ship_teardown.py`: opened-resource manifest (`opened_resources.json`) registers every resource the
  ceremony opens (branch, worktree, background session, scratch, draft PR) at open time; reconcile
  derives a closing count by reality-checking each entry per kind (worktree paths via git, branches
  via git rev-parse, scratch via filesystem, draft_pr via gh, background_session only via explicit
  close + evidence), and flags entries marked closed whose resources still exist as discrepancies
  (open, not trusted).
- `ship_receipt.py`: immutable receipt writer/reader — `mint()` refuses if closing count is non-zero
  (halts before advancing the ledger, matching #526/#346 gate shape), writes
  `ship_receipt.json` via `O_CREAT|O_EXCL` then `chmod 0444` (re-mint raises `ReceiptExistsError`),
  records every opened resource and its closed state; reader validates schema and never writes.
- `ship_ceremony.py` wiring: appends `teardown` as the terminal, non-skippable transition (tier
  `reversible`) after `branch_delete`; `next_transition` names `teardown` as the next step even for
  pre-0.78.0 ceremonies sitting at `branch_delete` (compatibility: old ceremonies regain one pending
  transition); new `_do_teardown` reconciles opened resources with reality probes, HALTs naming every
  blocker if closing count is non-zero, otherwise mints receipt and declares done; wiring
  register-on-open for branch, draft_pr, and worktrees (register at push/create, close at merge/delete).
- `reclaim` subcommand: sweeps `git worktree list --porcelain` (every linked worktree except primary
  and the running worktree), skips dirty trees and unmerged branches, removes merged-branch worktrees
  under a new `reversibility_certificate.OpKind.WORKTREE_RECLAIM_MERGED` authorize_write verdict,
  supports `--if-idle <duration>` flag (exits 0 "not idle" if newest mtime across saga sidecars /
  worktree registry is younger than bound; candidate worktrees with recent activity within the bound
  are skipped even if merged+clean). One additive SessionStart hook entry invokes
  `reclaim --if-idle 24h --quiet`.
- `ship_undo.py`: adds no-op handler for the new `teardown` transition (receipt is forward-only truth;
  undo must not crash on the new transition name).

## [0.77.0] - 2026-07-11

### Added - ceremony hazard preflight, deterministic merge-watcher, ship --undo rollback (#346)

- `ceremony_hazards.py`: detect stacked-PR topology and merge-not-landed hazards before destructive
  transitions; named hazard acknowledgment via `--acknowledge-hazard <hazard-id>` (stacked-PR
  acknowledgeable, merge-not-landed a hard refusal).
- `merge_watcher.py`: record merge expectation (target SHA, required checks, review state) at PR-open
  time, validate at merge, catch mid-poll check flips; divergences block the merge; no auto-heal
  (KTD7); `record --force` is the only re-baseline path.
- `ship_undo.py`: rollback manifest (per transition: branch/head/PR/merge SHA/remote-created flag)
  appended after each successful step; `ship --undo` (via `run --undo`) reverts ceremonies newest→oldest
  (forward-only: revert commit on main, branch resurrection), resumable and idempotent from
  manifest alone. Undo of `always_operator`-reversing entries requires `--operator-confirmed undo`
  (KTD5).
- `ship_ceremony.py` wiring: preflight hazard detection + merge-watcher validation after #526 gate and
  before dispatch; manifest append on every successful transition; `--undo` dispatches to ship_undo;
  `/work` SKILL and `pr-continuation-loop` reference updated with watcher + hazard + undo contract.
- Code-review hardening (same release): `_sha_reachable` fetches origin before declaring a recorded
  SHA unreachable (a merge-landed-but-not-pulled squash SHA is reachable, not a refusal); `saga_id`
  is validated as a single path-safe segment before any sidecar path is derived; manifest-sourced
  branch/SHA/PR values are refused if option-like before reaching git/gh argv (plus `--` separators
  where git supports them); sidecar writes are atomic (tmp + rename); corrupt sidecar/manifest JSON
  surfaces as a named module refusal, never a raw traceback; `SHA_UNREACHABLE` now carries a remedy.
- Dogfood fix (same release): the expectation sidecar records a name→passing map and `validate`
  raises `check_flipped` only for a recorded-passing check gone non-passing (R4-literal) — a
  conditionally-SKIPPED workflow, non-passing at record and merge alike, is baseline, not a flip.
  Legacy map-less sidecars stay strict; `record --force` upgrades them.

## [0.76.0] - 2026-07-11

### Added - operator-confirmed gate for `always_operator`-tier transitions (#526)

- `ship_ceremony.py run` now requires `--operator-confirmed <transition>` to execute
  `always_operator`-tier transitions (`merge`, `branch_delete`).
- A bare `run` reaching a gated transition exits non-zero, names the withheld transition, and leaves
  the ceremony ledger unadvanced — no state changes until the operator passes the flag naming that
  exact transition.
- Bare `run` behavior on `reversible`/`additive` transitions is unchanged.
- Guidance surfaces updated: `/work` skill and `pr-continuation-loop` reference now name the flag.

## [0.75.23] - 2026-07-10

### Changed - current Codex model routing and provenance (#559)

- Register GPT-5.6 Sol, Terra, and Luna high/xhigh Codex selectors with Sol high as the
  engine default; retain GPT-5.5 as explicit legacy selectors.
- Require registry-backed Codex dispatch to carry explicit model and reasoning effort, and keep the
  canonical `<model>-<effort>` identity aligned across invocation, receipts, evidence, and manifests.
- Preserve advisory-only, read-only, reviewer-role, disposable-clone, spend-guard, and no-write halt
  behavior.

## [0.75.22] - 2026-07-10

### Added - operator-confirmed, advisory-only second-opinion triggers (#394)

- Added one typed Saga coordinator for bounded single-finding external review. It uses the existing
  resolver/dispatch/reconciliation seams with `intent=second-opinion` and
  `role_kind=advisory-reviewer`; Codex and agy wrappers retain reviewer read-only/no-write posture, and
  external content cannot satisfy a gate.
- Added a durable pre-dispatch claim, conservative credential/customer/tenant egress classification,
  malformed-output degradation, and the ordered `reconcile` -> enriched artifact -> `available` -> `apply`
  recovery path. Metadata-only state stores fixed failure categories, never runner prose.
- Added `/work`'s bounded atomic `saga.work-second-opinion.v1` sidecar with target-specific three-fix
  debounce, reset/expiry semantics, and no replay after an unavailable outcome. `/code-review` and
  `/doc-review` now define native stable-finding point-outs and share the closed optional advisory projection
  while preserving Claude-owned final status/severity and report-only no-dispatch behavior.

## [0.75.21] - 2026-07-10

### Fixed - pull-cord schema still 400'd in 0.75.19; the top-level `oneOf` had to go entirely (#364)

- 0.75.19 fixed the wrong half of the Anthropic API's two-stage schema validation. A bare
  `{"oneOf": [...]}` first trips `400 tools.N.custom.input_schema.type: Field required`; 0.75.19
  added the top-level `"type"` but kept `oneOf` for the alternative `required` sets. That shape
  hits the API's **second** gate: `400 tools.N.custom.input_schema: input_schema does not support
  oneOf, allOf, or anyOf at the top level` (verified live 2026-07-10 on team-norns run
  `wf_758c9923-c2c`), so every cheap-tier unit's agent still died before running.
- `_return_schema` now emits a **flat** typed object for pull-cord units: the union of the unit's
  declared returns keys plus an optional `pull_cord` string, with no `required` alternation and no
  top-level combinator. The returns-XOR-pull_cord contract was never the schema's job — it is
  enforced by the emitted `__gate` (probes `pull_cord` first, then checks emptiness) and by the
  unit prompt's RETURN CONTRACT, both unchanged since #364.
- 0.75.19's regression sweep asserted only that every emitted schema carries a top-level `"type"`,
  which passed on the still-broken shape. That sweep now **also** asserts no emitted schema carries
  a top-level `oneOf`/`allOf`/`anyOf`, closing the gap that let the second failure ship.

## [0.75.20] - 2026-07-10

### Fixed - `save --kind` no longer silently flips a saga's identity kind

- `saga.py save --saga-id task-foo --id foo` with `--kind` omitted no longer stamps `kind: issue`
  over a prior `task` saga. `--kind` argparse-defaulted to `"issue"` and `kind` (a sticky identity
  field) has no dataclass default, so `_merge`'s default-equality carry-forward could never fire
  for it and the resolved default always won — the last deliberately-unfixed residual of the
  issue-157 absent-vs-default audit (0.75.18).
- `--kind` now defaults to `None`. An omitted `--kind` on an existing `--saga-id` carries the
  prior tick's kind forward in `save()` (via the `explicit_fields` set from 0.75.18); a new saga
  with no `--kind` still resolves to `"issue"` in `_build_save_saga` to derive its id. An explicit
  `--kind` that contradicts the prior tick's recorded kind is now rejected (exit 2) rather than
  applied, since identity is fixed at birth.
- Regression tests pin omitted-`--kind` task-kind preservation and explicit-contradiction
  rejection (`tests/test_saga_saga.py`); programmatic `save()` callers that pass no
  `explicit_fields` now inherit the prior tick's kind instead of overwriting it.

## [0.75.19] - 2026-07-10

### Fixed - pull-cord unit schemas rejected at agent dispatch (#364)

- The execution-spec emitter built cheap-tier pull-cord-capable unit schemas as a bare top-level
  `{"oneOf": [<returns-shape>, <pull-cord-shape>]}` with no top-level `"type"` key. The Anthropic
  API requires `type` on every tool input schema, so dispatch failed with
  `400 tools.N.custom.input_schema.type: Field required` — the unit's agent died before running
  and the workflow gate failed it as missing-output (reproduced 2026-07-10 in team-norns run
  `wf_758c9923-c2c`, unit U3 of the council-dispatch-gate plan). The emitter now hoists
  `type: "object"` and the union of both branches' `properties` to the top level, keeping `oneOf`
  only for the alternative `required` sets (declared returns vs `["pull_cord"]`).
- Regression guard: a new test sweeps every `schema:` blob in an emission covering all agent
  sites (plain unit, cheap pull-cord union, external-engine dispatch, refute-N verifier panel,
  iterate-to-consensus loop) and asserts each carries a top-level `"type": "object"`.

## [0.75.18] - 2026-07-10

### Fixed - explicit save flags equal to their defaults were swallowed by carry-forward

- `saga.py save --status active` on a `paused` saga now actually reactivates it. The argparse
  default for `--status` was `"active"`, and `_merge`'s scalar carry-forward treats an incoming
  value equal to the dataclass default as "not provided", so an explicit `--status active` was
  indistinguishable from an omitted flag and the prior `paused` carried forward (reproduced
  2026-07-09 in team-norns on saga issue-157: two consecutive reactivation saves both persisted
  `paused`).
- Same-class fixes for every scalar save flag whose meaningful value-space includes its dataclass
  default: `--lifecycle-phase ideation`, `--phase-status pending`, `--destination plan-only`,
  `--phase 0`, `--round 0`, `--progress-pct 0`, and `--orchestration-mode inline` (which
  previously manufactured a mode/operator-choice divergence the save-time provenance guard
  rejected). All now argparse-default to `None`; `_build_save_saga` resolves omissions to the
  dataclass default and reports the explicitly provided fields, and `_merge`/`save()` accept an
  `explicit_fields` set that bypasses default-equality carry-forward for those fields. Omitted
  flags carry forward exactly as before; programmatic `save()` callers are unaffected.

## [0.75.17] - 2026-07-09

### Added - typed external-engine reconciliation (#393)

- Add an exhaustive intent-to-recipe registry and typed finding reconciliation, recording
  `reconcile` and `apply` events in the existing hash-chained `run_fact.v1` ledger.
- Preserve rejected offloads as non-gating reviewer/validator evidence and add a bounded
  `PANEL_N_CAP = 7` advisory-jury path that persists only Claude-foreman results.
- Derive approval-gated `/retro` recipe-review proposals without mutating the ledger or registry.
- Cycle-1 hardening binds every result to dispatch identity, intent, evidence digest, and source IDs;
  stores only a bounded structural projection under `0600` locked ledger custody; enforces ordered
  reconcile/apply transitions; and centralizes capped advisory-panel policy below the resolver.
- Cycle-2 hardening adds immutable ordered per-content finding envelopes with exact multi-finding
  coverage, non-healing ordinary snapshots, 1024-byte evidence-bound rejection summaries, `0600`
  final manifests, and exact ordered-ID plus canonical-digest panel foreman binding.
- Cycle-3 and bounded-review hardening requires successful review output to exactly match its
  canonical declared-findings envelope before either direct or panel reconciliation can proceed.

## [0.75.16] - 2026-07-09

### Added - provider onboarding, conformance, and probation standing (#455)

- Add `trust_tier` enforcement across the registry and resolver: probationary rows can serve worker
  and generator offload but cannot serve advisory-reviewer or composing-panel roles.
- Add a named offline registry conformance gate and `tools/add-engine.sh`, which validates and
  atomically inserts OpenAI-compatible HTTP rows through the existing generic bridge.
- Add read-only, hash-chain-verified promotion assessment over the five most recent exact-variant
  bridge runs, plus the operator guide at `docs/adding-a-provider.md`.

## [0.75.15] - 2026-07-09

### Added - task provider recommendation primitive (#391)

- `plugins/saga/scripts/engine_recommend.py`: add read-only ranked recommendation ladder
  over `Registry.ranked_candidates()` with `cheapest-viable`, `free-first`, MODERATE
  capability floor, token-window filtering, and sensitive-task local-only halts.
- `plugins/saga/scripts/engine_registry.py` `plugins/saga/references/engine-registry.yaml`:
  require explicit `egress_policy` (`local-only` or `networked`) per engine row; current
  seed providers are marked networked, including in-repo agy rows.
- Add recommendation and registry coverage for price tie-breaks, free-first ordering,
  sensitivity filtering, side-effect-free behavior, and release metadata parity.

## [0.75.14] - 2026-07-09

### Added - output attestation lie detector (#388)

- `plugins/saga/scripts/bridge_signatures.py` and
  `plugins/saga/references/bridge-signatures.json`: add emitter-keyed bridge proof policy for
  output attestation, external-token proof, run keys, and liveness joins.
- `plugins/saga/scripts/engine_dispatch.py` and
  `plugins/saga/scripts/provenance_manifest.py`: classify missing attestation, hash mismatch,
  zero external tokens, and bridge-run proof contradictions as `proof-integrity`, never
  `RAN_AS_REQUESTED`, and record idempotent `bridge_run_key` token facts in the run ledger.
- Add focused lie-detector, liveness, ledger, attestation, and signature drift tests proving
  Claude-only or zero-call delegated-output disguises fail loud.

## [0.75.13] - 2026-07-09

### Added - offload economics guards (#386)

- `plugins/saga/scripts/engine_registry.py` and
  `plugins/saga/references/engine-registry.yaml`: add explicit cost-class and
  budget-ceiling metadata with lint coverage for metered and free providers.
- `plugins/saga/scripts/chaperone_economics.py`,
  `plugins/saga/scripts/engine_dispatch.py`, and
  `plugins/saga/scripts/provenance_manifest.py`: enforce break-even and budget-ceiling
  offload checks before dispatch, then record typed net-savings evidence in manifests
  and run-ledger facts.
- `plugins/saga/scripts/engine_offer.py` and
  `plugins/saga/references/engine-dispatch.md`: add advisory offload cost-delta
  previews while keeping dispatch as the hard spending stop.

## [0.75.12] - 2026-07-09

### Added - blind external-engine divergent generator lane (#454)

- `plugins/saga/skills/ideate/SKILL.md`: documents an additive, best-effort external-engine generator
  lane for `/ideate` Phase 2 using the same frame-agent prompt contract as Claude frame agents.
- `plugins/saga/skills/ideate/references/convergence-and-partnership.md` and
  `plugins/saga/skills/ideate/references/ideation-artifact.md`: record `engine-generated` as
  provenance only, with the existing basis gate and survivor scoring applied unchanged.

## [0.75.11] - 2026-07-09

### Added - engines route explain visibility (#453)

- `plugins/saga/scripts/engine_overlay.py`: adds validated repo-local
  `.saga/engine-overlay.json` pins and deprecations with atomic writes.
- `plugins/saga/scripts/engine_registry.py` and
  `plugins/saga/scripts/engine_resolver.py`: add overlay-aware route explanations
  and opt-in resolver overlay support while preserving no-overlay behavior.
- `plugins/saga/scripts/engine_registry_cli.py` and
  `plugins/saga/commands/engines.md`: add `/engines` listing, pin/deprecate/clear,
  and read-only `route explain` operator surfaces.

## [0.75.10] - 2026-07-09

### Added - engine-registry schema currency (#452)

- `plugins/saga/references/engine-registry.yaml`: adds capability vocabulary for
  bulk classification, structured extraction, and embeddings, materialized GPT-5.5
  family capability defaults, per-row cost/latency metadata, and an embeddings-only
  Ollama Cloud row.
- `plugins/saga/references/model-releases.yaml` and
  `plugins/saga/scripts/check_engine_registry.py`: add authored model-release
  currency data plus a named CI lint gate for stale registry rows.
- `plugins/saga/references/surface_intent_defaults.yaml` and
  `plugins/saga/scripts/engine_offer.py`: move lifecycle engine-offer intent
  defaults into data while preserving repo-local preference overrides.

## [0.75.9] - 2026-07-09

### Added - engine output trust-boundary contract (#385)

- `plugins/saga/references/engine-output-trust-boundary.md`: documents external-engine advisory
  output as untrusted input, forbidden executable/gate sinks, and opaque-data handling.
- `tests/test_engine_output_trust_boundary.py`: adds contract anchors, seeded unsafe interpolation
  guards, and an adversarial `AdvisoryEvidence.evidence` fixture proving malicious advisory text stays
  inert through `satisfy_gate`.

## [0.75.8] - 2026-07-09

### Added - shared lifecycle-stage engine offer helper (#451)

- `plugins/saga/scripts/engine_offer.py`: adds an advisory-only offer helper with
  stage/shape intent-tier resolution, repo-local `.saga/engine-prefs.json`
  preferences, conservative mechanical offload defaults, and a CLI facade for
  markdown-driven skills.
- `ideate`, `brainstorm`, `work`, `doc-review`, and `code-review` now document a
  shared helper call site with drift-guard coverage.

## [0.75.7] - 2026-07-09

### Fixed - advisory consensus evidence remains outside Saga completion gates (#382)

- `plugins/saga/scripts/engine_dispatch.py`: classify consensus advisory reviewers as
  non-gating evidence so panel/advisory receipts cannot satisfy completion gates even when
  verified or corroborated.

## [0.75.6] - 2026-07-09

### Added — cheap external-engine chaperoning economics (#381)

- `plugins/saga/scripts/chaperone_economics.py`: adds pure policy helpers for homogeneous same-engine batching, explicit `test-gated` / `unverifiable` review modes, evidence-size tier escalation, deterministic acceptance sampling, and sampled-defect full-review escalation.
- `plugins/saga/scripts/execution_spec.py`: adds optional external-engine `Unit.verifiability`, emits it only when authored, and threads it into emitted external-engine call metadata while preserving old specs byte-for-byte.
- `plugins/saga/scripts/engine_dispatch.py` and `engine_resolver.py`: add optional advisory chaperone provenance and run-scoped payload caching keyed by `unit_id`, protocol hash, and context hash; no manifest schema or gate semantics change.
- `/plan` tier table now has a registry-rendered `offload` + `verifiability=test-gated` ratify-only row and keeps absent/unverifiable offload on full-review posture.

## [0.75.5] - 2026-07-09

### Added — registry-authored provider credential preflight (#389)

- `plugins/saga/scripts/engine_registry.py`: `EngineEntry` now exposes normalized
  `invocation.auth` metadata for `files`, `env`, `bearer`, and `secret-ref` credential probes;
  HTTP bridge rows remain bearer-only until the bridge can consume another credential mode.
- `plugins/saga/scripts/engine_resolver.py`: CLI preflight now reads executable and credential
  requirements from registry rows, keeps legacy no-entry callers working, and caches row-backed
  preflight by row identity instead of only `engine_id`.
- `plugins/saga/references/engine-registry.yaml`: codex and agy CLI rows now declare `invocation.cli`
  plus file-backed auth probes, matching the existing HTTP bearer-row contract.

## [0.75.4] - 2026-07-08

### Fixed — refute-N verifier panels fail loudly instead of passing under-strength (#519)

- `plugins/saga/scripts/execution_spec.py`: verifier `agent()` calls now carry a structured
  verdict schema requiring `refuted`, `upheld`, `verifier_identity`, `fallback_depth`, and
  `examined_sha`, so prose verdicts no longer collapse panels to `0/N` reporting.
- Emitted workflows append the unit result directly to verifier prompts and instruct isolated
  verifiers to materialize the primary checkout SHA before judging, making branch/output
  visibility an explicit verifier contract rather than an improvisation.
- Below-quorum panels now throw `verifier-under-strength` after logging missing-verifier detail;
  refuted quorum panels still throw `verifier-disagreement`.

## [0.75.3] - 2026-07-08

### Fixed — execution_spec emits StructuredOutput schemas for returned unit values (#503)

- `plugins/saga/scripts/execution_spec.py`: unit `agent()` calls now carry a schema derived
  from declared `returns`, so singleton units, parallel thunks, iterate-to-consensus loops,
  external-engine dispatches, and unattended climb retries request structured output at
  generation time instead of relying only on prose parsing in `__gate`.
- Cheap-tier unit schemas preserve the existing pull-cord escape hatch with a `oneOf`
  alternative, keeping budget-depth escalation behavior compatible with the structured return
  contract.

## [0.75.2] - 2026-07-08

### Fixed — cross-repo Objective ingestion stamps child repos and collision-safe subplot IDs (#512/#513)

- `discover_subissues.py` now fetches `repository.nameWithOwner` for sub-issues and tracked issues,
  preserving typed repo/number relationships for cross-repo Objectives.
- `outcome_edges.py` centralizes subplot ID derivation: existing `sub-<number>` IDs are preserved
  for unique numbers, while same-number collisions become repo-qualified and edge inference resolves
  typed cross-repo dependencies without guessing ambiguous legacy refs.
- `outcome.py` stamps each ingested node with the child issue's own repository and uses the shared
  subplot ID mapping, so board-sync, reconcile, and harvest target the correct GitHub issue.

## [0.75.1] - 2026-07-08

### Fixed — board-sync progress comments are crash-replay idempotent (#502)

- `plugins/saga/scripts/board_progression.py`: `issue-progress-comment` payloads now carry a
  hidden marker derived from the same idempotency key as the board-sync ledger. The production board
  writer checks existing issue comments for that marker before posting, so a crash after the GitHub
  comment POST but before the local ledger write replays as a remote-marker skip and then restores
  the missing local ledger key instead of double-posting.

## [0.75.0] - 2026-07-07

### Added — fail-loud provenance wiring: SUBSTITUTED_ENGINE derivation, gate refusal, empty-delivery HALT, verify-spawn attribution (#390 U2/U4/U5/U6)

- `plugins/saga/scripts/engine_dispatch.py`: `dispatch()` gains an optional `expected_identity`,
  stamped into evidence provenance; `build_dispatch_manifest` auto-derives
  `Disposition.SUBSTITUTED_ENGINE` when the evidence's expected engine identity differs from the
  resolved `engine_id`/`variant`, with a disposition note naming both identities (branch
  precedence: `DELEGATION_INTEGRITY` > halt (`FELL_BACK_TO_CLAUDE`) > `SUBSTITUTED_ENGINE` >
  receipt check). Every non-`RAN_AS_REQUESTED` manifest now carries a non-empty
  `disposition_note` (fixed fallback string for degenerate empty reasons). `satisfy_gate` refuses
  any manifest whose disposition is `SUBSTITUTED_ENGINE` — substituted evidence can never satisfy
  a gate as-approved. `expected_identity=None` callers keep prior behavior byte-for-byte.
- `plugins/saga/scripts/manifest_reader.py`: the roll-up report gains a reasons section listing
  execution id, disposition, and `disposition_note` for every manifest whose disposition is not
  `RAN_AS_REQUESTED`, so a forced fallback is traceable to prose, not just an enum.
- `plugins/saga/scripts/check_empty_delivery.py` (new): pure verdict function plus a thin CLI
  (reads `git status --porcelain -z`) that HALTs a delegated unit claiming delivery with zero
  changed paths, and returns a proceed verdict authorizing the existing chaperone-owned commit
  step for a delivering unit. Kept distinct from `manifest_store.py`'s returned-value
  `missing-output` axis.
- `plugins/saga/scripts/execution_spec.py`: verifier verdict schema and prompt gain
  `verifier_identity` (emitter-stamped) and `fallback_depth` (default 0); panel aggregation
  renders an explicit "fallback tier N" marker in the gate summary when any reporter's depth
  exceeds 0, and no marker for an all-first-choice `saga:readonly-verifier` panel.
  `plugins/saga/references/sandbox-spawn-sites.md` documents the rung-recording requirement for
  inline prose-ladder spawns (rungs 2/3). The fallback ladder's own order and contract are
  unchanged.

## [0.74.1] - 2026-07-07

### Fixed — code-review: gate Phase 5.4 saga append in programmatic mode (#468, Defect 2)

- `plugins/saga/skills/code-review/SKILL.md`: update Phase 5.4 to skip the saga tick append entirely
  in programmatic / report-only mode where the caller owns persistence, while keeping the
  interactive mode behavior and the no-saga scan-first guard unchanged.

## [0.74.0] - 2026-07-07

### Added — runtime delegation tripwires: armed PreToolUse block, Stop-hook audit, two-signal acceptance (#384, U3-U5)

- `hooks/delegation_tripwire_hook.py` (new `PreToolUse` hook, matcher
  `Write|Edit|MultiEdit|NotebookEdit`): while a session is armed and no genuine engine invocation
  is yet evidenced (a run directory under `.claude/agy/runs/` or `.claude/codex/runs/` containing
  a `prompt.txt` newer than the armed-at timestamp), Claude's own file-tool calls are blocked
  (exit 2). Unarmed sessions and every error path (malformed stdin, unreadable marker) fail open
  (exit 0) — zero behavior change when nothing is armed.
- `hooks/delegation_stop_audit_hook.py` (new `Stop` + `SubagentStop` hook): on an armed turn,
  classifies the transcript and corroborates the engine's bundle via fleet-core's
  `delegation_audit` module; hard-blocks the stop (exit 2, stderr reason) on
  `fallback_suspected`, honoring the `stop_hook_active` loop guard (one forced continuation
  max, banner + durable audit record under `.claude/delegation/audits/`). Transcript-verdict vs.
  engine self-report divergence is surfaced as `DELEGATION_INTEGRITY` rather than silently
  resolved either way.
- `engine_dispatch.py` arms around each adapter run and reconciles the engine's self-report
  against observer corroboration (receipt validity + bundle launch flag); divergence is a new
  `Disposition.DELEGATION_INTEGRITY` member on `provenance_manifest.py`, returned as a typed
  re-queue disposition — one re-dispatch attempt, then HALT (never silent accept).
  `satisfy_gate()` now additionally requires observer corroboration, not just Claude's own
  `verified_by_claude` bit.
- `hooks/hooks.json`: registers both new hooks (`PreToolUse` matcher-scoped;
  `Stop`/`SubagentStop` both marker-gated, each fed the correct turn's transcript path).

## [0.73.1] - 2026-07-06

### Retired — `codex:codex-rescue` (openai-codex marketplace plugin) (#476, R6)

- Every in-repo dispatch reference to the retired `codex:codex-rescue` agent (engine
  registry rows, `engine_dispatch.py`'s `build_codex_invocation`, engine-dispatch and
  external-engine-workers reference docs, tests) now points at the first-party
  `codex:delegate` (`plugins/codex/`). A grep sweep for `codex:codex-rescue` / `codex-rescue`
  confirms zero live references remain outside historical CHANGELOG and
  `docs/engineering-journal` entries, which are records and intentionally untouched. See
  `plugins/codex/README.md`'s operator runbook for uninstalling the `openai-codex`
  marketplace plugin and the `codex:` namespace-collision note (both plugins claim the
  `codex:` agent prefix; the marketplace copy must be uninstalled before this plugin's
  agents resolve cleanly).

## [0.73.0] - 2026-07-06

### Added — generic HTTP bridge + bridge_receipt.v1 keystone pair (#387, #383)

- `engine_dispatch.py`'s `_build_invocation` gains a `transport`-keyed branch: `transport: http`
  registry rows dispatch through one generic OpenAI-compatible bridge
  (`engine_bridge_http.py`, stdlib `urllib.request` behind a `Runner`-shaped seam) with zero
  per-provider branching inside the bridge — provider differences live entirely in registry row
  data (base URL, auth mode/env var, model id). `transport: cli` keeps the existing codex/agy
  builders unchanged (default `cli`, byte-identical for every existing row).
- `engine_registry.py` / `engine-registry.yaml`: new `transport` field (closed vocab `cli | http`)
  plus http-conditional required invocation fields (`base_url`, `model`, `auth.mode`,
  `auth.key_env` when bearer, explicit `effort`); `receipt_emitter` is now a required key on every
  row, validated at load (`RegistryError` on a row missing it — a row without receipt wiring
  cannot be dispatched to). Two new seed rows: `ollama-cloud` (Ollama Cloud, bearer auth from
  `OLLAMA_API_KEY`, first $0-marginal offload row) and `deepseek` (bearer auth from
  `DEEPSEEK_API_KEY`). Neither row outranks an existing `by_capability` winner (routing-stability
  regression test bakes current winners as literals).
- `engine_resolver.py`: transport-aware `preflight()` (HTTP checks the auth env var is present and
  the row is well-formed — no live network; reachability is proven only by the availability-gated
  smoke test) and an explicit `RunMemo` object threaded as an optional `memo` keyword through
  `resolve` / `resolve_role`, memoizing one resolve/preflight per engine per run
  (`(capability, token_estimate)` for resolution, `engine_id` for preflight) — 10 resolves of one
  engine in a single run now invoke the availability probe once. Memo is opt-in; the no-memo path
  stays today's byte-for-byte behavior.
- `bridge_receipt.v1` (new `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py`,
  vendored to `plugins/agy/scripts/fleet_commons_shim.py`): the proof-of-execution contract every
  bridge emits — a common core (`schema`, `engine_id`, `variant`, `transport`, `wall_time_s`,
  `bytes_produced`) plus transport-discriminated runner evidence (`{pid, argv, exit_code}` for
  `cli`, `{url, status_code, model}` for `http`). `AdvisoryEvidence` gains an additive
  `runner_receipt: dict | None = None` field; `build_dispatch_manifest` assigns
  `Disposition.RAN_AS_REQUESTED` only when a schema-valid receipt is present, else the new
  `Disposition.UNPROVEN` (receipt-less success is never mislabeled as proven; `FELL_BACK_TO_CLAUDE`
  is unaffected). A structural guard rejects any runner result carrying a gate/verdict-shaped key
  (`verdict`, `gate_status`, `adjudicated`) as a `DispatchError` — external engines can never become
  gatekeepers (`{#external-engines-never-gatekeepers}` #283), enforced by construction, not policy.
- New `tests/test_bridge_receipt_drift.py`: a forcing-function drift guard enumerating every
  registry `receipt_emitter` value and proving each in-repo emitter dispatches through the shared
  receipt-emitting path (`PENDING_EMITTERS = {"codex-bridge": "#476"}` covers the not-yet-landed
  codex bridge; the guard reds if a pending entry's issue closes while the entry is still pending).
- Secret lifecycle: a bearer token resolved from `auth.key_env` exists only in the HTTP request
  headers at call time — never in the invocation dict (which flows into run-ledger telemetry), a
  receipt, `AdvisoryEvidence`, or a log line. Receipts may carry the env var *name*, never its
  value.
- New `plugins/saga/references/dispatch-adapter-contract.md`: the dispatch-adapter contract
  reference for anyone adding a `transport: http` registry row or a new bridge.
- Existing callers stay byte-identical: no signature breaks, `transport` defaults to `cli` for
  every pre-existing row, memo is opt-in, and `preflight()`'s new `entry` parameter is optional.

## [0.72.0] - 2026-07-06

### Fixed — /outcome attend emits the leaf's real issue-backed saga id (#491)

- `/outcome attend <id> <subplot>` printed the dispatcher's raw `leaf_saga_id`
  (`leaf-<outcome>-<subplot>`), but an issue-backed leaf's actual native saga is `issue-<N>` (what
  `/plan` and `/work` mint via `saga.derive_saga_id`) — so the `/resume` handoff pointed at a saga id
  that does not exist. `attend` now resolves the real id: `_leaf_handoff_id` reads the node's
  `github.sub_issue` (bare number) or parses `owner/repo#N` from `github.issue` (reusing
  `outcome_github._parse_ref`, #495) and emits `/resume issue-<N>`; a non-issue-backed (task/ad-hoc) leaf
  keeps the raw id.
- Scope is `attend` only: `outcome_report.py` never emitted the leaf handoff (`AttentionItem` carries
  only `subplot_id`), so it is unchanged.

### Notes

- Saga-only; last execution-discovered defect from the `tier-effort-first-class` `/outcome` dogfood.

## [0.71.0] - 2026-07-06

### Fixed — /outcome code-leaf completion harvest silently never fired (#495)

- **The producer gap (gap 1).** The `code:pr-merged` barrier (`outcome_orchestrator.py`) and the
  auto-merge queue (`outcome_merge._is_mergeable_kind`) both *consume* `node.github["pr"]`, but the
  record-only dispatch → native `/work` → squash-merge flow never *produced* it, so `advance` read
  "no PR ref yet" forever and left every code leaf pending (the only recovery was a hand-edit of the
  committed spec). New verb **`/outcome link-pr <id> <subplot> <pr-url>`** is the attended producer:
  it writes `node.github["pr"]` (validated as a PR URL, code-node-only, idempotent; `--push` banks it
  to the outcome branch). It attaches a pointer only — the barrier still re-verifies `merged`, so a
  wrong/unmerged link never falsely completes a node.
- **The ref-format gap (gap 2).** `outcome_github._parse_ref`/`_gh_ref` normalize a stored ref
  (`owner/repo#N` | full URL | bare `N`) to a gh-consumable token; `pr_state`, `issue_state`,
  `board_status`, and `issue_close_info` now resolve `owner/repo#N` (previously `gh` rejected it as an
  invalid issue format / misread it as a branch). `_closed_by` consumes `_parse_ref` too, so
  normalizing a view-ref to a URL never starves its REST events path.
- The `code:pr-merged` contract is unchanged and now regression-guarded: a closed tracking issue never
  satisfies a code leaf; only a merged `github.pr` does.

### Notes

- Saga-only; **R17 preserved** — the fix touches GitHub refs + completion events, never persists derived
  `node.state`/`complete` into the committed spec JSON.
- Deferred (not built): a zero-touch autonomous PR producer (the autonomous auto-merge path is not yet
  exercised, and its auto-mechanisms are fragile/coupling); a merge-time writeback was rejected as
  vacuous (the merge queue already requires `github.pr` to act).

## [0.70.0] - 2026-07-06

### Added — spend-delta machinery: the silent-cheap/ask-expensive levers (#367)

- `spend_delta(old, new) -> {cheapen | escalate | lateral}` in `execution_spec.py`: the three-way
  direction classifier, built on per-axis ordering (a shared `_axis_deltas` helper via the palette
  `stronger` op, never raw `.index()`). `is_escalation` now shares that helper but keeps its exact
  two-way semantics — `lateral` (a sideways axis trade) is deliberately distinct from `escalate`.
  Built on ordering, not `to_spend` magnitude: the cost table is injective, so a magnitude reading
  could never produce `lateral`.
- `adjacent_tier(tier, "cheaper"|"dearer")`: the relative one-notch lever. `cheaper` reuses
  `tier_resolver.cheaper_fallback` (#362); `dearer` is the symmetric one-rung-up. Boundary calls
  **raise** rather than clamp or wrap.
- `Unit.worth_it_because` + `Unit.cheaper_fallback` (both optional, byte-identical round-trip absent) +
  a **premium-tier worth-it hard-block**: `validate(require_receipts=True)` fails a premium tier
  (opus/fable model or xhigh effort, above the `sonnet/high` baseline) that lacks a justification or a
  strictly-cheaper named fallback. Gated on `require_receipts` — enforced at `/plan` authoring, never on
  the unconditional `validate()` that emit and existing specs run (no retroactive break).
  `execution_spec.py validate --require-receipts` is the authoring gate. Engine-owned units are exempt.
- `spend_authority.py` + `.saga/spend-authority.json`: a per-repo `silent_ceiling` matrix resolving each
  unit `silent`/`ask` (premium → `ask`). Absent file → safe default `sonnet/high`; malformed → loud
  `SpendAuthorityError`. Same `is_escalation` predicate as the worth-it block (pinned by an exhaustive
  grid guard test), so the two levers agree on what "premium" means.
- `/plan` §5.2a Step 1c documents the relative override, worth-it receipts, and spend-authority stamp.

### Notes

- Saga-only (no fleet-core change): `spend_delta`/`adjacent_tier` are `Tier`-typed and live in
  `execution_spec.py`; `tier_resolver.cheaper_fallback` is reused, not modified.
- Completes the `tier-effort-first-class` outcome (9/9): #366's `cost_budget`/`spend_envelope` answered
  "how much?"; #367's `spend_delta` answers "which way?".

## [0.69.0] - 2026-07-06

### Added — run-scoped spend budgets: price the tier lever (#366)

- `cost_weights.json` + `cost_weights.py` (in `fleet_commons`, beside `models.json`): an ordinal
  16-cell weight table and `to_spend(model, effort)`. Validated at import against the live
  `tier_palette` ordering — completeness, per-axis strict monotonicity, and off-palette rejection all
  raise `CostWeightsError` (a drifted table fails loud, closing the `{#tier-vocab-ordering}` gap).
  Weights are ordinal/relative, not dollar prices.
- `ExecutionSpec.cost_budget` + the emit-time cost HALT: `validate()`/`emit` raise a `SpecError` naming
  total vs ceiling when the multiplicity-aware summed spend exceeds the budget (mirrors `VERIFY_N_CAP`,
  with a soft warn band). The sum counts call multiplicity — fan-out target count and verify-panel `n`
  × iterations — so it cannot false-negative on the expensive fan-out/panel plans (HALT-not-degrade).
  `spec_spend()` and the module-level `unit_spend()` expose the arithmetic.
- `ExecutionSpec.spend_envelope` + the `SpendEnvelope` accumulator: collapses "ask before every
  expensive choice" into "ask once, at the crossing" (`consider(delta)` prompts only on the crossing
  choice). A CLI-set field + primitive, not an autonomous gate.
- `execution_spec.py spend <spec.json>` CLI verb: reports per-unit spend, total, `cost_budget` headroom,
  and `spend_envelope` — the surface `/plan` invokes to price a plan before locking it.
- `effort_ledger.py` + `effort-policy.yaml`: an effort-escrow ledger recording per-unit actual-vs-planned
  spend, refunding an under-spending unit's unused allocation to a run pool, and surfacing an
  escalation-request **before** a unit executes when it would exceed its allocation. CLI verbs
  `allocate` / `record` / `escalate` / `report`; an absent policy file resolves to the safe default.
- `/plan` §5.2a Step 1b (price the plan, set the guards) and `/work` execution-strategy effort-escrow
  accounting document the producer/consumer wiring.

### Notes

- All new `ExecutionSpec` fields round-trip byte-identical when absent — existing specs and
  `team_emitter` are untouched.
- The cost-weighted spend-*delta* classifier (silent-cheap/ask-expensive, relative lever, spend
  authority) is the separate #367.

## [0.68.0] - 2026-07-06

### Added — runtime ladder climbing: gated one-rung escalation on failure signals (#364)

- `escalate_tier(tier, ceiling=None)` — the pair-level one-rung climb: effort-first, then model
  (`supports_effort` invariant, never unrunnable), built on the named `tier_palette` ops. Returns
  `None` at the top of the ladder or when blocked by a ceiling — every caller renders that as an
  explicit HALT, never a silent same-tier re-run.
- `Unit.escalate_on_signal` (requires a verify panel): attended emission renders a refute as a
  throw-with-`escalation-proposal` ask gate (confirmed via the #365 `/tier` patch + re-emit);
  `emit --unattended` renders ONE in-script climb retry at the climbed tier with a fresh panel,
  then HALT — one climb per unit per run, session-ceiling-aware. Attendance is a run property and
  never enters the spec JSON (absent field round-trips byte-identical). v1 validate exclusions:
  `iterate_to_consensus`, fan-out, and no-panel (all unbounded-spend or dead-wiring vectors).
- `pull_cord` — the worker-initiated out-of-depth disposition on the cheap-tier return contract:
  the gate accepts `{"pull_cord": "<reason>"}` distinct from success/crash, the unit is never
  marked complete, and all cords batch into ONE end-of-run coordinator escalation entry carrying
  one-rung proposals.
- `/work` between-rounds recovery step (`references/pr-continuation-loop.md`): on a failure row,
  propose exactly one rung with the ordinal cost delta (`<old> -> <new> (+1 <axis> rung)`),
  end-clamped at the ladder top / session ceiling, gated on operator confirmation. The priced
  spend-delta classifier stays #367's.

## [0.67.0] - 2026-07-06

### Added — persisted tier preferences: repo overlay + issue band + one precedence rule (#368)

- New `scripts/tier_defaults.py`: committed per-repo `.saga/tier-defaults.json` overlay
  (`{"<work-shape>": {"model", "effort"}}`) pinning repo-tuned tier defaults over the shared
  `tier_policy.json` registry. `load_tier_defaults` (missing → `{}`, malformed → loud
  `TierDefaultsError`), `resolve_tier_with_overlay` (repo overlay > registry),
  `write_tier_default` (read-merge-write confirmed overrides, never clobbers other keys).
- `resolve_tier_for_plan(work_shape, issue_band)` — the one tested precedence contract:
  **repo overlay > issue-carried band > shared registry** (the repo override is closest to
  execution, so it wins the coarser issue-time band).
- `parse_tier_band(body)` — reads the `### Recommended Tier Band` section mission-control
  stamps at issue creation. Absent → `None` (normal); present-but-invalid (unparseable,
  off-palette, or unrunnable tier) → loud `TierDefaultsError` (halt-not-degrade).
- `/plan` SKILL Step 1 documents the resolve → confirm → write-back loop; every persisted
  override originates from an explicit operator confirmation (never silent auto-promotion),
  and the dirtied tracked overlay is committed with the run's changes.

## [0.66.0] - 2026-07-06

### Added — `/tier` mid-run lever: session ceiling + mid-run spec patch (#365)

- New `/tier` command (`commands/tier.md`) + `tier_session.py` module: a session-local, git-ignored
  override (`.claude/saga/tier-session-override.json`) recording a run-scoped tier **ceiling** and
  per-unit **overrides**. Off-palette values fail loud on read and write.
- `clamp_tier_to_ceiling()` — a pure, 2-axis, downward-only ceiling clamp (via `tier_palette.clamp`).
- Both emitters (`emit_workflow_script`, `team_emitter.emit_team_structure`) accept a `session_ceiling`
  and clamp each unit/segment tier down before rendering — the single enforcement point, applied
  **before** the #369 enforceability halt (so a ceiling can make an otherwise-unspawnable `fable` unit
  runnable on team-execution). Downgrades are logged; the `inline` backend honors the ceiling
  advisorily. The ceiling is the final word — it can clamp below a `min_tier` floor (the live override
  wins).
- `patch_spec_tiers()` (not-yet-run units only) + `is_escalation()` + an `execution_spec.py patch`
  subcommand: apply the session override's per-unit tiers, re-validate (hard gate), re-emit; an
  up-ladder escalation is surfaced for operator confirmation. The `emit` CLI now honors the ceiling.

## [0.65.0] - 2026-07-06

### Added — tier floors & backend enforceability (#369)

- `TIER_ENFORCEABLE_BY_BACKEND` matrix + `unenforceable_tier()` helper (`execution_spec.py`), the
  tier-axis sibling of `SANDBOX_ENFORCEABLE_BY_BACKEND`: each backend maps to the models it can spawn
  (`inline` / `cc-workflows-ultracode` reach the whole palette; `team-execution` = `{opus, sonnet,
  haiku}`, no `fable`). A backend absent from the matrix enforces nothing — unknown is never permissive.
- `team_emitter.emit_team_structure()` now HALTs (`SpecError`) when a unit's model is unreachable by
  `team-execution` (e.g. `fable`/`xhigh`) instead of rendering a cosmetic Tier cell the runtime will
  not obey — the tier-axis sibling of the existing unenforceable-sandbox halt.
- Optional `Unit.min_tier` floor: `segment_units()` clamps a merged segment tier UP to the strongest
  member floor via the palette ladder ops (never bare index math). An absent `min_tier` emits no key
  and round-trips byte-identical; an off-palette or unrunnable floor fails validation loudly.

### Deferred

- Agent-owned `tier-floor:` frontmatter (issue #369 mechanism 3) is deferred to a follow-up that
  lands it together with the per-teammate tier-override lever (`{#team-execution-per-teammate-effort}`)
  so the field ships with a real producer and consumer.

## [0.64.0] - 2026-07-06

### Changed — execution_spec consumes the single-source tier palette (#370)

- `segment_units()` now merges member tiers via `tier_palette.strongest()` instead of inlining
  `min(MODELS.index)` / `max(EFFORTS.index)` — the named ladder op reasons in strength, closing the
  `{#tier-vocab-ordering}` two-contracts footgun.
- `Tier.validate()` now HALTs (raises `SpecError`) when a Claude teammate's effort exceeds the
  model's `effort_ceiling` (e.g. `haiku`/`xhigh`) rather than silently running an un-runnable tier;
  engine-owned chaperone-dispatch units (`{#external-engine-chaperone-dispatch}`, #318) are excluded
  from the per-teammate ceiling check.

## [0.63.0] - 2026-07-05

### Changed — `team_emitter.py` validates and cascade-resolves per-teammate effort (#363)

`emit_team_structure()` now validates the A7 `Tier` cell's effort half against the canonical
`EFFORTS` vocabulary (`fleet_commons.tier_palette`, R4) — an off-palette value raises at compose
time instead of rendering an un-runnable team-structure table. A new `resolve_teammate_effort()`
resolves each non-chaperone teammate's effort through the three-layer cascade (plan-unit →
team-default → agent-frontmatter base, R5, KTD4), wrapping `tier_resolver.resolve()` and recording
which layer won as a provenance line. Chaperone workers (`offload`/`second-opinion` engine or
capability segments) are excluded from the cascade entirely — their effort is intent-driven and
must not be overridden (R6, KTD5). Closes the standing `{#team-execution-per-teammate-effort}`
queue item via the `inject_effort()` seam (see team-execution 2.11.0), not the rejected
route-onto-Workflow re-architecture.

## [0.62.0] - 2026-07-05

### Changed — `/plan`'s Step-1 tier table now renders from the shared work-shape→tier registry (#362)

Part of the dispatch-time tier resolver work (`fleet_commons/tier_resolver.py`, `tier_policy.json`)
that maps `(role_kind, work_shape, envelope_ceiling, operator_override)` to `{model, effort, because,
cheaper_fallback}`. `plugins/saga/skills/plan/SKILL.md`'s heuristic tier table is now a
registry-sourced block instead of prose, drift-guarded against `tier_policy.json` so the two can never
silently diverge. `plugins/saga/references/sandbox-spawn-sites.md` gained the tier-resolver dispatch
site alongside the existing readonly-verifier spawn-site inventory.

## [0.61.0] - 2026-07-05

### Added — one append-only, hash-chained, leaf-produced run-fact ledger substrate (#401)

The final Phase 0 item (objective #338). A single `run_fact.v1` ledger that spend / cache /
engine-usage / delegation telemetry all append into — landed empty of most consumers so the ≥8 wave-1
writers inherit one canonical format instead of N.

- **`run_ledger.py`** (new, saga-local, stdlib-only) — `run_fact.v1` schema (`kind` ∈
  spend|cache|engine|delegation, leaf-produced with `subplot_id`), a **hash-chained** `append_fact`
  (`prev_hash`→`this_hash`, reusing `outcome_store`'s `resolve_common_dir` + `O_APPEND` + torn-tail
  discipline in a **distinct** `run-facts.jsonl`, separate from the replay ledger), `read_facts`, and
  `verify_chain` (fails on in-place mutation, reorder, or middle-deletion — tamper-*evidence*).
- **Derive-on-read views** — `rollup`, `reuse_ratio` (defined-empty on no data), `last_n_prior`; no
  committed summary field.
- **Two consumers wired** — `engine_dispatch.dispatch(ledger=…, subplot_id=…, at=…)` records an
  `engine` fact on any advisory call and a `delegation` fact for an `agy.delegation.v1` call (telemetry
  only, never gates, no-op without a ledger); `lifecycle_state.recommend_execution_backend(ledger=…)`
  surfaces a `last_n_prior` prior additively (byte-identical to today with no ledger/data).
- **Docs** — `references/run-fact-ledger.md` (schema, chain custody + the tamper-evidence-not-resistance
  threat-model bound, derive-on-read views, adoption note) + DECISIONS `{#run-fact-ledger-401}`.

## [0.60.0] - 2026-07-05

### Added — remote gate approval over the fleet's own channel (#379)

Give the durable `/outcome` R20 frontier-approval gate a second, unattended delivery surface: the
fleet's own redis-channel / Discord bridge. When a gate holds while the terminal is unattended, its
prompt travels over the channel and the operator's reply becomes the durable approval — recording
**who** answered and over **which transport** as provenance (option A, 2026-07-05).

- **Provenance on the durable record** — `outcome_decompose.approve_frontier(...)` gains keyword-only
  `answerer` / `transport`, written into `approvals/r{rev}.json` only when supplied (a terminal
  approval stays byte-identical; `frontier_approved` is existence-only, so the extra keys are
  backward-compatible). `outcome approve` gains `--answerer` / `--transport`.
- **New `outcome_gate_transport.py`** (stdlib-only, decoupled from redis-channel) — transport-agnostic
  `compose_gate_notice` (renders the gate id `<outcome_id>@r<rev>` + pending subplots + lettered
  choices), `parse_gate_answer` (accepts a reply **only** when it quotes a gate id in the caller's
  `pending_gate_ids`, reads `answerer` / `transport` from router-set inbound fields not the body, and
  never defaults to *approve*), and a redis-only `emit_gate_notice` programmatic seam.
- **Access deferred to the transport (option A / KTD2)** — sender authorization is enforced upstream
  of the session by the transport's own access policy (Discord `gate()` pre-filters to `allowFrom`;
  redis-channel defers to its router); the gate records provenance and correlates a pending gate, it
  never re-authorizes a sender. A channel message cannot forge or escalate an approval.
- **Documented contract** — `references/operator-choice.md` §5.1 (channel-transport gate delivery) and
  `redis-channel/PROTOCOL.md` (transport-agnostic gate notice/answer convention; redis-channel stays
  router-agnostic — docs-only there). Notice delivery is session-driven for both transports.

## [0.59.0] - 2026-07-05

- Feat: fleet-wide 429 handling adopts the shared fleet-commons `retry_backoff` primitive (#348).
  The emitted `.workflow.js` wraps every `parallel([...])` wave thunk and refute-N panel verifier
  `agent()` call in a `__retry` helper (bounded exponential backoff, `Retry-After` honored) so a
  rate-limited agent re-queues instead of counting as a wave failure; a non-429 error still throws
  and HALTs the wave (singleton `await agent()` calls are unwrapped by design). `/outcome` dispatch
  now classifies a 429 (`BackendRateLimitError`) as `retriable-pending` — a derived-on-read RESULT
  label (`AdvanceResult.retriable`), never a committed `NODE_STATE`: the 429'd leaf stays `ready`
  and the ready frontier re-picks it on the next `advance()` tick with no operator action and no
  git/ledger state change (a per-call `retriable_seen` guard de-hammers a loop=True run).

## [0.58.0] - 2026-07-05

- Feat: `/outcome start --from-objective <owner>/<repo>#<N>` seeds the DAG from a GitHub Objective's
  sub-issues (#375). Wires the previously-unwired `discover_subissues.py` GraphQL reader (extended with
  `stateReason` + `trackedIssues`) through a new library `fetch_objective`, builds one node per
  sub-issue with `kind` from labels, an authored terminal `state` for closed sub-issues (COMPLETED→done,
  NOT_PLANNED→rejected — structural spec state, never a committed status field), and a `github`
  provenance stamp the reconcile/board-sync consumers read.
- Feat: new `outcome_edges.py` — a pure, cycle-safe `edges_from_relationships()` that infers
  `depends_on` edges among the ingested sub-issues, dropping and reporting dangling/cyclic edges so the
  produced spec always passes `OutcomeSpec.validate()`. Edge inference is best-effort (uses only stable
  GraphQL fields) and degrades to no-edges; the no-flag `start` default is unchanged.

## [0.57.0] - 2026-07-05

- Feat: extracted `/outcome`'s certificate-gated autonomous board writer into a new plugin-agnostic
  `board_progression.py` (#344). The per-op mechanism (authorize via `reversibility_certificate` →
  idempotency-keyed ledger → bounded-retry write → fail-loud record) plus the production
  `default_board_writer` (the `OpKind` → mission-control verb mapping, moved from `outcome.py`) now
  live there behind a `write` CLI so the markdown skills can invoke it. `outcome_board_sync.reconcile_board`
  delegates to it with zero behavior diff (`outcome_store._write_once` injected to preserve exact
  atomicity + test-patchability); `_safe_ledger_name`/`_default_board_writer` are re-exported so
  `outcome_reconcile` and `outcome.py`'s call sites are untouched.
- Feat: `/work`'s post-merge phase now fires the allowlisted Status → Done and sub-issue-close moves
  autonomously through `board_progression.py` (no operator prompt); merge/deploy and any
  non-allowlisted op still return `GATE` and fall back to the operator-prompted `mission-control`
  path — the autonomously-writable set cannot widen because the allowlist lives in the certificate.
- Feat: `status_card.py` gains `project_arc`, a pure derived-on-read idea→deploy lifecycle arc
  (gate-sequence over durable saga fields only), rendered by `/loop` at Route/Drive/Resume. `/loop`
  renders and sequences but never writes the board itself (router first-principle preserved).

## [0.56.0] - 2026-07-05

- Fix: `ship_ceremony.py` could not resolve a task-kind saga (no `issue_ref`) once `checkout_main`
  moved off the work branch — by-branch resolution on `main` matched every other saga left there
  and raised `AmbiguousSagaError`, forcing manual `pull`/`branch_delete` cleanup. `run` now accepts
  `--saga-id` (resolved directly, ahead of `issue_ref`, surviving any branch change), and the
  by-branch fallback ignores terminal (`done`/`abandoned`) sagas so stale sagas left on a branch no
  longer force a false ambiguous match.

## [0.55.0] - 2026-07-05

- Feat: `ship_ceremony.py`'s `open_pr` transition now injects a `Fixes #N` line (parsed from the
  saga's `issue_ref`) into the PR body it creates, so merging auto-closes the tracked issue instead
  of leaving the manual close step to be forgotten. Only added when the saga names a numeric issue;
  the `Plan:` link is preserved alongside it.
- Fix: `saga.py`'s `save()` now also refreshes `head_sha`/`last_commit_sha` from live git on every
  save (the #480 follow-up), so they track the current commit instead of freezing at the mint-time
  HEAD (`status_card` renders `head_sha` as its CI reference). SHAs need no default-branch guard.

## [0.54.4] - 2026-07-05

- Fix: `saga.py`'s `save()` only auto-derived the `branch` field from live git state on a saga's
  first-ever save (`if not merged.branch`), so a saga minted by `/plan` on `main` — before its
  work branch existed — carried `branch="main"` for its entire life, even after `/work` re-saved
  it on the work branch. `branch` now refreshes from live git on every save whenever git reports a
  definite (non-empty) branch, so `ship_ceremony.py`'s `branch_delete` guard and `/code-review`'s
  branch-match see the real branch. The non-empty guard is retained so a detached-HEAD / no-git
  read never clobbers a stored value; `head_sha`/`last_commit_sha` keep first-save-only capture
  pending a follow-up (#480).

## [0.54.3] - 2026-07-05

- Fix: `ship_ceremony.py`'s `open_pr` transition, on the front-loaded/existing-PR path, flipped
  the draft PR ready (`gh pr ready`) without pushing the commits accumulated since `start()` opened
  it — so CI could validate a stale HEAD while real work sat unpushed. It now pushes the branch
  first, via a shared `_push_branch` helper also used by the `commit` transition (#478).

## [0.54.2] - 2026-07-04

- Fix: `ship_ceremony.py`'s `request_review` transition always failed (`gh pr edit --add-reviewer
  @me` is not a valid login for the `requestReviewsByLogin` mutation). It is now a deliberate
  no-op — this repository has exactly one human maintainer, who is also the sole author of every
  ceremony PR, so there is no one else to request review from (#477).

## [0.54.1] - 2026-07-05

- Reformat CHANGELOG version headings to the fleet's canonical grammar (bracketed version,
  hyphen-minus date) as part of the release-surface single-source generator work (#429).

## [0.54.0] - 2026-07-05

### Feat: ship_ceremony.py — resumable ship-ceremony transition primitive (#345)
- New `scripts/ship_ceremony.py`: an explicit, ordered transition table
  (`commit -> open_pr -> request_review -> merge -> checkout_main -> pull -> branch_delete`),
  resumable across process restarts by re-reading the governing issue's saga tick each
  invocation. Each transition records a local `CeremonyTier` reversibility tag
  (`reversible` / `additive` / `always_operator`) — a small local registry, not a reuse of
  `reversibility_certificate.py` (that module's own scope excludes repo-level git/merge ops).
- `saga.py save` gains `--ceremony-transition` / `--ceremony-tier` (new `CEREMONY_TIERS`
  constant); ceremony state rides the existing work-thread saga tick, no second store.
- Two entry points share the implementation: `/work`'s PR-ready flow (section 5.4 no longer
  hand-drives raw `gh pr create` / `gh pr merge` / cleanup commands) and a new local
  (repo-scoped) `git ship` alias, installed/uninstalled by the primitive itself — never a
  real git hook, so merge/PR-open/review-request stay explicitly operator-confirmed.
- A front-loaded `ship_ceremony.py start` mode, offered right after `/work`'s Phase 1.4 saga
  mint, pushes the branch and opens a draft PR carrying the plan link immediately; the later
  `open_pr` transition detects it and flips it ready instead of opening a second PR.
- Decision record: `docs/engineering-journal/DECISIONS.md#ship-ceremony-primitive-345`.

## [0.53.0] - 2026-07-04

### Refactor: tier palette re-exported from fleet-core through the vendored fleet-commons shim (#463)
- `execution_spec.py` now loads `MODELS` / `EFFORTS` / `_CHEAP_MODELS` / `ENGINE_INTENTS` through
  the vendored `scripts/fleet_commons_shim.py` (byte-identical to fleet-core's canonical copy,
  drift-guarded in CI) and re-exports them under their existing names — intra-saga importers and
  the existing suite are untouched. `PASS_RULES` stays saga-local (refute-N vocabulary, not tier
  vocabulary). Vocabulary content and ordering are unchanged; the ordering contract is documented
  at the canonical home (`fleet-core` 0.1.0, DECISIONS `{#fleet-commons-mechanism-463}`).

## [0.52.0] - 2026-07-04

### Feat: gate-divergence telemetry — rubber-stamp rate for operator gates (#399)
- New `gate_divergence` full-snapshot list field on the `Saga` envelope, sibling to
  `gate_verdicts` — each entry records a gate id, the offered default/recommendation, the
  operator's actual answer, a divergence bit, and (when available) the offer-to-answer latency.
  Entries are base64-wrapped JSON blobs, pipe-joined (KTD1): `gate_verdicts`' colon convention is
  safe only because its `state` is a closed 6-value enum, but `gate_divergence`'s `answer` field
  is arbitrary `AskUserQuestion` free text, so a raw pipe-joined blob could be corrupted by a
  literal `|` in an answer — base64 makes the encoding safe against that regardless of content.
- New `plugins/saga/scripts/gate_divergence_reader.py` (modeled on `override_rate_reader.py`'s
  R12 house pattern) reports a per-gate-id rubber-stamp rate, interaction count, and mean
  latency, with the same zero-data "no data yet" contract; read-only.
- `/retro` Phase 1.6a runs the new reader read-only alongside the existing R12 override-rate
  reader and includes its output in the evidence block.
- Instrumentation notes added at the 5 `AskUserQuestion` gate sites currently offering a
  recommendation or pre-selected default (`brainstorm`, `founder-review` — 2 distinct gates,
  `investigate`, `loop`, `outcome`); see
  `plugins/saga/references/gate-divergence-instrumentation.md` for the convention and `gate_id`
  naming.
- This is a measurement facet only: it does not change what any gate does, does not add new
  gates, and does not itself widen any autonomous-progression allowlist.

## [0.51.0] - 2026-07-03

### Feat: board↔saga reconciliation on resume — detect drift over the /outcome board-sync ledger (#295)
- `/outcome` gains **reconcile-on-wake**, the companion to #279's autonomous board-sync writer.
  #279 drives and records autonomous board writes but never re-reads the live board, so an
  outside writer (operator, CI, a review agent) who changes a saga-owned board field while saga
  is at rest was never noticed — and a recorded idempotency key made the next tick *skip* the op,
  so the drift persisted silently forever. Reconcile closes that loop.
- New `outcome reconcile <id> [--resolve <drift-id> --action accept-board|re-assert|hold]` verb,
  and `advance --autonomous` now **detects drift before any board write**: a detected drift
  drift-holds only the affected issue's ops (`{status: drift-hold}`) while other leaves proceed
  (KTD3, not gate-all), and drift/recovered records ride `AdvanceResult.drift`.
- Detection is pure classification over three per-issue views: **asserted** (latest of ledger
  write record + reconcile-override, KTD5), **expected** (recomputed from `derive_states` →
  `_candidate_ops` → the schema status map, so a landed-but-unrecorded write is reconciled by
  recomputation with zero change to #279's writer, KTD1), and **live** (`outcome_github.board_status`
  + `issue_close_info`). Scope is ledger-bearing issues only (KTD6) — an untouched issue is never
  probed, so no false positives.
- External closes are **contract-aware + stateReason** (KTD4): a `completed` close that satisfies
  a non-code leaf's completion contract stays the harvester's sanctioned silent path; a
  `not_planned` close, or a close on a code leaf (contract = PR-merged), is drift. An unreadable
  stateReason degrades to today's contract-only behavior.
- Resolution is **HITL behind a replaceable policy seam** (`decide(drift, policy=None)`, R8);
  accept-board / re-assert / hold are recorded as append-only `reconcile-override` records.
  re-assert `authorize_write`s FIRST, then re-drives through the injected `board_writer` — never a
  direct gh call (R9). No new autonomous writer, no new persistence, no mission-control change.
- New reads `outcome_github.board_status` (via `gh issue view --json projectItems`) and
  `issue_close_info` (state/stateReason + best-effort close author from the REST events endpoint);
  both mirror `issue_state`'s never-raise degrade-safe contract. `issue_state` is untouched.
- `plugins/saga/references/outcome-spec.md` documents the reconcile-on-wake contract, the
  saga-owned field class, and the drift-hold semantics.

## [0.50.0] - 2026-07-03

### Fix: verify-panel reconciliation recomputes over reporting verifiers, not declared n (#293)
- A runtime-missing verifier (a `null` verdict slot from a skipped or terminally-errored
  `agent()` call) was previously counted as "did not refute" while the pass-rule threshold
  stayed fixed at the declared panel size (`⌈n/2⌉` majority / `n` unanimous) — masking genuine
  majority refutations, the unsafe direction, across all three emission sites
  (`_emit_thunk`, `_emit_verify_loop_singleton`, `_emit_verify_panel`).
- The three sites are consolidated into one shared `_emit_panel_reconciliation` helper
  (mirroring the `_verifier_agent_opts` single-source precedent), which now records which
  verifiers reported vs. went missing (by index), recomputes the threshold over the reporters
  (`majority`: `max(1, ⌈k/2⌉)`; `unanimous`: `max(1, k)`), and logs an UNDER-STRENGTH marker
  when the reporting count falls under a baked `⌈n/2⌉` quorum floor of the declared `n`. A
  refutation over reporters still throws/retries regardless of under-strength — the floor only
  annotates the accept path, so a small quorum disagreeing is never silently suppressed.
- **No behavior change when every verifier reports**: the recomputed expressions are
  arithmetically identical to today's fixed threshold in the all-report case (`k = n`).
- `plugins/saga/references/execution-spec.md` documents the throw consumer (not `log()`-only),
  the recompute table, the quorum floor, the static-vs-runtime two-kinds boundary, and the
  known no-verifier-timeout residue (workflow scripts have no timer primitive).

## [0.49.2] - 2026-07-03

### Fix: documented fallback + registration drift guard for `saga:readonly-verifier` (#325)
- `saga:readonly-verifier` is mandated by `CLAUDE.md` and `sandbox-spawn-sites.md` for every
  ad-hoc verify/review-class spawn, but a session whose plugin roster predates the agent's merge
  (#287/#320) cannot resolve it — the spawn hard-fails with no documented degrade path. Root cause
  confirmed at plan time: a live spawn in a fresh session resolved and ran successfully, so this is
  environmental staleness, not a registration defect.
- `sandbox-spawn-sites.md` gains a two-step fallback ladder: `Explore` + `isolation: "worktree"`
  first (structurally omits `Edit`/`Write` while keeping `Bash`, preserving the read-only axis by
  tool omission), then `general-purpose` + worktree + an explicit read-only prompt instruction only
  if `Explore` is also absent. `CLAUDE.md`'s ad-hoc spawn rule now points to it.
- New `tests/test_agent_registration_drift.py` pins the repo-side preconditions of
  discoverability: agent frontmatter `name:` matches its file stem, `execution_spec.py`'s
  `READONLY_VERIFIER_AGENT_TYPE` matches the on-disk agent, every spawn-context
  (`subagent_type`/`agentType`) `saga:<name>` reference resolves to a real agent file, and the
  fallback section is documented. Scoped to spawn-context lines specifically — a bare
  `saga:<name>` grep would false-positive on skill mentions like `/saga:work`, which share the
  same namespace.

## [0.49.1] - 2026-07-03

### Fix: `/outcome` autonomous board-sync schema-resolves status instead of a hardcoded literal (#326)
- `outcome_board_sync._candidate_ops` mapped every `ready`/`dispatched` leaf state to a hardcoded
  `"In Progress"` — a campps-workflow value with no meaning on the operations/asgard `intent_flow`
  board (`Idea → Shaping → Ready → Active → Verify → Done`), where the autonomous write failed
  loud and repeated. Now resolves `ready`/`dispatched` from mission-control's `sdlc-schema.json`
  `saga_lifecycle.phase_board_map` for the target project — correct for every board, and
  decoupled from any future ladder change.
- `reconcile_board` and `outcome.advance` gain a `project` parameter (default `"operations"`),
  threaded to both the board writer and the status resolver so they can never disagree about
  which board they're targeting. Resolution is lazy (attempted only when a leaf is actually
  `ready`/`dispatched`) and, on failure (missing schema, unknown project), fails loud and
  retryably per-op — no ledger key written, so the next tick re-attempts — while the coalesced
  progress comment for the same leaf still posts.
- **Behavior change:** on `campps`, a `ready` leaf now resolves to `"Committed"` instead of
  `"In Progress"` — the schema-correct value for that board's `campps_initiative` workflow.
  `dispatched` on campps is unchanged (`"In Progress"`).
- `done` (`SUB_ISSUE_CLOSE`) and the deferred no-op terminals (`blocked`/`failed`/`rejected`/
  `stalled`) are unchanged.

## [0.49.0] - 2026-07-02

### Artifact-pointers saga envelope field (#291)
- New `artifact_pointers` field on the `Saga` dataclass and `FRONTMATTER_FIELDS`, beside the
  existing `review_paths` block (`saga.py:192-195/253-254/274-275`), plus an `--artifact-pointers`
  flag on the `save` subparser wired into `_build_save_saga` (beside `--review-paths`,
  `saga.py:1218-1219/1280`). Absent field round-trips byte-identical on existing sagas.
- Lets a saga record typed artifact pointers (git-object diff pointers, content-addressed store
  pointers, or symbol pointers — see team-execution 2.8.0) so spawned team-execution agents can
  dereference stored artifacts the saga points at instead of receiving them inlined (KD5).
- `/resume` now **consumes** the field: a restored tick's `artifact_pointers` are dereferenced via
  `artifact_pointer.py deref` to recover the exact artifact bytes (fail-closed on
  `POINTER_HASH_MISMATCH` / `POINTER_STALE`), closing the producer+consumer dead-wiring loop
  (LEARNINGS `{#dead-wiring-needs-producer-and-consumer}`). The field was producer-only before this.

## [0.48.0] - 2026-07-02

### Team-spawn residency guard (#289)
- New warn-only `PreToolUse` hook, `team_spawn_residency_hook.py`: when a team-execution
  reviewer or tester is spawned (`Agent` in this harness, `Task` on stock Claude Code) without
  the named-persistent-teammate shape S-1 (#275) mandates, emits a one-line
  `additionalContext` advisory pointing at spawning with `name` for `SendMessage`
  re-addressability. Never blocks, denies, or mutates the spawn.
- Trigger set (18 agents: 10 reviewers, 8 testers) is parsed fresh from
  `reviewer-registry.md` / `validator-registry.md`'s `## Testers` section on every
  invocation — no materialized manifest to drift. Scanners, monitors, and `deploy-watcher`
  are excluded.
- Registry directory resolved via a four-step chain (dev-repo sibling → versioned-cache
  install, reading the active version from `installed_plugins.json` with a max-semver glob
  as last resort → `CLAUDE_PROJECT_DIR` → bounded cwd-ancestor scan) so it resolves correctly
  under both the dev-repo layout and a marketplace-installed versioned cache.
- Registered as a third `PreToolUse` entry (matcher `Agent|Task`) alongside the existing
  `Edit|Write|MultiEdit` and `Bash` entries.

## [0.47.0] - 2026-07-02

### Capability-scoped agent sandbox (#287)
- `execution_spec.py` / `outcome_spec.py`: new optional two-axis `sandbox` envelope on `Unit`/`Node`
  — `mutation_policy` (read-only | read-write) × `workspace_isolation` (ambient |
  disposable-worktree | owned-worktree), with named profile shorthand (`read-only-verify`,
  `sandboxed-mutate`) that expands at parse. Absent ⇒ ambient × read-write (existing specs
  round-trip byte-identical).
- New `plugins/saga/agents/readonly-verifier.md` (read-only toolset: Bash/Read/Grep/Glob, no
  Edit/Write). All three verifier-emitting sites now emit `agentType: "saga:readonly-verifier"` +
  `isolation: "worktree"` unconditionally (KTD6), collapsed into one `_verifier_agent_opts` helper.
- Per-backend enforceability matrix (`SANDBOX_ENFORCEABLE_BY_BACKEND` +
  `unenforceable_sandbox_axis`): a restrictive sandbox a backend cannot enforce HALTS (never
  downgrades). `team_emitter.emit` raises `SpecError` at authoring time (KTD3);
  `outcome_dispatcher.dispatch` probes the matrix into an axis-naming `HaltReceipt`; unlisted
  backends (fork/subagent/goal/manual) default to halt (R4).
- External write-ceiling lift (`engine_dispatch.py`): a `sandboxed-mutate` agy unit ⇒
  `mode: "patch-only"` + `write_set` from the unit's files; a `sandboxed-mutate` codex unit HALTS
  (no write adapter). Default/read-only is byte-identical. The declared sandbox is recorded as
  optional `attribution.sandbox` on the provenance manifest (no `saga.manifest.v1` bump).
- New `plugins/saga/references/sandbox-spawn-sites.md` inventory + ad-hoc spawn rule + `CLAUDE.md`
  pointer; four verify/review skills (code-review/qa/investigate/resume) name the read-only
  verifier + worktree isolation.
- New tests: `tests/test_sandbox_clobber_contained.py` (a real disposable worktree contains a
  `git checkout` clobber; the primary tree's uncommitted work survives), plus
  `tests/test_sandbox_spawn_sites.py` and sandbox coverage across the spec/emitter/dispatch suites.

## [0.46.0] - 2026-07-02

### External-engine workers — plan-time tier recommendation + resolution preview (#318)
- `execution_spec.py`: new optional `Unit.engine_intent` (`offload` / `second-opinion`, valid only
  alongside `engine`/`capability`, defaults to `offload`) carries the KTD2 delegation intent that
  drives a team-execution chaperone worker's tier recommendation.
- `segment_units()`: an engine/capability unit now gets its own resident boundary
  (`worker-<engine>` / `worker-<capability>`, keyed on the bare engine id, not the full
  engine/variant selector) instead of grouping purely by file path — it never merges with a plain
  Claude segment or a different engine/capability, regardless of adjacent file paths.
- `team_emitter.py`: the `### Workers` table gains Engine/Intent columns rendering the new
  segmentation (`cap:<key>` for a capability route, `—`/`—` for Claude segments); new column-shape
  test oracles (none existed before this change).
- `/plan` SKILL.md's tier-derivation table gains the KTD2 intent→tier recommendation rows and the
  plan-time capability-resolution preview ("resolves today to `<engine>/<variant>`") that a
  team-execution chaperone's `substituted-engine` disposition compares the run-time resolution
  against.

## [0.45.0] - 2026-07-01

### Evidence / provenance manifests — verified-vs-adjudicated record per delegated output (#285)
- `provenance_manifest.py`: frozen-dataclass envelope (`schema: "saga.manifest.v1"`) with
  `output_completeness` (declared vs produced) and `claim_provenance` (producer-claimed vs
  Claude-adjudicated) subrecords, pure `is_parroting`/`mismatch_reason_for`/`validate` predicates,
  no verdict field, no I/O at import (R1-R9, R12, R18, R20).
- `manifest_store.py`: git-common-dir carrier at `<git-common-dir>/saga-manifests/<saga-id>/
  <execution-id>.json` (reusing `resolve_common_dir`), a typed `manifest_ref` payload-key helper for
  outcome leaves, and CLI `write`/`read`/`list`/`record-completeness` entry points (R19, R3, R10, R13).
- `outcome_orchestrator.py`: `harvest` attaches the advisory `manifest_ref` pointer to a leaf's
  CompletionEvent payload when its dispatch recorded a provenance manifest (saga id = outcome id,
  execution id = subplot id; canonical store layout only — advisory, R8).
- `engine_dispatch.adjudicate_manifest` keys adjudications by `(claim text, source_ref)` so two
  claims sharing text but grounded in different sources adjudicate independently.
- `manifest_store._safe_name` delegates to `outcome_store._safe_name` — one implementation of the
  traversal guard, translated into `ManifestStoreError`.
- `engine_dispatch.py`: new `build_dispatch_manifest`/`record_dispatch_manifest` let the driving
  session persist an envelope-backed manifest for a dispatch through `manifest_store` (`dispatch()`
  itself does not auto-emit); `satisfy_gate()` now enforces R11 — a gated verdict cannot persist
  unless gate-relevant claims are Claude-adjudicated.
- `completeness_gate.py`: renamed `check_manifest` → `check_required_keys` (no external callers) to
  free "manifest" for the new envelope; `classify()` behavior unchanged.
- `manifest_reader.py`: advisory reader (parroting count, disposition rate, adjudicated-verified
  ratio) wired into `/code-review`, `/qa`, and `/retro` as a non-blocking signal (R7, R8, R15, R16,
  R18).
- `saga-spec.md` gains the manifest contract section (envelope/subrecord field reference + R17
  producer/reader matrix); a guard test enforces no manifest field ships without a live-or-scheduled
  reader.
- Enabled `fable`/`xhigh` execution-spec tiers (#285 U0) so judgment-heavy units (schema, gate
  semantics) can run on Claude Fable 5 xhigh.

## [0.44.0] - 2026-07-01

### External-engine capability routing — right engine, effort, protocol per task (#283)
- New saga-owned registry + resolver + dispatch adapter mapping a logical capability or an explicit
  engine to `{engine, effort, protocol}` and dispatching external LLM engines (Codex via
  `codex:codex-rescue`, Gemini via `agy:delegate`) as gated generators / advisory reviewers /
  non-gated workers, with Claude as verifier-of-record on every gated decision (R13).
- `engine-registry.yaml` (editable data, R4): per-variant capability profiles, prompting protocols,
  invocation recipes, a `cost_speed_rank` tie-break key, context-window limits, and per-row source
  attribution. Seeded 2026-06-27 for codex/gpt-5.5-{high,xhigh} and agy Gemini 3.5 Flash / 3.1 Pro.
- `engine_resolver.py`: capability-XOR-engine resolution (advisory/dispatch modes), role_kind-gated
  fallback (worker/generator) vs halt (reviewer/panel), byte-verbatim payload assembly (R9/R11),
  context-window fitness halt (R25), preflight availability, and `resolve_role` panel expansion (R16).
- `engine_dispatch.py`: an `AdvisoryEvidence` result type whose `satisfy_gate` structurally requires
  Claude verification before any gated return; failure statuses -> halt + provenance note (R24).
- execution_spec Units gain optional mutually-exclusive `engine`/`capability` selectors (backward
  compatible); the emitter routes engine-bearing units through an external-engine dispatch marker.
- `/doc-review` gains an opt-in cross-family external-reviewer panel. Records the binding
  "external engines are never gatekeepers" decision (DECISIONS.md).

## [0.43.0] - 2026-06-30

### PreCompact spore — re-ground the continuing session on structured facts (#281)
- New two-hook "spore" that guards the mid-run auto-compaction boundary: a `PreCompact` hook freezes the
  active saga box + the OutcomeOrchestrator DAG frontier (derived-on-read via `outcome.status`) to a
  session-keyed, worktree-stable cache `<git-common-dir>/saga-spores/<session_id>.json`; a separate
  `SessionStart(source=compact)` hook reads it, unlinks before emitting (at-most-once), and re-injects it
  as a self-describing `additionalContext` block so the continuing session re-grounds on structured
  facts, not the lossy prose summary.
- New `saga_spore.py` core (pure, offline-testable): active-saga resolution, leaf-id + bounded-scan
  outcome discovery (never guesses on ambiguity), DAG freeze, deterministic ≤9k serialization with the
  ready frontier **never dropped** plus a counted-drop pointer, and the dump/load seam with a
  `saga_id` + repo-root mismatch guard.
- Both hooks degrade silently **and** on a hard 1.5s wall-clock deadline (SIGALRM) — compaction is never
  blocked or stalled. The existing `/resume` path, tick chain, and `state.json` model are untouched
  (additive cache; the spore is the anchor, never the authority).
- Hooks registered in `hooks.json`: `PreCompact` (matcher `auto|manual`) + a sibling `SessionStart`
  (matcher `compact`, separate from the existing `startup|resume` entry).

## [0.42.0] - 2026-06-29

### Reversibility/idempotency certificate + autonomous `/outcome` board-sync (#279)
- New `reversibility_certificate.py` — one pure-data authority that declares each board op's
  reversibility facts and answers a single `authorize_write` verdict (AUTHORIZED / GATE, **default
  GATE**) over a closed, enumerated `OpKind` allowlist with declared inverses. Merge, deploy, and
  parent-issue-close (`ALWAYS_OPERATOR`) are never authorized.
- Subsumption: `degrade_decision`'s `had_side_effect → HALT` and `outcome_projection`'s parent-close
  are now derived from the certificate — behavior byte-identical (proven by a 672-combination
  equivalence sweep), with the certificate as the single source of both reversibility facts.
- New `outcome_board_sync.py` — the first autonomous consumer. `outcome advance --autonomous`
  reconciles each leaf's derived state to reversibility-authorized board writes (set-field "In
  Progress", sub-issue close, label add/remove, one coalesced progress comment), idempotent on a
  **separate** write-once board-sync ledger, with bounded retry + fail-loud surfacing. The default
  `advance` performs no board writes; GATE'd ops surface to the operator, never silently skip.
- Pairs with mission-control 2.4.0 (the new issue-write verbs the consumer drives).

## [0.41.0] - 2026-06-29

### Operator gate-status card (#278)
- New `status_card.py` — one shared, derived-on-read glyph-card renderer that is the single emitter of
  operator-facing status across all five saga surfaces. Constant-size, position-stable; every
  determinable cell is traceable to evidence via an indexed footer, and no operator-writable status
  field exists. Two archetypes (one renderer): gate-sequence and summary-projection (U1).
- A frozen six-value wire-state enum (`done` / `in-progress` / `blocked` / `failed` / `halted` /
  `not-reached`) with an additive operator-label + glyph display map and a raw-string fallback; an
  undeterminable cell renders *unknown* with no ref — never a guessed glyph (U1).
- `gate_verdicts` capture in the saga work-state envelope: a full-snapshot `list[str]` of
  `"gate:state:ref"` entries plus a repeatable `--gate-verdict` CLI flag and a `parse_gate_verdict`
  helper (splits on the first two colons so colon-bearing refs survive; validates the six gate
  states) (U2).
- Per-surface projections: `project_work` / `project_code_review` / `project_qa` (gate-sequence) and
  `project_outcome` / `project_resume` (summary-projection). `/work`'s Tests cell derives from
  `gate_verdicts`; `/outcome` re-renders `outcome_projection.project()` exactly (no second
  projection); `/qa` renders a failing verdict unmistakably (U3/U4).
- Routed all five surfaces' status-summary emissions through the card while keeping per-finding
  evidence as drill-down detail; `/work` now writes `gate_verdicts` on its test gate (U5).

## [0.40.0] - 2026-06-29

### Silent-omission completeness gate (#277)
- New `completeness_gate.py` oracle — the single source of omission semantics: a `FailureClass`
  enum (`missing-output` / `malformed-output` / `verifier-disagreement`, extensible), pure check
  predicates (presence, truncation, fan-out count, manifest-key), `classify()`, and a `--self-test`
  CLI that plants the four canonical omission fixtures (U1).
- `emit_workflow_script` now injects a single `__gate(result, opts)` helper (porting the oracle
  semantics to JS) and a guard call after every unit-result `agent()` site — the singleton and each
  `parallel` var — so an omission HALTS the workflow instead of passing `null`/partial downstream;
  the verify-panel verifier agents are excluded (U2).
- A refuted verify panel now HALTS with a typed `verifier-disagreement` throw instead of
  `log()`-and-proceed (R4), plus an opt-in bounded iterate-to-consensus override on `Verify`
  (`iterate_to_consensus` + `max_iterations`, `< 1` rejected at validate) (U3).

## [0.39.0] - 2026-06-28

### Worker×model cache scheduling (#275)
- Add a `files` field to `Unit` and a pure `segment_units()` that derives resident-worker
  segments — contiguous plugin-directory grouping, upgrade-only segment tier, and collapsed
  segment-level dependencies — without mutating the shared `ExecutionSpec`.
- `team_emitter` now emits one worker row per resident-worker segment
  (`Agent | Units | Tier | Mode | Depends-on`) instead of one row per unit.

## [0.38.0] - 2026-06-26

### OutcomeOrchestrator (outcome-orchestration feature — built across U1–U11, co-equal at release; the U11 feature-flip ships it)

- **U11** — **Feature flip + integration gate.** Advertise the complete `/outcome` surface and ship all
  34 requirements: saga metadata (`plugin.json` description + `marketplace.json`) advertises the outcome
  coordinator; the README + `docs/commands.md` + `docs/README.md` + `docs/boundaries.md` command counts
  move to **20 files / 19 routable** (the `/outcome` 19th routable); the Command Matrix visual gains the
  `/outcome` coordinator card; `tests/test_outcome_integration.py` drives a full outcome end-to-end
  through the **production** `advance` wiring (start → approve → **dispatch** → GitHub-canonical harvest →
  auto-merge → liveness → cost rollup → report → projection) on a DAG, proving the U1–U10 units compose
  (the dispatch seam is load-bearing — completion only flows after a leaf is dispatched). team-execution
  metadata already carries no tmux/setup (U4's R8 reshape). Released at saga 0.38.0 (the version-triad:
  `plugin.json` == `marketplace.json` == this heading).
- **U11 (R26/R27 persistence — closed the ship-gate P0).** `outcome.commit_spec` **commits + pushes the
  canonical spec to the outcome's own branch** (`outcome/<slug>`, **refuses on `main`/`master`** — R26
  "not main mid-run"), so a **different machine reconstructs the whole outcome by pulling the repo** then
  re-harvesting completion from GitHub, with no dependence on the local cache (R27/F5). Exposed as
  `/outcome commit [--push]` and `/outcome advance --persist` (commit each tick on an unattended run); the
  *cadence* is operator/`/loop`-driven, the *mechanism* now ships. `save_spec` no longer falsely claims to
  persist (it writes the working tree; `commit_spec` does the git write).
- **U11 (auto-merge dependency gate).** `process_merge_queue` now merges a code leaf only once **all of
  its `depends_on` are success-complete** — GitHub's mergeability does not model the outcome DAG, so a
  coincidentally-clean PR for a leaf with an incomplete (especially non-code) upstream is no longer
  squashed out of dependency order (R12 + the DAG).

- **U1** — Add the canonical outcome spec + DAG validator (`scripts/outcome_spec.py`,
  `references/outcome-spec.md`, `tests/test_outcome_spec.py`): a JSON outcome document
  (superset-in-pattern of `ExecutionSpec`) modelling a concurrent DAG of subplots with a per-node
  operational state machine in data (KTD2 — `state`/liveness/negative-state hooks/`child_spec_ref`),
  the Kahn `dependency_layers` + `ready_frontier` frontier engine, and a `validate` that rejects
  duplicate id / self-dep / cycle / missing dep / invalid `child_spec_ref` (incl. collision with a
  sibling `subplot_id`) **before any dispatch** (R20, R31 validation). Disconnection is a non-fatal
  advisory (`structural_warnings`), not a hard failure — independent workstreams under one objective
  are legal; the "forgot to wire it in" smell (R33) is surfaced consistently for a lone isolate and a
  multi-node island. Fail-loud `from_dict` coercion (a string `depends_on` is rejected, not
  char-iterated; `bool`/float liveness budgets and non-positive `spec_revision` are rejected);
  `redirect_dependency` is atomic (a rejected redirect never advances the revision or decision-trail,
  R26 fidelity). Pure functions, deterministic JSON round-trip, no I/O at import. (U1 covers the
  structure facet of R26 and the spec-container slice of R1/R2/R21/R33; the cross-facet machinery —
  GitHub completion, sub-issue projection, the coordinator runtime, decompose/promote — lands in
  later units.) Survived a 3-lens adversarial-verify pass (validator-bypass / round-trip / requirements
  honesty); the P1 redirect-atomicity + P2 string-edge/orphan-rule defects it surfaced are folded in.
- **U2** — Add the outcome **store** (`scripts/outcome_store.py`, `tests/test_outcome_store.py`,
  `tests/test_outcome_replay.py`): the git-common-dir cache + coordination substrate beside the
  canonical spec + GitHub (KTD15). Resolves its root from `git rev-parse --git-common-dir` so the cache
  is shared across every worktree but never committed and **deleting it loses no canonical state**
  (R27). Primitives: immutable write-once **completion events** (one file per leaf per attempt via
  `os.link`; idempotency-key dedup with a genuine new-attempt retry proceeding, R9/R10/R28); atomic
  `os.replace` writes + malformed-file **quarantine** (no torn read, R30); an append-only **replay
  ledger** (`O_APPEND`) tolerating a torn trailing line, with `replay_pending` pairing intents to
  commits so a crash after a side effect but before its commit re-drives idempotently (R30); lease-based
  **coordinator + per-subplot dispatch locks** (a second `advance` no-ops on a held lease, reclaims a
  stale one; no duplicate dispatch, R13); and an **offline queue** with the R34 policy made concrete
  (GitHub wins for completion → a server-superseded queued write is dropped; retry exhaustion pages the
  operator). Dependency-injected `runner`/`now` → unit-testable offline with no real git repo or wall
  clock; no I/O at import. (U2 ships the cache/durability facets of R9/R10/R13/R14/R27/R28/R30/R34; the
  parent-owned barrier predicate lands in U5, real GitHub/export wiring in U5/U6/U7.)
- **U3** — Add the thin `/outcome` command + skill + the reconcile engine (`commands/outcome.md`,
  `skills/outcome/SKILL.md`, `scripts/outcome.py`, `tests/test_outcome_command.py`): the
  **OutcomeOrchestrator** coordinator over a DAG of leaf sagas. A **level-triggered reconcile loop**
  (R29) — each `advance` tick reconstructs live state from the durable store, dispatches the ready
  frontier to executors via an injected dispatcher, and pages only on exceptions; it holds no
  authoritative in-memory DAG (crash-tolerant, host-agnostic). Enforces two invariants structurally:
  the **coordinator routes, never executes** (R2/R3 — `advance` only dispatches + harvests, never runs
  a leaf's work in-process; the record-only default dispatcher proves it, real backends arrive U4/U9),
  and **status is derived on read** (R17 — node live-state is computed each call from spec + completion
  events + dispatch records, never a stored field). Idempotent (the per-subplot dispatch lock + ledger
  record dedup repeated ticks); a second concurrent `advance` no-ops on the held coordinator lease
  (R13). Thin coordinator verbs only (KTD11/R16): `start` / `graph` / `advance` / `attend` / `resume` /
  `status` / `export` / `import` — `attend` prints the native `/resume <leaf-saga-id>` handoff; leaf
  work stays the native verbs (no `/outcome work`). Ships the R14 export/import portable bundle. Wired
  into the saga docs model + manual card (`/outcome` is in the source but the marketplace version flip +
  advertisement stay deferred to U11). (U3 ships R16/R29 + the dispatch-seam facet of R1/R3; the degrade
  path, real backends, decompose/report/close verbs land in later units.)
- **U4** — Add the backend **dispatcher seam** + make team-execution the first real backend
  (`scripts/outcome_dispatcher.py`, `tests/test_outcome_dispatcher.py`; promotes the by-mode fork in
  `scripts/execution_spec.py`). The single seam every subplot routes through (R5): it dispatches a leaf
  to its backend — minting a leaf saga id + a `/resume` **return channel** (the R9 re-entry token out) —
  or, when the chosen backend cannot run, emits a **visible HALT-not-degrade receipt** (`BackendHaltError`
  + `HaltReceipt`) rather than silently substituting a lesser backend (R5/R23). **team-execution is the
  first runnable backend** (R6); the rest of the menu (fork / subagent / cc-workflows-ultracode / `/goal`
  / manual) HALTs until U9, never a silent inline fallback. Wires the existing `team_emitter` as the
  **third leg of `recompile_for_tier`** (`team-execution` mode now recompiles to the `## Team Structure`
  markdown protocol, not the inline baseline — R5). The **production `/outcome advance` CLI now routes
  through the real seam** (`make_dispatcher`); the U3 record-only dispatcher is the test/skeleton fallback
  only. A HALT is handled **per leaf** in the reconcile loop: the leaf's dispatch lock is released (so a
  re-tick re-surfaces it rather than a leaked lease masking it for the TTL), the receipt is recorded in
  the ledger and returned in `AdvanceResult.halted`, and reconcile **continues** to other runnable leaves
  — one unavailable backend never starves the frontier and a HALT is never silently substituted. (U4
  ships R5/R6-first-backend + the R23 HALT receipt; the operator-presence degrade-vs-halt *decision* and
  the full backend menu land in U9.) The destructive **R8 reshape of team-execution** ships in that
  plugin's own 2.2.0 bump (see `plugins/team-execution/CHANGELOG.md`): tmux + `/team-setup` removed,
  validator-state check re-homed.
- **U5** — Add the **completion barrier** + GitHub-canonical completion read + harvest + cascade
  (`scripts/outcome_orchestrator.py`, `scripts/outcome_github.py`, `tests/test_outcome_completion.py`).
  "Done" is a **parent-owned barrier predicate over the returned evidence** (R9), never a child's
  self-report, HALTing on an unmet contract. Per-subplot completion **contract** (R11): a **code** leaf
  is done only when its **PR reads merged**; a **non-code** leaf when its **tracking sub-issue reads
  closed** (the cache-less-reconstructable canonical marker) or, untracked, a `canonical`-flagged
  completion event (cache-resident only — a wipe loses it; tracked work uses the issue path); a
  **child-outcome** node (`child_spec_ref`, KTD10) only when the child's terminal state reads
  successful — the production harvester **recurses** into the child outcome (cycle-guarded) to read it.
  `outcome_github` is the read-only PR/issue-state primitive (merged/closed/open) — **degrades to
  `unknown` on any `gh` failure, never a false completion** (R34); the merge/close *actions* are U6.
  `harvest` runs the barrier each tick and **materializes** GitHub-canonical completions as success
  events in the store (at a fresh attempt slot, so a prior negative terminal never collides), unlocking
  the next Kahn layer (R10) and surviving a cache wipe (re-derived from GitHub, R27). `blocked_subtree`
  is the R22 cascade — only a block's downstream subtree pauses, independent siblings keep running.
  **Wired into the production `/outcome advance` CLI** via an injected `harvester` (`AdvanceResult.harvested`),
  so a merged PR / closed issue unlocks dependents in the live loop. (U5 ships the **barrier-predicate
  half of R9** — the re-entry-token-out is U4's dispatch — plus R10/R11/R22 + the R27/R28 completion-read
  leg the U2/U3 honesty passes deferred here; the auto-merge action + negative-state cascade land in U6.)
- **U6** — Add the **auto-merge queue** + GitHub negative terminal states (`scripts/outcome_merge.py`,
  `scripts/outcome_github.py` write side, `tests/test_outcome_merge_queue.py`). A non-gated, clean code
  subplot **auto-merges** (server-side squash) to unlock dependents (R12). Merges are **serialized**, and
  **GitHub is the authoritative atomic guard** (not a local SHA compare): `gh pr merge --squash
  --match-head-commit <head>` is rejected by GitHub if the PR is not mergeable — base moved (`behind`),
  conflict (`dirty`), head moved, or required checks unmet — so a **stale tree can never be squashed**
  (R12/R30). The loop classifies via GitHub's `mergeStateStatus`: `behind` → **rebase (update-branch)
  then re-verify**; `dirty` → **conflict** (fail the leaf back to `work` + page, never a silent skip);
  `blocked` → wait for gates (the CI-green/review evidence is GitHub's own readiness); a rejected squash
  → **reloop**, base churn **capped at 3** → halt + page (no spin). **R34 safe-degrade:** an `unknown`
  merge-state or unreadable base (gh outage) **defers** (`not-ready`) — a gh outage never fails a leaf or
  merges wrongly. **Negative GitHub terminals** (R32): a PR **closed-unmerged** or a **definite-404
  deleted branch** records a sticky `rejected` terminal that **cascades** like a block (R22); an
  out-of-band merge is never double-merged; a `conflict` records a **retryable** `failed` terminal
  (re-enters the queue once /work fixes it — only `rejected`/`stalled` permanently skip). **Wired into
  the production `/outcome advance`** (`merge_processor`, `AdvanceResult.merges`) under the held
  coordinator lease, so it is single-writer **cross-process** too (R13). GitHub ops are an injected
  `MergeOps` adapter → fully unit-testable offline. (U6 ships R12 + R32-PR/branch + R22 negative cascade +
  R30 merge atomicity; the worktree-removed terminal is U7, the degrade decision U9.)
- **U7** — Add **decomposition + in-flight graph editing + the durable per-sub-outcome worktree
  lifecycle** (`scripts/outcome_decompose.py`, `scripts/outcome_worktrees.py`,
  `tests/test_outcome_graph_edit.py`, `tests/test_outcome_worktrees.py`). **Graph editing** (R21/R33): the
  four growth mechanisms — `add_node`/`prune`, `lazy_grow`, `elaborate` (splice a node into sub-nodes,
  inheriting its upstream + rewiring its dependents onto the sinks), `promote` (set `child_spec_ref`,
  rejecting a point-back at this/any **ancestor** outcome — the cross-spec cycle guard U1 deferred) — each
  **atomic** (snapshot → validate → bump revision + decision-trail; a rejected edit leaves the spec
  untouched, R26) and **state-aware**: a **dispatched** node may not be pruned or elaborated (would
  silently discard in-flight work) — a terminal transition must come first (R33). **Orphan
  reconciliation** (R33): a prune drops every edge to the node, **closes its generated sub-issue**
  (injected adapter; U8 produces the ref), and **reaps its worktree** — no zombies. **Draft-then-review
  approval gate** (R20): approval is recorded **per `spec_revision`**, so any structural edit (which bumps
  the revision) **re-closes** the gate — no layer dispatches before the operator approves the current
  frontier's edges. **Worktree lifecycle** (R15): one durable, named, owner-tagged worktree **per
  sub-outcome** (`child_spec_ref` node), **reused across its leaves** (not one-per-leaf); a hard **cap**
  defers past N (never an (N+1)th worktree); heavy installs **shared** across siblings via one
  `shared_install_ref`; reaped on terminal. **git is the liveness oracle** (the U6 lesson): a worktree
  removed **out-of-band** is detected from `git worktree list` and reaches the **defined `rejected`
  terminal** (R32 — the one U6 deferred) that **cascades** like a block (R22); a transient git failure
  degrades to **present** (never falsely terminates a live sub-outcome, R34). Paths are **canonicalized to
  git's absolute realpath form** on both sides (and `--repo-root` is resolved), so a relative or symlinked
  root can never read a live worktree as absent (which would silently break both the cap and R34). **Wired into the production
  `/outcome advance`**: a `worktree_processor` (reap + worktree-removed terminal + provision, under the
  held coordinator lease) and a `gate_factory` (the approval gate), plus new `/outcome approve` / `prune` /
  `promote` verbs (`AdvanceResult.worktrees` / `.gated`). Both `WorktreeOps` (git) and `issue_close` are
  injected → fully unit-testable offline. (U7 ships R13-namespacing + R14-graph-portability + R15 + R20 +
  R21 + R32-worktree + R33.)
- **U8** — Add the **derived-on-read report + attention consolidator + mission-control projection**
  (`scripts/outcome_report.py`, `scripts/outcome_projection.py`, `docs/outcomes/_example-ship-auth/`,
  `tests/test_outcome_report.py`, `tests/test_outcome_projection.py`). **Attention consolidator**
  (R18/AE5/F3): when several leaves need the operator at once, `consolidate()` bubbles them into **one**
  ranked prompt — **type-tier first** (a *gate* = ready-to-ship → an *ambiguity* = needs-a-decision → a
  *failure* = needs-a-fix), then **unblock-leverage** within a tier (the item gating the most downstream
  work first, `len(blocked_subtree)`); each node classified into **one** kind (terminal-negative →
  failure, HALT receipt → ambiguity, gated/risky/destructive + dispatched → gate); a healthy steady state
  consolidates to an empty surface. **Report** (R19/F6): `/outcome report` regenerates
  `docs/outcomes/<id>/report.md` from state — the Mermaid topology, the consolidated prompt, a per-subplot
  state + evidence + cost table, the cost rollup (**rendered when present, "no data yet" when absent** —
  so U8 depends only on U5/U6, **never on U10**, avoiding a U8↔U10 cycle), and the decision trail (the
  "why" for cold re-entry, F5). **Deterministic** (no wall-clock in the body) + **overwritten from
  state**, so it physically cannot drift. **Projection** (R25): `/outcome project` emits the
  mission-control **secondary** portfolio view, **generated** from the spec + store (no operator-writable
  status, R17) and **never auto-closes the parent** (`parent_close = operator-keystroke-only`). New
  `/outcome report` / `project` verbs + a consolidated `/outcome attend` (no subplot → the ranked prompt).
  (U8 ships R17 + R18 + R19 + R25 + AE5 + F3/F5/F6.)
- **U9** — Add the **full backend menu + the presence-conditional degrade policy + leaf liveness**
  (`scripts/outcome_dispatcher.py` extended, `scripts/outcome_liveness.py`, `references/operator-choice.md`
  §8, `tests/test_outcome_backends.py`, `tests/test_outcome_liveness.py`). **Full menu** (R6):
  `resolve_available()` exposes the host-conditional set — the always-available floor (`inline` /
  `team-execution` / `manual`) plus the host-dependent `fork` / `subagent` / `goal` / `cc-workflows-ultracode`
  (off by default; enabled via `--host-capable` / `--workflow-available`). **Presence-conditional degrade**
  (R23/AE1): `degrade_decision` — an unavailable backend **HALTs** when the operator is attending / the
  leaf is guarantee-bearing (`guarantee_tags` or `degrade_policy="halt"`) / it already side-effected (a
  `destructive` leaf), else **degrades one rung** down the `cc-workflows-ultracode → team-execution →
  inline` ladder (recording a visible `DegradeReceipt` surfaced in the report's **Degradations** section)
  when the leaf is autonomous and the operator is away; a backend off the ladder HALTs (no silent
  substitution, R5). **Liveness** (R31): `outcome_liveness.harvest_liveness` reclaims a dispatched leaf
  that breaches its `heartbeat_seconds` / `timeout_seconds` budget as the **`stalled`** terminal (pages
  once, cascades R22); `record_heartbeat` pushes back the deadline. **Frontier-budget + fork-cost levers**
  (R7): `recommend_outcome_backend` downgrades a per-leaf `cc-workflows-ultracode` recommendation to
  `team-execution` on a wide frontier, and `fork_is_cheap` claims the fork lever only when model + system
  + tools match the parent within the cache TTL. **Wired into the production `/outcome advance`**: a
  `liveness_processor` (under the held lease) + `available` / `attending` (`--autonomous`) driving the
  degrade decision in `_reconcile_once`; `AdvanceResult.liveness` / `.degraded`. (U9 ships R3 + R5 + R6 +
  R7 + R23 + R24-telemetry-capture + R31.)
- **U10** — Add **realized economics + the optimize/retro consumers** (`scripts/outcome_costs.py`,
  `skills/optimize/SKILL.md` §Outcome-economics, `skills/retro/SKILL.md` §1.7,
  `tests/test_outcome_economics.py`). **Producer** `record_cost` (a leaf saga reports its realized
  executor / tokens / wall-clock / operator-touches / retries / evidence into the shared store — the
  coordinator never runs the leaf, R3). **Consumer** `rollup` aggregates per outcome (R24): summed
  tokens/operator_touches/retries, `by_executor`, and the load-bearing **DAG-vs-one-thread** answer —
  `wall_seconds_parallel` (the critical path) vs `wall_seconds_serial` (the one-long-thread sum) +
  `beat_one_thread` — the falsifiable cost-vs-operator-time proof. Honest: an empty rollup is **"no data
  yet"** (never a fabricated zero), missing leaves are **counted** (`leaves_with_cost` / `leaves_total`)
  not summed as 0, and cost against a **pruned** subplot is reconciled into **`sunk`** (the pruned-node
  cost reconcile U7 deferred, R33). **Wired** as a `cost_processor` in `advance` that **materializes the
  rollup into `spec.cost_rollup`** (the producer → spec → U8-report edge — no U8→U10 dependency, the
  acyclicity rule). `/optimize` cites the rollup as a portfolio baseline + the override-rate reader;
  `/retro` adds a §1.7 read-only outcome-economics evidence pass. (U10 ships R7 + R24, and fills the U8
  report's "no data yet" cost slot + the U7 pruned-node cost reconcile.)

## [0.37.0] - 2026-06-21

- Document the parallel-layer + refute-N emitter constructs in `references/execution-spec.md`:
  topological-layer parallelism (KTD4) — independent units in the same dependency layer emit as a
  single `parallel([...])` wave; `Unit.verify` (KTD5) — optional refute-N judge-panel with `n` and
  `pass_rule` fields, default `n=3/majority`, hard cap `VERIFY_N_CAP=7`; `pass_rule` vocabulary
  (`majority`/`unanimous`); `/plan` author-validate-approve-persist-emit five-step flow for
  `cc-workflows-ultracode`; spec naming convention.
- Document the `/work` halt-not-degrade guarantee and `orchestration_ref` lifecycle in
  `references/operator-choice.md` §6: a `cc-workflows-ultracode` choice is guarantee-bearing (parallel
  fan-out + refute-N); `/work` halts when the Workflow tool is absent or the spec/ref is missing rather
  than silently substituting inline subagents; `orchestration_ref` points at the **spec JSON** at
  `/plan` time (canonical artifact — the `.workflow.js` is regenerable), then is overwritten with the
  workflow id after `/work` launches; the `saga.py` provenance guard backstops substitution attempts.
- Add `DECISIONS.md` entry `#parallel-refuteN-emitter-plan-work-wiring` covering KTD1-KTD7 rationale
  and the dogfooding fix (auto-derive must not fire on no-orchestration-args ticks).
- Bump saga to **0.37.0** (feature: parallel + refute-N emitter, /plan + /work wiring, provenance guard).

## [0.36.0] - 2026-06-21

- Generalize the stale-main `SessionStart` hook to run in ANY git repo. The hook
  (`plugins/saga/hooks/stale_main_session_hook.py`) is now fully SELF-CONTAINED — it no longer
  depends on the repo-local `tools/stale_main_guard.py` (which remains the repo's manual tool /
  R18 artifact), so the distributed plugin's hook is active everywhere saga is installed (user
  scope), not just this repo.
- Preconditions, each → exit 0 SILENT: CWD is inside a git repo (`git rev-parse --show-toplevel`);
  an `origin` remote exists (`git remote get-url origin`); the default branch is determinable.
- Default-branch detection is GENERIC (never hardcodes `main`): `git symbolic-ref --short
  refs/remotes/origin/HEAD` stripped of the `origin/` prefix, falling back to probing
  `origin/main` then `origin/master` via `git show-ref --verify`.
- Auto-fast-forward when safe (the chosen policy): if the local default branch is behind
  `origin/<default>` AND the current branch IS the default branch AND the tree is clean, the hook
  runs `git merge --ff-only origin/<default>` and confirms. Otherwise (feature branch, dirty tree,
  or a linked worktree) it WARNs only and mutates nothing. `git fetch origin` degrades quietly
  when offline. Always non-blocking (exit 0); emits the standard SessionStart `additionalContext`
  shape only when there is a message.
- Tests (`tests/test_stale_main_session_hook.py`) rebuilt around REAL temp git repos (bare origin
  + clone + advanced origin) — no mocks of git: not-a-repo (silent), no-origin (silent), up-to-date
  (silent), behind-on-default-clean (auto-FF actually moves the branch), behind-on-feature-branch
  (warn only, branch not moved), and a `master`-default repo (detected + handled).

## [0.35.0] - 2026-06-21

- Install the stale-main guard as a `SessionStart` hook (`startup|resume`). New wrapper
  `plugins/saga/hooks/stale_main_session_hook.py` reads the SessionStart payload from stdin,
  resolves the CWD repo root via `git rev-parse --show-toplevel`, and runs the repo's OWN
  `tools/stale_main_guard.py` — surfacing its output as SessionStart `additionalContext`
  (`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`).
- Repo-presence guard keeps the distributed plugin INERT elsewhere: if the CWD is not a git repo,
  or `tools/stale_main_guard.py` is absent at the repo root, the hook exits 0 silently (no
  `git fetch`, no subprocess). Always non-blocking (exit 0); degrades quietly on any error/timeout.
- Wire the new `SessionStart` event into `plugins/saga/hooks/hooks.json` (the plugin's 4th hook).
- Tests (`tests/test_stale_main_session_hook.py`): a fake repo-local guard exercises the wrapper
  end-to-end without any real `git fetch` — repo-without-guard (inert), not-a-git-repo (silent),
  guard-stale (warning reaches `additionalContext`), guard-silent (no output).

## [0.34.0] - 2026-06-21

- Wire the R12 producer path so override-rate telemetry is no longer inert. `saga.py save` gains
  `--orchestration-recommended` and `--orchestration-operator-choice` (both `choices=ORCHESTRATION_MODES`,
  default empty); `_build_save_saga` now sets `orchestration_recommended` from the flag and
  `orchestration_operator_choice` from its flag, defaulting to `--orchestration-mode` (the operator's
  chosen backend IS their choice). Backward-compatible: absent flags → `""`; older sagas still load.
- `/plan` (Phase 5.3) and `/work` (Phase 1.4) now instruct recording `--orchestration-recommended`
  alongside `--orchestration-mode` on each orchestration decision, so `override_rate_reader` sees real
  recommended-vs-chosen data instead of "no data yet".
- Tests: end-to-end producer→consumer test drives the real `saga.py save` twice (an override + a match)
  then asserts `override_rate_reader` reports non-zero data; a MultiEdit invalid-JSON case for the
  marketplace validation hook.

## [0.33.0] - 2026-06-21

- Add R12 override-rate reader (`scripts/override_rate_reader.py`): scans saga envelopes and
  surfaces override-rate, over/under-tier direction, and budget-exhaustion (capability
  degradation) signals. Zero-data reports "no data yet" (no divide-by-zero). Read-only; CLI
  supports `--json` for machine output.
- Wire the reader into `/retro` Phase 1.6: a dedicated evidence-gathering step runs the reader
  and includes its output verbatim; reference added to the SKILL.md reference-files section.
- Signal accrues post-merge as `/plan` records recommended vs operator-chosen backends (U3);
  this surface enables evidence-driven default re-weighting (R12's intent).

## [0.32.0] - 2026-06-21

- Capability-portable degradation (R11 / U12): every authored plan now carries a runnable
  inline/serial **baseline** alongside the dynamic-workflow script, so a plan executes on ANY
  host. Add `execution_spec.emit_inline_baseline()` (the always-runnable floor — no Workflow
  tool, no `agent()` harness; preserves every unit and its per-unit `{model, effort}` tier and
  enumerates fan-out targets) and `execution_spec.recompile_for_tier()` (re-emit the same spec
  for a possibly-downgraded orchestration tier). New `execution_spec.py baseline` CLI subcommand.
- Add `lifecycle_state.recheck_orchestration_capability()`: on an off-host resume it re-checks the
  Workflow tool and recompiles **only** the orchestration tier DOWN
  (`cc-workflows-ultracode → team-execution → inline`), preserving unit specs + per-unit tiers and
  surfacing a one-line downgrade note. AE3: it never errors and never silently runs nothing — an
  unknown or unavailable tier floors to the always-runnable inline baseline. New
  `lifecycle_state.py recheck-capability` CLI subcommand.
- Record the downgrade durably: add the `orchestration_downgrade` saga field (one-line note;
  empty on a host that ran the authored tier; backward-compatible default for older sagas).
- Document the degradation flow in `references/execution-spec.md` and the new field in
  `references/saga-spec.md`.

## [0.31.0] - 2026-06-21

- Add `scripts/execution_spec.py` (R9 keystone): the structured execution-spec schema and the
  Claude Code workflow-script emitter. `/plan` authors **one** spec (units with a per-unit
  `{model, effort}` tier, return contracts, dependency barriers, escalations, and enumerated
  fan-out targets) and emits a runnable `.workflow.js` from it; saga records only an
  `orchestration_ref`, never vendoring backend machinery.
- Enforce two authoring-time invariants at EMIT time so a mis-built spec fails loudly: a fan-out
  unit with no enumerated targets fails emit (R10, never a silent filter), and a pilot at a
  different tier than its fan-out fails emit (R3, a mis-tiered pilot is an invalid oracle).
- Bake the `workflow_structuredoutput_budget` lesson (cap output, mandatory final emit, skim, batch)
  into generated cheap-tier (haiku) agents, and bake enumerated-target post-run reconciliation into
  fan-out agents.
- Add `references/execution-spec.md` documenting the spec shape, the R3/R10 invariants, and the CLI
  (`validate` / `emit`).

## [0.30.0] - 2026-06-21

- Add `plugins/saga/agents/mechanical-executor.md`: cheap-tier (haiku, Bash-only)
  op-discriminated executor agent for deterministic mechanical ops dispatched by saga
  commands.  Approved ops: `census` (file enumeration), `file-exist` (path presence),
  `json-validate` (JSON parse check), `grep-count` (pattern match count), `link-check`
  (HTTP 2xx probe).  Unknown ops are rejected with a clear error message — never guessed.
  The agent is inert until called; it has no auto-trigger.  Addresses R16 / Epic 4 (U14).
- Update `plugins/saga/skills/work/references/execution-strategy.md`: add a `mechanical-executor`
  dispatch paragraph to the subagent dispatch section, naming the approved ops, the haiku/Bash-only
  scope, the op-discriminated rejection contract, and an example dispatch payload.  Wires the
  agent into the saga `/work` dispatch path without duplicating agent prose.

## [0.29.0] - 2026-06-21

- Add `tools/gate-manifest.json`: single-source declarative listing of the pre-push gate steps
  (`ruff format --check`, `ruff check`, `validate_plugins`, `validate marketplace`, `pytest`),
  each with an `id`, `label`, `command`, and `failure_hint`.  This file is the sole authoritative
  gate definition — the hook reads it at runtime and never diverges.  Addresses R15 / KTD10
  (Epic 3 hook harness, U9).
- Add `plugins/saga/hooks/pre_push_gate_hook.py`: a `PreToolUse` / Bash hook that fires when the
  Bash tool runs a `git push` command.  Reads `tools/gate-manifest.json` relative to the repo root,
  runs every step in order, and reports by exception — silent on pass, prints each failed step's
  label, output, and failure hint to stderr then exits 2 (blocking) on any failure.  Cross-repo-safe:
  degrades silently when the manifest is absent.  Co-located with U7/U8 in `hooks/hooks.json`.
- Update `plugins/saga/hooks/hooks.json`: add a `PreToolUse` / `Bash` matcher entry wiring
  `pre_push_gate_hook.py` into the hook harness alongside the existing JSON validator (U7) and
  journal nudge (U8).
- Add `tests/test_pre_push_gate.py`: 20 tests covering manifest structure (5 required step IDs,
  uniqueness, all fields present), push detection, exit-code contract (silent on pass, exit 2 on
  failure, exit 0 on non-push/non-Bash/malformed/missing-manifest), failure reporting (all failing
  steps listed, output echoed, hints included), and the single-source invariant (hook executes
  manifest-defined steps, not a hard-coded list).

## [0.28.0] - 2026-06-21

- Add `plugins/saga/hooks/journal_nudge_hook.py`: a non-blocking `PostToolUse` hook (exit 0 always)
  that fires on a `feat`/`fix` Bash commit touching code files with no `docs/engineering-journal/`
  entry staged, and prints a one-line nudge to stderr.  Does not write the entry and does not block.
  Ships cross-repo-safe: degrades silently when the journal dir is absent or git is unavailable.
  Co-located with U7 in `hooks/hooks.json` under a new `PostToolUse` / `Bash` matcher.
  Addresses R14 (Epic 3 hook harness, U8).

## [0.27.0] - 2026-06-21

- Add `plugins/saga/hooks/hooks.json` and `hooks/validate_json_hook.py`: the repo's first hook.
  A `PreToolUse` hook that JSON-parses `marketplace.json` and `plugin.json` on every
  `Edit`/`Write`/`MultiEdit`, asserts balanced brackets, and exits 2 (blocking) with the
  offending file path and line on failure.  Unrelated files pass through silently (exit 0).
  Addresses R13 (Epic 3 hook harness).

## [0.26.0] - 2026-06-21

- Split the recommender's `needs_consensus` signal on the **governance** axis (R7 keystone). A consensus
  signal is no longer an unconditional hard-force to `team-execution`: `recommend_execution_backend`
  gains `consensus_is_gated` (default True). **Gated** consensus (the verdict must block a merge/deploy and
  persist as evidence) → `team-execution`; **advisory** consensus (throwaway in-session votes) is OR'd into
  the existing `adversarial_confidence` ultracode trigger → `cc-workflows-ultracode`. A
  contested-but-not-gated job now reaches the advisory judge-panel and never regresses to `inline`.
- Add `--advisory-consensus` to the `recommend-backend` CLI so the markdown caller can reach the advisory
  branch; gated stays the default when the flag is omitted.
- Add the KTD4 gated-vs-advisory interrogation question + work-shape default to `skills/plan/SKILL.md` §5.2
  (default *gated* when deploy/security/persist signals are present, *advisory* otherwise; the operator
  confirms).
- Update `references/operator-choice.md` §3.1 to record the gated/advisory governance split and that only
  gated consensus reaches `team-execution`.
- Cover AE1 (advisory → ultracode), AE2 (gated → team), the overlap case, the docs-gating case, and the
  CLI round-trip in `tests/test_saga_plugin.py`.

## [0.25.0] - 2026-06-21

- Rewrite the `/plan` (`skills/plan/SKILL.md`) and `/code-review` execution-backend offers to name
  **both** dynamic-workflow purposes from `operator-choice.md` §3.2 — **breadth / scale** fan-out **and**
  **adversarial confidence** (judge-panel / refute-N / perspective-diverse) — instead of underselling
  `cc-workflows-ultracode` as fan-out only (R5).
- Reframe the team↔workflow fork on the **governance** axis ("does the verdict need to stick?" — gated
  consensus that blocks a merge/deploy and persists vs. advisory throwaway votes), not on "review depth"
  (which both backends have) (R6).
- Add `tests/test_operator_choice_drift.py` — a drift guard asserting every offer surface stays a
  SUPERSET of the §3.2 purpose list (anchored on stable content markers, not line numbers), so a future
  rebuild cannot silently drop a purpose or reintroduce the "review depth" framing.

## [0.24.0] - 2026-06-21

- Add `orchestration_recommended` and `orchestration_operator_choice` fields to the saga envelope
  (R12 — choice-vs-recommendation recording). Enables override-rate computation in `/retro`+`/optimize`.
  Both fields default to `""` so pre-0.24.0 sagas parse without error (backward-compatible additive
  evolution per §9 of the saga spec).
- Add `ORCHESTRATION_MODE_LABELS` display-label map to `saga.py` (`cc-workflows-ultracode` →
  "dynamic workflows", `team-execution` → "team execution", `inline` → "inline") and a
  `display_orchestration_mode()` helper that falls back to the raw enum string on a miss — never errors
  (R8 / KTD5).
- Route all offer-surface prose in `/plan`, `/work`, `/code-review`, `/loop`, `/founder-review`,
  `/optimize`, and `/retro` skills through the display labels so operators see "dynamic workflows"
  in descriptions while the stored enum string `cc-workflows-ultracode` remains the frozen wire
  contract (carried in persisted sagas and `--orchestration-mode` CLI choices, byte-for-byte unchanged).

## [0.23.0] - 2026-06-20

- Add the `/promote` skill — the workspace tier of the engineering journal. It promotes the *select few*
  cross-repo "transcendent" learnings into `infiquetra-context-library`'s `LEARNINGS.md` as distilled,
  pull-only org standards: a manual, gated, agent-judged pass with two feeders (the `/retro`-declared
  `**Transcendent.**` marker and a recurrence net over legacy `**Generalizable rule.**` lines). It mirrors
  `/ideate`'s cross-repo grounding, clusters the same lesson across repos by judgment (no vectors), and
  upserts ONE entry per lesson behind a propose-diff-and-wait gate. READ-ONLY on the SDLC; writes only to
  context-library; never writes back to source repos.
- Add `scripts/promote_scan.py` — the deterministic backbone: enumerate `*/docs/engineering-journal/
  LEARNINGS.md`, parse the marker + legacy-rule variants, compute the drift-stable `<repo>:<hash>` source
  key, read context-library's `promote-keys` ledger to drop already-promoted candidates, exclude
  context-library and self-feed entries (two layers), group exact-recurrence clusters, and render the
  idempotent gated upsert (create / update / noop). The marker form, key recipe, parser, entry template,
  and ledger are frozen in `skills/promote/references/promotion-contract.md` (the single source of truth).
- Teach `/retro`'s Phase-4 curation to propose the `**Transcendent.**` marker on the select cross-repo
  learnings (the single-repo, propose-diff-and-wait declare feeder).

## [0.22.1] - 2026-06-13

- Tighten the `adversarial_confidence` guidance: `/work` sets `--adversarial-confidence` only on an explicit
  operator request for many-independent-attempt verification (refute-N / judge-panel / perspective-diverse),
  never inferred from generic "make me more confident" phrasing — closes the oversell risk the adversarial
  review flagged. The trigger stays categorical; a true magnitude gate remains a documented revisit-when.
- Journal bookkeeping: record the 0.22.0 squash SHA (`331505a`).

## [0.22.0] - 2026-06-13

- Correct the execution-backend recommender (`recommend_execution_backend`) and the operator-choice contract
  so `cc-workflows-ultracode` (ultracode) is no longer framed as "fan-out, not review depth": ultracode
  delivers deterministic fan-out **and** independent/adversarial verification. The line to `team-execution`
  is GOVERNANCE (reviewer consensus + named scanner gates + guarded deploy), not review depth.
- Add `adversarial_confidence` as a second `cc-workflows-ultracode` trigger beside `broad_independent_fanout`
  (CLI `--adversarial-confidence`): prove-by-refutation / judge-panel work with no deploy/security signal now
  reaches ultracode instead of silently falling to `inline`.
- Add `has_code_surface` (default True; CLI `--no-code-surface`) so pure docs/spec/research output neutralizes
  the output-blind team-execution proxies — `file_count`, `phase_count`, and the `parse_issue.py` keyword
  flags `has_infra` / `has_security` / `deployment_sensitive` that fire on a doc merely *mentioning* infra or
  auth. `cross_repo` (ownership boundary) and `needs_consensus` (contested) survive as the output-agnostic
  governance signals; the ultracode risk-suppressor is itself gated by `has_code_surface` so broad infra/
  security DOCS still fan out.
- Reword operator-choice §3.1 (`PLUS` -> `OR`, matching the code's sufficient-on-its-own consensus) and §3.2
  (the corrected ultracode framing + the throwaway-signal-vs-standing-verdict mechanical boundary).

## [0.21.0] - 2026-06-09

- Add a comprehensive Saga documentation system: README atlas, manual pages under
  `plugins/saga/docs/`, curated source model, and generated SVG visual kit.
- Document every Saga command as a comparable decision card, including the 18 command-file /
  17 routable-command distinction and the `/ceo-review` -> `/founder-review` alias.
- Add dedicated lifecycle, state/readiness, scenario, boundary, and visual-maintenance pages.
- Add `plugins/saga/scripts/render_docs_visuals.py` to generate presentation-ready SVG assets from
  `plugins/saga/docs/model/saga-docs-model.yaml`.
- Add `tests/test_saga_docs_coverage.py` to guard command coverage, alias handling, derived
  readiness maturity, scenario coverage, manual links, source references, and visual inventory.

## [0.20.0] - 2026-06-07

- Add a shared formatting contract, `saga/references/formatting-style.md`, linked by all nine
  doc-writing skills (ideate, plan, brainstorm, spec, strategy, retro, doc-review, code-review,
  founder-review). It mandates scannable output: ≤3-sentence blank-line-separated paragraphs, a
  one-line summary opening each ranked item/section, comparative data as tables, the compact
  engineer-facing schema fields rendered as a table (narrative fields stay prose), no-hard-wrap
  soft-wrap for generated output, and dropping fields a heading already carries. (#201)
- Fix the triggering case: `ideate`'s `ideation-artifact.md` SURVIVOR SCHEMA no longer stacks
  bold-label lines (the CommonMark collapse that read as "all jumbled together") — it now leads with
  a one-line summary and renders the schema as a table.
- Enforce it: `tests/test_saga_doc_formatting.py` fails CI on a stacked-bold-label collapse and on
  any doc-writing skill that does not link the contract.

## [0.19.0] - 2026-06-05

- Rename the engine plugin to `saga` (Scheme Y plugin-family rename) and fold `blueprint-reviewer`
  into it. Metadata/marketplace change; no command behavior change. (#199)

## [0.18.0] - 2026-06-04

- Rebuild `/optimize` from a 20-line stub into a **metric-driven optimization engine** — the
  **thirteenth and final command rebuild** of the engine-merge campaign (after `/office-hours`,
  `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`,
  `/retro`, `/investigate`, `/spec`). It runs a **bounded-experiment loop** toward a measurable
  target: pick a metric, baseline it, hypothesize, run a bounded experiment, measure the delta,
  keep or discard, repeat until the target is hit or the budget is spent.
- **Honest attribution — single source, no merge.** `/optimize` is a **CE `ce-optimize`
  single-source PORT**. The **agent-usability** metric class is an **infiquetra-native** angle
  (Jeff's), **NOT a gstack port** — a full-file grep of gstack `plan-tune` for the agent-usability
  terms returned **zero**; `plan-tune` is a developer-psychographic question-coach that supplies
  nothing portable and is not ported. This is **NOT a merge** of any kind, and gstack is credited
  with **no insight**.
- **Off-chain, saga UNTOUCHED.** `/optimize` writes no saga, advances no `lifecycle_phase`, and
  makes **no `saga.py` edit** (mirrors `/strategy` / `/spec`). **No new Python** — no
  `handoff_envelope.py` edit either; the `docs/optimize/` handoff source dir is deliberately
  **deferred**.
- **Eight metric classes (the maximal v1 taxonomy):** performance, cost, reliability,
  **agent-usability**, security, quality, developer-experience, maintainability.
- **OFFERS operator-choice** for independent experiment fan-out (default serial inline); the choice
  is recorded **narratively** (saga-untouched) — not via an `orchestration_mode` saga field.
- **Campaign-closer.** With `/optimize` shipped, **all 13 command rebuilds of the engine-merge
  campaign are complete.** (Scope: this closes the *command-rebuild* campaign; `/pulse` live
  telemetry and other enhancements remain separate, queued items.)
- **Periphery** — version bumps (plugin `0.18.0`, marketplace entry `0.18.0`; keywords stay at 10);
  dispatch-table `/optimize` row flipped stub → shipped (metric-loop engine, advisory + off-chain),
  routing-rubric row updated, plus a `/qa`-vs-`/optimize` boundary note (gate-to-ship vs
  loop-toward-target); `operator-choice.md` `/optimize` row "at its rebuild" → "now, offers";
  README `/optimize` command-summary line tightened to the bounded-experiment loop + 8 metric
  classes. Dispatch-table command count stays **17** (`/optimize` was already counted).
- Documented in the engineering journal (PR #197): DECISIONS `#optimize-engine-rebuild`, ARCHIVE
  `#optimize-engine-rebuild-shipped` + the campaign-complete capstone (closes
  `#lifecycle-engine-merge-campaign`), LEARNINGS `#shipped-on-origin-not-in-stale-local-tree` +
  the third firing of `#campaign-brief-merge-is-a-provenance-hypothesis`; consumed
  `#optimize-engine-merge` from QUEUED, added `#optimize-log-helper`.

## [0.17.0] - 2026-06-04

- Add `/spec` — the lifecycle's net-new **spec-interrogation engine** and the **twelfth command
  rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`). It
  owns the relentless **WHAT-rigor** — the sibling of `/plan`'s HOW-rigor. A **gstack `spec`
  single-source port** of the WHAT-interrogation half: the principal-engineer-who-refuses-ambiguous-work
  persona, the HARD GATE (no spec after message 1 — always start the interview), Phase-1 five-Why,
  Phase-2 scope / MVP / out-of-scope / failure-mode lock, Phase-3 **read-code-first grounding** (cite
  `path:line` before asking, with a non-code escape), quantify-everything, and a draft-review pass.
- **Honest attribution — single source, no merge.** There is **NO CE spec engine** (ce-plan is
  `/plan`'s planning engine, not ported here), **NO /ideate+/brainstorm graft** (the
  assumption-challenge + failure-mode register is native to gstack's persona — the failure-mode bank
  already lives in `/plan/references/interrogation.md`, itself a gstack port), and no superpowers
  borrow. `/spec` and `/plan` split one source along the **WHAT vs HOW** altitude axis. The `/spec`
  SKILL does not duplicate `/plan`'s interrogation register. Sheds the entire gstack preamble,
  dedupe machinery, codex quality gate, two-layer redaction, `--execute` worktree spawn, gh issue
  authoring/filing, and the `~/.gstack` store.
- **Off-chain, saga UNTOUCHED.** `/spec` writes no saga, advances no `lifecycle_phase`, and makes no
  `saga.py` edit at all (mirrors `/strategy`). Its only durable output is a sharp WHAT artifact under
  `docs/specs/`. **No new Python.**
- **Q2 handoff wiring — the functional edit.** `handoff_envelope.py` now treats `docs/specs/` as an
  auto-discoverable handoff SOURCE: added `Path("docs/specs")` to `SOURCE_DIRS`, and
  `infer_maturity()` maps `docs/specs/` → `requirements-ready` (equals the existing default — a spec
  is a sharp WHAT, **not** plan-ready — set for consistency with the other source dirs, not a
  behavior change). `infer_lifecycle_phase()` leaves `docs/specs/` returning `"unknown"` (off-chain,
  no lifecycle phase). `references/saga-spec.md` §3.3 and `skills/handoff/SKILL.md` document the
  `docs/specs/ → requirements-ready` doc-path mapping; no `spec` phase is added to `LIFECYCLE_PHASES`.
- **Q4 + operator-choice honesty.** An offered `/doc-review` pass on a spec hits the **requirements**
  lens (`docs/specs/ → requirements` path tie-breaker added), not the blueprint route.
  Operator-choice **never offers** for `/spec` — a single durable spec artifact, no parallelism to
  escalate; size/risk lives in its scope sections and the downstream executor (`/plan` / `/work`)
  owns backend selection.
- **Brainstorm-seam resolution (decision d).** The `#brainstorm-spec-interrogation-seam` is resolved
  in favor of a **standalone `/spec`** that owns WHAT-rigor; `/brainstorm` stays the divergent
  explorer. `/brainstorm`'s Phase-4 handoff menu now offers **Sharpen with `/spec`** (divergent
  `/brainstorm` → convergent `/spec`).
- **Periphery** — version bumps (plugin `0.17.0`, marketplace entry `0.17.0`; keywords stay at 10);
  dispatch-table now **total over 17 routable commands** with `/spec` added (off-chain advisory route,
  routing OUT to `/handoff` / `/plan` / optional `/doc-review`); README `/spec` command-summary line.
  Two deferral closures: `operator-choice.md` `/spec` row "at its rebuild" → "never offers";
  office-hours `frame-diagnostic.md` `/spec` moved from "campaign-queued" to an active routing-rubric
  row.
- Documented in the engineering journal (PR #195): DECISIONS
  `#spec-interrogation-engine-rebuild`, ARCHIVE `#spec-interrogation-engine-shipped` +
  `#brainstorm-spec-interrogation-seam-resolved`, LEARNINGS
  `#campaign-brief-merge-is-a-provenance-hypothesis`; consumed both `#spec-interrogation-engine` and
  `#brainstorm-spec-interrogation-seam` from QUEUED.

## [0.16.0] - 2026-06-04

- Add `/investigate` — the lifecycle's net-new **systematic-debugging engine** and the **eleventh
  command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`). It answers "what is
  actually broken, and why?" — the diagnostic brain `/qa` (the gate) deliberately does not own. A
  **CE `ce-debug` spine** (causal-chain gate, falsifiable predictions for uncertain links, assumption
  audit, Phase-0 triage with trivial fast-path, smart-escalation, parallel read-only sub-agent
  dispatch) + **gstack `investigate` grafts** (the pattern-signature table — race/null/state/integration/config/cache
  — the two distinct numeric stop gates (hypothesis-exhaustion + 3-failed-fix), and the DEBUG REPORT
  Status enum) + a **superpowers
  systematic-debugging borrow**. Drops gstack scope-lock/freeze and all gstack runtime bins.
- **Diagnosis-primary, never a fixer.** `/investigate` produces a DEBUG REPORT (file:line, causal
  chain, regression-test path, Status enum) and **routes** the work out: a real fix → `/work` (via a
  `/handoff` issue); an applied inline fix → `/work` or `/code-review` to ship; a trackable defect →
  `/handoff`; a design-level root cause → `/brainstorm`. It does not commit, push, open/merge a PR, or
  deploy.
- **Saga READ-ONLY — zero saga edits.** `/investigate` reads saga context for evidence but writes no
  saga; **off-chain** (advisory, never blocks `/loop`). `saga.py`, `handoff_envelope.py`, and
  `references/saga-spec.md` are untouched. **No new Python** — `/investigate` is a markdown engine
  (SKILL + references + command). Verification is **own-minimal** (carries its own light verification),
  NOT a call back into `/qa`, overriding the pre-decision "verification CALLS /qa".
- **Full `/qa` cross-engine rewire — closes the deferred route at every site.** `/qa` deferred deep
  post-merge root-cause failures to "when `/investigate` is built." Building it closes that deferral
  **everywhere** (5 `/qa` SKILL mentions + 2 other-file notes): `/qa`'s post-merge FAIL branch is now
  **two-target** — deep-root-cause failures route to `/investigate` (now on the dispatch-table's
  routable list), clear/trackable defects still route to `/handoff`; pre-merge still routes to `/work`.
  Routing still **reads** `loop/references/dispatch-table.md`. No `/investigate`→`/qa` verify loop.
- **Periphery** — version bumps (plugin `0.16.0`, marketplace entry `0.16.0`; keywords stay at 10);
  dispatch-table now **total over 16 routable commands** with `/investigate` added (off-chain failure
  route); README `/investigate` command-summary entry; `operator-choice.md` + office-hours
  `frame-diagnostic.md` `/investigate` notes moved from "at its rebuild" / "campaign-queued" to active.
- Documented in the engineering journal (PR #193, squash 5079d8f):
  DECISIONS `#investigate-systematic-debugging-engine-rebuild`, ARCHIVE
  `#investigate-systematic-debugging-engine-shipped`, LEARNINGS
  `#deferred-cross-engine-wiring-must-close-on-build`; consumed from QUEUED.

## [0.15.0] - 2026-06-03

- Rebuild `/retro` from a 19-line stub into the lifecycle's **meta-improvement engine** — the **tenth
  command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`). A **real 3-source merge**, not a
  port: gstack's `retro` + `learn` passes merged with CE's `ce-compound` framing into one engine that
  captures lifecycle learnings, distills durable knowledge, and proposes improvements to the workflow
  itself.
- **Six net-new passes on top of the merged retro+learn+compound base** plus a lean metrics surface —
  the FULL engine shipped in v1, nothing deferred. `/retro` runs as a single command with an optional
  pass argument so a focused sub-pass can be invoked directly.
- **Tiered self-edit gate — the safety contract for a self-modifying engine.** Pure-additive,
  append-only journal writes auto-apply; every delete / modify / move of existing durable state
  (memory, directives, the lifecycle plugin's own SKILLs) is **propose-diff-and-wait**, and any
  global / cross-project edit carries an extra cross-project-impact warning. The blast radius is the
  full self-modification surface **including the lifecycle SKILLs**, gated rather than narrowed.
- **In-repo vs global/cross-project directive disambiguation.** `/retro` distinguishes a repo-local
  directive from a global / cross-project one and warns before touching cross-project surfaces.
- **Saga READ-ONLY — zero saga edits, no §11 change.** The planned `->retro` saga advance was dead
  wiring; it is dropped. `/retro` reads saga context but writes none, so `saga.py` and `saga-spec.md`
  are untouched. **No new Python** — `/retro` is a markdown engine (SKILL + references + command) that
  reuses existing helpers; the windowed mode keeps a stale-base guard scoped to that mode.
- Version bumps: plugin `0.15.0`, marketplace entry `0.15.0`. keywords stay at 10 (unchanged).

## [0.14.0] - 2026-06-03

- Rebuild `/strategy` from a 21-line stub into the lifecycle's **interview-driven STRATEGY.md
  engine** — the **ninth command rebuild** of the engine-merge campaign (after `/office-hours`,
  `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`). A **faithful
  single-source PORT of CE `ce-strategy`**, NOT a merge: gstack has **no** strategy engine — `cso/`
  is the Chief **SECURITY** Officer (a 14-phase security audit), so the pre-audit "gstack cso ≈ Chief
  Strategy Officer" mapping was a name-match mixup. CE `ce-strategy` is the sole engine source.
- **The whole engine, ported.** Rumelt-grounded kernel (diagnosis / guiding-policy / coherent-action)
  + Phase-0 file-state routing (new STRATEGY.md vs targeted-section update vs pick-a-section) +
  Phase-1 **8-section interview with a mandatory 2-round pushback per section** + a **locked
  root-`STRATEGY.md` template** (3-5 metrics, 2-4 tracks) + rerunnable update-in-place. All 8
  sections and the Rumelt kernel are kept (no trimming).
- **Agent-as-customer is persona-only.** Personas may name AI-agent actors **when the product is
  agent-consumed**; **tracks stay pure investment areas / domains of work, NOT actors**. The QUEUED
  brief's blanket "personas/tracks must name AI-agent actors" was half a category error — tracks are
  domains of work, not actors — caught by reading the real CE `interview.md` section semantics.
- **Zero saga edits, off-chain / pre-saga.** `/strategy` owns the durable `STRATEGY.md` direction
  and writes no saga (like `/founder-review`, it runs upstream of the work loop); `/founder-review`
  challenges the direction, `/strategy` records it. **No new Python** — `/strategy` is a markdown
  engine (SKILL + references + command). `saga.py` is untouched.
- Version bumps: plugin `0.14.0`, marketplace entry `0.14.0`. keywords stay at 10 (`strategy` was
  already a keyword; unchanged).

## [0.13.0] - 2026-06-03

- Rebuild `/qa` from a 19-line stub into the lifecycle's **gate-only acceptance-evidence engine** — the
  **eighth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`,
  `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`). A **real two-engine merge** against
  the cloned gstack source (`/qa` + `/qa-only` + `/investigate`) plus a CE `ce-debug` graft, **not** a
  phantom port: `/qa` adopts gstack's own report-only `/qa-only` model — it tests, gathers evidence,
  assigns severity, derives a verdict, and routes, but **never fixes, commits, pushes, opens/merges a
  PR, or deploys**.
- **Severity-banded verdict + a ported deterministic health score, reported alongside each other.** Each
  finding carries critical / high / medium / low (with a documented ↔ P0-P3 cross-walk to `/code-review`);
  pass/fail is stated per risk class and the overall ship verdict (`ship` / `ship-with-deferred` /
  `no-ship`) is derived from the tier's blocking threshold — and that verdict is the gate decision. A new
  deterministic scorer `scripts/qa_health_score.py` **ports gstack's Health Score Rubric**
  (`scripts/resolvers/utility.ts:286-321`, injected as the `{{QA_METHODOLOGY}}` macro): gstack's deduction
  values verbatim (critical -25 / high -15 / medium -8 / low -3) with documented infiquetra 9-way
  ship-risk-class weights, re-normalized over the in-scope classes, plus a baseline-from-prior-report
  delta. The 0-100 number is reported **alongside** the banded verdict, with the explicit caveat that its
  inputs are LLM-assigned severities — so it is one signal, not the gate decision.
- **Saga qa-track consumer — lands the deferred work→qa advance.** `/qa` `restore`s the work-thread
  saga, writes `qa_paths`, and **on PASS advances `lifecycle_phase` from `work` to `qa`** — the advance
  `/work` (0.10.0) explicitly deferred to this rebuild. On FAIL it keeps `lifecycle_phase=work` and
  records evidence. Every flag already exists (`--lifecycle-phase qa`, `--qa-paths`, the `qa` phase) —
  **zero `saga.py` edits**.
- **Durable risk reference + falsifiable-prediction graft.** Ships a `references/risk-taxonomy.md`
  (9-way risk router + per-class checklists + diff-aware file→class map + severity defs + the P0-P3
  cross-walk; gstack's 7 web categories fold under behavior/browser as **one MCP-driven class**, a
  graceful no-op off-UI) and `references/qa-report.md` (the report shape + ship-verdict derivation +
  tier→blocking-threshold table). Grafts CE `ce-debug`'s **falsifiable-prediction** discipline: for
  each uncertain-cause failure, state a prediction another path must also fail if the cause is real,
  giving the routed fixer a head start.
- **Merge-state failure routing.** PASS routes to `/handoff` or `/retro`; FAIL routes by merge state —
  pre-merge to `/work` (re-enter the round-N loop), post-merge to `/handoff` (open a new defect
  thread). `/investigate` is future-prose only (not on the dispatch-table's routable list). Routing
  **reads** `loop/references/dispatch-table.md`, never restating it.
- **One new script.** The Q2 final ports gstack's formula into `scripts/qa_health_score.py` (the scorer)
  with an oracle test; otherwise `/qa` is a markdown engine (SKILL + 2 refs + command + the scorer +
  tests), and `saga.py` is untouched. Also resolves the present-tense `docs/qa/` collision with the
  `/optimize` stub (one-line `/optimize` → `docs/optimize/`).
- Version bumps: plugin `0.13.0`, marketplace entry `0.13.0`. keywords stay at 10.

## [0.12.0] - 2026-06-03

- Rebuild `/resume` from a 23-line "read committed docs first" doc into the lifecycle's **heavy
  forensic reconstruction engine** — the **seventh command rebuild** of the engine-merge campaign
  (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`) and the
  **unblocked heavy partner** the `/loop` rebuild (0.11.0) explicitly deferred to it. `/loop` owns the
  **lightweight** scan → restore → route + inline cold-reconstruction; `/resume` owns the **heavy**
  forensic half. Unlike `/loop` (the campaign's native rebuild against a phantom brief source),
  `/resume` is a **real CE `ce-sessions` PORT** — verified TRUE and portable against the actual
  upstream, the positive counterpart to the `/loop` phantom-source lesson.
- **Two-tier design.** **Tier 1** (the common path) = saga-anchored deep reconstruction: a NEW saga
  **all-ticks reader** (`saga.py` `read_ticks`) that walks the full append-only tick-chain trajectory —
  the trajectory `/loop`'s latest-tick-only `restore` cannot see — plus PR archaeology and conflict
  reconciliation. **Tier 2** (FALLBACK ONLY, when there is **no saga AND no resolvable issue**) = a slim
  Claude-only port of CE `ce-sessions`: discover → file-mediated skeleton extract to scratch → **generic
  agent synthesis**, never reading multi-MB session JSONL into context (context-safety by construction).
- **The all-ticks reader lives in `saga.py`, NOT `load_saga_context.py`.** A brief deviation: the
  `load_saga_context.py` wrapper is **issue-locked** (its `--issue` arg is required), so it is the wrong
  layer for a cold-no-issue trajectory read. The all-ticks capability belongs in the saga engine itself
  (`read_ticks`); `load_saga_context.py` stays the shared issue-keyed substrate `/loop` and `/resume`
  both use.
- **Generic-agent synthesis — no `agents/` dir.** Tier-2 synthesis uses generic agents, honoring the
  shipped `/code-review` convention (no plugin `agents/` dir → generic agents, SKILL:164) rather than
  adding a structural first.
- **Drop the `[gstack-context]` commit trailer.** `/resume` does NOT adopt gstack's WIP-commit trailer —
  the saga's append-only tick log already IS the durable trajectory; a parallel trailer would duplicate
  it. Corrected Tier-2 trigger: same-machine work that never wrote a saga (NOT fresh-clone).
- **Routing + the one re-entry tick.** Routes to any phase via the **shared**
  `loop/references/dispatch-table.md` (referenced, never duplicated — no `/loop` ↔ `/resume` ping-pong).
  Writes exactly **one** git-ignored re-entry saga tick, **reusing the restored `saga_id`** (never-mint
  discipline — `/resume` is a reader/restorer, not a saga primary writer).
- **Recency-MVP ranking** for Tier-2 candidate sessions; keyword/branch relevance ranking deferred
  (QUEUED `#resume-session-relevance-ranking`).
- Version bumps: plugin `0.12.0`, marketplace entry `0.12.0`. keywords stay at 10.

## [0.11.0] - 2026-06-03

- Rebuild `/loop` from a router stub into a native router engine — the **sixth command rebuild** of the
  engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) and the
  campaign's **one native rebuild**: there is no upstream engine to port or merge. CE ships no router; the
  gstack "dispatch table" the QUEUED brief named is **phantom** (gstack's root SKILL is browser-testing, no
  router dir), and gstack's context-save/restore is the shipped saga + the queued `/resume`'s engine, not
  `/loop`'s. Three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive**
  (inline phase walk with a per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan →
  restore → route a durable work-thread).
- **Saga resume wiring.** `/loop` `scan`s for the matching work-thread saga, `tick`s a routing event, and
  `restore`s state on re-entry — plus inline cold-reconstruction via `load_saga_context.py` when re-entering
  without a live session. The routing tick carries the existing saga fields plus an offload pointer only for
  `/loop`-owned offloads (no schema change).
- **Operator-choice offer for `/loop`-owned work.** `/loop` offers the three execution backends
  (`inline` / `team-execution` / `cc-workflows-ultracode`) per decision point in Drive mode for work it owns.
  The offload pointer is scoped to `/loop`-owned work only — `/loop` does **not** instruct a routed command's
  backend (`/work` writes but never reads `orchestration_mode`).
- **Additive saga picker-field extension.** `saga.py` `scan()` / `_saga_summary` gained the issue_ref /
  plan_path / branch picker fields so a resuming `/loop` (and `/code-review`) can match the right thread —
  closing the `#code-review-saga-scan-touchups` queued item.

## [0.10.0] - 2026-06-03

- Rebuild `/work` from a 39-line facilitator stub into a real execution-loop engine — the **fifth command
  rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`)
  and the most architecturally entangled, because it lands two deferred foundations at once. A genuine
  **merge**: CE `ce-work`'s execution engine (Phase-0 complexity triage, task-list from plan U-IDs, the
  Execution-Strategy table + Parallel Safety Check, test discovery + scenario-completeness + system-wide
  check, incremental-commit heuristic, "already shipped → verify don't reimplement") + gstack `ship` /
  `land-and-deploy`'s autonomy contract, Review-Readiness + staleness gate, and merge-base-before-tests.
  Five numbered phases: enter + scan saga + triage + detect round-N → setup + task-list + backend → execute
  phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready +
  continuation routing.
- **Saga becomes first-class — `/work` is its primary writer (saga-spec §11).** `/work` `scan`s/`restore`s on
  re-entry (rehydrate round/phase/checks_run/next_step), mints/advances the work-thread saga to
  `lifecycle_phase=work` with `--plan-path` set + saved on-branch, and writes a tick per phase boundary
  (round bump via `--rounds-seen`, never `next_round`). Crucially it **mints + names the exact saga that
  `/code-review` (shipped 0.8.0, append-only/never-mint) appends `review_paths` to** — and passes the saga
  identity (`kind`+`id`) into the programmatic `/code-review` call so code-review hits that thread instead of
  scan-guessing. This closes the forward-coupling for both issue AND ad-hoc task work.
- **The deferred `recommend_execution_backend()` helper lands here** — its first real caller (a library-only
  helper would be uncallable from markdown). A pure function in `scripts/lifecycle_state.py` next to
  `should_offer_team_execution` (reused), plus a `recommend-backend` CLI subcommand returning
  `{recommended, rationale, alternatives, omit_ultracode}`. `alternatives` is computed independently of the
  precedence winner so an overlap case (consensus AND broad fan-out) still offers `cc-workflows-ultracode` as
  a one-keystroke escalation. `main()` refactored into `normalize` + `recommend-backend` subcommands.
  Closes the operator-choice 0.5.0 deferral.
- **`issue_progress.py`'s CLI extended** to forward the full field set the function already accepts
  (`--work-session-path --commit-sha --checks-run` [pipe-separated] `--blockers --pr-url --review-status
  --doc-review-artifact --doc-review-blocked --doc-review-findings` [pipe-separated] `--doc-review-override
  --deploy-status --workflow-url --evidence-link`) — the Phase-4 progress comment was previously
  uninvokable from markdown (only 8 of the function's fields had argparse flags).
- **PR-ready boundary + round-N PR continuation loop (`/work` owns it, NOT `/resume`).** `/work` executes to
  PR-ready, then on re-entry reads PR state with a total `gh pr view --json
  state,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,isDraft,mergedAt` and walks a total
  transition table (draft → mark-ready; review-required → pause; changes-requested/conflicting/failing-checks
  → round N+1; approved+clean+fresh → offer merge). **Merge is a confirmed git op `/work` owns**
  (`gh pr merge` only under explicit operator confirmation, never silent); only deploy mutation is delegated
  to `deploy`.
- **Hard review gate + honest override + computed staleness.** PR-ready blocks on unresolved P0/P1 (read from
  `/code-review`'s programmatic envelope + the saga `review_paths`) OR a stale review (parse the reviewed SHA
  from the newest review artifact → `git rev-list <reviewed_sha>..HEAD --count > 0`). Override only with a
  recorded rationale, never silent. `requires_hard_test_gate` blocks risky change-kinds at the test gate.
- **Boundary.** `/work` builds, gates, records, and coordinates the PR loop (merge under confirmation); it does
  NOT silently mutate GitHub, own deploy/canary (gstack's canary-verify + offer-revert are **relocated** to
  `deploy`, queued there), file SDLC issues (`mission-control`), or advance `lifecycle_phase` past
  `work` (the `qa` advance is honestly deferred to the `/qa` rebuild — the saga sits at `work` post-merge;
  `/qa`/`/resume` routing is advisory).
- Three new references: `skills/work/references/{execution-strategy,test-and-gates,pr-continuation-loop}.md`
  (CE execution strategy + the `recommend_execution_backend()` integration; test discovery + hard-gate +
  computed-staleness + the gstack autonomy contract; the total PR-state transition table). Thin
  `commands/work.md` launcher (saga-primary-writer + PR-ready boundary + hard review gate +
  merge-under-confirmation; no deploy/canary ownership). Surgical flip of `references/operator-choice.md`'s
  deferred-helper notes now that the helper has shipped. Self-contained: merges the CE + gstack engines, no
  vendoring, no runtime dep.

## [0.9.0] - 2026-06-03

- Rebuild `/founder-review` (alias `/ceo-review`) from a 20-line stub into a real scope/ambition/direction
  review engine — the fourth command rebuild of the engine-merge campaign (after `/office-hours`, `/plan`,
  and `/code-review`). A **port, not a merge**: gstack `plan-ceo-review` is the sole engine source (4
  user-selected scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted
  pre-review system audit), with only CE `product-pulse`'s sharpened no-false-precision posture stolen.
  Fires upstream of execution on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc
  scope question — the third member of the review trio (`/doc-review` = plan-readiness, `/code-review` =
  code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?**).
- **Four scope modes, committed for the whole review (no silent drift)** — SCOPE EXPANSION (cathedral) /
  SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon), selected
  via `AskUserQuestion` with context-defaults (greenfield→Expansion, enhancement→Selective, bugfix/refactor
  →Hold, >15 files→suggest Reduction). Each is distinct; all relevant pre-traction.
- **Review-only boundary** — `/founder-review` challenges scope/ambition/direction + captures a scope
  decision; it never makes code changes, never commits/pushes/opens PRs, never files SDLC issues, and never
  *records* the direction (`/strategy` records; founder-review challenges). On a `STRATEGY.md`, founder-review
  is the *ambition lens* and `/doc-review` the *readiness lens* — complementary, not a collision.
- **CLOSED-LOOP routing (not a hand-wave)** — accepted scope routes to `/plan` to re-plan; the (re-)expanded
  plan artifact is written/updated and handed **back** to `/doc-review` (readiness) + `/code-review` (code)
  **with the concrete path**, so expanding scope re-rigors that scope rather than dropping it. Phase 3
  applies the directives + patterns as scope-level lenses producing **named scope findings**, not vibes.
- **Target-conditional Step-0 ceremonies** — gstack's 0C-bis (implementation alternatives) + 0E (temporal
  interrogation) are plan-specific, so they run on a plan target and are skipped/recast on a
  strategy/brainstorm/scope-question target (0A/0B/0C/0F always run). An **office-hours escape** in 0A
  offers `/office-hours` when the session is vague/unframed, resuming after.
- **NO saga write** — founder-review runs upstream/pre-saga and its output is a scope decision, not a
  readiness/code-review artifact; `saga.py`'s `review_paths` is the wrong home and the guard would skip
  ~always. Cross-session persistence = the `docs/founder-reviews/` scope-decision artifact + the journal ADR.
- Durable artifacts land in their own `docs/founder-reviews/` scope-decision dir (intentionally NOT a
  `/handoff` source and NOT `docs/reviews/`), carrying the Mode + Vision + a Scope-Decisions table
  (ACCEPTED/DEFERRED/SKIPPED) + the founder verdict (ship / sharpen / scrap-and-rethink) + the next-command
  handback. **Operator-choice** offer — all three backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) on a scope-expansion/scrap verdict.
- Two new references: `skills/founder-review/references/{ceo-cognition,review-modes}.md` (the 18 patterns + 9
  directives + sharpened posture; the 4 modes + ceremonies + adapted audit + target-conditional gating).
  Thin `commands/founder-review.md` + `commands/ceo-review.md` (alias) launchers (review-only, no saga
  mention). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE.

## [0.8.0] - 2026-06-03

- Rebuild `/code-review` from a 20-line stub into a real pre-PR code-quality review engine — the third
  command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`). Merges CE's
  `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack
  `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories into a
  self-contained infiquetra engine. Fires at the work→PR boundary (after `/work` produces code, before
  PR/merge) — it is a within-work gate, NOT the saga `review` lifecycle slot (`/doc-review` owns that).
  Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) →
  review fan-out → merge + validate → report + route + saga.
- **Gate-only boundary** — `/code-review` reports + classifies + routes; it never mutates code, commits,
  pushes, opens PRs, or files SDLC issues (`/work` / `deploy` / `mission-control` own those).
  Adopts CE's full findings schema (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` /
  `pre_existing` / `evidence`) as agent-consumable routing metadata; fixer dispatch is offered, never
  auto-run. The programmatic mode (for `/work`'s future call) is zero-write to reviewed code.
- **Judgment-based lenses** — read the diff, spawn only lenses with real work, announce the team with a
  one-line justification each. Four always-on lenses (correctness, security, testing,
  maintainability/conventions) plus conditional-by-judgment lenses including a distinct
  deploy/migration-verification lens (DynamoDB/IaC/Ansible checklist) and a reliability lens. gstack's
  Rails/Swift/Stimulus specialists dropped; its high-signal checklist categories (enum-completeness,
  LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the lens checklists.
- **Built-vs-planned audit** — scope-drift detection (informational: CLEAN / DRIFT / REQUIREMENTS-MISSING)
  plus the 5-state plan-completion audit (DONE / PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE) with the
  three verification modes (DIFF / CROSS-REPO / EXTERNAL-STATE) and the honesty rule, reading the
  `docs/plans/` artifact + the journal. The audit always emits findings; the normal P0/P1 findings gate
  is what blocks the PR.
- **Independent validator pass, right-sized by MODE** — programmatic/headless runs a fresh per-finding
  validator over all Stage-A survivors (capped 15, ordered P0→P3, validator-reject/failure → drop);
  interactive mode lets the operator be the per-finding validator. The cost control is the upstream
  suppress-<75 confidence gate + the 15-cap, not a severity carve-out.
- `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread
  saga (found via `saga.py scan`): appends the artifact path to `review_paths` + records the backend in
  `orchestration_mode`, preserving `lifecycle_phase` (it does NOT advance the phase). If no saga exists it
  skips the saga write — never mints, never invents `--kind/--id`. Never `git add` the tick.
- Durable artifacts land in their own `docs/code-reviews/` dir (NOT `docs/reviews/` — avoids the
  handoff/mission-control plan-ready classifier collision), carrying the reviewed SHA + a review-result
  contract. **Operator-choice** offer — all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) for the fan-out + validator
  pass.
- Four new references: `skills/code-review/references/{lens-catalog,findings-schema,validator,built-vs-planned}.md`.
  Thin `commands/code-review.md` launcher reflecting the engine (gate-only + saga append + the hard
  boundary). Self-contained: ports both source engines, no gstack vendoring, no runtime dep on CE.

## [0.7.0] - 2026-06-02

- Rebuild `/plan` from a 27-line stub into a real implementation-plan engine — the second command
  rebuild of the engine-merge campaign. Merges CE's `ce-plan` structured-artifact engine (the
  Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end into a
  self-contained infiquetra engine. Six numbered phases: enter + warranted-gate → ground (HOW) →
  interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route +
  operator-choice.
- Artifact contract (CE wholesale): stable **R-IDs** (requirements), **KTDs** (Key Technical
  Decisions), independently-landable **U-IDs** with per-unit enumerated **test scenarios** + explicit
  test-file paths; requirements traceability; "decisions not code"; three-audience design (human +
  agent + `/work` consumer). The plan doc carries `origin:` + `Implementation Units` +
  `Key Technical Decisions` + `U1` markers so `/doc-review` recognizes it.
- **Warranted-gate** + scope classes up front — a `/plan` invocation that doesn't warrant a durable
  plan is named and routed, not force-fit into the artifact.
- **HOW-only interrogation** — `/plan` assumes the WHAT (requirements/scope) settled upstream
  (`/ideate` → `/brainstorm` → `/office-hours`); open WHAT-ambiguity bounces back with a recommendation
  to run `/brainstorm` first (it does NOT claim `/brainstorm` "accepts" a handoff). The interrogation
  register grounds in code (cite `path:line`) before asking.
- **Condensed deepening pass** — a conditional confidence self-review (not CE's full 248-line
  deepening), kept proportional. The full review gauntlet is NOT dropped — it's the `review` phase
  (`/doc-review` + `/code-review` + `/founder-review`); `/plan` keeps the condensed self-review and
  routes to `/doc-review` (the recommended next step) before `/work`.
- One **plan saga** via the saga CLI (`scripts/saga.py save`, `--lifecycle-phase plan`) — runnable,
  with an explicit "never `git add` the tick" boundary; epic/multi-unit splits hand to `mission-control`.
- **Operator-choice** offer: all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`), offered not defaulted.
- Hard boundary: `/plan` does NOT implement, does NOT file SDLC issues (`mission-control` owns that), and
  does NOT run the full review gauntlet (`/doc-review` owns that). Position: `/plan` answers
  "How should it be built?".

## [0.6.0] - 2026-06-02

- Rebuild `/office-hours` from a 23-line facilitative stub into a real two-mode thought-partner
  diagnostic ported from gstack and adapted to infiquetra — the Think-phase frame-finding front
  door that `/ideate` routes unframed asks to and `/brainstorm` bounces open thought-partner work
  back to. Keeps that handshake.
- Two modes: **Startup mode** — gstack's six market/customer forcing questions, made
  **stage-aware** (a pre-traction / pre-revenue greenfield operator gets a hypothesis-forming
  register, not an evidence-audit of customers that don't exist yet); **Builder mode** —
  discovery/shaping for infra, workflow, and internal-tooling asks, infiquetra's high-frequency
  mode, carrying real depth (not a one-liner). Modes can switch mid-session.
- Anti-sycophancy + pushback re-targeted: hard on vagueness and ungrounded assumptions, not on
  the operator's judgment; push-twice with escape hatches. **HARD GATE** (absolute): never
  implement, plan, or file an SDLC issue — frame-finding only. Stops the moment it can name the
  problem and a route, with plural clean exits (`/brainstorm`, `/plan`, `/strategy`).
- Route always (close by naming a next command); an optional **frame note** lands in its own
  `docs/office-hours/<date>-<topic>-frame.md` (frontmatter `kind: frame-note`) — kept out of
  `docs/ideation/` to avoid colliding with the `/ideate` resume scan.
- Self-contained: ports the gstack engine, sheds its runtime boilerplate (brain-context preflight,
  gbrain sync, learnings-search, telemetry, `~/.gstack` path conventions). No gstack vendoring, no
  runtime dependency on compound-engineering.

## [0.5.0] - 2026-06-02

- Add the operator-choice framework: a new contract document, `references/operator-choice.md`, that
  codifies the 3-way execution-backend choice — `inline` / `team-execution` / `cc-workflows-ultracode`
  (the canonical `ORCHESTRATION_MODES` enum strings). Lifecycle owns the *choice* of backend; it does
  not own execution.
- Add short prose offer hooks to `/loop` and `/work` that surface the operator-choice when work
  warrants a non-inline backend, pointing at the decision contract.
- Fix the `saga-spec.md` `orchestration_mode` cross-ref: it pointed at §7 (the save/restore/scan
  operation contract) instead of the decision contract; it now references
  `references/operator-choice.md`.
- Doc-only foundation. No code or helper is added in this release — the CLI-backed
  orchestration-choice helper is deferred to the `/work` rebuild.

## [0.4.0] - 2026-06-02

- Add a unified saga engine (`scripts/saga.py`): one source of truth for durable, resumable
  work-state with a stable derived identity (`issue-<N>` / `task-<slug>`, sticky for the life of
  the work), save/restore/scan, and gh-context aggregation. Sagas are written as an append-only,
  timestamped envelope log under `.claude/saga/sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`
  (gstack-style YAML frontmatter + `Summary`/`Decisions`/`Remaining`/`Notes` body), plus a derived,
  rebuildable `state.json` index. Envelopes are immutable; each save appends a new tick.
- The three legacy scripts — `scaffold_checkpoint.py`, `find_inflight_work.py`, and
  `load_saga_context.py` — are now thin wrappers that delegate to `saga.py`. Every CLI flag and JSON
  output key is preserved, so existing callers keep working.
- Behavior changes from this unification:
  - Storage moved from per-phase `checkpoints/` files to per-saga `sagas/<saga_id>/` envelope
    directories.
  - Ordering is now by envelope filename (the timestamped name **is** the canonical order), never by
    filesystem `mtime`. This makes ordering deterministic and robust under rsync/backup/snapshot
    restore.
  - Saves are append-only (a new immutable tick per save) instead of overwriting a single checkpoint.
  - Three stored state axes — `lifecycle_phase` (CE flow position), `phase_status` (phase
    completion, drives the next phase), and `status` (thread disposition) — replace the prior
    ad-hoc fields; `maturity` is derived at `/handoff` time, not stored. Frontmatter lists use
    full-snapshot replace semantics (a tick's lists replace; absent carries forward; empty clears).
- Add a plugin-level contract document, `references/saga-spec.md`, that the lifecycle consumers
  (`/plan`, `/work`, `/resume`, `/loop`) implement against.
- **Upgrade warning:** complete any in-flight `/loop` work before upgrading. Legacy
  `.claude/saga/checkpoints/` state is read as a low-priority `scan` fallback for one
  version only and then dropped — finish or re-save active loops so they migrate into the new
  `sagas/` layout.

## [0.3.0] - 2026-06-01

- Rebuild `/ideate` from a thin facilitative stub into a full divergent→convergent engine ported from
  compound-engineering and adapted to the infiquetra world: parallel frame agents generate many
  grounded candidates, the orchestrator critiques all and presents only the survivors, and cut ideas
  stay first-class and revivable. Adds a two-way thought-partnership — the operator's seed ideas feed
  *into* the frame agents (build on / challenge / combine) and face the identical critique — and a
  revival state machine that re-enters the filter with new evidence, preserving explicit rejection as
  the quality mechanism.
- Add infiquetra-specific grounding to `/ideate`: a grounding-fit gate (proceed / decline /
  recommend `/office-hours` / ask) weighing idea breadth against available grounding; a
  context-library reader (`*-context-library` repos via `gh`, local-clone preferred); a named-repo
  reader for multi-repo asks; read-only `gh` issue-theme clustering on backlog intent; and smart-auto
  web research for the cross-domain-analogy frame. Adaptive frame count (1–6) scales to scope.
- Rebuild `/brainstorm` into a thinking-partner engine that deep-dives one chosen idea (a `/ideate`
  survivor or a named topic) into a right-sized requirements document: scope assessment, a product
  pressure-test, one-question-at-a-time dialogue, 2–3 approaches with a non-obvious angle, and a
  `requirements-ready` artifact under `docs/brainstorms/` for `/plan`.
- Add reference files: `skills/ideate/references/convergence-and-partnership.md`,
  `skills/ideate/references/ideation-artifact.md`, and
  `skills/brainstorm/references/requirements-sections.md`. Self-contained — no runtime dependency on
  compound-engineering.
- Add `/handoff` to route durable lifecycle artifacts to `mission-control` prepared issue drafts, with a
  thin handoff-envelope helper that records source, maturity, target hints, blockers, open questions,
  and the `/issue --prepare` routing command without owning SDLC issue bodies. Teach
  `/plan <issue>` and `/work <issue>` to consume handoff maturity and source context from prepared
  SDLC issues.

## [0.2.0] - 2026-05-31

- Rename the plugin from `infiquetra-loop` to `saga`; "loop" named only the `/loop`
  router command, not the whole idea-to-ship lifecycle the plugin covers. The `/loop` command name
  is unchanged.
- Rename the ignored runtime-state directory from `.claude/infiquetra-loop/` to
  `.claude/saga/`; `mission-control` updated in lockstep.
- Rename the handoff-envelope `loop_owner` field to `lifecycle_owner`.
- Document the command set by lifecycle phase: Think, Plan & execute, Hand off, Review, and
  Improve & route.

## [0.1.0] - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
