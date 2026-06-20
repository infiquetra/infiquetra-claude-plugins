---
name: promote
description: Promote the select few cross-repo "transcendent" learnings into infiquetra-context-library's engineering journal as distilled, pull-only org standards. A manual, gated, agent-judged workspace pass — it enumerates every repo journal (mirroring /ideate's cross-repo grounding), reads the declared **Transcendent.** markers plus the legacy **Generalizable rule.** lines, excludes context-library (self-feed guard), clusters the same lesson across >=2 repos by judgment, distills Rule + Mechanism, and upserts ONE entry per lesson behind a propose-diff-and-wait gate keyed on a drift-stable source-key ledger. READ-ONLY on the SDLC; writes ONLY to context-library; never writes back to source repos. Triggers on "promote learnings", "run the transcendent-learnings pass", "globalize this lesson", "promote".
---

# Promote

`/promote` answers **"Which repo-local lessons have earned org-wide status, and lift those few."**
It is the workspace tier of the engineering journal: a **cross-repo journal feeder**, not a sixth
durable surface. It promotes the *select few* learnings that genuinely cross repositories into
`infiquetra-context-library`'s `LEARNINGS.md` as distilled, self-contained, pull-only standards. The
~785 per-repo learnings stay where they are, untouched and searchable; promotion **copies, never moves**.

The single source of truth for every format this skill reads or writes — the `**Transcendent.**`
marker, the drift-stable source key, the legacy-rule parser, the promoted-entry template, and the
idempotency ledger — is the frozen contract `references/promotion-contract.md`. This skill **quotes**
that contract; it never restates the recipes. If a format must change, it changes there first.

## Position in the lifecycle

`/promote` sits one tier *above* the per-repo lifecycle, fed by two converging feeders:

- **Declare** — `/retro` (or a human) marks a transcendent learning in its own repo with
  `**Transcendent.**`, a local gated edit (see `../retro/references/retro-passes.md`, Pass 5). No
  cross-repo write happens at mark time; the marker waits in place.
- **Recurrence net** — this pass enumerates every repo journal and clusters the same lesson recurring
  across repos, catching the transcendent lessons no one thought to declare.

Both feeders funnel through this one gated pass into one destination. From context-library, the
existing journal-to-surface promotion rules still apply — `/promote` extends that model, it does not
fork it (`infiquetra-sdlc/docs/process/engineering-journal.md`).

## Core principles

1. **Sparing, not a harvest.** The marker means "transcends repos," not "generalized from an incident."
   The default is *not* to promote. A bulk copy of every `**Generalizable rule.**` line is the
   explicitly rejected anti-pattern.
2. **Gated, always.** Every context-library write is **propose-diff-and-wait**: show the diff, wait for
   explicit approval. Nothing writes silently (contract §5, KTD6).
3. **Idempotent and boring to re-run.** Promotion is an upsert keyed on the drift-stable source-key
   ledger each entry carries (contract §2, §5). Re-running finds the keys already present and proposes
   nothing; a new origin repo for a known lesson adds one backlink, not a new entry.
4. **One auditable write surface.** The pass writes ONLY to `infiquetra-context-library`'s journal —
   never back to a source repo — and is **READ-ONLY on the SDLC** (no issue, board, or saga mutation).
5. **Judgment, not vectors.** Clustering "same lesson across repos" is by agent judgment over the
   in-window candidate pool (KTD4). No embeddings, no RAG, no index to drift.

## Interaction method

Use `AskUserQuestion` for the per-cluster apply / skip / modify gate and the threshold/scope choices.
Call `ToolSearch` with `select:AskUserQuestion` first if its schema is not loaded. In a channel session
(`redis-channel` active) `AskUserQuestion` cannot be called — inline the choices in the reply text per
the canonical convention in `../brainstorm/SKILL.md`. Use repo-relative paths in everything you write;
repo-qualify any cross-repo reference (e.g. `infiquetra-home-lab/docs/...`).

---

## Phase 0 — Ground and scope

Establish what the run covers before scanning anything.

- **Workspace root.** The per-repo clones live under `~/workspace/infiquetra/` (mirroring `/ideate`'s
  discovery). Confirm it exists; if the operator names a different root or a subset of repos, honor it.
- **Threshold.** A recurrence cluster is nominated at **>= 2 distinct repos** by default (configurable
  via the scan's `--threshold`). Surface the default; let the operator widen it.
- **Destination present.** Confirm `infiquetra-context-library` is cloned locally (the write target and
  the ledger source). If absent, stop and say so — there is nothing to upsert into.

## Phase 1 — Discover and scan (the deterministic backbone)

Run the mechanical backbone with `scripts/promote_scan.py` — it enumerates
`*/docs/engineering-journal/LEARNINGS.md` under the workspace root, parses the `**Transcendent.**`
markers and the legacy `**Generalizable rule.**` variants, computes the drift-stable source key for
each, reads context-library's `<!-- promote-keys: ... -->` ledger, drops already-promoted candidates,
excludes context-library from the pool, and groups exact-recurrence clusters:

```bash
python3 plugins/saga/scripts/promote_scan.py scan --workspace-root ~/workspace/infiquetra --json
```

The JSON payload carries `candidates` (every keyed, not-yet-promoted rule), `marked` (the declared
`**Transcendent.**` subset), and `recurrence_clusters` (same normalized rule in >= threshold repos —
the deterministic floor). If the candidate pool is large enough to strain one context window, the
script's `--threshold` and per-repo grain let you chunk the judgment; `log` when the pool is unusually
large (the revisit-when condition recorded in the sdlc DECISIONS entry).

**Self-feed guard (two layers, both in the script).** Context-library is excluded from the candidate
pool entirely; independently, any entry carrying a `promote-keys` comment is skipped — a promoted entry
can never be re-detected as a source, by construction. Do not weaken either layer.

## Phase 2 — Cluster by judgment

The script clusters *exact* recurrences (identical normalized wording). Your job is the judgment layer
the script cannot do: fold **near-identical** wordings of the same lesson into one cluster, and split a
coincidental hash-neighbor that is actually a different lesson. For each candidate and exact cluster,
apply the transcendence test — *would this rule still be true and useful in a repo of a different stack
or domain?* The two nomination sources:

- **Declared** (`marked`) — a human or `/retro` already vouched for it; treat as a strong nominee even
  at a single repo.
- **Recurrence** (`recurrence_clusters` + your near-duplicate folding) — the same lesson surfacing in
  >= 2 repos is the evidence that it transcends, even if no one declared it.

Each nominated cluster keeps **one source key per origin** (contract §2) — near-identical wordings each
retain their own key; they cluster by judgment but stay distinct in the ledger.

## Phase 3 — Distill and propose (the gated upsert)

For each approved cluster, distill into the contract §4 promoted-entry template — **only Rule +
Mechanism land** (the incident-specific Context / Evidence / Fix stay in the source repo):

- Compute the destination upsert: match an existing context-library entry whose `promote-keys` set
  overlaps this cluster; otherwise create a new entry (newest-first).
- For a match, **add** the new origins' `**Sources.**` backlinks and `promote-keys` — never a second
  entry for the same lesson (contract §5 upsert, AE3).
- Render the proposed change as a **diff** and gate it: `AskUserQuestion` apply / skip / modify (channel
  session: inline the choice). This is **propose-diff-and-wait** — wait for explicit approval.

`scripts/promote_scan.py` provides the upsert/ledger helpers (key computation, ledger membership, the
entry render) so the diff you propose is mechanically consistent with the contract.

## Phase 4 — Write (context-library only) under approval

On approval, write the upserted entry into
`infiquetra-context-library/docs/engineering-journal/LEARNINGS.md` and nothing else:

- **Write-surface guard.** Refuse any path outside context-library's journal. The pass never writes back
  to a source repo (R10) and never touches the SDLC (no issue/board/saga mutation).
- **Idempotency.** The entry carries its own `promote-keys` receipt, so the next run sees the keys and
  proposes nothing. A later third repo for the same lesson is an upsert (one new backlink, one new key).
- **Recall is pull-only.** Promoted entries are grepped or read on demand; nothing about this layer
  auto-loads into a session (R15).

After the writes, summarize what was promoted (by destination entry) and what was skipped, and stop.
`/promote` is terminal and SDLC READ-ONLY — it does not route into the saga or open issues.

---

## Reference files

- `references/promotion-contract.md` — **the frozen single source of truth.** The `**Transcendent.**`
  marker (§1), the drift-stable source-key recipe + golden vectors (§2), the legacy `**Generalizable
  rule.**` parser variants (§3), the promoted-entry template with `**Sources.**` + `promote-keys` (§4),
  and the idempotency / self-feed contract (§5). Everything here quotes it; nothing restates it.
- `../retro/references/retro-passes.md` — Pass 5's transcendence-marking sweep (the declare feeder that
  writes the marker this pass collects).
- `scripts/promote_scan.py` — the deterministic backbone (enumerate, parse, key, ledger-filter,
  exact-recurrence grouping) and the U4 upsert/ledger helpers.
