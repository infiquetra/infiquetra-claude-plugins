# The IntentEnvelope — one committed run-start posture (#380)

Run-start posture — attended vs. unattended, which ceremony gates apply, what spend posture
follows — is captured **once**, as one committed, schema-validated envelope, and every consumer
resolves through it. No plugin asks its own posture question; the fleet drift-guard test
(`tests/test_intent_envelope.py`) enforces that mechanically.

- **Canonical schema:** `plugins/fleet-core/scripts/fleet_commons/intent_envelope.py`
  (fleet-commons home — three plugins consume it). saga re-exports it at
  `plugins/saga/scripts/intent_envelope.py`, which also carries the saga-side glue
  (`compute_stakes`, `implied_required_checks`, `seeded_tier`) and the CLI.
- **Operator surface:** doc + CLI only (`{#operator-choice-framework}`) — nothing is
  runtime-injected.

## Schema (v1)

```json
{
  "schema_version": 1,
  "run_mode": "attended | unattended",
  "ceremony_gates": {
    "reviews_required": "gate | auto",
    "merge": "gate | auto",
    "deploy_nonprod": "gate | auto"
  },
  "source": "interview | issue-capture | defaults:unattended | ...",
  "authored_at": "2026-07-14T00:00:00Z",
  "authored_by": "jeff"
}
```

The schema is **closed**: an unknown key, an off-vocabulary value, or a foreign
`schema_version` is an error, never a pass. Extensions (#373's `backends_permitted` /
`degrade_policy` / `spend_envelope`, #449's envelope tokens, #372/#433's mid-run amendment
verbs) are made by editing the canonical module — never by consumers tolerating unknowns.
Every unset ceremony gate defaults to `gate` (T7-F3-2); the emitted artifact always writes
all three gates explicitly so a reader never needs to know the default.

**Threat model.** `source` / `authored_by` / `authored_at` are self-attested labels — a forged
envelope is syntactically indistinguishable from a real one. The envelope records the
operator's intent; **it authorizes nothing by itself**. Merge/deploy stay GATE-by-default in
the reversibility certificate regardless of what the envelope says; the revocable
`AUTONOMOUS_UNDER_ENVELOPE` write class with a real token check is #449's separate mechanism.
The `approval_token` in the spend resolver is an opaque presence check, not a validated
credential.

## The single interview (the registry)

Four typed questions, closed options, machine-parseable end to end (T1-F5-8):

| qid | options | default |
|---|---|---|
| `run_mode` | attended / unattended | *(required)* |
| `reviews_required` | gate / auto | gate |
| `merge` | gate / auto | gate |
| `deploy_nonprod` | gate / auto | gate |

```bash
# Render the interview (data-backed stakes come from the outcome spec's real DAG):
python3 plugins/saga/scripts/intent_envelope.py interview --outcome-spec docs/outcomes/<id>/outcome-spec.json
# Capture typed answers -> a validated envelope JSON:
echo '{"run_mode": "unattended", "merge": "auto"}' | \
  python3 plugins/saga/scripts/intent_envelope.py capture - --authored-by jeff > envelope.json
```

The interview prompt shows `parallel_width` (widest concurrent wave) and
`critical_path_estimate` (longest dependency chain, unit-weight `critical_path_wall`) so the
operator decides against computed stakes, not prose guesswork (T4-F4-2). Free-form answers,
unknown qids, and missing required answers all fail closed.

Which questions may still be asked? `unanswered_questions(envelope)` — with a valid envelope
it returns `()`; a consumer that asks anyway is re-asking an answered question (the
drift-guarded no-reprompt contract, H-F2-9).

## Consumers (all resolve through the registry)

| consumer | read |
|---|---|
| `/outcome start` | reads the issue-carried envelope (or `--intent-file`), commits it as `OutcomeSpec.intent`, and skips the interview when a valid envelope is present; absent/invalid falls back to the interview (surfaced, never adopted) |
| `/outcome` harvest | `ceremony_gates.reviews_required == "gate"` implies a `code-review` closure check on every code leaf — the leaf's `done` transition needs review evidence at the close SHA (via `closure_gate` + `evidence_ledger`) |
| `/plan` Step 1 | `intent_envelope.seeded_tier(spec, work_shape)` seeds the per-unit tier table defaults from the committed posture (`recommend_tier(work_shape, run_mode)`); the table, operator override flow, and `VERIFY_N_CAP` mechanics are unchanged |
| `/work` | resolves spend decisions through `intent_envelope.py spend` / `resolve_spend_action` — attended spend increases need an explicit approval token (`PostureError` otherwise); unattended runs stay cache-tight silently |
| team-execution Step B1 | `plugins/team-execution/skills/team-execution/scripts/posture_check.py` — the wired fan-out consumer (exit 2 on a posture refusal) |
| mission-control capture | `sdlc_manager.py issue intent-envelope` renders the ship-policy block; prepared-issue readiness BLOCKS on a present-but-invalid block |

## The issue-carried envelope (ask once, on the issue)

Mission-control authors the envelope onto the issue body at capture (S-22 / G-hybrids-4):

```bash
python3 plugins/mission-control/scripts/sdlc_manager.py issue intent-envelope \
  --run-mode unattended --merge auto --authored-by jeff
```

emits a `### Intent envelope` heading plus a fenced ` ```intent-envelope ` JSON block —
schema-validated, not prose. `/outcome start --from-objective <owner>/<repo>#<N>` reads the
parent Objective's body; exactly one block is the contract (two is an error). The spend/tier
machinery is pure functions:

```bash
python3 plugins/saga/scripts/intent_envelope.py recommend --work-shape judgment --run-mode unattended
python3 plugins/saga/scripts/intent_envelope.py spend --run-mode attended --spend-increase --approval-token <tok>
```

## Mode-keyed machinery (never prose)

- `spend_posture(run_mode)` → `("cache-tight", "silent")` for unattended;
  `("interactive", "ask-on-spend-increase")` for attended (T12-F3-7).
- `recommend_tier(work_shape, run_mode)` → attended = the tier-policy registry default;
  unattended = exactly one rung cheaper via the ladder ops (`{#tier-vocab-ordering}`), floor
  is a no-op (T12-F6-7).
- `self_select_posture(work_shape)` → an unattended run's full posture (envelope with all
  gates at `gate` + the unattended tier) from the same matrix, zero interactive answers
  (T1-F6-8).
