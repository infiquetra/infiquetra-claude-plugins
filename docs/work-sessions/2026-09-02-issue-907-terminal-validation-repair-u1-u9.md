# Issue 907 terminal-validation repair — units U1 through U9 executed

**Date:** 2026-09-02
**Branch:** `work/cp907-launcher-session-contract`
**Plan:** `docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md` (round-3 document review ready, bound to e2470964)
**Backend:** inline (the plan's frontmatter)
**Scope:** U1 through U9 only, per the operator's dispatch. U10 through U14 are not started.

## What was built, by unit

Every unit followed the plan's verification discipline: the reproducer was written and run
first (it had to fail with the failure the artifact describes), then the edit, then the
named counter-cases, then every mutation in the unit's proof list applied and killed, then
the plugin test subset (`plugins/agent-launcher/tests`, `tests/test_agent_launcher_plugin.py`,
all `tests/test_orchestrate_*.py`), then the unit's own commit with its kill list in the
message.

| Unit | Commit | One line |
|---|---|---|
| U1 | c2edbf93 | The composer row rule as one classification per row, proven against two live captures |
| U2 | c9570239 | `input_box_text_chars` has one definition; the vocabulary derives from `ComposerState` |
| U3 | e0558af3 | The resend guard inspects when unowned or when the launcher typed into the pane |
| U4 | 9a707130 | The authorising inspection sits immediately before the write it authorises |
| U5 | 3a60c6ca | One named failure contract for a broken composer parser, stable module name |
| U6 | 38fd46e5 | A staged-input stop retries through the same pane and keeps its evidence |
| U7 | e35c802c | Truthful cleanup reporting: one dedup owner, a reason per keep, no false `closed` |
| U8 | 09b43eda | The companion floor as a command-by-state matrix (KTD7) |
| U9 | 6272d408 | Atomic ingest, Orchestrate's own `--help`, roster bound, layout named, tolerant run files |

## Kill-list outcome per unit

- **U1:** all nine mutants killed (C2, C13, C18, C20, C21, C22, C23, the `_unstyled_text`
  join separator, the trailing strip). C21/C22 first survived with a parametrisation derived
  from the module roster — the shrunk roster deleted its own test case — so the roster cases
  are now pinned literals bound to the module by an equality drift pin.
- **U2:** both mutants killed (unstyled-length recording; `NOT_FOUND` rename). The rename was
  first demonstrated to survive the old literal vocabulary test.
- **U3:** all four mutants killed (`used_pane`-only revert, ownership-only revert, `if True:`,
  deleted guard). The artifact's L6 `if True:` survivor is dead via the zero-call counter-case.
- **U4:** four killed (guard moved back above the preflight; pre-send guard removed;
  pre-picker guard removed; `if True:` on the pre-send site). The ownership-half drop survives
  exactly as the plan declares, and the `used_pane` half it leaves unbound is killed in U6.
- **U5:** both killed (handler narrowed to three types; `abs(hash(path))` restored).
- **U6:** all six killed (identity clearing restored; unconditional skip restored;
  `launch` for a marked unit; `used_pane=False`; `redeliver` calling the wrapper;
  split-membership).
- **U7:** all three killed (dedup guard deleted — observed across two passes; `None` treated
  as closed; the `session_owned` check removed).
- **U8:** all eight killed (O5, O16, O17, O18, O21, O3, one command removed from the gated
  set, `status` added to the gated set).
- **U9:** both killed (namespace restore deleted; the `tab_close_failure` roster line deleted
  — the O13 survivor).

No named mutation survived except the two the plan itself declares as deferred to another
unit's kill (U4's ownership-half, killed in U6) or as a non-kill (the roster-shrink lesson).

## Reproducers that unexpectedly passed

- **U1's border-roster cases and the C18 edge** passed at the frozen revision: the plan does
  not name them as evidence, and the artifact records the live captures cannot observe C18 —
  they are mutation-only observers, verified as such.
- **U9's roster AST test** passed at the frozen revision: the plan's grounding already
  recorded the roster as complete today; the test exists as the drift binder, and its own
  first run caught a gap in its binding collector (tuple-unpacked constants) rather than in
  the roster.
- **U6's owned-direction counter-case** passed at the frozen revision, as the plan predicted
  (zero guard calls before and after) — it exists so the `if True:` mutant has something to
  fail.

## Deviations, disclosed

1. **The plan's two live Claude captures no longer exist.** `wEV:pM` and `wEV:p6` are gone
   from workspace wEV. Two same-shape captures (marker row between two horizontal-rule rows,
   three two-space-indented status rows below) were taken 2026-09-02 from `wEV:pG` and
   `wEV:pQ`, Herdr 0.8.2, and recorded under keys naming vendor, date, version and pane.
   Both classify `empty` before and after U1.
2. **U5's unstyled-length mutation lives at the composer seam, not `launcher.py:814`.** That
   line has no unstyled number in scope (the guard sees only the inspection's visible text),
   so the mutant is applied at `_classify_block` returning the unstyled text — the one-line
   realization of the old document's claim — killed by the same named observer.
3. **U7 touched one file outside the plan's Files list.** Populating the conflict-worktree
   label reason (required by the plan's cause list and its "none under the aggregate
   sentence" scenario) changes one pinned assertion in
   `tests/test_orchestrate_land_worktree.py::test_plain_clean_keeps_a_symlinked_conflict_pointer_and_its_victim_worktree`.
   The single assertion now expects the label's own reason line; the file is otherwise
   untouched. No way was found to populate the label causes without breaking that pin, and
   leaving them unpopulated would under-deliver REL-06.

## Checks

The plugin test subset after U9: **926 passed** (`plugins/agent-launcher/tests`,
`tests/test_agent_launcher_plugin.py`, every `tests/test_orchestrate_*.py` module), plus
`ruff check` and `ruff format` clean on every touched file. The full repository gate was
**not** run, per the dispatch — the plan runs it once, after U14.

Nothing was pushed, no PR was opened, no issue or board state was touched, and no file under
`docs/code-reviews/`, `docs/evidence/`, `docs/reviews/` or `docs/plans/` changed
(byte-identical against `9650b552`).

## Next step

U10 through U14 remain, all outside this dispatch: U10 (Decision 1, unowned dispatch guards),
U11 (the `origin/main` merge), U12 (the engineering journal), U13 (Decision 2, the two
`origin/main` documents), U14 (release surfaces once, then the full gate and the terminal
Saga Code Review).