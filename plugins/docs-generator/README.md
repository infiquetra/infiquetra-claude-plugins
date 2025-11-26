# Documentation Generator

Generate README, API specifications, and architecture documentation for your projects.

## Features

- **README Generation**: Project overview with standard sections
- **API Spec Generation**: REST API documentation with examples
- **Architecture Docs**: System architecture overview
- **Validation**: Check documentation completeness

## Installation

This plugin is part of the infiquetra-claude-plugins collection.

```bash
# Clone the plugins repository
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git ~/.claude/plugins/infiquetra
```

## Usage

### Generate All Documentation

```bash
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate \
    --all \
    --service my-service \
    --output docs
```

### Generate Specific Documentation

```bash
# README only
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate \
    --type readme \
    --service my-service

# API spec only
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate \
    --type api-spec \
    --service my-service

# Architecture only
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate \
    --type architecture \
    --service my-service
```

### Validate Documentation

```bash
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py validate \
    --service my-service \
    --output docs
```

## Options

### Generate Command

| Option | Default | Description |
|--------|---------|-------------|
| `--all` | false | Generate all documentation types |
| `--type` | - | Specific doc type: readme, api-spec, architecture |
| `--service` | my-service | Service name for documentation |
| `--output` | docs | Output directory |

### Validate Command

| Option | Default | Description |
|--------|---------|-------------|
| `--service` | my-service | Service name |
| `--output` | docs | Documentation directory to validate |

## Generated Files

| File | Location | Description |
|------|----------|-------------|
| README.md | Project root | Project overview |
| API.md | docs/ | REST API specification |
| ARCHITECTURE.md | docs/ | System architecture |

## Example Output

```
Documentation Generator
═════════════════════════════════════════════

Generating README...
   ✓ Created /project/README.md

Generating API specification...
   ✓ Created /project/docs/API.md

Generating architecture documentation...
   ✓ Created /project/docs/ARCHITECTURE.md

All documentation generated!
```

## Customization

The generated templates are designed as starting points. After generation, customize:

- **README.md**: Add specific features, installation steps, configuration
- **API.md**: Add your actual endpoints, request/response examples
- **ARCHITECTURE.md**: Add your specific components, data flows, diagrams

## Requirements

- Python 3.12+
- pyyaml

## License

MIT
