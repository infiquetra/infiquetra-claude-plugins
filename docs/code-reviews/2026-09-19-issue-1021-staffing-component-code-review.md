# Code Review — one staffing component in fleet-core, issue 1021

**Accepted.** Seven lenses ran against the branch `issue/1021`. Six returned gating findings; every
one was reproduced before repair, repaired, and re-verified. No gating finding remains.

The headline number is worth stating plainly: **fifteen gating defects, and every one of them lived
in code the author had already declared verified.**

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `issue/1021`, base `2044c363` |
| Final reviewed revision | `108ab819` |
| Roster | The four always-on lenses plus three conditionals, selected with stated applicability and approved by the caller |
| Backend | inline |
| Outcome | **accepted** |
| Repair cycles | Correctness took three, the cap. Every other lens took one. |
| Blocking findings remaining | none |
| Artifact | `docs/code-reviews/2026-09-19-issue-1021-staffing-component-code-review.md` |
| Linked issue | 1021, a child of the saga simplification parent 1018 |

## The roster

| Lens | Revision reviewed | Gating findings | Resolution |
|---|---|---|---|
| **correctness** | `1bb05a7c`, then `90b2382b`, then `1e8999e1` | 3 × P0: a test calling a helper the diff deleted; three tests pinning fleet-core's old version as a literal; saga's release surfaces never bumped | All repaired. Passed at cycle three. |
| **correctness (re-verification)** | `2ad7ec8a` | 1 × P0: a third version literal, in `plugins/mission-control/tests/` — a pytest root the journal rule written two rounds earlier did not name | Repaired, and the rule corrected. |
| **security** | `88410d52` | 1 × P1: `qualify_lens` granted `qualified` to a ledger entry with no evidence fields, because two absent values compared equal. Plus 3 malformed-data shapes raising on a path contracted never to raise. | All repaired; six malformed shapes now proven to degrade by construction. |
| **architecture and maintainability** | `3ef751af` | 1 × P1: a role's vendor and its model came from unconnected sources, so a pinned `codex` role answered `codex opus/high` — a model codex cannot run | Repaired by routing the pin through the portable execution-class vocabulary. |
| **testing** | `a048f789` | 1 × P1: `resolve_shape`'s `vendor` parameter reproduced the defect just fixed in its sibling, untested. 13 of 30 mutants survived; the suite had a guaranteed local-only failure. | Repaired; nine mutants killed; the suite made hermetic. |
| **api contract** | `609d51e7` | 2 × P1: three `role-tier:` aliases silently stopped resolving through saga's chain, against a changelog claiming behaviour was preserved; saga gained an undeclared hard dependency on fleet-core 0.26.0 | Both repaired; the obligation is now declared and enforced. |
| **documentation clarity** | `67eab820` | 3 × P1: the document stated an output shape three of its own examples contradict; a vendor key that fails silently when omitted; no import idiom for an audience it names | All repaired; knowledge the deleted documents carried restored. |
| **agent usability** | `ada32d54` | 1 × P1: a misspelled `--lens` accepted at exit zero on any host without the lifecycle checkout, reported as a policy answer | Repaired with a third status that says the name went unchecked. |

## The findings that mattered most

**The permission check that failed open.** `qualify_lens` decides whether an executor may establish
a scoring threshold for a review lens. It guarded with `entry.get("catalogue_version") != version`
and `passed != total`. An entry carrying only the four identity fields made both sides `None` on
both comparisons, so an entry proving nothing satisfied a check that reads as though it proves
everything. Every test built its entry from a fixture that always supplied all three evidence
fields, so no test could reach the branch.

**Two unconnected notions of who does the work.** A role's vendor came from its own row; its model
and effort came from the Claude-only work-shape policy; nothing translated between them. The
repair routes the pin through the portable execution-class names the vendor palette is already
keyed on. Then the testing lens found the identical hole, untouched, in the sibling entry point.

**An input class lost against a changelog that denied it.** A friendly "unknown work shape" error
was added in front of a call that accepts a wider vocabulary than the registry it validated
against. Three `role-tier:` aliases — carried in frontmatter by twenty-five agent definitions —
stopped resolving, while the changelog written in the same commit asserted the five public
functions kept "their behaviour". They kept their signatures and lost an input class.

**A dependency that only fails where nobody tests.** saga 0.160.0 loads the new fleet-core module at
import. Both installed plugin roots carry 0.25.3, where it does not exist. Inside a checkout the
resolution ladder finds the repository copy, which is why no test could see it.

## What the review cost, and what it bought

Nine repair commits after the six that built the feature. The pattern across all fifteen gating
findings is one thing, and it is now four journal entries: **the author verified what the change
touched and not what the change reached** — the sibling function, the second pytest root, the other
entry point, the wider input vocabulary, the document describing the command.

Four rules came out of it, each with a reproduction attached:

- Comparing two absent values with `!=` is how a permission check fails open.
- A test that reads a gitignored file is green on a fresh clone and red on a real machine.
- A version bump breaks every test that pinned the old version — in *every* pytest root, which
  means reading `testpaths` before trusting a sweep.
- A validity check placed before a normalising step silently narrows the input class.

## Residual findings, not gating

Recorded rather than repaired, each with its reason:

- **fleet-core hardcodes saga's `.saga/` directory name.** The architecture lens cites a journal
  decision that rejected a smaller version of the same inversion. The alternative reintroduces the
  two-constant split this card merged. Both designs are defensible; the plan chose this one.
- **The lifecycle checkout ladder is implemented twice**, here and in mission-control. Lifting it
  into a shared helper means touching a third plugin.
- **A fifth source of the work-shape bands survives** in `sdlc_manager.py`, as a hardcoded Python
  mirror. This card merged four; that one is now the only other.
- **The command-line overlay lookup has no upward walk**, so running from a subdirectory silently
  skips a repository-root overlay. Documented; the `source` field reports which layer answered.
- **A vendor-pinned role on a `haiku` work shape cannot be rendered**, because the portable
  vocabulary has three rungs and the Claude palette has four. Documented, with the error naming the
  remedy.
- **Twelve markdown files fail `ruff format --check`** and two Python files fail `ruff check`. All
  are untouched by this branch and fail identically at the base commit; the cause is an unpinned
  `ruff>=0.4` against a locally resolved 0.16.5 that formats Python inside markdown fences. This
  belongs to whoever owns the toolchain pin.

## Release facts

| Plugin | Before | After | Why |
|---|---|---|---|
| fleet-core | 0.25.3 | **0.26.0** | the new component |
| saga | 0.159.0 | **0.160.0** | the overlay reads through one implementation |
| team-execution | 3.1.1 | **3.2.0** | two reference documents repointed |
| mission-control | 2.16.0 | **2.17.0** | one comment repointed |

**Install obligation.** saga 0.160.0 requires **fleet-core 0.26.0 or later**. Both installed plugin
roots — `~/.claude` and `~/.claude-company` — carry **0.25.3 only**, and `staffing.py` is absent
from both. Verified directly, not inferred.

**Known collision.** The integration branch `parent/1018` independently bumped mission-control to
2.17.0 for the board-vocabulary card, with its own drift guard. This is not a textual conflict but
two changes claiming one version number.
