# Testing Patterns

Comprehensive testing strategies and patterns for Infiquetra Python projects using pytest, moto, fixtures, and coverage.

## Project Structure

```
project/
├── src/
│   └── service/
│       ├── __init__.py
│       ├── handler.py
│       ├── models.py
│       └── utils.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_handler.py
│   │   ├── test_models.py
│   │   └── test_utils.py
│   └── integration/
│       ├── __init__.py
│       └── test_api.py
├── pyproject.toml
└── pytest.ini (optional, prefer pyproject.toml)
```

## conftest.py Patterns

### Basic AWS Mocking Setup

```python
# tests/conftest.py

import os
import pytest
import boto3
from moto import mock_dynamodb, mock_s3, mock_lambda
from typing import Generator

# Set AWS credentials for moto (fake credentials)
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="function")
def dynamodb_table(aws_credentials):
    """Create a mocked DynamoDB table."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create table
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield table


@pytest.fixture(scope="function")
def s3_bucket(aws_credentials):
    """Create a mocked S3 bucket."""
    with mock_s3():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield s3


@pytest.fixture(scope="function")
def lambda_context():
    """Mock Lambda context."""
    class MockLambdaContext:
        def __init__(self):
            self.function_name = "test-function"
            self.function_version = "$LATEST"
            self.invoked_function_arn = (
                "arn:aws:lambda:us-east-1:123456789012:function:test-function"
            )
            self.memory_limit_in_mb = 128
            self.aws_request_id = "test-request-id"
            self.log_group_name = "/aws/lambda/test-function"
            self.log_stream_name = "2024/08/15/[$LATEST]test"

        def get_remaining_time_in_millis(self) -> int:
            return 300000

    return MockLambdaContext()
```

### Advanced Fixtures with Cleanup

```python
# tests/conftest.py

import pytest
from typing import Generator
from unittest.mock import Mock, patch


@pytest.fixture(scope="function")
def dynamodb_table_with_data(dynamodb_table) -> Generator:
    """DynamoDB table with test data."""
    # Setup: Add test data
    dynamodb_table.put_item(
        Item={"pk": "USER#123", "sk": "PROFILE", "name": "Test User"}
    )
    dynamodb_table.put_item(
        Item={"pk": "USER#456", "sk": "PROFILE", "name": "Another User"}
    )

    yield dynamodb_table

    # Teardown: Clean up is automatic with moto


@pytest.fixture(scope="function")
def mock_environment_variables(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STAGE", "test")


@pytest.fixture
def mock_external_api():
    """Mock external API calls."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"status": "success", "data": {"id": "123"}},
        )
        yield mock_get
```

### Session-Scoped Fixtures

```python
# tests/conftest.py

@pytest.fixture(scope="session")
def test_config():
    """Test configuration (shared across all tests)."""
    return {
        "region": "us-east-1",
        "table_name": "test-table",
        "bucket_name": "test-bucket",
    }


@pytest.fixture(scope="module")
def sample_event():
    """Sample Lambda event (shared within module)."""
    return {
        "httpMethod": "POST",
        "path": "/api/users",
        "body": '{"name": "Test User"}',
        "headers": {"Content-Type": "application/json"},
    }
```

## Unit Test Patterns

### Testing Lambda Handlers

```python
# tests/unit/test_handler.py

import json
import pytest
from src.service.handler import lambda_handler


def test_handler_success(lambda_context, dynamodb_table, mock_environment_variables):
    """Test successful Lambda handler execution."""
    event = {
        "httpMethod": "GET",
        "path": "/users/123",
        "pathParameters": {"userId": "123"},
    }

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"


def test_handler_missing_parameter(lambda_context):
    """Test handler with missing required parameter."""
    event = {
        "httpMethod": "GET",
        "path": "/users",
        # Missing pathParameters
    }

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


@pytest.mark.parametrize(
    "user_id,expected_status",
    [
        ("123", 200),
        ("456", 200),
        ("999", 404),
        ("", 400),
    ],
)
def test_handler_multiple_users(
    lambda_context, dynamodb_table_with_data, user_id, expected_status
):
    """Test handler with multiple user IDs."""
    event = {
        "httpMethod": "GET",
        "path": f"/users/{user_id}",
        "pathParameters": {"userId": user_id},
    }

    response = lambda_handler(event, lambda_context)
    assert response["statusCode"] == expected_status
```

### Testing with Moto (AWS Mocking)

```python
# tests/unit/test_dynamodb_service.py

import pytest
from src.service.db import DynamoDBService


def test_put_item(dynamodb_table):
    """Test putting item in DynamoDB."""
    service = DynamoDBService(table_name="test-table")

    result = service.put_item(
        pk="USER#123",
        sk="PROFILE",
        data={"name": "Test User", "email": "test@example.com"},
    )

    assert result is True

    # Verify item was stored
    response = dynamodb_table.get_item(Key={"pk": "USER#123", "sk": "PROFILE"})
    assert "Item" in response
    assert response["Item"]["name"] == "Test User"


def test_get_item(dynamodb_table_with_data):
    """Test getting item from DynamoDB."""
    service = DynamoDBService(table_name="test-table")

    item = service.get_item(pk="USER#123", sk="PROFILE")

    assert item is not None
    assert item["name"] == "Test User"


def test_query_items(dynamodb_table_with_data):
    """Test querying items by partition key."""
    service = DynamoDBService(table_name="test-table")

    # Add more items for the same user
    dynamodb_table_with_data.put_item(
        Item={"pk": "USER#123", "sk": "ORDER#1", "total": 100}
    )
    dynamodb_table_with_data.put_item(
        Item={"pk": "USER#123", "sk": "ORDER#2", "total": 200}
    )

    items = service.query_by_pk(pk="USER#123")

    assert len(items) == 3  # PROFILE + 2 ORDERs
```

### Testing S3 Operations

```python
# tests/unit/test_s3_service.py

import pytest
from src.service.storage import S3Service


def test_upload_file(s3_bucket):
    """Test uploading file to S3."""
    service = S3Service(bucket_name="test-bucket")

    content = b"test file content"
    result = service.upload_file(key="test.txt", content=content)

    assert result is True

    # Verify file was uploaded
    obj = s3_bucket.get_object(Bucket="test-bucket", Key="test.txt")
    assert obj["Body"].read() == content


def test_download_file(s3_bucket):
    """Test downloading file from S3."""
    # Setup: Upload test file
    s3_bucket.put_object(
        Bucket="test-bucket", Key="test.txt", Body=b"test content"
    )

    service = S3Service(bucket_name="test-bucket")
    content = service.download_file(key="test.txt")

    assert content == b"test content"


def test_delete_file(s3_bucket):
    """Test deleting file from S3."""
    # Setup: Upload test file
    s3_bucket.put_object(Bucket="test-bucket", Key="test.txt", Body=b"test")

    service = S3Service(bucket_name="test-bucket")
    result = service.delete_file(key="test.txt")

    assert result is True

    # Verify file was deleted
    with pytest.raises(Exception):
        s3_bucket.get_object(Bucket="test-bucket", Key="test.txt")
```

## Parametrized Tests

```python
# tests/unit/test_validators.py

import pytest
from src.service.validators import validate_email, validate_phone


@pytest.mark.parametrize(
    "email,expected",
    [
        ("test@example.com", True),
        ("user+tag@domain.co.uk", True),
        ("invalid.email", False),
        ("@example.com", False),
        ("test@", False),
        ("", False),
    ],
)
def test_validate_email(email, expected):
    """Test email validation with multiple inputs."""
    assert validate_email(email) == expected


@pytest.mark.parametrize(
    "phone,expected",
    [
        ("+1-555-123-4567", True),
        ("555-123-4567", True),
        ("5551234567", True),
        ("invalid", False),
        ("", False),
    ],
    ids=["international", "dashed", "numeric", "invalid", "empty"],
)
def test_validate_phone(phone, expected):
    """Test phone validation with labeled test cases."""
    assert validate_phone(phone) == expected
```

## Integration Test Patterns

### Testing API Endpoints

```python
# tests/integration/test_api.py

import pytest
import requests
from moto import mock_dynamodb


@pytest.mark.integration
def test_create_user_endpoint(api_base_url, dynamodb_table):
    """Test full user creation flow."""
    payload = {"name": "John Doe", "email": "john@example.com"}

    response = requests.post(f"{api_base_url}/users", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "userId" in data
    assert data["name"] == "John Doe"


@pytest.mark.integration
def test_get_user_endpoint(api_base_url, dynamodb_table_with_data):
    """Test retrieving user."""
    response = requests.get(f"{api_base_url}/users/123")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test User"
```

## Mocking Patterns

### Mocking Functions

```python
# tests/unit/test_service.py

from unittest.mock import Mock, patch, MagicMock


def test_with_function_mock():
    """Mock a specific function."""
    with patch("src.service.utils.get_current_time") as mock_time:
        mock_time.return_value = "2024-08-15T12:00:00Z"

        from src.service.utils import format_timestamp

        result = format_timestamp()
        assert result == "2024-08-15T12:00:00Z"
        mock_time.assert_called_once()


def test_with_class_mock():
    """Mock an entire class."""
    with patch("src.service.db.DynamoDBService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.get_item.return_value = {"id": "123"}

        from src.service.handler import process_user

        result = process_user("123")
        assert result["id"] == "123"
        mock_instance.get_item.assert_called_with(user_id="123")
```

### Mocking External APIs

```python
# tests/unit/test_external_api.py

import pytest
from unittest.mock import patch, Mock


def test_external_api_success(mock_external_api):
    """Test successful external API call."""
    from src.service.api_client import fetch_user_data

    data = fetch_user_data(user_id="123")

    assert data["status"] == "success"
    assert data["data"]["id"] == "123"
    mock_external_api.assert_called_once()


def test_external_api_failure():
    """Test external API failure handling."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=500, text="Server Error")

        from src.service.api_client import fetch_user_data

        with pytest.raises(Exception, match="API request failed"):
            fetch_user_data(user_id="123")
```

## Coverage Strategies

### Measuring Coverage

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Generate coverage badge
coverage-badge -o coverage.svg
```

### Improving Coverage

```python
# Test edge cases
def test_edge_cases():
    """Test boundary conditions."""
    assert validate_age(0) is False    # Lower bound
    assert validate_age(1) is True     # Just above
    assert validate_age(120) is True   # Upper bound
    assert validate_age(121) is False  # Just above


# Test error paths
def test_error_handling():
    """Test exception handling."""
    with pytest.raises(ValueError, match="Invalid input"):
        process_data(None)

    with pytest.raises(KeyError):
        get_required_field({})
```

## Test Markers

```python
# tests/unit/test_service.py

import pytest


@pytest.mark.unit
def test_unit_function():
    """Fast unit test."""
    pass


@pytest.mark.integration
def test_integration_flow():
    """Slower integration test."""
    pass


@pytest.mark.slow
def test_slow_operation():
    """Very slow test."""
    pass


@pytest.mark.aws
def test_aws_service():
    """Test requiring AWS services."""
    pass
```

Run specific markers:
```bash
# Run only unit tests
pytest -m unit

# Run everything except slow tests
pytest -m "not slow"

# Run unit and integration, but not slow
pytest -m "unit or integration" -m "not slow"
```

## TDD Workflow

1. **Write failing test**:
```python
def test_calculate_total():
    """Test order total calculation."""
    order = Order(items=[Item(price=10), Item(price=20)])
    assert order.calculate_total() == 30  # Test fails (not implemented)
```

2. **Implement minimum code to pass**:
```python
class Order:
    def calculate_total(self):
        return sum(item.price for item in self.items)
```

3. **Refactor while keeping tests green**:
```python
class Order:
    @property
    def total(self):
        """Calculate order total with tax."""
        subtotal = sum(item.price for item in self.items)
        return subtotal * (1 + self.tax_rate)
```

## Best Practices

1. **Test one thing per test**: Each test should verify a single behavior
2. **Use descriptive names**: `test_user_creation_with_invalid_email_fails`
3. **Arrange-Act-Assert**: Setup → Execute → Verify
4. **Fixtures for reusable setup**: Use conftest.py for shared fixtures
5. **Mock external dependencies**: Use moto for AWS, patch for external APIs
6. **Parametrize similar tests**: Use `@pytest.mark.parametrize`
7. **80%+ coverage target**: Focus on critical paths first
8. **Fast unit tests**: Keep unit tests under 100ms each
9. **Isolated tests**: Each test should be independent
10. **Clean up resources**: Use fixtures with proper teardown

## Related References

- [pyproject-template.md](./pyproject-template.md) - pytest configuration
- [pre-commit-config.md](./pre-commit-config.md) - Pre-commit test hooks
- [lambda-patterns.md](./lambda-patterns.md) - Lambda-specific testing
