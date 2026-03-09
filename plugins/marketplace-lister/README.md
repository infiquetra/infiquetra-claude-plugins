# marketplace-lister

Claude Code plugin for turning item photos into multi-platform marketplace listings. Claude identifies items using native vision, researches pricing with WebSearch, selects platforms automatically, and generates clipboard-ready listings for Facebook Marketplace and Mercari with sales strategy and shipping guidance.

## Why This Plugin

The previous automated approach (Freya/OpenClaw) had four problems:
- Vision models misidentified items
- No pricing research (missing Perplexity API key)
- Bare-bones listing output
- 10-minute cron timeout limited processing

This plugin solves all four by running interactively in Claude Code: Claude's vision is dramatically better, WebSearch is built-in, rich text generation is native, and there's no timeout.

## Features

- **Smart inbox grouping** — Dump all photos in inbox; Claude groups them into items automatically by filename sequence
- **Item identification** — Claude views photos and identifies brand, model, condition, specs
- **4-tier pricing** — Quick Sale, Fair Market, Above Market, Maximum Realistic
- **WebSearch pricing research** — eBay sold comps, local FB listings
- **Multi-platform listings** — Optimized copy for Facebook Marketplace and Mercari (with platform selection logic)
- **Shipping guidance** — Carrier recommendations, Pirate Ship setup, cost estimates, packaging tips
- **Listing improvement suggestions** — Photo, title, and description suggestions before saving (with approval)
- **Sales strategy** — Bundle suggestions, timing tips, negotiation guidance
- **iCloud integration** — Organizes photos in dated folders on iCloud Drive
- **listing.md** — Rich markdown file saved alongside photos
- **Clipboard copy** — Platform-specific listing text ready to paste
- **Todoist integration** — Optional task creation to track posting

## Quick Start

### 1. Initialize

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py init
```

Creates `~/Library/Mobile Documents/com~apple~CloudDocs/Marketplace/{inbox,unidentified}/`

### 2. Add Photos

**New in v2 — just dump all photos into inbox directly:**
```
inbox/
├── IMG_2670.heic   ← item 1
├── IMG_2671.heic   ← item 1
├── IMG_2672.heic   ← item 1
├── IMG_2680.heic   ← item 2 (gap in sequence → new item)
└── IMG_2681.heic   ← item 2
```
Claude groups them into items automatically based on filename sequence gaps.

Or use subfolders (still works):
```
inbox/
└── my-item/
    ├── photo1.heic
    └── photo2.heic
```

Or paste photos directly into Claude Code and say "list on marketplace".

### 3. Run

```
/marketplace
```

Or say: "list on marketplace", "process marketplace inbox"

## Plugin Structure

```
marketplace-lister/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── marketplace-lister.md          # For batch processing
├── skills/
│   └── marketplace-list/
│       ├── SKILL.md                   # Pipeline orchestrator
│       ├── scripts/
│       │   └── marketplace_client.py  # Filesystem CLI
│       └── references/
│           ├── fb-marketplace-fields.md
│           ├── mercari-fields.md
│           ├── platform-selection.md
│           ├── pricing-framework.md
│           ├── shipping-guide.md
│           └── listing-improvement-checklist.md
├── commands/
│   └── marketplace.md                 # /marketplace slash command
├── README.md
└── CHANGELOG.md
```

## Script Reference

```bash
python3 marketplace_client.py init
python3 marketplace_client.py scan [--path <dir>]
python3 marketplace_client.py group [--path <dir>]
python3 marketplace_client.py create-folder --name <slug> --photos IMG_001.JPG,IMG_002.JPG
python3 marketplace_client.py photos --folder <path>
python3 marketplace_client.py organize --source <path> --name <slug>
python3 marketplace_client.py unidentified --source <path>
echo '<json>' | python3 marketplace_client.py listing --folder <path>
python3 marketplace_client.py copy --folder <path> [--field title|description] [--platform fb|mercari]
python3 marketplace_client.py status
```

All commands output JSON (except `copy`, which outputs plain text for piping to `pbcopy`).

## Pipeline

```
Photos in iCloud inbox (loose or in subfolders)
        ↓
   group → propose item groupings → user confirms → create-folder
        ↓
   scan → user selects item
        ↓
   Read photos (Claude vision)
        ↓
   Identify → user confirms (with weight estimate)
        ↓
   WebSearch pricing → user reviews
        ↓
   Platform selection (FB/Mercari/both, ship vs. local) → user confirms
        ↓
   Generate listings (per-platform optimized)
        ↓
   Review & improve → suggestions → user approves
        ↓
   organize + listing.md + post.md + pbcopy (platform-specific)
        ↓
   [Optional] Todoist tasks
```

## Testing

```bash
pytest tests/test_marketplace_client.py -v
```

## Requirements

- Python 3.9+ (stdlib only, no pip installs)
- macOS with iCloud Drive enabled
- Claude Code with WebSearch capability
