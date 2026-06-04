# Metric taxonomy

The eight metric classes `/optimize` can drive, and the **hard-vs-judge** model that decides how each one
is measured. Pick the class and the measurement mode at spec time (Phase 1). A metric is either **hard**
(a direct numeric the measurement command emits, compared and gated automatically) or **judge** (semantic
quality that needs an LLM-as-judge against a rubric). Some classes split: the objective part is hard, the
qualitative part is judge.

---

## The eight classes

### 1. perf

- **Example metrics:** request latency (p50 / p95 / p99), build time, throughput (ops/sec, req/sec),
  cold-start time, bundle size, memory high-water mark.
- **Measurement method:** time the operation or read a profiler / benchmark harness; emit the scalar to
  the measurement command's JSON.
- **Hard-vs-judge:** **hard.** A direct number with an obvious better direction.

### 2. cost

- **Example metrics:** dollars per run, compute-seconds, token-dollars per call, storage cost, egress
  cost.
- **Measurement method:** read the bill / pricing model, count tokens × unit price, or sum compute time
  × rate.
- **Hard-vs-judge:** **hard.** A direct number; `minimize`.

### 3. reliability

- **Example metrics:** error rate, retry rate, flake rate, test pass rate, success rate over N runs.
- **Measurement method:** run the suite or the operation repeatedly and count failures. **Use
  repeat-aggregate** — reliability signals are noisy; a single run lies. Aggregate (median/mean) over N
  runs and watch variance.
- **Hard-vs-judge:** **hard** (repeat-aggregate for noise).

### 4. agent-usability — **the infiquetra-native class**

This class is **Jeff's angle and an infiquetra addition** — it is **not** present in the source
`ce-optimize` engine. It measures how cheaply and reliably an **AI agent** consumes an artifact or
completes a workflow.

- **Example metrics:** token count to complete a task; steps-to-success (turns / tool calls to a
  correct result); retry rate for an agent following an artifact or instruction — all **hard**.
  Plan-readability-for-agents (is the doc unambiguous enough that an agent acts on it cold?) — **judge**.
- **Measurement method:** count tokens / tool-calls from a transcript for the hard metrics; score the
  artifact against a clarity rubric for the judge metric.
- **Hard-vs-judge:** **split** — counts are hard; readability is judge.

### 5. security

- **Example metrics:** vulnerability count, scanner finding count, attack-surface size (exposed
  endpoints / privileges), CVE count in dependencies.
- **Measurement method:** run a scanner (`bandit`, dependency audit, SAST) and count findings by
  severity — **hard, via the scanner.**
- **Hard-vs-judge:** **hard.** **Note:** a deep, judgment-heavy security audit (threat modeling,
  exploit-chain reasoning) stays with `/qa` + appsec; `/optimize` drives a **countable** security signal
  (finding count, CVE count) toward a target by experiment.

### 6. quality/accuracy

- **Example metrics:** task success rate, classification accuracy, F1 / precision / recall (**hard**);
  answer quality, result relevance, summarization fidelity, clustering coherence (**judge**).
- **Measurement method:** score against a labeled set for the hard part; sample outputs and judge
  against a rubric for the qualitative part.
- **Hard-vs-judge:** **split** — labeled accuracy is hard; perceived quality is judge. When the target is
  qualitative, **prefer judge** — a hard proxy ("more clusters") can be gamed without improving real
  quality.

### 7. developer-experience

- **Example metrics:** setup / onboarding time, human build-feedback latency (edit-to-result loop),
  command count to get running (**hard**); documentation clarity, error-message helpfulness (**judge**).
- **Measurement method:** time the loop / count the steps for the hard metrics; judge the docs against a
  clarity rubric for the qualitative ones.
- **Hard-vs-judge:** **split** — times and counts are hard; clarity is judge.

### 8. maintainability

- **Example metrics:** cyclomatic complexity, coupling, code churn, test coverage %, duplication.
- **Measurement method:** run static analysis (complexity / coverage / lint tooling) and read the
  scalar — **hard, via static analysis.**
- **Hard-vs-judge:** **hard.**

---

## The hard-vs-judge three-tier model

Every experiment is evaluated through up to three tiers, **cheapest first**:

1. **Degenerate gates (hard, cheap, fast) — run FIRST.** Boolean checks that reject obviously broken
   solutions (e.g. `solo_pct <= 0.95` catches all-singletons, `coverage >= 0.0` catches a crashed run).
   If any gate fails, the experiment is `degenerate` — skip the expensive judge and revert. This is the
   money-saver.
2. **The primary metric — the optimization target.** For a **hard** metric, take the number directly
   from the measurement output. For a **judge** metric, sample outputs (stratified if configured), score
   them against the rubric, and aggregate. This tier is what the loop optimizes.
3. **Diagnostics — logged, not gated.** Distribution stats, counts, timings recorded for understanding
   **why** the primary metric moved. Never block on a diagnostic.

**Cheap gates before expensive judgment** is the cost discipline: a degenerate solution fails a boolean
check before it ever costs a judge call.

---

## Gate operators

A degenerate gate is a metric name + a comparison. Supported operators:

| Operator | Meaning |
|---|---|
| `>=` | at least |
| `<=` | at most |
| `>`  | greater than |
| `<`  | less than |
| `==` | equal to |
| `!=` | not equal to |

Example: `{ name: max_cluster_size, check: "<= 500" }` rejects mega-cluster degenerate solutions.

---

## noise_threshold vs minimum_improvement

Two different "is this real?" guards — do not conflate them:

- **`noise_threshold`** (hard metrics) — run-to-run flakiness. A hard-metric improvement must exceed this
  to count as a real win, not measurement noise. Pairs with repeat-aggregate measurement.
- **`minimum_improvement`** (judge metrics) — sample-composition variance. A judge-score improvement must
  exceed this to be accepted, because the sampled output structure can shift between experiments.

Either way: a change that does not clear its threshold is **reverted**, not kept.

---

## Domain note — no risk-weighted scorer is ported

`/qa` derives a deterministic 0-100 health score via `qa_health_score.py`, a **risk-class-weighted**
scorer over LLM-assigned severity counts. `/optimize` does **not** need it and does **not** port it: its
metrics are **direct numeric measurements compared head-to-head** (latency, cost, finding count, judge
score), so there is nothing to risk-weight — the numbers are measured and compared directly. `/optimize`
keeps zero new Python; the comparison is arithmetic on the measured values, not a scored synthesis.
