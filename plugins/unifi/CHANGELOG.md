# Changelog

## [1.2.0] - 2026-07-05

### Changed
- Both `unifi-network` and `unifi-protect` clients adopt the shared fleet-commons `retry_backoff`
  primitive (#348): a 429 response now retries with bounded exponential backoff (honoring
  `Retry-After`) instead of hard-exiting, preserving the existing typed error surface on
  exhaustion. Vendors the byte-identical `fleet_commons_shim.py` into each client dir (drift-guarded).

## [1.1.0] - 2026-06-21

### Changed
- `unifi-network-ops` agent: add frontmatter and pin `model: sonnet` (R1/R2a tiering;
  network ops are structured/investigative, not judgment-heavy decisions).

## [1.0.0] - 2026-03-17

### Added
- `unifi-network` skill: full UniFi Network API coverage (devices, clients, networks, firewall, traffic routes, port forwards, WLANs, VPN, DNS, DHCP, stats, backup)
- `unifi-protect` skill: full UniFi Protect API coverage (cameras, PTZ, events, NVR, liveviews, lights, sensors, chimes, viewers)
- Dry-run by default for all write operations — `--confirm` required to execute
- API key auth via `UNIFI_API_KEY` (`X-Api-Key` header) — bypasses CSRF tokens on UniFi OS 3.x+
- SSL verification disabled by default with `urllib3.InsecureRequestWarning` suppressed (UDM uses self-signed cert)
- `unifi-network-ops` agent with investigation workflow, common task examples, and safety rules
- Binary snapshot support: save to file or base64-encode into JSON output
