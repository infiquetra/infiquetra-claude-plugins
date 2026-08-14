# The completion contract

A child is `verified` when a bounded mechanical check passes on a settled, run-bound artifact,
inside its declared boundary, with its recorded destination actually changed — and, for judgment
work, with a claimed independent verifier's depth sample on record. Every one of those clauses is a
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

**Parent package initializers are closure members.** For `import pkg.oracle`, Python executes
`pkg/__init__.py` *before* `pkg/oracle.py`. A closure holding only the leaf would let a child whose
scope is exactly `pkg/__init__.py` change what `pkg.oracle` resolves to — in scope, with the closure
digest unchanged. Every initializer along the dotted path is followed, for every root.

**Bounds, stated rather than implied.** The closure is capped at 512 files and 8 MiB; exceeding
either raises rather than truncating, because a silently truncated closure reports a narrower
dependency set than the real one.

### What the closure does and does not follow, member by member

A prose claim of completeness over an incomplete walk is worse than an honest exclusion list,
because the exclusion list can be read and worked around while the claim cannot. This is the whole
class of ways Python code reaches other code, and where each one stands:

| Route to other code | Followed? |
| --- | --- |
| `import a.b.c` / `from a.b import c`, absolute | yes, including every parent `__init__.py` |
| relative imports (`from . import x`, `from ..pkg import y`) | yes, resolved against the importing file's package |
| imports inside `try`, `if`, or `if TYPE_CHECKING` blocks | yes — the parser sees them regardless of whether they run |
| transitive imports, any depth | yes |
| PEP 420 namespace packages (no `__init__.py`) | yes — there is simply no initializer to add |
| in-tree native extensions (`.so`, `.pyd`) | the file enters the closure and is digested; its own imports cannot be followed |
| path arguments to a runner (`pytest tests/`) | yes — for a runner, the arguments *are* the check |
| `importlib.import_module`, `__import__`, `exec`, `eval` | **no** |
| `sys.path` insertion, then an import of what it exposes | **no** |
| `PYTHONPATH` and `.pth` files injecting import roots | **no** |
| modules resolved from an installed distribution (`.venv`, site-packages) | **no** — they are outside the landing, so they are not closure members at all |
| the interpreter binary itself | **no** |
| data files a predicate reads (JSON, YAML, fixtures) | **no** — they are data, not code that decides what the check does |
| a symlinked closure member whose target is outside the landing | **no** — the target resolves outside and is dropped |
| the dependencies of a non-Python entry point (shell script, compiled binary) | **no** — the entry point is a closure leaf |

A predicate that reaches its oracle by any route in the lower half is outside this control. The
right response is to declare a predicate that does not, not to assume the digest covers it.

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

### Settlement is recorded, so it can be replayed

The rename is one-shot. After it, the in-flight file is gone and the destination is present — which
is byte-for-byte the state a child that wrote the destination directly would have left. Nothing on
disk tells those apart.

That matters because evaluation is not a once-only event. The catch-up contract re-evaluates
run-bound artifacts and predicates on every startup and reconnect, and judgment work needs a second
evaluation by construction (below). Without a record, the second evaluation of a perfectly correct
child fails `artifact_unsettled`.

So settlement writes a durable, authenticated record — nonce, destination, digest, timestamp — and a
later evaluation of the same dispatch replays it instead of renaming again. The replay is
conditional: if the destination no longer holds the digest that was settled, this is not a replay,
the evidence on disk is not the evidence that was settled, and it fails. A new dispatch to the same
row issues a new nonce, so the previous attempt's record cannot satisfy it.

## The register is not a trusted store

Everything durable this unit writes — the dispatch receipt and the settlement record — lives in
`.orchestrate/register.json`. Three facts about that file, together, are the problem:

1. Every child can write files in its landing. There is no launch flag that permits the artifact
   write and forbids everything else (see *The launch posture* below).
2. The register is inside every child's landing. A read-only child's landing *is* the ambient
   checkout.
3. `.orchestrate/` is Git-ignored, and Git-ignored means invisible to the boundary check. A child
   that rewrites the register is observed by nothing.

Two working forgeries followed from that, both reaching `verified`: replace the stored binding token
with one from a previous run and produce an artifact carrying it; or replace the stored predicate
with `/usr/bin/true` and recompute the closure digest so the tamper check agrees.

Inspection cannot close this, because a forged record and a genuine one are the same bytes in the
same place. **Authentication can.** Each durable record carries an HMAC-SHA-256 digest over exactly
the fields it stores, keyed by a per-run orchestrator secret. A record that does not authenticate
establishes nothing and is refused; an added key is a mismatch rather than a silently ignored field.

The secret lives **outside the repository** — `~/.orchestrate/run-secrets/<run_id>.key`, mode `0600`,
relocatable with `ORCHESTRATE_RUN_SECRET_DIR`. A secret directory inside the repository is refused
outright, because every child's landing is inside the repository. "Outside the workspace" is the one
boundary the supported CLIs genuinely express, which is what the separation rests on.

**Stated rather than assumed:** for Claude and Muse the CLI exposes no write-posture flag at all, so
for those runtimes the separation rests on the child never being pointed at the secret rather than
on a sandbox refusing it. And a child can always *destroy* a record rather than forge one — after
which nothing verifies, which is the correct failure, not a false pass.

## The launch posture

Every child is launched with its runtime's ordinary workspace-write posture, mutating or not:
`--sandbox workspace-write` (Codex), `--sandbox workspace` (Grok), `--sandbox` (Qwen, Agy), and no
flag for Claude (which has no cwd-write boundary flag) or Muse (whose sandbox is already on).

Read-only children are **not** launched under a no-write flag, and this is deliberate. Every child
is dispatched with an artifact it must write, and no supported CLI accepts a repository-relative
path allowlist — so a read-only flag never contained a read-only child, it only made its dispatch
impossible to satisfy.

**What the posture contains is writes *outside* the workspace, and that is the only containment
here.** Inside the workspace nothing is contained. The boundary check is *post-hoc, partial,
repository-visible change detection*: it runs after the child has stopped, it reports rather than
prevents, it sees only tracked and non-ignored paths, and in a shared checkout it cannot establish
which actor made a change. A read-only child's empty repository write allowlist means any
repository-visible change during its window fails **its completion** — a refusal to verify, not a
write that did not happen. A child that writes a Git-ignored workspace path outside its own artifact
directory produces no violation at all, and the register's records are authenticated precisely
because of that.

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
landing, at `.orchestrate/artifacts/<run_id>/<row_id>/`. That directory is required to be *invisible
to the boundary* — the check runs at receipt time and fails closed, because the whole attribution
argument depends on it.

"Invisible to the boundary" is a stronger question than "matched by an ignore rule", and it is asked
as the stronger one. A **tracked** path stays visible to `git status` and to the committed-diff
comparison whatever `.gitignore` says. An operator who archives an artifact with `git add -f` would
otherwise leave a tracked file under an ignored directory, and every later settle of that path would
be reported as a repository change — the control firing on the orchestrator's own rename rather than
on a child. Refusing at receipt time turns that into one actionable message before dispatch, and the
message says how to clear it (`git rm -r --cached`).

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
child stopped, so anything it writes there would otherwise be attributed to the child. Three
surfaces are snapshotted immediately before the predicate runs and compared after it:

- the child's landing, by Git status and committed diff;
- the ambient checkout, separately, because a mutating child's predicate runs in its worktree;
- **the artifact directory**, by content digest, file by file.

The third is not redundant. That directory is *required* to be invisible to Git, so the Git snapshot
cannot see it — and an observer added for "the observer must not disturb the evidence" that cannot
see the evidence is not observing the evidence. A predicate that rewrote the settled artifact after
its binding digest was taken previously returned a clean pass, with a recorded digest that no longer
matched the bytes on disk. It now fails `predicate_side_effect`. The whole directory rather than the
one artifact, because a predicate that rewrites the in-flight sibling of the *next* dispatch is the
same defect wearing a different filename.

### "The predicate has finished" includes everything it started

Two snapshots only bracket the interval between them. Waiting for the predicate's direct process
establishes that *that* process finished — a descendant it spawned outlives it, is reparented away,
and can write the artifact after the second snapshot has already certified it. That produced a
recorded pass whose durable digest did not match the file on disk, with no control observing it.

So the predicate is started as its own process group (`start_new_session=True`, making it a group
leader whose group id is its own pid) and **everything still in that group is SIGKILLed and waited
out on every exit path, success included, before `run_predicate` returns.** Ordering is the whole
point: the kill happens before the caller takes the after-snapshot, so anything a group member
wrote is inside the observed interval. A group that does not drain within five seconds is
`predicate_descendants` — a refusal, because an observation taken while something the predicate
started is still running cannot be trusted.

**Group membership is the whole of the claim, and it is narrower than "nothing can still write".**
A descendant that leaves the group — its own `setsid`, or anything built on it — is not reached by
the kill, and can rewrite the settled artifact after evaluation has recorded a pass and a digest.
That is a real, constructed case, not a theoretical one. The table below is the enumeration:

| Actor | Covered? |
| --- | --- |
| the predicate's direct process | yes — waited for |
| any descendant it started, at any depth | yes — killed with the group before the snapshot |
| a descendant already inside a kernel write when SIGKILL lands | **no** — the write completes; the window is microseconds and cannot be closed from user space |
| a process the predicate started that escaped the group (`setsid` of its own) | **no** — nothing in POSIX prevents a process leaving its group |
| the child session itself, if it never actually stopped | **no** — U5 does not verify that the child exited; readiness and stop are U4's |
| a sibling child writing into this child's artifact directory | **no** — the exclusive directory is exclusive by assignment, not enforcement |
| the operator, or anything else on the host | **no** — outside every control here |
| a concurrent re-dispatch of the same row | **no** — register locking is U2's; the nonce makes the *stale* case fail, not the concurrent one |

Well-behaved Python predicates are additionally kept from writing bytecode into the landing by
`PYTHONDONTWRITEBYTECODE` and a scratch `PYTHONPYCACHEPREFIX`.

**Residuals, stated:**

- The exclusive artifact directory is exclusive by assignment, not by enforcement. Nothing in the
  filesystem stops a child from writing into a sibling's artifact directory, and because that
  directory is invisible to Git the boundary check cannot see it either. Detecting deliberate
  cross-child writes needs a per-child filesystem boundary, which this unit does not provide.
- Git-ignored paths *outside* the artifact directory — `.orchestrate/register.json` above all — are
  not covered by the side-effect observation. A predicate that rewrites the register is caught by
  the register's records being authenticated, which is a different control with a different
  mechanism, not by this one.

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

**The verifier must be a dispatch this orchestrator issued.** A `verifier_row_id` that is merely a
non-empty string different from the child's is not a session — `"verifier-that-does-not-exist"`
satisfies that test. But neither is a *register row*: the register is the store the dispatch receipt
is sealed against precisely because every child can write it, so a check that reads only register
columns certifies exactly what the rest of this document distrusts. A write-capable child can plant
a row with the right run, the right phase, and any vendor and model it likes — and because the
sample is now persisted, that forgery leaves a durable audit trail of a session that never ran.

So the load-bearing requirement is an **authenticated dispatch receipt for the verifier row**, under
this run's orchestrator secret, which a child cannot produce. On top of that: the receipt's run must
be this child's run; the sample's vendor must match the vendor in that sealed receipt; the row must
not be recorded as still waiting to start; and the sample's model must match the row's recorded
model.

**This places a contract on whoever dispatches verifiers (U8): a verifier is an ordinary dispatched
child and must be issued a receipt like any other.** A verifier without one cannot be told apart
from a planted row.

**What this check establishes, exactly: a verifier was dispatched in this repository, for this run,
with this vendor.** It does not establish that the verifier ran. Two of the four things checked come
from the sealed receipt; the other two are register columns that any write-capable actor can set:

| Checked | Source | Survives an adversary? |
| --- | --- | --- |
| the dispatch exists, its run, and the repository it was issued in | sealed receipt | yes |
| the verifier's vendor | sealed receipt | yes |
| `phase` is one of the phases past launch | register column | **no** — moving it from `planned` to `working` presents a receipt-bearing verifier that never read anything |
| `model` matches the sample | register column | **no** — the model is resolved at launch and is not on the receipt |

The repository half is not incidental. The verifier's receipt is the one this module fetches by row
id instead of receiving as an argument, and the run secret is shared by run id across repositories,
so without it a genuine verifier dispatch copied out of another checkout of the same run
authenticates here and satisfies the gate. `read_receipt` enforces it.

The `phase` check is still worth having: it refuses the *honest* never-started case, which is what a
verifier dispatch that failed to launch actually looks like. It is not a proof of execution, and
nothing here should be read as one.

It asks for **membership** in the phases past launch — `launched`, `ready`, `working`, `verified`,
`reaped` — rather than refusing `planned` and `launching` by name. A refusal written as exclusions
accepts everything nobody thought of: the empty string and a value that is not a phase at all both
mean no dispatch was observed to start, and both read as started under a name-based refusal. The
supported write path validates the phase, so those values arrive only by writing `register.json`
directly — which is the access a child actually has, and the premise the receipt is sealed against.
This does not make the column trustworthy. It makes the check refuse the class it says it refuses.

Sealing `phase` is out of this unit's reach. The only evidence that separates "dispatched" from
"ran" is observed *after* launch, and both observers live elsewhere — the launch transition is U4's
and the liveness stream is U3's subscriber. Closing it means one of those units writing an
attestation under the run secret, not a change here.

**This residual and the accepted one on the child's own row — a child writing `phase=verified` into
its own row and being reaped with no completion record — are the same defect against two different
columns of the same untrusted store**, and a single authenticated-register change would close both.

**A sample that established nothing does not certify anything.** Any `unsupported` claim blocks
verification (`depth_sample_unsupported`), and so does a sample with no `supported` claim at all
(`depth_sample_inconclusive`). Treating the absence of a refutation as a confirmation is how an
independent read becomes a formality, and downstream it is indistinguishable from a real one.

Also enforced: the verifier must not be the child itself; the sample must be bound by digest to
*this* dispatch's settled artifact; at least one claim must be sampled; and every claim must name its
evidence location. Malformed external data is converted into a recorded `depth_sample_invalid`
verdict, never raised — a control that raises instead of recording leaves the register showing a
working child with no verdict, which is a fail-open one level up. Claim entries are validated, not
filtered: silently skipping a malformed entry would turn "one supported claim plus garbage" into a
clean one-claim sample.

**The sample is persisted.** The verifier's identity, every sampled claim, its evidence location and
its disposition are written into the row's `completion.depth_sample`. Without that, a child that was
genuinely sampled and one whose sample certified nothing are the same green row, and the pass
becomes its own evidence — the exact failure this unit exists to prevent.

What is on record there is a *claim*: the verifier's own report, with an authenticated dispatch
standing behind who was asked to produce it. A later unit reading `completion.depth_sample` should
read it as that and not as a proven independent read, which is why the type itself is named for the
smaller thing.

### The sequence for judgment work

The verifier reads the **settled** artifact, and settlement happens inside evaluation, so judgment
work takes two evaluations:

1. `evaluate_completion` with no sample. The mechanical controls run and the artifact settles; the
   result is `depth_sample_missing` and the row does not reach `verified`. The settled path and its
   digest are on the row.
2. An independent verifier session is dispatched against that settled path.
3. `evaluate_completion` again, with the sample. Settlement replays from its record rather than being
   re-attempted, and the mechanical controls are **re-run** rather than taken from the first call, so
   the second verdict is a fresh answer and not a cached one.

**Not enforced:** blindness. That the verifier read the artifact and not the child's own account of
it is a property of how the verifier was dispatched, and no record can prove it. Neither is vendor
diversity — nothing here requires the verifier's vendor to differ from the child's. Both are dispatch
contract obligations: a verifier session receives the settled artifact path and the claims to sample,
and never the child's self-assessment.

## Where a failed child sits in the register

`PHASES` is a closed, operator-approved vocabulary — `planned`, `launching`, `launched`, `ready`,
`working`, `verified`, `reaped` — with no member meaning *evaluated and failed*, and inventing one
is not this unit's call. So:

- **The invariant is: a row's phase is `verified` if and only if its latest completion verdict is a
  pass.** Both halves matter. A first evaluation that fails leaves the phase untouched — typically
  `working`. A **re**-evaluation that fails *demotes* the row from `verified` back to `working`,
  because the reap gate reads the phase: a row left at `verified` with `completion.result=failed`
  would be consumed downstream as a pass. A `reaped` row is past this question and is left alone
  **whichever way the verdict goes** — the earlier shape only left it alone on a failure, and a
  passing re-evaluation wrote `verified` straight over the terminal phase. That needed no forgery:
  catch-up re-evaluates run-bound artifacts on startup, a reaped child still has a settlement record
  and a file on disk, and settlement replays cleanly, so a closed tab came back as a live `verified`
  child and the next vanish check raised on its missing tab.
- **The verdict lives in the row's own `completion` key**: result, reason from the closed failure
  vocabulary, a human-readable detail, the artifact digest, the settled artifact path, the predicate
  outcome, and — for judgment work — the depth sample.
- **`verified` is written only on a full pass**, which is what makes the reap gate real.

Demotion does not invent a phase. *Evaluated and failed* is already representable as
`phase="working"` plus a recorded failure, which is exactly what `is_working_not_failed()` and
`failed_rows()` read.

The verdict deliberately does **not** live in `observed_state`. That column is owned by the liveness
detectors: the subscriber's snapshot catch-up rewrites it for every row with a live pane, so a
failure recorded only there is erased the next time catch-up runs while the child's pane is still
open. One owner per column. `failed_rows()` is the operator's "what stalled" view, and it is
distinguishable from "still working" without a new phase.

## Evaluation order

0. **Identity — every input the verdict depends on, not just the labels.** The child specification,
   the landing, the changed-path baseline and the receipt arrive as four independent arguments, and
   a landing that sits inside the receipt's repository has its outcome recorded under the
   *specification's* row in that register. A landing that does not raises rather than records.
   Nothing further down would notice if they described different dispatches. The bound set is the
   mechanical answer to "what does the evaluator read before deciding?", and taking that answer
   needs two passes in this order: **enumerate the signature, then the attribute reads.** Collecting
   `spec.`/`landing.` reads finds everything hanging off an object and is structurally blind to a
   plain parameter — which is how the repository root, then the first argument, stayed off this list
   while the list was being called complete.

   The root is no longer on the list because it is no longer an argument, and that is the more
   durable answer of the two. The enumeration has to be redone correctly every time the signature
   changes; the deletion holds on its own.

   **Deciding inputs** — something downstream branches on them, so substituting one changes the
   verdict:

   | Input | What it decides | How it is bound |
   | --- | --- | --- |
   | repository root | which register receives the settlement record, the verdict and the phase | **derived, not supplied** — see below |
   | `run_id`, `row_id` | which row the verdict lands on; the artifact landing; the token | sealed label |
   | landing path | where the predicate runs, what the boundary observes | sealed label |
   | `work_shape` | **whether the depth gate runs at all** | sealed label |
   | `mutating`, `scope` | what the boundary check permits | sealed labels |
   | `base_commit` | what committed change is measured against | sealed label |
   | `ambient_root` | which second tree is observed, and where integration is checked | sealed label |
   | changed-paths baseline | what "changed since the child started" means | **sealed digest** |

   **Consistency fields** — `runtime`, `integration_mode` and `destination`. Evaluation reads these
   from the *receipt*, never from the separately supplied arguments, so a mismatch cannot change the
   verdict. They are compared anyway, because a caller whose landing disagrees with its receipt has
   muddled two dispatches and failing closed is cheap — but calling them deciding inputs would be
   the same overclaim this document exists to avoid.

   `write_scope` is sealed and deliberately **not** compared: it is a pure function of `mutating`,
   `scope`, the landing, the run and the row, all of which are compared individually, so a
   comparison against it could never be the check that catches a substitution. A check that can
   never fire alone reports coverage it does not have.

   The baseline is the one input with no label: it is repository state *at an instant*, and the same
   landing has different, equally valid snapshots before and after a write, so binding the landing
   says nothing about *when* the snapshot was taken. It is bound by digest rather than re-taken here,
   because U4's readiness path is its producer and two takers of one snapshot is the same shape as
   two writers of one register column. One producer, one binder, one comparison. Any disagreement is
   `receipt_mismatch`, before anything else is read.

   The root is **derived, not supplied**. Comparing a supplied root against the receipt was tried
   and it does not work: every such comparison put a value the caller passed beside the copy the
   receipt made from that same value at issue time. That catches a caller who changes the
   repository between issuing and evaluating, and it cannot, even in principle, catch one that was
   wrong when it was copied — and the copy is made at issue time, which is the *first* observation
   of the repository and so has nothing to compare against. A check of X against a copy of X is not
   a check of X.

   So the parameter is gone from `issue_receipt`, `evaluate_completion`, `settle_artifact` and
   `settlement_record`. Issuing derives the repository from `landing.ambient_root`, which
   `GitLanding.provision` sets to the repository for both landing kinds — the ambient checkout for
   a read-only child, and the checkout a mutating child's worktree was cut from — and refuses a
   landing that does not sit inside that repository. `cwd` and `ambient_root` are independently
   settable; a receipt sealed from a working directory in one repository and a claimed root in
   another is internally consistent and would pass every later comparison. Containment against the
   filesystem is a fact with a provenance independent of either field.

   Evaluation still has two objects that name a repository. It takes the store from `receipt.root`
   only after the landing is shown to sit inside that repository, and raises rather than records
   when it does not: there is then no register this evaluation may write. `settlement_record` and
   `settle_artifact` receive a receipt and no second opinion, so they read the sealed root as the
   authority on where that receipt's own settlement belongs. A landing that does not name its
   repository is refused rather than defaulted to its working directory, because that default
   would seal a mutating child's worktree as its repository and file the verdict where nothing
   else about the run is recorded.

   `read_receipt` is the exception and it keeps the check. It is handed a repository and a row id
   and has no receipt yet, so the repository genuinely has to be supplied; there the two values
   have independent origins and comparing them is real. It matters most for the **verifier's**
   receipt, which the depth gate loads by row id rather than receiving as an argument: the run
   secret is named for the run alone and lives outside every repository, so two checkouts running
   one run id share it and an authentic verifier dispatch from one authenticates in the other.
   `_record` cannot make any check — it is handed a row id, not a receipt — and it does not need
   one: its caller derives the repository from the receipt rather than accepting it.
1. **Predicate tamper check** — the closure digest, before anything is executed.
2. **Settlement** — destination unchanged, in-flight present, rename; or a replay of the recorded
   settlement for this dispatch.
3. **Run binding** — the artifact carries this dispatch's token.

Those short-circuit: an unsettled or unbound artifact is not evidence, and there is nothing to
evaluate.

4. **Predicate outcome** and **boundary check**, computed independently. A boundary violation fails
   completion **even when the predicate passed**, and is reported in preference to a predicate
   failure because a breached boundary makes the whole result unattributable. The predicate's own
   side effects — on the landing, on the ambient tree, and on the artifact directory — are checked
   before either.
5. **Integration** to the recorded destination.
6. **Depth sample** for judgment-shaped work.

The whole sequence is safe to re-run for one dispatch, which is what makes both the restart path and
judgment work reachable.
