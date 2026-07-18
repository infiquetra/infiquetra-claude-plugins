#!/usr/bin/env python3
"""Cross-runtime Outcome compatibility contract (#604) — discovery, schemas, and HALT receipts.

This module is the runtime-neutral seam that lets another conforming runtime (the Codex Saga
consumer, infiquetra-codex-plugins#34) discover an existing Outcome by **canonical repository
identity plus Outcome ID** and negotiate compatibility before any coordination:

* The **committed** Outcome spec (a git blob, never the mutable working-tree file) and GitHub
  completion evidence remain the only canonical sources (parent #579 authority model).
* Same-clone coordination consumes the merged #356 fleet broker, #351 dispatch-settlement
  identity, and #355 protected-evidence contracts — this module never mints a sibling authority.
* A different clone receives read-only canonical reconstruction only; nothing serialized here
  carries dispatch authority, a filesystem path, or runtime-local state.

Four closed schemas (KTD8 — one producer vocabulary, consumed verbatim by the Codex port):

* ``outcome.discovery.v1``      — the discovery/compatibility envelope :func:`discover` emits.
* ``outcome.canonical-status.v1`` — the portable read-only projection (built in the U2 seam).
* ``outcome.handoff-reference.v1`` — the printable handoff reference (U3; a pointer, never a
  bearer token — KTD2).
* ``outcome.compatibility-halt.v1`` — the closed failure receipt every rejection path returns.

Fail-closed rules (KTD5/KTD7): unknown schemas, unknown fields, wrong types (including
``bool`` masquerading as ``int``), duplicate JSON keys, oversized input, symlinked or
non-regular files, ambiguous discovery refs, foreign or credentialed remotes, and protocol
skew all raise :class:`CompatibilityHaltError` **before** any store, broker, board, or GitHub
mutation. A halt receipt names the unsupported value, the locally supported range, and a
non-mutating next action — and never embeds a local path, credential, or raw file body.

House pattern: pure functions over explicit values, dependency-injected git runner, lazy
sibling imports, no I/O at import time.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, cast

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Schema names, protocol range, capability vocabulary, caps
# ---------------------------------------------------------------------------

SCHEMA_DISCOVERY = "outcome.discovery.v1"
SCHEMA_CANONICAL_STATUS = "outcome.canonical-status.v1"
SCHEMA_HANDOFF_REFERENCE = "outcome.handoff-reference.v1"
SCHEMA_COMPATIBILITY_HALT = "outcome.compatibility-halt.v1"

PROTOCOL_VERSION = 1
PROTOCOL_MIN_SUPPORTED = 1
PROTOCOL_MAX_SUPPORTED = 1

# The capabilities a consumer MUST support to coordinate with this producer (R9). Frozen
# vocabulary — the Codex consumer ports these strings verbatim from the committed fixtures.
REQUIRED_CAPABILITIES = (
    "committed-spec-structure",
    "github-completion",
    "git-common-dir-coordination",
    "fleet-broker-fencing",
    "dispatch-settlement-identity",
)

# Authority block constants — compatibility METADATA describing where authority lives; the
# receiver derives every fact independently and never trusts the envelope's self-description.
AUTHORITY = {
    "structure": "committed-spec",
    "completion": "github",
    "same_clone_coordination": "git-common-dir+fleet-broker+dispatch-settlement",
    "cross_clone_mutation": "forbidden",
}

RUNTIME_LABEL = "claude"

# Bounded-input caps (R12). Hitting a cap is a HALT, never a truncation-to-clean.
MAX_ENVELOPE_BYTES = 256 * 1024
MAX_SPEC_BLOB_BYTES = 8 * 1024 * 1024
MAX_SPEC_NODES = 10_000
GIT_STDOUT_CAP = 16 * 1024 * 1024
GIT_STDERR_CAP = 64 * 1024
GIT_TIMEOUT_SECONDS = 20.0

# The canonical committed placement of an outcome spec (repo-relative POSIX, R3/R4).
SPEC_PATH_TEMPLATE = "docs/outcomes/{outcome_id}/outcome-spec.json"

# The only remote host this contract recognizes (R2): exact, never configurable.
_CANONICAL_HOST = "github.com"

_OID_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")  # sha1 or sha256 object ids
_IDENTITY_RE = re.compile(r"^github\.com/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


class CompatibilityHaltError(Exception):
    """A fail-closed rejection carrying its ``outcome.compatibility-halt.v1`` receipt.

    Raised BEFORE any mutation (KTD7). ``receipt()`` is the closed, serializable form; the
    message mirrors it for logs. Receipts never contain absolute paths, credentials, or raw
    input bodies (R12) — callers may print them verbatim.
    """

    def __init__(self, code: str, *, unsupported: str, supported: str, next_action: str):
        self.code = code
        self.unsupported = unsupported
        self.supported = supported
        self.next_action = next_action
        super().__init__(f"{code}: unsupported={unsupported!r} supported={supported!r}")

    def receipt(self) -> dict[str, str]:
        return {
            "schema": SCHEMA_COMPATIBILITY_HALT,
            "code": self.code,
            "unsupported": self.unsupported,
            "supported": self.supported,
            "next_action": self.next_action,
        }


# ---------------------------------------------------------------------------
# Bounded fixed-argv git adapter (dependency-injected for tests)
# ---------------------------------------------------------------------------


def _git(
    args: list[str],
    *,
    cwd: Path,
    runner: Callable[..., Any] | None = None,
    binary: bool = False,
) -> bytes | str:
    """Run one fixed-argv git command with the R12 timeout and output caps.

    Returns stdout (text by default, raw bytes when ``binary``). Any failure — git missing,
    timeout, nonzero exit, output over cap — is a :class:`CompatibilityHaltError`; stderr is
    truncated to its cap and never echoed into the receipt (only into the exception message
    is avoided entirely — receipts stay redacted).
    """
    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 B607 — fixed argv, no shell, bounded by timeout
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        raise CompatibilityHaltError(
            "git-unavailable",
            unsupported=f"git {args[0]}",
            supported="a repository where fixed-argv git completes within the bounded timeout",
            next_action="verify git is installed and the repository is reachable, then retry",
        ) from None
    stdout = (
        result.stdout if isinstance(result.stdout, bytes) else str(result.stdout or "").encode()
    )
    stderr = (
        result.stderr if isinstance(result.stderr, bytes) else str(result.stderr or "").encode()
    )
    if len(stdout) > GIT_STDOUT_CAP or len(stderr) > GIT_STDERR_CAP:
        raise CompatibilityHaltError(
            "git-output-cap",
            unsupported=f"git {args[0]} output beyond {GIT_STDOUT_CAP} bytes",
            supported=f"stdout <= {GIT_STDOUT_CAP} bytes, stderr <= {GIT_STDERR_CAP} bytes",
            next_action="inspect the repository state manually; the scan refuses oversized output",
        )
    if getattr(result, "returncode", 1) != 0:
        raise CompatibilityHaltError(
            "git-failed",
            unsupported=f"git {args[0]} (exit {getattr(result, 'returncode', 'unknown')})",
            supported="a git invocation that exits 0",
            next_action="run the equivalent read-only git command manually to see the failure",
        )
    if binary:
        return stdout
    return stdout.decode("utf-8", errors="strict").strip()


# ---------------------------------------------------------------------------
# R2 — canonical repository identity (Git-derived, path-independent, exact)
# ---------------------------------------------------------------------------


def repository_identity(repo_root: Path, *, runner: Callable[..., Any] | None = None) -> str:
    """Normalize ``remote.origin.url`` to the exact ``github.com/<owner>/<repo>`` identity.

    Accepted spellings (R2): ``https://github.com/o/r``, ``git@github.com:o/r``, and
    ``ssh://git@github.com/o/r`` — each with an optional terminal ``.git`` (the ONLY suffix
    stripped). A credentialed URL, foreign host, missing origin, or unparseable remote HALTs
    before any store access. Local paths, symlink spellings, and worktree locations never
    participate — identity comes from git config alone (KTD5).
    """
    try:
        raw = _git(["config", "--get", "remote.origin.url"], cwd=repo_root, runner=runner)
    except CompatibilityHaltError as halt:
        if halt.code == "git-failed":
            raise CompatibilityHaltError(
                "repo-identity-missing-origin",
                unsupported="a repository with no remote.origin.url",
                supported="a clone whose origin remote points at the canonical github.com repository",
                next_action="add the canonical origin remote, then re-run discover",
            ) from None
        raise
    remote = cast(str, raw).strip()
    if not remote:
        raise CompatibilityHaltError(
            "repo-identity-missing-origin",
            unsupported="an empty remote.origin.url",
            supported="a clone whose origin remote points at the canonical github.com repository",
            next_action="add the canonical origin remote, then re-run discover",
        )

    path: str | None = None
    if remote.startswith("https://"):
        rest = remote.removeprefix("https://")
        host, _, tail = rest.partition("/")
        if "@" in host:
            raise CompatibilityHaltError(
                "repo-identity-credentialed-url",
                unsupported="a remote URL embedding credentials",
                supported="a credential-free https or ssh origin URL",
                next_action="remove embedded credentials from remote.origin.url, then re-run discover",
            )
        if host.lower() != _CANONICAL_HOST:
            _halt_foreign_host(host)
        path = tail
    elif remote.startswith("ssh://"):
        rest = remote.removeprefix("ssh://")
        userhost, _, tail = rest.partition("/")
        user, _, host = userhost.rpartition("@")
        if user not in ("", "git"):
            raise CompatibilityHaltError(
                "repo-identity-credentialed-url",
                unsupported="a remote URL embedding a non-git user",
                supported="ssh://git@github.com/<owner>/<repo>",
                next_action="use the canonical ssh origin form, then re-run discover",
            )
        if host.lower() != _CANONICAL_HOST:
            _halt_foreign_host(host)
        path = tail
    elif "@" in remote and ":" in remote and "://" not in remote:
        userhost, _, tail = remote.partition(":")
        user, _, host = userhost.rpartition("@")
        if user != "git":
            raise CompatibilityHaltError(
                "repo-identity-credentialed-url",
                unsupported="an scp-style remote with a non-git user",
                supported="git@github.com:<owner>/<repo>",
                next_action="use the canonical scp-style origin form, then re-run discover",
            )
        if host.lower() != _CANONICAL_HOST:
            _halt_foreign_host(host)
        path = tail
    else:
        raise CompatibilityHaltError(
            "repo-identity-malformed",
            unsupported="an unrecognized remote.origin.url form",
            supported="https://github.com/<o>/<r>, git@github.com:<o>/<r>, or ssh://git@github.com/<o>/<r>",
            next_action="point remote.origin.url at the canonical github.com repository, then re-run discover",
        )

    parts = [p for p in path.removesuffix(".git").strip("/").split("/") if p]
    if len(parts) != 2:
        raise CompatibilityHaltError(
            "repo-identity-malformed",
            unsupported="a remote path that is not exactly <owner>/<repo>",
            supported="github.com/<owner>/<repo>",
            next_action="point remote.origin.url at the canonical github.com repository, then re-run discover",
        )
    identity = f"{_CANONICAL_HOST}/{parts[0]}/{parts[1]}"
    if not _IDENTITY_RE.match(identity):
        raise CompatibilityHaltError(
            "repo-identity-malformed",
            unsupported="a repository identity with unsupported characters",
            supported="github.com/<owner>/<repo> using [A-Za-z0-9._-]",
            next_action="rename the origin remote to a canonical github.com form, then re-run discover",
        )
    return identity


def _halt_foreign_host(host: str) -> NoReturn:
    raise CompatibilityHaltError(
        "repo-identity-foreign-host",
        unsupported=f"remote host {host or '(empty)'!r}",
        supported=_CANONICAL_HOST,
        next_action="clone from the canonical github.com repository, then re-run discover",
    )


# ---------------------------------------------------------------------------
# Strict JSON (duplicate-key rejection, closed objects, exact types)
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise CompatibilityHaltError(
                "schema-duplicate-key",
                unsupported=f"duplicate JSON key {key!r}",
                supported="a JSON object with unique keys",
                next_action="regenerate the document from a conforming producer",
            )
        seen[key] = value
    return seen


def parse_strict_json(data: bytes | str, *, what: str, cap: int = MAX_ENVELOPE_BYTES) -> Any:
    """Parse JSON with duplicate-key rejection and the byte cap for ``what`` (R12)."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > cap:
        raise CompatibilityHaltError(
            "input-oversize",
            unsupported=f"{what} of {len(raw)} bytes",
            supported=f"{what} <= {cap} bytes",
            next_action="regenerate the document from a conforming producer",
        )
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except CompatibilityHaltError:
        raise
    except (UnicodeDecodeError, ValueError):
        raise CompatibilityHaltError(
            "schema-malformed-json",
            unsupported=f"unparseable {what}",
            supported="strict UTF-8 JSON",
            next_action="regenerate the document from a conforming producer",
        ) from None


def read_reference_file(path: Path, *, what: str, cap: int = MAX_ENVELOPE_BYTES) -> bytes:
    """Read an envelope/reference file rejecting symlinks and non-regular files (R12)."""
    if path.is_symlink() or not path.is_file():
        raise CompatibilityHaltError(
            "input-not-regular-file",
            unsupported=f"a {what} that is a symlink, directory, or special file",
            supported=f"a regular file holding the {what}",
            next_action="pass the regular file emitted by discover/handoff",
        )
    size = path.stat().st_size
    if size > cap:
        raise CompatibilityHaltError(
            "input-oversize",
            unsupported=f"{what} of {size} bytes",
            supported=f"{what} <= {cap} bytes",
            next_action="regenerate the document from a conforming producer",
        )
    return path.read_bytes()


def _require(obj: dict[str, Any], key: str, kind: type, *, where: str) -> Any:
    if key not in obj:
        raise CompatibilityHaltError(
            "schema-field-missing",
            unsupported=f"{where} without {key!r}",
            supported=f"{where} carrying {key!r}",
            next_action="regenerate the document from a conforming producer",
        )
    value = obj[key]
    if isinstance(value, bool) and kind is not bool:
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported=f"{where}.{key} as bool",
            supported=f"{where}.{key} as {kind.__name__}",
            next_action="regenerate the document from a conforming producer",
        )
    if not isinstance(value, kind):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported=f"{where}.{key} as {type(value).__name__}",
            supported=f"{where}.{key} as {kind.__name__}",
            next_action="regenerate the document from a conforming producer",
        )
    return value


def _closed(obj: dict[str, Any], allowed: tuple[str, ...], *, where: str) -> None:
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        raise CompatibilityHaltError(
            "schema-field-unknown",
            unsupported=f"{where} field {unknown[0]!r}",
            supported=f"{where} fields: {', '.join(allowed)}",
            next_action="regenerate the document from a conforming producer, or upgrade this runtime",
        )


def _str_list(obj: dict[str, Any], key: str, *, where: str) -> list[str]:
    value = _require(obj, key, list, where=where)
    for item in value:
        if isinstance(item, bool) or not isinstance(item, str):
            raise CompatibilityHaltError(
                "schema-field-type",
                unsupported=f"{where}.{key} entry as {type(item).__name__}",
                supported=f"{where}.{key} as a list of strings",
                next_action="regenerate the document from a conforming producer",
            )
    return list(value)


# ---------------------------------------------------------------------------
# Deterministic serialization (R8 — byte-identical across clones)
# ---------------------------------------------------------------------------


def canonical_json(obj: Any) -> str:
    """Serialize deterministically: sorted keys, compact separators, no wall-clock inputs."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(text.encode("utf-8")) > MAX_ENVELOPE_BYTES:
        raise CompatibilityHaltError(
            "input-oversize",
            unsupported=f"a serialized document of {len(text.encode('utf-8'))} bytes",
            supported=f"documents <= {MAX_ENVELOPE_BYTES} bytes",
            next_action="reduce the outcome graph or split the document",
        )
    return text


# ---------------------------------------------------------------------------
# R9 — protocol negotiation (narrow, fail closed, before any coordination)
# ---------------------------------------------------------------------------


def validate_protocol_block(block: dict[str, Any]) -> None:
    """Validate a ``protocol`` subobject structurally (closed, exact int types)."""
    _closed(
        block,
        ("version", "min_supported", "max_supported", "required_capabilities"),
        where="protocol",
    )
    version = _require(block, "version", int, where="protocol")
    lo = _require(block, "min_supported", int, where="protocol")
    hi = _require(block, "max_supported", int, where="protocol")
    _str_list(block, "required_capabilities", where="protocol")
    if lo > hi or not (lo <= version <= hi):
        raise CompatibilityHaltError(
            "protocol-range-malformed",
            unsupported=f"protocol range [{lo}, {hi}] with version {version}",
            supported="min_supported <= version <= max_supported",
            next_action="regenerate the envelope from a conforming producer",
        )


def negotiate(peer_protocol: dict[str, Any]) -> int:
    """Intersect a peer's protocol block with local support; HALT on skew (R9).

    Returns the highest mutually supported protocol version. There is no best-effort field
    dropping and no post-mutation downgrade — a failed negotiation happens before any
    coordination touches a store, broker, or GitHub.
    """
    validate_protocol_block(peer_protocol)
    lo = max(int(peer_protocol["min_supported"]), PROTOCOL_MIN_SUPPORTED)
    hi = min(int(peer_protocol["max_supported"]), PROTOCOL_MAX_SUPPORTED)
    if lo > hi:
        raise CompatibilityHaltError(
            "protocol-version-skew",
            unsupported=(
                f"peer protocol range [{peer_protocol['min_supported']}, "
                f"{peer_protocol['max_supported']}]"
            ),
            supported=f"local protocol range [{PROTOCOL_MIN_SUPPORTED}, {PROTOCOL_MAX_SUPPORTED}]",
            next_action="upgrade the older runtime until the protocol ranges intersect",
        )
    missing = [c for c in peer_protocol["required_capabilities"] if c not in REQUIRED_CAPABILITIES]
    if missing:
        raise CompatibilityHaltError(
            "capability-missing",
            unsupported=f"required capability {missing[0]!r}",
            supported=f"capabilities: {', '.join(REQUIRED_CAPABILITIES)}",
            next_action="upgrade this runtime to one advertising the required capability",
        )
    return hi


# ---------------------------------------------------------------------------
# R3/R4 — committed-spec discovery (deterministic; ambiguity is fatal)
# ---------------------------------------------------------------------------


def _candidate_refs(outcome_id: str) -> tuple[str, ...]:
    branch = f"outcome/{outcome_id}"
    return ("HEAD", f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")


def _blob_oid(
    repo_root: Path, ref: str, rel_path: str, *, runner: Callable[..., Any] | None
) -> str | None:
    """The blob OID of ``rel_path`` at ``ref``, or None when the ref/path is absent."""
    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 B607 — fixed argv, no shell, bounded by timeout
            ["git", "rev-parse", f"{ref}:{rel_path}"],
            cwd=str(repo_root),
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        raise CompatibilityHaltError(
            "git-unavailable",
            unsupported="git rev-parse",
            supported="a repository where fixed-argv git completes within the bounded timeout",
            next_action="verify git is installed and the repository is reachable, then retry",
        ) from None
    if getattr(result, "returncode", 1) != 0:
        return None
    stdout = (
        result.stdout if isinstance(result.stdout, bytes) else str(result.stdout or "").encode()
    )
    oid = stdout.decode("utf-8", errors="strict").strip()
    return oid if _OID_RE.match(oid) else None


def resolve_committed_spec(
    repo_root: Path,
    outcome_id: str,
    *,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Locate the committed outcome spec and bind its exact identity (R3/R4).

    Looks for ``docs/outcomes/<id>/outcome-spec.json`` on the current committed ref and on the
    canonical ``outcome/<id>`` local/remote refs. Every candidate ref that carries the path
    must agree on the exact blob; disagreement is an ambiguity HALT — never "pick newest"
    (KTD5). Returns the binding: ``spec_path`` (repo-relative), ``commit_oid``, ``blob_oid``,
    ``sha256``, ``schema_version``, ``spec_revision``, plus the parsed ``spec`` dict.
    """
    import outcome_store  # lazy sibling import (house pattern)

    safe_id = outcome_store._safe_name(outcome_id, what="outcome_id")
    rel_path = SPEC_PATH_TEMPLATE.format(outcome_id=safe_id)

    found: dict[str, str] = {}
    for ref in _candidate_refs(safe_id):
        oid = _blob_oid(repo_root, ref, rel_path, runner=runner)
        if oid is not None:
            found[ref] = oid
    if not found:
        raise CompatibilityHaltError(
            "discovery-spec-absent",
            unsupported=f"outcome {safe_id!r} with no committed spec on any candidate ref",
            supported="a committed docs/outcomes/<outcome-id>/outcome-spec.json",
            next_action="commit the outcome spec on its outcome branch, then re-run discover",
        )
    if len(set(found.values())) > 1:
        detail = ", ".join(f"{ref}={oid[:12]}" for ref, oid in sorted(found.items()))
        raise CompatibilityHaltError(
            "discovery-ambiguous-refs",
            unsupported=f"candidate refs disagree on the committed spec ({detail})",
            supported="every candidate ref carrying the spec agrees on one blob",
            next_action="reconcile the outcome branch with its remote, then re-run discover",
        )

    blob_oid = next(iter(found.values()))
    winning_ref = sorted(found)[0] if "HEAD" not in found else "HEAD"
    blob = cast(
        bytes, _git(["cat-file", "blob", blob_oid], cwd=repo_root, runner=runner, binary=True)
    )
    if len(blob) > MAX_SPEC_BLOB_BYTES:
        raise CompatibilityHaltError(
            "input-oversize",
            unsupported=f"a committed spec blob of {len(blob)} bytes",
            supported=f"spec blobs <= {MAX_SPEC_BLOB_BYTES} bytes",
            next_action="split the outcome graph; the discovery contract refuses oversized specs",
        )

    spec = parse_strict_json(blob, what="committed outcome spec", cap=MAX_SPEC_BLOB_BYTES)
    if not isinstance(spec, dict):
        raise CompatibilityHaltError(
            "discovery-spec-invalid",
            unsupported="a committed spec that is not a JSON object",
            supported="a JSON object with outcome_id, schema_version, spec_revision, nodes",
            next_action="repair the committed spec on the outcome branch, then re-run discover",
        )
    embedded = _require(spec, "outcome_id", str, where="spec")
    if embedded != safe_id:
        raise CompatibilityHaltError(
            "discovery-outcome-id-mismatch",
            unsupported=f"a spec embedding outcome_id {embedded!r} at the {safe_id!r} path",
            supported="a spec whose embedded outcome_id matches its committed path",
            next_action="repair the committed spec placement, then re-run discover",
        )
    schema_version = _require(spec, "schema_version", int, where="spec")
    spec_revision = _require(spec, "spec_revision", int, where="spec")
    nodes = _require(spec, "nodes", list, where="spec")
    if len(nodes) > MAX_SPEC_NODES:
        raise CompatibilityHaltError(
            "discovery-node-cap",
            unsupported=f"a spec with {len(nodes)} nodes",
            supported=f"specs with <= {MAX_SPEC_NODES} nodes",
            next_action="split the outcome graph; the discovery contract refuses oversized specs",
        )

    commit_oid = cast(
        str, _git(["rev-parse", winning_ref.removesuffix(":")], cwd=repo_root, runner=runner)
    )
    if not _OID_RE.match(commit_oid):
        raise CompatibilityHaltError(
            "git-failed",
            unsupported="an unparseable commit object id",
            supported="a 40- or 64-hex git object id",
            next_action="run git rev-parse manually to inspect the repository state",
        )
    return {
        "spec_path": rel_path,
        "ref": winning_ref,
        "commit_oid": commit_oid,
        "blob_oid": blob_oid,
        "sha256": hashlib.sha256(blob).hexdigest(),
        "schema_version": schema_version,
        "spec_revision": spec_revision,
        "spec": spec,
        "blob": blob,
    }


def working_tree_matches(
    repo_root: Path,
    binding: dict[str, Any],
) -> bool:
    """True when the working-tree spec file byte-matches the committed blob (KTD3).

    Same-clone mutation requires this to hold — an edited-but-uncommitted spec must not
    silently change apparent authority. A missing or unreadable working-tree file is False
    (fail toward refusing mutation), never an exception.
    """
    path = Path(repo_root) / str(binding["spec_path"])
    try:
        if path.is_symlink() or not path.is_file():
            return False
        return bool(path.read_bytes() == binding["blob"])
    except OSError:
        return False


# ---------------------------------------------------------------------------
# The discovery envelope (build + closed validation)
# ---------------------------------------------------------------------------


def build_discovery_envelope(
    repo_root: Path,
    outcome_id: str,
    *,
    saga_version: str,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Emit the ``outcome.discovery.v1`` envelope for one committed Outcome (R1-R4, R9).

    Validation order is deliberate (KTD7): repository identity, then committed-spec binding —
    all before any store resolution; this function never touches the git-common-dir cache.
    The envelope carries committed/GitHub references and digests only — no local path, no
    cache fact, no transient dispatch state.
    """
    identity = repository_identity(repo_root, runner=runner)
    binding = resolve_committed_spec(repo_root, outcome_id, runner=runner)
    envelope = {
        "schema": SCHEMA_DISCOVERY,
        "protocol": {
            "version": PROTOCOL_VERSION,
            "min_supported": PROTOCOL_MIN_SUPPORTED,
            "max_supported": PROTOCOL_MAX_SUPPORTED,
            "required_capabilities": list(REQUIRED_CAPABILITIES),
        },
        "repository": {"identity": identity},
        "outcome": {
            "id": outcome_id,
            "spec_path": binding["spec_path"],
            "schema_version": binding["schema_version"],
            "spec_revision": binding["spec_revision"],
        },
        "committed": {
            "commit_oid": binding["commit_oid"],
            "blob_oid": binding["blob_oid"],
            "sha256": binding["sha256"],
        },
        "authority": dict(AUTHORITY),
        "producer": {"runtime": RUNTIME_LABEL, "saga_version": saga_version},
    }
    validate_discovery_envelope(envelope)
    return envelope


def validate_discovery_envelope(obj: Any) -> dict[str, Any]:
    """Closed structural validation of an ``outcome.discovery.v1`` document."""
    if not isinstance(obj, dict):
        _halt_schema_kind("discovery envelope")
    _closed(
        obj,
        ("schema", "protocol", "repository", "outcome", "committed", "authority", "producer"),
        where="envelope",
    )
    schema = _require(obj, "schema", str, where="envelope")
    if schema != SCHEMA_DISCOVERY:
        raise CompatibilityHaltError(
            "schema-unknown",
            unsupported=f"schema {schema!r}",
            supported=SCHEMA_DISCOVERY,
            next_action="upgrade the consuming runtime or regenerate from a conforming producer",
        )
    validate_protocol_block(_require(obj, "protocol", dict, where="envelope"))

    repository = _require(obj, "repository", dict, where="envelope")
    _closed(repository, ("identity",), where="envelope.repository")
    identity = _require(repository, "identity", str, where="envelope.repository")
    if not _IDENTITY_RE.match(identity):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="a repository identity outside github.com/<owner>/<repo>",
            supported="github.com/<owner>/<repo>",
            next_action="regenerate the envelope from a conforming producer",
        )

    outcome = _require(obj, "outcome", dict, where="envelope")
    _closed(
        outcome, ("id", "spec_path", "schema_version", "spec_revision"), where="envelope.outcome"
    )
    _require(outcome, "id", str, where="envelope.outcome")
    spec_path_value = _require(outcome, "spec_path", str, where="envelope.outcome")
    if spec_path_value.startswith("/") or ".." in spec_path_value.split("/"):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="an absolute or traversing spec_path",
            supported="a repo-relative docs/outcomes/<id>/outcome-spec.json path",
            next_action="regenerate the envelope from a conforming producer",
        )
    _require(outcome, "schema_version", int, where="envelope.outcome")
    _require(outcome, "spec_revision", int, where="envelope.outcome")

    committed = _require(obj, "committed", dict, where="envelope")
    _closed(committed, ("commit_oid", "blob_oid", "sha256"), where="envelope.committed")
    for key in ("commit_oid", "blob_oid"):
        oid = _require(committed, key, str, where="envelope.committed")
        if not _OID_RE.match(oid):
            raise CompatibilityHaltError(
                "schema-field-type",
                unsupported=f"envelope.committed.{key} outside git object-id form",
                supported="a 40- or 64-hex git object id",
                next_action="regenerate the envelope from a conforming producer",
            )
    digest = _require(committed, "sha256", str, where="envelope.committed")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="envelope.committed.sha256 outside 64-hex form",
            supported="a 64-hex sha256 digest",
            next_action="regenerate the envelope from a conforming producer",
        )

    authority = _require(obj, "authority", dict, where="envelope")
    _closed(authority, tuple(AUTHORITY), where="envelope.authority")
    for key, expected in AUTHORITY.items():
        value = _require(authority, key, str, where="envelope.authority")
        if value != expected:
            raise CompatibilityHaltError(
                "schema-field-type",
                unsupported=f"envelope.authority.{key} = {value!r}",
                supported=f"envelope.authority.{key} = {expected!r}",
                next_action="regenerate the envelope from a conforming producer",
            )

    producer = _require(obj, "producer", dict, where="envelope")
    _closed(producer, ("runtime", "saga_version"), where="envelope.producer")
    _require(producer, "runtime", str, where="envelope.producer")
    _require(producer, "saga_version", str, where="envelope.producer")
    return cast(dict[str, Any], obj)


def parse_discovery_envelope(data: bytes | str) -> dict[str, Any]:
    """Parse + validate an ``outcome.discovery.v1`` document from raw bytes/text."""
    return validate_discovery_envelope(parse_strict_json(data, what="discovery envelope"))


# ---------------------------------------------------------------------------
# outcome.canonical-status.v1 — closed validation (the U2 seam builds instances)
# ---------------------------------------------------------------------------

_CANONICAL_STATES = ("complete", "open", "unknown")


def validate_canonical_status(obj: Any) -> dict[str, Any]:
    """Closed structural validation of an ``outcome.canonical-status.v1`` document."""
    if not isinstance(obj, dict):
        _halt_schema_kind("canonical status")
    _closed(
        obj,
        (
            "schema",
            "repository_identity",
            "outcome_id",
            "committed",
            "completed",
            "candidate_frontier",
            "unknown",
            "node_completion",
            "mutation_allowed",
        ),
        where="status",
    )
    schema = _require(obj, "schema", str, where="status")
    if schema != SCHEMA_CANONICAL_STATUS:
        raise CompatibilityHaltError(
            "schema-unknown",
            unsupported=f"schema {schema!r}",
            supported=SCHEMA_CANONICAL_STATUS,
            next_action="upgrade the consuming runtime or regenerate from a conforming producer",
        )
    identity = _require(obj, "repository_identity", str, where="status")
    if not _IDENTITY_RE.match(identity):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="a repository identity outside github.com/<owner>/<repo>",
            supported="github.com/<owner>/<repo>",
            next_action="regenerate the document from a conforming producer",
        )
    _require(obj, "outcome_id", str, where="status")
    committed = _require(obj, "committed", dict, where="status")
    _closed(committed, ("commit_oid", "blob_oid", "sha256"), where="status.committed")
    _str_list(obj, "completed", where="status")
    _str_list(obj, "candidate_frontier", where="status")
    _str_list(obj, "unknown", where="status")
    rows = _require(obj, "node_completion", list, where="status")
    for row in rows:
        if not isinstance(row, dict):
            _halt_schema_kind("status.node_completion row")
        _closed(
            row,
            ("subplot_id", "contract", "canonical_state", "evidence_digest"),
            where="status.node_completion",
        )
        _require(row, "subplot_id", str, where="status.node_completion")
        _require(row, "contract", str, where="status.node_completion")
        state = _require(row, "canonical_state", str, where="status.node_completion")
        if state not in _CANONICAL_STATES:
            raise CompatibilityHaltError(
                "schema-field-type",
                unsupported=f"canonical_state {state!r}",
                supported=f"one of: {', '.join(_CANONICAL_STATES)}",
                next_action="regenerate the document from a conforming producer",
            )
        _require(row, "evidence_digest", str, where="status.node_completion")
    allowed = _require(obj, "mutation_allowed", bool, where="status")
    if allowed is not False:
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="a canonical status claiming mutation_allowed=true",
            supported="mutation_allowed=false (cross-clone reconstruction is read-only)",
            next_action="use same-clone attach for mutation; canonical status never authorizes it",
        )
    return cast(dict[str, Any], obj)


# ---------------------------------------------------------------------------
# outcome.handoff-reference.v1 — closed validation (the U3 seam builds instances)
# ---------------------------------------------------------------------------

HANDOFF_OPERATIONS = ("advance-one", "attend")


def validate_handoff_reference(obj: Any) -> dict[str, Any]:
    """Closed structural validation of the printable ``outcome.handoff-reference.v1``.

    The public reference is a POINTER (KTD2): opaque id + digest + protocol + operation +
    subplot. It carries no path, no cache content, and cannot authorize by itself —
    acceptance reopens the protected local record.
    """
    if not isinstance(obj, dict):
        _halt_schema_kind("handoff reference")
    _closed(
        obj,
        ("schema", "handoff_id", "digest", "protocol", "operation", "subplot_id"),
        where="handoff",
    )
    schema = _require(obj, "schema", str, where="handoff")
    if schema != SCHEMA_HANDOFF_REFERENCE:
        raise CompatibilityHaltError(
            "schema-unknown",
            unsupported=f"schema {schema!r}",
            supported=SCHEMA_HANDOFF_REFERENCE,
            next_action="upgrade the consuming runtime or regenerate from a conforming producer",
        )
    handoff_id = _require(obj, "handoff_id", str, where="handoff")
    if not re.fullmatch(r"[0-9a-f]{32}", handoff_id):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="a handoff_id outside 32-hex form",
            supported="a 32-hex opaque handoff id",
            next_action="regenerate the reference from a conforming producer",
        )
    digest = _require(obj, "digest", str, where="handoff")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported="a handoff digest outside 64-hex form",
            supported="a 64-hex sha256 digest",
            next_action="regenerate the reference from a conforming producer",
        )
    validate_protocol_block(_require(obj, "protocol", dict, where="handoff"))
    operation = _require(obj, "operation", str, where="handoff")
    if operation not in HANDOFF_OPERATIONS:
        raise CompatibilityHaltError(
            "schema-field-type",
            unsupported=f"handoff operation {operation!r}",
            supported=f"one of: {', '.join(HANDOFF_OPERATIONS)}",
            next_action="request a supported single-subplot operation",
        )
    _require(obj, "subplot_id", str, where="handoff")
    return cast(dict[str, Any], obj)


# ---------------------------------------------------------------------------
# outcome.compatibility-halt.v1 — closed validation (receipts round-trip too)
# ---------------------------------------------------------------------------


def validate_halt_receipt(obj: Any) -> dict[str, Any]:
    """Closed structural validation of an ``outcome.compatibility-halt.v1`` receipt."""
    if not isinstance(obj, dict):
        _halt_schema_kind("halt receipt")
    _closed(obj, ("schema", "code", "unsupported", "supported", "next_action"), where="halt")
    schema = _require(obj, "schema", str, where="halt")
    if schema != SCHEMA_COMPATIBILITY_HALT:
        raise CompatibilityHaltError(
            "schema-unknown",
            unsupported=f"schema {schema!r}",
            supported=SCHEMA_COMPATIBILITY_HALT,
            next_action="upgrade the consuming runtime or regenerate from a conforming producer",
        )
    for key in ("code", "unsupported", "supported", "next_action"):
        _require(obj, key, str, where="halt")
    return cast(dict[str, Any], obj)


def _halt_schema_kind(what: str) -> NoReturn:
    raise CompatibilityHaltError(
        "schema-field-type",
        unsupported=f"a {what} that is not a JSON object",
        supported=f"a JSON object holding the {what}",
        next_action="regenerate the document from a conforming producer",
    )


# ---------------------------------------------------------------------------
# R8 — canonical cross-clone reconstruction (read-only, deterministic)
# ---------------------------------------------------------------------------


def build_canonical_status(
    repo_root: Path,
    outcome_id: str,
    *,
    runner: Callable[..., Any] | None = None,
    github_runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Build the portable ``outcome.canonical-status.v1`` projection (R8, KTD1).

    Inputs are exactly the two canonical sources: the **committed** spec blob (never the
    working tree, never the git-common-dir cache) and per-node GitHub completion evidence read
    through the parent-owned contracts (``outcome_github``). The function materializes nothing:
    no store, no quarantine, no harvest — two clones given the same commit and the same GitHub
    fixture serialize byte-identically.

    Conservative evidence rules (R8): a node whose GitHub evidence reads ``unknown`` — or whose
    canonical marker is cache-resident only (an untracked non-code leaf, a child-outcome node)
    — lands in ``unknown`` and is EXCLUDED from the candidate frontier: unknown can only reduce
    apparent completion and candidacy, never fabricate either. The projection never claims
    ``ready``/``dispatched``/``running``/lease/handoff state and always carries
    ``mutation_allowed: false`` — treating the candidate frontier as dispatchable is a HALT
    violation on the consumer side.
    """
    import outcome_spec

    identity = repository_identity(repo_root, runner=runner)
    binding = resolve_committed_spec(repo_root, outcome_id, runner=runner)
    try:
        spec = outcome_spec.OutcomeSpec.from_dict(binding["spec"])
        spec.validate()
    except Exception:
        raise CompatibilityHaltError(
            "discovery-spec-invalid",
            unsupported="a committed spec the canonical spec layer rejects",
            supported="a committed spec passing outcome_spec validation",
            next_action="repair the committed spec on the outcome branch, then re-run discover",
        ) from None

    completed: list[str] = []
    unknown: list[str] = []
    rows: list[dict[str, str]] = []
    for node in spec.nodes:
        contract, state, evidence = _canonical_node_completion(node, github_runner=github_runner)
        rows.append(
            {
                "subplot_id": node.subplot_id,
                "contract": contract,
                "canonical_state": state,
                "evidence_digest": hashlib.sha256(
                    canonical_json(evidence).encode("utf-8")
                ).hexdigest(),
            }
        )
        if state == "complete":
            completed.append(node.subplot_id)
        elif state == "unknown":
            unknown.append(node.subplot_id)

    frontier = [
        sid for sid in outcome_spec.ready_frontier(spec, set(completed)) if sid not in set(unknown)
    ]
    status = {
        "schema": SCHEMA_CANONICAL_STATUS,
        "repository_identity": identity,
        "outcome_id": outcome_id,
        "committed": {
            "commit_oid": binding["commit_oid"],
            "blob_oid": binding["blob_oid"],
            "sha256": binding["sha256"],
        },
        "completed": sorted(completed),
        "candidate_frontier": sorted(frontier),
        "unknown": sorted(unknown),
        "node_completion": sorted(rows, key=lambda r: r["subplot_id"]),
        "mutation_allowed": False,
    }
    return validate_canonical_status(status)


def _canonical_node_completion(
    node: Any, *, github_runner: Callable[..., Any] | None
) -> tuple[str, str, dict[str, str]]:
    """One node's (contract, canonical_state, evidence) from GitHub-canonical sources only."""
    import outcome_github  # lazy sibling import (house pattern)

    if getattr(node, "is_outcome", False):
        # A child-outcome node's terminal state lives in the child's own spec/store — not
        # GitHub-canonical from here. Unknown, never fabricated (R8).
        return (
            "child-outcome:terminal-success",
            "unknown",
            {"child_spec_ref": str(node.child_spec_ref)},
        )
    if node.kind == "code":
        pr = str(node.github.get("pr", ""))
        if not pr:
            return ("code:pr-merged", "open", {"pr": ""})
        state = outcome_github.pr_state(pr, runner=github_runner)
        canonical = (
            "complete" if state == "merged" else ("unknown" if state == "unknown" else "open")
        )
        return ("code:pr-merged", canonical, {"pr": pr, "pr_state": state})
    issue = str(node.github.get("issue", ""))
    if issue:
        state = outcome_github.issue_state(issue, runner=github_runner)
        canonical = (
            "complete" if state == "closed" else ("unknown" if state == "unknown" else "open")
        )
        return ("non-code:issue-closed", canonical, {"issue": issue, "issue_state": state})
    # Untracked non-code leaf: its only marker is cache-resident (store-local) — invisible to a
    # cross-clone reader, so it stays unknown rather than claiming open-or-complete (R8).
    return ("non-code:tick+canonical-marker", "unknown", {"issue": ""})
