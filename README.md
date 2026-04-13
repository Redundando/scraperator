# scraperator

`ScrapedModel` base class and Audible/Amazon scrapers with dual-backend caching (local JSON or DynamoDB) built on top of `ghostscraper`.

## Installation

```bash
pip install scraperator           # base class only
pip install scraperator[audible]  # + AudibleProduct, AudibleAuthor (requires beautifulsoup4)
pip install scraperator[amazon]   # + AmazonAuthor (requires beautifulsoup4, boto3, httpx, Pillow)
```

---

## Types

These named types are used throughout the API.

### `ProductInput(tld, asin)` — `NamedTuple`

Immutable input for Audible product construction and batch operations.

- `tld: str` — Audible marketplace TLD, e.g. `"com"`, `"co.uk"`, `"fr"`
- `asin: str` — Audible ASIN, e.g. `"B06VX22V89"`

### `AuthorInput(tld, author_id)` — `NamedTuple`

Immutable input for author construction and batch operations.

- `tld: str` — Marketplace TLD
- `author_id: str` — 10-character author ID, e.g. `"B000AP9A6K"`

### `LinkedEntity` — `TypedDict`

A named entity with an optional URL. Used for authors, narrators, publishers, series, tags, audiobooks.

- `name: str`
- `url: str | None`

### `ProductIdentity` — `TypedDict`

- `asin: str`
- `tld: str`

### `AuthorIdentity` — `TypedDict`

- `author_id: str`
- `tld: str`

---

## ScrapedModelConfig

Base configuration dataclass. All subclass configs inherit from this. Set as a class attribute on the subclass before use.

```python
AudibleProduct.config = AudibleProductConfig(cache="dynamodb", cache_table="my-table")
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `cache` | `str` | `"local"` | Where to store parsed data. `"local"` = JSON files, `"dynamodb"` = DynamoDB, `"none"` = disabled |
| `cache_table` | `str \| None` | `None` | DynamoDB table name for parsed data |
| `cache_ttl_days` | `int` | `30` | TTL for DynamoDB cache entries |
| `cache_directory` | `str` | `"cache"` | Directory for local JSON cache files |
| `scrape_cache` | `str` | `"local"` | Where GhostScraper stores raw HTML. Same options as `cache` |
| `scrape_cache_table` | `str \| None` | `None` | DynamoDB table name for raw HTML cache |
| `aws_region` | `str \| None` | `None` | AWS region for DynamoDB and S3 clients |
| `load_timeout_ms` | `int` | `30000` | Browser page load timeout in milliseconds |
| `max_concurrent` | `int` | `5` | Max concurrent browser pages in `scrape_many` |
| `max_scrape_attempts` | `int` | `3` | Consecutive 5xx/network failures before setting `all_scrapes_unsuccessful` |
| `max_retries` | `int` | `3` | Per-request retries inside GhostScraper |
| `backoff_factor` | `float` | `2.0` | Exponential backoff multiplier between retries |
| `load_strategies` | `list[str]` | `["domcontentloaded"]` | Playwright load event strategies |
| `wait_for_selectors` | `list[str]` | `[]` | CSS selectors to wait for before considering the page loaded |
| `browser_restart_every` | `int \| None` | `None` | Restart the browser process every N pages in `scrape_many` |
| `subprocess_batch_size` | `int \| None` | `None` | Pages per subprocess chunk in `scrape_stream` |
| `stream_max_concurrent` | `int \| None` | `None` | Max concurrent pages in `scrape_stream`; falls back to `max_concurrent` |
| `proxy` | `str \| None` | `None` | Proxy URL passed to GhostScraper, e.g. `"socks5://localhost:1080"` |

---

## ScrapedModel

Abstract base class. All scrapers inherit from it.

### Constructor

```python
ScrapedModel.__init__(self, on_progress: Callable | None = None)
```

- `on_progress` — Optional callback called with a progress event dict `{"event": str, "ts": float, ...}` at key lifecycle points. See [Progress events](#progress-events).

`super().__init__()` must be called **last** in subclass `__init__`, because it immediately calls `load_cache()`, which calls `cache_key`. All instance attributes needed by `cache_key` must be set before calling super.

### Instance attributes

| Attribute | Type | Description |
|---|---|---|
| `data` | `dict` | The parsed data dict. Populated after a successful scrape or cache load |
| `cache_hit` | `bool` | `True` if data was loaded from cache rather than scraped |
| `on_progress` | `Callable \| None` | The progress callback passed at construction |

### Properties

| Property | Type | Description |
|---|---|---|
| `cache_key` | `str` | **Abstract.** Unique storage key for this object, e.g. `"audible_product_com_B06VX22V89"` |
| `url` | `str` | **Abstract.** Canonical URL for this object |
| `response_code` | `int \| None` | HTTP response code from the last scrape, stored in `data` |
| `not_found` | `bool` | `True` if the last scrape returned a 4xx response |
| `all_scrapes_unsuccessful` | `bool` | `True` if `max_scrape_attempts` consecutive 5xx/network failures occurred. Once set, `scrape()` becomes a no-op until cache is cleared |
| `scrape_attempts` | `int` | Number of failed scrape attempts recorded in `data` |

### Instance methods

#### `scrape(clear_cache=False, upload_images=True) -> ScrapedModel` *(async)*

Scrapes the URL and populates `self.data`. Returns `self` for chaining.

- `clear_cache: bool` — If `True`, ignores existing cached data and re-scrapes. Default `False`.
- `upload_images: bool` — If `True` and `config.s3_bucket` is set, uploads the image to S3 after parsing. Default `True`.
- Returns: `self`
- Short-circuits and returns `self` immediately if `self.data` is already populated (cache hit) and `clear_cache` is `False`, or if `all_scrapes_unsuccessful` is set.

#### `load_cache() -> bool`

Loads data from the configured cache backend into `self.data`.

- Returns: `True` if valid cached data was found and loaded, `False` otherwise.
- Called automatically in `__init__`. Only call manually if you need to reload.
- Cache entries with a 5xx `response_code` are considered invalid and are not loaded.

#### `save_cache() -> None`

Persists `self.data` to the configured cache backend. Sets `data["cached_at"]` to the current UTC ISO timestamp before saving.

- No-op if `config.cache == "none"`.

#### `clear_cache() -> None`

Deletes the cached entry for this object and resets `self.data = {}`.

- For `"local"` cache: deletes the JSON file.
- For `"dynamodb"` cache: deletes the DynamoDB item.

#### `to_dict() -> dict`

Returns a flat dict combining identity fields, `url`, `cache_hit`, and all fields from `self.data`.

- Returns: `dict` with keys from `_identity_dict()` + `"url"` + `"cache_hit"` + all `data` keys.

#### `to_json(indent=2) -> str`

Returns `to_dict()` serialized as a JSON string.

- `indent: int` — JSON indentation level. Default `2`.
- Returns: `str`

#### `pprint() -> None`

Prints `to_dict()` as indented JSON to stdout.

### Class methods

#### `scrape_many(items, max_concurrent=None, on_progress=None, clear_cache=False, upload_images=True) -> list[ScrapedModel]` *(async)*

Scrapes a list of items concurrently using a shared browser pool.

- `items: list` — List of inputs. Deduplicated via `dict.fromkeys` before processing; if duplicates are present, the returned list will be shorter than the input.
- `max_concurrent: int | None` — Overrides `config.max_concurrent` for this call.
- `on_progress: Callable | None` — Progress callback. Receives batch-level events (`batch_started`, `batch_done`) in addition to per-item events.
- `clear_cache: bool` — Re-scrape all items even if cached. Default `False`.
- `upload_images: bool` — Upload images to S3 after parsing. Default `True`.
- Returns: `list[ScrapedModel]` — One object per deduplicated input, in input order. Cached items are included without re-scraping.

#### `scrape_stream(items, subprocess_batch_size=None, max_concurrent=None, on_progress=None, stream_id=None, upload_images=True) -> AsyncGenerator[ScrapedModel, None]` *(async generator)*

Memory-safe streaming alternative to `scrape_many`. Runs scraping in disposable subprocesses so Chromium memory is reclaimed by the OS between batches.

- `items: list` — List of inputs. Deduplicated before processing.
- `subprocess_batch_size: int | None` — Pages per subprocess chunk. Falls back to `config.subprocess_batch_size`.
- `max_concurrent: int | None` — Overrides `config.stream_max_concurrent` or `config.max_concurrent`.
- `on_progress: Callable | None` — Progress callback. Receives a `stream_cache_loaded` event after the initial cache batch load.
- `stream_id: str | None` — Optional identifier passed to GhostScraper for stream resumption.
- `upload_images: bool` — Upload images to S3 after parsing. Default `True`.
- Yields: `ScrapedModel` — Cached items are yielded first in input order, then uncached items are yielded as they complete.
- When `config.cache == "dynamodb"`, performs a single batch DynamoDB read for all items before streaming begins, instead of one read per item.

### Abstract methods (implement in subclasses)

| Method | Description |
|---|---|
| `cache_key -> str` | Unique storage key |
| `url -> str` | Canonical URL |
| `_from_input(cls, item) -> ScrapedModel` | Construct an instance from a single input item |
| `_parse_html(html, scraper=None) -> dict` *(async)* | Parse HTML and return the data dict |
| `_identity_dict() -> dict` | Return identity fields prepended to `to_dict()` output |

### Progress events

The `on_progress` callback receives a dict with at minimum `{"event": str, "ts": float}`. Additional keys depend on the event:

| Event | Extra keys | Description |
|---|---|---|
| `cache_hit` | `url` | `scrape()` returned cached data |
| `scrape_skipped` | `url`, `reason` | `scrape()` skipped due to `all_scrapes_unsuccessful` |
| `parse_complete` | `url`, `response_code` | HTML parsed successfully |
| `not_found` | `url`, `response_code` | 4xx response received |
| `scrape_failed` | `url`, `response_code`, `attempt`, `max_attempts` | 5xx or network failure |
| `all_scrapes_unsuccessful` | `url`, `attempt` | Max attempts reached |
| `cache_saved` | `url` | Cache written |
| `image_uploaded` | `url`, `key` | Image uploaded to S3 |
| `image_upload_failed` | `url`, `message` | S3 upload failed (non-fatal) |
| `batch_started` | `total`, `to_scrape`, `cached` | `scrape_many` started |
| `batch_done` | `total` | `scrape_many` finished |
| `stream_cache_loaded` | `total`, `cached`, `to_scrape` | `scrape_stream` initial cache load done |

---

## AudibleProductConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `audible_params` | `str` | `"overrideBaseCountry=true&ipRedirectOverride=true"` | Query params appended to the scrape URL to force the correct marketplace regardless of server IP |

---

## AudibleProduct

Scrapes an Audible product page.

### Construction

```python
AudibleProduct(tld="com", asin="B06VX22V89")
AudibleProduct(url="https://www.audible.com/pd/B06VX22V89")
```

- `tld: str | None` — Marketplace TLD. Required if `url` is not provided.
- `asin: str | None` — Product ASIN. Required if `url` is not provided. Normalized to uppercase.
- `url: str | None` — Full Audible product URL. If provided, `tld` and `asin` are parsed from it. Raises `ValueError` if the URL cannot be parsed.
- `on_progress: Callable | None` — Progress callback.

`cache_key` format: `"audible_product_{tld}_{asin}"` e.g. `"audible_product_com_B06VX22V89"`

`url` returns the clean canonical URL (`/pd/{asin}`). The actual scrape hits `_scrape_url`, which appends `config.audible_params`. If debugging a GhostScraper cache miss, look for the parameterised URL.

### Static methods

#### `is_audible_url(url) -> bool`

Returns `True` if the URL matches the Audible product URL pattern (supports `/pd/`, `/podcast/`, and `/ac/` paths).

- `url: str`
- Returns: `bool`

#### `parse_url(url) -> ProductInput | None`

Extracts `(tld, asin)` from an Audible product URL.

- `url: str`
- Returns: `ProductInput(tld, asin)` or `None` if the URL does not match.

### Class methods

#### `scrape_many(products, max_concurrent=None, on_progress=None, clear_cache=False, upload_images=True) -> list[AudibleProduct]` *(async)*

Same semantics as `ScrapedModel.scrape_many`. `products` is a `list[ProductInput]`.

Returns: `list[AudibleProduct]`

#### `scrape_stream(products, subprocess_batch_size=None, max_concurrent=None, on_progress=None, stream_id=None, upload_images=True) -> AsyncGenerator[AudibleProduct, None]`

Same semantics as `ScrapedModel.scrape_stream`. `products` is a `list[ProductInput]`.

Yields: `AudibleProduct`

### Properties (data accessors)

All return `None` if the data has not been scraped yet.

| Property | Type | Description |
|---|---|---|
| `title` | `str \| None` | Product title |
| `authors` | `list[LinkedEntity] \| None` | All authors |
| `author` | `LinkedEntity \| None` | First author, or `None` |
| `narrators` | `list[LinkedEntity] \| None` | All narrators |
| `narrator` | `LinkedEntity \| None` | First narrator, or `None` |
| `series` | `LinkedEntity \| None` | Series name and URL |
| `tags` | `list[LinkedEntity] \| None` | Category and chip tags combined |
| `release_date` | `str \| None` | Release date string as found on the page |
| `rating` | `float \| None` | Average star rating |
| `num_ratings` | `int \| None` | Number of ratings |
| `length_minutes` | `int \| None` | Total runtime in minutes |
| `publisher` | `LinkedEntity \| None` | Publisher name and URL |
| `publisher_summary` | `str \| None` | Publisher description text |
| `language` | `str \| None` | Language string |
| `format` | `str \| None` | Format string (e.g. `"Unabridged"`) |
| `image_url` | `str \| None` | Cover image URL |
| `available_regions` | `dict[str, str] \| None` | Map of `hreflang` → URL for alternate marketplace links |
| `is_audiobook` | `bool` | `True` if the LD+JSON contains an `Audiobook` type |
| `is_audible_original` | `bool` | `True` if the product is an Audible Original |

### `to_dict()` output keys

`asin`, `tld`, `url`, `cache_hit`, and all data fields: `title`, `authors`, `narrators`, `series`, `tags`, `release_date`, `rating`, `num_ratings`, `length_minutes`, `publisher`, `publisher_summary`, `language`, `format`, `is_audiobook`, `is_audible_original`, `image_url`, `available_regions`, `seo`, `response_code`, `cached_at`.

The `seo` field is a dict with keys: `title`, `description`, `canonical`, `robots`, `googlebot`, `og`, `twitter`, `hreflang`.

---

## AudibleAuthorConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `audible_params` | `str` | `"overrideBaseCountry=true&ipRedirectOverride=true"` | Query params appended to the scrape URL |
| `s3_bucket` | `str \| None` | `None` | S3 bucket for author image uploads. If `None`, image upload is skipped |
| `s3_prefix` | `str` | `"audible-authors/"` | S3 key prefix for uploaded images |

---

## AudibleAuthor

Scrapes an Audible author page.

### Construction

```python
AudibleAuthor(tld="com", author_id="B000AP9A6K")
AudibleAuthor(url="https://www.audible.com/author/B000AP9A6K")
```

- `tld: str | None` — Marketplace TLD. Required if `url` is not provided.
- `author_id: str | None` — 10-character author ID. Required if `url` is not provided.
- `url: str | None` — Full Audible author URL. If provided, `tld` and `author_id` are parsed from it. Raises `ValueError` if the URL cannot be parsed.
- `on_progress: Callable | None` — Progress callback.

`cache_key` format: `"audible_author_{tld}_{author_id}"`

### Static methods

#### `is_audible_author_url(url) -> bool`

Returns `True` if the URL matches the Audible author URL pattern.

- `url: str`
- Returns: `bool`

#### `parse_url(url) -> AuthorInput | None`

Extracts `(tld, author_id)` from an Audible author URL.

- `url: str`
- Returns: `AuthorInput(tld, author_id)` or `None` if the URL does not match.

### Class methods

#### `scrape_many(authors, max_concurrent=None, on_progress=None, clear_cache=False, upload_images=True) -> list[AudibleAuthor]` *(async)*

Same semantics as `ScrapedModel.scrape_many`. `authors` is a `list[AuthorInput]`.

Returns: `list[AudibleAuthor]`

#### `scrape_stream(authors, subprocess_batch_size=None, max_concurrent=None, on_progress=None, stream_id=None, upload_images=True) -> AsyncGenerator[AudibleAuthor, None]`

Same semantics as `ScrapedModel.scrape_stream`. `authors` is a `list[AuthorInput]`.

Yields: `AudibleAuthor`

### Properties (data accessors)

| Property | Type | Description |
|---|---|---|
| `name` | `str \| None` | Author name |
| `image_url` | `str \| None` | Author image URL from the page |
| `image_s3_key` | `str \| None` | S3 key of the uploaded image. Set after a successful S3 upload |
| `description` | `str \| None` | Author biography text |
| `audiobooks` | `list[LinkedEntity] \| None` | Audiobooks listed on the author page |

### Image upload

If `config.s3_bucket` is set, `scrape()` / `scrape_many()` / `scrape_stream()` will upload the author image to S3 after parsing and store the S3 key in `data["image_s3_key"]`. Pass `upload_images=False` to skip. The upload is a no-op if `image_s3_key` is already set in the cached data. The S3 key is `{config.s3_prefix}{cache_key}.{ext}`.

### `to_dict()` output keys

`author_id`, `tld`, `url`, `cache_hit`, and all data fields: `name`, `image_url`, `image_s3_key`, `description`, `audiobooks`, `response_code`, `cached_at`.

---

## AmazonAuthorConfig

Inherits all fields from `ScrapedModelConfig`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `s3_bucket` | `str \| None` | `None` | S3 bucket for author image uploads |
| `s3_prefix` | `str` | `"amazon-authors/"` | S3 key prefix for uploaded images |
| `placeholder_s3_key` | `str \| None` | `None` | S3 key of the Amazon placeholder image, used by `is_placeholder_image()` |

---

## AmazonAuthor

Scrapes an Amazon author store page.

### Construction

```python
AmazonAuthor(tld="com", author_id="B000AP9A6K")
AmazonAuthor(url="https://www.amazon.com/stores/J.K.-Rowling/author/B000AP9A6K")
```

- `tld: str | None` — Marketplace TLD. Required if `url` is not provided.
- `author_id: str | None` — 10-character author ID. Required if `url` is not provided.
- `url: str | None` — Full Amazon author URL. If provided, `tld` and `author_id` are parsed from it. The original URL (including any slug path) is stored verbatim as `self.url`. Raises `ValueError` if the URL cannot be parsed.
- `on_progress: Callable | None` — Progress callback.

When constructed with `tld` + `author_id`, a canonical URL `https://www.amazon.{tld}/stores/author/{author_id}` is generated. Both construction paths produce the same `cache_key`.

`cache_key` format: `"amazon_author_{tld}_{author_id}"`

### Static methods

#### `is_amazon_author_url(url) -> bool`

Returns `True` if the URL matches the Amazon author URL pattern.

- `url: str`
- Returns: `bool`

#### `parse_url(url) -> AuthorInput | None`

Extracts `(tld, author_id)` from an Amazon author URL.

- `url: str`
- Returns: `AuthorInput(tld, author_id)` or `None` if the URL does not match.

### Instance methods

#### `is_placeholder_image() -> bool` *(async)*

Compares the uploaded author image against the configured placeholder image using a 16×16 grayscale pixel diff. Returns `True` if the mean pixel difference is less than 10 (i.e. the images are visually identical).

- Returns `False` immediately if `image_s3_key` is not set or `config.placeholder_s3_key` is not set.
- Requires `config.s3_bucket` to be set.
- Returns: `bool`

### Class methods

#### `scrape_many(authors, max_concurrent=None, on_progress=None, clear_cache=False, upload_images=True) -> list[AmazonAuthor]` *(async)*

Same semantics as `ScrapedModel.scrape_many`. `authors` is a `list[AuthorInput]`.

Returns: `list[AmazonAuthor]`

#### `scrape_stream(authors, subprocess_batch_size=None, max_concurrent=None, on_progress=None, stream_id=None, upload_images=True) -> AsyncGenerator[AmazonAuthor, None]`

Same semantics as `ScrapedModel.scrape_stream`. `authors` is a `list[AuthorInput]`.

Yields: `AmazonAuthor`

### Properties (data accessors)

| Property | Type | Description |
|---|---|---|
| `name` | `str \| None` | Author name |
| `image_url` | `str \| None` | Author image URL from the page |
| `image_s3_key` | `str \| None` | S3 key of the uploaded image. Set after a successful S3 upload |

### Image upload

Same behaviour as `AudibleAuthor`. S3 key is `{config.s3_prefix}{cache_key}.{ext}`.

### `to_dict()` output keys

`author_id`, `tld`, `url`, `cache_hit`, and all data fields: `name`, `image_url`, `image_s3_key`, `response_code`, `cached_at`.

---

## Cache behaviour

- **5xx responses and network failures are never cached.** The object is retried on the next `scrape()` call.
- **4xx (not found) and successful scrapes are cached permanently** (subject to `cache_ttl_days` on DynamoDB).
- `all_scrapes_unsuccessful` is set after `max_scrape_attempts` consecutive 5xx/network failures. Once set, `scrape()` becomes a no-op until `clear_cache()` is called.
- Cache validity check: an entry is valid if it has `all_scrapes_unsuccessful`, `not_found`, or a `response_code < 500`.

## Two independent cache tables

`scrape_many` and `scrape_stream` operate with two separate cache backends:

- `config.cache_table` — DynamoDB table for parsed product/author data (this model's `data` dict).
- `config.scrape_cache_table` — DynamoDB table for raw GhostScraper HTML cache (passed through to GhostScraper).

They are independent and can each be `None`.

## Hydrating from an external store without cache

```python
p = AudibleProduct(tld="com", asin="B06VX22V89", use_cache=False)
p.data = record
```

## Subclassing ScrapedModel

Implement these five members:

```python
@property
def cache_key(self) -> str: ...          # unique storage key

@property
def url(self) -> str: ...                # canonical URL

@classmethod
def _from_input(cls, item, ...) -> "SubClass": ...  # construct from a single input

async def _parse_html(self, html: str, scraper=None) -> dict: ...  # return the data dict

def _identity_dict(self) -> dict: ...    # fields prepended to to_dict() output
```

`super().__init__()` must be called **last** in `__init__`.
