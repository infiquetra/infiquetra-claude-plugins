# /marketplace - Multi-Platform Marketplace Listing Tool

Identify items from photos, research pricing, and generate ready-to-post listings for Facebook Marketplace and Mercari.

## Usage

```bash
/marketplace              # Scan inbox and start processing
/marketplace scan         # Show inbox contents without processing
/marketplace status       # Show all current organized listings
```

## What It Does

The `/marketplace` command activates the **marketplace-list** skill which:

1. **Triages inbox** — Groups loose photos into items automatically (no manual subfolders needed)
2. **Identifies items** — Uses Claude's vision to identify brand, model, condition
3. **Researches pricing** — WebSearch for eBay sold comps and local FB prices
4. **Selects platforms** — Recommends FB Marketplace and/or Mercari based on item size, weight, and price
5. **Generates listings** — Platform-optimized copy for each selected platform
6. **Reviews & improves** — Suggests photo/title/description improvements before saving
7. **Organizes files** — Moves folder to dated location, writes listing.md + post.md
8. **Copies to clipboard** — Platform-specific listing text ready to paste

## Quick Actions

```bash
/marketplace                          # Check inbox and start
/marketplace scan                     # See what's in inbox
/marketplace status                   # See all organized listings
```

Or say naturally:
- "list on marketplace"
- "list on mercari"
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
├── inbox/          ← Drop photos here (subfolders or loose)
└── unidentified/   ← Items Claude couldn't identify
```

### 2. Add Items to Inbox

**New in v2 — Just dump photos directly:**
- Drop all photos into `inbox/` directly (no subfolders needed)
- Claude will group them into items automatically based on photo sequence

**Or use subfolders (still works):**
- Create a subfolder in inbox/ for each item
- Drag photos in

**From iPhone:**
1. Photograph items
2. Open Files app → iCloud Drive → Marketplace → inbox
3. Drop photos in (Claude handles grouping)

**Direct in conversation:**
- Paste photos directly into Claude Code chat
- Say "list this on marketplace"

## Example Session

```
You: /marketplace

Claude: Scanning inbox...

Found 14 loose photos. Grouping by sequence...

Proposed groups:
📁 Group 1 (IMG_2670–2672): 3 photos — appears to be a network switch
📁 Group 2 (IMG_2673–2676): 4 photos — appears to be server rack rails
📁 Group 3 (IMG_2677–2683): 7 photos — looks like 2 items (different objects)

Does this look right? I can split Group 3 if needed.

You: Group 3 is a drill and a level, split them at IMG_2680

Claude: Got it. Creating 4 item folders...
✅ group-1 (3 photos)
✅ group-2 (4 photos)
✅ group-3a (3 photos) ← drill
✅ group-3b (4 photos) ← level

Which item do you want to start with?

You: the switch

Claude: Let me look at the photos...

I see a **Cisco SG300-28 28-Port Gigabit Managed Switch** in **Good** condition.
- 28 × Gigabit ports
- Rack mountable, ears included
- Minor cosmetic wear on top, no damage
- Estimated weight: ~5 lbs

Is that correct?

You: Yes

Claude: Researching prices...

Pricing for Cisco SG300-28 (Good condition):
- eBay sold: $65-95
- Local FB comps: $55-80

4-Tier Pricing:
| Tier | Price | Timeline |
|------|-------|----------|
| Quick Sale | $55 | 24-48 hours |
| Fair Market | $70 | 3-7 days ← Recommended |
| Above Market | $80 | 1-2 weeks |
| Maximum | $95 | Perfect condition |

Platform recommendation:
- ✅ Facebook Marketplace ($70) — local pickup, free
- ✅ Mercari ($78) — nationwide home lab buyers, 10% fee
- 📦 Shipping: ~5 lbs → USPS Ground Advantage via Pirate Ship (~$9-11)

Does this pricing and platform recommendation work?

You: Yes, looks good

Claude: Generating listings...

[Shows FB listing and Mercari listing side by side]

Suggested improvements:
📸 Photos: Add a photo with LEDs lit (shows it powers on)
✏️ Mercari title: Add "home lab" — that community searches for it

Apply these? [Yes, all / Skip]

You: Yes

Claude: Organizing and saving...
✅ Listing saved: ~/iCloud Drive/Marketplace/2026-03-09-cisco-sg300-switch/listing.md
✅ FB listing copied to clipboard — paste into Facebook Marketplace
💡 For Mercari: run `copy --platform mercari` when ready to post there
```

## Copying Platform-Specific Listings

After organizing, copy each platform's listing separately:

```bash
# Copy FB description
python3 marketplace_client.py copy --folder <path> --field description --platform fb | pbcopy

# Copy Mercari description
python3 marketplace_client.py copy --folder <path> --field description --platform mercari | pbcopy

# Copy Mercari title
python3 marketplace_client.py copy --folder <path> --field title --platform mercari | pbcopy
```

## Complex Workflows

For batch processing multiple items, the **marketplace-lister agent** will be used automatically.

**Triggers for agent:**
- "Process everything in my inbox"
- "What should I bundle together?"
- "Help me figure out why things aren't selling"
- "Do a full inbox audit"
- "List all my items on both FB and Mercari"

## Troubleshooting

### "Inbox not found"

```bash
python3 plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py init
```

### "iCloud Drive not found"

Enable iCloud Drive in System Settings → Apple ID → iCloud → iCloud Drive.

### Photos not grouping correctly

The grouping algorithm uses filename sequence gaps (IMG_XXXX numbering). If photos group incorrectly, you can manually adjust after Claude presents the grouping — or create subfolders manually as in v1.

## Related

- **Skill:** `marketplace-list` — core pipeline (triage → identify → price → platform select → list → improve → organize)
- **Agent:** `marketplace-lister` — batch processing and sales coaching
- **Script:** `plugins/marketplace-lister/skills/marketplace-list/scripts/marketplace_client.py`
- **References:** `fb-marketplace-fields.md`, `mercari-fields.md`, `platform-selection.md`, `shipping-guide.md`, `pricing-framework.md`
