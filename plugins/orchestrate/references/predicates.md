# The completion contract

A child is `verified` when a bounded mechanical check passes on a settled, run-bound artifact,
inside its declared boundary, with its recorded destination actually changed — and, for judgment
work, with an independent verifier's depth sample on record. Every one of those clauses is a
refusal point. There is no partial pass.

This document states what each control actually establishes and, just as importantly, what it does
not. Evidence integrity is the category where a false pass is indistinguishable from a true one, so
a control described as stronger than it is causes exactly the failure it was built to prevent.

## The predicate is a typed, closed schema

```json
{
  "argv": ["/path/to/python", "checks/report_complete.py", ".orchestrate/artifacts/r1/c1/report.json"],
  "timeout_seconds": 120.0,
  "max_output_bytes": 262144
}
```

`argv` is a fixed argument vector. It is never a command string and never runs through a shell.
Rejected outright: a declaration that is text rather than an object; an `argv` that is a string; a
program whose name is a shell (`sh`, `bash`, `zsh`, `dash`, `ksh`, `csh`, `tcsh`, `fish`, `cmd`,
`powershell`); any inline-source flag (`-c`, `--command`, `-e`) anywhere in the vector; and any key
outside the three above. The schema is closed because a silently ignored `shell` or `timeout` key is
how an unbounded check reaches production looking bounded.

`timeout_seconds` must be in `(0, 900]` and `max_output_bytes` in `(0, 4 MiB]`. A declaration
outside those bounds is **rejected, not clamped** — a clamped limit reports a bound the author did
not ask for.

The check runs **inline, in the orchestrator's own process tree**, never through the mirror. Every
abnormal end is a failure and never a pass:

| Outcome | Recorded reason |
| --- | --- |
| exit 0 | `verified` (subject to the remaining clauses) |
| non-zero exit | `predicate_failed` |
| still running at the deadline | `predicate_timeout` |
| output past the byte cap | `predicate_output_limit` |
| program missing or unlaunchable | `predicate_error` |

Output is streamed to a temporary file rather than a pipe, so the cap is enforced **while the
process is still running**. A predicate that never exits is killed at the cap rather than buffered
until it exhausts memory.

## Predicate integrity: the closure, not just the entry point

A predicate script outside the child's write scope that *imports a module inside it* is exactly as
compromised as one that lives there, because the child can rewrite what the predicate imports.
Checking the entry-point path alone is not sufficient and is not what this does.

**Static half.** Closure roots are every `argv` element that resolves to a real path inside the
landing — the entry-point script *and* path arguments, because for a runner such as `pytest` the
arguments are the check. Python roots are then followed transitively through their `import` and
`from ... import` statements, including relative imports, resolving each module against the
importing file's directory and the landing root. Any closure member inside the child's write scope
is rejected **before evaluation**.

**Dynamic half.** A SHA-256 digest over the predicate declaration and the contents of every closure
member is captured before dispatch and recomputed before evaluation. A change to any statically
known closure file fails as `predicate_tampered` — even when that file sits *outside* the child's
declared scope, which is the case the static half cannot reach.

**Bounds, stated rather than implied.** The closure is capped at 512 files and 8 MiB; exceeding
either raises rather than truncating, because a silently truncated closure reports a narrower
dependency set than the real one. **Not analyzed:** dynamic imports (`importlib.import_module`,
`__import__`, `exec`), runtime `sys.path` manipulation, data files a predicate reads, the
interpreter and installed third-party packages, and the dependencies of a non-Python entry point
(a shell script is a closure leaf; its own dependencies are not followed). A predicate that reaches
its oracle by any of those routes is outside this control.

The artifact itself is excluded from the closure — it is the check's *subject*, data the check
reads, not code that decides what the check does. A predicate whose program **is** the artifact is
refused outright, and a predicate that statically imports its own subject is still caught, because
that import is discovered from another closure member.

## Settlement: the orchestrator renames, the child never does

**A file on disk does not record whether it arrived by rename or by direct write.** `stat` does not
carry it and content does not carry it. Any check that reads the finished artifact and claims to
know how it got there is claiming something it cannot establish.

So the guarantee is produced rather than inferred:

1. Before dispatch, the orchestrator records the destination's exact state (absent, or its size and
   content digest).
2. The child is instructed to write **only** the in-flight sibling `<artifact>.orchestrate-inflight`
   and never the destination.
3. At completion, the orchestrator requires the destination to be byte-for-byte the state it
   recorded, requires the in-flight path to be a regular file and not a symlink, and then performs
   `os.replace` itself.

Because the in-flight path is a sibling of the destination it is always on the same filesystem, so
this is a rename and never a copy. (A temporary path in `/tmp` renamed onto a repository path may
cross filesystems and would silently degrade to a copy; a sibling cannot.)

**What this establishes:** the predicate only ever reads a path the orchestrator renamed into
place, so it never observes a partially written file; and a child that wrote the destination
directly is rejected with a real observation, not a guess.

**What this does not establish:** how the child produced the in-flight file. A child that writes its
in-flight file slowly, or deletes and recreates it, is fine — nothing reads it until the rename.
The claim is *"the predicate reads only a renamed path"*, which is enforced. The claim
*"the child's own write was atomic"* is neither made nor enforceable.

## Run binding: computed before dispatch, never read from beside the artifact

The expected identity is a flat token generated **before the child runs** and stored in the
register row:

```
ORCHESTRATE-ARTIFACT-BINDING:<run_id>:<row_id>:<nonce>
```

The child must include it verbatim in its deliverable. At completion the artifact must contain that
exact token; if it does not, the failure message names whichever bindings it *does* carry, so a
stale artifact reports as stale rather than as merely unbound.

A receipt written by the child beside its own artifact would fail open — a stale receipt from a
previous run satisfies a comparison against itself. Nothing here is read from the child's output
directory. The token is deliberately flat and escape-free rather than a JSON payload: a token
containing quotes and braces is re-escaped when a child embeds it in a JSON, YAML, or XML
deliverable, and an exact-substring comparison against a correct artifact would then fail.

The binding read is capped at 8 MiB; a larger artifact is refused rather than loaded.

## The boundary check, and where a child may write

Each child's deliverable lands in a directory that is **exclusively its own**, inside its own
landing, at `.orchestrate/artifacts/<run_id>/<row_id>/`. That directory is required to be ignored by
the repository — the check runs at receipt time and fails closed in a repository that does not ignore
the orchestrate state directory, because the whole attribution argument depends on it.

From that follows the write scope, which is *every* place a child may write:

| Child | Repository write allowlist | Exclusive artifact directory |
| --- | --- | --- |
| mutating | its declared scope, in its own worktree | yes |
| read-only | **empty** | yes |

A read-only child's declared scope is a **read** scope. Treating it as a repository write allowlist
was the defect: a read-only child that wrote a report into the shared checkout made every concurrent
sibling fail its boundary check. A read-only child now writes nothing the repository can see, so
concurrent read-only children with disjoint scopes each complete cleanly, and any repository-visible
change during a read-only child's window is a real finding rather than a sibling's ordinary output.

The predicate itself is held to the same standard. It runs inline in the child's landing *after* the
child stopped, so anything it writes there would otherwise be attributed to the child. The landing
is snapshotted immediately before the predicate runs, and any predicate-authored change fails as
`predicate_side_effect` — a failure of the check, never of the child. Well-behaved Python predicates
are additionally kept from writing bytecode into the landing by `PYTHONDONTWRITEBYTECODE` and a
scratch `PYTHONPYCACHEPREFIX`.

**Residual, stated:** the exclusive artifact directory is exclusive by assignment, not by
enforcement. Nothing in the filesystem stops a child from writing into a sibling's artifact
directory, and because that directory is invisible to Git the boundary check cannot see it either.
Detecting deliberate cross-child writes needs a per-child filesystem boundary, which this unit does
not provide.

## Integration before reaping

A verified artifact whose change never landed is discarded when the worktree is reaped, so the
recorded destination is checked before a child can reach `verified` — and `verified` is what the
reap path requires.

- `branch` — the destination branch must exist and its tip must differ from the commit it pointed at
  when the receipt was issued.
- `path` — the destination path's content must differ from its pre-dispatch state.
- `none` — read-only work integrates nowhere. There is nothing to verify, and this is stated in the
  result rather than silently skipped.

## Depth sample for judgment work

Judgment-shaped work cannot reach `verified` on mechanical coverage alone: a review with every
required heading can miss the decisive defect while every visible gate stays green. Work shapes are
classified through fleet-core's authoritative vocabulary, not a locally invented list —
`judgment`, `second-opinion`, and `divergence` are judgment-shaped, and the `adversarial-review`
role-tier alias resolves into that set.

A depth sample records the verifier's identity (row, vendor, model), the digest of the artifact it
read, and one or more sampled claims, each with the claim, the evidence location where it was
checked, and a disposition from the closed set `supported` / `unsupported` / `inconclusive`.

Enforced: the verifier must not be the child itself; the sample must be bound by digest to *this*
dispatch's settled artifact; at least one claim must be sampled; every claim must name its evidence
location; and any `unsupported` claim blocks verification.

**Not enforced:** blindness. That the verifier read the artifact and not the child's own account of
it is a property of how the verifier was dispatched, and no record can prove it. The dispatch
contract owns it: a verifier session receives the settled artifact path and the claims to sample,
and never the child's self-assessment.

## Where a failed child sits in the register

`PHASES` is a closed, operator-approved vocabulary — `planned`, `launching`, `launched`, `ready`,
`working`, `verified`, `reaped` — with no member meaning *evaluated and failed*, and inventing one
is not this unit's call. So:

- **A failed completion does not move `phase` at all.** The child stays where it was, typically
  `working`.
- **The verdict lives in the row's own `completion` key**: result, reason from the closed failure
  vocabulary, a human-readable detail, the artifact digest, and the predicate outcome.
- **`verified` is written only on a full pass**, which is what makes the reap gate real.

The verdict deliberately does **not** live in `observed_state`. That column is owned by the liveness
detectors: the subscriber's snapshot catch-up rewrites it for every row with a live pane, so a
failure recorded only there is erased the next time catch-up runs while the child's pane is still
open. One owner per column. `failed_rows()` is the operator's "what stalled" view, and it is
distinguishable from "still working" without a new phase.

## Evaluation order

1. **Predicate tamper check** — the closure digest, before anything is executed.
2. **Settlement** — destination unchanged, in-flight present, rename.
3. **Run binding** — the artifact carries this dispatch's token.

Those three short-circuit: an unsettled or unbound artifact is not evidence, and there is nothing to
evaluate.

4. **Predicate outcome** and **boundary check**, computed independently. A boundary violation fails
   completion **even when the predicate passed**, and is reported in preference to a predicate
   failure because a breached boundary makes the whole result unattributable.
5. **Integration** to the recorded destination.
6. **Depth sample** for judgment-shaped work.
