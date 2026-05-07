import asyncio
import datetime
import hashlib
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from logorator import Logger

from .audible_product import AudibleProduct, _API_BASE_URLS, _RESPONSE_GROUPS, _parse_api_product
from .types import LinkedEntity, ProductInput, SearchInput, SearchResult

_logger = logging.getLogger(__name__)


@dataclass
class AudibleSearchConfig:
    # API
    api_base_urls: dict[str, str] = field(default_factory=lambda: dict(_API_BASE_URLS))
    response_groups: str = "contributors,product_attrs,product_desc,media"
    full_response_groups: str = _RESPONSE_GROUPS
    content_type: str = "Audiobook"
    size: int = 10
    request_timeout: int = 30

    # Cache
    cache: str = "local"  # "local", "dynamodb", "none"
    cache_table: str | None = None
    cache_ttl_days: int = 30
    cache_directory: str = "cache"
    aws_region: str | None = None

    # Retry
    max_retries: int = 3
    backoff_factor: float = 2.0

    # Concurrency
    max_concurrent: int = 3
    request_delay: float = 0.5


class AudibleSearch:
    """Search the Audible catalog by keywords. Standalone class with caching, retry, and progress events."""

    config: AudibleSearchConfig = AudibleSearchConfig()

    def __init__(
        self,
        tld: str,
        keywords: str,
        content_type: str | None = None,
        size: int | None = None,
        on_progress: Callable | None = None,
    ):
        self.tld = tld
        self.keywords = keywords
        self.content_type = content_type or self.config.content_type
        self.size = size or self.config.size
        self.on_progress = on_progress
        self.data: dict = {}
        self.cache_hit: bool = False

        if self.config.cache != "none":
            self.cache_hit = self.load_cache()

    def __str__(self) -> str:
        return f"AudibleSearch({self.tld}, {self.keywords!r})"

    # === Progress Events ===

    def _emit(self, event: str, **extra) -> None:
        if not self.on_progress:
            return
        try:
            self.on_progress({"event": event, "ts": time.time(), "keywords": self.keywords, "tld": self.tld, **extra})
        except Exception:
            _logger.warning("on_progress callback failed for %s", self.cache_key, exc_info=True)

    @staticmethod
    def _emit_static(on_progress: Callable | None, event: str, **extra) -> None:
        if not on_progress:
            return
        try:
            on_progress({"event": event, "ts": time.time(), **extra})
        except Exception:
            _logger.warning("on_progress callback failed", exc_info=True)

    # === Cache Key ===

    @property
    def cache_key(self) -> str:
        normalized = self.keywords.lower().strip()
        keywords_hash = hashlib.md5(normalized.encode()).hexdigest()
        return f"audible_search_{self.tld}_{keywords_hash}_{self.content_type}_{self.size}"

    # === Properties ===

    @property
    def products(self) -> list[SearchResult]:
        """Parsed search results as lightweight typed dicts."""
        raw_products = self.data.get("products") or []
        results: list[SearchResult] = []
        for p in raw_products:
            authors: list[LinkedEntity] | None = None
            if p.get("authors"):
                authors = [{"name": a.get("name", ""), "url": None} for a in p["authors"]]

            narrators: list[LinkedEntity] | None = None
            if p.get("narrators"):
                narrators = [{"name": n.get("name", ""), "url": None} for n in p["narrators"]]

            images = p.get("product_images") or {}
            image_url = next(iter(images.values()), None)

            results.append(SearchResult(
                asin=p.get("asin", ""),
                title=p.get("title"),
                authors=authors,
                narrators=narrators,
                language=(p.get("language") or "").title() or None,
                release_date=p.get("release_date"),
                runtime_length_min=p.get("runtime_length_min"),
                content_delivery_type=p.get("content_delivery_type"),
                image_url=image_url,
            ))
        return results

    @property
    def product_inputs(self) -> list[ProductInput]:
        """Convenience — list of ProductInput tuples for piping into AudibleProduct.scrape_many()."""
        return [ProductInput(self.tld, p["asin"]) for p in (self.data.get("products") or []) if p.get("asin")]

    @property
    def total_results(self) -> int | None:
        return self.data.get("total_results")

    @property
    def response_code(self) -> int | None:
        return self.data.get("response_code")

    # === Cache ===

    @Logger(exclude_args=["self"])
    def load_cache(self) -> bool:
        if self.config.cache == "dynamodb":
            from dynamorator import DynamoDBStore

            data = DynamoDBStore(
                table_name=self.config.cache_table, region_name=self.config.aws_region
            ).get(self.cache_key)
        elif self.config.cache == "local":
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            data = json.loads(path.read_text()) if path.exists() else None
        else:
            return False

        if not data:
            return False
        if data.get("response_code") and data["response_code"] < 500:
            self.data = data
            return True
        return False

    @Logger(exclude_args=["self"])
    def save_cache(self) -> None:
        if self.config.cache == "none":
            return
        self.data["cached_at"] = datetime.datetime.now(datetime.UTC).isoformat()
        if self.config.cache == "dynamodb":
            from dynamorator import DynamoDBStore

            DynamoDBStore(
                table_name=self.config.cache_table, region_name=self.config.aws_region
            ).put(self.cache_key, self.data, ttl_days=self.config.cache_ttl_days)
        else:
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.data, indent=2))

    @Logger(exclude_args=["self"])
    def clear_cache_entry(self) -> None:
        self.data = {}
        if self.config.cache == "dynamodb":
            from dynamorator import DynamoDBStore

            DynamoDBStore(
                table_name=self.config.cache_table, region_name=self.config.aws_region
            ).delete(self.cache_key)
        elif self.config.cache == "local":
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            if path.exists():
                path.unlink()

    # === API Fetching ===

    def _build_params(self, response_groups: str | None = None) -> dict:
        return {
            "keywords": self.keywords,
            "content_type": self.content_type,
            "size": str(self.size),
            "response_groups": response_groups or self.config.response_groups,
            "products_sort_by": "Relevance",
        }

    async def _fetch(self, client: httpx.AsyncClient, response_groups: str | None = None) -> tuple[dict | None, int]:
        base = self.config.api_base_urls.get(self.tld, f"https://api.audible.{self.tld}")
        url = f"{base}/1.0/catalog/search"
        params = self._build_params(response_groups)

        for attempt in range(1, self.config.max_retries + 1):
            try:
                r = await client.get(url, params=params)
                if r.status_code < 500:
                    return r.json() if r.status_code == 200 else None, r.status_code
                self._emit("search_failed", response_code=r.status_code, attempt=attempt, max_attempts=self.config.max_retries)
            except (httpx.HTTPError, Exception) as exc:
                _logger.debug("Search request failed for %r: %s", self.keywords, exc)
                self._emit("search_failed", response_code=None, attempt=attempt, max_attempts=self.config.max_retries)
            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.backoff_factor ** (attempt - 1))

        return None, 500

    # === Scrape ===

    @Logger(exclude_args=["self"])
    async def scrape(self, clear_cache: bool = False) -> "AudibleSearch":
        """Fetch search results from API. No-op if cached unless clear_cache=True."""
        if clear_cache:
            self.clear_cache_entry()
            self.cache_hit = False

        if self.data and not clear_cache:
            self._emit("cache_hit")
            return self

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            response_data, code = await self._fetch(client)

        self.cache_hit = False

        if response_data and code == 200:
            result_count = response_data.get("result_count") or {}
            total = result_count.get("total")
            self.data = {
                "products": response_data.get("products") or [],
                "total_results": int(total) if total else None,
                "response_code": code,
            }
            num_results = len(self.data["products"])
            self._emit("search_complete", response_code=code, num_results=num_results)
            if num_results == 0:
                self._emit("no_results")
        else:
            self.data = {"products": [], "total_results": None, "response_code": code}
            # Don't cache 5xx failures
            if code and code >= 500:
                return self

        self.save_cache()
        return self

    @Logger(exclude_args=["self"])
    async def scrape_products(self, clear_cache: bool = False) -> list["AudibleProduct"]:
        """Fetch with full response groups, return hydrated AudibleProduct instances.

        Products are cached under their normal cache key so subsequent
        AudibleProduct lookups are instant cache hits.
        """
        if clear_cache:
            self.clear_cache_entry()

        # If we have cached search data, we can try to build products from it
        # But cached data might have been fetched with lightweight response groups
        # So we always re-fetch with full groups for hydration
        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            response_data, code = await self._fetch(client, response_groups=self.config.full_response_groups)

        if not response_data or code != 200:
            return []

        result_count = response_data.get("result_count") or {}
        total = result_count.get("total")
        raw_products = response_data.get("products") or []

        # Cache the search result itself
        self.data = {
            "products": raw_products,
            "total_results": int(total) if total else None,
            "response_code": code,
        }
        self.save_cache()
        self._emit("search_complete", response_code=code, num_results=len(raw_products))

        # Hydrate into AudibleProduct instances
        results: list[AudibleProduct] = []
        for product_dict in raw_products:
            asin = product_dict.get("asin")
            if not asin:
                continue

            parsed = _parse_api_product(product_dict, self.tld)
            parsed["response_code"] = 200

            # Create AudibleProduct — __init__ calls load_cache()
            obj = AudibleProduct(tld=self.tld, asin=asin)
            if not obj.data:
                # Not already cached — populate and save
                obj.data = parsed
                obj.save_cache()
            results.append(obj)

        return results

    # === Batch Methods ===

    @classmethod
    @Logger(exclude_args=["cls"])
    async def scrape_many(
        cls,
        items: list[SearchInput],
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
    ) -> list["AudibleSearch"]:
        """Run multiple searches concurrently with throttling."""
        items = list(dict.fromkeys(items))  # Deduplicate
        objs = [cls(tld=item.tld, keywords=item.keywords, on_progress=on_progress) for item in items]
        to_search = [o for o in objs if not o.data or clear_cache]

        cls._emit_static(on_progress, "batch_started", total=len(objs), to_search=len(to_search), cached=len(objs) - len(to_search))

        if to_search:
            sem = asyncio.Semaphore(max_concurrent or cls.config.max_concurrent)
            delay = cls.config.request_delay
            delay_lock = asyncio.Lock()
            last_request_time: list[float] = [0.0]

            async def _search_one(obj: "AudibleSearch") -> None:
                async with sem:
                    if delay > 0:
                        async with delay_lock:
                            now = asyncio.get_event_loop().time()
                            wait = last_request_time[0] + delay - now
                            if wait > 0:
                                await asyncio.sleep(wait)
                            last_request_time[0] = asyncio.get_event_loop().time()
                    await obj.scrape(clear_cache=clear_cache)

            await asyncio.gather(*[_search_one(obj) for obj in to_search])

        cls._emit_static(on_progress, "batch_done", total=len(objs))
        return objs

    @classmethod
    @Logger(exclude_args=["cls"])
    async def scrape_stream(
        cls,
        items: list[SearchInput],
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
    ) -> AsyncGenerator["AudibleSearch", None]:
        """Yields cached results first, then fetched results as they complete."""
        items = list(dict.fromkeys(items))
        objs = [cls(tld=item.tld, keywords=item.keywords, on_progress=on_progress) for item in items]

        uncached: list["AudibleSearch"] = []
        for obj in objs:
            if obj.data and not clear_cache:
                yield obj
            else:
                uncached.append(obj)

        cls._emit_static(on_progress, "stream_cache_loaded", total=len(objs), cached=len(objs) - len(uncached), to_search=len(uncached))

        if not uncached:
            return

        sem = asyncio.Semaphore(max_concurrent or cls.config.max_concurrent)
        delay = cls.config.request_delay
        delay_lock = asyncio.Lock()
        last_request_time: list[float] = [0.0]

        async def _search_one(obj: "AudibleSearch") -> "AudibleSearch":
            async with sem:
                if delay > 0:
                    async with delay_lock:
                        now = asyncio.get_event_loop().time()
                        wait = last_request_time[0] + delay - now
                        if wait > 0:
                            await asyncio.sleep(wait)
                        last_request_time[0] = asyncio.get_event_loop().time()
                await obj.scrape(clear_cache=clear_cache)
                return obj

        tasks = [asyncio.create_task(_search_one(obj)) for obj in uncached]
        for task in asyncio.as_completed(tasks):
            obj = await task
            yield obj
