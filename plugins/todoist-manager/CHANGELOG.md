# Changelog

All notable changes to the Todoist Manager plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-02-23

### Added

#### Core Features
- **Complete Todoist Integration** via official `todoist-api-python` SDK (v3.x)
- **Natural Language Interface** - Talk naturally, no rigid commands required
- **Unified Skill (`todoist-manage`)** - Single entry point for all Todoist operations
- **Productivity Agent (`todoist-manager`)** - Strategic coach for complex workflows
- **Slash Command (`/todoist`)** - Quick access with auto-trigger support

#### Task Management
- Full CRUD operations (create, read, update, delete)
- Smart filter queries using Todoist filter language
- Quick-add with natural language parsing
- Bulk operations for multiple tasks
- Task comments for progress updates and notes
- Subtask support with parent/child relationships

#### Daily Planning Workflows
- **Morning Review**
  - Overdue, today, and upcoming task overview
  - Priority grouping with visual indicators
  - Time-blocked schedule generation
  - Focus list creation
  - Capacity analysis with buffer calculation
- **Evening Review**
  - Completion summary with win celebration
  - Incomplete task triage
  - Rescheduling and deferral support
  - Tomorrow's prep
- **Time-Blocking**
  - Available time calculation
  - Energy-matched scheduling (deep work, collaboration, admin)
  - Over-capacity warnings
  - Duration-based fitting algorithm

#### Weekly Reviews
- Completion metrics by project and priority
- Project health status indicators (on track, at risk, stalled)
- Pattern detection (priority inflation, task deferrals, overload)
- Maintenance workflows (archive, cleanup, label management)

#### Productivity Coaching
- Task breakdown framework for complex work
- Prioritization guidance
- Capacity planning and realistic scheduling
- Pattern recognition for productivity issues
- Proactive suggestions based on context
- Habit formation support

#### Project & Organization
- Project management (create, update, archive, delete)
- Section organization within projects
- Label system design and application
- Color coding and favorites
- Project hierarchy support

#### Advanced Features
- Complex filter queries with boolean logic (AND, OR, NOT)
- Date filters (today, overdue, 7 days, relative dates)
- Priority filters (p1-p4)
- Project/label/section filters
- Search functionality
- Duration tracking for time-blocking
- Recurring task support

#### Documentation
- Comprehensive `SKILL.md` with usage examples
- `todoist-api-reference.md` - Complete SDK method reference
- `filter-query-syntax.md` - Full filter query language guide
- `productivity-workflows.md` - Planning templates and coaching frameworks
- Detailed `README.md` with examples and troubleshooting
- Agent definition with strategic coaching approach
- Command documentation with quick reference

#### Python CLI Script
- `todoist_client.py` - 1000+ line CLI wrapping SDK
- JSON-only output for Claude parsing
- All resources supported: tasks, projects, sections, labels, comments
- Special endpoints: overview, daily-summary
- Comprehensive error handling
- Rate limit awareness
- Iterator pagination handling
- Nested object serialization

#### Safety & UX
- Confirmation prompts for destructive actions
- Consequence explanations for bulk operations
- Undo path suggestions where possible
- Contextual output formatting (checklist, table, grouped)
- Priority and status indicators (🔴🟡⚪)
- Progress celebration and motivational feedback

### Technical Details
- **SDK:** `todoist-api-python>=3.1.0,<4.0.0`
- **Python:** 3.12+ (3.11 compatible)
- **Authentication:** Personal API token via `TODOIST_TOKEN` env var
- **Output:** JSON for all operations
- **API Coverage:** REST API v2 via SDK (tasks, projects, sections, labels, comments)
- **Error Handling:** Graceful degradation with helpful error messages

### Dependencies
```toml
todoist-api-python = "^3.1.0,<4.0.0"
```

### File Structure
```
todoist-manager/
├── .claude-plugin/
│   └── plugin.json                         # Plugin manifest
├── skills/
│   └── todoist-manage/
│       ├── SKILL.md                        # Unified skill (400 lines)
│       ├── scripts/
│       │   └── todoist_client.py           # Python CLI (1000+ lines)
│       └── references/
│           ├── todoist-api-reference.md     # SDK reference (200 lines)
│           ├── filter-query-syntax.md       # Query syntax (120 lines)
│           └── productivity-workflows.md    # Planning templates (200 lines)
├── agents/
│   └── todoist-manager.md                   # Agent definition (80 lines)
├── commands/
│   └── todoist.md                           # /todoist command (80 lines)
├── README.md                                 # Plugin documentation (250 lines)
└── CHANGELOG.md                              # This file
```

### Installation
```bash
./install.sh todoist-manager
export TODOIST_TOKEN="your_token_here"
pip install 'todoist-api-python>=3.1.0,<4.0.0'
```

### Usage Examples

**Morning planning:**
```
/todoist
"Good morning, let's plan my day"
```

**Quick task add:**
```
"Add task: Buy milk tomorrow @shopping p1"
```

**Evening review:**
```
"Let's review my day"
```

**Complex reorganization:**
```
"I have 200 tasks and I'm overwhelmed - help me reorganize"
[Agent spawns for strategic session]
```

### Known Limitations
- Personal accounts only (no shared project collaboration features used)
- Completed tasks API has limited date filtering (requires manual filtering)
- Rate limits apply (free: ~450 requests/15 min)
- SDK v3.x (v4.x migration available when stable)

### Future Enhancements
Planned for future releases:
- Recurring task pattern analysis
- Productivity metrics dashboard
- Integration with calendar events
- Task template library
- GTD workflow presets
- Eisenhower matrix visualization
- Pomodoro timer integration
- Goal tracking with milestones

---

## Version History

- **1.0.0** (2025-02-23) - Initial release with full Todoist integration, daily planning, productivity coaching, and strategic agent
