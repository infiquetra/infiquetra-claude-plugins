# Coordinator record — runtime checkpoint topology deviation and evidence preservation

**Run:** issue 907, Agent Launcher session contract.
**Recorded by:** the run coordinator, on operator correction, before any cleanup was performed.

## The deviation

The runtime checkpoint created disposable Herdr workspace `wEY` and, inside it, split tab `wEY:t2`
into two panes:

| Pane | Session name | Probe |
|---|---|---|
| `wEY:p2` | `cp907-ck-claude` | the `ready` probe — a live Claude session with an empty composer |
| `wEY:p3` | `cp907-ck-claude-2` | the `again` probe — a live Claude session holding unsent staged text |

The approved run contract requires **one named tab per role or session and exactly one pane per
tab**, and forbids split panes. A two-pane tab violates that rule. Every other tab the checkpoint
created — `cp907-ck-bypass`, `cp907-ck-codex`, `cp907-ck-grok`, `cp907-ck-agy`, `cp907-ck-qwen`,
`cp907-ck-opencode` — carries exactly one pane and conforms.

## Purpose the split was serving

The plan's checkpoint table requires two reused-pane rows: a pane whose input box is empty, and a
pane holding staged text that was typed but never submitted. Both require a session the launcher did
**not** create, so that ownership reads false. The checkpoint obtained the second session by
splitting the first session's tab.

**The split was avoidable.** Ownership is decided by whether a tab id appears in the pre-launch
snapshot, not by pane adjacency, so two separate single-pane tabs created before the launch satisfy
the same condition. Any repeat of this proof uses one named tab per session with exactly one pane
per tab.

## Evidence preserved verbatim

Both probes are bounded, real, and useful, so their exact terminal state was captured before any
cleanup. Reproduced verbatim below.

### `wEY:p2` — `cp907-ck-claude`, the `ready` probe, empty composer

```
❯ Do nothing and reply with the single word: ready.

⏺ ready

✻ Cogitated for 2s · done 12:35 PM

──────────────────────────────────────────────────────────────────────────────────────
❯
──────────────────────────────────────────────────────────────────────────────────────
  jefcox:/infiquetra/orch-claude-plugins-907 (work/cp907-launcher-session-contract)
  Haiku 4.5 │ 47.8K/200.0K 24%
  -- INSERT -- ⏸ manual mode on
```

The composer row is `❯` followed by nothing. This is the empty-reused-box input.

### `wEY:p3` — `cp907-ck-claude-2`, the `again` probe, staged text unsent

```
❯ Do nothing further. Reply with the single word: again.

⏺ again

✻ Cooked for 3s · done 12:36 PM

─────────────────────────────────────────────────────────────────────────────────────
❯ harmless staged text for cp907 checkpoint
─────────────────────────────────────────────────────────────────────────────────────
  jefcox:/infiquetra/orch-claude-plugins-907 (work/cp907-launcher-session-contract)
  Haiku 4.5 │ 47.7K/200.0K 24%
  -- INSERT -- ⏸ manual mode on
```

The composer row reads `❯ harmless staged text for cp907 checkpoint`. The last completed turn is
`again` at 12:36 PM, so the staged string was typed after it and never submitted. This is the exact
condition unit L2 exists to detect, reproduced on a live pane rather than in a fixture.

Full captures, including ANSI styling for every checkpoint pane, are held at
`cp907-checkpoint-evidence/` in the coordinator's session scratchpad. Styling is retained because
the L2 discriminator distinguishes unstyled staged text from a dim-styled client placeholder.

## Boundaries observed

Workspace `wEV`, which holds the run's own roles, was not touched. Workspaces `wEW` and `wEX` belong
to two unrelated concurrent runs on this machine and were not touched. Only `wEY` and its own tabs
are checkpoint-owned and therefore in scope for cleanup.

## Disposition

1. Evidence captured verbatim before any cleanup. **Done** — recorded above.
2. Wait for all checkpoint work in `wEY` to settle. Cleanup does not begin while work is live.
3. Clean only checkpoint-owned sessions, tabs, and the disposable workspace `wEY`.
4. Read back the final topology and confirm `wEY` is empty or removed, and that `wEV`, `wEW` and
   `wEX` are unchanged.
5. Any proof that must be repeated is recreated with one named tab per session and exactly one pane
   per tab.

---

## Coordinator disposition of the checkpoint outcome

**Topology verification, performed after the checkpoint settled and cleaned up.** The checkpoint
closed all seven of its owned tabs through the launcher's own `close --receipt-json` path, and the
guard correctly refused the one unowned receipt. Verified independently:

| Check | Result |
|---|---|
| `wEY` present in `herdr workspace list` | **No** — removed |
| `wEV` tabs / panes | 6 tabs, exactly 1 pane each, **no split** |
| `wEW`, `wEX` (unrelated concurrent runs) | 6 tabs each, unchanged |

The split tab `wEY:t2` is gone with the workspace. Its evidence survives verbatim above, so nothing
was lost by the cleanup. **No proof needs repeating**: neither probe's verdict depended on the two
panes sharing a tab — ownership is decided by the pre-launch tab-id snapshot, and each probe was
read individually by pane id.

**Row 8 of the checkpoint failed. It is not sent back to the worker.** The row asserts that an
unknown posture stops "before any worktree, branch, or session is created". Observed: `start`
accepts the bad posture and creates the run branch; at `go` the unit's worktree and branch are
created by `make_worktree` before `launch` builds the argv that raises. The stop itself fires with
the exact message `unknown permission 'bypasss' for vendor 'claude'`, with no silent fallback and
**no session created**.

Compared against issue 896's own eight acceptance criteria, every one is met. None of them requires
the stop to precede worktree creation; that clause exists only in this plan's checkpoint row, where
it overstates the child. The underlying concern — that a bad plan is discovered only by starting a
run — is **already filed as issue 879, "Orchestrate has no non-mutating plan validator", a child of
the sibling parent issue 909.** Implementing plan-time validation here would take work from another
parent's child, which this run's contract forbids. Recorded as a residual, not repaired.

`muse` could not be covered in the vendor-marker row: the wrapper refuses it outright with
`unsupported interactive agent kind: muse`, so no muse pane can exist on this host. Written down
rather than assumed, per the row's own instruction. `opencode` fell to the allowed unreadable branch.

**Pre-L4 gate: PASSES.** `pane_account_label('wEY:p2')` returned `"personal"`, not `None`. This host
paints an account statusline, so L4 does not convert a previously succeeding launch into a hard
stop here. L4 is released.
# Supersession note — 2026-08-30 final residual repair

The staged composer text quoted below is historical probe evidence, not a field the shipped receipt
retains. The final issue 907 guard records only the staged category and character count, and its
stop message withholds the text itself.
