---
name: unifi-protect
description: Manage UniFi Protect cameras, PTZ control, motion/smart events, NVR info, liveviews, lights, sensors, chimes, and viewers
triggers:
  - "show cameras"
  - "camera snapshot"
  - "ptz"
  - "unifi protect"
  - "motion events"
  - "camera events"
  - "liveview"
  - "protect cameras"
  - "camera stream"
  - "patrol"
script: ./scripts/unifi_protect_client.py
---

# UniFi Protect Skill

Interacts with the UniFi Protect API on a UniFi Dream Machine (UDM) to manage surveillance cameras and related devices.

## Environment Setup

```bash
export UNIFI_API_KEY="your-api-key"   # required (same key as unifi-network)
export UNIFI_HOST="10.220.1.1"        # optional, default: 10.220.1.1
```

## Safety: Dry-Run by Default

All write operations require `--confirm` to execute.

## Commands

### Cameras
```bash
python unifi_protect_client.py cameras list
python unifi_protect_client.py cameras get --id <camera_id>
python unifi_protect_client.py cameras snapshot --id <camera_id> --output /tmp/snap.jpg
python unifi_protect_client.py cameras stream-url --id <camera_id>
python unifi_protect_client.py cameras update --id <camera_id> --json '{"name":"Front Door"}' --confirm
```

### PTZ Control
```bash
python unifi_protect_client.py ptz list-presets --id <camera_id>
python unifi_protect_client.py ptz goto-preset --id <camera_id> --preset-id 1 --confirm
python unifi_protect_client.py ptz patrol-start --id <camera_id> --confirm
python unifi_protect_client.py ptz patrol-stop --id <camera_id> --confirm
```

### Events
```bash
python unifi_protect_client.py events list
python unifi_protect_client.py events list --type motion --limit 20
python unifi_protect_client.py events list --type smartDetectZone
python unifi_protect_client.py events get --id <event_id>
```

### NVR
```bash
python unifi_protect_client.py nvr info
```

### Liveviews
```bash
python unifi_protect_client.py liveviews list
python unifi_protect_client.py liveviews create --json '{"name":"Security","slots":[]}' --confirm
```

### Lights, Sensors, Chimes, Viewers
```bash
python unifi_protect_client.py lights list
python unifi_protect_client.py lights update --id <id> --json '{"lightModeSettings":{"mode":"motion"}}' --confirm
python unifi_protect_client.py sensors list
python unifi_protect_client.py chimes list
python unifi_protect_client.py viewers list
```
