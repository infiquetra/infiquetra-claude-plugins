---
name: python-patterns
description: Python patterns for serverless applications (Lambda Powertools, DynamoDB, error handling, secrets)
when_to_use: |
  Use this skill when the user wants to:
  - Set up Lambda Powertools
  - Configure structured logging
  - Access DynamoDB
  - Use base classes for Python services
  - Handle AWS authentication
  - Manage secrets
  - Use Lambda Powertools decorators
  - Implement standard error handling patterns
---

# Python Patterns Guide

You are helping the user implement Python patterns for serverless applications on AWS.

## Lambda Powertools Patterns

### Complete Lambda Handler Setup

```python
# src/handler.py

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit

# Initialize Powertools (service name for organized logs/traces)
logger = Logger(service="my-service")
tracer = Tracer(service="my-service")
metrics = Metrics(namespace="MyServiceMetrics", service="wallet-api")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler with full Powertools integration."""
    logger.info("Processing request", extra={"request_type": event.get("type")})

    # Add metrics
    metrics.add_metric(name="RequestReceived", unit=MetricUnit.Count, value=1)

    try:
        result = process_request(event)

        metrics.add_metric(name="SuccessfulRequest", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "body": result,
        }

    except Exception as e:
        logger.exception("Request processing failed")
        metrics.add_metric(name="FailedRequest", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": {"error": "Internal server error"},
        }


@tracer.capture_method
def process_request(event: dict) -> dict:
    """Process request with automatic tracing."""
    # Business logic here
    return {"processed": True}
```

### Structured Logging

```python
from aws_lambda_powertools import Logger

logger = Logger(service="my-service")


def handler(event, context):
    # Structured logging with context
    logger.info(
        "Wallet operation started",
        extra={
            "user_id": event["userId"],
            "wallet_id": event["walletId"],
            "operation": "balance_check",
        },
    )

    # Append keys to all subsequent logs
    logger.append_keys(user_id=event["userId"])

    logger.info("Fetching wallet")  # Includes user_id automatically
    logger.info("Balance retrieved")  # Also includes user_id

    # Remove keys when done
    logger.remove_keys(["user_id"])
```

### Metrics and Dimensions

```python
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

metrics = Metrics(namespace="MyServiceMetrics")


@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    # Add environment dimension to all metrics
    metrics.add_dimension(name="Environment", value="prod")
    metrics.add_dimension(name="Region", value="us-east-1")

    # Business metrics
    metrics.add_metric(name="WalletCreated", unit=MetricUnit.Count, value=1)
    metrics.add_metric(
        name="TransactionAmount", unit=MetricUnit.Count, value=event["amount"]
    )
    metrics.add_metric(
        name="ProcessingTime", unit=MetricUnit.Milliseconds, value=245
    )

    return {"statusCode": 200}
```

### Distributed Tracing

```python
from aws_lambda_powertools import Tracer

tracer = Tracer(service="my-service")


@tracer.capture_lambda_handler
def handler(event, context):
    # Handler is automatically traced
    user_id = event["userId"]

    # Trace downstream calls
    wallet = get_wallet(user_id)

    return {"statusCode": 200, "wallet": wallet}


@tracer.capture_method
def get_wallet(user_id: str) -> dict:
    """Method automatically traced with timing."""
    # Add searchable annotations (indexed in X-Ray)
    tracer.put_annotation(key="user_id", value=user_id)

    # Add metadata (visible but not indexed)
    tracer.put_metadata(key="cache_hit", value=False)

    wallet = fetch_from_dynamodb(user_id)

    tracer.put_annotation(key="wallet_type", value=wallet.get("type"))

    return wallet
```

## DynamoDB Patterns

### Basic DynamoDB Service

```python
# src/db/service.py

import os
import boto3
from typing import Optional
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")


class DynamoDBService:
    """DynamoDB operations for Infiquetra services."""

    def __init__(self, table_name: str | None = None):
        self.table_name = table_name or os.environ["TABLE_NAME"]
        self.table = dynamodb.Table(self.table_name)

    @tracer.capture_method
    def get_item(self, pk: str, sk: str) -> Optional[dict]:
        """Get single item by primary key."""
        logger.debug("Getting item", extra={"pk": pk, "sk": sk})

        response = self.table.get_item(Key={"pk": pk, "sk": sk})

        return response.get("Item")

    @tracer.capture_method
    def put_item(self, pk: str, sk: str, data: dict) -> bool:
        """Store item in DynamoDB."""
        item = {"pk": pk, "sk": sk, **data}

        logger.info("Storing item", extra={"pk": pk, "sk": sk})

        self.table.put_item(Item=item)

        return True

    @tracer.capture_method
    def query_by_pk(self, pk: str, sk_prefix: str | None = None) -> list[dict]:
        """Query items by partition key with optional sort key prefix."""
        logger.debug("Querying items", extra={"pk": pk, "sk_prefix": sk_prefix})

        if sk_prefix:
            response = self.table.query(
                KeyConditionExpression="pk = :pk AND begins_with(sk, :sk_prefix)",
                ExpressionAttributeValues={":pk": pk, ":sk_prefix": sk_prefix},
            )
        else:
            response = self.table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": pk},
            )

        return response.get("Items", [])

    @tracer.capture_method
    def update_item(self, pk: str, sk: str, updates: dict) -> bool:
        """Update item attributes."""
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates.keys())
        expr_values = {f":{k}": v for k, v in updates.items()}

        logger.info("Updating item", extra={"pk": pk, "sk": sk})

        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )

        return True

    @tracer.capture_method
    def delete_item(self, pk: str, sk: str) -> bool:
        """Delete item."""
        logger.info("Deleting item", extra={"pk": pk, "sk": sk})

        self.table.delete_item(Key={"pk": pk, "sk": sk})

        return True
```

### Single Table Design Pattern

```python
# Infiquetra standard: Single table with composite keys

# Key structure:
# pk = "ENTITY#<id>"
# sk = "TYPE#<subid>" or "METADATA"

# Examples:
# Wallet metadata:    pk="WALLET#123",    sk="METADATA"
# Wallet transaction: pk="WALLET#123",    sk="TXN#abc"
# User wallet:        pk="USER#456",      sk="WALLET#123"


class WalletRepository:
    """Repository pattern for wallet data."""

    def __init__(self):
        self.db = DynamoDBService()

    def get_wallet(self, wallet_id: str) -> Optional[dict]:
        """Get wallet by ID."""
        return self.db.get_item(pk=f"WALLET#{wallet_id}", sk="METADATA")

    def create_wallet(self, wallet_id: str, user_id: str, wallet_type: str) -> dict:
        """Create new wallet."""
        wallet = {
            "wallet_id": wallet_id,
            "user_id": user_id,
            "type": wallet_type,
            "balance": 0,
            "created_at": self._timestamp(),
        }

        # Store wallet metadata
        self.db.put_item(pk=f"WALLET#{wallet_id}", sk="METADATA", data=wallet)

        # Create user->wallet index entry (for querying user's wallets)
        self.db.put_item(
            pk=f"USER#{user_id}",
            sk=f"WALLET#{wallet_id}",
            data={"wallet_id": wallet_id, "type": wallet_type},
        )

        return wallet

    def get_user_wallets(self, user_id: str) -> list[dict]:
        """Get all wallets for a user."""
        return self.db.query_by_pk(pk=f"USER#{user_id}", sk_prefix="WALLET#")

    def add_transaction(self, wallet_id: str, txn_id: str, amount: int) -> None:
        """Add transaction to wallet."""
        self.db.put_item(
            pk=f"WALLET#{wallet_id}",
            sk=f"TXN#{txn_id}",
            data={"txn_id": txn_id, "amount": amount, "timestamp": self._timestamp()},
        )

    def get_wallet_transactions(self, wallet_id: str) -> list[dict]:
        """Get all transactions for a wallet."""
        return self.db.query_by_pk(pk=f"WALLET#{wallet_id}", sk_prefix="TXN#")

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat()
```

### Conditional Updates (Optimistic Locking)

```python
from botocore.exceptions import ClientError


@tracer.capture_method
def update_wallet_balance(wallet_id: str, amount: int) -> bool:
    """Update wallet balance with conditional check."""
    try:
        table.update_item(
            Key={"pk": f"WALLET#{wallet_id}", "sk": "METADATA"},
            UpdateExpression=(
                "SET balance = balance + :amount, "
                "updated_at = :timestamp, "
                "version = version + :increment"
            ),
            ConditionExpression=(
                "attribute_exists(pk) AND "  # Wallet exists
                "balance + :amount >= :zero"  # Sufficient balance
            ),
            ExpressionAttributeValues={
                ":amount": amount,
                ":timestamp": get_timestamp(),
                ":increment": 1,
                ":zero": 0,
            },
        )

        logger.info("Balance updated", extra={"wallet_id": wallet_id, "amount": amount})
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(
                "Balance update failed: insufficient funds or wallet not found",
                extra={"wallet_id": wallet_id},
            )
            return False
        raise
```

## Environment Variable Management

### Standard Pattern

```python
# src/config.py

import os
from typing import Optional


class Config:
    """Application configuration from environment variables."""

    # Required variables
    TABLE_NAME: str = os.environ["TABLE_NAME"]
    REGION: str = os.environ.get("AWS_REGION", "us-east-1")

    # Optional variables with defaults
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    STAGE: str = os.environ.get("STAGE", "dev")
    TIMEOUT: int = int(os.environ.get("TIMEOUT", "30"))

    # Feature flags
    ENABLE_CACHING: bool = os.environ.get("ENABLE_CACHING", "false").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        required = ["TABLE_NAME"]
        missing = [var for var in required if not os.environ.get(var)]

        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")


# Validate on import
Config.validate()
```

### Secrets Management

```python
from aws_lambda_powertools.utilities import parameters


# Get SSM parameter
def get_api_key() -> str:
    """Get API key from SSM Parameter Store."""
    return parameters.get_parameter("/app/my-service/api-key", decrypt=True)


# Get secret from Secrets Manager
def get_db_credentials() -> dict:
    """Get database credentials from Secrets Manager."""
    import json

    secret = parameters.get_secret("app/my-service/db-credentials")
    return json.loads(secret)


# With caching
@parameters.clear_cache  # Clear cache after function execution
def handler(event, context):
    # Cached for 5 minutes by default
    api_key = parameters.get_parameter("/app/my-service/api-key")

    # Use api_key
    ...
```

## Error Handling Patterns

### Infiquetra Error Response Format

```python
from enum import Enum


class ErrorCode(str, Enum):
    """Standard Infiquetra error codes."""

    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def error_response(
    status_code: int, error_code: ErrorCode, message: str, details: dict | None = None
) -> dict:
    """Create standardized error response."""
    body = {
        "error": {
            "code": error_code.value,
            "message": message,
        }
    }

    if details:
        body["error"]["details"] = details

    return {"statusCode": status_code, "body": body}


# Usage in handler
def handler(event, context):
    try:
        user_id = event.get("userId")
        if not user_id:
            return error_response(
                400, ErrorCode.INVALID_INPUT, "userId is required", details={"field": "userId"}
            )

        wallet = get_wallet(user_id)
        if not wallet:
            return error_response(404, ErrorCode.NOT_FOUND, "Wallet not found")

        return {"statusCode": 200, "body": wallet}

    except Exception as e:
        logger.exception("Unexpected error")
        return error_response(500, ErrorCode.INTERNAL_ERROR, "Internal server error")
```

### Custom Exceptions

```python
# src/exceptions.py


class AppException(Exception):
    """Base exception for Infiquetra services."""

    def __init__(self, message: str, error_code: str, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class ItemNotFoundException(AppException):
    """Wallet not found exception."""

    def __init__(self, wallet_id: str):
        super().__init__(
            message=f"Wallet {wallet_id} not found",
            error_code="WALLET_NOT_FOUND",
            status_code=404,
        )


class BusinessRuleException(AppException):
    """Insufficient funds exception."""

    def __init__(self, required: int, available: int):
        super().__init__(
            message=f"Insufficient funds: required {required}, available {available}",
            error_code="INSUFFICIENT_FUNDS",
            status_code=400,
        )


# Usage
def withdraw(wallet_id: str, amount: int) -> dict:
    wallet = get_wallet(wallet_id)

    if not wallet:
        raise ItemNotFoundException(wallet_id)

    if wallet["balance"] < amount:
        raise BusinessRuleException(required=amount, available=wallet["balance"])

    # Process withdrawal
    ...
```

## API Event Handler Pattern

```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools import Logger, Tracer

app = APIGatewayRestResolver()
logger = Logger()
tracer = Tracer()


@app.get("/wallets/<wallet_id>")
@tracer.capture_method
def get_wallet(wallet_id: str):
    """Get wallet by ID."""
    logger.info("Fetching wallet", extra={"wallet_id": wallet_id})

    wallet = wallet_repo.get_wallet(wallet_id)

    if not wallet:
        return {"message": "Wallet not found"}, 404

    return wallet


@app.post("/wallets")
@tracer.capture_method
def create_wallet():
    """Create new wallet."""
    data = app.current_event.json_body

    # Validate
    if not data.get("userId"):
        return {"error": "userId is required"}, 400

    # Create wallet
    wallet = wallet_repo.create_wallet(
        wallet_id=generate_id(),
        user_id=data["userId"],
        wallet_type=data.get("type", "custodial"),
    )

    return wallet, 201


@app.put("/wallets/<wallet_id>/balance")
@tracer.capture_method
def update_balance(wallet_id: str):
    """Update wallet balance."""
    data = app.current_event.json_body

    amount = data.get("amount")
    if amount is None:
        return {"error": "amount is required"}, 400

    success = wallet_repo.update_balance(wallet_id, amount)

    if not success:
        return {"error": "Insufficient funds or wallet not found"}, 400

    return {"message": "Balance updated"}, 200


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    """Lambda handler."""
    return app.resolve(event, context)
```

## Infiquetra Best Practices

1. **Enable all Powertools decorators**: Logger, Tracer, Metrics
3. **Use structured logging**: Add context with `extra` parameter
4. **Implement single table design**: Use composite keys `pk` and `sk`
5. **Add metrics for business events**: Track operations, errors, timing
6. **Trace all external calls**: Use `@tracer.capture_method`
7. **Handle errors gracefully**: Standard error responses with codes
8. **Validate environment variables**: Check on startup
9. **Use conditional updates**: Prevent race conditions
10. **Repository pattern for data access**: Separate business logic from DB operations

## Complete Example

```python
# src/handler.py - Complete Infiquetra Lambda

import os
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from src.db.service import DynamoDBService
from src.repositories.wallet import WalletRepository

# Initialize
logger = Logger(service="my-service")
tracer = Tracer(service="my-service")
metrics = Metrics(namespace="MyServiceMetrics")
app = APIGatewayRestResolver()

# Services
wallet_repo = WalletRepository()


@app.get("/wallets/<wallet_id>")
@tracer.capture_method
def get_wallet(wallet_id: str):
    """Get wallet by ID."""
    metrics.add_metric(name="GetWalletRequest", unit="Count", value=1)

    wallet = wallet_repo.get_wallet(wallet_id)

    if not wallet:
        metrics.add_metric(name="WalletNotFound", unit="Count", value=1)
        return {"error": "Wallet not found"}, 404

    return wallet


@app.post("/wallets")
@tracer.capture_method
def create_wallet():
    """Create wallet."""
    data = app.current_event.json_body
    metrics.add_metric(name="CreateWalletRequest", unit="Count", value=1)

    wallet = wallet_repo.create_wallet(
        wallet_id=f"wallet-{generate_id()}",
        user_id=data["userId"],
        wallet_type=data.get("type", "custodial"),
    )

    metrics.add_metric(name="WalletCreated", unit="Count", value=1)
    return wallet, 201


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler."""
    return app.resolve(event, context)
```

## Related Skills

- [python-project-setup](../python-project-setup/SKILL.md) - Project setup
- [python-testing-patterns](../python-testing-patterns/SKILL.md) - Testing patterns

## Related References

- [lambda-patterns.md](../../references/lambda-patterns.md) - Detailed Powertools patterns
- [pyproject-template.md](../../references/pyproject-template.md) - Dependencies
- [testing-patterns.md](../../references/testing-patterns.md) - Testing Cox patterns
