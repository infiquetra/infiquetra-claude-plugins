# Lane A journal draft — integrator folds these entries under 2026-09-05

KTD6 assigns the journal files to Lane B. These complete entries are for the
integrator's serial fold; this lane has not edited the living journal.

## 2026-09-05

### A refusal fixture can defend a read bypass without proving that live routing is safe {#912-read-original-test-defended-bypass}

**Context.** Codex, Lane A, revisited Saga's handoff envelope after the six-cycle
fail-open pattern. The old `test_reanchored_missing_fallback_to_original` asserted
that a declaring out-of-root original must be read when its in-root twin is absent.
Its declaration was `pending-confirmation`.
**Evidence.** The old fixture's no-command assertion passes even while the bypass
exists, because `pending-confirmation` cannot route. The Lane A E1 transcript instead
uses an out-of-root `plan-ready` file: both the ordinary absolute source and an
in-root symlink emitted `/issue --prepare` before the fix. Those exact command
assertions fail on the pre-fix module and pass on the repaired one. The complete
transcripts and `cp` / `cmp -s` restoration results are in
`docs/evidence/issue-912/lane-A-evidence.md`.
**Mechanism.** A test that asserts the exceptional read becomes a defense of the
bypass. A second assertion about an already-unroutable value does not exercise the
security consequence, so green results make that defense look stronger than it is.
**Fix.** Refuse every source resolving outside a declared root unless a contained
marker-directory twin exists and supplies a declaration. Retain the unconfirmed
fixture as a refusal pin, and give the live-command leak its own `plan-ready`
fixtures. The repaired suite passes; the in-root twin's no-declaration mutation
returns `requirements-ready` and fails its new pin.
**Generalizable rule.** To prove that a refusal prevents an action, choose an input
that would perform that action if the guard disappeared. Keep consistency and
non-routable-value checks separate from that security proof.
**Refs.** Issue #912/#913; SEC-1, TEST-1, SEC-7, TEST-10; U1 and KTD1/KTD2 in
`docs/plans/2026-09-04-issue-912-repair-lanes.md`; existing learning
`tests-that-pin-fail-opens`; `tests/test_handoff_envelope_maturity.py`.

### Source resolution refuses the original outside the root and shares one decision {#912-refuse-original-outside-root}

**Decision.** A source that resolves outside the declared root is never read. If
its path carries a marker directory (`docs/brainstorms/` and the like) and the same
subpath exists inside the root, that in-root file is read instead and its
declaration decides. Otherwise the source is refused with `unknown:out-of-root:`,
whatever it declares, whether or not it exists, and however its path is spelled.
A twin that declares nothing is also refused; its path rule cannot authorize the
original. Containment uses resolved paths, including symlink targets.
**Date.** 2026-09-05; author: Codex, Lane A; approved by the issue #912 repair plan,
KTD1/KTD3/KTD9. This reverses the read-original choice in
`913-maturity-unknown-sentinel`; Lane B owns the in-place correction.
**Why.** Refusal now returns a diagnostic sentinel rather than a live path fallback,
so the earlier rationale against refusal no longer holds. `ResolvedSource` shares
the path and publication decision between inference and envelope construction.
The spy test and its divergent inline mutation prove that callers use that decision.
**Rejected.** Keeping the original-file read would allow a prepared issue to cite
an artifact absent from its declared checkout. Applying the path rule to an
undeclaring twin would reopen a different live route. Duplicating the re-anchor
decision would let attribution and classification diverge again.
**Revisit when.** The operator explicitly authorizes cross-root prepared-issue
sources or changes the consumer contract. `infer_maturity(..., root=None)` retains
the caller-named-file behavior; envelope construction always supplies a root.
**Refs.** Issue #912/#913; SEC-1, AM-3, AM-4, TEST-1, TEST-2;
`docs/evidence/issue-912/lane-A-evidence.md`; KTD9 cross-checked against
`resolve_source` and the twin-without-declaration refusal in `_resolved_maturity`.
