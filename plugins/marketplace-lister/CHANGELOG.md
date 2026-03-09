# Changelog

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
