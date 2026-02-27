---
name: pagerduty-incidents
description: Manage PagerDuty incidents with natural language queries, acknowledgments, resolutions, and notes
when_to_use: |
  Use this skill when the user wants to:
  - List, query, or search for incidents
  - View incident details and history
  - Acknowledge or resolve incidents
  - Add notes or context to incidents
  - Reassign incidents to different users
  - Investigate incident patterns or correlations
  - Perform incident triage
---

# PagerDuty Incident Management

You are helping the user manage PagerDuty incidents through natural language interactions.

## Prerequisites

Verify the `PAGERDUTY_API_KEY` environment variable is set:
```bash
echo $PAGERDUTY_API_KEY
```

If not set, guide the user to obtain their PagerDuty API key from **Integrations → API Access Keys** in PagerDuty.

## Core Operations

### List Incidents

Use natural language to query incidents with various filters:

```bash
# List all triggered incidents (defaults to Infiquetra team YOUR_TEAM_ID)
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents list --status triggered

# High-urgency incidents only
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents list --status triggered --urgency high

# Incidents for a specific service
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents list --service-id PXXXXX

# Incidents from the last 2 hours
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents list --since "2026-02-26T12:00:00Z"

# Incidents assigned to a specific user
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents list --user-id PXXXXX
```

**Common filters**:
- `--status`: `triggered`, `acknowledged`, `resolved`
- `--urgency`: `high`, `low`
- `--service-id`: Filter by specific service
- `--team-id`: Filter by team (defaults to Infiquetra team YOUR_TEAM_ID)
- `--user-id`: Filter by assigned user
- `--since`: Start date/time (ISO 8601 format)
- `--until`: End date/time (ISO 8601 format)

### Get Incident Details

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents get --id PXXXXX
```

Returns complete incident details including:
- Status, urgency, priority
- Service and escalation policy
- Assigned users
- Timeline and acknowledgments
- Alert details

### Acknowledge Incident

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents acknowledge --id PXXXXX

# With user context
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents acknowledge --id PXXXXX --from-email user@example.com
```

### Resolve Incident

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents resolve --id PXXXXX

# With user context
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents resolve --id PXXXXX --from-email user@example.com
```

### Add Note to Incident

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents add-note \
  --id PXXXXX \
  --content "Investigating database connection timeout. Checking CloudWatch logs." \
  --from-email user@example.com
```

### Reassign Incident

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents reassign \
  --id PXXXXX \
  --user-id PYYYYY \
  --from-email user@example.com
```

## Natural Language Examples

### Morning Incident Review

**User**: "Show me all incidents from the last 24 hours"

**Response**:
1. Calculate the time range (now - 24 hours)
2. List incidents with `--since` parameter
3. Summarize by status and urgency
4. Highlight any unacknowledged P1 incidents

### Incident Investigation

**User**: "What's the status of incident PXXXXX?"

**Response**:
1. Get incident details
2. Show current status, assignees, and timeline
3. Display recent notes and alerts
4. If triggered/acknowledged, offer to help investigate

**User**: "Show me all high-urgency incidents for wallet-service"

**Response**:
1. List services to find wallet-service ID
2. List incidents filtered by service and urgency=high
3. Group by status
4. Suggest next actions (acknowledge, investigate)

### Incident Triage

**User**: "Acknowledge incident PXXXXX and add note that I'm investigating"

**Response**:
1. Acknowledge the incident
2. Add note with investigation context
3. Confirm actions taken
4. Offer to help with investigation (logs, metrics)

### Blast Radius Analysis

**User**: "Show me all incidents in the last hour - what services are affected?"

**Response**:
1. List incidents from last hour
2. Extract unique service IDs
3. Get service details for each
4. Map services to teams and dependencies
5. Provide blast radius summary

## Integration with Other Tools

### Splunk Correlation

After listing incidents, offer to correlate with Splunk logs:

```
Found 3 incidents for wallet-service in the last hour. Would you like me to:
1. Check Splunk logs for error patterns
2. Analyze metrics in CloudWatch
3. Review recent deployments
```

### Slack Notifications

After acknowledging/resolving incidents:

```
Incident PXXXXX acknowledged. Would you like me to:
1. Post update to 
2. Notify on-call team
3. Create incident report
```

### Rally Tracking

For production incidents:

```
P1 incident resolved. Would you like me to:
1. Create Rally defect for root cause analysis
2. Link incident to existing story
3. Update sprint retrospective notes
```

## LLM Value-Add Features

### Intelligent Triage

When listing incidents, provide triage suggestions:

```json
{
  "summary": "5 triggered incidents, 3 high-urgency",
  "recommendations": [
    {
      "incident": "PXXXXX",
      "urgency": "high",
      "service": "wallet-service",
      "suggestion": "Acknowledge first - multiple alerts for same service suggest systemic issue",
      "related_incidents": ["PYYYYY", "PZZZZZ"]
    }
  ]
}
```

### Incident Correlation

Detect patterns across incidents:

```
Pattern detected: 3 incidents for wallet-service all triggered within 5 minutes.
Possible causes:
1. Recent deployment (check last 30 minutes)
2. Database connection pool exhaustion
3. Upstream dependency failure (identity-service)
```

### Deployment Correlation

Cross-reference incidents with deployment timing:

```
Incident PXXXXX triggered 2 minutes after wallet-service deployment v1.2.3.
Recommendation: Consider rollback while investigating.
```

### Natural Language Queries

Convert natural language to API queries:

- "Show me yesterday's P1 incidents" → `--since <yesterday-start> --until <yesterday-end> --urgency high`
- "What incidents are unacknowledged?" → `--status triggered`
- "List wallet service incidents from this week" → `--service-id <wallet-id> --since <week-start>`

## Error Handling

### Common Errors

1. **Missing API Key**:
   ```json
   {
     "error": true,
     "message": "PAGERDUTY_API_KEY environment variable not set"
   }
   ```
   **Solution**: Guide user to set API key

2. **Incident Not Found**:
   ```json
   {
     "error": true,
     "message": "API error: 404",
     "status_code": 404
   }
   ```
   **Solution**: Verify incident ID is correct

3. **Rate Limiting**:
   ```json
   {
     "error": true,
     "message": "Rate limit exceeded. Retry after 60 seconds",
     "status_code": 429,
     "retry_after": 60
   }
   ```
   **Solution**: Wait and retry, or reduce query frequency

## Best Practices

### Incident Management Workflow

1. **List & Triage**: Start with high-urgency triggered incidents
2. **Acknowledge**: Let team know you're investigating
3. **Add Notes**: Document investigation steps and findings
4. **Resolve**: Once root cause is fixed
5. **Follow-up**: Create Rally defect for long-term fixes

### Team Communication

- Always add notes when acknowledging incidents
- Include context: what you're checking, initial findings
- Tag relevant team members in notes if needed
- Update notes with resolution details

### Query Optimization

- Use team/service filters to reduce noise
- Set time ranges for historical analysis
- Sort by urgency to prioritize P1 incidents
- Combine filters for targeted queries

## Output Format

All commands return JSON in this format:

```json
{
  "success": true,
  "data": [...],
  "count": 5,
  "message": "Optional success message"
}
```

Parse the `data` field to extract incident information for further analysis.

## Reference Documentation

See `references/` directory for:
- `pagerduty-api.md`: Complete PagerDuty API v2 reference
- `incident-workflows.md`: Common incident management patterns
- `runbooks.md`: Infiquetra-specific incident response procedures
