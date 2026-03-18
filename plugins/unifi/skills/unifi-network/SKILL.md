---
name: unifi-network
description: Manage UniFi network infrastructure — devices, clients, VLANs, firewall rules, traffic routes, port forwards, VPN, DNS, DHCP, and stats — via the UniFi OS API
triggers:
  - "show unifi devices"
  - "list unifi clients"
  - "block client"
  - "unifi firewall"
  - "create vlan"
  - "unifi network"
  - "port forward"
  - "vpn clients"
  - "dns record"
  - "network health"
  - "unifi stats"
script: ./scripts/unifi_network_client.py
---

# UniFi Network Skill

Interacts with the UniFi Network API on a UniFi Dream Machine (UDM) to manage network infrastructure.

## Environment Setup

```bash
export UNIFI_API_KEY="your-api-key"          # required
export UNIFI_HOST="10.220.1.1"               # optional, default: 10.220.1.1
export UNIFI_SITE="default"                  # optional, default: default
```

Generate an API key in UniFi OS → Settings → API Keys.

## Safety: Dry-Run by Default

All write operations preview what they will do without executing. Pass `--confirm` to execute:

```bash
# Preview (safe)
python unifi_network_client.py networks create --json '{"name":"IoT","vlan":30}'

# Execute
python unifi_network_client.py networks create --json '{"name":"IoT","vlan":30}' --confirm
```

## Commands

### Devices
```bash
python unifi_network_client.py devices list
python unifi_network_client.py devices get --mac aa:bb:cc:dd:ee:ff
python unifi_network_client.py devices restart --mac aa:bb:cc:dd:ee:ff --confirm
python unifi_network_client.py devices upgrade --mac aa:bb:cc:dd:ee:ff --confirm
python unifi_network_client.py devices locate --mac aa:bb:cc:dd:ee:ff --confirm
```

### Clients
```bash
python unifi_network_client.py clients list
python unifi_network_client.py clients list-history
python unifi_network_client.py clients block --mac aa:bb:cc:dd:ee:ff --confirm
python unifi_network_client.py clients unblock --mac aa:bb:cc:dd:ee:ff --confirm
```

### Networks (VLANs)
```bash
python unifi_network_client.py networks list
python unifi_network_client.py networks create --json '{"name":"IoT","purpose":"corporate","vlan":30}' --confirm
python unifi_network_client.py networks update --id <id> --json '{"name":"IoT-Updated"}' --confirm
python unifi_network_client.py networks delete --id <id> --confirm
```

### Firewall Rules
```bash
python unifi_network_client.py firewall list
python unifi_network_client.py firewall create --json '{"name":"Block IoT","action":"drop","src_networkconf_id":"<id>"}' --confirm
python unifi_network_client.py firewall delete --id <id> --confirm
```

### Traffic Routes
```bash
python unifi_network_client.py traffic-routes list
python unifi_network_client.py traffic-routes create --json '{"name":"Route IoT via VPN","enabled":true}' --confirm
```

### Port Forwards
```bash
python unifi_network_client.py port-forwards list
python unifi_network_client.py port-forwards create --json '{"name":"Plex","fwd":"10.220.1.50","fwd_port":32400,"dst_port":32400,"proto":"tcp"}' --confirm
```

### Stats & Health
```bash
python unifi_network_client.py stats health
python unifi_network_client.py stats sysinfo
python unifi_network_client.py stats events --limit 20
python unifi_network_client.py stats alarms
```

### DNS (Static Records)
```bash
python unifi_network_client.py dns list
python unifi_network_client.py dns create --json '{"key":"proxmox.home","value":"10.220.1.7","record_type":"A"}' --confirm
```

### DHCP Leases
```bash
python unifi_network_client.py dhcp list-leases
```
