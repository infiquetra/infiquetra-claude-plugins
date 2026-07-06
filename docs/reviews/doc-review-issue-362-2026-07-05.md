# Doc Review — Dispatch-time tier resolver (#362)

**Target:** `docs/plans/2026-07-05-dispatch-tier-resolver-plan.md`
**Reviewed revision:** working tree (uncommitted)
**Linked:** issue #362 · saga `issue-362` · spec `docs/plans/2026-07-05-dispatch-tier-resolver-spec.json`
**Blocked:** NO — all findings resolved in place; no P0/P1 remain.

## Readiness verdict

The plan can safely drive implementation. Grounding was strong (verified `tier_palette.py`, the 25 team-execution agents, `plan/SKILL.md:298-304`, the dispatch-site inventory, and both sibling drafts), and the scope was operator-confirmed. The readiness-skeptic pass surfaced six findings — two P1 around the underspecified `role-tier` design — all fixed in place with repo-backed evidence.

## Findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P1 | `role-tier:` ↔ resolver-input `(role_kind, work_shape)` ↔ registry-key relationship underspecified; KTD7's role-tier names diverged from the registry work-shape keys, and a single frontmatter field can't feed a two-arg resolver without a defined derivation. | **Fixed** — R1 makes `work_shape` the primary key and `role_kind` optional; a `role-tier:` maps to a `work_shape` via an alias map; KTD7 rewritten. |
| 2 | P1 | 25-frontmatter migration semantics (tier-preserving vs role-based re-tiering) undefined; a role→default mapping could silently change an agent's effective model. | **Fixed** — verified the role→model correspondence is clean (10 `*-reviewer`=opus, 8 `*-tester`=sonnet, 7 `*-scanner`/`*-monitor`=haiku); KTD7 now specifies a tier-preserving 3-value mapping, `model:` kept as exact fallback, and a `tier_preservation` test added to U4. |
| 3 | P2 | `envelope_ceiling` appeared in the signature and a test but had no defined semantics or source in #362. | **Fixed** — R1 documents it as an optional forward-compat clamp (no live source in #362; #366 wires it later). |
| 4 | P2 | Registry couldn't represent the haiku-vs-sonnet distinction for "mechanical" work. | **Fixed** — R2 splits the registry into `mechanical` (sonnet) and `purely-mechanical` (haiku), per the `plan/SKILL.md:301` parenthetical. |
| 5 | P3 | Resolver's runtime location of `tier_policy.json` unspecified (JSON data file, not a shim-loaded module). | **Fixed** — U2 specifies `Path(__file__).parent`. |
| 6 | P3 | No top-level Verification section with the repo gate command. | **Fixed** — Verification section added. |

Line-number check: `plan/SKILL.md:298-304` is accurate (verified) — not a finding.

## Applied fixes

All in `docs/plans/2026-07-05-dispatch-tier-resolver-plan.md`: rewrote KTD7 (tier-preserving role-tier vocabulary, verified distribution); clarified R1 (signature, `role_kind` optional, `envelope_ceiling` forward-compat); R2 (mechanical/purely-mechanical registry split); U2 (JSON load path, alias map); U4 (`tier_preservation` test scenario); added a Verification section.

## Residual risk

Low. The role-tier vocabulary and the tier-preserving mapping are evidence-backed (the clean 10/8/7 role→model distribution and the SKILL's own mechanical split), and the `tier_preservation` test enforces no silent re-tiering at build. The two cross-leaf dependencies (#363 honoring, #370 vocab/ladder) are covered by the concerns filed on those issues, to be validated at each sibling's plan.

## Route

`/work` is **unblocked** (no P0/P1 remain). The spec (`…-spec.json`) is unchanged — its unit prompts are thin pointers that read the now-corrected plan as authoritative, so no spec edit was needed.
