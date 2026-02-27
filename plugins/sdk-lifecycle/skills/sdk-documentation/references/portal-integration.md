# documentation portal Integration

Publishing SDK documentation to Infiquetra documentation portal.

## Configuration

Create `.documentation portal.yml`:
```yaml
name: sdk-name
version: 1.0.0
language: python
docs:
  source: docs/
  target: /sdk-name
  index: README.md
```

## Publishing Workflow

1. Generate documentation locally
2. Validate documentation builds
3. Test examples
4. Publish to documentation portal
5. Verify links work

## CI/CD Integration

```yaml
name: Publish Documentation

on:
  release:
    types: [published]

jobs:
  publish-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate docs
        run: python sdk_docs.py
      - name: Publish to documentation portal
        run: documentation portal publish --docs docs/
```

## Versioning

- Maintain docs for each major version
- Archive old versions
- Provide version selector
- Update latest alias

## Best Practices

1. Version documentation with SDK
2. Test docs before publishing
3. Validate all links
4. Include search functionality
5. Monitor doc usage analytics
