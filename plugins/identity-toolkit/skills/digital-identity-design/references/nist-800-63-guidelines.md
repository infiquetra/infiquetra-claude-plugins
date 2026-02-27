# NIST 800-63 Digital Identity Guidelines

## Overview

NIST Special Publication 800-63 provides a comprehensive framework for digital identity management, covering identity proofing, authentication, and federation. The guidelines define three levels of assurance for each category.

**Document Structure**:
- **SP 800-63-3**: Overall digital identity framework
- **SP 800-63A**: Enrollment and identity proofing
- **SP 800-63B**: Authentication and lifecycle management
- **SP 800-63C**: Federation and assertions

## Identity Assurance Levels (IAL)

IAL defines the robustness of the identity proofing process. Higher levels require stronger evidence and verification.

### IAL1 - Self-Asserted Identity

**Requirements**:
- No requirement to link to real-life identity
- Self-asserted attributes
- No identity proofing required

**Use Cases**:
- Low-risk applications
- Public forums and discussions
- Non-sensitive services
- Pseudonymous accounts

**Implementation**:
```python
# IAL1 - Minimal verification
def register_ial1_user(email: str, password: str) -> User:
    """Register user with self-asserted identity."""
    # Only verify email ownership
    user = create_user(email=email, password=password)
    send_verification_email(user)
    return user
```

**Limitations**:
- No assurance of real identity
- High fraud risk
- Not suitable for financial services
- Cannot be used for legal identity

### IAL2 - Remote or In-Person Proofing

**Requirements**:
- Evidence of identity (government ID)
- Validation of evidence authenticity
- Verification against authoritative sources
- Address confirmation

**Evidence Requirements** (minimum):
- **One piece of SUPERIOR evidence**, OR
- **Two pieces of STRONG evidence**, OR
- **One STRONG + two FAIR evidence pieces**

**Evidence Strength Levels**:

**SUPERIOR**:
- US Passport
- Enhanced driver's license
- Government PIV card

**STRONG**:
- Standard driver's license
- State-issued ID card
- Utility bill (address verification)

**FAIR**:
- Bank statement
- HR document from established employer
- Social media account (established history)

**Validation Process**:
1. **Confirm evidence is genuine**
   - Check security features
   - Verify with issuing authority
   - Validate document expiration

2. **Confirm data accuracy**
   - Check consistency across documents
   - Validate against authoritative sources
   - Verify no tampering

3. **Confirm evidence relates to real person**
   - Cross-reference multiple sources
   - Check for synthetic identity indicators

**Verification Process**:
1. **Compare applicant to evidence**
   - Photo comparison (facial matching)
   - Biometric verification
   - Knowledge-based verification (KBV)

2. **Resolve identity**
   - Confirm uniqueness (no duplicate accounts)
   - Validate in authoritative sources
   - Check fraud databases

**Use Cases**:
- Financial services (banking, investment)
- Healthcare portals
- Government benefits
- E-commerce with high transaction values

**Implementation Example**:
```python
from typing import List

class IAL2Verification:
    def __init__(self, id_verification_service):
        self.id_service = id_verification_service

    async def verify_identity(
        self,
        applicant_id: str,
        evidence: List[IdentityEvidence],
        biometric_image: bytes
    ) -> VerificationResult:
        """Perform IAL2 identity verification."""

        # Step 1: Validate evidence
        validation_results = []
        for doc in evidence:
            result = await self.id_service.validate_document(
                document_image=doc.image,
                document_type=doc.type
            )
            validation_results.append(result)

        # Check minimum evidence requirements met
        if not self._meets_evidence_requirements(validation_results):
            return VerificationResult(
                success=False,
                reason="Insufficient evidence quality"
            )

        # Step 2: Verify applicant matches evidence
        face_match = await self.id_service.compare_faces(
            selfie=biometric_image,
            id_photo=evidence[0].photo
        )

        if face_match.confidence < 0.85:
            return VerificationResult(
                success=False,
                reason="Biometric match failed"
            )

        # Step 3: Resolve against authoritative sources
        resolution = await self.id_service.resolve_identity(
            name=evidence[0].name,
            date_of_birth=evidence[0].dob,
            address=evidence[1].address if len(evidence) > 1 else None
        )

        if not resolution.confirmed:
            return VerificationResult(
                success=False,
                reason="Unable to resolve identity"
            )

        # Step 4: Check for duplicate accounts
        duplicate_check = await self.check_duplicate_enrollment(
            name=evidence[0].name,
            dob=evidence[0].dob
        )

        if duplicate_check.found:
            return VerificationResult(
                success=False,
                reason="Duplicate enrollment detected"
            )

        return VerificationResult(
            success=True,
            assurance_level="IAL2",
            verified_attributes={
                "name": evidence[0].name,
                "dob": evidence[0].dob,
                "address": evidence[1].address if len(evidence) > 1 else None
            }
        )

    def _meets_evidence_requirements(
        self,
        validations: List[ValidationResult]
    ) -> bool:
        """Check if evidence meets IAL2 requirements."""
        superior = sum(1 for v in validations if v.strength == "SUPERIOR")
        strong = sum(1 for v in validations if v.strength == "STRONG")
        fair = sum(1 for v in validations if v.strength == "FAIR")

        # One SUPERIOR, OR two STRONG, OR one STRONG + two FAIR
        return (
            superior >= 1 or
            strong >= 2 or
            (strong >= 1 and fair >= 2)
        )
```

### IAL3 - In-Person Proofing

**Requirements**:
- All IAL2 requirements
- **Physical presence required**
- Biometric capture mandatory
- Trained operator conducts proofing
- Supervised remote identity proofing (SRIP) allowed with specific controls

**Additional Controls**:
- Operator training and certification
- Audit trail of proofing session
- High-quality biometric capture
- Enhanced liveness detection
- Document security feature verification

**Use Cases**:
- Government security clearances
- High-value financial transactions
- Legal identity establishment
- National security applications

**Not typically required for commercial applications**

## Authenticator Assurance Levels (AAL)

AAL defines the strength of the authentication process. Higher levels require stronger authenticator types and usage protocols.

### AAL1 - Single-Factor Authentication

**Requirements**:
- Single authentication factor
- Can be memorized secret (password)
- Minimum strength requirements

**Authenticator Types**:
- Passwords (with complexity requirements)
- Software OTP (if verifier stores secret)
- Single-factor cryptographic device

**Password Requirements**:
- Minimum 8 characters (12+ recommended)
- No composition rules required (no mandatory special chars)
- Check against breach databases
- No periodic rotation required
- Rate limiting on attempts

**Use Cases**:
- Low-risk applications
- Public information access
- Non-financial services

**Implementation**:
```python
import hashlib
import secrets
from typing import Optional

class AAL1Authentication:
    def __init__(self, breach_checker):
        self.breach_checker = breach_checker
        self.max_attempts = 5
        self.lockout_duration = 900  # 15 minutes

    async def register_password(
        self,
        user_id: str,
        password: str
    ) -> bool:
        """Register password for AAL1 authentication."""

        # Check minimum length
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        # Check against breach database
        if await self.breach_checker.is_breached(password):
            raise ValueError("Password found in breach database")

        # Hash with salt
        salt = secrets.token_bytes(32)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000  # iterations
        )

        # Store hash and salt
        await self.store_credentials(
            user_id=user_id,
            password_hash=password_hash,
            salt=salt
        )

        return True

    async def authenticate(
        self,
        user_id: str,
        password: str
    ) -> Optional[str]:
        """Authenticate user with password."""

        # Check rate limiting
        attempts = await self.get_failed_attempts(user_id)
        if attempts >= self.max_attempts:
            raise AuthenticationError("Account temporarily locked")

        # Get stored credentials
        stored = await self.get_credentials(user_id)

        # Hash provided password
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            stored.salt,
            100000
        )

        # Compare hashes
        if secrets.compare_digest(password_hash, stored.password_hash):
            await self.reset_failed_attempts(user_id)
            return self.generate_session_token(user_id)
        else:
            await self.increment_failed_attempts(user_id)
            return None
```

### AAL2 - Multi-Factor Authentication

**Requirements**:
- Two different authentication factors
- Factors must be from different categories

**Factor Categories**:
1. **Something you know**: Password, PIN
2. **Something you have**: Hardware token, phone, smartcard
3. **Something you are**: Biometric (fingerprint, face)

**Approved Authenticator Combinations**:
- Password + SMS OTP
- Password + TOTP app (Google Authenticator)
- Password + Hardware token (YubiKey)
- Password + Push notification
- Biometric + PIN
- Smartcard + PIN

**Memorized Secret Requirements** (if used):
- Minimum 8 characters
- Maximum length at least 64 characters
- Support all ASCII characters and spaces
- No composition rules required
- Check against breach databases

**OTP Requirements**:
- Time-based (TOTP): 30-second window, 6+ digits
- Event-based (HOTP): Counter-based, resistant to replay
- Use approved cryptographic algorithms (HMAC-SHA256+)

**Verifier Requirements**:
- Rate limiting (max 10 failed attempts)
- Throttling or exponential backoff
- Session binding after successful auth
- Reauthentication for sensitive operations

**Use Cases**:
- Financial applications (recommended minimum)
- Healthcare systems
- Corporate systems
- E-commerce

**Implementation Example**:
```python
import pyotp
from datetime import datetime, timedelta

class AAL2Authentication:
    def __init__(self):
        self.otp_window = 1  # Allow 1 step before/after
        self.session_timeout = 3600  # 1 hour

    async def setup_totp(self, user_id: str) -> dict:
        """Set up TOTP for user."""
        # Generate secret
        secret = pyotp.random_base32()

        # Create TOTP instance
        totp = pyotp.TOTP(secret)

        # Generate provisioning URI for QR code
        provisioning_uri = totp.provisioning_uri(
            name=user_id,
            issuer_name="Infiquetra"
        )

        # Store secret encrypted
        await self.store_totp_secret(user_id, secret)

        return {
            "secret": secret,
            "qr_code_uri": provisioning_uri
        }

    async def authenticate_mfa(
        self,
        user_id: str,
        password: str,
        otp_code: str
    ) -> Optional[str]:
        """Authenticate with password + TOTP."""

        # Step 1: Verify password (AAL1)
        password_valid = await self.verify_password(user_id, password)
        if not password_valid:
            return None

        # Step 2: Verify TOTP
        secret = await self.get_totp_secret(user_id)
        totp = pyotp.TOTP(secret)

        if not totp.verify(otp_code, valid_window=self.otp_window):
            await self.log_failed_mfa(user_id)
            return None

        # Both factors verified - create session
        session_token = await self.create_session(
            user_id=user_id,
            aal="AAL2",
            expires_at=datetime.utcnow() + timedelta(
                seconds=self.session_timeout
            )
        )

        return session_token

    async def require_reauthentication(
        self,
        session_token: str,
        operation: str
    ) -> bool:
        """Check if sensitive operation requires reauthentication."""
        session = await self.get_session(session_token)

        # Define sensitive operations requiring reauth
        sensitive_ops = [
            "transfer_funds",
            "change_password",
            "add_beneficiary"
        ]

        if operation in sensitive_ops:
            # Check time since last authentication
            time_since_auth = datetime.utcnow() - session.authenticated_at

            # Require reauth if > 5 minutes
            if time_since_auth > timedelta(minutes=5):
                return True

        return False
```

### AAL3 - Hardware-Based Cryptographic Authentication

**Requirements**:
- Hardware-based cryptographic authenticator
- Verifier impersonation resistant
- Authenticator possession proven with cryptographic protocol

**Approved Authenticators**:
- FIDO2/WebAuthn hardware tokens
- PIV/CAC smartcards
- Hardware TPM-backed keys
- Secure enclave (iOS/Android)

**Characteristics**:
- Private key stored in hardware (cannot be extracted)
- Phishing-resistant (cryptographic challenge-response)
- Replay-resistant (includes freshness/nonce)
- Man-in-the-middle resistant

**Verifier Requirements**:
- Authenticated protected channel (TLS)
- Verify authenticator type meets AAL3
- Check authenticator attestation
- Validate certificate chain (if applicable)

**Use Cases**:
- High-security government systems
- Financial trading platforms
- Critical infrastructure
- Privileged administrative access

**Implementation Example** (FIDO2/WebAuthn):
```python
from fido2.server import Fido2Server
from fido2.webauthn import PublicKeyCredentialRpEntity

class AAL3Authentication:
    def __init__(self, rp_id: str, rp_name: str):
        self.rp = PublicKeyCredentialRpEntity(rp_id, rp_name)
        self.server = Fido2Server(self.rp)

    async def register_authenticator(
        self,
        user_id: str,
        user_name: str
    ) -> dict:
        """Begin FIDO2 authenticator registration."""

        # Create registration challenge
        registration_data, state = self.server.register_begin(
            user={
                "id": user_id.encode(),
                "name": user_name,
                "displayName": user_name
            },
            credentials=[],  # Existing credentials to exclude
            user_verification="required"
        )

        # Store state for verification
        await self.store_registration_state(user_id, state)

        return registration_data

    async def complete_registration(
        self,
        user_id: str,
        credential_data: dict
    ) -> bool:
        """Complete FIDO2 authenticator registration."""

        # Retrieve state
        state = await self.get_registration_state(user_id)

        # Verify registration
        auth_data = self.server.register_complete(
            state,
            credential_data["clientDataJSON"],
            credential_data["attestationObject"]
        )

        # Store credential
        await self.store_credential(
            user_id=user_id,
            credential_id=auth_data.credential_data.credential_id,
            public_key=auth_data.credential_data.public_key,
            sign_count=auth_data.credential_data.sign_count
        )

        return True

    async def authenticate_fido2(
        self,
        user_id: str
    ) -> dict:
        """Begin FIDO2 authentication."""

        # Get user's registered credentials
        credentials = await self.get_user_credentials(user_id)

        # Create authentication challenge
        auth_data, state = self.server.authenticate_begin(credentials)

        # Store state for verification
        await self.store_auth_state(user_id, state)

        return auth_data

    async def complete_authentication(
        self,
        user_id: str,
        credential_id: bytes,
        client_data: bytes,
        auth_data: bytes,
        signature: bytes
    ) -> Optional[str]:
        """Complete FIDO2 authentication."""

        # Retrieve state and credential
        state = await self.get_auth_state(user_id)
        credential = await self.get_credential(credential_id)

        # Verify authentication
        self.server.authenticate_complete(
            state,
            credentials=[credential],
            credential_id=credential_id,
            client_data=client_data,
            auth_data=auth_data,
            signature=signature
        )

        # Update sign count (prevent credential cloning)
        await self.update_sign_count(
            credential_id,
            auth_data.sign_count
        )

        # Create AAL3 session
        session_token = await self.create_session(
            user_id=user_id,
            aal="AAL3",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        return session_token
```

## Federation Assurance Levels (FAL)

FAL defines the strength of the assertion protocol used to communicate authentication and attribute information.

### FAL1 - Bearer Assertion

**Requirements**:
- Bearer assertion (possession is proof)
- Signed by IdP
- Transmitted over authenticated protected channel (TLS)

**Use Cases**:
- Low-risk federated applications
- Internal enterprise SSO
- Read-only resource access

### FAL2 - Signed Assertion

**Requirements**:
- All FAL1 requirements
- Assertion signed with approved algorithm
- Reference to authentication event
- Assertion includes expiration

**Use Cases**:
- Medium-risk federated applications
- Cross-organization federation
- API access with delegated permissions

### FAL3 - Signed and Encrypted, Holder-of-Key

**Requirements**:
- All FAL2 requirements
- Assertion encrypted to relying party
- Holder-of-key binding (proof of possession)
- Key confirmed by IdP

**Use Cases**:
- High-risk federated applications
- Government cross-agency federation
- Healthcare information exchange

## Applying NIST 800-63 to Infiquetra

### Recommended Assurance Levels

**For Infiquetra Wallet Service**:
- **IAL2**: Vehicle custody involves financial value, requires identity verification
- **AAL2**: Multi-factor authentication required for all operations
- **FAL2**: If federation needed, use signed assertions

**For Infiquetra Identity Service**:
- **IAL2**: KYC verification for high-value operations
- **AAL2**: Minimum for production systems
- **AAL3**: Consider for administrative access

### Implementation Priorities

1. **Phase 1**: Implement AAL2 (MFA) across all services
2. **Phase 2**: Establish IAL2 identity proofing for wallet creation
3. **Phase 3**: Add AAL3 options for high-security users
4. **Phase 4**: Federation support if cross-organization access needed

### Compliance Checklist

**IAL2 Compliance**:
- [ ] Collect government-issued ID
- [ ] Validate document authenticity
- [ ] Verify biometric match (facial comparison)
- [ ] Resolve against authoritative source
- [ ] Check for duplicate enrollments
- [ ] Confirm address (separate piece of evidence)
- [ ] Document evidence retention policy
- [ ] Implement fraud detection

**AAL2 Compliance**:
- [ ] Implement MFA for all users
- [ ] Support TOTP or hardware tokens
- [ ] Check passwords against breach databases
- [ ] Implement rate limiting on authentication
- [ ] Require reauthentication for sensitive operations
- [ ] Session timeout (max 12 hours idle)
- [ ] Secure credential recovery process

**General Requirements**:
- [ ] TLS 1.2+ for all connections
- [ ] Encrypt PII at rest
- [ ] Audit logging of authentication events
- [ ] Privacy policy with data retention
- [ ] Breach notification procedures
- [ ] User consent for biometric collection

## References

- [NIST SP 800-63-3: Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [NIST SP 800-63A: Enrollment and Identity Proofing](https://pages.nist.gov/800-63-3/sp800-63a.html)
- [NIST SP 800-63B: Authentication and Lifecycle Management](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [NIST SP 800-63C: Federation and Assertions](https://pages.nist.gov/800-63-3/sp800-63c.html)
