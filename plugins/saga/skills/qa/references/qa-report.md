# QA Report Shape + Health-Score Model + Ship-Verdict Derivation

The durable QA artifact shape for `/qa`, adapted from gstack's `qa-report-template.md` —
**browser-decoupled** but carrying a **deterministic health-score block**. The score is a faithful PORT
of gstack's Health Score Rubric (deductions verbatim; class weights re-mapped to infiquetra ship-risk —
see "Health-score model" below). It rides alongside the severity-banded ship verdict: the score is one
**signal** (its inputs are LLM-assigned severity counts), the verdict is the **gate decision**. Plus
the ship-verdict derivation and the tier → blocking-threshold table the verdict is computed from.

The artifact lives at `docs/qa/qa-<saga-id-or-issue>-<date>.md` (its own directory — no handoff/sdlc
classifier collision).

---

## Report shape

```markdown
# QA Report: <target>

| Field | Value |
|-------|-------|
| Date | <YYYY-MM-DD> |
| Target | <issue #N / branch / PR / scope> |
| Reviewed revision | <commit SHA or "working tree"> |
| Merge state | pre-merge (PR open) / post-merge (on main) |
| Tier | Quick / Standard / Exhaustive |
| Scope | <risk classes in scope> |
| Saga | <saga-id or "none"> |

## Ship Verdict: <ship | ship-with-deferred | no-ship>

<one-line justification tied to the blocking threshold>

## Health Score: <overall 0-100>  (baseline <prior or n/a>, delta <+/-N or n/a>)

| Risk class (in scope) | Score |
|-----------------------|-------|
| behavior | <0-100> |
| security | <0-100> |
| ... | ... |

<one-line: the score is a deterministic gstack-formula port over LLM-assigned severities — a signal,
not the gate; the verdict above is the decision.>

## Top findings
1. <SEV> [class] <one-line>
2. ...

## Summary by severity
| Severity | Count | Blocks at this tier? |
|----------|-------|----------------------|
| critical | 0 | yes |
| high | 0 | yes |
| medium | 0 | <tier-dependent> |
| low | 0 | no (except Exhaustive) |

## Pass/fail by risk class
| Risk class | Result | Note |
|------------|--------|------|
| behavior | pass/fail | ... |
| security | pass/fail | ... |
| ... | ... | ... |

## Findings

### F1: <short title>
- **Severity:** critical / high / medium / low  (P0-P3 cross-walk in risk-taxonomy.md)
- **Risk class:** behavior / security / infra / API / deployment / data / config / docs / trivial
- **Evidence:** <file:line | check output | log | network response | MCP capture path>
- **Repro:** <minimal steps>
- **Falsifiable prediction:** <only for uncertain-cause failures — "if this is the real cause, then X in
  another path/scenario must also fail." Omit when the cause is obvious.>

## Recommended regression tests
<RECOMMEND tests — name the precondition, action, and assertion. /qa does NOT generate or commit them.>

## Deferred (with repro)
<non-blocking findings carried forward, each with full repro so the routed owner can act>
```

Kept from gstack (re-mapped): the `Health Score` block — but per **infiquetra risk class**, not
gstack's 7 web categories (see "Health-score model" below).

Drop entirely (vs gstack): the "Fixes Applied" / before-after / "fixed M" columns (`/qa` never fixes);
the `~/.gstack/` project-scoped write and `baseline.json` regression daemon (the baseline is read from
the prior report the saga's `qa_paths` points at — see "Baseline-from-prior-report" below).

---

## Health-score model

The 0-100 health score is a deterministic **PORT of gstack's Health Score Rubric**
(`gstack/scripts/resolvers/utility.ts:286-321`). Run it from the per-class severity counts:

```bash
python3 plugins/saga/scripts/qa_health_score.py \
  --findings-json '{"behavior": {"critical": 1}, "api": {}, "security": {"high": 2}}' \
  --baseline-score <prior-overall>
```

`--findings-json` accepts a file path **or** an inline JSON string keyed by in-scope risk class. The
scorer prints `{"per_class": {...}, "overall": N, "in_scope": [...], "baseline": N, "delta": D}`.

**Per-finding deductions (ported verbatim from gstack):** `critical -25`, `high -15`, `medium -8`,
`low -3`. A class score is `max(0, 100 - Σ deductions)` (floored at 0).

**Class weights (a DELIBERATE infiquetra adaptation — NOT gstack's).** gstack weights its web
categories (Console / Functional / Accessibility / …), which do not map onto infiquetra's
serverless / SDK / Ansible / plugin work. We replace them with ship-risk weights, ranked by blast
radius if a finding ships:

| Risk class | Weight |
|------------|--------|
| behavior | 20 |
| security | 20 |
| data | 15 |
| api | 15 |
| deployment | 10 |
| infra | 10 |
| config | 5 |
| docs | 3 |
| trivial | 2 |

**In-scope + re-normalization.** A class present in `--findings-json` is in scope (an empty `{}` map is
a checked-but-clean class and scores 100); an **absent** class is N/A and excluded. The overall is the
weighted average of per-class scores with the weights **re-normalized over only the in-scope classes**:
`overall = round(Σ score[c]·weight[c] / Σ weight[c])` (standard round-half-to-even). Empty input
(`{}` or no in-scope classes) is vacuously healthy → `overall 100`.

**Baseline-from-prior-report.** When the restored saga's most-recent `qa_paths` entry exists, read that
prior report's `## Health Score` overall and pass it as `--baseline-score`; the scorer then emits
`delta = overall - baseline`. No `baseline.json`, no saga baseline field — the baseline comes straight
from the prior report the saga points at. First run for a thread omits `--baseline-score` (`delta` is
null).

**Honest caveat.** The deductions are exact arithmetic, but the severity *counts* are LLM-assigned by
`/qa`, so the score is one **signal**. The severity-banded ship verdict (below) remains the gate
decision.

---

## Ship-verdict derivation

The overall verdict is **derived**, not eyeballed:

- **ship** — no finding blocks at the active tier.
- **ship-with-deferred** — only non-blocking findings remain (recorded in "Deferred (with repro)").
- **no-ship** — at least one finding blocks at the active tier.

A risk class **passes** when it has no blocking finding and **fails** when it has one. The verdict is the
roll-up across classes.

## Tier → blocking-threshold table

| Tier | Blocks the ship verdict | Verification depth |
|---|---|---|
| **Quick** | critical + high | the changed surface only; fastest |
| **Standard** (default) | critical + high + medium | changed surface + adjacent paths |
| **Exhaustive** | all severities (incl. low) | changed surface + a broad sweep |

Severity ↔ P0-P3 cross-walk lives in `references/risk-taxonomy.md` (critical→P0, high→P1, medium→P2,
low→P3).

---

## Runnable anchors

Emit issue progress with the evidence link + the checks run (`--checks-run` is pipe-separated; skip when
there is no issue ref):

```bash
python3 plugins/saga/scripts/issue_progress.py \
  --event qa \
  --issue-ref <owner/repo#N> \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --checks-run "<class:check | class:check>" \
  --evidence-link "docs/qa/<file>.md"
```

On a PASS verdict, advance the saga qa-track — write `qa_paths` and advance `lifecycle_phase` work→qa,
pinning `--phase` to the restored integer phase so `--phase-status complete` does not advertise a phantom
counter advance (reuse the restored `kind`/`id`):

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <restored-id> \
  --lifecycle-phase qa \
  --phase-status complete \
  --phase <restored-phase> \
  --qa-paths docs/qa/<file>.md \
  --checks-run "<class:check | ...>" \
  --next-step "<route to /handoff or /retro>" \
  --summary "<one-line ship verdict>"
```

On a FAIL verdict, **omit** `--lifecycle-phase` (the prior `work` phase carries forward) and still write
`--qa-paths docs/qa/<file>.md` plus the evidence — then route by merge state (pre-merge → `/work`,
post-merge → `/handoff`). Never `git add` a saga tick: saga state is git-ignored and machine-local.
