# Scraperator

A flexible web scraping toolkit with intelligent caching capabilities, supporting different fetching methods (Requests and Playwright) with automatic fallbacks, persistent caching, and Markdown conversion.

## Features

- **Multiple Scraping Methods**: Choose between standard HTTP requests or browser automation via Playwright
- **Smart Caching**: Persistent cache for scraped content with TTL support
- **Automatic Retries**: Built-in retry mechanism with exponential backoff
- **Concurrent Scraping**: Asynchronous scraping with a simple API
- **Content Processing**: Convert HTML to clean Markdown for easier content extraction
- **Flexible Configuration**: Extensive customization options for each scraping method

## Installation

```bash
pip install scraperator
```

Scraperator will automatically install the required browser binaries when they're first needed. No additional installation steps are required.

> **Note**: When the browser is first used, there may be a brief delay as the appropriate binaries are downloaded and installed. If you encounter permission issues during automatic installation, you may need to manually install the browsers by running `playwright install chromium` (or the browser of your choice) with administrator/sudo privileges.

## Quick Start

```python
from scraperator import Scraper

# Basic usage with Requests (default)
scraper = Scraper(url="https://example.com")
html = scraper.scrape()
print(scraper.markdown)  # Get content as Markdown

# Using Playwright for JavaScript-heavy sites
pw_scraper = Scraper(
    url="https://example.com/spa",
    method="playwright",
    headless=True
)
pw_scraper.scrape()
print(pw_scraper.get_status_code())  # Check status code
```

## API Reference

### Scraper Class

The main entry point for all scraping operations.

#### Constructor

```python
Scraper(
    url: str,
    method: str = "requests",
    cache_ttl: int = 1,
    cache_directory: Optional[str] = None,
    cache_id: Optional[str] = None,
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
    headless: bool = True,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    markdown_options: Optional[Dict[str, Any]] = None,
    **kwargs: Any
)
```

**Parameters:**
- `url`: The URL to scrape. This is the only required parameter.
- `method`: Scraping method to use. Options are:
  - `"requests"`: Uses the requests library for simple HTTP requests (default)
  - `"playwright"`: Uses browser automation for JavaScript-heavy sites
- `cache_ttl`: Time-to-live for cache in days (default: 1). Set how long scraped content remains valid in cache before refreshing.
- `cache_directory`: Custom directory for cache files. If not specified, defaults to "cache/scraper/{method}".
- `cache_id`: Custom identifier for cache entry. If not specified, an ID is generated from the URL.
- `browser_type`: Browser engine to use with Playwright. Options are "chromium" (default), "firefox", or "webkit".
- `headless`: Whether to run browser in headless mode (default: True). Set to False to see the browser while scraping.
- `max_retries`: Maximum number of retry attempts for failed requests (default: 3).
- `backoff_factor`: Factor for exponential backoff between retries (default: 2.0). Wait time is calculated as backoff_factor^attempt.
- `markdown_options`: Dictionary of options for Markdown conversion. See Markdown Options section.
- `**kwargs`: Additional options passed to the underlying scraper implementation.

#### Core Scraping Methods

##### `scrape(async_mode: bool = False, force_refresh: bool = False) -> Optional[str]`

Primary method to scrape the URL and return the HTML content.

**Parameters:**
- `async_mode`: If True, scraping happens in the background and the method returns immediately (default: False).
- `force_refresh`: If True, ignores cache and forces a new fetch from the website (default: False).

**Returns:**
- HTML content as string if `async_mode` is False
- None if `async_mode` is True (scraping happens in background)

**Example:**
```python
# Synchronous scraping
html = scraper.scrape()

# Asynchronous scraping
scraper.scrape(async_mode=True)
# ... do other work ...
if scraper.is_complete():
    html = scraper.get_html()
```

##### `get_html(force_refresh: bool = False) -> str`

Get the HTML content from the scraped URL. Will trigger scraping if not already done.

**Parameters:**
- `force_refresh`: If True, ignores cache and forces a new fetch (default: False).

**Returns:**
- HTML content as string.

**Example:**
```python
html = scraper.get_html()
# or force a refresh
fresh_html = scraper.get_html(force_refresh=True)
```

##### `get_status_code() -> Optional[int]`

Get the HTTP status code from the last scrape operation.

**Returns:**
- HTTP status code as integer (e.g., 200, 404, 500), or None if no scrape has been performed.

**Example:**
```python
status = scraper.get_status_code()
if status == 200:
    print("Scraping successful")
elif status >= 400:
    print(f"Error during scraping: HTTP {status}")
```

#### Content Processing Methods

##### `get_markdown() -> str`

Get the scraped content converted to Markdown format. Applies the markdown_options specified during initialization.

**Returns:**
- Markdown content as string.

**Example:**
```python
markdown_content = scraper.get_markdown()
with open("scraped_content.md", "w") as f:
    f.write(markdown_content)
```

#### Asynchronous Operation Methods

##### `is_complete() -> bool`

Check if an asynchronous scraping operation is complete.

**Returns:**
- True if scraping is complete or hasn't started, False otherwise.

**Example:**
```python
scraper.scrape(async_mode=True)
while not scraper.is_complete():
    print("Still scraping...")
    time.sleep(1)
print("Scraping complete!")
```

##### `wait(timeout: Optional[float] = None) -> bool`

Wait for an asynchronous scraping operation to complete.

**Parameters:**
- `timeout`: Maximum time to wait in seconds, or None to wait indefinitely.

**Returns:**
- True if scraping completed successfully, False if timeout was reached.

**Example:**
```python
scraper.scrape(async_mode=True)
if scraper.wait(timeout=10):
    print("Scraping completed within timeout")
else:
    print("Scraping timed out")
```

##### `get_result(timeout: Optional[float] = None) -> Tuple[str, int]`

Get the result of an asynchronous scraping operation. Blocks until complete or timeout reached.

**Parameters:**
- `timeout`: Maximum time to wait in seconds, or None to wait indefinitely.

**Returns:**
- Tuple of (HTML content, HTTP status code).

**Example:**
```python
scraper.scrape(async_mode=True)
try:
    html, status_code = scraper.get_result(timeout=30)
    print(f"Got result with status {status_code}")
except ValueError:
    print("Scraping hasn't been started")
```

##### `cancel() -> bool`

Cancel an ongoing asynchronous scraping operation.

**Returns:**
- True if operation was canceled successfully, False if no operation was in progress.

**Example:**
```python
scraper.scrape(async_mode=True)
time.sleep(2)
if scraper.cancel():
    print("Scraping canceled")
```

#### Resource Management Methods

##### `shutdown(wait: bool = True) -> None`

Clean up resources used by the scraper. Important to call this method when done to prevent resource leaks.

**Parameters:**
- `wait`: If True, wait for any pending operations to complete before shutting down (default: True).

**Example:**
```python
scraper.scrape()
# Process the results
# ...
scraper.shutdown()
```

#### Properties

##### `soup`

BeautifulSoup object for the scraped HTML. Allows direct access to BeautifulSoup methods for content parsing.

**Returns:**
- BeautifulSoup object initialized with the scraped HTML.

**Example:**
```python
scraper.scrape()
title = scraper.soup.title.string
all_links = [a['href'] for a in scraper.soup.find_all('a', href=True)]
```

##### `markdown`

Scraped content converted to Markdown. This is a convenience property that returns the same as get_markdown().

**Returns:**
- Markdown content as string.

**Example:**
```python
scraper.scrape()
print(scraper.markdown)
```

## Configuration Options

### Scraping Methods

#### Requests (Default)

Good for simple websites without heavy JavaScript.

```python
scraper = Scraper(
    url="https://example.com",
    method="requests",
    headers={"User-Agent": "Custom User Agent"},
    timeout=60
)
```

Additional options:
- `headers`: Custom HTTP headers
- `timeout`: Request timeout in seconds

#### Playwright

Recommended for JavaScript-heavy websites, SPAs, and sites with dynamic content.

```python
scraper = Scraper(
    url="https://example.com",
    method="playwright",
    browser_type="chromium",  # or "firefox", "webkit"
    headless=True,
    wait_for_selectors=[".content", "#main-article"],
    networkidle_timeout=15000,
    load_timeout=45000
)
```

Additional options:
- `browser_type`: Browser engine to use ("chromium", "firefox", or "webkit")
- `headless`: Whether to run browser in headless mode
- `wait_for_selectors`: CSS selectors to wait for before considering the page loaded
- `networkidle_timeout`: Time to wait for network to be idle (ms)
- `load_timeout`: Time to wait for page to load (ms)
- `browser_args`: Additional arguments for browser launch
- `context_args`: Additional arguments for browser context

### Caching Options

```python
scraper = Scraper(
    url="https://example.com",
    cache_ttl=7,  # Cache for 7 days
    cache_directory="custom/cache/dir",
    cache_id="custom_identifier"
)
```

### Markdown Conversion Options

```python
scraper = Scraper(
    url="https://example.com",
    markdown_options={
        "strip_tags": ["script", "style", "nav", "footer"],
        "content_selectors": ["article", ".post-content"],
        "preserve_images": True,
        "include_title": True,
        "compact_output": False
    }
)
```

## Advanced Usage

### Asynchronous Scraping

```python
from scraperator import Scraper
import time

scraper = Scraper(url="https://example.com")

# Start scraping in background
scraper.scrape(async_mode=True)

# Do other work
print("Doing other work while scraping...")
time.sleep(1)

# Check if scraping is finished
if scraper.is_complete():
    html = scraper.get_html()
    print("Scraping finished!")
else:
    # Wait for scraping to complete with timeout
    success = scraper.wait(timeout=10)
    if success:
        html = scraper.get_html()
    else:
        print("Scraping timed out")
```

### Using as Context Manager

```python
from scraperator import Scraper

with Scraper(url="https://example.com") as scraper:
    html = scraper.scrape()
    markdown = scraper.markdown
    # Resources automatically cleaned up after block
```

### Combining with BeautifulSoup

```python
from scraperator import Scraper

scraper = Scraper(url="https://example.com")
scraper.scrape()

# Access the BeautifulSoup object
soup = scraper.soup

# Use BeautifulSoup methods
title = soup.title.string
links = [a['href'] for a in soup.find_all('a', href=True)]
```

## Best Practices

1. **Choose the right scraping method**:
   - Use `requests` for simple static websites
   - Use `playwright` for JavaScript-heavy sites or SPAs

2. **Set appropriate cache TTL**:
   - Shorter TTL for frequently changing content
   - Longer TTL for static or archival content

3. **Handle resources properly**:
   - Use the context manager pattern with `with` statement
   - Or explicitly call `shutdown()` when done

4. **Respect website terms of service**:
   - Add delays between requests
   - Consider implementing rate limiting
   - Add proper user agent information

5. **Optimize Playwright usage**:
   - Specify `wait_for_selectors` for faster completion
   - Use headless mode unless debugging is needed

## Common Issues and Solutions

### Connection Errors

If you're experiencing connection errors:
- Increase the `max_retries` parameter
- Adjust the `backoff_factor` for longer waits between retries
- Check network connectivity and website availability

### Incomplete Content

If scraped content seems incomplete:
- Switch from `requests` to `playwright` method
- Specify `wait_for_selectors` for dynamic content
- Increase `networkidle_timeout` and `load_timeout` values

### High Memory Usage

If memory usage is a concern:
- Call `shutdown()` after scraping to release resources
- Use context manager pattern (`with` statement)
- Process and discard data in batches

## License

MIT License