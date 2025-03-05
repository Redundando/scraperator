# Scraperator

A flexible web scraping toolkit with caching capabilities, supporting different fetching methods (Requests and Playwright) with intelligent fallbacks, caching, and Markdown conversion.

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

## Advanced Usage

### Configuring Cache

```python
scraper = Scraper(
    url="https://example.com",
    cache_ttl=7,  # Cache for 7 days
    cache_directory="custom/cache/dir"
)
```

### Playwright Options

```python
scraper = Scraper(
    url="https://example.com/complex-page",
    method="playwright",
    browser_type="firefox",  # Use Firefox browser
    headless=False,  # Show browser window
    wait_for_selectors=[".content", "#main-article"]  # Wait for these elements
)
```

### Async Scraping

```python
scraper = Scraper(url="https://example.com")
# Start scraping in background
scraper.scrape(async_mode=True)

# Do other work...
print("Doing other work while scraping...")

# Check if scraping is finished
if scraper.is_complete():
    print("Scraping finished!")
else:
    # Wait for scraping to complete with timeout
    scraper.wait(timeout=10)
    html = scraper.get_html()
```

### Markdown Conversion Options

```python
scraper = Scraper(
    url="https://example.com/blog",
    markdown_options={
        "strip_tags": ["script", "style", "nav"],
        "content_selectors": ["article", ".post-content"],
        "preserve_images": True,
        "compact_output": True
    }
)
scraper.scrape()
markdown = scraper.get_markdown()
```

## License

MIT License
