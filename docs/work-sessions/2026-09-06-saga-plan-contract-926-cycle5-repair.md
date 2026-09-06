# Issue 926: cycle-5 dependency repair

Baseline: `6b7587f7879f7c0ee414ba60f6b62fc69d33db6d`, branch `work/cp918-p5-maintenance`.
The operator requests readiness for all selected lenses at overall >=9 and dimension >=7.
Independent review owns those scores and its dispatch; no acceptance is claimed here.

## U1 — Remove the edit-time pytest dependency

Read every per-lens C5 record and the merged controller record. The three active findings
(agentusab05, arch09, testing07) identify one cause. The controller dismissed 21 contradicted
findings; their implemented fixes remain in place. The roster's anchors require correct
dependency direction, bounded invocation cost and direct evidence, not just finding closure.

Moved the existing parser, independent factual checks and saved-result oracle from test
helpers into `plan_save_proof.py`. The documentation command calls it directly. The test
shim has no parser copy. Explicit proof checks survive Python optimization. A callable
save adapter uses the unchanged engine's real parser/build/save path and private roots;
its injectable Git boundary avoids subprocess discovery in empty temporary directories.
The twelve real-CLI scenarios remain, using the same independent expected snapshot.

Added an offline Python/PyYAML-only test without a tests directory; it exercises all three
operations and field, condition and renderer-fact mutations under `-O`. Added callable
save containment to the existing path-escape regression. The external inventory includes
the packaged proof. Updated moved canary anchors and registered missing-dependency,
proof-bypass and callable-containment controls. Updated prerequisites and edit outcomes
in the runbook. Historical decisions explicitly identify the superseded pytest mechanism.

Evidence: baseline valid carrier refused without pytest (exit 2); baseline 25 tests took
194.43 seconds. After extraction and removing irrelevant Git discovery, 68 focused tests
pass in 25.08 seconds; mypy passes for 349 files. All 19 registered canaries were caught and the external packaging guard passed (71.48 seconds).
The callable-containment fault injection was then made side-effect-free and its canary
reconfirmed caught. Final gate remains pending. See
[dependency receipt](../evidence/issue-926/cycle5-dependency-repair.json).

Scope: no runtime, carrier schema, generated prose, board sentences, model/effort confirmation,
five unrelated rows, manifest or marketplace changes. Current integrator version 0.157.0
is preserved. No push, PR, merge, board/issue write or review dispatch.

Next: assemble dimension-level evidence and run the full gate at the frozen final commit.
