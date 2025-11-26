#!/usr/bin/env python3
"""
Documentation Generator

Automated documentation generation for projects.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("Missing pyyaml. Install with: uv pip install pyyaml")
    sys.exit(1)

# Color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
RESET = "\033[0m"


class DocsGenerator:
    """Generates documentation for projects."""

    def __init__(self, service_name: str, output_dir: Path):
        self.service_name = service_name
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_readme(self) -> bool:
        """Generate README.md file."""
        print(f"\n{BLUE}Generating README...{RESET}")

        readme_content = f"""# {self.service_name.replace('-', ' ').title()}

## Overview

{self.service_name.replace('-', ' ').title()} service.

## Features

- Feature 1
- Feature 2
- Feature 3

## Quick Start

### Prerequisites

- Python 3.12+
- uv (recommended) or pip

### Installation

```bash
# Clone repository
git clone <repository-url>
cd {self.service_name}

# Install dependencies
uv pip install -e ".[dev]"
```

### Running Locally

```bash
# Run tests
pytest

# Run application
python -m {self.service_name.replace('-', '_')}
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
└── scripts/          # Utility scripts
```

### Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy src/

# Security scanning
bandit -r src/
```

## Deployment

### Development

```bash
# Deploy to development environment
./scripts/deploy.sh dev
```

### Production

```bash
# Deploy to production
./scripts/deploy.sh prod
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT
"""

        readme_path = self.output_dir.parent / "README.md"
        with open(readme_path, "w") as f:
            f.write(readme_content)

        print(f"   {GREEN}✓ Created {readme_path}{RESET}")
        return True

    def generate_api_spec(self) -> bool:
        """Generate API.md specification."""
        print(f"\n{BLUE}Generating API specification...{RESET}")

        api_content = f"""# {self.service_name.replace('-', ' ').title()} API

## Overview

REST API for {self.service_name.replace('-', ' ').title()} service.

**Base URL**: `https://api.example.com/{self.service_name}`
**Authentication**: Bearer token

## Authentication

All endpoints require authentication. Include the token in the Authorization header:

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
  "timestamp": "2024-01-15T14:30:00Z"
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
      "createdAt": "2024-01-15T14:30:00Z"
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
  "createdAt": "2024-01-15T14:30:00Z",
  "updatedAt": "2024-01-15T15:00:00Z"
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
  "createdAt": "2024-01-15T14:30:00Z"
}}
```

**Errors**:
- 400: Invalid request body
- 401: Unauthorized
- 409: Resource already exists

### Update Resource

`PUT /resources/{{id}}`

Update an existing resource.

**Path Parameters**:
- `id` (string, required): Resource ID

**Request**:
```json
{{
  "name": "Updated Name",
  "description": "Updated description"
}}
```

**Response** (200):
```json
{{
  "id": "resource-123",
  "name": "Updated Name",
  "updatedAt": "2024-01-15T16:00:00Z"
}}
```

### Delete Resource

`DELETE /resources/{{id}}`

Delete a resource.

**Path Parameters**:
- `id` (string, required): Resource ID

**Response** (204): No content

**Errors**:
- 404: Resource not found

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

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Request body is invalid |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `INTERNAL_ERROR` | 500 | Server error |

## Rate Limiting

- 100 requests per minute per user
- 1000 requests per minute per API key

## SDK Usage

### Python

```python
import requests

# Authentication
headers = {{"Authorization": f"Bearer {{token}}"}}

# List resources
response = requests.get(
    "https://api.example.com/{self.service_name}/resources",
    headers=headers
)
resources = response.json()

# Create resource
response = requests.post(
    "https://api.example.com/{self.service_name}/resources",
    headers=headers,
    json={{"name": "New Resource"}}
)
new_resource = response.json()
```

### cURL

```bash
# List resources
curl -H "Authorization: Bearer $TOKEN" \\
  https://api.example.com/{self.service_name}/resources

# Create resource
curl -X POST -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"name": "New Resource"}}' \\
  https://api.example.com/{self.service_name}/resources
```
"""

        api_path = self.output_dir / "API.md"
        with open(api_path, "w") as f:
            f.write(api_content)

        print(f"   {GREEN}✓ Created {api_path}{RESET}")
        return True

    def generate_architecture(self) -> bool:
        """Generate ARCHITECTURE.md file."""
        print(f"\n{BLUE}Generating architecture documentation...{RESET}")

        arch_content = f"""# {self.service_name.replace('-', ' ').title()} Architecture

## Overview

This document describes the architecture of the {self.service_name.replace('-', ' ').title()} service.

## High-Level Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   API GW    │────▶│   Service   │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  Database   │
                                        └─────────────┘
```

## Components

### API Layer

- **API Gateway**: Request routing, authentication, rate limiting
- **REST Endpoints**: Standard CRUD operations
- **Input Validation**: Request body and parameter validation

### Business Logic

- **Service Layer**: Core business logic
- **Domain Models**: Data structures and entities
- **Validators**: Business rule validation

### Data Layer

- **Repository**: Data access abstraction
- **Database**: Primary data storage
- **Cache**: Performance optimization (optional)

## Data Flow

1. **Request**: Client sends HTTP request
2. **Authentication**: Token validated
3. **Validation**: Request payload validated
4. **Processing**: Business logic executed
5. **Storage**: Data persisted
6. **Response**: JSON response returned

## Security

### Authentication

- Token-based authentication
- Token expiration with refresh capability

### Authorization

- Role-based access control (RBAC)
- Resource-level permissions

### Data Protection

- TLS encryption in transit
- Encryption at rest for sensitive data

## Scalability

### Horizontal Scaling

- Stateless service design
- Load balancer distribution
- Auto-scaling based on demand

### Performance

- Database connection pooling
- Caching for frequently accessed data
- Async processing for long-running tasks

## Monitoring

### Metrics

- Request latency (p50, p95, p99)
- Error rates
- Throughput (requests/second)

### Logging

- Structured JSON logging
- Request tracing with correlation IDs
- Error tracking and alerting

### Health Checks

- `/health` endpoint for load balancers
- Dependency health verification

## Deployment

### Environments

- **Development**: For active development
- **Staging**: Pre-production testing
- **Production**: Live environment

### CI/CD Pipeline

1. Code push triggers CI pipeline
2. Run tests and quality checks
3. Build artifacts
4. Deploy to environment
5. Run smoke tests

## Related Services

- **Auth Service**: User authentication
- **Notification Service**: Event notifications
- **Logging Service**: Centralized logging

## Future Considerations

- [ ] Add caching layer
- [ ] Implement event sourcing
- [ ] Add GraphQL endpoint
- [ ] Multi-region deployment
"""

        arch_path = self.output_dir / "ARCHITECTURE.md"
        with open(arch_path, "w") as f:
            f.write(arch_content)

        print(f"   {GREEN}✓ Created {arch_path}{RESET}")
        return True

    def validate(self) -> int:
        """Validate documentation completeness."""
        print(f"\n{BLUE}Validating documentation...{RESET}\n")

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
            print(f"{YELLOW}Images directory missing (optional){RESET}")

        # Check integration docs
        integration_path = self.output_dir / "INTEGRATION.md"
        if integration_path.exists():
            print(f"{GREEN}✓ INTEGRATION.md exists{RESET}")
            score += 1
        else:
            print(f"{YELLOW}INTEGRATION.md missing (optional){RESET}")

        final_score = int((score / total) * 100)
        print(f"\n{BLUE}Documentation Score: {final_score}/100{RESET}")

        return final_score


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Documentation Generator")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate documentation")
    gen_parser.add_argument("--all", action="store_true", help="Generate all documentation")
    gen_parser.add_argument("--type", choices=["readme", "api-spec", "architecture"], help="Documentation type")
    gen_parser.add_argument("--service", default="my-service", help="Service name")
    gen_parser.add_argument("--output", default="docs", help="Output directory")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate documentation")
    val_parser.add_argument("--service", default="my-service", help="Service name")
    val_parser.add_argument("--output", default="docs", help="Output directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Print header
    print(f"\n{BOLD}Documentation Generator{RESET}")
    print(f"{'═' * 45}")

    output_dir = Path(args.output)
    generator = DocsGenerator(args.service, output_dir)

    if args.command == "generate":
        if args.all:
            generator.generate_readme()
            generator.generate_api_spec()
            generator.generate_architecture()
            print(f"\n{GREEN}All documentation generated!{RESET}")
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
