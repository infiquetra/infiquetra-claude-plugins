# PagerDuty Incident Workflows

Common incident management workflows and best practices for Infiquetra operations.

## Standard Incident Response Workflow

### 1. Detection & Notification

Incident is automatically created when:
- Monitoring alert threshold breached (CloudWatch, Datadog, etc.)
- Email sent to service integration address
- Events API call from application/service

**Result**: Incident assigned to on-call engineer via PagerDuty notification (SMS, phone, push).

### 2. Acknowledgment

On-call engineer acknowledges incident:
```bash
python pagerduty_client.py incidents acknowledge --id PXXXXX
```

**Purpose**:
- Stops escalation timer
- Signals to team: "I'm on it"
- Prevents duplicate investigations

**Timeline**: Should occur within 5 minutes of trigger.

### 3. Investigation

Add notes as you investigate:
```bash
python pagerduty_client.py incidents add-note \
  --id PXXXXX \
  --content "Checking CloudWatch logs - seeing database connection timeouts"
```

**Best practices**:
- Add note every 10-15 minutes
- Document investigation steps
- Include findings (even negative results)
- Set expectations for next update

### 4. Resolution

When root cause fixed:
```bash
python pagerduty_client.py incidents resolve --id PXXXXX
```

**Before resolving, add final note**:
```bash
python pagerduty_client.py incidents add-note \
  --id PXXXXX \
  --content "Root cause: Database connection pool exhausted. Resolution: Increased pool size from 10 to 20 connections. Deployed v1.2.4. Monitoring for 15 minutes - no new errors."
```

### 5. Post-Incident Review

For P1/P2 incidents:
1. Create Rally defect for root cause analysis
2. Schedule postmortem meeting (within 1 week)
3. Update runbooks with learnings
4. Implement preventive measures

## Incident Triage Matrix

| Urgency | Service Type | Response Time | Escalation | Actions |
|---------|--------------|---------------|------------|---------|
| **High** | Customer-facing | < 5 minutes | L1 → L2 (5 min) → L3 (15 min) | Acknowledge immediately, notify team, investigate with urgency |
| **High** | Internal service | < 15 minutes | L1 → L2 (15 min) → L3 (30 min) | Acknowledge, investigate, assess customer impact |
| **Low** | Customer-facing | < 30 minutes | L1 → L2 (30 min) → L3 (1 hour) | Acknowledge, investigate during business hours |
| **Low** | Internal service | < 1 hour | L1 → L2 (1 hour) | Acknowledge, investigate when available |

## Common Incident Types

### Type 1: Service Outage

**Symptoms**:
- Service returning 5xx errors
- Health check failing
- Zero traffic/requests

**Investigation**:
1. Check service health endpoint
2. Review recent deployments (last 30 minutes)
3. Check CloudWatch metrics (CPU, memory, requests)
4. Review application logs for exceptions
5. Verify database connectivity

**Common causes**:
- Bad deployment
- Resource exhaustion (CPU, memory)
- Database connection failure
- Dependency outage

**Resolution**:
- Rollback deployment if recent
- Scale up resources if exhausted
- Restart service if transient issue
- Fix code bug if identified

### Type 2: Performance Degradation

**Symptoms**:
- High latency (p99 > threshold)
- Slow API responses
- Timeouts on some requests

**Investigation**:
1. Check API Gateway/ALB metrics
2. Review database query performance
3. Check for traffic spikes
4. Review recent configuration changes
5. Profile slow endpoints

**Common causes**:
- Database query regression
- Traffic spike (legitimate or attack)
- Downstream dependency slow
- Resource contention

**Resolution**:
- Optimize slow queries
- Scale resources for traffic spike
- Enable caching if applicable
- Add rate limiting if attack

### Type 3: Data Pipeline Failure

**Symptoms**:
- ETL job failed
- Data processing delayed
- Missing data in reports

**Investigation**:
1. Check pipeline job logs
2. Verify data source availability
3. Check for schema changes
4. Review resource limits

**Common causes**:
- Data source schema change
- Volume spike exceeding limits
- Permission/credential issues
- Code bug in transformation logic

**Resolution**:
- Fix schema handling
- Scale pipeline resources
- Update credentials
- Fix transformation bug
- Backfill missing data

### Type 4: Cascading Failure

**Symptoms**:
- Multiple service incidents within minutes
- Services have known dependencies
- Failures propagate downstream

**Investigation**:
1. Identify root cause service (first to fail)
2. Map dependency chain
3. Check for circuit breaker status
4. Verify retry/timeout configurations

**Common causes**:
- Upstream service failure
- Shared resource exhaustion (database, cache)
- Network partition
- Configuration change affecting multiple services

**Resolution**:
- Fix root cause service first
- Enable circuit breakers to prevent cascade
- Implement retry backoff
- Add health checks for dependencies

## Incident Communication

### Internal Communication

**Acknowledge with ETA**:
```
Acknowledged - Investigating

Initial findings:
- Wallet service returning 500 errors
- Started 5 minutes ago after v1.2.3 deployment
- Checking logs for stack traces

ETA for next update: 15 minutes
```

**Progress updates (every 10-15 min)**:
```
Update: Investigating deployment

Findings:
- Found database migration issue in v1.2.3
- Migration script has syntax error
- Other services unaffected

Next steps:
- Rolling back to v1.2.2
- ETA: 5 minutes
```

**Resolution summary**:
```
Resolved - Bad database migration

Root cause:
v1.2.3 deployment included database migration with SQL syntax error, causing wallet service to fail on startup.

Resolution:
Rolled back to v1.2.2 (last known good version)

Impact:
- Duration: 18 minutes
- Affected: wallet-service only
- Customer impact: Payment processing unavailable

Prevention:
- Added migration testing to CI/CD pipeline
- Rally defect created: DE12345
```

### External Communication

For customer-facing incidents, coordinate with product/support:

**Status page update**:
```
Investigating: Payment Processing Issues
We're investigating reports of payment processing failures.
Updates will be provided as more information becomes available.

Time: 2026-02-26 14:35 EST
```

**Resolution update**:
```
Resolved: Payment Processing Issues
The issue with payment processing has been resolved.
All services are operating normally.

Root cause: Internal service deployment issue
Duration: 18 minutes
Time: 2026-02-26 14:53 EST
```

## Escalation Criteria

### When to Escalate to L2 (Secondary On-Call)

- No progress after 15 minutes of investigation
- Root cause unclear after initial diagnostics
- Issue requires specialized expertise (database, network, security)
- Multiple services affected simultaneously

### When to Escalate to L3 (Manager)

- Multiple P1 incidents ongoing
- Customer-facing service down > 30 minutes
- Data integrity concern requiring executive decision
- Need for additional resources/budget approval

### How to Escalate

Add escalation note:
```bash
python pagerduty_client.py incidents add-note \
  --id PXXXXX \
  --content "Escalating to L2 (Sarah Smith). Root cause unclear after 15 minutes. Requires database expertise. Summary: Wallet service down, intermittent DB connection timeouts, no recent deployments."
```

Then reassign:
```bash
python pagerduty_client.py incidents reassign \
  --id PXXXXX \
  --user-id PYYYYY
```

## Incident Retrospective Template

For P1/P2 incidents, conduct postmortem:

### What Happened?

- **Incident**: [Brief description]
- **Duration**: [Start time - End time]
- **Impact**: [Services affected, customer impact]
- **Detection**: [How was it detected?]
- **Resolution**: [How was it fixed?]

### Timeline

| Time | Event |
|------|-------|
| 14:30 | Deployment of v1.2.3 to production |
| 14:32 | First alert: DatabaseConnectionTimeout |
| 14:33 | Incident PXXXXX created (auto-triggered) |
| 14:34 | Acknowledged by Jeff Cox |
| 14:38 | Root cause identified: migration syntax error |
| 14:43 | Rollback initiated |
| 14:48 | Service restored, monitoring for stability |
| 14:53 | Incident resolved |

### Root Cause

[Detailed explanation of underlying cause]

### What Went Well?

- Quick detection (2 minutes after deployment)
- Fast acknowledgment (< 5 minutes)
- Clear escalation path
- Effective rollback process

### What Could Be Improved?

- Migration testing in CI/CD
- Deployment checklist enforcement
- Automated rollback on health check failure

### Action Items

| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| Add migration testing to CI pipeline | Jeff Cox | 2026-03-01 | P0 |
| Create deployment runbook | Sarah Smith | 2026-03-05 | P1 |
| Implement auto-rollback on health check fail | Mike Davis | 2026-03-15 | P2 |

## Runbook Integration

Link incidents to runbooks:

```
Incident: High database CPU

See runbook: docs/runbooks/database-high-cpu.md

Quick actions:
1. Check slow query log: aws rds describe-db-log-files
2. Review active queries: SELECT * FROM pg_stat_activity
3. Kill long-running query: SELECT pg_terminate_backend(pid)
4. Scale RDS instance if needed: aws rds modify-db-instance
```

## Automation Opportunities

### Auto-Acknowledge on Investigation Start

Automatically acknowledge when opening incident details:
```python
incident = get_incident(incident_id)
if incident["status"] == "triggered":
    acknowledge_incident(incident_id)
```

### Auto-Resolve on Health Check Pass

For transient issues, auto-resolve if health check passes:
```python
incident = get_incident(incident_id)
service = incident["service"]["id"]

if check_health(service):
    resolve_incident(incident_id, note="Service health check passed - auto-resolved")
```

### Smart Routing Based on Service

Route incidents to specialized teams:
```python
service = incident["service"]["id"]
if service in DATABAS_SERVICES:
    assign_to_dba_team(incident_id)
elif service in NETWORK_SERVICES:
    assign_to_network_team(incident_id)
```

## Metrics to Track

### Response Metrics
- Time to acknowledge (target: < 5 minutes)
- Time to resolve (target: < 30 minutes for P1)
- Escalation rate (target: < 20%)

### Quality Metrics
- Incident recurrence rate (same root cause)
- False positive rate (alerts that weren't real issues)
- Postmortem completion rate (target: 100% for P1/P2)

### Team Health Metrics
- Incidents per on-call shift (target: < 5)
- After-hours incidents (minimize)
- On-call rotation balance (even distribution)

## Additional Resources

- **Infiquetra Runbooks**: `/docs/runbooks/`
- **Service Catalog**: SLED API (use sled plugin)
- **Deployment History**: GitHub deployments
- **Monitoring Dashboards**: CloudWatch/Datadog
- **Team Slack**: 
