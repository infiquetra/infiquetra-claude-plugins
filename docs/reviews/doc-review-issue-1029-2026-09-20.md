---
target: docs/plans/2026-09-20-issue-1029-continuation-mechanics-plan.md
reviewed_revision: working tree
blocked: false
issue: infiquetra/infiquetra-claude-plugins#1029
date: 2026-09-20
---

# Document review — issue 1029 continuation mechanics plan

**Verdict: ready to drive implementation.** Eight findings were raised and all eight were repaired
in place; nothing above `P2` remains, and the two `P2`s that remain are recorded below as accepted
rather than fixed.

The review ran the issue-phase rubric engine's three always-apply lenses (acceptance criteria
clarity, devil's advocate, spec fidelity) and the readiness-skeptic pass, in two rounds against the
working tree. The document is not committed at the time of the review, so the reviewed revision is
recorded as `working tree` rather than a commit identifier.

## Findings

| # | Priority | Finding | Status |
|---|---|---|---|
| F1 | P1 | The card's own verification command names `tests/test_spore_hooks.py`, which does not exist in this repository. An implementer running it verbatim gets a collection error, or creates an empty file of that name and reports green | fixed — a new "Acceptance criteria, and what proves each one" section resolves the criterion to the four test files that actually carry the suppression cases, and says explicitly that no file of that name is created |
| F2 | P1 | Unit U1 placed the resolver in `run_record.py`, which closes an import cycle: `run_record` → `saga_spore` → `saga` → `run_record`. The lazy import at `saga.py:1065` would hide it at runtime | fixed — KTD2a moves the resolver to a new module, `plugins/saga/scripts/next_step_context.py`, and U1's tests carry a guard for it |
| F3 | P1 | `/doc-review`'s new ending would have continued into `/work` after reviewing any document, including a strategy or requirements document that `/work` cannot execute | fixed — the ending is bounded by three conditions: the document classified as a plan, the review was standalone, and no `P0` or `P1` remains |
| F4 | P1 | The plan named no mapping from the card's three acceptance criteria to units and proving commands, and the third criterion is a live observation that no unit test can establish | fixed — the new acceptance section maps all three and states that U2 is unfinished until the two live session starts have been run and recorded |
| F5 | P2 | `R3` and `R4` used "live", "done" and "closed" without pointing at the one definition | fixed — both requirements now name KTD1's empty-string rule and say the first two conditions are one observable |
| F6 | P2 | KTD2 omitted that the saga envelope store is per-worktree while the run record store resolves to the primary checkout, so the branch fallback is the ordinary path in a worktree rather than an exceptional one | fixed — stated under KTD2 with both file references |
| F7 | P2 | `R7`'s coexistence requirement named no test | fixed — `tests/test_spore_hooks_registration.py` cases named in both U2 and U3 |
| F8 | P2 | No statement of what happens when a continued step fails | fixed — a risk-section paragraph: report and stop, no retry of the chain, `next_step` left naming the failed step |

## Accepted, not fixed

**The open operator question stays open on purpose.** `/plan` continuing into `/work` in the same
turn for a `pr` destination is KTD4's proposal, not a recorded operator ruling. The plan declares it
under a `gate-record` marker rather than resolving it, which is the correct handling for a decision
the reviewer cannot make.

**The suggestion hook's usefulness is argued, not measured.** KTD3 claims a conservative local
matcher is worth shipping and says so as a judgment, citing issue 1038's measurements for the
judgment it is not making. No local-matcher accuracy figure exists, and the plan does not claim one.

## Residual risk

Two sibling cards edit files this plan edits — issue 1025 (the orchestrate rewrite, which bumps the
saga version) and issue 938 (which edits `plugins/saga/skills/work/SKILL.md`). The plan states both
and states how each resolves. Neither was verified against a landed change, because neither has
landed on `parent/1018` at the time of this review.
