---
name: handoff
description: Route durable Infiquetra lifecycle artifacts into mission-control prepared issue drafts.
---

# Handoff

Use this when the user wants another team, agent team, or later session to pick up work from an
Infiquetra lifecycle artifact.

## Boundary

`saga` owns the handoff moment:

- select the durable source artifact or active pointer;
- infer lifecycle phase and handoff maturity;
- capture why the work is being handed off, blockers, open questions, target team, and target
  repository when known;
- route to `mission-control`.

`mission-control` owns the issue artifact:

- issue body sections;
- prepared draft markdown and JSON sidecar;
- readiness checks;
- labels, project fields, board placement, and GitHub mutation;
- create-after-confirmation mutation plan.

Do not copy SDLC issue templates into this skill.

## Deploy edge

The mission-control boundary above governs the saga -> mission-control handoff. A separate,
narrower contract governs the saga -> `deploy` edge, when a merged item's destination includes
deploy: a sibling module, `plugins/saga/scripts/deploy_handoff.py`, mints an **offer** (an ack
token + a gate-or-auto payload) and requires `deploy` to explicitly **accept** before ownership
is considered transferred.

- **Offer.** The releasing side (`/work`, at or after merge) mints the offer:

  ```bash
  python3 plugins/saga/scripts/deploy_handoff.py offer \
    --saga-id <saga-id> --offered-by <identity>
  ```

  The payload is never supplied at the command line — it is read from the saga record's
  `deploy_autonomy` field (`gate` or `auto`, captured once at `/plan` intent time; absent reads
  the safe `gate` default). A repeat offer rotates the token and supersedes the prior one, so a
  stale token can never be acked.

- **Accept.** `deploy` explicitly accepts (see `plugins/deploy/skills/deploy-state/SKILL.md`,
  "Accepting a saga handoff"). The ack is write-once and durable
  (`.claude/saga/sagas/<saga_id>/deploy_handoff.json`).

- **Unacknowledged, never silently done.** Until the ack is recorded, `deploy_handoff.py reconcile`
  derives `handed-off-unacknowledged` — the item is never read as `deployed`/`done` on an offer
  alone.

- **Gate never auto-fires.** A `gate` payload always blocks pending explicit confirmation on the
  deploy side; only `auto` authorizes unattended nonprod promotion. This posture travels with the
  offer and cannot be widened at accept time.

This is additive to the mission-control boundary, not a replacement for it — `/work` still routes
issue comments and board moves through `mission-control`; only deploy-bound ownership transfer
uses this ack contract.

## Workflow

1. Prefer an explicit source path or URL from the command arguments.
2. If no source is explicit, inspect `.claude/saga/state.json` and durable docs.
3. Build the envelope:

   ```bash
   python3 plugins/saga/scripts/handoff_envelope.py \
     --source docs/plans/example.md \
     --target-team Asgard \
     --target-repo infiquetra-claude-plugins
   ```

4. If the helper finds no source, ask for one.
5. If multiple durable artifacts are plausible, ask the user to choose.
6. Route with the envelope's `suggested_command` ONLY when `handoff_maturity` is one of the routable vocabulary values —
   `idea-ready`, `requirements-ready`, `plan-ready`, `resume-ready`, or `deferred-context`. For those values it is shaped like
   `/issue --prepare --from <source> --maturity <maturity>` and is runnable. When `handoff_maturity` is `pending-confirmation`, empty, or starts with `unknown:` (unreadable file, unterminated block, non-delimited frontmatter carrier, or unrecognized declared value), `suggested_command` is a non-routable prose diagnostic with no durable route and is NEVER a runnable command — stop, show the diagnostic, and have the declaring artifact's frontmatter fixed; do not route.
7. Review the prepared issue draft before mutation.
8. Use `issue create-prepared` only after confirmation.

## Maturity

A declared frontmatter `maturity` wins over path inference when it is an unindented, non-bulleted key inside a closed delimited `---` block. An indented key is nested and is ignored; a bulleted key at column 0 counts; a source the containment rules refuse to read, including an absolute path outside the declared root whose path carries no marker directory, is never consulted and resolves by path inference instead.

- `docs/ideation/` -> `idea-ready`
- `docs/brainstorms/` -> `requirements-ready`
- `docs/brainstorms/` frontmatter `pending-confirmation` -> `pending-confirmation` (no durable route)
- `docs/specs/` -> `requirements-ready`
- `docs/plans/` or `docs/reviews/` -> `plan-ready`
- `docs/work-sessions/` or branch refs -> `resume-ready`
- explicit preserve/defer language -> `deferred-context` when the user says execution should wait

Beyond these, two fail-closed states carry no route: an empty declared value, and an `unknown:`-prefixed sentinel. The sentinel carries one of four causes — `unknown:unreadable` when the file cannot be opened or cannot be decoded into text carrying a maturity declaration, `unknown:unterminated:` for an opening `---` with no closing `---`, `unknown:carrier:` for a maturity declared outside a delimited block, and `unknown:unrecognized:` for any other value (see `saga-spec.md` §9 and `DECISIONS.md` `{#913-maturity-unknown-sentinel}`). All three non-vocabulary shapes (`pending-confirmation`, empty, `unknown:`-prefixed) mean stop — never route.

## Recipient Guidance

Prepared issues must be self-contained for recipients without `saga`.

When a recipient does have `saga`, the issue may suggest:

- `/plan <issue>` for `idea-ready` or `requirements-ready`;
- `/work <issue>` for `plan-ready` or `resume-ready`.

Do not suggest `/loop` for normal team handoff.
