# Runtime checkpoint — issue 907 Agent Launcher run, after L1/L2/L3, before L4

**Run:** issue 907, Agent Launcher session contract.
**Worktree:** `/Users/jefcox/workspace/infiquetra/orch-claude-plugins-907`, branch
`work/cp907-launcher-session-contract`.
**Checkpoint specification:** `docs/plans/2026-08-30-agent-launcher-907-run-plan.md` lines
1131–1180.
**Commits under test:**

- `f5d6b382` — L1, bound the session create with an explicit timeout
- `b97a3226` — L2, inspect an unowned pane's input box before prompting it
- `87b1fd68` — L3, honour and confirm a declared worker permission

**Disposable workspace:** `wEY`, label `cp907-checkpoint-disposable`, created with
`herdr workspace create --label cp907-checkpoint-disposable --cwd <repo> --no-focus`, removed at
the end (read-backs below). Workspace `wEV` (the run's own roles) and every other pre-existing
workspace (`w7C`, `wCC`, `w7M`, `wEG`, `w7F`, `w9D`, `wEW`, `wEX`) were inventoried first and never
launched into, prompted, closed, or read.

**Containment mechanism.** Herdr and the `agents` wrapper resolve the "current" pane from the
`HERDR_PANE_ID` / `HERDR_WORKSPACE_ID` / `HERDR_TAB_ID` environment variables. Every launch in this
checkpoint ran with those pointed at the disposable workspace's root pane (`wEY:p1` / `wEY` /
`wEY:t1`), verified first:

```
$ HERDR_PANE_ID=wEY:p1 HERDR_WORKSPACE_ID=wEY HERDR_TAB_ID=wEY:t1 herdr pane current --current
→ pane wEY:p1, workspace wEY
$ agents --dry-run ... claude | grep herdr_workspace
herdr_workspace=<current-terminal:wEY>
```

This is equivalent to invoking the launcher from a shell inside the disposable workspace: the
wrapper's `--current` mode, the launcher's pre-launch tab snapshot (`list_tab_ids`), and the
preview gate (`confirm_preview`) all resolved to `wEY`. Without it, a cross-workspace CLI launch is
refused by `confirm_preview` (the dry-run's `herdr_workspace` names only the target).

**Topology deviation, already on record.** The reuse rows left tab `wEY:t2` holding two panes,
which violates the run contract's one-pane-per-tab rule. The coordinator recorded it, on operator
correction, in `docs/reviews/2026-08-30-cp907-checkpoint-topology-deviation.md`, with both panes'
terminal state preserved verbatim. Mechanism, for the record: the split is the **wrapper's own
behaviour** — on a `--task` name matching an existing tab, `agent-herdr prepare` reuses the tab and
splits a new pane into it (returning the new pane and an agent name suffixed `-2`). Cleanup below
followed that record's disposition.

---

## Row 1 — Bounded create (L1)

**Command.** `LAUNCH_CREATE_SECONDS` at `launcher.py:498` temporarily lowered `120.0 → 5.0` by
file edit (reverted below — there is no environment override for it). Wrapper stub
`agents-timeout-stub` on `PATH`, selected via `ORCHESTRATE_AGENT_LAUNCHER`: answers `--dry-run`
instantly with `cwd=<requested>` and `herdr_workspace=<current-terminal:wEY>`, sleeps 60 s on the
create call.

```
$ python3 plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py launch \
    --vendor claude --task cp907-ck-timeout --cwd <repo> --prompt "never"
exit=1 elapsed=5s   (returned on its own; not interrupted)
stderr: cp907-ck-timeout: session create timed out after 5.0s; no session was confirmed created
```

Tab list before: `['wEY:t1','wEY:t2','wEY:t3','wEY:t5','wEY:t6','wEY:t7','wEY:t8','wEY:t9']`
Tab list after: identical, byte for byte — no new tab.

Revert proof: `git diff HEAD | wc -l` → `0`; `grep -n "^LAUNCH_CREATE_SECONDS" launcher.py` →
`498:LAUNCH_CREATE_SECONDS = 120.0`.

**Verdict: PASS.**

## Row 2 — Ordinary create still works (L1)

```
$ python3 .../launcher.py launch --vendor claude --task cp907-ck-claude --cwd <repo> \
    --model haiku --prompt "Do nothing and reply with the single word: ready."
exit=0 elapsed=6s
```

Receipt (stdout, real wrapper, real create): `tab_id "wEY:t2"`, `pane "wEY:p2"`, `owned: true`,
`prompt_delivered: true`, `verified: true`, `confirmed_against_herdr: ["pane","kind",
"working_directory","readiness"]`. `herdr tab list --workspace wEY` showed the tab:
`{"label": "cp907-ck-claude", "tab_id": "wEY:t2"}`. Six seconds against a 120-second deadline.

**Verdict: PASS.**

## Row 3 — Fresh pane takes no inspection (L2)

Same receipt as row 2: `"owned": true` and **no `input_box` key anywhere in the receipt** — the
guard did not fire on the create path.

**Verdict: PASS.**

## Row 4 — Reused pane, empty box (L2)

Second launch with the same `--task cp907-ck-claude`; the wrapper reused tab `wEY:t2` (split a new
pane `wEY:p3`, agent `cp907-ck-claude-2`). A logging shim in front of `herdr` recorded every herdr
invocation the launcher made.

```
$ python3 .../launcher.py launch --vendor claude --task cp907-ck-claude --cwd <repo> \
    --model haiku --prompt "Do nothing further. Reply with the single word: again."
exit=0 elapsed=7s
receipt: {'owned': False, 'reused': True, 'tab_id': 'wEY:t2', 'pane': 'wEY:p3',
          'input_box': 'empty', 'input_box_text': None, 'prompt_delivered': True}
$ grep -c -- "--format ansi" herdr-calls-reused-empty.log
1
$ grep -- "--format ansi" herdr-calls-reused-empty.log
pane read wEY:p3 --source visible --format ansi
```

Ownership read false (tab `wEY:t2` was in the pre-launch snapshot of `wEY`), the box read `empty`,
the prompt was delivered, and exactly one extra pane read occurred. Note: the wrapper handed back a
freshly split pane rather than the original session's pane — the guard keys on tab-level ownership
exactly as designed, and the read was of the pane the wrapper returned.

**Verdict: PASS.**

## Row 5 — Reused pane, staged text (L2) — the incident reproduction

Staged first, on the live pane, through the real multiplexer, without Enter:

```
$ herdr pane send-text wEY:p3 "harmless staged text for cp907 checkpoint"
$ pane_input_text('wEY:p3')  →  'harmless staged text for cp907 checkpoint'
```

**Wrapper substitution, declared.** On this host the real wrapper never hands back an existing pane
— a tab-name collision always splits a fresh (empty) pane, so the incident's precondition cannot be
reached through it today. The handback was reproduced with a stub (`agents-reuse-stub` via
`ORCHESTRATE_AGENT_LAUNCHER`) that answers the dry-run like the wrapper and, on create, prints the
identity JSON of the **real live pane**: `{"tab_id": "wEY:t2", "pane_id": "wEY:p3", "agent_name":
"cp907-ck-claude-2", "reused": true}`. Everything downstream — ownership derivation from the real
tab snapshot, `verify_unit_preflight` against real herdr, the ANSI pane read of the real staged
text, the stop, the preservation — ran live. The launcher-under-test was not modified.

```
$ python3 .../launcher.py launch --vendor claude --task cp907-ck-staged --cwd <repo> \
    --prompt "This prompt must never be delivered."
exit=1
stderr: cp907-ck-staged: pane wEY:p3 already holds staged input 'harmless staged text for cp907
checkpoint'; refusing to prompt so the dispatched task cannot be concatenated onto it
receipt: {'owned': False, 'tab_id': 'wEY:t2', 'pane': 'wEY:p3', 'input_box': 'staged',
          'input_box_text': 'harmless staged text for cp907 checkpoint',
          'prompt_delivered': None}
```

Afterwards: `pane_input_text('wEY:p3')` → the same exact string (still in the box);
`herdr pane read wEY:p3 --source visible` shows the composer row
`❯ harmless staged text for cp907 checkpoint`; the pane's agent stayed `idle` with its last turn
still the earlier `again` reply — nothing was submitted. The stop names the unit, the pane, and the
exact text. The coordinator's deviation record preserves this pane's terminal state verbatim.

**Verdict: PASS** (with the declared wrapper substitution above).

## Row 6 — Composer parsing across vendors (L2)

Roster on this machine (`launcher.py roster`, asked of the real wrapper): claude, codex, grok,
muse, agy, qwen, opencode. One live pane per vendor was launched into `wEY` through the launcher
CLI (real wrapper), then read with the row's exact command shape
`herdr pane read <pane> --source visible --format ansi` and classified with the module's own
`COMPOSER_MARKERS` / `composer_staged_text`.

| Vendor | Pane | Result |
|---|---|---|
| claude | `wEY:p2` | marker `❯` found, staged `''` |
| codex | `wEY:p6` | marker `›` found, staged `''` |
| grok | `wEY:p7` | marker `❯` found, staged `''` |
| agy | `wEY:p8` | marker `>` found, staged `''` |
| qwen | `wEY:p9` | marker `>` found, staged `''` |
| opencode | `wEY:pA` | **unreadable branch** — no composer line found (the row's allowed second outcome; a launch onto an opencode pane will be prompted with the "input box not readable; prompted without inspection" note) |
| muse | — | **NOT COVERED.** The wrapper refuses the launch outright: `agent-herdr: command failed (2): unsupported interactive agent kind: muse`. Muse appears in the wrapper's `Tools:` list and therefore in the roster, but no muse pane can exist through this wrapper on this host, so no reused-pane inspection can ever encounter one here. Written down, not assumed. |

Every client placeholder was correctly discarded (all staged reads returned `''`, not the
placeholder text). Opencode's launch also drove the live `/variants` picker: variant `xhigh`
selected and verified; its `prompt_delivered: false` exit is irrelevant to this row (the pane is
live).

**Verdict: PASS with notes** (opencode on the unreadable branch as the table allows; muse
unlaunchable on this host and recorded).

## Row 7 — Declared posture confirmed (L3)

```
$ python3 .../launcher.py launch --vendor claude --task cp907-ck-bypass --cwd <repo> \
    --model haiku --permission bypass --prompt "Do nothing and reply with the single word: ready."
exit=0 elapsed=6s
receipt: permission          = bypass
         permission_resolved = {'confirmed_from': 'launch_argv', 'mode': 'bypass',
                                'tokens': ['--permission-mode', 'bypassPermissions']}
         requested_only      = ['model', 'permission', 'variant']
```

`tokens == ["--permission-mode", "bypassPermissions"]`, `confirmed_from == "launch_argv"`, and
`"permission"` still in `requested_only`. No Herdr read-back of the posture was attempted, per the
row's own instruction (finding D10: Herdr publishes no permission field).

**Verdict: PASS.**

## Row 8 — Unknown posture stops (L3)

Scratch git repository (checkpoint scratchpad), plan unit
`{"name": "u-bad", "vendor": "claude", "task": "do nothing", "permission": "bypasss"}`.

```
$ orchestrate.py start --plan plan.json
run branch orch/ck-bad from 950d6604 ...        start exit=0
  after start: branch orch/ck-bad EXISTS; no worktree yet
$ orchestrate.py go
  u-bad: orch-u-bad on orch/ck-bad-u-bad from orch/ck-bad
launching u-bad (claude) -> do nothing
  u-bad FAILED: unknown permission 'bypasss' for vendor 'claude'; expected one of ['auto', 'bypass']
  after go: branch orch/ck-bad-u-bad EXISTS; worktree orch-u-bad EXISTS
  wEY tab list: unchanged — NO session was created
```

The named stop fires with exactly the specified message, no silent fallback to the auto flag set,
and **no session is created** (the stop raises in `agent_argv`, before any wrapper subprocess).
But the row's evidence clause — "before any worktree, branch, or session is created" — is **not
met**: `start` accepts the bad posture and creates the run branch, and at `go` the unit's worktree
and branch are created by `make_worktree` (`orchestrate.py:2595`) before `launch`
(`orchestrate.py:2603`) builds the argv that raises. Nothing in `plan_units` or `cmd_start` calls
`resolve_permission`, so the earliest the typo can surface is launch time. **Finding for the
coordinator:** either the plan's evidence clause overstates the guard, or `start` should validate
each declared posture with `resolve_permission` at plan time — that would make the clause true and
is a one-line addition to `plan_units`.

**Verdict: FAIL against the row's written evidence clause** (the stop itself, its exact message,
and the no-session half all hold).

## Row 9 — Omission is visible (L3)

Scratch git repository, plan unit `{"name": "u-omit", "vendor": "claude", "task": "do nothing"}`
(no `permission` key).

```
$ orchestrate.py start --plan plan.json
permission not declared, inheriting auto: u-omit
run branch orch/ck-omit from 4afeaa74 ...
```

The line names the unit.

**Verdict: PASS.**

## Row 10 — Account statusline paints (pre-L4 gate)

On the throwaway Claude pane from the ordinary-create row (`wEY:p2`):

```
$ herdr pane read wEY:p2 --source visible     (tail)
  jefcox:/infiquetra/orch-claude-plugins-907 (work/cp907-launcher-session-contract)
  Haiku 4.5 │ ... 47.8K/200.0K 24% ...
$ pane_account_label('wEY:p2')  →  'personal'
```

The `<user>:` row paints and `pane_account_label` returns `"personal"`, not `None`. The gate
passes: on this host, L4's statusline-based account verification will have evidence to read, and
L4 may proceed. (Driver note: importing `launcher.py` standalone under Python 3.14 requires
registering the module in `sys.modules` before `exec_module`, or the `@dataclass` decorator fails;
this is an import-harness quirk, not launcher behaviour.)

**Verdict: PASS.**

---

## Cleanup read-back

Every tab this checkpoint created was closed through the launcher's own
`close --receipt-json` path (exit 0 for all seven owned receipts: ordinary-claude → `wEY:t2`
taking both panes of the split tab, bypass → `wEY:t3`, codex → `wEY:t5`, grok → `wEY:t6`,
agy → `wEY:t7`, qwen → `wEY:t8`, opencode → `wEY:t9`). The unowned staged-launch receipt was fed
to the same path first and correctly refused:
`cannot close: tab existed before this launch; this process does not own it` (exit 1).

```
$ herdr tab list --workspace wEY          (after the closes)
{"tabs": [{"label": "1", "tab_id": "wEY:t1", ...}]}     ← only the workspace's own root shell pane
$ herdr workspace close wEY
{"result": {"type": "ok"}}
$ herdr workspace list                     (after removal)
w7C Home Lab tabs: 3 / wCC Improve Agent Plugins tabs: 1 / w7M Infiquetra Claude Plugins tabs: 4 /
wEG Saga Plugin Review tabs: 2 / w7F Infiquetra SDLC Updates tabs: 2 / w9D Auralis tabs: 8 /
wEV claude-plugins-907 tabs: 6 / wEW claude-plugins-912 tabs: 6 / wEX claude-plugins-918 tabs: 6
```

`wEY` is gone; every pre-existing workspace carries exactly the tab count it had in the opening
inventory. The failed muse attempt leaked nothing (tab numbering skips `wEY:t4`; the list above
proves no orphan existed before the closes). Scratch git repositories and stubs live only in the
session scratchpad. `git status` in the run worktree shows no tracked change (`git diff HEAD`
empty); the only untracked files are this evidence file and the coordinator's deviation record.

## Overall verdict

**pass-with-notes** — nine of ten rows pass; the pre-L4 gate passes (`pane_account_label` →
`"personal"`), so L4 may proceed. The notes the coordinator must weigh:

1. **Row 8 fails its written evidence clause**: the unknown-posture stop fires with the exact
   message and creates no session, but only at `go`, after the run branch (at `start`) and the
   unit's worktree and branch (at `go`, `make_worktree` before `launch`) exist. A plan-time
   `resolve_permission` validation in `plan_units` would close the gap.
2. **Muse is unlaunchable on this host** (`unsupported interactive agent kind: muse` from
   `agent-herdr`), while the roster offers it — composer coverage for muse is unobtainable here,
   and any plan unit naming muse would pass `assert_vendors_available` and then fail at launch.
3. **The wrapper splits a fresh pane on tab-name reuse** (never returns the existing pane), which
   is how the one-pane-per-tab deviation on `wEY:t2` arose; the incident-shaped handback in row 5
   therefore needed the declared identity stub. Both are recorded in the coordinator's deviation
   file alongside the preserved pane captures.
