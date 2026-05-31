#!/usr/bin/env python3
"""Load prior issue, PR, checkpoint, and journal context for loop resume."""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

STATE_DIR = Path(".claude/infiquetra-lifecycle")
ROUND_RE = re.compile(r"round-(\d+)", re.IGNORECASE)


def parse_repo(value: str) -> tuple[str, str]:
    if "/" in value:
        owner, repo = value.split("/", 1)
        return owner, repo
    return "infiquetra", value


def latest_checkpoint(issue: int) -> dict[str, object] | None:
    checkpoint_dir = STATE_DIR / "checkpoints"
    if not checkpoint_dir.exists():
        return None
    matches = sorted(
        checkpoint_dir.glob(f"issue-{issue}-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return None
    latest = matches[0]
    content = latest.read_text(encoding="utf-8")
    return {
        "path": str(latest),
        "name": latest.name,
        "mtime": latest.stat().st_mtime,
        "content_preview": content[:2000],
    }


def prior_prs(owner: str, repo: str, issue: int) -> list[dict[str, object]]:
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--state",
        "all",
        "--search",
        f"in:title #{issue} round",
        "--json",
        "number,title,state,mergedAt,url,reviewDecision,body",
        "--limit",
        "50",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # nosec B603
    if result.returncode != 0:
        return []
    records: list[dict[str, object]] = []
    for pr in json.loads(result.stdout or "[]"):
        round_match = ROUND_RE.search(pr.get("title", "") or "")
        records.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "mergedAt": pr.get("mergedAt"),
                "url": pr.get("url"),
                "reviewDecision": pr.get("reviewDecision"),
                "round": int(round_match.group(1)) if round_match else None,
                "body_preview": (pr.get("body") or "")[:500],
            }
        )
    return sorted(records, key=lambda record: int(record.get("round") or 0))


def journal_entries(issue: int, adr_refs: list[str]) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = {"learnings": [], "decisions": []}
    journal_dir = Path("docs/engineering-journal")
    if not journal_dir.exists():
        return output

    refs_to_search = [f"#{issue}", *adr_refs]
    for filename, key in (("LEARNINGS.md", "learnings"), ("DECISIONS.md", "decisions")):
        path = journal_dir / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        sections = re.split(r"^## ", content, flags=re.MULTILINE)
        for section in sections[1:]:
            if any(ref in section for ref in refs_to_search):
                output[key].append(
                    {
                        "file": str(path),
                        "title": section.splitlines()[0].strip() if section else "",
                        "preview": section[:600],
                    }
                )
    return output


def adr_refs_from_text(content: str | None) -> list[str]:
    if not content:
        return []
    matches = re.findall(r"\bADR[-\s]?(\d{2,4})\b", content, flags=re.IGNORECASE)
    return [f"ADR-{int(number):04d}" for number in matches]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    owner, repo = parse_repo(args.repo)
    checkpoint = latest_checkpoint(args.issue)
    prs = prior_prs(owner, repo, args.issue)
    adrs = adr_refs_from_text(checkpoint["content_preview"] if checkpoint else None)
    rounds_seen = sorted({int(pr["round"]) for pr in prs if pr.get("round") is not None})
    print(
        json.dumps(
            {
                "repo": f"{owner}/{repo}",
                "issue": args.issue,
                "rounds_seen": rounds_seen,
                "next_round": (max(rounds_seen) + 1) if rounds_seen else 1,
                "checkpoint": checkpoint,
                "prior_prs": prs,
                "adr_refs": adrs,
                "journal": journal_entries(args.issue, adrs),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
