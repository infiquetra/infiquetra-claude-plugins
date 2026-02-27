# Infiquetra PagerDuty Plugin

Comprehensive PagerDuty integration for incident management, service configuration, team orchestration, and on-call automation through Claude Code.

## Features

### 🚨 Incident Management
- Query incidents with flexible filters (status, urgency, service, user)
- Acknowledge, resolve, and reassign incidents
- Add notes and context to incidents
- Natural language incident search
- Incident correlation with deployment timing

### 🔧 Service Management
- Full CRUD operations for services
- Service dependency mapping
- Integration configuration
- Service health monitoring

### 👥 Team & On-Call Management
- Team creation and member management
- Escalation policy configuration with audit trail
- On-call schedule management
- User lookup and permissions

### 🤖 Intelligent Agent
- **pagerduty-ops**: Incident investigation with blast radius analysis
  - Traces service → team → on-call → dependent services
  - Correlates incidents across services
  - Provides intelligent triage suggestions

## Installation

### Prerequisites

- Python 3.12+
- PagerDuty API key with appropriate permissions
- Infiquetra team access (optional, for defaults)

### Setup

1. **Obtain PagerDuty API Key**:
   - Log in to PagerDuty
   - Navigate to **Integrations** → **API Access Keys**
   - Create a new API key with required scopes:
     - `incidents.read`, `incidents.write`
     - `services.read`, `services.write`
     - `users.read`
     - `teams.read`, `teams.write`
     - `escalation_policies.read`, `escalation_policies.write`
     - `schedules.read`

2. **Configure Environment**:
   ```bash
   export PAGERDUTY_API_KEY="your-api-key-here"
   ```

3. **Install Plugin**:
   ```bash
   # Copy to Claude Code plugins directory
   cp -r plugins/pagerduty ~/.claude/plugins/

   # Or symlink for development
   ln -s $(pwd)/plugins/pagerduty ~/.claude/plugins/pagerduty
   ```

4. **Restart Claude Code** to load the plugin

## Usage

### Skills

#### pagerduty-incidents
Manage incidents with natural language queries:

```
List high-urgency triggered incidents for our team
Show me incidents from the last 2 hours
Acknowledge incident PXXXXX and add note "Investigating database slowdown"
Resolve incident PXXXXX
```

#### pagerduty-services
Manage services and integrations:

```
List all services for team Infiquetra
Show service details for wallet-service
Create a new service called "identity-verification"
Update service PXXXXX to add integration
```

#### pagerduty-teams
Manage teams, escalation policies, and on-call schedules:

```
Show all teams
List escalation policies for team YOUR_TEAM_ID
Who is on-call for wallet-service right now?
Create escalation policy with 5-minute escalation
```

### Commands

#### /pagerduty
Quick access to common PagerDuty operations:

```
/pagerduty incidents           # List recent incidents
/pagerduty services           # List team services
/pagerduty oncall             # Show current on-call engineers
```

### Agent

#### pagerduty-ops
Incident investigation and blast radius analysis:

```
Investigate incident PXXXXX - what's the blast radius?
Analyze the correlation between recent wallet-service incidents
Help me triage this production outage
```

## Configuration

### Infiquetra Defaults

The plugin includes Infiquetra-specific defaults:
- **Team ID**: `YOUR_TEAM_ID` (Infiquetra/infiquetra team)
- **Escalation Policy**: `YOUR_POLICY_ID` (Infiquetra production escalation)

Override these by specifying different IDs in your queries.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PAGERDUTY_API_KEY` | Yes | PagerDuty API access token |

## Infiquetra Integration

This plugin integrates with other Infiquetra tools:

- **sled**: Link services to SLED components for dependency mapping
- **splunk**: Correlate incidents with Splunk logs
- **slack**: Send incident notifications to team channels
- **rally**: Link incidents to Rally defects for tracking

## API Reference

The plugin uses PagerDuty REST API v2:
- Base URL: `https://api.pagerduty.com`
- Authentication: Token-based (Authorization header)
- Rate limits: 60,000 requests/hour (per API key)

See [PagerDuty API Documentation](https://developer.pagerduty.com/api-reference/) for detailed API reference.

## Examples

### Incident Workflows

**Morning incident review**:
```
Show me all incidents from the last 24 hours
What's the current P1 incident status?
List unacknowledged incidents
```

**Incident investigation**:
```
Use pagerduty-ops agent to investigate incident PXXXXX
What services are affected by this incident?
Show me the escalation history
```

**Incident resolution**:
```
Acknowledge incident PXXXXX
Add note "Fixed by deploying hotfix v1.2.3"
Resolve incident PXXXXX
```

### Service Management

**Service configuration**:
```
Create service "vehicle-checkout" with email integration
Update service PXXXXX to use escalation policy YOUR_POLICY_ID
List integrations for wallet-service
```

### Team Operations

**On-call management**:
```
Who is on-call for the wallet team right now?
List all on-call schedules
Show escalation policy audit log
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify `PAGERDUTY_API_KEY` is set correctly
   - Check API key has required scopes
   - Ensure API key hasn't expired

2. **Team/Service Not Found**:
   - Verify team ID or service ID is correct
   - Check you have access permissions

3. **Rate Limiting**:
   - The plugin handles rate limits automatically with exponential backoff
   - Reduce query frequency if hitting limits consistently

## Development

### Testing

```bash
# Run tests
uv run pytest tests/test_pagerduty_client.py -v

# Run with coverage
uv run pytest tests/test_pagerduty_client.py --cov=plugins/pagerduty --cov-report=term-missing
```

### Scripts

The plugin uses a single shared script:
- `skills/pagerduty-incidents/scripts/pagerduty_client.py` - PagerDuty API client (~900 lines)

All three skills reference this script for their operations.

## Support

- **Slack**: 
- **Documentation**: [Infiquetra Documentation](https://docs.example.com)
- **Issues**: [GitHub Issues](https://github.com/infiquetra/infiquetra-claude-plugins/issues)

## License

Internal use only - your organization/Infiquetra Team
