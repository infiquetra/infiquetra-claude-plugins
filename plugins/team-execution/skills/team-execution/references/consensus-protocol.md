# Consensus Protocol — team-execution

This file defines Team Execution's transport and worker-coordination role during review. Saga Code
Review owns the roster, scoring policy, transition state, and final result. Team Execution loads and
executes that policy; it never recomputes or restates it.

Read `reviewer-registry.md` for roster-driven selection and `review-criteria.md` for the canonical
policy pointer before starting this protocol.

---

## Resolve the Canonical Review Runtime

Before selecting or spawning a reviewer, run the packaged settlement preflight:

```bash
TEAM_SETTLEMENT="${CLAUDE_PLUGIN_ROOT:-plugins/team-execution}/skills/team-execution/scripts/dispatch_settlement_adapter.py"
SAGA_PREFLIGHT_JSON="$(python3 "$TEAM_SETTLEMENT" preflight)"
```

The returned JSON names the resolved Saga root. Load these files below that root:

- `references/lens-roster.json` — the only roster and policy declaration.
- `scripts/review_consensus.py` — the shared scorer and review transition engine.

Fail before the first reviewer call when either file is absent or has an unknown schema. Do not use
the quarantined `scripts/consensus_advisory.py` as a fallback.

---

## Lens Selection and Agent Residency

Run the selection procedure in `reviewer-registry.md` against the loaded roster. The selected lens
identifier is the dispatch and settlement unit identifier. Its
`implementations.team_execution.agent` value chooses the resident agent that performs the review.

Several lenses may map to the same agent. Spawn one named resident for that agent and re-engage it
for each mapped lens, while keeping separate structured results and evidence for each lens. Never
collapse lens dimensions into an agent-wide score.

For every conditional lens, retain the required one-line selection reason with the review record.
Keyword matching alone is not selection evidence.

---

## Review Execution

For the initial pass, give each mapped agent:

- the selected lens identifier;
- that lens's canonical dimensions and anchors from the roster;
- the plan and intended outcome;
- the complete reviewed diff, using `artifact-pointers.md` when pointerization is required;
- the revision being reviewed; and
- the required structured-result fields.

Below the SKILL.md Step B1 threshold, inline the reviewed diff. Above that threshold, pass the
producer-generated pointer in place of the diff and require the receiver to follow
`artifact-pointers.md`:

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch>","hash":"<snapshot-tree-oid>","epoch":"<epoch>","deref":"git diff <base-tree> <snapshot-tree>","base":"<base-tree-oid>"}
```

The returned result must identify the lens settlement unit, the mapped agent, the reviewed revision,
every applicable dimension score, every non-applicable dimension cause, the reported overall, and
the findings. Findings retain priority and confidence as metadata.

Use the shared `static-non-applicable` cause vocabulary from the
[architecture reviewer prompt](../../../agents/architecture-reviewer.md) when a roster precondition is
absent. Such an exclusion is never a failure signal and does not trigger the re-review path.
It is never re-run on that basis; the remaining applicable dimensions still go to the shared scorer.
The former `execution-spec.md` pointer was stale: that file does not define this vocabulary, so the
linked reviewer prompt above is the authoritative source.

Before any reviewer call, create one settlement manifest containing every selected lens identifier.
Append the stable spawn attempt immediately before that reviewer's Agent call, using the selected
lens identifier as the settlement unit:

```text
for each selected lens, append its spawn immediately before that
        reviewer's Agent call
```

```bash
python3 "$TEAM_SETTLEMENT" manifest --kind reviewer --repo-root "$REPO_ROOT" \
  --subplot-id "$SAGA_ID" --dispatch-id "$DISPATCH_ID" \
  --roster-json "$SELECTED_LENS_IDS_JSON" --at "$NOW"
python3 "$TEAM_SETTLEMENT" saga -- --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" spawn \
  --dispatch-id "$DISPATCH_ID" --unit-id "$LENS_ID" --attempt "$ATTEMPT" \
  --idempotency-key "team-execution:reviewer:$LENS_ID" --at "$NOW"
```

Store each returned result as JSON, with its `reviewer` field equal to the lens settlement unit, and
settle it through the existing adapter:

```bash
python3 "$TEAM_SETTLEMENT" settle --kind reviewer --repo-root "$REPO_ROOT" \
  --subplot-id "$SAGA_ID" --dispatch-id "$DISPATCH_ID" \
  --unit-id "$LENS_ID" --attempt "$ATTEMPT" --at "$NOW" \
  --source-json ".claude/team-execution/reviews/$LENS_ID.json" \
  --receipt-path ".claude/team-execution/settlement/$DISPATCH_ID-$LENS_ID.json"
```

The settlement adapter remains evidence-based. It validates identity, a bounded reported score,
non-empty dimension scores, and a findings list before materializing `dispatch.artifact.v1`.
Returned success prose, an artifact pointer presented as the result, or missing structured evidence
settles as `silent-no-op`; it never becomes a review score.

Run the casualty report before scoring. A casualty halt remains an independent operational gate.
Claim retry-eligible units through Saga's derived dead-letter view at the next review boundary.

---

## Invoke the Shared Scorer

Load the resolved `review_consensus.py` module and call its public U5 API. For every settled lens
result:

1. Construct `FindingEvidence` values from the recorded findings.
2. Call `score_lens_review` with the lens identifier, applicable dimension map,
   non-applicable-dimension causes, reported overall, and findings.
3. Collect the returned `LensScore` without replacing its derived fields with reviewer prose.
4. Call `evaluate_review_readiness` with all selected lens scores and the independently authoritative
   gates that apply.

The scorer loads the policy from the roster. Team Execution must not calculate an overall, compare a
score to a local cutoff, trust a reviewer verdict, or use finding priority or confidence as another
acceptance gate. A contradictory reported overall or finding-to-dimension record is invalid evidence,
not a result to repair locally.

Scanner, test, deployment, built-versus-planned, casualty, and operational-safety gates remain
separate inputs. Passing review does not bypass them, and their status never changes a lens score.

---

## Repair and Re-engagement

When the shared result requests repairs:

1. Consolidate fix requests by touched path and section.
2. Merge duplicates by the canonical finding fingerprint while preserving cross-reviewer agreement.
3. Route each structured request to the responsible worker. Finding priority may order this work but
   cannot change review acceptance.
4. After repairs land, re-engage only the resident agents for the failing lens identifiers. Send the
   delta since each lens's reviewed revision instead of spawning a fresh agent.
5. Leave accepted lenses with the revision they actually reviewed; the Code Review transition engine
   owns their later delta-check.

Do not pause or terminate review solely because a dimension crosses a reviewer-local severity band.
Urgent evidence is routed first, while the canonical scorer and the independent safety gates retain
their separate authority.

**Cycle-cap termination:** when the transition engine returns `cycle_cap_best_available`, stop review
attempts, proceed with its named best-available revision, and report every residual score and fix.

Delivery that remains missing after bounded retry yields the transition engine's incomplete-review
outcome without fabricating evidence or consuming a scoring transition.

---

## External Advisory Seat (Non-Scoring)

Read the external seat's defaults from the roster. The seat reviews the whole diff and may contribute
new findings to Code Review adjudication, but its opinion is never passed to `score_lens_review` or
`evaluate_review_readiness` as a scoring lens.

When present, display `External Advisory Seat: report-only` and attach a key/fingerprint based
convergence report with these buckets:

- `converged`
- `Claude-only`
- `external-only`
- `conflicting`

When absent, halted, or unavailable, record that state and continue with the selected scoring lenses.
Absence is not a panel failure. The quarantined legacy helper may still characterize convergence
rendering in tests, but it is not a production consensus path.

---

## Result Display

After each scoring transition, display the scorer's derived values and evidence without creating a
second verdict:

```text
Review transition: <outcome>
Revision: <reviewed revision>
Lens: <lens identifier>
Mapped agent: <Team Execution agent>
Derived overall: <value from LensScore>
Failing dimensions: <identifiers from LensScore>
Fix requests: <structured identifiers>
Independent gates: <unchanged gate results>
```

The typed Code Review outcome is the decision field. Reviewer prose is supporting evidence only.

---

## Context Templates

Initial review message:

````text
Review the implementation for lens <lens-id> at revision <revision>.

Use only the dimensions and anchors supplied from the canonical Saga roster. Return the structured
dimension evidence and findings requested by the Team Execution settlement contract. Do not decide
whether the overall review proceeds; Saga's scorer owns that decision.

Plan: <summary and intended outcome>
Changes: <inline diff below the SKILL.md Step B1 threshold, otherwise this artifact pointer>

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch>","hash":"<snapshot-tree-oid>","epoch":"<epoch>","deref":"git diff <base-tree> <snapshot-tree>","base":"<base-tree-oid>"}
```
````

Re-engagement message:

````text
Re-evaluate lens <lens-id> at revision <revision> after the requested repairs.

Review this delta against your prior revision and return a new structured lens result. Preserve
unresolved finding identifiers and record the disposition of resolved requests.

Implemented fixes: <summary>

## Changes Made (Delta Only)
Below the SKILL.md Step B1 threshold, inline only the delta since the prior review. Above the
threshold, pass an UPDATED `artifact-pointer` block with its epoch incremented from the prior pass.

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch+1>","hash":"<snapshot-tree-oid>","epoch":"<epoch+1>","deref":"git diff <base-tree> <snapshot-tree>","base":"<base-tree-oid>"}
```
````

The andon-cord remains available for fabricated evidence, unsafe mutation, or a wrong-direction
build. It is independent of numeric review acceptance and transition termination.
