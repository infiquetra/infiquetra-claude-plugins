#!/usr/bin/env python3
"""promote_scan.py — the deterministic backbone of the saga ``promote`` skill.

The transcendent-learnings layer promotes the *select few* learnings that cross
repositories into ``infiquetra-context-library``'s engineering journal as
distilled, pull-only org standards. ``promote`` has two halves: this script does
the mechanical work, and ``skills/promote/SKILL.md`` does the judgment
(near-duplicate clustering, distillation, the gated upsert).

This module implements the READ backbone (U3) and the WRITE helpers (U4), all
quoting the frozen contract at
``skills/promote/references/promotion-contract.md`` — there is no second
definition of the marker, the key recipe, or the entry template anywhere.

READ backbone (U3):
  * enumerate ``*/docs/engineering-journal/LEARNINGS.md`` under the workspace root;
  * parse the ``**Transcendent.**`` marker (contract §1) and every legacy
    ``**Generalizable rule.**`` line across its surface variants (§3);
  * compute the drift-stable ``<repo>:<hash>`` source key (§2);
  * read ``infiquetra-context-library``'s ``<!-- promote-keys: ... -->`` ledger
    and drop already-promoted candidates (§5);
  * exclude context-library from the candidate pool (self-feed layer 1, §5.2)
    and skip any entry carrying a ``promote-keys`` comment (backstop, layer 2);
  * group exact-recurrence clusters (same normalized rule in >= threshold
    distinct repos) — the deterministic floor under SKILL.md's judgment clustering.

Usage:
  python3 promote_scan.py scan [--workspace-root PATH] [--threshold N]
      [--context-library NAME] [--json]
  python3 promote_scan.py key --repo REPO --rule 'the rule text'

Output (``scan``) is ``json.dumps`` of the candidate pool, the declared-marker
list, and the exact-recurrence clusters — data only; the orchestrator does the
judgment and the gated write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- contract-frozen constants (promotion-contract.md) ---------------------

#: Workspace root that holds the per-repo clones (mirrors /ideate's discovery).
DEFAULT_WORKSPACE_ROOT = Path.home() / "workspace" / "infiquetra"
#: The promotion destination; excluded from the candidate pool (§5.2 layer 1).
DEFAULT_CONTEXT_LIBRARY = "infiquetra-context-library"
#: Per-repo journal path enumerated under the workspace root.
JOURNAL_RELPATH = "docs/engineering-journal/LEARNINGS.md"
#: A recurrence cluster is nominated at >= this many distinct repos (§ KTD4, R5).
DEFAULT_THRESHOLD = 2

#: §1 detection anchor for the transcendence marker (line start, no prefix).
TRANSCENDENT_RE = re.compile(r"^\*\*Transcendent\b")
#: §1 — capture the optional one-line reason after the marker label.
TRANSCENDENT_REASON_RE = re.compile(r"^\*\*Transcendent\.\*\*\s*(.*)$")
#: §3 match pattern — every legacy ``**Generalizable rule.**`` surface variant,
#: capturing the inline rule text (group 1) that follows the label.
RULE_LINE_RE = re.compile(
    r"^\s*>?\s*[-*]?\s*\*\*Generalizable rules?(?:\s*\([^)]*\))?[.:]?\*\*\s*(.*)$"
)
#: §2 step 2 — the rule label in any legacy form (defensive strip during normalize).
LABEL_STRIP_RE = re.compile(r"\*\*Generalizable rules?(?:\s*\([^)]*\))?[.:]?\*\*")
#: §2 step 1 — a leading blockquote / list bullet + surrounding whitespace.
LEADING_PREFIX_RE = re.compile(r"^\s*>?\s*[-*]?\s*")
#: §4/§5 — the drift-stable idempotency ledger carried by each promoted entry.
PROMOTE_KEYS_RE = re.compile(r"<!--\s*promote-keys:\s*(.*?)\s*-->")
#: Entry-block boundary inside a LEARNINGS.md (``### Title`` / ``## DATE``).
ENTRY_HEADER_RE = re.compile(r"^(?:##|###)\s")


# --- §2: the drift-stable source key ---------------------------------------


def normalize_rule(rule_text: str) -> str:
    """Normalize an inline rule (the text AFTER the label) per contract §2.

    Input is ``rule_text`` — the marker line's content after the
    ``**Generalizable rule.**`` label, as :func:`parse_journal` extracts it.
    The label/prefix strips (steps 1-2) are defensive no-ops on already-clean
    input; they matter only when a caller passes a less-trimmed fragment.
    """
    s = LEADING_PREFIX_RE.sub("", rule_text)  # 1. strip blockquote/bullet/ws
    s = LABEL_STRIP_RE.sub("", s)  # 2. strip the rule label in any legacy form
    s = re.sub(r"[*`_]", "", s)  # 3. strip markdown emphasis characters
    s = s.lower()  # 4. lowercase
    s = re.sub(r"\s+", " ", s).strip()  # 5. collapse whitespace runs; trim
    s = s.rstrip(".;:,")  # 6. strip trailing punctuation
    return s


def rule_hash(rule_text: str) -> str:
    """The ``sha256(normalized)[:12]`` half of the source key (§2)."""
    normalized = normalize_rule(rule_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def source_key(repo_dirname: str, rule_text: str) -> str:
    """The full drift-stable ``<repo>:<hash>`` source key (§2).

    ``repo_dirname`` is the source repo's directory name under the workspace
    root (e.g. ``infiquetra-home-lab``) — not a path, not a remote URL.
    """
    return f"{repo_dirname}:{rule_hash(rule_text)}"


# --- parsing ----------------------------------------------------------------


@dataclass
class Candidate:
    """One ``**Generalizable rule.**`` occurrence in a source repo's journal."""

    repo: str
    path: str  # workspace-relative ``<repo>/docs/.../LEARNINGS.md``
    line: int  # 1-based line number of the rule line (for the §4 backlink)
    rule_text: str  # inline content after the label (raw, un-normalized)
    normalized: str
    hash: str
    key: str
    transcendent: bool = False  # a §1 marker sits directly below this rule
    transcendent_reason: str = ""

    @property
    def backlink(self) -> str:
        """The §4 ``repo/path:line`` provenance pointer (may drift, R9)."""
        return f"{self.path}:{self.line}"


def _entry_skip_lines(lines: list[str]) -> set[int]:
    """0-based line indices inside an entry block carrying a promote-keys comment.

    Self-feed backstop (§5.2 layer 2): a promoted entry can never be re-detected
    as a recurring source, because the skip keys off the ``promote-keys`` comment
    rather than the (deliberately familiar) ``**Generalizable rule.**`` label.
    """
    # Block boundaries: each ``###``/``##`` header starts a new block.
    starts = [i for i, ln in enumerate(lines) if ENTRY_HEADER_RE.match(ln)]
    if not starts:
        starts = [0]
    if starts[0] != 0:
        starts = [0, *starts]
    bounds = list(zip(starts, [*starts[1:], len(lines)], strict=True))
    skip: set[int] = set()
    for start, end in bounds:
        if any("promote-keys:" in lines[i] for i in range(start, end)):
            skip.update(range(start, end))
    return skip


def parse_journal(text: str, repo: str, path: str) -> list[Candidate]:
    """Extract every keyed rule candidate from one journal's text.

    Skips rule lines inside an entry carrying a ``promote-keys`` comment
    (self-feed backstop) and rule lines with no inline content (no lesson to key).
    """
    lines = text.splitlines()
    skip = _entry_skip_lines(lines)
    out: list[Candidate] = []
    for i, line in enumerate(lines):
        if i in skip:
            continue
        m = RULE_LINE_RE.match(line)
        if not m:
            continue
        rule_text = m.group(1).strip()
        if not rule_text:
            continue  # the ~7/785 markers with no inline lesson — nothing to key
        transcendent = False
        reason = ""
        if i + 1 < len(lines):
            tm = TRANSCENDENT_REASON_RE.match(lines[i + 1].strip())
            if tm:
                transcendent = True
                reason = tm.group(1).strip()
        out.append(
            Candidate(
                repo=repo,
                path=path,
                line=i + 1,
                rule_text=rule_text,
                normalized=normalize_rule(rule_text),
                hash=rule_hash(rule_text),
                key=source_key(repo, rule_text),
                transcendent=transcendent,
                transcendent_reason=reason,
            )
        )
    return out


def parse_ledger(text: str) -> set[str]:
    """Build the already-promoted key set from context-library's journal (§5).

    Greps every ``<!-- promote-keys: a:1; b:2 -->`` comment and unions the keys.
    No separate ledger file: each promoted entry carries its own receipt.
    """
    keys: set[str] = set()
    for m in PROMOTE_KEYS_RE.finditer(text):
        for raw in m.group(1).split(";"):
            k = raw.strip()
            if k:
                keys.add(k)
    return keys


# --- enumeration + scan -----------------------------------------------------


def enumerate_journals(workspace_root: Path) -> list[tuple[str, Path]]:
    """``(repo_dirname, journal_path)`` for every repo journal under the root."""
    found: list[tuple[str, Path]] = []
    for journal in sorted(workspace_root.glob(f"*/{JOURNAL_RELPATH}")):
        repo = journal.relative_to(workspace_root).parts[0]
        found.append((repo, journal))
    return found


@dataclass
class ScanResult:
    workspace_root: str
    threshold: int
    context_library: str
    repos_scanned: list[str]
    ledger_key_count: int
    candidates: list[Candidate] = field(default_factory=list)
    marked: list[Candidate] = field(default_factory=list)
    recurrence_clusters: list[dict] = field(default_factory=list)
    filtered_by_ledger: int = 0
    skipped_promoted: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        # asdict drops @property; backlinks are recomputable, keep payload lean.
        return d


def scan(
    workspace_root: Path,
    threshold: int = DEFAULT_THRESHOLD,
    context_library: str = DEFAULT_CONTEXT_LIBRARY,
) -> ScanResult:
    """Run the full read backbone over a workspace root."""
    journals = enumerate_journals(workspace_root)
    ledger: set[str] = set()
    repos_scanned: list[str] = []
    raw_candidates: list[Candidate] = []
    skipped_promoted = 0

    for repo, journal in journals:
        text = journal.read_text(encoding="utf-8")
        rel = str(journal.relative_to(workspace_root))
        if repo == context_library:
            # §5.2 layer 1: read ONLY for the ledger; never a candidate source.
            ledger |= parse_ledger(text)
            continue
        repos_scanned.append(repo)
        parsed = parse_journal(text, repo, rel)
        # backstop count: rule lines suppressed by an in-entry promote-keys comment
        skipped_promoted += _count_suppressed_rules(text)
        raw_candidates.extend(parsed)

    # §5: drop candidates whose key is already in the ledger.
    candidates = [c for c in raw_candidates if c.key not in ledger]
    filtered = len(raw_candidates) - len(candidates)

    marked = [c for c in candidates if c.transcendent]
    clusters = _recurrence_clusters(candidates, threshold)

    return ScanResult(
        workspace_root=str(workspace_root),
        threshold=threshold,
        context_library=context_library,
        repos_scanned=repos_scanned,
        ledger_key_count=len(ledger),
        candidates=candidates,
        marked=marked,
        recurrence_clusters=clusters,
        filtered_by_ledger=filtered,
        skipped_promoted=skipped_promoted,
    )


def _count_suppressed_rules(text: str) -> int:
    """How many rule lines a journal's promote-keys backstop suppressed."""
    lines = text.splitlines()
    skip = _entry_skip_lines(lines)
    return sum(1 for i in skip if RULE_LINE_RE.match(lines[i]))


def _recurrence_clusters(candidates: Iterable[Candidate], threshold: int) -> list[dict]:
    """Group exact-recurrence clusters: same normalized rule in >= threshold repos.

    This is the deterministic floor; SKILL.md additionally clusters
    near-identical wordings by judgment (KTD4). Grouping is by the content hash
    (identical wording → identical hash across repos), counting *distinct* repos.
    """
    by_hash: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        by_hash[c.hash].append(c)
    clusters: list[dict] = []
    for h, members in by_hash.items():
        repos = sorted({c.repo for c in members})
        if len(repos) < threshold:
            continue
        clusters.append(
            {
                "hash": h,
                "normalized": members[0].normalized,
                "repos": repos,
                "keys": sorted({c.key for c in members}),
                "occurrences": [
                    {"repo": c.repo, "backlink": c.backlink, "key": c.key}
                    for c in members
                ],
                "declared_transcendent": any(c.transcendent for c in members),
            }
        )
    clusters.sort(key=lambda d: (-len(d["repos"]), d["hash"]))
    return clusters


# --- §4/§5: the gated upsert (write half, U4) ------------------------------

#: §4 — the promoted entry's `**Sources.**` line.
SOURCES_RE = re.compile(r"^\*\*Sources\.\*\*\s*(.*)$")
#: First dated section header — the newest-first insertion anchor.
DATE_HEADER_RE = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\b")
#: The canonical destination journal (R10 write-surface guard).
CONTEXT_LIBRARY_JOURNAL = JOURNAL_RELPATH


@dataclass
class Origin:
    """One source occurrence feeding a promoted entry: a backlink + its key."""

    backlink: str  # §4 `repo/path:line` provenance pointer (may drift, R9)
    key: str  # §2 drift-stable `repo:hash` idempotency key


@dataclass
class Promotion:
    """A distilled cluster ready to upsert (the agent supplies rule/mechanism)."""

    date: str
    title: str
    rule: str
    mechanism: str
    origins: list[Origin]

    @property
    def keys(self) -> list[str]:
        return [o.key for o in self.origins]


def render_entry(promo: Promotion) -> str:
    """Render the contract §4 promoted-entry template (Rule + Mechanism only)."""
    sources = "; ".join(o.backlink for o in promo.origins)
    keys = "; ".join(o.key for o in promo.origins)
    return (
        f"## {promo.date}\n\n"
        f"### {promo.title}\n\n"
        f"**Author.** promote (saga)\n"
        f"**Generalizable rule.** {promo.rule}\n"
        f"**Mechanism.** {promo.mechanism}\n"
        f"**Sources.** {sources}\n"
        f"<!-- promote-keys: {keys} -->\n"
    )


@dataclass
class _PromotedEntry:
    keys: set[str]
    keys_line: int  # index of the `<!-- promote-keys: ... -->` line
    sources_line: int  # index of the `**Sources.**` line (or -1)


def _promoted_entries(lines: list[str]) -> list[_PromotedEntry]:
    """Index existing context-library entries by their promote-keys + line refs."""
    starts = [i for i, ln in enumerate(lines) if re.match(r"^###\s", ln)]
    if not starts:
        return []
    bounds = list(zip(starts, [*starts[1:], len(lines)], strict=True))
    entries: list[_PromotedEntry] = []
    for start, end in bounds:
        keys: set[str] = set()
        keys_line = -1
        sources_line = -1
        for i in range(start, end):
            km = PROMOTE_KEYS_RE.search(lines[i])
            if km:
                keys_line = i
                keys |= {k.strip() for k in km.group(1).split(";") if k.strip()}
            if SOURCES_RE.match(lines[i]):
                sources_line = i
        if keys_line != -1:
            entries.append(_PromotedEntry(keys, keys_line, sources_line))
    return entries


def compute_upsert(journal_text: str, promo: Promotion) -> dict:
    """Compute (purely, no I/O) the upsert for ``promo`` against the journal.

    Returns ``{action, new_text, added_keys, ...}`` — the proposed change only;
    the gated WRITE is the caller's (the SKILL's) approved action. This purity
    *is* AE5: a nomination produces a proposed diff and changes nothing on disk
    until approval.

    - ``noop``   — every origin key already present (§5 idempotency, AE1).
    - ``update`` — an existing entry shares >=1 key; add the new origins'
      backlinks + keys, no new entry (§5 upsert, AE3 third-repo case).
    - ``create`` — no key overlap; prepend a new newest-first entry.
    """
    lines = journal_text.splitlines()
    entries = _promoted_entries(lines)
    origin_keys = set(promo.keys)

    match = next((e for e in entries if e.keys & origin_keys), None)
    if match is not None:
        new_origins = [o for o in promo.origins if o.key not in match.keys]
        if not new_origins:
            return {"action": "noop", "new_text": journal_text, "added_keys": []}
        out = list(lines)
        if match.sources_line != -1:
            out[match.sources_line] = (
                out[match.sources_line].rstrip()
                + "; "
                + "; ".join(o.backlink for o in new_origins)
            )
        km = PROMOTE_KEYS_RE.search(out[match.keys_line])
        existing = [k.strip() for k in km.group(1).split(";") if k.strip()]
        merged = existing + [o.key for o in new_origins]
        out[match.keys_line] = f"<!-- promote-keys: {'; '.join(merged)} -->"
        return {
            "action": "update",
            "new_text": "\n".join(out) + ("\n" if journal_text.endswith("\n") else ""),
            "added_keys": [o.key for o in new_origins],
        }

    # create: insert a new entry newest-first (before the first dated header).
    entry = render_entry(promo)
    insert_at = next((i for i, ln in enumerate(lines) if DATE_HEADER_RE.match(ln)), None)
    if insert_at is None:
        body = journal_text.rstrip("\n") + "\n\n" + entry
    else:
        head = "\n".join(lines[:insert_at]).rstrip("\n")
        tail = "\n".join(lines[insert_at:])
        body = f"{head}\n\n{entry}\n{tail}".rstrip("\n") + "\n"
    return {"action": "create", "new_text": body, "added_keys": list(promo.keys)}


def context_library_journal(workspace_root: Path, context_library: str) -> Path:
    """The one path the pass may write (R10)."""
    return workspace_root / context_library / CONTEXT_LIBRARY_JOURNAL


def assert_write_target(path: Path, workspace_root: Path, context_library: str) -> None:
    """Refuse any write outside context-library's journal (R10 write-surface guard)."""
    allowed = context_library_journal(workspace_root, context_library).resolve()
    if path.resolve() != allowed:
        raise ValueError(
            f"refusing to write outside the context-library journal: {path} "
            f"(only {allowed} is writable)"
        )


def write_promotion(
    path: Path, new_text: str, workspace_root: Path, context_library: str = DEFAULT_CONTEXT_LIBRARY
) -> None:
    """Write an approved upsert, enforcing the write-surface guard first."""
    assert_write_target(path, workspace_root, context_library)
    path.write_text(new_text, encoding="utf-8")


# --- CLI --------------------------------------------------------------------


def _candidate_payload(c: Candidate) -> dict:
    d = asdict(c)
    d["backlink"] = c.backlink
    return d


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sc = sub.add_parser("scan", help="scan the workspace for promotion candidates")
    sc.add_argument(
        "--workspace-root",
        default=str(DEFAULT_WORKSPACE_ROOT),
        help="Root holding the per-repo clones (default ~/workspace/infiquetra)",
    )
    sc.add_argument(
        "--threshold", type=int, default=DEFAULT_THRESHOLD,
        help="Distinct-repo count to nominate a recurrence cluster (default 2)",
    )
    sc.add_argument(
        "--context-library", default=DEFAULT_CONTEXT_LIBRARY,
        help="Repo dir excluded from candidates; read only for the ledger",
    )
    sc.add_argument("--json", action="store_true", help="Emit full JSON payload")

    kc = sub.add_parser("key", help="compute the §2 source key for one rule")
    kc.add_argument("--repo", required=True, help="Source repo directory name")
    kc.add_argument("--rule", required=True, help="The rule text (inline content)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "key":
        print(source_key(args.repo, args.rule))
        return 0

    root = Path(args.workspace_root).expanduser()
    if not root.is_dir():
        print(f"workspace root not found: {root}", file=sys.stderr)
        return 2
    result = scan(root, threshold=args.threshold, context_library=args.context_library)

    if args.json:
        payload = result.to_dict()
        payload["candidates"] = [_candidate_payload(c) for c in result.candidates]
        payload["marked"] = [_candidate_payload(c) for c in result.marked]
        print(json.dumps(payload, indent=2))
        return 0

    # human summary
    print(f"workspace: {result.workspace_root}")
    print(f"repos scanned: {len(result.repos_scanned)} (context-library excluded)")
    print(f"already-promoted keys in ledger: {result.ledger_key_count}")
    print(f"candidates: {len(result.candidates)} "
          f"(filtered by ledger: {result.filtered_by_ledger}, "
          f"backstop-skipped: {result.skipped_promoted})")
    print(f"declared transcendent: {len(result.marked)}")
    print(f"recurrence clusters (>= {result.threshold} repos): "
          f"{len(result.recurrence_clusters)}")
    for cl in result.recurrence_clusters:
        flag = " [declared]" if cl["declared_transcendent"] else ""
        print(f"  - {cl['hash']} x{len(cl['repos'])}{flag}: {cl['normalized'][:80]}")
        for occ in cl["occurrences"]:
            print(f"      {occ['backlink']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
