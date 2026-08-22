# Changelog

## [Unreleased]

### Fixed - documentation now matches the shipped clients (upstream repair, not yet released)

- Removed every reference to the four UniFi Protect capabilities the client does not
  implement — camera stream URLs, PTZ control, event listing, and NVR info. They were
  deleted from `unifi_protect_client.py` in commit `8a14ad49` on 2026-03-17, when the
  Protect base URL moved to `/proxy/protect/integration/v1`, and no changelog entry ever
  recorded the removal. Surfaces corrected: the Protect skill, the Protect API reference,
  the plugin README, the slash command document, the `unifi-network-ops` agent definition,
  the plugin manifest description, and the 1.0.0 entry below.
- Re-derived `references/protect-api-endpoints.md` from the client source. It documented the
  cookie-authenticated `/proxy/protect/api` base, which this client has never called, and
  gave `PATCH` for a liveview update the client sends as `PUT`.
- Corrected `references/udm-api-endpoints.md` on every path where it disagreed with the
  network client: traffic routes are v2 `trafficroutes` rather than v1 `rest/routing`;
  static DNS is v2 `static-dns` rather than the v1 `rest/setting/dnsmasq` settings object;
  DHCP leases are `stat/dhcp` rather than `stat/dhcp_lease`; alarms are `list/alarm` rather
  than `stat/alarm`; backup is `stat/backup` plus `cmd/backup` rather than `cmd/system` plus
  `dl/backup`; the VPN group is three `vpnconn` paths rather than one `stat/vpn`; and the
  device-locate body is a single `locate` command rather than a `set-locate` and
  `unset-locate` pair.

### Added - previously undocumented network capabilities

- The network skill now documents all twelve resource groups and all fifty-two actions the
  client implements. The `wlans`, `vpn`, and `backup` groups were entirely undocumented, as
  were the `devices adopt`, `devices forget`, and `stats dpi` actions.
- The Protect skill now documents all six resource groups and all twenty-one actions.
- `tests/test_unifi_docs_match_code.py` asserts the agreement mechanically against the real
  argument parsers and the client sources, so this class of drift fails a build instead of
  surviving five months unnoticed.

### Changed - skill frontmatter conforms to the open Agent Skills specification

- Both skills drop the non-specification `triggers` and `script` frontmatter fields. Their
  content moved into each skill's body as a "When to use this skill" list and a "Script"
  line, so nothing is lost and the frontmatter carries only permitted fields.

## [1.2.1] - 2026-08-08

### Added - house-style presentation contract on the network-ops agent (#704)

- `unifi-network-ops` agent definition gains a "Presentation contract (Infiquetra house style)" section, copied verbatim from `plugins/house-style/references/subagent-presentation-preamble.md`.

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
- `unifi-protect` skill: UniFi Protect Integration API coverage (cameras, liveviews, lights, sensors, chimes, viewers)
- Dry-run by default for all write operations — `--confirm` required to execute
- API key auth via `UNIFI_API_KEY` (`X-Api-Key` header) — bypasses CSRF tokens on UniFi OS 3.x+
- SSL verification disabled by default with `urllib3.InsecureRequestWarning` suppressed (UDM uses self-signed cert)
- `unifi-network-ops` agent with investigation workflow, common task examples, and safety rules
- Binary snapshot support: save to file or base64-encode into JSON output
