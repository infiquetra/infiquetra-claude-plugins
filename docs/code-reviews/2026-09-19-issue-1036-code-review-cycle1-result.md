---
reviewed_revision: 4c97ebdd9e4650f625acde3d01b77f3a2e2dfcf4
---

# Code review — issue 1036, cycle 1

The change is accepted. Seven findings, none above P2; three were repaired during the review and four are recorded residuals, none of which blocks.

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `issue/1036` |
| Base | commit `866d3670` on `main`, confirmed as the merge base with `origin/main` |
| Reviewed commit | `4c97ebdd9e4650f625acde3d01b77f3a2e2dfcf4` (`fix(saga): close three gaps the code review found in the flag union`) |
| Mode | the skill's default, run by the card driver |
| Outcome | `accepted` |
| Derived overall | 9.3 of 10 |
| Lowest applicable dimension | 8.0, agent-usability `machine-readable-output-actionable-errors` |
| Acceptance rule | overall at or above 9.0 and every applicable dimension at or above 7.0, per `plugins/saga/references/lens-roster.json` |
| Findings | 7 total: 0 at P0, 0 at P1, 1 at P2, 6 at P3 (3 repaired, 4 recorded) |
| Cycle | 1 of a possible 3; no repair cycle was needed |
| Saga | `issue-1036` |
| Linked issue | infiquetra/infiquetra-claude-plugins#1036, child of parent #1019 |
| Plan | `docs/plans/2026-09-19-issue-1036-widen-only-unions-plan.md` |
| Work session | `docs/work-sessions/2026-09-19-issue-1036-widen-only-unions.md` |
| Artifact | this file |

The three repairs this review produced landed in the reviewed commit, and every gate below was re-run at that revision rather than inherited from the one before it.

**On freshness.** `git rev-list 4c97ebdd..HEAD --count` reports 1, and that one commit is the one adding this file — a document the review itself produced, carrying no reviewed code. The freshness rule exists because code moved after the review; no code moved. Stated here rather than left for a reader to work out from the commit list.

## How this review was run

The caller approved the recommended lens set (`accept-recommended`) in its launch message. A caller-supplied selection is an approval record under the skill's own contract, so the operator question was not asked again.

**Transport deviation, recorded.** The caller forbade spawning subagents, so the lens pass ran in this thread, one lens at a time, instead of as parallel read-only verifier agents in disposable worktrees. That changes who executed each lens, not which lenses ran or what each was asked. Sibling cards merged today recorded the same deviation.

- **Always-on:** correctness, security, testing, architecture and maintainability.
- **Conditional, approved:** adversarial (the whole change rests on one load-bearing assumption — that the model can only widen); application-programming-interface contract (a command-line surface and a machine-readable output shape both grow); reliability (an outbound call joins a per-commit hook, with a fail-open policy); performance (that call's latency is paid on every qualifying commit); privacy (repository content leaves the machine for a third-party vendor); documentation clarity (a reference section, four skill documents, two changelogs and four journal entries ship together); agent usability (four saga skills read this script's output); accessibility and human usability (the nudge text and the command-line help are operator-facing).
- **Not selected:** deployment and infrastructure — the version bumps are release surfaces that the parity and diff guards already cover, and no infrastructure, deployment configuration or migration is touched. Previous comments — no pull request exists yet.

## Scope check

**Result: clean.** Intent, from the card and the plan: give the five issue-body flags and the journal nudge a model judgment each, unioned widen-only, through the fleet-core client. Delivered: exactly that, plus the seven advisory approval boundaries the card names, the release bookkeeping both bumped plugins require, and the journal entries this repository requires to ship with a behavior change. No file in the diff is unrelated to that intent.

## Plan-completion audit

| Requirement | Verdict | Evidence |
|---|---|---|
| R1 — every judgment goes through the fleet-core client | done | `jev_widen.widen` calls `typesafe_client.ask`; neither caller contains a URL, a request, or a header |
| R2 — the union is widen-only | done | One expression at `jev_widen.py:208`; mutating it to drop the floor reds `test_a_regex_floor_survives_a_confident_no`, watched failing and then passing |
| R3 — the nudge sends the message and the file list only | done | `test_the_judgment_sends_only_the_message_and_the_file_list` asserts the exact state mapping |
| R4 — the key is read from the environment and never printed | done | Every `note` the callers print is composed by this repository (`typesafe_client.py:601-640`); no new reference to the key name exists in `plugins/` |
| R5 — the hook exits 0 in every case | done | Twenty hook tests, one per failure mode, each asserting exit 0; the pre-existing thirty-one still pass unchanged |
| R6 — every test uses a fake client and no network | done | `ask` and `widen` are injected parameters; `test_the_injected_ask_is_the_only_call_path` asserts the fake was the callee |
| R7 — the default `parse_issue` path is unchanged | done | `test_without_flags_the_output_is_exactly_what_it_always_was` pins the key set; the fleet-core import is inside the `--flags` path |
| R8 — each judgment is logged as a verdict | done | `test_every_answered_question_writes_a_verdict` checks the resolved model and threshold in a temporary log directory |
| R9 — suggest mode; nothing acts on an answer by itself | done | No gate reads `approval_boundaries`; the nudge prints one line; the flags feed a gate that only ever gains a lens |

Unit completion: U1 through U5 all **done**. The acceptance criterion was additionally verified live against the real endpoint — see below.

## Live verification

`uv run python plugins/saga/scripts/parse_issue.py --issue 1036 --flags` was run against the real endpoint. Model `jev-1.13.0`, threshold 0.70, every one of the twelve categories printed with its keyword result, its probability and the union.

It reproduced the motivating case: `has_security` has `regex: false` and `probability: 0.76`, so the union is `true` with `source: model` — the flag the keyword floor missed on this card's own body is now set. `has_api` widened the same way at 0.73. The seven approval boundaries all came back below the threshold, the highest being `production` at 0.49, so none was raised.

## Findings

| ID | Priority | Lens | Status | Finding |
|---|---|---|---|---|
| F1 | P2 | correctness, testing | repaired | The caller's key constants and the verb's question keys had no guard |
| F2 | P3 | reliability | repaired | `parse_issue` failed open over client failures but not over the primitive's own faults |
| F3 | P3 | api-contract | repaired | `--repo` was accepted without `--issue` and silently ignored |
| F4 | P3 | reliability | recorded | One logging failure abandons the remaining verdicts |
| F5 | P3 | api-contract | recorded | `judgment.threshold` is `null` on the keyword-only path and a number otherwise |
| F6 | P3 | architecture | recorded | A third copy of the sibling-module loader idiom now exists in fleet-commons |
| F7 | P3 | agent-usability | recorded | Nothing tells a reading agent what to do with `approval_boundaries` |

### F1 — the key seam had no guard (P2, repaired)

`widen()` reports a question key the answer does not carry as "missing" and returns that key's floor. That is right for a vendor that omits an answer, and it is also what happens when the caller's constant and the registry's question key stop agreeing — so a rename on either side would quietly stop asking about that category rather than fail. Renaming `has_refactor` in the registry produced no failure at all before the guard existed.

`tests/test_parse_issue_flags.py::test_parse_issue_key_constants_and_the_issue_flags_verb_name_the_same_keys` now loads both modules and asserts the sets are equal. It was watched failing against the renamed key, then the rename was reverted and it passed. Recorded as LEARNINGS `{#1036-fail-open-hides-a-renamed-key}`.

### F2 — fail open did not cover the primitive's own faults (P3, repaired)

`widen()` converts every *client* failure into a floors-only result, but an unknown verb raises `ValueError` and any bug in the primitive raises whatever it raises — either of which would have killed `parse_issue.py` with a traceback. Four saga skills read this script's JSON, and the promise they rely on is that the JSON still prints. The call is now wrapped and returns the keyword result with the exception type named in `note`.

### F3 — `--repo` without `--issue` (P3, repaired)

The option only applies to the `gh` fetch, and passing it alone did nothing silently. It is now a usage error at exit 2, matching the neighbouring mutual-exclusion check.

### F4 — one logging failure abandons the rest (P3, recorded)

`_record` returns on the first exception rather than continuing to the next key, so a transient write failure on the first verdict loses the other eleven. Accepted: logging is explicitly best-effort, the union is already computed by then, and the realistic cause — a full disk or an unwritable directory — would fail for every key anyway. Continuing would turn one failure into twelve.

### F5 — `judgment.threshold` has two types (P3, recorded)

It is a number when the model answered and `null` when nothing was asked. A consumer typing that field sees both. Accepted: `asked` is the field that says which case it is, and it is a boolean; the two are meant to be read together.

### F6 — a third loader copy (P3, recorded)

`jev_widen._load_sibling` joins `typesafe_client._load_log_module` and the module-scope `retry_backoff` loader as a third spelling of "load a sibling through the shim, fall back to a path load". `_load_sibling` is the generalized form, so the right follow-up is for the other two to use it rather than for a fourth to appear. Not done here: it would mean editing a module this card otherwise only reads.

### F7 — `approval_boundaries` has no consumer guidance (P3, recorded)

The reference document says plainly that the seven categories report and never approve, but the four skill notes mention only `--flags`. An agent reading the output has to find the reference to know what the key is for. Accepted: the reference is the correct home for a policy statement, and inventing per-skill guidance for a key nothing reads would be worse.

## Lens scores

| Lens | Score | Lowest applicable dimension |
|---|---|---|
| Correctness | 9 | 9 |
| Security | 10 | 10 |
| Testing | 9 | 9 |
| Architecture and maintainability | 9 | 8, on convention reuse (F6) |
| Adversarial | 9 | 9 |
| Reliability | 9 | 9 |
| Performance | 9 | 9 |
| Privacy | 10 | 10 |
| API contract | 9 | 9 |
| Documentation clarity | 10 | 10 |
| Agent usability | 9 | 8, on machine-readable output (F7) |
| Accessibility and human usability | 9 | 9 |

Derived overall 9.3; every applicable dimension at or above 8.0. Both acceptance rules hold.

## Notes the lenses recorded rather than raised

**Security.** Every string either caller prints comes from this repository, not from the vendor: `typesafe_client` re-raises vendor exceptions with text it composes, so no response body and no credential can reach a `note` that `parse_issue.py` prints to standard output. `subprocess.run` is called with a fixed argument vector and no shell in both new call sites.

**Adversarial.** A crafted issue body can make the model raise every flag. That only widens a mandatory test gate, so the failure direction costs extra review and never removes any — which is the property the whole design is built around. A vendor answering `{"type": "noul", "noul": true}` is rejected: `_probability` excludes booleans explicitly before the numeric check.

**Performance.** The hook's call is skipped entirely when the `feat`/`fix` floor already nudged, when the commit carries a journal entry, when no code file was touched, and when the switch is off. What remains is bounded to one attempt inside a three-second deadline.
