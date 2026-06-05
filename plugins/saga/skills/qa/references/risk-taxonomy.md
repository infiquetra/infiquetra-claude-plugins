# QA Risk Taxonomy

The durable risk-class reference for `/qa`. The **9-way risk router** is primary: classify a change into
the classes it actually touches, run only those, narrow before broad. gstack's seven web categories and
its per-page browser checklist fold into **one** risk-driven `behavior/browser` class, driven by the
installed MCP and a graceful no-op off-UI.

---

## The 9-way risk router

| Class | What it covers | Acceptance / evidence checklist |
|---|---|---|
| **behavior** | User-visible behavior, business logic, browser/UI flows | Run the repo's behavior/integration tests; exercise the changed flow; for a UI surface run the browser MCP check (below); cite test output, logs, and MCP captures. |
| **security** | Auth, secrets, input trust boundaries, injection, egress | Confirm authz on changed paths; no secrets in code/logs; inputs validated; SQL/shell parameterized; redirect/SSRF allowlists honored. **Offer** `appsec-audit` for a real trust boundary (operator-choice); never run a destructive probe. |
| **infra** | Cluster, hosts, Ansible, networking, storage | **READ** inventory/state and confirm the change matches intent; idempotence/dry-run evidence; never mutate live infra. |
| **API** | Public/contract surfaces, request/response shapes | Contract still honored (status codes, schema, pagination, error shapes); backward-compatibility for existing clients; cite the contract + the response. |
| **deployment** | Release/promote/canary/revert config and wiring | **READ** deploy state and confirm acceptance evidence; version/tag policy honored; rollback path exists. Never deploy or mutate (`deploy` owns mutation). |
| **data** | Migrations, backfills, schema, persisted state | Migration applies + is reversible; backfill correctness on a sample; no silent data loss; cite the migration + a state read. |
| **API/config overlap → config** | Env vars, feature flags, build/CI config, settings | Required keys present + non-empty; flag defaults safe; config loads in the target env; cite the loaded value, not the source line. |
| **docs** | READMEs, references, journals, generated docs | Docs match shipped behavior; links resolve; examples run; no stale claims. |
| **trivial** | Formatting, comments, copy with no behavior change | Short-circuit: read-and-confirm there is genuinely no behavior surface; one-line evidence. |

A change usually lands in 1-3 classes. The hard-test-gate change kinds
(behavior / security / infra / api / deployment / data) are the high-risk classes; `docs` / `config` /
`trivial` are the low-risk classes.

---

## Browser as ONE MCP-driven class (the gstack fold)

gstack's seven web categories (visual, functional, ux, content, performance, console, accessibility) and
its per-page checklist collapse into the **behavior** class as a single MCP-driven check. Run it **only**
when the change has a UI surface; it is a graceful no-op for serverless / SDK / Ansible / plugin repos.

Per UI surface, using the installed **chrome-devtools / playwright MCP**:

1. **Load + visual scan** — navigate to the surface; screenshot; check for broken layout/images.
2. **Interactive elements** — click every changed button/link/control; does each do what it says?
3. **Forms** — fill + submit; test empty, invalid, and edge-case input (long text, special chars).
4. **Navigation + states** — in/out paths, back button; empty / loading / error / overflow states.
5. **Console + network** — read console messages and network requests after interactions; flag JS
   exceptions, 4xx/5xx, CORS, CSP, mixed-content.
6. **Responsiveness + a11y** — when relevant: viewport sizes, alt text, labels, keyboard nav, contrast.

Each observation becomes a finding with its MCP capture as evidence. gstack's `$B`/`browse` daemon is
not used — the installed MCP is the driver.

---

## File-pattern → risk-class map (diff-aware mode)

Map changed file paths (from Phase 0.3) to risk classes. A file may map to more than one class.

| Pattern (illustrative) | Risk class |
|---|---|
| `*.tf`, `ansible/`, `inventory/`, `*.yml` playbooks, `helm/`, `k8s/` | infra |
| `Dockerfile`, `*.tfvars`, deploy/release workflows, `deploy` config | deployment |
| `migrations/`, `*.sql`, schema files, backfill scripts | data |
| `routes`, `handlers/`, `api/`, `openapi.*`, `*.proto`, controllers | API |
| `.env*`, `settings.*`, `config/`, feature-flag files, CI config | config |
| `*.tsx`, `*.jsx`, `*.vue`, `templates/`, `views/`, `*.css`, frontend src | behavior (browser) |
| auth/, `secrets`, crypto, input parsing, URL-fetch/egress code | security |
| `*.md`, `docs/`, `README*`, generated-doc sources | docs |
| `src/`, `lib/`, service logic (non-UI) | behavior |
| formatting-only / comment-only / copy-only diff | trivial |

When a class is ambiguous, classify into the **higher-risk** class (security/data/deployment over
behavior over docs) — over-verifying is cheaper than a missed acceptance gap.

---

## Severity definitions

Adapted from gstack's issue taxonomy. Each finding carries exactly one.

| Severity | Definition | Examples |
|---|---|---|
| **critical** | Blocks a core workflow, causes data loss, or crashes the shipped thing | Submit errors out, checkout broken, migration drops rows, deploy bricks the service |
| **high** | Major feature broken or unusable, no workaround | Search returns wrong results, upload silently fails, auth redirect loop, contract break for live clients |
| **medium** | Works but with a noticeable problem; a workaround exists | Slow path (>5s), missing validation but submit still works, layout broken on mobile only |
| **low** | Minor cosmetic or polish issue | Typo, 1px misalignment, inconsistent hover state |

---

## Severity ↔ P0-P3 cross-walk (to `/code-review`)

`/qa` speaks gstack's severity vocabulary; `/code-review` speaks P0-P3. The mapping lets a routed finding
carry a consistent priority across the gate boundary.

| `/qa` severity | `/code-review` priority |
|---|---|
| **critical** | **P0** |
| **high** | **P1** |
| **medium** | **P2** |
| **low** | **P3** |

Which severities **block** the ship verdict is set by the tier (`references/qa-report.md`): Quick blocks
critical/high; Standard adds medium; Exhaustive blocks all.

---

## Runnable anchors

Restore the work-thread saga (Phase 0.2):

```bash
python3 plugins/saga/scripts/saga.py restore --saga-id <issue-N|task-slug>
```

Diff-aware scope, pre-merge / branch case (reused from `/code-review`, fetch-first to avoid a stale base):

```bash
git fetch origin <base> --quiet
DIFF_BASE=$(git merge-base origin/<base> HEAD)
git diff --name-only "$DIFF_BASE"
```

Post-merge case — the merge commit's changeset (three-dot `<base>...HEAD` is empty on `main`):

```bash
gh pr view <N> --json files
```
