# marketplace-lister

Claude Code plugin for turning item photos into Facebook Marketplace listings. Claude identifies items using native vision, researches pricing with WebSearch, and generates clipboard-ready listings with sales strategy.

## Why This Plugin

The previous automated approach (Freya/OpenClaw) had four problems:
- Vision models misidentified items
- No pricing research (missing Perplexity API key)
- Bare-bones listing output
- 10-minute cron timeout limited processing

This plugin solves all four by running interactively in Claude Code: Claude's vision is dramatically better, WebSearch is built-in, rich text generation is native, and there's no timeout.

## Features

- **Item identification** — Claude views photos and identifies brand, model, condition, specs
- **4-tier pricing** — Quick Sale, Fair Market, Above Market, Maximum Realistic
- **WebSearch pricing research** — eBay sold comps, local FB listings
- **Ready-to-post format** — Title, price, category, description all formatted for FB
- **Sales strategy** — Bundle suggestions, timing tips, negotiation guidance
- **Photo coaching** — Specific improvement suggestions based on photos seen
- **iCloud integration** — Organizes photos in dated folders on iCloud Drive
- **listing.md** — Rich markdown file saved alongside photos
- **Clipboard copy** — Listing text ready to paste into Facebook
- **Todoist integration** — Optional task creation to track posting

## Quick Start

### 1. Initialize

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py init
```

Creates `~/Library/Mobile Documents/com~apple~CloudDocs/Marketplace/{inbox,unidentified}/`

### 2. Add Photos

Drop item photos into a subfolder in `iCloud Drive/Marketplace/inbox/`:
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
│           └── pricing-framework.md
├── commands/
│   └── marketplace.md                 # /marketplace slash command
├── README.md
└── CHANGELOG.md
```

## Script Reference

```bash
python3 marketplace_client.py init
python3 marketplace_client.py scan [--path <dir>]
python3 marketplace_client.py photos --folder <path>
python3 marketplace_client.py organize --source <path> --name <slug>
python3 marketplace_client.py unidentified --source <path>
echo '<json>' | python3 marketplace_client.py listing --folder <path>
python3 marketplace_client.py status
```

All commands output JSON.

## Pipeline

```
Photos in iCloud inbox
        ↓
   scan → user selects item
        ↓
   Read photos (Claude vision)
        ↓
   Identify → user confirms
        ↓
   WebSearch pricing → user reviews
        ↓
   Generate listing → user reviews
        ↓
   organize + listing.md + pbcopy
        ↓
   [Optional] Todoist task
```

## Testing

```bash
pytest tests/test_marketplace_client.py -v
```

## Requirements

- Python 3.9+ (stdlib only, no pip installs)
- macOS with iCloud Drive enabled
- Claude Code with WebSearch capability
