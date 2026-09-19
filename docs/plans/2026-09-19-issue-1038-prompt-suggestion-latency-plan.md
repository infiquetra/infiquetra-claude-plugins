---
title: Prompt-submission skill suggestion — measuring whether a hook can be fast enough
type: docs
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-18-typesafe-jev-integration-research.md
backend: inline
deepened: 2026-09-19
---

# Prompt-submission skill suggestion — measuring whether a hook can be fast enough

## Summary

This plan builds a measurement harness that times six candidate shapes of a `UserPromptSubmit` hook that suggests a saga command from the operator's prompt text, using the TypeSafe client that issue 1032 shipped in fleet-core.

It produces one document, `docs/analysis/2026-09-19-prompt-suggestion-latency.md`, carrying measured per-shape latency, measured suggestion accuracy on a synthetic prompt corpus, and a keep, defer, or drop recommendation decided by a rule written down here, before any number is known.

It is an exploration with a one-working-session timebox. It ships no hook, registers nothing, and changes no plugin.

## Problem Frame

The research document `docs/analysis/2026-09-18-typesafe-jev-integration-research.md` lists twenty-eight recommended changes and flags exactly one as unproven: recommendation 26, the skill suggestion on prompt submission. Its section 7.3 gives the reason in one line — the TypeSafe API answers in about 0.3 to 0.4 seconds from this machine, but a cold Python process plus a TLS handshake on top of that was measured by the `codex-context-diet` project at 1.07 to 1.94 seconds per invocation, and an earlier two-second deadline in that project silently timed out on two of eight real runs.

A hook that fires on every prompt the operator types pays that cost every time. If the cost is a second and a half, the operator notices it on every single turn, and no amount of suggestion accuracy makes that worth having. The card sets the bar at a 95th-percentile latency of 400 milliseconds.

Here is the uncomfortable arithmetic this plan exists to test rather than assume. One live API call from this machine measured at 332 to 428 milliseconds across the six probes on 2026-09-18 that recorded a latency, one of which reported two figures at different payload sizes. The vendor's own skill-suggestion cookbook uses **two sequential requests** per prompt — a wide ranking over the whole roster, then a verification pass over the top three candidates. Two sequential calls at this machine's measured per-call latency land between 0.66 and 0.86 seconds before a single millisecond of process, import, or socket cost is counted. So the plausible finding going in is that **no shape which makes a blocking API call on the critical path can meet a 400 millisecond target from this machine**, and the only shapes that could are the ones that do not block on a call at all: a cache hit, or a suggestion computed for the next prompt rather than this one.

That hypothesis is why the shape list below deliberately includes shapes with no blocking call. An exploration that only measured the cookbook's shape would report "too slow" and stop, which answers half the card's question. The card asks which persistent local client shape makes the target true, and a shape that moves the call off the critical path is a candidate answer, not a cheat.

## Requirements

**R1.** Every live measurement calls the TypeSafe endpoint through `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py`'s `ask()`. No bespoke HTTP path, no direct vendor SDK call, no hand-rolled request. Measuring around the shipped client would measure a client we are not going to use.

**R2.** The API key is read from the `TYPESAFE_API_KEY` environment variable by the client's own environment reader. The harness never reads it, never prints it, never writes it to a results file, and never puts it in the document.

**R3.** Every prompt sent to the model is synthetic, written for this exploration. No real operator prompt, no session transcript, no issue body, no customer content. This is the fleet-core data rule recorded in `plugins/fleet-core/references/typesafe.md` section 1.

**R4.** The harness times what Claude Code actually pays: wall clock from immediately before the hook process is spawned to immediately after its standard output has been fully read and the process has exited. An in-process timing number is not the hook's cost and is not reported as one.

**R5.** The harness measures at least the six shapes named in the Key Technical Decisions below, plus a do-nothing floor: a hook process that starts, connects to nothing, prints nothing, and exits. If the floor alone exceeds 400 milliseconds, the question is settled before any client design matters.

**R6.** Each shape reports the number of trials, the 50th percentile, the 95th percentile, the minimum and the maximum, in milliseconds. The 95th percentile of a thirty-trial sample is a wide estimate and the document says so rather than presenting it as a pinned figure.

**R7.** Shapes are run interleaved, one trial of each in rotation, not in per-shape blocks. This machine is shared with other card drivers whose test runs come and go, and a load spike during a block would land entirely on one shape and be indistinguishable from that shape being slow.

**R8.** Any persistent process the harness prototypes is started by the harness and stopped by the harness in a `finally` block that runs on success, on failure, and on interrupt. The harness prints the process identifier it started and, at the end, confirms that identifier is gone. Nothing is left running after the session and nothing is installed to start on boot.

**R9.** The harness records suggestion correctness alongside latency for every shape that produces a suggestion, scored against the expected command recorded with each synthetic prompt. A fast wrong suggestion is worse than no suggestion, so latency alone cannot support a keep recommendation.

**R10.** The harness answers the card's three key questions with evidence, not assertion: whether a persistent process survives repeated separate hook invocations; which fleet-core resolution rung each of the two installed plugin trees uses, observed through `FLEET_COMMONS_DEBUG=1`; and what state a suggestion needs, where that state lives, and what makes it go stale. How much staleness is tolerable is not answered by inspection — it is answered by shape S5's accuracy, which is what a one-prompt-stale suggestion scores.

**R11.** Tests for the harness use a fake client injected through the existing seams and touch no network. `ask()` already takes `urlopen`, `getenv`, `clock` and `sleep` as injection parameters, so a fake is a parameter, not a monkeypatch.

**R12.** The keep, defer, or drop rule is written into this plan before any measurement runs, and the document applies that rule to the numbers rather than composing a recommendation to fit them.

**R13.** No plugin release surface changes. The harness lives outside `plugins/`, so no `plugin.json` version, no marketplace entry, and no changelog entry is touched. If that ever stops being true, the release surfaces move in the same pull request.

### Which unit advances which requirement

| Requirement | Advanced by |
|---|---|
| R1 shipped client only | U3, U4 |
| R2 the key stays in the environment | U2 (results-file guard), U3, U4 |
| R3 synthetic prompts only | U1 |
| R4 time what Claude Code pays | U2 |
| R5 six shapes plus the floor | U3, U4 |
| R6 trial count beside every percentile | U2, U6 |
| R7 interleave the shapes | U2 |
| R8 harness-owned start and stop | U4 |
| R9 accuracy beside latency | U1, U6 |
| R10 the card's three key questions | U5 |
| R11 fake client, no network in tests | U2, U3, U4, U5 |
| R12 the rule precedes the numbers | KTD5, applied in U6 |
| R13 no release surfaces move | U1 through U6, by construction |

## Key Technical Decisions

**KTD1 — the harness lives at `tools/prompt_suggestion_latency.py`, not as a `.py.txt` file under `docs/analysis/`.**

The research-folder convention stores probe scripts as `jev.py.txt` and similar precisely so repository linting skips them; `docs/analysis/2026-09-18-typesafe-jev-research-inputs/` holds five such files. That convention buys nothing here and costs the two things this harness needs. Repository linting runs `ruff check .` across the whole tree, which covers `tools/` (`.github/workflows/ci.yml:194`), so a harness under `tools/` is linted; type checking covers `plugins/ scripts/ tests/` only (`ci.yml:260`) and coverage measures `plugins` only (`pyproject.toml:99-101`), so `tools/` adds no type-checking or coverage burden. A test can load it: `tests/test_agent_spec_lint.py:20` already loads `tools/agent_spec.py` by path. *Rejected:* the `.py.txt` form, which cannot be linted and cannot be imported by a test, which would make requirement R11 unsatisfiable.

**KTD2 — six shapes are measured, chosen so the answer does not depend on the cookbook's shape being the only one.**

| Shape | What it is | What it isolates |
|---|---|---|
| S0 | Cold process, one API request | Our own cold-process figure on this machine, replacing a borrowed one |
| S1 | Cold process, two sequential API requests | The vendor cookbook's faithful shape; the realistic upper bound |
| S2 | Warm local process, two sequential API requests | What removing interpreter start, imports and the TLS handshake buys |
| S3 | Warm local process, one API request | What dropping the verification pass buys, and what it costs in accuracy |
| S4 | Warm local process, answer cache hit | The latency floor when no network call happens at all |
| S5 | Warm local process, no blocking call: the suggestion is computed for the next prompt | The only shape that can plausibly meet the target, at the cost of a one-prompt-stale suggestion |

Plus the do-nothing floor from R5, which is not a shape but the irreducible cost of having a hook at all.

*Rejected:* measuring only S0 and S1. That reproduces the research document's existing figure and answers "is the cookbook shape too slow", not the card's actual question, which is which client shape makes the target reachable.

**What S4 does not measure.** A cache is only worth having if real operator prompts repeat, and a twenty-entry corpus of deliberately distinct synthetic prompts cannot tell us how often that happens. S4 therefore measures cache-hit latency and nothing else. The hit rate a real prompt stream would produce is unmeasurable from this corpus and is named in Scope Boundaries as deferred, not reported as a number.

**KTD3 — the persistent process listens on a Unix domain socket under the session scratch directory, not on a localhost TCP port.**

The card's constraint is that any persistent prototype is bound to localhost. A Unix domain socket satisfies that constraint more strictly than a localhost port does: it has no port number, it is not reachable from any network stack, and access is governed by ordinary filesystem permissions on the socket path. Taking the stricter reading of a constraint needs no operator ruling. *Rejected:* a localhost TCP port, which is what the card's wording suggests and which would be measured only if the Unix socket proves unusable for a reason the harness discovers; if that happens the document records the reason and the fallback.

**The socket is owner-only, and that is not a detail.** The resident process holds a live API credential and answers whatever connects to it, so a socket any local account could open would let any process on this machine spend the operator's key and send it text of its choosing. The process creates its socket with owner-only permissions, inside a directory that is itself owner-only, and refuses to start if either check fails — refusing to start is the right failure, because a prototype that silently downgrades its own access control is exactly the kind of thing that survives into an implementation. A localhost TCP port has no equivalent control available without inventing an authentication scheme, which is a second reason the socket wins.

**KTD4 — both transports are measured, because a hook cannot assume the vendor package is importable.**

The client ships two transports behind one `ask()`, selected by `INFIQUETRA_TYPESAFE_TRANSPORT` (`typesafe_client.py:80-85`), and the decision recording that choice says in terms that the out-of-project case is real rather than hypothetical (`docs/engineering-journal/DECISIONS.md`, `{#typesafe-two-transports-1032}`, KTD1). Import cost is exactly the kind of thing that dominates a cold-process budget and is invisible in a warm one, so the cold shapes S0 and S1 are measured on both transports and the difference is reported. The warm shapes use whichever transport the cold measurement shows is cheaper to keep resident.

*Rejected:* measuring the vendor package's transport alone, which would produce a cold-process figure that no hook can rely on reproducing, since the package is only importable inside this project's environment.

**KTD5 — the keep, defer, or drop rule, fixed here before any number exists.**

*Keep* requires both halves: some shape reaches a 95th-percentile latency at or under 400 milliseconds, **and** that same shape clears both accuracy bars below. *Defer* is the verdict when the latency target is met only by shape S5, whose suggestion is one prompt stale, or only by a shape whose accuracy was not measured — in both cases the mechanism is promising and the evidence is incomplete, which is what deferral means. *Drop* is the verdict when no shape reaches 400 milliseconds and the cheapest failing shape is still slow enough that the operator would feel it on every turn.

**The two accuracy bars, fixed now.** On the corpus's positive entries — the prompts that do warrant a command — the shape names the expected command for at least 70 percent of them. On the corpus's negative entries — the prompts that warrant nothing — the shape stays silent for at least 80 percent of them.

Both numbers are pre-commitments, and the grounding for each is stated so a reader can judge the bar rather than take it on faith. The 70 percent positive bar comes from the research document's own saga-command routing probe, which put four of five raw asks on the right command with confidence at or above 0.87 and correctly showed the genuinely ambiguous fifth as ambiguous; a suggester that cannot reach 70 percent on prompts written to be routable is worse than that probe on easier input. The 80 percent negative bar is stricter than the positive one on purpose: the vendor's cookbook reports the pattern cutting needless loads from 9.8 percent to 4.0 percent, so quiet-when-it-should-be-quiet is the property the pattern is actually good at, and a suggester that interrupts the operator on one prompt in five is a nuisance whatever its hit rate on the rest.

The rule exists because a recommendation written after the numbers are known is a rationalization of the numbers, and a bar chosen after the numbers are known is the same failure wearing a threshold. *Rejected:* deciding the rule, or either bar, at write-up time.

**KTD6 — the prototype hook fails open, silently, on a hard client-side deadline.**

A hook that cannot reach the persistent process, or whose read exceeds its deadline, prints nothing and exits zero. It never blocks the prompt and never delays it past the deadline. This mirrors `plugins/saga/hooks/journal_nudge_hook.py`, which exits zero on every path including its own errors. The timeout path is itself measured, because a fail-open path that takes a second to decide to fail is not fail-open in any sense the operator cares about.

*Rejected:* printing a diagnostic on failure. A hook that fires on every prompt and complains when its daemon is down would produce noise on every turn for as long as the daemon stayed down, which is a worse failure than the missing suggestion.

**KTD7 — whether a live operator prompt may be sent at all is an open operator decision, recorded and not answered here.**

The fleet-core data rule permits issue bodies, plan text, code-review findings and diffs after redaction, and forbids credentials, raw session transcripts, and customer content. A live operator prompt is not a transcript — it is one message — but it is uncontrolled operator-authored text that nobody vetted for this purpose, which is the stated reason transcripts are excluded. The production shape of this hook would send exactly that text on every turn.

This exploration does not decide the question, because it is a data-governance decision the operator owns. It measures with synthetic prompts (R3), records the question in the deliverable document, and names it as a precondition the follow-up capability card must resolve with the operator before any implementation begins. A keep recommendation is therefore a recommendation to keep *pending that ruling*, and the document says so in those words.

## Implementation Units

Six units in dependency order. U1 and U2 are independent of each other and both precede everything else; U3, U4 and U5 each depend on U2's runner and on U1's corpus; U5 additionally depends on U4's resident process, since the survival probe has nothing to survive without it; U6 depends on all five and is the only unit that touches the live endpoint in anger.

```
U1 corpus ──┐
            ├── U3 cold shapes ─────────┐
U2 runner ──┤                           ├── U6 run live, write the document
            └── U4 daemon ──────────────┤
                     └── U5 probes ─────┘
```

### U1. The synthetic prompt corpus and the question set

Writes the inputs everything else measures against: a set of hand-written operator prompts with their expected saga command, and the TypeSafe question set the shapes ask about them.

**Scope:** a JSON data file holding roughly twenty synthetic prompts. Each carries the prompt text, the saga command a competent operator would say it warrants, and an explicit "none" for the prompts that warrant no command at all. The "none" entries matter: a suggester that fires on everything is worse than one that stays quiet, and without negative cases accuracy cannot distinguish the two. The question set follows the cookbook shape — a choice over the installed saga command roster with three orientation yes-or-no questions for the wide pass, and one yes-or-no question per candidate for the verification pass. The roster is twenty-four commands, counted from the installed saga plugin's `commands/` directory at version 0.159.2, which is an order of magnitude smaller than the 182-skill roster the cookbook reports; the document says so, because a smaller roster makes the wide pass cheaper here than the cookbook's figures imply and that difference should not be read as our shapes being fast.

**Files:** `docs/analysis/2026-09-19-prompt-suggestion-latency-inputs/corpus.json`, `docs/analysis/2026-09-19-prompt-suggestion-latency-inputs/questions.json`.

**Test scenarios:** every corpus entry parses and carries a prompt, an expected command, and a note on why; every expected command is either the literal string `none` or a command that exists in the installed saga plugin's `commands/` directory; no corpus entry contains a path under the operator's home directory, an at-sign address, or a token-shaped string — a cheap mechanical guard that the corpus really is synthetic. `tests/test_prompt_suggestion_latency.py`.

**Verification:** the corpus holds at least fifteen prompts with at least three expecting no command at all, and every expected command resolves to an installed saga command file.

### U2. The harness core — timing, shape registry, interleaving, statistics

Builds the measurement skeleton with no shape implemented, so the timing discipline is testable without a network or a daemon.

**Scope:** a shape registry mapping a shape name to a callable; an interleaved runner that rotates through the registered shapes rather than running them in blocks (R7); wall-clock timing measured around a subprocess spawn and its output read (R4); percentile statistics that report the trial count alongside every percentile (R6); and a JSON results file. The percentile function is ordinary arithmetic and belongs in code, never in a model call — the house rules forbid using the model for arithmetic.

**Files:** `tools/prompt_suggestion_latency.py`.

**Test scenarios:** the interleaved runner with three fake shapes and five trials each calls them in rotation, which the recorded call order proves; the percentile calculation on a known fifty-value series returns the known 50th and 95th values; a shape that raises is recorded as a failed trial with its reason and does not abort the run or silently vanish from the results; the results file contains no key whose name matches the client's secret-name pattern. `tests/test_prompt_suggestion_latency.py`.

**Verification:** a dry run with three fake shapes writes a results file carrying, per shape, all five figures R6 names — the trial count, the 50th percentile, the 95th percentile, the minimum and the maximum — and the recorded call order shows rotation rather than blocks.

### U3. The cold-process shapes and the do-nothing floor

Establishes this machine's own cold-process cost rather than borrowing another project's figure, and establishes the floor below which no hook can go.

**Scope:** shape S0 (cold process, one request), shape S1 (cold process, two sequential requests), and the do-nothing floor — a process that starts, prints nothing, and exits. Each cold shape runs on both transports per KTD4. The cold shapes call `ask()` directly; the floor calls nothing.

**Files:** `tools/prompt_suggestion_latency.py`.

**Test scenarios:** shape S0 with a fake `urlopen` that returns a canned body records one call and a latency greater than zero; shape S1 records exactly two calls in sequence, not one and not two in parallel; the do-nothing floor makes no call at all, proven by a fake client that fails the test if it is invoked; a transport value the client does not recognize is reported as a failed trial carrying the client's own reason. Note for the implementer: `resolve_transport` raises, but `ask()` catches that exception and returns a result whose status is `error` with the reason in its `note` field (`typesafe_client.py:855-860`), so the assertion is on the returned status, not on a raised exception. `tests/test_prompt_suggestion_latency.py`.

**Verification:** the results file carries a cold-process figure for each of the two transports and a floor figure, and the floor is strictly below both.

### U4. The persistent local process and the warm shapes

Builds the prototype the card is actually about — a resident process the hook talks to — and the four shapes that depend on it.

**Scope:** a small process listening on a Unix domain socket (KTD3) that holds the client's connection state resident and answers a prompt with a suggestion; a thin client the harness spawns per trial, which is what the hook would be; shapes S2 (warm, two requests), S3 (warm, one request), S4 (warm, cache hit through the client's existing `cache_dir` seam), and S5 (warm, no blocking call — the trial returns the previous prompt's answer and enqueues this one). Start and stop are owned by the harness with a `finally` block, the started process identifier is printed, and its absence is confirmed at the end (R8). The thin client carries the hard deadline and the silent fail-open path from KTD6, and the timeout path is measured.

**Files:** `tools/prompt_suggestion_latency.py`, `tools/prompt_suggestion_daemon.py`.

**Test scenarios:** the harness stops the process it started even when a shape raises mid-run, proven by asserting the process is gone after a run that was made to fail; the thin client with no process listening prints nothing, exits zero, and returns within its deadline; the thin client against a process that accepts the connection and then never answers returns within its deadline rather than hanging; shape S4 with a pre-populated cache directory makes no network call, proven by a fake `urlopen` that fails the test if invoked; shape S5's first trial returns no suggestion and its second returns the first trial's answer, which is the defining property of the one-prompt-stale shape; the process creates its socket with owner-only permissions, and refuses to start when handed a directory whose permissions are wider (KTD3). `tests/test_prompt_suggestion_latency.py`.

**Verification:** the run prints the identifier of the process it started, the results carry a figure for all four warm shapes and for the timeout path, and a process listing after the run shows the identifier is gone.

### U5. The lifecycle and two-tree survival probes

Answers the card's first key question with observation rather than assumption: does a persistent process survive Claude Code's hook lifecycle and the two installed plugin trees?

**Scope:** a survival probe that starts the process once and then runs thirty separate thin-client invocations from thirty separate operating-system processes, confirming from the process's own reported identifier and uptime that all thirty reached the same resident instance rather than thirty fresh ones. A resolution probe that runs the thin client with `FLEET_COMMONS_DEBUG=1` under each of the two installed plugin trees and records which rung of the fleet-core resolution ladder wins in each — the ladder is documented in `plugins/fleet-core/scripts/fleet_commons_shim.py:9-21` and its third rung reads `~/.claude/plugins/installed_plugins.json`, a file this fleet has repeatedly found stale after a release. A staleness probe that records what state a suggestion would need — the saga run record's `next_step` field (`plugins/saga/scripts/saga.py:179`) and the installed command roster — and where that state lives, noting that saga state sits under a git-ignored `.claude/saga/` directory and is therefore per-worktree.

Both installed trees are read only. Nothing in either is modified.

**Files:** `tools/prompt_suggestion_latency.py`.

**Test scenarios:** the survival probe with a fake process reporter that returns two distinct identifiers across the run reports a survival failure rather than passing; the resolution probe records the rung name it observed and, when the debug output is absent, records that it is unknown rather than guessing a rung. `tests/test_prompt_suggestion_latency.py`.

**Verification:** the results carry a yes or no on survival with the observed identifier and uptime, a named resolution rung for each of the two installed trees, and a written statement of what state a suggestion needs and where it lives.

### U6. Run the measurements live and write the deliverable

Turns the numbers into the document the card asks for, applies the rule fixed in KTD5, and drafts the follow-up card body if the verdict warrants one.

**Scope:** run the harness against the live endpoint with the key from the environment; write `docs/analysis/2026-09-19-prompt-suggestion-latency.md` carrying the per-shape latency table, the accuracy table, the three key-question answers from U5, the machine conditions the run happened under, and the recommendation the KTD5 rule produces. If the verdict is keep or defer, draft the body of a follow-up capability card under parent issue 1019 into the document as a fenced block. The coordinator files it; this plan does not create issues.

The document states the trial count beside every percentile, names the data-rule question from KTD7 as an unresolved operator decision, and reports the recommendation as the rule's output rather than as a judgment formed afterwards.

**Files:** `docs/analysis/2026-09-19-prompt-suggestion-latency.md`, the results JSON under `docs/analysis/2026-09-19-prompt-suggestion-latency-inputs/`.

**Test expectation:** none -- this unit runs the already-tested harness and writes prose; it adds no behavior of its own. The harness is covered by U1 through U5, and a test asserting the content of a measurement document would either assert nothing or assert a number nobody has measured yet.

**Verification:** the document exists at the path the card names, every shape in the results file appears in its latency table with a trial count, the three key questions are answered, and the recommendation names the KTD5 branch it came from.

## Scope Boundaries

**Out of scope — true non-goals.**

Registering the hook. Issue 1029 adds the hook registration and has not shipped; this harness is standalone and adds no entry to `plugins/saga/hooks/hooks.json` or any other manifest.

Shipping a daemon. The persistent process built in U4 is a prototype that exists to be timed. It is not installed, not registered to start, and not left running.

Changing any plugin. No file under `plugins/` is modified, so no version, no marketplace entry and no changelog entry moves (R13).

Deciding whether a live operator prompt may be sent to the vendor. That is KTD7's open operator decision, recorded rather than answered.

Filing the follow-up issue. U6 drafts a card body; the coordinator files it.

**Deferred to follow-up work.**

Measuring on a second machine. Every figure here is from this machine under this machine's network conditions, and the document says so; a figure from elsewhere would strengthen the conclusion and does not fit the timebox.

Tuning the question set for accuracy. U1 writes a reasonable question set from the cookbook's shape; squeezing accuracy out of better-worded criteria is implementation work for the follow-up card, and doing it here would make the latency numbers chase a moving target.

Measuring how often real operator prompts repeat closely enough to hit the answer cache. S4 measures cache-hit latency; the hit rate a real prompt stream would produce needs real prompts, which the data rule keeps out of this exploration.

Prefix caching of the command roster. The cookbook notes that placing the suggestion in a stable position preserves roster caching across turns. That is an optimization of a hook that does not exist yet.

## Risk Analysis and Mitigation

| Risk | Exposure | Mitigation |
|---|---|---|
| The shared machine's load from other card drivers inflates a shape's latency | every measured number | interleave the shapes (R7); record machine conditions in the document; report the minimum alongside the 95th percentile, since a clean minimum and a noisy tail look different from a genuinely slow shape |
| Thirty trials estimate a 95th percentile only loosely | the headline number | state the trial count beside every percentile (R6) and describe the figure as an estimate; use more trials for the shapes that cost no API call, where trials are nearly free |
| A prototype process is left running after the session | the operator's machine | harness-owned start and stop in a `finally`, the started identifier printed, its absence confirmed at the end (R8) |
| The key leaks into a results file or the document | credentials | the harness never reads the key; the client reads it at request-build time and places it only in a header; the results file is checked for secret-named keys in U2's tests |
| A synthetic corpus flatters the suggester relative to real prompts | the accuracy figure and therefore the recommendation | say plainly in the document that accuracy is measured on synthetic prompts written by the same agent that designed the question set, which is a known optimistic bias, and treat the accuracy figure as an upper bound |
| The measurement spends real money on API calls | cost | the probes on 2026-09-18 cost fractions of a cent for thousands of tokens; six shapes at thirty trials is a few hundred calls, well under a dollar at the published rate — but the document records the actual token usage the client returns rather than asserting the cost |
| The two installed plugin trees resolve fleet-core differently and the prototype silently uses an old copy | the validity of every warm-shape number | U5's resolution probe records the winning rung per tree through the shim's own debug output rather than assuming |
| The vendor rate-limits or overloads mid-run and slow retries are recorded as latency | every live shape's tail, especially the 95th percentile | the client retries only on rate-limit and overload responses and reports a closed status vocabulary; the harness records each trial's returned status and excludes any trial that was not `ok` from the latency statistics, counting it separately as a failure rather than silently averaging a retry into the tail |
| The vendor is weeks old and its latency, pricing or availability may move | the durability of every number in the document | the document dates every figure and names the resolved model version the client reports, so a future reader can tell a stale measurement from a current one rather than trusting an undated table |

## Open Questions

Two questions this plan deliberately does not answer, recorded so they are not mistaken for settled assumptions.

**May the hook send the operator's live prompt text to the vendor?** KTD7 holds the reasoning. This is a data-governance decision the operator owns, it blocks implementation rather than this exploration, and the deliverable document carries it forward as a precondition on the follow-up capability card. The exploration proceeds on synthetic prompts either way, so the measurement is not waiting on the answer.

**Is this machine's network latency representative?** Every figure comes from one machine on one network at one time of day. The document reports what was measured here and does not generalize; a second machine would strengthen the conclusion and does not fit the one-session timebox.

## Alternatives Considered

**Skip the measurement and take the research document's figure.** The 1.07 to 1.94 second range comes from a different project on a different machine with a different question set. Borrowing it would decide a card whose whole point is to measure, and would leave the actual question — which client shape changes the answer — untouched.

**Measure only the vendor cookbook's shape.** Faithful, and it would almost certainly report failure against a 400 millisecond target. It would also answer a question the card did not ask. The card asks which persistent client shape makes the target true, which requires shapes the cookbook does not describe.

**Build the hook and time it in a live session.** The most realistic measurement available, and it depends on issue 1029, which has not shipped. It also means installing a hook that fires on every prompt of a live session to find out whether it is too slow, which is the wrong order.

## Success Metrics

The exploration has succeeded when the document exists and a reader who was not in the session can answer three things from it without re-running anything: what each shape cost at the 50th and 95th percentile with the trial count stated, whether any shape met the 400 millisecond target, and what the keep, defer or drop rule fixed in KTD5 returns when applied to those numbers.

A recommendation of drop is a successful outcome. The card asks whether the hook can be fast enough, and a measured no, recorded with its numbers, closes the question and saves the implementation.

## Questions answered from the card

The `AskUserQuestion` tool is unavailable in this session, so every question the plan skill would have asked was answered from the card, the research document, or the code. Each is recorded here with its source.

| Question | Answer | Source |
|---|---|---|
| Is a plan document warranted, or is this atomic? | Warranted. The work has six units, seven key technical decisions, and an upstream artifact that needs traceability, which fails all four skip conditions. | Plan skill section 0.4; the card's deliverable list |
| Scope class — lightweight, standard, or deep? | Standard, with the confidence pass run anyway because the work touches an external API and a data-governance question, which the skill names as an auto-run trigger. | Plan skill sections 0.5 and 4 |
| Routing destination | `pr`. Supplied by the pre-answers carrier from the improve-claude-plugins run driver and applied at intake. | The invocation's `plan_pre_answers.v1` carrier |
| Execution backend | `inline`. Supplied by the same carrier. The recommender was still called as the skill requires and returned `team-execution`, driven by the unit count rather than by any security, infrastructure or deployment signal; the tick records recommended and chosen separately. | The carrier; `lifecycle_state.recommend_execution_backend` |
| Where does the harness live, given no release surfaces may change? | `tools/`, which repository linting covers and a test can import, rather than the research folder's unlintable `.py.txt` convention. | KTD1; `.github/workflows/ci.yml:193`, `pyproject.toml:99-101`, `tests/test_agent_spec_lint.py:20` |
| Localhost port or Unix domain socket for the prototype? | Unix domain socket, the stricter reading of the card's localhost constraint. | KTD3; the card's constraints |
| What is the latency target and where does it come from? | 400 milliseconds at the 95th percentile, stated on the card. | The card's success criteria |
| What accuracy must a shape reach for a keep recommendation? | The card sets no accuracy bar, so the plan fixes two and states their grounding: 70 percent on the prompts that warrant a command, 80 percent silence on the prompts that do not. These are the author's pre-commitments, not operator rulings, and are the most reasonable thing to overturn if the operator disagrees — overturning them after the numbers are known would defeat KTD5. | KTD5; the research document's saga-routing probe; the vendor cookbook's needless-load figures |
| May any local process reach the resident prototype? | No. The socket is owner-only and the process refuses to start otherwise, because it holds a live credential. A stricter reading of the card's constraint, so no operator ruling was needed. | KTD3 |
| May the hook send the operator's real prompt text to the vendor? | Not answered here. It is a data-governance decision the operator owns; the exploration measures with synthetic prompts and records the question as a precondition on the follow-up card. | KTD7; `plugins/fleet-core/references/typesafe.md` section 1 |
| Does this exploration file the follow-up issue? | No. It drafts the card body into the document; the coordinator files it. | The card's deliverables; plan skill section 5.5 |
