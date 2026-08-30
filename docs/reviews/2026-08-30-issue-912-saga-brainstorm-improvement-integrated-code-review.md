# Integrated code review — issue 912 Saga Brainstorm improvement run

> **This artifact is a reconstruction.** The original was written on 2026-08-30, deleted from the
> worktree during the worker's repair pass before it was ever committed, and rewritten from the
> reviewing session's own analysis. It is faithful in substance — every finding, count, quoted
> measurement, and verdict is the original's — but it is not the original bytes. Two items were
> folded in after the original was written and are marked as such: finding 30, surfaced by the
> runtime checkpoint, and the runtime-checkpoint result in the coverage section.

**Outcome: `repairs_requested`.** Eleven blocking findings and nineteen advisory. Six of the seven
lenses would block independently. The governing principle held: Brainstorm is still a creative
conversation, and no stop condition on issue 912 fired.

| field | value |
|---|---|
| target | branch `work/cp912-brainstorm-improvement`, range `3b2b7083..HEAD` (5 commits, 4,599 insertions) |
| reviewed revision | `26d5d122571c8fb6eef5751ef4c8ef462c4dcaed` |
| diff base | `3b2b7083fdda8e39e213b5f4acf9f8301d60dd52` |
| review contract | `plugins/saga/skills/code-review/SKILL.md` |
| lenses | architecture-maintainability, correctness, security, testing, api-contract, agent-usability, documentation-clarity (seven, operator-specified; max three concurrent) |
| outcome | **`repairs_requested`** |
| blocked status | **yes** — eleven P1 findings |
| applied fixes | none. The review brief forbids implementation; fix custody belongs to the worker |
| review artifact path | `docs/reviews/2026-08-30-issue-912-saga-brainstorm-improvement-integrated-code-review.md` |
| saga tick | none written — the brief scoped this review to a report plus this artifact |
| linked issue | [infiquetra/infiquetra-claude-plugins#912](https://github.com/infiquetra/infiquetra-claude-plugins/issues/912) |
| linked children | #913 (B1), #914 (B2), #915 (B3), #916 (B4) |
| prior reviews | none. There were no per-unit code reviews; this wave is the run's only one |
| review mode | interactive, report-only; zero source mutations, no commit, no GitHub or board write |

**Every line number below is anchored to the committed revision `26d5d122`.** The working tree has
since moved — the repair pass is uncommitted across roughly twenty files — so verify any citation
with `git show 26d5d122:<path>`, never by opening the working file.

## Commits under review

| Commit | Unit | Issue | Delivers |
|---|---|---|---|
| `5660c719` | plan | — | Run plan plus two document-review rounds |
| `e84be5f2` | B1 | 913 | Unified continuity contract; telemetry-promise removal |
| `45ccfeda` | B2 | 914 | Adaptive judgment model; bounded read-only helpers |
| `e26b5c69` | B3 | 915 | Layered behavioural evidence |
| `26d5d122` | B4 | 916 | Maintenance cleanup; lifecycle-order consistency check |

## Scope check: CLEAN

Every changed file sits on an owned list. The four unit commits landed in the recorded order
B1 → B2 → B3 → B4. `plugins/orchestrate/` is provably untouched, so no Orchestrate release bump is
warranted. The one cross-plugin surface is `tests/test_orchestrate_review_transport.py`, exactly as
issue 916 declares.

## What held

The hard constraint is satisfied. Brainstorm exposes no visible checklist, no fixed questionnaire,
no prescribed question sequence, no persisted score, and no live completeness gate. The private
concern model at `plugins/saga/skills/brainstorm/SKILL.md:246` is scoped "never written to the
artifact, never persisted, never rendered as a document section". No named assurance taxonomy exists
in the skill. `tests/data/brainstorm/rubric.json` carries descriptions and two named bands per
dimension with no weights, no scale, and no aggregate. The Phase 2.5 checkpoint is a maturity state
on an artifact that already existed, not a new state store, queue, or save boundary.

Local quality signals at the reviewed revision: `ruff check .` passes; `ruff format --check .`
reports 502 files already formatted; `mypy plugins/ scripts/ tests/ --ignore-missing-imports`
reports no issues across 335 source files; the focused suite
(`-k "brainstorm or handoff_envelope or lint_gate_absence or orchestrate_review or lifecycle or sandbox_spawn"`)
is 284 passed. `plugins/saga/scripts/lint_gate_absence_contract.py` reports `VIOLATIONS: 0`.

## Blocking findings

| # | File | Issue | Lenses | Conf |
|---|---|---|---|---|
| 1 | `plugins/saga/scripts/handoff_envelope.py:37` | Frontmatter maturity returned unvalidated; three live repo artifacts regress | 5 of 7 | 100 |
| 2 | `plugins/mission-control/scripts/sdlc_manager.py:4475` | Second, content-blind inference still promotes unconfirmed checkpoints | api-contract | 100 |
| 3 | `plugins/mission-control/scripts/sdlc_manager.py:4803` | `pending-confirmation` raises `KeyError`; `parse_issue.py:71` silently blanks it | 3 of 7 | 100 |
| 4 | `tests/test_brainstorm_scenarios.py:43` | Scenario grader is a constant function; calibration cannot detect drift | testing | 100 |
| 5 | `tests/test_brainstorm_mutation_proofs.py:168` | All eight mutation proofs reduce to `"x" not in text.replace("x","")` | testing | 100 |
| 6 | `tests/test_brainstorm_evidence_model.py:154` | AST honesty check evadable five ways; misses one Brainstorm module | testing, docs | 100 |
| 7 | `tests/test_orchestrate_review_transport.py:25` | Orchestrate coverage lost, not just name pinning | testing | 100 |
| 8 | `plugins/saga/skills/brainstorm/SKILL.md:418` | Route-gating paragraph contradicts every per-option condition below it | 3 of 7 | 100 |
| 9 | `plugins/saga/skills/brainstorm/SKILL.md:401` | Path A has no licensed route to `requirements-ready` | 2 of 7 | 75 |
| 10 | `plugins/saga/skills/brainstorm/SKILL.md:392` | Cross-day promotion forks the artifact and jams resume permanently | 2 of 7 | 100 |
| 11 | `plugins/saga/skills/resume/SKILL.md:107` | Declares a `/brainstorm` route no phase implements | agent-usability | 100 |

### 1 — Frontmatter maturity is returned unvalidated

`_read_frontmatter_maturity` returns whatever follows `maturity:` with no membership check, no
inline-comment stripping, and no scoping to `docs/brainstorms/`. Running the base and reviewed
versions of the production function over the repository's own `docs/ideation/` tree:

```
docs/ideation/2026-06-19-plugin-grooming-next-steps.md          idea-ready -> ready-to-execute
docs/ideation/2026-06-25-operator-outcome-orchestration-...md   idea-ready -> illustrative
docs/ideation/2026-06-24-muse-imagination-plugin-seeds.md       idea-ready -> 'imagination-seeds   # upstream of idea-ready; feeds /ideate'
```

The third value is interpolated whole into `suggested_command` at `handoff_envelope.py:158`, the
command `plugins/saga/skills/handoff/SKILL.md:82` instructs the agent to route with. A crafted
`maturity: ; rm -rf ~` likewise returns `'; rm -rf ~'`. In a repository whose workflow routinely has
delegated external workers author documents under `docs/`, that is a narrow single-line injection
path; the three live regressions are what make the finding blocking.

The run plan specified this behaviour at
`docs/plans/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan.md:238` — "that declared value
wins" — and neither the plan nor either document-review round mentions `sdlc_manager.py`,
`parse_issue.py`, or the maturity allow-list. The worker built what was designed.

### 2 — The defect B1 exists to fix is still live on the Mission Control path

`_infer_maturity_from_path` is a second, independent implementation of the same rule and never opens
the file:

```
mission-control _infer_maturity_from_path(unconfirmed checkpoint) -> requirements-ready
saga            infer_maturity(same artifact)                     -> pending-confirmation
```

Coordinator ruling OQ4 brought `plugins/saga/scripts/handoff_envelope.py` into B1's scope precisely
because "an unconfirmed checkpoint would hand off as ready." B1 repaired one of two implementations.
On the entry point documented at `plugins/mission-control/skills/issues/SKILL.md:395`, an
unconfirmed boundary still stamps `requirements-ready` onto the card's `Lifecycle Origin` field
(`sdlc_manager.py:4415`). The function itself is pre-existing; the unmet acceptance criterion is new.

### 3 — `pending-confirmation` reaches consumers that reject or silently drop it

`_suggested_next_action` (`sdlc_manager.py:4803`) is a bare five-key dict subscript.
`pending-confirmation`, `ready-to-execute`, and `illustrative` each raise `KeyError`;
`requirements-ready` renders normally. `_HANDOFF_MATURITY_CHOICES` (`sdlc_manager.py:4262`) rejects
the value at the argparse boundary and again at `:5422`. `parse_issue.py:71` is worse than a crash —
it coerces an unrecognised value to `""`, yielding `can_plan=False` / `can_work=False` /
`requires_clarification=False`, indistinguishable from an issue carrying no maturity at all.
`plugins/saga/references/saga-spec.md:298` calls itself the authoritative enum-domain section and
declares no maturity enum, so the real domain is hand-copied into three places with no drift guard.

### 4 — The scenario grader is a constant function

`grade()` returns `{"band": "pass"}` for every dimension on every input — verified by execution
against a deliberately bad transcript, a flawless one, and `None`, with identical results. Three of
the six cases in `tests/data/brainstorm/scenarios.json` carry `expected: fail`, and no test anywhere
compares the grader's band to them. `_agreement` at `:318` compares the constant against
`tests/data/brainstorm/calibration.json`, whose three cases all expect `"pass"`, so agreement is
exactly `1.0` against a `drift_floor` of `0.8` by construction. The seeded-disagreement case at
`:337` mutates the expected data, not the grader, and proves only that `"pass" != "fail"`.

The scenario *data* is honest and complete — six cases, all four required types present, every one
truthfully labelled `transcript: none`. It is the grader beneath it that proves nothing.

### 5 — The mutation proofs are tautologies

`_assert_mutation` does `text.replace(needle, "", 1)` in memory and calls a `check_*` predicate whose
own literal is that needle. All eight cases have this shape, verified case by case. It reduces to
`"x" not in text.replace("x", "", 1)`. The mechanism is a real phrase-presence guard against
documentation drift; it is not proof that a safeguard holds.

### 6 — The AST honesty check does not prove its claim

Commit `e26b5c69` states the check "proves mechanically that no deterministic test asserts a
question, its wording, or the order of the dialogue." Verified by execution against the production
predicate:

- A question held in a module constant or a `check_*` helper — **this suite's dominant idiom** —
  passes clean, because `_DialogueVisitor` visits only `ast.Assert` nodes.
- A non-interrogative ordered pair passes clean.
- `tests/test_brainstorm_dialogue_ownership.py`, added by B4 *after* B3 shipped the check, is absent
  from the hardcoded five-name tuple at `:154`, and the `.exists()` guard means a rename drops
  coverage silently.
- The three JSON data files are never parsed. They carry no question-shaped strings today.

There is no live violation of the run-level rule. The claim of mechanical proof is what fails.

### 7 — Orchestrate coverage was lost, not just name pinning

The removed `STAGE_SKILLS` entry fed a loop asserting six properties per file: three retired-name
absences **plus** `"HALT" in text`, `"engine-registry.yaml" in text`, `"capability metadata" in text`.
The Brainstorm skill lost all six; the loop now runs 24 assertions instead of 30. The removal was
forced — B4's prose rewrite dropped `engine-registry.yaml` and `capability metadata` from the skill
entirely (both 1 → 0). Re-coverage in `tests/test_brainstorm_dialogue_ownership.py:53` restores only
the three name absences. Issue 916's acceptance criterion "no Orchestrate coverage was lost" is unmet.

Every Orchestrate test function survives — 18 before and after, 41 tests pass. The loss is inside one
loop, not in test-function count.

### 8 — Phase 4 route gating contradicts the option list below it

`plugins/saga/skills/brainstorm/SKILL.md:417` says route-gating is "tied to declared maturity, not to
file existence". Options 2, 3 and 4 at `:436-440`, unchanged by this range, still read "Shown when a
requirements doc exists". A `pending-confirmation` checkpoint is a file on disk, so option 3's own
condition evaluates true and `/handoff` is offered — the exact leak the gate was added to close. An
executing agent meets the per-option condition second and it is the more specific of the two, so two
agents render different menus from the same file and the same artifact.

`check_artifact_free` in `tests/test_brainstorm_continuity_contract.py:120` asserts only that the
phrase "no route from options 1 through 4 is shown" is *present*; it never examines the contradicting
condition fifty lines below.

### 9 — Path A has no licensed route to `requirements-ready`

Phase 2.5 Path A has "no confirmation question" (`:349-352`), the checkpoint write is scoped "On Path
B only" (`:363`), and the only promotion mechanism is Path B's (`:396`), closed by an unconditional
refusal at `:401`. Phase 3 permits a Path A document but never states its maturity. Under the strict
reading the whole Lightweight tier loses every forward route; under the permissive reading Path A
writes `requirements-ready` with no confirmation, voiding the guarantee at `:370`. The text licenses
both.

### 10 — Cross-day promotion forks the artifact and jams resume

`:84` designs a cross-day resume on purpose ("A match at `maturity: pending-confirmation` re-enters
at the Phase 2.5 confirmation"). Phase 3 pins the filename to "today's date" (`:392`) while promotion
"rewrites the same Path B checkpoint path in place" (`:396`). On a later calendar day those name
different files. Phase 0.1 tier 1 then sees two files with the same `topic` plus `capability` and must
"stop and ask" (`:84`) — and legacy discovery "never writes to the file" (`:408`), so no instruction
licenses deleting or merging the stale one. The jam is permanent.

### 11 — `/resume` declares a route nothing implements

`plugins/saga/skills/resume/SKILL.md:107` says an unambiguous match "routes to `/brainstorm`". The
classifier immediately below (`:113-120`) offers only `matched-saga`, `resolvable-issue`, and
`NEITHER`, and a brainstorm artifact has none of `issue_ref`, `plan_path`, or `branch`. Phase 4 routes
per `plugins/saga/skills/loop/references/dispatch-table.md`, which **is not in this change set**,
whose row at `:72` sends `ideation`/`brainstorm` to `/plan` unconditionally and which contains zero
occurrences of `pending-confirmation`. Phase 5 mandates a re-entry tick reusing a `saga_id` a
brainstorm artifact cannot have.

## Advisory findings

| # | File | Issue |
|---|---|---|
| 12 | `plugins/saga/references/brainstorm-evidence-model.md:127` | Documents `BRAINSTORM_LIVE_GRADE` and an injectable runner; neither exists in any `.py` file |
| 13 | `plugins/saga/skills/handoff/SKILL.md:90` | Six shipped surfaces still document path-only derivation |
| 14 | `plugins/saga/scripts/handoff_envelope.py:27` | Uncaught `UnicodeDecodeError` aborts `/handoff` on a non-UTF-8 artifact |
| 15 | `plugins/saga/scripts/handoff_envelope.py:49` | `build_handoff_envelope(root=...)` resolves maturity against `cwd`, not `root` |
| 16 | `plugins/saga/references/sandbox-spawn-sites.md:62` | Scout keeps `Bash` without worktree isolation; `SKILL.md:176` overstates read-only |
| 17 | `tests/test_saga_lifecycle_consistency.py:295` | `"not a"` substring escape defeats the automatic-transition guard |
| 18 | `tests/test_saga_lifecycle_consistency.py:313` | Unanchored repo-wide `shaping` ban matches `reshaping` |
| 19 | five test modules | Inert `_HE` production import under a comment naming `scripts/lint_test_shape.py` |
| 20 | `docs/engineering-journal/LEARNINGS.md:24,32,39` | Three citations resolve to the wrong commit or wrong lines |
| 21 | `plugins/saga/docs/model/saga-docs-model.yaml:28` | Model and generated SVG contradict this range's own spec amendment, pinned green by a passing test |
| 22 | `plugins/saga/skills/brainstorm/SKILL.md:79` | "Producer facts" names three different field sets; tier-1 routing turns on it |
| 23 | `plugins/saga/skills/brainstorm/SKILL.md:362` | No rule for a rejected or abandoned pre-confirmation checkpoint |
| 24 | `plugins/saga/skills/brainstorm/SKILL.md:445` | Option 7 asserts "the requirements doc is saved" after an artifact-free run |
| 25 | `plugins/saga/skills/brainstorm/SKILL.md:286` | "Idle questions" carve-out is undefined and circular |
| 26 | `plugins/saga/scripts/handoff_envelope.py:56` | Thirteen dead lines whose comment claims resolution the code does not perform |
| 27 | `plugins/saga/references/brainstorm-evidence-model.md:1` | New shipped reference has no inbound link from anywhere in `plugins/` |
| 28 | `plugins/saga/skills/brainstorm/SKILL.md:285` | Eight rules stated two or three times after three authors |
| 29 | `plugins/saga/skills/brainstorm/SKILL.md:363` | "Checkpoint" gains a fourth meaning inside the plugin, one of them opposite |
| 30 | `plugins/saga/skills/brainstorm/SKILL.md:364` | `topic` frontmatter carries the verbatim invocation argument, but promotion normalizes to a kebab-case slug — the resume key changes shape mid-run |

### 30 — The resume key changes shape between checkpoint and promotion

**Surfaced by the runtime checkpoint after this review was written, not by any lens.** It is recorded
here on the checkpoint's evidence; the reviewing session did not reproduce it independently, so treat
the mechanism below as the checkpoint's finding rather than as a verified measurement of this review.

The Phase 2.5 checkpoint writes `topic` frontmatter carrying the **verbatim command argument** — the
full phrase the operator typed. `plugins/saga/skills/brainstorm/references/requirements-sections.md:69`
mandates that `topic` is a "kebab-case slug", and promotion writes the document under that contract.
So `topic` holds one shape before confirmation and a different shape after.

Phase 0.1 tier 1 matches on `topic` plus `capability` (`plugins/saga/skills/brainstorm/SKILL.md:80`).
Once promotion normalizes `topic` to the slug, a later re-run invoked with the original full-sentence
argument has **no defined exact-match rule** — the argument no longer equals the stored `topic`, and
the skill states no normalization step to bridge them. The run then falls through tier 1 to tier 2 or
tier 3 and can start fresh, duplicating an artifact that already exists.

This is the same family as finding 10 but milder: finding 10 produces two files and a permanent
ambiguity stop, while this one produces a silent miss. It compounds finding 22 — a tier-1 rule whose
key membership is already stated three ways now also has a key whose *shape* is unstable.

**Smallest fix.** State one normalization rule and apply it on both sides: slugify the invocation
argument before matching, and slugify `topic` at checkpoint-write time so the stored value never
changes shape between checkpoint and promotion. Whichever side is chosen, the two must agree, and
`requirements-sections.md:69` is the natural place to own the definition.

## Plan-completion audit

| Criterion | State |
|---|---|
| 913 — unconfirmed checkpoint cannot hand off as ready | **NOT DONE** — finding 2 |
| 913 — artifact-free exploration exposes no durable route | **PARTIAL** — finding 8 |
| 913 — resume restores the latest unambiguous checkpoint | **PARTIAL** — findings 10, 11, 30 |
| 913 — telemetry promise removed, marker retained and repointed | **DONE** — `saga.py save` absent; markers at `:48` and `:362`; lint clean |
| 914 — no named assurance levels, map never exposed | **DONE** |
| 914 — helper ceilings and distinct-question rule | **DONE** in prose; see finding 16 for the isolation gap |
| 915 — mechanical proof that no test asserts a question or order | **PARTIAL** — finding 6; the check exists, the proof claim does not hold |
| 915 — calibration set surfaces grader drift | **NOT DONE** — finding 4 |
| 915 — every critical safeguard carries a mutation case that fails when weakened | **PARTIAL** — finding 5 |
| 916 — no Orchestrate coverage lost | **NOT DONE** — finding 7 |
| 916 — lifecycle set re-counted at preflight | **DONE** — verified: `ideate`, `loop`, `office-hours`, `plan`; `founder-review` is a genuine variant; `strategy` carries inline mentions only |
| 916 — dispatch line count recorded, nothing manufactured | **DONE** — verified absent at the base |
| 916 — Shaping stated once | **DONE** — one new statement at `plugins/saga/references/saga-spec.md:311` |
| 912 — no visible checklist, questionnaire, sequence, score, or live gate | **DONE** |
| 912 — no test asserts an exact question, wording, or dialogue order | **DONE** — verified by hand over every added module and all three JSON files |
| 912 — release surfaces aligned | **DEFERRED** by coordinator ruling OQ7 to the fifth commit |
| 912 — `bash scripts/gate.sh` exits 0 | **UNVERIFIABLE at this revision**, by design (key technical decision 8) |

## Coverage and limits of this review

A full gate was already running in this worktree under another owner when the review began. It was
left alone rather than terminated, and it wrote no readable result marker. **No claim is made about a
green gate.** The individual CI-scope checks were run instead and are recorded above; key technical
decision 8 states the gate can only be green at the fifth commit, so a red gate at this revision is
expected rather than a finding.

The candidate Saga was reviewed as text on disk. It was not installed, not loaded, and not
`--plugin-dir`-ed; the plugin marketplace was not refreshed. The installed Saga surface stayed pinned
at 0.148.0 throughout, so the concurrent issue-907 run was not disturbed.

**Runtime evidence, added after this review was written.** The run's post-B2 runtime checkpoint has
since executed against the candidate and passed **7 of 7 observables**. That partially closes this
review's largest self-declared limitation — that it read the skill as text and could not exercise it
— and it is the source of finding 30, which no lens found. Two things follow honestly: the happy
paths the checkpoint exercised do work against the real candidate, and a defect that only appears
when a real invocation argument meets a real slug was invisible to seven text-reading lenses. Neither
observation changes any finding above.

No source file was mutated by this review, nothing was committed or pushed, and no GitHub or
project-board write was made.

Suppressed findings: none. Every finding admitted here carries confidence 75 or 100; nothing was
dropped by the anchor-75 admission rule.
