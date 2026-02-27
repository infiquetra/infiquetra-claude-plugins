#!/usr/bin/env python3
"""
PagerDuty CLI - Command-line interface for PagerDuty API operations.

This script provides a unified CLI for PagerDuty operations including incident management,
service configuration, team management, and on-call orchestration. All output is JSON for
Claude Code to parse.

Environment Variables:
    PAGERDUTY_API_KEY: PagerDuty API token (required)

Usage:
    python pagerduty_client.py incidents list --status triggered
    python pagerduty_client.py incidents acknowledge --id PXXXXX
    python pagerduty_client.py services list --team-id $PAGERDUTY_DEFAULT_TEAM_ID
    python pagerduty_client.py teams list
    python pagerduty_client.py oncall list --schedule-id PXXXXX
"""

import argparse
import json
import os
import sys
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


class PagerDutyClient:
    """Wrapper for PagerDuty API operations with JSON output."""

    def __init__(self, token: str | None = None):
        """Initialize the PagerDuty client.

        Args:
            token: PagerDuty API token (defaults to PAGERDUTY_API_KEY env var)
        """
        # Read defaults from environment at instantiation time (not import time)
        self.DEFAULT_TEAM_ID = os.environ.get("PAGERDUTY_DEFAULT_TEAM_ID", "")
        self.DEFAULT_ESCALATION_POLICY_ID = os.environ.get(
            "PAGERDUTY_DEFAULT_ESCALATION_POLICY_ID", ""
        )
        self.token = token or os.getenv("PAGERDUTY_API_KEY")
        if not self.token:
            self._error("PAGERDUTY_API_KEY environment variable not set")
            sys.exit(1)

        self.base_url = "https://api.pagerduty.com"
        self.headers = {
            "Authorization": f"Token token={self.token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
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
        """Make HTTP request to PagerDuty API with error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/incidents")
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
                json=data,
                timeout=30,
            )

            # Handle rate limiting with exponential backoff
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self._error(
                    f"Rate limit exceeded. Retry after {retry_after} seconds",
                    status_code=429,
                    retry_after=retry_after,
                )
                sys.exit(1)

            # Handle errors
            if response.status_code >= 400:
                error_msg = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"].get("message", error_msg)
                except (ValueError, KeyError):
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

    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        key: str = "items",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Paginate through API results.

        Args:
            endpoint: API endpoint
            params: Query parameters
            key: Key in response containing items (default: "items", PagerDuty uses various keys)
            limit: Items per page

        Returns:
            List of all items
        """
        all_items = []
        offset = 0
        params = params or {}
        params["limit"] = limit

        while True:
            params["offset"] = offset
            response = self._request("GET", endpoint, params=params)

            # PagerDuty wraps results in different keys depending on endpoint
            # Common keys: incidents, services, teams, users, escalation_policies, schedules
            items = response.get(key, [])
            if not items:
                # Try to find the right key automatically
                for possible_key in ["incidents", "services", "teams", "users",
                                    "escalation_policies", "schedules", "oncalls"]:
                    if possible_key in response:
                        items = response[possible_key]
                        break

            if not items:
                break

            all_items.extend(items)

            # Check if there are more pages
            if not response.get("more", False):
                break

            offset += limit

        return all_items

    # ===========================
    # INCIDENTS
    # ===========================

    def incidents_list(
        self,
        status: str | None = None,
        urgency: str | None = None,
        service_id: str | None = None,
        team_id: str | None = None,
        user_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        sort_by: str = "created_at:desc",
    ) -> None:
        """List incidents with optional filters.

        Args:
            status: Filter by status (triggered, acknowledged, resolved)
            urgency: Filter by urgency (high, low)
            service_id: Filter by service ID
            team_id: Filter by team ID (defaults to Infiquetra team)
            user_id: Filter by assigned user ID
            since: Start date/time (ISO 8601)
            until: End date/time (ISO 8601)
            sort_by: Sort order (default: created_at:desc)
        """
        params = {"sort_by": sort_by}

        if status:
            params["statuses[]"] = status
        if urgency:
            params["urgencies[]"] = urgency
        if service_id:
            params["service_ids[]"] = service_id
        if team_id or (team_id is None and not user_id):
            # Default to Infiquetra team if no filters specified
            params["team_ids[]"] = team_id or self.DEFAULT_TEAM_ID
        if user_id:
            params["user_ids[]"] = user_id
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        incidents = self._paginate("/incidents", params=params, key="incidents")
        self._success(incidents, count=len(incidents))

    def incidents_get(self, incident_id: str) -> None:
        """Get incident details.

        Args:
            incident_id: Incident ID
        """
        response = self._request("GET", f"/incidents/{incident_id}")
        self._success(response.get("incident", {}))

    def incidents_acknowledge(self, incident_id: str, from_email: str | None = None) -> None:
        """Acknowledge an incident.

        Args:
            incident_id: Incident ID
            from_email: Email of user acknowledging (optional)
        """
        data = {
            "incident": {
                "type": "incident_reference",
                "status": "acknowledged",
            }
        }

        headers = self.headers.copy()
        if from_email:
            headers["From"] = from_email

        response = self._request("PUT", f"/incidents/{incident_id}", data=data)
        self._success(response.get("incident", {}), message="Incident acknowledged")

    def incidents_resolve(self, incident_id: str, from_email: str | None = None) -> None:
        """Resolve an incident.

        Args:
            incident_id: Incident ID
            from_email: Email of user resolving (optional)
        """
        data = {
            "incident": {
                "type": "incident_reference",
                "status": "resolved",
            }
        }

        headers = self.headers.copy()
        if from_email:
            headers["From"] = from_email

        response = self._request("PUT", f"/incidents/{incident_id}", data=data)
        self._success(response.get("incident", {}), message="Incident resolved")

    def incidents_add_note(self, incident_id: str, content: str, from_email: str | None = None) -> None:
        """Add a note to an incident.

        Args:
            incident_id: Incident ID
            content: Note content
            from_email: Email of user adding note (optional)
        """
        data = {"note": {"content": content}}

        headers = self.headers.copy()
        if from_email:
            headers["From"] = from_email

        response = self._request("POST", f"/incidents/{incident_id}/notes", data=data)
        self._success(response.get("note", {}), message="Note added to incident")

    def incidents_reassign(self, incident_id: str, user_id: str, from_email: str | None = None) -> None:
        """Reassign an incident to a different user.

        Args:
            incident_id: Incident ID
            user_id: Target user ID
            from_email: Email of user reassigning (optional)
        """
        data = {
            "incident": {
                "type": "incident_reference",
                "assignments": [{"assignee": {"id": user_id, "type": "user_reference"}}],
            }
        }

        headers = self.headers.copy()
        if from_email:
            headers["From"] = from_email

        response = self._request("PUT", f"/incidents/{incident_id}", data=data)
        self._success(response.get("incident", {}), message=f"Incident reassigned to user {user_id}")

    # ===========================
    # SERVICES
    # ===========================

    def services_list(self, team_id: str | None = None, query: str | None = None) -> None:
        """List services.

        Args:
            team_id: Filter by team ID (defaults to Infiquetra team)
            query: Search query
        """
        params = {}

        if team_id or team_id is None:
            params["team_ids[]"] = team_id or self.DEFAULT_TEAM_ID
        if query:
            params["query"] = query

        services = self._paginate("/services", params=params, key="services")
        self._success(services, count=len(services))

    def services_get(self, service_id: str) -> None:
        """Get service details.

        Args:
            service_id: Service ID
        """
        response = self._request("GET", f"/services/{service_id}")
        self._success(response.get("service", {}))

    def services_create(
        self,
        name: str,
        description: str | None = None,
        escalation_policy_id: str | None = None,
    ) -> None:
        """Create a new service.

        Args:
            name: Service name
            description: Service description
            escalation_policy_id: Escalation policy ID (defaults to Infiquetra policy)
        """
        data = {
            "service": {
                "type": "service",
                "name": name,
                "description": description or "",
                "escalation_policy": {
                    "id": escalation_policy_id or self.DEFAULT_ESCALATION_POLICY_ID,
                    "type": "escalation_policy_reference",
                },
            }
        }

        response = self._request("POST", "/services", data=data)
        self._success(response.get("service", {}), message=f"Service '{name}' created")

    def services_update(
        self,
        service_id: str,
        name: str | None = None,
        description: str | None = None,
        escalation_policy_id: str | None = None,
    ) -> None:
        """Update a service.

        Args:
            service_id: Service ID
            name: New service name
            description: New description
            escalation_policy_id: New escalation policy ID
        """
        # Get current service
        current = self._request("GET", f"/services/{service_id}")
        service = current.get("service", {})

        # Build update data
        update_data = {
            "service": {
                "type": "service",
                "name": name or service.get("name"),
                "description": description or service.get("description", ""),
            }
        }

        if escalation_policy_id:
            update_data["service"]["escalation_policy"] = {
                "id": escalation_policy_id,
                "type": "escalation_policy_reference",
            }

        response = self._request("PUT", f"/services/{service_id}", data=update_data)
        self._success(response.get("service", {}), message=f"Service {service_id} updated")

    def services_delete(self, service_id: str) -> None:
        """Delete a service.

        Args:
            service_id: Service ID
        """
        self._request("DELETE", f"/services/{service_id}")
        self._success({}, message=f"Service {service_id} deleted")

    # ===========================
    # TEAMS
    # ===========================

    def teams_list(self, query: str | None = None) -> None:
        """List teams.

        Args:
            query: Search query
        """
        params = {}
        if query:
            params["query"] = query

        teams = self._paginate("/teams", params=params, key="teams")
        self._success(teams, count=len(teams))

    def teams_get(self, team_id: str) -> None:
        """Get team details.

        Args:
            team_id: Team ID
        """
        response = self._request("GET", f"/teams/{team_id}")
        self._success(response.get("team", {}))

    def teams_create(self, name: str, description: str | None = None) -> None:
        """Create a new team.

        Args:
            name: Team name
            description: Team description
        """
        data = {
            "team": {
                "type": "team",
                "name": name,
                "description": description or "",
            }
        }

        response = self._request("POST", "/teams", data=data)
        self._success(response.get("team", {}), message=f"Team '{name}' created")

    def teams_update(
        self,
        team_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Update a team.

        Args:
            team_id: Team ID
            name: New team name
            description: New description
        """
        # Get current team
        current = self._request("GET", f"/teams/{team_id}")
        team = current.get("team", {})

        update_data = {
            "team": {
                "type": "team",
                "name": name or team.get("name"),
                "description": description or team.get("description", ""),
            }
        }

        response = self._request("PUT", f"/teams/{team_id}", data=update_data)
        self._success(response.get("team", {}), message=f"Team {team_id} updated")

    def teams_delete(self, team_id: str) -> None:
        """Delete a team.

        Args:
            team_id: Team ID
        """
        self._request("DELETE", f"/teams/{team_id}")
        self._success({}, message=f"Team {team_id} deleted")

    def teams_members_list(self, team_id: str) -> None:
        """List team members.

        Args:
            team_id: Team ID
        """
        members = self._paginate(f"/teams/{team_id}/members", key="members")
        self._success(members, count=len(members))

    def teams_members_add(self, team_id: str, user_id: str, role: str = "manager") -> None:
        """Add a member to a team.

        Args:
            team_id: Team ID
            user_id: User ID to add
            role: User role (manager, responder, observer)
        """
        data = {
            "user": {
                "id": user_id,
                "type": "user_reference",
            },
            "role": role,
        }

        response = self._request("PUT", f"/teams/{team_id}/users/{user_id}", data=data)
        self._success(response, message=f"User {user_id} added to team {team_id}")

    def teams_members_remove(self, team_id: str, user_id: str) -> None:
        """Remove a member from a team.

        Args:
            team_id: Team ID
            user_id: User ID to remove
        """
        self._request("DELETE", f"/teams/{team_id}/users/{user_id}")
        self._success({}, message=f"User {user_id} removed from team {team_id}")

    # ===========================
    # ESCALATION POLICIES
    # ===========================

    def policies_list(self, team_id: str | None = None, query: str | None = None) -> None:
        """List escalation policies.

        Args:
            team_id: Filter by team ID
            query: Search query
        """
        params = {}
        if team_id:
            params["team_ids[]"] = team_id
        if query:
            params["query"] = query

        policies = self._paginate("/escalation_policies", params=params, key="escalation_policies")
        self._success(policies, count=len(policies))

    def policies_get(self, policy_id: str) -> None:
        """Get escalation policy details.

        Args:
            policy_id: Escalation policy ID
        """
        response = self._request("GET", f"/escalation_policies/{policy_id}")
        self._success(response.get("escalation_policy", {}))

    def policies_create(
        self,
        name: str,
        escalation_rules: list[dict[str, Any]],
        description: str | None = None,
        team_id: str | None = None,
    ) -> None:
        """Create a new escalation policy.

        Args:
            name: Policy name
            escalation_rules: List of escalation rules
            description: Policy description
            team_id: Team ID to assign policy to
        """
        data = {
            "escalation_policy": {
                "type": "escalation_policy",
                "name": name,
                "description": description or "",
                "escalation_rules": escalation_rules,
            }
        }

        if team_id:
            data["escalation_policy"]["teams"] = [{"id": team_id, "type": "team_reference"}]

        response = self._request("POST", "/escalation_policies", data=data)
        self._success(response.get("escalation_policy", {}), message=f"Escalation policy '{name}' created")

    def policies_update(
        self,
        policy_id: str,
        name: str | None = None,
        escalation_rules: list[dict[str, Any]] | None = None,
        description: str | None = None,
    ) -> None:
        """Update an escalation policy.

        Args:
            policy_id: Policy ID
            name: New policy name
            escalation_rules: New escalation rules
            description: New description
        """
        # Get current policy
        current = self._request("GET", f"/escalation_policies/{policy_id}")
        policy = current.get("escalation_policy", {})

        update_data = {
            "escalation_policy": {
                "type": "escalation_policy",
                "name": name or policy.get("name"),
                "description": description or policy.get("description", ""),
                "escalation_rules": escalation_rules or policy.get("escalation_rules", []),
            }
        }

        response = self._request("PUT", f"/escalation_policies/{policy_id}", data=update_data)
        self._success(response.get("escalation_policy", {}), message=f"Escalation policy {policy_id} updated")

    def policies_delete(self, policy_id: str) -> None:
        """Delete an escalation policy.

        Args:
            policy_id: Policy ID
        """
        self._request("DELETE", f"/escalation_policies/{policy_id}")
        self._success({}, message=f"Escalation policy {policy_id} deleted")

    # ===========================
    # ON-CALL SCHEDULES
    # ===========================

    def schedules_list(self, query: str | None = None) -> None:
        """List on-call schedules.

        Args:
            query: Search query
        """
        params = {}
        if query:
            params["query"] = query

        schedules = self._paginate("/schedules", params=params, key="schedules")
        self._success(schedules, count=len(schedules))

    def schedules_get(self, schedule_id: str) -> None:
        """Get schedule details.

        Args:
            schedule_id: Schedule ID
        """
        response = self._request("GET", f"/schedules/{schedule_id}")
        self._success(response.get("schedule", {}))

    def oncall_list(
        self,
        schedule_id: str | None = None,
        escalation_policy_id: str | None = None,
        user_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> None:
        """List current on-call users.

        Args:
            schedule_id: Filter by schedule ID
            escalation_policy_id: Filter by escalation policy ID
            user_id: Filter by user ID
            since: Start date/time (ISO 8601)
            until: End date/time (ISO 8601)
        """
        params = {}

        if schedule_id:
            params["schedule_ids[]"] = schedule_id
        if escalation_policy_id:
            params["escalation_policy_ids[]"] = escalation_policy_id
        if user_id:
            params["user_ids[]"] = user_id
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        oncalls = self._paginate("/oncalls", params=params, key="oncalls")
        self._success(oncalls, count=len(oncalls))

    # ===========================
    # USERS
    # ===========================

    def users_list(self, team_id: str | None = None, query: str | None = None) -> None:
        """List users.

        Args:
            team_id: Filter by team ID
            query: Search query (email, name)
        """
        params = {}
        if team_id:
            params["team_ids[]"] = team_id
        if query:
            params["query"] = query

        users = self._paginate("/users", params=params, key="users")
        self._success(users, count=len(users))

    def users_get(self, user_id: str) -> None:
        """Get user details.

        Args:
            user_id: User ID
        """
        response = self._request("GET", f"/users/{user_id}")
        self._success(response.get("user", {}))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PagerDuty CLI for incident management and operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="resource", help="Resource type")

    # ===========================
    # INCIDENTS
    # ===========================
    incidents_parser = subparsers.add_parser("incidents", help="Manage incidents")
    incidents_subparsers = incidents_parser.add_subparsers(dest="action", help="Incident action")

    # incidents list
    incidents_list_parser = incidents_subparsers.add_parser("list", help="List incidents")
    incidents_list_parser.add_argument("--status", choices=["triggered", "acknowledged", "resolved"], help="Filter by status")
    incidents_list_parser.add_argument("--urgency", choices=["high", "low"], help="Filter by urgency")
    incidents_list_parser.add_argument("--service-id", help="Filter by service ID")
    incidents_list_parser.add_argument("--team-id", help="Filter by team ID (defaults to Infiquetra team)")
    incidents_list_parser.add_argument("--user-id", help="Filter by assigned user ID")
    incidents_list_parser.add_argument("--since", help="Start date/time (ISO 8601)")
    incidents_list_parser.add_argument("--until", help="End date/time (ISO 8601)")
    incidents_list_parser.add_argument("--sort-by", default="created_at:desc", help="Sort order")

    # incidents get
    incidents_get_parser = incidents_subparsers.add_parser("get", help="Get incident details")
    incidents_get_parser.add_argument("--id", required=True, help="Incident ID")

    # incidents acknowledge
    incidents_ack_parser = incidents_subparsers.add_parser("acknowledge", help="Acknowledge incident")
    incidents_ack_parser.add_argument("--id", required=True, help="Incident ID")
    incidents_ack_parser.add_argument("--from-email", help="Email of user acknowledging")

    # incidents resolve
    incidents_resolve_parser = incidents_subparsers.add_parser("resolve", help="Resolve incident")
    incidents_resolve_parser.add_argument("--id", required=True, help="Incident ID")
    incidents_resolve_parser.add_argument("--from-email", help="Email of user resolving")

    # incidents add-note
    incidents_note_parser = incidents_subparsers.add_parser("add-note", help="Add note to incident")
    incidents_note_parser.add_argument("--id", required=True, help="Incident ID")
    incidents_note_parser.add_argument("--content", required=True, help="Note content")
    incidents_note_parser.add_argument("--from-email", help="Email of user adding note")

    # incidents reassign
    incidents_reassign_parser = incidents_subparsers.add_parser("reassign", help="Reassign incident")
    incidents_reassign_parser.add_argument("--id", required=True, help="Incident ID")
    incidents_reassign_parser.add_argument("--user-id", required=True, help="Target user ID")
    incidents_reassign_parser.add_argument("--from-email", help="Email of user reassigning")

    # ===========================
    # SERVICES
    # ===========================
    services_parser = subparsers.add_parser("services", help="Manage services")
    services_subparsers = services_parser.add_subparsers(dest="action", help="Service action")

    # services list
    services_list_parser = services_subparsers.add_parser("list", help="List services")
    services_list_parser.add_argument("--team-id", help="Filter by team ID (defaults to Infiquetra team)")
    services_list_parser.add_argument("--query", help="Search query")

    # services get
    services_get_parser = services_subparsers.add_parser("get", help="Get service details")
    services_get_parser.add_argument("--id", required=True, help="Service ID")

    # services create
    services_create_parser = services_subparsers.add_parser("create", help="Create service")
    services_create_parser.add_argument("--name", required=True, help="Service name")
    services_create_parser.add_argument("--description", help="Service description")
    services_create_parser.add_argument("--escalation-policy-id", help="Escalation policy ID (defaults to Infiquetra policy)")

    # services update
    services_update_parser = services_subparsers.add_parser("update", help="Update service")
    services_update_parser.add_argument("--id", required=True, help="Service ID")
    services_update_parser.add_argument("--name", help="New service name")
    services_update_parser.add_argument("--description", help="New description")
    services_update_parser.add_argument("--escalation-policy-id", help="New escalation policy ID")

    # services delete
    services_delete_parser = services_subparsers.add_parser("delete", help="Delete service")
    services_delete_parser.add_argument("--id", required=True, help="Service ID")

    # ===========================
    # TEAMS
    # ===========================
    teams_parser = subparsers.add_parser("teams", help="Manage teams")
    teams_subparsers = teams_parser.add_subparsers(dest="action", help="Team action")

    # teams list
    teams_list_parser = teams_subparsers.add_parser("list", help="List teams")
    teams_list_parser.add_argument("--query", help="Search query")

    # teams get
    teams_get_parser = teams_subparsers.add_parser("get", help="Get team details")
    teams_get_parser.add_argument("--id", required=True, help="Team ID")

    # teams create
    teams_create_parser = teams_subparsers.add_parser("create", help="Create team")
    teams_create_parser.add_argument("--name", required=True, help="Team name")
    teams_create_parser.add_argument("--description", help="Team description")

    # teams update
    teams_update_parser = teams_subparsers.add_parser("update", help="Update team")
    teams_update_parser.add_argument("--id", required=True, help="Team ID")
    teams_update_parser.add_argument("--name", help="New team name")
    teams_update_parser.add_argument("--description", help="New description")

    # teams delete
    teams_delete_parser = teams_subparsers.add_parser("delete", help="Delete team")
    teams_delete_parser.add_argument("--id", required=True, help="Team ID")

    # teams members
    teams_members_parser = teams_subparsers.add_parser("members", help="Manage team members")
    teams_members_parser.add_argument("--team-id", required=True, help="Team ID")
    teams_members_parser.add_argument("--action", choices=["list", "add", "remove"], required=True, help="Member action")
    teams_members_parser.add_argument("--user-id", help="User ID (for add/remove)")
    teams_members_parser.add_argument("--role", choices=["manager", "responder", "observer"], default="manager", help="User role (for add)")

    # ===========================
    # ESCALATION POLICIES
    # ===========================
    policies_parser = subparsers.add_parser("policies", help="Manage escalation policies")
    policies_subparsers = policies_parser.add_subparsers(dest="action", help="Policy action")

    # policies list
    policies_list_parser = policies_subparsers.add_parser("list", help="List escalation policies")
    policies_list_parser.add_argument("--team-id", help="Filter by team ID")
    policies_list_parser.add_argument("--query", help="Search query")

    # policies get
    policies_get_parser = policies_subparsers.add_parser("get", help="Get policy details")
    policies_get_parser.add_argument("--id", required=True, help="Policy ID")

    # ===========================
    # SCHEDULES
    # ===========================
    schedules_parser = subparsers.add_parser("schedules", help="Manage on-call schedules")
    schedules_subparsers = schedules_parser.add_subparsers(dest="action", help="Schedule action")

    # schedules list
    schedules_list_parser = schedules_subparsers.add_parser("list", help="List schedules")
    schedules_list_parser.add_argument("--query", help="Search query")

    # schedules get
    schedules_get_parser = schedules_subparsers.add_parser("get", help="Get schedule details")
    schedules_get_parser.add_argument("--id", required=True, help="Schedule ID")

    # ===========================
    # ON-CALL
    # ===========================
    oncall_parser = subparsers.add_parser("oncall", help="List current on-call users")
    oncall_parser.add_argument("--schedule-id", help="Filter by schedule ID")
    oncall_parser.add_argument("--escalation-policy-id", help="Filter by escalation policy ID")
    oncall_parser.add_argument("--user-id", help="Filter by user ID")
    oncall_parser.add_argument("--since", help="Start date/time (ISO 8601)")
    oncall_parser.add_argument("--until", help="End date/time (ISO 8601)")

    # ===========================
    # USERS
    # ===========================
    users_parser = subparsers.add_parser("users", help="Manage users")
    users_subparsers = users_parser.add_subparsers(dest="action", help="User action")

    # users list
    users_list_parser = users_subparsers.add_parser("list", help="List users")
    users_list_parser.add_argument("--team-id", help="Filter by team ID")
    users_list_parser.add_argument("--query", help="Search query (email, name)")

    # users get
    users_get_parser = users_subparsers.add_parser("get", help="Get user details")
    users_get_parser.add_argument("--id", required=True, help="User ID")

    # Parse arguments
    args = parser.parse_args()

    if not args.resource:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    client = PagerDutyClient()

    # Route to appropriate handler
    if args.resource == "incidents":
        if not args.action:
            incidents_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.incidents_list(
                status=args.status,
                urgency=args.urgency,
                service_id=args.service_id,
                team_id=args.team_id,
                user_id=args.user_id,
                since=args.since,
                until=args.until,
                sort_by=args.sort_by,
            )
        elif args.action == "get":
            client.incidents_get(incident_id=args.id)
        elif args.action == "acknowledge":
            client.incidents_acknowledge(incident_id=args.id, from_email=args.from_email)
        elif args.action == "resolve":
            client.incidents_resolve(incident_id=args.id, from_email=args.from_email)
        elif args.action == "add-note":
            client.incidents_add_note(incident_id=args.id, content=args.content, from_email=args.from_email)
        elif args.action == "reassign":
            client.incidents_reassign(incident_id=args.id, user_id=args.user_id, from_email=args.from_email)

    elif args.resource == "services":
        if not args.action:
            services_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.services_list(team_id=args.team_id, query=args.query)
        elif args.action == "get":
            client.services_get(service_id=args.id)
        elif args.action == "create":
            client.services_create(
                name=args.name,
                description=args.description,
                escalation_policy_id=args.escalation_policy_id,
            )
        elif args.action == "update":
            client.services_update(
                service_id=args.id,
                name=args.name,
                description=args.description,
                escalation_policy_id=args.escalation_policy_id,
            )
        elif args.action == "delete":
            client.services_delete(service_id=args.id)

    elif args.resource == "teams":
        if not args.action:
            teams_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.teams_list(query=args.query)
        elif args.action == "get":
            client.teams_get(team_id=args.id)
        elif args.action == "create":
            client.teams_create(name=args.name, description=args.description)
        elif args.action == "update":
            client.teams_update(team_id=args.id, name=args.name, description=args.description)
        elif args.action == "delete":
            client.teams_delete(team_id=args.id)
        elif args.action == "members":
            if args.action == "list":
                client.teams_members_list(team_id=args.team_id)
            elif args.action == "add":
                client.teams_members_add(team_id=args.team_id, user_id=args.user_id, role=args.role)
            elif args.action == "remove":
                client.teams_members_remove(team_id=args.team_id, user_id=args.user_id)

    elif args.resource == "policies":
        if not args.action:
            policies_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.policies_list(team_id=args.team_id, query=args.query)
        elif args.action == "get":
            client.policies_get(policy_id=args.id)

    elif args.resource == "schedules":
        if not args.action:
            schedules_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.schedules_list(query=args.query)
        elif args.action == "get":
            client.schedules_get(schedule_id=args.id)

    elif args.resource == "oncall":
        client.oncall_list(
            schedule_id=args.schedule_id,
            escalation_policy_id=args.escalation_policy_id,
            user_id=args.user_id,
            since=args.since,
            until=args.until,
        )

    elif args.resource == "users":
        if not args.action:
            users_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.users_list(team_id=args.team_id, query=args.query)
        elif args.action == "get":
            client.users_get(user_id=args.id)


if __name__ == "__main__":
    main()
