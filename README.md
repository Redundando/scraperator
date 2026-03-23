# scraperator

`ScrapedModel` base class and Audible/Amazon scrapers with dual-backend caching (local JSON or DynamoDB) built on top of `ghostscraper`.

## Installation

```bash
pip install scraperator           # base class only
pip install scraperator[audible]  # + AudibleProduct, AudibleAuthor
pip install scraperator[amazon]   # + AmazonAuthor (requires boto3, httpx, Pillow)
```

---

## ScrapedModel

### Subclassing contract

Implement these five members:

```python
@property
def cache_key(self) -> str: ...          # unique storage key, e.g. "com_B06VX22V89"

@property
def url(self) -> str: ...                # canonical URL

@classmethod
def _from_input(cls, item, dynamodb_table=None, use_cache=True) -> "SubClass": ...

async def _parse_html(self, html: str, scraper=None) -> dict: ...  # return the data dict

def _identity_dict(self) -> dict: ...    # fields prepended to to_dict() output
```

**`super().__init__()` must be called last** in `__init__`. It immediately calls `load_cache()`, which calls `cache_key` — so all instance attributes the subclass needs for `cache_key` must be set before calling super.

### Configuration

Each subclass has a config dataclass that inherits from `ScrapedModelConfig`. Set it as a class attribute before use:

```python
AudibleProduct.config = AudibleProductConfig(
    load_timeout_ms=30000,
    max_concurrent=5,
    scrape_dynamodb_table="my-scrape-table",
    audible_params="overrideBaseCountry=true",
)
```

Defaults are defined on the dataclass and are usable out of the box without any configuration.

### Cache behaviour

- **5xx responses are never cached.** The object is retried on the next `scrape()` call. 4xx (not found) and successful scrapes are cached permanently (subject to `cache_ttl_days` on DynamoDB).
- `all_scrapes_unsuccessful` is set after `max_scrape_attempts` consecutive 5xx/network failures. Once set, `scrape()` becomes a no-op until the cache is cleared.

### Two DynamoDB tables

`scrape_many` and `scrape_stream` accept two separate table names:

- `dynamodb_table` — stores the parsed product/author data (this model's `data` dict)
- `scrape_dynamodb_table` — stores the raw GhostScraper HTML cache (passed through to GhostScraper); falls back to `config.scrape_dynamodb_table`

They are independent and can be `None` independently.

### `scrape_many` deduplication

Inputs are deduplicated via `dict.fromkeys` before scraping. If you pass duplicate items, the returned list will be shorter than the input. Don't rely on positional index alignment between input and output.

### Hydrating from an external store without cache

```python
p = AudibleProduct(tld="com", asin="B06VX22V89", use_cache=False)
p.data = record
```

---

## AudibleProduct

### Construction

```python
AudibleProduct(tld="com", asin="B06VX22V89")
AudibleProduct(url="https://www.audible.com/pd/B06VX22V89")
AudibleProduct.scrape_many([("com", "B06VX22V89"), ...])
```

Static helpers for URL classification before construction:

```python
AudibleProduct.is_audible_url(url)   # bool
AudibleProduct.parse_url(url)        # ProductInput | None  →  (tld, asin)
```

### Scrape URL vs canonical URL

`product.url` returns the clean canonical URL (`/pd/{asin}`). The actual scrape hits `_scrape_url`, which appends `config.audible_params`. These params force Audible to serve the requested marketplace TLD regardless of the server's IP location — without them, Audible redirects to the local market. If you're debugging a GhostScraper cache miss, look for the parameterised URL, not the canonical one.

---

## AudibleAuthor

### Construction

```python
AudibleAuthor(tld="com", author_id="B000AP9A6K")
AudibleAuthor(url="https://www.audible.com/author/B000AP9A6K")
```

### Image upload

If `config.s3_bucket` is set, `scrape()` / `scrape_many()` will upload the author image to S3 after parsing and store the key in `data["image_s3_key"]`. Pass `upload_images=False` to skip. The upload is a no-op if `image_s3_key` is already set in the cached data.

---

## AmazonAuthor

### Construction

```python
AmazonAuthor(tld="com", author_id="B000AP9A6K")
AmazonAuthor(url="https://www.amazon.com/stores/J.K.-Rowling/author/B000AP9A6K")
```

Static helpers:

```python
AmazonAuthor.is_amazon_author_url(url)   # bool
AmazonAuthor.parse_url(url)              # AuthorInput | None  →  (tld, author_id)
```

### URL preservation

When constructed with `url=`, the original URL (including any slug path) is stored verbatim as `self.url`. When constructed with `tld` + `author_id`, a canonical `/stores/author/{author_id}` URL is generated. Both produce the same `cache_key`.

### Image upload

Same behaviour as `AudibleAuthor`. Additionally, if `config.placeholder_s3_key` is set, you can check whether the uploaded image is the Amazon placeholder:

```python
await author.is_placeholder_image()  # bool
```
