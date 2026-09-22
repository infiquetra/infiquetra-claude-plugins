---
title: Fleet-core: the TypeSafe client, the `jev` tool, the evaluation harness, and the data rule
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: low
mode: execute
handoff_maturity: requirements-ready
---

# Fleet-core: the TypeSafe client, the `jev` tool, the evaluation harness, and the data rule

### Objective

`typesafe_client.py` in fleet-core (stdlib `urllib`, injectable `urlopen`, `getenv`, and clock, the key resolved once from `TYPESAFE_API_KEY` and never logged, a closed status vocabulary, HTTP 529 and rate-limit handling, a deterministic truncation ladder under the 32k-token state limit); a `jev` command-line tool with the verbs the judgment points need (`ask`, `tier`, `triage`, `lenses`, `bucket`, `status`, `journal-route`, `preflight`, `handoff-check`, `roster-check`, `dedupe`, `readiness`, `eval`); an evaluation harness that replays cached answers against labeled outcomes and reports agreement per confidence band; a verdict log with the pinned model version kept outside model context; and the data rule (what may be sent: issue bodies, plan text, diffs after secret redaction; never credentials, transcripts, or customer content).

### Intent

The foundation every other TypeSafe card depends on (TR R1 to R4). Yesterday's probes used a 30-line client (`docs/analysis/2026-09-18-typesafe-jev-research-inputs/jev.py.txt`); the vendor SDKs are days old with breaking changes, so the plugin owns its client.

### Out-of-scope / non-goals

- No judgment point wired into a skill (B2 onward).
- No caching of answers across state changes; freshness is checked before reuse.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py` (new), `plugins/fleet-core/scripts/jev.py.txt` (new), `plugins/fleet-core/scripts/fleet_commons/jev_eval.py` (new), `plugins/fleet-core/references/typesafe.md` (new: the data rule and the verdict log format)
- release surfaces

### Tests to add or update

- `tests/test_typesafe_client.py` with a fake `urlopen`: request shape (`questions` is a dictionary keyed by id), bearer header from the environment, 200, 400, 422, 429, and 529 handling, truncation ladder, no key in any error message.
- `tests/test_jev_cli.py`: each verb round-trips a recorded response; `eval` reproduces the 30-issue benchmark from cached answers.

### Context library links

- coding_standards: _none_

General references:
- TR sections 1, 2, 5 (R1 to R4), 7, 8; https://docs.typesafe.ai/api.md; the probe scripts in `docs/analysis/2026-09-18-typesafe-jev-research-inputs/`

### Acceptance criteria

- [ ] `TYPESAFE_API_KEY=x uv run python plugins/fleet-core/scripts/jev.py.txt ask --state '{"x":"hello"}' --noul 'Is `x` a greeting?' --dry-run` prints the request body and no key.
- [ ] `uv run python plugins/fleet-core/scripts/jev.py.txt ask --state '{"x":"hello"}' --noul 'Is `x` a greeting?'` returns a probability in under 2 seconds with the live key from the environment.
- [ ] `uv run python plugins/fleet-core/scripts/jev.py.txt eval --cached docs/analysis/2026-09-18-typesafe-jev-research-inputs/` reproduces the tier probe's 10 of 10.
- [ ] `uv run pytest tests/test_typesafe_client.py tests/test_jev_cli.py -q` passes.

### Verification

```bash
uv run python plugins/fleet-core/scripts/jev.py.txt ask --state '{"x":"hello"}' --noul 'Is `x` a greeting?'
uv run pytest tests/test_typesafe_client.py tests/test_jev_cli.py -q
```

### Risk

low

a client and a tool with no callers yet; the data rule is the only policy it carries.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1032
- Number: 1032
- Created at: 2026-09-19T14:48:32.600747+00:00

