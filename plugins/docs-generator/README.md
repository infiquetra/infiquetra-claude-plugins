# docs-generator

Automated documentation generation for Infiquetra services with diagrams and API specs.

## Overview

The `docs-generator` skill automates the creation of standardized documentation for Infiquetra services, including API specifications, architecture diagrams, integration guides, and README files. This ensures consistent documentation across all Infiquetra services while saving significant developer time.

**Key Features:**
- **OpenAPI spec generation** from Lambda handlers and FastAPI routes
- **Architecture diagrams** using Python diagrams library
- **README templates** with Infiquetra standards
- **Integration guides** with code examples
- **Sequence diagrams** using mermaid syntax
- **Cross-reference management** for related services
- **Markdown formatting** with proper structure

## Usage

```bash
# Generate all documentation for current service
python3 scripts/docs_generator.py generate --all

# Generate specific documentation types
python3 scripts/docs_generator.py generate --type api-spec
python3 scripts/docs_generator.py generate --type architecture
python3 scripts/docs_generator.py generate --type readme

# Generate with service context
python3 scripts/docs_generator.py generate --service wallet --type api-spec

# Update existing documentation
python3 scripts/docs_generator.py update --file docs/API.md

# Validate documentation completeness
python3 scripts/docs_generator.py validate

# Generate diagrams only
python3 scripts/docs_generator.py diagrams --output docs/images/
```

## Prerequisites

### Required Tools
- Python 3.12+
- `diagrams` library for architecture diagrams
- `pyyaml` for configuration
- `jinja2` for templates

### Installation
```bash
# Using uv (recommended)
uv pip install diagrams pyyaml jinja2 graphviz

# Using pip
pip install diagrams pyyaml jinja2

# Install graphviz for diagram rendering
# macOS: brew install graphviz
# Ubuntu: apt-get install graphviz
```

### Project Structure
```
project/
├── docs/                    # Generated documentation
│   ├── API.md              # API specification
│   ├── ARCHITECTURE.md     # Architecture overview
│   ├── INTEGRATION.md      # Integration guide
│   └── images/             # Generated diagrams
│       ├── architecture.png
│       └── sequence.png
├── src/                    # Source code to document
└── .docs-config.yml        # Documentation configuration
```

## Implementation

The skill is implemented in `scripts/docs_generator.py` and provides:

### OpenAPI Spec Generation
Analyzes Lambda handlers and FastAPI routes to generate OpenAPI 3.0 specifications:
- Endpoint discovery from code
- Request/response schema extraction
- Authentication requirements
- Error responses

### Architecture Diagrams
Uses Python diagrams to create visual representations:
- AWS architecture diagrams
- Service interaction diagrams
- Data flow diagrams
- Infrastructure topology

### README Generation
Creates standardized README files with:
- Service overview and purpose
- Quick start guide
- API documentation links
- Development setup
- Deployment instructions
- Contributing guidelines

### Integration Guides
Documents how to integrate with the service:
- Authentication setup
- Request/response examples
- Error handling
- Rate limits
- SDK usage

## Examples

### Example 1: Generate All Documentation
```bash
$ python3 scripts/docs_generator.py generate --all --service wallet

🚀 Infiquetra Documentation Generator
═════════════════════════════════════════

🔍 Analyzing wallet service...
   Source: src/
   Handlers: 12 Lambda functions
   Endpoints: 8 API routes

📝 Generating documentation...

[1/5] API Specification .......................... ✓ (2.3s)
   Created: docs/API.md
   Endpoints: 8
   Schemas: 15

[2/5] Architecture Diagram ....................... ✓ (4.1s)
   Created: docs/images/architecture.png
   Components: AWS Lambda, DynamoDB, API Gateway

[3/5] README ...................................... ✓ (1.2s)
   Created: README.md
   Sections: 8

[4/5] Integration Guide .......................... ✓ (1.8s)
   Created: docs/INTEGRATION.md
   Examples: 5

[5/5] Sequence Diagrams .......................... ✓ (2.5s)
   Created: docs/images/auth-flow.png
   Created: docs/images/token-refresh.png

✅ Documentation generation complete!
   Files created: 7
   Diagrams: 3
   Total size: 245 KB
```

### Example 2: Generate API Specification
```bash
$ python3 scripts/docs_generator.py generate --type api-spec --service wallet

📝 Generating API Specification...

🔍 Discovering endpoints...
   Found: 8 API routes
   Authentication: JWT Bearer token

📋 Extracting schemas...
   Request schemas: 8
   Response schemas: 15
   Error schemas: 4

✍️  Writing OpenAPI spec...
   Format: OpenAPI 3.0.3
   Output: docs/API.md

✅ API specification generated!
   View: docs/API.md
   Swagger UI: https://editor.swagger.io/
```

**Generated API.md**:
```markdown
# Wallet Service API

## Overview
Digital wallet service for vehicle custody platform.

**Base URL**: `https://wallet.vecu.example.com`
**Authentication**: JWT Bearer token

## Endpoints

### Create Wallet
`POST /wallets`

Creates a new digital wallet for a user.

**Request**:
```json
{
  "userId": "string",
  "walletType": "custodial" | "non-custodial"
}
```

**Response** (201):
```json
{
  "walletId": "string",
  "userId": "string",
  "createdAt": "2024-08-15T14:30:00Z"
}
```

**Errors**:
- 400: Invalid request body
- 401: Unauthorized
- 409: Wallet already exists
```

### Example 3: Generate Architecture Diagram
```bash
$ python3 scripts/docs_generator.py diagrams --service wallet

🎨 Generating architecture diagrams...

📐 Creating AWS architecture diagram...
   Components:
   - API Gateway (REST API)
   - Lambda Functions (3)
   - DynamoDB Table
   - S3 Bucket
   - CloudWatch Logs

   ✓ Created: docs/images/architecture.png

📐 Creating data flow diagram...
   Flows:
   - User → API Gateway → Lambda
   - Lambda → DynamoDB
   - Lambda → S3

   ✓ Created: docs/images/data-flow.png

✅ Diagrams generated!
   Location: docs/images/
```

**Generated architecture.png** shows:
```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│  API Gateway     │
└────────┬─────────┘
         │
         ▼
┌─────────────────────┐
│  Lambda Function    │
└──────┬──────┬───────┘
       │      │
       ▼      ▼
┌──────────┐ ┌─────────┐
│ DynamoDB │ │   S3    │
└──────────┘ └─────────┘
```

### Example 4: Validate Documentation
```bash
$ python3 scripts/docs_generator.py validate

🔍 Validating documentation completeness...

✓ README.md exists and is complete
✓ API.md exists with all endpoints documented
✓ ARCHITECTURE.md exists
✗ INTEGRATION.md missing or incomplete
  Missing: Authentication examples
  Missing: Error handling guide
✓ Architecture diagram exists
✗ Sequence diagrams missing

📊 Documentation Score: 75/100

Recommendations:
- Add authentication examples to INTEGRATION.md
- Add error handling guide
- Generate sequence diagrams for key flows
```

## Integration with Infiquetra Workflows

### During Development
```bash
# Update docs after adding new endpoints
python3 scripts/docs_generator.py update --type api-spec

# Regenerate diagrams after infrastructure changes
python3 scripts/docs_generator.py diagrams
```

### Pre-Commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash
python3 scripts/docs_generator.py validate

if [ $? -ne 0 ]; then
    echo "⚠️  Documentation incomplete. Run 'generate --all' to update."
fi
```

### GitHub Actions
```yaml
# .github/workflows/docs.yml
- name: Generate Documentation
  run: |
    python3 scripts/docs_generator.py generate --all

- name: Commit Documentation
  run: |
    git add docs/
    git commit -m "docs: auto-generate documentation"
    git push
```

## Configuration

### .docs-config.yml
```yaml
service:
  name: wallet-service
  description: Digital wallet service for vehicle custody
  base_url: https://wallet.vecu.example.com

documentation:
  output_dir: docs
  diagrams_dir: docs/images

  templates:
    readme: templates/README.md.j2
    api: templates/API.md.j2
    integration: templates/INTEGRATION.md.j2

api:
  openapi_version: "3.0.3"
  authentication: JWT Bearer

diagrams:
  format: png
  include:
    - architecture
    - data-flow
    - auth-sequence

cross_references:
  - name: Identity Service
    url: https://github.com/infiquetra/idv
  - name: Transaction Service
    url: https://github.com/infiquetra/transaction-service
```

## Documentation Templates

### README Template Structure
```markdown
# {service_name}

{service_description}

## Features
- Feature 1
- Feature 2

## Quick Start
{quick_start_guide}

## API Documentation
See [API.md](docs/API.md)

## Architecture
See [ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Development
{development_setup}

## Deployment
{deployment_guide}

## Testing
{testing_guide}

## Contributing
{contributing_guide}
```

## Error Handling

The generator handles:
- **Missing source files**: Clear warnings about what's missing
- **Invalid configuration**: Validates .docs-config.yml
- **Diagram generation failures**: Falls back to text-based diagrams
- **Template errors**: Provides specific line numbers
- **Cross-reference failures**: Warns about broken links

## Advanced Features

### Multi-Service Documentation
Generate cross-service documentation:
```bash
# Generate integration guide for multiple services
python3 scripts/docs_generator.py generate --services wallet,identity,transaction --type integration
```

### Custom Templates
```bash
# Use custom Jinja2 templates
python3 scripts/docs_generator.py generate --template custom-readme.md.j2
```

### Diagram Customization
```bash
# Generate diagrams with custom styling
python3 scripts/docs_generator.py diagrams --style vecu --output docs/images/
```

## Notes

- Documentation is generated from code comments and type hints
- Diagrams require Graphviz installed system-wide
- OpenAPI specs can be imported into Postman or Swagger UI
- README files follow Infiquetra documentation standards
- Cross-references maintain single source of truth principle

## Infiquetra Documentation Standards

- **Every service** must have README.md, API.md, and ARCHITECTURE.md
- **Diagrams** should be PNG format, max 2MB
- **API specs** must use OpenAPI 3.0+ format
- **Code examples** must use actual endpoints (not localhost)
- **Cross-references** should link to canonical docs, not duplicate content

## Troubleshooting

### "graphviz not found"
```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Verify installation
dot -V
```

### "Template rendering failed"
Check Jinja2 template syntax:
```bash
python3 scripts/docs_generator.py validate --template README.md.j2
```

### "Endpoint discovery failed"
Ensure Lambda handlers follow standard patterns:
```python
def handler(event, context):
    """
    Handle wallet creation requests.

    POST /wallets
    """
    # Handler code
```

## Related Resources

- [Infiquetra Documentation Guide](https://github.com/infiquetra/infiquetra-claude-plugins/docs)
- [Python Diagrams Library](https://diagrams.mingrammer.com/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
