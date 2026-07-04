---
title: Gate-Divergence Telemetry — Rubber-Stamp Rate for Operator Gates
type: feat
status: active
date: 2026-07-04
origin: infiquetra/infiquetra-claude-plugins#399 (requirements-ready handoff issue; draft docs/sdlc-issue-drafts/plugin-fleet/pf-gate-divergence-telemetry.md, sidecar .json, source docs/plans/2026-07-03-plugin-fleet-grounding-brief.md)
---

# Gate-Divergence Telemetry — Rubber-Stamp Rate for Operator Gates

Phase 0 item 2 of 10 in the `improve-claude-plugins` execution program
(`docs/plans/2026-07-04-plugin-fleet-execution-order.md`). Issue #399,
slug `pf-gate-divergence-telemetry`.

## Problem frame

`plugins/saga/scripts/override_rate_reader.py` (R12) already measures whether the operator's
`orchestration_operator_choice` diverges from `orchestration_recommended` — one gate, one
question, wired into `/retro` Phase 1.6. Every *other* `AskUserQuestion` gate (mode selection,
fix-vs-diagnosis-vs-rethink, per-expansion opt-in, merge/deploy confirmation) records nothing:
no recommendation-vs-answer pair, no latency. Any future argument to auto-progress a gated
status has no evidence for those gates. This plan generalizes the R12 reader shape to a
fleet-wide `gate_divergence` telemetry facet without touching `override_rate_reader.py` or
`gate_verdicts` (a different, already-shipped, automated-check-gate concern).

All citations below were independently re-verified against the current repo state during
planning (not copied from the issue) — see the verification table in KTD1.

## Key Technical Decisions

**KTD1 — Entry encoding: base64-wrapped JSON blobs, pipe-joined.** `gate_verdicts` uses a
`gate:state:ref` colon convention (`saga.py:1145` `parse_gate_verdict`), but that format is safe
only because `state` is a closed 6-value enum (`saga.py:1140-1143`) — colons in `ref` survive
because the parser splits on the *first two* colons only. `gate_divergence`'s `answer` field is
arbitrary `AskUserQuestion` response text with no closed vocabulary, so a positional-colon split
would silently corrupt entries. The `--artifact-pointers` field's help text describes
"pipe-separated typed artifact-pointer JSON blocks" (`saga.py:1295-1298`), but this is a naming
convention only — **verified during this review that nothing in the codebase actually
`json.loads`s an `artifact_pointers` entry** (`grep -rn json.loads plugins/saga/scripts/*.py`
shows no caller reading that field), and the outer split (`_split_list`, `saga.py:1177-1184`) is
a raw `value.split("|")` with no escaping. Treating `--artifact-pointers`'s help text as a
proven precedent would be exactly the "stale claim asserted as fact" failure mode KTD1 of the
#461 plan warns about: a JSON blob whose `answer` field contains a literal `|` (plausible free
text — e.g. an operator typing "fix it | ship as-is") would silently corrupt the pipe split and
misalign every subsequent entry.

`gate_divergence` therefore base64-encodes each entry's JSON blob *before* pipe-joining:
`base64(json.dumps({"gate_id", "offered", "answer", "divergence", "latency_seconds"}))`, one
base64 string per pipe-separated list item. Base64's alphabet (`A-Za-z0-9+/=`) contains no `|`
character by construction, so `_split_list`'s existing raw split is safe regardless of entry
content — no changes to `_split_list` itself, and no new parsing primitive at the CLI layer.
`parse_gate_divergence_entry` reverses this (base64-decode, then `json.loads`) before
validating required keys.

**KTD2 — Latency capture without a second write path.** Gate sites are prose instructions in
skill `SKILL.md` files, executed by the assistant in-session — there is no running process that
can straddle "offer" and "answer" with an in-memory timer. Recording latency therefore requires
the skill instructions to capture two epoch-second timestamps (`date +%s` immediately before the
`AskUserQuestion` call and again immediately after the operator answers) and pass both into the
*same* `saga.py save --gate-divergence` call already used to record the decision — no separate
write helper process or script is introduced. When a skill invocation can't bracket the gate
(e.g. resumed from a prior tick), `latency_seconds` is `null`, never fabricated as `0` (matches
the reader's zero-data-contract discipline, `override_rate_reader.py:20-23`).

**KTD3 — Divergence bit is stored, not derived at read time**, despite `override_rate_reader.py`
deriving over/under-tier at read time from raw `orchestration_recommended`/`orchestration_operator_choice`.
Reason: `override_rate_reader.py`'s two fields are both closed/ordered (`_TIER_ORDER`,
`override_rate_reader.py:49-53`), so read-time comparison is cheap and unambiguous. `gate_divergence`'s
`answer`/`offered` are free text — "did it diverge" is a string-equality check the *write* site
already knows unambiguously (it just saw both values), while a read-time reader would have to
re-implement that same equality check per gate id with no shared vocabulary to lean on. Storing
the bit at write time avoids duplicating that logic across every future gate site and matches the
issue's own AC ("Divergence bit is derived correctly" — a stored, tested field, not a reader-side
inference).

Citation verification (independently re-read from source, this session, all matched the issue's
own citations exactly — no drift found, unlike #461's stale-brief citations):

| Citation | Verified |
|---|---|
| `saga.py:174-175` (`orchestration_recommended`/`orchestration_operator_choice`) | exact match |
| `saga.py:217` (`gate_verdicts` field) | exact match |
| `retro/SKILL.md:188-206` (R12 reader wiring) | matches the "1.6 R12 orchestration telemetry" block |
| `brainstorm/SKILL.md:31`, `founder-review/SKILL.md:80-85`, `investigate/SKILL.md:91-98`, `loop/SKILL.md:72-74`, `outcome/SKILL.md:154-161` | all exact |

## Scope boundaries

**In scope:** new `gate_divergence` field + CLI plumbing on `Saga`; `gate_divergence_reader.py`;
instrumentation text in the 5 cited `SKILL.md` gate sites; `/retro` Phase-1 wiring; tests;
release-surface bump.

**Out of scope (per issue, unchanged):** `override_rate_reader.py`'s own logic/CLI; `gate_verdicts`
semantics; the durable gate-record primitive (`pf-durable-gate-records`, a separate issue);
widening any autonomous-progression allowlist; a new UI/notification surface (renders as a table
in the existing retro evidence block).

## Requirements (from issue #399's Definition of Done)

- R1. New `gate_divergence` full-snapshot list field on `Saga`, following the `gate_verdicts` pattern.
- R2. A recorded entry captures gate id, offered recommendation/default, operator's answer, a
  correct divergence bit, and (when available) latency.
- R3. `gate_divergence_reader.py` reports per-gate-id rubber-stamp rate with a zero-data "no data
  yet" contract and never writes to disk.
- R4. `/retro` Phase 1 runs the new reader read-only alongside `override_rate_reader.py`.
- R5. The 5 cited `AskUserQuestion` gate sites carry instructions to record via the new CLI flag.
- R6. `override_rate_reader.py` and `gate_verdicts` are untouched (regression-tested).
- R7. Release surfaces (CHANGELOG, plugin.json, marketplace.json) updated in the same PR.

## Implementation Units

### U1. `gate_divergence` field + CLI plumbing on `Saga`

Add `gate_divergence: ListOrAbsent = ABSENT` to the `Saga` dataclass (`saga.py`, beside
`gate_verdicts` at line 217), register it in `FRONTMATTER_FIELDS`/the list-field sets (lines
~245-287, mirroring `gate_verdicts`'s registration exactly), and add a repeatable
`--gate-divergence` CLI arg (base64-wrapped JSON blob per KTD1, appended via `argparse.append`,
split into the dataclass field via the existing pipe-join `_split_list` helper — no new parsing
primitive, no change to `_split_list`). Add `parse_gate_divergence_entry(entry: str) -> dict`
that base64-decodes then `json.loads`s one entry and validates required keys (`gate_id`,
`offered`, `answer`, `divergence`) are present and `latency_seconds` is `int | float | None`;
raises `ValueError` with the offending entry echoed on malformed input (matches
`parse_gate_verdict`'s error-message style).

Test expectation: `tests/test_gate_divergence.py::test_records_interaction` — a `saga.py save
--gate-divergence '<base64-json>'` call round-trips through `Saga.save`/`parse_envelope` without
dropping the entry or corrupting fields; `test_gate_divergence.py::test_divergence_bit` —
`divergence` is `true` when `answer != offered`, `false` when equal, computed by the caller (the
CLI does not recompute it, it stores what it's given — KTD3 places correctness at the write
site, i.e. the instrumented skill's own equality check before calling `save`);
`test_gate_divergence.py::test_pipe_in_answer_survives` — an entry whose `answer` field contains
a literal `|` character round-trips intact (regression test for the corruption mode KTD1
identifies); `test_gate_divergence.py::test_roundtrip` — multiple entries across two distinct
`gate_id`s survive a save→parse cycle byte-identical.

### U2. Instrumentation convention (no separate write helper process)

Document the two-timestamp convention from KTD2 as a short reusable snippet
(`plugins/saga/references/gate-divergence-instrumentation.md`, new file) that each instrumented
`SKILL.md` links to rather than repeating: capture `date +%s` before `AskUserQuestion`, capture
it again after the answer, compute `divergence` via string equality against the offered
default/recommendation, base64-encode the JSON blob (`{"gate_id": "...", "offered": "...",
"answer": "...", "divergence": true|false, "latency_seconds": <int|null>}`, per KTD1), and
append `--gate-divergence '<base64-string>'` to the next `saga.py save` call already made in
that skill's flow (no new save call is introduced — this rides the existing tick).

Test expectation: none — this unit is a reference doc, not runnable code; U1's tests cover the
CLI contract this doc points at.

### U3. `gate_divergence_reader.py`

New file `plugins/saga/scripts/gate_divergence_reader.py`, modeled on
`override_rate_reader.py`'s pure-function/injectable-`root` shape (same house pattern, same
`--root`/`--json` CLI surface). Scans saga envelopes, groups `gate_divergence` entries by
`gate_id`, and reports a rubber-stamp rate (`1 - divergence_rate`) per gate id. Zero-data
contract: a `gate_id` (or the reader overall) with no recorded entries reports `None`/"no data
yet", never a fabricated `0%` (mirrors `override_rate_reader.py:20-23` exactly). Never opens
files for writing.

Test expectation: `tests/test_gate_divergence_reader.py::test_per_gate_rate` — a fixture set
(`tests/fixtures/gate_divergence_sagas/`) with entries across ≥2 gate ids produces the correct
rubber-stamp rate per gate id; `test_gate_divergence_reader.py::test_zero_data_reports_no_data_yet`
— an empty root reports "no data yet", not `0%`; `test_gate_divergence_reader.py::test_reader_is_read_only`
— asserts no file under the fixture root is modified (mtime/hash unchanged) after a run.

### U4. Instrument the 5 gate sites

Add a short instrumentation note (pointing at U2's reference doc, not repeating its content) at
each cited `AskUserQuestion` gate: `brainstorm/SKILL.md:31`, `founder-review/SKILL.md:80-85`,
`investigate/SKILL.md:91-98` (the fix-vs-diagnosis-vs-rethink gate specifically, `:222`),
`loop/SKILL.md:72-74`, `outcome/SKILL.md:154-161`. The issue's citations mark the general
`AskUserQuestion` usage guidance in each file, not necessarily one gate per file —
`founder-review/SKILL.md` alone fires this gate at **two** distinct decision points reachable
from that guidance: 0F mode selection (`:133`) and the per-expansion opt-in ceremony (`:144`).
One `gate_id` per **distinct decision point**, not per file: instrument both founder-review
sites separately (e.g. `founder-review-mode-selection`, `founder-review-expansion-optin`); verify
each of the other four files similarly before instrumenting (grounding check at execution time,
not assumed here) — a file cited once may still fire more than one gate. Each note names its
`gate_id` string (stable, kebab-case — e.g. `investigate-fix-vs-diagnosis`, `loop-mode-destination`)
so the reader's per-gate grouping stays meaningful across skills.

Test expectation: none — prose-only change; verified mechanically via
`grep -rn "gate-divergence-instrumentation" plugins/saga/skills/{brainstorm,founder-review,investigate,loop,outcome}/SKILL.md`
returning 5 matches (one per file).

### U5. `/retro` Phase-1 wiring

Add a step immediately after the existing "1.6 R12 orchestration telemetry" block in
`plugins/saga/skills/retro/SKILL.md` (new "1.6a Gate-divergence telemetry") that runs
`gate_divergence_reader.py --root . --json` read-only and includes its output verbatim in the
Phase-1 evidence block, following the same zero-data-contract prose already used for 1.6 (no
narrative fabricated from "no data yet").

Test expectation: `grep -n "gate_divergence_reader" plugins/saga/skills/retro/SKILL.md` returns
at least one match (matches issue AC verification command).

### U6. Tests, fixtures, release surfaces

Write `tests/test_gate_divergence.py`, `tests/test_gate_divergence_reader.py`, and
`tests/fixtures/gate_divergence_sagas/` (≥2 fixture saga envelopes spanning ≥2 gate ids, plus one
empty-root case for the zero-data test). Confirm `tests/test_override_rate_reader.py` still
passes with no diff to `override_rate_reader.py`'s public signatures (R6 regression). Bump
`plugins/saga/.claude-plugin/plugin.json` (`0.51.0` → `0.52.0`, minor: new field + new script,
no breaking change), sync `.claude-plugin/marketplace.json`, add a `plugins/saga/CHANGELOG.md`
entry, **and update the hardcoded version literal at `tests/test_saga_plugin.py:48`**
(`assert plugin_json["version"] == "0.51.0"`) to `"0.52.0"` — verified during this review that
this assertion is a literal string, not a computed read, so it silently fails CI if left
unbumped. Confirm the real version-parity drift-guard test, `tests/test_release_triad.py`
(verified during this review — the issue's suggested name `test_marketplace_drift.py` does not
exist in this repo), passes with the bump reflected.

Test expectation: full gate per the issue's own verification block —
`uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`.

## Closeout (per shared kickoff contract)

- Release surfaces: plugin.json/marketplace.json/CHANGELOG bump in the same PR (U6).
- Phase 0 checklist: tick row 2 (#399) in `docs/plans/2026-07-04-plugin-fleet-execution-order.md`
  in the same PR.
- Board hygiene: move issue #399 to the board's active status via mission-control at plan start
  (already board-onboarded — unlike #461, this issue carries `hermes-task`, confirmed no anomaly).
- Engineering journal: `DECISIONS.md` entries for KTD1–KTD3 in the same commit.
