#!/usr/bin/env python3
"""
Marketplace Lister CLI for Claude Code
Manages iCloud inbox photos for Facebook Marketplace listing generation.

Commands:
  init         Create Marketplace/{inbox,unidentified} dirs in iCloud Drive
  scan         List inbox subdirectories with photo counts → JSON
  photos       List image files in folder → JSON array of paths
  organize     Move folder to Marketplace/YYYY-MM-DD-<slug>/
  unidentified Move folder to Marketplace/unidentified/
  listing      Write listing.md from structured JSON (read from stdin)
  status       List all organized items with listing status
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

ICLOUD_BASE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
MARKETPLACE_BASE = ICLOUD_BASE / "Marketplace"
INBOX = MARKETPLACE_BASE / "inbox"
UNIDENTIFIED = MARKETPLACE_BASE / "unidentified"
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _success(data: dict) -> None:
    print(json.dumps(data, indent=2))


def _error(message: str) -> None:
    print(json.dumps({"error": message}))
    sys.exit(1)


def _photos_in(folder: Path) -> list[Path]:
    return [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in PHOTO_EXTS]


def _dated_slug(name: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    slug = name.lower().strip().replace(" ", "-")
    return f"{today}-{slug}"


def _resolve_path(path_str: str) -> Path:
    """Resolve a path — either absolute or relative to inbox."""
    p = Path(path_str)
    if p.is_absolute():
        if not p.exists():
            _error(f"Path not found: {path_str}")
        return p
    # Try as inbox subfolder name
    inbox_path = INBOX / path_str
    if inbox_path.exists():
        return inbox_path
    _error(f"Path not found: {path_str} (tried absolute and inbox-relative)")
    raise SystemExit(1)  # unreachable but satisfies type checker


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(_args: list[str]) -> None:
    """Create Marketplace directory structure in iCloud."""
    if not ICLOUD_BASE.exists():
        _error("iCloud Drive not found. Ensure iCloud Drive is enabled in System Settings.")
        return
    created = []
    for d in [MARKETPLACE_BASE, INBOX, UNIDENTIFIED]:
        if not d.exists():
            d.mkdir(parents=True)
            created.append(str(d))
    _success({
        "success": True,
        "created": created,
        "inbox": str(INBOX),
        "unidentified": str(UNIDENTIFIED),
        "message": "Marketplace directories ready." if created else "Already initialized.",
    })


def cmd_scan(args: list[str]) -> None:
    """List inbox subfolders with photo counts."""
    scan_path = Path(args[args.index("--path") + 1]) if "--path" in args else INBOX
    if not scan_path.exists():
        _error(f"Directory not found: {scan_path}. Run: marketplace_client.py init")
        return
    folders = []
    for item in sorted(scan_path.iterdir()):
        if item.is_dir():
            photos = _photos_in(item)
            folders.append({
                "folder": item.name,
                "path": str(item),
                "photo_count": len(photos),
                "photos": [p.name for p in sorted(photos)],
            })
    _success({"folders": folders, "count": len(folders), "path": str(scan_path)})


def cmd_photos(args: list[str]) -> None:
    """List absolute photo paths in a folder."""
    if not args:
        _error("Usage: marketplace_client.py photos --folder <path>")
        return
    folder_arg = args[args.index("--folder") + 1] if "--folder" in args else args[0]
    folder = _resolve_path(folder_arg)
    photos = sorted(_photos_in(folder))
    _success({"photos": [str(p) for p in photos], "count": len(photos), "folder": str(folder)})


def cmd_organize(args: list[str]) -> None:
    """Move folder to Marketplace/YYYY-MM-DD-<name>/."""
    if "--source" not in args or "--name" not in args:
        _error("Usage: marketplace_client.py organize --source <path> --name <slug>")
        return
    src_arg = args[args.index("--source") + 1]
    name = args[args.index("--name") + 1]
    src = _resolve_path(src_arg)
    dest_name = _dated_slug(name)
    dest = MARKETPLACE_BASE / dest_name
    if dest.exists():
        _error(f"Destination already exists: {dest}")
        return
    src.rename(dest)
    _success({
        "success": True,
        "from": str(src),
        "to": str(dest),
        "folder": dest_name,
    })


def cmd_unidentified(args: list[str]) -> None:
    """Move folder to Marketplace/unidentified/<timestamp>/."""
    if "--source" not in args and not args:
        _error("Usage: marketplace_client.py unidentified --source <path>")
        return
    src_arg = args[args.index("--source") + 1] if "--source" in args else args[0]
    src = _resolve_path(src_arg)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    dest = UNIDENTIFIED / f"{timestamp}-{src.name}"
    UNIDENTIFIED.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    _success({"success": True, "from": str(src), "to": str(dest)})


def cmd_listing(args: list[str]) -> None:
    """Read listing JSON from stdin, write listing.md to the specified folder."""
    folder_arg = args[args.index("--folder") + 1] if "--folder" in args else (args[0] if args else None)
    if not folder_arg:
        _error("Usage: marketplace_client.py listing --folder <path>  (pipe JSON via stdin)")
        return
    folder = Path(folder_arg)
    if not folder.exists():
        _error(f"Folder not found: {folder}")
        return

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        _error(f"Invalid JSON from stdin: {e}")
        return

    pricing = data.get("pricing", {})
    strategy = data.get("strategy", [])
    coaching = data.get("photo_coaching", [])
    specs = data.get("specs", {})

    lines = [
        f"# {data.get('title', 'Untitled Item')}",
        "",
        f"**Category:** {data.get('category', '')}  ",
        f"**Condition:** {data.get('condition', '')}  ",
        f"**Location:** {data.get('location', 'Indianapolis, IN')}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Facebook Marketplace Listing",
        "",
        "```",
        f"TITLE: {data.get('title', '')}",
        f"PRICE: ${pricing.get('fair_market', '—')}",
        f"CATEGORY: {data.get('category', '')}",
        f"CONDITION: {data.get('condition', '')}",
        f"LOCATION: {data.get('location', 'Indianapolis, IN')}",
        "",
        "DESCRIPTION:",
        data.get("description", ""),
        "```",
        "",
        "---",
        "",
        "## Description",
        "",
        data.get("description", ""),
        "",
    ]

    if specs:
        lines += ["## Specifications", ""]
        for k, v in specs.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

    if pricing:
        lines += [
            "## Pricing Strategy",
            "",
            "| Tier | Price | Notes |",
            "|------|-------|-------|",
            f"| Quick Sale | ${pricing.get('quick_sale', '—')} | Sell in 1-2 days |",
            f"| Fair Market | ${pricing.get('fair_market', '—')} | Recommended start |",
            f"| Above Market | ${pricing.get('above_market', '—')} | Patient seller |",
            f"| Maximum Realistic | ${pricing.get('maximum', '—')} | Perfect condition |",
            "",
        ]
        if pricing.get("reasoning"):
            lines += [f"**Pricing Basis:** {pricing['reasoning']}", ""]

    if strategy:
        lines += ["## Sales Strategy", ""]
        for tip in strategy:
            lines.append(f"- {tip}")
        lines.append("")

    if coaching:
        lines += ["## Photo Coaching", ""]
        for tip in coaching:
            lines.append(f"- {tip}")
        lines.append("")

    listing_path = folder / "listing.md"
    listing_path.write_text("\n".join(lines))
    _success({
        "success": True,
        "path": str(listing_path),
        "title": data.get("title"),
    })


def cmd_status(_args: list[str]) -> None:
    """List all organized item folders (excludes inbox and unidentified)."""
    if not MARKETPLACE_BASE.exists():
        _error("Marketplace not initialized. Run: marketplace_client.py init")
        return
    items = []
    for item in sorted(MARKETPLACE_BASE.iterdir()):
        if item.is_dir() and item.name not in ("inbox", "unidentified"):
            listing = item / "listing.md"
            photos = _photos_in(item)
            items.append({
                "folder": item.name,
                "path": str(item),
                "has_listing": listing.exists(),
                "photo_count": len(photos),
            })
    _success({"items": items, "count": len(items)})


# ── Dispatch ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "init": cmd_init,
    "scan": cmd_scan,
    "photos": cmd_photos,
    "organize": cmd_organize,
    "unidentified": cmd_unidentified,
    "listing": cmd_listing,
    "status": cmd_status,
}


def main() -> None:
    if len(sys.argv) < 2:
        _error(f"Usage: marketplace_client.py <command> [args...]\nCommands: {', '.join(COMMANDS)}")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in COMMANDS:
        _error(f"Unknown command: {command}. Available: {', '.join(COMMANDS)}")
        return

    try:
        COMMANDS[command](args)
    except SystemExit:
        raise
    except Exception as e:
        _error(str(e))


if __name__ == "__main__":
    main()
