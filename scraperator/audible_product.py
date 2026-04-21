import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import quote_plus

import httpx
from logorator import Logger

from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import LinkedEntity, ProductIdentity, ProductInput

_logger = logging.getLogger(__name__)

_API_BASE_URLS: dict[str, str] = {
    "com": "https://api.audible.com",
    "co.uk": "https://api.audible.co.uk",
    "de": "https://api.audible.de",
    "fr": "https://api.audible.fr",
    "co.jp": "https://api.audible.co.jp",
    "ca": "https://api.audible.ca",
    "com.au": "https://api.audible.com.au",
    "it": "https://api.audible.it",
    "es": "https://api.audible.es",
    "com.br": "https://api.audible.com.br",
    "in": "https://api.audible.in",
}

_RESPONSE_GROUPS = (
    "product_desc,product_attrs,contributors,media,rating,"
    "category_ladders,relationships,tags,spotlight_tags"
)


@dataclass
class AudibleProductConfig(ScrapedModelConfig):
    api_base_urls: dict[str, str] = field(default_factory=lambda: dict(_API_BASE_URLS))
    response_groups: str = _RESPONSE_GROUPS
    image_sizes: str = "500"
    batch_size: int = 50
    request_timeout: int = 30


def _strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = re.sub(r"<[^>]+>", "", html)
    return unescape(text).strip() or None


def _parse_api_product(product: dict, tld: str) -> dict:
    base = _API_BASE_URLS.get(tld, f"https://api.audible.{tld}")

    # Authors
    authors = None
    if product.get("authors"):
        authors = []
        for a in product["authors"]:
            url = f"https://www.audible.{tld}/author/{a['asin']}" if a.get("asin") else f"https://www.audible.{tld}/search?searchAuthor={quote_plus(a['name'])}"
            authors.append({"name": a["name"], "url": url})

    # Narrators
    narrators = None
    if product.get("narrators"):
        narrators = [
            {"name": n["name"], "url": f"https://www.audible.{tld}/search?searchNarrator={quote_plus(n['name'])}"}
            for n in product["narrators"]
        ]

    # Series (from relationships)
    series = None
    series_sequence = None
    for rel in product.get("relationships") or []:
        if rel.get("relationship_type") == "series" and rel.get("relationship_to_product") == "parent":
            url = f"https://www.audible.{tld}{rel['url']}" if rel.get("url") else None
            series = {"name": rel["title"], "url": url}
            series_sequence = rel.get("sequence")
            break

    # Fall back to publication_name if no series relationship
    if not series and product.get("publication_name"):
        series = {"name": product["publication_name"], "url": None}

    # Rating
    rating_dist = (product.get("rating") or {}).get("overall_distribution") or {}
    rating = rating_dist.get("average_rating")
    num_ratings = rating_dist.get("num_ratings")

    # Publisher
    publisher_name = product.get("publisher_name")
    publisher = {"name": publisher_name, "url": None} if publisher_name else None

    # Tags
    tags = None
    if product.get("tags"):
        tags = [
            {"name": t["display_text"], "url": f"https://www.audible.{tld}/tag/{t['id']}"}
            for t in sorted(product["tags"], key=lambda t: t.get("rank", 0))
            if t.get("display_text") and t.get("id")
        ] or None

    # Spotlight tags
    spotlight_tags = None
    if product.get("spotlight_tags"):
        spotlight_tags = [
            {"name": t["display_text"], "type": t.get("type")}
            for t in sorted(product["spotlight_tags"], key=lambda t: t.get("rank", 0))
            if t.get("display_text")
        ] or None

    # Category ladders
    category_ladders = None
    if product.get("category_ladders"):
        category_ladders = [
            [{"id": node["id"], "name": node["name"]} for node in ladder.get("ladder", [])]
            for ladder in product["category_ladders"]
        ] or None

    # Image
    images = product.get("product_images") or {}
    image_url = next(iter(images.values()), None)

    # Format
    fmt = product.get("format_type")
    if fmt:
        fmt = fmt.title()

    # is_audiobook
    cdt = product.get("content_delivery_type") or ""
    is_audiobook = cdt in ("SinglePartBook", "MultiPartBook")

    # is_audible_original
    is_audible_original = "audible original" in (publisher_name or "").lower()

    return {
        "title": product.get("title"),
        "subtitle": product.get("subtitle") or None,
        "authors": authors,
        "narrators": narrators,
        "series": series,
        "series_sequence": series_sequence,
        "tags": tags,
        "spotlight_tags": spotlight_tags,
        "category_ladders": category_ladders,
        "release_date": product.get("release_date"),
        "rating": rating,
        "num_ratings": num_ratings,
        "length_minutes": product.get("runtime_length_min"),
        "publisher": publisher,
        "publisher_summary": _strip_html(product.get("merchandising_summary")),
        "language": (product.get("language") or "").title() or None,
        "format": fmt,
        "is_audiobook": is_audiobook,
        "is_audible_original": is_audible_original,
        "content_delivery_type": cdt or None,
        "is_vvab": product.get("is_vvab", False),
        "has_children": product.get("has_children", False),
        "image_url": image_url,
        "available_regions": None,
        "seo": None,
    }


class AudibleProduct(ScrapedModel):
    config: AudibleProductConfig = AudibleProductConfig()
    _URL_RE = re.compile(r"audible\.([a-z.]+)/(?:pd|podcast|ac)/[^/]*/?(B0[A-Z0-9]{8}|\d{10})(?:[?#]|$)", re.IGNORECASE)

    @staticmethod
    def is_audible_url(url: str) -> bool:
        return bool(AudibleProduct._URL_RE.search(url))

    @staticmethod
    def parse_url(url: str) -> ProductInput | None:
        m = AudibleProduct._URL_RE.search(url)
        return (m.group(1), m.group(2)) if m else None

    def __init__(
        self,
        tld: str | None = None,
        asin: str | None = None,
        url: str | None = None,
        on_progress: Callable | None = None,
    ):
        if url:
            parsed = AudibleProduct.parse_url(url)
            if not parsed:
                raise ValueError(f"Could not parse Audible product URL: {url}")
            tld, asin = parsed
        self.tld = tld
        self.asin = asin.upper()
        self._url = f"https://www.audible.{tld}/pd/{asin}"
        super().__init__(on_progress=on_progress)

    def __str__(self) -> str:
        return f"AudibleProduct({self.tld}, {self.asin})"

    @property
    def cache_key(self) -> str:
        return f"audible_product_{self.tld}_{self.asin}"

    @property
    def url(self) -> str:
        return self._url

    @property
    def _api_url(self) -> str:
        base = self.config.api_base_urls.get(self.tld, f"https://api.audible.{self.tld}")
        return f"{base}/1.0/catalog/products/{self.asin}"

    @classmethod
    def _from_input(cls, item: ProductInput) -> "AudibleProduct":
        tld, asin = item
        return cls(tld, asin)

    # === Properties ===

    @property
    def title(self) -> str | None:
        return self.data.get("title")

    @property
    def subtitle(self) -> str | None:
        return self.data.get("subtitle")

    @property
    def authors(self) -> list[LinkedEntity] | None:
        return self.data.get("authors")

    @property
    def author(self) -> LinkedEntity | None:
        authors = self.data.get("authors")
        return authors[0] if authors else None

    @property
    def narrators(self) -> list[LinkedEntity] | None:
        return self.data.get("narrators")

    @property
    def narrator(self) -> LinkedEntity | None:
        narrators = self.data.get("narrators")
        return narrators[0] if narrators else None

    @property
    def series(self) -> LinkedEntity | None:
        return self.data.get("series")

    @property
    def series_sequence(self) -> str | None:
        return self.data.get("series_sequence")

    @property
    def tags(self) -> list[LinkedEntity] | None:
        return self.data.get("tags")

    @property
    def spotlight_tags(self) -> list[dict] | None:
        return self.data.get("spotlight_tags")

    @property
    def category_ladders(self) -> list[list[dict]] | None:
        return self.data.get("category_ladders")

    @property
    def release_date(self) -> str | None:
        return self.data.get("release_date")

    @property
    def rating(self) -> float | None:
        return self.data.get("rating")

    @property
    def num_ratings(self) -> int | None:
        return self.data.get("num_ratings")

    @property
    def length_minutes(self) -> int | None:
        return self.data.get("length_minutes")

    @property
    def publisher(self) -> LinkedEntity | None:
        return self.data.get("publisher")

    @property
    def publisher_summary(self) -> str | None:
        return self.data.get("publisher_summary")

    @property
    def language(self) -> str | None:
        return self.data.get("language")

    @property
    def format(self) -> str | None:
        return self.data.get("format")

    @property
    def image_url(self) -> str | None:
        return self.data.get("image_url")

    @property
    def available_regions(self) -> dict[str, str] | None:
        return self.data.get("available_regions")

    @property
    def is_audiobook(self) -> bool:
        return self.data.get("is_audiobook", False)

    @property
    def is_audible_original(self) -> bool:
        return self.data.get("is_audible_original", False)

    @property
    def content_delivery_type(self) -> str | None:
        return self.data.get("content_delivery_type")

    @property
    def is_vvab(self) -> bool:
        return self.data.get("is_vvab", False)

    @property
    def has_children(self) -> bool:
        return self.data.get("has_children", False)

    # === Export ===

    def _identity_dict(self) -> ProductIdentity:
        return {"asin": self.asin, "tld": self.tld}

    # === API fetching ===

    async def _fetch_single(self, client: httpx.AsyncClient) -> tuple[dict | None, int]:
        params = {
            "response_groups": self.config.response_groups,
            "image_sizes": self.config.image_sizes,
        }
        for attempt in range(1, self.config.max_retries + 1):
            try:
                r = await client.get(self._api_url, params=params)
                if r.status_code < 500:
                    return r.json().get("product") if r.status_code == 200 else None, r.status_code
                self._emit("scrape_failed", response_code=r.status_code, attempt=attempt, max_attempts=self.config.max_retries)
            except (httpx.HTTPError, Exception) as exc:
                _logger.debug("API request failed for %s: %s", self.asin, exc)
                self._emit("scrape_failed", response_code=None, attempt=attempt, max_attempts=self.config.max_retries)
            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.backoff_factor ** (attempt - 1))
        return None, 500

    @Logger(exclude_args=["self"])
    async def scrape(self, clear_cache: bool = False, **kwargs) -> "AudibleProduct":
        if self.data and not clear_cache:
            self._emit("cache_hit")
            return self
        if self.data.get("all_scrapes_unsuccessful"):
            self._emit("scrape_skipped", reason="all_scrapes_unsuccessful")
            return self

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            product, code = await self._fetch_single(client)

        if product and code == 200:
            self.data = _parse_api_product(product, self.tld)
            self.data["response_code"] = code
            self._emit("parse_complete", response_code=code)
        elif code and 400 <= code < 500:
            self.data["response_code"] = code
            self.data["not_found"] = True
            self._emit("not_found", response_code=code)
        else:
            self.data["response_code"] = code
            attempts = self.data.get("scrape_attempts", 0) + 1
            self.data["scrape_attempts"] = attempts
            if attempts >= self.config.max_scrape_attempts:
                self.data["all_scrapes_unsuccessful"] = True
                self._emit("all_scrapes_unsuccessful", attempt=attempts)

        self.save_cache()
        self._emit("cache_saved")
        return self

    # === Batch ===

    @classmethod
    async def _fetch_batch(
        cls,
        client: httpx.AsyncClient,
        asins: list[str],
        tld: str,
    ) -> dict[str, tuple[dict | None, int]]:
        base = cls.config.api_base_urls.get(tld, f"https://api.audible.{tld}")
        url = f"{base}/1.0/catalog/products"
        params = {
            "asins": ",".join(asins),
            "response_groups": cls.config.response_groups,
            "image_sizes": cls.config.image_sizes,
        }
        for attempt in range(1, cls.config.max_retries + 1):
            try:
                r = await client.get(url, params=params)
                if r.status_code == 200:
                    products = r.json().get("products") or []
                    result = {p["asin"]: (p, 200) for p in products}
                    for asin in asins:
                        if asin not in result:
                            result[asin] = (None, 404)
                    return result
                if r.status_code < 500:
                    return {asin: (None, r.status_code) for asin in asins}
            except (httpx.HTTPError, Exception) as exc:
                _logger.debug("Batch API request failed: %s", exc)
            if attempt < cls.config.max_retries:
                await asyncio.sleep(cls.config.backoff_factor ** (attempt - 1))
        return {asin: (None, 500) for asin in asins}

    @classmethod
    @Logger(exclude_args=["cls"])
    async def scrape_many(
        cls,
        products: list[ProductInput],
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        **kwargs,
    ) -> list["AudibleProduct"]:
        products = list(dict.fromkeys(products))
        objs = [cls._from_input(item) for item in products]
        to_scrape = [o for o in objs if not o.data or clear_cache]

        cls._emit_static(on_progress, "batch_started", total=len(objs), to_scrape=len(to_scrape), cached=len(objs) - len(to_scrape))

        if to_scrape:
            # Group by TLD
            by_tld: dict[str, list[AudibleProduct]] = {}
            for obj in to_scrape:
                by_tld.setdefault(obj.tld, []).append(obj)

            async with httpx.AsyncClient(timeout=cls.config.request_timeout) as client:
                sem = asyncio.Semaphore(max_concurrent or cls.config.max_concurrent)

                async def _fetch_chunk(tld: str, chunk: list[AudibleProduct]):
                    async with sem:
                        obj_by_asin = {o.asin: o for o in chunk}
                        results = await cls._fetch_batch(client, list(obj_by_asin.keys()), tld)
                        for asin, (product, code) in results.items():
                            obj = obj_by_asin.get(asin)
                            if not obj:
                                continue
                            if product and code == 200:
                                obj.data = _parse_api_product(product, tld)
                                obj.data["response_code"] = code
                                obj._emit("parse_complete", response_code=code)
                            elif code and 400 <= code < 500:
                                obj.data["response_code"] = code
                                obj.data["not_found"] = True
                                obj._emit("not_found", response_code=code)
                            else:
                                obj.data["response_code"] = code
                                attempts = obj.data.get("scrape_attempts", 0) + 1
                                obj.data["scrape_attempts"] = attempts
                                if attempts >= cls.config.max_scrape_attempts:
                                    obj.data["all_scrapes_unsuccessful"] = True
                                    obj._emit("all_scrapes_unsuccessful", attempt=attempts)
                            obj.save_cache()
                            obj._emit("cache_saved")

                tasks = []
                batch_size = cls.config.batch_size
                for tld, tld_objs in by_tld.items():
                    for i in range(0, len(tld_objs), batch_size):
                        tasks.append(_fetch_chunk(tld, tld_objs[i:i + batch_size]))
                await asyncio.gather(*tasks)

        cls._emit_static(on_progress, "batch_done", total=len(objs))
        return objs

    @classmethod
    @Logger(exclude_args=["cls"])
    async def scrape_stream(
        cls,
        products: list[ProductInput],
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        **kwargs,
    ) -> AsyncGenerator["AudibleProduct", None]:
        products = list(dict.fromkeys(products))
        objs = [cls._from_input(item) for item in products]

        if not clear_cache and cls.config.cache == "dynamodb":
            for obj in objs:
                obj.cache_hit = False
                obj.data = {}
            cached_data = await asyncio.to_thread(cls._batch_load_cache, objs)
            for obj in objs:
                data = cached_data.get(obj.cache_key)
                if data and cls._is_cache_valid(data):
                    obj.data = data
                    obj.cache_hit = True

        uncached = []
        for obj in objs:
            if obj.data and not clear_cache:
                yield obj
            else:
                obj.cache_hit = False
                obj.data = {}
                uncached.append(obj)

        cls._emit_static(on_progress, "stream_cache_loaded", total=len(objs), cached=len(objs) - len(uncached), to_scrape=len(uncached))

        if not uncached:
            return

        by_tld: dict[str, list[AudibleProduct]] = {}
        for obj in uncached:
            by_tld.setdefault(obj.tld, []).append(obj)

        batch_size = cls.config.batch_size
        async with httpx.AsyncClient(timeout=cls.config.request_timeout) as client:
            for tld, tld_objs in by_tld.items():
                for i in range(0, len(tld_objs), batch_size):
                    chunk = tld_objs[i:i + batch_size]
                    obj_by_asin = {o.asin: o for o in chunk}
                    results = await cls._fetch_batch(client, list(obj_by_asin.keys()), tld)
                    for asin, (product, code) in results.items():
                        obj = obj_by_asin.get(asin)
                        if not obj:
                            continue
                        if product and code == 200:
                            obj.data = _parse_api_product(product, tld)
                            obj.data["response_code"] = code
                            obj._emit("parse_complete", response_code=code)
                        elif code and 400 <= code < 500:
                            obj.data["response_code"] = code
                            obj.data["not_found"] = True
                            obj._emit("not_found", response_code=code)
                        else:
                            obj.data["response_code"] = code
                            attempts = obj.data.get("scrape_attempts", 0) + 1
                            obj.data["scrape_attempts"] = attempts
                            if attempts >= cls.config.max_scrape_attempts:
                                obj.data["all_scrapes_unsuccessful"] = True
                                obj._emit("all_scrapes_unsuccessful", attempt=attempts)
                        obj.save_cache()
                        obj._emit("cache_saved")
                        yield obj

    # === Abstract method stubs (not used by API class) ===

    async def _parse_html(self, html: str, scraper=None) -> dict:
        raise NotImplementedError("API-based AudibleProduct does not parse HTML")
