# Saga Code Review — issue 907 integrated target

**Verdict: NOT ACCEPTED — changes required.**

| Field | Value |
|---|---|
| Repository | `infiquetra/infiquetra-claude-plugins` |
| Reviewed commit | `0f363f2b4ef012c48076266db229cc1173401bae` |
| Branch | `work/cp907-launcher-session-contract` |
| Base | `3b2b7083` (`origin/main` at preflight) |
| Diff reviewed | `git diff 3b2b7083..0f363f2b` — all 21 files, 3,313 insertions, 45 deletions |
| Review wave | 1 (single wave) |
| Lens roster | `plugins/saga/references/lens-roster.json`, schema `lens_roster.v1` |
| Lens selection | Seven, supplied by the orchestrating caller; the selection gate is closed under `caller_or_orchestrate_selection_is_approval`. No hidden or supplemental lenses were run. |
| Concurrency | Three lenses in flight at most, in waves of 3 / 1 / 1 / 1 / 1. Every lens spawned as `saga:readonly-verifier` with `isolation: "worktree"`. |
| Reviewer authority | Read-only. No reviewed code was edited, committed, or pushed. The primary worktree was verified clean at the frozen commit after every lens returned. |

---

## Acceptance

The roster's `acceptance` block is threshold-only, with `combiner: "all"`, and both rules must hold
for every scoring lens:

| Rule | Metric | Test |
|---|---|---|
| `derived-overall-minimum` | `derived_overall` | `>= 9.0` |
| `applicable-dimension-floor` | every applicable dimension | `>= 7.0` |

`finding_priority_is_gate` and `finding_confidence_is_gate` are both `false`, so acceptance comes
from the scores alone.

**Zero of seven lenses meet the overall minimum.** Two also breach the dimension floor. The change
is therefore not accepted, and it would not be accepted even if every finding below were waived,
because acceptance is a score threshold rather than a finding count.

| Lens | Class | `derived_overall` | Overall `>= 9.0` | Dimension floor `>= 7.0` |
|---|---|---|---|---|
| `architecture-maintainability` | always-on | 8.0 | FAIL | pass |
| `security` | always-on | 7.6 | FAIL | pass |
| `reliability` | conditional | 7.3 | FAIL | pass |
| `api-contract` | conditional | 7.3 | FAIL | pass |
| `testing` | always-on | 7.2 | FAIL | pass |
| `correctness` | always-on | 6.8 | FAIL | **FAIL** (two dimensions at 6) |
| `documentation-clarity` | conditional | 6.5 | FAIL | **FAIL** (four dimensions at 6) |

---

## Per-lens dimension scores

### `correctness` — 6.8

| Dimension | Score | Note |
|---|---|---|
| `intent-behavior-completeness` | 6 | Three stated behaviours materially incorrect: the guard is bypassed on the OpenCode path, the composer classifier drops staged text on a standard reset, and the permission confirmation is self-referential. |
| `state-data-invariants-transactions-concurrency` | 7 | Ownership, receipt ordering and status transitions hold; dispatch is single-threaded. `confirmed_against_herdr` gains `"account"` from a filesystem transcript, against the rule the same commit states. |
| `boundary-types-serialization-numeric-time` | 6 | The wall-clock/mtime floor is correct and boundary-tested; terminal escape parsing silently changes a value and an empty receipt file still raises an uncaught decode error. |
| `side-effects-errors-resource-lifecycle` | 7 | The create deadline and the nonzero close both work; a timed-out create can orphan a tab and the new close diagnostic reaches an operator on one of three paths. |
| `caller-enum-consumer-completeness` | 8 | Every vendor/posture pair, all six `close_run_session` sites and every release-surface pin traced and correct; Orchestrate's `go` retains stale note handling. |

### `security` — 7.6

| Dimension | Score | Note |
|---|---|---|
| `authentication-authorization-tenant-isolation` | 7 | Unknown-posture handling now fails closed before any session exists; the argv check certifies a posture it never observes, and OpenCode's `auto` resolves to its `bypass` flag. |
| `input-trust-boundaries-injection` | 7 | The composer parser reads arbitrary bytes another process painted into a pane; the staged-versus-empty classifier fails open in several shapes, and an unreadable box prompts anyway. |
| `secrets-cryptography-session-handling` | 8 | No hardcoded secrets, no cryptography; the new secret-safety contract is correct and mutation-proofed — offset by a new unredacted persistence channel for arbitrary human-typed text. |
| `dependency-supply-chain` | 9 | Standard library only, verified from the import block. No third-party dependency added. Versions consistent across all four release surfaces. |
| `confidentiality-logs-errors-egress` | 7 | Verbatim staged terminal text reaches a receipt, a stderr message, a unit note, `.orchestrate/run.json`, and a committed run record. |

### `reliability` — 7.3

| Dimension | Score | Note |
|---|---|---|
| `timeouts-retries-circuit-breakers-idempotency` | 7 | The create call is bounded and proven against a real subprocess; the cleanup close and the statusline read still hang unboundedly, and `close` lost its safe re-run. |
| `queues-jobs-dead-letters-ordering-backpressure` | NOT APPLICABLE | Absent precondition: no asynchronous work queue, message broker, job store, or dead-letter path exists in the reviewed change. Dispatch is one synchronous `subprocess.run` per unit. |
| `concurrency-partial-failure-recovery` | 8 | One meaningful partial path — a create that times out after the wrapper made a session — leaves state a person must find by hand. |
| `graceful-degradation-cancellation-cleanup` | 7 | The new hard stops close what they own and the staged-input stop correctly closes nothing; the create-deadline path leaves a session behind and prints no handle for it. |
| `health-signals-observability-runbooks` | 7 | The receipt genuinely improved; the close-failure record never reaches the operator on the Orchestrate path. |

### `api-contract` — 7.3

| Dimension | Score | Note |
|---|---|---|
| `interface-contract-compatibility` | 7 | The new failing-close diagnostic is erased by Orchestrate's own launch handler; the guard's parser both misses styled staged text and invents staged text from a marker-prefixed transcript line. |
| `versioning-deprecation` | 7 | The `>=1.1.0` floor has no runtime enforcement and no version constant to enforce against; the release rationale misdescribes two return-type changes as additive. |
| `serialization-errors` | 7 | `permission_resolved.confirmed_from` asserts a confirmation that did not happen for three vendor cases. |
| `retry-idempotency-semantics` | 7 | `close --receipt-json` became non-idempotent, with no documented distinction between a terminal "already closed" and a retryable failure. |
| `pagination-rate-limits` | NOT APPLICABLE | Absent precondition: the diff introduces or modifies no collection traversal, cursor, page, ordering, quota, or throttle. The three new constants are deadlines, not rate limits. |
| `sdk-generated-client-impact` | 9 | Orchestrate's ingest seam still works and reads the one changed return it touches correctly; no guard keeps the fallback stub name list in sync with new launcher exports. |
| `specification-documentation-parity` | 7 | The new preflight block promises a read-back of model and reasoning effort the receipt cannot supply, and its example omits `--prompt`. |

### `testing` — 7.2

| Dimension | Score | Note |
|---|---|---|
| `requirements-regression-coverage` | 7 | Nine named mutation proofs re-verified dead on their named tests; the shipped "unreadable box is recorded in the receipt" requirement has no test at all. |
| `negative-edge-state-concurrency-time` | 7 | Strong error-path breadth; the pane-read failure boundary is untested and the recency slack is pinned on one side only. |
| `behavior-sensitive-assertions` | 7 | Mostly precise; one test's two named assertions are provably unreachable and the composition test now asserts only its endpoints. |
| `realistic-seams-mocks-integration-evidence` | 7 | Real shell wrappers, real subprocesses and real file mtimes elsewhere; the composer parser is fed only fixtures the test file wrote, which do not span the shapes it must survive. |
| `determinism-isolation-diagnostics-maintainability` | 8 | Deterministic and isolated; the prose-linting regexes couple the whole launcher README to the suite. |

### `architecture-maintainability` — 8.0

| Dimension | Score | Note |
|---|---|---|
| `architectural-fit-ownership-single-sources` | 8 | Permission policy, composer markers and every new timeout have exactly one home and Orchestrate keeps no copy; the receipt gained three keys and a fourth write site while the repository's own receipt pattern sits unused. |
| `separation-of-concerns` | 8 | Terminal parsing already lives in this module, but this is a partial protocol implementation the safety guard's correctness depends on. |
| `dependency-direction` | 9 | Direction correct and now test-pinned; the floor was raised with an explicit reason. |
| `simplicity-abstraction-duplication-changeability` | 8 | One named pattern shipped in two encodings by two consecutive units, plus two fresh copies of error-message construction. |
| `readability-naming-error-contracts` | 7 | `input_box: "unreadable"` names a read that succeeded; a docstring claims no caller raises when one does; a test name promises a guarantee its body never evaluates. |
| `conventions-portability-configuration` | 9 | Lint and format clean on every changed surface; naming, CHANGELOG, manifests and the three version-floor guards all moved together. |
| `significant-decision-documentation` | 7 | One well-formed journal entry with a mutation proof; the cross-cutting receipt-channel pattern and the styled-versus-unstyled heuristic both shipped with no `DECISIONS.md` entry. |

### `documentation-clarity` — 6.5

| Dimension | Score | Note |
|---|---|---|
| `shipped-behavior-parity` | 6 | The dry-run correction is exact, but three new or rewritten claims disagree with the shipped launcher. |
| `completeness-audience-prerequisites` | 6 | The guard's total inertness on OpenCode and the probe-name collision prerequisite are unstated. |
| `structure-navigation` | 8 | Placement of the new section is sensible; its example duplicates the block at the top of the document without saying how the two differ. |
| `terminology-cross-document-consistency` | 6 | The permission vocabulary conflicts across three live sources, and a stale instruction one screen below contradicts the rewritten paragraph. |
| `runnable-examples-actionability` | 6 | The primary new example exits nonzero as written and its teardown line has two reachable failure modes. |
| `runbook-safety-rollback-links-generated-drift` | 7 | Stop conditions and the cited issue link are sound; the documented teardown has no recovery when the receipt is empty or the session is unowned. |

---

## What the run already knew — verified, not rediscovered

| Claim in the run brief | Status |
|---|---|
| Base `3b2b7083` gated green, 25 steps | Not re-run; accepted as given. Two lenses independently ran lint and format clean on every changed surface. |
| Full suite reports zero failures | **Confirmed.** My own run of the whole suite on the frozen tip: exit 0. |
| Full suite reports 6555 passed, 7 skipped | **Skipped count confirmed; passed count does not reconcile.** My measurement is **6988 passed, 7 skipped, 1 xfailed, 0 failed** in 693s. One lens measured 6552 passed plus 3 environment-only failures in a detached tarball, and a third measured 6854. The three figures differ by collection environment, not by outcome. The zero-failure claim holds; the 6555 figure should not be quoted as the suite size on this tree. |
| Every unit carries mutation-proof tests | **Mostly confirmed, with two named exceptions.** The testing lens re-ran nine of the run plan's named mutation proofs and all nine died on their named test, including the real-subprocess create deadline. Two constants are not mutation-proof: `PANE_INPUT_READ_SECONDS` (deleting the timeout leaves 83 tests green) and `TRANSCRIPT_MTIME_SLACK_SECONDS` (widening 1.0 to 30.0 leaves the suite green). |
| A document review closed fourteen findings before implementation | Accepted as given; the committed review record is internally consistent. |
| The relaxed assertion in `test_delivery_warning_appends_to_the_file_handover_note` was the right call | **The direction is upheld; the repair is not.** See the adjudication below. |

### Adjudication of the operator's ruling on the relaxed assertion

The ruling was challenged, as the brief invited. **The lenses split, and the split is informative.**

`correctness` upheld the ruling outright: suppressing the guard's note to preserve exact equality
would have traded a real fix for a test's convenience, and the mutation the test exists to kill —
replacing rather than appending the delivery warning — still breaks `startswith`.

`testing`, `architecture-maintainability` and `api-contract` all reached the same different
conclusion: **the direction was necessary but the repair was weaker than the case required.** The
note that lands between the two pins is deterministic, not variable. It is exactly
`input box not readable; prompted without inspection`, every run, because the test's stub makes the
pane read unparseable. Exact equality naming that middle note would have preserved the
note-composition guard *and* given the unreadable branch its only assertion anywhere in the suite.
As shipped, the testing lens demonstrated by mutation that a duplicated delivery warning and an
arbitrary injected middle note both pass.

**My finding: the operator's ruling to fix rather than suppress was correct, and the fix chosen was
the second-best available one.** This matters more than its size suggests, because that test is the
suite's only end-to-end witness that the units compose inside one real `launch`. Recorded as
finding P2-6.

---

## Findings

47 findings after deduplication by `(path, line, category)`: **5 blocking (P1), 20 P2, 22 P3.**
Cross-lens agreement is recorded per finding; agreement strengthens evidence and is not counted
twice.

### Blocking — P1

Four of the five blockers belong to one unit: the input-box guard shipped for issue 897. That unit
does not hold.

```
title: Composer parser fails open on common style resets
severity: P1
dimension_id: boundary-types-serialization-numeric-time
file: plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py
line: 703
agreeing_lenses: correctness (P1), security (P2), architecture-maintainability (P2), api-contract (P2)
why_it_matters: The staged-versus-placeholder decision rests on one line that treats a run as
  styled unless the escape's parameter string is exactly "" or "0". Every other style-off code —
  22 (normal intensity), 39 (default foreground), 00, 0;10 — leaves the parser stuck in the styled
  state, so the operator's staged text is discarded as if it were a client placeholder. The guard
  then takes its empty branch, the receipt records `input_box: "empty"` as an affirmative fact,
  and the dispatched prompt is typed behind text that is still in the box. That is precisely the
  concatenate-and-submit failure the unit exists to prevent, now carrying a run record that
  asserts the box was inspected and found clear.
confidence: 100
evidence: launcher.py:703 — `styled = sgr.group(0)[2:-1] not in ("", "0")` is the entire reset test.
evidence: Coordinator-verified against the frozen module. Five shapes return `''` with text plainly
  staged: `ESC[2m❯ESC[00m /deploy prod --force`, and the same line with `ESC[39m`, `ESC[22m`,
  `ESC[0;10m`, and with the marker styled and never reset. The two controls behave correctly —
  a plain unstyled line and `ESC[2m❯ESC[m` both return the staged text.
evidence: Independently reproduced by three lenses with different fixtures, including
  `ESC[2m❯ ESC[22mstaged task text` -> `''` and `❯ ESC[1mfix the bugESC[0m` -> `''`.
evidence: launcher.py:746-749 writes `receipt["input_box"] = "empty"` and returns, so the
  misclassification becomes a durable claim.
evidence: No test covers the gap. The test file contains two ANSI fixtures; every staged-path test
  passes a completely unstyled composer line, which is the one shape that works.
pre_existing: false
suggested_fix: Parse the parameter list and end the styled span on any of 0, 21, 22, 23, 24, 27,
  28, 29, 39, 49 — or invert the default so an unclassifiable composer counts as staged.
unverified: Which escape spellings today's shipped clients actually emit around their composer.
  The run's own checkpoint shows five vendors classified correctly on this host, so no shipped
  client is demonstrated to hit this today. The defect is in the parser's contract, not in a
  measured live failure.
```

```
title: Marker scan takes the last marker line, not the composer
severity: P1
dimension_id: realistic-seams-mocks-integration-evidence
file: plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py
line: 684
agreeing_lenses: testing (P1), correctness (P2), api-contract (P2)
why_it_matters: The scan keeps the last line whose stripped first character is one of three
  markers, with no check that the line is a composer and no break. A plain ">" is one of those
  markers. It fails in both directions and both are reachable. Fail-open: a pane whose composer
  holds staged text, followed anywhere below by a bare ">" row — an OpenCode variant menu, a
  wrapped diff, a quoted line — reads as empty and gets prompted. False stop: ordinary pane output
  beginning with a marker is returned as staged input and refuses a legitimate unit mid-dispatch.
  Claude echoes every submitted prompt into scrollback prefixed with the same glyph the composer
  uses, which the run's own preserved pane capture shows verbatim.
confidence: 100
evidence: launcher.py:684-686 — the loop assigns `composer = line` on every match with no break.
evidence: Coordinator-verified against the frozen module. `"❯ rm -rf /important\n> "` returns `''`
  — fail open, with `rm -rf /important` still in the box. `"❯ rm -rf /important\n> quoted line"`
  returns `'quoted line'` — false stop. `"❯ deploy now\n> Option A\n> Option B"` returns
  `'Option B'`.
evidence: launcher.py:679 — `COMPOSER_MARKERS = ("❯", "›", ">")`; the bare ">" is a live marker for
  two vendors per the run's own checkpoint, and the module's own variant parser expects
  "> Option" rows in panes.
evidence: Mutation-proved unexercised: taking the first marker line instead of the last leaves the
  suite green, so the scrollback-decoy rule the code deliberately chose has no test.
evidence: The extracted text is never stripped of escapes, so a cursor escape inside staged text
  corrupts the value the guard promises is "preserved, not cleared" — `❯ deploy the ESC[7mfESC[0mleet`
  returns `'deploy the leet'`.
pre_existing: false
suggested_fix: Require the marker line to be the last non-blank line of the visible read, or anchor
  on the bracketing rule rows rather than on the glyph alone.
```

```
title: The guard's failure branch has zero coverage anywhere
severity: P1
dimension_id: negative-edge-state-concurrency-time
file: plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py
line: 726
agreeing_lenses: testing (P1), reliability (P3 on the timeout half)
why_it_matters: Every guard test replaces the module's `run` with a fake that always succeeds and
  whose signature discards keyword arguments, so neither the failed-read branch nor the timeout it
  is supposed to carry is ever executed. This is the harness-substitution shape exactly: the
  fixture stands in for the terminal, and the terminal is the component under test. A wedged,
  missing, or slow multiplexer makes every pane read fail, and nothing proves what happens then.
confidence: 100
evidence: Mutation, changing the failure return from `None` to `""` — which makes an unreadable box
  indistinguishable from an empty one, so the receipt would record a false clean bill of health on
  the audit field the run plan cites: 167 passed.
evidence: Mutation, deleting the entire `staged is None` branch (note plus receipt marking): 167
  passed. The guard's failure handling can disappear without trace.
evidence: Mutation, removing `timeout=PANE_INPUT_READ_SECONDS` from the pane read: 83 launcher
  contract tests passed. Independently found by a second lens.
evidence: test_launcher_contract.py:303 — `def fake_run(cmd, **_k)` swallows the timeout argument,
  which is the structural reason both mutations survive.
evidence: A grep over every test directory finds only four files referencing any of these
  behaviours; all four were run together for the mutations above.
pre_existing: false
suggested_fix: One test driving the guard with a stub returning a nonzero code, asserting
  `receipt["input_box"] == "unreadable"`, the note text, and that the send still happened; plus an
  assertion that the pane read is issued with a timeout.
```

```
title: Staged operator text persisted verbatim to four durable places
severity: P1
dimension_id: confidentiality-logs-errors-egress
file: plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py
line: 752
agreeing_lenses: security (P1)
why_it_matters: A terminal input box holds whatever a person last typed and did not submit. The
  guard records that line verbatim, with no redaction, no length cap, and no allowlist, into the
  receipt, the unit note, the stop message on stderr, and — through Orchestrate's handler — the
  run state file. If the operator had staged an export of a token, a login line, a customer name,
  or a half-typed destructive command, a fleet dispatch onto that pane turns it into repository
  content. The failure is silent to the person whose text it was.
confidence: 100
evidence: launcher.py:752 — `receipt["input_box_text"] = staged`, raw.
evidence: launcher.py:753 — the same text into the unit note; launcher.py:755 — into the SystemExit
  message, which the CLI dumps to the stream the skill tells the caller to redirect into a file.
evidence: orchestrate.py:2610 — `unit.note = str(exc)`, then `r.save()` writes it into the run state.
evidence: The path is not hypothetical. `docs/reviews/2026-08-30-cp907-runtime-checkpoint.md:142`
  carries `'input_box_text': 'harmless staged text for cp907 checkpoint'` as committed repository
  content, having travelled receipt to stderr to run record to markdown.
evidence: The same release states the opposing rule in its own new skill guidance — never persist a
  credential value, and redact inside the producing command before output exists. That contract
  governs what a caller may inspect; nothing governs what the launcher itself produces.
pre_existing: false
suggested_fix: Record a length and a coarse shape instead of the text. A stop needs no transcript
  of the operator's draft.
```

```
title: OpenCode picker types into the pane before the guard reads it
severity: P1
dimension_id: shipped-behavior-parity
file: plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py
line: 1230
agreeing_lenses: documentation-clarity (P1), correctness (P2)
why_it_matters: For an OpenCode unit landing on a pane the launcher did not create, the variant
  picker is driven into that pane — two lines typed and submitted through the same door the module
  uses to deliver prompts — before the guard has looked at anything. The guard's own docstring
  ("before anything is prompted into it"), the shipped skill sentence, and the changelog entry are
  all false on this path. Compounding it, the run's own live evidence shows OpenCode panes always
  fall to the unreadable branch, so even after those writes the guard gives that vendor no
  protection at all.
confidence: 100
evidence: Coordinator-verified from the frozen source. launcher.py:1229-1236 orders
  `await_ready` -> `drive_opencode_variant_selection` -> `verify_unit_preflight` ->
  `guard_reused_pane` -> `send`. The picker is second; the guard is second to last.
evidence: launcher.py:791 — `run(["herdr", "pane", "run", pane_id, "/variants"])` is the first
  action inside the picker drive; launcher.py:1312 uses the same command shape as the prompt
  delivery fallback, so the module treats it as a submitting door.
evidence: A lens executed the frozen `launch` for an unowned OpenCode pane holding staged text and
  recorded the call order: `/variants`, a read, `xhigh`, then the guard's read, then the stop —
  by which time two lines had already been submitted.
evidence: Every guard test uses a different vendor, so no test covers this ordering.
pre_existing: false
suggested_fix: Move the guard call above the vendor-specific picker drive.
```

### P2 — 20 findings

| # | Finding | File:line | Dimension | Lenses | Pre-existing |
|---|---|---|---|---|---|
| P2-1 | Argv permission check is self-referential; both sides come from the same call, so it cannot fail, and a contradicting posture in `launch_args` passes | `launcher.py:1123` | `intent-behavior-completeness` | security, correctness, api-contract | no |
| P2-2 | `confirmed_from: "launch_argv"` is recorded when the check did not run — two vendors resolve `auto` to an empty token list and skip the block entirely | `launcher.py:1178` | `serialization-errors` | api-contract, correctness, security, documentation | no |
| P2-3 | Orchestrate's launch handler replaces the whole unit note, erasing the close-failure record the release exists to surface | `orchestrate.py:2606` | `caller-enum-consumer-completeness` | reliability, correctness, api-contract | no |
| P2-4 | Orchestrate's sweep discards the new close return and reports the unit closed while its session is live | `orchestrate.py:4030` | `readability-naming-error-contracts` | architecture, correctness | partly |
| P2-5 | Both named assertions in the unknown-permission test are unreachable; the test proves only what its predecessor already proved | `tests/test_orchestrate_vendor_permissions.py:227` | `behavior-sensitive-assertions` | correctness, architecture, testing | no |
| P2-6 | The relaxed handover assertion leaves the middle of the note unpinned; a duplicated warning and an injected note both pass | `tests/test_orchestrate_status_and_notes.py:158` | `behavior-sensitive-assertions` | testing, architecture, api-contract | no |
| P2-7 | A timed-out create abandons a session with no receipt, no tab identifier, and no note, discarding the snapshot that could name it | `launcher.py:1208` | `graceful-degradation-cancellation-cleanup` | reliability, correctness | no |
| P2-8 | The close whose return code the release made load-bearing is itself unbounded, as is the statusline read inside the settle loop | `launcher.py:834`, `:950` | `timeouts-retries-circuit-breakers-idempotency` | reliability | yes |
| P2-9 | The resend loop re-sends into a pane the guard inspected once, and never runs the guard at all for an owned session | `launcher.py:1247` | `timeouts-retries-circuit-breakers-idempotency` | reliability | no |
| P2-10 | An empty or truncated receipt file still raises an uncaught decode traceback — the failure the unit was convened to eliminate, one branch over | `launcher.py:1539` | `boundary-types-serialization-numeric-time` | correctness, documentation | yes |
| P2-11 | `close --receipt-json` became non-idempotent: a re-run, or a close of an already-gone tab, exits nonzero with no terminal-versus-retryable distinction | `launcher.py:1462` | `retry-idempotency-semantics` | api-contract, reliability | no |
| P2-12 | The `>=1.1.0` floor is documentation only — the launcher exports no version and the resolver execs whatever file it finds | `orchestrate.py:1500` | `versioning-deprecation` | api-contract, reliability, testing | yes |
| P2-13 | The new read-back block promises model and reasoning effort the receipt cannot supply; the receipt has no effort key and model is the echoed request | `SKILL.md:69` | `specification-documentation-parity` | api-contract | no |
| P2-14 | The documented preflight example omits `--prompt` and exits 1 on its ordinary path, under a heading saying anything wrong is a stop | `SKILL.md:77` | `runnable-examples-actionability` | documentation (P1), api-contract (P2), correctness (P3) | no |
| P2-15 | "Confirmed against the launch argv" cannot distinguish OpenCode's two postures, which resolve to the same flag; the module admits this in a comment no document carries | `SKILL.md:32` | `shipped-behavior-parity` | documentation, security | no |
| P2-16 | The guard never fires on OpenCode at all — the run's own evidence puts every such pane on the unreadable branch — and the skill presents that branch as an edge case | `SKILL.md:36` | `completeness-audience-prerequisites` | documentation | no |
| P2-17 | The documented probe teardown has two reachable failures — an unowned tab from a name collision, and an empty receipt — with no recovery given | `SKILL.md:82` | `runbook-safety-rollback-links-generated-drift` | documentation | no |
| P2-18 | Orchestrate's skill documents no plan-row `permission` field or default, while shipping a line that names units omitting it; its one permission sentence cites a flag value the launcher never emits | `orchestrate SKILL.md:318` | `completeness-audience-prerequisites` | documentation | yes |
| P2-19 | A stale instruction one screen below still tells the reader to confirm model, effort and permissions through the multiplexer, which the rewritten paragraph says publishes none of them | `SKILL.md:161` | `terminology-cross-document-consistency` | documentation | yes |
| P2-20 | The recorded rationale for the minor version bump calls two scalar-to-tuple return changes "additive"; the number is right, the reason is not, and the reason is what a future release reuses | `run plan:1179` | `versioning-deprecation` | api-contract | no |

**Adjudication on P2-14.** The documentation lens rated this P1 and the other two rated it P2. I
carried it as P2: no lens executed the documented command against a live multiplexer, and the
consequence is a misleading exit status rather than a defeated guard. The operator should know the
disagreement exists, because the finding is the original defect's own species — a document
overselling what a check delivers — reappearing in the fix for it.

### P3 — 22 findings

| # | Finding | File:line | Pre-existing |
|---|---|---|---|
| P3-1 | `confirmed_against_herdr` gains `"account"` when the proof was a transcript file, contradicting the rule stated one screen earlier in the same commit | `launcher.py:1144` | yes |
| P3-2 | OpenCode's `auto` posture resolves to the same flag as `bypass`, now stamped with a machine-readable confirmation | `launcher.py:242` | yes |
| P3-3 | `input_box: "unreadable"` conflates a failed read with a successful read that found no composer line | `launcher.py:713` | no |
| P3-4 | The recency slack is pinned on the fresh side only; widening it from 1.0 to 30.0 leaves the suite green, readmitting the case the constant's own docstring names | `test_launcher_contract.py:581` | no |
| P3-5 | The contiguity rule the argv check leans on is untested; a set-membership rewrite survives | `launcher.py:1124` | no |
| P3-6 | Two doc-lint guards will fail the suite on innocuous future edits — a bare word in any README fence, and any 20-character run with three capitals | `test_launcher_contract.py:1308` | no |
| P3-7 | A fixture installs the launcher at 1.0.0 and asserts it resolves cleanly, so the suite declares a floor and demonstrates that violating it is fine | `tests/test_agent_launcher_plugin.py:248` | yes |
| P3-8 | The receipt has four write sites, two key sets and no declared shape, while the repository's own receipt pattern solves this next door | `launcher.py:1160` | yes |
| P3-9 | One named pattern shipped in two encodings by two consecutive units — a flat string and a nested object for the same idea | `launcher.py:1167` | no |
| P3-10 | No `DECISIONS.md` entry for the receipt-channel pattern or the styled-versus-unstyled heuristic, against the repository's same-commit rule | `LEARNINGS.md:24` | no |
| P3-11 | The close docstring says no caller raises; a caller in the same file raises on exactly that failure, rebuilding the message from scratch | `launcher.py:827` | no |
| P3-12 | Two fresh copies of error-message construction that helpers already own | `launcher.py:1215` | no |
| P3-13 | The plan parser now prints to stdout while every other thing it detects raises | `orchestrate.py:958` | no |
| P3-14 | A wrapper genuinely exiting 124 is reported as a timeout and its stderr is dropped, though the synthetic case carries an unambiguous marker | `launcher.py:1208` | no |
| P3-15 | `permission_declared` is persisted into every run record with no reader; a record written by the new version raises a bare traceback on the old one | `orchestrate.py:251` | yes |
| P3-16 | The launcher is chosen by lexicographic sort, which breaks at a two-digit minor; the plugin's own documented resolver uses a version-aware sort | `orchestrate.py:1524` | yes |
| P3-17 | A valid JSON scalar is now rejected as "neither an existing file nor JSON", which is untrue and points at a redirect already done | `launcher.py:1532` | no |
| P3-18 | The recency floor proves a roughly 45-second window rather than this session, because it is captured before a create plus a readiness wait plus a settle loop, and has no session identifier to match on | `launcher.py:926` | no |
| P3-19 | The permission-cycle sentence describes an external client's control cycle, is unverifiable from this checkout, carries no attribution, and sits in a vendor-neutral paragraph covering seven vendors | `SKILL.md:34` | no |
| P3-20 | The journal entry says the plugin-named test module holds only release surfaces; half its tests run an installed Orchestrate under subprocess and assert preflight behaviour | `LEARNINGS.md:30` | no |
| P3-21 | The runtime checkpoint reproduces an empty-box receipt as carrying `input_box_text: None`; the code writes that key only on the staged branch, so it is absent | `runtime-checkpoint.md:105` | no |
| P3-22 | The topology deviation record quotes the unknown-posture stop as an "exact message" while truncating the half naming the accepted values | `topology-deviation.md` | no |

---

## The six areas the brief asked me to look at hardest

**1. Coexistence — clean inside the launcher, broken across the plugin boundary.** No later unit
undoes an earlier one within `launcher.py`; three units extended one call site in order, each
reusing what the previous introduced, and the two units touching the verification block add disjoint
code. But the units do not coexist with their consumer: the close-failure record shipped by one unit
is erased by Orchestrate's launch handler (P2-3) and discarded by its sweep (P2-4), and the guard
shipped by another is bypassed on one vendor by pre-existing code in the same function (blocking
finding 5).

**2. Harness substitution — found, and it is the guard's whole failure surface.** Nine of the run
plan's named mutation proofs were re-run and all nine died correctly, including the hardest: a real
shell wrapper killed by a real subprocess deadline. The substitution is concentrated in one place —
the guard's fixtures. Its failure branch, its timeout, and its parser's real input shapes are all
represented by a fake the test wrote, and three separate mutations of that region leave the suite
green.

**3. The recency slack — the 1.0 second is not the window.** The floor is captured as wall clock
before the wrapper runs, and the last transcript check happens after the create, after a readiness
wait of up to 30 seconds, and inside a 10-second settle loop. The real exposure is roughly 45
seconds after the launch instant plus 1 before it, and the check has no session identifier to match
on, so it certifies recency rather than authorship (P3-18). Exploitability is low because each unit
gets its own worktree. The stale side of the boundary is also untested — 30 seconds of slack passes
(P3-4).

**4. The release surfaces — clean.** Three floor assertions moved to `>=1.1.0` and three shape-check
assertions correctly stayed at `>=1.0.0`, because those use the old string as arbitrary well-formed
input to a dependency-shape test rather than as a floor. Both plugin manifests, the registry, both
changelogs and the prose sentence all moved together, and reverting any of them turns the suite red.
The one unmoved fixture version is a discovery-path fixture, not a floor assertion — correctly left
alone as a fixture, though it now asserts the opposite of what the manifest declares (P3-7). What is
missing is enforcement: the floor is a metadata declaration with no runtime check behind it (P2-12).

**5. Proportionality — nothing to flag.** No supervisor, daemon, lock file, registry, broker,
telemetry sink, or admission control entered the diff. The Orchestrate change is one dataclass field,
one assignment, and one printed line. The one heavy addition — roughly thirty lines of
secret-safety doctrine plus eleven prose-lint tests — was specified by the accepted run plan and
recorded in the committed document review, so it is the plan author's scope decision rather than the
implementing unit's. Two of those lint guards will bite innocuous future edits (P3-6).

**6. Scope — clean.** Nothing touches the external wrapper, which lives outside this repository.
The only new multiplexer interaction is one additional pane read per unowned launch, bounded at five
seconds. The Orchestrate change is confined to the single unit-model field that was permitted.

---

## Coverage — what was checked and found clean

Recorded so the operator can tell coverage from silence.

- Every vendor and posture pair in the permission ladder was enumerated; the tightened resolver
  fails toward less privilege in all of them and no legitimate combination now dies.
- All six call sites of the changed close function were traced; none mis-reads the new `None` case.
- The receipt survives version skew in both directions. An older launcher closing a newer receipt
  and a newer launcher closing an older one both exit 0 and issue exactly one close. The receipt is
  additive; no migration is missing.
- Orchestrate's fallback stub name list still covers every launcher symbol Orchestrate references,
  and every command that touches one gates on the availability assertion first.
- The corrected dry-run sentence was checked clause by clause against the wrapper's own source. All
  four clauses are true: the dry-run path prints the working directory, the workspace and the
  command, then exits 0 with no model, effort, or account validation anywhere on it. **The original
  defect is genuinely fixed.**
- The secret-safety contract is internally consistent and its own example obeys its allowlist. Its
  guard tests are real rather than assertions that happen to hold, including a mutation proof that
  feeds a known-bad fixture through the same detector.
- No credential material appears in any of the four run-record documents. The only identifiers are a
  local username and path this repository already carries in hundreds of places.
- Standard library only. No third-party dependency was added.
- No threads, no pool, no async anywhere. The concurrency half of two dimensions has no path to
  exercise, which is why they scored on their other halves.
- The journal entry's primary claim holds, including its mutation proof: keying the guard on the
  wrapper's reuse bit instead of on ownership does fail the named test.
- The primary worktree was verified clean at the frozen commit after every lens returned. One lens
  reported that a shared scratchpad copy of the source was mutated mid-run by a sibling lens; it
  discarded that run and re-verified against a private copy whose checksum matches the frozen blob.
  No mutation reached the repository.

## What this review did not verify

- The 24-step gate was not run. Two lenses ran lint and format clean on every changed surface; the
  other 22 steps are unverified here.
- No live multiplexer or vendor client was driven. Three claims rest on code reading rather than
  measurement: which escape spellings live clients emit around their composer, what the multiplexer
  returns for closing a nonexistent tab, and what an empty prompt does on a real host.
- The claim about an external client's in-session permission cycle is unverifiable from this
  checkout and is recorded as unverified rather than as either true or false.

---

## Routing

Read-only review. No reviewed code was edited, nothing was committed, nothing was pushed.

The five blocking findings are the merge gate. Four of them belong to the input-box guard shipped for
issue 897, and the honest summary is that **the unit's stop works on the one shape it was tested
against and fails open on several it was not.** The other blocker is a disclosure channel that turns
an operator's terminal draft into repository content.

The seven-lens selection is recorded against this commit and this cycle. Reuse it on a repair cycle
unless applicability changes; if it does, ask once about only the delta.
