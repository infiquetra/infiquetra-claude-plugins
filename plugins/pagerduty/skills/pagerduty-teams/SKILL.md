---
name: pagerduty-teams
description: Manage teams, escalation policies, on-call schedules, and team membership
when_to_use: |
  Use this skill when the user wants to:
  - List or search for teams
  - View team details and members
  - Create or update teams
  - Manage team membership
  - View escalation policies
  - List on-call schedules
  - Find who's currently on-call
  - Manage user access and roles
---

# PagerDuty Teams & On-Call Management

You are helping the user manage PagerDuty teams, escalation policies, on-call schedules, and team membership.

## Prerequisites

Verify the `PAGERDUTY_API_KEY` environment variable is set:
```bash
echo $PAGERDUTY_API_KEY
```

## Core Operations

### Teams

#### List Teams

```bash
# List all teams
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams list

# Search teams by name
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams list --query "vecu"
```

#### Get Team Details

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams get --id YOUR_TEAM_ID
```

Returns:
- Team name and description
- Member count
- Associated services and escalation policies
- Team permissions

#### Create Team

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams create \
  --name "Infiquetra Platform Team" \
  --description "Infiquetra platform engineering and operations"
```

#### Update Team

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams update \
  --id PXXXXX \
  --name "Infiquetra Engineering" \
  --description "Updated description"
```

#### Delete Team

⚠️ **Warning**: Deleting a team may affect services and escalation policies.

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams delete --id PXXXXX
```

### Team Members

#### List Team Members

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams members \
  --team-id YOUR_TEAM_ID \
  --action list
```

Returns list of members with:
- User ID, name, email
- Role (manager, responder, observer)
- Contact methods

#### Add Team Member

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams members \
  --team-id YOUR_TEAM_ID \
  --action add \
  --user-id PXXXXX \
  --role responder
```

**Roles**:
- `manager`: Full team management permissions
- `responder`: Can respond to incidents, view schedules
- `observer`: Read-only access

#### Remove Team Member

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py teams members \
  --team-id YOUR_TEAM_ID \
  --action remove \
  --user-id PXXXXX
```

### Escalation Policies

#### List Escalation Policies

```bash
# List all policies
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py policies list

# Filter by team
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py policies list --team-id YOUR_TEAM_ID

# Search by name
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py policies list --query "production"
```

#### Get Escalation Policy Details

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py policies get --id YOUR_POLICY_ID
```

Returns:
- Policy name and description
- Escalation rules (levels, delays, targets)
- Associated services
- Teams assigned
- Number of incidents using policy

### On-Call Schedules

#### List Schedules

```bash
# List all on-call schedules
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py schedules list

# Search by name
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py schedules list --query "primary"
```

#### Get Schedule Details

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py schedules get --id PXXXXX
```

#### List Current On-Call Users

```bash
# All on-call users
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py oncall

# Filter by schedule
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py oncall --schedule-id PXXXXX

# Filter by escalation policy
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py oncall --escalation-policy-id YOUR_POLICY_ID

# On-call users for a time range
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py oncall \
  --since "2026-02-26T00:00:00Z" \
  --until "2026-02-27T00:00:00Z"
```

### Users

#### List Users

```bash
# List all users
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py users list

# Filter by team
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py users list --team-id YOUR_TEAM_ID

# Search by name/email
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py users list --query "jeff.cox"
```

#### Get User Details

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py users get --id PXXXXX
```

Returns:
- User name, email, timezone
- Contact methods (phone, SMS, email)
- Notification rules
- Teams and roles
- Current on-call status

## Natural Language Examples

### Team Discovery

**User**: "Show me all Infiquetra teams"

**Response**:
1. List teams with `--query "vecu"`
2. Display team names, IDs, member counts
3. Show associated services per team
4. Highlight primary contact/manager

**User**: "Who is on the wallet team?"

**Response**:
1. Find wallet-related team (search by name)
2. List team members with roles
3. Show current on-call rotation
4. Display contact information

### On-Call Queries

**User**: "Who is on-call right now?"

**Response**:
1. List current on-call users (no time filters)
2. Group by escalation policy/schedule
3. Show escalation levels (L1, L2, L3)
4. Display contact methods
5. Show when rotation changes (next shift)

**User**: "Who will be on-call next week?"

**Response**:
1. Calculate next week date range
2. Query on-call with `--since` and `--until`
3. Group by day/shift
4. Highlight rotation changes
5. Identify coverage gaps

**User**: "Am I on-call this weekend?"

**Response**:
1. Ask for user's email/name
2. Search users to get ID
3. Query on-call for user during weekend timeframe
4. Show shifts and escalation levels
5. Provide shift details (Saturday/Sunday times)

### Team Management

**User**: "Add Sarah to the Infiquetra team as a responder"

**Response**:
1. Search users for "Sarah" to get user ID
2. Confirm team ID (YOUR_TEAM_ID)
3. Add member with role=responder
4. Confirm addition
5. Show updated team roster

**User**: "Show me the Infiquetra escalation policy"

**Response**:
1. List policies for team YOUR_TEAM_ID
2. Get details for Infiquetra policy (YOUR_POLICY_ID)
3. Display escalation rules:
   - L1: Primary on-call (immediate)
   - L2: Secondary on-call (after 5 min)
   - L3: Manager escalation (after 15 min)
4. Show which services use this policy

### Escalation Policy Analysis

**User**: "Which services use the production escalation policy?"

**Response**:
1. Get policy details (YOUR_POLICY_ID)
2. Extract associated services from response
3. List services with details
4. Show incident statistics per service

## LLM Value-Add Features

### On-Call Coverage Analysis

```json
{
  "coverage_summary": {
    "current_week": {
      "covered_hours": 168,
      "gaps": 0,
      "rotations": 3
    },
    "next_week": {
      "covered_hours": 168,
      "gaps": 0,
      "rotations": 3
    }
  },
  "coverage_by_level": {
    "L1": "100% (Jeff Cox, Sarah Smith rotation)",
    "L2": "100% (Mike Johnson, Lisa Brown rotation)",
    "L3": "100% (Manager escalation)"
  }
}
```

### Team Health Metrics

```json
{
  "team": "Infiquetra (YOUR_TEAM_ID)",
  "metrics": {
    "members": 12,
    "services": 8,
    "active_incidents": 3,
    "escalation_policies": 2,
    "on_call_schedules": 2
  },
  "on_call_distribution": {
    "balanced": true,
    "avg_shifts_per_person_per_week": 2.5,
    "longest_continuous_shift": "12 hours",
    "shortest_rest_period": "36 hours"
  },
  "recommendations": [
    "On-call distribution is balanced across team",
    "Consider adding backup responder for wallet-service"
  ]
}
```

### Escalation Path Visualization

```
Incident Escalation for wallet-service:

Level 1 (Immediate):
  └─ Primary On-Call: Jeff Cox
     Contact: +1-555-0100, jeff.user@example.com
     Response time: < 5 minutes

Level 2 (After 5 minutes):
  └─ Secondary On-Call: Sarah Smith
     Contact: +1-555-0101, sarah.user@example.com
     Notification: SMS + Email

Level 3 (After 15 minutes):
  └─ Manager Escalation: Mike Johnson
     Contact: +1-555-0102, mike.user@example.com
     Notification: Phone Call + SMS

Current Status: All levels staffed ✓
```

### Smart Team Suggestions

When adding members:

```
Adding user to Infiquetra team...

Suggested role: responder
Reason: User has no manager permissions on other teams

Recommended next steps:
1. Add to primary on-call rotation (every 3rd week)
2. Grant access to  Slack
3. Add to documentation portal documentation
4. Schedule onboarding with team lead
```

## Integration with Other Tools

### Slack Integration

After on-call queries:

```
Current on-call: Jeff Cox (L1), Sarah Smith (L2)

Would you like to:
1. Post on-call schedule to 
2. Send DM to on-call engineer
3. Create on-call handoff thread
```

### SLED Integration

Link teams to SLED organizational structure:

```
Team: Infiquetra (YOUR_TEAM_ID)

SLED Mapping:
- Team ID: 
- Portfolio: I5 - Vehicle Services
- Services: 8 components
- On-call coverage: 24/7

Sync team roster to SLED? (y/n)
```

### Calendar Integration

Export on-call schedules:

```
On-call schedule for next month:

Export options:
1. iCal format (import to Outlook/Google Calendar)
2. CSV (import to spreadsheet)
3. JSON (programmatic access)
4. Send to Slack channel

Would you like to export?
```

## Escalation Policy Best Practices

### Infiquetra Standard Policy (YOUR_POLICY_ID)

The Infiquetra production escalation policy follows this structure:

```
Level 1 - Immediate Response (0 minutes):
  - Target: Primary on-call engineer
  - Notification: SMS + Push + Phone
  - Timeout: 5 minutes

Level 2 - Secondary Response (5 minutes):
  - Target: Secondary on-call engineer
  - Notification: SMS + Phone
  - Timeout: 10 minutes

Level 3 - Manager Escalation (15 minutes):
  - Target: Engineering manager
  - Notification: Phone call
  - Timeout: Incident resolved or manager responds
```

### Policy Audit

Check policy configurations:

```
Escalation Policy Audit for Infiquetra:

✓ Primary policy (YOUR_POLICY_ID):
  - 3 escalation levels
  - All levels staffed
  - Average response time: 2.3 minutes

⚠ Dev policy (P0G40L1):
  - Missing L3 escalation
  - Recommendation: Add manager fallback

✗ Legacy policy (P0G40L0):
  - Deprecated, no active services
  - Recommendation: Delete policy
```

## Error Handling

### Common Errors

1. **User Not Found**:
   ```json
   {
     "error": true,
     "message": "User PXXXXX not found",
     "status_code": 404
   }
   ```
   **Solution**: Search users first to get valid ID

2. **Insufficient Permissions**:
   ```json
   {
     "error": true,
     "message": "Insufficient permissions to modify team",
     "status_code": 403
   }
   ```
   **Solution**: Verify API key has team management permissions

3. **Team Member Already Exists**:
   ```json
   {
     "error": true,
     "message": "User is already a member of this team",
     "status_code": 400
   }
   ```
   **Solution**: Update member role instead of adding

## Best Practices

### Team Organization

- Keep teams aligned with organizational structure
- 5-15 members per team (manageable size)
- Clear team descriptions with responsibilities
- Regular roster reviews (quarterly)

### On-Call Management

- Rotate primary on-call weekly
- Maintain 2-3 escalation levels
- Ensure 24/7 coverage for production services
- Provide adequate rest between shifts (minimum 12 hours)
- Document on-call procedures in runbooks

### Role Assignment

- **Manager**: Team leads, senior engineers
- **Responder**: All engineers handling incidents
- **Observer**: Product managers, stakeholders (read-only)

### Escalation Policy Design

- L1: Primary on-call (immediate)
- L2: Secondary on-call (5-10 min delay)
- L3: Manager/lead (15-30 min delay)
- Timeout between levels: 5-15 minutes
- Final escalation: Always to manager/lead

## Output Format

All commands return JSON:

```json
{
  "success": true,
  "data": {...},
  "count": 5,
  "message": "Optional success message"
}
```

## Reference Documentation

See `references/` directory for:
- `pagerduty-api.md`: Complete PagerDuty API v2 reference
- `escalation-policies.md`: Policy configuration and best practices
- `on-call-management.md`: On-call scheduling and rotation patterns
- `team-structure.md`: Infiquetra team organization and roles
