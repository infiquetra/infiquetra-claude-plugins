# TypeSafe AI documentation brief

Source: the live docs at docs.typesafe.ai, fetched as Markdown (append `.md` to any page path) starting from the index at docs.typesafe.ai/llms.txt. Every page the index lists was read, plus the migration guide referenced from TypeSafe's own Claude Code skill. Citations give the page path under docs.typesafe.ai.

## 1. What Jev / System One is and how it works

**Plain-language claim:** TypeSafe's product is not a chatbot. It is a small, fast model that takes a block of text or JSON (called "state") plus one or more typed questions, and returns typed answers with probabilities that application code acts on directly — no text generation, no parsing step.

Jev is "TypeSafe's flagship model and the first System One model"; it "evaluates typed questions against a state and returns structured results directly," with "No text generation, no parsing" (introduction.md). The System One concept page sharpens the contrast with large language models: "System One models do not write replies, produce code, or generate explanations of their reasoning" (concepts/system-one.md), whereas ordinary large language models "are designed to produce text for humans to read" (introduction.md). The name borrows from dual-process psychology: "System 1 thinking is fast and intuitive. System 2 is slower and more deliberate" (concepts/system-one.md).

**Training and calibration.** TypeSafe trains Jev with a method it calls RLCD, "Reinforcement Learning for Calibrated Decisions" — a vendor-coined term, not an industry acronym — to "return decisions and calibrated probabilities instead of generated text" (introduction/machine-learning-primer.md). Calibration is defined numerically: a probability of 0.2 "should occur about 20% of the time," 0.8 "about 80%," 1.0 "100% of the time," but "these rates describe groups of predictions, not a guarantee about any single answer" (introduction/machine-learning-primer.md; repeated on confidence.md). The primer contrasts this with human-preference training (RLHF, Reinforcement Learning from Human Feedback), which "can also reward sycophancy and confident-sounding hallucinations" and causes "mode dropping" — favoring one stylistic mode over others. No benchmark numbers or third-party evaluations appear anywhere in the docs.

**What it explicitly should not be used for.** The current model's own "jaggedness" page lists nine documented weak spots (model-jaggedness/jev-1.13.md): (1) literal reading — "answers the question you wrote, not the one you meant," including negations taken at face value; (2) weak at math — "Jev is not a calculator"; (3) weak at date/time comparison — "reads dates as text, not as ordered quantities"; (4) accuracy loss on multi-hop indirection and double negatives; (5) accuracy falls as state grows with irrelevant content; (6) not adversarially robust by default — injected or misleading content is not treated "as hostile by default"; (7) confusable by contradictory instructions and criteria; (8) no guaranteed structural invariants (e.g. yes/no probabilities aren't guaranteed to sum to 1); (9) "not trained to generate text," so using it that way is "slow and unreliable."

**Model names and version.** The only model line is Jev; the current release is jev-1.13.0. Two aliases resolve to it today (models.md): `jev-latest` ("the most recent stable, official release. The default in our client SDKs") and `jev-preview` ("the most recent release, whether or not it is an official one" — currently identical because "there is no preview build available right now"). This is corroborated live: the quickstart's example call sends `"model":"jev-latest"` and the response echoes it back (introduction/quickstart.md), and the SDK's compiled-in default model constant is also `jev-latest` (sdk/python/api/constants.md) — so as of today, 2026-09-18, `jev-latest` resolves to `jev-1.13.0`. Input is text-only — string, JSON object, or array of text (concepts/state.md); no images, audio, or video. English is the primary trained language — "other languages, including CJK [Chinese, Japanese, Korean] scripts, are handled but not equally well."

**Speed.** The use-case map advertises "frontier intelligence at real-time speeds (150ms)" (concepts/use-case-map.md); independent cookbook benchmarks measured 111-114 millisecond single-call latency (cookbooks/consistency_noul_cookbook.md; cookbooks/consistency_choice_cookbook.md) and 0.27 seconds for a 13-question call over ~54,000 characters of state (cookbooks/parallel_questions.md). These are the vendor's own demo measurements, not an independent benchmark or a service level agreement.

## 2. The programming model

**Plain-language claim:** every call has three ingredients — state, one or more typed questions, and one typed answer per question in the response — and there are only three question shapes.

**State** (concepts/state.md) is a string, a JSON object with named fields, or an array of text values. Objects are recommended "for most requests to maintain clarity about relationships and field meanings." The core rule from the building guide: "separate content from questions" — facts go in state, judgments go in the question (concepts/how-to-build-with-system-one.md). Nested fields are referenced in question text with backtick-quoted paths, e.g. `` `support.tickets[0].message` ``.

**Questions** (primitives.md) need an ID (your key, never sent to the model), a `type`, `instructions` (the judgment, as string/object/array), and — depending on type — `criteria`. Comparison, in the docs' own words:

| Primitive | Answers | Returns | Distinguishing line |
| --- | --- | --- | --- |
| Choice | one of a fixed, unordered set | `choice`, `probabilities`, `confidence` | "one of a known set of options with no order between them" |
| Score | a position on an ordered, described spectrum | `score`, `legend`, `probabilities`, `confidence` | a judgment "on a spectrum" where "each point has defined meaning" |
| Noul | a yes/no probability | `noul` (0-1), no confidence field | "the probability itself is the useful signal" |

**Choice**, exactly: `criteria` is a map of option name to description, e.g. `{"billing": "Payment or subscription issues"}`. The response has `choice` (top option), `probabilities` (full distribution over every option, sums to 1), and `confidence` — defined as "a number from 0 to 1 computed from how probabilities is spread. A flat shape... means low confidence. A single peak on one option means high confidence" (primitives/choice.md).

**Score**, exactly: `criteria` is an ordered array of 2-10 level descriptions, indexed from 0. The returned `score` is not a winning index — it is "a probability-weighted mean of the level numbers" (each level number times its probability, summed), so a 0/1/2 rubric can return a fractional value like 1.3. The response also echoes a `legend` (level number to description) and a `probabilities` map keyed by level number, plus `confidence` with the same distribution-spread meaning as Choice (primitives/score.md).

**Noul**, exactly, because it is the primitive most likely to be misread: `criteria` is optional (true/false descriptions). The response has one field, `noul`, "the probability that the answer is yes." There is no confidence field — "the probability value itself conveys confidence" (primitives/noul.md). A mid-range value is not a moderate answer: "a value near 0.5 gives yes and no similar probability," not "somewhat"; the docs redirect that use case to Score. The building guide adds: use one Noul per label when several labels may independently apply, rather than forcing them into one Choice.

**Advanced/structured shapes** (primitives/advanced.md): `instructions` and `criteria` all accept an `EntryType` — string, JSON object, array, or null. Structured instructions suit multi-part questions (a field object with question/focus/compare keys) or handing Jev a taxonomy/schema to traverse directly, including nested taxonomies. Structured Choice options can carry a "what," a "not_for," and "examples" for boundary clarity (also urged on concepts/how-to-build-with-system-one.md). Structured Score levels can be objects with a summary and signals list; the response's `legend` preserves whatever structure was sent.

## 3. Contract facts

**Plain-language claim:** one HTTP endpoint, one request/response shape shared by all three question types, and two official SDKs (Python, JavaScript/TypeScript) that are both under two weeks old and both still shipping breaking changes.

**Endpoint and auth** (api.md; introduction/quickstart.md): base URL `https://api.typesafe.ai`, endpoint `POST /v1/systemone`, header `Authorization: Bearer <API_KEY>`, `Content-Type: application/json`. Request body: `state`, `model` (e.g. `"jev-latest"`), `questions` (map of ID to question object). Response body: `model`, `answers` (map of ID to typed answer), `usage` (`input_tokens`, `output_tokens`).

**Batching:** no documented maximum question count per request. The design intent is many at once: "evaluated in parallel, so adding more questions to a call typically doesn't add any latency" (patterns/fan-out.md; introduction.md). Demonstrated batches run 13-14 questions (cookbooks/parallel_questions.md; cookbooks/consistency_noul_cookbook.md); neither is described as a ceiling. Each request carries exactly one `state`; the docs do not mention multiple states per call.

**Size limits:** jev-1.13.0 accepts "64k tokens per request; 32k tokens for `state` plus the longest question" (models.md; a token is the model's sub-word text unit).

**Rate limits and pricing** (models.md): "250,000 tokens per second / 1,200 requests per minute," explicitly provisional — "Rate limits are adjusting dynamically" under demand. Pricing is $0.042 per million input tokens (equivalently $42 per billion), output tokens free ($0.00 per million) — corroborated independently by two cookbooks' own cost tables (cookbooks/parallel_questions.md; cookbooks/sde_cascade.md). No separate free tier is mentioned.

**Errors** (sdk/python/api/exceptions.md): base `TypeSafeError` covers all SDK failures. HTTP failures raise `TypeSafeAPIError` subclasses by status: 400 bad request, 401 authentication failed, 403 permission denied, 404 not found, 422 server-side validation failed, 429 rate limit exceeded, 5xx internal server error. Transport failures raise `TypeSafeAPIConnectionError` (no HTTP response) or `TypeSafeAPITimeoutError`; a malformed-but-200 body raises `TypeSafeAPIResponseValidationError`. The raw API page additionally documents HTTP 529, "service temporarily overloaded," advising exponential backoff rather than immediate retry (api.md) — no distinct exception is named for it, so it likely falls under the generic server-error bucket, but the docs do not say so. Every error carries a request ID from the `x-typesafe-request-id` header.

**Python SDK** (sdk/python.md): package `typesafe-sdk`, `pip install typesafe-sdk` or `uv add typesafe-sdk`. Both `TypeSafeClient` (sync) and `AsyncTypeSafeClient` share a constructor (`api_key`, `model`, `retry`, `timeout`, `headers`, `transport` or `http_client`, `base_url`) and a `system_one(state, questions, ...)` method returning `SystemOneResponse` (sdk/python/api/clients/sync.md; .../async.md). Minimal example, assembled from the docs:

```python
from typesafe_sdk import Choice, Noul, TypeSafeClient

with TypeSafeClient() as client:
    result = client.system_one(
        state="I was charged twice. Please help.",
        questions={
            "billing": Noul(instructions="Is this about billing?"),
            "tone": Choice(instructions="What is the tone?",
                            criteria={"calm": None, "angry": None}),
        },
    )
    print(result.answers["billing"].noul, result.answers["tone"].choice)
```

Retries use a `RetryPolicy` dataclass: 2 retries by default, exponential backoff from 0.5s up to a 5s cap with 25% jitter, retrying HTTP 408/429/500-599 plus connection/timeout errors, honoring `Retry-After`, within a 30-second total budget by default (sdk/python/api/retries.md). The changelog shows rapid, breaking iteration: v0.5.7 "initial public release" 2026-09-14; v0.6.0 (2026-09-15) breaking-changed `Score.criteria` from an integer-keyed dict to an ordered sequence; v0.7.0, dated today (2026-09-18), swapped internal serialization from msgspec to pydantic and added a `response_model` parameter for typed Pydantic responses (sdk/python/changelog.md). No streaming or batch-submission endpoint is documented; "async" here means non-blocking I/O, not a separate batch API.

**JavaScript/TypeScript SDK** (sdk/javascript.md): package `@typesafe-ai/sdk`, `npm install @typesafe-ai/sdk`, requires Node.js 20+. Minimal example:

```ts
import { choice, noul, TypeSafeClient } from "@typesafe-ai/sdk";

const client = new TypeSafeClient();
const { answers } = await client.systemOne({
  state: "I was charged twice. Please help.",
  questions: { billing: noul("Is this about billing?") },
});
console.log(answers.billing.noul);
```

It mirrors the Python SDK conceptually with camelCase naming (`systemOne`) and plain helper functions (`choice()`, `noul()`, `score()`) instead of question classes; ships ESM, CommonJS, and TypeScript declarations. Error classes parallel Python's by name — `RateLimitError` extends a common `APIError` base with `status`, `headers`, `body`, `requestId`, `retryAfterMs` (sdk/javascript/api/classes/RateLimitError.md). Changelog: v0.5.7 "initial public release" 2026-09-11; v0.6.0 (2026-09-15) carried the same breaking `Score.criteria` change as Python (sdk/javascript/changelog.md). The full reference (sdk/javascript/api.md) is a TypeDoc-generated set of dozens of individual class/interface/type/function pages; this brief samples representative ones (`TypeSafeClient`, `choice()`, `RateLimitError`, `ChoiceQuestion`) rather than enumerating all of them, since the shapes match the Python SDK's documented fields one for one.

**No MCP (Model Context Protocol) server and no command-line interface tool** appear anywhere in the docs — confirmed explicitly absent by the agent-skill page itself: "No MCP mentions appear in the provided documentation" (agent-skill.md). What TypeSafe does ship is an "Agent Skill": an installable Claude Code plugin / generic agent-skill bundle (`claude plugin marketplace add typesafe-ai/skills` then `claude plugin install typesafe@typesafe-ai`, or `npx skills add typesafe-ai/skills --skill typesafe-ai` for other agent frameworks) that hands a coding agent the docs, patterns, and cookbook index so the agent can design integrations itself (agent-skill.md).

**Legal/data handling** (legal.md): "our commitment not to train models on user data," and "zero data retention (ZDR) for enterprise customers" on request to privacy@typesafe.ai. No pricing, SLA, or compliance-certification detail on the legal overview itself — only pointers to a Data Processing Agreement, a Master Customer Agreement, and a Privacy Policy.

**Migration history** (migrating-to-v1.md): the one documented prior breaking revision moved `/preview/evaluation` to the current `/v1/systemone`, renaming `prompts`→`questions`, `document`→`state`, `responses`→`answers`, `probability`→`noul`, `chosen`→`choice`, `expectation`→`score`; restructured Choice's `probabilities` from an array of objects to a plain map; and changed how `confidence` is computed such that "the value will differ from preview even for an identical evaluation." The Python package was renamed `typesafe-client`→`typesafe-sdk`, method `evaluate()`→`system_one()`.

## 4. Pattern and cookbook catalog

**Plain-language claim:** four short "patterns" and eighteen worked "cookbooks" nearly all reduce to one move — replace a broad, generative LLM call with several narrow, typed TypeSafe questions plus code that composes the answers.

**Patterns** (patterns.md):

| Name | What it does | Primitives | When to use | Notable trick |
| --- | --- | --- | --- | --- |
| Speculative fan-out (patterns/fan-out.md) | Sends every plausible question up front, including ones that turn out irrelevant, avoiding a follow-up round trip | any | Branching logic that would otherwise need ask-then-ask-again | "adding more questions to a call typically doesn't add any latency" |
| Confidence-gated routing (patterns/confidence-routing.md) | Uses the confidence number, not just the answer, to decide act/confirm/escalate | Choice (shown) | Any automated action with real consequences | Per-action thresholds: 0.6 floor to act at all, >0.85 to auto-approve a transfer |
| Composite scoring (patterns/composite-scoring.md) | Scores several dimensions independently, combines with code-chosen weights | Score | Multi-axis ranking (e.g. resume screening) | Re-weighting for a new reviewer persona needs no new inference, only new arithmetic |
| Intent routing (patterns/intent-routing.md) | Classifies intent, routes to deterministic code, a specialist model, or a human | Choice + Score | Customer-service-style dispatch | Combines a confidence floor with a separate complexity score before treating a "confident" complaint as auto-handleable |

**Cookbooks** (all under cookbooks/):

| Name | What it does | Primitives | When to use | Notable trick |
| --- | --- | --- | --- | --- |
| Self-consistency, Nouls (consistency_noul_cookbook.md) | Measures probability wobble across repeated identical calls, insurance-claim example | Noul | Yes/no decisions near a risk-relevant threshold | Std. dev. 0.0102 vs. larger LLM swings at temperature 0; buckets 0.30-0.70 as "uncertain" |
| Self-consistency, Choices (consistency_choice_cookbook.md) | Same idea for Choice-based moderation routing | Choice | Moderation/routing needing stability across repeats | Agreement 90.8% raw, 99.2% once sub-0.60 answers are marked "uncertain" |
| Parallel questions (parallel_questions.md) | Times one 13-question batched call vs. 13 separate calls, same ~54k-char document | mixed | Justifying batched-request architecture | "12.2x cheaper, 10.0x faster" ($0.000497 vs. $0.006090) |
| Re-ranking (rerank_typesafe.md) | Re-scores a BM25 keyword shortlist of legal passages one at a time | Noul | Search/retrieval where keyword search under-performs | Top-1 accuracy 5%→18%, top-10 38%→62%, $0.0645 / 1,200 calls |
| Line-by-line search (semantic_find.md) | Finds which lines answer a plain-language question, detects when none do | Choice + Noul | Evidence location plus explicit "not answered here" | One request scores 218 candidate lines; "exists" separates answered (≥0.9) from unanswered (≤0.05) |
| Structure recovery / autoformat (autoformat.md) | Rebuilds Markdown structure from hard-wrapped plain text in two passes | Noul (stitching) + Choice (block type) | Recovering lost formatting without risking content changes | "the model never generates text... every character of the output comes from the input"; one memo cost $0.0015, 0.8s |
| Classifying RAG passages (classifying_rag_passages.md) | Screens retrieved passages for relevance, evidential value, premise conflict, injection risk | Noul x4 | Retrieval-augmented generation over untrusted documents | Caught a passage scoring 0.99 injection risk despite ranking first by similarity |
| Double-checking citations (citation_check.md) | Verifies cited quotes are real (string match) and supportive (Choice) | String match + Choice | Any pipeline where an LLM attaches citations | Caught one fabricated quote and one direct contradiction at 0.99 confidence |
| Function calling (function_calling.md) | Converts natural-language trading commands into one function name plus typed, enum-constrained arguments | Choice per slot | Natural language into calls against a fixed function/tool set | 14/14 test commands resolved, e.g. `rolling_correlation(symbol='NVDA', ...)` at 0.91 confidence |
| Date extraction (date_extraction_cookbook.md) | Extracts absolute/relative dates without model calendar math | Choice x7 (one per component) | Date/deadline extraction, given Jev's documented date-math weakness | Code assembles the final date; a nonexistent kickoff date correctly scored 0.46, flagged for review |
| Pre-parsed value extraction (pre_parsed_value_extraction_cookbook.md) | Regex finds candidates; TypeSafe picks the right one instead of generating a value | Choice | Extracting values while guaranteeing no hallucinated/transposed digits | "It cannot invent a value or transpose a digit" — only selects among regex-found spans |
| SDE cascade (sde_cascade.md) | Cheap model extracts, TypeSafe verifies per field, expensive reasoning model only redoes flagged records | Noul per field | Near-top-model extraction quality without top-model cost on every record | Verifier priced $0.042/$0.00 per million tokens; cookbook labels it "jev-1.12," one minor version behind current |
| Skill suggestion (skill_suggestion.md) | Ranks an agent's whole skill roster cheaply, deep-checks only the top 3, suggests at most one | Noul (gate + shortlist) | Agent frameworks with large tool/skill rosters | On 488 requests: wrong loads 16.8%→7.3%, needless loads 9.8%→4.0% |
| Entity alignment (entity_alignment.md) | Decides whether two records describe the same real-world entity, with a "send to curator" middle outcome | Score (3 levels) + Noul x3 | Deduplication where a wrong auto-merge is costly | 450 pairs: 8.9% auto-merge, 11.1% curator queue, 80.0% left unlinked |
| Hierarchical classification (hierarchical_classification.md) | Walks a taxonomy root-to-leaf via greedy or beam search | Choice per branch | Deep taxonomies (patents, catalogs, medical codes, codebases) | Beam search (K=3) got 4/4 test cases right; greedy got 2/4 |
| Classification using confidence (classification_using_confidence.md) | Classifies SEC filings into 75 industry groups, falls back to a broader division when unsure | Choice (single, 75-way) | Large flat classification with genuinely ambiguous inputs | Confident (≥0.9) answers hit 90% accuracy; forcing low-confidence answers to the specific level dropped to 40% vs. 70% at the broader level |
| Guardrails for LLMs (llm_guardrails.md) | Screens input and output for jailbreaks, harm requests, medical advice, self-harm signals, routes by policy | Noul x4 + Score | Input/output moderation with tunable, auditable thresholds | Identical probabilities produce different pass/block outcomes under a "strict" vs. "permissive" named policy |
| Autoresearch feature discovery (autoresearch_feature_discovery.md) | Turns free-text wine-tasting notes into numeric features for a downstream CatBoost model, LLM proposes new questions each round from model error | Score + Noul | Feature engineering from unstructured text for classical ML | RMSE (root-mean-square error) fell from 3.088 (mean baseline) to 1.772 after 5 rounds / 38 questions |

## 5. Question-design and threshold guidance

**Plain-language claim:** the single most repeated rule is to keep questions narrow and keep control flow in application code; thresholds are explicitly domain-specific and must be tuned on your own data, never copied from a demo.

Decomposition is called "probably the most important concept in this guide," because "broad questions hide several judgments behind one answer" (concepts/how-to-build-with-system-one.md). Concretely: ask one atomic, well-scoped judgment per question (concepts/system-one.md; concepts/how-to-build-with-system-one.md); give each question only the state it needs, since irrelevant content measurably lowers accuracy on large states (model-jaggedness/jev-1.13.md); prefer structured, named-field instructions over dense prose when several concerns are folded together (primitives/advanced.md); write contrastive criteria stating what does and doesn't belong, with examples, rather than a bare label (primitives/choice.md); reference nested state fields with backtick-quoted paths instead of re-describing them; and consider whether Choice needs an "other"/"none of the above" option, or whether a value-selection question needs a separate presence check first, since "the model cannot choose an omitted value" (concepts/how-to-build-with-system-one.md).

On thresholds: "the correct threshold values depend on your domain and the performance of the model for your use case," and "different actions within the same system should be gated at different levels depending on the consequences of getting it wrong" (confidence.md). The recommended mental model is three-tier — high confidence acts automatically, medium confidence proceeds with caution (e.g. asks the user to confirm), low confidence routes to a human or fallback (confidence.md) — demonstrated concretely by confidence-gated routing's differing 0.6-floor and >0.85-auto-approve thresholds within one system (patterns/confidence-routing.md). The practical method for finding the right number: "plot confidence against accuracy on your data" (concepts/how-to-build-with-system-one.md), not guess from a demo.

There is no dedicated "testing" or "evaluation" page in the index, but validating "in the target domain" rather than assuming transfer is a repeated theme (concepts/how-to-build-with-system-one.md), and every cookbook's numbers come from small samples (450 pairs, 488 requests, 60 filings, 100 prompts, 10 sample prompts) that read as worked examples, not guarantees. Several cookbooks build their own lightweight evaluation harness inline: repeated sampling cached to a JSON file "for reproducibility without re-spending" (cookbooks/consistency_noul_cookbook.md), or k-fold cross-validation to judge whether a new round of proposed questions actually helped (cookbooks/autoresearch_feature_discovery.md).

## 6. Use inside agents and LLM workflows

**Plain-language claim:** the docs consistently position TypeSafe as the fast, cheap layer around a slower large language model or a human — deciding when to escalate, what to verify, and which speculative branch to pursue — not as a replacement for either. The cookbooks below are already fully described in the section 4 table; this section adds only the agent-specific framing.

**Escalation and cascades.** SDE cascade and guardrails for LLMs (cookbooks/sde_cascade.md; cookbooks/llm_guardrails.md) both put TypeSafe between an application and a large language model: the cascade escalates only the fraction of records its verifier flags, and guardrails screens every message before or after the model call rather than trusting that model's own system prompt, which "is exactly the place a jailbreak talks its way past."

**Routing agents and tool/skill selection.** Skill suggestion (cookbooks/skill_suggestion.md) targets an agent choosing among a large tool/skill roster, where truncating every description into the system prompt "increases costs, degrades skill selection performance, and induces context rot for the rest of the session" — "context rot" is the docs' own term for accuracy degrading as irrelevant context accumulates, also used on introduction.md. Function calling (cookbooks/function_calling.md) addresses the sibling problem: turning an instruction into one function call with typed, enum-constrained arguments so "nothing has to map a label back to an argument afterwards."

**Verification of LLM output.** Double-checking citations and classifying RAG passages (cookbooks/citation_check.md; cookbooks/classifying_rag_passages.md) both sit between a retrieval step and a generation step, catching fabricated citations, contradicted claims, and prompt-injection attempts before they reach a reader or a generating model.

**Speculative fan-out in an interactive agent.** The smart-home demo evaluates every user utterance against a long list of questions up front, "including many that will end up irrelevant for most requests," because asking sequentially "ends up being much slower and more expensive" (demos/smart-home.md). The same demo shows TypeSafe deciding when to defer to a large language model at all: a Noul question detects multi-action requests (an LLM then splits them into atomic commands), and a separate branch detects pure conversation and hands that to an LLM for a freeform reply — TypeSafe is the router, not the responder.

## 7. Gaps and cautions

**Plain-language claim:** the docs are candid about the model's weaknesses but thin on several things a fleet integrator needs — independent benchmarks, a service level agreement, streaming/batch endpoints, and any MCP or CLI tooling — and both SDKs are new enough that their interfaces are still visibly moving.

**Not covered, stated plainly rather than inferred:** no third-party or published benchmark numbers anywhere — the only performance figures are the vendor's own small-sample cookbook demos; no formal service level agreement or uptime commitment (legal.md; api.md); no streaming response mode and no separate batch-submission endpoint — the only lever for many questions at once is one request's `questions` map (api.md; patterns/fan-out.md); no MCP server, confirmed explicitly absent (agent-skill.md); no command-line interface tool, only client SDKs and the agent-skill bundle; no documented maximum questions-per-request or states-per-call (only the 64k-token total budget); no FAQ page and no public benchmark/leaderboard page anywhere in the index.

**Likely to change or already version-dependent:** both SDKs are extremely new — Python's initial public release was 2026-09-14, JavaScript's was 2026-09-11 — and each has already shipped one breaking change (Score criteria moved from an integer-keyed dictionary to a plain ordered list), with Python shipping a second breaking change (its serialization library) on today's date, 2026-09-18 (sdk/python/changelog.md; sdk/javascript/changelog.md). Any integration built now should pin exact SDK versions and expect near-term migration work. The model-jaggedness page is versioned to jev-1.13, matching the current `jev-latest` release, so it is current — but the SDE-cascade cookbook's cost table names its TypeSafe verifier "jev-1.12" (cookbooks/sde_cascade.md), one minor version behind, a small but real sign that cookbook content is written against a point-in-time release and can lag the current one; verify pricing and behavior against models.md rather than a cookbook. Rate limits are self-described as provisional (models.md), so read them from the account dashboard, not this brief. Confidence and calibration are both repeatedly scoped as aggregate, not per-answer, properties — "these rates describe groups of predictions, not a guarantee about any single answer" (introduction/machine-learning-primer.md) — so no threshold from a cookbook or from this brief should be trusted without re-validating it against the target application's own data and consequences, exactly as confidence.md itself insists.
