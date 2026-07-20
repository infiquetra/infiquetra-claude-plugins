# Doc review (focused delta) — cross-runtime-acceptance plan 2026-07-20 AFK refresh

- **Target:** `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity` at base `23c48a34`
  (the refresh commit; the repairs below are committed together with this artifact — see the
  commit that carries both)
- **Scope:** the 2026-07-20 AFK-frontier refresh delta only. The 2026-07-15 body was reviewed
  pre-freeze; it is out of scope except where the delta touches it (KTD4, Implementation-units
  preface, Stop conditions, Completion gate — all reviewed here).
- **Blocked status:** not blocked
- **One-line verdict:** **READY** — the refresh delta is evidence-backed, all readiness-skeptic
  and second-opinion findings are repaired in place or adjudicated with evidence, zero P0–P3
  findings remain, and the ceremony anchor is byte-stable across every repair.

## Operating mode

Operator directive 2026-07-20 (verbatim in the plan Summary): "ok lets refresh the plan and assume
I will be afk for this frontier." Under the plan's KTD9, this repaired doc-review substitutes for
the interactive plan-review touchpoint, and the ceremony anchor is adopted under the same recorded
delegation rather than a fresh in-session approval. Engine offer for this stage
(`engine_offer.py offer --stage doc-review`): `prompt_required: false` — external opinion is
advisory by default; the gated readiness verdict stays Claude's alone.

## Delta reviewed and evidence

| # | Change | Evidence |
|---|--------|----------|
| 1 | Frontmatter `deepened: 2026-07-20`; Summary refresh paragraph binding the AFK delegation, vehicle, merge pre-approval, and anchor | Directive quoted verbatim from the 2026-07-20 session; vehicle precedent = approved anchors #604 `214431cf`, codex #33 `bc038d41`, codex #34 `c76ef1ee` |
| 2 | Verified baseline pins bound in Hard inputs: Claude `origin/main` `cf15a09f` (saga 0.104.0, fleet-core 0.15.0); Codex `origin/main` `d29e75fd` (saga 0.77.0+codex.20260720023112, fleet-core 0.9.0+codex.20260719174556) | Live `git fetch` + manifest reads on both repos 2026-07-20; codex #34 squash `d29e75fd` confirmed via `gh` |
| 3 | New KTD7 (upstream-first discharge precedes pinning; KTD4 stands), KTD8 (seam activation = parity restoration), KTD9 (AFK operating mode) | KTD8 wiring states read from source: Claude `outcome.py:2422/:2478` at `cf15a09f` already pass `default_lease_authority()`; codex `outcome.py:2011/:2129` at `d29e75fd` withhold it (the #34 plan's "KTD6" operator deferral 2026-07-19) |
| 4 | New `## Pre-acceptance production units` — PA-1 (help strings `outcome.py:2281/:2284`, dead success-print `:2624-2627`, `_write_once` handoff-dir `0o700` at `outcome_compat.py:1135`, `audit_store` ancestor hardening; saga →0.105.0, fleet-core →0.16.0) and PA-2 (seam activation at both `make_dispatcher` sites + activation pin, byte-faithful re-port, per-port-gate pin updates, saga →0.78.0+codex.`<ts>`, fleet-core →0.10.0+codex.`<ts>`) | All eight target sites read from source at the pinned SHAs; deferral dispositions traced to the #34 code-review artifact and QA artifact (paths now cited in the plan; both merged at `d29e75fd`) |
| 5 | Right-sizing: PA units under the programmatic `saga:code-review` gate, not the six-lens ceremony | Same remediation class as #34's `39a9ed4` commit, which shipped under the review gate alone |
| 6 | Implementation-units preface gates U1 on both PA merges + root pin re-verification | Circularity with the harness's own R1 repaired this review (see adjudication #8) |
| 7 | Harness suite renamed `tests/test_cross_runtime_acceptance.py` | Avoids near-collision with existing `tests/test_outcome_cross_runtime_contract.py` (#604) and exact collision with the codex port-gate suite name |
| 8 | Workflow Structure + operating contract converted from the Codex auto form (gpt-5.6 tiers, `role_lens_sha256` digests) to the cc-workflow inline form: 4 opus/high reviewers + 3 sonnet/medium validators, all `saga:readonly-verifier` + worktree isolation, bounded pool 3, halt-if-unavailable, three-cycle tripwire | Mirrors the #604/#33/#34 approved vehicle; `saga:readonly-verifier` present in the session agent roster; table parses 9 rows |
| 9 | Stop conditions: AFK halt bullet; Completion gate: PA discharge + AFK writebacks | Halt semantics and writeback targets made concrete this review (adjudications #9/#10) |

## Readiness-skeptic pass (first-party) — four safe fixes applied pre-second-opinion

1. Unspecified version rungs → pinned (saga 0.105.0 / fleet-core 0.16.0; codex 0.78.0/0.10.0).
2. PA-2 missing per-port-gate pinned-expectation update → added (stale pins are a silent-drift
   hazard, not a formality).
3. Freeze moment unstated → "The plan freezes at PA-1 branch creation."
4. Ancestor-scoping rationale for the `audit_store` hardening → recorded (below-home scope keeps
   temp-dir test roots valid).

## External second opinion — adjudication

Delegated codex reviewer, run `20260720T045532Z-14441910f0bc` (read-only, adversarial lens,
evidence bundle under `.claude/codex/runs/`). Eleven findings returned; every finding is advisory
and was adjudicated against document and repo evidence. All repairs land **outside** the anchored
span; the anchor was recomputed byte-exact after every edit and never moved.

| # | Reported | Adjudication | Disposition |
|---|----------|--------------|-------------|
| 1 | P0: merge pre-approval unverifiable from the plan | Valid self-containment gap (the approval is held in-session; a cold reader cannot verify it) | **Repaired** — provenance recorded in the Summary: granted by Jeff 2026-07-18 in-session, re-recorded in the outcome memory record and this artifact; scope = every merge inside this outcome, each contingent on its own green gates |
| 2 | P0: PA units require GitHub mutation the workflow contract forbids | **Dismissed as a contradiction** — the contract's first sentence explicitly assigns root "Git, PR/merge, issue and board reconciliation"; the "authorizes no…" clause constrains the lens fan-out, and the ceremony governs only U1-U5. Real ambiguity for a cold reader | **Repaired as clarification** — scope-division sentences added to the PA preamble (outside the anchor) |
| 3 | P1: KTD4 silently narrowed | Not silent — KTD7 records the reconciliation and rationale explicitly. Isolated-read hazard is real | **Repaired** — cross-reference added to KTD4 itself |
| 4 | P1: PA sources uncited | Valid | **Repaired** — code-review + QA artifact paths, finding routings, and the `d29e75fd` binding cited in the PA preamble |
| 5 | P1: committed outcome spec conflicts with "sole remaining node" | Verified true: `outcome-spec.json` is the 2026-07-15 bootstrap snapshot, all 11 nodes `state: pending`, `updated_at` 2026-07-15T10:56:45Z. Status is derived on read (coordinator R17) from the ledger (10/11 done) + GitHub events | **Repaired** — authority ordering recorded in Hard inputs; snapshot refreshes at the next `outcome commit --push` |
| 6 | P1: PA-1 branch mechanics undefined | Valid | **Repaired** — issue-first numbering, `work/<N>-<slug>` from freshly fetched `origin/main`, dedicated primary-checkout worktree, clean-tree requirement, content-drift = AFK HALT |
| 7 | P1: `<ts>` placeholder underived | Valid | **Repaired** — one UTC `date -u +%Y%m%d%H%M%S` value captured at release-surface authoring, reused verbatim across manifest/changelog/acceptance pins |
| 8 | P1: U1/R1 gate circular | Valid — wording bug | **Repaired** — the pre-U1 pin check is root's own (fetch + receipt match); the harness's R1 is implemented in U1 and re-checks on every invocation |
| 9 | P1: AFK halt semantics undefined | Valid | **Repaired** — halt = write `docs/outcomes/lease-safe-runtime-continuity/afk-halt-report.md`, commit+push to the outcome branch, deliver as the session's final message, no further mutation |
| 10 | P1: completion-gate children and memory target unenumerated | Valid | **Repaired** — four #579 children enumerated (#604/#605 claude, #33/#34 codex); memory target named; closing-report content pinned including the unpushed local-`main` commits `dc1d8bef`/`1a7b145a` |
| 11 | P2: PA-1 security boundaries ambiguous | Valid | **Repaired** — existing-directory predicate = `_ensure_private_dir` semantics (dir, non-symlink, euid-owned, exactly `0o700`, typed refusal); ancestor walk = lexical below-home scope, home excluded, per-component `lstat` without resolution, refuse symlink or `mode & 0o002` |

## Ceremony anchor (adopted under the KTD9 delegation)

```
4b21df73f98030f97b5f770adddaf33e14048a07af8221005f6d5e3699e1cb0f
```

3754 bytes from the `## Workflow Structure` heading to the `## Completion gate` heading, exclusive
(the span includes the operating contract). Recomputed byte-exact after the four first-party fixes
and again after all eleven second-opinion repairs — matched both times. Adoption note: under the
operator's 2026-07-20 AFK directive and the plan's KTD9, this repaired doc-review substitutes for
the interactive anchor-approval touchpoint; the vehicle and mechanism are identical to the
operator-approved #604/#33/#34 ceremonies. Any model, effort, lens, validator, or execution-class
change afterward invalidates the anchor and is an AFK HALT.

## Findings

None remaining. P0: 0, P1: 0, P2: 0, P3: 0.

## Links

- Plan: `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`
- Issue: infiquetra/infiquetra-claude-plugins#605 (leaf `cross-runtime-acceptance` of
  `lease-safe-runtime-continuity`; parent objective #579)
- Second-opinion evidence bundle: `.claude/codex/runs/20260720T045532Z-14441910f0bc/`
- PA sources of record (codex repo, merged at `d29e75fd`):
  `docs/code-reviews/2026-07-19-outcome-cross-runtime-parity-code-review.md`,
  `docs/evidence/adhoc-work-34-codex-parity/artifacts/d000674258b48d451467cbe99b1a4c2e67ad41bf138e3fba49238ed9aaa7d09d.md`
- Template: `docs/reviews/2026-07-18-issue-358-plan-refresh-delta-doc-review.md`
