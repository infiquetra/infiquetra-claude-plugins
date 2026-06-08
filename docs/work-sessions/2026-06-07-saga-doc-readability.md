---
date: 2026-06-07
issue: 201
plan: docs/plans/2026-06-07-saga-doc-readability-plan.md
review: docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md
status: pr-ready
---

# Work Session: Saga Document Readability (#201)

Built the shared formatting contract and rolled it across all nine doc-writing skills, with a pytest gate so it can't regress.

The triggering bug — ideate's stacked-bold-label SURVIVOR SCHEMA — is fixed; the other eight skills now link the contract and apply the lead-in/short-paragraph/table rules.

## What was built (by U-ID)

| unit | what | how |
|------|------|-----|
| U1 | Shared contract `saga/references/formatting-style.md` + golden specimen | authored directly |
| U2 | ideate: `ideation-artifact.md` schema → table + lead-in (drop `**title:**`); `convergence-and-partnership.md` present-phase aligned; SKILL link | ultracode agent |
| U3 | plan: lead-in rule + contract link; kept prose-heavy per-unit branch | ultracode agent |
| U4 | brainstorm/spec/strategy: contract link + light rules | ultracode agent |
| U5 | retro/doc-review/code-review/founder-review: contract link + light rules (code-review findings left as the existing table) | ultracode agent |
| U6 | `tests/test_saga_doc_formatting.py` — collapse + link-presence gate (25 tests) | authored directly |
| U7 | DECISIONS + LEARNINGS entries; CHANGELOG 0.20.0 + 0.19.0 backfill; plugin.json + marketplace.json → 0.20.0; version-pin test | authored directly |

## Key decisions

The schema renders as a table for compact fields with narrative kept as prose — verified safe because nothing machine-parses the fields (the consumer is an LLM + a human), recorded in LEARNINGS `{#saga-doc-schema-no-field-parser}`.

The rules live in one shared reference all skills link, enforced by pytest — recorded in DECISIONS `{#saga-doc-formatting-contract}`.

Execution used the `cc-workflows-ultracode` backend: U1/U6/U7 authored directly; U2–U5 ran as a four-agent parallel fan-out over disjoint files, then every diff was verified and the agents' clickable-link style was normalized to the repo's bare `saga/references/...` convention.

## Files modified

14 skill template/SKILL files (the 9 doc-writing skills) + `plugins/saga/references/formatting-style.md` (new) + `tests/test_saga_doc_formatting.py` (new) + `plugins/saga/CHANGELOG.md` + `plugins/saga/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `tests/test_saga_plugin.py` + `docs/engineering-journal/{DECISIONS,LEARNINGS}.md`.

## Checks run

`pytest` (709 passed), `ruff format --check` + `ruff check` (clean), `validate_plugins.py` (exit 0), `marketplace/validator/validate.py` (0 errors), `json.tool` on marketplace.json (valid).

## Next step

Open the PR, confirm CI green, squash-merge (destination = merge); post-merge, fill the journal SHAs and route to `/qa` advisorily.
