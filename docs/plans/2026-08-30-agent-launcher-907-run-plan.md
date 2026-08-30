---
title: Agent Launcher session contract run 907 — seven-unit implementation plan
type: fix
status: active
date: 2026-08-30
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/907
backend: inline
---

# Agent Launcher session contract run 907 — seven-unit implementation plan

## Preamble

| Item | Value |
|---|---|
| Repository | `infiquetra/infiquetra-claude-plugins` |
| Branch | `work/cp907-launcher-session-contract` |
| Base commit | `3b2b7083`, verified identical to `origin/main` after `git fetch` at planning time |
| Parent run contract | Issue 907 |
| Units | L1 issue 890, L2 issue 897, L3 issue 896, L4 issue 889, L5 issue 888, L6 issue 887, L7 issue 880 |
| Landing shape | Seven child-scoped commits on this branch, then one integrated pull request and one shared release-surface update |

**The serial rule.** Exactly one unit holds the working tree at a time, and the order L1 through L7
is fixed. L1 before L2 because both edit the function `launch` and L1 establishes both the create
deadline constant and the bound-argv local that L2's guard sits beside. L3 before L4 because L3
introduces the requested-versus-resolved receipt shape that L4's account evidence field reuses. L7
last so the skill document describes behaviour that already exists in the module.

**One commit per child**, message `type(scope): description` referencing the child's issue number.
Release surfaces are touched exactly once, after L7, in an eighth commit — never per unit.

## What was re-resolved, and against what

Every line reference below was found in the current tree rather than trusted from the issue bodies.
The working tree is exactly `origin/main` (`git log --oneline HEAD..origin/main` is empty and
`git diff --stat origin/main` is empty), so the issues' line numbers still resolve — but they were
confirmed one by one, not assumed.

Three external facts the units rest on were re-verified against live systems rather than quoted from
the issues:

1. **`agents --dry-run` accepts a nonexistent model and exits 0.** Re-run on this machine on
   2026-08-30 against `/Users/jefcox/.local/bin/agents` with `-m definitely-not-a-real-model-xyz`;
   the wrapper printed its `backend=`/`mode=`/`tool=` preview and exited 0. Issue 880's central
   claim holds.
2. **`herdr agent list` publishes no permission and no model.** The live JSON row carries
   `agent`, `agent_status`, `cwd`, `foreground_cwd`, `interactive_ready`, `name`, `pane_id`,
   `revision`, `state_change_seq`, `tab_id`, `terminal_id`, `terminal_title`,
   `terminal_title_stripped`, `workspace_id`, and sometimes `agent_session`. Nothing else. So the
   comment at `launcher.py:917` is factually correct and L3's confirmation must be argv-side, never
   a read-back from Herdr.
3. **`herdr pane read` can show the input box, and a client placeholder is visually distinct from
   typed text.** Verified live: an idle Claude pane renders its composer as a line `❯ ` between two
   dim horizontal rules, empty when nothing is staged; an idle Codex pane renders
   `› Ask Codex to do anything`, where the whole line including the marker sits inside a dim
   foreground run (`\x1b[38;2;153;153;153m`). `herdr pane read <pane> --source visible --format ansi`
   returns the styling. This is the evidence L2's discriminator is built on.

## Three findings that change how this run must be executed

These were not in the issue bodies and each one would have produced a red gate or a wrong fix.

### Finding 1 — the module the children name is not the module their tests belong in

Every child names `tests/test_agent_launcher_plugin.py` as "the launcher contract tests", and issue
907's run-level obligation is stated as running that file green with all seven children's cases
present. That file is a **release-surface and installed-layout contract**, 256 lines, whose six
tests check plugin metadata, marketplace registration, packaged file lists, and Orchestrate's
fail-fast behaviour when the launcher plugin is absent. It exercises no launcher behaviour at all.

The behaviour tests live in `plugins/agent-launcher/tests/test_launcher_contract.py` — 36 tests
covering argv construction, preview confirmation, launch stops, ownership, receipt separation, and
cleanup. That is where six of the seven units' cases belong.

**Consequence for the plan.** Behaviour tests for L1 through L6 go into
`plugins/agent-launcher/tests/test_launcher_contract.py`. `tests/test_agent_launcher_plugin.py`
still changes, but only for the release surfaces (see Finding 2). The coexistence obligation
therefore spans both modules and the run's green check is:

```bash
uv run pytest plugins/agent-launcher/tests/test_launcher_contract.py \
              tests/test_agent_launcher_plugin.py \
              tests/test_orchestrate_vendor_permissions.py \
              tests/test_orchestrate_task_dispatch.py \
              tests/test_orchestrate_account.py \
              tests/test_plugin_manifest_loader_contract.py -q
```

`tests/test_orchestrate_account.py` is in that list because L4 changes the account chain those 863
lines exercise, and `tests/test_plugin_manifest_loader_contract.py` because it holds one of the three
dependency-floor pins the release commit moves. Neither was in the first draft of this plan; both
would otherwise have been discovered as a red gate.

### Finding 2 — the release bump breaks two version-equality pins, and separately three floor pins

`tests/test_agent_launcher_plugin.py` pins the Agent Launcher version to the literal `"1.0.0"` in
two places:

- `test_agent_launcher_metadata_is_marketplace_registered` asserts `plugin_json["version"] == "1.0.0"`
- `test_orchestrate_declares_agent_launcher_dependency_in_metadata` asserts `launcher_entry["version"] == "1.0.0"`

A version bump without editing both turns the gate red.

Those two are **version-equality** pins on the launcher manifest. They are a different set from the
**three dependency-floor** pins on `>=1.0.0` that the release commit must also move, which live in
three separate files and are enumerated in the release section. Five assertions in total, plus one
prose sentence in Orchestrate's own skill. All of them belong in the single release-surface commit,
not scattered across units.

### Finding 3 — `reused` names the workspace, not the pane, so L2 keyed on the wrong field

Issue 897's acceptance says "a pane recorded `reused=true` is inspected". But `wrapper_reused`
(`launcher.py:54-63`) documents, in the module's own words, that the bit means *the workspace
already existed*, and that it "is not tab ownership". `SKILL.md` says the same. The existing test
`test_ownership_is_tab_id_not_in_prelaunch_snapshot` asserts `reused is True` and `owned is True`
simultaneously, proving the two are independent and that `reused=true` is the ordinary case for
every launch inside an existing Herdr workspace.

Keying the guard on `reused` would therefore inspect the pane on essentially every launch, including
freshly created panes whose box is known empty — which issue 897's own out-of-scope list forbids
("Do not add a general pane-content watcher or read pane content on the ordinary create path, where
the box is known empty").

**Resolution — settled, not open.** The correct discriminator is `session_owned(unit)` being false:
the launcher could not prove it created this tab, so the pane may carry text from before. The
planning role and an independent document review reached that conclusion from the same evidence, and
the coordinator has recorded the amendment on issue 897:

> The guard keys on ownership (`session_owned(unit)` being false), not on `wrapper_reused`. Issue
> 897's literal acceptance sentence naming `reused=true` is superseded, because `wrapper_reused` is
> a workspace-level bit and keying on it would read pane content on the ordinary create path, which
> issue 897's own out-of-scope clause forbids.

Concretely, issue 897's acceptance "a pane recorded `reused=true` is inspected" is replaced by "a
pane whose launch receipt records `owned=false` (the launcher did not create the tab) is inspected",
and its positive case "a freshly created pane (`reused=false`)" is replaced by "a freshly created
pane (`owned=true`)". Wrapper `reused` remains a workspace bit and is not the guard key.

Amendment: https://github.com/infiquetra/infiquetra-claude-plugins/issues/897#issuecomment-5469528122

**L2 is unblocked.** No operator ruling is outstanding on this point and the guard is not to be
retargeted onto `reused`.

---

## L1 — bound the session create (issue 890)

**Issue.** 890 — the session create has no timeout, so a hanging wrapper hangs the launcher.

### Current behaviour

`plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py:1015`, inside `launch`
(defined at `:1013`):

```python
def launch(unit: Any, backend: str = "inline", *, review_elsewhere: bool = False) -> None:
    preexisting = list_tab_ids()
    proc = run(agent_argv(unit))
```

`run` is defined at `:264` with `check: bool = True, timeout: float | None = None`, so this call is
both checked and unbounded. Its own docstring says a timeout "is reported as a non-zero result, so
callers handle it as 'no answer' rather than as a crash" — the 124 convention lives on the
`check=False` branch at `:288`:

```python
    except subprocess.TimeoutExpired:
        if check:
            raise SystemExit(f"timed out after {timeout}s: {' '.join(cmd)}") from None
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timed out")
```

Every sibling stage is bounded: `LAUNCH_SETTLE_SECONDS = 30.0` (`:487`),
`DELIVERY_CHECK_SECONDS = 15.0` (`:488`), `ACCOUNT_SETTLE_SECONDS = 10.0` (`:495`), and both
dry-run previews in `cli_main` pass `timeout=20`. The create is the only unbounded step.

### Change

1. **New constant** beside the existing deadlines at `launcher.py:487-495`:

   ```python
   # How long to give the wrapper to create the session. Larger than every other deadline on
   # purpose: this one call may reach another machine over SSH and cold-start a vendor CLI, where
   # the dry run it follows (timeout=20 in cli_main) only echoes a command line.
   LAUNCH_CREATE_SECONDS = 120.0
   ```

2. **Bind the argv once and bound the call** at `:1015`. `agent_argv` is called a single time so the
   command reported in a failure is exactly the command that ran, and so L2 and L3 have the argv
   available in the same scope:

   ```python
   argv = agent_argv(unit)
   proc = run(argv, check=False, timeout=LAUNCH_CREATE_SECONDS)
   if proc.returncode == 124:
       raise SystemExit(
           f"{unit.name}: session create timed out after {LAUNCH_CREATE_SECONDS}s; "
           "no session was confirmed created"
       )
   if proc.returncode != 0:
       err = (proc.stderr or proc.stdout or "").strip()
       raise SystemExit(f"command failed ({proc.returncode}): {' '.join(argv)}\n{err}")
   ```

   `check=False` is what produces the 124-as-result shape issue 890 asks for. The nonzero branch
   reproduces `run`'s own `command failed ({returncode}): {cmd}\n{err}` message verbatim, so the
   existing stop keeps its exact shape and the existing test that matches on `"command failed"`
   still passes.

3. Nothing else in `launch` changes. The malformed-receipt stop below it is untouched, no retry is
   added, and the receipt gains no field.

### Tests

All in `plugins/agent-launcher/tests/test_launcher_contract.py`.

| Test | What it does | Mutation it kills |
|---|---|---|
| `test_hanging_create_stops_at_the_deadline` | Writes a **real** wrapper script `#!/bin/sh\nsleep 5\n` followed by valid JSON, puts it on `PATH`, monkeypatches `launcher.LAUNCH_CREATE_SECONDS` to `0.5`, times the call, and asserts `SystemExit` matching `"timed out after"` with elapsed under 3 seconds | Removing `timeout=LAUNCH_CREATE_SECONDS` from the `run` call. The wrapper then completes after 5 seconds and the launch proceeds past the create, so the `match="timed out after"` assertion and the elapsed assertion both die |
| `test_launch_create_deadline_is_a_named_constant` | `inspect.getsource(launcher.launch)` contains `"LAUNCH_CREATE_SECONDS"`; the constant is a float in `(0, 300]` | Inlining the literal, or neutering the shipped constant to an effectively-infinite value |
| `test_create_within_the_deadline_is_unaffected` | Real wrapper returning JSON immediately, real `LAUNCH_CREATE_SECONDS`, preflight stubbed to stop; asserts `unit.tab_id` was recorded | A deadline so small it breaks ordinary launches |

**No harness substitution.** The first and third tests run a real `/bin/sh` wrapper through a real
`subprocess.run` with a real timeout — the component under test is `subprocess`'s own deadline, and
no fake stands in for it. This follows the existing pattern in
`test_nonzero_wrapper_exit_stops_launch` and `test_malformed_receipt_stops_launch`.

### Risk and interaction with adjacent units

- **Existing tests at risk:** `test_nonzero_wrapper_exit_stops_launch` matches `"command failed"`.
  The hand-rolled message preserves that string exactly; if the implementer paraphrases it, that
  test goes red and the paraphrase is the bug, not the test.
- **L2 depends on the bound `argv` local** existing in `launch`. Doing L1 first is what makes L2 and
  L3 a small diff rather than a re-shuffle of the same function.
- **A 120-second bound is a judgement, not a measurement.** No hang has been timed. If the runtime
  checkpoint shows a legitimate remote launch approaching it, the constant moves; the shape does not.
- **Rejected alternative:** keeping `check=True` and adding only `timeout=` is a one-argument diff
  and bounds the call, but it raises `SystemExit("timed out after …")` from inside `run` and never
  produces the 124 result the issue explicitly names. Recorded here so review does not re-derive it.

### Acceptance

- The session-creating call passes `timeout=LAUNCH_CREATE_SECONDS`.
- A wrapper hanging past the deadline yields the 124 result and a named stop, not a block.
- A create finishing inside the deadline is unchanged.
- Malformed-receipt and nonzero-exit stops keep their message shapes.
- The deadline is a named module constant beside the existing ones.
- Removing the timeout argument fails `test_hanging_create_stops_at_the_deadline`.

---

## L2 — inspect a pane the launcher did not create before prompting it (issue 897)

**Issue.** 897 — a reused pane is prompted without inspecting its input box for staged text.

### Current behaviour

The launcher computes reuse and ownership and records both, then prompts regardless.

- `wrapper_reused` at `launcher.py:54-63` — the wrapper's workspace bit, explicitly "not tab
  ownership".
- `tab_was_created` at `launcher.py:84-89` — `tab_id not in preexisting`, the real ownership test.
- `record_wrapper_identity` at `launcher.py:99-127` records `reused` at `:119` and `owned` at
  `:120` into `unit.launch_receipt`.
- `launch` calls `send(unit, pane_id, backend, review_elsewhere=review_elsewhere)` at
  `launcher.py:1034`. Between `verify_unit_preflight` at `:1032` and that send there is no read of
  the pane's input box.
- `read_pane` at `launcher.py:631-641` already reads a pane and returns its text **raw**; stripping
  is the caller's job, done by `confirm_opencode_variant_selected` at `:652` via
  `strip_ansi(read_pane(...))`. Its two callers are that confirmer and
  `drive_opencode_variant_selection` at `:680`. A separate ANSI reader is still needed because L2's
  discriminator depends on styling that `strip_ansi` would discard, but `read_pane` itself is not
  the thing that discards it.

The observed incident: a worker pane whose receipt recorded `reused=true` held an unsent slash
command nobody on the run had typed, and any Enter reaching it would have run a document review
inside the session that authored the material under review.

Per Finding 3, the guard keys on `session_owned(unit)` being false, not on `reused`.

### Change

1. **A marker table and a pure discriminator**, added beside `read_pane` at `launcher.py:631`:

   ```python
   # The glyph each vendor's composer draws at the start of its input line. Verified live on
   # 2026-08-30: claude draws U+276F between two dim rules, codex draws U+203A. A plain ">" is
   # included for a vendor that draws no decorated marker.
   COMPOSER_MARKERS = ("❯", "›", ">")

   def composer_staged_text(ansi_text: str) -> str | None:
       """Text a human staged in the input box, or None when no composer line was found.

       A client's own placeholder is drawn inside a styled run -- codex's "Ask Codex to do
       anything" arrives wrapped in a dim foreground SGR, and claude's hints the same way --
       while text somebody typed carries no styling. Discarding a placeholder is harmless and
       discarding staged operator text is not, so only unstyled runs count as staged.
       """
   ```

   Implementation shape: split the last composer-marker line into styled and unstyled runs by
   scanning `\x1b\[[0-9;]*m` sequences, keep the runs that are active under no SGR or under a plain
   reset, drop the marker glyph itself, strip, and return. Return `None` when no line's first
   non-space glyph is in `COMPOSER_MARKERS`.

2. **A named deadline**, beside the existing ones at `launcher.py:487-495`:

   ```python
   # How long to give one pane read before the input-box inspection gives up. A pane read is a
   # local socket round trip, so this is a bound on a wedged herdr rather than a wait for work.
   PANE_INPUT_READ_SECONDS = 5.0
   ```

3. **A reader**, `pane_input_text(pane_id: str) -> str | None`, running
   `["herdr", "pane", "read", pane_id, "--source", "visible", "--format", "ansi"]` with
   `check=False, timeout=PANE_INPUT_READ_SECONDS`, returning `composer_staged_text(proc.stdout)` on
   a zero return code and `None` otherwise — a timeout (return code 124) reads as unreadable, not as
   an empty box.

4. **A guard**, `guard_reused_pane(unit, pane_id) -> None`, called in `launch` immediately before
   the first `send` at `launcher.py:1034` and only when `session_owned(unit)` is false:

   - `None` (composer unreadable, or the read failed) — `append_unit_note` with
     `"input box not readable; prompted without inspection"`, set `unit.launch_receipt["input_box"]
     = "unreadable"`, and proceed. Visible, not silent.
   - `""` — set `unit.launch_receipt["input_box"] = "empty"` and proceed. Exactly one extra round
     trip, no behaviour change.
   - Non-empty — record the text into the receipt as `{"input_box": "staged", "input_box_text": …}`
     and into a unit note **before** raising, then:

     ```python
     raise SystemExit(
         f"{unit.name}: pane {pane_id} already holds staged input {staged!r}; refusing to "
         "prompt so the dispatched task cannot be concatenated onto it"
     )
     ```

     A named stop, and nothing is cleared — a stop discards nothing, which is the strongest reading
     of "never silently discarded". No confirmation prompt is added anywhere.

5. **`SKILL.md`** gains a paragraph in the verified-launch section stating that a session whose tab
   the launcher did not create has its input box inspected before any prompt, that staged text is a
   stop rather than a clear, and that a client placeholder is not staged text.

### Tests

Discriminator tests are pure functions over literal ANSI strings — no subprocess, no pane.

| Test | File | What it asserts | Mutation it kills |
|---|---|---|---|
| `test_composer_placeholder_is_not_staged_text` | contract | `composer_staged_text("\x1b[38;2;153;153;153m› Ask Codex to do anything\x1b[0m")` returns `""` | Treating any non-empty composer line as staged, which would stop every Codex launch |
| `test_composer_typed_text_is_staged` | contract | `composer_staged_text("❯ /saga:doc-review docs/plans/x.md")` returns the slash command | Collapsing the styled/unstyled distinction to "always empty", which would disarm the guard |
| `test_composer_absent_reads_as_unreadable` | contract | A pane dump with no marker line returns `None` | Returning `""` for an unparseable pane, which would silently claim the box was empty |
| `test_reused_pane_holding_a_slash_command_is_not_prompted` | contract | Drives `launch` with `owned=False` and a fake `run` answering the ANSI pane read with the observed staged line; asserts `SystemExit` matching `"already holds staged input"`, that the recorded `send` call list is empty, and that `unit.launch_receipt["input_box_text"]` carries the exact text | **Deleting the `guard_reused_pane` call** — `send` is then called and no `SystemExit` is raised |
| `test_staged_text_is_recorded_not_discarded` | contract | Same setup; asserts the note and the receipt both carry the text | A guard that stops but records nothing |
| `test_empty_reused_box_is_prompted_exactly_as_today` | contract | Composer `❯ ` with `owned=False`; asserts `send` called once and exactly one `pane read --format ansi` command in the recorded list | An inspection that loops or re-reads |
| `test_freshly_created_pane_takes_no_inspection_path` | contract | `owned=True`; asserts no `--format ansi` pane read appears in the recorded commands | Keying the guard on `reused` instead of ownership, which would read the pane on the ordinary create path |

`tests/test_orchestrate_task_dispatch.py` gains one case asserting an Orchestrate-dispatched unit
inherits the same guard through the ingested module, since Orchestrate consumes this exact function.

**No harness substitution.** The four discriminator tests call the real parser on real captured
byte shapes. The four `launch` tests replace `launcher.run` — the same monkeypatch the existing
`test_ownership_is_tab_id_not_in_prelaunch_snapshot` uses — but the code path under test (the guard
call site and its branching) is the real one, and the assertion that `send` was **not** called is
what proves it.

### Risk and interaction with adjacent units

- **Fail-open on an unreadable composer is a deliberate weakening.** A vendor whose composer this
  parser cannot find is prompted as it is today, with a note. The alternative — stopping — would
  break every launch into a vendor whose composer shape has not been characterised, and the observed
  incident was Claude. The choice is recorded in the receipt so a run can be audited for it.
- **Only two vendors' composers are verified** (Claude and Codex, live, 2026-08-30). The others are
  covered by the plain `>` marker or fall to the unreadable branch. Characterising the rest belongs
  to the runtime checkpoint, not to a guess in this plan.
- **Touches the same function as L1**, which is why L1 lands first. The guard call sits between
  `verify_unit_preflight` and `send`; L1's edit is above it and does not move.
- **Receipt gains fields.** Issue 897 does not forbid this; issues 890 and 887 forbid it inside
  *their* scopes, and neither L1 nor L6 adds one.

### Acceptance

- A session whose tab the launcher did not create has its input box inspected before any prompt.
- A prompt is never concatenated onto pre-existing input-box text.
- Non-empty staged text is a named stop with the text recorded in the note and the receipt.
- A client placeholder is distinguished from staged text and the discriminator is asserted directly.
- An empty box and a freshly created pane behave as today.
- No change is made to, or required of, Herdr or the wrapper.
- Deleting the guard call fails the two negative tests.

---

## L3 — honour and confirm a declared worker permission (issue 896)

**Issue.** 896 — Orchestrate and Agent Launcher never confirm a declared worker permission, so a run
silently proceeds under `auto`.

### Current behaviour

Three mechanisms, all re-resolved in the current tree.

**The silent fallback.** `launcher.py:457`, inside `agent_argv` (defined at `:436`):

```python
    modes = VENDOR_PERMISSION.get(unit.vendor, {})
    argv.extend(modes.get(unit.permission, modes.get("auto", [])))
```

A value outside that vendor's map falls through to the `auto` flag set with no error. `agy` and
`qwen` map `auto` to `[]`, so a typo there emits nothing at all.

**Permission excluded from verification.** `launcher.py:917`, inside `verify_unit_preflight`:

```python
    unconfirmed: list[str] = ["model", "permission"]  # herdr publishes neither
```

That comment is correct — the live `herdr agent list` row carries no permission field, verified
above — so the fix cannot be a Herdr read-back. The receipt records only the *requested* value, at
`launcher.py:121` in `record_wrapper_identity` and again at `launcher.py:991` in the preflight
receipt, both `"permission": getattr(unit, "permission", None)`.

**Omission inherits `auto` invisibly.** `orchestrate.py:245` declares `permission: str = "auto"` on
`Unit`, and `orchestrate.py:1807`, in `rebuild_unit`'s docstring, records that `permission` is among
the fields left at their defaults. Plan ingest is `plan_units`, which builds each unit with
`Unit(**raw)` at `orchestrate.py:931` and never notices that `raw` had no `permission` key.

The launcher's own CLI is already safe: `_add_launch_flags` declares `--permission` with
`choices=("auto", "bypass")` at `launcher.py:1284`. The unguarded path is reachable only from an
Orchestrate plan or a directly constructed `LaunchRequest`, which is precisely how the live incident
arrived.

### Change

**In `launcher.py`:**

1. New function beside `VENDOR_PERMISSION` (`:222-258`):

   ```python
   def resolve_permission(vendor: str, permission: str) -> list[str]:
       """The flags this vendor takes for this posture, or a stop naming what was asked for.

       A vendor absent from the table has no permission ladder and legitimately emits nothing.
       A posture absent from a vendor that HAS a ladder is a typo or a spelling from another
       vendor, and quietly handing it the auto flag set is how a run comes up in a posture it
       did not declare.
       """
       modes = VENDOR_PERMISSION.get(vendor)
       if modes is None:
           return []
       if permission not in modes:
           raise SystemExit(
               f"unknown permission {permission!r} for vendor {vendor!r}; "
               f"expected one of {sorted(modes)}"
           )
       return list(modes[permission])
   ```

2. `agent_argv` at `:457` becomes `argv.extend(resolve_permission(unit.vendor, unit.permission))`.
   The `auto` default is untouched: `"auto"` is a key in every vendor's map, so a unit that declares
   nothing behaves byte-for-byte as today.

3. `verify_unit_preflight` gains a keyword-only `argv: list[str] | None = None`, and `launch` passes
   the argv it already bound in L1. When `argv` is given:

   - `tokens = resolve_permission(unit.vendor, unit.permission)`
   - If `tokens` is non-empty and does not appear as a contiguous run in `argv`, close the session
     and stop: `f"{unit.name}: declared permission {unit.permission!r} resolves to {tokens} but the
     launch argv does not carry it"`.
   - **`"permission"` stays in `unconfirmed` and never enters `confirmed`.** The receipt key that
     list lands in is `confirmed_against_herdr`, and the docstring at `launcher.py:906-911` defines
     it as what Herdr published. Herdr publishes no permission — verified live — so putting an
     argv-derived fact there would make the receipt claim something the module elsewhere denies.
   - Argv confirmation gets its **own channel**, beside the requested value rather than inside
     Herdr's:

     ```python
     "permission_resolved": {
         "mode": unit.permission,          # the posture that was declared
         "tokens": tokens,                 # the flags it resolved to, [] when the vendor emits none
         "confirmed_from": "launch_argv",  # or None when no argv was supplied to check against
     },
     ```

     The existing `"permission"` key keeps holding the requested value. That is the
     requested-versus-resolved shape L4 reuses.
   - When `tokens` is empty because the vendor emits no flag for that mode (`agy`/`qwen` `auto`),
     `confirmed_from` is still `"launch_argv"` and `tokens` is `[]` — an honest record that the
     posture resolved to no flag, rather than a claim that a flag was seen.
   - When `argv` is `None` (a direct call, as several existing tests make), behaviour is exactly as
     today and `confirmed_from` is `None`. This is what keeps
     `test_herdr_readback_receipt_separates_confirmed_from_requested` green unchanged on the no-argv
     path, including its `assert "permission" in receipt["requested_only"]`.

4. **`SKILL.md:32`** is rewritten in this unit, because it currently reads "model and permission stay
   `requested_only` because `herdr agent list` does not publish them" — true of model, and now
   misleading about permission. It becomes: model stays `requested_only` because `herdr agent list`
   does not publish it; permission is not published by Herdr either, so it is confirmed against the
   launch argv instead and recorded under `permission_resolved`. **L7 must preserve this rewrite.**

**In `orchestrate.py`:**

5. One new field on `Unit`, which is the single unit-model field this run is permitted:

   ```python
   permission_declared: bool = True
   """Whether the plan row that produced this unit named `permission` explicitly.

   False means the unit inherited the default. Recorded because a run that declared a posture and
   a plan that omitted the field produce a worker in `auto` with nothing on screen to say so."""
   ```

   It is a declared dataclass field with a default, so `asdict` round-trips it and `read_unit`'s
   `Unit(**raw)` at `orchestrate.py:876` accepts a run record written before it existed.

6. In `plan_units`, immediately after `Unit(**raw)` at `orchestrate.py:931`, set
   `unit.permission_declared = "permission" in raw`. Before returning, print one line naming every
   unit that omitted it: `f"permission not declared, inheriting {default}: {', '.join(names)}"`.
   Nothing is rejected — issue 896 explicitly does not require plans to state permission.

   No run-level permission field is invented. `Run` carries `workspace` and `account` but no
   posture, and adding one would exceed the single-field allowance.

7. The Agent Launcher `SKILL.md` gains a sentence stating that permission is granted at launch and
   is not correctable in place: cycling a live session's permission control moves only through
   manual, accept-edits, plan and back to auto, so a session that came up in `auto` must be torn
   down and relaunched.

8. **`plugins/orchestrate/skills/orchestrate/SKILL.md:84`** states the dependency floor in prose —
   "Orchestrate declares `agent-launcher >=1.0.0` as a dependency". L3 is what makes Orchestrate
   depend on the launcher's new `resolve_permission`, so that sentence is raised to `>=1.1.0` in the
   release commit, and this unit records the dependency rather than silently creating it (finding
   D11).

### Tests

| Test | File | What it asserts | Mutation it kills |
|---|---|---|---|
| `test_unknown_permission_is_a_named_stop` | `tests/test_orchestrate_vendor_permissions.py` | `Unit(vendor="claude", permission="bypasss")` through `agent_argv` raises `SystemExit` matching `"unknown permission"`; the argv is never built | **Restoring `modes.get(unit.permission, modes.get("auto", []))`** — the argv builds silently with the auto flags and no exception is raised. This is the highest-value assertion in the unit |
| `test_unknown_permission_does_not_receive_the_auto_flag_set` | vendor permissions | Under `pytest.raises`, asserts nothing was appended; and separately that `resolve_permission("claude", "bypasss")` never returns `["--permission-mode", "auto"]` | A "fix" that warns and then falls back anyway |
| `test_declared_bypass_missing_from_argv_is_a_named_stop` | contract | Calls `verify_unit_preflight` with a hand-built `argv` from which the bypass tokens were removed; asserts `SystemExit` naming the unit, the declared posture, and the resolved tokens | Dropping the argv read-back and trusting the request |
| `test_receipt_records_resolved_posture_distinctly` | contract | `receipt["permission"] == "bypass"`, `receipt["permission_resolved"]["tokens"] == ["--permission-mode", "bypassPermissions"]`, `receipt["permission_resolved"]["confirmed_from"] == "launch_argv"`, and `"permission"` is still in `requested_only` and **not** in `confirmed_against_herdr` | Recording only the requested value, or moving an argv-derived fact into the Herdr-published channel |
| `test_no_argv_leaves_permission_unconfirmed` | contract | `verify_unit_preflight` with no `argv` yields `permission_resolved["confirmed_from"] is None` and `"permission" in requested_only` — the shape `test_herdr_readback_receipt_separates_confirmed_from_requested` already asserts | A change that confirms permission on a path with nothing to confirm it against |
| `test_skill_no_longer_calls_permission_herdr_requested_only` | contract | The `SKILL.md` sentence at line 32 no longer groups permission with model as Herdr-`requested_only`, and does name `permission_resolved` | Leaving the skill contradicting the receipt |
| `test_every_vendor_bypass_still_emits_its_documented_flag` | vendor permissions | Parametrised over `VENDOR_PERMISSION.keys()`; each vendor's `bypass` argv tail still equals today's | A refactor that changes the flags while making the guard pass |
| `test_auto_and_omitted_permission_are_unchanged` | vendor permissions | `permission="auto"` and a unit constructed without the field both produce today's argv exactly | Changing the default |
| `test_a_vendor_absent_from_the_table_emits_nothing` | vendor permissions | `resolve_permission("nosuchvendor", "bypass") == []` and no stop | A guard that stops on vendors with no ladder |
| `test_plan_omission_of_permission_is_reported` | `tests/test_orchestrate_task_dispatch.py` | `plan_units` on a plan whose unit lacks `permission` sets `permission_declared is False` and prints a line naming the unit (captured with `capsys`) | Silent inheritance |
| `test_declared_permission_survives_a_run_record_round_trip` | task dispatch | `asdict` then `Unit(**raw)` preserves `permission_declared` | A loose attribute that `asdict` drops |

**No harness substitution.** `agent_argv` resolves the wrapper for real — the existing
`launcher_on_path` fixture in `tests/test_orchestrate_vendor_permissions.py` puts a real executable
on `PATH` for exactly that reason, and every new argv test reuses it rather than stubbing
`launcher()`.

### Risk and interaction with adjacent units

- **Cross-parent collision.** Issue 909's child issue 900 also edits Orchestrate's unit model.
  **L3 and that child must not hold worktrees at the same time.** The conflict is mechanical: both
  add a field to the same dataclass. Confirm before starting L3 that issue 900 is not in flight; if
  it is, that is a stop condition, not something to merge around.
- **`opencode` maps `auto` and `bypass` to the same `["--auto"]`.** The resolved record will show
  identical tokens for both, which is the truth and is already documented in the table's own
  comment. Nothing is invented to hide it.
- **`verify_unit_preflight` gains a parameter.** It is keyword-only with a `None` default, so every
  existing caller and every existing test is unaffected. That is what makes this a small diff.
- **L4 builds on the receipt shape introduced here.** Doing L4 first would mean inventing the shape
  twice.
- This grants no new capability. A declared posture that previously degraded silently now stops; the
  `auto` default and every credential, shell, filesystem and Git boundary are untouched.

### Acceptance

- A permission outside the vendor's map is a named stop, never a silent `auto`.
- A declared posture absent from the resolved argv is a named stop naming unit, posture, and tokens.
- The receipt records the resolved posture distinctly from the requested one.
- Inheriting the default because a plan omitted the field is printed.
- The `auto` default is unchanged for units and runs that declare nothing.
- Every vendor still emits its documented bypass flag.
- `SKILL.md` states permission is launch-granted and not correctable in place.
- Restoring the silent fallback fails `test_unknown_permission_is_a_named_stop`.

---

## L4 — refuse to confirm an account from a transcript that predates the launch (issue 889)

**Issue.** 889 — the statusline-silent fallback can confirm a stale worktree transcript.

### Current behaviour

`launcher.py:830-847`:

```python
def observed_account(unit: Any, pane_id: str | None, seconds: float) -> str | None:
    deadline = time.monotonic() + seconds
    while True:
        from_pane = pane_account_label(pane_id)
        if from_pane:
            return from_pane
        from_transcript = transcript_account(unit)
        if from_transcript:
            return from_transcript
        if time.monotonic() >= deadline:
            return None
        time.sleep(1.0)
```

The transcript fallback is at `:842`. `transcript_account` (`:783-801`) picks the newest transcript
across the two roots by `st_mtime` and returns its account label; `find_claude_transcripts`
(`:770-781`) globs every `.jsonl` under the worktree's project slug. Nothing ties any of those files
to the session just launched, so a relaunch after a wrong-account launch — the exact case the
docstring at `:786` describes — can certify the earlier account.

`check_unit_account` (`:850-888`) already treats `None` as a stop, so the fix does not need a new
failure path; it needs the fallback to stop lying.

### Change

**The compatibility decision, made here rather than left to the implementer (finding D4).** An
omitted `since` **keeps today's fallback behaviour** — the transcript roots are still consulted with
no floor. The floor is passed only from `launch`, which is the one path where a launch instant
actually exists.

The alternative — treating an absent floor as "no evidence" — is the stricter rule and was this
plan's first draft, but it turns `tests/test_orchestrate_account.py` red: four cases in
`TestPostLaunchAccountVerification` (at lines 310, 350, 401 and 449) call
`verify_unit_preflight(unit, "pane-1", ready=True)` with no floor, under the `pane_reads_nothing`
fixture, and confirm or mismatch entirely from a planted transcript.
`test_matching_company_transcript_confirms_account` asserts `"account" in
receipt["confirmed_against_herdr"]` and would instead raise `account unverified`. Issue 889's defect
is a *launch-time* confirmation drawn from stale evidence, and closing it on the launch path closes
it; hardening every direct caller is scope this run did not take.

**Consequence, stated plainly:** a caller that reaches `verify_unit_preflight` without going through
`launch` still gets the old unbounded fallback. That is a deliberate, recorded limitation, not an
oversight, and it is why the guard lives on `launch` rather than in `transcript_account` alone.

1. **Thread a recency floor through the chain**, as an explicit parameter rather than a loose
   attribute. `Unit` and `LaunchRequest` are plain dataclasses serialized by `asdict`, so an ad-hoc
   `unit.launched_at` would be dropped on the next save; a parameter cannot be.

   Exact signatures, chosen against the arity these functions are already pinned to:

   ```python
   def transcript_account(unit: Any, *, since: float | None = None) -> str | None: ...
   def observed_account(unit: Any, pane_id: str | None, seconds: float,
                        *, since: float | None = None) -> tuple[str | None, str]: ...
   def check_unit_account(unit: Any, pane_id: str | None = None,
                          seconds: float = ACCOUNT_SETTLE_SECONDS, *,
                          since: float | None = None,
                          evidence_out: list[str] | None = None,
                          ) -> tuple[bool | None, str | None]: ...
   def verify_unit_account(unit: Any, pane_id: str | None = None, *,
                           since: float | None = None) -> tuple[bool | None, str]: ...
   def verify_unit_preflight(unit: Any, pane_id: str | None, *, ready: bool | None = None,
                             argv: list[str] | None = None,
                             since: float | None = None) -> dict[str, Any]: ...
   ```

   - `transcript_account` ignores any file whose `st_mtime` is below the floor. With `since is None`
     it behaves exactly as today.
   - `observed_account` returns `(label, evidence)` where evidence is `"statusline"`, `"transcript"`
     or `"none"`. It has **no callers outside this module and no test references**, so its return
     shape is free to change.
   - **`check_unit_account` keeps its two-tuple return, which is not negotiable.** Eight call sites
     pin it: `tests/test_orchestrate_account.py` lines 541, 688, 702, 717, 727, 733 and 860, and
     `tests/test_orchestrate_model_authority.py:282` — two of them compare the whole tuple
     (`== (True, None)`, `== (None, None)`) and two monkeypatch it with a two-tuple lambda. The
     evidence therefore leaves through an optional `evidence_out` list the caller supplies and the
     callee appends one string to. Every existing call site passes nothing and is unaffected,
     including the early `(None, None)` return for a non-Claude unit, which appends nothing.
   - `verify_unit_account` returns `(confirmed, evidence)`, defaulting evidence to `"none"` when
     `evidence_out` stayed empty. It is monkeypatched in exactly one place —
     `plugins/agent-launcher/tests/test_launcher_contract.py:325`, `lambda *a, **k: None` — which
     becomes `lambda *a, **k: (None, "none")`. Its two other test call sites,
     `tests/test_orchestrate_account.py:818` and `:844`, are inside `pytest.raises` blocks that
     never bind the return, so they are unaffected.

2. **`launch` captures the floor** immediately before the create, beside L1's bound argv:

   ```python
   created_at = time.time()
   argv = agent_argv(unit)
   proc = run(argv, check=False, timeout=LAUNCH_CREATE_SECONDS)
   ```

   and passes `since=created_at` into `verify_unit_preflight`. Wall clock, not `time.monotonic`,
   because it is compared against a filesystem mtime.

   **The comparison carries a granularity margin**, as a named constant beside the other deadlines:

   ```python
   # A transcript written during the create is legitimate evidence; one left by an earlier run is
   # minutes or hours old. One second absorbs filesystem mtime granularity without admitting a
   # stale file, and a same-instant write is a real case: the cmd_go account test plants its
   # transcript inside the wrapper call itself.
   TRANSCRIPT_MTIME_SLACK_SECONDS = 1.0
   ```

   so the accept test is `st_mtime >= since - TRANSCRIPT_MTIME_SLACK_SECONDS`. Without it,
   `test_cmd_go_marks_unit_account_mismatch_on_verified_mismatch`
   (`tests/test_orchestrate_account.py:554`) is at risk: it drives the real `launch`, and its fake
   wrapper writes `session.jsonl` during the create, microseconds after `created_at` is captured.

3. **`verify_unit_preflight` writes the evidence into the receipt**, with no ad-hoc attribute on
   `unit`:

   ```python
   account_confirmed, account_evidence = verify_unit_account(unit, pane_id, since=since)
   ...
   receipt["account_evidence"] = account_evidence
   ```

   `"account"` keeps holding the requested selection, so this is L3's requested-versus-resolved
   shape applied to the account.

Nothing else moves. `pane_account_label`'s parsing is untouched, `AccountMismatchError` and the hard
stop on a genuine mismatch are untouched, `--company-account` is untouched, no other vendor gains an
account check, and no transcript is pruned or deleted.

### Tests

All in `plugins/agent-launcher/tests/test_launcher_contract.py`, using `monkeypatch.setattr` on
`claude_transcript_roots` to point at `tmp_path` directories and `os.utime` to set mtimes precisely.

| Test | What it asserts | Mutation it kills |
|---|---|---|
| `test_stale_transcript_does_not_confirm_a_silent_statusline` | A `.jsonl` under the worktree slug with `st_mtime` set 60 seconds **before** `since`, `pane_account_label` stubbed to `None`: `observed_account(..., since=now)` returns `(None, "none")`, and `check_unit_account(..., since=now)` returns `(False, msg)` whose text contains `"unverified"` | **Restoring the unconditional transcript fallback** — the stale file is read and `"personal"` is returned, so both assertions die |
| `test_fresh_transcript_confirms_when_recency_is_provable` | Same file with `st_mtime` after `since`: `observed_account` returns `("company", "transcript")` and the receipt carries `account_evidence == "transcript"` | A floor so strict that no transcript ever qualifies, which would break the legitimate path |
| `test_transcript_written_during_the_create_still_confirms` | `st_mtime` set to exactly `since` — the same-instant write the `cmd_go` account test produces: confirms, because the accept test is `>= since - TRANSCRIPT_MTIME_SLACK_SECONDS` | Dropping the slack constant, or writing the comparison as a strict `>` |
| `test_statusline_evidence_still_confirms_exactly_as_today` | `pane_account_label` returns `"company"`, requested `company`: `check_unit_account` returns `(True, None)` and the receipt carries `account_evidence == "statusline"`; the transcript roots are never touched (asserted by pointing them at a nonexistent path) | Reordering the proof chain |
| `test_omitted_since_keeps_the_existing_fallback` | A fresh transcript with **no** `since`: still confirms, and `account_evidence == "transcript"`. This is the compatibility decision written down as a test, so a later tightening cannot happen by accident | Silently switching the default to the strict rule and turning `tests/test_orchestrate_account.py` red |
| `test_launch_passes_a_recency_floor` | Drives `launch` with a stale transcript planted **before** the call and no statusline; asserts the launch raises `AccountMismatchError` naming `account unverified` | **Dropping `since=created_at` from `launch`'s `verify_unit_preflight` call** — the stale transcript confirms again and no exception is raised. This is the mutation proof that the floor reaches the real path, not just the helper |
| `test_account_mismatch_still_raises_unchanged` | `pane_account_label` returns `"personal"`, requested `company`: `AccountMismatchError` with today's message | Collateral damage to the mismatch path |

**No harness substitution.** These tests write real files to a real temporary directory and set real
mtimes; the component under test is `Path.stat().st_mtime` comparison against a real clock, and no
fake stands in for the filesystem.

### Risk and interaction with adjacent units

- **This is a behaviour change on a real machine, not only a test change.** A statusline-silent
  Claude session launched through `launch`, which today confirms from a stale transcript, will after
  L4 stop with `account unverified`. That is the intended outcome and it is strictly safer, but it
  will surface as new stops on any host whose statusline does not paint. **The L1–L3 runtime
  checkpoint now observes exactly that before L4 lands** — see the account-statusline row there.
- **The transcript is normally absent at preflight anyway** — `transcript_account`'s own docstring
  says Claude writes it when the first prompt arrives, which is after this check. So in the ordinary
  case the fallback was already returning `None` and this changes nothing.
- **Two return shapes change and one does not.** `observed_account` and `verify_unit_account` become
  tuple-returning, which is safe because the first has no external references at all and the second
  is monkeypatched in exactly one test. `check_unit_account`'s two-tuple return is pinned by eight
  call sites and is left alone; that constraint, not preference, is why the evidence travels through
  `evidence_out`. Any implementer tempted to "clean this up" by widening `check_unit_account`'s
  return will turn `tests/test_orchestrate_account.py` and
  `tests/test_orchestrate_model_authority.py` red.
- **`tests/test_orchestrate_account.py` is the file this unit is most likely to break**, and the
  compatible default is what keeps it green. It is named in the coexistence section and belongs in
  the run's green check.
- **`verify_unit_preflight` gains its second new keyword in this run** (L3 added `argv`, L4 adds
  `since`), both keyword-only with `None` defaults; doing them in order keeps each diff small.
- The receipt gains `account_evidence`, which issue 889 does not forbid.

### Acceptance

- A session launched through `launch` with a silent statusline is not confirmed from a transcript
  whose recency cannot be tied to that launch.
- A statusline carrying account evidence confirms exactly as today.
- A fresh transcript provably newer than the launch still confirms, including one written during the
  create itself.
- A stale transcript from an earlier run in the same worktree never confirms **on the launch path**.
- A direct `verify_unit_preflight` call with no `since` keeps today's fallback, by decision, and
  `tests/test_orchestrate_account.py` stays green.
- The receipt records `account_evidence` distinctly from the requested `account`.
- The hard stop on a genuine mismatch is unchanged.
- Restoring the unconditional fallback fails the stale-transcript test; dropping `since=created_at`
  from `launch` fails `test_launch_passes_a_recency_floor`.

---

## L5 — surface a failing owned close (issue 888)

**Issue.** 888 — the owned close ignores a failing `herdr tab close`.

### Current behaviour

`launcher.py:706-711`:

```python
def close_run_session(unit: Any) -> None:
    """Close only the tab this launch created, leaving every other session alone."""
    if not session_owned(unit):
        return
    if unit.tab_id:
        run(["herdr", "tab", "close", unit.tab_id], check=False)
```

The result is discarded, so a leaked tab and a clean close are indistinguishable. `close_run_session`
is called from **five** sites: `verify_unit_account` at `launcher.py:894`, the kind-mismatch,
cwd-mismatch and workspace-mismatch stops inside `verify_unit_preflight` at `:927`, `:936` and
`:949`, and `close_owned_session` at `:1257`, which is what `cli_main`'s `close` branch reaches.
**L5 edits none of those five call sites** — they keep calling the function and ignoring its value —
but the count and the lines are recorded here so an implementer tracing callers after the return
type changes finds all of them and is not surprised by the two it would otherwise miss.

### Change

1. `close_run_session` returns the result and records a failure, without raising:

   ```python
   def close_run_session(unit: Any) -> subprocess.CompletedProcess[str] | None:
       """Close only the tab this launch created, leaving every other session alone.

       Returns the close result, or None when there was nothing owned to close. A failure is
       recorded rather than raised: every internal caller is already unwinding a different stop,
       and replacing that stop with this one loses the reason the session was being closed.
       """
       if not session_owned(unit):
           return None
       if not unit.tab_id:
           return None
       proc = run(["herdr", "tab", "close", unit.tab_id], check=False)
       if proc.returncode != 0:
           err = (proc.stderr or proc.stdout or "").strip()
           append_unit_note(unit, f"tab close failed ({proc.returncode}) for {unit.tab_id}: {err}")
       return proc
   ```

2. `close_owned_session` — the CLI-facing variant at `launcher.py:1226` — turns a failure into a
   nonzero exit, which is the minimum "surfacing the failure requires":

   ```python
       proc = close_run_session(unit)
       if proc is not None and proc.returncode != 0:
           err = (proc.stderr or proc.stdout or "").strip()
           raise SystemExit(f"tab close failed ({proc.returncode}) for {unit.tab_id}: {err}")
   ```

The ownership predicate `session_owned` is untouched, the receipt format is untouched, and no
unowned session is ever closed to tidy up after a failure.

### Tests

| Test | File | What it asserts | Mutation it kills |
|---|---|---|---|
| `test_failing_tab_close_is_recorded_on_the_unit` | contract | Fake `run` returns `returncode=1, stderr="no such tab"`; `close_run_session` on an owned unit leaves a note containing `"tab close failed"`, the tab id, and `"no such tab"` | **Discarding the result again** — the note is empty and the assertion dies |
| `test_failing_tab_close_exits_nonzero_through_the_cli_variant` | contract | Same fake; `close_owned_session` raises `SystemExit` matching `"tab close failed"` | A note-only fix that leaves the CLI reporting success |
| `test_successful_close_adds_no_note` | contract | Extends the existing `test_close_owned_session_closes_only_receipt_tab` shape: after a `returncode=0` close, `unit.note == ""` and `closed == [["herdr", "tab", "close", "tab-owned"]]` | A change that notes on every close, making the signal useless |
| `test_unowned_session_closes_nothing_and_reports_nothing` | contract | Extends the existing `test_preexisting_tab_is_not_owned`: after `close_run_session` on an unowned unit, `closed == []` **and** `unit.note == ""` | Recording a failure for a close that was correctly never attempted |

**No harness substitution.** These do replace `launcher.run` with a fake, which is the established
pattern in this module's close tests — but the code under test is the result-reading branch itself,
and the fake's returncode is the only input it needs. There is no version of this test where a stub
stands in for the function being fixed.

### Risk and interaction with adjacent units

- **`close_run_session`'s return type changes** from `None`. `mypy plugins/ scripts/ tests/` runs in
  the gate, so `subprocess` must already be imported in the module — it is, at `launcher.py:22`.
  Existing tests that monkeypatch `close_run_session` with a `None`-returning lambda still work,
  because the new `close_owned_session` code guards on `proc is not None`.
- **Ordering with L6 is free.** L5 and L6 are independent leaf repairs on different functions and
  could swap; the run order is kept as issue 907 recorded it so the commit sequence matches the
  parent's dependency graph.
- No new closing behaviour: a failing close still does not retry and still does not reach for a
  session the launch did not create.

### Acceptance

- A failing `herdr tab close` on an owned session is recorded with the Herdr error text.
- A caller can tell a closed tab from an attempted close that did not happen.
- An unowned session still closes nothing and reports nothing.
- A successful close behaves exactly as today, with no new output.
- Restoring the discarded result fails the failing-close test.

---

## L6 — a named stop for a receipt path that does not exist (issue 887)

**Issue.** 887 — `close --receipt-json` raises a raw JSON traceback for a missing receipt path.

### Current behaviour

`launcher.py:1322-1329`:

```python
def _load_receipt(raw: str) -> dict[str, Any]:
    path = Path(raw)
    text = path.read_text(encoding="utf-8") if path.is_file() else raw
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise SystemExit("receipt must be a JSON object")
    return loaded
```

Reached from the `close` branch of `cli_main` at `launcher.py:1339`. When `raw` names a file that
does not exist, `path.is_file()` is false, the filename itself is handed to `json.loads`, and the
caller gets a `json.JSONDecodeError` traceback where the module's agent-facing contract promises a
`SystemExit` naming a cause and a recovery.

### Change

One branch, discriminating on the shape of the argument rather than adding a path check anywhere
else in the CLI. A payload that is genuinely inline JSON begins with `{` or `[` after stripping;
anything else that is not an existing file is a path that is not there.

**`[` is in the test deliberately (finding D5).** A receipt must be a JSON *object*, so it is
tempting to accept only `{`. But `_load_receipt("[1, 2]")` must keep raising the existing
`"receipt must be a JSON object"` stop, and it can only reach that stop if a JSON array is first
recognised as inline JSON. Accepting only `{` would divert a valid-JSON array into the new
missing-path message and silently change a behaviour issue 887 says must not change.

```python
def _load_receipt(raw: str) -> dict[str, Any]:
    path = Path(raw)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    elif raw.lstrip()[:1] in ("{", "["):
        text = raw
    else:
        raise SystemExit(
            f"receipt {raw!r} is neither an existing file nor JSON; redirect launch output to a "
            "receipt file and pass that file: "
            "python3 launcher.py launch ... > receipt.json, then close --receipt-json receipt.json"
        )
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise SystemExit("receipt must be a JSON object")
    return loaded
```

Malformed **inline** JSON still reaches `json.loads` and still raises `JSONDecodeError` exactly as
today, which issue 887 requires. The receipt schema gains nothing. `launch`, ownership proof, and the
`owned`/`reused` semantics are untouched, and no other CLI argument gains an existence check.

### Tests

All in `plugins/agent-launcher/tests/test_launcher_contract.py`.

| Test | What it asserts | Mutation it kills |
|---|---|---|
| `test_missing_receipt_path_names_the_path_and_the_recovery` | `_load_receipt("/no/such/receipt.json")` raises `SystemExit` whose text contains the path and `"> receipt.json"`; asserts it is **not** a `JSONDecodeError` by catching `SystemExit` specifically | **Restoring the unguarded `json.loads`** — a `JSONDecodeError` escapes and `pytest.raises(SystemExit)` fails |
| `test_missing_receipt_path_through_the_cli_exits_without_a_traceback` | Runs `launcher.py close --receipt-json /no/such/file` as a **real subprocess**; asserts a nonzero exit and that `"Traceback"` does not appear in stderr | A fix that raises `SystemExit` from a place `cli_main` re-wraps, or one that only works when called directly |
| `test_inline_malformed_json_keeps_its_existing_stop_shape` | `_load_receipt('{"a":')` raises `json.JSONDecodeError` | Broadening the new stop to swallow inline JSON errors, changing behaviour issue 887 says must not change |
| `test_valid_receipt_file_is_unchanged` | A real file under `tmp_path` loads to the same dict | Reading order regressions |
| `test_valid_inline_json_is_unchanged` | `_load_receipt('{"tab_id": "t1", "owned": true}')` returns the dict | Requiring a file |
| `test_non_object_json_keeps_its_message` | `_load_receipt("[1, 2]")` raises `SystemExit` matching `"must be a JSON object"` | Reordering the checks so a JSON array hits the new branch |

**No harness substitution.** The second test runs the actual CLI in a real subprocess and inspects
real stderr, which is the only way to prove "no traceback" — an in-process `pytest.raises` cannot
distinguish a `SystemExit` that Python prints as a traceback from one it prints as a message.

### Risk and interaction with adjacent units

- **A receipt file containing leading whitespace then `{`** is handled by `lstrip()`. A receipt
  passed as inline JSON that begins with a comment or a BOM would now stop rather than raise a
  decode error; neither is a shape this CLI has ever produced, since `cli_main` writes receipts with
  `json.dump`.
- Independent of every other unit. It touches one function no other unit reads.

### Acceptance

- `close --receipt-json` on a nonexistent path exits nonzero naming the path and the recovery, with
  no traceback.
- The recovery text names redirecting `launch` stdout to a receipt file and passing that file.
- Malformed inline JSON keeps its existing stop shape and message.
- A valid receipt file and a valid inline payload both behave exactly as today.
- Restoring the unguarded `json.loads` fails the missing-path test.

---

## L7 — stop overselling `--dry-run`, and give callers the preflight that actually exists (issue 880)

**Issue.** 880 — the skill oversells `agents --dry-run` as a preflight that validates model, effort,
and account.

### Current behaviour

`plugins/agent-launcher/skills/agent-launcher/SKILL.md:51`:

```
`--dry-run` previews any launch without executing it. Use it before every creation command.
```

Read plainly, that is an instruction to treat dry-run as the preflight. Re-verified on this machine
on 2026-08-30 against `/Users/jefcox/.local/bin/agents`: `agents --dry-run --task cp907probe --cwd
"$PWD" claude -m definitely-not-a-real-model-xyz` printed its preview and exited 0. The wrapper
echoes the command it would run; it does not judge whether that command is answerable.

Two more surfaces carry the same unqualified claim:

- `SKILL.md:168` — "Preview with `--dry-run` before any creation command. Confirm `cwd` and
  `herdr_workspace`."
- `README.md:30` — "Preview with `--dry-run` before every creation. Stop if `cwd` or
  `herdr_workspace` is wrong."

The skill already models the honest register two paragraphs earlier, where it explains that model
and permission stay `requested_only` "because `herdr agent list` does not publish them" — a caveat
verified true above and simply missing from the dry-run guidance.

The `agents` binary is not source in this repository, so the missing validation cannot be fixed here.
The guidance that invites callers to trust it can be.

### Change

**`SKILL.md:51` is replaced** with a paragraph that keeps dry-run useful and states its limits:

- What it **does** verify, and this is genuinely worth keeping: the resolved working directory, the
  resolved Herdr workspace, the flag ordering, and the exact command that would run.
- What it **does not** verify: the model, the reasoning effort, and the account. Each of those is
  passed through unchecked and a nonexistent value exits 0.
- That it is therefore a preview, not a preflight, and must not be the only check before dispatching
  a fleet.

**A new section, "The only real preflight is a bounded live launch with a read-back,"** states the
ordering rule. The order is the substance, so it is written as three numbered steps:

1. **Identify the selected client auth mechanism before proving anything.** A client may hold an
   existing interactive OAuth session or draw on an environment-backed credential; the correct proof
   differs entirely, and guidance that skips this step pushes callers toward whichever proof it
   happened to describe.
2. **For an OAuth session, prove it without inspecting the environment.** Interactive readiness plus
   the client's own non-secret auth status is the whole proof. This is the common case and the
   documented default.
3. **Only when a declared run contract explicitly names an environment-backed credential** may
   guidance test for it, and then only for the presence of the required variable name, never its
   value. Absent such a declaration, inspecting the environment is out of scope.

Then the safeguards, which apply to every route:

- **An allowlist of inspectable launch arguments**, named explicitly: model, reasoning effort,
  permission posture, account or route, working directory, workspace. Never argv wholesale, because
  argv is not guaranteed free of credentials. The allowlist contains no credential-bearing entry.
- **Never dump an environment** — no `env`, no `printenv`, no `os.environ` dump, and no diff of two
  environments, since a diff prints values as surely as a dump.
- **Never read, hash, copy, truncate, fingerprint, or persist a credential value.** Hashing is called
  out by name because it looks like a safe compromise and is not: a hash of a short secret is
  attackable, and a hash in a transcript is still durable proof of possession.
- **Redact inside the producing command, before output exists.** Piping through a redacting filter is
  not sufficient — by then the value has been produced and buffered and may already be in a
  transcript, a log, or a failure path that bypasses the filter.
- A copyable shape for the read-back, using only allowlisted non-secret arguments, so callers get a
  pattern rather than a prohibition to interpret.

**`SKILL.md:168` and `README.md:30`** are amended to say dry-run confirms `cwd` and
`herdr_workspace` and does not confirm model, effort, or account.

`--dry-run` is neither removed nor discouraged, the full flag surface is not restated, and launch,
close, receipt handling, and ownership semantics are untouched.

### Tests

All in `plugins/agent-launcher/tests/test_launcher_contract.py`, beside the two existing
document-contract tests `test_skill_cleanup_example_redirects_receipt` and
`test_skill_declares_herdr_dependency_and_no_duplicate_herdr_skill`.

**Correction tests:**

| Test | What it asserts | Mutation it kills |
|---|---|---|
| `test_dry_run_guidance_names_what_it_does_not_validate` | The skill text contains `model`, `reasoning effort` and `account` inside the dry-run section, framed as not validated | Deleting the caveat |
| `test_dry_run_is_not_described_as_sufficient_preflight` | The exact string `"Use it before every creation command."` is **absent**, and the phrase describing a bounded live launch is present | **Restoring the unqualified wording alone** — this is the named mutation proof in issue 880 |
| `test_readme_and_skill_agree_on_dry_run` | Both files carry the same not-validated list, so the two surfaces cannot drift | Fixing one surface and leaving the other |

**Secret-safety contract tests**, run over the changed guidance text and every example it ships:

| Test | What it asserts |
|---|---|
| `test_guidance_names_an_allowlist_with_no_credential_entry` | The allowlist is present and every entry is in the permitted set; no entry matches a credential vocabulary (`key`, `token`, `secret`, `password`, `credential`) |
| `test_guidance_states_the_ordering_rule` | Identify the auth mechanism appears **before** either proof, by string index in the document |
| `test_oauth_path_is_the_default_and_touches_no_environment` | The OAuth step is described first and its passage contains none of `env`, `printenv`, `os.environ`, `$` followed by an all-caps variable |
| `test_environment_access_is_gated_on_a_declared_contract` | Every environment mention is inside the passage that names the declared run contract |
| `test_environment_check_asserts_presence_of_a_name_only` | The passage says presence of the variable name and contains no comparison, print, or capture of a value |
| `test_no_specific_credential_variable_is_named` | No token matching `[A-Z][A-Z0-9_]{3,}_(KEY|TOKEN|SECRET|PASSWORD)` appears |
| `test_no_example_dumps_diffs_or_serialises_an_environment` | No code fence contains `env`, `printenv`, `os.environ`, or an environment diff |
| `test_no_example_hashes_truncates_or_persists_a_value` | No code fence contains `sha256`, `md5`, `base64`, `cut -c`, `head -c`, or a redirect of a credential-bearing expression to a file |
| `test_redaction_appears_inside_the_producing_command` | Every example that could emit a value redacts within the command; no example pipes unredacted output into a downstream filter |
| `test_no_credential_shaped_literal_appears` | No string of 20 or more characters matching a key-like alphabet appears in any changed file, real or fake |

**Mutation proofs for the secret-safety guards.** Issue 880 requires each guard to be provably live.
Rather than committing bad examples, the three named mutations are exercised by feeding the
assertion helpers a synthetic document:

- `test_environment_dump_example_would_fail_its_guard` — the helper run over a fixture string
  containing `printenv` returns a failure.
- `test_hashing_example_would_fail_its_guard` — the helper run over a fixture string containing
  `sha256sum` returns a failure.
- `test_downstream_only_redaction_would_fail_its_guard` — the helper run over a fixture string that
  pipes into `sed 's/.*/REDACTED/'` returns a failure.

Each guard is therefore a function tested on both a passing and a failing input, which is what makes
it a guard rather than an assertion that happens to hold. No fixture contains a credential-shaped
literal, real or fake — the failing fixtures contain only the *commands*, never a value.

### Risk and interaction with adjacent units

- **String-matching tests over prose are brittle.** Each assertion is written against a short,
  distinctive phrase the guidance owns, not against a whole sentence, so ordinary editing does not
  break them while the specific claim returning does.
- **L7 depends on L2 and L3 having landed**, because the new guidance describes the reuse guard and
  the launch-granted permission posture as existing behaviour. That is the whole reason it is last.
- **L7 must preserve three earlier `SKILL.md` edits**, because all three land in the same file
  before it: L2's reuse-guard paragraph, L3's launch-granted-permission sentence, and L3's rewrite of
  line 32 (the sentence that used to group permission with model as Herdr-`requested_only`).
  Reintroducing any of the superseded wording while editing the dry-run paragraph would reopen a
  closed finding, and `test_skill_no_longer_calls_permission_herdr_requested_only` from L3 is what
  catches it.
- **The two existing document tests must keep passing**:
  `test_skill_cleanup_example_redirects_receipt` requires `> receipt.json` and
  `close --receipt-json receipt.json` to stay in the file, and
  `test_skill_declares_herdr_dependency_and_no_duplicate_herdr_skill` requires the phrases
  "canonical `herdr` skill" and "does not ship a copy". Neither is in the edited region, but the
  implementer must not reflow those paragraphs.
- Nothing is added to the external `agents` binary, and nothing here grants a new capability.

### Acceptance

Issue 880 carries fifteen acceptance bullets. All of them are covered by the change and tests above;
the load-bearing ones are: the skill states dry-run does not validate model, effort, or account; it
names what dry-run does verify; README and skill agree and a test holds them together; the bounded
live launch with read-back is given as the actual preflight; the ordering rule puts auth-mechanism
identification first; the OAuth path is the documented default with no environment access;
environment inspection is reachable only under a declared contract and tests a variable name for
presence only; no specific credential variable is named; the read-back inspects only the allowlist;
no example dumps, diffs, or serialises an environment; redaction happens inside the producing
command; no credential-shaped literal appears; and each secret-safety guard has a mutation proof.

---

## Runtime checkpoint — after L1, L2 and L3 are committed

Before L4 starts, install the unmerged candidate **only in a disposable Herdr workspace tab** and
exercise it against the real wrapper and the real multiplexer. This is runtime proof that the three
units that change live launch behaviour work outside pytest; it is not a substitute for the
integrated review.

**What to exercise, and what evidence makes it pass:**

| Check | Command shape | Evidence that passes |
|---|---|---|
| Bounded create (L1) | `launch` against a wrapper stub on `PATH` that sleeps past a temporarily lowered `LAUNCH_CREATE_SECONDS` | The process returns inside the deadline with `session create timed out after Ns`, and `herdr tab list` shows no new tab. A run that has to be interrupted by hand is a fail |
| Ordinary create still works (L1) | A genuine `launch` of one throwaway Claude tab in the disposable workspace | A receipt on stdout with a real `tab_id` and `pane_id`, the tab visible in `herdr tab list`, well inside the deadline |
| Fresh pane takes no inspection (L2) | The same genuine launch | `receipt["owned"] is true` and no `input_box` key, proving the guard did not fire on the create path |
| Reused pane, empty box (L2) | Launch a second unit onto a tab that already exists so `owned` is false, with the box empty | `receipt["input_box"] == "empty"`, the prompt is delivered, and exactly one extra pane read occurred |
| Reused pane, staged text (L2) | Type a harmless string into that pane's box **without pressing Enter**, then dispatch | A stop naming the unit, the pane and the exact text; the text is still in the box afterwards; nothing was submitted. This is the one check that reproduces the original incident |
| Composer parsing across vendors (L2) | `herdr pane read <pane> --source visible --format ansi` on one live pane per launchable vendor | For each vendor, either a marker in `COMPOSER_MARKERS` is found, or the vendor is recorded as falling to the unreadable branch. Any vendor not covered is written down, not assumed |
| Declared posture confirmed (L3) | `launch --permission bypass` for a Claude unit | `receipt["permission_resolved"]["tokens"] == ["--permission-mode", "bypassPermissions"]` and `["confirmed_from"] == "launch_argv"`, with `"permission"` still in `requested_only`. **No Herdr read-back of the posture is required or accepted as evidence** — this plan's own live inventory shows `herdr agent list` publishes no permission field, and `pane_account_label` parses an account label, not a posture (finding D10) |
| Unknown posture stops (L3) | An Orchestrate plan unit with `"permission": "bypasss"` | `unknown permission 'bypasss' for vendor 'claude'` before any worktree, branch, or session is created |
| Omission is visible (L3) | An Orchestrate plan unit with no `permission` key | The `permission not declared, inheriting auto:` line names that unit |
| **Account statusline paints (pre-L4 gate)** | `herdr pane read <pane> --source visible` on the throwaway Claude tab from the ordinary-create check, then `pane_account_label(pane_id)` against it | The pane shows the `<user>:` or `<user> [company]:` row and `pane_account_label` returns `"personal"` or `"company"`. **If it returns `None`, stop and surface to the operator before L4 lands** — that host is one where L4 converts a launch that used to succeed on a stale transcript into a hard stop, and that is an operator decision about the account-verification contract, not something the worker may relax by widening `since` |

The last row is the blast-radius gate for L4. It is here, in the L1–L3 checkpoint, because the
observation has to be made on a host running the *old* account behaviour: once L4 lands, a host with
a silent statusline stops rather than reporting, and the evidence is no longer collectable. The
`herdr pane read` seam and `pane_account_label` both already exist at `launcher.py:803-827`, so this
is an observation, not new code.

**Optional, not evidence.** An operator may glance at the bypass-permissions indicator on the
throwaway session's own status row to satisfy themselves the posture took. That is a human
observation; it is not machine-checkable from any seam this plan documents and no check above passes
or fails on it.

**Cleanup is part of the checkpoint.** Every tab created here is closed through the launcher's own
`close --receipt-json` path, and `herdr tab list` is read back to confirm the disposable workspace is
empty. A leaked tab from a check about leak detection would be its own answer.

---

## The shared release-surface update — performed once, after L7

One commit, after all seven child commits, message
`chore(release): agent-launcher 1.1.0 and orchestrate 3.1.0 for the 907 session-contract run`.

### Version targets

| Surface | From | To | Why |
|---|---|---|---|
| `plugins/agent-launcher/.claude-plugin/plugin.json` | `1.0.0` | `1.1.0` | Additive at the interface — every new parameter is keyword-only with a default — while adding new named stops and new receipt keys. A minor bump, not a patch, because callers gain observable new behaviour |
| `plugins/orchestrate/.claude-plugin/plugin.json` | `3.0.8` | `3.1.0` | One new `Unit` field and one new reported line. Additive, so minor |
| `.claude-plugin/marketplace.json` | `agent-launcher 1.0.0`, `orchestrate 3.0.8` | `1.1.0`, `3.1.0` | The registry entries must equal the plugin manifests; two drift tests assert exactly that |

The marketplace file's own top-level `version` stays `3.0.0` — it versions the marketplace format,
not its members.

### The dependency floor must rise, and **three** assertions plus one prose sentence move with it

Orchestrate 3.1.0's permission behaviour depends on `resolve_permission` existing in the ingested
launcher module. Installed beside launcher 1.0.0 it would silently get the old fallback, which is the
defect itself. So `plugins/orchestrate/.claude-plugin/plugin.json` moves its declared dependency from
`>=1.0.0` to `>=1.1.0`.

**Three live assertions read that manifest and pin the old floor.** Missing any one of them turns the
gate red (finding D7):

| File | Test | Assertion |
|---|---|---|
| `tests/test_plugin_manifest_loader_contract.py:108` | `test_orchestrate_keeps_its_agent_launcher_floor` | `assert floors.get("agent-launcher") == ">=1.0.0"` |
| `tests/test_agent_launcher_plugin.py:103` | `test_orchestrate_declares_agent_launcher_dependency_in_metadata` | `assert floors.get("agent-launcher") == ">=1.0.0"` |
| `plugins/agent-launcher/tests/test_launcher_contract.py:644` | `test_orchestrate_declares_agent_launcher_dependency_and_breaking_version` | `assert floors.get("agent-launcher") == ">=1.0.0"` |

All three become `">=1.1.0"`.

**One prose surface states the same floor** and drifts silently if left (finding D11):
`plugins/orchestrate/skills/orchestrate/SKILL.md:84` — "Orchestrate declares `agent-launcher
>=1.0.0` as a dependency" — becomes `>=1.1.0`.

**Two `>=1.0.0` occurrences are NOT pins and must be left alone.**
`tests/test_plugin_manifest_loader_contract.py:81` and `:95` are synthetic dictionary literals
constructed inside `check_dependencies_shape` calls to exercise the object-versus-array shape check.
They never read the live manifest, and rewriting them would weaken a test that has nothing to do with
this floor.

### The two version pins must move (Finding 2)

Both in `tests/test_agent_launcher_plugin.py`:

- `test_agent_launcher_metadata_is_marketplace_registered`: `assert plugin_json["version"] == "1.0.0"`
- `test_orchestrate_declares_agent_launcher_dependency_in_metadata`: `assert launcher_entry["version"] == "1.0.0"`

Both become `"1.1.0"`. These are the drift guards the repository policy relies on; they are updated
deliberately in this commit, never loosened to a comparison that would stop guarding.

**`_install_plugin(cache, "agent-launcher", "1.0.0", ...)` at `tests/test_agent_launcher_plugin.py:248`
is not a pin** — the string is a cache *directory name* in a simulated installed layout, unrelated to
the manifest version. Leave it. The same is true of the `"1.0.0"` literals in
`tests/test_sync_marketplace.py` and `tests/test_release_triad.py`, which belong to synthetic
fixture plugins named `alpha` and `myplugin`, not to agent-launcher; both were checked and neither
reads this plugin's manifest.

### CHANGELOG entries

`plugins/agent-launcher/CHANGELOG.md` gains a `## [1.1.0] - 2026-08-30` section with the seven
launcher-side entries, each naming its issue: bounded session create (890); reused-pane input-box
guard (897); declared permission resolved and confirmed (896); account recency floor (889); failing
close surfaced (888); named stop for a missing receipt path (887); dry-run guidance corrected and a
real preflight documented (880).

`plugins/orchestrate/CHANGELOG.md` gains a `## [3.1.0] - 2026-08-30` section with the one
Orchestrate-side entry: declared permission carried and unconfirmed inheritance reported (896).

### The complete release-commit file list

Nothing outside this list is touched by the release commit, and nothing in it is touched by a unit
commit.

```
plugins/agent-launcher/.claude-plugin/plugin.json          1.0.0  -> 1.1.0
plugins/agent-launcher/CHANGELOG.md                        new [1.1.0] section
plugins/orchestrate/.claude-plugin/plugin.json             3.0.8  -> 3.1.0, floor -> >=1.1.0
plugins/orchestrate/CHANGELOG.md                           new [3.1.0] section
plugins/orchestrate/skills/orchestrate/SKILL.md:84         floor prose -> >=1.1.0
.claude-plugin/marketplace.json                            both member versions
tests/test_plugin_manifest_loader_contract.py:108          floor assertion -> ">=1.1.0"
tests/test_agent_launcher_plugin.py:103                    floor assertion -> ">=1.1.0"
tests/test_agent_launcher_plugin.py:80, :112               version pins   -> "1.1.0"
plugins/agent-launcher/tests/test_launcher_contract.py:644 floor assertion -> ">=1.1.0"
docs/engineering-journal/LEARNINGS.md                      dated entry (below)
```

### Engineering journal

Per repository policy, the same commit carries a dated `docs/engineering-journal/LEARNINGS.md`
entry for the non-obvious mechanism this run turned up — that `reused` names the workspace and not
the pane, so a guard keyed on it inspects the ordinary create path (Finding 3) — with Evidence
(`launcher.py:54-63`, issue 897), Mechanism, and a one-line generalizable rule. Finding 1, that a
test module named for a plugin held only its release surfaces while its behaviour tests lived
elsewhere, belongs in the same entry.

---

## Coexistence — where the seven test additions could collide, and how they do not

The run-level obligation is that all seven units' cases pass **together**, not each in isolation.
Four real collision surfaces exist.

**1. The module-scoped `launcher` fixture.** `plugins/agent-launcher/tests/test_launcher_contract.py`
loads the launcher once per module with `@pytest.fixture(scope="module")` and caches it in
`sys.modules`. Any test that mutates module state — `monkeypatch.setattr(launcher, ...)` — is safe
because `monkeypatch` undoes it per test, but a test that mutates a *mutable module object in place*
is not. L3 is the risk: nothing may mutate `VENDOR_PERMISSION` itself. Every L3 test reads the table
and builds units; none edits it. `resolve_permission` returns `list(modes[permission])`, a copy, so
a caller that mutates the returned list cannot corrupt the table for the next test.

**2. `monkeypatch.setattr(launcher, "run", fake_run)` — the dominant pattern, and the sharpest
collision.** L1, L2 and L5 all exercise code paths that call `run`, and each existing fake answers
only the commands its own test expects. After L2, `launch` calls `herdr pane read --format ansi` on
the non-owned path, so any fake that previously fell through to "return the wrapper JSON for
anything" would answer a pane read with wrapper JSON. **The rule for this run: every new fake `run`
dispatches on `cmd[:3]` and raises `AssertionError` on an unrecognised command**, rather than
falling through. That converts a silent wrong answer into a loud test failure. The existing
`test_ownership_is_tab_id_not_in_prelaunch_snapshot` already needs its fall-through arm kept for the
wrapper call; L2 adds a `["herdr", "pane", "read"]` arm to it rather than a new fake.

**3. Real-wrapper-on-`PATH` tests versus `launcher_on_path`.** L1's timing tests write a real script
to `tmp_path` and prepend it to `PATH`, the same as `test_nonzero_wrapper_exit_stops_launch`. The
`launcher_on_path` fixture writes an *empty* `agents` stub to `tmp_path` and prepends the same
directory. A test that uses both would have the fixture's stub overwritten by the timing script or
the reverse, depending on ordering. **L1's timing tests must not request `launcher_on_path`**; they
write their own wrapper, which is all they need since `agent_argv` only requires the binary to
resolve.

**4. `tmp_path` transcript roots versus the operator's real ones.** L4's tests monkeypatch
`claude_transcript_roots` to return two `tmp_path` directories. Without that, the tests would read
`~/.claude/projects` on the machine running them and pass or fail on the operator's own history.
Every L4 test must patch the roots, and `test_statusline_evidence_still_confirms_exactly_as_today`
patches them at a deliberately nonexistent path so a transcript read would be provably impossible.

**5. `tests/test_orchestrate_account.py` and L4's compatible default.** This 863-line file is the
one most exposed to L4, and it is exposed through Orchestrate's *ingested* copy of the launcher, not
through a direct import — `orchestrate.verify_unit_preflight` and `orchestrate.check_unit_account`
are the launcher's own functions. Four cases in `TestPostLaunchAccountVerification` (lines 310, 350,
401, 449) call `verify_unit_preflight` with no recency floor under the `pane_reads_nothing` fixture
and decide entirely from a planted transcript; `test_cmd_go_marks_unit_account_mismatch_on_verified_mismatch`
(line 554) drives the real `launch` and plants its transcript *inside* the faked wrapper call, which
is why `TRANSCRIPT_MTIME_SLACK_SECONDS` exists. The compatible default keeps all five green. **No L4
test may monkeypatch `claude_transcript_roots` at module scope**, because that file sets the same
roots through `CLAUDE_PERSONAL_PROJECTS` / `CLAUDE_COMPANY_PROJECTS` environment variables in its own
`fake_claude_roots` fixture; the two mechanisms must not both be live in one process.

**Cross-file coexistence.** L3 touches three test files
(`tests/test_orchestrate_vendor_permissions.py`, `tests/test_orchestrate_task_dispatch.py`, and the
contract module). Those three load Orchestrate and the launcher under *different* module names
(`_orchestrate_vendor_permissions`, `_agent_launcher_contract`), so `sys.modules` caching does not
cross-contaminate. Adding a fourth module name is not necessary and should not be introduced.

**The green check for the run**, which must pass at the final integrated commit:

```bash
uv run pytest plugins/agent-launcher/tests/test_launcher_contract.py \
              tests/test_agent_launcher_plugin.py \
              tests/test_orchestrate_vendor_permissions.py \
              tests/test_orchestrate_task_dispatch.py \
              tests/test_orchestrate_account.py \
              tests/test_plugin_manifest_loader_contract.py -q
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
cat /tmp/gate-run/result.txt
```

The full gate is backgrounded because its twenty-four steps exceed the ordinary foreground timeout,
and `result.txt` is absent while a run is in flight — absence means running or killed, never green.

---

## Stop conditions this plan raises

One is settled and recorded. Two remain live.

1. **SETTLED — issue 897's discriminator is ownership, not `reused`.** The issue's literal acceptance
   said "a pane recorded `reused=true` is inspected"; the module defines `reused` as a workspace bit
   and the same issue's out-of-scope clause forbids reading the pane on the ordinary create path, so
   the two could not both be honoured. The coordinator has recorded the amendment on issue 897 and it
   is quoted in full in Finding 3 above:
   https://github.com/infiquetra/infiquetra-claude-plugins/issues/897#issuecomment-5469528122

   **No ruling is outstanding and L2 is not blocked on this.** The guard keys on `session_owned(unit)`
   being false. It is not to be retargeted onto `reused`.

2. **LIVE — L3 collides with issue 909's child issue 900 on Orchestrate's unit model.** Both add a
   field to the same dataclass. Confirm issue 900 does not hold a worktree before starting L3; if it
   does, stop and reconcile custody or land one before the other. Issue 907 names this collision
   explicitly and it is mechanical, not speculative.

3. **LIVE — L4 turns a silent wrong confirmation into a stop on statusline-silent hosts.** No
   acceptance criterion is unmeetable, but the operational effect is a new hard stop on the launch
   path where a launch previously proceeded on stale evidence.

   **This one now has a gate rather than a hope.** The L1–L3 runtime checkpoint carries an
   account-statusline observation that runs *before* L4 lands, on a host still running the old
   behaviour, using the existing `herdr pane read` seam and `pane_account_label`. If
   `pane_account_label` returns `None` on a live Claude pane, the run stops and surfaces to the
   operator: that host is one where L4 changes a working launch into a stop, and whether to accept
   that is an operator decision about the account-verification contract. **The worker may not relax
   it by widening `since`, by raising `TRANSCRIPT_MTIME_SLACK_SECONDS`, or by reverting to the
   unbounded fallback.**

**No child's acceptance requires changing the external `agents` wrapper or Herdr.** L7 is the one
that comes closest — the validation it wants genuinely cannot be added here — and issue 880 already
resolves that by recording itself as a documentation defect in this repository rather than a launcher
product defect. L2 reads Herdr through `herdr pane read`, a command that already exists and was
verified live; it changes nothing about pane splitting, name suffixing, or prompt queueing.
