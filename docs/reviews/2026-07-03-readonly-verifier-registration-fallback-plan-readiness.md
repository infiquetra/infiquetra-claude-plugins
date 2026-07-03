# Readiness review — readonly-verifier registration fallback plan

**Verdict: READY.** All findings were safe-fixable in place; no `P0`/`P1` remains. The plan can
drive `/work` without the implementing agent inventing missing decisions.

## Review-result contract

- **Target:** `docs/plans/2026-07-03-readonly-verifier-registration-fallback-plan.md`
- **Reviewed revision:** working tree (plan is uncommitted; repo HEAD `71faf92`)
- **Blocked:** no
- **Review type:** plan readiness-skeptic pass (plans are outside the idea/issue/spec rubric
  phases; no rubric engine run)
- **Linked issue:** infiquetra/infiquetra-claude-plugins#325
- **Linked saga:** `issue-325` (plan phase, destination merge, orchestration inline)
- **Review artifact:** this file

## Applied fixes (all evidence-backed, edited in place)

| # | Was | Fix | Evidence |
|---|---|---|---|
| 1 | R4(c) specified a bare `saga:<name>` cross-reference grep — would false-positive on skill names, which share the namespace (`/saga:work`, `saga:plan`) | Scoped the guard to spawn-context lines (`subagent_type` / `agentType`); documented why, and that bare unprefixed agent mentions are out of scope | Repo-wide grep: only `saga:readonly-verifier` matches the namespaced pattern today (passes by accident); `mechanical-executor` is referenced unprefixed at `plugins/saga/skills/work/references/execution-strategy.md:80`; the harness skill roster names `saga:plan` etc. |
| 2 | U2 said "parseable YAML frontmatter" with no parser strategy | Cited reuse of `_parse_frontmatter` at `tests/test_agent_tiering.py:18` (repo convention); noted `pyyaml>=6.0` is available but the hand-rolled parser is the established pattern for agent files | `pyproject.toml:14`; `tests/test_agent_tiering.py:18-36` |
| 3 | U1's fallback ladder implicitly assumed `Explore` exists — the same roster-name trust that caused #325 | Added an explicit rung-selection rule: a rung applies only when its agent type is present in the session roster; `general-purpose` is terminal because it is the harness default | Issue #325's own failure mode; global guidance "agent rosters change — never trust a remembered name" |
| 4 | U3 hardcoded the target version `0.49.2` | Allowed "or the next free patch version if another PR ships first" | Version-collision risk inherent to a shared registry; current `plugin.json` is `0.49.1` |
| 5 | U2 test scenarios lacked the namespace false-positive regression case | Added: a `/saga:work` prose mention must NOT be flagged | Follows from fix 1 |

## Verification performed

- Issue-claim evidence table in the plan re-checked against sources: `CLAUDE.md:9`,
  `sandbox-spawn-sites.md:44-55`, `execution_spec.py:93` (`READONLY_VERIFIER_AGENT_TYPE`),
  `tests/test_saga_plugin.py:1452-1459`, git dates `697fff1` / `9bdf363` — all hold.
- Both agent files' frontmatter `name:` matches the file stem (U2 assertion (a) passes on the
  current tree).
- `tests/test_agent_registration_drift.py` does not exist (new-file path is free).
- No overlap with `tests/test_agent_tiering.py` (pins 4 named ecosystem agents; saga structural
  agents not covered there).
- Issue proposed-fix mapping: fix 1 → R1 (evidence-only, verified live at plan time), fix 2 →
  R2/R3, fix 3 → R4. Release surfaces (R5) and journal capture (R6) per repo policy.
- Frontmatter contract: `origin:` present (issue URL, matching the #326 plan precedent);
  `Implementation Units` / `Key Technical Decisions` / `U1` markers present.

## Remaining findings

| Priority | Finding | Status |
|---|---|---|
| — | none | — |

## Residual risk from limited evidence

The environmental failure class itself (a running session with a stale plugin roster) is
unobservable from CI and untestable in-repo; the plan mitigates by fallback ladder + static
guard rather than eliminating it (Key Technical Decision 2). The deferred SessionStart
roster-staleness warning remains the only path to detection, and it is explicitly out of scope
here.
