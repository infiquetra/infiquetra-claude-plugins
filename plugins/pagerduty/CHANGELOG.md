# Changelog

All notable changes to the pagerduty plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-26

### Added
- Initial release of pagerduty plugin
- **Skills**:
  - `pagerduty-incidents`: Incident management with query, acknowledge, resolve, notes
  - `pagerduty-services`: Full CRUD for services and integrations
  - `pagerduty-teams`: Team management, escalation policies, on-call schedules
- **Agent**:
  - `pagerduty-ops`: Incident investigation and blast radius analysis
- **Command**:
  - `/pagerduty`: Quick access to common PagerDuty operations
- **Client Script**:
  - `pagerduty_client.py`: Comprehensive PagerDuty API v2 client
  - Support for incidents, services, teams, escalation policies, schedules, users
  - Pagination handling for large result sets
  - JSON output format for Claude parsing
  - Infiquetra defaults (Team ID: YOUR_TEAM_ID, Policy: YOUR_POLICY_ID)
- **Documentation**:
  - Comprehensive README with examples
  - API reference documentation
  - Productivity workflow guides
  - Integration patterns with other Infiquetra tools

### Features
- Natural language incident queries
- Incident correlation with deployment timing
- Blast radius analysis (service → team → dependencies)
- Intelligent triage suggestions
- Escalation policy audit trails
- On-call schedule management
