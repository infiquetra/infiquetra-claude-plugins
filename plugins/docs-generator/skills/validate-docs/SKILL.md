---
name: validate-docs
description: Validate documentation completeness and quality
when_to_use: |
  Use this skill when the user wants to:
  - Validate documentation
  - Check doc completeness
  - Calculate documentation score
  - Identify missing documentation
---

# Documentation Validation Guide

You are helping the user validate documentation completeness and quality.

## Validation Checks

### Completeness Check
- README.md exists
- API specification exists
- Architecture diagrams exist
- Integration guide exists
- All required sections present

### Quality Check
- Links are valid
- Code examples work
- Diagrams are up-to-date
- No broken references

### Documentation Score

Calculated from:
- Required sections present (40%)
- Code examples included (20%)
- Diagrams current (20%)
- Links valid (10%)
- Formatting correct (10%)

Target: 80%+ for production services

## Validation Command

```bash
python plugins/docs-generator/skills/generate-docs/scripts/docs_generator.py validate
```

Output:
```
Documentation Score: 85%

✓ README.md present
✓ API specification present
✓ Architecture diagrams present
✗ Integration guide missing
✓ All required README sections present
✓ Code examples included
⚠ 2 broken links found
```

## Remediation

For missing documentation:
- Run `generate-docs` to create missing files
- Update outdated content
- Fix broken links
- Add missing examples
