# Liveness consumer inventory

The shared algorithm exists only at `plugins/fleet-core/scripts/fleet_commons/liveness_engine.py`.
Every consumer below resolves or invokes it through the production plugin boundary.

| boundary | production caller | source evidence | action owner | fallback |
|---|---|---|---|---|
| Outcome advance tick | `outcome.production_liveness_processor` -> `outcome_liveness.harvest_liveness` | Outcome dispatch/heartbeat ledger | existing R31 `_is_stalled` then `_record_terminal` and R22 cascade | fixed heartbeat then absolute timeout; adaptive error is advisory |
| Team pre-spawn | `liveness_protocol.py baseline` | approved path set and temporary-index digest | none | halt before Agent when Saga/fleet-core preflight is unavailable |
| Team host return | `liveness_protocol.py open` | #351 manifest/spawn plus caller-asserted **ttl_seconds** and trusted host handle | none | no subject means no liveness claim |
| Team trusted event | `liveness_protocol.py record-event` / `record-idle-notice` | host heartbeat/idle/response receipt or scoped artifact observation | liveness fact only | hook-owned send events are refused; missing host notice IDs are lock-allocated |
| Team artifact observation | `liveness_protocol.py record-artifact-observation` -> `artifact_pointer.py` | approved-path baseline/current Git digest plus optional exclusive custody | liveness fact only | changed Git remains unattributed without exact subject provenance |
| Poll boundary | `liveness_protocol.py poll` | one verified run-fact snapshot | none | evidence-error, never inferred health/death |
| Agent/SendMessage host return | `liveness_protocol.py poll` | heartbeat/activity/notice/send/ack facts | none | evidence-error or unresolved send |
| Dependency unblock | `liveness_protocol.py poll` | current subject projection | coordinator may keep dependency blocked | never bypass a missing worker manifest |
| B2 reviewer fan-out | Team SKILL Step B2 poll | all resident projections | coordinator halts fan-out on evidence defect | no destructive action |
| Re-ping pre-call | `liveness_protocol.py claim-reping` then `stage-send` | atomic claim and request digest | SendMessage caller only | claim loser sends nothing |
| SendMessage completion | _(removed)_ — no hook may gate `SendMessage` | — | — | send outcome is unobserved; a re-ping claim stays staged and expires |
| Confirmed Team stall | Saga poll decision | three accepted, expired, unacknowledged windows | issue #358 reclaimer | #357 never stops/releases/deletes |

Required poll cadence is cooperative because the plugin host exposes no always-on daemon. If the
coordinator cannot poll during an in-flight tool call, the worker's next heartbeat is simply delayed;
no lease broker fences the mutation.
