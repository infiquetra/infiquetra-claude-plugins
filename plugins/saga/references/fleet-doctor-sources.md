# Fleet doctor — source matrix (#353)

Every source the doctor observes, its raw on-disk contract, the collector that reads it, and
the oracle that proves the read. This table is machine-checked: the conformance suite parses
the `source kind` column and fails when it drifts from `fleet_doctor.SOURCE_KINDS` or from the
kinds an actual full-fixture scan emits — a dead collector, an unused row, or an undeclared
source breaks the build (R9/U4).

| source kind | location (raw contract) | collector | proving oracle |
|---|---|---|---|
| git-repo | `git rev-parse --show-toplevel` / `--git-common-dir` (fixed argv, read-only) | `resolve_repo` | `test_missing_repo_is_config_error_exit_two` |
| run-facts | `<git-common-dir>/saga-run-facts/run-facts.jsonl` — hash-chained `run_fact.v1` JSONL (#351); `this_hash` = sha256 of the canonical record incl. `prev_hash`; torn trailing line = valid-prefix crash artifact; the chain proves **prefix integrity only** — whole-record trailing truncation at a newline boundary leaves an independently valid shorter chain and is undetectable without an external head anchor, hence the honest verdict `verified-prefix` | `collect_run_facts` / `verify_run_fact_chain` | `test_valid_ledger_verifies_chain`, `test_middle_mutated_ledger_breaks_chain`, `test_trailing_record_truncation_is_verified_prefix` |
| lease-registry | `<lease-store>/registry.json` — `fleet_lease_registry.v1` protocol 2 (#356): leases, resource_fences (close receipts), closed_owner_admissions | `collect_lease_registry` | `test_lease_registry_present_counts_leases`, `test_lease_registry_schema_skew_is_incomplete` |
| audit-store | `<audit-store>/runs/<run_id>/{manifest,result,receipt}.json` — durable delegation artifacts (#355 evidence root); receipts are `bridge_receipt.v1` | `collect_audit_store` / `reconcile_delegation` | `test_audit_runs_enumerated_and_digested`, `test_claimed_without_receipt_is_receiptless` |
| git-worktrees | one capped `git worktree list --porcelain` snapshot | `collect_git_worktrees` | `test_stale_worktree_both_git_and_filesystem` |
| worktree-registries | `<git-common-dir>/saga-outcomes/<outcome>/worktrees.json` — closed to one `worktrees` key; entries carry path/branch/owner/shared_install_ref/at/repo_root/outcome_id + optional lease binding | `collect_outcome_registries` | `test_dangling_registry_row`, `test_malformed_worktree_registry_is_incomplete` |
| outcome-dispatch-events | `<git-common-dir>/saga-outcomes/<outcome>/ledger.jsonl` — plain append-only replay ledger; `phase=commit, kind=dispatch` records carry the exact `settlement{dispatch_id, unit_id, attempt}` handle | `collect_outcome_dispatch_events` | `test_observed_commit_without_spawn_fact`, `test_exact_accounted_spawn_is_clean` |

Correlation-only inputs that ride the sources above (no separate source row): #358 teardown
facts are `kind=teardown` records inside the run-facts chain (`resource_id` is the broker
lease id; `generation` is the `broker_epoch:fencing_sequence` string), and broker agent-lease
identities are parsed from the two supported outcome vocabularies
(`outcome:<outcome>:<subplot>:<dispatch-identity>` and `outcome-dispatch:…:<attempt>`);
outcome-labeled leases outside them are counted in a warning, never silently dropped.

The doctor validates its own minimal `bridge_receipt.v1` subset at runtime;
`test_receipt_subset_conforms_to_canonical_validator` compares that subset against
fleet-core's canonical `validate_receipt` on a corruption fixture matrix and fails on drift
(the conformance-vs-runtime split, U3). Verdicts are equal wherever the canon is
well-defined; the one enumerated divergence is deliberate and pinned by the same test — the
canon's presence-only transport guard accepts `transport: null` (skipping runner-section
validation) and raises on unhashable transports, while the doctor rejects every non-string
transport fail-closed (it may over-flag a degenerate receipt, it can never crash or pass one
as clean).
