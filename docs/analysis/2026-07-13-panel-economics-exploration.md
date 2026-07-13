# Panel economics — measured reviewer independence, consensus elasticity, acceptance-sampling review

- **Date:** 2026-07-13
- **Issue:** #462 (exploration; objective #338 "Build the fleet telemetry and ledger substrate")
- **Absorbed ideas:** `H-F6-10` (consensus elasticity, primary), `T5-F3-6` (measured independence,
  facet), `T5-F5-7` (acceptance-sampling review, facet) — per
  `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`, slug
  `pf-panel-economics-exploration`
- **Status:** recommendation document. No code shipped; no plugin behavior changed.
- **Question answered:** when can the team-execution consensus panel's cost safely shrink
  without weakening the gate — and what must the ledger substrate emit before anyone can know?

Every claim about current behavior below carries a file:line citation verified against this
repo at the time of writing. Where evidence does not exist, the gap is stated as a finding.

---

## 1. What the panel actually does today (verified surfaces)

The consensus review cycle is defined in
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`:

- **Fixed roster, convention-set size.** Three base reviewers are always spawned regardless of
  plan content (`reviewer-registry.md:14-23`); optional reviewers join by keyword match on the
  plan (`reviewer-registry.md:30-37`, `:44-47`). No reviewer carries independence or correlation
  metadata anywhere in the registry — the roster tables hold only name, color, focus, and
  trigger keywords.
- **Scoring.** Each reviewer scores 5 dimensions 0-10 and averages them
  (`review-criteria.md:3-5`); verdict is ACCEPT at >= 9.0 overall with no applicable dimension
  < 7.0 (`consensus-protocol.md:76-78`); the gate passes when all gated Claude reviewers reach
  >= 9.0 (`consensus-protocol.md:51`).
- **Iteration.** Maximum 3 review-revise cycles (`consensus-protocol.md:17`); only reviewers
  scoring < 9.0 are re-engaged in later cycles (`consensus-protocol.md:58-61`, worked example at
  `:137-149`).
- **Full-diff review, no size scaling.** Every reviewer receives the full diff, or an
  artifact-pointer to the full snapshot which it must dereference with "full read, no per-lens
  scoping" (`consensus-protocol.md:28`, `:213-217`). Review cost therefore grows with lot size
  on every diff regardless of risk concentration.
- **Existing cost reducers.** Two already exist: re-review scoping (only < 9.0 reviewers re-run,
  `consensus-protocol.md:137-149`) and the triage escape hatch (skip or minimize the panel for
  trivial single-config-file changes, `reviewer-registry.md:78-93`). Both are binary and
  convention-triggered, not measurement-triggered.
- **External advisory seat is out of scope for all of this.** It is always excluded from the
  consensus denominator and cannot move the gate (`consensus-protocol.md:112-131`,
  `reviewer-registry.md:51-59`), per `{#external-engines-never-gatekeepers}` (#283, grounding
  brief section 2, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:45`).
- **Panel size is already a tunable elsewhere in the fleet.** Saga's verify panels carry
  `n`/`pass_rule`/optional per-panel tier, bounded by `VERIFY_N_CAP = 7`
  (`plugins/saga/scripts/execution_spec.py:156`, dataclass at `:530-556`) — proof the fleet
  treats panel size as ordered, bounded policy, but nothing yet ties any panel size to a
  measured signal.

**Citation-drift finding (AC7 hygiene).** The issue body cites `consensus-protocol.md:142-157`
for the ephemeral score table and `:161-172` for the final prose summary, and
`execution_spec.py:114` for `VERIFY_N_CAP`. All three anchors have drifted: the per-cycle score
display now sits at `consensus-protocol.md:43-49` (cycle structure) and `:165-180` (Score
Display Format), the after-3-cycles prose summary at `:184-196`, and `VERIFY_N_CAP = 7` at
`execution_spec.py:156`. The claims themselves re-verified as true at the new anchors; this
document cites the verified locations.

## 2. What survives a run today: the measurement gap

This is the exploration's central finding. **No per-reviewer, per-iteration record survives a
consensus run in any machine-readable form.**

- The per-cycle score table is a *display* instruction — "Collect and display scores"
  (`consensus-protocol.md:43-49`) and "Display scores in this format after each review cycle"
  (`:165-180`). It lives in the session transcript and nowhere else.
- After 3 cycles, the protocol keeps only a final prose summary in the completion report
  (`consensus-protocol.md:184-196`).
- The fix-consolidation step *computes* findings overlap — "Group fix requests by file …
  Deduplicate identical fixes" (`consensus-protocol.md:153-161`) — and then discards it. The
  exact signal an independence metric needs (which reviewers raised the same finding) is
  produced transiently on every multi-reviewer-failure cycle and thrown away.
- The one cross-run number the fleet has ever had for what independent review is worth — the
  Claude+Codex syntheses converging 15/17 — was hand-reconciled once and never captured as a
  repeatable signal (grounding brief `:146-147`).

Consequently: reviewer agreement, lens correlation, defect-catch attribution, and diff-size
distribution are all currently **unmeasurable**. Everything in sections 5-7 below is therefore
*design for instrumentation*, not calibration from data — and every build recommendation in
section 9 is gated on the instrumentation existing first.

## 3. The two ledger substrates that merged, and what each is for

The telemetry substrate this document targets is real and merged — the fact schemas proposed in
section 4 are emittable today with one closed-set extension, not hypothetical:

**Run-fact ledger (`run_fact.v1`, #401)** — `plugins/saga/scripts/run_ledger.py`:

- One append-only, hash-chained, machine-local JSONL file per repo under the git common dir
  (`run_ledger.py:11-14`), shared across worktrees, never committed.
- Facts are leaf-produced (every fact carries its producing `subplot_id`,
  `run_ledger.py:20-22`, enforced at `:102-103`); the coordinator only reads, via
  derive-on-read views: `rollup` (`:304-319`), `reuse_ratio` (`:322-337`), and `last_n_prior`
  (`:340-354`) — the last of which is exactly the "last N runs averaged X" prior an elasticity
  policy would consume.
- The kind vocabulary is a closed set: `FACT_KINDS = {"spend", "cache", "engine", "delegation",
  "reconciliation"}` (`run_ledger.py:43`), and `build_fact` rejects unknown kinds (`:99-101`).
  **There is no panel/review fact kind today** — adding one is a one-line vocabulary extension
  plus a writer, but it is new instrumentation, not existing emission.
- Kind-specific payload fields are free-form (`build_fact(kind, *, subplot_id, at, **fields)`,
  `:91-107`): the ledger enforces the envelope and chain, not per-kind schemas. A typed-field
  discipline like `reconcile.append_reconciliation_fact`'s (`plugins/saga/scripts/reconcile.py:715-757`,
  which appends structured `reconciliation` facts with `source_finding_ids` and per-item status,
  guarded by a snapshot-validating atomic append) is the precedent a `panel_review` fact writer
  should copy. team-execution-adjacent flows already write `run_fact.v1` facts through this path
  (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:71-77`),
  so a consensus-step writer has an in-fleet precedent, not just a theory.

**Evidence ledger (#398)** — `plugins/saga/scripts/evidence_ledger.py`:

- Content-addressed, append-only, **committed** custody log per saga under
  `docs/evidence/<saga-id>/` (`evidence_ledger.py:12-14`), built so a later PASS can never
  silently overwrite an earlier FAIL (`:8-10`).
- Identity is `(check_id, reviewed_sha, attempt)` (`:15-17`); entries carry `producer`,
  `verdict`, content `hash`, and a free-form `payload` object (`:267-280`).
- The `latest()` reader surfaces FAIL-then-PASS transitions as `superseded_fail` rather than
  silent green (`:365-403`), and `close_verify` rejects producer-equals-verifier
  self-certification (`:509-531`).

**Division of labor this document assumes:** cross-run *calibration priors* (agreement rates,
overlap statistics, diff-size distribution) belong on the run-fact ledger — machine-local,
cheap, windowed reads via `last_n_prior`. Per-run *gate custody* (which panel, at what size, on
what SHA, with what verdict — and any shrink-miss found later) belongs on the evidence ledger —
committed, tamper-evident, FAIL-never-buried. Spot-check snap-back (section 7.2) needs exactly
the evidence ledger's supersession semantics. This split also honors the repo's standing bias:
derive-on-read over committed state (grounding brief `:109`), with the committed side reserved
for custody, not summaries.

`tier_efficacy.py` (#402 U4) is the consumption precedent: it joins spend facts against
evidence-ledger verdict history and renders **propose-diff-and-wait** downgrade proposals,
never auto-applied (`plugins/saga/scripts/tier_efficacy.py:1-14`). Any panel-policy change
derived from these ledgers should follow the same pattern.

## 4. Agreement ledger fields

The exact facts the consensus step (protocol Step B3c, `consensus-protocol.md:43-49`) would
append, and each field's current-substrate status. Proposed as one new run-fact kind,
`panel_review`, one fact **per reviewer per iteration**, plus one `panel_run` fact per cycle for
panel-level context.

**Legend for "status":** *envelope-ready* = the ledger machinery (append, chain, locking,
windowed reads) exists and accepts the field with no schema change beyond the `FACT_KINDS`
extension; *transient-today* = the value is already produced during the run and discarded;
*new* = nothing produces this value today.

| # | Field | Description | Current-substrate status |
|---|-------|-------------|--------------------------|
| 1 | `run_id` | team-execution run identifier; already minted for artifact-pointer locators (`consensus-protocol.md:219-221`) | transient-today; envelope-ready |
| 2 | `subplot_id` | producing leaf id, required by `run_ledger.build_fact` (`run_ledger.py:102-103`). team-execution runs launched outside a saga leaf have no subplot id — an identity-mapping decision a follow-up must make (finding, section 8) | envelope-required; mapping **new** |
| 3 | `reviewed_snapshot` | snapshot tree OID + epoch from the artifact-pointer block (`consensus-protocol.md:219-221`), or the diff's tree hash below threshold | transient-today |
| 4 | `iteration` | cycle number 1-3 (`consensus-protocol.md:17`) | transient-today |
| 5 | `reviewer_id` | agent name from the registry roster (`reviewer-registry.md:18-23`, `:30-37`) | transient-today |
| 6 | `score_overall` | the reviewer's overall average (`review-criteria.md:3-5`) | transient-today (displayed then dropped, `consensus-protocol.md:165-180`) |
| 7 | `dimension_scores` | map of applicable dimension → score | transient-today |
| 8 | `excluded_dimensions` | dimension → exclusion cause (`static-non-applicable`, `consensus-protocol.md:84-105`) | transient-today |
| 9 | `verdict` | ACCEPT / NEEDS_REVISION / BLOCKING / EXCLUDED (`consensus-protocol.md:70-78`) | transient-today |
| 10 | `finding_keys` | list of normalized finding keys `(path, hunk-anchor, dimension-category)` for each fix request the reviewer raised | **new** — fix requests today are free prose (`consensus-protocol.md:41`); the consolidation step groups them by file/section (`:153-161`) but no key discipline exists. `reconcile.py`'s `SourceFinding` id+digest scheme (`reconcile.py:722-739`) is the precedent to copy |
| 11 | `panel_composition` | full roster spawned this run + which optional reviewers triggered and on what keywords | transient-today |
| 12 | `panel_size_policy` | which rung of the (future) ordered panel ladder was used and why (full / reduced / minimum) — constant "full/convention" until elasticity exists | **new** |
| 13 | `diff_stats` | hunk count, insertions/deletions, files touched, above/below artifact-pointer threshold (`consensus-protocol.md:28`) | **new** — nothing records diff-size distribution today (finding, section 8) |
| 14 | `advisory_convergence` | the four convergence-bucket counts when the external seat participates (`consensus-protocol.md:120-128`) — report-only, never gate-bearing | transient-today (rendered into the verdict artifact as prose, not machine-readable) |

**Findings-overlap is derived, not stored.** Given field 10 across the panel, pairwise overlap
(section 5) is computed on read — consistent with the run-fact ledger's derive-on-read design
(`run_ledger.py:20-22`) and the repo's recurring rejection of committed summaries (grounding
brief `:109`). No `overlap` field is written.

**Evidence-ledger side (custody, committed):** one evidence entry per consensus gate decision —
`check_id = consensus:<run_id>`, `reviewed_sha` = the reviewed snapshot's commit SHA, `producer`
= the team-lead role, `verdict` = the gate outcome, `payload` = panel composition + per-reviewer
final scores + `panel_size_policy`. Everything fits the existing `write()` signature
(`evidence_ledger.py:213-231`) with zero schema change: **envelope-ready today**. Shrink-miss
records from spot-checks (section 7.2) append as later attempts on the same identity, so a
shrunk-panel PASS followed by a shadow-panel FAIL is surfaced by the existing `superseded_fail`
machinery (`evidence_ledger.py:365-403`) rather than buried.

**Summary for AC1:** the ledger *machinery* for every field above exists and merged; the
consensus protocol's score table already *produces* fields 1, 3-9, 11, 14 transiently and
discards them; fields 10, 12, 13 plus the `FACT_KINDS` extension and the Step B3c writer are the
new instrumentation. Nothing proposed here requires a substrate that does not exist in this
repo today.

## 5. Measured reviewer independence

**Operational definition.** Two lenses are independent on a class of diffs to the degree their
finding sets do not overlap when reviewing the same snapshot. Concretely, for reviewers A and B
on the same `(reviewed_snapshot, iteration)`:

```
J(A,B) = |K_A ∩ K_B| / |K_A ∪ K_B|
```

where `K_X` is reviewer X's set of normalized finding keys (field 10). Per-pair independence is
`1 − J(A,B)` averaged over a rolling window of runs (via the run-fact ledger; `last_n_prior` at
`run_ledger.py:340-354` is the read shape), reported **with its sample count** — a pair with
fewer than a floor number of co-occurrent runs (proposed: 10) has *no* independence score, only
"insufficient data". A verdict-level supplement (Cohen's kappa over ACCEPT/NEEDS_REVISION
agreement, correcting for base rates) catches pairs that raise different findings but always
vote together; both signals must be healthy before a pair is treated as independent.

**Worked example (illustrative numbers — no real data exists yet; that gap is finding 1 in
section 8).** The registry makes a correlated trio structurally available today:
`security-reviewer` is a base reviewer whose focus explicitly includes PII
(`reviewer-registry.md:22`), and `privacy-reviewer` is keyword-triggered on PII/GDPR
(`reviewer-registry.md:36`) — a plan mentioning PII fields seats both. Suppose a 12-run window
of `panel_review` facts yields:

| Panel | Pairwise J | Effective votes n_eff |
|-------|-----------|----------------------|
| Correlated: security + privacy + infra | J(sec,priv)=0.58, J(sec,infra)=0.12, J(priv,infra)=0.09 | 1 + (1−0.58) + (1−0.12) = **2.30** |
| Diverse: devils-advocate + security + architecture (the base roster, `reviewer-registry.md:18-23`) | J(da,sec)=0.08, J(da,arch)=0.06, J(sec,arch)=0.11 | 1 + (1−0.08) + (1−0.11) = **2.81** |

with `n_eff = 1 + Σ_i (1 − max_{j<i} J(i,j))` (greedy discount: each added lens counts only for
what it does not share with an already-seated lens). Both panels present three ACCEPT votes to
the gate (`consensus-protocol.md:51`), but the correlated panel carries roughly 2.3 independent
opinions while scoring as 3 — the "one opinion counted three times" failure `T5-F3-6` names. A
panel-selection guard would warn (not block) when a proposed panel's `n_eff` falls below a
floor, and suggest the swap that raises it.

**What `reviewer-registry.md` would need to carry:** a per-lens-pair independence table —
`{pair, J_window, sample_runs, window_bounds, updated_at}`. Critically, this table must be
**generated from the ledger by tooling, never hand-edited**: the fleet's own journal records
hand-copied contract tables drifting from their source of truth as a top-ranked recurring
failure (grounding brief `:61-64`, `:67-68`). A hand-maintained independence table would be
born stale.

## 6. Acceptance-sampling review (risk-stratified hunk sampling)

Applies only to the full-diff review obligation (`consensus-protocol.md:28`, `:213-217`); the
model is per-reviewer and Claude-internal.

**Stratification rule — two strata, and stratum 1 is never sampled:**

1. **Always in-sample (100% review, unconditionally):** hunks touching security/auth surfaces —
   auth, secrets, permissions, PII, the same vocabulary the triage escape hatch already treats
   as un-skippable (`reviewer-registry.md:80-85`) and the escalation rule already treats as
   blocking (`consensus-protocol.md:262-263`); public-API/contract surfaces (exported
   signatures, schemas, release surfaces such as `plugin.json`/`marketplace.json`); CI and
   workflow definitions; and any file the plan names as intent-central. **Security, auth, and
   public-API hunks are always in-sample under this model — sampling can never exclude them.**
2. **AQL-sampled stratum:** every remaining hunk, sampled by lot size (lot = count of stratum-2
   hunks), acceptance number **Ac = 0**:

| Lot (stratum-2 hunks) | Sample size |
|----------------------|-------------|
| ≤ 25 | all (no sampling — overhead exceeds savings) |
| 26–90 | 20 |
| 91–280 | 32 |
| > 280 | 50 |

Starting parameters adapted from the ISO 2859-1 / MIL-STD-105E general-inspection shape the
`T5-F5-7` basis names (sample size and acceptance number as functions of lot size and
Acceptable Quality Level, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`); the
issue's executor profile sanctions a cheap external second opinion on the exact AQL constants
before implementation — these numbers are a design anchor, not a calibrated result.

**Escalation rule (one sentence):** if any sampled stratum-2 hunk yields a finding at
NEEDS-REVISION severity or above (any dimension it touches scoring < 9.0 per
`consensus-protocol.md:70-78`), the acceptance number Ac = 0 is exceeded and the reviewer
escalates to full review of the entire diff within the same iteration — sampling is only ever a
fast path *into* full review, never a cap on it.

Cross-run ledger history (sampling-escape rate, section 7.3) drives tightened/normal switching:
any observed escape tightens the next runs to full review for that plan type until a clean
streak restores sampling.

## 7. Miscalibration risk per mechanism, and its own detection signal

Each mechanism must ship carrying the instrument that detects the specific way it degrades the
gate. Generic test coverage does not qualify; the signals below are mechanism-specific and
ledger-backed.

### 7.1 Measured-independence panel-selection guards

**Risk:** the metric itself miscalibrates — key normalization splits the same defect into
different keys (same flaw, different file:line phrasing), deflating J and scoring correlated
lenses as independent; or thin samples produce confident-looking noise. The guard would then
*bless* the exact correlated panel it exists to catch, with a number attached — worse than
today's honest ignorance.

**Detection signal — duplicate-lens calibration probe.** Periodically (piggybacked on runs that
happen anyway — no standing ceremony, see section 9 constraints) seat a known-maximally-
correlated pair: the same lens prompt twice under distinct reviewer ids, or the structurally
overlapping security+privacy pair on a PII-heavy diff (`reviewer-registry.md:22`, `:36`). If
measured J for a same-lens-twice probe falls below a floor (proposed: 0.5), key normalization
is broken; the ledger's independence view is quarantined (all pairs report "uncalibrated") until
the probe passes. The probe result is itself a `panel_review` fact, so the quarantine state is
derivable on read. The sample-count floor (section 5) covers the thin-sample half of the risk.

### 7.2 Consensus elasticity (agreement-driven shrink with spot-check snap-back)

**Risk:** a shrunk panel misses a defect the full panel would have caught — precisely the
defect class the panel is praised for catching when green suites missed it (grounding brief
`:65-66`). The subtle form: agreement history is survivorship-biased. High measured agreement
may mean the window's diffs were easy, not that the dropped lens is redundant; the panel then
stays shrunk exactly until the first hard diff arrives, which is the diff that needed the full
panel.

**Detection signal — shadow-panel shrink-miss rate.** On a sampled fraction of shrunk-panel
runs (proposed: 1 in 5), run the dropped reviewers as a non-gating shadow panel. Any finding
raised by a shadow reviewer and missed by the seated panel is a **shrink-miss**: appended as a
new attempt on the consensus evidence-ledger identity, so a shrunk PASS followed by a shadow
FAIL surfaces through the existing `superseded_fail` supersession reader
(`evidence_ledger.py:365-403`) and can never be silently buried (`evidence_ledger.py:8-10`).
Snap-back rule: one shrink-miss at BLOCKING severity (< 7.0, `consensus-protocol.md:70-78`), or
two at NEEDS-REVISION within the window, snaps that lens/plan-type combination back to the full
panel and resets its agreement window to zero. Survivorship bias is addressed by stratifying
the agreement prior by diff class (the `diff_stats` fact, section 4 field 13): agreement
measured on small diffs never licenses shrinking on large ones.

### 7.3 Acceptance-sampling review

**Risk:** the one real defect sits in an out-of-sample hunk — either by unlucky draw (the
irreducible sampling risk Ac = 0 bounds but cannot eliminate) or, worse, by **stratification
leak**: the risk classifier mislabels a security-relevant hunk as stratum 2 and sampling skips
it, silently violating the always-in-sample invariant while the gate still reports full-rigor
review.

**Detection signal — out-of-sample escape rate with a stratification-leak alarm.** Every
sampled review appends its sample manifest (which hunks were in/out) to the ledger. When any
later gate — validator, CI, `/qa`, or a post-merge defect issue — attributes a defect to a
hunk, the manifest answers whether that hunk was sampled out. An out-of-sample escape increments
the escape-rate signal and tightens inspection (section 6); an escape in a hunk that *should*
have been stratum 1 (security/auth/public-API) is a stratification leak and is terminal for the
mechanism (kill criterion, section 9). Additionally, a periodic full-review audit run compares
its findings against what the sampling plan would have inspected, estimating the false-accept
rate without waiting for production escapes.

## 8. Evidence gaps — findings, not footnotes

1. **Zero panel telemetry exists.** No per-reviewer, per-iteration record survives any
   consensus run (`consensus-protocol.md:43-49`, `:165-180`, `:184-196` are display/prose only).
   Every number in section 5's worked example is illustrative. Nothing can be calibrated until
   the `panel_review` fact ships and accumulates a window.
2. **The findings-overlap signal is computed and discarded today** by fix consolidation
   (`consensus-protocol.md:153-161`) — the cheapest instrumentation win in this document.
3. **No diff-size distribution.** The artifact-pointer threshold exists
   (`consensus-protocol.md:28`) but nothing records how often it trips or the hunk-count
   distribution of reviewed diffs. Acceptance sampling's addressable spend is therefore
   **unknown**; the grounding brief's 350-450k-token singleton (`:145-146`) is a recon fan-out
   number, not a review-spend number, and does not substitute.
4. **The 15/17 convergence prior is a single hand measurement** (grounding brief `:146-147`) —
   motivating, but not a calibration baseline.
5. **Identity mapping is unresolved:** `run_ledger.build_fact` requires a `subplot_id`
   (`run_ledger.py:102-103`); team-execution runs launched outside a saga leaf have none. A
   follow-up must decide the mapping (synthetic subplot id from `run_id`, or a saga-context
   requirement) before the writer ships.
6. **Issue citation drift** (section 1): the issue's `consensus-protocol.md:142-157`/`:161-172`
   and `execution_spec.py:114` anchors no longer point at the cited content; verified locations
   are `:43-49`/`:165-180`/`:184-196` and `:156` respectively.

## 9. Build-or-park recommendation, in priority order

**Gated/advisory boundary statement (binding).** None of the three recommendations below
touches the gated/advisory boundary. All three mechanisms are Claude-internal panel
composition, sizing, and sampling. The external advisory seat remains always-excluded from the
consensus denominator exactly as specified (`consensus-protocol.md:112-131`,
`reviewer-registry.md:51-59`), and no mechanism here creates a lever by which an external
engine's score, convergence bucket, or availability can move the `>= 9.0` pass threshold or the
`< 7.0` blocking rule — consistent with `{#external-engines-never-gatekeepers}` (#283).

**Cross-cutting constraints honored by all three:** panel sizes and sampling levels are
ordered, bounded ladders (full → reduced → minimum; normal → tightened), never ad hoc numbers,
per `{#tier-vocab-ordering}`; any default-policy change derived from ledger evidence is
propose-diff-and-wait, following `tier_efficacy.py`'s precedent (`tier_efficacy.py:9-14`),
never auto-applied; and **no standing measurement ceremony is created** — every signal above is
appended by runs that happen anyway and derived on read, honoring the issue's explicit non-goal
and the fleet's prior rejection of standing ceremonies for solo-operator tooling.

### Priority 1 — Measured-independence panel-selection guards (`T5-F3-6`)

**Recommendation: build** — first, and in two stages: (1a) the agreement-ledger
instrumentation itself (the `panel_review`/`panel_run` fact kinds, the Step B3c writer, keyed
findings, the consensus evidence-ledger entry — section 4), then (1b) the advisory selection
guard once the sample floor is met. Rationale for first place: it is purely additive (no review
rigor is removed at any point), it is the prerequisite substrate for both other mechanisms, and
its riskiest component (key normalization) is testable cheaply via the duplicate-lens probe
before any decision depends on it. The guard itself stays advisory (warn + suggest swap), so a
miscalibrated metric cannot weaken the gate — only fail to strengthen it.

**Kill criterion:** park the *guard* (keep the ledger) if, after 15 recorded panel runs, the
pairwise-overlap distribution is statistically flat — no lens pair separable from the panel-wide
noise floor (all pairwise J within ±0.10 of the mean) — or if the duplicate-lens calibration
probe cannot be brought to J ≥ 0.5, meaning finding-key normalization is not achievable and
every independence number would be fiction. The ledger facts remain valuable for elasticity and
sampling evaluation even if the guard is parked.

### Priority 2 — Consensus elasticity (`H-F6-10`)

**Recommendation: build, conditionally** — gated on Priority 1's ledger showing, for a specific
lens/plan-type combination, sustained high agreement (proposed: ≥ 10 runs with pairwise J above
a redundancy threshold and kappa-corrected verdict agreement, stratified by diff class). Do not
build concurrently with Priority 1; elasticity consumes the agreement prior and is unsafe
without it. Ship the spot-check snap-back (section 7.2) in the same change as the shrink — a
shrink without its shadow-panel instrument is the "quietly erode the gate" failure by
construction. Honest pre-mortem: the protocol already has two cost reducers (re-review scoping,
`consensus-protocol.md:137-149`; triage escape hatch, `reviewer-registry.md:78-93`), and the
base panel is only three reviewers — the marginal savings may prove small once measured.

**Kill criteria:** park (or un-build) if any single shadow-panel shrink-miss at BLOCKING
severity is recorded; or if the ledger shows measured agreement is high only on small/easy
diffs (agreement does not survive stratification by `diff_stats` class — the survivorship-bias
tell); or if projected net savings are negative or marginal — shadow-panel spot-check cost
consuming ≥ 50% of the tokens the shrink saves over the measurement window — in which case
elasticity is ceremony with extra steps and the fixed panel is cheaper *and* safer.

### Priority 3 — Acceptance-sampling review (`T5-F5-7`)

**Recommendation: park** — until the ledger produces the missing denominator. Its addressable
spend is currently unknown (finding 3, section 8): nothing records how often reviewed diffs are
large enough for sampling to beat the ≤ 25-hunk full-review floor. Parking is cheap because
Priority 1's `diff_stats` fact accrues the needed evidence passively. Revisit when a measured
window exists; build only if it shows meaningful frequency of large lots (proposed revisit
threshold: ≥ 20% of consensus runs with stratum-2 lots above 90 hunks over a 20-run window),
and then only with the stratification rule and escalation sentence of section 6 verbatim
(security/auth/public-API always in-sample; Ac = 0), plus the intake-sanctioned external second
opinion on the AQL constants before implementation.

**Kill criteria:** park permanently if the measured diff-size distribution stays below the
revisit threshold (the mechanism would optimize a cost that does not exist); kill outright —
even mid-pilot, even if feasible — on a single observed stratification leak (a security/auth/
public-API hunk sampled out of review, section 7.3), because the invariant that makes sampling
safe is exactly the one a leak proves unenforced.

## 10. What follow-up implementation issues would need to cover

For the two build recommendations (Priority 1 now; Priority 2 when its gate condition is met):

- **Priority 1 issue:** `FACT_KINDS` extension + `panel_review`/`panel_run` fact writer invoked
  at consensus Step B3c; finding-key normalization spec (copying `reconcile.py:722-739`'s
  id+digest discipline); the consensus evidence-ledger entry; the `subplot_id` identity mapping
  (finding 5); duplicate-lens calibration probe; the generated (never hand-edited) independence
  table for `reviewer-registry.md`; derive-on-read views over the new facts. Release surfaces:
  `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/team-execution/CHANGELOG.md`, drift-guard tests — and the saga plugin's same
  surfaces if `run_ledger.py`/`reconcile.py` change.
- **Priority 2 issue (later):** the ordered panel ladder (full → reduced → minimum) in
  `consensus-protocol.md`; the agreement-prior read (thresholds, window, diff-class
  stratification); shadow-panel spot-check dispatch + shrink-miss evidence entries; snap-back
  rule; propose-diff-and-wait for any default change. Same team-execution release surfaces.
- **Priority 3:** no issue until the revisit threshold fires; the parked design is section 6 of
  this document.
