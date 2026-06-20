"""Tests for ``promote_scan.py`` — the deterministic backbone of saga ``promote``.

Every assertion traces to the frozen contract at
``plugins/saga/skills/promote/references/promotion-contract.md``:

* the §2 source-key recipe (golden vectors ``87c4c366deb7`` / ``821928016ab6``)
  and its drift proof (a line-number shift must not change the hash);
* the §3 legacy ``**Generalizable rule.**`` variant coverage (and the prose
  non-matches);
* the §1 ``**Transcendent.**`` marker detection;
* enumeration across repos, the context-library exclusion (self-feed layer 1),
  the ledger filter (§5 idempotency), and the promote-keys backstop (layer 2);
* the recurrence threshold (1 repo below, 2 repos nominated — AE2).

Unit assertions import the module directly; the end-to-end scan also runs through
the real CLI via ``subprocess`` so the JSON payload contract is exercised whole.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "promote_scan.py"
SKILL = ROOT / "plugins" / "saga" / "skills" / "promote" / "SKILL.md"
CONTRACT = (
    ROOT / "plugins" / "saga" / "skills" / "promote" / "references" / "promotion-contract.md"
)

_spec = importlib.util.spec_from_file_location("promote_scan", SCRIPT)
assert _spec and _spec.loader
promote_scan = importlib.util.module_from_spec(_spec)
# Register before exec so dataclass field resolution can find the module (3.12+).
sys.modules["promote_scan"] = promote_scan
_spec.loader.exec_module(promote_scan)


# --- fixtures ---------------------------------------------------------------

JOURNAL_REL = "docs/engineering-journal/LEARNINGS.md"


def _write_journal(workspace: Path, repo: str, body: str) -> Path:
    path = workspace / repo / JOURNAL_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _entry(rule: str, transcendent: str | None = None) -> str:
    """A minimal LEARNINGS entry carrying one Generalizable rule line."""
    lines = [
        "## 2026-06-20",
        "",
        "### Some lesson  {#some-lesson}",
        "",
        "**Context.** A thing happened.",
        f"**Generalizable rule.** {rule}",
    ]
    if transcendent is not None:
        lines.append(f"**Transcendent.** {transcendent}")
    lines.append("**Refs.** none.")
    lines.append("")
    return "\n".join(lines)


# --- §2: source key + golden vectors ---------------------------------------


def test_golden_vectors():
    """The §2 recipe reproduces the contract's real sha256[:12] oracle values."""
    assert (
        promote_scan.rule_hash(
            "A verification gate that is named but not executed is not a gate."
        )
        == "87c4c366deb7"
    )
    assert (
        promote_scan.rule_hash(
            "A monitoring check that is configured but never scraped is not monitoring."
        )
        == "821928016ab6"
    )


def test_source_key_format():
    """key := f'{repo}:{hash}' (§2) — repo dirname prefix, not a path."""
    key = promote_scan.source_key(
        "infiquetra-home-lab",
        "A verification gate that is named but not executed is not a gate.",
    )
    assert key == "infiquetra-home-lab:87c4c366deb7"


def test_normalization_is_emphasis_and_case_insensitive():
    """Re-bolding / casing / trailing punct are cosmetic — same identity (§2)."""
    a = promote_scan.rule_hash("A verification gate that is named but not executed is not a gate.")
    b = promote_scan.rule_hash("A *verification* gate that is NAMED but not executed is not a gate")
    c = promote_scan.rule_hash("  a verification gate that is named but not executed is not a gate;")
    assert a == b == c


def test_key_stable_under_line_shift(tmp_path):
    """Drift proof (§2): the same rule at a different line keeps the same key."""
    rule = "A verification gate that is named but not executed is not a gate."
    early = _write_journal(tmp_path, "repo-a", _entry(rule))
    # same rule, pushed far down by padding — different line number, same text
    padded = ("\n".join("<!-- pad -->" for _ in range(40))) + "\n" + _entry(rule)
    late = _write_journal(tmp_path, "repo-b", padded)

    ca = promote_scan.parse_journal(early.read_text(), "repo-a", "repo-a/" + JOURNAL_REL)
    cb = promote_scan.parse_journal(late.read_text(), "repo-b", "repo-b/" + JOURNAL_REL)
    assert len(ca) == 1 and len(cb) == 1
    assert ca[0].line != cb[0].line  # the line numbers genuinely differ
    assert ca[0].hash == cb[0].hash == "87c4c366deb7"  # ... but the hash does not


# --- §3: legacy marker variant coverage ------------------------------------


def test_all_legacy_variants_parse():
    """Every §3 surface form matches and yields the inline rule text."""
    variants = [
        "**Generalizable rule.** canonical form here.",
        "> **Generalizable rule.** blockquote-prefixed form here.",
        "- **Generalizable rule:** list bullet plus colon form here.",
        "**Generalizable rule:** colon-terminated form here.",
        "**Generalizable rule** no trailing period form here.",
        "**Generalizable rules.** plural form here.",
        "**Generalizable rule (revised).** parenthetical qualifier form here.",
    ]
    for line in variants:
        m = promote_scan.RULE_LINE_RE.match(line)
        assert m is not None, f"variant did not parse: {line!r}"
        assert m.group(1).strip().endswith("form here."), line


def test_prose_mentions_do_not_match():
    """§3 MUST NOT match lowercase mid-sentence prose lacking line-start bold."""
    non_markers = [
        "the generalizable rule is to test early.",
        "and generalizable rules. accumulate over time.",
        "We follow a **generalizable** principle here.",
    ]
    for line in non_markers:
        assert promote_scan.RULE_LINE_RE.match(line) is None, line


def test_parenthetical_label_is_stripped_from_identity():
    """A parenthetical qualifier in the label is part of the label, not the rule."""
    h_plain = promote_scan.rule_hash("the same exact lesson text")
    cands = promote_scan.parse_journal(
        _entry_with_raw_rule("**Generalizable rule (refined).** the same exact lesson text."),
        "r",
        "r/" + JOURNAL_REL,
    )
    assert len(cands) == 1
    assert cands[0].hash == h_plain


def _entry_with_raw_rule(rule_line: str) -> str:
    return "## 2026-06-20\n\n### T  {#t}\n\n**Context.** x.\n" + rule_line + "\n**Refs.** none.\n"


# --- §1: transcendence marker ----------------------------------------------


def test_transcendent_marker_detected_and_reason_captured():
    body = _entry("a rule that crosses repos here.", transcendent="holds in any stack.")
    cands = promote_scan.parse_journal(body, "repo-a", "repo-a/" + JOURNAL_REL)
    assert len(cands) == 1
    assert cands[0].transcendent is True
    assert cands[0].transcendent_reason == "holds in any stack."


def test_unmarked_rule_is_not_transcendent():
    cands = promote_scan.parse_journal(_entry("a plain rule here."), "r", "r/" + JOURNAL_REL)
    assert cands[0].transcendent is False
    assert cands[0].transcendent_reason == ""


# --- enumeration, exclusion, ledger, backstop, threshold -------------------


def test_enumerate_finds_all_repo_journals(tmp_path):
    for repo in ("repo-a", "repo-b", "infiquetra-context-library"):
        _write_journal(tmp_path, repo, _entry("a rule here."))
    found = dict(promote_scan.enumerate_journals(tmp_path))
    assert set(found) == {"repo-a", "repo-b", "infiquetra-context-library"}


def test_context_library_excluded_from_candidates(tmp_path):
    """Self-feed layer 1 (§5.2): context-library is never a candidate source."""
    _write_journal(tmp_path, "repo-a", _entry("a real lesson worth promoting here."))
    _write_journal(
        tmp_path,
        "infiquetra-context-library",
        _entry("a library-native lesson that must not recurse."),
    )
    result = promote_scan.scan(tmp_path)
    assert "infiquetra-context-library" not in result.repos_scanned
    assert all(c.repo != "infiquetra-context-library" for c in result.candidates)


def test_ledger_filters_already_promoted_keys(tmp_path):
    """§5 idempotency: a candidate whose key is in the ledger is dropped."""
    rule = "A verification gate that is named but not executed is not a gate."
    _write_journal(tmp_path, "infiquetra-home-lab", _entry(rule))
    # context-library already carries this lesson's key in a promote-keys ledger
    promoted = (
        "## 2026-06-20\n\n### Promoted  {#p}\n\n**Author.** promote (saga)\n"
        "**Generalizable rule.** distilled form.\n"
        "**Sources.** infiquetra-home-lab/x:1\n"
        "<!-- promote-keys: infiquetra-home-lab:87c4c366deb7 -->\n"
    )
    _write_journal(tmp_path, "infiquetra-context-library", promoted)
    result = promote_scan.scan(tmp_path)
    assert result.ledger_key_count == 1
    assert result.filtered_by_ledger == 1
    assert result.candidates == []


def test_self_feed_backstop_skips_entries_with_promote_keys(tmp_path):
    """Layer 2 (§5.2): a non-context-library entry carrying promote-keys is skipped."""
    body = (
        "## 2026-06-20\n\n### Leaked promoted entry  {#leak}\n\n"
        "**Generalizable rule.** a distilled rule that leaked into a normal repo.\n"
        "<!-- promote-keys: somerepo:deadbeefcafe -->\n"
    )
    _write_journal(tmp_path, "repo-a", body)
    result = promote_scan.scan(tmp_path)
    assert result.candidates == []
    assert result.skipped_promoted == 1


def test_recurrence_threshold(tmp_path):
    """AE2: a lesson in 1 repo is below threshold; in 2 repos it is nominated."""
    rule = "A verification gate that is named but not executed is not a gate."
    other = "A wholly different lesson that appears in only one repo here."
    _write_journal(tmp_path, "repo-a", _entry(rule) + "\n" + _entry(other))
    _write_journal(tmp_path, "repo-b", _entry(rule))

    result = promote_scan.scan(tmp_path, threshold=2)
    cluster_hashes = {c["hash"] for c in result.recurrence_clusters}
    assert "87c4c366deb7" in cluster_hashes  # in 2 repos → nominated
    solo_hash = promote_scan.rule_hash(other)
    assert solo_hash not in cluster_hashes  # in 1 repo → below threshold

    cluster = next(c for c in result.recurrence_clusters if c["hash"] == "87c4c366deb7")
    assert sorted(cluster["repos"]) == ["repo-a", "repo-b"]
    assert len(cluster["keys"]) == 2  # one per-repo key (different prefixes)


def test_recurrence_cluster_distinct_repos_not_duplicate_lines(tmp_path):
    """Two occurrences in the SAME repo do not satisfy the >=2 distinct-repo bar."""
    rule = "A verification gate that is named but not executed is not a gate."
    _write_journal(tmp_path, "repo-a", _entry(rule) + "\n" + _entry(rule))
    result = promote_scan.scan(tmp_path, threshold=2)
    assert result.recurrence_clusters == []  # same repo twice ≠ cross-repo recurrence


# --- end-to-end CLI ---------------------------------------------------------


def test_scan_cli_json_payload(tmp_path):
    """The real CLI emits the whole JSON payload contract."""
    rule = "A verification gate that is named but not executed is not a gate."
    _write_journal(tmp_path, "repo-a", _entry(rule, transcendent="holds anywhere."))
    _write_journal(tmp_path, "repo-b", _entry(rule))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "scan", "--workspace-root", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert sorted(payload["repos_scanned"]) == ["repo-a", "repo-b"]
    assert len(payload["recurrence_clusters"]) == 1
    assert payload["recurrence_clusters"][0]["declared_transcendent"] is True
    assert len(payload["marked"]) == 1
    assert payload["marked"][0]["transcendent_reason"] == "holds anywhere."
    # candidate payloads carry the §4 backlink
    assert all(":" in c["backlink"] for c in payload["candidates"])


def test_scan_cli_human_summary(tmp_path):
    """The default (non-JSON) CLI prints a readable nomination summary."""
    rule = "A verification gate that is named but not executed is not a gate."
    _write_journal(tmp_path, "repo-a", _entry(rule))
    _write_journal(tmp_path, "repo-b", _entry(rule))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "scan", "--workspace-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "repos scanned: 2" in proc.stdout
    assert "recurrence clusters (>= 2 repos): 1" in proc.stdout
    assert "87c4c366deb7" in proc.stdout


def test_scan_cli_missing_workspace_root_errors():
    """A missing workspace root exits non-zero with a clear message."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "scan", "--workspace-root", "/no/such/root/xyz"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "workspace root not found" in proc.stderr


def test_key_cli(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "key",
            "--repo",
            "infiquetra-home-lab",
            "--rule",
            "A verification gate that is named but not executed is not a gate.",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "infiquetra-home-lab:87c4c366deb7"


# --- in-process main() (coverage of the CLI dispatch + render paths) -------


def test_main_json_in_process(tmp_path, capsys):
    rule = "A verification gate that is named but not executed is not a gate."
    _write_journal(tmp_path, "repo-a", _entry(rule))
    _write_journal(tmp_path, "repo-b", _entry(rule))
    rc = promote_scan.main(["scan", "--workspace-root", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["threshold"] == 2
    assert payload["recurrence_clusters"][0]["hash"] == "87c4c366deb7"


def test_main_human_in_process(tmp_path, capsys):
    rule = "A verification gate that is named but not executed is not a gate."
    _write_journal(tmp_path, "repo-a", _entry(rule, transcendent="holds anywhere."))
    _write_journal(tmp_path, "repo-b", _entry(rule))
    rc = promote_scan.main(["scan", "--workspace-root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "declared transcendent: 1" in out
    assert "[declared]" in out  # the cluster carries a declared marker


def test_main_key_in_process(capsys):
    rc = promote_scan.main(
        ["key", "--repo", "r", "--rule", "A verification gate that is named but not executed is not a gate."]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "r:87c4c366deb7"


def test_main_missing_root_in_process():
    assert promote_scan.main(["scan", "--workspace-root", "/no/such/root/xyz"]) == 2


def test_parse_journal_without_headers():
    """A rule line outside any ###/## block still parses (no-header branch)."""
    cands = promote_scan.parse_journal(
        "**Generalizable rule.** a headerless lesson here.", "r", "r/" + JOURNAL_REL
    )
    assert len(cands) == 1
    assert cands[0].rule_text == "a headerless lesson here."


# --- SKILL.md contract (the /ideate-mirrored discovery tokens) -------------


def test_skill_mirrors_ideate_discovery():
    """U3 contract: promote/SKILL.md grounds on the /ideate cross-repo pattern."""
    assert SKILL.exists(), "promote/SKILL.md must exist"
    text = SKILL.read_text(encoding="utf-8")
    # discovery + grounding tokens mirrored from /ideate
    assert "workspace" in text.lower()
    assert "promote_scan.py" in text
    assert "infiquetra-context-library" in text
    # judgment-layer + gate tokens
    assert "propose-diff-and-wait" in text or "propose a diff" in text.lower()
    # quotes the frozen contract rather than redefining it
    assert "promotion-contract.md" in text


def test_skill_does_not_redefine_the_key_recipe():
    """Single source of truth: SKILL.md points at the contract for §2, not a copy."""
    text = SKILL.read_text(encoding="utf-8")
    # the SKILL must not embed a second sha256 recipe — that lives only in the contract
    assert "sha256" not in text.lower(), "key recipe must live only in promotion-contract.md"
