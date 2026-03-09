# /marketplace - Facebook Marketplace Listing Tool

Identify items from photos, research pricing, and generate ready-to-post Facebook Marketplace listings.

## Usage

```bash
/marketplace              # Scan inbox and start processing
/marketplace scan         # Show inbox contents without processing
/marketplace status       # Show all current organized listings
```

## What It Does

The `/marketplace` command activates the **marketplace-list** skill which:

1. **Scans inbox** — Checks iCloud Drive Marketplace/inbox for items to process
2. **Identifies items** — Uses Claude's vision to identify brand, model, condition
3. **Researches pricing** — WebSearch for eBay sold comps and local FB prices
4. **Generates listing** — Writes FB-ready title, description, and pricing strategy
5. **Organizes files** — Moves folder to dated location, writes listing.md
6. **Copies to clipboard** — Listing text ready to paste into Facebook

## Quick Actions

```bash
/marketplace                          # Check inbox and start
/marketplace scan                     # See what's in inbox
/marketplace status                   # See all organized listings
```

Or just say naturally:
- "list on marketplace"
- "create marketplace listing"
- "process marketplace inbox"
- "check marketplace inbox"
- "what's in my marketplace inbox"

## Prerequisites

### 1. Initialize Marketplace Directory

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py init
```

This creates:
```
~/Library/Mobile Documents/com~apple~CloudDocs/Marketplace/
├── inbox/          ← Drop item photo folders here
└── unidentified/   ← Items Claude couldn't identify
```

### 2. Add Items to Inbox

**From iPhone:**
1. Photograph the item
2. Open Files app → iCloud Drive → Marketplace → inbox
3. Create a new folder (item name or number)
4. Move/save photos into that folder

**From Mac:**
- Open Finder → iCloud Drive → Marketplace → inbox
- Create a subfolder for each item
- Drag photos in

**Direct in conversation:**
- Paste photos directly into Claude Code chat
- Say "list this on marketplace"

## Example Session

```
You: /marketplace

Claude: Scanning inbox...

Found 2 items ready to process:

📁 cooler (3 photos)
📁 monitor-stand (2 photos)

Which would you like to start with?

You: cooler

Claude: Let me look at the photos...

[Views all 3 photos]

I see a **YETI Tundra 45 Cooler** in **Good** condition.
- Color: White
- Size: 45 qt
- Visible wear: Minor scuffs on exterior, drain plug present
- No cracks or damage to interior

Is that correct?

You: Yes, that's right

Claude: Researching prices...

[WebSearch results]

Pricing for YETI Tundra 45 (Good condition):
- eBay sold: $180-240
- Local FB comps: $160-220

**4-Tier Pricing:**
| Tier | Price | Timeline |
|------|-------|----------|
| Quick Sale | $150 | 24-48 hours |
| Fair Market | $195 | 3-7 days ← Recommended |
| Above Market | $220 | 1-2 weeks |
| Maximum | $240 | Perfect condition premium |

Prices based on eBay sold comps and Indianapolis FB listings. YETI holds value well.

Does this pricing look right, or would you like to adjust?

You: Looks good, go with $195

Claude: Generating listing...

─────────────────────────────────
TITLE: YETI Tundra 45 Cooler White - Good Condition
PRICE: $195
CATEGORY: Sporting Goods > Outdoor & Camping
CONDITION: Good
LOCATION: Indianapolis, IN

DESCRIPTION:
YETI Tundra 45 hard-sided cooler in white. These hold ice for 5+ days and
are built to last — a $350 cooler available for a fraction of the price.

Capacity: 45 quarts (holds ~28 cans with ice)
Color: White
Condition: Good — minor exterior scuffs from normal use. Interior is clean
with no cracks or odors. Drain plug included.

Cash or Venmo. Pickup in Indianapolis. No holds without deposit.
─────────────────────────────────

Sales Tips:
- List Thursday for weekend traffic — coolers move fast in summer
- Bundle with fishing gear if you have any — outdoors buyers often want both
- Mention ice retention time in title if you test it

Photo Coaching:
- Add a photo with the lid open showing the clean interior
- Include something for scale (water bottle works well)

Organizing and saving...
✅ Listing saved: ~/iCloud Drive/Marketplace/2026-03-09-yeti-tundra-45/listing.md
✅ Copied to clipboard — ready to paste into Facebook Marketplace

Want me to create a Todoist task to track posting this?
```

## Complex Workflows

For batch processing multiple items or extended sales coaching, the **marketplace-lister agent** will be used automatically.

**Triggers for agent:**
- "Process everything in my inbox"
- "What should I bundle together?"
- "Help me figure out why things aren't selling"
- "Do a full inbox audit"

## Troubleshooting

### "Inbox not found"

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py init
```

### "iCloud Drive not found"

Enable iCloud Drive in System Settings → Apple ID → iCloud → iCloud Drive.

### Photos not showing in inbox

Ensure photos are in a **subfolder** inside inbox, not directly in the inbox folder:
```
inbox/
├── my-drill/        ← Correct: subfolder with photos
│   ├── photo1.jpg
│   └── photo2.jpg
└── photo.jpg        ← Wrong: photo directly in inbox
```

## Related

- **Skill:** `marketplace-list` — core pipeline (identify → price → list)
- **Agent:** `marketplace-lister` — batch processing and sales coaching
- **Script:** `plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py`
- **References:** `fb-marketplace-fields.md`, `pricing-framework.md`
