# Doc review — issue 1038 prompt-suggestion latency exploration plan

**Verdict: ready to drive implementation.** Ten findings, all repaired in place; nothing blocking remains.

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-1038-prompt-suggestion-latency-plan.md` |
| Reviewed revision | working tree, at base commit `866d3670` |
| Classification | plan — `docs/plans/` path, with `origin:`, `Implementation Units`, `Key Technical Decisions` and a `U1` unit identifier |
| Rubric engine | not run — the engine's rubrics cover the idea, issue and spec phases; a plan document has no rubric phase, so the readiness-skeptic pass ran alone |
| Triggered lenses | security and operations, because the document covers a credential, an external vendor integration and a resident local process |
| Blocked | no |
| Linked issue | infiquetra/infiquetra-claude-plugins#1038, child of #1019 |
| Override rationale | not applicable |

## Findings

All ten were repaired in the document rather than left open. Each repair is supported by the document itself or by repository evidence, which is what makes it a safe fix rather than an invention — except `D2`, noted below.

| Key | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The shape table promised that a cache-hit shape would reveal "the hit rate a real prompt stream would see". Twenty deliberately distinct synthetic prompts cannot produce a hit rate, so the plan promised a number the design cannot yield and the write-up would have had to invent or hand-wave it. | repaired — the shape now measures cache-hit latency only, the gap is named explicitly, and hit rate moved to deferred work |
| D2 | P1 | The keep rule required accuracy to beat a baseline "by a margin the document states", which places the margin after the numbers are known — the exact rationalization the rule exists to prevent. | repaired — two bars fixed in the plan, 70 percent on positive prompts and 80 percent silence on negative ones, each with its grounding stated |
| D3 | P1 | The resident prototype holds a live API credential and answers whatever connects, but the plan never specified the socket's permissions. Any local account could have spent the operator's key and fed the model text of its choosing. | repaired — owner-only socket inside an owner-only directory, the process refuses to start otherwise, and a test scenario covers the refusal |
| D4 | P2 | A test scenario said an unrecognized transport value "surfaces the client's own loud failure". `resolve_transport` does raise, but `ask()` catches it and returns an error-status result (`typesafe_client.py:855-860`), so an implementer writing an exception assertion would write a failing test. | repaired — the scenario now names the returned status and cites the catch |
| D5 | P2 | The command roster the wide pass ranks was left unquantified, against the plan skill's own instruction to find exact counts. | repaired — twenty-four commands, counted from the installed saga plugin at version 0.159.2, with a note that this is far smaller than the cookbook's 182-skill roster and that the difference must not be read as our shapes being fast |
| D6 | P2 | Requirement R10 promised to answer "how stale that state can be", but the unit that carries R10 only inspects where state lives; nothing measured staleness tolerance. | repaired — R10 now claims what the probe does, and points at the one-prompt-stale shape's accuracy as the evidence for tolerance |
| D7 | P3 | "Seven probes" overcounted: six probes recorded a latency, one of them at two payload sizes. | repaired |
| D8 | P3 | Two citations were off by a line or a few: the lint step's command line, and the line where the transport environment variable is defined. | repaired — `ci.yml:194` and `typesafe_client.py:80-85` |
| D9 | P3 | A verification line said "the five statistics" beside a separately named trial count, implying six figures where the requirement names five. | repaired — the five are now enumerated |
| D10 | P3 | The unit dependency diagram omitted the edge from the probe unit to the write-up unit, although the write-up consumes its answers. | repaired |

## Note on D2

Fixing an acceptance threshold is normally an unsafe edit — this skill treats inventing acceptance criteria as a finding to report, not a change to make. It was repaired here because the card's own success criteria name a latency bar and no accuracy bar, and leaving the accuracy bar unset would have shipped a plan whose central decision rule could not be applied. The plan records both numbers as the author's pre-commitments rather than operator rulings, states the evidence behind each, and says plainly that they are the right thing for the operator to overturn — before the measurements run, not after.

## Residual risk

The accuracy figures this exploration will produce come from a corpus written by the same agent that designed the question set, which flatters the suggester. The plan names this and treats the figure as an upper bound; no repair removes the bias, and only real prompts would, which the data rule excludes.

Whether the hook may send a live operator prompt to the vendor at all remains an open operator decision. It does not block the measurement, and it does block any implementation that follows.
