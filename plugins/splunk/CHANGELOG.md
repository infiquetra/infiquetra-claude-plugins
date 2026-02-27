# Changelog

## [1.0.0] - 2026-02-26

### Added
- Initial release of splunk plugin
- **splunk-search** skill: Log search and analysis
- `splunk_client.py`: Splunk REST API client (~400 lines)
- Search operations: submit, poll, results, execute, delete
- Resource management: list apps, list indexes
- Natural language to SPL query conversion
- Async search pattern with polling
- Convenience `execute` command for simple searches
- Integration with PagerDuty for incident correlation
- Time range parsing with relative and absolute times
- JSON output format for Claude parsing
