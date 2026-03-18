# UniFi Network API Endpoints Reference

Base URL pattern: `https://<UNIFI_HOST>/proxy/network/api/s/<site>/`

All requests use the `X-Api-Key` header for authentication on UniFi OS 3.x+. SSL verification is disabled (UDM uses a self-signed certificate).

---

## Devices

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/stat/device` | List all adopted devices |
| GET | `/proxy/network/api/s/{site}/stat/device/{mac}` | Get device by MAC address |
| POST | `/proxy/network/api/s/{site}/cmd/devmgr` | Device management commands (restart, upgrade, locate) |

**Device management command body examples**:
```json
{ "cmd": "restart", "mac": "aa:bb:cc:dd:ee:ff" }
{ "cmd": "upgrade", "mac": "aa:bb:cc:dd:ee:ff" }
{ "cmd": "set-locate", "mac": "aa:bb:cc:dd:ee:ff" }
{ "cmd": "unset-locate", "mac": "aa:bb:cc:dd:ee:ff" }
```

---

## Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/stat/sta` | List active (currently connected) clients |
| GET | `/proxy/network/api/s/{site}/stat/alluser` | List all clients including historical |
| POST | `/proxy/network/api/s/{site}/cmd/stamgr` | Client management commands (block, unblock) |

**Client management command body examples**:
```json
{ "cmd": "block-sta", "mac": "aa:bb:cc:dd:ee:ff" }
{ "cmd": "unblock-sta", "mac": "aa:bb:cc:dd:ee:ff" }
```

---

## Networks (VLANs / Network Configurations)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/rest/networkconf` | List all network configurations |
| POST | `/proxy/network/api/s/{site}/rest/networkconf` | Create a new network |
| PUT | `/proxy/network/api/s/{site}/rest/networkconf/{id}` | Update a network by ID |
| DELETE | `/proxy/network/api/s/{site}/rest/networkconf/{id}` | Delete a network by ID |

**Network create body example**:
```json
{
  "name": "IoT",
  "purpose": "corporate",
  "vlan": 30,
  "ip_subnet": "10.220.30.1/24",
  "dhcpd_enabled": true,
  "dhcpd_start": "10.220.30.100",
  "dhcpd_stop": "10.220.30.254"
}
```

---

## Firewall Rules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/rest/firewallrule` | List all firewall rules |
| POST | `/proxy/network/api/s/{site}/rest/firewallrule` | Create a firewall rule |
| PUT | `/proxy/network/api/s/{site}/rest/firewallrule/{id}` | Update a firewall rule |
| DELETE | `/proxy/network/api/s/{site}/rest/firewallrule/{id}` | Delete a firewall rule |

**Firewall rule body example**:
```json
{
  "name": "Block IoT to LAN",
  "ruleset": "LAN_IN",
  "rule_index": 2000,
  "action": "drop",
  "enabled": true,
  "src_networkconf_id": "<iot_network_id>",
  "dst_networkconf_id": "<lan_network_id>",
  "protocol": "all",
  "src_firewallgroup_ids": [],
  "dst_firewallgroup_ids": []
}
```

**Ruleset values**: `LAN_IN`, `LAN_OUT`, `LAN_LOCAL`, `WAN_IN`, `WAN_OUT`, `WAN_LOCAL`, `GUEST_IN`, `GUEST_OUT`, `GUEST_LOCAL`

---

## Traffic Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/rest/routing` | List all traffic routes |
| POST | `/proxy/network/api/s/{site}/rest/routing` | Create a traffic route |
| PUT | `/proxy/network/api/s/{site}/rest/routing/{id}` | Update a traffic route |
| DELETE | `/proxy/network/api/s/{site}/rest/routing/{id}` | Delete a traffic route |

---

## Port Forwards

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/rest/portforward` | List all port forwards |
| POST | `/proxy/network/api/s/{site}/rest/portforward` | Create a port forward |
| PUT | `/proxy/network/api/s/{site}/rest/portforward/{id}` | Update a port forward |
| DELETE | `/proxy/network/api/s/{site}/rest/portforward/{id}` | Delete a port forward |

**Port forward body example**:
```json
{
  "name": "Plex",
  "fwd": "10.220.1.50",
  "fwd_port": "32400",
  "dst_port": "32400",
  "proto": "tcp",
  "enabled": true
}
```

---

## WLANs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/rest/wlanconf` | List all wireless networks |
| PUT | `/proxy/network/api/s/{site}/rest/wlanconf/{id}` | Update a wireless network |

---

## VPN Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/stat/vpn` | List active VPN clients |

---

## DNS (Static Host Records)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/rest/setting/dnsmasq` | Get DNS/DHCP settings including static records |
| POST | `/proxy/network/api/s/{site}/rest/setting/dnsmasq` | Create a static DNS record |
| DELETE | `/proxy/network/api/s/{site}/rest/setting/dnsmasq/{id}` | Delete a static DNS record |

**DNS record body example**:
```json
{
  "key": "proxmox.home",
  "value": "10.220.1.7",
  "record_type": "A"
}
```

---

## DHCP Leases

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/stat/dhcp_lease` | List all active DHCP leases |

---

## Stats & Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/network/api/s/{site}/stat/health` | Network subsystem health summary |
| GET | `/proxy/network/api/s/{site}/stat/sysinfo` | System info (firmware version, uptime, etc.) |
| GET | `/proxy/network/api/s/{site}/stat/event` | Recent network events |
| GET | `/proxy/network/api/s/{site}/stat/alarm` | Active alarms |

**Event query params**: `?_limit=50&_start=0`

---

## Backup

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/proxy/network/api/s/{site}/cmd/system` | Trigger backup with `{"cmd":"backup"}` |
| GET | `/proxy/network/api/s/{site}/dl/backup` | Download latest backup file |

---

## API Version Notes

- **UniFi OS 3.x+**: Use `X-Api-Key` header with a generated API key. No session cookie or CSRF token required.
- **UniFi OS 2.x and earlier**: Requires session-based auth (POST `/api/auth/login`) and `X-Csrf-Token` header. Not supported by this client.
- **v1 vs v2**: Most Network API endpoints use the `/proxy/network/api/s/{site}/` path (v1-style). UniFi OS 3.x also exposes some endpoints under `/proxy/network/v2/api/site/{site}/` — these are used for newer features like traffic routes and some settings. The client uses the appropriate path per resource.
- **Site**: Almost always `default` unless multi-site is configured on the UDM.
