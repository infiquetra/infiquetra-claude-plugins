# Task Description Templates

7 task type templates for common work patterns. Each template ensures clarity, actionability, scope, context, and defined outcomes.

Use these when creating or improving tasks via the task-review or plan-task skills.

---

## Template 1: Research Task

**Pattern:** Research [topic] and produce [deliverable]

**Template:**
```
Content: Research [topic] for [purpose]
Description: |
  Scope: [specific sources or boundaries]
  Done when: [deliverable] written and saved to [location]
  Key questions to answer:
  - [Question 1]
  - [Question 2]
  - [Question 3]
Labels: @computer @focus
Duration: [30-60] min
Priority: P[1-4]
```

**Example:**
```
Content: Research top 5 CI/CD tools for Python monorepos
Description: |
  Scope: Focus on GitHub Actions, CircleCI, GitLab CI, Jenkins, Buildkite
  Done when: 1-page comparison table saved to docs/ci-research.md
  Key questions:
  - Supports matrix builds?
  - Docker layer caching?
  - Cost at scale?
Labels: @computer @focus
Duration: 60 min
Priority: P2
```

---

## Template 2: Writing Task

**Pattern:** Write/Draft [document type] for [audience]

**Template:**
```
Content: Draft [document type] for [audience/purpose]
Description: |
  Format: [format and length]
  Done when: [draft milestone] — e.g., first draft complete, reviewed, approved
  Key sections:
  - [Section 1]
  - [Section 2]
Labels: @computer @focus
Duration: [30-90] min
Priority: P[1-4]
Due: [date if applicable]
```

**Example:**
```
Content: Draft Q1 engineering retrospective for team meeting
Description: |
  Format: Slide deck, 8-10 slides
  Done when: Slides sent to team Slack channel by Thursday 5pm
  Sections: Wins, Challenges, Action Items, Goals for Q2
Labels: @computer @focus
Duration: 90 min
Priority: P1
Due: Thursday
```

---

## Template 3: Coding / Technical Task

**Pattern:** [Verb] [component] in [module/file] to [achieve outcome]

**Template:**
```
Content: [Fix/Build/Refactor/Test] [component] in [module] to [outcome]
Description: |
  Context: [why this needs to happen]
  Done when: [technical completion criterion]
  Acceptance criteria:
  - [Criterion 1]
  - [Criterion 2]
  Files: [relevant files or modules]
Labels: @computer @focus
Duration: [30-90] min
Priority: P[1-4]
```

**Example:**
```
Content: Fix null pointer exception in user.profile.get() method
Description: |
  Context: Crashes when user has no profile set (new users)
  Done when: Exception handled gracefully, returns empty profile object, unit test added
  Acceptance criteria:
  - No crash on empty profile
  - Test covers null/None case
  - Existing tests still pass
  Files: src/user/profile.py, tests/test_profile.py
Labels: @computer @focus
Duration: 45 min
Priority: P1
```

---

## Template 4: Meeting / Synchronous Task

**Pattern:** [Meet/Call/Present] with [person/group] about [topic]

**Template:**
```
Content: [Meet/Call/Present to] [person/group] re: [topic]
Description: |
  Goal: [what to accomplish in this meeting]
  Prepare: [what to do before meeting]
  Done when: [outcome — decision made, notes sent, follow-up scheduled]
  Attendees: [names if relevant]
Labels: @calendar @phone (or @video)
Duration: [15-60] min
Priority: P[1-4]
Due: [datetime of meeting]
```

**Example:**
```
Content: Call Sarah re: Q2 contract renewal terms
Description: |
  Goal: Agree on renewal price and timeline
  Prepare: Review current contract, check budget forecast
  Done when: Terms agreed verbally, follow-up email sent with summary
  Attendees: Sarah (client), self
Labels: @phone @client
Duration: 30 min
Priority: P1
Due: Tuesday at 2pm
```

---

## Template 5: Administrative Task

**Pattern:** [Complete/Submit/Process] [administrative item]

**Template:**
```
Content: [Complete/Submit/Process/File] [administrative item]
Description: |
  Where: [system/location/recipient]
  Done when: [confirmation received / submitted / filed]
  Required info: [what to gather first]
Labels: @quick @admin
Duration: [5-30] min
Priority: P[1-4]
Due: [deadline if applicable]
```

**Example:**
```
Content: Submit expense report for February conference travel
Description: |
  Where: Concur expense system
  Done when: Report submitted and confirmation email received
  Required info: Receipts from hotel, flight, meals (in email folder "Feb Conference")
Labels: @quick @admin
Duration: 20 min
Priority: P2
Due: Friday (month-end)
```

---

## Template 6: Communication Task

**Pattern:** [Send/Reply/Review] [communication] to/from [recipient]

**Template:**
```
Content: [Send/Reply to/Review] [email/message/document] [to/from] [recipient]
Description: |
  Key points to communicate: [main message]
  Tone: [formal/informal/technical]
  Done when: [sent / replied / reviewed and approved]
  Attachments/refs: [what to include]
Labels: @computer @quick (or @focus for complex)
Duration: [5-30] min
Priority: P[1-4]
Due: [deadline]
```

**Example:**
```
Content: Send project status update to client stakeholders
Description: |
  Key points: Sprint 3 complete, 2 bugs fixed, on track for March delivery
  Tone: Professional, reassuring
  Done when: Email sent to client-list@company.com, CC'd PM
  Attachments: Sprint 3 summary report (attached)
Labels: @computer @quick
Duration: 15 min
Priority: P1
Due: Today by 3pm
```

---

## Template 7: Planning / Design Task

**Pattern:** Plan/Design [initiative] for [timeframe/purpose]

**Template:**
```
Content: [Plan/Design/Outline/Architect] [initiative] for [purpose/timeframe]
Description: |
  Scope: [boundaries of what to plan]
  Stakeholders: [who will review/approve]
  Done when: [plan deliverable] — e.g., doc written, reviewed, approved
  Key decisions to make:
  - [Decision 1]
  - [Decision 2]
Labels: @computer @focus
Duration: [60-90] min
Priority: P[1-4]
Due: [date]
```

**Example:**
```
Content: Design database schema for multi-tenant user permissions
Description: |
  Scope: User, Role, Permission tables + join tables. Not the UI or API layer.
  Stakeholders: Backend lead (review), CTO (approve)
  Done when: Schema diagram + migration script draft reviewed by backend lead
  Key decisions:
  - RBAC vs ABAC approach
  - How to handle permission inheritance
  - Index strategy for permission checks
Labels: @computer @focus
Duration: 90 min
Priority: P2
Due: Thursday
```

---

## Quick Template Selector

| Task Type | When to Use | Typical Duration |
|-----------|-------------|-----------------|
| Research | Gathering information, exploring options | 30-60 min |
| Writing | Documents, reports, proposals, emails | 30-90 min |
| Coding | Build, fix, refactor, test code | 30-90 min |
| Meeting | Synchronous conversations | 15-60 min |
| Admin | Forms, expenses, filing, scheduling | 5-30 min |
| Communication | Emails, messages, responses | 5-30 min |
| Planning | Strategy, design, architecture | 60-120 min |

## Applying Templates

When reviewing a task with the task-review skill:

1. **Identify the task type** from the table above
2. **Map current task to template** — what's missing?
3. **Propose revised version** using the appropriate template
4. **Confirm with user** before applying changes
5. **Apply via update command:**

```bash
python3 <script_path> tasks update \
  --task-id <ID> \
  --content "Revised content matching template" \
  --description "Template description block" \
  --labels <appropriate labels> \
  --duration <estimate> \
  --due-string "<if applicable>"
```
