# Dispatch Table

The designed routing map for `/loop`. It is **total** over the 17 routable lifecycle commands: every
input type, saga `lifecycle_phase` + `phase_status`, and handoff maturity resolves to exactly one next
command. The table is designed from the already-shipped siblings' own clean-exit routing — there is no
upstream router to port. `/loop` reads this table in Phase 2, then ticks the saga and dispatches
(Phase 4).

The 17 routable commands: `/office-hours`, `/ideate`, `/brainstorm`, `/spec`, `/plan`, `/doc-review`,
`/work`, `/code-review`, `/qa`, `/investigate`, `/founder-review`, `/strategy`, `/optimize`, `/handoff`,
`/retro`, `/resume`, and `/loop` itself (re-entry).

---

## Stub-vs-shipped state (the advisory rule)

A route to a **stub** target is **advisory**: `/loop` names it as the next command and dispatches, but
**never blocks `/loop` on its output** — the stub cannot produce a gate result yet. Only the shipped
`/doc-review` route carries a HARD gate.

| Target | State | Routing |
|---|---|---|
| `/office-hours` | shipped (232L) | normal |
| `/ideate` | shipped (529L) | normal |
| `/brainstorm` | shipped (342L) | normal |
| `/spec` | shipped (spec-interrogation engine) | **advisory + off-chain** — never block |
| `/plan` | shipped | normal |
| `/doc-review` | shipped (178L) | **HARD gate** (P0/P1 block, see below) |
| `/work` | shipped | normal |
| `/code-review` | shipped | normal |
| `/founder-review` | shipped (239L) | normal |
| `/handoff` | shipped (68L, functional) | normal + handoff envelope |
| `/qa` | shipped (gate-only) | **advisory** — never block |
| `/investigate` | shipped (systematic-debugging engine) | **advisory + off-chain** — never block |
| `/retro` | shipped (meta-improvement engine) | **advisory + terminal** — never block |
| `/resume` | **stub (24L)** | **advisory / opt-in** — never auto-route |
| `/strategy` | shipped (STRATEGY.md engine) | **advisory** — never block |
| `/optimize` | **shipped (metric-loop engine)** | **advisory + off-chain** — never block |

---

## Cold-start / greenfield entry (no saga, no issue)

When `scan` finds no in-flight saga and there is no issue, route by how settled the ask is:

| Input shape | Next command |
|---|---|
| Bare, unframed ask ("I have an idea but don't know what it is", "what's even the right frame") | `/office-hours` |
| "Give me ideas" / "what should I improve" / open divergent ask | `/ideate` |
| One chosen idea, WHAT not yet pinned | `/brainstorm` |
| A vague ask / under-specified issue that needs a precise, formal WHAT before planning or handoff | `/spec` (advisory, off-chain) |
| Settled WHAT, ready for HOW | `/plan` |
| Strategic-direction ask ("where are we pointed") | `/strategy` (advisory, shipped) |

This mirrors `/ideate`'s and `/office-hours`'s own clean exits: `/ideate` routes an unframed ask to
`/office-hours`; `/office-hours` routes a settled frame onward to `/ideate` / `/brainstorm` / `/plan` /
`/strategy`.

---

## The main chain (issue / plan present)

The spine, by handoff maturity and saga phase:

```
idea/requirements-ready ─► /plan ─► /doc-review ─► /work ─► /code-review ─► /qa ─► /handoff or /retro
```

| Saga `lifecycle_phase` | `phase_status` | Handoff maturity | Next command |
|---|---|---|---|
| (none) | — | `idea-ready` / `requirements-ready` | `/plan` |
| `ideation` / `brainstorm` | any | — | `/plan` (settle HOW) |
| `plan` | `complete` | `plan-ready` | `/doc-review` (readiness) |
| `plan` | `pending` / `in_progress` | — | `/plan` (finish the plan) |
| `review` | `complete`, no P0/P1 | `plan-ready` | `/work` |
| `review` | `complete`, P0/P1 open | — | **BLOCK** -> `/work` only on override; else back to `/plan` |
| `work` | `in_progress` | `resume-ready` | `/work` (resume the round-N loop) |
| `work` | code at PR boundary | `resume-ready` | `/code-review` |
| `work` | `complete` (merged) | `resume-ready` | `/qa` (advisory, gate-only) |
| `qa` | any | `resume-ready` | `/handoff` or `/retro` (advisory, shipped) |
| `retro` | any | — | **terminal** — done; `/handoff` if a learning should become an issue |

For `plan-ready` / `resume-ready` issues, the direct consumer is `/work`; for `idea-ready` /
`requirements-ready`, it is `/plan` (matches `parse_issue.py`'s `handoff.can_plan` / `can_work`).

---

## Off-chain commands (not on the linear spine)

| Input / trigger | Next command | State |
|---|---|---|
| A vague ask / under-specified issue that needs a precise, formal WHAT (five-Why, scope/MVP/out-of-scope lock, failure modes) before planning or handoff | `/spec` | advisory, shipped (off-chain) |
| Bug / defect / root-cause question, a failing or flaky test, "why is this broken" | `/investigate` | advisory, shipped (off-chain) |
| Strategic-direction ask, STRATEGY.md maintenance | `/strategy` | advisory, shipped |
| "Improve / route / optimize this metric" | `/optimize` | advisory, shipped (off-chain) |
| Scope / ambition question ("is this ambitious enough", "think bigger") on a plan / strategy / brainstorm | `/founder-review` | shipped |
| Post-completion learnings capture, workflow self-improvement | `/retro` | advisory, shipped (terminal) |
| Hand a durable artifact to an SDLC issue | `/handoff` | shipped (+ envelope) |
| Deep forensic reconstruction (opt-in only) | `/resume` | advisory stub, never auto |

`/founder-review` fires **upstream of execution** and produces a scope decision, then routes accepted
scope back to `/plan` and the (re-)expanded plan back to `/doc-review` — `/loop` honors that closed
loop rather than treating founder-review as a terminal.

`/spec` is the **off-chain spec-interrogation engine** (the WHAT-rigor sibling of `/plan`'s HOW-rigor)
and is **saga-UNTOUCHED**: it writes a sharp WHAT artifact under `docs/specs/` and routes the work OUT
— to `/handoff` (the spec becomes a `requirements-ready` SDLC issue source), to `/plan` (settle the
HOW), or to an optional `/doc-review` pass (which reads the spec under the **requirements** lens). It
never enters the work thread and never blocks `/loop`.

`/investigate` is the **off-chain systematic-debugging engine** and is **READ-ONLY on the saga**: it
diagnoses (it never blocks `/loop`) and routes the work OUT by what it finds — a confirmed **real fix**
→ `/work` (via a `/handoff` issue that DESCRIBES the defect and LINKS the DEBUG REPORT as evidence —
never pass `docs/investigations/` to `handoff_envelope`'s classifier; it mis-classifies, see
debug-report.md); an **applied inline fix** → `/work` or `/code-review` to ship it; a **trackable
defect** (not fixing now) → `/handoff`; a
root cause that is really a **design problem** → `/brainstorm`. `/qa` routes deep post-merge
root-cause failures here (clear/trackable defects still go to `/handoff`); there is **no
`/investigate` → `/qa` verify loop` — `/investigate` carries its own minimal verification.

`/optimize` is the **off-chain metric-driven optimization engine** and is **saga-UNTOUCHED**: it
runs a **bounded-experiment loop** toward a measurable target across 8 metric classes (perf / cost /
reliability / agent-usability / security / quality / DX / maintainability). It never enters the work
thread and never blocks `/loop`.

**`/optimize` vs `/qa` — don't confuse the gate with the loop.** `/qa` **gates a shipped change**
(ship-or-not: "good / secure enough to ship?") — it runs once and returns a verdict. `/optimize`
**loops toward a measurable target** by bounded experiment ("drive this metric toward a target?") —
it iterates until the target is hit or the budget is spent. Route a ship/no-ship question to `/qa`;
route a "make this metric better" question to `/optimize`.

---

## Routing gates

- **Doc-review readiness (HARD).** Routing to `/work` from a plan is blocked when `/doc-review`
  reported unresolved **P0 or P1** findings. Override only with a recorded rationale. The target
  `/doc-review` is shipped, so the gate has a real engine. This is the **only** hard gate `/loop`
  enforces at routing time.
- **Hard test gate (carried).** `requires_hard_test_gate` change kinds
  (behavior / security / infra / api / deployment / data) and the issue flags
  (`has_security` / `has_infra` / `has_api`) are carried into the `/work` route as a constraint;
  `/work` enforces the block in its own Phase 3. `/loop` surfaces it; it does not run tests.
- **Review triggers.** Code at the work->PR boundary -> `/code-review`; a scope / ambition question ->
  `/founder-review`; a plan needing readiness -> `/doc-review`.

---

## Destination class (the routing horizon)

The destination (normalized via `lifecycle_state.py normalize`) sets how far `/loop` routes:

| Destination | Horizon |
|---|---|
| `plan-only` | stop at a written, reviewed plan (`/plan` -> `/doc-review`) |
| `pr` | run through `/work` to an open PR |
| `merge` | add `/work`'s confirmed merge of the PR |
| `nonprod-deploy` | after merge, hand `deploy` (`/loop` records the intent; deploy mutation belongs to `deploy`) |
