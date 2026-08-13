# Requirements: `orchestrate` — Codex phase

- **status:** requirements, pre-plan
- **date:** 2026-08-12
- **companion to:** [`2026-08-12-orchestrate-requirements.md`](2026-08-12-orchestrate-requirements.md)
- **target repository:** `infiquetra/infiquetra-codex-plugins` (read at `origin/main` `0383f82`,
  working tree current, 0 commits behind)

---

## 1. The requirement in one sentence

> *"I want to be able to start an orchestration with Claude and come back to it with Codex."*

Both runtimes drive the **same substrate** — the `agent` wrapper and `herdr` — so the sessions,
tabs, and panes are identical either way. What differs is the plugin that decides *what, when, and
how*. Interchangeability therefore reduces to one thing: **both runtimes must read and write the
same register with the same meaning.**

```
        ┌────────────────┐              ┌────────────────┐
        │  CLAUDE CODE   │              │     CODEX      │
        │  /orchestrate  │              │  orchestrate   │
        │                │              │    (skill)     │
        └───────┬────────┘              └───────┬────────┘
                │                               │
                │      the handoff seam         │
                └──────────►  register  ◄───────┘
                            (repo file)
                                 │
                ┌────────────────┴────────────────┐
                │   agent wrapper  +  herdr       │  identical for both
                └─────────────────────────────────┘
                                 │
                      children on any vendor
```

Everything below is either "make the seam work" or "account for a difference between the two
plugin repositories."

---

## 2. What already exists on the Codex side — and changes the Claude design

Surveying `infiquetra-codex-plugins` found three components that **replace requirements from the
companion document rather than duplicating them.** All are in `plugins/fleet-core/`.

### 2.1 `lease_broker.py` — evaluated and NOT adopted

> **Outcome: rejected.** This section is retained because the reasoning is worth keeping. The
> lease model below is genuinely well built, and it is the wrong fit here for one specific reason
> established by adversarial review — its expiry is **same-boot monotonic** and its lock is
> **per-host**, which is incompatible with C1's cross-machine handoff. See C5/C6 for what replaced
> it: a plain atomic write, with liveness from herdr events instead. `concurrency_policy.py`
> (§2.2) is still adopted; only the lease half is dropped.

Its own docstring:

> *Lease-backed fleet admission and fencing authority. The registry is a small, closed JSON
> document. Every mutation holds a stable sibling `flock` across read, validation, decision, and
> atomic replacement. Expiry is always derived from the same-boot monotonic renewal timestamp; no
> mutable status or expiry bit is stored.*

That is precisely what a cross-runtime register needs and it is already built:

| register need | what the lease broker already provides |
|---|---|
| two runtimes touching one file | `flock` held across read → validate → decide → atomic replace |
| crash safety | expiry derived from monotonic renewal, **not** a stored status bit |
| bounded concurrency | "admission and fencing authority" — admission control is the same problem as a WIP cap |
| a dead orchestrator's children | lease expiry, rather than a stale `running` flag nobody clears |

The last row matters more than it looks. The companion document's R23 (expected vs. observed
state) exists because a watcher without a record of intent alarms on every successful cleanup. A
lease answers that natively: a lease that is *released* is a clean exit, a lease that *expires* is
an abandonment. **The distinction is in the data structure rather than in a convention.**

### 2.2 `concurrency_policy.py` — fleet-wide, already cross-runtime

> *Fleet-wide serialized admission limits **shared by every runtime**. Saga owns resolution
> precedence. This module owns only the normalized defaults and the closed value that the lease
> broker records and enforces after resolution.*

"Shared by every runtime" is the interop property this phase needs, already stated as that
module's purpose. R31 in the companion document (bounded, declared work in progress) should be
satisfied by this rather than by anything new.

### 2.3 `models.json` — the cross-vendor mapping already exists, and is better than what I proposed

```json
"lineage_models": {
  "fable":  {"rank": 0, "effort_ceiling": "xhigh", "codex_model": "gpt-5.5", "codex_effort": "xhigh"},
  "opus":   {"rank": 1, "effort_ceiling": "xhigh", "codex_model": "gpt-5.5", "codex_effort": "high"},
  "sonnet": {"rank": 2, "effort_ceiling": "xhigh", "codex_model": "gpt-5.4", "codex_effort": "medium"}
}
```

The companion document's R25 proposed *extending the palette with per-vendor entries*. **That is
the wrong shape and this is the right one.** The four-tier lineage name is an *abstraction*; each
runtime resolves it to its own concrete model and effort. Adding Qwen, Gemini, or DeepSeek means
adding a resolution mapping, not new palette members — so the work-shape → tier policy stays
vendor-neutral and never has to be rewritten when a vendor is added.

It also carries `root_orchestration_profiles`, which is the orchestrator's *own* model profile:

```json
"root": { "preferred_model": "gpt-5.6-sol", "fallback_models": ["gpt-5.6-terra"],
          "default_effort": "max",
          "ultra": { "requires_explicit_selection": true,
                     "requires_independent_fanout": true, "leaf_allowed": false } }
```

**Known drift, flagged not fixed:** `lineage_models` maps to `gpt-5.5` / `gpt-5.4` while
`root_orchestration_profiles` names `gpt-5.6-sol` / `gpt-5.6-terra`. One of the two is stale.
Reconciling it is a prerequisite for trusting tier resolution on the Codex side, and it is
independent work.

---

## 3. Structural differences between the two repositories

| | `infiquetra-claude-plugins` | `infiquetra-codex-plugins` |
|---|---|---|
| manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| **command surface** | `commands/*.md` **and** `skills/` | **skills only** (`"skills": "./skills/"`) |
| plugin count | 12 | 11 |
| saga version | `0.131.1` | `0.83.0+codex.20260811103502` |
| workflow backend | `team-execution`, `cc-workflows-ultracode` | `verified-workflows`; **rejects** `cc-workflows-ultracode` |
| `/outcome` | 10 scripts | 17 scripts — **fully ported** |
| `fleet-core` extras | `intent_envelope`, `cost_weights`, `effort_rider`, `delegation_*`, `liveness_engine` | `lease_broker`, `concurrency_policy`, `codex_model_catalog`, `models.json`, `tier_palette`, `retry_backoff`, `orphan_evidence`, `workflow_compat` |

**The two `fleet-core`s have diverged.** Neither is a subset of the other. This is the single
largest risk in the Codex phase: `orchestrate` needs `IntentEnvelope` (Claude-only) *and*
`lease_broker` (Codex-only), and today neither repository has both.

---

## 4. Requirements

### A. The register is the handoff seam

- **C1.** The register is a **file in the target repository**, not session-local state. Rationale
  from the operator: provenance, and the ability to resume from a different runtime or machine.
- **C2.** The register carries an explicit **`schema_version`**. Both runtimes validate it before
  reading or writing.
- **C3.** A runtime encountering a `schema_version` it does not support **halts with a
  compatibility receipt** and changes nothing. It never best-effort parses, and never silently
  drops fields. This is the `outcome-cross-runtime` compatibility-halt pattern, which is proven and
  should be reused rather than re-derived.
- **C4.** A runtime **preserves fields it does not understand** on write. A Claude-side write must
  not silently delete a Codex-written key, or the handoff is lossy in one direction only — the
  failure mode that shows up as "it worked when I started it and lost data when I came back."
- **C5.** Register mutation is a **plain atomic write** — write a temporary file, rename over the
  target. A local advisory lock is acceptable within one host; nothing more is required.

  > **Revised — leases and fencing are cut.** Both reviewers independently found that
  > `lease_broker`'s expiry derives from *same-boot monotonic* renewal and its `flock` is
  > *per-host*, so C1's cross-machine handoff and lease fencing are **mutually exclusive as
  > originally specified**: resume on a second machine and every correctly-running child appears
  > expired and gets reaped as failed. One reviewer added that the lock protects the wrong thing
  > anyway — launch, prompt, and reap are external side effects on herdr tabs, which no
  > register lock covers. Git is the cross-machine serializer; concurrent orchestrators are not a
  > real condition for a single operator, and fencing can be added if one ever appears.

- **C6.** Child liveness comes from **herdr events**, not from a lease and not from a status field.
  The orchestrator subscribes to `pane.output_matched`, `pane_exited`, and `tab_closed` for the
  panes it owns (companion §4.2). A `tab_closed` for a child the register expected to be running is
  the divergence that raises an alarm; a `tab_closed` for one the register recorded as reaped is a
  confirmation.

  This also makes the wake mechanism **runtime-neutral**, which is what the handoff actually needs:
  Claude and Codex subscribe to the same socket with the same request, so neither runtime needs a
  background-task feature of its own.

### B. Component placement

- **C7.** Components needed by both runtimes live in **`fleet-core` on both sides**, with the
  same module name and the same behaviour. Concretely this means porting `IntentEnvelope`
  Claude→Codex, and `lease_broker` + `concurrency_policy` + `models.json` Codex→Claude.
- **C8.** Divergence between the two `fleet-core`s is a **known defect to be closed**, not an
  accepted condition. Where behaviour must differ, it differs by data (a mapping entry), never by
  a forked implementation.
- **C9.** The **work-shape → tier policy stays vendor-neutral**. Vendors are added by extending
  `lineage_models` resolution, never by adding vendor names to the tier vocabulary.

### C. Surface parity

- **C10.** Claude exposes `/orchestrate` as a command; Codex exposes it as a **skill**, since the
  Codex plugin format has no `commands/` directory. Behaviour is identical; only the invocation
  surface differs.
- **C11.** Both runtimes accept the **same outcome argument forms** — issue number, parent issue,
  requirements document, prose prompt.
- **C12.** `/outcome` deprecation (companion R2, R3) applies to **both repositories**. The Codex
  side carries the larger implementation, at 17 scripts, so the deprecation is not a Claude-only
  edit.
- **C13.** Backend permissions are **per-runtime data, not branching logic**. Codex rejects
  `cc-workflows-ultracode`; that belongs in `backends_permitted`, which already exists and is
  already read at dispatch.

### D. Interop acceptance

- **C14.** The phase is accepted by a **live round-trip**: start an orchestration under one
  runtime, launch at least one child, hand off, and have the other runtime resume it, observe the
  running child, and reap it correctly. Nothing less demonstrates the requirement, since every
  interesting failure is in the seam.
- **C15.** The round-trip is run **in both directions**. C4's lossy-write failure is directional
  and a single-direction test would miss it.

---

## 5. Operating constraint for the build

When Claude Code works inside `infiquetra-codex-plugins`, that repository's `plugins/` directory is
**the artifact under repair, not session tooling.** Its `saga.py`, validators, and renderers must
never be invoked to drive the session; the installed Claude saga is the tooling, with state under
`.claude/saga/`. This has previously produced confidently wrong conclusions and is a hard boundary
rather than a style preference.

---

## 6. Open

1. **Which repository hosts the shared components?** `fleet-core` exists in both and has diverged.
   Options: sync both by hand, make one canonical and vendor it, or extract a shared upstream. The
   operator's aside — *"if only there was a common plugin framework they all used"* — is the real
   problem underneath, and it is bigger than this build.
2. **`lineage_models` staleness.** The `gpt-5.5` / `gpt-5.6-sol` mismatch must be resolved before
   tier resolution can be trusted on the Codex side.
3. **Register location within the repo.** Alongside saga state under `.claude/` and `.codex/`
   would fork it by runtime, which defeats the purpose; a runtime-neutral path is needed.
4. **Hermes and Antigravity.** Both have plugin repositories on the same lifecycle. This document
   covers Codex only, per the operator's current scope.
