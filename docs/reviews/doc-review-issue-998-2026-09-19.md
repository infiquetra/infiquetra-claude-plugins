# Doc review — issue 998 plan, plan_save_proof.py command-line entrypoint

The plan is ready to drive implementation. Nine findings were raised across three rounds and all
nine were repaired in the document; none remains open, and nothing is blocked.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-998-plan-save-proof-cli-entrypoint-plan.md` |
| Reviewed revision | working tree, base commit `30c36bb5` |
| Blocked | no |
| Rounds | 3 — round 1 raised 6, round 2 raised 3, round 3 clean |
| Findings | 9 raised, 9 fixed, 0 open |
| Highest open priority | none |
| Review artifact | `docs/reviews/doc-review-issue-998-2026-09-19.md` |
| Linked issue | infiquetra/infiquetra-claude-plugins#998, parent grouping #1005 |
| Saga | `issue-998`, plan tick written 2026-09-19 |
| Override rationale | not applicable |

## Findings

Every finding was verified against the repository before it was raised, and every fix is supported
by a cited file and line in this checkout.

| # | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The canary identifier `plan-save-proof-cli-entrypoint` falls outside the prefix `tests/test_wiring_canary.py:40` selects on, so the canary would be registered but never executed | fixed |
| D2 | P2 | R2 required a malformed invocation to print "that same guidance", which argparse's own usage path cannot do | fixed |
| D3 | P2 | Nothing required the entrypoint to read `sys.argv`, so the canary mutation's teeth rested on an unstated implementation property | fixed |
| D4 | P3 | The rejected-alternative count said 28 other scripts without an entrypoint; the true count of *other* scripts is 27 | fixed |
| D5 | P3 | Two cited line numbers were off by one or imprecise: the pinned version and the inventory assertion | fixed |
| D6 | P3 | R6 pinned the version `0.159.3` with no instruction to re-derive it at commit time | fixed |
| D7 | P3 | Round 2: the fourth unit still cited the old, off-by-one line for the pinned version after R6 was corrected | fixed |
| D8 | P3 | Round 2: the unit preamble said U3 pins "all four requirements" after a fifth requirement was added | fixed |
| D9 | P3 | Round 2: the fifth key decision still cited a single line for the assertion R5 now cites as a range | fixed |

### D1 — the canary would never have run (P1)

`tests/test_wiring_canary.py:40` collects the entries it executes with
`entry["id"].startswith("plan-save-contract-")`. The plan's original identifier,
`plan-save-proof-cli-entrypoint`, is outside that prefix. The separate membership assertion in
`tests/test_saga_plugin.py` only checks that every guard function appears somewhere in the
registry, so the plan as written would have passed both checks while the mutation was never run —
a hollow guard of exactly the kind the canary mechanism exists to prevent.

Fixed by renaming the entry to `plan-save-contract-proof-cli` and recording in the unit why the
prefix is load-bearing. The two existing entries that mutate this same proof file,
`plan-save-contract-proof-containment` and `plan-save-contract-proof-required`, already follow the
convention, which confirms the reading.

### D2 — an unimplementable requirement (P2)

R2 required every non-help invocation to print "that same guidance" on standard error. Argparse
emits its own usage message for a malformed argument and exits 2; making that byte-identical to
the entrypoint's bare-invocation guidance would mean overriding argparse's error path for no
behavioral gain. Fixed by requiring what actually matters — exit 2, usage text on standard error,
and an empty standard output — and saying explicitly that the two texts need not match.

### D3 — the mutation's teeth rested on an unstated property (P2)

The canary mutation works by making the entrypoint fire while `runpy` loads the file, so that the
contract tool's own arguments reach the proof's parser and raise `SystemExit`. If an implementer
wrote an entrypoint that ignored `sys.argv`, the mutation would change nothing and the canary
would report toothless. Fixed by adding R2a, which requires the entrypoint to parse the real
command line, and pointing U2 at it.

### D7, D8, D9 — the round-1 fixes left three stale internal references (P3)

Re-reviewing the repaired document found three places the round-1 edits had not reached: the
fourth unit still named the old line for the pinned version, the unit preamble still said "all
four requirements" after a fifth was added, and the fifth key decision still cited a single line
where the requirement now cites a range. All three were repaired, and a fourth pass over the same
references came back clean. This is the ordinary hazard of editing a cross-referenced document:
correcting a fact in one place leaves its copies behind.

### D4, D5, D6 — counts, references and the version pin (P3)

The count of sibling scripts without an entrypoint was 28 including the proof itself, so 27 is the
correct figure for *other* scripts. The pinned Saga version assertion is at
`tests/test_saga_plugin.py:49`, not 48, and the registry membership assertion spans lines 211-214
rather than sitting on 211. R6 now also says to re-derive the version bump from `origin/main` at
commit time, because a sibling pull request taking the same version has auto-merged silently in
this repository before.

## Readiness summary

The plan can drive implementation without the implementer inventing decisions. Its five key
technical decisions each name what was rejected and why; its four units name their files, their
test expectations and their order; and its scope boundaries rule out the two tempting expansions
(making the proof runnable standalone, and touching the sibling file repaired earlier today).

The claims were checked rather than taken on trust. The reproduction in the Problem Frame was run
in this worktree; the `runpy.run_path` naming behavior underpinning KTD3 was probed directly; and
every cited path and line number was read at base commit `30c36bb5`.

## Residual risk from limited evidence

The plan's third unit builds a throwaway virtual environment to prove `--help` works without
PyYAML, which is the second test in that file to do so. That cost is accepted rather than
resolved: the sibling guard `test_contract_cli_envelopes_a_missing_pyyaml` established the pattern
earlier today, and a stub module that merely raises on import would prove the symptom without
proving the repair.

The canary mutation's downstream effect — that an unconditionally firing entrypoint turns the
contract tool's `validate` into a refusal at exit 2 — is reasoned from the sibling guard merged in
issue #996 rather than executed, because building the temporary checkout that would demonstrate it
belongs to the implementation stage. The unit instructs the implementer to watch the guard fail
before it passes, which is where that reasoning gets tested.
