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
today's file-edit scope (R21 — mutating external workers stay out of scope entirely, blocked on
the ideation-R14 sandbox profile, issue #287). This covers both worker kinds: an ordinary
Claude-agent worker, and a **chaperone worker** — a Claude-agent worker whose units are owned by
an external engine (agy, codex) it resolves, dispatches, verifies, and applies on behalf of (KTD1,
#283 U12). The chaperone is still the one that touches the working tree and owns the commit —
R21's scope never widens; see `external-engine-workers.md` for the full resolve → dispatch →
verify → apply → test → manifest protocol this document's attribution/disposition/tier fields feed
into.

## Who writes it and when

The **worker itself**, at segment/unit exit (Step B1, after its assigned units complete and
before the coordinator captures the wave's diff summary) — a worker is a live agent with
filesystem access, unlike a cc-workflows leaf (contrast `manifest_store.py`'s KTD7 driver-
materialized path, which exists only because workflow scripts have no filesystem access).

Call the store CLI directly:

```bash
python3 plugins/saga/scripts/manifest_store.py \
  --repo-root <repo-root> --saga-id <saga-id> \
  write --execution-id <worker-id>-<unit-id> --file <path-to-manifest.json>
```

`<manifest.json>` is the `to_dict()` output of a `provenance_manifest.Manifest` built as below.

## Manifest shape for a worker exit

**Attribution (R2), Claude-agent worker:** `kind="team-execution"`, `identity="worker-<plugin>"`
(the resident worker id, matching the `worker-<plugin>` naming in the residency table), `effort`
the tier the worker ran at (`opus/high`, etc., from the team-execution spec), `protocol=""` (no
external-engine protocol applies to a Claude-agent worker).

**Attribution (R2), chaperone worker:** `kind="external-engine"`, `identity="<engine>/<variant>"`
(the resolved engine and variant, not the resident id — the same identity format
`engine_dispatch.build_dispatch_manifest` always emits), `effort` the resolved engine's effort,
`protocol` populated from the resolution. The resident id (`worker-<engine>` /
`worker-<capability>`) still names the segment in the Workers table (KTD3) — it is not what
`identity` carries here, since `identity` attributes the *output*, not the residency slot that
produced it. Full mechanics in `external-engine-workers.md` §5.

When a chaperone batches multiple homogeneous external-engine units, it still writes distinct per-unit manifests. The batch id and sampling decision belong only in advisory chaperone provenance;
they do not replace each unit's `manifest_identity`, `output_completeness`, or disposition.

**Disposition (R18):** `ran-as-requested` for a worker (either kind) that completed its assigned
units as requested. For a chaperone worker, two more dispositions are live (not reserved): the
engine call itself never runs — `fell-back-to-claude` when the resolver's own capability-no-fit /
preflight-unavailable path routes the unit to the chaperone as Claude, carrying the fallback
reason as `disposition_note`; the engine ran but wasn't the one the operator approved —
`substituted-engine` when run-time capability routing resolved a different engine/variant than the
plan-time preview the tier table recorded (KTD4); `rejected-offload` when the requested engine ran
but Claude's chaperone rejected its output after review. A rejected offload requires a normalized,
non-empty `disposition_note`; that exact note is also the rationale of a typed `dropped`
reconciliation item passed to reviewers and validators as advisory evidence. A Claude-agent worker
(no `engine`/`capability` selector) only ever writes `ran-as-requested` — the other dispositions
require an external-engine resolution. Trigger conditions and the halt path (R25/R26 — a halt writes
no manifest at all, nothing ran) are in `external-engine-workers.md` §2, §4, and §5.

**Output completeness (R3):** one `OutputCompleteness` per unit the worker owned, derived the same
way `completeness_gate.Contract.from_unit` + `classify()` already do for spec-driven runs:
declared keys from the unit's `returns`/contract, produced keys from what the worker actually
changed/returned. A required, non-skipped, contract-bearing unit with no manifest at wave-close is
a `missing-output` trip — consistent with `validator-evidence-state.md`'s Required-Evidence
Absence rule for validators, applied here to workers.

**Claim provenance:** optional at v1. For a Claude-agent worker, output is code/diff, not a set of
prose claims — leave `claim_provenance` absent (lightweight tier, KTD9) unless a future revision
asks a worker to attest specific claims about its own diff. For a chaperone worker whose engine
returned prose claims alongside its evidence (e.g. a second-opinion review verdict), the chaperone
may populate `claim_provenance` from the engine's claimed layer — but every claim stays
producer-`claimed`-only until the chaperone adjudicates it (`engine_dispatch.adjudicate_manifest`,
never the engine itself); a claimed-`verified` status never counts toward a gate on its own (D5, no
self-attestation — same rule either worker kind).

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

A `rejected-offload` record is a recovered review signal, not a passing worker result. Its typed
reconciliation projection is delivered to both reviewer and validator evidence inputs, but neither
the note nor its `dropped` item may satisfy a gate.

The associated reconciliation result retains the unit's canonical intent. `offload`,
`second-opinion`, and `divergence` each select exactly one Saga recipe; a manifest disposition does
not replace or reinterpret that intent. The dispatch/result/manifest chain is bound to one non-empty
execution id, canonical intent and recipe, immutable evidence digest, and ordered content-derived
source-finding IDs; rejected-offload evidence retains those same bindings and its original unit
intent.

The typed result is bounded to 256 UTF-8 bytes per identifier, 256 findings, 4096 bytes per rationale,
and 65536 canonical bytes. Run-fact persistence is a smaller structural projection: identities,
digest, statuses, and canonical result hash only — no raw engine/panel output or rationale text. Each
reconcile/apply transition is appended from a verified snapshot under the per-ledger exclusive lock;
ledger and lock files are mode `0600`, and transition order is exactly reconcile then at most one
apply.

Advisory-jury policy comes from the shared lower-level Saga engine registry, including
`PANEL_N_CAP = 7`, advisory verdict, and Claude foreman. Dispatch adds 64 KiB per-member and 256 KiB
cumulative UTF-8 output caps before the foreman runs. Reconcile/apply facts and `/retro`'s
`approval_required` recipe-update proposals remain typed advisory evidence. They never grant the
manifest, an external engine, a panel member, or a proposal gate authority.
