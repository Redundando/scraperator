# scraperator

Audible/Amazon product and author data with dual-backend caching (local JSON or DynamoDB).

`AudibleProduct` fetches from the **Audible Catalog API** (no browser required). Author scrapers (`AudibleAuthor`, `AmazonAuthor`) use `ghostscraper` for browser-based scraping. A scraper-based fallback for products (`AudibleProductScraper`) is available for fields the API does not cover.

## Installation

```bash
pip install scraperator                    # AudibleProduct (API-based) + base classes
pip install scraperator[audible-scraper]   # + AudibleProductScraper, AudibleAuthor (requires beautifulsoup4, ghostscraper)
pip install scraperator[amazon]            # + AmazonAuthor (requires beautifulsoup4, boto3, httpx, Pillow)
```

Core dependencies: `httpx`, `dynamorator`, `logorator`.

---

## Types

### `ProductInput(tld, asin)` — `NamedTuple`

| Field | Type | Description |
|---|---|---|
| `tld` | `str` | Audible marketplace TLD, e.g. `"com"`, `"co.uk"`, `"fr"` |
| `asin` | `str` | Audible ASIN, e.g. `"B06VX22V89"` |

### `AuthorInput(tld, author_id)` — `NamedTuple`

| Field | Type | Description |
|---|---|---|
| `tld` | `str` | Marketplace TLD |
| `author_id` | `str` | 10-character author ID, e.g. `"B000AP9A6K"` |

### `LinkedEntity` — `TypedDict`

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Display name |
| `url` | `str \| None` | Associated URL, or `None` if unavailable |

### `ProductIdentity` — `TypedDict`

| Field | Type |
|---|---|
| `asin` | `str` |
| `tld` | `str` |

### `AuthorIdentity` — `TypedDict`

| Field | Type |
|---|---|
| `author_id` | `str` |
| `tld` | `str` |

---

## ScrapedModelConfig

Base configuration dataclass. All subclass configs inherit from this.

| Field | Type | Default | Description |
|---|---|---|---|
| `cache` | `str` | `"local"` | `"local"` = JSON files, `"dynamodb"` = DynamoDB, `"none"` = disabled |
| `cache_table` | `str \| None` | `None` | DynamoDB table name for parsed data |
| `cache_ttl_days` | `int` | `30` | TTL for DynamoDB cache entries |
| `cache_directory` | `str` | `"cache"` | Directory for local JSON cache files |
| `scrape_cache` | `str` | `"local"` | Where GhostScraper stores raw HTML (scraper classes only) |
| `scrape_cache_table` | `str \| None` | `None` | DynamoDB table name for raw HTML cache (scraper classes only) |
| `aws_region` | `str \| None` | `None` | AWS region for DynamoDB and S3 clients |
| `load_timeout_ms` | `int` | `30000` | Browser page load timeout in ms (scraper classes only) |
| `max_concurrent` | `int` | `5` | Max concurrent operations in `scrape_many` |
| `max_scrape_attempts` | `int` | `3` | Consecutive failures before setting `all_scrapes_unsuccessful` |
| `max_retries` | `int` | `3` | Per-request retries |
| `backoff_factor` | `float` | `2.0` | Exponential backoff multiplier between retries |
| `load_strategies` | `list[str]` | `["domcontentloaded"]` | Playwright load strategies (scraper classes only) |
| `wait_for_selectors` | `list[str]` | `[]` | CSS selectors to wait for (scraper classes only) |
| `browser_restart_every` | `int \| None` | `None` | Restart browser every N pages (scraper classes only) |
| `subprocess_batch_size` | `int \| None` | `None` | Pages per subprocess in `scrape_stream` (scraper classes only) |
| `stream_max_concurrent` | `int \| None` | `None` | Max concurrent pages in `scrape_stream` (scraper classes only) |
| `proxy` | `str \| None` | `None` | Proxy URL (scraper classes only) |

---

## ScrapedModel

Abstract base class. All product and author classes inherit from it.

### Constructor

```python
ScrapedModel.__init__(self, on_progress: Callable | None = None)
```

`super().__init__()` must be called **last** in subclass `__init__` — it immediately calls `load_cache()`.

### Instance attributes

| Attribute | Type | Description |
|---|---|---|
| `data` | `dict` | The parsed data dict. Populated after fetch or cache load |
| `cache_hit` | `bool` | `True` if data was loaded from cache |
| `on_progress` | `Callable \| None` | Progress callback |

### Properties

| Property | Type | Description |
|---|---|---|
| `cache_key` | `str` | Unique storage key |
| `url` | `str` | Canonical URL |
| `response_code` | `int \| None` | HTTP response code from the last fetch |
| `not_found` | `bool` | `True` if the last fetch returned 4xx |
| `all_scrapes_unsuccessful` | `bool` | `True` if `max_scrape_attempts` consecutive failures occurred. Not persisted across sessions. |
| `scrape_attempts` | `int` | Number of failed fetch attempts |

### Instance methods

| Method | Description |
|---|---|
| `await scrape(clear_cache=False) -> self` | Fetch data and populate `self.data`. No-op if cached (unless `clear_cache=True`) or `all_scrapes_unsuccessful`. |
| `load_cache() -> bool` | Load from cache into `self.data`. Called automatically in `__init__`. |
| `save_cache() -> None` | Persist `self.data` to cache. Sets `data["cached_at"]`. |
| `clear_cache() -> None` | Delete cached entry and reset `self.data = {}`. |
| `to_dict() -> dict` | Identity fields + `url` + `cache_hit` + all `data` keys. |
| `to_json(indent=2) -> str` | `to_dict()` as JSON string. |
| `pprint() -> None` | Print `to_dict()` as indented JSON. |

### Class methods

| Method | Description |
|---|---|
| `await scrape_many(items, ...) -> list` | Fetch a list of items concurrently. Deduplicates inputs. |
| `scrape_stream(items, ...) -> AsyncGenerator` | Streaming alternative. Yields cached items first, then fetched items. |

### Progress events

The `on_progress` callback receives `{"event": str, "ts": float, ...}`.

| Event | Extra keys | Description |
|---|---|---|
| `cache_hit` | `url` | Data loaded from cache |
| `scrape_skipped` | `url`, `reason` | Skipped due to `all_scrapes_unsuccessful` |
| `parse_complete` | `url`, `response_code` | Data parsed successfully |
| `not_found` | `url`, `response_code` | 4xx response |
| `scrape_failed` | `url`, `response_code`, `attempt`, `max_attempts` | 5xx or network failure |
| `all_scrapes_unsuccessful` | `url`, `attempt` | Max attempts reached |
| `cache_saved` | `url` | Cache written |
| `image_uploaded` | `url`, `key` | Image uploaded to S3 |
| `image_upload_failed` | `url`, `message` | S3 upload failed (non-fatal) |
| `batch_started` | `total`, `to_scrape`, `cached` | `scrape_many` started |
| `batch_done` | `total` | `scrape_many` finished |
| `stream_cache_loaded` | `total`, `cached`, `to_scrape` | `scrape_stream` initial cache load done |

---

## AudibleProduct

Fetches Audible product metadata from the **Audible Catalog API**. No browser required.

### Data source

```
GET https://api.audible.{tld}/1.0/catalog/products/{asin}
    ?response_groups=product_desc,product_attrs,contributors,media,rating,
                     category_ladders,relationships,tags,spotlight_tags
    &image_sizes=500
```

Batch endpoint for `scrape_many`:
```
GET https://api.audible.{tld}/1.0/catalog/products
    ?asins={asin1},{asin2},...
    &response_groups=...&image_sizes=...
```

### AudibleProductConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `api_base_urls` | `dict[str, str]` | All 11 Audible marketplaces | Map of TLD → API base URL |
| `response_groups` | `str` | `"product_desc,product_attrs,contributors,media,rating,category_ladders,relationships,tags,spotlight_tags"` | Comma-separated API response groups |
| `image_sizes` | `str` | `"500"` | Image pixel sizes to request |
| `batch_size` | `int` | `50` | Max ASINs per batch API call |
| `request_timeout` | `int` | `30` | httpx timeout in seconds |

Supported marketplaces: `com`, `co.uk`, `de`, `fr`, `co.jp`, `ca`, `com.au`, `it`, `es`, `com.br`, `in`.

### Construction

```python
AudibleProduct(tld="com", asin="B06VX22V89")
AudibleProduct(url="https://www.audible.com/pd/B06VX22V89")
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tld` | `str \| None` | Yes (unless `url` provided) | Marketplace TLD |
| `asin` | `str \| None` | Yes (unless `url` provided) | Product ASIN. Normalized to uppercase. |
| `url` | `str \| None` | No | Full Audible product URL. If provided, `tld` and `asin` are parsed from it. |
| `on_progress` | `Callable \| None` | No | Progress callback |

`cache_key`: `"audible_product_{tld}_{asin}"`
`url`: `"https://www.audible.{tld}/pd/{asin}"`

### Static methods

| Method | Returns | Description |
|---|---|---|
| `is_audible_url(url)` | `bool` | `True` if URL matches Audible product pattern (`/pd/`, `/podcast/`, `/ac/`) |
| `parse_url(url)` | `ProductInput \| None` | Extract `(tld, asin)` from URL |

### Instance methods

| Method | Description |
|---|---|
| `await scrape(clear_cache=False) -> AudibleProduct` | Fetch from API, populate `self.data`, save cache. Returns `self`. |

### Class methods

| Method | Description |
|---|---|
| `await scrape_many(products, max_concurrent=None, on_progress=None, clear_cache=False) -> list[AudibleProduct]` | Batch fetch using the multi-ASIN API endpoint. Groups by TLD, chunks by `batch_size`. |
| `scrape_stream(products, max_concurrent=None, on_progress=None, clear_cache=False) -> AsyncGenerator[AudibleProduct, None]` | Streaming alternative. Yields cached items first, then fetched items as batches complete. |

`products` is a `list[ProductInput]`.

### Data output (`self.data` keys)

| Key | Type | Description |
|---|---|---|
| `title` | `str \| None` | Product title |
| `subtitle` | `str \| None` | Subtitle (e.g. series subtitle, "A Novel") |
| `authors` | `list[LinkedEntity] \| None` | Authors. `url` is `https://www.audible.{tld}/author/{author_asin}` when author ASIN is available, otherwise falls back to `https://www.audible.{tld}/search?searchAuthor={name}`. |
| `narrators` | `list[LinkedEntity] \| None` | Narrators. `url` is `https://www.audible.{tld}/search?searchNarrator={name}`. |
| `series` | `LinkedEntity \| None` | Series name and URL. Extracted from `relationships` where `relationship_type == "series"`. `url` is the full series page URL. `None` if not part of a series. Falls back to `publication_name` (with `url: None`) if no relationship data. |
| `series_sequence` | `str \| None` | Book's position in the series (e.g. `"5"`, `"13"`). `None` if not part of a series. |
| `tags` | `list[LinkedEntity] \| None` | Content tags ordered by rank. Includes genre, theme, mood, and award tags. `url` is `https://www.audible.{tld}/tag/{tag_id}`. |
| `spotlight_tags` | `list[{"name": str, "type": str}] \| None` | 2–3 LLM-selected most relevant tags. Each has `name` and `type` (e.g. `"theme"`, `"world_tree-publisher_assigned"`). |
| `category_ladders` | `list[list[{"id": str, "name": str}]] \| None` | Full genre/category hierarchy. Each ladder is a list of nodes from root to leaf, each with `id` and `name`. |
| `release_date` | `str \| None` | Release date in ISO format `"YYYY-MM-DD"` |
| `rating` | `float \| None` | Average overall star rating |
| `num_ratings` | `int \| None` | Total number of ratings |
| `length_minutes` | `int \| None` | Total runtime in minutes |
| `publisher` | `LinkedEntity \| None` | Publisher name. `url` is always `None`. |
| `publisher_summary` | `str \| None` | Marketing description (HTML stripped to plain text) |
| `language` | `str \| None` | Language, title-cased (e.g. `"English"`) |
| `format` | `str \| None` | Format, title-cased (e.g. `"Unabridged"`, `"Original_Recording"`) |
| `is_audiobook` | `bool` | `True` if `content_delivery_type` is `SinglePartBook` or `MultiPartBook` |
| `is_audible_original` | `bool` | `True` if `publisher_name` contains "audible original" (case-insensitive heuristic) |
| `content_delivery_type` | `str \| None` | Product type: `"SinglePartBook"`, `"MultiPartBook"`, `"PodcastParent"`, `"PodcastEpisode"`, etc. |
| `is_vvab` | `bool` | Virtual Voice Audiobook flag |
| `has_children` | `bool` | Whether this product has child ASINs |
| `image_url` | `str \| None` | Cover image URL |
| `available_regions` | `None` | Always `None`. Not available from API. Use `AudibleProductScraper` if needed. |
| `seo` | `None` | Always `None`. Not available from API. Use `AudibleProductScraper` if needed. |
| `response_code` | `int \| None` | HTTP status code from the API call |
| `cached_at` | `str` | UTC ISO timestamp set by `save_cache()` |

### Properties

All `data` keys above are accessible as properties. Additional convenience properties:

| Property | Type | Description |
|---|---|---|
| `author` | `LinkedEntity \| None` | First author, or `None` |
| `narrator` | `LinkedEntity \| None` | First narrator, or `None` |

### `to_dict()` output

`asin`, `tld`, `url`, `cache_hit`, and all `data` keys listed above.

---

## AudibleProductScraper

Browser-based scraper fallback for Audible product pages. Use when you need `available_regions`, `seo`, or more accurate `is_audible_original` detection.

Requires the `audible-scraper` extra: `pip install scraperator[audible-scraper]`

### AudibleProductScraperConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `audible_params` | `str` | `"overrideBaseCountry=true&ipRedirectOverride=true"` | Query params appended to the scrape URL |

### Construction

Same as `AudibleProduct`:

```python
AudibleProductScraper(tld="com", asin="B06VX22V89")
AudibleProductScraper(url="https://www.audible.com/pd/B06VX22V89")
```

`cache_key`: `"audible_product_{tld}_{asin}"` — same as `AudibleProduct`, so cache entries are interchangeable.

### Data output (`self.data` keys)

| Key | Type | Description |
|---|---|---|
| `title` | `str \| None` | Product title |
| `authors` | `list[LinkedEntity] \| None` | Authors with Audible URLs |
| `narrators` | `list[LinkedEntity] \| None` | Narrators with search URLs |
| `series` | `LinkedEntity \| None` | Series name and series page URL |
| `tags` | `list[LinkedEntity] \| None` | Categories and chip tags with URLs |
| `release_date` | `str \| None` | Release date as displayed on page (e.g. `"01-20-26"`) |
| `rating` | `float \| None` | Average star rating |
| `num_ratings` | `int \| None` | Number of ratings |
| `length_minutes` | `int \| None` | Runtime in minutes |
| `publisher` | `LinkedEntity \| None` | Publisher with search URL |
| `publisher_summary` | `str \| None` | Full publisher description (plain text) |
| `language` | `str \| None` | Language (e.g. `"English"`) |
| `format` | `str \| None` | Format (e.g. `"Unabridged Audiobook"`) |
| `is_audiobook` | `bool` | `True` if LD+JSON contains `Audiobook` type |
| `is_audible_original` | `bool` | `True` if page badge or publisher name indicates Audible Original |
| `image_url` | `str \| None` | Cover image URL |
| `available_regions` | `dict[str, str] \| None` | Map of `hreflang` → URL for alternate marketplace links |
| `seo` | `dict \| None` | SEO metadata: `title`, `description`, `canonical`, `robots`, `googlebot`, `og`, `twitter`, `hreflang` |
| `response_code` | `int \| None` | HTTP status code |
| `cached_at` | `str` | UTC ISO timestamp |

### Fields only available via scraper (not from API)

| Field | Description |
|---|---|
| `available_regions` | Cross-marketplace hreflang links |
| `seo` | Full SEO metadata (og, twitter, canonical, robots) |
| `is_audible_original` | More accurate detection via page badge |

---

## AudibleAuthor

Scrapes an Audible author page. Browser-based via `ghostscraper`.

Requires the `audible-scraper` extra: `pip install scraperator[audible-scraper]`

### AudibleAuthorConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `audible_params` | `str` | `"overrideBaseCountry=true&ipRedirectOverride=true"` | Query params appended to the scrape URL |
| `s3_bucket` | `str \| None` | `None` | S3 bucket for author image uploads. If `None`, image upload is skipped. |
| `s3_prefix` | `str` | `"audible-authors/"` | S3 key prefix for uploaded images |

### Construction

```python
AudibleAuthor(tld="com", author_id="B000AP9A6K")
AudibleAuthor(url="https://www.audible.com/author/B000AP9A6K")
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tld` | `str \| None` | Yes (unless `url` provided) | Marketplace TLD |
| `author_id` | `str \| None` | Yes (unless `url` provided) | 10-character author ID |
| `url` | `str \| None` | No | Full Audible author URL |
| `on_progress` | `Callable \| None` | No | Progress callback |

`cache_key`: `"audible_author_{tld}_{author_id}"`

### Static methods

| Method | Returns | Description |
|---|---|---|
| `is_audible_author_url(url)` | `bool` | `True` if URL matches Audible author pattern |
| `parse_url(url)` | `AuthorInput \| None` | Extract `(tld, author_id)` from URL |

### Data output (`self.data` keys)

| Key | Type | Description |
|---|---|---|
| `name` | `str \| None` | Author name |
| `image_url` | `str \| None` | Author image URL from the page |
| `image_s3_key` | `str \| None` | S3 key of the uploaded image. Set after successful S3 upload. |
| `description` | `str \| None` | Author biography text |
| `audiobooks` | `list[LinkedEntity] \| None` | Audiobooks listed on the author page, each with `name` and `url` |
| `response_code` | `int \| None` | HTTP status code |
| `cached_at` | `str` | UTC ISO timestamp |

### Image upload

If `config.s3_bucket` is set, `scrape()` / `scrape_many()` / `scrape_stream()` upload the author image to S3 after parsing and store the key in `data["image_s3_key"]`. Pass `upload_images=False` to skip. The S3 key is `{config.s3_prefix}{cache_key}.{ext}`.

### `to_dict()` output

`author_id`, `tld`, `url`, `cache_hit`, and all `data` keys listed above.

---

## AmazonAuthor

Scrapes an Amazon author store page. Browser-based via `ghostscraper`.

Requires the `amazon` extra: `pip install scraperator[amazon]`

### AmazonAuthorConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `s3_bucket` | `str \| None` | `None` | S3 bucket for author image uploads |
| `s3_prefix` | `str` | `"amazon-authors/"` | S3 key prefix for uploaded images |
| `placeholder_s3_key` | `str \| None` | `None` | S3 key of the Amazon placeholder image, used by `is_placeholder_image()` |

### Construction

```python
AmazonAuthor(tld="com", author_id="B000AP9A6K")
AmazonAuthor(url="https://www.amazon.com/stores/J.K.-Rowling/author/B000AP9A6K")
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tld` | `str \| None` | Yes (unless `url` provided) | Marketplace TLD |
| `author_id` | `str \| None` | Yes (unless `url` provided) | 10-character author ID |
| `url` | `str \| None` | No | Full Amazon author URL. Stored verbatim as `self.url`. |
| `on_progress` | `Callable \| None` | No | Progress callback |

`cache_key`: `"amazon_author_{tld}_{author_id}"`

### Static methods

| Method | Returns | Description |
|---|---|---|
| `is_amazon_author_url(url)` | `bool` | `True` if URL matches Amazon author pattern |
| `parse_url(url)` | `AuthorInput \| None` | Extract `(tld, author_id)` from URL |

### Instance methods

| Method | Returns | Description |
|---|---|---|
| `await is_placeholder_image()` | `bool` | Compares uploaded image against `config.placeholder_s3_key` using 16×16 grayscale pixel diff. Returns `True` if mean diff < 10. Returns `False` if `image_s3_key` or `placeholder_s3_key` is not set. |

### Data output (`self.data` keys)

| Key | Type | Description |
|---|---|---|
| `name` | `str \| None` | Author name |
| `image_url` | `str \| None` | Author image URL from the page |
| `image_s3_key` | `str \| None` | S3 key of the uploaded image |
| `response_code` | `int \| None` | HTTP status code |
| `cached_at` | `str` | UTC ISO timestamp |

### `to_dict()` output

`author_id`, `tld`, `url`, `cache_hit`, and all `data` keys listed above.

---

## Cache behaviour

- **5xx responses and network failures are never cached.** The object is retried on the next `scrape()` call.
- **4xx (not found) and successful fetches are cached permanently** (subject to `cache_ttl_days` on DynamoDB).
- `all_scrapes_unsuccessful` is set after `max_scrape_attempts` consecutive 5xx/network failures. Once set, `scrape()` becomes a no-op for the rest of the current session. The flag is **not** persisted — `load_cache()` treats these entries as invalid, so the item is retried on the next run.
- Cache validity: an entry is valid if it has `not_found` or a `response_code < 500`.

### Cache interchangeability

`AudibleProduct` (API) and `AudibleProductScraper` share the same `cache_key` format (`audible_product_{tld}_{asin}`). A cache entry written by one can be read by the other. The data shapes differ slightly (see field tables above), but all shared properties work with either source.

### Two independent cache tables (scraper classes only)

Scraper-based classes (`AudibleProductScraper`, `AudibleAuthor`, `AmazonAuthor`) operate with two separate cache backends:

- `config.cache_table` — DynamoDB table for parsed data (`data` dict).
- `config.scrape_cache_table` — DynamoDB table for raw GhostScraper HTML cache.

`AudibleProduct` (API-based) only uses `config.cache_table`. There is no raw HTML cache.

---

## Usage examples

### AudibleProduct — single item

```python
import asyncio
from scraperator import AudibleProduct, AudibleProductConfig

AudibleProduct.config = AudibleProductConfig(
    cache="dynamodb",
    cache_table="my-table",
    aws_region="us-east-1",
)

async def main():
    p = AudibleProduct(tld="com", asin="B06VX22V89")
    await p.scrape()
    print(p.title, p.authors, p.series, p.series_sequence)

asyncio.run(main())
```

### AudibleProduct — batch

```python
from scraperator import AudibleProduct, ProductInput

products = await AudibleProduct.scrape_many([
    ProductInput("com", "B06VX22V89"),
    ProductInput("com", "B00MTTG9NC"),
    ProductInput("co.uk", "B07BB4FHKQ"),
])
for p in products:
    print(p.title, p.rating)
```

### AudibleProduct — streaming

```python
from scraperator import AudibleProduct, ProductInput

async for p in AudibleProduct.scrape_stream([
    ProductInput("com", "B06VX22V89"),
    ProductInput("com", "B00MTTG9NC"),
]):
    print(p.title)
```

### AudibleProductScraper — fallback for scrape-only fields

```python
from scraperator import AudibleProductScraper, AudibleProductScraperConfig

AudibleProductScraper.config = AudibleProductScraperConfig(
    cache="dynamodb",
    cache_table="my-table",
)

p = AudibleProductScraper(tld="com", asin="B06VX22V89")
await p.scrape()
print(p.available_regions)  # only available via scraper
print(p.seo)                # only available via scraper
```

### AudibleAuthor

```python
from scraperator import AudibleAuthor, AudibleAuthorConfig, AuthorInput

AudibleAuthor.config = AudibleAuthorConfig(
    cache="dynamodb",
    cache_table="my-table",
    s3_bucket="my-bucket",
)

authors = await AudibleAuthor.scrape_many([
    AuthorInput("com", "B000AP9A6K"),
])
for a in authors:
    print(a.name, a.description, a.image_s3_key)
```

### Hydrating from an external store without cache

```python
p = AudibleProduct(tld="com", asin="B06VX22V89", use_cache=False)
p.data = existing_record
```
