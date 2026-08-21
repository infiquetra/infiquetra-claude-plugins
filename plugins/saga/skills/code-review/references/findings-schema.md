# Findings Schema

Every review lens returns findings in this schema. It is adopted from CE's findings schema so findings
are **agent-consumable** — `autofix_class` and `owner` are routing metadata a downstream fixer reads.
`/code-review` itself only reports, classifies, and routes; it never applies a fix.

**Formatting contract.** The output below already tables findings (the pipe-delimited interactive table);
that satisfies the shared contract in
`saga/references/formatting-style.md`. When the report carries
any surrounding narrative (the Coverage section, the outcome blockquote), keep it as short (≤3-sentence)
blank-line-separated prose and lead each block with a one-line summary. Do **not** re-table the findings —
the schema and its table are canonical.

## Per-finding fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | yes | Short, specific issue title (<= 10 words). |
| `severity` | yes | `P0` / `P1` / `P2` / `P3`. |
| `dimension_id` | yes | Canonical dimension identifier whose score reflects this finding. |
| `critical` | yes | `FindingEvidence` score-consistency signal described below; this field is not serialized on `ReviewFinding`. |
| `file` | yes | Repo-relative path. |
| `line` | yes | Primary line number (>= 1). |
| `why_it_matters` | yes | The failure mode — what *breaks*, not what is wrong. |
| `autofix_class` | yes | Routing class (below). |
| `owner` | yes | Who owns the next action (below). |
| `requires_verification` | yes | Whether a fix needs targeted tests or a re-review pass. |
| `confidence` | yes | One anchor: `0` / `25` / `50` / `75` / `100`. |
| `evidence` | yes | >= 1 code-grounded item, each citing `file:line` or a snippet. |
| `pre_existing` | yes | True if the issue is in unchanged code this diff did not introduce. |
| `suggested_fix` | optional | Concrete minimal fix (rule below). |

`critical` is a score-consistency assertion, not another Priority or outcome gate. A reviewer sets it
to `true` when an unresolved finding means its mapped dimension cannot honestly be non-applicable or
meet the dimension floor; set it to `false` otherwise. Reconciliation still treats every active,
non-pre-existing, non-advisory P0 as critical, so an omitted or default `false` cannot downgrade that
derived signal. A pre-existing or advisory P0 remains non-critical for scoring and creates no fix request.

The typed result serializes these fields without translating the routing values:

```json
{
  "finding_id": "F-12",
  "lens_id": "correctness",
  "dimension_id": "state-data-invariants",
  "title": "Rollback loses the prior state",
  "severity": "P1",
  "file": "src/state.py",
  "line": 42,
  "why_it_matters": "A failed update leaves the stored state inconsistent.",
  "autofix_class": "gated_auto",
  "owner": "review-fixer",
  "requires_verification": true,
  "confidence": 100,
  "evidence": ["src/state.py:42"],
  "pre_existing": false,
  "suggested_fix": "Restore the previous value in the existing failure branch.",
  "touched_paths": ["src/state.py", "tests/test_state.py"],
  "status": "active"
}
```

## Severity (P0-P3)

- **P0** — Critical breakage, exploitable vulnerability, data loss/corruption. Highest routing urgency.
- **P1** — High-impact defect likely hit in normal usage, breaking a contract. High routing urgency.
- **P2** — Moderate issue with a meaningful downside (edge case, perf regression, maintainability trap).
  Fix if straightforward.
- **P3** — Low-impact, narrow scope, minor improvement. User's discretion.

## Confidence — 5 anchors with behavioral criteria

Use exactly one of these — floats are invalid (the model cannot calibrate finer; discrete anchors prevent
false-precision gaming):

- **0** — Not confident. A false positive that does not survive light scrutiny, OR a pre-existing issue
  this PR did not introduce. Do not report.
- **25** — Somewhat confident. Might be real, might be a false positive; could not verify from the diff and
  surrounding code alone. Do not report.
- **50** — Moderately confident. Verified real but a nitpick, narrow edge case, or minimal impact. Style
  preferences land here. Report only when P0 (or when synthesis routes to advisory).
- **75** — Highly confident. Double-checked: it will affect users, downstream callers, or runtime behavior
  in normal usage. Report.
- **100** — Absolutely certain. Verifiable from the code alone — compile error, type mismatch, definitive
  logic bug, or a quotable project-standards violation. Report.

**Report admission:** below anchor 75, do not report — **except** a P0 at anchor 50+ (a
critical-but-uncertain issue must not be silently dropped). This admission rule and the validator 15-cap
control evidence volume. Confidence and Priority are metadata; neither is a review-acceptance gate.

## autofix_class — routing metadata (4 values)

- **safe_auto** — Local, deterministic fix suitable for an in-skill fixer: one-sentence fix, no "depends on"
  clauses, no change to function signature / public API / error contract / security posture / permission
  model. Examples: extract a duplicated helper, add a missing nil check, fix an off-by-one, add a missing
  test, remove dead code. Bias toward `safe_auto` when the rubric permits.
- **gated_auto** — A concrete fix exists but it changes a contract, permission, or behavior, or its
  placement needs a design conversation. Needs approval before apply. Examples: add auth to an unprotected
  endpoint, change an API response shape.
- **manual** — Actionable work that needs a design decision or cross-cutting change. Usually paired with a
  `suggested_fix` the user can confirm. Examples: redesign a data model, add a pagination strategy.
- **advisory** — Report-only, no code change. Examples: residual-risk notes, deployment considerations, a
  design asymmetry the PR improves but does not fully resolve.

## owner — who acts next (4 values)

- **review-fixer** — the in-skill fixer can own this when policy allows.
- **downstream-resolver** — turn it into residual work for later resolution.
- **human** — a person must make a judgment call before code changes continue.
- **release** — operational/rollout follow-up; do not auto-convert into code-fix work.

`review_consensus.consolidate_fix_requests` groups active, non-pre-existing, non-advisory findings only
when they share an owner, an `autofix_class`, and overlapping touched paths. Disjoint path sets stay
separate so Orchestrate can route them to different Work workers. The serialized request is:

```json
{
  "fix_id": "fix-<stable digest>",
  "finding_ids": ["F-12"],
  "autofix_class": "gated_auto",
  "owner": "review-fixer",
  "touched_paths": ["src/state.py", "tests/test_state.py"],
  "summary": "Rollback loses the prior state",
  "requires_verification": true
}
```

## suggested_fix rule

Propose a concrete minimal fix whenever any defensible code change is reachable from review context
(parallel patterns, framework conventions, the cited code itself). Imperfect information is not grounds for
omission: propose the most defensible default, **name the assumption you made**, and let the user override.
"I need <input> to commit" is a **soft punt** — the right question is "what change would I propose if I had
to choose now?" Omit only when there is genuinely no code-level change (the finding is a question, or the
resolution is purely organizational). A soft punt is the failure mode this field exists to prevent.

## pre_existing honesty

Set `pre_existing: true` when the issue lives in unchanged code the diff merely touched. Pre-existing
findings are reported in a separate informational table — do not blame this diff for old code, and do not
gate the PR on issues it did not introduce.

## evidence

At least one item, each grounded in the code: a snippet, a `file:line` reference, or a precise pattern
description. A finding without evidence is not a finding.

## Merge, sort, and stable numbering

1. **Fingerprint dedup** — fingerprint is `path:line:category`. When multiple lenses flag the same issue,
   merge into one finding and record cross-reviewer agreement in the Reviewer column.
2. **Conservative route on disagreement** — keep the most conservative `autofix_class`
   (`safe_auto -> gated_auto -> manual`, never the reverse without stronger evidence).
3. **Sort** by severity (P0 first) -> confidence anchor (descending) -> file -> line.
4. **Stable #s** — assign monotonically increasing finding numbers once, across the full set. Reuse the
   same # wherever a finding reappears (residual work, fixer routing). Never restart per section.

## Output and durable-artifact contract

**Interactive output:** lead with P-level findings grouped by severity, each a pipe-delimited table
(`# | File | Issue | Reviewer | Confidence | Route`, where Route is `<autofix_class> -> <owner>`); escape
literal `|` inside cells as `\|`. Then a Coverage section (suppressed count, residual risks, testing gaps)
and a blockquote naming the typed outcome, next action, and fix order.

**Programmatic / report-only output:** canonical `review_result.v1` JSON from
`ReviewResult.to_json()`. A human rendering may follow with findings grouped by `autofix_class`, but it
does not add another decision field. Programmatic mode writes zero files to reviewed code.

The top-level serialized contract is:

```json
{
  "schema": "review_result.v1",
  "collection_operation": {"operation": "collect", "schema": "review_result.v1"},
  "revision_binding": {
    "best_available_revision": "<commit>",
    "lens_revisions": {"correctness": "<commit>"}
  },
  "selected_lenses": ["correctness"],
  "attempted_lenses": ["correctness"],
  "lens_results": [],
  "findings": [],
  "cycle_history": [],
  "failing_lenses": [],
  "fix_requests": [],
  "unresolved_fix_ids": [],
  "best_available_revision": "<commit>",
  "residual_summary": {
    "final_lens_scores": {},
    "unresolved_fix_ids": [],
    "score_regressions": [],
    "review_incomplete_reason": null
  },
  "outcome": "accepted",
  "next_action": "continue",
  "resume_transitions": ["continue"],
  "evidence_ledger": {},
  "external_advisory_reviews": []
}
```

`outcome` is exactly one of `accepted`, `repairs_requested`, `cycle_cap_best_available`, or
`review_incomplete`. It is the sole decision field. Each outcome names exactly one allowed resume
transition; `ReviewResult.require_resume_transition()` rejects any other value. Priority, confidence,
and the external-reviewer seat never change the outcome.

**Durable artifact** — persisted through the evidence ledger (#398, `SKILL.md` §5.3) in **interactive**
mode rather than a bare file write: `evidence_ledger.py write --check-id code-review ...`
content-addresses it under `docs/evidence/<saga-id>/artifacts/`. It carries the reviewed SHA, the complete
typed result, independent-gate state, coverage, and linked issue, plan, and work-session paths. The
ledger's generic command-line `--verdict` field stores the typed `outcome`; no `verdict` key is added to
`review_result.v1`.

## Whole-diff external advisory review

The optional external-reviewer seat reviews the whole revision-bound diff and may introduce findings no
native lens raised. It is cross-vendor, request-bound, externally admitted, and non-scoring. Code Review
adjudicates every returned finding before active survivors join normal deduplication and routing.

The managed-session claim store keeps its existing lifecycle vocabulary for wire compatibility:
`recommended | requested | available | unavailable | declined`, `intent: second-opinion`,
`role_kind: advisory-reviewer`, and `requested_by: human | claude`. Its bounded source records retain
`source_finding_id`, `keep|downgrade|dismiss`, `active|dismissed`, and the cumulative `256 KiB` limit.
These are transport and adjudication fields, not a second schema or an acceptance rule.

```json
{
  "reviewer_id": "external-seat-1",
  "reviewer_vendor": "vendor-b",
  "home_vendor": "vendor-a",
  "request_id": "request-1",
  "request_digest": "<digest>",
  "reviewed_revision": "<commit>",
  "whole_diff": true,
  "request_bound": true,
  "external_only_admitted": true,
  "scoring_authority": false,
  "findings": [],
  "adjudications": [
    {
      "finding_id": "external-F1",
      "decision": "keep",
      "rationale": "The independent evidence is valid.",
      "final_severity": "P1",
      "final_status": "active"
    }
  ]
}
```

`keep` preserves severity and active status. `downgrade` must select a strictly lower active severity.
`dismiss` preserves audit severity and sets `dismissed`. Prose such as `PASS`, shell syntax, or path-like
strings remains opaque evidence: it cannot select a route, execute, or decide the outcome. A pending
runner result is collected with its stored handle and never relaunched; `ran-empty` or `died` maps to
`review_incomplete` without a fabricated score or consumed cycle.
