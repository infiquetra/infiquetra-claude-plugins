# Doc review — issue 1036 plan, widen-only unions for the parse_issue flags and the journal nudge

The plan is ready to drive implementation. Six findings were raised across two rounds; five were repaired in the document and one is an accepted, already-disclosed limitation. Nothing is blocked.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-1036-widen-only-unions-plan.md` |
| Reviewed revision | working tree, base commit `866d3670` |
| Blocked | no |
| Rounds | 2 — round 1 raised 6, round 2 clean |
| Findings | 6 raised, 5 fixed, 1 accepted, 0 open above `P3` |
| Highest open priority | `P3` (accepted) |
| Review artifact | `docs/reviews/doc-review-issue-1036-2026-09-19.md` |
| Linked issue | infiquetra/infiquetra-claude-plugins#1036, parent #1019 |
| Saga | `issue-1036`, plan tick written 2026-09-19 |
| Override rationale | not applicable |

## Classification

A plan document, by both path (`docs/plans/`) and content signals (`origin:` frontmatter, `Key Technical Decisions`, `Implementation Units`, the `U1` prefix). The formal rubric engine covers the idea and issue phases, not plans, so no rubric run applies here; the readiness-skeptic pass ran in full, with the security and external-integration lens triggered because the plan sends repository content to a third-party vendor and reads a credential from the environment.

## Findings

| Key | Priority | Status | Finding |
|---|---|---|---|
| D1 | P1 | fixed | The widened hook had no reliable source for the commit message |
| D2 | P2 | fixed | The plan named four saga documents without naming or counting them |
| D3 | P2 | fixed | No runnable verification section |
| D4 | P2 | fixed | The issue-fetch command implied a required repository argument |
| D5 | P3 | fixed | The union primitive's signature omitted the overall deadline and left two loading details unstated |
| D6 | P3 | accepted | Both thresholds are unmeasured guesses |

### D1 — the widened hook had no reliable source for the commit message (P1, fixed)

The hook's existing `_extract_commit_message` parses the message out of the shell command string and handles only the `-m` forms (`plugins/saga/hooks/journal_nudge_hook.py:71-88`). A commit written with a here-document or with `-F` yields an empty string, so the model would have been asked to judge a bare file list — and would have judged it badly and silently.

Fixed in unit U4: the widen path reads the real message with `git show -s --format=%B HEAD`, mirroring the `git show` call the hook already makes on HEAD, and falls back to the parsed string. The `feat`/`fix` floor still reads the parsed string, so nothing about today's behaviour narrows.

### D2 — unnamed and uncounted documents (P2, fixed)

Unit U5 said "the saga skill documents that read the flags". A count of four and the exact paths with line numbers now stand in its place, and a risk row was added because prose edits to those files are guarded by saga's own drift tests.

### D3 — no runnable verification (P2, fixed)

The plan mapped the card's acceptance criteria to units but gave the implementer no commands. A Verification section now carries the test, lint and type commands, and says plainly which single command reaches the vendor and what happens without the key.

### D4 — the issue-fetch command implied a required repository argument (P2, fixed)

The plan showed `gh issue view <N> --repo <owner/repo>` as the fetch. The GitHub command infers the repository from the working directory, so the argument is an optional override; the plan now says so, which keeps the new `--repo` option from being written as mandatory.

### D5 — an incomplete primitive signature (P3, fixed)

The `widen()` signature omitted the overall deadline parameter, did not name its default `ask`, and did not say how it reaches the verdict-log module. All three are now stated, the last by pointing at the existing loader at `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py:796`.

### D6 — both thresholds are unmeasured (P3, accepted)

0.70 for the issue flags and 0.60 for the journal nudge come from reasoning about which mistake is cheaper, not from measurement. This is disclosed in decision KTD4 rather than dressed up, every verdict records the threshold that was in force, and the measurement is parent issue 1019's own acceptance criterion. No action is available inside this card, so the finding is accepted rather than fixed.

## Residual risk

Two risks survive the review and are carried in the plan's own risk table rather than here: the latency the hook adds to every commit, bounded by a single attempt and a three-second deadline with a documented off switch, and the chance that the widened flags fire the test gate too often, which only real verdicts can settle.
