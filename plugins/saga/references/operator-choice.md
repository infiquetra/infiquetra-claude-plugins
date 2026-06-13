# Operator-Choice Framework

**Status:** canonical contract · **plugin version:** 0.5.0
**Companion:** [`references/saga-spec.md`](./saga-spec.md) — the **STORAGE** contract for the chosen value.
**Audience:** every lifecycle command that runs work or routes work (`/loop`, `/work`, and the rest as they
rebuild) implements against this file when deciding *how* work executes.

This is the **DECISION contract** for choosing an execution backend in saga. Where
`saga-spec.md` says *how the choice is stored* (the `orchestration_mode` / `orchestration_ref` fields), this
document says *how the choice is made and offered*. Lifecycle owns the **CHOICE**, not the execution: it
recommends a backend, surfaces it, and records what the operator picked. The backends themselves do the
work.

> The CLI-backed execution-backend helper **shipped with the `/work` rebuild**: `recommend_execution_backend()`
> lives in [`scripts/lifecycle_state.py`](../scripts/lifecycle_state.py) (the `recommend-backend` subcommand).
> The prose offer hooks in `/loop` and `/work` cite this file; both call the helper (`/work` since 0.10.0,
> `/loop` since 0.11.0 — `/loop` offers a backend per decision point for `/loop`-owned work and writes the
> choice to the saga). This spec was settled as a doc-only foundation in 0.5.0 **before** consumers calcified
> against it, then the helper landed with `/work` and `/loop` became its second caller.

---

## 1. The three execution backends

There are exactly three backends. The recorded value is **EXACTLY one of** `inline | team-execution |
cc-workflows-ultracode` — these strings are the contract (they match `ORCHESTRATION_MODES` in
[`scripts/saga.py`](../scripts/saga.py) and §4 of `saga-spec.md`). Prose labels people say out loud
("CC workflows", "ultracode", "team mode") are **not** the contract; only the enum strings are.

| Backend (enum) | What it is | Owns execution? | Availability |
|---|---|---|---|
| `inline` | The agent does the work itself, single-context / serial. **The default.** | the agent | always |
| `team-execution` | The team-execution plugin: a `## Team Structure` plan section + worker / reviewer / validator agents with consensus + gates. | yes — team-execution owns its own run | plugin installed |
| `cc-workflows-ultracode` | The Claude Code **Workflow** tool: deterministic multi-agent orchestration (ultracode) — broad fan-out **and** independent/adversarial verification. | yes — the Workflow runtime owns its own run | **Claude Code only** (§4) |

**Ownership boundary.** Lifecycle **chooses**; the backends **execute**. `team-execution` and
`deploy` are **offered, not vendored** — lifecycle never reimplements their machinery, it points
to them and records the pointer. A saga holds the choice (`orchestration_mode`) and a pointer into the
backend (`orchestration_ref`); it is never the execution authority.

---

## 2. Who decides

The operator decides; lifecycle makes the cheapest-correct path one keystroke away.

- **inline by default.** Absent any escalation signal, work runs `inline`. No ceremony.
- **Auto-recommend the fitting backend.** Lifecycle reads the work shape (§3) and pre-selects the backend it
  judges best. This is a recommendation, not an imposition.
- **ALWAYS surface the choice.** Even when the recommendation is `inline`, the offer names the alternatives
  so escalation is **one step**. The pairing is *explicit default + cheap escalation*: the operator never
  has to know the backend names cold to reach for a heavier one.
- **Operator confirms or overrides.** The recorded value is whatever the operator picked, not what lifecycle
  guessed.

---

## 3. When to escalate (triggers)

### 3.1 `inline` -> `team-execution`

This mirrors `should_offer_team_execution` in
[`scripts/lifecycle_state.py`](../scripts/lifecycle_state.py) — **that function is the canonical trigger
source; keep these numbers — and the `has_code_surface` docs-gating below — identical to its constants.**
Offer `team-execution` when **ANY** of:

| Signal | Threshold |
|---|---|
| `file_count` | `>= 8` |
| `phase_count` | `>= 4` |
| `has_security` | true |
| `has_infra` | true |
| `cross_repo` | true |
| `deployment_sensitive` | true |

**OR** a needs-consensus signal: multiple reviewer lenses are warranted, a decision is contested, or
validator gates should bound the work. team-execution's whole value is *review consensus + gates*, so a job
that wants those is a team-execution job even if it is small — the consensus signal is **sufficient on its
own**, not an additive PLUS (this matches `recommend_execution_backend`, which ORs it in).

**Docs exception (`has_code_surface=False`).** team-execution's scanners + deploy gate are code-shaped and
inert on pure docs/spec/research output, so the **output-blind** rows above — `file_count`, `phase_count`,
`has_security`, `has_infra`, `deployment_sensitive` (the last two are `parse_issue.py` keyword matches that
fire on a doc merely *mentioning* terraform or auth) — are neutralized when the work has no code/ship
surface. Two rows survive because they signal governance, not code: **`cross_repo`** (crossing a repo =
crossing an ownership boundary = a multi-party coordination need) and the **needs-consensus** signal. A big
docs change with neither stays `inline`/ultracode, not team-execution.

### 3.2 `inline` -> `cc-workflows-ultracode` (Claude Code only)

Offer in **either** of two ungoverned-multiplicity modes, both without elevated risk:

- **Breadth / scale** — high-parallelism, broad independent fan-out (the same operation across many
  targets), or an exhaustive search-all / probe-all sweep where missing a target is the failure mode.
- **Adversarial confidence** (`adversarial_confidence`) — prove-by-refutation, a judge panel over N
  independent attempts, or perspective-diverse verifiers each applying a distinct lens. This is real review
  depth; the Workflow tool names *confidence* as a first-class purpose. Set it only on an **explicit**
  request for many-independent-attempt verification — not inferred from a generic "be more sure," and not
  when 1-3 lenses suffice (that is an `inline` / `team-execution` review, not an ultracode fan-out).

So ultracode is **not** "fan-out, not review depth" — it delivers deterministic fan-out **and** independent
adversarial verification. What it lacks is **governance**: no reviewer-CONSENSUS gate, no named scanner
registry, no guarded deploy. That — not "review depth" — is the line to `team-execution` (§3.1).

**The mechanical boundary** (artifact kind, not ceremony level): ultracode gives a *throwaway* confidence
signal on a finding you then act on yourself — N votes, the run ends, nothing is recorded or blocks.
team-execution gives a *standing* verdict — a consensus score that blocks downstream scanners and the deploy
and persists as evidence. Want independent cross-checking of a read-only finding → ultracode. Need the review
to gate a merge/deploy or be recorded → team-execution. (A job that is both risky **and** wide offers both —
§3.3.)

### 3.3 Overlap (both fire)

A large security audit is legitimately *both* risky **and** parallel — both triggers fire. When that
happens, **OFFER BOTH** and let the operator pick. List `team-execution` first (a mild risk-lean), but there
is **no hard precedence rule**: because the offer always confirms with the operator, any precedence would be
cosmetic. The operator resolves the overlap.

Recommended-default rule of thumb (which one to pre-select):

| Work shape | Lean |
|---|---|
| risky **and** parallel | `team-execution` |
| parallel **and** not risky | `cc-workflows-ultracode` |
| neither | `inline` |

---

## 4. Capability gate (`cc-workflows-ultracode` is Claude Code only)

This plugin runs on hosts **without** the Workflow tool (e.g. redis-channel sessions, other runners). Two
rules keep the contract honest across hosts:

- **Document all three backends ALWAYS.** This file is the full map; an off-host reader needs to understand
  `cc-workflows-ultracode` even though they cannot run it.
- **At the offer, prefer to omit `cc-workflows-ultracode` when the Workflow tool is observably absent in
  this session.** Don't offer a path the operator cannot take here.

**Regardless of the offer:** if `cc-workflows-ultracode` is chosen but turns out to be unavailable, **fall
back to `team-execution` or `inline` with a one-line note** rather than failing. This is the same
*attempt + graceful fallback* pattern `/ideate` and `/brainstorm` already use for `AskUserQuestion` (try the
rich path; degrade cleanly when it isn't there). `/loop`'s own phase-walk is the cross-host fallback when no
heavier backend is reachable.

---

## 5. How to offer (dual form)

The offer renders differently depending on the surface, because not every surface can call
`AskUserQuestion`:

- **Claude Code session** — use `AskUserQuestion` with the **recommended backend pre-selected** (§2, §3.3).
- **redis-channel session** — `AskUserQuestion` **cannot** be called; inline **lettered choices** in the
  reply text instead ("Which backend? A) inline … B) team-execution … C) cc-workflows-ultracode …"). Follow
  the canonical channel-inline convention documented in
  [`skills/brainstorm/SKILL.md`](../skills/brainstorm/SKILL.md) — **reference it; do not duplicate its
  wording here.** That doc is the single source for how channel-inline choices are phrased.

---

## 6. Recording the choice

**Durable home:** the saga envelope — `orchestration_mode` (the enum value, §1) plus `orchestration_ref` (a
pointer into the chosen backend). See [`references/saga-spec.md`](./saga-spec.md) for the storage contract
(field table §3.1, enum domain §4).

**Saga writers.** `/plan` (0.7.0), `/work` (0.10.0), and `/loop` (0.11.0) write sagas — they record the chosen
backend durably via the saga's `--orchestration-mode` field. `/loop` records the backend for **`/loop`-owned
work only**: in Drive mode it ticks the chosen backend onto the work-thread saga (the routing tick carries the
offload pointer only for `/loop`-owned offloads); when `/loop` *routes* to another command it does **not**
instruct or record that command's backend (each command owns its own backend decision — `/work`, e.g., writes
but never reads `orchestration_mode`). A command that does not yet write a saga records the backend
**NARRATIVELY**; it must not call `saga.save` until its rebuild wires it as a real consumer.

`orchestration_ref` by backend:

| `orchestration_mode` | `orchestration_ref` |
|---|---|
| `inline` | empty string `""` |
| `team-execution` | the team name |
| `cc-workflows-ultracode` | the workflow id |

---

## 7. Consumer contract (who cites this, when)

Each command cites this file at its own rebuild. The CLI-backed execution-backend helper
(`recommend_execution_backend()`) **shipped with the `/work` rebuild** (0.10.0); `/work` is its first caller.

| Command | Cites operator-choice |
|---|---|
| `/loop` | **now** (prose offer hook + saga writer for `/loop`-owned work + the CLI-backed `recommend_execution_backend()` helper, since 0.11.0) |
| `/work` | **now** (prose offer hook + the CLI-backed `recommend_execution_backend()` helper, shipped 0.10.0) |
| `/plan` | at its rebuild |
| `/resume` | at its rebuild |
| `/code-review` | at its rebuild |
| `/founder-review` | at its rebuild |
| `/qa` | at its rebuild |
| `/investigate` | **now** (saga read-only; offers a backend for large/parallel fixes + parallel hypothesis-probes, since 0.16.0) |
| `/retro` | at its rebuild |
| `/spec` | **never offers** — a single durable spec artifact; size/risk lives in its scope sections, and the downstream executor (/plan / /work) owns backend selection |
| `/optimize` | **now** — offers a backend for independent experiment fan-out (default serial inline); records the choice NARRATIVELY (saga-untouched); since 0.18.0 |
| `/doc-review` | at its rebuild |
| `/strategy` | **never offers** — a single durable doc, no parallelism to escalate |

---

## 8. References

- Storage contract (where the choice lives): [`references/saga-spec.md`](./saga-spec.md)
  (`orchestration_mode` / `orchestration_ref`, enum domain §4).
- Canonical team-execution trigger constants: [`scripts/lifecycle_state.py`](../scripts/lifecycle_state.py)
  (`should_offer_team_execution`).
- Channel-inline offer convention (do not duplicate): [`skills/brainstorm/SKILL.md`](../skills/brainstorm/SKILL.md).
- Decision record: [`docs/engineering-journal/DECISIONS.md`](../../../docs/engineering-journal/DECISIONS.md)
  `#operator-choice-framework`.
