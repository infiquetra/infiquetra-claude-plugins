---
title: defect(fleet): macOS boot identity splits into incomparable sysctl/utmpx cohorts that silently purge each other's leases
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# defect(fleet): macOS boot identity splits into incomparable sysctl/utmpx cohorts that silently purge each other's leases

## Problem

macOS boot identity is derived preferentially from `sysctl -n kern.boottime`
(`darwin:<sha256>`), falling back to a utmpx BOOT_TIME read (`darwin-utmpx:<sec>:<usec>`)
(`fleet_commons/lease_broker.py:487-515` at fleet-core 0.20.0). The two formats can never
compare equal — and on the same boot of jeff-mac-studio the underlying seconds even differ by
one (sysctl `1784373991` vs utmpx `1784373992`). Any process whose `sysctl` subprocess fails
(PATH without /usr/sbin, sandbox, or fork pressure against the 2 s timeout) silently lands in
the other cohort.

## Impact

`_admission_expired` and `_expired_static` treat any boot_id mismatch as a stale boot, so a
single utmpx-cohort process purges every sysctl-cohort lease and admission on its next locked
write (and vice versa) — silent, machine-wide, and indistinguishable from TTL expiry in the
aftermath. Not confirmed as the trigger of a specific observed fault yet (the 2026-07-23 canary
wipes were the async PostToolUse race), but it is a live structural hazard for every
intermittent "state vanished" report.

## Acceptance sketch

- One canonical boot identity per boot regardless of derivation path (e.g. always prefer one
  source, or normalize both to the same value with a tolerance for the observed 1 s skew).
- A mismatch between derivations on the same host logs loudly instead of silently purging.

## Evidence

- `docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md` (post-merge R8
  section, "Additional structural hazard")
- Reproduction: both derivations executed side-by-side on jeff-mac-studio 2026-07-23 produce
  incomparable strings for the same boot.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — `_default_boot_id` /
  `_darwin_utmpx_boot_id` normalization (:443-515)
- Release surfaces: plugin.json, marketplace.json, CHANGELOG, drift pins

### Tests to add or update

- `tests/test_fleet_lease_broker.py`: same-boot identity equal across derivation paths
  (sysctl mocked unavailable vs available); mismatch path logs loudly rather than purging.

### Verification

```
uv run pytest -q tests/test_fleet_lease_broker.py
# live: both derivations on the same host resolve one canonical identity
```

### Objective

Not yet assigned to an Objective — structural hazard identified during the #616 R8 canary diagnosis; grouping is the operator's call.

### Intent

One boot yields one canonical identity regardless of which derivation path a process lands on; cross-derivation mismatch is loud, never a silent purge.

### Out-of-scope / non-goals

Non-darwin platforms (linux boot_id path is single-source); redesign of lease expiry semantics.

### Context library links

- docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md (post-merge R8 section, structural hazard note)

### Acceptance criteria

- [ ] `uv run pytest -q tests/test_fleet_lease_broker.py -k boot_id` green, including: with `sysctl` mocked unavailable, the derived identity equals the sysctl-derived identity for the same boot (1 s sec-skew covered).
- [ ] A forced derivation mismatch surfaces as a loud log/error in the test, with zero leases or admissions purged.
- [ ] Live check on jeff-mac-studio: both derivation paths resolve one canonical identity — `python3 -c "...lb._default_boot_id()... lb._darwin_utmpx_boot_id()..."` prints equal canonical values.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/issue-bodies/boot-id-split.md
- Source type: local-file
- Source title: live: both derivations on the same host resolve one canonical identity

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/645
- Number: 645
- Created at: 2026-07-23T12:06:49.035693+00:00

