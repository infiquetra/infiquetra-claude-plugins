---
name: fleet-doctor
description: One strict, bounded, read-only cross-source audit of the fleet substrate — reconciles Git worktrees, outcome registries, broker leases/fences, chain-verified run facts, outcome dispatch events, and the delegation audit store into leaked-resource / unledgered-spawn / receiptless-delegation findings plus explicit evidence errors. Absence, corruption, and incompleteness are three different verdicts; a capped or corrupt scan exits 2 and can never return clean. Reports and routes to owners; never repairs, settles, retries, releases, or reaps. Triggers on "fleet doctor", "audit the fleet", "any leaked worktrees or unledgered spawns", "/fleet-doctor".
argument-hint: "[--repo-root PATH] [--lease-store PATH] [--audit-store PATH] [--format text|json] [--show-local-paths]"
---

# Fleet Doctor

`/fleet-doctor` answers **"is the fleet substrate internally consistent right now?"** with one
repo-scoped, point-in-time, derived-fresh report — `fleet_doctor_report.v1`. It is the strict
cross-source tripwire beside the tolerant, advisory `/delegation-audit`: where that query
degrades a malformed file to absence, the doctor turns it into an explicit evidence error that
blocks a clean exit (KTD5).

## The three diseases (plus evidence errors)

- **leaked-resource** — managed worktree drift in either direction (`stale-worktree`,
  `dangling-registry`), `ownership-drift` (path or lease-generation disagreement,
  broker-only leases), and `terminal-resource-open` (a teardown released it, a closed owner
  admission or close receipt exists, yet the lease lives on).
- **unledgered-spawn** — an independently observed position (outcome dispatch commit event or
  supported broker agent lease) with no matching #351 manifest/spawn fact; plus
  `phantom-spawn-fact` (fact with no observation) and `unsettled-spawn` (observed, spawned,
  never settled). One producer fact is never proof a process ran (KTD3).
- **receiptless-delegation** — a claimed real engine execution with no durable, schema-valid
  `bridge_receipt.v1`. A present-but-invalid receipt is a `delegation-evidence-error`, never
  absence and never clean; an admitted fallback is not receiptless.
- **evidence-error** — malformed JSON, unsafe paths, schema skew, broken hash chains,
  contradictory identities, caps hit, or a source changing mid-scan. Any evidence error makes
  the scan incomplete: exit 2.

## Contract

- **Read-only by construction (R1/R2).** No producer module is imported (the mutation-import
  denylist is an executable conformance test); bytecode writing is disabled; strict readers
  never follow symlinks, never heal, never quarantine, and cap every byte/record/depth/output
  dimension. A repeated scan over unchanged sources is byte-identical. The run-fact chain
  verdict is `verified-prefix`, deliberately: hash-chain verification proves the surviving
  prefix, and whole-record trailing truncation at a newline boundary is undetectable without
  an external head anchor.
- **Exit semantics fail closed (R8/KTD6).** 0 = complete + clean; 1 = complete + disease
  findings; 2 = incomplete proof. Hitting a cap emits `scan-incomplete`, never a truncated
  clean.
- **Managed scope is explicit (KTD4).** Only canonical `.saga-worktrees/<outcome>/<subplot>`
  paths participate in the leak invariant; the primary worktree, the current working tree,
  `_shared-install`, and unmanaged developer worktrees are excluded by construction.
- **Privacy (R7).** Machine-local store paths are redacted to `label:component` unless
  `--show-local-paths` is passed; no prompt, transcript, diff, or secret enters output.
  Redaction covers error text too — OS-level failures are reported by errno and message
  alone, never by absolute path — and control characters in untrusted identities are
  neutralized in the text rendering.
- **Owner routing.** Every finding carries a bounded, static `owner_command` naming the owning
  recovery surface. The doctor never executes it.

The full source matrix — every observed source, its on-disk contract, its collector, and its
proving test — is `references/fleet-doctor-sources.md`; the conformance suite fails if a
collector and the matrix drift apart.
