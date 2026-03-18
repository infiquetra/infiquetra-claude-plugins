# UniFi Plugin

Claude Code plugin for managing UniFi Network infrastructure and UniFi Protect cameras via the UniFi OS API. Follows the PagerDuty/Slack CLI pattern for full auditability — no MCP server, no third-party dependencies beyond `requests`.

## Skills

| Skill | Script | Purpose |
|---|---|---|
| `unifi-network` | `unifi_network_client.py` | Devices, clients, VLANs, firewall, routing, VPN, DNS, stats |
| `unifi-protect` | `unifi_protect_client.py` | Cameras, PTZ, events, NVR, liveviews, lights, sensors |

## Setup

### 1. Generate API Key

In UniFi OS → Settings → API Keys, generate a new key with appropriate scope.

### 2. Set Environment Variables

```bash
export UNIFI_API_KEY="your-api-key"    # required
export UNIFI_HOST="10.220.1.1"         # optional, default: 10.220.1.1
export UNIFI_SITE="default"            # optional, default: default (network only)
```

### 3. Install Dependencies

```bash
pip install requests
```

## Safety: Dry-Run by Default

**All write operations preview without executing.** Pass `--confirm` to execute:

```bash
# Shows what WOULD happen (safe to run anytime)
python unifi_network_client.py firewall create --json '{"name":"Block IoT","action":"drop"}'

# Actually creates the rule
python unifi_network_client.py firewall create --json '{"name":"Block IoT","action":"drop"}' --confirm
```

Dry-run output:
```json
{
  "dry_run": true,
  "action": "POST",
  "endpoint": "https://10.220.1.1/proxy/network/api/s/default/rest/firewallrule",
  "message": "Pass --confirm to execute this operation",
  "payload": {"name": "Block IoT", "action": "drop"}
}
```

## Network Client

```bash
# Devices
python unifi_network_client.py devices list
python unifi_network_client.py devices get --mac aa:bb:cc:dd:ee:ff
python unifi_network_client.py devices restart --mac aa:bb:cc:dd:ee:ff --confirm
python unifi_network_client.py devices upgrade --mac aa:bb:cc:dd:ee:ff --confirm

# Clients
python unifi_network_client.py clients list
python unifi_network_client.py clients list-history
python unifi_network_client.py clients block --mac aa:bb:cc:dd:ee:ff --confirm
python unifi_network_client.py clients unblock --mac aa:bb:cc:dd:ee:ff --confirm

# Networks (VLANs)
python unifi_network_client.py networks list
python unifi_network_client.py networks create --json '{"name":"IoT","purpose":"corporate","vlan":30}' --confirm
python unifi_network_client.py networks delete --id <id> --confirm

# Firewall Rules
python unifi_network_client.py firewall list
python unifi_network_client.py firewall create --json '{"name":"Block IoT","action":"drop","ruleset":"LAN_IN"}' --confirm

# Traffic Routes
python unifi_network_client.py traffic-routes list
python unifi_network_client.py traffic-routes create --json '{"name":"IoT via VPN","enabled":true}' --confirm

# Port Forwards
python unifi_network_client.py port-forwards list
python unifi_network_client.py port-forwards create --json '{"name":"Plex","fwd":"10.220.1.50","fwd_port":32400,"dst_port":32400,"proto":"tcp"}' --confirm

# WLANs
python unifi_network_client.py wlans list
python unifi_network_client.py wlans update --id <id> --json '{"enabled":false}' --confirm

# VPN
python unifi_network_client.py vpn list-clients
python unifi_network_client.py vpn list-servers

# DNS (Static Records)
python unifi_network_client.py dns list
python unifi_network_client.py dns create --json '{"key":"proxmox.home","value":"10.220.1.7","record_type":"A"}' --confirm

# DHCP Leases
python unifi_network_client.py dhcp list-leases

# Stats & Health
python unifi_network_client.py stats health
python unifi_network_client.py stats sysinfo
python unifi_network_client.py stats events --limit 20
python unifi_network_client.py stats alarms

# Backup
python unifi_network_client.py backup list
python unifi_network_client.py backup create --confirm
```

## Protect Client

```bash
# Cameras
python unifi_protect_client.py cameras list
python unifi_protect_client.py cameras get --id <camera_id>
python unifi_protect_client.py cameras snapshot --id <camera_id> --output /tmp/snap.jpg
python unifi_protect_client.py cameras snapshot --id <camera_id>   # base64 JSON output
python unifi_protect_client.py cameras stream-url --id <camera_id>
python unifi_protect_client.py cameras update --id <camera_id> --json '{"name":"Driveway"}' --confirm

# PTZ Control
python unifi_protect_client.py ptz list-presets --id <camera_id>
python unifi_protect_client.py ptz goto-preset --id <camera_id> --preset-id 1 --confirm
python unifi_protect_client.py ptz patrol-start --id <camera_id> --confirm
python unifi_protect_client.py ptz patrol-stop --id <camera_id> --confirm

# Events
python unifi_protect_client.py events list
python unifi_protect_client.py events list --type motion --limit 20
python unifi_protect_client.py events list --type smartDetectZone
python unifi_protect_client.py events get --id <event_id>

# NVR
python unifi_protect_client.py nvr info

# Liveviews
python unifi_protect_client.py liveviews list
python unifi_protect_client.py liveviews create --json '{"name":"Security","slots":[]}' --confirm
python unifi_protect_client.py liveviews delete --id <id> --confirm

# Lights, Sensors, Chimes, Viewers
python unifi_protect_client.py lights list
python unifi_protect_client.py lights update --id <id> --json '{"lightModeSettings":{"mode":"motion"}}' --confirm
python unifi_protect_client.py sensors list
python unifi_protect_client.py chimes list
python unifi_protect_client.py viewers list
```

## API Notes

- **Auth**: `X-Api-Key` header bypasses CSRF token requirement on UniFi OS 3.x+
- **SSL**: UDM uses a self-signed certificate; SSL verification is disabled by default with warnings suppressed
- **Site**: Network API uses site-scoped endpoints (`/api/s/{site}/`); Protect API is site-agnostic
- **API versions**: Most network endpoints use v1 (`/proxy/network/api/s/{site}/`); traffic routes and DNS use v2 (`/proxy/network/v2/api/site/{site}/`)

## Testing

```bash
# Run all UniFi tests
pytest tests/test_unifi_network_client.py tests/test_unifi_protect_client.py -v

# Run with coverage
pytest tests/test_unifi_network_client.py tests/test_unifi_protect_client.py --cov=plugins/unifi
```

## Smoke Tests (requires live UDM)

```bash
export UNIFI_API_KEY="your-key"

# Network
python plugins/unifi/skills/unifi-network/scripts/unifi_network_client.py stats health
python plugins/unifi/skills/unifi-network/scripts/unifi_network_client.py devices list

# Protect
python plugins/unifi/skills/unifi-protect/scripts/unifi_protect_client.py nvr info
python plugins/unifi/skills/unifi-protect/scripts/unifi_protect_client.py cameras list
```
