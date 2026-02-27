# Infiquetra Splunk Plugin

Splunk log search and analysis for Infiquetra operations with natural language query building and SPL execution.

## Features

- **Natural Language to SPL**: Convert user queries to SPL syntax
- **Async Search**: Submit, poll, and retrieve search results
- **Convenience Execute**: One-command search with automatic polling
- **Resource Discovery**: List apps and indexes
- **Incident Correlation**: Link logs with PagerDuty incidents

## Installation

1. Set environment variables:
```bash
export SPLUNK_TOKEN="your-splunk-token"
export SPLUNK_HOST="splunk.example.com"
```

2. Install plugin:
```bash
cp -r plugins/splunk ~/.claude/plugins/
```

3. Restart Claude Code

## Usage

### Quick Search

```
Search Splunk for errors from wallet-service in the last hour
```

### Advanced Queries

```
Find all 500 errors from the API in the last 24 hours
Show me database timeouts in checkout service
What are the most common errors today?
```

### Incident Investigation

```
Check logs around incident PXXXXX (triggered at 14:30)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SPLUNK_TOKEN` | Yes | Splunk authentication token |
| `SPLUNK_HOST` | Yes | Splunk hostname (e.g., splunk.example.com) |

## Integration

- **PagerDuty**: Correlate incidents with log patterns
- **Rally**: Add log evidence to defects
- **CloudWatch**: Cross-reference metrics with logs

## Support

- **Slack**: 
- **Documentation**: See SKILL.md and references/
