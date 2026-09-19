"""Jev second-opinion triage of the open improve-claude-plugins cards under the simplification direction."""
import json, sys, time
sys.path.insert(0, "docs/analysis/2026-09-18-typesafe-jev-research-inputs")
from jev import ask

DIRECTION = (
    "The operator is simplifying the saga plugin family for Claude Code. Decisions already made: "
    "(1) keep the lifecycle concepts and slash commands (plan, plan review, work, code review, QA, handoff, retro) "
    "but have them kick in automatically as guidance for the model rather than as gates, refusals, and protections; "
    "(2) code review gets clear, mechanical mechanisms, with the review lenses specified up front from the shape of the change; "
    "(3) implement, deploy, and test run as a loop until working software exists, and only then does code review run; "
    "(4) the team-execution plugin's structure (spawning Claude team agents, ordering, gating, result aggregation) is removed, "
    "while its roles (reviewers, scanners, testers, validators, monitors) survive as prompts for separate herdr terminal sessions; "
    "(5) race-condition, lease, launch-reservation, and double-dispatch protections are replaced by one git worktree per unit of work, "
    "one branch per worktree, and ordinary git merge."
)

QUESTIONS = [
    {"id": "bucket", "type": "choice",
     "instructions": "Read `direction` (the operator's simplification decisions) and `issue` (an open GitHub issue against the plugins). Decide how the issue should be handled once the simplification is carried out.",
     "criteria": {
        "KEEP": "The defect or need stays valid and its prescribed fix still applies unchanged under the simplified design.",
        "REWRITE": "The underlying concern stays valid, but the prescribed fix targets machinery the simplification changes, so the issue must be rewritten against the simplified design.",
        "SUPERSEDE": "The issue only fixes or extends machinery the simplification removes (lease, race, launch-reservation, double-dispatch protection, or team-execution structure), so it should be closed as superseded.",
        "UNRELATED": "The issue does not concern the lifecycle plugins or the direction at all."}},
    {"id": "race", "type": "noul",
     "instructions": "Is the issue in `issue` primarily about protecting against races, double launches, stale run state, leases, or collisions between concurrent sessions?"},
    {"id": "review", "type": "noul",
     "instructions": "Is the issue in `issue` primarily about code review or document review mechanics: lenses, verdicts, evidence ledgers, review result schemas, repair cycles, or publication of review results?"},
    {"id": "survives", "type": "noul",
     "instructions": "Would the problem described in `issue` still exist if each role ran in its own herdr terminal session with its own git worktree and branch, merged by ordinary git merge, with no team-execution or lease machinery?"},
]

QUESTIONS = {q.pop("id"): q for q in QUESTIONS}
issues = [i for i in json.load(open(sys.argv[1])) if i["state"] == "OPEN"]
rows, total_in, total_ms = [], 0, 0
for i in sorted(issues, key=lambda x: x["number"]):
    body = i["body"] or ""
    truncated = len(body) > 16000
    state = {"direction": DIRECTION,
             "issue": {"number": i["number"], "title": i["title"], "labels": i["labels"], "body": body[:16000]}}
    for attempt in range(3):
        try:
            out = ask(state, QUESTIONS); break
        except Exception as e:  # noqa: BLE001
            if attempt == 2: raise
            time.sleep(2)
    a = out["answers"]
    rows.append({"number": i["number"], "title": i["title"], "labels": i["labels"], "truncated": truncated,
                 "bucket": a["bucket"]["choice"], "bucket_conf": round(a["bucket"]["confidence"], 2),
                 "bucket_probs": {k: round(v, 2) for k, v in a["bucket"]["probabilities"].items()},
                 "race": round(a["race"]["noul"], 2), "review": round(a["review"]["noul"], 2),
                 "survives": round(a["survives"]["noul"], 2), "ms": out["_ms"], "input_tokens": out["usage"]["input_tokens"]})
    total_in += out["usage"]["input_tokens"]; total_ms += out["_ms"]
    print(f"{i['number']:5d} {a['bucket']['choice']:9s} conf={a['bucket']['confidence']:.2f} race={a['race']['noul']:.2f} review={a['review']['noul']:.2f} survives={a['survives']['noul']:.2f} {out['_ms']}ms", flush=True)

json.dump({"model": out["model"], "direction": DIRECTION, "questions": QUESTIONS, "rows": rows,
           "total_input_tokens": total_in, "total_ms": total_ms}, open(sys.argv[2], "w"), indent=1)
with open(sys.argv[3], "w") as f:
    f.write("# Jev second-opinion triage of open improve-claude-plugins cards\n\n")
    f.write(f"Model `{out['model']}`, {len(rows)} cards, one request per card with four questions, "
            f"{total_in:,} input tokens, {total_ms/len(rows):.0f} ms mean latency. Advisory only; the main thread's own classification governs.\n\n")
    f.write("| Issue | Bucket | Conf | P(race) | P(review) | P(survives herdr+worktree) | Title |\n|---|---|---|---|---|---|---|\n")
    for r in rows:
        f.write(f"| {r['number']} | {r['bucket']} | {r['bucket_conf']:.2f} | {r['race']:.2f} | {r['review']:.2f} | {r['survives']:.2f} | {r['title'][:80].replace('|','/')}{' (body truncated)' if r['truncated'] else ''} |\n")
    from collections import Counter
    c = Counter(r["bucket"] for r in rows)
    f.write("\n## Bucket counts\n\n" + "\n".join(f"- {k}: {v}" for k, v in c.most_common()) + "\n")
print(f"TOTAL cards={len(rows)} input_tokens={total_in} mean_ms={total_ms/len(rows):.0f}")
