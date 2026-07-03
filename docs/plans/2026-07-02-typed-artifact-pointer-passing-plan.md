---
title: Typed Artifact-Pointer Passing for team-execution
type: feat
status: active
date: 2026-07-02
origin: docs/brainstorms/2026-06-28-typed-artifact-pointer-passing-requirements.md
---

# Typed Artifact-Pointer Passing for team-execution

Implements infiquetra/infiquetra-claude-plugins#291: stop inlining large artifacts (diffs, changed
files, generated outputs) into spawned-agent prompts; pass a typed pointer (git object ref, or
path + hash + freshness) that the already-capable agent dereferences itself. Delivered as a
dependency-ordered stack: Layer 1 git-object diff pointers (no new storage), Layer 2 a
content-addressed store for non-git artifacts, Layer 3 light path+symbol pointers. v1 receivers
always dereference the **full** artifact — review invariance (issue R14) is preserved; per-lens
scoping stays deferred.

## Premise re-verification (2026-07-02)

The issue was written 2026-06-28. Five team-execution/saga-touching merges landed since (#277,
#278, evidence manifests, #318 external-engine workers, #287 capability sandbox). Every load-bearing
claim was re-checked against current `main` (b6bcf5c). All `file:line` citations in this plan are
**pinned to that pre-change snapshot** — U2 edits several of the cited files, so post-change line
numbers will differ by design; the U2 doc guards, not these citations, own the post-change state.

**Still true:**

- The B3a reviewer spawn inlines "git diff of all changes made" to every reviewer in parallel —
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:28` and the spawn
  template's "## Changes Made / [git diff or summary of files changed]" at
  `consensus-protocol.md:151-152`.
- Validators receive "Relevant changed files or diff summary" inline —
  `plugins/team-execution/skills/team-execution/references/validator-spawn-quirks.md:9-17`.
- Review happens against a **dirty working tree** — the orchestrator captures "changed files and a
  git diff summary for reviewers" after workers finish, before any commit
  (`plugins/team-execution/skills/team-execution/SKILL.md:325`).
- No team-execution agent declares a `tools:` frontmatter restriction (grep over
  `plugins/team-execution/agents/*.md`); `devils-advocate-reviewer.md:49` already instructs "Read
  the git diff or changed files" — receivers are capable of self-dereference today.
- Saga stores artifact paths nobody dereferences — `plugins/saga/scripts/saga.py:193-194`
  (`work_session_paths`, `review_paths`), serialized via `FRONTMATTER_FIELDS`
  (`saga.py:253-254`), written by `save` flags (`saga.py:1218-1219, 1280`).

**Drifted (plan adjusts for these):**

- "Sub-threshold reviewers are re-spawned fresh each cycle" is **reversed**. The residency protocol
  now forbids cold re-spawns: reviewers are persistent named teammates re-engaged via `SendMessage`
  (`consensus-protocol.md:53`), and the re-engagement template inlines a **delta-only** diff
  (`consensus-protocol.md:169-170`). The redundant-inlining cost therefore concentrates in the
  initial N-parallel B3a spawn plus the still-inlined delta on each re-engagement — the win is
  smaller than the issue implied but real: N ≥ 3 full-diff copies per run, plus deltas.
- `SKILL.md:297` → diff capture now lives at `SKILL.md:325` (Step B1 was rewritten for resident
  workers).
- Journal anchors moved: the no-back-edge rule is at `docs/engineering-journal/DECISIONS.md:529`
  (`{#saga-docs-source-model}` lineage); the dead-wiring rule is at
  `docs/engineering-journal/LEARNINGS.md:400` (`{#dead-wiring-needs-producer-and-consumer}`).
  Line numbers drift as the journal grows — the `{#slug}` anchors are the stable citation.

**New constraints that did not exist when the issue was written:**

- #287 capability sandbox: saga verify/review spawns use `saga:readonly-verifier` +
  `isolation: "worktree"` (linked worktrees, which **share** `.git/objects`). team-execution
  residents run unrestricted (authoring-time-unenforceable, DECISIONS
  `{#capability-sandbox-implementation}`).
- #318 external-engine workers: agy `sandboxed-mutate` units run in a **remotes-stripped disposable
  clone** (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:99-105`).
  A separate clone does **not** share the parent's `.git/objects` — git-object pointers are
  unresolvable there. This hardens issue R15 into KTD7 (degradation path).

## Requirements

Carried forward verbatim from #291 (R1–R15; stable IDs, do not renumber). Load-bearing ones for
implementation:

- R1. A pointer carries kind (`diff` | `file` | `symbol`), locator, integrity hash, freshness marker.
- R2. Receivers verify **both** hash and freshness before use; mismatch surfaces a typed error,
  never a silent review of wrong/stale bytes.
- R3. Pointerization is threshold-gated; small fixed context stays inline. Reviewers (full diff)
  and validators (diff summary) are configured separately.
- R4–R7. Layer 1: diff passed as a git object reference; receivers read the full diff; no new
  storage; re-engagement passes an updated reference.
- R8–R11. Layer 2: non-git artifacts written once to a bounded content-addressed store; accepted
  only via a real end-to-end producer → spawned-consumer path (dead-wiring bar,
  LEARNINGS `{#dead-wiring-needs-producer-and-consumer}`).
- R12–R13. Layer 3: light path+symbol form only; formal resolver deferred (feasibility probe under
  the spawned agent's tool profile would be required — not attempted in v1).
- R14. Pointerization never changes *what* is reviewed, only how bytes arrive.
- R15. Composition with worktree/clone isolation → resolved as KTD7.

## Key Technical Decisions

- **KTD1 — Q1 dirty-tree locator: temp-index tree snapshot + holding ref.** The Layer-1 locator is
  a git **tree object** built without touching the user's real index or working tree:
  `GIT_INDEX_FILE=<tmpfile> git add -A && git write-tree` (run with the temp index seeded from
  `HEAD` via `git read-tree`), yielding a tree OID that covers staged, unstaged, **and untracked**
  files. A holding ref `refs/team-execution/snapshots/<run-id>/<epoch>` pins it against `git gc`.
  The snapshot also records the **base tree OID** (`HEAD^{tree}` at snapshot time) inside the
  pointer, so the receiver's deref command is fully pinned — `git diff <base-tree> <snapshot-tree>`
  — and cannot drift if HEAD moves mid-run. *Empirically validated 2026-07-02 in a scratch repo:
  snapshot captured staged + unstaged + untracked; real index and worktree untouched; tree survived
  `git gc --prune=now` via the ref; deref succeeded from a linked worktree.*
  *Rejected:* `git stash create` (skips untracked; dangling object is GC-bait; `--include-untracked`
  is push/save-only — all three failure modes named in issue Q1); a checkpoint commit on the branch
  (mutates history the operator didn't ask for); routing diffs through the Layer-2 store (loses
  git's free content addressing and worktree sharing).
- **KTD2 — Integrity and freshness are two checks, one pointer.** Layer 1: integrity is the tree
  OID itself (git is content-addressed — no second hash); freshness is the epoch segment of the
  holding ref (`<run-id>/<epoch>`, epoch = consensus iteration), verified by asserting the ref still
  resolves to the OID. Layer 2: integrity is SHA-256 of the payload; freshness is the same
  `<run-id>/<epoch>` string in the pointer JSON; stale means a **newer epoch exists for the same
  run-id** in the store index (monotonic supersession, matching L1's ref-moved semantics).
  Verification failure exits non-zero with a typed error code (`POINTER_HASH_MISMATCH`,
  `POINTER_STALE`) the orchestrator can branch on (covers R2, AE2).
- **KTD3 — Pointer serialization: one fenced JSON block in the spawn prompt.** A pointer travels as
  a single fenced code block labelled `artifact-pointer` containing one JSON object
  (`{"kind": "diff", "locator": "...", "hash": "...", "epoch": "...", "deref": "<command>"}`).
  Machine-parseable, human-readable, and carries its own dereference command so a receiving agent
  needs zero prior knowledge. *Rejected:* bare prose instructions (unparseable, drift-prone);
  a sidecar file per spawn (adds a read hop before the read hop).
- **KTD4 — Threshold: pointerize at > 4 KB, or > 1 KB with ≥ 2 recipients; ≤ 1 KB always stays
  inline (KD3's false-economy boundary made numeric).** A dereference costs the receiver one tool
  round-trip (~100 tokens); a 4 KB artifact is ~1 000 tokens, and the B3a fan-out always has ≥ 3
  reviewer recipients, so multi-recipient artifacts earn pointerization at a quarter of the solo
  threshold — but a sub-1 KB payload never does, no matter the fan-out (the round-trips would cost
  more than the copies). Plan summary, intended outcome, and `review-criteria.md` path stay inline
  always. Reviewers (full diff) and validators (summary) are evaluated against the threshold
  independently (R3).
- **KTD5 — Saga envelope: one new list field `artifact_pointers`, shipped live on both axes.**
  Extends the existing artifact-pointer block (`saga.py:192-195`) rather than inventing parallel
  storage (issue KD5, DECISIONS.md:529 no-back-edge rule). Per the dead-wiring rule
  (LEARNINGS.md:400) the field ships with all three legs in one unit: producer
  (`--artifact-pointers` save flag + `_build_save_saga` assignment + SKILL instruction), consumer
  (team-execution spawn context instructs dereference), and an end-to-end test driving the real
  `saga.py save` entrypoint — never a fixture that fabricates on-disk shape.
- **KTD6 — Script home: `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`,
  standalone.** team-execution is the consumer, so the mechanics live there (repo CLI-plugin
  convention: `skills/<skill>/scripts/`). The script imports nothing from saga (no back-edge);
  saga.py gains only the passive envelope field (block at `saga.py:192-195`). Python 3.12,
  mypy-clean (CI scans `plugins/`), stdlib-only.
- **KTD7 — Degradation path is capability-keyed, not agent-keyed.** Git-object pointers resolve for
  same-cwd resident teammates and linked-worktree children (shared `.git/objects`); they do **not**
  resolve inside external-engine disposable clones (`external-engine-workers.md:99-105`) or any
  future tool-restricted agent. Spawn templates state the rule: if the receiver cannot run
  `git cat-file` against the parent repo, the orchestrator falls back to inlined content (issue
  KD6). External-engine worker dispatch is untouched by this plan.

## High-Level Technical Design

One small CLI, four subcommands, wired into prose templates:

```
artifact_pointer.py snapshot --run <id> --epoch <n>      → Layer-1 pointer JSON (tree OID + ref)
artifact_pointer.py store    --run <id> --epoch <n> FILE → Layer-2 pointer JSON (CAS path + sha256)
artifact_pointer.py deref    '<pointer-json>'            → verified content on stdout, or typed error
artifact_pointer.py gc       --max-age-days N            → reclaim snapshot refs + stale CAS entries
```

The orchestrator (SKILL.md Step B1) calls `snapshot` once per review epoch and embeds the pointer
block in each B3a spawn / B3e re-engagement instead of the inlined diff. Receivers run `deref`
(or the embedded raw `git diff` command) and verify per R2. The Layer-2 store lives beside existing
run-state at `.claude/team-execution/artifacts/<sha256[:2]>/<sha256>` and inherits Step B0a's
ignored-directory safety check (SKILL.md already gates `.claude/` state on gitignore, with the
`~/.claude/team-execution/state/<repo>/` fallback).

## Implementation Units

### U1 — Pointer contract + Layer 1 snapshot mechanics

**Delivers:** `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` with the
pointer dataclass (kind/locator/hash/epoch/deref), JSON round-trip, `snapshot` (KTD1 temp-index
write-tree + holding ref), `deref`, and typed verification errors (KTD2). Covers R1, R2, R4, R6.

**Bandit convention (follow, don't invent):** git calls use the established saga-script pattern —
`import subprocess  # nosec B404 — git only, fixed argv, no shell` on the import and
`# nosec B603` (plus `B607` for unqualified `git`) per `subprocess.run` call with the same
justification, and the runner resolved at call time (not bound as a default arg) so tests can
monkeypatch it — precedent at `plugins/saga/scripts/outcome_github.py:21,40` and
`outcome_store.py:41`.

**Depends on:** nothing.

**Files:** `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` (new),
`tests/test_team_execution_pointers.py` (new).

**Test scenarios** (`tests/test_team_execution_pointers.py`, real git repos via `tmp_path` fixtures):

- contract: construct → serialize → parse round-trips all four fields for kinds `diff`/`file`/`symbol`.
- snapshot captures staged + unstaged + **untracked** files in the tree OID; real index and
  worktree are byte-identical before/after (the KTD1 no-mutation guarantee).
- snapshot ref survives `git gc --prune=now` (retention, issue Q1).
- deref of a valid pointer emits the full diff; verify: byte-drift (rewrite tree, keep pointer) →
  `POINTER_HASH_MISMATCH`; moved ref with valid hash (stale epoch) → `POINTER_STALE`; both non-zero
  exit, typed error on stderr.
- deref resolves from a **linked worktree** of the same repo (KTD7 positive case).

### U2 — Layer 1 wiring: spawn templates pass pointers, receivers dereference

**Delivers:** prose/template changes making the pointer the default above threshold (KTD4).
Covers R3, R5, R7, R14.

**Depends on:** U1.

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md` (Step B1 capture at :325 →
snapshot + pointer), `references/consensus-protocol.md` (B3a template :140-157 and B3e delta
template :160-175 carry an `artifact-pointer` block, not an inlined diff, above threshold; delta
epochs increment), `references/validator-spawn-quirks.md` (context package line :9-17),
`references/artifact-pointers.md` (new — receiver contract: dereference, verify hash + freshness,
read the FULL artifact in v1, KTD7 fallback rule), `agents/devils-advocate-reviewer.md`,
`agents/security-reviewer.md`, `agents/architecture-reviewer.md` (each base reviewer gains a
pointer-dereference line referencing the receiver contract; only devils-advocate `:49` and
architecture `:66` have explicit diff-read lines today — security-reviewer gets the reference
added, not edited). Validator diff summaries above threshold reuse the **same Layer-1 tree
pointer** with a `git diff --stat <base-tree> <snapshot-tree>` deref command — no Layer-2
dependency, keeping U2 self-contained.

**Test scenarios** (`tests/test_team_execution_pointers.py`, doc-guard style matching
`tests/test_team_execution_plugin.py`):

- spawn_template: consensus-protocol B3a template contains an `artifact-pointer` fenced block and
  no longer mandates an inlined full-diff body; re-engagement template passes an updated pointer.
- `artifact-pointers.md` is packaged, linked from SKILL.md, and states full-dereference (R5/R14)
  and the KTD7 fallback verbatim guard phrases.
- threshold rule (4 KB / ≥ 2 recipients) is stated once in SKILL.md and referenced, not duplicated.

### U3 — Layer 2 content-addressed store

**Delivers:** `store` + `gc` subcommands: write-once CAS at
`.claude/team-execution/artifacts/` (B0a-gated, `~/.claude/team-execution/state/<repo>/artifacts`
fallback), sha256 integrity, epoch freshness sidecar, TTL reclamation (default 7 days — bounded per
R9). Covers R8, R9, R10.

**Depends on:** U1 (pointer contract).

**Files:** `artifact_pointer.py` (extend), `tests/test_team_execution_pointers.py` (extend).

**Test scenarios:**

- store is write-once: same bytes → same path, no duplicate; different bytes → different path.
- deref verifies sha256 and epoch; tampered file → `POINTER_HASH_MISMATCH`; superseded epoch →
  `POINTER_STALE`.
- gc reclaims entries older than TTL and prunes their snapshot refs; younger entries survive.

### U4 — Saga envelope extension + R11 end-to-end proof

**Delivers:** the KTD5 field, live on both axes: `artifact_pointers` on the `Saga` dataclass +
`FRONTMATTER_FIELDS` (beside `review_paths`, `saga.py:192-195/253-254/274-275`),
`--artifact-pointers` on the `save` subparser + `_build_save_saga` assignment (beside
`--review-paths`, `saga.py:1218-1219/1280`), and the layer2_end_to_end test. Covers R11,
issue KD5.

**Depends on:** U3.

**Files:** `plugins/saga/scripts/saga.py`, `plugins/saga/skills/work/SKILL.md` (producer
instruction: record pointers on save), `tests/test_team_execution_pointers.py`.

**Test scenarios:**

- layer2_end_to_end: drive the REAL entrypoints in subprocesses — `artifact_pointer.py store` as
  producer, then `saga.py save --artifact-pointers` records the pointer. The consumer leg replays
  the actual spawn flow as far as pytest can reach: it renders the spawn context from the **real
  template text in `consensus-protocol.md`** (read at test time, so template drift breaks the
  test), extracts the fenced `artifact-pointer` block exactly as a receiving agent would, and
  `deref`s + verifies it via the CLI from a separate process with a different cwd. No fabricated
  frontmatter fixtures, no hand-built pointers (dead-wiring bar, LEARNINGS.md:400).
  *Documented bar:* CI cannot spawn a live Claude agent, so template-coupled subprocess replay is
  the R11 acceptance bar by decision — the consensus reviewers judge the implementation against
  this stated bar, not against an unreachable literal reading.
- saga save/load round-trips `artifact_pointers`; absent field stays absent (byte-identical
  existing sagas — the #287 KTD1 precedent).

### U5 — Layer 3 light path+symbol pointers

**Delivers:** `kind: symbol` guidance: pointer locator is `<repo-relative-path>#<symbol-name>`;
receiver resolves with its existing grep/read tools (light form, R12). No formal resolver, no
feasibility probe — the probe is only required if a formal resolver is chosen (R13), and it is not.
Covers R12; R13 stays deferred by construction.

**Depends on:** U1 (kind already in contract), U2 (receiver doc).

**Files:** `references/artifact-pointers.md` (symbol section),
`tests/test_team_execution_pointers.py` (contract test already covers kind `symbol`; add doc guard
that the symbol form documents grep/read resolution and no resolver dependency).

**Test scenarios:**

- doc guard: `artifact-pointers.md` symbol section names the light form and explicitly defers the
  formal resolver (AE3's deferral arm).

### U6 — Release surfaces + engineering journal

**Delivers:** the CLAUDE.md release-surface contract for both touched plugins: team-execution
`2.7.0 → 2.8.0`, saga `0.48.0 → 0.49.0`, `.claude-plugin/marketplace.json` both entries,
both CHANGELOGs, drift-guard version assertions
(`tests/test_team_execution_plugin.py:64` and `tests/test_saga_plugin.py:48`), DECISIONS.md entry
for KTD1/KTD4/KTD5/KTD7.

**Depends on:** U1–U5.

**Files:** `plugins/team-execution/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/team-execution/CHANGELOG.md`, `plugins/saga/CHANGELOG.md`,
`tests/test_team_execution_plugin.py`, `tests/test_saga_plugin.py`,
`docs/engineering-journal/DECISIONS.md`.

**Test expectation:** existing drift-guard tests updated to the new versions (they ARE the tests).

## Execution Backend & Per-Unit Tiering

Backend: **team-execution** (operator-confirmed 2026-07-02; recommender agreed — 18 files,
6 dependency-ordered units, gated reviewer consensus blocking the `merge` destination).
Alternatives surfaced and declined: `inline` (loses the blocking gate), `cc-workflows-ultracode`
(advisory-only verdicts).

| U-ID | Unit | Model / Effort | Rationale |
|---|---|---|---|
| U1 | Pointer contract + Layer-1 snapshot | opus / high | Git-plumbing correctness and typed-error design; the foundation every other unit rests on |
| U2 | Layer-1 template wiring + receiver contract | sonnet / medium | Precise prose edits against U1's written contract; bounded, verifiable by doc guards |
| U3 | Layer-2 content-addressed store | sonnet / medium | Bounded, deterministic storage code following existing store patterns |
| U4 | Saga envelope + R11 end-to-end proof | opus / high | Cross-plugin seam; dead-wiring bar demands real-entrypoint test design judgment |
| U5 | Layer-3 symbol-form docs | haiku / low | Small doc addition plus one guard test; purely mechanical |
| U6 | Release surfaces + journal | sonnet / medium | Mechanical version/CHANGELOG/marketplace/drift-guard updates across two plugins |

Tiers operator-confirmed as proposed (2026-07-02). Segment dependency order for wave scheduling:
U1 → {U2, U3} in parallel → {U4 (needs U3), U5 (needs U2)} in parallel → U6.

## Scope Boundaries

**Out of scope (true non-goals):** per-lens scoping (conflicts with R14 — revisit only with a
no-silent-drop guarantee); formal LSP/serena resolver and its R13 probe; R15a context-GC and
semantic log compaction (other R15 fragments); S-1 worker-cache scheduling (#275); any change to
review semantics, scoring rubrics, consensus thresholds, or external-engine dispatch.

**Deferred follow-up work (distinct from non-goals):** child-side payload scoping once an
invariance guarantee exists; pointerizing external-engine envelopes (needs a clone-visible locator,
e.g. bundle transfer — new design); observing the realized orchestrator-context saving in live runs
(issue KD2 says observe, don't assert).

## Risk Analysis & Mitigation

- **Review-invariance regression (highest severity).** A reviewer that half-derefs sees less than
  the inlined version showed. Mitigation: v1 receiver contract mandates full read (R5), stated in
  `artifact-pointers.md` and guarded by U2 doc tests; per-lens scoping explicitly out of scope.
- **Snapshot litter.** Refs under `refs/team-execution/snapshots/` accumulate. Mitigation: `gc`
  subcommand + SKILL.md B4 completion step runs it; TTL default 7 days; U3 test proves reclaim.
- **Temp-index edge cases.** Repos with `core.splitIndex`, sparse-checkout, or submodules may
  surprise `read-tree`/`add -A` under `GIT_INDEX_FILE`. Mitigation: U1 tests cover a submodule-free
  standard repo (this repo's actual shape); snapshot failure is loud and the orchestrator falls
  back to inlining (KTD7 path) — degraded, never wrong.
- **Prompt-template drift.** Future SKILL edits silently reintroduce inlined diffs. Mitigation:
  U2 doc guards assert the pointer block's presence, same pattern as existing packaging guards.

## Team Structure

### Workers

| Agent | Units | Tier | Mode | Depends-on | Engine | Intent |
|-------|-------|------|------|------------|--------|--------|
| `worker-u1` | U1 | opus/high | bypassPermissions | — | — | — |
| `worker-u2` | U2 | sonnet/medium | bypassPermissions | `worker-u1` | — | — |
| `worker-u3` | U3 | sonnet/medium | bypassPermissions | `worker-u2` (serialized) | — | — |
| `worker-u4` | U4 | opus/high | bypassPermissions | `worker-u3` | — | — |
| `worker-u5` | U5 | haiku/low | bypassPermissions | `worker-u4` (serialized) | — | — |
| `worker-u6` | U6 | sonnet/medium | bypassPermissions | `worker-u5` | — | — |

All Claude workers; no engine-owned units. **Parallel Safety Check downgrade:** the plan's wave
order allows {U2, U3} and {U4, U5} in parallel, but U1–U5 all append to the shared
`tests/test_team_execution_pointers.py` and U2/U5 share `references/artifact-pointers.md` —
same-tree parallel writers would conflict, and worktree isolation is not worth the harvest
overhead for prose+test units. Execution is therefore **serialized U1 → U2 → U3 → U4 → U5 → U6**,
one resident worker per segment, shed at segment boundary.

### Reviewers

| Agent | Role | Required | Selection Reason |
|-------|------|----------|------------------|
| `devils-advocate-reviewer` | Devil's Advocate | yes | Base reviewer |
| `security-reviewer` | Security | yes | Base reviewer |
| `architecture-reviewer` | Architecture | yes | Base reviewer |
| `testing-reviewer` | Testing | yes | Plan is test-heavy: pytest scenarios per unit, e2e dead-wiring proof, doc-guard tests |
| `ai-usefulness-reviewer` | AI Usefulness | yes | `artifact-pointers.md` receiver contract + SKILL/template edits are AI-consumed specs |

### Validators

| Agent | Group | Required | Selection Reason | Blocking |
|-------|-------|----------|------------------|----------|
| `security-scanner` | Scanner | yes | New subprocess-git CLI (`artifact_pointer.py`); bandit + secret-scan over changed surface | hard-fail blocks PR/merge coordination |
| `github-actions-monitor` | Monitor | yes | CI must be green on the PR before merge offer | blocked CI blocks merge |

Not selected: dependency-scanner (no manifest/lockfile changes), iac-cost/api-compat scanners
(no infra/contract surface), all testers (no nonprod deploy target; `uv run pytest` gate is
owned by workers + CI), runtime-monitor/deploy-watcher (destination is merge, no deploy).

### Execution Gates

- Reviewer consensus threshold: >= 9.0/10 from every reviewer; no dimension < 7.0;
  security dimension < 5.0 is a blocking stop.
- Reviewer non-consensus blocks validators unless the operator explicitly overrides.
- Scanners run before PR/CI/merge coordination; hard-fail blocks.
- Maximum 3 review cycles / remediation loops before escalation.
- PR-open and merge remain `/work`-owned, explicitly operator-confirmed (destination: merge).

## Verification (CI parity)

```bash
uv run pytest tests/test_team_execution_pointers.py -v
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```

Acceptance criteria are the issue's five checkboxes, with one correction: the mypy gate is
`plugins/ scripts/ tests/` (CI scope, per CLAUDE.md), not the issue's `mypy plugins/`.
