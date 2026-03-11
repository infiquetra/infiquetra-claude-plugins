# Platform Selection Guide

## Platform Overview

| | FB Marketplace | Mercari | eBay |
|---|---|---|---|
| **Fees** | Free for local sales | 10% selling fee | ~13.25% FVF + $0.30/order |
| **Audience** | Local Indianapolis buyers | Nationwide buyers | Global buyers |
| **Shipping** | Local pickup default | Prepaid labels (~54% off retail) | Calculated, flat, or free |
| **API** | None (manual) | None (manual) | Full REST API (automated) |
| **Title limit** | 100 characters | 80 characters | 80 characters |
| **Description** | 5,000 chars, no markdown | 1,000 chars, up to 3 hashtags | HTML, no hard limit |
| **Photos** | Up to 10 | Up to 12 | Up to 24 |
| **Best for** | Large/heavy items, local-only | Electronics, small/medium items | Brand-name, collectibles, items with MPN |

## Platform Recommendation Decision Tree

### Step 1: Is the item large or heavy?

**If yes (furniture, appliances, anything > 30 lbs, or fragile/risky to ship):**
→ **FB Marketplace only** — local pickup is the right call

**If no → Step 2**

### Step 2: Is the price under $20?

**If yes:**
→ **FB Marketplace only** — shipping economics don't work at this price point (shipping often costs $5–10 which is 25–50% of the item value)

**If no → Step 3**

### Step 3: Does nationwide demand help this item?

**High nationwide demand (list on FB + Mercari):**
- Electronics (especially networking gear, home lab equipment, computer components)
- Name-brand tools (DeWalt, Milwaukee, Snap-on)
- Collectibles, vintage items, niche hobby gear
- Any item where local Indianapolis buyer pool is small

**Primarily local demand (FB Marketplace only):**
- Furniture
- Appliances
- Baby/kids items (parents prefer local pickup to inspect)
- Large sporting goods (bikes, exercise equipment)
- Anything where condition is best verified in person

**Default recommendation:** List on both FB Marketplace and Mercari for maximum exposure.

### Step 4: Should you also list on eBay?

eBay is recommended when the item meets **all** of these:
1. Nationwide buyer pool helps (same criteria as Mercari)
2. Item has a brand name, MPN, or UPC buyers search by exact model
3. Price is high enough to absorb ~13.25% fees (generally $30+)

**eBay recommended for:**
- Electronics with known models (networking gear, CPUs, GPUs, audio equipment)
- Name-brand tools (buyers search exact model numbers)
- Collectibles and vintage items
- Items with MPN/UPC that eBay can match to its catalog (better search visibility)
- Anything where reaching the widest possible audience maximizes sale price

**eBay NOT recommended for:**
- Heavy items (> 20 lbs) — shipping makes economics worse
- Generic/unbranded items without model numbers
- Items under $30 — fees eat too much of the margin
- Items best evaluated in person (furniture, appliances)

**eBay advantage:** Full API integration means Claude can publish, check status, add tracking, and manage messages programmatically — no manual copy-paste needed.

**eBay API workflow:** See Step 7 in the skill pipeline for the interactive publish flow.

## Ship vs. Local Decision

### Ship if ALL of these are true:
- Item weighs < 10 lbs
- Selling price > $25
- Item can be safely packaged (not extremely fragile or oddly shaped)

### Local only if ANY of these are true:
- Item weighs > 20 lbs
- Item is very fragile and can't be well-packaged
- Price is < $20 (shipping eats profit)
- Item is large/bulky regardless of weight

### Gray zone (5–20 lbs, $25–50):
- Check shipping cost estimate vs. item price
- If shipping > 25% of item price, lean local-only
- If buyer can pay shipping separately, shipping is less of an issue

## Price Adjustment by Platform

When listing on multiple platforms, adjust prices so net proceeds are similar:

| Platform | Adjustment | Formula | Example (FB $70) |
|----------|-----------|---------|-----------------|
| FB Marketplace | Base price | $70 | $70 |
| Mercari | +11% to cover 10% fee | FB ÷ 0.90 | $70 ÷ 0.90 = **$78** |
| eBay | +15% to cover 13.25% FVF + $0.30 | FB ÷ 0.87 | $70 ÷ 0.87 = **$80** |

Round to the nearest $1 for all non-FB platforms.

**eBay net calculation check:**
- List at $80
- eBay FVF (13.25%): −$10.60
- Per-order fee: −$0.30
- Net payout: **$69.10** ≈ FB net ✓

## Listing Strategy by Item Type

### Electronics (networking, computers, audio)
- **Platforms:** Both FB + Mercari
- **Shipping:** Ship if < 10 lbs
- **Why Mercari:** Nationwide home lab / enthusiast community pays fair prices; not dependent on Indianapolis tech buyers

### Power Tools
- **Platforms:** Both FB + Mercari (brand-name tools sell nationally)
- **Shipping:** Ship if < 10 lbs (most hand tools qualify; larger power tools local-only)
- **Why FB:** Local contractors browse FB regularly

### Furniture
- **Platforms:** FB Marketplace only
- **Shipping:** Local pickup always
- **Why:** Furniture is too large/heavy to ship affordably; local buyers prefer to inspect

### Sporting Goods (coolers, camping gear, fitness equipment)
- **Small gear (< 5 lbs):** Both platforms + ship
- **Large gear (coolers > 45qt, exercise equipment):** FB only, local pickup
- **Bikes:** FB only, local pickup

### Clothing / Fashion
- **Platforms:** Mercari preferred (better clothing buyer base nationally)
- **FB:** Only if brand-name or high value
- **Shipping:** Always ship for clothing

## Indianapolis Market Notes

- FB Marketplace is active here — strong local buyer pool for furniture, tools, outdoor gear
- Electronics buyers are fewer locally — Mercari nationwide audience helps
- Indianapolis prices run 10–15% below coastal markets on FB; Mercari is a national market with higher prices
- Best FB posting days: Thursday–Sunday (weekend browsing traffic)
- Mercari: less time-sensitive, active all week
