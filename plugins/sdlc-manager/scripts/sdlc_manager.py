#!/usr/bin/env python3
"""
Infiquetra SDLC Manager — Unified CLI for Infiquetra SDLC automation.

Reads configuration dynamically from the infiquetra-sdlc repository checkout
(INFIQUETRA_SDLC_PATH env var, default: ~/workspace/infiquetra/infiquetra-sdlc).

All GitHub operations use the `gh` CLI for zero-token-management auth.

Usage:
    sdlc_manager.py board view --project mount-olympus
    sdlc_manager.py board add --repo athena-service --number 42
    sdlc_manager.py board move --repo athena-service --number 42 --status "E2E Testing"
    sdlc_manager.py board archive --project mount-olympus [--dry-run]
    sdlc_manager.py board wip --project mount-olympus
    sdlc_manager.py board standup --project mount-olympus
    sdlc_manager.py board discover-fields --project mount-olympus

    sdlc_manager.py issue create --repo athena-service --type capability

    sdlc_manager.py labels sync-fields --repo athena-service --number 42
    sdlc_manager.py labels audit --repo athena-service
    sdlc_manager.py labels deploy --repo athena-service
    sdlc_manager.py labels auto-label --repo athena-service --number 42
    sdlc_manager.py fields create-option --project mount-olympus --field initiative --option "new-initiative"
    sdlc_manager.py fields discover --project mount-olympus

    sdlc_manager.py metrics cycle-time --project mount-olympus [--days 30] [--type capability]
    sdlc_manager.py metrics throughput --project mount-olympus [--weeks 4]
    sdlc_manager.py metrics wip-age --project mount-olympus
    sdlc_manager.py metrics column-time --project mount-olympus --number 42

    sdlc_manager.py milestones create --repo athena-service --title "Pilot: Auth MVP" --due-date 2026-04-15
    sdlc_manager.py milestones list --repo athena-service [--state open]
    sdlc_manager.py milestones progress --repo athena-service --milestone 1
    sdlc_manager.py milestones link --repo athena-service --issue 42 --milestone 1

    sdlc_manager.py rollout status [--team mount-olympus]
    sdlc_manager.py rollout gap-analysis --repo athena-service
    sdlc_manager.py rollout deploy-labels --repo athena-service
    sdlc_manager.py rollout deploy-templates --repo athena-service
    sdlc_manager.py rollout deploy-all --repo athena-service
    sdlc_manager.py rollout update --repo athena-service --field labels --status complete

    sdlc_manager.py flow set-field --project mount-olympus --repo R --number N --field Initiative --option <name>
    sdlc_manager.py flow field-options --project mount-olympus --field Objective
    sdlc_manager.py flow discover-project --repo athena-service
    sdlc_manager.py flow link-sub-issue --parent-repo R --parent-number P --child-repo R2 --child-number C
    sdlc_manager.py flow verify-label --repo athena-service --name high-priority [--color D93F0B] [--description "..."]
    sdlc_manager.py flow validate-card --repo athena-service --number 42

    sdlc_manager.py config show

Environment Variables:
    INFIQUETRA_SDLC_PATH: Path to infiquetra-sdlc repo (default: ~/workspace/infiquetra/infiquetra-sdlc)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ===========================
# CONFIGURATION
# ===========================

ORG = "infiquetra"


def get_sdlc_path() -> Path:
    """Get path to infiquetra-sdlc checkout."""
    env_path = os.environ.get("INFIQUETRA_SDLC_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / "workspace" / "infiquetra" / "infiquetra-sdlc"


def load_config() -> dict[str, Any]:
    """Load config from infiquetra-sdlc checkout with remote fallback."""
    sdlc_path = get_sdlc_path()
    config: dict[str, Any] = {}

    # `legacy_rollout_config` reads `beads-config.json` for back-compat.
    # That file was removed from infiquetra-sdlc on 2026-04-26 (Beads removal);
    # this key now degrades gracefully to {} on missing-file. Several functions
    # below (board_wip, rollout_status, rollout_update, config_show) read this
    # config; they treat empty as "no rollout state tracked" and behave
    # sensibly. When a replacement file ships (e.g., rollout-status.json),
    # rename the key + path here.
    config_files = {
        "project_mappings": sdlc_path / "config" / "project-mappings.json",
        "labels": sdlc_path / "config" / "labels.json",
        "legacy_rollout_config": sdlc_path / "config" / "beads-config.json",
    }

    for key, path in config_files.items():
        if path.exists():
            with open(path) as f:
                config[key] = json.load(f)
        else:
            # Remote fallback via gh api
            try:
                result = _gh(["api", f"repos/{ORG}/infiquetra-sdlc/contents/config/{path.name}",
                               "--jq", ".content"])
                if result:
                    import base64
                    content = base64.b64decode(result.strip()).decode()
                    config[key] = json.loads(content)
            except Exception:
                config[key] = {}

    config["sdlc_path"] = str(sdlc_path)
    return config


def get_project_config(config: dict, project_name: str) -> dict:
    """Get config for a specific project."""
    projects = config.get("project_mappings", {}).get("projects", {})
    if project_name not in projects:
        _error(f"Unknown project: {project_name}. Known projects: {', '.join(projects.keys())}")
        sys.exit(1)
    return projects[project_name]


def get_projects_for_repo(config: dict, repo_name: str) -> list[dict]:
    """Return list of project configs that this repo belongs to."""
    mappings = config.get("project_mappings", {})
    excluded = mappings.get("excluded_repositories", [])
    if repo_name in excluded:
        return []

    special = mappings.get("special_mappings", {})
    projects = mappings.get("projects", {})
    result = []

    if repo_name in special:
        project_nums = special[repo_name]["projects"]
        for proj in projects.values():
            if proj["number"] in project_nums:
                result.append(proj)
        return result

    for proj in projects.values():
        if repo_name in proj.get("repositories", []):
            result.append(proj)

    return result


# ===========================
# GH CLI WRAPPER
# ===========================

def _gh(args: list[str], input_data: str | None = None, capture: bool = True) -> str:
    """Run gh CLI command."""
    cmd = ["gh"] + args
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=capture,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            err = result.stderr.strip() if result.stderr else "Unknown error"
            raise RuntimeError(f"gh command failed: {err}")
        return result.stdout.strip() if capture else ""
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh command timed out after 60s")
    except FileNotFoundError:
        _error("gh CLI not found. Install from: https://cli.github.com/")
        sys.exit(1)


def _graphql(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query via gh CLI."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    args = ["api", "graphql", "--input", "-"]
    result = _gh(args, input_data=json.dumps(payload))
    data = json.loads(result)

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})


def _rest_get(path: str) -> Any:
    """Execute a REST GET via gh CLI."""
    result = _gh(["api", path])
    return json.loads(result)


def _rest_post(path: str, body: dict) -> Any:
    """Execute a REST POST via gh CLI."""
    result = _gh(["api", "--method", "POST", path,
                   "--input", "-"], input_data=json.dumps(body))
    return json.loads(result)


def _rest_patch(path: str, body: dict) -> Any:
    """Execute a REST PATCH via gh CLI."""
    result = _gh(["api", "--method", "PATCH", path,
                   "--input", "-"], input_data=json.dumps(body))
    return json.loads(result)


# ===========================
# OUTPUT HELPERS
# ===========================

def _out(data: Any, fmt: str = "text") -> None:
    """Output data in the requested format."""
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data if isinstance(data, str) else json.dumps(data, indent=2, default=str))


def _error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


# ===========================
# GRAPHQL QUERIES
# ===========================

QUERY_GET_ITEM_NODE_ID = """
query($org: String!, $repo: String!, $number: Int!) {
  repository(owner: $org, name: $repo) {
    issue(number: $number) { id number title }
    pullRequest(number: $number) { id number title }
  }
}
"""

QUERY_ADD_ITEM_TO_PROJECT = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"""

QUERY_ARCHIVE_ITEM = """
mutation($projectId: ID!, $itemId: ID!) {
  archiveProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
    item { id }
  }
}
"""

QUERY_SET_FIELD_VALUE = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { singleSelectOptionId: $optionId }
  }) { projectV2Item { id } }
}
"""

QUERY_GET_PROJECT_ITEMS = """
query($org: String!, $number: Int!, $cursor: String) {
  organization(login: $org) {
    projectV2(number: $number) {
      id
      title
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          createdAt
          updatedAt
          content {
            ... on Issue {
              number title url state
              labels(first: 20) { nodes { name } }
              repository { name }
              milestone { title dueOn }
            }
            ... on PullRequest {
              number title url state
              labels(first: 20) { nodes { name } }
              repository { name }
            }
          }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name id } }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field { ... on ProjectV2Field { name id } }
              }
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2Field { name id } }
              }
            }
          }
        }
      }
    }
  }
}
"""

QUERY_GET_PROJECT_FIELDS = """
query($org: String!, $number: Int!) {
  organization(login: $org) {
    projectV2(number: $number) {
      id
      title
      fields(first: 30) {
        nodes {
          ... on ProjectV2Field {
            id name dataType
          }
          ... on ProjectV2SingleSelectField {
            id name
            options { id name }
          }
          ... on ProjectV2IterationField {
            id name
          }
        }
      }
    }
  }
}
"""

QUERY_GET_ITEM_LABELS = """
query($org: String!, $repo: String!, $number: Int!) {
  repository(owner: $org, name: $repo) {
    issue(number: $number) { labels(first: 30) { nodes { name } } }
    pullRequest(number: $number) { labels(first: 30) { nodes { name } } }
  }
}
"""

QUERY_GET_ISSUE_TIMELINE = """
query($org: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $org, name: $repo) {
    issue(number: $number) {
      title
      createdAt
      closedAt
      timelineItems(first: 100, after: $cursor,
        itemTypes: [PROJECT_V2_ITEM_FIELD_VALUE_EVENT]) {
        pageInfo { hasNextPage endCursor }
        nodes {
          ... on ProjectV2ItemFieldValueEvent {
            createdAt
            previousProjectV2ItemFieldValue {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
            projectV2ItemFieldValue {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
          }
        }
      }
    }
  }
}
"""


# ===========================
# BOARD OPERATIONS
# ===========================

def get_project_items(project_number: int) -> tuple[str, list[dict]]:
    """Fetch all items from a project, returning (project_id, items)."""
    all_items = []
    cursor = None
    project_id = ""

    while True:
        data = _graphql(QUERY_GET_PROJECT_ITEMS, {
            "org": ORG,
            "number": project_number,
            "cursor": cursor,
        })
        proj = data.get("organization", {}).get("projectV2", {})
        if not project_id:
            project_id = proj.get("id", "")

        items_data = proj.get("items", {})
        all_items.extend(items_data.get("nodes", []))

        page_info = items_data.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    return project_id, all_items


def get_item_status(item: dict) -> str:
    """Extract Status field value from a project item."""
    for fv in item.get("fieldValues", {}).get("nodes", []):
        field_name = fv.get("field", {}).get("name", "")
        if field_name == "Status":
            return fv.get("name", "")
    return ""


def get_item_field_value(item: dict, field_name: str) -> str:
    """Extract any single-select or text field value."""
    for fv in item.get("fieldValues", {}).get("nodes", []):
        fn = fv.get("field", {}).get("name", "")
        if fn == field_name:
            return fv.get("name", "") or fv.get("text", "") or fv.get("date", "")
    return ""


def get_item_age_days(item: dict) -> float:
    """Get age of item in days (from createdAt)."""
    created = item.get("createdAt", "")
    if not created:
        return 0
    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def board_view(project_name: str, status_filter: str | None, fmt: str) -> None:
    """View project board items grouped by column."""
    config = load_config()
    proj = get_project_config(config, project_name)
    project_id, items = get_project_items(proj["number"])

    # Group by status
    columns: dict[str, list[dict]] = {}
    for item in items:
        status = get_item_status(item)
        if not status:
            status = "No Status"
        if status_filter and status != status_filter:
            continue
        columns.setdefault(status, []).append(item)

    # WIP limits
    wip_limits = {"Ready": 10, "In Development": None, "E2E Testing": 3,
                  "Deployment Ready": 5}
    column_order = ["Ready", "In Development", "E2E Testing", "Deployment Ready", "Deployed", "No Status"]

    if fmt == "json":
        _out({"project": project_name, "columns": columns}, fmt)
        return

    print(f"\n{'='*60}")
    print(f"  {proj['name']} (Project #{proj['number']})")
    print(f"{'='*60}\n")

    for col in column_order:
        col_items = columns.get(col, [])
        if not col_items and col not in wip_limits:
            continue

        limit = wip_limits.get(col)
        limit_str = f" [WIP: {len(col_items)}/{limit}]" if limit else f" [{len(col_items)} items]"
        over_limit = limit and len(col_items) > limit
        marker = " OVER LIMIT" if over_limit else ""

        print(f"### {col}{limit_str}{marker}")
        for item in col_items:
            content = item.get("content", {})
            repo = content.get("repository", {}).get("name", "unknown")
            number = content.get("number", "?")
            title = content.get("title", "")[:60]
            age = get_item_age_days(item)
            labels = [la["name"] for la in content.get("labels", {}).get("nodes", [])]
            type_label = next((la for la in labels if la in ["capability", "enhancement", "defect", "exploration"]), "")
            print(f"  - [{type_label or 'unknown'}] {repo}#{number}: {title} (age: {age:.0f}d)")
        print()


def board_add(repo: str, number: int, fmt: str, config: dict | None = None) -> None:
    """Add issue/PR to correct project(s)."""
    if not config:
        config = load_config()

    projects = get_projects_for_repo(config, repo)
    if not projects:
        mappings = config.get("project_mappings", {})
        excluded = mappings.get("excluded_repositories", [])
        if repo in excluded:
            print(f"Repo '{repo}' is excluded from project automation.")
        else:
            print(f"Repo '{repo}' is not mapped to any project. Add manually if needed.")
        return

    # Get item node ID
    data = _graphql(QUERY_GET_ITEM_NODE_ID, {"org": ORG, "repo": repo, "number": number})
    repo_data = data.get("repository", {})
    item_data = repo_data.get("issue") or repo_data.get("pullRequest")
    if not item_data:
        _error(f"Could not find issue/PR #{number} in {ORG}/{repo}")
        sys.exit(1)
    item_id = item_data["id"]

    results = []
    for proj in projects:
        try:
            _graphql(QUERY_ADD_ITEM_TO_PROJECT, {
                "projectId": proj["id"],
                "contentId": item_id,
            })
            results.append(f"Added {repo}#{number} to '{proj['name']}' (#{proj['number']})")

            # Sync label fields if project has label_fields config
            if "label_fields" in proj:
                sync_results = _sync_label_fields_for_item(
                    repo, number, proj, item_id
                )
                results.extend(sync_results)
        except Exception as e:
            results.append(f"Failed to add to '{proj['name']}': {e}")

    _out("\n".join(results), fmt)


def board_move(repo: str, number: int, status: str, fmt: str) -> None:
    """Move item to a different board column."""
    config = load_config()
    projects = get_projects_for_repo(config, repo)
    if not projects:
        _error(f"Repo '{repo}' not mapped to any project")
        sys.exit(1)

    results = []
    for proj in projects:
        project_id, items = get_project_items(proj["number"])

        # Find item
        target_item = None
        for item in items:
            content = item.get("content", {})
            if content.get("number") == number and \
               content.get("repository", {}).get("name") == repo:
                target_item = item
                break

        if not target_item:
            results.append(f"Item {repo}#{number} not found in '{proj['name']}'")
            continue

        # Find Status field ID and option ID via field discovery
        fields_data = _graphql(QUERY_GET_PROJECT_FIELDS, {"org": ORG, "number": proj["number"]})
        proj_fields = fields_data.get("organization", {}).get("projectV2", {}).get("fields", {}).get("nodes", [])

        status_field = None
        status_option_id = None
        for field in proj_fields:
            if field.get("name") == "Status":
                status_field = field
                for opt in field.get("options", []):
                    if opt["name"] == status:
                        status_option_id = opt["id"]
                        break
                break

        if not status_field:
            results.append(f"No Status field found in '{proj['name']}'")
            continue
        if not status_option_id:
            available = [o["name"] for o in status_field.get("options", [])]
            results.append(f"Status '{status}' not found. Available: {', '.join(available)}")
            continue

        try:
            _graphql(QUERY_SET_FIELD_VALUE, {
                "projectId": project_id,
                "itemId": target_item["id"],
                "fieldId": status_field["id"],
                "optionId": status_option_id,
            })
            results.append(f"Moved {repo}#{number} to '{status}' in '{proj['name']}'")
        except Exception as e:
            results.append(f"Failed to move: {e}")

    _out("\n".join(results), fmt)


def board_archive(project_name: str, dry_run: bool, fmt: str) -> None:
    """Archive items with 'Deployed' status."""
    config = load_config()
    proj = get_project_config(config, project_name)
    project_id, items = get_project_items(proj["number"])

    deployed = [i for i in items if get_item_status(i) == "Deployed"]

    if dry_run:
        print(f"DRY RUN: Would archive {len(deployed)} items from '{proj['name']}':")
        for item in deployed:
            content = item.get("content", {})
            print(f"  - {content.get('repository', {}).get('name', '?')}#{content.get('number', '?')}: {content.get('title', '')[:50]}")
        return

    results = []
    for item in deployed:
        content = item.get("content", {})
        label = f"{content.get('repository', {}).get('name', '?')}#{content.get('number', '?')}"
        try:
            _graphql(QUERY_ARCHIVE_ITEM, {
                "projectId": project_id,
                "itemId": item["id"],
            })
            results.append(f"Archived {label}")
        except Exception as e:
            results.append(f"Failed to archive {label}: {e}")

    ok = sum(1 for r in results if r.startswith("Archived"))
    _out(f"Archived {ok} items.\n" + "\n".join(results), fmt)


def board_wip(project_name: str, fmt: str) -> None:
    """Show WIP counts vs limits."""
    config = load_config()
    proj = get_project_config(config, project_name)
    _, items = get_project_items(proj["number"])

    # WIP limits: configurable via beads-config.json "wip_limits" section.
    # "In Development" default is 10 (conservative for a mixed human/agent team
    # where not all agents do dev work). Override in config for your team size.
    config_wip = config.get("legacy_rollout_config", {}).get("wip_limits", {})
    wip_limits = {
        "Ready": config_wip.get("ready", 10),
        "In Development": config_wip.get("in_development", 10),
        "E2E Testing": config_wip.get("e2e_testing", 3),
        "Deployment Ready": config_wip.get("deployment_ready", 5),
    }

    counts: dict[str, int] = {}
    for item in items:
        status = get_item_status(item)
        if status:
            counts[status] = counts.get(status, 0) + 1

    print(f"\nWIP Status — {proj['name']}")
    print("=" * 50)
    violations = []
    for col, limit in wip_limits.items():
        count = counts.get(col, 0)
        over = count > limit
        if over:
            violations.append(col)
        bar = "X" * count + "." * max(0, limit - count)
        marker = " OVER LIMIT" if over else ""
        print(f"  {col:20} {count:2}/{limit:<2} [{bar}]{marker}")

    if violations:
        print(f"\nWIP VIOLATIONS: {', '.join(violations)}")
        print("Stop pulling new work until WIP returns to limit.")
    else:
        print("\nAll WIP limits respected.")


def board_standup(project_name: str, fmt: str) -> None:
    """Right-to-left board review for standup."""
    config = load_config()
    proj = get_project_config(config, project_name)
    _, items = get_project_items(proj["number"])

    # Group and sort
    columns: dict[str, list[dict]] = {}
    for item in items:
        status = get_item_status(item) or "No Status"
        columns.setdefault(status, []).append(item)

    right_to_left = ["Deployed", "Deployment Ready", "E2E Testing", "In Development", "Ready"]

    print(f"\n{'='*60}")
    print(f"  STANDUP PREP — {proj['name']}")
    print(f"  {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    for col in right_to_left:
        col_items = columns.get(col, [])
        if not col_items:
            print(f"### {col}: (empty)")
            print()
            continue

        print(f"### {col} ({len(col_items)} items)")
        for item in col_items:
            content = item.get("content", {})
            repo = content.get("repository", {}).get("name", "?")
            number = content.get("number", "?")
            title = content.get("title", "")[:55]
            age = get_item_age_days(item)
            labels = [la["name"] for la in content.get("labels", {}).get("nodes", [])]
            blocked = "blocked" in labels
            marker = " BLOCKED" if blocked else ""
            aged = " AGING" if age > 3 else ""
            print(f"  - {repo}#{number}: {title}{marker}{aged} ({age:.0f}d)")
        print()

    # Summary
    total_active = sum(len(columns.get(c, [])) for c in ["In Development", "E2E Testing", "Deployment Ready"])
    print(f"Summary: {total_active} active items, {len(columns.get('Ready', []))} in Ready")


def board_discover_fields(project_name: str, fmt: str) -> None:
    """Discover all fields and options on a project."""
    config = load_config()
    proj = get_project_config(config, project_name)
    data = _graphql(QUERY_GET_PROJECT_FIELDS, {"org": ORG, "number": proj["number"]})
    fields = data.get("organization", {}).get("projectV2", {}).get("fields", {}).get("nodes", [])

    if fmt == "json":
        _out({"project": project_name, "fields": fields}, fmt)
        return

    print(f"\nFields for '{proj['name']}' (#{proj['number']})")
    print("=" * 50)
    for field in fields:
        name = field.get("name", "")
        fid = field.get("id", "")
        dtype = field.get("dataType", "")
        options = field.get("options", [])
        print(f"\n  {name} (type: {dtype or 'unknown'})")
        print(f"    ID: {fid}")
        if options:
            for opt in options:
                print(f"    Option: {opt['name']:30} ID: {opt['id']}")


# ===========================
# LABEL OPERATIONS
# ===========================

def _get_item_labels(repo: str, number: int) -> list[str]:
    """Get label names for an issue."""
    data = _graphql(QUERY_GET_ITEM_LABELS, {"org": ORG, "repo": repo, "number": number})
    repo_data = data.get("repository", {})
    item_data = repo_data.get("issue") or repo_data.get("pullRequest")
    if not item_data:
        return []
    return [n["name"] for n in item_data.get("labels", {}).get("nodes", [])]


def _sync_label_fields_for_item(
    repo: str, number: int, proj: dict, item_id: str
) -> list[str]:
    """Sync initiative/objective labels to project fields. Returns result messages."""
    label_fields = proj.get("label_fields", {})
    if not label_fields:
        return []

    labels = _get_item_labels(repo, number)
    results = []
    project_id = proj["id"]

    for label_prefix, field_config in label_fields.items():
        field_id = field_config.get("field_id", "")
        options = field_config.get("options", {})
        prefix = f"{label_prefix}:"

        matching = [lbl[len(prefix):] for lbl in labels if lbl.startswith(prefix)]
        if not matching:
            continue

        value = matching[0]
        option_id = options.get(value)

        if not option_id:
            results.append(f"No option ID for {label_prefix}:{value} — consider running 'fields create-option'")
            continue

        try:
            _graphql(QUERY_SET_FIELD_VALUE, {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "optionId": option_id,
            })
            results.append(f"Set {label_prefix}={value}")
        except Exception as e:
            results.append(f"Failed to set {label_prefix}={value}: {e}")

    return results


def labels_sync_fields(repo: str, number: int, fmt: str) -> None:
    """Sync initiative/objective labels to project single-select fields."""
    config = load_config()
    projects = get_projects_for_repo(config, repo)
    if not projects:
        _error(f"Repo '{repo}' not mapped to any project")
        sys.exit(1)

    all_results = []
    for proj in projects:
        if "label_fields" not in proj:
            continue

        # Find the project item ID
        project_id, items = get_project_items(proj["number"])
        target_item = next(
            (i for i in items
             if i.get("content", {}).get("number") == number
             and i.get("content", {}).get("repository", {}).get("name") == repo),
            None
        )
        if not target_item:
            all_results.append(f"Item {repo}#{number} not found in '{proj['name']}'")
            continue

        results = _sync_label_fields_for_item(repo, number, proj, target_item["id"])
        all_results.extend(results)

    _out("\n".join(all_results) if all_results else "No label fields to sync.", fmt)


def labels_audit(repo: str, fmt: str) -> None:
    """Check if repo has all required SDLC labels."""
    config = load_config()
    required_labels = [la["name"] for la in config.get("labels", {}).get("labels", [])]

    # Get existing labels
    try:
        existing_raw = _rest_get(f"/repos/{ORG}/{repo}/labels?per_page=100")
        existing = {la["name"] for la in existing_raw}
    except Exception as e:
        _error(f"Could not fetch labels from {repo}: {e}")
        sys.exit(1)

    missing = [la for la in required_labels if la not in existing]
    extra = [la for la in existing if la not in required_labels]

    if fmt == "json":
        _out({"repo": repo, "missing": missing, "extra": list(extra),
              "required_count": len(required_labels), "existing_count": len(existing)}, fmt)
        return

    print(f"\nLabel Audit: {ORG}/{repo}")
    print(f"Required: {len(required_labels)} | Existing: {len(existing)}")
    if missing:
        print(f"\nMissing ({len(missing)}):")
        for la in missing:
            print(f"  - {la}")
    else:
        print("\nAll required labels present")
    if extra:
        print(f"\nExtra labels ({len(extra)}):")
        for la in list(extra)[:10]:
            print(f"  - {la}")


def labels_deploy(repo: str, fmt: str) -> None:
    """Create/update all SDLC labels in target repo."""
    config = load_config()
    label_defs = config.get("labels", {}).get("labels", [])

    results = []
    for label in label_defs:
        name = label["name"]
        color = label["color"]
        description = label.get("description", "")

        try:
            _gh(["label", "create", name,
                 "--color", color,
                 "--description", description,
                 "--repo", f"{ORG}/{repo}",
                 "--force"])
            results.append(f"OK: {name}")
        except Exception as e:
            results.append(f"FAIL: {name}: {e}")

    ok = sum(1 for r in results if r.startswith("OK"))
    fail = len(results) - ok
    print(f"\nDeployed labels to {ORG}/{repo}: {ok} ok, {fail} failed")
    if fail:
        for r in results:
            if r.startswith("FAIL"):
                print(f"  {r}")


def labels_auto_label(repo: str, number: int, fmt: str) -> None:
    """Apply auto-label rules based on issue title/content."""
    config = load_config()
    rules = config.get("labels", {}).get("auto_label_rules", {})

    # Get issue title
    try:
        issue_data = _rest_get(f"/repos/{ORG}/{repo}/issues/{number}")
        title = issue_data.get("title", "")
        body = issue_data.get("body", "") or ""
    except Exception as e:
        _error(f"Could not fetch issue: {e}")
        sys.exit(1)

    text = f"{title} {body}"
    labels_to_add = []
    for rule_name, rule in rules.items():
        pattern = rule.get("pattern", "")
        if re.search(pattern, text, re.IGNORECASE):
            labels_to_add.extend(rule.get("add_labels", []))

    labels_to_add = list(set(labels_to_add))
    if not labels_to_add:
        print(f"No auto-label rules matched for {repo}#{number}")
        return

    # Apply labels
    try:
        _rest_post(
            f"/repos/{ORG}/{repo}/issues/{number}/labels",
            {"labels": labels_to_add}
        )
        print(f"Applied labels to {repo}#{number}: {', '.join(labels_to_add)}")
    except Exception as e:
        _error(f"Failed to apply labels: {e}")


def fields_create_option(project_name: str, field_name: str, option_name: str, fmt: str) -> None:
    """Create a new single-select option on a project field."""
    config = load_config()
    proj = get_project_config(config, project_name)

    # Discover fields
    data = _graphql(QUERY_GET_PROJECT_FIELDS, {"org": ORG, "number": proj["number"]})
    fields = data.get("organization", {}).get("projectV2", {}).get("fields", {}).get("nodes", [])

    target_field = None
    for f in fields:
        if f.get("name", "").lower() == field_name.lower():
            target_field = f
            break

    if not target_field:
        _error(f"Field '{field_name}' not found in project '{project_name}'")
        sys.exit(1)

    print(f"Creating option '{option_name}' for field '{field_name}' in '{project_name}'...")
    print(f"Field ID: {target_field['id']}")
    print(f"Existing options: {[o['name'] for o in target_field.get('options', [])]}")
    print(f"\nNote: Option creation via GraphQL may require specific permissions.")
    print(f"If this fails, add the option manually in the GitHub Projects UI:")
    print(f"  https://github.com/orgs/{ORG}/projects/{proj['number']}/settings/fields")


def fields_discover(project_name: str, fmt: str) -> None:
    """Alias for board discover-fields."""
    board_discover_fields(project_name, fmt)


# ===========================
# METRICS OPERATIONS
# ===========================

def _get_issue_column_times(org: str, repo: str, number: int) -> list[dict]:
    """Get time spent in each column via timeline events."""
    all_events = []
    cursor = None

    while True:
        data = _graphql(QUERY_GET_ISSUE_TIMELINE, {
            "org": org, "repo": repo, "number": number, "cursor": cursor
        })
        issue = data.get("repository", {}).get("issue", {})
        timeline = issue.get("timelineItems", {})
        all_events.extend(timeline.get("nodes", []))

        page_info = timeline.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    # Calculate time in each column
    transitions = []
    for event in all_events:
        if not event:
            continue
        prev = event.get("previousProjectV2ItemFieldValue", {})
        curr = event.get("projectV2ItemFieldValue", {})
        prev_status = prev.get("name", "") if prev else ""
        curr_status = curr.get("name", "") if curr else ""
        if curr_status:
            transitions.append({
                "at": event.get("createdAt", ""),
                "from": prev_status,
                "to": curr_status,
            })

    return transitions


def metrics_cycle_time(project_name: str, days: int, issue_type: str | None, fmt: str) -> None:
    """Calculate cycle time percentiles using timeline events."""
    config = load_config()
    proj = get_project_config(config, project_name)
    _, items = get_project_items(proj["number"])

    cycle_times = []

    print(f"Analyzing cycle times for '{proj['name']}' (last {days} days)...")
    print("This may take a moment as we fetch timeline events for each item.\n")

    for item in items:
        status = get_item_status(item)
        if status != "Deployed":
            continue

        content = item.get("content", {})
        labels = [la["name"] for la in content.get("labels", {}).get("nodes", [])]

        if issue_type and issue_type not in labels:
            continue

        repo = content.get("repository", {}).get("name", "")
        number = content.get("number")
        if not repo or not number:
            continue

        try:
            transitions = _get_issue_column_times(ORG, repo, number)
        except Exception:
            continue

        # Find In Development start and Deployed end
        dev_start = None
        deployed_time = None
        for t in transitions:
            if t["to"] == "In Development" and not dev_start:
                dev_start = datetime.fromisoformat(t["at"].replace("Z", "+00:00"))
            if t["to"] == "Deployed":
                deployed_time = datetime.fromisoformat(t["at"].replace("Z", "+00:00"))

        if dev_start and deployed_time:
            cycle_days = (deployed_time - dev_start).total_seconds() / 86400
            cycle_times.append(cycle_days)

    if not cycle_times:
        print("No completed items found in range.")
        return

    cycle_times.sort()
    n = len(cycle_times)
    p50 = cycle_times[int(n * 0.5)]
    p85 = cycle_times[int(n * 0.85)]
    p95 = cycle_times[min(int(n * 0.95), n - 1)]

    targets = {"capability": 5, "enhancement": 2, "defect": 1}
    target = targets.get(issue_type or "", None)

    if fmt == "json":
        _out({"count": n, "p50": p50, "p85": p85, "p95": p95, "target": target}, fmt)
        return

    print(f"Cycle Time — {proj['name']} ({issue_type or 'all types'})")
    print(f"Sample size: {n} items")
    target_ok = not target or p85 <= target
    print(f"  P50: {p50:.1f} days")
    print(f"  P85: {p85:.1f} days {'OK' if target_ok else 'OVER TARGET'}")
    print(f"  P95: {p95:.1f} days")
    if target:
        print(f"  Target: < {target} days (P85)")


def metrics_throughput(project_name: str, weeks: int, fmt: str) -> None:
    """Show items deployed per week."""
    config = load_config()
    proj = get_project_config(config, project_name)
    _, items = get_project_items(proj["number"])

    from collections import defaultdict
    weekly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for item in items:
        status = get_item_status(item)
        if status != "Deployed":
            continue

        content = item.get("content", {})
        labels = [la["name"] for la in content.get("labels", {}).get("nodes", [])]
        issue_type = next((la for la in labels if la in ["capability", "enhancement", "defect"]), "other")

        updated = item.get("updatedAt", "")
        if updated:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            week_key = dt.strftime("%Y-W%V")
            weekly[week_key][issue_type] += 1

    # Show last N weeks
    all_weeks = sorted(weekly.keys())[-weeks:]

    if fmt == "json":
        _out({"project": project_name, "weeks": {w: dict(v) for w, v in weekly.items() if w in all_weeks}}, fmt)
        return

    print(f"\nThroughput — {proj['name']} (last {weeks} weeks)")
    print(f"{'Week':15} {'Capabilities':12} {'Enhancements':12} {'Defects':8} {'Total':6}")
    print("-" * 55)
    for week in all_weeks:
        caps = weekly[week].get("capability", 0)
        enhs = weekly[week].get("enhancement", 0)
        defs = weekly[week].get("defect", 0)
        total = sum(weekly[week].values())
        print(f"  {week:13} {caps:12} {enhs:12} {defs:8} {total:6}")


def metrics_wip_age(project_name: str, fmt: str) -> None:
    """Show age of in-progress items."""
    config = load_config()
    proj = get_project_config(config, project_name)
    _, items = get_project_items(proj["number"])

    active_cols = ["Ready", "In Development", "E2E Testing", "Deployment Ready"]
    aged_thresholds = {"Ready": 2, "In Development": 5, "E2E Testing": 1, "Deployment Ready": 2}

    print(f"\nWIP Age — {proj['name']}")
    print("=" * 60)

    for col in active_cols:
        col_items = [(i, get_item_age_days(i)) for i in items if get_item_status(i) == col]
        col_items.sort(key=lambda x: x[1], reverse=True)
        threshold = aged_thresholds.get(col, 3)

        print(f"\n### {col}")
        for item, age in col_items:
            content = item.get("content", {})
            repo = content.get("repository", {}).get("name", "?")
            number = content.get("number", "?")
            title = content.get("title", "")[:45]
            flag = " AGING" if age > threshold else ""
            print(f"  - {repo}#{number}: {title} ({age:.0f}d){flag}")


def metrics_column_time(project_name: str, number: int, fmt: str) -> None:
    """Show time spent in each column for a specific item."""
    config = load_config()
    proj = get_project_config(config, project_name)
    _, items = get_project_items(proj["number"])

    # Find item and its repo
    target_item = None
    for item in items:
        if item.get("content", {}).get("number") == number:
            target_item = item
            break

    if not target_item:
        _error(f"Item #{number} not found in '{project_name}'")
        sys.exit(1)

    repo = target_item.get("content", {}).get("repository", {}).get("name", "")
    transitions = _get_issue_column_times(ORG, repo, number)

    print(f"\nColumn Times — {repo}#{number} in '{proj['name']}'")
    print(f"Title: {target_item.get('content', {}).get('title', '')}")
    print("=" * 50)

    if not transitions:
        print("No column transitions recorded.")
        return

    for i, t in enumerate(transitions):
        print(f"  {t['at'][:10]}: {t['from'] or 'start':25} -> {t['to']}")

    # Calculate durations between transitions
    print("\nTime in each column:")
    for i in range(len(transitions) - 1):
        t1 = datetime.fromisoformat(transitions[i]["at"].replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(transitions[i + 1]["at"].replace("Z", "+00:00"))
        duration_days = (t2 - t1).total_seconds() / 86400
        col = transitions[i]["to"]
        print(f"  {col:25}: {duration_days:.1f} days")


# ===========================
# MILESTONE OPERATIONS
# ===========================

def milestones_create(repo: str, title: str, due_date: str, description: str, fmt: str) -> None:
    """Create a GitHub milestone for an Objective."""
    body = {"title": title, "due_on": f"{due_date}T00:00:00Z"}
    if description:
        body["description"] = description

    try:
        result = _rest_post(f"/repos/{ORG}/{repo}/milestones", body)
        ms_number = result.get("number")
        url = result.get("html_url", "")
        print(f"Created milestone #{ms_number}: '{title}'")
        print(f"   URL: {url}")
        print(f"   Due: {due_date}")
    except Exception as e:
        _error(f"Failed to create milestone: {e}")


def milestones_list(repo: str, state: str, fmt: str) -> None:
    """List milestones in a repo."""
    try:
        milestones = _rest_get(f"/repos/{ORG}/{repo}/milestones?state={state}&per_page=50")
    except Exception as e:
        _error(f"Failed to list milestones: {e}")
        sys.exit(1)

    if fmt == "json":
        _out(milestones, fmt)
        return

    print(f"\nMilestones in {ORG}/{repo} ({state})")
    print("=" * 50)
    for ms in milestones:
        number = ms.get("number")
        title = ms.get("title", "")
        due = ms.get("due_on", "")[:10] if ms.get("due_on") else "no due date"
        open_count = ms.get("open_issues", 0)
        closed_count = ms.get("closed_issues", 0)
        total = open_count + closed_count
        pct = int(closed_count / total * 100) if total > 0 else 0
        print(f"  #{number}: {title}")
        print(f"    Due: {due} | Progress: {closed_count}/{total} ({pct}%)")


def milestones_progress(repo: str, milestone_num: int, fmt: str) -> None:
    """Show milestone completion progress."""
    try:
        ms = _rest_get(f"/repos/{ORG}/{repo}/milestones/{milestone_num}")
    except Exception as e:
        _error(f"Failed to get milestone: {e}")
        sys.exit(1)

    title = ms.get("title", "")
    open_count = ms.get("open_issues", 0)
    closed_count = ms.get("closed_issues", 0)
    total = open_count + closed_count
    pct = int(closed_count / total * 100) if total > 0 else 0
    due = ms.get("due_on", "")[:10] if ms.get("due_on") else "no due date"

    if fmt == "json":
        _out({"title": title, "open": open_count, "closed": closed_count,
              "total": total, "percent": pct, "due": due}, fmt)
        return

    print(f"\nMilestone Progress: {title}")
    print(f"  Due: {due}")
    bar = "X" * (pct // 5) + "." * (20 - pct // 5)
    print(f"  Progress: [{bar}] {pct}% ({closed_count}/{total} capabilities)")

    # Risk assessment
    if due != "no due date":
        due_dt = datetime.fromisoformat(due)
        days_left = (due_dt - datetime.now()).days
        if days_left < 0:
            print(f"  OVERDUE by {abs(days_left)} days")
        elif days_left < 7 and pct < 80:
            print(f"  AT RISK: {days_left} days left, only {pct}% complete")
        else:
            print(f"  {days_left} days until target date")


def milestones_link(repo: str, issue_num: int, milestone_num: int, fmt: str) -> None:
    """Link an issue to a milestone."""
    try:
        _rest_patch(
            f"/repos/{ORG}/{repo}/issues/{issue_num}",
            {"milestone": milestone_num}
        )
        print(f"Linked {repo}#{issue_num} to milestone #{milestone_num}")
    except Exception as e:
        _error(f"Failed to link issue to milestone: {e}")


# ===========================
# ROLLOUT OPERATIONS
# ===========================

def rollout_status(team_filter: str | None, fmt: str) -> None:
    """Show rollout status from config."""
    config = load_config()
    status = config.get("legacy_rollout_config", {})
    repos = status.get("repositories", {})
    summary = status.get("summary", {})

    if team_filter:
        repos = {k: v for k, v in repos.items() if v.get("team", "").lower() == team_filter.lower()}

    if fmt == "json":
        _out(status, fmt)
        return

    print(f"\nSDLC Rollout Status")
    print(f"Last updated: {status.get('last_updated', 'unknown')}")
    print(f"Total: {summary.get('total_repos', 0)} repos | "
          f"Complete: {summary.get('completed', 0)} | "
          f"In progress: {summary.get('in_progress', 0)} | "
          f"Pending: {summary.get('pending', 0)}")
    print()

    # Group by tier
    by_tier: dict[int, list[tuple[str, dict]]] = {}
    for repo_name, repo_data in repos.items():
        tier = repo_data.get("tier", 0)
        by_tier.setdefault(tier, []).append((repo_name, repo_data))

    for tier in sorted(by_tier.keys()):
        tier_repos = by_tier[tier]
        print(f"### Tier {tier}")
        for repo_name, repo_data in tier_repos:
            fields = ["labels", "templates", "claude_md", "project"]
            statuses = {f: repo_data.get(f, "unknown") for f in fields}
            complete = all(v == "complete" for v in statuses.values())
            in_progress = any(v == "complete" for v in statuses.values())
            if complete:
                marker = "DONE"
            elif in_progress:
                marker = "WIP"
            else:
                marker = "PENDING"
            team = repo_data.get("team", "")
            print(f"  [{marker}] {repo_name:40} [{team}]")
            if not complete:
                pending_fields = [f for f, v in statuses.items() if v != "complete"]
                print(f"       Pending: {', '.join(pending_fields)}")
        print()


def rollout_gap_analysis(repo: str, fmt: str) -> None:
    """Check what SDLC setup is missing from a repo."""
    config = load_config()
    required_labels = [la["name"] for la in config.get("labels", {}).get("labels", [])]
    template_names = ["capability.yml", "context-update.yml", "defect.yml",
                      "enhancement.yml", "exploration.yml", "objective.yml"]

    gaps = []

    # Check labels
    try:
        existing_labels_raw = _rest_get(f"/repos/{ORG}/{repo}/labels?per_page=100")
        existing_labels = {la["name"] for la in existing_labels_raw}
        missing_labels = [la for la in required_labels if la not in existing_labels]
        if missing_labels:
            gaps.append(f"Missing {len(missing_labels)} labels (run: sdlc_manager.py rollout deploy-labels --repo {repo})")
        else:
            gaps.append("All labels present")
    except Exception as e:
        gaps.append(f"Could not check labels: {e}")

    # Check templates
    try:
        existing_templates = _rest_get(f"/repos/{ORG}/{repo}/contents/.github/ISSUE_TEMPLATE")
        existing_template_names = {t["name"] for t in existing_templates}
        missing_templates = [t for t in template_names if t not in existing_template_names]
        if missing_templates:
            gaps.append(f"Missing templates: {', '.join(missing_templates)}")
        else:
            gaps.append("All issue templates present")
    except Exception:
        gaps.append(f"Missing .github/ISSUE_TEMPLATE/ directory (run: sdlc_manager.py rollout deploy-templates --repo {repo})")

    # Check project mapping
    projects = get_projects_for_repo(config, repo)
    if projects:
        gaps.append(f"Mapped to project(s): {', '.join(p['name'] for p in projects)}")
    else:
        gaps.append("Not mapped to any project")

    _out(f"\nGap Analysis: {ORG}/{repo}\n" + "\n".join(f"  - {g}" for g in gaps), fmt)


def rollout_deploy_labels(repo: str, fmt: str) -> None:
    """Deploy all SDLC labels to a repo."""
    labels_deploy(repo, fmt)


def rollout_deploy_templates(repo: str, fmt: str) -> None:
    """Copy all SDLC issue templates to target repo."""
    sdlc_path = get_sdlc_path()
    template_dir = sdlc_path / ".github" / "ISSUE_TEMPLATE"

    if not template_dir.exists():
        _error(f"Template directory not found: {template_dir}")
        sys.exit(1)

    templates = list(template_dir.glob("*.yml"))
    results = []

    for template_path in templates:
        with open(template_path) as f:
            content = f.read()

        import base64
        content_b64 = base64.b64encode(content.encode()).decode()

        gh_path = f".github/ISSUE_TEMPLATE/{template_path.name}"
        api_path = f"/repos/{ORG}/{repo}/contents/{gh_path}"

        # Check if file exists to get SHA for update
        sha = None
        try:
            existing = _rest_get(api_path)
            sha = existing.get("sha")
        except Exception:
            pass  # File doesn't exist yet

        body: dict[str, Any] = {
            "message": f"chore: deploy SDLC template {template_path.name}",
            "content": content_b64,
        }
        if sha:
            body["sha"] = sha

        try:
            if not sha:
                _rest_post(api_path, body)
            else:
                _rest_patch(api_path, body)
            results.append(f"OK: {template_path.name}")
        except Exception as e:
            results.append(f"FAIL: {template_path.name}: {e}")

    print(f"\nDeployed templates to {ORG}/{repo}:")
    for r in results:
        print(f"  {r}")


def rollout_deploy_all(repo: str, fmt: str) -> None:
    """Full deployment: labels + templates."""
    print(f"\n=== Deploying SDLC to {ORG}/{repo} ===\n")
    print("Step 1: Labels")
    rollout_deploy_labels(repo, fmt)
    print("\nStep 2: Templates")
    rollout_deploy_templates(repo, fmt)
    print("\nStep 3: Gap analysis")
    rollout_gap_analysis(repo, fmt)


def rollout_update(repo: str, field: str, status: str, fmt: str) -> None:
    """Update beads-config.json for a repo."""
    sdlc_path = get_sdlc_path()
    status_file = sdlc_path / "config" / "beads-config.json"

    config = load_config()
    beads = config.get("legacy_rollout_config", {})
    repos = beads.get("repositories", {})

    if repo not in repos:
        _error(f"Repo '{repo}' not found in beads-config.json")
        sys.exit(1)

    repos[repo][field] = status
    beads["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    # Recalculate summary
    summary = {"total_repos": len(repos), "completed": 0, "in_progress": 0, "pending": 0}
    for repo_data in repos.values():
        fields = ["labels", "templates", "claude_md", "project"]
        statuses_vals = [repo_data.get(f, "pending") for f in fields]
        if all(v == "complete" for v in statuses_vals):
            summary["completed"] += 1
        elif any(v == "complete" for v in statuses_vals):
            summary["in_progress"] += 1
        else:
            summary["pending"] += 1
    beads["summary"] = summary

    with open(status_file, "w") as f:
        json.dump(beads, f, indent=2)
        f.write("\n")

    print(f"Updated {repo}.{field} = {status} in beads-config.json")


# NOTE: The `beads` subcommand group + `_bd` shell helper + `beads_*`
# functions were removed in this PR. Beads/Dolt was decommissioned from
# the Mount Olympus coordination layer on 2026-04-26 (see
# infiquetra-sdlc/docs/engineering-journal/narratives/2026-04-26-beads-dolt-removed.md);
# the agent fleet now coordinates via Redis pub/sub (`olympus:*` channels)
# + GitHub Projects v2 + Discord per-card threads.


# ===========================
# FLOW OPERATIONS (Phase C)
# ===========================
# `flow` is a thin operator-facing surface over the GraphQL + REST APIs the
# plugin already uses elsewhere. Commands here are the minimum viable set
# needed to make the blueprint-to-issue workflow executable end-to-end:
#   - set-field          set a single-select project field on a card
#   - field-options      list current options for a project field
#   - discover-project   resolve which project a repo is mapped to
#   - link-sub-issue     wrap the native sub-issue API
#   - verify-label       self-heal missing labels (404 → create; exists → no-op)
#   - validate-card      run the card_validator schema check on an issue body


def _resolve_project_field(project_name: str, field_name: str) -> dict:
    """Look up a project field by name. Returns the field node (with
    id, name, options if SINGLE_SELECT). Raises RuntimeError if missing."""
    config = load_config()
    proj = get_project_config(config, project_name)
    data = _graphql(QUERY_GET_PROJECT_FIELDS, {"org": ORG, "number": proj["number"]})
    fields = data.get("organization", {}).get("projectV2", {}).get("fields", {}).get("nodes", [])
    for f in fields:
        if f.get("name", "").lower() == field_name.lower():
            return {**f, "_project_id": data["organization"]["projectV2"]["id"]}
    raise RuntimeError(
        f"Field '{field_name}' not found on project '{project_name}'. "
        f"Available fields: {[f.get('name') for f in fields]}. "
        f"If you expected this field to exist (e.g., Initiative or Objective), "
        f"the field-creation runbook is in "
        f"`infiquetra-sdlc/docs/operations/operational-reference.md` "
        f"under 'Initiative/Objective Tracking'."
    )


def flow_field_options(project_name: str, field_name: str, fmt: str) -> None:
    """List the current options for a project single-select field.
    Live discovery — option IDs rotate on rename/recreate; never cache them."""
    field = _resolve_project_field(project_name, field_name)
    options = field.get("options", [])
    if not options:
        _out(
            f"Field '{field_name}' has no options (or is not a SINGLE_SELECT field).",
            fmt,
        )
        return
    if fmt == "json":
        _out([{"id": o["id"], "name": o["name"]} for o in options], fmt)
    else:
        print(f"\nOptions for {project_name}.{field_name}:")
        for o in options:
            print(f"  {o['name']:30s}  (id: {o['id']})")


def flow_set_field(
    project_name: str,
    repo: str,
    number: int,
    field_name: str,
    option_name: str,
    fmt: str,
) -> None:
    """Set a single-select field value on a card. Idempotent: re-running
    with the same option produces the same final state."""
    field = _resolve_project_field(project_name, field_name)
    project_id = field["_project_id"]

    # Find the option by name (case-insensitive)
    options = field.get("options", [])
    option = next(
        (o for o in options if o.get("name", "").lower() == option_name.lower()),
        None,
    )
    if not option:
        raise RuntimeError(
            f"Option '{option_name}' not found on field '{field_name}'. "
            f"Available: {[o['name'] for o in options]}. "
            f"Hint: use `flow field-options --project {project_name} --field {field_name}` "
            f"to see current options."
        )

    # Find the project item for this repo+number
    _, items = get_project_items(get_project_config(load_config(), project_name)["number"])
    target_item = next(
        (i for i in items
         if i.get("content", {}).get("number") == number
         and i.get("content", {}).get("repository", {}).get("name") == repo),
        None,
    )
    if not target_item:
        raise RuntimeError(
            f"Issue {repo}#{number} is not on project '{project_name}'. "
            f"Use `sdlc_manager.py board add --repo {repo} --number {number}` first."
        )

    _graphql(QUERY_SET_FIELD_VALUE, {
        "projectId": project_id,
        "itemId": target_item["id"],
        "fieldId": field["id"],
        "optionId": option["id"],
    })
    _out(f"Set {field_name}='{option_name}' on {repo}#{number} ({project_name})", fmt)


def flow_discover_project(repo: str, fmt: str) -> None:
    """Resolve which project(s) a repo is mapped to via project-mappings.json.
    Returns a list of {name, number} entries; empty list if unmapped."""
    config = load_config()
    projects = get_projects_for_repo(config, repo)
    if not projects:
        mappings = config.get("project_mappings", {})
        excluded = mappings.get("excluded_repositories", [])
        if repo in excluded:
            _out(f"Repo '{repo}' is in excluded_repositories.", fmt)
        else:
            _out(f"Repo '{repo}' is not mapped to any project.", fmt)
        return
    if fmt == "json":
        _out([{"name": p["name"], "number": p["number"]} for p in projects], fmt)
    else:
        print(f"\n{repo} maps to:")
        for p in projects:
            print(f"  - {p['name']} (#{p['number']})")


def flow_link_sub_issue(
    parent_repo: str,
    parent_number: int,
    child_repo: str,
    child_number: int,
    fmt: str,
) -> None:
    """Link child as a native GitHub sub-issue of parent. Uses the REST
    sub-issues API. Cross-repo supported. Idempotent — re-POST returns
    HTTP 422 with 'already exists' which we treat as success."""
    # Look up child's database ID (the sub-issues API uses db_id, not node id)
    try:
        child_data = _rest_get(f"repos/{ORG}/{child_repo}/issues/{child_number}")
    except RuntimeError as e:
        raise RuntimeError(f"Could not fetch child {child_repo}#{child_number}: {e}")
    child_db_id = child_data.get("id")
    if not isinstance(child_db_id, int):
        raise RuntimeError(
            f"Child {child_repo}#{child_number} returned no integer 'id'; "
            f"got {child_db_id!r}. Cannot link."
        )

    # Validate parent exists + is an issue (not a PR)
    try:
        parent_data = _rest_get(f"repos/{ORG}/{parent_repo}/issues/{parent_number}")
    except RuntimeError as e:
        raise RuntimeError(f"Could not fetch parent {parent_repo}#{parent_number}: {e}")
    if "pull_request" in parent_data:
        raise RuntimeError(
            f"Parent {parent_repo}#{parent_number} is a PR, not an issue. "
            f"Sub-issues require an issue parent."
        )

    # POST the link. Endpoint is /repos/{owner}/{repo}/issues/{N}/sub_issues
    # with body {"sub_issue_id": <child_db_id>}. Idempotent on duplicate.
    try:
        _rest_post(
            f"repos/{ORG}/{parent_repo}/issues/{parent_number}/sub_issues",
            {"sub_issue_id": child_db_id},
        )
        _out(
            f"Linked {child_repo}#{child_number} as sub-issue of "
            f"{parent_repo}#{parent_number}",
            fmt,
        )
    except RuntimeError as e:
        # Detect "already exists" to honor idempotency
        msg = str(e).lower()
        if "already exists" in msg or "422" in msg:
            _out(
                f"Already linked: {child_repo}#{child_number} is already a "
                f"sub-issue of {parent_repo}#{parent_number} (idempotent re-run).",
                fmt,
            )
            return
        raise


def flow_verify_label(
    repo: str,
    name: str,
    color: str | None,
    description: str | None,
    fmt: str,
) -> None:
    """Self-healing label create. If the label exists on the repo, no-op.
    If 404, create with given color + description. Distinguishes 404
    (missing → create) from other errors (auth, rate-limit, server)."""
    # Probe for existence via gh api; capture stderr to detect 404 vs other failures
    cmd = ["api", f"repos/{ORG}/{repo}/labels/{name}"]
    try:
        _gh(cmd)
        _out(f"Label '{name}' already exists on {ORG}/{repo} (no-op).", fmt)
        return
    except RuntimeError as e:
        msg = str(e)
        if "Not Found" not in msg and "404" not in msg:
            # Re-raise non-404 errors verbatim — auth, rate-limit, server.
            # Do NOT silently treat them as missing.
            raise RuntimeError(
                f"verify-label probe failed with non-404 error (not creating): {msg}"
            )

    # 404 — create the label
    body: dict[str, str] = {"name": name}
    if color:
        body["color"] = color.lstrip("#")  # GH API rejects leading '#'
    if description:
        body["description"] = description
    _rest_post(f"repos/{ORG}/{repo}/labels", body)
    _out(f"Created label '{name}' on {ORG}/{repo}.", fmt)


# ===========================
# CARD VALIDATOR (mirror of home-lab card_validator.py)
# ===========================
# Mirrors the home-lab orchestrator's card_validator.py contract enough to
# pre-flight check an issue body before plan-review fires. This is NOT a
# strict re-implementation — the home-lab validator is the source of truth
# (`home-lab/ansible/roles/hermes_orchestrator/files/card_validator.py`) and
# should be consulted when the contract changes. We mirror the high-leverage
# checks: 6 required H3 headers, AC has ≥1 checklist item, Verification has
# ≥1 fenced code block, Files-expected has ≥1 path-like line, no placeholders.

# All regexes + the placeholder set below MUST mirror the home-lab source-of-truth:
# `home-lab/ansible/roles/hermes_orchestrator/files/card_validator.py`. When that
# file's contract changes, update these in the same PR.

_REQUIRED_H3_HEADERS = (
    "Objective",
    "Acceptance criteria",
    "Out-of-scope / non-goals",   # exact match: home-lab uses slash, not "or"
    "Files expected to change",
    "Tests to add or update",
    "Verification",
)
_OPTIONAL_H3_HEADERS = (
    "Notes / conventions",
    "Context library links",
)
_HEADER_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
# Checklist: `- [ ]`, `- [x]`, `* [ ]`, `* [X]`, with leading whitespace.
# Requires `\S` after the bracket — empty checkbox-only lines don't count
# (matches home-lab `card_validator.py:73`).
_CHECKLIST_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+\S", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"^```", re.MULTILINE)
# A "plausible path" — matches home-lab `_PATH_LINE_RE` exactly:
# optional bullet (`-` or `*`), optional quote/backtick wrapper, then a
# token containing either `/` or `.` (so `pyproject.toml` and `- src/foo.py`
# both pass). The orchestrator verifies actual existence; we just gate on
# "looks like a path."
_PATH_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s+)?"
    r"[`'\"]?"
    r"[\w./~\-]*[/.][\w./~\-]+"
    r".*$",
    re.MULTILINE,
)
_PLACEHOLDER_LINES = frozenset({
    "- [ ]", "-", "* [ ]", "*", "_no response_", "none", "<!-- placeholder -->",
})


def _split_sections(body: str) -> dict[str, str]:
    """Split a card body on `### H3` headers. Returns {header_text: section_text}."""
    matches = list(_HEADER_RE.finditer(body))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        header = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[header] = body[start:end].strip()
    return sections


def validate_card_body(body: str) -> tuple[bool, list[str]]:
    """Run the card_validator schema check on an issue body.

    Mirrors home-lab card_validator.py's high-leverage checks. When that
    file's contract changes, update this shim in the same PR.

    Returns (is_valid, errors). The 5 checks:
      1. All 6 required H3 sections present (Objective, Acceptance criteria,
         Out-of-scope / non-goals, Files expected to change, Tests to add
         or update, Verification).
      2. Acceptance criteria has at least one `- [ ]` or `* [ ]` checklist
         item with non-whitespace content after the bracket.
      3. Verification has at least one fenced code block (≥2 ``` markers).
      4. Files expected to change has at least one path-like line (matches
         home-lab _PATH_LINE_RE — accepts plain filenames like
         `pyproject.toml`, bullet-prefixed paths like `- src/foo.py`, and
         backtick-wrapped paths).
      5. No required section consists of only placeholder lines
         (`- [ ]`, `_No response_`, `None`, etc.).
    """
    errors: list[str] = []
    sections = _split_sections(body)
    section_names = set(sections.keys())

    # 1. Required headers present
    missing = [h for h in _REQUIRED_H3_HEADERS if h not in section_names]
    if missing:
        errors.append(f"Missing required H3 sections: {missing}")

    # 2. Acceptance criteria has ≥1 checklist item
    if "Acceptance criteria" in sections:
        ac = sections["Acceptance criteria"]
        if not _CHECKLIST_RE.search(ac):
            errors.append(
                "'Acceptance criteria' has no `- [ ]` checklist item "
                "(card_validator requires at least one)"
            )

    # 3. Verification has ≥1 fenced code block
    if "Verification" in sections:
        v = sections["Verification"]
        # Need at least 2 ``` markers to form one fenced block
        if len(_CODE_BLOCK_RE.findall(v)) < 2:
            errors.append(
                "'Verification' has no fenced code block "
                "(card_validator requires at least one ``` block)"
            )

    # 4. Files expected has ≥1 path-like line
    if "Files expected to change" in sections:
        f = sections["Files expected to change"]
        if not _PATH_LINE_RE.search(f):
            errors.append(
                "'Files expected to change' has no path-like line "
                "(card_validator requires at least one `dir/file` style entry)"
            )

    # 5. No placeholder-only sections
    for header in _REQUIRED_H3_HEADERS:
        if header not in sections:
            continue
        text = sections[header].strip()
        # Strip blank lines + check whether all remaining lines are placeholders
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines and all(ln.lower() in _PLACEHOLDER_LINES for ln in lines):
            errors.append(f"'{header}' contains only placeholder text")

    return (len(errors) == 0, errors)


class CardValidationError(RuntimeError):
    """Raised when an issue body fails the card_validator schema check.
    `main()` catches RuntimeError and exits non-zero — using a typed
    subclass lets future callers inspect the failure programmatically
    while preserving the standard CLI exit-code path."""

    def __init__(self, issue_ref: str, errors: list[str]):
        self.issue_ref = issue_ref
        self.errors = errors
        super().__init__(
            f"INVALID: {issue_ref} fails card_validator schema check: " +
            "; ".join(errors)
        )


def flow_validate_card(repo: str, number: int, fmt: str) -> None:
    """Fetch an issue body via gh, run card_validator, report result.

    Consistent with other flow helpers: raises RuntimeError on failure
    (caught by main() → exit 1). Does NOT call sys.exit() directly —
    that would bypass main()'s formatted-error path and break programmatic
    callers who import this function."""
    issue_ref = f"{repo}#{number}"
    try:
        data = _rest_get(f"repos/{ORG}/{repo}/issues/{number}")
    except RuntimeError as e:
        raise RuntimeError(f"Could not fetch issue {issue_ref}: {e}")
    body = data.get("body") or ""
    if not body:
        # Empty body fails trivially — report via the standard error path
        raise CardValidationError(issue_ref, ["Issue has empty body"])

    is_valid, errors = validate_card_body(body)
    if is_valid:
        _out(f"VALID: {issue_ref} passes card_validator schema check.", fmt)
        return

    # For JSON callers, emit the structured payload before raising.
    # The CardValidationError still propagates so main() exits 1.
    if fmt == "json":
        _out({"valid": False, "errors": errors, "issue": issue_ref}, fmt)
    else:
        print(f"INVALID: {issue_ref} fails card_validator schema check:")
        for e in errors:
            print(f"  - {e}")
    raise CardValidationError(issue_ref, errors)


# ===========================
# CONFIG OPERATIONS
# ===========================

def config_show(fmt: str) -> None:
    """Display loaded configuration."""
    config = load_config()
    sdlc_path = config.get("sdlc_path", "unknown")

    if fmt == "json":
        _out(config, fmt)
        return

    print(f"\nInfiquetra SDLC Manager Configuration")
    print(f"SDLC Path: {sdlc_path}")
    print(f"Organization: {ORG}")

    pm = config.get("project_mappings", {})
    projects = pm.get("projects", {})
    print(f"\nProjects: {len(projects)}")
    for name, proj in projects.items():
        print(f"  - {name}: #{proj['number']} — {proj.get('name', '')} ({len(proj.get('repositories', []))} repos)")

    labels = config.get("labels", {}).get("labels", [])
    print(f"\nLabels: {len(labels)} defined")

    beads = config.get("legacy_rollout_config", {})
    summary = beads.get("summary", {})
    print(f"\nRollout: {summary.get('completed', 0)}/{summary.get('total_repos', 0)} repos complete")


# ===========================
# CLI
# ===========================

def issue_create(repo: str, issue_type: str | None, fmt: str) -> None:
    """Interactive issue creation with template guidance."""
    if not issue_type:
        print("\nIssue Type Selection")
        print("=" * 40)
        print("Decision tree:")
        print("  1. Coordinating multiple capabilities with a target date? -> OBJECTIVE")
        print("  2. Broken in production? -> DEFECT")
        print("  3. New end-to-end deployable functionality? -> CAPABILITY")
        print("  4. Improving existing functionality? -> ENHANCEMENT")
        print("  5. Researching or investigating? -> EXPLORATION")
        print("  6. Updating documentation? -> CONTEXT UPDATE")
        print()
        types = ["capability", "enhancement", "defect", "exploration", "context-update", "objective"]
        choice = input("Select type (or press Enter for 'capability'): ").strip().lower()
        issue_type = choice if choice in types else "capability"

    print(f"\nCreating {issue_type} issue in {ORG}/{repo}")
    print(f"Use: gh issue create --repo {ORG}/{repo} --template {issue_type}.yml")
    print()

    try:
        result = input("Open interactive issue creation? (y/N): ").strip().lower()
        if result == "y":
            subprocess.run(
                ["gh", "issue", "create", "--repo", f"{ORG}/{repo}", "--web"],
            )
    except (EOFError, KeyboardInterrupt):
        print(f"\nRun manually: gh issue create --repo {ORG}/{repo} --template {issue_type}.yml")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Infiquetra SDLC Manager — Unified CLI for Infiquetra SDLC automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"],
                        default="text", help="Output format")

    subparsers = parser.add_subparsers(dest="resource", required=True)

    # ===========================
    # BOARD
    # ===========================
    board_p = subparsers.add_parser("board", help="Project board operations")
    board_sp = board_p.add_subparsers(dest="action", required=True)

    board_view_p = board_sp.add_parser("view", help="View board items by column")
    board_view_p.add_argument("--project", required=True, choices=["mount-olympus"])
    board_view_p.add_argument("--status", help="Filter by status column")

    board_add_p = board_sp.add_parser("add", help="Add issue/PR to project(s)")
    board_add_p.add_argument("--repo", required=True, help="Repository name (without org)")
    board_add_p.add_argument("--number", required=True, type=int, help="Issue or PR number")

    board_move_p = board_sp.add_parser("move", help="Move item to different column")
    board_move_p.add_argument("--repo", required=True)
    board_move_p.add_argument("--number", required=True, type=int)
    board_move_p.add_argument("--status", required=True,
                              help="Target status (e.g. 'In Development', 'E2E Testing')")

    board_archive_p = board_sp.add_parser("archive", help="Archive deployed items")
    board_archive_p.add_argument("--project", required=True, choices=["mount-olympus"])
    board_archive_p.add_argument("--dry-run", action="store_true")

    board_wip_p = board_sp.add_parser("wip", help="Show WIP counts and limits")
    board_wip_p.add_argument("--project", required=True, choices=["mount-olympus"])

    board_standup_p = board_sp.add_parser("standup", help="Standup prep — right-to-left board review")
    board_standup_p.add_argument("--project", required=True, choices=["mount-olympus"])

    board_fields_p = board_sp.add_parser("discover-fields", help="Discover all project fields and options")
    board_fields_p.add_argument("--project", required=True, choices=["mount-olympus"])

    # ===========================
    # ISSUE
    # ===========================
    issue_p = subparsers.add_parser("issue", help="Issue creation and management")
    issue_sp = issue_p.add_subparsers(dest="action", required=True)

    issue_create_p = issue_sp.add_parser("create", help="Create issue with template")
    issue_create_p.add_argument("--repo", required=True)
    issue_create_p.add_argument("--type",
                                choices=["capability", "enhancement", "defect",
                                         "exploration", "context-update", "objective"],
                                help="Issue type (uses template)")

    # ===========================
    # LABELS
    # ===========================
    labels_p = subparsers.add_parser("labels", help="Label management")
    labels_sp = labels_p.add_subparsers(dest="action", required=True)

    labels_sync_p = labels_sp.add_parser("sync-fields", help="Sync initiative/objective labels to project fields")
    labels_sync_p.add_argument("--repo", required=True)
    labels_sync_p.add_argument("--number", required=True, type=int)

    labels_audit_p = labels_sp.add_parser("audit", help="Check repo has all SDLC labels")
    labels_audit_p.add_argument("--repo", required=True)

    labels_deploy_p = labels_sp.add_parser("deploy", help="Create/update all labels in repo")
    labels_deploy_p.add_argument("--repo", required=True)

    labels_auto_p = labels_sp.add_parser("auto-label", help="Apply auto-label rules to issue")
    labels_auto_p.add_argument("--repo", required=True)
    labels_auto_p.add_argument("--number", required=True, type=int)

    # ===========================
    # FIELDS
    # ===========================
    fields_p = subparsers.add_parser("fields", help="Project field management")
    fields_sp = fields_p.add_subparsers(dest="action", required=True)

    fields_create_p = fields_sp.add_parser("create-option", help="Create new single-select option")
    fields_create_p.add_argument("--project", required=True, choices=["mount-olympus"])
    fields_create_p.add_argument("--field", required=True, help="Field name (e.g. initiative, objective)")
    fields_create_p.add_argument("--option", required=True, help="New option name")

    fields_discover_p = fields_sp.add_parser("discover", help="Discover all fields and options")
    fields_discover_p.add_argument("--project", required=True, choices=["mount-olympus"])

    # ===========================
    # METRICS
    # ===========================
    metrics_p = subparsers.add_parser("metrics", help="Flow metrics and analysis")
    metrics_sp = metrics_p.add_subparsers(dest="action", required=True)

    metrics_ct_p = metrics_sp.add_parser("cycle-time", help="Cycle time percentiles")
    metrics_ct_p.add_argument("--project", required=True, choices=["mount-olympus"])
    metrics_ct_p.add_argument("--days", type=int, default=30)
    metrics_ct_p.add_argument("--type", choices=["capability", "enhancement", "defect", "exploration"])

    metrics_th_p = metrics_sp.add_parser("throughput", help="Items deployed per week")
    metrics_th_p.add_argument("--project", required=True, choices=["mount-olympus"])
    metrics_th_p.add_argument("--weeks", type=int, default=4)

    metrics_age_p = metrics_sp.add_parser("wip-age", help="Age of in-progress items")
    metrics_age_p.add_argument("--project", required=True, choices=["mount-olympus"])

    metrics_col_p = metrics_sp.add_parser("column-time", help="Time in each column for a specific item")
    metrics_col_p.add_argument("--project", required=True, choices=["mount-olympus"])
    metrics_col_p.add_argument("--number", required=True, type=int)

    # ===========================
    # MILESTONES
    # ===========================
    ms_p = subparsers.add_parser("milestones", help="Milestone management for Objectives")
    ms_sp = ms_p.add_subparsers(dest="action", required=True)

    ms_create_p = ms_sp.add_parser("create", help="Create milestone for Objective")
    ms_create_p.add_argument("--repo", required=True)
    ms_create_p.add_argument("--title", required=True, help="Milestone title (e.g. 'Pilot: Auth MVP')")
    ms_create_p.add_argument("--due-date", required=True, help="Due date (YYYY-MM-DD)")
    ms_create_p.add_argument("--description", default="", help="Milestone description")

    ms_list_p = ms_sp.add_parser("list", help="List milestones")
    ms_list_p.add_argument("--repo", required=True)
    ms_list_p.add_argument("--state", choices=["open", "closed", "all"], default="open")

    ms_progress_p = ms_sp.add_parser("progress", help="Show milestone completion %")
    ms_progress_p.add_argument("--repo", required=True)
    ms_progress_p.add_argument("--milestone", required=True, type=int, help="Milestone number")

    ms_link_p = ms_sp.add_parser("link", help="Link issue to milestone")
    ms_link_p.add_argument("--repo", required=True)
    ms_link_p.add_argument("--issue", required=True, type=int)
    ms_link_p.add_argument("--milestone", required=True, type=int)

    # ===========================
    # ROLLOUT
    # ===========================
    rollout_p = subparsers.add_parser("rollout", help="Rollout tracking and deployment")
    rollout_sp = rollout_p.add_subparsers(dest="action", required=True)

    rollout_status_p = rollout_sp.add_parser("status", help="Show rollout status")
    rollout_status_p.add_argument("--team", help="Filter by team")

    rollout_gap_p = rollout_sp.add_parser("gap-analysis", help="Check what's missing from a repo")
    rollout_gap_p.add_argument("--repo", required=True)

    rollout_labels_p = rollout_sp.add_parser("deploy-labels", help="Deploy all SDLC labels to repo")
    rollout_labels_p.add_argument("--repo", required=True)

    rollout_templates_p = rollout_sp.add_parser("deploy-templates", help="Deploy all SDLC templates to repo")
    rollout_templates_p.add_argument("--repo", required=True)

    rollout_all_p = rollout_sp.add_parser("deploy-all", help="Full SDLC deployment to repo")
    rollout_all_p.add_argument("--repo", required=True)

    rollout_update_p = rollout_sp.add_parser("update", help="Update beads-config.json")
    rollout_update_p.add_argument("--repo", required=True)
    rollout_update_p.add_argument("--field", required=True,
                                   choices=["labels", "templates", "claude_md", "project"])
    rollout_update_p.add_argument("--status", required=True,
                                   choices=["pending", "in-progress", "complete"])

    # ===========================
    # FLOW (Phase C — operator-facing GraphQL/REST surface)
    # ===========================
    flow_p = subparsers.add_parser("flow", help="Operator-facing GraphQL + REST helpers")
    flow_sp = flow_p.add_subparsers(dest="action", required=True)

    flow_setfield_p = flow_sp.add_parser(
        "set-field",
        help="Set a single-select project field on a card",
    )
    flow_setfield_p.add_argument("--project", required=True, help="Project name (e.g., mount-olympus)")
    flow_setfield_p.add_argument("--repo", required=True)
    flow_setfield_p.add_argument("--number", required=True, type=int)
    flow_setfield_p.add_argument("--field", required=True, help="Field name (e.g., Initiative, Objective, Status)")
    flow_setfield_p.add_argument("--option", required=True, help="Option name (case-insensitive)")

    flow_options_p = flow_sp.add_parser(
        "field-options",
        help="List current options for a project field (live discovery)",
    )
    flow_options_p.add_argument("--project", required=True)
    flow_options_p.add_argument("--field", required=True)

    flow_disc_p = flow_sp.add_parser(
        "discover-project",
        help="Resolve which project(s) a repo is mapped to",
    )
    flow_disc_p.add_argument("--repo", required=True)

    flow_link_p = flow_sp.add_parser(
        "link-sub-issue",
        help="Link child as native sub-issue of parent (cross-repo supported, idempotent)",
    )
    flow_link_p.add_argument("--parent-repo", required=True)
    flow_link_p.add_argument("--parent-number", required=True, type=int)
    flow_link_p.add_argument("--child-repo", required=True)
    flow_link_p.add_argument("--child-number", required=True, type=int)

    flow_label_p = flow_sp.add_parser(
        "verify-label",
        help="Self-healing label create (404 → create; exists → no-op; other errors raise)",
    )
    flow_label_p.add_argument("--repo", required=True)
    flow_label_p.add_argument("--name", required=True)
    flow_label_p.add_argument("--color", default=None, help="Hex color without leading '#'")
    flow_label_p.add_argument("--description", default=None)

    flow_validate_p = flow_sp.add_parser(
        "validate-card",
        help="Run card_validator schema check on an existing issue body",
    )
    flow_validate_p.add_argument("--repo", required=True)
    flow_validate_p.add_argument("--number", required=True, type=int)

    # ===========================
    # CONFIG
    # ===========================
    config_p = subparsers.add_parser("config", help="Configuration operations")
    config_sp = config_p.add_subparsers(dest="action", required=True)
    config_sp.add_parser("show", help="Show loaded configuration")

    # ===========================
    # PARSE AND ROUTE
    # ===========================
    args = parser.parse_args()
    fmt = args.format

    try:
        if args.resource == "board":
            if args.action == "view":
                board_view(args.project, args.status, fmt)
            elif args.action == "add":
                board_add(args.repo, args.number, fmt)
            elif args.action == "move":
                board_move(args.repo, args.number, args.status, fmt)
            elif args.action == "archive":
                board_archive(args.project, args.dry_run, fmt)
            elif args.action == "wip":
                board_wip(args.project, fmt)
            elif args.action == "standup":
                board_standup(args.project, fmt)
            elif args.action == "discover-fields":
                board_discover_fields(args.project, fmt)

        elif args.resource == "issue":
            if args.action == "create":
                issue_create(args.repo, args.type, fmt)

        elif args.resource == "labels":
            if args.action == "sync-fields":
                labels_sync_fields(args.repo, args.number, fmt)
            elif args.action == "audit":
                labels_audit(args.repo, fmt)
            elif args.action == "deploy":
                labels_deploy(args.repo, fmt)
            elif args.action == "auto-label":
                labels_auto_label(args.repo, args.number, fmt)

        elif args.resource == "fields":
            if args.action == "create-option":
                fields_create_option(args.project, args.field, args.option, fmt)
            elif args.action == "discover":
                fields_discover(args.project, fmt)

        elif args.resource == "metrics":
            if args.action == "cycle-time":
                metrics_cycle_time(args.project, args.days, args.type, fmt)
            elif args.action == "throughput":
                metrics_throughput(args.project, args.weeks, fmt)
            elif args.action == "wip-age":
                metrics_wip_age(args.project, fmt)
            elif args.action == "column-time":
                metrics_column_time(args.project, args.number, fmt)

        elif args.resource == "milestones":
            if args.action == "create":
                milestones_create(args.repo, args.title, args.due_date, args.description, fmt)
            elif args.action == "list":
                milestones_list(args.repo, args.state, fmt)
            elif args.action == "progress":
                milestones_progress(args.repo, args.milestone, fmt)
            elif args.action == "link":
                milestones_link(args.repo, args.issue, args.milestone, fmt)

        elif args.resource == "rollout":
            if args.action == "status":
                rollout_status(args.team, fmt)
            elif args.action == "gap-analysis":
                rollout_gap_analysis(args.repo, fmt)
            elif args.action == "deploy-labels":
                rollout_deploy_labels(args.repo, fmt)
            elif args.action == "deploy-templates":
                rollout_deploy_templates(args.repo, fmt)
            elif args.action == "deploy-all":
                rollout_deploy_all(args.repo, fmt)
            elif args.action == "update":
                rollout_update(args.repo, args.field, args.status, fmt)

        elif args.resource == "flow":
            if args.action == "set-field":
                flow_set_field(args.project, args.repo, args.number,
                               args.field, args.option, fmt)
            elif args.action == "field-options":
                flow_field_options(args.project, args.field, fmt)
            elif args.action == "discover-project":
                flow_discover_project(args.repo, fmt)
            elif args.action == "link-sub-issue":
                flow_link_sub_issue(args.parent_repo, args.parent_number,
                                    args.child_repo, args.child_number, fmt)
            elif args.action == "verify-label":
                flow_verify_label(args.repo, args.name, args.color,
                                  args.description, fmt)
            elif args.action == "validate-card":
                flow_validate_card(args.repo, args.number, fmt)

        elif args.resource == "config":
            if args.action == "show":
                config_show(fmt)

    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        _error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
