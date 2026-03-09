# Changelog

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
