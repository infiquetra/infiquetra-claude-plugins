---
title: Work session — Reversibility/Idempotency Certificate (#279)
date: 2026-06-29
issue: infiquetra/infiquetra-claude-plugins#279
plan: docs/plans/2026-06-29-reversibility-certificate-plan.md
review: docs/reviews/2026-06-29-reversibility-certificate-readiness.md
branch: feat/279-reversibility-certificate
status: built — green; awaiting PR + merge
---

# #279 — Reversibility/Idempotency Certificate + autonomous `/outcome` board-sync

Built the VECU survivor S-2: one pure-data authority that declares per-op reversibility facts and answers a
single `authorize_write` verdict (default GATE), plus its first autonomous consumer — `/outcome` board-sync
across the saga↔mission-control boundary. v1 spans **two plugins** (saga 0.41.0→**0.42.0**, mission-control
2.3.1→**2.4.0**).

## Built (by U-ID)

- **U1** `reversibility_certificate.py` (NEW) — enumerated `OpKind` allowlist, `facts()`,
  `authorize_write()` (default GATE), declarative inverses (close⇄reopen, label add⇄remove), `idempotency_key()`.
- **U2** subsumption — `degrade_decision`'s `had_side_effect→HALT` and `outcome_projection`'s parent-close now
  derive from the certificate; behavior byte-identical (proven by an adversarial 672-combination sweep, 0 diffs).
- **U3** mission-control issue-write verbs (close/reopen/comment/label-add/label-remove, idempotent) + the
  autouse no-live-`gh` conftest guard (deny-by-default; self-test proves it fires).
- **U4** `outcome_board_sync.py` (NEW) consumer + the `advance(autonomous=True)` wiring + a production
  `_default_board_writer`. Makes U1 a live producer+consumer (KTD8); the integration test drives the real
  `advance` entrypoint.
- **U5** `/outcome` SKILL.md "Autonomous board-sync" section + mutation-proof doc-contract test.
- **U6** release triad for both plugins + version-pin guards.

## Commits (branch `feat/279-reversibility-certificate`)

`8c1fb22` U1 · `a1dd403` U2 · `39cdaa7` U3 · `dd18bfa` U4 · `0cd2bfe` U5 · `f04cc47` fix (2 adversarial-verify
P2s) · `fecdaf8` release 0.42.0 / 2.4.0.

## Adversarial-verify (ultracode, operator-requested on U2 + U4)

- **U2**: 672-combination cartesian sweep of `degrade_decision` pre/post → **0 diffs**; no production consumer
  branches on `parent_close`; `side_effected` is pure identity. Subsumption equivalence confirmed.
- **U4**: found + fixed **two real P2 holes the unit tests missed** — (1) repo-blind `idempotency_key` →
  cross-repo same-number leaves (`saga#5` vs `mission-control#5`) collided → silent lost write; (2) a
  ledger-write fault sat outside the retry try/except → wedged the whole `advance()` tick + orphaned a
  committed write. Both fixed with regression tests.

## ⚠️ Execution provenance — agy was never used

The build was planned (KTD7) to delegate each feature unit to **agy Gemini Pro 3.1 High**. Mid-build the
operator flagged that the "agy" teammates looked like Claude doing the work. **Verified from the agent
transcripts** (`subagents/agent-aagy-u{1..4}-*.jsonl`): each named `agy:runner` spawn had Read/Write/Edit
tools, emitted Claude's `★ Insight` output style, and made **zero `agy` invocations** — i.e. the named-spawn
produced a **Claude clone**, not the agy wrapper. So **all units are Claude-authored**; commit messages were
rewritten to say so, and the "n=4 agy Pro run" experiment data is **invalid**. Prior runs (#275/#277/#278)
are now suspect and need the same transcript audit. Full detail: memory `[[project-external-agent-delegation]]`.

## Checks

`uv run pytest` (1427 passed; the sole failure is the known local-only `.claude`-leak guard, green in CI) ·
`ruff check .` + `ruff format --check .` clean · `mypy plugins/ scripts/ tests/` clean (fresh cache — a stale
`.mypy_cache` produced phantom errors mid-build; clear it before trusting a local mypy that disagrees with CI).

## Next step

Open the PR for `feat/279-reversibility-certificate` (destination = merge) → squash-merge on green CI →
optional `/qa` advisory. The autonomous board-sync ships **armed but inert**: merging does not perform any
board write; writes only fire when an operator runs `/outcome advance --autonomous`.
