# Doc Review - Codex cross-runtime Outcome parity plan

One-line verdict: **READY TO FREEZE** - all P0-P3 findings were fixed; execution is gated on both
merged prerequisite releases, operator approval, a fresh target worktree, refreshed target-repo
review, and the port classification gate.

## Review-result contract

- **Target:** `docs/plans/2026-07-15-codex-cross-runtime-outcome-parity-plan.md`
- **Reviewed revision:** local outcome worktree based on
  `a20cc3ce6d740a4891bddba71f7e8f2856620655`
- **Review artifact:**
  `docs/reviews/2026-07-15-codex-cross-runtime-outcome-parity-plan-doc-review.md`
- **Target repository:** `infiquetra/infiquetra-codex-plugins`
- **Classification:** high-risk cross-runtime authority/compatibility proof port
- **Rubrics:** issue cores plus context completeness, issue sizing, prerequisite mapping, and
  readiness authority, migration, portability, release, and rollback lenses
- **Linked nodes:** `claude-cross-runtime`, `codex-substrate`, then `codex-parity`
- **Blocked actions:** no remote mutation, target worktree/branch, agent, validator, implementation,
  install, Git write, or workflow run occurred

## Applied fixes

| ID | Priority | Status | Applied fix |
|---|---|---|---|
| D579P-1 | P1 | fixed | Added the missing Codex shared-runtime substrate prerequisite; protocol parity no longer hides a lease/settlement port. |
| D579P-2 | P1 | fixed | Made native `outcome.dispatch.v2` acknowledgement a preservation invariant; handoff acceptance cannot itself mark launched. |
| D579P-3 | P1 | fixed | Split same-clone mutation from different-clone reconstruction; cross-clone output exposes canonical completion/candidate frontier with transient state unknown and mutation denied. |
| D579P-4 | P1 | fixed | Replaced bearer-token handoff language with protected local offer/accept-intent/successor/accept-commit state, one operation/subplot, 300-second TTL, and 30-second future-skew limit. |
| D579P-5 | P1 | fixed | Retired legacy `outcome-bundle/1` import writes/replay and prohibited an escape hatch. |
| D579P-6 | P1 | fixed | Required exact merged Claude fixture/schema bytes and prohibited schema drift inside the Codex PR. |
| D579P-7 | P2 | fixed | Added exhaustive runbook-v3 manifest/classification, current Codex preservation drift, isolated install, fresh-session, cutover, and rollback evidence. |
| D579P-8 | P2 | fixed | Added real Git topology, process-race, write-once backend, acknowledgement, crash/replay, and no-mutation tests in both runtime orderings. |
| D579P-9 | P2 | fixed | Required a target-repo plan/review copy and frozen-ref refresh before manifest initialization. |
| D579P-10 | P2 | fixed | Scoped Fleet Core behavior as preserve-only and removed lease/settlement reimplementation from expected work. |
| D579P-11 | P3 | fixed | Added the machine outcome-spec path/node and completed this review-result contract with reviewed revision and artifact path. |

## Readiness summary

| rubric | score | result |
|---|---:|---|
| acceptance clarity | 10/10 | discovery, projection, handoff, native launch, legacy migration, and release claims are executable |
| authority/security | 10/10 | repo/blob identity and compatibility checks precede all mutation; protected same-clone evidence is required |
| prerequisite mapping | 10/10 | exact Claude contract and Codex substrate releases are hard inputs |
| Codex preservation | 10/10 | native dispatch-v2 and protected launch semantics cannot be overwritten by parity |
| portability fidelity | 10/10 | fresh manifest/classification and all cutover proofs are mandatory |
| issue sizing | 9/10 | one cohesive compatibility adapter/release; substrate and final acceptance remain separate |

## Evidence verified

- Current Codex Outcome already uses `outcome.dispatch.v2` intent/acknowledgement and treats
  `handed-off` separately from `launched`.
- Current Codex legacy bundle import writes spec/receipt/fact state, so explicit retirement is
  necessary to avoid a second authority path.
- The merged Claude plan defines the four exact compatibility schemas, committed-spec/GitHub
  authority, cross-clone read-only projection, and protected scoped handoff contract.
- Codex's runbook requires behavior adaptation, not host-shaped byte copy, and makes classification,
  installed proof, fresh-session readback, and rollback part of completion.
- The Workflow Structure parses and passes full-review selection with digest
  `1ca06d3b15280fa357d69d8d9e588d90b660a36473ac04af87e4d03b39378aba`.

## Remaining findings by priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual risk

The final Claude fixture/schema and Codex substrate interfaces are not merged. The mandatory
target-repo refresh must resolve actual names and exact SHAs. Any incompatible contract returns to
the owning upstream issue; it is not papered over by a Codex-only translation or workflow downgrade.
