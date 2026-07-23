# Code review — issue #617 registry schema forward-compatibility

**Final verdict: clean at `62c88cad` (round 2)** — round 1 at `4b0a0ae7` was **blocked** with one
validated P1 (silent extras drop on the settlement-commit fence rebuild) plus three validated P3s;
all four were repaired in commit `62c88cad` and delta-adjudicated resolved with zero new findings.

## Review-result contract

- **Branch:** `work/617-registry-schema-forward-compat` · **HEAD (REVIEWED_SHA):** `4b0a0ae7`
  · **base:** `4eb2fe15` (= origin/main, verified merge-base, main unmoved)
- **Scope:** commits `a55ec82c` (U1+U2 broker tolerance layer + doctor/repair) and `4b0a0ae7`
  (U3 release surfaces); 13 files, +1018/−27 — exactly the spec-declared surfaces.
- **Judged against:** `docs/plans/2026-07-23-issue-617-registry-schema-forward-compat-plan.md`
  (R1–R10, KTD1–KTD5, U1–U3).
- **Mode:** programmatic report-only (caller /work Phase 5.1 owns persistence); active saga
  `issue-issue-617`, artifact appended to `review_paths`, lifecycle untouched.
- **Gates at HEAD (driver-run, pre-review):** pytest 5407 passed / 0 failed / 1 skipped; ruff
  check + format --check clean; mypy clean; bandit delta zero vs base; release-surface parity
  clean.

## Built-vs-planned audit

R1–R9 DONE with pinning tests; R10 (live acceptance) deferred by design, operator-gated
post-merge. D1 (FencingToken audit comments) and D2 (CHANGELOG exit codes) discharged in-unit —
verified present, not re-raised. Scope CLEAN: no undeclared surfaces touched.

## Review team

Three finder lenses (opus, `saga:readonly-verifier`, worktree isolation): correctness+reliability,
security+integrity, testing+release-surfaces. Stage A merged 4 raw findings (no fingerprint
collisions, all confidences ≥80, none suppressed). Stage B: one adversarial validator per
survivor (F1 opus, F2–F4 sonnet; same sandbox profile) — 4/4 validated, 0 rejected.

## Findings

| # | Sev | Conf | File | Finding | Validation |
|---|-----|------|------|---------|------------|
| F1 | P1 | 96 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:3630` | Settlement-commit rebuilds the resource fence via bare `ResourceFence(...)`, silently dropping preserved extras (newer-writer state loss — the exact KTD2/R1 hazard) | validated — live repro: injected fence-level key survives read/renew, GONE after prepare→commit |
| F2 | P3 | 85 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:1967,2003` | Archived closed-fence sidecar parses bypass the 64 KiB extras cap (KTD5 hole); `_read_archived_fence` single 64 KiB read truncates legit near-cap fences; `_inspect_archived_fences` read loop unbounded | validated — confirmed regression: pre-#617 `ResourceFence.from_dict` failed closed on this channel |
| F3 | P3 | 90 | `plugins/saga/scripts/lease_broker.py:537` | doctor CLI exit map defaults unknown status → 0 (fail-open) — latent (only 3 statuses exist today) but contradicts the design's fail-closed stance | validated — no caller/test pins the default; flip is safe |
| F4 | P3 | 92 | `tests/test_fleet_lease_broker.py:2321` | R5 byte-identity test is self-referential (same broker serializes and compares); cannot detect #617-introduced serialization drift. Real R5 guard is the separate `"extras" not in _all_keys(raw)` assertion | validated — differential repro: test passes unmodified against the pre-#617 broker; plan's R5 wording demands a pre/post comparison |

### F1 detail (blocking)

`_commit_settlement_locked` reads `head = registry.resource_fences.get(digest)` (`:3621`), CAS-proves
it is the *same logical fence* (identical broker_epoch / fencing_sequence / lease_id, no
close_receipt), then overwrites it at `:3630-3636` with a fresh `ResourceFence(...)` that passes no
`extras` — defaulting to `{}`. Sibling updates in the same function use `replace(...)` and preserve
extras (`:3550/:3552/:3613`), proving the fence site is an oversight, not an intended reset. The
plan (R1/KTD2) mandates per-fence unknown keys be preserved byte-faithfully through write; the only
intentional extras-clears in the codebase are the repair/strip helpers. Consequence: an
older-but-tolerant broker committing a settlement destroys a schema-newer writer's per-fence state —
data loss masquerading as success, the highest-severity failure mode the plan names. Test gap
confirmed: the extras-preservation test drives `renew` only; no test drives a settlement commit over
an extras-carrying fence.

**Fix:** `registry.resource_fences[digest] = replace(head, close_receipt=close)` + regression test
(inject fence extras → prepare → commit → assert extras survive on the closed fence and its archive).

## Coverage notes (aggregated from lenses)

- Extras cap tested at cap+1 and under-cap but not exactly at `== cap` (strict `>` makes boundary
  well-defined); extras-across-mutation pinned via `renew` (representative of the shared
  `_write_registry` path — except the F1 commit path, which rebuilds rather than mutates).
- doctor CLI exit 4 covered at the seam (fake broker) and 0/3 end-to-end; exit 4 not driven
  end-to-end through a real corrupt registry.
- `repair()` "strict revalidate" is implemented as tolerant re-parse + empty-extras-inventory
  check — judged equivalent to strict, not materially misleading (audited by two lenses).
- `SettlementRecord.settlement_sha256` now hashes `to_dict()` including outer extras — judged a
  strengthening, not a hazard (bindings stay self-consistent across tolerant readers).
- Load-bearing-ness proven by checkout-swap: `test_unknown_keys_at_every_scope_survive_read_then_write`
  and the repair suite FAIL against the base broker; byte-identity + settlement-close carve-out
  tests pass on base by nature.
- R10 live acceptance out of scope (operator-gated, post-merge).
- Machinery note: two of three lens seats and one validator hit fleet-lease hook HALTs on Bash
  mid-review (worktree seats lease-blind / token expiry — the known worktree-reservation-claim
  defect); all fell back to Read-tool static verification. F1's validator retained Bash and
  reproduced the defect live.

## Round 2 — repairs and delta adjudication (verdict: clean)

Repair commit `62c88cad` (7 files, +147/−29). Gates at the repaired tree: full battery
**5410 passed / 0 failed / 1 skipped**, ruff check + format --check clean (437 files), mypy
exit 0, bandit delta zero (same 5 pre-existing Low), release-surface parity clean.

| # | Repair | Delta adjudication (opus verifier over `4b0a0ae7..62c88cad`) |
|---|--------|---------------------------------------------------------------|
| F1 | `replace(head, close_receipt=close)` at the commit linearization point + `test_fence_extras_survive_settlement_commit` | resolved — behavior-identical on every non-extras field (CAS proves lease_id/epoch/sequence equality; digest + `from_dict` proves resource_ref); test empirically fails pre-repair (extras dropped to None), passes post-repair |
| F2 | `_read_bounded_archived_fence_payload` (EOF loop, 4× cap byte bound) + `_validated_archived_fence` (per-record extras cap) wired into both sidecar readers + 3-leg regression test | resolved — fd lifecycle leak-safe, error strings distinct, both call sites converted, `classify_token` route exercises the de-truncated read |
| F3 | doctor exit map default → 4 + `("unrecognized-future-status", 4)` test case + CHANGELOG wording | resolved — line and pin verified |
| F4 | `test_extras_free_output_matches_pre_617_golden` pinning SHA-256 `fb0bc764…755127` (2925 bytes) | resolved — golden independently recomputed from the base `4eb2fe15` broker AND the repaired broker (exact match both); fixture determinism verified |

New findings: none. Collateral (format-only `test_saga_plugin.py` fix, CHANGELOG amendments)
verified accurate. One non-defect note kept for the record: the archive byte bound measures
pretty-printed bytes while the extras cap measures compact bytes, so pathologically deep-nested
tolerated extras (unrealistic for forward-compat fields) could fail closed on archive re-read —
the safe direction, and strictly better than the pre-repair 64 KiB truncation.

Also carried in `62c88cad`: the `tests/test_saga_plugin.py` ruff-format fix — the committed U3
tree actually failed `ruff format --check` (one over-wrapped assert), contradicting the Phase-3
gate record; corrected there and in the work-session doc.
