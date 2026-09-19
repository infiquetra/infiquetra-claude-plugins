import json
from jev import ask
ideas = json.load(open("ideas.json"))
POLICY = ("Jev is a System One model: fast typed judgments over text, calibrated probabilities, ~0.35s, $0.042 per million input tokens. "
          "Good fit: classification, routing, ranking, yes/no checks over a few thousand tokens of text with clear criteria. "
          "Poor fit: arithmetic, counting, date comparison, adversarial or injected content, decisions that need live external state, "
          "free-text generation, decisions where a wrong automatic action is costly and there is no human confirmation step.")
def batch(chunk):
    state = {"policy": POLICY, "ideas": [{"i": n, "area": x["area"], "text": x["text"]} for n, x in enumerate(chunk)]}
    qs = {}
    for n in range(len(chunk)):
        p = f"`ideas[{n}].text` (area: `ideas[{n}].area`)"
        qs[f"value_{n}"] = {"type": "score", "instructions": f"How much operator time or model cost would {p} save, or how many errors would it prevent, if it worked?",
                            "criteria": ["Negligible", "Small: minutes per week", "Moderate: hours per week or a recurring error class", "Large: a daily bottleneck or an expensive model call replaced"]}
        qs[f"effort_{n}"] = {"type": "score", "instructions": f"How much engineering effort does {p} need, including tests and release surfaces?",
                             "criteria": ["Trivial: under a day", "Small: a few days", "Medium: a week or two", "Large: multi-week or cross-repo"]}
        qs[f"risk_{n}"] = {"type": "score", "instructions": f"If the typed judgment in {p} is wrong, how bad is the consequence given the described safeguards?",
                           "criteria": ["Harmless: advisory, easily ignored", "Minor: a wrong label or suggestion someone corrects", "Serious: a skipped gate, wrong routing, or wasted expensive run", "Severe: unsafe action, data loss, or governance failure"]}
        qs[f"fit_{n}"] = {"type": "noul", "instructions": f"Per `policy`, is {p} a good fit for Jev's strengths and clear of its documented weaknesses?"}
    return ask(state, qs)
rows = []; ms = 0; toks = 0
for start in range(0, len(ideas), 8):
    chunk = ideas[start:start+8]; out = batch(chunk); ms += out["_ms"]; toks += out["usage"]["input_tokens"]
    for n, x in enumerate(chunk):
        a = out["answers"]
        v, e, r, f = a[f"value_{n}"]["score"], a[f"effort_{n}"]["score"], a[f"risk_{n}"]["score"], a[f"fit_{n}"]["noul"]
        composite = v * f - 0.5 * e - 0.6 * r          # code-owned weights; re-weight without re-inference
        rows.append((composite, x["id"], x["area"], v, e, r, f))
rows.sort(reverse=True)
lines = ["| Rank | Idea | Area | Value 0-3 | Effort 0-3 | Risk 0-3 | Fit p(yes) | Composite |", "|---|---|---|---|---|---|---|---|"]
for k, (c, i, ar, v, e, r, f) in enumerate(rows, 1):
    lines.append(f"| {k} | `{i}` | {ar} | {v:.2f} | {e:.2f} | {r:.2f} | {f:.2f} | {c:.2f} |")
lines.append(f"\nComposite = value × fit − 0.5 × effort − 0.6 × risk (weights are code-owned; changing them needs no re-inference). "
             f"{len(ideas)} ideas × 4 questions in {(len(ideas)+7)//8} requests, {ms} ms total, {toks} input tokens (≈ ${toks*0.042/1e6:.4f}).")
open("jev_ranking.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
