---
name: marketplace-list
description: Identify items from photos, research pricing, and generate Facebook Marketplace listings
when_to_use: |
  Use this skill when the user:
  - Wants to list items for sale on Facebook Marketplace
  - Has photos of items to sell and wants identification + pricing
  - Asks to process or check the marketplace inbox
  - Wants help creating a marketplace listing

  Auto-triggers:
  - "list on marketplace"
  - "create marketplace listing"
  - "process marketplace inbox"
  - "check marketplace inbox"
---

# Marketplace Lister Skill

Turn photos into Facebook Marketplace listings. Claude identifies items using native vision, researches pricing via WebSearch, and generates ready-to-post listings with sales strategy.

## Script

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py <command> [args]
```

## Full Pipeline

### Step 1 — Input Detection

Determine how the user is providing items:

**A. Photos pasted directly in conversation** → Skip to Step 3 (identify immediately)

**B. User points to a specific folder** → Run `scan --path <folder>`, then Step 3

**C. "Process inbox" / no path given** → Run scan on default inbox:
```bash
python3 marketplace_client.py scan
```
Show results and ask user which item(s) to process. If inbox is empty, say so and stop.

### Step 2 — Read Photos

Use the Read tool to view each image file in the folder. Claude's native vision handles HEIC, JPG, PNG, and WEBP without conversion.

```bash
python3 marketplace_client.py photos --folder <path>
```

Read each returned path using the Read tool.

### Step 3 — Identify Item (CHECKPOINT: user confirms)

Analyze all photos and identify:
- Brand, model, product name (be specific — "Cooler Master Hyper 212" not "CPU cooler")
- Condition: New / Like New / Good / Fair / Poor
- Key specifications visible in photos (dimensions, color, model number, capacity, etc.)
- Accessories or components included
- Visible damage, wear, or missing parts

**Present to user for confirmation:**
> "I see a **[Item Name]** in **[Condition]** condition. [One sentence of key details]. Is that correct?"

If user corrects → update identification. If truly unidentifiable → run:
```bash
python3 marketplace_client.py unidentified --source <folder>
```
Then ask user to add more photos or a description.

### Step 4 — Price Research (CHECKPOINT: user reviews)

Use WebSearch to research market prices:

1. `"[item name] used price site:ebay.com sold"` — actual transaction prices
2. `"[item name] Facebook Marketplace Indianapolis"` — local market
3. `"[item name] new price"` — new price anchor (ceiling for used)

Synthesize into **4-tier pricing**:

| Tier | Target | Strategy |
|------|--------|----------|
| **Quick Sale** | 20-30% below fair market | Sells in 24-48 hours |
| **Fair Market** | Based on eBay sold + local FB comps | Recommended start, sells in 3-7 days |
| **Above Market** | 10-15% above fair market | Patient seller, 1-2 weeks |
| **Maximum Realistic** | Highest justifiable | Perfect condition premium |

**Indianapolis adjustment:** Prices typically run 10-15% below coastal markets.

**Transparency note:** Always label pricing as estimates and cite sources (eBay sold, local FB comps, model knowledge).

Present pricing tiers with reasoning. Ask user to confirm or adjust before proceeding.

### Step 5 — Generate Listing

Produce the complete listing in clipboard-ready format:

```
TITLE: [Brand] [Model] [Key Spec] - [Condition]
PRICE: $[fair_market]
CATEGORY: [FB Marketplace category]
CONDITION: [New/Like New/Good/Fair/Poor]
LOCATION: Indianapolis, IN

DESCRIPTION:
[2-4 paragraphs. Lead with what it is and why someone wants it.
Include key specs. End with pickup/payment logistics.]

Cash or Venmo. Pickup in [neighborhood], Indianapolis. No holds without deposit.
```

Also generate:
- **Sales strategy:** Bundle suggestions, timing tips, negotiation advice
- **Photo coaching:** 1-3 specific improvements based on the photos seen

Print full listing in conversation for user review.

### Step 6 — Save & Organize

**Organize the folder:**
```bash
python3 marketplace_client.py organize --source <inbox-folder-name> --name <item-slug>
```
Use concise, searchable slug: `dewalt-drill-set`, `iphone-14-pro`, `sectional-sofa-gray`

**Write the listing file (pipe JSON via stdin):**
```bash
echo '<listing-json>' | python3 marketplace_client.py listing --folder <organized-folder-path>
```

The JSON schema for the listing command:
```json
{
  "title": "Brand Model Key Spec - Condition",
  "category": "Electronics > Computers",
  "condition": "Good",
  "description": "Full description text",
  "location": "Indianapolis, IN",
  "pricing": {
    "quick_sale": 25,
    "fair_market": 35,
    "above_market": 42,
    "maximum": 50,
    "reasoning": "eBay sold comps show $30-40 range for Good condition units"
  },
  "strategy": [
    "List Thursday-Friday for maximum weekend traffic",
    "Mention compatibility with Intel and AMD for broader appeal"
  ],
  "photo_coaching": [
    "Add a photo showing the fan mounting bracket — buyers often ask",
    "Include a close-up of the model sticker"
  ],
  "specs": {
    "Brand": "Cooler Master",
    "Model": "Hyper 212",
    "Socket Support": "Intel LGA1700/1200, AMD AM4/AM5",
    "Condition": "Good"
  }
}
```

**Copy to clipboard:**
```bash
echo "[clipboard-ready listing text]" | pbcopy
```

Tell user: "Listing copied to clipboard — ready to paste into Facebook Marketplace."

### Step 7 — Todoist (opt-in)

Ask: "Want me to create a Todoist task to track posting this?"

If yes, use the todoist-manage skill to create:
- **Task:** `Post [Item Name] on Facebook Marketplace - $[fair_market]`
- **Project:** Marketplace (create if needed)
- **Description:** Pricing summary + listing.md path

## Reference Documents

- `references/fb-marketplace-fields.md` — All FB form fields, categories, condition values, title tips
- `references/pricing-framework.md` — 4-tier methodology, WebSearch query templates, Indianapolis market notes

## Script Commands Reference

| Command | Key Args | Output |
|---------|----------|--------|
| `init` | — | Creates iCloud Marketplace dirs |
| `scan` | `--path <dir>` (optional) | JSON: folder list with photo counts |
| `photos` | `--folder <path>` | JSON: array of image file paths |
| `organize` | `--source <path> --name <slug>` | JSON: new folder path |
| `unidentified` | `--source <path>` | JSON: moved path |
| `listing` | `--folder <path>` (stdin: JSON) | JSON: listing.md path |
| `status` | — | JSON: all organized items |
