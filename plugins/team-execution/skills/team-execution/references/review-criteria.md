# Review Criteria — team-execution

Team Execution does not define review dimensions, score anchors, arithmetic, acceptance rules, or
iteration policy. Those values live only in Saga's canonical roster:

`plugins/saga/references/lens-roster.json`

In an installed-plugin run, resolve Saga with `dispatch_settlement_adapter.py preflight` and read
`references/lens-roster.json` below the returned root. Require the declared roster schema and refuse
missing or unknown policy instead of using a local default.

For each selected lens:

1. Read its `dimensions` and their `anchors` from the roster.
2. Give the mapped Team Execution agent the lens identifier and those canonical dimensions.
3. Require a score for every applicable dimension and a recorded cause for every non-applicable
   dimension.
4. Treat the agent's reported overall and findings as evidence, not an acceptance decision.
5. Submit that evidence to Saga's `score_lens_review` function in
   `plugins/saga/scripts/review_consensus.py`.

Priority and confidence stay attached to findings for repair routing. They do not change numeric
acceptance. Scanner, test, deployment, casualty, and operational-safety gates remain separate and
authoritative.

Do not copy roster values into this file or an agent prompt. A policy change is made once in the
roster and exercised through the shared scorer.
