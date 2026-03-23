---
Package: logorator
Version: 2.0.3
Source: https://pypi.org/project/logorator/
Fetched: 2026-03-23 16:22:31
---

# Logorator

A powerful decorator-based logging library for Python with support for both synchronous and asynchronous functions, featuring automatic depth tracking, log levels, and smart argument formatting.

## Features

- **Simple decorator-based logging** for function calls
- **Full async support** for both synchronous and asynchronous functions
- **Automatic depth tracking** with visual indentation for nested calls
- **Log levels** (DEBUG, INFO, WARNING, ERROR) with color coding
- **Smart argument formatting** - shows parameter names and handles objects intelligently
- **Argument filtering** - include or exclude specific parameters
- **Function execution time** measurement
- **ANSI color-coded output** for better readability
- **Optional file output** with automatic color stripping
- **Configurable output formats** (normal and short modes)
- **Custom notes** for inline logging
- **Works with classes** - instance methods, class methods, static methods

## Installation

```bash
pip install logorator
```

## Quick Start

```python
from logorator import Logger

@Logger()
def add(a, b):
    return a + b

result = add(3, 5)
```

**Output:**
```
Running add
  a: 3
  b: 5
Finished add  Time elapsed: 0.15 ms
```

## Basic Usage

### Synchronous Functions

```python
from logorator import Logger

@Logger()
def calculate(x, y, operation="add"):
    if operation == "add":
        return x + y
    return x - y

result = calculate(10, 5, operation="subtract")
```

**Output:**
```
Running calculate
  x: 10
  y: 5
  operation: subtract
Finished calculate  Time elapsed: 0.12 ms
```

### Asynchronous Functions

```python
from logorator import Logger
import asyncio

@Logger()
async def fetch_data(url):
    await asyncio.sleep(1)
    return f"Data from {url}"

asyncio.run(fetch_data("https://example.com"))
```

**Output:**
```
Running async fetch_data
  url: https://example.com
Finished async fetch_data (https://example.com)  Time elapsed: 1,002.34 ms
```

### Nested Function Calls

Depth tracking is **enabled by default**, showing call hierarchy with indentation:

```python
@Logger()
def outer(x):
    return inner(x * 2)

@Logger()
def inner(y):
    return y + 10

outer(5)
```

**Output:**
```
Running outer
  x: 5
  Running inner
    y: 10
  Finished inner  Time elapsed: 0.08 ms
Finished outer  Time elapsed: 0.25 ms
```

## Advanced Features

### Log Levels

Control logging verbosity with log levels and color coding:

```python
from logorator import Logger, LogLevel

@Logger(level=LogLevel.DEBUG)    # Cyan - detailed info
def debug_function():
    pass

@Logger(level=LogLevel.INFO)     # Green - general info (default)
def info_function():
    pass

@Logger(level=LogLevel.WARNING)  # Yellow - warnings
def warning_function():
    pass

@Logger(level=LogLevel.ERROR)    # Red - errors
def error_function():
    pass

# Set global minimum level
Logger.set_level(LogLevel.WARNING)  # Only WARNING and ERROR will show
```

### Argument Filtering

**Exclude sensitive or verbose arguments:**

```python
@Logger(exclude_args=["password", "token"])
def login(username, password, token):
    # password and token won't be logged
    pass

@Logger(exclude_args=["self"])  # Common for class methods
def process(self, data):
    pass
```

**Include only specific arguments:**

```python
@Logger(include_args=["user_id", "action"])
def audit_log(user_id, action, timestamp, metadata, session):
    # Only user_id and action will be logged
    pass
```

### Working with Classes

Logger works seamlessly with all types of class methods:

```python
class DataProcessor:
    def __init__(self, name):
        self.name = name
    
    @Logger(exclude_args=["self"])  # Hide self for cleaner output
    def process(self, data):
        return self._transform(data)
    
    @Logger(exclude_args=["self"])
    def _transform(self, data):
        return [x * 2 for x in data]
    
    @classmethod
    @Logger()
    def create(cls, name):
        return cls(name)
    
    @staticmethod
    @Logger()
    def validate(value):
        return value > 0
```

**Output:**
```
Running process
  data: [1, 2, 3]
  Running _transform
    data: [1, 2, 3]
  Finished _transform  Time elapsed: 0.05 ms
Finished process  Time elapsed: 0.15 ms
```

### Custom Object Formatting

Logger intelligently formats objects:

```python
class User:
    def __init__(self, name):
        self.name = name
    
    # Without __str__: shows "User"
    # With __str__: shows your custom format
    def __str__(self):
        return f"User({self.name})"

@Logger()
def greet(user):
    return f"Hello, {user.name}"

greet(User("Alice"))
```

**Output:**
```
Running greet
  user: User(Alice)
Finished greet  Time elapsed: 0.08 ms
```

### File Output

Redirect logs to a file (ANSI colors are automatically stripped):

```python
Logger.set_output("logs/application.log")

@Logger()
def main():
    # All logs go to file
    pass

# Switch back to console
Logger.set_output(None)
```

### Custom Notes

Insert custom log messages during execution:

```python
@Logger()
def process_data(data):
    Logger.note("Starting validation")
    # validation logic
    Logger.note("Validation complete")
    return data
```

### Short Mode

Compact tab-separated output:

```python
@Logger(mode="short")
def calculate(a, b):
    return a + b
```

### Disable Depth Tracking

```python
@Logger(show_depth=False)
def flat_logging():
    pass
```

### Custom Function Names

```python
@Logger(override_function_name="DatabaseConnect")
async def connect_to_db(url):
    pass
```

### Global Silent Mode

```python
import os

# Disable all logging in production
if os.environ.get("ENVIRONMENT") == "production":
    Logger.set_silent(True)
```

## API Reference

### `Logger` Class

#### Constructor Parameters

```python
Logger(
    silent=None,                    # Override global silent mode
    mode="normal",                  # "normal" or "short"
    override_function_name=None,    # Custom name in logs
    level=LogLevel.INFO,            # Log level (DEBUG, INFO, WARNING, ERROR)
    include_args=None,              # List of args to include
    exclude_args=None,              # List of args to exclude
    show_depth=True                 # Enable depth tracking (default: True)
)
```

#### Class Methods

##### `Logger.set_silent(silent=True)`
Enable or disable all logging globally.

##### `Logger.set_level(level)`
Set the minimum log level to display.

```python
Logger.set_level(LogLevel.WARNING)  # Only WARNING and ERROR
```

##### `Logger.set_output(filename=None)`
Set output file path. Pass `None` to log to console.

```python
Logger.set_output("logs/app.log")
```

##### `Logger.note(note="", mode="normal")`
Log a custom note.

```python
Logger.note("Processing complete")
```

##### `Logger.log(message="", end="")`
Low-level logging method (rarely needed directly).

## Async Support

Logger fully supports `asyncio` including concurrent execution:

```python
@Logger()
async def process_item(item_id):
    await asyncio.sleep(0.1)
    return f"Processed {item_id}"

@Logger()
async def main():
    # Concurrent execution - logs are properly tracked
    results = await asyncio.gather(
        process_item(1),
        process_item(2),
        process_item(3)
    )

asyncio.run(main())
```

## Best Practices

### 1. Use `@Logger()` for Most Cases
The defaults work great for most scenarios:
```python
@Logger()
def my_function(x, y):
    pass
```

### 2. Exclude `self` in Instance Methods
```python
@Logger(exclude_args=["self"])
def process(self, data):
    pass
```

### 3. Use Log Levels Appropriately
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages for important events
- **ERROR**: Error messages for serious problems

### 4. Filter Sensitive Data
```python
@Logger(exclude_args=["password", "api_key", "token", "secret"])
def authenticate(username, password, api_key):
    pass
```

### 5. Set Global Level in Production
```python
# In production, only show warnings and errors
Logger.set_level(LogLevel.WARNING)
```

## Combining with Other Decorators

Place `@Logger()` as the outermost (top) decorator:

```python
@Logger()
@cache
@validate_input
def expensive_calculation(x):
    pass
```

## Requirements

- Python 3.7+
- No external dependencies

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Changelog

### Version 2.0.0
- Added log levels (DEBUG, INFO, WARNING, ERROR)
- Added automatic depth tracking with indentation
- Added smart argument formatting for objects
- Added parameter name display for all arguments
- Added argument filtering (include_args/exclude_args)
- Improved async support with contextvars
- Enhanced class method support

### Version 1.0.0
- Initial release
- Basic decorator logging
- Async function support
- File output
- ANSI color support
