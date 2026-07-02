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
object with five fields, matching `artifact_pointer.py`'s `ArtifactPointer` dataclass exactly:

```artifact-pointer
{"kind":"diff","locator":"refs/team-execution/snapshots/<run-id>/<epoch>","hash":"<tree-oid>","epoch":"<epoch>","deref":"git diff <base-tree> <tree-oid>"}
```

- `kind` — `diff` (Layer 1, the only kind wired in this unit), `file`, or `symbol` (later layers).
- `locator` — the git holding ref pinning the snapshot tree.
- `hash` — the tree OID; git is content-addressed, so this doubles as the integrity hash (no
  second checksum).
- `epoch` — the freshness marker (the consensus iteration the snapshot was taken in).
- `deref` — the self-describing command that fetches the artifact; a receiver needs zero prior
  knowledge beyond running it.

## Dereference procedure

Run either of these — they are equivalent:

```bash
python3 plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py \
  deref '<the pointer JSON object>'
```

or the embedded raw command from the pointer's `deref` field directly (e.g. `git diff <base-tree>
<tree-oid>`), after independently confirming the ref still resolves to the stated hash.

`artifact_pointer.py deref` does both for you: it verifies **integrity** (the tree OID resolves as
a tree AND the holding ref still points at it) and **freshness** (no newer epoch ref exists for the
same run-id) before running the deref command. Verification failure raises a typed error and exits
non-zero — never a silent review of wrong or stale bytes:

- `POINTER_HASH_MISMATCH` — the ref moved or the tree is unresolvable. Do not proceed; report the
  mismatch to the orchestrator instead of guessing at the diff.
- `POINTER_STALE` — a newer epoch supersedes this pointer. Request a fresh pointer before reviewing;
  reviewing a stale snapshot risks scoring code that has already changed.

## Full dereference — review invariance (R5/R14)

**v1 receivers always dereference and read the FULL artifact.** Per-lens scoping (a reviewer
fetching only the hunks relevant to its dimension) is explicitly **not allowed** in v1 — it would
change what is reviewed, not just how the bytes arrive, and pointerization must never do that
(R14). A reviewer or validator that half-derefs sees strictly less than the inlined version showed
it before this change. If a future revision wants per-lens scoping, it needs its own
no-silent-drop guarantee before it can touch this contract.

## KTD7 fallback — capability-keyed degradation

Git-object pointers only resolve for a receiver that shares the parent repo's `.git/objects` —
same-cwd resident teammates and linked-worktree children. They do **not** resolve inside an
external-engine disposable clone (remotes-stripped, separate object store) or any future
tool-restricted agent that cannot run `git cat-file` against the parent repo.

The rule is capability-keyed, not agent-keyed: if the receiver cannot run `git cat-file` against
the parent repo, the orchestrator falls back to inlined content for that receiver, regardless of
what kind of agent it is. This is a degradation path, not an error — inlining is always a safe
fallback; a wrong or unresolvable pointer is not.

## Threshold

The pointerize-vs-inline decision is stated once, in `SKILL.md` Step B1. This document does not
repeat the numbers — see `SKILL.md` for the authoritative threshold rule.

## Layer 3 — symbol pointers (light form)

A `kind: symbol` pointer's `locator` is a light `<repo-relative-path>#<symbol-name>` reference —
no formal resolver. The receiver resolves it with its existing grep/read tools, the same way it
would locate a symbol during ordinary code review. There is no dependency on an LSP/serena-style
resolver in v1; a formal resolver is deferred and not attempted here.
