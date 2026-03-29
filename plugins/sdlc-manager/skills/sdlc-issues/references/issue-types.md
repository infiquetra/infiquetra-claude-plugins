# Issue Types Reference

Complete guide to all 6 Infiquetra SDLC issue types. This replaces the traditional
Epic/Feature/Story/Task hierarchy with types optimized for AI-assisted development.

---

## Decision Tree

```
Is this coordinating multiple capabilities with a target date?
+- Yes -> OBJECTIVE
+- No
   +- Is it broken in production?
      +- Yes -> DEFECT
      +- No
         +- Is it new functionality?
            +- Yes
            |  +- Is it end-to-end and deployable independently?
            |     +- Yes -> CAPABILITY
            |     +- No -> ENHANCEMENT (or break down if too large)
            +- No
               +- Are you improving existing functionality?
                  +- Yes -> ENHANCEMENT
                  +- No
                     +- Are you researching or investigating?
                        +- Yes -> EXPLORATION
                        +- No
                           +- Are you updating documentation?
                              +- Yes -> CONTEXT UPDATE
                              +- No -> Reconsider what you're trying to accomplish
```

---

## Comparison Table

| Attribute | Objective | Capability | Enhancement | Defect | Exploration | Context Update |
|-----------|-----------|------------|-------------|--------|-------------|----------------|
| **Duration** | 2-8 weeks | 1-4 weeks | 2-5 days | Hours-2 days | 1-3 days | Hours-1 day |
| **AI Usage** | N/A | 60-80% | 50-70% | 30-50% | 20-40% | 40-60% |
| **Review Required** | Stakeholder | 2 reviewers | 1 reviewer | 1 reviewer | 1 reviewer | 1 reviewer |
| **Test Coverage** | N/A | 90%+ | 85%+ | 90%+ | N/A | N/A |
| **Contains** | 3-10 Capabilities | N/A | N/A | N/A | N/A | N/A |

---

## 1. Objective

**Definition**: A time-bounded deliverable set that coordinates multiple Capabilities toward a common goal.
Used for Pilots, MVPs, Releases, and Program milestones.

### When to Use
- Coordinating time-bounded pilot or customer validation
- Planning MVP or release with a specific target date
- Tracking OKR or program milestone
- Multiple Capabilities must deliver together
- Executive visibility required

### When NOT to Use
- Single Capability (assign Capability directly to Initiative instead)
- Ongoing work without a specific delivery target
- Informal team coordination

### Size / Duration
2-8 weeks. Contains 3-10 Capabilities:

| Size | Duration | Capabilities |
|------|----------|--------------|
| Small | 2-4 weeks | 3-5 capabilities |
| Medium | 4-6 weeks | 5-8 capabilities |
| Large | 6-8 weeks | 8-10 capabilities |

If > 10 Capabilities: consider breaking into multiple Objectives or extending the timeline.

### Objective Types
| Type | When to Use | Example |
|------|-------------|---------|
| **Pilot** | Customer validation with specific participants | "Pilot: Platform Launch with 5 early adopters" |
| **MVP** | Minimum viable product for initial launch | "MVP: Core Auth Integration" |
| **Release** | Versioned delivery requiring coordination | "Release: Olympus v1.0" |
| **Program** | OKR milestone or initiative phase | "Program: Q1 KR1 - User Adoption" |

### Required Labels
- `objective` (auto-applied by template)
- `objective:{short-name}` (applied after creation, e.g., `objective:platform-launch`)
- `initiative:{name}` (if part of a strategic initiative)

### Examples
**Good**:
- "Pilot: Platform Launch with 5 early adopters by March 15, 2026"
- "Release: Olympus v1.0 general availability by April 30, 2026"
- "MVP: Core auth integration complete by Feb 28"

**Not an Objective**:
- "Improve platform performance" — too vague, no target date
- "Add logging to services" — single Capability or Enhancement, not a coordinated set

---

## 2. Capability

**Definition**: A complete, deployable piece of system functionality that delivers meaningful business
or technical value. The primary unit of work in AI-native development.

### When to Use
- Delivers complete end-to-end functionality (UI + API + data + infrastructure)
- Can be deployed and used independently
- Has clear acceptance criteria and success metrics
- Represents meaningful business value
- Requires 1-4 weeks with AI assistance

### When NOT to Use
- The work improves existing functionality -> use **Enhancement**
- Something is broken in production -> use **Defect**
- You need to research options first -> use **Exploration**
- Scope exceeds 4 weeks -> break into multiple Capabilities

### Size / Duration
1-4 weeks with AI assistance:

| Size | Duration | Examples |
|------|----------|----------|
| XS | 1-2 days | Add new API endpoint with basic CRUD |
| S | 3-5 days | Auth integration with external provider |
| M | 1-2 weeks | Notification system with message queue + workers |
| L | 2-4 weeks | Identity verification service with multiple providers |

### Required Labels
- `capability`, `needs-analysis` (auto-applied by template)

### Examples
**Good**:
- "Implement user onboarding service with API, database persistence, and monitoring"
- "Add biometric authentication flow to app with backend API integration"
- "Create automated notification system with retry logic"

**Not a Capability (too small)**:
- "Add logging to API endpoint" -> use **Enhancement**
- "Fix timeout error in auth API" -> use **Defect**

**Not a Capability (too large)**:
- "Implement entire identity verification platform" -> break into multiple Capabilities

---

## 3. Enhancement

**Definition**: Improves an existing capability without adding fundamentally new functionality.
For optimization, refinement, refactoring, and incremental improvements.

### When to Use
- Improves existing functionality
- Optimizes performance or reduces cost
- Enhances user experience
- Adds minor features to an existing capability
- Refactors existing code

### When NOT to Use
- Building new end-to-end functionality -> use **Capability**
- Fixing broken functionality in production -> use **Defect**

### Size / Duration
2-5 days with AI assistance:

| Duration | Complexity | Examples |
|----------|------------|----------|
| 2 hours | Trivial | Add log statement, update copy text |
| 1 day | Simple | Add validation, simple refactor |
| 2-3 days | Moderate | Add caching, improve error handling |
| 4-5 days | Complex | Significant refactor, performance optimization |

### Required Labels
- `enhancement`, `needs-analysis` (auto-applied by template)

### Examples
**Good**:
- "Add caching layer to reduce API latency from 800ms to 200ms"
- "Improve error messages in authentication flow"
- "Add pagination to user list endpoint"
- "Refactor auth service for better testability"

**Not an Enhancement**:
- "Build authentication service" -> use **Capability** (new functionality)
- "Fix crash in auth validation" -> use **Defect** (broken functionality)

---

## 4. Defect

**Definition**: A bug or issue in production that requires fixing. Defects have the highest priority
and shortest cycle time targets.

### When to Use
- Functionality that previously worked is now broken
- Functionality doesn't match the specification
- Error or exception occurs in production
- Performance has regressed significantly
- Security vulnerability discovered

### When NOT to Use
- Adding new functionality -> use **Capability** or **Enhancement**
- Pre-production issues discovered during development -> fix inline or use **Enhancement**

### Size / Duration
Hours to 2 days. Priority determines SLA:

| Priority | SLA | Description | Examples |
|----------|-----|-------------|---------|
| Critical | 4 hours | System down, data loss, security breach | API returning 500, data corruption |
| High | 1 day | Major functionality broken | Auth failing, can't create records |
| Medium | 3 days | Minor functionality broken | Validation too strict, UI glitch |
| Low | When capacity | Cosmetic or rare edge case | Typo, rare race condition |

### Required Labels
- `defect`, `needs-triage` (auto-applied by template)
- `critical` / `high-priority` / `medium-priority` / `low-priority` (add manually)

### Examples
**Good**:
- "API returning 500 error for valid requests since deploy at 14:30"
- "Auth token validation failing for tokens issued before Jan 15"
- "Record creation silently failing for IDs with special characters"

**Not a Defect**:
- "Auth service could be faster" -> use **Enhancement** (performance improvement, not regression)
- "Add retry logic to external API calls" -> use **Enhancement** (new resilience feature)

---

## 5. Exploration

**Definition**: Research, proof-of-concept, or architectural investigation that informs future
decisions. Produces knowledge, not production code.

### When to Use
- Need to evaluate multiple technical approaches
- Uncertain about feasibility
- Need to learn a new technology or library
- Architectural decision requires validation
- Estimating a large Capability requires research first

### When NOT to Use
- You already know the approach -> create a **Capability** directly
- Exploration exceeds 3 days -> timebox strictly; create follow-up Exploration if needed

### Size / Duration
1-3 days maximum (timebox strictly).

### Required Labels
- `exploration`, `research` (auto-applied by template)

### Exploration Outcomes
- **Clear Recommendation**: Document in Blueprint, create ADR, create follow-up Capability
- **Need More Research**: Document learnings, create refined follow-up Exploration
- **Not Feasible**: Document why, propose alternatives, inform stakeholders

### Examples
**Good**:
- "Evaluate auth SDK options: Auth0 vs. Clerk vs. Supabase Auth"
- "POC: Can we achieve <100ms latency with current architecture?"
- "Spike: Estimate effort to migrate database schema"
- "Investigation: Root cause of intermittent timeout errors in API service"

**Not an Exploration**:
- "Implement biometric authentication" -> use **Capability** (you already know the approach)

---

## 6. Context Update

**Definition**: Maintains the Blueprint Repository's accuracy and completeness. Essential for
AI effectiveness — Claude Code relies on up-to-date context in the blueprint repo.

### When to Use
- Implementing a Capability reveals spec gaps
- Architecture decision needs documenting (ADR)
- API contract changes
- New patterns or best practices emerge
- Existing docs become outdated
- Successful AI prompts should be saved for reuse

### When NOT to Use
- Changes to production code -> those are Capabilities or Enhancements

### Size / Duration
Hours to 1 day. Should accompany every Capability.

### Required Labels
- `context-update`, `documentation` (auto-applied by template)

### Where to Document
| Content Type | Location |
|--------------|----------|
| Business Requirements | `infiquetra-blueprint/requirements/` |
| Technical Specifications | `infiquetra-blueprint/specifications/` |
| Architecture Decisions | `infiquetra-blueprint/architecture/decisions/` |
| Reusable Patterns | `infiquetra-blueprint/patterns/` |
| API Contracts | `infiquetra-blueprint/specifications/api/` |
| AI Prompts | `infiquetra-blueprint/ai-prompts/` |

### Examples
**Good**:
- "Update service specification with new webhook schema"
- "Add ADR-042 for choosing Auth0 over Clerk"
- "Document error handling patterns for API services"
- "Add successful Claude prompt for API generation to library"

**Not a Context Update**:
- "Refactor the API" -> use **Enhancement** (code change, not documentation)

---

## Common Questions

**Q: Can I combine issue types in one PR?**
- Capability + Context Update (document as you build)
- Enhancement + Defect (fix while improving)
- Avoid Capability + Enhancement (scope creep)

**Q: Should I create separate issues for frontend and backend?**
Generally no. A Capability should be end-to-end. Exception: if they can truly deploy independently.

**Q: How do I handle tech debt?**
- Refactoring code -> **Enhancement**
- Documenting known limitations -> **Context Update**
- Researching migration options -> **Exploration**

**Q: What if I don't know the size up front?**
Start with an **Exploration** to research and estimate, then create the **Capability**.

**Q: Can a Capability span multiple repositories?**
Yes, if it's one deployable feature. Track all changes in one Capability issue with links
to multiple PRs.
