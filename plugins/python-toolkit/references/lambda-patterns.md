# Lambda Powertools Patterns

AWS Lambda Powertools patterns for Infiquetra Python Lambda functions with structured logging, tracing, metrics, and best practices.

## Installation

```bash
# Install Lambda Powertools
pip install aws-lambda-powertools

# Or in pyproject.toml
dependencies = [
    "aws-lambda-powertools>=2.30.0",
]
```

## Basic Lambda Handler Pattern

### Simple Handler with All Features

```python
# src/handler.py

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="VECUWalletService")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler with Powertools decorators."""
    logger.info("Processing request", extra={"request_id": context.aws_request_id})

    # Add custom metric
    metrics.add_metric(name="RequestReceived", unit=MetricUnit.Count, value=1)

    try:
        # Business logic
        result = process_event(event)

        metrics.add_metric(name="SuccessfulRequest", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "body": {"status": "success", "data": result},
        }

    except Exception as e:
        logger.exception("Request failed")
        metrics.add_metric(name="FailedRequest", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": {"status": "error", "message": str(e)},
        }


@tracer.capture_method
def process_event(event: dict) -> dict:
    """Process event with automatic tracing."""
    logger.info("Processing event", extra={"event_type": event.get("type")})
    # Business logic here
    return {"processed": True}
```

## Structured Logging

### Basic Logging

```python
from aws_lambda_powertools import Logger

logger = Logger(service="wallet-service")


def handler(event, context):
    # Info level logging
    logger.info("Processing wallet creation")

    # With structured data
    logger.info(
        "User wallet created",
        extra={
            "user_id": "123",
            "wallet_id": "abc-456",
            "wallet_type": "custodial",
        },
    )

    # Warning
    logger.warning("Rate limit approaching", extra={"current_count": 95})

    # Error with exception
    try:
        risky_operation()
    except Exception:
        logger.exception("Operation failed")  # Automatically logs exception details
```

### Log Levels

```python
# Set log level via environment variable
# LOG_LEVEL=DEBUG, INFO, WARNING, ERROR

logger = Logger(service="wallet-service", level="INFO")

logger.debug("Detailed debugging info")  # Not shown in INFO level
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
```

### Correlation IDs

```python
from aws_lambda_powertools import Logger

logger = Logger()


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
def handler(event, context):
    """Lambda context automatically adds correlation_id to all logs."""
    logger.info("Processing request")
    # Log output includes: "correlation_id": "abc-123-def-456"

    return {"statusCode": 200}
```

### Appending Keys to All Logs

```python
logger = Logger()


def handler(event, context):
    # Append keys that will be in all subsequent logs
    logger.append_keys(user_id="123", tenant_id="tenant-456")

    logger.info("Operation 1")  # Includes user_id and tenant_id
    logger.info("Operation 2")  # Also includes user_id and tenant_id

    # Remove keys when done
    logger.remove_keys(["user_id", "tenant_id"])
```

## Distributed Tracing

### Basic Tracing

```python
from aws_lambda_powertools import Tracer

tracer = Tracer(service="wallet-service")


@tracer.capture_lambda_handler
def handler(event, context):
    """Handler with automatic tracing."""
    user_id = event["userId"]

    # Trace external calls
    result = get_user_wallet(user_id)

    return {"statusCode": 200, "body": result}


@tracer.capture_method
def get_user_wallet(user_id: str) -> dict:
    """Method with automatic tracing and timing."""
    # This entire method is traced automatically
    wallet = fetch_from_dynamodb(user_id)
    return wallet
```

### Adding Annotations and Metadata

```python
@tracer.capture_method
def process_payment(payment_id: str) -> dict:
    # Add searchable annotation (indexed in X-Ray)
    tracer.put_annotation(key="payment_id", value=payment_id)
    tracer.put_annotation(key="payment_status", value="processing")

    # Add metadata (not indexed, but visible in trace)
    tracer.put_metadata(key="payment_details", value={"amount": 100, "currency": "USD"})

    # Process payment
    result = charge_card()

    tracer.put_annotation(key="payment_status", value="completed")
    return result
```

### Custom Subsegments

```python
from aws_lambda_powertools import Tracer

tracer = Tracer()


def handler(event, context):
    with tracer.provider.in_subsegment(name="DynamoDB Query") as subsegment:
        # Operations here are grouped under "DynamoDB Query" subsegment
        items = dynamodb_table.query(KeyConditionExpression="pk = :pk")
        subsegment.put_annotation(key="item_count", value=len(items))

    return {"statusCode": 200}
```

## Metrics

### Adding Metrics

```python
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

metrics = Metrics(namespace="VECUWalletService", service="wallet-api")


@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    # Add default dimensions to all metrics
    metrics.add_dimension(name="environment", value="prod")

    # Count metric
    metrics.add_metric(name="WalletCreated", unit=MetricUnit.Count, value=1)

    # Timing metric
    metrics.add_metric(name="ProcessingTime", unit=MetricUnit.Milliseconds, value=245)

    # Size metric
    metrics.add_metric(name="PayloadSize", unit=MetricUnit.Bytes, value=1024)

    return {"statusCode": 200}
```

### Multiple Metrics

```python
@metrics.log_metrics
def handler(event, context):
    # Multiple metrics for a single event
    metrics.add_metric(name="RequestReceived", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name="ActiveUsers", unit=MetricUnit.Count, value=42)
    metrics.add_metric(name="CacheHitRate", unit=MetricUnit.Percent, value=85.5)

    # Metrics with dimensions
    metrics.add_dimension(name="WalletType", value="custodial")
    metrics.add_metric(name="WalletCreated", unit=MetricUnit.Count, value=1)

    # Clear dimensions for next metric
    metrics.clear_dimensions()

    return {"statusCode": 200}
```

### Metric Units

```python
from aws_lambda_powertools.metrics import MetricUnit

# Available units:
MetricUnit.Seconds
MetricUnit.Microseconds
MetricUnit.Milliseconds
MetricUnit.Bytes
MetricUnit.Kilobytes
MetricUnit.Megabytes
MetricUnit.Gigabytes
MetricUnit.Terabytes
MetricUnit.Bits
MetricUnit.Kilobits
MetricUnit.Megabits
MetricUnit.Gigabits
MetricUnit.Terabits
MetricUnit.Percent
MetricUnit.Count
MetricUnit.BytesPerSecond
MetricUnit.KilobytesPerSecond
MetricUnit.MegabytesPerSecond
MetricUnit.GigabytesPerSecond
MetricUnit.TerabytesPerSecond
MetricUnit.BitsPerSecond
MetricUnit.KilobitsPerSecond
MetricUnit.MegabitsPerSecond
MetricUnit.GigabitsPerSecond
MetricUnit.TerabitsPerSecond
MetricUnit.CountPerSecond
```

## Event Handler (API Gateway)

### REST API Handler

```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools import Logger, Tracer

app = APIGatewayRestResolver()
logger = Logger()
tracer = Tracer()


@app.get("/users/<user_id>")
@tracer.capture_method
def get_user(user_id: str):
    """Get user by ID."""
    logger.info("Fetching user", extra={"user_id": user_id})

    user = fetch_user(user_id)

    if not user:
        return {"statusCode": 404, "message": "User not found"}

    return user  # Automatically serialized to JSON


@app.post("/users")
def create_user():
    """Create new user."""
    data = app.current_event.json_body  # Parse JSON body

    user_id = create_user_record(data)

    return {"userId": user_id, "status": "created"}, 201  # Return with status code


@app.delete("/users/<user_id>")
def delete_user(user_id: str):
    """Delete user."""
    delete_user_record(user_id)
    return {}, 204  # No content


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    return app.resolve(event, context)
```

### Request Validation

```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

app = APIGatewayRestResolver()


@app.post("/wallets")
def create_wallet():
    data = app.current_event.json_body

    # Validate required fields
    if not data.get("userId"):
        raise BadRequestError("userId is required")

    if data.get("walletType") not in ["custodial", "non-custodial"]:
        raise BadRequestError("Invalid walletType")

    wallet = create_wallet_record(data)
    return wallet, 201
```

### Path and Query Parameters

```python
@app.get("/users/<user_id>/wallets")
def get_user_wallets(user_id: str):
    # Path parameter: user_id

    # Query parameters
    wallet_type = app.current_event.get_query_string_value(
        name="type", default_value="all"
    )
    limit = app.current_event.get_query_string_value(name="limit", default_value="10")

    wallets = fetch_wallets(user_id, wallet_type, int(limit))
    return wallets
```

## DynamoDB Access Patterns

### Basic DynamoDB Operations

```python
import boto3
from aws_lambda_powertools import Logger, Tracer
from typing import Optional

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("wallet-table")


@tracer.capture_method
def get_wallet(wallet_id: str) -> Optional[dict]:
    """Get wallet by ID."""
    logger.info("Fetching wallet", extra={"wallet_id": wallet_id})

    try:
        response = table.get_item(Key={"pk": f"WALLET#{wallet_id}", "sk": "METADATA"})

        return response.get("Item")
    except Exception as e:
        logger.exception("Failed to fetch wallet")
        raise


@tracer.capture_method
def create_wallet(user_id: str, wallet_data: dict) -> str:
    """Create new wallet."""
    wallet_id = generate_wallet_id()

    item = {
        "pk": f"WALLET#{wallet_id}",
        "sk": "METADATA",
        "user_id": user_id,
        "created_at": get_timestamp(),
        **wallet_data,
    }

    table.put_item(Item=item)

    logger.info("Wallet created", extra={"wallet_id": wallet_id, "user_id": user_id})

    return wallet_id


@tracer.capture_method
def query_user_wallets(user_id: str) -> list[dict]:
    """Query all wallets for a user using GSI."""
    response = table.query(
        IndexName="UserIdIndex",
        KeyConditionExpression="user_id = :user_id",
        ExpressionAttributeValues={":user_id": user_id},
    )

    return response.get("Items", [])
```

### Conditional Updates

```python
from botocore.exceptions import ClientError


@tracer.capture_method
def update_wallet_balance(wallet_id: str, amount: int) -> bool:
    """Update wallet balance with conditional check."""
    try:
        table.update_item(
            Key={"pk": f"WALLET#{wallet_id}", "sk": "METADATA"},
            UpdateExpression="SET balance = balance + :amount, updated_at = :timestamp",
            ConditionExpression="attribute_exists(pk) AND balance >= :zero",
            ExpressionAttributeValues={
                ":amount": amount,
                ":timestamp": get_timestamp(),
                ":zero": 0,
            },
        )
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning("Wallet update failed: condition not met")
            return False
        raise
```

### Batch Operations

```python
@tracer.capture_method
def batch_get_wallets(wallet_ids: list[str]) -> list[dict]:
    """Batch get multiple wallets."""
    keys = [{"pk": f"WALLET#{wid}", "sk": "METADATA"} for wid in wallet_ids]

    response = dynamodb.batch_get_item(RequestItems={"wallet-table": {"Keys": keys}})

    return response["Responses"]["wallet-table"]


@tracer.capture_method
def batch_write_transactions(transactions: list[dict]) -> None:
    """Batch write multiple transactions."""
    with table.batch_writer() as batch:
        for txn in transactions:
            item = {
                "pk": f"TXN#{txn['id']}",
                "sk": "METADATA",
                **txn,
            }
            batch.put_item(Item=item)
```

## Environment Variable Management

### Using Parameters Utility

```python
from aws_lambda_powertools.utilities import parameters

# Get SSM parameter
api_key = parameters.get_parameter("/vecu/wallet/api-key")

# Get secret from Secrets Manager
db_credentials = parameters.get_secret("vecu/wallet/db-creds")

# Get multiple parameters with caching
@parameters.clear_cache  # Clear cache after function execution
def handler(event, context):
    # Cached for 5 minutes by default
    config = parameters.get_parameters("/vecu/wallet/config")

    return {"statusCode": 200}
```

### Environment Variables

```python
import os
from aws_lambda_powertools import Logger

logger = Logger()

# Get environment variables with defaults
TABLE_NAME = os.environ.get("TABLE_NAME", "default-table")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
STAGE = os.environ.get("STAGE", "dev")


def handler(event, context):
    logger.info(
        "Starting handler",
        extra={"table": TABLE_NAME, "stage": STAGE},
    )
```

## Error Handling Patterns

### Graceful Error Handling

```python
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
    InternalServerError,
)

logger = Logger()


def handler(event, context):
    try:
        result = process_request(event)
        return {"statusCode": 200, "body": result}

    except ValueError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return {"statusCode": 400, "body": {"error": str(e)}}

    except KeyError as e:
        logger.error("Missing required field", extra={"field": str(e)})
        return {"statusCode": 400, "body": {"error": f"Missing field: {e}"}}

    except Exception as e:
        logger.exception("Unexpected error")
        return {"statusCode": 500, "body": {"error": "Internal server error"}}
```

## Complete Lambda Example

```python
# src/handler.py

import os
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.metrics import MetricUnit

# Initialize Powertools
logger = Logger(service="wallet-service")
tracer = Tracer(service="wallet-service")
metrics = Metrics(namespace="VECUWalletService", service="wallet-api")
app = APIGatewayRestResolver()

# DynamoDB setup
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


@app.get("/wallets/<wallet_id>")
@tracer.capture_method
def get_wallet(wallet_id: str):
    """Get wallet by ID."""
    logger.info("Fetching wallet", extra={"wallet_id": wallet_id})
    metrics.add_metric(name="GetWalletRequest", unit=MetricUnit.Count, value=1)

    response = table.get_item(Key={"pk": f"WALLET#{wallet_id}", "sk": "METADATA"})

    if "Item" not in response:
        metrics.add_metric(name="WalletNotFound", unit=MetricUnit.Count, value=1)
        return {"message": "Wallet not found"}, 404

    metrics.add_metric(name="WalletFound", unit=MetricUnit.Count, value=1)
    return response["Item"]


@app.post("/wallets")
@tracer.capture_method
def create_wallet():
    """Create new wallet."""
    data = app.current_event.json_body

    logger.info("Creating wallet", extra={"user_id": data.get("userId")})
    metrics.add_metric(name="CreateWalletRequest", unit=MetricUnit.Count, value=1)

    # Validate
    if not data.get("userId"):
        return {"error": "userId is required"}, 400

    # Create wallet
    wallet_id = f"wallet-{data['userId']}-{generate_id()}"
    item = {
        "pk": f"WALLET#{wallet_id}",
        "sk": "METADATA",
        "wallet_id": wallet_id,
        "user_id": data["userId"],
        "balance": 0,
        "created_at": get_timestamp(),
    }

    table.put_item(Item=item)

    logger.info("Wallet created", extra={"wallet_id": wallet_id})
    metrics.add_metric(name="WalletCreated", unit=MetricUnit.Count, value=1)

    return {"walletId": wallet_id}, 201


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler with full Powertools integration."""
    metrics.add_dimension(name="environment", value=os.environ.get("STAGE", "dev"))
    return app.resolve(event, context)


def generate_id() -> str:
    """Generate unique ID."""
    import uuid

    return str(uuid.uuid4())[:8]


def get_timestamp() -> str:
    """Get ISO timestamp."""
    from datetime import datetime

    return datetime.utcnow().isoformat()
```

## Best Practices

1. **Always use decorators in correct order**: `@logger` → `@tracer` → `@metrics`
2. **Add correlation IDs**: Use `correlation_id_path` for request tracking
3. **Use structured logging**: Add context with `extra` parameter
4. **Capture cold starts**: Enable `capture_cold_start_metric=True`
5. **Add dimensions to metrics**: Group related metrics with dimensions
6. **Trace external calls**: Use `@tracer.capture_method` on all functions
7. **Handle exceptions gracefully**: Log and metrics for errors
8. **Use environment variables**: Configure via Lambda environment
9. **Enable X-Ray tracing**: Set `Tracing: Active` in Lambda configuration
10. **Keep handlers thin**: Move business logic to traced methods

## Related References

- [pyproject-template.md](./pyproject-template.md) - Dependencies configuration
- [testing-patterns.md](./testing-patterns.md) - Testing Lambda functions
- [AWS Lambda Powertools Documentation](https://docs.aws.amazon.com/powertools/python/latest/)
