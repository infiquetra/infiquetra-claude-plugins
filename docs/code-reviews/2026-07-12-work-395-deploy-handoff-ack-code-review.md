# Code Review — Issue #395 (deploy handoff-ack protocol)

One-line verdict: **PASS** — 8 actionable findings (3 P2, 5 P3) from a 4-lens adversarial review,
all fixed in-branch; the falsification loop then ran **three rounds**, twice refuting the sweep
fix with new attack classes (OSError abort, then a FIFO **hang**) before returning `resolved`
with 21 independent probes and zero new findings.

## Review-result contract

- **Target**: branch `work/395-deploy-handoff-ack`, diff `232a089..99f3611`
- **Reviewed SHA**: 4-lens pass at `da33fbd`; falsification rounds at `5f746dd`, `fc5cf50`
  (interim), final `resolved` at `99f3611` (fix commits `5f746dd`, `fc5cf50`, `99f3611`).
  Artifact commits after `99f3611` are docs-only and non-staling for the code verdict.
- **Mode**: programmatic / report-only — `/work` owns persistence (this artifact)
- **Lenses**: correctness, security, testing, maintainability — each `saga:readonly-verifier`,
  worktree isolation, opus tier, mandated `examined_sha` reporting
- **Linked**: issue #395; PR #564; plan
  `docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md`; saga `issue-395`

## Findings (Stage A merged, deduped by path:line:category — no cross-lens overlaps)

| # | Sev | Conf | Lens | Finding | Status |
|---|---|---|---|---|---|
| 1 | P2 | 78 | correctness (reproduced) | one corrupt sidecar aborts the entire `reconcile --all` sweep with empty output — masks every sibling's dropped baton (the F2 safety net) | **fixed** across `5f746dd`/`fc5cf50`/`99f3611` — see falsification loop below |
| 2 | P2 | 90 | testing | `accept` CLI verb + the error→exit-1 boundary had zero end-to-end coverage (main() lines 518-525, 545-547 missed) | **fixed** `5f746dd`: CLI-driven success + error tests (message-not-traceback asserted) |
| 3 | P2 | 85 | testing | `--deploy-autonomy` carry-forward-on-omit never exercised through real argparse+`_merge` — a default regression would silently restamp an authored posture | **fixed** `5f746dd`: real-CLI carry-forward + explicit-restamp tests |
| 4 | P3 | 90 | testing | `read` CLI verb untested incl. its no-handoff exit-1 | **fixed** `5f746dd` |
| 5 | P3 | 85 | testing | defensive branches untested: non-object-JSON sidecar, corrupt `state.json` → `gate` fallback (the R5 self-heal) | **fixed** `5f746dd` |
| 6 | P3 | 80 | maintainability | saga CHANGELOG falsely claimed the delegator "calls offer()" and "delegates accept/authorize" (the #347 comment-falsehood class) | **fixed** `5f746dd`: describes `build_envelope()` + writes-nothing reality |
| 7 | P3 | 75 | maintainability | stale module docstring ("payload defaults to gate … lands in U2" — U2 had landed) + write-once claim unqualified | **fixed** `5f746dd`: docstring states saga-record sourcing + API-layer (not filesystem) write-once with the trust model |
| 8 | P3 | 90 | security | `accept` write-once is check-then-replace (TOCTOU), no sidecar integrity guard — within the machine-local single-operator trust model, no privilege boundary crossed | **fixed** `5f746dd` (documentation honesty): trust model stated in the module docstring; mechanism unchanged by design (O_EXCL inapplicable — accept mutates an existing file) |

## The falsification loop (the round that earned its cost)

An independent adversarial verifier attacked the fixes, **default-to-refuted**, three rounds:

- **Round 1 at `5f746dd` — REFUTED fix 1.** The sweep degrade caught only `InvalidHandoffError`,
  but `open()` raises `IsADirectoryError` / `PermissionError` (OSError family) *before* JSON
  validation — a directory-shaped or chmod-000 sidecar still aborted the whole sweep (reproduced
  with a masked sibling). Same class as #347's `_worktree_is_dirty` P1. Patched in `fc5cf50`
  (broadened except + 2 repro tests). Fixes 2-6 upheld with independent reconstructions.
- **Round 2 at `fc5cf50` — STILL REFUTED, worse.** A FIFO-shaped sidecar makes blocking `open()`
  **hang forever** — nothing is raised, so no except clause can ever fire; strictly worse than the
  original loud abort (SIGALRM-guarded reproduction). Also: a dangling-symlink sidecar silently
  vanished from the sweep (`exists()` follows the link → treated as never-offered), and the
  single-saga CLI path leaked raw OSError tracebacks past the `DeployHandoffError` boundary.
- **Round-2 fix `99f3611` — moved the defense to the root.** `_read_sidecar` now: `lexists` for
  true absence (→ `None`); dangling symlink → named error; `stat.S_ISREG` check **before**
  `open()` (non-regular files are refused without ever blocking); every remaining OSError wrapped
  into `InvalidHandoffError` so the CLI contract ("message, never a traceback") holds for all
  verbs. Sweep guard switched to `lexists`. Three regression tests incl. a SIGALRM hang guard.
- **Round 3 at `99f3611` — RESOLVED.** 21 independent probes: FIFO (no hang, degrades), dangling
  symlink (sweep + single-saga), directory + chmod-000 (sweep + CLI message-not-traceback),
  symlink-to-directory, AF_UNIX socket, mixed acked/unacked/corrupt sweeps — and the legitimate
  symlink-to-valid-file case verified to still work (read, reconcile, accept through the link).
  Zero new findings. Regression sweep: 104 tests + ruff check + format all green.

## Suppressed (below the confidence-75 gate; residual notes, not defects)

- `offer` over a corrupt sidecar refuses (fail-loud) rather than superseding (conf 70,
  correctness) — **kept by design**: the corrupt file may contain a real ack; destroying it to
  recover would trade evidence for convenience, and the fixed sweep now names the saga so the
  operator sees it.
- Docs said "consult `authorize_promotion`" implying a CLI verb that doesn't exist (conf 50,
  maintainability) — reworded anyway (cheap truthfulness fix); an `authorize` CLI verb is a
  follow-up candidate if deploy wants a mechanical consult instead of `read` + apply-the-rule.
- Age-helper None/naive-datetime branches untested (part of finding 5's coverage list) —
  diagnostic-only code, never load-bearing for the derived status.

## Validation method

Every lens ran in a disposable worktree pinned to the reviewed SHA with `examined_sha` reported
back; findings required file:line evidence with reproductions (the correctness P2 and every
security attack were run, not read). The testing lens proved all five AC selectors **non-vacuous
by mutation testing** — 7 targeted code mutations each failed exactly the named selector. The
falsification verifier rebuilt every scenario from scratch each round rather than re-running the
authors' tests, and kept its default-to-refuted posture until round 3.
