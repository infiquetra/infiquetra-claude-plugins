---
title: issue 912 repair round — three file-disjoint worker lanes for the 45 open review findings
type: fix
status: active
date: 2026-09-04
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/912
backend: inline
---

# issue 912 repair round — three file-disjoint worker lanes for the 45 open review findings

## Summary

This plan decomposes the 45 findings still open after cycle 8 of the issue-912 code review into
three worker lanes whose owned file sets do not overlap, so three workers can run at once and their
work can be integrated one lane at a time onto `repair/cp912-review-cycle-1` (HEAD `77c01c99`).

- **Lane A — the handoff envelope core.** 20 findings whole plus the test halves of two more. This is
  the **constrained lane**: every one of them edits `plugins/saga/scripts/handoff_envelope.py` or the
  test module that pins it, so they cannot be spread without faking disjointness.
- **Lane B — the handoff contract's prose, the release note, the journal, and the dialogue guard.**
  9 findings whole plus the prose halves of two more, plus one residue the brief lists as closed.
- **Lane C — `/loop`, `/resume`, `/brainstorm` routing prose, the test guards that pin them, and the
  docs model and renderer.** 14 findings.

Integration order is **A, then B, then C, then a serial journal fold**. Lane A lands first because
it decides the behaviour every prose surface in Lane B must describe. Lane B lands before Lane C
because Lane B tightens a guard that scans Lane C's test files, so Lane C's integration run is where
any violation of that guard should surface.

Every finding gets a disposition in the table at the end. Two are already satisfied on the live
tree and are confirmed by mutation rather than re-implemented (API-4 and the decision-record half of
SEC-9). One finding the brief lists as closed (DOC-1) still has its named line wrong on the live tree
and is folded into Lane B. One finding (SEC-1) reverses a recorded design decision; the plan commits
to the reversal and names it as the first stop-and-surface item.

Authored 2026-09-05 against the checkout state verified that day; the filename carries the date the
planning dispatch named.

## Authoritative inputs and the custody constraints

Inputs, read in full before planning:

1. The typed review result bound to `1bcee0a9` (evidence-ledger sequence 17):
   `docs/evidence/issue-912/artifacts/219441cf70af78afe2d682a6156d5dfb2bc7441dab0393f5bc1b6bfdea2056cc.md`.
   Each finding's "Why each finding matters" entry is the source for the work items below, not the
   index table.
2. The cycle-8 disposition, `docs/evidence/issue-912/disposition-cycle-8.md`.
3. The cycle-7 residual record, `docs/evidence/issue-912/residuals-cycle-7.md` (API-23, issue 950).

Hard constraints, restated so that every worker carries them:

- `docs/plans/2026-08-30-agent-launcher-907-run-plan.md` is untracked, belongs to issue 907, and is
  never modified, staged, removed, or restored. Its SHA-256 stays
  `f695be329f00597156b7c085d17885403a3b52b6b5afa1244f91524a694aac84`. No lane lists it.
- Nothing under `plugins/mission-control/` or `plugins/orchestrate/` is edited.
- No plugin is installed and the marketplace is not refreshed (issue 907 has a live worker pinned to
  installed Saga 0.148.0).
- Nothing under `docs/plans/` is rewritten. This file is a new plan, not an edit.
- `/Users/jefcox/workspace/infiquetra/orch-claude-plugins-918` and issue 918 are not touched.
- Commits reference issues as `re #912` (and `re #913` etc.), never `Fixes`, `Closes`, `Resolves`.
  No attribution trailers of any kind.
- `origin/main` is not merged into the branch. The controller incorporates main after issue 918
  lands.
- No worker ever runs `git checkout <path>`, `git restore`, or `git stash` on a working file. The
  restore protocol is a `cp` backup and a `cmp -s` byte-identity check (KTD2).

## Preflight findings — what the live tree says that the brief does not

Verified on 2026-09-05 at `77c01c99`, branch `repair/cp912-review-cycle-1`, clean apart from the
untracked 907 plan.

| # | Finding | Evidence | Consequence for the plan |
|---|---|---|---|
| P1 | **DOC-1 is listed as closed, but its named line is still false.** Cycle 8 rewrote only the fourth bullet of the 0.156.0 release note. The second bullet (`plugins/saga/CHANGELOG.md:8`) still says an out-of-root source with no readable declaration "still resolves by the path rule and can route live" and that a marker-less declaring file "is not read and its declared maturity is bypassed by path inference". | `git diff 1bcee0a9 HEAD -- plugins/saga/CHANGELOG.md` touches one line, the line-10 bullet. Line 8 is byte-identical to the reviewed revision. | Lane B rewrites bullets 2 and 4 together under SEC-1's prose work. The disposition table records DOC-1 as "closed in the brief, residue repaired here". |
| P2 | **API-4 appears already pinned by cycle 8.** `tests/test_handoff_envelope_maturity.py:870` (`test_marker_less_out_of_root_declaration_is_never_read`) writes a marker-less absolute file declaring `plan-ready` outside the root and asserts the `unknown:out-of-root:` sentinel. The review's API-4 mutation (delete the `absolute = False` assignment for the marker-less arm) makes that file route live, so this test should fail under it. | Test read in full; mutation reasoned from `handoff_envelope.py:324-327` and `:329-335`. Not yet executed. | Lane A confirms by running the mutation (evidence shape E2). If the test fails under the mutation, API-4 is closed with no new test. If it survives, Lane A adds the pin. |
| P3 | **The decision-record half of SEC-9 is already satisfied.** `docs/engineering-journal/DECISIONS.md:7` now enumerates all five sentinel causes including `unknown:out-of-root:<path>`. | Read at HEAD; cycle 8 commit `b6bf5b05` changed six lines of the file. | SEC-9 reduces to the forgery pin test (Lane A). Lane B has nothing to do for it. |
| P4 | **No plugin version bump is needed for this round, and none is planned.** The branch's saga manifest is `0.156.0`; `origin/main` is at `0.155.0` (`c84af7ad`, one commit ahead of the merge base `f30d8678`). `tools/release_surface_diff_guard.py` requires a strictly advancing version against the base, which `0.156.0` already is. | `plugins/saga/.claude-plugin/plugin.json` on both refs. | The unreleased 0.156.0 entry is amended in place (KTD5). The eight version surfaces stay untouched. If issue 918 lands on main carrying `0.156.0` before this branch is frozen, the controller must re-bump all eight surfaces; that is the version-collision watch in the stop-and-surface list. |
| P5 | **The full gate cannot run green in this checkout.** `tests/test_plan_artifact_conformance.py` scans `docs/plans/` from disk, untracked files included, and the 907 plan fails it. Cycle 8 ran the gate in a clean detached worktree for that reason. | `docs/evidence/issue-912/disposition-cycle-8.md` "Gate" section; test read. | Workers run scoped tests in their own checkouts. The integrator runs the full gate in a detached worktree at each integration commit (KTD10). This plan file itself satisfies the conformance contract (frontmatter fields `title`, `type`, `status`, `date`, `backend`; the three section markers). |
| P6 | **Every line number in the review is stale for the envelope module and for `LEARNINGS.md`.** Cycle 8 inserted the strict YAML loader (23 lines at the top) and the alias-tracking walk, shifting the envelope anchors by roughly 37 lines, and added 26 lines at the top of `LEARNINGS.md`, shifting its anchors by 26. | `git diff --stat 1bcee0a9 HEAD` shows `+55` on the module. | The line map below is the one workers use. Findings are identified by content, never by the review's line numbers. |
| P7 | **The continuity contract test binds three prose files at once.** `tests/test_brainstorm_continuity_contract.py` holds the checks for the near-match predicate in `brainstorm/SKILL.md`, the run classes in `resume/SKILL.md`, and the routing rows in `dispatch-table.md`. | File read; checks at lines 391, 409, 458, 482, 504. | Those three prose files and that test module must be one lane (Lane C). The dialogue guard in `tests/test_brainstorm_evidence_model.py` scans every `tests/test_brainstorm_*.py`, so it goes to a different lane (B) and Lane C's integration must run it. |

### Line map for `plugins/saga/scripts/handoff_envelope.py` (review anchor → HEAD `77c01c99`)

| Review line | HEAD line | Content |
|---|---|---|
| 45 | 71 | `_FRONTMATTER_READ_LIMIT = 8192` |
| 66-72 | 74 (signature), 77-78 (docstring), 92-96 (arm) | the `allow_bullet=False` arm of `_extract_declared_maturity_value` |
| 154 | 180 | `end = text.find("\n---", 3)` |
| 169-170 | 195-196 | the unreachable `continue` in the unterminated scan |
| 196 | 233 | `yaml.load(frontmatter, Loader=_StrictMappingLoader)` |
| 199-211 | 237-249 | top-level-key decision after parse |
| 230 | 264-270 | `_reanchor_to_marker` docstring ("single owner") |
| 239 | 276 | the `idx == 0` arm of the marker slice |
| 243 | 280 | `def infer_maturity` |
| 275 | 312 | refusal when the in-root twin exists but declares nothing (TEST-1's uncovered branch) |
| 277-280 | 285-293, 314-317 | the comment block cycle 8 rewrote (still describes "three outcomes" and a read of the original) |
| 281-286 | 318-323 | read of the original absolute file (SEC-1's live route) |
| 290 | 327 | `absolute = False` for the marker-less arm (API-4) |
| 302 | 332, 339 | unguarded `candidate.is_file()` (SEC-8) |
| 421 | 455-464 | `build_handoff_envelope`'s own inline re-anchor decision (AM-3, TEST-2) |
| 438 | 474-476 | the "redundant with suggested_command" comment (API-11) |
| 451 | 488-495 | the `unknown:carrier:` diagnostic (AU-2) |
| 484 | 517-523 | the `unknown:unrecognized:` diagnostic and its remediation list (AU-11) |
| 488 | 525-533 | the "should not occur" fallback arm (AM-10) |
| 499 | 536 | `suggested_command = f"/issue --prepare --from {selected_source} --maturity {maturity}"` (SEC-5) |

## Key Technical Decisions

**KTD1 — SEC-1 is repaired by refusing every out-of-root source, whatever it declares.** When a root
is declared and the source resolves outside it: if the path carries a marker directory and the same
subpath exists inside the root as a resolved, contained file, that in-root twin is read and its
declaration decides; otherwise the source is refused with `unknown:out-of-root:<path>`, whether or
not the file exists and however the path is spelled. Two rules a worker must not soften. First: if
the in-root twin exists but declares nothing (the frontmatter reader returns `None`), the source is
refused with `unknown:out-of-root:`; the path rule is never applied to the twin, and TEST-1 pins
exactly that refusal. Second: containment is judged on resolved paths, so an in-root symlink whose
target lies outside the root is refused, not read, in both spellings. The arm at HEAD lines 318-323
that reads the original absolute file is deleted.
This reverses the clause in `DECISIONS.md` `{#913-maturity-unknown-sentinel}` that chose reading the
original over refusing. That clause's stated reason, "refusing would hide its declared maturity
behind a path-rule fallback that routes live", is no longer true: refusal now returns a sentinel with
a diagnostic, not a path-rule route. What is given up: a `/handoff` run from a checkout that does not
contain the artifact another worktree wrote now stops with "name a source inside the declared root"
instead of routing. That is the correct stop for a prepared issue, which would otherwise cite a path
absent from the repository. Scope: containment applies only when `root` is passed; `infer_maturity`
with `root=None` keeps reading the absolute path the caller named, because `build_handoff_envelope`
always passes a root and the envelope is the surface the finding is about. `test_root_honoured`'s
cwd-decoy case (in-root twin exists) is unaffected.

**KTD2 — Two evidence shapes, one restore protocol, and no `git checkout` ever.** Every finding's
acceptance is one of:

- **E1, behaviour defect.** The named test is written first and run against the unfixed module: it
  must FAIL, and the failing assertion line is pasted into the lane's evidence note. The fix is
  applied; the test passes. If the worker has already fixed the module, the pre-fix module is
  obtained with `git show 77c01c99:<path> > "$SCRATCH/pre.py"` (a read, not a checkout), copied over
  the live file for the red run, then the fixed copy is restored and byte-compared.
- **E2, missing pin.** The new test passes on the live code. The review's named mutation is applied
  to the LIVE file; the new test must FAIL; the file is restored and byte-compared. A mutation that
  the new test survives means the pin is not load-bearing and the work item is not done.

The protocol, verbatim, with `SCRATCH` set to the worker's scratchpad directory:

```bash
cp "$FILE" "$SCRATCH/$(basename "$FILE").bak"
# ... apply the mutation or the pre-fix copy to "$FILE" ...
uv run pytest "$TEST_FILE" -q -k "$TEST_NAME"        # record PASSED/FAILED verbatim
cp "$SCRATCH/$(basename "$FILE").bak" "$FILE"
cmp -s "$SCRATCH/$(basename "$FILE").bak" "$FILE" && echo RESTORED-BYTE-IDENTICAL || echo RESTORE-FAILED
```

`RESTORE-FAILED` is a stop: do not continue, do not commit, report it. A previous verify agent ran
`git checkout <path>` mid-run and clobbered live uncommitted work; that command and its siblings are
banned for every worker in this round.

**KTD3 — One resolver owns the source decision (AM-3, TEST-2).** A module-level pure function
`resolve_source(source: str, root: Path | None) -> ResolvedSource` returns a small dataclass:
`path_to_read: Path | None`, `published: str`, `reanchored: bool`, `refused: bool`. `infer_maturity`
and `build_handoff_envelope` both call it; the envelope's inline re-anchor block at HEAD lines
455-464 is deleted, and the backslash normalisation happens once inside the resolver. Ownership is
pinned by a spy test: `resolve_source` is monkeypatched to return a forced answer and the envelope's
published `source` must equal that answer's `published` field, while `handoff_maturity` must equal
`infer_maturity`'s answer for the same input. An inline re-anchor in either caller makes one of
those equalities fail.

**KTD4 — The sentinel vocabulary does not grow.** Five `unknown:` causes ship; AU-2 is repaired by
making the `unknown:carrier:` diagnostic name its actual sub-cause (non-delimited, nested under a
key, sequence item, block that will not parse), not by minting a sixth sentinel. A sixth cause would
change `saga-spec.md` §4 and §9, the handoff skill, the decision record, the release note, and the
consumer contract, which is a contract change this round does not make. The sub-cause reaches the
diagnostic through a second, non-published channel (a `carrier_detail(path)` helper the envelope
calls only when the maturity is `unknown:carrier:`); the published `handoff_maturity` string is
unchanged.

**KTD5 — No plugin version bump; the unreleased 0.156.0 entry is amended in place.** The entry's
heading `## [0.156.0] - 2026-09-01` is kept so `tests/test_saga_plugin.py:48`, the marketplace
entry, and the other six version surfaces stay untouched. Its bullets are rewritten to describe the
behaviour that ships after this round. The envelope `schema_version` stays `1.1`: SEC-5's quoting
changes no field's meaning (a plain path renders byte-identically; only a path needing quotes is
quoted), and the read-window rule narrows a fail-open, which is the direction the 1.1 bump already
described.

**KTD6 — Journal writes are serialised.** `docs/engineering-journal/LEARNINGS.md` and
`DECISIONS.md` are Lane B's files. Lane B makes the in-place corrections (DOC-8, DOC-11, DOC-6) and
writes its own new entries under a new `## 2026-09-05` heading at the top of each file (the journal
lint requires added entries in the newest date section, dates strictly descending). Lanes A and C
write their learnings and decisions as complete six-field entries into lane-owned draft files
(`docs/evidence/issue-912/lane-A-journal-draft.md`, `lane-C-journal-draft.md`). The integrator folds
those drafts into the `## 2026-09-05` sections after Lane C lands and deletes the draft files. This
deviates from "same commit that ships the change" by three commits inside one branch, for the sake
of disjointness; it is recorded here so nobody reads the fold commit as an afterthought.

**KTD7 — The read window fails closed (CORR-6) and a parse failure scans the whole window (CORR-7).**
When the 8192-byte read fills the window (the file is larger) and no closing delimiter line is found
inside it, the block is classified `unknown:unterminated:` with a diagnostic that names the window
("closing `---` not found within the first 8192 bytes; shorten the frontmatter or close the block")
instead of telling the author to close a block that is closed. A small file with no closing
delimiter and no visible maturity keeps its current behaviour. The closing delimiter is a line that
is exactly `---` (regex `^---\s*$`, multiline), not any `\n---` substring. When the delimited slice
fails to parse as YAML, the fallback scan for a `maturity:` line covers every line of the read window
rather than the truncated slice, so a visible declaration after an early `---` inside a quoted string
fails closed as `unknown:carrier:` instead of routing on the path rule. This branch runs only for a
document that is already malformed, so a body mention of `maturity:` costing a refusal is the
fail-closed price and is acceptable.

**KTD8 — `suggested_command` is shell-safe (SEC-5).** The runnable form quotes the source with
`shlex.quote`, so `shlex.split(cmd)` yields exactly six tokens: `/issue`, `--prepare`, `--from`, the
source, `--maturity`, the maturity. A plain path needs no quotes and renders byte-identically, so
every existing exact-string assertion still passes. Every diagnostic form renders the source through
one display helper that escapes control characters (`\n`, `\r`, `\t`, NUL) and bounds the displayed
source to 256 characters with an ellipsis, so no published string contains a line break. The
`--target-team` and `--target-repo` suffixes come from operator flags, not author-controlled files,
and are left as they are.

**KTD9 — Both lanes write the same containment truth.** Lane A (docstrings, comments, tests) and
Lane B (skill, spec, release note, decision record) use this canonical sentence, adapted to each
surface's voice but not in meaning:

> A source that resolves outside the declared root is never read. If its path carries a marker
> directory (`docs/brainstorms/` and the like) and the same subpath exists inside the root, that
> in-root file is read instead and its declaration decides. Otherwise the source is refused with
> `unknown:out-of-root:`, whatever it declares, whether or not it exists, and however its path is
> spelled.

The integrator checks Lane B against Lane A with the greps in U4, not by re-reading.

**KTD10 — Scoped runs while working; the full gate only in a detached worktree at integration.**
Each lane runs the test modules named in its "Tests to run" list plus `uv run ruff check .`,
`uv run ruff format --check .`, and `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
(never two mypy runs at once). The integrator runs the full gate, 21 blocking steps plus 4
advisory steps for 25 step headers, in a detached worktree at each integration commit,
backgrounded, and reads `result.txt`, never the summary line. Blocking failures fail the gate;
advisory findings (the board census, the golden fixture, and the two bandit steps) are read, not
voted green. An integrator counting headers expects 25, matching cycle 8's recorded run. A scoped
run is not a green gate and no lane claims one.

## Run topology

```
Lane A --> integrate A --> Lane B --> integrate B --> Lane C --> integrate C --> journal fold --> full gate
```

Lanes A, B and C run concurrently in their own checkouts of `77c01c99`. Integration is serialised
onto `repair/cp912-review-cycle-1` in that order. Recommended tiers: Lane A at Opus, extra-high
effort (design and adversarial pinning in the file that has failed six reviews); Lane B at Opus, high
(contract prose whose every sentence was scored); Lane C at Opus, high (guard redesigns are
judgment). Six repair cycles on this branch failed on repair quality, not on volume, so cheaper tiers
here are a false economy. Concurrency: three workers is the cap when any is above Haiku.

| Lane | Subject | Findings whole | Findings split | Owned paths |
|---|---|---|---|---|
| A | handoff envelope core (constrained) | 20 | AU-3 test half, SEC-9 test half | 6 |
| B | contract prose, release note, journal, dialogue guard | 9 | AU-3 prose half, SEC-9 prose half (already satisfied), SEC-1 prose half, DOC-1 residue | 10 |
| C | routing prose, test guards, docs model and renderer | 14 | — | 18 |

## Implementation Units

### U1. Lane A — the handoff envelope core (constrained lane)

**Lane statement.** Make `plugins/saga/scripts/handoff_envelope.py` fail closed on every out-of-root,
oversized, unparseable, and injected input the review reproduced, decompose its two oversized
functions into single-exit-set helpers, and pin every repair by a test the review's own mutations
make fail.

**Why this lane is constrained.** All 20 whole findings and both split halves edit the envelope
module, its maturity test module, or both. Spreading them would put one file in two lanes.

**Owned paths (complete; a Lane A worker may edit nothing else):**

- `plugins/saga/scripts/handoff_envelope.py`
- `plugins/saga/scripts/parse_issue.py` (owned so no other lane touches it; CORR-5 needs no code
  change here)
- `tests/test_handoff_envelope_maturity.py`
- `tests/test_handoff_envelope.py`
- `docs/evidence/issue-912/lane-A-evidence.md` (new: every E1/E2 run, verbatim)
- `docs/evidence/issue-912/lane-A-journal-draft.md` (new: journal entries for the fold, KTD6)

**Forbidden for Lane A:** every prose surface (`CHANGELOG.md`, `saga-spec.md`, any `SKILL.md`,
`state-readiness.md`, the journal). Where a Lane A change makes a prose claim false, the canonical
sentence in KTD9 is what Lane B writes; Lane A records the affected surfaces in its evidence note.

**Fix requests → findings → files.**

| Fix request | Findings | Files touched |
|---|---|---|
| `fix-21fc252e3694` | SEC-1, TEST-1, TEST-2, AU-2, AM-3, AM-4, AM-5, AM-6, AM-10, API-4, API-11, AU-11, CORR-6, CORR-7, SEC-3, SEC-5, SEC-8 | `handoff_envelope.py`, `test_handoff_envelope_maturity.py` |
| `fix-81762bf840d0` | SEC-7, TEST-10 | `test_handoff_envelope_maturity.py` |
| `fix-1f7d0e31b73e` | CORR-5 | `test_handoff_envelope_maturity.py` (already loads `parse_issue.py`) |
| `fix-c953e1223ef6` (test half) | AU-3 | `test_handoff_envelope_maturity.py` |
| `fix-e9b5ab8ede0f` (test half) | SEC-9 | `test_handoff_envelope_maturity.py` |

**Work items and acceptance evidence.** Names given for new tests are the pre-agreed names; Lane B's
release note cites one of them.

1. **SEC-1 (P1) — refuse every out-of-root source.** Implement KTD1 and KTD3 together: `resolve_source`
   decides; the read-original arm (HEAD 318-323) is gone. Rewrite the comment block at HEAD 285-293
   and 314-317 to enumerate exactly the exits the code has (this closes **AM-4**). Three tests:

   (a) `test_out_of_root_declaring_file_is_refused_in_both_spellings` (E1, **the SEC-1 security
   proof**): a marker-bearing out-of-root file declaring `plan-ready`, no in-root twin, queried
   absolutely and via `os.path.relpath`; both spellings return `unknown:out-of-root:` and the
   envelope's `suggested_command` contains no `/issue --prepare`. **The red line that must be
   pasted is this test failing on the pre-fix module because `suggested_command` contains
   `/issue --prepare` for the absolute `plan-ready` spelling.** A red line on the maturity value
   alone is not the proof.

   (b) `test_in_root_symlink_to_out_of_root_is_refused` (E1): `root/docs/plans/link.md` is a
   symlink to an out-of-root file declaring `plan-ready`; both the relative source
   `docs/plans/link.md` and the absolute spelling of that in-root path return
   `unknown:out-of-root:` and no `/issue --prepare`. On the pre-fix module the absolute spelling
   returns `plan-ready` with a live command, so it FAILS.

   (c) Invert `test_reanchored_missing_fallback_to_original` into
   `test_reanchored_missing_twin_is_refused`: the same `pending-confirmation` fixture, built with
   `tmp_path` and no `monkeypatch` parameter, asserting `unknown:out-of-root:`. This is the TEST-10
   rewrite plus a sentinel pin, **not** the security proof: its fixture declares
   `pending-confirmation`, which never emits a runnable command, so its "no `/issue --prepare`"
   half is green before and after the fix and proves nothing about the live route.

   Evidence: the (a) and (b) red runs pasted verbatim with the failing assertion line, then all
   three green.

2. **TEST-1 (P1) — pin the refusal when the in-root twin exists but declares nothing.** New test
   `test_reanchored_twin_declaring_nothing_is_refused` (E2): root holds `docs/brainstorms/x.md`
   with frontmatter `title: hello` only; source is `<tmp>/elsewhere/docs/brainstorms/x.md`; expect
   `unknown:out-of-root:`. Mutation: replace that refusal's `return` (HEAD 312, or its successor in
   the resolver) with `pass`; the test must FAIL with `requirements-ready`. Restore, `cmp -s`.

3. **TEST-2 (P1) — pin single ownership of re-anchoring.** Two tests under KTD3: (a)
   `test_resolve_source_is_the_single_owner` monkeypatches `HE.resolve_source` to return a forced
   `ResolvedSource(refused=True, published="FORCED-BY-TEST", ...)` and asserts
   `envelope["source"] == "FORCED-BY-TEST"` and `envelope["handoff_maturity"].startswith("unknown:out-of-root:")`;
   (b) `test_infer_and_envelope_agree_on_every_out_of_root_shape` parametrised over the four shapes
   the review reproduced (ghost twin, twin declares nothing, backslash-spelled path, marker-less
   absolute) asserting `envelope["handoff_maturity"] == infer_maturity(source, root)`. Mutation (E2):
   reintroduce the review's inline divergent re-anchor in `build_handoff_envelope` (slice from the
   marker rather than its parent); (a) must FAIL. Second mutation: drop the backslash normalisation
   from the resolver's envelope path only; (b) must FAIL on the backslash case.

4. **AU-2 (P1) — the carrier diagnostic names its cause.** KTD4. New parametrised test
   `test_carrier_diagnostic_names_the_actual_cause` (E1) over three fixtures: (i) closed block,
   `maturity` nested under `meta:`; (ii) closed block, `keys:` then `- maturity: requirements-ready`;
   (iii) no delimiters, `maturity: requirements-ready` on line 1. Assert all three carry
   `unknown:carrier:` in `handoff_maturity`; assert (i)'s diagnostic does not contain
   "missing delimiters" and does contain "nested" (or "not a top-level key"); (ii)'s names a sequence
   item; (iii)'s names missing delimiters; and that the three diagnostics are pairwise different. On
   the pre-fix module all three are byte-identical, so it FAILS. `test_carrier_diagnostic_names_delimiters_not_vocabulary` (existing) stays green.

5. **AM-3 (P2) — single resolver.** Delivered by KTD3 with item 3. Acceptance beyond the tests:
   `grep -c "_reanchor_to_marker(" plugins/saga/scripts/handoff_envelope.py` returns exactly 1 (the
   call inside `resolve_source`), and `grep -c "_is_within(" ` returns the count inside the resolver
   only (no call in `build_handoff_envelope`). The docstring's "cannot diverge" claim is replaced by a
   sentence pointing at the spy test that enforces it.

6. **AM-4 (P2) — false comments.** Cycle 8 corrected the two sentences the review quoted; the block
   still says "three outcomes are possible … the original absolute file is read". Rewritten under item 1.
   Acceptance: `grep -c "original absolute file is read" plugins/saga/scripts/handoff_envelope.py`
   returns 0; the comment enumerates two outcomes (twin read, refused).

7. **AM-5 (P2) — three unreachable branches.** Delete the `allow_bullet` parameter and its False arm
   (both callers pass True), the `continue` at HEAD 195-196, and the `idx == 0` arm at HEAD 276 (both
   callers guard on an absolute path). Acceptance: `uv run pytest tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py --cov=plugins/saga/scripts --cov-report=term-missing`
   shows no missing lines inside any function of `handoff_envelope.py` that item 8 produces from
   `_extract_declared_maturity_value`, `_read_frontmatter_maturity`, and `_reanchor_to_marker`; the
   coverage table lines are pasted into the evidence note.

8. **AM-6 (P2) — decompose the two oversized functions.** Move the three closures
   (`_scanned_maturity_line`, `_carrier`, `_has_nested_maturity`) to module scope; split
   `_read_frontmatter_maturity` into a bounded reader (bytes → text or `unknown:unreadable`), a block
   splitter (text → none / unterminated / closed body, applying KTD7), and a classifier (closed body →
   declaration or sentinel); `infer_maturity` becomes resolver plus path rule. Acceptance is the AST
   count, pasted verbatim:

   ```bash
   uv run python - <<'PY'
   import ast
   tree = ast.parse(open("plugins/saga/scripts/handoff_envelope.py").read())
   for f in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
       returns = sum(isinstance(n, ast.Return) for n in ast.walk(f))
       branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp)) for n in ast.walk(f))
       nested = sum(isinstance(n, ast.FunctionDef) for n in ast.walk(f)) - 1
       print(f"{f.name}: returns={returns} branches={branches} nested_defs={nested}")
   PY
   ```

   Bar: no function with more than 8 returns or more than 12 branch nodes, and `nested_defs=0`
   everywhere. The review measured 13/18 and 23/37 with three nested defs.

9. **AM-10 (P3) — the "should not occur" arm is the blank-maturity path.** Add an explicit
   `elif maturity == ""` diagnostic ("Blank maturity for <source> — the key is declared but empty; …")
   and delete the `removeprefix("unknown:")` ternary and the "should not occur" comment. New test
   `test_blank_maturity_diagnostic_says_blank_not_unrecognized` (E1): fixture `---\nmaturity:\n---`;
   assert "blank" in the diagnostic (case-insensitive) and "Unrecognized" not in it; FAILS on the
   pre-fix module. Acceptance grep: `grep -c "should not occur"` returns 0.

10. **API-4 (P2) — confirm the existing pin (P2 preflight).** E2 only: mutation = remove the
    `absolute = False` assignment for the marker-less arm (HEAD 324-327, or its successor);
    `test_marker_less_out_of_root_declaration_is_never_read` must FAIL. If it does, record "API-4
    closed by cycle-8 test, mutation-confirmed" in the evidence note and add nothing. If it survives,
    add `test_marker_less_absolute_out_of_root_is_refused` asserting the sentinel and repeat the
    mutation until it fails.

11. **API-11 (P3) — the 120-character bound comment is false.** Rewrite HEAD 474-476 to say that both
    `handoff_maturity` and `suggested_command` carry the bounded text and the full author-declared
    value appears in neither. Acceptance: `grep -c "redundant with suggested_command"` returns 0.

12. **AU-11 (P2) — the unrecognized diagnostic omits `pending-confirmation`.** Append to the
    remediation list: ", or `pending-confirmation` for a Brainstorm boundary that is not yet confirmed
    (no durable route until it is)". New test `test_unrecognized_remediation_names_pending_confirmation`
    (E1): fixture under `docs/brainstorms/` declaring `maturity: pending confirmation` (space);
    assert `"pending-confirmation" in envelope["suggested_command"]`; FAILS on the pre-fix module.
    Update any existing assertion that pins the exact old list (`test_unrecognized_maturity_fails_closed`
    if it does). `ROUTABLE_MATURITIES` itself is unchanged.

13. **CORR-6 (P2) — the read window is a semantic boundary.** Implement KTD7. Two new tests (E1)
    using the review's recipe (a closed block with 900 filler keys, 9,946 bytes):
    `test_maturity_past_the_read_window_fails_closed` (maturity after the filler; on the pre-fix module
    returns `requirements-ready`, so FAILS; after: `unknown:unterminated:`) and
    `test_closing_delimiter_past_the_read_window_names_the_window` (`maturity: plan-ready` on line 2,
    close after the filler; assert the diagnostic contains `8192` and does not contain
    "closing --- missing"; FAILS on the pre-fix diagnostic). `test_frontmatter_read_limit_does_not_split_a_codepoint` stays green.

14. **CORR-7 (P2) — an early `---` truncates the block.** Implement KTD7's line-anchored close and
    whole-window fallback scan. New test `test_early_dashes_inside_quoted_value_fail_closed` (E1) with
    the review's fixture `---\nnote: "line\n---\n"\nmaturity: pending-confirmation\n---\n# doc\n`;
    assert `unknown:carrier:` and no runnable command; FAILS on the pre-fix module
    (`requirements-ready`).

15. **SEC-3 (P2) — `RecursionError` escapes the YAML handler.** Catch `RecursionError` beside
    `yaml.YAMLError` and treat it as will-not-parse. New test `test_deeply_nested_yaml_fails_closed_without_traceback`
    (E1): `a: ` plus 4000 `[` and 4000 `]` inside a closed block preceded by `maturity: plan-ready`;
    assert the call returns a string starting `unknown:carrier:` and raises nothing; FAILS
    (raises) on the pre-fix module.

16. **SEC-5 (P2) — command injection through the source path.** Implement KTD8. New parametrised
    test `test_suggested_command_is_shell_safe_and_single_line` (E1) over the review's four probes
    (semicolon plus `rm`, `--maturity resume-ready --target x`, `--force`, a name carrying a newline
    and a second `/issue` line): for a routable maturity assert
    `shlex.split(cmd) == ["/issue", "--prepare", "--from", source, "--maturity", maturity]`; for
    the newline probe under a refusing declaration assert `"\n" not in cmd`; FAILS on the pre-fix
    module for every probe. Plus `test_plain_path_command_is_byte_identical` asserting the existing
    exact string for `docs/plans/a.md`.

17. **SEC-8 (P3) — overlong path component raises `OSError`.** Guard every `is_file()` in the module
    with a helper that returns False on `OSError`/`ValueError`. New test
    `test_overlong_path_component_returns_a_sentinel_not_oserror` (E1): `docs/plans/` plus a
    400-character component; assert the result is a `str` and no exception; FAILS (raises) on the
    pre-fix module.

18. **SEC-7 (P2) — two containment tests pass for incidental reasons.** (a) In
    `test_reanchored_candidate_escaping_root_is_refused`, create the `elsewhere` directory tree so
    the source exists; keep the assertion. E2 mutation: delete the containment check on the
    re-anchored candidate; the test must FAIL (the escape target's `plan-ready` leaks in). (b) Extend
    `test_same_file_two_spellings_agree` with the absolute-versus-relative pair for an in-root file
    and for an out-of-root file (both spellings refused). E2 mutation: reintroduce a read of the
    original absolute path; the out-of-root pair disagrees and the test must FAIL.

19. **TEST-10 (P3) — `mkdtemp` and an unused fixture.** Delivered by item 1's rewrite. Acceptance:
    `grep -c "mkdtemp" tests/test_handoff_envelope_maturity.py` returns 0 and the rewritten test's
    signature takes `tmp_path` only.

20. **CORR-5 (P2) — the present-but-garbled handoff section is pinned by no test.** New test
    `test_unrecognized_handoff_section_requires_clarification` in the maturity module (it already
    loads `parse_issue.py`): a body whose `### Handoff maturity` section holds
    `unknown:carrier:requirements-ready` yields `maturity == ""`, `can_plan is False`,
    `requires_clarification is True`; a body with no section yields `requires_clarification is False`.
    E2 mutation: revert `parse_issue.py:86` to `maturity == "deferred-context"`; the test must FAIL.

21. **AU-3 (P2), test half — pin that a top-level flow mapping declares.** New test
    `test_top_level_flow_mapping_declares` : `---\n{maturity: requirements-ready, topic: x}\n---`
    returns `requirements-ready`. This is a documentation pin of behaviour the review called
    defensible; it passes on the live code and needs no mutation. Lane B fixes the four prose
    surfaces that say the opposite.

22. **SEC-9 (P3), test half — pin that `unknown:` cannot be forged.** New test
    `test_hand_written_unknown_prefix_is_wrapped_not_honoured`: a frontmatter declaring
    `maturity: unknown:out-of-root:x` yields `unknown:unrecognized:unknown:out-of-root:x` and no
    runnable command; likewise for `unknown:carrier:`. E2 mutation: make the classifier return a
    declared value verbatim when it starts with `unknown:`; the test must FAIL.

**Tests to run (scoped, every commit):**

```bash
uv run pytest tests/test_handoff_envelope_maturity.py tests/test_handoff_envelope.py \
  tests/test_saga_plugin.py tests/test_saga_saga.py tests/test_saga_docs_coverage.py -q
uv run python scripts/lint_test_shape.py
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

`tests/test_saga_plugin.py` and `tests/test_saga_saga.py` import the envelope module and pin the
version and vocabulary; they must stay green without being edited.

**Definition of done.** Every item above has its E1 red line or E2 mutation-fail line pasted in
`lane-A-evidence.md` together with the `RESTORED-BYTE-IDENTICAL` line; the AST count and the
coverage table are pasted; the scoped run is green; `git status --short` in the lane checkout shows
only owned paths; the journal draft carries at least one learning (the shape of the six-cycle
defect: the read-original arm was pinned by a test asserting the bypass) and the SEC-1 decision text
Lane B will need is cross-checked against KTD9.

**Commit message (one commit, or one per numbered group, each in this form):**

```
fix(saga): handoff envelope fails closed on every out-of-root, oversized, unparseable and injected source

Refuse any source resolving outside the declared root unless its in-root twin exists
(SEC-1); one resolver owns the decision and a spy test pins it (AM-3, TEST-2); the
carrier diagnostic names its cause (AU-2); the read window and an early --- fail closed
(CORR-6, CORR-7); RecursionError and OSError return sentinels (SEC-3, SEC-8); the
suggested command is shell-quoted and single-line (SEC-5); three unreachable branches
and the "should not occur" arm are gone and the module is decomposed (AM-5, AM-6,
AM-10); pins added for TEST-1, CORR-5, SEC-9, AU-3, SEC-7, AU-11, API-4 confirmed.

re #912 re #913
```

### U2. Lane B — the handoff contract's prose, the release note, the journal corrections, and the dialogue guard

**Lane statement.** Make every shipped sentence about handoff maturity true for the code Lane A ships,
scope the fail-closed claim honestly, repair the journal's three wrong lines, fix the residual
record's recommendation, and make the dialogue guard unbypassable and precise about where it fired.

**Owned paths (complete):**

- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/saga-spec.md`
- `plugins/saga/skills/handoff/SKILL.md`
- `plugins/saga/docs/state-readiness.md`
- `plugins/saga/references/brainstorm-evidence-model.md`
- `tests/test_brainstorm_evidence_model.py`
- `docs/engineering-journal/DECISIONS.md`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/evidence/issue-912/residuals-cycle-7.md`
- `docs/evidence/issue-912/lane-B-evidence.md` (new)

**Forbidden for Lane B:** `handoff_envelope.py` and its tests; every skill file other than
`handoff/SKILL.md`; the dispatch table; the docs model and renderer; the SVG assets; every other test
module. Tests that READ Lane B's files and must stay green unedited:
`tests/test_handoff_envelope_maturity.py` (vocabulary values and `schema_version "1.1"` in
`saga-spec.md`), `tests/test_saga_plugin.py:257-261` (four fixed phrases in `handoff/SKILL.md`),
`tests/test_saga_plugin.py:4023-4061` (`test_handoff_and_loop_skills_use_positive_routable_vocabulary_gate`,
the load-bearing consumer-contract pin: it requires `handoff/SKILL.md` to contain verbatim
"ONLY when `handoff_maturity` is one of the routable vocabulary values" (step 6), "NEVER a runnable
command" (step 6), "two fail-closed states" (the Maturity section), the five routable value names,
and the three shapes `pending-confirmation`, `unknown:`, `empty`), and
`:4113-4115` (vocabulary in the spec), `tests/test_saga_docs_coverage.py::test_state_readiness_table_matches_model`
(the table in `state-readiness.md`, which Lane B does not touch), `tests/test_saga_lifecycle_consistency.py`
(reads the spec), `tests/test_changelog_heading_lint.py`, `tests/test_release_triad.py`,
`tests/test_release_surface_parity.py`, `tests/test_lint_journal_order.py`, `tests/test_release_rituals.py`.

**Fix requests → findings → files.**

| Fix request | Findings | Files touched |
|---|---|---|
| `fix-e9b5ab8ede0f` | API-9; SEC-9 prose half (already satisfied, P3 preflight) | `CHANGELOG.md` |
| `fix-c953e1223ef6` (prose half) | AU-3 | `state-readiness.md`, `handoff/SKILL.md`, `saga-spec.md`, `CHANGELOG.md` |
| `fix-4f0a70c896a2` | API-6, API-12 | `saga-spec.md` |
| `fix-1f40ab804724` | DOC-11, DOC-8 | `LEARNINGS.md` |
| `fix-ce1de91aa297` | DOC-6 | `brainstorm-evidence-model.md`, `DECISIONS.md`, `LEARNINGS.md` |
| `fix-e738a4aa8d53` | AM-7 | `residuals-cycle-7.md` |
| `fix-aacbeb7871b4` | TEST-4, TEST-8 | `tests/test_brainstorm_evidence_model.py`, `brainstorm-evidence-model.md` |
| (from Lane A's SEC-1, KTD1/KTD9) | SEC-1 prose half; DOC-1 residue (P1 preflight) | `CHANGELOG.md`, `handoff/SKILL.md`, `saga-spec.md`, `DECISIONS.md` |

**Work items and acceptance evidence.** Prose acceptance is a grep whose count is pasted, plus the
named binding tests green.

1. **SEC-1 prose and the DOC-1 residue — the containment story, told once and truthfully.**
   Rewrite, using KTD9's sentence: `CHANGELOG.md` bullets 2 and 4 of the 0.156.0 entry (bullet 4's
   reference to `test_reanchored_missing_fallback_to_original` becomes
   `test_reanchored_missing_twin_is_refused`); `handoff/SKILL.md` "Maturity" paragraph (line 90); and
   `saga-spec.md` §4 sentence at lines 322-323. In `handoff/SKILL.md` step 6 (line 84) the only
   change is adding `out-of-root` to the parenthetical list of `unknown:` causes; every phrase
   `tests/test_saga_plugin.py:4023-4061` pins (listed above under "must stay green") stays verbatim
   in step 6 and in the Maturity section, neither dropped nor re-cased, while the containment
   sentences around them are rewritten from KTD9. In `DECISIONS.md`: add a new entry under a new `## 2026-09-05` heading,
   `{#912-out-of-root-refused-outright}`, recording the reversal with the reason from KTD1
   (the rejected option's stated downside no longer exists), what is given up, and a "revisit when"
   (a legitimate cross-worktree handoff appears that cannot name an in-root path); and amend the
   `{#913-maturity-unknown-sentinel}` entry's "Why" and "Rejected" clauses with one sentence each
   pointing at the new anchor. Acceptance greps (each pasted):
   `grep -c "can route live" plugins/saga/CHANGELOG.md` → 0 within lines 3-12;
   `grep -c "original absolute file is read" plugins/saga/CHANGELOG.md docs/engineering-journal/DECISIONS.md` → 0;
   `grep -c "is read only when its path carries a marker directory" plugins/saga/skills/handoff/SKILL.md` → 0;
   `grep -c "that declaration is honoured" plugins/saga/skills/handoff/SKILL.md` → 0;
   `grep -c "reanchored_missing_fallback_to_original" plugins/saga/CHANGELOG.md` → 0;
   `uv run python scripts/lint_journal_order.py --base-ref origin/main` exits 0.

2. **API-9 (P2) — scope the fail-closed claim.** Add to the 0.156.0 entry one sentence: "This
   contract is saga's reader's. Mission Control's `issue --prepare` path infers maturity from the
   artifact path alone and does not apply it; that gap is tracked as issue 950." Acceptance:
   `sed -n '3,12p' plugins/saga/CHANGELOG.md | grep -c "950"` → 1.

3. **SEC-9 (P3), prose half — already satisfied.** `DECISIONS.md:7` lists five causes at HEAD.
   Acceptance: `grep -c "unknown:out-of-root" docs/engineering-journal/DECISIONS.md` ≥ 1, pasted.
   No edit.

4. **AU-3 (P2), prose half — a top-level flow mapping declares.** In `state-readiness.md:3`,
   `handoff/SKILL.md:90`, `saga-spec.md:314-316`, and CHANGELOG bullet 3, replace the flat "a
   flow-style `{maturity: ...}`" with "a flow-style mapping nested under another key", and add that a
   flow-style mapping that IS the whole top-level mapping declares like any top-level key.
   Acceptance: `grep -rn "flow-style" plugins/saga/docs/state-readiness.md plugins/saga/skills/handoff/SKILL.md plugins/saga/references/saga-spec.md plugins/saga/CHANGELOG.md`
   shows every hit qualified by "nested" or "top-level", pasted; Lane A's
   `test_top_level_flow_mapping_declares` is the behavioural anchor.

5. **API-6 (P2) — §9 lists four causes.** Add `unknown:out-of-root:<path>` to the §9 field-contract
   enumeration at `saga-spec.md:509-513`. Acceptance: `awk '/^## 9/,/^## 10/' plugins/saga/references/saga-spec.md | grep -c "out-of-root"` → ≥ 1.

6. **API-12 (P3) — the ungrammatical rule.** `saga-spec.md:312-313`: "must be an / the top-level"
   becomes "must be the top-level". Acceptance: `grep -c "must be an$" plugins/saga/references/saga-spec.md` → 0.
   Also fix the sentence at 317-318 ("beyond those windows the path rule applies") to match KTD7:
   beyond the window the source fails closed as `unknown:unterminated:`.

7. **DOC-11 (P3).** `LEARNINGS.md:83` (the review's line 57, before cycle 8 added 26 lines): `## [0.151.0]` → `## [0.156.0]`. Acceptance:
   `grep -c "retitled this branch's CHANGELOG entry to \`## \[0.156.0\]\`" docs/engineering-journal/LEARNINGS.md` → 1.

8. **DOC-8 (P2) — the bare heading.** Restore the six-field body under the retitled heading at
   `LEARNINGS.md:162` (the review's line 136) from the merge base: `git show f30d8678:docs/engineering-journal/LEARNINGS.md`
   lines 149-154 carry Context, Evidence, Mechanism, Fix, Generalizable rule, Refs for the same
   anchor (line 147 is the old heading and is not copied; the current heading at HEAD
   `LEARNINGS.md:162` stays). Adapt the Fix line to the new title (the counts were deleted, not
   refreshed). Acceptance:
   `awk '/916-dispatch-line-count-no-target/,/^### /' docs/engineering-journal/LEARNINGS.md | grep -c '^\*\*'` → 6.

9. **DOC-6 (P2) — the renamed key.** `brainstorm-evidence-model.md:54` and `:63`: `expected` per
   dimension → `authored_verdicts`; document the `grading_status` key that
   `tests/test_brainstorm_scenarios.py:322-323` pins. `DECISIONS.md:195` and `LEARNINGS.md:219` (the review's line 193):
   append "(the key was renamed `authored_verdicts` on this branch)". Acceptance:
   `grep -c "authored_verdicts" plugins/saga/references/brainstorm-evidence-model.md` → ≥ 2 and
   `grep -c "grading_status"` → ≥ 1; the two journal lines carry the parenthetical.

10. **AM-7 (P2) — the residual's next step is a ruled-out import.** Replace the "Recommended next
    step" paragraph of `residuals-cycle-7.md` in place, dated "corrected 2026-09-05": the route is the
    vendored fleet-commons shim (`plugins/fleet-core/scripts/fleet_commons/`, reached through each
    plugin's `fleet_commons_shim.py`, with the drift guard), moving `HANDOFF_MATURITIES`,
    `ROUTABLE_MATURITIES` and the path rule there; a direct import of `handoff_envelope.infer_maturity`
    from mission-control is ruled out by `{#marketplace-install-layout-no-import-path}` per
    `plugins/saga/references/dispatch-adapter-contract.md:48-54`. Acceptance:
    `grep -c "fleet_commons" docs/evidence/issue-912/residuals-cycle-7.md` → ≥ 1 and the paragraph
    names the ruling-out anchor.

11. **TEST-4 (P2) and TEST-8 (P3) — the dialogue guard.** Refactor
    `test_no_dialogue_assertions_negative_load_bearing` so the scan is a pure function
    `find_dialogue_assertions(paths: Iterable[Path]) -> list[str]` that parses each module
    separately, scopes the `_INTERROGATIVES` and `_is_question_shaped` exemptions to the guard's own
    module path, and reports `"<path>:<line>: ..."` with the real file and line. The real test calls
    it on the glob. Three seeded tests on `tmp_path` copies (never on other lanes' files): a control
    (a question-shaped constant in a synthetic module → flagged with that file and line), an escape
    (`_INTERROGATIVES = ("What …?", "How …?")` in a synthetic module not named like the guard →
    flagged), and a self-exemption (the same tuple in a synthetic module whose path matches the
    guard's own filename → not flagged). E2 mutation: restore the unscoped name-based exemption; the
    escape test must FAIL. Update `brainstorm-evidence-model.md`'s description of the exclusion to
    match. Acceptance: the three seeded tests green, the mutation red line pasted.

**Tests to run (scoped, every commit):**

```bash
uv run pytest tests/test_brainstorm_evidence_model.py tests/test_saga_plugin.py \
  tests/test_handoff_envelope_maturity.py tests/test_saga_docs_coverage.py \
  tests/test_saga_lifecycle_consistency.py tests/test_lint_journal_order.py \
  tests/test_release_triad.py tests/test_release_surface_parity.py \
  tests/test_changelog_heading_lint.py tests/test_release_rituals.py \
  tests/test_manifest_consumer_matrix.py tests/test_workflow_extraction.py \
  tests/test_saga_plan_save_and_routing.py tests/test_brainstorm_scenarios.py -q
uv run python scripts/lint_journal_order.py --base-ref origin/main
uv run python scripts/lint_test_shape.py
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Note: `tests/test_handoff_envelope_maturity.py` in Lane B's checkout is the pre-Lane-A version; it
must stay green against Lane B's spec edits (it checks vocabulary presence and the `"1.1"` string).

**Definition of done.** Every grep above pasted with its count; the journal lint exit code pasted;
the scoped run green; `git status --short` shows only owned paths; the SEC-1 prose is written from
KTD9 and names the new test name from U1 item 1.

**Commit message:**

```
docs(saga): tell the containment story once and truthfully; scope the fail-closed claim; repair the journal and the dialogue guard

Release note, handoff skill, spec section 4 and section 9, and the decision record now
describe refuse-all containment (SEC-1, DOC-1 residue, API-6, API-12, AU-3); the note
scopes the claim to saga's reader and names issue 950 (API-9); LEARNINGS regains the
six-field body and the right version (DOC-8, DOC-11); the evidence-model reference names
authored_verdicts and grading_status (DOC-6); the residual record recommends the
fleet-commons route (AM-7); the dialogue guard parses per file and cannot be bypassed by
a renamed constant (TEST-4, TEST-8).

re #912 re #913 re #915
```

### U3. Lane C — routing prose, the test guards that pin it, and the docs model and renderer

**Lane statement.** Make `/loop`, `/resume` and `/brainstorm` send an agent to one place for every
maturity the code can produce, make the four guards that pin that prose falsifiable, and make the
readiness ladder readable and honest.

**Owned paths (complete):**

- `plugins/saga/skills/loop/references/dispatch-table.md`
- `plugins/saga/skills/loop/references/drive-and-resume.md` (AU-8 only: two "`/resume` stub" lines)
- `plugins/saga/skills/loop/SKILL.md`
- `plugins/saga/skills/resume/SKILL.md`
- `plugins/saga/skills/brainstorm/SKILL.md`
- `tests/test_brainstorm_continuity_contract.py`
- `tests/test_brainstorm_judgment_contract.py`
- `tests/test_saga_lifecycle_consistency.py`
- `tests/test_saga_docs_coverage.py`
- `plugins/saga/docs/model/saga-docs-model.yaml`
- `plugins/saga/docs/model/README.md`
- `plugins/saga/scripts/render_docs_visuals.py`
- `plugins/saga/docs/assets/state-readiness-ladder.svg`
- `plugins/saga/docs/assets/command-matrix.svg`
- `plugins/saga/docs/assets/lifecycle-atlas.svg`
- `plugins/saga/docs/assets/ownership-boundary-map.svg`
- `docs/evidence/issue-912/lane-C-evidence.md` (new)
- `docs/evidence/issue-912/lane-C-journal-draft.md` (new)

**Forbidden for Lane C:** `handoff_envelope.py`, `parse_issue.py`, their tests; `handoff/SKILL.md`,
`state-readiness.md` (the table there matches the model and Lane C does not change model data),
`saga-spec.md`, `CHANGELOG.md`, the journal, `tests/test_brainstorm_evidence_model.py`. Tests that
READ Lane C's files and must stay green unedited: `tests/test_saga_plugin.py:870-880`,
`:4013-4017` (three exact dispatch rows), and `:4023-4061`
(`test_handoff_and_loop_skills_use_positive_routable_vocabulary_gate`, which requires
`loop/SKILL.md` to contain verbatim "ONLY when the maturity is one of the routable vocabulary
values" and "never a runnable command" at 4.2, "`unknown:`-prefixed", and the two 0.2 phrases
"empty -> the issue carries no recognized handoff metadata" and "continue to the saga scan" at
line 119; AU-4 is therefore additive, see item 3), `tests/test_saga_plan_save_and_routing.py` (dispatch
table), `tests/test_brainstorm_predicate_wiring.py` and `tests/test_brainstorm_dialogue_ownership.py`
(brainstorm skill), `tests/test_lint_gate_absence_contract.py` (loop and brainstorm skills; the
gate-absence lint is section-scoped, so no new `AskUserQuestion` mention may land in a section
without a `gate-record` or `gate-exempt` marker), `tests/test_sandbox_spawn_sites.py`,
`tests/test_review_publication_lane.py` (docs model), `tests/test_brainstorm_evidence_model.py`
(scans every `tests/test_brainstorm_*.py`; after Lane B lands it also refuses a renamed
`_INTERROGATIVES`).

**Fix requests → findings → files.**

| Fix request | Findings | Files touched |
|---|---|---|
| `fix-cbddcf8b9683` | AU-7, AU-8 | `dispatch-table.md`, `test_brainstorm_continuity_contract.py` |
| `fix-351473c97c09` | AU-4 | `loop/SKILL.md`, `test_brainstorm_continuity_contract.py` |
| `fix-6eb95fb43577` | AU-6 | `resume/SKILL.md`, `test_brainstorm_continuity_contract.py` |
| `fix-5b524f3e3145` | AU-5, AU-10 | `brainstorm/SKILL.md`, `resume/SKILL.md`, `test_brainstorm_continuity_contract.py` |
| `fix-1ccb8d5f395c` | TEST-3, TEST-9 | `test_brainstorm_continuity_contract.py`, `dispatch-table.md`, `test_brainstorm_judgment_contract.py` |
| `fix-fa193a7777a8` | TEST-7 | `test_saga_lifecycle_consistency.py` |
| `fix-2851f8c208bc` | TEST-6 | `test_saga_docs_coverage.py`, `saga-docs-model.yaml` |
| `fix-1c98d161ef41` | AM-8 | `saga-docs-model.yaml` |
| `fix-e77b6847f5e5` | AM-9, CORR-9, DOC-12 | `render_docs_visuals.py`, the four SVGs, `test_saga_docs_coverage.py` |

**Work items and acceptance evidence.** Every prose change is pinned by a `check_<rule>(text)`
predicate in the continuity module, run on the real file (expect `[]`) and on a mutated copy (expect
non-empty), the repository's established shape.

1. **AU-7 (P2) — `deferred-context` has no dispatch row.** Add to the main-chain table:
   `| (none) | — | \`deferred-context\` | ask the operator the clarifying question the issue names (\`/loop\` 0.2); dispatch nothing until answered |`.
   New `check_dispatch_deferred_context(text)` asserting exactly one such row whose command cell
   contains "clarifying question"; mutation (row deleted) → non-empty. The three exact rows
   `tests/test_saga_plugin.py:4014-4017` pins are untouched.

2. **AU-8 (P2) — `/resume` is labelled a stub.** In `dispatch-table.md`: row 36: `**stub**` →
   `shipped (forensic reconstruction engine)`; line 108: `advisory stub, never auto` → `advisory,
   opt-in only`. The advisory rule paragraph (17-19) is left as the rule for any target whose State
   cell still says stub. In `loop/SKILL.md`, which reads that table and still calls `/resume` a stub
   on a file Lane C owns: at lines 66-67 remove `/resume` and `/retro` (shipped, table row 35) from
   the stub-targets list, so the sentence reads that routes to any target whose State cell in
   `references/dispatch-table.md` still says stub are advisory and never block `/loop`, and that
   `/retro`, `/resume`, `/strategy` and `/optimize` are advisory by their own rows, not by being
   stubs; at lines 247-249 replace "the `/resume` stub" with "`/resume`" (keep "**Never**
   auto-route") and replace the parenthetical "`/resume` is a stub today; routing to it is advisory
   and never blocks `/loop`" with "routing to `/resume` is advisory and opt-in and never blocks
   `/loop`". In `loop/references/drive-and-resume.md` (owned by Lane C for this item), lines 137 and
   142 make the same "the `/resume` stub" → "`/resume`" replacement, keeping the never-auto-route
   rule. Acceptance, each pasted:
   `grep -n "stub" plugins/saga/skills/loop/references/dispatch-table.md plugins/saga/skills/loop/SKILL.md plugins/saga/skills/loop/references/drive-and-resume.md`
   shows no line naming `/resume` or `/retro`; `tests/test_saga_plugin.py:870-880` (which reads the
   loop corpus for `saga.py scan` and the save blocks) stays green.

3. **AU-4 (P2) — no route for a present-but-unrecognized declaration.** `loop/SKILL.md` 0.2 is
   **additive**. The existing "empty" bullet at line 119 is kept verbatim, because
   `tests/test_saga_plugin.py:4057-4058` pins both `empty -> the issue carries no recognized
   handoff metadata` and `continue to the saga scan`, and Lane C may not edit that test. Do not
   rephrase, re-case, or split that bullet. Add a new bullet directly after it: "empty with
   `handoff.requires_clarification` True -> the Handoff maturity section is present but its value
   is unrecognized (including any `unknown:` sentinel); STOP, show the declared value, and have the
   issue's handoff section fixed; never continue to the saga scan on it." The new bullet's opening
   words make the existing bullet the `requires_clarification` False case without touching it. New
   `check_loop_unrecognized_declaration_stops(text)` in the continuity module asserting the new
   bullet's "never continue to the saga scan on it" clause and that the pinned line-119 phrase is
   still present; mutation (new bullet removed) → non-empty.

4. **AU-6 (P2) — legacy artifacts have no run class.** `resume/SKILL.md:120`: matched-brainstorm
   is "exactly one tier 1 match (exact, or a near-match the operator confirmed), or, when tier 1
   produced none, exactly one tier 2 candidate the labelled inference path qualified". Extend
   `check_matched_brainstorm` to require the tier 2 clause; mutation → non-empty.

5. **AU-5 (P2) — a declined Path B artifact has no way back.** `brainstorm/SKILL.md` Phase 4 option 5:
   "If the artifact on disk is at `maturity: pending-confirmation`, whether never confirmed or
   declined, or the refinement changed the boundary of an already-confirmed artifact, re-enter Phase
   2.5 for fresh confirmation before returning here." New `check_declined_artifact_reenters_confirmation(text)`;
   mutation → non-empty. The Phase 4 section already carries its `gate-record` marker; add no
   `AskUserQuestion` mention outside it.

6. **AU-10 (P3) — reordered topics fall to tier 3; a clause is duplicated.** `brainstorm/SKILL.md:81`:
   define the near-match as same `capability` and either a strict subset relation between the two
   token sets in either direction, or equal token sets whose slug strings differ (a reordered topic);
   delete the second copy of "and the two are not equal, equality being the exact match handled
   above". Mirror the reorder arm in `resume/SKILL.md:108`. Extend `check_near_match_predicate` with
   the reorder clause and a duplicate-clause check (the phrase appears at most once); mutation →
   non-empty. `test_near_match_multiplicity_rule_mirrored_in_resume` stays green.

7. **TEST-3 (P2) — the guard was narrowed to table rows.** Restore `check_no_pending_to_plan` to
   every line. Split `dispatch-table.md:93` into two sentences on separate lines so that
   `pending-confirmation` and `/plan` no longer share a line (the `/plan` sentence about
   `can_plan`/`can_work`, then the `pending-confirmation` sentence routing to `/brainstorm`). Add the
   seeded negative: the review's sentence "When the handoff maturity is `pending-confirmation`, route
   straight to `/plan`." appended to a copy → non-empty. E2 mutation: re-add the `startswith("|")`
   qualifier → the seeded negative must FAIL.

8. **TEST-9 (P3) — a dead disjunction.** `check_checkpoint`: keep only the case-insensitive
   condition. In `tests/test_brainstorm_judgment_contract.py:385` and `:408`, keep only the
   count-specific assertion (`"2 passed" in result.stdout`, `"1 passed" in result.stdout`); the
   `or "passed"` operand is deleted. Acceptance: `grep -c 'or "passed" in' tests/test_brainstorm_judgment_contract.py` → 0;
   the seeded-inversion control in the continuity module still fires.

9. **TEST-7 (P3) — the ordering clause is unfalsifiable.** Add a seeded negative to
   `tests/test_saga_lifecycle_consistency.py`: a synthetic text carrying all three markers with
   `/plan` before `/brainstorm` → `_has_block_shape` returns False. E2 mutation: replace the body with
   an unordered all-present check → the seeded test must FAIL.

10. **TEST-6 (P2) and AM-8 (P2) — `read_by` graded against a literal; the comment is false.**
    `saga-docs-model.yaml:48-50`: replace the comment with "read_by lists only readers that have been
    inventoried; absence means not yet inventoried, not no reader (see README.md)". In
    `test_saga_docs_coverage.py::test_readiness_is_derived_not_stored`, replace the literal-set
    assertion with a derivation: every entry in `read_by` names a skill whose
    `plugins/saga/skills/<name>/SKILL.md` contains `pending-confirmation`, and the comment block does
    not contain "has no readers". E2 mutation: add `/qa` to a `tmp_path` copy of the model → the
    derivation must FAIL. `README.md` is unchanged unless the worker finds it inconsistent.

11. **AM-9 (P3) — `globals()` lookup.** `render_docs_visuals.py:250`: rename the local
    (`ladder_rows = maturity_rows(model)`); no `globals()`. Acceptance:
    `grep -c "globals()" plugins/saga/scripts/render_docs_visuals.py` → 0; ruff and mypy green; the
    four SVGs regenerate byte-identical from this change alone (`git status --short` shows no asset
    change before item 12).

12. **CORR-9 (P3) — the source column overruns.** Draw the source label within the column budget
    (the maturity label's x, 1115, minus the source x, 830, minus padding), by wrapping onto a second
    `<text>` line inside the 62px row (preferred), a narrower face, or moved column origins. New
    test `test_ladder_source_labels_fit_their_column` in `test_saga_docs_coverage.py` computing the
    budget from the renderer's own calibration (`max_chars=46` in 490px, about 10.6px per character)
    and asserting every rendered source line fits (E1: the 50-character `pending-confirmation` source
    fails on the pre-fix renderer). If wrapping splits the string,
    `test_ladder_renderer_rows_equal_model_maturity_values` (271-275) is adjusted to assert each
    fragment. Regenerate: `uv run python plugins/saga/scripts/render_docs_visuals.py`;
    `test_generated_visual_assets_match_model` green.

13. **DOC-12 (P3) — the caption contradicts the sentence above it.** `render_docs_visuals.py:264`:
    "never stored in saga frontmatter" → "never stored as saga tick frontmatter". New assertion in
    `test_saga_docs_coverage.py`: the rendered ladder contains the new phrase and not the old (E1).
    Regenerate assets.

**Tests to run (scoped, every commit):**

```bash
uv run pytest tests/test_brainstorm_continuity_contract.py tests/test_brainstorm_judgment_contract.py \
  tests/test_brainstorm_predicate_wiring.py tests/test_brainstorm_dialogue_ownership.py \
  tests/test_brainstorm_evidence_model.py tests/test_brainstorm_scenarios.py \
  tests/test_saga_lifecycle_consistency.py tests/test_saga_docs_coverage.py \
  tests/test_saga_plugin.py tests/test_saga_plan_save_and_routing.py \
  tests/test_lint_gate_absence_contract.py tests/test_sandbox_spawn_sites.py \
  tests/test_review_publication_lane.py -q
uv run python plugins/saga/scripts/lint_gate_absence_contract.py
uv run python scripts/lint_test_shape.py
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

**Definition of done.** Each predicate's real-file `[]` and mutated-copy non-empty results pasted;
the two E2 mutation red lines (TEST-3, TEST-7) and the E1 red lines (CORR-9, DOC-12) pasted; the
`globals()` and `stub` greps pasted; assets regenerated and `test_generated_visual_assets_match_model`
green; `git status --short` shows only owned paths.

**Commit message:**

```
fix(saga): one route per maturity in /loop, /resume and /brainstorm; falsifiable guards; a readable readiness ladder

dispatch-table gains the deferred-context row and stops calling /resume a stub (AU-7,
AU-8); /loop stops on a present-but-unrecognized declaration (AU-4); Resume gives
legacy artifacts a run class (AU-6); a declined boundary can re-enter confirmation and
a reordered topic is a near-match (AU-5, AU-10); the pending-to-plan guard scans every
line again, the dead disjunctions are gone, and the block-shape ordering has a seeded
negative (TEST-3, TEST-9, TEST-7); read_by is derived, not asserted (TEST-6, AM-8); the
ladder renderer drops globals(), wraps its source column and corrects its caption
(AM-9, CORR-9, DOC-12).

re #912 re #914 re #916
```

### U4. Integration — serial, in the order A, B, C, then the journal fold

**Owner:** the controller (integrator), one step at a time, on `repair/cp912-review-cycle-1`.

**Step 1 — integrate Lane A.** Merge (or cherry-pick) Lane A's commit(s). Run Lane A's scoped list.
Run the full gate in a detached worktree at the resulting commit:

```bash
git worktree add --detach "$SCRATCH/gate-A" HEAD
( cd "$SCRATCH/gate-A" && GATE_LOG_DIR="$SCRATCH/gate-A-logs" bash scripts/gate.sh > "$SCRATCH/gate-A.log" 2>&1 & )
# later: cat "$SCRATCH/gate-A-logs/result.txt"   # absent = still running, never green
# expect 25 step headers in the log: 21 blocking + 4 advisory (KTD10)
```

Why first: Lane A defines the behaviour. Prose that lands before it cannot be checked against
anything.

**Step 2 — integrate Lane B.** Merge. Then the cross-lane truth checks, each count pasted into
`docs/evidence/issue-912/integration-log.md` (new, integrator-owned):

```bash
grep -c "can route live" plugins/saga/CHANGELOG.md                                       # expect 0 in the 0.156.0 entry
grep -c "original absolute file is read" plugins/saga/CHANGELOG.md docs/engineering-journal/DECISIONS.md plugins/saga/scripts/handoff_envelope.py   # expect 0
grep -c "test_reanchored_missing_twin_is_refused" plugins/saga/CHANGELOG.md tests/test_handoff_envelope_maturity.py   # expect 1 and 1
grep -c "reanchored_missing_fallback_to_original" plugins/saga/CHANGELOG.md tests/test_handoff_envelope_maturity.py   # expect 0 and 0
awk '/^## 9/,/^## 10/' plugins/saga/references/saga-spec.md | grep -c "out-of-root"     # expect >= 1
uv run pytest tests/test_handoff_envelope_maturity.py tests/test_brainstorm_evidence_model.py -q
uv run python scripts/lint_journal_order.py --base-ref origin/main
```

Full gate in a fresh detached worktree. Why second: Lane B's dialogue guard now scans Lane C's
test files; landing it before C means C's integration run is where a C-authored violation shows.

**Step 3 — integrate Lane C.** Merge. Run Lane C's scoped list plus
`uv run pytest tests/test_brainstorm_evidence_model.py -q` (Lane B's guard over Lane C's files) and
`uv run python plugins/saga/scripts/lint_gate_absence_contract.py`. Full gate in a fresh detached
worktree.

**Step 4 — journal fold.** Move the entries from `lane-A-journal-draft.md` and
`lane-C-journal-draft.md` into the `## 2026-09-05` sections Lane B created in `LEARNINGS.md` and
`DECISIONS.md`; delete both draft files; commit as
`docs(journal): fold the lane A and lane C learnings from the issue 912 repair round` with `re #912`.
Run `uv run python scripts/lint_journal_order.py --base-ref origin/main` and the full gate one last
time. Record the final `result.txt` verbatim, the step-header count (25: 21 blocking plus 4
advisory), and the final commit hash in
`integration-log.md`.

**Step 5 — custody check.** `shasum -a 256 docs/plans/2026-08-30-agent-launcher-907-run-plan.md`
equals `f695be329f00597156b7c085d17885403a3b52b6b5afa1244f91524a694aac84`; `git status --short`
shows only that untracked file; no path under `plugins/mission-control/` or `plugins/orchestrate/`
appears in `git diff --stat 77c01c99 HEAD`; `origin/main` was not merged (`git log --oneline
77c01c99..HEAD` contains no merge commit).

## Disposition of every open finding

Status vocabulary: **repair** (work item exists), **confirm** (already satisfied on the live tree;
the lane proves it by mutation or grep and adds nothing unless the proof fails), **split** (two
lanes, halves named).

| # | Finding | P | Lane | Status | Where |
|---|---|---|---|---|---|
| 1 | SEC-1 | P1 | A + B | split: code A (U1 item 1), prose B (U2 item 1) | KTD1, KTD9 |
| 2 | TEST-1 | P1 | A | repair | U1 item 2 |
| 3 | TEST-2 | P1 | A | repair | U1 item 3 |
| 4 | AU-2 | P1 | A | repair | U1 item 4 |
| 5 | AM-3 | P2 | A | repair | U1 items 3, 5 |
| 6 | AM-4 | P2 | A | repair (cycle 8 fixed the two quoted sentences; the "three outcomes" block remains) | U1 items 1, 6 |
| 7 | AM-5 | P2 | A | repair | U1 item 7 |
| 8 | AM-6 | P2 | A | repair | U1 item 8 |
| 9 | AM-10 | P3 | A | repair | U1 item 9 |
| 10 | API-4 | P2 | A | confirm (cycle-8 test appears to pin it; mutation decides) | U1 item 10, preflight P2 |
| 11 | API-11 | P3 | A | repair | U1 item 11 |
| 12 | AU-11 | P2 | A | repair | U1 item 12 |
| 13 | CORR-6 | P2 | A | repair | U1 item 13, KTD7 |
| 14 | CORR-7 | P2 | A | repair | U1 item 14, KTD7 |
| 15 | SEC-3 | P2 | A | repair | U1 item 15 |
| 16 | SEC-5 | P2 | A | repair | U1 item 16, KTD8 |
| 17 | SEC-8 | P3 | A | repair | U1 item 17 |
| 18 | SEC-7 | P2 | A | repair | U1 item 18 |
| 19 | TEST-10 | P3 | A | repair | U1 item 19 |
| 20 | CORR-5 | P2 | A | repair | U1 item 20 |
| 21 | AU-3 | P2 | A + B | split: pin test A (U1 item 21), four prose surfaces B (U2 item 4) | — |
| 22 | SEC-9 | P3 | A + B | split: forgery test A (U1 item 22); decision-record half confirm, already satisfied (U2 item 3) | preflight P3 |
| 23 | API-9 | P2 | B | repair | U2 item 2 |
| 24 | API-6 | P2 | B | repair | U2 item 5 |
| 25 | API-12 | P3 | B | repair | U2 item 6 |
| 26 | DOC-11 | P3 | B | repair | U2 item 7 |
| 27 | DOC-8 | P2 | B | repair | U2 item 8 |
| 28 | DOC-6 | P2 | B | repair | U2 item 9 |
| 29 | AM-7 | P2 | B | repair | U2 item 10 |
| 30 | TEST-4 | P2 | B | repair | U2 item 11 |
| 31 | TEST-8 | P3 | B | repair | U2 item 11 |
| 32 | AU-7 | P2 | C | repair | U3 item 1 |
| 33 | AU-8 | P2 | C | repair | U3 item 2 |
| 34 | AU-4 | P2 | C | repair | U3 item 3 |
| 35 | AU-6 | P2 | C | repair | U3 item 4 |
| 36 | AU-5 | P2 | C | repair | U3 item 5 |
| 37 | AU-10 | P3 | C | repair | U3 item 6 |
| 38 | TEST-3 | P2 | C | repair | U3 item 7 |
| 39 | TEST-9 | P3 | C | repair (including the two pre-existing sibling lines the finding names) | U3 item 8 |
| 40 | TEST-7 | P3 | C | repair | U3 item 9 |
| 41 | TEST-6 | P2 | C | repair | U3 item 10 |
| 42 | AM-8 | P2 | C | repair | U3 item 10 |
| 43 | AM-9 | P3 | C | repair | U3 item 11 |
| 44 | CORR-9 | P3 | C | repair | U3 item 12 |
| 45 | DOC-12 | P3 | C | repair | U3 item 13 |

Closed before this round and not re-planned: SEC-2, SEC-4, AM-1, DOC-1, AM-2, CORR-1. Of these,
**DOC-1's named line is still false** (preflight P1) and is repaired inside Lane B's SEC-1 prose
work; the other five were checked at HEAD and hold.

No finding is judged wrong or unrepairable. Two are judged already satisfied (API-4, SEC-9's
decision-record half) and are confirmed rather than re-done.

## Integration order and why

**A, then B, then C, then the fold.**

- **A first.** Lane A is the source of truth for what the envelope does. Lane B's sentences and Lane
  C's dispatch rows describe or route on that behaviour, so nothing prose-side can be checked before
  the code lands. Lane A is also the constrained lane with the most work; landing it first means the
  longest wait is at the front, not in the middle.
- **B before C.** Lane B tightens the dialogue guard that scans every `tests/test_brainstorm_*.py`,
  and Lane C edits two of those modules. With B in place first, a question-shaped constant Lane C
  added is caught at Lane C's own integration run, where Lane C's author fixes it in Lane C's own
  file. In the other order the failure would surface at Lane B's integration and need a cross-lane
  edit.
- **The fold last.** Only after all three lanes are in can the journal carry every lane's entries
  under one `## 2026-09-05` heading without a merge conflict at the top of the file.

Concurrency is safe because no path appears in two lanes; the coupling that remains (Lane B's guard
over Lane C's tests, Lane B's prose over Lane A's behaviour, `tests/test_saga_plugin.py` reading
files from all three lanes) is checked at integration by the greps and scoped runs in U4, not by
trust.

## Stop-and-surface items

1. **SEC-1 reverses a recorded decision.** KTD1 commits to refusing every out-of-root source. The
   cycle-8 disposition called this "an open question, not a settled one". The plan settles it on the
   evidence that the rejected option's stated downside no longer exists. If the operator wants the
   read-original arm kept, veto before dispatch: Lane A's item 1 becomes "make both spellings agree
   by honouring the declaration", Lane B keeps the four-row table, and SEC-1 is disposed as
   "consistency repaired, containment design retained" with the security lens's objection recorded.
   Both lanes must know before they start, because they write the same sentence.
2. **DOC-1 is listed as closed but its named line is still wrong** (preflight P1). The plan repairs
   it under Lane B. The brief's "closed and proven" list is wrong on this one item.
3. **API-4 is probably already pinned** (preflight P2). Lane A proves it by mutation. No new test
   unless the mutation survives.
4. **Version-collision watch.** The branch is at saga `0.156.0`; `origin/main` at `0.155.0`. If
   issue 918 lands carrying `0.156.0` before this branch is frozen, all eight version surfaces must
   re-bump (the list is in `LEARNINGS.md` `{#saga-version-taken-by-concurrent-run}`, line 83, corrected by DOC-11). Not a lane's job.
5. **The full gate cannot run green in the primary checkout** (preflight P5): the untracked 907 plan
   fails the plan-conformance test. Every gate run in U4 is in a detached worktree. This plan file
   was checked against the conformance contract before delivery.
6. **No sixth sentinel.** KTD4 fixes AU-2 without growing the vocabulary. If the operator prefers
   distinct sentinels for the carrier sub-causes, that is a contract change touching six prose
   surfaces and the consumer contract, and it is not in this plan.
7. **An evidence file is edited in place** (AM-7, `residuals-cycle-7.md`). It is not
   content-addressed and is not in the ledger; cycle 8 edited the decision record the same way. If
   the operator wants evidence files immutable, Lane B instead adds
   `docs/evidence/issue-912/residuals-cycle-7-correction.md` and links it.
8. **Journal timing deviates by three commits** (KTD6). Lanes A and C cannot write the journal
   without breaking disjointness, so their entries land in the fold commit inside the same branch.
9. **`tests/test_saga_plugin.py` is edited by nobody and read by everybody.** Its version pin,
   its three exact dispatch rows, its four handoff-skill phrases, its routable-vocabulary gate at
   lines 4023-4061 (which pins step 6 of the handoff skill and lines 119 and 370 of the loop
   skill verbatim), and its vocabulary drift guard all stay green by construction of the lanes:
   Lane B changes step 6 only by adding `out-of-root` to its parenthetical, and Lane C's AU-4 is
   additive. If any lane finds it must change, that is a plan defect:
   stop and surface, do not edit it.

10. **One more "`/resume` stub" mention lives outside every lane.**
    `plugins/saga/skills/work/references/pr-continuation-loop.md:145` says the mechanism "does not
    depend on the `/resume` stub being rebuilt". It is a `/work` reference, no lane owns it, and no
    test pins it. It is not part of AU-8's named surfaces and is left for a later pass; it is
    recorded here so nobody reads its survival as an oversight.

## Verification (run-level)

- All three lanes' evidence notes exist and every E1/E2 line and grep count is pasted, not
  described.
- `integration-log.md` records four `result.txt` reads (after A, after B, after C, after the fold),
  each `GATE GREEN` with the step-header count (25: 21 blocking plus 4 advisory), and the final
  commit hash.
- The disposition table above has 45 rows and every row's "Where" resolves to a work item that has
  evidence in a lane note.
- Custody (U4 step 5) holds: the 907 plan hash is unchanged, no forbidden path changed, `origin/main`
  was not merged, and no commit message carries a closing keyword or an attribution trailer.
- The next step after this plan is not a merge. It is a fresh `review_result.v1` bound to the fold
  commit; the branch is not accepted until that result says so.
