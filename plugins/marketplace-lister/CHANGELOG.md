# Changelog

## [3.0.0] - 2026-03-11

### Added

- **eBay platform support** — Full eBay listing generation with HTML description, condition codes (1000/1500/4000/5000/6000/7000), item specifics, listing format (fixed/auction), and eBay price (FB ÷ 0.87 to cover 13.25% FVF + $0.30)
- **`ebay_client.py`** — New eBay REST API client with:
  - `EBayAuth` — OAuth 2.0 token management with token caching, sandbox support, auto-retry on 401
  - `EBayAPI` — REST wrapper for eBay Inventory, Taxonomy, Fulfillment, and Messaging APIs
  - `publish` — Queries eBay taxonomy for category suggestions and item aspects; returns review data for Claude
  - `publish-confirm` — Uploads photos (with optional HEIC→JPEG via Pillow), creates inventory item, creates offer, publishes listing; saves `ebay.json` per item
  - `status` — Checks listing status for one item or all organized items
  - `relist` — Re-publishes ended listings
  - `revise` — Updates active listing fields
  - `ship` — Adds shipping fulfillment with tracking number after a sale
  - `messages` — Views recent buyer messages
  - `limits` — Shows monthly limit usage with warnings at 80% capacity
  - `categories` — Searches eBay taxonomy by keyword
- **Monthly limit tracking** (`ebay-limits.json`) — Tracks 20-item/$1,000 monthly limits; warns at 80%, blocks at 100%
- **Per-item eBay state** (`ebay.json`) — Saves listing ID, offer ID, SKU, status, price, URL, views, watchers
- **eBay section in `listing.md`** — Title, price, category, condition code, format, item specifics, HTML description
- **eBay section in `post.md`** — Part of multi-platform format with `═` section headers
- **`--platform ebay` on `copy`** — Extracts eBay HTML description from post.md
- **Interactive eBay publish flow in SKILL.md** — Step 7: category confirmation, item specifics review, format selection, shipping options, return policy, photo order, final summary with limits check
- `references/ebay-fields.md` — eBay condition codes, HTML description template, item specifics by category, fee breakdown, listing format guidance, return policy, shipping options, OAuth scopes

### Changed

- **Multi-platform detection fixed** — `post.md` format now uses `len(platforms) > 1` instead of `if "mercari" in platforms` — correctly triggers multi-platform format when any two platforms are selected
- `listing` command JSON schema extended with `ebay_title`, `ebay_description`, `ebay_category`, `condition_code`, `listing_format`, `listing_duration`, `item_specifics`, `ebay_shipping`, `return_policy`, `pricing.ebay_price`
- `references/platform-selection.md` — Added eBay column to comparison table; added eBay decision tree and eBay price row
- `references/pricing-framework.md` — Added platform price tier table (FB/Mercari/eBay) with fee breakdown
- `references/shipping-guide.md` — Added eBay shipping section (calculated/flat/free, carrier options, Global Shipping Program, packaging notes)
- `references/listing-improvement-checklist.md` — Added eBay-specific photo, title, description, and pricing checks
- SKILL.md pipeline extended to 8 steps (was 7); Step 4.5 adds eBay recommendation logic; Step 5 adds eBay listing template; Step 6 updates JSON schema; Step 7 adds full eBay API publish flow
- `agents/marketplace-lister.md` — Updated for eBay batch management (status checks, fulfillment); updated reference list
- `commands/marketplace.md` — Added eBay triggers, eBay API section, environment variable instructions
- `plugin.json` — Version bumped to 3.0.0; updated description; added "ebay" and "api" keywords
- README.md — Added eBay features, ebay_client.py reference, eBay setup instructions, state file documentation

## [2.0.0] - 2026-03-09

### Added

- **Smart inbox grouping** — `group` command detects loose photos in inbox and proposes item groupings by filename sequence gaps (gap ≥ 5 = new item)
- **`create-folder` command** — Creates a named subfolder and moves specified photos into it; used after grouping confirmation
- **Mercari platform support** — Full Mercari listing generation with platform-optimized title (80 char), description (1,000 char + hashtags), and price (11% above FB to cover 10% fee)
- **Multi-platform `post.md`** — post.md now has per-platform sections with `═` headers when listing on multiple platforms
- **`--platform` flag on `copy`** — `copy --platform fb|mercari` extracts content from the correct platform section
- **Shipping guidance** — `listing` command accepts `shipping` JSON field; writes Shipping section to listing.md
- **Step 4.5 (Platform Selection)** — SKILL.md pipeline step recommends which platform(s) based on item size, weight, and price
- **Step 5.5 (Review & Improve)** — SKILL.md pipeline step presents photo/title/description suggestions before saving, waits for user approval
- `references/mercari-fields.md` — Mercari listing fields, fee structure, shipping rates, platform tips
- `references/platform-selection.md` — Platform recommendation decision tree, ship vs. local logic, price adjustment formulas
- `references/shipping-guide.md` — Starter kit, Pirate Ship setup, carrier selection by weight, packaging tips, DIM weight warning
- `references/listing-improvement-checklist.md` — Checklist Claude uses in Step 5.5 to generate improvement suggestions
- `scan` command now also reports `loose_photos` and `loose_count` fields

### Changed

- `listing` command JSON schema extended with `mercari_title`, `mercari_description`, `mercari_category`, `pricing.mercari_price`, `shipping`, `platforms` fields
- SKILL.md fully rewritten — 10-step pipeline (was 7 steps) with inbox triage, platform selection, and improvement review
- `agents/marketplace-lister.md` — Updated for multi-platform batch processing; includes inbox triage step
- `commands/marketplace.md` — Updated examples showing v2 workflow
- `plugin.json` — Version bumped to 2.0.0
- `marketplace.json` — Version bumped to 2.0.0, added mercari/shipping keywords

## [1.0.0] - 2026-03-09

### Added
- Initial release
- `marketplace_client.py` — filesystem CLI for iCloud Drive Marketplace management
  - `init` — create iCloud Marketplace directory structure
  - `scan` — list inbox folders with photo counts
  - `photos` — list image files in a folder
  - `organize` — move inbox folder to dated organized location
  - `unidentified` — move unidentifiable items to unidentified/
  - `listing` — write listing.md from structured JSON
  - `status` — list all organized items
- `marketplace-list` skill — interactive pipeline: identify → price → list → organize
- `marketplace-lister` agent — batch processing and extended sales coaching
- `/marketplace` slash command
- `fb-marketplace-fields.md` reference — FB form fields, categories, condition values
- `pricing-framework.md` reference — 4-tier methodology, query templates, Indianapolis market
