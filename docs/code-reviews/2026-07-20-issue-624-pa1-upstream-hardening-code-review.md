# Code Review — Issue #624 PA-1 Upstream Hardening

## Verdict

> **PASS.** Ten findings were raised, eight survived the confidence gate, and all eight survived
> adversarial validation and are closed in the remediation revision. No P0/P1 was found; the single
> P2 (a receipt leaking an absolute path against a documented invariant) is fixed. No finding
> remains open.

| Field | Value |
|---|---|
| Target | `work/624-pa1-upstream-hardening` against `origin/main` |
| Merge base | `cf15a09f` |
| Reviewed revision | `d50ecaea4087cfbdfac144f2a8fe0f8c1909648e` |
| Remediation revision | `5115c5f1` |
| Issue | #624 (PA-1 of #605, outcome `lease-safe-runtime-continuity`) |
| Plan | `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`, "Pre-acceptance production units" |
| Mode | Programmatic (gate only; criteria-freeze skipped, artifact caller-persisted) |
| Scope check | CLEAN |
| Blocked | false |

## Scope Check

The diff is confined to the four PA-1 remediation targets (`outcome.py` help strings and the dead
import success print, `outcome_compat._ensure_private_dir`, `fleet_commons/audit_store` ancestor
hardening), their tests, the saga 0.105.0 / fleet-core 0.16.0 release surfaces, and two journal
entries. It introduces no new command, schema, or consumer contract.

## Built vs Planned

| Criterion (#624) | Status | Evidence |
|---|---|---|
| Export/import `--help` reflect live #604 R10 semantics | DONE | `outcome.py` export/import parser help; pinned by `test_cli_help_pins_retired_bundle_semantics`. |
| Stale section comment corrected | DONE | `outcome.py` bundle-section comment. |
| Dead import success print removed | DONE, deviation | Refusal is `OutcomeError` → top-level `{"ok": false}` receipt, exit 1 — not exit 3. See Deviation. |
| Handoff store created `0o700`, unsafe pre-existing refused | DONE | `outcome_compat._ensure_private_dir` + `_write_once`; three contract tests. |
| Audit-store ancestors hardened | DONE | `audit_store._refuse_unsafe_ancestors`; three tests. |
| Release surfaces coherent | DONE | saga 0.105.0, fleet-core 0.16.0 across both `plugin.json`, `marketplace.json`, both changelogs, and four test pins; parity + sync scripts green. |

COMPLETION: 6/6 criteria accepted.

### Recorded deviation

The issue body specifies the import arm should "exit 3 with a refusal-receipt JSON", mirroring the
export arm's `CompatibilityHaltError` path. The shipped behavior is exit 1 via the pinned
`OutcomeError` contract. `import_bundle`'s refusal is pinned by
`test_legacy_bundle_import_is_refused_with_zero_writes`, which predates #624; converting it to a
compatibility halt would change a contract outside PA-1's remediation scope for no behavioral gain,
since both paths refuse with the same migration guidance and write nothing. The minimal,
plan-faithful reading was taken. Recorded on the issue.

## Review Team

Four always-on lenses, spawned as `saga:readonly-verifier` with worktree isolation at opus, three
concurrent (the account cap): correctness, security, testing, maintainability/conventions. No
conditional lens was warranted — the diff touches no API surface, infrastructure, or personal data.
Stage-B validators ran at sonnet, one per surviving finding, each charged to refute.

## Findings

Ten raw findings. Stage A deduplicated by `path:line:category` and applied the confidence gate
(<75 suppressed unless P0 ≥ 50). Eight survivors went to Stage B; all eight were upheld.

| # | Sev | Conf | Finding | Validator | Status |
|---|---|---|---|---|---|
| S1 | P2 | 100 | `handoff-store-unsafe` receipt embeds an absolute path, violating the documented "receipts never contain absolute paths" invariant (R12) that lets callers print them verbatim. | upheld, 90 | closed |
| S2 | P3 | 75 | `outcome_compat._ensure_private_dir` omits the ancestor walk its fleet-core sibling gained in the same commit while claiming "the same predicate"; a symlinked intermediate parent was traversed and only the leaf checked. | upheld, 95 | closed |
| C1 | P3 | 75 | `Store.for_root`'s `resolve()` makes the new symlink-ancestor refusal inert for every production caller, though the docstring promises it unconditionally. | upheld, 92 | closed |
| C2 | P3 | 100 | The import arm reads and parses the bundle before the unconditional refusal, so a missing file raises an uncaught `FileNotFoundError` and a malformed one returns a JSON parse error instead of migration guidance. (pre-existing) | upheld, 96 | closed |
| C3 | P3 | 75 | The ancestor `lstat` walk catches only `FileNotFoundError`, so an unreadable ancestor raises a raw `PermissionError`. (pre-existing in class) | upheld, 92 | closed |
| T1 | P3 | 100 | The new CLI import test passes unchanged at the merge base; its docstring claims a behavior delta it cannot detect (the removed print was already dead since #604 R10). | upheld, 97 | closed |
| T2 | P3 | 100 | The below-home fresh-creation branch of the ancestor walk — the production default-root path — is uncovered. | upheld, 95 | closed |
| T3 | P3 | 75 | The deliberate group-writable-permitted boundary is unpinned and can drift in either direction silently. | upheld, 92 | closed |

Validators reproduced rather than reasoned where they could: S1 by importing the reviewed blob and
triggering the refusal, S2 and C1 by probing symlinked layouts against both entry points, C2 by
running both error paths and then re-running them against a patched copy, T1 by executing the new
test against the merge base, T2 by mutation-testing the branch (flipping the `return` to a `raise`
left all 17 tests passing).

### Suppressed by the confidence gate

| Sev | Conf | Finding | Disposition |
|---|---|---|---|
| P2 | 55 | The `outcome_compat` docstring's parity cross-reference is stale now that fleet-core gained an ancestor walk. | Substance carried by S2; closed by the same fix, which makes the parity claim true rather than softening it. |
| P3 | 50 | The ancestor guard permits group-writable (`0o020`) ancestors, refusing only world-writable. | Deliberate per the guard's stated scope; the boundary is now pinned by T3's test rather than changed. |

## Remediation

All eight findings are closed in `5115c5f1`:

- **S1** — receipts carry no path; the remedy names the git-common-dir store instead. A new test
  asserts no receipt field contains the store path or the home directory.
- **S2** — `_refuse_unsafe_handoff_ancestors` ported into `outcome_compat` (ported, not imported:
  the module is the frozen cross-runtime seam consumed byte-faithfully by the codex repo), raising
  `CompatibilityHaltError` per the module's error discipline. Parity is now real.
- **C1** — the docstring states the split reach instead of overpromising: mode bits survive
  `resolve()` so the world-writable branch covers every caller, while symlink identity does not, so
  that branch covers direct callers and the post-resolve window. `.resolve()` was kept deliberately —
  `test_default_root_resolves_under_home_dot_claude_delegation_audit` pins canonical-root semantics
  and refusing a symlinked `~/.claude` outright would break common dotfile-manager layouts.
- **C2** — the arm refuses without reading its path argument; the schema echo degrades cleanly.
- **C3** — both walks refuse an uninspectable component typed. Note the validator confirmed every
  common production caller already absorbs the raw error as an `OSError`, so this is hygiene, not a
  live defect.
- **T1** — docstring reframed as a forward contract guard, with the pre-#624 truth stated.
- **T2/T3** — below-home fresh-creation tests on both sides, plus the group-writable acceptance pin.

The mechanism behind C1 and S2 is recorded as a durable learning
(`{#resolve-disarms-symlink-guards-624}`): canonicalizing a path upstream silently disarms the
symlink half of a downstream guard, and testing only the private helper hides it.

## Gates

| Gate | Result at `5115c5f1` |
|---|---|
| Full suite | 5229 passed, 0 failed, 1 skipped |
| `ruff check` / `ruff format --check` | clean / 435 files formatted |
| `mypy plugins/ scripts/ tests/` | clean (one pre-existing annotation note) |
| `bandit` (changed files) | 1 low, pre-existing `B404`; zero new |
| `check_release_surface_parity.py` | all plugins in parity |
| `sync_marketplace.py --check` | marketplace matches the plugin fleet |
| `git diff --check` | clean |

## Saga

No work-thread saga matches issue-624 — this is Claude-direct execution of the PA-1 unit under the
`lease-safe-runtime-continuity` outcome (leaf `leaf-lease-safe-runtime-continuity-cross-runtime-acceptance`).
Per scan-first / never-mint, no tick was written and no `review_paths` append was made. This artifact
is caller-persisted.
