# Adding an External-Engine Provider

Saga can onboard an OpenAI-compatible Chat Completions provider as a probationary row in the
external-engine registry. The onboarding tool validates and renders the row; it does not contact the
provider, read credentials, or generate provider-specific bridge code.

The supported v1 path is intentionally narrow:

- transport is HTTP;
- the endpoint implements OpenAI-compatible `POST /chat/completions`;
- authentication is a bearer token named by an environment variable;
- dispatch uses the existing `engine-bridge-http` bridge and `http-bridge` receipt emitter; and
- the generated row is evidence-only and starts at `trust_tier: probation`.

CLI providers and non-Chat-Completions APIs need a real wrapper or bridge implementation. Do not use
this tool to create an inert registry row for them.

## Provider specification

Create a JSON object with the exact fields below. Unknown fields are rejected.

```json
{
  "transport": "http",
  "engine_id": "fixture-http",
  "variant": "fixture-chat",
  "base_url": "https://api.example.com/v1",
  "model": "fixture-chat",
  "auth_key_env": "FIXTURE_API_KEY",
  "context_window": 32768,
  "cost_speed_rank": 99,
  "cost_class": "metered",
  "cost_per_token": {
    "input_usd": 0.000001,
    "output_usd": 0.000002
  },
  "budget_ceiling_usd": 5.0,
  "latency_class": "standard",
  "model_identity": "fixture-chat",
  "last_validated": "2026-07-09",
  "capability_profile": {
    "code-generation": {
      "rating": "MODERATE",
      "note": "Provider documentation and local evaluation support this seed rating."
    }
  },
  "prompting_protocol": [
    "Return advisory evidence only."
  ],
  "sources": [
    {
      "claim": "OpenAI-compatible endpoint and model id",
      "url": "https://api.example.com/docs",
      "date": "2026-07-09",
      "tag": "OFFICIAL",
      "corroboration": "STRONG"
    }
  ]
}
```

Field rules:

| Field | Rule |
| --- | --- |
| `transport` | Must be `http`. CLI providers are rejected. |
| `engine_id`, `variant` | Lowercase letters, digits, dots, and hyphens; the pair must be unique. |
| `base_url` | Absolute HTTPS API root with a host and no credentials, query, or fragment. Saga appends `/chat/completions`. |
| `model` | Provider model identifier sent in the request body. |
| `auth_key_env` | Uppercase environment-variable name. Supply a name, never a token value. |
| `context_window` | Positive integer token limit. |
| `cost_speed_rank` | Non-negative tie-break rank; lower values win equal capability ratings. |
| `cost_class` | `metered` or `free`. |
| `cost_per_token` | Exactly `input_usd` and `output_usd`, both finite and non-negative. Free providers use zero for both. |
| `budget_ceiling_usd` | Required, finite, and non-negative for `metered`; omitted for `free`. |
| `latency_class` | `fast`, `standard`, `slow`, or `batch`. |
| `model_identity` | Stable model-family identity used by release-currency checks. |
| `last_validated` | ISO date for the provider claims and model id. |
| `capability_profile` | Non-empty map of Chat Completions capabilities and `WEAK`, `MODERATE`, or `STRONG` ratings. `embedding` is rejected by this v1 tool. |
| `prompting_protocol` | Non-empty list of provider-specific prompting constraints. |
| `sources` | Non-empty list; each source needs `claim`, `url`, `date`, `tag`, and `corroboration`. |

Supported v1 capability names are `code-generation`, `adversarial-review`, `second-opinion`,
`debug`, `refactor`, `scaffold`, `long-form-writing`, `bulk-classification`, and
`structured-extraction`. The registry's `embedding` capability is intentionally excluded because
the generic v1 bridge calls Chat Completions.

The tool derives the fields operators should not choose per provider: `substrate: external`,
`egress_policy: networked`, `trust_tier: probation`, `write_capable: false`, bearer auth,
`invocation.via: engine-bridge-http`, `invocation.effort: default`, and
`receipt_emitter: http-bridge`. The first variant for an engine id becomes its default; later variants
do not replace that default.

## Validate and apply

Dry-run first. This validates the provider specification, complete candidate registry, offline
registry-to-dispatch conformance, and final rendered YAML without changing the destination:

```bash
tools/add-engine.sh --spec provider.json
```

Use `--registry` to target a non-default registry. Add `--apply` only after reviewing the rendered
row:

```bash
tools/add-engine.sh --spec provider.json \
  --registry plugins/saga/references/engine-registry.yaml \
  --apply
```

Apply inserts only the new list item before the top-level `roles` mapping. It preserves surrounding
comments and formatting, rechecks the source hash immediately before replacement, preserves file
mode, and replaces the destination atomically. A duplicate key, invalid candidate, failed
conformance check, or concurrent edit aborts without overwriting the registry. Re-running an applied
spec therefore fails clearly instead of creating a duplicate.

Run the repository gates after apply:

```bash
uv run python plugins/saga/scripts/check_engine_registry.py
uv run python plugins/saga/scripts/engine_registry_conformance.py
uv run pytest tests/test_engine_onboarding.py tests/test_engine_registry_conformance.py -q
```

Conformance is offline. It proves exact-key lookup, capability candidate reachability, invocation
materialization through the real dispatch builder, and receipt-emitter registration. It does not
prove provider availability, credential validity, or live API compatibility. Add a separate
availability-gated smoke test when live proof is warranted.

## Probation and promotion

A probationary row can serve `worker` and `generator` offload. It cannot serve an
`advisory-reviewer` or panel role, and a composing role cannot name it. `/engines list` exposes each
row's trust tier.

Promotion eligibility comes from the hash-chained run-fact ledger. Assess the exact variant after it
has real shadow-mode traffic:

```bash
python3 plugins/saga/scripts/engine_promotion.py fixture-http/fixture-chat --json
```

Use `--ledger <path>` to assess a specific ledger. The five most recent exact-variant engine facts
must all have:

- `status: ok`;
- `proof_integrity_status: ok`; and
- a distinct, non-empty `bridge_run_key`.

Zero through four matches, a failed or unproven run, a missing or duplicate bridge key, or evidence
from a sibling variant yields `eligible: false`. A malformed input, unknown or already-advisory row,
corrupt hash chain, or ledger changing during assessment fails closed.

The assessment is read-only. An eligible result does not edit the registry, add role membership, or
grant gate authority. Promotion is a normal reviewed pull request that changes the exact row to
`trust_tier: advisory`, reruns registry and resolver tests, and remains subject to the rule that
external engines provide advisory evidence only.
