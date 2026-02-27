#!/usr/bin/env python3
"""
Infiquetra Documentation Generator

Automated documentation generation for Infiquetra services.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("❌ Missing pyyaml. Install with: uv pip install pyyaml")
    sys.exit(1)

# Color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
RESET = "\033[0m"


class DocsGenerator:
    """Generates documentation for Infiquetra services."""

    def __init__(self, service_name: str, output_dir: Path):
        self.service_name = service_name
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_readme(self) -> bool:
        """Generate README.md file."""
        print(f"\n{BLUE}📝 Generating README...{RESET}")

        readme_content = f"""# {self.service_name.upper()} Service

## Overview
{self.service_name.replace('-', ' ').title()} service for the Infiquetra platform.

## Features
- Feature 1
- Feature 2
- Feature 3

## Quick Start

### Prerequisites
- Python 3.12+
- AWS CLI configured

### Installation
```bash
# Clone repository
git clone https://github.com/infiquetra/{self.service_name}.git
cd {self.service_name}

# Install dependencies
uv pip install -r requirements.txt
```

### Running Locally
```bash
# Set environment variables
export AWS_REGION=us-east-1

# Run tests
pytest tests/

# Deploy
cdk deploy
```

## API Documentation
See [API.md](docs/API.md) for detailed API documentation.

## Architecture
See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for architecture overview.

## Development

### Project Structure
```
{self.service_name}/
├── src/              # Source code
├── tests/            # Test files
├── docs/             # Documentation
└── cdk/              # CDK infrastructure
```

### Testing
```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

## Deployment

### Non-Production
```bash
python3 scripts/cdk_deploy.py deploy --env nonprod
```

### Production
```bash
python3 scripts/cdk_deploy.py deploy --env prod --crq CHG#######
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Team
- **Team**: infiquetra (Chainproofers)
- **Slack**: 
- **Portfolio**: I5, Vehicle Services

## License
Copyright © 2024 your organization Inc.
"""

        readme_path = self.output_dir.parent / "README.md"
        with open(readme_path, "w") as f:
            f.write(readme_content)

        print(f"   {GREEN}✓ Created {readme_path}{RESET}")
        return True

    def generate_api_spec(self) -> bool:
        """Generate API.md specification."""
        print(f"\n{BLUE}📝 Generating API specification...{RESET}")

        api_content = f"""# {self.service_name.upper()} API

## Overview
REST API for {self.service_name.replace('-', ' ').title()} service.

**Base URL**: `https://{self.service_name}.vecu.example.com`
**Authentication**: JWT Bearer token

## Authentication
All endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### Health Check
`GET /health`

Check service health status.

**Response** (200):
```json
{{
  "status": "healthy",
  "timestamp": "2024-08-15T14:30:00Z"
}}
```

### List Resources
`GET /resources`

Retrieve list of resources.

**Query Parameters**:
- `limit` (integer, optional): Max results (default: 100)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response** (200):
```json
{{
  "resources": [
    {{
      "id": "resource-123",
      "name": "Resource Name",
      "createdAt": "2024-08-15T14:30:00Z"
    }}
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}}
```

### Get Resource
`GET /resources/{{id}}`

Retrieve a specific resource.

**Path Parameters**:
- `id` (string, required): Resource ID

**Response** (200):
```json
{{
  "id": "resource-123",
  "name": "Resource Name",
  "createdAt": "2024-08-15T14:30:00Z",
  "updatedAt": "2024-08-15T15:00:00Z"
}}
```

**Errors**:
- 404: Resource not found

### Create Resource
`POST /resources`

Create a new resource.

**Request**:
```json
{{
  "name": "Resource Name",
  "description": "Resource description"
}}
```

**Response** (201):
```json
{{
  "id": "resource-123",
  "name": "Resource Name",
  "createdAt": "2024-08-15T14:30:00Z"
}}
```

**Errors**:
- 400: Invalid request body
- 401: Unauthorized
- 409: Resource already exists

## Error Responses
All errors follow this format:
```json
{{
  "error": {{
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {{}}
  }}
}}
```

## Rate Limiting
- 100 requests per minute per user
- 1000 requests per minute per organization

## SDK Usage
```python
import requests

# Authenticate
headers = {{"Authorization": f"Bearer {{token}}"}}

# List resources
response = requests.get(
    "https://{self.service_name}.vecu.example.com/resources",
    headers=headers
)
resources = response.json()
```
"""

        api_path = self.output_dir / "API.md"
        with open(api_path, "w") as f:
            f.write(api_content)

        print(f"   {GREEN}✓ Created {api_path}{RESET}")
        return True

    def generate_architecture(self) -> bool:
        """Generate ARCHITECTURE.md file."""
        print(f"\n{BLUE}📝 Generating architecture documentation...{RESET}")

        arch_content = f"""# {self.service_name.upper()} Architecture

## Overview
This document describes the architecture of the {self.service_name.replace('-', ' ').title()} service.

## Components

### API Gateway
- REST API endpoint
- JWT authentication
- Request/response transformation
- Rate limiting

### Lambda Functions
- **Handler**: Main request handler
- **Validator**: Input validation
- **Processor**: Business logic execution

### DynamoDB
- **Table**: Primary data store
- **GSI**: Secondary indexes for queries
- **Streams**: Change data capture

### S3
- **Bucket**: Object storage
- **Versioning**: Enabled
- **Encryption**: Server-side (SSE-S3)

## Data Flow

1. **Request**: Client sends request to API Gateway
2. **Authentication**: JWT token validated
3. **Handler**: Lambda function processes request
4. **Storage**: Data written to DynamoDB
5. **Response**: JSON response returned to client

## Security

### Authentication
- JWT tokens issued by Identity Service
- Token expiration: 15 minutes
- Refresh tokens: 7 days

### Authorization
- Role-based access control (RBAC)
- Resource-level permissions
- Audit logging

### Encryption
- TLS 1.3 for data in transit
- AES-256 for data at rest
- KMS for key management

## Scalability

### Auto-Scaling
- Lambda: Concurrent executions (default: 1000)
- DynamoDB: On-demand billing mode
- API Gateway: Throttling limits

### Performance
- Average latency: <100ms
- P99 latency: <500ms
- Throughput: 1000 req/s

## Monitoring

### Metrics
- Lambda invocations, errors, duration
- API Gateway requests, errors, latency
- DynamoDB read/write capacity, throttles

### Alarms
- Lambda error rate >5%
- API Gateway 5XX errors
- DynamoDB throttling

### Logs
- CloudWatch Logs for all components
- Log retention: 30 days
- Log format: JSON

## Disaster Recovery

### Backup
- DynamoDB: Point-in-time recovery enabled
- S3: Cross-region replication
- CloudFormation: Stack versioning

### Recovery
- RTO (Recovery Time Objective): 1 hour
- RPO (Recovery Point Objective): 5 minutes

## Deployment

### CI/CD Pipeline
1. Code push triggers GitHub Actions
2. Run tests and quality checks
3. Build CDK assets
4. Deploy to non-prod environment
5. Manual promotion to production

### Environments
- **NonProd**: Development and staging
- **Prod**: Production (multi-region)

## Related Services
- **Identity Service**: User authentication
- **Transaction Service**: Transaction processing
- **Notification Service**: Event notifications
"""

        arch_path = self.output_dir / "ARCHITECTURE.md"
        with open(arch_path, "w") as f:
            f.write(arch_content)

        print(f"   {GREEN}✓ Created {arch_path}{RESET}")
        return True

    def validate(self) -> int:
        """Validate documentation completeness."""
        print(f"\n{BLUE}🔍 Validating documentation...{RESET}\n")

        score = 0
        total = 5

        # Check README
        readme_path = self.output_dir.parent / "README.md"
        if readme_path.exists():
            print(f"{GREEN}✓ README.md exists{RESET}")
            score += 1
        else:
            print(f"{RED}✗ README.md missing{RESET}")

        # Check API docs
        api_path = self.output_dir / "API.md"
        if api_path.exists():
            print(f"{GREEN}✓ API.md exists{RESET}")
            score += 1
        else:
            print(f"{RED}✗ API.md missing{RESET}")

        # Check Architecture docs
        arch_path = self.output_dir / "ARCHITECTURE.md"
        if arch_path.exists():
            print(f"{GREEN}✓ ARCHITECTURE.md exists{RESET}")
            score += 1
        else:
            print(f"{RED}✗ ARCHITECTURE.md missing{RESET}")

        # Check images directory
        images_dir = self.output_dir / "images"
        if images_dir.exists():
            print(f"{GREEN}✓ Images directory exists{RESET}")
            score += 1
        else:
            print(f"{YELLOW}⚠️  Images directory missing{RESET}")

        # Check integration docs
        integration_path = self.output_dir / "INTEGRATION.md"
        if integration_path.exists():
            print(f"{GREEN}✓ INTEGRATION.md exists{RESET}")
            score += 1
        else:
            print(f"{YELLOW}⚠️  INTEGRATION.md missing{RESET}")

        final_score = int((score / total) * 100)
        print(f"\n{BLUE}📊 Documentation Score: {final_score}/100{RESET}")

        return final_score


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Infiquetra Documentation Generator")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate documentation")
    gen_parser.add_argument("--all", action="store_true", help="Generate all documentation")
    gen_parser.add_argument("--type", choices=["readme", "api-spec", "architecture"], help="Documentation type")
    gen_parser.add_argument("--service", default="service", help="Service name")
    gen_parser.add_argument("--output", default="docs", help="Output directory")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate documentation")
    val_parser.add_argument("--service", default="service", help="Service name")
    val_parser.add_argument("--output", default="docs", help="Output directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Print header
    print(f"\n{BOLD}🚀 Infiquetra Documentation Generator{RESET}")
    print(f"{'═' * 45}")

    output_dir = Path(args.output)
    generator = DocsGenerator(args.service, output_dir)

    if args.command == "generate":
        if args.all:
            generator.generate_readme()
            generator.generate_api_spec()
            generator.generate_architecture()
            print(f"\n{GREEN}✅ All documentation generated!{RESET}")
        elif args.type == "readme":
            generator.generate_readme()
        elif args.type == "api-spec":
            generator.generate_api_spec()
        elif args.type == "architecture":
            generator.generate_architecture()

    elif args.command == "validate":
        score = generator.validate()
        sys.exit(0 if score >= 80 else 1)


if __name__ == "__main__":
    main()
