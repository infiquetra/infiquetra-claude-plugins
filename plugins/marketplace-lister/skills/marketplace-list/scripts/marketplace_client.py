#!/usr/bin/env python3
"""
Marketplace Lister CLI for Claude Code
Manages iCloud inbox photos for marketplace listing generation.

Commands:
  init           Create Marketplace/{inbox,unidentified} dirs in iCloud Drive
  scan           List inbox subdirectories with photo counts → JSON
  group          Group loose photos in inbox by filename sequence gaps → JSON
  create-folder  Create a named subfolder in inbox and move photos into it
  photos         List image files in folder → JSON array of paths
  organize       Move folder to Marketplace/YYYY-MM-DD-<slug>/
  unidentified   Move folder to Marketplace/unidentified/
  listing        Write listing.md + post.md from structured JSON (read from stdin)
  copy           Print title or description from post.md to stdout (pipe to pbcopy)
  status         List all organized items with listing status
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

ICLOUD_BASE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
MARKETPLACE_BASE = ICLOUD_BASE / "Marketplace"
INBOX = MARKETPLACE_BASE / "inbox"
UNIDENTIFIED = MARKETPLACE_BASE / "unidentified"
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}

# Gap threshold between IMG sequence numbers to signal a new item
GROUP_GAP_THRESHOLD = 5


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


def _extract_seq(filename: str) -> int | None:
    """Extract the first numeric sequence from a filename (e.g. IMG_2670.JPG → 2670)."""
    m = re.search(r"(\d+)", filename)
    return int(m.group(1)) if m else None


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
    """List inbox subfolders with photo counts, plus any loose photos."""
    scan_path = Path(args[args.index("--path") + 1]) if "--path" in args else INBOX
    if not scan_path.exists():
        _error(f"Directory not found: {scan_path}. Run: marketplace_client.py init")
        return
    folders = []
    loose = []
    for item in sorted(scan_path.iterdir()):
        if item.is_dir():
            photos = _photos_in(item)
            folders.append({
                "folder": item.name,
                "path": str(item),
                "photo_count": len(photos),
                "photos": [p.name for p in sorted(photos)],
            })
        elif item.is_file() and item.suffix.lower() in PHOTO_EXTS:
            loose.append(item.name)
    _success({
        "folders": folders,
        "count": len(folders),
        "path": str(scan_path),
        "loose_photos": loose,
        "loose_count": len(loose),
    })


def cmd_group(args: list[str]) -> None:
    """Scan inbox for loose photos (not in subfolders) and propose item groupings by sequence gaps."""
    scan_path = Path(args[args.index("--path") + 1]) if "--path" in args else INBOX
    if not scan_path.exists():
        _error(f"Directory not found: {scan_path}. Run: marketplace_client.py init")
        return

    # Collect only loose files (not in subfolders)
    loose_photos = sorted(
        f for f in scan_path.iterdir()
        if f.is_file() and f.suffix.lower() in PHOTO_EXTS
    )

    if not loose_photos:
        _success({
            "groups": [],
            "group_count": 0,
            "loose_count": 0,
            "message": "No loose photos found. Photos are already organized into subfolders.",
        })
        return

    # Group by gaps in filename sequence numbers
    groups: list[list[Path]] = []
    current: list[Path] = [loose_photos[0]]

    for i in range(1, len(loose_photos)):
        prev_seq = _extract_seq(loose_photos[i - 1].name)
        curr_seq = _extract_seq(loose_photos[i].name)

        if prev_seq is not None and curr_seq is not None and (curr_seq - prev_seq) >= GROUP_GAP_THRESHOLD:
            groups.append(current)
            current = [loose_photos[i]]
        else:
            current.append(loose_photos[i])

    groups.append(current)

    result_groups = [
        {
            "group_index": i,
            "photos": [p.name for p in grp],
            "photo_paths": [str(p) for p in grp],
            "count": len(grp),
        }
        for i, grp in enumerate(groups)
    ]

    _success({
        "groups": result_groups,
        "group_count": len(result_groups),
        "loose_count": len(loose_photos),
        "inbox": str(scan_path),
    })


def cmd_create_folder(args: list[str]) -> None:
    """Create a named subfolder in inbox and move specified photos into it."""
    if "--name" not in args or "--photos" not in args:
        _error("Usage: marketplace_client.py create-folder --name <slug> --photos IMG_001.JPG,IMG_002.JPG")
        return

    name = args[args.index("--name") + 1]
    photos_csv = args[args.index("--photos") + 1]
    photo_names = [p.strip() for p in photos_csv.split(",") if p.strip()]

    inbox_path = Path(args[args.index("--path") + 1]) if "--path" in args else INBOX
    dest_folder = inbox_path / name

    if dest_folder.exists():
        _error(f"Folder already exists: {dest_folder}")
        return

    dest_folder.mkdir(parents=True)

    moved = []
    missing = []
    for photo_name in photo_names:
        src = inbox_path / photo_name
        if src.exists():
            src.rename(dest_folder / photo_name)
            moved.append(photo_name)
        else:
            missing.append(photo_name)

    result: dict = {"success": True, "folder": str(dest_folder), "moved": moved, "missing": missing}
    if missing:
        result["warning"] = f"Photos not found in inbox: {', '.join(missing)}"
    _success(result)


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
    """Read listing JSON from stdin, write listing.md + post.md to the specified folder."""
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
    shipping = data.get("shipping", {})
    platforms = data.get("platforms", ["fb"])

    title = data.get("title", "")
    description = data.get("description", "")
    price = pricing.get("fair_market", "")
    mercari_title = data.get("mercari_title", title)
    mercari_description = data.get("mercari_description", description)
    mercari_price = pricing.get("mercari_price", "")
    mercari_shipping_cost = shipping.get("estimated_cost", "")

    # ── listing.md ────────────────────────────────────────────────────────────

    lines = [
        f"# {title or 'Untitled Item'}",
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
        f"TITLE: {title}",
        f"PRICE: ${price}",
        f"CATEGORY: {data.get('category', '')}",
        f"CONDITION: {data.get('condition', '')}",
        f"LOCATION: {data.get('location', 'Indianapolis, IN')}",
        "",
        "DESCRIPTION:",
        description,
        "```",
        "",
    ]

    if "mercari" in platforms:
        lines += [
            "## Mercari Listing",
            "",
            "```",
            f"TITLE: {mercari_title}",
            f"PRICE: ${mercari_price or price}",
            f"CATEGORY: {data.get('mercari_category', data.get('category', ''))}",
            f"CONDITION: {data.get('condition', '')}",
        ]
        if mercari_shipping_cost:
            lines.append(f"SHIPPING: Prepaid label — {mercari_shipping_cost}")
        lines += [
            "",
            "DESCRIPTION:",
            mercari_description,
            "```",
            "",
        ]

    lines += [
        "---",
        "",
        "## Description",
        "",
        description,
        "",
    ]

    if specs:
        lines += ["## Specifications", ""]
        for k, v in specs.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

    if shipping:
        lines += [
            "## Shipping",
            "",
            f"**Estimated Weight:** {shipping.get('estimated_weight_lbs', '—')} lbs  ",
            f"**Recommended Carrier:** {shipping.get('recommended_carrier', '—')}  ",
            f"**Estimated Cost:** {shipping.get('estimated_cost', '—')}  ",
            f"**Packaging:** {shipping.get('packaging', '—')}  ",
            f"**Ship or Local?** {shipping.get('ship_or_local', '—')}",
            "",
        ]

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
        ]
        if "mercari" in platforms and mercari_price:
            lines.append(f"| Mercari Price | ${mercari_price} | Includes 10% fee buffer |")
        lines.append("")
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

    # ── post.md ───────────────────────────────────────────────────────────────

    sep_thick = "═" * 52
    sep_thin = "─" * 60
    post_lines: list[str] = []

    if "mercari" in platforms:
        # Multi-platform format with clear section headers
        post_lines += [
            sep_thick,
            "FACEBOOK MARKETPLACE",
            sep_thick,
            f"TITLE: {title}",
            f"PRICE: ${price}",
            "",
            sep_thin,
            "DESCRIPTION:",
            sep_thin,
            "",
            description,
            "",
            sep_thick,
            "MERCARI",
            sep_thick,
            f"TITLE: {mercari_title}",
            f"PRICE: ${mercari_price or price}",
        ]
        if mercari_shipping_cost:
            post_lines.append(f"SHIPPING: Prepaid label — {mercari_shipping_cost}")
        post_lines += [
            "",
            sep_thin,
            "DESCRIPTION:",
            sep_thin,
            "",
            mercari_description,
        ]
    else:
        # Single-platform (FB only) — legacy format
        post_lines = [
            f"TITLE: {title}",
            f"PRICE: ${price}",
            "",
            sep_thin,
            "DESCRIPTION:",
            sep_thin,
            "",
            description,
        ]

    post_path = folder / "post.md"
    post_path.write_text("\n".join(post_lines))

    _success({
        "success": True,
        "path": str(listing_path),
        "post_path": str(post_path),
        "title": title,
        "platforms": platforms,
    })


def cmd_copy(args: list[str]) -> None:
    """Print title or description from post.md to stdout for piping to pbcopy."""
    if "--folder" not in args:
        _error("Usage: marketplace_client.py copy --folder <path> [--field title|description] [--platform fb|mercari]")
        return
    folder = Path(args[args.index("--folder") + 1])
    field = args[args.index("--field") + 1] if "--field" in args else "description"
    platform = args[args.index("--platform") + 1] if "--platform" in args else "fb"
    post_path = folder / "post.md"
    if not post_path.exists():
        _error(f"post.md not found in {folder}. Run 'listing' command first.")
        return
    content = post_path.read_text()
    all_lines = content.splitlines()

    # Detect multi-platform format (uses ═ section headers)
    has_platform_headers = any(line.startswith("═") for line in all_lines)

    if has_platform_headers:
        platform_label = "FACEBOOK MARKETPLACE" if platform == "fb" else "MERCARI"
        section_lines: list[str] = []
        in_section = False
        past_header_sep = False

        for line in all_lines:
            if line == platform_label:
                in_section = True
                past_header_sep = False
                continue
            if in_section:
                if not past_header_sep and line.startswith("═"):
                    past_header_sep = True
                    continue
                if past_header_sep and line.startswith("═"):
                    break  # Start of next section
                if past_header_sep:
                    section_lines.append(line)

        if not section_lines:
            _error(f"Platform '{platform}' section not found in post.md")
            return
        target_lines = section_lines
    else:
        # Legacy single-platform format
        target_lines = all_lines

    if field == "title":
        for line in target_lines:
            if line.startswith("TITLE: "):
                print(line[len("TITLE: "):].strip())
                return
        _error("Title not found in post.md")
    elif field == "description":
        separators = [i for i, line in enumerate(target_lines) if line.startswith("─")]
        if len(separators) >= 2:
            print("\n".join(target_lines[separators[1] + 1:]).strip())
        elif len(separators) == 1:
            print("\n".join(target_lines[separators[0] + 1:]).strip())
        else:
            _error("Description not found in post.md")
    else:
        _error(f"Unknown field '{field}'. Use: title, description")


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
    "group": cmd_group,
    "create-folder": cmd_create_folder,
    "photos": cmd_photos,
    "organize": cmd_organize,
    "unidentified": cmd_unidentified,
    "listing": cmd_listing,
    "copy": cmd_copy,
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
