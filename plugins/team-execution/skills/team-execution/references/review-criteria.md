# Review Criteria — team-execution

All reviewers score 5 dimensions (0-10 each). Overall = average of 5 dimensions.

Pass threshold: **Overall >= 9.0 AND no dimension < 7.0**

If any reviewer scores < 9.0, their fix requests are routed to workers for revision.
Maximum 3 review-revise cycles; then proceed with the best available version.

---

## Devil's Advocate Rubric

The Devil's Advocate focuses on **assumption validity, edge cases, failure modes, scope, and alternatives**.

### Dimension 1: Assumption Validity (0-10)

| Score | Definition |
|-------|------------|
| 10 | All assumptions are explicitly stated and verifiably correct in this codebase context |
| 9 | 1-2 minor assumptions that are reasonable but unstated |
| 7-8 | A load-bearing assumption that may not hold in edge cases |
| 5-6 | An assumption that is likely wrong or untested |
| < 5 | Multiple incorrect assumptions; implementation will fail in common scenarios |

### Dimension 2: Edge Case Coverage (0-10)

| Score | Definition |
|-------|------------|
| 10 | All meaningful boundary conditions handled or explicitly out-of-scope |
| 9 | 1-2 minor edge cases unhandled but unlikely to be hit in practice |
| 7-8 | A notable edge case (empty input, concurrent modification, timeout) unhandled |
| 5-6 | Multiple edge cases unhandled; would cause runtime failures |
| < 5 | Common edge cases ignored; implementation not production-safe |

### Dimension 3: Failure Mode Analysis (0-10)

| Score | Definition |
|-------|------------|
| 10 | All failure paths handled gracefully; errors are informative |
| 9 | 1-2 failure paths with generic error handling |
| 7-8 | A meaningful failure path with no error handling (swallowed exception, unhandled state) |
| 5-6 | Multiple unhandled failures; silent failures present |
| < 5 | No meaningful error handling; implementation will fail silently |

### Dimension 4: Scope Creep Risk (0-10)

| Score | Definition |
|-------|------------|
| 10 | Implementation does exactly what the plan asked; no gold-plating |
| 9 | 1-2 minor additions that are harmless but unnecessary |
| 7-8 | A meaningful addition that creates maintenance burden |
| 5-6 | Significant scope beyond the plan; implementation is harder to maintain |
| < 5 | Implementation has substantially more scope than needed |

### Dimension 5: Alternatives Considered (0-10)

| Score | Definition |
|-------|------------|
| 10 | Clear evidence that alternatives were weighed and the chosen approach is defensible |
| 9 | Approach is reasonable; 1-2 obvious alternatives not mentioned but unlikely to be better |
| 7-8 | A simpler or more idiomatic approach exists that wasn't considered |
| 5-6 | Approach is over-engineered vs. a simpler alternative that would work equally well |
| < 5 | Implementation introduces unnecessary complexity over a much simpler known pattern |

---

## Security Reviewer Rubric

The Security Reviewer focuses on **auth/authZ, secrets, input validation, PII, and dependencies**.

### Dimension 1: Auth & AuthZ (0-10)

| Score | Definition |
|-------|------------|
| 10 | All endpoints/mutations properly authenticated AND authorized; principle of least privilege followed |
| 9 | Authentication complete; 1 minor authZ gap in a low-risk area |
| 7-8 | AuthZ missing on an endpoint or over-permissive role |
| 5-6 | Authentication missing on an endpoint or significant privilege escalation risk |
| < 5 | Auth fundamentally broken or bypassed; **BLOCKING** |

### Dimension 2: Secrets Management (0-10)

| Score | Definition |
|-------|------------|
| 10 | All secrets via a secrets manager or env vars; no hardcoded values; no logging of secrets |
| 9 | 1 minor config value (non-sensitive) passed as env var without secrets management |
| 7-8 | A sensitive value in env var format instead of a secrets manager |
| 5-6 | A secret in a config file that could be committed |
| < 5 | Hardcoded secret in source code; **BLOCKING** |

### Dimension 3: Input Validation & Injection (0-10)

| Score | Definition |
|-------|------------|
| 10 | All external inputs validated; parameterized queries used; no injection vectors |
| 9 | 1-2 minor validation gaps on low-risk inputs |
| 7-8 | A meaningful validation gap on a user-controlled field |
| 5-6 | SQL/NoSQL/command injection vector present |
| < 5 | Direct user input in queries or shell commands without sanitization |

### Dimension 4: PII / Data Privacy (0-10)

| Score | Definition |
|-------|------------|
| 10 | PII identified, minimized, encrypted at rest, with retention defined |
| 9 | PII handling largely correct; 1 minor gap (e.g., retention period not explicitly set) |
| 7-8 | PII field not encrypted or logged unnecessarily |
| 5-6 | PII in logs, unencrypted at rest, or shared without consent mechanism |
| < 5 | PII fundamentally mishandled |

### Dimension 5: Dependency & Supply Chain (0-10)

| Score | Definition |
|-------|------------|
| 10 | All deps necessary, pinned to exact versions, no known CVEs |
| 9 | Dependencies pinned; 1 non-critical CVE in a low-impact dependency |
| 7-8 | A dependency not pinned to exact version or with a moderate CVE |
| 5-6 | An unnecessary dependency or a dependency with a significant CVE |
| < 5 | Dependency with critical CVE or from an unvetted source |

---

## Architecture Reviewer Rubric

The Architecture Reviewer focuses on **design patterns, separation of concerns, dependency direction,
convention adherence, and architecture documentation coverage** across the codebase.

### Dimension 1: Pattern Consistency (0-10)

| Score | Definition |
|-------|------------|
| 10 | New code follows the established patterns in neighboring files and the broader codebase |
| 9 | 1 minor deviation from existing patterns with a reasonable implicit rationale |
| 7-8 | A meaningful pattern deviation without explicit rationale |
| 5-6 | A pattern contradiction in a core area of the codebase |
| < 5 | Multiple pattern contradictions; implementation would create architectural inconsistency |

### Dimension 2: Separation of Concerns (0-10)

| Score | Definition |
|-------|------------|
| 10 | Each module/class/function has a single, clear responsibility; no blending of layers |
| 9 | 1 minor case of mixed concerns that is unlikely to grow into a problem |
| 7-8 | A meaningful mixing of concerns (e.g., business logic in a data layer) |
| 5-6 | Multiple layers blended; hard to change one without affecting others |
| < 5 | No discernible separation of concerns; monolithic logic scattered throughout |

### Dimension 3: Dependency Direction (0-10)

| Score | Definition |
|-------|------------|
| 10 | Dependencies flow in the correct direction; no circular dependencies; abstractions used at boundaries |
| 9 | 1 minor dependency that goes "the wrong way" but is unlikely to create problems |
| 7-8 | A meaningful reverse dependency or tight coupling that will impede future changes |
| 5-6 | Multiple reverse dependencies; circular imports or coupling across unrelated modules |
| < 5 | Dependency structure is fundamentally inverted or circular |

### Dimension 4: Convention Adherence (0-10)

| Score | Definition |
|-------|------------|
| 10 | Naming, file structure, API conventions, and project-specific idioms all followed consistently |
| 9 | 1-2 minor naming or convention lapses that are harmless |
| 7-8 | A meaningful convention violation (wrong naming pattern, wrong file location, wrong API shape) |
| 5-6 | Multiple convention violations; new code would confuse a reader familiar with the rest of the codebase |
| < 5 | Implementation ignores the project's established conventions throughout |

### Dimension 5: Architecture Documentation Coverage (0-10)

| Score | Definition |
|-------|------------|
| 10 | Significant new patterns or decisions are documented; existing docs updated if changed |
| 9 | 1 minor undocumented choice that is self-evident from the code |
| 7-8 | A meaningful architectural decision made without documentation |
| 5-6 | A significant cross-cutting decision with no documentation, making it hard for future developers |
| < 5 | Major new patterns introduced with no documentation; future maintainers would have no context |

---

## Optional Reviewer Rubrics

### Code Quality Reviewer (5 dimensions)
1. **DRY / Duplication** — Is logic duplicated? Are abstractions appropriate?
2. **Complexity & Readability** — Can a new team member understand this in < 5 minutes?
3. **Pattern Consistency** — Does the code follow existing patterns in this codebase?
4. **Naming & Abstraction** — Are names meaningful? Are abstractions at the right level?
5. **Error Handling Quality** — Are errors handled consistently and informatively?

### Privacy Reviewer (5 dimensions)
1. **Data Minimization** — Is only the necessary data collected and stored?
2. **Consent & Purpose Limitation** — Is data used only for stated purposes?
3. **PII Handling & Classification** — Is PII classified and protected appropriately?
4. **Retention & Deletion** — Are retention periods defined? Is deletion implemented?
5. **Cross-Border & Compliance** — Are data residency and regulatory requirements met?

### Infra Reviewer (5 dimensions)
1. **IaC Correctness** — Is the infrastructure code syntactically and logically correct?
2. **IAM Least Privilege** — Are IAM roles/policies scoped to minimum required permissions?
3. **Cost Awareness** — Are resource configurations cost-appropriate? Any cost bombs?
4. **Resilience** — Are single points of failure avoided where required?
5. **Observability** — Are metrics/alarms/logs configured for new resources?

### API Reviewer (5 dimensions)
1. **API Contract Correctness** — Is the API consistent with stated contracts/schemas?
2. **Versioning & Deprecation** — Are breaking changes versioned? Are deprecations communicated?
3. **Error Response Design** — Are error codes meaningful and consistent with platform standards?
4. **Idempotency** — Are mutation endpoints idempotent where required?
5. **SDK Impact** — How does this API change affect existing SDK consumers?

### Testing Reviewer (5 dimensions)
1. **Coverage Adequacy** — Are new code paths covered by tests?
2. **Test Quality** — Do tests actually validate behavior or just exercise code paths?
3. **Edge Case Testing** — Are boundary conditions and error paths tested?
4. **Mock/Fixture Appropriateness** — Are mocks scoped correctly? Are integration tests real?
5. **Test Maintainability** — Will tests be easy to update when implementation changes?

### Clarity Reviewer (5 dimensions)
1. **Structure & Navigation** — Can the reader find what they need without reading everything?
2. **Precision of Language** — Are terms used consistently? Is ambiguity eliminated?
3. **Completeness** — Are there unexplained gaps that force the reader to guess?
4. **Understandability** — Is the content pitched at the right level for the intended audience?
5. **Actionability** — Does the reader know what to do next after reading?

### AI Usefulness Reviewer (5 dimensions)
1. **Context Completeness** — Does the AI have everything it needs to act without follow-up questions?
2. **Unambiguous Acceptance Criteria** — Are success conditions explicit and verifiable?
3. **Example Coverage** — Are inputs, outputs, and edge cases shown with examples?
4. **Constraint Explicitness** — Is it clear what NOT to do? Are guardrails stated?
5. **Machine-Parseable Structure** — Are headers, lists, and code blocks used instead of prose walls?
