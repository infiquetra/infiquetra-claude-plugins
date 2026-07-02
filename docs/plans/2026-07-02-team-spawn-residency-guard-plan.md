---
title: Team-spawn residency guard — warn-first hook for nameless team-family spawns
type: feat
status: active
date: 2026-07-02
origin: infiquetra/infiquetra-claude-plugins#289
---

# Team-spawn residency guard — warn-first hook for nameless team-family spawns

Build the warn-only `PreToolUse` hook from issue #289: when the orchestrator spawns a
team-execution **reviewer or tester** without the named-persistent-teammate shape, emit a one-line
`additionalContext` advisory that the teammate will re-pay full context every consensus/remediation
cycle instead of keeping its prompt cache warm via `SendMessage`. Exit 0 always; the hook observes
the S-1 residency protocol, it never enforces it. Three units: the hook + its decision-surface
tests, registration in `hooks.json`, release surfaces.

## Issue / origin

- Issue: infiquetra/infiquetra-claude-plugins#289 (`capability`, OPEN, `requirements-ready`)
- Upstream WHAT: `docs/brainstorms/2026-06-28-team-spawn-residency-guard-requirements.md`
  (D1–D6, R1–R13 carried forward verbatim below where load-bearing)
- Ideation provenance: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (survivor R6)

## Go/no-go feasibility probe — resolved 2026-07-02, verdict: GO

The requirements gated planning on confirming the spawn tool name and persistence fields against a
live spawn. Resolved from direct sources:

| Question | Answer | Evidence |
|---|---|---|
| Spawn `tool_name` this harness emits | `Agent` (stock Claude Code uses `Task`) | Live transcript `~/.claude-company-bootstrap/projects/.../d19962ce-….jsonl` — `Agent` tool_use with fields `description`, `model`, `prompt`, `subagent_type` |
| Is `subagent_type` a `tool_input` field? | Yes | Same transcript record; one-shot spawn carried `subagent_type: general-purpose`, no `name` |
| Is `name` a `tool_input` field? | Yes — optional; absent on one-shot spawns | Current session `Agent` tool schema (`name`, `subagent_type`, `prompt`, `description`, `isolation`, `mode`, `model`, `team_name`) |
| Is `run_in_background` required for persistence? | **No — the field no longer exists on the `Agent` tool** | Current `Agent` schema has no `run_in_background` property; the live spawn carries none. `consensus-protocol.md:26` prose still names it (stale vs harness — see Deferred Follow-Up) |
| Does PreToolUse honor `additionalContext`? | Yes — injected next to the tool result, JSON processed only on exit 0 | code.claude.com/docs/en/hooks, "Add context for Claude": PreToolUse listed; envelope confirmed as `tool_name` + `tool_input` + `cwd` + `hook_event_name` |
| `subagent_type` addressing format | Plugin-prefixed `team-execution:security-reviewer` is the live addressable type; registries and issue ACs use bare names | Session agent-type roster vs `reviewer-registry.md` tables |
| Are `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PROJECT_DIR` visible to the hook process? | Yes — both are "exported as environment variables to hook processes" | code.claude.com/docs/en/plugins-reference, Environment variables section |
| Matcher semantics for `Agent\|Task` | Exact-string list (letters + `\|` only) — matches `Agent` or `Task` exactly, never `TaskCreate` etc. | code.claude.com/docs/en/hooks, matcher table |
| Installed-plugin layout | Versioned cache: `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`; active version recorded in `installed_plugins.json`; stale version dirs linger (~7 days per docs) | Local: saga `0.46.0` at `cache/infiquetra-plugins/saga/0.46.0`, team-execution `2.6.0` sibling; docs "path changes when the plugin updates" |

**Dependency gate (D6) — cleared.** S-1 (#275, worker×model cache scheduling) is CLOSED. U3/U4
residency prose is live: `consensus-protocol.md:26` mandates named persistent reviewer spawns and
`:51-53` mandates `SendMessage` re-engagement ("never re-spawned from cold"). The hook now guards a
real, shipped protocol — no premature-noise risk.

## Requirements

Carried from #289, re-baselined against the probe.

- R1. Hook fires on `PreToolUse` for the spawn tool and reads `tool_name` + `tool_input` from the
  stdin envelope (same fields `pre_push_gate_hook.py:122-128` reads). Matcher covers **both**
  `Agent` (this harness) and `Task` (stock Claude Code); the decision function is tool-name-agnostic.
- R2. Warn when the normalized `subagent_type` is in the team-family trigger set AND `tool_input`
  lacks a non-empty string `name`. `run_in_background` is **not** required (probe: field no longer
  exists); if present it is ignored.
- R3. Trigger set = team-execution **reviewer + tester** roles (18 agents today: 10 reviewers, 8
  testers). Scanners (4), monitors (2), and operational (`deploy-watcher`) are excluded.
- R4. Trigger set is parsed at hook invocation from the existing registries —
  `reviewer-registry.md` (all reviewer tables) and `validator-registry.md` `## Testers` section —
  plus an operator override via optional env vars (KTD5). No new standalone manifest.
- R5. Any spawn outside the trigger set, or carrying a non-empty `name`, passes silently
  (exit 0, no output).
- R6. On match, emit a single advisory via `hookSpecificOutput.additionalContext`
  (`hookEventName: "PreToolUse"`) and exit 0. Never block, deny, or mutate the spawn.
- R7. The advisory names the agent, states the one-line residency cost (one-shot spawn re-pays full
  context each review/remediation cycle), and gives the fix: spawn with `name` so the teammate is
  re-addressable via `SendMessage` (per `consensus-protocol.md:26,52`).
- R8. Advisory is one concise line — no lecture.
- R9. Malformed/unparseable envelope → exit 0, no output (mirrors `pre_push_gate_hook.py:118-120`).
- R10. Registry files absent or unreadable → empty trigger set, all spawns pass silently (D5;
  mirrors `pre_push_gate_hook.py:142-144`).
- R11. No subprocess, network I/O, or directory walk on the hot path — one stdin read plus two
  small file reads (4.1K + 4.5K) and a set-membership check per invocation.
- R12. Registered as a `PreToolUse` entry in `plugins/saga/hooks/hooks.json`, matcher `Agent|Task`,
  alongside the existing JSON-validate (`Edit|Write|MultiEdit`) and pre-push-gate (`Bash`) entries.
- R13. Trigger decision is a pure function (parsed `tool_input` + trigger set → advisory-or-None)
  with unit tests over that surface, following the `_is_git_push_command` isolation style.

## Key Technical Decisions

- **KTD1 — Persistence predicate is `name`-only; matcher is `Agent|Task`.** The probe shows the
  current `Agent` tool has no `run_in_background` parameter; requiring it would false-warn on every
  correctly-named spawn. Predicate: warn iff trigger-set match AND `name` missing/empty/non-string.
  Matcher `Agent|Task` keeps the hook correct on stock Claude Code (whose `Task` tool carries
  `subagent_type`), and the issue's own acceptance-criteria envelopes use `tool_name: "Task"`.

- **KTD2 — Normalize `subagent_type` by stripping an optional `<plugin>:` prefix.** Live spawns
  address agents as `team-execution:security-reviewer`; registries hold bare names. The decision
  function strips everything up to the last `:` before set membership, so both forms match. A bare
  `security-reviewer` from another plugin colliding is acceptable D4 false-positive noise.

- **KTD3 — Registry location: four-step resolution chain; silent degrade.** The naive
  sibling path is **wrong when marketplace-installed** — the installed layout is versioned
  (`cache/<marketplace>/<plugin>/<version>/`, verified locally: saga `0.46.0` and team-execution
  `2.6.0` under `cache/infiquetra-plugins/`), so from an installed saga root
  `../team-execution` does not exist. Resolution order (first hit wins, pathlib + stdlib-json
  only — no subprocess, honoring R11; deliberately NOT `git rev-parse`, unlike the pre-push gate):
  1. `$CLAUDE_PLUGIN_ROOT/../team-execution/skills/team-execution/references/` — dev-repo layout
     (`plugins/` siblings).
  2. Versioned cache layout — resolve the **active** team-execution version from the plugin
     registry, not by guessing: when `$CLAUDE_PLUGIN_ROOT` matches
     `…/cache/<marketplace>/<plugin>/<version>`, read `ROOT.parents[3]/installed_plugins.json`
     (verified shape: `{"plugins": {"team-execution@<marketplace>": [{"installPath": …,
     "version": …}]}}`), prefer the `team-execution@<marketplace-from-path>` key and fall back to
     any `team-execution@*` key, and use entry `installPath` +
     `skills/team-execution/references/`. Only if that file is absent, unreadable, or lacks the
     key: glob `$CLAUDE_PLUGIN_ROOT/../../team-execution/<version>/` one level and pick the
     highest semver dir containing the references (last-resort heuristic; possible ~7-day
     staleness is advisory-tolerable, D4).
  3. `$CLAUDE_PROJECT_DIR/plugins/team-execution/skills/team-execution/references/` — session
     project root (env var exported to hook processes per plugins-reference docs).
  4. Bounded ancestor scan (≤10 levels) from envelope `cwd`, falling back to process cwd when the
     envelope has none — this is also what makes the manual `printf | python3` acceptance checks
     work from a repo-root shell with no env vars set.
  Nothing found → empty trigger set, silent pass (R10/D5).

- **KTD4 — Parse registries per invocation; no cache file.** Each hook run is a fresh process, so
  "cache" can only mean a materialized data file — which is exactly the drift-prone second source
  R4 forbids. Two ≤5K file reads per spawn is well inside R11. Parse rule: within markdown table
  rows (lines starting `|`), collect backticked tokens matching `[a-z0-9-]+-reviewer` anywhere in
  `reviewer-registry.md`, and any backticked `[a-z0-9-]+` token in `validator-registry.md` between
  the `## Testers` heading and the next `##` heading. The `<name>-reviewer` template literal in
  reviewer-registry's "Adding a New Reviewer" section is not in a table row and contains `<`, so it
  cannot match.

- **KTD5 — Operator override via env vars, not a config file.** `TEAM_SPAWN_GUARD_INCLUDE` /
  `TEAM_SPAWN_GUARD_EXCLUDE` (comma-separated bare agent names) extend/shrink the parsed set.
  Settings-configurable through `settings.json` `env`, zero new files, no dead-wiring. When U3
  worker roles need coverage later, INCLUDE covers the gap until the registry-parse is extended.

- **KTD6 — No debounce in v1.** Stateless by design (D4). The wave-spawn worst case (3 base
  reviewers spawned nameless in one turn) yields 3 one-line advisories, each injected next to its
  own tool result — tolerable, and each is independently actionable. Revisit only if telemetry
  shows advisory fatigue.

## Implementation Units

### U1. Hook: pure decision core + stdin shim

**Summary:** New `plugins/saga/hooks/team_spawn_residency_hook.py` — registry parser, pure decision
function, advisory formatter, `main()` envelope shim.

**Changes:**
- `load_trigger_set(references_dir: Path) -> frozenset[str]` — KTD4 parse of the two registry
  files; missing/unreadable file contributes nothing (R10).
- `_find_references_dir(cwd: str | None) -> Path | None` — the KTD3 four-step chain: plugin-root
  sibling → versioned-cache lookup via `installed_plugins.json` (semver-glob only as last
  resort) → `CLAUDE_PROJECT_DIR` → bounded ancestor scan from envelope/process cwd.
- `decide(tool_input: dict, trigger_set: frozenset[str]) -> str | None` — pure predicate (R2, R5,
  KTD1, KTD2): returns the advisory string on a nameless team-family spawn, else `None`. Applies
  env overrides (KTD5).
- `main()` — reads envelope; malformed → exit 0 (R9); tool_name not `Agent`/`Task` → exit 0; on
  advisory, prints `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
  <one line>}}` and exits 0 (R6, mirrors `stale_main_session_hook.py:235-245`).

**Test scenarios** (`tests/test_team_spawn_residency_hook.py`):
- Nameless `security-reviewer` spawn → advisory returned; advisory names the agent and mentions
  `SendMessage`/`name` (R7).
- Prefixed `team-execution:security-reviewer` nameless → advisory (KTD2).
- Same envelope + `"name": "sec-1"` → `None`; empty-string / non-string `name` → advisory.
- `run_in_background` present or absent changes nothing (KTD1).
- `general-purpose`, `saga:mechanical-executor`, `security-scanner`, `github-actions-monitor`,
  `deploy-watcher` nameless → `None` (R3, R5).
- `load_trigger_set` against the **real repo registries** → exactly the 18 expected names, none of
  the 7 excluded ones, and no `<name>-reviewer` template artifact (R3, R4).
- `load_trigger_set` on a missing/unreadable dir → empty set; `decide` with empty set → `None` (R10).
- `_find_references_dir` (tmp_path fixtures): dev-repo layout resolves via plugin-root sibling;
  versioned cache layout with `installed_plugins.json` pointing at `2.4.0` while `2.6.0` also
  exists on disk → resolves to `2.4.0` (registry is authoritative over max-semver); registry file
  absent/malformed/missing-key → semver-glob fallback picks `2.6.0`; `CLAUDE_PROJECT_DIR` layout
  resolves; bare cwd-ancestor layout resolves; nothing present → `None` (KTD3).
- Env overrides: EXCLUDE removes a reviewer; INCLUDE adds `worker-x` (KTD5).
- Subprocess-level: `printf 'not json' | python3 …` → no output, exit 0 (R9); nameless
  team-family envelope via stdin → stdout JSON parses, has `additionalContext`, exit 0;
  `tool_name: "Bash"` envelope → silent exit 0.

**Test file:** `tests/test_team_spawn_residency_hook.py`

### U2. Registration in hooks.json + registration guard

**Summary:** Wire the hook as a third `PreToolUse` entry; guard the wiring the way
`test_spore_hooks_registration.py` guards the spore pair.

**Changes:**
- `plugins/saga/hooks/hooks.json` — new `PreToolUse` entry, matcher `"Agent|Task"`, command
  `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/team_spawn_residency_hook.py"`.

**Test scenarios** (added to `tests/test_team_spawn_residency_hook.py`):
- `hooks.json` parses; a `PreToolUse` matcher covering both `Agent` and `Task` routes to
  `team_spawn_residency_hook.py` (R12).
- Existing `Bash` → `pre_push_gate_hook.py` and `Edit|Write|MultiEdit` → `validate_json_hook.py`
  entries are untouched (no-regression assert, mirrors
  `test_spore_hooks_registration.py:54-60`).

**Depends on:** U1

### U3. Release surfaces

**Summary:** Version-bump the saga triad; the parametrized drift guard enforces sync.

**Changes:**
- `plugins/saga/.claude-plugin/plugin.json` — `0.47.0` → `0.48.0` (minor: new feature).
- `.claude-plugin/marketplace.json` — saga entry → `0.48.0`.
- `plugins/saga/CHANGELOG.md` — `## 0.48.0` entry describing the warn-only residency guard.

**Test expectation:** none new — `tests/test_release_triad.py` is parametrized over the
marketplace and already fails on any drift among the three surfaces.

**Depends on:** U1, U2

## Scope Boundaries

Carried from #289 unchanged:

- Warn-only; no blocking mode, no `--strict` escalation in v1.
- Stateless; no cross-spawn re-engagement tracking (D4).
- The hook nudges — it never assigns a `name`, rewrites the spawn (`updatedInput` exists but is
  out of scope), or auto-persists the teammate.
- Not enforcement of the residency protocol (KTD4 of S-1 keeps that prose) and not a security
  control.

**Deferred Follow-Up Work** (distinct from non-goals):
- `consensus-protocol.md:26` still instructs `Agent name + run_in_background`, but the harness
  dropped the `run_in_background` parameter. Team-execution prose fix — file separately, not this
  hook's surface.
- Adding worker roles (S-1 U3) to the parsed trigger set once a worker-role registry section is
  worth parsing; until then `TEAM_SPAWN_GUARD_INCLUDE` covers it (KTD5).
- Debounce/advisory-fatigue tuning if telemetry warrants (KTD6).

## Verification

```bash
uv run pytest tests/test_team_spawn_residency_hook.py -v
uv run ruff check plugins/saga/hooks/ && uv run ruff format --check plugins/saga/hooks/
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run pytest tests/test_release_triad.py

# Manual decision checks (issue ACs — bare and prefixed, warn and silent)
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"team-execution:security-reviewer"}}' \
  | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"
printf '{"tool_name":"Task","tool_input":{"subagent_type":"security-reviewer","name":"sec-1"}}' \
  | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"
printf 'not json' | python3 plugins/saga/hooks/team_spawn_residency_hook.py; echo "exit=$?"
python3 -m json.tool plugins/saga/hooks/hooks.json > /dev/null && echo "hooks.json valid"
```
