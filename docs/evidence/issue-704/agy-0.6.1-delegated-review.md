# Delegated adversarial review of the subagent presentation preamble

**What this is.** The verbatim output of a genuine `agy` (Antigravity) delegation run, preserved
because the run bundle it came from lives under `.claude/`, which is git-ignored.

**Why the run happened.** Issue #704 added the house-style presentation contract to
`plugins/agy/agents/agy-coder.md` and `plugins/agy/agents/agy-reviewer.md`. Editing a plugin's
agent definitions requires a marketplace version bump (`tools/release_surface_diff_guard.py`), and
a version bump on `agy` — the fleet's only external-engine bridge — requires a delegation-proof
artifact backed by a real run (`scripts/check_delegation_proof.py`). Rather than spend that
mandatory run on a ping, it was given real work: an adversarial review of
`plugins/house-style/references/subagent-presentation-preamble.md`, the canonical source of the
very text that triggered the bump.

**Run facts** (from the bundle, and attested in
`docs/delegation-proofs/agy/house-style-preamble-review-0.6.1.proof.json`):

| field | value |
| --- | --- |
| model | Gemini 3.1 Pro (High) |
| role / mode / lens | reviewer / `no-write` / adversarial |
| `real_agy_verdict` | `real` |
| exit code / wall time | 0 / 67.05s |
| delegate output | 4,246 bytes |
| files changed | none (`changed_paths=[]`, `diff.patch` 0 bytes) |
| base commit | `715031a4` |

**Disposition.** Not folded into issue #704's branch — its `/code-review` gate had already closed
with 26 findings fixed, and the preamble text is duplicated across 36 agent-definition files, so
editing it is its own unit of work. Findings 1 and 2 below are assessed as real and are queued at
`docs/engineering-journal/QUEUED.md` `{#preamble-findings-from-the-0-6-1-delegation}`, which also
records why findings 3 and 4 were rejected.

**Provenance note.** Everything below the rule is the delegate's own text, unedited. It has not
been fact-checked line by line; the assessment of which findings survive is recorded in the queued
entry, not here.

---

1. CONTRADICTIONS
- "**Lead with the answer.** The first sentence says what you found or what is now true."
- "**Situate before you detail.** One sentence naming the repository, host, or system in play, before any number, path, or identifier."

An `agy-reviewer` agent finishes its execution and needs to report the wrapper projection path and evidence bundle path to its caller. To obey "**Lead with the answer.**", the agent must state the specific file paths in its very first sentence. To obey "**Situate before you detail.**", a complete sentence naming the repository must appear *before* any path is written. The agent cannot place a full situating sentence prior to the paths while simultaneously placing those paths in the very first sentence.

2. UNDERSPECIFIED RULES
- "**No operator ceremony.** The operator-facing closing block and the main thread's style tell belong to the main thread alone. Do not write either one."

Output 1: The agent writes a standard conversational sign-off (e.g., "Let me know if you need anything else!"), assuming this is standard helpfulness rather than an "operator-facing closing block" or a "style tell."
Output 2: The agent ends its report abruptly after its final finding with no sign-off, closing remarks, or filler.

The author most likely wanted Output 2. However, because terms like "operator-facing closing block" and "style tell" are jargon defined only in `house-style.md` (which subagents do not read), a subagent has no actionable definition of what specific text structures it is being told to suppress.

3. RULES THAT WILL BE DISOBEYED
- "**Say what you did not verify.** An unverified inference is labelled as one, in the same sentence. 'I did not check X' is a finding; a confident guess that reads like a measurement is a defect that propagates, because your caller cannot tell the two apart from the outside."

A competent model will naturally violate this because LLMs generate text probabilistically and frequently blur the epistemic line between facts explicitly read from a tool output and highly probable assumptions drawn from their training data. An agent will naturally assert standard conventions (e.g., assuming a configuration file is in the default location) as verified facts without realizing it made an inference. To detect this violation, a checker would have to extract every factual claim the agent makes, diff it against the exact raw stdout and file contents in the agent's tool transcripts, and flag any claim that does not have a direct source in the retrieved data.

4. HARMFUL RULES
- "**Report state, not activity.** 'The migration runs clean on Postgres 16' is state. 'I ran the migration and then checked the logs' is activity. State is what your caller can act on."

When a subagent fails to complete its task or hits a blocker, obeying this rule actively harms the orchestrating main thread (the reader). If an agent attempts multiple tool calls or workarounds and all fail, the main thread needs to know exactly what activity was attempted so it does not redundantly repeat those steps and can accurately debug the failure path. By suppressing the activity report, the subagent blinds the orchestrator to its trajectory, forcing the main thread to either guess what was already tried or spend extra turns digging through transcripts to recover the lost context.

5. THE SINGLE HIGHEST-VALUE EDIT
Change:
`**No operator ceremony.** The operator-facing closing block and the main thread's style tell belong to the main thread alone. Do not write either one. End when your content ends.`
to:
`**No conversational filler.** Do not write greetings, conversational sign-offs, or offers for further help. End when your content ends.`

Justification: The original text relies entirely on jargon ("operator-facing closing block", "main thread's style tell") defined in a separate `house-style.md` document that subagents are never given. As a result, the rule is unactionable for standalone subagents and fails to suppress standard LLM conversational habits. This edit replaces the opaque jargon with plain descriptions of the actual behavior you want to prevent. The modified rule becomes immediately actionable for any model without requiring external context.
