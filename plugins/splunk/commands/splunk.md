---
name: splunk
description: Quick Splunk log searches
usage: |
  /splunk [query]

  Examples:
    /splunk errors last hour
    /splunk wallet-service 500 errors
---

# /splunk Command

Quick access to Splunk log searches.

## Usage

```
/splunk errors last hour
/splunk wallet-service 500 errors
/splunk database timeout checkout
```

Converts natural language to SPL and executes search.

## Integration

Use full `splunk-search` skill for:
- Custom SPL queries
- Longer time ranges
- Advanced aggregations
- Job management
