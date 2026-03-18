# UniFi Protect API Endpoints Reference

Base URL pattern: `https://<UNIFI_HOST>/proxy/protect/api/`

All requests use the `X-Api-Key` header for authentication on UniFi OS 3.x+. SSL verification is disabled (UDM uses a self-signed certificate).

---

## NVR (Bootstrap / System Info)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/bootstrap` | Full NVR bootstrap: NVR info, all cameras, lights, sensors, viewers, liveviews, and current state |
| GET | `/proxy/protect/api/nvr` | NVR system info (firmware, storage, uptime, network interfaces) |

The bootstrap endpoint is the most efficient way to retrieve all device data in a single request. The client caches this response and filters by device type.

---

## Cameras

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/cameras` | List all cameras |
| GET | `/proxy/protect/api/cameras/{id}` | Get a specific camera by ID |
| PATCH | `/proxy/protect/api/cameras/{id}` | Update camera settings (name, recording modes, smart detections, etc.) |
| GET | `/proxy/protect/api/cameras/{id}/snapshot` | Get a JPEG snapshot from the camera |
| GET | `/proxy/protect/api/cameras/{id}/streams` | Get camera stream URLs (RTSP, RTMP) |

**Snapshot query params**: `?ts=<unix_timestamp>` (optional, defaults to now), `?force=true` (bypass cache)

**Stream URL response** includes RTSP URLs for high, medium, and low quality streams.

**Camera update body examples**:
```json
{ "name": "Front Door" }
{ "recordingSettings": { "mode": "always" } }
{ "smartDetectSettings": { "objectTypes": ["person", "vehicle"] } }
```

**Recording mode values**: `always`, `never`, `motion`, `smartDetect`

---

## PTZ Control

PTZ commands are sent as PATCH requests to the camera endpoint with a `cameraActions` payload.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/cameras/{id}` | Lists `featureFlags.hasPtz` and `ptzPresetsCount` |
| PATCH | `/proxy/protect/api/cameras/{id}` | Send PTZ move, zoom, preset, or patrol commands |

**PTZ command body examples**:
```json
{ "cameraActions": [{ "action": "gotoPreset", "preset": 1 }] }
{ "cameraActions": [{ "action": "patrolStart" }] }
{ "cameraActions": [{ "action": "patrolStop" }] }
{ "cameraActions": [{ "action": "move", "pan": 0.5, "tilt": -0.3, "speed": 0.5 }] }
{ "cameraActions": [{ "action": "zoom", "speed": 1.0 }] }
```

**Pan/tilt range**: -1.0 to 1.0 (normalized). **Speed range**: 0.0 to 1.0.

**Preset index**: 0-based in the API, displayed as 1-based in the client CLI (`--preset-id 1` maps to preset index 0).

Presets are stored in the camera object as `ptzPresets` (array of `{ name, slot }` objects) and are retrieved from the bootstrap or camera GET response.

---

## Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/events` | List events with optional filters |
| GET | `/proxy/protect/api/events/{id}` | Get a specific event by ID |

**Event query params**:
- `?type=motion` — filter by event type
- `?type=smartDetectZone` — filter by smart detection events
- `?limit=50` — number of events to return (default: 50)
- `?start=<unix_ms>` — events after this timestamp
- `?end=<unix_ms>` — events before this timestamp
- `?cameraId=<id>` — filter by specific camera

**Event type values**: `motion`, `smartDetectZone`, `ring`, `disconnect`, `connection`, `provisionCamera`

**Smart detection object types** (in event `metadata.detectedObjects`): `person`, `vehicle`, `animal`, `package`, `licensePlate`

---

## Liveviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/liveviews` | List all saved liveviews |
| POST | `/proxy/protect/api/liveviews` | Create a new liveview |
| PATCH | `/proxy/protect/api/liveviews/{id}` | Update a liveview |
| DELETE | `/proxy/protect/api/liveviews/{id}` | Delete a liveview |

**Liveview body example**:
```json
{
  "name": "Security Overview",
  "isDefault": false,
  "isGlobal": true,
  "layout": 1,
  "slots": [
    { "cameras": ["<camera_id_1>"], "cycleMode": "none", "cycleInterval": 10 },
    { "cameras": ["<camera_id_2>"], "cycleMode": "none", "cycleInterval": 10 }
  ]
}
```

**Layout values**: `1` (1x1), `2` (2x1), `4` (2x2), `9` (3x3), `16` (4x4)

---

## Lights

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/lights` | List all UniFi Flood Lights |
| GET | `/proxy/protect/api/lights/{id}` | Get a specific light |
| PATCH | `/proxy/protect/api/lights/{id}` | Update light settings |

**Light update body example**:
```json
{
  "lightModeSettings": {
    "mode": "motion",
    "enableAt": "dark"
  },
  "lightOnSettings": {
    "isLedForceOn": false,
    "ledLevel": 3
  }
}
```

**Mode values**: `off`, `motion`, `always`, `schedule`
**enableAt values**: `dark`, `always`

---

## Sensors

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/sensors` | List all sensors (door/window, temperature, humidity, light) |
| GET | `/proxy/protect/api/sensors/{id}` | Get a specific sensor |
| PATCH | `/proxy/protect/api/sensors/{id}` | Update sensor settings |

Sensor data includes `stats` (current temperature, humidity, light level) and `alarmSettings` (motion sensitivity, tamper detection).

---

## Chimes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/chimes` | List all UniFi Chimes |
| GET | `/proxy/protect/api/chimes/{id}` | Get a specific chime |
| PATCH | `/proxy/protect/api/chimes/{id}` | Update chime settings (volume, ringtone) |
| POST | `/proxy/protect/api/chimes/{id}/play-speaker` | Play a ringtone on demand |

---

## Viewers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/proxy/protect/api/viewers` | List all UniFi Viewers |
| GET | `/proxy/protect/api/viewers/{id}` | Get a specific viewer |
| PATCH | `/proxy/protect/api/viewers/{id}` | Update viewer settings (active liveview, volume) |

---

## API Notes

- **Authentication**: `X-Api-Key` header with a key generated in UniFi OS → Settings → API Keys. The same key works for both the Network and Protect APIs.
- **SSL**: The UDM uses a self-signed TLS certificate. All requests must disable SSL verification (`verify=False` in requests, `urllib3.InsecureRequestWarning` suppressed).
- **IDs**: UniFi Protect uses 24-character hex string IDs (e.g., `64a2f3b1c8e4d500011a2b3c`). These are returned in list/get responses and required for all targeted operations.
- **Bootstrap caching**: The bootstrap endpoint returns all device state in one call. The client uses it for list operations to minimize API calls. The `lastUpdateId` field can be used with the WebSocket event stream for real-time updates (not implemented in this CLI client).
- **Timestamps**: All timestamps in Protect are Unix milliseconds (not seconds).
- **Snapshot content type**: `image/jpeg`. The client returns raw bytes when `--output` is specified, or base64-encodes into a JSON wrapper for programmatic use.
