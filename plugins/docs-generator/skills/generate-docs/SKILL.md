---
name: generate-docs
description: Generate comprehensive documentation for Infiquetra services (README, API specs, architecture diagrams)
when_to_use: |
  Use this skill when the user wants to:
  - Generate documentation
  - Create README file
  - Generate API specification
  - Create architecture documentation
  - Generate integration guides
---

# Documentation Generation Guide

You are helping the user generate comprehensive documentation for their Infiquetra service.

## Documentation Types

### README.md
Service overview, setup instructions, usage examples

### API Specification
OpenAPI/Swagger specification for REST APIs

### Architecture Diagrams
System architecture, data flow, deployment diagrams

### Integration Guides
How to integrate with other Infiquetra services

## Generation Process

```bash
python plugins/docs-generator/skills/generate-docs/scripts/docs_generator.py \
  --type all \
  --service-name "wallet-service"
```

Options:
- `--type readme` - Generate README.md only
- `--type api-spec` - Generate OpenAPI specification
- `--type architecture` - Generate architecture diagrams
- `--type integration` - Generate integration guide
- `--type all` - Generate all documentation

## Output Structure

```
docs/
├── README.md
├── api/
│   └── openapi.yaml
├── architecture/
│   ├── system-architecture.png
│   ├── data-flow.png
│   └── deployment.png
└── integration/
    └── integration-guide.md
```

## README Template

Generated README includes:
- Service overview and purpose
- Prerequisites and dependencies
- Installation and setup
- Configuration options
- Usage examples
- API endpoints
- Environment variables
- Troubleshooting
- Contributing guidelines
- License information

## API Specification

OpenAPI 3.0 specification with:
- Endpoint definitions
- Request/response schemas
- Authentication methods
- Error responses
- Example requests

## Architecture Diagrams

Using Python diagrams library:
- AWS service diagram
- Data flow diagram
- Deployment diagram
- Component interactions

## Best Practices

1. **Keep documentation updated** - Regenerate after major changes
2. **Cross-reference, don't duplicate** - Link to canonical sources
3. **Include examples** - Actual working code samples
4. **Document errors** - Common issues and solutions
5. **Version documentation** - Match service version

## Next Steps

After generation:
1. Review generated documentation for accuracy
2. Add service-specific examples
3. Commit documentation to repository
4. Update documentation portal links if applicable
