# marketplace-lister

Claude Code plugin for turning item photos into multi-platform marketplace listings. Claude identifies items using native vision, researches pricing with WebSearch, selects platforms automatically, and generates clipboard-ready listings for Facebook Marketplace, Mercari, and eBay — with full eBay API integration for programmatic publish, status tracking, and fulfillment management.

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
- **Multi-platform listings** — Optimized copy for Facebook Marketplace, Mercari, and eBay (HTML description)
- **Platform selection logic** — Recommends FB/Mercari/eBay based on item type, weight, price, and brand
- **eBay API publish** — Full REST API integration: category lookup, photo upload, inventory creation, offer publish
- **eBay management** — Status checks, relist, shipping fulfillment, buyer messages, limit tracking
- **Monthly limit tracking** — Tracks 20-item/$1,000 monthly limits with warnings at 80% capacity
- **Shipping guidance** — Carrier recommendations, Pirate Ship setup, eBay shipping options, packaging tips
- **Listing improvement suggestions** — Photo, title, and description suggestions before saving (with eBay-specific checks)
- **Sales strategy** — Bundle suggestions, timing tips, negotiation guidance
- **iCloud integration** — Organizes photos in dated folders on iCloud Drive
- **listing.md** — Rich markdown file saved alongside photos with all platform listings
- **Clipboard copy** — Platform-specific listing text ready to paste (`--platform fb|mercari|ebay`)
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
│   └── marketplace-lister.md          # For batch processing + eBay management
├── skills/
│   └── marketplace-list/
│       ├── SKILL.md                   # Pipeline orchestrator (8-step)
│       ├── scripts/
│       │   ├── marketplace_client.py  # Filesystem CLI + listing text generation
│       │   └── ebay_client.py         # eBay REST API client
│       └── references/
│           ├── fb-marketplace-fields.md
│           ├── mercari-fields.md
│           ├── ebay-fields.md         # eBay condition codes, HTML, fees, OAuth
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

### marketplace_client.py (listing text generation)

```bash
python3 marketplace_client.py init
python3 marketplace_client.py scan [--path <dir>]
python3 marketplace_client.py group [--path <dir>]
python3 marketplace_client.py create-folder --name <slug> --photos IMG_001.JPG,IMG_002.JPG
python3 marketplace_client.py photos --folder <path>
python3 marketplace_client.py organize --source <path> --name <slug>
python3 marketplace_client.py unidentified --source <path>
echo '<json>' | python3 marketplace_client.py listing --folder <path>
python3 marketplace_client.py copy --folder <path> [--field title|description] [--platform fb|mercari|ebay]
python3 marketplace_client.py status
```

### ebay_client.py (eBay API operations)

```bash
# Requires: EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REFRESH_TOKEN

python3 ebay_client.py publish --folder <path>
echo '<confirmed-json>' | python3 ebay_client.py publish-confirm --folder <path>
python3 ebay_client.py status [--folder <path>]
python3 ebay_client.py relist --folder <path>
echo '<revision-json>' | python3 ebay_client.py revise --folder <path>
python3 ebay_client.py ship --folder <path> --tracking <number> --carrier <name>
python3 ebay_client.py messages [--limit 20]
python3 ebay_client.py limits
python3 ebay_client.py categories --query 'networking switch'
```

All commands output JSON (except `copy`, which outputs plain text for piping to `pbcopy`).

### eBay State Files

Each organized item folder gets `ebay.json` after publishing:
```json
{
  "listing_id": "123456789",
  "offer_id": "offer123",
  "sku": "MKPL-2026-03-09-cisco-sg300-switch",
  "status": "active",
  "listing_format": "fixed_price",
  "published_at": "2026-03-11T10:30:00",
  "price": 80.0,
  "category_id": "11176",
  "url": "https://www.ebay.com/itm/123456789",
  "views": 0,
  "watchers": 0
}
```

Monthly limits are tracked in `~/iCloud Drive/Marketplace/ebay-limits.json`.

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

- Python 3.12+
- macOS with iCloud Drive enabled
- Claude Code with WebSearch capability
- `requests` library (already in project dependencies)
- `Pillow` (optional, for HEIC→JPEG conversion during eBay photo upload): `pip install Pillow`
- eBay Developer account (free) for API credentials: developer.ebay.com

## eBay Setup

1. Create account at developer.ebay.com
2. Create an application → get App ID (Client ID) and Cert ID (Client Secret)
3. Generate a User Token with the required scopes (sell.inventory, sell.fulfillment, sell.account, commerce.taxonomy.readonly)
4. Set environment variables:
   ```bash
   export EBAY_CLIENT_ID=your-app-id
   export EBAY_CLIENT_SECRET=your-cert-id
   export EBAY_REFRESH_TOKEN=your-user-token
   ```
5. Test with sandbox: `export EBAY_SANDBOX=true`

See `references/ebay-fields.md` for complete OAuth scope details.
