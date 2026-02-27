# Changelog

All notable changes to the Infiquetra Identity Toolkit plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-11

### Added

- Initial release of identity-toolkit plugin
- **digital-identity-design skill** with comprehensive identity architecture guidance
  - ISO 18013-5 and mDoc standards coverage
  - OpenID for Verifiable Presentations (OID4VP) protocols
  - W3C Verifiable Credentials and DIDs
  - NIST 800-63 digital identity guidelines (IAL, AAL, FAL)
  - OAuth 2.0/OIDC authentication patterns
- **digital-identity-architect agent** for expert identity system analysis
- **Reference documentation**:
  - `nist-800-63-guidelines.md` - Complete NIST digital identity guidelines with implementation examples
  - `identity-architecture-patterns.md` - Custodial, non-custodial, and hybrid wallet patterns
  - `identity-stack.md` - Infiquetra-specific identity architecture and integration patterns
- **Wallet architecture patterns**:
  - Custodial wallet design with AWS KMS integration
  - Non-custodial wallet with HD key derivation
  - Hybrid approaches with social recovery
- **Identity verification guidance**:
  - KYC/AML integration patterns
  - Identity proofing workflows
  - Biometric verification
- **Security design patterns**:
  - Key management (HSM, KMS, secure enclave)
  - Cryptographic protocols (ECDSA, EdDSA, zero-knowledge proofs)
  - Threat modeling and mitigation strategies
- **Compliance frameworks**:
  - NIST 800-63 assurance levels
  - GDPR privacy requirements
  - Financial services regulations
- **Infiquetra integration examples**:
  - identity-service patterns
  - wallet-service implementation
  - AWS Cognito integration
  - Lambda/API Gateway authentication
- **Code examples**:
  - Python implementations for all major patterns
  - TypeScript/React Native for client-side wallets
  - Solidity smart contracts for social recovery
  - AWS CDK infrastructure patterns

### Documentation

- Comprehensive README with use cases and examples
- Detailed reference documents for all standards
- Infiquetra-specific implementation guidance
- Migration strategies for legacy systems

[1.0.0]: https://github.com/infiquetra/infiquetra-claude-plugins/releases/tag/plugins/identity-toolkit/v1.0.0
