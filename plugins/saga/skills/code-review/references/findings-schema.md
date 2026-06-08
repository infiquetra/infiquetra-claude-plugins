# Findings Schema

Every review lens returns findings in this schema. It is adopted from CE's findings schema so findings
are **agent-consumable** — `autofix_class` and `owner` are routing metadata a downstream fixer reads.
`/code-review` itself only reports, classifies, and routes; it never applies a fix.

**Formatting contract.** The output below already tables findings (the pipe-delimited interactive table);
that satisfies the shared contract in
`saga/references/formatting-style.md`. When the report carries
any surrounding narrative (the Coverage section, the verdict blockquote), keep it as short (≤3-sentence)
blank-line-separated prose and lead each block with a one-line summary. Do **not** re-table the findings —
the schema and its table are canonical.

## Per-finding fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | yes | Short, specific issue title (<= 10 words). |
| `severity` | yes | `P0` / `P1` / `P2` / `P3`. |
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

## Severity (P0-P3)

- **P0** — Critical breakage, exploitable vulnerability, data loss/corruption. Must fix before merge.
- **P1** — High-impact defect likely hit in normal usage, breaking a contract. Should fix.
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

**Suppress gate:** below anchor 75, do not report — **except** a P0 at anchor 50+ (a critical-but-uncertain
issue must not be silently dropped). This gate, plus the validator 15-cap, is the cost control — there is
no per-severity validator carve-out.

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
and a blockquote verdict with reasoning and fix order.

**Programmatic / report-only output:** the CE headless envelope — verdict in the header, findings grouped
by `autofix_class` (severity-sorted within each group), an `Artifact:` line, a `[needs-verification]`
marker where `requires_verification` is true, and `Review complete` as the terminal line. ZERO file writes
to reviewed code.

**Durable artifact** (`docs/code-reviews/YYYY-MM-DD-<branch-or-pr>-code-review.md`) carries the **reviewed
SHA** plus the review-result contract: target and reviewed revision; blocked status (blocked when any
P0/P1 remains); finding priorities and statuses; plan-completion results and the scope-check verdict;
coverage stats; and linked issue/plan/work-session paths.
