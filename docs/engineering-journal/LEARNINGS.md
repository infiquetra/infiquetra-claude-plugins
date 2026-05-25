# Learnings — Infiquetra Claude Plugins

> **Empirical findings + mechanisms + fixes + validations.** When something turns out to be true that wasn't obvious — about a plugin's runtime behavior, the marketplace registry, hook timing, skill activation, MCP env propagation, build/test tooling, or a deploy gotcha — it goes here. Include the **evidence** (PR / commit / file:line / reproduction) and the **mechanism** (why it's true), not just the observation.
>
> **Append new entries to the top.** Most-recent first. Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short descriptive title  {#slug}
>
> **Context.** One paragraph framing the situation.
> **Evidence.** Specific PR / commit / file:line / reproduction recipe.
> **Mechanism.** Why it happened (or why it's true) — root cause, not just symptoms.
> **Fix (or queued).** Concrete action + commit hash, OR a QUEUED.md ref if deferred.
> **Validation (if applicable).** What later run / test / install proved the fix.
> **What surprised (optional).** The thing that wasn't in the original mental model.
> **Generalizable rule.** The lesson stripped of this specific incident — what would I tell a future-me hitting a similar shape?
> **Refs.** Cross-links to DECISIONS / QUEUED / narratives / other LEARNINGS entries.
> ```
>
> The `{#slug}` HTML anchor on the entry title makes the entry linkable from `README.md` quick-nav and from cross-references. Keep slugs short and stable.
>
> When new evidence invalidates a learning, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**. Never silently overwrite.

---

## 2026-05-25

### Verification findings while planning the `redis-bridge` plugin  {#redis-bridge-verification}

**Context.** During design of the `redis-bridge` + `hermes-claude-code-router` plan, several "obvious" claims about the Hermes-side infrastructure turned out to be wrong in ways that meaningfully reshaped the architecture. This entry captures the surprises for future plan-verification work.

**Evidence.**
- An earlier exploration agent reported voice-forge on Mac mini as listening at `0.0.0.0:9876` reachable from the LAN. Direct `lsof` proved it bound to `127.0.0.1:9876` only. Not a blocker (Hermes consumes it locally) but the initial plan's "127.0.0.1:9876 from laptop" wiring was wrong.
- `home-lab/ansible/inventory/group_vars/all/all.yml` was assumed to be whole-file vault-encrypted. `ansible-vault view` fails with "Input is not vault encrypted data" — the file uses inline `!vault` tags (field-level encryption). For per-secret extraction, must use `ansible -m debug -a "var=<name>"` or the Python `VaultLib` API, not the CLI.
- Discord voice-receive code was assumed to live in `home-lab/.../asgard_voice_arbiter/`. It doesn't — the arbiter is routing-only (~250 LoC). The actual sink/decode/buffer logic is in closed-source `hermes-agent.gateway.platforms.discord`. Mirroring it from the visible code was impossible; this killed the plan's original "plugin holds Discord directly" architecture and forced the Hermes-router pattern.
- Hermes plugins CAN register MCP-style tools the LLM can call: `ctx.register_tool(name, schema, handler)` at `hermes-extensions/docs/plugin-authoring.md:54`. No existing plugin uses the API yet; the new router will be the first.
- The Claude Code channels protocol does NOT have a native facility for `AskUserQuestion`-style structured questions. Verified by reading the official Discord channel plugin source and `https://code.claude.com/docs/en/channels-reference`. Coaching Claude is insufficient; the CC plugin must intercept the tool call deterministically.
- The Mimir Discord bot (ID `1486896133660868758`, Mount Olympus guild) does NOT currently have a Hermes profile on Mac mini — `~/.hermes/profiles/mimir/` doesn't exist. Building the bridge requires creating the profile first.

**Mechanism.** Earlier exploration agents conflated **proximity** ("X is referenced near Y") with **availability** ("X is implemented in this repo"). Clearest examples: voice-receive (referenced in arbiter, implemented in hermes-agent) and voice-forge (running on Mac mini, but as a local-bound daemon, not LAN-reachable). The agents reported the references; the implementation locations weren't independently verified.

**Fix.** Build proceeds with the architecture the actual ground truth supports: `redis-bridge` stays Hermes-agnostic; Hermes does all voice work via its existing pipeline; vault extraction switches to Python-based per-field; Mimir profile is a prereq before any bridge code runs. The plan's "Prerequisites" section codifies this; the LEARNINGS-flagged "I should have looked here first" findings shaped Decisions [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled) and [askuserquestion-interception](DECISIONS.md#askuserquestion-interception).

**What surprised.** That `ctx.register_tool` exists at all — initially I assumed Hermes plugins were hook-only and the LLM-fallback path would require modifying Hermes core. Reading `hermes-extensions/docs/plugin-authoring.md` end-to-end found the API in the first place I should have looked.

**Generalizable rule.** When a plan rests on "we can mirror Asgard's X" or similar reuse claims, **verify the implementation actually lives where the reference points** before committing to it. Two grep passes are cheaper than a 3–5 day rebuild. Specifically for reuse-of-existing-system claims, check that the visible code is the implementation, not just a thin wrapper around closed-source bits elsewhere.

**Refs.** [redis-bridge-decoupled](DECISIONS.md#redis-bridge-decoupled); plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

---

## 2026-05-08

### Missing optional validator dependencies can hide invalid manifests  {#jsonschema-hidden-validation}

**Context.** CI consolidation restored `marketplace/validator/validate.py` and added `jsonschema` to dev dependencies so schema validation runs in normal CI installs.

**Evidence.** `python3 marketplace/validator/validate.py` passed in the system environment while warning `jsonschema not installed, skipping schema validation`. Running the same validator inside a temporary environment after `pip install -e ".[dev]"` failed on `plugins/sdlc-manager/.claude-plugin/plugin.json` because its description exceeded `marketplace/validator/schema.json`'s 200 character limit.

**Mechanism.** The validator treats missing `jsonschema` as a warning and continues. That made schema validation effectively optional in local and previous CI paths, so an invalid manifest could sit in the repository undetected until the dependency became available.

**Fix.** Added `jsonschema` to project dev dependencies and shortened the `sdlc-manager` plugin description to satisfy the schema limit.

**Validation.** `/tmp/infiquetra-plugins-verify-venv/bin/python marketplace/validator/validate.py` passes with `jsonschema` installed.

**Generalizable rule.** A validator's optional dependency is part of the validation contract. CI must install it, or invalid inputs can pass under a degraded "warning only" path.

**Refs.** `.github/workflows/ci.yml`; `pyproject.toml`; `marketplace/validator/validate.py`; `marketplace/validator/schema.json`.

---

## 2026-05-01

### Plugin code can ship without marketplace registration — the registry is a separate source of truth  {#marketplace-drift}

**Context.** A user reported that the `blueprint-reviewer` plugin did not appear when they tried to install plugins from this marketplace. The plugin's code lived under `plugins/blueprint-reviewer/` on `main` and was fully functional, but it was invisible to the marketplace UI.

**Evidence.**
- `plugins/blueprint-reviewer/` was added by PR #110 (merge commit `ae93035`) and Phase B work merged via PR #111 (commit `a7fea08`).
- Neither PR modified `.claude-plugin/marketplace.json`.
- At time of report: 15 plugin directories under `plugins/` but only 14 entries in `marketplace.json`.
- Fixed in PR #112 (commit `4da5705`).

**Mechanism.** Plugin code in `plugins/<name>/` and the marketplace registry in `.claude-plugin/marketplace.json` are independent files. PR review focused on the new plugin's code (skills, commands, scripts) and overlooked the one-line registry diff. Two PRs in a row missed it because the omission isn't visible in the plugin's own diff — it's a *missing* edit to a sibling file. Reviewers don't see absences.

**Fix.** PR #112 added the `blueprint-reviewer` entry to `marketplace.json` (mirrors `sdlc-manager`'s shape: `source`, `version`, `category: development`, keywords copied from the plugin manifest).

**Validation.** Post-merge: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print(len(d['plugins']))"` returns `15`; `'blueprint-reviewer' in [p['name'] for p in d['plugins']]` is `True`.

**What surprised.** That the bug shipped *twice* in a row (#110 and #111). The second PR was specifically follow-up work on the same plugin; the registry omission was right there to be noticed but wasn't.

**Generalizable rule.** When two files must stay in sync (plugin dir + registry, schema + migration, code + docs index, env var + Lambda config), reviewers will drift one against the other given enough opportunities. Add a CI assertion that fails on drift — don't rely on PR review.

**Refs.**
- [QUEUED.md](QUEUED.md#marketplace-ci-guard) — P1 work item for the CI guard.
- [DECISIONS.md](DECISIONS.md#gitignore-claude-and-no-uv-lock) — repo hygiene shipped alongside.
- [ARCHIVE.md](ARCHIVE.md#pr-112-marketplace-fix) — SHIPPED record.

---

### `marketplace.json` `Edit` calls must include the array's closing `]` in `old_string`  {#marketplace-edit-guard}

**Context.** When appending a new plugin entry to `.claude-plugin/marketplace.json`, the `Edit` tool can produce invalid JSON if the `old_string` doesn't include enough context to capture the array's closing bracket. This has misfired multiple times.

**Evidence.** Repeated occurrences traced through prior memory record `marketplace.json Editing Guard`. The wrong-pattern shape:

```json
    }
  ],
    {
      "name": "new-plugin",
      ...
    }
  ],
  "version": "2.0.0"
}
```

— two closing `]`, parser fails. Caught only by post-edit validation.

**Mechanism.** When `old_string` ends at the last entry's closing `}`, the `Edit` tool inserts the new content *after* the line, which lands it after the array's `]` rather than inside the array. The fix is to include both the previous last entry's closing `}` AND the array's `]` in the `old_string`, so the new entry can be inserted *before* the `]` (with a `,` added to the prior `}`).

**Fix.** Standard pattern — `old_string` extends through the array's closing `]` and at least the next line:

```
old_string: "      \"workflow\"\n      ],\n      \"category\": \"development\"\n    }\n  ],\n  \"version\": \"2.0.0\"\n}"
```

Always validate immediately: `python3 -m json.tool .claude-plugin/marketplace.json > /dev/null`.

**Validation.** PR #112 (commit `4da5705`) used this exact pattern and produced valid JSON on first try.

**Generalizable rule.** When using `Edit` on a JSON/YAML file to append into a nested array, the `old_string` MUST include the array's closing bracket. Inserting "before the `]`" is correct; inserting "after the prior entry's `}`" is wrong because edits land on the line *after* the match. Always validate the file with the language's parser immediately after the edit.

**Refs.** Same lesson cached in `~/.claude/projects/.../memory/marketplace_editing_guard.md` for runtime convenience; this file is the durable project record.

---
