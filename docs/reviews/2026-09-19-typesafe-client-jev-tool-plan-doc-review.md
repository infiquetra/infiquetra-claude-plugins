# Doc review — the TypeSafe client and `jev` tool plan (issue 1032)

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-typesafe-client-jev-tool-plan.md` |
| Reviewed revision | working tree, uncommitted, on branch `issue/1032` (base commit 2044c363) |
| Linked issue | infiquetra/infiquetra-claude-plugins#1032 |
| Linked plan saga | `issue-1032`, plan tick recorded 2026-09-19 |
| Classification | plan document — not an idea, issue, or spec artifact, so no rubric-engine phase applies |
| Triggered lens | security and external integration (an API credential, and repository content sent to a third-party vendor) |
| Blocked | no |
| Findings remaining | 0 at P0, 0 at P1, 3 at P2, 2 at P3 |
| Safe fixes applied | 7 |

## How this review was run

The plan's author also ran the review, so the pass was split. An independent adversarial reviewer was dispatched on a disposable read-only worktree to attempt to refute the plan's factual claims, its requirement mapping, and its security posture. In parallel the author ran the readiness-skeptic pass and checked the plan's external assumptions against live sources rather than against the documentation the plan cites.

The second check is what produced the two substantive findings below. Both were repaired in place, which is why they appear as applied fixes rather than as open findings.

## Safe fixes applied

Each is supported by evidence gathered during the review, not by preference.

1. **The evaluation harness had nothing to replay.** The card's third acceptance criterion asks `jev eval --cached docs/analysis/2026-09-18-typesafe-jev-research-inputs/` to reproduce the tier probe's 10 of 10. A search of that folder for recorded responses found none: it holds five research briefs, five probe scripts, the thirty-two candidate ideas, and a rendered ranking table, and the ten tasks with their expected tiers exist only as literals inside `tier_probe.py.txt:9-20`. As written the criterion was unsatisfiable. Added requirements R18a and R18b, rewrote unit U6 to seed the cache once from a live run and commit the answers, and recorded the gap in Open Questions.

2. **A yes/no answer carries no confidence field.** A live request on 2026-09-19 returned `{"type": "noul", "noul": 0.97}` with no `confidence`, while a choice answer returned `choice`, `confidence`, and `probabilities`. The plan's verdict record (R10) assumed a confidence on every answer. Added R10a fixing how a yes/no answer is recorded and banded.

3. **The retry helper does not cover HTTP 529 by default.** `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py:38-40` retries on status 429 only, but requirement R5 needs 429 and 529. The plan named the helper without naming that gap. Added the constraint and a mandatory test scenario to unit U2.

4. **A wrong claim about type checking.** The plan argued that shipping the tool as `jev.py.txt` would cost linting, type checking, and importability. Type checking is lost either way: `pyproject.toml:84` already excludes `plugins/.*/scripts/` from mypy. Corrected KTD4 to claim only what is true, and added that `fleet_commons_shim.load()` could in fact load a `.txt` file by path.

5. **The result object was never specified.** "A result object carrying status, answers, model…" left the implementer to choose between a dictionary and a class. Pinned it to a frozen dataclass in unit U2, with the field list and the reason.

6. **The evaluation harness's input format was never specified.** Added R18b naming the record shape and accepting the verdict log as a second input.

7. **Rate-limit behavior was assumed, not observed.** The live response returned no rate-limit headers at all, so the client cannot pace itself pre-emptively. Recorded the observation in the design section and added a test scenario for a 429 with no `Retry-After` header.

## Remaining findings

### P0

None.

### P1

None.

### P2

**P2-1 — The two transports are asserted to be interchangeable, but only one test proves it.** Unit U2 has a scenario comparing the SDK and `urllib` results for one recorded response. One example is thin for a claim the whole design rests on; a shared parameterized suite running every applicable scenario against both transports would prove it properly. Suggested fix: make the transport a test parameter across the unit rather than a single comparison case.

**P2-2 — The truncation ladder's token estimate is described but not pinned.** Unit U3 says the budget uses "a conservative character-to-token estimate that errs toward cutting more rather than less" without naming the ratio. Two implementers would pick different numbers, and the ladder's determinism requirement (R9) is about reproducibility across machines, which a hand-chosen constant satisfies only if it is written down. Suggested fix: name the ratio in the plan or require it to be a named module constant with its rationale in a comment.

**P2-3 — The confidence floor in the verb registry has no consumer in this card.** Unit U5 stores a confidence floor per verb (requirement R14), but nothing in this card reads it; the first consumer is issue 1033. That is defensible as foundation work, but the plan should say so explicitly so a reviewer does not read it as dead code. Suggested fix: one line in the scope boundaries naming the floor as a field populated here and consumed downstream.

### P3

**P3-1 — Unit U7 lists the ten house rules by reference.** It points at the research document's section 8 rather than restating them, so the reference document's content depends on a document under `docs/analysis/` staying put. Minor, but a reference file that cannot be read standalone is less useful than one that can.

**P3-2 — The plan does not say where the `jev` tool is invoked from.** The acceptance criteria run it as `uv run python plugins/fleet-core/scripts/jev.py …` from the repository root. Callers outside the repository, which the whole `urllib` transport exists to serve, would need an absolute path or an installed entry point. Worth a sentence, though it does not block the work.

## Notes carried to the operator

Two items in the plan need the operator's eye and are not review findings, because a reviewer cannot settle them:

The plan ships the command-line tool as `plugins/fleet-core/scripts/jev.py`, while three of the card's four acceptance criteria name `jev.py.txt`. The evidence that the suffix is a copy artifact is strong, but the criteria are the operator's text.

The seeding run in unit U6 produces fresh answers, not the originals. If it scores below 10 of 10, that is a reproducibility result to report, not a number to engineer toward.
