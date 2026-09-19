"""Tiny TypeSafe client: python3 jev.py <request.json>  -> compact answers + timing."""
import json, os, sys, time, urllib.request

def ask(state, questions, model="jev-latest"):
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
    req = urllib.request.Request(
        "https://api.typesafe.ai/v1/systemone", data=body, method="POST",
        headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}",
                 "Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read())
    out["_ms"] = round((time.perf_counter() - t0) * 1000)
    return out

def compact(ans):
    t = ans["type"]
    if t == "noul":
        return f"noul={ans['noul']:.2f}"
    if t == "choice":
        top = sorted(ans["probabilities"].items(), key=lambda kv: -kv[1])[:3]
        return f"{ans['choice']} conf={ans['confidence']:.2f} " + " ".join(f"{k}:{v:.2f}" for k, v in top)
    if t == "score":
        return f"score={ans['score']:.2f} conf={ans['confidence']:.2f}"
    return json.dumps(ans)

if __name__ == "__main__":
    req = json.load(open(sys.argv[1]))
    out = ask(req["state"], req["questions"], req.get("model", "jev-latest"))
    for k, v in out["answers"].items():
        print(f"{k}: {compact(v)}")
    print(f"[{out['model']} {out['_ms']}ms in={out['usage']['input_tokens']} out={out['usage']['output_tokens']}]")
