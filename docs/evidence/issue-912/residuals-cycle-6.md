# Issue 912 — recorded residuals after cycle 6

Everything here is a validated review finding that this run did **not** repair, with the evidence
that establishes it and the reason it was left. It is recorded so the next reader does not have to
rediscover it, and so no closure claims more than was done.

## `AM-28` — re-anchoring is implemented twice and the two copies disagree

**Severity:** P2 · **Lens:** architecture-maintainability · **Location:**
`plugins/saga/scripts/handoff_envelope.py:192-238` and `:367-388`

**What is wrong.** Which path was classified has two owners. `infer_maturity` rewrites the
normalized path to the marker subpath whenever a marker directory is present, including when
neither the re-anchored candidate nor the original exists. `build_handoff_envelope` rewrites the
selected source only when the re-anchored candidate is an existing file. So for an out-of-root
absolute source whose re-anchored candidate does not exist, maturity is classified from the
re-anchored subpath while the envelope still emits the out-of-root absolute path.

**Reproduced at this revision.** With a declared root and an out-of-root absolute source:

```
neither exists        handoff_maturity='requirements-ready'
                      source='/…/tmp0zv1bnzb/docs/brainstorms/ghost.md'
                      suggested_command='/issue --prepare --from /…/tmp0zv1bnzb/docs/brainstorms/ghost.md'
exists, no maturity   same shape
```

The consequence is real rather than cosmetic: a consumer following `suggested_command` runs
`/issue --prepare --from` a path outside the declared root, which is not the path the maturity was
derived from.

**Why it was not repaired here.** The correct fix is the one the review prescribed — extract a
single `resolve_source(source, root) -> (path_used, is_reanchored)` and have both functions consume
its one return, so classification and attribution cannot diverge. That is a genuine refactor across
two functions. Twice in this run a narrower, cleverer patch closed the reported symptom and opened a
new defect: the cycle-4 repairs produced the cycle-5 P1 decode fail-open, and the cycle-5 repairs
produced three cycle-6 findings including a third fail-open shape. Attempting a minimal patch to
this divergence under the same pressure is the same bet a third time.

**What is safe about leaving it.** It is an attribution defect, not a fail-open. No shape reaches a
live route that should have failed closed — the fail-open class is closed and mutation-proven across
all six frontmatter shapes. The wrong value is the path named in the command, not the maturity
decision that gates it.

**Recommended next step.** Do the extraction as its own change with its own review, not folded into
a repair cycle.
