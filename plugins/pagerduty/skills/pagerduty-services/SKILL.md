---
name: pagerduty-services
description: Full CRUD operations for PagerDuty services, integrations, and configuration
when_to_use: |
  Use this skill when the user wants to:
  - List or search for services
  - View service details and configuration
  - Create new services
  - Update service settings (name, description, escalation policy)
  - Delete services
  - Configure service integrations
  - Map services to teams
---

# PagerDuty Service Management

You are helping the user manage PagerDuty services and integrations through natural language interactions.

## Prerequisites

Verify the `PAGERDUTY_API_KEY` environment variable is set:
```bash
echo $PAGERDUTY_API_KEY
```

## Core Operations

### List Services

```bash
# List all services for Infiquetra team (defaults to YOUR_TEAM_ID)
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services list

# List services for a specific team
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services list --team-id PXXXXX

# Search services by name
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services list --query "wallet"
```

**Filters**:
- `--team-id`: Filter by team ID (defaults to Infiquetra team YOUR_TEAM_ID)
- `--query`: Search by service name or description

### Get Service Details

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services get --id PXXXXX
```

Returns complete service information:
- Service name and description
- Status (active, disabled, warning, critical)
- Escalation policy configuration
- Integrations (email, API, monitoring tools)
- Teams assigned
- Alert grouping settings
- Auto-resolution configuration

### Create Service

```bash
# Basic service creation (uses Infiquetra default escalation policy YOUR_POLICY_ID)
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services create \
  --name "vehicle-checkout-service" \
  --description "Vehicle checkout and handoff service"

# With custom escalation policy
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services create \
  --name "identity-verification-service" \
  --description "Identity verification and KYC service" \
  --escalation-policy-id PYYYYY
```

**Parameters**:
- `--name`: Service name (required)
- `--description`: Service description (optional)
- `--escalation-policy-id`: Escalation policy (defaults to Infiquetra policy YOUR_POLICY_ID)

### Update Service

```bash
# Update service name
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services update \
  --id PXXXXX \
  --name "wallet-service"

# Update description
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services update \
  --id PXXXXX \
  --description "Digital wallet and payment service for vehicle custody"

# Change escalation policy
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services update \
  --id PXXXXX \
  --escalation-policy-id PYYYYY
```

### Delete Service

⚠️ **Warning**: Deleting a service removes all associated incidents and integrations.

```bash
python plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py services delete --id PXXXXX
```

**Always confirm with user before deleting** and consider:
1. Are there open incidents? (list first)
2. Are integrations configured? (may need manual cleanup)
3. Is this a production service? (double-check!)

## Natural Language Examples

### Service Discovery

**User**: "Show me all Infiquetra services"

**Response**:
1. List services for Infiquetra team (YOUR_TEAM_ID)
2. Group by status (active, critical, warning)
3. Summarize incident counts per service
4. Highlight services with recent incidents

**User**: "Find services related to wallet"

**Response**:
1. Search services with `--query "wallet"`
2. Show matching services with descriptions
3. Display escalation policies
4. Show recent incident history

### Service Configuration

**User**: "Create a new service for the identity verification feature"

**Response**:
1. Ask for service name (suggest: "identity-verification-service")
2. Ask for description
3. Confirm escalation policy (use Infiquetra default YOUR_POLICY_ID or custom?)
4. Create service
5. Provide next steps:
   - Configure integrations (email, API endpoint)
   - Set up monitoring tool integration
   - Test alert flow

**User**: "Update wallet-service to use the new on-call policy"

**Response**:
1. Find wallet-service by name (list with --query)
2. Ask for new escalation policy ID
3. Update service
4. Confirm change
5. Verify with service get to show new configuration

### Service Audit

**User**: "Show me which services are using the old escalation policy"

**Response**:
1. List all Infiquetra services
2. Filter by escalation_policy_id in results
3. Group services by policy
4. Highlight services using old/deprecated policies
5. Offer to bulk update to new policy

## Service Integration Patterns

### CloudWatch Integration

After creating a service, guide integration setup:

```
Service created: identity-verification-service (PXXXXX)

Next steps for CloudWatch integration:
1. Get service integration key from PagerDuty
2. Configure CloudWatch alarm action:
   - SNS topic → PagerDuty endpoint
   - Integration key in URL
3. Test with sample alarm
4. Verify incident creation
```

### API Integration

For custom monitoring tools:

```
Service created: wallet-service (PXXXXX)

API integration setup:
1. Create integration: Services → wallet-service → Integrations → Add
2. Select "Events API v2"
3. Copy integration key
4. Add to Lambda Powertools configuration:
   POWERTOOLS_SERVICE_NAME: wallet-service
   PAGERDUTY_INTEGRATION_KEY: <integration-key>
5. Test with: aws lambda invoke --function-name <name> --payload '{}'
```

### Email Integration

For email-based alerts:

```
Service created: checkout-service (PXXXXX)

Email integration (auto-generated):
1. Service email: checkout-service@example.pagerduty.com
2. Add to monitoring tool alert destinations
3. Test: Send email with subject containing "CRITICAL" or "WARNING"
4. Verify incident creation
```

## LLM Value-Add Features

### Service Dependency Mapping

When viewing services, correlate with SLED components:

```
Found 5 Infiquetra services:
- wallet-service (PXXXXX) → SLED component CI2408590
- identity-service (PYYYYY) → SLED component CI2408591
- checkout-service (PZZZZZ) → SLED component CI2408592

Dependencies:
- checkout-service depends on wallet-service and identity-service
- Incidents in wallet-service may affect checkout-service
```

### Service Health Dashboard

Summarize service health:

```json
{
  "team": "Infiquetra (YOUR_TEAM_ID)",
  "services": {
    "healthy": 3,
    "warning": 1,
    "critical": 1
  },
  "critical_services": [
    {
      "name": "wallet-service",
      "id": "PXXXXX",
      "open_incidents": 2,
      "status": "critical",
      "last_incident": "2026-02-26T14:30:00Z"
    }
  ],
  "recommendations": [
    "Check wallet-service - multiple open incidents",
    "Review identity-service escalation policy - using deprecated policy"
  ]
}
```

### Configuration Audit

Compare service configurations:

```
Escalation Policy Audit:
✓ 3 services using current policy (YOUR_POLICY_ID)
⚠ 2 services using deprecated policy (P0G40L1)
  - legacy-service (PXXXXX)
  - old-api-service (PYYYYY)

Recommendation: Update deprecated services to YOUR_POLICY_ID
```

### Service Naming Conventions

Enforce Infiquetra naming standards:

```
Service name suggestion:
- Current: "Wallet API"
- Recommended: "wallet-service"
- Reason: Follows Infiquetra kebab-case convention, includes '' prefix

Update service name? (y/n)
```

## Service Lifecycle Management

### New Service Checklist

When creating a service, provide a complete checklist:

```
✓ Service created: checkout-service (PXXXXX)

Setup checklist:
[ ] Configure CloudWatch integration
[ ] Set up API integration key in Lambda
[ ] Add service to SLED component registry
[ ] Document service in Dev Hub
[ ] Test incident creation flow
[ ] Add service to team runbook
[ ] Configure auto-resolution rules
[ ] Set up alert grouping
```

### Service Deprecation

When deleting a service, ensure safe deprecation:

```
Service deletion safety check for wallet-service (PXXXXX):
⚠ Open incidents: 2 (resolve first!)
⚠ Active integrations: 3 (cleanup required)
✓ No recent incidents (30 days)

Recommended steps:
1. Resolve/reassign open incidents
2. Disable integrations
3. Remove from monitoring tools
4. Update documentation
5. Archive in SLED
6. Delete service

Proceed? (y/n)
```

## Integration with Other Tools

### SLED Component Linking

After creating a service:

```
Service created: wallet-service (PXXXXX)

Would you like to:
1. Link to existing SLED component
2. Create new SLED component
3. Skip (link later)

Recommended: Link to CI2408590 (wallet-service)
```

### Rally Story Tracking

For feature-related services:

```
Service created for new feature: vehicle-handoff-service

Would you like to:
1. Link to Rally story/epic
2. Create implementation checklist in Rally
3. Add service details to PRR documentation
```

## Error Handling

### Common Errors

1. **Duplicate Service Name**:
   ```json
   {
     "error": true,
     "message": "Service with name 'wallet-service' already exists",
     "status_code": 400
   }
   ```
   **Solution**: Use a unique name or update existing service

2. **Invalid Escalation Policy**:
   ```json
   {
     "error": true,
     "message": "Escalation policy PXXXXX not found",
     "status_code": 404
   }
   ```
   **Solution**: List escalation policies to find valid ID

3. **Service Not Found**:
   ```json
   {
     "error": true,
     "message": "API error: 404",
     "status_code": 404
   }
   ```
   **Solution**: Verify service ID with services list

## Best Practices

### Service Naming

- Use lowercase with hyphens: `wallet-service`
- Include `` prefix for team services
- Be descriptive: `vehicle-checkout` not `checkout`
- Match repository names for traceability

### Service Organization

- One service per microservice/component
- Group related services with shared escalation policy
- Use clear descriptions (include tech stack, purpose)
- Keep service count manageable (combine minor components)

### Escalation Policy Selection

- Production services: Use YOUR_POLICY_ID (Infiquetra production policy)
- Development/staging: Use dev-specific policy
- Critical services: Consider dedicated policy with faster escalation
- Shared services: Use team-specific policy

## Output Format

All commands return JSON:

```json
{
  "success": true,
  "data": {...},
  "message": "Optional success message"
}
```

## Reference Documentation

See `references/` directory for:
- `pagerduty-api.md`: Complete PagerDuty API v2 reference
- `service-configuration.md`: Service setup and integration guides
- `services.md`: Infiquetra service catalog and policies
