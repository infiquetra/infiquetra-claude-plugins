# Worker Exit Manifest — team-execution

A provenance manifest (`saga.manifest.v1`, `plugins/saga/scripts/provenance_manifest.py`) is a
typed, cross-worktree evidence record for a delegated output. This document is the worker-exit
contract: what a team-execution worker's manifest carries and how it is written. It complements —
never duplicates — `validator-evidence-state.md`: validators keep their repo-local per-run
evidence JSON (`.claude/team-execution/validators/`); a manifest is the cross-worktree envelope
for the worker's *output*, and it outlives the run (git-common-dir, R19).

---

## Evidence, never authority (R20/R21)

A worker manifest grants no privilege and holds no verdict. It does not gate a wave, unblock a
dependency, or substitute for reviewer/validator consensus. It is read-only, advisory evidence
(R8) that downstream consumers (`/code-review`, `/qa`, `/retro`) may use to spend attention more
efficiently — never something a worker or coordinator can use to skip a required check. Nothing
in this contract expands what a team-execution worker is authorized to mutate; workers keep
today's file-edit scope (R21 — mutating external workers stays out of scope entirely; this
contract covers Claude-agent team-execution workers only, the only kind that exist until #283's
U12 external-engine-as-worker wrapper lands).

## Who writes it and when

The **worker itself**, at segment/unit exit (Step B1, after its assigned units complete and
before the coordinator captures the wave's diff summary) — a worker is a live agent with
filesystem access, unlike a cc-workflows leaf (contrast `manifest_store.py`'s KTD7 driver-
materialized path, which exists only because workflow scripts have no filesystem access).

Call the store CLI directly:

```bash
python3 plugins/saga/scripts/manifest_store.py write \
  --repo-root <repo-root> --saga-id <saga-id> --execution-id <worker-id>-<unit-id> \
  --file <path-to-manifest.json>
```

`<manifest.json>` is the `to_dict()` output of a `provenance_manifest.Manifest` built as below.

## Manifest shape for a worker exit

**Attribution (R2):** `kind="team-execution"`, `identity="worker-<plugin>"` (the resident worker
id, matching the `worker-<plugin>` naming in the residency table), `effort` the tier the worker
ran at (`opus/high`, etc., from the team-execution spec), `protocol=""` (no external-engine
protocol applies to a Claude-agent worker).

**Disposition (R18):** `ran-as-requested` for a worker that completed its assigned units;
`fell-back-to-claude` / `substituted-engine` do not apply to a Claude-agent worker today — they
are reserved for the future external-engine-as-worker leg (R14, deferred, #283 U12).

**Output completeness (R3):** one `OutputCompleteness` per unit the worker owned, derived the same
way `completeness_gate.Contract.from_unit` + `classify()` already do for spec-driven runs:
declared keys from the unit's `returns`/contract, produced keys from what the worker actually
changed/returned. A required, non-skipped, contract-bearing unit with no manifest at wave-close is
a `missing-output` trip — consistent with `validator-evidence-state.md`'s Required-Evidence
Absence rule for validators, applied here to workers.

**Claim provenance:** optional at v1 for worker manifests — a worker's output is code/diff, not a
set of prose claims the way an external-engine dispatch is. Leave `claim_provenance` absent
(lightweight tier, KTD9) unless a future revision asks a worker to attest specific claims about
its own diff (it would still require Claude adjudication before any claimed-`verified` status
counts toward a gate — D5, no self-attestation).

## Tier

Lightweight is the default and typically sufficient (attribution + disposition + existence bit).
Use full tier — with `output_completeness` populated — for any unit whose plan marks it
contract-bearing (has a declared `returns`/output contract), matching R10/R13's existing
completeness-gate scoping.

## Failure modes stay evidence-only

A worker that halts, is reassigned, or produces a partial result records that honestly in
`disposition` + a `disposition_note` — never silently. The manifest records what happened; it
never decides whether the wave proceeds. That decision stays with the coordinator and the
existing reviewer/validator consensus machinery.
