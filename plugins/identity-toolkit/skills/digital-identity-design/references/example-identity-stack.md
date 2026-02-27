# Infiquetra Identity Stack Reference

This document describes the current and planned identity architecture for Infiquetra (Infiquetra) services at your organization.

## Overview

Infiquetra implements a **custodial wallet architecture** with centralized identity management, designed to meet enterprise security requirements while providing a user-friendly experience.

## Current Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Infiquetra Identity Stack                     │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐        ┌──────────────────┐
│  Web/Mobile      │───────▶│  API Gateway     │
│  Applications    │        │  (AWS)           │
└──────────────────┘        └────────┬─────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
           ┌────────▼────────┐  ┌───▼────────┐  ┌───▼────────┐
           │  identity- │  │       │  │  Other     │
           │  service        │  │  wallet-   │  │  Services  │
           │                 │  │  service   │  │            │
           └────────┬────────┘  └─────┬──────┘  └────────────┘
                    │                 │
           ┌────────▼─────────────────▼────────┐
           │      AWS Cognito User Pools        │
           └────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │  AWS KMS    │   │  Secrets    │   │  DynamoDB   │
    │  (Keys)     │   │  Manager    │   │  (Metadata) │
    └─────────────┘   └─────────────┘   └─────────────┘
```

### identity-service

**Purpose**: Core identity management and authentication service.

**Responsibilities**:
- User registration and enrollment
- Authentication (username/password + MFA)
- JWT token generation and validation
- User profile management
- Identity verification (KYC) integration

**Tech Stack**:
- **Runtime**: Python 3.12 + AWS Lambda
- **Framework**: FastAPI
- **Authentication**: AWS Cognito
- **Database**: DynamoDB
- **API**: REST via API Gateway

**Key Endpoints**:
```
POST   /auth/register          - Register new user
POST   /auth/login             - Authenticate user
POST   /auth/refresh           - Refresh access token
GET    /auth/verify            - Verify JWT token
POST   /auth/mfa/enable        - Enable MFA for user
POST   /auth/mfa/verify        - Verify MFA code
GET    /users/{id}             - Get user profile
PUT    /users/{id}             - Update user profile
POST   /users/{id}/verify      - Initiate identity verification
```

**Authentication Flow**:
```python
# Example: Login with MFA
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
import boto3

logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver()

cognito = boto3.client('cognito-idp')
USER_POOL_ID = os.environ['COGNITO_USER_POOL_ID']
CLIENT_ID = os.environ['COGNITO_CLIENT_ID']

@app.post("/auth/login")
@tracer.capture_method
def login():
    """Authenticate user with Cognito."""
    body = app.current_event.json_body

    try:
        # Initiate auth with Cognito
        response = cognito.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': body['username'],
                'PASSWORD': body['password']
            }
        )

        # Check if MFA required
        if response.get('ChallengeName') == 'SOFTWARE_TOKEN_MFA':
            return {
                'challenge': 'MFA_REQUIRED',
                'session': response['Session']
            }

        # Return tokens
        return {
            'access_token': response['AuthenticationResult']['AccessToken'],
            'id_token': response['AuthenticationResult']['IdToken'],
            'refresh_token': response['AuthenticationResult']['RefreshToken'],
            'expires_in': response['AuthenticationResult']['ExpiresIn']
        }

    except cognito.exceptions.NotAuthorizedException:
        return {'error': 'Invalid credentials'}, 401
```

**Environment Variables**:
```bash
# Required for identity-service
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
JWT_SECRET_NAME=app/identity/jwt-secret
DYNAMODB_TABLE_NAME=users
SLED_API_KEY_SECRET=app/external/api-key
KYC_PROVIDER_API_KEY=app/kyc/api-key
```

---

### wallet-service

**Purpose**: Custodial wallet management for vehicle custody.

**Responsibilities**:
- Wallet creation and management
- Private key generation (via KMS)
- Transaction signing
- Balance tracking
- Transaction history

**Tech Stack**:
- **Runtime**: Python 3.12 + AWS Lambda
- **Framework**: FastAPI
- **Key Management**: AWS KMS
- **Database**: DynamoDB
- **API**: REST via API Gateway

**Key Endpoints**:
```
POST   /wallets                - Create new wallet
GET    /wallets/{id}           - Get wallet details
GET    /wallets/{id}/balance   - Get wallet balance
POST   /wallets/{id}/sign      - Sign transaction
GET    /wallets/{id}/history   - Get transaction history
POST   /wallets/{id}/transfer  - Transfer funds
```

**Wallet Management**:
```python
# Example: Create wallet and sign transaction
from dataclasses import dataclass
import boto3

kms = boto3.client('kms')
dynamodb = boto3.resource('dynamodb')
wallets_table = dynamodb.Table('wallets')

@dataclass
class Wallet:
    user_id: str
    wallet_id: str
    kms_key_id: str
    public_address: str
    created_at: str

@app.post("/wallets")
@tracer.capture_method
def create_wallet():
    """Create new custodial wallet for authenticated user."""
    user_id = app.current_event.request_context.authorizer.claims['sub']

    # Generate KMS key for user
    key_response = kms.create_key(
        Description=f'Infiquetra wallet for user {user_id}',
        KeyUsage='SIGN_VERIFY',
        KeySpec='ECC_NIST_P256',
        Tags=[
            {'TagKey': 'user_id', 'TagValue': user_id},
            {'TagKey': 'service', 'TagValue': 'wallet'},
            {'TagKey': 'component_id', 'TagValue': 'your-component-id'}
        ]
    )

    kms_key_id = key_response['KeyMetadata']['KeyId']

    # Get public key and derive address
    public_key_response = kms.get_public_key(KeyId=kms_key_id)
    public_address = derive_address(public_key_response['PublicKey'])

    # Store wallet metadata
    wallet_id = str(uuid.uuid4())
    wallet = Wallet(
        user_id=user_id,
        wallet_id=wallet_id,
        kms_key_id=kms_key_id,
        public_address=public_address,
        created_at=datetime.utcnow().isoformat()
    )

    wallets_table.put_item(Item=wallet.__dict__)

    return {
        'wallet_id': wallet_id,
        'public_address': public_address
    }

@app.post("/wallets/{wallet_id}/sign")
@tracer.capture_method
def sign_transaction(wallet_id: str):
    """Sign transaction with wallet's private key."""
    user_id = app.current_event.request_context.authorizer.claims['sub']
    body = app.current_event.json_body

    # Get wallet and verify ownership
    wallet_response = wallets_table.get_item(
        Key={'wallet_id': wallet_id}
    )

    if 'Item' not in wallet_response:
        return {'error': 'Wallet not found'}, 404

    wallet = Wallet(**wallet_response['Item'])

    if wallet.user_id != user_id:
        return {'error': 'Unauthorized'}, 403

    # Sign with KMS (key never leaves HSM)
    transaction_data = bytes.fromhex(body['transaction_hash'])

    signature_response = kms.sign(
        KeyId=wallet.kms_key_id,
        Message=transaction_data,
        MessageType='RAW',
        SigningAlgorithm='ECDSA_SHA_256'
    )

    return {
        'signature': signature_response['Signature'].hex(),
        'public_address': wallet.public_address
    }
```

**Environment Variables**:
```bash
# Required for wallet-service
DYNAMODB_WALLETS_TABLE=wallets
DYNAMODB_TRANSACTIONS_TABLE=transactions
KMS_KEY_ALIAS=alias/wallet-master
BLOCKCHAIN_RPC_URL=https://rpc.example.com
COMPONENT_ID=your-component-id
```

---

### AWS Cognito Integration

**User Pools Configuration**:
```yaml
UserPool:
  Type: AWS::Cognito::UserPool
  Properties:
    UserPoolName: user-pool
    Schema:
      - Name: email
        Required: true
        Mutable: false
      - Name: phone_number
        Required: false
        Mutable: true
    Policies:
      PasswordPolicy:
        MinimumLength: 12
        RequireUppercase: true
        RequireLowercase: true
        RequireNumbers: true
        RequireSymbols: true
    MfaConfiguration: OPTIONAL
    EnabledMfas:
      - SOFTWARE_TOKEN_MFA
    AccountRecoverySetting:
      RecoveryMechanisms:
        - Name: verified_email
          Priority: 1
        - Name: verified_phone_number
          Priority: 2
    UserAttributeUpdateSettings:
      AttributesRequireVerificationBeforeUpdate:
        - email
```

**Token Configuration**:
- **Access Token**: 60 minutes (API authorization)
- **ID Token**: 60 minutes (user claims)
- **Refresh Token**: 30 days (token renewal)

**JWT Claims**:
```json
{
  "sub": "12345678-1234-1234-1234-123456789012",
  "cognito:username": "user@example.com",
  "email": "user@example.com",
  "email_verified": true,
  "phone_number": "+15555551234",
  "phone_number_verified": true,
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX",
  "aud": "XXXXXXXXXXXXXXXXXXXXXXXXXX",
  "token_use": "access",
  "scope": "aws.cognito.signin.user.admin",
  "auth_time": 1735686000,
  "iat": 1735686000,
  "exp": 1735689600
}
```

---

### API Gateway Configuration

**Authorization**:
- **Cognito Authorizer**: Validates JWT tokens
- **Scopes**: Fine-grained permission control
- **Rate Limiting**: 1000 requests/second per account

**Request Flow**:
```
1. Client sends request with JWT in Authorization header
2. API Gateway validates JWT with Cognito
3. If valid, request forwarded to Lambda with user context
4. Lambda extracts user_id from context.authorizer.claims
5. Lambda processes request with user identity
```

**API Gateway Configuration** (CDK):
```python
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito

# Cognito authorizer
authorizer = apigw.CognitoUserPoolsAuthorizer(
    self,
    "AppApiAuthorizer",
    cognito_user_pools=[user_pool]
)

# API Gateway
api = apigw.RestApi(
    self,
    "AppApi",
    rest_api_name="Infiquetra API",
    description="Infiquetra API",
    default_cors_preflight_options=apigw.CorsOptions(
        allow_origins=apigw.Cors.ALL_ORIGINS,
        allow_methods=apigw.Cors.ALL_METHODS
    )
)

# Protected endpoint
wallets_resource = api.root.add_resource("wallets")
wallets_resource.add_method(
    "POST",
    apigw.LambdaIntegration(create_wallet_lambda),
    authorizer=authorizer,
    authorization_type=apigw.AuthorizationType.COGNITO
)
```

---

## Security Patterns

### Token Validation

All Infiquetra services validate JWT tokens:

```python
import jwt
import requests
from functools import wraps

class TokenValidator:
    def __init__(self, user_pool_id: str, region: str):
        self.user_pool_id = user_pool_id
        self.region = region
        self.jwks_url = (
            f"https://cognito-idp.{region}.amazonaws.com/"
            f"{user_pool_id}/.well-known/jwks.json"
        )
        self.jwks = self._fetch_jwks()

    def _fetch_jwks(self) -> dict:
        """Fetch JSON Web Key Set from Cognito."""
        response = requests.get(self.jwks_url)
        return response.json()

    def validate_token(self, token: str) -> dict:
        """Validate JWT token and return claims."""
        # Decode header to get key ID
        header = jwt.get_unverified_header(token)
        kid = header['kid']

        # Find matching key in JWKS
        key = next(
            (k for k in self.jwks['keys'] if k['kid'] == kid),
            None
        )

        if not key:
            raise ValueError('Public key not found')

        # Verify token
        claims = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=os.environ['COGNITO_CLIENT_ID'],
            issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"
        )

        return claims

# Decorator for protected endpoints
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return {'error': 'Missing authorization'}, 401

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        try:
            claims = validator.validate_token(token)
            request.user_id = claims['sub']
            return f(*args, **kwargs)
        except Exception as e:
            return {'error': 'Invalid token'}, 401

    return decorated_function
```

### Key Rotation

**KMS Key Rotation**:
- Automatic rotation enabled (yearly)
- No manual intervention required
- Old keys retained for decryption
- New keys used for signing

**JWT Secret Rotation**:
```python
# Rotate JWT signing secret
import boto3

secrets_manager = boto3.client('secretsmanager')

def rotate_jwt_secret():
    """Rotate JWT signing secret."""
    # Generate new secret
    new_secret = secrets.token_urlsafe(64)

    # Store in Secrets Manager
    secrets_manager.update_secret(
        SecretId='app/identity/jwt-secret',
        SecretString=new_secret
    )

    # Trigger application reload (Lambda function versions)
    lambda_client = boto3.client('lambda')
    lambda_client.publish_version(
        FunctionName='identity-service'
    )
```

### Audit Logging

All authentication and authorization events are logged:

```python
from aws_lambda_powertools import Logger

logger = Logger()

@logger.inject_lambda_context
def handler(event, context):
    """Lambda handler with automatic context logging."""

    # Log authentication attempt
    logger.info(
        "Authentication attempt",
        user_id=event['requestContext']['authorizer']['claims']['sub'],
        action="wallet_creation",
        ip_address=event['requestContext']['identity']['sourceIp']
    )

    # ... business logic ...

    # Log success
    logger.info(
        "Wallet created",
        user_id=user_id,
        wallet_id=wallet_id
    )
```

**Logs are sent to CloudWatch Logs with:**
- Request ID for tracing
- User ID for auditing
- IP address for security monitoring
- Timestamp for chronology

---

## Migration Paths

### Current State → W3C Verifiable Credentials

**Phase 1: Dual Mode** (6-12 months)
- Keep existing JWT authentication
- Add VC issuance service
- Issue VCs alongside JWT tokens
- Services accept both formats

**Phase 2: VC Adoption** (12-18 months)
- Encourage VC usage (incentives)
- Update documentation and SDKs
- Maintain JWT for legacy clients
- Monitor adoption metrics

**Phase 3: JWT Deprecation** (18-24 months)
- Announce JWT deprecation timeline
- Force VC migration for new users
- Sunset JWT endpoints
- Full VC-only authentication

**Implementation Example**:
```python
# Dual-mode authentication
def authenticate_user(credentials):
    """Support both JWT and VC authentication."""

    if is_jwt(credentials):
        # Legacy JWT path
        return validate_jwt_token(credentials)

    elif is_verifiable_credential(credentials):
        # New VC path
        return validate_verifiable_credential(credentials)

    else:
        raise AuthenticationError("Unsupported credential format")
```

### Custodial → Non-Custodial Option

**Hybrid Model**:
1. Default: Custodial (current)
2. Option: "Export to non-custodial"
3. User downloads seed phrase
4. Warning about responsibility
5. Wallet migrated to non-custodial mode
6. Keys removed from KMS

**Implementation**:
```python
@app.post("/wallets/{wallet_id}/export")
def export_to_non_custodial(wallet_id: str):
    """Export wallet to non-custodial mode."""

    # Verify user ownership
    wallet = get_wallet(wallet_id)

    # Get private key from KMS (one-time export)
    key_material = kms.get_key_material(wallet.kms_key_id)

    # Generate BIP-39 mnemonic from key
    mnemonic = key_to_mnemonic(key_material)

    # Mark wallet as non-custodial
    update_wallet_mode(wallet_id, mode="non_custodial")

    # Schedule key deletion from KMS (30 days)
    kms.schedule_key_deletion(
        KeyId=wallet.kms_key_id,
        PendingWindowInDays=30
    )

    # Return mnemonic (user must save)
    return {
        "mnemonic": mnemonic,
        "warning": "Save this seed phrase securely. We cannot recover it.",
        "key_deletion_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
    }
```

---

## Best Practices for Infiquetra Development

### 1. Always Validate JWT Tokens

```python
# Use TokenValidator class (shown above)
validator = TokenValidator(
    user_pool_id=os.environ['COGNITO_USER_POOL_ID'],
    region='us-east-1'
)

@require_auth
def protected_endpoint():
    user_id = request.user_id  # Set by decorator
    # ... business logic ...
```

### 2. Use KMS for All Key Operations

```python
# NEVER export private keys
# ALWAYS use KMS signing

# ✅ Correct
signature = kms.sign(KeyId=key_id, Message=data)

# ❌ Wrong
private_key = kms.export_key(key_id)  # Don't do this!
signature = sign_locally(private_key, data)
```

### 3. Implement Rate Limiting

```python
from functools import wraps
import time

def rate_limit(max_calls: int, period: int):
    """Rate limit decorator."""
    def decorator(f):
        calls = {}

        @wraps(f)
        def wrapped(*args, **kwargs):
            now = time.time()
            user_id = request.user_id

            # Clean old calls
            calls[user_id] = [
                call for call in calls.get(user_id, [])
                if call > now - period
            ]

            if len(calls.get(user_id, [])) >= max_calls:
                return {'error': 'Rate limit exceeded'}, 429

            calls.setdefault(user_id, []).append(now)
            return f(*args, **kwargs)

        return wrapped
    return decorator

@app.post("/wallets/{wallet_id}/transfer")
@require_auth
@rate_limit(max_calls=10, period=60)  # 10 transfers per minute
def transfer_funds(wallet_id: str):
    # ... transfer logic ...
```

### 4. Log All Security Events

```python
logger.info(
    "Security event",
    event_type="authentication_failed",
    user_id=user_id,
    reason="invalid_mfa_code",
    ip_address=request.remote_addr
)
```

### 5. Encrypt Sensitive Data

```python
# Use AWS KMS for encryption
def encrypt_sensitive_data(data: str) -> str:
    """Encrypt data using KMS."""
    response = kms.encrypt(
        KeyId='alias/data-encryption',
        Plaintext=data.encode()
    )
    return base64.b64encode(response['CiphertextBlob']).decode()

def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt data using KMS."""
    ciphertext = base64.b64decode(encrypted_data)
    response = kms.decrypt(CiphertextBlob=ciphertext)
    return response['Plaintext'].decode()
```

---

## Testing Strategies

### Unit Testing

```python
import pytest
from moto import mock_kms, mock_dynamodb2

@mock_kms
@mock_dynamodb2
def test_create_wallet():
    """Test wallet creation."""
    # Setup mocks
    setup_mocked_kms()
    setup_mocked_dynamodb()

    # Test
    response = create_wallet(user_id="test-user")

    assert response['wallet_id']
    assert response['public_address']
```

### Integration Testing

```python
def test_end_to_end_authentication():
    """Test complete authentication flow."""

    # Register user
    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!"
        }
    )
    assert register_response.status_code == 200

    # Login
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": "test@example.com",
            "password": "SecurePass123!"
        }
    )
    assert login_response.status_code == 200

    access_token = login_response.json()['access_token']

    # Create wallet (authenticated)
    wallet_response = requests.post(
        f"{BASE_URL}/wallets",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert wallet_response.status_code == 200
```

---

## Related Services

### custody-service
Manages vehicle custody transactions and state transitions.

### document-service
Stores and retrieves vehicle custody documents.

### notification-service
Sends notifications for custody events (email, SMS, push).

---

## Resources

**Internal Documentation**:
- [Infiquetra Architecture Guide](https://github.com/infiquetra/infiquetra-claude-plugins/docs/ARCHITECTURE.md)
- [Infiquetra Security Standards](https://github.com/infiquetra/infiquetra-claude-plugins/docs/SECURITY.md)
- [your organization CDK Patterns](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html)

**AWS Documentation**:
- [AWS KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)
- [Amazon Cognito Security](https://docs.aws.amazon.com/cognito/latest/developerguide/security.html)
- [API Gateway Authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-integrate-with-cognito.html)

**Standards**:
- [NIST 800-63 Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
