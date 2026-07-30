---
title: Retire the fleet lease broker — unwind 91 call sites, then delete 10,203 lines
type: refactor
status: active
date: 2026-07-30
deepened: 2026-07-30
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/677
---

# Retire the fleet lease broker — unwind 91 call sites, then delete 10,203 lines

## Summary

Unwind every remaining caller of `fleet_commons/lease_broker.py` in this repository, then delete the
module, its orphan-evidence companion, and their two test suites — 10,203 lines. The runtime fence
they implement was replaced at emit time by issue #673; this plan removes the thing it replaced.

> **STATUS: SCOPE RESOLVED — Option C (delete everything, name the accepted losses). See "Scope
> Decision" below.** Grounding established that the broker still provides three capabilities with live
> callers that the emit-time replacement does not cover. An earlier draft characterized the work as
> "mostly subtraction"; that was wrong. The scope was then settled on 2026-07-30 by measuring the
> lease registry rather than by argument — see KTD11. The units below (U1–U7) are sized for Option C
> and now match the chosen scope, but each accepted loss must appear in the decision record.
>
> **Reviewed 2026-07-30 (`/doc-review`), safe fixes applied in place.** All 15 line counts, all three
> plugin versions, and all six issue states verified exact against `ddba53a0`. The review found one whole
> class of work missing (agent-facing documentation → new **R11**/**R11a**), one rename whose blast radius
> was understated by four files (→ new **R4a**), one requirement that undercounted the behavior it
> preserves (→ new **R5c**), and a requirement-number collision between this plan's R6 and issue #358's R6
> quoted in source. Full review at `docs/reviews/doc-review-issue-677-2026-07-30.md`.
>
> **Operator decisions, settled 2026-07-30 — no open questions remain.** (1) **No documentation-only
> unit**: the 13 documents in R11 each ship with the unit that removes the behavior they describe.
> (2) **`team-execution` → 3.0.0** (R8). (3) **U2 and U3 run in parallel** — the earlier "does U3 have
> to precede U2" question was based on a wrong premise and is now closed; see Implementation Units.
> (4) **Two broker consumers found after decomposition** were folded into existing units rather than
> given an eighth card: `plugins/saga/hooks/team_teardown_hook.py` → U2, and
> `plugins/saga/scripts/outcome_decompose.py` → U3. Both had escaped the consumer survey because
> neither literally imports `lease_broker` — the same escape mechanism that hid
> `liveness_events.py` (R4a).

**Scope is this repository only.** `infiquetra-codex-plugins` is explicitly **not** in scope and no
card is filed for it — the operator owns that decision and will work it directly with codex. The
reason is recorded below under "Codex — out of scope": that repo's newest commit deliberately kept the
lease substrate, and a teardown there would undo a cleanup that just landed. The measurements are
preserved there as a handoff, not as planned work.

> **Every `file:line` reference in this plan was measured against the working tree at commit
> `ddba53a0`** (the tip of `main` when the plan was written and reviewed). Line numbers drift as soon as
> any unit lands. Treat them as "look here first," re-grep the symbol before editing, and do not treat a
> mismatch as evidence the claim was wrong. Line *counts* and file sizes were re-verified at review time
> and are exact as of that commit.

## Problem Frame

The `lease-safe-runtime-continuity` outcome built a runtime lease system between 2026-07-16 and
2026-07-20 (issues #350, #351, #353, #355, #356, #357, #358, #604, #605 — all closed COMPLETED). Issue
#671 then concluded the runtime fence was the wrong mechanism: concurrent-write collisions are a
planning problem, solved by assigning work units that do not cross files. Three pull requests acted
on that — #673 (`b3c13006`) shipped the emit-time replacement, #674 (`ebdc535f`) removed the write
fence, #676 (`ddba53a0`) retired agy's live-apply mode and the first consumer set.

What remains is dead weight that still compiles. Runtime enforcement is off globally
(`INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off`, set in `~/.claude/settings.json:11`), so the broker fences
nothing today, yet four open defect cards (#645, #646, #647, #661) describe bugs inside it. Those are
repair tickets against a component that should not exist.

**The precondition #671 set has been met.** That issue said *"Do NOT delete `lease_broker.py` /
`lease_mutation_hook.py` until one of the above lands"* and listed partition-by-declaration as option
3. #673 shipped it: `wave_file_conflicts()` at `plugins/saga/scripts/execution_spec.py:1781` and
`assert_no_wave_file_conflicts()` at `:1830`, called from both emitters
(`plugins/saga/scripts/team_emitter.py:235`, `plugins/saga/scripts/execution_spec.py:3465`). #674 then
deleted `lease_mutation_hook.py`, in that order.

## Scope Decision — resolved 2026-07-30: Option C

Grounding found that #673's emit-time file-disjointness check replaces **only the fencing third** of
what the broker does. Two other capabilities have live callers and no replacement: leaf-dispatch
idempotency (admission) and trusted agent identity (liveness). Three scopes were possible, and they
differ materially in the units they imply:

**Option A — Delete only the fencing parts.** Unwind `outcome_compat.py`'s handoff protocol,
`engine_dispatch.py`'s manifest CAS, and the fencing half of `outcome_worktrees.py`. Keep a much
smaller admission-and-liveness core. Deletes perhaps 2,000–3,000 of the 4,731 broker lines rather than
all of it, and `orphan_evidence.py` still goes. Honest about what #673 actually replaced. Costs: the
module survives, so all four open defects (#645, #646, #647, #661) stay open as real defects, and "retire
the lease broker" becomes "shrink it."

**Option B — Delete everything, replace the two capabilities.** Build leaf-dispatch idempotency
(content-digest keyed, cross-runtime, per `git-common-dir`), a trusted identity source for
`bind_identity`, and an owner-liveness probe for worktree reaping. Achieves the full 10,203-line
deletion but is a re-architecture, not a teardown — three new mechanisms, each needing its own design.

**Option C — Delete everything, accept the losses explicitly. → CHOSEN.** Take the deletion and record
that leaf dispatch is no longer idempotent across concurrent runtimes, agent identity is
caller-asserted, and worktrees on the outcome path are reclaimed by hand. Cheapest and fastest;
defensible only if those exposures are genuinely acceptable given the fleet's real usage. Requires a
decision record naming each accepted loss, not silence.

**Why C, and what the measurement did and did not settle.** The deciding question was whether the
collision that refuse-mode admission exists to catch has ever actually occurred. It has not been
recorded once — see KTD11 for the full count and its limits. That clears the first of the three losses
on evidence and makes Option B's replacement work a defense against an unobserved event.

The three accepted losses are **not** equally supported, and the decision record must say so per loss:

| Accepted loss | Basis | Strength |
|---|---|---|
| Leaf dispatch not idempotent across concurrent runtimes | Zero recorded refusals on 26 exercised admission keys (KTD11) | Evidence, with a stated telemetry gap |
| Agent identity becomes caller-asserted (`bind_identity` / `verify_agent` go away) | Operator judgment — no measurement was taken | **Judgment only** |
| Worktrees on the outcome path reclaimed by hand | 3 of 3 production teardown sites already inject no reaper (KTD12); only `outcome_worktrees.py:674` reaps | Evidence, narrower loss than first written |

## Requirements

**R1.** No production file under `plugins/` imports `lease_broker` or `orphan_evidence` when this plan
completes. Verified by grep returning zero files, and pinned by a new re-add guard test.

**R2.** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (4,731 lines),
`orphan_evidence.py` (1,578), `tests/test_fleet_lease_broker.py` (2,709), and
`tests/test_orphan_fencing.py` (1,185) are deleted — 10,203 lines.

**R3.** `plugins/fleet-core/scripts/fleet_commons/concurrency_policy.py` (78 lines) survives and stays
imported. It is the emit-time replacement's policy source, not part of the fence.

**R4.** The fleet-shared liveness engine survives as a capability. Its `lease_ttl_seconds` observation
field is renamed to a source-neutral `ttl_seconds`, and the `lease-ttl-cold-start` reason string to
`ttl-cold-start`, so any caller may supply a deadline without a lease.

**R4a.** The R4 rename crosses a **serialized event schema**, not just one module, and every producer and
consumer of the field moves in the same unit (U6). Measured surface — five files, not one:

| Site | Role |
|---|---|
| `liveness_engine.py:94`, `:288`, `:289` | dataclass field, the branch guard, and a `_finite_nonnegative(…, "lease_ttl_seconds")` **string literal** that appears in error messages |
| `liveness_engine.py:367` | the `lease-ttl-cold-start` reason string |
| `saga/scripts/liveness_events.py:65` | membership in the `IDENTITY_KEYS` tuple — a required-key contract |
| `saga/scripts/liveness_events.py:207`, `:236`, `:258`, `:644` | dataclass field, wire **parse** (`value["lease_ttl_seconds"]`), wire **serialize**, and construction from `identity.lease_ttl_seconds` |
| `team-execution/.../liveness_protocol.py:291` | the producer: `"lease_ttl_seconds": lease.ttl_seconds` |
| `tests/test_liveness_engine.py`, `test_liveness_events.py:56`, `test_team_execution_liveness.py:126` | assert on the old field name and reason string |

`liveness_events.py` does **not** import the broker (it loads `liveness_engine` through
`fleet_commons_shim` at `:574`, `:1028`), so it is absent from the consumer table below by design — but it
is squarely inside R4's blast radius, and renaming the engine field without it produces a `KeyError` at
`:236` on the first event parsed. Whether previously written events must still parse under the old key is
an open compatibility question, flagged in the findings rather than decided here.

**R5.** Teardown keeps working, and its **disposition reporting** survives the broker's removal —
`already-absent`, `released`, and `retained` remain produced, re-keyed on worktree path instead of
`lease_id`. This requirement no longer claims teardown reaps worktrees, because per **KTD12** it does not:
all three production call sites pass no `worktree_reaper`. Corrected from an earlier draft that asserted
the opposite.

**R5a.** Automatic reclamation of per-leaf **outcome** worktrees is deliberately given up when
`outcome_worktrees.py:674` is deleted, and a documented manual reclamation procedure ships in the same
unit that removes it (U3). An accepted loss with no substitute and no record does not satisfy this
requirement.

**R5b.** The `DECISIONS.md` entry states all three accepted losses **with their individual basis**, and
marks the caller-asserted-identity loss as taken on judgment rather than measurement. It carries a
separate "revisit when" condition for that row.

**R5c.** The disposition surface is **five outcomes across four reason codes and three evidence-ref
strings**, not three dispositions — read from `_worktree_sweep` (`team_teardown.py:1251-1277`) rather than
summarized. All of it must be accounted for, because the reason codes and evidence refs are what
teardown's evidence contract is built from:

| Line | Disposition | Reason code | Evidence ref |
|---|---|---|---|
| `:1255` | `already-absent` | `lease-already-released` | `broker:lease-absent:{lease_id}` |
| `:1263` | `released` | *(none)* | `sweep:reaped:{lease_id}` |
| `:1269` | `retained` | `sweep:{retained_reason}` | *(none)* |
| `:1272` | `already-absent` | `released-by-sweep` | `sweep:lease-gone:{lease_id}` |
| `:1277` | `retained` | `not-a-sweep-candidate` | *(none)* |

Two consequences the word "re-key" understates, and U2 must handle both:

1. **All three evidence-ref strings are lease-id-namespaced** — `broker:` and `sweep:` prefixes plus a
   `{lease_id}` suffix. With no broker there is no lease id and no `broker:` namespace, so these strings
   are **redefined**, not re-keyed. Any test or downstream consumer asserting on their literal shape
   breaks by design; the replacement namespace must be chosen deliberately and named in the CHANGELOG.
2. **`already-absent` changes meaning.** Today it fires when the *lease* head is gone
   (`reason_code="lease-already-released"`), which says nothing about whether the worktree exists on disk.
   Re-keyed on worktree path it comes to mean "git no longer lists this worktree" — a different
   predicate wearing the same word. State the new definition explicitly rather than inheriting the old
   one silently.

**R6.** `tests/test_agy_run_lease.py` passes with **zero modifications**. It covers the *subprocess*
lease (run id, pid, timeouts, shutdown), which shares a word with the broker and nothing else. Any
need to edit it means the deletion went too far.

**R7.** No unit in the same dependency wave declares the same file as another, per #673. `emit` HALTs
on a collision, so unit boundaries must be file-disjoint by construction.

**R8.** Every plugin whose files change gets its version, CHANGELOG, and the generated
`marketplace.json` moved together, per the repo's release-surface rule. Target versions, settled at review
time because an unstated bump is an invitation to guess wrong at the last minute:

| Plugin | Current | Target | Reasoning |
|---|---|---|---|
| `fleet-core` | 0.23.0 | **0.24.0** | Pre-1.0; deletes its largest module. Minor bump is this repo's convention for pre-1.0 capability removal — the same call the agy teardown made (0.5.1 → 0.6.0). |
| `saga` | 0.122.0 | **0.123.0** | Pre-1.0; deletes a hook and a wrapper. Same convention. |
| `team-execution` | 2.23.0 | **3.0.0** | **The one real decision.** This plugin is post-1.0, and it loses a capability its README advertises at `:20-29` (lease admission, preflight, renewal, release, dead-owner sweep) plus, likely, the whole of `lease_protocol.py`. Under semver that is a breaking change, not a feature removal behind a flag. A `2.24.0` here would understate it. |

If the `team-execution` major bump is unwanted, the alternative is to keep `lease_protocol.py` as a
deprecated no-op shim through one more minor release — but that contradicts R1 and R2, so it is a scope
reversal, not a version tweak. Decide the version, not the shim.

**R9.** No file in `infiquetra-codex-plugins` is touched, and no codex card is filed. That repo's
disposition is the operator's to decide, separately. The survey findings are recorded here only so the
operator does not have to re-derive them.

**R10.** Journal entries land in the same commit as the change that earns them, per the repo rule.

**R11.** **Agent-facing documentation moves with the code that stops being true.** Added by review: no unit
below listed a single Markdown file, yet the repo rule R8 already invokes requires user-facing guidance to
move on the same pull request as the behavior change. These documents are **executable instruction for
agents**, not commentary — a `SKILL.md` that tells an agent to run a lease preflight after the preflight is
deleted produces wrong runtime behavior, not stale prose.

Measured surface — 13 documents with substantive fleet-lease content, in the three affected plugins
(counts are matches of `lease`/`leases`/`leased`/`lease_broker`/`orphan evidence`, excluding
`release`; UniFi's hits are DHCP leases and are correctly out of scope):

| Document | Hits | Why it stops being true |
|---|---|---|
| `saga/references/concurrency-spawn-sites.md` | 13 | An inventory table whose columns *are* "Lease pool / Acquire or reserve seam / Bind seam / Renewal seam / Release seam" — every row goes false |
| `team-execution/skills/team-execution/SKILL.md` | 8 | The skill agents actually execute |
| `saga/skills/work/SKILL.md` | 8 | Same, and the most-used surface in the repo |
| `team-execution/.../references/liveness-protocol.md` | 7 | Survives as a capability but not as a lease-fed one (R4/R4a) |
| `team-execution/.../references/lease-protocol.md` | 7 | Documents `lease_protocol.py`, a whole-file deletion candidate in U6 — likely deleted outright, not edited |
| `team-execution/README.md` | 7 | `:20-29` describes lease admission, preflight, renewal, release, and dead-owner sweep as current behavior |
| `fleet-core/README.md` | 7 | Describes the deleted module as a library capability |
| `saga/skills/fleet-doctor/SKILL.md` | 6 | Doctor loses its orphan-evidence probe in U7 |
| `team-execution/.../references/teardown-reclamation.md` | 5 | Directly contradicted by KTD12 and R5c |
| `saga/references/fleet-doctor-sources.md` | 5 | Source list includes the deleted module |
| `saga/references/teardown-consumer-sites.md` | 4 | A consumer-site inventory of exactly what is being removed |
| `saga/references/liveness-consumer-sites.md` | 3 | Same, for liveness |
| `saga/README.md`, `saga/references/outcome-spec.md`, `saga/references/outcome-cross-runtime.md`, `saga/docs/commands.md`, `saga/skills/outcome/SKILL.md`, `saga/commands/fleet-doctor.md` | 2–4 each | Incidental references |

**Assignment rule:** each document moves in the unit that removes the behavior it describes — the
team-execution documents with U6, the teardown documents with U2, the fleet-doctor documents with U7.
Do not batch them into a documentation-only pull request at the end; that guarantees a window where the
shipped skills lie.

**No documentation-only unit, and the units are bigger than U1–U7 were first sized.** Settled at review
time rather than left open: adding a U8 for documentation would recreate exactly the trailing-PR window the
assignment rule exists to prevent. So U2, U6, and U7 each absorb their share and are **larger than their
original estimates** — U6 most of all, since it takes five team-execution documents on top of the R4a
rename. Two documents span more than one unit and get a named owner so they are not orphaned:

- `saga/references/concurrency-spawn-sites.md` — rows are emptied progressively by U1 through U4, so it is
  rewritten **once, in U7**, when the last row goes. Until then it is stale-but-consistent, which is
  preferable to four partial rewrites.
- `saga/skills/work/SKILL.md` — 8 references spanning dispatch and teardown. **Owned by U3**, the unit that
  removes the dispatch behavior it leans on hardest.

**R11a.** `plugins/fleet-core/.claude-plugin/plugin.json:4` advertises *"shared primitives, **lease** and
liveness decisions…"* in its `description`, and that string is mirrored into
`.claude-plugin/marketplace.json:204`. R8's version-and-CHANGELOG move is not sufficient — the
**description** changes too, and `marketplace.json` is regenerated from `plugin.json`, never hand-edited.

## Key Technical Decisions

**KTD1 — Unwind by call-site cluster, not by file size.** The intuitive split (start with the biggest
file) is wrong here. Measured call sites diverge sharply from line counts: `outcome.py` is the largest
file at 2,979 lines but carries only **2** broker call sites, while `engine_dispatch.py` (2,586 lines)
carries **23** and `outcome_worktrees.py` (980 lines) carries **16**. Units are cut along capability
seams — settlement, teardown, dispatch — because that is where the work actually is.

**KTD2 — Delete the two shim-shaped files rather than editing them.**
`plugins/saga/hooks/lease_lifecycle_hook.py` (92 lines) is entirely broker-protocol dispatch:
`ensure_protocol`, `reserve_hook_agent`, `claim_hook_agent`, `record_hook_terminal`,
`record_hook_parent` at `:59-70`. `plugins/saga/scripts/lease_broker.py` (574 lines) is the saga-side
wrapper every other saga file imports. Both become empty of purpose, so they go whole. This also makes
the dependency order explicit: leaf consumers first, then the saga wrapper, then the fleet-core module.

**KTD3 — The batch-renewal debt is discharged by deletion, not repaid.** Decision
`{#fence-carried-batch-renewal-671}` recorded that `assert_write_target` opportunistically renewed
batch leases (`lease_broker.py:3300-3307`) and that deleting the fence deleted that heartbeat, with a
revisit-when of *"anyone proposes re-arming enforcement, or the lease system's runtime admission is
retired wholesale."* This plan is the second branch. Verified: `assert_write_target` and
`_renew_batch_member` now have **no callers outside the broker module itself**. The 300s-TTL
measurement that decision demanded is a precondition for *restoring* enforcement, not for removing it
— deletion discharges the debt rather than inheriting it.

**KTD4 — `renew_batch` is the one genuinely live lease seam.** Unlike `assert_write_target`, it still
has external callers: `plugins/saga/scripts/workflow_emitter.py:187` and
`plugins/saga/scripts/lease_broker.py:406`. Workflow children emit no lifecycle events between waves
(#615), so cooperative renewal at collection boundaries is a real mechanism, not dead code. It goes
away with the batch concept itself; the replacement is that no batch lease exists to renew.

**KTD5 — Liveness keeps the cold-start heuristic under a neutral name.**
`fleet_commons/liveness_engine.py` never imports the broker — it accepts `lease_ttl_seconds` as an
optional observation field (`:94`) feeding a `lease-ttl-cold-start` branch (`:367`). The heuristic
answers "too early to have a phi signal yet," which is useful independent of leases. Rename rather
than delete; a caller may supply any deadline. Rejected: deleting the field, which would discard
working cold-start handling that a future deadline source would have to rebuild.

**KTD6 — Codex is out of scope entirely; no card, no plan, operator-owned.** Superseded an earlier
"own card, claude first" decision after measurement contradicted its premise. Codex commit `45890ae`
(2026-07-29, tip of `main`) narrowed fleet-core to 0.14.0 and named *"leases, concurrency, orphan
evidence"* among what it kept — a teardown there would reverse a cleanup that landed the same day.
Planning it from this side risks undoing work the operator just finished, so the disposition moves to
the operator to settle directly with codex. Rejected: filing a codex card now (commits this repo's
conclusion onto a repo whose newest decision points the other way), and quietly leaving codex in scope
(the contradiction would surface at execution time instead of decision time).

**KTD7 — WITHDRAWN.** This slot held a decision about how to record the codex deletion in that repo's
port contracts. Codex is now out of scope (KTD6), so the decision is not this plan's to make. The
findings behind it are preserved under "Codex — out of scope" so the operator has them. The number is
retained rather than reused, because the saga tick and issue #677 reference it.

**KTD8 — Worktree reclamation needs a replacement, and it is not simply `git worktree list`.** This is the plan's one genuinely new mechanism, and it was nearly missed. Worktree
reclamation in `team_teardown.py` is not merely *passed through* the broker — it is **indexed by
lease**. The `_worktree_sweep` closure at `:1251-1277` reads a lease head via `_current_head(broker,
lease)`, calls `broker.sweep(worktree_reaper=…)`, then interprets the result through
`result["reaped_worktree_leases"]` and `result["retained"][lease_id]`. Every branch is keyed on
`lease_id`. Delete the broker and there is no remaining way to enumerate worktrees through this path.

**`git worktree list` alone is NOT sufficient, and an earlier draft of this KTD said it was.** Two
things break that answer:

1. **Reaping needs owner-liveness, not just enumeration.** `sweep()` reaps a worktree only when the
   lease is TTL-expired **and** `_owner_state(lease)` (`lease_broker.py:4264`) returns `"dead"`;
   `"live"` and `"unknown"` are retained (`:4320-4327`). Git can tell you a worktree exists. It cannot
   tell you the process that owned it is dead. That probe is the load-bearing half.
2. **It violates an existing stated rule.** The docstring of `make_worktree_sweep_adapter`
   (`team_teardown.py:1241-1248`) reads *"Worktrees go through the canonical #356 `sweep` only (R6) —
   never a direct `git worktree remove`."* A git-driven reaper is the exact thing that rule forbids, and
   it was written deliberately.

   ⚠️ **Name collision — read carefully.** The "R6" inside that docstring is **issue #358's**
   requirement 6, quoted from the plan that built teardown. It is **not** this plan's R6 (which is the
   unrelated rule that `tests/test_agy_run_lease.py` must pass unmodified). Every mention below writes
   **#358's R6** in full to keep the two apart.

So the replacement needs an **owner-liveness probe** independent of leases (pid plus boot-id
generation is what `_owner_state` uses) plus enumeration, and it needs **#358's R6** either honored or
explicitly retired with a reason. This is materially more than "swap in git." Rejected: keeping a lightweight
lease-shaped registry purely to index worktrees — but note that rejection is now weaker, because such
a registry is close to what an honest replacement looks like.

**KTD9 — Engine dispatch hard-requires the lease module and pins its protocol version; unwinding it is
real work, not deletion.** Verified rather than assumed, and the answer inverts the optimistic reading.
`engine_dispatch.py:799` looks like a degradation-tolerant load — `lease_module, lease_degradation =
_load_fleet_module("lease_broker")` — but `:800-804` raises:

```python
if lease_module is None:
    raise DispatchError(
        "engine dispatch requires lease-capable fleet-core; install/update fleet-core: "
        + lease_degradation
    )
```

`lease_degradation` is an error-message string, not a fallback path. `_load_fleet_module`'s docstring
promises "version skew degrades named, never crashes" (`:46-54`), and the caller then converts that
graceful `None` straight into an exception. On top of it, `_require_lease_protocol(lease_module)` at
`:805` gates on `_REQUIRED_LEASE_PROTOCOL_VERSION`, so dispatch is coupled to a lease **protocol
version**, not just to the module's presence. U3 must remove a hard requirement and a version gate,
across four such load sites.

**KTD10 — Deleting from claude cannot break codex's port contracts.** Verified rather than assumed.
`port_contract.git_inventory()` at `scripts/port_contract.py:232` runs
`git diff --name-status -z -M {base}..{target}` between two **pinned commits**, so the oracles read
immutable history, not the live worktree. Both pinned commits —
`a6f3bcff` (2026-07-16) and `cf15a09f` (2026-07-18) — are present and are ancestors of `main`. The
consequence is a hard constraint, not a free pass: **history containing those commits must never be
rewritten or pruned.**

**KTD11 — The collision refuse-mode admission guards against has never been recorded; that settles the
scope fork toward Option C, with a stated telemetry gap.** Measured on 2026-07-30 against the live
lease state at `~/.local/state/infiquetra/fleet-leases/registry.json`, not inferred.

What the registry shows:

- **2,045 lease acquisitions** over the broker's lifetime (`next_fencing_sequence: 2046`), across
  **128 distinct resource keys**.
- **26 of those keys are outcome-dispatch admission keys** — `logical_unit_id` values of the form
  `outcome:{outcome-id}:{leaf}:outcome:{digest}:frontier:…`, which is the key shape
  `outcome_dispatcher.py:295-303` builds for its `on_conflict="refuse"` acquire. The refuse-mode path
  was therefore genuinely exercised, not dead code.
- **Nothing is live now**: `leases`, `settlements`, `session_admissions`, and
  `closed_owner_admissions` are all 0 entries.
- **Zero recorded refusals, anywhere.** A workspace-wide search for `LeaseConflictError` and the
  broker's refusal message (`"refuse-mode admission will not supersede it"`,
  `lease_broker.py:2420-2422`) returns 21 files across both repositories. Every one is a plan, a code
  review, a `DECISIONS.md` entry, a build-time workflow-evidence file from the work that *created*
  refuse-mode (#627, #637), or codex's port of the same. **None is a production halt record.**

Two limits, stated rather than buried, because they are what would make this conclusion wrong:

1. **Refusals were never persisted.** A refuse-mode conflict raises `LeaseConflictError`, surfaces as a
   `DispatcherError` halt, and is written to no counter, ledger, or log. "Zero recorded" is therefore
   partly absence of telemetry, not purely absence of events. This was a known gap at build time — the
   #627 code review logged it as an accepted tradeoff with "branch on `LeaseConflictError` vs other
   `DispatcherError` causes for escalation" routed to follow-up, at
   `docs/evidence/issue-627/artifacts/ce4ff9605026457f5a004ef36f3f9176e6f28630cabb130e7d8c565617f44ebd.md:50`
   (full filename given because the earlier elided form was not resolvable).
2. **The observation window is about eight days.** The broker landed 2026-07-16; enforcement has been
   durably `off` since 2026-07-24 (`INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off` at
   `~/.claude/settings.json:11`, confirmed present in the current environment). Refuse-mode itself was
   only hardened on 2026-07-21/22 by #637, so the window for the hardened form is narrower still.

Rejected alternative: treat "never happened" as operator recollection and proceed. Rejected because the
operator explicitly hedged it ("I don't think"), and the registry could be read directly.

**KTD12 — Worktree auto-reclamation is already dead on the teardown path, so that accepted loss is
narrower than first written.** Verified rather than assumed. `make_worktree_sweep_adapter`
(`team_teardown.py:1241`) takes an optional `worktree_reaper`, and its docstring is explicit that without
one "every worktree stays visibly retained." The reaper reaches it only through `production_adapters`
(defined `:1378`, threading the argument at `:1419`) — and all **three** production call sites pass no
reaper: `plugins/saga/hooks/team_teardown_hook.py:80`, `team_teardown.py:1710`, and `:1724`, each calling
`production_adapters(broker)` bare. The only path that actually reaps is
`outcome_worktrees.py:674`, which injects `_validated_reaper`.

Consequence for the plan: deleting the broker removes worktree reaping **only** for the outcome-worktree
path. For team teardown it changes nothing, because nothing was being reclaimed there in the first
place. U2 should stop describing this as a general loss.

## High-Level Technical Design

The import graph is three layers deep, which fixes the unwind order:

```
        11 leaf consumers  (saga scripts + hooks + team-execution)
                    │  import lease_broker as {saga_leases, fleet_leases}
                    │  or fleet_commons_shim.load("lease_broker")
                    ▼
        plugins/saga/scripts/lease_broker.py        574 lines   ← saga-side wrapper
                    │
                    ▼
        plugins/fleet-core/scripts/fleet_commons/
          lease_broker.py      4,731   ← the module
          orphan_evidence.py   1,578   ← already production-consumerless
```

**Reconciling the three counts that describe the same work**, because they differ and all three appear in
writing: **11** leaf consumers (the table below), **12** files to unwind (the 11 plus the saga wrapper
`plugins/saga/scripts/lease_broker.py`, which is what issue #677's title means by "12 remaining
importers"), and **91** call sites across those 12. The `fleet-core` module and the two fleet test suites
are deletions, not unwinds, so they are in none of the three figures.

Nothing may delete a layer until the layer above it is clear. Leaf consumers reach the module through
four different aliasing idioms, which is why a name-based grep undercounts:

| Idiom | Example |
|---|---|
| `import lease_broker as saga_leases` | `plugins/saga/scripts/second_opinion.py:25` |
| `import lease_broker as fleet_leases` | `plugins/saga/scripts/outcome_worktrees.py:47` |
| `_load_fleet_module("lease_broker")` | `plugins/saga/scripts/engine_dispatch.py:799` |
| `fleet_commons_shim.load("lease_broker")` | `plugins/team-execution/.../lease_protocol.py:19` |

**Measured call sites per file.** Alias-based counts are an upper bound — the alias may serve
non-broker uses in the same file — so treat these as sizing signals, not exact totals:

| File | Lines | Call sites | Capability |
|---|---|---|---|
| `plugins/saga/scripts/engine_dispatch.py` | 2,586 | ~23 | dispatch |
| `plugins/saga/scripts/outcome_worktrees.py` | 980 | ~16 | worktree routing |
| `plugins/saga/scripts/team_teardown.py` | 1,741 | 13 | teardown / reclamation |
| `plugins/team-execution/.../liveness_protocol.py` | 798 | ~9 | liveness |
| `plugins/saga/scripts/outcome_compat.py` | 1,700 | 6 | settlement / handoff |
| `plugins/saga/scripts/workflow_emitter.py` | 261 | 6 | emitted contract |
| `plugins/saga/hooks/lease_lifecycle_hook.py` | 92 | 6 | hook protocol |
| `plugins/team-execution/.../lease_protocol.py` | 234 | ~4 | lease protocol |
| `plugins/saga/scripts/second_opinion.py` | 1,539 | ~3 | second opinion |
| `plugins/saga/scripts/outcome_dispatcher.py` | 879 | ~3 | dispatch |
| `plugins/saga/scripts/outcome.py` | 2,979 | 2 | outcome driver |
| `plugins/saga/hooks/team_teardown_hook.py` | 110 | 6 | teardown hook |
| `plugins/saga/scripts/outcome_decompose.py` | 439 | 5 | decompose / prune |

⚠️ **The last two rows were added on 2026-07-30, after decomposition, and neither appears in the
idiom table above — which is exactly why they were missed.** `team_teardown_hook.py` reaches the
broker through `team_teardown.default_broker()`; `outcome_decompose.py` receives it as an injected
`lease_authority` parameter. Neither ever writes the string `lease_broker`. This is the third
instance of the same escape (the first was `liveness_events.py`, see R4a), so **any survey that greps
only for `lease_broker` is known-incomplete** — grep `lease_authority` and `fleet_leases` too.

**Three capabilities the broker still carries**, per decision `{#split-not-fence-671}`: *"admission,
liveness, and mutation authority — never file containment."* An earlier draft dismissed two of the
three. Verified in the source, that was wrong — **admission and liveness have more live call sites
than fencing does**, and #673's emit-time check replaces none of them:

- **Admission — LOAD-BEARING, no replacement exists.** `outcome_dispatcher.py:295-303` uses
  `acquire_agent(..., mutation="none", on_conflict="refuse")` as leaf-dispatch **idempotency**. Its
  own comment: *"A live, unexpired prior on the same content-derived digest (a concurrent runtime
  preparing the same leaf) refuses here at admission with a typed conflict … rather than silently
  superseding the peer and double-preparing the leaf."* This is not file containment. #673 checks two
  units within one spec at emit time; this refuses two **runtimes** preparing the same leaf, keyed on
  a content digest, scoped per `git-common-dir`. Deleting it re-opens double-preparation.
  Also live: session and aggregate concurrency limits via `concurrency_policy.AdmissionLimits()`
  (`:283-284`), and `close_owner_admission` gating whether a team run may be declared closed
  (`team_teardown.py:806`, `:931`).
- **Liveness — LOAD-BEARING for identity, separable for the engine.** `liveness_engine.py` never
  imported the broker, so KTD5's rename still holds. But `liveness_protocol.py:257-284`
  `bind_identity()` calls `selected.verify_agent(agent_id)` as the **trusted identity source** —
  its docstring is explicit that the *"caller cannot choose their digests or generations."* Delete
  the broker and nothing supplies untamperable identity. Also live: `Providers().boot_id()` restart
  detection (`:462`) and TTL renew/sweep across four files.
- **Mutation authority — genuinely gone.** `lease_mutation_hook.py` was deleted by #674 and
  `assert_write_target` now has no callers outside the broker module. This one really is vestigial.

Fencing-only usage — the part #673 actually replaced — is concentrated in three places:
`outcome_compat.py`'s handoff protocol, `engine_dispatch.py`'s manifest-transition CAS
(`:1960-2010`, `:2453-2464`), and parts of `outcome_worktrees.py`.

## Implementation Units

**Decomposed into cards on 2026-07-30.** Issue #677 is now the parent; each unit below is a child
issue on the Operations board (project 3), Objective `defects-claude-plugins`, Status `Shaping`:
U1 → #678, U2 → #679, U3 → #680, U4 → #681, U5 → #682, U6 → #683, U7 → #684.

Units are file-disjoint so any two may share a dependency wave without tripping
`assert_no_wave_file_conflicts()` (R7). U1 through U4 may run in parallel; U5 requires all of them.

**U2 and U3 run in parallel — the sequencing question is closed (2026-07-30).** An earlier draft warned
that U2 would have to add a dependency on `outcome_worktrees.py` while U3 rewrites it, and left the
ordering open. That warning rested on a wrong premise. The enumeration source U2 needs already exists and
is broker-free: `outcome_worktrees.live_worktrees(store, ops)` at `:314` reads the worktree registry
(`worktrees.json`, a `{subplot_id -> entry}` map) and asks git whether each registered `path` still
exists. It reads `entry["path"]` only — the registry's `lease` field is consumed solely by `_lease_binding`
at `:192`, which feeds the `prevalidate_reap_authority` reap path U3 deletes.

What is genuinely missing is smaller and lives inside U2: `team_teardown.py` imports only
`fleet_commons_shim` and `run_ledger`, and `reclaim_all(...)` takes `subplot_id` and `team_run_id` but no
outcome store, so it cannot locate `worktrees.json`. The store is threaded in through
`plugins/saga/hooks/team_teardown_hook.py` — the single production caller of `production_adapters`, and now
part of U2. That is caller-side plumbing, not an interface U3 must build and hand over.

The residual coupling is one contract, carried as a **non-goal on U3**: do not remove or change
`read_registry` (`:138`), `live_worktrees` (`:314`), or the registry entry's `path` field. U2 imports the
first two and edits neither, so the units still declare disjoint file sets and
`assert_no_wave_file_conflicts()` remains sufficient.

### U1. Unwind settlement and handoff — issue #678

Remove the broker from the dispatch-settlement and successor-handoff path built by #351.

**Files:** `plugins/saga/scripts/outcome_compat.py` (1,700 lines, 6 call sites at `:1328`, `:1393`,
`:1413`, `:1545`, `:1643`, `:1664`).

**Approach:** The calls are `verify`, `prepare_agent_settlement`, `commit_agent_settlement`,
`inspect_resource_head`, `acquire_successor`, `verify`. Settlement's purpose was at-least-once
accounting for dispatched work; with no lease, the resource-ref/token pair it verified does not exist.
Remove the lease verification and let settlement record outcomes without a fencing token. Where a
function's only job was to thread a token, delete the function rather than leaving a pass-through.

**Test scenarios:** `tests/test_saga_outcome_compat.py` — a settlement records a terminal outcome with
no lease present; a successor handoff completes without `acquire_successor`; a settlement for an
unknown dispatch id still raises rather than silently passing.

### U2. Unwind teardown, preserving the disposition vocabulary (not the reaping — there is none) — issue #679

Strip the broker from the non-skippable teardown contract built by #358. Per **KTD12** this unit does
**not** need to preserve worktree reclamation, because teardown never performed any: all three
production call sites construct `production_adapters(broker)` with no `worktree_reaper`, so the sweep's
reap branch is unreachable in production and every worktree is already left retained. What must survive
is the **disposition reporting** teardown's evidence refs are built from, not a removal capability that
was never wired.

**Files:** `plugins/saga/scripts/team_teardown.py` (1,741 lines) and — **added 2026-07-30** —
`plugins/saga/hooks/team_teardown_hook.py`, the only production caller of `production_adapters` and a
broker consumer in its own right (`team_teardown.default_broker()` at `:50`, `read_decision_input` at
`:56`, `broker.root_sha256` at `:58`, `production_adapters(broker)` at `:80`). It escaped the consumer
survey because it never imports `lease_broker` — it reaches the broker through `default_broker()`. It is
also where the outcome store is threaded into `reclaim_all`. In `team_teardown.py` there are **13
broker-touching sites, counted
precisely:** 11 direct broker-method calls at `:532`, `:806`, `:931`, `:1036`, `:1072`, `:1105`, `:1214`,
`:1228`, `:1260`, `:1311`, `:1403`, plus 2 invocations of the `_current_head(broker, …)` helper
(defined `:1063`) at `:1253` and `:1270`. An earlier draft printed "13" beside a list of 11 lines, which
read as a miscount; the helper calls are the other two.

**Approach:** Calls are `inspect` ×2, `close_owner_admission` ×2, `inspect_owner_admission`, `release` ×4,
`sweep(worktree_reaper=…)`, `acquire_agent`. Most are straightforward removals. The `_worktree_sweep`
closure at `:1251-1277` is not — per **KTD8** it is lease-indexed end to end:

```python
head, _token = _current_head(broker, lease)          # :1253  lease head
swept = broker.sweep(worktree_reaper=worktree_reaper) # :1260  broker enumerates
if lease_id in result.get("reaped_worktree_leases", []):   # :1262  keyed by lease_id
retained_reason = result.get("retained", {}).get(lease_id) # :1267  keyed by lease_id
follow_up, _ = _current_head(broker, lease)                # :1270  second lease-head read
```

The closure runs to `:1277`, not `:1272` — an earlier draft cut the range short and so missed its last
two branches (`released-by-sweep` at `:1272` and the `not-a-sweep-candidate` fallthrough at `:1277`).
**R5c** carries the full five-outcome inventory; work from that table, not from this excerpt.

So this is a **re-key**, not a replace: enumerate worktrees from `git worktree list` cross-referenced
with `outcome_worktrees.py`'s per-leaf routing, and re-key the `ActionOutcome` dispositions
(`already-absent`, `released`, `retained`) on worktree path instead of `lease_id`. Keep the disposition
vocabulary — it is what teardown's evidence refs are built from.

**KTD8's objection does not bite here, and the reason matters.** KTD8 records that `git worktree list`
cannot substitute for the broker's `sweep`, because `sweep` reaps only when a lease is TTL-expired
**and** `_owner_state(lease) == "dead"` (`lease_broker.py:4264`, `:4277-4280`), and git cannot supply
owner-liveness. That is a fatal objection to enumerating in order to **remove**, and it is also why
**#358's R6** (quoted in `make_worktree_sweep_adapter`'s docstring — not this plan's R6) forbids a direct
`git worktree remove`. This unit removes nothing — it enumerates in order to **report**. Reporting
`retained` for a worktree that git still lists needs no liveness judgment. Any future attempt to add
removal here re-opens KTD8 in full.

Risk is materially lower than the earlier draft of this plan assumed, because the mechanism being
replaced is a reporting surface rather than a reclamation guarantee. It is still the unit where the
existing tests assert on lease-keyed dispositions and so must be rewritten alongside the code, which
means they cannot serve as its safety net. Land this unit alone, not batched.

**Test scenarios:** `tests/test_team_teardown.py` — with no broker present, teardown reports a
worktree that `git worktree list` still shows as `retained` with a reason code; a worktree git no
longer lists yields `already-absent`; teardown with zero worktrees is a clean no-op; teardown of an
already-torn-down run is idempotent; **and a regression sentinel: teardown removes no worktree from
disk under any input**, which pins KTD12's finding that reclamation was never teardown's job.

### U3. Unwind dispatch and worktree routing — issue #680

The largest unit by call-site count — the two files where broker use is genuinely threaded rather than
localized.

**Files:** `plugins/saga/scripts/engine_dispatch.py` (2,586 lines, ~23 sites; loads at `:799`,
`:1043`, `:1960`, `:2453`), `plugins/saga/scripts/outcome_worktrees.py` (980 lines, ~16 sites;
imports at `:47`), and — **added 2026-07-30** — `plugins/saga/scripts/outcome_decompose.py` (439
lines), whose prune path takes `lease_authority` at `:259` and threads it at `:288`, `:292`, `:306`,
`:346`, calling `prevalidate_reap_authority(...)` — the exact function this unit deletes. It escaped
the consumer survey because it never imports `lease_broker`; it receives the authority as an injected
parameter.

⚠️ **Non-goal for this unit:** do not remove or change `read_registry` (`:138`), `live_worktrees`
(`:314`), or the registry entry's `path` field in `outcome_worktrees.py`. U2 imports the first two as
its broker-free worktree enumeration source. They touch no lease code today — the registry's `lease`
field is read only by `_lease_binding` (`:192`), which feeds the reap path this unit removes.

**Approach:** The loader *looks* degradation-tolerant and is not — per **KTD9**, `:800-804` converts the
graceful `None` into a raised `DispatchError`, and `_require_lease_protocol()` at `:805` additionally
pins `_REQUIRED_LEASE_PROTOCOL_VERSION`. So there is no existing no-lease path to fall back into. Each
of the four load sites (`:799`, `:1043`, `:1960`, `:2453`) needs its hard requirement and its version
gate removed, plus whatever `lease_admission.validate()` and `_bounded_lease_identity()` feed
(`:796-798`). Check whether `_require_lease_protocol` and `_REQUIRED_LEASE_PROTOCOL_VERSION` have any
non-lease callers before deleting them.

One easy-to-miss dependency in the same file: `outcome_worktrees.py` takes a `lease_ttl_seconds`
parameter at `:384`, `:572`, and `:838`, each **defaulting to the broker constant**
`fleet_leases.authority.DEFAULT_TTL_SECONDS`. That default vanishes with the module, so each signature
needs either a literal replacement default or the parameter removed — and `tests/test_outcome_worktrees.py`
passes `lease_ttl_seconds=` explicitly at ten call sites, so the choice is test-visible. This is a
*different* `lease_ttl_seconds` from the liveness observation field in R4a; do not conflate them.

`outcome_worktrees.py` is the file that routes sub-outcomes into per-leaf worktrees — the *second*
isolation mechanism that made the broker redundant for outcome paths (per #671's own analysis). Its
lease use is mostly bookkeeping over an isolation it already achieves structurally, with one exception
that this unit must not gloss over.

**This unit is where the one real reclamation loss lands.** Per **KTD12**, `outcome_worktrees.py:674` is
the *only* production site that actually reaps: `swept = lease_authority.sweep(worktree_reaper=
_validated_reaper)`. Deleting it means stale per-leaf outcome worktrees accumulate until reclaimed by
hand. That is the second accepted loss in the Scope Decision table, and it is the one with a known
precedent: an earlier manual cleanup in this workspace removed 88 redundant worktrees. Two obligations
follow, neither optional:

1. The decision record must name this loss specifically — outcome worktrees, not "worktrees."
2. This unit ships an operator-facing reclamation path to replace it, even a manual one (a documented
   `git worktree list` + prune procedure, or a small script). Deleting an automatic reaper and leaving
   no documented substitute converts an accepted loss into an unrecorded one.

Also handle admission's third capability here: `engine_dispatch.py:796-798` feeds
`lease_admission.validate()` and `_bounded_lease_identity()`. Under Option C the identity check becomes
caller-asserted — the one accepted loss taken on judgment rather than measurement (Scope Decision
table, row 2). Note it in the code comment that replaces the check, so the next reader knows it was a
decision and not an oversight.

**Test scenarios:** `tests/test_engine_dispatch.py` — dispatch completes with no lease module
importable; a dispatch that previously acquired a lease still records its engine resolution; two
concurrent dispatches of the same leaf both proceed and neither raises (pinning the accepted
idempotency loss as intended behavior rather than a regression).
`tests/test_outcome_worktrees.py` — a sub-outcome routes into its own worktree with no lease; two
sub-outcomes get distinct worktrees; worktree cleanup runs without lease release; the documented
manual reclamation path removes a stale leaf worktree.

### U4. Unwind the light consumers and the emitted contract — issue #681

Four files with few call sites each, grouped because none needs restructuring.

**Files:** `plugins/saga/scripts/outcome.py` (2 sites: `:1853` broker construction, `:2810`
`acquire_agent`), `plugins/saga/scripts/second_opinion.py` (~3), `plugins/saga/scripts/outcome_dispatcher.py`
(~3, loads at `:88`, `:259`, `:281`), `plugins/saga/scripts/workflow_emitter.py` (sites at `:117`,
`:151`, `:186` broker construction, **`:187` the live `renew_batch`**, `:198`, `:254`, `:255` — an earlier
draft's list stopped at `:186` and so omitted the one site KTD4 singles out as load-bearing).

**Approach:** Mostly deleting a construction and an acquire. `workflow_emitter.py` is the exception —
it holds the live `renew_batch` call at `:187` (KTD4) and catches `lease_broker.HookInputError` and
`lease_broker.authority.LeaseBrokerError` at `:254-255`. Those two exception types disappear with the
module, so the surrounding `except` must be re-narrowed, not just shortened; catching nothing where it
used to catch lease errors is a behavior change worth stating in the CHANGELOG.

**Test scenarios:** `tests/test_workflow_emitter.py` — an emit completes with no batch lease; an emit
whose child fails still surfaces the failure through the re-narrowed handler.
`tests/test_saga_outcome.py` — an outcome run starts with no broker constructed.

### U5. Delete the hook and the saga wrapper — issue #682

Two whole-file deletions, unblocked once U1–U4 land.

**Files:** `plugins/saga/hooks/lease_lifecycle_hook.py` (92 lines, delete) and
`plugins/saga/scripts/lease_broker.py` (574 lines, delete).

**Approach:** Remove the hook's registration in the plugin's hook manifest in the same commit as the
file — a dangling registration is a startup error, not a dead entry. Confirm the manifest surface by
reading it, not by grepping Python. Verify no remaining `import lease_broker` in saga before deleting
the wrapper.

**Depends on:** U1, U2, U3, U4.

**Test scenarios:** `tests/test_saga_plugin.py` — the hook manifest contains no reference to the
deleted hook; the plugin loads with no lease hook registered. `tests/test_saga_hooks.py` — the
remaining hooks still fire.

### U6. Unwind team-execution and decouple liveness — issue #683

The second consumer set, plus the R4 rename.

**Files:** `plugins/team-execution/skills/team-execution/scripts/lease_protocol.py` (234 lines,
loads at `:19`), `.../liveness_protocol.py` (798 lines, ~9 sites at `:242`, `:257`, `:258`, `:462`, and the
wire producer at `:291`), `plugins/fleet-core/scripts/fleet_commons/liveness_engine.py` (the rename at
`:94`, `:288`, `:289`, `:367`), and — **added by this review, previously in no unit** —
`plugins/saga/scripts/liveness_events.py` (`:65`, `:207`, `:236`, `:258`, `:644`).

**Approach:** `lease_protocol.py` is a candidate for whole-file deletion — confirm whether anything
in it survives the lease concept. `liveness_protocol.py:242` takes `lease_broker: Any | None = None`
as an injected dependency and constructs a default at `:258`; remove the parameter rather than
defaulting it to `None` forever. Then apply KTD5's rename across **all five files in R4a's table, in one
commit** — `liveness_events.py:236` parses the wire key and `:258` writes it, while
`liveness_protocol.py:291` produces it, so a partial rename fails at runtime with a `KeyError` rather
than at import time or in mypy. Also update the `_finite_nonnegative(…, "lease_ttl_seconds")` string
literal at `liveness_engine.py:289`, which surfaces in operator-visible error text.

**Test scenarios:** `tests/test_team_execution_liveness.py` — liveness reports a suspect resident with
no lease module present; the cold-start branch fires from a supplied `ttl_seconds` with no lease.
`tests/test_liveness_engine.py` — `ttl_seconds` drives `ttl-cold-start`; the old field name is gone.
`tests/test_liveness_events.py` — an event round-trips through serialize-then-parse under the new key,
and `IDENTITY_KEYS` no longer names `lease_ttl_seconds`.

### U7. Delete fleet-core, add the re-add guard, move the release surfaces — issue #684

The payload unit: 10,203 lines out, one guard test in.

**Files:** delete `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (4,731),
`orphan_evidence.py` (1,578), `tests/test_fleet_lease_broker.py` (2,709), `tests/test_orphan_fencing.py`
(1,185). Edit `tests/test_fleet_doctor.py` (drop its orphan-evidence probe). Add
`tests/test_no_lease_broker_readd.py`. Move `fleet-core`, `saga`, and `team-execution` plugin versions,
their CHANGELOGs, and the generated `.claude-plugin/marketplace.json`.

**Approach:** Edit `fleet-core`'s `plugin.json` `description` to drop *"lease and"* (R11a), then generate
`marketplace.json` with `scripts/sync_marketplace.py` from the source-of-truth `plugin.json` files — never
hand-edit it. Run `scripts/check_release_surface_parity.py` before opening the pull request. Also carry the
fleet-doctor documents named in R11 (`saga/skills/fleet-doctor/SKILL.md`,
`saga/references/fleet-doctor-sources.md`, `saga/commands/fleet-doctor.md`) in this unit, alongside the
`tests/test_fleet_doctor.py` edit.

The re-add guard is the unit's real product. It must scan **resolved** module paths, not only the repo
tree: defect #642 was `fleet_commons_shim` rung 3 trusting a stale `installed_plugins.json` and
resurrecting an old broker from a plugin cache. A guard that only greps `plugins/` would not have
caught that.

**Depends on:** U5, U6.

**Test scenarios:** `tests/test_no_lease_broker_readd.py` — no file under `plugins/` imports
`lease_broker` or `orphan_evidence`; the guard fails when handed a fixture that does; the guard
inspects shim-resolved paths, not just the tree. `tests/test_fleet_doctor.py` — doctor runs with no
orphan-evidence module. `tests/test_agy_run_lease.py` — passes unmodified (R6).

## Verification

Added by review — the plan previously named per-unit test scenarios but no repository quality gates, so
an agent following it literally would not know what "green" means. These are the repo's own gates, from
`CLAUDE.md`, and every unit must pass all of them before its pull request opens:

```bash
rtk proxy uv run pytest -q                                    # baseline BEFORE touching anything
uv run ruff check . && uv run ruff format --check .            # CI runs both; check-clean can still fail format
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports  # match CI scope, not just plugins/
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py                          # newest-first journal ordering
python3 scripts/check_release_surface_parity.py                # R8 — before opening the PR
```

Take the `pytest` baseline before the first edit. This teardown deletes two large test suites
(`test_fleet_lease_broker.py` 2,709 lines, `test_orphan_fencing.py` 1,185) and adds new ones, so the
collected count moves in both directions across U1–U7. Record the per-unit delta in each pull-request
body rather than asserting a target number here — an unexplained drop is the signal that a deletion
reached past its unit.

Cross-unit sentinels, checked at every unit boundary and not only at the end:

1. **`tests/test_agy_run_lease.py` passes unmodified** (R6 — this plan's R6, the subprocess-lease rule).
2. **No production file under `plugins/` reaches the broker** once U7 lands. Grep for all four names,
   not just the module — two consumers were missed on 2026-07-30 precisely because they never write
   `lease_broker`:
   ```bash
   grep -rn "lease_broker\|orphan_evidence\|lease_authority\|fleet_leases" plugins/ --include=*.py
   ```
   must return nothing, and the U7 guard test pins it against shim-*resolved* paths, not just the tree.
3. **The four bare-string exclusions in Scope Boundaries stay intact** — `tests/test_agy_apply_policy.py`'s
   ban-list assertions and the two agy documents that retain `auto-if-clean` as dated records.

## Risk Analysis & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| A `grep -i lease` sweep deletes subprocess-lease handling (`run-lease.json`, `LEASE_RENEWAL_INTERVAL_SECONDS`) | high | R6 — `tests/test_agy_run_lease.py` must pass **unmodified**. If it needs editing, revert and narrow. |
| `promote_scan.py:504` defines its own unrelated `assert_write_target(path, workspace_root, context_library)` | high | Named in Scope Boundaries. Different signature, different job — a symbol-name search will collide with it. |
| U2 silently stops reclaiming worktrees | **retired as a risk** | KTD12 — teardown never reclaimed any: all three production sites pass no `worktree_reaper`. U2 re-keys a reporting surface, not a reclamation guarantee. Retained obligation: its tests must still be rewritten with it, and a sentinel must assert U2 removes nothing from disk. |
| **U3 silently stops reclaiming outcome worktrees** | **high** | The real version of the risk above. `outcome_worktrees.py:674` is the only production reaper (KTD12), and Option C deletes it deliberately. Mitigation is disclosure plus substitution, not prevention: name the loss in the decision record and ship a documented manual reclamation path in the same unit. |
| `fleet_commons_shim` resurrects a deleted broker from a stale plugin cache | medium | Exactly defect #642's mechanism. The U7 guard must scan resolved paths. |
| `engine_dispatch.py` has no no-lease path — it raises, and pins a lease protocol version | **confirmed** | KTD9. Budget U3 as real work across four load sites plus a version gate, not as deletion. The optimistic reading of `_load_fleet_module` is wrong. |
| Re-narrowing `workflow_emitter.py:254-255` swallows a different error class | medium | Name the behavior change in the CHANGELOG under `Changed`, not `Removed`. |
| History rewrite makes the port contract's pinned commits unreachable, breaking codex | low | KTD10 — stated as a hard constraint. Never rewrite or prune history containing `a6f3bcff` or `cf15a09f`. |
| U1 through U4 turn out larger than one reviewable pull request each | medium | Split by file, not by layer; every split must leave the suite green. |
| **Shipped skills instruct agents to use a deleted mechanism** | **high** | R11 — 13 agent-facing documents describe the broker as current behavior, including `saga/skills/work/SKILL.md` and `team-execution`'s SKILL and lease-protocol reference. No unit listed a Markdown file until this review. Each document moves with the unit that removes the behavior, never batched at the end. |
| **The R4 rename half-lands and breaks the liveness event schema at runtime** | **high** | R4a — the field crosses five files including a wire parse at `liveness_events.py:236` and a serialize at `:258`. A partial rename raises `KeyError` at event-parse time, not at import time and not under mypy, so neither the type checker nor a smoke import catches it. Rename all five in one commit; round-trip test required. |
| U3 deletes `read_registry` / `live_worktrees` along with the reap path, breaking U2's enumeration | medium | **Resolved 2026-07-30 — no sequencing needed.** U2 imports those two broker-free functions and edits no file U3 owns, so the units stay file-disjoint and `assert_no_wave_file_conflicts()` remains sufficient. The residual coupling is one contract, carried as an explicit non-goal and acceptance criterion on U3: both functions and the registry's `path` field survive. |
| A broker consumer that never imports `lease_broker` is missed entirely | high | This has now happened three times: `liveness_events.py` (R4a), `team_teardown_hook.py` (reaches the broker via `default_broker()`), and `outcome_decompose.py` (receives `lease_authority` as an injected parameter). All three are assigned. Mitigation for the next one: U7's re-add guard greps `lease_authority` and `fleet_leases`, not only `lease_broker`. |

**Pre-mortem — the most likely way this fails.** Not the deletion, and no longer U2. Measurement moved
this risk: KTD12 established that teardown was never reclaiming worktrees, so U2 cannot lose a
capability it never had. The failure mode relocates to two places, one technical and one procedural.

*Technical.* U3 deletes `outcome_worktrees.py:674`, the only production reaper. Stale per-leaf outcome
worktrees then accumulate silently — no error, no failing test, nothing until disk fills. There is
precedent for exactly this: 88 redundant worktrees were cleared by hand in this workspace once already.
Mitigation is not prevention, because the loss is deliberate — it is substitution. If U3 lands without
a documented reclamation procedure, this plan has traded a working automatic reaper for nothing and
recorded it nowhere.

*Procedural, and the likelier of the two.* The Scope Decision rests on three accepted losses of
**unequal** strength. Two are measured; the identity loss is operator judgment with no measurement
behind it (Scope Decision table, row 2). The failure is that the decision record flattens all three into
one confident paragraph, and six months from now the identity loss reads as evidence-backed because it
sits next to two things that were. Mitigation: the `DECISIONS.md` entry must carry the per-loss basis
column verbatim, including the words "judgment only," and a distinct "revisit when" condition for the
identity row.

The tell to watch for on the technical side: if U3's tests pass without ever creating and reclaiming a
real routed sub-outcome worktree, they are asserting the new code's shape rather than its behavior.
Verify against `git worktree list` output from an actual routed sub-outcome.

## Scope Boundaries

**Explicit non-goals.**

- Do NOT delete `fleet_commons/concurrency_policy.py` (78 lines) — R3, it is the replacement's policy
  source.
- Do NOT touch anything named `run-lease`. `plugins/agy/scripts/agy_delegate.py`'s `run-lease.json` and
  `tests/test_agy_run_lease.py` are subprocess supervision.
- Do NOT touch `plugins/saga/scripts/promote_scan.py:504` — its `assert_write_target` is a different
  function with a different signature that happens to share a name.
- Do NOT modify `tests/test_agy_apply_policy.py`'s ban-list assertions. It mentions `lease_broker` and
  `orphan_evidence` deliberately, as the guard proving those strings are absent from `agy_delegate.py`.
- Do NOT rewrite `plugins/agy/README.md` or `plugins/agy/docs/harness-proof.md`. They retain
  `auto-if-clean` as annotated dated records; `tests/test_agy_plugin.py` asserts the strings persist.
- Do NOT re-enable `INFIQUETRA_FLEET_LEASE_ENFORCEMENT` to exercise the old path before deleting it.
- Do NOT rehome batch renewal before deleting (KTD3) — that inverts cost and benefit for a path nobody
  runs.
- Do NOT reopen the #671 design question. If the emit-time check proves not to cover a path the broker
  covered, stop and escalate rather than adding a runtime guard.

**Deferred to Follow-Up Work.**

*(Nothing about codex is deferred here — it is out of scope. See "Codex — out of scope" below.)*

**Issue dispositions.** Moved here by review from the tail of the codex section, where it was easy to miss
— none of these are codex issues. Verified against `gh` at review time:

| Issue | State | Disposition |
|---|---|---|
| #645 boot identity splits into incomparable cohorts | open defect | closes resolved-by-removal when U7 lands |
| #646 lease TTL lifecycle | open defect | closes resolved-by-removal when U7 lands |
| #647 worktree reservation without `worktree_root` | open defect | closes resolved-by-removal when U7 lands |
| #661 lease refusal names condition, not remedy | open defect | closes resolved-by-removal when U7 lands |
| #648 verifier lease health as refute-panel precondition | open **enhancement** | **needs a rewrite against the emit-time mechanism, not closure** — the capability is still wanted; only its lease-based implementation goes |
| #642 shim rung 3 resurrects a stale broker | **already closed** | cited only as the precedent mechanism the U7 guard must defend against |

The distinction matters at execution time: four of these close with the deletion, one does not, and
mis-closing #648 would drop a wanted capability on the floor.

## Codex — out of scope, operator-owned

**Not planned. No card filed. No file touched.** `infiquetra-codex-plugins` holds a ported twin of this
substrate, and the operator will decide its disposition directly with codex. This section exists only so
that decision starts from measurement instead of a re-derivation.

**Why it is out of scope — the reason is stronger than sequencing convenience.** Commit `45890ae`
(2026-07-29, tip of `main`) bumped codex fleet-core to **0.14.0**, and its CHANGELOG at
`plugins/fleet-core/CHANGELOG.md:5-17` reads: *"Narrow Fleet Core to model/profile resolution, bridge
and output proof, shims, **leases, concurrency, orphan evidence**, workflow compatibility, and a
stateless bounded 429 helper."* Leases and orphan evidence are named among what Fleet Core was narrowed
**to** — kept deliberately. The same commit's Removed section took out audit and delegation stores,
effort riders, cost weights, and the tier-table renderer; the diff confirms `audit_store.py` deleted and
`lease_broker.py` untouched. **A teardown there would reverse a cleanup that landed the same day.**
Planning it from this repo would risk undoing finished work on the strength of a conclusion reached
elsewhere.

One line in that same entry cuts the other way and belongs in the operator's deliberation: *"Codex 0.146
owns child lifecycle and liveness; callers own domain policy."* If the Codex CLI now owns liveness, the
liveness rationale for keeping the broker there may already be superseded — an argument for retirement
drawn from that commit's own reasoning. That tension is exactly why this is a decision, not a task.

### Measurements, preserved

Measured live at `main`, archives under `.codex/proofs/` and `.codex/cutover/` excluded — 17 live files,
and a hypothetical deletion payload of **10,631 lines**:

| Path | Lines |
|---|---|
| `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` | 4,581 |
| `plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py` | 1,578 |
| `plugins/fleet-core/tests/test_lease_broker.py` | 2,363 |
| `plugins/fleet-core/tests/test_orphan_evidence.py` | 1,185 |
| `plugins/saga/scripts/lease_broker.py` | 564 |
| `tests/test_saga_lease_broker.py` | 360 |

### Findings that bear on the operator's decision

1. **No unprotected concurrent-writer path.** There is no `plugins/team-execution/` in codex. Its
   replacement is the `verified-workflows` plugin with a root-owned DAG, per that repo's DECISIONS
   entry of 2026-07-10 — the root thread owns spawn, wait, and adjudication. team-execution residents
   sharing one tree were the *entire* reason #671 said keep the fence; codex never had them.
2. **The emit-time replacement already exists there, in a different plugin.** An earlier draft said
   codex "has no replacement and needs none." Half wrong. Codex has no `concurrency_governor.py` —
   it is explicitly `"defer"`-treated, never ported (`tests/test_lease_safe_substrate_port_contract.py:55`)
   — but `plugins/verified-workflows/scripts/workflow_dispatch.py:468-518` `_validate_graph()`
   independently implements the same guarantee: each `Assignment` declares a `writes` list, and any two
   assignments not in each other's dependency closure get a pairwise `_paths_overlap()` check that
   raises `WorkflowDispatchError(f"concurrent assignments … overlap writes …")`. It is on the live
   compile path, called from `compile_workflow_contract()` at `:637`. Codex's **saga** is the component
   without the check; `verified-workflows` has it. `fleet_commons/concurrency_policy.py` survives either
   way.
3. **The port contracts do not break.** KTD10 — the oracles diff pinned commits.

4. **If the operator ever does decide to retire it there, the port-contract cost is three test files,
   not two.** Recorded so it is not rediscovered late. Deleting `fleet_commons/lease_broker.py` from
   codex fails all three port-contract tests, by two different mechanisms:
   - `tests/test_lease_safe_substrate_port_contract.py` (U2 row) and
     `tests/test_codex_627_seam_refreeze_port_contract.py` (U3 row) fail the
     `(ROOT / target).is_file() or target in RETIRED_CURRENT_ARTIFACTS` check. Fix: add the literal
     manifest path string to **both** set literals (`:24` and `:63` — two separate copies), in the same
     commit as the deletion. That is the exact `45890ae` / `audit_store.py` precedent. Note the tighter
     invariant at `test_codex_627_seam_refreeze_port_contract.py:225` —
     `assert pending == sorted(RETIRED_CURRENT_ARTIFACTS & planned)` is a strict equality — and `:227`
     requires each artifact's parent directory to still exist.
   - `tests/test_lease_registry_forward_compat_port_contract.py` has **zero**
     `RETIRED_CURRENT_ARTIFACTS` references and needs a different fix: `:214-218` does a bare
     `AUTHORITY.read_text()` / `ADAPTER.read_text()` on the live paths (`:58-59`), so deletion raises
     `FileNotFoundError` before any assertion. It would need to read historical content via
     `git show <SOURCE_TARGET>:path`, or be retired with its port row.

Also worth noting for that decision: codex's `plugins/saga/scripts/outcome_worktrees.py` sits inside the
frozen port range, so whatever this repo settles for worktree reclamation (see KTD8, currently unresolved)
may or may not transfer.

*(Issue dispositions for #645–#648, #661 and #642 moved to "Deferred to Follow-Up Work" under Scope
Boundaries — they are this repository's issues, not codex's, and belong there.)*

## Alternatives Considered

**Keep the broker, disarmed.** Rejected. It is already disarmed and that is the problem: 10,203 lines
carried as live code, with four open defect cards describing bugs in it. Disarmed-but-present is the
worst of both — the maintenance cost with none of the protection.

**Delete fleet-core first, fix the fallout.** Rejected. Eleven leaf consumers import through four
different aliasing idioms; deleting the base first turns a planned unwind into a compile-error hunt
with no ordering guarantee.

**One pull request for the whole teardown.** Rejected. ~91 call sites across 12 files spanning three
plugins is not reviewable in one pass, and R7 forces file-disjoint units anyway.

**Rehome batch renewal before deleting.** Rejected per KTD3 and consistent with
`{#fence-carried-batch-renewal-671}`, which already rejected it once for inverting cost and benefit.

**Plan the codex teardown alongside this one.** Rejected — see KTD6. That repo's newest commit kept the
lease substrate on purpose, so planning its removal from here would risk undoing a cleanup that just
landed. The operator owns that call.

**Option A — shrink the broker instead of deleting it** (keep an admission-and-liveness core, delete only
the fencing third). Rejected on the KTD11 measurement: the collision refuse-mode admission exists to
catch has never been recorded, so the core being preserved would guard an unobserved event while
`#645`/`#646`/`#647` stay open as live defects against code that is kept for that guard. Option A was
the honest reading of what #673 actually replaced, and it remains the correct fallback **if the
telemetry gap in KTD11 is ever closed and refusals turn out to have been firing silently.** (All **four**
open defects stay open under Option A, not three — #661 belongs in that list alongside #645/#646/#647.)

**Option B — delete everything and build three replacements** (cross-runtime dispatch idempotency, a
trusted identity source, an owner-liveness probe). Rejected as disproportionate: three new mechanisms,
each needing its own design pass, to preserve guarantees with no recorded need. Revisit when concurrent
multi-runtime dispatch of the same leaf becomes a real workflow rather than a hypothetical one — at
which point the idempotency mechanism should be built deliberately and standalone, not recovered from
the broker.
