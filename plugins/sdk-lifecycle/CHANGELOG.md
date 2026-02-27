# Changelog

All notable changes to the sdk-lifecycle plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-11

### Added
- Initial release of sdk-lifecycle plugin
- `sdk-scaffolding` skill for multi-language SDK project setup
  - Support for .NET, Python, and TypeScript projects
  - Project structure generation with tests, docs, and CI/CD
  - Package configuration templates (pyproject.toml, package.json, .csproj)
- `sdk-security-review` skill for automated security auditing
  - Dependency vulnerability scanning
  - OWASP security checklist validation
  - Security scorecard generation
- `sdk-documentation` skill for documentation generation
  - API reference extraction from code comments
  - Usage guide templates
  - documentation portal integration for publishing
- Comprehensive reference documentation for all supported languages
- CI/CD pipeline patterns for GitHub Actions
- Security checklist and vulnerability management guides
