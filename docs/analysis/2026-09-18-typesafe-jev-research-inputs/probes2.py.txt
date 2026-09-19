import json, urllib.error
from jev import ask

TYPES = {"capability": "A new capability or feature that does not exist yet",
         "enhancement": "An improvement to behavior that already exists and works as designed",
         "defect": "Existing behavior is broken, wrong, or regressed",
         "exploration": "Investigate, spike, or research before deciding what to build",
         "context-update": "Update docs, guidance, CLAUDE.md, journal, or other context; no code behavior change"}
PRIO = {"high-priority": "Blocks work, a release, or correctness of the product; act soon",
        "medium-priority": "Real problem or clear value, but nothing is blocked",
        "low-priority": "Nice to have, cosmetic, or can wait indefinitely"}
issues = json.load(open("issues.json"))
def pick(iss, keys):
    hits = [l["name"] for l in iss["labels"] if l["name"] in keys]
    return hits[0] if len(hits) == 1 else None

# (a) issue-type + priority benchmark against real labels
rows = [i for i in issues if pick(i, TYPES)][:30]
ok_t = n_t = ok_p = n_p = 0; ms = 0; conf = []
for i in rows:
    q = {"type": {"type": "choice", "instructions": "Which SDLC issue type fits this GitHub issue (`title`, `body`)?", "criteria": TYPES}}
    if pick(i, PRIO):
        q["prio"] = {"type": "choice", "instructions": "What priority does this GitHub issue (`title`, `body`) deserve?", "criteria": PRIO}
    out = ask({"title": i["title"], "body": (i["body"] or "")[:2500]}, q); a = out["answers"]; ms += out["_ms"]
    n_t += 1; hit = a["type"]["choice"] == pick(i, TYPES); ok_t += hit; conf.append((a["type"]["confidence"], hit))
    if not hit: print(f"  type miss #{i['number']}: label={pick(i,TYPES)} jev={a['type']['choice']} conf={a['type']['confidence']:.2f} :: {i['title'][:70]}")
    if "prio" in a:
        n_p += 1; hp = a["prio"]["choice"] == pick(i, PRIO); ok_p += hp
        if not hp: print(f"  prio miss #{i['number']}: label={pick(i,PRIO)} jev={a['prio']['choice']} conf={a['prio']['confidence']:.2f}")
hi = [h for c, h in conf if c >= 0.6]; lo = [h for c, h in conf if c < 0.6]
print(f"(a) issue TYPE agreement {ok_t}/{n_t}; PRIORITY agreement {ok_p}/{n_p}; mean {ms//n_t}ms; "
      f"type acc when conf>=0.6: {sum(hi)}/{len(hi)}, when conf<0.6: {sum(lo)}/{len(lo)}")

# (b) latency and limits on a real diff
diff = open("last_pr.diff").read()
plugins = ["saga","orchestrate","mission-control","team-execution","deploy","unifi","redis-channel","home-lab-ops","agy","codex","agent-launcher","fleet-core","other"]
qd = {"release_surface": {"type": "noul", "instructions": "Does `diff` change any plugin release surface: a plugin.json version, marketplace.json, or a CHANGELOG.md?"},
      "plugin": {"type": "choice", "instructions": "Which plugin does `diff` primarily change?", "criteria": {p: None for p in plugins}},
      "risk": {"type": "score", "instructions": "How risky is merging `diff`?", "criteria": ["Docs or tests only", "Small behavior change, well tested", "Core logic change with partial tests", "Core logic change, untested or concurrency-sensitive"]}}
for size in (10_000, 40_000, len(diff)):
    try:
        out = ask({"diff": diff[:size]}, qd); a = out["answers"]
        print(f"(b) diff {size:>7} chars: {out['_ms']}ms in={out['usage']['input_tokens']} release_surface={a['release_surface']['noul']:.2f} plugin={a['plugin']['choice']}({a['plugin']['confidence']:.2f}) risk={a['risk']['score']:.2f}")
    except urllib.error.HTTPError as e:
        print(f"(b) diff {size:>7} chars: HTTP {e.code} {e.read()[:200]!r}")

# (c) team-execution optional-reviewer selection (one noul per reviewer)
plan = ("Add a DynamoDB idempotency table for the Stripe webhook Lambda. CDK stack gains the table plus an IAM policy scoped to "
        "PutItem/GetItem. Handler stores the event id with a 24h TTL and skips duplicates. Add pytest unit tests with moto and a "
        "contract test against the OpenAPI spec for the /webhooks/stripe endpoint. Update the runbook.")
reviewers = {"api": "API design, contract correctness, versioning, idempotency, SDK impact",
             "infra": "CDK/CloudFormation, IAM, AWS resources, cost, resilience, observability",
             "privacy": "PII handling, consent, retention, data classification",
             "testing": "test coverage adequacy, mocks/fixtures, edge cases",
             "clarity": "documentation structure, precision, actionability of docs/runbooks",
             "code_quality": "duplication, complexity, naming, abstraction, refactoring",
             "ai_usefulness": "AI-consumability of specs, templates, SKILL.md, acceptance criteria"}
qr = {f"needs_{k}": {"type": "noul", "instructions": f"Should the optional '{k}' reviewer be spawned for `plan`? That reviewer covers: {v}."} for k, v in reviewers.items()}
out = ask({"plan": plan}, qr)
print("(c) reviewer selection:", " ".join(f"{k[6:]}={v['noul']:.2f}" for k, v in out["answers"].items()), f"[{out['_ms']}ms]")

# (d) saga lifecycle routing
cmds = {"office-hours": "very early, vague idea; find the right frame", "ideate": "generate and critique many ideas", "brainstorm": "deep-dive one chosen idea into requirements",
        "spec": "turn a vague ask into a precise WHAT spec", "plan": "create an implementation plan from requirements", "work": "execute an approved plan to PR",
        "investigate": "find the root cause of a bug or failure", "code-review": "review a diff or PR", "qa": "run quality/browser/deploy/acceptance checks",
        "resume": "reconstruct a stale work thread", "retro": "turn finished work into journal knowledge"}
asks = ["the pre-push hook keeps going red only from a split pane, CI is green, figure out why",
        "I have a rough feeling we should make agents cheaper somehow, not sure what that means yet",
        "here's the approved plan in docs/plans/x.md, go build it",
        "we shipped the lease work last week, what did we learn",
        "what would it take to let codex run the verify panels instead of claude"]
for s in asks:
    out = ask({"ask": s}, {"cmd": {"type": "choice", "instructions": "Which saga lifecycle command should handle `ask`?", "criteria": cmds}})
    a = out["answers"]["cmd"]; top = sorted(a["probabilities"].items(), key=lambda kv: -kv[1])[:2]
    print(f"(d) {s[:62]:62} -> {a['choice']:13} conf={a['confidence']:.2f} runner-up={top[1][0]}:{top[1][1]:.2f}")
