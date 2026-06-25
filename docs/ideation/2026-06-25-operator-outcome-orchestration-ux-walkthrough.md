---
date: 2026-06-25
topic: operator-outcome-orchestration-ux-walkthrough
kind: ux-walkthrough (illustrative)
repo: infiquetra-claude-plugins
maturity: illustrative
---

# Operator UX Walkthrough — Outcome Orchestration

Illustrative companion to
[`2026-06-25-operator-outcome-orchestration-ideation.md`](./2026-06-25-operator-outcome-orchestration-ideation.md).
Command names, output, and numbers are **placeholders** for `/brainstorm` to settle — this exists to
*feel* the operator experience of the reframed design (an in-saga `OutcomeOrchestrator` that owns a
DAG of leaf sagas; leaves execute and report completion back as ticks).

## The picture

```
   you ──/outcome──▶  ┌──────────────────────────────────────────────┐
                      │        OutcomeOrchestrator  (coordinator)     │
                      │   owns: the DAG · locks · attention routing   │
                      │   reuses: execution_spec Kahn/DAG · recommender│
                      └───────────────┬──────────────────────────────┘
                                      │  owns a DAG of …
            ┌───────────────┬─────────┴────────┬─────────────────┐
            ▼               ▼                  ▼                 ▼
      ┌───────────┐   ┌───────────┐      ┌───────────┐    ┌─────────────┐
      │ subplot A │   │ subplot B │      │ subplot C │    │  subplot D  │ ← leaf SAGAS
      │  (saga)   │   │  (saga)   │      │  (saga)   │    │(sub-outcome)│   strictly linear
      └─────┬─────┘   └─────┬─────┘      └─────┬─────┘    └──────┬──────┘   plan→work→qa
         executor        executor           executor        (its own DAG)
            ▼               ▼                  ▼
       [ workflow ]     [ inline ]        [ team-exec ]
```

The coordinator never executes — it routes. Leaves run wherever (often other sessions) and report
completion **as per-saga ticks** (never the racy `state.json`), which unlocks the next layer.

## Small scale — the machinery is invisible

```
$ /work fix the flaky timezone test in billing
  saga ▸ tiny outcome, 1 leaf — no orchestration needed
  backend: inline (1 file · low risk)
  ✓ done · test green · PR #412 · ~3k tokens
```

A "task" is a one-leaf outcome. Same engine, no visible DAG — the self-similar *experience* we kept.

## Epic scale — ① start: it drafts, you prune

```
$ /outcome new "Migrate platform from API-keys to OAuth2"
  drafting the DAG (you prune — you don't author 7 nodes by hand)…

  OUTCOME  oauth2-migration                          (entry altitude: epic)
  ├─ 1  shared-auth-sdk         deps: —         ~M   fork          (shares your ctx)
  ├─ 2  identity-service        deps: 1         ~L   team-exec   ⚑ gated
  ├─ 3  gateway-service         deps: 1         ~L   cc-workflows
  ├─ 4  billing-service         deps: 1         ~M   cc-workflows
  ├─ 5  integration-tests       deps: 2,3,4     ~M   workflow
  ├─ 6  docs + migration-guide  deps: 2,3,4     ~S   inline
  └─ 7  nonprod rollout         deps: 5,6       ~S   deploy      ⚑ gated

  7 subplots · 3 layers · est. ~480k tokens · ~2 stops that need you
  prune/edit?  ▸ drop 6; split 4 into 4a/4b
```

Backend per node is **recommended, not chosen by you** — you only override. The ⚑ gated nodes are the
only ones that stop for sign-off.

## Epic scale — ② run: healthy looks like silence

```
$ /outcome next
  layer 1 → ▸ subplot 1 (sdk) → fork
  ✓ subplot 1 done (tick ← session 'sdk-lane') · PR #418
  layer 2 unlocked → dispatching 3 in parallel:
     ▸ 2 identity → team-exec  ⚑ will stop for you
     ▸ 3 gateway  → cc-workflows  (autonomous)
     ▸ 4a metering→ cc-workflows  (autonomous)
  surface: quiet · 3 in flight · 0 need you      ← empty = healthy
```

## Epic scale — ③ when things need you: ONE consolidated pane

```
  ⚑ 2 things need you   (aggregated — not 3 tmux panes screaming)
  [1] subplot 2 identity · GATED
      team-exec consensus 9.2/10 · ready to open PR #421
      → approve? (y / view diff / hold)
  [2] subplot 4a metering · BLOCKED
      ambiguous: "per-seat or per-event?" — your call
      sibling 3 still running · 4b waits on this
      → answer, or park 4a and let 3 finish?
  ▸ _
```

The cognitive-load win (#16): concurrent blocks bubble up into one ranked prompt with context.

## ④ Cold re-entry after a long break

```
# 5 days later · fresh session · you forgot everything
$ /outcome resume oauth2-migration
  reconstructed from saga ticks (nothing lost):
  where:  layer 3 of 3 · 85% · last active 5d ago
  done:   sdk, identity, gateway, metering, invoicing, tests ✓
  left:   7 nonprod rollout (gated — waits on you)
  why paused: you stopped after tests went green, before rollout sign-off
  trail:  metering → per-event (your call, day 2) · tests caught 1 regression, fixed #429
  ▸ next: /outcome next → opens the gated rollout
```

Replays **where + what + why** (the decision trail) from durable per-saga ticks — a 5-day gap costs
nothing.

## ⑤ What's there when it's done

```
$ /outcome report oauth2-migration              (state: COMPLETE)
  ✓ COMPLETE · 4 days · ~520k tokens
  delivered:   7/7 · 6 PRs merged · nonprod deployed (tag v2.0.0-nonprod)
  evidence:    each subplot → PR · CI run · review score · qa artifact
  cost rollup: fork 12k · inline 28k · team-exec 140k · workflows 290k
               → biggest spend: gateway+billing workflows (as expected)
  decisions:   per-event metering · docs subplot pruned (you)
  full trail → docs/outcomes/oauth2-migration-report.md   (regenerated, never hand-edited)
  vs hand-managed inline: ~4 days operator-time → est. ~2 weeks
```

Per-subplot **evidence** (PR/CI/review/qa), the realized **cost rollup** (#10, the cost thesis
measured), the **decision trail**, and the durable digest.

## Through-line & open questions

One set of verbs at any altitude — `/work` a task (1-leaf, invisible) ↔ `/outcome` an epic (full
coordinator). `/brainstorm` still settles: the exact `/outcome` verb surface, the digest format, the
consolidator's ranking, the failure-cascade policy (#15), and **where the outcome state is stored so
it survives multiple sessions / worktrees / machines** (the session-independent store — see the brief
#8/#14).
