# eBay Listing Fields Reference

Complete field reference for creating eBay Fixed Price and Auction listings via the Inventory API.

## Title (80 characters max)

eBay search is keyword-driven. Pack the title with searchable terms.

**Formula:** `[Brand] [Model] [Key Spec] [Condition] [Keyword2]`

**Good:** `Cisco SG300-28 28-Port Gigabit Managed Switch Good Home Lab`
**Bad:** `Nice networking switch, works great, barely used`

**Rules:**
- No punctuation (commas, periods, exclamation marks reduce search rank)
- No "free shipping" or pricing (eBay strips it)
- No duplicate words — each word should earn its place
- Include the MPN (manufacturer part number) if known — buyers search by MPN
- Include UPC/EAN if known (improves catalog matching)
- Condition last — saves prime characters for keywords buyers actually search

## Condition Codes

| Code | Label | When to Use |
|------|-------|-------------|
| 1000 | New | Factory sealed, never opened |
| 1500 | New Other | New but not in original packaging |
| 2000 | Certified Refurbished | Manufacturer-certified refurb |
| 2500 | Seller Refurbished | Repaired/cleaned by seller |
| 3000 | Used | General used condition (avoid — too vague) |
| 4000 | Very Good | Minor cosmetic wear, fully functional |
| 5000 | Good | Normal wear and tear, fully functional |
| 6000 | Acceptable | Heavy wear but functional |
| 7000 | For Parts or Not Working | Defective, incomplete, or untested |

**Practical mapping from common condition labels:**
- "Like New" → 4000 (Very Good) or 1500 (New Other)
- "Good" → 5000 (Good)
- "Fair" → 6000 (Acceptable)
- "Poor" → 7000 (For Parts or Not Working)

**Add a condition description:** Always fill in the condition description field with specific details ("minor scratch on top panel, no impact on function, all ports work").

## HTML Description

eBay descriptions render HTML. Use it — plain text looks unprofessional.

**Template:**
```html
<div style="font-family: Arial, sans-serif; max-width: 700px;">
  <h2>[Brand] [Model] — [Condition]</h2>

  <h3>What You're Getting</h3>
  <p>[2-3 sentences: what it is, why someone wants it, what condition it's in]</p>

  <h3>Specifications</h3>
  <ul>
    <li><strong>Brand:</strong> [Brand]</li>
    <li><strong>Model:</strong> [Model]</li>
    <li><strong>Key Spec:</strong> [Value]</li>
    <li><strong>Includes:</strong> [List accessories]</li>
  </ul>

  <h3>Condition Details</h3>
  <p>[Specific condition notes — mention any cosmetic issues, confirm functionality]</p>

  <h3>Shipping</h3>
  <p>Item ships within 1 business day of payment. Carefully packed to arrive safely.</p>

  <h3>Returns</h3>
  <p>30-day returns accepted. Item must be returned in same condition as sold.</p>
</div>
```

**Notes:**
- No JavaScript — eBay strips it
- Inline styles only — no `<style>` blocks
- Keep images out of description — use the photo upload instead
- Mobile renders cleanly with `max-width: 700px`

## Item Specifics

Item specifics are searchable attributes eBay uses for filtered search. **Fill as many as possible** — listings with complete specifics rank higher.

### Universal specifics (always fill)
- **Brand** — Required for most categories
- **Model** — The exact model number/name
- **MPN** (Manufacturer Part Number) — Critical for exact-match search
- **UPC** / **EAN** — If you have the original box or can look it up
- **Color** — Even for electronics ("Black", "Silver")
- **Type** — Sub-category type

### Electronics specifics
- **Compatible Brand** / **Compatible Model** (for peripherals/accessories)
- **Connectivity** (WiFi 6, Bluetooth 5.0, etc.)
- **Interface** (USB-C, PCIe 4.0, etc.)
- **Form Factor** (ATX, mATX, 1U Rack, etc.)
- **Ports** (for networking gear)
- **Operating System** (for software/devices)

### Tools specifics
- **Power Source** (Corded, 20V Battery, Pneumatic)
- **Drive Size** / **Chuck Size**
- **Max RPM**
- **Set Includes** (list contents)

### Clothing specifics (if applicable)
- **Size**, **Size Type**, **Color**, **Material**, **Style**

## Listing Format

### Fixed Price (Good 'Til Cancelled)
- **Best for:** Items with a known market price, electronics, tools, most items
- **Auto-renews** every 30 days (small insertion fee each renewal)
- **Buy It Now** only — buyer clicks Buy and pays immediately
- **Price:** Set at eBay price = FB price ÷ 0.87

### Auction
- **Best for:** Vintage/collectible items, rare items where you're unsure of value, items with strong demand
- **Duration:** 3, 5, 7, or 10 days (7-day recommended)
- **Starting bid:** Set at your floor price (minimum acceptable)
- **Reserve price:** Optional hidden minimum
- **Risk:** Can sell below fair market if traffic is low

**When to use auction:**
- Vintage, antique, or collectible items where price is uncertain
- Items with rabid fan bases (vintage electronics, niche hobby gear)
- You want a fast sale and are OK with market price
- Item has bidding history on eBay showing strong demand

**When NOT to auction:**
- You know the market price — use Fixed Price
- Item is common — not enough demand for auction competition
- You need a specific price to make the deal worthwhile

## Fee Breakdown

eBay charges a **Final Value Fee (FVF)** on the total sale amount (item + shipping).

| Category | FVF Rate | Notes |
|----------|----------|-------|
| Most Electronics | 13.25% | Up to $7,500; 2.35% above |
| Computers/Tablets | 13.25% | |
| Cell Phones | 13.25% | |
| Tools & Hardware | 12.00% | |
| Clothing & Accessories | 15.00% | |
| Books/DVDs/Music | 14.95% | |
| Most other categories | 13.25% | |

**Plus per-order fee:** $0.30 per transaction (deducted from payout)

**Insertion fee:** Free for first 250 listings/month; $0.35 per listing after that (resets monthly)

**Net calculation:**
```
Net payout = eBay price × (1 − FVF%) − $0.30
eBay price = FB price ÷ 0.87    (conservative — covers 13.25% FVF + $0.30 buffer)
```

**Example:**
- FB price: $70
- eBay price: $70 ÷ 0.87 = **$80** (round to nearest dollar)
- eBay FVF (13.25%): −$10.60
- Per-order fee: −$0.30
- Net payout: $69.10 ✓ (nearly matches FB net)

## Return Policy

**30-day free returns** is strongly recommended — listings with free returns rank higher in eBay search and win the algorithm's preference.

Options:
- 30-day free returns (recommended)
- 30-day buyer-pays-return-shipping
- 60-day free returns (maximizes search rank)
- No returns (reduces visibility significantly — avoid)

**Restocking fee:** Not worth it for individual sellers — it discourages buyers.

## Shipping Options

Three models on eBay:

### Calculated Shipping
- Buyer's zip code + item weight/dimensions → real-time carrier rate
- Buyer sees their actual shipping cost at checkout
- Best for: Heavy items, items shipping long distances, items where you want accurate cost recovery
- Set up: Enter package weight + dimensions; eBay calculates rates

### Flat Rate Shipping
- Fixed dollar amount regardless of buyer location
- Best for: Lightweight items where rates don't vary much; simpler setup
- Risk: Overcharging nearby buyers; undercharging distant buyers

### Free Shipping
- You bake shipping into the item price
- Listings with free shipping get slight search ranking boost
- Best for: Light items (< 1 lb) where shipping is $4-6 — easy to bake in
- Not recommended for: Anything over 3 lbs (too much variability)

**eBay carrier preference in Pirate Ship:** UPS > FedEx > USPS depending on weight zone. Always rate-shop in Pirate Ship.

**eBay Guaranteed Delivery:** eBay may show "Guaranteed by [date]" to buyers. To qualify, ship within 1 business day and use a tracked carrier.

## Monthly Seller Limits

New and recently restored accounts have monthly limits:

- **Item limit:** 20 items per month
- **Amount limit:** $1,000 total selling amount per month

These limits reset on the 1st of each month. After 3 months of consistent selling with good feedback, eBay typically increases limits automatically.

**Tracking:** The `ebay_client.py limits` command shows current usage.

**Warning thresholds:**
- At 16/20 items or $800/$1,000: issue warning
- At 20/20 items or $1,000/$1,000: block publish, show upgrade path

## OAuth Scopes Required

```
https://api.ebay.com/oauth/api_scope/sell.inventory
https://api.ebay.com/oauth/api_scope/sell.fulfillment
https://api.ebay.com/oauth/api_scope/sell.account
https://api.ebay.com/oauth/api_scope/commerce.taxonomy.readonly
```

To generate a refresh token: eBay Developer Portal → My Account → User Tokens → Generate Token. Select all scopes above.

## Environment Variables

```bash
EBAY_CLIENT_ID=...        # App ID from developer.ebay.com
EBAY_CLIENT_SECRET=...    # Cert ID (not the Dev ID)
EBAY_REFRESH_TOKEN=...    # Long-lived user token (generated in dev portal)
EBAY_SANDBOX=true         # Optional — use sandbox for testing
```
