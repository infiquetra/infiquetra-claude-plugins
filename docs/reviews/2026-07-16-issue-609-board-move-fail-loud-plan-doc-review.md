# Doc review - issue 609 board-move fail-loud plan

Date: 2026-07-16
Issue: `infiquetra/infiquetra-claude-plugins#609`
Plan: `docs/plans/2026-07-16-issue-609-board-move-fail-loud-plan.md`
Verdict: PROCEED

## Findings resolved

1. **High - exiting inside the project loop would hide later failures.** The
   plan makes `board_move()` aggregate outcomes, emit every result, then lets
   the CLI route choose exit 1.
2. **High - source tests alone would not prove the marketplace release.** The
   plan retains the canonical canary's merged-source refresh, installed version
   and enabled-state readback, installed invalid-status behavior, no-mutation
   proof, and fresh-process boundary on VM 209.
3. **Medium - a valid move would make the first canary unnecessarily mutating.**
   Runtime proof uses a nonexistent Status against a real item, exercising the
   changed installed path before the mutation call.
4. **Medium - partial release metadata could leave installed Claude on 2.10.0.**
   Manifest, generated marketplace, changelog, version guard, parity checks, and
   installed readback are one required unit.
5. **Medium - the pretrigger run is bound to the base head.** Any implementation
   head must use a successor run before PR evidence is recorded; attempt 1 is
   immutable and cannot be relabeled.

## Readiness

The failure classes, output behavior, exit boundary, test seams, release
surfaces, installed target, no-mutation proof, restart boundary, rollback, and
scope exclusions are decision-complete. No unresolved P0-P2 finding remains.
