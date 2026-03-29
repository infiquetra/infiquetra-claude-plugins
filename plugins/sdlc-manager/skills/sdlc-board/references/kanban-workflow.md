# Kanban Workflow Reference

Condensed reference for operating the Infiquetra Mount Olympus Kanban board. For the full
authoritative document see `$INFIQUETRA_SDLC_PATH/docs/process/kanban-workflow.md`.

---

## Board Structure

```
+---------+----------------+-------------+------------------+----------+
|  Ready  | In Development | E2E Testing | Deployment Ready | Deployed |
|(WIP: 10)|  (WIP: 3/dev)  |  (WIP: 3)   |     (WIP: 5)     | (Auto-   |
|         |                |             |                  | Archive) |
+---------+----------------+-------------+------------------+----------+
```

Backlog lives in `infiquetra-blueprint` (outside the flow board).
Analysis is optional — used when context gathering is needed before Ready.

---

## Column Definitions

### Ready (WIP: 10)

**Purpose**: Fully specified work waiting for developer capacity.

**Entry criteria**:
- Capability/issue defined in Blueprint with all acceptance criteria
- No blocking dependencies
- Team has identified this as current milestone focus

**Exit criteria**: Developer pulls item when capacity available (WIP < 3)

**Alert**: Item ages > 5 days

**Typical duration**: 0-2 days

---

### In Development (WIP: 3 per developer)

**Purpose**: Active AI-assisted development, code review, and integration testing.

**Entry criteria**:
- Developer has capacity (< 3 items in progress)
- Context reviewed, approach understood
- Cycle time start recorded

**Activities**:
- Claude Code implementation
- Unit + integration tests written
- Code review (automated gates + AI + human risk-based)
- PR merged
- Integration tests pass in non-prod

**Exit criteria**:
- All acceptance criteria met
- Tests passing (including integration)
- PR merged
- Ready for manual E2E

**Alert**: Item ages > expected cycle time (see typical durations below)

**Typical durations**:
- Capability: 3-12 days
- Enhancement: 1-4 days
- Defect: 2 hours - 1 day

---

### E2E Testing (WIP: 3)

**Purpose**: Manual end-to-end testing in pre-prod environment.

**Entry criteria**:
- PR merged, deployed to pre-prod
- Integration tests passing
- E2E test plan defined (from In Development)

**Activities**:
- Execute manual E2E test scenarios
- UAT, cross-service integration validation
- Document any issues found

**Exit criteria**:
- All E2E scenarios pass
- No critical issues
- Performance acceptable

**Alert**: Item ages > 2 days

**Typical durations**:
- Capability: 4-8 hours
- Enhancement: 1-4 hours
- Defect: 30 minutes - 2 hours

---

### Deployment Ready (WIP: 5)

**Purpose**: Queue of work ready for production deployment.

**Entry criteria**:
- All tests passing in non-prod
- Deployment plan documented with rollback plan

**Activities**:
- Await deployment window
- Coordinate dependent deployments

**Exit criteria**:
- Deployed to production successfully
- Health checks and monitoring confirm stability

**Typical duration**: 0-2 days

---

### Deployed (Auto-archive after 2 weeks)

**Purpose**: Completed work under production observation.

**Entry criteria**:
- Successfully deployed to production
- Cycle time end recorded
- Monitoring active

**Activities**:
- 48-hour observation period
- Collect metrics

**Exit criteria**: 2 weeks in production, no critical issues -> auto-archive

---

## WIP Limits

| Column | Limit | Rationale |
|--------|-------|-----------|
| Ready | 10 | Buffer for capacity matching |
| In Development | 3 per developer | Prevents context switching |
| E2E Testing | 3 | Manual testing capacity |
| Deployment Ready | 5 | Deployment schedule constraint |
| Deployed | Unlimited | Auto-archive keeps board clean |

**Dynamic In Development WIP**:
```
WIP limit = Number of active developers x 3
```
Example: 5 developers = WIP limit of 15

**When WIP is exceeded**:
1. Immediate Discord alert to team channel
2. Team stops pulling new work until WIP returns to limit
3. Daily standup focuses on clearing the bottleneck
4. Process improvement if violations are frequent

---

## Standup Format (15 minutes max)

### 1. Board Review — Right to Left

Walk the board from **Deployed -> Ready** (pull items through, don't push):

| Column | Key Questions |
|--------|---------------|
| Deployed | Anything to learn? Issues observed post-deploy? |
| Deployment Ready | When will these deploy? Any blockers? |
| E2E Testing | Test failures? Blocking issues? Items aging? |
| In Development | Aging items? Blockers? Code review stalled? |
| Ready | What should we focus on next? Team alignment? |

### 2. WIP Check
- Any columns at or over limit?
- Where is work accumulating?
- What is causing the bottleneck?

### 3. Milestone Alignment
- Are we on track for the current milestone?
- Do we need to swarm on any capabilities?
- Any ad-hoc sessions needed today?

### 4. Objective Check-in (if active time-bounded Objective)
- Days until Objective target date
- Progress: X of Y Capabilities deployed
- Any blockers risking the deadline?
- Scope adjustments needed?

### 5. Action Items
- Who will help with the bottleneck?
- What blockers need escalation?
- Any process improvements needed?

---

## Escalation Policies

| Condition | Action | Timeframe |
|-----------|--------|-----------|
| Item blocked | Add `blocked` label + notify team | Immediately |
| Blocked > 4 hours | Escalate to tech lead | 4 hours |
| Blocked > 1 day | Escalate to engineering manager | 24 hours |
| Item aging > expected + 50% | Flag in daily standup | Daily check |

---

## Aging Thresholds (Flag in Board Review)

| Column | Flag if age > |
|--------|--------------|
| Ready | 5 days |
| In Development | Expected cycle time + 50% (flag at >3 days as a practical default) |
| E2E Testing | 2 days |
| Deployment Ready | 2 days |

---

## Common Scenarios

### Production Emergency (Critical Defect)
1. Create defect issue immediately
2. Add `critical` priority label
3. Pull directly to In Development — **bypass Ready queue**
4. Fix, PR, expedite review (15-min SLA)
5. Deploy to production immediately
6. Follow up with root cause analysis

**Note**: Critical defects can temporarily exceed WIP limits.

### Blocked by External Dependency
1. Add `blocked` label with comment (what, who, when expected)
2. Create separate enhancement for external dependency
3. Move item back to Ready
4. Pull new work to maintain flow
5. Resume when blocker is cleared

### Context is Incomplete
1. Move item back to Ready (or optionally to Analysis)
2. Create `context-update` issue for Blueprint
3. Complete context update first, then resume

### Large Capability (4+ weeks estimated)
1. Break into 2-3 smaller capabilities if possible
2. If truly atomic, use sub-tasks for internal tracking
3. Consider feature flags for incremental delivery

---

## Cycle Time Targets (85th percentile)

| Issue Type | Target |
|------------|--------|
| Capability | < 5 days |
| Enhancement | < 2 days |
| Defect | < 1 day |

**Cycle time** = time from entering "In Development" to "Deployed"

---

## Work Pulling Rules

1. Check your WIP: < 3 items in In Development?
2. Review with team in standup or Discord
3. Consider current milestone focus
4. Review context — is it clear?
5. Pull (or swarm)
6. Update daily

**If capacity but nothing urgent in Ready**:
1. Help with E2E Testing (highest priority — unblocks deployment)
2. Pair with someone on in-progress work
3. Update Blueprint context
4. Optional Analysis for future work
