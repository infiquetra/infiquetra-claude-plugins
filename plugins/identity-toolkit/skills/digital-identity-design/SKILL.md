---
name: digital-identity-design
description: Design digital identity systems with ISO 18013-5, mDoc, OID4VP, W3C Verifiable Credentials, and NIST 800-63 compliance
when_to_use: |
  Use this skill when the user wants to:
  - Design identity systems or wallet architectures
  - Implement mDoc, ISO 18013-5, or OID4VP protocols
  - Work with W3C Verifiable Credentials or DIDs
  - Meet NIST 800-63 identity assurance requirements
  - Implement KYC/AML verification flows
  - Build custodial or non-custodial wallet solutions
  - Design key management systems
  - Plan identity verification workflows
  - Migrate legacy authentication to modern standards
  - Ensure identity system compliance (GDPR, financial services)
---

# Digital Identity Architecture Design

You are helping the user design a digital identity system using modern standards and best practices.

## Overview

This skill provides comprehensive guidance on designing identity systems, digital wallets, and credential management solutions following industry standards:

- **ISO 18013-5**: Mobile driving license (mDL) and mobile document (mDoc) standards
- **OID4VP**: OpenID for Verifiable Presentations
- **W3C Standards**: Verifiable Credentials (VC), Decentralized Identifiers (DIDs)
- **NIST 800-63**: Digital identity guidelines and assurance levels
- **OAuth 2.0/OIDC**: Modern authentication and authorization protocols

## Standards Coverage

### ISO 18013-5 & mDoc

ISO 18013-5 defines the standard for mobile driving licenses (mDL) and extends to general mobile documents (mDoc):

**Key Concepts**:
- **mDoc**: Mobile document format for digitally signed credentials
- **Reader Authentication**: Cryptographic verification of document readers
- **Selective Disclosure**: Share only requested attributes, not full document
- **Offline Verification**: Cryptographic validation without network connectivity

**Use Cases**:
- Digital driver's licenses
- Government-issued credentials
- Age verification
- Identity proofing

**Implementation Considerations**:
- Requires secure element or trusted execution environment
- BLE and NFC protocols for presentation
- Privacy-preserving selective disclosure
- Cryptographic binding to device

### OID4VP (OpenID for Verifiable Presentations)

Protocol for requesting and presenting verifiable credentials using OAuth 2.0 framework:

**Key Features**:
- Request specific credentials from holders
- Present credentials to verifiers
- Compatible with W3C Verifiable Credentials
- Supports various presentation formats (JWT, JSON-LD)

**Flow**:
1. Verifier creates presentation request (QR code, deep link)
2. Wallet receives request and prompts user
3. User consents to share credentials
4. Wallet creates signed presentation
5. Verifier validates presentation and grants access

**Benefits**:
- Familiar OAuth 2.0 patterns
- Interoperable with existing identity infrastructure
- Strong cryptographic verification
- User consent and control

### W3C Verifiable Credentials

Standard format for tamper-evident credentials that can be cryptographically verified:

**Components**:
- **Issuer**: Creates and signs credentials
- **Holder**: Stores credentials in wallet
- **Verifier**: Validates credential signatures and claims
- **Credential**: Digitally signed set of claims about a subject

**Key Properties**:
- Tamper-evident (cryptographic signatures)
- Privacy-respecting (selective disclosure, zero-knowledge proofs)
- Machine-verifiable (automated validation)
- Decentralized (no central authority required)

**Common Formats**:
- JWT-based VCs (compact, widely supported)
- JSON-LD VCs (semantic web, linked data)

### W3C Decentralized Identifiers (DIDs)

Self-sovereign identifier system not dependent on centralized registries:

**Characteristics**:
- User controls their identifier
- No central authority
- Cryptographically verifiable
- Resolvable to DID documents

**Common DID Methods**:
- `did:web` - Web-based DIDs (easier adoption)
- `did:key` - Self-contained cryptographic keys
- `did:ion` - Bitcoin-anchored DIDs (ION network)
- `did:ethr` - Ethereum-based DIDs

### NIST 800-63 Guidelines

Comprehensive framework for digital identity:

**Identity Assurance Levels (IAL)**:
- **IAL1**: Self-asserted identity (minimal verification)
- **IAL2**: Remote or in-person identity proofing (KYC verification)
- **IAL3**: In-person identity proofing (highest assurance)

**Authenticator Assurance Levels (AAL)**:
- **AAL1**: Single-factor authentication
- **AAL2**: Multi-factor authentication (MFA)
- **AAL3**: Hardware-based cryptographic authentication

**Federation Assurance Levels (FAL)**:
- **FAL1**: Bearer assertion (no additional protection)
- **FAL2**: Assertion signed by IdP
- **FAL3**: Encrypted and signed assertion, holder-of-key binding

See `references/nist-800-63-guidelines.md` for detailed requirements.

## Wallet Architectures

### Custodial Wallets

Server-managed wallet where the service provider controls private keys:

**Characteristics**:
- Keys stored on server (encrypted at rest)
- Service handles key management
- User authentication via passwords/biometrics
- Account recovery mechanisms available
- Centralized control and responsibility

**Benefits**:
- Easier user experience
- Account recovery possible
- Familiar authentication patterns
- Service can assist with transactions

**Considerations**:
- Service is custodian (regulatory implications)
- Single point of compromise
- Must implement robust security (HSM, key rotation)
- KYC/AML requirements likely apply

**Infiquetra Implementation Pattern**:
```python
# Custodial wallet key management
from aws_kms import KMSClient

class CustodialWalletService:
    def __init__(self):
        self.kms = KMSClient()

    async def create_wallet(self, user_id: str) -> Wallet:
        # Generate key in KMS
        key_id = await self.kms.generate_key(
            key_spec="ECC_NIST_P256",
            user_context={"user_id": user_id}
        )

        # Store wallet metadata
        wallet = await self.db.create_wallet({
            "user_id": user_id,
            "kms_key_id": key_id,
            "created_at": datetime.utcnow()
        })

        return wallet
```

### Non-Custodial Wallets

User-controlled wallet where user holds their private keys:

**Characteristics**:
- User generates and stores private keys
- Seed phrase backup (BIP-39 mnemonic)
- No server-side key storage
- User fully responsible for key security
- Service cannot recover lost keys

**Benefits**:
- User sovereignty and control
- No custodial liability for service
- Privacy-preserving (minimal user data)
- Resistant to service compromise

**Considerations**:
- Users must understand key security
- No account recovery if keys lost
- More complex UX
- Seed phrase backup critical

**Best Practices**:
- Clear warnings about key responsibility
- Secure key derivation (BIP-32/BIP-44)
- Biometric encryption for mobile apps
- Hardware wallet integration options

### Hybrid Approaches

Combine benefits of both custodial and non-custodial models:

**Social Recovery**:
- User holds keys but designates trusted contacts
- Lost keys can be recovered with threshold of contacts
- Examples: Argent wallet, Gnosis Safe

**Custodial with Escape Hatch**:
- Default custodial experience
- User can "upgrade" to full control
- Migration path from custodial to non-custodial

**Multi-Signature Wallets**:
- Keys split between user and service
- Both parties must sign transactions
- Balance of control and security

See `references/identity-architecture-patterns.md` for detailed patterns.

## Identity Verification & KYC

### Identity Proofing Process

For IAL2 compliance (NIST 800-63):

1. **Evidence Collection**:
   - Government-issued ID (driver's license, passport)
   - Proof of address
   - Biometric capture (photo, liveness detection)

2. **Evidence Validation**:
   - Document authenticity checks (security features, barcodes)
   - Data consistency verification
   - Expiration date validation

3. **Verification**:
   - Compare biometric to ID photo
   - Check against authoritative sources
   - Fraud detection (duplicate IDs, synthetic identities)

4. **Binding**:
   - Associate verified identity with account
   - Establish authenticator (password, MFA device)
   - Create audit trail

### KYC/AML Integration

**Regulatory Requirements**:
- Customer Due Diligence (CDD)
- Enhanced Due Diligence (EDD) for high-risk
- Ongoing monitoring
- Suspicious Activity Reports (SAR)

**Service Providers**:
- Identity verification APIs (Jumio, Onfido, Veriff)
- Watchlist screening (Chainalysis, Elliptic)
- Document verification services
- Biometric liveness detection

**Privacy Considerations**:
- Minimize data collection
- Secure storage with encryption
- Access controls and audit logging
- Data retention policies
- GDPR compliance (right to erasure)

## Security Design

### Key Management

**Key Generation**:
- Use cryptographically secure random number generators
- Generate keys in secure environments (HSM, TEE, secure enclave)
- Never transmit private keys
- Derive keys using BIP-32/BIP-44 for HD wallets

**Key Storage**:
- **Server-side**: AWS KMS, Azure Key Vault, HSMs
- **Client-side**: Keychain (iOS), Keystore (Android), secure enclave
- Encrypt keys at rest with additional layer
- Separate encryption and signing keys

**Key Rotation**:
- Regular rotation schedule (90 days for high-risk)
- Graceful rotation (overlap period for verification)
- Update all dependent systems
- Audit rotation events

### Cryptographic Protocols

**Signature Schemes**:
- ECDSA with P-256 curve (widely supported)
- EdDSA with Ed25519 (modern, performant)
- RSA-PSS for legacy compatibility

**Encryption**:
- AES-256-GCM for symmetric encryption
- ECIES for asymmetric encryption
- Perfect forward secrecy for session keys

**Zero-Knowledge Proofs**:
- Prove attributes without revealing values
- Age verification without showing birthdate
- Credential possession without showing credential
- Examples: zk-SNARKs, BBS+ signatures

### Threat Modeling

**Identity System Threats**:
- **Credential theft**: Phishing, malware, session hijacking
- **Key compromise**: Server breach, client malware
- **Replay attacks**: Reusing stolen presentations
- **Man-in-the-middle**: Intercepting credential presentations
- **Synthetic identities**: Fabricated identity combinations

**Mitigations**:
- Multi-factor authentication
- Device binding and attestation
- Time-limited credentials (short expiry)
- Challenge-response protocols
- Rate limiting and anomaly detection
- Hardware security modules

## Compliance & Regulations

### GDPR Considerations

**Privacy by Design**:
- Minimize personal data collection
- Purpose limitation (specific use cases)
- Data minimization (only necessary data)
- Storage limitation (retention policies)

**User Rights**:
- Right to access (export user data)
- Right to rectification (update incorrect data)
- Right to erasure ("right to be forgotten")
- Right to data portability

**Technical Measures**:
- Encryption at rest and in transit
- Pseudonymization where possible
- Access controls and audit logging
- Data breach notification procedures

### Financial Services Regulations

**For Custodial Wallet Services**:
- Money transmission licenses (state-by-state in US)
- FinCEN registration (MSB)
- KYC/AML compliance programs
- Transaction monitoring
- Suspicious Activity Reporting (SAR)

**For Non-Custodial Services**:
- May have reduced regulatory burden
- Still subject to general consumer protection laws
- Clear disclosures about user responsibility

## Implementation Guidance

### Architecture Decision Framework

When designing identity systems, consider:

1. **Custody Model**: Who controls the keys?
   - Custodial: Easier UX, regulatory burden, security responsibility
   - Non-custodial: User sovereignty, no recovery, simpler compliance
   - Hybrid: Balance trade-offs

2. **Standards Selection**: Which protocols to support?
   - W3C VC: Broad support, flexible, future-proof
   - mDoc/ISO 18013-5: Government use cases, offline verification
   - OAuth/OIDC: Legacy integration, familiar patterns

3. **Assurance Level**: What identity proofing required?
   - IAL1: Self-asserted (low risk)
   - IAL2: KYC verification (medium risk)
   - IAL3: In-person proofing (high risk)

4. **Authenticator Type**: How do users authenticate?
   - AAL1: Password (low security)
   - AAL2: MFA required (recommended)
   - AAL3: Hardware token (high security)

### Code Examples

**Verifiable Credential Issuance** (Python/FastAPI):
```python
from dataclasses import dataclass
from datetime import datetime, timedelta
import jwt

@dataclass
class VerifiableCredential:
    issuer: str
    subject: str
    claims: dict
    expiration: datetime

class CredentialIssuer:
    def __init__(self, issuer_did: str, private_key: str):
        self.issuer_did = issuer_did
        self.private_key = private_key

    def issue_credential(
        self,
        subject_did: str,
        claims: dict,
        validity_days: int = 365
    ) -> str:
        """Issue a W3C Verifiable Credential as JWT."""
        now = datetime.utcnow()
        exp = now + timedelta(days=validity_days)

        payload = {
            "iss": self.issuer_did,
            "sub": subject_did,
            "iat": now.timestamp(),
            "exp": exp.timestamp(),
            "vc": {
                "@context": [
                    "https://www.w3.org/2018/credentials/v1"
                ],
                "type": ["VerifiableCredential"],
                "credentialSubject": claims
            }
        }

        # Sign with private key (ES256)
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers={"kid": f"{self.issuer_did}#key-1"}
        )

        return token
```

**Credential Verification** (Python):
```python
import jwt
from cryptography.hazmat.primitives import serialization

class CredentialVerifier:
    def __init__(self, trusted_issuers: dict[str, str]):
        """Initialize with trusted issuer DIDs and public keys."""
        self.trusted_issuers = trusted_issuers

    async def verify_credential(self, credential_jwt: str) -> dict:
        """Verify a Verifiable Credential JWT."""
        # Decode header to get issuer
        header = jwt.get_unverified_header(credential_jwt)
        payload = jwt.decode(
            credential_jwt,
            options={"verify_signature": False}
        )

        issuer_did = payload.get("iss")

        # Check issuer is trusted
        if issuer_did not in self.trusted_issuers:
            raise ValueError(f"Untrusted issuer: {issuer_did}")

        # Get public key for issuer
        public_key = self.trusted_issuers[issuer_did]

        # Verify signature
        verified_payload = jwt.decode(
            credential_jwt,
            public_key,
            algorithms=["ES256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "require": ["iss", "sub", "iat", "exp"]
            }
        )

        return verified_payload
```

### Migration Strategies

**Legacy Auth → JWT**:
1. Add JWT generation alongside existing session
2. Update clients to accept JWT tokens
3. Migrate endpoints one-by-one
4. Deprecate legacy sessions

**JWT → Verifiable Credentials**:
1. Implement VC issuance service
2. Issue VCs alongside JWTs (dual mode)
3. Update verifiers to accept both formats
4. Gradually transition to VC-only
5. Support revocation (status lists)

**Centralized → Decentralized Identity**:
1. Generate DIDs for existing users
2. Issue VCs for user attributes
3. Implement DID authentication
4. Support both centralized and DID login
5. Migrate users gradually with incentives

## Infiquetra-Specific Guidance

### Current Infiquetra Identity Stack

Infiquetra uses the following identity architecture:

- **identity-service**: Core identity and authentication
- **wallet-service**: Custodial wallet management
- **AWS Cognito**: User pools for authentication
- **JWT tokens**: Bearer tokens for API access
- **API Gateway**: Token validation and authorization

See `references/identity-stack.md` for detailed patterns.

### Recommended Patterns for Infiquetra

1. **Use AWS KMS for key management** (custodial wallets)
2. **Implement IAL2 verification** for high-value operations
3. **Support MFA** (AAL2) for all production systems
4. **Design for eventual DID support** (future-proofing)
5. **Follow Infiquetra security standards** (encryption, audit logging)

## Testing Strategies

### Identity System Testing

**Functional Testing**:
- Credential issuance flows
- Presentation and verification flows
- Key rotation procedures
- Account recovery mechanisms

**Security Testing**:
- Penetration testing (OWASP Top 10)
- Credential replay attack testing
- Key compromise scenarios
- Man-in-the-middle attack testing

**Compliance Testing**:
- IAL/AAL/FAL level verification
- GDPR right-to-erasure testing
- KYC/AML process validation
- Audit log completeness

**Performance Testing**:
- Concurrent credential issuance
- Verification throughput
- Key derivation performance
- Database query optimization

## Deployment & Operations

### Operational Considerations

**Key Management Operations**:
- Regular key rotation schedule
- Key backup and recovery procedures
- HSM failover testing
- Key compromise response plan

**Monitoring & Alerting**:
- Failed authentication attempts
- Key usage patterns (anomaly detection)
- Credential verification failures
- KYC process completion rates

**Incident Response**:
- Key compromise procedure
- Credential revocation process
- User notification plans
- Regulatory reporting requirements

## References

For detailed technical information, see:

- `references/nist-800-63-guidelines.md` - Complete NIST digital identity guidelines and requirements
- `references/identity-architecture-patterns.md` - Common architecture patterns and design trade-offs
- `references/identity-stack.md` - Infiquetra-specific identity architecture and integration patterns

## External Resources

**Standards Documentation**:
- [W3C Verifiable Credentials](https://www.w3.org/TR/vc-data-model/)
- [W3C DIDs](https://www.w3.org/TR/did-core/)
- [ISO 18013-5](https://www.iso.org/standard/69084.html)
- [OpenID for Verifiable Presentations](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html)
- [NIST 800-63 Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)

**Implementation Libraries**:
- [PyJWT](https://pyjwt.readthedocs.io/) - JWT encoding/decoding for Python
- [did-jwt](https://github.com/decentralized-identity/did-jwt) - DID-based JWT (JavaScript)
- [vc-js](https://github.com/digitalbazaar/vc-js) - Verifiable Credentials library

**Service Providers**:
- [Jumio](https://www.jumio.com/) - Identity verification and KYC
- [Onfido](https://onfido.com/) - Document and biometric verification
- [Trinsic](https://trinsic.id/) - Verifiable Credentials platform
