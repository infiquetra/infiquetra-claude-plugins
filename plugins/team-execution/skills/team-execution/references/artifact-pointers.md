# Artifact Pointers — Receiver Contract

An **artifact pointer** replaces an inlined artifact (a full `git diff`, a changed-files summary)
in a spawned-agent prompt once the payload crosses the threshold defined in
`team-execution/skills/team-execution/SKILL.md` Step B1. A receiver that gets a pointer instead of
inlined bytes dereferences it itself — the receiver is already capable of running the tools this
requires (`git`, `cat-file`, `diff`); a pointer removes redundant copies from the prompt, not
capability from the receiver.

This document is the contract every pointer receiver — reviewer, validator, or any future consumer
— follows. It is referenced, not duplicated, by the spawn templates in `consensus-protocol.md` and
`validator-spawn-quirks.md`, and by the base reviewer agents.

---

## Pointer shape

A pointer travels as a single fenced code block labelled `artifact-pointer` containing one JSON
object matching `artifact_pointer.py`'s `ArtifactPointer` dataclass exactly. A Layer-1 (`diff`)
pointer:

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch>","hash":"<snapshot-tree-oid>","epoch":"<epoch>","deref":"git diff <base-tree> <snapshot-tree>","base":"<base-tree-oid>"}
```

A Layer-2 (`file`) pointer — note the `epoch` and `locator` take a different shape:

```artifact-pointer
{"kind":"file","locator":"objects/<sha256[:2]>/<sha256>","hash":"<sha256>","epoch":"<run-id>/<epoch>","deref":"artifact_pointer.py deref '<pointer-json>'","base":""}
```

- `kind` — `diff` (Layer 1, git-object snapshot), `file` (Layer 2, content-addressed store), or
  `symbol` (Layer 3, light path reference).
- `locator` — for `diff`, the git holding ref pinning the snapshot tree; for `file`,
  `objects/<sha256[:2]>/<sha256>` under the store root; for `symbol`, `<repo-path>#<symbol>`.
- `hash` — for `diff`, the snapshot tree OID (git is content-addressed, so this doubles as the
  integrity hash, no second checksum); for `file`, the sha256 of the stored bytes.
- `epoch` — the freshness marker. For `diff` it is a bare `<epoch>`; for `file` it is
  `<run-id>/<epoch>`. A non-numeric ("opaque") epoch is carried but freshness is not enforced for it.
- `deref` — a human-readable description of how the artifact is fetched. It is **illustrative only**:
  the receiver does not parse or execute this string (see below).
- `base` — for `diff`, the base tree OID the snapshot is diffed against, pinned at snapshot time so
  the deref cannot drift if HEAD moves mid-run; empty for `file` / `symbol`.

## Dereference procedure

**`artifact_pointer.py deref` is the required verification path.** Run it from the repo root — it
resolves git objects and the store relative to the repository, and a spawned agent's cwd is not
guaranteed to be the repo root, so pass `--repo-root <path>` if you are elsewhere:

```bash
python3 plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py \
  deref '<the pointer JSON object>'
```

Do **not** hand-run the raw `git diff` from the `deref` field as a substitute. That field is
illustrative, and running it yourself verifies neither **freshness** nor integrity — so you could
review a superseded snapshot. The CLI verifies both, then rebuilds the fetch command deterministically
from the validated fields (never from the free-form `deref` string) and returns the full artifact on
stdout:

- **integrity** — for `diff`, the tree OID resolves as a tree AND the holding ref still points at it;
  for `file`, the stored bytes re-hash to the pointer's sha256.
- **freshness** — no newer epoch supersedes this pointer for the same run-id.

It never returns wrong or stale bytes. Exit codes are part of the contract:

- **exit 1** — a typed pointer failure; the code is printed on stderr:
  - `POINTER_HASH_MISMATCH` — the ref moved, the tree/bytes are unresolvable, or the pointer is
    otherwise inconsistent. Do not proceed; report it to the orchestrator instead of guessing.
  - `POINTER_STALE` — a newer epoch supersedes this pointer. Request a fresh pointer; reviewing a
    stale snapshot risks scoring code that has already changed.
- **exit 2** — malformed input or an underlying git error (invalid pointer JSON, or a `symbol`
  pointer passed to `deref`). A usage/environment problem, not a retryable staleness signal — fix the
  input rather than requesting a fresh pointer.

## Full dereference — review invariance (R5/R14)

**v1 receivers always dereference and read the FULL artifact.** Per-lens scoping (a reviewer
fetching only the hunks relevant to its dimension) is explicitly **not allowed** in v1 — it would
change what is reviewed, not just how the bytes arrive, and pointerization must never do that
(R14). A reviewer or validator that half-derefs sees strictly less than the inlined version showed
it before this change. If a future revision wants per-lens scoping, it needs its own
no-silent-drop guarantee before it can touch this contract.

The dereferenced Layer-1 diff is a **superset** of a plain working-tree `git diff`: the snapshot
stages untracked files (`git add -A` under a temp index), so newly-added files a working-tree diff
would omit ARE visible here. Pointerization therefore never shows a receiver *less* than inlining
would — the invariant is "never less than inline," not byte-for-byte identical.

## Liveness observations are not artifact pointers

`artifact_pointer.py liveness-baseline` and `liveness-observe` reuse the temporary-index custody
pattern but intentionally create no holding ref or CAS entry. They hash only the resident's declared
paths and return `unchanged`, `scoped-activity-unattributed`, or `artifact-progress`. A changed digest
never proves authorship, even when worker scopes are disjoint. `artifact-progress` requires an exact
`liveness.exclusive-provenance.v1` receipt binding the subject, live lease/fence, paths, both digests,
observation interval, custody, and covered generation IDs. Pointer epoch, mtime, chat activity, and
the ordinary snapshot command are not liveness progress evidence.

## KTD7 fallback — capability-keyed degradation

Git-object pointers only resolve for a receiver that shares the parent repo's `.git/objects` —
same-cwd resident teammates and linked-worktree children. They do **not** resolve inside an
external-engine disposable clone (remotes-stripped, separate object store) or any future
tool-restricted agent that cannot run `git cat-file` against the parent repo.

The rule is capability-keyed, not agent-keyed: if the receiver cannot run `git cat-file` against
the parent repo, the orchestrator falls back to inlined content for that receiver, regardless of
what kind of agent it is. This is a degradation path, not an error — inlining is always a safe
fallback; a wrong or unresolvable pointer is not.

This fallback is an **advisory orchestrator rule, not a runtime-enforced gate**. There is no
capability preflight in v1: the orchestrator decides by the receiver's kind, and a git pointer
mis-sent to a clone that cannot resolve it surfaces reactively as a `POINTER_HASH_MISMATCH` the
receiver reports (fail-then-inline), rather than being prevented before the send.

## Threshold

The pointerize-vs-inline decision is stated once, in `SKILL.md` Step B1. This document does not
repeat the numbers — see `SKILL.md` for the authoritative threshold rule. Like the KTD7 fallback, it
is an advisory rule the orchestrator applies by judgment, not a gate enforced at runtime.

## Layer 3 — symbol pointers (light form)

A `kind: symbol` pointer's `locator` is a light `<repo-relative-path>#<symbol-name>` reference —
no formal resolver. The receiver resolves it with its existing grep/read tools, the same way it
would locate a symbol during ordinary code review. There is no dependency on an LSP/serena-style
resolver in v1; a formal resolver is deferred and not attempted here.

**Do not run `artifact_pointer.py deref` on a `kind: symbol` pointer** — the CLI dereferences only
`diff` and `file` kinds and rejects a symbol pointer (exit 2). Resolve a symbol pointer directly with
your grep/read tools.
