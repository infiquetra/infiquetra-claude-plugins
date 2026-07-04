# Plugin-Fleet Baseline Metrics (frozen 2026-07-04)

Committed "before" snapshot for the `improve-claude-plugins` execution program, per issue
#461. Freezes 8 recurring, independently-corroborated fleet pain metrics before any
wave-1/wave-2 fix lands, so a later "did the fleet get better" retro has an authoritative
number to diff against instead of an assertion. Documentation-only — this does not fix any
of the 8 underlying pain points.

Each metric below carries a one-line definition, a `file:line` evidence citation into the
committed grounding brief, and an executable recipe an agent can re-run cold to re-derive or
re-confirm the number.

### 1. Manual ship ceremony rate

**Definition:** repos where the commit→PR→merge→checkout-main→pull→cleanup ceremony is
still performed with raw `git`/`gh` in session after session, even where saga or
mission-control tooling is installed.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119`

**Frozen number:** 8 repos.

```bash
grep -n "Manual ship ceremony" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

### 2. Gate-primitive unreliability rate

**Definition:** repos where `AskUserQuestion` silently auto-proceeds on timeout (treated as
consent), fires before an answer is captured, or errors outright, forcing agents to fall
back to plain-text questions.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122`

**Frozen number:** 6 repos.

```bash
grep -n "Gate-primitive unreliability" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

### 3. mission-control board/field drift rate

**Definition:** repos exhibiting nonexistent-field assumptions, hardcoded aliases,
item-list pagination silently truncating results, or racing create/board-add/field-set
calls.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:126`

**Frozen number:** 4 repos; underlying pagination-truncation claim is "200 of 375" items.

```bash
grep -n "board/field drift" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

Secondary liveness check (confirms the query mechanism the truncation claim is about is
still reachable today — this is **not** a re-derivation of the historical 375-item
snapshot, only a check that a live total-count query works):

```bash
gh api graphql -f query='{ organization(login: "infiquetra") { projectV2(number: 3) { title, items(first: 1) { totalCount } } } }'
```

### 4. Rate-limit fan-out kill rate

**Definition:** fan-out runs where a meaningful fraction of dispatched agents failed
outright due to rate limiting, with no concurrency-governance mechanism in place to shed
load.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:129`

**Frozen number:** 3 repos; underlying incident is "6 of 7 agents failed on rate-limiting."

```bash
grep -n "Rate-limit fan-out kills" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

### 5. Codex sessions with zero mining substrate

**Definition:** codex sessions that fell inside the ideation program's observation window
but had no cross-repo learning-mining substrate applied to them at all — a dark gap in the
fleet's promote-loop coverage.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:115`

**Frozen number:** 219 sessions.

```bash
grep -n "no mining substrate" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

### 6. Promote-ledger firings

**Definition:** count of learnings that have ever been promoted through the fleet's
cross-repo promote-ledger mechanism — the loop that is supposed to turn a
≥3-repo-corroborated learning into a durable, shared decision.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:72`

**Frozen number:** 0 firings ("0 learnings ever promoted; no genuine ≥3-repo transcendent
cluster").

```bash
grep -n "Promote ledger" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

### 7. Read-only recon fan-out token cost

**Definition:** token cost observed for a read-only reconnaissance fan-out (a broad,
parallel, no-write search/survey operation) completing in under 20 minutes.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:145`

**Frozen number:** 350–450k tokens in <20 min.

```bash
grep -n "350–450k tokens" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

### 8. Silent no-op / dead-wiring incidents

**Definition:** count of distinct learnings documenting a delegation or integration path
that silently no-ops or falls back (e.g. a silent Claude-fallback, a dead-wired adapter) —
appearing to run and persist when it did neither.

**Evidence:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:101`

**Frozen number:** 5+ learnings.

```bash
grep -n "Silent no-ops in delegation" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

## Re-run this baseline on the next `/retro`

Before any future `/retro` claims the fleet improved, re-run all 8 recipes above and diff
the output against the frozen numbers in this document. A claim of improvement without that
diff is exactly the "stale claim asserted as fact" failure mode this document exists to
prevent (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §6 item 2).
