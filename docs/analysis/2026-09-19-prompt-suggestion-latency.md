# Can a prompt-submission hook suggest a saga command fast enough? — measured

**Recommendation: defer.** The suggestion is accurate enough to be worth having — a warm single-request shape names the right command on 14 of 15 prompts and stays quiet on all 5 that deserve silence — but no shape that makes a blocking call reaches the 400 millisecond target, and the two shapes that do reach it are not usable as built.

Issue 1038, an exploration under parent 1019. The plan is [`docs/plans/2026-09-19-issue-1038-prompt-suggestion-latency-plan.md`](../plans/2026-09-19-issue-1038-prompt-suggestion-latency-plan.md); the harness is `tools/prompt_suggestion_latency.py` and `tools/prompt_suggestion_daemon.py`; the raw results are beside this file under `2026-09-19-prompt-suggestion-latency-inputs/`.

---

## 1. The one-sentence answer

A resident local process removes about 343 milliseconds from a cold hook — nearly half its cost — and what is left over is almost entirely one API round trip of roughly 350 milliseconds, which no client design on this machine can shorten. A 400 millisecond budget cannot absorb a blocking call plus a process start, so the only way to meet it is not to make the call on the critical path.

## 2. What was measured

Seven shapes, each timed as Claude Code pays for it: wall clock around a subprocess spawn, its output read in full, and its exit. Every request went through the fleet-core TypeSafe client that issue 1032 shipped (`plugins/fleet-core/scripts/fleet_commons/typesafe_client.py`), never around it. Every prompt was synthetic.

| Shape | What it is |
|---|---|
| `floor` | a process that starts, prints nothing, exits — the cost of having a hook at all |
| `s0` | cold process, one API request |
| `s1` | cold process, two sequential API requests (the vendor cookbook's shape) |
| `s2` | resident process, two sequential API requests |
| `s3` | resident process, one API request |
| `s4` | resident process, answer served from the client's cache — no network |
| `s5` | resident process, no blocking call: answers from the *previous* prompt |

## 3. Latency

All figures in milliseconds. `within 400ms` is the share of trials that finished inside the target, which is what the target means operationally — a percentile alone does not say where the rest of the distribution sits.

| Shape | trials | p50 | p95 | min | max | within 400ms |
|---|---:|---:|---:|---:|---:|---:|
| `floor` | 50 | 46.9 | 49.8 | 42.6 | 50.8 | 100% |
| `s0` cold, 1 request | 20 | 741.6 | 781.0 | 685.7 | 781.4 | 0% |
| `s1` cold, 2 requests | 20 | 1044.3 | 1189.9 | 703.2 | 1253.4 | 0% |
| `s2` warm, 2 requests | 20 | 694.5 | 793.4 | 371.2 | 801.8 | 20% |
| `s3` warm, 1 request | 20 | 398.9 | **428.4** | 374.0 | 449.1 | 55% |
| `s4` warm, cache hit | 50 | 49.2 | 53.3 | 46.5 | 55.3 | 100% |
| `s5` warm, no blocking call | 20 | 48.6 | 52.0 | 46.4 | 52.5 | 100% |

Twenty trials is a small sample for a 95th percentile: the figure is the second-slowest of twenty observations, not a pinned value, and it should be read as an estimate with wide error bars. The cheap shapes carry fifty trials because they cost nothing to repeat.

**The arithmetic that decides this card.** The floor is 47 milliseconds. The warm single-request shape sits at 399 at the median, so the API round trip itself is about 352 milliseconds — squarely inside the 332 to 428 millisecond range the earlier research measured for a standalone call. Two sequential calls cost twice that: the warm two-request shape spends about 647 milliseconds above the floor. A persistent client removes process start, interpreter start and module import; it cannot remove the network.

**What the persistent process is worth.** Cold one-request 741.6 against warm one-request 398.9 at the median: 343 milliseconds saved, 46% of the cold cost. That is a real and large saving, and it is still not enough, which is the finding.

That particular comparison spans two runs minutes apart on a shared machine, so it is not a controlled A/B and should not be read as one. What makes it trustworthy is that the `floor` shape was measured in both runs and came out at 46.5 and 46.9 milliseconds at the median — the same to within half a millisecond. The floor is the control variable here, and it says machine conditions did not move between the runs.

## 4. Accuracy

Scored against the plan's two pre-committed bars, fixed before any measurement ran: 70% on the fifteen prompts that warrant a command, 80% silence on the five that warrant none.

| Shape | names the right command | stays quiet when it should | clears both bars |
|---|---:|---:|:--:|
| `s0` cold, 1 request | 14/15 (93%) | 5/5 (100%) | yes |
| `s1` cold, 2 requests | 13/15 (87%) | 5/5 (100%) | yes |
| `s2` warm, 2 requests | 13/15 (87%) | 5/5 (100%) | yes |
| `s3` warm, 1 request | 14/15 (93%) | 5/5 (100%) | yes |
| `s4` warm, cache hit | 14/15 (93%) | 5/5 (100%) | yes |
| `s5` warm, no blocking call | 1/15 (7%) | 4/5 (80%) | **no** |

Two things in this table need saying rather than leaving to the reader.

**The verification pass did not help here.** One request scored 93% and two scored 87%, twice — the second pass changed two correct answers to wrong ones and cost an extra 350 milliseconds. That is the opposite of the vendor cookbook's result, and the likely reason is roster size: the cookbook ranks 182 skills, where a wide pass is genuinely uncertain and a verification pass earns its keep. This repository has 24 saga commands, and the wide pass is already confident on them (one probe returned `investigate` at 0.99). A shortlist re-check adds a second chance to talk itself out of a correct answer.

**One deviation from the cookbook, and what it does and does not affect.** The cookbook's verification pass re-ranks the top *three* candidates. This harness verifies only the single winner the choice primitive returns; building a genuine top-three would have meant reading the answer's `probabilities` map, which it does not. This is recorded rather than quietly fixed after the fact, so that the shipped harness is the harness that produced these numbers. It cannot affect any latency figure, because both variants make exactly one verification request and the call count is what drives the timing. It could affect the two-request shapes' *accuracy*: a real three-candidate shortlist might recover the two answers the verification pass lost, or lose more. That is untested, and it is on the follow-up list below rather than asserted either way.

**The stale shape's 7% is an artifact of the corpus, not a verdict on the shape.** `s5` answers with the previous prompt's suggestion, and the twenty corpus prompts are deliberately unrelated to one another, so the previous answer is almost never right. Real operator prompts arrive in related runs — three prompts about the same failing test — where a one-prompt-stale suggestion would do far better. This corpus cannot measure that, and the number above should not be read as though it could.

## 5. The card's three key questions

**Does a persistent process survive the hook lifecycle and the two plugin trees?** Yes for the lifecycle: thirty separate hook processes, each a fresh operating-system process, all reached the same resident instance (one process identifier across all thirty, uptime growing between the first and last).

The two-tree question has a sharper answer than expected, and it is bad news. Both installed trees resolve fleet-core through the *same* file — `~/.claude/plugins/installed_plugins.json`, rung 3 of the resolution ladder — so a hook in either tree lands on `~/.claude/plugins/cache/infiquetra-plugins/fleet-core/0.25.3`. Both trees carry only 0.25.3, and **0.25.3 does not contain `typesafe_client.py` at all**: the client shipped in 0.26.0, which is merged to `main` and has reached neither tree. A suggestion hook installed today could not make the call, on either tree. This is the repository's known registry-skew problem showing up as a hard blocker rather than a nuisance.

**What state does the suggestion need, and how is it kept fresh?** Two things: the command roster, read from the installed saga plugin's `commands/` directory (24 commands today), and, if the suggestion is ever to be run-aware, the saga run record's `next_step` field. The roster is cheap and changes only on a plugin release. The run record is the awkward one: saga state lives under a git-ignored `.claude/saga/` directory, which is per-worktree, so a single resident process serving several worktrees would have to resolve which run record applies rather than holding one. Nothing here measured how stale that may safely be; `s5`'s accuracy is the only staleness evidence collected, and its corpus cannot support the conclusion.

**How is a wrong suggestion surfaced and overridden without noise?** The cookbook's answer, which this harness followed, is that the suggestion enters as one line the model may ignore, and both thresholds resolve to silence. That worked: silence was correct on 5 of 5 negative prompts for every blocking shape. The override mechanism was not exercised, because nothing was wired into a live session.

## 6. The recommendation, from the rule fixed before the numbers

The plan's rule: **keep** needs one shape at or under 400 milliseconds at the 95th percentile *and* clearing both accuracy bars; **defer** when the target is met only by the stale shape or only by a shape whose accuracy is not established; **drop** when nothing reaches 400 milliseconds and the cheapest failure is still noticeable.

Applying it honestly, including the part that is inconvenient:

- `s3` clears both accuracy bars decisively and misses the latency target by 28 milliseconds at the 95th percentile. Close, and a miss.
- `s2` clears the accuracy bars and misses the target by roughly twice the budget.
- `s5` meets the target and fails the positive accuracy bar outright.
- `s4` **literally satisfies both halves of the keep condition** — 53 millisecond 95th percentile, 93% and 100% accuracy. It does not count, and the reason must be stated rather than quietly dropped: a cache hit requires that the identical prompt was already answered and paid for. A prompt the operator has never typed before cannot hit the cache, and the accuracy figure above is the *replayed* accuracy of the single-request answers that populated it. Reading `s4` as "the hook runs in 53 milliseconds" would be reading the cache as though it were the suggester. The plan anticipated this and said so; the measured numbers do not change it.

So: no shape both meets the target and earns its accuracy. The target is met only by shapes that do not make the call — one whose accuracy this corpus cannot measure, one whose accuracy is borrowed. **That is the defer branch, precisely as written.**

Defer rather than drop, for three reasons worth weighing. The suggestion is genuinely accurate at 93% positive and 100% negative, which is better than expected and is the hard part. The miss is 28 milliseconds at the 95th percentile on a twenty-trial sample, which is within the noise of the estimate itself. And the one shape that could plausibly both be fast and be right — a suggestion computed off the critical path — was measured against a corpus built to defeat it.

**Pending, in any case, an operator ruling.** Every measurement here used synthetic prompts. The production shape of this hook would send the operator's live prompt text to a third-party vendor on every turn. The fleet-core data rule permits issue bodies, plans and diffs after redaction and forbids raw session transcripts; a single live prompt is not a transcript, but it is uncontrolled text nobody vetted, which is the stated reason transcripts are excluded. **This exploration does not decide that, and no implementation should start before it is decided.**

## 7. What a follow-up would have to settle

This is not a filed card and not the drafted card body a *keep* verdict would have produced. It is the list of what remains open, so the decision is the coordinator's and the operator's rather than mine.

1. The data-governance ruling above. It is a precondition, not a task.
2. Whether 400 milliseconds is the right target. A single API round trip is about 352 milliseconds here, so any blocking shape needs a budget above roughly 450 milliseconds to be viable at all. That is an operator judgment about what is noticeable, not a measurement.
3. Whether a one-prompt-stale suggestion is accurate on *related* consecutive prompts. This is the cheapest remaining experiment and the only one that could turn a blocked shape into a viable one: it needs a corpus of realistic prompt *sequences*, which the data rule makes awkward to build from real sessions.
4. The installed-tree blocker. A hook cannot work until fleet-core 0.26.0 or later reaches the plugin trees, which is the repository's standing registry-skew problem and is not this card's to fix.
5. Drop the verification pass unless the roster grows. It cost 350 milliseconds and lost accuracy on a 24-command roster — and it was measured verifying one candidate rather than the cookbook's three, so if it is kept at all, measure the three-candidate form before judging it.

## 8. How this was run, and what would weaken it

**Machine and conditions.** One machine, one network, one evening, shared with other card drivers whose test runs come and go. Shapes were run interleaved — one trial of each in rotation — so a load spike cannot land entirely on one shape. The minimum and maximum columns are reported for the same reason: a clean minimum with a noisy tail looks different from a genuinely slow shape, and `s2`'s 371 millisecond minimum against a 694 millisecond median is visible evidence of exactly that variability.

**Sample sizes.** Twenty trials for shapes that spend an API call, fifty for the two that do not. The 95th percentile of twenty is an estimate, and this document has tried to say so everywhere it quotes one.

**Accuracy is measured against a corpus written by the same agent that wrote the question set**, which flatters the suggester. Treat 93% as an upper bound, not a forecast.

**The cold figures cannot prove that no request failed, and here is why they are still trustworthy.** At the time the cold shapes were measured, the cold hook did not report each request's status, so a failed request and a successful one with nothing to suggest were indistinguishable in its output. The code review caught this and it is now fixed, but fixing it does not retroactively add statuses to figures already taken. What the recorded data does show: a failed request returns either fast, with an error, or after the client's long retry deadline — and the cold maxima are 781 and 1253 milliseconds, with minima of 686 and 703, so there is no fast-error outlier and no multi-second timeout anywhere in the distribution. A failed request also yields no suggestion, which scores as a miss, and the cold shapes scored 14 of 15 and 13 of 15. Both lines of evidence say these were real calls; neither is a status field, and the difference is worth stating rather than glossing.

**Two runs, and why.** The warm-shape figures come from a second run. In the first, the harness timed the warm shapes against the same half-second deadline the hook uses to fail open — so every two-request trial returned at the deadline, the recorded latency *was* the deadline, and the empty answer that came back was scored as a deliberate silence. Warm two-request accuracy read as 0 of 15 where the identical cold shape read 13 of 15, which is what exposed it. The measurement deadline is now fifteen seconds and separate from the fail-open policy, a timed-out warm trial is recorded as a failure rather than a fast success, and the shapes were re-measured. The cold figures are from the first run and are unaffected: a cold hook never talks to the resident process, so it never used that deadline.

**Spend.** About 235 live requests across the smoke run, both measurement runs and two diagnostics — under the 300 the coordinator set. The two measurement runs recorded 436,479 input and 55,452 output tokens, and 346,503 input and 44,257 output tokens respectively; the smaller runs add roughly 22,000 input tokens. Nothing was left running: the resident process is started and stopped by the harness in a `finally`, and both its absence and the absence of any leftover socket were confirmed after the run.

**A constraint worth recording.** A Unix domain socket path may not exceed about 104 bytes, and this session's scratch directory is far longer than that, so the socket cannot live beside the results. The harness creates its own short, owner-only directory and refuses a path it cannot bind, with a message that says why.
