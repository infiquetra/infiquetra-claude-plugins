# Issue 912 Code Review — ship disposition after cycle 8

**Status: NOT ACCEPTED. Issues #912–#916 and their board cards stay open.**

The last serialized `review_result.v1` (evidence ledger seq 17, bound to revision
`1bcee0a940a2bc3c4409a3c706d2c34afbc78581`) returned `outcome: repairs_requested` with
`next_action: dispatch_repairs`, 51 findings (10 P1, 27 P2, 14 P3) and 22 open fix requests. No
lens reached the acceptance threshold; the seven lens scores ranged from 4.0 to 7.12. Cycle 8 was
scoped by operator decision to a named subset of that result and did not attempt the rest, so the
acceptance gate is still unsatisfied and nothing here re-closes an issue.

## What cycle 8 was authorised to do

The operator chose a scoped cycle: fix only the two P1 defects that cycle 7's own repairs
introduced, plus the false claims in the release note, and then record the remainder honestly and
stop. No further review round was authorised. This document is that record.

## What cycle 8 changed, and the proof

Commits `b6bf5b05` and `86ee2871`, on `repair/cp912-review-cycle-1`.

**SEC-2, denial of service (fixed).** YAML expands anchors into shared objects, so the
nested-maturity walk added in cycle 7 revisited them and grew about ninefold per anchor level. The
walk now records container identities and visits each shared node once. Measured against the
pre-fix and post-fix module with the same generator:

| Anchor levels | Bytes | Pre-fix | Post-fix |
| --- | --- | --- | --- |
| 6 | 294 | 0.055s | 0.003s |
| 7 | 340 | 0.475s | 0.002s |
| 8 | 386 | 4.253s | 0.001s |
| 9 | 432 | 38.271s | 0.001s |
| 10 | 478 | did not finish in 77s | 0.002s |
| 14 | 696 | not measured | 0.002s |

**SEC-4, fail-open (fixed).** `yaml.safe_load` applies last-key-wins silently, so a frontmatter
whose visible first `maturity:` said `pending-confirmation` and whose second said `plan-ready`
parsed as `plan-ready` and routed live. A strict `SafeLoader` subclass now refuses duplicate
mapping keys, routing the document into the same fail-closed path a malformed block already takes.
Measured on the same input: pre-fix `'plan-ready'`, post-fix `'unknown:carrier:pending-confirmation'`.

**Both fixes are pinned by tests that fail on the unfixed code.** Run against the pre-fix module,
`test_alias_shared_frontmatter_does_not_blow_up` did not complete in 200 seconds and
`test_duplicate_top_level_maturity_fails_closed` fails its assertion. Post-fix both pass in 0.18s.
The verification originally reported for SEC-2 used a 230-byte payload that completes in 0.054s on
the broken code and therefore proved nothing; that is recorded as a learning
(`{#probe-sized-to-the-defect}`).

**The false claims (fixed).** Five copies described out-of-root containment wrongly, in both
directions — first that every out-of-root source is refused, then that a declaring one is always
honoured. The behaviour, established by execution rather than by reading:

| Out-of-root source | Marker directory in path | Declares a maturity | Result |
| --- | --- | --- | --- |
| a | yes | yes | read and honoured |
| b | no | yes | `unknown:out-of-root:` — never read |
| c | no | no | `unknown:out-of-root:` |
| d | yes | no | `unknown:out-of-root:` |

Corrected in the 0.156.0 release note, the handoff skill, the decision record, and two source
comments — one of which asserted that control "DOES reach the path rule below and can route live"
two lines above the `return` that refuses it. Case b was covered by no test and is now pinned by
`test_marker_less_out_of_root_declaration_is_never_read`. That test passes against the pre-fix
module as well: it pins behaviour cycle 7 already had and documented backwards, so it is a
documentation pin rather than evidence of a code fix.

## The 10 P1 findings, honestly

| Finding | Lens | State after cycle 8 |
| --- | --- | --- |
| SEC-2 | security | **Closed**, proven by the measurement table above |
| SEC-4 | security | **Closed**, proven by pre/post inversion |
| AM-1 | architecture-maintainability | **Closed** — the false release-note headline is corrected |
| DOC-1 | documentation-clarity | **Closed** — the release-note body no longer claims a live fall-through |
| AM-2 | architecture-maintainability | **Closed** — the decision record now matches the shipped code, and lists the fifth sentinel cause it was missing |
| CORR-1 | correctness | **Closed** — all three surfaces and both source comments corrected |
| SEC-1 | security | **OPEN.** A marker-bearing out-of-root file that declares a maturity still produces a live, runnable `suggested_command`. This is the shipped design, pinned by `test_reanchored_missing_fallback_to_original`, and cycle 8 corrected the documentation to say so rather than changing the behaviour. Whether the design is right is an open question, not a settled one |
| TEST-1 | testing | **OPEN.** Cycle 8 added a test for the marker-less refusal, but which of the three `unknown:out-of-root:` returns the finding names was not established by mutation, so no closure is claimed |
| TEST-2 | testing | **OPEN.** The single-owner re-anchoring invariant is still pinned by no test |
| AU-2 | agent-usability | **OPEN.** The `unknown:carrier:` diagnostic still names the wrong cause and prescribes a fix the artifact already satisfies |

## The 22 fix requests

Three are closed by cycle 8 and one is partially addressed. The remaining eighteen were not
attempted, by operator decision, and are unresolved.

**Closed:** `fix-9b51e53d45d2` (AM-1, DOC-1) · `fix-e3cd5ddc4bb9` (AM-2) · `fix-92444e041fb0`
(CORR-1).

**Partially addressed:** `fix-21fc252e3694` bundles nineteen findings; cycle 8 closed two of them
(SEC-2, SEC-4). Seventeen remain open in that bundle: AM-3, AM-4, AM-5, AM-6, AM-10, API-4, API-11,
AU-2, AU-11, CORR-6, CORR-7, SEC-1, SEC-3, SEC-5, SEC-8, TEST-1, TEST-2.

**Not attempted (18):**

| Fix request | Findings | Subject |
| --- | --- | --- |
| `fix-1f40ab804724` | DOC-11, DOC-8 | The version-collision learning names 0.151.0 where the shipped heading is 0.156.0 |
| `fix-e738a4aa8d53` | AM-7 | The disclosed residual recommends a cross-plugin import as its next step |
| `fix-e9b5ab8ede0f` | API-9, SEC-9 | The release note asserts the fail-closed contract without the scoping the residual record says a reader needs |
| `fix-1c98d161ef41` | AM-8 | An inline comment asserts the claim the same change added a README paragraph to retract |
| `fix-c953e1223ef6` | AU-3 | Four surfaces say a flow-style maturity fails closed; a top-level flow mapping routes live |
| `fix-ce1de91aa297` | DOC-6 | The evidence-model reference still names the per-dimension key the same commit renamed |
| `fix-4f0a70c896a2` | API-6, API-12 | The normative sentence defining what declares a maturity is ungrammatical and unusable as a rule |
| `fix-5b524f3e3145` | AU-5, AU-10 | The near-match predicate conflates token-set and slug-string equality |
| `fix-351473c97c09` | AU-4 | The `/loop` maturity bullets give no route for a present-but-unrecognized declaration |
| `fix-cbddcf8b9683` | AU-7, AU-8 | `deferred-context` is routable but has no row in the dispatch table `/loop` is told to read |
| `fix-6eb95fb43577` | AU-6 | Narrowing Resume's matched-brainstorm class strands the legacy tier-2 artifacts the same paragraph describes |
| `fix-1f7d0e31b73e` | CORR-5 | The present-but-garbled maturity repair is pinned by no test |
| `fix-e77b6847f5e5` | AM-9, CORR-9, DOC-12 | The ladder renderer calls its own module function through a `globals()` lookup |
| `fix-1ccb8d5f395c` | TEST-3, TEST-9 | A guard was narrowed to table rows so this branch's own prose line would pass |
| `fix-aacbeb7871b4` | TEST-4, TEST-8 | The question-shape guard exempts by identifier name across every module it scans |
| `fix-81762bf840d0` | SEC-7, TEST-10 | Two containment tests pass for incidental reasons |
| `fix-2851f8c208bc` | TEST-6 | The `read_by` assertion grades the docs model against a hardcoded literal rather than the code |
| `fix-fa193a7777a8` | TEST-7 | `_has_block_shape` was rewritten into a strictly more permissive search |

## Other residuals carried forward

- **API-23** is recorded in `residuals-cycle-7.md` with its reproduction table: the fail-closed
  guarantee is scoped to saga's reader, and mission-control's own reader is unaffected. Tracked as
  issue 950.
- **A defect on `origin/main`, not on this branch:** `tests/test_plan_artifact_conformance.py`
  scans `docs/plans/` from disk including untracked files, so any worktree holding an in-flight
  plan fails two tests that have nothing to do with its own changes. This gate was therefore run in
  a clean detached worktree. Not filed; awaiting the operator's call.

## Gate

The full 25-step gate is **green** at `86ee2871`, the exact revision this disposition ships with:
25 steps ran, 0 blocking failures, 0 uncovered, with 7257 tests passed, 7 skipped and 1 xfailed in
11m26s at 85% coverage. The step count was confirmed independently of the summary line by counting
step headers in the log, and the verdict was read from the run's result marker rather than from
stdout.

It was run in a clean detached worktree, not in the working checkout. `origin/main` carries a
defect where `tests/test_plan_artifact_conformance.py` scans `docs/plans/` from disk including
untracked files, so any worktree holding an in-flight plan fails two tests unrelated to its own
changes — here, run #907's plan. That plan was never moved or modified; its SHA-256 is unchanged at
`f695be329f00597156b7c085d17885403a3b52b6b5afa1244f91524a694aac84`.

Two steps are advisory rather than blocking, in the gate and in `ci.yml` alike: the live-gated
board schema census, and the bandit scan. The bandit finding on this branch was read rather than
skipped: the strict loader introduced for SEC-4 raised the repository's only B506, at MEDIUM/HIGH,
because bandit checks the `yaml.load` call syntactically without inspecting that the loader
subclasses `SafeLoader`. It is suppressed as `# noqa: S506 # nosec B506`, the idiom already used at
`tools/agent_spec.py:196` for the identical construct. Bandit results went from 113 to 112, with
zero B506.

## Evidence custody

The evidence ledger verifies clean at seventeen entries — nine artifacts and eight criteria blocks,
all content-addressed and chain-verified. This disposition is deliberately NOT appended to the
ledger: entries there carry verdicts bound to a revision, and the honest terminal verdict remains
seq 17's `repairs_requested`. Appending would read as a newer verdict that no review produced. The
document's custody is its commit on this branch.

## Why this is not an acceptance

`review_result.v1` is the only decision surface, and the last one bound to a revision returned
`repairs_requested`. Cycle 8 repaired a named subset of it under an explicit scope decision and did
not re-run the review, so no result exists that accepts the current revision. Four P1 findings
remain open, along with nineteen fix requests. Issues #912, #913, #914, #915 and #916 and their
board cards therefore stay open, and the commits on this branch reference them with `re` rather
than a closing keyword.
