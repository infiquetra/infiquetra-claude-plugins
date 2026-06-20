# Promotion Data Contract

> Status: **frozen** (U1, approved 2026-06-20) — the formats the transcendent-learnings layer depends on.
> `promote_scan.py` (U3), the `/retro` transcendence-marking sweep (U2), and the gated upsert (U4)
> all quote **this** file — there is no second definition anywhere. If a format must change, it
> changes here first, then its consumers and their tests.

Part of the saga `promote` skill. Design package: `docs/plans/2026-06-20-global-transcendent-learnings-plan.md`
and `docs/brainstorms/2026-06-20-global-transcendent-learnings-requirements.md` (this repo).

The layer promotes the *select few* learnings that genuinely cross repositories into
`infiquetra-context-library`'s engineering journal as distilled, pull-only org standards. Two feeders
find them — a **declared** marker (this contract, §1) and a **recurrence net** over existing
`**Generalizable rule.**` lines (§3) — and a single gated, idempotent upsert lands them (§4–§5).

---

## 1. The transcendence marker (source repos)

The marker elevates one `**Generalizable rule.**` to "this crosses repositories." It is written into
the **source** repo's `docs/engineering-journal/LEARNINGS.md`, on its own line immediately below the
rule it elevates:

    **Generalizable rule.** <the rule, inline as today>
    **Transcendent.** <optional one-line reason it holds in a repo of a different stack or domain>

- **One canonical form only:** `**Transcendent.**` at line start — bold, capital `T`, trailing period.
  We *own* this marker (it is new), so we mandate a single form rather than tolerate variants (the
  variant-tolerance burden in §3 applies only to the legacy `**Generalizable rule.**` marker we do
  not control).
- **Detection anchor:** `^\*\*Transcendent\b` (line start, no blockquote or list prefix).
- **Placement:** the line directly after the entry's `**Generalizable rule.**` line, so reader and
  scanner both bind the marker to its rule by adjacency.
- **Writers:** the `/retro` marking sweep (U2, R2) and humans (R3). Both write only this canonical
  form, and both propose it as a Tier-2 **propose-diff-and-wait** edit (it modifies an existing
  entry — KTD6).
- **No cross-repo write at mark time (R4, KTD7):** the marker sits in its own repo until the next
  `promote` run collects it. `/retro` stays single-repo.

## 2. Source key — the drift-stable identity

Every source occurrence of a lesson has a key `<repo>:<hash>`, computed identically by U2, U3, and
U4. There is exactly one recipe:

    rule_text  := the marker line's content AFTER the label
                  (the inline lesson; 778 of 785 corpus markers carry it inline)
    normalized := rule_text, transformed in order:
        1. strip a leading blockquote `>`, list bullet `-`/`*`, and surrounding whitespace
        2. strip the rule label in any legacy form (see §3): e.g. `**Generalizable rule.**`,
           `**Generalizable rule:**`, `**Generalizable rules.**`, `**Generalizable rule (...)**`
        3. strip markdown emphasis characters: `*`  `` ` ``  `_`   (cosmetic re-bolding is not a new identity)
        4. lowercase
        5. collapse every whitespace run to a single space; trim both ends
        6. strip trailing punctuation: `.`  `;`  `:`  `,`

    hash := sha256(normalized.encode("utf-8")).hexdigest()[:12]
    key  := f"{origin_repo_dirname}:{hash}"

- `origin_repo_dirname` is the source repo's directory name under the workspace root
  (e.g. `infiquetra-home-lab`) — not a path, not a remote URL.
- **Content-addressed (R12):** if the source line *moves*, the key is unchanged. This — not the
  `repo/path:line` backlink (§4, which may drift, R9) — is the idempotency identity.
- **Per-occurrence:** the same lesson in two repos hashes its own wording in each, yielding two
  distinct keys (different repo prefix) → two backlinks on one promoted entry (R13). Near-identical
  wordings still cluster by judgment (U3, KTD4) while each keeps its own key.

**Golden vectors** (oracle for U3's key tests — these are real `sha256[:12]` values):

    normalized: a verification gate that is named but not executed is not a gate
    hash:       87c4c366deb7

    normalized: a monitoring check that is configured but never scraped is not monitoring
    hash:       821928016ab6

A line-number shift in the source must leave the hash byte-for-byte identical (the drift proof).

## 3. Legacy `**Generalizable rule.**` parsing (recurrence-net feeder)

The recurrence net (U3, R5) reads `**Generalizable rule.**` lines across **all** source repos. The
corpus has real surface variation. Observed forms (this session's scan of the workspace top-level
journals — the table enumerates the **forms** the parser must tolerate; counts are an anchor for
U3's coverage test, not a frozen census, and the workspace-wide total is ~785 lines / ~30 repos):

    539  **Generalizable rule.**         canonical
     28  > **Generalizable rule.**       blockquote-prefixed
     15  - **Generalizable rule:**       list bullet + colon
      6  **Generalizable rule:**         colon-terminated
      5  **Generalizable rule**          no trailing period
      4  **Generalizable rules.**        plural
      *  **Generalizable rule (...)**    parenthetical qualifier

**Match pattern** (one regex, anchored on line start + bold-wrapping):

    ^\s*>?\s*[-*]?\s*\*\*Generalizable rules?(?:\s*\([^)]*\))?[.:]?\*\*

- **MUST match:** every form above (canonical / blockquote / list / colon / no-period / plural /
  parenthetical).
- **MUST NOT match:** lowercase mid-sentence prose such as "the generalizable rule is" or
  "and generalizable rules." — these lack the line-start bold-wrapping and are not markers.

## 4. The promoted entry (context-library)

A promotion writes a distilled, self-contained entry into
`infiquetra-context-library/docs/engineering-journal/LEARNINGS.md` (newest-first, like every other
entry). It reuses context-library's existing bold-subheader grammar:

    ## YYYY-MM-DD

    ### <the transcendent rule, stated as a one-line title>

    **Author.** promote (saga)
    **Generalizable rule.** <the rule — self-contained, readable without opening the source repo>
    **Mechanism.** <the why — the principle, stripped of incident-specific detail>
    **Sources.** <repo>/<path>:<line>; <repo>/<path>:<line>
    <!-- promote-keys: <repo>:<hash>; <repo>:<hash> -->

Field semantics:

- `**Author.**` = `promote (saga)` — provenance: a derived/promoted entry, not hand-authored.
- `**Generalizable rule.**` + `**Mechanism.**` — reuse context-library's existing field labels, so a
  promoted entry reads like a (distilled) native one. **Only Rule + Mechanism land (R8);** the
  incident-specific Context / Evidence / Fix stay in the source repo — promotion **copies, never
  moves** (R10), and the ~785 source learnings are left untouched (R16).
- `**Sources.**` — **new convention (KTD3).** One human-navigable `repo/path:line` backlink per
  origin repo, separated by `; `. Provenance pointers only — they **may drift** as source files grow
  (R9); they are *not* the dedup key.
- `<!-- promote-keys: ... -->` — the **drift-stable idempotency keys** (§2), one per origin,
  `; `-separated. Invisible when rendered; visible in the raw file and `git` diff. This is the dedup
  ledger (§5) — the entry carries its own receipt, so there is no separate ledger file to drift out
  of sync with the entries.

## 5. Idempotency and self-feed protection

**Every context-library write is gated (R11, KTD6):** `promote` proposes a diff and waits for explicit
human approval before writing. Nothing below writes silently.

**Idempotency (R12 — "re-running is safe and boring"):**

- On each run, `promote` greps every `<!-- promote-keys: ... -->` line in context-library's journal and
  builds the set of already-promoted keys. (No separate ledger file: each entry carries its own keys,
  so ledger and entries cannot disagree.)
- A candidate source occurrence is **skipped** when its key (§2) is already in that set.
- A recurrence cluster with a **new** origin repo for an already-promoted lesson is an **upsert**
  (R13, AE3): the matching entry's `**Sources.**` line gains a backlink and its `promote-keys` comment
  gains the new key — **no new entry is created**.

**Self-feed protection (R14, AE4) — two independent layers:**

1. **Primary:** `promote_scan.py` excludes `infiquetra-context-library`'s own journal from the
   candidate pool entirely.
2. **Backstop (structural):** the scanner skips any entry that carries a `promote-keys` comment. Even
   if layer 1 regressed, a promoted entry can never be re-detected as a recurring source — by
   construction, not by policy. This is *why* promoted entries keep the familiar
   `**Generalizable rule.**` label safely: the skip keys off the comment, not the label.

**Recall (R15):** promoted entries are consumed pull-only — grepped or read on demand. Nothing about
this layer auto-loads into a session.

## 6. Worked example (end to end)

*Illustrative — repo/line refs are placeholders; the keys are the real §2 golden vectors.*

Two source repos each carry a sibling lesson; a human (or `/retro`) marks one transcendent, and the
recurrence net (§3) clusters the other with it:

    # infiquetra-home-lab/docs/engineering-journal/LEARNINGS.md
    **Generalizable rule.** A verification gate that is named but not executed is not a gate.
    **Transcendent.** Holds for any pipeline with declared-but-unwired checks, not just docs.

    # infiquetra-aws-infra/docs/engineering-journal/LEARNINGS.md
    **Generalizable rule.** A monitoring check that is configured but never scraped is not monitoring.

`promote` proposes (gated) a single upserted context-library entry:

    ## 2026-06-20

    ### A declared-but-unexecuted verification is not a gate

    **Author.** promote (saga)
    **Generalizable rule.** A check that is declared but never executed provides no protection — wire it
    into the path that actually runs, or it is theater.
    **Mechanism.** A gate's value is in its execution, not its declaration; an unwired check passes
    vacuously and hides the very class of failure it claims to cover.
    **Sources.** infiquetra-home-lab/docs/engineering-journal/LEARNINGS.md:142; infiquetra-aws-infra/docs/engineering-journal/LEARNINGS.md:88
    <!-- promote-keys: infiquetra-home-lab:87c4c366deb7; infiquetra-aws-infra:821928016ab6 -->

Re-running `promote` finds both keys already present → proposes nothing. A third repo with the same
lesson → an upsert that adds one backlink and one key, not a new entry.

## Requirement traceability

| Contract section | Freezes |
|---|---|
| §1 marker | R1, R2, R3, R4 · KTD1, KTD6, KTD7 |
| §2 source key | R12 · KTD2 |
| §3 legacy parsing | R5 (feeds R6/R7 clustering) · KTD4 |
| §4 promoted entry | R8, R9, R10, R16 · KTD3 |
| §5 idempotency / self-feed | R11, R12, R13, R14, R15 · KTD6 |
| §6 worked example | AE1, AE3, AE4 (executable expectations live in U3/U4 tests) |
