# Reviewer Registry — team-execution

Team Execution does not own a reviewer roster. Load the canonical, versioned roster from Saga at
`plugins/saga/references/lens-roster.json` in a source checkout, or `references/lens-roster.json`
under the Saga root returned by `dispatch_settlement_adapter.py preflight` in an installed-plugin
run. Refuse an unknown schema rather than falling back to this document or an agent-directory scan.

The roster is authoritative for lens identifiers, selection classes, judgment guidance,
dimensions, score anchors, acceptance policy, participant defaults, and Team Execution agent
mappings. This file describes only how Team Execution consumes that data.

**Tier note (#362, KTD5/KTD7):** every mapped reviewer agent's frontmatter carries
`role-tier: adversarial-review`, which resolves through `fleet_commons/tier_policy.json` to the
review tier. The frontmatter `model:` literal remains a last-resort fallback; it is not the source
of truth for dispatch tier.

---

## Selection Procedure

1. Load the roster and require `schema == "lens_roster.v1"`.
2. Select every lens whose `trigger.class` is `always-on`.
3. Evaluate every `conditional` lens using the change and repository evidence. Selection requires
   judgment and the recorded one-line reason required by the lens trigger. Keyword matching may
   inform that judgment but never selects a lens by itself.
4. For each selected lens, read `implementations.team_execution.agent` and
   `implementations.team_execution.path`. Refuse a missing mapping, an absent agent file, or an
   agent identifier that does not match the mapped file.
5. Keep one scored result per selected lens. If several lenses map to the same agent, reuse that
   named resident agent while preserving separate lens identifiers, dimension evidence, and
   settlement records.

Removing a lens from the canonical roster therefore removes it from Team Execution selection; no
parallel table here can keep it alive.

---

## Resident Agent Trigger Index

This compatibility index lists shipped reviewer Agent entrypoints for Saga's residency hook. It is
not a lens roster and never selects an agent; selection comes only from the canonical roster's
mapping. An entry may remain available even when no selected lens maps to it in a particular run.

| Agent entrypoint |
| --- |
| `architecture-reviewer` |
| `infra-reviewer` |
| `code-quality-reviewer` |
| `security-reviewer` |
| `testing-reviewer` |
| `devils-advocate-reviewer` |
| `api-reviewer` |
| `privacy-reviewer` |
| `clarity-reviewer` |
| `ai-usefulness-reviewer` |

---

## Work Classification Is Evidence, Not a Trigger Table

Classify the plan as code, documentation/specification, or mixed, and inspect repository signals as
before. Feed that evidence into the conditional-lens judgment. Do not translate classifications or
keywords into a private reviewer list.

Documentation-only work does not automatically skip review. It still selects the always-on lenses
and any conditional lenses justified by the actual change.

---

## External Advisory Seat (Non-Scoring)

Read `participant_defaults.external_advisory_seat` from the roster. The external seat is
report-only and remains outside scoring, the consensus denominator, acceptance rules, and rerun
selection. Its absence or transport failure is recorded without changing the scoring result.

It is excluded from reviewer selection counts. The Claude-only reviewer flow proceeds unchanged
when the seat is absent.

The seat may be dispatched through the chaperone contract in `external-engine-workers.md` with
`role_kind="advisory-reviewer"`. Its findings enter the convergence report and Code Review
adjudication, never the score.

---

## Custom Reviewers

Read `participant_defaults.custom_reviewer` from the roster. A user-requested custom reviewer is
non-scoring unless an explicit policy grants voting authority. Record its requested focus and
advisory evidence without adding it to selected scoring lenses by convention.

When confirming a team, ask only whether the user wants an additional advisory focus. Do not imply
that adding a custom agent changes the canonical acceptance policy.

---

## Triage Escape Hatch

The existing trivial-change offer remains available only when all of these are true:

1. The change affects one configuration file.
2. No security surface is affected.
3. Fewer than three files change.
4. No specification or documentation content changes.

If the operator chooses review, run the canonical selection procedure above. The escape hatch does
not define a reduced roster and cannot promote a custom or advisory reviewer into a scoring seat.

---

## Adding an Implementation

To make a Team Execution agent implement a lens:

1. Create or update the agent file under `plugins/team-execution/agents/`.
2. Update that lens's `implementations.team_execution` mapping in the canonical Saga roster.
3. Extend the roster parity tests and the relevant agent behavior tests.
4. Update the plugin release surfaces required by the repository workflow.

Never add a lens, trigger, dimension, anchor, or acceptance rule to this document.
