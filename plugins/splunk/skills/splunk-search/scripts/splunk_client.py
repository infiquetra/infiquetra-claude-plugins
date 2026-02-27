#!/usr/bin/env python3
"""
Splunk CLI - Command-line interface for Splunk REST API operations.

This script provides a unified CLI for Splunk search operations including job management,
result retrieval, and resource discovery. All output is JSON for Claude Code to parse.

Environment Variables:
    SPLUNK_TOKEN: Splunk authentication token (required)
    SPLUNK_HOST: Splunk host (required, e.g., splunk.example.com)

Usage:
    python splunk_client.py search submit --query 'search index=main error'
    python splunk_client.py search poll --job-id <sid>
    python splunk_client.py search results --job-id <sid>
    python splunk_client.py search execute --query 'search index=main error' --timeout 60
    python splunk_client.py apps list
    python splunk_client.py indexes list
"""

import argparse
import json
import os
import sys
import time
from typing import Any

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


class SplunkClient:
    """Wrapper for Splunk REST API operations with JSON output."""

    def __init__(self, token: str | None = None, host: str | None = None):
        """Initialize the Splunk client.

        Args:
            token: Splunk authentication token (defaults to SPLUNK_TOKEN env var)
            host: Splunk host (defaults to SPLUNK_HOST env var)
        """
        self.token = token or os.getenv("SPLUNK_TOKEN")
        self.host = host or os.getenv("SPLUNK_HOST")

        if not self.token:
            self._error("SPLUNK_TOKEN environment variable not set")
            sys.exit(1)

        if not self.host:
            self._error("SPLUNK_HOST environment variable not set")
            sys.exit(1)

        # Remove protocol if included
        self.host = self.host.replace("https://", "").replace("http://", "")

        self.base_url = f"https://{self.host}:8089"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _error(self, message: str, **kwargs) -> None:
        """Output error in JSON format."""
        error_data = {"error": True, "message": message}
        error_data.update(kwargs)
        print(json.dumps(error_data, indent=2))

    def _success(self, data: Any, **kwargs) -> None:
        """Output success data in JSON format."""
        output = {"success": True, "data": data}
        output.update(kwargs)
        print(json.dumps(output, indent=2, default=str))

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request to Splunk API with error handling.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data

        Returns:
            Response data as dict

        Raises:
            sys.exit on error
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                data=data,
                timeout=30,
                verify=True,  # Enable SSL verification for Splunk
            )

            # Handle errors
            if response.status_code >= 400:
                error_msg = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if "messages" in error_data:
                        error_msg = error_data["messages"][0]["text"]
                except (ValueError, KeyError, IndexError):
                    error_msg = response.text or error_msg

                self._error(error_msg, status_code=response.status_code)
                sys.exit(1)

            return response.json()

        except requests.exceptions.Timeout:
            self._error("Request timeout after 30 seconds")
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            self._error(f"Connection error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            self._error(f"Unexpected error: {str(e)}")
            sys.exit(1)

    # ===========================
    # SEARCH
    # ===========================

    def search_submit(
        self,
        query: str,
        earliest_time: str = "-1h",
        latest_time: str = "now",
        max_count: int = 100,
    ) -> None:
        """Submit a search job.

        Args:
            query: SPL search query
            earliest_time: Start time (e.g., -1h, -24h, 2026-02-26T00:00:00)
            latest_time: End time (e.g., now, 2026-02-26T23:59:59)
            max_count: Maximum number of results
        """
        # Ensure query starts with 'search' command
        if not query.strip().startswith("search "):
            query = f"search {query}"

        data = {
            "search": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "max_count": max_count,
            "output_mode": "json",
        }

        response = self._request("POST", "/services/search/jobs", data=data)

        # Extract job ID (sid)
        sid = response.get("sid")
        if not sid:
            self._error("Failed to create search job - no SID returned")
            sys.exit(1)

        self._success({"sid": sid, "query": query}, message="Search job created")

    def search_poll(self, job_id: str) -> None:
        """Poll search job status.

        Args:
            job_id: Search job ID (sid)
        """
        response = self._request(
            "GET", f"/services/search/jobs/{job_id}", params={"output_mode": "json"}
        )

        # Extract job entry
        entry = response.get("entry", [{}])[0]
        content = entry.get("content", {})

        job_status = {
            "sid": job_id,
            "dispatch_state": content.get("dispatchState"),
            "is_done": content.get("isDone", False),
            "progress": content.get("doneProgress", 0),
            "result_count": content.get("resultCount", 0),
            "scan_count": content.get("scanCount", 0),
            "event_count": content.get("eventCount", 0),
        }

        self._success(job_status)

    def search_results(self, job_id: str, offset: int = 0, count: int = 100) -> None:
        """Get search job results.

        Args:
            job_id: Search job ID (sid)
            offset: Result offset
            count: Number of results to return
        """
        params = {"output_mode": "json", "offset": offset, "count": count}

        response = self._request(
            "GET", f"/services/search/jobs/{job_id}/results", params=params
        )

        results = response.get("results", [])
        self._success(results, count=len(results), offset=offset)

    def search_execute(
        self,
        query: str,
        earliest_time: str = "-1h",
        latest_time: str = "now",
        max_count: int = 100,
        timeout: int = 60,
        poll_interval: int = 2,
    ) -> None:
        """Execute search and wait for results (convenience method).

        Args:
            query: SPL search query
            earliest_time: Start time
            latest_time: End time
            max_count: Maximum results
            timeout: Max wait time in seconds
            poll_interval: Polling interval in seconds
        """
        # Ensure query starts with 'search' command
        if not query.strip().startswith("search "):
            query = f"search {query}"

        # Submit job
        data = {
            "search": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "max_count": max_count,
            "output_mode": "json",
        }

        response = self._request("POST", "/services/search/jobs", data=data)
        sid = response.get("sid")

        if not sid:
            self._error("Failed to create search job - no SID returned")
            sys.exit(1)

        # Poll until done or timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_response = self._request(
                "GET", f"/services/search/jobs/{sid}", params={"output_mode": "json"}
            )

            entry = status_response.get("entry", [{}])[0]
            content = entry.get("content", {})
            is_done = content.get("isDone", False)

            if is_done:
                # Get results
                results_response = self._request(
                    "GET",
                    f"/services/search/jobs/{sid}/results",
                    params={"output_mode": "json", "count": max_count},
                )

                results = results_response.get("results", [])
                self._success(
                    results,
                    count=len(results),
                    sid=sid,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                return

            time.sleep(poll_interval)

        # Timeout
        self._error(
            f"Search timeout after {timeout} seconds. Job still running (SID: {sid})",
            sid=sid,
            timeout=timeout,
        )
        sys.exit(1)

    def search_delete(self, job_id: str) -> None:
        """Delete a search job.

        Args:
            job_id: Search job ID (sid)
        """
        self._request("DELETE", f"/services/search/jobs/{job_id}")
        self._success({}, message=f"Search job {job_id} deleted")

    # ===========================
    # APPS
    # ===========================

    def apps_list(self) -> None:
        """List Splunk apps."""
        response = self._request(
            "GET", "/services/apps/local", params={"output_mode": "json", "count": 0}
        )

        entries = response.get("entry", [])
        apps = []

        for entry in entries:
            content = entry.get("content", {})
            apps.append(
                {
                    "name": entry.get("name"),
                    "label": content.get("label"),
                    "version": content.get("version"),
                    "visible": content.get("visible", False),
                    "disabled": content.get("disabled", False),
                }
            )

        self._success(apps, count=len(apps))

    # ===========================
    # INDEXES
    # ===========================

    def indexes_list(self) -> None:
        """List Splunk indexes."""
        response = self._request(
            "GET", "/services/data/indexes", params={"output_mode": "json", "count": 0}
        )

        entries = response.get("entry", [])
        indexes = []

        for entry in entries:
            content = entry.get("content", {})
            indexes.append(
                {
                    "name": entry.get("name"),
                    "total_event_count": content.get("totalEventCount", 0),
                    "current_db_size_mb": content.get("currentDBSizeMB", 0),
                    "max_time": content.get("maxTime"),
                    "min_time": content.get("minTime"),
                    "disabled": content.get("disabled", False),
                }
            )

        self._success(indexes, count=len(indexes))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Splunk CLI for search and resource operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="resource", help="Resource type")

    # ===========================
    # SEARCH
    # ===========================
    search_parser = subparsers.add_parser("search", help="Manage searches")
    search_subparsers = search_parser.add_subparsers(dest="action", help="Search action")

    # search submit
    search_submit_parser = search_subparsers.add_parser("submit", help="Submit search job")
    search_submit_parser.add_argument("--query", required=True, help="SPL search query")
    search_submit_parser.add_argument("--earliest-time", default="-1h", help="Start time (default: -1h)")
    search_submit_parser.add_argument("--latest-time", default="now", help="End time (default: now)")
    search_submit_parser.add_argument("--max-count", type=int, default=100, help="Max results (default: 100)")

    # search poll
    search_poll_parser = search_subparsers.add_parser("poll", help="Poll search job status")
    search_poll_parser.add_argument("--job-id", required=True, help="Search job ID (sid)")

    # search results
    search_results_parser = search_subparsers.add_parser("results", help="Get search results")
    search_results_parser.add_argument("--job-id", required=True, help="Search job ID (sid)")
    search_results_parser.add_argument("--offset", type=int, default=0, help="Result offset (default: 0)")
    search_results_parser.add_argument("--count", type=int, default=100, help="Result count (default: 100)")

    # search execute
    search_execute_parser = search_subparsers.add_parser("execute", help="Execute search and wait for results")
    search_execute_parser.add_argument("--query", required=True, help="SPL search query")
    search_execute_parser.add_argument("--earliest-time", default="-1h", help="Start time (default: -1h)")
    search_execute_parser.add_argument("--latest-time", default="now", help="End time (default: now)")
    search_execute_parser.add_argument("--max-count", type=int, default=100, help="Max results (default: 100)")
    search_execute_parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds (default: 60)")
    search_execute_parser.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds (default: 2)")

    # search delete
    search_delete_parser = search_subparsers.add_parser("delete", help="Delete search job")
    search_delete_parser.add_argument("--job-id", required=True, help="Search job ID (sid)")

    # ===========================
    # APPS
    # ===========================
    apps_parser = subparsers.add_parser("apps", help="Manage apps")
    apps_subparsers = apps_parser.add_subparsers(dest="action", help="App action")

    # apps list
    apps_subparsers.add_parser("list", help="List apps")

    # ===========================
    # INDEXES
    # ===========================
    indexes_parser = subparsers.add_parser("indexes", help="Manage indexes")
    indexes_subparsers = indexes_parser.add_subparsers(dest="action", help="Index action")

    # indexes list
    indexes_subparsers.add_parser("list", help="List indexes")

    # Parse arguments
    args = parser.parse_args()

    if not args.resource:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    client = SplunkClient()

    # Route to appropriate handler
    if args.resource == "search":
        if not args.action:
            search_parser.print_help()
            sys.exit(1)

        if args.action == "submit":
            client.search_submit(
                query=args.query,
                earliest_time=args.earliest_time,
                latest_time=args.latest_time,
                max_count=args.max_count,
            )
        elif args.action == "poll":
            client.search_poll(job_id=args.job_id)
        elif args.action == "results":
            client.search_results(job_id=args.job_id, offset=args.offset, count=args.count)
        elif args.action == "execute":
            client.search_execute(
                query=args.query,
                earliest_time=args.earliest_time,
                latest_time=args.latest_time,
                max_count=args.max_count,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
        elif args.action == "delete":
            client.search_delete(job_id=args.job_id)

    elif args.resource == "apps":
        if not args.action:
            apps_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.apps_list()

    elif args.resource == "indexes":
        if not args.action:
            indexes_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.indexes_list()


if __name__ == "__main__":
    main()
