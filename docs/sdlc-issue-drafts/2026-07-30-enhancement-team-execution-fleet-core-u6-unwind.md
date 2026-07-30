---
title: enhancement(team-execution,fleet-core): U6 unwind lease_protocol and rename lease_ttl_seconds
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: high
handoff_maturity: plan-ready
approval_state: needs_operator_approval
---

# enhancement(team-execution,fleet-core): U6 unwind lease_protocol and rename lease_ttl_seconds

### Objective
Remove the fleet lease broker from the `team-execution` plugin, and decouple the liveness engine from
the lease concept by renaming the `lease_ttl_seconds` observation field to `ttl_seconds` across every
producer and consumer of the serialized event schema — **all five files in one commit**.

Unit **U6** of seven under parent issue #677 (retire the fleet lease broker). Plan:
`docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board objective:
`defects-claude-plugins`.

### Intent
Two pieces of work in one unit, because the rename cannot be split.

**Piece one — the team-execution consumers.** `lease_protocol.py` (234 lines, loads at `:19`) is a
candidate for whole-file deletion; confirm whether anything in it survives the lease concept.
`liveness_protocol.py` (798 lines, ~9 sites at `:242`, `:257`, `:258`, `:462`, and the wire producer at
`:291`) takes `lease_broker: Any | None = None` as an injected dependency at `:242` and constructs a
default at `:258` — **remove the parameter rather than defaulting it to `None` forever.**

**Piece two — the rename, and why it is dangerous.** `lease_ttl_seconds` is not a local field. It is
parsed off the wire, serialized back to the wire, and sits inside a required-key contract. A partial
rename raises a `KeyError` **at event-parse time** — invisible to mypy and to a smoke import. The full
measured surface is five files:

| Site | Role |
|---|---|
| `fleet-core/.../liveness_engine.py:94`, `:288`, `:289` | dataclass field, branch guard, and a `_finite_nonnegative(…, "lease_ttl_seconds")` **string literal** that appears in operator-visible error messages |
| `fleet-core/.../liveness_engine.py:367` | the `lease-ttl-cold-start` reason string |
| `saga/scripts/liveness_events.py:65` | membership in the `IDENTITY_KEYS` tuple — a required-key contract |
| `saga/scripts/liveness_events.py:207`, `:236`, `:258`, `:644` | dataclass field, wire **parse** (`value["lease_ttl_seconds"]`), wire **serialize**, and construction from `identity.lease_ttl_seconds` |
| `team-execution/.../liveness_protocol.py:291` | the producer: `"lease_ttl_seconds": lease.ttl_seconds` |

`plugins/saga/scripts/liveness_events.py` appeared in no unit until the document review added it. It
does **not** import the broker — it loads `liveness_engine` through `fleet_commons_shim` at `:574` and
`:1028` — which is exactly why it escaped the consumer survey. It is squarely inside the rename's blast
radius.

**Open compatibility question, not decided by the plan:** whether previously written events must still
parse under the old key. Answer it before writing the parse path.

### Out-of-scope / non-goals
- Do not touch `outcome_worktrees.py`'s `lease_ttl_seconds` parameter. **That is a different field
  with the same name** — a worktree TTL defaulting to a broker constant — and it belongs to U3. Do not
  conflate them.
- Do not delete anything under `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` or
  `orphan_evidence.py` — that is U7.
- Do not split the rename across commits. All five files move together or the event schema breaks at
  runtime.
- Do not bump the `team-execution` version in this unit. All three release surfaces move together in
  U7, where `team-execution` goes to **3.0.0**.

### Files expected to change
- `plugins/team-execution/skills/team-execution/scripts/lease_protocol.py` (234 lines; likely deleted
  outright)
- `plugins/team-execution/skills/team-execution/scripts/liveness_protocol.py` (798 lines, ~9 sites)
- `plugins/fleet-core/scripts/fleet_commons/liveness_engine.py` (rename at `:94`, `:288`, `:289`,
  `:367`)
- `plugins/saga/scripts/liveness_events.py` (`:65`, `:207`, `:236`, `:258`, `:644`)
- `tests/test_team_execution_liveness.py`, `tests/test_liveness_engine.py`,
  `tests/test_liveness_events.py`

Agent-facing documentation moves in the same pull request as the behavior it describes (plan
requirement R11). This unit carries the largest documentation share — five documents:

- `plugins/team-execution/skills/team-execution/SKILL.md` — the skill agents actually execute
- `plugins/team-execution/skills/team-execution/references/lease-protocol.md` — documents a file this
  unit likely deletes outright, so this is probably a deletion too
- `plugins/team-execution/skills/team-execution/references/liveness-protocol.md` — liveness survives as
  a capability but not as a lease-fed one
- `plugins/team-execution/README.md` — `:20-29` describes lease admission, preflight, renewal, release,
  and dead-owner sweep as current behavior
- `plugins/saga/references/liveness-consumer-sites.md` — a consumer-site inventory of what is being
  removed

Line references were measured at revision `ddba53a0`. Re-grep before editing.

### Tests to add or update
`tests/test_team_execution_liveness.py`:

- Liveness reports a suspect resident with no lease module present.
- The cold-start branch fires from a supplied `ttl_seconds` with no lease.

`tests/test_liveness_engine.py`:

- `ttl_seconds` drives `ttl-cold-start`.
- The old field name is gone.

`tests/test_liveness_events.py`:

- **An event round-trips through serialize-then-parse under the new key.** This is the test that would
  have caught the partial rename.
- `IDENTITY_KEYS` no longer names `lease_ttl_seconds`.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U6, requirements R4
  and R4a, decision KTD5, documentation inventory R11)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md` — finding D2 is the origin of
  R4a and of `liveness_events.py` being in this unit at all
- Origin of the liveness engine: issue #357

### Inputs inventory
- The five-file rename table above, measured at revision `ddba53a0`.
- `plugins/saga/scripts/liveness_events.py:65` — the `IDENTITY_KEYS` tuple, a required-key contract.
  Membership is what turns a partial rename into a runtime `KeyError` rather than a type error.
- `plugins/saga/scripts/liveness_events.py:236` (wire parse) and `:258` (wire serialize) — the two
  ends of the serialized event schema.
- `plugins/team-execution/skills/team-execution/scripts/liveness_protocol.py:291` — the wire producer.
- The `fleet_commons_shim` load sites at `liveness_events.py:574` and `:1028`, which explain why this
  file never appeared in the broker-consumer survey.
- The five documents listed under Files expected to change, and their fleet-lease content.
- Any previously written liveness events that may still need to parse — the open compatibility
  question.

### Failure modes / pre-mortem
1. **Most likely: the rename half-lands.** Someone renames the engine's dataclass field and the tests
   that assert on it, but misses the wire parse at `liveness_events.py:236` or the producer at
   `liveness_protocol.py:291`. mypy passes. Import succeeds. The first parsed event raises `KeyError`.
   Mitigation: the serialize-then-parse round-trip test, written before the rename, plus the
   single-commit requirement.
2. **The two `lease_ttl_seconds` fields are conflated.** U3 owns a worktree TTL parameter with the
   identical name in `outcome_worktrees.py`. Renaming that one here, or this one there, produces a
   silently wrong signature. Mitigation: this unit touches none of U3's files, and vice versa.
3. **The shipped skill keeps instructing agents to use a deleted mechanism.** These five documents are
   executable instruction, not commentary — a stale `SKILL.md` makes an agent attempt a mechanism that
   no longer exists. Mitigation: the documents ship in this pull request, not a trailing one.
4. `liveness_protocol.py:242`'s `lease_broker` parameter is defaulted to `None` instead of removed,
   leaving a permanent dead parameter in a public signature. Mitigation: stated explicitly above and
   in the acceptance criteria.
5. The old-key compatibility question is never answered, and the parse path silently drops support for
   previously written events. Mitigation: answering it in the pull request body is an acceptance
   criterion.

### Stop conditions
Stop and escalate rather than pressing on if:

- Old events turn out to need to parse under **both** keys — that is a dual-schema requirement, which
  changes the shape of this unit and needs a decision, not an improvised fallback.
- `lease_protocol.py` turns out to contain something that survives the lease concept, so the
  whole-file deletion becomes a partial edit of unclear scope.
- The rename cannot be landed in a single commit for a mechanical reason (for example, a file is owned
  by another in-flight unit).
- Removing the `lease_broker` parameter from `liveness_protocol.py:242` breaks a caller outside the
  files listed here.

### Acceptance criteria
- [ ] `grep -rn "lease_ttl_seconds" plugins/ tests/` returns no matches.
- [ ] `grep -rn "lease-ttl-cold-start" plugins/ tests/` returns no matches.
- [ ] `grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/team-execution/` returns no
      matches.
- [ ] `uv run pytest tests/test_liveness_events.py -q` passes, including the serialize-then-parse
      round-trip under the new key.
- [ ] `uv run pytest tests/test_liveness_engine.py tests/test_team_execution_liveness.py -q` passes.
- [ ] The five renamed sites land in **one** commit — confirm with
      `git show --stat HEAD` naming all of `liveness_engine.py`, `liveness_events.py`, and
      `liveness_protocol.py`.
- [ ] The open compatibility question — whether previously written events must still parse under the
      old key — is answered in the pull request body, not left implicit.
- [ ] `uv run pytest -q` passes with no failures attributable to this unit.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.

### Verification
```bash
rtk proxy uv run pytest -q                      # baseline BEFORE touching anything
uv run pytest tests/test_liveness_events.py tests/test_liveness_engine.py tests/test_team_execution_liveness.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
grep -rn "lease_ttl_seconds\|lease-ttl-cold-start" plugins/ tests/
grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/team-execution/
```

Cross-unit sentinel:

```bash
uv run pytest tests/test_agy_run_lease.py -q   # must pass UNMODIFIED
```

### Notes / conventions
Neither mypy nor a smoke import will catch a half-landed rename here — the failure surfaces as a
`KeyError` the first time an event is parsed. The round-trip test in `tests/test_liveness_events.py` is
the only mechanical guard, so write it first.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U6)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U6

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/683
- Number: 683
- Created at: 2026-07-30T11:38:43.377368+00:00

