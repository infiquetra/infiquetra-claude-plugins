# Changelog

## [1.0.0] - 2026-03-17

### Added
- `unifi-network` skill: full UniFi Network API coverage (devices, clients, networks, firewall, traffic routes, port forwards, WLANs, VPN, DNS, DHCP, stats, backup)
- `unifi-protect` skill: full UniFi Protect API coverage (cameras, PTZ, events, NVR, liveviews, lights, sensors, chimes, viewers)
- Dry-run by default for all write operations — `--confirm` required to execute
- API key auth via `UNIFI_API_KEY` (`X-Api-Key` header) — bypasses CSRF tokens on UniFi OS 3.x+
- SSL verification disabled by default with `urllib3.InsecureRequestWarning` suppressed (UDM uses self-signed cert)
- `unifi-network-ops` agent with investigation workflow, common task examples, and safety rules
- Binary snapshot support: save to file or base64-encode into JSON output
