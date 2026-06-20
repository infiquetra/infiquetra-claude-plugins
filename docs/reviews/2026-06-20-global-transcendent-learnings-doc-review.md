---
date: 2026-06-20
type: doc-review
target: docs/brainstorms/2026-06-20-global-transcendent-learnings-requirements.md
reviewed_revision: working tree
blocked: false
---

# Doc Review — Global Transcendent-Learnings Layer

## Review-result contract

- **Target:** `docs/brainstorms/2026-06-20-global-transcendent-learnings-requirements.md`
- **Reviewed revision:** working tree (uncommitted)
- **Classification:** requirements (path + content shape; no formal SDLC rubric phase applies)
- **Blocked:** No — no `P0` or `P1` findings.
- **Applied fixes:** all five findings resolved as in-place edits to the target at the user's direction (2026-06-20).
- **Linked source:** `docs/ideation/2026-06-19-global-engineering-journal-ideation.md` (survivors #1 + #2)
- **Resolution:** dedup key repinned to a drift-stable identity (R9/R12/R13/AE1 + decision bullet); transcendence test made operational (R2/R3); recurrence threshold defaulted to ≥2, configurable (R7); enumeration root named (R5); source-marker lifecycle specified with no write-back (R5 + new scope boundary).

## Readiness summary

The doc can drive `/plan` — scope, decisions, and success criteria are pinned, and the open items are correctly tagged deferred-to-planning. The two `P2` findings are sharpenings that make the layer more precise and its idempotency guarantee real; neither blocks planning, but both are cheaper to settle now than after code exists.

## Findings by priority

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P2 | Idempotency key is unstable under line drift: R9 pins backlinks to `repo/path:line`, R12 calls the backlink set the dedup ledger. As `LEARNINGS.md` files grow, line numbers shift, so a line-keyed ledger can fail to recognize an already-promoted lesson and re-propose it — undercutting the "no duplicate proliferation, ever" success criterion. The R11 human gate backstops actual duplication, so blast radius is repeated re-proposals to reject, not corrupted data. Resolution: key dedup on something drift-stable (lesson/content hash or a stable ID), keep `file:line` only as a human-navigable pointer. | Resolved |
| 2 | P2 | Transcendence criterion is conceptual, not operational: R2/R3 rely on "judges whether a learning crosses repos." The Problem Frame illustrates the distinction (generalized-from-incident vs transcends-repos) but gives no concrete test, risking inconsistent marking across `/retro` runs and humans. Mitigated by the recurrence net (feeder 2) and the gate, so it is a precision/recall issue, not a correctness one. Resolution: add a one-line operational test, e.g. "would this rule be true and useful in a repo of a different stack/domain?" | Resolved |
| 3 | P3 | Recurrence threshold has no default: R7's "at least a configurable threshold of distinct repos" is left fully open (also in Outstanding Questions). Suggest leaning to a default of ≥2 repos — the literal meaning of "recurs across repositories" — raisable if it proves noisy. | Resolved |
| 4 | P3 | Repo-enumeration root undefined: R5 reads "across all repo journals," but the pass needs a defined discovery root, and the workspace root is not a git repo. An agent would otherwise invent where to look. Name the enumeration root during planning. | Resolved |
| 5 | P3 | Local marker lifecycle after promotion is unspecified: once a declared learning is promoted, the doc does not say whether its source marker is annotated as promoted. Dedup (R12) keeps re-collection correct either way, so this is a minor re-scan-cost/clarity point, not a correctness gap. | Resolved |

## Residual risk from limited evidence

The "single context window holds the candidate pool" assumption (the basis for judgment-over-vectors) is verified at ~785 lines today but is the layer's main scaling fault line; the doc surfaces it, and it is the right thing to revisit as the corpus grows.

Because the doc reshapes a workflow the user relies on and carries a real product-scope decision (transcendent-subset over aggregate), `/founder-review` is a reasonable optional lens before planning — not required, since the scope call is already made and recorded.
