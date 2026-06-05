# Retro report + journal-promotion templates

The shape of the `docs/retros/` writeup and the journal entry templates `/retro` promotes into.

---

## The `docs/retros/` writeup shape

Path: `docs/retros/<saga-id-or-issue>-<date>.md`. **Agent-consumable structured findings, NOT a
4500-word essay.** A future agent reads it cold and acts. Keep it tight; every claim links to evidence.

```markdown
# Retro — <thread or window>  ·  <date>

**Scope.** thread-scoped (<saga-id / issue / branch>) | meta-retro (<window>)
**Evidence freshness.** verified at HEAD | window guard: passed / disclosed-skip (<reason>)

## What shipped
- <one line each, linked to a PR # / commit / merged issue>

## Findings  (the structured core)
- **<finding title>** — <one or two sentences>. Evidence: <PR # / file:line / saga tick / check>.
  Promotion: LEARNINGS #<slug> | DECISIONS #<slug> | QUEUED #<slug> | none.
- ...

## Diff vs last retro
- Prior retro: <docs/retros/...>.
- Moved since: <new hotspots / resolved blockers / recurring friction>.
- Recurring (compounding signal): <friction seen in a prior retro → Pass 6(a) new-skill candidate>.

## Surfaced follow-ups
- → /handoff: <follow-up that should become an SDLC issue>
- → QUEUED: <durable backlog item>

## Proposed edits (Tier-2, awaiting operator)
- <curation / refine-lifecycle / refine-directive / memory-prune proposal> — status: proposed / applied / skipped.

## Refs
- Saga: <saga-id> (read-only).  PRs: <#N ...>.  Journal: <entries promoted>.
```

Rules: link every finding to evidence (no "it felt slow"); record the **diff-vs-last** so the retro
compounds; list Tier-2 proposals with their disposition (proposed / applied / skipped) — the doc is the
audit trail of what the engine offered and what the operator accepted.

---

## Journal-promotion entry templates

Match the existing journal format (each core file's block-quote intro is canonical). **Append new entries
to the top** of each file. New entries are Tier-1 AUTO (pure append).

### LEARNINGS.md

```markdown
## YYYY-MM-DD

### Short descriptive title  {#slug}

**Context.** One paragraph framing the situation.
**Evidence.** Specific PR / commit / file:line / reproduction.
**Mechanism.** Why it happened (root cause, not symptoms).
**Fix (or queued).** Concrete action + commit hash, OR a QUEUED.md ref if deferred.
**Validation (if applicable).** What later run / test proved it.
**What surprised (optional).** The thing not in the original mental model.
**Generalizable rule.** The lesson stripped of this incident — the highest-value line.
**Refs.** Cross-links to DECISIONS / QUEUED / narratives.
```

### DECISIONS.md

```markdown
## YYYY-MM-DD

### Short title (commit hash)  {#slug}

**Decision.** What we picked.
**Rejected alternatives.** What we considered and didn't pick.
**Rationale.** Why this won.
**Revisit when.** Condition that would change the calculus.
**Refs.** Related LEARNINGS / QUEUED / narratives.
```

### QUEUED.md

```markdown
### Short title  {#slug}

**Priority.** P0 / P1 / P2 / P3 / Maybe.
**Effort.** Rough estimate (hours / half-day / day / week / multi-day).
**Worth it when.** Specific trigger that would make this pressing.
**Context.** What surfaced this; cross-references.
```

### ARCHIVE.md

```markdown
### Short title  {#slug}

**SHIPPED YYYY-MM-DD** (commit hash) — was QUEUED P<n> #<slug>.   <!-- or REJECTED / SUPERSEDED -->

**Summary.** What shipped (or why rejected / what superseded it + revisit conditions).
**Refs.** DECISIONS / LEARNINGS / QUEUED cross-links.
```

A `QUEUED → ARCHIVE` move deletes the QUEUED entry, so it is **propose-diff-and-wait**
(`self-edit-safety.md`), not an auto-append — even though the ARCHIVE half is an append.
