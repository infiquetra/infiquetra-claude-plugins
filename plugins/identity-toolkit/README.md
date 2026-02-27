# Infiquetra Identity Toolkit

Digital identity architecture and wallet design guidance for Infiquetra projects, covering ISO 18013-5, mDoc, OID4VP, W3C Verifiable Credentials, and NIST 800-63 compliance.

## Overview

The Infiquetra Identity Toolkit provides expert guidance on designing secure, compliant digital identity systems. Whether you're building custodial wallets, implementing KYC verification, or migrating to decentralized identity standards, this plugin offers comprehensive architectural patterns and best practices.

**Key Capabilities**:
- 🏛️ **Standards Expertise**: ISO 18013-5, mDoc, OID4VP, W3C VC/DIDs, NIST 800-63
- 🔐 **Wallet Architectures**: Custodial, non-custodial, and hybrid patterns
- 🎯 **Identity Verification**: KYC/AML integration, identity assurance levels
- 🔒 **Security Design**: Cryptographic protocols, key management, threat modeling
- ⚖️ **Compliance**: GDPR, NIST, financial services regulations
- 💼 **Infiquetra Integration**: Patterns specific to Infiquetra identity and wallet services

## Features

### Standards Supported

**ISO 18013-5 & mDoc**:
- Mobile document credentials
- Offline verification
- Selective disclosure
- Reader authentication

**OpenID for Verifiable Presentations (OID4VP)**:
- OAuth 2.0-based credential presentation
- QR code and deep link flows
- Compatible with W3C VCs

**W3C Verifiable Credentials**:
- Tamper-evident digital credentials
- JWT and JSON-LD formats
- Issuer-holder-verifier model

**W3C Decentralized Identifiers (DIDs)**:
- Self-sovereign identifiers
- Multiple DID methods (did:web, did:key, did:ion, did:ethr)
- DID document resolution

**NIST 800-63 Digital Identity Guidelines**:
- Identity Assurance Levels (IAL1, IAL2, IAL3)
- Authenticator Assurance Levels (AAL1, AAL2, AAL3)
- Federation Assurance Levels (FAL1, FAL2, FAL3)

### Architecture Patterns

**Custodial Wallets**:
- Server-managed private keys
- AWS KMS integration
- Account recovery mechanisms
- Regulatory compliance patterns

**Non-Custodial Wallets**:
- User-controlled keys
- HD wallet derivation (BIP-32/BIP-44)
- Seed phrase management
- Secure enclave integration

**Hybrid Solutions**:
- Social recovery mechanisms
- Multi-signature wallets
- Threshold signing schemes

### Security Design

**Key Management**:
- Hardware Security Module (HSM) patterns
- Cloud KMS integration (AWS, Azure)
- Key rotation strategies
- Secure key derivation

**Authentication**:
- DID-based authentication
- OAuth 2.0/OIDC patterns
- Multi-factor authentication (MFA)
- Hardware token support (FIDO2/WebAuthn)

**Cryptographic Protocols**:
- Signature schemes (ECDSA, EdDSA)
- Encryption patterns (AES-GCM, ECIES)
- Zero-knowledge proofs

## Skills

### digital-identity-design

Comprehensive skill providing guidance on all aspects of digital identity architecture.

**When to Use**:
- Designing identity systems or wallet architectures
- Implementing mDoc, ISO 18013-5, or OID4VP protocols
- Working with W3C Verifiable Credentials or DIDs
- Meeting NIST 800-63 requirements
- Building KYC/AML verification flows
- Implementing custodial or non-custodial wallets
- Planning key management systems
- Migrating to modern identity standards

**Trigger Phrases**:
- "design identity system"
- "implement digital wallet"
- "mDoc credential"
- "ISO 18013-5"
- "OID4VP"
- "verifiable credential"
- "NIST 800-63"
- "KYC verification"
- "custodial wallet"
- "non-custodial wallet"
- "DID implementation"

**Coverage**:
- Standards overview and selection guidance
- Wallet architecture patterns
- Identity verification workflows
- Security design and threat modeling
- Compliance frameworks (GDPR, NIST, financial services)
- Implementation code examples
- Infiquetra-specific integration patterns

## Agents

### digital-identity-architect

Expert agent for deep analysis and design of digital identity systems.

**Expertise**:
- 15+ years digital identity architecture
- W3C DID/VC specifications
- NIST Digital Identity Guidelines
- Wallet technologies (custodial/non-custodial)
- Regulatory compliance (KYC/AML, GDPR)
- Cryptographic protocols
- Blockchain integration

**Approach**:
- Standards-first analysis
- Security-by-design
- Compliance awareness
- Scalability planning
- Proactive research

## Usage Examples

### Example 1: Design Custodial Wallet System

```
You: "I need to design a custodial wallet system for Infiquetra that handles KYC verification and stores user credentials securely"

Response:
- AWS KMS-based key management architecture
- NIST IAL2 identity verification flow
- AAL2 multi-factor authentication
- Regulatory compliance checklist (KYC/AML)
- Infiquetra-specific integration patterns
- Code examples for wallet creation and transaction signing
```

### Example 2: Implement mDoc Verification

```
You: "How do I implement ISO 18013-5 mDoc verification for age verification?"

Response:
- ISO 18013-5 standard overview
- mDoc structure and selective disclosure
- BLE/NFC presentation protocols
- Offline cryptographic verification
- Reader authentication
- Privacy-preserving implementation
- Example verification code
```

### Example 3: Meet NIST 800-63 IAL2 Requirements

```
You: "We need to meet NIST 800-63 IAL2 for our identity verification process"

Response:
- IAL2 requirements breakdown
- Evidence strength levels (SUPERIOR, STRONG, FAIR)
- Identity proofing process
- Validation and verification steps
- KYC service provider integration
- Biometric matching requirements
- Implementation checklist
- Code examples
```

### Example 4: Migrate to W3C Verifiable Credentials

```
You: "Our system uses JWTs. How do we migrate to W3C Verifiable Credentials?"

Response:
- Dual-mode authentication strategy
- VC issuance service design
- JWT to VC migration path
- Backward compatibility patterns
- Timeline and phases
- Code examples for both formats
- Testing and validation approach
```

## Use Cases

### Infiquetra Wallet Service

Design and implement secure wallet solutions:
- Custodial wallet architecture with AWS KMS
- Multi-factor authentication (AAL2)
- Transaction signing patterns
- Key rotation strategies
- Account recovery mechanisms

### Infiquetra Identity Service

Build robust identity verification:
- KYC/AML integration
- Identity assurance level compliance (IAL2)
- DID-based authentication
- JWT token management
- Federation patterns

### Digital Credentials

Implement verifiable credential systems:
- W3C VC issuance and verification
- OID4VP presentation flows
- mDoc credential management
- Selective disclosure
- Revocation mechanisms

### Decentralized Identity

Migrate to decentralized identity:
- DID implementation strategy
- Self-sovereign identity patterns
- Non-custodial wallet design
- User key management
- Privacy-preserving protocols

## Prerequisites

### Knowledge Requirements

**Basic Understanding Of**:
- Identity and authentication concepts
- Public key cryptography
- JWT tokens and OAuth 2.0
- RESTful API design

**Helpful But Not Required**:
- Blockchain and distributed systems
- W3C standards ecosystem
- Regulatory compliance frameworks
- AWS services (KMS, Cognito, Lambda)

### Technical Environment

**For Infiquetra Integration**:
- Python 3.12+ (Lambda runtime)
- AWS CDK for infrastructure
- Familiarity with Infiquetra services
- Access to Infiquetra repositories

## References

### Included Documentation

**NIST 800-63 Guidelines** (`references/nist-800-63-guidelines.md`):
- Identity Assurance Levels (IAL1, IAL2, IAL3)
- Authenticator Assurance Levels (AAL1, AAL2, AAL3)
- Federation Assurance Levels (FAL1, FAL2, FAL3)
- Implementation requirements and code examples
- Infiquetra compliance checklist

**Identity Architecture Patterns** (`references/identity-architecture-patterns.md`):
- Custodial wallet architecture
- Non-custodial wallet architecture
- Hybrid approaches (social recovery)
- Authentication patterns (DID, OAuth, JWT)
- Key management patterns (HD wallets, KMS)
- Federation patterns
- Recovery mechanisms

**Infiquetra Identity Stack** (`references/identity-stack.md`):
- Current Infiquetra identity architecture
- identity-service implementation
- wallet-service implementation
- AWS Cognito integration
- Security patterns and best practices
- Migration paths
- Testing strategies

### External Resources

**Standards Documentation**:
- [W3C Verifiable Credentials](https://www.w3.org/TR/vc-data-model/)
- [W3C DIDs](https://www.w3.org/TR/did-core/)
- [ISO 18013-5](https://www.iso.org/standard/69084.html)
- [OpenID for Verifiable Presentations](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html)
- [NIST 800-63 Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)

**Implementation Libraries**:
- [PyJWT](https://pyjwt.readthedocs.io/) - JWT encoding/decoding
- [did-jwt](https://github.com/decentralized-identity/did-jwt) - DID-based JWT
- [vc-js](https://github.com/digitalbazaar/vc-js) - Verifiable Credentials
- [py-multibase](https://github.com/multiformats/py-multibase) - Multibase encoding

## Related Infiquetra Projects

- **identity-service**: Core identity and authentication service
- **wallet-service**: Custodial wallet management
- **aws-core-infra**: AWS infrastructure and CDK constructs
- **documentation portal**: Developer portal and documentation

## Installation

This plugin is part of the Infiquetra Claude Plugin Marketplace. Install via:

```bash
/plugin install identity-toolkit
```

Or configure the Infiquetra marketplace in your Claude Code settings:

```json
{
  "extraKnownMarketplaces": [
    {
      "name": "plugins",
      "url": "https://github.com/infiquetra/infiquetra-claude-plugins/raw/main/.claude-plugin/marketplace.json"
    }
  ]
}
```

## Support

For questions or issues:
- **Slack**: 
- **GitHub Issues**: [claude-plugins/issues](https://github.com/infiquetra/infiquetra-claude-plugins/issues)
- **Documentation**: [Infiquetra Documentation](https://github.com/infiquetra/infiquetra-claude-plugins)

## License

MIT License - Copyright (c) 2026 your organization

## Version

Current version: 1.0.0

See [CHANGELOG.md](./CHANGELOG.md) for version history.
