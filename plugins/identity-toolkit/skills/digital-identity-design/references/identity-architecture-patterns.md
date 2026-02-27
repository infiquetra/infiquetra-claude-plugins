# Identity Architecture Patterns

This document describes common architectural patterns for digital identity systems, wallet implementations, and credential management.

## Table of Contents

- [Wallet Architecture Patterns](#wallet-architecture-patterns)
- [Authentication Patterns](#authentication-patterns)
- [Key Management Patterns](#key-management-patterns)
- [Credential Lifecycle Patterns](#credential-lifecycle-patterns)
- [Federation Patterns](#federation-patterns)
- [Recovery Patterns](#recovery-patterns)

## Wallet Architecture Patterns

### Pattern 1: Custodial Wallet

**Description**: Service provider controls private keys on behalf of users.

**Architecture**:
```
┌─────────────┐
│   Client    │
│  (Browser/  │
│   Mobile)   │
└──────┬──────┘
       │ HTTPS
       │ (Username/Password + MFA)
       ▼
┌─────────────────────────────┐
│   Identity Service          │
│   - Authentication          │
│   - Session Management      │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Wallet Service            │
│   - Key Management (KMS)    │
│   - Transaction Signing     │
│   - Balance Tracking        │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Key Management Service    │
│   (AWS KMS, Azure Key Vault)│
│   - Private Keys (encrypted)│
│   - Signing Operations      │
└─────────────────────────────┘
```

**Components**:

1. **Identity Service**:
   - User authentication (username/password + MFA)
   - Session token generation (JWT)
   - Authorization decisions

2. **Wallet Service**:
   - Wallet creation and management
   - Transaction construction
   - Balance queries
   - Delegation to KMS for signing

3. **Key Management Service (KMS)**:
   - Private key generation
   - Secure key storage (HSM-backed)
   - Signing operations (keys never leave HSM)
   - Key rotation

**Data Flow - Transaction Signing**:
```
1. User → Identity Service: Authenticate
2. Identity Service → User: JWT token
3. User → Wallet Service: Sign transaction + JWT
4. Wallet Service → Identity Service: Validate JWT
5. Wallet Service: Construct transaction
6. Wallet Service → KMS: Sign with user's key
7. KMS → Wallet Service: Signature
8. Wallet Service → Blockchain: Broadcast transaction
9. Wallet Service → User: Transaction ID
```

**Implementation Example** (Python/AWS):
```python
from dataclasses import dataclass
from typing import Optional
import boto3

@dataclass
class Wallet:
    user_id: str
    kms_key_id: str
    public_address: str
    created_at: str

class CustodialWalletService:
    def __init__(self):
        self.kms = boto3.client('kms')
        self.dynamodb = boto3.resource('dynamodb')
        self.wallets_table = self.dynamodb.Table('wallets')

    async def create_wallet(self, user_id: str) -> Wallet:
        """Create a new custodial wallet for user."""

        # Generate key in KMS (never exposed)
        key_response = self.kms.create_key(
            Description=f'Wallet key for user {user_id}',
            KeyUsage='SIGN_VERIFY',
            KeySpec='ECC_NIST_P256',
            Tags=[
                {'TagKey': 'user_id', 'TagValue': user_id},
                {'TagKey': 'purpose', 'TagValue': 'wallet'}
            ]
        )

        kms_key_id = key_response['KeyMetadata']['KeyId']

        # Derive public address from public key
        public_key = self.kms.get_public_key(KeyId=kms_key_id)
        public_address = self._derive_address(public_key['PublicKey'])

        # Store wallet metadata
        wallet = Wallet(
            user_id=user_id,
            kms_key_id=kms_key_id,
            public_address=public_address,
            created_at=datetime.utcnow().isoformat()
        )

        self.wallets_table.put_item(Item=wallet.__dict__)

        return wallet

    async def sign_transaction(
        self,
        user_id: str,
        transaction_data: bytes
    ) -> bytes:
        """Sign transaction with user's key."""

        # Get user's wallet
        response = self.wallets_table.get_item(
            Key={'user_id': user_id}
        )

        if 'Item' not in response:
            raise ValueError(f"No wallet found for user {user_id}")

        wallet = Wallet(**response['Item'])

        # Sign with KMS (key never leaves HSM)
        signature_response = self.kms.sign(
            KeyId=wallet.kms_key_id,
            Message=transaction_data,
            MessageType='RAW',
            SigningAlgorithm='ECDSA_SHA_256'
        )

        return signature_response['Signature']
```

**Pros**:
- ✅ Familiar UX (username/password)
- ✅ Account recovery possible
- ✅ No seed phrase management for users
- ✅ Service can assist with transactions

**Cons**:
- ❌ Service is custodian (regulatory burden)
- ❌ Single point of compromise
- ❌ Trust requirement (service could misuse keys)
- ❌ KYC/AML requirements apply

**Best For**:
- Consumer applications
- Users new to crypto/digital identity
- Regulated financial services
- Enterprise solutions

---

### Pattern 2: Non-Custodial Wallet

**Description**: User controls private keys entirely. Keys never leave user's device.

**Architecture**:
```
┌──────────────────────────────┐
│   Client (Browser/Mobile)    │
│                              │
│  ┌────────────────────────┐  │
│  │  Wallet Logic          │  │
│  │  - Key Generation      │  │
│  │  - Transaction Signing │  │
│  │  - Seed Management     │  │
│  └────────────────────────┘  │
│            │                 │
│            ▼                 │
│  ┌────────────────────────┐  │
│  │  Secure Storage        │  │
│  │  (Keychain/Keystore/   │  │
│  │   Secure Enclave)      │  │
│  └────────────────────────┘  │
└──────────┬───────────────────┘
           │ HTTPS
           │ (Read-only queries)
           ▼
┌─────────────────────────────┐
│   Blockchain Node           │
│   - Balance Queries         │
│   - Transaction Broadcast   │
│   - Block Data              │
└─────────────────────────────┘
```

**Components**:

1. **Client-Side Wallet**:
   - HD wallet key derivation (BIP-32/BIP-44)
   - Transaction construction and signing
   - Seed phrase generation (BIP-39)
   - Local secure storage

2. **Secure Storage**:
   - iOS: Keychain (backed by Secure Enclave)
   - Android: Keystore (backed by TEE/StrongBox)
   - Browser: Web Crypto API + IndexedDB (encrypted)

3. **Blockchain Node** (read-only):
   - Balance queries
   - Transaction history
   - Transaction broadcasting
   - No authentication required

**Data Flow - Transaction Signing**:
```
1. User: Initiate transaction
2. Client: Retrieve key from secure storage
3. Client: Construct transaction
4. Client: Sign transaction locally
5. Client → Blockchain Node: Broadcast signed transaction
6. Blockchain Node → Client: Transaction ID
```

**Implementation Example** (TypeScript/React Native):
```typescript
import * as bip39 from 'bip39';
import { HDKey } from '@scure/bip32';
import * as Keychain from 'react-native-keychain';

class NonCustodialWallet {
  private readonly SEED_KEY = 'wallet_seed';
  private readonly KEY_PATH = "m/44'/60'/0'/0/0"; // Ethereum BIP-44

  async createWallet(): Promise<{ address: string; mnemonic: string }> {
    // Generate random mnemonic (12 or 24 words)
    const mnemonic = bip39.generateMnemonic(256); // 24 words

    // Derive seed from mnemonic
    const seed = await bip39.mnemonicToSeed(mnemonic);

    // Store seed in secure storage (encrypted by OS)
    await Keychain.setGenericPassword(
      this.SEED_KEY,
      seed.toString('hex'),
      {
        accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        securityLevel: Keychain.SECURITY_LEVEL.SECURE_HARDWARE
      }
    );

    // Derive address
    const hdKey = HDKey.fromMasterSeed(seed);
    const derived = hdKey.derive(this.KEY_PATH);
    const address = this.deriveAddress(derived.publicKey!);

    return { address, mnemonic };
  }

  async signTransaction(txData: TransactionData): Promise<string> {
    // Retrieve seed from secure storage
    const credentials = await Keychain.getGenericPassword({
      service: this.SEED_KEY
    });

    if (!credentials) {
      throw new Error('Wallet not initialized');
    }

    const seed = Buffer.from(credentials.password, 'hex');

    // Derive private key
    const hdKey = HDKey.fromMasterSeed(seed);
    const derived = hdKey.derive(this.KEY_PATH);
    const privateKey = derived.privateKey!;

    // Sign transaction
    const tx = this.constructTransaction(txData);
    const signature = await this.sign(tx, privateKey);

    // Securely clear private key from memory
    privateKey.fill(0);

    return signature;
  }

  async exportSeedPhrase(): Promise<string> {
    // Require user authentication before export
    const biometricAuth = await this.authenticateBiometric();
    if (!biometricAuth) {
      throw new Error('Authentication required');
    }

    const credentials = await Keychain.getGenericPassword({
      service: this.SEED_KEY
    });

    if (!credentials) {
      throw new Error('Wallet not initialized');
    }

    const seed = Buffer.from(credentials.password, 'hex');
    const mnemonic = bip39.entropyToMnemonic(seed);

    return mnemonic;
  }

  private deriveAddress(publicKey: Uint8Array): string {
    // Ethereum address derivation example
    const hash = keccak256(publicKey.slice(1)); // Remove 0x04 prefix
    return '0x' + hash.slice(-20).toString('hex');
  }
}
```

**Pros**:
- ✅ User sovereignty (full control)
- ✅ No custodial liability
- ✅ Privacy-preserving (minimal server data)
- ✅ Resistant to service compromise

**Cons**:
- ❌ Users must secure seed phrase
- ❌ No recovery if seed lost
- ❌ More complex UX
- ❌ User responsible for key security

**Best For**:
- Crypto-native users
- Privacy-focused applications
- Decentralized applications (dApps)
- Users who want full control

---

### Pattern 3: Hybrid Wallet (Social Recovery)

**Description**: User controls keys but can recover using trusted contacts.

**Architecture**:
```
┌────────────────────────────┐
│   Primary Device           │
│   - Full wallet control    │
│   - Private key            │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│   Recovery Contract        │
│   (Smart Contract or       │
│    Threshold Signing)      │
│                            │
│   Guardians:               │
│   - Guardian 1 (friend)    │
│   - Guardian 2 (family)    │
│   - Guardian 3 (device)    │
│                            │
│   Threshold: 2 of 3        │
└────────────────────────────┘
```

**Components**:

1. **Primary Wallet**: User's main device with full control
2. **Guardian Wallets**: Trusted contacts with partial control
3. **Recovery Contract**: Smart contract or threshold signature scheme
4. **Threshold**: Minimum guardians needed for recovery (e.g., 2 of 3)

**Recovery Flow**:
```
1. User loses primary device
2. User contacts guardians
3. Guardians approve recovery (2 of 3)
4. Recovery contract creates new wallet
5. Assets transferred to new wallet
6. User regains access
```

**Implementation Example** (Smart Contract):
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SocialRecoveryWallet {
    address public owner;
    mapping(address => bool) public guardians;
    uint256 public threshold;
    uint256 public guardianCount;

    struct RecoveryRequest {
        address newOwner;
        uint256 approvalCount;
        mapping(address => bool) approvals;
        bool executed;
    }

    RecoveryRequest public activeRecovery;

    event RecoveryInitiated(address indexed initiator, address indexed newOwner);
    event RecoveryApproved(address indexed guardian, address indexed newOwner);
    event RecoveryExecuted(address indexed oldOwner, address indexed newOwner);
    event GuardianAdded(address indexed guardian);
    event GuardianRemoved(address indexed guardian);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier onlyGuardian() {
        require(guardians[msg.sender], "Not guardian");
        _;
    }

    constructor(address[] memory _guardians, uint256 _threshold) {
        require(_threshold > 0 && _threshold <= _guardians.length, "Invalid threshold");

        owner = msg.sender;
        threshold = _threshold;

        for (uint256 i = 0; i < _guardians.length; i++) {
            address guardian = _guardians[i];
            require(guardian != address(0) && !guardians[guardian], "Invalid guardian");

            guardians[guardian] = true;
            emit GuardianAdded(guardian);
        }

        guardianCount = _guardians.length;
    }

    function initiateRecovery(address _newOwner) external onlyGuardian {
        require(_newOwner != address(0), "Invalid new owner");
        require(!activeRecovery.executed, "Recovery in progress");

        activeRecovery.newOwner = _newOwner;
        activeRecovery.approvalCount = 1;
        activeRecovery.approvals[msg.sender] = true;
        activeRecovery.executed = false;

        emit RecoveryInitiated(msg.sender, _newOwner);

        // Execute immediately if threshold is 1
        if (threshold == 1) {
            _executeRecovery();
        }
    }

    function approveRecovery() external onlyGuardian {
        require(!activeRecovery.executed, "Recovery already executed");
        require(!activeRecovery.approvals[msg.sender], "Already approved");

        activeRecovery.approvals[msg.sender] = true;
        activeRecovery.approvalCount++;

        emit RecoveryApproved(msg.sender, activeRecovery.newOwner);

        // Execute if threshold reached
        if (activeRecovery.approvalCount >= threshold) {
            _executeRecovery();
        }
    }

    function _executeRecovery() private {
        require(activeRecovery.approvalCount >= threshold, "Threshold not met");

        address oldOwner = owner;
        owner = activeRecovery.newOwner;
        activeRecovery.executed = true;

        emit RecoveryExecuted(oldOwner, owner);
    }

    function addGuardian(address _guardian) external onlyOwner {
        require(_guardian != address(0), "Invalid guardian");
        require(!guardians[_guardian], "Already guardian");

        guardians[_guardian] = true;
        guardianCount++;

        emit GuardianAdded(_guardian);
    }

    function removeGuardian(address _guardian) external onlyOwner {
        require(guardians[_guardian], "Not a guardian");
        require(guardianCount > threshold, "Would break threshold");

        guardians[_guardian] = false;
        guardianCount--;

        emit GuardianRemoved(_guardian);
    }
}
```

**Pros**:
- ✅ User control with safety net
- ✅ Recovery without seed phrase
- ✅ Distributed trust (no single point of failure)
- ✅ Better UX than pure non-custodial

**Cons**:
- ❌ Requires trusted contacts
- ❌ More complex setup
- ❌ Guardian coordination needed
- ❌ Potential for social engineering

**Best For**:
- Users wanting control with recovery
- Family/friend support networks
- Long-term storage (cold wallet alternative)

---

## Authentication Patterns

### Pattern 4: DID-Based Authentication

**Description**: Decentralized identifier-based authentication without passwords.

**Flow**:
```
1. User → Service: "I am did:example:123"
2. Service → User: Challenge (nonce)
3. User: Sign challenge with private key
4. User → Service: Signed challenge
5. Service: Verify signature using DID document
6. Service → User: Access granted
```

**Implementation**:
```python
from typing import Optional
import did_jwt

class DIDAuthentication:
    def __init__(self, did_resolver):
        self.resolver = did_resolver
        self.challenges = {}  # In production: use Redis with TTL

    async def create_challenge(self, did: str) -> dict:
        """Create authentication challenge for DID."""
        import secrets

        # Generate random nonce
        nonce = secrets.token_urlsafe(32)

        # Store challenge (expires in 5 minutes)
        self.challenges[did] = {
            'nonce': nonce,
            'created_at': datetime.utcnow()
        }

        return {
            'did': did,
            'nonce': nonce,
            'expires_in': 300
        }

    async def verify_challenge_response(
        self,
        did: str,
        signed_challenge: str
    ) -> Optional[str]:
        """Verify signed challenge and create session."""

        # Get stored challenge
        challenge = self.challenges.get(did)
        if not challenge:
            return None

        # Check expiration
        age = datetime.utcnow() - challenge['created_at']
        if age.total_seconds() > 300:
            del self.challenges[did]
            return None

        # Resolve DID to get public key
        did_document = await self.resolver.resolve(did)
        public_key = did_document['verificationMethod'][0]['publicKeyJwk']

        # Verify signature
        try:
            decoded = did_jwt.verify(
                signed_challenge,
                public_key
            )

            # Check nonce matches
            if decoded['nonce'] != challenge['nonce']:
                return None

            # Clean up challenge
            del self.challenges[did]

            # Create session
            session_token = self.create_session(did)
            return session_token

        except Exception as e:
            print(f"Verification failed: {e}")
            return None
```

**Pros**:
- ✅ No passwords
- ✅ Phishing-resistant
- ✅ Decentralized (no identity provider)
- ✅ Cryptographically secure

**Cons**:
- ❌ Requires key management
- ❌ Less familiar to users
- ❌ Browser/device support needed

---

### Pattern 5: OAuth 2.0 with JWT Tokens

**Description**: Standard OAuth 2.0 flow with JWT bearer tokens.

**Flow**:
```
1. User → Client: Login request
2. Client → Auth Server: Authorization request
3. Auth Server → User: Login page
4. User → Auth Server: Credentials
5. Auth Server → Client: Authorization code
6. Client → Auth Server: Exchange code for token
7. Auth Server → Client: JWT access token
8. Client → Resource Server: API request + JWT
9. Resource Server: Validate JWT signature
10. Resource Server → Client: Protected resource
```

**JWT Structure**:
```json
{
  "header": {
    "alg": "ES256",
    "typ": "JWT",
    "kid": "key-1"
  },
  "payload": {
    "iss": "https://auth.vecu.com",
    "sub": "user-123",
    "aud": "wallet-service",
    "exp": 1735689600,
    "iat": 1735686000,
    "scope": "wallet:read wallet:transfer"
  },
  "signature": "..."
}
```

**Implementation**:
```python
import jwt
from datetime import datetime, timedelta

class JWTAuthenticationService:
    def __init__(self, private_key, public_key, issuer):
        self.private_key = private_key
        self.public_key = public_key
        self.issuer = issuer

    def generate_token(
        self,
        user_id: str,
        scopes: list[str],
        expires_in: int = 3600
    ) -> str:
        """Generate JWT access token."""
        now = datetime.utcnow()
        exp = now + timedelta(seconds=expires_in)

        payload = {
            "iss": self.issuer,
            "sub": user_id,
            "aud": "services",
            "iat": now.timestamp(),
            "exp": exp.timestamp(),
            "scope": " ".join(scopes)
        }

        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers={"kid": "key-1"}
        )

        return token

    def verify_token(self, token: str) -> dict:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["ES256"],
                issuer=self.issuer,
                audience="services"
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
```

**Pros**:
- ✅ Industry standard
- ✅ Widely supported
- ✅ Stateless verification
- ✅ Scalable

**Cons**:
- ❌ Token revocation challenging
- ❌ Token size (all claims in token)
- ❌ Vulnerable if not implemented correctly

---

## Key Management Patterns

### Pattern 6: Hierarchical Deterministic (HD) Wallets

**Description**: Single seed generates unlimited keys deterministically.

**BIP-32 Derivation**:
```
Master Seed (128-256 bits)
    ↓
Master Private Key + Chain Code
    ↓
Child Private Key (m/44'/60'/0'/0/0)
    ↓
Public Key
    ↓
Address
```

**BIP-44 Path Structure**:
```
m / purpose' / coin_type' / account' / change / address_index

Examples:
- Bitcoin: m/44'/0'/0'/0/0
- Ethereum: m/44'/60'/0'/0/0
- Custom: m/44'/9999'/0'/0/0
```

**Implementation**:
```python
from mnemonic import Mnemonic
from bip32 import BIP32

class HDWalletManager:
    def __init__(self):
        self.mnemo = Mnemonic("english")

    def generate_wallet(self) -> dict:
        """Generate new HD wallet."""
        # Generate mnemonic (12 or 24 words)
        mnemonic = self.mnemo.generate(strength=256)  # 24 words

        # Derive seed from mnemonic
        seed = self.mnemo.to_seed(mnemonic)

        # Create BIP32 root
        bip32 = BIP32.from_seed(seed)

        return {
            "mnemonic": mnemonic,
            "seed": seed.hex(),
            "master_key": bip32.get_xpriv()
        }

    def derive_address(
        self,
        mnemonic: str,
        coin_type: int = 60,  # Ethereum
        account: int = 0,
        change: int = 0,
        index: int = 0
    ) -> dict:
        """Derive address at specific path."""
        # Derive seed
        seed = self.mnemo.to_seed(mnemonic)
        bip32 = BIP32.from_seed(seed)

        # BIP-44 path
        path = f"m/44'/{coin_type}'/{account}'/{change}/{index}"

        # Derive key
        derived = bip32.get_privkey_from_path(path)
        public_key = bip32.get_pubkey_from_path(path)

        return {
            "path": path,
            "private_key": derived.hex(),
            "public_key": public_key.hex(),
            "address": self.derive_address_from_public_key(public_key)
        }
```

**Pros**:
- ✅ Single backup (seed phrase)
- ✅ Unlimited addresses
- ✅ Deterministic (reproducible)
- ✅ Industry standard

**Cons**:
- ❌ Seed phrase must be secured
- ❌ All keys compromised if seed leaked

---

## Summary

This document covered the most common identity architecture patterns. Key takeaways:

1. **Choose wallet type based on use case**:
   - Custodial: Consumer-friendly, regulated
   - Non-custodial: Privacy, user sovereignty
   - Hybrid: Balance of both

2. **Authentication should match risk**:
   - Low risk: Password-based
   - Medium risk: OAuth + JWT
   - High risk: DID-based, hardware tokens

3. **Key management is critical**:
   - HD wallets for non-custodial
   - KMS/HSM for custodial
   - Social recovery for hybrid

4. **Consider recovery mechanisms**:
   - Custodial: Account recovery
   - Non-custodial: Seed phrase
   - Hybrid: Social recovery

Choose patterns that match your security requirements, regulatory environment, and user expectations.
