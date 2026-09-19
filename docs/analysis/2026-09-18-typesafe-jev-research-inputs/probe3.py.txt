import json
from jev import ask
policy = open("/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/plugins/mission-control/skills/issues/references/issue-types.md").read()
TYPES = ["capability", "enhancement", "defect", "exploration", "context-update"]
issues = json.load(open("issues.json"))
def pick(i): 
    h = [l["name"] for l in i["labels"] if l["name"] in TYPES]; return h[0] if len(h) == 1 else None
rows = [i for i in issues if pick(i)][:30]
ok = 0; conf = []; ms = 0; toks = 0; misses = []
for i in rows:
    out = ask({"issue": {"title": i["title"], "body": (i["body"] or "")[:2500]}, "policy": policy},
              {"type": {"type": "choice",
                        "instructions": "Apply `policy` (the Infiquetra SDLC issue-type reference, including its decision tree and when-not-to-use rules) to classify `issue` into exactly one issue type.",
                        "criteria": {t: f"Issue type '{t}' as defined in `policy`" for t in TYPES}}})
    a = out["answers"]["type"]; ms += out["_ms"]; toks += out["usage"]["input_tokens"]
    hit = a["choice"] == pick(i); ok += hit; conf.append((a["confidence"], hit))
    if not hit: misses.append(f"#{i['number']} label={pick(i)} jev={a['choice']}({a['confidence']:.2f}) :: {i['title'][:60]}")
hi = [h for c, h in conf if c >= 0.6]; lo = [h for c, h in conf if c < 0.6]
print(f"WITH POLICY: type agreement {ok}/{len(rows)}; mean {ms//len(rows)}ms; mean input tokens {toks//len(rows)}; acc conf>=0.6: {sum(hi)}/{len(hi)}; conf<0.6: {sum(lo)}/{len(lo)}")
print("\n".join(misses))
