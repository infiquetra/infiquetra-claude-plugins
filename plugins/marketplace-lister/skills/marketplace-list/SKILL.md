---
name: marketplace-list
description: Identify items from photos, research pricing, and generate multi-platform listings for FB Marketplace, Mercari, and eBay (with full API publish support for eBay)
when_to_use: |
  Use this skill when the user:
  - Wants to list items for sale on Facebook Marketplace, Mercari, or eBay
  - Has photos of items to sell and wants identification + pricing
  - Asks to process or check the marketplace inbox
  - Wants help creating a marketplace listing
  - Wants to publish an item to eBay via API

  Auto-triggers:
  - "list on marketplace"
  - "create marketplace listing"
  - "process marketplace inbox"
  - "check marketplace inbox"
  - "list on mercari"
  - "list on ebay"
  - "publish to ebay"
  - "post to ebay"
---

# Marketplace Lister Skill

Turn photos into ready-to-post listings for Facebook Marketplace, Mercari, and eBay. Claude identifies items using native vision, researches pricing via WebSearch, selects platforms, and generates optimized content for each platform. eBay listings can be published programmatically via the eBay API.

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

### Step 4.5 — Platform Selection

Using `references/platform-selection.md`, recommend which platform(s) to list on:

**Ask yourself:**
1. Is the item large/heavy (> 30 lbs or fragile to ship)? → FB only
2. Is the price under $20? → FB only (shipping economics don't work)
3. Does the item benefit from nationwide audience? → FB + Mercari
4. Does it have a brand name, MPN, or UPC and price > $30? → Consider adding eBay

**eBay decision:** Recommend eBay when the item has a known brand/model, benefits from the widest buyer pool, and is worth the ~13.25% fee. Brand-name electronics, tools, collectibles with MPN — strong eBay candidates.

**Ship vs. Local:**
- Ship if: weight < 10 lbs AND price > $25
- Local only if: weight > 20 lbs, price < $20, or item is fragile/risky

**Price adjustments:**
- Mercari: FB price ÷ 0.90 (covers 10% fee). Example: FB $70 → Mercari $78
- eBay: FB price ÷ 0.87 (covers 13.25% FVF + $0.30). Example: FB $70 → eBay $80

**Present recommendation:**
```
Platform recommendation:
- ✅ Facebook Marketplace ($70) — local pickup, no fees
- ✅ Mercari ($78) — nationwide buyers, 10% fee (nets same as FB)
- ✅ eBay ($80) — global buyers, API publish, 13.25% FVF (nets ~$69)
- 📦 Shipping: 3 lbs estimated → USPS Ground Advantage via Pirate Ship (~$7–9)

This is a Cisco networking switch — strong eBay demand from home lab buyers.
I recommend all three platforms.
Does this work, or would you prefer to skip any?
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

#### eBay (if recommended)

```
TITLE: [keyword-dense, 80 char max — brand/model/MPN/key spec/condition keyword]
PRICE: $[ebay_price]  ← FB price ÷ 0.87
CATEGORY: [eBay category name]
CONDITION CODE: [1000/1500/4000/5000/6000/7000]
FORMAT: Fixed Price  (or Auction if vintage/collectible/uncertain value)
LISTING DURATION: Good 'Til Cancelled  (or 7-day for auction)

ITEM SPECIFICS:
  Brand: [Brand]
  Model: [Model]
  MPN: [Part number if known]
  [other category-relevant specifics]

DESCRIPTION (HTML):
<div style="font-family: Arial, sans-serif; max-width: 700px;">
  <h2>[Brand] [Model] — [Condition]</h2>
  <h3>What You're Getting</h3>
  <p>[2-3 sentences: what it is, why someone wants it]</p>
  <h3>Specifications</h3>
  <ul>
    <li><strong>Brand:</strong> [Brand]</li>
    <li><strong>Model:</strong> [Model]</li>
    [key specs as li items]
  </ul>
  <h3>Condition Details</h3>
  <p>[Specific condition notes — mention cosmetic issues, confirm functionality]</p>
  <h3>Shipping</h3>
  <p>Ships within 1 business day. Carefully packaged.</p>
  <h3>Returns</h3>
  <p>30-day returns accepted.</p>
</div>
```

**Key differences from other platforms:**
- eBay title: no punctuation, pack MPN if known, brand+model+spec+condition keyword in 80 chars
- eBay description: HTML renders — use it for professional presentation
- eBay price: ~15% above FB to cover 13.25% FVF + $0.30 per order
- Item specifics: fill Brand, Model, MPN at minimum — more = better search rank
- Condition code: map your assessed condition to the numeric code (see `references/ebay-fields.md`)

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
  "ebay_title": "Brand Model KeySpec MPN Good Keyword",
  "category": "Electronics > Networking",
  "mercari_category": "Electronics > Networking Equipment",
  "ebay_category": "Switches & Hubs",
  "condition": "Good",
  "condition_code": 5000,
  "description": "Full FB description text...",
  "mercari_description": "Spec-forward Mercari description... #networking #cisco",
  "ebay_description": "<div style=\"font-family:Arial\"><h2>Cisco SG300-28</h2><ul><li><strong>Ports:</strong> 28 Gigabit</li></ul><p>Condition: Good. Minor cosmetic wear only.</p></div>",
  "location": "Indianapolis, IN",
  "platforms": ["fb", "mercari", "ebay"],
  "listing_format": "fixed_price",
  "listing_duration": "GTC",
  "item_specifics": {
    "Brand": "Cisco",
    "Model": "SG300-28",
    "MPN": "SG300-28-K9-NA",
    "Number of Ports": "28"
  },
  "ebay_shipping": "calculated",
  "return_policy": "30_day_free",
  "pricing": {
    "quick_sale": 55,
    "fair_market": 70,
    "above_market": 80,
    "maximum": 90,
    "mercari_price": 78,
    "ebay_price": 80,
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

For FB-only listings, omit `mercari_*` and `ebay_*` fields and set `"platforms": ["fb"]`.
For FB + Mercari only, omit `ebay_*` fields and set `"platforms": ["fb", "mercari"]`.

**Copy to clipboard** — use the `copy` command after saving:
```bash
python3 marketplace_client.py copy --folder <path> --field description --platform fb | pbcopy
```

For Mercari:
```bash
python3 marketplace_client.py copy --folder <path> --field description --platform mercari | pbcopy
```

For eBay (HTML description — paste into eBay's description field):
```bash
python3 marketplace_client.py copy --folder <path> --field description --platform ebay | pbcopy
```

Tell user: "FB listing copied to clipboard — ready to paste into Facebook Marketplace."
Tell user (if Mercari): "Run the copy command with `--platform mercari` when ready to post there."
Tell user (if eBay): "For eBay, use the API publish flow (Step 7) or run `copy --platform ebay` for manual posting."

---

### Step 7 — eBay API Publish (if eBay platform selected)

eBay supports full API-based publishing. Walk the user through the interactive review process.

#### 7.1 — Prepare for review

```bash
python3 ebay_client.py publish --folder <organized-folder-path>
```

This returns:
- Top 5 category suggestions (from eBay taxonomy API)
- Item aspects/specifics suggested by eBay for the category
- Current monthly limits (`items_listed / 20`, `amount_listed / $1,000`)

#### 7.2 — Walk through interactive review

Present each decision point and wait for user confirmation:

**Category:**
```
I found these eBay categories for this item:
1. Switches & Hubs (most common — recommended)
2. Enterprise Networking
3. Computer Components > Networking

Which category? (Enter 1-5 or type a different one)
```

**Item specifics:** Show eBay-suggested specifics pre-filled from the listing. Ask user to confirm or adjust.

**Listing format:**
```
Format recommendation:
- Fixed Price (Good 'Til Cancelled) — recommended for networking gear with known market value
- Auction (7-day) — better if you're unsure of value or want fastest possible sale

Go with Fixed Price at $80?
```

**Shipping:**
```
Shipping options:
1. Calculated — buyer pays actual carrier rate based on their zip (recommended for 3+ lbs)
2. Flat rate — set $12 regardless of distance
3. Free shipping — bake into price (recommend only for < 1 lb)

For 5 lbs, I recommend Calculated shipping. Confirm?
```

**Return policy:**
```
Return policy: 30-day free returns (recommended — improves search rank)
Confirm?
```

**Photo order:** Show current photo list. Ask if user wants to reorder.

**Final summary with limits check:**
```
Ready to publish to eBay:
- Title: Cisco SG300-28 28-Port Gigabit Managed Switch Good
- Price: $80.00 (Fixed Price)
- Category: Switches & Hubs
- Condition: Good (5000)
- Shipping: Calculated
- Returns: 30-day free

Monthly limits: 5/20 items, $245/$1,000 — plenty of capacity.

Publish now?
```

#### 7.3 — Execute publish

When user approves, pipe the confirmed JSON to publish-confirm:

```bash
echo '<confirmed-json>' | python3 ebay_client.py publish-confirm --folder <path>
```

This will:
1. Upload all photos in the folder to eBay
2. Create eBay inventory item with full details
3. Create offer with pricing, shipping, and return policy
4. Publish the offer (makes it live)
5. Save `ebay.json` in the item folder with listing ID and URL
6. Update `Marketplace/ebay-limits.json` with the new listing

Report success:
```
✅ Published to eBay!
URL: https://www.ebay.com/itm/[listing-id]
eBay listing ID saved to ebay.json

Monthly limits updated: 6/20 items, $325/$1,000
```

#### 7.4 — Post-publish management

After publishing, these commands are available via `ebay_client.py`:

| Command | When to Use |
|---------|-------------|
| `status --folder <path>` | Check views, watchers, sold status |
| `ship --folder <path> --tracking NUM --carrier NAME` | Add fulfillment after sale |
| `relist --folder <path>` | Re-publish an ended listing |
| `messages` | Check buyer messages |
| `limits` | Show current monthly limit usage |

---

### Step 8 — Todoist (opt-in)

Ask: "Want me to create Todoist tasks to track posting?"

If yes, use the todoist-manage skill to create:
- **Task 1:** `Post [Item Name] on Facebook Marketplace - $[fair_market]`
- **Task 2 (if Mercari):** `Post [Item Name] on Mercari - $[mercari_price]`
- **Task 3 (if eBay and not yet published):** `Publish [Item Name] on eBay - $[ebay_price]`
- **Project:** Marketplace (create if needed)
- **Description:** Pricing summary + listing.md path

---

## Reference Documents

- `references/fb-marketplace-fields.md` — FB form fields, categories, condition values, listing tips
- `references/mercari-fields.md` — Mercari fields, fee structure, shipping rates, platform tips
- `references/ebay-fields.md` — eBay condition codes, HTML description, item specifics, fees, OAuth scopes
- `references/platform-selection.md` — Which platform(s) to use, ship vs. local decision matrix, eBay recommendation logic
- `references/shipping-guide.md` — Starter kit, Pirate Ship, carrier selection, packaging tips, eBay shipping options
- `references/pricing-framework.md` — 4-tier methodology, platform price adjustments, WebSearch query templates
- `references/listing-improvement-checklist.md` — Review checklist for Step 5.5, including eBay-specific checks

---

## Script Commands Reference

### marketplace_client.py (listing text generation)

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
| `copy` | `--folder <path> [--field title\|description] [--platform fb\|mercari\|ebay]` | Plain text for pbcopy |
| `status` | — | JSON: all organized items |

### ebay_client.py (eBay API operations)

| Command | Key Args | Output |
|---------|----------|--------|
| `publish` | `--folder <path>` | JSON: category suggestions + review data |
| `publish-confirm` | `--folder <path>` (stdin: confirmed JSON) | JSON: listing ID + URL |
| `status` | `[--folder <path>]` | JSON: listing status + views/watchers |
| `relist` | `--folder <path>` | JSON: new listing ID |
| `ship` | `--folder <path> --tracking NUM --carrier NAME` | JSON: fulfillment confirmation |
| `messages` | `[--limit N]` | JSON: recent buyer messages |
| `limits` | — | JSON: monthly usage (items + amount) |
| `categories` | `--query TEXT` | JSON: eBay category suggestions |
