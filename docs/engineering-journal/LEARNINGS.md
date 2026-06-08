# Learnings — Infiquetra Claude Plugins

> **Empirical findings + mechanisms + fixes + validations.** When something turns out to be true that wasn't obvious — about a plugin's runtime behavior, the marketplace registry, hook timing, skill activation, MCP env propagation, build/test tooling, or a deploy gotcha — it goes here. Include the **evidence** (PR / commit / file:line / reproduction) and the **mechanism** (why it's true), not just the observation.
>
> **Append new entries to the top.** Most-recent first. Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short descriptive title  {#slug}
>
> **Context.** One paragraph framing the situation.
> **Evidence.** Specific PR / commit / file:line / reproduction recipe.
> **Mechanism.** Why it happened (or why it's true) — root cause, not just symptoms.
> **Fix (or queued).** Concrete action + commit hash, OR a QUEUED.md ref if deferred.
> **Validation (if applicable).** What later run / test / install proved the fix.
> **What surprised (optional).** The thing that wasn't in the original mental model.
> **Generalizable rule.** The lesson stripped of this specific incident — what would I tell a future-me hitting a similar shape?
> **Refs.** Cross-links to DECISIONS / QUEUED / narratives / other LEARNINGS entries.
> ```
>
> The `{#slug}` HTML anchor on the entry title makes the entry linkable from `README.md` quick-nav and from cross-references. Keep slugs short and stable.
>
> When new evidence invalidates a learning, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**. Never silently overwrite.

---

## 2026-06-07

### Saga ideation/review schema fields are not machine-parsed — the consumer is an LLM + a human (squash `abcc06b`, PR #205, #201)  {#saga-doc-schema-no-field-parser}

**Context.** Issue #201 (make saga docs readable) carried a constraint "keep the schema machine-parseable for `/handoff` and `/plan`," and the templates' own comments asserted those consumers "parse" `basis`/`confidence`/`complexity`. That constraint drove two early heavyweight ideas (a YAML field sidecar, a full doc serializer).
**Evidence.** `plugins/saga/scripts/parse_issue.py` parses issue *bodies* only (ADR/AC refs, keyword flags, H3 headings, handoff maturity) — never ideation-doc fields. `handoff/SKILL.md:53-57` routes by directory → maturity plus frontmatter `maturity:`; `brainstorm`/`plan` consume the doc as an LLM reader, with the human naming the survivor by title or `R#`. No code regexes `**basis:**` / `**confidence:**` / `**complexity:**`.
**Mechanism.** The "machine-parseable" contract was aspirational template prose, never an implemented parser. The real consumers are a model reading the markdown and a human — both of which read a table or fenced block *better* than a run-on bold-label stack.
**Fix.** Rendered the compact schema fields as a table (#201) and kept the field names stable for legibility and future-proofing; dropped the YAML-sidecar and serializer ideas.
**What surprised.** A constraint stated as load-bearing ("must stay parseable") was satisfied — and improved — by the human-readability fix itself, because the asserted parser did not exist. Reading the consumer code flipped two heavyweight options straight into the reject pile.
**Generalizable rule.** Before honoring a "must stay machine-parseable" constraint, grep for the actual parser. If the consumer is an LLM plus a human with no regex, optimize for legibility — a table beats a field stack on both the human and the model axis — and do not pay for a structured-data split that serves a parser that is not there.
**Refs.** DECISIONS {#saga-doc-formatting-contract}; `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`.

### Doc-review's premise-check caught a plan that over-stated its own remediation (#201)  {#doc-review-catches-plan-over-claim}

**Context.** The #201 plan — produced by this repo's own `/ideate`→`/plan` — asserted a uniform "fix the bold-label collapse across all nine doc-writing skills." `/doc-review`'s readiness pass grepped the actual templates before approving.
**Evidence.** `rg -c '^\*\*[a-z_]+:\*\*'` returned non-zero ONLY for `ideation-artifact.md` (9 lines); the other eight templates returned 0 — they already used headings/prose/tables, and `code-review` already rendered findings as a pipe-delimited table (`findings-schema.md:105`). Recorded as F1/F2 in `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`.
**Mechanism.** A plan written from one vivid instance (ideate's collapse) generalized the remediation to all siblings without measuring each. The premise was a hypothesis dressed as a fact.
**Fix.** `/doc-review` safe-fixed the plan (KTD5 + U5 + an execution guard) before `/work` ran, so the parallel fan-out did not over-edit eight already-clean templates.
**Generalizable rule.** A plan's quantitative premise ("all N have problem X") is a hypothesis — measure it against the repo before building, even when the plan came from your own ideation. The cheapest place to catch an over-claim is the doc-review gate, not the diff.
**Refs.** DECISIONS {#saga-doc-formatting-contract}; the campaign's components-present-≠-verified lesson.

### Parallel fan-out agents hedge on output conventions unless given the exact form (#201)  {#fanout-agents-hedge-conventions}

**Context.** The #201 `/work` used a `cc-workflows-ultracode` four-agent fan-out to roll a shared-reference LINK into nine skill files. Each agent was told to "link `saga/references/formatting-style.md`."
**Evidence.** The ideate/plan agents used the repo's bare code-span convention; the brainstorm/spec/strategy/retro/doc-review/code-review/founder-review agents instead emitted a clickable markdown link `[...](../../../references/formatting-style.md)` — several putting BOTH forms on one line, hedging. Normalized to the bare convention post-fan-out before commit (PR #205).
**Mechanism.** "Link X" under-specifies the FORM. Absent the exact convention, independent agents each pick a defensible-but-different rendering, and some hedge by emitting two.
**Generalizable rule.** When fanning out a uniform edit across files, give each agent the EXACT output form (a one-line example of the convention), not just the target — or budget a normalization pass. Verifying every fan-out diff is non-optional; the same review pass also caught a hard-coded version-pin test that needed bumping.
**Refs.** LEARNINGS {#doc-review-catches-plan-over-claim}.

---

## 2026-06-04

### "X shipped" can be TRUE on origin yet INVISIBLE in a stale local tree — verify against origin/<tip> + `gh pr view`, not the checkout, before concluding "X didn't ship"  {#shipped-on-origin-not-in-stale-local-tree}

**Context.** The `/optimize` build (the campaign closer) opened from a worktree branched off `origin/main`. A continued-conversation summary / memory asserted earlier siblings (e.g. `/spec` 0.17.0) had shipped. The risk shape: a local working tree (or a stale primary checkout whose `main` was never fast-forwarded after a remote squash-merge) can lack the merged files even though the change is live on origin — so a naive "grep the local files; they're not there → it didn't ship" read produces a false negative and risks re-doing or double-counting shipped work.

**Evidence.** GitHub squash-merges land a single commit on `origin/<default-branch>`; a local `main` that hasn't been fetched + fast-forwarded still points at the pre-merge tip, so the squashed files are absent locally. The campaign's own siblings shipped this way (each PR squash-merged: `/spec` PR #195 squash 9a61e5b, `/investigate` PR #193 squash 5079d8f, etc. — recorded in ARCHIVE). The authority for "did it ship" is the remote tip + the PR's merged state/SHA, not the contents of whatever tree happens to be checked out. The fix here was structural: this worktree was branched from **origin/main** (not a stale local main), so it carries the shipped siblings — confirmed by reading the current 0.17.0 files (CHANGELOG `## 0.17.0`, the `/spec` row already "never offers" in `operator-choice.md`, dispatch-table "total over 17") directly in-tree.

**Mechanism.** "Shipped" is a property of **origin + the merged PR**, not of the local filesystem. Local trees drift: a worktree can be fresh-from-origin (correct) or a checkout can be stale (lagging a squash-merge). A summary/memory claim and a local grep are two independent signals that can disagree, and neither is the source of truth. The validation-discipline corollary: a current-source check means the *authoritative* current source (the remote tip + `gh pr view`), not the most convenient one (the working tree).

**Fix (applied at build).** Before treating any "X shipped / didn't ship" claim as settled, verify against `git log origin/<tip>` + `gh pr view <n>` (the merged SHA + `MERGED` state), and confirm the worktree is branched from `origin/main` (so it carries shipped work) rather than a stale local main. For this build: confirmed the worktree is origin-based and the 0.17.0 siblings are present in-tree before building the 0.18.0 closer on top.

**What surprised.** The two signals that *look* like ground truth — a confident memory/summary and a direct file grep — can BOTH be wrong relative to origin: the summary because it is a remembered claim, the grep because the tree is stale. Only the remote tip + PR state arbitrate.

**Generalizable rule.** A continued-conversation summary or memory claiming "X shipped" can be **TRUE on origin yet invisible in a stale local working tree** (a local `main` not fast-forwarded after a remote squash-merge). Before concluding "X didn't ship" from local files — or trusting that it did — verify against **origin/<tip> + `gh pr view`** (the merged SHA + state), not the checkout. This is the validation-discipline corollary to [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways): there, "not in the install cache" ≠ "doesn't exist"; here, "not in my local tree" ≠ "didn't ship". The authoritative current source is the remote, not the most convenient local one.

**Refs.** [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways) (the sibling "absence locally ≠ absence in fact" lesson). The campaign whose squash-merged siblings demonstrate the pattern — DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign), ARCHIVE [#lifecycle-engine-merge-campaign-complete](ARCHIVE.md#lifecycle-engine-merge-campaign-complete). The build that surfaced it — DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild).

### A campaign brief's "merge of A + B + graft-from-C" is a provenance HYPOTHESIS, not a fact — verify each named contributor EXISTS and is DISTINCT before encoding it  {#campaign-brief-merge-is-a-provenance-hypothesis}

**Context.** The `/spec` build (twelfth command of the engine-merge campaign) arrived with a QUEUED brief whose engine line read like the campaign's standard "merge two upstreams + graft a third": gstack `spec` as the spine, "reuse the assumption-challenge/failure-mode register already in `/ideate` and `/brainstorm`" as a graft. Encoding that literally would have produced a fabricated `/spec` — a port of gstack `spec` PLUS a graft that doesn't exist as a separate thing PLUS a phantom CE engine if anyone pattern-matched "every other rebuild had a CE source."

**Evidence.** (a) **No CE spec engine.** The campaign's CE source for the planning family is `ce-plan` — that is `/plan`'s engine, already ported. There is no `ce-spec`; pattern-matching "must have a CE half" would have invented one. (b) **The "graft" is native, not separate.** gstack `spec`'s persona already IS the assumption-challenge + failure-mode register: "You think in failure modes: what happens when the input is empty, null, enormous, duplicated, called by the wrong role, or called twice?" (gstack `spec` SKILL :751-752, the persona block). That same register was ALREADY ported into the lifecycle — as the failure-mode bank in `/plan/references/interrogation.md` :37-50 (empty / null / huge / duplicate / wrong-role / called-twice), itself a gstack port. So the "graft from `/ideate`+`/brainstorm`" was not a third source — it was the spine's own native content, already living in a sibling reference. (c) **Two new commands, one source.** `/spec` and `/plan` both draw from gstack `spec`; the brief did not name the axis that keeps them from overlapping.

**Mechanism.** A campaign brief describes provenance from **labels** ("CE", "the assumption-challenge register", "graft"), written before anyone re-reads the actual sources. Labels travel by family resemblance — "every rebuild is a 2-source merge, so this one must be too" — and a register that is *native to a persona* gets re-labeled as a *separable graft from wherever it was last seen*. Encoding the label without checking the source manufactures structure: a phantom CE engine, a duplicate graft, an overlap with the sibling that already ported the same content. The fix is the same shape as `#spec-adaptation-is-a-hypothesis` and `#source-fidelity-cuts-both-ways`: read the implementation, not the brief's description of it.

**Fix (applied at build).** `/spec` shipped as a **gstack `spec` SINGLE-SOURCE port** of the WHAT-interrogation half — no fabricated CE half, no `/ideate`+`/brainstorm` graft (the register is the spine's own, already in `/plan/references/interrogation.md`), no superpowers borrow. The `/spec` SKILL does **not** duplicate `/plan`'s interrogation register. The axis that splits the two same-source commands is named explicitly: **WHAT vs HOW altitude** (`/spec` = WHAT, `/plan` = HOW). DECISIONS [#spec-interrogation-engine-rebuild](DECISIONS.md#spec-interrogation-engine-rebuild) (honest-attribution section); shipped 0.17.0, ARCHIVE [#spec-interrogation-engine-shipped](ARCHIVE.md#spec-interrogation-engine-shipped).

**What surprised.** The brief's own interview question — "*CE* — none for spec; reuse the assumption-challenge/failure-mode register already in `/ideate` and `/brainstorm`" — half-named the trap itself ("none for spec") while still framing the register as a reusable graft. The honest read flips the framing: it is not a graft TO bring in, it is the spine's native content that was ALREADY brought in elsewhere.

**Third firing — `/optimize` (2026-06-04): even a one-line "insight graft" must be GREP-VERIFIED in the named source before crediting it.** The `/optimize` brief (the campaign's final command) was milder than `/spec`'s — it didn't claim a phantom CE engine, and it correctly named CE `ce-optimize` as the metric-loop spine. But it framed the **agent-usability** angle as gstack `plan-tune`'s **INSIGHT** to keep ("Keep gstack's INSIGHT (optimize includes agent-usability)") — i.e. a single-line graft crediting gstack with the idea. The honest read: **a full-file grep of gstack `plan-tune` for the agent-usability terms (agent-usability / steps-to-success / token cost / retry rate / plan readability) returned ZERO.** `plan-tune` is a *developer-psychographic question-tuning coach* (a 5-dimension declared-profile interviewer), not a perf optimizer and not an agent-usability thinker — it supplies **nothing portable**. So agent-usability is an **infiquetra-native** angle (Jeff's), and `/optimize` shipped as a **CE `ce-optimize` SINGLE-SOURCE port** with no gstack contribution and no "merge" framing. The same trap as `/spec`, one altitude down: not a fabricated *engine* this time, a fabricated *attribution* — crediting a named source with an insight that isn't in it. DECISIONS [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild) (honest-attribution); shipped 0.18.0, ARCHIVE [#optimize-engine-rebuild-shipped](ARCHIVE.md#optimize-engine-rebuild-shipped).

**Generalizable rule.** A campaign brief's "merge of A + B + graft-from-C" is a **hypothesis about provenance written from labels, not from source.** Before encoding it: verify each named contributor (1) **EXISTS** as a real engine and (2) is **DISTINCT** from the spine — a register that is native to the spine's persona is not a separable third source, and a missing engine is not a graft to fabricate by family resemblance. And when two new commands draw from one source, **name the AXIS that splits them** (here WHAT vs HOW altitude, `/spec` vs `/plan`) so the boundary is principled, not accidental. **The rule extends below the engine altitude to a single-line "insight graft": before crediting a named source with an idea, GREP that source for the idea's terms — an insight you cannot find in the named source is your own, so attribute it honestly (the `/optimize` agent-usability angle is infiquetra-native because a grep of gstack `plan-tune` returned zero, NOT a gstack contribution).** A "merge" framing earns its name only when every named contributor survives a grep; otherwise it is a single-source port.

**Refs.** DECISIONS [#spec-interrogation-engine-rebuild](DECISIONS.md#spec-interrogation-engine-rebuild), [#optimize-engine-rebuild](DECISIONS.md#optimize-engine-rebuild) (the third firing — agent-usability is infiquetra-native, grep-verified zero in gstack `plan-tune`). The sibling hypotheses-about-source lessons — [#spec-adaptation-is-a-hypothesis](#spec-adaptation-is-a-hypothesis), [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways). The seam this build closed — DECISIONS [#plan-engine-rebuild](DECISIONS.md#plan-engine-rebuild), ARCHIVE [#brainstorm-spec-interrogation-seam-resolved](ARCHIVE.md#brainstorm-spec-interrogation-seam-resolved). Evidence: gstack `spec` SKILL :751-752 (persona failure-mode register); `/plan/references/interrogation.md` :37-50 (the already-ported failure-mode bank); the `/optimize` grep — a full-file scan of gstack `plan-tune` for the agent-usability terms returned zero matches.

### Building the engine a deferred route pointed at must CLOSE the deferral at EVERY site — and a routed OUTPUT is dead wiring unless it lands in the consumer's real input shape  {#deferred-cross-engine-wiring-must-close-on-build}

**Context.** The `/investigate` build (eleventh command of the engine-merge campaign) was the engine `/qa` had deferred a route to: `/qa` (0.13.0) named `/investigate` as "future prose only" for deep post-merge root-cause failures, "when `/investigate` is built." Building `/investigate` had to close that deferral. The naive scope was "flip the one post-merge FAIL line." The real scope was wider on two axes.

**Evidence.** (a) **Multi-site deferral.** `grep -n investigate skills/qa/SKILL.md` found **5** mentions, not 1: principle-1's fixer list ("the future `/investigate`"), the post-merge FAIL branch, the deferral block ("when `/investigate` is built … not a runnable route … never emit `/investigate`"), and the hard-boundary line ("`/work` and the future `/investigate` own those"). Closing only the post-merge branch would have left **four** stale "future" / "not runnable" assertions live — directly contradicting the now-shipped routable target. Beyond the SKILL, **2 other files** carried "queued/at-its-rebuild" notes for `/investigate`: `references/operator-choice.md` (`| /investigate | at its rebuild |`) and office-hours `references/frame-diagnostic.md` ("Campaign-queued routes (add when they ship): `/investigate` …"). The dispatch-table header ("15 routable commands") + its routable list were a third closure surface. The contract-test floor for `/qa` (`test_qa_engine_merge_contract`) asserts the gate-only negatives and dispatch tokens — building the route requires that floor still pass (and `/investigate`'s own floor must assert the new wiring). (b) **Routed-output dead-wiring (the non-saga dead-wiring axis).** The brief said `/investigate`'s confirmed-bug output "→ hand the DEBUG REPORT to sdlc-manager as a defect issue … so `/work` can pick up the fix." But **`/work` consumes ISSUES, not `docs/investigations/` doc paths** — its Phase 0 reads a handoff issue / saga, not an arbitrary report file. A DEBUG REPORT dropped only at `docs/investigations/<file>.md` and named as the `/work` route is dead wiring: `/work` never ingests it. The fix routes the report **through `/handoff`** (which mints the issue `/work` actually reads), with the report **linked as evidence** in the issue (never passed to `handoff_envelope`'s path-classifier, which doesn't recognize `docs/investigations/`) — landing the output in the consumer's real input contract.

**Mechanism.** (a) A deferred cross-engine route is rarely a single reference. When engine A defers a route to "future engine B", that "future" framing leaks into every place A reasons about the route — its principle list, its boundary statement, its routing block, AND any sibling file (operator-choice tables, other engines' routing rubrics, the shared dispatch-table) that mirrors A's command set. Closing the deferral means closing *all* of them; a `grep` for the target name across the SKILL **and** the references is the only way to find the full set. (b) "Route the output to consumer X" is only real if X's *actual input contract* accepts that output's *shape and location*. A report at a doc path and an engine that reads issues are two different contracts; naming the route does not bridge them. This is the dead-wiring lesson (verify a write/advance has a real downstream consumer) on a **non-saga axis** — the saga version recurred in `/work`, `/founder-review`, and `/retro`'s dropped `→retro` advance; here the same shape appears for a routed *document output*.

**Fix.** Closed the deferral at all 7 sites (5 `/qa` SKILL mentions → present-tense routable; `operator-choice.md` "at its rebuild" → "now"; `frame-diagnostic.md` "campaign-queued" → active route) + the dispatch-table (15→16 routable, `/investigate` added with stub-vs-shipped + off-chain failure rows + routing-OUT prose). Made `/qa`'s post-merge FAIL branch two-target (deep root cause → `/investigate`, clear defect → `/handoff`). Routed `/investigate`'s confirmed-bug DEBUG REPORT through `/handoff` (mints the issue `/work` reads), not a bare `docs/investigations/` path named as the `/work` route. DECISIONS [#investigate-systematic-debugging-engine-rebuild](DECISIONS.md#investigate-systematic-debugging-engine-rebuild) (Q3 the all-refs rewire); shipped 0.16.0, ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped).

**What surprised.** The deferral read like one line to flip (the post-merge FAIL branch — the place it was most visible). The `grep` turned up four *more* "future `/investigate`" assertions in the same SKILL plus two sibling-file notes — the deferral had quietly seeded itself across the whole command's prose and its neighbors. And the brief's own "→ `/work` picks up the fix" route, which read as settled wiring, was dead at the consumer boundary because `/work` reads issues, not docs.

**Generalizable rule.** When you build the engine a deferred route pointed at ("we'll route to B when B is built"), **`grep` the target's name across the deferring engine's SKILL AND every sibling file that mirrors its command set** (operator-choice tables, other engines' routing rubrics, the shared dispatch-table, the contract-test floors) and close the deferral at **every** site — one stale "future B" assertion left live contradicts the shipped target. AND: a **routed output is dead wiring unless it lands in a shape and location the consumer actually ingests** — before naming "route the output to X", verify X's real input contract (an engine that reads *issues* will not pick up a *doc path*); bridge it through whatever mints the consumer's real input (here `/handoff` → issue). This is the dead-wiring lesson on a non-saga axis: verify the downstream consumer for routed *documents* and *cross-engine routes*, not just for saga writes/advances.

**Refs.** The rebuild + the all-refs rewire (Q3) + the own-minimal-not-`/qa`-back-call decision (Q2, avoiding the inverse cycle): DECISIONS [#investigate-systematic-debugging-engine-rebuild](DECISIONS.md#investigate-systematic-debugging-engine-rebuild), ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped). The saga-axis dead-wiring precedents this generalizes — DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild), [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild) (the dropped `→retro` advance). The `/qa` side of the route — DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

---

## 2026-06-03

### A self-modifying meta-engine is safe only behind a tiered gate — auto-apply pure-additive appends, propose-diff-and-wait every delete/modify/move, extra warning for global edits  {#self-modifying-engine-needs-a-gate}

**Context.** The `/retro` rebuild (tenth command of the engine-merge campaign) made `/retro` a **meta-improvement engine** — a pass that can propose edits to durable state across the whole system: the engineering journal, the `.claude` auto-memory, the claude/agent/antigravity directive files, AND `infiquetra-lifecycle`'s own SKILLs (the plugin the engine itself lives in). An engine that can rewrite its own plugin, its own memory, and the directives that govern every session is a foot-gun: a wrong auto-applied edit to `~/.claude/CLAUDE.md` or to a lifecycle SKILL silently changes behavior everywhere, with no review. The design question (Q3/Q4) was: narrow the reach, or keep full reach and gate it?

**Evidence.** Settled in DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild) (Q3 + Q4 + the rejected "narrow the reach" and "auto-apply directive/memory/SKILL edits" alternatives). The chosen contract: (1) **pure-additive, append-only journal writes auto-apply** — a new `LEARNINGS.md` / `DECISIONS.md` / `ARCHIVE.md` entry adds knowledge and cannot corrupt existing state, so it needs no gate; (2) **every delete / modify / move of existing durable state is propose-diff-and-wait** — memory, directives, and the engine's own plugin SKILLs are never auto-edited, the engine shows the diff and waits; (3) **a global / cross-project edit carries an EXTRA cross-project-impact warning** before the propose-diff, because `~/.claude/CLAUDE.md`, auto-memory, and the antigravity directive class span every repo, not just this one. The reach is **full** (it can propose editing itself); safety is the gate, not a narrowed surface. Shipped 0.15.0 (ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped)).

**Mechanism.** The risk of a self-edit is **asymmetric by edit kind, not by edit target**. A pure append is monotonic — it only adds; the worst case is a low-value entry, which the next curation pass prunes. A delete/modify/move is destructive — it can silently change or erase load-bearing state, and for directives/memory/the engine's own SKILLs the blast radius is "all future behavior," often across repos. So the safe partition is **by reversibility/additivity**, not by which file is touched: gate on "does this remove or change existing durable state?" (yes → propose-diff-and-wait) rather than on a per-file allowlist. The cross-project tier exists because the *same* edit kind (modify a `CLAUDE.md`) has a much larger blast radius when the file is the global one — so the warning scales with reach, not just kind. Narrowing the reach instead (forbidding the engine from touching its own SKILLs) would have crippled the whole point — a meta-improvement engine that cannot improve itself — to buy safety the gate already provides.

**Fix.** Adopted the tiered self-edit gate as the engine's safety contract: auto-apply pure-additive journal appends; propose-diff-and-wait every delete/modify/move of existing durable state (memory, directives, lifecycle SKILLs); extra cross-project-impact warning before any global/cross-project edit. Full reach + hard gate, not narrow reach. DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild) (Q3/Q4); shipped 0.15.0, ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped) (PR #191, squash f6faae2).

**What surprised.** The instinct under "this engine can edit its own plugin" is to **clamp the reach** — forbid the scary edits. But that throws away the engine's reason to exist. The cleaner lever is the **gate**, partitioned by edit-kind (additive vs destructive) rather than edit-target (which file): you can grant the engine the full self-modification surface and still be safe, because the dangerous operations all share one property (they remove or change existing state) and that property is exactly what the gate keys on.

**Generalizable rule.** A self-modifying meta-engine — one that can edit its own code/config, the memory it reads, or the directives that govern it — is safe only behind a **tiered gate keyed on edit-kind, not edit-target**: pure-additive, append-only writes may auto-apply (monotonic, prunable, low blast radius), but **every delete / modify / move of existing durable state must be propose-diff-and-wait**, and a **global / cross-project edit needs an extra cross-project-impact warning** because its blast radius spans every consumer. Prefer **full reach + a hard gate** over **narrow reach**: don't cripple the engine's usefulness to buy safety the gate already provides — partition by reversibility, gate the destructive half, warn louder the wider the reach.

**Refs.** The rebuild + Q3/Q4 (tiered gate, full blast radius incl. lifecycle SKILLs, in-repo vs global directive disambiguation): DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild), ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped). Saga read-only / off-chain siblings (write no durable saga state either): DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### A spec's pre-written ADAPTATION note is a hypothesis, not a fact — the `/strategy` brief's "AI-agent actors in persona AND tracks" was half a category error  {#spec-adaptation-is-a-hypothesis}

**Context.** The `/strategy` rebuild (ninth command of the engine-merge campaign) was a faithful single-source port of CE `ce-strategy`. The QUEUED brief for it carried a pre-written **adaptation** note under its *Infiquetra* field: "Persona/track sections **must name AI-agent actors**, not just humans." That note was written by the brief workflow *before* anyone read the actual CE `interview.md` section semantics — and on close reading it turned out to be **half a category error**.

**Evidence.** The brief's adaptation said personas **and tracks** must name AI-agent actors. Reading CE `ce-strategy`'s real `interview.md` section definitions: a **persona** section describes the *customer / consumer* of what the strategy serves — so "name the AI agent as a customer" is sound **when the product is agent-consumed**. But a **track** section is an **investment area / domain of work** (where effort/resources are committed), **not** a list of actors. Naming "AI-agent actors" in a track conflates a domain of work with an agent — a category error. Caught by reading the source section semantics + a Jeff challenge to the blanket framing. Settled in DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild) (Q3): persona-as-agent-customer YES (for agent-consumed products); tracks-as-actors NO (tracks stay pure investment areas).

**Mechanism.** A brief / spec is produced before close source reading, so any **adaptation** it pre-writes ("change X to fit infiquetra") is a *hypothesis* about how the source's concept should bend — generated from the concept's *name*, not its *semantics*. "Persona" and "track" both *sounded* like places actors could appear, so the blanket "name AI-agent actors in both" looked uniform and plausible. But the two sections mean different things (consumer vs domain-of-work), and the adaptation is only valid for the one whose semantics actually admit an actor. A plausible, uniform-sounding adaptation can be a category error precisely because it was written from the label, not the definition.

**Fix.** Re-derived the adaptation against the source's actual section semantics: kept persona-as-agent-customer (agent-consumed products only), rejected tracks-as-actors (tracks are investment areas / domains of work). DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild) (Q3 + the rejected-alternative); shipped 0.14.0, ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped) (PR #189, squash a9d4c90).

**What surprised.** The adaptation note read as a single uniform rule ("AI-agent actors in persona AND tracks"), so it was tempting to encode it wholesale. It took reading the *definition* of each section — not just its name — to see that exactly half of it was right and half was a category error. A note that looks internally consistent can still be half-wrong when its two halves rest on different underlying concepts.

**Generalizable rule.** A spec's pre-written ADAPTATION note is a **hypothesis written before close source reading** — re-derive each adaptation against the source's *actual semantics* (the section's definition, not its name) before encoding it. A plausible, uniform-sounding adaptation can be a **category error**: when one note covers two source concepts, verify it holds for *each* concept separately — it may be sound for one (persona = consumer → agent-as-customer works) and a category error for the other (track = domain of work, not an actor). This pairs with [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways): that entry says read the source's real *implementation* before claiming to port a mechanic; this one says read the source's real *semantics* before encoding a pre-written adaptation of it. Both: the brief/spec is a starting hypothesis, the source is the authority.

**Refs.** The rebuild + Q3 (persona-only agent actors; tracks stay investment areas): DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild), ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped). Pairs with the source-fidelity (read the implementation) lesson: LEARNINGS [#source-fidelity-cuts-both-ways](#source-fidelity-cuts-both-ways). Name-match-≠-verified-mapping precedent (gstack `cso`): LEARNINGS [#lifecycle-thin-reskin-systemic](#lifecycle-thin-reskin-systemic). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### Source fidelity cuts both ways — "not in the install cache" ≠ "doesn't exist", and reading the SCAFFOLD ≠ reading the ENGINE  {#source-fidelity-cuts-both-ways}

**Context.** The `/qa` rebuild (eighth command of the engine-merge campaign) was framed as a gstack `/qa`+`/qa-only` merge that would **keep gstack's 0-100 health score**. Two source-fidelity failures nearly hardened into the build — one about *acquiring* the source, one about *reading the right file within it*.

**Evidence.** (a) **Acquisition.** Searching the local plugin **install cache** (`~/.claude/plugins/cache/`) found no gstack, and the rebuild was nearly framed as a "native rebuild against a phantom gstack" — the `/loop` precedent (LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact)). But gstack is a **GitHub repo** (`github.com/garrytan/gstack`), not an installed plugin. Cloning it produced the **real** source (`/qa` 354L `.tmpl`, `/qa-only` 114L, `/investigate` 259L, the taxonomy + report-template refs) — a real two-engine merge, the opposite of the `/loop` phantom. (b) **Right-file (CORRECTED — see SUPERSEDED note below).** The brief's "keep gstack's health score" assumed the scoring lived in the cloned `qa/SKILL.md.tmpl`. It does not appear *inline* there: the `.tmpl` carries a `{{QA_METHODOLOGY}}` macro injected by `gen-skill-docs.ts`. The DA stopped at that dispatch file and concluded "no formula / LLM-eyeballed" — but that was itself a one-hop-short source-fidelity error. The formula **does exist**: `scripts/resolvers/utility.ts:286-321` defines a deterministic **Health Score Rubric** (per-category deductions Critical -25 / High -15 / Medium -8 / Low -3, explicit category weights — Functional 20%, Console/UX/Accessibility 15%, …, and `score = Σ (category_score × weight)`), exported as `generateQAMethodology` (`utility.ts:89`), wired `QA_METHODOLOGY: generateQAMethodology` (`resolvers/index.ts:50`), i.e. it IS the `{{QA_METHODOLOGY}}` macro `qa/SKILL.md.tmpl:122` injects. **Locating the real formula changed the outcome.** The interim "no formula" read had the score slated to be **dropped**; once the deterministic rubric was found, Jeff chose to **PORT it** — a deterministic scorer (`scripts/qa_health_score.py`) that takes gstack's deduction values verbatim (Critical -25 / High -15 / Medium -8 / Low -3) with documented infiquetra ship-risk-class weights, re-normalized over the in-scope classes, reported **alongside** the severity-banded verdict (with the honest caveat that its inputs are LLM-assigned, so it is one signal, not the gate). The false-precision concern is handled by that caveat, not by deletion.

**Mechanism.** Two distinct gaps. (a) The install cache is one acquisition path, not the universe of a source's existence — a source can be a clonable repo even when it is absent from the cache. Concluding "phantom" from a single failed lookup is the same shape as concluding "exists" from a single confident citation; both skip verification. (b) A scaffold (`.tmpl`) **slots** values into a generated artifact — but "read the implementation" means following the macro's dispatch **one more hop** to the resolver that computes it. The DA read `gen-skill-docs.ts` (the file that *names* the macro) and the bare `{SCORE}/100` template placeholder, then stopped — it did not open `resolvers/utility.ts` where `generateQAMethodology` actually defines the weighted formula. Stopping at the dispatch table while believing you've "read the implementation" is the precise failure this entry's own rule warns against.

**Fix.** Cloned gstack from GitHub (real merge against the actual source) AND followed the macro one hop further to `resolvers/utility.ts:286-321`, finding the real deterministic rubric. **The payoff is concrete: finding the real implementation CHANGED the outcome — drop → PORT.** The score is **not** dropped; once the formula was located, Jeff chose to PORT it into a deterministic scorer (`scripts/qa_health_score.py`, gstack deductions verbatim + documented infiquetra class weights, re-normalized over in-scope classes, baseline-delta), reported alongside the severity-banded verdict with the LLM-assigned-inputs caveat. The interim "no formula → drop" position was the wrong rationale **and** the wrong outcome; both are corrected. DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild) (Q2 final: port + report-alongside); shipped 0.13.0, ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped).

**What surprised.** After the `/loop` phantom, the reflex was to read a missing install-cache entry as "phantom again." But the prior lesson is "verify the source," not "assume phantom" — and verifying here meant *cloning*, which produced a real source. The phantom reflex would have thrown away a genuine two-engine merge. The *second* surprise: the DA's "no formula" finding — folded as a load-bearing fact and nearly shipped in this very entry — was itself a one-hop-short read, exactly the failure mode the entry exists to teach. Verification cuts both ways: the corrective review also has to follow the dispatch the last hop.

**Generalizable rule.** Before claiming to port or **keep** a named mechanic: (1) **exhaust all acquisition paths for the source** — install cache, vendored copy, AND the upstream repo (clone it) — because "not in the cache" ≠ "doesn't exist", the positive counterpart to the phantom-source lesson; and (2) **locate and read the mechanic's actual IMPLEMENTATION by following the dispatch the last hop** — a `.tmpl` that *slots* a value (`{SCORE}/100`) and even the file that *names* its macro (`gen-skill-docs.ts`) are not the algorithm; the algorithm is in the resolver the dispatch table points to (`resolvers/utility.ts`). "I read the implementation" must mean you opened the function body, not the scaffold that references it. And reading the real implementation can **change the decision, not just its rationale**: here, finding the deterministic rubric flipped the outcome from drop to PORT — a value you were about to discard on a convenient-but-unverified premise ("no formula exists") may be worth keeping once you actually read it. A false rationale in a durable entry teaches a false fact about a named upstream AND can cost you a real capability.

> **SUPERSEDED (2026-06-03, same session).** The pre-correction version of this entry's (b)/Fix/rule asserted "gstack has no scoring formula — its health score is LLM-eyeballed" and the rule "a value with no formula behind it should be dropped." That was itself a one-hop-short source read (it stopped at `gen-skill-docs.ts` and did not open `resolvers/utility.ts:286-321`, where the deterministic weighted rubric lives). Corrected inline above; the pre-correction text is preserved in ARCHIVE [#source-fidelity-no-formula-superseded](ARCHIVE.md#source-fidelity-no-formula-superseded) per journal rule 6.

**Refs.** Acquisition counterpart (the phantom that this confirms is not always the answer): LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact), [#resume-port-source-verified-true](#resume-port-source-verified-true). The rebuild + the Q2 final (port the scorer, report alongside the banded verdict): DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild), ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped). No-false-precision posture: DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### A wrapper's required arg can make it the wrong layer for a capability — the issue-locked `load_saga_context.py` left the lifecycle with NO cold-no-issue recovery, and latest-only restore left the tick trajectory unread  {#wrapper-required-arg-wrong-layer}

**Context.** The `/resume` rebuild (seventh command of the engine-merge campaign) needed to reconstruct a work-thread cold. The QUEUED brief implied **extending `load_saga_context.py`** (the existing issue-keyed restore wrapper). Before doing that, checked the wrapper's signature and the saga restore semantics.

**Evidence.** Two verified structural facts. (i) `load_saga_context.py`'s `--issue` argument is **required** — the wrapper cannot be called without an issue number, so it structurally cannot serve a cold resume where no issue is known/resolvable. That is the recovery hole: the lifecycle had **no** cold-no-issue recovery path before `/resume`. (ii) The saga `restore` reads the **latest** tick only — the append-only tick **log** (the full trajectory across rounds/phases) was unread by any consumer until the rebuild added `saga.py read_ticks`. `/loop`'s lightweight restore (0.11.0) is latest-tick-only by design; nothing walked the whole chain.

**Mechanism.** A wrapper built for the common case (resume a known issue) hard-codes that case into its interface (`--issue` required). When a new caller needs the *uncommon* case (resume with no issue), the wrapper's required arg makes it the wrong layer — the capability has to live one level down, in the engine (`saga.py`), where the required-arg assumption doesn't apply. Likewise, "restore" naturally means "give me the current state" (latest tick), so the trajectory-reading capability is a *different* operation (`read_ticks`) that no one had needed yet.

**Fix.** Put the all-ticks reader (`read_ticks`) in `saga.py` (the engine), NOT `load_saga_context.py` (the issue-locked wrapper); the wrapper stays the shared issue-keyed substrate. `/resume`'s Tier-2 fallback fills the cold-no-issue hole. DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild); shipped 0.12.0, ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped).

**Generalizable rule.** When a brief says "extend wrapper X" to add a capability, check X's **signature first**: a `required=` argument can make the wrapper the wrong layer — it bakes in an assumption (here: "an issue always exists") the new capability must violate. The capability belongs in the engine the wrapper wraps, not the wrapper. And "restore latest" ≠ "read the whole trajectory" — if the durable record is append-only, walking the full log is a distinct operation a latest-only restore will silently not provide.

**Refs.** DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild), ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). Saga foundation: DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation). Lightweight-restore partner: DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild).

### Verification cuts both ways — the `/resume` brief source (CE `ce-sessions`) verified TRUE + portable; and a shipped sibling can encode a convention a later rebuild must honor  {#resume-port-source-verified-true}

**Context.** The immediately-prior `/loop` rebuild taught "verify a brief's source claims before building" after its named gstack source turned out to be **phantom** (LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact)). The `/resume` rebuild applied that same verification discipline to its own brief — and to the question of whether to add a new structural element.

**Evidence.** Two findings. (i) **The brief source verified TRUE.** The `/resume` brief named CE `ce-sessions` as the forensic-reconstruction engine source; checking the actual upstream confirmed `ce-sessions` exists and is portable (zero-save session-log reconstruction, file-mediated extraction that never reads multi-MB JSONL into context) — so `/resume` is a **real CE port**, the opposite outcome to `/loop`'s phantom. (ii) **The C1 convention catch.** The Tier-2 synthesis step wanted a synthesis agent; the instinct was to add a `agents/` dir. Grepping the shipped siblings showed `/code-review` (0.8.0) already states the convention: **no plugin `agents/` dir → use generic agents** (`skills/code-review/SKILL.md:164`). `/resume` honored it (generic-agent synthesis) rather than introducing a structural first.

**Mechanism.** The `/loop` lesson framed verification as a *negative* check (catch a phantom). But the same one-line upstream check is *positive evidence* when the source is real — verifying is not just for catching lies, it confirms a true port is safe to build. Separately: a shipped sibling command is not just code, it is a record of **conventions already decided** (here: no `agents/` dir). A later rebuild that adds a structural element without checking the siblings risks contradicting a settled decision — the convention is discoverable by grepping the neighbors, exactly as a cross-skill wiring fact is.

**Fix.** Built `/resume` as a genuine CE `ce-sessions` port (Tier 2) and used generic-agent synthesis (no `agents/` dir), per the `/code-review` convention. DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild) (C1 + the port distinction); shipped 0.12.0.

**What surprised.** After the `/loop` phantom, the working prior was "briefs over-claim sources" — but `/resume`'s source was real. The lesson is not "briefs lie" but "briefs must be verified" — and verification is just as likely to greenlight as to block.

**Generalizable rule.** Verification cuts both ways: the cheap upstream check that catches a phantom source (LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact)) is the *same* check that **confirms** a true source is safe to port — run it regardless of which way you expect it to land. And before adding a structural first (a new dir, a new file class), **grep the shipped siblings for a stated convention** — a sibling can encode a plugin convention (no `agents/` dir → generic agents) a later rebuild must honor; conventions are discoverable, not just inheritable.

**Refs.** Negative-case counterpart: LEARNINGS [#brief-source-claim-phantom-artifact](#brief-source-claim-phantom-artifact). The rebuild: DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild), ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). The convention source: DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

### A budget-exhausted brief workflow asserted a SOURCE artifact that does not exist — verify a brief's upstream claims before building on them  {#brief-source-claim-phantom-artifact}

**Context.** Starting the `/loop` rebuild (sixth command of the engine-merge campaign). The QUEUED brief for `/loop` (`#loop-engine-merge-saga-workflow-offload`) named the engine source as gstack's "top-level SKILL = a proactive **dispatch table**" — i.e. it framed `/loop` as a port/merge of a gstack router engine, the same shape as every prior rebuild. Before building on that framing, checked the actual upstream.

**Evidence.** `gh api repos/garrytan/gstack/contents/` lists no `router`/`dispatch`/`loop` directory; `gh api repos/garrytan/gstack/contents/SKILL.md` decodes to `description: Fast headless browser for QA testing and site dogfooding` (a browser-testing skill, not a router/dispatch table). gstack's actual routing-adjacent engine is `context-save`/`context-restore` — which is the already-shipped **saga** primitive plus the queued `/resume`'s scope, **not** a `/loop` router. The brief that asserted the "dispatch table SKILL" was produced by the budget-exhausted brief workflow documented in [#workflow-structuredoutput-budget](#workflow-structuredoutput-budget) (16/19 agents over-read + failed to emit; the survivors synthesized from skim-level reads).

**Mechanism.** The brief-generation agents skimmed engine files under a tight budget (the very fix that made them *emit* — skim-not-full-read — also made them *summarize from headings*), so a heading-level impression ("gstack has a top-level SKILL that dispatches") hardened into a confident SOURCE claim ("dispatch table SKILL") in the brief. The brief's *intent* was sound (`/loop` should route + resume); its *provenance claim* (a gstack engine to port) was a hallucinated artifact. Trusting the brief's source claim uncritically would have sent the rebuild chasing a phantom merge.

**Fix.** Treated `/loop` as the campaign's **one native rebuild** — authored fresh against the lifecycle's own saga + operator-choice contracts, with **no upstream port/merge** — and recorded the phantom-source distinction in the ADR. DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild); shipped 0.11.0, ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped).

**What surprised.** Every prior rebuild brief had a real, verifiable upstream engine — so the campaign's working assumption was "the brief names a real source." `/loop` was the first brief whose named source did not exist, and it looked exactly as authoritative as the true ones.

**Generalizable rule.** A brief produced by a budget-constrained skim workflow can assert a SOURCE artifact that does not exist — its *intent* may be sound while its *provenance* is hallucinated. Before building on a brief, verify its **source claims against the actual upstream** (here: a one-line `gh api .../contents/` + a SKILL.md decode), exactly as you would verify any system-state claim. A confident-sounding source citation is not evidence the source exists.

**Refs.** Upstream cause: LEARNINGS [#workflow-structuredoutput-budget](#workflow-structuredoutput-budget). The rebuild it informed: DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild), ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped). Campaign: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

## 2026-06-02

### `infiquetra-lifecycle` is a thin reskin of gstack + CE; engine-loss is systemic, not isolated to `/ideate`  {#lifecycle-thin-reskin-systemic}

**Context.** After rebuilding `/ideate` (0.3.0), audited the remaining lifecycle commands against their source arts. The plugin was derived from compound-engineering (CE) **and** [gstack](https://github.com/garrytan/gstack) — gstack was the source missed in the first audit pass; Jeff named it. Most commands kept the source's name + intent but dropped its engine.

**Evidence.** A 19-agent `lifecycle-engine-audit-queue` workflow read each command's gstack + CE engine vs the current stub. Representative gaps: `office-hours` 23-line stub vs gstack's two-mode YC diagnostic; `code-review` 20 lines vs gstack's 7-specialist review army + CE's persona/findings/validator engine; `founder-review` 20 lines vs gstack ceo-review's 4 scope modes + 18 CEO patterns; `plan` 27 lines vs CE's R-ID/KTD/U-ID artifact engine + gstack's spec interrogation; `qa`/`strategy`/`optimize`/`work`/`resume`/`retro` similarly stubbed. Only `/doc-review` carried its CE engine. Briefs → QUEUED [#lifecycle-engine-merge initiative](QUEUED.md).

**Mechanism.** Porting a skill's **name + intent** without its tuned engine (sub-agent prompts, rubrics, state machines, findings schemas) silently reverts it to a facilitative stub — the same mechanism as [#stub-port-drops-engine](#stub-port-drops-engine), but repo-wide: ~10 of 13 commands affected, because the initial port applied the same lossy transform uniformly.

**Fix (queued).** The engine-merge initiative in [QUEUED.md](QUEUED.md) — rebuild each command by merging CE + gstack into a self-contained infiquetra engine, 1-by-1, interview-driven. Decision: DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign).

**What surprised.** gstack's `cso/` skill is **Chief SECURITY Officer** (a 14-phase security audit), not Chief Strategy Officer — so the pre-audit table's "`/strategy` ← gstack cso" mapping was wrong. `/strategy`'s engine source is **CE `ce-strategy` only**; gstack has no strategy engine. (Corrected in the queue.) Lesson within the lesson: a plausible name match (`cso` ≈ "Chief Strategy Officer") is not a verified mapping.

**Generalizable rule.** When a plugin is "based on" upstreams, audit **every** command against **all** named upstreams before trusting any mapping — a derived plugin tends to inherit the upstream's *structure* while uniformly dropping its *engine*, and a name that looks like a match (`cso`) may not be one. Verify the engine, not the label.

**Refs.** DECISIONS [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign); QUEUED engine-merge initiative; LEARNINGS [#stub-port-drops-engine](#stub-port-drops-engine); DECISIONS [#ce-ideation-engine-restore](DECISIONS.md#ce-ideation-engine-restore).

### Schema-output workflow agents that over-read + over-write fail to call `StructuredOutput` — budget exhaustion, not rate limits  {#workflow-structuredoutput-budget}

**Context.** Ran a 19-agent `Workflow` to produce the engine-merge queue briefs. Each agent read large gstack engine files (some 2000+ lines) and was required to emit a schema-validated brief via the `StructuredOutput` tool.

**Evidence.** Run `wf_4a5f04b6-c00`: **16 of 19** agents failed with `subagent completed without calling StructuredOutput (after 2 in-conversation nudges)` — not API-error kills. The 3 that succeeded produced verbose briefs (one ~31K chars). Re-run `wf_577148f3-749` with the fix below: **16 of 16** succeeded (846K subagent tokens, 0 failures).

**Mechanism.** Heavy reading + essay-length synthesis consumed the agents' turn/context budget, leaving nothing to make the final `StructuredOutput` tool call; the failure presents as "completed in prose." Transient 429s seen in the live `/workflows` view ate retry budget but were **not** the fatal cause — the recorded failure reason was non-emission, not a rate-limit error. (Jeff's initial read — "rate limits" — was the visible symptom, not the root cause.)

**Fix.** Re-ran the 16 with four changes: (1) **hard brevity** — each schema field 1-3 sentences, "this is a stub not the design"; (2) **explicit emit rule** — "the ONLY accepted output is the StructuredOutput tool call; prose = lost work"; (3) **light reading** — Grep to the engine heading + skim ~150 lines, don't full-read 2000-line files; (4) **batched concurrency** (5 at a time) to dodge the 429 retries that wasted budget.

**Validation.** Re-run produced all 16 missing briefs cleanly; combined with the 3 banked from run 1 = 19 total, synthesized into QUEUED.md.

**Generalizable rule.** For schema-output workflow fan-outs over large inputs: cap output length, make the `StructuredOutput` call mandatory + explicit, instruct skim-not-full-read, and batch concurrency. "Completed without calling StructuredOutput" almost always means **budget exhaustion** (over-reading + over-writing), not rate limits — fix the budget, not (only) the throughput. Keep the same script's successful agents and re-run only the failures with the tightened prompt.

**Refs.** QUEUED engine-merge initiative (the briefs this produced); the audit workflow `lifecycle-engine-audit-queue`.

## 2026-06-01

### A plugin version bump must update its metadata test's hardcoded version — and `UNSTABLE` is not a green CI gate  {#version-bump-test-pin}

**Context.** Bumping `infiquetra-lifecycle` 0.2.0 → 0.3.0 turned `main` red: CI's Tests job failed on a
hardcoded assertion. The PR (#167) had been squash-merged while `mergeStateStatus` was `UNSTABLE`.

**Evidence.** `tests/test_infiquetra_lifecycle_plugin.py:42` asserts `plugin_json["version"] == "0.2.0"`
— a literal pin (line 43 then checks the marketplace entry matches it dynamically). Pre-merge local
checks — `marketplace/validator/validate.py` (0 errors) and `python3 -m json.tool` — both passed
because neither runs pytest. `gh pr checks` showed `Tests (Python 3.12) fail` while Lint / Type Check /
Security / Validate Plugins passed; the merge still completed because Tests is not a *required* status
check, so the PR was `UNSTABLE` (mergeable) rather than `BLOCKED`.

**Mechanism.** Each `test_<plugin>_plugin.py` pins the plugin's current version as a literal so version,
`plugin.json`, and the marketplace entry cannot silently drift. A version bump is therefore a
**three-file change**: `plugin.json`, the `marketplace.json` entry, AND the test's literal. The
marketplace validator only checks semver *shape* + entry/source existence, not the pinned value.
Separately, `gh pr checks --watch` exiting 0 and `mergeable: MERGEABLE` are NOT proof of green — only
every check showing `pass` is.

**Fix.** Updated the test literal to `0.3.0` (this follow-up commit).

**Generalizable rule.** (1) When bumping a plugin version in this repo, grep `tests/` for the old
version string and update the metadata-test literal in the same change. (2) Gate a merge on `gh pr
checks` showing every check `pass` — never on `--watch`'s exit code or on `mergeStateStatus: UNSTABLE`,
which permits merging over a non-required failing check. Run `uv run pytest` (or at least the affected
`test_<plugin>_plugin.py`) as part of pre-merge validation, not just the marketplace validator.

**Refs.** DECISIONS `{#ce-ideation-engine-restore}`. Surfaced fixing PR #167's red `main`.

### Porting a skill's name without its engine — including its tuned sub-agent prompts — silently changes its behavior  {#stub-port-drops-engine}

**Context.** `infiquetra-lifecycle`'s `/ideate` and `/brainstorm` were derived from
compound-engineering (CE) but had been reduced to ~13–20 line facilitative stubs. In use they felt
like the operator supplied all the ideas, and once Claude declared `/ideate` "too lightweight" and
improvised its own fan-out.

**Evidence.** Pre-rebuild `skills/ideate/SKILL.md` (13 lines) said "produce a small option set; lead
the user through choices" — facilitation, not generation. CE's `ce-ideate` (~400-line SKILL + 3
reference files) runs 6 parallel frame agents → adversarial filter → survivors. A home-lab artifact
(`home-lab/docs/ideation/2026-05-31-card-sizing-...-ideation.md`) was labeled
`/infiquetra-lifecycle:ideate` but used a hand-rolled decision-axis structure — Claude improvising a
substitute engine because the skill had none.

**Mechanism.** CE's repeatability does not live in the phase *structure* alone; it lives in the
*verbatim, separately-tuned sub-agent prompts* (the codebase-scan prompt, the frame-generator prompt,
the critique rubric). Porting the structure but reducing the sub-agents to "dispatch an Explore agent"
reintroduces the same facilitate-instead-of-generate failure one level down. An adversarial-review
workflow over the rebuild caught exactly this risk plus functional gaps it would have masked (a
soft-promote loophole in revival; a gate promising multi-repo grounding no Phase 1 source delivered).

**Fix (commit `30c9099`).** Rebuilt both engines self-contained with verbatim tuned prompts for every
sub-agent; ran an author→adversarially-verify→remediate ultracode workflow (5 major findings fixed, 0
blocking); plugin `0.3.0`. Follow-up fix: the version bump tripped a hardcoded
`assert plugin_json["version"] == "0.2.0"` in `tests/test_infiquetra_lifecycle_plugin.py` — caught by
CI, not by the marketplace validator or `json.tool`, because the plugin-metadata test pins the literal
version. Lesson reinforced below.

**Generalizable rule.** When you "port" or "slim" a skill, diff the *mechanics and the sub-agent
prompt bodies*, not just the prose intent. A skill that keeps the name and the goal but drops the
engine — or reduces its sub-agents to generic dispatch — will silently behave like a stub, and the
degradation won't surface until someone notices the AI stopped doing the work.

**Refs.** DECISIONS `{#ce-ideation-engine-restore}`. Plan
`.claude/plans/can-you-review-the-inherited-lantern.md`.

## 2026-05-30

### `gh api` with `-f` silently defaults to POST — breaks read-only queries  {#gh-api-f-defaults-post}

**Context.** `/deploy-status` was non-functional: `query_deployments.py` `latest_deployment()` called `gh api repos/{repo}/deployments -f environment={env} -f per_page=1` and got `HTTP 422 "ref wasn't supplied"`. The intent was to *read* the deployments list; the API was rejecting it as a malformed *create*.
**Evidence.** Issue #161; `plugins/deploy/scripts/query_deployments.py:86` (pre-fix). Live repro against `infiquetra/campps-identity-access` returned 422; the GET form `gh api --method GET repos/infiquetra/campps-identity-access/deployments -f environment=nonprod -f per_page=1 --jq '.[0].ref'` returns `v0.1.0`.
**Mechanism.** `gh api` chooses the HTTP method by *inference*: with no `--method`, the presence of any `-f`/`-F` field flag flips the default from GET to **POST** (the flags are assumed to be a request body). `POST repos/{repo}/deployments` is the create-deployment endpoint, which requires a `ref` — hence 422. With `--method GET` explicit, `gh` instead serializes `-f` params into the query string.
**Fix.** Added `--method GET` and a tag-ref filter; commit on `fix/deploy-status-query-deployments`. Validated: live smoke prints `nonprod: v0.1.0`, no 422; regression test asserts `--method GET` is present so it can't silently revert to POST.
**Second defect (same fix).** Even as a GET, taking the newest record per env was wrong — GitHub Actions `environment:` job keys auto-create Deployment objects with branch/SHA refs (`main`, PR branches) that interleave with real tag refs. Fixed by `is_tag_ref()` (known prefix + version digit) selecting the newest *tag-ref* record. See [QUEUED: per_page lookback cap](QUEUED.md#deploy-status-perpage-cap).
**Generalizable rule.** Any `gh api` call meant to *read* must pass `--method GET` explicitly the moment it also passes `-f`/`-F` (e.g. for query params) — otherwise gh turns it into a POST. When asserting against an external API in tests, assert the *method*, not just the URL/params.
**Refs.** Issue #161; [QUEUED.md#deploy-status-perpage-cap](QUEUED.md#deploy-status-perpage-cap).

### Prepared issue creation needs an artifact boundary before mutation  {#prepared-issue-artifact-boundary}

**Context.** `sdlc-manager` needed to turn rough source text into Asgard or Mount Olympus issues
without creating cards that fail team readiness checks or require hidden board/label repair.

**Evidence.** The new workflow in `plugins/mission-control/scripts/sdlc_manager.py` writes markdown
drafts plus JSON sidecars, re-runs readiness in `issue create-prepared`, and records created issue
state back onto the draft. Tests in `plugins/mission-control/tests/test_issue_prepare.py` and
`plugins/mission-control/tests/test_issue_create_prepared.py` cover blocked drafts, safe statuses,
mapping PR stop, override creation, and draft-created state.

**Mechanism.** A direct "source text -> GitHub issue" command mixes interpretation, validation,
and side effects. Splitting the workflow into a durable draft/sidecar artifact and a confirmed
mutation step lets agents shape prose while deterministic code owns readiness, repair ordering,
and idempotent recovery.

**Fix.** Added prepared drafts, readiness profiles, mutation planning, repo prerequisite repair,
mapping PR handling, natural-language prompt guidance, and plugin metadata for `sdlc-manager`
1.6.0 in PR #159, commit `74cd372`.

**Validation.** `uv run pytest -q`, `uv run ruff check .`, `uv run python -m mypy plugins/
scripts/ tests/ --ignore-missing-imports`, `uv run python -m ruff format --check .`,
`uv run python marketplace/validator/validate.py`, `uv run python
plugins/mission-control/scripts/sync_template_docs.py --check`, and `git diff --check` pass. The
post-merge `main` CI run `26685668123` also passed.

**Generalizable rule.** When a plugin command turns ambiguous human or agent text into external
side effects, make a reviewable artifact the boundary and re-validate it at mutation time.

**Refs.** DECISIONS [prepared issue workflow boundary](DECISIONS.md#prepared-issue-workflow-boundary);
ARCHIVE [Asgard/Olympus issue readiness workflow](ARCHIVE.md#asgard-olympus-issue-readiness).

### Prompt docs need their own drift guards  {#prompt-docs-need-drift-guards}

**Context.** `sdlc-manager` had already learned to consume the current `infiquetra-sdlc`
board schema and generated template reference, but handwritten prompts and references still taught
old label behavior.

**Evidence.** `plugins/mission-control/config/sdlc-schema.json` matched
`../infiquetra-sdlc/config/sdlc-schema.json`, and
`uv run python plugins/mission-control/scripts/sync_template_docs.py --check` passed. The remaining
drift was in handwritten files such as
`plugins/mission-control/agents/sdlc-operator.md`,
`plugins/mission-control/commands/sdlc-triage.md`, and
`plugins/mission-control/skills/sdlc-issues/references/issue-types.md`.

**Mechanism.** Generated docs can stay correct while nearby prompt text keeps stale duplicated
facts. Agents read both surfaces, so a correct generated reference is insufficient if the operator
prompt still says exploration/context-update are `hermes-task` or examples still apply
`needs-analysis` as a current template label.

**Fix.** Aligned the handwritten prompts/references with the generated template contract and added
`plugins/mission-control/tests/test_prompt_alignment.py` to pin the current metadata,
Hermes-actionability, and label wording.

**Validation.** `uv run python plugins/mission-control/scripts/sync_template_docs.py --check`,
`uv run ruff check plugins/mission-control/tests/test_prompt_alignment.py`, and
`uv run pytest plugins/mission-control/tests tests/test_sdlc_manager.py -q` pass.

**Generalizable rule.** When a plugin mixes generated references with human-authored prompts, add
drift guards for the human-authored prompts too; otherwise agents can keep following stale
instructions even while generated docs are correct.

**Refs.** ARCHIVE [sdlc-manager prompt alignment](ARCHIVE.md#sdlc-manager-prompt-alignment).

---

## 2026-05-29

### Schema migrations need legacy fallback contract tests  {#schema-migration-legacy-fallbacks}

**Context.** Updating the doc-review PR branch from `main` pulled in the sdlc-manager schema
migration and exposed a CI failure in `board_wip`: mocked legacy WIP limits were ignored when no
`sdlc_schema` was present.

**Evidence.** PR #158 CI failed
`tests/test_sdlc_manager.py::TestWipLimitsConfigurable::test_uses_config_wip_limits`; local
`uv run python -m pytest -q` reproduced the same `Ready 0/10` output instead of the configured
`Ready 0/5`.

**Mechanism.** `_wip_limits()` was changed to read schema-backed board limits first, but the
migration removed the previous `legacy_rollout_config.wip_limits` fallback path. Test fixtures and
older operator configs that intentionally inject only legacy config then silently fell through to
defaults.

**Fix.** Keep the schema as canonical when present, and restore the Mount Olympus legacy fallback
only when schema limits are absent.

**Validation.** `uv run python -m pytest tests/test_sdlc_manager.py::TestWipLimitsConfigurable -q`
and `uv run python -m ruff format --check .` pass after the fix.

**Generalizable rule.** When migrating plugin runtime config from a legacy source to a canonical
schema, encode the fallback contract directly in tests before deleting old read paths.

**Refs.** PR #158.

---

## 2026-05-27

### Setup commands must prove every bundled asset path exists  {#team-setup-asset-drift}

**Context.** The `team-execution` v2 validator port reworked `/team-setup` and exposed that the
existing command referenced `docs/example_tmux.conf` and `docs/agent-overflow.sh`, but the plugin
did not actually ship those files.

**Evidence.** `tests/test_team_execution_plugin.py::test_team_setup_references_existing_assets`
failed before the port because `plugins/team-execution/docs/example_tmux.conf` was absent. The
fix adds both files under `plugins/team-execution/docs/` and keeps `/team-setup` pointing at those
packaged paths.

**Mechanism.** The setup command evolved as operational documentation, but no repository check tied
its copy commands to real plugin assets. The command could therefore promise an install path that
worked only in a developer's local config, not from a fresh plugin package.

**Fix.** Add packaged setup assets and a contract test that every `/team-setup` asset reference
resolves in the plugin tree (commit pending).

**Validation.** `uv run pytest tests/test_team_execution_plugin.py -q` now passes.

**Generalizable rule.** Any plugin command that copies, installs, or references bundled files needs
a manifest-style test proving those paths exist in the package, not just in a developer's machine.

**Refs.** DECISIONS [team-execution validators](DECISIONS.md#team-execution-v2-validators).

---

## 2026-05-26

### Channel-plugin notifications don't reach `--bg` / `/bg` sessions: Claude Code's carry-through set excludes channels  {#cc-channels-bg-not-supported}

**Context.** Phase 2.5 (PRs #144-#151) added env-var-driven auto-connect (`CLAUDE_CHANNEL_AUTO_CONNECT=1`) and a `claude-channel` wrapper, designed to enable Phase 5's "Mimir programmatically spawns a CC session" pattern. The wrapper successfully propagates env to background-dispatched sessions via claude's `--settings '{"env":{...}}'` JSON (verified with `ps eww -p <mcp-pid>` — env vars present in the MCP server's environment). The plugin auto-connects, registers presence in Redis, and creates the consumer group. The XREADGROUP loop reads each XADD'd inbound message and `xack`s it cleanly. But **Claude inside the dispatched bg session never sees the `<channel>` notification in its context** — no `↳ redis-channel: <text>` line in the attached terminal, no LLM-side processing, no reply.

**Evidence.**
1. **Empirical round-trip test (passes in foreground, fails in --bg):**
   - Foreground `claude-channel --session-name plugin-testing-2271` → auto-connected to `mimir`, XADD'd test inbound, Claude replied: `'Confirmed — foreground auto-connected session received your message on endpoint mimir. Reply path working.'` → outbound stream got it. ✓
   - `claude-channel --bg --session-name plugin-testing` → auto-connected, presence registered, consumer thread attached (XINFO GROUPS showed `consumers=1 pending=0 last-delivered-id=<my-msg-id>`), but no notification rendered in the attached bg session's terminal, no outbound reply. ✗
   - Running explicit `/redis-channel-connect` inside the bg session (to rebuild the consumer with a guaranteed-live `ctx`) made no difference — confirms NoopNotifier-vs-AsyncNotifier wasn't the issue.
2. **Process inspection (bg-spare daemon claim):** `ps -ww -p <bg-session-pid>` showed the bg session's claude was invoked as `claude --bg-spare /tmp/cc-daemon-501/<id>/spare/<n>.claim.sock` — completely different argv than what our wrapper passed. **No `--dangerously-load-development-channels` flag in the bg-spare process's argv.** The dispatching `claude --bg ...` call only applies its flags to the supervisor-dispatch action; the spare process that actually runs the dispatched session has its own argv set by the daemon, not the caller.
3. **`/bg` (from inside a running session) behaves the same way.** A foreground session that was working perfectly (plugin-testing-2271, full round-trip verified) had `/bg` invoked. After `/bg`: the session was *removed* from the Redis registry (v0.4.6 graceful disconnect cleanup fired during the foreground claude's shutdown), and the new bg-spare that took over the session ID came up without dev-channels enabled — so it didn't auto-connect or receive notifications.
4. **Documentation confirmation** (via claude-code-guide subagent against the agent-view docs): the flags that carry through from a `--bg` dispatch (or `/bg`) to the dispatched session are: `--mcp-config`, `--strict-mcp-config`, `--settings`, `--add-dir`, `--plugin-dir`, `--fallback-model`, and directories added with `/add-dir`. **`--dangerously-load-development-channels` and `--channels` are deliberately not in this set.** Channels are session-specific opt-ins, intended only for foreground use; the docs don't expose a config knob (settings.json key, env var, plugin manifest field) that says "enable this channel by default for future sessions."

**Mechanism.** Claude Code's bg-dispatch model is supervisor + spare-process pool. The user-facing `claude --bg ...` or `/bg` is a *handoff*, not a context-clone: the supervisor claims a spare process from its pre-warmed pool, hands the session-id + (a few) carry-through flags to it, and that spare process starts a fresh Claude with just those flags. The original claude process — including its loaded channels plugin, its MCP servers, and its `--dangerously-load-development-channels` config — exits or detaches. Channels are deliberately scoped to the launching session because they're an interactive concept (someone routing messages into "your" claude session), not a worker-process concept (bg agents are independent tasks).

Internally, our MCP server's `_enable_channel_capability` monkey-patch declares `claude/channel` in the initialize response, but **only a Claude Code client that was launched with the channels feature opted-in (via `--dangerously-load-development-channels` for research preview, or `--channels` later) will recognize and route those `notifications/claude/channel` events to the model's context.** A bg-spare that wasn't launched with the flag accepts the notification at the MCP-protocol level (no handshake error) but drops it before surfacing to Claude — which is why the consumer thread on the server side sees its message ack'd successfully while nothing reaches the model.

**Fix.** Not a code fix; an architecture acknowledgment. Phase 2.5 shipped a correct + working solution for the foreground auto-connect case. The bg-dispatch case is not currently solvable from the plugin side. Two practical workarounds for "long-running session that consumes from Redis":
1. **Foreground inside tmux.** `tmux new-session -d -s <name> 'claude-channel --session-name <name>'` runs claude foreground (PTY-backed) but detaches the user's terminal. The session has the dev flag in its argv → channels work. User can `tmux attach -t <name>` to inspect. This is the Phase 5 spawn primitive going forward. *(Funny twist: my v0.4.15 tmux work was right architecture, wrong reasoning — I cited PTY allocation, but the actual reason tmux helps is "keeps the session foreground from Claude Code's POV.")*
2. **Pre-launched dedicated foreground sessions.** User opens an iTerm/Terminal window with claude-channel running once; that long-lived session listens. Less flexible than spawn-on-demand but no tooling needed.

Phase 5's plan section ([[plan-file]] §5) currently assumes `claude --bg` works for Mimir-spawn; that section needs revising to mandate tmux-wrapped foreground sessions (or document an Anthropic feature request for adding channels to the carry-through set).

**Validation.**
- Foreground round-trip: outbound payload `'Confirmed — foreground auto-connected session received your message on endpoint mimir. Reply path working.'` proves the full pipeline (auto-connect → presence → inbound → notification → model → reply tool → outbound) works in foreground.
- Bg round-trip: 4 separate test inbounds (Phase 2.5 testing across v0.4.15 → v0.4.18 + post-`/bg`) all showed the same pattern: consumer reads + acks, no reply.
- Docs-side validation: claude-code-guide subagent against Claude Code agent-view docs confirmed the carry-through flag list. Nothing in `settings.json` schema for channel defaults.

**What surprised.**
1. The `--settings '{"env":{...}}'` env injection (v0.4.17) and the auto-connect-fallback (v0.4.18) BOTH worked — env DID propagate to bg-spare, MCP server DID auto-connect, presence DID register, consumer DID read. But channel-notification routing is a separate Claude Code-client-side concern that none of those mechanisms touch.
2. `/bg` is not a context-switch; it's a process hand-off. The foreground claude exits cleanly (our v0.4.6 graceful-disconnect cleanup fires and HDEL's the registry) — which is exactly the behavior you'd want, but it means there's no "still the same session, just running in the background" semantic.
3. claude-codex's `--settings` pattern (which we copied for env propagation) is for ANTHROPIC_BASE_URL / model / proxy config — none of which are dev-channels-related. Codex doesn't have this problem because it doesn't use channels.
4. The MCP-server side declaration of `claude/channel` capability via `_enable_channel_capability` is necessary but not sufficient — the *client* must also opt in via `--channels` / `--dangerously-load-development-channels`. A spare-process started without the flag silently drops channel notifications.

**Generalizable rules.**
- **Channel plugins are foreground-only today.** If your plugin uses `notifications/claude/channel`, design for `claude` launched in an interactive context (terminal or tmux pane). Don't assume `--bg` or `/bg` will keep channels working; they won't, even when MCP servers, env, and tools all propagate correctly.
- **Carry-through ≠ inheritance.** When Claude Code "dispatches" a session (bg-spare, agent-spawn, etc.), it's not forking your current process — it's claiming a fresh worker and passing it a small, *documented* set of flags. Always verify your launch flag is in that set before assuming it'll propagate. Flags NOT in the set: `--dangerously-load-development-channels`, `--channels`, anything model-specific, anything debug-specific, plus most experimental features.
- **For programmatic-spawn ("Mimir starts a session for me"), tmux is the right primitive while channels stay research-preview.** tmux gives you: detached-from-user-terminal but foreground-from-claude's-POV, plus a way to inspect/attach later. The CLI invocation looks like: `tmux new-session -d -s <name> 'claude-channel --session-name <name>'`.
- **When debugging "Claude doesn't see my MCP notification": always check both server-side emit AND client-side capability.** Server-side: monkey-patch + emit work. Client-side: `--dangerously-load-development-channels` (or its successor) must be in the claude process's argv that's *actually receiving* the notification — not the one that dispatched it.

**Refs.**
- Phase 2.5 PRs #144-#151 (v0.4.11 through v0.4.18) trace the chase
- Existing [[cc-channels-surface-split]] entry (related: terminal/channel surface split by design)
- claude-code-guide subagent output (this conversation)
- `~/bin/claude-codex` for the `--settings` env pattern (line 327-333) we copied for env propagation
- Plan file §5 (Phase 5 — Hybrid intelligence) needs updating to mandate tmux-wrapped foreground for the spawn primitive

---

### Claude Code Channels split terminal + channel surfaces *by design* — stop trying to mirror them  {#cc-channels-surface-split}

**Context.** After Phase 2 text-bridge worked end-to-end (PRs #128-138), the local-terminal UX bothered Jeff: the inbound `<channel>` notification rendered as `↳ redis-channel: <text>`, but Claude's reply rendered only as `Called plugin:redis-channel:...` — no visible reply text in the terminal. Drove five iterative attempts (v0.4.5–v0.4.10) to make Claude emit a text_block alongside the `reply` tool call. None worked. Turns out we were fighting documented Claude Code Channels design intent, not a bug.

**Evidence.**
- Discord plugin source (`~/.claude/plugins/cache/claude-plugins-official/discord/0.0.4/server.ts:456`):
  ```
  instructions: [
    'The sender reads Discord, not this session. Anything you want them to see
     must go through the reply tool — your transcript output never reaches their chat.',
    ...
  ]
  ```
  No "MANDATORY mirror text in both places" guidance. The Discord plugin *embraces* the surface split.
- Anthropic docs Jeff surfaced: *"When using Claude Code Channels (for Discord or Telegram), it is normal behavior that messages sent within the terminal session are not visible in the Discord channel, and vice-versa. This design is intended to separate remote task execution from active local terminal work."*
- Cheap self-report test (v0.4.9 turn at 14:06): asked Claude to repeat its prior reply verbatim. Claude replied: `'no text block, only tool call.'` — confirming via self-report that Claude is intentionally not emitting transcript text for channel-triggered turns.
- Five coaching iterations (v0.4.5 soft framing, v0.4.7 MANDATORY, v0.4.8 echo-removal, v0.4.9 two-user reframe, v0.4.10 coaching delivered via `instructions=` instead of inert agent file) produced **zero observable behavior change**.

**Mechanism.** Claude Code Channels (`notifications/claude/channel` capability) are architected as a *separation* feature: the channel surface is a router endpoint where remote users live; the local terminal is for the developer driving the session. Mirroring the channel content into the terminal would defeat the point ("active local terminal work" gets cluttered with remote chatter the developer didn't initiate). Claude's training reflects this — notification-triggered turns produce `[tool_use(reply)]` without a text_block because the inbound is treated as a remote-user event, not a local prompt. Coaching to override this loses to training every time.

**Fix.** Stop chasing it. Three of the five versions were dead-end coaching iterations — net zero behavioral change but we kept v0.4.10's architectural move (coaching into `instructions=`) because it's the *right place* for any future coaching independent of this question. v0.4.6 stream cleanup + v0.4.10 instructions-delivery are real correctness fixes; the coaching wordsmithing in 0.4.7/0.4.8/0.4.9 was chasing a non-bug.

**Validation.** Discord plugin source confirms intent; Anthropic docs confirm design; Claude's own self-report confirms the model isn't going to comply with mirror coaching. Three convergent evidence sources.

**What surprised.**
1. `agents/*.md` files in a Claude Code plugin are **subagent definitions invoked via the `Agent` tool — they are NOT auto-loaded into the system prompt.** I'd assumed `agents/coach.md` was an always-on context document. Empirical proof: editing the agent file four times (v0.4.5/0.4.7/0.4.9) produced no behavior change; moving the same content into FastMCP's `instructions=` field (v0.4.10) finally landed it in the system prompt as visible "MCP Server Instructions". The discord/imessage/telegram official plugins have **no `agents/` directory at all** — all their runtime coaching lives in `instructions=`. That's the canonical pattern.
2. Claude's self-report when asked about its own prior output was honest and useful (`'no text block, only tool call.'`). I'd half-expected a hallucination; instead the model accurately reported what it did. Worth remembering: ask the model itself when you want to know what just happened.
3. The Discord plugin doesn't try to fix this gap because it isn't a gap from Anthropic's POV — the channel surface and terminal surface are intentionally distinct audiences with distinct content.

**Generalizable rules.**
- **For Claude Code plugins, runtime behavior coaching belongs in the MCP server's `instructions=` field, not in `agents/*.md`.** Agent files define subagents invokable via the `Agent` tool — they are not auto-loaded into the active conversation context. Coaching that must apply on *every* turn (especially notification-triggered ones, where no Agent invocation happens) must live in `instructions=` to actually reach Claude.
- **Before chasing a "Claude isn't doing X" issue, check whether X is intended design.** Read what the official plugins (`claude-plugins-official/discord`, `imessage`, `telegram`) actually do in their `instructions=` strings. If they don't try to do X either, X probably isn't expected. Anthropic's official plugins are the canonical reference for "what behavior Claude Code intends with this feature."
- **When you've made three coaching changes with no observable effect, stop and verify the coaching is even being delivered to the model.** "I changed the coach four times and Claude still does the same thing" is strong evidence the coaching isn't reaching Claude — go check the delivery mechanism (`instructions=`, `system_prompt`, `CLAUDE.md` scope, agent activation conditions) before changing the words again.
- **Claude can self-report on its own prior output reliably for simple yes/no factual questions about message structure.** "Did you emit X in your previous turn?" → useful diagnostic. Don't confuse this with "what were you thinking?" (that one's unreliable).

**Refs.**
- `plugins/redis-channel/CHANGELOG.md` (v0.4.5 → v0.4.10 entries trace the chase)
- PRs #137 (v0.4.5), #139 (v0.4.7), #140 (v0.4.8), #141 (v0.4.9), #142 (v0.4.10)
- Discord plugin source: `~/.claude/plugins/cache/claude-plugins-official/discord/0.0.4/server.ts:455-465`
- Plan: `~/.claude/plans/i-would-like-to-distributed-hanrahan.md` — terminal-UX expectations were unstated in the original plan; this learning clarifies for Phase 3+ that voice-routing UX matters but local-terminal mirroring is out of reach.

---

## 2026-05-25

### Channel-plugin naming: noun-channel, not noun-bridge  {#redis-channel-rename}

**Context.** Shipped the plugin as `redis-bridge` through Phases 0-2 (PRs #127-131). Jeff flagged the name as too generic: Anthropic's official channel plugins are named after what they connect to (`discord`, `telegram`, `imessage`), and "bridge" loses the signal that this is a `notifications/claude/channel`-emitting MCP server vs. a tool-only MCP. Renamed to `redis-channel` before Phase 3 work (which will pair with the not-yet-built router-side repo).

**Evidence.** Naming convention from official Claude Code plugins: the plugin name = the system it bridges to. `discord`, `telegram`, `imessage` etc. For redis-channel, the plugin is deliberately Hermes-agnostic — the only thing it "knows about" is Redis. So `redis` + `-channel` suffix to signal channel-protocol-emitting plugin. Slug "channel" parallels the discord/telegram pattern in that it identifies what kind of plugin this is at a glance.

**Mechanism (of why bridge was wrong).** "bridge" is generic — could mean anything that connects two things. "channel" is a specific term in the Claude Code MCP spec referring to plugins that emit `notifications/claude/channel`. Naming a Claude Code channel-plugin `*-channel` makes the type self-documenting; `*-bridge` doesn't. Cost of late rename: every Phase 3+ writeup would have propagated the wrong shape.

**Fix.** Single PR renames 33 files end-to-end:
- `plugins/redis-bridge/` → `plugins/redis-channel/` (git mv preserves history)
- `redis_bridge_*` MCP tool names → `redis_channel_*`
- `/redis-bridge-*` slash commands → `/redis-channel-*`
- Logger `redis_bridge.channel` → `redis_channel.channel`
- `~/.claude/channels/redis-bridge/` runtime config dir → `~/.claude/channels/redis-channel/`
- Marketplace entry name + plugin.json + `.mcp.json` server key
- 9 test files renamed
- 6 slash command files renamed
- Plugin version 0.3.0 → 0.4.0 (signals breaking-name change)
- All `redis-bridge` references in README/CHANGELOG/coach/journal prose
- Auto-memory files updated

**Preserved deliberately**:
- Two engineering-journal anchor slugs (`#redis-bridge-verification`, `#redis-bridge-decoupled`) per the journal convention "keep slugs stable". Their titles + prose now say "redis-channel" but the slug stays as a historical ID for any external link.
- Zero protocol breakage: the Redis namespace `cc-sessions:*` doesn't reference the plugin name, so router-side and existing-Redis-state need no migration. PROTOCOL.md unchanged in semantics.

**Validation.** All 387 unit tests pass. Headless integration test passes all 4 phases (live olympus-bus Redis): real connect, inbound XADD → notifications/claude/channel notification, reply tool XADD round-trip, graceful disconnect, SIGKILL+lazy-GC.

**What surprised.** How clean the rename was. The plugin's Redis-side wire format (`cc-sessions:*`) was deliberately not bound to the plugin name in PROTOCOL.md, so we got the "free" rename property: old Redis state stays valid, the (not-yet-built) router doesn't need to know the plugin was renamed. The lesson there is about loose coupling at protocol boundaries: **name your wire format independently of your plugin name**.

**Generalizable rule.** **For Claude Code channel-emitting plugins, use the `<target>-channel` shape** (parallels `discord`/`telegram`/etc.). Avoid generic suffixes like `-bridge` / `-mcp` / `-server` — those describe an implementation detail, not what the user will reach for in `/plugin install`. Catch this naming question before Phase 1, not after Phase 2.

**Refs.** PR for the rename; previous PRs #127-131 under the old name.

---

### Redis password URL-injection broke on URL-special characters  {#redis-url-password-encoding}

**Context.** Phase 2 headless integration test against live olympus-bus Redis failed at the `redis_channel_connect` call with `"Port could not be cast to integer value as 'YPPu3qQ0VkURKkkm1J81l4'"`. The "port" was actually a suffix of the 44-char Hermes Redis password. fakeredis unit tests had passed because the test password was the literal string `"password"` with no URL-special chars; the bug was invisible in unit tests.

**Evidence.** `plugins/redis-channel/server/redis_client.py:resolve_url_with_password` was building the netloc as `f":{password}@{host}:{port}"` with the raw password. When the password contained `:` (the user:password separator) or `@` (the auth:host separator), redis-py's URL parser tokenized it wrong and tried to interpret a substring as the port number.

**Mechanism.** Real Redis passwords from password generators or `openssl rand -base64 32` contain `:`, `+`, `/`, `=`, `@` etc. URL syntax for `://user:pass@host:port/db` is positional: the parser scans for the next `:` after the user (which would be inside our unencoded password). The fix is straightforward — `urllib.parse.quote(password, safe="")` — but the bug class is wider: **any URL component built from external input MUST be URL-encoded if not coming from a URL itself**.

**Fix.** `urllib.parse.quote(password, safe="")` on both the password and username before injection. Eight new regression tests in `tests/test_redis_channel_redis_client.py` covering: no password / unset env / empty env / simple password / password with `:` / with `@` / with `/` / base64-shaped 44-char password / db-index preservation. Commit on Phase 2 follow-up.

**Validation.** Headless integration test rerun: all 4 phases pass end-to-end against live olympus-bus Redis. Real password (44 chars, base64-style) connects cleanly; redis-py URL parser doesn't barf.

**What surprised.** That the unit test suite — which had 76 fakeredis-backed cases by that point — never caught it. The seam was at the URL-build → `redis.Redis.from_url` boundary, and our fakeredis fixture bypasses URL parsing entirely (you instantiate `FakeRedis()` directly). A integration test against real Redis was the first thing that exercised the URL parser.

**Generalizable rule.** **Anytime you interpolate a value into a URL component, URL-encode it.** Doubly true when the value comes from an environment variable / user config / secret that you don't control the shape of. And: **fakeredis-backed unit tests don't exercise the URL parser** — for any plugin that builds Redis URLs, an integration test against real Redis is the only way to catch URL-formatting bugs.

**Refs.** `plugins/redis-channel/server/redis_client.py`, `tests/test_redis_channel_redis_client.py`, headless integration test at `$CLAUDE_JOB_DIR/integ_test.py`.

---

### FastMCP stdio loop doesn't exit on SIGTERM  {#fastmcp-stdio-sigterm}

**Context.** Phase 2 integration test's MCPClient.shutdown() called `proc.terminate()` (sends SIGTERM) and waited 5s, then fell back to SIGKILL. Every shutdown of the server process logged `[harness] server didn't exit on terminate; SIGKILL`. The redis-channel server installs SIGTERM handlers, but they don't fire fast enough for shutdown to complete in 5s.

**Evidence.** `plugins/redis-channel/server/channel.py:_install_signal_handlers` installs a handler that calls `_STATE.shutdown()` then `sys.exit(0)`. In practice the server only exits when its stdin closes (FastMCP's stdio transport blocks on the read loop). SIGTERM gets queued but doesn't interrupt the async stdin reader.

**Mechanism.** FastMCP runs the MCP server inside an `asyncio.run()` that drives `stdio_server()`. The stdio transport reads from stdin via `anyio` streams, which on macOS uses kqueue-backed file descriptors. SIGTERM is delivered to the Python process but the asyncio loop doesn't have a signal handler for it (we install a *signal* handler, not a *loop signal handler* via `loop.add_signal_handler`), so the handler runs synchronously on the main thread but can't preempt the blocking read.

**Fix (queued, not blocking).** Adding `loop.add_signal_handler(SIGTERM, ...)` would let asyncio receive the signal and cancel the stdio task. Out of scope for Phase 2's headless test (the integration test works fine with the SIGKILL fallback); queued for Phase 6 polish.

**Validation.** Integration test passes end-to-end despite the SIGKILL fallback. Server's atexit-registered cleanup still fires before kill (registry HDEL + hb DEL via the previous disconnect call in phase C; SIGKILL'd-phase server in phase D was *meant* to skip cleanup to test the stale-GC path).

**What surprised.** That the signal handler we installed runs but doesn't actually break the server out of its async loop within a useful timeframe. The classic Python signal trap — synchronous handlers can't interrupt blocking syscalls cleanly.

**Generalizable rule.** **In FastMCP-based stdio servers, use `asyncio.get_running_loop().add_signal_handler(...)` instead of `signal.signal(...)` for graceful shutdown.** Plain `signal.signal()` works at the language level but the asyncio loop doesn't see it, so it can't cancel the stdio read task. For tests / orchestration: don't rely on SIGTERM-then-wait for a clean exit; close stdin or fall back to SIGKILL.

**Refs.** `plugins/redis-channel/server/channel.py:_install_signal_handlers`. Queued follow-up.

---

### Headless integration test caught two bugs unit tests didn't  {#integ-test-value}

**Context.** Built a headless harness that drives `python -m server` over real JSON-RPC stdio against live olympus-bus Redis. 4 phases: connect+inbound+notification round-trip, reply outbound XADD, graceful disconnect, SIGKILL+lazy GC. First run failed phase A with the Redis password URL-encoding bug above; second run (after fix) passed all 4 phases.

**Evidence.** Harness lives in `$CLAUDE_JOB_DIR/integ_test.py`. Bugs caught:
1. **Password URL-encoding** ([see entry above](#redis-url-password-encoding)) — would have shipped to first manual user run.
2. **FastMCP SIGTERM behavior** ([see entry above](#fastmcp-stdio-sigterm)) — known FastMCP-side issue but our wrapper code didn't paper over it.

Validated:
- Real `XREADGROUP` + `XADD` round-trip against Redis 7.0.15.
- AsyncNotifier successfully marshals `notifications/claude/channel` from the consumer thread → asyncio loop → JSON-RPC stdout.
- `_msg_id` correlation works end-to-end.
- `reply` tool XADDs the full Outbound payload with all fields (session_name, endpoint, chat_id, text, voice, in_reply_to, ts) round-tripping correctly.
- Lazy stale-GC: kill server without unregister → fresh server's `list` call lazily HDELs the stale registry entry.

**Mechanism.** fakeredis is a pure-Python redis-protocol implementation that doesn't go through redis-py's URL parser — you construct `FakeRedis()` directly. Anything that breaks at the URL-build → `Redis.from_url()` boundary is invisible to fakeredis-backed tests. Real Redis exercises the full stack including URL parsing, authentication handshake, stream consumer groups, and pubsub.

**Fix (artifact).** Promoting the harness into `plugins/redis-channel/scripts/integ_test.py` so it lives with the plugin. Won't run in CI (needs real Redis + a keychain password) but documented as the way to verify before manual ship.

**Generalizable rule.** **For Redis-backed plugins, a live-Redis integration test is non-optional.** Unit tests with fakeredis verify the plugin's own logic; they cannot verify URL encoding, auth handshake, or any behavior that depends on the real wire protocol. Write the integration test as soon as you have a Redis to point at — even a synthetic harness like the one for redis-channel catches real bugs the unit suite can't.

**Refs.** `$CLAUDE_JOB_DIR/integ_test.py` (transient), `plugins/redis-channel/scripts/integ_test.py` (after promotion).

---

### Wrong-hostname propagation: stale plan + memory beats current inventory  {#redis-host-mac-mini-vs-olympus-bus}

**Context.** Plan + Phase 1 example config + Phase 2 PR body all asserted Redis lived at `jeffs-mac-mini.infiquetra.com:6379`. User caught it during verification-recipe handoff: Redis is actually on `olympus-bus.infiquetra.com` (10.220.1.64), a Proxmox-cluster VM. Migration off the Mac mini happened 2026-04-26 per `home-lab/ansible/inventory/hosts.yml` (`redis_bus` group, comment: "Renamed from olympus_bus 2026-04-26 (legacy pull-queue scaffolding stripped)").

**Evidence.**
- `home-lab/ansible/inventory/hosts.yml` redis_bus group: `olympus-bus.infiquetra.com → 10.220.1.64`.
- `host olympus-bus.infiquetra.com` → `10.220.1.64` (resolved).
- `nc -zv olympus-bus.infiquetra.com 6379` → Connection succeeded.
- The redis-channel plan I'd written days earlier included this in its "Resolved by verification" section: `Redis auth + reachability: 10.220.1.64:6379 reachable`. The IP was right; I just paired it with the wrong hostname.
- Wrong references shipped in three files: `plugins/redis-channel/docs/registry.example.json`, `plugins/redis-channel/commands/redis-channel-configure.md`, `plugins/redis-channel/skills/redis-channel/SKILL.md`. All fixed in this PR.

**Mechanism.** The plan was written from incomplete-context exploration, and the "Mac mini" / "Hermes Redis" association got cemented before I'd re-verified the actual host. Memory carried the IP forward but lost the hostname/host-association. When I wrote the example registry config in Phase 1, I reached for a hostname from conversation context (Mac mini) without re-checking the inventory. Twice in Phase 2 follow-up writeups I propagated the same wrong fact. The user's CLAUDE.md explicitly warns against this pattern ("Validation Discipline — NEVER assert without checking"), and I violated it.

**Fix.** Corrected the three files. Saved a feedback memory ([[verify-infra-facts-against-home-lab]]) + a reference memory ([[redis-bus-location]]) so future-me has both the rule and the canonical fact in one place. MEMORY.md updated to surface both at the top of the index.

**Validation.** `grep -rn jeffs-mac-mini plugins/redis-channel/ docs/` now empty for the redis-channel references. `host olympus-bus.infiquetra.com` and `nc -zv ... 6379` both succeed.

**What surprised.** That the wrong fact survived three writeups (Phase 0 plan, Phase 1 PR, Phase 2 PR body) even though my memory had the correct IP. The IP and the hostname are normally bound; here they got decoupled because I'd seen `10.220.1.64` in one context (Hermes Redis) and "Mac mini" in another (voice work) and merged them.

**Generalizable rule.** **Don't write infrastructure facts (hostnames, IPs, service-host mappings) into shipped code or docs without grepping `home-lab/ansible/inventory/` or live-probing first.** Plan documents and conversation context are not authoritative for infra — the home-lab inventory is. Plans from N days ago describing "where service X runs" are especially suspect because of the ongoing Mac-mini→Proxmox migrations. If you can't verify in the current context, say "I'd need to check — let me verify" instead of asserting. Mac mini hostnames are the highest-risk class because they're the legacy location for many services that have since moved.

**Refs.** [[verify-infra-facts-against-home-lab]] memory, [[redis-bus-location]] memory, `home-lab/ansible/inventory/hosts.yml` redis_bus group.

---

### Emitting custom MCP notification methods from FastMCP  {#fastmcp-custom-notification}

**Context.** Phase 2 of `redis-channel` needs the MCP server to emit `notifications/claude/channel` — a notification type that's specific to Claude Code's channel protocol and **not** part of the upstream MCP spec. FastMCP's `Context` exposes `log/info/debug/error/elicit` but none of those emit a custom method name. The underlying `ServerSession.send_notification` accepts a typed `SendNotificationT` union, and Claude's `notifications/claude/channel` is not in that union.

**Evidence.**
- `[m for m in dir(Context) if not m.startswith('_')]` → no raw `send_notification` exposed.
- `ServerSession.send_notification` signature: `(notification: SendNotificationT, related_request_id)`. `SendNotificationT` is a discriminated union over Pydantic Notification subclasses keyed on the method literal — no `"notifications/claude/channel"` variant.
- But `mcp.types` also exports `Notification[Union[dict[str, Any], NoneType], str]` — a fully-generic Notification[params, method-as-str] form. This is the escape hatch.

**Mechanism.** `send_notification` doesn't actually validate that the notification method is in the spec union — it just calls `notification.model_dump(by_alias=True, mode='json', exclude_none=True)` and wraps the result in a `JSONRPCNotification`. The discrimination happens via Pydantic, but a generic `Notification[dict, str]` instance has `method: str` so it passes through verbatim. Static typing rejects it (`type: ignore[arg-type]` needed), runtime accepts it.

**Fix.** `plugins/redis-channel/server/notifier.py` constructs `Notification[dict, str](method="notifications/claude/channel", params=payload)` and passes it to `session.send_notification(notif)` with a type-ignore. Threadsafe scheduling via `asyncio.run_coroutine_threadsafe` because the consumer thread isn't on the asyncio loop.

**Validation.** Phase 2 unit test `test_async_notifier_schedules_coroutine` constructs an AsyncNotifier with a stub session + a real asyncio loop running on a side thread, calls emit, and verifies the stub session's `send_notification` was awaited with `method="notifications/claude/channel"` and `params` matching.

**What surprised.** The MCP SDK exports a fully-generic `Notification[params, method-as-str]` type. Looking at the dir() of `mcp.types`, the entry `'Notification[Union[dict[str, Any], NoneType], str]'` was the giveaway — that's exactly the escape hatch for vendor-specific notification methods.

**Generalizable rule.** When you need to emit an MCP notification method that isn't in the SDK's `ServerNotificationType` union (Claude-specific extensions like `notifications/claude/channel`, or any other downstream extension): use the generic `Notification[dict, str]` form with a string method, accept the `type: ignore[arg-type]` on `send_notification`, and don't try to wedge it into the typed union. Static typing was wrong to demand discrimination here — the JSON-RPC protocol itself doesn't care.

**Refs.** `plugins/redis-channel/server/notifier.py`; Phase 2 PR.

---

### `@dataclass(slots=True)` doesn't expose class-level field defaults  {#dataclass-slots-class-defaults}

**Context.** While building `plugins/redis-channel/server/registry.py`, the loader read each config field via `defaults_raw.get(key, Defaults.heartbeat_seconds)` — reaching into the dataclass class to pull the field default. Five tests failed with `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'member_descriptor'`.

**Evidence.** Reproducer:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class D:
    n: int = 10

print(type(D.n))  # <class 'member_descriptor'>  ← not int!
print(D().n)     # 10  ← only an *instance* has the value
```

`pytest` failure trail at `plugins/redis-channel/server/registry.py:130` calling `int(Defaults.heartbeat_seconds)`. Fix commit in this PR replaces `Defaults.<field>` with `base = Defaults(); base.<field>`.

**Mechanism.** With `slots=True`, the dataclass `__slots__` machinery installs *descriptors* on the class to mediate per-instance attribute storage. Looking up `D.field` returns the descriptor object itself, not the field's default. Without `slots=True`, the class still has plain class attributes that happen to equal the defaults — so the pattern works by accident, masking the bug for any non-slotted dataclass. `dataclasses.fields(D)[i].default` is the *correct* way to read a field's default without instantiating.

**Fix.** Construct a `Defaults()` instance first and pull values off it; commit on branch `worktree-redis-channel-phase1` (this PR).

**Validation.** 35 unit tests across session_id, registry, and presence now pass (was 30 passing + 5 failing).

**What surprised.** The error message ("not a real number") gives no hint that the issue is `slots=True`. I assumed a JSON-parsing bug for several minutes before the traceback pointed at `int(Defaults.heartbeat_seconds)`.

**Generalizable rule.** When you put `slots=True` on a dataclass, **do not read field defaults via `Class.field`** — that pattern returns the slot descriptor, not the default. Either (a) instantiate a default object and read from it, (b) call `dataclasses.fields(Class)`, or (c) drop `slots=True` if you want the convenience. This bug is invisible without slots, so it only shows up after you turn slots on for memory/lookup reasons.

**Refs.** Phase 1 PR for redis-channel.

---

### MCP Python SDK's `RedisLike` Protocol stricter than the runtime  {#redis-like-protocol-too-strict}

**Context.** I declared a `RedisLike` `typing.Protocol` in `redis_client.py` to allow both `redis.Redis` and `fakeredis.FakeRedis` (used in tests) as Presence inputs without circular typing. mypy rejected `Presence(redis.Redis(...), ...)` because `redis.Redis.exists` returns `Awaitable[Any] | Any` (covering both sync and async clients) and my Protocol declared `-> int`.

**Evidence.** mypy on `channel.py:78`:

```
error: Argument 1 to "Presence" has incompatible type "Redis"; expected "RedisLike"
note: Following member(s) of "Redis" have conflicts:
note:     Expected: def delete(self, *names: str) -> int
note:     Got: def delete(self, *names: bytes|str|memoryview[int]) -> Awaitable[Any]|Any
```

**Mechanism.** `redis-py` types its client union-style (sync + async share one class hierarchy) so every call returns `Awaitable[Any] | Any`. A narrowed Protocol that promises a concrete return type can never be satisfied by such a wide union, even though the runtime behavior is exactly what we want.

**Fix.** `RedisLike = typing.Any`. Code keeps duck-typing; mypy is unblocked. Both `redis.Redis` and `fakeredis.FakeRedis` work at runtime as before. Commit on branch `worktree-redis-channel-phase1`.

**Generalizable rule.** When a client library exposes both sync + async via one wide-union type, narrowing it via `Protocol` to be more useful in your code's signatures will fight you. Use `Any` (or accept that you're going to lose mypy coverage on those calls). The dynamic-typing escape hatch is the right tool here — Protocol is for protocols you actually want to enforce, not for shaving down third-party type uncertainty.

**Refs.** `plugins/redis-channel/server/redis_client.py`.

---

### Verification findings while planning the `redis-channel` plugin  {#redis-bridge-verification}

**Context.** During design of the `redis-channel` + `hermes-claude-code-router` plan, several "obvious" claims about the Hermes-side infrastructure turned out to be wrong in ways that meaningfully reshaped the architecture. This entry captures the surprises for future plan-verification work.

**Evidence.**
- An earlier exploration agent reported voice-forge on Mac mini as listening at `0.0.0.0:9876` reachable from the LAN. Direct `lsof` proved it bound to `127.0.0.1:9876` only. Not a blocker (Hermes consumes it locally) but the initial plan's "127.0.0.1:9876 from laptop" wiring was wrong.
- `home-lab/ansible/inventory/group_vars/all/all.yml` was assumed to be whole-file vault-encrypted. `ansible-vault view` fails with "Input is not vault encrypted data" — the file uses inline `!vault` tags (field-level encryption). For per-secret extraction, must use `ansible -m debug -a "var=<name>"` or the Python `VaultLib` API, not the CLI.
- Discord voice-receive code was assumed to live in `home-lab/.../asgard_voice_arbiter/`. It doesn't — the arbiter is routing-only (~250 LoC). The actual sink/decode/buffer logic is in closed-source `hermes-agent.gateway.platforms.discord`. Mirroring it from the visible code was impossible; this killed the plan's original "plugin holds Discord directly" architecture and forced the Hermes-router pattern.
- Hermes plugins CAN register MCP-style tools the LLM can call: `ctx.register_tool(name, schema, handler)` at `hermes-extensions/docs/plugin-authoring.md:54`. No existing plugin uses the API yet; the new router will be the first.
- The Claude Code channels protocol does NOT have a native facility for `AskUserQuestion`-style structured questions. Verified by reading the official Discord channel plugin source and `https://code.claude.com/docs/en/channels-reference`. Coaching Claude is insufficient; the CC plugin must intercept the tool call deterministically.
- The Mimir Discord bot (ID `1486896133660868758`, Mount Olympus guild) does NOT currently have a Hermes profile on Mac mini — `~/.hermes/profiles/mimir/` doesn't exist. Building the bridge requires creating the profile first.

**Mechanism.** Earlier exploration agents conflated **proximity** ("X is referenced near Y") with **availability** ("X is implemented in this repo"). Clearest examples: voice-receive (referenced in arbiter, implemented in hermes-agent) and voice-forge (running on Mac mini, but as a local-bound daemon, not LAN-reachable). The agents reported the references; the implementation locations weren't independently verified.

**Fix.** Build proceeds with the architecture the actual ground truth supports: `redis-channel` stays Hermes-agnostic; Hermes does all voice work via its existing pipeline; vault extraction switches to Python-based per-field; Mimir profile is a prereq before any bridge code runs. The plan's "Prerequisites" section codifies this; the LEARNINGS-flagged "I should have looked here first" findings shaped Decisions [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled) and [askuserquestion-interception](DECISIONS.md#askuserquestion-interception).

**What surprised.** That `ctx.register_tool` exists at all — initially I assumed Hermes plugins were hook-only and the LLM-fallback path would require modifying Hermes core. Reading `hermes-extensions/docs/plugin-authoring.md` end-to-end found the API in the first place I should have looked.

**Generalizable rule.** When a plan rests on "we can mirror Asgard's X" or similar reuse claims, **verify the implementation actually lives where the reference points** before committing to it. Two grep passes are cheaper than a 3–5 day rebuild. Specifically for reuse-of-existing-system claims, check that the visible code is the implementation, not just a thin wrapper around closed-source bits elsewhere.

**Refs.** [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled); plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

---

## 2026-05-08

### Missing optional validator dependencies can hide invalid manifests  {#jsonschema-hidden-validation}

**Context.** CI consolidation restored `marketplace/validator/validate.py` and added `jsonschema` to dev dependencies so schema validation runs in normal CI installs.

**Evidence.** `python3 marketplace/validator/validate.py` passed in the system environment while warning `jsonschema not installed, skipping schema validation`. Running the same validator inside a temporary environment after `pip install -e ".[dev]"` failed on `plugins/mission-control/.claude-plugin/plugin.json` because its description exceeded `marketplace/validator/schema.json`'s 200 character limit.

**Mechanism.** The validator treats missing `jsonschema` as a warning and continues. That made schema validation effectively optional in local and previous CI paths, so an invalid manifest could sit in the repository undetected until the dependency became available.

**Fix.** Added `jsonschema` to project dev dependencies and shortened the `sdlc-manager` plugin description to satisfy the schema limit.

**Validation.** `/tmp/infiquetra-plugins-verify-venv/bin/python marketplace/validator/validate.py` passes with `jsonschema` installed.

**Generalizable rule.** A validator's optional dependency is part of the validation contract. CI must install it, or invalid inputs can pass under a degraded "warning only" path.

**Refs.** `.github/workflows/ci.yml`; `pyproject.toml`; `marketplace/validator/validate.py`; `marketplace/validator/schema.json`.

---

## 2026-05-01

### Plugin code can ship without marketplace registration — the registry is a separate source of truth  {#marketplace-drift}

**Context.** A user reported that the `blueprint-reviewer` plugin did not appear when they tried to install plugins from this marketplace. The plugin's code lived under `plugins/blueprint-reviewer/` on `main` and was fully functional, but it was invisible to the marketplace UI.

**Evidence.**
- `plugins/blueprint-reviewer/` was added by PR #110 (merge commit `ae93035`) and Phase B work merged via PR #111 (commit `a7fea08`).
- Neither PR modified `.claude-plugin/marketplace.json`.
- At time of report: 15 plugin directories under `plugins/` but only 14 entries in `marketplace.json`.
- Fixed in PR #112 (commit `4da5705`).

**Mechanism.** Plugin code in `plugins/<name>/` and the marketplace registry in `.claude-plugin/marketplace.json` are independent files. PR review focused on the new plugin's code (skills, commands, scripts) and overlooked the one-line registry diff. Two PRs in a row missed it because the omission isn't visible in the plugin's own diff — it's a *missing* edit to a sibling file. Reviewers don't see absences.

**Fix.** PR #112 added the `blueprint-reviewer` entry to `marketplace.json` (mirrors `sdlc-manager`'s shape: `source`, `version`, `category: development`, keywords copied from the plugin manifest).

**Validation.** Post-merge: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print(len(d['plugins']))"` returns `15`; `'blueprint-reviewer' in [p['name'] for p in d['plugins']]` is `True`.

**What surprised.** That the bug shipped *twice* in a row (#110 and #111). The second PR was specifically follow-up work on the same plugin; the registry omission was right there to be noticed but wasn't.

**Generalizable rule.** When two files must stay in sync (plugin dir + registry, schema + migration, code + docs index, env var + Lambda config), reviewers will drift one against the other given enough opportunities. Add a CI assertion that fails on drift — don't rely on PR review.

**Refs.**
- [QUEUED.md](QUEUED.md#marketplace-ci-guard) — P1 work item for the CI guard.
- [DECISIONS.md](DECISIONS.md#gitignore-claude-and-no-uv-lock) — repo hygiene shipped alongside.
- [ARCHIVE.md](ARCHIVE.md#pr-112-marketplace-fix) — SHIPPED record.

---

### `marketplace.json` `Edit` calls must include the array's closing `]` in `old_string`  {#marketplace-edit-guard}

**Context.** When appending a new plugin entry to `.claude-plugin/marketplace.json`, the `Edit` tool can produce invalid JSON if the `old_string` doesn't include enough context to capture the array's closing bracket. This has misfired multiple times.

**Evidence.** Repeated occurrences traced through prior memory record `marketplace.json Editing Guard`. The wrong-pattern shape:

```json
    }
  ],
    {
      "name": "new-plugin",
      ...
    }
  ],
  "version": "2.0.0"
}
```

— two closing `]`, parser fails. Caught only by post-edit validation.

**Mechanism.** When `old_string` ends at the last entry's closing `}`, the `Edit` tool inserts the new content *after* the line, which lands it after the array's `]` rather than inside the array. The fix is to include both the previous last entry's closing `}` AND the array's `]` in the `old_string`, so the new entry can be inserted *before* the `]` (with a `,` added to the prior `}`).

**Fix.** Standard pattern — `old_string` extends through the array's closing `]` and at least the next line:

```
old_string: "      \"workflow\"\n      ],\n      \"category\": \"development\"\n    }\n  ],\n  \"version\": \"2.0.0\"\n}"
```

Always validate immediately: `python3 -m json.tool .claude-plugin/marketplace.json > /dev/null`.

**Validation.** PR #112 (commit `4da5705`) used this exact pattern and produced valid JSON on first try.

**Generalizable rule.** When using `Edit` on a JSON/YAML file to append into a nested array, the `old_string` MUST include the array's closing bracket. Inserting "before the `]`" is correct; inserting "after the prior entry's `}`" is wrong because edits land on the line *after* the match. Always validate the file with the language's parser immediately after the edit.

**Refs.** Same lesson cached in `~/.claude/projects/.../memory/marketplace_editing_guard.md` for runtime convenience; this file is the durable project record.

---
