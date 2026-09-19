import json
from jev import ask, compact

TIER_RULE = ("Tiering rule: judgment, design, architecture, root-cause investigation, or adversarial review -> opus. "
             "Mechanical or deterministic work (scaffolding, fixed transforms, mechanical edits, running commands) -> haiku. "
             "Read-only survey, search, sampling, summarising -> sonnet.")
tasks = [
 ("rename var across 12 files, tests must pass",            "haiku",  "low"),
 ("design retry/idempotency for payment webhook + write ADR", "opus",   "high"),
 ("list every file:line that reads TYPESAFE_API_KEY",        "sonnet", "low"),
 ("adversarial review of PR for concurrency defects in lease handling", "opus", "high"),
 ("scaffold a new plugin dir from the template named unifi-two", "haiku", "low"),
 ("convert 40 unittest cases to pytest style, no behavior change", "haiku", "low"),
 ("investigate flaky test failing 1 in 20 runs (race in worker pool)", "opus", "high"),
 ("summarise last 50 commits into a CHANGELOG entry",         "sonnet", "medium"),
 ("decide whether to split the saga plugin into three; weigh tradeoffs", "opus", "max"),
 ("run the test suite and report failing test names",        "haiku",  "low"),
]
questions = {
  "model": {"type": "choice",
            "instructions": {"question": "Which model tier should run `task`?", "policy": TIER_RULE},
            "criteria": {"haiku": "cheapest; mechanical/deterministic work",
                         "sonnet": "mid; survey, search, summarising, moderate coding",
                         "opus": "most capable; judgment, design, adversarial review, root cause"}},
  "effort": {"type": "choice",
             "instructions": "How much reasoning effort does `task` need?",
             "criteria": {"low": "obvious steps, little ambiguity", "medium": "some judgment",
                          "high": "substantial ambiguity or many interacting constraints",
                          "max": "consequential architectural or strategic decision"}},
  "needs_review": {"type": "noul", "instructions": "Does `task` require adversarial or design judgment rather than mechanical execution?"},
}
agree_m = agree_e = 0; total_ms = 0
for task, exp_m, exp_e in tasks:
    out = ask({"task": task}, questions); a = out["answers"]; total_ms += out["_ms"]
    m, e = a["model"]["choice"], a["effort"]["choice"]
    agree_m += m == exp_m; agree_e += e == exp_e
    flag = "" if m == exp_m else f"  <-- expected {exp_m}"
    print(f"{task[:58]:58} model={m:6} ({a['model']['confidence']:.2f}) effort={e:6} review={a['needs_review']['noul']:.2f}{flag}")
print(f"\nmodel agreement {agree_m}/10, effort agreement {agree_e}/10, mean latency {total_ms//10}ms, model={out['model']}")
