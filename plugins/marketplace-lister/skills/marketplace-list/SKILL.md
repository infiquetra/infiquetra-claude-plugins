---
name: marketplace-list
description: Identify items from photos, research pricing, and generate multi-platform listings for FB Marketplace and Mercari
when_to_use: |
  Use this skill when the user:
  - Wants to list items for sale on Facebook Marketplace or Mercari
  - Has photos of items to sell and wants identification + pricing
  - Asks to process or check the marketplace inbox
  - Wants help creating a marketplace listing

  Auto-triggers:
  - "list on marketplace"
  - "create marketplace listing"
  - "process marketplace inbox"
  - "check marketplace inbox"
  - "list on mercari"
---

# Marketplace Lister Skill

Turn photos into ready-to-post listings for Facebook Marketplace and Mercari. Claude identifies items using native vision, researches pricing via WebSearch, selects platforms, and generates optimized copy-paste content for each platform.

## Script

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py <command> [args]
```

---

## Full Pipeline

### Step 0 — Inbox Triage (if loose photos detected)

When scanning reveals loose photos (not in subfolders), run inbox grouping first:

```bash
python3 marketplace_client.py scan
```

If `loose_count > 0`, run:

```bash
python3 marketplace_client.py group
```

The `group` command returns proposed item groupings based on filename sequence gaps (gap ≥ 5 between IMG numbers = likely new item).

**Present to user for confirmation:**
```
I found 14 loose photos and grouped them into 3 items:

📁 Group 1 (IMG_2670–2672): 3 photos — appears to be a network router
📁 Group 2 (IMG_2673–2676): 4 photos — appears to be server rack rails
📁 Group 3 (IMG_2677–2683): 7 photos — appears to be a mix (split?)

Does this grouping look right? I can adjust any group before creating folders.
```

View the first photo of each group to visually confirm the grouping. If a group looks like two items, suggest splitting it.

After user confirms, create subfolders for each group:

```bash
python3 marketplace_client.py create-folder --name <slug> --photos IMG_2670.JPG,IMG_2671.JPG,IMG_2672.JPG
```

Run `create-folder` once per group. Use a descriptive slug (e.g., `router`, `rack-rails`, `item-3`). After creating folders, proceed to Step 1.

---

### Step 1 — Input Detection

Determine how the user is providing items:

**A. Photos pasted directly in conversation** → Skip to Step 3 (identify immediately)

**B. User points to a specific folder** → Run `scan --path <folder>`, then Step 3

**C. "Process inbox" / no path given** → Run scan on default inbox:
```bash
python3 marketplace_client.py scan
```
Show results and ask user which item(s) to process. If inbox is empty and no loose photos, say so and stop.

---

### Step 2 — Read Photos

Use the Read tool to view each image file in the folder. Claude's native vision handles HEIC, JPG, PNG, and WEBP without conversion.

```bash
python3 marketplace_client.py photos --folder <path>
```

Read each returned path using the Read tool.

---

### Step 3 — Identify Item (CHECKPOINT: user confirms)

Analyze all photos and identify:
- Brand, model, product name (be specific — "Cooler Master Hyper 212" not "CPU cooler")
- Condition: New / Like New / Good / Fair / Poor
- Key specifications visible in photos (dimensions, color, model number, capacity, etc.)
- Accessories or components included
- Visible damage, wear, or missing parts
- Estimated weight (important for shipping decision)

**Present to user for confirmation:**
> "I see a **[Item Name]** in **[Condition]** condition. [One sentence of key details]. Estimated weight: ~[N] lbs. Is that correct?"

If user corrects → update identification. If truly unidentifiable → run:
```bash
python3 marketplace_client.py unidentified --source <folder>
```
Then ask user to add more photos or a description.

---

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

**Indianapolis adjustment:** Prices typically run 10-15% below coastal markets for FB listings.

**Shipping cost estimate:** Based on estimated item weight:
- Under 1 lb → ~$4–6 via Pirate Ship
- 1–3 lbs → ~$6–9
- 3–8 lbs → ~$9–15
- 8–20 lbs → ~$15–28
- Over 20 lbs → local pickup recommended

Present pricing tiers with reasoning. Ask user to confirm or adjust before proceeding.

---

### Step 4.5 — Platform Selection (NEW)

Using `references/platform-selection.md`, recommend which platform(s) to list on:

**Ask yourself:**
1. Is the item large/heavy (> 30 lbs or fragile to ship)? → FB only
2. Is the price under $20? → FB only (shipping economics don't work)
3. Does the item benefit from nationwide audience? → Both FB + Mercari

**Ship vs. Local:**
- Ship if: weight < 10 lbs AND price > $25
- Local only if: weight > 20 lbs, price < $20, or item is fragile/risky

**Mercari price adjustment:**
- Mercari charges 10% selling fee
- Set Mercari price = FB price ÷ 0.90 (rounds to nearest $1)
- Example: FB $70 → Mercari $78

**Present recommendation:**
```
Platform recommendation:
- ✅ Facebook Marketplace ($70) — local pickup, no fees
- ✅ Mercari ($78) — nationwide buyers, 10% fee (nets same as FB)
- 📦 Shipping: 3 lbs estimated → USPS Ground Advantage via Pirate Ship (~$7–9)

This item is lightweight enough to ship profitably. I recommend listing on both.
Does this work, or would you prefer local-only?
```

---

### Step 5 — Generate Listing

Produce optimized listings for each recommended platform.

#### Facebook Marketplace

```
TITLE: [Brand] [Model] [Key Spec] - [Condition]   (max 100 chars)
PRICE: $[fair_market]
CATEGORY: [FB Marketplace category]
CONDITION: [New/Like New/Good/Fair/Poor]
LOCATION: Indianapolis, IN

DESCRIPTION:
[2-4 paragraphs. Lead with what it is and why someone wants it.
Include key specs. End with pickup/payment logistics.]

Cash or Venmo. Pickup in [neighborhood], Indianapolis. No holds without deposit.
```

#### Mercari (if recommended)

```
TITLE: [keyword-dense, 80 char max — pack brand/model/spec]
PRICE: $[mercari_price]
CATEGORY: [Mercari category]
CONDITION: [same condition value]
SHIPPING: Prepaid label — [carrier, estimated cost]

DESCRIPTION:
[1,000 char max. Specs first. No markdown renders. End with 1-3 hashtags.]

#[keyword] #[keyword] #[keyword]
```

**Key differences:**
- Mercari title: keyword density > readability (buyers search by keyword)
- Mercari description: no markdown, spec-forward, hashtags at end
- Mercari price: 11% higher to cover fee

Also generate:
- **Sales strategy:** Bundle suggestions, timing tips, negotiation advice
- **Photo coaching:** 1-3 specific improvements based on photos seen

Print full listing in conversation for user review.

---

### Step 5.5 — Review & Improve (NEW)

After generating the listing but before saving, review it against `references/listing-improvement-checklist.md`.

Check for:
- **Photos:** Missing angles, poor lighting, wrong order, no "powered on" shot for electronics
- **Title:** Missing searchable keywords, wasted characters, missing "Firm" if appropriate
- **Description:** Missing specs buyers ask about, no compatibility notes, no social proof
- **Pricing:** Significant gap from comps, bundle opportunity, seasonal timing issues

**Present only real suggestions** (skip checklist items where listing is already good):

```
## Suggested Improvements

Before I save this listing, here are a few suggestions:

📸 **Photos:**
1. Add a photo with the unit powered on (LEDs lit) — shows it works
2. Move the model label close-up to position 3 (builds trust)

✏️ **Description:**
1. Add rack depth compatibility note — buyers always ask
2. Add "home lab" to Mercari title — that community searches for it

Apply these improvements? [Yes, all / Pick which ones / Skip]
```

Wait for user response before proceeding. Apply any approved changes.

---

### Step 6 — Save & Organize

**Organize the folder:**
```bash
python3 marketplace_client.py organize --source <inbox-folder-name> --name <item-slug>
```
Use concise, searchable slug: `dewalt-drill-set`, `cisco-sg300-switch`, `yeti-tundra-45`

**Write the listing file (pipe JSON via stdin):**
```bash
echo '<listing-json>' | python3 marketplace_client.py listing --folder <organized-folder-path>
```

The JSON schema for the listing command:
```json
{
  "title": "Brand Model Key Spec - Condition",
  "mercari_title": "Brand Model KeySpec Keyword2 Good",
  "category": "Electronics > Networking",
  "mercari_category": "Electronics > Networking Equipment",
  "condition": "Good",
  "description": "Full FB description text...",
  "mercari_description": "Spec-forward Mercari description... #networking #cisco",
  "location": "Indianapolis, IN",
  "platforms": ["fb", "mercari"],
  "pricing": {
    "quick_sale": 55,
    "fair_market": 70,
    "above_market": 80,
    "maximum": 90,
    "mercari_price": 78,
    "reasoning": "eBay sold comps show $65-85 for Good condition"
  },
  "shipping": {
    "estimated_weight_lbs": 3.0,
    "recommended_carrier": "USPS Ground Advantage via Pirate Ship",
    "estimated_cost": "~$8-10",
    "packaging": "Medium box, bubble wrap around unit, kraft paper fill",
    "ship_or_local": "Both — item is light enough to ship profitably"
  },
  "strategy": [
    "List Thursday for maximum weekend traffic",
    "Mention home lab use in Mercari title — that community pays full price"
  ],
  "photo_coaching": [
    "Add a photo with LEDs lit to show it powers on",
    "Include a close-up of the rear ports"
  ],
  "specs": {
    "Brand": "Cisco",
    "Model": "SG300-28",
    "Ports": "28 × Gigabit",
    "Managed": "Yes — Layer 3",
    "Condition": "Good"
  }
}
```

For FB-only listings, omit `mercari_*` fields and set `"platforms": ["fb"]`.

**Copy to clipboard** — use the `copy` command after saving:
```bash
python3 marketplace_client.py copy --folder <path> --field description --platform fb | pbcopy
```

For Mercari:
```bash
python3 marketplace_client.py copy --folder <path> --field description --platform mercari | pbcopy
```

Tell user: "FB listing copied to clipboard — ready to paste into Facebook Marketplace."
Tell user (if Mercari): "Run the copy command with `--platform mercari` when ready to post there."

---

### Step 7 — Todoist (opt-in)

Ask: "Want me to create Todoist tasks to track posting?"

If yes, use the todoist-manage skill to create:
- **Task 1:** `Post [Item Name] on Facebook Marketplace - $[fair_market]`
- **Task 2 (if Mercari):** `Post [Item Name] on Mercari - $[mercari_price]`
- **Project:** Marketplace (create if needed)
- **Description:** Pricing summary + listing.md path

---

## Reference Documents

- `references/fb-marketplace-fields.md` — FB form fields, categories, condition values, listing tips
- `references/mercari-fields.md` — Mercari fields, fee structure, shipping rates, platform tips
- `references/platform-selection.md` — Which platform(s) to use, ship vs. local decision matrix
- `references/shipping-guide.md` — Starter kit, Pirate Ship, carrier selection, packaging tips
- `references/pricing-framework.md` — 4-tier methodology, WebSearch query templates, Indianapolis market
- `references/listing-improvement-checklist.md` — Review checklist for Step 5.5

---

## Script Commands Reference

| Command | Key Args | Output |
|---------|----------|--------|
| `init` | — | Creates iCloud Marketplace dirs |
| `scan` | `--path <dir>` (optional) | JSON: folder list + loose photos |
| `group` | `--path <dir>` (optional) | JSON: proposed photo groupings |
| `create-folder` | `--name <slug> --photos <csv>` | JSON: new folder path |
| `photos` | `--folder <path>` | JSON: array of image file paths |
| `organize` | `--source <path> --name <slug>` | JSON: new folder path |
| `unidentified` | `--source <path>` | JSON: moved path |
| `listing` | `--folder <path>` (stdin: JSON) | JSON: listing.md + post.md paths |
| `copy` | `--folder <path> [--field title\|description] [--platform fb\|mercari]` | Plain text for pbcopy |
| `status` | — | JSON: all organized items |
