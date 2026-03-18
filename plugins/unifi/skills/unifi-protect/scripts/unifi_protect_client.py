#!/usr/bin/env python3
"""
UniFi Protect CLI - Command-line interface for UniFi Protect API operations.

Manages UniFi Protect cameras, PTZ control, motion/smart events, NVR info,
liveviews, lights, sensors, chimes, and viewers via the UniFi OS Protect API.

Environment Variables:
    UNIFI_API_KEY: UniFi OS API key (required)
    UNIFI_HOST: UDM IP or hostname (default: 10.220.1.1)

Usage:
    python unifi_protect_client.py cameras list
    python unifi_protect_client.py cameras snapshot --id <cam_id> --output /tmp/snap.jpg
    python unifi_protect_client.py events list --type motion --limit 20
    python unifi_protect_client.py ptz goto-preset --id <cam_id> --preset-id 1 --confirm
"""

import argparse
import base64
import json
import os
import sys
from typing import Any

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
except ImportError:
    print(
        json.dumps(
            {
                "error": "requests library not installed",
                "message": "Install with: pip install requests",
                "install_command": "pip install requests",
            }
        )
    )
    sys.exit(1)


class UnifiProtectClient:
    """Wrapper for UniFi Protect API operations with JSON output."""

    def __init__(
        self,
        api_key: str | None = None,
        host: str | None = None,
        verify_ssl: bool = False,
    ):
        """Initialize the UniFi Protect client.

        Args:
            api_key: UniFi OS API key (defaults to UNIFI_API_KEY env var)
            host: UDM IP or hostname (defaults to UNIFI_HOST env var or 10.220.1.1)
            verify_ssl: Whether to verify SSL certificates (default: False for self-signed certs)
        """
        self.api_key = api_key or os.getenv("UNIFI_API_KEY")
        if not self.api_key:
            self._error("UNIFI_API_KEY environment variable not set")
            sys.exit(1)

        self.host = host or os.getenv("UNIFI_HOST", "10.220.1.1")
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{self.host}/proxy/protect/api"
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _error(self, message: str, **kwargs: Any) -> None:
        """Output error in JSON format."""
        error_data = {"error": True, "message": message}
        error_data.update(kwargs)
        print(json.dumps(error_data, indent=2))

    def _success(self, data: Any, **kwargs: Any) -> None:
        """Output success data in JSON format."""
        output = {"success": True, "data": data}
        output.update(kwargs)
        print(json.dumps(output, indent=2, default=str))

    def _dry_run(self, method: str, url: str, data: dict[str, Any] | None = None) -> None:
        """Output dry-run info in JSON format."""
        dry_run_data: dict[str, Any] = {
            "dry_run": True,
            "message": "Pass --confirm to execute this operation",
            "method": method,
            "url": url,
        }
        if data is not None:
            dry_run_data["body"] = data
        print(json.dumps(dry_run_data, indent=2))

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        confirm: bool = True,
        binary: bool = False,
    ) -> Any:
        """Make HTTP request to UniFi Protect API with error handling.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            url: Full URL (already includes base_url)
            params: Query parameters
            data: Request body data
            confirm: Whether this mutation is confirmed (False → dry-run for mutating methods)
            binary: Whether to return raw bytes instead of parsed JSON

        Returns:
            Response data as dict, bytes (if binary=True), or exits on error
        """
        mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

        if method.upper() in mutating_methods and not confirm:
            self._dry_run(method.upper(), url, data)
            sys.exit(0)

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30,
                verify=self.verify_ssl,
            )

            if response.status_code == 401:
                self._error("API key invalid or expired", status_code=401)
                sys.exit(1)

            if response.status_code == 403:
                self._error(
                    "Insufficient permissions. Check API key scope.",
                    status_code=403,
                )
                sys.exit(1)

            if response.status_code == 404:
                self._error(
                    "Resource not found. Verify camera/device ID.",
                    status_code=404,
                )
                sys.exit(1)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self._error(
                    f"Rate limited. Retry after {retry_after} seconds",
                    status_code=429,
                    retry_after=retry_after,
                )
                sys.exit(1)

            if response.status_code >= 500:
                self._error(
                    f"Controller error: {response.status_code}",
                    status_code=response.status_code,
                )
                sys.exit(1)

            if response.status_code >= 400:
                self._error(
                    f"API error: {response.status_code}",
                    status_code=response.status_code,
                )
                sys.exit(1)

            if binary:
                return response.content

            # Handle empty responses (e.g., 204 No Content)
            if not response.content:
                return {}

            return response.json()

        except requests.exceptions.Timeout:
            self._error("Request timeout after 30 seconds")
            sys.exit(1)
        except requests.exceptions.SSLError:
            self._error(
                "SSL verification failed. Set verify_ssl=True or check certificate."
            )
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            self._error(
                f"Cannot reach UDM at {self.host}. Check network connectivity."
            )
            sys.exit(1)
        except Exception as e:
            self._error(f"Unexpected error: {str(e)}")
            sys.exit(1)

    # ===========================
    # CAMERAS
    # ===========================

    def cameras_list(self) -> None:
        """List all cameras."""
        url = f"{self.base_url}/cameras"
        result = self._request("GET", url)
        self._success(result, count=len(result) if isinstance(result, list) else None)

    def cameras_get(self, camera_id: str) -> None:
        """Get camera details.

        Args:
            camera_id: Camera ID
        """
        url = f"{self.base_url}/cameras/{camera_id}"
        result = self._request("GET", url)
        self._success(result)

    def cameras_snapshot(self, camera_id: str, output_path: str | None = None) -> None:
        """Get a JPEG snapshot from a camera.

        Args:
            camera_id: Camera ID
            output_path: Optional file path to save the snapshot; if omitted returns base64
        """
        url = f"{self.base_url}/cameras/{camera_id}/snapshot"
        image_bytes = self._request("GET", url, binary=True)

        if output_path:
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            self._success({"saved_to": output_path, "size_bytes": len(image_bytes)})
        else:
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            self._success({"data": encoded, "encoding": "base64", "format": "jpeg"})

    def cameras_update(self, camera_id: str, data: dict[str, Any], confirm: bool = False) -> None:
        """Update camera settings.

        Args:
            camera_id: Camera ID
            data: Fields to update (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/cameras/{camera_id}"
        result = self._request("PATCH", url, data=data, confirm=confirm)
        self._success(result, message=f"Camera {camera_id} updated")

    def cameras_stream_url(self, camera_id: str) -> None:
        """Get the RTSP stream URL for a camera.

        Args:
            camera_id: Camera ID
        """
        url = f"{self.base_url}/cameras/{camera_id}"
        camera_data = self._request("GET", url)

        channels = camera_data.get("channels", [])
        best = next((c for c in channels if c.get("isRtspEnabled")), None)

        if best:
            rtsp_url = f"rtsp://{self.host}:7447/{best['rtspAlias']}"
            self._success({"rtsp_url": rtsp_url, "camera_id": camera_id, "channel": best})
        else:
            self._error(
                "No RTSP-enabled channel found for this camera. Enable RTSP in Protect settings.",
                camera_id=camera_id,
            )
            sys.exit(1)

    # ===========================
    # PTZ CONTROL
    # ===========================

    def ptz_goto_preset(self, camera_id: str, preset_id: int, confirm: bool = False) -> None:
        """Move PTZ camera to a saved preset position.

        Args:
            camera_id: Camera ID
            preset_id: Preset ID to move to
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/cameras/{camera_id}/ptz"
        data = {"type": "goto", "payload": {"presetId": preset_id}}
        result = self._request("POST", url, data=data, confirm=confirm)
        self._success(result, message=f"Camera {camera_id} moved to preset {preset_id}")

    def ptz_patrol_start(self, camera_id: str, confirm: bool = False) -> None:
        """Start PTZ patrol on a camera.

        Args:
            camera_id: Camera ID
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/cameras/{camera_id}/ptz"
        data = {"type": "patrol", "payload": {"action": "start"}}
        result = self._request("POST", url, data=data, confirm=confirm)
        self._success(result, message=f"PTZ patrol started on camera {camera_id}")

    def ptz_patrol_stop(self, camera_id: str, confirm: bool = False) -> None:
        """Stop PTZ patrol on a camera.

        Args:
            camera_id: Camera ID
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/cameras/{camera_id}/ptz"
        data = {"type": "patrol", "payload": {"action": "stop"}}
        result = self._request("POST", url, data=data, confirm=confirm)
        self._success(result, message=f"PTZ patrol stopped on camera {camera_id}")

    def ptz_list_presets(self, camera_id: str) -> None:
        """List PTZ presets for a camera.

        Args:
            camera_id: Camera ID
        """
        url = f"{self.base_url}/cameras/{camera_id}"
        camera_data = self._request("GET", url)
        presets = camera_data.get("ptzPresets", [])
        self._success(presets, count=len(presets), camera_id=camera_id)

    # ===========================
    # EVENTS
    # ===========================

    def events_list(
        self,
        event_type: str | None = None,
        limit: int = 50,
        start: int | None = None,
        end: int | None = None,
    ) -> None:
        """List events with optional filters.

        Args:
            event_type: Filter by event type (motion, smartDetectZone, ring, loitering)
            limit: Maximum number of events to return (default: 50)
            start: Start timestamp in Unix milliseconds
            end: End timestamp in Unix milliseconds
        """
        url = f"{self.base_url}/events"
        params: dict[str, Any] = {"limit": limit}

        if event_type:
            params["type"] = event_type
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end

        result = self._request("GET", url, params=params)
        count = len(result) if isinstance(result, list) else None
        self._success(result, count=count)

    def events_get(self, event_id: str) -> None:
        """Get event details.

        Args:
            event_id: Event ID
        """
        url = f"{self.base_url}/events/{event_id}"
        result = self._request("GET", url)
        self._success(result)

    # ===========================
    # NVR
    # ===========================

    def nvr_info(self) -> None:
        """Get NVR information."""
        url = f"{self.base_url}/nvr"
        result = self._request("GET", url)
        self._success(result)

    # ===========================
    # LIVEVIEWS
    # ===========================

    def liveviews_list(self) -> None:
        """List all liveviews."""
        url = f"{self.base_url}/liveviews"
        result = self._request("GET", url)
        self._success(result, count=len(result) if isinstance(result, list) else None)

    def liveviews_get(self, liveview_id: str) -> None:
        """Get liveview details.

        Args:
            liveview_id: Liveview ID
        """
        url = f"{self.base_url}/liveviews/{liveview_id}"
        result = self._request("GET", url)
        self._success(result)

    def liveviews_create(self, data: dict[str, Any], confirm: bool = False) -> None:
        """Create a new liveview.

        Args:
            data: Liveview configuration (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/liveviews"
        result = self._request("POST", url, data=data, confirm=confirm)
        self._success(result, message="Liveview created")

    def liveviews_update(
        self, liveview_id: str, data: dict[str, Any], confirm: bool = False
    ) -> None:
        """Update a liveview.

        Args:
            liveview_id: Liveview ID
            data: Fields to update (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/liveviews/{liveview_id}"
        result = self._request("PUT", url, data=data, confirm=confirm)
        self._success(result, message=f"Liveview {liveview_id} updated")

    def liveviews_delete(self, liveview_id: str, confirm: bool = False) -> None:
        """Delete a liveview.

        Args:
            liveview_id: Liveview ID
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/liveviews/{liveview_id}"
        self._request("DELETE", url, confirm=confirm)
        self._success({}, message=f"Liveview {liveview_id} deleted")

    # ===========================
    # LIGHTS
    # ===========================

    def lights_list(self) -> None:
        """List all lights."""
        url = f"{self.base_url}/lights"
        result = self._request("GET", url)
        self._success(result, count=len(result) if isinstance(result, list) else None)

    def lights_get(self, light_id: str) -> None:
        """Get light details.

        Args:
            light_id: Light ID
        """
        url = f"{self.base_url}/lights/{light_id}"
        result = self._request("GET", url)
        self._success(result)

    def lights_update(self, light_id: str, data: dict[str, Any], confirm: bool = False) -> None:
        """Update light settings.

        Args:
            light_id: Light ID
            data: Fields to update (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/lights/{light_id}"
        result = self._request("PATCH", url, data=data, confirm=confirm)
        self._success(result, message=f"Light {light_id} updated")

    # ===========================
    # SENSORS
    # ===========================

    def sensors_list(self) -> None:
        """List all sensors."""
        url = f"{self.base_url}/sensors"
        result = self._request("GET", url)
        self._success(result, count=len(result) if isinstance(result, list) else None)

    def sensors_get(self, sensor_id: str) -> None:
        """Get sensor details.

        Args:
            sensor_id: Sensor ID
        """
        url = f"{self.base_url}/sensors/{sensor_id}"
        result = self._request("GET", url)
        self._success(result)

    def sensors_update(self, sensor_id: str, data: dict[str, Any], confirm: bool = False) -> None:
        """Update sensor settings.

        Args:
            sensor_id: Sensor ID
            data: Fields to update (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/sensors/{sensor_id}"
        result = self._request("PATCH", url, data=data, confirm=confirm)
        self._success(result, message=f"Sensor {sensor_id} updated")

    # ===========================
    # CHIMES
    # ===========================

    def chimes_list(self) -> None:
        """List all chimes."""
        url = f"{self.base_url}/chimes"
        result = self._request("GET", url)
        self._success(result, count=len(result) if isinstance(result, list) else None)

    def chimes_get(self, chime_id: str) -> None:
        """Get chime details.

        Args:
            chime_id: Chime ID
        """
        url = f"{self.base_url}/chimes/{chime_id}"
        result = self._request("GET", url)
        self._success(result)

    def chimes_update(self, chime_id: str, data: dict[str, Any], confirm: bool = False) -> None:
        """Update chime settings.

        Args:
            chime_id: Chime ID
            data: Fields to update (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/chimes/{chime_id}"
        result = self._request("PATCH", url, data=data, confirm=confirm)
        self._success(result, message=f"Chime {chime_id} updated")

    # ===========================
    # VIEWERS
    # ===========================

    def viewers_list(self) -> None:
        """List all viewers."""
        url = f"{self.base_url}/viewers"
        result = self._request("GET", url)
        self._success(result, count=len(result) if isinstance(result, list) else None)

    def viewers_get(self, viewer_id: str) -> None:
        """Get viewer details.

        Args:
            viewer_id: Viewer ID
        """
        url = f"{self.base_url}/viewers/{viewer_id}"
        result = self._request("GET", url)
        self._success(result)

    def viewers_update(self, viewer_id: str, data: dict[str, Any], confirm: bool = False) -> None:
        """Update viewer settings.

        Args:
            viewer_id: Viewer ID
            data: Fields to update (JSON object)
            confirm: Must be True to execute; False shows dry-run
        """
        url = f"{self.base_url}/viewers/{viewer_id}"
        result = self._request("PATCH", url, data=data, confirm=confirm)
        self._success(result, message=f"Viewer {viewer_id} updated")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="UniFi Protect CLI for camera and device management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--confirm", action="store_true", help="Confirm mutating operations")
    parser.add_argument("--host", help="Override UNIFI_HOST (UDM IP or hostname)")
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        default=False,
        help="Enable SSL certificate verification (disabled by default for self-signed certs)",
    )

    subparsers = parser.add_subparsers(dest="resource", help="Resource type")

    # ===========================
    # CAMERAS
    # ===========================
    cameras_parser = subparsers.add_parser("cameras", help="Manage cameras")
    cameras_subparsers = cameras_parser.add_subparsers(dest="action", help="Camera action")

    # cameras list
    cameras_subparsers.add_parser("list", help="List all cameras")

    # cameras get
    cameras_get_parser = cameras_subparsers.add_parser("get", help="Get camera details")
    cameras_get_parser.add_argument("--id", required=True, help="Camera ID")

    # cameras snapshot
    cameras_snapshot_parser = cameras_subparsers.add_parser("snapshot", help="Capture a JPEG snapshot")
    cameras_snapshot_parser.add_argument("--id", required=True, help="Camera ID")
    cameras_snapshot_parser.add_argument("--output", help="File path to save snapshot (optional; returns base64 if omitted)")

    # cameras update
    cameras_update_parser = cameras_subparsers.add_parser("update", help="Update camera settings")
    cameras_update_parser.add_argument("--id", required=True, help="Camera ID")
    cameras_update_parser.add_argument("--json", required=True, dest="json_data", help="JSON object of fields to update")

    # cameras stream-url
    cameras_stream_url_parser = cameras_subparsers.add_parser("stream-url", help="Get RTSP stream URL")
    cameras_stream_url_parser.add_argument("--id", required=True, help="Camera ID")

    # ===========================
    # PTZ
    # ===========================
    ptz_parser = subparsers.add_parser("ptz", help="PTZ camera control")
    ptz_subparsers = ptz_parser.add_subparsers(dest="action", help="PTZ action")

    # ptz goto-preset
    ptz_goto_parser = ptz_subparsers.add_parser("goto-preset", help="Move to a saved PTZ preset")
    ptz_goto_parser.add_argument("--id", required=True, help="Camera ID")
    ptz_goto_parser.add_argument("--preset-id", required=True, type=int, help="Preset ID to move to")

    # ptz patrol-start
    ptz_patrol_start_parser = ptz_subparsers.add_parser("patrol-start", help="Start PTZ patrol")
    ptz_patrol_start_parser.add_argument("--id", required=True, help="Camera ID")

    # ptz patrol-stop
    ptz_patrol_stop_parser = ptz_subparsers.add_parser("patrol-stop", help="Stop PTZ patrol")
    ptz_patrol_stop_parser.add_argument("--id", required=True, help="Camera ID")

    # ptz list-presets
    ptz_list_presets_parser = ptz_subparsers.add_parser("list-presets", help="List PTZ presets")
    ptz_list_presets_parser.add_argument("--id", required=True, help="Camera ID")

    # ===========================
    # EVENTS
    # ===========================
    events_parser = subparsers.add_parser("events", help="Query motion and smart detection events")
    events_subparsers = events_parser.add_subparsers(dest="action", help="Events action")

    # events list
    events_list_parser = events_subparsers.add_parser("list", help="List events")
    events_list_parser.add_argument(
        "--type",
        dest="event_type",
        choices=["motion", "smartDetectZone", "ring", "loitering"],
        help="Filter by event type",
    )
    events_list_parser.add_argument("--limit", type=int, default=50, help="Maximum number of events (default: 50)")
    events_list_parser.add_argument("--start", type=int, help="Start timestamp in Unix milliseconds")
    events_list_parser.add_argument("--end", type=int, help="End timestamp in Unix milliseconds")

    # events get
    events_get_parser = events_subparsers.add_parser("get", help="Get event details")
    events_get_parser.add_argument("--id", required=True, help="Event ID")

    # ===========================
    # NVR
    # ===========================
    nvr_parser = subparsers.add_parser("nvr", help="NVR information")
    nvr_subparsers = nvr_parser.add_subparsers(dest="action", help="NVR action")

    nvr_subparsers.add_parser("info", help="Get NVR info")

    # ===========================
    # LIVEVIEWS
    # ===========================
    liveviews_parser = subparsers.add_parser("liveviews", help="Manage liveviews")
    liveviews_subparsers = liveviews_parser.add_subparsers(dest="action", help="Liveviews action")

    # liveviews list
    liveviews_subparsers.add_parser("list", help="List all liveviews")

    # liveviews get
    liveviews_get_parser = liveviews_subparsers.add_parser("get", help="Get liveview details")
    liveviews_get_parser.add_argument("--id", required=True, help="Liveview ID")

    # liveviews create
    liveviews_create_parser = liveviews_subparsers.add_parser("create", help="Create a liveview")
    liveviews_create_parser.add_argument("--json", required=True, dest="json_data", help="JSON object for liveview configuration")

    # liveviews update
    liveviews_update_parser = liveviews_subparsers.add_parser("update", help="Update a liveview")
    liveviews_update_parser.add_argument("--id", required=True, help="Liveview ID")
    liveviews_update_parser.add_argument("--json", required=True, dest="json_data", help="JSON object of fields to update")

    # liveviews delete
    liveviews_delete_parser = liveviews_subparsers.add_parser("delete", help="Delete a liveview")
    liveviews_delete_parser.add_argument("--id", required=True, help="Liveview ID")

    # ===========================
    # LIGHTS
    # ===========================
    lights_parser = subparsers.add_parser("lights", help="Manage lights")
    lights_subparsers = lights_parser.add_subparsers(dest="action", help="Lights action")

    # lights list
    lights_subparsers.add_parser("list", help="List all lights")

    # lights get
    lights_get_parser = lights_subparsers.add_parser("get", help="Get light details")
    lights_get_parser.add_argument("--id", required=True, help="Light ID")

    # lights update
    lights_update_parser = lights_subparsers.add_parser("update", help="Update light settings")
    lights_update_parser.add_argument("--id", required=True, help="Light ID")
    lights_update_parser.add_argument("--json", required=True, dest="json_data", help="JSON object of fields to update")

    # ===========================
    # SENSORS
    # ===========================
    sensors_parser = subparsers.add_parser("sensors", help="Manage sensors")
    sensors_subparsers = sensors_parser.add_subparsers(dest="action", help="Sensors action")

    # sensors list
    sensors_subparsers.add_parser("list", help="List all sensors")

    # sensors get
    sensors_get_parser = sensors_subparsers.add_parser("get", help="Get sensor details")
    sensors_get_parser.add_argument("--id", required=True, help="Sensor ID")

    # sensors update
    sensors_update_parser = sensors_subparsers.add_parser("update", help="Update sensor settings")
    sensors_update_parser.add_argument("--id", required=True, help="Sensor ID")
    sensors_update_parser.add_argument("--json", required=True, dest="json_data", help="JSON object of fields to update")

    # ===========================
    # CHIMES
    # ===========================
    chimes_parser = subparsers.add_parser("chimes", help="Manage chimes")
    chimes_subparsers = chimes_parser.add_subparsers(dest="action", help="Chimes action")

    # chimes list
    chimes_subparsers.add_parser("list", help="List all chimes")

    # chimes get
    chimes_get_parser = chimes_subparsers.add_parser("get", help="Get chime details")
    chimes_get_parser.add_argument("--id", required=True, help="Chime ID")

    # chimes update
    chimes_update_parser = chimes_subparsers.add_parser("update", help="Update chime settings")
    chimes_update_parser.add_argument("--id", required=True, help="Chime ID")
    chimes_update_parser.add_argument("--json", required=True, dest="json_data", help="JSON object of fields to update")

    # ===========================
    # VIEWERS
    # ===========================
    viewers_parser = subparsers.add_parser("viewers", help="Manage viewers")
    viewers_subparsers = viewers_parser.add_subparsers(dest="action", help="Viewers action")

    # viewers list
    viewers_subparsers.add_parser("list", help="List all viewers")

    # viewers get
    viewers_get_parser = viewers_subparsers.add_parser("get", help="Get viewer details")
    viewers_get_parser.add_argument("--id", required=True, help="Viewer ID")

    # viewers update
    viewers_update_parser = viewers_subparsers.add_parser("update", help="Update viewer settings")
    viewers_update_parser.add_argument("--id", required=True, help="Viewer ID")
    viewers_update_parser.add_argument("--json", required=True, dest="json_data", help="JSON object of fields to update")

    # Parse arguments
    args = parser.parse_args()

    if not args.resource:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    client = UnifiProtectClient(host=args.host, verify_ssl=args.verify_ssl)

    # ===========================
    # ROUTE: CAMERAS
    # ===========================
    if args.resource == "cameras":
        if not args.action:
            cameras_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.cameras_list()

        elif args.action == "get":
            client.cameras_get(camera_id=args.id)

        elif args.action == "snapshot":
            client.cameras_snapshot(camera_id=args.id, output_path=args.output)

        elif args.action == "update":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.cameras_update(camera_id=args.id, data=data, confirm=args.confirm)

        elif args.action == "stream-url":
            client.cameras_stream_url(camera_id=args.id)

    # ===========================
    # ROUTE: PTZ
    # ===========================
    elif args.resource == "ptz":
        if not args.action:
            ptz_parser.print_help()
            sys.exit(1)

        if args.action == "goto-preset":
            client.ptz_goto_preset(camera_id=args.id, preset_id=args.preset_id, confirm=args.confirm)

        elif args.action == "patrol-start":
            client.ptz_patrol_start(camera_id=args.id, confirm=args.confirm)

        elif args.action == "patrol-stop":
            client.ptz_patrol_stop(camera_id=args.id, confirm=args.confirm)

        elif args.action == "list-presets":
            client.ptz_list_presets(camera_id=args.id)

    # ===========================
    # ROUTE: EVENTS
    # ===========================
    elif args.resource == "events":
        if not args.action:
            events_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.events_list(
                event_type=args.event_type,
                limit=args.limit,
                start=args.start,
                end=args.end,
            )

        elif args.action == "get":
            client.events_get(event_id=args.id)

    # ===========================
    # ROUTE: NVR
    # ===========================
    elif args.resource == "nvr":
        if not args.action:
            nvr_parser.print_help()
            sys.exit(1)

        if args.action == "info":
            client.nvr_info()

    # ===========================
    # ROUTE: LIVEVIEWS
    # ===========================
    elif args.resource == "liveviews":
        if not args.action:
            liveviews_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.liveviews_list()

        elif args.action == "get":
            client.liveviews_get(liveview_id=args.id)

        elif args.action == "create":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.liveviews_create(data=data, confirm=args.confirm)

        elif args.action == "update":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.liveviews_update(liveview_id=args.id, data=data, confirm=args.confirm)

        elif args.action == "delete":
            client.liveviews_delete(liveview_id=args.id, confirm=args.confirm)

    # ===========================
    # ROUTE: LIGHTS
    # ===========================
    elif args.resource == "lights":
        if not args.action:
            lights_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.lights_list()

        elif args.action == "get":
            client.lights_get(light_id=args.id)

        elif args.action == "update":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.lights_update(light_id=args.id, data=data, confirm=args.confirm)

    # ===========================
    # ROUTE: SENSORS
    # ===========================
    elif args.resource == "sensors":
        if not args.action:
            sensors_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.sensors_list()

        elif args.action == "get":
            client.sensors_get(sensor_id=args.id)

        elif args.action == "update":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.sensors_update(sensor_id=args.id, data=data, confirm=args.confirm)

    # ===========================
    # ROUTE: CHIMES
    # ===========================
    elif args.resource == "chimes":
        if not args.action:
            chimes_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.chimes_list()

        elif args.action == "get":
            client.chimes_get(chime_id=args.id)

        elif args.action == "update":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.chimes_update(chime_id=args.id, data=data, confirm=args.confirm)

    # ===========================
    # ROUTE: VIEWERS
    # ===========================
    elif args.resource == "viewers":
        if not args.action:
            viewers_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.viewers_list()

        elif args.action == "get":
            client.viewers_get(viewer_id=args.id)

        elif args.action == "update":
            try:
                data = json.loads(args.json_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": True, "message": f"Invalid JSON: {e}"}))
                sys.exit(1)
            client.viewers_update(viewer_id=args.id, data=data, confirm=args.confirm)


if __name__ == "__main__":
    main()
