---
name: unifi
description: UniFi network and protect operations — devices, clients, cameras, events
---

# UniFi Command

Provides quick access to UniFi Network and Protect operations for your home lab UDM.

## Usage

```
/unifi [network|protect] <resource> <action> [options] [--confirm]
```

## Quick Reference

**Network**:
- `/unifi devices list` — list all network devices
- `/unifi clients list` — list active wireless clients
- `/unifi stats health` — show network health
- `/unifi firewall list` — list firewall rules

**Protect**:
- `/unifi cameras list` — list all cameras
- `/unifi events list --type motion` — recent motion events
- `/unifi cameras snapshot --id <id>` — grab a snapshot
