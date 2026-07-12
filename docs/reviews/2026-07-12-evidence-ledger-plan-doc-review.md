# Doc review — evidence-ledger plan (#398)

Verdict: **READY** — all findings were evidence-backed and fixed in place; nothing remains open.

## Review-result contract

- **Target:** `docs/plans/2026-07-12-evidence-ledger-plan.md`
- **Reviewed revision:** working tree on `outcome/evidence-integrity` (base commit `7fd3907`;
  plan file untracked at review time)
- **Blocked status:** NOT blocked — zero unresolved P0/P1
- **Linked issue:** infiquetra/infiquetra-claude-plugins#398 (root leaf of outcome
  `evidence-integrity`)
- **Linked plan saga:** `issue-398` (git-ignored, machine-local)
- **Review artifact:** `docs/reviews/2026-07-12-evidence-ledger-plan-doc-review.md` (this file)
- **Rubric engine:** not run — the rubric phases are `idea`/`issue`/`spec`; no plan-phase rubric
  exists, so the readiness-skeptic pass is the operative review for a `docs/plans/` artifact.
- **External-engine offer:** `engine_offer.py offer --stage doc-review` → stored preference,
  `intent: none`, no prompt required; no external panel dispatched.

## Findings and dispositions

All eight findings were fixed in place per the operator's instruction ("fix all issues found");
every fix is backed by document, issue, or repo evidence — none invents a decision.

| ID | Pri | Finding | Status |
|---|---|---|---|
| D1 | P1 | KTD6 reused `_write_once`/`_atomic_write` but omitted the `_safe_name` path-traversal guard, despite saga-id/check_id/SHA flowing into filesystem paths — both existing stores sanitize (`outcome_store._safe_name`, wrapped at `manifest_store.py:72-82`) | FIXED — KTD6 now mandates `_safe_name` on every path-bound identity component; U1 test scenario adds a traversal-shaped-id rejection case |
| D2 | P1 | U4 left the no-saga case unspecified: `/code-review` §5.4 explicitly documents interactive runs with no work-thread saga, but R7 requires every artifact write to pass through the ledger — an implementer would have had to invent the fallback | FIXED — U4 now specifies the `docs/evidence/adhoc-<branch-slug>/` fallback scope (slug from the branch-or-pr stem the artifact filename already uses); only the saga tick is skipped, never the custody entry; test scenario extended |
| D3 | P1 | Both criteria-freeze wiring anchors were wrong: "qa Phase 1 check-class selection" (actual: Phase 1 is Risk classification; checks run in Phase 2) and "code-review scope-lock" (no such step; intent is pinned in Phase 1 "Intent and built-vs-planned audit") | FIXED — anchors corrected against `plugins/saga/skills/qa/SKILL.md:140,154` and `plugins/saga/skills/code-review/SKILL.md:118` headings |
| D4 | P2 | Attempt assignment unspecified (auto-increment vs caller-passed) — two implementers would build incompatible no-clobber semantics | FIXED — KTD2 now states: ledger auto-assigns next attempt per (check_id, reviewed_sha) group; an explicit `--attempt` is strict and rejects on collision |
| D5 | P2 | Torn/malformed trailing JSONL line behavior unspecified; `outcome_store` quarantines, but quarantine-and-continue is wrong for committed evidence | FIXED — KTD7 now mandates HALT with the offending line number, with rationale distinguishing the disposable cache from committed evidence; U1 test scenario added |
| D6 | P2 | The issue's "Files expected to change" lists three survivor JSONs the plan never mentions; verified the survivor schema has no stampable ship-status field (`verdict`/`dod_sketch` only) | FIXED — recorded as a deferred scope note: advisory issue-map metadata, confirm stamping at `/handoff`/`/retro` |
| D7 | P3 | Criteria filename `<sha>` ambiguous (short vs full) | FIXED — full 40-char SHA specified |
| D8 | P3 | Closure entry's relation to its own verification scope undefined (self-reference) | FIXED — U3 now states the closure entry certifies preceding entries and appends only after success |

## Evidence verified during review

- Grounding-brief citations are real: the probe-overwrite-FAIL-with-PASS incident at
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151`; "evidence-artifact
  immutability" in the §8 direct-to-candidate pool; provenance re-verification as §6 pattern 2.
- Precedent line refs are accurate: `_atomic_write`/`_write_once` at
  `plugins/saga/scripts/outcome_store.py:195-220`; `manifest_store` private-helper reuse at
  `plugins/saga/scripts/manifest_store.py:72-82`.
- Wire-through targets exist verbatim: `plugins/saga/skills/qa/SKILL.md:269` ("5.1 Write the
  durable artifact"), `plugins/saga/skills/code-review/SKILL.md:306` ("5.3 Write the durable
  artifact"). The issue's `plugins/saga/scripts/qa/SKILL.md` path is a typo (directory absent);
  the plan correctly targets `skills/`.
- All seven issue `-k` test filters map to plan test names as substrings; saga plugin version
  0.80.0 confirmed (release unit bumps to 0.81.0); outcome spec confirms sub-398 `backend:
  inline`, `depends_on: []`, with sub-396/397/402 downstream.

## Residual risk

- The `adhoc-<branch-slug>` fallback (D2 fix) is a reviewer-chosen default implied by the
  surrounding contract, not an issue-stated requirement — flag at implementation review if a
  better identity source emerges.
- Rubric-engine coverage does not include plan-phase artifacts; this review's rigor rests on the
  readiness-skeptic pass alone.
