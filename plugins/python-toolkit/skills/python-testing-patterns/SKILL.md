---
name: python-testing-patterns
description: Python testing best practices with pytest, moto, fixtures, and coverage
when_to_use: |
  Use this skill when the user wants to:
  - Write tests
  - Set up pytest
  - Create test fixtures
  - Mock AWS services
  - Improve test coverage
  - Set up conftest.py
  - Test Lambda functions
  - Run integration tests
  - Use moto for AWS mocking
  - Implement TDD workflow
---

# Python Testing Patterns Guide

You are helping the user write comprehensive tests for their Python project using pytest, moto, and modern testing patterns.

## Testing Philosophy

**Infiquetra Standard**: 80% minimum test coverage focusing on:
- Critical business logic paths
- Error handling and edge cases
- AWS service interactions
- API endpoints and handlers

## Project Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated tests
│   ├── __init__.py
│   ├── test_handler.py
│   ├── test_models.py
│   └── test_utils.py
└── integration/             # Slower tests with dependencies
    ├── __init__.py
    └── test_api_flow.py
```

## conftest.py Setup

Create `tests/conftest.py` with common fixtures:

```python
import os
import pytest
import boto3
from moto import mock_dynamodb, mock_s3, mock_lambda
from typing import Generator

# Mock AWS credentials
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


@pytest.fixture(scope="function")
def dynamodb_table(aws_credentials):
    """Create mocked DynamoDB table."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

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
    """Create mocked S3 bucket."""
    with mock_s3():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield s3


@pytest.fixture(scope="function")
def lambda_context():
    """Mock Lambda context."""
    class MockLambdaContext:
        function_name = "test-function"
        function_version = "$LATEST"
        aws_request_id = "test-request-id"
        memory_limit_in_mb = 128

        def get_remaining_time_in_millis(self) -> int:
            return 300000

    return MockLambdaContext()


@pytest.fixture(scope="function")
def mock_environment_variables(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
```

## Testing Lambda Handlers

### Basic Handler Test

```python
# tests/unit/test_handler.py

import json
from src.service.handler import lambda_handler


def test_handler_success(lambda_context, mock_environment_variables):
    """Test successful handler execution."""
    event = {
        "httpMethod": "GET",
        "path": "/users/123",
        "pathParameters": {"userId": "123"},
    }

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"


def test_handler_error_handling(lambda_context):
    """Test handler error response."""
    event = {
        "httpMethod": "GET",
        "path": "/users",
        # Missing required pathParameters
    }

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
```

### Parametrized Handler Tests

```python
import pytest


@pytest.mark.parametrize(
    "user_id,expected_status,expected_message",
    [
        ("123", 200, None),
        ("456", 200, None),
        ("999", 404, "User not found"),
        ("", 400, "Invalid user ID"),
    ],
    ids=["valid-user-1", "valid-user-2", "not-found", "empty-id"],
)
def test_get_user_various_inputs(
    lambda_context,
    user_id,
    expected_status,
    expected_message,
):
    """Test handler with multiple user IDs."""
    event = {
        "httpMethod": "GET",
        "path": f"/users/{user_id}",
        "pathParameters": {"userId": user_id} if user_id else {},
    }

    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == expected_status

    if expected_message:
        body = json.loads(response["body"])
        assert expected_message in body.get("message", "")
```

## Testing DynamoDB Operations

### Basic DynamoDB Tests

```python
# tests/unit/test_db_service.py

import pytest
from src.service.db import DynamoDBService


def test_put_item(dynamodb_table, mock_environment_variables):
    """Test storing item in DynamoDB."""
    service = DynamoDBService()

    result = service.put_item(
        pk="USER#123",
        sk="PROFILE",
        data={"name": "Test User", "email": "test@example.com"},
    )

    assert result is True

    # Verify item exists
    response = dynamodb_table.get_item(
        Key={"pk": "USER#123", "sk": "PROFILE"}
    )
    assert "Item" in response
    assert response["Item"]["name"] == "Test User"


def test_get_item_not_found(dynamodb_table, mock_environment_variables):
    """Test getting non-existent item."""
    service = DynamoDBService()

    item = service.get_item(pk="USER#999", sk="PROFILE")

    assert item is None


def test_update_item(dynamodb_table, mock_environment_variables):
    """Test updating existing item."""
    # Setup: Create item
    dynamodb_table.put_item(
        Item={"pk": "USER#123", "sk": "PROFILE", "name": "Old Name"}
    )

    service = DynamoDBService()
    result = service.update_item(
        pk="USER#123",
        sk="PROFILE",
        updates={"name": "New Name"},
    )

    assert result is True

    # Verify update
    response = dynamodb_table.get_item(
        Key={"pk": "USER#123", "sk": "PROFILE"}
    )
    assert response["Item"]["name"] == "New Name"
```

### Testing Query Operations

```python
def test_query_by_partition_key(dynamodb_table, mock_environment_variables):
    """Test querying items by partition key."""
    # Setup: Add multiple items for same partition
    items = [
        {"pk": "USER#123", "sk": "PROFILE", "name": "Test User"},
        {"pk": "USER#123", "sk": "ORDER#1", "total": 100},
        {"pk": "USER#123", "sk": "ORDER#2", "total": 200},
    ]
    for item in items:
        dynamodb_table.put_item(Item=item)

    service = DynamoDBService()
    results = service.query_by_pk(pk="USER#123")

    assert len(results) == 3
    assert any(item["sk"] == "PROFILE" for item in results)
    assert any(item["sk"] == "ORDER#1" for item in results)
```

## Testing S3 Operations

```python
# tests/unit/test_s3_service.py

from src.service.storage import S3Service


def test_upload_file(s3_bucket, mock_environment_variables):
    """Test uploading file to S3."""
    service = S3Service()

    content = b"test file content"
    result = service.upload_file(key="test.txt", content=content)

    assert result is True

    # Verify upload
    obj = s3_bucket.get_object(Bucket="test-bucket", Key="test.txt")
    assert obj["Body"].read() == content


def test_download_file(s3_bucket, mock_environment_variables):
    """Test downloading file from S3."""
    # Setup: Upload test file
    s3_bucket.put_object(
        Bucket="test-bucket",
        Key="test.txt",
        Body=b"test content",
    )

    service = S3Service()
    content = service.download_file(key="test.txt")

    assert content == b"test content"


def test_file_exists(s3_bucket, mock_environment_variables):
    """Test checking if file exists."""
    # Setup: Upload file
    s3_bucket.put_object(Bucket="test-bucket", Key="exists.txt", Body=b"test")

    service = S3Service()

    assert service.file_exists("exists.txt") is True
    assert service.file_exists("not-exists.txt") is False
```

## Mocking External APIs

### Using unittest.mock

```python
# tests/unit/test_api_client.py

from unittest.mock import patch, Mock
from src.service.api_client import fetch_user_data


def test_fetch_user_success():
    """Test successful API call."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"id": "123", "name": "Test User"},
        )

        data = fetch_user_data(user_id="123")

        assert data["id"] == "123"
        assert data["name"] == "Test User"
        mock_get.assert_called_once_with(
            "https://api.example.com/users/123",
            headers={"Authorization": "Bearer token"},
        )


def test_fetch_user_api_error():
    """Test API error handling."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=500, text="Server Error")

        with pytest.raises(Exception, match="API request failed"):
            fetch_user_data(user_id="123")
```

### Fixture-Based Mocking

```python
# tests/conftest.py

@pytest.fixture
def mock_external_api():
    """Mock external API calls."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"status": "success", "data": {}},
        )
        yield mock_get


# tests/unit/test_service.py

def test_with_mocked_api(mock_external_api):
    """Test using fixture-based mock."""
    result = call_external_api()

    assert result["status"] == "success"
    mock_external_api.assert_called_once()
```

## Integration Tests

```python
# tests/integration/test_api_flow.py

import pytest


@pytest.mark.integration
def test_create_and_retrieve_user(
    dynamodb_table,
    lambda_context,
    mock_environment_variables,
):
    """Test full user creation and retrieval flow."""
    from src.service.handler import lambda_handler

    # Create user
    create_event = {
        "httpMethod": "POST",
        "path": "/users",
        "body": '{"name": "Test User", "email": "test@example.com"}',
    }

    create_response = lambda_handler(create_event, lambda_context)
    assert create_response["statusCode"] == 201

    # Extract user ID
    import json
    user_id = json.loads(create_response["body"])["userId"]

    # Retrieve user
    get_event = {
        "httpMethod": "GET",
        "path": f"/users/{user_id}",
        "pathParameters": {"userId": user_id},
    }

    get_response = lambda_handler(get_event, lambda_context)
    assert get_response["statusCode"] == 200

    user_data = json.loads(get_response["body"])
    assert user_data["name"] == "Test User"
```

## Coverage Strategies

### Running Coverage

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Check coverage threshold
pytest --cov=src --cov-fail-under=80
```

### Improving Coverage

Focus on:
1. **Untested functions**: Check coverage report for 0% functions
2. **Edge cases**: Test boundary conditions
3. **Error paths**: Test exception handling
4. **Branch coverage**: Test all if/else paths

```python
# Example: Testing all branches
def test_validate_age_all_branches():
    """Test all age validation branches."""
    assert validate_age(0) is False     # Lower bound
    assert validate_age(1) is True      # Just above
    assert validate_age(50) is True     # Middle
    assert validate_age(120) is True    # Upper bound
    assert validate_age(121) is False   # Just above
    assert validate_age(-1) is False    # Negative
```

## Test Markers

Define markers in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast unit tests",
    "integration: Slower integration tests",
    "slow: Very slow tests",
    "aws: Tests requiring AWS services",
]
```

Use markers:

```python
@pytest.mark.unit
def test_fast_function():
    """Fast unit test."""
    pass


@pytest.mark.integration
@pytest.mark.slow
def test_full_workflow():
    """Slow integration test."""
    pass
```

Run specific markers:

```bash
# Run only unit tests
pytest -m unit

# Run everything except slow
pytest -m "not slow"

# Run unit and integration
pytest -m "unit or integration"
```

## TDD Workflow

### 1. Write Failing Test

```python
def test_calculate_order_total():
    """Test order total calculation."""
    order = Order(items=[
        Item(price=10.00),
        Item(price=20.00),
    ])

    assert order.calculate_total() == 30.00  # FAILS: Not implemented
```

### 2. Implement Minimum Code

```python
class Order:
    def __init__(self, items):
        self.items = items

    def calculate_total(self):
        return sum(item.price for item in self.items)
```

### 3. Test Passes

```bash
$ pytest tests/unit/test_order.py
✓ test_calculate_order_total PASSED
```

### 4. Add More Tests and Refactor

```python
def test_calculate_total_with_tax():
    """Test total with tax calculation."""
    order = Order(items=[Item(price=100)], tax_rate=0.10)

    assert order.calculate_total() == 110.00


def test_calculate_total_empty_order():
    """Test empty order."""
    order = Order(items=[])

    assert order.calculate_total() == 0.00
```

## Best Practices

1. **Test one thing per test**: Each test verifies a single behavior
2. **Descriptive names**: `test_user_creation_with_invalid_email_returns_400`
3. **Arrange-Act-Assert pattern**:
   ```python
   def test_example():
       # Arrange: Set up test data
       user = User(name="Test")

       # Act: Execute the operation
       result = user.validate()

       # Assert: Verify the result
       assert result is True
   ```
4. **Use fixtures for setup**: Reuse common test setup in conftest.py
5. **Mock external dependencies**: Don't make real AWS/API calls
6. **Parametrize similar tests**: Use `@pytest.mark.parametrize`
7. **Keep tests fast**: Unit tests should be < 100ms each
8. **Test edge cases**: Boundaries, empty inputs, None values
9. **Test error paths**: Exceptions and error handling
10. **80%+ coverage**: Focus on critical business logic

## Common Testing Patterns

### Testing Exceptions

```python
def test_invalid_input_raises_error():
    """Test that invalid input raises ValueError."""
    with pytest.raises(ValueError, match="Invalid user ID"):
        process_user(user_id=None)


def test_missing_field_raises_keyerror():
    """Test missing required field."""
    with pytest.raises(KeyError):
        parse_event({})  # Missing required fields
```

### Testing with Fixtures

```python
@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    return {
        "id": "123",
        "name": "Test User",
        "email": "test@example.com",
    }


def test_with_fixture(sample_user):
    """Test using fixture data."""
    assert sample_user["id"] == "123"
    assert validate_user(sample_user) is True
```

### Testing Async Functions

```python
import pytest


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await fetch_data_async()

    assert result is not None
    assert "data" in result
```

## Troubleshooting

### Tests fail with "ModuleNotFoundError"

Install project in editable mode:
```bash
pip install -e .
```

### Moto mocks not working

Ensure AWS credentials are set in conftest.py before importing moto.

### Coverage not reaching 80%

View detailed coverage:
```bash
coverage html
open htmlcov/index.html
```

Focus on red/yellow highlighted lines.

### Tests are too slow

- Use `@pytest.mark.slow` for slow tests
- Mock external dependencies
- Use smaller test data sets
- Run fast tests first: `pytest -m "not slow"`

## Infiquetra Testing Standards

- ✅ Minimum 80% test coverage
- ✅ Separate unit and integration tests
- ✅ Use moto for AWS service mocking
- ✅ pytest with coverage reporting
- ✅ Test markers for selective execution
- ✅ conftest.py with shared fixtures
- ✅ Parametrized tests for similar scenarios
- ✅ Mock external APIs
- ✅ Test error handling and edge cases
- ✅ Fast unit tests (< 100ms each)

## Related Skills

- [python-project-setup](../python-project-setup/SKILL.md) - Project configuration
- [cox-python-patterns](../cox-python-patterns/SKILL.md) - Cox/Infiquetra patterns

## Related References

- [testing-patterns.md](../../references/testing-patterns.md) - Complete testing examples
- [pyproject-template.md](../../references/pyproject-template.md) - pytest configuration
- [lambda-patterns.md](../../references/lambda-patterns.md) - Testing Lambda functions
