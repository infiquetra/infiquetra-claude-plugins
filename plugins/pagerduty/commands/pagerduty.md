---
name: pagerduty
description: Quick access to common PagerDuty operations
usage: |
  /pagerduty [subcommand]

  Subcommands:
    incidents    - List recent incidents
    services     - List team services
    oncall       - Show current on-call engineers
    help         - Show this help message
---

# /pagerduty Command

Quick access to common PagerDuty operations for Infiquetra team incident management.

## Usage

```
/pagerduty [subcommand]
```

## Subcommands

### incidents

List recent incidents for the Infiquetra team.

**Usage**:
```
/pagerduty incidents
/pagerduty incidents triggered
/pagerduty incidents high-urgency
```

**Default behavior**:
- Lists last 24 hours of incidents
- Filters to Infiquetra team (YOUR_TEAM_ID)
- Groups by status (triggered, acknowledged, resolved)
- Highlights high-urgency incidents

**Output**:
```
Infiquetra Incidents (Last 24 hours):

Triggered (2):
  • PXXXXX - wallet-service - Database timeout [HIGH]
    Triggered: 2026-02-26 14:32 (5 min ago)

  • PYYYYY - checkout-service - High error rate [LOW]
    Triggered: 2026-02-26 12:15 (2 hours ago)

Acknowledged (1):
  • PZZZZZ - identity-service - API latency [HIGH]
    Acknowledged by: Jeff Cox
    Acknowledged: 2026-02-26 10:00 (4 hours ago)

Resolved Today (3):
  [Summary of resolved incidents]

Actions:
  • Type "investigate PXXXXX" to analyze incident
  • Type "acknowledge PXXXXX" to acknowledge
```

### services

List all services for the Infiquetra team.

**Usage**:
```
/pagerduty services
/pagerduty services wallet
```

**Default behavior**:
- Lists all Infiquetra team services
- Shows service status (healthy, warning, critical)
- Displays escalation policy
- Shows recent incident count

**Output**:
```
Infiquetra Services:

Critical (1):
  • wallet-service (PXXXXX)
    Status: Critical
    Policy: Infiquetra Production (YOUR_POLICY_ID)
    Open incidents: 2
    Last incident: 5 min ago

Healthy (7):
  • checkout-service (PYYYYY)
  • identity-service (PZZZZZ)
  • vehicle-handoff-service (PAAAAA)
  [... more services]

Actions:
  • Type "show service PXXXXX" for details
  • Type "create service" to add new service
```

### oncall

Show who is currently on-call for Infiquetra services.

**Usage**:
```
/pagerduty oncall
/pagerduty oncall next-week
```

**Default behavior**:
- Shows current on-call rotation
- Groups by escalation level (L1, L2, L3)
- Displays contact information
- Shows when rotation changes

**Output**:
```
Infiquetra On-Call (Current):

Level 1 (Primary):
  Jeff Cox
  📱 +1-555-0100
  ✉️  jeff.user@example.com
  Next rotation: Saturday 9:00 AM

Level 2 (Secondary):
  Sarah Smith
  📱 +1-555-0101
  ✉️  sarah.user@example.com
  Next rotation: Saturday 9:00 AM

Level 3 (Manager):
  Mike Johnson (Engineering Manager)
  📱 +1-555-0102
  ✉️  mike.user@example.com

Next Week On-Call:
  L1: Sarah Smith (starting Saturday 9:00 AM)
  L2: Mike Davis (starting Saturday 9:00 AM)

Actions:
  • Type "I'm on-call - what should I focus on?" for triage help
```

### help

Show available subcommands and usage examples.

**Usage**:
```
/pagerduty help
/pagerduty
```

## Examples

### Morning standup - check incident status

```
/pagerduty incidents
```

Shows all incidents from last 24 hours, grouped by status. Quick overview of what happened overnight.

### Service health check

```
/pagerduty services
```

Shows all Infiquetra services with current health status. Identify critical services needing attention.

### On-call handoff

```
/pagerduty oncall
```

Shows current and next on-call rotation. Use during shift handoffs to verify coverage.

## Integration with Skills

The `/pagerduty` command provides quick access, but for more detailed operations, use the full skills:

- **Detailed incident management**: Use `pagerduty-incidents` skill
  ```
  "Show me high-urgency incidents for wallet-service"
  "Acknowledge incident PXXXXX and add investigation note"
  ```

- **Service configuration**: Use `pagerduty-services` skill
  ```
  "Create a new service called vehicle-inspection"
  "Update wallet-service escalation policy"
  ```

- **Team management**: Use `pagerduty-teams` skill
  ```
  "Add Sarah to Infiquetra team as responder"
  "Show escalation policy details for YOUR_POLICY_ID"
  ```

- **Deep investigation**: Use `pagerduty-ops` agent
  ```
  "Investigate incident PXXXXX - what's the blast radius?"
  "Analyze correlation between recent wallet incidents"
  ```

## Infiquetra Defaults

The command uses these Infiquetra-specific defaults:

- **Team ID**: YOUR_TEAM_ID (Infiquetra/infiquetra)
- **Escalation Policy**: YOUR_POLICY_ID (Infiquetra Production)
- **Time Range**: Last 24 hours (for incidents)
- **Status Filter**: All statuses (triggered, acknowledged, resolved)

Override defaults by using the full skills with specific parameters.

## Quick Reference

| Command | What it does | When to use |
|---------|--------------|-------------|
| `/pagerduty incidents` | List recent incidents | Morning standup, shift start |
| `/pagerduty incidents triggered` | Show only active incidents | Quick triage check |
| `/pagerduty services` | List all services | Service health overview |
| `/pagerduty oncall` | Show on-call rotation | Handoff, coverage check |
| `/pagerduty help` | Show command help | Reference, new users |

## Tips

1. **Use it for quick checks**: The command is optimized for speed
2. **Combine with agents**: Use `/pagerduty` to identify issues, then invoke agents for investigation
3. **Alias it**: Set up shell aliases for common queries
4. **Morning routine**: Run `/pagerduty incidents` every morning to stay informed
5. **Pre-handoff**: Check `/pagerduty oncall` before and after rotation changes

## Environment Setup

Ensure `PAGERDUTY_API_KEY` is set:

```bash
export PAGERDUTY_API_KEY="your-api-key"
```

Add to `~/.bashrc` or `~/.zshrc` for persistence:

```bash
echo 'export PAGERDUTY_API_KEY="your-api-key"' >> ~/.zshrc
source ~/.zshrc
```

## Troubleshooting

### Command not found

```
Error: /pagerduty command not recognized
```

**Solution**: Ensure pagerduty plugin is installed in `~/.claude/plugins/`

### No incidents returned

```
Infiquetra Incidents (Last 24 hours): None
```

**Possible causes**:
- No incidents in last 24 hours (good news!)
- Wrong team ID (verify YOUR_TEAM_ID is correct)
- API key lacks team access permissions

### Rate limit errors

```
Error: Rate limit exceeded. Retry after 60 seconds
```

**Solution**: Wait 60 seconds before retrying. PagerDuty has rate limits of 60,000 requests/hour.

## Related Commands

- `/splunk`: Search Splunk logs for incident correlation
- `/slack`: Post incident updates to team channel
- `/rally`: Create defects for incident follow-up
- `/sled`: Check service dependencies and components

## Support

- **Slack**: 
- **Documentation**: See plugin README and skill documentation
- **API Reference**: https://developer.pagerduty.com/api-reference/
