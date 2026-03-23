---
Package: dynamorator
Version: 0.1.7
Source: https://pypi.org/project/dynamorator/
Fetched: 2026-03-23 10:49:54
---

# Dynamorator

Lightweight DynamoDB JSON storage with automatic TTL support. A simple, reliable wrapper for storing and retrieving JSON data in AWS DynamoDB.

## Features

- Simple key-value JSON storage in DynamoDB
- Batch operations for retrieving multiple items efficiently
- Optional gzip compression with configurable threshold
- Automatic TTL (Time To Live) support
- Automatic table creation with proper configuration
- Silent error handling - never crashes your application
- Shared boto3 client for efficiency
- Optional logging with logorator
- Minimal dependencies (boto3, logorator)

## Installation

```bash
pip install dynamorator
```

## Quick Start

```python
from dynamorator import DynamoDBStore

# Initialize (table will be auto-created if it doesn't exist)
store = DynamoDBStore(table_name="my-data-store")

# Or specify an AWS region explicitly
store = DynamoDBStore(table_name="my-data-store", region_name="us-east-1")

# Store data (expires in 7 days)
store.put("user:123", {"name": "Alice", "score": 100}, ttl_days=7)

# Retrieve data
data = store.get("user:123")  # Returns dict or None
print(data)  # {'name': 'Alice', 'score': 100}

# Batch retrieve multiple items
keys = ["user:123", "user:456", "user:789"]
cached = store.batch_get(keys)
print(f"Found {len(cached)} items")

# List all keys
result = store.list_keys(limit=50)
print(result['keys'])  # ['user:123', ...]

# Delete data
store.delete("user:123")
```

## Silent Mode

Disable logging for production environments:

```python
# With logging (default)
store = DynamoDBStore(table_name="my-store")

# Silent mode - no logging
store = DynamoDBStore(table_name="my-store", silent=True)
```

## AWS Credentials Setup

Dynamorator uses boto3, which follows the standard AWS credential chain:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (when running on EC2, ECS, Lambda, etc.)

See [AWS Boto3 Configuration](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) for details.

## Required IAM Permissions

Your AWS credentials need the following DynamoDB permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/your-table-name"
    }
  ]
}
```

If the table already exists, you only need: `PutItem`, `GetItem`, `DeleteItem`, and `Scan`.

## Compression

Enable gzip compression for large items to reduce storage costs and improve performance:

```python
# Enable compression with default 1KB threshold
store = DynamoDBStore(
    table_name="my-store",
    compress=True
)

# Custom compression threshold (only compress if JSON > 2KB)
store = DynamoDBStore(
    table_name="my-store",
    compress=True,
    compress_threshold=2048
)

# Compression is transparent - no API changes needed
store.put("large:1", {"data": "x" * 10000}, ttl_days=7)
data = store.get("large:1")  # Automatically decompressed
```

**Compression behavior:**
- Only compresses items larger than threshold (default: 1024 bytes)
- Uses gzip compression + base64 encoding
- Automatically decompresses on retrieval
- Works with both `get()` and `batch_get()`
- Stores compression flag with each item
- Backward compatible with uncompressed items

## Batch Operations

Retrieve multiple items efficiently with a single API call:

```python
# Check which items exist in cache
keys = [f"product:{asin}" for asin in product_ids]
cached = store.batch_get(keys)

print(f"Found {len(cached)} cached items")
for key, data in cached.items():
    print(f"{key}: {data}")
```

**Batch features:**
- Retrieves up to 10,000 keys per call
- Automatically chunks into batches of 100 (DynamoDB limit)
- Handles UnprocessedKeys with exponential backoff
- Returns only found items (missing keys are omitted)
- Works with compressed and uncompressed items

## API Reference

### `DynamoDBStore(table_name=None, silent=False, compress=False, compress_threshold=1024, region_name=None)`

Initialize the store.

**Parameters:**
- `table_name` (str, optional): DynamoDB table name. If None, the store is disabled.
- `silent` (bool, optional): If True, disables all logging output. Default is False.
- `compress` (bool, optional): Enable gzip compression for items. Default is False.
- `compress_threshold` (int, optional): Only compress items larger than this (bytes). Default is 1024.
- `region_name` (str, optional): AWS region (e.g., `"us-east-1"`). If None, uses the default boto3 resolution chain.

**Behavior:**
- Automatically creates the table if it doesn't exist
- Uses `PAY_PER_REQUEST` billing mode
- Configures TTL on the `ttl` attribute
- Table schema: partition key `cache_id` (String)

### `is_enabled() -> bool`

Check if the store is enabled.

**Returns:** `True` if table_name is set, `False` otherwise.

```python
store = DynamoDBStore(table_name="my-store")
if store.is_enabled():
    print("Store is ready!")
```

### `get(key: str) -> Optional[dict]`

Retrieve JSON data by key.

**Parameters:**
- `key` (str): The key to retrieve

**Returns:** Dictionary if found, `None` if not found or on error.

```python
data = store.get("user:123")
if data:
    print(f"Found: {data}")
else:
    print("Not found")
```

### `batch_get(keys: list[str]) -> dict[str, dict]`

Retrieve multiple items efficiently.

**Parameters:**
- `keys` (list[str]): List of keys to retrieve (max 10,000)

**Returns:** Dictionary mapping found keys to their data. Missing keys are omitted.

**Behavior:**
- Automatically chunks requests into batches of 100
- Retries UnprocessedKeys with exponential backoff (5 attempts)
- Silently truncates to 10,000 keys if more provided
- Works with compressed and uncompressed items

```python
# Batch retrieve
keys = ["user:1", "user:2", "user:3"]
results = store.batch_get(keys)

for key, data in results.items():
    print(f"{key}: {data}")

# Check cache hit rate
cached_count = len(results)
total_count = len(keys)
print(f"Cache hit rate: {cached_count}/{total_count}")
```

### `put(key: str, data: dict, ttl_days: float)`

Store JSON data with TTL.

**Parameters:**
- `key` (str): The key to store under
- `data` (dict): JSON-serializable dictionary
- `ttl_days` (float): Expiration time in days (can be fractional, e.g., 0.5 for 12 hours)

**Behavior:**
- Silently fails on error (no exceptions raised)
- Automatically handles datetime objects in data using `DateTimeEncoder`
- Stores creation timestamp for tracking

```python
from datetime import datetime

store.put("session:abc", {
    "user_id": 123,
    "created": datetime.now(),
    "expires": datetime(2026, 12, 31)
}, ttl_days=1)
```

### `delete(key: str)`

Delete an entry by key.

**Parameters:**
- `key` (str): The key to delete

**Behavior:**
- Silently fails on error (no exceptions raised)

```python
store.delete("user:123")
```

### `list_keys(limit=100, last_key=None) -> dict`

List keys in the table with pagination support.

**Parameters:**
- `limit` (int): Maximum number of keys to return (default: 100)
- `last_key` (str, optional): Pagination token from previous call

**Returns:** Dictionary with:
- `keys` (list): List of key strings
- `last_key` (str or None): Token for next page, or None if no more results

```python
# Get first page
result = store.list_keys(limit=50)
print(result['keys'])

# Get next page if available
if result['last_key']:
    next_result = store.list_keys(limit=50, last_key=result['last_key'])
    print(next_result['keys'])
```

## Table Structure

Dynamorator creates tables with the following structure:

```
Partition Key: cache_id (String)

Attributes:
  - data (String)       - JSON serialized dictionary (or compressed+base64)
  - ttl (Number)        - Unix timestamp for expiration
  - created_at (Number) - Unix timestamp of creation
  - compressed (Bool)   - True if data is gzip compressed (optional)

TTL: Enabled on 'ttl' attribute
Billing: PAY_PER_REQUEST
```

## TTL Behavior

DynamoDB's TTL feature:
- Automatically deletes expired items (usually within 48 hours of expiration)
- Doesn't consume write capacity
- Items may still be returned by queries shortly after expiration
- Free of charge

Example TTL values:
```python
store.put(key, data, ttl_days=7)      # 7 days
store.put(key, data, ttl_days=0.5)    # 12 hours
store.put(key, data, ttl_days=30)     # 30 days
store.put(key, data, ttl_days=365)    # 1 year
```

## Error Handling

Dynamorator follows a "silent failure" philosophy:
- `get()` returns `None` on errors
- `put()` and `delete()` fail silently
- Only table creation operations raise exceptions

This design ensures your application continues running even if DynamoDB is temporarily unavailable.

```python
# Safe to use without try/except
data = store.get("key")  # Returns None on error
store.put("key", {"value": 1}, ttl_days=1)  # Silent on error
store.delete("key")  # Silent on error
```

## DateTimeEncoder

Automatically handles datetime serialization:

```python
from datetime import datetime
from dynamorator import DynamoDBStore

store = DynamoDBStore(table_name="events")

# Datetime objects are automatically converted to ISO format
store.put("event:1", {
    "name": "Meeting",
    "scheduled": datetime(2026, 3, 15, 14, 30),
    "created": datetime.now()
}, ttl_days=30)

# Retrieved as ISO strings
data = store.get("event:1")
# {'name': 'Meeting', 'scheduled': '2026-03-15T14:30:00', 'created': '2026-02-21T...'}
```

## Use Cases

- **Session Storage**: Store user sessions with automatic expiration
- **Cache Layer**: Simple caching for API responses or computed data with batch retrieval
- **Product Catalog Cache**: Batch check which products are cached before fetching from API
- **Feature Flags**: Store and retrieve feature flag configurations
- **Temporary Data**: Any data that should automatically expire
- **User Preferences**: Store user settings with optional expiration
- **Large Object Storage**: Use compression for storing large JSON objects efficiently

## Disabled Mode

Pass `None` as table_name to disable the store (useful for testing or optional features):

```python
import os

# Only enable in production
table_name = os.getenv("DYNAMODB_TABLE") if os.getenv("ENV") == "production" else None
store = DynamoDBStore(table_name=table_name)

# Safe to call even when disabled
store.put("key", {"data": 1}, ttl_days=1)  # No-op when disabled
data = store.get("key")  # Returns None when disabled
```

## License

MIT License - see LICENSE file for details.

## Author

Arved Klöhn

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
