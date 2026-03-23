---
Package: ghostscraper
Version: 0.9.5
Source: https://pypi.org/project/ghostscraper/
Fetched: 2026-03-23 16:22:31
---

# Ghostscraper

Playwright-based async web scraper with persistent caching, subprocess isolation for memory safety, and multiple output formats.

## Installation

```bash
pip install ghostscraper
```

Playwright browsers are installed automatically on first run.

## Quick Start

```python
import asyncio
from ghostscraper import GhostScraper

async def main():
    scraper = GhostScraper(url="https://example.com")
    print(await scraper.response_code())  # 200
    print(await scraper.text())           # plain text
    print(await scraper.markdown())       # markdown

asyncio.run(main())
```

## GhostScraper

### Constructor

```python
GhostScraper(
    url: str = "",
    cache: bool = True,
    clear_cache: bool = False,
    ttl: int = 999,
    markdown_options: Optional[Dict[str, Any]] = None,
    logging: bool = True,
    dynamodb_table: Optional[str] = None,
    on_progress: Optional[Callable] = None,
    lazy: bool = False,
    **kwargs  # forwarded to PlaywrightScraper
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | `""` | URL to scrape |
| `cache` | `bool` | `True` | Enable caching. `False` disables all cache reads/writes |
| `clear_cache` | `bool` | `False` | Delete existing cache entry on init |
| `ttl` | `int` | `999` | Cache time-to-live in days |
| `markdown_options` | `dict` | `None` | Options forwarded to `html2text.HTML2Text` |
| `logging` | `bool` | `True` | Enable/disable log output |
| `dynamodb_table` | `str` | `None` | DynamoDB table name. When set, replaces local cache with DynamoDB |
| `on_progress` | `Callable` | `None` | Progress callback (sync or async). Errors are swallowed |
| `lazy` | `bool` | `False` | Skip cache restore on init. Used internally by `ScrapeStream` |
| `**kwargs` | | | Forwarded to `PlaywrightScraper` (see below). Note: `cache`, `clear_cache`, `ttl`, `lazy`, and `markdown_options` are consumed by `GhostScraper` and never reach `PlaywrightScraper` |

**PlaywrightScraper kwargs** (passable to GhostScraper):

| Parameter | Type | Default | Description |
|---|---|---|---|
| `browser_type` | `str` | `"chromium"` | `"chromium"`, `"firefox"`, or `"webkit"` |
| `headless` | `bool` | `True` | Run browser headlessly |
| `browser_args` | `dict` | `None` | Extra args for `browser.launch()` |
| `context_args` | `dict` | `None` | Extra args for `browser.new_context()` |
| `max_retries` | `int` | `3` | Retry attempts per URL |
| `backoff_factor` | `float` | `2.0` | Exponential backoff multiplier |
| `network_idle_timeout` | `int` | `3000` | Timeout (ms) for `networkidle` strategy |
| `load_timeout` | `int` | `20000` | Timeout (ms) for other strategies |
| `wait_for_selectors` | `list` | `None` | CSS selectors to wait for after page load |
| `load_strategies` | `list` | `["load", "networkidle", "domcontentloaded"]` | Loading strategy chain, tried in order |
| `no_retry_on` | `list` | `None` | Status codes that skip retries (e.g. `[404, 410]`) |

### Instance Attributes

| Attribute | Type | Description |
|---|---|---|
| `url` | `str` | The URL this scraper was initialized with |
| `error` | `Exception \| None` | Set when a fetch fails under `fail_fast=False`. When set, `html()` returns `""` and `response_code()` returns `None` |

### Async Output Methods

All methods trigger a fetch (or cache restore) on first call. Subsequent calls return the cached/computed value.

| Method | Returns | Description |
|---|---|---|
| `await html()` | `str` | Raw HTML. Returns `""` if `error` is set |
| `await response_code()` | `int \| None` | HTTP status code. Returns `None` if `error` is set |
| `await response_headers()` | `dict` | HTTP response headers |
| `await redirect_chain()` | `list[dict]` | List of `{"url": str, "status": int}` entries |
| `await final_url()` | `str` | Last URL in redirect chain. Falls back to `self.url` |
| `await markdown()` | `str` | HTML converted to Markdown via `html2text` |
| `await text()` | `str` | Plain text via `newspaper4k` |
| `await authors()` | `list` | Authors detected by `newspaper4k` |
| `await article()` | `newspaper.Article` | Full parsed article object |
| `await soup()` | `BeautifulSoup` | Parsed HTML |
| `await seo()` | `dict` | SEO metadata (see below) |

#### SEO Dict Structure

All keys are omitted if the corresponding tag is absent:

```python
{
    "title": str,           # <title>
    "description": str,     # <meta name="description">
    "canonical": str,       # <link rel="canonical">
    "robots": {             # <meta name="robots">
        "noindex": True,
        "nofollow": True,
    },
    "googlebot": { ... },   # same shape as robots
    "og": {                 # <meta property="og:*">
        "title": str,
        "description": str,
        "image": str,
        "url": str,
    },
    "twitter": { ... },     # <meta name="twitter:*">
    "hreflang": {           # <link rel="alternate" hreflang="...">
        "en-us": ["https://..."],
        "de": ["https://..."],
    }
}
```

### Cache Methods

| Method | Description |
|---|---|
| `save_cache()` | Persist cached fields to disk/DynamoDB |
| `clear_cache_entry()` | Delete this URL's cache entry |
| `cache_stats()` | Returns `{"key": str, "exists": bool}` |
| `cache_list_keys(limit=100, last_key=None)` | Returns `{"keys": [...], "last_key": ...}` |

### Deprecated Methods

These still work but emit `DeprecationWarning`:

| Old | New |
|---|---|
| `json_cache_save()` | `save_cache()` |
| `json_cache_save_db()` | `save_cache()` |
| `json_cache_clear()` | `clear_cache_entry()` |
| `json_cache_stats()` | `cache_stats()` |
| `json_cache_list_db_keys()` | `cache_list_keys()` |

## Caching

Three cache modes, determined at construction:

| Mode | Condition | Behavior |
|---|---|---|
| **Local JSON** | Default (`cache=True`, no `dynamodb_table`) | JSON files in `data/ghostscraper/` |
| **DynamoDB** | `dynamodb_table` is set | DynamoDB only via dynamorator (compressed). No local files |
| **Disabled** | `cache=False` | All cache operations are no-ops |

Cached fields: `_html`, `_response_code`, `_response_headers`, `_redirect_chain`. Cache key: slugified URL. Derived outputs (`markdown`, `text`, `authors`, `soup`, `seo`, `article`) are computed in-memory and not persisted.

```python
# Local cache (default)
scraper = GhostScraper(url="https://example.com")

# DynamoDB cache
scraper = GhostScraper(url="https://example.com", dynamodb_table="my-cache-table")

# No cache
scraper = GhostScraper(url="https://example.com", cache=False)

# Force re-fetch
scraper = GhostScraper(url="https://example.com", clear_cache=True)
```

## Batch Scraping

```python
scrapers = await GhostScraper.scrape_many(
    urls=["https://example.com", "https://python.org"],
    max_concurrent=5,
    ttl=7,
    load_strategies=["domcontentloaded"],
)
for scraper in scrapers:
    print(await scraper.text())
```

### scrape_many Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `urls` | `list[str]` | required | URLs to scrape |
| `max_concurrent` | `int` | `15` | Max concurrent page loads |
| `logging` | `bool` | `True` | Enable logging |
| `fail_fast` | `bool` | `True` | `True`: exception aborts batch. `False`: failed scrapers get `error` set |
| `on_scraped` | `Callable` | `None` | Callback per URL (sync or async). Fires for cached URLs too |
| `browser_restart_every` | `int` | `None` | Restart browser every N pages to cap memory growth |
| `on_progress` | `Callable` | `None` | Progress callback |
| `**kwargs` | | | Forwarded to `GhostScraper` and `PlaywrightScraper` |

Returns `List[GhostScraper]` in the same order as `urls`. Already-cached URLs are skipped.

### Partial Failure Handling

```python
scrapers = await GhostScraper.scrape_many(urls=urls, fail_fast=False)
for s in scrapers:
    if s.error:
        print(f"FAILED {s.url}: {s.error}")
    else:
        print(f"OK {s.url}: {await s.response_code()}")
```

### Memory-Efficient Batch Processing

```python
results = []

async def handle(scraper: GhostScraper) -> None:
    results.append(await scraper.text())
    scraper._html = None  # release — already persisted to cache

await GhostScraper.scrape_many(urls=urls, max_concurrent=10, on_scraped=handle)
```


## ScrapeStream

Memory-safe streaming for large URL sets. Each chunk runs in a disposable subprocess — when it exits, the OS reclaims all Chromium memory. Results are yielded one at a time via `async for`.

### Creating a Stream

```python
stream = GhostScraper.create_stream(
    urls=urls,
    dynamodb_table="my-cache-table",
    stream_id="my-seo-audit",
    priority=5,
    subprocess_batch_size=50,
    max_concurrent=10,
    on_progress=my_callback,
    # All other kwargs forwarded to GhostScraper/PlaywrightScraper
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `urls` | `list[str]` | required | URLs to scrape |
| `dynamodb_table` | `str` | `None` | DynamoDB table for cache. Local cache used if `None` |
| `stream_id` | `str` | auto UUID | Identifier for monitoring/cancellation |
| `priority` | `int` | `5` | Lower = higher priority (0–10) |
| `subprocess_batch_size` | `int` | `50` | URLs per subprocess |
| `max_concurrent` | `int` | `15` | Concurrent pages within each subprocess |
| `on_progress` | `Callable` | `None` | Progress callback |
| `**kwargs` | | | Forwarded to `GhostScraper`/`PlaywrightScraper` |

### Consuming Results

```python
async for scraper in stream:
    if scraper.error:
        print(f"FAILED {scraper.url}: {scraper.error}")
    else:
        text = await scraper.text()
        save_to_db(scraper.url, text)
    # scraper goes out of scope → GC reclaims
```

### Monitoring

```python
status = GhostScraper.get_stream_status("my-seo-audit")
# StreamStatus(stream_id, total, completed, failed, pending, status)
# status: "running" | "completed" | "cancelled"

all_streams = GhostScraper.get_all_streams()  # List[StreamStatus]
```

### Cancellation

```python
GhostScraper.cancel_stream("my-seo-audit")
# Current subprocess chunk finishes gracefully, then the async for loop ends
```

### Shutdown

```python
await GhostScraper.shutdown()
# Waits for running subprocesses, drains queue
```


## Fetch Raw Bytes

Fetch a URL as raw bytes using the Playwright browser context. Useful for CDN-protected resources that block plain HTTP clients.

```python
body, status_code, headers = await GhostScraper.fetch_bytes(
    "https://example.com/image.jpg",
    cache=True,
    ttl=30,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | required | URL to fetch |
| `cache` | `bool` | `False` | Persist result to disk/DynamoDB |
| `clear_cache` | `bool` | `False` | Force re-fetch |
| `ttl` | `int` | `999` | Cache TTL in days |
| `dynamodb_table` | `str` | `None` | DynamoDB table |
| `logging` | `bool` | `True` | Enable logging |
| `**kwargs` | | | Forwarded to `PlaywrightScraper` |

Returns `Tuple[bytes, int, dict]` — `(body, status_code, headers)`.

## Loading Strategies

Playwright loading strategies are tried in order, falling back on timeout:

1. `load` — waits for the `load` event. Works for most sites.
2. `networkidle` — waits until no network activity for 500ms. Better for JS-heavy pages.
3. `domcontentloaded` — waits only for HTML parsing. Fastest, least complete.

If all strategies fail, the attempt is retried up to `max_retries` times with exponential backoff.

```python
# Per-scraper override
scraper = GhostScraper(url=url, load_strategies=["domcontentloaded"])

# Global override
ScraperDefaults.LOAD_STRATEGIES = ["domcontentloaded"]
```


## Progress Callbacks

Pass `on_progress` to receive real-time events. Accepts sync and async callables. Errors inside the callback are swallowed.

```python
scraper = GhostScraper(url="https://example.com", on_progress=lambda e: print(e["event"]))
```

Each event is a dict with `event` (str) and `ts` (Unix timestamp). Additional fields vary by event:

| Event | Extra Fields | Notes |
|---|---|---|
| `started` | `url` | Before fetch begins |
| `loading_strategy` | `url`, `strategy`, `attempt`, `max_retries`, `timeout` | Per strategy attempt |
| `retry` | `url`, `attempt`, `max_retries` | When another attempt follows |
| `page_loaded` | `url`, `completed`, `total`, `status_code` | Success or error status |
| `error` | `url`, `message` | Unhandled exception |
| `batch_started` | `total`, `to_fetch`, `cached` | `scrape_many` only |
| `batch_done` | `total` | `scrape_many` only |
| `browser_ready` | `browser` | First-run browser check |
| `browser_installing` | `browser` | First-run install |

## ScraperDefaults

Global defaults, modifiable at runtime:

```python
from ghostscraper import ScraperDefaults

ScraperDefaults.BROWSER_TYPE = "chromium"
ScraperDefaults.HEADLESS = True
ScraperDefaults.LOAD_TIMEOUT = 20000            # ms
ScraperDefaults.NETWORK_IDLE_TIMEOUT = 3000     # ms
ScraperDefaults.LOAD_STRATEGIES = ["load", "networkidle", "domcontentloaded"]
ScraperDefaults.MAX_RETRIES = 3
ScraperDefaults.BACKOFF_FACTOR = 2.0
ScraperDefaults.MAX_CONCURRENT = 15
ScraperDefaults.CACHE_TTL = 999                 # days
ScraperDefaults.CACHE_DIRECTORY = "data/ghostscraper"
ScraperDefaults.DYNAMODB_TABLE = None
ScraperDefaults.BROWSER_RESTART_EVERY = None
ScraperDefaults.LOGGING = True

# Stream settings
ScraperDefaults.MAX_WORKERS = 2                 # concurrent subprocess workers
ScraperDefaults.SUBPROCESS_BATCH_SIZE = 50      # URLs per subprocess
ScraperDefaults.MAX_QUEUE_SIZE = 500            # max pending chunks in queue
ScraperDefaults.DEFAULT_PRIORITY = 5            # default stream priority (0–10)
```

## PlaywrightScraper

Low-level browser automation used internally. Use directly only for raw browser control.

```python
async with PlaywrightScraper(logging=False) as browser:
    html, status, headers, chain = await browser.fetch_url("https://example.com")
    body, status, headers = await browser.fetch_bytes("https://example.com/image.jpg")
```

| Method | Returns | Description |
|---|---|---|
| `await fetch()` | `(html, status, headers, chain)` | Fetch `self.url` |
| `await fetch_url(url)` | `(html, status, headers, chain)` | Fetch specific URL |
| `await fetch_many(urls, max_concurrent=5)` | `list[tuple]` | Parallel fetch |
| `await fetch_and_close()` | `(html, status, headers, chain)` | Fetch and close browser |
| `await fetch_bytes(url)` | `(bytes, status, headers)` | Raw bytes fetch |
| `await close()` | `None` | Close browser |
| `await check_and_install_browser()` | `bool` | Check/install browser |

Supports `async with` context manager.

## Dependencies

- playwright
- beautifulsoup4
- html2text
- newspaper4k
- python-slugify
- logorator
- dynamorator
- lxml_html_clean

## License

MIT. Contributions welcome: https://github.com/Redundando/ghostscraper
