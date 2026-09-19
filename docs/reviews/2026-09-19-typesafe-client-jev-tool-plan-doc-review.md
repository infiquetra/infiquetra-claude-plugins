# Doc review — the TypeSafe client and `jev` tool plan (issue 1032)

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-typesafe-client-jev-tool-plan.md` |
| Reviewed revision | working tree on branch `issue/1032`; round 1 reviewed the pre-commit draft, round 2 reviewed commit 8f865a3c |
| Linked issue | infiquetra/infiquetra-claude-plugins#1032 |
| Linked plan saga | `issue-1032`, plan tick recorded 2026-09-19 |
| Classification | plan document — not an idea, issue, or spec artifact, so no rubric-engine phase applies |
| Triggered lens | security and external integration (an API credential, and repository content sent to a third-party vendor) |
| Rounds | 2 |
| Blocked | no |
| Findings after round 2 | 0 at P0, 0 at P1, 0 at P2, 2 at P3 |
| Safe fixes applied | 7 in round 1, 18 in round 2 |

## How this review was run

The plan's author also ran the review, so the pass was split two ways and run twice.

Round 1 was the author's own readiness-skeptic pass, checking the plan's external assumptions against live sources rather than against the documentation it cites. It produced seven fixes and left three P2 and two P3 findings.

Round 2 was an independent adversarial reviewer on a disposable read-only worktree, asked to refute the plan's factual claims, its requirement mapping, and its security posture. It returned two P0 and seven P1 findings, plus nine P2 and three P3. Three of those had already been fixed in round 1, because the reviewer read the pre-repair draft. The rest were real, and all are now repaired. The reviewer independently re-verified every repository citation in the plan and found them accurate.

Every finding at P0, P1, and P2 is closed. Nothing was downgraded to make the review pass.

## Round 1 — fixes from the author's pass

1. **The evaluation harness had nothing to replay.** The card's third acceptance criterion asks `jev eval --cached` to reproduce the tier probe's 10 of 10, but the research inputs folder holds five research briefs, five probe scripts, the candidate ideas, and a rendered ranking table — and no recorded API responses. The ten tasks and their expected tiers exist only as literals inside `tier_probe.py.txt:9-20`. Added R18a and R18b, rewrote U6 to seed the cache from one live run, recorded the gap in Open Questions.

2. **A yes/no answer carries no confidence field.** A live request returned `{"type": "noul", "noul": 0.97}` with no confidence, while a choice answer returned choice, confidence, and probabilities. Added R10a.

3. **The retry helper does not cover HTTP 529 by default.** `retry_backoff.py` retries on 429 only. Added the constraint and a mandatory test scenario to U2.

4. **A wrong claim about type checking**, corrected in KTD4: `pyproject.toml:84` already excludes `plugins/.*/scripts/` from mypy, so the suffix question does not turn on type checking.

5. **The result object was unspecified** — pinned to a frozen dataclass with its field list.

6. **The harness input format was unspecified** — added R18b.

7. **Rate-limit behavior was assumed** — the live response returned no rate-limit headers, recorded in the design section with a test scenario for a missing `Retry-After`.

## Round 2 — the two P0 findings, both repaired

**P0-1, the missing benchmark data.** Already closed by round 1 fix 1; the reviewer read the earlier draft.

**P0-2, the cache key was uncomputable at lookup time.** R12 keyed the cache on the *resolved* model version, but the resolved version only arrives with the response, and the design's own diagram puts the lookup before the transport. Every resolution available to an implementer silently lost a stated property: keying on the alias would serve a stale `jev-1.13.0` answer after the alias moved, and keying on the resolved version could never hit at all for the documented default. Repaired by rewriting R12 to key on the requested alias, adding R12a for an alias-to-version pin that invalidates the bucket when the resolution changes, correcting the diagram, and replacing one cache test scenario with three.

## Round 2 — the seven P1 findings, all repaired

**P1-3, no unit owned the live latency criterion, and the chosen default might have broken it.** The card requires a live call under two seconds; no requirement mentioned latency and no unit ran it, while KTD1 made the heavier SDK the default transport. Measured on this machine rather than argued: importing pydantic and httpx costs 0.13 to 0.26 seconds cold against 0.05 for `urllib`, and the live call measured 0.44 seconds, so the SDK path lands near 0.7 seconds and the default stands. Added R6a, assigned it to U5, and recorded the measurement in KTD1.

**P1-4, the key requirement was unenforceable on the SDK path.** The vendor's quickstart lets the package read `TYPESAFE_API_KEY` itself, through its code and its exception text, so R3's "read through the injected environment reader, placed only in the header" described the `urllib` path alone — and the containment test used a fake SDK client, so it would have passed regardless. Added R3a requiring the key be passed explicitly and the SDK's exceptions re-raised with messages this repository composes.

**P1-5, redaction landed one unit after a working client.** U2 delivered a complete client over both transports and U3 delivered redaction, so an intermediate revision would send raw state to a third party, and U2's own containment test inspects results and logs rather than the outbound body. Repaired by requiring the transports to refuse any state lacking the preparation marker from U2 onward, with a test asserting an unprepared state raises.

**P1-6, three retry details were wrong or missing.** The default predicate lives at `retry_backoff.py:140` and `:166-168`, not the lines cited; the delay goes through an injected `sleep`, not `clock`, so two test scenarios were unwritable as phrased; the helper retries on a raised exception while the mirrored pattern catches and returns, a boundary the plan never named; and the helper has no total-deadline parameter, so R5's wall-clock bound is work this unit writes rather than an argument it passes. All four stated in U2, and `sleep` added to the declared seams.

**P1-7, the two transports return different shapes.** The raw endpoint returns one `answers` mapping; the SDK returns per-type buckets read as `response.nouls[key].noul`. The plan asserted interchangeability and planned to prove it by comparing two hand-written fakes, which would agree by construction. Added a design section requiring a field-by-field normalization table, naming the two facts to confirm against the installed package, and requiring the equivalence test to drive both transports from one recorded payload.

**P1-8, the verdict log would have died with the worktree.** Agents here run in worktrees under `.claude/`, which is git-ignored, so a repository-root log is per-worktree and destroys the durability R10 asks for. Pinned the default to `~/.claude/typesafe/verdicts.jsonl`, matching `audit_store.py:53`, with a test asserting it resolves outside the repository tree.

**P1-9, the harness input format.** Closed by round 1 fix 6, and strengthened: `id` named as the join key and matched to the verdict log's `decision_id`, and R18c added with literal default confidence bands.

## Round 2 — the nine P2 findings, all repaired

The wire contract (endpoint, request body, all three question shapes, response body) is now written into the plan instead of living only in a probe script. U5's verification no longer claims type checking, and the scope boundaries state that all four new modules sit outside the mypy scope. The truncation estimate is pinned at three characters per token as a named constant, with the questions-over-budget case stated. The high-entropy redaction rule has a literal threshold — 40 characters, entropy 4.0 bits per character, not firing on lock-file hash forms — plus a fixture test over a real hunk of `uv.lock`, since a rule without a threshold would have shredded the first real diff. Transport selection now fails loudly on an unrecognized or unsatisfiable override rather than falling through silently. Cross-module loading goes through `fleet_commons_shim.load` with the `cost_weights.py:37` precedent cited. The dropped thirty-issue benchmark is now named in Open Questions with the reason. The reinterpretation of the card's freshness clause is flagged rather than assumed. The data-rule document gained a drift guard, so U7 is no longer test-free.

## Remaining findings

### P0, P1, P2

None.

### P3

**P3-1 — U7's data-rule document lists the ten house rules by reference** to the research document's section 8 rather than restating them, so it depends on a file under `docs/analysis/` staying put.

**P3-2 — The plan does not say how a caller outside the repository invokes the tool.** The acceptance criteria run it from the repository root; the `urllib` transport exists precisely to serve callers that are not there, and they would need an absolute path or an installed entry point.

## Notes carried to the operator

Three items need the operator and are not review findings, because a reviewer cannot settle them.

The plan ships the tool as `plugins/fleet-core/scripts/jev.py` while three of the card's four acceptance criteria name `jev.py.txt`.

The card's thirty-issue evaluation benchmark is not planned. It scored 17 of 30 and 19 of 30 in the research, figures the research itself attributes to label noise, so there is no meaningful number to reproduce.

The cache-seeding run in U6 produces fresh answers, not the originals. If it scores below 10 of 10, that is a reproducibility result to report, not a number to engineer toward.
