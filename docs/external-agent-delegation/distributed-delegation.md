# Distributed delegation — independent agents, independent identities

**Status: forward-looking design (n=0 — NOT yet run).** Every claim here is design-by-principle, not
evidence. The sibling [`blueprint.md`](blueprint.md) is grounded in a real n=1 dogfood; **this document
is not** — it takes a topology we have not dogfooded and reasons about it from the human-shop analogy
and from what the platform already enforces. Treat each section as a hypothesis to validate, and do not
cite it as proven the way the blueprint can be cited.

**Audience:** the same as the blueprint — a fresh agent (any model) asked to make external-agent
delegation safe *and* valuable — but under a different, stronger assumption about how the agents are
deployed.

---

## 0. The one assumption that changes everything

The [`blueprint.md`](blueprint.md) assumes **one desk**: the orchestrator and the delegate share a
machine, a working directory, and — load-bearing — the **same GitHub credential**. Every hard mechanism
in it (disposable clone, `remote remove origin`, the `git` PATH-shim, harvest-via-`git diff <BASE>`)
exists *only* to rebuild, by hand and locally, a boundary the platform does not enforce between two
processes sharing one login.

This document assumes the opposite:

> **N agents, each with its OWN workspace, its OWN GitHub identity, and its OWN authentications,
> operating independently.**

That single change moves the containment boundary from the **filesystem** (which you must *build*) to
**identity** (which the platform *already enforces*). The consequence is a clean trade:

```
                         CO-LOCATED (blueprint.md)        DISTRIBUTED (this doc)
   Boundary             filesystem (you build it)         identity (platform enforces it)
   "can't push to main" clone with origin removed         bot lacks write to protected main
   FS "house key" gap   OPEN (clone confines repo only)   CLOSED (each agent its own box/user)
   Credential blast     shared token = everyone's risk    per-identity, contained
   Containment effort   HIGH (local jail machinery)        LOW (branch protection + forks)
   Coordination effort  LOW (shared directory)             HIGH (integrate N divergent branches)
   Mental model         lead + junior at one desk          maintainer + untrusted fork contributors
```

Containment gets **easier**; coordination gets **harder**. The blueprint solves a hard containment
problem and a trivial coordination problem. This topology inverts both.

---

## 1. What gets EASIER (and why)

- **Identity is the boundary, enforced server-side.** "The junior cannot push to `main`" stops being a
  removable local trick and becomes a real GitHub permission: the bot identity has write only to its own
  fork or branch namespace, never to protected `main`. Branch protection, `CODEOWNERS`, required
  reviews, and fork-isolated Actions secrets all become available — none of which a local clone-jail can
  provide.
- **The FS "key to your house" gap closes for free.** Each agent runs on its own box / container /
  user, so it physically cannot reach another agent's filesystem, another's `~/.claude`, or a sibling
  repo. The human-shop analogy becomes *literally* true: each junior is on their own laptop. The
  blueprint's unsolved §3 filesystem-confinement problem simply does not exist here.
- **Credential blast radius shrinks to one agent.** Under shared auth (today) a single leaked or
  misused token is *everyone's* blast radius. Independent, least-privilege identities contain a
  wander/compromise to that one agent's scope.
- **Real provenance and rate-limiting.** Each commit is authored by a distinct identity → a genuine
  audit trail, attributable PRs, per-bot rate limits, and `CODEOWNERS`-routable review.

---

## 2. What gets HARDER (and why) — the new problem set

- **Integration becomes first-class.** N independent workspaces produce N divergent branches that must
  be *integrated* — ordering, conflict resolution, a who-builds-what frontier, stale-base rebases. The
  orchestrator's job shifts from *process supervisor* to **merge-queue maintainer + frontier scheduler**.
  This is where the existing `OutcomeOrchestrator` DAG and the dependency-wave / worker-segment thinking
  become load-bearing: they partition the write-sets so N agents do not collide.
- **No shared filesystem → artifacts move through git.** You cannot read the delegate's working tree;
  work passes between agents as **PRs, branches, published packages, or an artifact store**. Every
  hand-off is a published contribution, not a directory read.
- **Credential lifecycle at scale.** Provisioning, scoping, rotating, and revoking N bot identities and
  their tokens is now real operational work. The principle: each delegate gets **least-privilege** creds
  (write to its own fork only); the maintainer/orchestrator holds **none of the delegates' creds** — it
  reviews and merges under its own identity.
- **Coordination overhead and consistency.** Distributed state, eventual consistency, duplicated effort,
  merge-conflict storms when agents touch overlapping files. Rebase discipline and a merge queue stop
  being nice-to-haves.

---

## 3. The reference model: open-source maintainer, not lead-at-one-desk

The right mental model flips. Co-located delegation is *lead + junior sharing a desk* — you supervise a
process you can watch. Distributed delegation is **maintainer + untrusted fork contributors** — you
review contributions from identities you do not control, using a boundary GitHub already hardened for
untrusted contribution. Reuse it rather than rebuild a local jail:

- **Fork-based isolation beats branch-based.** A fork cannot read the upstream repo's Actions secrets;
  a same-repo branch can. For an untrusted delegate, fork > branch.
- **Required reviews + `CODEOWNERS` are the gate** — the server-side equivalent of "the lead cherry-picks
  only what was right."
- **A merge queue is the integration order** — it serializes N contributions and rebases each on the
  latest `main`, so the frontier advances without conflict storms.

---

## 4. The containment ladder, re-derived for this topology

Mapping the blueprint's four layers onto independent identities — note that **only Layer 1 changes
substance; Layers 2–4 are the same discipline applied at a different seam:**

| Layer | Co-located (blueprint) | Distributed (this doc) |
|---|---|---|
| **1 — Containment** | Disposable clone, `origin` removed, git-shim, OS sandbox for FS | **Platform identity + fork isolation + branch protection.** No local jail needed; the credential itself lacks the authority. |
| **2 — Validation floor** | Re-derive `git diff <BASE>`, run full gate, mutation-proof, sole committer | **Unchanged in principle** — re-derive the PR diff, run YOUR full CI under the maintainer identity, mutation-proof, merge yourself. Applied at the PR boundary, not a local harvest. |
| **3 — Process** | Wrapper script, background launch, escalation channels | **Merge-queue maintainer + DAG frontier scheduler** — dispatch ready work, harvest via PR, integrate in order. Escalation = a PR comment / issue, not a stdout channel. |
| **4 — Task packet** | Write-set, read-context, verify commands, run report | **Same packet**, plus per-agent identity + credential scope + the fork/branch it owns. |

The tell that Layer 2 is the irreducible core: it survives the topology change **untouched**. Whatever
else moves, *a delegate's self-report is never evidence; you re-derive and run your own gate before you
integrate.*

---

## 4a. The coordination substrate already exists (n=2 observation — co-located, not yet distributed)

The one piece of this topology that is **no longer purely n=0** is the *coordination primitive*. n=2
(#277, co-located) ran the delegate through the **`/agy:delegate` plugin, which spawns `agy:runner` as a
session teammate** — mailbox-addressable, idle-notifies on completion, reachable via `SendMessage`. That
is exactly the shape Layer 3 needs to scale to N agents: a *dispatch + await-idle + message-back*
primitive, rather than a stdout pipe.

So the layers thread together cleanly: **identity isolation is the containment layer; the
teammate/mailbox model is the coordination layer.** The distributed scheduler (merge-queue + DAG frontier,
§4 Layer 3) should be built **on** the teammate/mailbox/await-idle primitive — many delegate-teammates,
each identity-isolated, coordinated over one mailbox + a ready-frontier — rather than reinventing
coordination from scratch. This also lines up with the OutcomeOrchestrator's existing `ready_frontier`
DAG work in saga (`execution_spec.py`).

**Honesty marker:** the *primitive* has co-located evidence (n=2); the *distributed topology* that would
use it across independent identities is still **n=0**. This narrows what is unproven (cross-identity
coordination at scale) without overclaiming the topology itself.

---

## 5. What is the SAME (do not re-litigate)

- **Self-report is never evidence.** Re-derive every contribution; trust the diff and your own CI, not
  the agent's account of its work.
- **Specify-harder is still the regime-collapse trap** ([`blueprint.md`](blueprint.md) §2). Containment —
  now via identity — is what lets you give the delegate latitude safely; tighter prompts still trade away
  the value.
- **Read broad, write narrow, surface the rest** — now expressed as *fork-wide read, PR-scoped write,
  escalate via PR comment / issue* instead of silently editing or silently skipping.

---

## 6. Open questions and explicit assumptions (n=0 — be honest)

- **We have not run this.** There is no n=1 for the distributed topology. Everything above is reasoned
  from principle and from the platform's existing guarantees; none of it is dogfood-validated.
- **Cost vs payoff is unmeasured.** N credentialed identities + merge-queue coordination has real
  overhead; whether it beats co-located delegation depends on parallelism actually paying for the
  coordination tax — untested.
- **Latency.** Does fork → PR → review → merge latency kill the fast iteration loop that made local
  delegation quick? Possibly; measure it before committing.
- **Merge-conflict storms.** N agents on overlapping files need the DAG to partition write-sets up front
  (connects to capability #287 and the worker-segment derivation in `execution_spec.py`). Without that
  partition, integration could dominate.
- **Where this lives in-repo.** The co-located enforcement home is #287. The distributed model is a
  *different architecture* — likely its own exploration/capability, not a fold into #287. Decide when (if)
  we run it.

---

## 7. Other tradeoffs to map (non-exhaustive — seeds, not yet analyzed)

§2 named coordination first; it is **not** the only cost. These are seeds for a later pass, recorded so
the tradeoff set is honestly open rather than appearing closed:

- **Economics / lost cache locality.** Independent agents share no prompt cache and no warm workspace —
  each re-pays context *creation* every time (the creation-tax half of the worker-derivation cost model).
  Co-located delegation gets cache reuse almost for free; distributed discards it. The tax may swamp the
  parallelism.
- **Aggregate attack surface vs contained blast radius (a tension, not a win).** Per-agent containment
  improves, but N identities + N tokens = more to leak, rotate, and audit. Fleet-wide surface grows even
  as per-incident damage shrinks — book both, not just the upside.
- **Observability / debuggability collapses.** No single working tree to inspect; failures scatter across
  N boxes with partial state and eventual consistency, so "what state are we in?" gets expensive.
- **Provisioning friction.** Standing up an agent now needs an identity + scoped creds + a workspace + CI
  access, vs co-located "launch a process" (connects to the `team-scaffold` identity-provisioning pattern).
- **Latency vs isolation.** fork → PR → review → merge round-trips are slower per unit than a local
  harvest; you trade iteration speed for isolation.
- **Identity provenance / anti-impostor.** With truly independent identities, verifying a PR came from
  *your* agent (not an impostor) makes commit signing / provenance a real requirement, not an afterthought.

This list is itself non-exhaustive — there are almost certainly more.

---

## Provenance

Sparked by an operator observation (2026-06-28): the [`blueprint.md`](blueprint.md) assumes a shared
workspace and a shared GitHub credential; this document takes the independent-identity assumption
instead (N agents, own workspace, own creds, own auth). **Forward-looking, n=0** — it accumulates the
practice's thinking ahead of evidence, and must be validated (or invalidated) by a real distributed run
before any claim here is treated as settled.

**n=2 update (2026-06-29):** the *coordination primitive* (§4a) is no longer purely speculative — the
`/agy:delegate` teammate/mailbox/await-idle model has co-located evidence from #277. The *distributed
topology* remains n=0; what is now n=2 is only the in-session primitive it would be built on.
