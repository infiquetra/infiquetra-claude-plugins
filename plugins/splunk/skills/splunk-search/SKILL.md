---
name: splunk-search
description: Search and analyze Splunk logs with natural language query building and SPL execution
when_to_use: |
  Use this skill when the user wants to:
  - Search Splunk logs for errors, patterns, or events
  - Build SPL queries from natural language
  - Correlate logs with PagerDuty incidents
  - Analyze application behavior and performance
  - Investigate production issues
  - Query specific indexes or time ranges
---

# Splunk Search

You are helping the user search and analyze Splunk logs through natural language interactions.

## Prerequisites

Verify environment variables are set:
```bash
echo $SPLUNK_TOKEN
echo $SPLUNK_HOST
```

If not set:
- `SPLUNK_TOKEN`: Get from Splunk Settings → Tokens
- `SPLUNK_HOST`: Splunk hostname (e.g., splunk.example.com)

## Core Operations

### Execute Search (Convenience Method)

Most common operation - submit search and wait for results:

```bash
python plugins/splunk/skills/splunk-search/scripts/splunk_client.py search execute \
  --query 'index=prod service=wallet-service level=ERROR' \
  --earliest-time '-1h' \
  --timeout 60
```

**Parameters**:
- `--query`: SPL search query (will prepend 'search' if missing)
- `--earliest-time`: Start time (default: -1h) - supports relative times
- `--latest-time`: End time (default: now)
- `--max-count`: Max results (default: 100)
- `--timeout`: Max wait seconds (default: 60)

### Advanced Search Pattern (Submit → Poll → Results)

For long-running searches:

**1. Submit search job**:
```bash
python splunk_client.py search submit \
  --query 'index=prod service=wallet-service | stats count by status_code'
```

Returns: `{"success": true, "data": {"sid": "1234567890.12345"}}`

**2. Poll job status**:
```bash
python splunk_client.py search poll --job-id 1234567890.12345
```

Returns job progress and status

**3. Get results**:
```bash
python splunk_client.py search results --job-id 1234567890.12345
```

### List Resources

**List apps**:
```bash
python splunk_client.py apps list
```

**List indexes**:
```bash
python splunk_client.py indexes list
```

## Natural Language Examples

### Error Investigation

**User**: "Show me errors from wallet-service in the last hour"

**Response**:
1. Build SPL query: `index=prod service=wallet-service level=ERROR`
2. Set time range: `-1h` to `now`
3. Execute search
4. Parse and summarize results
5. Highlight common patterns

**User**: "Find all 500 errors from the API in the last 24 hours"

**Response**:
```bash
python splunk_client.py search execute \
  --query 'index=prod source="api*" status_code=500' \
  --earliest-time '-24h'
```

### Incident Correlation

**User**: "Check logs around the time of incident PXXXXX (14:30)"

**Response**:
1. Get incident trigger time from PagerDuty
2. Build time range: 5 minutes before/after
3. Search relevant service logs
4. Correlate error patterns with incident

### Pattern Detection

**User**: "What errors are most common in the checkout service?"

**Response**:
```bash
python splunk_client.py search execute \
  --query 'index=prod service=checkout-service level=ERROR | stats count by error_message | sort -count'
```

### Performance Analysis

**User**: "Show API response times over 2 seconds in the last hour"

**Response**:
```bash
python splunk_client.py search execute \
  --query 'index=prod source="api*" response_time>2000 | stats avg(response_time) by endpoint'
```

## SPL Query Building

Convert natural language to SPL:

| Natural Language | SPL Query |
|------------------|-----------|
| "errors from wallet-service" | `index=prod service=wallet-service level=ERROR` |
| "500 errors from API" | `index=prod source="api*" status_code=500` |
| "database timeouts" | `index=prod error_type=timeout | search *database*` |
| "high memory usage" | `index=metrics metric_name=memory_usage | where value>80` |
| "requests per minute" | `index=prod | timechart span=1m count` |

### Common SPL Patterns

**Basic search**:
```spl
index=prod service=wallet-service level=ERROR
```

**With time range**:
```spl
index=prod earliest=-1h latest=now
```

**Field extraction**:
```spl
index=prod | rex field=message "error_code=(?<code>\d+)"
```

**Aggregation**:
```spl
index=prod | stats count by service, level
```

**Filtering**:
```spl
index=prod | where response_time > 1000
```

**Sorting**:
```spl
index=prod | stats count by error_message | sort -count | head 10
```

## Integration with Other Tools

### PagerDuty Correlation

After incident acknowledgment:
```
Incident PXXXXX acknowledged (wallet-service, 14:32)

Check Splunk logs?
1. Errors in 5-minute window (14:27-14:37)
2. Stack traces and exceptions
3. Request volume patterns
4. Related service errors
```

Suggested query:
```spl
index=prod service=wallet-service earliest="2026-02-26T14:27:00" latest="2026-02-26T14:37:00" level=ERROR
```

### Rally Defect Context

When creating defects:
```
Rally defect DE12345: Database timeout in wallet-service

Splunk evidence:
- 143 timeout errors in 10-minute window
- Query: SELECT * FROM transactions WHERE...
- Stack trace: [link to Splunk search]
```

### CloudWatch Metrics Correlation

```
High CPU in wallet-service (CloudWatch shows 85%)

Splunk log analysis:
- 234 slow queries (>1s) in last hour
- Pattern: Large transaction batch processing
- Recommendation: Optimize query or add batching
```

## LLM Value-Add Features

### Intelligent Query Suggestions

When user describes an issue:
```
User: "The checkout is slow"

Suggested Splunk queries:
1. Response times: index=prod service=checkout | stats avg(response_time) by endpoint
2. Error rates: index=prod service=checkout level=ERROR | timechart count
3. External calls: index=prod service=checkout | search *timeout* OR *slow*
4. Database queries: index=prod service=checkout source=*db* | stats avg(duration_ms)
```

### Pattern Recognition

```json
{
  "pattern_detected": "Database Connection Pool Exhaustion",
  "evidence": [
    "142 'connection timeout' errors",
    "Peak at 14:32 (matches incident trigger)",
    "Error message: 'Unable to acquire connection from pool'"
  ],
  "related_searches": [
    "Check connection pool metrics",
    "Review database CPU usage",
    "Find concurrent request count"
  ]
}
```

### Natural Language to SPL

**User input**: "Show me yesterday's errors sorted by frequency"

**Translation**:
```spl
index=prod earliest=-1d@d latest=@d level=ERROR
| stats count by error_message
| sort -count
```

**Explanation**:
- `earliest=-1d@d`: Start of yesterday
- `latest=@d`: Start of today (end of yesterday)
- `stats count by error_message`: Group and count by error
- `sort -count`: Sort descending by count

## Time Range Syntax

Splunk supports flexible time ranges:

| Expression | Meaning |
|------------|---------|
| `-1h` | Last hour |
| `-24h` | Last 24 hours |
| `-7d` | Last 7 days |
| `-1d@d` | Start of yesterday |
| `@d` | Start of today |
| `@w0` | Start of this week (Sunday) |
| `@mon` | Start of this month |
| `2026-02-26T14:30:00` | Absolute time (ISO 8601) |

## Best Practices

### Search Optimization

1. **Always specify index**: `index=prod` faster than searching all indexes
2. **Use earliest/latest**: Limit time range for faster searches
3. **Filter early**: Put filters before pipes for better performance
4. **Limit results**: Use `head` or `--max-count` to avoid large result sets

Good:
```spl
index=prod service=wallet-service earliest=-1h | stats count by level
```

Bad:
```spl
* | search service=wallet-service | stats count by level
```

### Security

- Never log sensitive data (passwords, tokens, PII)
- Use field extraction to parse structured logs
- Redact sensitive fields in query results

## Error Handling

### Common Errors

**1. Missing credentials**:
```json
{
  "error": true,
  "message": "SPLUNK_TOKEN environment variable not set"
}
```
**Solution**: Set SPLUNK_TOKEN

**2. Search timeout**:
```json
{
  "error": true,
  "message": "Search timeout after 60 seconds. Job still running (SID: 1234567890.12345)",
  "sid": "1234567890.12345"
}
```
**Solution**: Use longer timeout or check job manually with poll/results

**3. Invalid SPL syntax**:
```json
{
  "error": true,
  "message": "Error in 'stats' command: The argument 'by' is invalid.",
  "status_code": 400
}
```
**Solution**: Fix SPL syntax

## Output Format

All commands return JSON:

```json
{
  "success": true,
  "data": [
    {
      "_time": "2026-02-26T14:32:15.000Z",
      "service": "wallet-service",
      "level": "ERROR",
      "message": "Database connection timeout"
    }
  ],
  "count": 1,
  "elapsed_seconds": 2.34
}
```

## Reference Documentation

See `references/` directory for:
- `splunk-api.md`: Complete Splunk REST API reference
- `spl-reference.md`: SPL query language guide
