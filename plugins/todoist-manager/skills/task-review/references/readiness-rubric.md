# Task Readiness Rubric

5-dimension scoring system for evaluating Todoist task quality. Each dimension scores 0-2 for a maximum of 10 points.

## Scoring Summary

| Score | Interpretation |
|-------|----------------|
| 9-10  | ✅ Ready to Execute — start immediately |
| 7-8   | ✅ Ready with minor polish |
| 5-6   | ⚠️ Needs Improvement — fix before starting |
| 3-4   | ❌ Not Ready — significant rework needed |
| 0-2   | ❌ Placeholder — must be rewritten |

---

## Dimension 1: Clarity (0-2)

**Question:** Is the task content unambiguous? Could someone unfamiliar with the project understand exactly what needs to be done?

| Score | Criteria |
|-------|----------|
| 2 | Completely clear. Specific subject, verb, and object. No ambiguity about what or why. |
| 1 | Mostly clear but has one vague element (e.g., missing context or imprecise outcome). |
| 0 | Vague or ambiguous. "Work on X", "Handle Y", "Do Z" — unclear what action to take. |

**Examples:**

- ✅ 2: "Review PR #142 for security vulnerabilities in auth module"
- ⚠️ 1: "Review the pull request" (which one?)
- ❌ 0: "Handle the PR thing"

**Common clarity failures:**
- Pronouns without antecedents ("it", "that thing")
- Missing subject ("Fix the bug" — in which file/module?)
- Overloaded tasks ("Handle client feedback and update docs and deploy")

---

## Dimension 2: Actionability (0-2)

**Question:** Does the task start with a concrete action verb? Is the first physical action obvious?

| Score | Criteria |
|-------|----------|
| 2 | Starts with a strong action verb. The first physical step is immediately obvious. |
| 1 | Has an implied action but not explicit. Or starts with a weak verb ("work on", "look at", "deal with"). |
| 0 | No action verb. Or requires significant interpretation to identify the first step. |

**Strong action verbs:**
Research, Write, Review, Read, Call, Email, Draft, Design, Build, Fix, Test, Deploy, Update, Schedule, Send, Analyze, Create, Document, Approve, Configure, Install, Setup, Record, Present, Interview

**Weak action verbs (score 1):**
Work on, Handle, Deal with, Think about, Look at, Go over, Touch base, Check on

**No action verb (score 0):**
"Project proposal", "Client meeting notes", "The report"

---

## Dimension 3: Scope (0-2)

**Question:** Can this task be completed in a single work session (under 2 hours)? Is the scope bounded?

| Score | Criteria |
|-------|----------|
| 2 | Clearly bounded. Completable in 1-2 hours. Has an end state. |
| 1 | Mostly bounded but could expand. Duration uncertain (1-3 hours). |
| 0 | Unbounded or multi-day effort. Should be a project, not a task. |

**Duration guidelines:**
- ✅ < 30 min: ideal for @quick or admin tasks
- ✅ 30-90 min: good for focus tasks
- ⚠️ 90-120 min: borderline — consider splitting
- ❌ > 120 min: break into subtasks

**Scope reduction patterns:**

Too large → Split into phases:
- "Write technical spec" → "Draft technical spec outline (30 min)" + "Write technical spec body (60 min)" + "Review and finalize (30 min)"

Too vague → Define the deliverable:
- "Research competitors" → "Research top 3 competitors and write 1-page summary"

---

## Dimension 4: Context (0-2)

**Question:** Does the task have the metadata needed to schedule, filter, and prioritize it effectively?

| Score | Criteria |
|-------|----------|
| 2 | Has project, priority, and at least one label. Due date if time-sensitive. |
| 1 | Has some metadata but missing one important field (e.g., no labels or wrong priority). |
| 0 | Missing most metadata. No project, no labels, default priority. Hard to find or schedule. |

**Metadata checklist:**
- [ ] **Project:** Assigned to correct project (not Inbox)
- [ ] **Priority:** Accurate (P1=must-do-today, P2=important, P3=nice-to-have, P4=someday)
- [ ] **Labels:** At least one context or energy label
- [ ] **Due date:** Set if task is time-sensitive
- [ ] **Duration:** Set if task requires time-blocking
- [ ] **Description:** Added if task needs more context

**Priority calibration:**
- P1 (Urgent): Blocking others or has hard deadline today
- P2 (Higher): Important, should be done this week
- P3 (High): Nice to have, can slip to next week
- P4 (Normal): Backlog, no urgency

---

## Dimension 5: Outcome (0-2)

**Question:** Is "done" clearly defined? Would you know with certainty when this task is complete?

| Score | Criteria |
|-------|----------|
| 2 | Clear, testable completion criterion. "Done when: [specific deliverable or state]" |
| 1 | Implied outcome but not explicit. Could be interpreted as complete prematurely or never. |
| 0 | No defined outcome. Could go on forever or be abandoned without clear stopping point. |

**Outcome patterns:**

Good (score 2):
- "Done when: PR is approved and merged"
- "Done when: Email sent to client with attachment"
- "Done when: Test coverage >80% on auth module"
- "Done when: 1-page summary written and saved"

Implied (score 1):
- "Write unit tests" (how many? which coverage?)
- "Update documentation" (which pages? what changes?)

Missing (score 0):
- "Work on the refactor"
- "Handle client stuff"

**Where to record the outcome:**
- For short tasks: include in content ("Write and send weekly status email")
- For complex tasks: add to description field

---

## Scoring Examples

### Example 1: High Score

**Task:** "Write unit tests for user authentication module"
- **Priority:** P2
- **Labels:** @focus, @computer
- **Due:** Friday
- **Duration:** 90 min
- **Description:** "Done when: test coverage for auth module is >85%"

| Dimension | Score | Notes |
|-----------|-------|-------|
| Clarity | 2 | Specific module, specific action |
| Actionability | 2 | "Write" — clear first step |
| Scope | 2 | 90 min, bounded to one module |
| Context | 2 | Has project, priority, labels, duration |
| Outcome | 2 | >85% coverage criterion |
| **Total** | **10/10** | ✅ Ready to Execute |

---

### Example 2: Medium Score

**Task:** "Update documentation"
- **Priority:** P3
- **Labels:** none
- **Due:** none
- **Duration:** none

| Dimension | Score | Notes |
|-----------|-------|-------|
| Clarity | 1 | Which documentation? |
| Actionability | 1 | "Update" is weak — what kind of update? |
| Scope | 1 | Could be 30 min or 3 days |
| Context | 0 | No labels, no duration, no due date |
| Outcome | 0 | "Updated" is not defined |
| **Total** | **3/10** | ❌ Not Ready |

**Revised:** "Update API reference docs with new /auth endpoints (3 pages)"
+ Description: "Done when: /login, /refresh, /logout endpoints documented with examples"
+ Labels: @computer, @focus
+ Duration: 60 min

---

### Example 3: Low Score

**Task:** "Handle the thing"
- All defaults

| Dimension | Score | Notes |
|-----------|-------|-------|
| Clarity | 0 | No idea what "thing" is |
| Actionability | 0 | "Handle" gives no direction |
| Scope | 0 | Undefined |
| Context | 0 | No metadata |
| Outcome | 0 | Undefined |
| **Total** | **0/10** | ❌ Placeholder — must be rewritten |
