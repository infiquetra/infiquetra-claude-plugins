# Doc review (delta) - issue #357 plan cc-workflow Claude-native candidate

Verdict: **READY AT OPERATOR GATE** - the focused delta (Codex Verified Workflows ceremony replaced
by a Claude-native cc-workflow ceremony, plus refreshed baseline facts) carries one P3 finding and
nothing higher; every changed claim was verified against live session, repo, and git evidence.
Execution stays blocked until Jeff approves anchor
`453fa2d1df14f149b367e3cd92a603135b7ac2b187faf5dba38e5313e72d5b15`.

## Review-Result Contract

- **Target:** `docs/plans/2026-07-15-issue-357-fleet-shared-liveness-engine-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity`, base `5cc24fcc`
- **Scope:** focused delta review of the replaced Workflow Structure / Workflow Operating Contract
  sections, the refreshed Serialized-baseline and R13 version facts, and the Summary/Verification
  execution-prose; the full plan body was previously reviewed READY with zero P0-P3 findings at
  `docs/reviews/2026-07-15-issue-357-fleet-shared-liveness-engine-plan-doc-review.md`
- **Blocked status:** document not blocked; execution blocked at the operator workflow-approval gate
- **Linked issue:** infiquetra/infiquetra-claude-plugins#357, outcome node `sub-357` of
  `lease-safe-runtime-continuity`
- **Supersedes:** the Codex inline-vehicle candidate (digest `0cda70f6bf10...`), explored and
  discarded 2026-07-18 at operator direction — the outcome completes on Claude mechanisms
- **Override rationale:** none

## Delta Under Review

1. Workflow Structure table replaced: same eight-step topology (implement -> four review lenses +
   two validator lenses -> integrate), now on the cc-workflow backend. Lens rows are `agent()` calls
   in one root-authored Claude Code Workflow script: `agent_type=saga:readonly-verifier`,
   reviewers at `opus`/`high`, validators at `sonnet`/`medium`, `isolation=worktree`,
   `mutation=none`, bounded pool of 3.
2. Operating contract rewritten for Claude runtime: root-owned Git/PR/merge-under-confirmation,
   preserved-bytes replay onto current main, lens charters carried in the plan (no dependency on
   team-execution agent definitions), `/code-review` + `/qa` as the required gates, halt-not-degrade
   when the Workflow tool is absent, change control anchored to the section-bytes SHA-256.
3. Baseline facts refreshed: current main `a1dc0c2a` carries fleet-core 0.12.0 / Saga 0.99.1 /
   team-execution 2.18.0 (the plan's expected 0.13.0/0.100.0 base never materialized); preserved
   implementation base `c9cdc992` is not an ancestor of current main, so `implement` replays the
   diff and corrects R13 increments (-> fleet-core 0.13.0, Saga 0.100.0, team-execution 2.19.0).
4. Codex Verified Workflows record roots retained read-only as audit residue; their custody ceremony
   is superseded by this operator-approved candidate.

## Evidence Checks (all confirmed from current sources)

| claim | evidence | result |
|---|---|---|
| Workflow tool with per-call agentType/model/effort/isolation | session tool contract for `Workflow` `agent()` opts | available; all four opts supported |
| `saga:readonly-verifier` exists and fits | session agent roster + agent definition | present; Bash/Read/Grep/Glob toolset, worktree isolation contract, per-call model/effort override documented |
| preserved base not on current main | `git merge-base --is-ancestor c9cdc992 a1dc0c2a` | not an ancestor — replay required, now stated in-plan |
| actual version baseline | `plugin.json` on main for fleet-core/saga/team-execution | 0.12.0 / 0.99.1 / 2.18.0 — matches revised R13 text |
| preserved implementation intact | `git status` in `issue-357-shared-liveness-engine-replacement-r2` | 30 modified/untracked paths at `c9cdc992`, uncommitted |
| gates match the outcome contract | `outcome-spec.json` sub-357 `evidence.required_checks` | exactly `qa`, `code-review` |
| stale-machinery sweep | grep for Verified Workflow / gpt-5.6 / `vehicle=auto` / team-execution agent refs | only the intentional audit-residue sentence remains |
| approval anchor | SHA-256 over UTF-8 bytes from `## Workflow Structure` up to `## Completion Gate` (trailing separator stripped) | `453fa2d1df14f149b367e3cd92a603135b7ac2b187faf5dba38e5313e72d5b15` |

## Remaining Findings

| priority | finding | status |
|---|---|---|
| P3 | `saga:readonly-verifier`'s default system prompt is refute-oriented ("not a general-purpose reviewer"); the candidate uses it as the sandbox profile with the per-call lens charter defining the actual role. Acceptable for adversarial review/validation, but the first run should confirm charter framing dominates the profile's refute default. | OPEN - informational |

## Residual Risk

- This exact cc-workflow ceremony has not yet been exercised end-to-end; the first run on #357 is
  its proof. Spawn parameters are harness-recorded, not cryptographically attested — stated
  in-contract.
- The replay of the preserved diff onto current main may surface real conflicts (both #612-#614 and
  the preserved bytes touch saga/fleet-core files); focused suites must be green before lens
  dispatch, per the operating contract.

## Routing

Present anchor `453fa2d1df14f149b367e3cd92a603135b7ac2b187faf5dba38e5313e72d5b15` to Jeff and stop.
On approval: commit the revised plan + this artifact to the outcome branch, then `/work` executes -
replay preserved bytes onto current main, focused suites green, dispatch the six-lens Workflow
script (pool of 3), fix findings, `/code-review` + `/qa` gates, PR, merge under explicit
confirmation, issue/board reconciliation, and outcome harvest.
