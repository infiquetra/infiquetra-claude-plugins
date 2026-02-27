# PagerDuty REST API v2 Reference

Complete reference for PagerDuty REST API v2 used by the pagerduty plugin.

## API Basics

- **Base URL**: `https://api.pagerduty.com`
- **API Version**: v2 (current)
- **Authentication**: Token-based (Authorization header)
- **Rate Limits**: 60,000 requests/hour per API token
- **Response Format**: JSON

### Authentication

All requests require authentication via token:

```http
GET /incidents HTTP/1.1
Host: api.pagerduty.com
Authorization: Token token=YOUR_API_TOKEN
Accept: application/vnd.pagerduty+json;version=2
Content-Type: application/json
```

## Core Resources

### Incidents

**List Incidents**:
```
GET /incidents
```

Query parameters:
- `statuses[]`: Filter by status (triggered, acknowledged, resolved)
- `urgencies[]`: Filter by urgency (high, low)
- `service_ids[]`: Filter by service ID
- `team_ids[]`: Filter by team ID
- `user_ids[]`: Filter by assigned user ID
- `since`: Start date/time (ISO 8601)
- `until`: End date/time (ISO 8601)
- `sort_by`: Sort field and direction (e.g., created_at:desc)
- `offset`: Pagination offset
- `limit`: Results per page (max 100)

Response format:
```json
{
  "incidents": [
    {
      "id": "PXXXXX",
      "incident_number": 1234,
      "title": "Database connection timeout",
      "status": "triggered",
      "urgency": "high",
      "created_at": "2026-02-26T14:32:00Z",
      "service": {
        "id": "PXXXXX",
        "type": "service_reference",
        "summary": "wallet-service"
      },
      "assignments": [
        {
          "at": "2026-02-26T14:32:00Z",
          "assignee": {
            "id": "PXXXXX",
            "type": "user_reference",
            "summary": "Jeff Cox"
          }
        }
      ],
      "escalation_policy": {
        "id": "YOUR_POLICY_ID",
        "type": "escalation_policy_reference",
        "summary": "Infiquetra Production"
      }
    }
  ],
  "limit": 25,
  "offset": 0,
  "more": false,
  "total": 1
}
```

**Get Incident**:
```
GET /incidents/:id
```

**Update Incident (Acknowledge/Resolve)**:
```
PUT /incidents/:id
```

Request body:
```json
{
  "incident": {
    "type": "incident_reference",
    "status": "acknowledged"  // or "resolved"
  }
}
```

**Add Note to Incident**:
```
POST /incidents/:id/notes
```

Request body:
```json
{
  "note": {
    "content": "Investigating database connection timeout"
  }
}
```

### Services

**List Services**:
```
GET /services
```

Query parameters:
- `team_ids[]`: Filter by team ID
- `query`: Search query
- `offset`: Pagination offset
- `limit`: Results per page (max 100)

Response format:
```json
{
  "services": [
    {
      "id": "PXXXXX",
      "name": "wallet-service",
      "description": "Digital wallet and payment service",
      "status": "active",
      "escalation_policy": {
        "id": "YOUR_POLICY_ID",
        "type": "escalation_policy_reference",
        "summary": "Infiquetra Production"
      },
      "teams": [
        {
          "id": "YOUR_TEAM_ID",
          "type": "team_reference",
          "summary": "Infiquetra"
        }
      ]
    }
  ],
  "limit": 25,
  "offset": 0,
  "more": false,
  "total": 1
}
```

**Get Service**:
```
GET /services/:id
```

**Create Service**:
```
POST /services
```

Request body:
```json
{
  "service": {
    "type": "service",
    "name": "new-service-name",
    "description": "Service description",
    "escalation_policy": {
      "id": "YOUR_POLICY_ID",
      "type": "escalation_policy_reference"
    }
  }
}
```

**Update Service**:
```
PUT /services/:id
```

**Delete Service**:
```
DELETE /services/:id
```

### Teams

**List Teams**:
```
GET /teams
```

Query parameters:
- `query`: Search query
- `offset`: Pagination offset
- `limit`: Results per page (max 100)

**Get Team**:
```
GET /teams/:id
```

**Create Team**:
```
POST /teams
```

Request body:
```json
{
  "team": {
    "type": "team",
    "name": "Team Name",
    "description": "Team description"
  }
}
```

**Update Team**:
```
PUT /teams/:id
```

**Delete Team**:
```
DELETE /teams/:id
```

**List Team Members**:
```
GET /teams/:id/members
```

**Add Team Member**:
```
PUT /teams/:team_id/users/:user_id
```

Request body:
```json
{
  "user": {
    "id": "PXXXXX",
    "type": "user_reference"
  },
  "role": "manager"  // or "responder", "observer"
}
```

**Remove Team Member**:
```
DELETE /teams/:team_id/users/:user_id
```

### Escalation Policies

**List Escalation Policies**:
```
GET /escalation_policies
```

Query parameters:
- `team_ids[]`: Filter by team ID
- `query`: Search query
- `offset`: Pagination offset
- `limit`: Results per page (max 100)

**Get Escalation Policy**:
```
GET /escalation_policies/:id
```

Response includes escalation rules:
```json
{
  "escalation_policy": {
    "id": "YOUR_POLICY_ID",
    "name": "Infiquetra Production",
    "escalation_rules": [
      {
        "id": "PXXXXX",
        "escalation_delay_in_minutes": 0,
        "targets": [
          {
            "id": "PXXXXX",
            "type": "schedule_reference"
          }
        ]
      },
      {
        "id": "PYYYYY",
        "escalation_delay_in_minutes": 5,
        "targets": [
          {
            "id": "PYYYYY",
            "type": "schedule_reference"
          }
        ]
      }
    ]
  }
}
```

### Schedules

**List Schedules**:
```
GET /schedules
```

**Get Schedule**:
```
GET /schedules/:id
```

### On-Call

**List On-Call Users**:
```
GET /oncalls
```

Query parameters:
- `schedule_ids[]`: Filter by schedule ID
- `escalation_policy_ids[]`: Filter by escalation policy ID
- `user_ids[]`: Filter by user ID
- `since`: Start date/time (ISO 8601)
- `until`: End date/time (ISO 8601)

Response format:
```json
{
  "oncalls": [
    {
      "escalation_policy": {
        "id": "YOUR_POLICY_ID",
        "type": "escalation_policy_reference",
        "summary": "Infiquetra Production"
      },
      "escalation_level": 1,
      "schedule": {
        "id": "PXXXXX",
        "type": "schedule_reference",
        "summary": "Primary On-Call"
      },
      "user": {
        "id": "PXXXXX",
        "type": "user_reference",
        "summary": "Jeff Cox"
      },
      "start": "2026-02-26T09:00:00Z",
      "end": "2026-03-05T09:00:00Z"
    }
  ]
}
```

### Users

**List Users**:
```
GET /users
```

Query parameters:
- `team_ids[]`: Filter by team ID
- `query`: Search query (name, email)
- `offset`: Pagination offset
- `limit`: Results per page (max 100)

**Get User**:
```
GET /users/:id
```

Response includes contact methods:
```json
{
  "user": {
    "id": "PXXXXX",
    "name": "Jeff Cox",
    "email": "jeff.user@example.com",
    "time_zone": "America/New_York",
    "color": "blue",
    "role": "admin",
    "contact_methods": [
      {
        "id": "PXXXXX",
        "type": "phone_contact_method",
        "summary": "+1-555-0100",
        "phone_number": "+15550100",
        "country_code": 1
      },
      {
        "id": "PYYYYY",
        "type": "email_contact_method",
        "summary": "jeff.user@example.com",
        "address": "jeff.user@example.com"
      }
    ]
  }
}
```

## Pagination

All list endpoints support pagination:

```
GET /incidents?offset=0&limit=100
```

Response includes pagination info:
```json
{
  "incidents": [...],
  "limit": 100,
  "offset": 0,
  "more": true,
  "total": 250
}
```

To get next page:
```
GET /incidents?offset=100&limit=100
```

Continue until `more: false`.

## Rate Limiting

Rate limits:
- **60,000 requests per hour** per API token
- Rate limit headers in response:
  - `X-Rate-Limit-Limit`: Total allowed requests
  - `X-Rate-Limit-Remaining`: Remaining requests
  - `X-Rate-Limit-Reset`: Unix timestamp when limit resets

When rate limit exceeded:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "error": {
    "message": "Rate limit exceeded",
    "code": 2002
  }
}
```

**Handling**: Implement exponential backoff and retry after `Retry-After` seconds.

## Error Responses

Common error codes:

**400 Bad Request**:
```json
{
  "error": {
    "message": "Invalid Input Provided",
    "code": 2001,
    "errors": [
      "escalation_policy.id must be a valid escalation policy ID"
    ]
  }
}
```

**401 Unauthorized**:
```json
{
  "error": {
    "message": "Invalid API token",
    "code": 2008
  }
}
```

**403 Forbidden**:
```json
{
  "error": {
    "message": "Insufficient permissions",
    "code": 2004
  }
}
```

**404 Not Found**:
```json
{
  "error": {
    "message": "Incident not found",
    "code": 2003
  }
}
```

**429 Too Many Requests**:
```json
{
  "error": {
    "message": "Rate limit exceeded",
    "code": 2002
  }
}
```

**500 Internal Server Error**:
```json
{
  "error": {
    "message": "Internal Server Error",
    "code": 2000
  }
}
```

## Best Practices

### 1. Use Pagination

Always paginate for large result sets:
```python
def get_all_incidents():
    incidents = []
    offset = 0
    limit = 100

    while True:
        response = get(f"/incidents?offset={offset}&limit={limit}")
        incidents.extend(response["incidents"])

        if not response["more"]:
            break

        offset += limit

    return incidents
```

### 2. Handle Rate Limits

Implement exponential backoff:
```python
import time

def api_request_with_retry(endpoint, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(endpoint)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            continue

        return response

    raise Exception("Max retries exceeded")
```

### 3. Use Filters

Reduce response size and improve performance:
```
# Good: Filtered query
GET /incidents?team_ids[]=YOUR_TEAM_ID&status=triggered

# Bad: Get all and filter client-side
GET /incidents  # Returns everything
```

### 4. Batch Operations

When possible, batch multiple updates:
```json
PUT /incidents
{
  "incidents": [
    {"id": "P1", "type": "incident_reference", "status": "acknowledged"},
    {"id": "P2", "type": "incident_reference", "status": "acknowledged"},
    {"id": "P3", "type": "incident_reference", "status": "acknowledged"}
  ]
}
```

### 5. Cache Service/Team Data

Services and teams change infrequently - cache them:
```python
# Cache for 5 minutes
@cache(ttl=300)
def get_service(service_id):
    return api_get(f"/services/{service_id}")
```

## Additional Resources

- **Official Docs**: https://developer.pagerduty.com/api-reference/
- **API Explorer**: https://developer.pagerduty.com/api-reference/explorer/
- **Webhooks**: https://developer.pagerduty.com/docs/webhooks/
- **Events API**: https://developer.pagerduty.com/docs/events-api-v2/overview/
- **Status Page**: https://status.pagerduty.com/
